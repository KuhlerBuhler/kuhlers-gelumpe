"""Builds the MFX 2 patch (docs/messungen/2026-10-10-mfx-umschalter.md) for firmware 2.02 with Hacktribe.

TOUCH SCALE becomes a second MASTER FX button. MASTER FX puts the touch pad in
master effect mode with the pattern's own effect type (MFX 1). TOUCH SCALE does
the same with MFX 2, a second type that belongs to the pattern slot: the
effect type switches to it, the TOUCH SCALE LED lights and the MASTER FX LED
goes dark. GATE ARP goes to the firmware's mode Gate Arp + Touch Scale from every mode (pressed
again it does nothing) with only the GATE ARP LED lit, TOUCH SCALE stays dark; the mode itself,
the touch pad's behaviour, is the firmware's. The firmware's Gate Arp alone is not reachable. The old TOUCH SCALE function is
SHIFT + TOUCH SCALE. Internally there is still one effect: this is a fast,
per-pattern shortcut for the type change.

MFX 2 is chosen on the device: while MFX 2 is on, the MFX TYPE page (and every
other type change) edits it, and WRITE stores it with the pattern. The table
(250 entries, default 07 Looper as the display numbers it) is an own flash
record with id, version, length and CRC-32 in a sector no known writer touches.
The pattern itself is always written with its own type (MFX 1).

After power-on the touch pad starts in master effect mode (MASTER FX lit) instead of Touch Scale:
the firmware's start mode is the constant 1 in the touch pad object's constructor, which runs before
the rescue paths, so the patch sets the mode once at the first tick of the main screen, the way a press
of MASTER FX does. With a key held at power-on (EXIT, or one of the firmware's start modes) the mode stays
the firmware's Touch Scale; with EXIT held nothing of the patch runs.

    python3 tools/patch/mfx_switch.py --vsb SYSTEM.VSB [--out data/patches/mfx-switch.json] [--b-type 7]

Four hooks, none in the start phase:
  key dispatcher  first instruction of 0xC00700D8, the buttons
  screen tick     the call of 0xC006F178 at 0xC00836F8, follows pattern changes, sets the start mode
  type setter     first instruction of 0xC0048A64, sees loads and edits
  pattern write   the copy call at 0xC004C2BC, stores MFX 1 and the table

The two LEDs the patch sets itself (TOUCH SCALE 0x1b, MASTER FX 0x1c) go through the firmware's own LED
path (wanted value, then 0xC00875F4), so the firmware's copy of what the panel got, which a device read shows,
stays equal to the panel (docs/messungen/2026-10-14-led-zustand-ram.md).

All four start with the kill switch: EXIT held at power-on, then every call goes
straight to the original. Nothing of the firmware is copied. Every address is a
RAM address of the measured build; the file offset in the VSB is address -
0xC0000000 + 0x100.
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

CODE_AT = 0xC01A5000            # free (FF) run, clear of the splash editor (ends 0xC01A4A00)
CODE_END = 0xC01A5C00
STATE = 0xC01A5C00              # run time state, in RAM only; FF there means "MFX 2 off"
STATE_END = 0xC01A5C40
RECBUF = 0xC01A5D00             # the record as stored, 268 bytes; the table starts at +8
RECBUF_END = 0xC01A5E20
BLECH_MFX = 0xC01D6E1C          # a word of the BLECH menu's state (script-runtime), read here, never written

KEY_HOOK = 0xC00700D8           # first instruction of the key dispatcher, ldr r3, [r0, #4]
KEY_HOOK_WORD = 0xE5903004
KEY_BODY = 0xC00700DC           # the rest of it, entered with r3 = [r0, #4]
TICK_CALL = 0xC00836F8          # bl 0xC006F178, the screen manager's tick
TICK_FUNC = 0xC006F178
SET_HOOK = 0xC0048A64           # first instruction of the type setter, ldr r3, [r0, #4]
SET_BODY = 0xC0048A68
WRITE_CALL = 0xC004C2BC         # bl 0xC000985C, copies the live pattern into the staging buffer
COPY_FUNC = 0xC000985C

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)
LED_GATE = 0x1A                 # GATE ARP, the only one lit in Gate Arp + Touch Scale
LED_ON = 0x1B                   # TOUCH SCALE shows MFX 2
LED_OFF = 0x1C                  # MASTER FX is dark while MFX 2 is on
FLASH_RECORD = 0x7E8000         # a 4 KiB sector no known writer touches, FF in the user's dump
RECORD_ID = int.from_bytes(b"MFX2", "little")
RECORD_VERSION = 1
TABLE_BYTES = 256               # 250 patterns used
RECORD_SIZE = 4 + 2 + 2 + TABLE_BYTES + 4
DEFAULT_TYPE = 7                # display number


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 held keys
.equ LEDMGR, 0xC0345A1C         ; pointer to the LED manager: wanted brightness at +8*led+0x4e, copy of what was sent at +0x88c+8*led
.equ PATTERN, 0xC033E6A4        ; pointer to the pattern being edited, block at +4, type at +0x41
.equ SEQ, 0xC034029C            ; pointer to the sequencer object, pattern number at +0x318
.equ CTL, 0xC06912E0            ; pointer to the touch pad object, mode at +0x334 (0 GA, 1 TS, 2 MFX, 3 both)
.equ MGR, 0xC03404C0            ; pointer to the screen manager
.equ GLOBALS, 0xC0691334        ; pointer to the object the type setter hangs on, +0x4004
.equ PAD_KEY, 0xC006FF94        ; the touch pad's key handler, r1 = key (6 is MASTER FX), sets the mode
.equ SHIFT_OBJ, 0xC0040F04      ; returns the object that holds the SHIFT flag at +0x358
.equ LED_UPDATE, 0xC00875F4     ; (manager, led, 0): compares wanted and sent, copies the entry, queues the panel message
{lock_equ}.equ LED_MODE, 0xC0088118       ; (manager, touch pad mode): the firmware's own LEDs for GATE ARP, TOUCH SCALE, MASTER FX
.equ FLASH_OBJ, 0xC0029A40
.equ FLASH_READ, 0xC0029A74     ; (object, destination, address, length)
.equ FLASH_WRITE, 0xC0029AB8    ; (object, address, length, source)
.equ BUILD_PAGE, 0xC0067270     ; builds the page of a Pattern menu screen
.equ KILL, {kill:#x}
.equ LED_GATE, {led_gate}
.equ BLECH_MFX, {blech_mfx:#x}        ; the BLECH menu's effective MFX 2 setting; stays FF (on) while that menu is not armed
.equ LED_ON, {led_on}
.equ LED_OFF, {led_off}
.equ DEFAULT, {default}
.equ STATE, {state:#x}
.equ S_MODE, 0                  ; 1 while MFX 2 is on
.equ S_A, 4                     ; the pattern's own type
.equ S_B, 8                     ; MFX 2 as applied now
.equ S_IDX, 12                  ; pattern number MFX 2 was applied for
.equ S_PEND, 16                 ; 1 after a pattern was loaded
.equ S_LOADED, 20               ; 1 once the table is in RAM
.equ S_DIRTY, 24                ; 1 when the table differs from flash
.equ S_TICK, 28
.equ S_BOOT, 32                 ; 1 once the start mode was applied
.equ RECBUF, {recbuf:#x}
.equ TABLE, RECBUF+8
.equ FLASH_ADDR, {flash:#x}
.equ REC_LEN, {rec_len:#x}
.equ RECORD_ID, {record_id:#x}
.equ RECORD_VER_LEN, {record_ver_len:#x}

.org {code_at:#x}

; ===================================================== key dispatcher hook
; Entered from the first instruction of the key dispatcher, r0 = this, r1 = key,
; r2 = 1 pressed or 0 released, lr = the caller.
key_hook:
    push {{r4, r5, r6, r7, r8, lr}}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    bl killed
    cmp r0, #0
    bne call_orig
    cmp r6, #1
    bne call_orig
    cmp r5, #5
    beq k_ts
    cmp r5, #6
    beq k_mfx
    cmp r5, #4
    beq k_gate
call_orig:
    mov r0, r4
    mov r1, r5
    mov r2, r6
    bl call_fw
done:
    pop {{r4, r5, r6, r7, r8, pc}}

; TOUCH SCALE
k_ts:
    bl shift_held
    cmp r0, #0
    bne k_shift_ts
    ldr r0, =STATE
    ldr r0, [r0, #S_MODE]
    cmp r0, #1
    beq done
    mov r0, r4
    mov r1, #6
    mov r2, #1
    bl call_fw
    bl pad_mode
    cmp r0, #2
    bne done
    bl enter_mfx2
    b done
; SHIFT + TOUCH SCALE: the old function, with SHIFT cleared for the original
k_shift_ts:
    bl mfx2_sync
    bl leave_mfx2
    bl SHIFT_OBJ
    mov r7, r0
    ldr r8, [r7, #0x358]
    mov r3, #0
    str r3, [r7, #0x358]
    mov r0, r4
    mov r1, r5
    mov r2, r6
    bl call_fw
    str r8, [r7, #0x358]
    bl led_restore
    b done
; MASTER FX: MFX 1 again, the stock press
k_mfx:
    bl shift_held
    cmp r0, #0
    bne call_orig
    bl mfx2_sync
    bl leave_mfx2
    mov r0, r4
    mov r1, r5
    mov r2, r6
    bl call_fw
    bl led_restore
    b done
; GATE ARP: Gate Arp + Touch Scale (touch pad mode 3) from every mode, with the firmware's own presses:
; from 1 its GATE ARP gives 3, from 0 its TOUCH SCALE does, from 2 (Master FX, MFX 2) its GATE ARP gives 0
; and then its TOUCH SCALE 3. In mode 3 the press does nothing. MFX 2 goes off with the mode.
; The mode is the firmware's, only the LEDs differ: the firmware lights GATE ARP and TOUCH SCALE for mode 3,
; led_restore (below) darkens TOUCH SCALE again, so only GATE ARP shows it.
k_gate:
    bl shift_held
    cmp r0, #0
    bne call_orig
    mov r7, #2
g_next:
    bl pad_mode
    cmp r0, #3
    beq g_done
    cmp r0, #0xFF
    beq g_done
    mov r1, #4
    cmp r0, #0
    moveq r1, #5
    mov r0, r4
    mov r2, #1
    bl call_fw
    subs r7, r7, #1
    bne g_next
g_done:
    bl mfx2_sync
    bl leave_mfx2
    bl led_restore
    b done

; the key dispatcher without its first instruction
call_fw:
    push {{lr}}
    ldr r3, [r0, #4]
    bl {body:#x}
    pop {{pc}}

; r0 = 1 when EXIT was held at power-on (or the panel object is not there yet)
killed:
    ldr r0, =BLECH_MFX
    ldr r0, [r0]
    cmp r0, #0
    beq killed_yes
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq killed_yes
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    bne killed_yes
    mov r0, #0
    bx lr
killed_yes:
    mov r0, #1
    bx lr

shift_held:
    push {{lr}}
    bl SHIFT_OBJ
    ldr r0, [r0, #0x358]
    cmp r0, #0
    movne r0, #1
    pop {{pc}}

; r0 = the touch pad mode, 0xFF when there is none
pad_mode:
    ldr r0, =CTL
    ldr r0, [r0]
    cmp r0, #0
    moveq r0, #0xFF
    bxeq lr
    ldr r0, [r0, #0x334]
    bx lr

; ===================================================== MFX 2 on and off
; The touch pad is in master effect mode: remember the pattern's own type, apply MFX 2.
enter_mfx2:
    push {{r4, r5, lr}}
    ldr r4, =STATE
    bl table_load
    ldr r0, =PATTERN
    ldr r5, [r0]
    cmp r5, #0
    beq en_out
    ldr r0, =SEQ
    ldr r0, [r0]
    cmp r0, #0
    beq en_out
    ldr r0, [r0, #0x318]
    cmp r0, #249
    bhi en_out
    str r0, [r4, #S_IDX]
    bl get_b
    str r0, [r4, #S_B]
    ldrb r1, [r5, #0x41]
    str r1, [r4, #S_A]
    mov r1, #0
    str r1, [r4, #S_PEND]
    mov r1, #1
    str r1, [r4, #S_MODE]
    ldr r1, [r4, #S_B]
    bl set_type
    bl refresh_page
    bl led_assert
en_out:
    pop {{r4, r5, pc}}

; back to the pattern's own type, no-op when MFX 2 is off
leave_mfx2:
    push {{r4, lr}}
    ldr r4, =STATE
    ldr r0, [r4, #S_MODE]
    cmp r0, #1
    bne lv_out
    mov r0, #0
    str r0, [r4, #S_MODE]
    ldr r1, [r4, #S_A]
    bl set_type
    bl refresh_page
lv_out:
    pop {{r4, pc}}

; r1 = type (0 based). The firmware's own type change with notification, as the MFX TYPE page makes it.
set_type:
    push {{lr}}
    ldr r0, =PATTERN
    ldr r0, [r0]
    cmp r0, #0
    popeq {{pc}}
    ldrb r2, [r0, #0x41]
    cmp r2, r1
    popeq {{pc}}
    ldr r0, =GLOBALS
    ldr r0, [r0]
    cmp r0, #0
    popeq {{pc}}
    add r0, r0, #0x4000
    add r0, r0, #4
    mov r2, #1
    ldr r3, [r0, #4]
    bl {set_body:#x}
    pop {{pc}}

; r0 = pattern number, returns MFX 2 for it (0 based): the table entry, else the default
get_b:
    ldr r1, =STATE
    ldr r1, [r1, #S_LOADED]
    cmp r1, #1
    bne gb_def
    ldr r1, =TABLE
    ldrb r0, [r1, r0]
    cmp r0, #1
    blo gb_def
    cmp r0, #100
    bhi gb_def
    sub r0, r0, #1
    bx lr
gb_def:
    mov r0, #DEFAULT-1
    bx lr

; ===================================================== following the pattern
; Called after every screen tick (22 per second, the UI task, as the key events are).
mfx2_sync:
    push {{r4, r5, lr}}
    ldr r4, =STATE
    ldr r0, [r4, #S_MODE]
    cmp r0, #1
    bne ms_out
    bl pad_mode
    cmp r0, #2
    beq ms_mode
    mov r0, #0
    str r0, [r4, #S_MODE]
    ldr r1, [r4, #S_A]
    bl set_type
    bl refresh_page
    bl led_restore
    b ms_out
ms_mode:
    ldr r0, =SEQ
    ldr r0, [r0]
    cmp r0, #0
    beq ms_out
    ldr r5, [r0, #0x318]
    cmp r5, #249
    bhi ms_out
    ldr r0, [r4, #S_PEND]
    cmp r0, #0
    bne ms_re
    ldr r0, [r4, #S_IDX]
    cmp r0, r5
    bne ms_re
    ldr r0, [r4, #S_TICK]
    add r0, r0, #1
    str r0, [r4, #S_TICK]
    ands r0, r0, #15
    bne ms_out
    bl led_assert
    b ms_out
; another pattern (or the same one loaded again): its own type came in with the load, apply its MFX 2
ms_re:
    mov r0, #0
    str r0, [r4, #S_PEND]
    str r5, [r4, #S_IDX]
    mov r0, r5
    bl get_b
    str r0, [r4, #S_B]
    mov r1, r0
    bl set_type
    bl refresh_page
    bl led_assert
ms_out:
    pop {{r4, r5, pc}}

; The first touch pad mode after power-on is MASTER FX instead of the firmware's TOUCH SCALE: once, at the
; first tick of the main screen, the key handler of the MASTER FX button runs as for a press. A start with
; any key held (the firmware's start modes) stays as the firmware has it.
; Before the main screen the tick only gets as far as the screen test.
boot_mode:
    push {{r4, lr}}
    ldr r4, =STATE
    ldr r0, [r4, #S_BOOT]
    cmp r0, #1
    beq bm_out
    ldr r0, =MGR
    ldr r0, [r0]
    cmp r0, #0
    beq bm_out
    ldr r0, [r0, #0x2C]
    cmp r0, #1
    bne bm_out
{lock_test}    mov r0, #1
    str r0, [r4, #S_BOOT]
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq bm_out
    ldr r0, [r0, #0x18]
    cmp r0, #0
    bne bm_out
    bl shift_held
    cmp r0, #0
    bne bm_out
    bl pad_mode
    cmp r0, #1
    bne bm_out
    mov r1, #6
    bl PAD_KEY
bm_out:
    pop {{r4, pc}}

tick_hook:
    push {{r4, lr}}
    bl {tick_func:#x}
    bl killed
    cmp r0, #0
    bne tk_out
    bl boot_mode
    bl mfx2_sync
tk_out:
    pop {{r4, pc}}

; ===================================================== type setter hook
; Entered from the first instruction of the setter, r0 = object, r1 = type, r2 = 1 when the
; change is announced. 0 comes from loading a pattern, 1 from the MFX TYPE page and other edits.
set_hook:
    push {{r4, r5, r6, lr}}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    bl killed
    cmp r0, #0
    bne sh_orig
    ldr r3, =STATE
    ldr r0, [r3, #S_MODE]
    cmp r0, #1
    bne sh_orig
    cmp r6, #0
    bne sh_edit
    str r5, [r3, #S_A]
    mov r0, #1
    str r0, [r3, #S_PEND]
    b sh_orig
sh_edit:
    str r5, [r3, #S_B]
    ldr r0, =SEQ
    ldr r0, [r0]
    cmp r0, #0
    beq sh_orig
    ldr r0, [r0, #0x318]
    cmp r0, #249
    bhi sh_orig
    ldr r1, =TABLE
    add r2, r5, #1
    strb r2, [r1, r0]
    mov r0, #1
    str r0, [r3, #S_DIRTY]
sh_orig:
    mov r0, r4
    mov r1, r5
    mov r2, r6
    ldr r3, [r0, #4]
    bl {set_body:#x}
    pop {{r4, r5, r6, pc}}

; ===================================================== pattern write hook
; Replaces the call that copies the live pattern into the staging buffer (r0 = staging).
; The copy gets the pattern's own type, and the table goes to flash when it changed.
write_hook:
    push {{r4, lr}}
    mov r4, r0
    bl {copy_func:#x}
    bl killed
    cmp r0, #0
    bne wh_out
    ldr r3, =STATE
    ldr r0, [r3, #S_MODE]
    cmp r0, #1
    bne wh_dirty
    ldr r0, [r3, #S_A]
    strb r0, [r4, #61]
wh_dirty:
    ldr r0, [r3, #S_DIRTY]
    cmp r0, #1
    bne wh_out
    bl table_save
wh_out:
    pop {{r4, pc}}

; ===================================================== the table in flash
table_load:
    push {{r4, lr}}
    ldr r4, =STATE
    ldr r0, [r4, #S_LOADED]
    cmp r0, #1
    popeq {{r4, pc}}
    mov r0, #1
    str r0, [r4, #S_LOADED]
    bl FLASH_OBJ
    ldr r1, =RECBUF
    ldr r2, =FLASH_ADDR
    ldr r3, =REC_LEN
    bl FLASH_READ
    cmp r0, #0
    beq tl_bad
    ldr r0, =RECBUF
    bl record_valid
    cmp r0, #0
    bne tl_out
tl_bad:
    ldr r0, =TABLE
    mov r1, #0
    mov r2, #64
tl_clear:
    str r1, [r0], #4
    subs r2, r2, #1
    bne tl_clear
tl_out:
    pop {{r4, pc}}

table_save:
    push {{r4, lr}}
    ldr r4, =RECBUF
    ldr r0, =RECORD_ID
    str r0, [r4]
    ldr r0, =RECORD_VER_LEN
    str r0, [r4, #4]
    mov r0, r4
    ldr r1, =REC_LEN-4
    bl crc32
    str r0, [r4, #REC_LEN-4]
    bl FLASH_OBJ
    ldr r1, =FLASH_ADDR
    ldr r2, =REC_LEN
    mov r3, r4
    bl FLASH_WRITE
    cmp r0, #0
    beq ts_out
    ldr r3, =STATE
    mov r0, #0
    str r0, [r3, #S_DIRTY]
ts_out:
    pop {{r4, pc}}

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

; ===================================================== LEDs and the MFX TYPE page
; The LEDs go through the firmware's own path, never straight to the panel. It keeps a copy of what it queued
; (manager + 0x88c + 8 * led, brightness in byte 2), and a read of the LEDs from the device (the editor's
; device mode) shows that copy: a message past the manager leaves the copy at the firmware's value, the opposite
; of what the panel shows (docs/messungen/2026-10-14-led-zustand-ram.md).

; r4 = manager, r1 = led, r2 = brightness: the wanted value, then the firmware's compare, copy and send
led_put:
    push {{lr}}
    add r3, r4, r1, lsl #3
    strb r2, [r3, #0x4e]
    mov r0, r4
    mov r2, #0
    bl LED_UPDATE
    pop {{pc}}

; TOUCH SCALE lit, MASTER FX dark
led_assert:
    push {{r4, lr}}
    ldr r4, =LEDMGR
    ldr r4, [r4]
    cmp r4, #0
    popeq {{r4, pc}}
    mov r1, #LED_ON
    mov r2, #255
    bl led_put
    mov r1, #LED_OFF
    mov r2, #0
    bl led_put
    pop {{r4, pc}}

; the LEDs of the current touch pad mode: modes 0 to 2 by the firmware's own function for them (so no table is
; copied here, and after MFX 2 the LEDs get the firmware's wanted values back); in Gate Arp + Touch Scale
; (mode 3) only GATE ARP is lit, TOUCH SCALE and MASTER FX are dark.
; The firmware sets the LEDs of a mode once, inside the key press (measured: no later write to GATE ARP,
; TOUCH SCALE or MASTER FX while mode 3 stays, through pattern changes, play, menus, WRITE and keys), so one
; call after the press is enough. Its table lights TOUCH SCALE for mode 3, which is why every restore goes
; through here.
led_restore:
    push {{r4, lr}}
    ldr r4, =LEDMGR
    ldr r4, [r4]
    cmp r4, #0
    beq lr_out
    bl pad_mode
    cmp r0, #3
    bhi lr_out                  ; no touch pad object, or a mode the firmware's LED table does not have
    beq lr_gate
    mov r1, r0
    mov r0, r4
    bl LED_MODE
    b lr_out
lr_gate:
    mov r1, #LED_GATE
    mov r2, #255
    bl led_put
    mov r1, #LED_ON
    mov r2, #0
    bl led_put
    mov r1, #LED_OFF
    mov r2, #0
    bl led_put
lr_out:
    pop {{r4, pc}}

; the MFX TYPE page (Pattern menu, page 5) draws its text when it is built: build it again
refresh_page:
    push {{r4, lr}}
    ldr r0, =MGR
    ldr r0, [r0]
    cmp r0, #0
    popeq {{r4, pc}}
    ldr r1, [r0, #0x2C]
    cmp r1, #3
    popne {{r4, pc}}
    ldr r1, [r0, #0x24]
    cmp r1, #0
    popne {{r4, pc}}
    ldr r4, [r0, #0x20]
    cmp r4, #0
    popeq {{r4, pc}}
    ldr r1, [r4, #0x2C]
    cmp r1, #5
    popne {{r4, pc}}
    mov r0, r4
    bl BUILD_PAGE
    pop {{r4, pc}}
lit_pool:
.pool
"""


