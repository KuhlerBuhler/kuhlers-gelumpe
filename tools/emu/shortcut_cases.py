# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the EXIT shortcuts of the BLECH runtime (tools/patch/script_shortcuts.s,
docs/messungen/2026-10-19-exit-shortcuts.md).

check.py runs `cases` on every patched copy that carries the BLECH menu, the blue Electribe's too (its places from data/synth-map/). With EXIT held on the main screen, WRITE
saves the edited pattern into its own place (through the firmware's Write window) and a pad puts the sound of a part back to
the values saved in the bank, the steps and the other parts left as they are, and the part's voices take its saved sample again,
stopped and while playing. WRITE alone still only opens the window, and with
EXIT held at power-on both are the firmware's.

    tools/emu/.venv/bin/python tools/emu/shortcut_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases  # noqa: E402
import synthaddr  # noqa: E402
import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402
from machine import load_flash  # noqa: E402
from pswitch_cases import Box, play  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

PATPTR = 0xC033E6A4
LEDMGR = 0xC0345A1C
EXIT, WRITE, SHIFT, TRIGGER, SEQUENCER = 0x0D, 0x0E, 0x0A, 0x13, 0x15
PART_MUTE, PART_ERASE, KEYBOARD, CHORD, STEP_JUMP, PATTERN_SET = 0x10, 0x11, 0x17, 0x18, 0x19, 0x1B
WRITE_LED = 0x0B
WINDOW = 18                     # the firmware's Write window
PART, STRIDE, SOUND = 0x800, 0x330, range(2, 0x30)
STEPS = 0x30                    # the steps of a part start here, 12 bytes each
KILL = menu_cases.KILL
KEY_AT = 39                     # KEY of the pattern, 0 to 11
KEY_PADS_ON = script_hooks.MENU_STATE + 0x104   # M_KP: the page KEY PADS (tools/patch/script_menu.s)
# Per pad the KEY that KEY PADS sets, -1 none: chromatic in pad order, pad 1 C to pad 12 B; pads 13 to 16 set nothing.
KEY_NOTES = list(range(12)) + [-1] * 4
KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DRAW_TEXT = {False: 0xC003F7D0, True: 0xC003A408}   # the firmware's text draw (text, x, y, ...), Sampler and synth
DISPATCH = 0xC002837C           # the dispatcher of panel messages, before the input filter
SEQ_NOTIFY = 0xC0070688         # (observers, message): KEY PADS opens the parameter window with {0x5A, KEY} through it
FILTER_TOGGLE_ON = script_hooks.MENU_STATE + 0x1C0   # M_FT: the page FILTER TOGGLE (tools/patch/script_menu.s)
FILTER_AT = 0x80C               # the filter type of part 1 in the pattern file (live()); 0 OFF, 1 to 6 LPF, 7 to 11 HPF, 12 to 16 BPF
FILTER_KEYS = {"lpf": 0x12, "hpf": 0x14, "bpf": 0x16}
FILTER_LEDS = (0x0C, 0x0D, 0x0E)
FILTER_NOTIFY = 0xC004B208      # (this, part, parameter, value): the firmware's message that a parameter changed
FILTER_PARAM = 29               # its number for the filter type
# Per key, the type from which one press of the hardware key lands on a type (synth_filter_cases.MEASURED)
FIRMWARE_FROM = {"lpf": {0: 6, 2: 1, 3: 2}, "hpf": {0: 11, 7: 0, 8: 7}, "bpf": {12: 0}}


def has_hooks(payload):
    return menu_cases.has_menu(payload)


def entry(name, ok, detail):
    return {"id": f"shortcut:{name}", "ok": bool(ok), "detail": str(detail)}


class SBox(Box):
    def live(self):
        return bytes(self.m.uc.mem_read(self.u32(PATPTR) + 4, 0x4000))

    def saved(self, number=None):
        return bytes(self.m.uc.mem_read(self.slots + (self.running() if number is None else number) * 0x4000, 0x4000))

    def poke(self, at, value):
        self.m.uc.mem_write(self.u32(PATPTR) + 4 + at, bytes([value]))

    def screen(self):
        return self.dev.screen()["number"]

    def selected(self):
        return self.u32(self.u32(LEDMGR) + 0xB60)

    def exit_held(self, down):
        self.m.press(EXIT, down)
        self.run(0.2)

    def pad(self, n):
        self.m.send([4, n, 0, 100, 1])
        self.run(0.1)
        self.m.send([4, n, 0, 0, 0])
        self.run(0.3)


def nudge(box):
    """Turns knob 1 so that the pattern changes: 200 is the value it already holds in the synth's Init pattern, 40 then."""
    for value in (200, 40):
        box.m.send([2, 0, 0, value, 0])
        box.run(0.5)
        if box.live() != box.saved():
            return


def edit(box, part, step_byte=None):
    """Changes three sound bytes of a part (cutoff, level, pan) and, if asked, a byte of its first step. Returns the changed offsets."""
    base = PART + STRIDE * part
    at = [base + 13, base + 24, base + 25]
    for a in at:
        box.poke(a, box.live()[a] ^ 0x15)
    if step_byte is not None:
        a = base + STEPS + step_byte
        box.poke(a, box.live()[a] ^ 1)
        at.append(a)
    return at


def case_save(payload, flash):
    out = []
    box = SBox(payload, flash)
    others = [box.saved(n) for n in (1, 2)]
    nudge(box)
    edited = box.live() != box.saved()
    box.exit_held(True)
    box.dev.press(WRITE, 1.0)
    box.exit_held(False)
    box.run(0.5)
    out.append(entry("exit_write_saves", edited and box.live() == box.saved() and box.screen() == 1
                     and [box.saved(n) for n in (1, 2)] == others and not box.m.asserts,
                     f"edited {edited}; EXIT + WRITE: saved into its own place {box.live() == box.saved()}, screen {box.screen()}, "
                     f"other places untouched {[box.saved(n) for n in (1, 2)] == others}"))
    plain = SBox(payload, flash)
    nudge(plain)
    plain.dev.press(WRITE, 0.3)
    plain.dev.press(WRITE, 1.5)
    out.append(entry("write_alone_is_stock", plain.screen() == WINDOW and plain.live() != plain.saved() and not plain.m.asserts,
                     f"WRITE without EXIT: screen {plain.screen()} (the Write window waits), unsaved {plain.live() != plain.saved()}"))
    return out


def case_reset(payload, flash):
    out = []
    box = SBox(payload, flash)
    saved = box.saved()
    zero = edit(box, 0, step_byte=2)
    five = edit(box, 5)
    box.exit_held(True)
    box.pad(0)
    box.exit_held(False)
    live = box.live()
    sound_back = all(live[PART + i] == saved[PART + i] for i in SOUND)
    step_kept = live[zero[3]] != saved[zero[3]]
    five_kept = all(live[a] != saved[a] for a in five)
    out.append(entry("exit_pad_resets_its_part", sound_back and step_kept and five_kept and box.selected() == 0
                     and box.screen() == 1 and not box.m.asserts,
                     f"TRIGGER, EXIT + pad 1: sound of part 1 back {sound_back}, its step edit kept {step_kept}, part 6 still edited {five_kept}, "
                     f"selected part {box.selected()}, screen {box.screen()}"))
    box.exit_held(True)
    box.pad(5)
    box.exit_held(False)
    live = box.live()
    out.append(entry("exit_pad_takes_the_pads_part", all(live[a] == saved[a] for a in five) and box.selected() == 0 and not box.m.asserts,
                     f"TRIGGER, EXIT + pad 6: part 6 back {all(live[a] == saved[a] for a in five)}, the selected part stays {box.selected()}"))
    seq = SBox(payload, flash)
    saved = seq.saved()
    zero = edit(seq, 0)
    seq.dev.press(SEQUENCER, 0.3)
    seq.exit_held(True)
    seq.pad(9)
    seq.exit_held(False)
    live = seq.live()
    out.append(entry("exit_pad_in_sequencer_resets_the_selected_part", all(live[a] == saved[a] for a in zero)
                     and live[PART + STEPS + 9 * 12] == saved[PART + STEPS + 9 * 12] and not seq.m.asserts,
                     f"SEQUENCER, EXIT + pad 10: part 1 (selected) back {all(live[a] == saved[a] for a in zero)}, step 10 not toggled "
                     f"{live[PART + STEPS + 9 * 12] == saved[PART + STEPS + 9 * 12]}"))
    playing = SBox(payload, flash)
    saved = playing.saved()
    play(playing)
    at = edit(playing, 2)
    before = playing.running()
    playing.exit_held(True)
    playing.pad(2)
    playing.exit_held(False)
    playing.run(1.0)
    live = playing.live()
    out.append(entry("exit_pad_while_playing", all(live[a] == saved[a] for a in at) and playing.transport() == 1
                     and playing.running() == before and not playing.m.asserts,
                     f"playing, EXIT + pad 3: part 3 back {all(live[a] == saved[a] for a in at)}, still playing {playing.transport() == 1}, "
                     f"pattern {playing.running()} (was {before})"))
    return out


PART_OBJECT = 0xC009AF20        # (part) -> the part's object for the voices; +0x34 the sample its next note takes
OBJECT_SAMPLE = 0x34
NOTE_ON = 0xC00998B4            # a voice takes a note: r0 the voice, r1 the sample (pswitch_cases.case_voices)
MAILBOX = 0xFF900A34            # the DSP's mailbox: what a note sends there (ht_osc_cases.Box.note)
SAMPLE_AT = 8                   # the sample of a part, a half word in its record
OSC_DIAL = [1, 1, 0, 1, 0]      # the OSC encoder one step up: the firmware's own sample change (live_write_cases.PART_INPUTS)


class VBox(SBox):
    """A device that sees what the voices of part 1 get: the sample in its part object, the samples of the notes the voices
    take, and the words the DSP's mailbox gets (DspLog, the note messages as ht_osc_cases reads them)."""

    def __init__(self, payload, flash=None, held=0):
        super().__init__(payload, flash, held)
        from mfx_cases import DspLog
        self.log = DspLog(self.m)
        self.notes = []
        self.part = self.dev.call(PART_OBJECT, 0)
        at = self.dev.a(NOTE_ON)
        self.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: self.notes.append(uc.reg_read(UC_ARM_REG_R1)), begin=at, end=at)
        self.m.uc.ctl_flush_tb()

    def sample(self, data=None):
        return struct.unpack_from("<H", self.live() if data is None else data, PART + SAMPLE_AT)[0]

    def voice_sample(self):
        return struct.unpack("<H", self.dev.read(self.part + OBJECT_SAMPLE, 2))[0]

    def steps(self, part_one):
        """No part has a step on, or (part_one) part 1 has all 64 on: every note the sequencer plays is part 1's, at every step."""
        for part in range(16):
            for step in range(64):
                at = PART + STRIDE * part + STEPS + 12 * step
                on = part_one and part == 0
                self.poke(at, 1 if on else 0)
                for i, value in enumerate((60, 100, 1, 60) if on else (), 1):
                    self.poke(at + i, value)

    def change_sample(self):
        for _ in range(3):
            self.m.send(OSC_DIAL)
            self.run(0.3)
        self.run(1.5)                   # the OSC value window closes

    def reset(self):
        self.exit_held(True)
        self.pad(0)
        self.exit_held(False)
        self.run(0.5)

    def hit(self):
        """Pad 1 (TRIGGER: part 1 sounds): the samples its voice takes and the values of the mailbox's note messages."""
        self.notes.clear()
        self.log.clear()
        self.pad(0)
        words = {x[3][4] for x in self.log.xfers if x[0] == 0xAB and x[1] == MAILBOX and len(x[3]) > 4 and x[3][0] & 2 and x[3][1] == 0}
        return list(self.notes), words

    def sequenced(self, seconds=1.5):
        """The samples of the notes the sequencer plays in `seconds`."""
        self.notes.clear()
        self.run(seconds)
        return sorted(set(self.notes))


