"""Builds the loading animation patch (docs/ideen/41-startbild-ausbauen.md, entwuerfe/design-1.3/geraet) for firmware 2.02
with Hacktribe.

While the start loads the samples (e2sSample.all), the firmware shows a window "Loading nnn%". With this patch Blechy
draws a line instead: the line is the bar, he stands where the tip of his tube has eaten it, the percent counts up at the
bottom right, and from 95 percent the finale plays (eyes torn open, shaking). The pictures are assets/blechy/loading.bin,
made by the same renderer as the previews; the overlay puts them together (compose_reference is the same in Python).
At most one new picture every 50 ms. The start image (assets/blechy/splash.json) is seen from power-on until the load begins.

    python3 tools/patch/load_bar.py --vsb SYSTEM.VSB [--out data/patches/load-bar.json]

Four hooks:
  stat      the call that asks whether e2sSample.all exists, 0xC002AE60, in the start task right after the rescue
            paths (the panel update and the start modes never get there): remembers "a load is coming"
  progress  the call that updates the text "Loading nnn%" in the loader, 0xC00366D4: remembers where the loader is
            and, while the overlay draws, leaves the update out (nobody sees the window, and its redraws cost time)
  load      the call of the loader, 0xC0038D60: remembers that it is done
  frame     the tail call that sends the frame to the display, 0xC008370C: while a load is expected it puts the
            image over the frame before it goes out, so the window never reaches the display

The picture is drawn into the frame buffer every frame (the firmware's window would show otherwise), but only a new
picture is marked as changed, so the display gets pages only then. The firmware's own draw of a whole image takes 2.5
million instructions, which is why the overlay draws its own.

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
CODE_END = 0xC0181F00
LOAD_AT = 0xC01A3D00            # assets/blechy/loading.bin, written by the patch (free behind the start image editor's vtable)
LOAD_END = 0xC01A4A00
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



# ---- the loading animation (entwuerfe/design-1.3/geraet: Blechy draws the line from left to right) ----
# assets/blechy/loading.bin holds its pictures, written by entwuerfe/design-1.3/geraet/firmware_assets.py from the same
# renderer as the previews. Everything is in the order of the frame buffer (bit 0 the top row of a page) with a set bit lit
# on the reversed display (DISPLAY INVERT ON); the overlay complements its picture when the display is not reversed.
LOAD_ART = ART.parent / "loading.bin"
LINE_X, LINE_Y, SWEEP = 49, 54, 48      # the line: x 49 to 97 on row 54, lumps above it
SPRITE_PAGE, SPRITE_PAGES = 2, 5        # Blechy lives in pages 2 to 6 (rows 16 to 55)
FINALE_AT = 95                          # from 95 percent the finale plays while the count runs on
TICKS = 0xC06A292C              # the operating system's tick count, one per millisecond (tools/patch/power_off.py)
MENU_STATE = 0xC01D6E00         # tools/patch/script_hooks.py:MENU_STATE
TICK_MS = 64                    # the finale's pictures change every 64 ms (a power of two: no division)
TICKS_N, FRAME_MS = 8, 50               # the finale's 8 pictures; at most one new picture every 50 ms (20 per second)
PCT_RIGHT, PCT_Y = 123, 58              # the percent, right-aligned, in the 3 x 5 font
GLYPHS = "0123456789%"


def pack_loading(base, foot_done, lumps, digits, fig, fin, ticks):
    """loading.bin from its parts: base 1024, foot_done 128 (page 7), lumps 49 heights, digits 11 glyphs of 3 column bytes,
    fig (x0, width, bits, mask), fin (x0, width, bytes), ticks 8 lists of (offset in the frame buffer, byte)."""
    out = bytearray(base) + bytes(foot_done)
    out += bytes(lumps) + bytes(52 - len(lumps))
    out += bytes(b for g in digits for b in g) + bytes(36 - 3 * len(digits))
    (fx, fw, fbits, fmask), (nx, nw, nbytes) = fig, fin
    out += bytes((fx, fw, nx, nw))
    for p in range(SPRITE_PAGES):
        out += fbits[p * fw:(p + 1) * fw] + fmask[p * fw:(p + 1) * fw]
    out += nbytes
    out += bytes(-len(out) % 4)
    table_at = len(out)
    out += bytes(2 * TICKS_N)
    for i, entries in enumerate(ticks):
        struct.pack_into("<H", out, table_at + 2 * i, len(out) - table_at)
        out += struct.pack("<H", len(entries)) + bytes(2)
        for at, value in entries:
            out += struct.pack("<HBB", at, value, 0)
    return bytes(out)


def parse_loading(blob):
    fx, fw, nx, nw = blob[1240:1244]
    fig_at = 1244
    fin_at = fig_at + SPRITE_PAGES * fw * 2
    table_at = fin_at + SPRITE_PAGES * nw
    table_at += -table_at % 4
    ticks = []
    for i in range(TICKS_N):
        at = table_at + struct.unpack_from("<H", blob, table_at + 2 * i)[0]
        n = struct.unpack_from("<H", blob, at)[0]
        ticks.append([struct.unpack_from("<HB", blob, at + 4 + 4 * k) for k in range(n)])
    return {"base": blob[:1024], "foot_done": blob[1024:1152], "lumps": blob[1152:1152 + SWEEP + 1],
            "digits": [blob[1204 + 3 * g:1207 + 3 * g] for g in range(len(GLYPHS))],
            "fig_x": fx, "fig_w": fw, "fig_at": fig_at, "fin_x": nx, "fin_w": nw, "fin_at": fin_at,
            "table_at": table_at, "ticks": ticks, "blob": blob}


def loading_key(pct, done, tick):
    """What the overlay draws: the percent, done, and the finale's picture (0 before the finale)."""
    finale = done or pct >= FINALE_AT
    return (100 if done else pct) | (1 << 8 if done else 0) | ((tick % TICKS_N if finale else 0) << 16)


