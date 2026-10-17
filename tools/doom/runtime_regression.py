#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Vergleicht den echten Doom Firmwarestand mit der Referenz und prüft SD Fehler."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/emu")]
from tools.doom.boot_probe import TASKS, SAMPLER
from tools.doom.artifacts import external_output
from tools.doom.build_bootstrap import validate_delta
from tools.doom.run_runtime import run, state, ObservedCard
from tools.emu.bootmap import START_MODES, KILL_SWITCH
from tools.emu.machine import Machine, load_flash
from tools.emu.script_cases import card_image
from tools.emu.sdcard import MemoryMedium, SDCard
import unicorn


class CountedMedium(MemoryMedium):
    def __init__(self, data):
        super().__init__(data, read_only=True)
        self.write_calls = 0

    def write(self, lba, block):
        self.write_calls += 1
        super().write(lba, block)


def snapshot(image, flash, held, card, panel_version=None, times=(0.1, 0.8)):
    machine = Machine(image[0x100:], flash)
    machine.held = held
    if panel_version is not None:
        machine.panel_version = panel_version
    medium = CountedMedium(card)
    observed_card = ObservedCard(medium)
    machine.insert_card(observed_card)
    before = hashlib.sha256(medium.data).hexdigest()
    tasks, sampler = set(), set()
    for address, task in TASKS.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: tasks.add(d), task, begin=address, end=address)
    for address, name in SAMPLER.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: sampler.add(d), name, begin=address, end=address)
    error = None
    clock = []
    try:
        for seconds in times:
            machine.run_until(seconds)
            clock.append(dict(nanoseconds=machine.time_ns, ticks=struct.unpack("<I", machine.uc.mem_read(0xC06A2930, 4))[0]))
    except Exception as exc:
        error = repr(exc)
    manager = struct.unpack("<I", machine.uc.mem_read(0xC03404C0, 4))[0]
    lcd = bytes(b for row in machine.fb for b in row)
    return dict(tasks=sorted(tasks), sampler=sorted(sampler), asserts=machine.asserts, error=error,
                manager=manager,
                screen=struct.unpack("<I", machine.uc.mem_read(manager + 0x2C, 4))[0] if manager else None,
                lcd_sha256=hashlib.sha256(lcd).hexdigest(),
                leds=sorted(machine.leds.items()), doom=state(machine), clock=clock,
                sd_write_calls=medium.write_calls, sd_write_commands=observed_card.write_commands, sd_unchanged=hashlib.sha256(medium.data).hexdigest() == before)



def power_case(image, flash, program, wad, error_idle):
    machine = Machine(image[0x100:], flash)
    machine.held = 0x408
    medium = None
    card = None
    if not error_idle:
        medium = CountedMedium(card_image({"/KORG/blechtribe/Doom/doom.bin": program,
                                          "/KORG/blechtribe/Doom/doom.wad": wad}))
        card = ObservedCard(medium)
        machine.insert_card(card)
    card_digest = hashlib.sha256(medium.data).hexdigest() if medium else None
    tasks, sampler, entries, calls, full_power = set(), set(), [], [], []
    for address, task in TASKS.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: tasks.add(d), task, begin=address, end=address)
    for address, name in SAMPLER.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: sampler.add(d), name, begin=address, end=address)
    machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: entries.append(machine.time_ns), begin=0xC1000000, end=0xC1000000)
    def power(uc, address, size, data):
        calls.append(dict(nanoseconds=machine.time_ns, r0=machine.reg(machine.A.UC_ARM_REG_R0), r1=machine.reg(machine.A.UC_ARM_REG_R1)))
    machine.uc.hook_add(unicorn.UC_HOOK_CODE, power, begin=0xC001734C, end=0xC001734C)
    machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: full_power.append(machine.time_ns), begin=0xC0038A54, end=0xC0038A54)
    error = None
    before, after_release = None, False
    try:
        while machine.time_ns < 5e9 and not machine.asserts and machine.powered:
            machine.run_until(machine.time_ns / 1e9 + 0.05)
            current = state(machine)
            if current["magic"] == 0x4D4F4F44 and current["stage"] == (0x80000000 if error_idle else 4):
                before = current
                break
        if before:
            machine.send([6, 0, 0, 0, 0])
            machine.run_until(machine.time_ns / 1e9 + 0.02)
            after_release = machine.powered
            machine.send([6, 1, 0, 0, 0])
            machine.run_until(machine.time_ns / 1e9 + 2.0)
    except Exception as exc:
        error = repr(exc)
    after = state(machine)
    result = dict(before=before, after=after, powered_after_release=after_release, powered=machine.powered,
                  calls=calls, full_power_calls=full_power, engine_entries=entries,
                  tasks=sorted(tasks), sampler=sorted(sampler), asserts=machine.asserts, error=error,
                  sd_write_calls=medium.write_calls if medium else 0,
                  sd_write_commands=card.write_commands if card else 0,
                  sd_unchanged=hashlib.sha256(medium.data).hexdigest() == card_digest if medium else True,
                  seconds=machine.time_ns / 1e9)
    result["ok"] = before is not None and after_release and not machine.powered and not error and not machine.asserts and tasks == {1, 8} and sampler <= {"globals", "patterns"} and not full_power and bool(entries) == (not error_idle) and calls and calls[-1]["r0"] == 0x01E26000 and calls[-1]["r1"] == 1 and result["sd_write_calls"] == result["sd_write_commands"] == 0 and result["sd_unchanged"] and after["error"] == before["error"]
    result["ok"] = bool(result["ok"])
    return result


