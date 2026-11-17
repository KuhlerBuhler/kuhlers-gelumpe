"""Emulator cases of plugin API 29: korg.pads.mode, korg.pads.bar and korg.screen read the firmware's words, the events padMode,
screen and write report their changes and every WRITE, korg.read.patternName copies a pattern's name and korg.display.chars draws
an array as text, as korg.display.text draws the same string.

    python3 tools/emu/plugin_api29_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api29-state-events.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

LED_MANAGER, MODEL, SCREENS = 0xC0345A1C, 0xC0348884, 0xC03404C0   # Sampler places; Dev.a gives the synth's (data/synth-map/)
SEQ, PATTERN_PTR, BANK = 0xC034029C, 0xC033E6A4, 0xC08B2940
NAME_AT, LENGTH_AT = 16, 37                     # in a pattern block (data/map/pattern.mjs, data/script/contract.mjs)
LEAVES = {"mode": 55, "bar": 56, "screen": 57}
PAD_KEYS = {"trigger": 0x13, "sequencer": 0x15, "keyboard": 0x17, "chord": 0x18, "step_jump": 0x19, "pattern_set": 0x1B}
BAR_KEYS = [0x1C, 0x1D, 0x1E, 0x1F]
MENU, EXIT, WRITE = 0x09, 0x0D, 0x0E
STORED = 5                                      # the stored pattern whose name the program reads from the bank
APP_PAGE = 1                                    # the page of the app in TOOLS, behind Blechy

PROGRAMS = {
    "api29": f"""let modes = 0; let mode = -9; let screens = 0; let screen = -9; let writes = 0; let written = -9;
const name = new Array(16); const stored = new Array(16);
let length = -9; let first = -9; let sum = -9; let storedLength = -9; let storedSum = -9;
korg.onEvent("padMode", m => {{ modes = modes + 1; mode = m; }});
korg.onEvent("screen", n => {{ screens = screens + 1; screen = n; }});
korg.onEvent("write", p => {{ writes = writes + 1; written = p; }});
korg.onEvent("frame", () => {{
  length = korg.read.patternName(name, -1);
  storedLength = korg.read.patternName(stored, {STORED});
  first = name[0]; sum = 0; storedSum = 0;
  for (let i = 0; i < 16; i = i + 1) {{ sum = sum + name[i] * (i + 1); storedSum = storedSum + stored[i] * (i + 1); }}
}});""",
    "chars": """korg.app("Chars", "TOOLS");
const s = [72, 105, 256 + 33, 0, 65];
korg.onEvent("open", () => { korg.display.clear(); korg.display.chars(s, 3, 4, 9); });""",
    "text": """korg.app("Chars", "TOOLS");
korg.onEvent("open", () => { korg.display.clear(); korg.display.text("Hi!", 3, 4); });""",
    "blank": """korg.app("Chars", "TOOLS");
korg.onEvent("open", () => { korg.display.clear(); });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api29:{name}", "ok": bool(ok), "detail": str(detail)}


def weighted(data):
    return sum(b * (i + 1) for i, b in enumerate(data))


class World:
    def __init__(self, vsb, flash=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"]["api29"]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(1.0)
        self.sym = self.built.symbols
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], ["api29"])["api29"]
        self.dev.run(0.5)

    def word(self, pointer, offset):
        obj = self.dev.u32(pointer)
        return self.dev.m.u32(obj + offset) if obj not in (0, 0xFFFFFFFF) else None

    def firmware(self):
        return {"mode": self.word(LED_MANAGER, 0xB58), "bar": self.word(MODEL, 0x344), "screen": self.word(SCREENS, 0x2C)}

    def leaves(self):
        return {name: self.dev.call(self.sym["script_object_get_glue"], leaf, 0xFFFFFFFF) for name, leaf in LEAVES.items()}

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)

    def key(self, code, wait=0.4):
        self.dev.press(code, wait)

    def pattern(self):
        return self.dev.m.u32(self.dev.u32(SEQ) + 0x318)

    def ram(self):
        return self.dev.u32(PATTERN_PTR) + 4


def pad_mode_cases(w):
    """Each pad mode key: the leaf is the firmware's word, a change brings padMode events (PATTERN SET passes through a mode of
    its own on the way), the last one with the new mode; no change, no event."""
    seen, ok = [], True
    last, count = w.firmware()["mode"], w.vars()["modes"]
    for name in ["sequencer", "keyboard", "chord", "step_jump", "pattern_set", "trigger", "trigger"]:
        w.key(PAD_KEYS[name])
        fw, leaf, v = w.firmware()["mode"], w.leaves()["mode"], w.vars()
        events = v["modes"] - count
        seen.append((name, fw, leaf, events, v["mode"]))
        ok = ok and leaf == fw and (events >= 1 and v["mode"] == fw if fw != last else events == 0)
        last, count = fw, v["modes"]
    distinct = len({s[1] for s in seen})
    return [entry("pad_mode_follows_the_keys", ok and distinct >= 4 and not w.dev.m.asserts,
                  f"build {w.build}: (key, firmware, leaf, events, last) {seen}")]