# The firmware places the patch names, as the Sampler has them. For the synth (the blue Electribe 2) each has its own address in
# data/synth-map/ (mfx-switch.json and auto.json). The panel keys (GATE ARP 4, TOUCH SCALE 5, MASTER FX 6) and the LED ids (0x1a to 0x1c)
# are the same there (docs/messungen/2026-10-16-blau-mfx-switch.md), the patch's own areas keep their addresses.
FIRMWARE_PLACES = ["KEY_HOOK", "KEY_BODY", "TICK_CALL", "TICK_FUNC", "SET_HOOK", "SET_BODY", "WRITE_CALL", "COPY_FUNC"]
BUILD = "hacktribe"


def use_build(build):
    """The places the hooks go to, for `build`: the Sampler's (as the module states them) or the synth's."""
    global BUILD
    BUILD = build
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def sampler_address(name):
    """A firmware place as the Sampler has it, whatever build use_build chose (the source text is mapped as a whole)."""
    return globals().get("_SAMPLER_ADDRESSES", {}).get(name, globals()[name])


# The synth applies its start mode after the firmware releases the input lock.
LOCKED = 0xC002D634             # returns that lock byte (the Sampler's address; the synth's is in data/synth-map/mfx-switch.json)
LOCK_EQU = ".equ LOCKED, {locked:#x}\n"
LOCK_TEST = "    bl LOCKED\n    cmp r0, #0\n    bne bm_out\n"


