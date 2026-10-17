# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the dice patch (tools/patch/dice.py, docs/messungen/2026-10-16-wuerfeln.md).

check.py runs `cases` on every patched copy that carries the patch's hook. SHIFT + PART ERASE on the main screen writes a new melody into the
selected part: notes of the pattern's key and scale, rests and notes on the 16th grid, within the pattern's length and the part's LAST STEP.
Only that part's step records change, nothing else of the pattern, nothing in flash; the pad LEDs follow; the part plays what was written. Every
other key, and the same combination with the setting off, with EXIT held at power-on or without a card, is the firmware's own. The reference for
"as it was" is the same copy with the setting word at 0 (every other patch of the set stays on), so a difference is the dice's.

    tools/emu/.venv/bin/python tools/emu/dice_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import dice as spec  # noqa: E402
import fat32  # noqa: E402
import synthaddr  # noqa: E402
from machine import UART1, load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
MODEL_PTR = 0xC0348884                              # pointer to the sequencer model, +0x320 the selected part (the synth has its own place, data/synth-map/dice.json)
PATTERN_PTR = 0xC033E6A4
SET_KEY, SET_SCALE = 0xC004A6FC, 0xC004A77C         # (pattern, value, notify): the setters the Pattern menu calls
KEYS = {"rec": 0x00, "stop": 0x01, "play": 0x02, "menu": 0x09, "exit": 0x0D, "part_right": 0x0F, "part_left": 0x0B, "trigger": 0x13, "sequencer": 0x15,
        "keyboard": 0x17, "chord": 0x18, "step_jump": 0x19, "pattern_set": 0x1B, "bar1": 0x1C, "bar4": 0x1F}
STEP_BASE = 0x800 + 0x30 + 4                        # part 0, step 0 in the pattern object; 12 bytes a step: on, gate, velocity, trigger, 4 notes
KILL = spec.KILL_SWITCH
_card = {}


def for_build(payload):
    """Put the patch module's places to the build of this image (the synth has its own addresses, data/synth-map/)."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")
SHIFT, PART_ERASE = 0x0A, 0x11
BLOCK = 0x4010                                      # the pattern object's block with its 4-byte lead
PART = 0x330
RECORD = 12
# the notes of each scale over its root, music theory (the same as src/dice.mjs knows); the firmware's own layout is the second witness
SCALES = {0: range(12), 1: (0, 2, 4, 5, 7, 9, 11), 2: (0, 2, 3, 5, 7, 9, 10), 3: (0, 1, 3, 5, 7, 8, 10), 4: (0, 2, 4, 6, 7, 9, 11), 5: (0, 2, 4, 5, 7, 9, 10),
          6: (0, 2, 3, 5, 7, 8, 10), 7: (0, 1, 3, 5, 6, 8, 10), 10: (0, 2, 3, 4, 7, 9), 11: (0, 3, 5, 6, 7, 10), 14: (0, 2, 4, 7, 9), 15: (0, 3, 5, 7, 10), 29: (0, 2, 4, 6, 8, 10)}


def has_hooks(payload):
    """True when the first instruction of the mode keys' key function branches into the patch's code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.KEY_HOOK - IMAGE)[0]
    return word >> 24 == 0xEA and spec.CODE_AT <= spec.KEY_HOOK + 8 + ((word & 0xFFFFFF) << 2) < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"dice:{name}", "ok": bool(ok), "detail": str(detail)}


def sha(data):
    return hashlib.sha256(bytes(data)).hexdigest()[:12]


def card_image():
    """A formatted card without files, made once per process."""
    if "img" not in _card:
        _card["img"] = bytes(fat32.format_image(64 * 1024 * 1024))
    return bytearray(_card["img"])


