"""Builds the idle insert effect patch (docs/messungen/2026-10-18-ifx-ruht.md) for firmware 2.02 with Hacktribe and Korg's own 2.02.

The DSP runs the insert effect of every part all the time, also while the part is muted or its IFX is off (measured: IFX off
does not take the effect out, only its output). Korg's FAQ names too many heavy effects as one reason why notes drop out. This
patch gives a part that has been silent for its effect for HOLD_TICKS (5 s) the lightest effect, Punch (insert preset 1,
index 0, one stage, unit 4), and the part's own effect back as soon as it can be heard again:

    silent  the part is muted, or its IFX is off; a part whose effect is Punch already, and the second part of a stereo pair
            (the first one owns the effect), are left alone
    after   HOLD_TICKS ticks of the LED manager's 40 ms timer in a row; the switch to Punch happens on the main screen only
    back    the moment the part is unmuted or its IFX goes on, through the firmware's own part reload (0xC0097E70)

The firmware remembers the last index it gave each part (its table behind 0xC0097D18) and reloads only when the part's index
differs from it. The patch writes Punch's index there when it switches, so every later reload of the firmware (pattern change,
an effect chosen) loads the part's real effect again; a reload of the firmware after the switch shows as a remembered index that
is not Punch's any more, and the patch then forgets its switch.

The patch is on unless EXIT was held at power-on. No setting, nothing written to the card.

    python3 tools/patch/ifx_idle.py --vsb SYSTEM.VSB [--out data/patches/ifx-idle.json]

One hook: the LED manager registers its 40 ms tick (0xC0087740) through the literal at 0xC0089D90; the patch puts its own tick
there, which calls the LED manager's tick first and then looks at the parts.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import ramdecl  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC018C000            # free (FF) in all three images, behind the pad colours (0xC018B000 to 0xC018C000)
CODE_END = 0xC018C800
STATE = 0xC018CF00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC018CF40
S_COUNT, S_SWAP = 0, 0x10       # per part: ticks silent (FF at start), and 1 while the patch has given it Punch

KILL_SWITCH = 0x2000            # EXIT held at power-on
HOLD_TICKS = 125                # 125 * 40 ms = 5 s silent before Punch
PUNCH = 0                       # index of insert preset 1, Punch (the getter 0xC003E738 reads entry 0 of its table)

TIMER_LITERAL = 0xC0089D90      # the LED manager's tick as its timer registers it
LED_TICK = 0xC0087740


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ SCREEN_PTR, 0xC03404C0     ; pointer to the screen manager, +0x2C the screen number
.equ PATPTR, 0xC033E6A4         ; the pattern object: part n at +0x804 + 0x330 * n
.equ MUTE_AT, 0x805             ; part byte 1: not 0 while muted
.equ IFXON_AT, 0x824            ; part byte 32: IFX on
.equ STRIDE, 0x330
.equ LED_TICK, @LED_TICK@
.equ PART_OBJ, 0xC009AF20       ; (part) -> the part's sound object; +8 its parameter copy (type at +0x1D), +0x31 its number
.equ OWNS_IFX, 0xC009B138       ; (object) -> 0 for the second part of a stereo pair
.equ PAIRED, 0xC009B124         ; (object) -> 1 for the first part of a stereo pair
.equ REMEMBERED, 0xC0097D18     ; (part) -> address of the index the firmware gave the part last
.equ RELOAD, 0xC0097E70         ; (object, remembered) the firmware's part reload: loads the part's effect when it differs
.equ SET_IFX, 0xC003EDEC        ; (index | 0x80 for a pair, part, tempo * 10) gives a part an insert effect
.equ TEMPO_OBJ, 0xC03403B8
.equ TEMPO_GET, 0xC002BF70      ; the tempo the reload passes, the way 0xC0097E94 gets it
.equ SEQ_OBJ, 0xC004A7D8
.equ MAIN_SCREEN, 1
.equ KILL, @KILL@
.equ STATE, @STATE@
.equ S_COUNT, @S_COUNT@
.equ S_SWAP, @S_SWAP@
.equ HOLD, @HOLD@
.equ PUNCH, @PUNCH@

.org @CODE_AT@

; ===================================================== the tick
; r0 = the LED manager, as the timer passes it. The LED manager's own tick runs first and untouched.
ii_tick:
    push {r3, r4, r5, r6, r7, r8, r9, r10, r11, lr}
    bl LED_TICK
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq ii_done
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    bne ii_done
    ldr r4, =STATE
    mov r5, #0
ii_part:
    mov r0, r5
    bl PART_OBJ
    movs r6, r0
    beq ii_next
    bl OWNS_IFX
    cmp r0, #0
    beq ii_next
    add r8, r4, r5
    ldr r7, [r6, #8]
    ldrb r0, [r7, #0x1D]
    cmp r0, #PUNCH
    beq ii_heard
    ldr r1, =PATPTR
    ldr r1, [r1]
    mov r2, #STRIDE
    mul r2, r5, r2
    add r1, r1, r2
    ldrb r0, [r1, #MUTE_AT]
    cmp r0, #0
    bne ii_silent
    ldrb r0, [r1, #IFXON_AT]
    cmp r0, #0
    beq ii_silent

; heard: the count starts again, and a part that has Punch from the patch gets its own effect back
ii_heard:
    mov r0, #0
    strb r0, [r8, #S_COUNT]
    ldrb r0, [r8, #S_SWAP]
    cmp r0, #1
    bne ii_next
    mov r0, #0
    strb r0, [r8, #S_SWAP]
    mov r0, r5
    bl REMEMBERED
    mov r1, r0
    mov r0, r6
    bl RELOAD
    b ii_next

ii_silent:
    ldrb r0, [r8, #S_SWAP]
    cmp r0, #1
    bne ii_count
    mov r0, r5
    bl REMEMBERED
    ldrb r0, [r0]
    and r0, r0, #0x7F
    cmp r0, #PUNCH
    beq ii_next
    mov r0, #0                  ; the firmware has loaded an effect since: the switch is over, count again
    strb r0, [r8, #S_SWAP]
    strb r0, [r8, #S_COUNT]
    b ii_next

ii_count:
    ldrb r0, [r8, #S_COUNT]
    cmp r0, #0xFF
    moveq r0, #0
    cmp r0, #HOLD
    addlo r0, r0, #1
    strb r0, [r8, #S_COUNT]
    blo ii_next
    ldr r0, =SCREEN_PTR
    ldr r0, [r0]
    cmp r0, #0
    beq ii_next
    ldr r0, [r0, #0x2C]
    cmp r0, #MAIN_SCREEN
    bne ii_next
    mov r0, r5
    bl REMEMBERED
    ldrb r0, [r0]
    cmp r0, #0xFF               ; the firmware has not given the part an effect yet
    beq ii_next
    mov r0, r6
    bl PAIRED
    cmp r0, #0
    movne r9, #0x80
    moveq r9, #0
    orr r9, r9, #PUNCH
    ldr r0, =TEMPO_OBJ
    bl TEMPO_GET
    cmp r0, #0
    bge ii_tempo
    bl SEQ_OBJ
    mov r2, #10
    ldr r3, [r0, #0x318]
    mul r0, r2, r3
ii_tempo:
    lsl r2, r0, #16
    lsr r2, r2, #16
    mov r0, r9
    ldrb r1, [r6, #0x31]
    bl SET_IFX
    ldrb r0, [r6, #0x31]
    bl REMEMBERED
    strb r9, [r0]
    tst r9, #0x80
    strbne r9, [r0, #1]
    mov r0, #1
    strb r0, [r8, #S_SWAP]

ii_next:
    add r5, r5, #1
    cmp r5, #16
    blt ii_part
ii_done:
    pop {r3, r4, r5, r6, r7, r8, r9, r10, r11, pc}

.align 4
.pool
"""


