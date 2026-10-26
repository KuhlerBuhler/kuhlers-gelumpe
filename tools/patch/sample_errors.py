"""Builds the sample error patch (docs/messungen/2026-10-15-sample-fehler.md) for firmware 2.02, Hacktribe and Korg's own build.

When the firmware loads e2sSample.all (at start, and again for a restore from the card), it stops at the first sample it
cannot take and shows "Error / Unknown Error." (or "Format Error.") without saying which sample or why. With this patch the
loader skips such a sample and goes on with the next one, and at the end the window names the first one it skipped:

    title    Sample 371
    message  8 bit, use 16/24        (or: not PCM, tag 3 / 3 channels, max 2 / slot in use / slot not usable /
                                      too big for memory / bad WAV file / cannot be loaded)

Only the two codes the loader returns before it has changed anything are skipped: 32 (the format check, shown by the firmware
as "Format Error.") and 36 (the sample could not be entered into its slot, shown as "Unknown Error."). Every other code, among
them a read error and "Memory Full", stops the load as before. The window is the firmware's own with a code of ours (0x40),
which the window class does not know and so would show as "Unknown Error."; two hooks hand it our two lines instead.

    python3 tools/patch/sample_errors.py --vsb SYSTEM.VSB [--out data/patches/sample-errors.json] [--listing]

Hooks (the same addresses in both builds, checked byte for byte):
  0xC00364F0  the loader's first instruction: clears our state and runs the loader with the card at 25 MHz instead of 12.5
              (SD default speed; docs/messungen/2026-10-25-sd-takt.md), only from the firmware's own divider; a load that
              ends in a card error runs once more at 12.5 MHz
  0xC0035FB4, 0xC0035FC4, 0xC0035FD4  the three branches of the sample function that refuse a format (tag, channels, bits):
              they remember which and the value, then go where they went before
  0xC004EE0C, 0xC004EE50, 0xC004EE68  the three branches of the slot function that refuse a sample (slot not usable, in use,
              too big): the same
  0xC0036700  after the sample function returns: a 32 or 36 is counted and the loop goes on, anything else is as before
  0xC0036714  the loop is complete: with a sample skipped the loader returns our code, after the two lines are built
  0xC00630F0, 0xC0063144  the two text objects of the error window: with our code they get our lines

With EXIT held at power-on every hook goes straight to the original. Nothing of the firmware is copied.
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
import sample_seek  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC0183000            # free (FF) in the image, behind the start image editor's area and before Blechy's block at 0xC0184000
CODE_END = 0xC0183700
STATE = 0xC0183800              # run time state and the two lines, in RAM only
STATE_END = 0xC0183900
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)
PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 the keys held at power-on
OUR_CODE = 0x40                 # the result byte the loader returns when a sample was skipped; the firmware knows codes up to 35

LOADER = 0xC00364F0
SAMPLE_FORMAT = [0xC0035FB4, 0xC0035FC4, 0xC0035FD4]
SAMPLE_FAIL = 0xC0035B70
SLOT_REFUSE = [0xC004EE0C, 0xC004EE50, 0xC004EE68]
SLOT_FAIL = 0xC004EEFC
RESULT = 0xC0036700
DONE = 0xC0036714
LOOP_NEXT = 0xC0036708
LOOP_END = 0xC0036718
ALLOC = 0xC0028DCC
WINDOW_TITLE = 0xC00630F0
WINDOW_TEXT = 0xC0063144
MMCCLK = 0x01C40004             # MMC0's clock register: bit 8 on, bits 0-7 CLKRT; the card runs at 150 MHz / (2 * (CLKRT + 1))
CLKRT_FIRMWARE, CLKRT_FAST = 5, 2  # 12.5 MHz as the firmware sets it, 25 MHz (SD default speed)
CARD_ERROR = 4                  # the loader's result for a read error of the card, "Card Error"

# the state: counts, the first skipped sample, and what the two refusing places said
S_COUNT, S_IDX, S_ORIG, S_REASON, S_VAL, S_FREASON, S_FVAL = 0, 4, 8, 12, 16, 20, 24
S_TITLE, S_TEXT = 0x40, 0x60
R_TAG, R_CHANNELS, R_BITS, R_CATEGORY, R_USE, R_BIG = 1, 2, 3, 4, 5, 6

SOURCE = f"""
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ STATE, {STATE:#x}
.equ TITLE, {STATE + S_TITLE:#x}
.equ TEXT, {STATE + S_TEXT:#x}
.equ OURS, {OUR_CODE}
.equ LOADER_BACK, {LOADER + 4:#x}
.equ SAMPLE_FAIL, {SAMPLE_FAIL:#x}
.equ SLOT_FAIL, {SLOT_FAIL:#x}
.equ LOOP_NEXT, {LOOP_NEXT:#x}
.equ RESULT_BACK, {RESULT + 4:#x}
.equ LOOP_END, {LOOP_END:#x}
.equ ALLOC, {ALLOC:#x}
.equ MMCCLK, {MMCCLK:#x}
.equ CLKRT_FIRMWARE, {CLKRT_FIRMWARE}
.equ CLKRT_FAST, {CLKRT_FAST}
.equ CARD_ERROR, {CARD_ERROR}
.equ S_COUNT, {S_COUNT}
.equ S_IDX, {S_IDX}
.equ S_ORIG, {S_ORIG}
.equ S_REASON, {S_REASON}
.equ S_VAL, {S_VAL}
.equ S_FREASON, {S_FREASON}
.equ S_FVAL, {S_FVAL}
.equ R_TAG, {R_TAG}
.equ R_CHANNELS, {R_CHANNELS}
.equ R_BITS, {R_BITS}
.equ R_CATEGORY, {R_CATEGORY}
.equ R_USE, {R_USE}
.equ R_BIG, {R_BIG}

.org {CODE_AT:#x}

; r12 = 1 when EXIT was held at power-on, else 0. Only r12 changes.
killed:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    moveq r12, #1
    bxeq lr
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    movne r12, #1
    moveq r12, #0
    bx lr

; ---- the loader's first instruction: the state starts empty for every load, the card runs at 25 MHz --------------
; Replaces push {{r4-r11, lr}}: the loader runs as a call from here (loader_body), so its result comes back. The card goes from
; the firmware's 12.5 MHz to 25 MHz (device 25.10.: 3.1 to 5.2 MiB/s); a load that ends in a card error (4) is run once more
; at 12.5 MHz, and only that result reaches the caller, which shows "Card Error" for a 4 as before.
loader_entry:
    push {{r0, lr}}             ; the path and the caller
    bl killed
    cmp r12, #0
    bne entry_plain
    bl entry_clear
    bl clock_fast
    cmp r0, #0
    beq entry_plain
    ldr r0, [sp]
    bl loader_body
    cmp r0, #CARD_ERROR
    bne entry_out
    bl clock_slow
    bl entry_clear
entry_plain:
    ldr r0, [sp]
    bl loader_body
entry_out:
    pop {{r1, lr}}
    bx lr
loader_body:
    push {{r4, r5, r6, r7, r8, r9, r10, r11, lr}}
    b LOADER_BACK

entry_clear:                    ; the state empty; r1, r2 and r12 change
    ldr r12, =STATE
    mov r1, #0
    mov r2, #0x40
entry_clear_next:
    subs r2, r2, #4
    str r1, [r12, r2]
    bne entry_clear_next
    bx lr

; the card's divider from the firmware's to the fast one, r0 = 1 when it changed; any other divider is left alone. The clock is
; off while the divider changes, as the TRM asks. r1, r2 and r12 change.
clock_fast:
    ldr r12, =MMCCLK
    ldr r1, [r12]
    and r2, r1, #0xFF
    cmp r2, #CLKRT_FIRMWARE
    movne r0, #0
    bxne lr
    mov r2, #CLKRT_FAST
    b clock_set
clock_slow:                     ; back to the firmware's divider
    ldr r12, =MMCCLK
    ldr r1, [r12]
    mov r2, #CLKRT_FIRMWARE
clock_set:                      ; r1 = the register, r2 = the divider
    bic r1, r1, #0x100
    str r1, [r12]
    bic r1, r1, #0xFF
    orr r1, r1, r2
    str r1, [r12]
    orr r1, r1, #0x100
    str r1, [r12]
    mov r0, #1
    bx lr

; ---- the places that refuse a sample: they say why, then go where they went before ---------------------------------
; r0 to r3, r12 and lr are free at all six (the code they go to sets its result and returns)
fmt_tag:                        ; r3 = the format tag of the fmt chunk
    mov r0, #R_TAG
    b refused_r3
fmt_bits:                       ; r3 = bits per sample
    mov r0, #R_BITS
refused_r3:
    mov r2, r3
    b refused_sample
fmt_channels:                   ; r11 = channels
    mov r0, #R_CHANNELS
    mov r2, r11
refused_sample:
    ldr r1, =SAMPLE_FAIL
    b refused

slot_category:                  ; the slot's category is not one a sample may have
    mov r0, #R_CATEGORY
    mov r2, r3
    b refused_slot
slot_use:                       ; the slot is in use
    mov r0, #R_USE
    mov r2, #0
    b refused_slot
slot_big:                       ; r2 = the length of the sample in bytes, more than is free
    mov r0, #R_BIG
refused_slot:
    ldr r1, =SLOT_FAIL

; r0 = reason, r2 = value, r1 = where to go on
refused:
    mov r3, r1
    bl killed
    cmp r12, #0
    bne refused_go
    ldr r12, =STATE
    str r0, [r12, #S_FREASON]
    str r2, [r12, #S_FVAL]
refused_go:
    bx r3

; ---- the sample function returned, r0 = its result; r8 points behind the table entry, r5 is the table -------------
result_hook:
    bl killed
    cmp r12, #0
    bne result_orig
    cmp r0, #32
    cmpne r0, #36
    bne result_orig
    ldr r12, =STATE
    ldr r1, [r12, #S_COUNT]
    cmp r1, #0
    bne result_counted
    sub r2, r8, r5
    sub r2, r2, #20
    lsr r2, r2, #2
    str r2, [r12, #S_IDX]
    str r0, [r12, #S_ORIG]
    ldr r2, [r12, #S_FREASON]
    str r2, [r12, #S_REASON]
    ldr r2, [r12, #S_FVAL]
    str r2, [r12, #S_VAL]
result_counted:
    add r1, r1, #1
    str r1, [r12, #S_COUNT]
    mov r2, #0
    str r2, [r12, #S_FREASON]
    b LOOP_NEXT
result_orig:
    subs r4, r0, #0
    b RESULT_BACK

; ---- every entry was visited ---------------------------------------------------------------------------------------
done_hook:
    mov r4, r6
    bl killed
    cmp r12, #0
    bne done_out
    ldr r12, =STATE
    ldr r0, [r12, #S_COUNT]
    cmp r0, #0
    beq done_out
    bl build_texts
    mov r4, #OURS
done_out:
    b LOOP_END

; the two lines of the window from the state
build_texts:
    push {{r4, lr}}
    ldr r4, =STATE
    ldr r0, =t_title
    ldr r1, =TITLE
    ldr r2, [r4, #S_IDX]
    add r2, r2, #1
    bl fill
    ldr r2, [r4, #S_REASON]
    ldr r0, =t_bad
    ldr r3, [r4, #S_ORIG]
    cmp r2, #0
    cmpeq r3, #36
    ldreq r0, =t_other
    cmp r2, #R_TAG
    ldreq r0, =t_tag
    cmp r2, #R_CHANNELS
    ldreq r0, =t_channels
    cmp r2, #R_BITS
    ldreq r0, =t_bits
    cmp r2, #R_CATEGORY
    ldreq r0, =t_category
    cmp r2, #R_USE
    ldreq r0, =t_use
    cmp r2, #R_BIG
    ldreq r0, =t_big
    ldr r1, =TEXT
    ldr r2, [r4, #S_VAL]
    bl fill
    pop {{r4, pc}}

; r0 = a template, r1 = where to write it, r2 = a number: the template is copied, a # becomes the number
fill:
    push {{r4, lr}}
    mov r4, r2
fill_next:
    ldrb r3, [r0], #1
    cmp r3, #0x23
    beq fill_number
    strb r3, [r1], #1
    cmp r3, #0
    bne fill_next
    pop {{r4, pc}}
fill_number:
    push {{r0}}
    mov r0, r4
    bl put_decimal
    pop {{r0}}
    b fill_next

; r0 = a number (cut at 9999), r1 = where to write it; r1 moves behind the digits
put_decimal:
    ldr r2, =10000
    cmp r0, r2
    subhs r0, r2, #1
    mov r3, #0
""" + "".join(f"""    mov r2, #0
pd{d}:
    cmp r0, #{d}
    subhs r0, r0, #{d}
    addhs r2, r2, #1
    bhs pd{d}
    orrs r3, r3, r2
    addne r2, r2, #0x30
    strbne r2, [r1], #1
""" for d in (1000, 100, 10)) + f"""    add r0, r0, #0x30
    strb r0, [r1], #1
    bx lr

; ---- the error window: our code gets our two lines ----------------------------------------------------------------
window_title:                   ; replaces the call that makes the title object (r0 = its size), r6 = the code
    cmp r6, #OURS
    ldreq r9, =TITLE
    b ALLOC
window_text:                    ; the same for the text object
    cmp r6, #OURS
    ldreq r9, =TEXT
    b ALLOC

t_title:
    .asciz "Sample #"
t_tag:
    .asciz "not PCM, tag #"
t_channels:
    .asciz "# channels, max 2"
t_bits:
    .asciz "# bit, use 16/24"
t_category:
    .asciz "slot not usable"
t_use:
    .asciz "slot in use"
t_big:
    .asciz "too big for memory"
t_bad:
    .asciz "bad WAV file"
t_other:
    .asciz "cannot be loaded"
.align 4
.pool
"""


SOURCE += sample_seek.parser_source(sample_seek.PARSER + 4)
SOURCE += sample_seek.seek_source(killed='killed')
SOURCE += '\n.pool\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_offset(addr):
    return addr - RAM + HEADER


def build_code():
    code = arm.assemble(SOURCE)
    (at, data), = code.sections
    return at, data, code.symbols


def redirect(word, at, target):
    """The branch `word` (at address `at`) with its condition and its link bit, aimed at `target`."""
    return (word & 0xFF000000) | (((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb):
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n=4):
        return vsb[file_offset(addr):file_offset(addr) + n]

    frame = arm.assemble('sub sp, sp, #0x4C0\nsub sp, sp, #12').bytes
    if was(sample_seek.PARSER + 8, len(frame)) != frame:
        raise SystemExit('the sample parser stack frame does not match its cursor checkpoint')

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    def hook(addr, stub, original=None, goes_to=None):
        """The word at `addr` aimed at our `stub`. `original` is the instruction it must be (it becomes a plain branch), or `goes_to`
        the target of the branch it must be (its condition and link bit stay)."""
        word = struct.unpack("<I", was(addr))[0]
        if original is not None:
            ok = word == original
        else:
            offset = ((word & 0xFFFFFF) ^ 0x800000) - 0x800000
            ok = (word & 0x0E000000) == 0x0A000000 and addr + 8 + offset * 4 == goes_to
        if not ok:
            raise SystemExit(f"the instruction at {addr:#x} is not where the patch expects it in this VSB")
        return struct.pack("<I", redirect(0xEA000000 if original is not None else word, addr, symbols[stub]))

    words = [
        (LOADER, "loader_entry", dict(original=0xE92D4FF0), "the loader's first instruction jumps to a stub that clears the state, raises the card clock and runs the loader, once more at 12.5 MHz after a card error",
         "the loader starts: the state of the skipped samples is cleared (all hooks pass on at once with EXIT held at power-on)"),
        (SAMPLE_FORMAT[0], "fmt_tag", dict(goes_to=SAMPLE_FAIL), "the branch that refuses a format tag other than PCM goes to a stub that notes it", None),
        (SAMPLE_FORMAT[1], "fmt_channels", dict(goes_to=SAMPLE_FAIL), "the branch that refuses a channel count other than 1 or 2 goes to a stub that notes it", None),
        (SAMPLE_FORMAT[2], "fmt_bits", dict(goes_to=SAMPLE_FAIL), "the branch that refuses a bit depth other than 16 or 24 goes to a stub that notes it", None),
        (SLOT_REFUSE[0], "slot_category", dict(goes_to=SLOT_FAIL), "the branch that refuses a slot of a category no sample may have goes to a stub that notes it", None),
        (SLOT_REFUSE[1], "slot_use", dict(goes_to=SLOT_FAIL), "the branch that refuses a slot that is in use goes to a stub that notes it", None),
        (SLOT_REFUSE[2], "slot_big", dict(goes_to=SLOT_FAIL), "the branch that refuses a sample longer than the free memory goes to a stub that notes it", None),
        (RESULT, "result_hook", dict(original=0xE2504000), "the instruction after the sample function (subs r4, r0, #0) jumps to a stub that skips a result of 32 or 36", None),
        (DONE, "done_hook", dict(original=0xE1A04006), "the instruction at the end of a complete load (mov r4, r6) jumps to a stub that returns our code when a sample was skipped",
         "when the loop is complete, the first skipped sample's two lines are built"),
        (WINDOW_TITLE, "window_title", dict(goes_to=ALLOC), "the call that makes the title object of the error window goes through a stub that gives our code its own title", None),
        (WINDOW_TEXT, "window_text", dict(goes_to=ALLOC), "the call that makes the text object of the error window goes through a stub that gives our code its own line", None),
    ]
    words.append((sample_seek.PARSER, 'sample_anchor_entry', dict(original=0xE92D4FF0),
                  'the sample parser keeps a private read cursor checkpoint on its stack', None))
    words.extend((site, 'sample_anchor_seek', dict(goes_to=sample_seek.LSEEK),
                  'backward seeks within a sample reuse its cursor checkpoint before FatFs continues', None)
                 for site in sample_seek.SITES)
    changes = [{"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
                "note": "sample errors: the stubs, the two lines and their texts"}]
    start = [{"file": file_offset(CODE_AT), "length": len(code),
              "why": "the stubs run while e2sSample.all loads, at start before the main screen and for a restore from the card"}]
    for addr, stub, how, note, why in words:
        changes.append({"file": file_offset(addr), "bytes": hook(addr, stub, **how).hex(), "expect": sha(was(addr)), "note": note})
        start.append({"file": file_offset(addr), "length": 4, "why": why or "inside the sample loader, which runs at start before the main screen, and calls the stub"})
    chain = "sample-errors"
    hooks = [{"site": f"0x{addr:08X}", "kind": "instruction", "chain": chain, "position": "before", "swallow": stub in ("result_hook", "done_hook"),
              "note": note} for addr, stub, _, note, _ in words]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "sample-errors",
        "builds": ["hacktribe", "stock"],
        "name": "Sample-Fehler: ein Sample überspringen und sagen, welches",
        "changes": changes,
        "startPhase": start,
        "hooks": hooks,
        "ram": [ramdecl.area(STATE, STATE_END - STATE, "run time state: count and reason of the first skipped sample, and the two lines of the error window", "tools/patch/sample_errors.py:STATE")],
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
