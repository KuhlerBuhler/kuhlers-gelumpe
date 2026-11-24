"""Emulator cases of IDLE POWER SAVE (CUSTOMIZATION > POWER SAVE > IDLE SAVE, tools/patch/script_idle.s): with no touch for 2,
3 and 4 minutes the light and the LEDs keep 75, 50 and 25 percent, after 5 minutes they are dark. The time is set ahead in RAM
(the tick of the last touch), not run. PLAY and recording keep the device awake, on mains power and on battery, pause does not.
The first touch while dimmed wakes the device and the firmware never sees it: press and release of a key or a pad, the encoder,
the touchpad until it is let go. A press that reached the firmware before goes on reaching it past stage 1. A knob wakes and
goes to the firmware (its parameter changes), ADC noise does neither wake nor count. A MIDI note or CC keeps the device awake,
the clock does not, korg.system.keepAwake(), a remote key and the power key wake it. A plugin's light and LEDs are held and
come back, a stopped plugin's light does not. The test mode goes first, Korg's power save and idle together are never brighter
than the darker one, also with another LED DIMMING and with SAVE LIGHT set. The page switches it, WRITE keeps OFF as bit 1 of byte 7
(version 4), ON (the default) writes version 3. With EXIT held at power-on nothing of it runs.

    python3 tools/emu/idle_save_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

Measured in docs/messungen/2026-11-14-energie-befunde.md ("Idle Power Save").
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases as mc  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
import testmode_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402
from sdcard import SDCard, MemoryMedium  # noqa: E402
import lifetime  # noqa: E402

IDLE = script_hooks.IDLE
IS_STAGE, IS_KEEP = IDLE + 4, IDLE + 5
TICKS = 0xC06A292C                       # the OS tick, 1 ms (script_hw.s:OS_TICKS)
TRANSPORT = 0xC06BC318                   # 0 stop, 1 play, 2 pause, 3 REC armed, 4 recording (script_hw.s:HW_TRANSPORT)
PATTERN_PTR = 0xC033E6A4                 # the pattern object, its block at +4; part 1's LEVEL at block + 0x800 + 24 (live_write_cases)
LEVEL = 4 + 0x800 + 24
PARTS = 0x4274                           # the pattern object with all 16 parts and the copy behind (live_write_cases.OBJECT)
MX_SAVE = mc.STATE - 0x1F                # SAVE LIGHT 0 to 15 (script_menu.s:MX_SAVE)
PC_IDLE = 0xC018BF8C                     # the patch pad-colors' S_IDLE byte (script_idle.s:PC_IDLE)
FIRMWARE_INPUT = 0xC0028380              # where a panel message the input hook lets through goes on (script_hooks.s:input_pass)
POWER_CONNECT = mc.POWER_CONNECT         # the firmware's switch of power save: 1 dims light and LEDs, 0 back
METER = range(0x4C, 0x58)                # the bottom LEDs follow the meter, left out of the LED checks
WRITE_LED = 0x0B                         # breathes (period ~1.2 s) while the pattern is unsaved; two looks 0.5 s apart can match
KEEPS = (100, 75, 50, 25, 0)
AGES = (0, 121_000, 181_000, 241_000, 301_000)   # ms since the last touch: stage 0 to 4
LIGHT = (1.0, 12 / 16, 8 / 16, 4 / 16, 0.0)      # white at INTENSITY 15 scaled by the stage, rounded up
EXIT, PLAY, STOP, TOUCHPAD = 0x0D, 0x02, 0x01, 34
PLUGIN_LED = 0x30                        # a pad LED the main screen leaves alone (0x50 is the meter's)
PROGRAMS = {"idlekeep": f"""korg.onEvent("ready", () => {{ korg.backlight(0, 1, 0); korg.led({PLUGIN_LED}, 200); }});
korg.onEvent("midiIn", (s, a, b) => {{ if ((s & 0xF0) == 0xC0) korg.system.keepAwake(); }});"""}
PWM_COST = 0.1                           # percentage points the light's PWM may cost while dimmed (measured 0.02 on all three builds)
SWALLOW_WAIT = 0.3                       # s a swallowed message is given; an awake one reaches the firmware within 0.05 s
NS = 5                                   # ns an instruction (arm_load's model)


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"idle_save:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to its main screen, the backlight pins watched and every panel message the firmware gets logged."""

    def __init__(self, payload, flash, held=0, adapter=True, card=None):
        self.payload = payload
        self.build = identify(payload).build
        self.wait = 10.0 if self.build == "synth" else 2.0
        if card is None:
            self.dev = mc.boot(payload, flash, held=held, files=mc.CARD_FOLDER, adapter=adapter, seconds=self.wait, idle=True)
        else:
            self.dev = Dev(payload, flash, held)
            self.dev.m.adapter = adapter
            self.dev.m.insert_card(SDCard(MemoryMedium(bytearray(card))))
            self.dev.run(self.wait)
        dev = self.dev
        mc.watch_pins(dev)
        self.got = []

        def seen(u, at, size, _):
            r0 = u.reg_read(dev.m.A.UC_ARM_REG_R0)
            self.got.append(tuple(u.mem_read(r0 + 0x0C, 5)))
        dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, seen, begin=dev.a(FIRMWARE_INPUT), end=dev.a(FIRMWARE_INPUT))
        dev.m.uc.ctl_flush_tb()
        dev.run(0.5)

    def stage(self):
        return self.dev.read(IS_STAGE, 1)[0], self.dev.read(IS_KEEP, 1)[0]

    def age(self, ms, wait=0.2):
        """The last touch `ms` ago, then `wait` s for the next frames."""
        now = self.dev.u32(self.dev.a(TICKS))
        self.dev.m.uc.mem_write(IDLE, struct.pack("<I", (now - ms) & 0xFFFFFFFF))
        self.dev.run(wait)

    def light(self, seconds=0.3):
        return mc.duty(self.dev, seconds)[0]

    def leds(self):
        return {led: v for led, v in self.dev.m.leds.items() if led not in METER}

    def steady(self):
        """The lit LEDs that hold their brightness over 0.5 s (some blink with the tempo)."""
        first = self.leds()
        self.dev.run(0.5)
        return {led: v for led, v in self.leds().items() if v and first.get(led) == v and led != WRITE_LED}

    def send(self, msg, wait=0.05):
        """A panel message -> the messages of its kind the firmware got."""
        self.got.clear()
        self.dev.m.send(list(msg))
        self.dev.run(wait)
        return [g for g in self.got if g[0] == msg[0]]

    def load(self, seconds=1.0):
        """The ARM's load in percent over `seconds`, arm_load's model: instructions times 5 ns over device time."""
        count = [0]

        def block(u, at, size, _):
            count[0] += size // 4
        h = self.dev.m.uc.hook_add(unicorn.UC_HOOK_BLOCK, block)
        self.dev.m.uc.ctl_flush_tb()
        t0 = self.dev.m.time_ns
        self.dev.run(seconds)
        self.dev.m.uc.hook_del(h)
        return count[0] * NS / (self.dev.m.time_ns - t0) * 100