class DBox:
    """A booted device (3 s) with a mounted card unless asked otherwise, and the helpers of these cases. The pattern is four bars long."""

    def __init__(self, payload, flash=None, held=0, card=True, seconds=3.0):
        self.payload = bytes(payload)
        for_build(self.payload)
        self.dev = Dev(self.payload, flash, held)
        self.m = self.dev.m
        if card:
            self.m.insert_card(SDCard(MemoryMedium(card_image())))
        self.dev.run(seconds)
        self.marks = {}
        if self.raw(self.pattern() + 0x29, 1)[0] < 3:
            self.m.uc.mem_write(self.pattern() + 0x29, bytes([3]))

    def u32(self, addr):
        """A place of the firmware's image or its variables, by the Sampler's address (translated for the synth)."""
        return self.dev.u32(addr)

    def raw(self, addr, n):
        """Memory at a run time address (a heap object): never translated."""
        return bytes(self.m.uc.mem_read(addr, n))

    def raw32(self, addr):
        return struct.unpack("<I", self.raw(addr, 4))[0]

    def run(self, seconds):
        self.dev.run(seconds)

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

    def pad_down(self, n, velocity=100, wait=0.15):
        self.m.send([4, n, 0, velocity, 1])
        self.run(wait)

    def pad_up(self, n, wait=0.2):
        self.m.send([4, n, 0, 0, 0])
        self.run(wait)

    def pattern(self):
        return self.u32(PATTERN_PTR)

    def set_scale(self, key, scale):
        """The key and the scale as the Pattern menu sets them: through the firmware's setters, which build the layout again."""
        self.dev.call(SET_KEY, self.pattern(), key, 0)
        self.dev.call(SET_SCALE, self.pattern(), scale, 0)
        self.run(0.3)

    def mark(self, name="m"):
        self.marks[name] = len(self.m.uart[UART1]["tx"])

    def midi(self, name="m"):
        """Channel messages sent since the mark, as (status, data bytes); clock and the like left out."""
        data = bytes(self.m.uart[UART1]["tx"][self.marks[name]:])
        out, cur, status = [], [], None
        for x in data:
            if x >= 0xF8:
                continue
            if x & 0x80:
                status, cur = x, []
                continue
            if status is None:
                continue
            cur.append(x)
            if len(cur) == (1 if status & 0xF0 in (0xC0, 0xD0) else 2):
                out.append((status, tuple(cur)))
                cur = []
        return out

    def layout(self):
        """The note of each pad in KEYBOARD mode, from the MIDI out of the firmware (only the firmware's own, no hook needed)."""
        notes = []
        for n in range(16):
            self.mark("l")
            self.pad_down(n, wait=0.1)
            on = [d[0] for st, d in self.midi("l") if st & 0xF0 == 0x90]
            self.pad_up(n, wait=0.1)
            notes.append(on[0] if on else None)
        return notes

    def combo(self, key=PART_ERASE, shift=True, hold=0.1, wait=0.5):
        """SHIFT held, the key pressed and let go, SHIFT let go."""
        if shift:
            self.m.press(SHIFT, True)
            self.run(0.1)
        self.m.press(key, True)
        self.run(hold)
        self.m.press(key, False)
        self.run(0.1)
        if shift:
            self.m.press(SHIFT, False)
        self.run(wait)

    def selected(self):
        return self.raw32(self.u32(MODEL_PTR) + 0x320)

    def select(self, part):
        for _ in range(32):
            selected = self.selected()
            if selected == part:
                return
            self.key("part_right" if selected < part else "part_left", 0.25)
        raise RuntimeError(f"part selection did not reach {part}")

    def block(self):
        return self.raw(self.pattern(), BLOCK)

    def records(self, part):
        """The 64 step records of a part, 12 bytes each."""
        raw = self.raw(self.pattern() + STEP_BASE + PART * part, RECORD * 64)
        return [raw[i * RECORD:(i + 1) * RECORD] for i in range(64)]

    def fill(self, part, record):
        """Every step of a part set to one record, so that what the dice leave alone is recognisable."""
        self.m.uc.mem_write(self.pattern() + STEP_BASE + PART * part, bytes(record) * 64)

    def poke(self, offset, value):
        self.m.uc.mem_write(self.pattern() + offset, bytes([value]))

    def flash_sha(self):
        return sha(self.m.flash.mem)

    def flash_writes(self):
        return tuple(self.m.flash.commands[c] for c in (0x01, 0x02, 0x20, 0x52, 0xD8, 0x60, 0xC7))

    def look(self):
        return (self.dev.screen()["number"], self.dev.screen()["window"] != 0, sha(self.dev.fb()), sorted(self.leds().items()))


_layouts = {}


def layout_of(payload, flash, key, scale):
    """The 16 notes of the keyboard for a key and scale, measured with the patch off (EXIT held at power-on), so it is the firmware's alone."""
    if (key, scale) not in _layouts:
        box = DBox(payload, flash, KILL)
        box.dev.press(KEYS["keyboard"], 0.4)
        box.set_scale(key, scale)
        _layouts[(key, scale)] = box.layout()
    return _layouts[(key, scale)]


def step_area(box, part):
    """The offsets of the first eight bytes of every step record of a part: what the dice may write."""
    base = STEP_BASE + PART * part
    return {base + RECORD * s + k for s in range(64) for k in range(8)}


def changed(a, b):
    return [i for i in range(min(len(a), len(b))) if a[i] != b[i]]


def notes_of(records):
    return [r[4] - 1 for r in records if r[0] == 1 and r[4]]


