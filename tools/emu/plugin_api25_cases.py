"""Emulator cases of plugin API 25: korg.keyDown and korg.keyUp, korg.padDown and korg.padUp, korg.encoder and korg.touch give
the firmware the panel's own messages, so a plugin works the device like a finger; korg.knob is held against the knob's message.

Every case runs in two worlds booted the same way with the same plugin: in one the panel sends the messages, in the other the
plugin makes the calls. After each step both must agree on the pattern in RAM, the screen, the LEDs, the pad mode, the selected
part, the mute bytes, the transport and the MIDI the firmware sent.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api25_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-08-plugin-api25-panel-calls.md.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_api15_cases as api15  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import remote_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import UART1, load_flash  # noqa: E402

COMMAND = 9                     # the stored pattern whose part 0 carries the command: filter type a counter, then op and arguments
LEDMGR = 0xC0345A1C             # the LED manager; +0xB58 the pad mode: 0 PART MUTE, 3 TRIGGER, 4 SEQUENCER, 5 KEYBOARD
OBJECT = 0x4274
REC, STOP, PLAY, MENU, SHIFT, EXIT, PART_MUTE = 0, 1, 2, 9, 10, 13, 16
TRIGGER, SEQUENCER, KEYBOARD, CHORD, TOUCH_SCALE, MASTER_FX, TOUCH = 19, 21, 23, 24, 5, 6, 34
KNOBS = {"LEVEL": 0, "RESONANCE": 3, "ATTACK": 6}
BLINK = 0x14                    # an LED that blinks on its own clock
CLOCK = 0xF8                    # MIDI clock: the plugin's call lands a frame after the panel's message, the clock bytes in between differ
FADING = range(5)               # the encoder LEDs fade out after a turn
SETTLE = 2.0
RETRIES = 12                    # a blinking text or LED may be caught at its edge: each field has to match once within 0.6 s, a blink period

# op, then p (cutoff), d (EG INT, signed), y (MOD SPEED) of part 0 of the command pattern
OPS = {"keyDown": 1, "keyUp": 2, "padDown": 3, "padUp": 4, "encoder": 5, "touch": 6, "lift": 7, "pressKey": 8, "knob": 9,
       "padHold": 10, "padFree": 11, "fault": 12}
PROGRAM = f"""let done = 0; let presses = 0; let pads = 0; let touches = 0;
korg.onEvent("buttonPress", (k) => {{ presses = presses + 1; }});
korg.onEvent("pad", (i, down, v) => {{ pads = pads + 1; }});
korg.onEvent("touch", (x, y, first) => {{ touches = touches + 1; }});
korg.onEvent("frame", () => {{
  let go = korg.read.patternValue({COMMAND}, 0, 1);
  if (go == done) return;
  done = go;
  let op = korg.read.patternValue({COMMAND}, 0, 2);
  let p = korg.read.patternValue({COMMAND}, 0, 3);
  let d = korg.read.patternValue({COMMAND}, 0, 4);
  let y = korg.read.patternValue({COMMAND}, 0, 6);
  if (op == 1) korg.keyDown(p);
  if (op == 2) korg.keyUp(p);
  if (op == 3) korg.padDown(p, d);
  if (op == 4) korg.padUp(p);
  if (op == 5) korg.encoder(p, d);
  if (op == 6) korg.touch(p * 4, y * 4);
  if (op == 7) korg.touch(-1, 0);
  if (op == 8) korg.pressKey(p);
  if (op == 9) korg.knob(p, y);
  if (op == 10) korg.padHold(1);
  if (op == 11) korg.padHold(0);
  if (op == 12) korg.keyHold(korg.key.EXIT, 1);
}});"""


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"api25": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"plugin_api25:{name}", "ok": bool(ok), "detail": str(detail)}


class World:
    """A booted device with the plugin running. `panel` sends the messages of a step, `plugin` has the plugin make the calls."""

    def __init__(self, vsb, flash, built, programs):
        self.dev, self.at = edit.running(vsb, flash, built, programs, "api25")
        self.program = programs["api25"]
        self.seq = 0
        self.poke(0, 0, 0, 0, 0)     # the stored byte, whatever it held: no command before the first step
        self.dev.run(0.3)
        self.midi = len(self.dev.m.uart[UART1]["tx"])
        self.seen = []
        dev = self.dev

        # the dispatcher's start, before the input filter: what the panel queue hands the firmware
        def dispatch(uc, *_):
            self.seen.append(bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0) + 0xC, 8)))
        dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, dispatch, begin=dev.a(remote_cases.DISPATCH), end=dev.a(remote_cases.DISPATCH))
        dev.m.uc.ctl_flush_tb()

    def poke(self, seq, op, p, d, y):
        base = self.dev.a(edit.BANK) + COMMAND * 0x4000 + edit.PART_AT(0)
        edit.poke(self.dev, base + 13, [op, p, d & 0xFF])
        edit.poke(self.dev, base + 17, [y])
        edit.poke(self.dev, base + 12, [seq])

    def call(self, op, p=0, d=0, y=0, wait=0.15):
        self.seq = self.seq % 250 + 1
        self.poke(self.seq, OPS[op], p, d, y)
        self.dev.run(wait)

    def send(self, msgs, wait=0.15):
        for m in msgs:
            self.dev.m.send(m)
        self.dev.run(wait)

    def vars(self):
        return edit.script_cases.variables(self.dev, self.at, self.program)

    def state(self):
        dev = self.dev
        mgr = dev.u32(dev.a(LEDMGR))
        return {
            "pattern": dev.read(dev.u32(edit.PATTERN_PTR), OBJECT),
            "screen": hashlib.sha256(dev.fb()).hexdigest()[:12],
            "leds": {k: v for k, v in dev.m.leds.items() if k != BLINK},
            "pad_mode": dev.u32(mgr + 0xB58),
            "part": dev.u32(dev.a(edit.PART)),
            "mutes": dev.read(dev.a(edit.MUTE), 0x330 * 16)[::0x330].hex(),
            "transport": dev.u32(dev.a(edit.TRANSPORT)),
            "midi": bytes(b for b in dev.m.uart[UART1]["tx"][self.midi:] if b != CLOCK).hex(),
            "asserts": len(dev.m.asserts),
        }


def differ(a, b, settled=True):
    sa, sb = a.state(), b.state()
    if not settled:
        for s in (sa, sb):
            s["leds"] = {k: v > 0 for k, v in s["leds"].items()} | {k: v for k, v in s["leds"].items() if k not in FADING}
    return [k for k in sa if sa[k] != sb[k]], sa, sb


def show(k, x, y):
    """What differs in one field of the state, short."""
    if k == "pattern":
        return [(hex(i - 4), x[i], y[i]) for i in range(len(x)) if x[i] != y[i]][:8]
    if k == "leds":
        return [(i, x.get(i), y.get(i)) for i in sorted(set(x) | set(y)) if x.get(i) != y.get(i)]
    return (x, y)


def agree(a, b, settled=True):
    """-> the fields that never matched while both worlds ran on for up to RETRIES samples, 50 ms apart. The screen also counts
    as the same when both worlds showed the same pictures over the samples: a blinking text keeps its own phase per world, the
    plugin's world spends more device time per loop, so the two can blink in opposite phase and never match in one sample."""
    keys, sa, sb = differ(a, b, settled)
    first = (sa, sb)
    left = set(keys)
    screens = ({sa["screen"]}, {sb["screen"]})
    for _ in range(RETRIES):
        if not left or left == {"screen"} and screens[0] == screens[1] and len(screens[0]) > 1:
            break
        for w in (a, b):
            w.dev.run(0.05)
        keys, sa, sb = differ(a, b, settled)
        left &= set(keys)
        screens[0].add(sa["screen"])
        screens[1].add(sb["screen"])
    if "screen" in left and screens[0] == screens[1] and len(screens[0]) > 1:
        left.discard("screen")
    return [k for k in first[0] if k in left], first[0], first[1]


