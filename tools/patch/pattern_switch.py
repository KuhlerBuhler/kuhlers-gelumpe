"""Builds the pattern switch patch (docs/ideen/46-patternwechsel-bestaetigung.md) for firmware 2.02 with Hacktribe.

While a pattern plays, the wheel only browses: the firmware already shows the chosen pattern as
NEXT:nnn and holds nothing but a number and a flag, so the patch keeps the choice from being applied.
MENU (ENTER) on the main screen confirms the browsed pattern, and it starts at the next sequence end.
EXIT takes the browse or the confirmation back. Stopped, in record and for every other way to choose a
pattern (pad, MIDI program change, chain), the firmware behaves as it always did.

    python3 tools/patch/pattern_switch.py --vsb SYSTEM.VSB [--out data/patches/pattern-switch.json]

Eight hooks, none of them before the main screen:
  wheel        the tail call of the main screen's VALUE handler into the selector, 0xC006513C
  pad          first instruction of the pad selection, 0xC006EDE4, clears browse and confirmation
  MIDI         first instruction of the program change handler, 0xC006EE00, ditto
  MENU         slot +0x18 of the main screen's class, 0xC00E34B0, confirms
  EXIT         slot +0x08 of the same class, 0xC00E34A0, takes browse or confirmation back
  sequence end the call that asks for the number to start, 0xC005F1C4 (runs in the engine task, only reads)
  STOP         first instruction of the pending-pattern applier, 0xC0081B5C
  label        the load of "NEXT:" in the lower line builder, 0xC0086DC4, shows VIEW: while browsing

The patch is on only when EXIT was not held at power-on, a card is available and the setting word PS_SETTING
is not 0 (the BLECH menu writes it; never written means on). Off, every hook goes straight to the original.
Nothing of the firmware is copied and nothing is written to flash or to the card.
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
import synthaddr  # noqa: E402
import card_gate  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC0180000            # free (FF) in the image, far from the other patches
CODE_END = 0xC0180C00
STATE = 0xC0180F00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC0180F40
S_BROWSE, S_ARMED, S_ARMNUM, S_SETTING = 0, 4, 8, 0x10
PS_SETTING = STATE + S_SETTING  # the setting word the BLECH menu writes: never written (FFFFFFFF) or 1 is on, 0 is off

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)

WHEEL_HOOK = 0xC006513C         # b 0xC008206C, the VALUE handler's tail call into the selector
WHEEL_WORD = 0xEA0073CA
SELECT = 0xC008206C
PAD_HOOK = 0xC006EDE4           # push {r4, lr}
PAD_WORD = 0xE92D4010
PAD_BODY = 0xC006EDE8
MIDI_HOOK = 0xC006EE00          # push {r3, r4, r5, lr}
MIDI_WORD = 0xE92D4038
MIDI_BODY = 0xC006EE04
MENU_SLOT = 0xC00E34B0          # main screen class, slot 6
MENU_ORIG = 0xC0065144
EXIT_SLOT = 0xC00E34A0          # main screen class, slot 2
EXIT_ORIG = 0xC0060F04
SEQ_CALL = 0xC005F1C4           # bl 0xC00818D8, the pattern number the sequence end asks for
SEQ_FUNC = 0xC00818D8
STOP_HOOK = 0xC0081B5C          # ldrb r3, [r0, #0x341]
STOP_WORD = 0xE5D03341
STOP_BODY = 0xC0081B60
LABEL_HOOK = 0xC0086DC4         # ldr r1, [pc, #0xe0] = "NEXT:"
LABEL_WORD = 0xE59F10E0
NEXT_TEXT = 0xC00A72E0


FIRMWARE_PLACES = ["WHEEL_HOOK", "SELECT", "PAD_HOOK", "PAD_BODY", "MIDI_HOOK", "MIDI_BODY", "MENU_SLOT", "MENU_ORIG", "EXIT_SLOT", "EXIT_ORIG",
                   "SEQ_CALL", "SEQ_FUNC", "STOP_HOOK", "STOP_BODY", "LABEL_HOOK", "NEXT_TEXT"]
SYNTH = False
SYNTH_LABEL_WORD = 0xE59F10FC   # ldr r1, [pc, #0xfc]: the synth's builder is laid out a little differently


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); the code and the state stay where they are."""
    global SYNTH, LABEL_WORD
    SYNTH = build == "synth"
    synthaddr.use(globals(), FIRMWARE_PLACES, build)
    LABEL_WORD = SYNTH_LABEL_WORD if SYNTH else _SAMPLER_LABEL_WORD


