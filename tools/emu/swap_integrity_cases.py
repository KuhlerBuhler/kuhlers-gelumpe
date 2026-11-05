"""Generated-sample regressions for atomic publication and cached descriptors."""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c


def publication(payload, flash=None):
    box = c.Box(payload, flash, c.small(range(500, 510)), [500], bank={1: [501]}, cap=0x40000)
    masks = []

    def preempt(machine, *_):
        if machine.reg_read(box.m.A.UC_ARM_REG_R0) != c.spec.DESC2:
            return
        masked = bool(machine.reg_read(box.m.A.UC_ARM_REG_CPSR) & 128)
        masks.append(masked)
        if not masked:
            machine.mem_write(c.spec.STATE + c.spec.OFF['GEN'], struct.pack('<I', box.state('GEN') + 1))

    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, preempt,
                      begin=c.spec.FIRMWARE['RESERVE'], end=c.spec.FIRMWARE['RESERVE'])
    generation = box.state('GEN')
    box.key('play', 0.2)
    box.choose(1)
    loaded = box.until(lambda: box.resident(501), 5)
    ok = loaded and masks and all(masks) and box.state('GEN') == generation and not box.m.asserts
    return dict(id='publication_defers_ui_preemption', ok=bool(ok), loaded=loaded,
                native_publication_irq_masks=masks, generation_before=generation,
                generation_after=box.state('GEN'), asserts=box.m.asserts)


def descriptor(payload, flash=None, *, offset=48, during_copy=False):
    box = c.Box(payload, flash, c.small(range(500, 506)), [500], bank={1: [502]}, cap=0x40000, record_dsp=True)
    box.key('play', 0.2)
    filled = box.until(lambda: box.cached(502), 8)
    cache = box.u32(c.spec.DIR + 502 * 16)
    generation = box.state('GEN')
    mutations, published = [], []

    def mutate(machine, *_):
        if mutations:
            return
        if during_copy and (machine.reg_read(box.m.A.UC_ARM_REG_R0) != c.spec.DESC2
                            or machine.reg_read(box.m.A.UC_ARM_REG_R1) != cache):
            return
        machine.mem_write(cache + offset, struct.pack('<I', 8000000))
        mutations.append(offset)

    def reserve(machine, *_):
        if machine.reg_read(box.m.A.UC_ARM_REG_R0) == c.spec.DESC2:
            published.append(box.u32(c.spec.DESC2 + offset))

    if filled:
        if during_copy:
            box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, mutate, begin=box.sym['copy32'], end=box.sym['copy32'])
        else:
            mutate(box.m.uc)
    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, reserve,
                      begin=c.spec.FIRMWARE['RESERVE'], end=c.spec.FIRMWARE['RESERVE'])
    box.choose(1)
    loaded = box.until(lambda: box.resident(502), 10)
    pcm_equal = loaded and box.dsp_bytes(*box.extent(502)) == c.wav_pcm(502, c.FRAMES)
    ok = (filled and mutations and loaded and pcm_equal and box.state('GEN') > generation
          and box.state('STAT_SRC') == 0 and published and 8000000 not in published and not box.m.asserts)
    return dict(id=f'descriptor_{offset}_corruption_' + ('during_copy' if during_copy else 'before_load'),
                ok=bool(ok), filled=filled, loaded=loaded, generation_before=generation,
                generation_after=box.state('GEN'), source=box.state('STAT_SRC'),
                published_values=published, pcm_equal=pcm_equal, asserts=box.m.asserts)