def twin(name, a, b, panel, plugin, extra=lambda sa, sb: (True, "")):
    """Step lists run side by side; after each step both worlds must agree. The plugin's call lands a frame after the panel's
    message, so between the steps an encoder LED may be one fade step apart and a blinking text a frame off; at the end, once
    fades are over, everything has to be the same. -> one entry."""
    before = a.state()
    for n, (step_panel, step_plugin) in enumerate(zip(panel, plugin)):
        step_panel(a)
        step_plugin(b)
        keys, sa, sb = agree(a, b, settled=False)
        if keys:
            return entry(name, False, f"step {n}: {dict((k, show(k, sa[k], sb[k])) for k in keys)}")
    for w in (a, b):
        w.dev.run(SETTLE)
    keys, sa, sb = agree(a, b)
    if keys:
        return entry(name, False, f"settled: {dict((k, show(k, sa[k], sb[k])) for k in keys)}")
    ok, more = extra(sa, sb)
    moved = [k for k in sa if sa[k] != before[k]]
    return entry(name, ok and not sa["asserts"], f"same after {len(panel)} steps, changed {moved}{more}")


def key(k, down):
    return [0, k, 1 if down else 0, 0, 0]


def P(*msgs, wait=0.15):
    return lambda w: w.send(list(msgs), wait)