def case_reset_voice(payload, flash):
    """EXIT + pad after the sample of part 1 was changed with the OSC encoder: the voices get the saved sample again, stopped and
    while playing (device report 10.11.: the display went back, PLAY still played the changed sample). Checked where the voices
    take it: the part object, the sample of each note a voice takes (sequencer and pad), and a twin probe of the DSP: without any
    step on, the values the mailbox gets for the note of pad 1 hold none of those only a device with the changed sample sends,
    and all of those only an untouched device sends (the voices rotate, so values are compared, not places)."""
    out = []
    for playing in (False, True):
        slug, how = ("while_playing", "playing") if playing else ("stopped", "stopped")
        box = VBox(payload, flash)
        box.steps(True)
        if playing:
            play(box)
        saved = box.sample(box.saved())
        box.change_sample()
        changed = box.sample()
        firmware_follows = box.voice_sample() == changed != saved
        box.reset()
        restored = box.sample() == saved and box.voice_sample() == saved
        if not playing:
            play(box)
        seq = box.sequenced()
        notes = sorted(set(box.hit()[0]))      # the sequencer's notes of part 1 come along
        out.append(entry(f"exit_pad_resets_the_voice_{slug}", firmware_follows and restored and seq == [saved] and notes == [saved]
                         and box.transport() == 1 and not box.m.asserts,
                         f"{how}: saved sample {saved}, OSC encoder 3 up {changed}, part object took it {firmware_follows}; EXIT + pad 1: "
                         f"pattern {box.sample()}, part object {box.voice_sample()}; {'sequencer goes on' if playing else 'PLAY'}, its notes "
                         f"take {seq}; pad 1 takes {notes}; playing {box.transport() == 1}"))
        twins = {kind: VBox(payload, flash) for kind in ("plain", "changed", "reset")}
        for kind, twin in twins.items():
            twin.steps(False)
            if playing:
                play(twin)
            if kind != "plain":
                twin.change_sample()
            if kind == "reset":
                twin.reset()
        hits = {kind: twin.hit() for kind, twin in twins.items()}
        only_changed = hits["changed"][1] - hits["plain"][1]
        only_plain = hits["plain"][1] - hits["changed"][1]
        dsp_ok = bool(only_changed) and bool(only_plain) and not hits["reset"][1] & only_changed and only_plain <= hits["reset"][1]
        out.append(entry(f"exit_pad_resets_the_dsp_{slug}", dsp_ok and not any(t.m.asserts for t in twins.values()),
                         f"{how}, pad 1: mailbox values only the changed twin sends {sorted(only_changed)}, only the untouched twin "
                         f"{sorted(only_plain)}; after EXIT + pad: of the changed ones {sorted(hits['reset'][1] & only_changed)}, of the "
                         f"untouched ones {sorted(hits['reset'][1] & only_plain)}; samples of the notes {[hits[k][0] for k in hits]}"))
    return out



