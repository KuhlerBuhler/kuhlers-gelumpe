# SPDX-License-Identifier: GPL-2.0-only
"""Native MFX/WRITE checks for project research, using only synthetic pattern data.

The existing MFX patch is applied in memory. No VSB output or device access.
    tools/emu/.venv/bin/python tools/emu/project_mfx_cases.py --base SYSTEM.VSB --report report.json
"""

import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/patch"), str(Path(__file__).parent)]
import mfx_switch as spec
import unicorn
from firmware import identify
from machine import blank_flash
from mfx_cases import record_table
from project_probe import pattern_file
from splash_cases import Dev

ENQUEUE = 0xC002D5D8
DISPATCH, COMMAND_END = 0xC002D684, 0xC002D81C
RUNNER, COMMAND_TABLE = 0xC034057C, 0xC03404C8
PATTERN_SLOTS, RAM_SLOTS = 0x240000, 0xC08B2940
PATTERN_MANAGER, GLOBALS = 0xC033E6A4, 0xC0691334
BLOCK = 0x4000
STABLE_FIELDS = (0, 4, 8, 12, 16, 20, 24, 32)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patched_mfx(payload, build):
    raw = bytearray(0x100) + bytearray(payload)
    patch = spec.build_patch(raw, build=build)
    for change in patch["changes"]:
        offset, data = change["file"], bytes.fromhex(change["bytes"])
        if digest(raw[offset:offset + len(data)]) != change["expect"]:
            raise ValueError("MFX patch does not match the supplied original image")
        raw[offset:offset + len(data)] = data
    return bytes(raw[0x100:])