def near(got, want, tol=0.02):
    return all(abs(got[k] - want) <= tol for k in "RGB")


def scaled(v, keep):
    return (v * keep + 99) // 100


def step_cases(r):
    """Each stage: its percent, the light and the LEDs."""
    out = []
    lit = r.steady()
    seen = []
    ok = bool(lit)
    for stage, (ms, keep, light) in enumerate(zip(AGES, KEEPS, LIGHT)):
        r.age(ms, wait=0.4)
        now, duty, leds = r.stage(), r.light(), r.leds()
        want = {led: scaled(v, keep) for led, v in lit.items()}
        got = {led: leds.get(led, 0) for led in lit}
        meter = {led: v for led, v in r.dev.m.leds.items() if led in METER and v}
        good = now == (stage, keep) and near(duty, light) and got == want and (stage < 4 or not meter)
        ok = ok and good
        seen.append((stage, now, duty, None if got == want else {k: (got[k], want[k]) for k in got if got[k] != want[k]},
                     meter if stage == 4 else None))
    r.age(0, wait=0.4)
    back = r.stage(), r.light(), {led: r.leds().get(led, 0) for led in lit} == lit
    out.append(entry("each_stage", ok and back[0] == (0, 100) and near(back[1], 1.0) and back[2] and not r.dev.m.asserts,
                     f"build {r.build}: (stage, (stage, kept), light, LEDs off from want, meter LEDs lit when dark) {seen}, back {back}, lit {len(lit)} LEDs"))
    return out


