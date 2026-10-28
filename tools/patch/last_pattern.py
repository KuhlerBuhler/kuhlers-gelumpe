"""Builds the last-pattern patch (idea 76, docs/messungen/2026-10-28-letztes-pattern.md) for firmware 2.02, Hacktribe and Korg's own build.

At power-on the device opens the pattern that was selected last, instead of 001. The firmware keeps the number itself:
every pattern selection (0xC0079DB4, the function that clamps the number to 0..249 and loads the pattern) writes it plus
one into Global byte 248, a byte no page of the Global menu reaches and that is 0 on every device read so far. The
firmware saves the Globals to the flash when the device switches off and on WRITE in the Global menu (0xC004C1B4), the
byte goes with them; nothing of ours writes the flash or the card.

At power-on the start function loads pattern 0 into the edit buffer (mov r1, #0 at 0xC002AF40) and a command selects
pattern 0 a moment later (the first call of 0xC0079DB4, from 0xC0036FA0). Both take the kept number: the first through
boot(), the second because boot() leaves a mark in Global byte 249 that the first selection reads and clears. Without a
kept number (byte 248 is 0, or above 250 when the byte was ever set otherwise) both stay pattern 0.

    python3 tools/patch/last_pattern.py --vsb SYSTEM.VSB [--out data/patches/last-pattern.json]

With EXIT held at power-on boot() keeps pattern 0 and no selection notes its number, as in every patch (docs/patcher.md,
"Notschalter"): the kept number waits for the next start without EXIT. Every address is a RAM address of the measured build; the file offset in the
VSB is address - 0xC0000000 + 0x100.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC014FE00            # FF in all three builds, the end of the run 0xC0148880..0xC0150000 (docs/patcher.md), not written at run time
CODE_END = 0xC014FF00

BOOT_SITE = 0xC002AF40          # mov r1, #0: the pattern the start function loads into the edit buffer
BOOT_WAS = 0xE3A01000
SELECT_SITE = 0xC0079DC8        # mov r4, r0 in the pattern selection, behind the clamp of the number into r5
SELECT_WAS = 0xE1A04000
GLOBALS = 0xC0691324            # pointer to the Global settings (tools/emu/power_off_cases.py)
SLOT = 248                      # Global byte: the last selected pattern plus one, 0 for none
PENDING = 249                   # Global byte: 1 from boot() until the first selection took the kept number
PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 held keys
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)
PATTERNS = 250


def source():
    return f"""
.equ GLOBALS, {GLOBALS:#x}
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ SLOT, {SLOT}
.equ PENDING, {PENDING}
.equ PATTERNS, {PATTERNS}
.org {CODE_AT:#x}

; replaces mov r1, #0 in the start function: r1 = the kept pattern, or 0. Clobbers r0 and r12.
lp_boot:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq lb_none
    ldr r1, [r12, #0x18]
    tst r1, #KILL
    bne lb_none
    ldr r12, =GLOBALS
    ldr r12, [r12]
    cmp r12, #0
    beq lb_none
    ldrb r1, [r12, #SLOT]
    cmp r1, #0
    beq lb_none
    cmp r1, #PATTERNS
    bhi lb_none
    sub r1, r1, #1
    mov r0, #1
    strb r0, [r12, #PENDING]
    bx lr
lb_none:
    mov r1, #0
    bx lr

; replaces mov r4, r0 in the selection, r5 = the clamped number: the first selection after boot() takes the kept one,
; every selection notes its number; with EXIT held at power-on none does. Clobbers r12.
lp_select:
    mov r4, r0
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq ls_out
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    bne ls_out
    ldr r12, =GLOBALS
    ldr r12, [r12]
    cmp r12, #0
    bxeq lr
    ldrb r0, [r12, #PENDING]
    cmp r0, #0
    beq ls_note
    mov r0, #0
    strb r0, [r12, #PENDING]
    ldrb r5, [r12, #SLOT]
    sub r5, r5, #1
ls_note:
    add r0, r5, #1
    strb r0, [r12, #SLOT]
ls_out:
    mov r0, r4
    bx lr
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


def build_patch(vsb):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    if was(CODE_AT, len(code)) != b"\xff" * len(code):
        raise SystemExit(f"{CODE_AT:#x}..{CODE_AT + len(code):#x} is not free in this VSB")
    for site, word in ((BOOT_SITE, BOOT_WAS), (SELECT_SITE, SELECT_WAS)):
        if struct.unpack("<I", was(site, 4))[0] != word:
            raise SystemExit(f"{site:#x} does not hold the instruction the patch replaces in this VSB")
    return {
        "format": "gelumpe-patch", "version": 1, "id": "last-pattern",
        "name": "Letztes Pattern beim Einschalten",
        "builds": ["hacktribe", "stock"],
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": sha(was(CODE_AT, len(code))),
             "note": "last pattern: the start function and the first selection take the kept number, every selection notes it in Global byte 248"},
            {"file": file_offset(BOOT_SITE), "bytes": struct.pack("<I", bl_word(BOOT_SITE, symbols["lp_boot"])).hex(),
             "expect": sha(was(BOOT_SITE, 4)), "note": "the pattern the start function loads comes from lp_boot instead of 0"},
            {"file": file_offset(SELECT_SITE), "bytes": struct.pack("<I", bl_word(SELECT_SITE, symbols["lp_select"])).hex(),
             "expect": sha(was(SELECT_SITE, 4)), "note": "the pattern selection notes its number (and takes the kept one once after power-on)"},
        ],
        "hooks": [
            {"site": f"0x{BOOT_SITE:08X}", "kind": "instruction", "chain": "start", "position": "replace", "swallow": False,
             "note": "r1 = the kept pattern instead of 0; with EXIT held at power-on it stays 0"},
            {"site": f"0x{SELECT_SITE:08X}", "kind": "instruction", "chain": "pattern-select", "position": "replace", "swallow": False,
             "note": "does the replaced mov r4, r0, notes the number, and once after power-on swaps in the kept one"},
        ],
        "startPhase": [
            {"file": file_offset(BOOT_SITE), "length": 4,
             "why": "the start function loads its first pattern here and now asks lp_boot for the number"},
            {"file": file_offset(SELECT_SITE), "length": 4,
             "why": "the start selects its first pattern through the selection, which now notes the number and takes the kept one"},
            {"file": file_offset(CODE_AT), "length": len(code),
             "why": "lp_boot and lp_select run with those calls; they read the held keys and Global bytes 248 and 249"},
        ],
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