def compose_reference(art, key):
    """The frame buffer the overlay draws for `key`, as the firmware composes it (before the complement)."""
    pct, done, tick = key & 0xFF, key >> 8 & 1, key >> 16 & 0xFF
    fb = bytearray(art["base"])
    if done:
        fb[896:1024] = art["foot_done"]

    def put(x, y):
        fb[(y >> 3) * 128 + x] |= 1 << (y & 7)
    if not (done or pct >= FINALE_AT):
        shift = (pct * SWEEP + 50) // 100
        for x in range(LINE_X + shift, LINE_X + SWEEP + 1):
            for k in range(art["lumps"][x - LINE_X] + 1):
                put(x, LINE_Y - k)
        blob, fw = art["blob"], art["fig_w"]
        for p in range(SPRITE_PAGES):
            row = art["fig_at"] + p * fw * 2
            for c in range(fw):
                i = (SPRITE_PAGE + p) * 128 + art["fig_x"] + shift + c
                fb[i] = (fb[i] & ~blob[row + fw + c] & 0xFF) | blob[row + c]
    else:
        blob, nw = art["blob"], art["fin_w"]
        for p in range(SPRITE_PAGES):
            i = (SPRITE_PAGE + p) * 128 + art["fin_x"]
            fb[i:i + nw] = blob[art["fin_at"] + p * nw:art["fin_at"] + (p + 1) * nw]
        for at, value in art["ticks"][tick]:
            fb[at] = value
    text = f"{pct}%"
    x = PCT_RIGHT - (4 * len(text) - 1) + 1
    for ch in text:
        for c, col in enumerate(art["digits"][GLYPHS.index(ch)]):
            for r in range(5):
                if col >> r & 1:
                    put(x + c, PCT_Y + r)
        x += 4
    return bytes(fb)