def wake_cases(r):
    """The touch that wakes is swallowed whole: key, pad, touchpad, encoder; the next one goes through. Each swallowed message
    gets SWALLOW_WAIT, six times what an awake one needs, so an empty list is not just a message still on its way."""
    out = []
    W = SWALLOW_WAIT

    def asleep(stage_ms=301_000):
        r.age(stage_ms, wait=0.3)
        return r.stage()[0]

    # key: press and release swallowed, light back; the next press goes through
    s = asleep()
    down, up = r.send([0, EXIT, 1, 0, 0], wait=W), r.send([0, EXIT, 0, 0, 0], wait=W)
    woke = r.stage(), r.light()
    again = r.send([0, EXIT, 1, 0, 0]) + r.send([0, EXIT, 0, 0, 0])
    out.append(entry("wake_key_swallowed", s == 4 and down == [] and up == [] and woke[0] == (0, 100) and near(woke[1], 1.0)
                     and [g[2] for g in again] == [1, 0] and not r.dev.m.asserts,
                     f"build {r.build}: dark {s}, firmware got press {down} release {up}, then {woke}, next key {again}"))
    # pad: press, pressure and release swallowed (stage 1 counts as dimmed too)
    s = asleep(121_000)
    pad = r.send([4, 3, 0, 100, 1], wait=W) + r.send([4, 3, 0, 60, 1], wait=W) + r.send([4, 3, 0, 0, 0], wait=W)
    after = r.stage()[0]
    again = r.send([4, 3, 0, 100, 1]) + r.send([4, 3, 0, 0, 0])
    out.append(entry("wake_pad_swallowed", s == 1 and pad == [] and after == 0 and [g[4] for g in again] == [1, 0]
                     and not r.dev.m.asserts, f"build {r.build}: stage {s}, firmware got {pad}, then stage {after}, next pad {again}"))
    # touchpad: the key and every position until it is let go
    s = asleep()
    touch = (r.send([0, TOUCHPAD, 1, 0, 0], wait=W) + r.send([5, 3, 0x20, 1, 0x90], wait=W) + r.send([5, 3, 0x40, 1, 0x80], wait=W)
             + r.send([0, TOUCHPAD, 0, 0, 0], wait=W))
    after = r.stage()[0]
    again = r.send([0, TOUCHPAD, 1, 0, 0]) + r.send([5, 3, 0x20, 1, 0x90]) + r.send([0, TOUCHPAD, 0, 0, 0])
    out.append(entry("wake_touchpad_swallowed", s == 4 and touch == [] and after == 0 and len(again) == 3 and not r.dev.m.asserts,
                     f"build {r.build}: dark {s}, firmware got {touch}, then stage {after}, next touch {again}"))
    # a pad pressed while awake and held past stage 1: its pressure and release still reach the firmware
    r.age(0, wait=0.2)
    press = r.send([4, 5, 0, 100, 1])
    s = asleep(121_000)
    held = r.send([4, 5, 0, 70, 1]) + r.send([4, 5, 0, 0, 0])
    out.append(entry("pad_held_past_stage_1_passes", [g[4] for g in press] == [1] and s == 1 and [g[4] for g in held] == [1, 0]
                     and r.stage()[0] == 0 and not r.dev.m.asserts,
                     f"build {r.build}: press {press}, stage {s}, then pressure and release {held}, stage {r.stage()[0]}"))
    # the same for the touchpad: its positions and its release
    r.age(0, wait=0.2)
    press = r.send([0, TOUCHPAD, 1, 0, 0])
    s = asleep(121_000)
    held = r.send([5, 3, 0x30, 1, 0x70]) + r.send([0, TOUCHPAD, 0, 0, 0])
    out.append(entry("touch_held_past_stage_1_passes", len(press) == 1 and s == 1 and len(held) == 2 and held[-1][2] == 0
                     and r.stage()[0] == 0 and not r.dev.m.asserts,
                     f"build {r.build}: touch {press}, stage {s}, then position and release {held}, stage {r.stage()[0]}"))
    # knob: never seen before (FF), a turn while dark wakes AND goes to the firmware: the LEVEL of the selected part changes
    # (the pads above selected another part, so the whole pattern object is compared)
    obj = r.dev.u32(PATTERN_PTR)
    level = r.dev.read(obj + LEVEL, 1)[0]
    before = r.dev.read(obj, PARTS)
    first, raw = max(0, 2 * level - 10), min(254, 2 * level + 30)   # a turn across the value: changes it in every KNOB MODE
    s = asleep()
    knob = r.send([2, 0, 0, first, 0], wait=0.4)
    woke = r.stage(), r.light()
    knob += r.send([2, 0, 0, raw, 0], wait=0.4)
    after = r.dev.read(obj, PARTS)
    moved = [hex(i - 4) for i in range(PARTS) if before[i] != after[i]]
    # ADC noise of 1 while dimmed goes to the firmware but does not wake
    s2 = asleep(181_000)
    noise = r.send([2, 0, 0, raw + 1, 0], wait=0.3)
    still = r.stage()[0]
    out.append(entry("knob_wakes_and_passes", s == 4 and [g[3] for g in knob] == [first, raw] and woke[0] == (0, 100) and near(woke[1], 1.0)
                     and moved and s2 == 2 and [g[3] for g in noise] == [raw + 1] and still == 2 and not r.dev.m.asserts,
                     f"build {r.build}: dark {s}, firmware got {knob}, then {woke}, changed in the pattern {moved[:4]}; "
                     f"noise at stage {s2} went on as {noise}, stage {still}"))
    # encoder
    s = asleep()
    turn = r.send([1, 0, 0, 1, 0], wait=W)
    after = r.stage()[0]
    nxt = r.send([1, 0, 0, 1, 0])
    out.append(entry("wake_encoder_swallowed", s == 4 and turn == [] and after == 0 and len(nxt) == 1 and not r.dev.m.asserts,
                     f"build {r.build}: dark {s}, firmware got {turn}, then stage {after}, next turn {nxt}"))
    # a remote key (korg.pressKey's way in) wakes and reaches the firmware
    s = asleep()
    r.got.clear()
    testmode_cases.Remote(r.dev, r.payload).send(testmode_cases.KEY, EXIT, wait=0.4)
    remote = [g for g in r.got if g[0] == 0 and g[1] == EXIT]
    out.append(entry("remote_key_wakes", s == 4 and remote and r.stage()[0] == 0 and not r.dev.m.asserts,
                     f"build {r.build}: remote EXIT at stage {s} -> {r.stage()[0]}, firmware got {remote}"))
    r.age(0, wait=0.3)
    return out


