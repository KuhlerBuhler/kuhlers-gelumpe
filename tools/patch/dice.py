"""Builds the dice patch (docs/messungen/2026-10-16-wuerfeln.md, docs/ideen/29-wuerfeln.md) for firmware 2.02 with Hacktribe and Korg's own 2.02.

SHIFT + PART ERASE writes a new melody into the part that is selected, on the device, in the pattern in RAM:

    notes   random notes of the pattern's own key and scale (the firmware's own scale table, 0xC00C5DB8, 16 bytes a scale; the
            key from the pattern byte 0x2B, the scale from 0x2C), within two octaves from the root at C3 (note 48 plus the key);
            a walk with small steps, now and then a leap, and on the first step of a bar often the root
    rhythm  rests and notes on the 16th grid: the beats of a bar are likely, the steps in between are not; step 1 always sounds
    gates   mostly a half or three quarters of a step, now and then a full step, a short one, and a tie (gate 127) into a following note
    length  the pattern's length (1 to 4 bars) and the part's LAST STEP (the first k steps of every bar play, measured); steps the
            part does not play are not touched

The part is the selected one, whatever it is: there is no drum mode. Only the steps of that part change (on, gate, velocity, trigger and
the first note slot; the other three note slots are cleared); nothing else of the pattern, nothing in flash, nothing on the card. The
pattern stays unsaved until WRITE, like after any edit. Without SHIFT, PART ERASE is the firmware's own key.

The patch is on only when EXIT was not held at power-on, a card was seen since power-on and the setting word DC_SETTING is not 0 (a menu
page would write it, like TM_SETTING of TAP MOTION; never written means on). It works on the main screen only.

    python3 tools/patch/dice.py --vsb SYSTEM.VSB [--out data/patches/dice.json]

One hook, no start phase: the first instruction of 0xC006FEDC, the key function of the mode keys (PART ERASE, TRIGGER, SEQUENCER,
KEYBOARD, CHORD, STEP JUMP; the key dispatcher 0xC00700D8 sends them there with the object, the key and 1 for pressed). It
takes the press of PART ERASE with SHIFT held and hands everything else to the firmware's own code. The random numbers are a
xorshift32 generator, seeded at every press from Timer3 (the free-running 150 MHz counter of the script runtime) and its own
last state.

The steps are written as bytes, the way the firmware's own setters do (0xC0048FD4, 0xC0049040, 0xC0049214, 0xC0049098 are plain
byte stores into the part's step record). The pads show the steps of the selected bar and only redraw when the firmware's model tells
its observers something changed, so the roll ends with the message the firmware itself sends when the bar section changes (0x0B and
the section that is selected already, through 0xC0070688); without it the pad LEDs keep the old picture until the next bar key. The
roll does not enter the firmware's undo memory: SHIFT + EDIT< does nothing to it.
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

CODE_AT = 0xC018A000            # free (FF) in the image, behind the note assistant (0xC0189000 to 0xC018A000) and clear of the synth filters (0xC0190000)
CODE_END = 0xC018A800
STATE = 0xC018AF00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC018AF40
S_SETTING, S_RNG, S_POOLN, S_POOL = 0, 4, 8, 0x10
DC_SETTING = STATE + S_SETTING  # the setting word a menu page would write: never written (FFFFFFFF) or 1 is on, 0 is off

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)
KEY_PART_ERASE = 0x11           # panel number of PART ERASE (data/panel.mjs)
ROOT_NOTE = 48                  # C3: the key adds 0 to 11 semitones
SPAN = 24                       # the notes lie within two octaves from the root

KEY_HOOK = 0xC006FEDC           # push {r3, r4, r5, r6, r7, lr}, the key function of the mode keys
KEY_WORD = 0xE92D40F8
KEY_BODY = 0xC006FEE0
BODY_WORD = 0xE59F30A8          # what the function does next (ldr r3, [pc, #0xa8]): the hook stub goes on there after the replaced push
KEY_PUSH = "push {r3, r4, r5, r6, r7, lr}"
SCALE_TABLE = 0xC00C5DB8        # 16 bytes a scale, 35 scales: the degrees of the scale over the root, two octaves worth. Hacktribe keeps a copy at 0xC013D000 (docs/messungen/2026-10-15-note-assistant.md); Korg's own build only has this one, the same bytes in both
TIMER3 = 0x01F0D010             # the free-running counter the script runtime reads (docs/plugins.md, korg.millis)


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ FATFS, 0xC06A010C          ; FatFs volume table: first entry is the volume of the card, its byte 0 is the mounted type
.equ PATPTR, 0xC033E6A4         ; the pattern object, the block starts 4 bytes in: part n at +0x804 + 0x330 * n, step k of it at +0x30 + 12 * k
.equ HW_PART, 0xC06B2428        ; the selected part, 0 to 15
.equ SCREEN_PTR, 0xC03404C0     ; pointer to the screen manager: +0x2C the screen number (1 is the main screen), +0x24 the window (0 none)
.equ SHIFT_OBJ, 0xC0040F04      ; returns the object that holds the SHIFT flag at +0x358
.equ NOTIFY, 0xC0070688         ; (observers, message): tells the observers of the sequencer's model (the pad LEDs among them) what changed
.equ OBSERVERS, 0xC06B210C      ; the model's observer list (the model object at 0xC06B2108, its first 4 bytes are the vtable)
.equ SECTION, 0xC06B244C        ; the model's selected bar section, 0 to 3 (+0x344): the pads show the 16 steps of it
.equ MSG_SECTION, 0x0B          ; the message the firmware sends when the section changes; the pad LEDs redraw from the pattern on it
.equ TABLE, @TABLE@
.equ TIMER3, @TIMER3@
.equ KILL, @KILL@
.equ KEY_ERASE, @KEY_ERASE@
.equ ROOT, @ROOT@
.equ SPAN, @SPAN@
.equ STATE, @STATE@
.equ S_SETTING, @S_SETTING@     ; DC_SETTING: FFFFFFFF or 1 is on, 0 is off
.equ S_RNG, @S_RNG@             ; the generator's state
.equ S_POOLN, @S_POOLN@         ; how many different notes the scale gives within SPAN
.equ S_POOL, @S_POOL@           ; those notes (degrees, ascending), up to 16 bytes
.equ KEY_BODY, @KEY_BODY@

.org @CODE_AT@

; ===================================================== the hook
; The first instruction of the mode keys' key function (r0 = the object, r1 = key, r2 = 1 pressed or 0 released, lr = the caller).
; PART ERASE pressed with SHIFT held, on the main screen, with the patch on: roll the part. Everything else goes on into the firmware.
dice_hook:
    cmp r1, #KEY_ERASE
    cmpeq r2, #1
    bne dh_orig
    push {r0, r1, r2, r3, r12, lr}
    bl dc_ready
    cmp r0, #0
    beq dh_pass
    bl dice_run
    pop {r0, r1, r2, r3, r12, lr}
    bx lr                       ; taken: the firmware would only switch its erase mode
dh_pass:
    pop {r0, r1, r2, r3, r12, lr}
dh_orig:
    push {r3, r4, r5, r6, r7, lr}   ; the replaced first instruction
    b KEY_BODY

; ===================================================== is the patch on
; r0 = 1 when EXIT was not held at power-on, a card was seen since power-on and the setting is not off. Clobbers r0 and r12.
; Writes only the card latch (tools/patch/card_gate.py), the first time a card is there.
dc_active:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq da_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne da_no
@CARD_CHECK@    ldr r12, =STATE
    ldr r12, [r12, #S_SETTING]
    cmn r12, #1
    moveq r0, #1
    bxeq lr
    ands r0, r12, #1
    bxne lr
da_no:
    mov r0, #0
    bx lr

; r0 = 1 when the patch is on, the main screen is up with no window over it, and SHIFT is held. Clobbers r0 to r3 and r12.
dc_ready:
    push {lr}
    bl dc_active
    cmp r0, #0
    beq dr_no
    ldr r12, =SCREEN_PTR
    ldr r12, [r12]
    cmp r12, #0
    beq dr_no
    ldr r0, [r12, #0x2C]
    cmp r0, #1
    bne dr_no
    ldr r0, [r12, #0x24]
    cmp r0, #0
    bne dr_no
    bl SHIFT_OBJ
    ldr r0, [r0, #0x358]
    cmp r0, #0
    movne r0, #1
    pop {pc}
dr_no:
    mov r0, #0
    pop {pc}

; ===================================================== the generator
; r0 = the next 32-bit number (xorshift32). Clobbers r12 only.
dc_rand:
    ldr r12, =STATE
    ldr r0, [r12, #S_RNG]
    eor r0, r0, r0, lsl #13
    eor r0, r0, r0, lsr #17
    eor r0, r0, r0, lsl #5
    str r0, [r12, #S_RNG]
    bx lr

; The state takes the counter in: a press a little later gives other numbers. Clobbers r0 to r2.
dc_seed:
    ldr r0, =TIMER3
    ldr r0, [r0]
    ldr r1, =STATE
    ldr r2, [r1, #S_RNG]
    eor r2, r2, r0
    eor r2, r2, r0, lsl #16
    cmp r2, #0
    ldreq r2, =0x9E3779B9
    str r2, [r1, #S_RNG]
    bx lr

; ===================================================== the notes the scale gives
; r0 = the scale's row of the firmware's table (16 degrees). The degrees up to SPAN, different and ascending, go to POOL; their
; number to POOLN. Clobbers r0 to r3 and r12.
dc_pool:
    push {r4, r5, r6, lr}
    ldr r4, =STATE
    add r4, r4, #S_POOL
    mov r3, #0                  ; how many so far
    mov r1, #0                  ; the degree being looked at
dp_next:
    ldrb r2, [r0, r1]
    cmp r2, #SPAN
    bhi dp_skip
    mov r12, #0                 ; where it goes: the first place holding a degree that is not lower
dp_find:
    cmp r12, r3
    bhs dp_ins
    ldrb r5, [r4, r12]
    cmp r5, r2
    bhs dp_same
    add r12, r12, #1
    b dp_find
dp_same:
    beq dp_skip                 ; already there
dp_ins:
    mov r6, r3                  ; make room: move the higher ones one place up
dp_shift:
    cmp r6, r12
    bls dp_put
    sub r5, r6, #1
    ldrb r5, [r4, r5]
    strb r5, [r4, r6]
    sub r6, r6, #1
    b dp_shift
dp_put:
    strb r2, [r4, r12]
    add r3, r3, #1
dp_skip:
    add r1, r1, #1
    cmp r1, #16
    bne dp_next
    ldr r5, =STATE
    str r3, [r5, #S_POOLN]
    pop {r4, r5, r6, pc}

; ===================================================== the roll
; Registers: r4 the pattern object, later the number of notes in POOL; r5 the part, later the index of the note in POOL; r6 the part's
; record, later the step being written; r7 the first step's record; r8 the number of steps (16 to 64); r9 the root note; r10 the
; steps a bar plays (LAST STEP, 1 to 16); r11 POOL; r1 the step.
dice_run:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    ldr r4, =PATPTR
    ldr r4, [r4]
    cmp r4, #0
    beq dn_out
    ldr r5, =HW_PART
    ldr r5, [r5]
    cmp r5, #15
    bhi dn_out
    mov r0, #0x330
    mul r1, r5, r0
    add r6, r4, r1
    add r6, r6, #0x800
    add r6, r6, #4              ; the part's record
    add r7, r6, #0x30           ; its first step
    ldrb r0, [r4, #0x29]        ; pattern length, 0 to 3 for 1 to 4 bars
    cmp r0, #3
    movhi r0, #3
    add r0, r0, #1
    lsl r8, r0, #4
    ldrb r0, [r6]               ; LAST STEP: 0 or 16 all of a bar, k the first k steps of each bar
    mov r10, #16
    cmp r0, #1
    blo dn_lim
    cmp r0, #15
    movls r10, r0
dn_lim:
    ldrb r9, [r4, #0x2B]        ; the key, 0 (C) to 11 (B)
    cmp r9, #11
    movhi r9, #0
    add r9, r9, #ROOT
    ldrb r0, [r4, #0x2C]        ; the scale, 0 to 34
    cmp r0, #34
    movhi r0, #0
    ldr r1, =TABLE
    add r0, r1, r0, lsl #4
    bl dc_pool
    bl dc_seed

; the rhythm: which steps sound. The beats of a bar are likely, the steps in between are not; step 1 always.
    mov r1, #0
n1_loop:
    and r3, r1, #15
    cmp r3, r10
    bhs n1_next                 ; a step the part does not play: left as it is
    cmp r3, #0
    moveq r2, #250
    beq n1_roll
    cmp r3, #8
    moveq r2, #210
    beq n1_roll
    tst r3, #3
    moveq r2, #170
    beq n1_roll
    tst r3, #1
    moveq r2, #130
    movne r2, #60
n1_roll:
    bl dc_rand
    lsr r0, r0, #24
    cmp r0, r2
    movlo r0, #1
    movhs r0, #0
    cmp r1, #0
    moveq r0, #1
    add r12, r7, r1, lsl #3
    add r12, r12, r1, lsl #2
    strb r0, [r12]
n1_next:
    add r1, r1, #1
    cmp r1, r8
    bne n1_loop

; the notes, velocities and gates of the steps that sound
    ldr r11, =STATE
    ldr r4, [r11, #S_POOLN]
    add r11, r11, #S_POOL
    mov r0, #85                 ; the walk starts a third of the way up the pool
    mul r5, r4, r0
    lsr r5, r5, #8
    mov r1, #0
n2_loop:
    and r3, r1, #15
    cmp r3, r10
    bhs n2_next
    add r6, r7, r1, lsl #3
    add r6, r6, r1, lsl #2
    ldrb r0, [r6]
    cmp r0, #0
    beq n2_next
    bl dc_rand
    cmp r3, #0
    bne n2_walk
    lsr r2, r0, #28             ; the first step of a bar: the root, four times in ten
    cmp r2, #6
    movlo r5, #0
    blo n2_note
n2_walk:
    lsr r2, r0, #24
    and r2, r2, #15
    cmp r2, #0
    bne n2_step
    lsr r2, r0, #16             ; one time in sixteen a leap to anywhere in the pool
    and r2, r2, #255
    mul r5, r2, r4
    lsr r5, r5, #8
    b n2_note
n2_step:
    lsr r2, r0, #20             ; else a small step up or down, now and then none: degrees -3 to +3, kept in 0 to 6
    and r2, r2, #15
    ldr r12, =deltas
    ldrb r2, [r12, r2]
    add r5, r5, r2
    subs r5, r5, #3
    rsbmi r5, r5, #0            ; a step past the lowest note comes back up, past the highest comes back down
    cmp r5, r4
    blo n2_note
    sub r12, r4, #1
    rsbs r5, r5, r12, lsl #1
    movmi r5, #0
n2_note:
    ldrb r2, [r11, r5]
    add r2, r2, r9
    add r2, r2, #1              ; a step holds the note plus one
    bl dc_rand
    tst r3, #3
    lsr r12, r0, #27
    addeq r12, r12, #92         ; on the beats 92 to 123, between 60 to 91
    addne r12, r12, #60
    strb r12, [r6, #2]
    lsr r12, r0, #8             ; the gate
    and r12, r12, #15
    cmp r12, #8
    movlo r12, #56
    blo n2_gate
    cmp r12, #11
    movlo r12, #76
    blo n2_gate
    cmp r12, #13
    movlo r12, #90
    blo n2_gate
    cmp r12, #14
    moveq r12, #34
    movne r12, #96
n2_gate:
    tst r0, #0x70               ; one time in eight a tie, when a note follows
    bne n2_store
    add r0, r1, #1              ; the next step the part plays
    and r3, r0, #15
    cmp r3, r10
    bichs r0, r0, #15
    addhs r0, r0, #16
    cmp r0, r8
    movhs r0, #0
    add r3, r7, r0, lsl #3
    add r3, r3, r0, lsl #2
    ldrb r0, [r3]
    cmp r0, #0
    movne r12, #127
n2_store:
    mov r0, #1
    strb r0, [r6]
    strb r12, [r6, #1]
    strb r0, [r6, #3]
    strb r2, [r6, #4]
    mov r0, #0
    strb r0, [r6, #5]
    strb r0, [r6, #6]
    strb r0, [r6, #7]
n2_next:
    add r1, r1, #1
    cmp r1, r8
    bne n2_loop
; the pads show the steps of the selected bar: tell the observers the section is (still) the one it is, so they redraw from the pattern
    mov r4, sp
    sub sp, sp, #8
    bic sp, sp, #7
    ldr r0, =SECTION
    ldr r0, [r0]
    and r0, r0, #255
    mov r1, #MSG_SECTION
    orr r1, r1, r0, lsl #8
    str r1, [sp]
    mov r1, #0
    str r1, [sp, #4]
    ldr r0, =OBSERVERS
    mov r1, sp
    bl NOTIFY
    mov sp, r4
dn_out:
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}

deltas:
    .byte 0, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4, 4, 4, 5, 5, 6

.align 4
lit_pool:
.pool
"""


