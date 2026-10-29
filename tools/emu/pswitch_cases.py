# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the pattern switch patch (tools/patch/pattern_switch.py,
docs/ideen/46-patternwechsel-bestaetigung.md).

check.py runs `cases` on every patched copy that carries the patch's hooks. While a pattern
plays, the wheel only browses (no MIDI, the lower line says VIEW:), MENU confirms and the
pattern starts at the next sequence end, EXIT takes browse or confirmation back, STOP drops
a browse; stopped, with EXIT held at power-on, without a card or with the setting off the
firmware is exactly as it was. The reference for "as it was" is the same copy with EXIT held
at power-on: no hook of the patch does anything then (the patch's first test).

    tools/emu/.venv/bin/python tools/emu/pswitch_cases.py cases --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import pattern_switch as spec  # noqa: E402
import synthaddr  # noqa: E402
from machine import UART1, load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
PSEL_PTR, PLAYER_PTR, TRANSPORT_PTR = 0xC03487E8, 0xC034029C, 0xC03405BC
PAD_SELECT, MIDI_PROGRAM = 0xC006EDE4, 0xC006EE00     # (any, number) and (any, number, any), called from the screen tick
KEYS = {"play": 2, "stop": 1, "menu": 9, "exit": 0x0D, "shift": 0x0A, "part_mute": 0x10}
SLOTS = 0xC08B2940                  # the pattern bank in RAM, 0x4000 per pattern
CHAIN_TO, CHAIN_REPEAT = 15104, 15106
KILL = spec.KILL_SWITCH
_card = {}


def for_build(payload):
    """Put the patch module's places to the build of this image (the synth has its own addresses, data/synth-map/)."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hooks(payload):
    """True when the MENU slot of the main screen points into the patch's code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.MENU_SLOT - IMAGE)[0]
    return spec.CODE_AT <= word < spec.CODE_END


def card_image():
    """A formatted card without files, made once per process."""
    if "img" not in _card:
        _card["img"] = bytes(fat32.format_image(64 * 1024 * 1024))
    return bytearray(_card["img"])


class Box:
    """A booted device (3 s) with a mounted card, or without one."""

    def __init__(self, payload, flash=None, held=0, card=True, seconds=3.0, adapter=False):
        self.payload = bytes(payload)
        for_build(self.payload)
        self.dev = Dev(self.payload, flash, held, adapter=adapter)
        self.m = self.dev.m
        if card:
            self.m.insert_card(SDCard(MemoryMedium(card_image())))
        self.dev.run(seconds)
        self.marks = {}
        # The cases play patterns that last several seconds (a click must come before the sequence end). The flash dump has patterns of four
        # bars; an empty flash holds Init patterns of one bar, which end within two seconds. The length (block offset 37, bars minus one) is
        # read at PLAY and when a pattern is chosen, so the live pattern (the block starts 4 bytes behind its pointer) and the bank get it.
        # A pattern chains only with CHAIN MODE on (global block offset 31, 1 in the flash dump, 0 in an empty flash), in both copies of the block.
        self.slots = self.dev.a(SLOTS)
        for glob in (0xC06A2A94, 0xC08A2940):
            if self.dev.read(glob, 4) == b"GLST":
                self.m.uc.mem_write(self.dev.a(glob) + 31, bytes([1]))
        live = self.u32(0xC033E6A4) + 4 + 37
        for at in [live, *(self.slots + n * 0x4000 + 37 for n in range(16))]:
            if self.dev.read(at, 1)[0] < 3:
                self.m.uc.mem_write(at, bytes([3]))

    # ---- the firmware's numbers
    def u32(self, addr):
        return self.dev.u32(addr)

    def running(self):
        return self.u32(self.u32(PLAYER_PTR) + 0x318)

    def chosen(self):
        return self.u32(self.u32(PSEL_PTR) + 0x318)

    def pending(self):
        return self.dev.read(self.u32(PSEL_PTR) + 0x341, 1)[0]

    def transport(self):
        return self.u32(self.u32(TRANSPORT_PTR) + 0x308)

    def flags(self):
        """(browse, confirmed, number) of the patch; FFFFFFFF where nothing was ever written."""
        return tuple(self.u32(spec.STATE + o) for o in (spec.S_BROWSE, spec.S_ARMED, spec.S_ARMNUM))

    def menu_led(self):
        """MENU's LED in the LED manager: (mode, brightness now); mode 1 steady, 2 blinking."""
        at = self.u32(spec.LED_MGR) + 8 * spec.LED_MENU
        return self.dev.read(at + 0x4D, 1)[0], self.dev.read(at + 0x4E, 1)[0]

    def view(self):
        """What the pattern selection shows: (running, chosen, pending)."""
        return self.running(), self.chosen(), self.pending()

    def dirty(self):
        """Whether the pattern in RAM differs from its place in the bank (unsaved changes)."""
        live = bytes(self.m.uc.mem_read(self.u32(0xC033E6A4) + 4, 0x4000))
        return live != bytes(self.m.uc.mem_read(self.slots + self.running() * 0x4000, 0x4000))

    # ---- bedienen
    def key(self, name, wait=0.3):
        self.dev.press(KEYS[name], wait)

    def turn(self, delta, wait=0.3):
        self.dev.turn(delta, wait)

    def run(self, seconds):
        self.dev.run(seconds)

    def set_setting(self, value):
        self.m.uc.mem_write(spec.PS_SETTING, struct.pack("<I", value))

    def pattern_bytes(self, number, at, data):
        self.m.uc.mem_write(self.slots + number * 0x4000 + at, bytes(data))

    # ---- MIDI out
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

    def program_changes(self, name="m"):
        """The program numbers sent since the mark, with their bank select left out."""
        return [d[0] for st, d in self.midi(name) if st & 0xF0 == 0xC0]

    def until_change(self, limit=20.0, step=0.01, settle=0.5):
        """Seconds from PLAY until the running number changes (None if it does not within the limit), looked at every 10 ms of device time.
        Then `settle` seconds more: the user interface clears the pending flag a little after the change."""
        start, t = self.running(), 0.0
        while t < limit and self.running() == start:
            self.run(step)
            t += step
        changed = round((self.m.time_ns - self.t_play) / 1e9, 2) if self.running() != start else None
        self.run(settle)
        return changed

    def look(self):
        """The screen and the frame as the firmware drew it (the frame buffer: the load bar's look changes only what is sent)."""
        return self.dev.screen()["number"], self.dev.read(VRAM, 1024)


VRAM = 0xC031B310               # the firmware's frame buffer

def near(a, b, tolerance=0.03):
    """Two times of the same device timeline, looked at in steps of 10 ms."""
    return a is not None and b is not None and abs(a - b) <= tolerance


def play(box):
    box.t_play = box.m.time_ns
    box.key("play", 0.5)


def entry(name, ok, detail):
    return {"id": f"pswitch:{name}", "ok": bool(ok), "detail": str(detail)}


# ---------------------------------------------------------------------------------------- the cases
def case_browse(payload, flash):
    """The wheel browses while a pattern plays; nothing starts, no MIDI goes out, the lower line says VIEW:, MENU confirms."""
    out = []
    ref = Box(payload, flash, KILL)
    box = Box(payload, flash)
    ref2 = Box(payload, flash, KILL)
    target = max(b.m.time_ns for b in (ref, box, ref2))
    for b in (ref, box, ref2):
        b.run((target - b.m.time_ns) / 1e9)
    for b in (ref, box, ref2):
        play(b)
        b.mark()
        b.turn(1)
        b.turn(1)
        b.turn(3)
    # the reference is the firmware's own: pending, MIDI on every click, the number starts at the end
    ref_end = ref.until_change()
    out.append(entry("reference_firmware", ref.flags() == (0xFFFFFFFF,) * 3 and ref.program_changes() == [1, 2, 5] and ref_end is not None and ref.running() == 5,
                     f"EXIT held: a click sends a program change each ({ref.program_changes()}), pending, the number starts at the sequence end after {ref_end} s, the patch's state untouched {ref.flags()}"))
    out.append(entry("browse_is_silent", box.view() == (0, 5, 1) and box.flags()[0] == 1 and box.program_changes() == [] and not box.m.asserts,
                     f"after three clicks: running/chosen/pending {box.view()}, browse flag {box.flags()[0]}, program changes sent {box.program_changes()}"))
    # The firmware's NEXT: display blinks the pattern name; when the sample falls on the dark half moves with every instruction a patch adds
    # to the frame (the emulator's time is counted in instructions). Look ten times in 0.5 s, both run alike; one look where only the lower
    # line differs is the answer.
    differ = None
    for _ in range(10):
        fb, theirs = box.dev.read(VRAM, 1024), ref2.dev.read(VRAM, 1024)
        now = {i // 128 for i in range(1024) if fb[i] != theirs[i]}
        if now and now <= {6, 7}:
            differ = now
            break
        differ = now
        for b in (box, ref2):
            b.run(0.05)
    out.append(entry("browse_label_is_view", differ and differ <= {6, 7} and box.flags()[0] == 1,
                     f"the display differs from the firmware's NEXT: display only in the lower line (pages {sorted(set(differ))}), where the label reads VIEW:"))
    box.run(7.0)
    out.append(entry("browse_keeps_looping", box.running() == 0 and box.view() == (0, 5, 1) and box.transport() == 1 and not box.m.asserts,
                     f"after seven seconds (the reference switched after {ref_end} s) the pattern still loops: running/chosen/pending {box.view()}"))
    return out


def case_confirm(payload, flash):
    """MENU confirms: MIDI goes out now, the pattern starts at the same sequence end the firmware would use, the state is over."""
    out = []
    ref = Box(payload, flash, KILL)
    box = Box(payload, flash)
    leds = []
    for b in (ref, box):
        play(b)
        b.mark()
        leds.append(b.menu_led())
        b.turn(3)
        leds.append(b.menu_led())
        b.run(0.3)
        leds.append(b.menu_led())
        b.key("menu")
        leds.append(b.menu_led())
    ref_end, box_end = ref.until_change(), box.until_change()
    leds.append(box.menu_led())
    out.append(entry("menu_led_shows_where_to_press", leds[4:] == [(1, 0), (2, 0), (2, 255), (1, 255), (1, 0)] and set(leds[:4]) == {(1, 0)},
                     f"MENU's LED (mode, brightness) playing, browsed, 0.3 s later, confirmed, switched: {leds[4:]}; the firmware alone: {leds[:4]}"))
    out.append(entry("confirm_switches_at_sequence_end",
                     near(box_end, ref_end) and box.running() == 3 and box.view() == (3, 3, 0) and box.flags()[:2] == (0, 0) and not box.m.asserts,
                     f"browse +3, MENU: the pattern changes after {box_end} s, the firmware's own pending number after {ref_end} s; running/chosen/pending {box.view()}, flags {box.flags()}"))
    pcs = box.program_changes()
    out.append(entry("confirm_sends_midi_once", pcs == [3] and ref.program_changes() == [3],
                     f"the program change goes out when MENU confirms, once ({pcs}); the firmware sent {ref.program_changes()} for the same click"))
    box.run(6.0)
    out.append(entry("confirmed_pattern_loops", box.running() == 3 and box.view() == (3, 3, 0) and box.flags()[:2] == (0, 0), f"{box.view()} {box.flags()}"))
    # browsing on after the confirmation does not change what starts
    b2 = Box(payload, flash)
    play(b2)
    b2.turn(2)
    b2.key("menu")
    b2.turn(5)
    out.append(entry("browse_after_confirm_keeps_it", b2.flags() == (1, 1, 2) and b2.chosen() == 7, f"flags {b2.flags()}, chosen {b2.chosen()}"))
    b2.until_change()
    out.append(entry("confirm_wins_over_later_browse", b2.running() == 2 and b2.flags()[:2] == (0, 0), f"the confirmed 2 starts, not the browsed 7: running {b2.running()}"))
    b3 = Box(payload, flash)
    play(b3)
    b3.turn(4)
    b3.turn(-4)
    out.append(entry("back_on_running_cancels", b3.view() == (0, 0, 0) and b3.flags()[:2] == (0, 0), f"browsing back to the running pattern leaves nothing pending: {b3.view()} {b3.flags()}"))
    return out


def case_exit(payload, flash):
    out = []
    box = Box(payload, flash)
    play(box)
    box.mark()
    box.turn(2)
    box.key("exit")
    out.append(entry("exit_takes_browse_back", box.view() == (0, 0, 0) and box.flags()[:2] == (0, 0) and box.program_changes() == [],
                     f"EXIT while browsing: running/chosen/pending {box.view()}, flags {box.flags()}, MIDI {box.midi()}"))
    box.run(5.0)
    out.append(entry("exit_browse_never_switches", box.running() == 0, f"running {box.running()} after five seconds"))
    box.turn(2)
    box.key("menu")
    box.key("exit")
    out.append(entry("exit_takes_confirmation_back", box.view() == (0, 0, 0) and box.flags()[:2] == (0, 0) and box.program_changes() == [2, 0],
                     f"confirm 2, EXIT: {box.view()}, flags {box.flags()}, program changes {box.program_changes()} (2 on confirm, 0 puts the running pattern back)"))
    box.run(5.0)
    out.append(entry("exit_confirmation_never_switches", box.running() == 0, f"running {box.running()} after five seconds"))
    # browsing on after a confirmation and EXIT: back to the confirmed number first, then the confirmation goes
    b2 = Box(payload, flash)
    play(b2)
    b2.turn(2)
    b2.key("menu")
    b2.turn(4)
    b2.key("exit")
    first = (b2.view(), b2.flags())
    b2.key("exit")
    out.append(entry("exit_steps_back_in_two", first == ((0, 2, 1), (0, 1, 2)) and b2.view() == (0, 0, 0) and b2.flags()[:2] == (0, 0),
                     f"browse away from the confirmed 2 and EXIT: {first}; EXIT again: {b2.view()} {b2.flags()}"))
    return out


def case_stopped(payload, flash):
    """Stopped, and when record is armed, the wheel is the firmware's: it loads at once and sends MIDI."""
    out = []
    ref, box = Box(payload, flash, KILL), Box(payload, flash)
    for b in (ref, box):
        b.mark()
        b.turn(1)
        b.turn(3)
        b.dev.m.press(KEYS["shift"], True)
        b.run(0.2)
        b.turn(1)
        b.dev.m.press(KEYS["shift"], False)
        b.run(0.3)
    out.append(entry("stopped_is_stock", box.view() == ref.view() and box.midi() == ref.midi() and box.look() == ref.look() and box.flags() == (0xFFFFFFFF,) * 3 and ref.view()[0] == 14,
                     f"stopped: wheel clicks and SHIFT + wheel: number, pending, MIDI ({len(box.midi())} messages) and display equal the firmware's ({box.view()} / {ref.view()}); the patch's state untouched {box.flags()}"))
    # menu and exit with nothing pending are the firmware's; the reference is the same copy with the setting off (the other patches of
    # the set change the Pattern menu's neighbours, so a run with EXIT held would differ for their sake)
    plain = Box(payload, flash)
    plain.set_setting(0)
    plain.turn(1)
    plain.turn(3)
    plain.dev.m.press(KEYS["shift"], True)
    plain.run(0.2)
    plain.turn(1)
    plain.dev.m.press(KEYS["shift"], False)
    plain.run(0.3)
    for b in (plain, box):
        b.key("exit")
    same_exit = box.look() == plain.look()
    for b in (plain, box):
        b.key("menu", 0.6)
    out.append(entry("menu_and_exit_unpended_are_stock", same_exit and box.look() == plain.look() and box.look()[0] != 1,
                     f"EXIT and MENU with nothing pending: the screen ({box.look()[0]}) and the display equal those of the same copy with the setting off"))
    return out


def case_stop(payload, flash):
    out = []
    ref, box = Box(payload, flash, KILL), Box(payload, flash)
    for b in (ref, box):
        play(b)
        b.turn(3)
        b.key("stop", 0.6)
    out.append(entry("stop_drops_browse", ref.view() == (3, 3, 0) and box.view() == (0, 0, 0) and box.transport() == 0 and box.flags()[:2] == (0, 0),
                     f"browse +3, STOP: the firmware applies the pending number {ref.view()}; the patch keeps the pattern that played {box.view()}, flags {box.flags()}"))
    box.key("play", 0.5)
    ok_play = box.transport() == 1 and box.running() == 0
    ref2, box2 = Box(payload, flash, KILL), Box(payload, flash)
    for b in (ref2, box2):
        play(b)
        b.turn(2)
        b.key("menu")
        b.key("stop", 0.6)
    out.append(entry("stop_applies_confirmation", box2.view() == ref2.view() == (2, 2, 0) and box2.flags()[:2] == (0, 0) and ok_play,
                     f"browse 2, MENU, STOP: {box2.view()} as the firmware's {ref2.view()}; PLAY after the dropped browse plays the old pattern ({ok_play})"))
    out.append(entry("stop_runs_clean", not ref.m.asserts and not box.m.asserts and not box2.m.asserts, "no assertion after the STOP cases"))
    return out


def case_chain(payload, flash):
    """A pattern with a chain: browsing does not stop the chain, a confirmed pattern beats it (as a pending one does)."""
    out = []

    def make(held):
        b = Box(payload, flash, held)
        b.pattern_bytes(4, CHAIN_TO, [10])          # pattern 5 chains to pattern 10 (the byte counts from 1)
        b.pattern_bytes(4, CHAIN_REPEAT, [1])
        b.turn(4)                                    # stopped: loads pattern 4 at once
        return b
    ref, plain, browsed, confirmed = make(KILL), make(0), make(0), make(0)
    for b in (ref, plain):
        play(b)
    ref_end, plain_end = ref.until_change(), plain.until_change()
    play(browsed)
    browsed.turn(3)
    browsed_end = browsed.until_change()
    play(confirmed)
    confirmed.turn(3)
    confirmed.key("menu")
    confirmed_end = confirmed.until_change()
    out.append(entry("chain_runs_unbrowsed", ref.running() == 9 and plain.running() == 9 and near(plain_end, ref_end),
                     f"pattern 4 chains to 9: firmware {ref.running()} after {ref_end} s, patched {plain.running()} after {plain_end} s"))
    out.append(entry("chain_runs_while_browsing", browsed.running() == 9 and near(browsed_end, ref_end) and not browsed.pending(),
                     f"browsing 3 away does not stop the chain: running {browsed.running()} after {browsed_end} s, pending {browsed.pending()}"))
    out.append(entry("confirmed_beats_chain", confirmed.running() == 7 and near(confirmed_end, ref_end), f"confirmed 7 starts instead of the chain's 9: running {confirmed.running()} after {confirmed_end} s"))
    return out


def case_other_sources(payload, flash):
    """A pad or a program change is a deliberate choice: it wins over a browse and starts at the end as the firmware does."""
    out = []
    for name, call in (("pad", lambda b: b.dev.call(PAD_SELECT, 0, 7)), ("midi", lambda b: b.dev.call(MIDI_PROGRAM, 0, 9, 0))):
        ref, box = Box(payload, flash, KILL), Box(payload, flash)
        for b in (ref, box):
            play(b)
            b.turn(2)
            call(b)
        ref_end, box_end = ref.until_change(), box.until_change()
        want = 7 if name == "pad" else 9
        out.append(entry(f"{name}_wins_over_browse", ref.running() == box.running() == want and near(box_end, ref_end) and box.flags()[:2] == (0, 0) and not box.m.asserts,
                         f"{name} {want} after a browse of 2: running {box.running()} after {box_end} s, the firmware {ref.running()} after {ref_end} s, flags {box.flags()}"))
    return out


def case_wrap(payload, flash):
    """The browse wraps like the firmware's wheel and SHIFT + wheel goes in tens."""
    out = []
    ref, box = Box(payload, flash, KILL), Box(payload, flash)
    for b in (ref, box):
        play(b)
        b.turn(-1)
        b.dev.m.press(KEYS["shift"], True)
        b.run(0.2)
        b.turn(1)
        b.dev.m.press(KEYS["shift"], False)
        b.run(0.3)
    out.append(entry("browse_wraps_and_shift_steps", ref.chosen() == box.chosen() == 9 and box.pending() == 1 and box.running() == 0,
                     f"-1 from 0 wraps to 249, SHIFT +1 is +10 and wraps to 9: chosen {box.chosen()} (firmware {ref.chosen()})"))
    return out


def case_off(payload, flash):
    """EXIT held at power-on, no card, and the setting off: nothing of the patch runs and the firmware is as it was."""
    out = []
    ref = Box(payload, flash, KILL)
    cases = {"exit_held_is_stock": ref,
             "no_card_is_stock": Box(payload, flash, card=False),
             "setting_off_is_stock": None}
    off = Box(payload, flash)
    off.set_setting(0)
    cases["setting_off_is_stock"] = off
    results = {}
    for name, b in cases.items():
        play(b)
        b.mark()
        b.turn(1)
        b.turn(3)
        b.key("menu", 0.6)
        b.key("exit", 0.6)
        results[name] = (b.view(), b.program_changes(), b.flags())
    ref_view = results["exit_held_is_stock"][:2]
    for name, (view, pcs, flags) in results.items():
        out.append(entry(name, (view, pcs) == ref_view and view == (0, 4, 1) and pcs == [1, 4] and flags == (0xFFFFFFFF,) * 3 and not cases[name].m.asserts,
                         f"wheel clicks while playing send a program change each ({pcs}) and leave 4 pending ({view}); MENU and EXIT ignore it; the patch's state untouched {flags}"))
    on = Box(payload, flash)
    on.set_setting(1)
    play(on)
    on.turn(2)
    out.append(entry("setting_on_browses", on.flags()[0] == 1 and on.view() == (0, 2, 1), f"setting 1: {on.view()} {on.flags()}"))
    return out


def case_mfx(payload, flash):
    """With the MFX 2 patch in the copy, browsing leaves the effect alone and a pattern change brings MFX 2 for the new one."""
    import mfx_cases
    if not mfx_cases.has_key_hook(payload):
        return []
    out = []
    ref, box = Box(payload, flash), Box(payload, flash)
    ref.set_setting(0)
    for b in (ref, box):
        play(b)
        b.dev.press(5, 0.8)            # TOUCH SCALE: MFX 2 on
    type_before = box.dev.read(box.u32(mfx_cases.PATTERN) + 4 + 61, 1)[0]
    for b in (ref, box):
        b.turn(2)
    still = box.dev.read(box.u32(mfx_cases.PATTERN) + 4 + 61, 1)[0]
    box.key("menu")
    ref_end, box_end = ref.until_change(), box.until_change()
    box.run(1.5)
    ref.run(1.5)

    def mfx(b):
        return (b.u32(mfx_cases.spec.STATE + mfx_cases.S_MODE), b.u32(mfx_cases.spec.STATE + mfx_cases.S_IDX), b.dev.read(b.u32(mfx_cases.PATTERN) + 4 + 61, 1)[0], b.m.leds.get(0x1B, 0))
    out.append(entry("mfx2_combined", still == type_before and box.running() == ref.running() == 2 and near(box_end, ref_end) and mfx(box) == mfx(ref) and mfx(box)[0] == 1 and not box.m.asserts,
                     f"MFX 2 on: browsing leaves the effect type ({type_before} -> {still}), the change after {box_end} s (setting off, the firmware's pending: {ref_end} s) ends with MFX 2 on for the new pattern as without the patch: {mfx(box)} / {mfx(ref)}"))
    return out


def case_unsaved(payload, flash):
    """Stopped with unsaved changes (the pattern in RAM differs from its place in the bank), the wheel browses as while playing: the
    lower line says VIEW:, nothing is loaded, EXIT stays on the edited pattern, MENU loads the browsed one. Without changes the wheel is
    the firmware's. PLAY during such a browse plays the edited pattern (device wish 18.10.)."""
    out = []
    import unicorn

    def edited(b):
        knob = 1 if b.dev.synth else 0    # a knob of the selected part: one byte of the pattern in RAM changes (the synth's knob 0 is not stored, measured)
        b.m.send([2, knob, 0, 200, 0])
        b.run(0.5)
        return b.dirty()

    def views(b):
        """How often the lower line reads the patch's "VIEW:" from now on (a list that grows)."""
        at = IMAGE + bytes(b.payload).find(b"VIEW:\x00", spec.CODE_AT - IMAGE, spec.CODE_END - IMAGE)
        seen = []
        b.m.uc.hook_add(unicorn.UC_HOOK_MEM_READ, lambda *a: seen.append(1), begin=at, end=at)
        b.m.uc.ctl_flush_tb()           # a memory hook only reaches code translated after it
        return seen

    box = Box(payload, flash)
    dirty = edited(box)
    seen = views(box)
    box.mark()
    box.turn(1)
    box.turn(2)
    out.append(entry("unsaved_wheel_browses", dirty and box.view() == (0, 3, 1) and box.flags()[0] == 1 and box.dirty() and box.midi() == [] and seen and not box.m.asserts,
                     f"edited {dirty}; two clicks: running/chosen/pending {box.view()}, browse {box.flags()[0]}, the edit still there {box.dirty()}, MIDI {box.midi()}, "
                     f"VIEW: read {len(seen)} times"))
    box.key("exit")
    out.append(entry("unsaved_exit_stays", box.view() == (0, 0, 0) and box.flags()[0] == 0 and box.dirty() and not box.m.asserts,
                     f"EXIT: {box.view()}, browse {box.flags()[0]}, the edit still there {box.dirty()}"))
    box.turn(2)
    box.key("menu", 0.6)
    out.append(entry("unsaved_menu_loads", box.view() == (2, 2, 0) and box.flags()[0] == 0 and not box.dirty() and box.program_changes() == [2] and not box.m.asserts,
                     f"two clicks and MENU: {box.view()}, the browsed pattern loaded (unsaved {box.dirty()}), program changes {box.program_changes()}"))
    clean = Box(payload, flash)
    clean.turn(1)
    out.append(entry("saved_wheel_is_stock", clean.view() == (1, 1, 0) and clean.flags()[0] in (0, 0xFFFFFFFF),
                     f"without changes a click loads at once as always: {clean.view()}"))
    # the MFX pad's X and Y (0x3E, 0x3F) differ from the bank after a touch of the pad: no edit, the click loads (device wish 25.10.)
    touched = Box(payload, flash)
    xy = touched.u32(0xC033E6A4) + 4 + 0x3E
    touched.m.uc.mem_write(xy, bytes(b ^ 0x40 for b in touched.dev.read(xy, 2)))
    touched.turn(1)
    out.append(entry("pad_xy_is_not_an_edit", touched.view() == (1, 1, 0) and not touched.m.asserts,
                     f"pad X and Y changed in RAM, a click: {touched.view()}"))
    if not clean.dev.synth:
        # saved with the MFX pad touched (byte 0x3C = 1, HOLD off): the load writes 0 there; that is no edit (device report 19.10.)
        pad = Box(payload, flash)
        pad.pattern_bytes(1, 0x3C, [1])
        pad.pattern_bytes(1, 0x41, [0])
        pad.turn(1, 1.0)
        first = pad.view()
        pad.turn(1, 1.0)
        out.append(entry("pad_state_saved_wheel_loads", first == (1, 1, 0) and pad.view() == (2, 2, 0) and not pad.m.asserts,
                         f"pattern saved with the pad touched: a click {first}, the next click {pad.view()}"))
    played = Box(payload, flash)
    edited(played)
    played.turn(3)
    play(played)
    played.run(1.0)
    out.append(entry("unsaved_browse_then_play_plays_the_edit", played.running() == 0 and played.transport() == 1 and played.dirty() and not played.m.asserts,
                     f"browse +3, PLAY: running {played.running()}, transport {played.transport()}, the edit still there {played.dirty()}, view {played.view()}"))
    # WRITE during such a browse: the firmware ignores WRITE while a number is pending (measured: the Write screen does not open), so
    # nothing lands in the browsed place; after EXIT, WRITE works as always and saves the edit into its own place
    wr = Box(payload, flash)
    edited(wr)
    slot = lambda n: bytes(wr.m.uc.mem_read(wr.slots + n * 0x4000, 0x4000))
    three = slot(3)
    wr.turn(3)
    screens = []
    for _ in range(3):
        wr.dev.press(0x0E, 1.0)
        screens.append(wr.dev.screen()["number"])
    ignored = screens == [1, 1, 1] and wr.dirty() and slot(3) == three
    wr.key("exit")
    for _ in range(3):
        wr.dev.press(0x0E, 1.0)
        if not wr.dirty():
            break
    out.append(entry("unsaved_browse_write_waits_for_exit", ignored and not wr.dirty() and slot(3) == three and not wr.m.asserts,
                     f"browse +3, WRITE three times: screens {screens}, the edit kept and place 3 unchanged ({ignored}); after EXIT the edit is saved "
                     f"into its own place ({not wr.dirty()})"))
    off = Box(payload, flash)
    off.set_setting(0)
    edited(off)
    off.turn(1)
    out.append(entry("unsaved_setting_off_is_stock", off.view() == (1, 1, 0), f"PATTERN CONFIRM off: a click loads at once {off.view()}"))
    return out


def case_sync_group(payload, flash):
    """Sync groups (all builds; on the synth since 24.10.): the wheel on another pattern of the running pattern's group confirms it at once, a pattern of
    another group only browses; between two patterns of one group the state of the pattern that played (part mutes and sound,
    tempo) carries over, changed or not, and back again; a part's sample only when it was changed live; the steps stay the new pattern's;
    into any other pattern nothing carries; a pad pressed during the load counts."""
    import unicorn
    out = []
    live = lambda b: b.u32(0xC033E6A4) + 4
    rd = lambda b, at, n=1: bytes(b.dev.read(live(b) + at, n))
    mutes = lambda b: [rd(b, 0x800 + 0x330 * k + 1)[0] for k in range(16)]
    P1, P2 = 0x800, 0x800 + 0x330
    BUSY_PTR = 0xC034057C                         # the firmware's command runner, its busy byte at +0x10
    PITCH, MOD, CUTOFF, SAMPLE, TEMPO, STEP, MFX = P1 + 36, P1 + 18, P2 + 13, P1 + 8, 34, P1 + 0x30 + 2, 61

    def setup(b):
        for n, g in ((0, 7), (1, 7), (2, 0), (3, 7)):
            b.pattern_bytes(n, spec.GROUP_AT, struct.pack("<H", g))
        b.pattern_bytes(0, SAMPLE, struct.pack("<H", 0x0105))
        b.pattern_bytes(1, SAMPLE, struct.pack("<H", 0x0200))
        b.pattern_bytes(1, CUTOFF, [33])          # an untouched value pattern 2 has of its own
        b.m.uc.mem_write(live(b) + spec.GROUP_AT, struct.pack("<H", 7))
        b.m.uc.mem_write(live(b) + SAMPLE, struct.pack("<H", 0x0105))

    def edit(b):
        for k in (3, 5):                          # parts 4 and 6 switched live
            at = live(b) + 0x800 + 0x330 * k + 1
            b.m.uc.mem_write(at, bytes([b.dev.read(at, 1)[0] ^ 1]))
        b.m.uc.mem_write(live(b) + PITCH, bytes([(rd(b, PITCH)[0] + 5) & 0xFF]))
        b.m.uc.mem_write(live(b) + MOD, bytes([rd(b, MOD)[0] ^ 0x20]))
        b.m.uc.mem_write(live(b) + SAMPLE, struct.pack("<H", 0x0106))    # only the low byte differs from the bank
        b.m.uc.mem_write(live(b) + TEMPO, struct.pack("<H", struct.unpack("<H", rd(b, TEMPO, 2))[0] + 50))
        b.m.uc.mem_write(live(b) + STEP, bytes([rd(b, STEP)[0] ^ 0x10]))   # a step: never carried
        b.m.uc.mem_write(live(b) + MFX, bytes([(rd(b, MFX)[0] + 3) % 30]))  # the MFX type (MFX 2's while it is on): never carried

    box = Box(payload, flash)
    setup(box)
    # the bank block the pattern in RAM came from is the start's load, remembered by the copy hook
    loaded = box.u32(spec.STATE + spec.S_LOADED)
    out.append(entry("sync_remembers_the_start_load", loaded == box.slots + box.running() * 0x4000,
                     f"loaded bank block {loaded:#x}, pattern {box.running()} at {box.slots + box.running() * 0x4000:#x}"))
    play(box)
    box.run(0.3)
    edit(box)
    b_saved = bytes(box.m.uc.mem_read(box.slots + 0x4000, 0x4000))
    a_live = bytes(box.m.uc.mem_read(live(box), 0x4000))
    box.mark()
    box.turn(1)
    armed = (box.view(), box.flags(), box.u32(spec.STATE + spec.S_AUTO), box.program_changes())
    out.append(entry("group_confirms_at_once", armed == ((0, 1, 1), (0, 1, 1), 1, [1]) and not box.m.asserts,
                     f"group 7 to group 7: running/chosen/pending, flags (browse, confirmed, number), auto, program changes {armed}"))
    box.until_change()
    got = bytes(box.m.uc.mem_read(live(box), 0x4000))
    want_mutes = [a_live[0x800 + 0x330 * k + 1] for k in range(16)]
    checks = {
        "mutes": mutes(box) == want_mutes,
        "pitch": got[PITCH] == a_live[PITCH],
        "mod depth": got[MOD] == a_live[MOD],
        "sample as one value": got[SAMPLE:SAMPLE + 2] == struct.pack("<H", 0x0106),
        "tempo": got[TEMPO:TEMPO + 2] == a_live[TEMPO:TEMPO + 2],
        "untouched cutoff carried": got[CUTOFF] == a_live[CUTOFF] != 33,
        "step stays": got[STEP] == b_saved[STEP],
        "MFX type stays": got[MFX] == b_saved[MFX] != a_live[MFX],
    }
    out.append(entry("group_carries_the_state", box.running() == 1 and all(checks.values()) and not box.m.asserts,
                     f"running {box.running()}: {checks}; mutes {mutes(box)}, wanted {want_mutes}"))
    back = Box(payload, flash)
    setup(back)
    play(back)
    back.run(0.3)
    back.turn(1)
    back.until_change()
    own = rd(back, SAMPLE, 2)                     # not changed live: pattern 2 plays its own sample on part 1 (device wish 25.10.)
    at = live(back) + 0x800 + 1                   # part 1 switched in the second pattern
    back.m.uc.mem_write(at, bytes([back.dev.read(at, 1)[0] ^ 1]))
    b_live = mutes(back)
    back.turn(-1)
    back.until_change()
    out.append(entry("group_keeps_an_unchanged_sample", own == struct.pack("<H", 0x0200) and not back.m.asserts,
                     f"part 1's sample after the switch {own.hex()}, pattern 2 has 0002 of its own"))
    out.append(entry("group_carries_back", back.running() == 0 and mutes(back) == b_live and rd(back, SAMPLE, 2) == struct.pack("<H", 0x0105)
                     and not back.m.asserts,
                     f"back to pattern 1: running {back.running()}, mutes {mutes(back)}, wanted {b_live}; sample {rd(back, SAMPLE, 2).hex()}, wanted 0501"))
    pad = Box(payload, flash)                     # a pad pressed right after the switch acts on what played, as one before it
    setup(pad)
    a_mute = mutes(pad)[0]
    pad.pattern_bytes(1, 0x800 + 1, [a_mute ^ 1])
    play(pad)
    pad.key("part_mute")
    pad.turn(1)
    pad.until_change(settle=0.0)
    # The carry into the new pattern runs right at the change: a press in its first 5 ms or less is lost (measured 23.10.). The change is
    # seen on a 10 ms grid, so the press waits 20 ms, after the carry in every build.
    pad.run(0.02)
    pad.m.send([4, 0, 0, 100, 1])
    pad.run(0.08)
    pad.m.send([4, 0, 0, 0, 0])
    pad.run(0.5)
    out.append(entry("pad_at_the_switch_toggles_what_played", pad.running() == 1 and mutes(pad)[0] == a_mute ^ 1 and not pad.m.asserts,
                     f"part 1 was {a_mute} in the first pattern, {a_mute ^ 1} saved in the second; pressed in PART MUTE right after the switch: {mutes(pad)[0]}"))
    # The firmware drops a pad press while its command runner is busy, the pattern load among others (device report 25.10.); the patch
    # keeps it and hands it on when the load is done. A tap sent the moment the runner turns busy: press and release both fall in.
    tap = Box(payload, flash)
    setup(tap)
    t_mute = mutes(tap)[0]
    play(tap)
    tap.key("part_mute")
    tap.turn(1)
    runner = tap.u32(BUSY_PTR) + 0x10
    sent, calls = [], []

    def on_busy(uc, access, addr, size, value, _):
        if value == 1 and not sent:
            sent.append(round((tap.m.time_ns - tap.t_play) / 1e9, 3))
            tap.m.send([4, 0, 0, 100, 1])
            tap.m.send([4, 0, 0, 0, 0])
    tap.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, on_busy, begin=runner, end=runner)
    tap.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *a: calls.append(uc.reg_read(unicorn.arm_const.UC_ARM_REG_R4)),
                      begin=spec.PGATE_CONT, end=spec.PGATE_CONT)     # where the handler goes on with a pad (r4 = pressed)
    tap.m.uc.ctl_flush_tb()
    changed = tap.until_change()
    out.append(entry("pad_during_the_load_is_kept", tap.running() == 1 and sent and changed is not None and 0 <= changed - sent[0] < 0.02
                     and mutes(tap)[0] == t_mute ^ 1 and calls == [1, 0] and not tap.m.asserts,
                     f"tap sent at {sent} s as the runner turned busy, the pattern changed at {changed} s; part 1 was {t_mute}, now {mutes(tap)[0]}; "
                     f"pads the handler went on with, pressed: {calls}"))
    box.turn(1)
    browse = (box.view(), box.flags()[:2], box.u32(spec.STATE + spec.S_AUTO))
    out.append(entry("other_group_only_browses", browse == ((1, 2, 1), (1, 0), 0), f"group 7 to group 0: {browse}"))
    box.turn(1)
    again = (box.view(), box.flags())
    out.append(entry("turning_on_rearms_in_the_group", again == ((1, 3, 1), (0, 1, 3)), f"on to pattern 4 (group 7): {again}"))
    box.turn(-1)
    left = (box.view(), box.flags()[:2], box.u32(spec.STATE + spec.S_AUTO))
    out.append(entry("turning_away_takes_the_group_back", left == ((1, 2, 1), (1, 0), 0), f"back to pattern 3 (group 0): {left}"))
    box.key("menu")
    box.until_change()
    other = bytes(box.m.uc.mem_read(live(box), 0x4000))
    stored = bytes(box.m.uc.mem_read(box.slots + 2 * 0x4000, 0x4000))
    differ = [i for i in range(0x4000) if other[i] != stored[i] and i != 0x3C]
    out.append(entry("no_carry_out_of_the_group", box.running() == 2 and not differ and not box.m.asserts,
                     f"confirmed into pattern 3 (group 0): differs from its bank block at {differ[:8]}"))
    ref = Box(payload, flash, KILL)
    setup(ref)
    play(ref)
    ref.run(0.3)
    edit(ref)
    ref.turn(1)
    ref.until_change()
    got = bytes(ref.m.uc.mem_read(live(ref), 0x4000))
    saved = bytes(ref.m.uc.mem_read(ref.slots + 0x4000, 0x4000))
    # Korg's synth firmware itself leaves bytes 0x0B and 0x24 of part 1 different from the bank after this switch: measured the
    # same on the unpatched synth 2.02 (docs/messungen/2026-10-24-blau-sync-group.md), so they are the firmware's, not a carry.
    native = {0x80B, 0x824} if synthaddr.is_synth(payload) else set()
    differ = [i for i in range(0x4000) if got[i] != saved[i] and i != 0x3C and i not in native]
    out.append(entry("group_off_with_exit_held", ref.running() == 1 and not differ and not ref.m.asserts,
                     f"EXIT held at power-on: the firmware's own switch, differs from the bank block at {differ[:8]}"))
    return out


