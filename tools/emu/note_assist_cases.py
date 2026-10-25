# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the note assistant patch (tools/patch/note_assist.py, docs/messungen/2026-10-15-note-assistant.md).

check.py runs `cases` on every patched copy that carries the patch's hooks. In KEYBOARD mode, right after a pad note (the next tick of the
LED manager) the pads of the notes that fit show a dim pink, the pad's red and blue LED together, the better the fit the brighter (unison and
fifth, then thirds, fourth and a step of the scale, then sixths); stopped they stay, while the pattern plays they fade, the dim ones first;
the pads of the layout are the pattern's own key and scale already. The firmware's own pad lighting wins, and outside KEYBOARD mode and
the main screen the pads are the firmware's. With EXIT held at power-on, without a card or with the setting off the firmware is exactly as
it was; the reference for "as it was" is the same copy with EXIT held at power-on (no hook of the patch does anything then).

What the panel shows is what the firmware last sent it (`Machine.leds`, set by every `00 LED brightness` message), so every check
reads the LEDs the way the panel would.

    tools/emu/.venv/bin/python tools/emu/note_assist_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import note_assist as spec  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from pswitch_cases import Box  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
PATTERN_PTR = 0xC033E6A4
LED_MANAGER_PTR = 0xC0345A1C
SET_KEY, SET_SCALE = 0xC004A6FC, 0xC004A77C        # (pattern, value, notify): the setters the Pattern menu calls
KEYS = {"rec": 0x00, "stop": 0x01, "play": 0x02, "menu": 0x09, "exit": 0x0D, "part_right": 0x0F, "part_left": 0x0B, "trigger": 0x13, "sequencer": 0x15,
        "keyboard": 0x17, "chord": 0x18, "step_jump": 0x19, "pattern_set": 0x1B, "bar1": 0x1C, "bar4": 0x1F}
KILL = spec.KILL_SWITCH
DELAY_S = 1.8                                       # a wait between two steps of a case; stopped, the hints stay (device wish 19.10.)


def is_hint(pair):
    """A pad holds the patch's values: an odd red other than 255 (the firmware writes 0, 192, 255 or twice a velocity) and 5/8 of it in blue, odd."""
    red, blue = pair
    return red % 2 == 1 and red != 255 and blue == ((red * 5) >> 3) | 1
PART_BLUE = 255                                     # what the firmware lights on the pad of the selected part
STEP_BASE = 0x800 + 0x30 + 4                        # part 0, step 0 in the pattern object; 12 bytes a step: on, gate, velocity, trigger, 4 notes
# the notes of each scale over its root, music theory (the same as src/dice.mjs knows), to check that the pads are in the key and scale
SCALES = {0: range(12), 1: (0, 2, 4, 5, 7, 9, 11), 2: (0, 2, 3, 5, 7, 9, 10), 6: (0, 2, 3, 5, 7, 8, 10), 14: (0, 2, 4, 7, 9), 15: (0, 3, 5, 7, 10)}
NAMES = {0: "Chromatic", 1: "Ionian", 2: "Dorian", 6: "Aeolian", 14: "Major Penta", 15: "minor Penta"}


def for_build(payload):
    """Put the patch module's places to the build of this image (the synth has its own addresses, data/synth-map/).
    The cases name the firmware's places by their Sampler address (PATTERN_PTR, LED_MANAGER_PTR, SET_KEY, SET_SCALE, the LED send function);
    Dev translates them for the synth (dev.a), so only the module's own constants are put here."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hooks(payload):
    """True when the end of the LED manager's tick branches into the patch's code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.TICK_HOOK - IMAGE)[0]
    return word >> 24 == 0xEA and spec.CODE_AT <= spec.TICK_HOOK + 8 + ((word & 0xFFFFFF) << 2) < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"noteassist:{name}", "ok": bool(ok), "detail": str(detail)}


