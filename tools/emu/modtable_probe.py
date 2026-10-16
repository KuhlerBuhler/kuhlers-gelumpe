# SPDX-License-Identifier: GPL-2.0-only
"""Research probe for the modulation table, stage 2 (docs/messungen/2026-10-15-modulation-stufe2.md).

Stage 1 made name, destination label, default depth, default speed and curve of the 72 modulation types editable.
This probe measures the rest of an entry (every byte from +0x14 on) on the firmware as it is, in the emulator, and
nothing else: no hardware, no patch. Every claim of the measurement file is one check here. A check changes bytes of
the table that the firmware reads (RAM at 0xC019FFFC, live), or of a copy of the firmware file that is booted
(`file_edits`, the cross check), selects a type on part 1 with MOD. TYPE, sets MOD. DEPTH and MOD. SPEED, plays a
note on part 1 and looks at three places:

  - the firmware's per-part modulation state in RAM: nine bytes per part (`SLOTS`: speed outputs and six slot
    strengths) and what the engine adds up per destination (`ACC`, eleven words) at every call;
  - the display (a hash of the frame buffer after the type is chosen);
  - what the ARM sends to the DSP over the host port (the A34 mailbox packets, hashed per command and word).

Entries are numbered like the map (data/map/firmware.mjs): an offset here is an offset in the map's entry window,
which starts four bytes before the firmware's own record (the record starts at the name, 0xC01A0000 for type 0).

    E2_VSB=/path/SYSTEM.VSB E2_FLASH=/path/flash.bin \\
        tools/emu/.venv/bin/python tools/emu/modtable_probe.py [--only layout,reads,table,model,slots,targets,curve,speed,flags,unread,scratch,copy] [--jobs 4] [--json out.json]

Each check prints ok or FAIL with the numbers behind it; the exit status is 1 when one fails. A full run takes roughly
20 minutes on four workers (GELUMPE_JOBS), most of it the unread section.
"""
import argparse
import collections
import hashlib
import json
import os
import statistics
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unicorn  # noqa: E402
from unicorn import arm_const as A  # noqa: E402
import bootcache  # noqa: E402
import parallel  # noqa: E402
from machine import Machine, load_flash  # noqa: E402
from mfx_cases import DspLog  # noqa: E402
from splash_cases import Dev  # noqa: E402

# ---- firmware addresses (firmware 2.02 with Hacktribe) ----
REC = 0xC01A0000               # record of type 0 in RAM: it starts at the name
WINDOW = REC - 4               # the map's entry window (table.modType, file 0x1A00FC)
FILE_WINDOW = 0x1A00FC         # file offset of entry 0 in the map's frame, the copy the firmware reads
FILE_STOCK = 0xD82EC           # the same table in Korg's copy, dead data in the Hacktribe image
STRIDE = 0x58
COUNT = 72
PATTERN_WORD = 0xC033E6A4      # holds the pattern object; the part records start at +4 + 0x800, 0x330 each
SLOTS = 0xC06924DD             # nine bytes per part: out0, out1, out2, six slot strengths
SCRATCH_FLAG = 0xC06924DC      # nonzero: every lookup returns the entry at SCRATCH_ENTRY
SCRATCH_ENTRY = 0xC00F9D90     # one record named "for Voicing", outside the table
ACCESSOR = 0xC0098D10          # type -> record address
RECOMPUTE = 0xC0099088         # (part object) recompute SLOTS from the table, MOD. DEPTH and MOD. SPEED
GET_PART = 0xC009AF20          # (part) -> the modulation object of the part
TEMPO_SET = 0xC004A80C         # (pattern object, tenths of a BPM, 1)
TEMPO_WORD = 0xC0691518        # tenths of a BPM
ENGINE_EXIT = 0xC009B52C       # in the engine: the six slots are summed, the eleven destination setters follow
ACC = 0xC069FEC8               # eleven words: what the engine adds up per destination
UNITS = 0xC069151C             # 0x18 bytes per part, word 0 is the phase of the LFO integrator
ACCESSOR_LITERALS = {0xC0098D38: SCRATCH_FLAG, 0xC0098D3C: REC, 0xC0098D40: SCRATCH_ENTRY}
KNOB_DEPTH, KNOB_SPEED, ENC_TYPE = 5, 10, 3
KEY_PLAY, KEY_STOP = 2, 1

# ---- the entry, in map offsets ----
NAME, TARGET, DEPTH, SPEED, CURVE = 4, 0x19, 0x1A, 0x1B, 0x1C
SYNC, TEMPO_SYNC, CACHE_LFO = 0x1D, 0x1E, 0x1F
RATE_LO, RATE_HI = 0x20, 0x21
EG_BPM, CACHE_EG = 0x24, 0x25
EG_LO, EG_HI = 0x28, 0x29
SLOT0, SLOT_STRIDE, SLOTS_N = 0x2C, 8, 6
FIELD = dict(kind=0, target=1, cache=2, lo=3, hi=4, follow=5, spare1=6, spare2=7)


def slot(k, field):
    return SLOT0 + SLOT_STRIDE * k + FIELD[field]


# What the read hook saw, as record offsets (map offset minus four). The slots 0 and 1 are the ones the table uses;
# kind and target of a slot are only read once its strength is not 0 (see the "slots" section).
R_NAME = set(range(0x00, 0x10))
R_ALWAYS = {0x16, 0x18, 0x19, 0x1A, 0x1C, 0x1D, 0x20, 0x24, 0x25}
R_SLOT = {s + o for s in (0x28 + 8 * k for k in range(6)) for o in (0, 1, 3, 4, 5)}


def s8(v):
    return v - 256 if v > 127 else v


# ---- the arithmetic of the firmware, as read from the code (0xC0098D44, 0xC0098DE4, 0xC0098F78, 0xC0098FEC) ----
def lerp(x, lo, hi):
    """Value for x (0 to 127) between lo and hi in 256 steps; 0xC0098D44."""
    if lo == hi:
        return lo
    if lo < hi:
        v = lo + (((hi - lo + 1) * (2 * x + 1)) >> 8)
        return lo if v < lo else min(v, hi)
    v = lo - (((lo - hi + 1) * (2 * x + 1)) >> 8)
    return lo if v > lo else max(v, hi)


def strength(a, b, depth):
    """Strength of a slot with signed lo `a` and hi `b` at `depth`; 0xC0098DE4."""
    if b > 0:
        return lerp(depth, 0, 63) if a < 0 else lerp(depth, a, b)
    return -lerp(depth, -b, -a)


def model_slots(e, part_depth, part_speed):
    """The nine bytes the firmware keeps per part for a type, from the entry `e` (the map window, 0x5C bytes)."""
    sp = part_speed & 0x7F
    out2 = lerp(sp, min(e[EG_LO], 127), min(e[EG_HI], 127)) & 0xFF
    v = lerp(sp, min(e[RATE_LO], 127), min(e[RATE_HI], 127)) & 0xFF
    out0, out1 = (v, 0xFF) if e[TEMPO_SYNC] == 0 else (0xFF, v)
    out = [out0, out1, out2]
    for k in range(SLOTS_N):
        used = e[DEPTH] if e[slot(k, "follow")] == 0 else part_depth & 0x7F
        out.append(strength(s8(e[slot(k, "lo")]), s8(e[slot(k, "hi")]), used) & 0xFF)
    return bytes(out)


