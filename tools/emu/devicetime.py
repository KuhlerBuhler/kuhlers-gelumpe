# SPDX-License-Identifier: GPL-2.0-only
"""How long code that runs in the emulator takes on the device.

The emulator's base rate is `machine.NS_PER_INSN` for every instruction. Measured on the own device against the
emulator (docs/messungen/2026-10-16-emulator-timing.md, `tools/device/timing_probe.py`):

- Plain ALU code with a taken branch every fourth instruction runs at 5.04 ns per instruction: the emulator's
  5 ns is right for it, and stays the base rate.
- A dependent multiply costs 6.7 ns more than the 5 ns the emulator charges.
- Reading memory costs more per byte the less the data cache helps: 0.5 ns/B when it hits, 6.8 ns/B when it
  misses on every line (a streaming read over more than the cache holds), 12.4 ns/B uncached.

`Pace` applies those surcharges while the emulator runs (machine.Machine.run_slice): once per slice it looks at
the code where the CPU stopped and gives the device nanoseconds per instruction for the next slice. See its docstring for
how and for what it assumes. `estimate_device_ns` is the same arithmetic for a stretch counted by hand.
"""

ALU_NS_PER_INSN = 5.0           # = machine.NS_PER_INSN (test_devicetime.py); the device measured 5.04
MUL_EXTRA_NS = 6.7              # per dependent multiply, on top of the ALU rate
READ_HIT_EXTRA_NS_PER_BYTE = 0.5
READ_STREAM_EXTRA_NS_PER_BYTE = 6.8
READ_UNCACHED_EXTRA_NS_PER_BYTE = 12.4

# Model assumptions (Modellannahme in docs/emulator.md), not measured:
DCACHE_BYTES = 16 * 1024        # AM1808 data sheet: 16 KiB data cache. Measured only: 4 KiB hit, 256 KiB missed
UNCACHED = (0xC4000000, 0xC8000000)   # the uncached view of the SDRAM (timing_probe.py ALIAS)
RAM = (0xC0000000, 0xC8000000)  # reads elsewhere (registers, the vector page) get no surcharge
WALK_GAP_NS = 1_000_000         # two samples of one loop at most this far apart belong to the same walk (a slice of
                                # SLICE instructions takes up to about 0.7 ms at the uncached rate)
SCAN = 64                       # instructions looked at ahead of the sampled one
LOOP_BACK = 1024                # a backward branch at most this many bytes back closes a loop around the sample


def estimate_device_ns(emulator_ns, mul_insns=0, read_hit_bytes=0, read_stream_bytes=0, read_uncached_bytes=0):
    """Device nanoseconds for a stretch the emulator timed at `emulator_ns`, given what it did besides plain
    instructions: dependent multiplies, bytes read from data that was in the cache, bytes streamed from RAM, bytes
    read through the uncached alias (0xC4000000)."""
    return (emulator_ns + mul_insns * MUL_EXTRA_NS + read_hit_bytes * READ_HIT_EXTRA_NS_PER_BYTE
            + read_stream_bytes * READ_STREAM_EXTRA_NS_PER_BYTE + read_uncached_bytes * READ_UNCACHED_EXTRA_NS_PER_BYTE)


# ---- ARM decoding, only as far as the cost needs it ------------------------------------------------------------------
END, LOOP_END = "end", "loop"


def decode(w, at):
    """What one ARM instruction at `at` costs and how it ends a block:
    (multiplies, read: (base register, bytes, writes the base back) or None, flow) with flow None (falls through),
    ("loop", target) for a plain branch backwards, ("fwd", target) for a conditional branch forwards, END otherwise
    (call, return, jump, load or write of pc)."""
    cond = w >> 28
    if cond == 0xF:
        return 0, None, (END if (w >> 25) & 7 == 0b101 else None)       # blx imm ends; pld and friends do not
    op = (w >> 25) & 7
    if op == 0b101:                                                     # b, bl
        if w & (1 << 24):
            return 0, None, END
        off = w & 0xFFFFFF
        target = (at + 8 + ((off - (1 << 24) if off & 0x800000 else off) << 2)) & 0xFFFFFFFF
        if target <= at:
            return 0, None, (LOOP_END, target)
        return 0, None, (("fwd", target) if cond != 0xE else END)
    if w & 0x0FFFFFD0 == 0x012FFF10:                                    # bx, blx reg
        return 0, None, END
    if op <= 1 and w & 0x0F0000F0 == 0x00000090:                         # mul, mla, umull, smull, umlal, smlal
        return 1, None, None
    if op == 0b000 and w & 0x90 == 0x90 and (w >> 5) & 3:                # ldrh, ldrsb, ldrsh, ldrd, strh, strd
        sh, load, p, wb = (w >> 5) & 3, w & (1 << 20), w & (1 << 24), w & (1 << 21)
        rn = (w >> 16) & 15
        if load:
            return 0, (rn, 1 if sh == 2 else 2, not p or bool(wb)), None
        if sh == 2:                                                     # ldrd
            return 0, (rn, 8, not p or bool(wb)), None
        return 0, None, None
    if (w >> 26) & 3 == 1:                                              # ldr, ldrb, str, strb
        if (w >> 25) & 1 and w & 0x10:
            return 0, None, None                                        # media instructions, not on this core
        load, rd, rn = w & (1 << 20), (w >> 12) & 15, (w >> 16) & 15
        if not load:
            return 0, None, None
        read = (rn, 1 if w & (1 << 22) else 4, not w & (1 << 24) or bool(w & (1 << 21)))
        return 0, read, (END if rd == 15 else None)
    if op == 0b100:                                                     # ldm, stm
        if not w & (1 << 20):
            return 0, None, None
        n = bin(w & 0xFFFF).count("1")
        return 0, ((w >> 16) & 15, 4 * n, bool(w & (1 << 21))), (END if w & 0x8000 else None)
    if op <= 1 and (w >> 12) & 15 == 15 and not 8 <= (w >> 21) & 15 <= 11:   # mov pc, add pc, ...
        return 0, None, END
    return 0, None, None


