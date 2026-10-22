"""Time a few small workloads on the own Electribe and in the emulator, RAM only, to compare the two clocks.

A stub of about 200 bytes goes to 0xC1000000 (the Hacktribe upload area) and runs through Hacktribe's execute
command 0x57, like vm_bench.py. It reads Timer 3 (TIM12 at 0x01F0D010, 150 MHz, measured on the device) and the
OS tick (0xC06A292C, 1 per ms) before and after one workload and stores both in its own data block:

    alu   add, eor with rotate, subs, bne: 4 instructions per round, no memory access
    mul   mul, add, subs, bne: 4 instructions per round, the multiplier in the loop
    mem   ldmia of 4 words, 4 adds, subs, bne: 7 instructions per round, a read-only sum over firmware RAM
          (0xC0040000, cached on the device)
    memu  the same sum over the uncached alias 0xC4400000 (device only: the emulator has no alias)
    memh  the same sum over a 4 KiB window again and again (8 instructions per round), so the data cache hits

Each workload runs at several sizes; the time per round is the slope of ticks against rounds, so the fixed
cost of the timer reads drops out. The emulator side also counts the stub's instructions with a code hook,
which gives exact instructions per round; the device cannot. The original bytes at the stub address are put
back at the end, as in led_show.py. Nothing but the stub area is written, flash and bootloader are not touched.

    python3 timing_probe.py --dry-run                  # device on USB: checks only, writes nothing
    python3 timing_probe.py --json device.json         # device on USB: the real run
    tools/emu/.venv/bin/python tools/device/timing_probe.py --emu SYSTEM.VSB --json emu.json
    python3 timing_probe.py --report device.json emu.json   # ratios, no device or emulator needed

Needs led_show.py and vm_bench.py next to it, ../patch/arm.py (and ../emu/machine.py for --emu); mido for the
device.
"""
import argparse
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "patch"))

import arm  # noqa: E402
import vm_bench as vb  # noqa: E402

STUB_AT = vb.STUB_AT
STUB_SIZE = vb.STUB_SIZE
TIMER = 0x01F0D000                       # timer 3: counter TIM12 at +0x10, PRD12 at +0x18, TCR at +0x20, TGCR at +0x24
TICK_HZ = 150e6
OS_TICK = 0xC06A292C                     # 1 per ms (docs/messungen/2026-10-15-blechy-power-off.md)
SUM_AT = 0xC0040000                      # firmware code, read-only
ALIAS = 0x04000000                       # uncached view of 0xC0000000..0xC3FFFFFF
DONE = 0x600D0000

EXPECTED = {                             # sha256 of the code the run relies on (own VSB), same as vm_bench.py
    (0xC00016A4, 0x34): "f33f00d1ca5392c857af29991ed0e4e10340bb4675df9e2f030af0caf730bd6a",
    (0xC0000040, 64): "0ecfbf472eb414c359f29af80817ad36cac542fe94b1f4e3cd4fe078a50e6de0",
    (0xC017059C, 512): "94975043805a3baa09d4916636d9ba93c9ab7c367efbf7b8d8d8e1b848219470",
}

# Data block at the start of the image (a host write always starts at 0xC1000000 and is a prefix of the image).
HEAD_LEN = 0x40
OFF = {"kind": 4, "n": 8, "addr": 12, "t0": 0x10, "t1": 0x14, "os0": 0x18, "os1": 0x1C, "prd": 0x20,
       "cpsr": 0x24, "sum": 0x28, "done": 0x2C, "tcr": 0x30, "tgcr": 0x34, "run": 0x3C}
KINDS = {"alu": 0, "mul": 1, "mem": 2, "memu": 2, "memh": 3}
INSNS_PER_ROUND = {"alu": 4, "mul": 4, "mem": 7, "memu": 7, "memh": 8}

