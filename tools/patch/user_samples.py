"""Builds the user samples patch for the blue Electribe 2, Korg's synth firmware 2.02
(docs/messungen/2026-11-12-blau-sample-import.md, docs/messungen/2026-10-15-synth-samples.md).

The blue has no IMPORT SAMPLE. Its PCM waves come from the flash at every start and are written into the DSP's memory, and a
voice only gets a start address, a loop and a pitch word. This patch loads the samples of the card's sample file, the same
`KORG/<folder>/Sample/e2sSample.all` the red Electribe and the app write, right after the factory waves, into the DSP's PCM
window behind them, and lists them as oscillators of a new group `[User]` behind `[Audio In]`.

The idea that the blue's DSP has room for samples of one's own came from the Omnitribe project; nothing of it is used here
(its source was gone, 12.11.2026), the numbers are our own measurements.

What changes in the firmware:

  0xC00473D0  `mov r0, r6` at the end of the PCM load (r6 = the bank loaded) becomes a call of `load`, which reads the
              sample file and returns with r0 = r6.
  oscillators the table of 409 records (0xC00BEB48, 32 bytes each) is copied into free image space at patch time (a copy
              change, from the user's own VSB) and gets USER_MAX records behind it, each a copy of SAW until a sample fills
              it. The 10 literals of the table point to the copy.
  bounds      the 11 places that refuse an index above 408 take 408 + USER_MAX; the three places that step through the list
              (next group, previous group, the knob's step and its wrap) take 408 + the samples loaded, so the list ends
              at the last sample.
  per part    the firmware keeps 3 bytes per oscillator and part (A and B, and a flag) in an array of 16 x 409 x 3 bytes at
              0xC056CF96. It moves to free RAM with room for the new records: 9 literals of its address, 9 of its stride.
  group name  the table of the 14 group names (0xC00CABD8) is copied and gets "[User]" as the 15th, the name lookup
              accepts group 14.

A sample needs: RIFF/WAVE with fmt (PCM, 16 bit, mono or stereo, which is averaged), data, and the sampler's `esli` record
in the `korg` chunk for name, start, loop, end and one-shot (without it: the whole sample, one-shot, named USER). It is
written as 16-bit mono at its own rate (the pitch word carries the rate, root key C4), behind the factory waves, 64 bytes
of zeros behind each, never beyond the window's end (0x1365AE0). One that does not fit or is not readable is left out
and counted; the others go on. At most USER_MAX samples.

With EXIT held at power-on, without a bank or without the file, nothing loads and the list is Korg's, 409 records.

    python3 tools/patch/user_samples.py --vsb SYSTEM.VSB [--out data/patches/user-samples-synth.json]
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

USER_MAX = 64                   # records of the [User] group
OSC_COUNT = 409                 # Korg's records
OSC_LAST = OSC_COUNT - 1        # 0x198, the largest index Korg's code accepts
MAX_INDEX = OSC_LAST + USER_MAX # 0x1D8, the largest index the patched code accepts
OSC_STRIDE = 0x20
USER_GROUP = 14                 # [Kick] is 0, [Audio In] 13
SAW = 325                       # what an unfilled user record plays: the oscillator a new pattern starts with
TEMPLATE = 0                    # a PCM record whose A/B ranges and defaults a sample gets (SubBeef, wave 0x32)
TEMPLATE_AT = TEMPLATE * 0x20

# ---- the places of Korg's synth 2.02 (docs/messungen/2026-10-15-synth-samples.md, 2026-11-12-blau-sample-import.md)
OSC_TABLE_OLD = 0xC00BEB48
TABLE_LITERALS = [0xC003B954, 0xC003B98C, 0xC003BA48, 0xC006B4C8, 0xC0070E18, 0xC0086C0C, 0xC0086CF0, 0xC0086DA4,
                  0xC0087068, 0xC00871D4]
BOUND_SITES = [0xC0086BEC, 0xC0086C68, 0xC0086D24, 0xC0087034, 0xC0087218, 0xC00872AC, 0xC00872E0, 0xC0087318,
               0xC008735C, 0xC00873A4, 0xC00873F0]   # cmp rX, #0x198: the index is refused above it
NEXT_GROUP = 0xC003B93C         # cmp r0, #0x198 in the scan to the next group (the function has pushed lr)
PREV_GROUP = 0xC003BA3C         # mov r1, #0x198: the scan to the previous group wraps to the last record
STEP = 0xC003BB3C               # addmi r4, r4, #0x198 after `adds r4, r7, r4`: the knob's step and its wrap, to 0xC003BB54
STEP_DONE = 0xC003BB78
AB_OLD = 0xC056CF96             # 16 parts x 409 x 3 bytes
AB_LITERALS = [0xC00871D0, 0xC008724C, 0xC00872A0, 0xC00872D8, 0xC0087310, 0xC0087340, 0xC0087388, 0xC00873D4, 0xC0087420]
AB_STRIDE_LITERALS = [0xC00871CC, 0xC0087248, 0xC00872A4, 0xC00872D4, 0xC008730C, 0xC008733C, 0xC0087384, 0xC00873D0,
                      0xC008741C]
GROUP_NAMES_OLD = 0xC00CABD8    # 14 pointers to "[Kick]" .. "[Audio In]"
GROUP_LITERAL = 0xC006B4CC
GROUP_CMP = 0xC006B4A4          # cmp r3, #0xd: a larger group gets the default text
HOOK = 0xC00473D0               # mov r0, r6 at the end of the PCM load
PANEL = 0xC033E8F8              # pointer to the panel object, +0x18 the keys held at power-on
KILL_SWITCH = 0x2000            # EXIT held at power-on
FOLDER = 0xC003256C             # (string object, id): the card folder the update reads from (0xC0035308 calls it)
FOLDER_ID = 0x123
STRING_FREE = 0xC008CF4C        # frees that string object (0xC003531C)
F_OPEN, F_READ, F_CLOSE, F_LSEEK = 0xC008A6B8, 0xC008A8CC, 0xC008AF34, 0xC008AF5C
DSP_PORT = 0xC0011554           # () -> the object of the DSP host port
DSP_WRITE = 0xC00105A4          # (port, DSP byte address, source, count of 16-bit words, a multiple of 16)
MSVS, MSPR, MSRL, SMPR = 0xC034DE68, 0xC0351E68, 0xC0348664, 0xC0353E74
COUNT_INST, COUNT_MSPR, COUNT_MSRL, COUNT_SMPR = 0xC0353E68, 0xC0353E6C, 0xC0359E74, 0xC034DE64
LIMIT_INST, LIMIT_MSRL = 0x200, 0x600   # what the arrays hold (MSVS and MSPR 512, MSRL and SMPR 1536)
DSP_BASE = 0x365AE0             # the first PCM byte in the DSP
PCM_END = 0x1365AE0             # end of the DSP's PCM window: its effect buffers follow
ONE_SHOT = 0x10000
SMPR_FLAGS = 0x34               # what the probe's appended instrument plays with (synth_probe.py demo)
ROOT_KEY = 60
ROOT_WORD = ROOT_KEY * 256

# ---- our places in the free image run of the synth (0xC01217F4 to 0xC01FFFF0, data/patch-ram.mjs)
CODE_AT = 0xC0128000
CODE_END = 0xC0128F00
GROUP_NAMES = 0xC0128F00        # 15 pointers
OSC_TABLE = 0xC0129000          # (409 + USER_MAX) x 32 bytes, to 0xC012CB20
USER_OSC = OSC_TABLE + OSC_COUNT * OSC_STRIDE   # the record of [User] 1
AB_ARRAY = 0xC012D000           # 16 x (409 + USER_MAX) x 3 bytes, to 0xC01328B0
AB_STRIDE = (OSC_COUNT + USER_MAX) * 3
STATE = 0xC0133000              # run time state, 0x100
PATH = 0xC0133100               # the path of the sample file, 0x100
FIL = 0xC0133200                # the FatFs file object, 0x400
HDR = 0xC0134000                # the 4096-byte head of the sample file
BUF = 0xC0135000                # a block of PCM, 16 KiB and the zeros behind the last one
BLOCK = 0x4000
BUF_LEN = BLOCK + 0x100
SLOTS = 1020

S_LOADED, S_REJECTED, S_NEXT, S_LAST, S_BR, S_STATUS, S_PORT = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18
S_START, S_LOOP, S_END, S_ONESHOT, S_BYTES = 0x1C, 0x20, 0x24, 0x28, 0x2C
S_HEAD = 0x30                   # 44 bytes of the WAV's head
S_ESLI = 0x60                   # "korg", size, "esli", size, 80 bytes of the record
ESLI_READ = 96
S_NAME = 0xC0                   # 16 bytes
S_MODE = 0xD0                   # 0: a sample's table records are appended; 1: they are written over those at S_IX
S_IX = 0xD4                     # u16 each: the SMPR, MSRL, MSPR and instrument record of the sample being loaded
S_FLAGS = 0xDC                  # byte 0 bit 0 REVERSE (esli[54]), byte 1 PLAY LEVEL +12 dB (esli[66]), byte 2 TUNE (esli[77], i8)
ST_NOBANK, ST_EXIT, ST_NOFILE, ST_NOTALL, ST_OK = 1, 2, 3, 4, 5

# ---- IMPORT SAMPLE and SAMPLE EDIT at run time (the BLECH menu calls them through the vector at CODE2)
HW_DSP_WRITE = 0xC000FB44       # (DSP byte address, source, count of 16-bit words): DSP_WRITE under the firmware's lock, for tasks
F_WRITE, F_MKDIR = 0xC008AB10, 0xC008B510
FIL_SIZE = 0x0C                 # the file size in a FatFs file object
FA_READ_WRITE, FA_OPEN_ALWAYS = 0x03, 0x10
FR_NO_PATH = 5
FIRST_USER, LAST_USER = 500, 998   # the slots of 501 to 999 (docs/hintergrund/sample-datei.md)
ESLI_LEN = 1172
KORG_LEN = 8 + ESLI_LEN         # the korg chunk's size field: "esli", size, the record
RIFF_FIXED = 4 + 24 + 8 + 8 + KORG_LEN   # the RIFF size of a mono sample without its values
TUNE_SHIFT = 8                  # a TUNE step in the pitch word (1/256 semitone): a semitone, not yet measured on the red
CODE2 = 0xC013A000              # the run time code, to CODE2_END
CODE2_END = 0xC013E000
UT = 0xC013E000                 # per [User] sample 64 bytes, USER_MAX of them
U_SLOT, U_CH, U_IX, U_ENTRY, U_ESLI, U_BYTES, U_BASE = 0x00, 0x02, 0x04, 0x0C, 0x10, 0x14, 0x18
U_START, U_LOOP, U_END, U_RATE, U_FLAGS = 0x1C, 0x20, 0x24, 0x28, 0x2C   # U_FLAGS: S_FLAGS, byte 3 one-shot
RT = 0xC013F000                 # run time state, 0x100
RT_RUN, RT_SRC, RT_K, RT_BR, RT_DATA, RT_DSIZE, RT_CH, RT_BYTES = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C
RT_FRAME, RT_RATE, RT_M, RT_BLOCKB, RT_ENTRY, RT_SLOT, RT_LOADED, RT_REJ = 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C
RT_NEXT, RT_CHUNK, RT_FMT, RT_WAV = 0x40, 0x48, 0x50, 0x60     # 8, 16 and 44 bytes
SRC_FIL = 0xC013F100            # the FatFs file object of the WAV being imported, 0x400
ESLI_BUF = 0xC013F500           # the korg chunk being written or the head of one being changed, 0x4A4
RUN_END = 0xC013FA00
E_OK, E_OFF, E_SRC, E_FMT, E_ROOM, E_FILE, E_CARD, E_FULL, E_K = range(9)
F_START, F_LOOP, F_END, F_TUNE, F_LEVEL, F_REVERSE = range(6)


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.org {CODE_AT:#x}

; ===================================================== the list's end, read where the list is walked
; The last index of the list: 408 and the samples loaded. Before the load it is not written yet (FF in the image), then 408.

next_group_cmp:                 ; stands for `cmp r0, #0x198`; keeps r0 to r3
    ldr ip, =STATE_LAST
    ldr ip, [ip]
    cmp ip, #{MAX_INDEX:#x}
    movhi ip, #{OSC_LAST:#x}
    cmp r0, ip
    bx lr

prev_group_last:                ; stands for `mov r1, #0x198`
    ldr r1, =STATE_LAST
    ldr r1, [r1]
    cmp r1, #{MAX_INDEX:#x}
    movhi r1, #{OSC_LAST:#x}
    bx lr

step_wrap:                      ; r4 = index + step (flags of the adds before): wrapped into 0 to the last index
    ldr ip, =STATE_LAST
    ldr ip, [ip]
    cmp ip, #{MAX_INDEX:#x}
    movhi ip, #{OSC_LAST:#x}
    cmp r4, #0
    addlt r4, r4, ip
    addlt r4, r4, #1
    bxlt lr
    cmp r4, ip
    subgt r4, r4, ip
    subgt r4, r4, #1
    bx lr

; ===================================================== the load, at the end of the PCM load (r6 = the bank loaded)
load:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    ldr r11, =STATE
    mov r0, #0
    str r0, [r11, #{S_LOADED}]
    str r0, [r11, #{S_REJECTED}]
    mov r0, #{OSC_LAST:#x}
    str r0, [r11, #{S_LAST}]
    mov r0, #{ST_NOBANK}
    str r0, [r11, #{S_STATUS}]
    cmp r6, #0
    beq ld_out
    mov r0, #{ST_EXIT}
    str r0, [r11, #{S_STATUS}]
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq ld_go
    ldr r0, [r0, #0x18]
    tst r0, #{KILL_SWITCH:#x}
    bne ld_out
ld_go:
    bl make_path
    ldr r0, =FIL
    mov r1, #0
    mov r2, #0x400
ld_clear:
    subs r2, r2, #4
    str r1, [r0, r2]
    bne ld_clear
    ldr r1, =PATH
    mov r2, #1                  ; FA_READ
    bl {F_OPEN:#x}
    cmp r0, #0
    movne r0, #{ST_NOFILE}
    strne r0, [r11, #{S_STATUS}]
    bne ld_out
    mov r0, #0
    ldr r1, =HDR
    mov r2, #0x1000
    bl read_at
    cmp r0, #0
    bne ld_bad
    ldr r1, =HDR
    ldr r0, [r1]
    ldr r2, =0x20733265         ; "e2s "
    cmp r0, r2
    ldreq r0, [r1, #4]
    ldreq r2, =0x706d6173       ; "samp"
    cmpeq r0, r2
    bne ld_bad
    mov r0, #{ST_OK}
    str r0, [r11, #{S_STATUS}]
    bl free_start
    bl {DSP_PORT:#x}
    str r0, [r11, #{S_PORT}]
    mov r10, #0
ld_slot:
    ldr r1, =HDR + 16
    ldr r4, [r1, r10, lsl #2]
    cmp r4, #0
    blne load_one
    ldr r0, [r11, #{S_LOADED}]
    cmp r0, #{USER_MAX}
    bhs ld_close
    add r10, r10, #1
    ldr r0, ={SLOTS}
    cmp r10, r0
    blo ld_slot
    b ld_close
ld_bad:
    mov r0, #{ST_NOTALL}
    str r0, [r11, #{S_STATUS}]
ld_close:
    ldr r0, =FIL
    bl {F_CLOSE:#x}
    ldr r0, [r11, #{S_LOADED}]
    add r0, r0, #{OSC_LAST:#x}
    str r0, [r11, #{S_LAST}]
ld_out:
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    mov r0, r6
    bx lr

; PATH = the update's folder (the firmware's own function) + "Sample/e2sSample.all"
make_path:
    push {{r4, lr}}
    sub sp, sp, #0x10
    mov r0, sp
    ldr r1, ={FOLDER_ID:#x}
    bl {FOLDER:#x}
    ldr r1, [sp]
    ldr r0, =PATH
    mov r2, #0x3F
mp_folder:
    ldrb r3, [r1], #1
    cmp r3, #0
    beq mp_tail
    strb r3, [r0], #1
    subs r2, r2, #1
    bne mp_folder
mp_tail:
    ldr r1, =sample_name
mp_copy:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    cmp r3, #0
    bne mp_copy
    mov r0, sp
    bl {STRING_FREE:#x}
    add sp, sp, #0x10
    pop {{r4, pc}}

; r0 = file offset, r1 = destination, r2 = bytes: r0 = 0 when they all came
read_at:
    push {{r4, r5, lr}}
    mov r4, r1
    mov r5, r2
    mov r1, r0
    ldr r0, =FIL
    bl {F_LSEEK:#x}
    cmp r0, #0
    bne ra_fail
    ldr r0, =FIL
    mov r1, r4
    mov r2, r5
    add r3, r11, #{S_BR}
    bl {F_READ:#x}
    cmp r0, #0
    bne ra_fail
    ldr r0, [r11, #{S_BR}]
    subs r0, r0, r5
    pop {{r4, r5, pc}}
ra_fail:
    mov r0, #1
    pop {{r4, r5, pc}}

; S_NEXT = behind the last factory wave: the largest start + end + 2 of the SMPR records, on 32 bytes
free_start:
    ldr r0, =COUNT_SMPR
    ldr r0, [r0]
    ldr r1, =SMPR
    ldr r2, ={DSP_BASE:#x}
fs_loop:
    cmp r0, #0
    beq fs_done
    ldr r3, [r1]
    ldr ip, [r1, #8]
    add r3, r3, ip
    add r3, r3, #2
    cmp r3, r2
    movhi r2, r3
    add r1, r1, #16
    sub r0, r0, #1
    b fs_loop
fs_done:
    add r2, r2, #0x1F
    bic r2, r2, #0x1F
    str r2, [r11, #{S_NEXT}]
    bx lr

; ===================================================== one sample, r4 = its offset in the file; keeps r10 and r11
load_one:
    push {{r10, lr}}
    mov r0, r4
    add r1, r11, #{S_HEAD}
    mov r2, #44
    bl read_at
    cmp r0, #0
    bne lo_reject
    add r5, r11, #{S_HEAD}
    ldr r0, [r5]
    ldr r1, =0x46464952         ; "RIFF"
    cmp r0, r1
    ldreq r0, [r5, #8]
    ldreq r1, =0x45564157       ; "WAVE"
    cmpeq r0, r1
    ldreq r0, [r5, #12]
    ldreq r1, =0x20746d66       ; "fmt "
    cmpeq r0, r1
    ldreq r0, [r5, #16]
    cmpeq r0, #16
    ldreq r0, [r5, #36]
    ldreq r1, =0x61746164       ; "data"
    cmpeq r0, r1
    bne lo_reject
    ldr r0, [r5, #20]           ; format 1 (PCM), 1 or 2 channels
    mov r7, r0, lsr #16
    mov r0, r0, lsl #16
    cmp r0, #0x10000
    bne lo_reject
    cmp r7, #1
    cmpne r7, #2
    bne lo_reject
    ldr r0, [r5, #32]           ; block align, bits
    mov r0, r0, lsr #16
    cmp r0, #16
    bne lo_reject
    ldr r8, [r5, #24]           ; rate
    cmp r8, #1000
    blo lo_reject
    ldr r0, =192000
    cmp r8, r0
    bhi lo_reject
    ldr r9, [r5, #40]           ; data bytes
    sub r0, r7, #1
    mov r6, r9, lsr r0          ; bytes as 16-bit mono: data / channels, whole values
    bic r6, r6, #1
    cmp r6, #4
    blo lo_reject
    str r6, [r11, #{S_BYTES}]
    ; the esli record behind the data: name, start, loop, end, one-shot
    sub r0, r6, #2
    str r0, [r11, #{S_END}]
    str r0, [r11, #{S_LOOP}]
    mov r0, #0
    str r0, [r11, #{S_START}]
    str r0, [r11, #{S_FLAGS}]
    mov r0, #1
    str r0, [r11, #{S_ONESHOT}]
    ldr r0, =0x52455355         ; "USER"
    str r0, [r11, #{S_NAME}]
    mov r0, #0
    str r0, [r11, #{S_NAME} + 4]
    str r0, [r11, #{S_NAME} + 8]
    str r0, [r11, #{S_NAME} + 12]
    add r0, r4, #44
    add r0, r0, r9
    and r1, r9, #1
    add r0, r0, r1
    add r1, r11, #{S_ESLI}
    mov r2, #{ESLI_READ}
    bl read_at
    cmp r0, #0
    bne lo_stream
    add r5, r11, #{S_ESLI}
    ldr r0, [r5]
    ldr r1, =0x67726f6b         ; "korg"
    cmp r0, r1
    ldreq r0, [r5, #8]
    ldreq r1, =0x696c7365       ; "esli"
    cmpeq r0, r1
    bne lo_stream
    add r5, r5, #16             ; the record
    ldrb r0, [r5, #54]          ; REVERSE, PLAY LEVEL, TUNE
    and r0, r0, #1
    ldrb r1, [r5, #66]
    cmp r1, #0
    orrne r0, r0, #0x100
    ldrb r1, [r5, #77]
    orr r0, r0, r1, lsl #16
    str r0, [r11, #{S_FLAGS}]
    add r0, r5, #2
    add r1, r11, #{S_NAME}
    mov r2, #15
lo_name:
    ldrb r3, [r0], #1
    strb r3, [r1], #1
    cmp r3, #0
    beq lo_named
    subs r2, r2, #1
    bne lo_name
lo_named:
    mov r3, #0
lo_name_zero:                   ; up to 16 bytes in all: the zero behind the name already counts
    strb r3, [r1], #1
    subs r2, r2, #1
    bgt lo_name_zero
    ; start, loop and end as byte offsets of a value (of both channels in a stereo file); outside the sample the defaults stay
    ldr r0, [r5, #48]
    ldr r1, [r5, #44]
    ldr r2, [r5, #40]
    cmp r7, #2
    moveq r0, r0, lsr #1
    moveq r1, r1, lsr #1
    moveq r2, r2, lsr #1
    bic r0, r0, #1
    bic r1, r1, #1
    bic r2, r2, #1
    sub r3, r6, #2
    cmp r0, r3
    bhi lo_stream
    cmp r1, r0
    bhi lo_stream
    cmp r2, r0
    bhi lo_stream
    str r2, [r11, #{S_START}]
    str r1, [r11, #{S_LOOP}]
    str r0, [r11, #{S_END}]
    ldrb r0, [r5, #52]
    str r0, [r11, #{S_ONESHOT}]
lo_stream:
    ; the room: the values, 64 bytes of zeros, on 32 bytes, before the window's end
    ldr r0, [r11, #{S_NEXT}]
    add r1, r6, #0x5F
    bic r1, r1, #0x1F
    add r1, r0, r1
    ldr r2, ={PCM_END:#x}
    cmp r1, r2
    bhi lo_reject
    ; the tables have room
    ldr r0, =COUNT_INST
    ldr r0, [r0]
    cmp r0, #{LIMIT_INST:#x}
    bhs lo_reject
    ldr r0, =COUNT_MSPR
    ldr r0, [r0]
    cmp r0, #{LIMIT_INST:#x}
    bhs lo_reject
    ldr r0, =COUNT_MSRL
    ldr r0, [r0]
    cmp r0, #{LIMIT_MSRL:#x}
    bhs lo_reject
    ldr r0, =COUNT_SMPR
    ldr r0, [r0]
    cmp r0, #{LIMIT_MSRL:#x}
    bhs lo_reject
    ; the values, a block at a time; r9 = data bytes left (whole frames), r5 = where in the DSP
    mov r0, r7, lsl #1
    sub r0, r0, #1
    bic r9, r9, r0
    ldr r5, [r11, #{S_NEXT}]
    add r0, r4, #44
    ldr r1, =BUF
    mov r2, #0
    bl read_at                  ; only the seek: 0 bytes
    cmp r0, #0
    bne lo_reject
lo_block:
    mov r8, #{BLOCK:#x}
    cmp r9, r8
    movlo r8, r9
    bl rev_seek
    ldr r0, =FIL
    ldr r1, =BUF
    mov r2, r8
    add r3, r11, #{S_BR}
    bl {F_READ:#x}
    cmp r0, #0
    bne lo_reject
    ldr r0, [r11, #{S_BR}]
    cmp r0, r8
    bne lo_reject
    sub r9, r9, r8
    cmp r7, #2
    bne lo_mono
    ; stereo: (left + right) / 2, in place
    ldr r0, =BUF
    mov r1, r0
    mov r2, r8, lsr #2
lo_mix:
    ldrb r3, [r0], #1
    ldrb ip, [r0], #1
    orr r3, r3, ip, lsl #8
    mov r3, r3, lsl #16
    ldrb ip, [r0], #1
    ldrb lr, [r0], #1
    orr ip, ip, lr, lsl #8
    mov ip, ip, lsl #16
    mov r3, r3, asr #16
    add r3, r3, ip, asr #16
    mov r3, r3, asr #1          ; (left + right) / 2, rounded down
    strb r3, [r1], #1
    mov r3, r3, lsr #8
    strb r3, [r1], #1
    subs r2, r2, #1
    bne lo_mix
    mov r8, r8, lsr #1
lo_mono:
    bl pcm_fx
    cmp r9, #0
    bne lo_write
    ; the last block: 64 bytes of zeros behind it, then on 32 bytes
    ldr r0, =BUF
    add r1, r8, #0x5F
    bic r1, r1, #0x1F
    mov r2, #0
lo_zero:
    strb r2, [r0, r8]
    add r8, r8, #1
    cmp r8, r1
    blo lo_zero
lo_write:
    ldr r0, [r11, #{S_PORT}]
    mov r1, r5
    ldr r2, =BUF
    mov r3, r8, lsr #1
    bl dsp_put
    add r5, r5, r8
    cmp r9, #0
    bne lo_block
    bl add_tables
    bl note_user
    str r5, [r11, #{S_NEXT}]
    ldr r0, [r11, #{S_LOADED}]
    add r0, r0, #1
    str r0, [r11, #{S_LOADED}]
    pop {{r10, pc}}
lo_reject:
    ldr r0, [r11, #{S_REJECTED}]
    add r0, r0, #1
    str r0, [r11, #{S_REJECTED}]
    pop {{r10, pc}}

; ===================================================== the tables: SMPR, MSRL, MSPR, MSVS, the counts and the oscillator record
add_tables:
    push {{r4, r5, r6, r7, r8, r9, lr}}
    ; start, loop and end as byte offsets of the sample, checked against its length
    ldr r6, [r11, #{S_BYTES}]
    sub r6, r6, #2              ; the last value
    ldr r2, [r11, #{S_END}]
    cmp r2, r6
    movhi r2, r6
    cmp r2, #0
    moveq r2, r6
    bic r2, r2, #1
    ldr r0, [r11, #{S_START}]
    cmp r0, r2
    movhi r0, #0
    bic r0, r0, #1
    ldr r1, [r11, #{S_LOOP}]
    cmp r1, r0
    movlo r1, r0
    cmp r1, r2
    movhi r1, r2
    bic r1, r1, #1
    str r0, [r11, #{S_START}]
    str r1, [r11, #{S_LOOP}]
    str r2, [r11, #{S_END}]
    ldr r3, [r11, #{S_ONESHOT}]
    cmp r3, #0
    movne r1, r2
    sub r1, r1, r0              ; loop, end: from the start
    sub r2, r2, r0
    ldr r3, [r11, #{S_NEXT}]
    add r0, r3, r0              ; the start in the DSP
    cmp r1, r2
    ldr r3, ={SMPR_FLAGS:#x}
    orreq r3, r3, #{ONE_SHOT:#x}
    ldr r4, =COUNT_SMPR
    mov ip, #{S_IX}
    bl tab_ix
    mov r5, r4
    ldr ip, =SMPR
    add ip, ip, r5, lsl #4
    str r0, [ip]
    str r1, [ip, #4]
    str r2, [ip, #8]
    str r3, [ip, #12]
    ; MSRL: 127, 0, sample, pitch word, FFFF
    ldr r0, [r11, #{S_HEAD} + 24]
    bl pitch_word
    ldr r1, [r11, #{S_FLAGS}]   ; TUNE
    mov r1, r1, lsl #8
    mov r1, r1, asr #24
    add r0, r0, r1, lsl #{TUNE_SHIFT}
    ldr r4, =COUNT_MSRL
    mov ip, #{S_IX} + 2
    bl tab_ix
    mov r6, r4
    ldr ip, =MSRL
    add ip, ip, r6, lsl #3
    mov r1, #0x7F
    strb r1, [ip]
    mov r1, #0
    strb r1, [ip, #1]
    strb r5, [ip, #2]
    mov r1, r5, lsr #8
    strb r1, [ip, #3]
    strb r0, [ip, #4]
    mov r1, r0, lsr #8
    strb r1, [ip, #5]
    mov r1, #0xFF
    strb r1, [ip, #6]
    strb r1, [ip, #7]
    ; MSPR: the first 8 characters of the name, the layer, 0
    ldr r4, =COUNT_MSPR
    mov ip, #{S_IX} + 4
    bl tab_ix
    mov r7, r4
    ldr ip, =MSPR
    add ip, ip, r7, lsl #4
    ldr r0, [r11, #{S_NAME}]
    str r0, [ip]
    ldr r0, [r11, #{S_NAME} + 4]
    str r0, [ip, #4]
    str r6, [ip, #8]
    mov r0, #0
    str r0, [ip, #12]
    ; MSVS: the template instrument's record, one zone over all keys to the new MSPR, the template's level in all four
    ldr r0, =OSC_TABLE + {TEMPLATE_AT:#x} + 0x12
    ldrb r1, [r0]
    ldrb r2, [r0, #1]
    orr r1, r1, r2, lsl #8
    sub r1, r1, #0x32
    ldr r0, =MSVS
    add r1, r0, r1, lsl #5
    ldr r4, =COUNT_INST
    mov ip, #{S_IX} + 6
    bl tab_ix
    mov r8, r4
    add ip, r0, r8, lsl #5
    mov r2, #0
ms_copy:
    ldr r3, [r1, r2]
    str r3, [ip, r2]
    add r2, r2, #4
    cmp r2, #32
    bne ms_copy
    mov r2, #0x7F
    strb r2, [ip, #8]
    strb r2, [ip, #9]
    strb r2, [ip, #10]
    strb r2, [ip, #11]
    ldrb r2, [ip, #0x18]
    ldrb r3, [ip, #0x19]
    mov r1, #0
ms_zone:
    add r0, ip, r1, lsl #1
    strb r7, [r0, #0x10]
    mov r9, r7, lsr #8
    strb r9, [r0, #0x11]
    strb r2, [r0, #0x18]
    strb r3, [r0, #0x19]
    add r1, r1, #1
    cmp r1, #4
    bne ms_zone
    ; the oscillator record 409 + loaded: the template's, the name, group [User], the wave of the instrument
    ldr r0, [r11, #{S_LOADED}]
    add r0, r0, #{OSC_LAST:#x}
    add r0, r0, #1
    ldr ip, =OSC_TABLE
    add r1, ip, #{TEMPLATE_AT:#x}
    add ip, ip, r0, lsl #5
    mov r2, #0
os_copy:
    ldr r3, [r1, r2]
    str r3, [ip, r2]
    add r2, r2, #4
    cmp r2, #32
    bne os_copy
    ldr r0, [r11, #{S_NAME}]
    str r0, [ip]
    ldr r0, [r11, #{S_NAME} + 4]
    str r0, [ip, #4]
    ldr r0, [r11, #{S_NAME} + 8]
    str r0, [ip, #8]
    ldr r0, [r11, #{S_NAME} + 12]
    bic r0, r0, #0xFF000000
    str r0, [ip, #12]
    mov r0, #{USER_GROUP}
    strb r0, [ip, #0x10]
    add r0, r8, #0x32
    strb r0, [ip, #0x12]
    mov r0, r0, lsr #8
    strb r0, [ip, #0x13]
    pop {{r4, r5, r6, r7, r8, r9, pc}}

; r0 = rate -> r0 = 256 * (ROOT_KEY + 12 * log2(48000 / rate)), 1/256 semitone
pitch_word:
    push {{r4, lr}}
    bl log2q
    mov r4, r0
    ldr r0, =48000
    bl log2q
    sub r0, r0, r4
    mov r0, r0, asr #4
    ldr r1, =3072
    mul r2, r0, r1
    mov r0, r2, asr #12
    add r0, r0, #{ROOT_WORD:#x}
    pop {{r4, pc}}

; r0 = x (1 or more) -> r0 = log2(x) in 1/65536; uses r1 to r3 and ip
log2q:
    mov r1, #0
    mov r2, r0
lq_int:
    cmp r2, #1
    movhi r2, r2, lsr #1
    addhi r1, r1, #1
    bhi lq_int
    rsbs r2, r1, #15
    movpl r3, r0, lsl r2
    rsbmi r2, r2, #0
    movmi r3, r0, lsr r2
    mov r0, r1, lsl #16
    mov r2, #0x8000
lq_frac:
    mul ip, r3, r3
    mov r3, ip, lsr #15
    cmp r3, #0x10000
    movhs r3, r3, lsr #1
    orrhs r0, r0, r2
    movs r2, r2, lsr #1
    bne lq_frac
    bx lr

.pool
sample_name:
.asciz "Sample/e2sSample.all"
user_group:
.asciz "[User]"

; ===================================================== run time: IMPORT SAMPLE and SAMPLE EDIT, and what the load shares with them
.org {CODE2:#x}
; The vector the BLECH menu calls (fixed places): us_import, us_set, us_store, then a mark that the code is there.
us_api:
    b us_import
    b us_set
    b us_store
    .word 0x53554C42            ; "BLUS"
    b us_info

; r4 = the address of a table's count, ip = the place in STATE of the record's index -> r4 = the record's index. Appending
; (S_MODE 0) takes the count, raises it and keeps the index there; S_MODE 1 takes the index kept. Keeps r0 to r3.
tab_ix:
    push {{r0, r1}}
    ldr r0, [r11, #{S_MODE}]
    cmp r0, #1
    ldrheq r4, [r11, ip]
    beq tx_out
    ldr r0, [r4]
    add r1, r0, #1
    str r1, [r4]
    strh r0, [r11, ip]
    mov r4, r0
tx_out:
    pop {{r0, r1}}
    bx lr

; the load's block (r8 bytes, r9 left before it, r4 the entry): REVERSE reads the blocks from the end
rev_seek:
    ldrb r0, [r11, #{S_FLAGS}]
    tst r0, #1
    bxeq lr
    add r1, r4, #44
    add r1, r1, r9
    sub r1, r1, r8
    ldr r0, =FIL
    b {F_LSEEK:#x}

; r8 bytes of 16-bit mono in BUF: PLAY LEVEL +12 dB times 4 held in the 16-bit range, REVERSE turns the block round
pcm_fx:
    ldr r0, [r11, #{S_FLAGS}]
    tst r0, #0x100
    beq pf_rev
    ldr r1, =BUF
    add r2, r1, r8
    ldr ip, =0x7FFF
pf_gain:
    cmp r1, r2
    bhs pf_rev
    ldrsh r3, [r1]
    mov r3, r3, lsl #2
    cmp r3, ip
    movgt r3, ip
    cmn r3, #0x8000
    mvnlt r3, ip
    strh r3, [r1], #2
    b pf_gain
pf_rev:
    tst r0, #1
    bxeq lr
    ldr r1, =BUF
    add r2, r1, r8
    sub r2, r2, #2
pf_swap:
    cmp r1, r2
    bxhs lr
    ldrh r3, [r1]
    ldrh ip, [r2]
    strh ip, [r1], #2
    strh r3, [r2], #-2
    b pf_swap

; DSP_WRITE's arguments: at start the firmware's writer, at run time (RT_RUN 1) the one under the firmware's lock
dsp_put:
    ldr ip, =RT
    ldr ip, [ip, #{RT_RUN}]
    cmp ip, #1
    bne {DSP_WRITE:#x}
    mov r0, r1
    mov r1, r2
    mov r2, r3
    b {HW_DSP_WRITE:#x}

; behind add_tables: the record of [User] S_LOADED + 1, slot r10, entry r4, at S_NEXT in the DSP. Keeps r4 to r11.
note_user:
    ldr r0, [r11, #{S_LOADED}]
    cmp r0, #{USER_MAX}
    bxhs lr
    ldr r1, =UT
    add r1, r1, r0, lsl #6
    strh r10, [r1, #{U_SLOT}]
    ldrh r0, [r11, #{S_HEAD} + 22]
    strb r0, [r1, #{U_CH}]
    ldr r0, [r11, #{S_IX}]
    str r0, [r1, #{U_IX}]
    ldr r0, [r11, #{S_IX} + 4]
    str r0, [r1, #{U_IX} + 4]
    str r4, [r1, #{U_ENTRY}]
    ldr r0, [r11, #{S_HEAD} + 40]
    add r2, r4, #44
    add r2, r2, r0
    and r0, r0, #1
    add r2, r2, r0
    add r2, r2, #16
    str r2, [r1, #{U_ESLI}]
    ldr r0, [r11, #{S_BYTES}]
    str r0, [r1, #{U_BYTES}]
    ldr r0, [r11, #{S_NEXT}]
    str r0, [r1, #{U_BASE}]
    ldr r0, [r11, #{S_START}]
    str r0, [r1, #{U_START}]
    ldr r0, [r11, #{S_LOOP}]
    str r0, [r1, #{U_LOOP}]
    ldr r0, [r11, #{S_END}]
    str r0, [r1, #{U_END}]
    ldr r0, [r11, #{S_HEAD} + 24]
    str r0, [r1, #{U_RATE}]
    ldr r0, [r11, #{S_FLAGS}]
    bic r0, r0, #0xFF000000
    ldr r2, [r11, #{S_ONESHOT}]
    cmp r2, #0
    orrne r0, r0, #0x01000000
    str r0, [r1, #{U_FLAGS}]
    bx lr

; ----------------------------------------------------- IMPORT SAMPLE
; r0 = the path of a WAV file, r1 = the [User] number it goes to: 1 to the samples loaded + 1, at most USER_MAX. A number
; that has a sample gets the new one (the old one's bytes stay in the file and the DSP until the next start).
; -> r0 = E_OK, or what stopped it. The file is written first and the head last; the sample plays at once.
us_import:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    ldr r11, =STATE
    ldr r10, =RT
    str r0, [r10, #{RT_SRC}]
    str r1, [r10, #{RT_K}]
    mov r0, #1
    str r0, [r10, #{RT_RUN}]
    ldr r0, =SRC_FIL
    bl fil_clear
    ldr r0, =FIL
    bl fil_clear
    bl ui_ready
    cmp r0, #0
    bne ui_close
    ldr r1, [r10, #{RT_K}]
    ldr r2, [r11, #{S_LOADED}]
    add r2, r2, #1
    cmp r1, #1
    blo ui_bad_k
    cmp r1, #{USER_MAX}
    bhi ui_bad_k
    cmp r1, r2
    bhi ui_bad_k
    ldr r0, =SRC_FIL
    ldr r1, [r10, #{RT_SRC}]
    mov r2, #1                  ; FA_READ
    bl {F_OPEN:#x}
    cmp r0, #0
    movne r0, #{E_SRC}
    bne ui_close
    bl ui_parse
    cmp r0, #0
    bne ui_close
    ldr r0, [r11, #{S_NEXT}]    ; room in the DSP: the values, 64 bytes of zeros, on 32 bytes
    ldr r1, [r10, #{RT_M}]
    add r1, r1, #0x5F
    bic r1, r1, #0x1F
    add r0, r0, r1
    ldr r1, ={PCM_END:#x}
    cmp r0, r1
    movhi r0, #{E_ROOM}
    bhi ui_close
    bl ui_open_all
    cmp r0, #0
    bne ui_close
    bl ui_slot
    cmp r0, #0
    bne ui_close
    bl ui_name
    bl ui_write
    cmp r0, #0
    bne ui_close
    ldr r0, =SRC_FIL
    bl {F_CLOSE:#x}
    bl ui_live
    cmp r0, #0
    bne ui_close
    ldr r0, [r10, #{RT_SLOT}]   ; the head last: the slot's offset
    mov r0, r0, lsl #2
    add r0, r0, #16
    ldr r1, =HDR
    add r1, r1, r0
    ldr r2, [r10, #{RT_ENTRY}]
    str r2, [r1]
    mov r2, #4
    bl write_at
    cmp r0, #0
    movne r0, #{E_CARD}
    b ui_close
ui_bad_k:
    mov r0, #{E_K}
ui_close:
    mov r4, r0
    ldr r0, =SRC_FIL
    bl {F_CLOSE:#x}
    ldr r0, =FIL
    bl {F_CLOSE:#x}
    mov r0, r4
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}

; r0 = a file object: cleared, as the load clears its own before f_open
fil_clear:
    mov r1, #0
    mov r2, #0x400
fc_loop:
    subs r2, r2, #4
    str r1, [r0, r2]
    bne fc_loop
    bx lr

; -> r0 = 0 when the start's load left the tables in a state to add to (a file was read, or there was none), else E_OFF/E_FILE
ui_ready:
    ldr r0, [r11, #{S_STATUS}]
    cmp r0, #{ST_OK}
    moveq r0, #0
    bxeq lr
    cmp r0, #{ST_NOTALL}
    moveq r0, #{E_FILE}
    bxeq lr
    cmp r0, #{ST_NOFILE}
    movne r0, #{E_OFF}
    bxne lr
    push {{lr}}
    bl free_start               ; the load stopped before it found where the factory waves end
    mov r0, #{ST_OK}
    str r0, [r11, #{S_STATUS}]
    mov r0, #0
    pop {{pc}}

; r0 = offset, r1 = destination, r2 = bytes of the WAV being imported; r3 = another file object from src_at_fil -> r0 = 0 when all came
src_at:
    ldr r3, =SRC_FIL
src_at_fil:
    push {{r4, r5, r6, lr}}
    mov r4, r1
    mov r5, r2
    mov r6, r3
    mov r1, r0
    mov r0, r6
    bl {F_LSEEK:#x}
    cmp r0, #0
    bne sa_fail
    mov r0, r6
    mov r1, r4
    mov r2, r5
    add r3, r10, #{RT_BR}
    bl {F_READ:#x}
    cmp r0, #0
    bne sa_fail
    ldr r0, [r10, #{RT_BR}]
    subs r0, r0, r5
    pop {{r4, r5, r6, pc}}
sa_fail:
    mov r0, #1
    pop {{r4, r5, r6, pc}}

; r0 = offset in the sample file (-1: where the last write ended), r1 = source, r2 = bytes -> r0 = 0 when all were written
write_at:
    push {{r4, r5, lr}}
    mov r4, r1
    mov r5, r2
    cmn r0, #1
    beq wa_write
    mov r1, r0
    ldr r0, =FIL
    bl {F_LSEEK:#x}
    cmp r0, #0
    bne wa_fail
wa_write:
    ldr r0, =FIL
    mov r1, r4
    mov r2, r5
    add r3, r10, #{RT_BR}
    bl {F_WRITE:#x}
    cmp r0, #0
    bne wa_fail
    ldr r0, [r10, #{RT_BR}]
    subs r0, r0, r5
    pop {{r4, r5, pc}}
wa_fail:
    mov r0, #1
    pop {{r4, r5, pc}}

; r0 / r1 (r1 > 0) -> r0 = quotient, r1 = remainder; uses r2, r3 and ip
udiv:
    mov r2, r1
    mov r3, #1
ud_shift:
    cmp r2, r0, lsr #1
    movls r2, r2, lsl #1
    movls r3, r3, lsl #1
    bls ud_shift
    mov ip, #0
ud_sub:
    cmp r0, r2
    subhs r0, r0, r2
    addhs ip, ip, r3
    movs r3, r3, lsr #1
    movne r2, r2, lsr #1
    bne ud_sub
    mov r1, r0
    mov r0, ip
    bx lr

; the WAV's chunks: fmt before data; PCM (or extensible), 16 or 24 bit, 1 or 2 channels, 1 to 192 kHz -> r0 = 0, E_SRC or E_FMT
ui_parse:
    push {{r4, r5, r6, lr}}
    mov r0, #0
    add r1, r10, #{RT_FMT}      ; the first 12 bytes go where the fmt chunk will
    mov r2, #12
    bl src_at
    cmp r0, #0
    bne up_src
    ldr r0, [r10, #{RT_FMT}]
    ldr r1, =0x46464952         ; "RIFF"
    cmp r0, r1
    ldreq r0, [r10, #{RT_FMT} + 8]
    ldreq r1, =0x45564157       ; "WAVE"
    cmpeq r0, r1
    bne up_src
    mov r4, #12                 ; where the chunk is
    mov r5, #0                  ; 1 once fmt was read
    ldr r6, =SRC_FIL
    ldr r6, [r6, #{FIL_SIZE}]
up_walk:
    add r0, r4, #8
    cmp r0, r6
    bhi up_src
    mov r0, r4
    add r1, r10, #{RT_CHUNK}
    mov r2, #8
    bl src_at
    cmp r0, #0
    bne up_src
    ldr r0, [r10, #{RT_CHUNK}]
    ldr r1, =0x20746d66         ; "fmt "
    cmp r0, r1
    beq up_fmt
    ldr r1, =0x61746164         ; "data"
    cmp r0, r1
    beq up_data
up_next:
    ldr r0, [r10, #{RT_CHUNK} + 4]
    cmp r0, r6
    bhs up_src
    add r0, r0, #1
    bic r0, r0, #1
    add r4, r4, r0
    add r4, r4, #8
    b up_walk
up_fmt:
    ldr r0, [r10, #{RT_CHUNK} + 4]
    cmp r0, #16
    blo up_src
    add r0, r4, #8
    add r1, r10, #{RT_FMT}
    mov r2, #16
    bl src_at
    cmp r0, #0
    bne up_src
    mov r5, #1
    b up_next
up_data:
    cmp r5, #0
    beq up_src
    add r0, r4, #8
    str r0, [r10, #{RT_DATA}]
    ldr r1, [r10, #{RT_CHUNK} + 4]
    sub r0, r6, r0              ; a data chunk that says more than the file holds: what is there
    cmp r1, r0
    movhi r1, r0
    str r1, [r10, #{RT_DSIZE}]
    ldrh r0, [r10, #{RT_FMT}]
    cmp r0, #1
    ldrne r1, =0xFFFE
    cmpne r0, r1
    bne up_fmt_bad
    ldrh r4, [r10, #{RT_FMT} + 2]
    cmp r4, #1
    cmpne r4, #2
    bne up_fmt_bad
    ldr r0, [r10, #{RT_FMT} + 4]
    cmp r0, #1000
    blo up_fmt_bad
    ldr r1, =192000
    cmp r0, r1
    bhi up_fmt_bad
    str r0, [r10, #{RT_RATE}]
    ldrh r5, [r10, #{RT_FMT} + 14]
    cmp r5, #16
    cmpne r5, #24
    bne up_fmt_bad
    mov r5, r5, lsr #3
    mul r1, r5, r4
    str r4, [r10, #{RT_CH}]
    str r5, [r10, #{RT_BYTES}]
    str r1, [r10, #{RT_FRAME}]
    ldr r0, [r10, #{RT_DSIZE}]
    bl udiv
    mov r0, r0, lsl #1          ; bytes as 16-bit mono
    cmp r0, #4
    blo up_fmt_bad
    str r0, [r10, #{RT_M}]
    mov r0, #{BLOCK:#x}         ; a block of whole frames
    ldr r1, [r10, #{RT_FRAME}]
    bl udiv
    ldr r1, [r10, #{RT_FRAME}]
    mul r2, r0, r1
    str r2, [r10, #{RT_BLOCKB}]
    mov r0, #0
    pop {{r4, r5, r6, pc}}
up_src:
    mov r0, #{E_SRC}
    pop {{r4, r5, r6, pc}}
up_fmt_bad:
    mov r0, #{E_FMT}
    pop {{r4, r5, r6, pc}}

; the sample file, open to read and write (never made anew: FatFs here cannot shorten it); a missing one gets its head, a
; missing folder Sample is made -> r0 = 0, E_CARD or E_FILE; HDR holds the head, RT_ENTRY where a new sample goes
ui_open_all:
    push {{r4, lr}}
    bl make_path
    ldr r0, =FIL
    ldr r1, =PATH
    mov r2, #{FA_READ_WRITE} + {FA_OPEN_ALWAYS}
    bl {F_OPEN:#x}
    cmp r0, #{FR_NO_PATH}
    bne uo_opened
    bl ui_mkdir
    ldr r0, =FIL
    bl fil_clear
    ldr r0, =FIL
    ldr r1, =PATH
    mov r2, #{FA_READ_WRITE} + {FA_OPEN_ALWAYS}
    bl {F_OPEN:#x}
uo_opened:
    cmp r0, #0
    movne r0, #{E_CARD}
    popne {{r4, pc}}
    ldr r4, =FIL
    ldr r4, [r4, #{FIL_SIZE}]
    cmp r4, #0
    bne uo_head
    ldr r0, =HDR                ; a new file: the head without samples
    mov r1, #0
    mov r2, #0x1000
uo_zero:
    subs r2, r2, #4
    str r1, [r0, r2]
    bne uo_zero
    ldr r1, =head_magic
    ldmia r1, {{r1, r2, r3, ip}}
    stmia r0, {{r1, r2, r3, ip}}
    mov r0, #0
    ldr r1, =HDR
    mov r2, #0x1000
    bl write_at
    cmp r0, #0
    movne r0, #{E_CARD}
    popne {{r4, pc}}
    mov r4, #0x1000
    b uo_size
uo_head:
    mov r0, #0
    ldr r1, =HDR
    mov r2, #0x1000
    ldr r3, =FIL
    bl src_at_fil
    cmp r0, #0
    bne uo_bad
    ldr r1, =HDR
    ldr r0, [r1]
    ldr r2, =0x20733265         ; "e2s "
    cmp r0, r2
    ldreq r0, [r1, #4]
    ldreq r2, =0x706d6173       ; "samp"
    cmpeq r0, r2
    bne uo_bad
uo_size:
    add r4, r4, #1
    bic r4, r4, #1
    str r4, [r10, #{RT_ENTRY}]
    mov r0, #0
    pop {{r4, pc}}
uo_bad:
    mov r0, #{E_FILE}
    pop {{r4, pc}}

; PATH without its last part: the folder Sample, made
ui_mkdir:
    push {{r4, lr}}
    ldr r0, =PATH
    mov r4, #0
um_find:
    ldrb r1, [r0], #1
    cmp r1, #0x2F
    subeq r4, r0, #1
    cmp r1, #0
    bne um_find
    cmp r4, #0
    popeq {{r4, pc}}
    strb r1, [r4]
    ldr r0, =PATH
    bl {F_MKDIR:#x}
    mov r1, #0x2F
    strb r1, [r4]
    pop {{r4, pc}}

; RT_SLOT: the slot of [User] k, or for a new number the slot behind the last one used, from 501 on -> r0 = 0 or E_FULL
ui_slot:
    ldr r0, [r10, #{RT_K}]
    ldr r1, [r11, #{S_LOADED}]
    cmp r0, r1
    bhi us_new
    ldr r2, =UT
    sub r0, r0, #1
    add r2, r2, r0, lsl #6
    ldrh r0, [r2, #{U_SLOT}]
    str r0, [r10, #{RT_SLOT}]
    mov r0, #0
    bx lr
us_new:
    ldr r2, =HDR + 16
    ldr r0, ={SLOTS} - 1
us_scan:
    ldr r3, [r2, r0, lsl #2]
    cmp r3, #0
    bne us_found
    subs r0, r0, #1
    bpl us_scan
us_found:
    add r0, r0, #1
    cmp r0, #{FIRST_USER}
    movlo r0, #{FIRST_USER}
    ldr r1, ={LAST_USER}
    cmp r0, r1
    movhi r0, #{E_FULL}
    bxhi lr
    str r0, [r10, #{RT_SLOT}]
    mov r0, #0
    bx lr

; S_NAME: the file's name without folder and extension, at most 15 characters
ui_name:
    ldr r0, [r10, #{RT_SRC}]
    mov r1, r0
un_find:
    ldrb r2, [r0], #1
    cmp r2, #0x2F
    moveq r1, r0
    cmp r2, #0
    bne un_find
    add r3, r11, #{S_NAME}
    mov r2, #0
    str r2, [r3]
    str r2, [r3, #4]
    str r2, [r3, #8]
    str r2, [r3, #12]
    mov r2, #15
un_copy:
    ldrb r0, [r1], #1
    cmp r0, #0
    cmpne r0, #0x2E
    bxeq lr
    strb r0, [r3], #1
    subs r2, r2, #1
    bne un_copy
    bx lr

; the entry at RT_ENTRY: RIFF head, the values as 16-bit mono, the korg chunk -> r0 = 0, E_CARD or E_SRC
ui_write:
    push {{r4, r5, r8, r9, lr}}
    add r4, r10, #{RT_WAV}
    ldr r5, [r10, #{RT_M}]
    ldr r0, =0x46464952         ; "RIFF"
    str r0, [r4]
    ldr r0, ={RIFF_FIXED}
    add r0, r0, r5
    str r0, [r4, #4]
    ldr r0, =0x45564157         ; "WAVE"
    str r0, [r4, #8]
    ldr r0, =0x20746d66         ; "fmt "
    str r0, [r4, #12]
    mov r0, #16
    str r0, [r4, #16]
    ldr r0, =0x00010001         ; PCM, mono
    str r0, [r4, #20]
    ldr r0, [r10, #{RT_RATE}]
    str r0, [r4, #24]
    mov r0, r0, lsl #1
    str r0, [r4, #28]
    ldr r0, =0x00100002         ; 2 bytes a frame, 16 bits
    str r0, [r4, #32]
    ldr r0, =0x61746164         ; "data"
    str r0, [r4, #36]
    str r5, [r4, #40]
    ldr r0, [r10, #{RT_ENTRY}]
    mov r1, r4
    mov r2, #44
    bl write_at
    cmp r0, #0
    bne uw_card
    ldr r0, [r10, #{RT_DATA}]   ; the source at its values (a read of 0 bytes)
    ldr r1, =BUF
    mov r2, #0
    bl src_at
    cmp r0, #0
    bne uw_src
    mov r0, r5, lsr #1          ; whole frames
    ldr r1, [r10, #{RT_FRAME}]
    mul r9, r0, r1
uw_block:
    cmp r9, #0
    beq uw_esli
    ldr r8, [r10, #{RT_BLOCKB}]
    cmp r9, r8
    movlo r8, r9
    ldr r0, =SRC_FIL
    ldr r1, =BUF
    mov r2, r8
    add r3, r10, #{RT_BR}
    bl {F_READ:#x}
    cmp r0, #0
    bne uw_src
    ldr r0, [r10, #{RT_BR}]
    cmp r0, r8
    bne uw_src
    sub r9, r9, r8
    bl to_mono16
    mov r2, r0
    mvn r0, #0
    ldr r1, =BUF
    bl write_at
    cmp r0, #0
    bne uw_card
    b uw_block
uw_esli:
    bl ui_esli
    mvn r0, #0
    ldr r1, =ESLI_BUF
    ldr r2, ={KORG_LEN} + 8
    bl write_at
    cmp r0, #0
    bne uw_card
    pop {{r4, r5, r8, r9, pc}}
uw_card:
    mov r0, #{E_CARD}
    pop {{r4, r5, r8, r9, pc}}
uw_src:
    mov r0, #{E_SRC}
    pop {{r4, r5, r8, r9, pc}}

; BUF, r8 bytes of whole frames -> 16-bit mono in place (24 bit: the upper 16; stereo: (left + right) / 2 rounded down, as
; the load) -> r0 = bytes
to_mono16:
    push {{r4, r5, lr}}
    ldr r0, =BUF
    mov r1, r0
    add r2, r0, r8
    ldr r4, [r10, #{RT_CH}]
    ldr r5, [r10, #{RT_BYTES}]
tm_frame:
    cmp r0, r2
    bhs tm_done
    cmp r5, #3
    addeq r0, r0, #1
    ldrb r3, [r0], #1
    ldrb ip, [r0], #1
    orr r3, r3, ip, lsl #8
    mov r3, r3, lsl #16
    mov r3, r3, asr #16
    cmp r4, #2
    bne tm_put
    cmp r5, #3
    addeq r0, r0, #1
    ldrb ip, [r0], #1
    ldrb lr, [r0], #1
    orr ip, ip, lr, lsl #8
    mov ip, ip, lsl #16
    add r3, r3, ip, asr #16
    mov r3, r3, asr #1
tm_put:
    strb r3, [r1], #1
    mov r3, r3, lsr #8
    strb r3, [r1], #1
    b tm_frame
tm_done:
    ldr r0, =BUF
    sub r0, r1, r0
    pop {{r4, r5, pc}}

; ESLI_BUF: the korg chunk of a new sample, the fields of tools/emu/sampleset.py (measured against the red's export)
ui_esli:
    push {{r4, r5, lr}}
    ldr r4, =ESLI_BUF
    mov r0, #0
    ldr r1, ={KORG_LEN} + 8
ue_zero:
    subs r1, r1, #4
    str r0, [r4, r1]
    bne ue_zero
    ldr r0, =0x67726f6b         ; "korg"
    str r0, [r4]
    ldr r0, ={KORG_LEN}
    str r0, [r4, #4]
    ldr r0, =0x696c7365         ; "esli"
    str r0, [r4, #8]
    ldr r0, ={ESLI_LEN}
    str r0, [r4, #12]
    add r4, r4, #16
    ldr r5, [r10, #{RT_SLOT}]
    strh r5, [r4]
    strh r5, [r4, #78]
    add r0, r11, #{S_NAME}
    add r1, r4, #2
    mov r2, #16
ue_name:
    ldrb r3, [r0], #1
    strb r3, [r1], #1
    subs r2, r2, #1
    bne ue_name
    mov r0, #2                  ; category
    strh r0, [r4, #18]
    mov r0, r5
    mov r1, #100
    bl udiv
    ldr r0, =0x226
    add r0, r0, r1
    strh r0, [r4, #20]
    mov r0, #0x7F
    strb r0, [r4, #25]
    mov r0, #1
    strb r0, [r4, #27]
    strb r0, [r4, #52]          ; one-shot
    strb r0, [r4, #64]
    strb r0, [r4, #67]
    ldr r0, =0x42E6
    strh r0, [r4, #34]
    ldr r0, =0xFFFF
    strh r0, [r4, #36]
    ldr r1, [r10, #{RT_M}]
    sub r0, r1, #2
    str r0, [r4, #44]           ; loop
    str r0, [r4, #48]           ; end
    str r1, [r4, #60]
    ldr r0, =0x04B0
    strh r0, [r4, #68]
    ldr r0, [r10, #{RT_RATE}]
    str r0, [r4, #72]
    pop {{r4, r5, pc}}

; the entry just written, into the DSP and the tables as the load does it (reading it back from the card): a new number is
; appended, an old one gets its records written over -> r0 = 0 or E_FULL (no room in the tables)
ui_live:
    push {{r4, r5, r6, r7, r8, r9, r10, lr}}
    ldr r0, [r10, #{RT_K}]
    sub r0, r0, #1
    ldr r1, [r11, #{S_LOADED}]
    str r1, [r10, #{RT_LOADED}]
    cmp r0, r1
    movlo r2, #1
    movhs r2, #0
    str r2, [r11, #{S_MODE}]
    ldrlo r3, =UT
    addlo r3, r3, r0, lsl #6
    ldrlo r2, [r3, #{U_IX}]
    strlo r2, [r11, #{S_IX}]
    ldrlo r2, [r3, #{U_IX} + 4]
    strlo r2, [r11, #{S_IX} + 4]
    str r0, [r11, #{S_LOADED}]
    ldr r4, [r10, #{RT_ENTRY}]
    ldr r10, [r10, #{RT_SLOT}]
    bl reload
    pop {{r4, r5, r6, r7, r8, r9, r10, pc}}

; load_one at run time: r4 = the entry, r10 = its slot, S_LOADED = k - 1, S_MODE and S_IX set; S_LOADED, S_REJECTED
; and S_MODE as they were before, S_LOADED one up for a new number, S_LAST behind it -> r0 = 0 or E_FULL. Clobbers r4 to r10.
reload:
    push {{lr}}
    ldr r0, =RT
    ldr r1, [r11, #{S_REJECTED}]
    str r1, [r0, #{RT_REJ}]
    bl load_one
    ldr r10, =RT
    mov r0, #0
    str r0, [r11, #{S_MODE}]
    ldr r1, [r11, #{S_REJECTED}]
    ldr r2, [r10, #{RT_REJ}]
    str r2, [r11, #{S_REJECTED}]
    cmp r1, r2
    movne r0, #{E_FULL}
    ldr r1, [r11, #{S_LOADED}]
    ldr r2, [r10, #{RT_LOADED}]
    cmp r1, r2
    movlo r1, r2
    str r1, [r11, #{S_LOADED}]
    add r1, r1, #{OSC_LAST:#x}
    str r1, [r11, #{S_LAST}]
    pop {{pc}}

; ----------------------------------------------------- SAMPLE EDIT
; r0 = [User] number, r1 = F_START, F_LOOP, F_END (byte offsets of a value), F_TUNE (-63 to 63), F_LEVEL (0, 1: +12 dB),
; F_REVERSE (0, 1), r2 = the value -> r0 = E_OK or what stopped it. Points and TUNE take effect at the next note and are kept
; in RAM until us_store; PLAY LEVEL and REVERSE store the sample's record and load its values again, in their place.
us_set:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    ldr r11, =STATE
    ldr r10, =RT
    mov r3, #1
    str r3, [r10, #{RT_RUN}]
    ldr r3, [r11, #{S_LOADED}]
    sub r0, r0, #1
    cmp r0, r3
    movhs r0, #{E_K}
    bhs ss_out
    cmp r0, #{USER_MAX}
    movhs r0, #{E_K}
    bhs ss_out
    str r0, [r10, #{RT_K}]
    ldr r4, =UT
    add r4, r4, r0, lsl #6
    cmp r1, #{F_TUNE}
    blo ss_point
    beq ss_tune
    cmp r1, #{F_LEVEL}
    moveq r1, #1
    movne r1, #0
    cmp r2, #0
    movne r2, #1
    add r3, r4, #{U_FLAGS}
    strb r2, [r3, r1]
    bl store_one
    cmp r0, #0
    bne ss_out
    bl make_path
    ldr r0, =FIL
    bl fil_clear
    ldr r0, =FIL
    ldr r1, =PATH
    mov r2, #1                  ; FA_READ
    bl {F_OPEN:#x}
    cmp r0, #0
    movne r0, #{E_FILE}
    bne ss_out
    ldr r0, [r11, #{S_LOADED}]
    str r0, [r10, #{RT_LOADED}]
    ldr r0, [r11, #{S_NEXT}]
    str r0, [r10, #{RT_NEXT}]
    ldr r0, [r4, #{U_BASE}]
    str r0, [r11, #{S_NEXT}]
    ldr r0, [r4, #{U_IX}]
    str r0, [r11, #{S_IX}]
    ldr r0, [r4, #{U_IX} + 4]
    str r0, [r11, #{S_IX} + 4]
    mov r0, #1
    str r0, [r11, #{S_MODE}]
    ldr r0, [r10, #{RT_K}]
    str r0, [r11, #{S_LOADED}]
    ldrh r10, [r4, #{U_SLOT}]
    ldr r4, [r4, #{U_ENTRY}]
    bl reload
    mov r4, r0
    ldr r0, [r10, #{RT_NEXT}]
    str r0, [r11, #{S_NEXT}]
    ldr r0, =FIL
    bl {F_CLOSE:#x}
    mov r0, r4
    b ss_out
ss_point:
    add r3, r4, #{U_START}
    str r2, [r3, r1, lsl #2]
    bl smpr_put
    mov r0, #0
    b ss_out
ss_tune:
    strb r2, [r4, #{U_FLAGS} + 2]
    bl msrl_put
    mov r0, #0
ss_out:
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}

; r4 = a UT record: its points kept within the sample and written to its SMPR record (as add_tables does)
smpr_put:
    push {{r5, lr}}
    ldr r2, [r4, #{U_END}]
    ldr r3, [r4, #{U_BYTES}]
    sub r3, r3, #2
    cmp r2, r3
    movhi r2, r3
    bic r2, r2, #1
    ldr r0, [r4, #{U_START}]
    cmp r0, r2
    movhi r0, r2
    bic r0, r0, #1
    ldr r1, [r4, #{U_LOOP}]
    cmp r1, r0
    movlo r1, r0
    cmp r1, r2
    movhi r1, r2
    bic r1, r1, #1
    str r0, [r4, #{U_START}]
    str r1, [r4, #{U_LOOP}]
    str r2, [r4, #{U_END}]
    ldrb r3, [r4, #{U_FLAGS} + 3]
    cmp r3, #0
    movne r1, r2
    sub r1, r1, r0
    sub r2, r2, r0
    ldr r3, [r4, #{U_BASE}]
    add r0, r3, r0
    ldr r3, ={SMPR_FLAGS:#x}
    cmp r1, r2
    orreq r3, r3, #{ONE_SHOT:#x}
    ldrh r5, [r4, #{U_IX}]
    ldr ip, =SMPR
    add ip, ip, r5, lsl #4
    str r0, [ip]
    str r1, [ip, #4]
    str r2, [ip, #8]
    str r3, [ip, #12]
    pop {{r5, pc}}

; r4 = a UT record: the pitch word of its rate and TUNE into its MSRL record
msrl_put:
    push {{lr}}
    ldr r0, [r4, #{U_RATE}]
    bl pitch_word
    ldrsb r1, [r4, #{U_FLAGS} + 2]
    add r0, r0, r1, lsl #{TUNE_SHIFT}
    ldrh r1, [r4, #{U_IX} + 2]
    ldr r2, =MSRL
    add r2, r2, r1, lsl #3
    strb r0, [r2, #4]
    mov r0, r0, lsr #8
    strb r0, [r2, #5]
    pop {{pc}}

; r0 = [User] number: its points, PLAY LEVEL, REVERSE and TUNE into its esli record in the file -> r0 = E_OK or what stopped it
us_store:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    ldr r11, =STATE
    ldr r10, =RT
    ldr r3, [r11, #{S_LOADED}]
    sub r0, r0, #1
    cmp r0, r3
    movhs r0, #{E_K}
    bhs st_out
    ldr r4, =UT
    add r4, r4, r0, lsl #6
    bl store_one
st_out:
    pop {{r4, r5, r6, r7, r8, r9, r10, r11, pc}}

; r0 = [User] number -> r0 = its name in the oscillator list (16 bytes) or 0 when the list has no such number, r1 = how many the
; list has, r2 = its UT record or 0. Keeps r4 to r11.
us_info:
    ldr r3, =STATE
    ldr r1, [r3, #{S_LOADED}]
    sub r0, r0, #1
    cmp r0, r1
    movhs r0, #0
    movhs r2, #0
    bxhs lr
    ldr r2, =UT
    add r2, r2, r0, lsl #6
    ldr r3, ={USER_OSC:#x}
    add r0, r3, r0, lsl #5      ; OSC_STRIDE
    bx lr

; r4 = a UT record -> r0 = E_OK, E_FILE (no file, or no esli record where the load found one) or E_CARD
store_one:
    push {{r5, lr}}
    bl make_path
    ldr r0, =FIL
    bl fil_clear
    ldr r0, =FIL
    ldr r1, =PATH
    mov r2, #{FA_READ_WRITE}
    bl {F_OPEN:#x}
    cmp r0, #0
    movne r0, #{E_FILE}
    popne {{r5, pc}}
    ldr r0, [r4, #{U_ESLI}]
    sub r0, r0, #16
    ldr r1, =ESLI_BUF
    mov r2, #{ESLI_READ}
    ldr r3, =FIL
    bl src_at_fil
    ldr r5, =ESLI_BUF
    cmp r0, #0
    bne so_bad
    ldr r0, [r5]
    ldr r1, =0x67726f6b         ; "korg"
    cmp r0, r1
    ldreq r0, [r5, #8]
    ldreq r1, =0x696c7365       ; "esli"
    cmpeq r0, r1
    bne so_bad
    add r5, r5, #16
    ldrb r3, [r4, #{U_CH}]      ; a stereo file counts both channels
    sub r3, r3, #1
    ldr r0, [r4, #{U_START}]
    mov r0, r0, lsl r3
    str r0, [r5, #40]
    ldr r0, [r4, #{U_LOOP}]
    mov r0, r0, lsl r3
    str r0, [r5, #44]
    ldr r0, [r4, #{U_END}]
    mov r0, r0, lsl r3
    str r0, [r5, #48]
    ldrb r0, [r5, #54]
    bic r0, r0, #1
    ldrb r1, [r4, #{U_FLAGS}]
    orr r0, r0, r1
    strb r0, [r5, #54]
    ldrb r0, [r4, #{U_FLAGS} + 1]
    strb r0, [r5, #66]
    ldrb r0, [r4, #{U_FLAGS} + 2]
    strb r0, [r5, #77]
    ldr r0, [r4, #{U_ESLI}]
    sub r0, r0, #16
    ldr r1, =ESLI_BUF
    mov r2, #{ESLI_READ}
    bl write_at
    cmp r0, #0
    movne r0, #{E_CARD}
    b so_close
so_bad:
    mov r0, #{E_FILE}
so_close:
    mov r5, r0
    ldr r0, =FIL
    bl {F_CLOSE:#x}
    mov r0, r5
    pop {{r5, pc}}

.pool
.align 2
head_magic:
.ascii "e2s sample all"
.byte 0x1A, 0
"""