def probe(payload, build=None):
    actual = identify(payload).build
    if build is not None and build != actual:
        raise ValueError("requested build differs from the image")
    if actual not in ("stock", "hacktribe"):
        raise ValueError("this MFX experiment supports the two Sampler builds")
    patched = patched_mfx(payload, actual)
    flash = blank_flash()
    bank = pattern_file("BASE")[0x10100:]
    flash[PATTERN_SLOTS:PATTERN_SLOTS + len(bank)] = bank
    dev = Dev(patched, flash, adapter=True)
    dev.run(2)
    m, uc, arm = dev.m, dev.m.uc, dev.m.A
    checks, commands, drivers, finished, io = [], [], [], [], []
    stage = "prepare"
    pages = collections.Counter()

    def check(name, ok, observed):
        checks.append(dict(name=name, ok=bool(ok), observed=observed))

    def word(address):
        return struct.unpack("<I", uc.mem_read(address, 4))[0]

    def context():
        sp = uc.reg_read(arm.UC_ARM_REG_SP)
        task = ((word(0xC06A289C) - 0xC06A24E4) >> 5) + 1
        size, lo = struct.unpack("<II", uc.mem_read(0xC00A37A8 + 4 * 32 + 16, 8))
        return dict(task=task, sp=hex(sp), command_stack=lo <= sp < lo + size,
                    mode=uc.reg_read(arm.UC_ARM_REG_CPSR) & 31)

    def dispatch(cpu, address, size, data):
        message = cpu.reg_read(arm.UC_ARM_REG_R1)
        ident = uc.mem_read(message + 4, 1)[0]
        commands.append(dict(stage=stage, command=ident, **context()))

    def complete(cpu, address, size, data):
        finished.append(word(word(RUNNER) + 12))

    def driver(cpu, address, size, data):
        drivers.append(dict(stage=stage, first_sector=cpu.reg_read(arm.UC_ARM_REG_R1),
                            sectors=cpu.reg_read(arm.UC_ARM_REG_R2), **context()))

    uc.hook_add(unicorn.UC_HOOK_CODE, dispatch, begin=DISPATCH, end=DISPATCH)
    uc.hook_add(unicorn.UC_HOOK_CODE, complete, begin=COMMAND_END, end=COMMAND_END)
    uc.hook_add(unicorn.UC_HOOK_CODE, driver, begin=0xC001E57C, end=0xC001E57C)
    original_erase, original_byte = m.flash.erase, m.flash.byte

    def erase(size):
        io.append(dict(stage=stage, operation="erase", start=m.flash.addr & ~(size - 1), length=size))
        original_erase(size)

    def byte(value):
        if m.flash.cmd == 0x02 and len(m.flash.buf) >= 3 and m.flash.wel:
            pages[(stage, m.flash.addr & ~255)] += 1
        return original_byte(value)

    m.flash.erase, m.flash.byte = erase, byte

    def native_command(ident, index):
        count = len(finished)
        dev.call(ENQUEUE, ident, index, 0)
        deadline = m.time_ns / 1e9 + 10
        while len(finished) == count and m.time_ns / 1e9 < deadline and not m.asserts:
            dev.run(0.02)
        if len(finished) == count:
            raise RuntimeError("native command did not finish")
        return uc.mem_read(word(COMMAND_TABLE + 4 * ident) + 0x18, 1)[0]

    def stable():
        return [word(spec.STATE + offset) for offset in STABLE_FIELDS]

    dev.press(5, wait=0.4)
    dev.call(0xC0048A64, word(GLOBALS) + 0x4004, 11, 1)
    dev.run(0.1)
    check("mfx2-active-and-dirty", word(spec.STATE) == 1 and word(spec.STATE + 24) == 1,
          dict(mode=word(spec.STATE), own_type=word(spec.STATE + 4), second_type=word(spec.STATE + 8), dirty=word(spec.STATE + 24)))
    if not checks[-1]["ok"]:
        raise RuntimeError("could not prepare native active/dirty MFX state")

    before_state = stable()
    before_record = bytes(uc.mem_read(spec.RECBUF, spec.RECBUF_END - spec.RECBUF))
    before_metadata = bytes(m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + 4096])
    target = 7
    for label, own_type in (("equal-slot", 0), ("different-slot", 3)):
        stage = label
        incoming = bytearray(bank[target * BLOCK:(target + 1) * BLOCK])
        incoming[61] = own_type
        uc.mem_write(RAM_SLOTS + target * BLOCK, bytes(incoming))
        status = native_command(0x0A, target)
        stored = bytes(m.flash.mem[PATTERN_SLOTS + target * BLOCK:PATTERN_SLOTS + (target + 1) * BLOCK])
        check(label + "-preserves-incoming-pattern", status == 0 and stored == incoming,
              dict(status=status, incoming_type=own_type, stored_type=stored[61], matches=stored == incoming))
        check(label + "-does-not-persist-mfx-table", bytes(m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + 4096]) == before_metadata,
              dict(metadata_unchanged=bytes(m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + 4096]) == before_metadata))
        check(label + "-keeps-mfx-state", stable() == before_state and bytes(uc.mem_read(spec.RECBUF, len(before_record))) == before_record,
              dict(fields=stable(), unchanged=stable() == before_state))

    stage = "model-mfx-preimage"
    dev.call(0xC0048A64, word(GLOBALS) + 0x4004, 12, 1)
    changed = stable() != before_state
    dev.call(0xC0048A64, word(GLOBALS) + 0x4004, before_state[2], 1)
    for offset, value in zip(STABLE_FIELDS, before_state):
        uc.mem_write(spec.STATE + offset, struct.pack("<I", value))
    uc.mem_write(spec.RECBUF, before_record)
    check("model-mfx-preimage-restores-fields-and-table", changed and stable() == before_state
          and bytes(uc.mem_read(spec.RECBUF, len(before_record))) == before_record,
          dict(mutated=changed, fields_match=stable() == before_state, native_project_rollback=False))

    stage = "physical-write"
    own, second = word(spec.STATE + 4), word(spec.STATE + 8)
    dev.press("write", wait=0.6)
    dev.press("write", wait=3)
    record = bytes(m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + spec.RECORD_SIZE])
    table = record_table(record)
    stored = bytes(m.flash.mem[PATTERN_SLOTS:PATTERN_SLOTS + BLOCK])
    live_type = uc.mem_read(word(PATTERN_MANAGER) + 4 + 61, 1)[0]
    check("physical-write-uses-native-staging-mfx-semantics", stored[61] == own and live_type == second
          and any(item["stage"] == stage and item["command"] == 8 for item in commands),
          dict(own_type=own, second_type=second, stored_type=stored[61], live_type=live_type,
               commands=[item["command"] for item in commands if item["stage"] == stage]))
    check("physical-write-can-persist-dirty-mfx-table", table is not None and table[0] == second + 1 and word(spec.STATE + 24) == 0,
          dict(valid_record=table is not None, selected_entry=table[0] if table else None, dirty=word(spec.STATE + 24)))
    check("native-commandtask-context", bool(commands) and bool(drivers)
          and all(item["task"] == 5 and item["command_stack"] and item["mode"] == 19 for item in commands + drivers),
          dict(commands=commands, flash_drivers=drivers))
    check("no-firmware-assert", not m.asserts, m.asserts)
    for (phase, address), count in sorted(pages.items()):
        io.append(dict(stage=phase, operation="program", start=address, length=count))
    for phase in ("equal-slot", "different-slot"):
        erases = [item for item in io if item["stage"] == phase and item["operation"] == "erase"]
        programs = [item for item in io if item["stage"] == phase and item["operation"] == "program"]
        check(phase + "-native-spi-writes-observed", len(erases) == 4 and len(programs) == 64
              and all(item["length"] == 256 for item in programs),
              dict(erases=len(erases), program_pages=len(programs)))
    check("raw-slot-stores-touch-only-pattern-slot", all(PATTERN_SLOTS + target * BLOCK <= item["start"]
          and item["start"] + item["length"] <= PATTERN_SLOTS + (target + 1) * BLOCK
          for item in io if item["stage"] in ("equal-slot", "different-slot")),
          dict(erase_count=sum(item["operation"] == "erase" for item in io if item["stage"] in ("equal-slot", "different-slot")),
               program_pages=sum(item["operation"] == "program" for item in io if item["stage"] in ("equal-slot", "different-slot"))))
    return dict(build=actual, original_payload_sha256=digest(payload), mfx_payload_sha256=digest(patched),
                checks=checks, flash_operations=io,
                assumptions=["Only the existing MFX patch is applied in emulator RAM; not the complete BLECH set.",
                             "Incoming slot bytes are synthetic fixtures placed in RAM, not a project import.",
                             "MFX preimage restoration is host-model memory restoration, not implemented native rollback.",
                             "Identical raw stores still invoke native writes; selective comparison is not implemented here.",
                             "Emulated SPI/DSP and synthetic factory/sample-pattern banks; no physical device or sound."])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.base.read_bytes()[0x100:])
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    failed = [item["name"] for item in result["checks"] if not item["ok"]]
    print(json.dumps(dict(build=result["build"], checks=len(result["checks"]), failed=failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