def source(default_type=DEFAULT_TYPE):
    synth = BUILD == "synth"
    text = SOURCE.format(
        lock_equ=LOCK_EQU.format(locked=LOCKED) if synth else "", lock_test=LOCK_TEST if synth else "",
        kill=KILL_SWITCH, led_gate=LED_GATE, led_on=LED_ON, led_off=LED_OFF, default=default_type, state=STATE, recbuf=RECBUF, blech_mfx=BLECH_MFX,
        flash=FLASH_RECORD, rec_len=RECORD_SIZE, record_id=RECORD_ID, record_ver_len=RECORD_VERSION | (TABLE_BYTES << 16),
        code_at=CODE_AT, body=sampler_address("KEY_BODY"), set_body=sampler_address("SET_BODY"), tick_func=sampler_address("TICK_FUNC"),
        copy_func=sampler_address("COPY_FUNC"))
    if BUILD == "synth":
        text = synthaddr.source(text, own=[(CODE_AT, CODE_END), (STATE, STATE_END), (RECBUF, RECBUF_END)], keep=[BLECH_MFX])
    return text


def build_code(default_type=DEFAULT_TYPE):
    code = arm.assemble(source(default_type))
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def bl_word(at, target):
    return struct.unpack("<I", branch(at, target, True))[0]


