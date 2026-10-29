"""Builds the blechtribe patch: the firmware's card folder becomes KORG/blechtribe.

Two strings of the firmware's path table are rewritten in place: the folder name (`hacktribe`, or
`electribe sampler` in Korg's own build) and the relative path `KORG/<folder>/`. The new text is
`blechtribe` and fits the window the old one stood in; what is left of the window becomes zeros. The
firmware builds every card path from these (the sample file, the exports, the script files), so after
the patch a card needs KORG/blechtribe/ where it had the old folder.

The blue Electribe 2 (the synth) names its folder `electribe`, in windows too short for `blechtribe`. Its
name and path functions (0xC0032520, 0xC003256C) pick the string by the device type: 0x123, its own, from
the third word of their pools, 0x124 from the first, `electribe sampler` and `KORG/electribe sampler/`,
which the synth never asks for. The patch writes `blechtribe` into those two longer windows and points the
two 0x123 words at them. Both builds keep the strings at the
same addresses and nothing points into the middle of them (measured, every literal in the image that
points into the table points at a string start). Reads the VSB only for the checksums of the bytes it
replaces; no firmware bytes go into the patch. The build is read from the VSB, the two variants share
the id `blechtribe` and differ in `builds`.

    python3 tools/patch/blechtribe.py --vsb SYSTEM.VSB [--out data/patches/blechtribe.json]
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HEADER = 0x100
RAM = 0xC0000000
HACKTRIBE_CODE = (0x170100, 0x40)    # erased in Korg's own build, same rule as src/firmware.mjs buildOf
NEW = (b"blechtribe\0", b"KORG/blechtribe/\0")
# per build: (address, the window the old text stands in with its zero padding), one per string of NEW
WINDOWS = {
    "hacktribe": [(0xC00A5656, b"hacktribe\0\0"), (0xC00A5678, b"KORG/hacktribe/\0\0")],
    "stock": [(0xC00A5656, b"electribe sampler\0"), (0xC00A5678, b"KORG/electribe sampler/\0")],
}
WHY = "the firmware reads its card folder name from this string while it builds the sample path at start"
# the synth: the 0x124 windows get the new text, the 0x123 pool words (address, old target, new target) point at them
SYNTH_WINDOWS = [(0xC00904C2, b"electribe sampler\0"), (0xC00904E4, b"KORG/electribe sampler/\0")]
SYNTH_POINTERS = [(0xC0032568, 0xC00904B8, 0xC00904C2), (0xC00325B4, 0xC00904D4, 0xC00904E4)]
WINDOWS["synth"] = SYNTH_WINDOWS
WHY_POINTER = "the folder functions of the synth take the card folder of device type 0x123 from this pool word"


def file_offset(address):
    return address - RAM + HEADER


def build_of(raw):
    run = raw[HACKTRIBE_CODE[0]:HACKTRIBE_CODE[0] + HACKTRIBE_CODE[1]]
    if run != b"\xff" * HACKTRIBE_CODE[1]:
        return "hacktribe"
    return "synth" if raw[0x10:0x13] == b"E2\0" else "stock"


def inside_references(raw, windows):
    """Addresses of 32-bit literals that point into the middle of a window: they would read a changed string from there."""
    words = struct.unpack_from(f"<{(len(raw) - HEADER) // 4}I", raw, HEADER)
    return [RAM + 4 * i for i, w in enumerate(words)
            if any(a < w < a + len(old) for a, old in windows)]


def build_patch(raw, build=None):
    build = build or build_of(raw)
    changes, spans = [], []
    if (bad := inside_references(raw, WINDOWS[build])):
        raise ValueError(f"literals at {', '.join(map(hex, bad))} point into the middle of a folder string")
    for (address, old), text in zip(WINDOWS[build], NEW):
        at = file_offset(address)
        new = text.ljust(len(old), b"\0")
        if len(new) != len(old):
            raise ValueError("the new text must fit the window")
        if raw[at:at + len(old)] != old:
            raise ValueError(f"unexpected bytes at {address:#x}: this is not the measured {build} firmware")
        changes.append({"file": at, "bytes": new.hex(), "expect": hashlib.sha256(old).hexdigest()})
        spans.append({"file": at, "length": len(old), "why": WHY})
    for address, old, new in SYNTH_POINTERS if build == "synth" else ():
        at = file_offset(address)
        if raw[at:at + 4] != struct.pack("<I", old):
            raise ValueError(f"unexpected word at {address:#x}: this is not the measured synth firmware")
        changes.append({"file": at, "bytes": struct.pack("<I", new).hex(), "expect": hashlib.sha256(struct.pack("<I", old)).hexdigest()})
        spans.append({"file": at, "length": 4, "why": WHY_POINTER})
    return {
        "format": "gelumpe-patch", "version": 1, "id": "blechtribe",
        "name": "Kartenordner blechtribe statt " + {"hacktribe": "hacktribe", "stock": "electribe sampler", "synth": "electribe"}[build],
        "builds": [build],
        "changes": changes,
        "startPhase": spans,
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
