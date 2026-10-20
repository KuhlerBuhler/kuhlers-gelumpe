# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the synth filters patch (tools/patch/synth_filters.py, docs/messungen/2026-10-15-synth-filter.md).

check.py runs `cases` on every patched copy that carries the patch's hooks (Korg's build only). The LPF, HPF and BPF keys walk through the
filter families the way Hacktribe's firmware does, the part keeps the type it is given (key or pattern load), the display shows the type's
name, the LED of the key stays lit, and a pattern with a synth type is written and read back as it was. With EXIT held at power-on the
firmware is exactly as it was: its keys know OFF and the electribe filters only, and it folds every other type onto them.

The expected key table is what Hacktribe's firmware was measured to do in the emulator (docs/messungen/2026-10-15-synth-filter.md): the
same presses on Hacktribe's SYSTEM.VSB gave these types, these LEDs and these display frames. With E2_HACKTRIBE_VSB set to that file the cases
also run the keys on it and compare the frames of the display (the patched copy must then carry this patch alone, the BLECH theme changes the frames), the part byte and the LEDs press by press (local only, like E2_VSB).

    tools/emu/.venv/bin/python tools/emu/synth_filter_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import synth_filters as spec  # noqa: E402
from machine import load_flash  # noqa: E402
from pswitch_cases import Box  # noqa: E402

IMAGE = 0xC0000000
PATTERN_PTR = 0xC033E6A4
FILTER_TYPE = 0x810              # in the pattern object, part 1; 0x330 per part
PART_STRIDE = 0x330
SLOTS = 0xC08B2940               # the pattern bank in RAM, 0x4000 per pattern
SLOT_FILTER_TYPE = 0x80C         # in the stored pattern block, part 1
NAME_LIST = 0xC00785C0           # pointers to the names of the types 1 to 16, read when the display draws one
NOTIFY = 0xC004B208              # (this, part, parameter, value): the firmware's message that a parameter changed
PARAM_FILTER_TYPE = 29
KEYS = {"lpf": 0x12, "hpf": 0x14, "bpf": 0x16, "write": 0x0E, "menu": 0x09}
LEDS = (0x0C, 0x0D, 0x0E)        # LPF, HPF, BPF
KILL = spec.KILL_SWITCH

NAMES = {1: "electribe LPF", 2: "MS20 LPF", 3: "MG   LPF", 4: "P5 LPF", 5: "OB LPF", 6: "Acid LPF",
         7: "electribe HPF", 8: "MS20 HPF", 9: "P5 HPF", 10: "OB HPF", 11: "Acid HPF",
         12: "electribe BPF", 13: "MS20 BPF", 14: "P5 BPF", 15: "OB BPF", 16: "Acid BPF"}

# What Hacktribe's keys do, from the current type 0 to 16 (rows) for LPF, HPF and BPF (columns). Measured in the emulator.
MEASURED = [
    (1, 7, 12), (2, 7, 12), (3, 8, 13), (4, 7, 12), (5, 9, 14), (6, 10, 15), (0, 11, 16), (1, 8, 12), (2, 9, 13),
    (4, 10, 14), (5, 11, 15), (6, 0, 16), (1, 7, 13), (2, 8, 14), (4, 9, 15), (5, 10, 16), (6, 11, 0),
]
CYCLES = {"lpf": [2, 3, 4, 5, 6, 0, 1, 2], "hpf": [7, 8, 9, 10, 11, 0, 7, 8], "bpf": [12, 13, 14, 15, 16, 0, 12, 13]}
FOLDED = {**{t: 1 for t in (2, 3, 4, 5, 6)}, **{t: 7 for t in (8, 9, 10, 11)}, **{t: 12 for t in (13, 14, 15, 16)}}   # what Korg's setter makes of a type


def has_hooks(payload):
    """True when the key handler's hook site branches into the patch's code."""
    word = struct.unpack_from("<I", payload, spec.SELECT_HOOK - IMAGE)[0]
    return word >> 24 == 0xEA and spec.CODE_AT <= spec.SELECT_HOOK + 8 + ((word & 0xFFFFFF) << 2) < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"synthfilter:{name}", "ok": bool(ok), "detail": str(detail)}


def lit(t):
    """The LEDs of LPF, HPF and BPF for a part type: the key of its family is lit."""
    return tuple(255 if spec.family(t) == k and t else 0 for k in (spec.LPF, spec.HPF, spec.BPF))