def compare(base, image, flash, program, wad, output):
    validate_delta(base, image)
    output = external_output(output)
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    card = card_image({"/KORG/blechtribe/Doom/doom.bin": program,
                       "/KORG/blechtribe/Doom/doom.wad": wad})
    checks, cases = [], {}
    def add(name, ok):
        checks.append(dict(id=name, ok=bool(ok)))
    fields = ["tasks", "sampler", "asserts", "manager", "screen", "lcd_sha256", "leds"]
    configurations = [(f"normal-{mask:08x}", mask, flash, None)
                      for mask in [0, KILL_SWITCH, 0x408 | KILL_SWITCH, *START_MODES]]
    for name, contents, version in [("update-offer", bytes([255]) * 0x1000000, None),
                                    ("panel-update", flash, 0x95)]:
        configurations += [(f"{name}-{held:08x}", held, contents, version) for held in [0, 0x408]]
    for name, held, contents, version in configurations:
        reference = snapshot(base, contents, held, card, version)
        candidate = snapshot(image, contents, held, card, version)
        different = [field for field in fields if reference[field] != candidate[field]]
        entered = candidate["doom"]["magic"] == 0x4D4F4F44
        add(name, not different and not entered and not reference["error"] and not candidate["error"] and not candidate["asserts"])
        cases[name] = dict(reference=reference, candidate=candidate, different=different)
        (output / (name + ".json")).write_text(json.dumps(cases[name], indent=2) + "\n")
        print(json.dumps(dict(case=name, ok=checks[-1]["ok"])), file=sys.stderr, flush=True)
    native_clock = snapshot(image, flash, 0x408, card, times=(1.5, 2.5))
    (output / "native-clock.json").write_text(json.dumps(native_clock, indent=2) + "\n")
    clock_case = native_clock["clock"]
    if len(clock_case) == 2:
        elapsed = clock_case[1]["nanoseconds"] - clock_case[0]["nanoseconds"]
        tick_delta = (clock_case[1]["ticks"] - clock_case[0]["ticks"]) & 0xFFFFFFFF
        add("native-kernel-clock-1000hz", native_clock["doom"]["magic"] == 0x4D4F4F44 and native_clock["doom"]["stage"] in (4, 5) and abs(tick_delta * 1000000 - elapsed) <= 1000000)
    else:
        add("native-kernel-clock-1000hz", False)
    add("matrix-sd-readonly", all(case["candidate"]["sd_write_calls"] == 0 and case["candidate"]["sd_write_commands"] == 0 and case["candidate"]["sd_unchanged"] for case in cases.values()))
    for fault, group in [("no-card", "mount"), ("missing-program", "open"),
                         ("short-program", "size"), ("corrupt-program", "digest"),
                         ("missing-wad", "engine"), ("bad-wad", "engine")]:
        result = run(image, flash, program, wad, seconds=10.0, fault=fault, output=output / fault)
        status = result["state"]
        error = status["error"]
        expected = ((0x100 <= error < 0x200) if group == "mount" else
                    (0x200 <= error < 0x300) if group == "open" else
                    error == 0x300 if group == "size" else
                    error == 0x500 if group == "digest" else error == 0xFFFFFFFF)
        add(fault, status["magic"] == 0x4D4F4F44 and status["stage"] == 0x80000000 and expected
            and result["tasks"] == [1, 8] and set(result["sampler"]) <= {"globals", "patterns"} and not result["asserts"]
            and not result["error"] and 0 < result["framebuffer_nonzero"] < 8192
            and bool(result["engine_entry"]) == (group == "engine"))
        add(fault + "-sd-readonly", result.get("sd_write_calls") == 0 and result.get("sd_write_commands") == 0 and result.get("sd_unchanged") is True)
        cases[fault] = result
        print(json.dumps(dict(case=fault, ok=checks[-2]["ok"], error=hex(error))), file=sys.stderr, flush=True)
    for name, idle in [("power-error-idle", True), ("power-native-init", False)]:
        result = power_case(image, flash, program, wad, idle)
        cases[name] = result
        (output / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        add(name, result["ok"])
        print(json.dumps(dict(case=name, ok=result["ok"])), file=sys.stderr, flush=True)
    report = dict(ok=all(check["ok"] for check in checks), checks=checks, cases=cases, native_clock=native_clock,
                  base_sha256=hashlib.sha256(base).hexdigest(), image_sha256=hashlib.sha256(image).hexdigest(),
                  program_sha256=hashlib.sha256(program).hexdigest(), wad_sha256=hashlib.sha256(wad).hexdigest(),
                  wall_seconds=time.monotonic() - started,
                  scope="Echte lokale Firmware, SD Bus, Panel und SPI im Emulator; kein Gerätetest")
    path = output / "regression.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return dict(ok=report["ok"], count=len(checks), passed=sum(check["ok"] for check in checks),
                failed=[check["id"] for check in checks if not check["ok"]], report=str(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["base", "image", "program", "wad", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--flash", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    summary = compare(args.base.read_bytes(), args.image.read_bytes(), load_flash(args.flash),
                      args.program.read_bytes(), args.wad.read_bytes(), args.output)
    print(json.dumps(summary))
    sys.exit(0 if summary["ok"] else 1)