class NBox(Box):
    """A booted device (card mounted unless asked otherwise) with the helpers of these cases. On mains power: on battery power save
    dims every LED to a quarter (pad-colors, menu_cases checks it), and these cases look at the pads' own values."""

    def __init__(self, payload, flash=None, held=0, card=True, seconds=3.0):
        for_build(payload)
        if not synthaddr.is_synth(payload):
            super().__init__(payload, flash, held, card, seconds, adapter=True)
            return
        # the synth: no sample bank and no flash dump of its own (the dump is the Sampler's). Box's tweaks of the pattern length and chain mode
        # write Sampler RAM addresses, so they are left out; the cases here need a pattern only for part 5's step, which they write themselves.
        self.payload = bytes(payload)
        self.dev = Dev(self.payload, None, held, adapter=True)
        self.m = self.dev.m
        if card:
            self.m.insert_card(SDCard(MemoryMedium(bytearray(self.card_image()))))
        self.dev.run(seconds)
        self.marks = {}

    @staticmethod
    def card_image():
        from pswitch_cases import card_image
        return card_image()

    def key(self, name, wait=0.3):
        self.dev.press(KEYS[name], wait)

    def leds(self):
        """{pad: (red, blue)} of the pads that are not dark, as the panel last got them."""
        out = {}
        for n in range(16):
            red, blue = self.m.leds.get(0x2C + 2 * n, 0), self.m.leds.get(0x2D + 2 * n, 0)
            if red or blue:
                out[n] = (red, blue)
        return out

    def hinted(self):
        return sorted(n for n, v in self.leds().items() if is_hint(v))

    def levels(self):
        """{pad: the red of its hint}."""
        return {n: v[0] for n, v in self.leds().items() if is_hint(v)}

    def stable_levels(self):
        """levels() once two looks 10 ms apart agree: a pad's red and blue go out as two messages, a look between them sees neither."""
        now = self.levels()
        for _ in range(5):
            self.run(0.01)
            again = self.levels()
            if again == now:
                return now
            now = again
        return now

    def others(self):
        """The pads that hold something but not the patch's values."""
        return {n: v for n, v in self.leds().items() if not is_hint(v)}

    def forget(self):
        """Ends the hints the way a user does when stopped: another pad mode and back."""
        self.key("trigger", 0.2)
        self.key("keyboard", 0.3)

    def pad_down(self, n, velocity=100, wait=0.15):
        self.m.send([4, n, 0, velocity, 1])
        self.run(wait)

    def pad_up(self, n, wait=0.2):
        self.m.send([4, n, 0, 0, 0])
        self.run(wait)

    def tap_pad(self, n, hold=0.1, wait=0.2):
        self.pad_down(n, wait=hold)
        self.pad_up(n, wait=wait)

    def pattern(self):
        return self.u32(PATTERN_PTR)

    def set_scale(self, key, scale):
        """The key and the scale as the Pattern menu sets them: through the firmware's setters, which build the layout again."""
        self.dev.call(SET_KEY, self.pattern(), key, 0)
        self.dev.call(SET_SCALE, self.pattern(), scale, 0)
        self.run(0.3)

    def manager(self):
        return self.u32(LED_MANAGER_PTR)

    def state(self, offset):
        return self.u32(spec.STATE + offset)

    def clear_steps(self, part=0):
        base = self.pattern() + STEP_BASE + 0x330 * part
        self.m.uc.mem_write(base, bytes(12 * 64))

    def layout(self):
        """The note of each pad, from the MIDI out of the firmware (only the firmware's own, no hook needed)."""
        notes = []
        for n in range(16):
            self.mark("l")
            self.pad_down(n, wait=0.1)
            on = [d[0] for st, d in self.midi("l") if st & 0xF0 == 0x90]
            self.pad_up(n, wait=0.1)
            notes.append(on[0] if on else None)
        return notes

    def wait_hints(self, limit=3.0):
        """Waits (in steps of 10 ms) for the first hint; returns the seconds, None when none comes."""
        t = 0.0
        while t < limit:
            if self.hinted():
                return round(t, 2)
            self.run(0.01)
            t += 0.01
        return None


_layouts = {}


def layout_of(payload, flash, key, scale):
    """The 16 notes of the keyboard for a key and scale, measured with the patch off (EXIT held at power-on), so it is the firmware's alone."""
    if (key, scale) not in _layouts:
        box = NBox(payload, flash, KILL)
        box.dev.press(KEYS["keyboard"], 0.4)
        box.set_scale(key, scale)
        _layouts[(key, scale)] = box.layout()
    return _layouts[(key, scale)]


def place(pad):
    """The pad's place in the firmware's table of the layout: pads 0 to 7 are places 8 to 15, pads 8 to 15 places 0 to 7."""
    return pad + 8 if pad <= 7 else pad - 8


def want_levels(layout, pad):
    """{pad: level} after a note on `pad`: by the interval (spec.LEVELS), and the notes a step of the scale away (the neighbours in the
    table) at least the middle level."""
    note = layout[pad]
    out = {p: spec.LEVELS[(n - note) % 12] for p, n in enumerate(layout) if n is not None}
    for p in range(16):
        if abs(place(p) - place(pad)) == 1:
            out[p] = max(out[p], spec.LEVEL_MID)
    return {p: v for p, v in out.items() if v}


def fitting(layout, pad, skip=()):
    """The pads that should show a hint after `pad`. The pad of the selected part is one of them like any other."""
    return sorted(p for p in want_levels(layout, pad) if p not in skip)


# ---------------------------------------------------------------------------------------- the cases
SOON = 0.15          # seconds after a pad went down by which the hints are there: the next 40 ms tick and the LED messages


