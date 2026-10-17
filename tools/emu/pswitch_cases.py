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
KEYS = {"play": 2, "stop": 1, "menu": 9, "exit": 0x0D, "shift": 0x0A}
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

    def __init__(self, payload, flash=None, held=0, card=True, seconds=3.0):
        self.payload = bytes(payload)
        for_build(self.payload)
        self.dev = Dev(self.payload, flash, held)
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

    def view(self):
        """What the pattern selection shows: (running, chosen, pending)."""
        return self.running(), self.chosen(), self.pending()

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
        return self.dev.screen()["number"], bytes(self.dev.fb())


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
        fb = bytes(box.dev.fb())
        now = {i // 128 for i in range(1024) if fb[i] != ref2.dev.fb()[i]}
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
    for b in (ref, box):
        play(b)
        b.mark()
        b.turn(3)
        b.key("menu")
    ref_end, box_end = ref.until_change(), box.until_change()
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


GROUPS = (case_browse, case_confirm, case_exit, case_stopped, case_stop, case_chain, case_other_sources, case_wrap, case_off, case_mfx)


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
