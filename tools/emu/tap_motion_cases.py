# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the TAP motion patch (tools/patch/tap_motion.py, docs/messungen/2026-10-15-tap-motion-patch.md,
docs/ideen/39-automationen-tap.md).

check.py runs `cases` on every patched copy that carries the patch's hooks. REC records knob movements and Master FX
gestures as always; TAP then switches the recorded motion of the selected part on and off at once (the mode byte of the part,
the way the Part menu sets it), MASTER FX held with TAP switches the Master FX motion, the TAP LED shows the state, and the tap
tempo is gone. With EXIT held at power-on, without a card or with the setting off the firmware is exactly as it was; the
reference for "as it was" is the same copy with EXIT held at power-on (no hook of the patch does anything then).

    tools/emu/.venv/bin/python tools/emu/tap_motion_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import synthaddr  # noqa: E402
import tap_motion as spec  # noqa: E402
from machine import load_flash  # noqa: E402
from pswitch_cases import Box, card_image  # noqa: E402
from splash_cases import Dev  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402

IMAGE = 0xC0000000
PATTERN_PTR = 0xC033E6A4
TEMPO = 0xC0691518
STEP = 0xC06904B0               # step counter of part 1
MOTION_OUT = 0xC068DB1C         # what the motion engine plays for the first lane, FFFFFFFF while silent
PAD_STATE = 0xC068D074          # the Master FX pad state the effect was last given
HW_PART, HW_PATTERN = 0xC06B2428, 0xC06B2420
FATFS = 0xC06A010C              # FatFs volume table: the card's volume, its byte 0 the mounted type (0 unmounted)
LED = 0x14
KEYS = {"rec": 0x00, "stop": 0x01, "play": 0x02, "tap": 0x03, "touch_scale": 0x05, "master_fx": 0x06, "write": 0x0E, "part_right": 0x0F, "part_left": 0x0B, "shift": 0x0A, "menu": 0x09}
KILL = spec.KILL_SWITCH
MODE, COPY, STRIDE, COPY_STRIDE = 0x807, 0x382E, 0x330, 0x24
MFX_MODE = 0x44                 # the switch of the Master FX lanes, in the pattern object
LANE_DATA = 0x134
SWEEP = [(8 * k + 16) % 250 for k in range(16)]       # knob values sent in the steps 16 to 31
SILENT = 0xFFFFFFFF
RUNTIME = 0xC01AE000
POOL = 0xC01D7000                # the plugin pool of the script runtime
RT_ARMED, RT_CAPTURE_MASK = RUNTIME + 0x60, RUNTIME + 0x94   # SCRIPT_CONTROL_ARMED and SCRIPT_CONTROL_CAPTURE_MASK of the script runtime
WINDOW = range(16, 32)


def for_build(payload):
    """Put the patch module's places to the build of this image (the synth has its own addresses, data/synth-map/)."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hooks(payload):
    """True when the key handler's hook site branches into the patch's code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.TAP_HOOK - IMAGE)[0]
    return word >> 24 == 0xEA and spec.CODE_AT <= spec.TAP_HOOK + 8 + ((word & 0xFFFFFF) << 2) < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"tapmotion:{name}", "ok": bool(ok), "detail": str(detail)}