_SAMPLER_LABEL_WORD = LABEL_WORD


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ FATFS, 0xC06A010C          ; FatFs volume table: first entry is the volume of the card, its byte 0 is the mounted type
.equ TRANSPORT, 0xC0030D28      ; returns the transport object, +0x308 its state (0 stopped, 3 to 5 record)
.equ PSEL, 0xC00431F0           ; returns the pattern selection object: +0x318 chosen number, +0x341 pending flag
.equ PLAYER, 0xC002FAFC         ; returns the player: +0x318 the number that runs
.equ SET_NUMBER, 0xC0081F50     ; (psel, number, send MIDI)
.equ WRAP, 0xC0040D24           ; (value, 0, 249) wraps into the pattern range
.equ SELECT, @SELECT@
.equ MENU_ORIG, @MENU_ORIG@
.equ EXIT_ORIG, @EXIT_ORIG@
.equ NEXT_TEXT, @NEXT_TEXT@
.equ KILL, @KILL@
.equ STATE, @STATE@
.equ S_BROWSE, 0                ; 1 while the wheel has browsed away from what will play
.equ S_ARMED, 4                 ; 1 while a pattern is confirmed
.equ S_ARMNUM, 8                ; the confirmed number, valid while S_ARMED is 1
.equ S_SETTING, 0x10            ; PS_SETTING: FFFFFFFF or 1 is on, 0 is off

.org @CODE_AT@

