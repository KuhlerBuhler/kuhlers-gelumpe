#!/usr/bin/env python3
"""Checks the tube curve patch in the QEMU DSP core (BFIN9 worker): loads the DSP boot stream of a SYSTEM.VSB with and
without data/patches/tube-curve*.json and calls the master output function the way the frame code does (R0 = the
stereo pair), once per sample pair.

    off     patched routine with the parameter block as the boot stream leaves it (zeros) gives Korg's clipper output
            bit for bit, unpatched program as reference
    drive   every TUBE DRIVE step gives tools/dsp/tube_model.py model() bit for bit
    cycles  CYCLES per call: Korg's clipper, patched OFF, patched ON

    tube_qemu.py SYSTEM.VSB PATCH.json [--emu DIR] [--worker PATH] [--pairs N] [--json OUT]

--emu is the tools/emu folder that holds blackfin_backend.py (the QEMU tooling of #671; this branch does not carry
it). Exit status 1 on any difference.
"""
import argparse
import json
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'patch'))
import tube_model  # noqa: E402
import tube_curve  # noqa: E402  (tools/patch/tube_curve.py: targets and stream places)
import dsp_extract  # noqa: E402

PAIR = 0x03100000          # stereo pair in SDRAM, as [P4 + 0x10] in the frame
HALT = 0x03000000          # return address, a NOP the run stops at
STACK = 0x03F00000


def patched(vsb, patch):
    out = bytearray(vsb)
    for change in patch['changes']:
        data = bytes.fromhex(change['bytes'])
        out[change['file']:change['file'] + len(data)] = data
    return bytes(out)


def regions(vsb, stream):
    memory = {}
    for _, _, flags, target, count, arg, payload in dsp_extract.parse(vsb, *stream):
        if flags & (dsp_extract.F_IGNORE | dsp_extract.F_INIT) or count == 0:
            continue
        if flags & dsp_extract.F_FILL:
            if count > dsp_extract.FILL_LIMIT:
                continue
            payload = struct.pack('<I', arg) * (count // 4)
        memory.update(zip(range(target, target + len(payload)), payload))
    out = []
    for address in sorted(memory):
        if out and out[-1][0] + len(out[-1][1]) == address:
            out[-1][1].append(memory[address])
        else:
            out.append([address, bytearray([memory[address]])])
    return out


class Dsp:
    def __init__(self, backend, worker, vsb, stream):
        self.mod = backend
        self.dsp = backend.BlackfinBackend(worker, timeout=600).__enter__()
        self.reg = {name: i for i, name in enumerate(backend.REGISTER_NAMES)}
        for target, data in regions(vsb, stream):
            for at in range(0, len(data), backend.LIMIT):
                self.dsp.write(target + at, bytes(data[at:at + backend.LIMIT]))
        self.dsp.write(HALT, b'\0\0')
        self.dsp.set_register(self.reg['SYSCFG'], self.dsp.register(self.reg['SYSCFG']) | 2)   # CCEN

    def call(self, func, left, right):
        """Runs func on one pair; returns (left, right, cycles)."""
        d, r = self.dsp, self.reg
        d.write(PAIR, struct.pack('<ii', left, right))
        d.set_register(r['R0'], PAIR)
        d.set_register(r['SP'], STACK)
        d.set_register(r['FP'], STACK)
        d.set_register(r['RETS'], HALT)
        d.set_register(r['PC'], func)
        start = d.register(r['CYCLES'])
        result = d.run(10000, until=HALT)
        if not result['reached']:
            raise SystemExit(f'{func:#x} did not return: {result}')
        cycles = (d.register(r['CYCLES']) - start) & 0xFFFFFFFF
        return (*struct.unpack('<ii', d.read(PAIR, 8)), cycles)

    def close(self):
        self.dsp.close()


def inputs(n, seed=1):
    rng = random.Random(seed)
    edge = [0, 1, -1, 2 ** 31 - 1, -2 ** 31, 2 ** 30, -2 ** 30, 0x361962E9, -0x361962E9, 0x7FFF0000, -0x7FFF0000]
    out = [(x, -x if x != -2 ** 31 else 0) for x in edge]
    for k in range(n - len(out)):
        scale = rng.choice((31, 31, 28, 24, 16))
        out.append((rng.randrange(-2 ** scale, 2 ** scale), rng.randrange(-2 ** scale, 2 ** scale)))
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument('vsb', type=Path)
    a.add_argument('patch', type=Path)
    a.add_argument('--emu', type=Path, default=Path(__file__).resolve().parents[1] / 'emu')
    a.add_argument('--worker')
    a.add_argument('--pairs', type=int, default=2000)
    a.add_argument('--json', type=Path)
    args = a.parse_args()
    sys.path.insert(0, str(args.emu))
    try:
        import blackfin_backend
        import blackfin_worker
    except ImportError:
        raise SystemExit(f'no blackfin_backend.py in {args.emu}: pass --emu with the QEMU tooling of #671')
    worker = args.worker or blackfin_worker.find(None)
    vsb = args.vsb.read_bytes()
    patch = json.loads(args.patch.read_text())
    target = next(k for k, t in tube_curve.TARGETS.items() if t['id'] == patch['id'])
    t = tube_curve.TARGETS[target]
    pairs = inputs(args.pairs)
    report = dict(vsb=args.vsb.name, patch=patch['id'], pairs=len(pairs))
    failed = False

    orig = Dsp(blackfin_backend, worker, vsb, t['stream'])
    korg = [orig.call(t['clipper'], l, r) for l, r in pairs]
    orig.close()

    new = Dsp(blackfin_backend, worker, patched(vsb, patch), t['stream'])
    block = new.dsp.read(tube_model.PARAM, tube_model.PARAM_SIZE)
    report['boot_block_zero'] = block == bytes(tube_model.PARAM_SIZE)
    failed |= not report['boot_block_zero']
    off = [new.call(t['at'], l, r) for l, r in pairs]
    bad = [i for i, (k, o) in enumerate(zip(korg, off)) if k[:2] != o[:2]]
    report['off'] = dict(differ=len(bad), first=[(pairs[i], korg[i][:2], off[i][:2]) for i in bad[:3]])
    failed |= bool(bad)

    report['drive'] = {}
    on_cycles = []
    for step in range(1, len(tube_model.STEPS) + 1):
        words = tube_model.params(step)
        new.dsp.write(tube_model.PARAM, tube_model.block(step))
        got = [new.call(t['at'], l, r) for l, r in pairs]
        want = [(tube_model.model(l, words), tube_model.model(r, words)) for l, r in pairs]
        bad = [i for i, (g, w) in enumerate(zip(got, want)) if g[:2] != w]
        report['drive'][step] = dict(differ=len(bad), first=[(pairs[i], want[i], got[i][:2]) for i in bad[:3]])
        failed |= bool(bad)
        on_cycles += [g[2] for g in got]
    new.close()
    report['cycles'] = dict(korg=[min(k[2] for k in korg), max(k[2] for k in korg)],
                            off=[min(o[2] for o in off), max(o[2] for o in off)],
                            on=[min(on_cycles), max(on_cycles)])
    report['ok'] = not failed
    text = json.dumps(report, indent=1)
    print(text)
    if args.json:
        args.json.write_text(text + '\n')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