class TBox(Box):
    """A booted device (card mounted unless asked otherwise) with the helpers of these cases. On mains power: on battery power save
    dims every LED to a quarter (pad-colors, menu_cases checks it), and these cases look at the TAP LED's own value."""

    def __init__(self, payload, flash=None, held=0, card=True, seconds=3.0):
        if synthaddr.is_synth(payload):
            # Box looks at the Sampler's pattern bank and global block (RAM places the synth does not have): do what it does without them
            self.payload = bytes(payload)
            self.dev = Dev(self.payload, flash, held, adapter=True)
            self.m = self.dev.m
            if card:
                self.m.insert_card(SDCard(MemoryMedium(card_image())))
            self.dev.run(seconds)
            self.marks = {}
        else:
            super().__init__(payload, flash, held, card, seconds, adapter=True)
        # The cases record and read steps 16 to 31, which need a pattern of four bars. The flash dump has them; an empty flash holds
        # Init patterns of one bar, where the steps stop at 15. The length (block offset 37, the bars minus one) is read at PLAY.
        length = self.pat() + 4 + 37
        if self.dev.read(length, 1)[0] < 3:
            self.m.uc.mem_write(length, bytes([3]))

    def key(self, name, wait=0.3):
        self.dev.press(KEYS[name], wait)

    def pat(self):
        return self.u32(PATTERN_PTR)

    def mode(self, part=0):
        """(mode byte, its copy) of a part."""
        p = self.pat()
        return self.dev.read(p + MODE + STRIDE * part, 1)[0], self.dev.read(p + MODE + COPY + COPY_STRIDE * part, 1)[0]

    def set_mode(self, value, part=0):
        p = self.pat()
        self.m.uc.mem_write(p + MODE + STRIDE * part, bytes([value]))
        self.m.uc.mem_write(p + MODE + COPY + COPY_STRIDE * part, bytes([value]))

    def mfx_mode(self):
        return self.dev.read(self.pat() + MFX_MODE, 1)[0]

    def set_mfx_mode(self, value):
        self.m.uc.mem_write(self.pat() + MFX_MODE, bytes([value]))

    def leds(self):
        return self.m.leds.get(LED)

    def led_packets(self, since):
        return [p.hex() for p in self.m.panel_log[since:] if len(p) >= 2 and p[0] == 0 and p[1] == LED]

    def step(self):
        return self.u32(STEP)

    def out(self, i=0):
        at = synthaddr.tr(MOTION_OUT) if self.dev.synth else MOTION_OUT
        return struct.unpack("<I", self.m.uc.mem_read(at + 4 * i, 4))[0]

    def ensure_master_fx(self):
        from mfx_cases import CTL
        control = self.dev.u32(CTL)
        mode = struct.unpack("<I", self.m.uc.mem_read(control + 0x334, 4))[0]
        if mode != 2:
            self.key("master_fx", 0.2)

    def tempo(self):
        return self.u32(TEMPO)

    def tap(self, wait=0.3):
        self.dev.press(KEYS["tap"], wait)

    def press_in_script(self, *keys):
        """Keys inside `script` (TAP when none is named): down now in that order, up 50 ms later, so the sampling goes on."""
        self.pressed = keys or ("tap",)
        for k in self.pressed:
            self.m.press(KEYS[k], True)
        self.release_at = self.m.time_ns + 50_000_000

    def hold(self, key, down):
        self.m.press(KEYS[key], down)
        self.run(0.1)

    def lane(self, i=0):
        return [b for b in self.dev.read(self.pat() + LANE_DATA + 0x40 * i, 0x40) if b]

    def record_knob(self):
        """REC, PLAY, the sweep as knob 0 in the steps 16 to 31, STOP: one lane for the selected part."""
        self.key("rec", 0.2)
        self.key("play", 0.0)
        last, t = None, 0.0
        while t < 12.0:          # to the end of step 31, whatever the tempo (3.4 s are enough at 150 BPM, an Init pattern at 120 needs 4 s)
            self.run(0.005)
            t += 0.005
            st = self.step()
            if st != last:
                last = st
                if 16 <= st < 32:
                    self.m.send([2, 0, 0, SWEEP[st - 16], 0])
                elif st >= 32:
                    break
        self.key("stop", 0.5)

    def record_gesture(self):
        """The Master FX pad touched in steps 16 to 31 and let go at 32: three lanes."""
        self.ensure_master_fx()
        self.key("rec", 0.2)
        self.key("play", 0.0)
        last, t, down = None, 0.0, False
        while t < 12.0:          # to step 32, whatever the tempo
            self.run(0.005)
            t += 0.005
            st = self.step()
            if st != last:
                last = st
                if 16 <= st < 32:
                    if not down:
                        self.m.send([0, 0x22, 1, 0, 0])
                        down = True
                    px, py = 200 + 40 * (st - 16), 300 + 30 * (st - 16)
                    self.m.send([5, px >> 8, px & 255, py >> 8, py & 255])
                elif st >= 32 and down:
                    self.m.send([0, 0x22, 0, 0, 0])
                    down = False
            if st >= 32 and not down:
                break
        self.key("stop", 0.5)

    def script(self, actions, loops=2, sample=lambda box: box.out()):
        """PLAY from the start; at the first sight of (loop, step) the action registered for it runs (a function of the box).
        Returns {(loop, step): what `sample` saw last in that step} for `loops` runs through the 64 steps."""
        self.key("play", 0.0)
        seen, loop, last = {}, 0, None
        self.release_at = None
        while True:
            self.run(0.01)
            if self.release_at is not None and self.m.time_ns >= self.release_at:
                for k in reversed(self.pressed):
                    self.m.press(KEYS[k], False)
                self.release_at = None
            st = self.step()
            if last is not None and st < last:
                loop += 1
                if loop >= loops:
                    break
            if st != last:
                last = st
                if (loop, st) in actions:
                    actions[(loop, st)](self)
            seen[(loop, st)] = sample(self)
        self.key("stop", 0.3)
        return seen


def audible(seen, loop, steps):
    return [s for s in steps if seen.get((loop, s), SILENT) != SILENT]