def case_reset_dsp(payload, flash):
    """EXIT + pad 1 leaves part 1 switched on at the DSP, stopped and while playing, after its note sounded and its sample was
    changed. Asked on the DSP's side of the host port (dsp_model.py), so it holds whatever firmware routine a reset calls.
    Device test 11.11.: a reset that switched the part off left it silent until the SAMPLE knob was turned and the sequencer
    restarted (#506); the model cannot tell silence, only that the switch went to 0 (docs/messungen/2026-11-12-dsp-modell.md)."""
    from dsp_model import DspModel
    out = []
    for playing in (False, True):
        slug, how = ("while_playing", "playing") if playing else ("stopped", "stopped")
        box = VBox(payload, flash)
        dsp = DspModel.attach(box.m)
        box.steps(True)
        if playing:
            play(box)
        box.hit()
        on_before = dsp.part_on(0)
        box.change_sample()
        mark = dsp.mark()
        box.reset()
        offs = dsp.parts_switched_off(mark)
        out.append(entry(f"exit_pad_keeps_the_part_on_at_the_dsp_{slug}", on_before and not offs and dsp.part_on(0)
                         and not box.m.asserts,
                         f"{how}: part 1 on at the DSP after its note {on_before}; EXIT + pad 1 switched off parts {offs or 'none'}, "
                         f"part 1 on afterwards {dsp.part_on(0)}"))
    return out


