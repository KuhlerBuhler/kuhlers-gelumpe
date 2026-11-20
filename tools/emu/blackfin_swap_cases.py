#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check PCM relocation and voice sample bindings in the executed native DSP."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import time

from blackfin_backend import BlackfinPort, BackendError
import blackfin_worker
from blackfin_rom import SysControl
from firmware import identify
from machine import blank_flash
import swap_cases
from swap_cases import Box, DSP_MIN, wav_pcm
import sample_swap as spec


SAMPLES = {500: ('native500', 2000), 501: ('native501', 1000), 502: ('native502', 2000)}
CAP = 6144
POOL_MIN = DSP_MIN + spec.DSP_GUARD
VOICE = 0xFF900EAC


def verify_patch_code(payload, screens):
    for address, expected in spec.build_code(screens)[0]:
        at = address - 0xC0000000
        if payload[at:at + len(expected)] != expected:
            raise ValueError(f'sample swap code differs at {address:#x}; rebuild the candidate with the current sources')


def bound_session(machine, deadline):
    run_slice = machine.run_slice

    def bounded_slice(*args, **kwargs):
        if time.monotonic() >= deadline:
            raise BackendError('native sample swap session deadline exceeded')
        return run_slice(*args, **kwargs)
    machine.run_slice = bounded_slice


def cases(payload, worker, *, core_hz, wall_timeout=1200):
    if not isinstance(wall_timeout, (int, float)) or not math.isfinite(wall_timeout) or not 1 <= wall_timeout <= 1800:
        raise ValueError('a finite session deadline between 1 and 1800 seconds is required')
    profile = identify(payload)
    if profile.build not in ('stock', 'hacktribe'):
        raise ValueError('sample swap currently supports the two red firmware builds')
    verify_patch_code(payload, profile.screens)
    deadline = time.monotonic() + wall_timeout
    report = dict(ok=False, hardware_contact=False, samples=[], checks={},
                  verification_scope='startup, PCM transport, residency, voice sample address and DSP sample reads',
                  sample_playback_end_verified=False)
    box = None
    with BlackfinPort(worker, operating=True, timeout=15, rom=SysControl(),
                      sport=dict(core_hz=core_hz, input='lcg'), host_transport='fifo') as port:
        def observe(box):
            bound_session(box.m, deadline)

        try:
            box = Box(payload, blank_flash(), SAMPLES, [500] + [0] * 15, cap=CAP,
                      before_boot=observe, dsp_backend=port)

            def inspect(slot, phase):
                start, size = box.extent(slot)
                actual = box.dsp_bytes(start, size)
                expected = wav_pcm(slot, SAMPLES[slot][1])
                row = dict(slot=slot, phase=phase, time_ns=box.m.time_ns,
                           start=start, bytes=size, resident=box.resident(slot),
                           in_pool=POOL_MIN <= start and start + size <= POOL_MIN + CAP,
                           pcm_equal=actual == expected,
                           actual_sha256=hashlib.sha256(actual).hexdigest(),
                           expected_sha256=hashlib.sha256(expected).hexdigest())
                report['samples'].append(row)
                return row

            initial = inspect(500, 'start')
            initial_residents = box.residents(SAMPLES)
            part = box.dev.call(spec.FIRMWARE['PART'], 0)
            record = box.u32(part + 8)
            inspect(500, 'before_selection')
            selected = []
            for slot in (501, 502):
                box.m.send([1, 1, 0, 1, 0])
                settled = box.until(lambda: box.u16(record + 8) == slot and box.u16(part + 0x34) == slot, 3)
                selected.append(settled)
                if not settled:
                    raise BackendError(f'sample {slot} did not finish loading and selection')
                inspect(slot, 'selected')

            final = {slot: inspect(slot, 'after_eviction') for slot in (501, 502)}
            before = struct.unpack('<624I', port.backend.read(VOICE, 24 * 26 * 4))
            port.backend.watch_memory(final[502]['start'], final[502]['bytes'])
            box.m.send([4, 0, 0, 100, 1])
            box.run(.02)
            active = struct.unpack('<624I', port.backend.read(VOICE, 24 * 26 * 4))
            early_accesses = port.backend.memory_accesses()
            opened = [i for i in range(24) if before[i * 26] == 0 and active[i * 26] != 0]
            box.run(.12)
            later = struct.unpack('<624I', port.backend.read(VOICE, 24 * 26 * 4))
            later_accesses = port.backend.memory_accesses()
            voice_index = opened[0] if len(opened) == 1 else None
            voice = active[voice_index * 26:voice_index * 26 + 26] if voice_index is not None else None
            ended = later[voice_index * 26] if voice_index is not None else None
            start, size = final[502]['start'], final[502]['bytes']
            reads = later_accesses['dma_read']
            # Watched window is the relocated PCM only, so every counted DMA read is a sample read.
            dsp_reads_sample = (early_accesses['dma_read']['accesses'] > 0
                                and reads['accesses'] > early_accesses['dma_read']['accesses']
                                and start <= reads['address'] < start + size)
            playback_end = dsp_reads_sample and reads['address'] + reads['width'] >= start + size
            clock = port.backend.clock_status()
            expected_cycles = (int(box.m.time_ns) - port._clock_origin_ns) * core_hz // 1000000000
            checks = dict(native_initialization=port.initialized,
                          native_clock=clock['cycles'] == expected_cycles,
                          swap_active=box.state('MODE') == 1,
                          initially_only_current_sample=initial['resident'] and initial_residents == [500],
                          selected=all(selected),
                          pcm=all(row['pcm_equal'] for row in report['samples']),
                          final_resident_pcm=all(row['pcm_equal'] for row in final.values()),
                          pool=all(row['in_pool'] for row in report['samples']),
                          no_sample_overlap=(final[501]['start'] + final[501]['bytes'] <= final[502]['start']
                                             or final[502]['start'] + final[502]['bytes'] <= final[501]['start']),
                          unused_sample_evicted=not box.resident(500),
                          other_samples_resident=box.resident(501) and box.resident(502),
                          voice_uses_relocated_sample=voice is not None and voice[10] == final[502]['start'],
                          dsp_reads_relocated_sample=dsp_reads_sample,
                          dsp_reaches_sample_end=playback_end,
                          no_arm_assertions=not box.m.asserts,
                          no_dsp_exception=port.backend.register(47) == 0)
            report.update(ok=all(checks.values()), checks=checks, clock=clock,
                          sample_playback_end_verified=playback_end,
                          opened_voices=opened, voice_index=voice_index,
                          gate_cleared_without_release=ended == 0,
                          sample_accesses_early=early_accesses, sample_accesses_later=later_accesses,
                          voice_gate=voice[0] if voice is not None else None,
                          voice_sample=voice[10] if voice is not None else None, voice_gate_later=ended,
                          arm_time_ns=box.m.time_ns, assertions=box.m.asserts)
        except (BackendError, ValueError, RuntimeError) as error:
            report['error'] = str(error)
            if box is not None:
                report['arm_time_ns'] = box.m.time_ns
    return report