EQUS = ["STATE", "PATH", "FIL", "HDR", "BUF", "PANEL", "OSC_TABLE", "MSVS", "MSPR", "MSRL", "SMPR",
        "COUNT_INST", "COUNT_MSPR", "COUNT_MSRL", "COUNT_SMPR", "UT", "RT", "SRC_FIL", "ESLI_BUF"]


def source():
    names = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, int)}
    head = "".join(f".equ {name}, {globals()[name]:#x}\n" for name in EQUS) + f".equ STATE_LAST, {STATE + S_LAST:#x}\n"
    return head + SOURCE.format(**names)


def build_code():
    """The load at CODE_AT; the run time code (IMPORT SAMPLE, SAMPLE EDIT) at CODE2 is `build_code2`."""
    code = arm.assemble(source())
    (at, data), _ = code.sections
    return at, data, code.symbols


def build_code2():
    code = arm.assemble(source())
    _, (at, data) = code.sections
    return at, data


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | (((target - (at + 8)) >> 2) & 0xFFFFFF))


def hex_addr(addr):
    return f"{addr:#010X}".replace("0X", "0x")


def build_patch(vsb):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
    at2, code2 = build_code2()
    if at2 != CODE2 or at2 + len(code2) > CODE2_END:
        raise SystemExit(f"run time code is {len(code2):#x} bytes, room for {CODE2_END - CODE2:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def word(addr):
        return struct.unpack("<I", was(addr, 4))[0]

    def need(addr, value, what):
        if word(addr) != value:
            raise SystemExit(f"{addr:#x}: {what} is not where the patch expects it in this VSB (Korg's synth 2.02 only)")

    for a in TABLE_LITERALS:
        need(a, OSC_TABLE_OLD, "a literal of the oscillator table")
    for a in BOUND_SITES:
        if word(a) & 0x0FF0FFFF != 0x03500F66:
            raise SystemExit(f"{a:#x}: no `cmp rX, #0x198` in this VSB")
    need(NEXT_GROUP, 0xE3500F66, "cmp r0, #0x198")
    need(PREV_GROUP, 0xE3A01F66, "mov r1, #0x198")
    need(STEP, 0x42844F66, "addmi r4, r4, #0x198")
    need(STEP_DONE, 0xE59F3058, "the step's end")
    for a in AB_LITERALS:
        need(a, AB_OLD, "a literal of the per-part array")
    for a in AB_STRIDE_LITERALS:
        need(a, OSC_COUNT * 3, "the per-part stride")
    need(GROUP_LITERAL, GROUP_NAMES_OLD, "the literal of the group names")
    need(GROUP_CMP, 0xE353000D, "cmp r3, #0xd")
    need(HOOK, 0xE1A00006, "mov r0, r6")
    for addr, n in ((CODE_AT, CODE_END - CODE_AT), (GROUP_NAMES, 0x100), (OSC_TABLE, (OSC_COUNT + USER_MAX) * OSC_STRIDE),
                    (AB_ARRAY, 16 * AB_STRIDE), (STATE, BUF + BUF_LEN - STATE), (CODE2, RUN_END - CODE2)):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x} is not free in this VSB")

    def raw(addr, data, note):
        return {"file": file_offset(addr), "bytes": data.hex(), "expect": sha(was(addr, len(data))), "note": note}

    def copy(addr, source_addr, n, note):
        return {"file": file_offset(addr), "copy": {"file": file_offset(source_addr), "length": n, "expect": sha(was(source_addr, n))},
                "expect": sha(was(addr, n)), "note": note}

    changes = [raw(CODE_AT, code, "the load of the sample file, the list's end for the three places that walk the list, the path and the group name"),
               raw(CODE2, code2, "IMPORT SAMPLE and SAMPLE EDIT at run time, called by the BLECH menu; REVERSE, PLAY LEVEL and the record of each [User] sample for the load")]
    changes.append(copy(OSC_TABLE, OSC_TABLE_OLD, OSC_COUNT * OSC_STRIDE, "the oscillator table, copied from the VSB to where it has room for the [User] records"))
    for i in range(USER_MAX):
        changes.append(copy(OSC_TABLE + (OSC_COUNT + i) * OSC_STRIDE, OSC_TABLE_OLD + SAW * OSC_STRIDE, OSC_STRIDE,
                            f"[User] record {i + 1}: SAW until a sample fills it"))
    changes.append(copy(GROUP_NAMES, GROUP_NAMES_OLD, 14 * 4, "the 14 group names, copied from the VSB"))
    changes.append(raw(GROUP_NAMES + 14 * 4, struct.pack("<I", symbols["user_group"]), "the 15th group name, [User]"))
    for a in TABLE_LITERALS:
        changes.append(raw(a, struct.pack("<I", OSC_TABLE), "a literal of the oscillator table points to the copy"))
    changes.append(raw(GROUP_LITERAL, struct.pack("<I", GROUP_NAMES), "the group names' literal points to the copy"))
    changes.append(raw(GROUP_CMP, struct.pack("<I", 0xE353000E), "the name lookup accepts group 14"))
    for a in BOUND_SITES:
        changes.append(raw(a, struct.pack("<I", (word(a) & ~0xFFF) | 0xF76), "the index is refused above 0x1D8 instead of 0x198"))
    for a in AB_LITERALS:
        changes.append(raw(a, struct.pack("<I", AB_ARRAY), "the per-part A/B array moves to room for the [User] records"))
    for a in AB_STRIDE_LITERALS:
        changes.append(raw(a, struct.pack("<I", AB_STRIDE), "its stride per part, 3 bytes per record"))
    changes.append(raw(NEXT_GROUP, branch(NEXT_GROUP, symbols["next_group_cmp"], True), "the scan to the next group ends at the list's end"))
    changes.append(raw(PREV_GROUP, branch(PREV_GROUP, symbols["prev_group_last"], True), "the scan to the previous group wraps to the list's end"))
    changes.append(raw(STEP, branch(STEP, symbols["step_wrap"], True) + branch(STEP + 4, STEP_DONE),
                       "the knob's step wraps at the list's end"))
    changes.append(raw(HOOK, branch(HOOK, symbols["load"], True), "the end of the PCM load calls the load of the sample file"))

    return {
        "format": "gelumpe-patch", "version": 1, "id": "user-samples", "builds": ["synth"],
        "name": "Eigene Samples: e2sSample.all von der Karte als Oszillatoren der Gruppe [User]",
        "changes": changes,
        "hooks": [
            {"site": hex_addr(HOOK), "kind": "instruction", "chain": "pcm-loaded", "position": "replace", "swallow": False,
             "note": "the load of the sample file runs at the end of the PCM load and returns the firmware's result"},
            {"site": hex_addr(NEXT_GROUP), "kind": "instruction", "chain": "osc-next-group", "position": "replace", "swallow": True,
             "note": "the list ends at the last sample"},
            {"site": hex_addr(PREV_GROUP), "kind": "instruction", "chain": "osc-prev-group", "position": "replace", "swallow": True,
             "note": "the list ends at the last sample"},
            {"site": hex_addr(STEP), "kind": "instruction", "chain": "osc-step", "position": "replace", "swallow": True,
             "note": "the knob wraps at the last sample"},
        ],
        "startPhase": [
            {"file": file_offset(HOOK), "length": 4, "why": "the end of the PCM load at start now calls the loader"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "the loader runs at start: it reads e2sSample.all, writes the DSP and the wave tables, reads the held keys"},
            {"file": file_offset(CODE2), "length": len(code2), "why": "the loader calls the run time code's helpers at start: table index, REVERSE, PLAY LEVEL, the DSP writer, the record per sample"},
            {"file": file_offset(OSC_TABLE), "length": (OSC_COUNT + USER_MAX) * OSC_STRIDE,
             "why": "the moved oscillator table: the loader fills the [User] records, the first pattern's oscillators are read from it"},
            *({"file": file_offset(a), "length": 4, "why": "the oscillator table moved: the first pattern's oscillators are read through this literal"}
              for a in TABLE_LITERALS),
            *({"file": file_offset(a), "length": 4, "why": "the oscillator check takes the [User] records; it runs when the first pattern loads"}
              for a in BOUND_SITES),
            *({"file": file_offset(a), "length": 4, "why": "the per-part array moved; the first pattern's oscillators are set through this literal"}
              for a in AB_LITERALS + AB_STRIDE_LITERALS),
        ],
        "ram": [
            {"at": hex_addr(AB_ARRAY), "length": 16 * AB_STRIDE, "what": "the per-part array of A, B and a flag per oscillator, moved from 0xC056CF96 with room for the [User] records",
             "source": "tools/patch/user_samples.py:AB_ARRAY"},
            {"at": hex_addr(STATE), "length": 0x100, "what": "run time state: samples loaded and left out, the next DSP address, the list's end, the result, the WAV head and esli record of the sample being loaded",
             "source": "tools/patch/user_samples.py:STATE"},
            {"at": hex_addr(PATH), "length": 0x100, "what": "the path of the sample file", "source": "tools/patch/user_samples.py:PATH"},
            {"at": hex_addr(FIL), "length": 0x400, "what": "the FatFs file object", "source": "tools/patch/user_samples.py:FIL"},
            {"at": hex_addr(HDR), "length": 0x1000, "what": "the head of the sample file, an offset per slot", "source": "tools/patch/user_samples.py:HDR"},
            {"at": hex_addr(BUF), "length": BUF_LEN, "what": "a block of PCM on its way to the DSP and the zeros behind the last one", "source": "tools/patch/user_samples.py:BUF"},
            {"at": hex_addr(UT), "length": USER_MAX * 64, "what": "per [User] sample: slot, table records, file places, DSP start, points, rate, REVERSE, PLAY LEVEL, TUNE", "source": "tools/patch/user_samples.py:UT"},
            {"at": hex_addr(RT), "length": 0x100, "what": "run time state of IMPORT SAMPLE and SAMPLE EDIT", "source": "tools/patch/user_samples.py:RT"},
            {"at": hex_addr(SRC_FIL), "length": 0x400, "what": "the FatFs file object of the WAV being imported", "source": "tools/patch/user_samples.py:SRC_FIL"},
            {"at": hex_addr(ESLI_BUF), "length": RUN_END - ESLI_BUF, "what": "the korg chunk being written, or the head of an esli record being changed", "source": "tools/patch/user_samples.py:ESLI_BUF"},
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