SOURCE = """
head:   b       entry
        .space  0x3C
entry:  push    {r4-r12, lr}
        ldr     r11, =0xC1000000
        ldr     r6, [r11, #4]           ; kind
        ldr     r5, [r11, #8]           ; rounds
        ldr     r7, [r11, #12]          ; address for the sums
        ldr     r2, =0x01F0D000
        ldr     r12, =0xC06A292C
        .word   0xE10F0000              ; mrs r0, cpsr
        str     r0, [r11, #0x24]
        ldr     r0, [r2, #0x18]
        str     r0, [r11, #0x20]
        ldr     r0, [r2, #0x20]
        str     r0, [r11, #0x30]
        ldr     r0, [r2, #0x24]
        str     r0, [r11, #0x34]
        mov     r0, #1
        ldr     r1, =0x9E3779B1
        mov     lr, #0
        ldr     r9, [r12]
        ldr     r10, [r2, #0x10]
        cmp     r6, #0
        beq     alu
        cmp     r6, #1
        beq     mul
        cmp     r6, #3
        beq     memh
        b       mem
alu:    add     r0, r0, r1
        eor     r1, r1, r0, ror #3
        subs    r5, r5, #1
        bne     alu
        mov     lr, r0
        b       done
mul:    mul     r3, r0, r1
        add     r0, r3, #1
        subs    r5, r5, #1
        bne     mul
        mov     lr, r0
        b       done
mem:    ldmia   r7!, {r0, r1, r3, r4}
        add     lr, lr, r0
        add     lr, lr, r1
        add     lr, lr, r3
        add     lr, lr, r4
        subs    r5, r5, #1
        bne     mem
        b       done
memh:   ldmia   r7!, {r0, r1, r3, r4}
        bic     r7, r7, #0x1000
        add     lr, lr, r0
        add     lr, lr, r1
        add     lr, lr, r3
        add     lr, lr, r4
        subs    r5, r5, #1
        bne     memh
done:   ldr     r3, [r2, #0x10]
        ldr     r4, [r12]
        str     r10, [r11, #0x10]
        str     r3, [r11, #0x14]
        str     r9, [r11, #0x18]
        str     r4, [r11, #0x1C]
        str     lr, [r11, #0x28]
        ldr     r0, [r11, #0x3C]
        str     r0, [r11, #0x2C]
        mov     r0, #0
        pop     {r4-r12, lr}
        bx      lr
        .pool
"""


def build():
    a = arm.assemble(SOURCE, STUB_AT)
    if len(a.bytes) > STUB_SIZE:
        raise SystemExit(f"stub is {len(a.bytes)} bytes, over the {STUB_SIZE}-byte stub area")
    return a.bytes