def midi_cases(r):
    """A note and a CC keep the device awake and wake it, the clock does not."""
    seen = {}
    for name, msg in (("note", [0x90, 60, 100, 0x80, 60, 0]), ("clock", [0xF8] * 24), ("cc", [0xB0, 7, 100])):
        r.age(181_000, wait=0.3)
        before = r.stage()[0]
        r.dev.m.midi(msg)
        r.dev.run(0.3)
        seen[name] = (before, r.stage()[0])
    return [entry("midi_note_cc_wake_clock_not", seen == {"note": (2, 0), "clock": (2, 2), "cc": (2, 0)} and not r.dev.m.asserts,
                  f"build {r.build}: (stage before, after) {seen}")]


def play_cases(r):
    """PLAY keeps the device awake past 5 minutes; pause (transport 2) and STOP do not."""
    r.age(0)
    r.dev.press(PLAY, wait=0.3)
    running = r.dev.u32(r.dev.a(TRANSPORT))
    r.age(301_000, wait=0.4)
    playing = r.stage()[0]
    r.age(0, wait=0.2)
    r.dev.press(PLAY, wait=0.3)                                      # PLAY while playing pauses
    pause = r.dev.u32(r.dev.a(TRANSPORT))
    r.age(181_000, wait=0.4)
    paused = r.stage()[0]
    r.age(0, wait=0.2)
    r.dev.press(STOP, wait=0.5)
    r.age(301_000, wait=0.4)
    stopped = r.stage()[0]
    r.age(0, wait=0.3)
    return [entry("play_keeps_awake_pause_not", running == 1 and playing == 0 and pause == 2 and paused == 2 and stopped == 4 and not r.dev.m.asserts,
                  f"build {r.build}: transport {running:#x}, 5 minutes on while playing stage {playing}, 3 minutes on paused (transport {pause}) {paused}, "
                  f"after STOP {stopped}")]


