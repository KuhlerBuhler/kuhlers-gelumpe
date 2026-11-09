"""Emulator cases of plugin API 23: korg.parts[i].ifxOn, ampEg, ifxType and sample become writable. A value set by a plugin leaves
the pattern in RAM and the sound engine's copy as the IFX ON or AMP EG key, the IFX encoder or the SAMPLE knob does, and the key's
LED as the key leaves it; IFX type stops at the build's type count, a sample slot the SAMPLE knob skips is not written. MFX SEND
(API 21) lights its LED now as its key does.

Each twin also compares what goes towards the sound engine (PR #401): the calls of the parameter set (part + 1, id, value, flag)
and of the dispatcher behind the part edit and the setters (part, code, value, refresh flag), on the Sampler also its filter,
AMP EG, MFX SEND and IFX ON paths. MFX SEND hands 127 to the sound engine as its key does, IFX TYPE, SAMPLE and MOD TYPE refresh
it as their encoders do, and the filter type refreshes it and lights the LPF, HPF and BPF LEDs as the filter keys do.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api23_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-07-plugin-api23-part-writes.md and docs/messungen/2026-11-09-plugin-part-dsp.md.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import unicorn

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
# the key of each value and the LED it lights (measure:2026-11-07/plugin-api23-part-writes)
KEYS = {"mfxSend": (0x1A, 15), "ampEg": (0x20, 16), "ifxOn": (0x21, 17)}
IFX_ENCODER, SAMPLE_ENCODER, MOD_ENCODER = 4, 1, 3
# the filter keys and their LEDs (data/panel.mjs)
FILTER_KEYS, FILTER_LEDS = {"HPF": 0x14, "BPF": 0x16, "LPF": 0x12}, (12, 13, 14)
# the dispatcher the part edit, the setters and the parameter set call with (pattern object + 0x401C, part, code, value) and a
# refresh flag on the stack; with the flag it calls the Sampler's filter, AMP EG, MFX SEND and IFX ON paths
# (measure:2026-11-09/plugin-part-dsp)
DISPATCH = 0xC004B208
PATHS = {0xC009A5EC: "filterPath", 0xC009A700: "ampEgPath", 0xC009A704: "mfxSendPath", 0xC009A764: "ifxOnPath"}

PROGRAM = """let eg = -1; let on = -1; let type = -1; let sample = -1;
korg.onEvent("ready", () => {
  korg.parts[1].ampEg = 1 - korg.parts[1].ampEg;
  korg.parts[1].ifxOn = 1 - korg.parts[1].ifxOn;
  korg.parts[1].ifxType = 7;
  korg.parts[1].sample = 3;
  eg = korg.parts[1].ampEg; on = korg.parts[1].ifxOn; type = korg.parts[1].ifxType; sample = korg.parts[1].sample;
});"""


def entry(name, ok, detail):
    return {"id": f"plugin_api23:{name}", "ok": bool(ok), "detail": str(detail)}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    fields()
    edit.compiled({"api23": PROGRAM})


def fields():
    code = ("import {PART_FIELDS} from './data/script/contract.mjs';"
            "process.stdout.write(JSON.stringify(PART_FIELDS.map(f => [f.name, f.offset])))")
    return node_json.run(code)


def changed(a, b):
    return [i for i in range(len(a)) if a[i] != b[i]]


class Dsp:
    """Records what goes towards the sound engine: the parameter set (part + 1, id, value, flag), the dispatcher (part, code,
    value, refresh flag) and, on the Sampler, its four paths (part, value). take() hands over the calls since the last take."""

    def __init__(self, dev, build):
        self.calls = []
        arm = dev.m.A
        watch = {script_hooks.PART_HELPERS[build]["HW_PARAM_SET"]: "paramSet", dev.a(DISPATCH): "dispatch"}
        if build != "synth":
            watch.update(PATHS)

        def hit(uc, at, size, data):
            r = [uc.reg_read(arm.UC_ARM_REG_R0 + i) for i in range(4)]
            name = watch[at]
            if name == "paramSet":
                self.calls.append((name, *r))
            elif name == "dispatch":
                flag = struct.unpack("<I", bytes(uc.mem_read(uc.reg_read(arm.UC_ARM_REG_SP), 4)))[0]
                self.calls.append((name, r[1], r[2], r[3], flag))
            else:
                self.calls.append((name, r[0], r[1]))
        for at in watch:
            dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, hit, begin=at, end=at)
        dev.m.uc.ctl_flush_tb()

    def take(self):
        out, self.calls = self.calls, []
        return out


def show(calls):
    return [" ".join(c if isinstance(c, str) else hex(c) for c in call) for call in calls]


class World:
    def __init__(self, vsb, flash=None, built=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.part = fields()
        self.built = built or script_hooks.build(edit.compiled({"api23": PROGRAM})["include"], build=self.build)
        self.s = self.built.symbols
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(0.3)
        self.obj = self.dev.u32(PATTERN_PTR)
        self.dsp = Dsp(self.dev, self.build)

    def state(self):
        return self.dev.read(self.obj, OBJECT)

    def at(self, part, name):
        return 4 + PART_BASE + part * PART_STRIDE + dict(self.part)[name]

    def value(self, part, name):
        at = self.at(part, name)
        state = self.state()
        return state[at] | state[at + 1] << 8 if name == "sample" else state[at]

    def read(self, part, name):
        v = self.dev.call(self.s["script_read_pattern_value_glue"], 0xFFFFFFFF, part, [n for n, _ in self.part].index(name))
        return v - (1 << 32) if v >= 1 << 31 else v

    def set_part(self, part, name, value):
        self.dev.call(self.s["script_seq_set_part_value_glue"], part, [n for n, _ in self.part].index(name), value & 0xFFFFFFFF)
        self.dev.run(0.4)

    def leds(self):
        return {i: self.dev.m.leds.get(i) for _, i in KEYS.values()}

    def encoder(self, index, delta):
        self.dev.m.send([1, index, 0, delta & 0xFF, 0])
        self.dev.run(0.4)

    def ifx_top(self):
        """The top IFX type of this build: the immediate of the IFX type setter's own `cmp r2, #top`."""
        _, _, cmp = script_hooks.PART_SETTERS[self.build]["ifxType"]
        return self.dev.u32(self.dev.a(cmp)) & 0xFF


