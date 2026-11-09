# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the touch-scale-zero patch (tools/patch/touch_scale_zero.py, docs/messungen/2026-10-30-touch-scale-null.md):
the page TOUCH SCALE RANGE of the Global menu takes 0, and with 0 the touch pad's X plays the pattern's key note in the
keyboard's octave, wherever it is pressed. Ranges 1 to 4 play what Korg's firmware plays (the table below, measured on the
unpatched firmware of all three builds).

    tools/emu/.venv/bin/python tools/emu/touch_scale_zero_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import synthaddr  # noqa: E402
import touch_scale_zero as spec  # noqa: E402
from machine import UART1, load_flash  # noqa: E402
from mfx_cases import Box, blank_for, press_seq  # noqa: E402
from splash_cases import go_to_global  # noqa: E402

IMAGE = 0xC0000000
TOUCH = 0xC06911E4                  # the touch scale object: +0x14 the range, +0x18 the keyboard's octave (synth from data/synth-map/)
RANGE_AT, OCTAVE_AT = 0x14, 0x18
GLOBALS_PTR = 0xC033E6A0            # *ptr + 4 is the live global block, byte 38 the range (docs/messungen/2026-10-14-global-felder.md)
GLOBAL_RANGE = 38
GLOBAL_FLASH = 0x230000             # the stored global block (docs/messungen/2026-10-13-globals-zurueckgesetzt.md)
PATTERN_PTR = 0xC033E6A4
SET_KEY = 0xC004A6FC                # (pattern, value, notify): the setter the Pattern menu calls
RANGE_PAGE = 11                     # TOUCH SCALE RANGE is page 12/20 of the Global menu
KEYS = {"keyboard": 0x17, "bar1": 0x1C, "bar4": 0x1F}
XS = (0, 128, 256, 384, 512, 640, 768, 896, 1023)
# Notes at XS on the unpatched firmware (Hacktribe, Korg's red and blue 2.02 alike), boot pattern, key C, keyboard octave 4.
STOCK = {
    1: [48, 50, 51, 53, 55, 57, 58, 60, 60],
    2: [48, 50, 53, 57, 60, 63, 67, 70, 72],
    3: [48, 51, 57, 62, 67, 70, 75, 81, 84],
    4: [48, 53, 60, 65, 72, 79, 84, 91, 96],
}


def for_build(payload):
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hooks(payload):
    """True when the page's clamp takes 0 (movle r1, #0 where the firmware has movle r1, #1)."""
    for_build(payload)
    at = spec.MENU_MOV - IMAGE
    return struct.unpack_from("<I", payload, at)[0] == spec.MOVLE_0


def entry(name, ok, detail):
    return {"id": f"touchscalezero:{name}", "ok": bool(ok), "detail": str(detail)}


# ------------------------------------------------------------------------------------------------- helpers

def touch_object(box):
    return box.dev.a(TOUCH)


def set_range(box, value):
    box.m.uc.mem_write(touch_object(box) + RANGE_AT, struct.pack("<I", value))


def touch_scale(box):
    """The firmware's Touch Scale mode (SHIFT + TOUCH SCALE with BLECH, TOUCH SCALE is MFX 2 there)."""
    press_seq(box, "shift_touch_scale", 0.5)
    return box.mode()


def notes_out(box, start):
    data = bytes(box.m.uart[UART1]["tx"][start:])
    return [data[i + 1] for i in range(len(data) - 2) if data[i] & 0xF0 == 0x90 and data[i + 2] > 0]


def touch(box, x, y=500, hold=0.3):
    """The note-ons of one touch at (x, y)."""
    start = len(box.m.uart[UART1]["tx"])
    box.m.press(0x22, True)
    box.m.send([0x05, x >> 8, x & 0xFF, y >> 8, y & 0xFF])
    box.run(hold)
    box.m.press(0x22, False)
    box.run(0.2)
    return notes_out(box, start)


def sweep(box, xs=XS):
    return [touch(box, x) for x in xs]


def single(notes):
    """[[n], [n], ...] as [n, n, ...], None where a touch played no note or more than one."""
    return [n[0] if len(n) == 1 else None for n in notes]


