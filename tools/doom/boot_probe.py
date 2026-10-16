#!/usr/bin/env python3
"""Prüft nur im Firmwareemulator einen Treiberstart ohne Sampleranwendung."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/emu")]
from tools.patch.arm import assemble
from tools.emu.bootmap import START_MODES, KILL_SWITCH
from tools.emu.script_cases import card_image
from tools.emu.machine import Machine, load_flash
from tools.emu.sdcard import MemoryMedium, SDCard
import unicorn

BASE, SITE = 0xC1000000, 0xC002ADB0
FIL, BUFFER, MESSAGE, FATFS, RESULT = [BASE + n for n in [0x1000, 0x1400, 0x1800, 0x2000, 0x3000]]
COMBINATION = 0x408
SUPPORTED = {
    "b0890899cbe5951d0709724c46d38350a35a6134a4a01d3a5bad63e51ac22ae7",
    "584f5b7a057adf23c04f07da09c8669c5410a68c494bdd19a66245fc8cfab9cb",
}
TASKS = {0xC002AB7C: 1, 0xC002AA34: 2, 0xC002A3C0: 3, 0xC002B144: 4,
         0xC002A598: 5, 0xC00245F0: 6, 0xC002C980: 7, 0xC001DA9C: 8,
         0xC002B220: 9, 0xC002AACC: 10}
SAMPLER = {0xC004BE8C: "globals", 0xC004BF8C: "patterns", 0xC00364F0: "samples"}


def program():
    return assemble(f"""