def key_cases(w):
    """Each key pressed, pressed back, then the value it reached set by the plugin: the pattern object and the LEDs the same both
    ways. A part that is not selected gets the value without an LED."""
    out = []
    for name, (key, led) in KEYS.items():
        at = w.at(0, name)
        start, lit = w.state(), w.leds()
        w.dsp.take()
        w.dev.press(key, 0.4)
        menu, menu_lit, menu_dsp = w.state(), w.leds(), w.dsp.take()
        w.dev.press(key, 0.4)
        back, back_dsp = w.leds(), w.dsp.take()
        w.set_part(0, name, menu[at])
        plugin, plugin_lit, plugin_dsp = w.state(), w.leds(), w.dsp.take()
        diff = changed(menu, plugin)
        out.append(entry(f"{name}_like_the_key", menu[at] != start[at] and not diff and menu_lit == plugin_lit and back == lit
                         and menu_lit[led] != lit[led] and any(i >= 4 + COPY for i in changed(start, plugin)) and not w.dev.m.asserts,
                         f"key set {start[at]} -> {menu[at]}, plugin differs at {[(hex(i - 4), menu[i], plugin[i]) for i in diff][:6]}, "
                         f"LEDs key {menu_lit} plugin {plugin_lit} before {lit}, asserts {w.dev.m.asserts}"))
        w.set_part(0, name, start[at])
        on_dsp = w.dsp.take()
        out.append(entry(f"{name}_sound_engine_like_the_key", menu_dsp and plugin_dsp == menu_dsp and on_dsp == back_dsp
                         and not w.dev.m.asserts,
                         f"key {start[at]} -> {menu[at]} {show(menu_dsp)}, plugin {show(plugin_dsp)}; key back to {start[at]} "
                         f"{show(back_dsp)}, plugin {show(on_dsp)}"))
        before, lit = w.state(), w.leds()
        w.set_part(2, name, 1 - before[w.at(2, name)])
        out.append(entry(f"{name}_other_part_no_led", w.state()[w.at(2, name)] == 1 - before[w.at(2, name)] and w.leds() == lit
                         and not w.dev.m.asserts, f"part 3 {before[w.at(2, name)]} -> {w.state()[w.at(2, name)]}, LEDs {lit} -> {w.leds()}"))
    return out


