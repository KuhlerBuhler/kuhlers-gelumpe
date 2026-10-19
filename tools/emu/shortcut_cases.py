# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the EXIT shortcuts of the BLECH runtime (tools/patch/script_shortcuts.s,
docs/messungen/2026-10-19-exit-shortcuts.md).

check.py runs `cases` on every patched sampler copy that carries the BLECH menu. With EXIT held on the main screen, WRITE
saves the edited pattern into its own place (through the firmware's Write window) and a pad puts the sound of a part back to
the values saved in the bank, the steps and the other parts left as they are. WRITE alone still only opens the window, and with
EXIT held at power-on both are the firmware's.

    tools/emu/.venv/bin/python tools/emu/shortcut_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from pswitch_cases import Box, play  # noqa: E402

PATPTR = 0xC033E6A4
LEDMGR = 0xC0345A1C
EXIT, WRITE, TRIGGER, SEQUENCER = 0x0D, 0x0E, 0x13, 0x15
WRITE_LED = 0x0B
WINDOW = 18                     # the firmware's Write window
PART, STRIDE, SOUND = 0x800, 0x330, range(2, 0x30)
STEPS = 0x30                    # the steps of a part start here, 12 bytes each
KILL = menu_cases.KILL


def has_hooks(payload):
    return menu_cases.has_menu(payload) and not synthaddr.is_synth(payload)


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
    box.m.send([2, 0, 0, 200, 0])
    box.run(0.5)
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
    plain.m.send([2, 0, 0, 200, 0])
    plain.run(0.5)
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


def case_kill(payload, flash):
    box = SBox(payload, flash, held=KILL)
    box.m.send([2, 0, 0, 200, 0])
    box.run(0.5)
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
    box.m.send([2, 0, 0, 200, 0])
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
    return [entry("pad_state_is_not_an_edit", rewritten and not rest and seen == {0} and not box.m.asserts,
                  f"pattern {box.running()}, byte 0x3C live {live[0x3C]} saved {saved[0x3C]}, other differences {rest[:8]}, WRITE LED {sorted(seen)}")]


GROUPS = (case_save, case_reset, case_kill, case_unsaved, case_pad_state)


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
