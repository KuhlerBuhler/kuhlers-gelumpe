# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the grooves-scales patch (tools/patch/grooves_scales.py, docs/messungen/2026-11-28-grooves-skalen-rot.md):
62 grooves and 70 scales on Korg's red build. The firmware builds its 25 grooves into the patch's table and they read as on
the unpatched firmware; the 37 new ones are selectable by setter and menu and the groove engine plays their steps; the 35
new scales are selectable, give their steps, name and chord object, the keyboard plays them; Korg's 35 scales are unchanged.

    tools/emu/.venv/bin/python tools/emu/grooves_scales_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import grooves_scales as spec  # noqa: E402
from machine import UART1, load_flash  # noqa: E402
from mfx_cases import Box, KEYS  # noqa: E402
import menu_cases  # noqa: E402
import lifetime  # noqa: E402
import parallel  # noqa: E402

IMAGE = 0xC0000000
PARTS = 0x400C                      # pattern object + this: what the part setters get in r0 (live_write_cases.py)
PART_BLOCK, PART_STRIDE, GROOVE_BYTE = 4 + 0x800, 0x330, 28
SET_GROOVE = 0xC0049DA4             # (pattern + PARTS, part, groove, notify), the Part menu's setter
ENGINE = 0xC0348910                 # *ENGINE is the object the groove readers take the part's groove from
GROOVE_OF = 0xC0048F34              # (object, part) -> the part's groove
READ_OFFSET, READ_VELOCITY, READ_GATE = 0xC00479CC, 0xC0047A2C, 0xC0047A8C   # (-, part, step) -> the groove's step value
SET_SCALE = 0xC004A77C              # (pattern, scale, notify), the Pattern menu's setter
SCALE_CLAMPED = 0xC0048608          # (scale, notify): clamps, then SET_SCALE on the pattern
SCALE_STATE = 0xC068BF7C            # +0x304 the scale index, +0x30C a pointer to its steps entry
SCALE_OBJECT = 0xC0055364           # () -> the chord object of the scale
SCALE_NAME = 0xC00545B0             # (scale) -> its name
PART_SCREEN, GROOVE_PAGE = 7, 17    # the Part menu, its page GROOVE (plugin_api24_cases.py)
PATTERN_SCREEN = 3
SET_KEY = 0xC004A6FC                # (pattern, key, notify)
KEYBOARD, CHORD = 0x17, 0x18        # the keys of the pads' modes (dice_cases.py)


def has_hooks(payload):
    """True when the groove readers point at the patch's table."""
    return struct.unpack_from("<I", payload, spec.GROOVE_LITERALS[0] - IMAGE)[0] == spec.GROOVES


def entry(name, ok, detail):
    return {"id": f"grooves-scales:{name}", "ok": bool(ok), "detail": str(detail)}


def unpatched(payload):
    """The copy with the literals and clamps of the firmware put back: Korg's own grooves and scales, the rest of the copy alike."""
    raw = bytearray(payload)
    for at in spec.GROOVE_LITERALS:
        struct.pack_into("<I", raw, at - IMAGE, spec.GROOVE_RAM)
    struct.pack_into("<I", raw, spec.GROOVE_NAME_LITERAL - IMAGE, spec.GROOVE_RAM + 0x10)
    for at, table in spec.SCALE_LITERALS.items():
        struct.pack_into("<I", raw, at - IMAGE, table)
    for at, (old, _) in {**spec.GROOVE_CLAMPS, **spec.SCALE_CLAMPS}.items():
        struct.pack_into("<I", raw, at - IMAGE, old)
    return bytes(raw)


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def part_groove(box, part=0):
    return box.raw(box.pattern() + PART_BLOCK + PART_STRIDE * part + GROOVE_BYTE, 1)[0]


def set_groove(box, value, part=0):
    box.dev.call(SET_GROOVE, box.pattern() + PARTS, part, value, 1)
    box.run(0.1)
    return part_groove(box, part)


