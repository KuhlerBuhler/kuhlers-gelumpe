"""Builds the pad colour patch for firmware 2.02 (Hacktribe and Korg's build): the pads' red and blue get colours of the user's choice.

The firmware lights a pad with two LEDs, red (0x2C + 2n) and blue (0x2D + 2n). Red is what the pad shows (the part plays, the
pad is held, a step), blue the selected part; both together are pink. The patch sends other LEDs for the same meaning:

    PART colour      what the firmware shows in red: red, blue or pink
    SELECT colour    what it shows in blue: red, blue or pink, never the PART colour
    both at once     the colour that is left (pink pads and a blue cursor overlap in red)

The firmware's own values stay as they are (the LED manager's first table and its copy); only what goes to the panel changes, at
the one place every LED message passes (0xC00876A8, the end of 0xC00875F4, branch to the sender 0xC0087578). When one LED of a pad
changes, the other may have to change too (it takes the overlap colour or gives it back), so the hook sends that one as well.
With the default colours (red, blue), EXIT held at power-on or no setting written, nothing is changed. Nothing goes to flash.

Power save: while the firmware dims the backlight (its flag 0xC00F9310, set by 0xC0028AB4), every LED goes out at a quarter
of its brightness (the panel takes levels: the plugin Pulsieren pulses smoothly on the device, 18.10.). The hook at the start
of 0xC0028AB4 runs the firmware's function and sends every LED again when the state changed, so the pads dim and come back
at once. With EXIT held at power-on nothing of this happens.

    python3 tools/patch/pad_colors.py --vsb SYSTEM.VSB [--out data/patches/pad-colors.json]
    python3 tools/patch/pad_colors.py --vsb BLUE.VSB --build synth [--out data/patches/pad-colors-synth.json]

The blue Electribe 2 (the synth) has the same LED manager and the same power save switch, instruction for instruction
(data/synth-map/pad-colors.json); its build uses those places and keeps the code and the state where they are.
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

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC018B000            # free (FF) in the image, behind the dice (0xC018A000 to 0xC018B000)
CODE_END = 0xC018B800
STATE = 0xC018BF00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC018BF40
S_SETTING, S_SENT = 0, 0x10     # the setting word; 32 bytes: the brightness last sent for each pad LED
PC_SETTING = STATE + S_SETTING  # the BLECH menu writes PART | SELECT << 4 (0 red, 1 blue, 2 pink); FFFFFFFF never written
RED, BLUE, PINK = 0, 1, 2

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)

SEND_TAIL = 0xC00876A8          # b 0xC0087578: the end of the LED manager's send function, the message is built
SEND_TAIL_WORD = 0xEAFFFFB2
SENDER = 0xC0087578             # (sender object, message): sends message[0] (LED) with brightness message[2] to the panel
DIM_SWITCH = 0xC0028AB4         # (dim): the firmware's power save switch, ldr r3, [pc, #0x44] (its flag 0xC00F9310)
DIM_SWITCH_WORD = 0xE59F3044
DIM_BODY = 0xC0028AB8           # the rest of it: sets the flag and returns, or clears it and lights the backlight
S_DIM = 0x38                    # the power save state the LEDs were last sent for
S_PEND = 0x3C                   # 1: every LED is due to go out again, from the next LED message of the firmware on (pc_tail)
DIM_FLAG = 0xC00F9310           # byte: not 0 while the firmware dims for power save (the literal behind the switch)
FIRMWARE_PLACES = ["SEND_TAIL", "SENDER", "DIM_SWITCH", "DIM_BODY", "DIM_FLAG"]
BUILD = "hacktribe"


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); the code and the state stay where they are."""
    global BUILD
    BUILD = build
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ KNOB_LAST, 4             ; LEDs 0 to 4: the five knob LEDs (docs/messungen/2026-10-13-led-inventur.md)
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ SENDER, @SENDER@
.equ MSG_AT, 0xB4C              ; manager + 0xB4C: the message {LED, flag, brightness}; + 0xB54 the sender object
.equ SENDOBJ_AT, 0xB54
.equ LED_VALUE, 0x4E            ; manager + 0x4E + 8 * led: the brightness the firmware wants
.equ LED_PAD_FIRST, 0x2C
.equ KILL, @KILL@
.equ STATE, @STATE@
.equ S_SETTING, @S_SETTING@
.equ S_SENT, @S_SENT@
.equ S_MSG, 0x30                ; our own message for the other LED of a pad
.equ S_DIM, @S_DIM@             ; the power save state the LEDs were last sent for (FF at start)
.equ S_PEND, @S_PEND@           ; 1 while every LED is due to go out again (set at start, done by the next pass through pc_tail)
.equ MGR, 0xC03404C0            ; pointer to the screen manager, +0x2C the screen that is up (1 the main screen)
.equ LED_MODE_AT, 0x4F          ; manager + 0x4F + 8 * led: the second byte of the message
.equ METER_FIRST, 0x4C          ; the bottom RGB LEDs 0x4C to 0x57: the meter's own, not sent again here
.equ DIM_FLAG, 0xC00F9310       ; byte: not 0 while the firmware dims the backlight for power save
.equ DIM_BODY, @DIM_BODY@
.equ LED_COUNT, 0x58            ; LEDs 0 to 87