CORE_HZ = 516096000                 # the core clock the measurements ran at (docs/messungen/2026-11-16-qemu-dsp-kern.md)
REQUIRED = 'GELUMPE_DSP_REQUIRED'   # set in CI: a missing worker fails the case instead of leaving it out


def has_native_swap(payload):
    """check.py runs this module for a red copy with the sample swap, when a Blackfin worker is there or required."""
    if not swap_cases.has_hooks(payload) or identify(payload).build not in ('stock', 'hacktribe'):
        return False
    return bool(blackfin_worker.find() or os.environ.get(REQUIRED))


def report_entries(report):
    if report.get('error'):
        return [{"id": "dspswap:session", "ok": False, "detail": report['error']}]
    return [{"id": f"dspswap:{name}", "ok": bool(ok), "detail": f"executed DSP ({report.get('verification_scope')}): {name} {ok}"}
            for name, ok in report['checks'].items()]


def cases_task():
    import parallel
    worker = blackfin_worker.find()
    if worker is None:
        return [{"id": "dspswap:worker", "ok": False,
                 "detail": f'{REQUIRED} is set, but there is no Blackfin worker (tools/dsp/build_qemu.py, BFIN_WORKER)'}]
    try:
        report = cases(parallel.shared["payload"], worker, core_hz=CORE_HZ)
    except (OSError, BackendError, ValueError) as error:
        report = dict(error=str(error))
    return report_entries(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--worker', type=Path, help='default: blackfin_worker.find()')
    parser.add_argument('--core-hz', type=int, required=True)
    parser.add_argument('--wall-timeout', type=float, default=1200)
    args = parser.parse_args()
    try:
        worker = blackfin_worker.find(args.worker)
        if worker is None:
            raise ValueError('no Blackfin worker: build one with tools/dsp/build_qemu.py or pass --worker')
        raw = args.patched.read_bytes()
        if len(raw) != 0x200100:
            raise ValueError('expected a complete SYSTEM.VSB')
        report = cases(raw[0x100:], worker, core_hz=args.core_hz, wall_timeout=args.wall_timeout)
    except (OSError, BackendError, ValueError) as error:
        report = dict(ok=False, hardware_contact=False, error=str(error))
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
