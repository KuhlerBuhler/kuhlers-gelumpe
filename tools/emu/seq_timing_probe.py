# SPDX-License-Identifier: GPL-2.0-only
"""Measure the sequencer's timing in the emulator (docs/hintergrund/sequencer-timing.md).

Boots the firmware with a flash dump, writes a test pattern into the live pattern (part 5, every step
on, given gate, swing, beat) or picks a pattern of the bank (--bank), sets the tempo and plays. It stamps every byte the firmware writes to the
DIN MIDI output with device time and reports:

  clock     MIDI clock (0xF8) intervals, mean against the ideal, drift over the run
  notes     the engine's note-on times against an even step grid (even and odd steps apart, for swing),
            note length (gate), note-on after the last clock, MIDI note-on after the engine's call
  ext       Clock Mode External MIDI: 0xF8 fed into DIN at an exact rate, the tempo the firmware takes
            per pulse (the period of its tick generator) and the clock it sends back out

Nothing is written anywhere but the emulator's RAM. Times are device time with machine.SLICE = 2000
(10 us); the 1 kHz timer edge and UART bytes fall at their own time (machine.slice_length).

    tools/emu/.venv/bin/python tools/emu/seq_timing_probe.py clock --vsb SYSTEM.VSB --flash dump.bin --tempo 1600
    tools/emu/.venv/bin/python tools/emu/seq_timing_probe.py notes --vsb ... --flash ... --tempo 1200 --swing 48 --gate 48
    tools/emu/.venv/bin/python tools/emu/seq_timing_probe.py ext --vsb ... --flash ... --ext-bpm 120 --jitter-us 0
"""

import argparse
import json
import random
import statistics
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import machine  # noqa: E402
from machine import UART1, load_flash  # noqa: E402
from pswitch_cases import Box, KEYS  # noqa: E402

machine.SLICE = 2000

LIVE = 0xC06B279C            # live pattern block (pattern offset 34 = tempo, set by 0xC004A80C)
PATTERN_OBJ = 0xC06B2798
TEMPO_SET = 0xC004A80C       # (PATTERN_OBJ, tenths of BPM, 1)
GLOBAL_PTR = 0xC033E6A0      # global settings object, +44 = clock mode (0 internal, 1 auto, 2 ext USB, 3 ext MIDI, 4 ext sync)
CLOCK = 0xC0340380           # tick generator: +8 period in ps (64 bit), +16 time in ps, +0x2C tempo in 0.01 BPM
SEQ_TICK = 0xC005E914        # SeqTask: r0 = tick units since the last call (2304 per quarter)
EXT_PULSE = 0xC002C1C4       # follower: an external clock pulse came in
CLOCK_MODE_CHANGED = 0xC009A860   # (mode): 0xC002BE00(0xC03403B8, mode)
NOTE_ON, NOTE_OFF = 0xC005AD44, 0xC005A20C   # (part, source, note, velocity); source 0x10 = sequencer
PART, STEP = 0x800, 0x30


def u64(box, a):
    return struct.unpack("<Q", bytes(box.m.uc.mem_read(a, 8)))[0]


def u32(box, a):
    return box.u32(a)


def write_pattern(box, gate, swing, beat, note=60, part=4):
    """Part 5 (0-based 4, the one part the flash dump's live pattern leaves unmuted) plays every step of a one-bar
    pattern; all other parts have no step on. Clearing a part's mute byte in the live pattern does not reach the
    engine, so for more load use --bank with a busy pattern."""
    uc = box.m.uc
    base = LIVE
    uc.mem_write(base + 36, struct.pack("<b", swing))
    uc.mem_write(base + 37, bytes([0]))       # length: one bar
    uc.mem_write(base + 38, bytes([beat]))
    for p in range(16):
        for s in range(64):
            at = base + PART + p * 0x330 + STEP + s * 12
            on = p == part and s < 16
            uc.mem_write(at, bytes([1 if on else 0, gate, 100, 1 if on else 0, note + 1 if on else 0, 0, 0, 0]))


