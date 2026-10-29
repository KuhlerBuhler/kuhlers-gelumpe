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


def cases(payload, flash=None):
    sections, _ = c.spec.build_code(c.firmware.identify(payload).screens)
    if any(payload[at - c.IMAGE:at - c.IMAGE + len(data)] != data for at, data in sections):
        raise ValueError('patched runtime differs from the current builder')
    return [publication(payload, flash), *[descriptor(payload, flash, offset=offset, during_copy=during)
                                          for offset, during in ((44, False), (48, False), (48, True))]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    args = parser.parse_args()
    rows = cases(args.patched.read_bytes()[256:])
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, results=rows), indent=2))
    return 0 if all(row['ok'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