def case_layout_and_hints(payload, flash):
    """For a few keys and scales: the pads are notes of the key and the scale; right after a note the pads that fit show the pair of values, the rest stays dark."""
    out = []
    bad_layout, bad_hints, bad_dark, bad_levels, seen = [], [], [], [], []
    for key, scale, pads in ((0, 2, (3, 12)), (3, 14, (1, 9)), (0, 0, (5,)), (7, 1, (10,)), (5, 15, (8,)), (9, 6, (2, 14))):
        layout = layout_of(payload, flash, key, scale)
        box = NBox(payload, flash)
        box.key("keyboard", 0.4)
        box.set_scale(key, scale)
        in_scale = {(key + i) % 12 for i in SCALES[scale]}
        if any(n is None or n % 12 not in in_scale for n in layout):
            bad_layout.append((key, scale, layout))
        for pad in pads:
            box.tap_pad(pad, hold=0.1, wait=0.1)
            got = box.hinted()
            levels = box.levels()
            if levels != {p: v for p, v in want_levels(layout, pad).items() if p in got}:
                bad_levels.append((key, scale, pad, levels, want_levels(layout, pad)))
            # the pads of the played note (the same note on another pad) are the firmware's red while the note sounds; after the 0.1 s hold they are dark again
            want = fitting(layout, pad)
            dark = {n for n in range(16) if n not in got and n not in box.leds()}
            if got != want:
                bad_hints.append((key, scale, pad, got, want))
            if box.others() != {}:
                bad_dark.append((key, scale, pad, box.others()))
            seen.append((NAMES[scale], key, pad, layout[pad], got))
            if len(dark) != 16 - len(got):
                bad_dark.append((key, scale, pad, "dark pads", sorted(dark)))
    out.append(entry("layout_is_the_key_and_scale", not bad_layout, f"the 16 pad notes of the firmware's layout are notes of the pattern's key and scale in every case tried ({len(seen)} runs), so the interval rule alone filters; wrong: {bad_layout}"))
    out.append(entry("fitting_pads_show_the_hint", not bad_hints, f"{len(seen)} runs over six keys and scales, 0.2 s after the note: the lit pads are the ones the played note's MIDI note and the layout the firmware sent give (0, 3, 4, 5, 7, 8, 9 semitones, and a step of the scale); wrong: {bad_hints}; (scale, key, pad, note, lit pads): {seen}"))
    out.append(entry("levels_by_fit", not bad_levels, f"the brightness of each hint by its interval ({spec.LEVELS}), a step of the scale at least {spec.LEVEL_MID}; wrong: {bad_levels}"))
    out.append(entry("other_pads_stay_dark", not bad_dark, f"every other pad is dark, the part's pad (pad 0) included, which shows the hint or is dark like the rest; wrong: {bad_dark}"))
    return out


def case_timing(payload, flash):
    """The hints come with the next tick. Stopped they stay; while the pattern plays they fade, the dim ones first, and when the last is
    gone the part's pad has the firmware's blue again; paused they stay where they are (device wish 19.10.)."""
    layout = layout_of(payload, flash, 0, 2)
    want = want_levels(layout, 3)
    box = NBox(payload, flash)
    live = box.u32(0xC033E6A4) + 4
    for part in range(16):                     # no steps: notes the pattern plays would light keyboard pads of their own
        box.m.uc.mem_write(live + 0x800 + 0x330 * part + 0x30, bytes(12 * 64))
    box.key("keyboard", 0.4)
    t0 = box.m.time_ns
    box.pad_down(3, wait=0.0)
    first = box.wait_hints(1.0)
    appeared = round((box.m.time_ns - t0) / 1e9, 3) if first is not None else None
    box.pad_up(3, wait=0.3)
    box.run(4.0)
    stopped = box.levels()
    box.key("play", 0.0)
    t1 = box.m.time_ns
    gone, paused = {}, None
    while (box.m.time_ns - t1) / 1e9 < 6.0 and len(gone) < len(want):
        box.run(0.04)
        now = box.stable_levels()
        for p in want:
            if p not in now and p not in gone:
                gone[p] = round((box.m.time_ns - t1) / 1e9, 2)
        if paused is None and (box.m.time_ns - t1) / 1e9 >= 0.6:
            box.key("play", 0.0)               # pause
            box.run(0.05)
            before = box.stable_levels()
            box.run(1.0)
            paused = (before, box.stable_levels())
            box.key("play", 0.0)
    part = box.leds().get(0)
    order = [min(t for p, t in gone.items() if want[p] == lv) for lv in sorted(set(want.values())) if any(want[p] == lv for p in gone)]
    return [entry("hints_come_with_the_next_tick", appeared is not None and appeared <= 0.1, f"the first hint {appeared} s after the pad went down (one tick of the LED manager is 0.04 s)"),
            entry("stopped_hints_stay", stopped == {p: v for p, v in want.items() if p != 3} | ({3: want[3]} if 3 in want else {}),
                  f"stopped, 4 s after the note: {stopped}, want {want}"),
            entry("paused_hints_stay", paused is not None and paused[0] == paused[1] and paused[0], f"paused 1 s: {paused}"),
            entry("playing_hints_fade_dim_first", len(gone) == len(want) and len(order) >= 3 and all(x < y for x, y in zip(order, order[1:])) and order[-1] <= 5.0,
                  f"playing (with a pause of 1 s at 0.6 s): the first pad gone of each level, dimmest first, at {order} s; every pad {gone}"),
            entry("part_blue_comes_back_when_the_hints_end", part == (0, PART_BLUE) and not box.m.asserts,
                  f"the pad of the selected part (pad 0) holds {part} once the last hint is gone")]