def testmode_cases_(r):
    """The test mode goes first: no stage while it runs, the device awake and lit after it."""
    remote = testmode_cases.Remote(r.dev, r.payload)
    r.age(181_000, wait=0.3)
    dimmed = r.stage()[0]
    remote.test(True)
    r.age(301_000, wait=0.4)
    during = r.stage()[0]
    remote.test(False)
    r.dev.run(0.4)
    after = r.stage()[0], r.light()
    return [entry("testmode_before_idle", dimmed == 2 and during == 0 and after[0] == 0 and near(after[1], 1.0) and not r.dev.m.asserts,
                  f"build {r.build}: stage before {dimmed}, in the test mode 5 minutes on {during}, after it {after}")]


def korg_together(r, lit):
    """Korg's power save on, then stage 1, 3 and 4, then awake again with Korg's dim still on -> (ok, seen)."""
    r.dev.call(POWER_CONNECT, 1)
    r.dev.run(0.4)
    korg = r.light(), {led: r.leds().get(led, 0) for led in lit}
    seen, ok = [("korg", korg)], bool(lit)
    for stage in (1, 3, 4):
        r.age(AGES[stage], wait=0.4)
        light, leds = r.light(), {led: r.leds().get(led, 0) for led in lit}
        if stage < 4:
            good = all(light[k] <= korg[0][k] + 0.02 for k in "RGB") and all(leds[k] <= korg[1][k] for k in lit) \
                and all(leds[k] <= scaled(lit[k], KEEPS[stage]) for k in lit)
        else:
            good = max(light.values()) == 0 and not any(leds.values())
        ok = ok and good
        seen.append((stage, light, {k: (lit[k], korg[1][k], leds[k]) for k in lit}, good))
    r.age(0, wait=0.4)
    woke = r.light(), {led: r.leds().get(led, 0) for led in lit}
    good = all(abs(woke[0][k] - korg[0][k]) <= 0.02 for k in "RGB") and woke[1] == korg[1]
    ok = ok and good
    seen.append(("woke, Korg's dim on", woke, good))
    r.dev.call(POWER_CONNECT, 0)
    r.dev.run(0.4)
    return ok, seen, korg


def korg_save_cases(r):
    """Korg's power save and idle together: never brighter than the darker. The firmware's dim stays while idle only dims,
    the LEDs keep the smaller share, dark is dark, waking goes back to Korg's dim. Again with another LED DIMMING step and
    with SAVE LIGHT 15 (idle scales the power save light)."""
    out = []
    r.age(0, wait=0.3)
    lit = r.steady()
    ok, seen, korg = korg_together(r, lit)
    back = r.light()
    out.append(entry("korg_power_save_plus_idle", ok and max(korg[0].values()) < 0.1 and near(back, 1.0) and not r.dev.m.asserts,
                     f"build {r.build}: {seen}, both off {back}"))
    # LED DIMMING one step down from 75 percent
    mc.goto_group(r.dev, mc.GROUP_PSAVE, 1)
    r.dev.turn(-1, wait=0.4)
    step = mc.texts_of(r.dev)[1]
    script_cases.leave_menu(r.dev)
    r.age(0, wait=0.4)
    lit2 = r.steady()
    ok2, seen2, korg2 = korg_together(r, lit2)
    out.append(entry("korg_power_save_plus_idle_led_dimming_step", step != "75%" and ok2 and korg2[1] != korg[1] and not r.dev.m.asserts,
                     f"build {r.build}: LED DIMMING {step}, {seen2}"))
    # SAVE LIGHT 8: the power save light is white at a part of INTENSITY 15, idle scales it down from there
    r.dev.m.uc.mem_write(MX_SAVE, bytes([8]))
    r.dev.call(POWER_CONNECT, 1)
    r.age(AGES[1], wait=0.4)                                         # a stage change applies the look with the new SAVE LIGHT
    r.age(0, wait=0.4)
    seen3 = [("korg", r.light())]
    for stage in (1, 2, 3):
        r.age(AGES[stage], wait=0.4)
        seen3.append((stage, r.light()))
    r.dev.call(POWER_CONNECT, 0)
    r.age(0, wait=0.4)
    r.dev.m.uc.mem_write(MX_SAVE, bytes([0]))
    r.age(AGES[1], wait=0.4)
    r.age(0, wait=0.4)
    seen3.append(("back", r.light()))
    w = [x[1]["G"] for x in seen3[:4]]
    good = 0.1 < w[0] < 0.95 and w[0] > w[1] > w[2] > w[3] > 0 and near(seen3[4][1], 1.0)
    out.append(entry("save_light_scaled_by_idle", good and not r.dev.m.asserts, f"build {r.build}: (stage, light) {seen3}"))
    return out


