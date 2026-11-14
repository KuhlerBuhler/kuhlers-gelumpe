"""Emulator cases of plugin API 31: korg.audio.level reads the two levels of the level meter as the firmware smooths them, also
while the meter is off (Global power save Always) or a plugin holds the LEDs.

    python3 tools/emu/plugin_api31_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api31-audio-level.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

LEVELS = 0xC033E4F4                             # -> the object the meter reads: +0x13 one level, the top byte of +0x14 the other
METER = 0xC0088284                              # the bottom LEDs' function, every 40 ms; the emulator's DSP side clears the levels
SMOOTH_STATE = 0xC06913A8                       # Sampler places; Dev.a gives the synth's (data/synth-map/)
LED_MANAGER, LED_LOCK = 0xC0345A1C, 0xB98         # the LED manager: +0xB98 the lock korg.ledHold sets
POWER_SAVE = 0xC0691324                         # -> Global: +0x29 power save, 2 Always switches the meter off

PROGRAMS = {
    "api31": """let l0 = -1; let l1 = -1;
korg.onEvent("frame", () => { l0 = korg.audio.level(0); l1 = korg.audio.level(1); });""",
    "holder": """let l0 = -1; let l1 = -1;
korg.onEvent("ready", () => { korg.ledHold(1); });
korg.onEvent("frame", () => { l0 = korg.audio.level(0); l1 = korg.audio.level(1); });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api31:{name}", "ok": bool(ok), "detail": str(detail)}


class World:
    def __init__(self, vsb, flash, name):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"][name]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(1.0)
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], [name])[name]
        self.raw = (0, 0)
        at = self.dev.a(METER)
        self.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, a, s, d: self.poke(), begin=at, end=at)
        self.dev.m.uc.ctl_flush_tb()
        self.dev.run(0.5)

    def poke(self):
        """The raw levels into the object, right before every call of the meter, as the DSP side would leave them."""
        obj = self.dev.u32(LEVELS)
        if obj in (0, 0xFFFFFFFF):
            return
        a, b = self.raw
        word = self.dev.m.u32(obj + 0x14)
        self.dev.m.uc.mem_write(obj + 0x13, bytes([a & 0xFF]))
        self.dev.m.uc.mem_write(obj + 0x14, ((word & 0xFFFFFF) | ((b & 0xFF) << 24)).to_bytes(4, "little"))

    def feed(self, a, b):
        """Both raw levels as the firmware gets them (signed bytes), then 1.5 s: the smoothing settles within about 25 steps."""
        self.raw = (a, b)
        self.dev.run(1.5)

    def state(self):
        at = self.dev.a(SMOOTH_STATE)
        return [self.dev.m.u32(at + 4 * i) for i in range(2)]

    def leaves(self):
        v = script_cases.variables(self.dev, self.at, self.program)
        return v["l0"], v["l1"]


def signed(word):
    return word - (1 << 32) if word & 0x80000000 else word


def want(raw):
    return max(0, min(254, 2 * (raw - 256 if raw > 127 else raw)))


def near(got, raw):
    """The firmware's integer smoothing settles one below twice a level above 0 (measured)."""
    return want(raw) - 1 <= got <= want(raw)


def follow(w, pairs):
    """Each pair of raw levels: the leaves are twice the levels (0 to 254, one less as the smoothing settles) and the firmware's
    smoothing state shifted by 7."""
    seen, ok = [], True
    for a, b in pairs:
        w.feed(a, b)
        got, state = w.leaves(), [max(0, min(254, signed(s) >> 7)) for s in w.state()]
        ok = ok and near(got[0], a) and near(got[1], b) and list(got) == state
        seen.append(((a, b), got, state))
    return ok and not w.dev.m.asserts, seen


def cases(vsb, flash=None):
    w = World(vsb, flash, "api31")
    ok, seen = follow(w, [(100, 50), (127, 0), (0x90, 20), (0, 0)])
    out = [entry("level_follows_the_meter", ok, f"build {w.build}: (raw, leaves, firmware state >> 7) {seen}")]
    h = World(vsb, flash, "holder")
    ok, seen = follow(h, [(60, 120), (10, 5)])
    lock = h.dev.m.uc.mem_read(h.dev.u32(h.dev.a(LED_MANAGER)) + LED_LOCK, 1)[0]
    out.append(entry("level_while_a_plugin_holds_the_leds", ok and lock == 1,
                     f"build {h.build}: LED lock {lock}, (raw, leaves, firmware state >> 7) {seen}"))
    w.dev.m.uc.mem_write(w.dev.u32(w.dev.a(POWER_SAVE)) + 0x29, b"\x02")
    ok, seen = follow(w, [(30, 40), (90, 70)])
    dark = menu_cases.leds(w.dev)
    out.append(entry("level_while_power_save_turns_the_meter_off", ok and not any(dark),
                     f"build {w.build}: bottom LEDs {dark}, (raw, leaves, firmware state >> 7) {seen}"))
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
