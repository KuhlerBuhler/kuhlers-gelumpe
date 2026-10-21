"""Builds the Blechy power-off patch (docs/messungen/2026-10-15-blechy-power-off.md) for firmware 2.02, Hacktribe and Korg's own build.

When the device switches off (the power key held about 2 s, or Auto Power Off), the firmware opens its window 0x1C,
a box with "Power Off", waits one second and then saves and lets go of the power hold (handler 0xC0038A54, CommandTask).
With this patch the wait shows a short sequence instead (sequence() below): Blechy waves
(assets/blechy/sprites/blechy-wave-1.png and -2.png) next to a line in his voice, then the picture fades and goes out
like an old tube. Only the first picture is stored; the arm of the second pose is 19 bytes, the rest is computed.

    python3 tools/patch/power_off.py --vsb SYSTEM.VSB [--out data/patches/power-off.json] [--png frame.png]

One hook, none in the start phase: the call of the wait function (0xC0000B78, 1000 ms) in the handler goes through our
code. It does what the original does, the same time in sleeps of 2 ms for the first 60 ms and then 10 ms (counted against the operating system's tick
count, so the total stays 1000 ms, and against the sum of the slices, so it ends even if the count stood still), and
between the sleeps it writes the picture of that moment into the display buffer (1024 bytes), which covers the box the
firmware keeps painting. Nothing of the save is touched: the save call, the flash and card writes and the moment the
power hold falls stay the firmware's own (measured in the emulator, docs/messungen/2026-10-15-blechy-power-off.md).

With EXIT held at power-on the call goes straight to the original wait, as in every patch (docs/patcher.md, "Notschalter").
The picture is our own art, nothing of the firmware is copied. Every address is a RAM address of the measured build; the
file offset in the VSB is address - 0xC0000000 + 0x100.
"""

import argparse
import functools
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import ramdecl  # noqa: E402
import synthaddr  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000
ROOT = Path(__file__).resolve().parents[2]

CODE_AT = 0xC01A5800            # free (FF) in all three builds, between MFX 2 (ends before 0xC01A5800) and its RAM at 0xC01A5C00
CODE_END = 0xC01A5BF0
OFF_ACTIVE = 0xC01A5BF0          # RAM: 1 from the start of the sequence; the look of the loading bar leaves such frames alone
FRAME_AT = 0xC01A4C00           # the picture, 128 x 64, 1024 bytes
FRAME_END = 0xC01A5000

WAIT_CALL = 0xC0038A74          # bl 0xC0000B78 in the power-off handler, r0 = 1000 ms
WAIT_FUNC = 0xC0000B78
DISPLAY = 0xC031B310            # the display buffer, byte (y / 8) * 128 + x, bit y % 8 (docs/hintergrund/skript-laufzeit.md, 4.1)
PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 held keys
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)
TICKS = 0xC06A292C              # the operating system's tick count, one per millisecond (measured); the wait function adds to it
SLICE_MS = 10                   # the picture is redrawn every 10 ms: the firmware paints parts of its box again and again,
                                # and the display frame (every 40 ms) has to find the picture in the buffer
EARLY_MS = 60                   # the box is painted when the window opens, at a time the display frame does not wait for:
SHORT_MS = 2                    # in the first 60 ms the picture goes over it every 2 ms

SPRITES = ROOT / "assets" / "blechy" / "sprites"
SPRITE = SPRITES / "blechy-wave-1.png"
WAVE = SPRITES / "blechy-wave-2.png"
FONT = ROOT / "data" / "script" / "font.mjs"
SPRITE_AT = (6, 4)              # top left of the 56 x 56 sprite
TEXT = ["Haus'te", "rin mein", "Akh"]
MENU_STATE = 0xC01D6E00         # the BLECH menu (tools/patch/script_hooks.py): +0 is 1 when armed, +0x1B8 is 1 with DISPLAY INVERT ON
M_INV = 0x1B8