METER_OBJECT = 0xC033E4F4       # the meter LEDs read the output peak from [this] +0x10 (left) and +0x14 (right), both builds


def case_meter_dsp(payload, flash):
    """The bottom LEDs follow the output peak the DSP hands back (dsp_model.py, docs/messungen/2026-11-12-pegel-leds.md): the
    firmware reads 0xFF9030F4 every 40 ms into the meter object and sets it back to 0 at the DSP. Silent, full scale, silent
    again, on mains power (on battery the LEDs are off)."""
    from dsp_model import FULL_SCALE, DspModel
    dev = menu_cases.boot(payload, flash, adapter=True)
    dsp = DspModel.attach(dev.m)
    seen = []
    for level in (0, 1.0, 0):
        dsp.output(level)
        dev.run(1.0)
        obj = dev.u32(METER_OBJECT)
        seen.append(((dev.u32(obj + 0x10), dev.u32(obj + 0x14)), menu_cases.leds(dev)))
    (quiet_peak, quiet), (loud_peak, loud), (after_peak, after) = seen
    ok = (quiet_peak == after_peak == (0, 0) and loud_peak == (FULL_SCALE, FULL_SCALE) and loud != quiet and after == quiet
          and loud[:3] == loud[3:6] and loud[0] > 200 and loud[1] == 0 and not dev.m.asserts)
    return [entry("dsp_output_peak_drives_the_meter_leds", ok,
                  f"peak in the meter object silent {quiet_peak}, full {loud_peak}, silent again {after_peak}; LEDs {quiet}, "
                  f"{loud}, {after}")]


