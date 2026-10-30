"""Probe native transaction recovery in the installed runtime or with emulator-only hooks."""
import argparse
from collections import deque
import json
import struct
import sys
from pathlib import Path

import swap_cases as c
import native_dsp_scope as scope
import sample_swap_io as io

CODE, CALL = 0xC1005000, 0xC100A000
POINTER = c.spec.NATIVE_SCOPE
RESOURCE_SITES = scope.RESOURCE_SITES
TARGETS = dict(command=c.spec.FIRMWARE['PART_UPDATE'], stereo=c.spec.FIRMWARE['PART_UPDATE'],
               read=0xC00141F8, write=0xC0014284,
               **{'0xc0012758': 0xC0012758, '0xc001430c': 0xC001430C, '0xc00143e4': 0xC00143E4})


def runtime_symbols(payload):
    sections, symbols = c.spec.build_code(c.firmware.identify(payload).screens)
    original, installed = [], []
    for site, word, target, label in scope.HOOKS:
        actual = struct.unpack_from('<I', payload, site - c.IMAGE)[0]
        original.append(actual == (word if word is not None else c.spec.redirect(0xEB000000, site, target)))
        installed.append(actual == c.spec.redirect(0xEB000000, site, symbols[label]))
    if all(original):
        return None
    if not all(installed):
        raise ValueError('mixed or unknown native DSP hooks')
    for at, data in sections:
        skip = 4 if at == c.spec.CODE1 else 0
        if payload[at - c.IMAGE + skip:at - c.IMAGE + len(data)] != data[skip:]:
            raise ValueError('native DSP runtime differs from the current builder')
    for site, _, _, label, link, _, _ in c.spec.SITES:
        expected = c.spec.redirect(0xEB000000 if link else 0xEA000000, site, symbols[label])
        if struct.unpack_from('<I', payload, site - c.IMAGE)[0] != expected:
            raise ValueError('sample runtime hook differs from the current builder')
    return symbols


def validation_image(payload):
    symbols = runtime_symbols(payload)
    reference = bytearray(payload)
    if symbols is not None:
        for site, original, target, _, _, _, _ in c.spec.SITES:
            word = original if original is not None else c.spec.redirect(0xEB000000, site, target)
            struct.pack_into('<I', reference, site - c.IMAGE, word)
    image = bytes(256) + reference
    scope.validate_firmware(image)
    return image


def validate(payload):
    validation_image(payload)


def install(box, *, origin=CODE, poll_budget=128):
    """Use the verified runtime driver or install it into a paused emulator."""
    payload = box.payload
    validate(payload)
    installed = runtime_symbols(payload)
    if installed is not None:
        return installed
    uc = box.m.uc
    code, symbols = scope.build_driver_code(origin, scope=POINTER,
                                    fault=c.spec.STATE + c.spec.OFF['TSTATE'],
                                    mode=c.spec.STATE + c.spec.OFF['MODE'],
                                    generation=c.spec.STATE + c.spec.OFF['GEN'], poll_budget=poll_budget)
    uc.mem_write(origin, code)
    uc.mem_write(POINTER, struct.pack('<I', 0))
    for acquire, release in RESOURCE_SITES:
        for site, native, replacement in ((acquire, scope.ACQUIRE, symbols['native_scope_take']),
                                           (release, io.RELEASE, symbols['native_scope_close'])):
            expected = c.spec.redirect(0xEB000000, site, native)
            if struct.unpack_from('<I', payload, site - 0xC0000000)[0] != expected:
                raise ValueError('native DSP resource call differs')
            uc.mem_write(site, struct.pack('<I', c.spec.redirect(0xEB000000, site, replacement)))
    for sites, label in ((scope.CONTROL_SITES, 'native_scope_control'), (scope.GPIO_SITES, 'native_scope_gpio')):
        for site in sites:
            uc.mem_write(site, struct.pack('<I', c.spec.redirect(0xEB000000, site, symbols[label])))
    return symbols