# ---------------------------------------------------------------------------------------- the cases
def case_toggle(payload, flash):
    """TAP switches the recorded motion of the part at once, from the next step on, no waiting for the bar."""
    out = []
    ref = TBox(payload, flash, KILL)
    box = TBox(payload, flash)
    for b in (ref, box):
        b.record_knob()
    rec_mode = box.mode()
    want = {s: SWEEP[s - 16] >> 1 for s in WINDOW}
    actions = {(0, 5): TBox.press_in_script, (0, 24): TBox.press_in_script, (1, 20): TBox.press_in_script}
    ref_seen = ref.script(actions)
    seen = box.script(actions)
    out.append(entry("reference_firmware", rec_mode == (1, 1) and ref.mode() == (1, 1) and len(audible(ref_seen, 0, WINDOW)) >= 15 and len(audible(ref_seen, 1, WINDOW)) >= 15,
                     f"EXIT held: TAP leaves the mode alone {ref.mode()} and the motion plays in both runs ({len(audible(ref_seen, 0, WINDOW))} and {len(audible(ref_seen, 1, WINDOW))} of 16 steps)"))
    first = audible(seen, 0, WINDOW)
    out.append(entry("off_before_the_window", not audible(seen, 0, range(16, 24)), f"TAP at step 5 (off): the lane is silent in the steps 16 to 23 ({audible(seen, 0, range(16, 24))})"))
    out.append(entry("on_in_the_middle_of_the_bar", first and first[0] in (25, 26) and first == list(range(first[0], 32)) and all(seen[(0, s)] == want[s] for s in first),
                     f"TAP at step 24 (on): audible from step {first[0] if first else None}, not at the next bar; the steps {first} play the recorded values"))
    second = audible(seen, 1, WINDOW)
    out.append(entry("off_in_the_middle_of_the_bar", second and second[-1] in (20, 21) and second == list(range(16, second[-1] + 1)) and all(seen[(1, s)] == want[s] for s in second),
                     f"TAP at step 20 (off): the lane plays until step {second[-1] if second else None} and is silent after it ({second})"))
    out.append(entry("no_assertion", not box.m.asserts and not ref.m.asserts, f"box {box.m.asserts} reference {ref.m.asserts}"))

    # the mode byte and its copy move together (the part setter), with no menu involved
    t = TBox(payload, flash)
    t.tap()
    off = t.mode()
    t.tap()
    on = t.mode()
    out.append(entry("byte_and_copy_follow", off == (0, 0) and on == (1, 1) and t.dev.screen()["number"] == 1, f"after TAP {off}, after TAP again {on}, screen {t.dev.screen()['number']}"))

    # no tap tempo: four taps in 0.65 s steps are the firmware's 92.3 BPM when EXIT is held, nothing with the patch
    ref2, box2 = TBox(payload, flash, KILL), TBox(payload, flash)
    tempo_before = box2.tempo()       # the tempo of the pattern at hand: 160.0 in the flash dump's first pattern, 120.0 in an Init pattern
    for b in (ref2, box2):
        for _ in range(4):
            b.tap(0.6)
        b.run(0.3)
    out.append(entry("tap_tempo_is_gone", ref2.tempo() == 923 and box2.tempo() == tempo_before and box2.mode() == (1, 1),
                     f"four taps, 0.65 s apart: the firmware sets {ref2.tempo()}, with the patch the tempo stays {box2.tempo()} and the mode went off and on twice {box2.mode()}"))
    return out


def case_memory(payload, flash):
    """Off remembers the mode, on gives it back; never on is Smooth; each part has its own byte; the LED follows the selected part."""
    out = []
    box = TBox(payload, flash)
    box.set_mode(2)
    box.tap()
    a = box.mode()
    box.tap()
    b = box.mode()
    out.append(entry("trigger_hold_comes_back", a == (0, 0) and b == (2, 2), f"Trigger Hold, TAP {a}, TAP {b}"))
    fresh = TBox(payload, flash)
    fresh.set_mode(0)
    fresh.tap()
    out.append(entry("never_on_is_smooth", fresh.mode() == (1, 1), f"mode 0 set by hand, nothing remembered, TAP {fresh.mode()}"))

    part = TBox(payload, flash)
    lit = part.leds()
    part.key("part_right", 0.3)
    p2_lit = part.leds()
    part.tap()
    modes = [part.mode(0), part.mode(1)]
    p2_dark = part.leds()
    part.key("part_left", 0.3)
    p1_lit = part.leds()
    part.key("part_right", 0.3)
    p2_back = part.leds()
    out.append(entry("only_the_selected_part", modes == [(1, 1), (0, 0)] and part.u32(HW_PART) == 1, f"part 2 selected, TAP: parts 1 and 2 {modes}"))
    out.append(entry("led_follows_the_selected_part", (lit, p2_lit, p2_dark, p1_lit, p2_back) == (255, 255, 0, 255, 0),
                     f"LED on part 1 {lit}, part 2 {p2_lit}, after TAP {p2_dark}, back on part 1 {p1_lit}, part 2 again {p2_back}"))

    led = TBox(payload, flash)
    boot_lit = led.leds()
    led.tap()
    dark = led.leds()
    led.tap()
    lit_again = led.leds()
    led.key("play", 0.0)
    packets = len(led.m.panel_log)
    led.run(2.0)
    flashing = led.led_packets(packets)
    out.append(entry("led_is_the_state", (boot_lit, dark, lit_again) == (255, 0, 255) and not flashing and not led.m.asserts,
                     f"LED after start {boot_lit}, after TAP {dark}, after TAP again {lit_again}; no beat flash while playing ({flashing})"))
    ref = TBox(payload, flash, KILL)
    ref.key("play", 0.0)
    packets = len(ref.m.panel_log)
    ref.run(2.0)
    flash_ref = set(ref.led_packets(packets))
    out.append(entry("reference_led_flashes", flash_ref == {"0014ff0000", "0014000000"}, f"EXIT held: the firmware flashes the TAP LED on every beat ({sorted(flash_ref)})"))
    return out


