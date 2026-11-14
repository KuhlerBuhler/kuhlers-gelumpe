#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded DSP reset/RTOS diagnostics with a host-loaded boot stream."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'emu'))
from blackfin_backend import BlackfinPort, BackendError
from blackfin_rom import SysControl
from dsp_extract import STREAM_RAM, STREAM_LEN, file_offset


def observe_frames(port, frames, entry, budget=1000000):
    """Wait for native frame entries without changing control flow."""
    if not isinstance(frames, int) or not 1 <= frames <= 1000 or entry & 1:
        raise ValueError('bounded frame count and aligned frame entry required')
    backend = port.backend
    observations = []
    for index in range(frames + 1):
        result = backend.run(budget, until=entry)
        if not result['reached']:
            raise BackendError(f'native frame entry not reached within {budget} instructions: {result}')
        observations.append(dict(pc=backend.register(53), sp=backend.register(14),
                                 caller_return=backend.register(37), sample_index=backend.register(4),
                                 seqstat=backend.register(47),
                                 cycles=backend.register(44) | (backend.register(45) << 32)))
        if index < frames:
            backend.run(1)
    return dict(completed=frames, entries=observations, sport=backend.sport_status())


def observe_host_roundtrip(port, address, budget=100000):
    """Transfer generated words through HOSTDP and wait for native acknowledgments."""
    if not isinstance(address, int) or address & 1 or not 0 <= address <= 0xFFFFFFE0:
        raise ValueError('an aligned bounded HOSTDP test address is required')
    if not isinstance(budget, int) or not 1 <= budget <= 1000000:
        raise ValueError('a bounded HOSTDP completion budget is required')
    backend = port.backend

    def configure(command):
        if not backend.host_status() & 0x80:
            raise BackendError('HOSTDP configuration is not ready')
        for word in (command, address & 65535, address >> 16, 16, 2, 0, 0):
            backend.host_control(word)
        backend.run(200)

    def completion():
        steps = 0
        while steps < budget:
            status = backend.host_status()
            if status & 8 and not status & 1:
                return status
            executed = backend.run(min(1000, budget - steps))['steps']
            if executed <= 0:
                raise BackendError('HOSTDP completion made no execution progress')
            steps += executed
        raise BackendError('native HOSTDP completion was not acknowledged within its budget')

    expected = [(0xA55A + index * 233) & 65535 for index in range(16)]
    configure(0xAB)
    for word in expected:
        backend.host_write(word)
    full = bool(backend.host_status() & 2)
    after_write = completion()
    configure(0xA9)
    before_drain = bool(backend.host_status() & 0x8000)
    observed = [backend.host_read() for _ in range(16)]
    after_drain = bool(backend.host_status() & 0x8000)
    after_read = completion()
    if observed != expected or not full or before_drain or not after_drain:
        raise BackendError('HOSTDP roundtrip data or completion ordering is incorrect')
    return dict(address=address, words=16, fifo_full_before_dma=full, roundtrip=True,
                read_done_before_drain=before_drain, read_done_after_drain=after_drain,
                after_write=after_write, after_read=after_read, full_arm_coupling=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', required=True, type=Path)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--virtual', action='store_true', help='instruction-only diagnostic without interrupt hardware')
    parser.add_argument('--boot-steps', type=int, default=250000000, help='bounded native instruction budget, at most 500000000')
    parser.add_argument('--sport-core-hz', type=int, help='explicit simulated CCLK for the 48 kHz external SPORT0 clock')
    parser.add_argument('--sport-input', choices=('silence', 'lcg'), default='silence')
    parser.add_argument('--observe-frames', type=int, default=0)
    parser.add_argument('--frame-entry', type=lambda value: int(value, 0))
    parser.add_argument('--host-transport', choices=('compatibility', 'fifo'), default='compatibility')
    parser.add_argument('--host-address', type=lambda value: int(value, 0), help='scratch address for a generated 16-word FIFO roundtrip')
    args = parser.parse_args()
    if args.observe_frames and (args.frame_entry is None or args.sport_core_hz is None):
        parser.error('--observe-frames requires --frame-entry and --sport-core-hz')
    if args.host_address is not None and (args.host_transport != 'fifo' or args.sport_core_hz is None or args.virtual):
        parser.error('--host-address requires --host-transport fifo, --sport-core-hz and operating mode')
    vsb = args.vsb.read_bytes()
    stream = vsb[file_offset(STREAM_RAM):file_offset(STREAM_RAM)+STREAM_LEN]
    rom = SysControl()
    sport = None if args.sport_core_hz is None else dict(core_hz=args.sport_core_hz, input=args.sport_input)
    try:
        with BlackfinPort(args.worker, operating=not args.virtual, timeout=15, rom=rom,
                          boot_steps=args.boot_steps, sport=sport, host_transport=args.host_transport) as port:
            port.boot(stream)
            port.wait_ready()
            observations = observe_frames(port, args.observe_frames, args.frame_entry) if args.observe_frames else None
            host = observe_host_roundtrip(port, args.host_address) if args.host_address is not None else None
            report = dict(mode='reset-entry', full_boot=False, initialization=port.boot_report,
                          rom_model=rom.report(),
                          sport=port.backend.sport_status() if sport else None,
                          frame_observation=observations,
                          host_roundtrip=host,
                          note='An initialization response alone does not prove full DSP operation')
        print(json.dumps(dict(ok=True, **report), indent=2))
        return 0
    except (BackendError, ValueError) as error:
        print(json.dumps(dict(ok=False, error=str(error), full_boot=False, rom_model=rom.report(), sport_config=sport), indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())