def build_patch(vsb, default_type=DEFAULT_TYPE, build="hacktribe"):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    use_build(build)
    if not 1 <= default_type <= 100:
        raise SystemExit("--b-type is the number the display shows, 1 to 100")
    at, code, symbols = build_code(default_type)
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

    for addr, expect, what in ((KEY_HOOK, KEY_HOOK_WORD, "the key dispatcher does not start with ldr r3, [r0, #4]"),
                               (SET_HOOK, KEY_HOOK_WORD, "the type setter does not start with ldr r3, [r0, #4]"),
                               (TICK_CALL, bl_word(TICK_CALL, TICK_FUNC), "the screen tick call is not where the patch expects it"),
                               (WRITE_CALL, bl_word(WRITE_CALL, COPY_FUNC), "the pattern copy call is not where the patch expects it")):
        if word(addr) != expect:
            raise SystemExit(f"{what} in this VSB")
    free(STATE, STATE_END - STATE)
    free(RECBUF, RECBUF_END - RECBUF)

    def hook(addr, name, link, note):
        return {"file": file_offset(addr), "bytes": branch(addr, symbols[name], link).hex(), "expect": sha(was(addr, 4)), "note": note}

    def declare(addr, kind, chain, position, swallow, note):
        return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": kind, "chain": chain, "position": position, "swallow": swallow, "note": note}

    code_at = file_offset(CODE_AT)

    def span(first, last, why):
        end = symbols[last] if last in symbols else CODE_AT + len(code)
        return {"file": file_offset(symbols[first]), "length": end - symbols[first], "why": why}

    return {
        "format": "gelumpe-patch", "version": 1, "id": "mfx-switch",
        "name": f"MFX 2 (TOUCH SCALE, Vorgabe Typ {default_type})",
        "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "MFX 2: key, tick, type setter and pattern write hooks, flash table"},
            hook(KEY_HOOK, "key_hook", False, "first instruction of the key dispatcher jumps to the hook"),
            hook(TICK_CALL, "tick_hook", True, "the screen tick call goes through the hook"),
            hook(SET_HOOK, "set_hook", False, "first instruction of the type setter jumps to the hook"),
            hook(WRITE_CALL, "write_hook", True, "the pattern copy call goes through the hook"),
        ],
        "hooks": [
            declare(KEY_HOOK, "instruction", "key-dispatch", "before", True, "TOUCH SCALE, MASTER FX and SHIFT combinations are handled here, the other keys go on to the original"),
            declare(TICK_CALL, "call", "frame", "after", False, "the original tick runs first, then the hook sets the start mode (once) and follows pattern changes"),
            declare(SET_HOOK, "instruction", "type-set", "before", False, "sees every type change, then enters the original"),
            declare(WRITE_CALL, "call", "pattern-write", "after", False, "the original copy runs first, then the hook sets the pattern's own type"),
        ],
        "startPhase": [
            {"file": file_offset(SET_HOOK), "length": 4, "why": "the type setter runs when the first pattern is loaded (about 99 ms, after the rescue paths at 75 ms) and jumps to set_hook"},
            {"file": file_offset(TICK_CALL), "length": 4, "why": "the screen tick runs before the main screen (about 340 ms) and now calls tick_hook"},
            span("killed", "shift_held", "the kill switch test every hook starts with"),
            span("mfx2_sync", "write_hook", "mfx2_sync, boot_mode, tick_hook and set_hook: at start they only test the kill switch, the screen and that MFX 2 is off"),
            span("lit_pool", "end", "the literal words those functions load"),
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state, FF means MFX 2 off", "tools/patch/mfx_switch.py:STATE"),
            ramdecl.area(RECBUF, RECBUF_END - RECBUF, "the table record as stored in flash, 268 bytes", "tools/patch/mfx_switch.py:RECBUF"),
        ],
        "shares": [
            ramdecl.share(BLECH_MFX, 4, "script-runtime", "the BLECH menu's effective MFX 2 setting, read at every hook (MENU_STATE + M_EFF_MFX)", "tools/patch/mfx_switch.py:BLECH_MFX"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    p.add_argument("--b-type", type=int, default=DEFAULT_TYPE, help="MFX 2 where the table has no entry, as the display numbers it (7 = Looper)")
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    use_build(a.build)
    patch = build_patch(raw, a.b_type, a.build)
    if a.listing:
        at, code, symbols = build_code(a.b_type)
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
