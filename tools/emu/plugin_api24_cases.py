"""Emulator cases of plugin API 24: a value a plugin sets behaves as the knob, encoder, key or menu page that sets it on the
device. korg.seq.setPartValue sends the MIDI CC the knob, the cutoff encoder, IFX ON or MFX SEND sends, opens the parameter window
the knob opens (also on the blue, whose part edit is measured now) and leaves the pattern object as the control does; seven more
part values (last step, motion sequence, pad velocity, scale mode, priority, groove type and depth) and five pattern values
(alternate 13-14 and 15-16, MFX hold, the touchpad's X and Y) become readable and writable; korg.display.popups keeps the window
shut on a plugin's writes. Each knob twin and the cutoff encoder's also compare what goes to the sound engine (PR #401): the
knob's parameter set (part + 1, id, value, 1) after the part edit, and the dispatcher calls of both.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api24_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-08-plugin-api24-part-cc.md and docs/messungen/2026-11-09-plugin-part-dsp.md.
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
import plugin_api23_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import UART1, load_flash  # noqa: E402

PATTERN_PTR = 0xC033E6A4        # the pattern object; its block starts at +4, the sound engine's copy at block + 0x4000
OBJECT = 0x4274
COPY = 0x4000
PART_BASE, PART_STRIDE = 0x800, 0x330
KEYS = menu_cases.KEYS
PATTERN_SCREEN, PART_SCREEN = 3, 7
# the knob of each value, the panel's index (data/panel.mjs); GLIDE is SHIFT and the PITCH knob (measure:2026-11-08/plugin-api24-part-cc)
KNOBS = {"level": 0, "pan": 1, "pitch": 2, "resonance": 3, "egInt": 4, "modDepth": 5, "attack": 6, "ifxEdit": 7, "decay": 8,
         "oscEdit": 9, "modSpeed": 10}
SHIFT, CUTOFF_ENCODER = 0x0A, 2
# the key of each value and its LED
PART_KEYS = {"ifxOn": (0x21, 17), "mfxSend": (0x1A, 15)}
MFX_HOLD = (0x07, 0x1D)
# the page of the Part and the Pattern menu that turns each value, the same on all three firmwares
PART_PAGES = {"lastStep": 16, "grooveType": 17, "grooveDepth": 18, "priority": 20, "motionMode": 21, "padVelocity": 22, "scaleMode": 23}
PATTERN_PAGES = {"alternate1314": 11, "alternate1516": 12}
PAD_CC = {"mfxPadX": 102, "mfxPadY": 103}
# rows 0 to 54 of the picture: the bottom rows hold a status line that is not part of the value
KEEP = bytes(0xFF if row < 6 else 0x7F if row == 6 else 0 for row in range(8) for _ in range(128))

QUIET = """let quiet = -1; let level = -1;
korg.onEvent("ready", () => {
  korg.display.popups = 0;
  korg.parts[0].level = 33;
  korg.parts[0].lastStep = 7;
  korg.current.mfxHold = 1;
  quiet = korg.display.popups; level = korg.parts[0].level;
});"""
LOUD = """let shown = -1;
korg.onEvent("ready", () => { korg.parts[0].level = 33; shown = korg.read.popups(); });"""


def entry(name, ok, detail):
    return {"id": f"plugin_api24:{name}", "ok": bool(ok), "detail": str(detail)}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    fields()
    edit.compiled({"quiet": QUIET, "loud": LOUD})


def fields():
    code = ("import {PATTERN_FIELDS, PART_FIELDS} from './data/script/contract.mjs';"
            "process.stdout.write(JSON.stringify([PATTERN_FIELDS.map(f => [f.name, f.offset]), PART_FIELDS.map(f => [f.name, f.offset])]))")
    return node_json.run(code)


def changed(a, b):
    return [i for i in range(len(a)) if a[i] != b[i]]


class World:
    def __init__(self, vsb, flash=None, built=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.pattern, self.part = fields()
        self.built = built or script_hooks.build(edit.compiled({"quiet": QUIET, "loud": LOUD})["include"], build=self.build)
        self.s = self.built.symbols
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(0.3)
        self.obj = self.dev.u32(PATTERN_PTR)
        self.mark = 0
        self.dsp = plugin_api23_cases.Dsp(self.dev, self.build)

    def state(self):
        return self.dev.read(self.obj, OBJECT)

    def at(self, part, name):
        return 4 + PART_BASE + part * PART_STRIDE + dict(self.part)[name]

    def pattern_at(self, name):
        return 4 + dict(self.pattern)[name]

    def read(self, part, name):
        names = [n for n, _ in (self.pattern if part < 0 else self.part)]
        v = self.dev.call(self.s["script_read_pattern_value_glue"], 0xFFFFFFFF, part & 0xFFFFFFFF, names.index(name))
        return v - (1 << 32) if v >= 1 << 31 else v

    def set_part(self, part, name, value):
        self.dev.call(self.s["script_seq_set_part_value_glue"], part, [n for n, _ in self.part].index(name), value & 0xFFFFFFFF)
        self.dev.run(0.4)

    def set_pattern(self, name, value):
        self.dev.call(self.s["script_seq_set_pattern_value_glue"], [n for n, _ in self.pattern].index(name), value & 0xFFFFFFFF)
        self.dev.run(0.4)

    def midi(self):
        """The MIDI bytes sent since the last call, without the clock and active sensing."""
        tx = self.dev.m.uart[UART1]["tx"]
        data = bytes(tx[self.mark:])
        self.mark = len(tx)
        return bytes(b for b in data if b < 0xF8)

    def knob(self, index, raw, shift=False):
        if shift:
            self.dev.m.press(SHIFT, True)
            self.dev.run(0.1)
        self.dev.m.send([2, index, 0, raw, 0])
        self.dev.run(0.4)
        if shift:
            self.dev.m.press(SHIFT, False)
            self.dev.run(0.3)

    def page(self, screen, k):
        menu_cases.go(self.dev, screen)
        for _ in range(40):
            if menu_cases.counter(self.dev)[0] == k:
                return
            self.dev.press(KEYS["edit_next"], 0.25)
        raise AssertionError(f"page {k} not reached")

    def reenter(self, k):
        self.dev.press(KEYS["edit_next"], 0.25)
        self.dev.press(KEYS["edit_prev"], 0.25)
        assert menu_cases.counter(self.dev)[0] == k, menu_cases.counter(self.dev)
        return bytes(b & m for b, m in zip(self.dev.fb(), KEEP))


def knob_twin(w, name, index, shift=False):
    """The knob turned to a value, then elsewhere until its window closed, then the value it reached set by the plugin: the pattern
    object, the MIDI out and the screen the same both ways."""
    w.knob(index, 60, shift)
    w.dev.run(2.5)
    w.midi()
    w.dsp.take()
    w.knob(index, 200, shift)
    want = w.read(0, name)
    knob = (w.state(), w.midi(), w.dev.fb(), w.dsp.take())
    w.knob(index, 60, shift)
    w.dev.run(2.5)
    w.midi()
    if shift:                   # the window draws differently while SHIFT is down: the plugin writes with SHIFT held as well
        w.dev.m.press(SHIFT, True)
        w.dev.run(0.1)
    w.dsp.take()
    w.set_part(0, name, want)
    if shift:
        w.dev.m.press(SHIFT, False)
        w.dev.run(0.3)
    plugin = (w.state(), w.midi(), w.dev.fb(), w.dsp.take())
    diff = changed(knob[0], plugin[0])
    sound = any(c[0] == "paramSet" for c in knob[3]) and knob[3] == plugin[3]
    return entry(f"{name}_like_the_knob", not diff and knob[1] == plugin[1] and knob[1] and knob[2] == plugin[2] and sound
                 and not w.dev.m.asserts,
                 f"knob set {want}, plugin differs at {[(hex(i - 4), knob[0][i], plugin[0][i]) for i in diff][:6]}, MIDI knob "
                 f"{knob[1].hex(' ')} plugin {plugin[1].hex(' ')}, screen equal {knob[2] == plugin[2]}, sound engine knob "
                 f"{plugin_api23_cases.show(knob[3])} plugin {plugin_api23_cases.show(plugin[3])}, asserts {w.dev.m.asserts}")


def knob_cases(w):
    out = [knob_twin(w, name, index) for name, index in KNOBS.items()]
    out.append(knob_twin(w, "glide", KNOBS["pitch"], shift=True))
    return out


def cutoff_case(w):
    """The cutoff encoder turned down by one (the start may be its top), back, then the value it reached set by the plugin:
    object, MIDI and screen."""
    start = w.state()
    w.dev.run(2.5)
    w.midi()
    w.dsp.take()
    w.dev.m.send([1, CUTOFF_ENCODER, 0, 0xFF, 0])
    w.dev.run(0.4)
    want = w.read(0, "cutoff")
    enc = (w.state(), w.midi(), w.dev.fb(), w.dsp.take())
    w.dev.m.send([1, CUTOFF_ENCODER, 0, 1, 0])
    w.dev.run(2.5)
    w.midi()
    w.dsp.take()
    w.set_part(0, "cutoff", want)
    plugin = (w.state(), w.midi(), w.dev.fb(), w.dsp.take())
    diff = changed(enc[0], plugin[0])
    sound = any(c[0] == "paramSet" for c in enc[3]) and enc[3] == plugin[3]
    return entry("cutoff_like_the_encoder", enc[0] != start and not diff and enc[1] == plugin[1] and enc[1] and enc[2] == plugin[2]
                 and sound and not w.dev.m.asserts,
                 f"encoder set {want}, plugin differs at {[(hex(i - 4), enc[0][i], plugin[0][i]) for i in diff][:6]}, MIDI encoder "
                 f"{enc[1].hex(' ')} plugin {plugin[1].hex(' ')}, screen equal {enc[2] == plugin[2]}, sound engine encoder "
                 f"{plugin_api23_cases.show(enc[3])} plugin {plugin_api23_cases.show(plugin[3])}")


def key_cases(w):
    """IFX ON and MFX SEND pressed, pressed back, then the value the key reached set by the plugin: the same MIDI CC, object and
    LED. Another part gets its CC on its own channel."""
    out = []
    for name, (key, led) in PART_KEYS.items():
        at = w.at(0, name)
        w.midi()
        w.dev.press(key, 0.4)
        menu, sent, lit = w.state(), w.midi(), w.dev.m.leds.get(led)
        w.dev.press(key, 0.4)
        w.midi()
        w.set_part(0, name, menu[at])
        plugin, got, plugin_lit = w.state(), w.midi(), w.dev.m.leds.get(led)
        out.append(entry(f"{name}_cc_like_the_key", sent and sent == got and menu == plugin and lit == plugin_lit and not w.dev.m.asserts,
                         f"key sent {sent.hex(' ')} plugin {got.hex(' ')}, object differs at {[hex(i - 4) for i in changed(menu, plugin)][:6]}, "
                         f"LED {lit} {plugin_lit}"))
    w.set_part(4, "level", 90)
    got = w.midi()
    out.append(entry("other_part_on_its_channel", bytes([0xB4, 7, 90]) in got, f"part 5 level 90 sent {got.hex(' ')}"))
    return out


def window_cases(w):
    """A write opens the knob's window for the selected part; korg.display.popups(0) keeps it shut for that plugin's writes."""
    w.dev.run(2.5)
    idle = w.dev.fb()
    request = edit.compiled({"quiet": QUIET, "loud": LOUD})
    at = script_cases.install(w.dev, w.built, request["programs"], ["loud"])["loud"]
    w.dev.run(0.5)
    shown = w.dev.fb()
    loud = script_cases.variables(w.dev, at, request["programs"]["loud"])
    out = [entry("write_opens_the_window", shown != idle and loud.get("shown") == 1 and w.read(0, "level") == 33,
                 f"screen changed {shown != idle}, popups read {loud.get('shown')}, level {w.read(0, 'level')}")]
    w2 = World(bytes(0x100) + w.payload, None, w.built)
    w2.dev.run(2.5)
    idle = w2.dev.fb()
    before = w2.state()
    at = script_cases.install(w2.dev, w2.built, request["programs"], ["quiet"])["quiet"]
    w2.dev.run(0.5)
    seen = script_cases.variables(w2.dev, at, request["programs"]["quiet"])
    after = w2.state()
    out.append(entry("popups_off_keeps_it_shut", w2.dev.fb() == idle and seen.get("quiet") == 0 and seen.get("level") == 33
                     and after[w2.at(0, "lastStep")] == 7 and after[w2.pattern_at("mfxHold")] == 1 and before != after
                     and not w2.dev.m.asserts,
                     f"screen unchanged {w2.dev.fb() == idle}, read {seen}, last step {after[w2.at(0, 'lastStep')]}, "
                     f"MFX hold {after[w2.pattern_at('mfxHold')]}"))
    return out


def menu_twin(w, screen, k, name, part):
    """The page turned by one (down at its top), back, then the value the menu reached set by the plugin: object and page."""
    w.page(screen, k)
    start = w.state()
    step = 1
    w.dev.turn(step, 0.4)
    if w.state() == start:
        step = -1
        w.dev.turn(step, 0.4)
    want = w.read(part, name)
    menu = (w.state(), w.reenter(k))
    w.dev.turn(-step, 0.4)
    w.reenter(k)
    if part < 0:
        w.set_pattern(name, want)
    else:
        w.set_part(part, name, want)
    plugin = (w.state(), w.reenter(k))
    moved = changed(start, menu[0])
    return entry(f"{name}_like_the_menu", moved and menu[0] == plugin[0] and menu[1] == plugin[1] and not w.dev.m.asserts,
                 f"menu set {want}, menu changed {[hex(i - 4) for i in moved][:6]}, plugin differs at "
                 f"{[hex(i - 4) for i in changed(menu[0], plugin[0])][:6]}, page equal {menu[1] == plugin[1]}")


def menu_cases_(w):
    out = [menu_twin(w, PART_SCREEN, k, name, 0) for name, k in PART_PAGES.items()]
    out += [menu_twin(w, PATTERN_SCREEN, k, name, -1) for name, k in PATTERN_PAGES.items()]
    top = w.dev.u32(script_hooks.PART_SETTERS[w.build]["grooveType"][2]) & 0xFF
    w.set_part(1, "grooveType", 200)
    out.append(entry("grooveType_stops_at_the_groove_count", w.read(1, "grooveType") == top, f"200 -> {w.read(1, 'grooveType')}, top {top}"))
    return out


def mfx_cases(w, vsb, flash):
    """MFX HOLD pressed on one device, set by the plugin on a second one from the same start: object and LED, then off the same
    way, and a write of the value it has presses nothing. The touchpad's X and Y are written and sent as the touchpad sends them."""
    key, led = MFX_HOLD
    at = w.pattern_at("mfxHold")
    w2 = World(vsb, flash, w.built)
    out = []
    for value in (1, 0):
        w.dev.press(key, 0.4)
        w2.set_pattern("mfxHold", value)
        menu, lit, plugin, plugin_lit = w.state(), w.dev.m.leds.get(led), w2.state(), w2.dev.m.leds.get(led)
        out.append(entry(f"mfxHold_{value}_like_the_key", menu[at] == value and menu == plugin and lit == plugin_lit
                         and not w.dev.m.asserts and not w2.dev.m.asserts,
                         f"key set {menu[at]}, object differs at {[hex(i - 4) for i in changed(menu, plugin)][:6]}, LED {lit} {plugin_lit}"))
    w2.set_pattern("mfxHold", 0)
    out.append(entry("mfxHold_same_value_presses_nothing", w2.state() == plugin and w2.dev.m.leds.get(led) == plugin_lit,
                     f"object differs at {[hex(i - 4) for i in changed(plugin, w2.state())][:6]}"))
    for name, cc in PAD_CC.items():
        w.midi()
        w.set_pattern(name, 50)
        got = w.midi()
        out.append(entry(f"{name}_written_and_sent", w.read(-1, name) == 50 and w.state()[w.pattern_at(name)] == 50
                         and bytes([0xB0, cc, 50]) in got and not w.dev.m.asserts, f"read {w.read(-1, name)}, sent {got.hex(' ')}"))
    return out