def _setting_off(payload, flash):
    box = TBox(payload, flash)
    box.m.uc.mem_write(spec.TM_SETTING, struct.pack("<I", 0))
    box.run(0.3)
    return box


def case_stock(payload, flash):
    """No card, the setting off, EXIT held at power-on: the tap tempo and the beat flash are the firmware's, the motion is not touched."""
    out = []
    rows = {}
    for name, make in {
        "exit_held": lambda: TBox(payload, flash, KILL),
        "no_card": lambda: TBox(payload, flash, card=False),
        "setting_off": lambda: _setting_off(payload, flash),
    }.items():
        box = make()
        for _ in range(4):
            box.tap(0.6)
        box.run(0.3)
        box.key("play", 0.0)
        packets = len(box.m.panel_log)
        box.run(2.0)
        rows[name] = (box.tempo(), box.mode(), len(set(box.led_packets(packets))), box.m.asserts)
    out.append(entry("stock_without_the_patch", all(r[:3] == (923, (1, 1), 2) and not r[3] for r in rows.values()), f"(tempo, mode, beat flash packets) after four taps: {rows}"))

    # the setting switched off while the patch has the LED: the firmware's beat flash is back
    box = TBox(payload, flash)
    on = box.leds()
    box.m.uc.mem_write(spec.TM_SETTING, struct.pack("<I", 0))
    box.run(0.3)
    box.key("play", 0.0)
    packets = len(box.m.panel_log)
    box.run(2.0)
    back = set(box.led_packets(packets))
    box.tap(0.5)
    out.append(entry("setting_off_gives_the_led_back", on == 255 and len(back) == 2 and box.mode() == (1, 1) and box.u32(spec.STATE + spec.S_LED) == 0,
                     f"lit with the patch ({on}), the setting set to 0: the beat flash is back ({sorted(back)}), TAP no longer switches ({box.mode()})"))
    return out


def case_shift_tap(payload, flash):
    """SHIFT + TAP stays the firmware's: the Pattern menu on the page BPM, the motion not touched."""
    box = TBox(payload, flash)
    box.hold("shift", True)
    box.tap(0.3)
    box.hold("shift", False)
    box.run(0.3)
    screen = box.dev.screen()
    return [entry("shift_tap_is_the_bpm_page", screen["number"] == 3 and box.mode() == (1, 1) and box.leds() == 255 and not box.m.asserts,
                  f"screen {screen}, mode {box.mode()}, LED {box.leds()}")]


