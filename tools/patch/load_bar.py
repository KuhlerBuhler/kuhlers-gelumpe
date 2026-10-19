"""Builds the loading bar patch (docs/ideen/41-startbild-ausbauen.md) for firmware 2.02 with Hacktribe.

While the start loads the samples (e2sSample.all), the firmware shows a window "Loading nnn%". With this patch
the BLECH image is shown instead and the underline under BLECH becomes the progress bar, while the eyes look around and
small faces fade in and out at the left and right edge, one at a time, a corner after the other. The image is the patch's own
copy of assets/blechy/splash.bin, not the start image of the file: a start image drawn with the start image editor is seen
from power-on until the load begins, the BLECH image with its eyes while the samples load (device 18.10.: with one pixel of
the start image changed the eyes stood still, because the image was recognised by its CRC).

    python3 tools/patch/load_bar.py --vsb SYSTEM.VSB [--out data/patches/load-bar.json]

Four hooks:
  stat      the call that asks whether e2sSample.all exists, 0xC002AE60, in the start task right after the rescue
            paths (the panel update and the start modes never get there): remembers "a load is coming"
  progress  the call that updates the text "Loading nnn%" in the loader, 0xC00366D4: remembers where the loader is
            and, while the overlay draws, leaves the update out (nobody sees the window, and its redraws cost time)
  load      the call of the loader, 0xC0038D60: remembers that it is done
  frame     the tail call that sends the frame to the display, 0xC008370C: while a load is expected it puts the
            image over the frame before it goes out, so the window never reaches the display

The image is drawn whole when the overlay starts and again whenever a window comes or goes; in between only the
pixels that change (the bar, the pupils) are drawn, which costs next to nothing. The firmware's own draw of the whole
image takes 2.5 million instructions, which is why the first version, one per frame, made the start 59 percent longer.

With EXIT held at power-on, without a card or without e2sSample.all nothing is ever expected and every hook goes
straight to the original. A card that is in the slot but not mounted after the start's question is asked again, up to
RETRIES times, RETRY_MS apart (device 18.10.: a card that answered late left the start without samples or hanging). When the
loader ends with a code (a card error), the overlay ends at once, so the firmware's window is seen. The overlay ends when the main screen comes (or after a cap of frames).
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

HEADER = 0x100
RAM = 0xC0000000
ART = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2]) / "assets" / "blechy" / "splash.bin"   # frozen: unpacked next to the code

CODE_AT = 0xC0181000            # free (FF) in the image, behind the pattern switch
CODE_END = 0xC0181A00
BASE = 0xC0181A00               # the BLECH image in the order of the frame buffer, 1024 bytes, written by the patch
BASE_END = 0xC0181E00
STATE = 0xC0181F00              # run time state, in RAM only
STATE_END = 0xC0181F40

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)
RETRIES = 3                     # a card that is not mounted after the start's question is asked again up to 3 times,
RETRY_MS = 500                  # 500 ms apart
FRAME_CAP = 8000                # about 6 minutes of frames; the main screen ends it much earlier

STAT_CALL = 0xC002AE60          # bl 0xC0035440, the start asks whether e2sSample.all exists
STAT_FUNC = 0xC0035440
PROGRESS_CALL = 0xC00366D4      # bl 0xC002D8EC in the loader's loop: the text "Loading nnn%"
PROGRESS_FUNC = 0xC002D8EC
LOAD_CALL = 0xC0038D60          # bl 0xC00364F0, the loader
LOAD_FUNC = 0xC00364F0
FLUSH = 0xC008370C              # b 0xC0015DD0, the frame function's tail call
FLUSH_FUNC = 0xC0015DD0

# The pupils are 3 by 3 pixels, top rows 15, left columns 50 and 77 (assets/blechy/splash.bin); the bar is rows 61 and 62, x 20 to 107.
# The pupil's step to the side, plus 5: fast at the start of a sweep and braking towards its end (ease-out, 10 * (1 - (1 - k/6)^2)),
# then a rest, the same way back, a rest (device 18.10.: the even steps looked too linear).
EYE_SWEEP = [3, 6, 8, 9, 10]
EYE_TABLE = EYE_SWEEP + [10] * 7 + [10 - v for v in EYE_SWEEP] + [0] * 7
EYE_EVERY = 4                   # frames between two steps of the pupils (a power of two)

# The faces: 8 by 9 pixels, drawn dark on the light edge of the image (x 0 to 13 and 114 to 127 are plain light in the BLECH image).
# They fade in by a 4 by 4 ordered dither: at level n of 16 the pixels whose threshold is below n are drawn.
# One cycle is 16 steps of FACE_EVERY frames; in each cycle the face sits in the next of four places.
FACE = [".XXXXXX.",
        "XXXXXXXX",
        "X..XX..X",
        "X.XXXX.X",
        "X..XX..X",
        "XXXXXXXX",
        "X.X..X.X",
        "XXXXXXXX",
        ".XXXXXX."]
FACE_LEVELS = [0, 0, 0, 4, 8, 12, 16, 16, 16, 16, 12, 8, 4, 0, 0, 0]
FACE_PLACES = [(2, 10), (118, 38), (118, 10), (2, 38)]      # left, right, right, left: x, y of the top left pixel
FACE_EVERY = 4                  # frames per step (a power of two)
BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def art_frame():
    """assets/blechy/splash.bin in the order of the frame buffer: the bits of every byte reversed (bit 0 is the top row of a page)."""
    data = ART.read_bytes()
    if len(data) != 1024:
        raise SystemExit(f"{ART} is not a 1024 byte start image")
    return bytes(int(f"{b:08b}"[::-1], 2) for b in data)


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ MGR, 0xC03404C0            ; pointer to the screen manager, +0x2C the screen number, +0x5C asks for a full redraw
.equ VRAM, 0xC031B310           ; the firmware's frame buffer, 8 pages of 128 bytes, bit 0 of a byte is the top row of its page
.equ MARK, 0xC001531C           ; (x, y, x2, y2): marks a region of the frame buffer as changed
.equ STAT, @STAT_FUNC@
.equ FATFS, 0xC06A010C          ; FatFs volume table: first entry is the volume of the card, its byte 0 the mounted type (0 not mounted)
.equ WAIT, 0xC0000B78           ; (ms): the operating system's sleep
.equ SD_INPUT, 0x01E26070       ; GPIO IN_DATA45; bit 1 (GPIO 4.1) is low while a card is in the slot
.equ SD_DETECT, 2
.equ RETRIES, @RETRIES@
.equ RETRY_MS, @RETRY_MS@
.equ LOADER, @LOAD_FUNC@
.equ SETTEXT, @PROGRESS_FUNC@
.equ FLUSH, @FLUSH_FUNC@
.equ KILL, @KILL@
.equ BASE, @BASE@
.equ STATE, @STATE@
.equ FRAME_CAP, @CAP@
.equ EYE_SHIFT, @EYE_SHIFT@
.equ S_EXPECT, 0               ; 1 while a load is expected and the overlay draws, 2 when it is over, FFFFFFFF never started
.equ S_CUR, 4                  ; the loader's file offset
.equ S_MAX, 8                  ; the largest offset in the file
.equ S_DONE, 12                ; 1 when the loader has returned
.equ S_FRAME, 16               ; frames drawn
.equ S_MODE, 20                ; 1: the BLECH image (kept for the readers of the state; there is no other any more)
.equ S_DRAWN, 24               ; 1 once the whole frame buffer has been marked as changed
.equ S_FILL, 28                ; pixels of the bar marked so far
.equ S_DX, 32                  ; step of the pupils marked so far
.equ S_FACE, 36                ; the face marked so far: place * 256 + level
.equ S_FACE_NOW, 40            ; the face of this frame
.equ FACE_SHIFT, @FACE_SHIFT@

.org @CODE_AT@

; ===================================================== stat
; Replaces the call that asks whether e2sSample.all exists (r0 = the path, the answer comes back in r0, nonzero when it does).
; Reached only on the normal start, after the panel update and the start modes. A load is expected when the file is there
; and EXIT was not held at power-on.
lb_stat:
    push {r4, r5, r6, lr}
    mov r6, r0
    bl STAT
    mov r4, r0
    mov r5, #RETRIES
; The card's volume is not mounted after the question (a card that did not answer in time, device 18.10.): wait and ask again,
; RETRIES times; then the start goes on as the firmware does without a card. Not with EXIT held at power-on.
ls_try:
    ldr r0, =FATFS
    ldr r0, [r0]
    cmp r0, #0
    ldrbne r0, [r0]
    cmpne r0, #0
    bne ls_have
    subs r5, r5, #1
    bmi ls_have
    ldr r1, =SD_INPUT           ; no card in the slot (GPIO 4.1 high): nothing to ask again
    ldr r1, [r1]
    tst r1, #SD_DETECT
    bne ls_have
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq ls_have
    ldr r1, [r1, #0x18]
    tst r1, #KILL
    bne ls_have
    ldr r0, =RETRY_MS
    bl WAIT
    mov r0, r6
    bl STAT
    mov r4, r0
    b ls_try
ls_have:
    cmp r4, #0
    beq ls_out
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq ls_out
    ldr r1, [r1, #0x18]
    tst r1, #KILL
    bne ls_out
    ldr r1, =STATE
    mov r2, #0
    str r2, [r1, #S_CUR]
    str r2, [r1, #S_MAX]
    str r2, [r1, #S_DONE]
    str r2, [r1, #S_FRAME]
    str r2, [r1, #S_DRAWN]
    str r2, [r1, #S_FILL]
    str r2, [r1, #S_DX]
    str r2, [r1, #S_FACE]
    str r2, [r1, #S_FACE_NOW]
    mov r2, #1
    str r2, [r1, #S_MODE]
    str r2, [r1, #S_EXPECT]
ls_out:
    mov r0, r4
    pop {r4, r5, r6, pc}

; ===================================================== loader
; Replaces the loader's call of the text update (r0, r1 are its arguments): the loader's file offset is in r4, the largest in r7.
; While the overlay draws, the update is left out: the window it would redraw is never seen.
lb_progress:
    ldr r12, =STATE
    str r4, [r12, #S_CUR]
    str r7, [r12, #S_MAX]
    ldr r12, [r12, #S_EXPECT]
    cmp r12, #1
    moveq r0, #1
    bxeq lr
    ldr r12, =SETTEXT
    bx r12

; Replaces the call of the loader: remembers that it is over. When the loader ends with a code (a card error, a sample it
; could not load), the overlay ends at once, so the firmware's window says what happened (device 18.10.: "Card error" stayed
; behind the image).
lb_load:
    push {r4, lr}
    bl LOADER
    ldr r1, =STATE
    mov r2, #1
    str r2, [r1, #S_DONE]
    cmp r0, #0
    beq ll_out
    ldr r2, [r1, #S_EXPECT]
    cmp r2, #1
    moveq r2, #2
    streq r2, [r1, #S_EXPECT]
    ldr r2, =MGR
    ldr r2, [r2]
    cmp r2, #0
    movne r3, #1
    strbne r3, [r2, #0x5C]      ; the screen manager draws everything anew
ll_out:
    pop {r4, pc}

; ===================================================== frame
; Replaces the tail call that sends the frame to the display (r0, r1, r2 are its arguments, lr the caller's).
lb_frame:
    ldr r3, =STATE
    ldr r12, [r3, #S_EXPECT]
    cmp r12, #1
    bne lf_pass
    push {r0, r1, r2, lr}
    bl overlay
    pop {r0, r1, r2, lr}
lf_pass:
    ldr r12, =FLUSH
    bx r12

; Puts the image over the frame buffer, or ends the overlay: when the main screen has come, or after the frame cap.
; The user interface has drawn the window into the buffer by now; every frame the image goes over all of it again.
overlay:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    ldr r4, =STATE
    ldr r0, =MGR
    ldr r0, [r0]
    cmp r0, #0
    beq ov_go
    ldr r1, [r0, #0x2C]
    cmp r1, #1
    bne ov_go
    mov r1, #1
    strb r1, [r0, #0x5C]
ov_end:
    mov r1, #2
    str r1, [r4, #S_EXPECT]
    b ov_out
ov_go:
    ldr r5, [r4, #S_FRAME]
    add r5, r5, #1
    str r5, [r4, #S_FRAME]
    ldr r1, =FRAME_CAP
    cmp r5, r1
    bhi ov_end
    bl compose
ov_out:
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; r0 = the pixels of the bar that are filled: all of them when the loader is done, else the loader's share of the file.
fill_px:
    push {r4, lr}
    ldr r4, =STATE
    mov r2, #88
    ldr r1, [r4, #S_DONE]
    cmp r1, #1
    moveq r0, r2
    popeq {r4, pc}
    ldr r0, [r4, #S_CUR]
    ldr r1, [r4, #S_MAX]
    cmp r1, #0
    moveq r0, #0
    popeq {r4, pc}
fp_scale:
    cmp r1, #0x10000
    blo fp_scaled
    mov r0, r0, lsr #1
    mov r1, r1, lsr #1
    b fp_scale
fp_scaled:
    mul r3, r0, r2
    mov r0, #0
fp_loop:
    cmp r3, r1
    blo fp_out
    cmp r0, r2
    bhs fp_out
    sub r3, r3, r1
    add r0, r0, #1
    b fp_loop
fp_out:
    pop {r4, pc}

; r0 = buffer, r1 = x, r2 = y, r3 = 1 lit or 0 dark. Bit 0 of a byte is the top row of its page, 128 bytes per page.
; Clobbers r1, r2 and r12.
set_px:
    mov r12, r2, lsr #3
    add r12, r1, r12, lsl #7
    and r2, r2, #7
    mov r1, #1
    mov r1, r1, lsl r2
    ldrb r2, [r0, r12]
    cmp r3, #0
    biceq r2, r2, r1
    orrne r2, r2, r1
    strb r2, [r0, r12]
    bx lr

; r0 = buffer, r1 = x of the left column, r2 = y of the top row, r3 = 1 or 0: a square of 3 by 3 pixels
block3:
    push {r4, r5, r6, r7, r8, lr}
    mov r4, r1
    mov r5, r2
    mov r6, #0
b3_row:
    mov r7, #0
b3_col:
    add r1, r4, r7
    add r2, r5, r6
    bl set_px
    add r7, r7, #1
    cmp r7, #3
    blo b3_col
    add r6, r6, #1
    cmp r6, #3
    blo b3_row
    pop {r4, r5, r6, r7, r8, pc}

; The image with the bar and the eyes into the frame buffer. Only what changed since the last frame is marked
; as changed (the first time everything): the display is sent page by page, and sending pages costs more than drawing them.
compose:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    ldr r4, =STATE
    ldr r7, =VRAM
    ldr r1, =BASE
    mov r0, r7
    mov r2, #1024
cp_loop:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne cp_loop
    bl fill_px
    mov r9, r0
    mov r6, #0
cp_blech:
    cmp r6, #88
    bhs cp_eyes
    cmp r6, r9
    movlo r3, #0
    movhs r3, r6
    andhs r3, r3, #1
    mov r0, r7
    add r1, r6, #20
    mov r2, #61
    bl set_px
    mov r0, r7
    add r1, r6, #20
    mov r2, #62
    bl set_px
    add r6, r6, #1
    b cp_blech
cp_eyes:
    ldr r5, [r4, #S_FRAME]
    mov r5, r5, lsr #EYE_SHIFT
cp_mod:
    cmp r5, #24
    subhs r5, r5, #24
    bhs cp_mod
    ldr r1, =eye_table
    ldrb r8, [r1, r5]
    sub r8, r8, #5
    mov r0, r7
    mov r1, #50
    mov r2, #15
    mov r3, #1
    bl block3
    mov r0, r7
    mov r1, #77
    mov r2, #15
    mov r3, #1
    bl block3
    mov r0, r7
    add r1, r8, #50
    mov r2, #15
    mov r3, #0
    bl block3
    mov r0, r7
    add r1, r8, #77
    mov r2, #15
    mov r3, #0
    bl block3
    bl face
cp_mark:
    ldr r0, [r4, #S_DRAWN]
    cmp r0, #0
    bne cp_delta
    mov r0, #1
    str r0, [r4, #S_DRAWN]
    str r9, [r4, #S_FILL]
    str r8, [r4, #S_DX]
    ldr r0, [r4, #S_FACE_NOW]
    str r0, [r4, #S_FACE]
    mov r0, #0
    mov r1, #0
    mov r2, #128
    mov r3, #64
    bl MARK
    b cp_done
cp_delta:
    ldr r5, [r4, #S_FILL]
    cmp r5, r9
    beq cp_pupils
    mov r6, #20                  ; the bar: x from 20, rows 61 and 62
    mov r1, #61
    mov r3, #63
    add r0, r6, r5
    add r2, r6, r9
    bl MARK
    str r9, [r4, #S_FILL]
cp_pupils:
    ldr r5, [r4, #S_DX]
    cmp r5, r8
    beq cp_face
    mov r0, #44
    mov r1, #15
    mov r2, #88
    mov r3, #18
    bl MARK
    str r8, [r4, #S_DX]
cp_face:
    ldr r5, [r4, #S_FACE_NOW]
    ldr r6, [r4, #S_FACE]
    cmp r5, r6
    beq cp_done
    str r5, [r4, #S_FACE]
    mov r0, r6
    bl mark_face
    mov r0, r5
    bl mark_face
cp_done:
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; r0 = place * 256 + level: marks the place of that face as changed
mark_face:
    push {lr}
    mov r1, r0, lsr #8
    and r1, r1, #3
    ldr r2, =face_places
    add r2, r2, r1, lsl #1
    ldrb r0, [r2]
    ldrb r1, [r2, #1]
    add r2, r0, #8
    add r3, r1, #9
    bl MARK
    pop {pc}

; The small face of this frame into the frame buffer r7 (r4 = STATE): the level and the place come from the frame count, the key
; goes to S_FACE_NOW for the marking. Keeps every register.
face:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    ldr r5, [r4, #S_FRAME]
    mov r6, r5, lsr #FACE_SHIFT
    and r0, r6, #15
    ldr r1, =face_levels
    ldrb r10, [r1, r0]
    mov r6, r6, lsr #4
    and r6, r6, #3
    orr r0, r10, r6, lsl #8
    str r0, [r4, #S_FACE_NOW]
    cmp r10, #0
    beq fc_out
    ldr r1, =face_places
    add r1, r1, r6, lsl #1
    ldrb r5, [r1]
    ldrb r6, [r1, #1]
    mov r11, #0
fc_row:
    ldr r1, =face_art
    ldrb r8, [r1, r11]
    mov r9, #0
fc_col:
    mov r0, #1
    tst r8, r0, lsl r9
    beq fc_next
    add r1, r5, r9
    add r2, r6, r11
    and r3, r2, #3
    and r12, r1, #3
    add r3, r12, r3, lsl #2
    ldr r12, =bayer
    ldrb r3, [r12, r3]
    cmp r3, r10
    bhs fc_next
    mov r0, r7
    mov r3, #0
    bl set_px
fc_next:
    add r9, r9, #1
    cmp r9, #8
    blo fc_col
    add r11, r11, #1
    cmp r11, #9
    blo fc_row
fc_out:
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}

eye_table:
    .byte @EYES@
face_levels:
    .byte @LEVELS@
face_places:
    .byte @PLACES@
bayer:
    .byte @BAYER@
face_art:
    .byte @FACE@
.align 4
lit_pool:
.pool
"""