def case_voices_dsp(payload, flash):
    """The voices the DSP opens follow the sequencer (dsp_model.py voices): part 1 on every step, part 3 on every 4th, played
    1.5 s. Every note the firmware starts (NOTE_ON) opens one voice of its part at the DSP, and the note's end closes it."""
    from dsp_model import DspModel
    box = VBox(payload, flash)
    dsp = DspModel.attach(box.m)
    for part in range(16):
        for step in range(64):
            at = PART + STRIDE * part + STEPS + 12 * step
            on = part == 0 or (part == 2 and step % 4 == 0)
            box.poke(at, 1 if on else 0)
            for i, value in enumerate((60, 100, 1, 60) if on else (), 1):
                box.poke(at + i, value)
    box.run(0.3)
    mark = len(dsp.gates)
    box.notes.clear()
    play(box)
    box.run(1.5)
    one, three = len(dsp.notes(0, mark)), len(dsp.notes(2, mark))
    opened = [g for g in dsp.gates[mark:] if g[3]]
    closed = [g for g in dsp.gates[mark:] if not g[3]]
    ok = (one + three == len(dsp.notes(None, mark)) == len(box.notes) and 0 < three < one
          and len(opened) - len(closed) == len(dsp.voices()) <= 2 and not box.m.asserts)
    return [entry("dsp_voices_follow_the_sequencer", ok,
                  f"NOTE_ON {len(box.notes)}; voices opened for part 1 {one}, part 3 {three}, other parts "
                  f"{len(dsp.notes(None, mark)) - one - three}; closed {len(closed)}, open now {dsp.voices()}")]

MODES = ((PART_MUTE, "PART MUTE", True), (KEYBOARD, "KEYBOARD", True), (PART_ERASE, "PART ERASE", True), (CHORD, "CHORD", True),
         (PATTERN_SET, "PATTERN SET", True), (STEP_JUMP, "STEP JUMP", False))


def case_reset_modes(payload, flash):
    """EXIT + pad 6 in the other pad modes: the pad's part where a pad stands for a part, a note, a chord or a pattern; the
    selected part where it stands for a step (STEP JUMP, like SEQUENCER in case_reset). The selected part stays 1."""
    out = []
    for key, name, pads_part in MODES:
        box = SBox(payload, flash)
        saved = box.saved()
        box.dev.press(key, 0.3)
        six = edit(box, 5)
        one = edit(box, 0)
        box.exit_held(True)
        box.pad(5)
        box.exit_held(False)
        live = box.live()
        six_back = all(live[a] == saved[a] for a in six)
        one_back = all(live[a] == saved[a] for a in one)
        want = (True, False) if pads_part else (False, True)
        slug = name.lower().replace(" ", "_")
        what = "part 6 (the pad's)" if pads_part else "part 1 (the selected)"
        out.append(entry(f"exit_pad_in_{slug}_resets_{'the_pads_part' if pads_part else 'the_selected_part'}",
                         (six_back, one_back) == want and box.selected() == 0 and box.screen() == 1 and not box.m.asserts,
                         f"{name}, parts 1 and 6 edited, EXIT + pad 6: wants {what} back; part 6 back {six_back}, part 1 back {one_back}, "
                         f"selected part {box.selected()}, screen {box.screen()}"))
    return out


def case_kill(payload, flash):
    box = SBox(payload, flash, held=KILL)
    nudge(box)
    at = edit(box, 0)
    box.exit_held(True)
    box.dev.press(WRITE, 1.0)
    window = box.screen()
    box.dev.press(EXIT, 0.5)
    box.pad(0)
    box.exit_held(False)
    live, saved = box.live(), box.saved()
    return [entry("kill_switch", window == WINDOW and live != saved and all(live[a] != saved[a] for a in at) and not box.m.asserts,
                  f"EXIT held at power-on: EXIT + WRITE leaves the Write window open (screen {window}), nothing saved {live != saved}, "
                  f"EXIT + pad resets nothing {all(live[a] != saved[a] for a in at)}")]


def case_unsaved(payload, flash):
    """The WRITE LED breathes (odd values, changing) while the pattern is unsaved, and goes dark once it is saved."""
    box = SBox(payload, flash, adapter=True)     # on battery power save sends every LED at a quarter
    led = lambda: box.m.leds.get(WRITE_LED, 0)
    box.run(1.0)
    clean = led()
    nudge(box)
    seen = set()
    for _ in range(40):
        box.run(0.05)
        seen.add(led())
    box.exit_held(True)
    box.dev.press(WRITE, 1.0)
    box.exit_held(False)
    box.run(1.0)
    saved = led()
    lit = sorted(v for v in seen if v)
    return [entry("write_led_breathes_while_unsaved", clean == 0 and len(lit) >= 5 and all(v % 2 == 1 and v < 128 for v in lit) and saved == 0
                  and box.live() == box.saved() and not box.m.asserts,
                  f"saved: WRITE LED {clean}; a knob turned, 2 s: values {lit}; after EXIT + WRITE {saved}")]