def bar_cases(w):
    """A pattern of 4 bars in SEQUENCER mode: BAR 1 to 4 select the bar the pads show, the leaf follows the firmware's word."""
    w.dev.m.uc.mem_write(w.ram() + LENGTH_AT, bytes([3]))
    w.key(PAD_KEYS["sequencer"])
    seen = []
    for i, code in enumerate(BAR_KEYS[::-1] + BAR_KEYS):
        w.key(code)
        seen.append((i, w.firmware()["bar"], w.leaves()["bar"]))
    ok = all(fw == leaf for _, fw, leaf in seen) and [s[1] for s in seen[4:]] == [0, 1, 2, 3]
    return [entry("bar_follows_the_bar_keys", ok and not w.dev.m.asserts, f"build {w.build}: (press, firmware, leaf) {seen}")]


def screen_cases(w):
    """MENU and EXIT: the leaf is the screen number, each change one screen event."""
    v0 = w.vars()
    main = (w.firmware()["screen"], w.leaves()["screen"])
    w.key(MENU, 0.6)
    menu = (w.firmware()["screen"], w.leaves()["screen"], w.vars())
    w.key(EXIT, 0.6)
    back = (w.firmware()["screen"], w.leaves()["screen"], w.vars())
    ok = (main[0] == main[1] and menu[0] == menu[1] != main[0] and back[0] == back[1] == main[0]
          and menu[2]["screens"] - v0["screens"] >= 1 and menu[2]["screen"] == menu[0]
          and back[2]["screen"] == main[0] and back[2]["screens"] > menu[2]["screens"])
    return [entry("screen_follows_menu_and_exit", ok and not w.dev.m.asserts,
                  f"build {w.build}: main {main}, after MENU {menu[:2]} events {menu[2]['screens'] - v0['screens']}, "
                  f"after EXIT {back[:2]} events {back[2]['screens'] - v0['screens']} last {back[2]['screen']}")]


def write_cases(w):
    """WRITE and its confirmation: one write event with the pattern written."""
    p = w.pattern()
    before = w.vars()["writes"]
    w.key(WRITE, 1.0)
    w.key(WRITE, 1.0)
    w.dev.run(2.0)
    v = w.vars()
    return [entry("write_reports_the_pattern", v["writes"] - before == 1 and v["written"] == p and not w.dev.m.asserts,
                  f"build {w.build}: pattern {p}, events {v['writes'] - before}, pattern reported {v['written']}")]


def name_cases(w):
    """The name in RAM and a stored pattern's in the bank, 16 bytes each, as the program reads them every frame."""
    w.dev.m.uc.mem_write(w.ram() + NAME_AT, b"API 29 NAME\0\0\0\0\0")
    w.dev.m.uc.mem_write(w.dev.a(BANK) + STORED * 0x4000 + NAME_AT, b"STORED PATTERN!!")
    w.dev.run(0.3)
    v = w.vars()
    ram, bank = w.dev.read(w.ram() + NAME_AT, 16), w.dev.read(w.dev.a(BANK) + STORED * 0x4000 + NAME_AT, 16)
    ok = (v["length"] == 16 and v["first"] == ord("A") and v["sum"] == weighted(ram)
          and v["storedLength"] == 16 and v["storedSum"] == weighted(bank))
    return [entry("pattern_name_copies_16_bytes", ok and not w.dev.m.asserts,
                  f"build {w.build}: {v['length']}/{v['storedLength']} bytes, sums {v['sum']}/{v['storedSum']}, want {weighted(ram)}/{weighted(bank)}")]


def chars_cases(vsb, flash, programs):
    """An app draws [72, 105, 289, 0, 65] with chars and another "Hi!" with text: the same pixels, not those of a blank app."""
    shown = {}
    for name in ["chars", "text", "blank"]:
        dev = edit.boot(vsb, flash, programs, name)
        script_cases.open_app(dev, menu_cases.GROUP_TOOLS, APP_PAGE)
        dev.run(0.3)
        shown[name] = (dev.fb(), dev.m.asserts)
    ok = shown["chars"][0] == shown["text"][0] != shown["blank"][0] and not any(a for _, a in shown.values())
    return [entry("chars_draws_like_text", ok, f"chars == text {shown['chars'][0] == shown['text'][0]}, "
                  f"differs from blank {shown['chars'][0] != shown['blank'][0]}, asserts {[a for _, a in shown.values()]}")]


def cases(vsb, flash=None):
    w = World(vsb, flash)
    out = pad_mode_cases(w)
    out += screen_cases(w)
    out += name_cases(w)
    out += write_cases(w)
    out += bar_cases(World(vsb, flash))
    out += chars_cases(vsb, flash, w.request["programs"])
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