def source():
    text = SOURCE
    for key, value in {
        "STAT_FUNC": f"{STAT_FUNC:#x}", "LOAD_FUNC": f"{LOAD_FUNC:#x}", "PROGRESS_FUNC": f"{PROGRESS_FUNC:#x}", "FLUSH_FUNC": f"{FLUSH_FUNC:#x}",
        "KILL": f"{KILL_SWITCH:#x}", "BASE": f"{BASE:#x}", "STATE": f"{STATE:#x}", "CAP": str(FRAME_CAP), "RETRIES": str(RETRIES), "RETRY_MS": str(RETRY_MS),
        "CODE_AT": f"{CODE_AT:#x}", "EYES": ", ".join(str(v) for v in EYE_TABLE), "EYE_SHIFT": str(EYE_EVERY.bit_length() - 1),
        "FACE_SHIFT": str(FACE_EVERY.bit_length() - 1), "LEVELS": ", ".join(str(v) for v in FACE_LEVELS),
        "PLACES": ", ".join(str(v) for xy in FACE_PLACES for v in xy), "BAYER": ", ".join(str(v) for v in BAYER),
        "FACE": ", ".join(str(sum(1 << k for k, c in enumerate(row) if c == "X")) for row in FACE),
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


def word_of(at, target, link):
    return struct.unpack("<I", branch(at, target, link))[0]


def build_patch(vsb):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
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
        (STAT_CALL, word_of(STAT_CALL, STAT_FUNC, True), "the start does not ask whether e2sSample.all exists where the patch expects it"),
        (PROGRESS_CALL, word_of(PROGRESS_CALL, PROGRESS_FUNC, True), "the loader does not update its text where the patch expects it"),
        (LOAD_CALL, word_of(LOAD_CALL, LOAD_FUNC, True), "the call of the loader is not where the patch expects it"),
        (FLUSH, word_of(FLUSH, FLUSH_FUNC, False), "the frame function does not end in the display flush where the patch expects it"),
    )
    for addr, want, why in expected:
        if word(addr) != want:
            raise SystemExit(f"{why} in this VSB")
    free(STATE, STATE_END - STATE)

    def hook(addr, name, link, note):
        return {"file": file_offset(addr), "bytes": branch(addr, symbols[name], link).hex(), "expect": sha(was(addr, 4)), "note": note}

    def declare(addr, kind, chain, position, swallow, note):
        return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": kind, "chain": chain, "position": position, "swallow": swallow, "note": note}

    return {
        "format": "gelumpe-patch", "version": 1, "id": "load-bar", "builds": ["hacktribe", "stock"],
        "name": "Ladebalken im Startbild",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "loading bar: the BLECH image while e2sSample.all loads, the underline is the bar, the eyes look around"},
            {"file": file_offset(BASE), "bytes": art_frame().hex(), "expect": free(BASE, BASE_END - BASE),
             "note": "the BLECH image (assets/blechy/splash.bin) in the order of the frame buffer"},
            hook(STAT_CALL, "lb_stat", True, "the question whether e2sSample.all exists goes through the hook"),
            hook(PROGRESS_CALL, "lb_progress", True, "the loader's text update goes through the hook"),
            hook(LOAD_CALL, "lb_load", True, "the call of the loader goes through the hook"),
            hook(FLUSH, "lb_frame", False, "the frame function's flush goes through the hook"),
        ],
        "hooks": [
            declare(STAT_CALL, "call", "start", "after", False, "after the original asks whether e2sSample.all exists, the hook remembers that a load is coming"),
            declare(PROGRESS_CALL, "call", "start", "before", False, "the hook notes the loader's position; while the overlay draws the text update is left out, otherwise it runs"),
            declare(LOAD_CALL, "call", "start", "after", False, "the loader runs, then the hook notes that it is done"),
            declare(FLUSH, "instruction", "frame", "before", False, "while a load is expected the hook puts the image over the frame, then the original flush runs"),
        ],
        "startPhase": [
            {"file": file_offset(STAT_CALL), "length": 4, "why": "the start task asks whether e2sSample.all exists, about 75 ms in, after the panel update and the start modes, and now calls lb_stat"},
            {"file": file_offset(PROGRESS_CALL), "length": 4, "why": "the loader updates its text for every sample and now calls lb_progress"},
            {"file": file_offset(LOAD_CALL), "length": 4, "why": "the start task calls the loader and now calls lb_load"},
            {"file": file_offset(FLUSH), "length": 4, "why": "every frame of the user interface task ends in this flush; from the first frame (about 170 ms) it calls lb_frame"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "the hooks and what they call: they note a load only when the file exists and EXIT was not held, and draw only then"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state of the overlay", "tools/patch/load_bar.py:STATE"),
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
        print(f"section {at:#x} + {len(code):#x} bytes, base {BASE:#x}, state {STATE:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