# ---- a booted device ----
class Lab:
    def __init__(self, payload, flash):
        self.payload = payload
        self.m, self.dsp = bootcache.booted(bytes(payload), flash, 0, 5.0, observer=DspLog)
        self.dev = Dev(payload, flash, 0, machine=self.m)
        self._last = {}

    def run(self, seconds):
        self.dev.run(seconds)

    def u32(self, a):
        return self.dev.u32(a)

    def read(self, a, n):
        return self.dev.read(a, n)

    def write(self, a, data):
        self.m.uc.mem_write(a, bytes(data))

    def call(self, func, *args):
        return self.dev.call(func, *args)

    def pattern(self):
        return self.u32(PATTERN_WORD) + 4

    def part_record(self, p=0):
        return self.pattern() + 0x800 + 0x330 * p

    def part(self, p=0):
        b = self.read(self.part_record(p) + 16, 3)
        return dict(type=b[0], speed=b[1], depth=b[2])

    def knob(self, index, raw, wait=0.3):
        self.m.send([2, index, 0, raw, 0])
        self.run(wait)

    def set_knob(self, index, raw, wait=0.3):
        """A knob moves to `raw`; the part gets raw >> 1. The same raw value twice is no movement, so one bit flips."""
        if self._last.get(index) == raw:
            raw ^= 1
        self._last[index] = raw
        self.knob(index, raw, wait)

    def pad(self, n=0, vel=100, hold=0.3, wait=0.3):
        self.m.send([4, n, 0, vel, 1])
        self.run(hold)
        self.m.send([4, n, 0, 0, 0])
        self.run(wait)

    def key(self, k, wait=0.3):
        self.m.press(k, True)
        self.run(0.05)
        self.m.press(k, False)
        self.run(wait)

    def choose(self, ty, p=0):
        """Turn MOD. TYPE until part p holds `ty`."""
        for _ in range(100):
            now = self.part(p)["type"]
            if now == ty:
                return
            self.m.send([1, ENC_TYPE, 0, (1 if now < ty else -1) & 0xFF, 0])
            self.run(0.25)
        raise RuntimeError(f"MOD. TYPE did not reach {ty}")

    def poke(self, entry, off, value):
        """One byte of the table the firmware reads, live."""
        self.write(WINDOW + entry * STRIDE + off, bytes([value & 0xFF]))

    def entry(self, i):
        return self.read(WINDOW + i * STRIDE, STRIDE + 4)

    def slots(self, p=0):
        return self.read(SLOTS + 9 * p, 9)

    def fb_hash(self):
        return hashlib.sha256(self.dev.fb()).hexdigest()[:12]


class Tracer:
    """What the modulation engine of one part adds up, at every call, and the integrator phase."""

    def __init__(self, lab, part=0):
        self.lab, self.part = lab, part
        self.rows = []          # (device ms, acc[0..10], LFO output, unit words)
        lab.m.uc.hook_add(unicorn.UC_HOOK_CODE, self._hook, begin=ENGINE_EXIT, end=ENGINE_EXIT)
        lab.m.uc.ctl_flush_tb()

    def _hook(self, uc, addr, size, data):
        obj = uc.reg_read(A.UC_ARM_REG_R5)
        if uc.mem_read(obj + 0x31, 1)[0] != self.part:
            return
        acc = struct.unpack("<11i", bytes(uc.mem_read(ACC, 44)))
        lfo = struct.unpack("<h", bytes(uc.mem_read(obj + 0x8C, 2)))[0]
        words = struct.unpack("<6I", bytes(uc.mem_read(UNITS + 0x18 * self.part, 0x18)))
        self.rows.append((round(self.lab.m.time_ns / 1e6, 1), acc, lfo, words))


def period_ms(rows):
    """Period of the LFO integrator from the slope of its phase between calls."""
    steps = []
    for a, b in zip(rows, rows[1:]):
        dt = b[0] - a[0]
        dp = (b[3][0] - a[3][0]) & 0xFFFFFFFF
        if dt > 0 and 0 < dp < 0x80000000:
            steps.append(dp / dt)
    if not steps:
        return None
    rate = statistics.median(steps)
    return round(2 ** 32 / rate) if rate else None


def metrics(rows, k=None):
    lfo = [r[2] for r in rows]
    sgn = [(v > 0) - (v < 0) for v in lfo]
    out = dict(n=len(rows), cross=sum(1 for a, b in zip(sgn, sgn[1:]) if a and b and a != b),
               lfo_min=min(lfo) if lfo else None, lfo_max=max(lfo) if lfo else None, lfo_distinct=len(set(lfo)))
    acc_max = [max((abs(r[1][i]) for r in rows), default=0) for i in range(11)]
    out["acc_max"] = acc_max
    if k is not None and rows:
        a = [r[1][k] for r in rows]
        mag = [abs(v) for v in a]
        peak = max(mag)
        out.update(acc_min=min(a), acc_peak=peak, acc_nz=sum(1 for v in a if v))
        if peak:
            ip = mag.index(peak)
            t0 = rows[0][0]
            half = next((rows[i][0] - t0 for i in range(ip, len(mag)) if mag[i] <= peak / 2), None)
            out["t_half"] = None if half is None else round(half)
    return out


def profile(rows):
    """Mean LFO output (thousands) per sixteenth of the phase."""
    bins = [[] for _ in range(16)]
    for _, _, lfo, words in rows:
        bins[words[0] >> 28].append(lfo)
    return [round(sum(b) / len(b) / 1000, 1) if b else None for b in bins]


def a34_signature(dsp):
    """Per (command, word) a hash of the values over all A34 packets of that command, and how many values occur."""
    packets = [x[3] for x in dsp.xfers if x[0] == 0xAB and x[1] == 0xFF900A34 and len(x[3]) >= 2]
    by_cmd = collections.defaultdict(list)
    for w in packets:
        by_cmd[w[1]].append(w)
    sig = {}
    for cmd, ws in by_cmd.items():
        for i in range(max(len(w) for w in ws)):
            vals = [w[i] if i < len(w) else None for w in ws]
            sig[f"{cmd:#x}:{i}"] = (hashlib.sha1(repr(vals).encode()).hexdigest()[:10], len(set(vals)), len(vals))
    return sig, len(packets)


def classify(profile_):
    """A name for the shape of a waveform profile."""
    p = [v for v in profile_ if v is not None]
    if len(p) < 16:
        return "unvollständig"
    hi, lo = max(p), min(p)
    if hi == lo:
        return "konstant"
    if all(abs(v - hi) < 0.5 or abs(v - lo) < 0.5 for v in p):
        return "Rechteck" if lo < -1 else "Rechteck einpolig"
    drops = sum(1 for a, b in zip(p, p[1:]) if b < a)
    if drops >= 14:
        return "Sägezahn fallend"
    if drops <= 1:
        return "Sägezahn steigend"
    if abs(p[1] - p[0]) > 0 and max(p[:8]) > 15 and p[4] > 0.8 * max(p[:8]) and p[7] < 8:
        first, third = p[1] - p[0], p[3] - p[2]
        return "Sinus" if third < 0.7 * first else "Dreieck"
    return "Zufall"


# ---- one measurement ----
def file_edit(payload, edits, base):
    data = bytearray(payload)
    for i, off, v in edits:
        data[base - 0x100 + i * STRIDE + off] = v
    return bytes(data)