class Recorder:
    """Run the machine slice by slice and stamp DIN out bytes and probe points with device time."""

    def __init__(self, box):
        import unicorn
        self.box, self.m = box, box.m
        self.tx = []            # (ns, byte)
        self.ticks = []         # (ns, units) at the SeqTask tick
        self.pulses = []        # (ns, period ps before) at the follower
        self.notes = []         # (ns, on, part, source, note)
        self.seen = len(self.m.uart[UART1]["tx"])
        uc = self.m.uc
        uc.hook_add(unicorn.UC_HOOK_CODE, self._tick, begin=SEQ_TICK, end=SEQ_TICK)
        uc.hook_add(unicorn.UC_HOOK_CODE, self._pulse, begin=EXT_PULSE, end=EXT_PULSE)
        uc.hook_add(unicorn.UC_HOOK_CODE, self._note, begin=NOTE_ON, end=NOTE_ON)
        uc.hook_add(unicorn.UC_HOOK_CODE, self._note, begin=NOTE_OFF, end=NOTE_OFF)
        uc.ctl_flush_tb()

    def _note(self, uc, addr, size, data):
        r = [uc.reg_read(self.m.A.UC_ARM_REG_R0 + i) for i in range(3)]
        self.notes.append((self.m.time_ns, addr == NOTE_ON, r[0], r[1], r[2]))

    def _tick(self, uc, addr, size, data):
        self.ticks.append((self.m.time_ns, uc.reg_read(self.m.A.UC_ARM_REG_R0), uc.reg_read(self.m.A.UC_ARM_REG_CPSR) & 0x1F))

    def _pulse(self, uc, addr, size, data):
        self.pulses.append((self.m.time_ns, u64(self.box, CLOCK + 8), uc.reg_read(self.m.A.UC_ARM_REG_CPSR) & 0x1F))

    def run(self, seconds, feed=None):
        """feed: sorted list of (ns, bytes) put on the DIN input at that device time."""
        m = self.m
        end = m.time_ns + seconds * 1e9
        feed = list(feed or [])
        while m.time_ns < end and not m.asserts:
            limit = min(end, feed[0][0]) if feed else end
            start = m.run_slice(limit)      # a byte is stamped with the start of its slice (at most 10 us early),
                                            # not its end, which jumps ahead to the next event when the CPU waits
            while feed and m.time_ns >= feed[0][0]:
                m.receive(UART1, feed.pop(0)[1])
            m.lines()
            m.irq()
            tx = m.uart[UART1]["tx"]
            if len(tx) > self.seen:
                self.tx += [(start, b) for b in tx[self.seen:]]
                self.seen = len(tx)

    def clocks(self):
        return [t for t, b in self.tx if b == 0xF8]

    def messages(self):
        out, status, cur, t0 = [], None, [], 0
        for t, b in self.tx:
            if b >= 0xF8:
                continue
            if b & 0x80:
                status, cur, t0 = b, [], t
                continue
            if status is None:
                continue
            cur.append(b)
            if len(cur) == (1 if status & 0xF0 in (0xC0, 0xD0) else 2):
                out.append((t0, status, tuple(cur)))
                cur = []
        return out


def boot(args):
    payload = Path(args.vsb).read_bytes()[0x100:]
    flash = load_flash([args.flash]) if args.flash else None
    return Box(payload, flash, card=False)


def select(box, number):
    """Choose a pattern of the bank with the wheel while stopped (the firmware copies it into the live pattern)."""
    left = number - box.running()
    while left:
        d = max(-100, min(100, left))
        box.turn(d, 0.3)
        left -= d
    box.run(0.5)
    return box.running()


def prepare(box, args):
    """The test pattern, or with --bank a pattern of the user's own bank as it is."""
    if args.bank is not None:
        return select(box, args.bank)
    write_pattern(box, args.gate, args.swing, args.beat)
    return None


def set_tempo(box, tenths):
    box.dev.call(TEMPO_SET, PATTERN_OBJ, tenths, 1)
    box.run(0.1)