def pwm_cases(r):
    """What the light's PWM costs while dimmed: the ARM's load awake (white is a plain pin) and in stages 1 to 3 (white by PWM)."""
    r.age(0, wait=0.3)
    awake = r.load()
    dimmed = []
    for stage in (1, 2, 3):
        r.age(AGES[stage], wait=0.3)
        dimmed.append(r.load())
    r.age(0, wait=0.3)
    cost = max(dimmed) - awake
    return [entry("pwm_cost", cost <= PWM_COST and not r.dev.m.asserts,
                  f"build {r.build}: load awake {awake:.2f} %, in stages 1 to 3 {[round(d, 2) for d in dimmed]} %, the PWM costs "
                  f"{cost:.2f} points at most (limit {PWM_COST})")]


def battery_cases(payload, flash):
    """On battery the stages run as on mains power, PLAY keeps the device awake there too."""
    r = Run(payload, flash, adapter=False)
    r.age(AGES[2], wait=0.4)
    dimmed = r.stage()
    r.age(0, wait=0.3)
    r.dev.press(PLAY, wait=0.3)
    r.age(AGES[4], wait=0.4)
    playing = r.stage()[0]
    r.dev.press(STOP, wait=0.5)
    return [entry("battery_stages_and_play", dimmed == (2, 50) and playing == 0 and not r.dev.m.asserts,
                  f"build {r.build}: on battery 3 minutes on {dimmed}, 5 minutes on while playing stage {playing}")]


def power_key_cases(payload, flash):
    """The power key is a touch: it wakes and goes to the firmware (which then switches off, so a device of its own)."""
    r = Run(payload, flash)
    r.age(AGES[4], wait=0.4)
    dark = r.stage()[0]
    got = r.send([6, 1, 0, 0, 0], wait=0.1)
    return [entry("power_key_wakes", dark == 4 and r.stage()[0] == 0 and len(got) == 1 and not r.dev.m.asserts,
                  f"build {r.build}: dark {dark}, power key -> stage {r.stage()[0]}, firmware got {got}")]


def kill_cases(payload, flash):
    """EXIT held at power-on: nothing counts, the light stays as Korg's."""
    r = Run(payload, flash, held=mc.KILL)
    before = r.dev.read(IDLE, 8)
    lit = r.steady()
    r.age(301_000, wait=0.5)
    got = r.send([0, EXIT, 1, 0, 0]) + r.send([0, EXIT, 0, 0, 0])
    leds = {led: r.leds().get(led, 0) for led in lit}
    pc = r.dev.read(PC_IDLE, 1)[0]
    return [entry("exit_at_power_on_nothing", r.stage()[0] == 0xFF and near(r.light(), 1.0) and len(got) == 2 and leds == lit
                  and pc == 0xFF and not r.dev.m.asserts,
                  f"build {r.build}: EXIT held, idle area {before.hex()}, 5 minutes on stage {r.stage()}, light {r.light()}, keys {got}, "
                  f"LEDs kept {leds == lit}, PC_IDLE {pc:#x}")]