def C(op, p=0, d=0, y=0, wait=0.15):
    return lambda w: w.call(op, p, d, y, wait)


def tap(k):
    """A key tapped through the panel, the same in both worlds."""
    return lambda w: (w.send([key(k, 1)], 0.08), w.send([key(k, 0)], 0.2))


def pad_cases(a, b):
    out = []
    for name, mode in (("trigger", TRIGGER), ("sequencer", SEQUENCER), ("keyboard", KEYBOARD), ("chord", CHORD)):
        for w in (a, b):
            tap(mode)(w)
        out.append(twin(f"pad_{name}", a, b,
                        [P([4, 3, 0, 100, 1], wait=0.12), P([4, 3, 0, 0, 0], wait=0.2), P([4, 9, 0, 40, 1], wait=0.12), P([4, 9, 0, 0, 0], wait=0.2)],
                        [C("padDown", 3, 100, wait=0.12), C("padUp", 3, wait=0.2), C("padDown", 9, 40, wait=0.12), C("padUp", 9, wait=0.2)]))
    for w in (a, b):
        tap(TRIGGER)(w)
    # PART MUTE held: the pad mode shows the mutes while the key is down, the pad toggles the part's mute
    held = []
    out.append(twin("part_mute_held_with_pad", a, b,
                    [P(key(PART_MUTE, 1), wait=0.6), P([4, 2, 0, 100, 1], wait=0.12), P([4, 2, 0, 0, 0], wait=0.12), P(key(PART_MUTE, 0), wait=0.3)],
                    [lambda w: (C("keyDown", PART_MUTE, wait=0.6)(w), held.append(w.state()["pad_mode"])),
                     C("padDown", 2, 100, wait=0.12), C("padUp", 2, wait=0.12), C("keyUp", PART_MUTE, wait=0.3)],
                    lambda sa, sb: (held == [0], f", pad mode while held {held}")))
    events = b.vars()["pads"]
    out.append(entry("plugin_pads_are_no_pad_event", events == 0, f"pad events the plugin got from its own pads: {events}"))
    return out


def pad_hold_cases(a, b):
    """korg.padHold in the plugin's world: the panel's pad stays with the plugin, the plugin's own pad reaches the firmware."""
    b.call("padHold")
    before = b.state()
    pads = b.vars()["pads"]
    b.send([[4, 5, 0, 100, 1]], 0.12)
    b.send([[4, 5, 0, 0, 0]], 0.2)
    held = b.state()
    got = b.vars()["pads"] - pads
    out = [entry("pad_hold_keeps_the_panel_pad", held == before and got == 2,
                 f"firmware state unchanged {held == before}, pad events {got}")]
    out.append(twin("pad_down_passes_pad_hold", a, b,
                    [P([4, 5, 0, 100, 1], wait=0.12), P([4, 5, 0, 0, 0], wait=0.2)],
                    [C("padDown", 5, 100, wait=0.12), C("padUp", 5, wait=0.2)]))
    b.call("padFree")
    return out


def encoder_cases(a, b):
    out = []
    for i in range(5):
        out.append(twin(f"encoder_{i}", a, b,
                        [P([1, i, 0, 1, 0], wait=0.3), P([1, i, 0, 0xFE, 0], wait=0.3), P([1, i, 0, 1, 0], wait=0.3)],
                        [C("encoder", i, 1, wait=0.3), C("encoder", i, -2, wait=0.3), C("encoder", i, 1, wait=0.3)]))
    for i in (0, 2):
        out.append(twin(f"shift_encoder_{i}", a, b,
                        [P(key(SHIFT, 1), wait=0.1), P([1, i, 0, 1, 0], wait=0.3), P(key(SHIFT, 0), wait=0.3)],
                        [C("keyDown", SHIFT, wait=0.1), C("encoder", i, 1, wait=0.3), C("keyUp", SHIFT, wait=0.3)]))
    return out