FIRMWARE_PLACES = ["KEY_HOOK", "KEY_BODY", "SCALE_TABLE"]    # the other firmware places of the source are literals in the text, mapped by synthaddr.source
BUILD = "hacktribe"


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/dice.json); the patch's own code and state stay where they are."""
    global BUILD, KEY_WORD, BODY_WORD, KEY_PUSH
    BUILD = build
    synthaddr.use(globals(), FIRMWARE_PLACES, build)
    if build == "synth":
        # the synth's key function of the mode keys starts with push {r3, r4, r5, lr}, then mov r5, r1 (checked in docs/messungen/2026-10-16-blau-dice.md)
        KEY_WORD, BODY_WORD, KEY_PUSH = 0xE92D4038, 0xE1A05001, "push {r3, r4, r5, lr}"
    else:
        KEY_WORD, BODY_WORD, KEY_PUSH = 0xE92D40F8, 0xE59F30A8, "push {r3, r4, r5, r6, r7, lr}"


# The model's pointer instead of the model's address: the model object lives on the heap (0xC06B2108 in the Sampler's emulator, 0xC0582F78 in the
# synth's), the pointer variable is the stable place. The Sampler's source stays as it is (its output is fixed); the synth reads through the pointer.
SYNTH_MODEL = [
    (".equ HW_PART, 0xC06B2428        ; the selected part, 0 to 15\n", ".equ MODEL, 0xC0348884          ; pointer to the sequencer model: +4 its observers, +0x320 the selected part (0 to 15), +0x344 the bar section\n"),
    (".equ OBSERVERS, 0xC06B210C      ; the model's observer list (the model object at 0xC06B2108, its first 4 bytes are the vtable)\n", ""),
    (".equ SECTION, 0xC06B244C        ; the model's selected bar section, 0 to 3 (+0x344): the pads show the 16 steps of it\n", ""),
    ("    ldr r5, =HW_PART\n    ldr r5, [r5]\n", "    ldr r5, =MODEL\n    ldr r5, [r5]\n    ldr r5, [r5, #0x320]\n"),
    ("    ldr r0, =SECTION\n    ldr r0, [r0]\n", "    ldr r0, =MODEL\n    ldr r0, [r0]\n    ldr r0, [r0, #0x344]\n"),
    ("    ldr r0, =OBSERVERS\n", "    ldr r0, =MODEL\n    ldr r0, [r0]\n    add r0, r0, #4\n"),
]


