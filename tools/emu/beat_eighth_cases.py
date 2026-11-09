# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the beat-eighth patch (tools/patch/beat_eighth.py, docs/messungen/2026-10-29-beat-achtel.md): BEAT 4 ("8")
makes the steps eighth notes. The reference everywhere is "BEAT 8 at 160 BPM plays like BEAT 16 at 80 BPM", while the MIDI clock
stays at the real tempo.

    tools/emu/.venv/bin/python tools/emu/beat_eighth_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--only N]
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import beat_eighth as spec  # noqa: E402
import synthaddr  # noqa: E402
import menu_cases  # noqa: E402
import seq_timing_probe as probe  # noqa: E402
from machine import load_flash  # noqa: E402
from pswitch_cases import Box  # noqa: E402
from splash_cases import Dev  # noqa: E402
from tap_motion_cases import LANE_DATA, TBox  # noqa: E402

IMAGE = 0xC0000000
PATTERN_PTR = 0xC033E6A4             # the pattern in RAM, its block from +4
BEAT_AT = 4 + 38                     # BEAT in the pattern object (block offset 38)
LENGTH_AT = 4 + 37
DIVISOR = 0xC06900A0                 # the divider the sequencer took at PLAY (Sampler; the synth's from data/synth-map/)
PATTERN_MENU = 3                     # the screen Pattern menu, pages BPM, SWING, BEAT, ... (data/map/screen.mjs)
TEXT_DRAWN = 0xC0080F20              # mov r2, sp behind the page BEAT's ldr of its text: r1 is the text
EXPORT_LENGTH = 0xC002ED08           # (_, part): the export length of a part in 48 kHz samples
SLICE_MAP = 0xC009A934               # (part object): the step map of a sliced sample, 64 bytes at +0x108
PART_OBJECT = 0xC009AF20             # (part): the object SLICE_MAP takes
SLICE_COUNT, SLICE_BEAT = 0xC004EB70, 0xC004EBB4   # (oscillator): the slices of the part's sample and the beat they were cut to
TAP_PLAY = 0x02
KNOB = 0                             # knob 0 of the selected part in the panel's messages
GATE_ARP = 0x04
STEP_NS = 187_500_000                # a step of BEAT 16 at 80 BPM, of BEAT 8 at 160 BPM


def for_build(payload):
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hooks(payload):
    """True when the divider table has its fifth entry (the byte behind 06 03 08 04)."""
    for_build(payload)
    at = spec.DIVIDER - IMAGE
    return payload[at:at + 5] == bytes([6, 3, 8, 4, spec.EIGHTH])


def entry(name, ok, detail):
    return {"id": f"beateighth:{name}", "ok": bool(ok), "detail": str(detail)}