def case_new_note(payload, flash):
    """A new pad note replaces the hints at once with the new note's; stopped, they stay."""
    layout = layout_of(payload, flash, 0, 2)
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    box.tap_pad(3, hold=0.1, wait=0.1)
    first = box.hinted()
    box.run(1.0)
    still = box.hinted()
    box.pad_down(12, wait=SOON)
    down = box.leds()
    second = box.hinted()
    box.pad_up(12, wait=0.1)
    box.run(2.0)
    later = box.hinted()
    return [entry("new_note_replaces_the_hints", first == fitting(layout, 3) and still == first and second == fitting(layout, 12, skip=(12,)) and second != first and down.get(12) == (192, 0),
                  f"hints for pad 3 {first}, still {still} a second later; a new note on pad 12 (note {layout[12]}): {SOON} s later {second} (pad 12 itself is the firmware's {down.get(12)})"),
            entry("new_note_hints_stay", later == fitting(layout, 12), f"2 s after the second note, stopped: {later}")]


def case_firmware_wins(payload, flash):
    """The pressed pad and the pads of its note keep the firmware's red, the blue of the part stays, the sequencer's own pad light wins."""
    out = []
    layout = layout_of(payload, flash, 0, 2)
    # 1. a pad that is held keeps the firmware's value while the hints show around it, and gets the hint when it is let go
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    box.pad_down(3, wait=SOON + 0.1)
    held = box.leds()
    others_hinted = box.hinted()
    box.pad_up(3, wait=0.2)
    after = box.leds()
    box.forget()
    out.append(entry("held_pad_keeps_the_firmwares_light", held.get(3) == (192, 0) and 3 not in others_hinted and others_hinted == [p for p in fitting(layout, 3) if p != 3]
                     and (is_hint(held[0]) if 0 in fitting(layout, 3) else held.get(0) is None) and is_hint(after.get(3, (0, 0))) and box.hinted() == [] and box.leds().get(0) == (0, PART_BLUE),
                     f"a pad held: pad 3 {held.get(3)} (the firmware's red), the part's pad {held.get(0)} (a hint when its note fits), hints on the others {others_hinted}; let go, pad 3 {after.get(3)}; after another mode and back {box.hinted()}, the part's pad {box.leds().get(0)}"))
    # 2. the pad of the selected part is a pad like any other while the hints show: its hint when its note fits, dark when not, the
    #    firmware's blue 255 again when they end
    part_pad = 3
    fits_pad = next(p for p in range(16) if p != part_pad and part_pad in fitting(layout, p))
    dark_pad = next(p for p in range(16) if p != part_pad and part_pad not in fitting(layout, p))
    rows = {}
    for label, played in (("fits", fits_pad), ("does_not_fit", dark_pad)):
        box = NBox(payload, flash)
        box.key("keyboard", 0.4)
        for _ in range(3):
            box.key("part_right", 0.3)
        box.tap_pad(played, hold=0.1, wait=0.1)
        shown = box.leds().get(part_pad)
        want = fitting(layout, played)
        hints = box.hinted()
        box.forget()
        rows[label] = (played, shown, hints == want, box.leds().get(part_pad), box.m.asserts)
    out.append(entry("blue_of_the_part_is_a_pad_like_any_other", rows["fits"][1] is not None and is_hint(rows["fits"][1]) and rows["fits"][2] and rows["does_not_fit"][1] is None and rows["does_not_fit"][2],
                     f"part 4 selected (pad {part_pad}): after pad {rows['fits'][0]}, whose note fits it, the pad holds {rows['fits'][1]} (the hint); after pad {rows['does_not_fit'][0]}, whose note does not, it is dark ({rows['does_not_fit'][1]}); the other pads are the fitting ones as always"))
    out.append(entry("blue_of_the_part_comes_back", all(r[3] == (0, PART_BLUE) and not r[4] for r in rows.values()),
                     f"when the hints end the firmware's blue 255 is back on the part's pad, hint or dark before: {[(k, r[3]) for k, r in rows.items()]}"))
    # why the patch has to give the blue back: the firmware does not light it again by itself (measured with the patch off, EXIT held at power-on)
    box = NBox(payload, flash, KILL)
    box.key("keyboard", 0.5)
    mgr, led = box.manager(), 0x2D
    for offset in (0x4E, 0x4E + 0x2C0):
        box.m.uc.mem_write(mgr + offset + 8 * led, b"\x00")
    box.dev.call(0xC00875F4, mgr, led, 1)
    box.run(4.0)
    out.append(entry("firmware_does_not_redraw_the_part_blue", box.leds().get(0) is None and not box.m.asserts,
                     f"patch off, the blue of the part's pad set dark through the LED manager's tables and send function: four seconds later the pad holds {box.leds().get(0)} (the firmware never lights it again)"))
    # the part changes while the hints show: the new part's pad is a pad like any other, the old one ends dark, no stale blue is written
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    for _ in range(3):
        box.key("part_right", 0.3)
    box.tap_pad(dark_pad, hold=0.1, wait=0.1)
    box.key("part_right", 0.3)
    during = box.leds()
    box.forget()
    after = box.leds()
    out.append(entry("part_change_leaves_no_stale_blue", after.get(4) == (0, PART_BLUE) and after.get(3) is None and not box.m.asserts,
                     f"part 4 to 5 while the hints show: pads 3 and 4 then {during.get(3)}, {during.get(4)}; when the hints end pad 3 {after.get(3)}, pad 4 {after.get(4)} (the firmware's blue on the new part's pad only)"))
    # 3. a note of the sequencer: part 5 of the factory pattern plays the note 63 on its first step, the firmware lights the pad of that note,
    #    which the patch would have hinted (pad 0 is the note 60, 63 is a minor third up). PLAY comes while the hints last.
    box = NBox(payload, flash)
    # an empty flash holds Init patterns without a note: step 1 of part 5 gets the note 63 (block offset 0x800 + 4 * 0x330 + 0x30: on, gate,
    # velocity, trigger, note), as it has in the factory pattern; the live pattern's block starts 4 bytes behind its pointer
    first_step = box.u32(0xC033E6A4) + 4 + 0x800 + 4 * 0x330 + 0x30
    if not box.dev.read(first_step, 1)[0]:
        box.m.uc.mem_write(first_step, bytes([1, 0xFF, 0x60, 1, 0x40]))
    box.key("keyboard", 0.4)
    for _ in range(4):
        box.key("part_right", 0.3)
    box.tap_pad(0, hold=0.1, wait=0.1)
    before = box.hinted()
    box.key("play", 0.0)
    flashed, seen_flash, t = None, False, 0.0
    while t < 1.0 and not seen_flash:
        box.run(0.01)
        t += 0.01
        leds = box.leds()
        if leds.get(2) == (192, 0):
            seen_flash, flashed = True, dict(leds)
    held = None
    for _ in range(60):
        box.run(0.01)
        if box.leds().get(2) == (spec.PLAY_RED, 0):
            held = box.leds().get(2)
            break
    kept = []                      # the rest of the step and the gap behind it: the pad stays lit (only step 1 holds a note)
    for _ in range(40):
        box.run(0.01)
        kept.append(box.leds().get(2))
    box.key("stop", 0.5)
    back = box.leds().get(2)
    after_seq = box.hinted()
    out.append(entry("sequencer_light_wins", before == fitting(layout, 0) and 2 in before and seen_flash and flashed.get(2) == (192, 0)
                     and held is not None and all(v == (spec.PLAY_RED, 0) for v in kept) and back is not None and is_hint(back),
                     f"part 5 selected, hints for pad 0 {before} (pad 2, the note 63, is one of them); then the sequencer plays that note: pad 2 {flashed.get(2) if flashed else None} (the firmware's light, not the hint), "
                     f"after the note it keeps the patch's red {held} for the next 0.4 s ({sorted(set(kept), key=str)}), and stopped the hint is back ({back})"))
    # 4. the note of the sequencer gives the hints itself (device 18.10.): no pad pressed, PLAY, the hints are those of pad 2 (the note 63)
    seq = NBox(payload, flash)
    if not seq.dev.read(first_step, 1)[0]:
        seq.m.uc.mem_write(first_step, bytes([1, 0xFF, 0x60, 1, 0x40]))
    seq.key("keyboard", 0.4)
    for _ in range(4):
        seq.key("part_right", 0.3)
    quiet = seq.hinted()
    seq.key("play", 0.0)
    seq.run(0.6)
    shown = seq.hinted()
    played = seq.leds().get(2)
    seq.key("stop", 0.5)
    out.append(entry("sequencer_note_shows_hints", not quiet and shown == fitting(layout, 2, skip=(2,)) and played == (spec.PLAY_RED, 0)
                     and after_seq and set(after_seq) <= set(fitting(layout, 2)) and not seq.m.asserts,
                     f"before PLAY {quiet}, 0.6 s after PLAY {shown} (want those of pad 2, the note 63: {fitting(layout, 2)}, pad 2 itself the note that "
                     f"played: {played}); after the pad note and the sequencer's note {after_seq}"))
    # 5. a second note takes the red over (device wish 22.10.): step 1 the note 63 (pad 2), step 5 another note of the layout
    two = NBox(payload, flash)
    other = next(p for p in range(16) if p != 2 and layout[p] is not None and layout[p] != layout[2])
    if not two.dev.read(first_step, 1)[0]:
        two.m.uc.mem_write(first_step, bytes([1, 0xFF, 0x60, 1, 0x40]))
    two.m.uc.mem_write(first_step + 4 * 12, bytes([1, 0x30, 0x60, 1, layout[other] + 1, 0, 0, 0]))   # a step holds the note + 1 (0 is empty)
    two.key("keyboard", 0.4)
    for _ in range(4):
        two.key("part_right", 0.3)
    two.key("play", 0.0)
    # When the steps play follows the tempo of the pattern in the flash, so the pads are read every 20 ms for 1.6 s and only the order counts.
    red = (spec.PLAY_RED, 0)
    seen = []
    for _ in range(80):
        two.run(0.02)
        now = (two.leds().get(2) == red, two.leds().get(other) == red)
        if not seen or seen[-1] != now:
            seen.append(now)
    first = seen.index((True, False)) if (True, False) in seen else None
    taken = first is not None and (False, True) in seen[first:]
    two.key("stop", 0.5)
    stopped = (two.leds().get(2), two.leds().get(other))
    out.append(entry("next_note_takes_the_red", taken and red not in stopped and not two.m.asserts,
                     f"pad 2 (the note 63, step 1) and pad {other} (the note {layout[other]}, step 5) red, in the order seen: {seen}; stopped: {stopped}"))
    return out