def cache_handoff(payload, flash=None):
    box = c.Box(payload, flash, c.small(range(500, 506)), [500], cap=0x40000)
    uc, arm = box.m.uc, box.m.A
    sections, _ = c.spec.build_code(c.firmware.identify(payload).screens)
    end = max(at + len(data) for at, data in sections if c.spec.STORE_CODE <= at < c.spec.STORE_CODE_END)
    origin = (end + 15) & ~15
    probe = c.spec.arm.assemble(f'''
pcm:
    push {{r4, r10, r11, lr}}
    ldr r11, ={c.spec.STATE}
    mov r0, #{c.spec.sample_owner.READ}
    bl {box.sym['owner_acquire']}
    cmp r0, #0
    popne {{r4, r10, r11, pc}}
    mov r10, r1
    bl {box.sym['chunk']}
    b release
descriptor:
    push {{r4, r10, r11, lr}}
    ldr r11, ={c.spec.STATE}
    mov r0, #{c.spec.sample_owner.READ}
    bl {box.sym['owner_acquire']}
    cmp r0, #0
    popne {{r4, r10, r11, pc}}
    mov r10, r1
    ldr r0, =501
    bl {box.sym['start_prepare']}
release:
    mov r4, r0
    mov r0, r10
    bl {box.sym['owner_release']}
    mov r0, r4
    pop {{r4, r10, r11, pc}}
handoff_return:
    bx lr
.pool
''', origin=origin)
    if origin + len(probe.bytes) > c.spec.STORE_CODE_END:
        raise ValueError('handoff probe exceeds unused owned code space')
    if payload[origin - c.IMAGE:origin - c.IMAGE + len(probe.bytes)] != b'\xff' * len(probe.bytes):
        raise ValueError('handoff probe code space is occupied')
    uc.mem_write(origin, probe.bytes)
    rows = []
    registers = [arm.UC_ARM_REG_R0 + i for i in range(13)] + [arm.UC_ARM_REG_SP, arm.UC_ARM_REG_LR,
                                                          arm.UC_ARM_REG_PC]
    for kind in ('pcm', 'descriptor'):
        for after_read in (False, True):
            generation = box.state('GEN')
            destination = c.spec.ARENA_L + (0x4A0 if kind == 'pcm' else 0)
            length = 96 if kind == 'pcm' else 0x4A0
            source = c.spec.STAGE if kind == 'pcm' else c.spec.DESC
            foreign = b'\xa5' * length
            state = dict(copying=False, pending=False, handed=False, writes=0, giver=False)
            values = dict(J_GEN=generation, J_STATE=1 if kind == 'pcm' else 0, J_SRC=0, J_DST=1,
                          J_BASE=c.spec.ARENA_L, J_LEN=96, J_STAGED=96 if kind == 'pcm' else 0,
                          J_SLOT=501, J_DONE=0, CPTR=c.spec.ARENA_L, CGEN=generation)
            for name, value in values.items():
                uc.mem_write(c.spec.STATE + c.spec.OFF[name], struct.pack('<I', value))
            uc.mem_write(c.spec.DIR + 501 * 16, bytes(16))
            uc.mem_write(c.spec.STAGE, bytes(range(96)))
            before = bytes(uc.mem_read(c.META, c.spec.SAMPLE_COUNT * 0x45C))

            def code(machine, at, size, _):
                if at == probe.symbols['handoff_return']:
                    state['giver'] = (machine.reg_read(arm.UC_ARM_REG_R0) == c.WORK_BUFFER
                                      and box.u32(c.spec.STAGE + c.spec.CHUNK) == 0x1A00100)
                    machine.mem_write(destination, foreign)
                    machine.reg_write(arm.UC_ARM_REG_CPSR, state['control'])
                    for register, value in zip(registers, state['saved']):
                        machine.reg_write(register, value)
                    state['handed'] = True
                    return
                if (not state['handed'] and at == box.sym['copy32']
                        and machine.reg_read(arm.UC_ARM_REG_R0) == destination):
                    state['copying'] = True
                    state['pending'] = not after_read
                if state['pending'] and not machine.reg_read(arm.UC_ARM_REG_CPSR) & 0x80:
                    state['pending'] = False
                    state['control'] = machine.reg_read(arm.UC_ARM_REG_CPSR)
                    state['saved'] = [machine.reg_read(register) for register in registers]
                    machine.reg_write(arm.UC_ARM_REG_R0, c.spec.STAGE + c.spec.CHUNK)
                    machine.reg_write(arm.UC_ARM_REG_LR, probe.symbols['handoff_return'])
                    machine.reg_write(arm.UC_ARM_REG_PC, 0xC00369F0)

            def read(machine, access, at, size, value, _):
                if after_read and state['copying'] and not state['handed']:
                    state['pending'] = True

            def write(machine, access, at, size, value, _):
                if state['handed']:
                    state['writes'] += 1

            hooks = [uc.hook_add(c.unicorn.UC_HOOK_CODE, code),
                     uc.hook_add(c.unicorn.UC_HOOK_MEM_READ, read, begin=source, end=source + length - 1),
                     uc.hook_add(c.unicorn.UC_HOOK_MEM_WRITE, write,
                                 begin=destination, end=destination + length - 1)]
            uc.ctl_flush_tb()
            try:
                box.dev.call(probe.symbols[kind])
            finally:
                for hook in hooks:
                    uc.hook_del(hook)
                uc.ctl_flush_tb()
            preserved = bytes(uc.mem_read(destination, length)) == foreign
            unchanged = bytes(uc.mem_read(c.META, len(before))) == before
            ok = (state['handed'] and state['giver'] and state['writes'] == 0 and preserved and unchanged
                  and box.state('GEN') == generation + 1 and box.state('J_STATE') == 0
                  and box.u32(c.spec.DIR + 501 * 16) == 0 and not box.m.asserts)
            rows.append(dict(kind=kind, after_read=after_read, ok=bool(ok),
                             native_giver=state['giver'], foreign_buffer_preserved=preserved,
                             writes_after_handoff=state['writes'], metadata_unchanged=unchanged))
    return dict(id='cache_copy_work_buffer_handoff', ok=all(row['ok'] for row in rows),
                cases=rows, asserts=box.m.asserts)