def interval_stats(times_ns, ideal_ms):
    iv = [(b - a) / 1e6 for a, b in zip(times_ns, times_ns[1:])]
    hist = {}
    for x in iv:
        k = round(x, 2)
        hist[k] = hist.get(k, 0) + 1
    drift = [(t - times_ns[0]) / 1e6 - i * ideal_ms for i, t in enumerate(times_ns)]
    return {
        "count": len(iv), "ideal_ms": round(ideal_ms, 4),
        "mean_ms": round(statistics.fmean(iv), 4) if iv else None,
        "min_ms": round(min(iv), 3) if iv else None, "max_ms": round(max(iv), 3) if iv else None,
        "histogram_ms": dict(sorted(hist.items())),
        "drift_ms_min_max": [round(min(drift), 3), round(max(drift), 3)] if drift else None,
        "drift_ms_end": round(drift[-1], 4) if drift else None,
    }


def late_clocks(rec, clock_ms):
    """Clocks that left more than 0.1 ms after a whole millisecond of the clock grid, with the bytes sent just before."""
    out = []
    for i, (t, b) in enumerate(rec.tx):
        frac = (t / 1e6) % 1.0
        if b == 0xF8 and 0.1 < frac < 0.95:
            out.append({"ms": round(t / 1e6, 2), "late_ms": round(frac, 2), "before": bytes(x for _, x in rec.tx[max(0, i - 8):i]).hex()})
    return {"count": len(out), "first": out[:4]}


def cmd_clock(args):
    box = boot(args)
    prepare(box, args)
    set_tempo(box, args.tempo)
    rec = Recorder(box)
    box.dev.press(KEYS["play"], 0.0)
    rec.run(args.seconds)
    clocks = rec.clocks()[24:]          # leave the start out
    ideal = 60000 / (args.tempo / 10) / 24
    units = [u for _, u, _ in rec.ticks]
    tick_iv = [(b[0] - a[0]) / 1e6 for a, b in zip(rec.ticks, rec.ticks[1:])]
    return {"late_clocks": late_clocks(rec, ideal), "tempo_bpm": args.tempo / 10, "clock_period_ps": u64(box, CLOCK + 8), "clock_tempo_0.01bpm": u32(box, CLOCK + 0x2C),
            "clock": interval_stats(clocks, ideal),
            "seqtask_tick": {"calls": len(units), "units": sorted(set(units)), "mode": sorted({c for *_, c in rec.ticks}),
                             "interval_ms": sorted({round(x, 2) for x in tick_iv})[:12]},
            "asserts": box.m.asserts}


def cmd_notes(args):
    box = boot(args)
    prepare(box, args)
    set_tempo(box, args.tempo)
    rec = Recorder(box)
    box.dev.press(KEYS["play"], 0.0)
    rec.run(args.seconds)
    clocks = rec.clocks()
    per_step = {0: 6, 1: 3, 2: 8, 3: 4}[args.beat]   # MIDI clocks per step (24 per quarter)
    clock_ms = 60000 / (args.tempo / 10) / 24
    step_ms = clock_ms * per_step
    out = {"tempo_bpm": args.tempo / 10, "swing": args.swing, "gate": args.gate, "beat": args.beat, "bank": args.bank,
           "step_ms": round(step_ms, 4), "clock": interval_stats(clocks[24:], clock_ms) if len(clocks) > 30 else len(clocks)}
    # the engine's own note calls (SeqTask), part by part: k-th note-on of a part is its k-th step
    first = None
    even, odd, gates, phase = [], [], [], []
    for part in sorted({n[2] for n in rec.notes}):
        ev = [n for n in rec.notes if n[2] == part and n[3] == 0x10]
        ons = [n for n in ev if n[1]]
        if first is None and ons:
            first = ons[0][0]
        for k, (t, *_r) in enumerate(ons):
            res = (t - first - k * step_ms * 1e6) / 1e6
            (even if k % 2 == 0 else odd).append(round(res, 3))
            off = next((u for u, on, *_x in ev if not on and u > t), None)
            if off:
                gates.append(round((off - t) / 1e6, 3))
            prev = [c for c in clocks if c <= t]
            if prev:
                phase.append(round((t - prev[-1]) / 1e6, 2))
    out.update({
        "engine_note_ons": len(even) + len(odd),
        "even_steps_vs_grid_ms": sorted(set(even[1:])), "odd_steps_vs_grid_ms": sorted(set(odd)),
        "odd_minus_even_mean_ms": round(statistics.fmean(odd) - statistics.fmean(even), 3) if odd and even else None,
        "gate_ms": sorted(set(gates)), "gate_mean_ms": round(statistics.fmean(gates), 3) if gates else None,
        "note_on_after_last_clock_ms": sorted(set(phase))[:24],
    })
    msgs = rec.messages()
    midi_on = [t for t, st, d in msgs if st & 0xF0 == 0x90 and d[1] > 0]
    eng_on = [n[0] for n in rec.notes if n[1] and n[3] == 0x10]
    lag = [round((m - e) / 1e6, 2) for e, m in zip(eng_on, midi_on)]
    out.update({"midi_note_ons": len(midi_on), "midi_minus_engine_ms": sorted(set(lag))[:24],
                "late_clocks": late_clocks(rec, clock_ms),
                "asserts": box.m.asserts})
    return out