def case_modes(payload, flash):
    """Nothing outside KEYBOARD mode and the main screen: not in the other pad modes, not in the menu, not after an octave shift."""
    out = []
    layout = layout_of(payload, flash, 0, 2)
    count = len(fitting(layout, 3))
    rows = {}
    for label, mode in (("sequencer", "sequencer"), ("trigger", "trigger"), ("chord", "chord"), ("step_jump", "step_jump"), ("pattern_set", "pattern_set")):
        box = NBox(payload, flash)
        box.key("keyboard", 0.4)
        box.tap_pad(3, hold=0.05, wait=0.0)
        box.key(mode, 0.1)
        box.run(0.3)
        in_mode = box.hinted()
        box.run(DELAY_S)
        box.key("keyboard", 0.2)
        box.run(DELAY_S + 0.5)
        rows[label] = (in_mode, box.hinted())
    out.append(entry("no_hint_in_other_pad_modes", all(v == ([], []) for v in rows.values()),
                     f"a pad played in KEYBOARD, then the mode changed within 0.15 s: no hint in that mode and none when KEYBOARD is back (the note is forgotten): {rows}"))
    rows = {}
    for label, mode in (("sequencer", "sequencer"), ("trigger", "trigger"), ("chord", "chord"), ("step_jump", "step_jump")):
        box = NBox(payload, flash)
        box.key("keyboard", 0.4)
        box.tap_pad(3, hold=0.1, wait=0.1)
        shown = len(box.hinted())
        box.key(mode, 0.1)
        gone = box.hinted()
        part_in_mode = box.leds().get(0)
        box.run(DELAY_S)
        box.key("keyboard", 0.2)
        box.run(DELAY_S + 0.5)
        rows[label] = (shown, gone, box.hinted(), part_in_mode, box.leds().get(0))
    out.append(entry("hints_go_when_the_mode_changes", all(v[0] == count and v[1] == [] and v[2] == [] for v in rows.values()),
                     f"hints shown, the mode changed: gone within 0.1 s and not back with KEYBOARD (shown, left, after returning): {rows}"))
    out.append(entry("part_blue_back_when_the_mode_changes", all(v[3] is not None and v[3][1] == PART_BLUE and v[4] == (0, PART_BLUE) for v in rows.values()),
                     f"the part's pad holds the blue 255 right after the mode changed (the firmware's own light in that mode, the sequencer's step LED adds red) and the firmware's blue after KEYBOARD is back: {[(k, v[3], v[4]) for k, v in rows.items()]}"))
    box = NBox(payload, flash)
    for mode in ("trigger", "sequencer", "chord"):
        box.key(mode, 0.3)
        box.tap_pad(5, wait=0.3)
    box.key("keyboard", 0.3)
    box.run(DELAY_S + 1.0)
    out.append(entry("pads_in_other_modes_leave_nothing", box.hinted() == [], f"pads pressed in TRIGGER, SEQUENCER and CHORD, then KEYBOARD: hints {box.hinted()}"))
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    box.tap_pad(3, hold=0.1, wait=0.05)
    shown = len(box.hinted())
    box.key("menu", 0.3)
    in_menu = box.hinted()
    screen = box.dev.screen()["number"]
    box.key("exit", 0.4)
    back = box.dev.screen()["number"]
    box.run(DELAY_S + 1.0)
    out.append(entry("no_hint_in_the_menu", shown == count and in_menu == [] and screen != 1 and back == 1 and box.hinted() == [] and box.leds().get(0) == (0, PART_BLUE),
                     f"hints shown ({shown}), MENU (screen {screen}): hints {in_menu}; EXIT (screen {back}): hints {box.hinted()} until a new note, the part's pad {box.leds().get(0)}"))
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    box.tap_pad(3, hold=0.1, wait=0.05)
    shown = len(box.hinted())
    box.key("bar4", 0.3)
    after_octave = box.hinted()
    box.run(DELAY_S + 1.0)
    later = box.hinted()
    box.tap_pad(3, hold=0.1, wait=0.1)
    again = box.hinted()
    out.append(entry("octave_shift_ends_the_hints", shown == count and after_octave == [] and later == [] and len(again) == count and (box.leds().get(0) is None or is_hint(box.leds()[0])),
                     f"shown {shown}, BAR 4 (an octave up): {after_octave}, later {later}; the next note brings them back {again}"))
    return out