def encoder_twin(w, name, index):
    """The encoder turned by one on the selected part, back, then the value it reached set by the plugin."""
    start, picture = w.state(), w.dev.fb()
    step = 1
    w.dsp.take()
    w.encoder(index, step)
    if w.state() == start:
        step = -1
        w.encoder(index, step)
    want = w.value(0, name)
    menu, shown, menu_dsp = w.state(), w.dev.fb(), w.dsp.take()
    w.encoder(index, -step)
    w.dev.run(2.0)
    w.dsp.take()
    w.set_part(0, name, want)
    plugin, drawn, plugin_dsp = w.state(), w.dev.fb(), w.dsp.take()
    diff = changed(menu, plugin)
    screen = shown == drawn
    sound = bool(menu_dsp) and plugin_dsp == menu_dsp
    return (menu != start and not diff and shown != picture and screen and sound and not w.dev.m.asserts,
            f"encoder set {want}, encoder changed {[hex(i - 4) for i in changed(start, menu)][:8]}, plugin differs at "
            f"{[(hex(i - 4), menu[i], plugin[i]) for i in diff][:6]}, screen as the encoder's {shown == drawn}, sound engine "
            f"encoder {show(menu_dsp)} plugin {show(plugin_dsp)}, asserts {w.dev.m.asserts}")


def mod_type_cases(w):
    ok, detail = encoder_twin(w, "modType", MOD_ENCODER)
    return [entry("modType_like_the_encoder", ok, detail)]


def filter_cases(w):
    """Each filter key pressed, then LPF, then the type the key reached set by the plugin: the pattern object, the LPF, HPF and
    BPF LEDs and what goes to the sound engine the same both ways. Another part than the selected one gets no LED."""
    out = []
    leds = lambda: {i: w.dev.m.leds.get(i) for i in FILTER_LEDS}
    for name, key in FILTER_KEYS.items():
        w.dsp.take()
        w.dev.press(key, 0.4)
        menu, menu_lit, menu_dsp = w.state(), leds(), w.dsp.take()
        want = w.value(0, "filterType")
        w.dev.press(FILTER_KEYS["LPF" if name != "LPF" else "HPF"], 0.4)
        w.dev.run(2.0)
        w.dsp.take()
        w.set_part(0, "filterType", want)
        plugin, plugin_lit, plugin_dsp = w.state(), leds(), w.dsp.take()
        diff = changed(menu, plugin)
        out.append(entry(f"filterType_like_the_{name}_key", not diff and menu_lit == plugin_lit and menu_dsp and plugin_dsp == menu_dsp
                         and not w.dev.m.asserts,
                         f"key set {want}, plugin differs at {[(hex(i - 4), menu[i], plugin[i]) for i in diff][:6]}, LEDs key {menu_lit} "
                         f"plugin {plugin_lit}, sound engine key {show(menu_dsp)} plugin {show(plugin_dsp)}, asserts {w.dev.m.asserts}"))
    lit = leds()
    other = w.value(2, "filterType")
    w.set_part(2, "filterType", 12 if other != 12 else 7)
    out.append(entry("filterType_other_part_no_led", w.value(2, "filterType") != other and leds() == lit and not w.dev.m.asserts,
                     f"part 3 {other} -> {w.value(2, 'filterType')}, LEDs {lit} -> {leds()}"))
    return out