def case_sync_voices(payload, flash):
    """A held pad keeps its allocated voice and old sample through the load; the next press uses the new sample."""
    import unicorn
    out = []
    for name, group, held, keep in (("different_samples", 7, 0, True), ("same_samples", 7, 0, True),
                                    ("other_group", 8, 0, False), ("group_off", 0, 0, False),
                                    ("exit_held", 7, KILL, False)):
        box = Box(payload, flash, held)
        live = box.u32(0xC033E6A4) + 4
        box.m.uc.mem_write(live + spec.GROUP_AT, struct.pack("<H", 7))
        box.pattern_bytes(0, spec.GROUP_AT, struct.pack("<H", 7))
        box.pattern_bytes(1, spec.GROUP_AT, struct.pack("<H", group))
        for pat in (0, 1):
            box.pattern_bytes(pat, 37, b"\0")
        box.m.uc.mem_write(live + 37, b"\0")
        wanted = []
        previous = []
        native = []
        if not spec.SYNTH:
            descriptors = box.u32(0xC00997F0)
            native = [i for i in range(421) if struct.unpack("<H", box.dev.read(descriptors + i * 32 + 18, 2))[0] <= 49]
            if len(native) < 2:
                raise RuntimeError("the sampler has no two built-in DSP oscillators for the voice check")
        for part in range(16):
            at = 0x800 + part * 0x330
            old = struct.unpack("<H", box.dev.read(live + at + 8, 2))[0]
            if native:
                old = native[0]
            new = (native[1] if native else (old + 1) % 1000) if name == "different_samples" else old
            previous.append(old)
            wanted.append(new)
            box.m.uc.mem_write(live + at + 8, struct.pack("<H", old))
            box.pattern_bytes(0, at + 8, struct.pack("<H", old))
            box.pattern_bytes(1, at + 8, struct.pack("<H", new))
            for pat in (0, 1):
                box.pattern_bytes(pat, at + 0x30, bytes(0x300))
            box.m.uc.mem_write(live + at + 0x30, bytes(0x300))
        box.dev.call(0xC0079B78, box.u32(PLAYER_PTR), box.slots, 0)
        play(box)
        part8 = box.dev.call(0xC009AF20, 7)
        voice_sample = 0x38 if spec.SYNTH else 0x3A
        calls, parts = [], []
        notes, snapshots = [], {}
        loading = [False]
        hooks = []

        def voice_state():
            return (box.u32(part8 + 4), struct.unpack("<H", box.dev.read(notes[0][0] + voice_sample, 2))[0]) if notes else (0, None)

        def trace(uc, addr, size, _):
            if addr == box.dev.a(0xC0079BE0):
                loading[0] = True
                snapshots["before"] = voice_state()
            elif addr == box.dev.a(0xC0079C30):
                loading[0] = False
                snapshots["after"] = voice_state()
            elif loading[0] and addr == box.dev.a(0xC0098C70):
                parts.append(uc.reg_read(unicorn.arm_const.UC_ARM_REG_R0))
            elif loading[0]:
                calls.append(addr)

        for at in (0xC0079BE0, 0xC0079C30, 0xC0098C70, 0xC0091F5C):
            address = box.dev.a(at)
            hooks.append(box.m.uc.hook_add(unicorn.UC_HOOK_CODE, trace, begin=address, end=address))
        address = box.dev.a(0xC00998B4)
        hooks.append(box.m.uc.hook_add(unicorn.UC_HOOK_CODE,
                     lambda uc, *_: notes.append((uc.reg_read(unicorn.arm_const.UC_ARM_REG_R0),
                                                   uc.reg_read(unicorn.arm_const.UC_ARM_REG_R1))), begin=address, end=address))
        box.m.uc.ctl_flush_tb()
        box.m.send([4, 7, 0, 100, 1])
        box.run(0.1)
        box.turn(1)
        if not keep:
            box.key("menu")
        box.until_change()
        samples = [struct.unpack("<H", box.dev.read(at + 0x34, 2))[0] for at in parts]
        stopped = box.dev.a(0xC0091F5C) in calls
        preserved = snapshots.get("before", (0, None))[0] != 0 and snapshots.get("before") == snapshots.get("after")
        old_sample = snapshots.get("after", (0, None))[1] == previous[7]
        held = voice_state() == snapshots.get("before")
        count = len(notes)
        box.m.send([4, 7, 0, 0, 0])
        box.run(0.05)
        box.m.send([4, 7, 0, 100, 1])
        box.run(0.1)
        next_sample = len(notes) > count and notes[-1][1] == wanted[7] and struct.unpack(
            "<H", box.dev.read(notes[-1][0] + voice_sample, 2))[0] == wanted[7]
        cleared = snapshots.get("after", (None, None))[0] == 0
        box.key("stop")
        stop_works = box.u32(box.u32(TRANSPORT_PTR) + 0x308) == 0 and box.u32(spec.STATE + spec.S_VOICES) == 0
        box.m.send([4, 7, 0, 0, 0])
        box.run(0.1)
        released = box.u32(part8 + 4) == 0
        out.append(entry(f"voices_{name}", box.running() == 1 and stopped != keep and len(parts) == 16
                         and samples == wanted and (preserved and old_sample and held if keep else cleared)
                         and next_sample and stop_works and released and not box.m.asserts,
                         f"global reset {stopped}, voice before/after {snapshots}, prepared samples {samples}, expected {wanted}; "
                         f"held voice after settling {held}, next trigger uses new sample {next_sample}, STOP stops transport {stop_works}, "
                         f"pad release frees voice {released}; "
                         f"asserts {box.m.asserts}"))
        for hook in hooks:
            box.m.uc.hook_del(hook)
    return out