def case_stock(payload, flash):
    """EXIT held at power-on, no card, the setting off: the patch does nothing, the pads are the firmware's; the setting off at run time gives the LEDs back."""
    out = []
    count = len(fitting(layout_of(payload, flash, 0, 2), 3))
    rows = {}
    makers = {
        "exit_held": lambda: NBox(payload, flash, KILL),
        "no_card": lambda: NBox(payload, flash, card=False),
        "setting_off": lambda: _setting_off(payload, flash),
    }
    for name, make in makers.items():
        box = make()
        box.key("keyboard", 0.4)
        values, hints = set(), []
        for pad in (3, 9, 12):
            box.pad_down(pad)
            values |= {v for pair in box.leds().values() for v in pair}
            box.pad_up(pad, wait=0.3)
            hints += box.hinted()
            values |= {v for pair in box.leds().values() for v in pair}
            box.run(DELAY_S + 0.3)
        rows[name] = (sorted(values), hints, [box.state(o) for o in (spec.S_SINCE, spec.S_NOTE, spec.S_PAD)], box.m.asserts)
    untouched = [0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]
    out.append(entry("stock_without_the_patch", all(r[0] == [0, 192, 255] and r[1] == [] and not r[3] for r in rows.values()) and rows["exit_held"][2] == untouched and rows["no_card"][2] == untouched,
                     f"three notes each (values of the pad LEDs, hints, state words, assertions): {rows}; with EXIT held or without a card the patch does not write its state either"))
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    box.tap_pad(3, hold=0.1, wait=0.1)
    shown = len(box.hinted())
    box.m.uc.mem_write(spec.NA_SETTING, struct.pack("<I", 0))
    box.run(0.3)
    gone = box.hinted()
    box.run(DELAY_S)
    box.tap_pad(3, hold=0.1, wait=0.1)
    off_again = box.hinted()
    out.append(entry("setting_off_gives_the_leds_back", shown == count and gone == [] and off_again == [] and not box.m.asserts and box.leds().get(0) == (0, PART_BLUE),
                     f"{shown} hints shown, the setting word set to 0: {gone} within 0.3 s, and no hint after a new note {off_again}; the part's pad {box.leds().get(0)}"))
    box.m.uc.mem_write(spec.NA_SETTING, struct.pack("<I", 1))
    box.run(DELAY_S)
    box.tap_pad(3, hold=0.1, wait=0.1)
    out.append(entry("setting_on_again", len(box.hinted()) == count, f"set to 1: the next note shows {len(box.hinted())} hints"))
    return out