probe:
    push {{r4, lr}}
    bl 0xC002A35C
    push {{r0-r3}}
    .word 0xE10F4000 ; mrs r4, cpsr
    push {{r4, r5}}
    ldr r0, =0xC033E6F8
    ldr r0, [r0]
    ldr r1, [r0, #0x18]
    ldr r2, ={COMBINATION}
    cmp r1, r2
    bne normal
    ldr r1, [r0, #0x1c]
    cmp r1, #0
    bne normal
    ldrb r1, [r0, #0x20]
    cmp r1, #0
    bne normal
    ldrb r1, [r0, #0x22]
    cmp r1, #0
    bne normal
    ldr r4, ={RESULT}
    mov r0, #1
    str r0, [r4]
    mov r0, #1
    bl 0xC0025754
    mov r0, #8
    bl 0xC00005A0
    mov r0, #1
    bl 0xC0025A14
    bl 0xC003FD20
    ldr r0, ={FATFS}
    ldr r1, =drive
    mov r2, #1
    bl 0xC009DAD8
    str r0, [r4, #24]
    cmp r0, #0
    bne failed
    mov r0, #2
    str r0, [r4]
    ldr r0, ={FIL}
    ldr r1, =path
    mov r2, #1
    bl 0xC009DB60
    str r0, [r4, #4]
    cmp r0, #0
    bne failed
    mov r0, #3
    str r0, [r4]
    ldr r0, ={FIL}
    ldr r1, ={BUFFER}
    mov r2, #1024
    add r3, r4, #8
    bl 0xC009DD74
    str r0, [r4, #12]
    ldr r0, ={FIL}
    bl 0xC009E3DC
    str r0, [r4, #16]
    ldr r0, [r4, #12]
    cmp r0, #0
    bne failed
    ldr r0, [r4, #16]
    cmp r0, #0
    bne failed
    ldr r0, [r4, #8]
    cmp r0, #1024
    bne failed
    mov r0, #4
    str r0, [r4]
    ldr r0, =0xC031B310
    ldr r1, ={BUFFER}
    mov r2, #1024
copy:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne copy
    ldr r0, =0xC031BB2C
    mov r1, #2
    mov r2, #0
    bl 0xC0015DD0
    ldr r0, =0xC031BB2C
    mov r1, #3
    mov r2, #0
    bl 0xC0015DD0
    mov r0, #5
    str r0, [r4]
    b poll
failed:
    mov r0, #6
    str r0, [r4]
poll:
    ldr r0, =0xC033E57C
    ldr r1, ={MESSAGE}
    bl 0xC0024B6C
    cmp r0, #0
    beq poll
    ldr r0, [r4, #20]
    add r0, r0, #1
    str r0, [r4, #20]
    b poll
normal:
    pop {{r4, r5}}
    .word 0xE12FF004 ; msr cpsr_cxsf, r4
    pop {{r0-r3}}
    pop {{r4, pc}}
.pool
drive:
    .asciz "SD:"
path:
    .asciz "SD:/PROBE.IN"
""", origin=BASE).bytes


def image_with_probe(vsb):
    if hashlib.sha256(vsb).hexdigest() not in SUPPORTED:
        raise ValueError("Nur die beiden dokumentierten lokalen Firmwarestände sind geprüft")
    payload = bytearray(vsb[0x100:])
    at = SITE - 0xC0000000
    original = assemble("bl 0xC002A35C", origin=SITE).bytes
    if payload[at:at + 4] != original:
        raise ValueError("Unerwartete Übergabestelle")
    payload[at:at + 4] = assemble(f"bl {BASE}", origin=SITE).bytes
    return bytes(payload)


def run(payload, flash, held, frame, selected=False, card=True, missing=False, panel_version=None):
    machine = Machine(payload, flash)
    machine.held = held
    if panel_version is not None:
        machine.panel_version = panel_version
    machine.uc.mem_write(BASE, program())
    if card:
        data = card_image({} if missing else {"/PROBE.IN": frame})
        machine.insert_card(SDCard(MemoryMedium(data, read_only=True)))
    tasks, sampler = set(), set()
    for address, task in TASKS.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: tasks.add(d), task, begin=address, end=address)
    for address, name in SAMPLER.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: sampler.add(d), name, begin=address, end=address)
    machine.run_until(0.3 if selected else 0.8)
    if selected:
        machine.send([0, 3, 1, 0, 0])
        machine.run_until(0.4)
    read = lambda at, n: bytes(machine.uc.mem_read(at, n))
    status = list(struct.unpack("<7I", read(RESULT, 28)))
    manager = struct.unpack("<I", read(0xC03404C0, 4))[0]
    lcd = bytes(b for row in machine.fb for b in row)
    return dict(status=status, tasks=sorted(tasks), sampler=sorted(sampler), asserts=machine.asserts,
                screen=struct.unpack("<I", read(manager + 0x2C, 4))[0] if manager else None,
                lcd_sha256=hashlib.sha256(lcd).hexdigest(), lcd_pixels=sum(b.bit_count() for b in lcd),
                read_sha256=hashlib.sha256(read(BUFFER, 1024)).hexdigest(),
                input=list(read(MESSAGE, 5)),
                leds=sorted((k, v) for k, v in machine.leds.items() if k != 0x14))


def check(vsb, flash, frame, matrix=True):
    patched = image_with_probe(vsb)
    active = run(patched, flash, COMBINATION, frame, selected=True)
    checks = []
    add = lambda name, ok: checks.append(dict(id=name, ok=bool(ok)))
    expected = hashlib.sha256(frame).hexdigest()
    add("sd-read", active["status"][:5] == [5, 0, 1024, 0, 0] and active["status"][6] == 0 and active["read_sha256"] == expected)
    add("lcd-wire", active["lcd_sha256"] == expected)
    add("panel-input", active["status"][5] == 1 and active["input"] == [0, 3, 1, 0, 0])
    add("no-sampler", active["tasks"] == [1, 8] and active["sampler"] == [] and active["screen"] is None)
    add("no-assert", not active["asserts"])
    cases = {}
    for name, kw in [("no-card", {"card": False}), ("no-file", {"missing": True})]:
        result = run(patched, flash, COMBINATION, frame, selected=True, **kw)
        cases[name] = result
        add(name, result["status"][0] == 6 and result["tasks"] == [1, 8] and not result["asserts"])
    masks = [0, KILL_SWITCH, COMBINATION | KILL_SWITCH]
    if matrix:
        masks += list(START_MODES)
    for held in masks:
        reference = run(vsb[0x100:], flash, held, frame)
        candidate = run(patched, flash, held, frame)
        fields = ["tasks", "sampler", "asserts", "screen", "lcd_sha256", "leds"]
        add(f"normal-{held:08x}", candidate["status"][0] == 0 and all(reference[f] == candidate[f] for f in fields))
        cases[f"normal-{held:08x}"] = dict(reference=reference, candidate=candidate)
    for name, options in [("update-offer", {"flash": bytes([255]) * 0x1000000}),
                          ("panel-update", {"flash": flash, "panel_version": 0x95})]:
        for held in [0, COMBINATION]:
            reference = run(vsb[0x100:], held=held, frame=frame, **options)
            candidate = run(patched, held=held, frame=frame, **options)
            fields = ["tasks", "sampler", "asserts", "screen", "lcd_sha256", "leds"]
            key = f"{name}-{held:08x}"
            add(key, candidate["status"][0] == 0 and all(reference[f] == candidate[f] for f in fields))
            cases[key] = dict(reference=reference, candidate=candidate)
    return dict(ok=all(c["ok"] for c in checks), checks=checks, active=active, cases=cases,
                base_sha256=hashlib.sha256(vsb).hexdigest(), probe_bytes=len(program()),
                frame_sha256=expected, changed_site=hex(SITE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--flash", type=Path, nargs="+", required=True)
    parser.add_argument("--frame", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    frame = args.frame.read_bytes() if args.frame else bytes(0x55 if (i // 8) % 2 else 0xAA for i in range(1024))
    if len(frame) != 1024:
        parser.error("Das Displaybild muss genau 1024 Byte haben")
    result = check(args.base.read_bytes(), load_flash(args.flash), frame, not args.quick)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