def run_spec(spec):
    """One scenario on a fresh boot; `spec` is a dict (see PLAN keys). Returns plain data."""
    shared = parallel.shared
    payload = shared["payload"]
    if spec.get("file_edits"):
        payload = file_edit(payload, spec["file_edits"], FILE_WINDOW)
    if spec.get("stock_edits"):
        payload = file_edit(payload, spec["stock_edits"], FILE_STOCK)
    L = Lab(payload, shared["flash"])
    L.run(0.2)
    ty = spec["type"]
    for i, off, v in spec.get("early", ()):
        L.poke(i, off, v)
    L.choose(ty)
    for i, off, v in spec.get("edits", ()):
        L.poke(i, off, v)
    if spec.get("tempo"):
        L.call(TEMPO_SET, L.u32(PATTERN_WORD), spec["tempo"], 1)
        L.run(0.3)
    other = (ty + 1) % COUNT
    L.choose(other)
    L.choose(ty)                       # the type is read again with the edit in place
    L.run(0.3)
    fb_type = L.fb_hash()              # the display with the type name; a knob replaces it with the knob's value
    # MOD. DEPTH as raw knob value (the part gets half): an envelope type at full depth, an LFO type at 100
    L.set_knob(KNOB_DEPTH, spec.get("depth", 254 if ty < 24 else 200), 0.2)
    L.set_knob(KNOB_SPEED, spec.get("speed", 200), 0.2)
    out = dict(name=spec["name"], slots=L.slots().hex(" "), part=L.part(), fb=L.fb_hash(), fb_type=fb_type, tempo=L.u32(TEMPO_WORD))
    L.run(spec.get("pre", 0.0))        # shifts every later moment against the firmware's own clocks
    tr = Tracer(L)
    L.dsp.xfers.clear()
    mode = spec.get("mode", "pad")
    marks = []
    if mode == "play":
        L.key(KEY_PLAY, 0.1)
        L.run(spec.get("hold", 0.6) + spec.get("tail", 1.5))
        L.key(KEY_STOP, 0.2)
    elif mode == "idle":
        L.run(spec.get("tail", 0.5))
    elif mode == "bursts":
        for _ in range(spec.get("bursts", 8)):
            marks.append(L.m.time_ns / 1e6)
            L.pad(0, hold=spec.get("hold", 0.4), wait=spec.get("gap", 0.3))
    else:
        L.pad(0, hold=spec.get("hold", 0.6), wait=spec.get("tail", 1.5))
    rows = tr.rows
    out["m"] = metrics(rows, spec.get("k"))
    out["rows"] = hashlib.sha256(repr([(r[1], r[2]) for r in rows]).encode()).hexdigest()[:10]
    out["period"] = period_ms(rows[5:]) if rows else None
    out["profile"] = profile(rows) if spec.get("profile") else None
    out["a34"], out["a34_n"] = a34_signature(L.dsp)
    if marks:
        firsts = []
        for t in marks:
            after = next((r for r in rows if r[0] >= t), None)
            firsts.append(None if after is None else after[3][0] >> 20)
        out["first_phase"] = firsts
    return out


# ---- tasks that are not one scenario ----
def layout_task():
    shared = parallel.shared
    L = Lab(shared["payload"], shared["flash"])
    out = {"names": [], "literals": {}}
    for i in range(COUNT):
        out["names"].append(bytes(L.read(REC + i * STRIDE, 16)).split(b"\0")[0].decode("latin1"))
    out["file_match"] = all(bytes(L.read(WINDOW + i * STRIDE, STRIDE)) == bytes(shared["payload"][FILE_WINDOW - 0x100 + i * STRIDE: FILE_WINDOW - 0x100 + (i + 1) * STRIDE]) for i in range(COUNT))
    out["literals"] = {hex(a): hex(L.u32(a)) for a in ACCESSOR_LITERALS}
    out["literals_ok"] = all(L.u32(a) == v for a, v in ACCESSOR_LITERALS.items())
    out["scratch_name"] = bytes(L.read(SCRATCH_ENTRY, 16)).split(b"\0")[0].decode("latin1")
    out["scratch_flag"] = L.read(SCRATCH_FLAG, 1)[0]
    out["tail_after_71"] = bytes(L.read(REC + COUNT * STRIDE, 4)).hex()
    return out


def reads_task():
    """Which bytes of the 72 records the firmware reads while types are chosen, depth and speed moved, notes played."""
    shared = parallel.shared
    L = Lab(shared["payload"], shared["flash"])
    L.run(0.3)
    seen = collections.defaultdict(set)

    def hook(u, access, addr, size, value, data):
        pc = u.reg_read(A.UC_ARM_REG_PC)
        for b in range(addr, addr + size):
            seen[(b - REC) % STRIDE].add(pc)

    L.m.uc.hook_add(unicorn.UC_HOOK_MEM_READ, hook, begin=REC, end=REC + COUNT * STRIDE - 1)
    for t in range(COUNT):
        L.choose(t)
        L.set_knob(KNOB_DEPTH, 40 + t, 0.1)
        L.set_knob(KNOB_SPEED, 200 - t, 0.1)
        L.pad(0, hold=0.2, wait=0.25)
    L.key(KEY_PLAY, 0.1)
    L.run(1.5)
    L.key(KEY_STOP, 0.2)
    return {hex(o): sorted(hex(p) for p in pcs) for o, pcs in sorted(seen.items())}


def boot_reads_task():
    """The same hook from power-on: what the firmware reads of the table while it starts."""
    shared = parallel.shared
    m = Machine(bytes(shared["payload"]), shared["flash"])
    seen = collections.defaultdict(set)

    def hook(u, access, addr, size, value, data):
        pc = u.reg_read(A.UC_ARM_REG_PC)
        for b in range(addr, addr + size):
            seen[(b - REC) % STRIDE].add(pc)

    m.uc.hook_add(unicorn.UC_HOOK_MEM_READ, hook, begin=REC, end=REC + COUNT * STRIDE - 1)
    Dev(shared["payload"], shared["flash"], 0, machine=m).run(5.0)
    return {hex(o): sorted(hex(p) for p in pcs) for o, pcs in sorted(seen.items())}


def model_task():
    """SLOTS against the model for every type and a few depth and speed pairs, by writing the part and recomputing."""
    shared = parallel.shared
    L = Lab(shared["payload"], shared["flash"])
    L.run(0.3)
    bad, n = [], 0
    for part, combos in ((0, ((0, 0), (127, 127), (64, 32), (21, 100), (101, 7))), (5, ((77, 3), (127, 0))), (15, ((9, 120), (127, 127)))):
        obj = L.call(GET_PART, part)
        copy = L.u32(obj + 8)             # the firmware's working copy of the part, 0x382E behind the pattern's
        for ty in range(COUNT):
            e = L.entry(ty)
            for depth, speed in combos:
                L.write(copy + 16, bytes([ty, speed, depth]))
                L.call(RECOMPUTE, obj)
                got = L.slots(part)
                want = model_slots(e, depth, speed)
                n += 1
                if got != want:
                    bad.append((part, ty, depth, speed, got.hex(), want.hex()))
    return {"compared": n, "bad": bad[:20], "bad_n": len(bad)}


def defaults_task():
    """Does MOD. TYPE give the part the default depth and speed of the entry? 71 of 72 by the earlier measurement."""
    shared = parallel.shared
    L = Lab(shared["payload"], shared["flash"])
    L.run(0.3)
    same, differ = 0, []
    for ty in range(COUNT):
        L.choose(ty)
        e = L.entry(ty)
        p = L.part()
        if (p["depth"], p["speed"]) == (e[DEPTH], e[SPEED]):
            same += 1
        else:
            differ.append((ty, p, e[DEPTH], e[SPEED]))
    return {"same": same, "differ": differ}


def scratch_task():
    shared = parallel.shared
    L = Lab(shared["payload"], shared["flash"])
    L.run(0.3)
    out = {"flag0": {}, "flag1": {}}
    for ty in (0, 25, 71):
        out["flag0"][ty] = hex(L.call(ACCESSOR, ty))
    L.choose(25)
    obj = L.call(GET_PART, 0)
    L.write(L.u32(obj + 8) + 16, bytes([25, 100, 100]))
    L.call(RECOMPUTE, obj)
    out["slots_normal"] = L.slots().hex(" ")
    L.write(SCRATCH_FLAG, b"\x01")
    for ty in (0, 25, 71):
        out["flag1"][ty] = hex(L.call(ACCESSOR, ty))
    L.call(RECOMPUTE, obj)
    out["slots_scratch"] = L.slots().hex(" ")
    out["scratch_entry"] = L.read(SCRATCH_ENTRY, 0x58).hex()
    return out


