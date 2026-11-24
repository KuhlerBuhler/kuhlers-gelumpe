#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare whole audio blocks of the coupled ARM/DSP run in two BFIN9 workers.

record: runs the coupled emulator session (tools/emu/blackfin_cases.py) on the
GNU worker and writes every worker request with a hash of its answer. After
each advance that finished a block of --block SPORT TX frames it adds a
snapshot: all 54 registers (ASTAT and CYCLES included) and DSP L1 memory;
every 1000 blocks and at the last block also the first 32 MiB of DSP
SDRAM.

replay: sends the same requests in the same order to the QEMU worker and
compares every answer. The first difference ends the run with the request
index, the operation and the block it fell in.

    qemu_blocks.py SYSTEM.VSB --gnu GNU_WORKER --qemu QEMU_WORKER --blocks N [--trace FILE]
    qemu_blocks.py SYSTEM.VSB --gnu GNU_WORKER --qemu QEMU_WORKER --mfx 0-31

--mfx boots, then sets each MFX TYPE with Korg's own setter, hits pad 1 on
noise input and compares the same way, a snapshot after each type.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'emu'))
import blackfin_backend  # noqa: E402
from blackfin_backend import BlackfinBackend, BackendError, _ROMCall  # noqa: E402
import blackfin_cases  # noqa: E402
from blackfin_backend import BlackfinPort  # noqa: E402
from blackfin_rom import SysControl  # noqa: E402
from firmware import identify  # noqa: E402
from machine import Machine, blank_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402

CORE_HZ = 516096000
RATE = 48000
L1 = ((0xFF800000, 0x8000), (0xFF900000, 0x8000), (0xFFB00000, 0x1000))
SDRAM = (0, 32 << 20)
HEADER = struct.Struct('<IIIIIB32s')   # op, address, count, extra, data length, outcome, answer hash
OK, ROM, SNAPSHOT = 0, 1, 2
# A0.X and A1.X: GNU keeps 32 bits after some writes (SET_AREG32 gives 0xffffffff), QEMU keeps the 40-bit
# accumulator. Every GNU instruction reads only the low 8 bits, so the comparison does too.
EXTENSIONS = (32, 34)


def answer_digest(op, address, answer):
    if op == 3 and address in EXTENSIONS and len(answer) == 4:
        answer = struct.pack('<I', struct.unpack('<I', answer)[0] & 0xFF)
    return hashlib.sha256(answer).digest()


def progress(label, done, total):
    folder = Path.home() / '.claude' / 'progress'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{label}.json'
    path.with_suffix('.tmp').write_text(json.dumps(dict(label=label, done=done, total=total, updatedAt=time.time(),
                                                        staleAfter=600)))
    os.replace(path.with_suffix('.tmp'), path)


