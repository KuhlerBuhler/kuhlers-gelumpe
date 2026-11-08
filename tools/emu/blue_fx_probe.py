# SPDX-License-Identifier: GPL-2.0-only
"""Catalog effects on the blue Electribe 2, in the emulator (docs/messungen/2026-11-08-blau-eigene-effekte.md).

Builds, in memory only, what a port of `preset-tables` and `fx-catalog` would write into a blue image: the patch's
arrays and knob memory at the Sampler's addresses (free in the blue image too), the getters' literals and clamps, the
knob memory literals and the menu lengths at the synth's places (data/synth-map/). The records come from
tools/emu/blue_fx_records.mjs. The same steps run on Korg's red 2.02 with its own places, so both can be compared.

    tools/emu/.venv/bin/python tools/emu/blue_fx_probe.py --vsb KORG.VSB --records recs.json [--compare OTHER.VSB OTHER.json]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import preset_tables as pt  # noqa: E402
import synthaddr  # noqa: E402
from mfx_cases import DspLog, blank_for, same_dsp  # noqa: E402
from splash_cases import Dev  # noqa: E402

HEADER, IMAGE = 0x100, 0xC0000000
IFX_COUNT = [0x3f0dc, 0x98250, 0x98294, 0x981ec, 0x9819c, 0x9821c, 0x98238]   # data/map/firmware.mjs, file offsets
IFX_LAST = [0x49080, 0x49ff0, 0x4a2f8, 0x9824c, 0x98288, 0x981e8]
IFX_ROW, MFX_COUNT = 0x98184, 0x3f0e4
GET = {"ifx": 0xC003E738, "mfx": 0xC003E750}
COUNT = {"ifx": 0xC003EFDC, "mfx": 0xC003EFE4}
# Places of the knob memory set-up and the insert menu length that data/synth-map/ has no entry for: fwmap.py (Korg red against
# blue 2.02, 2026-11-08); build() still checks the instruction or literal it expects at each.
FWMAP = {0xC0098150: 0xC0085748, 0xC0098194: 0xC008578C, 0xC00980EC: 0xC00856E4, 0xC009809C: 0xC0085694, 0xC009811C: 0xC0085714,
         0xC0098138: 0xC0085730, 0xC0048F80: 0xC0043140, 0xC0049EF0: 0xC004400C, 0xC004A1F8: 0xC00442F8, 0xC009814C: 0xC0085744,
         0xC0098188: 0xC0085780, 0xC00980E8: 0xC00856E0, 0xC0098084: 0xC008567C, 0xC00981B4: 0xC00857AC,
         0xC0098100: 0xC00856F8, 0xC0098144: 0xC008573C, 0xC0098168: 0xC0085760}
SET_MFX, PATTERN, GLOBALS, PART_BASE, ENCODER_IFX = 0xC0048A64, 0xC033E6A4, 0xC0691334, 0x800, 4


def build(raw, rows):
    """The image with the port applied; raises when a place does not hold the measured instruction or value."""
    p = bytearray(raw)
    synth = synthaddr.is_synth(p)
    tr = (lambda a: FWMAP.get(a) or synthaddr.tr(a)) if synth else (lambda a: a)
    at = lambda a: tr(a) - IMAGE
    u32 = lambda a: struct.unpack_from("<I", p, at(a))[0]

    def put(a, value, expect=None):
        if expect is not None and u32(a) != expect:
            raise SystemExit(f"{tr(a):#x}: {u32(a):#x}, expected {expect:#x}")
        struct.pack_into("<I", p, at(a), value)
    old = {k: u32(pt.LITERAL[g]) for k, g in (("ifx", pt.GETTER_IFX), ("mfx", pt.GETTER_MFX))}
    knob = u32(pt.EDIT_LITERALS[0])
    for area, n in ((pt.ARRAY_IFX, 0x400), (pt.RES_IFX, pt.EXTRA * pt.RECORD), (pt.RES_MFX, pt.EXTRA * pt.RECORD), (pt.EDIT_TABLE, 16 * pt.CAPACITY)):
        if any(b != 0xFF for b in p[area - IMAGE:area - IMAGE + n]):
            raise SystemExit(f"{area:#x} is not erased")
    for kind, array in (("ifx", pt.ARRAY_IFX), ("mfx", pt.ARRAY_MFX)):
        src = p[old[kind] - IMAGE:old[kind] - IMAGE + 400]
        p[array - IMAGE:array - IMAGE + 400] = src
        p[array - IMAGE + 400:array - IMAGE + 512] = src[:4] * pt.EXTRA
    for g, (c, m) in pt.CLAMP.items():
        put(c, pt.CMP_127, pt.CMP_99)
        put(m, pt.MOV_127, pt.MOV_99)
    put(pt.LITERAL[pt.GETTER_IFX], pt.ARRAY_IFX)
    put(pt.LITERAL[pt.GETTER_MFX], pt.ARRAY_MFX)
    for a in pt.EDIT_LITERALS:
        put(a, pt.EDIT_TABLE, knob)
    n = {"ifx": 38, "mfx": 32}
    for r in rows:
        array = pt.ARRAY_IFX if r["kind"] == "ifx" else pt.ARRAY_MFX
        target = struct.unpack_from("<I", p, array - IMAGE + 4 * (r["slot"] - 1))[0]
        if p[target - IMAGE + 1] != 0:
            raise SystemExit(f"slot {r['slot']} of {r['kind']} holds a named record")
        p[target - IMAGE:target - IMAGE + pt.RECORD] = bytes.fromhex(r["record"])
        n[r["kind"]] = max(n[r["kind"]], r["slot"])
    sites = [(f, n["ifx"], 38) for f in IFX_COUNT] + [(f, n["ifx"] - 1, 37) for f in IFX_LAST] + [(IFX_ROW, n["ifx"], 38), (MFX_COUNT, n["mfx"], 32)]
    for f, value, was in sites:
        a = f - HEADER + IMAGE
        if p[at(a)] != was:
            raise SystemExit(f"menu length at {tr(a):#x} is {p[at(a)]}, expected {was}")
        p[at(a)] = value
    return bytes(p), {"synth": synth, "arrays": {k: hex(v) for k, v in old.items()}, "knob": hex(knob), "menu": n}


class Box:
    def __init__(self, payload):
        self.dev = Dev(payload, blank_for(payload))
        self.dsp = DspLog(self.dev.m)
        self.dev.run(10.0 if self.dev.synth else 6.0)

    def count(self, kind):
        return self.dev.call(COUNT[kind])

    def name(self, kind, index):
        a = self.dev.call(GET[kind], index)
        return bytes(self.dev.m.uc.mem_read(a + 1, 15)).split(b"\0")[0].decode("latin1")

    def ifx_type(self):
        base = struct.unpack("<I", bytes(self.dev.m.uc.mem_read(self.dev.a(PATTERN), 4)))[0]
        return bytes(self.dev.m.uc.mem_read(base + 4 + PART_BASE + 33, 1))[0]

    def step_ifx(self, delta=1):
        self.dev.m.send([0x01, ENCODER_IFX, 0, delta & 0xFF, 0])
        self.dev.run(0.25)

    def set_mfx(self, value):
        g = struct.unpack("<I", bytes(self.dev.m.uc.mem_read(self.dev.a(GLOBALS), 4)))[0]
        self.dev.call(SET_MFX, g + 0x4004, value, 1)
        self.dev.run(0.3)

    def select(self, kind, index, n):
        if kind == "ifx":
            for _ in range(2 * n):
                cur = self.ifx_type()
                if cur == (index - 1) % n:
                    break
                self.step_ifx(1 if (index - 1 - cur) % n < n // 2 else -1)
            self.dsp.clear()
            self.step_ifx(1)
        else:
            self.set_mfx(0 if index else 1)
            self.dsp.clear()
            self.set_mfx(index)
        self.dev.run(1.0)
        return self.dsp.changes()


def measure(raw, rows):
    payload, info = build(raw[HEADER:], rows)
    box = Box(payload)
    out = {**info, "asserts_boot": list(box.dev.m.asserts), "count": {k: box.count(k) for k in ("ifx", "mfx")}}
    out["names"] = {k: [box.name(k, r["slot"] - 1) for r in rows if r["kind"] == k] for k in ("ifx", "mfx")}
    first = box.ifx_type()
    seen = [first]
    for _ in range(out["count"]["ifx"] + 2):
        box.step_ifx()
        seen.append(box.ifx_type())
    out["walk_wraps"] = seen == [(first + i) % out["count"]["ifx"] for i in range(len(seen))]
    out["dsp"] = {f"{r['kind']}{r['slot']}": box.select(r["kind"], r["slot"] - 1, out["count"][r["kind"]]) for r in rows}
    out["dsp_factory"] = {"ifx2": box.select("ifx", 1, out["count"]["ifx"]), "mfx2": box.select("mfx", 1, out["count"]["mfx"])}
    out["asserts"] = list(box.dev.m.asserts)
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--vsb", required=True, type=Path)
    a.add_argument("--records", required=True, type=Path)
    a.add_argument("--compare", nargs=2, type=Path)
    o = a.parse_args()
    mine = measure(o.vsb.read_bytes(), json.loads(o.records.read_text()))
    report = {k: v for k, v in mine.items() if k not in ("dsp", "dsp_factory")}
    report["transfers"] = {k: len(v) for k, v in {**mine["dsp"], **mine["dsp_factory"]}.items()}
    if o.compare:
        other = measure(o.compare[0].read_bytes(), json.loads(o.compare[1].read_text()))
        report["other_transfers"] = {k: len(v) for k, v in {**other["dsp"], **other["dsp_factory"]}.items()}
        report["same_as_other"] = {k: same_dsp(v, {**other["dsp"], **other["dsp_factory"]}.get(k, [])) for k, v in {**mine["dsp"], **mine["dsp_factory"]}.items()}
        report["other_asserts"] = other["asserts"]
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