# ---- the table in the file ----
def table_stats(vsb):
    base = FILE_WINDOW
    E = [vsb[base + i * STRIDE: base + (i + 1) * STRIDE + 4] for i in range(COUNT)]
    stats = {}
    for off in range(0, 0x5C):
        c = collections.Counter(e[off] for e in E)
        stats[off] = dict(sorted(c.items()))
    return E, stats


# ---- the plan: every scenario by name ----
class Plan:
    def __init__(self):
        self.specs = []
        self.extra = []
        self.index = {}
        self.done = None

    def add(self, name, ty, edits=(), **kw):
        assert name not in self.index, name
        spec = dict(name=name, type=ty, edits=list(edits), **kw)
        self.index[name] = len(self.specs)
        self.specs.append(spec)
        return name

    def result(self, name):
        return self.done[self.index[name]]


SECTIONS = ["layout", "reads", "table", "model", "slots", "targets", "curve", "speed", "flags", "unread", "scratch", "copy"]

# offsets the firmware never reads (see the "reads" section), by map offset, for the "unread" section
UNREAD_SINGLE = ([0x14, 0x15, 0x16, 0x17, 0x18, TARGET, CACHE_LFO, 0x22, 0x23, CACHE_EG, 0x26, 0x27, 0x2A, 0x2B]
                 + [slot(k, "cache") for k in range(SLOTS_N)]
                 + [slot(k, f) for k in range(SLOTS_N - 1) for f in ("spare1", "spare2")])


def build(plan, only):
    for_ = lambda s: only is None or s in only  # noqa: E731

    # slots on an LFO type (25, LFOTri Pitch, slot 0 pitch), and on an envelope (1, EG+ Pitch)
    if for_("slots"):
        T = 25
        plan.add("slots.base", T, k=1)
        plan.add("slots.idle", T, k=1, mode="idle", tail=0.5)
        for kind in (0, 2, 3, 255):
            plan.add(f"slots.kind.{kind}", T, [(T, slot(0, "kind"), kind)], k=1)
        for a, b in ((0xC1, 0), (10, 20), (0, 20), (0xF6, 20), (5, 5), (20, 10), (0xEC, 0xFB), (0, 127), (0x80, 0x7F)):
            plan.add(f"slots.range.{s8(a)}.{s8(b)}", T, [(T, slot(0, "lo"), a), (T, slot(0, "hi"), b)], k=1)
        for f in (0, 2):
            plan.add(f"slots.follow.{f}", T, [(T, slot(0, "follow"), f)], k=1)
        plan.add("slots.spare", T, [(T, slot(0, "cache"), 0x70), (T, slot(0, "spare1"), 9), (T, slot(0, "spare2"), 9)], k=1)
        plan.add("slots.second.filter", T, [(T, slot(1, "kind"), 1), (T, slot(1, "target"), 3), (T, slot(1, "hi"), 63), (T, slot(1, "follow"), 1)], k=3)
        plan.add("slots.second.pitch", T, [(T, slot(1, "kind"), 1), (T, slot(1, "target"), 1), (T, slot(1, "hi"), 63), (T, slot(1, "follow"), 1)], k=1)
        plan.add("slots.sixth.without_tail", T, [(T, slot(5, "kind"), 1), (T, slot(5, "target"), 8), (T, slot(5, "lo"), 0), (T, slot(5, "follow"), 1)], k=8)
        plan.add("slots.sixth.with_tail", T, [(T, slot(5, "kind"), 1), (T, slot(5, "target"), 8), (T, slot(5, "lo"), 0), (T, 0x58, 63), (T, 0x59, 1)], k=8)
        # the envelope entry: two slots on the pitch, EG source
        plan.add("slots.eg.base", 1, k=1, speed=100)
        plan.add("slots.eg.lfo_source", 1, [(1, slot(0, "kind"), 1)], k=1, speed=100)

    if for_("targets"):
        for t in list(range(0, 13)) + [100, 255]:
            plan.add(f"targets.{t}", 25, [(25, slot(0, "target"), t)], k=t if t <= 10 else 0)

    if for_("curve"):
        for c in list(range(0, 10)) + [15, 16, 255]:
            plan.add(f"curve.lfo.{c}", 25, [(25, CURVE, c)], k=1, speed=130, tail=2.0, profile=True)
        for c in (0, 1, 2, 6):
            plan.add(f"curve.eg.{c}", 1, [(1, CURVE, c)], k=1, speed=100, profile=True)

    if for_("speed"):
        for n in (0, 16, 32, 64, 96, 127):
            plan.add(f"speed.free.{n}", 25, [(25, RATE_LO, n), (25, RATE_HI, n)], k=1)
        for lo, hi in ((0, 64), (64, 127), (127, 0)):
            plan.add(f"speed.free.range.{lo}.{hi}", 25, [(25, RATE_LO, lo), (25, RATE_HI, hi)], k=1, speed=254)
        for n in range(1, 17):
            plan.add(f"speed.sync.{n}", 30, [(30, RATE_LO, n), (30, RATE_HI, n)], k=3)
        for tempo in (900, 2400):
            plan.add(f"speed.sync.8.tempo.{tempo}", 30, [(30, RATE_LO, 8), (30, RATE_HI, 8)], k=3, tempo=tempo)
        for s in (40, 100, 200):
            plan.add(f"speed.eg.s{s}", 1, k=1, speed=s)
        for lo, hi in ((0, 64), (64, 127), (127, 0), (100, 100)):
            plan.add(f"speed.eg.range.{lo}.{hi}", 1, [(1, EG_LO, lo), (1, EG_HI, hi)], k=1, speed=254)
        plan.add("speed.eg.bpm.on.s20", 1, [(1, EG_BPM, 1)], k=1, speed=20)
        plan.add("speed.eg.bpm.on.s100", 1, [(1, EG_BPM, 1)], k=1, speed=100)
        # type 7 is type 1 with the tempo flag and the pair (16, 1): the same two pitch slots, so the same metric
        plan.add("speed.eg.bpm.type7.s100", 7, k=1, speed=100)
        plan.add("speed.eg.bpm.type7.off", 7, [(7, EG_BPM, 0)], k=1, speed=100)
        plan.add("speed.eg.bpm.on.step16", 1, [(1, EG_BPM, 1), (1, EG_LO, 16), (1, EG_HI, 16)], k=1, speed=100)
        for n in (17, 20, 127):
            plan.add(f"speed.sync.over.{n}", 30, [(30, RATE_LO, n), (30, RATE_HI, n)], k=3)
        for tempo in (900, 2400):
            plan.add(f"speed.eg.bpm.type7.tempo.{tempo}", 7, k=1, speed=100, tempo=tempo)

    if for_("flags"):
        for t, f in ((30, 1), (30, 0), (25, 1), (25, 0)):
            plan.add(f"flags.sync.{t}.{f}", t, [(t, SYNC, f)], mode="bursts", bursts=8, hold=0.4, gap=0.3, speed=130)
        for t in (25, 30):
            for pre in (0.1, 0.2, 0.45):
                plan.add(f"flags.sync.{t}.1.pre{pre}", t, [(t, SYNC, 1)], mode="bursts", bursts=8, hold=0.4, gap=0.3, speed=130, pre=pre)
        plan.add("flags.tempo.free_on", 25, [(25, TEMPO_SYNC, 1), (25, RATE_LO, 8), (25, RATE_HI, 8)], k=1)
        plan.add("flags.tempo.free_default", 25, [(25, RATE_LO, 8), (25, RATE_HI, 8)], k=1)
        plan.add("flags.tempo.sync_off", 30, [(30, TEMPO_SYNC, 0), (30, RATE_LO, 8), (30, RATE_HI, 8)], k=3)

    if for_("unread"):
        for t in (1, 25, 36):
            plan.add(f"unread.base.{t}", t, k=1, hold=0.4, tail=0.8)
        for t in (1, 25, 36):
            plan.add(f"unread.all.{t}", t, [(t, off, 0xA5) for off in UNREAD_SINGLE], k=1, hold=0.4, tail=0.8)
        for t in (1, 25):
            for off in UNREAD_SINGLE:
                plan.add(f"unread.{t}.{off:#04x}", t, [(t, off, 0x5A)], k=1, hold=0.4, tail=0.8)
        # the name: a byte after the terminator, and the first letter
        plan.add("name.base", 25, k=1, hold=0.2, tail=0.3)
        plan.add("name.after_nul", 25, [(25, NAME + 14, 0x41)], k=1, hold=0.2, tail=0.3)
        plan.add("name.first_letter", 25, [(25, NAME, ord("X"))], k=1, hold=0.2, tail=0.3)
        # sixteen characters fill the field; the terminator is then the byte behind it (+0x14), which is 0 in all 72 entries
        plan.add("name.sixteen", 25, [(25, NAME + i, ord("ABCDEFGHIJKLMNOP"[i])) for i in range(16)], k=1, hold=0.2, tail=0.3)

    if for_("copy"):
        # the same edit once live in RAM and once in a copy of the firmware that is booted
        plan.add("copy.curve.ram", 25, [(25, CURVE, 6)], k=1, speed=130, profile=True)
        plan.add("copy.curve.file", 25, file_edits=[(25, CURVE, 6)], k=1, speed=130, profile=True)
        plan.add("copy.curve.stock", 25, stock_edits=[(25, CURVE, 6)], k=1, speed=130, profile=True)
        plan.add("copy.eg.ram", 1, [(1, EG_LO, 0), (1, EG_HI, 64)], k=1, speed=254)
        plan.add("copy.eg.file", 1, file_edits=[(1, EG_LO, 0), (1, EG_HI, 64)], k=1, speed=254)
        plan.add("copy.eg.stock", 1, stock_edits=[(1, EG_LO, 0), (1, EG_HI, 64)], k=1, speed=254)
        plan.add("copy.target.ram", 25, [(25, slot(0, "target"), 3)], k=3)
        plan.add("copy.target.file", 25, file_edits=[(25, slot(0, "target"), 3)], k=3)
        plan.add("copy.base", 25, k=1, speed=130, profile=True)
        plan.add("copy.eg.base", 1, k=1, speed=254)
        plan.add("copy.target.base", 25, k=3)