def case_rec_and_pattern(payload, flash):
    """REC records with the motion off, and the lane then plays on TAP; WRITE keeps the state of the byte as it is at WRITE time, an unwritten
    state goes with the pattern change like any other edit; a pattern change forgets the mode that was remembered."""
    out = []
    box = TBox(payload, flash)
    box.tap()
    box.record_knob()
    lane = box.lane()
    off_mode = box.mode()
    silent = box.script({}, 1)
    again = box.script({(0, 5): TBox.press_in_script}, 1)
    want = {s: SWEEP[s - 16] >> 1 for s in WINDOW}
    out.append(entry("rec_with_the_motion_off", len(lane) >= 12 and off_mode == (0, 0) and not audible(silent, 0, WINDOW) and audible(again, 0, WINDOW) == list(WINDOW) and all(again[(0, s)] == want[s] for s in WINDOW),
                     f"TAP off, then REC: the lane has {len(lane)} bytes, the mode stays {off_mode}, the lane is silent ({len(audible(silent, 0, WINDOW))} steps) until TAP switches it on ({len(audible(again, 0, WINDOW))} of 16 steps, values as recorded)"))

    # WRITE saves what the byte is at that moment; the other pattern has its own state
    w = TBox(payload, flash)
    slots = w.dev.a(0xC08B2940)
    w.tap()
    w.key("write", 0.5)
    w.key("write", 0.8)
    w.run(1.0)
    saved = w.m.uc.mem_read(slots + 0x803, 1)[0]
    w.turn(1, 0.5)
    other = (w.u32(HW_PATTERN), w.mode(), w.leds())
    w.turn(-1, 0.5)
    back = (w.u32(HW_PATTERN), w.mode(), w.leds())
    out.append(entry("write_saves_the_state_at_write_time", saved == 0 and other == (1, (1, 1), 255) and back == (0, (0, 0), 0) and not w.m.asserts,
                     f"TAP off, WRITE: the stored pattern holds {saved}; the next pattern {other}; back on the written one {back}"))
    u = TBox(payload, flash)
    u.tap()
    u.turn(1, 0.5)
    browsed = u.running()             # what plays/is loaded, not the number shown
    u.key("menu", 0.5)                 # the TAP made the pattern unsaved: stopped, the wheel only browses (pattern-switch), MENU loads
    u.turn(-1, 0.5)
    out.append(entry("unwritten_state_goes_with_the_pattern_change", browsed == 0 and u.mode() == (1, 1) and u.leds() == 255,
                     f"TAP off, no WRITE, away (the wheel browses, still on {browsed}; MENU loads) and back: mode {u.mode()}, LED {u.leds()} (the pattern is loaded as it was written)"))

    # the Master FX byte is part of the pattern as well: WRITE keeps it, loading the pattern brings it back
    f = TBox(payload, flash)
    f.hold("master_fx", True)
    f.tap()
    f.hold("master_fx", False)
    off_now = f.mfx_mode()
    f.key("write", 0.5)
    f.key("write", 0.8)
    f.run(1.0)
    stored = f.m.uc.mem_read(slots + 0x40, 1)[0]
    f.turn(1, 0.5)
    other_pattern = f.mfx_mode()
    f.turn(-1, 0.5)
    out.append(entry("mfx_byte_is_saved_with_the_pattern", off_now == 0 and stored == 0 and other_pattern == 1 and f.mfx_mode() == 0 and f.mode() == (1, 1),
                     f"MASTER FX held and TAP: the byte is {off_now}; after WRITE the stored pattern holds {stored}; the next pattern has {other_pattern}; back on the written one {f.mfx_mode()}, the part's byte {f.mode()}"))

    # the mode remembered for a part belongs to the pattern: after a pattern change TAP gives Smooth, not the mode of the other pattern
    m = TBox(payload, flash)
    m.set_mode(2)
    m.tap()
    m.turn(1, 0.5)
    m.set_mode(0)
    m.tap()
    out.append(entry("pattern_change_forgets_the_remembered_mode", m.mode() == (1, 1) and m.u32(HW_PATTERN) == 1, f"Trigger Hold, TAP off on pattern 1, pattern 2 with its byte 0, TAP: {m.mode()}"))
    return out