; ===================================================== is the patch on
; r0 = 1 when EXIT was not held at power-on, a card is available and the setting is not off. Clobbers r0 and r12.
; Reads memory only, so the engine task may call it.
pc_active:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq pa_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne pa_no
@CARD_CHECK@    ldr r12, =STATE
    ldr r12, [r12, #S_SETTING]
    cmn r12, #1
    moveq r0, #1
    bxeq lr
    ands r0, r12, #1
    bxne lr
pa_no:
    mov r0, #0
    bx lr

; ===================================================== the wheel
; Entered from the VALUE handler's tail call: r0 = the selection object, r1 = the steps (times ten with SHIFT), lr = its caller.
; The firmware's selector would add them to the chosen number and set it with MIDI. While a pattern plays, this sets it
; without MIDI and remembers that it is only being browsed. Stopped or recording, the selector runs as always.
wheel_hook:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    bl pc_active
    cmp r0, #0
    beq wh_stock
    bl TRANSPORT
    ldr r0, [r0, #0x308]
    cmp r0, #0
    beq wh_stock
    sub r0, r0, #3
    cmp r0, #2
    bls wh_stock
    ldr r6, =STATE
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    bne wh_go
    mov r0, #0                  ; nothing is pending: an old browse or confirmation is gone
    str r0, [r6, #S_ARMED]
    str r0, [r6, #S_BROWSE]
wh_go:
    ldr r0, [r4, #0x318]
    add r0, r5, r0
    mov r1, #0
    mov r2, #249
    bl WRAP
    mov r5, r0
    mov r0, #1                  ; browsing, set before the firmware tells the display (the lower line reads it then),
    ldr r1, [r6, #S_ARMED]      ; unless this is the confirmed number: nothing left to browse
    cmp r1, #1
    bne wh_set
    ldr r1, [r6, #S_ARMNUM]
    cmp r1, r5
    moveq r0, #0
wh_set:
    str r0, [r6, #S_BROWSE]
    mov r0, r4
    mov r1, r5
    mov r2, #0                  ; no MIDI while browsing
    bl SET_NUMBER
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    bne wh_out
    mov r0, #0                  ; back on the number that runs: the firmware cleared the pending flag, so nothing is browsed or confirmed
    str r0, [r6, #S_BROWSE]
    str r0, [r6, #S_ARMED]
wh_out:
    pop {r4, r5, r6, pc}
wh_stock:
    mov r0, r4
    mov r1, r5
    pop {r4, r5, r6, lr}
    b SELECT

; ===================================================== a pad or a program change chooses: that is a deliberate choice
pad_hook:
    push {r0, r12}
    ldr r12, =STATE
    mov r0, #0
    str r0, [r12, #S_ARMED]
    str r0, [r12, #S_BROWSE]
    pop {r0, r12}
    push {r4, lr}               ; the replaced first instruction
    b @PAD_BODY@

midi_hook:
    push {r0, r12}
    ldr r12, =STATE
    mov r0, #0
    str r0, [r12, #S_ARMED]
    str r0, [r12, #S_BROWSE]
    pop {r0, r12}
    push {r3, r4, r5, lr}       ; the replaced first instruction
    b @MIDI_BODY@

; ===================================================== MENU on the main screen
; Slot of the main screen's class: r0 = the screen. The firmware ignores MENU while a pattern is pending; this confirms
; a browsed pattern (MIDI goes out now, the pattern starts at the sequence end). Anything else is the firmware's.
menu_hook:
    push {r4, r5, r6, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq mn_stock
    bl PSEL
    mov r5, r0
    ldrb r0, [r5, #0x341]
    cmp r0, #0
    beq mn_stock
    ldr r3, =STATE
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    bne mn_stock
    ldr r0, [r5, #0x318]
    str r0, [r3, #S_ARMNUM]     ; the number first, the engine task reads it as soon as S_ARMED is 1
    mov r1, #1
    str r1, [r3, #S_ARMED]
    mov r1, #0
    str r1, [r3, #S_BROWSE]
    mov r1, r0
    mov r0, r5
    mov r2, #1                  ; Bank Select and Program Change now, and the display is told
    bl SET_NUMBER
    pop {r4, r5, r6, pc}
mn_stock:
    mov r0, r4
    pop {r4, r5, r6, lr}
    b MENU_ORIG

; ===================================================== EXIT on the main screen
; Browsing goes back to the confirmed number, or to the one that runs. A confirmation without browsing is taken back,
; with the program change for the running pattern. Anything else is the firmware's.
exit_hook:
    push {r4, r5, r6, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq ex_stock
    bl PSEL
    mov r5, r0
    ldrb r0, [r5, #0x341]
    cmp r0, #0
    beq ex_stock
    ldr r6, =STATE
    ldr r0, [r6, #S_BROWSE]
    cmp r0, #1
    beq ex_browse
    ldr r0, [r6, #S_ARMED]
    cmp r0, #1
    bne ex_stock
    mov r0, #0                  ; take the confirmation back
    str r0, [r6, #S_ARMED]
    bl PLAYER
    ldr r1, [r0, #0x318]
    mov r0, r5
    mov r2, #1
    bl SET_NUMBER
    pop {r4, r5, r6, pc}
ex_browse:
    mov r0, #0
    str r0, [r6, #S_BROWSE]
    ldr r0, [r6, #S_ARMED]
    cmp r0, #1
    ldreq r1, [r6, #S_ARMNUM]
    beq ex_to
    bl PLAYER
    ldr r1, [r0, #0x318]
ex_to:
    mov r0, r5
    mov r2, #0
    bl SET_NUMBER
    ldrb r0, [r5, #0x341]
    cmp r0, #0
    bne ex_out
    mov r0, #0                  ; back on the running pattern, nothing is confirmed any more
    str r0, [r6, #S_ARMED]
ex_out:
    pop {r4, r5, r6, pc}
ex_stock:
    mov r0, r4
    pop {r4, r5, r6, lr}
    b EXIT_ORIG

; ===================================================== sequence end
; Replaces the call that fetches the number to start (r0 = the selection object). Engine task: this only reads.
; Confirmed: that number (and the state is over). Browsing: the one that runs, so the pattern repeats or chains as it does
; without a choice. Anything else: the chosen number as always.
seq_hook:
    push {r4, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq sq_plain
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    beq sq_plain
    ldr r3, =STATE
    ldr r0, [r3, #S_ARMED]
    cmp r0, #1
    bne sq_browse
    ldr r0, [r3, #S_ARMNUM]
    mov r1, #0
    str r1, [r3, #S_ARMED]
    str r1, [r3, #S_BROWSE]
    pop {r4, pc}
sq_browse:
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    bne sq_plain
    bl PLAYER
    ldr r0, [r0, #0x318]
    pop {r4, pc}
sq_plain:
    ldr r0, [r4, #0x318]
    pop {r4, pc}

; ===================================================== STOP
; First instruction of the function that applies a pending pattern at once (r0 = the selection object). A confirmed
; pattern is applied as the firmware does; a browse is dropped, the playing pattern stays and nothing is pending.
stop_hook:
    push {r1, r2, r3, r4, r5, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq st_out
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    beq st_out
    ldr r3, =STATE
    ldr r0, [r3, #S_ARMED]
    cmp r0, #1
    ldreq r0, [r3, #S_ARMNUM]
    streq r0, [r4, #0x318]
    beq st_flags
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    bne st_out                  ; pending from a pad or a program change: the firmware's
    bl PLAYER
    ldr r1, [r0, #0x318]
    str r1, [r4, #0x318]
    mov r2, #0
    strb r2, [r4, #0x341]
    mov r0, r4
    bl SET_NUMBER               ; the firmware leaves the chosen number alone once it is the running one: written above, this tells the display
st_flags:
    ldr r3, =STATE
    mov r0, #0
    str r0, [r3, #S_ARMED]
    str r0, [r3, #S_BROWSE]
st_out:
    mov r0, r4
    pop {r1, r2, r3, r4, r5, lr}
    ldrb r3, [r0, #0x341]       ; the replaced first instruction
    b @STOP_BODY@

; ===================================================== the label of the lower line
; Replaces the load of "NEXT:" in the builder of that line (bl, so lr is ours; r0 = the screen must survive).
; Browsing shows VIEW: instead, a confirmed pattern keeps NEXT:.
label_hook:
    push {r0, lr}
    bl pc_active
    cmp r0, #0
    beq lb_next
    bl PSEL
    mov r3, r0
    ldrb r0, [r3, #0x341]
    cmp r0, #0
    beq lb_next
    ldr r2, =STATE
    ldr r0, [r2, #S_BROWSE]
    cmp r0, #1
    bne lb_next
    ldr r1, =view_text
    pop {r0, pc}
lb_next:
    ldr r1, =NEXT_TEXT
    pop {r0, pc}

view_text:
    .asciz "VIEW:"
.align 4
lit_pool:
.pool
"""


# the synth has no wrap function (its selector wraps inline); the patch carries its own for 0..249
WRAP_LOCAL = """
wrap_local:                     ; (value, 0, 249) like the firmware's, the range is the synth's pattern count
    cmp r0, #0
    addlt r0, r0, #250
    cmp r0, #249
    subgt r0, r0, #250
    bx lr
"""


def source():
    text = SOURCE.replace("@CARD_CHECK@", card_gate.source("synth" if SYNTH else "hacktribe", "pa_no"))
    if SYNTH:
        text = synthaddr.source(text, keep={0xC0040D24}).replace("bl WRAP", "bl wrap_local").replace("\nview_text:", WRAP_LOCAL + "\nview_text:")
    for key, value in {
        "SELECT": f"{SELECT:#x}", "MENU_ORIG": f"{MENU_ORIG:#x}", "EXIT_ORIG": f"{EXIT_ORIG:#x}", "NEXT_TEXT": f"{NEXT_TEXT:#x}",
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}", "PAD_BODY": f"{PAD_BODY:#x}",
        "MIDI_BODY": f"{MIDI_BODY:#x}", "STOP_BODY": f"{STOP_BODY:#x}",
    }.items():
        text = text.replace(f"@{key}@", value)
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def branch_word(at, target):
    return struct.unpack("<I", branch(at, target))[0]


def bl_word(at, target):
    return struct.unpack("<I", branch(at, target, True))[0]


def build_patch(vsb, build="hacktribe"):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    use_build(build)
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def word(addr):
        return struct.unpack("<I", was(addr, 4))[0]

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    expected = (
        (WHEEL_HOOK, branch_word(WHEEL_HOOK, SELECT), "the wheel handler does not end in the branch into the selector"),
        (PAD_HOOK, PAD_WORD, "the pad selection does not start with push {r4, lr}"),
        (MIDI_HOOK, MIDI_WORD, "the program change handler does not start with push {r3, r4, r5, lr}"),
        (MENU_SLOT, MENU_ORIG, "the MENU slot of the main screen is not the one the patch expects"),
        (EXIT_SLOT, EXIT_ORIG, "the EXIT slot of the main screen is not the one the patch expects"),
        (SEQ_CALL, bl_word(SEQ_CALL, SEQ_FUNC), "the sequence end does not call the number fetch where the patch expects it"),
        (STOP_HOOK, STOP_WORD, "the pending applier does not start with ldrb r3, [r0, #0x341]"),
        (LABEL_HOOK, LABEL_WORD, "the lower line builder does not load NEXT: as the patch expects"),
    )
    for addr, want, why in expected:
        if word(addr) != want:
            raise SystemExit(f"{why} in this VSB")
    literal = LABEL_HOOK + 8 + (LABEL_WORD & 0xFFF)
    if word(literal) != NEXT_TEXT:
        raise SystemExit("the load of NEXT: does not read the address of the NEXT: text in this VSB")
    if was(NEXT_TEXT, 6) != b"NEXT:\x00":
        raise SystemExit("the NEXT: text is not where the patch expects it in this VSB")
    free(STATE, STATE_END - STATE)

    def hook(addr, name, link, note):
        return {"file": file_offset(addr), "bytes": branch(addr, symbols[name], link).hex(), "expect": sha(was(addr, 4)), "note": note}

    def slot(addr, name, note):
        return {"file": file_offset(addr), "bytes": struct.pack("<I", symbols[name]).hex(), "expect": sha(was(addr, 4)), "note": note}

    def declare(addr, kind, chain, position, swallow, note):
        return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": kind, "chain": chain, "position": position, "swallow": swallow, "note": note}

    return {
        "format": "gelumpe-patch", "version": 1, "id": "pattern-switch", "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "name": "Patternwechsel erst nach Bestaetigung (MENU)",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "pattern switch: wheel, MENU, EXIT, pad, program change, sequence end, STOP and label hooks"},
            hook(WHEEL_HOOK, "wheel_hook", False, "the wheel's tail call into the selector goes through the hook"),
            hook(PAD_HOOK, "pad_hook", False, "first instruction of the pad selection jumps to the hook"),
            hook(MIDI_HOOK, "midi_hook", False, "first instruction of the program change handler jumps to the hook"),
            slot(MENU_SLOT, "menu_hook", "MENU of the main screen goes to the hook"),
            slot(EXIT_SLOT, "exit_hook", "EXIT of the main screen goes to the hook"),
            hook(SEQ_CALL, "seq_hook", True, "the sequence end asks the hook for the number to start"),
            hook(STOP_HOOK, "stop_hook", False, "first instruction of the pending applier jumps to the hook"),
            hook(LABEL_HOOK, "label_hook", True, "the load of NEXT: goes through the hook"),
        ],
        "hooks": [
            declare(WHEEL_HOOK, "instruction", "pattern-set", "replace", False, "wheel while playing: browse with set_number(psel, n, 0) instead of the branch into the selector; set_number is still called, so what reacts to it still sees the number"),
            declare(PAD_HOOK, "instruction", "pattern-set", "before", False, "pad selection clears browse and confirmation"),
            declare(MIDI_HOOK, "instruction", "pattern-set", "before", False, "MIDI program change clears browse and confirmation"),
            declare(MENU_SLOT, "vtable-slot", "key-dispatch", "before", True, "MENU on the main screen confirms the browsed pattern"),
            declare(EXIT_SLOT, "vtable-slot", "key-dispatch", "before", True, "EXIT on the main screen takes the browse or the confirmation back"),
            declare(SEQ_CALL, "call", "sequence-end", "replace", False, "the pattern number the sequence end asks for"),
            declare(STOP_HOOK, "instruction", "stop-pending", "before", False, "STOP drops a browse, or applies the confirmed pattern as the firmware does"),
            declare(LABEL_HOOK, "instruction", "pattern-label", "replace", False, "VIEW: instead of NEXT: while browsing"),
        ],
        "startPhase": [],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: browse, armed, armed number, and PS_SETTING at +0x10 for the BLECH menu", "tools/patch/pattern_switch.py:STATE"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    use_build(a.build)
    patch = build_patch(raw, a.build)
    if a.listing:
        at, code, symbols = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}, setting word {PS_SETTING:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