# The sequence over the one second of the wait, in ms from its start: Blechy waves (the arm swaps every SLOT), the
# picture fades into the dark over the 4 x 4 Bayer grid, is pressed into eight rows like an old tube, shrinks to a line,
# a dot and goes dark. The picture is drawn light on dark: with DISPLAY INVERT ON the controller shows set bits light,
# otherwise the code complements the buffer, so the screen stays dark either way (as the loading bar does).
SLOT = 125
FADE_AT, FADE2_AT, TUBE_AT, LINE_AT, DOT_AT, DARK_AT = 700, 760, 820, 880, 930, 970
FADE, FADE2 = 6, 11
LINE_W, DOT_W = 72, 6
BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
TEXT_X = 68
TEXT_Y = 17
TEXT_STEP = 11


def sha(data):
    return hashlib.sha256(data).hexdigest()


# ---- the picture -------------------------------------------------------------------
def read_png(path):
    """Rows of 0 (black) and 1 (white) of a greyscale PNG with 1 to 8 bits (our own 1-bit sprites)."""
    raw = Path(path).read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} is not a PNG")
    at, idat, head = 8, b"", None
    while at < len(raw):
        n, kind = struct.unpack_from(">I4s", raw, at)
        body = raw[at + 8:at + 8 + n]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        at += 12 + n
    width, height, depth, colour, _, _, interlace = head
    if colour != 0 or interlace or depth not in (1, 2, 4, 8):
        raise SystemExit(f"{path}: only plain greyscale PNGs")
    stride = (width * depth + 7) // 8
    data = zlib.decompress(idat)
    rows, prev = [], bytearray(stride)
    for y in range(height):
        kind, line = data[y * (stride + 1)], bytearray(data[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        bpp = 1
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        rows.append([(line[x * depth // 8] >> (8 - depth - (x * depth) % 8)) & ((1 << depth) - 1) for x in range(width)])
    top = (1 << depth) - 1
    return [[1 if v * 2 > top else 0 for v in row] for row in rows]


def read_font():
    """The 5 x 7 font of the script display, {char: five column bytes, bit 0 the top row}."""
    rows = re.findall(r'"([0-9a-f]{10})"', FONT.read_text())
    if len(rows) != 0x7F - 0x20:
        raise SystemExit("the font table does not have the characters 0x20 to 0x7e")
    font = {chr(0x20 + i): bytes.fromhex(r) for i, r in enumerate(rows)}
    font["ü"] = bytes(b | dot for b, dot in zip(font["u"], (0, 1, 0, 1, 0)))   # "u" with two dots in the top row
    return font


def frame_pixels(sprite=None, text=None, text_y=TEXT_Y):
    """The whole display as rows of 0 and 1 (1 is a dark pixel): the sprite left, the text right."""
    grid = [[0] * 128 for _ in range(64)]
    sprite = read_png(SPRITE) if sprite is None else sprite
    for y, row in enumerate(sprite):
        for x, v in enumerate(row):
            if not v:
                grid[SPRITE_AT[1] + y][SPRITE_AT[0] + x] = 1
    font = read_font()
    for line, string in enumerate(TEXT if text is None else text):
        for i, ch in enumerate(string):
            for col, bits in enumerate(font[ch]):
                for row in range(7):
                    if bits >> row & 1:
                        grid[text_y + line * TEXT_STEP + row][TEXT_X + i * 6 + col] = 1
    return grid


def fade_mask(level):
    """Four bytes, one per x % 4: the bits of a column byte whose Bayer threshold is below `level` (the pattern repeats every 4 rows)."""
    return bytes(sum(1 << y for y in range(8) if BAYER[(y % 4) * 4 + x] < level) for x in range(4))


@functools.cache
def wave_diff():
    """The bytes where the second waving pose differs from the picture, as (offset, value)."""
    a, b = frame_bytes(frame_pixels()), frame_bytes(frame_pixels(read_png(WAVE)))
    return [(i, b[i]) for i in range(1024) if a[i] != b[i]]


@functools.cache
def base_frame():
    return frame_bytes(frame_pixels())


def sequence(ms, inverted=True):
    """The display buffer the code writes `ms` into the wait; `inverted` is DISPLAY INVERT ON with the BLECH menu armed."""
    out = bytearray(base_frame())
    if ms >= TUBE_AT or ms >= FADE_AT or (ms // SLOT) & 1:
        for i, v in wave_diff():
            out[i] = v
    if FADE_AT <= ms < TUBE_AT:
        mask = fade_mask(FADE if ms < FADE2_AT else FADE2)
        out = bytearray(v & ~mask[i & 3] & 255 for i, v in enumerate(out))
    elif ms >= TUBE_AT:
        pic, out = bytes(out), bytearray(1024)
        if ms < LINE_AT:
            for x in range(1, 128, 2):              # the even columns are dark at level 4 in the rows the tube keeps
                acc = sum(((pic[page * 128 + x] >> 4) & 1) << page for page in range(8))
                out[3 * 128 + x] = (acc & 15) << 4
                out[4 * 128 + x] = acc >> 4
        elif ms < DARK_AT:
            w = LINE_W if ms < DOT_AT else DOT_W
            for x in range(64 - w // 2, 64 - w // 2 + w):
                out[3 * 128 + x] = 0x80
                out[4 * 128 + x] = 0x01
    if not inverted:
        out = bytearray(v ^ 255 for v in out)
    return bytes(out)


def frame_bytes(grid):
    """The display buffer: byte (y / 8) * 128 + x, bit y % 8."""
    out = bytearray(1024)
    for y, row in enumerate(grid):
        for x, v in enumerate(row):
            if v:
                out[(y // 8) * 128 + x] |= 1 << (y % 8)
    return bytes(out)


def write_png(path, grid, scale=4):
    """The picture as the LCD shows it, for a look."""
    paper, ink = (174, 183, 154), (27, 36, 20)
    raw = bytearray()
    for row in grid:
        line = bytearray([0])
        for v in row:
            line += bytes(ink if v else paper) * scale
        raw += bytes(line) * scale

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    head = struct.pack(">IIBBBBB", 128 * scale, 64 * scale, 8, 2, 0, 0, 0)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))


# ---- the code ----------------------------------------------------------------------
def source():
    diff = "\n".join(f"    .word {(i << 8) | v:#x}" for i, v in wave_diff())
    return f"""
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ WAIT, {WAIT_FUNC:#x}
.equ DISPLAY, {DISPLAY:#x}
.equ FRAME, {FRAME_AT:#x}
.equ TICKS, {TICKS:#x}
.equ MENU_STATE, {MENU_STATE:#x}
.equ OFF_ACTIVE, {OFF_ACTIVE:#x}
.equ M_INV, {M_INV:#x}
.equ SLICE, {SLICE_MS}
.equ SHORT, {SHORT_MS}
.equ EARLY, {EARLY_MS}
.equ SLOT, {SLOT}
.equ FADE_AT, {FADE_AT}
.equ FADE2_AT, {FADE2_AT}
.equ TUBE_AT, {TUBE_AT}
.equ LINE_AT, {LINE_AT}
.equ DOT_AT, {DOT_AT}
.equ DARK_AT, {DARK_AT}
.equ LINE_X, {64 - LINE_W // 2}
.equ LINE_W, {LINE_W}
.equ DOT_X, {64 - DOT_W // 2}
.equ DOT_W, {DOT_W}
.equ DIFF_N, {len(wave_diff())}

.org {CODE_AT:#x}

; Entered instead of the call of the wait function in the power-off handler (0xC0038A54), r0 = milliseconds.
; Returns what the wait returns. Six registers are pushed, a multiple of eight bytes as the stack is kept.
power_off_wait:
    push {{r4, r5, r6, r7, r8, lr}}
    mov r6, r0
    cmp r6, #0
    ble plain
    bl killed
    cmp r0, #0
    bne plain
    mov r0, #1
    ldr r1, =OFF_ACTIVE
    str r0, [r1]
    ldr r8, =TICKS
    ldr r8, [r8]
    add r5, r8, r6
    sub r7, r6, #EARLY
    mov r4, #0
wait_loop:
    ldr r0, =TICKS
    ldr r0, [r0]
    sub r0, r0, r8
    add r1, r7, #EARLY
    sub r1, r1, r6
    cmp r1, r0
    movgt r0, r1
    bl draw
    ldr r0, =TICKS
    ldr r0, [r0]
    sub r0, r5, r0
    cmp r0, #0
    ble wait_done
    cmp r0, r7
    movgt r1, #SHORT
    movle r1, #SLICE
    cmp r0, r1
    movgt r0, r1
    sub r6, r6, r0
    bl WAIT
    mov r4, r0
    cmp r6, #0
    bgt wait_loop
wait_done:
    mov r0, r4
    pop {{r4, r5, r6, r7, r8, pc}}
plain:
    mov r0, r6
    pop {{r4, r5, r6, r7, r8, lr}}
    b WAIT

; r0 = 1 when EXIT was held at power-on (or the panel object is not there yet)
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

; r0 = ms into the wait: the picture of that moment into the display buffer (sequence() in power_off.py)
draw:
    push {{r4, r5, r6, r7, r8, lr}}
    mov r4, r0
    ldr r5, =DISPLAY
    ldr r1, =LINE_AT
    cmp r4, r1
    bge dr_lines
; the waving picture: the frame, and the arm of the second pose in every odd slot and from the fade on
    mov r0, r5
    ldr r1, =FRAME
    mov r2, #128
dr_copy:
    ldmia r1!, {{r3, r12}}
    stmia r0!, {{r3, r12}}
    subs r2, r2, #1
    bne dr_copy
    ldr r1, =FADE_AT
    cmp r4, r1
    bge dr_arm
    mov r0, r4
    mov r1, #0
dr_slot:
    cmp r0, #SLOT
    subge r0, r0, #SLOT
    eorge r1, r1, #1
    bge dr_slot
    cmp r1, #0
    beq dr_flip
dr_arm:
    ldr r1, =diff
    mov r2, #DIFF_N
dr_arm_loop:
    ldr r3, [r1], #4
    strb r3, [r5, r3, lsr #8]
    subs r2, r2, #1
    bne dr_arm_loop
    ldr r1, =FADE_AT
    cmp r4, r1
    blt dr_flip
    ldr r1, =TUBE_AT
    cmp r4, r1
    bge dr_tube
; the fade: clear the bits under the Bayer threshold, one mask byte per x % 4
    ldr r1, =FADE2_AT
    cmp r4, r1
    ldr r6, =mask_fade
    addge r6, r6, #4                ; mask_fade2 follows
    mov r0, #0
dr_fade:
    ldrb r2, [r5, r0]
    and r3, r0, #3
    ldrb r3, [r6, r3]
    bic r2, r2, r3
    strb r2, [r5, r0]
    add r0, r0, #1
    cmp r0, #1024
    blt dr_fade
    b dr_flip
; the tube: row 4 of every page of the odd columns pressed into rows 28 to 35, the rest dark
dr_tube:
    mov r0, #0
dr_tube_col:
    mov r2, #0
    tst r0, #1
    beq dr_tube_put
    mov r1, #7
dr_tube_bit:
    add r3, r0, r1, lsl #7
    ldrb r3, [r5, r3]
    mov r3, r3, lsr #4
    and r3, r3, #1
    orr r2, r3, r2, lsl #1
    subs r1, r1, #1
    bge dr_tube_bit
dr_tube_put:
    add r12, r5, r0
    mov r3, #0
    mov r1, #0
dr_tube_clear:
    strb r3, [r12, r1]
    add r1, r1, #128
    cmp r1, #1024
    blt dr_tube_clear
    and r3, r2, #15
    mov r3, r3, lsl #4
    strb r3, [r12, #384]
    mov r3, r2, lsr #4
    strb r3, [r12, #512]
    add r0, r0, #1
    cmp r0, #128
    blt dr_tube_col
    b dr_flip
; a line, a dot, then dark: rows 31 and 32 lit over the width
dr_lines:
    mov r0, r5
    mov r1, #0
    mov r2, #0
    mov r3, #0
    mov r12, #0
    mov r6, #128
dr_clear:
    stmia r0!, {{r1, r2, r3, r12}}
    stmia r0!, {{r1, r2, r3, r12}}
    subs r6, r6, #4
    bne dr_clear
    ldr r1, =DARK_AT
    cmp r4, r1
    bge dr_flip
    ldr r1, =DOT_AT
    cmp r4, r1
    movlt r0, #LINE_X
    movlt r1, #LINE_W
    movge r0, #DOT_X
    movge r1, #DOT_W
    add r0, r5, r0
    mov r2, #0x80
    mov r3, #1
dr_line:
    strb r2, [r0, #384]
    strb r3, [r0, #512]
    add r0, r0, #1
    subs r1, r1, #1
    bne dr_line
; dark either way: complemented unless the BLECH menu is armed with DISPLAY INVERT ON
dr_flip:
    ldr r0, =MENU_STATE
    ldr r1, [r0]
    cmp r1, #1
    bne dr_not
    ldr r1, [r0, #M_INV]
    cmp r1, #0
    bne dr_out
dr_not:
    mov r0, r5
    mov r2, #256
dr_not_loop:
    ldr r3, [r0]
    mvn r3, r3
    str r3, [r0], #4
    subs r2, r2, #1
    bne dr_not_loop
dr_out:
    pop {{r4, r5, r6, r7, r8, pc}}
.align 2
mask_fade:
    .byte {", ".join(str(b) for b in fade_mask(FADE))}
mask_fade2:
    .byte {", ".join(str(b) for b in fade_mask(FADE2))}
.align 2
diff:
{diff}
.pool
"""


FIRMWARE_PLACES = ["PANEL", "WAIT_CALL", "WAIT_FUNC", "TICKS"]     # DISPLAY keeps its address in the synth (the entry says "same")


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); the code and the picture stay where they are."""
    synthaddr.use(globals(), FIRMWARE_PLACES + ["DISPLAY"], build)


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def bl_word(at, target):
    return struct.unpack("<I", struct.pack("<I", 0xEB000000 | ((target - (at + 8)) >> 2) & 0xFFFFFF))[0]


def build_patch(vsb, build="hacktribe"):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    use_build(build)
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
    frame = frame_bytes(frame_pixels())
    if FRAME_AT + len(frame) > FRAME_END:
        raise SystemExit("the picture does not fit")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    if struct.unpack("<I", was(WAIT_CALL, 4))[0] != bl_word(WAIT_CALL, WAIT_FUNC):
        raise SystemExit("the wait call of the power-off handler is not where the patch expects it in this VSB")
    hook = struct.pack("<I", bl_word(WAIT_CALL, symbols["power_off_wait"]))
    return {
        "format": "gelumpe-patch", "version": 1, "id": "power-off",
        "name": "Blechy beim Ausschalten",
        "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "power-off picture: the wait of the power-off handler draws the moment of the sequence every 2 to 10 ms"},
            {"file": file_offset(FRAME_AT), "bytes": frame.hex(), "expect": free(FRAME_AT, len(frame)),
             "note": "the power-off picture, 1024 bytes of display buffer: Blechy waving and his line"},
            {"file": file_offset(WAIT_CALL), "bytes": hook.hex(), "expect": sha(was(WAIT_CALL, 4)),
             "note": "the wait call of the power-off handler goes through the picture code"},
        ],
        "hooks": [
            {"site": f"0x{WAIT_CALL:08X}", "kind": "call", "chain": "power-off",
             "position": "replace", "swallow": False,
             "note": "does the original wait in slices of 10 and 100 ms and draws between them; with EXIT held at power-on it is the original wait"},
        ],
        "ram": [ramdecl.area(OFF_ACTIVE, 4, "1 while the sequence runs, read by the look of the loading bar", "tools/patch/power_off.py:OFF_ACTIVE")],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    p.add_argument("--png", type=Path, help="write the picture as the LCD shows it")
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    use_build(a.build)
    patch = build_patch(raw, a.build)
    if a.listing:
        at, code, symbols = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    if a.png:
        write_png(a.png, frame_pixels())
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing and not a.png:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