def exit_bypass(payload, flash=None, *, release_during_open=False):
    folder = c.cardstore.card_folder(payload)
    path = f'KORG/{folder}/Sample/e2sSample.all'
    journal_path = path[:-3] + 'txn'
    journal = b'bad journal' + bytes(4160 - 11)
    samples = {500: ('Own EXIT sample', 100), 501: ('Own next sample', 200)}
    original = c.sampleset.build(samples)
    released = []

    def before_boot(box):
        def opening(machine, *_):
            pointer = machine.reg_read(box.m.A.UC_ARM_REG_R1)
            name = bytes(machine.mem_read(pointer, 128)).split(b'\0', 1)[0]
            panel = box.u32(c.spec.FIRMWARE['PANEL'])
            if not released and panel and name.endswith(b'/Sample/e2sSample.all'):
                keys = box.u32(panel + 0x18) & ~c.spec.KILL
                machine.mem_write(panel + 0x18, struct.pack('<I', keys))
                released.append(True)
        box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, opening,
                          begin=c.spec.FIRMWARE['F_OPEN'], end=c.spec.FIRMWARE['F_OPEN'])

    box = c.Box(payload, flash, samples, [500], held=c.spec.KILL, cap=0x200,
                extra={journal_path: journal.hex()}, before_boot=before_boot if release_during_open else None)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        retained = volume.read(journal_path) == journal
        unchanged = volume.read(path) == original
    finally:
        volume.close()
    name = bytes(box.m.uc.mem_read(c.NAMES + 500 * 32 + 12, 16)).split(b'\0', 1)[0]
    loaded = name == b'Own EXIT sample' and box.resident(500)
    scope = box.u32(c.spec.NATIVE_SCOPE)
    return dict(id='exit_bypasses_invalid_journal' + ('_key_released_during_open' if release_during_open else ''),
                ok=(box.state('MODE') == 0 and loaded and retained and unchanged and not box.m.asserts
                    and scope == 0xFFFFFFFF and (not release_during_open or bool(released))),
                mode=box.state('MODE'), sample_loaded=loaded, journal_retained=retained,
                library_unchanged=unchanged, released_during_open=bool(released), native_scope=scope,
                asserts=box.m.asserts)


def part_faults(payload, flash=None):
    box = c.Box(payload, flash, c.small(range(500, 506)), [500], cap=0x40000)
    uc = box.m.uc
    sections, _ = c.spec.build_code(c.firmware.identify(payload).screens)
    end = max(at + len(data) for at, data in sections if c.spec.STORE_CODE <= at < c.spec.STORE_CODE_END)
    origin = (end + 15) & ~15
    code = c.spec.arm.assemble(f'''
    push {{r11, lr}}
    ldr r11, ={c.spec.STATE}
    bl {box.sym['part_ready']}
    pop {{r11, pc}}
.pool
''', origin=origin)
    if (origin + len(code.bytes) > c.spec.STORE_CODE_END
            or payload[origin - c.IMAGE:origin - c.IMAGE + len(code.bytes)] != b'\xff' * len(code.bytes)):
        raise ValueError('part probe has no unused owned code space')
    uc.mem_write(origin, code.bytes)
    part = box.dev.call(c.spec.FIRMWARE['PART'], 0)
    record = box.u32(part + 8)
    rows, active, entered, writes = [], [False], [], []
    original_write = box.m.write

    def write(address, value):
        if active[0] and address in (c.DSP_DATA, c.DSP_DATA + 2):
            writes.append(address)
        return original_write(address, value)

    box.m.write = write
    uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda *_: entered.append(True),
                begin=0xC009A000, end=0xC009A000)
    uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda *_: active.__setitem__(0, True),
                begin=c.spec.FIRMWARE['PART_UPDATE'], end=c.spec.FIRMWARE['PART_UPDATE'])
    for fault in (0, 1):
        for target in (400, 500, 501):
            uc.mem_write(c.spec.STATE + c.spec.OFF['MODE'], struct.pack('<I', 2))
            uc.mem_write(c.spec.STATE + c.spec.OFF['TSTATE'], struct.pack('<I', fault))
            uc.mem_write(record + 8, struct.pack('<H', target))
            # a latched DSP fault holds back indexed user samples only, a factory sample still binds
            allowed = target != 501 and (fault == 0 or not 500 <= target <= c.spec.LAST_USER)
            ready = box.dev.call(origin, part)
            entered.clear()
            writes.clear()
            before = box.u16(part + 0x34)
            try:
                box.dev.call(c.spec.FIRMWARE['PART_UPDATE'], part)
            finally:
                active[0] = False
            actual = box.u16(part + 0x34)
            ok = (ready == int(allowed) and bool(entered) == allowed
                  and actual == (target if allowed else before))
            if not allowed:
                ok = ok and not writes
            rows.append(dict(target=target, fault=fault, ready=ready, actual_before=before, actual_after=actual,
                             native_continued=bool(entered), port_writes=len(writes), ok=bool(ok)))
    return dict(id='card_and_dsp_faults_keep_distinct_part_guards',
                ok=all(row['ok'] for row in rows) and not box.m.asserts, cases=rows, asserts=box.m.asserts)


