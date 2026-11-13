"""Native WAV imports propagate bounded PCM failures using generated samples."""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c
import sample_protection_cases as protection

SOURCE_PATH = 0xC1008000


def case(payload, frames, failure):
    box = c.Box(payload, None, c.small(range(500, 506)), [500], cap=0x40000,
                record_dsp=True, extra={'/input.wav': c.plain_wav(frames).hex()})
    protection.unbind(box)
    original = protection.library(box, payload)
    box.m.uc.mem_write(SOURCE_PATH, b'SD:/input.wav\0')
    target = 0xC00141F8 if failure == 'read' else 0xC0014284
    active = [False]
    writes_after_fault = []
    entered = []
    generation_at_transfer = []

    def enter(uc, address, size, data):
        entered.append(address)
        generation_at_transfer.append(box.state('GEN'))
        active[0] = failure != 'none'

    box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, enter, begin=target, end=target)
    read, write = box.m.read, box.m.write

    def stalled(address):
        if active[0] and address == c.DSP_DATA + 2:
            return 0
        return read(address)

    def written(address, value):
        if address in (c.DSP_DATA, c.DSP_DATA + 2) and box.state('TSTATE') == c.spec.sample_swap_io.LATCHED:
            writes_after_fault.append(address)
        return write(address, value)

    box.m.read, box.m.write = stalled, written
    before = box.state('GEN')
    try:
        result = box.dev.call(0xC003644C, SOURCE_PATH, 502)
    finally:
        box.m.read, box.m.write = read, write
    fault = failure != 'none'
    status = 4 if fault else 0
    signature = box.u32(c.spec.SIG + 502 * 4)
    physical = box.meta_index(502)
    extent = box.extent(502)
    native_scope = box.u32(c.spec.NATIVE_SCOPE)
    unchanged = protection.library(box, payload) == original
    preserved = box.state('TSTATE') == (c.spec.sample_swap_io.LATCHED if fault else 0)
    ok = (result == status and bool(entered) and preserved and unchanged and not writes_after_fault
          and native_scope == 0 and box.u32(c.spec.sample_swap_io.SEMA) == 1 and not box.m.asserts
          and box.state('GEN') == generation_at_transfer[-1] + int(fault) and (signature == 0 if fault else extent[1] == frames * 2))
    return dict(id=f'native_import_{frames}_frames_{failure}', ok=bool(ok), result=result,
                native_calls=len(entered), fault=box.state('TSTATE'), scope=native_scope,
                physical=physical, extent=extent, signature=signature,
                generation_before=before, generation_at_transfer=generation_at_transfer,
                generation_after=box.state('GEN'), semaphore=box.u32(c.spec.sample_swap_io.SEMA),
                library_unchanged=unchanged, writes_after_fault=len(writes_after_fault),
                asserts=box.m.asserts)


def cases(payload):
    return [case(payload, frames, failure) for frames, failure in
            ((1, 'none'), (1, 'read'), (16, 'none'), (16, 'write'), (17, 'none'), (17, 'write'))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    args = parser.parse_args()
    results = cases(args.patched.read_bytes()[256:])
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, results=results), indent=2))
    return 0 if all(row['ok'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