def close(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


# ------------------------------------------------------------------------------------------------- helpers

def box_of(payload, flash, card=False):
    return Box(payload, flash, card=card)


def pattern(box):
    return box.u32(PATTERN_PTR)


def set_beat(box, beat, tempo):
    """BEAT and tempo (tenths of BPM) of the pattern in RAM, while stopped; the sequencer takes BEAT at PLAY."""
    box.m.uc.mem_write(pattern(box) + BEAT_AT, bytes([beat]))
    probe.set_tempo(box, tempo)


def one_part(box, part=4, note=60, gate=48):
    """Part 5 plays every step of a one bar pattern, nothing else plays (probe.write_pattern on the pattern in RAM)."""
    base = pattern(box) + 4
    uc = box.m.uc
    uc.mem_write(base + 37, bytes([0]))
    for p in range(16):
        for s in range(64):
            on = p == part and s < 16
            uc.mem_write(base + probe.PART + p * 0x330 + probe.STEP + s * 12,
                         bytes([1 if on else 0, gate, 100, 1 if on else 0, note + 1 if on else 0, 0, 0, 0]))


def play(box, seconds, feed=None):
    """PLAY, run, STOP; returns the recorder (notes, clock out)."""
    rec = probe.Recorder(box)
    box.dev.press(TAP_PLAY, 0.0)
    rec.run(seconds, feed)
    box.dev.press(0x01, 0.3)          # STOP
    return rec


def mean_interval(times, skip=1):
    iv = [(b - a) / 1e6 for a, b in zip(times, times[1:])][skip:]
    return round(statistics.fmean(iv), 2) if iv else None


def note_times(rec, part=4, sequencer=True):
    return [t for t, on, p, src, n in rec.notes if on and p == part and (src == 0x10) == sequencer]


# ------------------------------------------------------------------------------------------------- the cases

def case_steps(payload, flash):
    """The step length of BEAT 0 to 4 at 160 BPM, BEAT 16 at 80 BPM, and the MIDI clock out."""
    out = []
    box = box_of(payload, flash)
    one_part(box)
    got = {}
    for beat, tempo in ((0, 1600), (1, 1600), (2, 1600), (3, 1600), (4, 1600), (0, 800)):
        set_beat(box, beat, tempo)
        rec = play(box, 2.5)
        got[(beat, tempo)] = (mean_interval(note_times(rec)), mean_interval(rec.clocks(), 24), box.u32(DIVISOR))
    stock = {0: 93.75, 1: 46.875, 2: 125.0, 3: 62.5}
    out.append(entry("beats_0_to_3_unchanged", all(close(got[(b, 1600)][0], ms, 1.0) for b, ms in stock.items()),
                     {b: got[(b, 1600)][0] for b in stock}))
    eighth, sixteenth, slow = got[(4, 1600)], got[(0, 1600)], got[(0, 800)]
    out.append(entry("beat_8_is_twice_beat_16", close(eighth[0], 2 * sixteenth[0], 1.0) and eighth[2] == spec.EIGHTH,
                     f"BEAT 8 {eighth[0]} ms (divider {eighth[2]}), BEAT 16 {sixteenth[0]} ms"))
    out.append(entry("beat_8_at_160_is_beat_16_at_80", close(eighth[0], slow[0], 1.0), f"{eighth[0]} ms against {slow[0]} ms"))
    out.append(entry("clock_out_stays_at_the_tempo", close(eighth[1], 15.625, 0.05) and close(slow[1], 31.25, 0.1),
                     f"F8 every {eighth[1]} ms at 160 BPM with BEAT 8, {slow[1]} ms at 80 BPM"))
    out.append(entry("no_assert", not box.m.asserts, box.m.asserts))
    return out


def case_external_clock(payload, flash):
    """Clock Mode External MIDI with F8 at exactly 160 BPM: 12 pulses per step with BEAT 8, 6 with BEAT 16."""
    out = []
    res = {}
    for beat in (0, 4):
        box = box_of(payload, flash)
        one_part(box)
        set_beat(box, beat, 1600)
        glob = probe.u32(box, probe.GLOBAL_PTR)
        box.m.uc.mem_write(glob + 44, bytes([3]))
        box.dev.call(probe.CLOCK_MODE_CHANGED, 3)
        rec = probe.Recorder(box)
        period = 60e9 / 160 / 24
        t0 = box.m.time_ns + 50e6
        feed = [(t0, bytes([0xFA]))] + [(t0 + 1e6 + i * period, bytes([0xF8])) for i in range(int(3 * 1e9 / period))]
        rec.run(3.2, feed)
        ons = note_times(rec)
        ins = [t for t, b in feed if b == bytes([0xF8])]
        per = sorted({sum(1 for t in ins if a <= t < b) for a, b in zip(ons, ons[1:])})
        res[beat] = (per, mean_interval(ons))
    out.append(entry("external_clock_12_pulses_per_step", res[4][0] == [12] and res[0][0] == [6],
                     f"BEAT 8 {res[4]}, BEAT 16 {res[0]} (pulses per step, ms per step)"))
    return out


def beat_page(dev):
    """The Pattern menu on its page BEAT."""
    menu_cases.go(dev, PATTERN_MENU)
    for _ in range(2):
        dev.press(menu_cases.KEYS["edit_next"], 0.3)


def case_menu(payload, flash):
    """The page BEAT steps 0 to 4, stops at both ends, and shows \\\\8 for 4."""
    import unicorn
    for_build(payload)
    out = []
    dev = menu_cases.boot(payload, flash, card=False, seconds=2.0)
    drawn = []
    at = dev.a(TEXT_DRAWN)
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: drawn.append(u.reg_read(dev.m.A.UC_ARM_REG_R1)), begin=at, end=at)
    dev.m.uc.ctl_flush_tb()
    beat = lambda: dev.read(dev.u32(PATTERN_PTR) + BEAT_AT, 1)[0]   # noqa: E731
    dev.m.uc.mem_write(dev.u32(PATTERN_PTR) + BEAT_AT, bytes([0]))
    beat_page(dev)
    seen, shown = [beat()], {}
    for _ in range(5):
        drawn.clear()
        dev.turn(1, 0.3)
        seen.append(beat())
        if drawn:
            shown[seen[-1]] = dev.read(drawn[-1], 8).split(b"\0")[0].decode("latin-1")
    texts = sorted(shown.values())
    shown = shown.get(4)
    dev.turn(1, 0.3)
    top = beat()
    down = []
    for _ in range(5):
        dev.turn(-1, 0.3)
        down.append(beat())
    out.append(entry("page_steps_0_to_4", seen == [0, 1, 2, 3, 4, 4] and top == 4 and down == [3, 2, 1, 0, 0],
                     f"up {seen}, again {top}, down {down}"))
    out.append(entry("page_shows_8", shown == "\\\\8" and "?" not in texts, f"shown at 4: {shown!r}, all: {texts}"))
    out.append(entry("no_assert", not dev.m.asserts, dev.m.asserts))
    return out


