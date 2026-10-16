"""Measure writes into the synth's free image run during startup and playback."""
import argparse
import json
from pathlib import Path

from machine import Machine, load_flash

FREE_START, FREE_END = 0xC01217F4, 0xC01FFFF0


def probe(raw, flash):
    import unicorn
    payload = raw[0x100:]
    dev = Machine(payload, flash)
    if dev.profile.build != 'synth':
        raise ValueError('the probe needs the blue synth firmware')
    writes = set()
    dev.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                    lambda uc, access, addr, size, value, data: writes.add((addr, size)),
                    begin=FREE_START, end=FREE_END - 1)
    dev.run_until(0.3)
    dev.finish_boot()
    dev.press(2, True)
    dev.run_until(dev.time_ns / 1e9 + 0.05)
    dev.press(2, False)
    dev.run_until(dev.time_ns / 1e9 + 2)
    image_free = payload[FREE_START - 0xC0000000:FREE_END - 0xC0000000]
    result = {'range': [hex(FREE_START), hex(FREE_END)], 'bytes': len(image_free),
              'image_ff': image_free == b'\xff' * len(image_free),
              'writes': [[hex(a), n] for a, n in sorted(writes)],
              'screen': dev.screen(), 'asserts': dev.asserts, 'device_ms': dev.time_ns / 1e6}
    result['ok'] = result['image_ff'] and not writes and dev.screen() == 1 and not dev.asserts
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vsb', type=Path, required=True)
    p.add_argument('--flash', type=Path, nargs='*', default=[])
    args = p.parse_args()
    result = probe(args.vsb.read_bytes(), load_flash(args.flash) if args.flash else None)
    print(json.dumps(result, indent=1))
    raise SystemExit(0 if result['ok'] else 1)