def ifx_type_cases(w):
    ok, detail = encoder_twin(w, "ifxType", IFX_ENCODER)
    out = [entry("ifxType_like_the_encoder", ok, detail)]
    top = w.ifx_top()
    w.set_part(1, "ifxType", 200)
    high = w.read(1, "ifxType")
    w.set_part(1, "ifxType", -5)
    low = w.read(1, "ifxType")
    out.append(entry("ifxType_stops_at_the_type_count", high == top and low == 0 and not w.dev.m.asserts,
                     f"200 -> {high}, -5 -> {low}, top {top} ({top + 1} types)"))
    return out


def sample_cases(w):
    if not script_hooks.PART_HELPERS[w.build]["HW_SAMPLE_NEXT"]:
        before = w.state()
        w.set_part(1, "sample", 3)
        return [entry("sample_not_written", w.state() == before and not w.dev.m.asserts,
                      f"no samples on this build, changed {[hex(i - 4) for i in changed(before, w.state())][:6]}")]
    ok, detail = encoder_twin(w, "sample", SAMPLE_ENCODER)
    out = [entry("sample_like_the_knob", ok, detail)]
    next_slot = script_hooks.PART_HELPERS[w.build]["HW_SAMPLE_NEXT"]
    empty = next(n for n in range(999, 0, -1) if w.dev.call(next_slot, n, 1) != n)
    full = next(n for n in range(2, 999) if w.dev.call(next_slot, n, 1) == n and n != w.value(1, "sample"))
    before = w.state()
    w.set_part(1, "sample", empty)
    w.set_part(1, "sample", 5000)
    skipped = changed(before, w.state())
    w.set_part(1, "sample", full)
    out.append(entry("sample_empty_slot_not_written", not skipped and w.read(1, "sample") == full and not w.dev.m.asserts,
                     f"slot {empty} and 5000 changed {[hex(i - 4) for i in skipped][:6]}; slot {full} read back {w.read(1, 'sample')}"))
    return out


def plugin_cases(w):
    """A plugin writes and reads the four values by name."""
    before = w.state()
    request = edit.compiled({"api23": PROGRAM})
    program = request["programs"]["api23"]
    entry_at = script_cases.install(w.dev, w.built, request["programs"], ["api23"])["api23"]
    w.dev.run(0.5)
    seen = script_cases.variables(w.dev, entry_at, program)
    sample = script_hooks.PART_HELPERS[w.build]["HW_SAMPLE_NEXT"] != 0
    want = {"eg": 1 - before[w.at(1, "ampEg")], "on": 1 - before[w.at(1, "ifxOn")], "type": 7,
            "sample": 3 if sample else before[w.at(1, "sample")] | before[w.at(1, "sample") + 1] << 8}
    ram = {"eg": w.value(1, "ampEg"), "on": w.value(1, "ifxOn"), "type": w.value(1, "ifxType"), "sample": w.value(1, "sample")}
    return [entry("plugin_sets_and_reads_by_name", seen == {**seen, **want} and ram == want and not w.dev.m.asserts,
                  f"read back {dict((k, seen.get(k)) for k in want)}, in RAM {ram}, want {want}, asserts {w.dev.m.asserts}")]


def cases(vsb, flash=None):
    w = World(vsb, flash)
    out = key_cases(w)
    w = World(vsb, flash, w.built)
    out += ifx_type_cases(w)
    w = World(vsb, flash, w.built)
    out += sample_cases(w)
    w = World(vsb, flash, w.built)
    out += mod_type_cases(w)
    w = World(vsb, flash, w.built)
    out += filter_cases(w)
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