def watch_resource(box, symbols):
    """Keep recent resource-1 calls, including returns rejected by the kernel."""
    uc, regs = box.m.uc, box.m.A
    recent, failed, pending = deque(maxlen=32), [], {}
    returns = {0xC0000E0C: (4, 0), 0xC0000D30: (8, 4), 0xC0000D5C: (8, 4), 0xC0000D70: (8, 4)}

    def entered(kind):
        def record(machine, *_):
            if machine.reg_read(regs.UC_ARM_REG_R0) != 1:
                return
            link, stack = machine.reg_read(regs.UC_ARM_REG_LR), machine.reg_read(regs.UC_ARM_REG_SP)
            row = dict(kind=kind, link=link, stack=stack, counter=box.u32(io.SEMA),
                       control=machine.reg_read(regs.UC_ARM_REG_CPSR) & 255,
                       caller=box.u32(stack + 4) if link == symbols['native_scope_acquired'] else link)
            pending[link, stack] = row
            recent.append(dict(stage='enter', **row))
        return record

    def returned(machine, address, *_):
        size, link_offset = returns[address]
        stack = machine.reg_read(regs.UC_ARM_REG_SP)
        row = pending.pop((box.u32(stack + link_offset), stack + size), None)
        if row is not None:
            result = dict(stage='return', **row, result=machine.reg_read(regs.UC_ARM_REG_R0), counter_after=box.u32(io.SEMA))
            recent.append(result)
            if result['result'] and len(failed) < 8:
                failed.append(result)
                print(json.dumps(dict(resource_failure=result)), file=sys.stderr, flush=True)

    for address, kind in ((scope.ACQUIRE, 'take'), (io.RELEASE, 'release')):
        uc.hook_add(c.unicorn.UC_HOOK_CODE, entered(kind), begin=address, end=address)
    for address in returns:
        uc.hook_add(c.unicorn.UC_HOOK_CODE, returned, begin=address, end=address)
    return lambda: dict(recent=list(recent), failed=failed, pending=list(pending.values()))


def session(payload, flow=None, trace_resource=False):
    """Run the native mode sequence with recovery code outside the work buffer."""
    import capture_fault

    observations = []

    class ScopedBox(c.Box):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            capture_fault.validate_firmware(validation_image(self.payload))
            sections, _ = c.spec.build_code(c.firmware.identify(self.payload).screens)
            last = max(at + len(data) for at, data in sections if c.spec.STORE_CODE <= at < c.spec.STORE_CODE_END)
            if runtime_symbols(self.payload) is not None:
                start, end = c.spec.STORE_CODE, last
                symbols = install(self)
            else:
                start = (last + 15) & ~15
                code, _ = scope.build_driver_code(start, scope=POINTER,
                                              fault=c.spec.STATE + c.spec.OFF['TSTATE'],
                                              mode=c.spec.STATE + c.spec.OFF['MODE'],
                                              generation=c.spec.STATE + c.spec.OFF['GEN'])
                finish = (start + len(code) + 15) & ~15
                end = finish + 0x100
                if end > c.spec.STORE_CODE_END or any(value != 255 for value in self.payload[start - c.IMAGE:end - c.IMAGE]):
                    raise ValueError('no unused owned code space for the session')
                symbols = install(self, origin=start, poll_budget=io.POLL_BUDGET)
                code, labels = capture_fault.build_code(finish, fault=c.spec.STATE + c.spec.OFF['TSTATE'])
                if finish + len(code) > end:
                    raise ValueError('capture guards exceed the session code space')
                self.m.uc.mem_write(finish, code)
                for site, label in capture_fault.HOOKS:
                    self.m.uc.mem_write(site, struct.pack('<I', c.spec.redirect(0xEA000000, site, labels[label])))
            resource = watch_resource(self, symbols) if trace_resource else lambda: None
            expected = bytes(self.m.uc.mem_read(start, end - start))
            observed = dict(transactions=0, refused=0, faults=0, failures=[], origin=start, bytes=end - start)
            observations.append((self, observed, expected, resource))
            for label, key in (('native_scope_enter', 'transactions'), ('native_scope_refused', 'refused'), ('native_scope_abort', 'faults')):
                def count(*_, key=key):
                    observed[key] += 1
                    if key != 'transactions' and len(observed['failures']) < 8:
                        fp = self.m.uc.reg_read(self.m.A.UC_ARM_REG_R11)
                        observed['failures'].append(dict(kind=key, caller=self.u32(fp),
                                                        control=self.m.uc.reg_read(self.m.A.UC_ARM_REG_CPSR) & 255))
                self.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, count, begin=symbols[label], end=symbols[label])

    try:
        checks = (c.case_full_session(payload, None, box_type=ScopedBox) if flow is None
                  else c.flow_task(payload, None, flow, box_type=ScopedBox))
    except Exception:
        print(json.dumps([observed for _, observed, _, _ in observations]), file=sys.stderr)
        raise
    rows = []
    for box, observed, expected, resource in observations:
        observed.update(code_unchanged=bytes(box.m.uc.mem_read(observed['origin'], observed['bytes'])) == expected,
                        fault=box.state('TSTATE'), scope=box.u32(POINTER), semaphore=box.u32(io.SEMA), resource=resource())
        rows.append(observed)
    ok = (all(check['ok'] for check in checks) and bool(rows)
          and all(row['transactions'] > 0 and row['refused'] == row['faults'] == row['fault'] == row['scope'] == 0
                  and row['semaphore'] == 1 and row['code_unchanged'] for row in rows))
    return dict(ok=ok, checks=checks, observations=rows, boot_scoped=False)