def source():
    text = SOURCE
    for key, value in {
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}", "LED_TICK": f"{LED_TICK:#x}",
        "S_COUNT": S_COUNT, "S_SWAP": S_SWAP, "HOLD": HOLD_TICKS, "PUNCH": PUNCH,
    }.items():
        text = text.replace(f"@{key}@", str(value))
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def build_patch(vsb):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    if struct.unpack("<I", was(TIMER_LITERAL, 4))[0] != LED_TICK:
        raise SystemExit("the LED manager does not register its tick through the literal at 0xC0089D90 in this VSB")
    free(STATE, STATE_END - STATE)

    return {
        "format": "gelumpe-patch", "version": 1, "id": "ifx-idle", "builds": ["hacktribe", "stock"],
        "name": "Ruhender Insert-Effekt: ein Part, der 5 s stumm ist oder dessen IFX aus ist, bekommt Punch, bis er wieder zu hören ist",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "idle insert effect: the LED manager's tick, then per part the silent time, Punch after 5 s, the own effect back when heard"},
            {"file": file_offset(TIMER_LITERAL), "bytes": struct.pack("<I", symbols["ii_tick"]).hex(), "expect": sha(was(TIMER_LITERAL, 4)),
             "note": "the LED manager registers the patch's tick instead of its own; the patch's tick calls it first"},
        ],
        "hooks": [
            {"site": f"{TIMER_LITERAL:#010X}".replace("0X", "0x"), "kind": "literal", "chain": "led-timer", "position": "replace", "swallow": False,
             "note": "the patch's tick runs the LED manager's tick, then looks at the parts"},
        ],
        "startPhase": [
            {"file": file_offset(TIMER_LITERAL), "length": 4, "why": "the LED manager registers its 40 ms timer while the device starts, now with the patch's tick"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "ii_tick runs every 40 ms from the start: it runs the LED manager's tick and counts; it switches only on the main screen after 5 s"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: per part the ticks silent and whether it has Punch from the patch", "tools/patch/ifx_idle.py:STATE"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    patch = build_patch(raw)
    if a.listing:
        at, code, symbols = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