def case_pad_state(payload, flash):
    """A pattern saved with the MFX pad touched (byte 0x3C = 1, HOLD off) loads with 0 there, the firmware's doing: the WRITE LED
    stays dark, nothing was edited (device report 19.10.)."""
    box = SBox(payload, flash, adapter=True)
    led = lambda: box.m.leds.get(WRITE_LED, 0)
    box.m.uc.mem_write(box.slots + 0x4000 + 0x3C, bytes([1]))
    box.m.uc.mem_write(box.slots + 0x4000 + 0x41, bytes([0]))
    box.turn(1, 1.0)
    seen = set()
    for _ in range(40):
        box.run(0.05)
        seen.add(led())
    live, saved = box.live(), box.saved()
    rewritten = box.running() == 1 and live[0x3C] == 0 and saved[0x3C] == 1
    rest = [i for i in range(0x4000) if i != 0x3C and live[i] != saved[i]]
    xy = box.u32(PATPTR) + 4 + 0x3E               # a touch of the pad writes its X and Y: no edit either (device wish 25.10.)
    box.m.uc.mem_write(xy, bytes(b ^ 0x40 for b in box.dev.read(xy, 2)))
    touched = set()
    for _ in range(40):
        box.run(0.05)
        touched.add(led())
    return [entry("pad_state_is_not_an_edit", rewritten and not rest and seen == {0} and not box.m.asserts,
                  f"pattern {box.running()}, byte 0x3C live {live[0x3C]} saved {saved[0x3C]}, other differences {rest[:8]}, WRITE LED {sorted(seen)}"),
            entry("pad_xy_is_not_an_edit", touched == {0} and not box.m.asserts, f"pad X and Y changed in RAM: WRITE LED {sorted(touched)}")]


def case_key_pads(payload, flash):
    """KEY PADS: KEYBOARD held on the main screen, a pad sets the KEY of the pattern and the firmware's parameter window shows
    "KEY" and the note; a short press of KEYBOARD alone reaches the firmware (marked) and switches to KEYBOARD mode; SHIFT +
    KEYBOARD and the page switched OFF leave KEYBOARD to the firmware, whose KEYBOARD + pad selects the part."""
    box = SBox(payload, flash)
    key = lambda: box.live()[KEY_AT]  # noqa: E731
    mode = lambda: box.u32(box.u32(LEDMGR) + 0xB58)  # noqa: E731
    texts, marked = [], []

    def draw(uc, *_):
        texts.append(bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0), 8)).split(b"\0")[0].decode("latin-1"))

    def dispatch(uc, *_):
        msg = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0) + 0xC, 8))
        if msg[0] == 0 and msg[1] == KEYBOARD and msg[7] == 0xB7:
            marked.append(msg[2])

    def notify(uc, *_):
        code, value = struct.unpack("<II", bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1), 8)))
        if code == 0x5A:
            opened.append(value)
    opened = []
    at = DRAW_TEXT[box.dev.synth]
    box.m.uc.hook_add(unicorn.UC_HOOK_CODE, draw, begin=at, end=at)
    at = box.dev.a(DISPATCH)
    box.m.uc.hook_add(unicorn.UC_HOOK_CODE, dispatch, begin=at, end=at)
    at = box.dev.a(SEQ_NOTIFY)
    box.m.uc.hook_add(unicorn.UC_HOOK_CODE, notify, begin=at, end=at)
    box.m.uc.ctl_flush_tb()

    def held(k, down, wait=0.2):
        box.m.press(k, down)
        box.run(wait)

    out = []
    box.poke(KEY_AT, 0)
    part = box.selected()
    held(KEYBOARD, True)
    got, shown, windows = [], [], []
    for n in range(16):
        texts.clear()
        opened.clear()
        if KEY_NOTES[n] < 0:
            box.poke(KEY_AT, 3)             # a pad without a note leaves any KEY as it is
        box.pad(n)
        got.append(key())
        windows.append(list(opened))
        if KEY_NOTES[n] >= 0:
            shown.append(KEY_NAMES[KEY_NOTES[n]] in texts and "KEY" in texts)
    held(KEYBOARD, False, 0.3)
    want = [n if n >= 0 else 3 for n in KEY_NOTES]
    out.append(entry("key_pads_set_the_key", got == want and box.selected() == part and marked == [] and not box.m.asserts,
                     f"KEY after each of the 16 pads {got} (want {want}), part {box.selected()} (was {part}), KEYBOARD passed on {marked}"))
    out.append(entry("key_pads_window_shows_the_key", len(shown) == 12 and all(shown)
                     and windows == [[n] if n >= 0 else [] for n in KEY_NOTES] and not box.m.asserts,
                     f"pads 1 to 12, window with KEY and the note: {shown}; window messages per pad {windows}"))

    box.dev.press(KEYBOARD, 0.4)
    out.append(entry("key_pads_short_press_reaches_the_firmware", marked == [1, 0] and mode() == 5 and key() == 3
                     and box.dev.read(script_hooks.PRESS_KEY, 8) == b"\xff" * 8 and not box.m.asserts,
                     f"KEYBOARD passed on {marked} (want press and release), pad mode {mode()} (want 5 KEYBOARD), KEY {key()}"))

    marked.clear()
    box.poke(KEY_AT, 0)
    held(SHIFT, True)
    held(KEYBOARD, True)
    held(KEYBOARD, False)
    held(SHIFT, False)
    box.m.uc.mem_write(KEY_PADS_ON, (0).to_bytes(4, "little"))
    held(KEYBOARD, True)
    box.pad(12)
    held(KEYBOARD, False, 0.3)
    out.append(entry("key_pads_shift_and_off_are_stock", key() == 0 and box.selected() == 12 and marked == [] and not box.m.asserts,
                     f"after SHIFT + KEYBOARD and KEY PADS OFF + KEYBOARD + pad 13: KEY {key()} (want 0), part {box.selected()} "
                     f"(want 12, the firmware's part select), marked presses {marked}"))
    return out