def probe(payload, stall=None, transaction='command', masked=False):
    if transaction not in TARGETS:
        raise ValueError('unknown native transaction')
    if stall == 'busy-status' and transaction != 'command':
        raise ValueError('busy-status applies to the command status loop')
    validate(payload)
    stereo = transaction == 'stereo'
    samples = {500: ('Own', 100), 501: ('Own stereo', 100, 48000, 'stereo16')} if stereo else {500: ('Own', 100)}
    box = c.Box(payload, None, samples, [500, 500, 500] if stereo else [500], record_dsp=True)
    symbols = install(box)
    runtime = runtime_symbols(payload) is not None
    uc = box.m.uc
    target = TARGETS[transaction]
    assembly = (f"push {{r4, lr}}\n.word 0xe10f4000\norr r12, r4, #0x80\n.word 0xe121f00c\nbl {target}\n.word 0xe121f004\ncall_return:\npop {{r4, pc}}" if masked
                else f"push {{r4, lr}}\nbl {target}\ncall_return:\npop {{r4, pc}}")
    assembled = c.spec.arm.assemble(assembly, origin=CALL)
    uc.mem_write(CALL, assembled.bytes)
    return_site = assembled.symbols['call_return']

    active, enters, releases, writes, writes_after_fault = [False], [], [], [], []
    frames, transition = [], {}

    def frame(machine):
        return dict(stack=machine.reg_read(box.m.A.UC_ARM_REG_SP),
                    link=machine.reg_read(box.m.A.UC_ARM_REG_LR),
                    control=machine.reg_read(box.m.A.UC_ARM_REG_CPSR) & 0xFF,
                    saved=[machine.reg_read(box.m.A.UC_ARM_REG_R4 + i) for i in range(8)])

    def called(machine, *args):
        active[0] = True
        frames.append(frame(machine))
        if stereo:
            part = machine.reg_read(box.m.A.UC_ARM_REG_R0)
            transition.update(part=part, before=box.u16(part + 0x34))
            uc.mem_write(box.u32(part + 8) + 8, struct.pack('<H', 501))

    def returning(machine, *args):
        observed = frame(machine)
        observed['popped'] = [box.u32(observed['stack'] + i * 4) for i in range(2)]
        frames.append(observed)

    uc.hook_add(c.unicorn.UC_HOOK_CODE, called, begin=CALL, end=CALL)
    uc.hook_add(c.unicorn.UC_HOOK_CODE, returning, begin=return_site, end=return_site)
    for address in (symbols['native_scope_enter'], symbols['native_scope_refused']):
        uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda machine, *args: enters.append(machine.reg_read(box.m.A.UC_ARM_REG_R0)) if active[0] else None,
                    begin=address, end=address)

    def released(machine, *args):
        if active[0] and machine.reg_read(box.m.A.UC_ARM_REG_R0) == 1:
            releases.append(box.u32(POINTER))

    uc.hook_add(c.unicorn.UC_HOOK_CODE, released, begin=io.RELEASE, end=io.RELEASE)
    read, write = box.m.read, box.m.write

    def stalled(address):
        if active[0]:
            if address == c.DSP_DATA + 2 and stall == 'status':
                return 0
            if address == c.DSP_DATA + 2 and stall == 'busy-status':
                return 0xD0
            if address == io.GPIO and stall == 'gpio':
                return 0
            if address == io.GPIO and stall == 'data-gpio' and len(writes) >= 7:
                return 2
        return read(address)

    def written(address, value):
        if active[0] and address in (c.DSP_DATA, c.DSP_DATA + 2):
            writes.append(address)
            if box.state('TSTATE') != 0:
                writes_after_fault.append(address)
        write(address, value)

    box.m.read, box.m.write = stalled, written
    if stereo:
        box.dev.call(0xC009A0A8, 0xFFFFFFFF)
        for part in (0, 2):
            box.m.send([4, part, 0, 100, 1])
            box.run(0.1)
    if transaction in ('command', 'stereo'):
        arguments = [box.dev.call(c.spec.FIRMWARE['PART'], 0)]
    elif transaction in ('read', 'write'):
        arguments = [io.DSP_MIN, c.spec.STAGE, 32, 2]
        for i in range(32):
            if transaction == 'read':
                box.m.dsp_mem[io.DSP_MIN + i * 2] = 0x4000 + i
            else:
                uc.mem_write(c.spec.STAGE + i * 2, struct.pack('<H', 0x4000 + i))
    else:
        arguments = []
    before = dict(generation=box.state('GEN'), resource=box.u32(io.SEMA))
    try:
        box.dev.call(CALL, *arguments)
    finally:
        active[0] = False
        box.m.read, box.m.write = read, write
    after = dict(generation=box.state('GEN'), resource=box.u32(io.SEMA), mode=box.state('MODE'),
                 fault=box.state('TSTATE'), scope=box.u32(POINTER))
    refused = any(value != 0 for value in enters)
    expected_fault = int(stall is not None or masked)
    pcm_matches = (None if transaction not in ('read', 'write') or expected_fault else
                   all((box.u16(c.spec.STAGE + i * 2) if transaction == 'read' else box.dsp.get(io.DSP_MIN + i * 2)) == 0x4000 + i for i in range(32)))
    frame_restored = (len(frames) == 2 and frames[1]['stack'] == frames[0]['stack'] - 8
                      and frames[1]['control'] == frames[0]['control']
                      and frames[1]['saved'][1:] == frames[0]['saved'][1:]
                      and frames[1]['popped'] == [frames[0]['saved'][0], frames[0]['link']])
    ok = (after['fault'] == expected_fault and after['generation'] == before['generation'] + expected_fault
          and before['resource'] == after['resource'] == 1 and after['scope'] == 0
          and sum(value == 0 for value in enters) == len(releases) and len(enters) > 0 and all(value == 0 for value in releases)
          and not writes_after_fault and pcm_matches is not False and frame_restored and refused == masked
          and not box.m.asserts and (after['mode'] == 2 if expected_fault else len(writes) > 0)
          and (not writes if refused or stall in ('status', 'busy-status', 'gpio') else len(writes) == 7 if stall == 'data-gpio' else True))
    if stereo:
        transition.update(after=box.u16(transition['part'] + 0x34),
                          kind=uc.mem_read(transition['part'] + 0x39, 1)[0])
        if not expected_fault:
            import stereo_pad_cases
            kind, transactions = (4, 10) if stereo_pad_cases.has_hooks(payload) else (3, 11)
            ok = (ok and transition['before'] == 500 and transition['after'] == 501
                  and transition['kind'] == kind and len(enters) == transactions)
    return dict(ok=ok, stall=stall, transaction=transaction, masked=masked, refused=refused, runtime_driver=runtime,
                transition=transition if stereo else None,
                pcm_matches=pcm_matches, frame_restored=frame_restored,
                before=before, after=after, transactions=len(enters),
                releases=len(releases), acquire_results=enters, port_writes=len(writes),
                writes_after_fault=len(writes_after_fault), asserts=box.m.asserts)