def sliced(w, sample):
    """The sliced check (HW_SAMPLE_SLICED) answers 1 for this sample: the card in the emulator holds no sliced sample."""
    import unicorn
    uc, R = w.dev.m.uc, w.dev.m.A

    def hook(u, addr, size, data):
        if u.reg_read(R.UC_ARM_REG_R0) == sample:
            u.reg_write(R.UC_ARM_REG_R0, 1)
            u.reg_write(R.UC_ARM_REG_PC, u.reg_read(R.UC_ARM_REG_LR))
    address = script_hooks.PART_HELPERS[w.build]["HW_SAMPLE_SLICED"]
    uc.hook_add(unicorn.UC_HOOK_CODE, hook, begin=address, end=address)
    uc.ctl_flush_tb()


def slice_case(vsb, flash, built):
    """The SAMPLE encoder turned up onto a sliced sample on one device, the sample set by the plugin on a second one: object and
    screen, the slice included (param 0x1E, -1 as the encoder passes it turned up)."""
    w, w2 = World(vsb, flash, built), World(vsb, flash, built)
    for d in (w, w2):
        d.dev.run(2.5)
    start = w.read(0, "sample")
    w.dev.m.send([1, 1, 0, 1, 0])
    w.dev.run(0.4)
    want = w.read(0, "sample")
    for d in (w, w2):
        sliced(d, want)
    w.dev.m.send([1, 1, 0, 0xFF, 0])
    w.dev.run(2.5)
    w.dev.m.send([1, 1, 0, 1, 0])
    w.dev.run(0.4)
    w2.set_part(0, "sample", want)
    enc, plugin = (w.state(), w.dev.fb()), (w2.state(), w2.dev.fb())
    diff = changed(enc[0], plugin[0])
    return entry("sample_slice_like_the_encoder", want != start and not diff and enc[1] == plugin[1] and not w.dev.m.asserts
                 and not w2.dev.m.asserts, f"encoder {start} -> {want}, plugin differs at "
                 f"{[(hex(i - 4), enc[0][i], plugin[0][i]) for i in diff][:6]}, screen equal {enc[1] == plugin[1]}")


def cases(vsb, flash=None):
    w = World(vsb, flash)
    out = knob_cases(w)
    w = World(vsb, flash, w.built)
    out.append(cutoff_case(w))
    out += key_cases(w)
    w = World(vsb, flash, w.built)
    out += menu_cases_(w)
    w = World(vsb, flash, w.built)
    out += mfx_cases(w, vsb, flash)
    if w.build != "synth":
        out.append(slice_case(vsb, flash, w.built))
    w = World(vsb, flash, w.built)
    out += window_cases(w)
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
