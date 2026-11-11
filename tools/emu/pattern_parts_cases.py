"""Emulator cases of the pattern and part values a plugin writes from API 21 (`korg.pattern.current.*`, `korg.current.*`,
`korg.parts[i].*`): each value set by a plugin leaves the pattern in RAM, the sound engine's copy behind it and the page of the
Pattern or Part menu as the menu's own turn (or the key) does. Sample, IFX on and IFX type, read-only in API 21, are written
from API 23 (plugin_api23_cases.py).

    PYTHONPATH=tools/patch python3 tools/emu/pattern_parts_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-06-plugin-api21-pattern-parts.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import node_json  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PATTERN_PTR = 0xC033E6A4        # the pattern object; its block starts at +4, the sound engine's copy at block + 0x4000
OBJECT = 0x4274
COPY = 0x4000
PART_BASE, PART_STRIDE = 0x800, 0x330
KEYS = menu_cases.KEYS
PATTERN_SCREEN, PART_SCREEN = 3, 7
# the page of the Pattern menu that turns each field, the same on all three firmwares (measure:2026-11-06/plugin-api21-pattern-parts)
PATTERN_PAGES = {"tempo": 0, "swing": 1, "beat": 2, "length": 3, "mfxType": 5, "key": 7, "scale": 8, "chordSet": 9, "gateArp": 10,
                 "chainTo": 13, "chainRepeat": 14, "syncGroup": 15}
PART_PAGES = {"voiceAssign": 19}     # the Part menu counts on from the 16 pages of the Pattern menu
PART_KEYS = {"mfxSend": 0x1A}
# rows 0 to 54 of the picture: the bottom rows hold a status line that is not part of the value
KEEP = bytes(0xFF if row < 6 else 0x7F if row == 6 else 0 for row in range(8) for _ in range(128))

PROGRAM = """let tempo = -1; let key = -1; let group = -1; let voice = -1; let send = -1; let level = -1;
korg.onEvent("ready", () => {
  korg.pattern.current.tempo = 1234;
  korg.current.key = 5;
  korg.pattern.current.syncGroup = 42;
  korg.current.level = 77;
  korg.parts[1].voiceAssign = 2;
  korg.parts[1].mfxSend = 1 - korg.parts[1].mfxSend;
  tempo = korg.current.tempo; key = korg.pattern.current.key; group = korg.current.syncGroup; level = korg.pattern.current.level;
  voice = korg.parts[1].voiceAssign; send = korg.parts[1].mfxSend;
});"""


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    fields()
    edit.compiled({"values": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"pattern_parts:{name}", "ok": bool(ok), "detail": str(detail)}


def fields():
    code = ("import {PATTERN_FIELDS, PART_FIELDS} from './data/script/contract.mjs';"
            "process.stdout.write(JSON.stringify([PATTERN_FIELDS.map(f => f.name), PART_FIELDS.map(f => [f.name, f.offset])]))")
    pattern, part = node_json.run(code)
    return pattern, part


class World:
    def __init__(self, vsb, flash=None, built=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.pattern, self.part = fields()
        self.built = built or script_hooks.build(edit.compiled({"values": PROGRAM})["include"], build=identify(self.payload).build)
        self.s = self.built.symbols
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(0.3)
        self.obj = self.dev.u32(PATTERN_PTR)

    def state(self):
        return self.dev.read(self.obj, OBJECT)

    def part_at(self, part, name):
        return 4 + PART_BASE + part * PART_STRIDE + dict(self.part)[name]

    def read(self, part, field):
        v = self.dev.call(self.s["script_read_pattern_value_glue"], 0xFFFFFFFF, part & 0xFFFFFFFF, field)
        return v - (1 << 32) if v >= 1 << 31 else v

    def set_pattern(self, name, value):
        self.dev.call(self.s["script_seq_set_pattern_value_glue"], self.pattern.index(name), value & 0xFFFFFFFF)
        self.dev.run(0.3)

    def set_part(self, part, name, value):
        self.dev.call(self.s["script_seq_set_part_value_glue"], part, [n for n, _ in self.part].index(name), value & 0xFFFFFFFF)
        self.dev.run(0.3)

    def page(self, screen, k):
        menu_cases.go(self.dev, screen)
        for _ in range(40):
            if menu_cases.counter(self.dev)[0] == k:
                return
            self.dev.press(KEYS["edit_next"], 0.25)
        raise AssertionError(f"page {k} not reached")

    def reenter(self, k):
        """Leave the page and come back: the page draws the value it finds in the pattern."""
        self.dev.press(KEYS["edit_next"], 0.25)
        self.dev.press(KEYS["edit_prev"], 0.25)
        assert menu_cases.counter(self.dev)[0] == k, menu_cases.counter(self.dev)
        return bytes(b & m for b, m in zip(self.dev.fb(), KEEP))


def changed(a, b):
    return [i for i in range(len(a)) if a[i] != b[i]]


def twin(w, screen, k, value_of, set_value):
    """The page turned by one in the menu (down when the value is at its top), back, then the value the menu reached set by the
    plugin: the pattern object (block and copy) and the page drawn again after leaving it must be the same both ways."""
    w.page(screen, k)
    start = w.state()
    step = 1
    w.dev.turn(step, 0.4)
    if w.state() == start:
        step = -1
        w.dev.turn(step, 0.4)
    want = value_of()
    menu = (w.state(), w.reenter(k))
    w.dev.turn(-step, 0.4)
    back = w.reenter(k)
    set_value(want)
    plugin = (w.state(), w.reenter(k))
    diff = changed(menu[0], plugin[0])
    moved = changed(start, menu[0])
    return (menu[0] == plugin[0] and menu[1] == plugin[1] and moved and back is not None and not w.dev.m.asserts,
            f"menu set {want}, menu changed {[hex(i - 4) for i in moved][:6]}, plugin differs at {[hex(i - 4) for i in diff][:6]}, "
            f"page equal {menu[1] == plugin[1]}, asserts {w.dev.m.asserts}")


def pattern_cases(w):
    out = []
    for name, k in PATTERN_PAGES.items():
        field = w.pattern.index(name)
        ok, detail = twin(w, PATTERN_SCREEN, k, lambda: w.read(-1, field), lambda v: w.set_pattern(name, v))
        out.append(entry(f"{name}_like_the_menu", ok, detail))
    before = w.state()
    w.set_pattern("level", 77)
    level = w.read(-1, w.pattern.index("level"))
    moved = changed(before, w.state())
    out.append(entry("level_in_ram_and_copy", level == 77 and 4 + 42 in moved and any(i >= 4 + COPY for i in moved) and not w.dev.m.asserts,
                     f"read back {level}, changed {[hex(i - 4) for i in moved][:6]}"))
    w.set_pattern("syncGroup", 5000)
    out.append(entry("sync_group_clamped", w.read(-1, w.pattern.index("syncGroup")) == 999, w.read(-1, w.pattern.index("syncGroup"))))
    return out


def part_cases(w):
    out = []
    names = [n for n, _ in w.part]
    for name, k in PART_PAGES.items():
        field = names.index(name)
        ok, detail = twin(w, PART_SCREEN, k, lambda: w.read(0, field), lambda v: w.set_part(0, name, v))
        out.append(entry(f"{name}_like_the_menu", ok, detail))
    menu_cases.go(w.dev, PART_SCREEN)
    for name, key in PART_KEYS.items():
        at = w.part_at(0, name)
        start = w.state()
        w.dev.press(key, 0.4)
        menu = w.state()
        w.dev.press(key, 0.4)
        w.set_part(0, name, menu[at])
        plugin = w.state()
        out.append(entry(f"{name}_like_the_key", menu[at] != start[at] and menu == plugin and any(i >= 4 + COPY for i in changed(start, plugin))
                         and not w.dev.m.asserts,
                         f"key set {start[at]} -> {menu[at]}, plugin differs at {[(hex(i - 4), menu[i], plugin[i]) for i in changed(menu, plugin)][:6]}"))
    return out


def plugin_cases(w):
    """A plugin writes and reads the values by name, the new korg.pattern.current and the old korg.current."""
    before = w.state()
    send = before[w.part_at(1, "mfxSend")]
    request = edit.compiled({"values": PROGRAM})
    program = request["programs"]["values"]
    entry_at = script_cases.install(w.dev, w.built, request["programs"], ["values"])["values"]
    w.dev.run(0.5)
    seen = script_cases.variables(w.dev, entry_at, program)
    want = {"tempo": 1234, "key": 5, "group": 42, "level": 77, "voice": 2, "send": 1 - send}
    after = w.state()
    ram = (after[4 + 34] | after[4 + 35] << 8, after[4 + 39], after[4 + 0x3B80] | after[4 + 0x3B81] << 8, after[4 + 42],
           after[w.part_at(1, "voiceAssign")], after[w.part_at(1, "mfxSend")])
    return [entry("plugin_sets_and_reads_by_name", seen == {**seen, **want} and list(ram) == [want[k] for k in ("tempo", "key", "group", "level", "voice", "send")]
                  and not w.dev.m.asserts, f"read back {seen}, in RAM {ram}, asserts {w.dev.m.asserts}")]


def cases(vsb, flash=None):
    w = World(vsb, flash)
    out = pattern_cases(w)
    w = World(vsb, flash, w.built)
    out += part_cases(w)
    w = World(vsb, flash, w.built)
    out += plugin_cases(w)
    return out


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
