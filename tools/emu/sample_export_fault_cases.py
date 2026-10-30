"""Native single-sample export with generated PCM and emulator-only DSP faults."""
import argparse
import json
import struct
from pathlib import Path

import native_dsp_scope_cases as native
import sample_export_fault

c = native.c
CODE = 0xC100D000


def case(payload, failure, guarded=True):
    if failure not in ('none', 'preexisting', 'read'):
        raise ValueError('unknown export failure')
    sample_export_fault.validate_firmware(native.validation_image(payload))
    box = c.Box(payload, None, {500: ('Own export fault', 2001)}, [500], record_dsp=True)
    box.m.dsp_mem.update(box.dsp)
    native.install(box, poll_budget=native.io.POLL_BUDGET)
    installed = native.runtime_symbols(payload) is not None
    if installed and not guarded:
        raise ValueError('the installed export guards cannot be disabled by this probe')
    if guarded and not installed:
        code, labels = sample_export_fault.build_code(CODE, fault=c.spec.STATE + c.spec.OFF['TSTATE'])
        box.m.uc.mem_write(CODE, code)
        for site, label in sample_export_fault.HOOKS:
            box.m.uc.mem_write(site, struct.pack('<I', c.spec.redirect(0xEA000000, site, labels[label])))
    box.m.uc.mem_write(c.WORK_BUFFER, bytes([0xA5]) * 0x10000)
    if failure == 'preexisting':
        box.m.uc.mem_write(c.spec.STATE + c.spec.OFF['TSTATE'], struct.pack('<I', 1))
    generation, cursor, extent = box.state('GEN'), box.u32(c.CURSOR), box.extent(500)
    observed = dict(releases=0, closes=0, writes_after_fault=0)

    def released(*_):
        observed['releases'] += 1

    def closed(*_):
        observed['closes'] += 1

    def writing(*_):
        if box.state('TSTATE'):
            observed['writes_after_fault'] += 1

    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, released, begin=0xC0036A08, end=0xC0036A08)
    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, closed, begin=0xC009E3DC, end=0xC009E3DC)
    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, writing, begin=0xC009DFB8, end=0xC009DFB8)
    read = box.m.read

    def stuck(address):
        return 0 if failure == 'read' and address == c.DSP_DATA + 2 else read(address)

    box.m.read = stuck
    if failure == 'read':
        native.as_swap_step(box)
    result = box.dev.call(0xC0039CC4, 0xC100A000, 500)
    # The stall ends with the export. Native traffic after the fault is no longer bounded (only the swap's own step is),
    # so a DSP that stayed dead would hold up the next native transaction as in Korg's firmware.
    box.m.read = read
    box.run(0.2)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        files = [(path, volume.read(path)) for path, _ in volume.walk() if path.lower().endswith('.wav')]
    finally:
        volume.close()
    expected = c.wav_pcm(500, 2001)
    rows = [dict(path=path, bytes=len(data), pcm_equal=data[44:44 + len(expected)] == expected) for path, data in files]
    file_ok = (len(rows) == 1 and rows[0]['pcm_equal'] if failure == 'none' else not rows if failure == 'preexisting'
               else len(rows) == 1 and rows[0]['bytes'] == 44)
    fault = int(failure != 'none')
    ok = ((result != 0) == bool(fault) and file_ok and box.state('TSTATE') == fault
          and box.state('GEN') == generation + int(failure != 'preexisting') + int(failure == 'read')
          and box.u32(c.CURSOR) == cursor and box.extent(500) == extent
          and box.u32(native.POINTER) == 0 and box.u32(native.io.SEMA) == 1 and not box.m.asserts
          and observed['releases'] == observed['closes'] == int(failure != 'preexisting')
          and observed['writes_after_fault'] == 0)
    return dict(ok=ok, failure=failure, guarded=guarded, runtime_guards=installed, result=result, fault=box.state('TSTATE'),
                files=rows, generation=[generation, box.state('GEN')], cursor=[cursor, box.u32(c.CURSOR)],
                extent=[extent, box.extent(500)], scope=box.u32(native.POINTER), semaphore=box.u32(native.io.SEMA),
                **observed, asserts=box.m.asserts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    parser.add_argument('--unguarded', action='store_true')
    args = parser.parse_args()
    payload = args.patched.read_bytes()[256:]
    results = [case(payload, failure, not args.unguarded) for failure in ('none', 'preexisting', 'read')]
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, firmware_patch_changed=False,
                         emulator_hooks=True, results=results), indent=2))
    return 0 if all(item['ok'] for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