def head_block(kind, n, addr, run):
    w = [0] * (HEAD_LEN // 4)
    w[0] = struct.unpack_from("<I", IMAGE, 0)[0]          # the branch word stays as it is
    w[OFF["kind"] // 4], w[OFF["n"] // 4], w[OFF["addr"] // 4] = KINDS[kind], n, addr
    w[OFF["run"] // 4] = DONE | run
    return struct.pack(f"<{len(w)}I", *w)


def parse(raw):
    return {k: struct.unpack_from("<I", raw, o)[0] for k, o in OFF.items()}


def reference(name, n):
    """The checksum the stub leaves in lr for alu and mul (None for the sums, which depend on RAM)."""
    m = 0xFFFFFFFF
    r0, r1 = 1, 0x9E3779B1
    for _ in range(n):
        if name == "alu":
            r0 = (r0 + r1) & m
            x = r0
            r1 ^= ((x >> 3) | (x << 29)) & m
        else:
            r0 = (r0 * r1 + 1) & m
    return r0 if name in ("alu", "mul") else None


def elapsed(a, b, prd):
    d = b - a
    return d if d >= 0 else d + prd + 1


class Probe(vb.Bench):
    """vb.Bench's guarded writes, read-backs and cache handling; its own execute with the done marker."""

    def execute_run(self, run, label):
        tries = self.args.retries
        for i in range(tries + 1):
            try:
                self.dev.execute(STUB_AT)
                return
            except SystemExit as e:
                why = e.code
            print(f"  {label}: no ack ({why})")
            time.sleep(self.args.settle)
            if parse(self.read(STUB_AT, HEAD_LEN))["done"] == DONE | run:
                print("  the stub finished and only its ack was lost; going on")
                return
            if i == tries:
                raise vb.StageFailed(f"{label}: no ack after {tries + 1} tries and no end mark")
            time.sleep(self.args.retry_pause * 2 ** i)
            self.make_coherent(IMAGE, HEAD_LEN)

    def run_once(self, name, n, addr, run):
        self.put(STUB_AT, head_block(name, n, addr, run))
        label = f"{name} n={n}"
        self.execute_run(run, label)
        w = parse(self.read(STUB_AT, HEAD_LEN))
        if w["done"] != DONE | run:
            raise vb.StageFailed(f"{label}: end mark missing, the stub did not finish")
        want = reference(name, n)
        if want is not None and w["sum"] != want:
            raise vb.StageFailed(f"{label}: checksum {w['sum']:#x} instead of {want:#x}")
        w["ticks"] = elapsed(w["t0"], w["t1"], w["prd"])
        w["os_ms"] = (w["os1"] - w["os0"]) & 0xFFFFFFFF
        w["insns"] = getattr(self.dev, "last_insns", None)
        return w


def sizes_for(name, prd_ns_per_round, target_us):
    """Round counts: a tiny one, then a ladder up to about target_us (estimate from the first run)."""
    top = max(8, int(target_us * 1e3 / prd_ns_per_round))
    if name in ("mem", "memu", "memh"):
        top = min(top, 16384)               # 256 KiB, the most the task asks for
    return [max(1, top // 16), max(2, top // 8), max(3, top // 4), max(4, top // 2), top]


def measure(probe, name, args, runs):
    addr = SUM_AT + (ALIAS if name == "memu" else 0)
    n0 = 64 if name not in ("mem", "memu", "memh") else 256
    first = probe.run_once(name, n0, addr, next(runs))
    ns_round = max(first["ticks"], 1) * 1e9 / TICK_HZ / n0
    ladder = sizes_for(name, ns_round, args.target_us)
    rows = []
    for n in ladder:
        reps = [probe.run_once(name, n, addr, next(runs)) for _ in range(args.repeat)]
        best = min(reps, key=lambda r: r["ticks"])
        rows.append({"n": n, "ticks": best["ticks"], "all": sorted(r["ticks"] for r in reps), "insns": best["insns"],
                     "sum": best["sum"], "os_ms": best["os_ms"], "cpsr": best["cpsr"], "prd": best["prd"],
                     "tcr": best["tcr"], "tgcr": best["tgcr"]})
        print(f"  {name} n={n}: " + " ".join(f"{t * 1e6 / TICK_HZ:.1f}" for t in rows[-1]["all"]) + " us")
    return rows


def slope(rows, key):
    xs = [r["n"] for r in rows]
    ys = [r[key] for r in rows]
    a, b = vb.fit(xs, ys)
    return a, b


def run(dev, args):
    probe = Probe(dev, None, args)
    for (addr, length), digest in EXPECTED.items():
        if hashlib.sha256(probe.read(addr, length)).hexdigest() != digest:
            raise SystemExit(f"code at {addr:#x} differs from the measured build; nothing written")
    if args.emu:                            # the emulator's clock stands still between two SysEx reads
        print("checks passed: firmware code matches")
    else:
        t_a = struct.unpack("<I", probe.read(OS_TICK, 4))[0]
        time.sleep(0.5)
        t_b = struct.unpack("<I", probe.read(OS_TICK, 4))[0]
        print(f"checks passed: firmware code matches; OS tick {t_a} then {t_b} after 0.5 s ({t_b - t_a} ms)")
        if not 300 < t_b - t_a < 800:
            raise SystemExit("the OS tick does not run at 1 kHz; nothing written")
    original = probe.read(STUB_AT, len(IMAGE))
    print(f"{len(IMAGE)} bytes at {STUB_AT:#x} saved")
    if args.dry_run:
        print("dry run: nothing written")
        return {}
    results, failure = {}, None
    counter = iter(range(1, 1 << 15))
    try:
        probe.upload(IMAGE)
        for name in args.workloads:
            if name == "memu" and args.emu:
                print("  memu skipped: the emulator has no uncached alias")
                continue
            results[name] = measure(probe, name, args, counter)
            if name == "alu":                # one long run (about 20 ms) to check Timer 3's clock against the 1 kHz OS tick
                n = int(20e6 / summary(results[name])["ns_round"])
                w = probe.run_once("alu", n, 0, next(counter))
                results["_clock"] = {"n": n, "ticks": w["ticks"], "os_ms": w["os_ms"]}
                print(f"  clock check: {w['ticks']} ticks of Timer 3 = {w['ticks'] / TICK_HZ * 1e3:.2f} ms at 150 MHz, OS tick says {w['os_ms']} ms")
    except vb.StageFailed as e:
        failure = e
    finally:
        time.sleep(0.2)
        try:
            probe.put(STUB_AT, original)
            probe.make_coherent(original)
            print("original bytes at the stub address restored")
        except vb.StageFailed as e:
            print(f"  warning: {e}")
        except SystemExit as e:
            print(f"  RESTORE FAILED ({e.code}): the stub bytes are still at {STUB_AT:#x}; rerun to restore them, or restart the device")
            failure = failure or vb.StageFailed("restore failed")
    if failure:
        print(f"stopped: {failure}")
        raise SystemExit(2)
    return results


def summary(rows):
    """ns per round two ways. "best": the fastest single run divided by its rounds, over all runs of all sizes; an
    interrupt handler that lands in a run only makes it slower, so this is the interrupt-free cost (the fixed cost
    of the timer reads is under 1 % at these sizes). "fit": the slope of the best run per size against rounds,
    which includes the interrupts that hit every long run."""
    tick_ns = 1e9 / TICK_HZ
    a, b = slope(rows, "ticks")
    best = min(t / r["n"] for r in rows for t in r["all"] if r["n"] >= 256)
    out = {"ns_round": best * tick_ns, "fit_ns_round": b * tick_ns, "fixed_ns": a * tick_ns}
    if rows[-1]["insns"] is not None:
        ia, ib = slope(rows, "insns")
        out["insns_round"], out["insns_fixed"] = ib, ia
    return out


def report(label, results):
    print(f"== {label} ==")
    for name, rows in results.items():
        if name == "_clock":
            print(f"  clock check: {rows['ticks'] / TICK_HZ * 1e3:.2f} ms by Timer 3 at 150 MHz, {rows['os_ms']} ms by the OS tick")
            continue
        s = summary(rows)
        extra = f", {s['insns_round']:.3f} instructions/round" if "insns_round" in s else ""
        print(f"  {name}: best {s['ns_round']:.2f} ns/round, fit {s['fit_ns_round']:.2f} (fixed {s['fixed_ns']:.0f} ns){extra}")


def compare(dev, emu):
    """Device against emulator per workload: ns per round, and device ns per emulator instruction."""
    print("== device against emulator ==")
    print(f"{'workload':8} {'dev ns/round':>13} {'emu ns/round':>13} {'emu insn/round':>15} {'dev/emu':>8} {'dev ns/insn':>12}")
    out = {}
    for name, rows in dev["results"].items():
        if name == "_clock" or name not in emu["results"]:
            continue
        d, e = summary(rows), summary(emu["results"][name])
        insns = e.get("insns_round") or INSNS_PER_ROUND[name]
        e_ns = insns * emu.get("ns_per_insn", 5)
        out[name] = {"dev_ns_round": d["ns_round"], "emu_ns_round_timer": e["ns_round"], "emu_ns_round_model": e_ns,
                     "ratio": d["ns_round"] / e_ns, "dev_ns_per_insn": d["ns_round"] / insns}
        print(f"{name:8} {d['ns_round']:13.2f} {e_ns:13.2f} {insns:15.3f} {d['ns_round'] / e_ns:8.3f} {d['ns_round'] / insns:12.3f}")
    return out


def emu_link(vsb):
    dev, m = vb.emulator_link(vsb)
    return dev, m


def main():
    global IMAGE
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--emu", metavar="VSB")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--workloads", default="alu,mul,memh,mem,memu")
    p.add_argument("--repeat", type=int)
    p.add_argument("--target-us", type=float, default=1500, help="time of the longest run per workload")
    p.add_argument("--settle", type=float, default=2.0)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--retry-pause", type=float, default=1.5)
    p.add_argument("--pause", type=float)
    p.add_argument("--evict-kib", type=int)
    p.add_argument("--json", metavar="FILE")
    p.add_argument("--report", nargs=2, metavar=("DEVICE_JSON", "EMU_JSON"), help="compare two result files, touch nothing")
    a = p.parse_args()
    if a.report:
        dev, emu = (json.loads(Path(f).read_text()) for f in a.report)
        report("device", dev["results"])
        report("emulator", emu["results"])
        compare(dev, emu)
        return
    IMAGE = build()
    a.workloads = a.workloads.split(",")
    unknown = [w for w in a.workloads if w not in KINDS]
    if unknown:
        raise SystemExit(f"unknown workload {unknown}")
    on_device = not a.emu
    a.repeat = a.repeat or (5 if on_device else 2)
    a.caches = on_device
    a.pause = a.pause if a.pause is not None else (0.3 if on_device else 0.0)
    a.evict_kib = a.evict_kib if a.evict_kib is not None else (128 if on_device else 0)
    if a.target_us > 20000:
        raise SystemExit("--target-us above 20000 could disturb audio and MIDI; refused")
    m = None
    if a.emu:
        dev, m = vb.emulator_link(a.emu)
    else:
        from led_show import Device, mido_ask
        dev = Device(mido_ask())
    results = run(dev, a)
    if m is not None:
        m.run_until(m.time_ns / 1e9 + 0.5)
        print("emulator asserts:", m.asserts)
    if results:
        report("emulator" if a.emu else "device", results)
        if a.json:
            ns = None
            if a.emu:
                sys.path.insert(0, str(HERE.parent / "emu"))
                import machine
                ns = machine.NS_PER_INSN
            Path(a.json).write_text(json.dumps({"mode": "emulator" if a.emu else "device", "tick_hz": TICK_HZ,
                                                "ns_per_insn": ns, "results": results}, indent=1))
            print(f"results written to {a.json}")


IMAGE = b""

if __name__ == "__main__":
    main()
