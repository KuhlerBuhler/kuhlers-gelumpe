#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare DSP functions of the electribe sampler in two BFIN9 workers.

Loads the DSP boot stream of a SYSTEM.VSB into each worker, fills a synthetic
context ("soup", as tools/dsp/bfsim_bench.py) and runs a small harness in the
DSP that calls one function N times with fixed register presets, all in one
run. Afterwards both workers must agree on the soup (FNV-1a) and on every
register, ASTAT and CYCLES included.

    qemu_compare.py SYSTEM.VSB --gnu GNU_WORKER --qemu QEMU_WORKER [--calls N]
                    [--func ADDR ...] [--bench --min-speedup X]
    qemu_compare.py --fuzz N [--seed S] [--fuzz-length L | --fuzz-class C] --gnu GNU_WORKER --qemu QEMU_WORKER
    qemu_compare.py SYSTEM.VSB --blocks N --gnu GNU_WORKER --qemu QEMU_WORKER

Without --func the 38 functions from docs/messungen/2026-11-16-qemu-bfin-
vergleich.md are compared. --bench times the calls in both workers and fails
when QEMU is not at least --min-speedup times faster. --fuzz runs N short
programs of random ALU, shift and DSP instructions (no memory access) from
random registers and compares all registers afterwards; an instruction that
raises an exception has to raise in both workers. --fuzz-class limits each
program to one instruction of a 32-bit class (mac, mult, alu, shift,
shiftimm); each difference line carries the start registers. --blocks
records N audio blocks of the coupled ARM/DSP run in GNU and replays them in
QEMU (qemu_blocks.py). Exit status 1 on any
difference or a missed speed-up.
"""
import argparse
import json
from pathlib import Path
import random
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'emu'))
import bfsim_bench  # noqa: E402
import dsp_extract  # noqa: E402
from blackfin_backend import BlackfinBackend, BackendError, REGISTER_NAMES, LIMIT  # noqa: E402

FUNCTIONS = {
    0xFFA0383C: 'Filterkern electribe', 0xFFA03A1C: 'Filterkern OB', 0xFFA03C3C: 'Filterkern Acid',
    0xFFA03EAC: 'Filterkern MS20', 0xFFA0411E: 'Filterkern MG', 0xFFA042DA: 'Filterkern P5',
    0xFFA03820: 'Verstärkungskern', 0xFFA078D8: 'Insert mKP2 Comp', 0xFFA00AD0: 'Insert SR1 Comp/Limiter',
    0xFFA08D98: 'Insert Cheap Comp', 0xFFA08508: 'Insert 2 Band EQ', 0xFFA086A8: 'Insert 4 Band EQ',
    0xFFA08B84: 'Insert Exciter', 0xFFA00C80: 'Insert Decimator', 0xFFA075D0: 'Insert Filter',
    0xFFA09138: 'Insert Distortion', 0xFFA08E7C: 'Insert Acid Driver', 0xFFA002B8: 'Insert Chorus',
    0xFFA0048C: 'Insert Flanger', 0xFFA08F48: 'Insert Phaser', 0xFFA00FE4: 'Insert Tremolo',
    0xFFA0777C: 'Insert Level Mod', 0xFFA007D0: 'Insert Ring Mod', 0xFFA08998: 'Insert Short Delay',
    0x1C77E34: 'Master mKP2 Comp', 0xEE3C: 'Master SR1 Comp/Limiter', 0x1C7D328: 'Master 4 Band EQ',
    0x15FB4: 'Master Wah', 0x1C7A908: 'Master MultiModeFilter', 0x1C81068: 'Master Distortion',
    0x15414: 'Master TubePre', 0xDDF8: 'Master Chorus', 0x10D2C: 'Master Flanger', 0x1C8005C: 'Master Phaser',
    0x1C7B5F0: 'Master Level Mod', 0x12ADC: 'Master Hall/Plate Reverb', 0x13FB8: 'Master Room Reverb',
    0x1C79B9C: 'Master Mod.Delay',
}
# Section 1 of the measurement: soup pages and constants before every call.
SOUP_REGS = ['R0', 'P0', 'P1', 'P2', 'P3', 'P4', 'I0', 'I1', 'I2', 'I3']
CONSTANTS = dict(R1=0x00012345, R2=0x7FF01234, R3=0x80001000, R4=0x00400000, R5=0x12345678, R6=0x0000ABCD,
                 R7=0x40000000, M0=4, M1=4, M2=4, M3=4)
HARNESS = bfsim_bench.HARNESS
COUNTER = bfsim_bench.RESULT
STACK = bfsim_bench.STACK
GROUPS = {'R': 0, 'P': 1, 'SP': 1, 'FP': 1, 'I': 2, 'M': 2, 'B': 3, 'L': 3}
FNV_PRIME = 0x01000193
# The GNU simulator keeps A0.X/A1.X sign-extended to 32 bits after "A0 = R0" and
# "A0.X = R0.L"; every GNU reader uses bits 0-7 only, QEMU keeps those 8 bits.
WIDTH = {'A0.X': 0xFF, 'A1.X': 0xFF}


def register_code(name):
    if name == 'SP':
        return 1, 6
    if name == 'FP':
        return 1, 7
    kind, number = name[0], int(name[1:])
    return GROUPS[kind], number + (4 if kind in 'ML' else 0)


def load_immediate(name, value):
    """reg.L = value.L; reg.H = value.H (LDIMMhalf)."""
    group, reg = register_code(name)
    low = 0xE100 | group << 3 | reg
    return [low, value & 0xFFFF, low | 0x40, value >> 16]


def harness(func, presets):
    """Halfwords of: loop: presets; P5 = func; CALL (P5); P4 = COUNTER; R0 = [P4];
    R0 += -1; [P4] = R0; CC = R0 == 0; IF !CC JUMP loop; halt: NOP."""
    words = []
    for name, value in presets:
        words += load_immediate(name, value)
    words += load_immediate('P5', func)
    words.append(0x0065)                      # CALL (P5)
    words += load_immediate('P4', COUNTER)
    words += [0xA020, 0x67F8, 0xB020, 0x0C00]  # R0 = [P4]; R0 += -1; [P4] = R0; CC = R0 == 0
    offset = -len(words)                      # BRCC counts halfwords from its own address
    words.append(0x1000 | offset & 0x3FF)     # IF !CC JUMP loop
    halt = HARNESS + 2 * len(words)
    words.append(0x0000)
    return struct.pack(f'<{len(words)}H', *words), halt


def dsp_regions(vsb):
    """Contiguous (target, bytes) regions of the boot stream, as dsp_extract.extract writes them."""
    memory = {}
    for _, _, flags, target, count, arg, payload in dsp_extract.parse(vsb):
        if flags & (dsp_extract.F_IGNORE | dsp_extract.F_INIT) or count == 0:
            continue
        if flags & dsp_extract.F_FILL:
            if count > dsp_extract.FILL_LIMIT:
                continue
            payload = struct.pack('<I', arg) * (count // 4)
        memory.update(zip(range(target, target + len(payload)), payload))
    regions = []
    for address in sorted(memory):
        if regions and regions[-1][0] + len(regions[-1][1]) == address:
            regions[-1][1].append(memory[address])
        else:
            regions.append([address, bytearray([memory[address]])])
    return regions


def fnv(data, value=0x811C9DC5):
    for (word,) in struct.iter_unpack('<I', data):
        value = ((value ^ word) * FNV_PRIME) & 0xFFFFFFFF
    return value


def presets():
    soup = bfsim_bench.SOUP_BASE + 0x800
    out = []
    for name in SOUP_REGS:
        out.append((name, soup))
        soup += 16 * bfsim_bench.PAGE
    return out + list(CONSTANTS.items())


def run_function(worker, regions, soup, func, calls):
    code, halt = harness(func, presets())
    with BlackfinBackend(worker, timeout=600) as dsp:
        for target, data in regions:
            for at in range(0, len(data), LIMIT):
                dsp.write(target + at, data[at:at + LIMIT])
        dsp.write(bfsim_bench.SOUP_BASE, soup)
        dsp.write(HARNESS, code)
        dsp.write(COUNTER, struct.pack('<I', calls))
        names = {name: i for i, name in enumerate(REGISTER_NAMES)}
        dsp.set_register(names['SP'], STACK)
        dsp.set_register(names['FP'], STACK)
        dsp.set_register(names['SYSCFG'], dsp.register(names['SYSCFG']) | 2)   # CCEN: CYCLES counts
        dsp.set_register(names['PC'], HARNESS)
        steps = 0
        started = time.perf_counter()
        while True:
            result = dsp.run(1000000, until=halt)
            steps += result['steps']
            if result['reached']:
                break
            if steps > 100000 * calls:
                raise BackendError(f'no return to the harness after {steps} instructions')
        seconds = time.perf_counter() - started
        registers = {name: dsp.register(i) for i, name in enumerate(REGISTER_NAMES)}
        checksum = fnv(dsp.read(bfsim_bench.SOUP_BASE, bfsim_bench.SOUP_SIZE))
    return dict(checksum=f'{checksum:08x}', steps=steps, seconds=seconds, registers=registers)


def compare(args):
    vsb = args.vsb.read_bytes()
    regions = dsp_regions(vsb)
    soup = bfsim_bench.soup_bytes()
    failed = False
    gnu_total = qemu_total = 0
    for func in args.func or FUNCTIONS:
        row = dict(func=f'{func:#x}', name=FUNCTIONS.get(func, ''), calls=args.calls)
        try:
            gnu = run_function(args.gnu, regions, soup, func, args.calls)
        except BackendError as error:
            row.update(status='GNU fehlgeschlagen', error=str(error)[:200])
            print(json.dumps(row, ensure_ascii=False))
            continue
        qemu = run_function(args.qemu, regions, soup, func, args.calls)
        differ = [n for n in REGISTER_NAMES
                  if (gnu['registers'][n] ^ qemu['registers'][n]) & WIDTH.get(n, 0xFFFFFFFF)]
        equal = gnu['checksum'] == qemu['checksum'] and not differ
        failed |= not equal
        gnu_total += gnu['seconds']
        qemu_total += qemu['seconds']
        row.update(status='gleich' if equal else 'abweichend', checksum=gnu['checksum'],
                   qemu_checksum=qemu['checksum'], registers_differ=differ,
                   cycles=gnu['registers']['CYCLES'], gnu_s=round(gnu['seconds'], 3),
                   qemu_s=round(qemu['seconds'], 3))
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if args.bench and qemu_total:
        speedup = gnu_total / qemu_total
        print(json.dumps(dict(gnu_s=round(gnu_total, 3), qemu_s=round(qemu_total, 3), speedup=round(speedup, 2),
                              min_speedup=args.min_speedup)))
        failed |= speedup < args.min_speedup
    return 1 if failed else 0


ASTAT_BITS = 0x030F316F
# 16-bit ALU2op, PTR2op, LOGI2op, comp3op, COMPI2op, CCflag; 32-bit dsp32mac/mult/alu/shift/shiftimm.
FUZZ_16 = [(0x4000, 0x4800), (0x4800, 0x5000), (0x5000, 0x6000), (0x6000, 0x7000), (0x0800, 0x1000)]
FUZZ_32 = [(0xC000, 0xC800), (0xC800, 0xD000)]
# --fuzz-class: base and random bits of the first word. ALU and shift keep the
# reserved bits 6..8 clear, which GNU rejects anyway.
FUZZ_CLASSES = {'mac': (0xC000, 0x1FF), 'mult': (0xC200, 0x1FF), 'alu': (0xC400, 0x3F),
                'shift': (0xC600, 0x1F), 'shiftimm': (0xC680, 0x1F)}
FUZZ_REGISTERS = ([f'R{i}' for i in range(8)] + [f'P{i}' for i in range(6)] + ['SP', 'FP'] + [f'{k}{i}' for k in 'IMB' for i in range(4)]
                  + ['A0.X', 'A0.W', 'A1.X', 'A1.W'])


def fuzz_program(rng, length, cls=None):
    words = []
    if cls:
        base, bits = FUZZ_CLASSES[cls]
        words = [base | rng.getrandbits(16) & bits, rng.randrange(0x10000)]
        return struct.pack('<3H', *words, 0), HARNESS + 4
    for _ in range(length):
        if rng.random() < 0.5:
            low, high = rng.choice(FUZZ_16)
            words.append(rng.randrange(low, high))
        else:
            low, high = rng.choice(FUZZ_32)
            words += [rng.randrange(low, high) & ~0x0800, rng.randrange(0x10000)]   # no multi-issue bundle
    halt = HARNESS + 2 * len(words)
    return struct.pack(f'<{len(words) + 1}H', *words, 0), halt


def fuzz_state(rng):
    state = {name: rng.getrandbits(32) for name in FUZZ_REGISTERS}
    state['A0.X'] = state['A0.X'] & 0xFF
    state['A1.X'] = state['A1.X'] & 0xFF
    astat = rng.getrandbits(32) & ASTAT_BITS & ~0xC   # AC0_COPY and V_COPY mirror AC0 and V
    astat |= (astat >> 12 & 1) << 2 | (astat >> 24 & 1) << 3
    state.update({f'L{i}': 0 for i in range(4)}, ASTAT=astat)
    return state


def fuzz_run(workers, worker, code, halt, state):
    names = {name: i for i, name in enumerate(REGISTER_NAMES)}
    try:
        if worker not in workers:
            workers[worker] = BlackfinBackend(worker, timeout=10).__enter__()
        dsp = workers[worker]
        dsp.write(HARNESS, code)
        for name, value in state.items():
            dsp.set_register(names[name], value)
        dsp.set_register(names['PC'], HARNESS)
        result = dsp.run(1000, until=halt)
        if not result['reached']:
            return dict(error=f"stopped at {result['pc']:#x}")
        return {name: dsp.register(i) for i, name in enumerate(REGISTER_NAMES)}
    except BackendError as error:
        workers.pop(worker).close()
        return dict(error=str(error).split('\n')[0][:120])


def fuzz(args):
    rng = random.Random(args.seed)
    workers = {}
    failed = exceptions = gnu_only = 0
    try:
        for trial in range(args.fuzz):
            code, halt = fuzz_program(rng, args.fuzz_length, args.fuzz_class)
            state = fuzz_state(rng)
            for (word,) in struct.iter_unpack('<H', code):
                if 0x4000 <= word < 0x40C0:
                    # Rd >>>= Rs, >>=, <<=: GNU shifts by the whole register as a C int, undefined above 31.
                    state[f'R{word >> 3 & 7}'] &= 0x1F
            gnu = fuzz_run(workers, args.gnu, code, halt, state)
            qemu = fuzz_run(workers, args.qemu, code, halt, state)
            if 'error' in gnu and 'error' not in qemu:
                gnu_only += 1    # illegal in GNU, executed by QEMU
                continue
            if 'error' in gnu or 'error' in qemu:
                same = 'error' in gnu and 'error' in qemu
                exceptions += same
                differ = [] if same else ['Ausnahme']
            else:
                differ = [n for n in REGISTER_NAMES if (gnu[n] ^ qemu[n]) & WIDTH.get(n, 0xFFFFFFFF)]
            if differ:
                failed += 1
                inputs = {n: f'{v:#x}' for n, v in state.items() if n[0] in 'RA' or n == 'ASTAT'}
                print(json.dumps(dict(trial=trial, code=code.hex(), differ=differ, inputs=inputs,
                                      gnu={n: f'{gnu[n]:#x}' for n in differ if n in gnu} or gnu,
                                      qemu={n: f'{qemu[n]:#x}' for n in differ if n in qemu} or qemu)), flush=True)
    finally:
        for dsp in workers.values():
            dsp.close()
    print(json.dumps(dict(programs=args.fuzz, seed=args.seed, both_raised=exceptions, illegal_only_in_gnu=gnu_only,
                          differ=failed)))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('vsb', type=Path, nargs='?')
    parser.add_argument('--gnu', type=Path, required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--calls', type=int, default=2000)
    parser.add_argument('--func', type=lambda text: int(text, 16), action='append')
    parser.add_argument('--bench', action='store_true')
    parser.add_argument('--min-speedup', type=float, default=10)
    parser.add_argument('--fuzz', type=int, metavar='N')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--fuzz-length', type=int, default=1, help='instructions per program')
    parser.add_argument('--fuzz-class', choices=sorted(FUZZ_CLASSES), help='one 32-bit insn of this class per program')
    parser.add_argument('--blocks', type=int, metavar='N', help='compare N audio blocks of the coupled run (qemu_blocks.py)')
    args = parser.parse_args()
    if args.blocks is not None:
        if args.vsb is None:
            parser.error('--blocks needs SYSTEM.VSB')
        import qemu_blocks
        result = qemu_blocks.run(args.vsb, args.gnu, args.qemu, args.blocks)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['ok'] else 1)
    if args.fuzz is None and args.vsb is None:
        parser.error('SYSTEM.VSB or --fuzz N is required')
    sys.exit(fuzz(args) if args.fuzz is not None else compare(args))


if __name__ == '__main__':
    main()