def played(box, part=0, steps=64):
    """(offset, velocity, gate) the groove engine reads for each step of the part's groove."""
    out = []
    for step in range(steps):
        o = s32(box.dev.call(READ_OFFSET, 0, part, step))
        out.append((o, box.dev.call(READ_VELOCITY, 0, part, step) & 0xFF, box.dev.call(READ_GATE, 0, part, step) & 0xFF))
    return out


def pads(box, scale):
    """The note-ons of each of the 16 pads, one pad at a time, with the scale set."""
    box.dev.call(SET_SCALE, box.pattern(), scale, 0)
    box.run(0.3)
    out = []
    for n in range(16):
        start = len(box.m.uart[UART1]["tx"])
        box.m.send([4, n, 0, 100, 1])
        box.run(0.15)
        box.m.send([4, n, 0, 0, 0])
        box.run(0.15)
        out.append(note_ons(bytes(box.m.uart[UART1]["tx"][start:])))
    return out


def note_ons(data):
    """The notes of the note-ons in MIDI out bytes, with running status and real-time bytes in between."""
    out, status, cur = [], None, []
    for x in data:
        if x >= 0xF8:
            continue
        if x & 0x80:
            status, cur = x, []
            continue
        if status is None or status >= 0xF0:
            continue
        cur.append(x)
        if len(cur) == (1 if status & 0xF0 in (0xC0, 0xD0) else 2):
            if status & 0xF0 == 0x90 and cur[1]:
                out.append(cur[0])
            cur = []
    return out


# ------------------------------------------------------------------------------------------------- cases

def case_factory_grooves(payload, flash):
    """Korg's 25 grooves: the firmware builds them into the patch's table at start, byte for byte what it builds without the
    patch, and leaves its old RAM alone; Korg's 35 scale entries are copied unchanged."""
    box = Box(payload, flash)
    ours = box.raw(spec.GROOVES, spec.KORG_GROOVES * spec.TEMPLATE)
    old = box.raw(spec.GROOVE_RAM, spec.KORG_GROOVES * spec.TEMPLATE)
    plain = Box(unpatched(payload), flash)
    korg = plain.raw(spec.GROOVE_RAM, spec.KORG_GROOVES * spec.TEMPLATE)
    marks = all(korg[i * spec.TEMPLATE:i * spec.TEMPLATE + 4] == b"GVST" for i in range(spec.KORG_GROOVES))
    place, _ = spec.layout()
    same = []
    for table, size in ((spec.SCALE_STEPS, spec.STEP_ENTRY), (spec.SCALE_SNAP, spec.SNAP_ENTRY), (spec.SCALE_NAMES, 4), (spec.SCALE_OBJECTS, 4),
                        (spec.SCALE_PADS, spec.PAD_ENTRY)):
        key = {spec.SCALE_STEPS: "steps", spec.SCALE_SNAP: "snap", spec.SCALE_NAMES: "names", spec.SCALE_OBJECTS: "objects",
               spec.SCALE_PADS: "pads"}[table]
        n = spec.KORG_SCALES * size
        same.append(box.raw(place[key], n) == plain.raw(table, n))
    return [
        entry("factory_grooves_built_in_the_table", marks and ours == korg, f"25 GVST marks {marks}, equal {ours == korg}"),
        entry("old_groove_ram_untouched", old == bytes(len(old)), f"{sum(1 for b in old if b)} bytes written"),
        entry("factory_scale_entries_copied", all(same), same),
        entry("no_assert", not box.m.asserts and not plain.m.asserts, (box.m.asserts, plain.m.asserts)),
    ]


