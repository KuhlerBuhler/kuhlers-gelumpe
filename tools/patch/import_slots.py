"""Builds the import-slots patch (IMPORT SAMPLE onto the factory sample slots, docs/messungen/2026-11-16-import-werks-slots.md) for firmware 2.02, Hacktribe and Korg's own build.

DATA UTILITY > IMPORT SAMPLE asks for the destination in a selector (0xC006A224) that keeps the number in 0xC00F9CCC
(the display number, the slot is the number minus one) and wraps it at 501 and 999: only the user slots can be chosen.
The import itself (message 0x22, the slot function 0xC004EDF0) takes any slot whose wave id is above 49. Below that it
refuses the slot with code 36, which the firmware shows as "Error / Unknown Error.". Those are the oscillator slots,
one run from slot 0: 0 to 17 in Korg's build (the DSP waves and the audio inputs), 0 to 273 in Hacktribe's (its synth
waves as well). This patch moves the selector's lower end from 501 to the first slot the import takes, 19 or 275, and
keeps 999 as the upper end. The seven instructions from 0xC006A23C on get a range test against that number:

    sub r3, r1, #HI        r3 is free here, the selector loads it again at 0xC006A260
    cmp r3, #LO            HI + LO is the lowest number
    addlt r1, r1, #SPAN    below it: wrap to the top, SPAN = 1000 - lowest number, in two encodable parts
    cmp r1, #1000
    subge r1, r1, #SPAN    above 999: wrap to the lowest number

The sample then replaces the factory sample in that slot as it would a user sample, and the firmware writes it to
e2sSample.all with the others. Factory samples stay in the firmware image: a slot that gets its sample back from a
restore or a cleared e2sSample.all plays the factory sample again. The blue Electribe 2 (synth) has no IMPORT SAMPLE.
The build is read from the VSB; the two variants share the id `import-slots` and differ in `builds`.

    python3 tools/patch/import_slots.py --vsb SYSTEM.VSB [--out data/patches/import-slots.json]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000
HACKTRIBE_CODE = (0x170100, 0x40)    # erased in Korg's own build, same rule as src/firmware.mjs buildOf

SITE = 0xC006A23C                    # the selector's range test: cmp r1, #500 up to subge r1, r1, #3
WAS = bytes.fromhex("7d0f51e31f1e81d2031081d2020000dafa0f51e31f1e41a2031041a2")
TOP = 999
# the lowest number the import takes: one past the run of oscillator slots (wave id 49 or below) from slot 0
LOWEST = {"stock": 19, "hacktribe": 275}
WHY = "the destination selector of DATA UTILITY > IMPORT SAMPLE wraps at the first slot the import takes instead of at 501"


def file_offset(address):
    return address - RAM + HEADER


def build_of(raw):
    run = raw[HACKTRIBE_CODE[0]:HACKTRIBE_CODE[0] + HACKTRIBE_CODE[1]]
    if run != b"\xff" * HACKTRIBE_CODE[1]:
        return "hacktribe"
    if raw[0x10:0x13] == b"E2\0":
        raise ValueError("the synth has no IMPORT SAMPLE")
    return "stock"


def parts(value):
    """value as the sum of two ARM immediates, the larger first."""
    for low in range(0, 256):
        if arm.encode_immediate(value - low) is not None:
            return value - low, low
    raise ValueError(f"{value} is not the sum of two immediates")


def source(lowest):
    hi, lo = (lowest & ~0xFF, lowest & 0xFF) if lowest > 255 else (0, lowest)
    s_hi, s_lo = parts(TOP + 1 - lowest)
    return f"""
.org {SITE:#x}
    sub r3, r1, #{hi:#x}
    cmp r3, #{lo:#x}
    addlt r1, r1, #{s_hi:#x}
    addlt r1, r1, #{s_lo:#x}
    cmp r1, #{TOP + 1:#x}
    subge r1, r1, #{s_hi:#x}
    subge r1, r1, #{s_lo:#x}
"""


def build_patch(raw, build=None):
    build = build or build_of(raw)
    at = file_offset(SITE)
    if raw[at:at + len(WAS)] != WAS:
        raise ValueError(f"unexpected bytes at {SITE:#x}: this is not the measured {build} firmware")
    (origin, code), = arm.assemble(source(LOWEST[build])).sections
    if origin != SITE or len(code) != len(WAS):
        raise ValueError(f"the range test is {len(code)} bytes, it must replace {len(WAS)}")
    return {
        "format": "gelumpe-patch", "version": 1, "id": "import-slots",
        "name": "Import auf Werks-Slots",
        "builds": [build],
        "changes": [{"file": at, "bytes": code.hex(), "expect": hashlib.sha256(WAS).hexdigest(),
                     "note": f"IMPORT SAMPLE: the destination runs from {LOWEST[build]} to {TOP} instead of 501 to {TOP}"}],
        "hooks": [{"site": f"0x{SITE:08X}", "kind": "instruction", "chain": "import-destination", "position": "replace",
                   "swallow": False, "note": WHY}],
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