class FBox(Box):
    """A booted device with the helpers of these cases; records which name the display looks up and the parameter messages.
    On mains power: on battery power save dims every LED to a quarter (pad-colors, menu_cases checks it)."""

    def __init__(self, payload, flash=None, held=0):
        super().__init__(payload, flash, held, adapter=True)
        import unicorn
        self.names_read, self.notices = [], []
        uc = self.m.uc
        arm = self.m.A
        uc.hook_add(unicorn.UC_HOOK_MEM_READ, lambda u, a, addr, s, v, d: self.names_read.append(addr), begin=NAME_LIST, end=NAME_LIST + 0x43)
        uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: self.notices.append(
            tuple(u.reg_read(r) & 0xFFFFFFFF for r in (arm.UC_ARM_REG_R1, arm.UC_ARM_REG_R2, arm.UC_ARM_REG_R3))), begin=NOTIFY, end=NOTIFY)
        uc.ctl_flush_tb()

    def pat(self):
        return self.u32(PATTERN_PTR)

    def ftype(self, part=0):
        return self.dev.read(self.pat() + FILTER_TYPE + PART_STRIDE * part, 1)[0]

    def set_ftype(self, value, part=0):
        self.m.uc.mem_write(self.pat() + FILTER_TYPE + PART_STRIDE * part, bytes([value]))

    def slot_type(self, number):
        return self.dev.read(SLOTS + number * 0x4000 + SLOT_FILTER_TYPE, 1)[0]

    def set_slot_type(self, number, value):
        self.m.uc.mem_write(SLOTS + number * 0x4000 + SLOT_FILTER_TYPE, bytes([value]))

    def leds(self):
        return tuple(self.m.leds.get(x, 0) for x in LEDS)

    def frame(self):
        return bytes(self.dev.fb())

    def press(self, name, wait=0.4):
        """A key; returns (stored type, LEDs, frame, the names the display looked up (type numbers), the notices of the parameter change)."""
        self.names_read.clear()
        self.notices.clear()
        self.dev.press(KEYS[name], wait)
        return self.look()

    def look(self):
        looked = sorted({(a - NAME_LIST) // 4 + 1 for a in self.names_read})
        return self.ftype(), self.leds(), self.frame(), looked, [n for n in self.notices if n[1] == PARAM_FILTER_TYPE]

    def name_of(self, number):
        """The text of a type's name as the firmware's list has it."""
        pointer = self.u32(NAME_LIST + 4 * (number - 1))
        return bytes(self.dev.read(pointer, 24)).split(b"\0")[0].decode("latin1")


def hacktribe_payload():
    path = os.environ.get("E2_HACKTRIBE_VSB")
    return Path(path).read_bytes()[0x100:] if path else None


def case_cycle(key):
    """Each press from the electribe filter on: the type, the LED of the key, the name the display looks up, the parameter message."""

    def run(payload, flash):
        out = []
        box = FBox(payload, flash)
        seen, rows = [], []
        for want in CYCLES[key]:
            t, leds, frame, looked, notices = box.press(key)
            rows.append(t)
            seen.append((want, t, leds == lit(t), looked == ([want] if want else looked) and (want == 0 or box.name_of(want) == NAMES[want]),
                         notices == [(0, PARAM_FILTER_TYPE, want)], frame))
        out.append(entry(f"{key}_cycle", rows == CYCLES[key], f"{key.upper()} pressed {len(rows)} times from the electribe filter: {rows}, expected {CYCLES[key]}"))
        out.append(entry(f"{key}_leds", all(s[2] for s in seen), f"the LED of {key.upper()} follows the family of the type: {[s[2] for s in seen]}"))
        out.append(entry(f"{key}_names", all(s[3] for s in seen), f"the display looks up the name of the type it shows ({', '.join(NAMES[w] for w in CYCLES[key] if w)}): {[s[3] for s in seen]}"))
        out.append(entry(f"{key}_message", all(s[4] for s in seen), f"each press gives one parameter message for the filter type with the new type as value: {[s[4] for s in seen]}"))
        frames = {s[0]: s[5] for s in seen}
        out.append(entry(f"{key}_frames", len(set(frames.values())) == len(frames) and all(s[5] == frames[s[0]] for s in seen),
                         f"every type has a frame of its own and the same one each time it comes round ({len(frames)} types)"))
        # the table, from every current type, with the part byte set directly
        wrong = []
        for current, row in enumerate(MEASURED):
            box.set_ftype(current)
            box.run(0.2)
            got = box.press(key)[0]
            if got != row[("lpf", "hpf", "bpf").index(key)]:
                wrong.append((current, got, row[("lpf", "hpf", "bpf").index(key)]))
        for current in (17, 40, 255):
            box.set_ftype(current)
            box.run(0.2)
            got = box.press(key)[0]
            if got != 0:
                wrong.append((current, got, 0))
        out.append(entry(f"{key}_table", not wrong, f"{key.upper()} from every current type 0 to 16 and above 16 gives what Hacktribe's keys give; deviations (current, got, wanted): {wrong}"))
        ref = hacktribe_payload()
        if ref is not None:
            out.append(hacktribe_entry(key, payload, ref, flash))
        return out
    return run


def hacktribe_entry(key, payload, ref, flash):
    """Local only: the same presses on Hacktribe's firmware give the same part byte, LEDs and frames, press by press."""
    mine, theirs = FBox(payload, flash), FBox(ref, flash)
    diffs = []
    for i in range(14):
        a, b = mine.press(key), theirs.press(key)
        if a[:3] != b[:3]:
            diffs.append(i)
    return entry(f"{key}_equals_hacktribe", not diffs, f"{key.upper()} 14 presses on the patched copy and on Hacktribe's firmware: type, LEDs and display frame equal; presses that differ: {diffs}")


def case_stock_frames(payload, flash):
    """Filter frames before the popup expires, with DISPLAY INVERT off on both paths."""
    on, off = FBox(payload, flash), FBox(payload, flash, KILL)
    import menu_cases
    if menu_cases.has_menu(payload):
        on.m.uc.mem_write(menu_cases.STATE + menu_cases.S_INVERT, struct.pack("<I", 0))
    on.run(0.3)
    off.run(0.3)
    frames = {}
    for _ in range(7):
        t, _, frame, _, _ = on.press("lpf", wait=0.2)
        frames.setdefault(t, frame)
    for key in ("hpf", "bpf"):
        on.set_ftype(0)
        t, _, frame, _, _ = on.press(key, wait=0.2)
        frames.setdefault(t, frame)
    stock = {}
    for key in ("lpf", "lpf", "hpf", "bpf"):
        t, _, frame, _, _ = off.press(key, wait=0.2)
        stock.setdefault(t, frame)
    same = {t: frames.get(t) == stock.get(t) for t in (0, 1, 7, 12)}
    return [entry("electribe_frames_are_korgs", all(same.values()) and set(stock) == {0, 1, 7, 12},
                  f"the frames of OFF, electribe LPF, HPF and BPF equal those of the firmware with EXIT held at power-on: {same}")]


def case_load(payload, flash):
    """A pattern that carries a synth type keeps it when it is selected (the part setter no longer folds it); a type above 16 is the electribe LPF."""
    box = FBox(payload, flash)
    rows = {}
    for t in (*range(2, 7), *range(8, 12), *range(13, 17), 17, 40):
        box.set_slot_type(1, t)
        box.dev.turn(1, 0.6)
        rows[t] = (box.ftype(), box.leds(), box.slot_type(1))
        box.dev.turn(-1, 0.6)
    want = {t: (t if t <= 16 else 1) for t in rows}
    return [entry("load_keeps_type", {t: r[0] for t, r in rows.items()} == want and all(r[1] == lit(want[t]) for t, r in rows.items()),
                  f"patterns with a part 1 type of {sorted(rows)} select to {{{', '.join(f'{t}: {r[0]}' for t, r in rows.items())}}}, the LED of the family lit"),
            entry("load_leaves_slot", all(r[2] == t for t, r in rows.items()), "selecting a pattern leaves the stored type in the slot as it was")]


def case_roundtrip(payload, flash):
    """A synth type made with the keys is written, the pattern is left and selected again, and the type is the same."""
    box = FBox(payload, flash)
    box.press("lpf")
    box.press("lpf")                           # MG
    before = box.ftype()
    box.dev.press(KEYS["write"], 0.6)
    box.dev.press(KEYS["write"], 0.6)
    box.dev.press(KEYS["menu"], 0.6)
    box.run(1.0)
    written = box.slot_type(0)
    box.dev.turn(1, 0.6)
    away = box.ftype()
    box.dev.turn(-1, 0.6)
    back = box.ftype()
    return [entry("roundtrip", before == 3 and written == 3 and back == 3,
                  f"LPF twice (type {before}), WRITE: the slot holds {written}; the next pattern has {away} (its own), back at this one the part has {back}")]


def case_stock(payload, flash):
    """With EXIT held at power-on: Korg's keys (OFF and the electribe filters), Korg's folding of the synth types when a pattern is selected,
    and the loss when such a pattern is written."""
    box = FBox(payload, flash, KILL)
    rows = {k: [box.press(k)[0] for _ in range(3)] for k in ("lpf", "hpf", "bpf")}
    keys_ok = rows == {"lpf": [0, 1, 0], "hpf": [7, 0, 7], "bpf": [12, 0, 12]}
    box.set_ftype(1)
    got = {}
    for t in (*range(2, 7), *range(8, 12), *range(13, 17), 17, 40):
        box.set_slot_type(1, t)
        box.dev.turn(1, 0.6)
        got[t] = box.ftype()
        box.dev.turn(-1, 0.6)
    want = {t: FOLDED.get(t, 1) for t in got}
    # a pattern with a synth type, written: the folded type is what the slot keeps
    box.set_slot_type(1, 5)
    box.dev.turn(1, 0.6)
    box.dev.press(KEYS["write"], 0.6)
    box.dev.press(KEYS["write"], 0.6)
    box.dev.press(KEYS["menu"], 0.6)
    box.run(1.0)
    lost = box.slot_type(1)
    return [entry("kill_keys_are_korgs", keys_ok, f"EXIT held at power-on: three presses of LPF, HPF, BPF from the electribe LPF give {rows}"),
            entry("kill_folds_synth_types", got == want, f"EXIT held at power-on: patterns with a part 1 type of {sorted(got)} select to {got} (2 to 6 to 1, 8 to 11 to 7, 13 to 16 to 12, above 16 to 1)"),
            entry("kill_write_loses_type", lost == 1, f"EXIT held at power-on: a pattern stored with a part 1 type of 5, selected and written, keeps {lost} in its slot (the folded type)")]


GROUPS = (case_cycle("lpf"), case_cycle("hpf"), case_cycle("bpf"), case_stock_frames, case_load, case_roundtrip, case_stock)


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