def touch_cases(a, b, build):
    """The finger in Master FX mode, then SHIFT + TOUCH SCALE and the finger in Touch Scale mode; the X the firmware made of it
    from the hooks of plugin_api15_cases."""
    seen = {id(a): [], id(b): []}
    for w in (a, b):
        uc = w.dev.m.uc
        log = seen[id(w)]
        uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_, log=log, w=w: log.append(("mfx", w.dev.u32(uc.reg_read(UC_ARM_REG_R0) + 0x1C))),
                    begin=api15.MFX_TOUCH[build], end=api15.MFX_TOUCH[build])
        uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_, log=log: log.append(("scale", uc.reg_read(UC_ARM_REG_R1))),
                    begin=api15.SCALE_MODE[build], end=api15.SCALE_MODE[build])
        uc.ctl_flush_tb()
    finger_panel = [P(key(TOUCH, 1), [5, 1, 0x90, 1, 0xF4]), P([5, 2, 0x58, 1, 0x2C]), P(key(TOUCH, 0), wait=0.3)]
    finger_plugin = [C("touch", 100, y=125), C("touch", 150, y=75), C("lift", wait=0.3)]
    out = []
    for name, setup_panel, setup_plugin in (
            ("master_fx", [], []),
            ("touch_scale", [P(key(SHIFT, 1), wait=0.1), P(key(TOUCH_SCALE, 1), wait=0.1), P(key(TOUCH_SCALE, 0), wait=0.1), P(key(SHIFT, 0), wait=0.3)],
             [C("keyDown", SHIFT, wait=0.1), C("keyDown", TOUCH_SCALE, wait=0.1), C("keyUp", TOUCH_SCALE, wait=0.1), C("keyUp", SHIFT, wait=0.3)])):
        if setup_panel:
            out.append(twin("shift_touch_scale", a, b, setup_panel, setup_plugin))
        for log in seen.values():
            log.clear()
        out.append(twin(f"touch_{name}", a, b, finger_panel, finger_plugin,
                        lambda sa, sb: (seen[id(a)] == seen[id(b)] and len(seen[id(a)]) > 0,
                                        f", firmware X panel {sorted(set(seen[id(a)]))} plugin {sorted(set(seen[id(b)]))}")))
    touches = b.vars()["touches"]
    out.append(entry("plugin_touch_is_no_touch_event", touches == 0, f"touch events the plugin got from its own finger: {touches}"))
    return out


def key_cases(a, b):
    out = []
    presses = b.vars()["presses"]
    out.append(twin("key_down_up_play_stop", a, b,
                    [P(key(PLAY, 1)), P(key(PLAY, 0), wait=0.3), P(key(STOP, 1)), P(key(STOP, 0), wait=0.3)],
                    [C("keyDown", PLAY), C("keyUp", PLAY, wait=0.3), C("keyDown", STOP), C("keyUp", STOP, wait=0.3)]))
    out.append(twin("exit_leaves_the_menu", a, b,
                    [tap(MENU), P(key(EXIT, 1)), P(key(EXIT, 0), wait=0.3), tap(MENU), tap(EXIT)],
                    [tap(MENU), C("keyDown", EXIT), C("keyUp", EXIT, wait=0.3), tap(MENU), C("pressKey", EXIT, wait=0.28)]))
    got = b.vars()["presses"] - presses
    out.append(entry("plugin_keys_are_no_button_event", got == 2, f"buttonPress events in the plugin's world: {got} (the two MENU taps)"))

    # SHIFT down, then the plugin stops on a fault: the frame's end lets SHIFT go for it
    b.call("keyDown", SHIFT)
    b.seen.clear()
    b.call("fault", wait=0.3)
    state = b.dev.u32(b.at + 12)
    ups = [m.hex() for m in b.seen if m[0] == 0 and m[1] == SHIFT]
    out.append(entry("stopped_plugin_lets_go", state == 3 and [(m[2], m[7]) for m in b.seen if m[0] == 0 and m[1] == SHIFT] == [(0, 0xB7)]
                     and b.dev.read(script_hooks.SIM_INPUT, 12)[:8] == b"\xff" * 8, f"script state {state}, SHIFT messages {ups}"))
    return out


def knob_cases(a, b):
    """korg.knob (the firmware's knob function, API 13) against the knob's own message `02 i 00 v`."""
    return [twin(f"knob_{name}", a, b, [P([2, i, 0, 77, 0], wait=0.3), P([2, i, 0, 200, 0], wait=0.3)],
                 [C("knob", i, y=77, wait=0.3), C("knob", i, y=200, wait=0.3)]) for name, i in KNOBS.items()]


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    build = identify(payload).build
    request = edit.compiled({"api25": PROGRAM})
    built = script_hooks.build(request["include"], build=build)
    programs = request["programs"]
    pair = lambda: (World(vsb, flash, built, programs), World(vsb, flash, built, programs))  # noqa: E731
    out = []
    out += pad_cases(*pair())
    out += pad_hold_cases(*pair())
    out += encoder_cases(*pair())
    out += touch_cases(*pair(), build)
    out += key_cases(*pair())
    out += knob_cases(*pair())
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