class Recorder:
    def __init__(self, out, blocks, block):
        self.out, self.blocks, self.block = out, blocks, block
        self.done = 0
        self.inside = False
        self.original = BlackfinBackend._request

    def install(self):
        recorder = self

        def request(backend, op, address, count, data=b'', extra=0):
            try:
                answer = recorder.original(backend, op, address, count, data, extra)
            except _ROMCall as call:
                recorder.write(op, address, count, extra, data, ROM,
                               hashlib.sha256(struct.pack('<I', call.steps) + struct.pack('<I', call.caller)
                                              + str(sorted(call.registers.items())).encode()).digest())
                raise
            recorder.write(op, address, count, extra, data, OK, answer_digest(op, address, answer))
            if op in (18, 20) and not recorder.inside:
                recorder.after_advance(backend)
            return answer
        BlackfinBackend._request = request

    def uninstall(self):
        BlackfinBackend._request = self.original

    def write(self, op, address, count, extra, data, outcome, digest):
        self.out.write(HEADER.pack(op, address, count, extra, len(data), outcome, digest))
        self.out.write(data)

    def marker(self, kind):
        self.out.write(HEADER.pack(0, kind, self.done, 0, 0, SNAPSHOT, bytes(32)))

    def after_advance(self, backend):
        self.inside = True
        try:
            frames = backend.sport_status()['tx_frames']
            if frames >= (self.done + 1) * self.block and self.done < self.blocks:
                last = self.done
                self.done = frames // self.block
                self.snapshot(backend, full=self.done // 1000 > last // 1000 or self.done >= self.blocks)
                if self.done % 100 == 0:
                    progress('QEMU-Bloecke-Aufnahme', min(self.done, self.blocks), self.blocks)
        finally:
            self.inside = False

    def snapshot(self, backend, *, full):
        self.marker(1)
        for number in range(54):
            backend.register(number)
        for address, size in L1 + ((SDRAM,) if full else ()):
            for at in range(address, address + size, blackfin_backend.LIMIT):
                backend.read(at, min(blackfin_backend.LIMIT, address + size - at))


def record(vsb, worker, trace, blocks, block):
    raw = vsb.read_bytes()
    if len(raw) != 0x200100:
        raise ValueError('expected a complete SYSTEM.VSB')
    seconds = math.ceil((blocks * block / RATE + 1.5) * 10) / 10
    with gzip.open(trace, 'wb', compresslevel=1) as out:
        recorder = Recorder(out, blocks, block)
        recorder.install()
        try:
            report = blackfin_cases.cases(raw[0x100:], worker, core_hz=CORE_HZ, seconds=seconds, wall_timeout=1800)
            recorder.inside = True
            recorder.done = max(recorder.done, recorder.blocks)
            recorder.marker(2)
        finally:
            recorder.uninstall()
    return dict(report=report, blocks=recorder.done, seconds=seconds)


MFX_SETTER, GLOBALS = 0xC0048A64, 0xC0691334      # Korg's MFX TYPE setter and its object (mfx_cases.py)


def mfx_session(payload, worker, recorder, types, dwell=.4, boot_limit=6.0):
    """Boot, then switch the master effect to each of `types` with the firmware's own setter, hit pad 1 and let
    it play `dwell` seconds on noise input. A snapshot ends each type; the report keeps SPORT TX hash and
    SEQSTAT per type."""
    report = dict(types=[])
    with BlackfinPort(worker, operating=True, timeout=15, rom=SysControl(),
                      sport=dict(core_hz=CORE_HZ, input='lcg'), host_transport='fifo') as port:
        machine = Machine(payload, flash=blank_flash(), profile=identify(payload), dsp_backend=port)
        try:
            while not machine.booted and machine.time_ns < boot_limit * 1e9 and not machine.asserts:
                machine.run_until(machine.time_ns / 1e9 + .05)
            if not machine.booted:
                raise BackendError('main screen not reached')
            dev = Dev(payload, machine=machine)
            for kind in types:
                dev.call(MFX_SETTER, dev.u32(GLOBALS) + 0x4004, kind, 1)
                machine.send([4, 0, 0, 100, 1])
                machine.run_until(machine.time_ns / 1e9 + dwell / 2)
                machine.send([4, 0, 0, 0, 0])
                machine.run_until(machine.time_ns / 1e9 + dwell / 2)
                recorder.inside = True
                try:
                    sport = port.backend.sport_status()
                    report['types'].append(dict(type=kind, tx_hash=f"{sport['tx_hash']:#010x}",
                                                tx_frames=sport['tx_frames'], seqstat=port.backend.register(47)))
                    recorder.snapshot(port.backend, full=kind == types[-1])
                finally:
                    recorder.inside = False
            report.update(arm_time_ns=machine.time_ns, assertions=machine.asserts)
        except (BackendError, ValueError, RuntimeError) as error:
            report['error'] = str(error)
    return report


def record_mfx(vsb, worker, trace, types, block=64):
    raw = vsb.read_bytes()
    if len(raw) != 0x200100:
        raise ValueError('expected a complete SYSTEM.VSB')
    with gzip.open(trace, 'wb', compresslevel=1) as out:
        recorder = Recorder(out, 10 ** 9, block)
        recorder.install()
        try:
            report = mfx_session(raw[0x100:], worker, recorder, types)
            recorder.inside = True
            recorder.marker(2)
        finally:
            recorder.uninstall()
    return dict(report=report, blocks=recorder.done)


def entries(trace):
    with gzip.open(trace, 'rb') as source:
        while True:
            head = source.read(HEADER.size)
            if not head:
                return
            op, address, count, extra, size, outcome, digest = HEADER.unpack(head)
            yield op, address, count, extra, source.read(size), outcome, digest


def replay(worker, trace, total):
    backend = BlackfinBackend(worker, operating=True, timeout=15)
    block = requests = 0
    started = time.monotonic()
    try:
        for index, (op, address, count, extra, data, outcome, digest) in enumerate(entries(trace)):
            if outcome == SNAPSHOT:
                block = count
                if address == 1 and block % 100 == 0:
                    progress('QEMU-Bloecke-Vergleich', min(block, total), total)
                continue
            requests += 1
            try:
                answer = BlackfinBackend._request(backend, op, address, count, data, extra)
                got, answered = OK, answer_digest(op, address, answer)
            except _ROMCall as call:
                answer = (struct.pack('<I', call.steps) + struct.pack('<I', call.caller)
                          + str(sorted(call.registers.items())).encode())
                got, answered = ROM, hashlib.sha256(answer).digest()
            if got != outcome or answered != digest:
                detail = dict(index=index, op=op, address=f'{address:#x}', count=count, block=block,
                              outcome=dict(gnu=outcome, qemu=got))
                if op == 3:
                    detail['register'] = blackfin_backend.REGISTER_NAMES[address]
                    detail['qemu_value'] = f'{struct.unpack("<I", answer)[0]:#x}'
                return dict(ok=False, requests=requests, blocks=block, first_difference=detail)
    finally:
        backend.close()
    return dict(ok=True, requests=requests, blocks=block, seconds=round(time.monotonic() - started, 1))


def run(vsb, gnu, qemu, blocks=10000, block=64, keep=None):
    """Record on `gnu`, replay on `qemu`; returns the JSON report. `keep` keeps the trace there."""
    trace = keep or Path(os.environ.get('TMPDIR', '/tmp')) / f'qemu-blocks-{os.getpid()}.bin.gz'
    try:
        recorded = record(vsb, gnu, trace, blocks, block)
        if 'error' in recorded['report']:
            raise BackendError(f'GNU session failed: {recorded["report"]["error"]}')
        if recorded['blocks'] < blocks:
            raise BackendError(f'only {recorded["blocks"]} blocks recorded')
        result = replay(qemu, trace, blocks)
        result.update(block_frames=block, model_seconds=recorded['seconds'], trace_bytes=trace.stat().st_size)
    except (OSError, BackendError, ValueError) as error:
        result = dict(ok=False, error=str(error))
    finally:
        if keep is None and trace.exists():
            trace.unlink()
    return result


def run_mfx(vsb, gnu, qemu, types, keep=None):
    trace = keep or Path(os.environ.get('TMPDIR', '/tmp')) / f'qemu-mfx-{os.getpid()}.bin.gz'
    try:
        recorded = record_mfx(vsb, gnu, trace, types)
        if 'error' in recorded['report']:
            raise BackendError(f'GNU session failed: {recorded["report"]["error"]}')
        result = replay(qemu, trace, recorded['blocks'])
        result.update(gnu=recorded['report'], trace_bytes=trace.stat().st_size)
    except (OSError, BackendError, ValueError) as error:
        result = dict(ok=False, error=str(error))
    finally:
        if keep is None and trace.exists():
            trace.unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('vsb', type=Path)
    parser.add_argument('--gnu', type=Path, required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--blocks', type=int, default=10000)
    parser.add_argument('--block', type=int, default=64, help='SPORT TX frames per block')
    parser.add_argument('--trace', type=Path, help='keep the GNU trace here (default: a temporary file)')
    parser.add_argument('--mfx', metavar='A-B', help='instead: switch MFX TYPE A..B after boot, pad 1 each')
    args = parser.parse_args()
    if args.mfx:
        first, last = (int(x) for x in args.mfx.split('-'))
        result = run_mfx(args.vsb, args.gnu, args.qemu, list(range(first, last + 1)), args.trace)
    else:
        result = run(args.vsb, args.gnu, args.qemu, args.blocks, args.block, args.trace)
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