.equ LEDMGR_PTR, 0xC0345A1C
.equ LED_SEND, 0xC00875F4       ; (manager, led, force)

.org @CODE_AT@
; ===================================================== the BLECH menu's entries (script_menu.s, PC_CODE)
    b pc_from_look              ; +0  (look word of the settings file): the colours from bits 2 to 3 and 29 to 30
    b pc_to_look                ; +4  -> those bits for the current colours
    b pc_step                   ; +8  (kind 24 PAD COLOR or 25 SELECT COLOR, steps of the dial): the next colour
    b pc_texts                  ; +12 (kind) -> r0 = title, r1 = the colour's name

; -> r0 = PART, r1 = SELECT; never written (or nonsense) is red and blue. Clobbers r12.
pc_colours:
    ldr r12, =STATE
    ldr r12, [r12, #S_SETTING]
    and r0, r12, #15
    mov r1, r12, lsr #4
    and r1, r1, #15
    cmp r0, #2
    cmpls r1, #2
    bhi pcc_default
    cmp r0, r1
    bxne lr
pcc_default:
    mov r0, #0
    mov r1, #1
    bx lr

; r0 = PART, r1 = SELECT: stored only. At start (the settings file) nothing may be sent yet: on the synth the menu reads the
; settings before the LED manager runs, and a send from there never came back (emulator, 18.10.); the firmware sends the pads
; itself once its screen is up, through pc_tail and so in these colours. Keeps r1 to r11.
pc_set:
    orr r0, r0, r1, lsl #4
    ldr r12, =STATE
    str r0, [r12, #S_SETTING]
    mov r0, #1
    str r0, [r12, #S_PEND]
    bx lr

; r0 = PART, r1 = SELECT: stored, and every pad LED sent again (a page of the menu changed them). Keeps r4 to r11.
pc_store:
    push {r4, r5, lr}
    orr r0, r0, r1, lsl #4
    ldr r12, =STATE
    str r0, [r12, #S_SETTING]
    ldr r4, =LEDMGR_PTR
    ldr r4, [r4]
    cmp r4, #0
    beq pcs_out
    mov r5, #LED_PAD_FIRST
pcs_led:
    mov r0, r4
    mov r1, r5
    mov r2, #1
    bl LED_SEND
    add r5, r5, #1
    cmp r5, #LED_PAD_FIRST + 32
    blo pcs_led
pcs_out:
    pop {r4, r5, pc}

; SELECT in the file is 0 blue, 1 red, 2 pink, so that a file without it (0) is the firmware's blue
pc_from_look:
    mov r1, r0, lsr #29
    and r1, r1, #3
    ldr r2, =sel_from_file
    ldrb r1, [r2, r1]
    mov r0, r0, lsr #2
    and r0, r0, #3
    cmp r0, #2
    movhi r0, #0
    cmp r0, r1
    moveq r0, #0
    moveq r1, #1
    b pc_set

pc_to_look:
    push {lr}
    bl pc_colours
    ldr r2, =sel_from_file      ; the table is its own inverse
    ldrb r1, [r2, r1]
    mov r0, r0, lsl #2
    orr r0, r0, r1, lsl #29
    pop {pc}

pc_step:
    push {r4, r5, r6, lr}
    mov r4, r0
    cmp r1, #0
    movgt r5, #1
    movle r5, #2                ; down is two steps up, modulo 3
    bl pc_colours
    cmp r4, #24
    moveq r6, r0                ; the colour that moves
    movne r6, r1
    moveq r3, r1                ; the one it may not take
    movne r3, r0
    add r6, r6, r5
    cmp r6, #3
    subhs r6, r6, #3
    cmp r6, r3
    addeq r6, r6, r5
    cmp r6, #3
    subhs r6, r6, #3
    cmp r4, #24
    moveq r0, r6
    movne r1, r6
    bl pc_store
    pop {r4, r5, r6, pc}

pc_texts:
    push {r4, lr}
    mov r4, r0
    bl pc_colours
    cmp r4, #24
    movne r0, r1
    ldr r2, =colour_names
    ldr r1, [r2, r0, lsl #2]
    cmp r4, #24
    ldreq r0, =str_pad
    ldrne r0, =str_select
    pop {r4, pc}

sel_from_file:
    .byte 1, 0, 2, 0
str_pad:
    .asciz "PAD COLOR"
str_select:
    .asciz "SELECT COLOR"
str_red:
    .asciz "RED"
str_blue:
    .asciz "BLUE"
str_pink:
    .asciz "PINK"
.align 4
colour_names:
    .word str_red, str_blue, str_pink

; r0 = the setting word when the colours are not the default and the patch is on, else -1. Clobbers r0 to r2 and r12.
pc_active:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq pa_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne pa_no
    ldr r12, =STATE
    ldr r0, [r12, #S_SETTING]
    and r1, r0, #15             ; PART
    mov r2, r0, lsr #4
    and r2, r2, #15             ; SELECT
    cmp r1, #2
    bhi pa_no
    cmp r2, #2
    bhi pa_no
    cmp r1, r2
    beq pa_no
    cmp r1, #0                  ; red and blue are what the firmware does
    cmpeq r2, #1
    beq pa_no
    and r0, r0, #0xFF
    bx lr
pa_no:
    mvn r0, #0
    bx lr

; r4 = manager, r8 = the red LED of a pad, r6 = setting -> r0 = red to send, r1 = blue to send. Clobbers r2, r3, r12.
pc_map:
    add r12, r4, r8, lsl #3
    ldrb r2, [r12, #LED_VALUE]          ; what the firmware wants in red
    ldrb r3, [r12, #LED_VALUE + 8]      ; and in blue
    and r0, r6, #15                     ; PART
    mov r1, r6, lsr #4                  ; SELECT
    cmp r2, #0
    beq pm_blue
    cmp r3, #0
    beq pm_part
    rsb r0, r0, #3                      ; both: the colour that is left, 3 - PART - SELECT
    sub r0, r0, r1
    cmp r3, r2
    movhi r2, r3                        ; brightness: the brighter of the two
    b pm_colour
pm_part:
    b pm_colour
pm_blue:
    cmp r3, #0
    moveq r0, #0
    beq pm_colour
    mov r0, r1
    mov r2, r3
pm_colour:                              ; r0 = colour, r2 = brightness
    mov r1, #0
    cmp r0, #1                          ; blue or pink: the blue LED
    movhs r1, r2
    cmp r0, #1                          ; red or pink: the red LED
    moveq r0, #0
    movne r0, r2
    bx lr

; -> r0 = 1 while the firmware dims for power save and EXIT was not held at power-on. Clobbers r12.
pc_dimming:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq pd_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne pd_no
    ldr r12, =DIM_FLAG
    ldrb r0, [r12]
    cmp r0, #0
    movne r0, #1
    bx lr
pd_no:
    mov r0, #0
    bx lr

; r2 = brightness -> r2 = a quarter of it, never 0 for a lit LED
pc_quarter:
    add r2, r2, #3
    mov r2, r2, lsr #2
    bx lr

; Entered by the branch at the end of the send function: r0 = sender object, r1 = message (manager + 0xB4C), lr = its caller.
pc_tail:
    push {r0, r1, r4, r5, r6, r7, r8, r9, lr}
    ldr r5, [sp, #4]
    bl pc_dimming
    mov r9, r0
    bl pc_active
    mov r6, r0
    ldr r12, =STATE
    ldr r0, [r12, #S_PEND]
    cmp r0, #1
    bne pt_message
    ldr r0, =MGR                        ; not before the main screen: during the start the panel queue does not take a whole round
    ldr r0, [r0]                        ; (on the synth the start hung, emulator 18.10.)
    cmp r0, #0
    beq pt_message
    ldr r0, [r0, #0x2C]
    cmp r0, #1
    bne pt_message
    mov r0, #0
    str r0, [r12, #S_PEND]
    bl pc_resend
pt_message:
    cmn r6, #1
    bne pt_colours
pt_dim_only:
    cmp r9, #0
    beq pt_stock
    ldrb r2, [r5, #2]
    ldrb r0, [r5]
    cmp r0, #KNOB_LAST          ; the LEDs of the knobs (VALUE, SAMPLE/OSC, CUTOFF, MOD TYPE, IFX TYPE) go out (device 18.10.)
    movls r2, #0
    blhi pc_quarter
    strb r2, [r5, #2]
    b pt_stock
pt_colours:
    sub r4, r5, #0xB40
    sub r4, r4, #0xC                    ; manager = message - 0xB4C
    ldrb r7, [r5]                       ; the LED
    sub r8, r7, #LED_PAD_FIRST
    cmp r8, #31
    bhi pt_dim_only
    bic r8, r8, #1
    add r8, r8, #LED_PAD_FIRST          ; the pad's red LED
    bl pc_map
    cmp r9, #0
    beq pt_mapped
    mov r2, r0
    bl pc_quarter
    mov r0, r2
    mov r2, r1
    bl pc_quarter
    mov r1, r2
pt_mapped:
    ldr r12, =STATE + S_SENT
    cmp r7, r8
    moveq r2, r0                        ; this LED's brightness
    movne r2, r1
    moveq r3, r1                        ; the other LED's
    movne r3, r0
    strb r2, [r5, #2]
    sub r0, r7, #LED_PAD_FIRST
    strb r2, [r12, r0]
    eor r7, r7, #1                      ; the other LED of the pad
    sub r0, r7, #LED_PAD_FIRST
    ldrb r1, [r12, r0]
    cmp r1, r3
    beq pt_send
    strb r3, [r12, r0]
    ldr r1, =STATE + S_MSG
    strb r7, [r1]
    strb r3, [r1, #2]
    ldr r0, [r4, #SENDOBJ_AT]
    bl SENDER
pt_send:
pt_stock:
    pop {r0, r1, r4, r5, r6, r7, r8, r9, lr}
    b SENDER

; Inside pc_tail (the firmware's own sending path, so from a task that may send): every LED but the meter's goes out again as the
; manager holds it, mapped and dimmed as pc_tail does. r5 = the message the firmware is sending, r6 = setting or -1, r9 = dimming.
; Keeps r5, r6, r9.
pc_resend:
    push {r4, r7, r8, r10, r11, lr}
    sub r4, r5, #0xB40
    sub r4, r4, #0xC                    ; manager = message - 0xB4C
    mov r10, #0
pr_led:
    cmp r10, #METER_FIRST               ; the meter's LEDs 0x4C to 0x57 are the last twelve
    bhs pr_out
    add r12, r4, r10, lsl #3
    ldrb r2, [r12, #LED_VALUE]          ; what the firmware wants
    ldrb r11, [r12, #LED_MODE_AT]
    sub r8, r10, #LED_PAD_FIRST
    cmp r8, #31
    bhi pr_dim
    cmn r6, #1
    beq pr_dim
    bic r8, r8, #1
    add r8, r8, #LED_PAD_FIRST          ; a pad: the colours, as pc_tail maps them
    bl pc_map
    cmp r10, r8
    moveq r2, r0
    movne r2, r1
pr_dim:
    cmp r9, #0
    blne pc_quarter
    sub r8, r10, #LED_PAD_FIRST
    cmp r8, #31
    ldrls r12, =STATE + S_SENT
    strbls r2, [r12, r8]
    ldr r1, =STATE + S_MSG
    strb r10, [r1]
    strb r11, [r1, #1]
    strb r2, [r1, #2]
    ldr r0, [r4, #SENDOBJ_AT]
    bl SENDER
    add r10, r10, #1
    b pr_led
pr_out:
    pop {r4, r7, r8, r10, r11, pc}

; Replaces the first instruction of the firmware's power save switch (r0 = 1 dim, 0 not): runs the function, then sends
; every LED again when the dimming changed, so they take or leave the quarter brightness at once.
pc_dim_switch:
    push {r4, r5, lr}
    ldr r3, =DIM_FLAG                   ; the replaced instruction loads this literal
    bl DIM_BODY
    bl pc_dimming
    ldr r12, =STATE
    ldr r1, [r12, #S_DIM]
    cmp r0, r1
    beq pds_out
    str r0, [r12, #S_DIM]
    cmn r1, #1                          ; the first call (FF) comes during the start: nothing is sent from here (on the synth a send
    moveq r1, #1                        ; from there never came back, 18.10.); the next LED message of the firmware sends them all again
    streq r1, [r12, #S_PEND]
    beq pds_out
    ldr r4, =LEDMGR_PTR
    ldr r4, [r4]
    cmp r4, #0
    beq pds_out
    mov r5, #0
pds_led:
    mov r0, r4
    mov r1, r5
    mov r2, #1
    bl LED_SEND
    add r5, r5, #1
    cmp r5, #LED_COUNT
    blo pds_led
pds_out:
    pop {r4, r5, pc}

.align 4
lit_pool:
.pool
"""


def source():
    """The assembler text. For the synth the firmware's places are written as the Sampler's and translated as a whole (synthaddr.source)."""
    sampler = globals().get("_SAMPLER_ADDRESSES", {})
    place = lambda name: sampler.get(name, globals()[name])
    text = SOURCE
    for key, value in {"KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}", "S_SETTING": S_SETTING,
                       "S_SENT": S_SENT, "SENDER": f"{place('SENDER'):#x}", "S_DIM": f"{S_DIM:#x}", "DIM_BODY": f"{place('DIM_BODY'):#x}",
                       "S_PEND": f"{S_PEND:#x}"}.items():
        text = text.replace(f"@{key}@", str(value))
    if BUILD == "synth":
        text = synthaddr.source(text, own=[(CODE_AT, CODE_END), (STATE, STATE_END)])
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target):
    return struct.pack("<I", 0xEA000000 | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb, build="hacktribe"):
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

    if struct.unpack("<I", was(SEND_TAIL, 4))[0] != SEND_TAIL_WORD:
        raise SystemExit("the LED manager's send function does not end with b 0xC0087578 in this VSB")
    if struct.unpack("<I", was(DIM_SWITCH, 4))[0] != DIM_SWITCH_WORD or struct.unpack("<I", was(DIM_SWITCH + 0x4C, 4))[0] != DIM_FLAG:
        raise SystemExit(f"the power save switch {DIM_SWITCH:#x} does not load the flag {DIM_FLAG:#x} in this VSB")
    free(STATE, STATE_END - STATE)
    return {
        "format": "gelumpe-patch", "version": 1, "id": "pad-colors", "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "name": "Eigene Farben für die Pads: Part und Auswahl in Rot, Blau oder Pink (PAD COLORS); im Energiesparmodus alle LEDs gedimmt",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "pad colours: the hook at the end of the LED send function, and what the BLECH menu writes (PC_SETTING)"},
            {"file": file_offset(SEND_TAIL), "bytes": branch(SEND_TAIL, symbols["pc_tail"]).hex(), "expect": sha(was(SEND_TAIL, 4)),
             "note": "the branch to the sender at the end of the LED send function goes through the hook"},
            {"file": file_offset(DIM_SWITCH), "bytes": branch(DIM_SWITCH, symbols["pc_dim_switch"]).hex(), "expect": sha(was(DIM_SWITCH, 4)),
             "note": "the power save switch goes through the hook, which sends the LEDs again when the dimming changes"},
        ],
        "hooks": [
            {"site": f"{SEND_TAIL:#010X}".replace("0X", "0x"), "kind": "instruction", "chain": "led-send", "position": "replace", "swallow": False,
             "note": "sends a pad LED in the chosen colour, and the other LED of the pad when it has to change with it; every LED at a quarter while power save dims"},
            {"site": f"{DIM_SWITCH:#010X}".replace("0X", "0x"), "kind": "instruction", "chain": "backlight", "position": "replace", "swallow": False,
             "note": "runs the firmware's power save switch, then sends every LED again when the dimming changed"},
        ],
        "startPhase": [
            {"file": file_offset(SEND_TAIL), "length": 4, "why": "every LED message from the start on now passes pc_tail"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "pc_tail, pc_active and pc_dimming: at start they look at the panel object, the kill switch, the setting word (FF until the menu writes it) and the power save flag; on battery with power save the LEDs go out at a quarter from the start, as the backlight is dimmed from the start"},
            {"file": file_offset(DIM_SWITCH), "length": 4, "why": "the firmware sets power save at start too; the hook runs its function and sends the LEDs again when the dimming changed"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: PC_SETTING at +0 for the BLECH menu, the brightness sent for each pad LED, a message, the power save state last sent", "tools/patch/pad_colors.py:STATE"),
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
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}, setting word {PC_SETTING:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