def source():
    text = SOURCE.replace("@CARD_CHECK@", card_gate.source("synth" if BUILD == "synth" else "hacktribe", "da_no", STATE + card_gate.LATCH_OFFSET))
    if BUILD == "synth":
        for old, new in SYNTH_MODEL:
            if text.count(old) != 1:
                raise SystemExit(f"the source has no single place for: {old.strip()}")
            text = text.replace(old, new)
        text = text.replace("    push {r3, r4, r5, r6, r7, lr}   ; the replaced first instruction\n", f"    {KEY_PUSH}   ; the replaced first instruction\n")
        text = synthaddr.source(text, own=[(CODE_AT, CODE_END), (STATE, STATE_END)])
    for key, value in {
        "TABLE": f"{SCALE_TABLE:#x}", "TIMER3": f"{TIMER3:#x}", "KILL": f"{KILL_SWITCH:#x}", "KEY_ERASE": f"{KEY_PART_ERASE:#x}",
        "ROOT": ROOT_NOTE, "SPAN": SPAN, "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}", "KEY_BODY": f"{KEY_BODY:#x}",
        "S_SETTING": S_SETTING, "S_RNG": S_RNG, "S_POOLN": S_POOLN, "S_POOL": S_POOL,
    }.items():
        text = text.replace(f"@{key}@", str(value))
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | ((target - (at + 8)) >> 2) & 0xFFFFFF)


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

    if word(KEY_HOOK) != KEY_WORD:
        raise SystemExit(f"the mode keys' key function does not start with {KEY_PUSH} in this VSB")
    if word(KEY_BODY) != BODY_WORD:
        raise SystemExit(f"the mode keys' key function does not go on with {BODY_WORD:#010x} in this VSB")
    # the table the scale is read from: scale 1 (Ionian) starts 0, 2, 4, 5, 7, 9, 11, 12
    if was(SCALE_TABLE + 16, 8) != bytes([0, 2, 4, 5, 7, 9, 11, 12]) or was(SCALE_TABLE, 16) != bytes(range(16)):
        raise SystemExit("the scale table is not where the patch expects it in this VSB")
    free(STATE, STATE_END - STATE)

    return {
        "format": "gelumpe-patch", "version": 1, "id": "dice", "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "name": "Würfeln: SHIFT + PART ERASE würfelt eine Melodie für den gewählten Part (DICE)",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "dice: the hook, the generator, the scale pool and the roll, and the word a menu page would write (DC_SETTING)"},
            {"file": file_offset(KEY_HOOK), "bytes": branch(KEY_HOOK, symbols["dice_hook"]).hex(), "expect": sha(was(KEY_HOOK, 4)),
             "note": "first instruction of the mode keys' key function jumps to the hook"},
        ],
        "hooks": [
            {"site": f"{KEY_HOOK:#010X}".replace("0X", "0x"), "kind": "instruction", "chain": "mode-key", "position": "before", "swallow": True,
             "note": "SHIFT + PART ERASE rolls the selected part and does not reach the firmware; every other press of a mode key does"},
        ],
        "startPhase": [],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: DC_SETTING at +0 for a menu page, the generator's state, the notes the scale gives", "tools/patch/dice.py:STATE"),
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
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}, setting word {DC_SETTING:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