def large_transfer(payload, flash=None):
    length = 2 * 1024 * 1024
    box = c.Box(payload, flash, {500: ('Own large probe', 100)}, [500], record_dsp=True)
    install(box, poll_budget=io.POLL_BUDGET)
    source = c.spec.ARENA_U
    pcm = bytes((i * 17) % 256 for i in range(length))
    box.m.uc.mem_write(source, pcm)
    call = c.spec.arm.assemble('push {r4, lr}\nbl 0xC0014284\npop {r4, pc}', origin=CALL)
    box.m.uc.mem_write(CALL, call.bytes)
    start, done, calls = box.m.time_ns, 0, 0
    while done < length and box.state('TSTATE') == 0:
        count = min(length - done, 0xFFF0 * 2)
        box.dev.call(CALL, io.DSP_MIN + done, source + done, count // 2, 2)
        done += count
        calls += 1
    equal = done == length and box.dsp_bytes(io.DSP_MIN, length) == pcm
    ok = equal and box.state('TSTATE') == 0 and box.u32(POINTER) == 0 and box.u32(io.SEMA) == 1 and not box.m.asserts
    return dict(id='native_large_transfer_uses_bounded_u16_calls', ok=bool(ok), pcm_equal=equal,
                bytes=length, native_calls=calls, maximum_halfwords=0xFFF0, fault=box.state('TSTATE'),
                elapsed_emulator_ms=(box.m.time_ns - start) / 1000000,
                runtime_driver=runtime_symbols(payload) is not None, asserts=box.m.asserts)


def cold_state(payload, flash=None, *, held=False):
    box = c.Box(payload, flash, {500: ('Own cold probe', 100)}, [500], held=c.spec.KILL if held else 0)
    pointer = box.u32(POINTER)
    return dict(id='native_cold_exit_passthrough' if held else 'native_cold_library_initialization',
                ok=pointer == (0xFFFFFFFF if held else 0) and box.state('TSTATE') == 0 and not box.m.asserts,
                scope=pointer, fault=box.state('TSTATE'), asserts=box.m.asserts)


def runtime_cases(payload, flash=None):
    if runtime_symbols(payload) is None:
        raise ValueError('native DSP runtime hooks are not installed')
    rows = [cold_state(payload, flash), cold_state(payload, flash, held=True), large_transfer(payload, flash)]
    choices = [(None, name, False) for name in ('command', 'stereo', 'read', 'write')]
    choices += [('status', name, False) for name in ('command', 'read', 'write')]
    choices += [('busy-status', 'command', False), ('gpio', 'write', False),
                ('data-gpio', 'write', False), (None, 'command', True)]
    for stall, transaction, masked in choices:
        row = probe(payload, stall, transaction, masked)
        row['id'] = f'native_{transaction}_{stall or "ready"}_' + ('masked' if masked else 'unmasked')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    parser.add_argument('--stall', choices=('none', 'status', 'busy-status', 'gpio', 'data-gpio'), default='none')
    parser.add_argument('--transaction', choices=tuple(TARGETS), default='command')
    parser.add_argument('--masked', action='store_true', help='call native code with IRQs disabled')
    parser.add_argument('--session', action='store_true', help='run native mode transitions after boot with bounded recovery')
    parser.add_argument('--flow', type=int, choices=range(len(c.FLOWS)), help='isolate one mode in the session')
    parser.add_argument('--trace-resource', action='store_true', help='record native resource-1 kernel calls in a session')
    args = parser.parse_args()
    payload = args.patched.read_bytes()[256:]
    if (args.flow is not None or args.trace_resource) and not args.session:
        parser.error('--flow and --trace-resource require --session')
    result = session(payload, args.flow, args.trace_resource) if args.session else probe(payload, None if args.stall == 'none' else args.stall, args.transaction, args.masked)
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, firmware_patch_changed=False, emulator_hooks=True, result=result), indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