def lost_notification(payload, flash=None):
    box = c.Box(payload, flash, c.small(range(500, 510)), [500], bank={5: [505]}, cap=0x40000)
    _, symbols = c.spec.build_code(c.firmware.identify(payload).screens)
    dropped, dispatched = [], []

    def discard(machine, *_):
        if not dropped:
            dropped.append(box.m.time_ns)
            machine.reg_write(box.m.A.UC_ARM_REG_PC, machine.reg_read(box.m.A.UC_ARM_REG_LR))
        else:
            dispatched.append(box.m.time_ns)

    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, discard, begin=symbols['ss_step'], end=symbols['ss_step'])
    box.key('play', 0.2)
    box.choose(5)
    box.run(0.5)
    waited = not box.resident(505) and not dispatched
    recovered = box.until(lambda: box.resident(505) and box.running() == 5, 8)
    delay = (dispatched[0] - dropped[0]) / 1e9 if dispatched and dropped else None
    return dict(id='lost_notification_retries_without_an_early_switch',
                ok=bool(dropped and waited and recovered and delay >= 1.5 and not box.m.asserts),
                dropped=len(dropped), waited=waited, recovered=recovered, retry_emulator_seconds=delay,
                asserts=box.m.asserts)


def selection_cancellation(payload, flash=None):
    samples = c.small(range(500, 510))
    samples[501] = ('Own invalid', 0, 48000, 'junk')
    box = c.Box(payload, flash, samples, [500], bank={1: [501], 5: [505]}, cap=0x40000)
    box.key('play', 0.2)
    box.choose(1)
    failed = box.until(lambda: box.state('REQ') == 1 and box.running() == 0
                       and bool(box.u32(c.spec.STATE + c.spec.FAILED + 4 * (501 >> 5)) & (1 << (501 & 31))), 8)
    box.choose(0)
    cancelled = box.state('REQ') == 0xFFFFFFFF
    box.choose(5)
    new_choice = box.state('REQ') == 0xFFFFFFFF
    switched = box.until(lambda: box.running() == 5 and box.resident(505), 8)
    return dict(id='an_accepted_choice_replaces_an_impossible_target',
                ok=bool(failed and cancelled and new_choice and switched and not box.m.asserts),
                failed_target_waited=failed, cancellation_acknowledged=cancelled,
                new_choice_acknowledged=new_choice, switched=switched, asserts=box.m.asserts)


def faulted_pattern(payload, flash=None):
    box = c.Box(payload, flash, c.small(range(500, 510)), [500], bank={5: [500]}, cap=0x40000)
    box.key('play', 0.2)
    box.m.uc.mem_write(c.spec.STATE + c.spec.OFF['TSTATE'], struct.pack('<I', 1))
    box.m.uc.mem_write(c.spec.STATE + c.spec.OFF['MODE'], struct.pack('<I', 2))
    box.choose(5)
    box.run(4)
    return dict(id='a_dsp_fault_does_not_switch_even_to_resident_pcm',
                ok=box.running() == 0 and box.state('REQ') == 5 and box.resident(500) and not box.m.asserts,
                running=box.running(), requested=box.state('REQ'), pcm_resident=box.resident(500), asserts=box.m.asserts)


def cases(payload, flash=None):
    sections, _ = c.spec.build_code(c.firmware.identify(payload).screens)
    if any(payload[at - c.IMAGE:at - c.IMAGE + len(data)] != data for at, data in sections):
        raise ValueError('patched runtime differs from the current builder')
    return [publication(payload, flash), *[descriptor(payload, flash, offset=offset, during_copy=during)
                                          for offset, during in ((44, False), (48, False), (48, True))],
            cache_handoff(payload, flash), exit_bypass(payload, flash),
            exit_bypass(payload, flash, release_during_open=True), part_faults(payload, flash), lost_notification(payload, flash),
            selection_cancellation(payload, flash), faulted_pattern(payload, flash)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    args = parser.parse_args()
    rows = cases(args.patched.read_bytes()[256:])
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, results=rows), indent=2))
    return 0 if all(row['ok'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