def _setting_off(payload, flash, **kw):
    box = DBox(payload, flash, **kw)
    box.m.uc.mem_write(spec.DC_SETTING, struct.pack("<I", 0))
    box.run(0.1)
    return box


# ---------------------------------------------------------------------------------------- the cases
def case_roll(payload, flash):
    """SHIFT + PART ERASE rolls the selected part; only that part's step records change, in the first eight bytes of each; two rolls differ."""
    out = []
    box = DBox(payload, flash)
    flash_before = box.flash_sha()
    writes_before = box.flash_writes()
    seen = []
    for part in (0, 6, 15):
        box.select(part)
        before = box.block()
        box.combo()
        after = box.block()
        diff = changed(before, after)
        stray = [i for i in diff if i not in step_area(box, part)]
        recs = box.records(part)
        on = [s for s, r in enumerate(recs) if r[0] == 1]
        bad = [(s, r.hex()) for s, r in enumerate(recs) if r[0] == 1 and not (r[3] == 1 and 1 <= r[2] <= 127 and (1 <= r[1] <= 96 or r[1] == 127) and 1 <= r[4] <= 128 and r[5:8] == b"\0\0\0")]
        seen.append((part, len(on), sorted(stray)[:6], bad[:3], box.selected()))
        second = box.records(part)
        box.combo()
        again = box.records(part)
        seen[-1] += (second != again,)
    out.append(entry("combo_rolls_the_selected_part", all(on >= 8 and not stray and not bad and sel == part and differ for (part, on, stray, bad, sel, differ) in seen) and not box.m.asserts,
                     f"parts 1, 7 and 16: (part, steps on of 64, changed bytes outside the part's step records, malformed steps, part after, a second roll differs): {seen}"))
    out.append(entry("rolls_only_the_selected_part", all(not stray for (_, _, stray, *_) in seen),
                     "every byte of the pattern block outside the first eight bytes of the selected part's 64 step records is the same after the roll"))
    out.append(entry("nothing_written_to_flash", box.flash_sha() == flash_before and box.flash_writes() == writes_before and not box.m.asserts,
                     f"the complete flash image is the same after six rolls ({box.flash_sha()}), no additional write commands"))
    return out


def case_scale(payload, flash):
    """The notes are notes of the pattern's key and scale (the firmware's own layout for it is the witness), from the root up to two octaves."""
    bad, rows = [], []
    for key, scale in ((0, 2), (7, 1), (3, 14), (11, 15), (5, 0), (2, 10), (9, 11), (4, 29), (0, 34), (6, 28)):
        box = DBox(payload, flash)
        box.set_scale(key, scale)
        notes = []
        for _ in range(3):
            box.combo(wait=0.3)
            notes += notes_of(box.records(0))
        low, high = spec.ROOT_NOTE + key, spec.ROOT_NOTE + key + spec.SPAN
        theory = {(key + i) % 12 for i in SCALES[scale]} if scale in SCALES else None
        layout = [n for n in layout_of(payload, flash, key, scale) if n is not None]
        witness = {(n - key) % 12 for n in layout}
        rows.append((key, scale, len(notes), sorted(set(notes))[:12]))
        wrong = [n for n in notes if not low <= n <= high or (n - key) % 12 not in witness or (theory is not None and n % 12 not in theory)]
        if wrong or not notes or (scale not in (34,) and len(set(notes)) < 3):
            bad.append((key, scale, wrong[:5], len(set(notes))))
    return [entry("notes_stay_in_key_and_scale", not bad,
                  f"ten keys and scales (Dorian in C, Ionian in G, Major Penta in D#, minor Penta in B, Chromatic in F, Major Blues in D, minor Blues in A, Whole Tone in E, octaves only, the wide scale 28), three rolls each: "
                  f"every note lies from the root (C3 plus the key) to two octaves above, is a pitch class of the key's scale by theory and by the firmware's own pad layout, and at least three different notes come; wrong: {bad}; (key, scale, notes, distinct): {rows}")]