def case_mfx(payload, flash):
    """The Master FX lanes of a gesture play with the part byte on or off; the byte at pattern + 0x44 switches them, and MASTER FX held
    with TAP writes it: at once, the pad let go when it is switched off in the middle of a gesture, the part and its byte left alone."""
    out = []
    fresh = TBox(payload, flash)
    default = fresh.mfx_mode()

    def run(mfx, part):
        b = TBox(payload, flash)
        b.record_gesture()
        b.set_mfx_mode(mfx)
        b.set_mode(part)
        return b, b.script({}, 1, sample=lambda x: (x.out(0), x.out(1)))

    rows = {}
    for label, (mfx, part) in {"both on": (1, 1), "part off": (1, 0), "mfx off": (0, 1), "mfx 2": (2, 1)}.items():
        b, seen = run(mfx, part)
        rows[label] = len({v for k, v in seen.items() if k[1] in WINDOW and v[0] != SILENT})
    out.append(entry("mfx_byte_switches_the_lanes", default == 1 and rows["both on"] >= 12 and rows["part off"] >= 12 and rows["mfx off"] == 0 and rows["mfx 2"] >= 12,
                     f"byte {default} on a new pattern; distinct X outputs in the steps 16 to 31 with {rows}"))

    # a gesture is on in the steps 16 to 31; MASTER FX held and TAP at step 20 switches it off, at step 24 of the next run it is on again
    down = lambda x: x.m.press(KEYS["master_fx"], True)
    up = lambda x: x.m.press(KEYS["master_fx"], False)
    tap = TBox.press_in_script
    base = TBox(payload, flash)
    base.record_gesture()
    plain = base.script({}, 1, sample=lambda x: (x.out(0), x.out(1)))
    box = TBox(payload, flash)
    box.record_gesture()
    seen = box.script({(0, 18): down, (0, 20): tap, (0, 23): up, (1, 22): down, (1, 24): tap, (1, 27): up}, 2,
                      sample=lambda x: (x.out(0), x.out(1), x.u32(PAD_STATE), x.mfx_mode(), x.mode(), x.leds()))
    # the outputs of these lanes keep their last value while the byte is 0 (a part's lane goes silent): what counts is that they stop moving
    xy = lambda loop, s: seen[(loop, s)][:2]
    frozen = {xy(0, s) for s in range(21, 32)} | {xy(1, s) for s in range(16, 25)}
    out.append(entry("mfx_off_at_once", all(xy(0, s) == plain[(0, s)] for s in range(16, 21)) and frozen == {plain[(0, 20)]},
                     f"MASTER FX held, TAP at step 20: the lanes play as recorded until step 20 and stand still after it ({sorted(frozen)}, step 20 was {plain[(0, 20)]})"))
    out.append(entry("mfx_on_at_once", all(xy(1, s) == plain[(0, s)] for s in range(25, 32)),
                     f"TAP again at step 24 of the next run: from step 25 the lanes play as recorded again ({[xy(1, s) for s in range(25, 32)]}), pad state by step {[seen[(1, s)][2] for s in range(22, 34)]}"))
    pad = {s: seen[(0, s)][2] for s in range(16, 34)}
    out.append(entry("mfx_pad_let_go", all(pad[s] == 1 for s in range(16, 20)) and all(pad[s] == 0 for s in range(20, 34)), f"pad state by step with the gesture switched off at 20: {pad}"))
    # the LED is not compared here: with the gesture recorded and its motion on it blinks (case_mfx_blink)
    out.append(entry("mfx_leaves_the_part_alone", all(v[4] == (1, 1) for v in seen.values()) and box.mfx_mode() == 1,
                     f"the part's byte stayed {set(v[4] for v in seen.values())}, the Master FX byte ends {box.mfx_mode()}"))
    states = {k: v[3] for k, v in seen.items() if k[1] in (10, 22, 30)}
    out.append(entry("mfx_byte_follows", states[(0, 10)] == 1 and states[(0, 22)] == 0 and states[(1, 10)] == 0 and states[(1, 30)] == 1, f"Master FX byte {states}"))

    # the LED shows the Master FX motion while MASTER FX is held, the part's otherwise
    led = TBox(payload, flash)
    led.set_mfx_mode(0)
    held_dark = None
    led.hold("master_fx", True)
    led.run(0.3)
    held_dark = led.leds()
    led.hold("master_fx", False)
    led.run(0.3)
    out.append(entry("mfx_led_while_held", held_dark == 0 and led.leds() == 255, f"Master FX motion off: LED {held_dark} while MASTER FX is held, {led.leds()} after (the part's motion is on)"))

    # the gesture itself is not touched: recording with the Master FX motion off still records, a live touch still reaches the pad
    off = TBox(payload, flash)
    off.set_mfx_mode(0)
    off.record_gesture()
    lanes = [off.lane(i) for i in range(3)]
    live = TBox(payload, flash)
    live.ensure_master_fx()
    live.set_mfx_mode(0)
    live.m.send([0, 0x22, 1, 0, 0])
    live.run(0.1)
    live.m.send([5, 0x01, 0xF4, 0x01, 0x90])
    live.run(0.3)
    xy = live.dev.read(live.pat() + 0x40, 4).hex()
    out.append(entry("mfx_off_still_records_and_plays_live", all(len(l) >= 10 for l in lanes) and xy[0:2] == "01" and xy[4:6] != "00" and off.mfx_mode() == 0,
                     f"lanes recorded with the byte at 0: {[len(l) for l in lanes]} bytes; a live touch writes the pad bytes {xy}"))
    return out


def runtime_size():
    """Bytes of the script runtime's state area, from its patch (the app table is the last 0x78 of them: SCRIPT_APPS_STATE_SIZE)."""
    patch = json.loads((ROOT / "data" / "patches" / "script-runtime.json").read_text())
    return next(int(a["length"]) for a in patch["ram"] if int(a["at"], 16) == RUNTIME)