def cmd_ext(args):
    box = boot(args)
    write_pattern(box, 48, 0, 0)
    glob = u32(box, GLOBAL_PTR)
    box.m.uc.mem_write(glob + 44, bytes([3]))       # External MIDI
    box.dev.call(CLOCK_MODE_CHANGED, 3)             # what the Global menu calls after the change: arms the MIDI clock follower
    rec = Recorder(box)
    period = 60e9 / args.ext_bpm / 24
    rnd = random.Random(1)
    t0 = box.m.time_ns + 50e6
    n = int(args.seconds * 1e9 / period)
    feed = [(t0, bytes([0xFA]))]
    feed += [(t0 + 1e6 + i * period + rnd.uniform(-args.jitter_us, args.jitter_us) * 1e3, bytes([0xF8])) for i in range(n)]
    feed.sort()
    rec.run(args.seconds + 0.2, feed)
    tempos = [2604166666600 / p / 100 for _, p, _ in rec.pulses[1:] if p]
    out_clocks = rec.clocks()
    in_times = [t for t, b in feed if b == bytes([0xF8])]
    steps = [t for t, s, d in rec.messages() if s & 0xF0 == 0x90 and d[1] > 0]
    late = []
    if steps and in_times:
        for t in steps[2:]:
            k = min(range(len(in_times)), key=lambda i: abs(in_times[i] - t))
            late.append(round((t - in_times[k]) / 1e6, 2))
    return {"ext_bpm": args.ext_bpm, "jitter_us": args.jitter_us, "pulses_seen": len(rec.pulses),
            "pulse_mode": sorted({c for *_, c in rec.pulses}),
            "period_tempo_bpm_set": sorted({round(t, 2) for t in tempos})[:20],
            "period_tempo_mean": round(statistics.fmean(tempos), 3) if tempos else None,
            "clock_out": interval_stats(out_clocks[24:], 60000 / args.ext_bpm / 24) if len(out_clocks) > 30 else len(out_clocks),
            "note_after_nearest_in_clock_ms": sorted(set(late))[:20],
            "asserts": box.m.asserts}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["clock", "notes", "ext"])
    ap.add_argument("--vsb", required=True)
    ap.add_argument("--flash")
    ap.add_argument("--tempo", type=int, default=1200, help="tenths of BPM")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--gate", type=int, default=48)
    ap.add_argument("--swing", type=int, default=0)
    ap.add_argument("--beat", type=int, default=0)
    ap.add_argument("--bank", type=int, help="play pattern N (0-based) of the bank instead of the test pattern")
    ap.add_argument("--ext-bpm", type=float, default=120.0)
    ap.add_argument("--jitter-us", type=float, default=0.0)
    args = ap.parse_args()
    out = {"clock": cmd_clock, "notes": cmd_notes, "ext": cmd_ext}[args.what](args)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