def _setting_off(payload, flash):
    box = NBox(payload, flash)
    box.m.uc.mem_write(spec.NA_SETTING, struct.pack("<I", 0))
    box.run(0.1)
    return box


def case_values(payload, flash):
    """What the firmware itself writes to the pad LEDs: 0, 192, 255, or twice a velocity with Pad Velocity on. The patch's two values are odd and not 255, so the patch tells its own from them."""
    rows = {}
    for label, pad_velocity in (("pad velocity off", 0), ("pad velocity on", 1)):
        box = NBox(payload, flash, KILL)
        for part in range(16):                          # the pads of TRIGGER mode select parts, so every part gets the setting
            box.m.uc.mem_write(box.pattern() + 0x808 + 0x330 * part, bytes([pad_velocity]))
        values = set()
        box.m.panel_log.clear()
        for mode in ("trigger", "sequencer", "keyboard", "chord", "step_jump", "pattern_set"):
            box.key(mode, 0.3)
            for pad, velocity in ((1, 5), (6, 40), (11, 90), (14, 127)):
                box.pad_down(pad, velocity=velocity, wait=0.15)
                box.pad_up(pad, wait=0.15)
                box.key("play", 0.0)
                box.run(0.4)
                box.key("stop", 0.2)
            values |= {m[2] for m in box.m.panel_log if m[0] == 0 and 0x2C <= m[1] <= 0x4B}
            box.m.panel_log.clear()
        rows[label] = sorted(values)
    every = set(rows["pad velocity off"]) | set(rows["pad velocity on"])
    graded = sorted(v for v in rows["pad velocity on"] if v not in (0, 192, 255))
    return [entry("firmware_pad_values", set(rows["pad velocity off"]) == {0, 192, 255} and len(graded) >= 3 and all(v % 2 == 0 or v == 255 for v in every),
                  f"values the firmware sent to the pad LEDs over all six pad modes, playing and not: {rows}; with Pad Velocity on the pad light follows the hit (graded values {graded}), "
                  f"so the pad LEDs take intermediate values in the protocol; the patch's values are odd and not 255 ({spec.LEVELS}), never among them")]