def case_write(payload, flash):
    """BEAT 4 set on the page, WRITE, another pattern and back: 4 is still there, in the bank and in RAM."""
    out = []
    box = Box(payload, flash, card=False)
    n = box.running()
    beat_page(box.dev)
    for _ in range(5):
        box.dev.turn(1, 0.3)
    for _ in range(2):
        box.dev.press(menu_cases.KEYS["exit"], 0.3)
    live = lambda: box.dev.read(pattern(box) + BEAT_AT, 1)[0]   # noqa: E731
    slot = lambda: box.dev.read(box.slots + n * 0x4000 + 38, 1)[0]   # noqa: E731
    before = (live(), slot())
    for _ in range(3):
        box.dev.press(0x0E, 1.0)
        if not box.dirty():
            break
    written = slot()
    box.turn(1)
    box.run(0.5)
    away = (box.running(), live())
    box.turn(-1)
    box.run(0.5)
    back = (box.running(), live())
    out.append(entry("write_and_reload_keep_4", before[0] == 4 and written == 4 and back == (n, 4),
                     f"RAM {before[0]}, bank before {before[1]}, after WRITE {written}, away {away}, back {back}"))
    return out


def case_gate_arp(payload, flash):
    """Gate Arp with the pad held: BEAT 8 at 160 BPM as BEAT 16 at 80 BPM, while playing and stopped after a PLAY."""
    out = []
    res = {}
    for beat, tempo in ((0, 800), (4, 1600)):
        for playing in (True, False):
            box = box_of(payload, flash)
            one_part(box)
            set_beat(box, beat, tempo)
            if not playing:
                box.dev.press(TAP_PLAY, 0.6)
                box.dev.press(0x01, 0.5)
            box.dev.press(GATE_ARP, 0.3)
            rec = probe.Recorder(box)
            if playing:
                box.dev.press(TAP_PLAY, 0.0)
            box.m.send([0, 0x22, 1, 0, 0])
            box.m.send([5, 0x01, 0x00, 0x01, 0x00])
            rec.run(3.0)
            box.m.send([0, 0x22, 0, 0, 0])
            arp = [t for t, on, p, src, n in rec.notes if on and src != 0x10]
            res[(beat, playing)] = (len(arp), mean_interval(arp, 0))
    for playing in (True, False):
        a, b = res[(4, playing)], res[(0, playing)]
        out.append(entry(f"gate_arp_{'playing' if playing else 'stopped'}", a[0] > 8 and close(a[1], b[1], 1.0) and close(a[1], STEP_NS / 1e6, 3.0),
                         f"BEAT 8 at 160: {a[0]} notes, {a[1]} ms; BEAT 16 at 80: {b[0]} notes, {b[1]} ms"))
    return out


def case_export(payload, flash):
    """The export length of a part in 48 kHz samples: BEAT 8 at 160 BPM as BEAT 16 at 80 BPM, BEAT 0 to 3 as the firmware had them."""
    out = []
    dev = Dev(bytes(payload), flash)
    dev.run(2.0)
    p = dev.u32(PATTERN_PTR)
    dev.m.uc.mem_write(p + LENGTH_AT, bytes([1]))                     # two bars
    got = {}
    for beat, tempo in ((0, 800), (0, 1600), (1, 1600), (2, 1600), (3, 1600), (4, 1600)):
        dev.m.uc.mem_write(p + BEAT_AT, bytes([beat]))
        dev.call(probe.TEMPO_SET, p, tempo, 1)
        got[(beat, tempo)] = dev.call(EXPORT_LENGTH, 0, 0)
    steps = {0: (4, 16), 1: (8, 16), 2: (3, 12), 3: (6, 12), 4: (2, 16)}
    want = {k: int(60 / (steps[k[0]][0] * k[1] / 10) * steps[k[0]][1] * 2 * 48000) for k in got}
    out.append(entry("export_length", got == want and got[(4, 1600)] == got[(0, 800)], f"got {got}, want {want}"))
    return out


def case_divider(payload, flash):
    """The divider the sequencer takes at PLAY and the MIDI clock out, BEAT 8 and 16 at 160 BPM (on the synth, where the
    Sampler's note probes do not apply)."""
    out = []
    dev = Dev(bytes(payload), flash)
    dev.run(2.0)
    p = dev.u32(PATTERN_PTR)
    got = {}
    for beat in (0, 4):
        dev.m.uc.mem_write(p + BEAT_AT, bytes([beat]))
        dev.call(probe.TEMPO_SET, p, 1600, 1)
        rec = probe.Recorder(dev)
        dev.press(TAP_PLAY, 0.0)
        rec.run(2.0)
        dev.press(0x01, 0.3)
        got[beat] = (dev.u32(DIVISOR), mean_interval(rec.clocks(), 24))
    out.append(entry("divider_and_clock", got[4][0] == spec.EIGHTH and got[0][0] == 6 and close(got[4][1], 15.625, 0.05),
                     f"BEAT 8: divider {got[4][0]}, F8 every {got[4][1]} ms; BEAT 16: divider {got[0][0]}"))
    return out


