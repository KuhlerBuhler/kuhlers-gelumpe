"""Builds the splash editor patch (docs/ideen.md idea 35) for firmware 2.02 with Hacktribe.

The patch adds a page SPLASH SCREEN to the Global menu: page 20, after
XY CALIBRATION. MENU opens an editor for the 128 x 64 start image, the main
dial moves a blinking cursor (left and right, with SHIFT held up and down), MENU
flips the pixel under it and, held, paints that colour wherever the cursor goes,
WRITE stores the image in flash and EXIT leaves. At start the stored image is drawn, or the
one in the VSB when nothing valid is stored.

Everything here is our own code. Nothing of the firmware is copied into the
patch: the table of virtual functions of the Global screen is copied from the
user's VSB when the patch is applied (a `copy` change, src/patch.mjs).

    python3 tools/patch/splash_editor.py --vsb SYSTEM.VSB [--out data/patches/splash-editor.json]

reads the VSB only for the checksums of the bytes the patch replaces. Only the Sampler builds (Hacktribe and
Korg's own 2.02) carry the editor; the blue Electribe gets the start image as a data patch. Design
and measurements: docs/hintergrund/startbild-editor.md and
docs/messungen/2026-10-10-startbild-editor.md. Every address is a RAM address of
the measured build; the file offset in the VSB is address - 0xC0000000 + 0x100.
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

# ---- where our bytes go ------------------------------------------------------
# Free (FF) run in the image, 0xC01A2100 to 0xC01FFFF0 (docs/patcher.md). The
# code that runs at start is kept apart from the editor, so the export check can
# show that nothing else of ours runs before the main screen.
START_AT = 0xC01A2100
START_END = 0xC01A2500
EDITOR_AT = 0xC01A2500
EDITOR_END = 0xC01A3C00
VTABLE_AT = 0xC01A3C00          # copy of the Global screen's vtable, 18 words
VTABLE_WORDS = 18
STATE = 0xC0182000              # run time state, not in the file (stays FF there); in the free run below the pattern switch and the loading bar, clear of the power-off picture at 0xC01A4A00
STATE_SIZE = 0x100
RECBUF = 0xC0182100             # the record as stored: 0x40C bytes
EDIT = 0xC0182920               # the image being edited: 1024 bytes
FIL = 0xC0182D20                # the card file of the import (the firmware's FatFs writes 0x224 bytes of it, measured)
BR = 0xC0182F60                 # bytes the last read gave
FREE_END = 0xC0183000
IMPORT_ENTRY = 0xC01A2500       # EDITOR_AT: b splash_import, for the BLECH menu; r0 = 0 stored, 1 no file, 2 no 128 x 64 BMP with 1 bit, 3 flash
DRAW_ENTRY = 0xC01A2504         # b splash_draw: Global, page SPLASH SCREEN, the editor open; the menu jumps here instead of returning
TICK_HOOK = 0xC006F178          # first instruction of the screen manager's tick, ldrb r3, [r0, #0x4c]
TICK_WORD = 0xE5D0304C
IMPORT_PATH = "SD:KORG/blechtribe/splash.bmp"

# ---- firmware facts (measured, see the research doc) ---------------------------
ORIG_VTABLE = 0xC00E33F8        # class of Global screen 9
VTABLE_LITERAL = 0xC0064D3C     # the one literal the constructor loads that vtable from
START_CALL = 0xC002ADAC         # bl 0xC002A248, after the rescue paths
SPLASH_CALL = 0xC002AC38        # bl 0xC003F650 drawing image 13, before them
PAGE_SHOWN_1 = 0xC0064980       # mov r2, #0x14: the "/20" of the page display
PAGE_SHOWN_2 = 0xC0064D04
PAGES_SHOWN = (PAGE_SHOWN_1, PAGE_SHOWN_2)
SLOTS = {"dtor": 0, "dtor_free": 1, "exit": 2, "keys": 3, "edit_prev": 4, "edit_next": 5, "menu": 6, "value": 10}

FLASH_RECORD = 0x7F0000         # a 4 KiB sector no known writer touches
RECORD_ID = int.from_bytes(b"GLSP", "little")
RECORD_VERSION = 1
IMAGE_BYTES = 1024
RECORD_SIZE = 4 + 2 + 2 + IMAGE_BYTES + 4
MAGIC = 0x314C5053              # "SPL1", set last by the start code
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, derived)
PAGE = 20                       # the new page's number

SOURCE = f"""
; ---------------------------------------------------------------- constants
.equ ORIG_VT, {ORIG_VTABLE:#x}
.equ PARAM, 0xC0691240          ; pointer to the Global parameter object
.equ DESC13, 0xC00C5A54         ; data pointer of image 13, the start image
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 held keys, +0x22 panel update
.equ MGR, 0xC03404C0            ; pointer to the screen manager, +0x5C asks for a full redraw
.equ DISPLAY_OUT, 0xC031BB2C
.equ FLASH_RECORD, {FLASH_RECORD:#x}
.equ REC_LEN, {RECORD_SIZE:#x}
.equ RECORD_ID, {RECORD_ID:#x}
.equ RECORD_VER_LEN, {RECORD_VERSION | (IMAGE_BYTES << 16):#x}
.equ MAGIC, {MAGIC:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ STATE, {STATE:#x}
.equ RECBUF, {RECBUF:#x}
.equ EDIT, {EDIT:#x}
.equ FIL, {FIL:#x}
.equ BR, {BR:#x}
.equ FS_OPEN, 0xC009DB60
.equ FS_READ, 0xC009DD74
.equ FS_CLOSE, 0xC009E3DC
.equ S_MAGIC, 0
.equ S_MODE, 4                  ; 1 while the editor is open
.equ S_CUR, 8                   ; cursor, y * 128 + x
.equ S_PHASE, 12                ; 1 while the cursor shows the inverse of its pixel
.equ S_TICK, 16
.equ S_REDRAW, 20               ; after WRITE: 1 waiting for the Working window to come up, 2 it is up (or VALUE moved the cursor); the image is drawn again once it is gone
.equ S_PUSHED, 24               ; screen object our widget sits in
.equ S_PENDING, 28              ; ticks left in which the Global screen the BLECH menu asked for opens on the editor
.equ S_VBEGIN, 0x20             ; while the editor is open: the screen's widget vector (begin, end, capacity) as it was,
.equ S_VEND, 0x24               ; so only our widget is drawn (the page's text widgets redrew themselves after VALUE and
.equ S_ONE, 0x28                ; showed for a tick on the device); S_ONE is the one-entry vector that stands in for it
.equ S_VCAP, 0x2C
.equ S_PAINT, 0x30              ; the colour MENU last gave a pixel (0 or 1): held, MENU paints it under the moving cursor
.equ S_WIDGET, 0x40
.equ KEYS, 0xC06BCA70           ; the UI task's key states, 8 bytes per key, the word is not 0 while the key is held
.equ KEY_MENU, 0x09
.equ KEY_SHIFT, 0x0A
.equ WINDOW_WAIT, 40            ; ticks to wait for the Working window before drawing without it

; ------------------------------------------------- code that runs at start
.org {START_AT:#x}

; Replaces the call at 0xC002ADAC. Runs the original call, then draws the start
; image once: the stored one when it is valid, else the one in the VSB. With EXIT
; held at power-on, or when the panel is being updated, it reads nothing, sets
; nothing up and draws the VSB image, as an unpatched firmware would. The display
; output is the two calls of the firmware's own splash path, without its third
; call 0xC0015C78: that is the DSP boot, which the early path still runs once.
splash_start:
    push {{r4, r5, r6, r7, r8, lr}}
    bl 0xC002A248
    mov r4, r0
    mov r8, #1
    ldr r5, =PANEL
    ldr r5, [r5]
    ldr r6, [r5, #0x18]
    tst r6, #KILL
    movne r8, #0
    ldrb r6, [r5, #0x22]
    cmp r6, #0
    movne r8, #0
    cmp r8, #0
    beq start_draw
    bl 0xC0029A40
    ldr r1, =RECBUF
    ldr r2, =FLASH_RECORD
    ldr r3, =REC_LEN
    bl 0xC0029A74
    cmp r0, #0
    beq start_state
    ldr r0, =RECBUF
    bl record_valid
    cmp r0, #0
    beq start_state
    ldr r1, =DESC13
    ldr r2, =RECBUF+8
    str r2, [r1]
start_state:
    ldr r0, =STATE
    mov r1, #0
    mov r2, #{STATE_SIZE // 4}
start_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne start_zero
    ldr r0, =STATE
    ldr r1, =MAGIC
    str r1, [r0, #S_MAGIC]
start_draw:
    mov r0, #0
    bl draw_image
    ldr r0, =DISPLAY_OUT
    mov r1, #2
    mov r2, #0
    bl 0xC0015DD0
    ldr r0, =DISPLAY_OUT
    mov r1, #3
    mov r2, #0
    bl 0xC0015DD0
    mov r0, r4
    pop {{r4, r5, r6, r7, r8, pc}}

; r0 = record, returns 1 when id, version, length and CRC-32 all fit
record_valid:
    push {{r4, lr}}
    mov r4, r0
    ldr r1, [r4]
    ldr r2, =RECORD_ID
    cmp r1, r2
    bne valid_no
    ldr r1, [r4, #4]
    ldr r2, =RECORD_VER_LEN
    cmp r1, r2
    bne valid_no
    mov r0, r4
    ldr r1, =REC_LEN-4
    bl crc32
    ldr r1, [r4, #REC_LEN-4]
    cmp r0, r1
    bne valid_no
    mov r0, #1
    pop {{r4, pc}}
valid_no:
    mov r0, #0
    pop {{r4, pc}}

; r0 = data, r1 = length, returns the CRC-32 (zlib's, bit by bit)
crc32:
    ldr r12, =0xEDB88320
    mvn r2, #0
crc_byte:
    cmp r1, #0
    beq crc_done
    ldrb r3, [r0], #1
    eor r2, r2, r3
    mov r3, #8
crc_bit:
    movs r2, r2, lsr #1
    eorcs r2, r2, r12
    subs r3, r3, #1
    bne crc_bit
    sub r1, r1, #1
    b crc_byte
crc_done:
    mvn r0, r2
    bx lr

; r0 = image to draw, or 0 for the one image 13 points at; clears the display buffer first
draw_image:
    push {{r4, r5, r6, lr}}
    sub sp, sp, #12
    mov r4, r0
    ldr r5, =DESC13
    ldr r6, [r5]
    cmp r4, #0
    strne r4, [r5]
    bl 0xC003F0D4
    bl 0xC003F104
    mov r0, #13
    str r0, [sp]
    mov r1, #0
    str r1, [sp, #4]
    str r1, [sp, #8]
    mov r0, sp
    add r1, sp, #4
    add r2, sp, #8
    bl 0xC003F650
    bl 0xC003F108
    str r6, [r5]
    mov r0, #0
    mov r1, #0
    mov r2, #128
    mov r3, #64
    bl 0xC001531C
    add sp, sp, #12
    pop {{r4, r5, r6, pc}}
; First instruction of the screen manager's tick (r0 = the manager). Does nothing unless splash_draw asked for the editor.
splash_tick:
    push {{r0, r1, r2, r3, r12, lr}}
    ldr r12, =STATE
    ldr r1, [r12, #S_MAGIC]
    ldr r2, =MAGIC
    cmp r1, r2
    bne tick_out
    ldr r1, [r12, #S_MODE]          ; editor open: the firmware's wish to redraw the whole page (set after VALUE) is dropped,
    cmp r1, #1                      ; so the page never shows over the image (it flickered for a tick, device 17.10.)
    bne tick_pending
    ldr r1, =MGR
    ldr r1, [r1]
    mov r2, #0
    strb r2, [r1, #0x5C]
tick_pending:
    ldr r1, [r12, #S_PENDING]
    cmp r1, #0
    beq tick_out
    sub r1, r1, #1
    str r1, [r12, #S_PENDING]
    ldr r1, =MGR
    ldr r1, [r1]
    ldr r2, [r1, #0x2C]
    cmp r2, #9
    bne tick_out
    ldr r1, [r1, #0x20]
    cmp r1, #0
    beq tick_out
    mov r2, #0
    str r2, [r12, #S_PENDING]
    push {{r1}}
    mov r0, r1
    bl show_page
    pop {{r0}}
    bl enter_editor
    ldr r12, =STATE
    mov r2, #2                  ; the firmware draws the new screen after this tick: the image goes over it on the next
    str r2, [r12, #S_REDRAW]
tick_out:
    pop {{r0, r1, r2, r3, r12, lr}}
    ldrb r3, [r0, #0x4c]        ; the replaced instruction
    b {TICK_HOOK + 4:#x}

.pool

; ------------------------------------------------------------- the editor
.org {EDITOR_AT:#x}
    b splash_import             ; IMPORT_ENTRY, called by the BLECH menu
    b splash_draw               ; DRAW_ENTRY, jumped to by the BLECH menu

; Checks the replaced slots start with: the state was set up at start and EXIT was
; not held. Otherwise the original slot runs, with every argument as it came.
{{gates}}

; ---- slots of the Global screen, this = r0
slot_dtor:
{{gate0}}
    push {{r0, r1, r2, lr}}
    bl show_widgets
    pop {{r0, r1, r2, lr}}
    ldr r3, =STATE
    mov r2, #0
    str r2, [r3, #S_MODE]
    str r2, [r3, #S_PUSHED]
    b orig0

slot_dtor_free:
{{gate1}}
    push {{r0, r1, r2, lr}}
    bl show_widgets
    pop {{r0, r1, r2, lr}}
    ldr r3, =STATE
    mov r2, #0
    str r2, [r3, #S_MODE]
    str r2, [r3, #S_PUSHED]
    b orig1

slot_exit:
{{gate2}}
    ldr r3, =STATE
    ldr r3, [r3, #S_MODE]
    cmp r3, #1
    bne orig2
    b leave_editor

slot_keys:
{{gate3}}
    ldr r3, =STATE
    ldr r3, [r3, #S_MODE]
    cmp r3, #1
    bne orig3
    cmp r1, #0x0E
    bne orig3
    cmp r2, #1
    bne orig3
    push {{r0, r1, r2, lr}}
    bl save_image
    pop {{r0, r1, r2, lr}}
    b orig3

slot_edit_prev:
{{gate4}}
    ldr r3, =STATE
    ldr r3, [r3, #S_MODE]
    cmp r3, #1
    bxeq lr
    ldr r3, [r0, #0x2C]
    cmp r3, #0
    beq show_page
    cmp r3, #{PAGE}
    bne orig4
    mov r3, #{PAGE - 1}
    str r3, [r0, #0x2C]
    b 0xC0064948

slot_edit_next:
{{gate5}}
    ldr r3, =STATE
    ldr r3, [r3, #S_MODE]
    cmp r3, #1
    bxeq lr
    ldr r3, [r0, #0x2C]
    cmp r3, #{PAGE - 1}
    beq show_page
    b orig5

slot_menu:
{{gate6}}
    ldr r3, =STATE
    ldr r3, [r3, #S_MODE]
    cmp r3, #1
    beq toggle_pixel
    ldr r3, [r0, #0x2C]
    cmp r3, #{PAGE}
    beq enter_editor
    b orig6

slot_value:
{{gate10}}
    ldr r3, =STATE
    ldr r3, [r3, #S_MODE]
    cmp r3, #1
    beq move_cursor
    ldr r3, [r0, #0x2C]
    cmp r3, #{PAGE}
    bxeq lr
    b orig10

; ---- page 20, this = r0. Never writes 20 into the firmware's page byte: its
; three tables of 20 entries would be read at index 20.
show_page:
    push {{r4, lr}}
    mov r4, r0
    mov r0, #{PAGE}
    str r0, [r4, #0x2C]
    ldr r0, =PARAM
    ldr r0, [r0]
    mov r1, #{PAGE - 1}
    bl 0xC007B084
    ldr r0, [r4, #0x24]
    mov r1, #{PAGE}
    bl 0xC0085948
    ldr r0, [r4, #0x24]
    ldr r1, =0xC00A65D1
    bl 0xC0085888
    ldr r0, [r4, #0x28]
    mov r1, #{PAGE}
    mov r2, #{PAGE + 1}
    bl 0xC008A8A8
    ldr r0, [r4, #0x24]
    ldr r1, =title
    bl 0xC00857E4
    ldr r0, [r4, #0x24]
    ldr r1, =0xC00A5A23
    bl 0xC0085828
    pop {{r4, pc}}

; ---- editor, this = r0
enter_editor:
    push {{r4, lr}}
    mov r4, r0
    ldr r3, =STATE
    mov r2, #1
    str r2, [r3, #S_MODE]
    mov r2, #0
    str r2, [r3, #S_CUR]
    str r2, [r3, #S_TICK]
    str r2, [r3, #S_REDRAW]
    ldr r0, =EDIT
    ldr r1, =DESC13
    ldr r1, [r1]
    mov r2, #{IMAGE_BYTES}
    bl {{copy_in}}
    ldr r3, =STATE
    ldr r2, [r3, #S_PUSHED]
    cmp r2, r4
    beq enter_draw
    str r4, [r3, #S_PUSHED]
    add r0, r3, #S_WIDGET
    mov r1, #0
    mov r2, #16
enter_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne enter_zero
    ldr r1, =widget_vtable
    str r1, [r3, #S_WIDGET]
    add r1, r3, #S_WIDGET
    sub sp, sp, #8
    str r1, [sp]
    add r0, r4, #0x10
    mov r1, sp
    bl 0xC00614FC
    add sp, sp, #8
enter_draw:
    bl hide_widgets
    ldr r0, =EDIT
    bl draw_image
    ldr r3, =STATE
    mov r2, #1
    str r2, [r3, #S_PHASE]
    bl px_update
    pop {{r4, pc}}

leave_editor:
    push {{lr}}
    bl show_widgets
    ldr r3, =STATE
    mov r2, #0
    str r2, [r3, #S_MODE]
    ldr r3, =MGR
    ldr r3, [r3]
    mov r2, #1
    strb r2, [r3, #0x5C]
    pop {{pc}}

; r4 = the screen: its widget vector becomes the one entry of our widget; begin, end and capacity are kept to be given back.
; The capacity is the end too, so a widget the firmware adds meanwhile goes to a new buffer, never over our state.
hide_widgets:
    ldr r3, =STATE
    ldr r0, [r3, #S_VBEGIN]
    cmp r0, #0
    bxne lr
    ldr r0, [r4, #0x10]
    str r0, [r3, #S_VBEGIN]
    ldr r0, [r4, #0x14]
    str r0, [r3, #S_VEND]
    ldr r0, [r4, #0x18]
    str r0, [r3, #S_VCAP]
    add r0, r3, #S_WIDGET
    str r0, [r3, #S_ONE]
    add r0, r3, #S_ONE
    str r0, [r4, #0x10]
    add r0, r0, #4
    str r0, [r4, #0x14]
    str r0, [r4, #0x18]
    bx lr

; the screen (S_PUSHED) gets its widget vector back, when we took it. Clobbers r1 to r3.
show_widgets:
    ldr r3, =STATE
    ldr r1, [r3, #S_VBEGIN]
    cmp r1, #0
    bxeq lr
    ldr r2, [r3, #S_PUSHED]
    str r1, [r2, #0x10]
    ldr r1, [r3, #S_VEND]
    str r1, [r2, #0x14]
    ldr r1, [r3, #S_VCAP]
    str r1, [r2, #0x18]
    mov r1, #0
    str r1, [r3, #S_VBEGIN]
    bx lr

; r1 = steps: pixels to the right, with SHIFT held rows down. With MENU held the cursor goes one step at a time and every pixel
; it lands on gets S_PAINT, so a fast turn leaves no gap.
move_cursor:
    push {{r4, r5, lr}}
    mov r4, r1
    mov r5, #1
    ldr r3, =KEYS
    ldr r3, [r3, #8 * KEY_SHIFT]
    cmp r3, #0
    movne r5, #128
    ldr r3, =STATE
    mov r2, #0
    str r2, [r3, #S_PHASE]
    bl px_update
    ldr r3, =KEYS
    ldr r3, [r3, #8 * KEY_MENU]
    cmp r3, #0
    bne move_paint
    mul r1, r4, r5
    bl move_by
    b move_shown
move_paint:
    cmp r4, #0
    beq move_shown
    movgt r1, r5
    rsblt r1, r5, #0
    subgt r4, r4, #1
    addlt r4, r4, #1
    bl move_by
    bl pixel_at
    ldr r12, =STATE
    ldr r12, [r12, #S_PAINT]
    cmp r12, #0
    biceq r1, r1, r2
    orrne r1, r1, r2
    strb r1, [r3, r0]
    bl px_update
    b move_paint
move_shown:
    ldr r3, =STATE
    mov r2, #1
    str r2, [r3, #S_PHASE]
    mov r2, #0
    str r2, [r3, #S_TICK]
    bl px_update
    pop {{r4, r5, pc}}

; r1 = signed amount: the cursor moves by it, wrapping over the 8192 pixels
move_by:
    ldr r3, =STATE
    ldr r2, [r3, #S_CUR]
    add r2, r2, r1
    ldr r1, =0x1FFF
    and r2, r2, r1
    str r2, [r3, #S_CUR]
    bx lr

; the pixel under the cursor -> r3 = EDIT, r0 = its byte there, r1 = that byte, r2 = its bit. Clobbers r12.
pixel_at:
    ldr r12, =STATE
    ldr r0, [r12, #S_CUR]
    mov r1, r0, lsr #7
    and r0, r0, #127
    mov r2, r1, lsr #3
    mov r2, r2, lsl #7
    add r0, r0, r2
    and r1, r1, #7
    rsb r1, r1, #7
    mov r2, #1
    mov r2, r2, lsl r1
    ldr r3, =EDIT
    ldrb r1, [r3, r0]
    bx lr

toggle_pixel:
    push {{r4, lr}}
    bl pixel_at
    eor r1, r1, r2
    strb r1, [r3, r0]
    ands r1, r1, r2
    movne r1, #1
    ldr r4, =STATE
    str r1, [r4, #S_PAINT]
    bl px_update
    pop {{r4, pc}}

; draws the pixel under the cursor: its value in the image, inverted while the cursor is lit
px_update:
    push {{r4, r5, r6, lr}}
    sub sp, sp, #12
    ldr r4, =STATE
    ldr r5, [r4, #S_CUR]
    mov r6, r5, lsr #7
    and r5, r5, #127
    str r5, [sp]
    str r6, [sp, #4]
    mov r0, r6, lsr #3
    mov r0, r0, lsl #7
    add r0, r0, r5
    ldr r1, =EDIT
    ldrb r2, [r1, r0]
    and r3, r6, #7
    rsb r3, r3, #7
    mov r2, r2, lsr r3
    and r2, r2, #1
    ldr r3, [r4, #S_PHASE]
    eor r2, r2, r3
    str r2, [sp, #8]
    mov r0, sp
    add r1, sp, #4
    add r2, sp, #8
    bl 0xC0015824
    add sp, sp, #12
    pop {{r4, r5, r6, pc}}

; Slot 2 of our widget, called for every widget of the screen on each tick of the
; screen manager: redraws once after the Working window, blinks the cursor.
widget_draw:
    push {{r4, lr}}
    ldr r4, =STATE
    ldr r0, [r4, #S_MODE]
    cmp r0, #1
    bne widget_out
    ldr r0, [r4, #S_REDRAW]
    cmp r0, #0
    beq widget_blink
    ldr r1, =MGR
    ldr r1, [r1]
    ldr r1, [r1, #0x24]
    cmp r1, #0
    beq window_gone
    mov r0, #2
    str r0, [r4, #S_REDRAW]
    b widget_out
window_gone:
    cmp r0, #2
    beq widget_redraw
    ldr r1, [r4, #S_TICK]
    add r1, r1, #1
    str r1, [r4, #S_TICK]
    cmp r1, #WINDOW_WAIT
    blt widget_out
widget_redraw:
    mov r0, #0
    str r0, [r4, #S_REDRAW]
    str r0, [r4, #S_TICK]
    ldr r0, =EDIT
    bl draw_image
    bl px_update
    b widget_out
widget_blink:
    ldr r0, [r4, #S_TICK]
    add r0, r0, #1
    str r0, [r4, #S_TICK]
    cmp r0, #6
    blt widget_out
    mov r0, #0
    str r0, [r4, #S_TICK]
    ldr r0, [r4, #S_PHASE]
    eor r0, r0, #1
    str r0, [r4, #S_PHASE]
    bl px_update
widget_out:
    pop {{r4, pc}}

widget_stub:
    mov r0, #0
    bx lr

; ---- WRITE: the edited image as a record into the flash sector, then the stored image is the current one
save_image:
    push {{r4, lr}}
    ldr r4, =RECBUF
    ldr r0, =RECORD_ID
    str r0, [r4]
    ldr r0, =RECORD_VER_LEN
    str r0, [r4, #4]
    add r0, r4, #8
    ldr r1, =EDIT
    mov r2, #{IMAGE_BYTES}
    bl memcpy
    mov r0, r4
    ldr r1, =REC_LEN-4
    bl crc32
    str r0, [r4, #REC_LEN-4]
    bl 0xC0029A40
    ldr r1, =FLASH_RECORD
    ldr r2, =REC_LEN
    mov r3, r4
    bl 0xC0029AB8
    cmp r0, #0
    beq save_done
    ldr r1, =DESC13
    add r2, r4, #8
    str r2, [r1]
    ldr r3, =STATE
    mov r2, #1
    str r2, [r3, #S_REDRAW]
    mov r2, #0
    str r2, [r3, #S_TICK]
save_done:
    pop {{r4, pc}}

; ---- the start image from the card: KORG/blechtribe/splash.bmp, 128 x 64 pixels, 1 bit per pixel, not compressed.
; The darker of the two colours is drawn. Stored in flash like WRITE in the editor and drawn from the next start on.
; r0 = 0 stored, 1 no file, 2 not such a BMP (nothing stored), 3 the flash write failed.
splash_import:
    push {{r4, r5, r6, r7, r8, lr}}
    ldr r4, =FIL
    ldr r5, =RECBUF
    mov r0, r4
    ldr r1, =import_path
    mov r2, #1
    bl FS_OPEN
    cmp r0, #0
    movne r0, #1
    bne imp_out
    mov r0, r5
    mov r1, #54
    bl imp_read
    cmp r0, #0
    bne imp_bad
    ldrb r0, [r5]
    cmp r0, #0x42
    ldrbeq r0, [r5, #1]
    cmpeq r0, #0x4D
    bne imp_bad
    add r0, r5, #10
    bl imp_u32
    mov r6, r0                  ; where the pixels start
    add r0, r5, #14
    bl imp_u32
    mov r7, r0                  ; size of the info header, the palette follows it
    add r0, r5, #18
    bl imp_u32
    cmp r0, #128
    bne imp_bad
    add r0, r5, #22
    bl imp_u32
    mov r8, r0                  ; 64 rows from the bottom, -64 from the top
    cmp r8, #64
    cmnne r8, #64
    bne imp_bad
    ldr r0, [r5, #28]           ; 1 bit per pixel and no compression: bytes 28 to 33
    ldr r1, =0x00000001
    cmp r0, r1
    bne imp_bad
    ldrb r0, [r5, #32]
    ldrb r1, [r5, #33]
    orrs r0, r0, r1
    bne imp_bad
    ldrb r0, [r5, #26]
    cmp r0, #1
    bne imp_bad
    add r0, r7, #22             ; the two palette entries end before the pixels, and the header fits the buffer
    cmp r0, r6
    bhi imp_bad
    cmp r6, #0x200
    bhi imp_bad
    sub r1, r6, #54
    cmp r1, #0
    beq imp_palette
    add r0, r5, #54
    bl imp_read
    cmp r0, #0
    bne imp_bad
imp_palette:
    add r0, r5, r7
    add r0, r0, #14
    ldrb r1, [r0]
    ldrb r2, [r0, #1]
    add r1, r1, r2
    ldrb r2, [r0, #2]
    add r1, r1, r2
    ldrb r2, [r0, #4]
    ldrb r3, [r0, #5]
    add r2, r2, r3
    ldrb r3, [r0, #6]
    add r2, r2, r3
    cmp r2, r1
    movlo r7, #1                ; the index of the darker colour
    movhs r7, #0
    mov r0, r5
    mov r1, #1024
    bl imp_read
    cmp r0, #0
    bne imp_bad
    ldr r0, =EDIT
    mov r1, #0
    mov r2, #256
imp_clear:
    str r1, [r0], #4
    subs r2, r2, #1
    bne imp_clear
    mov r6, #0                  ; y
imp_row:
    cmp r8, #64
    rsbeq r1, r6, #63
    movne r1, r6
    add r1, r5, r1, lsl #4
    mov r2, #0                  ; x
imp_px:
    mov r3, r2, lsr #3
    ldrb r3, [r1, r3]
    and r0, r2, #7
    rsb r0, r0, #7
    mov r3, r3, lsr r0
    and r3, r3, #1
    cmp r3, r7
    bne imp_next
    mov r0, r6, lsr #3
    add r0, r2, r0, lsl #7
    ldr r12, =EDIT
    add r12, r12, r0
    and r0, r6, #7
    rsb r0, r0, #7
    mov r3, #1
    mov r3, r3, lsl r0
    ldrb r0, [r12]
    orr r0, r0, r3
    strb r0, [r12]
imp_next:
    add r2, r2, #1
    cmp r2, #128
    blo imp_px
    add r6, r6, #1
    cmp r6, #64
    blo imp_row
    bl save_image
    cmp r0, #0
    moveq r0, #3
    movne r0, #0
    b imp_close
imp_bad:
    mov r0, #2
imp_close:
    push {{r0}}
    mov r0, r4
    bl FS_CLOSE
    pop {{r0}}
imp_out:
    pop {{r4, r5, r6, r7, r8, pc}}

; ---- from the BLECH menu straight into the editor: the Global parameter screen (9), the page SPLASH SCREEN, the editor open.
; Jumped to instead of returning from a key slot of the menu screen. The screen manager builds the new screen on a later tick,
; so the switch is asked for here and the editor opened by the tick hook once screen 9 is up (within 10 ticks, else never).
splash_draw:
    ldr r12, =STATE
    ldr r0, [r12, #S_MAGIC]
    ldr r1, =MAGIC
    cmp r0, r1
    bxne lr
    mov r0, #10
    str r0, [r12, #S_PENDING]
    mov r0, #9
    mov r1, #0
    b 0xC0083D28


; r0 = to, r1 = bytes -> r0 = 0 when all of them came
imp_read:
    push {{r4, lr}}
    mov r4, r1
    mov r2, r1
    mov r1, r0
    ldr r0, =FIL
    ldr r3, =BR
    bl FS_READ
    cmp r0, #0
    movne r0, #1
    bne imp_read_out
    ldr r0, =BR
    ldr r0, [r0]
    cmp r0, r4
    movne r0, #1
    moveq r0, #0
imp_read_out:
    pop {{r4, pc}}

; r0 = address, any alignment -> the little endian word there
imp_u32:
    ldrb r1, [r0]
    ldrb r2, [r0, #1]
    orr r1, r1, r2, lsl #8
    ldrb r2, [r0, #2]
    orr r1, r1, r2, lsl #16
    ldrb r2, [r0, #3]
    orr r0, r1, r2, lsl #24
    bx lr

; r0 = to, r1 = from, r2 = bytes, a multiple of 4
memcpy:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne memcpy
    bx lr

{{extra}}
title:
    .asciz "SPLASH SCREEN"
import_path:
    .asciz "{IMPORT_PATH}"
.align 4
widget_vtable:
    .word widget_stub, widget_stub, widget_draw, widget_stub, widget_stub, widget_stub, widget_stub, widget_stub
    .word widget_stub, widget_stub, widget_stub, widget_stub, widget_stub, widget_stub, widget_stub, widget_stub
.pool
"""


def gate(slot):
    """The check each replaced slot starts with (r3 and r12 only)."""
    return f"""
    ldr r12, =STATE
    ldr r12, [r12, #S_MAGIC]
    ldr r3, =MAGIC
    cmp r12, r3
    bne orig{slot}
    ldr r12, =PANEL
    ldr r12, [r12]
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    bne orig{slot}"""


# The synth's start image is at an address that is 2 mod 4 (word loads there would rotate), so the editor copies it a byte at a time.
BYTE_COPY = """memcpyb:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne memcpyb
    bx lr
"""
BUILD = "hacktribe"
OWN_AREAS = [(synthaddr.FREE_FROM, 0xC0200000)]      # the patch's own code, data and state: they keep their addresses in the synth


def source():
    slots = sorted(SLOTS.values())
    gates = "\n".join(f"orig{n}:\n    ldr r12, =ORIG_VT+{4 * n}\n    ldr pc, [r12]" for n in slots)
    synth = BUILD == "synth"
    text = SOURCE.replace("{gates}", gates)
    text = text.replace("{copy_in}", "memcpyb" if synth else "memcpy").replace("{extra}\n", BYTE_COPY if synth else "")
    for n in slots:
        text = text.replace("{gate%d}" % n, gate(n))
    # the text is written with the Sampler's addresses; the synth's are the entries of data/synth-map/
    return synthaddr.source(text, own=OWN_AREAS) if synth else text


FIRMWARE_PLACES = ["ORIG_VTABLE", "VTABLE_LITERAL", "START_CALL", "SPLASH_CALL", "PAGE_SHOWN_1", "PAGE_SHOWN_2", "TICK_HOOK"]


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); our code, data and state stay where they are."""
    global BUILD, PAGES_SHOWN
    target = "synth" if build == "synth" else "hacktribe"
    synthaddr.use(globals(), FIRMWARE_PLACES, target)
    BUILD = target
    PAGES_SHOWN = (PAGE_SHOWN_1, PAGE_SHOWN_2)


def build_code():
    """The assembled sections [(address, bytes)] and the symbols."""
    code = arm.assemble(source())
    return code.sections, code.symbols


def vtable_slots(symbols):
    """slot index -> address of our function."""
    names = {"dtor": "slot_dtor", "dtor_free": "slot_dtor_free", "exit": "slot_exit", "keys": "slot_keys",
             "edit_prev": "slot_edit_prev", "edit_next": "slot_edit_next", "menu": "slot_menu", "value": "slot_value"}
    return {SLOTS[k]: symbols[v] for k, v in names.items()}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target):
    return struct.pack("<I", 0xEA000000 | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def bl(at, target):
    off = (target - (at + 8)) >> 2
    return struct.pack("<I", 0xEB000000 | off & 0xFFFFFF)


def hook(addr, kind, chain, position, swallow, note):
    return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": kind, "chain": chain, "position": position, "swallow": swallow, "note": note}


def build_patch(vsb, build="hacktribe"):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    use_build(build)
    sections, symbols = build_code()
    (a_at, a_code), (b_at, b_code) = sections
    if b_at != IMPORT_ENTRY or DRAW_ENTRY != IMPORT_ENTRY + 4:
        raise SystemExit("the import entry is not at the start of the editor section")
    if a_at + len(a_code) > START_END:
        raise SystemExit(f"start code is {len(a_code):#x} bytes, room for {START_END - START_AT:#x}")
    if b_at + len(b_code) > EDITOR_END:
        raise SystemExit(f"editor code is {len(b_code):#x} bytes, room for {EDITOR_END - EDITOR_AT:#x}")
    if VTABLE_AT + 4 * VTABLE_WORDS > 0xC01A4A00:
        raise SystemExit("vtable copy runs into the power-off picture")
    if STATE + STATE_SIZE > RECBUF or RECBUF + RECORD_SIZE > EDIT or EDIT + IMAGE_BYTES > FIL or FIL + 0x224 > BR or BR + 4 > FREE_END:
        raise SystemExit("state and buffers overlap")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def free(addr, n):
        # Our bytes only go over erased flash image (FF); the buffers we leave alone must be erased too.
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    free(STATE, FREE_END - STATE)
    if struct.unpack("<I", was(TICK_HOOK, 4))[0] != TICK_WORD:
        raise SystemExit("the screen manager's tick does not start with ldrb r3, [r0, #0x4c] in this VSB")
    changes = [
        {"file": file_offset(a_at), "bytes": a_code.hex(), "expect": free(a_at, len(a_code)),
         "note": "start code: draw the stored start image, or the VSB one"},
        {"file": file_offset(b_at), "bytes": b_code.hex(), "expect": free(b_at, len(b_code)),
         "note": "editor: page 20, cursor, WRITE"},
        {"file": file_offset(VTABLE_AT), "copy": {"file": file_offset(ORIG_VTABLE), "length": 4 * VTABLE_WORDS,
                                                  "expect": sha(was(ORIG_VTABLE, 4 * VTABLE_WORDS))},
         "over": [{"at": 4 * slot, "bytes": struct.pack("<I", addr).hex()} for slot, addr in sorted(vtable_slots(symbols).items())],
         "expect": free(VTABLE_AT, 4 * VTABLE_WORDS), "note": "the Global screen's vtable with our slots"},
        {"file": file_offset(VTABLE_LITERAL), "bytes": struct.pack("<I", VTABLE_AT).hex(), "expect": sha(was(VTABLE_LITERAL, 4)),
         "note": "the constructor of screen 9 takes the copy"},
        {"file": file_offset(START_CALL), "bytes": bl(START_CALL, symbols["splash_start"]).hex(), "expect": sha(was(START_CALL, 4)),
         "note": "start hook after the rescue paths"},
        {"file": file_offset(SPLASH_CALL), "bytes": struct.pack("<I", 0xE1A00000).hex(), "expect": sha(was(SPLASH_CALL, 4)),
         "note": "no start image before the rescue paths (nop)"},
        {"file": file_offset(TICK_HOOK), "bytes": branch(TICK_HOOK, symbols["splash_tick"]).hex(), "expect": sha(was(TICK_HOOK, 4)),
         "note": "the screen manager's tick looks whether the BLECH menu asked for the editor"},
    ]
    for at in PAGES_SHOWN:
        changes.append({"file": file_offset(at), "bytes": struct.pack("<I", 0xE3A02015).hex(), "expect": sha(was(at, 4)),
                        "note": "page display shows /21"})
    return {
        "format": "gelumpe-patch", "version": 1, "id": "splash-editor", "name": "Startbild-Editor (Global, Seite 20)",
        "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "changes": changes,
        "hooks": [
            hook(START_CALL, "call", "start", "after", False, "runs the original call, then draws the stored start image"),
            hook(SPLASH_CALL, "call", "start-image", "replace", True, "the early start image call is dropped"),
            hook(TICK_HOOK, "instruction", "frame", "before", False, "opens the editor on the Global screen the BLECH menu asked for"),
            hook(VTABLE_LITERAL, "literal", "global-screen", "replace", True, "the Global screen's class is the copy with our slots"),
            *[hook(at, "instruction", "global-screen", "replace", False, "page display shows /21") for at in PAGES_SHOWN],
        ],
        "startPhase": [
            {"file": file_offset(START_CALL), "length": 4, "why": "the call after the rescue paths now runs splash_start"},
            {"file": file_offset(SPLASH_CALL), "length": 4, "why": "the start image call before the rescue paths is dropped"},
            {"file": file_offset(a_at), "length": len(a_code), "why": "splash_start and what it calls: flash read, CRC, draw; splash_tick, which before the magic word is set only compares it and hands over"},
            {"file": file_offset(TICK_HOOK), "length": 4, "why": "the screen manager's tick runs from the start and now enters splash_tick first"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_SIZE, "run time state of the start code and the editor", "tools/patch/splash_editor.py:STATE"),
            ramdecl.area(RECBUF, EDIT - RECBUF, "the record as read from or about to be written to flash", "tools/patch/splash_editor.py:RECBUF"),
            ramdecl.area(EDIT, FREE_END - EDIT, "the image being edited, the card file and byte count of the import, the rest of the editor's 4 KiB kept free", "tools/patch/splash_editor.py:EDIT"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    p.add_argument("--listing", action="store_true", help="print sizes and symbol addresses")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    use_build(a.build)
    patch = build_patch(raw, a.build)
    if a.listing:
        sections, symbols = build_code()
        for at, code in sections:
            print(f"section {at:#x} + {len(code):#x} bytes")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