def case_sync_unsaved(payload, flash):
    """Stopped with unsaved changes, the wheel on another pattern of the pattern's sync group loads it at once, without the browse
    (VIEW:) and without MENU; a pattern of another group is browsed as before. A pattern that came in through a sync group's carry is not
    unsaved because of the carried values, so a run through a group does not stop at a question; an edit made afterwards still is one."""
    out = []
    live = lambda b: b.u32(0xC033E6A4) + 4
    P1 = 0x800
    STEP = P1 + 0x30 + 2

    def setup(b):
        for n, g in ((0, 7), (1, 7), (2, 0), (3, 7)):
            b.pattern_bytes(n, spec.GROUP_AT, struct.pack("<H", g))
        b.m.uc.mem_write(live(b) + spec.GROUP_AT, struct.pack("<H", 7))

    def flip(b, at):
        b.m.uc.mem_write(live(b) + at, bytes([b.dev.read(live(b) + at, 1)[0] ^ 0x10]))

    box = Box(payload, flash)
    setup(box)
    flip(box, STEP)
    flip(box, P1 + 1)                 # a part's mute: carried
    flip(box, 36)                     # the pattern's own value: carried
    first = box.dirty()
    box.turn(1)
    out.append(entry("group_unsaved_loads_at_once", first and box.view() == (1, 1, 0) and box.flags()[0] in (0, 0xFFFFFFFF) and box.u32(spec.STATE + spec.S_STOPPED) == 0
                     and not box.m.asserts,
                     f"edited pattern 1 (group 7), a click to pattern 2 (group 7): running/chosen/pending {box.view()}, browse {box.flags()[0]:#x}"))
    box.turn(2)
    out.append(entry("group_unsaved_run_through", box.view() == (3, 3, 0) and not box.m.asserts,
                     f"two clicks on to pattern 4 (group 7) with the carried values differing from the bank: {box.view()}"))
    box.turn(-1)
    out.append(entry("group_carry_is_not_unsaved", box.view() == (2, 2, 0) and not box.m.asserts,
                     f"out of the group into pattern 3 (group 0) after only a carry: loads at once, {box.view()}"))
    # an edit after the carry is unsaved again
    ed = Box(payload, flash)
    setup(ed)
    flip(ed, P1 + 1)
    ed.turn(1)
    flip(ed, STEP)
    ed.turn(1)
    out.append(entry("group_edit_after_carry_browses", ed.view() == (1, 2, 1) and ed.flags()[0] == 1 and not ed.m.asserts,
                     f"into pattern 2 by the carry, a step changed, a click to pattern 3 (group 0): {ed.view()}, browse {ed.flags()[0]}"))
    mu = Box(payload, flash)
    setup(mu)
    mu.turn(1)
    flip(mu, P1 + 1)
    mu.turn(1)
    out.append(entry("group_carried_edit_browses", mu.view() == (1, 2, 1) and mu.flags()[0] == 1 and not mu.m.asserts,
                     f"into pattern 2 by the carry, a part's mute changed, a click to pattern 3 (group 0): {mu.view()}, browse {mu.flags()[0]}"))
    # a browse that is open, then a click onto a pattern of the group: loads
    br = Box(payload, flash)
    setup(br)
    flip(br, STEP)
    br.turn(2)
    opened = (br.view(), br.flags()[0])
    br.turn(1)
    out.append(entry("group_ends_an_open_browse", opened == ((0, 2, 1), 1) and br.view() == (3, 3, 0) and br.flags()[0] == 0 and not br.m.asserts,
                     f"edited pattern 1, browse to pattern 3 (group 0) {opened}; one more click to pattern 4 (group 7): {br.view()}, browse {br.flags()[0]}"))
    other = Box(payload, flash)
    setup(other)
    flip(other, STEP)
    other.turn(2)
    out.append(entry("other_group_unsaved_browses", other.view() == (0, 2, 1) and other.flags()[0] == 1 and other.dirty() and not other.m.asserts,
                     f"edited pattern 1 (group 7), a click to pattern 3 (group 0): browse as before, {other.view()}"))
    ref = Box(payload, flash, KILL)
    setup(ref)
    flip(ref, STEP)
    ref.turn(1)
    out.append(entry("group_unsaved_kill_switch_is_stock", ref.view() == (1, 1, 0) and ref.flags()[0] in (0, 0xFFFFFFFF), f"EXIT held at power-on: {ref.view()}"))
    return out


