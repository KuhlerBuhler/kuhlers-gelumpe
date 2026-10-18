# SPDX-License-Identifier: GPL-2.0-only
"""Where the ARM spends its instructions: while the firmware loads e2sSample.all at start, idle on the main screen and
while a pattern plays (docs/messungen/2026-10-18-cpu-last-und-laden.md).

    tools/emu/.venv/bin/python tools/emu/cpu_profile.py --vsb SYSTEM.VSB [--audio-seconds 20]

Busy is instructions executed times the emulator's 5 ns per instruction over device time; the rest the firmware sleeps in
wait-for-interrupt. The card is answered on the emulator's fixed raster (one interrupt per 100 us), so the loading time is
the emulator's, not the device's; what counts is the work per byte and where it goes. Counts are per 256-byte page of code.
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "tools" / "patch"))

import unicorn  # noqa: E402
from unicorn import arm_const as A  # noqa: E402
import cardstore  # noqa: E402
import fat32  # noqa: E402
import loadbar_cases  # noqa: E402
import sampleset  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402

NS = 5


def top(counts, n=12):
    total = sum(counts.values()) or 1
    return [(f"{page:#010x}", round(c / total * 100, 1)) for page, c in counts.most_common(n)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--audio-seconds", type=float, default=20.0)
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    image = fat32.format_image(256 * 1024 * 1024)
    volume = fat32.Volume(image)
    data = sampleset.build(sampleset.sized(20, int(a.audio_seconds * 48000)))
    volume.write(f"KORG/{cardstore.card_folder(payload)}/Sample/e2sSample.all", data)
    volume.close()
    dev = loadbar_cases.WatchedDev(payload, None, 0)
    m, uc = dev.m, dev.m.uc
    m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    counts, span = collections.Counter(), {"on": False, "t0": None, "t1": None}

    def block(_u, address, size, _d):
        if span["on"]:
            counts[address & ~0xFF] += size // 4

    def enter(u, _a, _s, _d):
        if span["t0"] is not None:
            return
        span.update(on=True, t0=m.time_ns)

        def leave(*_):
            if span["on"]:
                span.update(on=False, t1=m.time_ns)
        lr = u.reg_read(A.UC_ARM_REG_LR)
        u.hook_add(unicorn.UC_HOOK_CODE, leave, begin=lr, end=lr)
        u.ctl_flush_tb()

    uc.hook_add(unicorn.UC_HOOK_BLOCK, block)
    uc.hook_add(unicorn.UC_HOOK_CODE, enter, begin=loadbar_cases.LOADER, end=loadbar_cases.LOADER)
    while m.time_ns < 120e9 and span["t1"] is None and not m.asserts:
        dev.run(0.05)
    total = sum(counts.values())
    length = (span["t1"] or m.time_ns) - span["t0"]
    print(f"load: file {len(data)} bytes, loader {length / 1e6:.1f} ms of emulator time, {total / len(data):.1f} instructions per byte, "
          f"busy {total * NS / length * 100:.1f}%")
    print("  pages", top(counts))
    dev.run(1.0)
    for label, key in (("idle", None), ("playing", 0x02)):
        if key is not None:
            m.press(key, True)
            dev.run(0.05)
            m.press(key, False)
            dev.run(0.5)
        counts.clear()
        span["on"] = True
        uc.ctl_flush_tb()
        t0 = m.time_ns
        dev.run(2.0)
        span["on"] = False
        print(f"{label}: busy {sum(counts.values()) * NS / (m.time_ns - t0) * 100:.1f}%")
        print("  pages", top(counts, 8))


if __name__ == "__main__":
    main()