def case_app(payload, flash):
    """A plugin or an app that owns the keys keeps TAP from the firmware: no toggle, no tap tempo. The capture mask is the plugin's way,
    an open app forces it for every key but the transport keys (tools/patch/script_hooks.s, input_mask_app). The state area of the runtime
    is zeroed first, the way an initialised runtime leaves it before a plugin is loaded (nothing open, nothing captured)."""
    from menu_cases import has_menu
    if not has_menu(payload):
        return []
    size = runtime_size()
    rows = {}
    for label, mask, app_open in (("armed, nothing captured", 0, 0), ("keys captured", 1, 0), ("app open", 0, 1)):
        box = TBox(payload, flash)
        box.m.uc.mem_write(RUNTIME, bytes(size))
        box.m.uc.mem_write(RT_ARMED, struct.pack("<I", 1))
        box.m.uc.mem_write(RT_CAPTURE_MASK, struct.pack("<I", mask))
        if app_open:
            # an entry in the pool that looks like a loaded app (its blob lies in the pool, the frame hook leaves Blechy's block alone)
            box.m.uc.mem_write(POOL, bytes(0x124))
            box.m.uc.mem_write(POOL + 4, struct.pack("<I", POOL))                  # SCRIPT_ENTRY_BLOB
            app_open = POOL
        box.m.uc.mem_write(RUNTIME + size - 0x78, struct.pack("<I", app_open))     # SCRIPT_APPS_OPEN: the entry of the open app
        box.run(0.1)
        tempo_before = box.tempo()
        for _ in range(3):
            box.tap(0.6)
        rows[label] = (box.mode(), box.tempo() == tempo_before, box.m.asserts)
    return [entry("app_owns_tap", rows["armed, nothing captured"] == ((0, 0), True, []) and rows["keys captured"] == ((1, 1), True, []) and rows["app open"] == ((1, 1), True, []),
                  f"three TAPs with the runtime armed (mode, tempo unchanged, assertions): {rows}; the first row toggles three times, the other two reach the plugin only")]


def case_once(payload, flash):
    """Setting ONCE (2): a motion TAP switched on plays to the end of the pattern and goes off when the steps start over."""
    out = []
    box = TBox(payload, flash)
    box.m.uc.mem_write(spec.TM_SETTING, struct.pack("<I", 2))
    box.run(0.1)
    box.record_knob()
    tap = TBox.press_in_script
    seen = box.script({(0, 2): tap, (0, 8): tap}, 3)
    first, second, third = audible(seen, 0, WINDOW), audible(seen, 1, WINDOW), audible(seen, 2, WINDOW)
    out.append(entry("once_plays_to_the_end", len(first) >= 15 and not second and not third and box.mode() == (0, 0),
                     f"TAP off at step 2, on at step 8: the steps 16 to 31 play in the first run ({len(first)} of 16), not in the second ({second}) "
                     f"or third ({third}); the mode is {box.mode()} afterwards"))
    box.tap()
    out.append(entry("once_comes_back_with_tap", box.mode() == (1, 1), f"TAP again: mode {box.mode()}"))
    on = TBox(payload, flash)
    on.m.uc.mem_write(spec.TM_SETTING, struct.pack("<I", 1))
    on.run(0.1)
    on.record_knob()
    kept = on.script({(0, 2): tap, (0, 8): tap}, 2)
    out.append(entry("on_keeps_playing", len(audible(kept, 1, WINDOW)) >= 15 and on.mode() == (1, 1),
                     f"setting ON: the second run plays too ({len(audible(kept, 1, WINDOW))} of 16), mode {on.mode()}"))
    out.append(entry("once_no_assertion", not box.m.asserts and not on.m.asserts, f"{box.m.asserts} {on.m.asserts}"))
    return out


def case_touch_scale(payload, flash):
    """TOUCH SCALE held with TAP switches the Master FX lanes like MASTER FX held (MFX 2 sits on TOUCH SCALE); the LED shows them
    while it is held; the part stays as it was."""
    out = []
    box = TBox(payload, flash)
    box.record_gesture()
    before, part = box.mfx_mode(), box.mode()
    box.hold("touch_scale", True)
    held_led = box.leds()
    box.tap(0.2)
    off, led_off, part_off = box.mfx_mode(), box.leds(), box.mode()
    box.tap(0.2)
    on = box.mfx_mode()
    box.hold("touch_scale", False)
    out.append(entry("touch_scale_tap_switches_mfx", before == 1 and off == 0 and on == 1 and box.mode() == part,
                     f"byte {before}, TOUCH SCALE held and TAP: {off}, TAP again: {on}; part {part} -> {box.mode()}"))
    out.append(entry("touch_scale_led_shows_mfx", held_led == 255 and led_off == 0 and part_off == part,
                     f"LED while held {held_led}, after switching the lanes off {led_off} while the part stays {part_off}"))
    return out