def case_length(payload, flash):
    """The pattern's length and the part's LAST STEP bound the roll; steps the part does not play are left as they were."""
    out = []
    marker = bytes([1, 0x33, 0x44, 1, 0x30, 0, 0, 0, 0, 0, 0, 0])
    box = DBox(payload, flash)
    box.fill(0, marker)
    box.poke(0x29, 0)                                         # one bar
    box.combo()
    recs = box.records(0)
    one_bar = (recs[16:] == [marker] * 48, any(r != marker for r in recs[:16]))
    box = DBox(payload, flash)
    box.fill(0, marker)
    box.poke(0x804 + 0, 5)                                    # LAST STEP: the first five steps of every bar play
    box.combo()
    recs = box.records(0)
    last = [s for s in range(64) if s % 16 >= 5 and recs[s] != marker], [s for s in range(64) if s % 16 < 5 and recs[s] != marker]
    box = DBox(payload, flash)
    box.fill(0, marker)
    box.poke(0x804 + 0, 16)
    box.combo()
    recs = box.records(0)
    sixteen = all(any(recs[b * 16 + k] != marker for k in range(16)) for b in range(4))
    out.append(entry("length_bounds_the_roll", one_bar == (True, True),
                     f"a one-bar pattern: steps 17 to 64 are the marker steps (all 48 {one_bar[0]}), steps 1 to 16 changed ({one_bar[1]})"))
    out.append(entry("last_step_bounds_the_roll", not last[0] and len(last[1]) >= 3 and sixteen,
                     f"LAST STEP 5: steps outside the first five of a bar that changed {last[0]}, steps inside that changed {len(last[1])} of 20; LAST STEP 16 rolls all four bars ({sixteen})"))
    return out


def case_play(payload, flash):
    """The part plays what was written: the MIDI notes of the sequencer are the notes of the steps that are on, in order."""
    box = DBox(payload, flash)
    box.select(4)
    box.combo()
    recs = box.records(4)
    want = []
    for s in range(32):
        if recs[s][0] == 1:
            want.append(recs[s][4] - 1)
    box.mark("p")
    box.key("play", 0.0)
    box.run(3.6)                                          # 28 steps at 120 BPM (an Init pattern on an empty flash), 38 at 160
    box.key("stop", 0.3)
    played = [d[0] for st, d in box.midi("p") if st & 0xF0 == 0x90 and st & 0x0F == 4 and d[1] > 0]
    n = min(len(played), len(want), 20)
    ties = sum(1 for r in recs if r[0] == 1 and r[1] == 127)
    out = [entry("part_plays_what_was_written", n >= 6 and played[:n] == want[:n] and not box.m.asserts,
                 f"part 5 rolled, then PLAY: the first {n} note-ons on its MIDI channel {played[:n]} are the notes of the steps that are on {want[:n]} ({ties} ties in the part)")]
    # rolled again and again while it plays: every note that went on goes off, none stays
    box = DBox(payload, flash)
    box.select(4)
    box.combo()
    box.mark("w")
    box.key("play", 0.0)
    for _ in range(6):
        box.run(0.37)
        box.combo(hold=0.05, wait=0.0)
    box.run(0.5)
    box.key("stop", 0.5)
    open_notes, sent = {}, 0
    for st, d in box.midi("w"):
        if st & 0xF0 == 0x90 and d[1] > 0:
            open_notes[(st & 15, d[0])] = open_notes.get((st & 15, d[0]), 0) + 1
            sent += 1
        elif st & 0xF0 == 0x80 or (st & 0xF0 == 0x90 and d[1] == 0):
            open_notes[(st & 15, d[0])] = open_notes.get((st & 15, d[0]), 0) - 1
    stuck = {k: v for k, v in open_notes.items() if v}
    out.append(entry("roll_while_playing_leaves_no_stuck_note", sent >= 8 and not stuck and not box.m.asserts,
                     f"six rolls in 2.5 s while part 5 plays: {sent} notes went on, notes still on after STOP {stuck}"))
    return out


def case_leds(payload, flash):
    """In SEQUENCER mode the pads show which steps of the bar are on: after a roll they show the new ones, without a key."""
    box = DBox(payload, flash)
    box.key("sequencer", 0.4)
    box.combo()
    recs = box.records(0)
    lit = sorted(n for n, v in box.leds().items() if v[0] == 255)
    want = [s for s in range(16) if recs[s][0] == 1]
    box.dev.press(0x1D, 0.3)
    lit2 = sorted(n for n, v in box.leds().items() if v[0] == 255)
    want2 = [s for s in range(16) if recs[16 + s][0] == 1]
    return [entry("pad_leds_follow_the_roll", lit == want and lit2 == want2 and len(want) >= 3 and not box.m.asserts,
                  f"SEQUENCER mode, bar 1: lit pads {lit}, steps on {want}; after bar 2 {lit2}, steps on {want2}")]