def sha(data):
    return hashlib.sha256(data).hexdigest()


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
.equ STATE, @STATE@
.equ FRAME_CAP, @CAP@
.equ S_EXPECT, 0               ; 1 while a load is expected and the overlay draws, 2 when it is over, FFFFFFFF never started
.equ S_CUR, 4                  ; the loader's file offset
.equ S_MAX, 8                  ; the largest offset in the file
.equ S_DONE, 12                ; 1 when the loader has returned
.equ S_FRAME, 16               ; frames drawn
.equ S_MODE, 20                ; 1: the BLECH image (kept for the readers of the state; there is no other any more)
.equ S_DRAWN, 24               ; 1 once the whole frame buffer has been marked as changed
.equ S_KEY, 28                 ; the picture drawn: percent | done << 8 | the finale's picture << 16
.equ S_LAST, 32                ; TICKS when that key was taken
.equ TICKS, @TICKS@             ; the operating system's tick count, one per millisecond
.equ MENU_STATE, @MENU_STATE@   ; the BLECH menu (script runtime): M_ON 1 when armed, M_INV 1 with DISPLAY INVERT ON
.equ M_ON, 0
.equ M_INV, 0x1B8
.equ ART, @ART@
.equ ART_FOOT, @ART_FOOT@
.equ ART_LUMPS, @ART_LUMPS@
.equ ART_DIGITS, @ART_DIGITS@
.equ ART_FIG, @ART_FIG@
.equ ART_FIN, @ART_FIN@
.equ ART_TICKS, @ART_TICKS@
.equ FIG_X, @FIG_X@
.equ FIG_W, @FIG_W@
.equ FIG_W2, @FIG_W2@
.equ FIN_X, @FIN_X@
.equ FIN_W, @FIN_W@
.equ SPRITE_OFF, @SPRITE_OFF@
.equ SPRITE_PAGES, @SPRITE_PAGES@
.equ LINE_X, @LINE_X@
.equ LINE_END, @LINE_END@
.equ LINE_Y, @LINE_Y@
.equ SWEEP, @SWEEP@
.equ FINALE_AT, @FINALE_AT@
.equ TICKS_MASK, @TICKS_MASK@
.equ TICK_SHIFT, @TICK_SHIFT@
.equ FRAME_MS, @FRAME_MS@
.equ PCT_X0, @PCT_X0@
.equ PCT_Y, @PCT_Y@

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
    str r2, [r1, #S_KEY]
    str r2, [r1, #S_LAST]
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

; r0 = the percent: 100 when the loader is done, else the loader's share of the file, at most 99.
pct_now:
    push {r4, lr}
    ldr r4, =STATE
    mov r2, #100
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
    cmp r0, #99
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

; Picks the picture and draws it. The key (percent, done, the finale's picture) changes at most every FRAME_MS; until then
; the last one is drawn again, every frame, over whatever the firmware put into the buffer. Only a new key is marked as changed.
compose:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    ldr r4, =STATE
    ldr r7, =VRAM
    bl pct_now
    mov r5, r0                   ; percent
    ldr r6, [r4, #S_DONE]
    cmp r6, #1
    movne r6, #0
    ldr r0, =TICKS
    ldr r8, [r0]                 ; now, ms
    mov r9, #0                   ; the finale's picture
    cmp r6, #1
    cmpne r5, #FINALE_AT
    blo cp_key
    mov r0, r8, lsr #TICK_SHIFT  ; a new finale picture every 64 ms
    and r9, r0, #TICKS_MASK
cp_key:
    orr r10, r5, r6, lsl #8
    orr r10, r10, r9, lsl #16
    ldr r0, [r4, #S_DRAWN]
    cmp r0, #0
    beq cp_take
    ldr r0, [r4, #S_KEY]
    cmp r0, r10
    beq cp_same
    ldr r1, [r4, #S_LAST]
    sub r1, r8, r1
    cmp r1, #FRAME_MS
    bhs cp_take
cp_same:
    ldr r10, [r4, #S_KEY]
    mov r0, r10
    bl draw_key
    b cp_done
cp_take:
    str r10, [r4, #S_KEY]
    str r8, [r4, #S_LAST]
    mov r0, r10
    bl draw_key
    ldr r0, [r4, #S_DRAWN]
    cmp r0, #0
    mov r0, #1
    str r0, [r4, #S_DRAWN]
    mov r0, #0
    moveq r1, #0                 ; the first picture: all of it
    movne r1, #16                ; then rows 16 to 63, the wordmark never changes
    mov r2, #128
    mov r3, #64
    bl MARK
cp_done:
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; r0 = key: the picture into the frame buffer (VRAM), complemented when the display is not reversed.
draw_key:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    and r4, r0, #0xFF            ; percent
    mov r5, r0, lsr #8
    and r5, r5, #1               ; done
    mov r6, r0, lsr #16          ; the finale's picture
    ldr r7, =VRAM
    ldr r1, =ART
    mov r0, r7
    mov r2, #1024
dk_base:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne dk_base
    cmp r5, #0
    beq dk_foot
    ldr r1, =ART_FOOT
    add r0, r7, #896
    mov r2, #128
dk_done:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne dk_done
dk_foot:
    cmp r5, #0
    cmpeq r4, #FINALE_AT
    bhs dk_finale
; the line from the tip of the tube to its end, then Blechy over it
    mov r0, #SWEEP
    mul r1, r4, r0
    add r1, r1, #50
    ldr r0, =1311                ; / 100: exact for these values (at most 94 * 48 + 50)
    mul r2, r1, r0
    mov r8, r2, lsr #17          ; shift
    add r9, r8, #LINE_X          ; x
dk_line:
    cmp r9, #LINE_END
    bhi dk_fig
    ldr r0, =ART_LUMPS
    sub r1, r9, #LINE_X
    ldrb r10, [r0, r1]
    mov r11, #LINE_Y
dk_lump:
    mov r0, r7
    mov r1, r9
    mov r2, r11
    mov r3, #1
    bl set_px
    sub r11, r11, #1
    subs r10, r10, #1
    bpl dk_lump
    add r9, r9, #1
    b dk_line
dk_fig:
    ldr r10, =ART_FIG
    add r11, r7, #SPRITE_OFF
    add r11, r11, #FIG_X
    add r11, r11, r8
    mov r9, #SPRITE_PAGES
dk_fig_page:
    mov r8, #0
dk_fig_col:
    ldrb r0, [r11, r8]
    add r1, r10, #FIG_W
    ldrb r1, [r1, r8]
    bic r0, r0, r1
    ldrb r1, [r10, r8]
    orr r0, r0, r1
    strb r0, [r11, r8]
    add r8, r8, #1
    cmp r8, #FIG_W
    blo dk_fig_col
    add r10, r10, #FIG_W2
    add r11, r11, #128
    subs r9, r9, #1
    bne dk_fig_page
    b dk_pct
; the finale: its first picture, then the bytes that differ in this one
dk_finale:
    ldr r10, =ART_FIN
    add r11, r7, #SPRITE_OFF
    add r11, r11, #FIN_X
    mov r9, #SPRITE_PAGES
dk_fin_page:
    mov r8, #0
dk_fin_col:
    ldrb r0, [r10, r8]
    strb r0, [r11, r8]
    add r8, r8, #1
    cmp r8, #FIN_W
    blo dk_fin_col
    add r10, r10, #FIN_W
    add r11, r11, #128
    subs r9, r9, #1
    bne dk_fin_page
    ldr r10, =ART_TICKS          ; halfwords as two bytes: the assembler has no ldrh
    add r1, r10, r6, lsl #1
    ldrb r0, [r1]
    ldrb r2, [r1, #1]
    orr r0, r0, r2, lsl #8
    add r10, r10, r0
    ldrb r9, [r10]
    ldrb r2, [r10, #1]
    orr r9, r9, r2, lsl #8
    add r10, r10, #4
dk_tick:
    subs r9, r9, #1
    bmi dk_pct
    ldrb r0, [r10]
    ldrb r2, [r10, #1]
    orr r0, r0, r2, lsl #8
    ldrb r1, [r10, #2]
    strb r1, [r7, r0]
    add r10, r10, #4
    b dk_tick
; the percent, right-aligned at PCT_RIGHT: one to three digits and %
dk_pct:
    mov r8, #1
    cmp r4, #10
    movhs r8, #2
    cmp r4, #100
    movhs r8, #3                 ; r8 = digits
    add r0, r8, #1
    mov r0, r0, lsl #2
    rsb r9, r0, #PCT_X0          ; x of the first: PCT_RIGHT + 1 - (4 * (digits + 1) - 1)
    mov r10, #100
    cmp r8, #3
    movlo r10, #10
    cmp r8, #2
    movlo r10, #1                ; r10 = place value of the first digit
dk_digit:
    mov r0, #0
dk_div:
    cmp r4, r10
    blo dk_got
    sub r4, r4, r10
    add r0, r0, #1
    b dk_div
dk_got:
    bl glyph
    add r9, r9, #4
    cmp r10, #1
    beq dk_percent
    cmp r10, #100
    moveq r10, #10
    movne r10, #1
    b dk_digit
dk_percent:
    mov r0, #10
    bl glyph
; complemented unless the BLECH menu is armed with DISPLAY INVERT ON (then the controller shows set bits light)
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_ON]
    cmp r1, #1
    bne dk_flip
    ldr r1, [r0, #M_INV]
    cmp r1, #0
    bne dk_out
dk_flip:
    mov r0, r7
    mov r2, #1024
dk_flip_loop:
    ldr r3, [r0]
    mvn r3, r3
    str r3, [r0], #4
    subs r2, r2, #4
    bne dk_flip_loop
dk_out:
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}

; r0 = glyph (0 to 9, 10 is %), r9 = x, r7 = VRAM: three columns of five rows at PCT_Y. Keeps r4 to r11.
glyph:
    push {r4, r5, r6, r8, lr}
    ldr r1, =ART_DIGITS
    add r0, r0, r0, lsl #1
    add r4, r1, r0
    mov r5, #0
gl_col:
    ldrb r6, [r4, r5]
    mov r8, #0
gl_row:
    tst r6, #1
    beq gl_next
    mov r0, r7
    add r1, r9, r5
    add r2, r8, #PCT_Y
    mov r3, #1
    bl set_px
gl_next:
    mov r6, r6, lsr #1
    add r8, r8, #1
    cmp r8, #5
    blo gl_row
    add r5, r5, #1
    cmp r5, #3
    blo gl_col
    pop {r4, r5, r6, r8, pc}

.align 4
lit_pool:
.pool
"""


def art():
    data = LOAD_ART.read_bytes()
    if len(data) > LOAD_END - LOAD_AT:
        raise SystemExit(f"{LOAD_ART} has {len(data)} bytes, room for {LOAD_END - LOAD_AT}")
    return data


def source():
    a = parse_loading(art())
    text = SOURCE
    for key, value in {
        "STAT_FUNC": f"{STAT_FUNC:#x}", "LOAD_FUNC": f"{LOAD_FUNC:#x}", "PROGRESS_FUNC": f"{PROGRESS_FUNC:#x}", "FLUSH_FUNC": f"{FLUSH_FUNC:#x}",
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CAP": str(FRAME_CAP), "RETRIES": str(RETRIES), "RETRY_MS": str(RETRY_MS),
        "CODE_AT": f"{CODE_AT:#x}", "TICKS": f"{TICKS:#x}", "MENU_STATE": f"{MENU_STATE:#x}",
        "ART": f"{LOAD_AT:#x}", "ART_FOOT": f"{LOAD_AT + 1024:#x}", "ART_LUMPS": f"{LOAD_AT + 1152:#x}",
        "ART_DIGITS": f"{LOAD_AT + 1204:#x}", "ART_FIG": f"{LOAD_AT + a['fig_at']:#x}", "ART_FIN": f"{LOAD_AT + a['fin_at']:#x}",
        "ART_TICKS": f"{LOAD_AT + a['table_at']:#x}", "FIG_X": str(a["fig_x"]), "FIG_W": str(a["fig_w"]), "FIG_W2": str(2 * a["fig_w"]),
        "FIN_X": str(a["fin_x"]), "FIN_W": str(a["fin_w"]), "SPRITE_OFF": str(SPRITE_PAGE * 128), "SPRITE_PAGES": str(SPRITE_PAGES),
        "LINE_X": str(LINE_X), "LINE_END": str(LINE_X + SWEEP), "LINE_Y": str(LINE_Y), "SWEEP": str(SWEEP),
        "FINALE_AT": str(FINALE_AT), "TICKS_MASK": str(TICKS_N - 1), "TICK_SHIFT": str(TICK_MS.bit_length() - 1), "FRAME_MS": str(FRAME_MS),
        "PCT_X0": str(PCT_RIGHT + 2), "PCT_Y": str(PCT_Y),
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
            {"file": file_offset(LOAD_AT), "bytes": art().hex(), "expect": free(LOAD_AT, len(art())),
             "note": "the pictures of the loading animation (assets/blechy/loading.bin)"},
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
        "shares": [
            ramdecl.share(MENU_STATE, 4, "script-runtime", "read only: is the BLECH menu armed (M_ON)", "tools/patch/load_bar.py:MENU_STATE"),
            ramdecl.share(MENU_STATE + 0x1B8, 4, "script-runtime", "read only: DISPLAY INVERT (M_INV)", "tools/patch/load_bar.py:MENU_STATE"),
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
        print(f"section {at:#x} + {len(code):#x} bytes, pictures {LOAD_AT:#x}, state {STATE:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
