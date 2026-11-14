#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run original ARM and DSP startup with a shared clock and native HOSTDP."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

from blackfin_backend import BlackfinPort, BackendError
from blackfin_rom import SysControl
from firmware import identify
from machine import Machine, DSP_CTRL, DSP_DATA, blank_flash, hardware_flash


def cases(payload, worker, *, core_hz, seconds=1, input='silence', wall_timeout=600):
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not .01 <= seconds <= 30:
        raise ValueError('a bounded ARM/DSP session between .01 and 30 seconds is required')
    if not isinstance(wall_timeout, (int, float)) or not math.isfinite(wall_timeout) or not 1 <= wall_timeout <= 1800:
        raise ValueError('a finite session deadline is required')
    rom = SysControl()
    traffic = dict(control=0, write=0, read=0)
    report = dict(ok=False, full_boot=False, hardware_contact=False, checks=[], traffic=traffic)
    deadline = time.monotonic() + wall_timeout
    with BlackfinPort(worker, operating=True, timeout=15, rom=rom,
                      sport=dict(core_hz=core_hz, input=input), host_transport='fifo') as port:
        profile = identify(payload)
        flash = hardware_flash('blue') if profile.build == 'synth' else blank_flash()
        machine = Machine(payload, flash=flash, profile=profile, dsp_backend=port)
        read, write = machine.read, machine.write

        def observed_read(address):
            value = read(address)
            if address == DSP_DATA:
                traffic['read'] += 1
            return value

        def observed_write(address, value):
            result = write(address, value)
            if address in (DSP_CTRL, DSP_DATA):
                traffic['control' if address == DSP_CTRL else 'write'] += 1
            return result

        machine.read, machine.write = observed_read, observed_write
        try:
            while machine.time_ns < seconds * 1000000000 and not machine.asserts and machine.powered:
                if time.monotonic() >= deadline:
                    raise BackendError('coupled ARM/DSP session deadline exceeded')
                machine.run_until(min(seconds, machine.time_ns / 1000000000 + .005))
            if not port.loaded:
                raise BackendError('ARM did not upload a DSP program')
            clock = port.backend.clock_status()
            expected = (int(machine.time_ns) - port._clock_origin_ns) * core_hz // 1000000000
            checks = dict(native_clock=clock['cycles'] == expected,
                          native_initialization=port.initialized,
                          bidirectional_traffic=traffic['control'] > 7 and traffic['write'] > 16 and traffic['read'] >= 16,
                          no_arm_assertions=not machine.asserts,
                          no_dsp_exception=port.backend.register(47) == 0,
                          powered=machine.powered,
                          main_screen=machine.booted)
            report.update(ok=all(checks.values()), full_boot=machine.booted,
                          checks=checks, build=machine.profile.build,
                          arm_time_ns=machine.time_ns, arm_pc=machine.reg(machine.A.UC_ARM_REG_PC),
                          clock=clock, dsp_pc=port.backend.register(53),
                          host_status=port.backend.host_status(), sport=port.backend.sport_status(),
                          initialization=port.boot_report, assertions=machine.asserts,
                          firmware_sha256=hashlib.sha256(payload).hexdigest())
        except (BackendError, ValueError) as error:
            report.update(error=str(error), arm_time_ns=machine.time_ns,
                          arm_pc=machine.reg(machine.A.UC_ARM_REG_PC))
        report['rom_model'] = rom.report()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--core-hz', type=int, required=True)
    parser.add_argument('--seconds', type=float, default=1)
    parser.add_argument('--wall-timeout', type=float, default=600)
    parser.add_argument('--input', choices=('silence', 'lcg'), default='silence')
    args = parser.parse_args()
    try:
        raw = args.vsb.read_bytes()
        if len(raw) != 0x200100:
            raise ValueError('expected a complete SYSTEM.VSB')
        report = cases(raw[0x100:], args.worker, core_hz=args.core_hz,
                       seconds=args.seconds, input=args.input, wall_timeout=args.wall_timeout)
    except (OSError, BackendError, ValueError) as error:
        report = dict(ok=False, error=str(error), hardware_contact=False)
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