class FTBox(SBox):
    """A device for FILTER TOGGLE: SHIFT + a filter key, and what the press leaves behind (the part's type, the LEDs of LPF, HPF
    and BPF, the texts drawn, the frame, the firmware's parameter messages for the filter type)."""

    def __init__(self, payload, flash=None, held=0):
        super().__init__(payload, flash, held)
        self.texts, self.notices = [], []
        uc = self.m.uc

        def draw(u, *_):
            self.texts.append(bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), 16)).split(b"\0")[0].decode("latin-1"))

        def notice(u, *_):
            regs = (unicorn.arm_const.UC_ARM_REG_R2, unicorn.arm_const.UC_ARM_REG_R3)
            parameter, value = (u.reg_read(r) & 0xFFFFFFFF for r in regs)
            if parameter == FILTER_PARAM:
                self.notices.append(value)
        at = DRAW_TEXT[self.dev.synth]
        uc.hook_add(unicorn.UC_HOOK_CODE, draw, begin=at, end=at)
        at = self.dev.a(FILTER_NOTIFY)
        uc.hook_add(unicorn.UC_HOOK_CODE, notice, begin=at, end=at)
        uc.ctl_flush_tb()

    def ftype(self, part):
        return self.live()[FILTER_AT + STRIDE * part]

    def set_ftype(self, part, value):
        self.poke(FILTER_AT + STRIDE * part, value)

    def select(self, part):
        """The firmware's part select, KEYBOARD + pad, with KEY PADS off for it."""
        self.m.uc.mem_write(KEY_PADS_ON, (0).to_bytes(4, "little"))
        self.m.press(KEYBOARD, True)
        self.run(0.2)
        self.pad(part)
        self.m.press(KEYBOARD, False)
        self.run(0.3)
        self.m.uc.mem_write(KEY_PADS_ON, (1).to_bytes(4, "little"))

    def shift_key(self, key):
        """SHIFT held, the filter key pressed and released; returns what the press left behind (the texts each once: how often
        the window redraws in 0.4 s varies), taken while SHIFT is still held."""
        self.m.press(SHIFT, True)
        self.run(0.2)
        self.texts.clear()
        self.notices.clear()
        self.dev.press(key, 0.4)
        part = self.selected()
        look = (self.ftype(part), tuple(self.m.leds.get(x, 0) for x in FILTER_LEDS), tuple(dict.fromkeys(self.texts)), list(self.notices),
                bytes(self.dev.fb()))
        self.m.press(SHIFT, False)
        self.run(0.3)
        return look


