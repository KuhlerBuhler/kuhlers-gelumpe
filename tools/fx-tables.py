#!/usr/bin/env python3
"""Read the effect parameter tables out of your own SYSTEM.VSB.

    python3 tools/fx-tables.py /path/SYSTEM.VSB > data/map/fx-ranges.mjs

The ARM image carries the Blackfin DSP program as a stream of boot blocks
(16-byte header: flags, target address, count, argument; the XOR of the
header bytes is 0). Loaded into DSP memory, 66 pointers at 0x4C30 lead to one
descriptor per unit, and each descriptor leads to its parameter records:

    descriptor (0x34 bytes)  +0 name, +4 count (byte), +0x14 pointer to a list of record pointers
    record     (20 bytes)    +0 name, +5 default (byte), +6 min (s16), +8 max (s16), +10 max again,
                             +12 and +16 pointers into DSP code (not read here)

The unit number the ARM side uses is the index into the 66 pointers. This
tool keeps only what the map needs: per unit, the min and max of each
parameter. It refuses a unit whose parameter count or defaults differ from
data/units.json, because then the two lists are not talking about the same
positions. It also reads two label tables the DSP's text functions use: time
ratio in percent and the looper step. The stream is the same in Korg's 2.02
and in Hacktribe.

Needs only the standard library. Writes numbers derived from the firmware, no
firmware bytes and no names.
"""
import json
import struct
import sys
from pathlib import Path

STREAM_OFF = 0xF9F10   # file offset of the stream, RAM 0xC00F9E10
STREAM_LEN = 0x422A0
DESCRIPTORS = 0x4C30   # DSP address of the 66 descriptor pointers; the ARM image holds them at RAM 0xC00FED74
UNITS = 66
SDRAM = 0x02000000
# Label tables, as (name, DSP address of the pointer table, entries): the mod delay's time ratio shown in percent
# (the short delay's copy is checked against it) and the looper's step. RAM address of each in the ARM image below.
LABEL_TABLES = [("timeRatio", 0x1F0D368, 128), ("looperStep", 0x1C7C230, 19)]
TIME_RATIO_COPY = 0x1F0DA6C
LABEL_EVIDENCE = {"timeRatio": "derived:vsb-table/0xC012B93C", "looperStep": "derived:vsb-table/0xC01196E0"}
DSP_STRINGS = (0x1F00000, 0x1F06000)


def load_sdram(vsb):
    """Apply the blocks that land in SDRAM: data blocks, and fill blocks as their 32-bit pattern."""
    mem = bytearray(SDRAM)
    pos, end = STREAM_OFF, STREAM_OFF + STREAM_LEN
    while pos < end:
        code, target, count, arg = struct.unpack_from("<IIII", vsb, pos)
        x = 0
        for b in vsb[pos:pos + 16]:
            x ^= b
        if code >> 24 != 0xAD or x:
            sys.exit(f"not a DSP stream at file offset {pos:#x}: another firmware build?")
        flags = code & 0xFFFF
        fill = flags & 0x100
        if target < SDRAM:
            if fill:
                data = (struct.pack("<I", arg) * (count // 4 + 1))[:count]
            else:
                data = vsb[pos + 16:pos + 16 + count]
            mem[target:target + count] = data
        pos += 16 + (0 if fill else count)
        if flags & 0x8000:
            break
    if pos != end:
        sys.exit(f"stream ends at {pos:#x}, expected {end:#x}: another firmware build?")
    return mem


def cstr(mem, at):
    return mem[at:mem.index(b"\0", at)].decode("latin1")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    vsb = Path(sys.argv[1]).read_bytes()
    mem = load_sdram(vsb)
    word = lambda a: struct.unpack_from("<I", mem, a)[0]
    units = json.loads((Path(__file__).parent.parent / "data" / "units.json").read_text())

    tables = {}
    for i in range(UNITS):
        d = word(DESCRIPTORS + 4 * i)
        name = cstr(mem, word(d))
        if not name.startswith(("[I", "[M")):
            sys.exit(f"descriptor {i} is called {name!r}: another firmware build?")
        n, tab = mem[d + 4], word(d + 0x14)
        if not (n and tab):
            continue
        params = []
        for j in range(n):
            r = word(tab + 4 * j)
            lo, hi, hi2 = struct.unpack_from("<hhh", mem, r + 6)
            assert hi == hi2, f"unit {i} parameter {j}: the two maxima differ"
            params.append((mem[r + 5], lo, hi))
        tables[i] = params

    out, skipped = {}, []
    for key in ("ifx_device", "mfx_device"):
        for hex_id, entry in units[key].items():
            i = int(hex_id, 16)
            ours = [int(p["default"], 16) for p in entry["params"]]
            theirs = tables.get(i)
            if theirs is None:
                continue
            if [p[0] for p in theirs] != ours:
                skipped.append((hex_id, entry["unit"], len(ours), len(theirs)))
                continue
            out.setdefault(hex_id, [[p[1], p[2]] for p in theirs])
    for hex_id, unit, a, b in skipped:
        print(f"skipped {hex_id} {unit}: units.json has {a} parameters, the DSP table {b}, or the defaults differ", file=sys.stderr)

    labels = {}
    for name, dsp, count in LABEL_TABLES:
        words = struct.unpack_from(f"<{count}I", mem, dsp)
        labels[name] = [cstr(mem, p) for p in words]
        assert all(DSP_STRINGS[0] <= p < DSP_STRINGS[1] for p in words), f"{name}: not a table of strings: another firmware build?"
    # The short delay keeps its own copy of the time ratio labels; they must read the same.
    again = [cstr(mem, p) for p in struct.unpack_from("<128I", mem, TIME_RATIO_COPY)]
    assert again == labels["timeRatio"], "the two time ratio label tables differ"

    print("// Generated by tools/fx-tables.py from the parameter tables in the DSP stream of a SYSTEM.VSB. Do not edit.")
    print("// Per unit and parameter position: [min, max] as the DSP table gives them. The stored byte")
    print("// is the shown value minus min (default 36 in a range of -36 to 36 is 0), so a stored")
    print("// byte runs from 0 to max - min. A range of 0 to 0 means the table declares no span.")
    print("// labels: what the DSP's text functions show for a stored value, one string per value.")
    print("export default {")
    print('  evidence: "derived:vsb-table/0xC00FED74",')
    print("  labels: {")
    for name, evidence in LABEL_EVIDENCE.items():
        print(f'    {name}: {{ evidence: "{evidence}", list: {json.dumps(labels[name])} }},')
    print("  },")
    print("  units: {")
    for hex_id in sorted(out):
        print(f'    "{hex_id}": {json.dumps(out[hex_id], separators=(",", ":"))},')
    print("  },")
    print("};")


if __name__ == "__main__":
    main()