def case_keys(payload, flash):
    """Every key but SHIFT + PART ERASE is the firmware's: the same keys on the copy with the setting off give the same pattern, screen, window, display and LEDs."""
    sequence = [("part_erase", PART_ERASE, False), ("shift_trigger", 0x13, True), ("shift_sequencer", 0x15, True), ("shift_keyboard", 0x17, True), ("shift_chord", 0x18, True),
                ("shift_step_jump", 0x19, True), ("shift_part_mute", 0x10, True), ("shift_pattern_set", 0x1B, True), ("trigger", 0x13, False), ("sequencer", 0x15, False),
                ("keyboard", 0x17, False), ("chord", 0x18, False), ("step_jump", 0x19, False), ("shift_tap", 0x03, True), ("shift_edit_left", 0x08, True)]
    box, ref = DBox(payload, flash), _setting_off(payload, flash)
    diffs = []
    for name, key, shift in sequence:
        for b in (box, ref):
            b.combo(key, shift, wait=0.4)
            if name in ("shift_chord", "shift_tap", "shift_edit_left", "shift_part_mute"):
                b.key("exit", 0.5)
        if box.block() != ref.block() or box.look() != ref.look():
            diffs.append((name, len(changed(box.block(), ref.block())), box.look()[:3], ref.look()[:3]))
    # PART ERASE mode: erase while the part plays, the way the firmware does, with and without the patch
    for b in (box, ref):
        b.key("sequencer", 0.3)
        b.fill(0, bytes([1, 0x40, 0x60, 1, 0x3D, 0, 0, 0, 0, 0, 0, 0]))
        b.key("play", 0.3)
        b.dev.press(PART_ERASE, 0.3)
        b.pad_down(3, wait=1.0)
        b.pad_up(3, wait=0.2)
        b.key("stop", 0.3)
    erase_same = box.block() == ref.block()
    erased = sum(1 for r in box.records(0) if r[0] == 0)
    return [entry("other_keys_are_the_firmwares", not diffs and erase_same and not box.m.asserts,
                  f"{len(sequence)} presses (PART ERASE alone, SHIFT with the mode keys, PART MUTE, PATTERN SET, TAP and EDIT left, and the mode keys alone) on the patched copy and on the same copy with DC_SETTING 0: "
                  f"differences {diffs}; PART ERASE mode while playing erases {erased} steps and leaves the same pattern as without the patch ({erase_same})")]


def case_screens(payload, flash):
    """Off the main screen the combination is the firmware's: in the menu and under a window nothing is written."""
    out = []
    box = DBox(payload, flash)
    box.key("menu", 0.5)
    screen = box.dev.screen()["number"]
    before = box.block()
    box.combo()
    in_menu = (screen, box.dev.screen()["number"], box.block() == before)
    box.key("exit", 0.5)
    box.key("exit", 0.5)
    box.m.press(SHIFT, True)
    box.run(0.1)
    box.m.press(0x08, True)
    box.run(0.1)
    box.m.press(0x08, False)
    box.run(0.1)
    box.m.press(SHIFT, False)
    box.run(0.4)
    window = box.dev.screen()["window"] != 0
    before = box.block()
    box.combo()
    under = box.block() == before
    out.append(entry("no_roll_in_menu_or_window", in_menu[2] and in_menu[0] != 1 and under and window and not box.m.asserts,
                     f"in the menu (screen {in_menu[0]}, then {in_menu[1]}) the pattern is unchanged ({in_menu[2]}); under a window ({window}) it is unchanged ({under})"))
    return out


def case_stock(payload, flash):
    """EXIT held at power-on, no card, the setting off: SHIFT + PART ERASE does nothing of the dice and the state is untouched; set back to 1 it works."""
    out, rows = [], {}
    for name, make in {"exit_held": lambda: DBox(payload, flash, KILL), "no_card": lambda: DBox(payload, flash, card=False), "setting_off": lambda: _setting_off(payload, flash)}.items():
        box = make()
        before = box.block()
        box.combo()
        rows[name] = (box.block() == before, box.u32(spec.STATE + spec.S_RNG), box.u32(spec.STATE + spec.S_POOLN), box.m.asserts)
    untouched = all(r[0] and r[1] == 0xFFFFFFFF and r[2] == 0xFFFFFFFF and not r[3] for r in rows.values())
    out.append(entry("stock_without_the_patch", untouched,
                     f"(pattern unchanged, generator state, pool size, assertions) after SHIFT + PART ERASE: {rows}; the patch does not write its state either"))
    box = _setting_off(payload, flash)
    box.m.uc.mem_write(spec.DC_SETTING, struct.pack("<I", 1))
    before = box.records(0)
    box.combo()
    out.append(entry("setting_on_again", box.records(0) != before and not box.m.asserts, "the setting word set to 1 at run time: the roll works"))
    return out


GROUPS = (case_roll, case_scale, case_length, case_play, case_leds, case_keys, case_screens, case_stock)


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
