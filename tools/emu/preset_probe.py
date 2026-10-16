"""Measures how the firmware finds and counts FX presets (docs/messungen/2026-10-15-preset-tabellen.md).

    tools/emu/.venv/bin/python tools/emu/preset_probe.py --vsb SYSTEM.VSB [--flash dump.bin] [--seconds 6]

Boots the image, calls the preset getters of the firmware with indexes around the table ends, and drives the
INSERT type encoder and the master type setter to the end of their lists. Prints JSON, no firmware bytes.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from machine import load_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402

GET_IFX, GET_MFX = 0xC003E738, 0xC003E750          # preset record address by index, the index clamps at 99
COUNT_IFX, COUNT_MFX = 0xC003EFDC, 0xC003EFE4      # menu lengths
SET_MFX = 0xC0048A64
APPLY_PATTERN = 0xC004A8E4                          # takes the pattern in force and sets every effect, sound and mode from it
PATTERN = 0xC033E6A4
GLOBALS = 0xC0691334
PART_BASE = 0x800                                   # data/map/pattern.mjs, first part inside the pattern block
ENCODER_IFX = 4


def name_at(dev, rec):
    return dev.read(rec + 1, 15).split(b"\0")[0].decode("latin1")


def table_ends(dev):
    out = {}
    for label, getter, count in (("ifx", GET_IFX, COUNT_IFX), ("mfx", GET_MFX, COUNT_MFX)):
        n = dev.call(count)
        rows = {}
        for i in (0, n - 1, n, 99, 100, 127, 255):
            rec = dev.call(getter, i)
            rows[str(i)] = {"record": hex(rec), "name": name_at(dev, rec)}
        out[label] = {"count": n, "entries": rows}
    return out


def drive_insert(dev, steps):
    """Turn the INSERT type encoder up and record the type byte of part 1 after every step."""
    at = dev.u32(PATTERN) + 4 + PART_BASE + 33
    seen = [dev.read(at, 1)[0]]
    for _ in range(steps):
        dev.m.send([0x01, ENCODER_IFX, 0, 1, 0])
        dev.run(0.25)
        seen.append(dev.read(at, 1)[0])
    return seen


def drive_master(dev, values):
    at = dev.u32(PATTERN) + 4 + 61
    out = {}
    for v in values:
        dev.call(SET_MFX, dev.u32(GLOBALS) + 0x4004, v, 1)
        dev.run(0.3)
        out[str(v)] = dev.read(at, 1)[0]
    return out


def drive_pattern(dev, cases):
    """What the firmware does when the pattern it applies names presets beyond its menus: the pattern's master type and
    the type of part 1 are written into the pattern in RAM and the routine that applies a pattern to the effects runs.
    What comes out is the type the pattern holds afterwards and the record the master getter finds for it. The DSP
    traffic of this routine is not captured here."""
    pattern = dev.u32(PATTERN)
    out = []
    for master, insert in cases:
        dev.m.uc.mem_write(pattern + 4 + 61, bytes([master]))
        dev.m.uc.mem_write(pattern + 4 + PART_BASE + 33, bytes([insert]))
        dev.call(APPLY_PATTERN, dev.u32(GLOBALS))
        dev.run(1.0)
        out.append({
            "master_in_pattern": master, "insert_in_pattern": insert,
            "master_after": dev.read(pattern + 4 + 61, 1)[0], "insert_after": dev.read(pattern + 4 + PART_BASE + 33, 1)[0],
            "master_record_name": name_at(dev, dev.call(GET_MFX, master)), "asserts": len(dev.m.asserts),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vsb", required=True, type=Path)
    ap.add_argument("--flash", type=Path)
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--steps", type=int, default=0, help="encoder steps for the INSERT list (0 = count + 3)")
    ap.add_argument("--compat", action="store_true", help="also apply patterns that name presets beyond the menus")
    a = ap.parse_args()
    dev = Dev(a.vsb.read_bytes()[0x100:], load_flash([a.flash]) if a.flash else None)
    dev.run(a.seconds)
    report = {"ends": table_ends(dev)}
    steps = a.steps or report["ends"]["ifx"]["count"] + 3
    report["insert_type_after_each_step"] = drive_insert(dev, steps)
    n = report["ends"]["mfx"]["count"]
    report["master_type_after_set"] = drive_master(dev, [0, n - 1, n, n + 1, 99, 100, 127])
    if a.compat:
        top_i, top_m = report["ends"]["ifx"]["count"], n
        report["pattern_beyond_menus"] = drive_pattern(dev, [(0, 0), (top_m - 1, top_i - 1), (top_m, top_i), (top_m + 18, top_i + 22), (127, 127)])
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