def advances(w):
    """The register an add or sub of an immediate to itself moves (rN = rN +- imm), else None."""
    if (w >> 26) & 3 == 0 and w & (1 << 25) and (w >> 21) & 15 in (2, 4) and (w >> 12) & 15 == (w >> 16) & 15:
        return (w >> 16) & 15
    return None


class Region:
    """The code a sample stands for: the loop around it, or the instructions from it to the end of its block.
    `fixed` is the surcharge in ns that does not depend on data (multiplies, reads that cannot miss: off pc or sp),
    `reads` the other reads as (base register, bytes, walks: the base moves through memory inside a loop)."""
    __slots__ = ("start", "n", "fixed", "reads", "loop")

    def __init__(self, start, n, fixed, reads, loop):
        self.start, self.n, self.fixed, self.reads, self.loop = start, n, fixed, reads, loop


def region(pc, words):
    """Region for a sample at `pc`. `words(address, count)` gives the instruction words there."""
    ahead = words(pc, SCAN)
    end, loop = None, None
    for i, w in enumerate(ahead):
        _, _, flow = decode(w, pc + 4 * i)
        if flow is None or flow[0] == "fwd":
            continue
        if flow != END and pc - LOOP_BACK <= flow[1] <= pc:
            loop = flow[1]
        end = pc + 4 * i
        break
    if end is None:
        end = pc + 4 * (len(ahead) - 1)
    start = loop if loop is not None else pc
    body = words(start, (end - start) // 4 + 1)
    moved = {advances(w) for w in body} if loop is not None else set()
    fixed, reads = 0.0, []
    for i, w in enumerate(body):
        mul, read, _ = decode(w, start + 4 * i)
        fixed += mul * MUL_EXTRA_NS
        if read:
            rn, size, wb = read
            if rn in (13, 15):
                fixed += size * READ_HIT_EXTRA_NS_PER_BYTE
            else:
                reads.append((rn, size, loop is not None and (wb or rn in moved)))
    return Region(start, len(body), fixed, tuple(reads), loop is not None)


class Pace:
    """Device ns per instruction for the code at a sample point, with what the data cache does.

    The emulator runs in slices of up to `machine.SLICE` instructions and cannot afford to look at every memory
    access (a Unicorn memory hook with a Python callback makes it 5 to 7 times slower, measured). So where a slice
    stops after its instructions it takes the pc as a sample: the code there, decoded once (`region`), stands for the
    next slice, which is charged at its rate (machine.Machine.run_slice says which slices give no sample). In a loop
    the region is the whole loop, so every sample in it gives the same rate; in straight code it is the rest of the
    block.

    Reads: off pc or sp they hit the cache. Through the uncached alias they cost the uncached rate. A read whose base
    register walks through memory in a loop (written back, or moved by an add/sub of itself) misses on every line once
    the walk covers more than the data cache: two samples of that loop in quick succession (WALK_GAP_NS) more than
    DCACHE_BYTES apart, moving the same way. Everything else hits; so does a walk's first sample. Writes, the instruction cache, mispredicted branches and peripheral
    reads cost nothing extra; Thumb code runs at the base rate."""

    def __init__(self):
        self.regions = {}               # (pc, word at pc) -> Region; derived from the code, not part of a snapshot
        self.walks = {}                 # (loop start, base register) -> [first address, last address, last time, span]

    def rate(self, pc, word, reg, now_ns, words):
        """ns per instruction at `pc` (holding `word`). `reg(n)` reads register n, `words(address, count)` code."""
        key = (pc, word)
        r = self.regions.get(key)
        if r is None:
            r = self.regions[key] = region(pc, words)
        extra = r.fixed
        for rn, size, walks in r.reads:
            a = reg(rn)
            if not RAM[0] <= a < RAM[1]:
                continue
            if UNCACHED[0] <= a < UNCACHED[1]:
                extra += size * READ_UNCACHED_EXTRA_NS_PER_BYTE
            elif walks and self._streams((r.start, rn), a, now_ns):
                extra += size * READ_STREAM_EXTRA_NS_PER_BYTE
            else:
                extra += size * READ_HIT_EXTRA_NS_PER_BYTE
        return ALU_NS_PER_INSN + extra / r.n

    def _streams(self, key, a, now_ns):
        """True when the loop `key` walks on from where it was sampled last, and the walk covers more than the cache."""
        walk = self.walks.get(key)
        if walk is None or now_ns - walk[2] > WALK_GAP_NS or (a - walk[1]) * (walk[1] - walk[0]) < 0:
            self.walks[key] = [a, a, now_ns, 0]         # a new walk, or the loop turned round: from here
            return False
        walk[1], walk[2] = a, now_ns
        walk[3] = max(walk[3], abs(a - walk[0]))
        return walk[3] > DCACHE_BYTES