# ---- checks ----
FAILS = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def changed(base, got):
    """Keys of the A34 signature whose hash differs, and the count of A34 packets."""
    return sorted(k for k in set(base["a34"]) | set(got["a34"]) if base["a34"].get(k, (None,))[0] != got["a34"].get(k, (None,))[0])


def same_run(base, got):
    """True when the engine rows, the slots, the display and every A34 word are the same."""
    return (base["rows"] == got["rows"] and base["slots"] == got["slots"] and base["fb"] == got["fb"] and base["fb_type"] == got["fb_type"]
            and not changed(base, got) and base["a34_n"] == got["a34_n"])


def evaluate(plan, results, vsb, out):
    R = plan.result
    have = lambda s: s in plan.index  # noqa: E731

    if "layout" in results:
        r = results["layout"]
        print("\n== layout")
        check("layout.record_start", r["names"][0] == "EG+ Filter" and r["names"][71] == "Random IFX",
              f"RAM {REC:#x} holds {r['names'][0]!r} .. {r['names'][71]!r}; the map's window starts four bytes before")
        check("layout.ram_equals_file", r["file_match"], "the RAM copy at 0xC019FFFC equals the file bytes at 0x1A00FC for all 72 entries")
        check("layout.accessor", r["literals_ok"], f"0xC0098D10 loads the scratch flag, {REC:#x} and {SCRATCH_ENTRY:#x} from its literals: {r['literals']}")
        check("layout.scratch_entry", r["scratch_name"].strip() == "for Voicing" and r["scratch_flag"] == 0, f"extra record named {r['scratch_name']!r}, flag {r['scratch_flag']}")
        check("layout.record_end", bytes.fromhex(r["tail_after_71"]).isalpha(), f"record 71 ends at {REC + COUNT * STRIDE:#x}; behind it starts the next structure, the oscillator names: {bytes.fromhex(r['tail_after_71'])!r}")
        out["layout"] = r

    if "reads" in results:
        print("\n== reads")
        seen = {int(o, 16) for o in results["reads"]}
        boot = {int(o, 16) for o in results["boot_reads"]}
        allowed = R_NAME | R_ALWAYS | R_SLOT
        check("reads.only_documented", seen <= allowed, f"read offsets outside the documented set: {sorted(hex(o) for o in seen - allowed)}")
        check("reads.always", (R_ALWAYS | R_NAME) <= seen, f"documented bytes that were not read: {sorted(hex(o) for o in (R_ALWAYS | R_NAME) - seen)}")
        unread = sorted(set(range(STRIDE)) - seen)
        print("     never read (record offsets):", " ".join(f"{o:02x}" for o in unread))
        print("     read at boot (record offsets):", " ".join(f"{o:02x}" for o in sorted(boot)))
        check("reads.boot_defaults", {0x16, 0x17} <= boot, "default depth and speed are read while the firmware starts (it fills the per-part memory)")
        out["reads"] = dict(read=sorted(seen), boot=sorted(boot), unread=unread, pcs=results["reads"])

    if "table" in results:
        print("\n== table")
        E, stats = results["table"]
        by = lambda off: stats[off]  # noqa: E731
        check("table.targets", sorted(by(TARGET).items()) == [(i, 12) for i in range(6)], f"target byte {by(TARGET)}: 6 values, 12 entries each")
        check("table.flag_follow", by(slot(0, "follow")) == {1: 72}, f"slot 0 follows MOD. DEPTH in all 72: {by(slot(0, 'follow'))}")
        check("table.curves", set(by(CURVE)) == {0, 1, 2, 3, 4}, f"curve values used: {by(CURVE)}")
        check("table.sync", by(SYNC) == {0: 35, 1: 37} and by(TEMPO_SYNC) == {0: 36, 1: 36}, f"phase reset {by(SYNC)}, tempo sync {by(TEMPO_SYNC)}")
        check("table.egbpm", by(EG_BPM) == {0: 60, 1: 12}, f"EG tempo flag {by(EG_BPM)}")
        used = [sum(1 for e in E if e[slot(k, 'lo')] or e[slot(k, 'hi')]) for k in range(SLOTS_N)]
        check("table.slots_used", used == [72, 4, 0, 0, 0, 0], f"entries with a nonzero strength range per slot: {used}")
        zero = [off for off in (0x14, 0x15, 0x16, 0x17, 0x18, 0x22, 0x23, 0x26, 0x27, 0x2A, 0x2B) if set(by(off)) != {0}]
        check("table.zero_bytes", not zero, f"bytes that are 0 in all 72 entries: 0x14 to 0x18, 0x22, 0x23, 0x26, 0x27, 0x2A, 0x2B (exceptions {zero})")
        caches = []
        for e in E:
            sp = e[SPEED]
            v = lerp(sp, min(e[RATE_LO], 127), min(e[RATE_HI], 127)) & 0xFF
            w = lerp(sp, min(e[EG_LO], 127), min(e[EG_HI], 127)) & 0xFF
            caches.append((e[CACHE_LFO] == v, e[CACHE_EG] == w))
        check("table.cache_equals_default", all(a and b for a, b in caches), f"+0x1F and +0x25 equal the speed output for the default speed in {sum(1 for a, b in caches if a and b)} of 72 entries")
        pos = neg = 0
        pos_ok = neg_ok = 0
        for e in E:
            for k in range(5):
                a, b, c = s8(e[slot(k, "lo")]), s8(e[slot(k, "hi")]), e[slot(k, "cache")]
                if a or b:
                    got = strength(a, b, e[DEPTH]) & 0xFF
                    mirrored = strength(a, b, 127 - e[DEPTH]) & 0xFF
                    if b > 0:
                        pos += 1
                        pos_ok += c == got
                    else:
                        neg += 1
                        neg_ok += c in (got, mirrored)
        print(f"     slot cache byte: positive ranges {pos_ok} of {pos} equal the strength at the default depth; negative ranges {neg_ok} of {neg} equal it at the mirrored depth 127-d, within the rounding")
        odd = [(i, k, e[slot(k, 'cache')]) for i, e in enumerate(E) for k in range(2, 6) if e[slot(k, 'cache')]]
        print(f"     cache bytes of an inactive slot that are not 0: {odd}")
        print(f"     the four bytes before type 0 (end of the structure in front of the table): {E[0][0:4].hex()}, before the other types 0: {sorted({e[0:4].hex() for e in E[1:]})}")
        out["table"] = {hex(o): v for o, v in stats.items()}

    if "model" in results:
        print("\n== model")
        r = results["model"]
        check("model.slots_all_types", r["bad_n"] == 0, f"{r['compared']} (type, depth, speed) combinations compared, {r['bad_n']} differ {r['bad'][:3]}")
        d = results["defaults"]
        check("model.defaults", d["same"] == 71 and len(d["differ"]) == 1, f"MOD. TYPE gives the default depth and speed in {d['same']} of 72 types; the one that differs: {d['differ']}")
        out["model"] = dict(model=r, defaults=d)

    if have("slots.base"):
        print("\n== slots (type 25 LFOTri Pitch, slot 0 unless said)")
        base = R("slots.base")
        k0 = R("slots.kind.0")
        check("slots.kind0_is_envelope", k0["m"]["acc_nz"] <= 2 and k0["m"]["acc_peak"] > 3000, f"kind 0 takes the envelope as source: the LFO type then moves the pitch once ({k0['m']['acc_nz']} calls) instead of {base['m']['acc_nz']}")
        check("slots.kind1_is_lfo", base["m"]["acc_nz"] > 1500 and base["m"]["acc_peak"] == 3481, f"kind 1 takes the LFO: pitch peak {base['m']['acc_peak']} in {base['m']['acc_nz']} calls")
        check("slots.engine_needs_a_voice", R("slots.idle")["m"]["n"] == 0 and base["m"]["n"] > 1500, f"the engine is called only while the part sounds: {R('slots.idle')['m']['n']} calls in 0.5 s of idle, {base['m']['n']} while a note plays")
        none = [R(f"slots.kind.{k}") for k in (2, 3, 255)]
        check("slots.kind_other_is_off", all(n["m"]["acc_peak"] == 0 for n in none), "kind 2, 3 and 255 add nothing")
        pitch_peaks = {}
        for a, b in ((0xC1, 0), (10, 20), (0, 20), (0xF6, 20), (5, 5), (20, 10), (0xEC, 0xFB), (0, 127), (0x80, 0x7F)):
            r = R(f"slots.range.{s8(a)}.{s8(b)}")
            e = bytearray(0x5C)
            e[DEPTH] = 31
            e[slot(0, "lo")], e[slot(0, "hi")], e[slot(0, "follow")] = a, b, 1
            want = model_slots(bytes(e), 100, 100)[3]
            pitch_peaks[(s8(a), s8(b))] = (r["slots"].split(" ")[3], f"{want:02x}", r["m"]["acc_peak"])
        check("slots.range_model", all(int(g, 16) == int(w, 16) for g, w, _ in pitch_peaks.values()), f"(lo, hi) -> (strength in RAM, model, pitch peak): {pitch_peaks}")
        r = R("slots.range.-10.20")
        check("slots.range_negative_lo_ignored", r["rows"] == base["rows"] and r["slots"] == base["slots"], "lo below 0 with hi above 0 behaves as 0 to 63, whatever the two values are")
        f0, f2 = R("slots.follow.0"), R("slots.follow.2")
        check("slots.follow_fixed", f0["slots"].split(" ")[3] == "0f" and f2["rows"] == base["rows"], f"follow 0 uses the entry's default depth 31 instead of MOD. DEPTH 100: strength {f0['slots'].split(' ')[3]} instead of 32; any nonzero value follows the knob")
        sp = R("slots.spare")
        check("slots.spare_no_effect", same_run(base, sp), "the byte after the target, and the two bytes after the follow flag, change nothing (rows, slots, display, DSP)")
        s2 = R("slots.second.filter")
        check("slots.second_slot", s2["m"]["acc_max"][3] > 15000 and s2["m"]["acc_max"][1] == base["m"]["acc_max"][1], f"a second slot on the filter adds a second destination: acc[3] peak {s2['m']['acc_max'][3]}, pitch unchanged {s2['m']['acc_max'][1]}")
        s2p = R("slots.second.pitch")
        check("slots.second_slot_adds", s2p["m"]["acc_max"][1] == 2 * base["m"]["acc_max"][1], f"two slots on the pitch add up: {s2p['m']['acc_max'][1]} = 2 x {base['m']['acc_max'][1]}")
        s5a, s5b = R("slots.sixth.without_tail"), R("slots.sixth.with_tail")
        check("slots.sixth_needs_next_entry", s5a["m"]["acc_max"][8] == 0 and s5b["m"]["acc_max"][8] > 12000, f"the sixth slot works only when its hi and follow bytes (the first bytes of the next entry's window) are set: level peak {s5a['m']['acc_max'][8]} without, {s5b['m']['acc_max'][8]} with")
        eg, egl = R("slots.eg.base"), R("slots.eg.lfo_source")
        check("slots.eg_source", eg["m"]["acc_peak"] > 12000 and egl["m"]["acc_peak"] < eg["m"]["acc_peak"] and egl["m"]["acc_nz"] > eg["m"]["acc_nz"], f"an envelope type (1, EG+ Pitch) with kind 1 follows its LFO unit instead of the envelope: peak {eg['m']['acc_peak']} -> {egl['m']['acc_peak']}")
        out["slots"] = {n: {"slots": R(n)["slots"], "m": R(n)["m"]} for n in plan.index if n.startswith("slots.")}

    if have("targets.0"):
        print("\n== targets (slot 0 of type 25, target code 0 to 12)")
        base = R("targets.0")
        scale = {}
        rows = []
        for t in range(0, 13):
            r = R(f"targets.{t}")
            idx = [i for i, v in enumerate(r["m"]["acc_max"]) if v]
            scale[t] = r["m"]["acc_max"][t] if t <= 10 else 0
            words = changed(base, r) if t else []
            steady = [w for w in words if r["a34"][w][1] > 8]
            rows.append((t, idx, scale[t], steady[:6], len(words)))
            print(f"     target {t:2d}: acc index {idx}, peak {scale[t]:6d}, A34 words that follow it {steady[:6]}, words changed in all {len(words)}")
        check("targets.index", all((rows[t][1] == [t]) for t in range(1, 11)) and rows[0][1] == [] and rows[11][1] == [] and rows[12][1] == [], "a slot target 1 to 10 adds to the destination of that number, 0 and above 10 add nothing")
        check("targets.scaling", scale[1] == 3481 and scale[3] == 20000 and all(scale[t] == 12800 for t in (2, 4, 5, 6, 7, 8, 9, 10)), f"scaling per destination at strength 50: pitch {scale[1]}, filter {scale[3]}, all others {sorted(set(scale[t] for t in (2, 4, 5, 6, 7, 8, 9, 10)))}")
        check("targets.dsp", all(rows[t][3] for t in (1, 2, 3, 8)), "pitch, OSC, filter and level reach the DSP as A34 words that take many values while the slot modulates")
        check("targets.high_codes", all(same_run(base, R(f"targets.{t}")) for t in (11, 12, 100, 255)), "target codes 11, 12, 100 and 255 change nothing (rows, slots, display, DSP): the engine adds 0 to a word nobody uses")
        out["targets"] = {t: dict(acc_index=rows[t][1], peak=rows[t][2], dsp_words=rows[t][3], dsp_changed=rows[t][4]) for t in range(13)}

    if have("curve.lfo.0"):
        print("\n== curve (waveform of the LFO unit, type 25 at a fixed speed)")
        shapes = {}
        for c in list(range(0, 10)) + [15, 16, 255]:
            r = R(f"curve.lfo.{c}")
            shapes[c] = classify(r["profile"])
            print(f"     curve {c:3d}: {shapes[c]:18s} distinct outputs {r['m']['lfo_distinct']:5d}  profile {r['profile']}")
        check("curve.waveforms", [shapes[c] for c in range(7)][:3] == ["Sägezahn fallend", "Rechteck", "Dreieck"] and shapes[5] == "Rechteck einpolig" and shapes[6] == "Sinus", f"0 saw, 1 square, 2 triangle, 5 unipolar square, 6 sine: {[shapes[c] for c in range(8)]}")
        check("curve.random", shapes[3] == "Zufall" and shapes[4] == "Zufall" and shapes[7] == "Zufall" and R("curve.lfo.4")["rows"] == R("curve.lfo.7")["rows"] and R("curve.lfo.3")["rows"] != R("curve.lfo.4")["rows"], "3 is sample and hold, 4 and 7 are the same random shape, 3 and 4 differ")
        check("curve.above_seven", all(R(f"curve.lfo.{c}")["rows"] == R("curve.lfo.0")["rows"] for c in (8, 9, 15, 16)) and R("curve.lfo.255")["rows"] == R("curve.lfo.3")["rows"], "8, 9, 15 and 16 give the saw of 0, 255 gives the sample and hold of 3: the index runs past the eight-byte table into other data")
        eg = {c: R(f"curve.eg.{c}")["m"] for c in (0, 1, 2, 6)}
        check("curve.eg_is_dc", all(m["cross"] <= 1 for m in eg.values()) and R("curve.eg.2")["rows"] != R("curve.eg.1")["rows"], f"on an envelope type the LFO unit stands still (rate 0), the curve only sets the constant it stands at: lfo range {[(m['lfo_min'], m['lfo_max']) for m in eg.values()]}")
        out["curve"] = {c: dict(shape=shapes[c], profile=R(f"curve.lfo.{c}")["profile"], distinct=R(f"curve.lfo.{c}")["m"]["lfo_distinct"]) for c in shapes}

    if have("speed.free.0"):
        print("\n== speed")
        free = {n: R(f"speed.free.{n}")["period"] for n in (0, 16, 32, 64, 96, 127)}
        print("     free LFO, rate index n (pair n, n): period in ms", free)
        check("speed.free_exponential", (free[0] is None or free[0] > 50000) and all(free[a] > free[b] for a, b in ((16, 32), (32, 64), (64, 96), (96, 127))) and free[127] < 20, "a higher rate index is faster, from standing still at 0 to about 100 Hz at 127")
        rng = {(lo, hi): R(f"speed.free.range.{lo}.{hi}") for lo, hi in ((0, 64), (64, 127), (127, 0))}
        check("speed.free_range", rng[(0, 64)]["slots"].startswith("40 ff") and rng[(64, 127)]["slots"].startswith("7f ff") and rng[(127, 0)]["slots"].startswith("00 ff"), f"MOD. SPEED 127 gives the upper end of the pair, a reversed pair (127, 0) turns the knob around: {[r['slots'][:5] for r in rng.values()]}")
        beat = lambda r: 600000 / r["tempo"]  # noqa: E731
        sync = {n: R(f"speed.sync.{n}") for n in range(1, 17)}
        beats = {n: round(r["period"] / beat(r), 3) for n, r in sync.items()}
        print(f"     tempo-synced LFO, step n: period in beats (tempo {sync[8]['tempo'] / 10} BPM):", beats)
        check("speed.sync_steps", abs(beats[8] - 1.0) < 0.02 and abs(beats[1] - 16.0) < 0.35 and abs(beats[2] - 8.0) < 0.2 and all(beats[n] > beats[n + 1] for n in range(1, 16)), "a higher step is shorter: step 8 is one beat, step 2 is eight, step 1 sixteen")
        over = {n: R(f"speed.sync.over.{n}")["period"] for n in (17, 20, 127)}
        check("speed.sync_over_16", all(p is not None and abs(p - sync[16]["period"]) <= 3 for p in over.values()), f"a synced LFO with a step above 16 runs as step 16: period {over} ms against {sync[16]['period']} ms")
        t9, t24 = R("speed.sync.8.tempo.900"), R("speed.sync.8.tempo.2400")
        check("speed.sync_follows_tempo", abs(t9["period"] / beat(t9) - 1) < 0.03 and abs(t24["period"] / beat(t24) - 1) < 0.03, f"step 8 is one beat at any tempo: {t9['period']} ms at {t9['tempo'] / 10} BPM, {t24['period']} ms at {t24['tempo'] / 10} BPM")
        eg = {s: R(f"speed.eg.s{s}")["m"].get("t_half") for s in (40, 100, 200)}
        check("speed.eg_time", eg[40] < eg[100] < eg[200], f"envelope decay (time to half) for MOD. SPEED 20, 50 and 100: {eg} ms")
        er = {(lo, hi): R(f"speed.eg.range.{lo}.{hi}") for lo, hi in ((0, 64), (64, 127), (127, 0), (100, 100))}
        check("speed.eg_range", er[(0, 64)]["slots"].split(" ")[2] == "40" and er[(127, 0)]["slots"].split(" ")[2] == "00" and er[(100, 100)]["m"]["t_half"] == R("speed.eg.s200")["m"]["t_half"], f"MOD. SPEED 127 gives the upper end of the EG pair; (100, 100) equals MOD. SPEED 100; (127, 0) turns the knob around: t_half {[ (k, v['m'].get('t_half')) for k, v in er.items()]}")
        bpm_on20, bpm_on100 = R("speed.eg.bpm.on.s20"), R("speed.eg.bpm.on.s100")
        t7, t7off = R("speed.eg.bpm.type7.s100"), R("speed.eg.bpm.type7.off")
        near = lambda a, b: abs(a - b) <= 2  # noqa: E731  # the time to half is read off calls about 0.5 ms apart
        check("speed.eg_bpm_flag", near(bpm_on20["m"]["t_half"], t7["m"]["t_half"]) and bpm_on20["m"]["acc_nz"] == t7["m"]["acc_nz"] and not near(t7off["m"]["t_half"], t7["m"]["t_half"]), f"+0x24 reads the speed output as a note step of the tempo: step 10 gives {t7['m']['t_half']} ms on type 7 (EG+ BPM Pitch) and {bpm_on20['m']['t_half']} ms on type 1 with the flag set, {t7off['m']['t_half']} ms on type 7 without the flag (a rate index)")
        check("speed.eg_bpm_clamp", near(R("speed.eg.bpm.on.step16")["m"]["t_half"], bpm_on100["m"]["t_half"]), f"with the flag a step of 50 acts as 16: {bpm_on100['m']['t_half']} ms, the same as step 16 ({R('speed.eg.bpm.on.step16')['m']['t_half']} ms)")
        t7t = {t: R(f"speed.eg.bpm.type7.tempo.{t}")["m"]["t_half"] for t in (900, 2400)}
        check("speed.eg_bpm_tempo", t7t[900] > t7["m"]["t_half"] > t7t[2400], f"tempo-synced envelope time at 90, 160 and 240 BPM: {t7t[900]}, {t7['m']['t_half']}, {t7t[2400]} ms")
        out["speed"] = dict(free=free, sync_beats=beats, eg_half=eg)

    if have("flags.sync.30.1"):
        print("\n== flags")
        fl = {(t, f): R(f"flags.sync.{t}.{f}")["first_phase"] for t in (30, 25) for f in (0, 1)}
        resets = {k: sum(1 for p in v[1:] if p == 0) for k, v in fl.items()}
        print("     phase (top 12 bits) at the first engine call after each of 8 notes; resets:", resets, fl)
        check("flags.sync", resets[(30, 1)] >= 1 and resets[(25, 1)] >= 1 and resets[(30, 0)] == 0 and resets[(25, 0)] == 0, "+0x1D set: the LFO phase goes back to 0 at some note starts (condition open); clear: never")
        late = {(t, pre): R(f"flags.sync.{t}.1.pre{pre}")["first_phase"] for t in (25, 30) for pre in (0.1, 0.2, 0.45)}
        late_resets = {k: sum(1 for p in v[1:] if p == 0) for k, v in late.items()}
        check("flags.sync_timing", all(n >= 1 for n in late_resets.values()), f"with 0.1, 0.2 and 0.45 s more lead before the notes the resets (of 7, flag set) are {dict(late_resets)}: which notes reset depends on the moment")
        fe, fd = R("flags.tempo.free_on"), R("flags.tempo.free_default")
        so = R("flags.tempo.sync_off")
        check("flags.tempo_sync", fe["slots"].startswith("ff 08") and fd["slots"].startswith("08 ff") and abs(fe["period"] - 600000 / fe["tempo"]) < 5, f"+0x1E set moves the speed output from out0 to out1 and the LFO becomes tempo-synced: step 8 gives {fe['period']} ms (a free rate index 8 gives {fd['period']} ms); cleared on a synced type: {so['period']} ms")
        out["flags"] = dict(first_phase={f"{k[0]}.{k[1]}": v for k, v in fl.items()}, resets={f"{k[0]}.{k[1]}": v for k, v in resets.items()})

    if have("unread.base.1"):
        print("\n== unread (bytes that nothing reads: a flip changes rows, slots, display and DSP words?)")
        bad = []
        for t in (1, 25):
            for off in UNREAD_SINGLE:
                if not same_run(R(f"unread.base.{t}"), R(f"unread.{t}.{off:#04x}")):
                    bad.append((t, hex(off)))
        check("unread.single", not bad, f"{2 * len(UNREAD_SINGLE)} single flips on an envelope type and an LFO type; differing: {bad}")
        badall = [t for t in (1, 25, 36) if not same_run(R(f"unread.base.{t}"), R(f"unread.all.{t}"))]
        check("unread.all", not badall, f"all {len(UNREAD_SINGLE)} unread bytes flipped at once on types 1, 25 and 36; differing: {badall}")
        nb = R("name.base")
        check("unread.name_after_nul", same_run(nb, R("name.after_nul")), "a byte after the name's terminator changes nothing")
        sixteen = R("name.sixteen")
        check("unread.name_sixteen", sixteen["m"]["acc_max"] == nb["m"]["acc_max"] and sixteen["slots"] == nb["slots"] and sixteen["fb_type"] != nb["fb_type"], "a name of 16 characters works: the terminator is the byte behind the field (+0x14, 0 in all 72 entries); the modulation reaches the same peaks (the longer name only shifts the timing of the engine's calls)")
        check("unread.name_shows", R("name.first_letter")["fb_type"] != nb["fb_type"], "the first letter of the name changes the display where the type is chosen (and only there: the knob pages stay the same)")
        out["unread"] = dict(offsets=[hex(o) for o in UNREAD_SINGLE])

    if "scratch" in results:
        print("\n== scratch")
        r = results["scratch"]
        check("scratch.accessor", all(v == hex(SCRATCH_ENTRY) for v in r["flag1"].values()) and r["flag0"][0] == hex(REC) and r["flag0"][25] == hex(REC + 25 * STRIDE) and r["flag0"][71] == hex(REC + 71 * STRIDE), f"flag 0: {r['flag0']}, flag 1: {r['flag1']}")
        check("scratch.changes_slots", r["slots_normal"] != r["slots_scratch"], f"type 25 with the flag set takes its slots from the record 'for Voicing': {r['slots_normal']} -> {r['slots_scratch']}")
        out["scratch"] = {k: v for k, v in r.items() if k != "scratch_entry"}

    if have("copy.curve.ram"):
        print("\n== copy (the same edit live in RAM, in a booted copy of the file, and in Korg's copy)")
        for tag in ("curve", "eg", "target"):
            base, ram, file = R(f"copy.{tag}.base") if tag != "curve" else R("copy.base"), R(f"copy.{tag}.ram"), R(f"copy.{tag}.file")
            check(f"copy.{tag}.ram_equals_file", ram["rows"] == file["rows"] and ram["slots"] == file["slots"] and not changed(ram, file), f"live write and booted copy give the same engine rows {ram['rows']} and slots {ram['slots']}")
            check(f"copy.{tag}.differs_from_original", ram["rows"] != base["rows"], f"and both differ from the unedited firmware ({base['rows']})")
        for tag in ("curve", "eg"):
            base = R("copy.base") if tag == "curve" else R("copy.eg.base")
            stock = R(f"copy.{tag}.stock")
            check(f"copy.{tag}.stock_unread", same_run(base, stock), "the same edit in Korg's copy at 0xD82EC changes nothing")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma separated sections: " + ",".join(SECTIONS))
    parser.add_argument("--jobs", type=int, default=0, help="worker processes (default GELUMPE_JOBS or 4)")
    parser.add_argument("--json", type=Path, help="write the numbers behind the checks here")
    args = parser.parse_args()
    only = None if not args.only else set(args.only.split(","))
    if only and only - set(SECTIONS):
        parser.error("unknown section " + ",".join(sorted(only - set(SECTIONS))))
    vsb_path = os.environ.get("E2_VSB")
    if not vsb_path:
        parser.error("E2_VSB is not set")
    vsb = Path(vsb_path).expanduser().read_bytes()
    flash = load_flash([str(Path(p).expanduser()) for p in os.environ["E2_FLASH"].split(os.pathsep) if p]) if os.environ.get("E2_FLASH") else None
    jobs = args.jobs or int(os.environ.get("GELUMPE_JOBS") or 4)
    want = lambda s: only is None or s in only  # noqa: E731

    plan = Plan()
    build(plan, only)
    tasks = [("modtable_probe", "run_spec", (s,)) for s in plan.specs]
    named = []
    for sec, fn, key in (("layout", "layout_task", "layout"), ("reads", "reads_task", "reads"), ("reads", "boot_reads_task", "boot_reads"),
                         ("model", "model_task", "model"), ("model", "defaults_task", "defaults"), ("scratch", "scratch_task", "scratch")):
        if want(sec):
            named.append(key)
            tasks.append(("modtable_probe", fn, ()))
    started = time.time()
    print(f"{len(plan.specs)} scenarios and {len(named)} other tasks on {min(jobs, len(tasks))} workers")
    done = parallel.run_tasks(tasks, {"payload": vsb[0x100:], "flash": flash}, jobs)
    plan.done = done[:len(plan.specs)]
    results = dict(zip(named, done[len(plan.specs):]))
    if want("table"):
        results["table"] = table_stats(vsb)
    print(f"measured in {time.time() - started:.0f} s")
    out = {}
    evaluate(plan, results, vsb, out)
    if args.json:
        args.json.write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    print(f"\n{len(FAILS)} checks failed" if FAILS else "\nall checks ok")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
