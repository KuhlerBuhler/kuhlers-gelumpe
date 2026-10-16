"""Builds the blechtribe patch: the firmware's card folder becomes KORG/blechtribe.

Two strings of the firmware's path table are rewritten in place: the folder name (`hacktribe`, or
`electribe sampler` in Korg's own build) and the relative path `KORG/<folder>/`. The new text is
`blechtribe` and fits the window the old one stood in; what is left of the window becomes zeros. The
firmware builds every card path from these (the sample file, the exports, the script files), so after
the patch a card needs KORG/blechtribe/ where it had the old folder. Both builds keep the strings at the
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


def file_offset(address):
    return address - RAM + HEADER


def build_of(raw):
    run = raw[HACKTRIBE_CODE[0]:HACKTRIBE_CODE[0] + HACKTRIBE_CODE[1]]
    return "stock" if run == b"\xff" * HACKTRIBE_CODE[1] else "hacktribe"


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
    return {
        "format": "gelumpe-patch", "version": 1, "id": "blechtribe",
        "name": "Kartenordner blechtribe statt " + ("hacktribe" if build == "hacktribe" else "electribe sampler"),
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