def case_slices(payload, flash):
    """(red) The step map of a sliced sample: with BEAT 8 the same as with BEAT 16, for samples cut to each of the four beats."""
    import unicorn
    if synthaddr.is_synth(payload):
        return []
    out = []
    dev = Dev(bytes(payload), flash)
    dev.run(2.0)
    uc, A = dev.m.uc, dev.m.A
    fake = {"count": 16, "beat": 0}

    def ret(value):
        def hook(u, a, s, d):
            u.reg_write(A.UC_ARM_REG_R0, value())
            u.reg_write(A.UC_ARM_REG_PC, u.reg_read(A.UC_ARM_REG_LR))
        return hook
    uc.hook_add(unicorn.UC_HOOK_CODE, ret(lambda: fake["count"]), begin=SLICE_COUNT, end=SLICE_COUNT)
    uc.hook_add(unicorn.UC_HOOK_CODE, ret(lambda: fake["beat"]), begin=SLICE_BEAT, end=SLICE_BEAT)
    uc.ctl_flush_tb()
    p = dev.u32(PATTERN_PTR)
    obj = dev.call(PART_OBJECT, 0)
    maps, same = {}, True
    for count in (16, 32):
        for sbeat in range(4):
            fake.update(count=count, beat=sbeat)
            for beat in (0, 4):
                uc.mem_write(p + BEAT_AT, bytes([beat]))
                dev.call(SLICE_MAP, obj)
                maps[(count, sbeat, beat)] = dev.read(obj + 0x108, 64)
            same &= maps[(count, sbeat, 4)] == maps[(count, sbeat, 0)]
    first = maps[(16, 0, 4)]
    out.append(entry("slice_map_as_beat_16", same and first[:16] == bytes(range(16)),
                     f"16 slices cut to 16ths, BEAT 8: {first[:16].hex()}; all eight equal to BEAT 16: {same}"))
    return out


def case_tap_motion(payload, flash):
    """(red) REC of a knob: BEAT 8 at 160 BPM records into the same steps as BEAT 16 at 80 BPM, the same values, two bars of 16 steps."""
    if synthaddr.is_synth(payload):
        return []
    out = []
    lanes, counted = {}, {}
    for beat, tempo in ((0, 800), (4, 1600)):
        box = TBox(payload, flash)
        set_beat(box, beat, tempo)
        box.key("rec", 0.2)
        rec = probe.Recorder(box)
        box.key("play", 0.0)
        start = box.m.time_ns
        sent, last = [], None
        for k in range(32):                       # one value in the middle of each 187.5 ms, by time, not by step
            at = start + k * STEP_NS + STEP_NS // 2
            rec.run(max(0, at - box.m.time_ns) / 1e9)
            box.m.send([2, 0, KNOB, 16 + 6 * k, 0])
            sent.append(box.step())
        rec.run(STEP_NS / 1e9)
        last = box.step()
        box.key("stop", 0.5)
        lanes[beat] = box.dev.read(box.pat() + LANE_DATA, 0x40)
        counted[beat] = (sent == list(range(32)), last)
    a, b = lanes[4], lanes[0]
    filled = [i for i, x in enumerate(a) if x]
    # byte 0 of the lane stays 0 in both setups, the 32 values follow: two bars of 16 steps
    out.append(entry("rec_as_beat_16_at_80", a == b and filled == list(range(1, 33)) and counted[4] == counted[0] == (True, 32),
                     f"BEAT 8 at 160 steps {counted[4]}, BEAT 16 at 80 steps {counted[0]}; lane {a[:34].hex()} against {b[:34].hex()}"))
    return out


GROUPS = (case_steps, case_external_clock, case_menu, case_write, case_gate_arp, case_export, case_slices, case_tap_motion)
SYNTH_GROUPS = (case_menu, case_export, case_divider)


def groups_for(payload):
    return SYNTH_GROUPS if synthaddr.is_synth(payload) else GROUPS


def group_entries(payload, flash, i):
    for_build(payload)
    groups = groups_for(payload)
    return groups[i](payload, flash) if i < len(groups) else []


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
        raise SystemExit("this copy does not carry the beat-eighth patch")
    found = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(found, indent=1))
    raise SystemExit(0 if all(e["ok"] for e in found) else 1)


if __name__ == "__main__":
    main()