def case_lock(payload, flash):
    """A plugin that holds the LED lock keeps the pads: the patch writes nothing while the lock is held."""
    box = NBox(payload, flash)
    box.key("keyboard", 0.4)
    box.m.uc.mem_write(box.manager() + 0xB98, bytes([1]))
    box.m.panel_log.clear()
    box.tap_pad(3, hold=0.1, wait=0.1)
    held = box.hinted()
    written = [m for m in box.m.panel_log if m[0] == 0 and 0x2C <= m[1] <= 0x4B and m[2] % 2 == 1 and m[2] != 255]
    box.m.uc.mem_write(box.manager() + 0xB98, bytes([0]))
    box.run(0.3)
    count = len(fitting(layout_of(payload, flash, 0, 2), 3))
    return [entry("led_lock_keeps_the_pads", held == [] and written == [] and len(box.hinted()) == count,
                  f"lock held while the note plays: hints {held}, LED messages with the patch's values {len(written)}; lock let go: {len(box.hinted())} hints")]


def chord_roots(payload, flash, key, scale):
    """The lowest note of each pad's chord in CHORD mode, from the MIDI out of the firmware (patch off)."""
    box = NBox(payload, flash, KILL)
    box.key("keyboard", 0.4)
    box.set_scale(key, scale)
    box.key("chord", 0.4)
    roots = []
    for n in range(16):
        box.mark("c")
        box.pad_down(n, wait=0.1)
        on = sorted(d[0] for st, d in box.midi("c") if st & 0xF0 == 0x90)
        box.pad_up(n, wait=0.1)
        roots.append(on[0] if on else None)
    return roots


def case_chord(payload, flash):
    """CHORD mode with a scale of seven notes: after a chord the pads of the chords that follow well light up, brighter for the
    better (spec.CHORD_LEVELS by the interval of the roots); with a pentatonic scale nothing (the firmware's chords of it are not
    the keyboard's scale)."""
    out = []
    for key, scale, pad in ((0, 2, 9), (9, 6, 12)):
        roots = chord_roots(payload, flash, key, scale)
        want = {p: spec.CHORD_LEVELS[(r - roots[pad]) % 12] for p, r in enumerate(roots) if r is not None}
        want = {p: v for p, v in want.items() if v}
        box = NBox(payload, flash)
        box.key("keyboard", 0.4)
        box.set_scale(key, scale)
        box.key("chord", 0.4)
        box.pad_down(pad, wait=0.2)
        held = box.levels()
        box.pad_up(pad, wait=0.2)
        after = box.levels()
        out.append(entry(f"chord_hints_{NAMES[scale].lower()}", held == {p: v for p, v in want.items() if p != pad} and after == want and not box.m.asserts,
                         f"{NAMES[scale]} on {key}, pad {pad + 1} (root {roots[pad]}): while held {held}, after {after}, want {want}"))
    penta = NBox(payload, flash)
    penta.key("keyboard", 0.4)
    penta.set_scale(0, 14)
    penta.key("chord", 0.4)
    penta.tap_pad(9, hold=0.2, wait=0.2)
    out.append(entry("chord_pentatonic_none", penta.hinted() == [] and not penta.m.asserts, f"Major Penta: hints {penta.hinted()}"))
    return out


GROUPS = (case_chord, case_layout_and_hints, case_timing, case_new_note, case_firmware_wins, case_modes, case_stock, case_values, case_lock)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own devices, so they can run side by side."""
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
