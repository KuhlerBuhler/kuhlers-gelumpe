"""Builds the TAP motion patch (docs/messungen/2026-10-15-tap-motion-patch.md, docs/ideen/39-automationen-tap.md) for firmware 2.02 with Hacktribe.

REC records knob movements and Master FX gestures into the pattern, as always. TAP then switches the recorded
motion of the selected part on and off, at once and without waiting for the bar, the way Gross Beat does:

    TAP                 the Motion Sequence of the selected part: on (the mode it had, Smooth when it never had one)
                        or off (the part's mode byte 0)
    MASTER FX + TAP     the Motion Sequence of the Master FX lanes (the pattern byte 0x44, found as their switch);
                        TOUCH SCALE + TAP the same, for MFX 2 on TOUCH SCALE (mfx-switch.json)
    TAP LED             lit while that motion is on, dark while it is off; the part that is selected counts, and
                        while MASTER FX is held the LED shows the Master FX motion instead. While the Master FX motion
                        is on and a lane holds a Master FX gesture (MASTER FX not held) the LED blinks: half on, half off with the part's motion off,
                        on with a short dark gap with it on (period BLINK_TICKS of the 40 ms tick)

The firmware's tap tempo is gone while the patch is on. SHIFT + TAP stays the firmware's (the Pattern menu on the page
BPM). The patch is on only when EXIT was not held at power-on, a card was seen since power-on and the setting word TM_SETTING is not
0 (the BLECH menu page TAP MOTION writes it; never written means on). With TM_SETTING 2 (ONCE) a motion TAP switched on
goes off by itself when its part's step counter comes back to the start: it plays to the end of the pattern once.

    python3 tools/patch/tap_motion.py --vsb SYSTEM.VSB [--out data/patches/tap-motion.json]

Three hooks, none of them before the main screen:
  TAP        0xC0042CC0, the instruction right where the key handler is about to call the tap tempo calculation, after
             the firmware has checked every condition for it (key down, SHIFT not held, the screens where TAP is live)
  beat flash 0xC00881E0, the function that flashes the TAP LED on every beat; while the patch is on it does nothing
  LED tick   0xC0087740, the 40 ms task of the LED manager; keeps LED 0x14 as wanted, through the firmware's own path
             (0xC0087710, which sets the manager's entry and sends it), and gives the LED back when the patch goes off

The part's mode is set with the firmware's own setter 0xC0049410 (the one the Part menu calls), so the byte and its
second copy 0x382E further stay the same, with no notification. The Master FX byte has no setter and is written as it
is. Nothing of the firmware is copied and nothing is written to flash or to the card.
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

CODE_AT = 0xC0188000            # free (FF) in the image, behind the block of Blechy (0xC0184000 to 0xC0188000)
CODE_END = 0xC0188800
STATE = 0xC0188F00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC0188F40
S_SETTING, S_LED, S_PATNUM, S_LAST, S_MFXLAST, S_ONCE, S_STEPS, S_BLINK = 0, 4, 8, 0x10, 0x20, 0x24, 0x28, 0x3A
BLINK_TICKS, BLINK_HALF, BLINK_LONG = 12, 6, 10   # 480 ms: on for 6 ticks (part off) or 10 ticks (part on)
TM_SETTING = STATE + S_SETTING  # the setting word the BLECH menu writes: never written (FFFFFFFF) or 1 is on, 0 is off, 2 once

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)

TAP_HOOK = 0xC0042CC0           # ldr r0, [pc, #0x16c] right before the call of the tap tempo calculation
TAP_WORD = 0xE59F016C
TAP_BODY = 0xC0042CC4
TAP_EXIT = 0xC0042E18
TAP_LITERAL = 0xC0340358        # what the replaced instruction loads: the tap tempo calculation's object
TAP_LITERAL_AT = 0xC0042E34     # where the pool of the key handler holds it
TAP_CALL_WORD = 0xEBFFA29D      # the bl behind the hook (pc relative, so it differs in the synth)
TAP_EXIT_WORD = 0xE28DD014      # add sp, sp, #0x14
BEAT_HOOK = 0xC00881E0          # ldrb r2, [r0, #0xba4]
BEAT_WORD = 0xE5D02BA4
BEAT_BODY = 0xC00881E4
TICK_HOOK = 0xC0087740          # push {r4, r5, r6, lr}
TICK_WORD = 0xE92D4070
TICK_BODY = 0xC0087744
FRAME_CALL = 0xC00836F0         # bl 0xC006EAE0 in the screen manager's frame, in the UI task (where TAP is handled too)
FRAME_FUNC = 0xC006EAE0


# What the hook sites must hold, per build: the Sampler's words, and the synth's where a pc relative offset differs.
# The synth's key handler is the same code with a frame 4 bytes smaller (it does not keep r7): its literal pool is 8 bytes nearer
# (ldr r0, [pc, #0x164] instead of #0x16c) and its exit is add sp, sp, #0x10; pop {r4, r5, r6, pc}.
FIRMWARE_PLACES = ["TAP_HOOK", "TAP_BODY", "TAP_EXIT", "TAP_LITERAL", "TAP_LITERAL_AT", "BEAT_HOOK", "BEAT_BODY", "TICK_HOOK", "TICK_BODY", "FRAME_CALL", "FRAME_FUNC"]
BUILD = "hacktribe"


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); the code and the state stay where they are."""
    global BUILD, TAP_WORD, TAP_CALL_WORD, TAP_EXIT_WORD
    BUILD = build
    synthaddr.use(globals(), FIRMWARE_PLACES, build)
    TAP_WORD = 0xE59F0164 if build == "synth" else 0xE59F016C
    TAP_CALL_WORD = 0xEBFFADA2 if build == "synth" else 0xEBFFA29D
    TAP_EXIT_WORD = 0xE28DD010 if build == "synth" else 0xE28DD014      # the synth's handler has a frame of 0x10 and pops r4 to r6


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ FATFS, 0xC06A010C          ; FatFs volume table: first entry is the volume of the card, its byte 0 is the mounted type
.equ PATPTR, 0xC033E6A4         ; the pattern object
.equ MOTION_THIS, 0xC0348900    ; the object the part setters work on (+4 the pattern)
.equ MOTION_SET, 0xC0049410     ; (this, part, mode, notify): the part's Motion Sequence mode, as the Part menu sets it
.equ HW_PART, 0xC06B2428        ; the selected part, 0 to 15
.equ HW_PATTERN, 0xC06B2420     ; the pattern number
.equ KEYS, 0xC06BCA70           ; the UI task's key states, 8 bytes per key, the word is not 0 while the key is held
.equ KEY_MASTER_FX, 6
.equ KEY_TOUCH_SCALE, 5         ; MFX 2 with mfx-switch.json
.equ HW_TRANSPORT, 0xC06BC318   ; 0 while the sequencer stands
.equ HW_STEP, 0xC06904B0        ; part n's step counter at + 0x48 * n
.equ PAD_STATE, 0xC068D074      ; the Master FX pad state the effect was last given
.equ PAD_SET, 0xC0057C28        ; (on): the pad on or off through the effect's setter
.equ LED_SET, 0xC0087710        ; (manager, led, mode, duration): the manager's own path to set an LED and send it
.equ LED_TAP, 0x14
.equ LED_MODE, 0xED             ; manager + 0x4c + 8 * 0x14 + 1: the mode byte of the TAP LED
.equ MODE_BYTE, 0x807           ; part n: pattern + 0x807 + 0x330 * n
.equ MFX_BYTE, 0x44             ; the Master FX lanes' mode, same values as the part's
.equ MFX_TOUCH, 0x40            ; 1 while a finger is on the pad
.equ LANE_PART, 0x104           ; the part of each of the 24 motion lanes (0 none, 1 to 16 the part, 17 Master FX)
.equ LANES, 24
.equ LANE_MFX, 17
.equ KILL, @KILL@
.equ STATE, @STATE@
.equ S_SETTING, @S_SETTING@     ; TM_SETTING: FFFFFFFF or 1 is on, 0 is off
.equ S_LED, @S_LED@             ; 1 while the patch has taken the TAP LED over
.equ S_PATNUM, @S_PATNUM@       ; the pattern number the remembered modes belong to
.equ S_LAST, @S_LAST@           ; 16 bytes: the mode each part had before it was switched off (0 nothing remembered)
.equ S_MFXLAST, @S_MFXLAST@     ; the same for the Master FX lanes
.equ S_ONCE, @S_ONCE@           ; ONCE: bit n part n plays to its end and goes off, bit 16 the Master FX lanes (on part 1's counter)
.equ S_STEPS, @S_STEPS@         ; 17 bytes: the step counter last seen for each of those
.equ S_BLINK, @S_BLINK@         ; byte: the tick within the blink of the TAP LED while the Master FX motion is on
.equ BLINK_TICKS, @BLINK_TICKS@
.equ BLINK_HALF, @BLINK_HALF@
.equ BLINK_LONG, @BLINK_LONG@
.equ TAP_BODY, @TAP_BODY@
.equ TAP_EXIT, @TAP_EXIT@
.equ TAP_LITERAL, @TAP_LITERAL@
.equ BEAT_BODY, @BEAT_BODY@
.equ TICK_BODY, @TICK_BODY@
.equ FRAME_FUNC, @FRAME_FUNC@

.org @CODE_AT@

; ===================================================== is the patch on
; r0 = 1 when EXIT was not held at power-on, a card was seen since power-on and the setting is not off. Clobbers r0 and r12.
; Writes only the card latch (tools/patch/card_gate.py), the first time a card is there.
tm_active:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq ta_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne ta_no
@CARD_CHECK@    ldr r12, =STATE
    ldr r12, [r12, #S_SETTING]
    cmp r12, #0
    movne r0, #1
    bxne lr
ta_no:
    mov r0, #0
    bx lr

; r2 = the mode now, r7 = where the last mode that was on is kept -> r2 = the mode to set.
; Going off remembers the mode. Going on gives it back; nothing remembered (or anything but 1 and 2) is Smooth,
; the firmware's default for a pattern and for a part whose motion was recorded.
tm_next:
    cmp r2, #0
    beq tn_on
    strb r2, [r7]
    mov r2, #0
    bx lr
tn_on:
    ldrb r2, [r7]
    sub r3, r2, #1
    cmp r3, #1
    movhi r2, #1
    bx lr

; ===================================================== TAP
; Runs where the key handler is about to call the tap tempo calculation: key down, no SHIFT, a screen where TAP is live.
; Registers of the handler are saved here. With the patch on the calculation is not called: the motion is switched.
tap_hook:
    push {r0, r1, r2, r3, r12, lr}
    bl tm_active
    cmp r0, #0
    beq th_stock
    bl tm_toggle
    pop {r0, r1, r2, r3, r12, lr}
    b TAP_EXIT
th_stock:
    pop {r0, r1, r2, r3, r12, lr}
    ldr r0, =TAP_LITERAL        ; the replaced instruction
    b TAP_BODY

; r0 = 1 while MASTER FX or TOUCH SCALE (MFX 2) is held. Clobbers r0 and r12.
tm_mfx_held:
    ldr r12, =KEYS
    ldr r0, [r12, #8 * KEY_MASTER_FX]
    cmp r0, #0
    ldreq r0, [r12, #8 * KEY_TOUCH_SCALE]
    cmp r0, #0
    movne r0, #1
    bx lr

; r6 = part (16 the Master FX lanes), r2 = the mode just set. With the setting ONCE a motion going on is marked to go
; off at its end, one going off is unmarked. Clobbers r0 to r3 and r12.
tm_mark:
    ldr r12, =STATE
    ldr r0, [r12, #S_ONCE]
    mov r1, #1
    mov r1, r1, lsl r6
    bic r0, r0, r1
    cmp r2, #0
    beq tm_mark_store
    ldr r3, [r12, #S_SETTING]
    cmp r3, #2
    bne tm_mark_store
    orr r0, r0, r1
    and r3, r6, #15
    mov r1, #0x48
    mul r1, r3, r1
    ldr r3, =HW_STEP
    ldr r1, [r3, r1]
    add r3, r12, #S_STEPS
    strb r1, [r3, r6]
tm_mark_store:
    str r0, [r12, #S_ONCE]
    bx lr

tm_toggle:
    push {r4, r5, r6, r7, lr}
    ldr r4, =PATPTR
    ldr r4, [r4]
    cmp r4, #0
    beq tt_out
    ldr r5, =STATE
    bl tm_mfx_held
    cmp r0, #0
    bne tt_mfx
    ldr r6, =HW_PART
    ldr r6, [r6]
    cmp r6, #15
    bhi tt_out                  ; no part selected: nothing to switch
    mov r0, #0x330
    mul r1, r6, r0
    add r1, r4, r1
    ldrb r2, [r1, #MODE_BYTE]
    add r7, r5, #S_LAST
    add r7, r7, r6
    bl tm_next
    ldr r0, =MOTION_THIS
    ldr r0, [r0]
    cmp r0, #0
    beq tt_out
    mov r1, r6
    mov r7, r2
    mov r3, #0                  ; no notification, TAP is a performance switch
    bl MOTION_SET
    mov r2, r7
    bl tm_mark
    b tt_out
tt_mfx:
    ldrb r2, [r4, #MFX_BYTE]
    add r7, r5, #S_MFXLAST
    bl tm_next
    mov r6, #16
    bl tm_mfx_set
tt_out:
    pop {r4, r5, r6, r7, pc}

; r4 = pattern, r2 = the Master FX lanes' new mode, r6 = 16. Clobbers r0 to r3 and r12.
tm_mfx_set:
    push {lr}
    strb r2, [r4, #MFX_BYTE]
    bl tm_mark
    ldrb r2, [r4, #MFX_BYTE]
    cmp r2, #0
    bne tms_out
    ldr r0, =PAD_STATE          ; switched off in the middle of a gesture: the lane that would have let the pad go
    ldr r0, [r0]                ; never comes, so the pad is let go here (unless a finger is on it)
    cmp r0, #0
    beq tms_out
    ldrb r0, [r4, #MFX_TOUCH]
    cmp r0, #0
    bne tms_out
    mov r0, #0
    bl PAD_SET
tms_out:
    pop {pc}

; ONCE, every frame of the UI task (the call at FRAME_CALL goes through here, after the call it replaces): the motions are switched
; off in the task that handles TAP, so letting the Master FX pad go works as with TAP (from the LED task the effect stayed on, device 17.10.).
frame_hook:
    push {r0, r1, r2, r3, r4, r5, r12, lr}
    bl FRAME_FUNC
    bl tm_active
    cmp r0, #0
    beq fh_out
    ldr r4, =PATPTR
    ldr r4, [r4]
    cmp r4, #0
    blne tm_once
fh_out:
    pop {r0, r1, r2, r3, r4, r5, r12, pc}

; ONCE: a marked motion whose step counter went back (the pattern started over) goes off, as TAP would switch it.
; While the sequencer stands the counters are not compared, and the last ones seen are 0. r4 = pattern.
tm_once:
    push {r4, r5, r6, r7, r8, lr}
    ldr r5, =STATE
    ldr r8, [r5, #S_ONCE]
    cmp r8, #0
    beq to_out
    ldr r0, =HW_TRANSPORT
    ldr r0, [r0]
    mov r6, #0
to_part:
    mov r1, #1
    tst r8, r1, lsl r6
    beq to_next
    add r7, r5, #S_STEPS
    cmp r0, #0
    moveq r1, #0
    strbeq r1, [r7, r6]
    beq to_next
    and r3, r6, #15
    mov r1, #0x48
    mul r1, r3, r1
    ldr r3, =HW_STEP
    ldr r1, [r3, r1]
    ldrb r2, [r7, r6]
    strb r1, [r7, r6]
    cmp r1, r2
    bhs to_next
    push {r0}
    cmp r6, #16
    beq to_mfx
    mov r0, #0x330
    mul r1, r6, r0
    add r1, r4, r1
    ldrb r2, [r1, #MODE_BYTE]
    add r7, r5, #S_LAST
    add r7, r7, r6
    bl tm_next
    ldr r0, =MOTION_THIS
    ldr r0, [r0]
    cmp r0, #0
    beq to_done
    mov r1, r6
    mov r3, #0
    bl MOTION_SET
    mov r2, #0
    bl tm_mark
    b to_done
to_mfx:
    ldrb r2, [r4, #MFX_BYTE]
    add r7, r5, #S_MFXLAST
    bl tm_next
    bl tm_mfx_set
to_done:
    pop {r0}
    ldr r8, [r5, #S_ONCE]
to_next:
    add r6, r6, #1
    cmp r6, #17
    blo to_part
to_out:
    pop {r4, r5, r6, r7, r8, pc}

; ===================================================== the beat flash of the TAP LED
; First instruction of the function the sequencer calls on every beat to flash LED 0x14 (r0 = the LED manager).
; With the patch on the LED belongs to the tick below, so there is no flash.
beat_hook:
    push {r0, r1, r2, r3, lr}
    bl tm_active
    cmp r0, #0
    pop {r0, r1, r2, r3, lr}
    bne bh_mine
    ldrb r2, [r0, #0xba4]       ; the replaced first instruction
    b BEAT_BODY
bh_mine:
    bx lr

; ===================================================== the LED, every 40 ms
; First instruction of the manager's tick (r0 = the manager). Before the tick runs, the TAP LED is brought to what
; the selected part's motion (or Master FX's, while MASTER FX is held) says: mode 1, steady on, or mode 0, off.
; While the Master FX motion is on, a lane holds a Master FX gesture (byte 1 alone is the default of every new pattern) and
; MASTER FX is not held, it blinks, so it shows without a key held: BLINK_HALF of BLINK_TICKS on with the part's motion off,
; BLINK_LONG of them with it on.
; The manager's entry is compared first, so nothing is sent while it is right. When the patch goes off, the LED is let go.
; A change of the pattern forgets the modes remembered for the parts.
tick_hook:
    push {r0, r1, r2, r3, r4, r5, r6, r7, r8, r12, lr}
    mov r8, r0
    ldr r5, =STATE
    bl tm_active
    cmp r0, #0
    beq tk_release
    ldr r0, =HW_PATTERN
    ldr r0, [r0]
    ldr r1, [r5, #S_PATNUM]
    cmp r0, r1
    beq tk_state
    str r0, [r5, #S_PATNUM]
    mov r1, #0
    str r1, [r5, #S_LAST]
    str r1, [r5, #S_LAST + 4]
    str r1, [r5, #S_LAST + 8]
    str r1, [r5, #S_LAST + 12]
    str r1, [r5, #S_MFXLAST]
    str r1, [r5, #S_ONCE]
tk_state:
    mov r6, #0
    ldr r4, =PATPTR
    ldr r4, [r4]
    cmp r4, #0
    beq tk_set
    bl tm_mfx_held
    cmp r0, #0
    beq tk_part
    ldrb r6, [r4, #MFX_BYTE]
    b tk_set
tk_part:
    ldr r0, =HW_PART
    ldr r0, [r0]
    cmp r0, #15
    bhi tk_blink
    mov r1, #0x330
    mul r2, r0, r1
    add r2, r4, r2
    ldrb r6, [r2, #MODE_BYTE]
tk_blink:
    ldrb r0, [r4, #MFX_BYTE]
    cmp r0, #0
    beq tk_set
    add r1, r4, #LANE_PART
    mov r2, #LANES
tk_lane:
    ldrb r3, [r1], #1
    cmp r3, #LANE_MFX
    beq tk_blink_on
    subs r2, r2, #1
    bne tk_lane
    b tk_set
tk_blink_on:
    ldrb r1, [r5, #S_BLINK]
    add r1, r1, #1
    cmp r1, #BLINK_TICKS
    movhs r1, #0
    strb r1, [r5, #S_BLINK]
    cmp r6, #0
    movne r2, #BLINK_LONG
    moveq r2, #BLINK_HALF
    cmp r1, r2
    movlo r6, #1
    movhs r6, #0
tk_set:
    cmp r6, #0
    movne r6, #1
    ldr r0, [r5, #S_LED]        ; the first time the patch has the LED it is sent whatever the manager's entry says:
    cmp r0, #1                  ; the entry starts as mode 1 while the panel has been told dark
    bne tk_send
    ldrb r0, [r8, #LED_MODE]
    cmp r0, r6
    beq tk_owned
tk_send:
    mov r0, r8
    mov r1, #LED_TAP
    mov r2, r6
    mov r3, #0
    bl LED_SET
tk_owned:
    mov r0, #1
    str r0, [r5, #S_LED]
    b tk_out
tk_release:
    ldr r0, [r5, #S_LED]
    cmp r0, #1
    bne tk_out
    mov r0, #0
    str r0, [r5, #S_LED]
    mov r0, r8
    mov r1, #LED_TAP
    mov r2, #0
    mov r3, #0
    bl LED_SET
tk_out:
    pop {r0, r1, r2, r3, r4, r5, r6, r7, r8, r12, lr}
    push {r4, r5, r6, lr}       ; the replaced first instruction
    b TICK_BODY

.align 4
lit_pool:
.pool
"""


def source():
    """The assembler text. For the synth the firmware's places are written as the Sampler's and translated as a whole (synthaddr.source)."""
    sampler = globals().get("_SAMPLER_ADDRESSES", {})
    place = lambda name: sampler.get(name, globals()[name])
    text = SOURCE.replace("@CARD_CHECK@", card_gate.source(BUILD, "ta_no", STATE + card_gate.LATCH_OFFSET))
    for key, value in {
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}",
        "S_SETTING": S_SETTING, "S_LED": S_LED, "S_PATNUM": S_PATNUM, "S_LAST": S_LAST, "S_MFXLAST": S_MFXLAST, "S_ONCE": S_ONCE, "S_STEPS": S_STEPS,
        "S_BLINK": S_BLINK, "BLINK_TICKS": BLINK_TICKS, "BLINK_HALF": BLINK_HALF, "BLINK_LONG": BLINK_LONG,
        "TAP_BODY": f"{place('TAP_BODY'):#x}", "TAP_EXIT": f"{place('TAP_EXIT'):#x}", "TAP_LITERAL": f"{place('TAP_LITERAL'):#x}",
        "BEAT_BODY": f"{place('BEAT_BODY'):#x}", "TICK_BODY": f"{place('TICK_BODY'):#x}", "FRAME_FUNC": f"{place('FRAME_FUNC'):#x}",
    }.items():
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


def bl(at, target):
    return branch(at, target, link=True)


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

    expected = (
        (TAP_HOOK, TAP_WORD, "the key handler does not load the tap tempo calculation's object where the patch expects it"),
        (BEAT_HOOK, BEAT_WORD, "the TAP LED beat flash does not start with ldrb r2, [r0, #0xba4]"),
        (TICK_HOOK, TICK_WORD, "the LED manager's tick does not start with push {r4, r5, r6, lr}"),
    )
    for addr, want, why in expected:
        if word(addr) != want:
            raise SystemExit(f"{why} in this VSB")
    if word(FRAME_CALL) != struct.unpack("<I", bl(FRAME_CALL, FRAME_FUNC))[0]:
        raise SystemExit("the screen manager's frame does not call 0xC006EAE0 where the patch expects it in this VSB")
    if word(TAP_BODY) != TAP_CALL_WORD or word(TAP_EXIT) != TAP_EXIT_WORD or word(TAP_LITERAL_AT) != TAP_LITERAL:
        raise SystemExit("the tap tempo block does not end where the patch expects it in this VSB")
    free(STATE, STATE_END - STATE)

    def hook(addr, name, note):
        return {"file": file_offset(addr), "bytes": branch(addr, symbols[name]).hex(), "expect": sha(was(addr, 4)), "note": note}

    def declare(addr, chain, swallow, note):
        return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": "instruction", "chain": chain, "position": "before", "swallow": swallow, "note": note}

    return {
        "format": "gelumpe-patch", "version": 1, "id": "tap-motion", "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "name": "TAP schaltet die aufgenommene Motion Sequence (TAP MOTION)",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "TAP motion: the TAP switch, the TAP LED, and what the BLECH menu's TAP MOTION page writes (TM_SETTING)"},
            hook(TAP_HOOK, "tap_hook", "the instruction before the call of the tap tempo calculation jumps to the hook"),
            hook(BEAT_HOOK, "beat_hook", "first instruction of the TAP LED beat flash jumps to the hook"),
            hook(TICK_HOOK, "tick_hook", "first instruction of the LED manager's tick jumps to the hook"),
            {"file": file_offset(FRAME_CALL), "bytes": bl(FRAME_CALL, symbols["frame_hook"]).hex(), "expect": sha(was(FRAME_CALL, 4)),
             "note": "the frame's call of 0xC006EAE0 goes through frame_hook, which makes it first (ONCE switches off in the UI task)"},
        ],
        "hooks": [
            declare(TAP_HOOK, "key-dispatch", True, "TAP with the patch on switches the motion and does not call the tap tempo calculation"),
            declare(BEAT_HOOK, "tap-led", True, "with the patch on there is no beat flash on the TAP LED"),
            declare(TICK_HOOK, "tap-led", False, "keeps the TAP LED at the state of the motion and lets it go when the patch goes off"),
            {"site": f"{FRAME_CALL:#010X}".replace("0X", "0x"), "kind": "call", "chain": "frame", "position": "after", "swallow": False,
             "note": "makes the original call, then switches off what ONCE marked when its pattern started over"},
        ],
        "startPhase": [
            {"file": file_offset(BEAT_HOOK), "length": 4, "why": "the sequencer's first beat (about 100 ms, after the rescue paths at 57 to 60 ms) calls the TAP LED's beat flash, which now jumps to beat_hook"},
            {"file": file_offset(TICK_HOOK), "length": 4, "why": "the LED manager's tick runs from about 140 ms, after the rescue paths, and now jumps to tick_hook"},
            {"file": file_offset(FRAME_CALL), "length": 4, "why": "the screen manager's frame calls frame_hook, which makes the original call and then only looks at the setting"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "tm_active, beat_hook and tick_hook: at start they only look at the panel object, the kill switch, the card and the setting word and hand over to the firmware's own code; the rest runs on a key or when the patch is on"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: TM_SETTING at +0 for the BLECH menu, the LED, the pattern number, the remembered modes", "tools/patch/tap_motion.py:STATE"),
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
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}, setting word {TM_SETTING:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
