"""Builds the touch-scale-zero patch: a value 0 on the page TOUCH SCALE RANGE of the Global menu, the touch pad's X then plays
the pattern's key note in the octave of the keyboard (docs/messungen/2026-10-30-touch-scale-null.md).

The global byte 38 holds the range in octaves, 1 to 4 on the device. The firmware copies it into the touch scale object
(0xC06911E4, +0x14) and maps X (0 to 127) to a step of the scale: slots = steps x range + 1, step = X x slots / 128, octave =
step / steps + the keyboard's octave (+0x18), degree = step % steps. Range 0 already gives one slot, so the firmware plays the
key note there, but one octave below the keyboard's (C3 where KEYBOARD pad 1 plays C4).

Two places:
  menu   the clamp of the page (0xC007A940, movle r1, #1) takes 0: movle r1, #0. The page shows "0 Oct" without a change.
  notes  the mapping (0xC0060654, 11 words) sets the flags with its first multiply (muls: zero only for range 0) and puts the
         step to `steps` for range 0 (moveq r7, r5): octave + 1, degree 0. To make room, lsl #9 then lsr #16 becomes lsr #7,
         the same number for every input (the product is below 2^16). Ranges 1 to 4 map as before.

No code of our own, no start phase, no RAM. Range 0 on Korg's firmware without BLECH plays the key note an octave lower.

    python3 tools/patch/touch_scale_zero.py --vsb SYSTEM.VSB [--out data/patches/touch-scale-zero.json]
    python3 tools/patch/touch_scale_zero.py --vsb blue/SYSTEM.VSB --build synth [--out data/patches/touch-scale-zero-synth.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import synthaddr  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

MENU_MOV = 0xC007A940           # movle r1, #1: the low end of the page TOUCH SCALE RANGE
MAPPING = 0xC0060654            # ldr r7, [r4, #0x14]: X to a step of the scale
FIRMWARE_PLACES = ["MENU_MOV", "MAPPING"]

MOVLE_1, MOVLE_0 = 0xD3A01001, 0xD3A01000

# The firmware's 11 words at MAPPING (equal in all three builds) and what the patch puts there.
ORIGINAL = [
    0xE5947014,     # ldr  r7, [r4, #0x14]     range
    0xE1D433B0,     # ldrh r3, [r4, #0x30]     X, 0 to 127
    0xE0070790,     # mul  r7, r0, r7          steps x range
    0xE20050FF,     # and  r5, r0, #0xff       steps
    0xE2877001,     # add  r7, r7, #1
    0xE20770FF,     # and  r7, r7, #0xff       slots
    0xE0070793,     # mul  r7, r3, r7
    0xE1A01005,     # mov  r1, r5
    0xE1A07487,     # lsl  r7, r7, #9
    0xE1A07827,     # lsr  r7, r7, #16         step
    0xE1A00007,     # mov  r0, r7              to the division by steps
]
PATCHED = [
    0xE5947014,     # ldr  r7, [r4, #0x14]
    0xE1D433B0,     # ldrh r3, [r4, #0x30]
    0xE0170790,     # muls r7, r0, r7          Z for range 0
    0xE20050FF,     # and  r5, r0, #0xff
    0xE2877001,     # add  r7, r7, #1
    0xE20770FF,     # and  r7, r7, #0xff
    0xE0070793,     # mul  r7, r3, r7          (no flags)
    0xE1A073A7,     # lsr  r7, r7, #7          the same as lsl #9, lsr #16 here
    0x01A07005,     # moveq r7, r5             range 0: step = steps, the key note an octave up
    0xE1A01005,     # mov  r1, r5
    0xE1A00007,     # mov  r0, r7
]


def use_build(build):
    """For the synth (the blue Electribe 2) the firmware's places have their own addresses (data/synth-map/)."""
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def word(vsb, addr):
    return struct.unpack_from("<I", vsb, file_offset(addr))[0]


def raw(vsb, addr, new, note):
    old = vsb[file_offset(addr):file_offset(addr) + len(new)]
    return {"file": file_offset(addr), "bytes": new.hex(), "expect": sha(old), "note": note}


def build_patch(vsb, build="hacktribe"):
    synth = build == "synth"
    if word(vsb, MENU_MOV) != MOVLE_1 or word(vsb, MENU_MOV - 4) != 0xE3510000 or word(vsb, MENU_MOV + 8) != 0xE3510004:
        raise SystemExit(f"the clamp of the page TOUCH SCALE RANGE is not cmp r1, #0; movle r1, #1 ... cmp r1, #4 at {MENU_MOV:#x}")
    found = [word(vsb, MAPPING + 4 * i) for i in range(len(ORIGINAL))]
    if found != ORIGINAL:
        raise SystemExit(f"the touch scale mapping at {MAPPING:#x} is not the one the patch expects")
    changes = [
        raw(vsb, MENU_MOV, struct.pack("<I", MOVLE_0), "the page TOUCH SCALE RANGE goes down to 0 (movle r1, #0)"),
        raw(vsb, MAPPING, b"".join(struct.pack("<I", w) for w in PATCHED),
            "touch scale: range 0 plays the key note in the keyboard's octave (muls sets Z, moveq r7, r5); ranges 1 to 4 as before"),
    ]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "touch-scale-zero",
        "name": "TOUCH SCALE RANGE 0",
        "builds": ["synth"] if synth else ["hacktribe", "stock"],
        "changes": changes,
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    use_build(a.build)
    raw_vsb = a.vsb.read_bytes()
    if len(raw_vsb) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw_vsb, a.build), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
