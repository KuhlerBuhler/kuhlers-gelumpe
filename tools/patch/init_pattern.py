"""Builds the init-pattern patch (Set Init Pattern, docs/messungen/2026-10-28-init-pattern.md) for firmware 2.02, Hacktribe and Korg's own build.

DATA UTILITY 5 INITIALIZE PATTERN fills the pattern from the firmware's template (0xC00CFF58, data/map/firmware.mjs
table.initPattern) through 0xC0036BEC, called at 0xC0036A34. With this patch the call goes through our code: it runs the
firmware's function as before, and when Global byte 247 names a pattern (its number plus one, 1 to 250, set on the page
INIT PATTERN of the BLECH menu's FEATURES), it copies that stored pattern (its block in the pattern bank, 0xC08B2940 plus
number times 0x4000) over the result. Three bytes the firmware fills from its settings (+0x0C to +0x0E) stay the firmware's.
A block without the PTST mark is left alone: the result stays the firmware's template.

The other three callers of 0xC0036BEC (the start, filling patterns the flash has no valid copy of, and the pattern load's
fallback) keep the firmware's template. Nothing is written but the buffer the firmware passes. With EXIT held at power-on the
call is the firmware's own (docs/patcher.md, "Notschalter").

    python3 tools/patch/init_pattern.py --vsb SYSTEM.VSB [--out data/patches/init-pattern.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import synthaddr  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC014FD00            # FF in the run 0xC0148880..0xC0150000, just before the last-pattern code (0xC014FE00)
CODE_END = 0xC014FE00

INIT_CALL = 0xC0036A34          # bl 0xC0036BEC in DATA UTILITY's INITIALIZE PATTERN, r1 = the buffer it fills
INIT_FUNC = 0xC0036BEC
MEMCPY = 0xC000985C             # (dst, src, n), as the init function calls it
GLOBALS = 0xC0691324            # pointer to the Global settings (tools/emu/power_off_cases.py)
SLOT = 247                      # Global byte: the template pattern plus one, 0 for the firmware's template
BANK = 0xC08B2940               # pattern 0 in the pattern bank (docs/messungen/2026-10-08-boot-pattern-speicher.md)
BLOCK = 0x4000
MARK = 0x54535450               # "PTST", the first word of a pattern
PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 held keys
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)
PATTERNS = 250


FIRMWARE_PLACES = ["INIT_CALL", "INIT_FUNC", "MEMCPY", "GLOBALS", "BANK", "PANEL"]


def use_build(build):
    """For the synth (the blue Electribe 2) the firmware's places have their own addresses (data/synth-map/); the code stays where it is."""
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def source():
    return f"""
.equ INIT_FUNC, {INIT_FUNC:#x}
.equ MEMCPY, {MEMCPY:#x}
.equ GLOBALS, {GLOBALS:#x}
.equ SLOT, {SLOT}
.equ BANK, {BANK:#x}
.equ MARK, {MARK:#x}
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ PATTERNS, {PATTERNS}
.org {CODE_AT:#x}

; replaces bl INIT_FUNC in INITIALIZE PATTERN: r0, r1 as the firmware passes them, returns what the firmware returns
ip_init:
    push {{r4, r5, r6, r7, r8, lr}}
    mov r5, r1
    bl INIT_FUNC
    mov r6, r0
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq ip_out
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne ip_out
    ldr r12, =GLOBALS
    ldr r12, [r12]
    cmp r12, #0
    beq ip_out
    ldrb r0, [r12, #SLOT]
    cmp r0, #0
    beq ip_out
    cmp r0, #PATTERNS
    bhi ip_out
    sub r0, r0, #1
    ldr r4, =BANK
    add r4, r4, r0, lsl #14
    ldr r0, [r4]
    ldr r1, =MARK
    cmp r0, r1
    bne ip_out
    ldrb r7, [r5, #0x0C]
    ldrb r8, [r5, #0x0D]
    ldrb r12, [r5, #0x0E]
    push {{r12}}
    mov r0, r5
    mov r1, r4
    mov r2, #0x4000
    bl MEMCPY
    pop {{r12}}
    strb r7, [r5, #0x0C]
    strb r8, [r5, #0x0D]
    strb r12, [r5, #0x0E]
ip_out:
    mov r0, r6
    pop {{r4, r5, r6, r7, r8, pc}}
.pool
"""


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bl_word(at, target):
    return 0xEB000000 | (((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb, build="hacktribe"):
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    if was(CODE_AT, len(code)) != b"\xff" * len(code):
        raise SystemExit(f"{CODE_AT:#x}..{CODE_AT + len(code):#x} is not free in this VSB")
    if struct.unpack("<I", was(INIT_CALL, 4))[0] != bl_word(INIT_CALL, INIT_FUNC):
        raise SystemExit("INITIALIZE PATTERN does not call the init function where the patch expects it in this VSB")
    return {
        "format": "gelumpe-patch", "version": 1, "id": "init-pattern",
        "name": "Eigenes Init-Pattern",
        "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": sha(was(CODE_AT, len(code))),
             "note": "init pattern: INITIALIZE PATTERN copies the pattern Global byte 247 names over the firmware's template"},
            {"file": file_offset(INIT_CALL), "bytes": struct.pack("<I", bl_word(INIT_CALL, symbols["ip_init"])).hex(),
             "expect": sha(was(INIT_CALL, 4)), "note": "INITIALIZE PATTERN calls ip_init, which calls the firmware's init function first"},
        ],
        "hooks": [
            {"site": f"0x{INIT_CALL:08X}", "kind": "call", "chain": "pattern-init", "position": "after", "swallow": False,
             "note": "the firmware's init runs first; then the chosen pattern is copied over it, three settings bytes kept"},
        ],
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    use_build(a.build)
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw, a.build), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