def case_groove_setter(payload, flash):
    """The setter takes 25 to 61 and sets 0 beyond (the firmware's rule, top moved from 24 to 61); the groove engine reads the
    new grooves' steps, the factory ones still theirs; a pattern plays with groove 61 without an assert."""
    box = Box(payload, flash)
    got = {v: set_groove(box, v) for v in (25, 40, 61, 62, 200)}
    engine = box.dev.u32(ENGINE)
    ok_reads, detail = True, []
    for g in (25, 33, 45, 61):
        set_groove(box, g)
        name, steps = spec.GROOVE_LIST[g - spec.KORG_GROOVES]
        want = [steps[i % len(steps)] for i in range(64)]
        have = played(box)
        if box.dev.call(GROOVE_OF, engine, 0) != g or have != want:
            ok_reads = False
            detail.append(f"{g} {name}: {have[:4]} want {want[:4]}")
    set_groove(box, 0)
    factory = played(box, steps=16)
    tpl = box.raw(spec.GROOVES, spec.TEMPLATE)
    from_table = [(struct.unpack("b", tpl[0x30 + 4 * i:0x31 + 4 * i])[0], tpl[0x31 + 4 * i], tpl[0x32 + 4 * i]) for i in range(16)]
    set_groove(box, 61)
    start = len(box.m.uart[UART1]["tx"])
    box.key("play", 1.5)
    box.key("stop", 0.3)
    out = bytes(box.m.uart[UART1]["tx"][start:])
    notes = sum(1 for i in range(len(out) - 2) if out[i] & 0xF0 == 0x90 and out[i + 2])
    return [
        entry("setter_takes_25_to_61", got == {25: 25, 40: 40, 61: 61, 62: 0, 200: 0}, got),
        entry("engine_plays_new_grooves", ok_reads, detail or "25, 33, 45, 61 over 64 steps"),
        entry("engine_plays_factory_groove", factory == from_table, factory[:4]),
        entry("plays_with_groove_61", notes > 0 and not box.m.asserts, f"{notes} notes, asserts {box.m.asserts}"),
    ]


def case_groove_menu(payload, flash):
    """The page GROOVE of the Part menu wraps 61 <-> 0 and steps through the new grooves."""
    box = Box(payload, flash)
    dev = box.dev
    menu_cases.go(dev, PART_SCREEN)
    for _ in range(40):
        if menu_cases.counter(dev)[0] == GROOVE_PAGE:
            break
        dev.press(KEYS["edit_next"], 0.25)
    page = menu_cases.counter(dev)[0]
    set_groove(box, 0)
    seen = []
    dev.turn(-1, 0.4)
    seen.append(part_groove(box))
    dev.turn(1, 0.4)
    seen.append(part_groove(box))
    set_groove(box, 24)
    for _ in range(3):
        dev.turn(1, 0.4)
        seen.append(part_groove(box))
    return [
        entry("menu_wraps_and_steps", page == GROOVE_PAGE and seen == [61, 0, 25, 26, 27], f"page {page}, {seen}"),
        entry("no_assert", not box.m.asserts, box.m.asserts),
    ]