def case_view(payload, flash):
    """While a pattern is browsed or confirmed (VIEW:, NEXT:) the pads and the Edit info texts show that pattern, from the pattern bank, and
    go back when the browse or the confirmation ends; the pattern in RAM and the sound stay on what plays."""
    import re
    out = []
    CELL_W, CELL_O = 0xC0691388, 0xC069136C            # the Sampler's addresses, the device translates them for the synth
    STEP, PITCH = 0x800 + 0x30, 0x800 + 0x24
    live = lambda b: b.u32(0xC033E6A4) + 4

    def lit(b):
        """The pads that show red: steps that are on, parts that are not muted (the blue of the selected part is left out)."""
        return sorted(n for n in range(16) if b.m.leds.get(0x2C + 2 * n, 0))

    def info_text(b):
        """The text of the info line's widget (the label while one stands)."""
        page = b.dev.screen()["page"]
        return bytes(b.m.uc.mem_read(b.u32(page + 0x50), 40)).split(b"\0")[0].decode("latin-1")

    def cells(b):
        return b.u32(CELL_W), b.u32(CELL_O)

    def seed(b, live_steps=(0, 4, 8, 12), bank_steps=(1, 3, 5, 7)):
        for st in live_steps:
            b.m.uc.mem_write(live(b) + STEP + 12 * st, bytes([1]))
        for st in bank_steps:
            b.m.uc.mem_write(b.slots + 0x4000 + STEP + 12 * st, bytes([1]))
        b.m.uc.mem_write(live(b) + PITCH, bytes([0]))
        b.m.uc.mem_write(b.slots + 0x4000 + PITCH, bytes([20]))

    box = Box(payload, flash)
    seed(box, live_steps=(2, 6, 10, 14))
    box.dev.press(0x15, 0.4)                                  # SEQUENCER: the pads show the steps of the bar
    start = (lit(box), cells(box))
    box.turn(1)
    box.run(0.5)
    viewing = (box.view(), box.flags()[0], lit(box), cells(box))
    box.key("exit")
    box.run(0.5)
    back = (lit(box), cells(box))
    out.append(entry("view_pads_show_the_browsed_pattern", start[0] == [2, 6, 10, 14] and viewing[0] == (0, 1, 1) and viewing[1] == 1 and viewing[2] == [1, 3, 5, 7]
                     and viewing[3][0] == spec.VIEW_W and back == start and not box.m.asserts,
                     f"SEQUENCER, steps 2,6,10,14 in RAM, 1,3,5,7 in pattern 2: before {start[0]}, VIEW: {viewing[2]} through {viewing[3][0]:#x}, EXIT {back[0]}, "
                     f"pointers back {back[1] == start[1]}"))
    mutes = Box(payload, flash)
    seed(mutes)
    mutes.key("part_mute")
    live_mutes = lit(mutes)
    mutes.m.uc.mem_write(mutes.slots + 0x4000 + 0x800 + 1, bytes([mutes.dev.read(live(mutes) + 0x800 + 1, 1)[0] ^ 1]))
    mutes.turn(1)
    mutes.run(0.5)
    other = lit(mutes)
    mutes.key("exit")
    mutes.run(0.5)
    out.append(entry("view_pads_show_the_browsed_mutes", other != live_mutes and lit(mutes) == live_mutes and not mutes.m.asserts,
                     f"PART MUTE: pads in RAM {live_mutes}, part 1 muted the other way in pattern 2: VIEW: {other}, EXIT {lit(mutes)}"))
    info = Box(payload, flash)
    seed(info)
    info.turn(1)
    info.run(0.5)
    page = info.dev.screen()["page"]
    label = info_text(info)
    shown = []
    for _ in range(6):                       # the Edit key steps the line through Pitch and the rest
        info.dev.press(0x0C, 0.7)
        shown.append(info_text(info))
    pitch = shown[0]
    info.key("exit")
    info.run(0.8)
    for _ in range(5):                       # back to the first line the key showed
        info.dev.press(0x08, 0.7)
    after = info_text(info)
    out.append(entry("view_edit_key_shows_the_info_texts_of_the_browsed_pattern", label.startswith("VIEW:") and pitch.replace("\\", " ").split()[-1:] == ["20"]
                     and after.startswith("Pitch") and after.replace("\\", " ").split()[-1:] == ["0"] and not info.m.asserts,
                     f"VIEW: the line says {label!r}; the Edit key steps it: {shown}; after EXIT the same line is {after!r}"))
    play_box = Box(payload, flash)
    seed(play_box)
    play_box.dev.press(0x15, 0.4)
    play(play_box)
    play_box.run(0.3)
    play_box.turn(1)
    play_box.key("menu", 0.6)
    armed = (play_box.view(), play_box.flags()[1], cells(play_box)[0] == spec.VIEW_W)
    play_box.until_change()
    play_box.run(0.8)
    done = (play_box.running(), cells(play_box)[0] != spec.VIEW_W, play_box.flags()[1])
    out.append(entry("view_follows_the_confirmation_and_ends_at_the_switch", armed == ((0, 1, 1), 1, True) and done == (1, True, 0) and not play_box.m.asserts,
                     f"NEXT: running/chosen/pending, confirmed, pointer on the view {armed}; after the switch running, pointer back, confirmed {done}"))
    for name, kw in (("kill_switch", dict(held=KILL)), ("setting_off", {})):
        b = Box(payload, flash, **kw)
        seed(b)
        if name == "setting_off":
            b.set_setting(0)
        was = cells(b)
        b.turn(1)
        b.run(0.5)
        out.append(entry(f"view_{name}_is_stock", cells(b) == was and b.u32(spec.VIEW_W + spec.V_NUM) in (0xFFFFFFFF, 0) or cells(b) == was,
                         f"{name}: pointers {cells(b) == was}"))
    return out