def case_filter_toggle(payload, flash):
    """FILTER TOGGLE: SHIFT + LPF, HPF or BPF turns the filter of the selected part off, the same combination turns it on again
    with the type that key had last (per part and key), SHIFT + another filter key goes to that key's last type, the family's
    first type before it had one. Twin probe: every press is set against a press of the hardware filter key on a second device,
    from the type whose firmware step lands on the same type; the stored type, the LEDs, the texts of the firmware's "FILTER TYPE"
    window, the frame and the firmware's parameter message must be the same. FILTER TOGGLE OFF and EXIT held at power-on are the
    firmware's own keys."""
    toggle, twin = FTBox(payload, flash), FTBox(payload, flash)
    twin.m.uc.mem_write(FILTER_TOGGLE_ON, (0).to_bytes(4, "little"))     # the twin's SHIFT + key is the firmware's own key
    out, rows = [], []
    for box in (toggle, twin):
        box.select(0)

    def step(label, part, key, want, start=None):
        if start is not None:
            toggle.set_ftype(part, start)
        got = toggle.shift_key(FILTER_KEYS[key])
        twin.set_ftype(part, FIRMWARE_FROM[key][want])
        ref = twin.shift_key(FILTER_KEYS[key])
        rows.append((label, got[0], want, ref[0], got[1] == ref[1], got[2] == ref[2], got[3] == ref[3], got[4] == ref[4], got[2]))

    step("MS20 LPF, SHIFT+LPF: off", 0, "lpf", 0, start=2)
    step("SHIFT+LPF again: MS20 LPF back", 0, "lpf", 2)
    step("SHIFT+HPF: electribe HPF, the first", 0, "hpf", 7)
    for box in (toggle, twin):
        box.dev.press(FILTER_KEYS["hpf"], 0.4)      # the plain key cycles as always: MS20 HPF
        box.run(1.5)        # its window closes first: the device whose loop runs longer would redraw it into the next press's texts
    plain = toggle.ftype(0)
    step("SHIFT+LPF: MS20 LPF, its last", 0, "lpf", 2)
    step("SHIFT+HPF: MS20 HPF, its last", 0, "hpf", 8)
    step("SHIFT+HPF again: off", 0, "hpf", 0)
    step("SHIFT+BPF: electribe BPF, the first", 0, "bpf", 12)
    for box in (toggle, twin):
        box.select(3)
    step("part 4 MG LPF, SHIFT+LPF: off", 3, "lpf", 0, start=3)
    step("part 4 SHIFT+LPF: MG LPF, its own last", 3, "lpf", 3)
    for box in (toggle, twin):
        box.select(0)
    step("part 1 SHIFT+LPF: MS20 LPF, part 1's last", 0, "lpf", 2)

    bad = [r for r in rows if not (r[1] == r[2] == r[3])]
    out.append(entry("filter_toggle_types", not bad and plain == 8 and not toggle.m.asserts and not twin.m.asserts,
                     f"type after each SHIFT + key (got, want, the hardware key's): {[(r[0], r[1], r[2], r[3]) for r in rows]}; "
                     f"plain HPF from electribe HPF {plain} (want 8)"))
    out.append(entry("filter_toggle_twin_leds", all(r[4] for r in rows), f"LEDs of LPF, HPF, BPF equal the hardware key's: {[r[4] for r in rows]}"))
    out.append(entry("filter_toggle_twin_window", all(r[5] for r in rows) and all("FILTER TYPE" in " ".join(r[8]) or r[2] == 0 for r in rows),
                     f"the texts drawn equal the hardware key's: {[r[5] for r in rows]}; drawn {[r[8] for r in rows][:3]}"))
    out.append(entry("filter_toggle_twin_message", all(r[6] for r in rows), f"the firmware's parameter message equals the hardware key's: {[r[6] for r in rows]}"))
    out.append(entry("filter_toggle_twin_frame", all(r[7] for r in rows), f"the frame equals the hardware key's: {[r[7] for r in rows]}"))

    def stock(box):
        """From MS20 LPF two presses of SHIFT + LPF, then the same with the plain key."""
        part = box.selected()
        box.set_ftype(part, 2)
        shifted = [box.shift_key(FILTER_KEYS["lpf"])[0] for _ in range(2)]
        box.set_ftype(part, 2)
        plain = []
        for _ in range(2):
            box.dev.press(FILTER_KEYS["lpf"], 0.4)
            plain.append(box.ftype(part))
        return shifted, plain

    toggle.m.uc.mem_write(FILTER_TOGGLE_ON, (0).to_bytes(4, "little"))
    off = stock(toggle)
    killed = FTBox(payload, flash, held=KILL)
    kill = stock(killed)
    out.append(entry("filter_toggle_off_and_kill_are_stock", off[0] == off[1] and kill[0] == kill[1] and off[0] != [0, 2]
                     and not toggle.m.asserts and not killed.m.asserts,
                     f"from MS20 LPF, SHIFT + LPF twice and LPF twice: FILTER TOGGLE OFF {off}, EXIT held at power-on {kill} "
                     f"(the same both ways, the firmware's steps)"))
    return out


GROUPS = (case_save, case_reset, case_reset_modes, case_reset_voice, case_reset_dsp, case_meter_dsp, case_voices_dsp, case_kill, case_unsaved, case_pad_state, case_key_pads, case_filter_toggle)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own device, so they can run side by side."""
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.load_gate()
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