def arp_timed(box, y, pad=2, seconds=2.0):
    """(time in ms, status, note, velocity) of the channel messages while the sequencer plays, a trigger pad is held and the
    touch pad is touched at X 500 and the given Y; the box is in Gate Arp + Touch Scale."""
    box.key("play", 0.5)
    tx = box.m.uart[UART1]["tx"]
    box.m.send([0x04, pad, 0, 100, 1])
    box.run(0.2)
    box.m.press(0x22, True)
    box.m.send([0x05, 500 >> 8, 500 & 0xFF, y >> 8, y & 0xFF])
    out, status, cur, t0 = [], None, [], box.m.time_ns
    seen = len(tx)
    for _ in range(int(seconds / 0.01)):
        box.run(0.01)
        for byte in bytes(tx[seen:]):
            if byte >= 0xF8:
                continue
            if byte & 0x80:
                status, cur = byte, []
                continue
            cur.append(byte)
            if status is not None and len(cur) == 2:
                out.append(((box.m.time_ns - t0) // 1_000_000, status & 0xF0, cur[0], cur[1]))
                cur = []
        seen = len(tx)
    box.m.press(0x22, False)
    box.m.send([0x04, pad, 0, 0, 0])
    box.run(0.3)
    box.key("stop", 0.3)
    return out


def gate_lengths(messages, notes):
    """The time from each note-on of one of `notes` to its note-off, in ms."""
    on, lengths = {}, []
    for t, status, note, vel in messages:
        if note not in notes:
            continue
        if status == 0x90 and vel > 0:
            on[note] = t
        elif (status == 0x80 or (status == 0x90 and vel == 0)) and note in on:
            lengths.append(t - on.pop(note))
    return lengths


def flash_with_range(payload, value):
    """A blank flash of the build whose stored global block is the firmware's default with the range byte set."""
    flash = blank_for(payload)
    start = payload.find(b"GLST")
    while start >= 0 and payload[start + 252:start + 256] != b"GLED":
        start = payload.find(b"GLST", start + 1)
    block = bytearray(payload[start:start + 256])
    block[GLOBAL_RANGE] = value
    flash[GLOBAL_FLASH:GLOBAL_FLASH + 256] = block
    return bytes(flash)


# ------------------------------------------------------------------------------------------------- cases

def case_menu(payload, flash):
    """The page TOUCH SCALE RANGE steps 4 down to 0 and stops there, back up to 4 and stops; the touch scale object follows."""
    for_build(payload)
    box = Box(payload, flash)
    dev = box.dev
    go_to_global(dev)
    for _ in range(25):
        if dev.screen()["page"] == RANGE_PAGE:
            break
        dev.press("edit_next", 0.2)
    page = dev.screen()["page"]
    glob = dev.u32(GLOBALS_PTR) + 4
    byte = lambda: dev.read(glob + GLOBAL_RANGE, 1)[0]        # noqa: E731
    obj = lambda: box.raw32(touch_object(box) + RANGE_AT)      # noqa: E731
    for _ in range(4):
        dev.turn(1, 0.25)
    down, objs = [], []
    for _ in range(6):
        dev.turn(-1, 0.3)
        down.append(byte())
        objs.append(obj())
    up = []
    for _ in range(6):
        dev.turn(1, 0.3)
        up.append(byte())
    return [
        entry("page_goes_to_0", page == RANGE_PAGE and down == [3, 2, 1, 0, 0, 0] and up == [1, 2, 3, 4, 4, 4],
              f"page {page}, down {down}, up {up}"),
        entry("object_follows", objs == down, f"range in the touch scale object {objs}"),
        entry("no_assert", not box.m.asserts, box.m.asserts),
    ]


def case_notes(payload, flash):
    """Ranges 1 to 4 play Korg's notes; range 0 plays the key note (C4 with key C) wherever X is."""
    for_build(payload)
    box = Box(payload, flash)
    mode = touch_scale(box)
    got = {}
    for r in (1, 2, 3, 4, 0):
        set_range(box, r)
        got[r] = single(sweep(box))
    out = [entry("touch_scale_mode", mode == 1, f"mode {mode} after SHIFT + TOUCH SCALE")]
    for r in (1, 2, 3, 4):
        out.append(entry(f"range_{r}_as_korg", got[r] == STOCK[r], f"{got[r]}, Korg {STOCK[r]}"))
    out.append(entry("range_0_key_note", got[0] == [60] * len(XS), f"{got[0]} for X {list(XS)}"))
    out.append(entry("no_assert", not box.m.asserts, box.m.asserts))
    return out


def case_octave(payload, flash):
    """KEYBOARD + 4 and KEYBOARD + 1 shift the fixed note by an octave each, as they shift the keyboard's pad 1."""
    for_build(payload)
    box = Box(payload, flash)
    touch_scale(box)
    set_range(box, 0)
    base = single(sweep(box, (0, 1023)))
    box.dev.press(KEYS["keyboard"], 0.4)
    box.dev.press(KEYS["bar4"], 0.4)
    up = single(sweep(box, (0, 1023)))
    start = len(box.m.uart[UART1]["tx"])
    box.pad(0, 0.3)
    pad1 = notes_out(box, start)
    box.dev.press(KEYS["bar1"], 0.4)
    box.dev.press(KEYS["bar1"], 0.4)
    down = single(sweep(box, (0, 1023)))
    octave = box.raw32(touch_object(box) + OCTAVE_AT)
    return [
        entry("octave_up", base == [60, 60] and up == [72, 72] and pad1 == [72], f"start {base}, after 4: {up} (pad 1 plays {pad1})"),
        entry("octave_down", down == [48, 48] and octave == 3, f"after 1 twice: {down}, keyboard octave {octave}"),
    ]


def case_key(payload, flash):
    """The fixed note is the pattern's key: D gives D4 (62), A gives A4 (69); ranges 1 to 4 start on it an octave lower."""
    for_build(payload)
    box = Box(payload, flash)
    touch_scale(box)
    out = []
    for key, note in ((2, 62), (9, 69)):
        box.dev.call(SET_KEY, box.dev.u32(PATTERN_PTR), key, 1)
        box.run(0.3)
        set_range(box, 0)
        zero = single(sweep(box, (0, 512, 1023)))
        set_range(box, 1)
        one = single(sweep(box, (0,)))
        out.append(entry(f"key_{key}", zero == [note] * 3 and one == [note - 12], f"range 0: {zero}, range 1 at X 0: {one}"))
    return out


def case_gate_arp(payload, flash):
    """Gate Arp + Touch Scale (GATE ARP with BLECH): range 0 repeats the key note with the pad's note, Y still sets the gate length."""
    for_build(payload)
    out = []
    lengths = {}
    for y in (100, 900):
        box = Box(payload, flash)
        box.dev.call(SET_KEY, box.dev.u32(PATTERN_PTR), 2, 1)       # key D: the scale note (62) is not the pad's (60)
        box.run(0.3)
        press_seq(box, "gate_arp", 0.5)
        set_range(box, 0)
        mode = box.mode()
        msgs = arp_timed(box, y)
        ons = sorted({n for _, s, n, v in msgs if s == 0x90 and v > 0})
        lengths[y] = gate_lengths(msgs, {62})
        out.append(entry(f"notes_y{y}", mode == 3 and ons == [60, 62], f"mode {mode}, notes {ons}"))
    short, long_ = (sum(lengths[y]) / len(lengths[y]) if lengths[y] else None for y in (100, 900))
    out.append(entry("y_sets_length", short is not None and long_ is not None and short != long_,
                     f"mean gate of the key note at Y 100: {short} ms, at Y 900: {long_} ms"))
    return out


def case_boot(payload, flash):
    """A stored range 0 comes back after power-on: the global block keeps it and the touch pad plays the key note."""
    for_build(payload)
    box = Box(payload, flash_with_range(payload, 0))
    glob = box.dev.u32(GLOBALS_PTR) + 4
    stored = box.dev.read(glob + GLOBAL_RANGE, 1)[0]
    obj = box.raw32(touch_object(box) + RANGE_AT)
    touch_scale(box)
    notes = single(sweep(box, (0, 1023)))
    return [entry("range_0_after_power_on", stored == 0 and obj == 0 and notes == [60, 60],
                  f"global byte {stored}, object {obj}, notes {notes}")]


GROUPS = (case_menu, case_notes, case_octave, case_key, case_gate_arp, case_boot)


def group_entries(payload, flash, i):
    for_build(payload)
    return GROUPS[i](payload, flash) if i < len(GROUPS) else []


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    p.add_argument("--only", type=int)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    payload = raw[0x100:] if len(raw) == 0x200100 else raw
    flash = load_flash([a.flash]) if a.flash else None
    if not has_hooks(payload):
        raise SystemExit("this copy does not carry the touch-scale-zero patch")
    found = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(found, indent=1))
    raise SystemExit(0 if all(e["ok"] for e in found) else 1)


if __name__ == "__main__":
    main()
