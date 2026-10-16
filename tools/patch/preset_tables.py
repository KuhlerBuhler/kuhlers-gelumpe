"""Builds the preset-tables patch: room for 128 insert and 128 master FX presets (docs/messungen/2026-10-15-preset-tabellen.md).

The firmware finds an FX preset through two small getters (0xC003E738 insert, 0xC003E750 master). Each reads a
pointer from an array of 100 entries, whose address sits in a literal word behind the getter, and clamps the
index at 99. Both builds work this way; Hacktribe moved the arrays and the records they point at, Korg's own
build keeps them scattered. This patch does not move a record. It does four things, the same in both builds:

 1. a new pointer array of 128 entries per table in erased image space: the first 100 are copied from the
    build's own array, the last 28 point at the record of entry 0 until the editor gives them a record of their own;
 2. the two literals behind the getters point at the new arrays and the clamps become 127 (the index is a 7 bit
    value in the firmware, bit 7 of the same byte is a flag, so 128 is the most the firmware can address);
 3. the per-part memory of the insert knob (16 parts times the menu length, one byte each, 0xC0692278 in Korg's
    build, 0xC013C200 in Hacktribe's) moves to a table of 16 times 128 bytes: five literals;
 4. 28 records of room per table behind the arrays, for the presets that go beyond the 100 the firmware had.

The menu lengths stay what the file has. Raising them is the editor's job, together with a record to point at.
Reads the VSB only for the checksums of what it replaces and for the old arrays' addresses; no firmware bytes
go into the patch. The two variants share the id `preset-tables` and differ in `builds`.

    python3 tools/patch/preset_tables.py --vsb SYSTEM.VSB [--out data/patches/preset-tables.json]
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HEADER = 0x100
RAM = 0xC0000000
HACKTRIBE_CODE = (0x170100, 0x40)       # erased in Korg's own build, same rule as src/firmware.mjs buildOf

CAPACITY = 128                          # the firmware's index is 7 bits wide
OLD_SLOTS = 100                         # entries of the firmware's own arrays
RECORD = 0x20C
EXTRA = CAPACITY - OLD_SLOTS            # records of room per table

# Erased image space the set leaves free in both builds (data/patch-ram.mjs, the run before 0xC01A0000).
RES_IFX = 0xC0174000                    # EXTRA records for the insert table, 0x3950 bytes
RES_MFX = 0xC0178000                    # EXTRA records for the master table, 0x3950 bytes
ARRAY_IFX = 0xC017C000                  # CAPACITY pointers, 512 bytes
ARRAY_MFX = 0xC017C200
EDIT_TABLE = 0xC017C400                 # 16 parts times CAPACITY bytes of the insert knob memory

GETTER_IFX, GETTER_MFX = 0xC003E738, 0xC003E750
CLAMP = {GETTER_IFX: (0xC003E73C, 0xC003E740), GETTER_MFX: (0xC003E754, 0xC003E758)}
LITERAL = {GETTER_IFX: 0xC003E74C, GETTER_MFX: 0xC003E764}
EDIT_LITERALS = (0xC00980A8, 0xC0098100, 0xC0098144, 0xC0098168, 0xC00981B4)
CMP_99, MOV_99 = 0xE3500063, 0x23A00063      # cmp r0, #99 / movhs r0, #99
CMP_127, MOV_127 = 0xE350007F, 0x23A0007F

# per build: array of the insert presets, array of the master presets, the insert knob memory
KNOWN = {
    "hacktribe": (0xC00A7F60, 0xC00B4DA0, 0xC013C200),
    "stock": (0xC00ADF94, 0xC00AF390, 0xC0692278),
}
WHY_ARRAY = "the preset getters read their pointer from this array while the firmware sets up its FX channels at start"
WHY_CODE = "the firmware runs the preset getters and the knob memory set-up at start"


def off(address):
    return address - RAM + HEADER


def build_of(raw):
    run = raw[HACKTRIBE_CODE[0]:HACKTRIBE_CODE[0] + HACKTRIBE_CODE[1]]
    return "stock" if run == b"\xff" * HACKTRIBE_CODE[1] else "hacktribe"


def word(raw, address):
    return struct.unpack_from("<I", raw, off(address))[0]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def raw_change(raw, address, new):
    old = raw[off(address):off(address) + 4]
    return {"file": off(address), "bytes": struct.pack("<I", new).hex(), "expect": sha(old)}


def build_patch(raw, build=None):
    build = build or build_of(raw)
    old_ifx, old_mfx, old_edit = KNOWN[build]
    if word(raw, LITERAL[GETTER_IFX]) != old_ifx or word(raw, LITERAL[GETTER_MFX]) != old_mfx:
        raise ValueError(f"the getter literals do not point where the measured {build} firmware has its arrays")
    for getter, (cmp_at, mov_at) in CLAMP.items():
        if (word(raw, cmp_at), word(raw, mov_at)) != (CMP_99, MOV_99):
            raise ValueError(f"the clamp behind the getter at {getter:#x} is not the measured one")
    for at in EDIT_LITERALS:
        if word(raw, at) != old_edit:
            raise ValueError(f"the literal at {at:#x} does not point at the knob memory of the {build} firmware")
    for area, length in ((ARRAY_IFX, 2 * CAPACITY * 4), (RES_IFX, EXTRA * RECORD), (RES_MFX, EXTRA * RECORD), (EDIT_TABLE, 16 * CAPACITY)):
        if any(b != 0xFF for b in raw[off(area):off(area) + length]):
            raise ValueError(f"{area:#x} is not erased")
    erased = lambda n: sha(b"\xff" * n)
    changes = []
    for array, old in ((ARRAY_IFX, old_ifx), (ARRAY_MFX, old_mfx)):
        source = raw[off(old):off(old) + OLD_SLOTS * 4]
        # the firmware's own 100 entries, copied; then the extra entries, all pointing at the record of entry 0
        changes.append({"file": off(array), "expect": erased(OLD_SLOTS * 4),
                        "copy": {"file": off(old), "length": OLD_SLOTS * 4, "expect": sha(source)}})
        changes.append({"file": off(array) + OLD_SLOTS * 4, "bytes": (source[:4] * EXTRA).hex(), "expect": erased(EXTRA * 4)})
    for getter, (cmp_at, mov_at) in CLAMP.items():
        changes.append(raw_change(raw, cmp_at, CMP_127))
        changes.append(raw_change(raw, mov_at, MOV_127))
    changes.append(raw_change(raw, LITERAL[GETTER_IFX], ARRAY_IFX))
    changes.append(raw_change(raw, LITERAL[GETTER_MFX], ARRAY_MFX))
    for at in EDIT_LITERALS:
        changes.append(raw_change(raw, at, EDIT_TABLE))
    code = [LITERAL[GETTER_IFX], LITERAL[GETTER_MFX], *EDIT_LITERALS, *[a for pair in CLAMP.values() for a in pair]]
    start_phase = [{"file": off(a), "length": 4, "why": WHY_CODE} for a in code]
    start_phase += [{"file": off(a), "length": CAPACITY * 4, "why": WHY_ARRAY} for a in (ARRAY_IFX, ARRAY_MFX)]
    name = "Presets: Platz für 128 Insert- und 128 Master-Effekte"
    return {
        "format": "gelumpe-patch", "version": 1, "id": "preset-tables", "name": name,
        "builds": [build],
        "changes": changes,
        "startPhase": start_phase,
        "ram": [
            {"at": f"0x{RES_IFX:08X}", "length": EXTRA * RECORD, "what": f"room for {EXTRA} more insert preset records, written by the editor", "source": "tools/patch/preset_tables.py:RES_IFX"},
            {"at": f"0x{RES_MFX:08X}", "length": EXTRA * RECORD, "what": f"room for {EXTRA} more master preset records, written by the editor", "source": "tools/patch/preset_tables.py:RES_MFX"},
            {"at": f"0x{EDIT_TABLE:08X}", "length": 16 * CAPACITY, "what": "knob memory of the insert effect, 16 parts by CAPACITY entries, filled by the firmware at start", "source": "tools/patch/preset_tables.py:EDIT_TABLE"},
        ],
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
