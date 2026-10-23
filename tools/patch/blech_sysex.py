"""Builds the BLECH SysEx patch (docs/messungen/2026-10-15-blech-sysex.md) for firmware 2.02, Hacktribe and Korg's own build.

BLECH's own commands for reading and writing RAM over MIDI, in large blocks, each block with a CRC-32 and an answer that
says how it went. They work on Korg's original with BLECH too, which has none of Hacktribe's commands 0x52 to 0x57, and
they are written here from the protocol up, nothing of Hacktribe's code is used. The message is Korg's frame,
F0 42 3n 00 01 24 <function> <7-bit packed words> F7, with n the global channel.

    function  from the host                                      answer function
    0x60      INFO: nothing                                      0x68
    0x61      READ: address, length                              0x69  status, address, length, CRC-32, the bytes
    0x62      WRITE BEGIN: address, length, CRC-32 of the bytes  0x6A  status, address, length
    0x63      WRITE DATA: the bytes, as many as BEGIN said       0x6B  status, address, length, CRC-32 read back
    0x64      FLASH READ: address, length                        0x6C  status, address, length, CRC-32, the bytes
    0x65      FILE READ: offset, length (0 for the size only)    0x6D  status, offset, length, CRC-32, file size, the bytes
    0x66      FILE BEGIN: offset, length, CRC-32 of the bytes    0x6E  status, offset, length; WRITE DATA follows
    0x67      PLUGIN BEGIN: offset, length, CRC-32, 16 bytes name 0x6E  status, offset, length; WRITE DATA follows

PLUGIN BEGIN writes a plugin file, SD:KORG/blechtribe/Plugin/<name>.blech, where IMPORT PLUGIN of the BLECH menu lists it
(tools/patch/script_menu.s). The name is 1 to 16 letters, digits, "_" or "-", zero bytes after it; anything else is refused
with status 3, so no path can be built from it. Otherwise it works like FILE BEGIN (offset 0 makes the file anew, the block is
read back from the card for the CRC).

The two FILE commands reach exactly two files of the card, chosen by bit 31 of the offset: the update file
KORG/<folder>/System/SYSTEM.VSB (bit clear) and beside it ORIGINAL.BIN (bit set), where the editor keeps the unpatched file the
next update starts from (a patched file cannot be patched again; not .VSB, so no updater takes it). The path is built
with the firmware's own function the update uses (0xC0035720, "KORG/blechtribe/" on the Sampler with BLECH, "KORG/electribe/"
on the synth), so the file lands where Korg's update looks for it. A FILE BEGIN at offset 0 makes the file anew, every other
writes into the existing one; every block is read back from the card and its CRC sent. Offset plus length never passes
0x200100, the size of a VSB. Status 6 is a card error (no card, no file, card full). The firmware's update writes the flash
from that file when the user starts it; nothing here writes the flash.

Every field is a 32-bit little endian word (the status too), the words are packed as every Electribe SysEx payload is
(src/bytes.mjs). The status is 0 for ok, 1 for a CRC that does not match, 2 for refused, 3 for out of range, 5 when the bytes
read back after the copy differ. A BEGIN that is answered with 0 declares one DATA message; a DATA message without it is not
taken in at all. The firmware refuses by its own table (the protection of data/protected.mjs, src/sysex-table.mjs): outside
the RAM window of 128 MiB, in every region a write must not touch (the table says which windows of a region the editor may write),
and in the mirror of such a region. The commands touch RAM only; there is no flash command and no execute command.

Two hooks, none in the start phase and none that does anything before the main screen:
  0xC0026A8C  the function that sorts a SysEx function byte into how many bytes follow and where they go; our four
              function bytes are taken here, the receive state machine then decodes the bytes straight into a buffer
  0xC0026418  the function that runs a received message in CommandTask; ours are run here

Every message of ours is decoded into our own buffer first, checked against its CRC, and only then copied to the address. A
reply is built in the same buffer, packed in place from the end, and sent through the firmware's own reply path (the lock that
keeps the parser quiet while it goes out, the output queues of USB and DIN, the port the request came in on).

With EXIT held at power-on both hooks pass everything on: the four function bytes are not taken and the device is silent
to them, as with Korg's original without the patch (docs/patcher.md, "Notschalter").

    python3 tools/patch/blech_sysex.py --vsb SYSTEM.VSB --table table.bin --build hacktribe|stock [--out data/patches/blech-sysex.json]

The table is made by tools/patch/blech_sysex.mjs from data/protected.mjs, one for each build (the regions the editor writes
differ: Hacktribe keeps its presets in two tables, Korg's build scattered). Every address is a RAM address of the measured
build; the file offset in the VSB is address - 0xC0000000 + 0x100.
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

CODE_AT = 0xC0172100            # free (FF) in the image, behind Hacktribe's code (ends 0xC01720B0) and clear of every other patch
CODE_END = 0xC0173800
TABLE_AT = 0xC0173800           # the protection table, 412 bytes today (src/sysex-table.mjs)
TABLE_END = 0xC0174000
STATE = 0xC0191000              # run time state, in RAM only (behind the synth filters' 0xC0190000 to 0xC0190100)
STATE_END = 0xC0191100
BUF = 0xC0191100                # the buffer a message is decoded into and a reply is packed in
MAX_BLOCK = 0x8000              # bytes in one READ or WRITE DATA
MAX_REPLY_HEADER = 20
# Packed frame, its group bytes, and up to three bytes lost aligning the raw source.
BUFFER_REQUIRED = MAX_BLOCK + MAX_REPLY_HEADER + (MAX_BLOCK + MAX_REPLY_HEADER + 6) // 7 + 8 + 3
BUF_END = BUF + ((BUFFER_REQUIRED + 255) & ~255)
FILE_AREA = 0xC019F000          # FatFs file object (0x224 bytes, measured), the count of bytes read or written, the path
FILE_AREA_END = 0xC01A0000
FILE_LIMIT = 0x200100           # offset plus length of a FILE command: the size of a VSB
FILE_OTHER = 0x80000000         # bit 31 of a FILE offset: ORIGINAL.BIN instead of SYSTEM.VSB
NAME_MAX = 16                   # characters of a plugin file's name (PLUGIN BEGIN)

# STATE: +0 pending (the magic below when a BEGIN waits for its DATA), +4 address, +8 length, +12 CRC,
# +0x10 a request as decoded, +0x20 the words of a short reply, +0x40 where a short reply is packed
S_PENDING, S_ADDR, S_LEN, S_CRC, S_REQ, S_MODE, S_RAW, S_OUT = 0, 4, 8, 12, 0x10, 0x1C, 0x20, 0x40   # S_MODE 1: the declared write goes to SYSTEM.VSB, 2 to ORIGINAL.BIN
PENDING_MAGIC = 0x444E4550      # "PEND": the image is FF where it has not been written, so 0 and FF both mean nothing waits

FUNC_INFO, FUNC_READ, FUNC_BEGIN, FUNC_DATA, FUNC_FLASH, FUNC_FREAD, FUNC_FBEGIN, FUNC_PBEGIN = 0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67
REPLY_INFO, REPLY_READ, REPLY_BEGIN, REPLY_DATA, REPLY_FLASH, REPLY_FREAD, REPLY_FBEGIN = 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E
STATUS_OK, STATUS_BAD_CRC, STATUS_REFUSED, STATUS_RANGE, STATUS_FLASH, STATUS_VERIFY, STATUS_FILE = 0, 1, 2, 3, 4, 5, 6
PROTOCOL_VERSION = 1
FLAGS = 0x3F                    # bit 0 read, bit 1 write, bit 2 CRC-32, bit 3 FLASH READ (read only, no flash write exists), bit 4 the update file, bit 5 plugin files
FLASH_MAX = 0x1000              # bytes in one FLASH READ: the sector size, the largest piece the firmware's own flash code takes at once
FLASH_LIMIT = 0x1000000         # the end of the 16 MiB flash; a request from 0x1000000 on hung the device (docs/speicherbereiche.md), so none reaches it

CLASSIFY_HOOK = 0xC0026A8C      # cmp r1, #0x1c, the first instruction of the function that sorts the function byte
CLASSIFY_WORD = 0xE351001C
CLASSIFY_BACK = 0xC0026A90
PROCESS_HOOK = 0xC0026418       # push {r0-r6, lr}, the first instruction of the function that runs a received message
PROCESS_WORD = 0xE92D407F
PROCESS_BACK = 0xC002641C

PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 the keys held at power-on
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)
DESC = 0xC033E6CC               # where the receive state machine puts the bytes: pointer, bytes left, bytes in, +0x10 and +0x11 the packing state
FLAG = 0xC033E6C9               # set when a message is complete, so that the F7 after it hands the message on
CHANNEL = 0xC00F930F            # the global channel, 0 to 15
PORT_OF = 0xC0026260            # r0 = message, returns 1 (USB), 2 (DIN) or -1 from where the message came in
TX_BEGIN = 0xC0027D54           # takes the lock that keeps the parser quiet while a reply goes out
TX_SEND = 0xC0027834            # (r0 unused, r1 = bytes, r2 = length, r3 = port) puts the bytes into the output queue of the port
TX_END = 0xC0027D6C
MODEL = 0x24                    # the model byte of the frame: 0x24 on the Sampler, 0x23 on the blue Electribe 2 (the device search of its firmware answers it)
FLASH_OBJ = 0xC0029A40          # returns the flash object (the one the MFX 2 patch reads its table with)
FLASH_READ = 0xC0029A74         # (object, destination, flash address, length): takes the firmware's lock, calls the driver, 1 on success
FS_OPEN, FS_READ, FS_WRITE, FS_CLOSE, FS_LSEEK = 0xC009DB60, 0xC009DD74, 0xC009DFB8, 0xC009E3DC, 0xC009E404   # FatFs (docs/hintergrund/virtuelle-sd.md)
FOLDER = 0xC0035720             # (string object, id): the card folder the update reads from, "KORG/blechtribe/" with BLECH (measured)
FOLDER_ID = 0x124               # the id the update passes (0x123 in the synth)
STRING_FREE = 0xC00A21D4        # frees such a string object, as the update does after reading it
FIL_SIZE = 0x0C                 # the file size in a FatFs file object (measured on both builds)
WINDOW = (0xC0000000, 0xC8000000)
MIRROR = 0x4000000


def crc_nibbles():
    """The 16 words of the CRC-32 (polynomial 0xEDB88320) for a nibble at a time."""
    out = []
    for i in range(16):
        c = i
        for _ in range(4):
            c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
        out.append(c)
    return out


def sha(data):
    return hashlib.sha256(data).hexdigest()


CRC_WORDS = ", ".join(f"{w:#010x}" for w in crc_nibbles())

def source():
    return f"""
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ DESC, {DESC:#x}
.equ FLAG, {FLAG:#x}
.equ CHANNEL, {CHANNEL:#x}
.equ PORT_OF, {PORT_OF:#x}
.equ TX_BEGIN, {TX_BEGIN:#x}
.equ TX_SEND, {TX_SEND:#x}
.equ TX_END, {TX_END:#x}
.equ MODEL, {MODEL:#x}
.equ FLASH_OBJ, {FLASH_OBJ:#x}
.equ FLASH_READ, {FLASH_READ:#x}
.equ FS_OPEN, {FS_OPEN:#x}
.equ FS_READ, {FS_READ:#x}
.equ FS_WRITE, {FS_WRITE:#x}
.equ FS_CLOSE, {FS_CLOSE:#x}
.equ FS_LSEEK, {FS_LSEEK:#x}
.equ FOLDER, {FOLDER:#x}
.equ FOLDER_ID, {FOLDER_ID:#x}
.equ STRING_FREE, {STRING_FREE:#x}
.equ FIL_SIZE, {FIL_SIZE:#x}
.equ FILE_FIL, {FILE_AREA:#x}
.equ FILE_BR, {FILE_AREA + 0x240:#x}
.equ FILE_PATH, {FILE_AREA + 0x280:#x}
.equ FILE_NAME, {FILE_AREA + 0x300:#x}
.equ NAME_MAX, {NAME_MAX}
.equ FILE_LIMIT, {FILE_LIMIT:#x}
.equ S_MODE, {S_MODE}
.equ FLASH_MAX, {FLASH_MAX:#x}
.equ FLASH_LIMIT, {FLASH_LIMIT:#x}
.equ CLASSIFY_BACK, {CLASSIFY_BACK:#x}
.equ PROCESS_BACK, {PROCESS_BACK:#x}
.equ TABLE, {TABLE_AT:#x}
.equ STATE, {STATE:#x}
.equ BUF, {BUF:#x}
.equ BUF_END, {BUF_END:#x}
.equ MAX_BLOCK, {MAX_BLOCK:#x}
.equ MAGIC, {PENDING_MAGIC:#x}
.equ WIN_START, {WINDOW[0]:#x}
.equ WIN_END, {WINDOW[1]:#x}
.equ MIRROR, {MIRROR:#x}
.equ HALF, {WINDOW[0] + MIRROR:#x}
.equ S_ADDR, {S_ADDR}
.equ S_LEN, {S_LEN}
.equ S_CRC, {S_CRC}
.equ S_REQ, {S_REQ}
.equ S_RAW, {S_RAW}
.equ S_OUT, {S_OUT}
.equ FLAGS, {FLAGS}
.equ VERSION, {PROTOCOL_VERSION}

.org {CODE_AT:#x}

; ---- hook 1: the function byte ------------------------------------------------------------------------------------
; Entered instead of the first instruction of the function at 0xC0026A8C. r0 = the parser's state object, r1 = the function byte.
; It returns the state the parser goes on in. For anything but our four bytes it is the original instruction and the original function.
classify_hook:
    sub r2, r1, #0x60
    cmp r2, #8
    blo classify_ours
    cmp r1, #0x1c
    b CLASSIFY_BACK

classify_ours:
    push {{r4, lr}}
    mov r4, r0
    strb r1, [r4, #0x10]
    strb r1, [r4]
    bl killed
    cmp r0, #0
    bne classify_reject
    ldr r3, =DESC
    ldr r12, =STATE
    cmp r1, #0x60
    beq classify_empty
    cmp r1, #0x63
    beq classify_data
    add r0, r12, #S_REQ
    cmp r1, #0x62
    cmpne r1, #0x66
    moveq r2, #12
    movne r2, #8
    cmp r1, #0x67
    moveq r2, #12+NAME_MAX
    b classify_receive
classify_data:
    ldr r2, [r12]
    ldr r0, =MAGIC
    cmp r2, r0
    bne classify_reject
    ldr r2, [r12, #S_LEN]
    ldr r0, =BUF
classify_receive:
    str r0, [r4, #4]
    str r0, [r3]
    str r2, [r3, #4]
    mov r2, #0
    str r2, [r3, #8]
    strb r2, [r3, #0x10]
    strb r2, [r3, #0x11]
    mov r0, #0x1e
    pop {{r4, pc}}
classify_empty:
    ldr r3, =FLAG
    mov r2, #1
    strb r2, [r3]
    mov r0, #0
    pop {{r4, pc}}
classify_reject:
    mvn r3, #0
    strb r3, [r4, #0x10]
    mov r0, #0
    pop {{r4, pc}}
.pool

; r0 = 1 when EXIT was held at power-on (or the panel object is not there yet); touches r0 only
killed:
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    moveq r0, #1
    bxeq lr
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    movne r0, #1
    moveq r0, #0
    bx lr
.pool

; ---- hook 2: the message --------------------------------------------------------------------------------------------
; Entered instead of the first instruction of the function at 0xC0026418, r0 = the received message, byte 0 its function.
process_hook:
    ldrb r12, [r0]
    sub r12, r12, #0x60
    cmp r12, #8
    blo process_ours
    push {{r0, r1, r2, r3, r4, r5, r6, lr}}
    b PROCESS_BACK

process_ours:
    push {{r3, r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    mov r4, r0
    bl killed
    cmp r0, #0
    bne process_done
    ldrb r5, [r4]
    ldr r6, =STATE
    mov r0, r4
    bl PORT_OF
    mov r7, r0
    cmp r5, #0x60
    beq do_info
    cmp r5, #0x61
    beq do_read
    cmp r5, #0x62
    beq do_begin
    cmp r5, #0x64
    beq do_flash
    cmp r5, #0x65
    beq do_fread
    cmp r5, #0x66
    beq do_fbegin
    cmp r5, #0x67
    beq do_pbegin
    b do_data
process_done:
    pop {{r3, r4, r5, r6, r7, r8, r9, r10, r11, pc}}
.pool

; INFO: status, version, flags, largest block, CRC-32 of the table, 0
do_info:
    add r8, r6, #S_RAW
    mov r3, #0
    str r3, [r8]
    mov r3, #VERSION
    str r3, [r8, #4]
    mov r3, #FLAGS
    str r3, [r8, #8]
    ldr r3, =MAX_BLOCK
    str r3, [r8, #12]
    ldr r0, =TABLE
    ldr r1, [r0]
    add r1, r1, r1, lsl #1
    ldr r2, [r0, #4]
    add r2, r2, r2, lsl #2
    add r1, r1, r2
    add r1, r1, #2
    lsl r1, r1, #2
    bl crc32
    str r0, [r8, #16]
    ldr r3, =FLASH_MAX
    str r3, [r8, #20]
    mov r0, #{REPLY_INFO}
    mov r1, r8
    mov r2, #24
    add r3, r6, #S_OUT
    b reply_tail

; READ: the bytes go into the end of BUF behind four words, the CRC is taken over that copy, the reply is packed in place
do_read:
    ldr r8, [r6, #S_REQ]
    ldr r9, [r6, #S_REQ + 4]
    mov r0, r8
    mov r1, r9
    mov r2, #0
    bl policy
    cmp r0, #0
    bne read_failed
    ldr r10, =BUF_END
    sub r10, r10, r9
    bic r10, r10, #3
    mov r0, r10
    mov r1, r8
    mov r2, r9
    bl memcpy
    mov r0, r10
    mov r1, r9
    bl crc32
    sub r11, r10, #16
    str r0, [r11, #12]
    mov r3, #0
    str r3, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    mov r0, #{REPLY_READ}
    mov r1, r11
    add r2, r9, #16
    ldr r3, =BUF
    b reply_tail
read_failed:
    add r11, r6, #S_RAW
    str r0, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    mov r3, #0
    str r3, [r11, #12]
    mov r0, #{REPLY_READ}
    mov r1, r11
    mov r2, #16
    add r3, r6, #S_OUT
    b reply_tail

; FLASH READ: address, length. Reads the flash through the firmware's own read function into the end of BUF, like READ does with RAM,
; and answers status, address, length, CRC-32 and the bytes. The only thing that is checked is the range: 1 to FLASH_MAX bytes,
; wholly below FLASH_LIMIT (no carry). Nothing here writes or erases; the reply is the whole effect. Status 3 range, 4 the flash
; function did not report success.
do_flash:
    ldr r8, [r6, #S_REQ]
    ldr r9, [r6, #S_REQ + 4]
    mov r4, #{STATUS_RANGE}
    cmp r9, #0
    beq flash_failed
    ldr r3, =FLASH_MAX
    cmp r9, r3
    bhi flash_failed
    adds r0, r8, r9
    bcs flash_failed
    ldr r3, =FLASH_LIMIT
    cmp r0, r3
    bhi flash_failed
    ldr r10, =BUF_END
    sub r10, r10, r9
    bic r10, r10, #3
    bl FLASH_OBJ
    mov r1, r10
    mov r2, r8
    mov r3, r9
    bl FLASH_READ
    cmp r0, #1
    movne r4, #{STATUS_FLASH}
    bne flash_failed
    mov r0, r10
    mov r1, r9
    bl crc32
    sub r11, r10, #16
    str r0, [r11, #12]
    mov r3, #0
    str r3, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    mov r0, #{REPLY_FLASH}
    mov r1, r11
    add r2, r9, #16
    ldr r3, =BUF
    b reply_tail
flash_failed:
    add r11, r6, #S_RAW
    str r4, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    mov r3, #0
    str r3, [r11, #12]
    mov r0, #{REPLY_FLASH}
    mov r1, r11
    mov r2, #16
    add r3, r6, #S_OUT
    b reply_tail
.pool

; WRITE BEGIN: the range is checked now, so that a refusal comes before the bytes are sent, and kept for the DATA that follows
do_begin:
    ldr r8, [r6, #S_REQ]
    ldr r9, [r6, #S_REQ + 4]
    ldr r10, [r6, #S_REQ + 8]
    mov r3, #0
    str r3, [r6]
    str r3, [r6, #S_MODE]
    mov r0, r8
    mov r1, r9
    mov r2, #1
    bl policy
    cmp r0, #0
    bne begin_reply
    str r8, [r6, #S_ADDR]
    str r9, [r6, #S_LEN]
    str r10, [r6, #S_CRC]
    ldr r3, =MAGIC
    str r3, [r6]
begin_reply:
    add r11, r6, #S_RAW
    str r0, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    mov r0, #{REPLY_BEGIN}
    mov r1, r11
    mov r2, #12
    add r3, r6, #S_OUT
    b reply_tail
.pool

; WRITE DATA: CRC of what arrived, the range again, the copy, the CRC of what is there now
do_data:
    ldr r0, [r6]
    ldr r1, =MAGIC
    cmp r0, r1
    bne process_done
    ldr r8, [r6, #S_ADDR]
    ldr r9, [r6, #S_LEN]
    ldr r10, [r6, #S_CRC]
    mov r0, #0
    str r0, [r6]
    ldr r0, =BUF
    mov r1, r9
    bl crc32
    mov r11, r0
    cmp r11, r10
    movne r4, #{STATUS_BAD_CRC}
    bne data_reply
    ldr r0, [r6, #S_MODE]
    sub r0, r0, #1
    cmp r0, #3                  ; 1 SYSTEM.VSB, 2 ORIGINAL.BIN, 3 a plugin file
    blo data_file
    mov r0, r8
    mov r1, r9
    mov r2, #1
    bl policy
    movs r4, r0
    movne r11, #0
    bne data_reply
    mov r0, r8
    ldr r1, =BUF
    mov r2, r9
    bl memcpy
    mov r0, r8
    mov r1, r9
    bl crc32
    mov r11, r0
    cmp r11, r10
    moveq r4, #{STATUS_OK}
    movne r4, #{STATUS_VERIFY}
    b data_reply
; the declared write goes to the update file: written, closed, then read back from the card for the CRC
data_file:
    ldr r5, [r6, #S_MODE]
    sub r5, r5, #1              ; which file
    mov r0, #0
    str r0, [r6, #S_MODE]
    mov r0, r5
    bl file_path
    ldr r0, =FILE_FIL
    ldr r1, =FILE_PATH
    cmp r8, #0
    moveq r2, #0x0A             ; FA_CREATE_ALWAYS | FA_WRITE: the first block makes the file anew
    movne r2, #0x03             ; FA_OPEN_EXISTING | FA_READ | FA_WRITE
    bl FS_OPEN
    cmp r0, #0
    bne data_file_error
    ldr r0, =FILE_FIL
    mov r1, r8
    bl FS_LSEEK
    cmp r0, #0
    bne data_file_close
    ldr r0, =FILE_FIL
    ldr r1, =BUF
    mov r2, r9
    ldr r3, =FILE_BR
    bl FS_WRITE
    cmp r0, #0
    bne data_file_close
    ldr r0, =FILE_BR
    ldr r0, [r0]
    cmp r0, r9
    bne data_file_close
    ldr r0, =FILE_FIL
    bl FS_CLOSE
    cmp r0, #0
    bne data_file_error
    mov r0, r8
    mov r1, r9
    mov r2, r5
    bl file_read_back
    cmp r0, #0
    bne data_file_error
    ldr r0, =BUF_END
    sub r0, r0, r9
    bic r0, r0, #3
    mov r1, r9
    bl crc32
    mov r11, r0
    cmp r11, r10
    moveq r4, #{STATUS_OK}
    movne r4, #{STATUS_VERIFY}
    b data_reply
data_file_close:
    ldr r0, =FILE_FIL
    bl FS_CLOSE
data_file_error:
    mov r4, #{STATUS_FILE}
    mov r11, #0
data_reply:
    add r0, r6, #S_RAW
    str r4, [r0]
    str r8, [r0, #4]
    str r9, [r0, #8]
    str r11, [r0, #12]
    mov r1, r0
    mov r0, #{REPLY_DATA}
    mov r2, #16
    add r3, r6, #S_OUT
reply_tail:
    bl send_reply
    b process_done
.pool

.pool

; FILE BEGIN: offset, length, CRC: the range is checked now and the write declared for the file; the DATA that follows carries the bytes
do_fbegin:
    ldr r8, [r6, #S_REQ]
    ldr r9, [r6, #S_REQ + 4]
    ldr r10, [r6, #S_REQ + 8]
    mov r3, #0
    str r3, [r6]
    mov r5, r8, lsr #31         ; which file: 0 SYSTEM.VSB, 1 ORIGINAL.BIN (r5, the function byte, is not needed any more)
    bic r8, r8, #0x80000000
fbegin_checked:
    ldr r10, [r6, #S_REQ + 8]
    mov r0, #{STATUS_RANGE}
    cmp r9, #0
    beq fbegin_reply
    ldr r3, =MAX_BLOCK
    cmp r9, r3
    bhi fbegin_reply
    adds r3, r8, r9
    bcs fbegin_reply
    ldr r2, =FILE_LIMIT
    cmp r3, r2
    bhi fbegin_reply
    str r8, [r6, #S_ADDR]
    str r9, [r6, #S_LEN]
    str r10, [r6, #S_CRC]
    add r3, r5, #1
    str r3, [r6, #S_MODE]
    ldr r3, =MAGIC
    str r3, [r6]
    mov r0, #{STATUS_OK}
fbegin_reply:
    add r11, r6, #S_RAW
    str r0, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    mov r0, #{REPLY_FBEGIN}
    mov r1, r11
    mov r2, #12
    add r3, r6, #S_OUT
    b reply_tail

; PLUGIN BEGIN: offset, length, CRC, the name. The name is checked and kept for the path, then it is a FILE BEGIN of file 2.
do_pbegin:
    ldr r8, [r6, #S_REQ]
    ldr r9, [r6, #S_REQ + 4]
    mov r3, #0
    str r3, [r6]
    add r1, r6, #S_REQ + 12      ; the name as received (it reaches over S_MODE and S_RAW, both written only after it is copied)
    ldr r2, =FILE_NAME
    mov r3, #0                   ; characters
    mov r0, #{STATUS_RANGE}
pb_char:
    ldrb r12, [r1, r3]
    cmp r12, #0
    beq pb_end
    cmp r12, #0x2D               ; "-"
    cmpne r12, #0x5F             ; "_"
    beq pb_ok
    sub r10, r12, #0x30
    cmp r10, #10
    blo pb_ok
    orr r10, r12, #0x20
    sub r10, r10, #0x61
    cmp r10, #26
    bhs fbegin_reply
pb_ok:
    strb r12, [r2, r3]
    add r3, r3, #1
    cmp r3, #NAME_MAX
    blo pb_char
pb_end:
    cmp r3, #0
    beq fbegin_reply
    mov r12, #0
    strb r12, [r2, r3]
pb_rest:                         ; zero bytes only behind the name
    cmp r3, #NAME_MAX
    bhs pb_named
    ldrb r12, [r1, r3]
    cmp r12, #0
    bne fbegin_reply
    add r3, r3, #1
    b pb_rest
pb_named:
    bic r8, r8, #0x80000000
    str r8, [r6, #S_REQ]
    mov r5, #2
    b fbegin_checked

; FILE READ: offset, length (0 asks for the size only). The bytes go into the end of BUF behind five words, like READ;
; at the end of the file fewer come back, the length word says how many.
do_fread:
    ldr r8, [r6, #S_REQ]
    ldr r9, [r6, #S_REQ + 4]
    mov r11, r8, lsr #31        ; which file: 0 SYSTEM.VSB, 1 ORIGINAL.BIN
    bic r8, r8, #0x80000000
    mov r4, #{STATUS_RANGE}
    mov r5, #0
    ldr r3, =MAX_BLOCK
    cmp r9, r3
    bhi fread_failed
    adds r3, r8, r9
    bcs fread_failed
    ldr r2, =FILE_LIMIT
    cmp r3, r2
    bhi fread_failed
    mov r0, r8
    mov r1, r9
    mov r2, r11
    bl file_read_back
    mov r4, r0
    ldr r5, =FILE_FIL
    ldr r5, [r5, #FIL_SIZE]
    cmp r4, #0
    movne r5, #0
    bne fread_failed
    ldr r9, =FILE_BR
    ldr r9, [r9]
    ldr r10, =BUF_END
    ldr r3, [r6, #S_REQ + 4]
    sub r10, r10, r3
    bic r10, r10, #3
    mov r0, r10
    mov r1, r9
    bl crc32
    sub r11, r10, #20
    str r0, [r11, #12]
    mov r3, #0
    str r3, [r11]
    str r8, [r11, #4]
    str r9, [r11, #8]
    str r5, [r11, #16]
    mov r0, #{REPLY_FREAD}
    mov r1, r11
    add r2, r9, #20
    ldr r3, =BUF
    b reply_tail
fread_failed:
    add r11, r6, #S_RAW
    str r4, [r11]
    str r8, [r11, #4]
    mov r3, #0
    str r3, [r11, #8]
    str r3, [r11, #12]
    str r5, [r11, #16]
    mov r0, #{REPLY_FREAD}
    mov r1, r11
    mov r2, #20
    add r3, r6, #S_OUT
    b reply_tail
.pool

; r0 = offset, r1 = length, r2 = which file: its bytes from there into the end of BUF (rounded down to a word, as READ does), the
; count in FILE_BR and the size in the file object; returns r0 = 0, or STATUS_FILE when the card says no. Keeps r4 to r11.
file_read_back:
    push {{r4, r5, r6, lr}}
    mov r4, r0
    mov r5, r1
    mov r0, r2
    bl file_path
    ldr r0, =FILE_BR
    mov r1, #0
    str r1, [r0]
    ldr r0, =FILE_FIL
    ldr r1, =FILE_PATH
    mov r2, #1                  ; FA_READ
    bl FS_OPEN
    cmp r0, #0
    bne frb_error
    ldr r0, =FILE_FIL
    mov r1, r4
    bl FS_LSEEK
    cmp r0, #0
    bne frb_close
    cmp r5, #0
    beq frb_done
    ldr r1, =BUF_END
    sub r1, r1, r5
    bic r1, r1, #3
    ldr r0, =FILE_FIL
    mov r2, r5
    ldr r3, =FILE_BR
    bl FS_READ
    cmp r0, #0
    bne frb_close
frb_done:
    ldr r0, =FILE_FIL
    bl FS_CLOSE
    cmp r0, #0
    bne frb_error
    mov r0, #0
    pop {{r4, r5, r6, pc}}
frb_close:
    ldr r0, =FILE_FIL
    bl FS_CLOSE
frb_error:
    mov r0, #{STATUS_FILE}
    pop {{r4, r5, r6, pc}}

; r0 = which: FILE_PATH = the update's folder (the firmware's own function, as the update builds it) + "System/SYSTEM.VSB", or
; "System/ORIGINAL.BIN" for 1; for 2 the plugin file SD:KORG/blechtribe/Plugin/<FILE_NAME>.blech. Keeps r4 to r11.
file_path:
    cmp r0, #2
    beq plugin_path
    push {{r4, r5, lr}}
    mov r4, r0
    sub sp, sp, #0x10
    mov r0, sp
    ldr r1, =FOLDER_ID
    bl FOLDER
    ldr r1, [sp]
    ldr r0, =FILE_PATH
    mov r2, #0x3F               ; at most 63 characters of the folder
fp_folder:
    ldrb r3, [r1], #1
    cmp r3, #0
    beq fp_tail
    strb r3, [r0], #1
    subs r2, r2, #1
    bne fp_folder
fp_tail:
    ldr r1, =update_name
    cmp r4, #0
    ldrne r1, =original_name
fp_name:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    cmp r3, #0
    bne fp_name
    mov r0, sp
    bl STRING_FREE
    add sp, sp, #0x10
    pop {{r4, r5, pc}}
plugin_path:
    ldr r0, =FILE_PATH
    ldr r1, =plugin_prefix
pp_prefix:
    ldrb r3, [r1], #1
    cmp r3, #0
    strbne r3, [r0], #1
    bne pp_prefix
    ldr r1, =FILE_NAME
pp_name:
    ldrb r3, [r1], #1
    cmp r3, #0
    strbne r3, [r0], #1
    bne pp_name
    ldr r1, =plugin_suffix
pp_suffix:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    cmp r3, #0
    bne pp_suffix
    bx lr
plugin_prefix:
    .asciz "SD:KORG/blechtribe/Plugin/"
plugin_suffix:
    .asciz ".blech"
.align 4
update_name:
    .asciz "System/SYSTEM.VSB"
original_name:
    .asciz "System/ORIGINAL.BIN"
.align 4
.pool

; ---- the reply -------------------------------------------------------------------------------------------------------
; r0 = function, r1 = the words, r2 = their length in bytes, r3 = where the message is built; r7 = the port. The words may lie
; in the same buffer, at least one byte behind where the message starts and the further behind the more words there are: the
; packing writes eight bytes for seven and never reaches the words it has not read yet.
send_reply:
    push {{r4, r5, r6, r8, r9, lr}}
    mov r8, r3
    mov r9, r0
    mov r4, r3
    mov r12, #0xf0
    strb r12, [r4], #1
    mov r12, #0x42
    strb r12, [r4], #1
    ldr r12, =CHANNEL
    ldrb r12, [r12]
    and r12, r12, #0x0f
    orr r12, r12, #0x30
    strb r12, [r4], #1
    mov r12, #0
    strb r12, [r4], #1
    mov r12, #1
    strb r12, [r4], #1
    mov r12, #MODEL
    strb r12, [r4], #1
    strb r9, [r4], #1
    mov r0, r4
    bl pack
    mov r12, #0xf7
    strb r12, [r0], #1
    sub r5, r0, r8
    bl TX_BEGIN
    mov r1, r8
    mov r2, r5
    mov r3, r7
    bl TX_SEND
    bl TX_END
    pop {{r4, r5, r6, r8, r9, pc}}
.pool

; r0 = where to put it, r1 = the bytes, r2 = how many; returns r0 behind the packed bytes. Seven bytes become eight: the high bits
; of the seven first, then the seven with bit 7 cleared. Touches r3 to r6 and r12.
pack:
pack_group:
    cmp r2, #0
    bxle lr
    cmp r2, #7
    movge r3, #7
    movlt r3, r2
    mov r4, #0
    mov r5, #0
pack_byte:
    ldrb r6, [r1, r5]
    tst r6, #0x80
    movne r12, #1
    orrne r4, r4, r12, lsl r5
    and r6, r6, #0x7f
    add r12, r0, r5
    strb r6, [r12, #1]
    add r5, r5, #1
    cmp r5, r3
    blt pack_byte
    strb r4, [r0]
    add r0, r0, r3
    add r0, r0, #1
    add r1, r1, r3
    sub r2, r2, r3
    b pack_group

; r0 = the bytes, r1 = how many; returns r0 = CRC-32 (the one of zlib). Touches r1 to r3 and r12.
crc32:
    mvn r2, #0
    ldr r3, =crc_table
crc_loop:
    cmp r1, #0
    beq crc_done
    ldrb r12, [r0], #1
    eor r2, r2, r12
    and r12, r2, #15
    ldr r12, [r3, r12, lsl #2]
    eor r2, r12, r2, lsr #4
    and r12, r2, #15
    ldr r12, [r3, r12, lsl #2]
    eor r2, r12, r2, lsr #4
    sub r1, r1, #1
    b crc_loop
crc_done:
    mvn r0, r2
    bx lr
.pool
crc_table:
.word {CRC_WORDS}

; r0 = to, r1 = from, r2 = how many (not 0); whole words when all three allow it. Touches r0 to r3.
memcpy:
    orr r3, r0, r1
    orr r3, r3, r2
    tst r3, #3
    bne copy_bytes
copy_words:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne copy_words
    bx lr
copy_bytes:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne copy_bytes
    bx lr

; r0 = a start, r1 = a length, r2 = 1 for a write; returns r0 = 0 for yes, 2 for refused, 3 for out of range.
; The range has to lie in the RAM window and be 1 to MAX_BLOCK bytes. A write may not touch a region of the table unless the whole
; range lies in one window of that region's class; a read is refused only in regions that are refused for reads. A write is checked
; a second time for its mirror in the other half of the window, where no window counts.
policy:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    cmp r1, #0
    beq policy_range
    ldr r3, =MAX_BLOCK
    cmp r1, r3
    bhi policy_range
    adds r4, r0, r1
    bcs policy_range
    ldr r3, =WIN_START
    cmp r0, r3
    blo policy_range
    ldr r3, =WIN_END
    cmp r4, r3
    bhi policy_range
    mov r9, r0
    mov r8, r2
    mov r5, r0
    mov r6, r4
    mov r7, #0
policy_spot:
    ldr r10, =TABLE
    ldr r11, [r10]
    add r10, r10, #8
policy_region:
    cmp r11, #0
    beq policy_next
    sub r11, r11, #1
    ldr r12, [r10]
    ldr r2, [r10, #4]
    ldr r3, [r10, #8]
    add r10, r10, #12
    cmp r6, r12
    bls policy_region
    cmp r5, r2
    bhs policy_region
    cmp r8, #0
    bne policy_hit
    tst r3, #0x100
    beq policy_region
policy_hit:
    cmp r7, #0
    bne policy_refused
    ands r2, r3, #0xff
    beq policy_refused
    mov r0, r9
    bl in_window
    cmp r0, #0
    beq policy_refused
    b policy_region
policy_next:
    cmp r7, #0
    bne policy_yes
    cmp r8, #0
    beq policy_yes
    mov r7, #1
    ldr r3, =MIRROR
    ldr r12, =HALF
    cmp r9, r12
    addlo r5, r9, r3
    subhs r5, r9, r3
    add r6, r5, r1
    b policy_spot
policy_yes:
    mov r0, #0
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}
policy_refused:
    mov r0, #2
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}
policy_range:
    mov r0, #3
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}
.pool

; r0 = a start, r1 = a length, r2 = class bits; returns r0 = 1 when the range lies wholly in one window of the table that has one
; of those bits. A window run is count windows of width bytes, stride apart; the offset is cut down by whole strides.
in_window:
    push {{r3, r4, r5, r6, r7, r8, lr}}
    ldr r3, =TABLE
    ldr r4, [r3]
    ldr r5, [r3, #4]
    add r4, r4, r4, lsl #1
    add r3, r3, #8
    add r3, r3, r4, lsl #2
window_loop:
    cmp r5, #0
    beq window_no
    ldr r4, [r3, #16]
    tst r4, r2
    beq window_next
    ldr r4, [r3]
    subs r4, r0, r4
    blo window_next
    ldr r6, [r3, #8]
    ldr r7, [r3, #12]
window_index:
    cmp r7, #0
    beq window_next
    cmp r4, r6
    blo window_here
    sub r4, r4, r6
    sub r7, r7, #1
    b window_index
window_here:
    ldr r8, [r3, #4]
    add r4, r4, r1
    cmp r4, r8
    bls window_yes
window_next:
    add r3, r3, #20
    sub r5, r5, #1
    b window_loop
window_yes:
    mov r0, #1
    pop {{r3, r4, r5, r6, r7, r8, pc}}
window_no:
    mov r0, #0
    pop {{r3, r4, r5, r6, r7, r8, pc}}
.pool
"""


FIRMWARE_PLACES = ["CLASSIFY_HOOK", "CLASSIFY_BACK", "PROCESS_HOOK", "PROCESS_BACK", "PANEL", "DESC", "FLAG", "CHANNEL", "PORT_OF",
                   "TX_BEGIN", "TX_SEND", "TX_END", "FLASH_OBJ", "FLASH_READ", "FS_OPEN", "FS_READ", "FS_WRITE", "FS_CLOSE", "FS_LSEEK",
                   "FOLDER", "STRING_FREE"]
CODE_PLACES = ["CLASSIFY_HOOK", "PROCESS_HOOK", "TX_BEGIN", "TX_SEND", "TX_END", "FLASH_READ"]   # their 16 words must equal the Sampler's


def use_build(build, ref=None, vsb=None):
    """For the synth the places of the firmware are not where the Sampler has them: find each by the Sampler's address
    (tools/patch/fwmap.py, which needs the Sampler's VSB `ref`) and refuse a code place whose words differ. The code
    of the patch and the places in free runs stay as they are (the synth's free run covers the Sampler's)."""
    if build != "synth":
        return {}
    if ref is None:
        raise SystemExit("the synth build needs --ref, the Sampler's SYSTEM.VSB, to find the places")
    import fwmap
    globals()["MODEL"] = 0x23
    globals()["FOLDER_ID"] = 0x123           # the id the synth's update passes to its folder function (0xC0035304 loads it)
    mapped = fwmap.FirmwareMap(fwmap.load(ref), vsb[HEADER:])
    found = {}
    for name in FIRMWARE_PLACES:
        try:
            found[name] = mapped.at(globals()[name])
            if name in CODE_PLACES and not mapped.same_code(globals()[name]):
                raise SystemExit(f"{name}: the code at {globals()[name]:#x} is not the same in the synth")
        except fwmap.Unmapped as error:
            raise SystemExit(f"{name}: {error}")
    globals().update(found)
    return found


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target):
    return 0xEA000000 | (((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb, table, build):
    """The patch for one build as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes, `table` the bytes of src/sysex-table.mjs for that build."""
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
    if len(table) % 4 or TABLE_AT + len(table) > TABLE_END:
        raise SystemExit(f"the table is {len(table)} bytes, room for {TABLE_END - TABLE_AT}")
    if BUF_END - BUF < BUFFER_REQUIRED:
        raise SystemExit("the buffer is too small for the largest block packed in place")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    def hook(addr, word, target):
        if struct.unpack("<I", was(addr, 4))[0] != word:
            raise SystemExit(f"the instruction at {addr:#x} is not where the patch expects it in this VSB")
        return struct.pack("<I", branch(addr, target))

    classify = hook(CLASSIFY_HOOK, CLASSIFY_WORD, symbols["classify_hook"])
    process = hook(PROCESS_HOOK, PROCESS_WORD, symbols["process_hook"])
    return {
        "format": "gelumpe-patch", "version": 1, "id": "blech-sysex",
        "name": "BLECH SysEx: RAM und Flash lesen" if build == "synth" else "BLECH SysEx: RAM lesen und schreiben in großen Blöcken",
        "builds": [build],
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "BLECH SysEx: the two hooks, the CRC-32, the packing, the range check and the commands"},
            {"file": file_offset(TABLE_AT), "bytes": bytes(table).hex(), "expect": free(TABLE_AT, len(table)),
             "note": "the protection table, cut from data/protected.mjs by src/sysex-table.mjs"},
            {"file": file_offset(CLASSIFY_HOOK), "bytes": classify.hex(), "expect": sha(was(CLASSIFY_HOOK, 4)),
             "note": "the first instruction of the function that sorts a SysEx function byte jumps to the hook"},
            {"file": file_offset(PROCESS_HOOK), "bytes": process.hex(), "expect": sha(was(PROCESS_HOOK, 4)),
             "note": "the first instruction of the function that runs a received message jumps to the hook"},
        ],
        "hooks": [
            {"site": f"0x{CLASSIFY_HOOK:08X}", "kind": "instruction", "chain": "sysex-request",
             "position": "before", "swallow": True,
             "note": "the function bytes 0x60 to 0x66 are taken here, every other byte goes on to the original; with EXIT held at power-on all of them do"},
            {"site": f"0x{PROCESS_HOOK:08X}", "kind": "instruction", "chain": "sysex-request",
             "position": "before", "swallow": True,
             "note": "a received message with function 0x60 to 0x66 is run here, every other goes on to the original; with EXIT held at power-on all of them do"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: the declared write, the request as decoded, the words and the packed bytes of a short reply", "tools/patch/blech_sysex.py:STATE"),
            ramdecl.area(BUF, BUF_END - BUF, "the buffer a message is decoded into and a reply is packed in, up to MAX_BLOCK bytes of data", "tools/patch/blech_sysex.py:BUF"),
            ramdecl.area(FILE_AREA, FILE_AREA_END - FILE_AREA, "the FatFs file object, the byte count and the path of the FILE commands", "tools/patch/blech_sysex.py:FILE_AREA"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--table", required=True, type=Path, help="the protection table (src/sysex-table.mjs)")
    p.add_argument("--build", required=True, choices=["hacktribe", "stock", "synth"], help="the build the table is for; the code is the same in the Sampler's two builds")
    p.add_argument("--ref", type=Path, help="for the synth: the Sampler's SYSTEM.VSB, to find the places by their Sampler addresses")
    p.add_argument("--out", type=Path)
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    found = use_build(a.build, a.ref, raw)
    if found and a.listing:
        for name, addr in found.items():
            print(f"  synth {name} {addr:#010x}")
    patch = build_patch(raw, a.table.read_bytes(), a.build)
    if a.listing:
        at, code, symbols = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