def case_view_pads(payload, flash):
    """While a pattern is viewed its pads are the viewed pattern's (decision 29.10.): the playing pattern's mutes and steps cannot be
    switched, PART MUTE switches the viewed pattern's mutes, the switch to it takes them, and its pads have their own colour."""
    out = []
    MUTE, STEP = 0x800 + 1, 0x800 + 0x30
    live = lambda b: b.u32(0xC033E6A4) + 4

    def mutes(b, base):
        return [b.dev.read(base + MUTE + 0x330 * p, 1)[0] for p in range(16)]

    def red(b):
        return [b.m.leds.get(0x2C + 2 * n, 0) for n in range(16)]

    def blue(b):
        return [b.m.leds.get(0x2D + 2 * n, 0) for n in range(16)]

    def pad(b, n):
        b.m.send([4, n, 0, 100, 1])
        b.run(0.1)
        b.m.send([4, n, 0, 0, 0])
        b.run(0.4)

    def viewing(b):
        """Part mute mode, pattern 1 plays, pattern 2 (parts 2 and 3 muted in the bank) is browsed."""
        bank = b.slots + 0x4000
        for part in (1, 2):
            b.m.uc.mem_write(bank + MUTE + 0x330 * part, bytes([1]))
        b.key("part_mute")
        play(b)
        b.run(0.3)
        before = (red(b), blue(b))
        b.turn(1)
        b.run(0.5)
        return bank, before

    box = Box(payload, flash)
    bank, before = viewing(box)
    shown = (red(box), blue(box))
    pad(box, 0)
    pad(box, 1)
    toggled = (mutes(box, live(box))[:3], mutes(box, bank)[:3], red(box)[:3])
    out.append(entry("view_pads_switch_the_viewed_mutes_not_the_playing_ones",
                     box.view() == (0, 1, 1) and toggled == ([0, 0, 0], [0, 1, 1], [0, 255, 0]) and not box.m.asserts,
                     f"PART MUTE, pattern 2 viewed: pads 1 and 2 pressed; mutes in RAM {toggled[0]}, in the bank {toggled[1]}, pads 1 to 3 red {toggled[2]}"))
    out.append(entry("view_pads_have_their_own_colour",
                     before == ([255] * 16, [255] + [0] * 15) and shown[0][1:3] == [0, 0] and shown[0][3:] == [255] * 13 and shown[1][3:] == [255] * 13
                     and shown[0][0] == 255 and shown[1][0] == 0,
                     f"playing pattern: red {before[0]}, blue {before[1]}; viewed: red {shown[0]}, blue {shown[1]} (lit pads red and blue, the "
                     f"selected part in the colour left)"))
    box.key("menu", 0.6)
    box.until_change()
    box.run(0.8)
    after = (box.running(), mutes(box, live(box))[:4], mutes(box, bank)[:4], red(box), blue(box)[1:])
    out.append(entry("view_switch_takes_the_mutes_set_on_the_pads",
                     after[0] == 1 and after[1] == [1, 0, 1, 0] and after[2] == [0, 1, 1, 0] and after[3][:4] == [0, 255, 0, 255]
                     and after[4] == [0] * 15 and not box.m.asserts,
                     f"after MENU and the switch: running {after[0]}, mutes in RAM {after[1]} (bank {after[2]}), red {after[3][:4]}, "
                     f"blue of pads 2 to 16 {after[4][:4]}... (the playing pattern's colours again)"))

    back = Box(payload, flash)
    bank, _ = viewing(back)
    pad(back, 0)
    back.key("exit")
    back.run(0.5)
    dropped = (mutes(back, live(back))[:3], red(back)[:3])
    back.turn(1)
    back.run(0.5)
    again = red(back)[:3]
    out.append(entry("view_exit_drops_the_mutes_set_on_the_pads",
                     dropped == ([0, 0, 0], [255, 255, 255]) and again == [255, 0, 0] and not back.m.asserts,
                     f"pad 1 pressed while viewing, EXIT: mutes in RAM {dropped[0]}, pads {dropped[1]}; viewed again: pads {again} (the bank's)"))

    seq = Box(payload, flash)
    seq.m.uc.mem_write(live(seq) + STEP, bytes([1]))
    seq.dev.press(0x15, 0.4)
    play(seq)
    seq.run(0.3)
    seq.turn(1)
    seq.run(0.5)
    pad(seq, 0)
    pad(seq, 1)
    steps = [seq.dev.read(live(seq) + STEP + 12 * n, 1)[0] for n in range(2)]
    seq.key("exit")
    seq.run(0.5)
    pad(seq, 1)
    plain = seq.dev.read(live(seq) + STEP + 12, 1)[0]
    out.append(entry("view_sequencer_pads_leave_the_playing_steps",
                     steps == [1, 0] and plain == 1 and not seq.m.asserts,
                     f"SEQUENCER, pattern 2 viewed, pads 1 and 2 pressed: steps 1 and 2 in RAM {steps}; after EXIT pad 2 sets step 2: {plain}"))

    ref = Box(payload, flash, KILL)
    ref.key("part_mute")
    play(ref)
    ref.run(0.3)
    ref.turn(1)
    ref.run(0.5)
    pad(ref, 0)
    out.append(entry("view_pads_kill_switch_is_stock", mutes(ref, live(ref))[0] == 1 and not ref.m.asserts,
                     f"EXIT at power-on: pad 1 mutes part 1 of the pattern in RAM: {mutes(ref, live(ref))[0]}"))
    return out


GROUPS = (case_browse, case_confirm, case_exit, case_stopped, case_stop, case_chain, case_other_sources, case_wrap, case_off, case_mfx, case_unsaved,
          case_sync_group, case_sync_voices, case_sync_unsaved, case_view, case_view_pads)


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