def case_card_pulled(payload, flash):
    """A card pulled while the device runs leaves the patch on: it was seen at power-on, the latch of tools/patch/card_gate.py
    keeps it (device 18.10.: TAP MOTION went off with the card). The Sampler's volume is also marked unmounted, as FatFs
    does at the next access; the synth's detect pin goes high with the eject."""
    box = TBox(payload, flash)
    box.tap()
    before = box.mode()
    box.m.eject_card()
    box.run(1.0)
    volume = None
    if not box.dev.synth:
        fs = box.u32(FATFS)
        volume = box.dev.read(fs, 1)[0]
        box.m.uc.mem_write(fs, b"\0")
    box.tap()
    after = box.mode()
    box.tap()
    again = box.mode()
    return [entry("card_pulled_keeps_tap", before == (0, 0) and after == (1, 1) and again == (0, 0) and not box.m.asserts,
                  f"TAP with the card: {before}; card pulled (volume type byte after a second {volume}, then 0), TAP: {after}, TAP: {again}; "
                  f"assertions {box.m.asserts}")]


def case_mfx_blink(payload, flash):
    """With a Master FX gesture recorded and its motion on, the TAP LED blinks without MASTER FX held: half on with the part's
    motion off, on with a short gap with it on; with the Master FX motion off, or with no gesture recorded (the byte is 1 in
    every new pattern), it is steady as the part says."""
    def watch(box, seconds=1.92):
        box.run(0.1)                     # the LED follows within one 40 ms tick
        seen, t = [], 0.0
        while t < seconds:
            box.run(0.02)
            t += 0.02
            seen.append(1 if box.leds() == 255 else 0)
        changes = sum(1 for a, b in zip(seen, seen[1:]) if a != b)
        return round(sum(seen) / len(seen), 2), changes

    plain = TBox(payload, flash)
    no_gesture = (plain.mfx_mode(), watch(plain))
    box = TBox(payload, flash)
    box.record_gesture()
    rows = {}
    for name, part, mfx in (("part on", 1, 1), ("part off", 0, 1), ("mfx off", 1, 0), ("both off", 0, 0)):
        box.set_mode(part)
        box.set_mfx_mode(mfx)
        rows[name] = watch(box)
    box.set_mode(1)
    box.set_mfx_mode(1)
    box.hold("master_fx", True)
    held = watch(box, 0.4)
    box.hold("master_fx", False)
    ok = (no_gesture[0] == 1 and no_gesture[1] == (1.0, 0)
          and 0.75 <= rows["part on"][0] <= 0.92 and rows["part on"][1] >= 6
          and 0.4 <= rows["part off"][0] <= 0.6 and rows["part off"][1] >= 6
          and rows["mfx off"] == (1.0, 0) and rows["both off"] == (0.0, 0) and held == (1.0, 0) and not box.m.asserts)
    return [entry("mfx_motion_blinks", ok, f"(share of samples lit, changes) in 1.92 s: new pattern without a gesture, byte {no_gesture[0]}: {no_gesture[1]}; "
                  f"with a gesture {rows}; MASTER FX held {held}; assertions {box.m.asserts}")]


def case_hold(payload, flash):
    """TAP held 320 ms or longer works only while held: letting go switches back; a short TAP stays switched (device 18.10.)."""
    t = TBox(payload, flash)
    start = t.mode()
    t.hold("tap", True)
    t.run(0.5)
    held = t.mode()
    t.hold("tap", False)
    t.run(0.2)
    let_go = t.mode()
    t.tap()
    short = t.mode()
    t.run(0.5)
    later = t.mode()
    t.tap()
    t.ensure_master_fx()
    t.hold("master_fx", True)
    mfx_start = t.mfx_mode()
    t.hold("tap", True)
    t.run(0.5)
    mfx_held = t.mfx_mode()
    t.hold("tap", False)
    t.run(0.2)
    mfx_back = t.mfx_mode()
    t.hold("master_fx", False)
    return [entry("hold_works_while_held", start == (1, 1) and held == (0, 0) and let_go == (1, 1) and not t.m.asserts,
                  f"before {start}, held 0.6 s {held}, let go {let_go}"),
            entry("short_tap_stays", short == (0, 0) and later == (0, 0), f"after a short TAP {short}, 0.5 s later {later}"),
            entry("hold_with_master_fx", mfx_held != mfx_start and mfx_back == mfx_start, f"Master FX motion before {mfx_start}, held {mfx_held}, let go {mfx_back}")]


GROUPS = (case_toggle, case_memory, case_stock, case_shift_tap, case_rec_and_pattern, case_mfx, case_app, case_once, case_touch_scale, case_card_pulled, case_mfx_blink, case_hold)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own devices, so they can run side by side."""
    for_build(payload)
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases",))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    entries = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
