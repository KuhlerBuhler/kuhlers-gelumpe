"""Builds the usb-name patch: the computer sees the Electribe as "Electribe 3" (docs/ideen/69-geraetename.md).

The USB string descriptors live as data in the firmware: string 2 is the product name, strings 3 and 4 name the two
MIDI ports. Each one is a USB string descriptor (length byte, type 0x03, UTF-16LE text) in a slot of its own; the slot
ends where the next descriptor starts, and what the text leaves of it are zeros. The patch writes the new descriptor
into the same slot and fills the rest with zeros, the table that points at the slots stays. The manufacturer string
("KORG INC.") and the USB IDs stay as they are.

The red Electribe (Korg's 2.02 and Hacktribe) keeps the strings at the same addresses with the same bytes, so one
patch serves both; the blue one (synth) has shorter slots and gets shorter port names, since "Electribe 3 _ PAD/KNOB"
does not fit there. Every name keeps "Electribe": the app finds the ports with /electribe/i (src/session.mjs).

Reads the VSB only to check the old descriptors and for the checksums of the bytes it replaces; no firmware bytes go
into the patch. The build is read from the VSB.

    python3 tools/patch/usb_name.py --vsb SYSTEM.VSB [--out data/patches/usb-name.json]
    python3 tools/patch/usb_name.py --vsb blue/SYSTEM.VSB [--out data/patches/usb-name-synth.json]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HEADER = 0x100
RAM = 0xC0000000
HACKTRIBE_CODE = (0x170100, 0x40)    # erased in Korg's own build, same rule as src/firmware.mjs buildOf
STRING = 0x03
# per hardware: the descriptor table and, per string, (index, address, slot length, old text, new text)
SAMPLER = {
    "table": 0xC00A40A0,
    "strings": [
        (2, 0xC00A4120, 40, "electribe2 sampler", "Electribe 3"),
        (3, 0xC00A4148, 56, "electribe2 sampler _ SOUND", "Electribe 3 _ SOUND"),
        (4, 0xC00A4180, 60, "electribe2 sampler _ PAD/KNOB", "Electribe 3 _ PAD/KNOB"),
    ],
}
SYNTH = {
    "table": 0xC008EB00,
    "strings": [
        (2, 0xC008EB80, 24, "electribe2", "Electribe 3"),
        (3, 0xC008EB98, 40, "electribe2 _ SOUND", "Electribe 3 SOUND"),
        (4, 0xC008EBC0, 44, "electribe2 _ PAD/KNOB", "Electribe 3 PAD/KNOB"),
    ],
}
LAYOUT = {"hacktribe": SAMPLER, "stock": SAMPLER, "synth": SYNTH}
WHAT = {2: "the product name", 3: "the name of the SOUND port", 4: "the name of the PAD/KNOB port"}


def file_offset(address):
    return address - RAM + HEADER


def build_of(raw):
    run = raw[HACKTRIBE_CODE[0]:HACKTRIBE_CODE[0] + HACKTRIBE_CODE[1]]
    if run != b"\xff" * HACKTRIBE_CODE[1]:
        return "hacktribe"
    return "synth" if raw[0x10:0x13] == b"E2\0" else "stock"


def descriptor(text):
    data = text.encode("utf-16-le")
    if len(data) + 2 > 0xFF:
        raise ValueError(f"{text!r} is too long for a string descriptor")
    return bytes([len(data) + 2, STRING]) + data


def slot(text, length):
    """The descriptor of `text` in a slot of `length` bytes, the rest zeros as in the firmware."""
    d = descriptor(text)
    if len(d) > length:
        raise ValueError(f"{text!r} needs {len(d)} bytes, the slot has {length}")
    return d.ljust(length, b"\0")


def build_patch(raw, build=None):
    build = build or build_of(raw)
    layout = LAYOUT[build]
    table = file_offset(layout["table"])
    changes = []
    for index, address, length, old_text, new_text in layout["strings"]:
        pointer = int.from_bytes(raw[table + 4 * index:table + 4 * index + 4], "little")
        if pointer != address:
            raise ValueError(f"string {index} is at {pointer:#x}, not {address:#x}: this is not the measured {build} firmware")
        at = file_offset(address)
        old = raw[at:at + length]
        if old != slot(old_text, length):
            raise ValueError(f"unexpected bytes at {address:#x}: this is not the measured {build} firmware")
        changes.append({
            "file": at, "bytes": slot(new_text, length).hex(), "expect": hashlib.sha256(old).hexdigest(),
            "note": f"USB string {index}, {WHAT[index]}: {new_text}",
        })
    builds = ["hacktribe", "stock"] if build in ("hacktribe", "stock") else ["synth"]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "usb-name",
        "name": "Gerätename Electribe 3",
        "builds": builds,
        "changes": changes,
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
    text = json.dumps(build_patch(raw), indent=1, ensure_ascii=False) + "\n"
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
