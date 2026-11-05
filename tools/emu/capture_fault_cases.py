"""Capture completion after DSP faults, using installed or emulator-only guards."""
import argparse
import json
import struct
from pathlib import Path

import native_dsp_scope_cases as native
import capture_fault

c = native.c
CODE, CALL = 0xC100D000, native.CALL


def case(payload, failure, guarded=True):
    native.validate(payload)
    capture_fault.validate_firmware(native.validation_image(payload))
    box = c.Box(payload, None, {500: ('Own before capture', 2001)}, [500], record_dsp=True)
    uc = box.m.uc
    transport = box.dev.call(0xC0030D28)
    cursor = box.u32(c.CURSOR)
    native.install(box)
    installed = native.runtime_symbols(payload) is not None
    if installed and not guarded:
        raise ValueError('the installed capture guards cannot be disabled by this probe')
    if guarded and not installed:
        code, symbols = capture_fault.build_code(CODE, fault=c.spec.STATE + c.spec.OFF['TSTATE'])
        uc.mem_write(CODE, code)
        for site, label in capture_fault.HOOKS:
            uc.mem_write(site, struct.pack('<I', c.spec.redirect(0xEA000000, site, symbols[label])))
    started = box.dev.call(0xC0082F1C, transport, 0)
    pcm = c.wav_pcm(501, 1025)
    end = cursor + len(pcm)
    box.m.dsp_mem[0xFF903210], box.m.dsp_mem[0xFF903212] = end & 0xFFFF, end >> 16
    for at in range(0, len(pcm), 2):
        box.m.dsp_mem[cursor + at] = struct.unpack_from('<H', pcm, at)[0]

    if failure == 'preexisting':
        uc.mem_write(c.spec.STATE + c.spec.OFF['TSTATE'], struct.pack('<I', 1))
        uc.mem_write(c.spec.STATE + c.spec.OFF['MODE'], struct.pack('<I', 2))
    regions = [(c.META, 999 * 0x45C), (c.NAMES, 999 * 32),
               (c.spec.FIRMWARE['MAP_A'], 999 * 32),
               (c.spec.FIRMWARE['MAP_B'], 999 * 16), (c.spec.FIRMWARE['MAP_C'], 999 * 8)]
    before_tables = [bytes(uc.mem_read(at, size)) for at, size in regions]
    old = bytes(uc.mem_read(c.META + box.meta_index(500) * 0x45C, 0x45C))
    before_generation = box.state('GEN')
    assembly = 'push {r4, lr}\nbl 0xc0082d40\nreturned:\npop {r4, pc}'
    compiled = c.spec.arm.assemble(assembly, origin=CALL)
    uc.mem_write(CALL, compiled.bytes)
    active, reading, frames, writes_after_fault = [False], [False], [], []

    def frame(machine):
        return (machine.reg_read(box.m.A.UC_ARM_REG_SP),
                machine.reg_read(box.m.A.UC_ARM_REG_CPSR) & 0xFF,
                [machine.reg_read(box.m.A.UC_ARM_REG_R4 + i) for i in range(8)],
                machine.reg_read(box.m.A.UC_ARM_REG_LR))

    def enter(machine, *args):
        active[0] = True
        frames.append(frame(machine))

    def returned(machine, *args):
        value = frame(machine)
        frames.append((value, [box.u32(value[0] + i * 4) for i in range(2)]))

    uc.hook_add(c.unicorn.UC_HOOK_CODE, enter, begin=CALL, end=CALL)
    uc.hook_add(c.unicorn.UC_HOOK_CODE, returned, begin=compiled.symbols['returned'], end=compiled.symbols['returned'])
    uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda *args: reading.__setitem__(0, True), begin=0xC004E23C, end=0xC004E23C)
    read, write = box.m.read, box.m.write

    def stalled(address):
        if active[0] and address == c.DSP_DATA + 2 and (failure == 'stop' or failure == 'end' and reading[0]):
            return 0
        return read(address)

    def written(address, value):
        if active[0] and address in (c.DSP_DATA, c.DSP_DATA + 2) and box.state('TSTATE') != 0:
            writes_after_fault.append(address)
        return write(address, value)

    box.m.read, box.m.write = stalled, written
    if failure in ('stop', 'end'):
        native.as_swap_step(box)
    restart = None
    try:
        box.dev.call(CALL, transport)
        if failure != 'none':
            box.dev.call(0xC004F20C, 0, 2)
            restart = box.dev.call(0xC0082F1C, transport, 0)
    finally:
        active[0] = False
        box.m.read, box.m.write = read, write
    after_tables = [bytes(uc.mem_read(at, size)) for at, size in regions]
    unchanged = before_tables == after_tables
    old_kept = old == bytes(uc.mem_read(c.META + box.meta_index(500) * 0x45C, 0x45C))
    expected_fault = int(failure != 'none')
    completed = box.resident(501) and box.extent(501) == (cursor, len(pcm)) and box.u32(c.CURSOR) == end
    refused = unchanged and not box.resident(501) and box.u32(c.CURSOR) == cursor
    restored = (len(frames) == 2 and frames[1][0][0] == frames[0][0] - 8
                and frames[1][0][1] == frames[0][1] and frames[1][0][2][1:] == frames[0][2][1:]
                and frames[1][1] == [frames[0][2][0], frames[0][3]])
    recording = box.u32(transport + 0x308)
    ok = (started == 1 and old_kept and restored and not writes_after_fault and not box.m.asserts
          and box.state('TSTATE') == expected_fault and box.u32(native.POINTER) == 0 and box.u32(native.io.SEMA) == 1
          and box.state('GEN') == before_generation + int(failure in ('stop', 'end'))
          and (refused and recording == 11 and restart == 0 if expected_fault else completed and recording == 12))
    return dict(ok=ok, failure=failure, guarded=guarded, runtime_guards=installed, completed=completed, refused=refused,
                tables_unchanged=unchanged, old_sample_kept=old_kept, frame_restored=restored,
                recording=recording, restart=restart, cursor=box.u32(c.CURSOR), target_extent=box.extent(501),
                fault=box.state('TSTATE'), writes_after_fault=len(writes_after_fault), asserts=box.m.asserts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    parser.add_argument('--unguarded', action='store_true')
    args = parser.parse_args()
    payload = args.patched.read_bytes()[256:]
    results = [case(payload, failure, not args.unguarded) for failure in ('none', 'preexisting', 'stop', 'end')]
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, firmware_patch_changed=False,
                         emulator_hooks=True, results=results), indent=2))
    return 0 if all(item['ok'] for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
