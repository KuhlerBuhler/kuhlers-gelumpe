"""Builds BLECH's sample swap (docs/ideen/25-mehr-sample-speicher.md) for the red Sampler 2.02, Korg's build and Hacktribe.

An e2sSample.all larger than the DSP's user bank (25 MiB) no longer stops the load at "Memory Full". At start the loader
reads the file's header and only the samples the current pattern uses. While the device runs, the patch keeps the DSP
holding what the playing pattern needs plus the pattern that comes next (the chosen one, else the chain target), and loads
the rest from the card when a pattern needs it. A pattern switch whose samples are not all in the DSP yet does not happen:
the playing pattern runs once more and the switch comes at a later sequence end.

While a pattern plays on the main screen, the samples of the neighbouring patterns and of the chain target are read ahead
into free ARM RAM, so a later switch copies RAM to DSP instead of reading the card. That RAM is a cache only during normal
playback: every other screen (import, export, sampling, resampling, every menu) and every call of the firmware's work buffer
giver drop it, and the next PLAY on the main screen starts filling it again. A sum over each cached sample is checked before
the sample is entered into its slot, so a cache written by someone else is never used.

    python3 tools/patch/sample_swap.py --vsb SYSTEM.VSB [--out data/patches/sample-swap.json]

The patch is on only when the file is larger than the user bank and EXIT was not held at power-on; otherwise every hook passes
on at once and the firmware loads as before. The blue Synth is refused: its RAM places are not mapped.

Hooks (the same addresses in both builds, checked byte for byte):
  0xC00364F4  after the library loader's prologue: a latched DSP fault refuses the load before clearing sample metadata
  0xC0036510  the loader's f_open: the file's size decides whether the swap is on, the path is kept
  0xC00366D8  the loader's loop, before the seek of a slot: samples the current pattern does not use are skipped
  0xC003621C  the sample parser after the format checks: for the swap's own reads it returns with the slot's descriptor
  0xC00369F0  the work buffer giver: drops the cache
  0xC00836F4  the UI task's frame (25 Hz): drops the cache off the main screen or under a window on it (the sampling
              mode is one), starts a fill session at PLAY, posts a step
  0xC002D684  the command task's dispatch: the posted step runs there, where the firmware does all its card work
  0xC005F1D4  the sequence end's switch: a pattern whose samples are not ready is not switched to
  0xC0079A74  the chain's switch: the same for the chain target, with the repeat counter kept at its last round
Boot recovery precedes the collection's open. The slot writer appends verified records and commits their index through a
recovery journal; its import service is not yet bound to the normal controls. Nothing of the firmware is copied or written to flash.
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import ramdecl  # noqa: E402
import sample_swap_io  # noqa: E402
import sample_store  # noqa: E402
import sample_import  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

# Code and state in FF runs of both builds that no patch of the BLECH set uses (data/patch-ram.mjs).
CODE1, CODE1_END = 0xC01A2FD0, 0xC01A3C00
CODE2, CODE2_END = 0xC018A4C0, 0xC018AF00
CODE3, CODE3_END = 0xC0189760, 0xC0189F00
TRANSPORT, TRANSPORT_END = 0xC018BF40, 0xC018C400
STORE_CODE, STORE_CODE_END = 0xC019A400, 0xC019C400
STATE, STATE_END = 0xC0188530, 0xC0188730
# RAM above the interrupt stack, never touched by the firmware in any measured phase (docs/messungen/2026-10-22-ram-frei.md).
HIGH, HIGH_END = 0xC274F000, 0xC4000000
STAGE = HIGH                    # 96 KiB of file bytes for one chunk, then 16-bit PCM
FIL = 0xC2767100                # the swap's own FatFs file object
DESC = 0xC2767400               # a slot's descriptor as the parser built it
DESC2 = 0xC2767900              # the copy the firmware's slot entry may change
HDR = 0xC2768000                # the file's 4096-byte header: 16 bytes of name, then the slot offsets
DIR = 0xC2769000                # per slot 16 bytes: cache entry, PCM bytes, sum, generation
LIST = 0xC276D000               # active DSP extents while a place is searched
ARENA_U, ARENA_U_END = 0xC276F000, HIGH_END
# The firmware's work buffer (giver 0xC00369F0): borrowed only while the cache is valid.
ARENA_L, ARENA_L_END = 0xC1010000, 0xC273AA40

CAP_DEFAULT = 0x1900000         # the DSP user bank above the factory samples, 0x365EC0 to 0x1C65EC0
CHUNK = 0x10000                 # DSP bytes per chunk, the transport's largest call
BUDGET = 150_000_000 // 1000 * 15  # timer 3 ticks (150 MHz) one command task step may work for: 15 ms
MSG = 0x7E                      # the step's command number; the firmware's table ends at 44
MAIN = 1                        # the main screen
KILL = 0x2000                   # EXIT held at power-on

# State words (STATE + offset). FF at power-on; the loader's f_open hook sets them when the swap goes on.
FIELDS = """MODE GEN SESSION WASPLAY POSTED REQ FILE FILEGEN PREP P_LEN P_BITS P_FBYTES J_STATE J_SLOT J_SRC J_DST
J_LEN J_DONE J_BITS J_BASE J_ENTRY J_SUM J_GEN J_STAGED J_TICKS CPTR CGEN CFILL PFULL LASTRUN T0 GOT HDRFOR
TSTATE STAT_COUNT STAT_BYTES STAT_TICKS STAT_SRC""".split()
OFF = {name: 4 * i for i, name in enumerate(FIELDS)}
FAILED = 0xA0                   # 1024 bits, a slot that cannot be loaded
PROT = 0x120                    # 32 half words: the live pattern's and the target's samples
PATH = 0x160                    # the file's path as the loader opened it, 128 bytes
assert 4 * len(FIELDS) <= FAILED and PATH + 128 <= STATE_END - STATE

FIRST_USER, LAST_USER = 500, 998
SAMPLE_COUNT = LAST_USER + 1
SAMPLE_COUNT_AT = 0xC004E3C4

FIRMWARE = dict(
    F_OPEN=0xC009DB60, F_READ=0xC009DD74, F_LSEEK=0xC009E404, F_CLOSE=0xC009E3DC,
    PARSER=0xC0035B10, RESERVE=0xC004EDF0, DELETE=0xC004E558, POST=0xC002D5D8,
    PLAYER=0xC002FAFC, PSEL=0xC00431F0, TRANSPORT=0xC0030D28, REPEATS=0xC004A3D8,
    PART=0xC009AF20, PART_UPDATE=0xC0099FFC, VOICE_USED=0xC009115C, VOICES=0xC06916A0,
    PATPTR=0xC033E6A4, BANK=0xC08B2940, PANEL=0xC033E6F8,
    NAMES=0xC047B080, META=0xC036AD88, MAP_A=0xC035738C, MAP_B=0xC035F06C, MAP_C=0xC0350644,
    CURSOR=0xC00F9C80, DSP_MIN=0x365EC0, DSP_END=0x1C65EC0, TIMER=0x01F0D000,
    SWITCH=0xC0079AA8, SKIP_NEXT=0xC0036708, PARSE_OUT=0xC00363F0,
)

# (site, original word or None for a bl whose target must be `calls`, calls, stub, link, start phase, note)
SITES = [
    (0xC00364F4, 0xE24DDD21, None, "ss_library", False, True,
     "a latched DSP fault refuses a library load before the native metadata reset"),
    (0xC0036510, None, 0xC009DB60, "ss_fopen", True, True,
     "the loader's f_open goes through the hook, which turns the swap on for a file larger than the user bank"),
    (0xC00366D8, 0xE28D001C, None, "ss_skip", False, True,
     "the loader skips a slot the current pattern does not use while the swap is on"),
    (0xC003621C, 0xE59D1008, None, "ss_parse", False, True,
     "the sample parser returns with the descriptor when the swap reads a slot for itself"),
    (0xC00369F0, 0xE59F3008, None, "ss_giver", False, True,
     "the work buffer giver drops the swap's cache before it hands the buffer out"),
    (0xC00836F4, 0xE1A00004, None, "ss_frame", True, True,
     "the UI frame drops the cache off the main screen and posts the swap's step"),
    (0xC002D684, 0xE3A03001, None, "ss_cmd", False, True,
     "the command task's dispatch runs the swap's step for its own command number"),
    (0xC005F1D4, None, 0xC0079AA8, "ss_gate_seq", True, False,
     "the sequence end does not switch to a pattern whose samples are not loaded yet"),
    (0xC0079A74, 0xE5840318, None, "ss_gate_chain", False, False,
     "the chain does not switch to a target whose samples are not loaded yet; its counter stays at the last round"),
    (0xC0099FFC, 0xE92D4038, None, "ss_part_update", False, True,
     "the part update keeps its actual sample until the requested PCM is resident"),
    (0xC0099D88, 0xE5903008, None, "ss_part_bind", False, True,
     "direct part binding waits for an indexed sample to finish loading"),
]

# Native calls and the layouts they read, compared byte for byte in both red builds.
CALLED = (
    (0xC00369F0, 0x10, "giver"),
    (0xC004A3D8, 0x0C, "chain repeat count"),
    (0xC0079768, 0x10, "chain counter reset"),
    (0xC003B7FC, 0x1C, "event builder of the command post"),
    (0xC009DB60, 0xB00, "FatFs open, read, write, close and seek"),
    (0xC009E9B8, 0x148, "FatFs unlink"),
    (0xC004E1F4, 0x14, "sample descriptor initializer"),
    (0xC009115C, 0x34, "voice allocation state"),
    (0xC009AF20, 0x38, "part table getter"),
    (0xC00998B4, 0x90, "voice sample binding"),
    (0xC0091F5C, 0xD0, "voice pool layout"),
    (0xC004E558, 0x68, "CPU-only sample deletion"),
    (0xC004E2F0, 0x34, "physical sample lookup"),
    (0xC0099D88, 0x320, "part sample binding and update"),
)


def halfword(source):
    """ldrh/strh with an immediate or register offset as .word lines; the assembler knows no half word transfers."""
    def one(m):
        op, rd, rn, off = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        load = op == "ldrh"
        if off is None or off.startswith("#"):
            imm = int(off[1:], 0) if off else 0
            assert 0 <= imm < 256, m.group(0)
            word = 0xE1C000B0 | load << 20 | rn << 16 | rd << 12 | (imm >> 4) << 8 | imm & 15
        else:
            word = 0xE18000B0 | load << 20 | rn << 16 | rd << 12 | int(off[1:])
        return f".word {word:#010x}"
    return re.sub(r"\b(ldrh|strh) r(\d+), \[r(\d+)(?:, (#\w+|r\d+))?\]", one, source)


def equs(screens):
    names = {**FIRMWARE, "SCREENS": screens, "ST": STATE, "CODE1": CODE1, "CODE2": CODE2, "CODE3": CODE3,
             "STORE_CODE": STORE_CODE, "STAGE": STAGE, "FIL": FIL, "DESC": DESC, "DESC2": DESC2,
             "HDR": HDR, "DIR": DIR, "LIST": LIST, "ARENA_U": ARENA_U, "ARENA_U_END": ARENA_U_END, "ARENA_L": ARENA_L,
             "ARENA_L_END": ARENA_L_END, "CHUNK": CHUNK, "BUDGET": BUDGET, "MSG": MSG, "MAIN": MAIN, "KILL": KILL,
             "FAILED": FAILED, "PROT": PROT, "PATH": PATH, "STATE_WORDS": len(FIELDS),
             "LAST_USER": LAST_USER, "SAMPLE_COUNT": SAMPLE_COUNT, "CAP_DEFAULT": CAP_DEFAULT,
             "BUSY": sample_swap_io.BUSY, **OFF}
    return "".join(f".equ {k}, {v:#x}\n" for k, v in names.items())


SOURCE = r"""
.org CODE1
ss_cap:
    .word CAP_DEFAULT