def plugin_cases(payload, flash):
    """A plugin's light and LED are held while dimmed and dark and come back on waking; keepAwake wakes."""
    r = Run(payload, flash)
    request = edit.compiled(PROGRAMS)
    built = script_hooks.build(request["include"], build=r.build)
    script_cases.install(r.dev, built, request["programs"], ["idlekeep"])
    r.dev.run(0.6)
    own = r.light(), r.dev.m.leds.get(PLUGIN_LED)
    r.age(AGES[2], wait=0.4)
    dimmed = r.stage()[0], r.light(), r.dev.m.leds.get(PLUGIN_LED)
    r.age(AGES[4], wait=0.4)
    dark = r.light(), r.dev.m.leds.get(PLUGIN_LED)
    r.dev.m.midi([0xC0, 5])
    r.dev.run(0.5)
    woke = r.stage()[0], r.light(), r.dev.m.leds.get(PLUGIN_LED)
    green = {"R": 0.0, "G": 1.0, "B": 0.0}
    # the plugin stops: its light is forgotten, waking brings the BLECH look back, not the green
    entry_at = script_cases.plugin_entry(r.dev, built.layout["runtime"])
    r.dev.m.uc.mem_write(entry_at + 12, struct.pack("<I", 0))
    r.dev.run(0.3)
    forgot = r.dev.read(IDLE + 6, 1)[0]
    r.age(AGES[2], wait=0.4)
    r.age(0, wait=0.4)
    after_stop = r.light()
    out = [entry("plugin_light_and_led_held_and_back",
                 own[0] == green and own[1] and dimmed[0] == 2 and near(dimmed[1], LIGHT[2]) and dimmed[2] == scaled(own[1], 50)
                 and max(dark[0].values()) == 0 and dark[1] == 0 and woke[1:] == own and not r.dev.m.asserts,
                 f"build {r.build}: own {own}, 3 minutes on (stage, light, LED) {dimmed}, dark {dark}, after keepAwake {woke}"),
           entry("keep_awake_wakes", woke[0] == 0 and not r.dev.m.asserts,
                 f"build {r.build}: a program change calls keepAwake, stage {woke[0]}"),
           entry("stopped_plugin_light_forgotten", entry_at and forgot == 0xFF and near(after_stop, 1.0) and not r.dev.m.asserts,
                 f"build {r.build}: plugin entry {entry_at:#x} stopped, IS_BL {forgot:#x}, light after waking {after_stop}")]
    return out


def setting_cases(payload, flash):
    """The page: ON by default, OFF holds every stage away; WRITE with ON writes version 3, with OFF version 4 with bit 1 of byte
    7, which the next start reads."""
    r = Run(payload, flash)
    dev = r.dev

    def write():
        mc.goto_group(dev, mc.GROUP_FEATURES, mc.FEAT_TM)
        mc.press(dev, "write", wait=0.6)
        dev.run(3.0)
        files = [f for f in mc.settings_raw(dev.m.mmc.card.medium.data).values() if len(f) >= 24 and f[:4] == b"GSET"]
        f = max(files, key=lambda f: struct.unpack_from("<I", f, 8)[0])
        return f[4], f[7]

    default = write()
    mc.goto_group(dev, mc.GROUP_PSAVE, 2)
    page = mc.texts_of(dev)
    dev.turn(-1, wait=0.3)
    off = mc.texts_of(dev)[1], dev.read(mc.MX_FLAGS2, 1)[0]
    r.age(AGES[3], wait=0.4)
    held = r.stage()[0], r.light()
    written = write()
    back = Run(payload, flash, card=dev.m.mmc.card.medium.data)
    read = back.dev.read(mc.MX_FLAGS2, 1)[0]
    back.age(AGES[3], wait=0.4)
    still = back.stage()[0]
    mc.goto_group(back.dev, mc.GROUP_PSAVE, 2)
    back.dev.turn(1, wait=0.3)
    on = mc.texts_of(back.dev)[1]
    back.age(AGES[3], wait=0.4)
    dims = back.stage()[0]
    back.age(0, wait=0.3)
    dev = back.dev
    again = write()
    return [entry("default_on_writes_v3", page == ("IDLE SAVE", "ON", "") and default == (3, 0) and not r.dev.m.asserts,
                  f"build {r.build}: page {page}, WRITE (version, byte 7) {default}"),
            entry("off_holds_and_writes_v4", off == ("OFF", 2) and held[0] == 0 and near(held[1], 1.0) and written == (4, 2)
                  and not r.dev.m.asserts, f"build {r.build}: OFF (value, byte 7) {off}, 4 minutes on {held}, WRITE {written}"),
            entry("off_read_back_and_on_again", read == 2 and still == 0 and on == "ON" and dims == 3 and again == (3, 0)
                  and not back.dev.m.asserts,
                  f"build {r.build}: next start byte 7 {read}, 4 minutes on stage {still}, ON {on} then stage {dims}, WRITE {again}")]


def cases(payload, flash=None):
    """All idle power save cases on `payload` (the image behind the 256-byte header), as menu_cases.look_parts calls them."""
    mc.for_build(payload)
    r = Run(payload, flash)
    out = []
    for part in (pwm_cases, step_cases, wake_cases, midi_cases, play_cases, testmode_cases_, korg_save_cases):
        out += part(r)
    for part in (battery_cases, power_key_cases, kill_cases, plugin_cases, setting_cases):
        out += part(payload, flash)
    return out


def main():
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes()[0x100:], load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