def case_scales(payload, flash):
    """Scales 35 to 69: set, their steps, name and chord object; the chord rows are ours; the keyboard plays the scale."""
    box = Box(payload, flash)
    place, _ = spec.layout()
    bad = []
    for i, (name, steps) in enumerate(spec.SCALES):
        s = spec.KORG_SCALES + i
        box.dev.call(SET_SCALE, box.pattern(), s, 0)
        state = box.raw(SCALE_STATE + 0x304, 1)[0]
        entry_ = box.raw(box.raw32(SCALE_STATE + 0x30C), spec.STEP_ENTRY)
        text = box.raw(box.dev.call(SCALE_NAME, s), len(name) + 1)
        obj = box.dev.call(SCALE_OBJECT)
        vt, rows, variants, table = struct.unpack("<4I", box.raw(obj, 16))
        method = struct.unpack("<I", box.raw(vt + 8, 4))[0]
        row = box.dev.call(method, obj, rows - 1)
        want_row = spec.chord_table(steps)[(rows - 1) * spec.ROW:rows * spec.ROW]
        if (state, entry_, text, rows, variants) != (s, spec.scale_steps(steps), name.encode() + b"\0", len(steps), spec.VARIANTS) \
                or row != table + (rows - 1) * spec.ROW or box.raw(row, spec.ROW) != want_row:
            bad.append(f"{s} {name}: state {state} steps {entry_.hex()} name {text} rows {rows} row {row:#x}")
    box.dev.call(SET_KEY, box.pattern(), 0, 0)
    box.run(0.3)
    box.dev.press(KEYBOARD, 0.4)
    layouts = {s: [n[0] if n else None for n in pads(box, s)] for s in (35, 44, 69)}
    # pads 8 to 15 are the lower row, the first half of the table (0xC0044B04)
    play_ok = all(None not in n and [x - n[8] for x in n[8:] + n[:8]] == list(spec.pad_notes(spec.SCALES[s - spec.KORG_SCALES][1]))
                  for s, n in layouts.items())
    box.dev.press(CHORD, 0.4)
    chords, chord_ok = {}, True
    for s in (35, 44, 69):
        steps = spec.SCALES[s - spec.KORG_SCALES][1]
        table = spec.chord_table(steps)
        shapes = set()
        for k in range(0, len(table), 8):
            e = table[k:k + 8]
            notes = [b - 256 if b > 127 else b for b in e[3:3 + e[2]]]
            shapes.add(tuple(x - notes[0] for x in notes))
        chords[s] = pads(box, s)
        for notes in chords[s]:
            notes = sorted(notes)
            if len(notes) < 2 or tuple(x - notes[0] for x in notes) not in shapes or not {x % 12 for x in notes} <= set(steps):
                chord_ok = False
    clamped = box.dev.call(SCALE_CLAMPED, 69, 0) is not None and box.raw(box.pattern() + 4 + 40, 1)[0]
    return [
        entry("new_scales_set_name_steps_chords", not bad, bad[:3] or "35 to 69"),
        entry("keyboard_plays_new_scales", play_ok, layouts),
        entry("chord_pads_play_our_chords", chord_ok, {s: c[:4] for s, c in chords.items()}),
        entry("clamped_setter_takes_69", clamped == 69, clamped),
        entry("no_assert", not box.m.asserts, box.m.asserts),
    ]


def case_scale_menu(payload, flash):
    """The scale page of the Pattern menu goes past Korg's 34 to 69 and stops there."""
    box = Box(payload, flash)
    dev = box.dev
    byte = lambda: box.raw(box.pattern() + 4 + 40, 1)[0]     # noqa: E731
    menu_cases.go(dev, PATTERN_SCREEN)
    page = None
    for _ in range(30):
        dev.call(SET_SCALE, box.pattern(), 33, 0)
        before = byte()
        dev.turn(1, 0.3)
        if byte() != before:
            page = menu_cases.counter(dev)[0]
            break
        dev.press(KEYS["edit_next"], 0.25)
    seen = [byte()]
    for _ in range(2):
        dev.turn(1, 0.3)
        seen.append(byte())
    dev.call(SET_SCALE, box.pattern(), 68, 0)
    for _ in range(2):
        dev.turn(1, 0.3)
        seen.append(byte())
    return [
        entry("menu_reaches_69", page is not None and seen == [34, 35, 36, 69, 69], f"page {page}, {seen}"),
        entry("no_assert", not box.m.asserts, box.m.asserts),
    ]


GROUPS = (case_factory_grooves, case_groove_setter, case_groove_menu, case_scales, case_scale_menu)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash) if i < len(GROUPS) else []


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    p.add_argument("--only", type=int)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    payload = raw[0x100:] if len(raw) == 0x200100 else raw
    flash = load_flash([a.flash]) if a.flash else None
    if not has_hooks(payload):
        raise SystemExit("this copy does not carry the grooves-scales patch")
    found = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(found, indent=1))
    raise SystemExit(0 if all(e["ok"] for e in found) else 1)


if __name__ == "__main__":
    main()
