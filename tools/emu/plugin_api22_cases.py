"""Emulator cases of plugin API 22: korg.seq.getOn, getGate, getVelocity and getNote read a step of the pattern in RAM as it is
(getNote the MIDI note of a note place, -1 for an empty one), the same bytes korg.seq.setStep and the firmware's step edit write,
and a read does not mark the frame as one that wrote steps (the pads are not redrawn for it).

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api22_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-06-plugin-api22-step-getters.md.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PATTERN_PTR = 0xC033E6A4        # the pattern object; its block starts at +4
PART_BASE, PART_STRIDE = 0x800, 0x330
STEP_BASE, STEP_STRIDE = 0x30, 12
# (part, step, record): on, gate, velocity, trigger, four note places (note + 1, 0 empty), four bytes the runtime leaves alone
RECORDS = [
    (0, 0, [1, 96, 100, 1, 61, 0, 0, 0, 0, 0, 0, 0]),
    (3, 9, [1, 255, 101, 1, 61, 0, 128, 1, 7, 7, 7, 7]),
    (7, 31, [0, 127, 1, 0, 0, 49, 0, 73, 0, 0, 0, 0]),
    (15, 63, [1, 40, 127, 1, 128, 128, 128, 128, 0, 0, 0, 0]),
]

PROGRAM = """let on = -9; let gate = -9; let vel = -9; let n0 = -9; let n1 = -9; let n2 = -9; let n3 = -9; let last = -9;
korg.onEvent("ready", () => {
  on = korg.seq.getOn(3, 9); gate = korg.seq.getGate(3, 9); vel = korg.seq.getVelocity(3, 9);
  n0 = korg.seq.getNote(3, 9, 0); n1 = korg.seq.getNote(3, 9, 1); n2 = korg.seq.getNote(3, 9, 2); n3 = korg.seq.getNote(3, 9, 3);
  last = korg.seq.getGate(15, 63);
});"""


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"api22": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"plugin_api22:{name}", "ok": bool(ok), "detail": str(detail)}


def signed(v):
    return v - (1 << 32) if v >= 1 << 31 else v


class World:
    def __init__(self, vsb, flash=None, built=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.request = edit.compiled({"api22": PROGRAM})
        self.built = built or script_hooks.build(self.request["include"], build=identify(self.payload).build)
        self.s = self.built.symbols
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(0.3)
        self.block = self.dev.u32(PATTERN_PTR) + 4
        self.flag = self.built.layout["card"] + self.s["SQ_AT"]

    def step_at(self, part, step):
        return self.block + PART_BASE + part * PART_STRIDE + STEP_BASE + step * STEP_STRIDE

    def put(self):
        for part, step, record in RECORDS:
            self.dev.m.uc.mem_write(self.step_at(part, step), bytes(record))

    def get(self, name, *args):
        return signed(self.dev.call(self.s[f"script_seq_get_{name}_glue"], *args))


def glue_cases(w):
    w.put()
    want, seen = [], []
    for part, step, record in RECORDS:
        want.append([record[0], record[1], record[2], *[b - 1 for b in record[4:8]]])
        seen.append([w.get("on", part, step), w.get("gate", part, step), w.get("velocity", part, step),
                     *[w.get("note", part, step, slot) for slot in range(4)]])
    out = [entry("glue_reads_the_record", seen == want and not w.dev.m.asserts, f"on, gate, velocity, notes 0 to 3: read {seen}, in RAM {want}")]

    w.dev.m.uc.mem_write(w.flag, struct.pack("<I", 0))
    before = w.dev.read(w.block, 0x4000)
    for part, step, _ in RECORDS:
        w.get("on", part, step), w.get("gate", part, step), w.get("velocity", part, step), w.get("note", part, step, 2)
    flag = w.dev.u32(w.flag)
    same = w.dev.read(w.block, 0x4000) == before
    w.dev.call(w.s["script_seq_set_gate_glue"], 0, 1, 40)
    marked = w.dev.u32(w.flag)
    out.append(entry("reads_mark_nothing", flag == 0 and same and marked != 0 and not w.dev.m.asserts,
                     f"frame flag after the reads {flag:#x}, pattern block unchanged {same}; after setGate {marked:#x}"))
    return out


def tie_cases(w):
    """setStep behind a TIE: the loop of a plugin that fills a part with one tied note. Trigger 0 on every step behind a TIE, as
    the firmware writes it, so the chain plays as one note (docs/messungen/2026-11-06-step-trigger.md)."""
    for step in range(64):
        w.dev.call(w.s["script_seq_set_step_glue"], 2, step, 63, 100)
        w.dev.call(w.s["script_seq_set_gate_glue"], 2, step, 127)
    triggers = [w.dev.read(w.step_at(2, step) + 3, 1)[0] for step in range(64)]
    return [entry("set_step_after_tie", triggers == [1] + [0] * 63 and not w.dev.m.asserts, f"triggers of part 2: {triggers}")]


def plugin_cases(w):
    w.put()
    program = w.request["programs"]["api22"]
    at = script_cases.install(w.dev, w.built, w.request["programs"], ["api22"])["api22"]
    w.dev.run(0.5)
    seen = script_cases.variables(w.dev, at, program)
    want = {"on": 1, "gate": 255, "vel": 101, "n0": 60, "n1": -1, "n2": 127, "n3": 0, "last": 40}
    return [entry("plugin_reads_by_name", seen == {**seen, **want} and not w.dev.m.asserts,
                  f"read {dict((k, seen.get(k)) for k in want)}, want {want}, asserts {w.dev.m.asserts}")]


def cases(vsb, flash=None):
    w = World(vsb, flash)
    out = glue_cases(w)
    out += tie_cases(w)
    w = World(vsb, flash, w.built)
    out += plugin_cases(w)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