; ------------------------------------------------------------- the loader at start (command task)
ss_library:
    ldr r12, =ST
    ldr r12, [r12, #TSTATE]
    cmn r12, #1
    cmpne r12, #0
    movne r0, #4
    popne {r4-r11, pc}
    sub sp, sp, #0x840
    b 0xC00364F8

; Replaces the loader's bl f_open (r0 file object, r1 path, r2 mode). Off unless the file is larger than the user bank.
ss_fopen:
    push {r3-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r7, r2
    ldr r11, =ST
    ldr r8, [r11, #MODE]
    cmp r8, #1
    cmpne r8, #2
    moveq r0, #2
    movne r0, #0
    str r0, [r11, #MODE]
    ldr r9, [r11, #TSTATE]
    ldr r10, [r11, #GEN]
    add r10, r10, #1
    str r10, [r11, #GEN]
    cmn r9, #1
    moveq r9, #0
    str r9, [r11, #TSTATE]
    mov r0, #0
    add r1, r11, #8
    mov r2, #STATE_WORDS - 2
fo_reset:
    sub r3, r1, r11
    cmp r3, #TSTATE
    cmpne r3, #FILE
    strne r0, [r1]
    add r1, r1, #4
    subs r2, r2, #1
    bne fo_reset
    mvn r0, #0
    str r0, [r11, #REQ]
    str r0, [r11, #LASTRUN]
    str r0, [r11, #FILEGEN]
    bl clear_failed
    bl cache_reset
    bl close_reader
    cmp r0, #0
    bne fo_fault
fo_transport:
    cmp r9, #0
    bne fo_fault
    cmp r5, #0
    beq fo_fault
    add r1, r11, #PATH
    mov r2, #0
fo_copy:
    ldrb r3, [r5, r2]
    strb r3, [r1, r2]
    cmp r3, #0
    beq fo_recover
    add r2, r2, #1
    cmp r2, #127
    blo fo_copy
    mov r0, #0
    strb r0, [r1]
    b fo_fault
fo_recover:
    mov r0, r5
    bl store_recover
    cmp r0, #0
    bne fo_fault
    mov r0, r4
    mov r1, r5
    mov r2, r7
    bl F_OPEN
    mov r6, r0
    cmp r6, #0
    bne fo_out
    mov r8, #0
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq fo_mode
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    bne fo_mode
    ldr r0, [r4, #0xc]
    ldr r1, =ss_cap
    ldr r1, [r1]
    add r1, r1, #0x1000
    cmp r0, r1
    bls fo_mode
    mov r8, #1
fo_mode:
    str r8, [r11, #MODE]
    b fo_out
fo_fault:
    mov r0, #2
    str r0, [r11, #MODE]
    mov r6, #1
fo_out:
    mov r0, r6
    pop {r3-r11, pc}

; Replaces add r0, sp, #0x1c in the loader's loop (r5 the header, r8 behind the slot's offset): with the swap on, a slot
; the current pattern does not use is skipped. The header is kept for the swap.
ss_skip:
    push {r0-r3, r12, lr}
    ldr r12, =ST
    ldr r0, [r12, #MODE]
    cmp r0, #1
    bne sk_load
    ldr r0, [r12, #HDRFOR]
    cmp r0, r5
    beq sk_have
    str r5, [r12, #HDRFOR]
    ldr r0, =HDR
    mov r1, r5
    mov r2, #0x1000
sk_copy:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne sk_copy
sk_have:
    sub r1, r8, r5
    sub r1, r1, #0x14
    mov r1, r1, lsr #2
    ldr r0, =PATPTR
    ldr r0, [r0]
    cmp r0, #0
    beq sk_load
    add r0, r0, #0x800
    add r0, r0, #0xc
    mov r2, #16
sk_part:
    ldrh r3, [r0]
    cmp r3, r1
    beq sk_load
    add r0, r0, #0x330
    subs r2, r2, #1
    bne sk_part
    pop {r0-r3, r12, lr}
    b SKIP_NEXT
sk_load:
    pop {r0-r3, r12, lr}
    add r0, sp, #0x1c
    b 0xC00366DC

; Replaces ldr r1, [sp, #8] in the sample parser, after its format checks (r8 descriptor, r6 PCM bytes in the DSP). For the
; swap's own reads it keeps the lengths and returns 0x7E before anything of the slot or the DSP changes.
ss_parse:
    ldr r12, =ST
    ldr r1, [r12, #PREP]
    cmp r1, #1
    bne pr_plain
    mov r1, #0
    str r1, [r12, #PREP]
    str r6, [r12, #P_LEN]
    ldr r1, [sp, #0x20]
    str r1, [r12, #P_FBYTES]
    ldrb r1, [sp, #0x32]
    str r1, [r12, #P_BITS]
    mov r3, #0x7e
    b PARSE_OUT
pr_plain:
    ldr r1, [sp, #8]
    b 0xC0036220

; Replaces the work buffer giver's first instruction: every user of the buffer drops the cache before it gets it.
ss_giver:
    ldr r12, =ST
    ldr r3, [r12, #GEN]
    add r3, r3, #1
    str r3, [r12, #GEN]
    mov r3, #0
    str r3, [r12, #SESSION]
    str r3, [r12, #CFILL]
    ldr r3, =0x1A00100
    str r3, [r0]
    ldr r0, =0xC0D3A940
    bx lr

; ------------------------------------------------------------- UI task, 25 Hz
; Called instead of mov r0, r4 in the frame function (r4 its object, returned in r0).
ss_frame:
    push {r0-r3, r12, lr}
    ldr r12, =ST
    ldr r0, [r12, #MODE]
    cmp r0, #1
    bne fr_out
    bl TRANSPORT
    ldr r2, [r0, #0x308]
    ldr r12, =ST
    ldr r0, =SCREENS
    ldr r0, [r0]
    cmp r0, #0
    beq fr_out
    ldr r1, [r0, #0x2c]
    ldr r3, [r0, #0x24]
    cmp r3, #0
    movne r1, #0
    cmp r1, #MAIN
    beq fr_main
    ldr r0, [r12, #SESSION]
    ldr r3, [r12, #CFILL]
    orrs r0, r0, r3
    beq fr_post
    ldr r0, [r12, #GEN]
    add r0, r0, #1
    str r0, [r12, #GEN]
    mov r0, #0
    str r0, [r12, #SESSION]
    str r0, [r12, #CFILL]
    b fr_post
fr_main:
    cmp r2, #1
    movne r2, #0
    ldr r3, [r12, #WASPLAY]
    str r2, [r12, #WASPLAY]
    cmp r2, #1
    bne fr_post
    cmp r3, #1
    movne r0, #1
    strne r0, [r12, #SESSION]
fr_post:
    ldr r0, [r12, #POSTED]
    cmp r0, #0
    bne fr_out
    mov r0, #1
    str r0, [r12, #POSTED]
    mov r0, #MSG
    mov r1, #0
    mov r2, #0
    bl POST
fr_out:
    pop {r0-r3, r12, lr}
    mov r0, r4
    bx lr

; ------------------------------------------------------------- sequencer task: the two switches
; Replaces bl 0xC0079AA8 at the sequence end (r0 the player, r1 the number to start, r2 0).
ss_gate_seq:
    push {r0-r2, r4, r5, lr}
    ldr r4, =ST
    ldr r3, [r4, #MODE]
    cmp r3, #1
    cmpne r3, #2
    bne gs_go
    ldr r3, [r0, #0x318]
    cmp r1, r3
    beq gs_go
    mov r5, r1
    mov r0, r1
    bl ready
    cmp r0, #0
    bne gs_go
    str r5, [r4, #REQ]
    ldr r0, [sp]
    ldr r3, [r0, #0x318]
    str r3, [sp, #4]
gs_go:
    pop {r0-r2, r4, r5, lr}
    b SWITCH

; Replaces str r0, [r4, #0x318] in the chain step (r0 the target, r4 the player, r6 the pattern's accessor).
ss_gate_chain:
    push {r0-r3, r12, lr}
    ldr r12, =ST
    ldr r1, [r12, #MODE]
    cmp r1, #1
    cmpne r1, #2
    bne gc_ok
    bl ready
    cmp r0, #0
    bne gc_ok
    ldr r0, [sp]
    ldr r12, =ST
    str r0, [r12, #REQ]
    mov r0, r6
    bl REPEATS
    subs r0, r0, #1
    movmi r0, #0
    str r0, [r4, #0x31c]
    pop {r0-r3, r12, lr}
    pop {r4, r5, r6, pc}
gc_ok:
    pop {r0-r3, r12, lr}
    str r0, [r4, #0x318]
    b 0xC0079A78

; r0 = pattern: 1 when every user sample of its bank block is in the DSP. Reads only.
ready:
    push {r4-r6, lr}
    cmp r0, #250
    movhs r0, #1
    pophs {r4-r6, pc}
    ldr r4, =BANK + 0x808
    add r4, r4, r0, lsl #14
    mov r5, #16
rd_part:
    ldrh r0, [r4]
    cmp r0, #500
    blo rd_next
    ldr r1, =LAST_USER
    cmp r0, r1
    bhi rd_next
    bl resident
    cmp r0, #0
    popeq {r4-r6, pc}
rd_next:
    add r4, r4, #0x330
    subs r5, r5, #1
    bne rd_part
    mov r0, #1
    pop {r4-r6, pc}

; r0 = slot: 1 when it is in the file, not marked as failed and not in the DSP. Clobbers r1-r3, r12.
needs:
    push {r4, lr}
    mov r4, r0
    bl loadable
    cmp r0, #0
    popeq {r4, pc}
    mov r0, r4
    bl resident
    eor r0, r0, #1
    pop {r4, pc}

; r0 = slot: 1 for a user slot with an offset in the header. Clobbers r1.
indexed:
    cmp r0, #500
    blo ix_no
    ldr r1, =LAST_USER
    cmp r0, r1
    bhi ix_no
    ldr r1, =HDR + 16
    ldr r1, [r1, r0, lsl #2]
    cmp r1, #0
    movne r0, #1
    bxne lr
ix_no:
    mov r0, #0
    bx lr

; r0 = slot: 1 for an indexed user slot that is not marked as failed. Clobbers r1-r3, r12.
loadable:
    push {r4, lr}
    mov r4, r0
    bl indexed
    cmp r0, #0
    popeq {r4, pc}
    ldr r1, =ST + FAILED
    mov r2, r4, lsr #5
    ldr r1, [r1, r2, lsl #2]
    and r2, r4, #31
    mov r3, #1
    tst r1, r3, lsl r2
    bne lo_no
    mov r0, #1
    pop {r4, pc}
lo_no:
    mov r0, #0
    pop {r4, pc}

; r0 = slot: 1 when the firmware's tables say its sample is in the DSP. Clobbers r1-r3.
resident:
    push {r12, lr}
    bl physical
    ldr r1, =SAMPLE_COUNT
    cmp r0, r1
    movhs r0, #0
    pophs {r12, pc}
    ldr r1, =0x45C
    mul r2, r0, r1
    ldr r3, =META + 11
    ldrb r0, [r3, r2]
    cmp r0, #1
    movne r0, #0
    pop {r12, pc}

; r0 PCM bytes: rounded user-bank size, or zero for an invalid sample. Clobbers r1.
pcm_size:
    cmp r0, #0
    bxeq lr
    tst r0, #1
    movne r0, #0
    bxne lr
    ldr r1, =CAP_DEFAULT
    cmp r0, r1
    movhi r0, #0
    bxhi lr
    add r0, r0, #31
    bic r0, r0, #31
    bx lr

; r0 visible slot: physical metadata index, or -1 when its mapping is invalid. Clobbers r1-r3.
physical:
    ldr r3, =SAMPLE_COUNT
    cmp r0, r3
    bhs re_no
    ldr r1, =NAMES
    add r1, r1, r0, lsl #5
    ldrh r0, [r1, #30]
; r0 cached import number: physical metadata index, or -1.
physical_import:
    ldr r3, =SAMPLE_COUNT
    subs r1, r0, #50
    bmi re_no
    cmp r1, r3
    bhs re_no
    mov r0, r3
    ldr r2, =MAP_A
    add r2, r2, r1, lsl #5
    ldrh r2, [r2, #16]
    cmp r2, r0
    bhs re_no
    ldr r3, =MAP_B
    add r3, r3, r2, lsl #4
    ldrh r3, [r3, #8]
    cmp r3, r0
    bhs re_no
    ldr r2, =MAP_C
    add r2, r2, r3, lsl #3
    ldrh r2, [r2, #2]
    cmp r2, r0
    bhs re_no
    mov r0, r2
    bx lr
re_no:
    mvn r0, #0
    bx lr

; r0 user slot: 1 when neither patterns, actual parts nor allocated voices use its physical sample.
can_evict:
    push {r4-r8, lr}
    mov r4, r0
    cmp r4, #500
    blo ce_no
    ldr r1, =LAST_USER
    cmp r4, r1
    bhi ce_no
    bl resident
    cmp r0, #0
    beq ce_no
    mov r0, r4
    bl physical
    mov r5, r0
    cmp r5, #500
    blo ce_no
    ldr r0, =0x45C
    mul r1, r5, r0
    ldr r0, =META
    ldr r0, [r0, r1]
    ldr r1, =DSP_MIN
    cmp r0, r1
    blo ce_no
    ldr r1, =DSP_END
    cmp r0, r1
    bhs ce_no
    add r6, r11, #PROT
    mov r7, #32
ce_pattern:
    ldrh r0, [r6]
    add r6, r6, #2
    cmp r0, r4
    beq ce_no
    bl physical
    cmp r0, r5
    beq ce_no
    subs r7, r7, #1
    bne ce_pattern
    mov r6, #0
ce_part:
    mov r0, r6
    bl PART
    ldrh r0, [r0, #0x34]
    bl physical
    cmp r0, r5
    beq ce_no
    add r6, r6, #1
    cmp r6, #16
    blo ce_part
    ldr r6, =VOICES
    mov r7, #0
ce_voice:
    mov r0, r7
    bl VOICE_USED
    cmp r0, #0
    beq ce_next_voice
    ldr r0, [r6, #4]
    cmp r0, #0
    beq ce_no
    ldrh r0, [r6, #0x40]
    cmp r0, #50
    blo ce_next_voice
    bl physical_import
    cmn r0, #1
    beq ce_no
    cmp r0, r5
    beq ce_no
ce_next_voice:
    add r6, r6, #0x48
    add r7, r7, #1
    cmp r7, #24
    blo ce_voice
    mov r0, #1
    pop {r4-r8, pc}
ce_no:
    mov r0, #0
    pop {r4-r8, pc}

; A snapshot candidate, rechecked by evict_unused before any metadata changes.
victim:
    push {r4, lr}
    mov r4, #500
vi_slot:
    mov r0, r4
    bl can_evict
    cmp r0, #0
    movne r0, r4
    popne {r4, pc}
    add r4, r4, #1
    ldr r0, =LAST_USER
    cmp r4, r0
    bls vi_slot
    mov r0, #0
    pop {r4, pc}

; r0 candidate slot: IRQs stay masked only across its final check and the CPU-only delete.
evict_unused:
    push {r4, r5, r8, lr}
    mov r4, r0
    .word 0xE10F8000
    orr r1, r8, #0x80
    .word 0xE121F001
    bl swap_ok
    cmp r0, #0
    moveq r4, #0
    beq eu_done
    mov r0, r4
    bl can_evict
    cmp r0, #0
    moveq r4, #0
    beq eu_done
    ldr r1, =NAMES
    add r1, r1, r4, lsl #5
    ldrh r0, [r1, #30]
    sub r0, r0, #50
    bl DELETE
    mov r4, r0
eu_done:
    .word 0xE121F008
    mov r0, r4
    pop {r4, r5, r8, pc}

ss_part_update:
    push {r0-r4, r11, r12, lr}
    ldr r11, =ST
    bl part_ready
    cmp r0, #0
    popeq {r0-r4, r11, r12, pc}
    pop {r0-r4, r11, r12, lr}
    push {r3, r4, r5, lr}
    b 0xC009A000

ss_part_bind:
    push {r0-r4, r11, r12, lr}
    ldr r11, =ST
    bl part_ready
    cmp r0, #0
    popeq {r0-r4, r11, r12, pc}
    pop {r0-r4, r11, r12, lr}
    ldr r3, [r0, #8]
    b 0xC0099D8C

; r0 part: indexed user samples may bind only after their PCM is resident.
part_ready:
    push {r4, lr}
    mov r4, r0
    ldr r0, [r11, #MODE]
    cmp r0, #2
    beq pr_no
    cmp r0, #1
    bne pr_yes
    ldr r0, [r11, #TSTATE]
    cmp r0, #0
    bne pr_no
    ldr r0, [r4, #8]
    cmp r0, #0
    beq pr_no
    ldrh r4, [r0, #8]
    cmp r4, #500
    blo pr_yes
    ldr r0, =LAST_USER
    cmp r4, r0
    bhi pr_yes
    ldr r0, =HDR + 16
    ldr r0, [r0, r4, lsl #2]
    cmp r0, #0
    beq pr_yes
    mov r0, r4
    bl resident
    pop {r4, pc}
pr_yes:
    mov r0, #1
    pop {r4, pc}
pr_no:
    mov r0, #0
    pop {r4, pc}

; Refresh only parts that requested the sample whose transfer just completed.
apply_ready_parts:
    push {r4-r6, lr}
    mov r5, r0
    mov r4, #0
arp_part:
    mov r0, r4
    bl PART
    mov r6, r0
    ldr r1, [r0, #8]
    cmp r1, #0
    beq arp_next
    ldrh r1, [r1, #8]
    cmp r1, r5
    bne arp_next
    mov r0, r6
    bl PART_UPDATE
arp_next:
    add r4, r4, #1
    cmp r4, #16
    blo arp_part
    pop {r4-r6, pc}
.pool

.org CODE2
; ------------------------------------------------------------- command task: the step
; Replaces mov r3, #1 at the dispatch of the command runner (r0 the runner, r1 the event, +4 its command number).
ss_cmd:
    ldrb r12, [r1, #4]
    cmp r12, #MSG
    beq ss_step
    mov r3, #1
    b 0xC002D688

ss_step:
    push {r3-r11, lr}
    ldr r11, =ST
    mov r0, #0
    str r0, [r11, #POSTED]
    ldr r0, [r11, #MODE]
    cmp r0, #1
    bne st_ret
    ldr r0, [r11, #TSTATE]
    cmp r0, #0
    movne r0, #2
    strne r0, [r11, #MODE]
    bne st_ret
    bl swap_ok
    cmp r0, #0
    bne st_context
    bl pause_jobs
    b st_ret
st_context:
    bl PLAYER
    ldr r0, [r0, #0x318]
    ldr r1, [r11, #LASTRUN]
    cmp r0, r1
    beq st_same
    str r0, [r11, #LASTRUN]
    ldr r1, [r11, #REQ]
    cmp r1, r0
    mvneq r1, #0
    streq r1, [r11, #REQ]
    bl clear_failed
    ldr r0, [r11, #PFULL]
    cmp r0, #0
    blne cache_reset
    mov r0, #0
    str r0, [r11, #PFULL]
st_same:
    ldr r0, =TIMER
    ldr r0, [r0, #0x10]
    str r0, [r11, #T0]
st_loop:
    bl swap_ok
    cmp r0, #0
    bne st_work
    bl pause_jobs
    b st_ret
st_work:
    ldr r0, [r11, #J_STATE]
    cmp r0, #1
    beq st_chunk
    bl pick
    cmp r0, #0
    beq st_ret
    b st_budget
st_chunk:
    bl chunk
    cmp r0, #2
    beq st_ret
st_budget:
    ldr r0, [r11, #T0]
    bl since
    ldr r1, =BUDGET
    cmp r0, r1
    blo st_loop
st_ret:
    pop {r3-r11, pc}

; r0 = an earlier reading of timer 3: ticks since then.
since:
    ldr r1, =TIMER
    ldr r2, [r1, #0x10]
    subs r0, r2, r0
    ldrmi r3, [r1, #0x18]
    addmi r0, r0, r3
    addmi r0, r0, #1
    bx lr

; Starts the next job: first what the live pattern misses, then what the target misses, then, while the cache may fill,
; the samples of the chain target and the two neighbours. r0 = 0 when there is nothing to do.
pick:
    push {r4-r8, lr}
    ldr r0, =PATPTR
    ldr r0, [r0]
    cmp r0, #0
    beq pk_none
    add r0, r0, #0x800
    add r0, r0, #0xc
    add r1, r11, #PROT
    bl parts16
    bl target
    mov r5, r0
    add r1, r11, #PROT + 32
    cmp r5, #250
    ldrlo r0, =BANK + 0x808
    addlo r0, r0, r5, lsl #14
    blo pk_tparts
    mvn r0, #0
    mov r2, #16
pk_none16:
    strh r0, [r1]
    add r1, r1, #2
    subs r2, r2, #1
    bne pk_none16
    b pk_scan0
pk_tparts:
    bl parts16
pk_scan0:
    add r6, r11, #PROT
    mov r7, #32
pk_scan:
    ldrh r0, [r6]
    bl needs
    cmp r0, #0
    bne pk_install
    add r6, r6, #2
    subs r7, r7, #1
    bne pk_scan
    ldr r0, [r11, #PFULL]
    cmp r0, #0
    bne pk_none
    bl fill_ok
    cmp r0, #0
    beq pk_none
    ldr r0, =PATPTR
    ldr r0, [r0]
    ldr r1, =0x3B04
    ldrh r0, [r0, r1]
    sub r0, r0, #1
    bl prefetch
    cmp r0, #0
    bne pk_done
    ldr r4, [r11, #LASTRUN]
    add r0, r4, #1
    cmp r0, #250
    movhs r0, #0
    bl prefetch
    cmp r0, #0
    bne pk_done
    subs r0, r4, #1
    movmi r0, #249
    bl prefetch
    cmp r0, #0
    bne pk_done
pk_none:
    mov r0, #0
    pop {r4-r8, pc}
pk_install:
    ldrh r0, [r6]
    bl start_install
    pop {r4-r8, pc}
pk_done:
    mov r0, #1
    pop {r4-r8, pc}

; r0 = pattern: starts reading the first of its samples the cache should hold. r0 = 1 when a job started or failed.
prefetch:
    push {r4, r5, r6, lr}
    cmp r0, #250
    bhs pf_none
    ldr r4, =BANK + 0x808
    add r4, r4, r0, lsl #14
    mov r5, #16
pf_part:
    ldrh r6, [r4]
    mov r0, r6
    bl needs
    cmp r0, #0
    beq pf_next
    mov r0, r6
    bl cached
    cmp r0, #0
    bne pf_next
    mov r0, r6
    bl start_prepare
    mov r0, #1
    pop {r4, r5, r6, pc}
pf_next:
    add r4, r4, #0x330
    subs r5, r5, #1
    bne pf_part
pf_none:
    mov r0, #0
    pop {r4, r5, r6, pc}

; The pattern that comes next: one the switch refused, else the chosen one, else the chain target of the live pattern; -1 none.
target:
    push {r4, lr}
    ldr r0, [r11, #REQ]
    cmp r0, #250
    blo tg_out
    bl PSEL
    ldrb r1, [r0, #0x341]
    cmp r1, #0
    ldrne r0, [r0, #0x318]
    bne tg_check
    ldr r0, =PATPTR
    ldr r0, [r0]
    cmp r0, #0
    beq tg_none
    ldr r1, =0x3B04
    ldrh r0, [r0, r1]
    sub r0, r0, #1
tg_check:
    cmp r0, #250
    blo tg_out
tg_none:
    mvn r0, #0
tg_out:
    pop {r4, pc}

; 1 when the cache may be filled: a PLAY session on the main screen that nothing dropped.
fill_ok:
    push {r4, lr}
    ldr r0, [r11, #SESSION]
    cmp r0, #1
    bne fk_no
    bl swap_ok
    cmp r0, #0
    beq fk_no
    bl TRANSPORT
    ldr r0, [r0, #0x308]
    cmp r0, #1
    bne fk_no
    mov r0, #1
    pop {r4, pc}
fk_no:
    mov r0, #0
    pop {r4, pc}

; Only the unobscured main screen in a sequencer state may use the swap buffers or DSP allocator.
swap_ok:
    push {r4, lr}
    ldr r0, =SCREENS
    ldr r0, [r0]
    cmp r0, #0
    beq so_no
    ldr r1, [r0, #0x24]
    cmp r1, #0
    bne so_no
    ldr r0, [r0, #0x2c]
    cmp r0, #MAIN
    bne so_no
    bl TRANSPORT
    cmp r0, #0
    beq so_no
    ldr r1, [r0, #0x308]
    cmp r1, #5
    bhi so_no
    ldrb r0, [r0, #0x312]
    cmp r0, #0
    bne so_no
    mov r0, #1
    pop {r4, pc}
so_no:
    mov r0, #0
    pop {r4, pc}

job_ok:
    push {r4, lr}
    bl swap_ok
    cmp r0, #0
    bleq pause_jobs
    pop {r4, pc}

pause_jobs:
    ldr r0, [r11, #J_STATE]
    ldr r1, [r11, #J_STAGED]
    orr r0, r0, r1
    ldr r1, [r11, #SESSION]
    orr r0, r0, r1
    ldr r1, [r11, #CFILL]
    orrs r0, r0, r1
    ldrne r0, [r11, #GEN]
    addne r0, r0, #1
    strne r0, [r11, #GEN]
    mov r0, #0
    str r0, [r11, #J_STATE]
    str r0, [r11, #J_STAGED]
    str r0, [r11, #SESSION]
    str r0, [r11, #CFILL]
    bx lr

; r0 = the first part's sample in a pattern block, r1 = 16 half words to fill.
parts16:
    mov r2, #16
p16:
    ldrh r3, [r0]
    strh r3, [r1]
    add r0, r0, #0x330
    add r1, r1, #2
    subs r2, r2, #1
    bne p16
    bx lr

; r0 = slot: 1 when the cache holds it in this generation.
cached:
    ldr r1, =DIR
    add r1, r1, r0, lsl #4
    ldr r2, [r1]
    cmp r2, #0
    beq ca_no
    ldr r2, [r1, #12]
    ldr r3, [r11, #GEN]
    cmp r2, r3
    moveq r0, #1
    bxeq lr
ca_no:
    mov r0, #0
    bx lr

clear_failed:
    add r0, r11, #FAILED
    mov r1, #0
    mov r2, #32
cf_loop:
    str r1, [r0], #4
    subs r2, r2, #1
    bne cf_loop
    bx lr

; r0 = slot
set_failed:
    add r1, r11, #FAILED
    mov r2, r0, lsr #5
    ldr r3, [r1, r2, lsl #2]
    and r0, r0, #31
    mov r12, #1
    orr r3, r3, r12, lsl r0
    str r3, [r1, r2, lsl #2]
    bx lr

cache_reset:
    ldr r0, =DIR
    add r1, r0, #16000
    mov r2, #0
cr_loop:
    str r2, [r0], #16
    cmp r0, r1
    blo cr_loop
    ldr r0, =ARENA_U
    str r0, [r11, #CPTR]
    ldr r0, [r11, #GEN]
    str r0, [r11, #CGEN]
    bx lr

; r0 dst, r1 src, r2 bytes (a multiple of 32).
copy32:
    push {r4-r10}
c32:
    ldmia r1!, {r3-r10}
    stmia r0!, {r3-r10}
    subs r2, r2, #32
    bne c32
    pop {r4-r10}
    bx lr

; r0 buffer, r1 bytes (a multiple of 4): r0 = their sum as words.
sum32:
    mov r2, #0
s32:
    ldr r3, [r0], #4
    add r2, r2, r3
    subs r1, r1, #4
    bne s32
    mov r0, r2
    bx lr
.pool

; ------------------------------------------------------------- the card
; r11 state. FILE is 0 when closed, 1 when open, 2 until an uncertain close succeeds.
close_reader:
    push {r4, lr}
    ldr r0, [r11, #FILE]
    cmp r0, #1
    cmpne r0, #2
    bne cr_closed
    mov r0, #2
    str r0, [r11, #FILE]
    mvn r0, #0
    str r0, [r11, #FILEGEN]
    ldr r0, =FIL
    bl F_CLOSE
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
cr_closed:
    mov r0, #0
    str r0, [r11, #FILE]
    mvn r1, #0
    str r1, [r11, #FILEGEN]
    pop {r4, pc}
.pool

; Opens the file again when nothing is open or the cache generation moved on (the file may have changed), and reads its
; header. r0 = 0 when it is open.
ensure_file:
    push {r4, lr}
    ldr r4, [r11, #GEN]
    ldr r0, [r11, #FILE]
    cmp r0, #1
    bne ef_close
    ldr r0, [r11, #FILEGEN]
    cmp r0, r4
    moveq r0, #0
    popeq {r4, pc}
ef_close:
    bl close_reader
    cmp r0, #0
    bne ef_fail
ef_open:
    ldr r0, =FIL
    add r1, r11, #PATH
    mov r2, #1
    bl F_OPEN
    cmp r0, #0
    bne ef_fail
    mov r0, #1
    str r0, [r11, #FILE]
    ldr r0, =FIL
    ldr r1, =HDR
    mov r2, #0x1000
    add r3, r11, #GOT
    bl F_READ
    cmp r0, #0
    bne ef_read_fail
    ldr r0, [r11, #GOT]
    cmp r0, #0x1000
    bne ef_read_fail
    mov r0, #1
    str r0, [r11, #FILE]
    str r4, [r11, #FILEGEN]
    ldr r1, [r11, #GEN]
    cmp r4, r1
    moveq r0, #0
    movne r0, #1
    pop {r4, pc}
ef_read_fail:
    bl close_reader
ef_fail:
    mov r0, #2
    str r0, [r11, #MODE]
    mov r0, #1
    pop {r4, pc}
.pool

.org CODE3
; r0 = slot: the firmware's parser reads its metadata into DESC and stops before the slot or the DSP change; the file is
; then at the slot's audio. r0 = 0 when it went through.
parse:
    push {r4, lr}
    mov r4, r0
    bl ensure_file
    cmp r0, #0
    bne pa_fail
    ldr r1, =HDR + 16
    ldr r1, [r1, r4, lsl #2]
    ldr r0, =FIL
    bl F_LSEEK
    cmp r0, #0
    bne pa_fail
    mov r0, #1
    str r0, [r11, #PREP]
    ldr r0, =FIL
    ldr r1, =DESC
    mvn r2, #0
    mov r3, #0
    bl PARSER
    mov r1, #0
    str r1, [r11, #PREP]
    cmp r0, #0x7e
    bne pa_fail
    ldr r0, [r11, #P_LEN]
    cmp r0, #0
    beq pa_fail
    mov r0, #0
    pop {r4, pc}
pa_fail:
    mov r0, #1
    pop {r4, pc}

; r0 slot: starts a DSP copy from RAM or card. Returns 0 for a deferred attempt, 1 for a started job or bad source.
start_install:
    push {r4-r8, lr}
    mov r4, r0
    ldr r1, [r11, #GEN]
    str r1, [r11, #J_GEN]
    bl cached
    cmp r0, #0
    beq si_card
    ldr r0, =DIR
    add r0, r0, r4, lsl #4
    ldr r6, [r0]
    ldr r7, [r0, #4]
    mov r8, #1
    mov r0, #16
    str r0, [r11, #P_BITS]
    b si_place
si_card:
    mov r0, r4
    bl parse
    ldr r1, [r11, #J_GEN]
    ldr r2, [r11, #GEN]
    cmp r1, r2
    movne r0, #0
    popne {r4-r8, pc}
    cmp r0, #0
    bne si_fail
    ldr r7, [r11, #P_LEN]
    mov r6, #0
    mov r8, #0
si_place:
    mov r0, r7
    bl pcm_size
    cmp r0, #0
    beq si_fail
    bl place
    ldr r1, [r11, #J_GEN]
    ldr r2, [r11, #GEN]
    cmp r1, r2
    movne r0, #0
    popne {r4-r8, pc}
    cmp r0, #0
    beq si_wait
    .word 0xE10F5000
    orr r1, r5, #0x80
    .word 0xE121F001
    push {r0, r5}
    bl swap_ok
    cmp r0, #0
    beq si_reserve_stop
    ldr r1, [r11, #J_GEN]
    ldr r2, [r11, #GEN]
    cmp r1, r2
    bne si_reserve_stop
    ldr r0, [sp]
    add r1, r7, #31
    bic r1, r1, #31
    add r1, r0, r1
    ldr r2, =CURSOR
    ldr r3, [r2]
    cmp r1, r3
    strhi r1, [r2]
    str r0, [r11, #J_BASE]
    pop {r0, r5}
    .word 0xE121F005
    mov r0, #0
    str r0, [r11, #J_DST]
    b job_common
si_reserve_stop:
    pop {r0, r5}
    .word 0xE121F005
    mov r0, #0
    b si_wait
si_fail:
    mov r0, r4
    bl set_failed
    mov r0, #1
si_wait:
    pop {r4-r8, pc}

; r0 = slot: starts reading it from the card into the cache.
start_prepare:
    push {r4-r8, lr}
    mov r4, r0
    ldr r1, [r11, #GEN]
    str r1, [r11, #J_GEN]
    bl parse
    ldr r1, [r11, #J_GEN]
    ldr r2, [r11, #GEN]
    cmp r1, r2
    popne {r4-r8, pc}
    cmp r0, #0
    bne sp_fail
    ldr r7, [r11, #P_LEN]
    mov r0, r7
    bl pcm_size
    cmp r0, #0
    beq sp_fail
    add r5, r0, #0x4A0
    ldr r0, [r11, #CGEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    beq sp_have
    bl cache_reset
sp_have:
    ldr r6, [r11, #CPTR]
    ldr r0, =ARENA_U
    cmp r6, r0
    blo sp_lower
    ldr r1, =ARENA_U_END
    cmp r6, r1
    bhi sp_fail
    add r2, r6, r5
    cmp r2, r1
    bls sp_ok
    ldr r6, =ARENA_L
sp_lower:
    ldr r0, =ARENA_L
    cmp r6, r0
    blo sp_fail
    ldr r1, =ARENA_L_END
    add r2, r6, r5
    cmp r2, r1
    bls sp_ok
    mov r0, #1
    str r0, [r11, #PFULL]
    pop {r4-r8, pc}
sp_ok:
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    movne r0, #0
    popne {r4-r8, pc}
    str r6, [r11, #CPTR]
    mov r0, r6
    ldr r1, =DESC
    mov r2, #0x4A0
    bl copy32
    mov r8, #0
    mov r0, #1
    str r0, [r11, #J_DST]
    str r6, [r11, #J_BASE]
    b job_common
sp_fail:
    mov r0, r4
    bl set_failed
    pop {r4-r8, pc}

; r4 slot, r6 cache entry (source or target), r7 PCM bytes, r8 source (0 card, 1 cache); returns for the two starters.
job_common:
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    movne r0, #0
    popne {r4-r8, pc}
    str r4, [r11, #J_SLOT]
    str r8, [r11, #J_SRC]
    str r6, [r11, #J_ENTRY]
    str r7, [r11, #J_LEN]
    ldr r0, [r11, #P_BITS]
    str r0, [r11, #J_BITS]
    mov r0, #0
    str r0, [r11, #J_DONE]
    str r0, [r11, #J_SUM]
    str r0, [r11, #J_STAGED]
    str r0, [r11, #J_TICKS]
    mov r0, #1
    str r0, [r11, #J_STATE]
    pop {r4-r8, pc}

; r0 = DSP bytes (a multiple of 32): a free place in the user bank, after moving out samples that neither the live pattern
; nor the target use. r0 = 0 when there is none.
place:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, #500
pl_try:
    mov r0, r4
    bl first_fit
    cmp r0, #0
    popne {r4-r6, pc}
    subs r5, r5, #1
    beq pl_none
    bl victim
    cmp r0, #0
    beq pl_none
    bl evict_unused
    cmp r0, #0
    beq pl_none
    b pl_try
pl_none:
    mov r0, #0
    pop {r4-r6, pc}

; r0 = DSP bytes: the lowest 32-byte aligned place in the user bank, up to its budget, that overlaps no active sample.
first_fit:
    push {r4-r10, lr}
    mov r4, r0
    ldr r5, =LIST
    mov r6, r5
    ldr r7, =META
    mov r8, #0
    ldr r10, =DSP_MIN
ff_scan:
    ldrb r0, [r7, #11]
    cmp r0, #1
    bne ff_next
    ldr r0, [r7]
    cmp r0, r10
    blo ff_next
    ldr r1, [r7, #4]
    add r1, r0, r1
    stmia r6!, {r0, r1}
ff_next:
    ldr r0, =0x45C
    add r7, r7, r0
    add r8, r8, #1
    ldr r0, =SAMPLE_COUNT
    cmp r8, r0
    blo ff_scan
    ldr r9, =ss_cap
    ldr r9, [r9]
    add r9, r9, r10
    ldr r0, =DSP_END
    cmp r9, r0
    movhi r9, r0
    mov r7, r10
    mov r10, r5
    b ff_check
ff_cand:
    cmp r10, r6
    bhs ff_none
    ldr r7, [r10, #4]
    add r10, r10, #8
    add r7, r7, #31
    bic r7, r7, #31
ff_check:
    add r8, r7, r4
    cmp r8, r9
    bhi ff_cand
    mov r0, r5
ff_over:
    cmp r0, r6
    bhs ff_found
    ldmia r0!, {r1, r2}
    cmp r1, r8
    bhs ff_over
    cmp r2, r7
    bls ff_over
    b ff_cand
ff_found:
    mov r0, r7
    pop {r4-r10, pc}
ff_none:
    mov r0, #0
    pop {r4-r10, pc}

; One chunk of the running job. r0 = 0 go on, 1 the job ended, 2 stop this step (the port is busy, or a fault).
chunk:
    push {r4-r10, lr}
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne ck_end
    ldr r0, =TIMER
    ldr r9, [r0, #0x10]
    ldr r4, [r11, #J_LEN]
    ldr r5, [r11, #J_DONE]
    sub r6, r4, r5
    cmp r6, #CHUNK
    movhi r6, #CHUNK
    add r7, r6, #31
    bic r7, r7, #31
    ldr r0, [r11, #J_STAGED]
    cmp r0, #0
    bne ck_out
    ldr r0, [r11, #J_SRC]
    cmp r0, #1
    beq ck_cache
    ldr r0, [r11, #J_BITS]
    cmp r0, #24
    moveq r2, r6, lsr #1
    addeq r2, r2, r6
    movne r2, r6
    mov r8, r2
    ldr r0, =FIL
    ldr r1, =STAGE
    add r3, r11, #GOT
    bl F_READ
    cmp r0, #0
    bne ck_fail
    ldr r0, [r11, #GOT]
    cmp r0, r8
    bne ck_fail
    ldr r0, [r11, #J_BITS]
    cmp r0, #24
    bne ck_pad
    ldr r0, =STAGE
    mov r1, r0
    mov r2, r6, lsr #1
ck_conv:
    ldrb r3, [r1, #1]
    ldrb r12, [r1, #2]
    strb r3, [r0], #1
    strb r12, [r0], #1
    add r1, r1, #3
    subs r2, r2, #1
    bne ck_conv
ck_pad:
    ldr r0, =STAGE
    add r1, r0, r6
    add r2, r0, r7
    mov r3, #0
ck_zero:
    cmp r1, r2
    strblo r3, [r1], #1
    blo ck_zero
    b ck_sum
ck_cache:
    ldr r1, [r11, #J_ENTRY]
    add r1, r1, #0x4A0
    add r1, r1, r5
    ldr r0, =STAGE
    mov r2, r7
    bl copy32
ck_sum:
    ldr r0, =STAGE
    mov r1, r7
    bl sum32
    ldr r1, [r11, #J_SUM]
    add r1, r1, r0
    str r1, [r11, #J_SUM]
    str r6, [r11, #J_STAGED]
ck_out:
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne ck_end
    bl job_ok
    cmp r0, #0
    beq ck_defer
    ldr r0, [r11, #J_DST]
    cmp r0, #1
    beq ck_tocache
    mov r0, #1
    ldr r1, =STAGE
    ldr r2, [r11, #J_BASE]
    add r2, r2, r5
    mov r3, r7, lsr #1
    bl transfer
    cmp r0, #BUSY
    moveq r0, #2
    popeq {r4-r10, pc}
    cmp r0, #0
    beq ck_moved
    mov r0, #2
    str r0, [r11, #MODE]
    mov r0, #0
    str r0, [r11, #J_STATE]
    mov r0, #2
    pop {r4-r10, pc}
ck_tocache:
    ldr r0, [r11, #J_BASE]
    add r0, r0, #0x4A0
    add r0, r0, r5
    ldr r1, =STAGE
    mov r2, r7
    bl copy32
ck_moved:
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne ck_end
    bl job_ok
    cmp r0, #0
    beq ck_defer
    add r5, r5, r6
    str r5, [r11, #J_DONE]
    mov r0, #0
    str r0, [r11, #J_STAGED]
    mov r0, r9
    bl since
    ldr r1, [r11, #J_TICKS]
    add r1, r1, r0
    str r1, [r11, #J_TICKS]
    cmp r5, r4
    movlo r0, #0
    poplo {r4-r10, pc}
    ldr r6, [r11, #J_SLOT]
    ldr r0, [r11, #J_DST]
    cmp r0, #1
    bne ck_enter
    ldr r0, =DIR
    add r0, r0, r6, lsl #4
    ldr r1, [r11, #J_BASE]
    ldr r2, [r11, #J_SUM]
    ldr r3, [r11, #J_GEN]
    str r1, [r0]
    str r4, [r0, #4]
    str r2, [r0, #8]
    str r3, [r0, #12]
    add r4, r4, #31
    bic r4, r4, #31
    add r1, r1, r4
    add r1, r1, #0x4A0
    str r1, [r11, #CPTR]
    mov r0, #1
    str r0, [r11, #CFILL]
    b ck_end
ck_enter:
    ldr r0, [r11, #J_SRC]
    cmp r0, #1
    bne ck_desc_card
    ldr r0, =DIR
    add r0, r0, r6, lsl #4
    ldr r0, [r0, #8]
    ldr r1, [r11, #J_SUM]
    cmp r0, r1
    beq ck_desc_cache
    ldr r0, [r11, #GEN]
    add r0, r0, #1
    str r0, [r11, #GEN]
    mov r0, #0
    str r0, [r11, #SESSION]
    str r0, [r11, #CFILL]
    b ck_end
ck_desc_cache:
    ldr r1, [r11, #J_ENTRY]
    b ck_desc
ck_desc_card:
    ldr r1, =DESC
ck_desc:
    ldr r0, =DESC2
    mov r2, #0x4A0
    bl copy32
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne ck_end
    bl job_ok
    cmp r0, #0
    beq ck_defer
    ldr r2, =CURSOR
    ldr r7, [r2]
    ldr r0, [r11, #J_BASE]
    str r0, [r2]
    ldr r0, =DESC2
    bl RESERVE
    mov r8, r0
    ldr r2, =CURSOR
    ldr r3, [r2]
    cmp r7, r3
    strhi r7, [r2]
    cmp r8, #0
    beq ck_fail
    mov r0, r6
    bl resident
    cmp r0, #0
    beq ck_fail
    mov r0, r6
    bl apply_ready_parts
    ldr r0, [r11, #STAT_COUNT]
    add r0, r0, #1
    str r0, [r11, #STAT_COUNT]
    str r4, [r11, #STAT_BYTES]
    ldr r0, [r11, #J_TICKS]
    str r0, [r11, #STAT_TICKS]
    ldr r0, [r11, #J_SRC]
    str r0, [r11, #STAT_SRC]
    b ck_end
ck_defer:
    mov r0, #2
    pop {r4-r10, pc}
ck_fail:
    ldr r0, [r11, #J_SLOT]
    bl set_failed
ck_end:
    mov r0, #0
    str r0, [r11, #J_STATE]
    mov r0, #1
    pop {r4-r10, pc}
.pool
"""


def source(screens):
    importer = sample_import.source(state=STATE, file=FIL, descriptor=DESC, normalizer=FIL + 0x240,
                                    prep=OFF["PREP"], bits=OFF["P_BITS"], file_bytes=OFF["P_FBYTES"])
    body = SOURCE + "\n.org STORE_CODE\n" + sample_store.source(STAGE) + importer
    return halfword(equs(screens) + f".equ transfer, {TRANSPORT:#x}\n" + body)


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def screens_of(vsb):
    sys.path.insert(0, str(Path(__file__).parent.parent / "emu"))
    import firmware
    return firmware.identify(vsb[HEADER:]).screens


AREAS = ((CODE1, CODE1_END, "CODE1_END"), (CODE2, CODE2_END, "CODE2_END"), (CODE3, CODE3_END, "CODE3_END"),
         (STORE_CODE, STORE_CODE_END, "STORE_CODE_END"),
         (TRANSPORT, TRANSPORT_END, "TRANSPORT_END"))


def build_code(screens):
    """(sections [(address, bytes)], symbols): swap, storage and bounded transport code."""
    code = arm.assemble(source(screens), origin=CODE1)
    io, _ = sample_swap_io.build_code(origin=TRANSPORT, state=STATE + OFF["TSTATE"])
    sections = [*code.sections, (TRANSPORT, io)]
    for at, data in sections:
        hi = next(hi for lo, hi, _ in AREAS if lo <= at < hi)
        if at + len(data) > hi:
            raise SystemExit(f"code at {at:#x} is {len(data):#x} bytes, room for {hi - at:#x}")
    return sections, {**code.symbols, "transfer": TRANSPORT}


def redirect(word, at, target):
    return (word & 0xFF000000) | (((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb, build=None):
    if len(vsb) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    actual = sample_swap_io.validate_firmware(vsb)
    if build not in (None, actual) or actual not in ("stock", "hacktribe"):
        raise SystemExit("only the mapped red Sampler builds, Korg's and Hacktribe, are supported")
    if struct.unpack_from("<I", vsb, file_offset(SAMPLE_COUNT_AT))[0] != SAMPLE_COUNT:
        raise SystemExit("the native sample table count is not the mapped count")
    screens = screens_of(vsb)
    sections, symbols = build_code(screens)

    def was(addr, n=4):
        return vsb[file_offset(addr):file_offset(addr) + n]

    for at, length, what in CALLED:
        if sha(was(at, length)) != CALLED_SHA[at]:
            raise SystemExit(f"the {what} at {at:#x} is not the measured code")

    changes, start, hooks = [], [], []
    for at, data in sections:
        if was(at, len(data)) != b"\xff" * len(data):
            raise SystemExit(f"{at:#x}..{at + len(data):#x} is not free in this VSB")
        changes.append({"file": file_offset(at), "bytes": data.hex(), "expect": sha(was(at, len(data))),
                        "note": "sample swap: bounded DSP transport" if at == symbols["transfer"] else "sample swap: code"})
        start.append({"file": file_offset(at), "length": len(data),
                      "why": "the loader's hooks run while e2sSample.all loads, the frame and command hooks from the first frame on"})
    for site, original, calls, stub, link, boot, note in SITES:
        word = struct.unpack("<I", was(site))[0]
        if original is not None:
            ok = word == original
        else:
            offset = ((word & 0xFFFFFF) ^ 0x800000) - 0x800000
            ok = (word & 0x0F000000) == 0x0B000000 and site + 8 + offset * 4 == calls
        if not ok:
            raise SystemExit(f"the instruction at {site:#x} is not where the patch expects it in this VSB")
        new = redirect(0xEB000000 if link else 0xEA000000, site, symbols[stub])
        changes.append({"file": file_offset(site), "bytes": struct.pack("<I", new).hex(), "expect": sha(was(site)), "note": note})
        if boot:
            start.append({"file": file_offset(site), "length": 4, "why": "runs before the main screen and passes on at once while the swap is off"})
        hooks.append({"site": f"0x{site:08X}", "kind": "instruction", "chain": "sample-swap", "position": "before",
                      "swallow": stub in ("ss_skip", "ss_parse", "ss_cmd", "ss_gate_chain"), "note": note})
    ram = [ramdecl.area(STATE, STATE_END - STATE, "run time state of the sample swap: mode, cache generation, the running job, failed slots, the file's path", "tools/patch/sample_swap.py:STATE"),
           ramdecl.area(HIGH, HIGH_END - HIGH, "staging buffer, file object, descriptors, header, cache index and the upper cache of the sample swap", "tools/patch/sample_swap.py:HIGH")]
    for lo, hi, name in AREAS:
        end = max(at + len(data) for at, data in sections if lo <= at < hi)
        if end < hi:
            ram.append(ramdecl.area(end, hi - end, "unused code room of the sample swap", f"tools/patch/sample_swap.py:{name}"))
    return {
        "format": "gelumpe-patch", "version": 1, "id": "sample-swap",
        "builds": ["hacktribe", "stock"],
        "name": "Sample-Swap: größere Sample-Datei als der DSP-Speicher",
        "changes": changes,
        "startPhase": start,
        "hooks": hooks,
        "ram": ram,
    }


CALLED_SHA = {
    0xC00369F0: "a7d23f74586936ec6866a848f54213f688dd8ce3dce2d848dfd0fa2fa72ac7d3",
    0xC004A3D8: "f0c285da7e342df0813bc2e614de39930ac11479aabcb5448e660a23d6431093",
    0xC0079768: "e8014e3bdef321b0885d7e7224608407c1f094f089a270441413b68f72928204",
    0xC003B7FC: "fd8f006c9e0687d555e18f66b74e990a56c3cf53a7b1239bf8919b320b3c6237",
    0xC009DB60: "1fee2e34672d676636cc44dfeaf6fffb0085766fe43b513f2250c023df11c2cf",
    0xC009E9B8: "c780e1a223851dc1480a08a7038091cfa03672277490b6167311edf40ad5c1c8",
    0xC004E1F4: "3c697676bad05a608c6dc09d8dde53321fe6ab01eeb6ef94055c5fb8409f32ac",
    0xC009115C: "09fe21fa4fbda3f46cb888c38bfc24ae3752427cd7b02f600b91596189ad5bb1",
    0xC009AF20: "5d6e8fdc70e16ac964ebe6353d8fded9f1d4068684f426825c0628d1198988ed",
    0xC00998B4: "827982f7904668b6486154341fd2d0bcf490d89d4c17de404abc671765bc272f",
    0xC0091F5C: "7fcc3f9b41ebdd6daa9229bdec96f133a8453d91d60a958573a748c003ef424f",
    0xC004E558: "dbf2300087233dba96787b8a3f74659ae678fffe2f61d538ea12df6a87185ddf",
    0xC004E2F0: "675b2a102036631fc0d01634272bfb9fbf536b8f9ece00d30423b6d1a3a0fcd1",
    0xC0099D88: "9ce2ec5c3423766f300330cb1ae2e0b18713d17a29761e718a3ff3d7cf7b2556",
}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    patch = build_patch(a.vsb.read_bytes())
    text = json.dumps(patch, indent=1, ensure_ascii=False) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
