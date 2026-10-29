"""Builds the loading animation patch (docs/ideen/41-startbild-ausbauen.md, tools/art/loading) for firmware 2.02
with Hacktribe.

While the start loads the samples (e2sSample.all), the firmware shows a window "Loading nnn%". With this patch Blechy
draws a line instead: the line is the bar, he stands where the tip of his tube has eaten it, the percent counts up at the
bottom right, and from 95 percent the finale plays (eyes torn open, shaking). The pictures are a loading animation file
(docs/hintergrund/ladeanimation.md): a custom one the app writes into ANIM_SLOT when it passes the checks, else the default
assets/blechy/loading.blla, made from the parts in assets/blechy/loading.bin by the renderer of the previews
(compose_reference is the same in Python). The picture follows the bytes the loader has read of e2sSample.all, smoothed
within a read. At most one new picture every 50 ms. The start image (assets/blechy/splash.json) is seen from power-on
until the load begins.

    python3 tools/patch/load_bar.py --vsb SYSTEM.VSB [--out data/patches/load-bar.json]

Five hooks:
  stat      the call that asks whether e2sSample.all exists, 0xC002AE60, in the start task right after the rescue
            paths (the panel update and the start modes never get there): remembers "a load is coming"
  progress  the call that updates the text "Loading nnn%" in the loader, 0xC00366D4: remembers where the loader is
            and, while the overlay draws, leaves the update out (nobody sees the window, and its redraws cost time)
  read      the two calls of f_read in the sample parser's PCM loop, 0xC00362FC and 0xC003635C: count the bytes read
  load      the call of the loader, 0xC0038D60: remembers that it is done
  frame     the tail call that sends the frame to the display, 0xC008370C: while a load is expected it puts the
            image over the frame before it goes out, so the window never reaches the display

The picture is drawn into the frame buffer every frame (the firmware's window would show otherwise), but only a new
picture is marked as changed, so the display gets pages only then. The firmware's own draw of a whole image takes 2.5
million instructions, which is why the overlay draws its own.

With EXIT held at power-on, without a card or without e2sSample.all nothing is ever expected and every hook goes
straight to the original. A card that is in the slot but not mounted after the start's question is asked again, up to
RETRIES times, RETRY_MS apart (device 18.10.: a card that answered late left the start without samples or hanging). When the
loader ends with a code (a card error), the image stays with the percent where it stopped. The overlay ends when the main screen comes (or after a cap of frames).
While the firmware's error box says "No Card." or "Card Error" (its code at ERR_CODE), the display send shows Blechy's card
picture for that code instead of the box, until the box goes (EXIT).
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
import loading_anim  # noqa: E402
import ramdecl  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000
ART = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2]) / "assets" / "blechy" / "splash.bin"   # frozen: unpacked next to the code

CODE_AT = 0xC0181000            # free (FF) in the image, behind the pattern switch
CODE_END = 0xC0181F00
LOAD_AT = 0xC01A3D00            # the card pictures, written by the patch (free behind the start image editor's vtable)
LOAD_END = 0xC01A4A00
# The first code area of the plugin runtime until 1.3.7 (tools/patch/script_hooks.py:CODE_START), a reserve since; free (FF)
# in all three images. The loading animation lives here.
ANIM_SLOT = 0xC01A6000          # a custom loading animation, written by the app; FF without one
ANIM_SLOT_END = 0xC01AA000      # MAX_BYTES of tools/patch/loading_anim.py
ANIM_DEFAULT = 0xC01AA000       # assets/blechy/loading.blla, written by the patch: shown when the slot holds no good file
ANIM_DEFAULT_END = 0xC01AC000
ANIM_CODE = 0xC01AC000          # the code that plays it and counts the loader's reads
ANIM_CODE_END = 0xC01AC800
ANIM_VARS = 0xC01AC800          # its run time state, in RAM only
ANIM_VARS_END = 0xC01AC840
ANIM_BUF = 0xC01ACC00           # the progress picture on screen, in RAM only
ANIM_BUF_END = 0xC01AD000
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
READ_CALLS = (0xC00362FC, 0xC003635C)   # bl 0xC009DD74 in the sample parser's PCM loop (16 and 24 bit): r0 the file, r2 the bytes
READ_FUNC = 0xC009DD74          # FatFs f_read (file, buffer, bytes, &read); the file's position at +8, its size at +12
UDIV = 0xC00021FC               # the firmware's unsigned division: r0 = r0 / r1
UDIV_WORD = 0xE2512001          # its first instruction, subs r2, r1, #1
UDIVMOD = 0xC00022F0            # the same with the remainder in r1
UDIVMOD_WORD = 0xE3510000       # cmp r1, #0



# ---- the loading animation (tools/art/loading: Blechy draws the line from left to right) ----
# assets/blechy/loading.bin holds its pictures, written by tools/art/loading/firmware_assets.py from the same
# renderer as the previews. Everything is in the order of the frame buffer (bit 0 the top row of a page) with a set bit lit
# on the reversed display (DISPLAY INVERT ON); the overlay complements its picture when the display is not reversed.
LOAD_ART = ART.parent / "loading.bin"
LOAD_ANIM = ART.parent / "loading.blla"
LINE_X, LINE_Y, SWEEP = 49, 54, 48      # the line: x 49 to 97 on row 54, lumps above it
SPRITE_PAGE, SPRITE_PAGES = 2, 5        # Blechy lives in pages 2 to 6 (rows 16 to 55)
FINALE_AT = 95                          # from 95 percent the finale plays while the count runs on
TICKS = 0xC06A292C              # the operating system's tick count, one per millisecond (tools/patch/power_off.py)
MENU_STATE = 0xC01D6E00         # tools/patch/script_hooks.py:MENU_STATE
TICK_MS = 96                    # the loop's pictures change every 96 ms; 64 ms was too fast for the LCD, Blechy's eyes only flickered
TICKS_N, FRAME_MS = 8, 50               # the finale's 8 pictures; at most one new picture every 50 ms (20 per second)
STALL_MS = 500                  # an animation that loops while waiting starts its loop when the progress stood this long
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


# ---- the look (restyle_reference below): the firmware's screens restyled like the start image ----
# Every frame of the user interface goes out through the flush hook. With DISPLAY INVERT ON the hook copies the frame,
# draws the look over it, lets the firmware send it (the firmware compares each page with its own copy of what the
# display shows and sends only the changed ones, from that copy) and puts the frame back, so the firmware keeps drawing
# into its own pixels. The rules, in this order:
#   tab     the inverted page tab at the top left gets a stamped corner at the bottom right
#   box     an outline box gets cut corners and a dithered shadow down and right; a filled box (the main screen's
#           pattern name) becomes an outline box one pixel taller at both ends, so the screen stays dark
#   rim     a dithered rim, dense at the lit glass and fading inward, on the bottom, left and right only along clear
#           stretches of 16 pixels and more; the right one also runs up beside the symbols of the header
LOOK_CODE = 0xC0183900          # the rest of the look's code, free (FF) behind the sample errors' state
LOOK_CODE_END = 0xC0184000
LOOK_BACK = 0xC018C400          # the frame as the firmware drew it (RAM only, behind the code of the resting IFX)
LOOK_OUT = 0xC018C800           # the frame with the look, the display send takes its pages from here
LOOK_VARS = 0xC018CC00          # the tab, the box count, where the send takes its pages from
LOOK_BOXES = 0xC018CC40         # the boxes found, LOOK_BOX bytes each
LOOK_BOX, LOOK_NBOX = 48, 12    # least-code: at most 12 boxes a frame, the firmware's screens have 3; more are left plain
LOOK_END = LOOK_BOXES + LOOK_BOX * LOOK_NBOX
PAGE_CALL = 0xC0016084          # bl 0xC0015AB4 in the display send: compares a page with what the display shows
PAGE_FUNC = 0xC0015AB4
SHADOW = 0xC031B710             # the firmware's copy of what the display shows (the literal of 0xC0015A60)
APP_PICTURE = 0xC01D6704        # the open app's picture (script runtime RT_DISPLAY): a frame equal to it is the app's own
OFF_ACTIVE = 0xC01A5BF0         # 1 while Blechy says goodbye at power off (tools/patch/power_off.py:OFF_ACTIVE)
ERR_CODE = 0xC00F9CC8          # the code of the firmware's error box (0xC0063068 sets it, its destructor puts 0x26 back)
ERR_CODE_LIT = 0xC00631D4       # the literal of the error box that holds ERR_CODE
CARD_CODES = (2, 4)             # "No Card." and "Card Error" (the box's text table 0xC00E3280, code - 1)
CARD_SPRITE = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2]) / "assets" / "blechy" / "sprites" / "blechy-terror-1.png"
CARD_TEXTS = {2: (["Keine", "karte", "drin", "Diggi."], 10), 4: (["Karte", "kaputt", ":("], 16)}   # (lines, top row) per code
EDITOR_MODE = 0xC0182004        # the start image editor's S_MODE, 1 while it is open (tools/patch/splash_editor.py)
DITHER = (0, 2, 3, 1)           # 2 x 2 ordered dither: a pixel is lit when its level is above the threshold of its place
W, H = 128, 64
VRAM_ADDR = 0xC031B310         # the firmware's frame buffer


def dither(x, y, level):
    return level > DITHER[(y & 1) * 2 + (x & 1)]


def restyle_reference(fb):
    """The look over a frame buffer (1024 bytes, set bits lit on the reversed display), as the hook draws it."""
    px = [[(fb[(y >> 3) * W + x] >> (y & 7)) & 1 for x in range(W)] for y in range(H)]
    out = [row[:] for row in px]
    covered = [[0] * W for _ in range(H)]

    tab = None
    for top in range(3):
        n = 0
        while n < W and px[top][n]:
            n += 1
        if 30 <= n <= 100:
            end = n - 1
            full = [y for y in range(top + 6, min(H, top + 13)) if all(px[y][x] for x in range(end + 1))]
            if full:
                tab = (top, full[-1], end)
                break
    if tab:
        top, bottom, end = tab
        for x, y in ((end - 1, bottom), (end, bottom), (end, bottom - 1)):     # the stamped corner
            out[y][x] = 0
        for y in range(bottom + 2):                                          # the header row keeps no rim
            covered[y] = [1] * W

    boxes = []
    for y0 in range(H):
        x = 0
        while x < W:
            if not px[y0][x]:
                x += 1
                continue
            x0 = x
            while x < W and px[y0][x]:
                x += 1
            x1 = x - 1
            if x1 - x0 < 23 or (y0 and px[y0 - 1][x0] and px[y0 - 1][x1]):
                continue                                                     # too short, or not the top line
            last = None
            for y1 in range(y0 + 1, H):
                if not (px[y1][x0] and px[y1][x1]):
                    break
                if all(px[y1][x0:x1 + 1]):
                    last = y1
            if last is not None and last - y0 >= 6 and len(boxes) < LOOK_NBOX:
                inside = sum(px[y][x0 + 1:x1].count(1) for y in range(y0 + 1, last))
                boxes.append((x0, y0, x1, last, 2 * inside > (last - y0 - 1) * (x1 - x0 - 1)))
    boxes = [b for i, b in enumerate(boxes)
             if not any(j != i and o[0] <= b[0] and o[1] <= b[1] and o[2] >= b[2] and o[3] >= b[3] for j, o in enumerate(boxes))]

    done = []
    for x0, y0, x1, y1, plate in boxes:
        if tab and y0 <= tab[1]:
            continue                                                         # the tab itself
        if any(not (x1 < a or x0 > c or y1 < b or y0 > d) for a, b, c, d in done):
            continue                                                         # a run inside a box already handled
        done.append((x0, y0, x1, y1))
        if plate:                                                            # inverted, the edge one pixel further out
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    out[y][x] = 1 - px[y][x]
            y0, y1 = max(0, y0 - 1), min(H - 1, y1 + 1)
            for x in range(x0, x1 + 1):
                out[y0][x] = out[y1][x] = 1
            for y in range(y0, y1 + 1):
                out[y][x0] = out[y][x1] = 1
        for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            out[cy][cx] = 0                                                  # cut corners
            out[cy + dy][cx + dx] = 1
        for x in range(x0 + 2, min(W, x1 + 3)):                              # shadow below
            for y in (y1 + 1, y1 + 2):
                if y < H:
                    out[y][x] = int(dither(x, y, 2 if y == y1 + 1 else 1))
        for y in range(y0 + 2, min(H, y1 + 3)):                              # shadow right
            for x in (x1 + 1, x1 + 2):
                if x < W:
                    out[y][x] = int(dither(x, y, 2 if x == x1 + 1 else 1))
        for y in range(max(0, y0 - 1), min(H, y1 + 3)):
            for x in range(max(0, x0 - 1), min(W, x1 + 3)):
                covered[y][x] = 1

    for y in range(0, (tab[1] if tab else 9) + 2):                           # the right rim beside the header's symbols
        last = max([x for x in range(W) if px[y][x]], default=-9)
        for x in range(W - 3, W):
            if x > last + 1:
                out[y][x] = int(dither(x, y, x - (W - 4)))

    def free(x, y):
        if covered[y][x]:
            return False
        return not any(px[yy][xx] for yy in range(max(0, y - 2), min(H, y + 3)) for xx in range(max(0, x - 2), min(W, x + 3)))

    cells = {"bottom": lambda t, d: (t, H - 1 - d), "left": lambda t, d: (d, t), "right": lambda t, d: (W - 1 - d, t)}
    for side, n in (("bottom", W), ("left", H), ("right", H)):              # the top edge is the header, it stays plain
        cell = cells[side]
        ok = [all(free(*cell(t, d)) for d in range(3)) for t in range(n)] + [False]
        start = None
        for t in range(n + 1):
            if ok[t] and start is None:
                start = t
            elif not ok[t] and start is not None:
                if t - start >= 16:
                    for u in range(start, t):
                        for d in range(3):
                            x, y = cell(u, d)
                            if min(x, y, W - 1 - x, H - 1 - y) == d:
                                out[y][x] = int(dither(x, y, 3 - d))
                start = None

    res = bytearray(1024)
    for y in range(H):
        for x in range(W):
            if out[y][x]:
                res[(y >> 3) * W + x] |= 1 << (y & 7)
    return bytes(res)


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
.equ S_CUR, 4                  ; the loader's file offset: where the sample it is about to load begins
.equ S_MAX, 8                  ; the size of the file
.equ S_DONE, 12                ; 1 when the loader has returned without an error
.equ S_FRAME, 16               ; frames drawn
.equ S_MODE, 20                ; 1: the BLECH image (kept for the readers of the state; there is no other any more)
.equ S_DRAWN, 24               ; 1 once the whole frame buffer has been marked as changed
.equ S_KEY, 28                 ; the picture drawn: the progress picture | the loop's picture + 1 << 16 (0 no loop) | done << 24
.equ S_LAST, 32                ; TICKS when that key was taken
.equ S_PWR, 36                 ; TICKS when the power key was first seen held while the samples load (bit 0 set), 0 not held
.equ GPIO_IN67, 0x01E26098      ; GPIO IN_DATA67; bit 31 (GPIO 7.15) is low while the power key is held
.equ GPIO_BASE, 0x01E26000
.equ GPIO_WRITE, 0xC0016BB4     ; (base, 0, 3, mask): clears the pins in mask; 0x08000000 is GPIO 7.11, the power hold
.equ POWER_HOLD, 0x08000000
.equ POWER_MS, 7000             ; as the firmware: 2 s until the panel reports the key, then 5 s more (script_hooks.s, Doom)
.equ TICKS, @TICKS@             ; the operating system's tick count, one per millisecond
.equ MENU_STATE, @MENU_STATE@   ; the BLECH menu (script runtime): M_ON 1 when armed, M_INV 1 with DISPLAY INVERT ON
.equ M_ON, 0
.equ M_INV, 0x1B8
.equ FRAME_MS, @FRAME_MS@
.equ SLOT, @SLOT@               ; a custom loading animation (docs/hintergrund/ladeanimation.md), FF without one
.equ DEFAULT, @DEFAULT@         ; assets/blechy/loading.blla
.equ MAX_BYTES, @MAX_BYTES@
.equ MAGIC, 0x414C4C42         ; "BLLA"
.equ HEAD_FRAME, 1040          ; the header and picture 0: the list table starts here or later
.equ PBUF, @PBUF@               ; the progress picture on screen, 1024 bytes
.equ VARS, @VARS@
.equ LOOP_MS, @LOOP_MS@         ; a new loop picture every LOOP_MS
.equ STALL_MS, @STALL_MS@
.equ F_READ, @F_READ@
.equ UDIV, @UDIV@               ; r0 = r0 / r1
.equ UDIVMOD, @UDIVMOD@         ; r1 = r0 % r1
.equ A_FILE, 0                 ; the animation shown: SLOT when it passed the checks, else DEFAULT
.equ A_N, 4                    ; its progress pictures
.equ A_M, 8                    ; its loop pictures
.equ A_TABLE, 12               ; where its list table is
.equ A_FROM, 16                ; the percent its loop plays from, 0 while the progress stands
.equ A_SHOWN, 20               ; the progress picture in PBUF
.equ R_POS, 24                 ; bytes of the file read so far
.equ R_NEXT, 28                ; where the read under way ends (R_POS when none is)
.equ R_T, 32                   ; TICKS when it began
.equ R_BYTES, 36               ; bytes read in the PCM loop, all reads of this load
.equ R_MS, 40                  ; TICKS they took
.equ P_SHOWN, 44               ; the progress shown, permille
.equ P_T, 48                   ; TICKS when it last went up
.equ LOOK_BACK, @LOOK_BACK@
.equ LOOK_OUT, @LOOK_OUT@
.equ SHADOW, @SHADOW@          ; the firmware's copy of what the display shows, 8 pages of 128 bytes
.equ LOOK_VARS, @LOOK_VARS@
.equ LOOK_BOXES, @LOOK_BOXES@
.equ LOOK_BOX, @LOOK_BOX@
.equ LOOK_NBOX, @LOOK_NBOX@
.equ APP_PICTURE, @APP_PICTURE@
.equ OFF_ACTIVE, @OFF_ACTIVE@
.equ EDITOR_MODE, @EDITOR_MODE@
.equ ERR_CODE, @ERR_CODE@
.equ CARD_ART, @CARD_ART@        ; the card picture of code 2, run-length coded: (count, byte) pairs up to 1024 bytes
.equ CARD_ART4, @CARD_ART4@      ; the one of code 4, right behind it
.equ DITHER_WORD, @DITHER_WORD@  ; the thresholds of DITHER, one per byte
.equ V_TAB, 0                  ; 1 when the page tab was found
.equ V_BOT, 4                  ; its last row
.equ V_END, 8                  ; its last column
.equ V_N, 12                   ; boxes found
.equ V_SRC, 16                 ; where the send takes its pages from this time: LOOK_OUT, else the frame buffer
.equ B_X0, 0
.equ B_Y0, 4
.equ B_X1, 8
.equ B_Y1, 12
.equ B_PLATE, 16               ; 1 when more than half of the inside is lit
.equ B_ALIVE, 20               ; 0 when another box holds it
.equ B_DONE, 24                ; 1 when drawn; then B_CX0 to B_CY1 is where no rim goes
.equ B_CX0, 28
.equ B_CY0, 32
.equ B_CX1, 36
.equ B_CY1, 40

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
    bl anim_start
    ldr r1, =STATE
    mov r2, #0
    str r2, [r1, #S_CUR]
    str r2, [r1, #S_MAX]
    str r2, [r1, #S_DONE]
    str r2, [r1, #S_FRAME]
    str r2, [r1, #S_DRAWN]
    str r2, [r1, #S_KEY]
    str r2, [r1, #S_LAST]
    str r2, [r1, #S_PWR]
    mov r2, #1
    str r2, [r1, #S_MODE]
    str r2, [r1, #S_EXPECT]
ls_out:
    mov r0, r4
    pop {r4, r5, r6, pc}

; ===================================================== loader
; Replaces the loader's call of the text update (r0, r1 are its arguments): the loader's file offset is in r4; its file
; object is at sp + 0x1C, the size of the file 12 bytes into it (r7 is only the largest offset in the loader's table, so the
; whole last sample would have shown 100 percent). While the overlay draws, the update is left out: the window it would
; redraw is never seen.
lb_progress:
    ldr r12, =STATE
    str r4, [r12, #S_CUR]
    ldr r2, [sp, #0x28]
    str r2, [r12, #S_MAX]
    ldr r12, [r12, #S_EXPECT]
    cmp r12, #1
    moveq r0, #1
    bxeq lr
    ldr r12, =SETTEXT
    bx r12

; Replaces the call of the loader: remembers that it is done. When the loader ends with a code (a card error, a sample it
; could not load), the image stays with its percent until the main screen comes; the firmware's box then says what happened
; (device 18.10.: "Card error" stayed behind the image, which drew on past the main screen), for no card or a broken card
; as Blechy's card picture.
lb_load:
    push {r4, lr}
    bl LOADER
    cmp r0, #0
    ldreq r1, =STATE
    moveq r2, #1
    streq r2, [r1, #S_DONE]
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
; ===================================================== the look
; Replaces the call of the page compare in the display send (0xC0016084, the 40 ms send task, every page 0 to 7 in turn;
; r0 points at the page number, r1 is 1 to send it anyway). The firmware's function compares the page of its frame buffer
; with its copy of what the display shows, copies it over and says whether it changed; the send then goes out from the
; copy. Here it is the same, but from LOOK_OUT when the look is wanted: at page 0 the look is drawn there from the frame.
; The firmware's frame buffer is never written.
lb_page:
    push {r4, r5, r6, lr}
    ldr r4, [r0]
    mov r5, r1
    ldr r6, =LOOK_VARS
    cmp r4, #0
    bne lp_have
    bl card_wanted
    cmp r0, #0
    bne lp_src
    bl look_wanted
    cmp r0, #0
    moveq r0, #0
    beq lp_src
    ldr r0, [r6, #V_SRC]          ; the frame unchanged since the look was drawn: it stands
    ldr r1, =LOOK_OUT
    cmp r0, r1
    bne lp_draw
    ldr r0, =LOOK_BACK
    mov r1, #0
    mov r2, #1024
    bl same
    cmp r0, #0
    ldrne r0, =LOOK_OUT
    bne lp_src
lp_draw:
    bl restyle
    ldr r0, =LOOK_OUT
lp_src:
    str r0, [r6, #V_SRC]
lp_have:
    ldr r0, [r6, #V_SRC]
    ldr r1, =LOOK_OUT
    cmp r0, r1
    ldrne r0, =VRAM
    add r0, r0, r4, lsl #7
    ldr r1, =SHADOW
    add r1, r1, r4, lsl #7
    mov r2, #0
    mov r3, #32
lp_loop:
    ldr r12, [r0], #4
    ldr lr, [r1]
    cmp r12, lr
    movne r2, #1
    str r12, [r1], #4
    subs r3, r3, #1
    bne lp_loop
    cmp r5, #0
    movne r2, #1
    mov r0, r2
    pop {r4, r5, r6, pc}

; r0 = 1 when the look goes over this frame: the loading overlay does not draw, EXIT was not held at power-on, the BLECH
; menu is armed with DISPLAY INVERT ON, the start image editor is not open, and the frame is neither the open app's picture
; nor Blechy at power off (the power-off patch sets OFF_ACTIVE to 1 when his sequence starts).
look_wanted:
    ldr r1, =STATE
    ldr r1, [r1, #S_EXPECT]
    cmp r1, #1
    beq lw_no
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq lw_no
    ldr r1, [r1, #0x18]
    tst r1, #KILL
    bne lw_no
    ldr r1, =MENU_STATE
    ldr r2, [r1, #M_ON]
    cmp r2, #1
    bne lw_no
    ldr r2, [r1, #M_INV]
    cmp r2, #0
    beq lw_no
    ldr r1, =EDITOR_MODE
    ldr r1, [r1]
    cmp r1, #1
    beq lw_no
    push {r4, lr}
    ldr r0, =APP_PICTURE
    mov r1, #0
    mov r2, #1024
    bl same
    cmp r0, #0
    bne lw_no_pop
    ldr r0, =OFF_ACTIVE
    ldr r0, [r0]
    cmp r0, #1
    beq lw_no_pop
    mov r0, #1
    pop {r4, pc}
lw_no_pop:
    mov r0, #0
    pop {r4, pc}
lw_no:
    mov r0, #0
    bx lr

; r0 = another picture, r1 = offset, r2 = bytes (a multiple of 4): r0 = 1 when the frame buffer has the same bytes there.
same:
    ldr r3, =VRAM
    add r3, r3, r1
    add r0, r0, r1
sm_loop:
    ldr r1, [r0], #4
    ldr r12, [r3], #4
    cmp r1, r12
    movne r0, #0
    bxne lr
    subs r2, r2, #4
    bne sm_loop
    mov r0, #1
    bx lr

.pool

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
    bl lb_power
    ldr r5, [r4, #S_FRAME]
    add r5, r5, #1
    str r5, [r4, #S_FRAME]
    ldr r1, =FRAME_CAP
    cmp r5, r1
    bhi ov_end
    bl compose
ov_out:
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; The power key while the samples load (device 25.10.: held 30 s, the device stayed on): the panel's report of the key, which
; script_hooks.s waits for during the start, does not come in this phase. So the pin is read here, every frame of the overlay:
; held POWER_MS without a break, the power hold (GPIO 7.11) is let go, as the start and Doom do. Let go earlier, nothing happens.
; Clobbers r0 to r3 and r12.
lb_power:
    ldr r2, =STATE
    ldr r0, =GPIO_IN67
    ldr r0, [r0]
    tst r0, #0x80000000
    movne r0, #0
    strne r0, [r2, #S_PWR]
    bxne lr
    ldr r1, =TICKS
    ldr r1, [r1]
    ldr r3, [r2, #S_PWR]
    cmp r3, #0
    orreq r1, r1, #1
    streq r1, [r2, #S_PWR]
    bxeq lr
    sub r3, r1, r3
    ldr r0, =POWER_MS
    cmp r3, r0
    bxlo lr
    ldr r0, =GPIO_BASE
    mov r1, #0
    mov r2, #3
    ldr r3, =POWER_HOLD
    ldr r12, =GPIO_WRITE
    blx r12
lb_power_wait:
    b lb_power_wait

; ===================================================== the look
; restyle_reference in Python is the same, rule for rule. The frame is copied to LOOK_BACK and LOOK_OUT, read from LOOK_BACK
; and the look drawn into LOOK_OUT.

restyle:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    ldr r0, =VRAM
    ldr r1, =LOOK_BACK
    mov r2, #32
    ldr r11, =LOOK_OUT
rs_copy:
    ldmia r0!, {r3-r10}
    stmia r1!, {r3-r10}
    sub r1, r1, #32
    ldmia r1!, {r3-r10}
    stmia r11!, {r3-r10}
    subs r2, r2, #1
    bne rs_copy
    ldr r11, =LOOK_VARS
    mov r0, #0
    str r0, [r11, #V_TAB]
    str r0, [r11, #V_N]
; the tab: a run of 30 to 100 pixels from x 0 in one of the rows 0 to 2, its bottom the last full row 6 to 12 rows down
    mov r4, #0
rs_tab:
    mov r5, #0
rs_tab_run:
    mov r0, r5
    mov r1, r4
    bl src_px
    cmp r0, #0
    beq rs_tab_len
    add r5, r5, #1
    cmp r5, #128
    blo rs_tab_run
rs_tab_len:
    cmp r5, #30
    blo rs_tab_next
    cmp r5, #100
    bhi rs_tab_next
    sub r6, r5, #1
    mvn r7, #0
    add r8, r4, #6
    add r9, r4, #12
rs_tab_row:
    cmp r8, r9
    bhi rs_tab_rows
    mov r0, #0
    mov r1, r6
    mov r2, r8
    bl full_row
    cmp r0, #0
    movne r7, r8
    add r8, r8, #1
    b rs_tab_row
rs_tab_rows:
    cmp r7, #0
    blt rs_tab_next
    mov r0, #1
    str r0, [r11, #V_TAB]
    str r7, [r11, #V_BOT]
    str r6, [r11, #V_END]
    sub r0, r6, #1               ; the stamped corner
    mov r1, r7
    mov r2, #0
    bl dst_put
    mov r0, r6
    mov r1, r7
    mov r2, #0
    bl dst_put
    mov r0, r6
    sub r1, r7, #1
    mov r2, #0
    bl dst_put
    b rs_boxes
rs_tab_next:
    add r4, r4, #1
    cmp r4, #3
    blo rs_tab
; the boxes: a top line of 24 pixels and more, both sides down from it, the bottom the last full row before a side breaks
rs_boxes:
    mov r4, #0
rb_row:
    mov r5, #0
rb_rescan:                       ; r10 the row's page in LOOK_BACK, r9 the row's bit
    ldr r10, =LOOK_BACK
    mov r0, r4, lsr #3
    add r10, r10, r0, lsl #7
    and r0, r4, #7
    mov r9, #1
    mov r9, r9, lsl r0
rb_scan:
    cmp r5, #128
    bhs rb_row_next
    ldrb r0, [r10, r5]
    tst r0, r9
    addeq r5, r5, #1
    beq rb_scan
    mov r6, r5
rb_run:
    add r5, r5, #1
    cmp r5, #128
    bhs rb_run_end
    ldrb r0, [r10, r5]
    tst r0, r9
    bne rb_run
rb_run_end:
    sub r7, r5, #1
    sub r0, r7, r6
    cmp r0, #23
    blo rb_scan
    cmp r4, #0
    beq rb_top
    mov r0, r6
    sub r1, r4, #1
    bl src_px
    cmp r0, #0
    beq rb_top
    mov r0, r7
    sub r1, r4, #1
    bl src_px
    cmp r0, #0
    bne rb_scan
rb_top:
    mvn r8, #0
    add r9, r4, #1
rb_down:
    cmp r9, #64
    bhs rb_found
    mov r0, r6
    mov r1, r9
    bl src_px
    cmp r0, #0
    beq rb_found
    mov r0, r7
    mov r1, r9
    bl src_px
    cmp r0, #0
    beq rb_found
    mov r0, r6
    mov r1, r7
    mov r2, r9
    bl full_row
    cmp r0, #0
    movne r8, r9
    add r9, r9, #1
    b rb_down
rb_found:
    cmp r8, #0
    blt rb_rescan
    sub r0, r8, r4
    cmp r0, #6
    blo rb_rescan
    ldr r10, [r11, #V_N]
    cmp r10, #LOOK_NBOX
    bhs rb_rescan
    ldr r9, =LOOK_BOXES
    mov r0, #LOOK_BOX
    mul r1, r10, r0
    add r9, r9, r1
    str r6, [r9, #B_X0]
    str r4, [r9, #B_Y0]
    str r7, [r9, #B_X1]
    str r8, [r9, #B_Y1]
    mov r0, #1
    str r0, [r9, #B_ALIVE]
    mov r0, #0
    str r0, [r9, #B_DONE]
    add r10, r10, #1
    str r10, [r11, #V_N]
    add r0, r6, #1
    add r1, r4, #1
    sub r2, r7, #1
    sub r3, r8, #1
    bl count_in
    mov r0, r0, lsl #1
    sub r1, r8, r4
    sub r1, r1, #1
    sub r2, r7, r6
    sub r2, r2, #1
    mul r3, r1, r2
    cmp r0, r3
    movhi r0, #1
    movls r0, #0
    str r0, [r9, #B_PLATE]
    b rb_rescan
rb_row_next:
    add r4, r4, #1
    cmp r4, #64
    blo rb_row
; a box inside another is left out
    ldr r10, [r11, #V_N]
    ldr r4, =LOOK_BOXES
    mov r5, #0
rc_i:
    cmp r5, r10
    bhs rc_done
    mov r0, #LOOK_BOX
    mla r6, r5, r0, r4
    mov r7, #0
rc_j:
    cmp r7, r10
    bhs rc_next_i
    cmp r7, r5
    beq rc_next_j
    mla r8, r7, r0, r4
    ldr r1, [r8, #B_X0]
    ldr r2, [r6, #B_X0]
    cmp r1, r2
    bgt rc_next_j
    ldr r1, [r8, #B_Y0]
    ldr r2, [r6, #B_Y0]
    cmp r1, r2
    bgt rc_next_j
    ldr r1, [r8, #B_X1]
    ldr r2, [r6, #B_X1]
    cmp r1, r2
    blt rc_next_j
    ldr r1, [r8, #B_Y1]
    ldr r2, [r6, #B_Y1]
    cmp r1, r2
    blt rc_next_j
    mov r1, #0
    str r1, [r6, #B_ALIVE]
    b rc_next_i
rc_next_j:
    add r7, r7, #1
    b rc_j
rc_next_i:
    add r5, r5, #1
    b rc_i
rc_done:
; drawn in order, but not the tab and not one that overlaps a box drawn before
    mov r5, #0
rp_i:
    cmp r5, r10
    bhs rs_header
    mov r0, #LOOK_BOX
    mla r6, r5, r0, r4
    ldr r0, [r6, #B_ALIVE]
    cmp r0, #0
    beq rp_next
    ldr r0, [r11, #V_TAB]
    cmp r0, #0
    beq rp_overlap
    ldr r0, [r6, #B_Y0]
    ldr r1, [r11, #V_BOT]
    cmp r0, r1
    ble rp_next
rp_overlap:
    mov r7, #0
rp_j:
    cmp r7, r5
    bhs rp_take
    mov r0, #LOOK_BOX
    mla r8, r7, r0, r4
    ldr r0, [r8, #B_DONE]
    cmp r0, #0
    beq rp_next_j
    ldr r0, [r6, #B_X1]
    ldr r1, [r8, #B_X0]
    cmp r0, r1
    blt rp_next_j
    ldr r0, [r6, #B_X0]
    ldr r1, [r8, #B_X1]
    cmp r0, r1
    bgt rp_next_j
    ldr r0, [r6, #B_Y1]
    ldr r1, [r8, #B_Y0]
    cmp r0, r1
    blt rp_next_j
    ldr r0, [r6, #B_Y0]
    ldr r1, [r8, #B_Y1]
    cmp r0, r1
    bgt rp_next_j
    b rp_next
rp_next_j:
    add r7, r7, #1
    b rp_j
rp_take:
    mov r0, #1
    str r0, [r6, #B_DONE]
    mov r0, r6
    bl draw_box
rp_next:
    add r5, r5, #1
    b rp_i
; the right rim beside the header's symbols: rows 0 to the tab's bottom + 1 (else 10), only right of the last lit pixel + 1
rs_header:
    mov r9, #9
    ldr r0, [r11, #V_TAB]
    cmp r0, #0
    ldrne r9, [r11, #V_BOT]
    add r9, r9, #1
    mov r4, #0
rh_row:
    cmp r4, r9
    bhi rs_rim
    mov r5, #127
rh_last:
    mov r0, r5
    mov r1, r4
    bl src_px
    cmp r0, #0
    bne rh_have
    subs r5, r5, #1
    bpl rh_last
    mvn r5, #8
rh_have:
    add r5, r5, #1
    mov r6, #125
rh_col:
    cmp r6, r5
    ble rh_skip
    mov r0, r6
    mov r1, r4
    sub r2, r6, #124
    bl dith_put
rh_skip:
    add r6, r6, #1
    cmp r6, #128
    blo rh_col
    add r4, r4, #1
    b rh_row
; the rim on the bottom, left and right: where all three of its pixels are free, in stretches of 16 and more
rs_rim:
    mov r4, #0
rr_side:
    cmp r4, #3
    bhs rs_out
    cmp r4, #0
    moveq r5, #128
    movne r5, #64
    mvn r6, #0
    mov r7, #0
rr_t:
    cmp r7, r5
    bhs rr_end_side
    mov r8, #0
rr_d:
    mov r0, r7
    mov r1, r8
    mov r2, r4
    bl cell
    bl covered_at
    cmp r0, #0
    bne rr_bad
    add r8, r8, #1
    cmp r8, #3
    blo rr_d
    mov r0, r7                   ; no lit pixel within 2 of any of the three: one rectangle, the windows together
    mov r1, r4
    bl ink_near
    cmp r0, #0
    bne rr_bad
    cmp r6, #0
    movlt r6, r7
    add r7, r7, #1
    b rr_t
rr_bad:
    cmp r6, #0
    blt rr_bad_next
    mov r0, r6
    mov r1, r7
    mov r2, r4
    bl paint_run
    mvn r6, #0
rr_bad_next:
    add r7, r7, #1
    b rr_t
rr_end_side:
    cmp r6, #0
    blt rr_next_side
    mov r0, r6
    mov r1, r5
    mov r2, r4
    bl paint_run
rr_next_side:
    add r4, r4, #1
    b rr_side
rs_out:
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}

.align 4
.pool

.org @LOOK_CODE@
; r0 = the box: inverts a plate, draws the cut corners and the shadow, notes where no rim goes. Keeps r4 to r11.
draw_box:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    mov r11, r0
    ldr r4, [r11, #B_X0]
    ldr r5, [r11, #B_Y0]
    ldr r6, [r11, #B_X1]
    ldr r7, [r11, #B_Y1]
    ldr r0, [r11, #B_PLATE]
    cmp r0, #0
    beq db_corners
    mov r8, r4                   ; inverted, a column of a page at a time
db_inv_col:
    mov r9, r5, lsr #3
db_inv_page:
    mov r0, r9, lsl #3
    cmp r0, r7
    bhi db_inv_next
    mov r0, r9
    mov r1, r5
    mov r2, r7
    bl page_mask
    ldr r1, =LOOK_BACK
    add r1, r1, r8
    ldrb r1, [r1, r9, lsl #7]
    ldr r2, =LOOK_OUT
    add r2, r2, r8
    add r2, r2, r9, lsl #7
    ldrb r3, [r2]
    bic r3, r3, r0
    mvn r1, r1
    and r1, r1, r0
    orr r3, r3, r1
    strb r3, [r2]
    add r9, r9, #1
    cmp r9, #8
    blo db_inv_page
db_inv_next:
    add r8, r8, #1
    cmp r8, r6
    bls db_inv_col
    cmp r5, #0
    subne r5, r5, #1
    cmp r7, #63
    addlo r7, r7, #1
    mov r8, r4
db_h:
    mov r0, r8
    mov r1, r5
    mov r2, #1
    bl dst_put
    mov r0, r8
    mov r1, r7
    bl dst_put
    add r8, r8, #1
    cmp r8, r6
    bls db_h
    mov r9, r5
db_v:
    mov r0, r4
    mov r1, r9
    mov r2, #1
    bl dst_put
    mov r0, r6
    bl dst_put
    add r9, r9, #1
    cmp r9, r7
    bls db_v
db_corners:
    mov r0, r4
    mov r1, r5
    mov r2, #0
    bl dst_put
    add r0, r4, #1
    add r1, r5, #1
    mov r2, #1
    bl dst_put
    mov r0, r6
    mov r1, r5
    mov r2, #0
    bl dst_put
    sub r0, r6, #1
    add r1, r5, #1
    mov r2, #1
    bl dst_put
    mov r0, r4
    mov r1, r7
    mov r2, #0
    bl dst_put
    add r0, r4, #1
    sub r1, r7, #1
    mov r2, #1
    bl dst_put
    mov r0, r6
    mov r1, r7
    mov r2, #0
    bl dst_put
    sub r0, r6, #1
    sub r1, r7, #1
    mov r2, #1
    bl dst_put
    add r8, r4, #2               ; the shadow below
    add r10, r6, #2
    cmp r10, #127
    movhi r10, #127
db_below:
    cmp r8, r10
    bhi db_right
    add r1, r7, #1
    cmp r1, #63
    bhi db_below_next
    mov r0, r8
    mov r2, #2
    bl dith_put
    add r1, r7, #2
    cmp r1, #63
    bhi db_below_next
    mov r0, r8
    mov r2, #1
    bl dith_put
db_below_next:
    add r8, r8, #1
    b db_below
db_right:
    add r9, r5, #2               ; the shadow right
    add r10, r7, #2
    cmp r10, #63
    movhi r10, #63
db_right_row:
    cmp r9, r10
    bhi db_cover
    add r0, r6, #1
    cmp r0, #127
    bhi db_right_next
    mov r1, r9
    mov r2, #2
    bl dith_put
    add r0, r6, #2
    cmp r0, #127
    bhi db_right_next
    mov r1, r9
    mov r2, #1
    bl dith_put
db_right_next:
    add r9, r9, #1
    b db_right_row
db_cover:
    subs r0, r4, #1
    movmi r0, #0
    str r0, [r11, #B_CX0]
    subs r0, r5, #1
    movmi r0, #0
    str r0, [r11, #B_CY0]
    add r0, r6, #2
    cmp r0, #127
    movhi r0, #127
    str r0, [r11, #B_CX1]
    add r0, r7, #2
    cmp r0, #63
    movhi r0, #63
    str r0, [r11, #B_CY1]
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}
.pool

; r0 = x0, r1 = x1, r2 = y: r0 = 1 when the frame is lit from x0 to x1 in row y. Clobbers r1 to r3 and r12.
full_row:
    ldr r3, =LOOK_BACK
    mov r12, r2, lsr #3
    add r3, r3, r12, lsl #7
    and r12, r2, #7
    mov r2, #1
    mov r2, r2, lsl r12
fr_loop:
    ldrb r12, [r3, r0]
    tst r12, r2
    moveq r0, #0
    bxeq lr
    add r0, r0, #1
    cmp r0, r1
    bls fr_loop
    mov r0, #1
    bx lr

; r0 = x0, r1 = y0, r2 = x1, r3 = y1: r0 = the lit pixels of the frame in that rectangle. Keeps r4 to r11.
count_in:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mov r8, #0
    ldr r10, =LOOK_BACK
ci_col:
    cmp r4, r6
    bhi ci_out
    mov r9, r5, lsr #3
ci_page:
    mov r0, r9, lsl #3
    cmp r0, r7
    bhi ci_next_col
    mov r0, r9
    mov r1, r5
    mov r2, r7
    bl page_mask
    add r1, r10, r4
    ldrb r1, [r1, r9, lsl #7]
    and r1, r1, r0
    mov r2, r1, lsr #1           ; the bits set in the byte
    and r2, r2, #0x55
    sub r1, r1, r2
    and r2, r1, #0x33
    mov r1, r1, lsr #2
    and r1, r1, #0x33
    add r1, r1, r2
    add r1, r1, r1, lsr #4
    and r1, r1, #0x0F
    add r8, r8, r1
    add r9, r9, #1
    cmp r9, #8
    blo ci_page
ci_next_col:
    add r4, r4, #1
    b ci_col
ci_out:
    mov r0, r8
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; r0 = page, r1 = first row, r2 = last row: r0 = the bits of the page that lie in those rows. Clobbers r1 to r3.
page_mask:
    mov r0, r0, lsl #3
    subs r1, r1, r0
    movmi r1, #0
    sub r2, r2, r0
    cmp r2, #7
    movgt r2, #7
    rsb r2, r2, #7
    mov r0, #0xFF
    mov r3, r0, lsr r2
    mov r0, r0, lsl r1
    and r0, r0, r3
    bx lr

; r0 = t, r1 = d (0 at the edge), r2 = side (0 bottom, 1 left, 2 right): r0 = x, r1 = y. Clobbers r2.
cell:
    cmp r2, #1
    beq ce_left
    bhi ce_right
    rsb r1, r1, #63
    bx lr
ce_left:
    mov r2, r0
    mov r0, r1
    mov r1, r2
    bx lr
ce_right:
    mov r2, r0
    rsb r0, r1, #127
    mov r1, r2
    bx lr

; r0 = x, r1 = y: r0 = 1 when no rim goes there: the header row of a tab, next to a drawn box. Keeps r4 to r11.
covered_at:
    push {r4, r5, r6, r7}
    ldr r12, =LOOK_VARS
    ldr r2, [r12, #V_TAB]
    cmp r2, #0
    beq ca_boxes
    ldr r2, [r12, #V_BOT]
    add r2, r2, #1
    cmp r1, r2
    ble ca_yes
ca_boxes:
    ldr r6, [r12, #V_N]
    ldr r7, =LOOK_BOXES
ca_box:
    subs r6, r6, #1
    bmi ca_no
    ldr r2, [r7, #B_DONE]
    cmp r2, #0
    beq ca_next
    ldr r2, [r7, #B_CX0]
    cmp r0, r2
    blt ca_next
    ldr r2, [r7, #B_CX1]
    cmp r0, r2
    bgt ca_next
    ldr r2, [r7, #B_CY0]
    cmp r1, r2
    blt ca_next
    ldr r2, [r7, #B_CY1]
    cmp r1, r2
    ble ca_yes
ca_next:
    add r7, r7, #LOOK_BOX
    b ca_box
ca_yes:
    mov r0, #1
    pop {r4, r5, r6, r7}
    bx lr
ca_no:
    mov r0, #0
    pop {r4, r5, r6, r7}
    bx lr

; r0 = t, r1 = side: r0 = the lit pixels within 2 of the rim's three pixels at t (bottom: columns t - 2 to t + 2 of rows
; 59 to 63; left: columns 0 to 4, right: 123 to 127, of rows t - 2 to t + 2). Keeps r4 to r11.
ink_near:
    push {r4, lr}
    cmp r1, #0
    bne in_side
    add r2, r0, #2
    subs r0, r0, #2
    movmi r0, #0
    cmp r2, #127
    movhi r2, #127
    mov r1, #59
    mov r3, #63
    b in_count
in_side:
    mov r4, r1
    subs r1, r0, #2
    movmi r1, #0
    add r3, r0, #2
    cmp r3, #63
    movhi r3, #63
    cmp r4, #1
    moveq r0, #0
    moveq r2, #4
    movne r0, #123
    movne r2, #127
in_count:
    bl count_in
    pop {r4, pc}

; r0 = start, r1 = end (not included), r2 = side: the rim along a stretch of 16 and more. Keeps r4 to r11.
paint_run:
    sub r3, r1, r0
    cmp r3, #16
    bxlo lr
    push {r4, r5, r6, r7, r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
pr_u:
    cmp r4, r5
    bhs pr_out
    mov r7, #0
pr_d:
    mov r0, r4
    mov r1, r7
    mov r2, r6
    bl cell
    mov r8, r0                   ; the pixel's distance to the nearest edge
    cmp r1, r8
    movlo r8, r1
    rsb r2, r0, #127
    cmp r2, r8
    movlo r8, r2
    rsb r2, r1, #63
    cmp r2, r8
    movlo r8, r2
    cmp r8, r7
    bne pr_next
    rsb r2, r7, #3
    bl dith_put
pr_next:
    add r7, r7, #1
    cmp r7, #3
    blo pr_d
    add r4, r4, #1
    b pr_u
pr_out:
    pop {r4, r5, r6, r7, r8, pc}

; r0 = x, r1 = y: r0 = the pixel of the frame (LOOK_BACK). Clobbers r12.
src_px:
    ldr r12, =LOOK_BACK
    add r12, r12, r0
    mov r0, r1, lsr #3
    add r12, r12, r0, lsl #7
    ldrb r12, [r12]
    and r0, r1, #7
    mov r0, r12, lsr r0
    and r0, r0, #1
    bx lr

; r0 = x, r1 = y, r2 = level 0 to 4: the dithered pixel into LOOK_OUT. Clobbers r0, r2, r3, r12.
dith_put:
    and r3, r1, #1
    and r12, r0, #1
    add r3, r12, r3, lsl #1
    mov r3, r3, lsl #3
    ldr r12, =DITHER_WORD
    mov r12, r12, lsr r3
    and r12, r12, #0xFF
    cmp r2, r12
    movhi r2, #1
    movls r2, #0
; r0 = x, r1 = y, r2 = 1 lit or 0 dark: the pixel into LOOK_OUT. Clobbers r0, r3, r12.
dst_put:
    ldr r12, =LOOK_OUT
    add r12, r12, r0
    mov r0, r1, lsr #3
    add r12, r12, r0, lsl #7
    and r0, r1, #7
    mov r3, #1
    mov r3, r3, lsl r0
    ldrb r0, [r12]
    cmp r2, #0
    biceq r0, r0, r3
    orrne r0, r0, r3
    strb r0, [r12]
    bx lr

; r0 = LOOK_OUT with the card picture in it while the firmware's error box says "No Card." or "Card Error", else 0.
; Not with EXIT held at power-on. The look's copy of the frame is spoiled, so the look draws anew once the box is gone.
card_wanted:
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq cw_no
    ldr r1, [r1, #0x18]
    tst r1, #KILL
    bne cw_no
    ldr r1, =ERR_CODE
    ldr r1, [r1]
    cmp r1, #2
    ldreq r0, =CARD_ART
    beq cw_have
    cmp r1, #4
    bne cw_no
    ldr r0, =CARD_ART4
cw_have:
    ldr r1, =LOOK_OUT
    add r3, r1, #1024
cw_run:
    ldrb r2, [r0], #1
    ldrb r12, [r0], #1
cw_put:
    strb r12, [r1], #1
    subs r2, r2, #1
    bne cw_put
    cmp r1, r3
    blo cw_run
    ldr r1, =VRAM
    ldr r1, [r1]
    mvn r1, r1
    ldr r2, =LOOK_BACK
    str r1, [r2]
    ldr r0, =LOOK_OUT
    bx lr
cw_no:
    mov r0, #0
    bx lr

.align 4
lit_pool:
.pool

.org @ANIM_CODE@
; ===================================================== the animation (docs/hintergrund/ladeanimation.md)
; loading_anim.validate and loading_anim.picture in Python are the same, check for check and list for list.

; Picks the animation (the custom one in SLOT when it passes validate, else DEFAULT), puts its picture 0 into PBUF and
; clears the counts of the loader's reads. Runs in lb_stat before the overlay is switched on. Keeps r4 to r11.
anim_start:
    push {r4, r5, r6, lr}
    ldr r4, =VARS
    ldr r0, =SLOT
    bl validate
    cmp r0, #0
    ldrne r5, =SLOT
    ldreq r5, =DEFAULT
    str r5, [r4, #A_FILE]
    add r0, r5, #6
    bl u16
    str r0, [r4, #A_N]
    add r0, r5, #8
    bl u16
    str r0, [r4, #A_M]
    add r0, r5, #10
    bl u16
    add r0, r5, r0
    str r0, [r4, #A_TABLE]
    ldrb r0, [r5, #5]
    str r0, [r4, #A_FROM]
    mov r0, #0
    str r0, [r4, #A_SHOWN]
    str r0, [r4, #R_POS]
    str r0, [r4, #R_NEXT]
    str r0, [r4, #R_T]
    str r0, [r4, #R_BYTES]
    str r0, [r4, #R_MS]
    str r0, [r4, #P_SHOWN]
    ldr r0, =TICKS
    ldr r0, [r0]
    str r0, [r4, #P_T]
    add r1, r5, #16
    ldr r0, =PBUF
    mov r2, #1024
as_copy:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne as_copy
    pop {r4, r5, r6, pc}

; r0 = a file (word aligned): r0 = 1 when it may be played, else 0. Magic, version, the loop's percent, the size at most
; MAX_BYTES, at least one progress picture, the list table behind picture 0 and inside the file, every list and every run
; inside the file and no run past byte 1023. Keeps r4 to r11.
validate:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    mov r4, r0
    ldr r1, [r4]
    ldr r2, =MAGIC
    cmp r1, r2
    bne va_bad
    ldrb r1, [r4, #4]
    cmp r1, #1
    bne va_bad
    ldrb r1, [r4, #5]
    cmp r1, #100
    bhi va_bad
    ldr r5, [r4, #12]            ; the size
    ldr r1, =MAX_BYTES
    cmp r5, r1
    bhi va_bad
    add r0, r4, #6
    bl u16
    subs r6, r0, #1              ; N - 1
    bmi va_bad
    add r0, r4, #8
    bl u16
    add r6, r6, r0               ; the lists: N - 1 + M
    add r0, r4, #10
    bl u16
    mov r7, r0                   ; where the table is
    ldr r1, =HEAD_FRAME
    cmp r7, r1
    blo va_bad
    add r1, r7, r6, lsl #1
    cmp r1, r5
    bhi va_bad
va_list:
    subs r6, r6, #1
    bmi va_good
    add r0, r4, r7
    bl u16
    add r7, r7, #2
    mov r8, r0                   ; where the list is
    add r1, r8, #2
    cmp r1, r5
    bhi va_bad
    add r0, r4, r8
    bl u16
    mov r9, r0                   ; its runs
    add r8, r8, #2
va_run:
    subs r9, r9, #1
    bmi va_list
    add r1, r8, #2
    cmp r1, r5
    bhi va_bad
    add r0, r4, r8
    bl u16
    mov r1, r0, lsr #10
    add r1, r1, #1               ; length
    bic r0, r0, #0xFC00          ; offset in the picture
    add r0, r0, r1
    cmp r0, #1024
    bhi va_bad
    add r8, r8, #2
    add r8, r8, r1
    cmp r8, r5
    bhi va_bad
    b va_run
va_good:
    mov r0, #1
    pop {r4, r5, r6, r7, r8, r9, r10, pc}
va_bad:
    mov r0, #0
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; r0 = an address: r0 = the halfword there, little endian, byte by byte (the file has no alignment; the assembler has no
; ldrh). Clobbers r1.
u16:
    ldrb r1, [r0, #1]
    ldrb r0, [r0]
    orr r0, r0, r1, lsl #8
    bx lr

; r0 = a list, r1 = a picture: the list's runs written over the picture. Keeps r4 to r11.
apply:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    bl u16
    mov r6, r0                   ; runs
    add r4, r4, #2
ap_run:
    subs r6, r6, #1
    bmi ap_out
    mov r0, r4
    bl u16
    mov r2, r0, lsr #10          ; length - 1
    bic r0, r0, #0xFC00
    add r0, r5, r0
    add r4, r4, #2
ap_byte:
    ldrb r1, [r4], #1
    strb r1, [r0], #1
    subs r2, r2, #1
    bpl ap_byte
    b ap_run
ap_out:
    pop {r4, r5, r6, pc}

; r0 = list number: r0 = the list (table entry, an offset from the start of the file). Keeps r4 to r11.
list_at:
    push {r4, lr}
    ldr r4, =VARS
    ldr r1, [r4, #A_TABLE]
    add r0, r1, r0, lsl #1
    bl u16
    ldr r1, [r4, #A_FILE]
    add r0, r1, r0
    pop {r4, pc}

; r0 = the progress picture wanted: the lists from the one in PBUF up to it are written over PBUF one after the other,
; only forward. Keeps r4 to r11.
advance:
    push {r4, r5, r6, lr}
    ldr r4, =VARS
    mov r5, r0
    ldr r6, [r4, #A_SHOWN]
ad_next:
    cmp r6, r5
    bhs ad_out
    mov r0, r6                   ; list k + 1 makes picture k + 1, it is entry k of the table
    add r6, r6, #1
    bl list_at
    ldr r1, =PBUF
    bl apply
    b ad_next
ad_out:
    str r6, [r4, #A_SHOWN]
    pop {r4, r5, r6, pc}

; r0 = the progress in permille: 1000 when the loader is done, else the share of the file read so far, at most 999. While a
; read is under way it runs on at the rate of this load's reads so far (bytes per tick), never past the end of that read,
; and it never goes back. Keeps r4 to r11.
permille:
    push {r4, r5, r6, r7, r8, lr}
    ldr r4, =STATE
    ldr r5, =VARS
    ldr r0, [r4, #S_DONE]
    cmp r0, #1
    moveq r0, #1000
    beq pm_keep
    ldr r6, [r4, #S_CUR]
    ldr r0, [r5, #R_POS]
    cmp r0, r6
    movhi r6, r0                 ; read so far
    ldr r7, [r5, #R_NEXT]
    cmp r7, r6
    bls pm_scale                 ; no read under way
    ldr r1, [r5, #R_MS]
    cmp r1, #0
    beq pm_scale                 ; no rate yet
    ldr r0, [r5, #R_BYTES]
    bl UDIV
    ldr r1, =0xFFFF
    cmp r0, r1
    movhi r0, r1                 ; bytes per tick
    ldr r3, [r5, #R_T]           ; before the clock: a read that begins in between gives no negative time
    ldr r2, =TICKS
    ldr r2, [r2]
    sub r2, r2, r3
    cmp r2, r1
    movhi r2, r1                 ; ticks since the read began
    mul r3, r0, r2
    sub r2, r7, r6
    cmp r3, r2
    movhs r6, r7
    addlo r6, r6, r3
pm_scale:
    ldr r1, [r4, #S_MAX]
    cmp r1, #0
    moveq r0, #0
    beq pm_keep
pm_shift:
    cmp r1, #0x400000
    blo pm_div
    mov r6, r6, lsr #1
    mov r1, r1, lsr #1
    b pm_shift
pm_div:
    mov r0, #1000
    mul r2, r6, r0
    mov r0, r2
    bl UDIV
    ldr r1, =999
    cmp r0, r1
    movhi r0, r1
pm_keep:
    ldr r1, [r5, #P_SHOWN]
    cmp r0, r1
    movls r0, r1
    bls pm_out
    str r0, [r5, #P_SHOWN]
    ldr r1, =TICKS
    ldr r1, [r1]
    str r1, [r5, #P_T]
pm_out:
    pop {r4, r5, r6, r7, r8, pc}

; Picks the picture and draws it. The key (the progress picture, the loop's picture, done) changes at most every FRAME_MS;
; until then the last one is drawn again, every frame, over whatever the firmware put into the buffer. Only a new key is
; marked as changed.
compose:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    ldr r4, =STATE
    ldr r5, =VARS
    bl permille
    mov r6, r0                   ; permille
    ldr r0, =TICKS
    ldr r8, [r0]                 ; now, ms
    ldr r1, [r5, #A_N]
    sub r1, r1, #1
    mul r0, r6, r1
    ldr r1, =1000
    bl UDIV
    mov r7, r0                   ; the progress picture: permille * (N - 1) / 1000
    mov r9, #0                   ; the loop's picture + 1, 0 none
    ldr r0, [r5, #A_M]
    cmp r0, #0
    beq cp_key
    ldr r1, [r5, #A_FROM]
    cmp r1, #0
    beq cp_stall
    mov r0, #10
    mul r2, r1, r0
    cmp r6, r2
    blo cp_key                   ; before the loop's percent
    b cp_loop
cp_stall:
    ldr r1, [r5, #P_T]
    sub r1, r8, r1
    ldr r2, =STALL_MS
    cmp r1, r2
    blo cp_key                   ; the progress has not stood long enough
cp_loop:
    mov r0, r8
    ldr r1, =LOOP_MS
    bl UDIV
    ldr r1, [r5, #A_M]
    bl UDIVMOD
    add r9, r1, #1
cp_key:
    orr r10, r7, r9, lsl #16
    ldr r0, [r4, #S_DONE]
    cmp r0, #1
    orreq r10, r10, #0x1000000
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
    ldr r0, [r4, #S_KEY]
    bl draw
    b cp_done
cp_take:
    str r10, [r4, #S_KEY]
    str r8, [r4, #S_LAST]
    mov r0, r7
    bl advance
    mov r0, r10
    bl draw
    mov r0, #1
    str r0, [r4, #S_DRAWN]
    mov r0, #0
    mov r1, #0
    mov r2, #128
    mov r3, #64
    bl MARK
cp_done:
    pop {r4, r5, r6, r7, r8, r9, r10, pc}

; r0 = key: PBUF into the frame buffer (VRAM), the loop's list over it, complemented when the display is not reversed.
draw:
    push {r4, r5, r6, lr}
    mov r4, r0
    ldr r0, =VRAM
    ldr r1, =PBUF
    mov r2, #1024
dr_copy:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #4
    bne dr_copy
    mov r0, r4, lsr #16
    ands r0, r0, #0xFF
    beq dr_flip
    ldr r5, =VARS
    ldr r1, [r5, #A_N]
    add r0, r0, r1
    sub r0, r0, #2               ; table entry N - 1 + loop
    bl list_at
    ldr r1, =VRAM
    bl apply
; complemented unless the BLECH menu is armed with DISPLAY INVERT ON (then the controller shows set bits light)
dr_flip:
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_ON]
    cmp r1, #1
    bne dr_not
    ldr r1, [r0, #M_INV]
    cmp r1, #0
    bne dr_out
dr_not:
    ldr r0, =VRAM
    mov r2, #1024
dr_not_loop:
    ldr r3, [r0]
    mvn r3, r3
    str r3, [r0], #4
    subs r2, r2, #4
    bne dr_not_loop
dr_out:
    pop {r4, r5, r6, pc}

; ===================================================== read
; Replaces the two calls of f_read in the sample parser's PCM loop (r0 the file object, r1 the buffer, r2 the bytes, r3
; where the count goes). While the overlay draws it notes where the read ends and when it began, reads, then adds the bytes
; and ticks to this load's totals and notes the file's position and size. Otherwise it is the plain call.
lb_read:
    ldr r12, =STATE
    ldr r12, [r12, #S_EXPECT]
    cmp r12, #1
    ldrne r12, =F_READ
    bxne r12
    push {r4, r5, r6, r7, r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    ldr r8, =VARS
    ldr r0, =TICKS
    ldr r0, [r0]
    str r0, [r8, #R_T]           ; first the time, then the end: the frame never sees a new end with an old time
    ldr r0, [r4, #8]
    add r0, r0, r6
    ldr r1, [r4, #12]
    cmp r0, r1
    movhi r0, r1
    str r0, [r8, #R_NEXT]
    mov r0, r4
    mov r1, r5
    mov r2, r6
    mov r3, r7
    bl F_READ
    mov r5, r0                   ; its result
    ldr r0, =TICKS
    ldr r0, [r0]
    ldr r1, [r8, #R_T]
    sub r0, r0, r1
    ldr r1, [r8, #R_MS]
    add r1, r1, r0
    str r1, [r8, #R_MS]
    ldr r0, [r7]
    ldr r1, [r8, #R_BYTES]
    add r1, r1, r0
    str r1, [r8, #R_BYTES]
    ldr r0, [r4, #8]
    ldr r1, [r8, #R_POS]
    cmp r0, r1
    movhi r1, r0
    str r1, [r8, #R_POS]
    str r1, [r8, #R_NEXT]
    ldr r0, [r4, #12]
    ldr r1, =STATE
    str r0, [r1, #S_MAX]
    mov r0, r5
    pop {r4, r5, r6, r7, r8, pc}

.align 4
.pool
"""


def art():
    return LOAD_ART.read_bytes()


def anim():
    """The default loading animation, assets/blechy/loading.blla."""
    data = LOAD_ANIM.read_bytes()
    bad = loading_anim.validate(data)
    if bad or len(data) > ANIM_DEFAULT_END - ANIM_DEFAULT:
        raise SystemExit(f"{LOAD_ANIM}: {bad or f'{len(data)} bytes, room for {ANIM_DEFAULT_END - ANIM_DEFAULT}'}")
    return data


def card_frame(code):
    """The picture while the error box shows `code`: Blechy in terror and his line, as the power-off picture is made
    (tools/patch/power_off.py)."""
    import power_off
    lines, top = CARD_TEXTS[code]
    return power_off.frame_bytes(power_off.frame_pixels(power_off.read_png(CARD_SPRITE), lines, top))


def rle(frame):
    """Run-length coded as (count, byte) pairs."""
    out, i = bytearray(), 0
    while i < len(frame):
        j = i
        while j < len(frame) and frame[j] == frame[i] and j - i < 255:
            j += 1
        out += bytes((j - i, frame[i]))
        i = j
    return bytes(out)


def card_picture():
    """Both card pictures, code 2 then code 4."""
    return rle(card_frame(2)) + rle(card_frame(4))


def card_at():
    return LOAD_AT


def source():
    text = SOURCE
    for key, value in {
        "STAT_FUNC": f"{STAT_FUNC:#x}", "LOAD_FUNC": f"{LOAD_FUNC:#x}", "PROGRESS_FUNC": f"{PROGRESS_FUNC:#x}", "FLUSH_FUNC": f"{FLUSH_FUNC:#x}",
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CAP": str(FRAME_CAP), "RETRIES": str(RETRIES), "RETRY_MS": str(RETRY_MS),
        "CODE_AT": f"{CODE_AT:#x}", "TICKS": f"{TICKS:#x}", "MENU_STATE": f"{MENU_STATE:#x}", "FRAME_MS": str(FRAME_MS),
        "SLOT": f"{ANIM_SLOT:#x}", "DEFAULT": f"{ANIM_DEFAULT:#x}", "MAX_BYTES": str(loading_anim.MAX_BYTES), "PBUF": f"{ANIM_BUF:#x}",
        "VARS": f"{ANIM_VARS:#x}", "LOOP_MS": str(TICK_MS), "STALL_MS": str(STALL_MS), "F_READ": f"{READ_FUNC:#x}",
        "UDIV": f"{UDIV:#x}", "UDIVMOD": f"{UDIVMOD:#x}", "ANIM_CODE": f"{ANIM_CODE:#x}",
        "LOOK_CODE": f"{LOOK_CODE:#x}", "LOOK_BACK": f"{LOOK_BACK:#x}", "LOOK_OUT": f"{LOOK_OUT:#x}", "SHADOW": f"{SHADOW:#x}", "LOOK_VARS": f"{LOOK_VARS:#x}", "LOOK_BOXES": f"{LOOK_BOXES:#x}", "LOOK_BOX": str(LOOK_BOX),
        "LOOK_NBOX": str(LOOK_NBOX), "APP_PICTURE": f"{APP_PICTURE:#x}", "OFF_ACTIVE": f"{OFF_ACTIVE:#x}",
        "EDITOR_MODE": f"{EDITOR_MODE:#x}", "ERR_CODE": f"{ERR_CODE:#x}", "CARD_ART": f"{card_at():#x}", "CARD_ART4": f"{card_at() + len(rle(card_frame(2))):#x}", "DITHER_WORD": f"{int.from_bytes(bytes(DITHER), 'little'):#x}",
    }.items():
        text = text.replace(f"@{key}@", value)
    return text


def build_code():
    """(code at, its bytes, symbols, the look's code at, its bytes, the animation's code at, its bytes)."""
    code = arm.assemble(source())
    (at, data), (look_at, look), (anim_at, anim_code) = code.sections
    return at, data, code.symbols, look_at, look, anim_at, anim_code


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def word_of(at, target, link):
    return struct.unpack("<I", branch(at, target, link))[0]


def build_patch(vsb):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    at, code, symbols, look_at, look, anim_at, anim_code = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
    if look_at != LOOK_CODE or look_at + len(look) > LOOK_CODE_END:
        raise SystemExit(f"the look's code is {len(look):#x} bytes, room for {LOOK_CODE_END - LOOK_CODE:#x}")
    if anim_at != ANIM_CODE or anim_at + len(anim_code) > ANIM_CODE_END:
        raise SystemExit(f"the animation's code is {len(anim_code):#x} bytes, room for {ANIM_CODE_END - ANIM_CODE:#x}")

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
        (PAGE_CALL, word_of(PAGE_CALL, PAGE_FUNC, True), "the display send does not compare its pages where the patch expects it"),
        (0xC0015A94, SHADOW, "the display's copy is not where the patch expects it"),
        (0xC0015B4C, 0xC031B310, "the page compare does not read the frame buffer the patch expects"),
        (ERR_CODE_LIT, ERR_CODE, "the error box does not keep its code where the patch expects it"),
        *((site, word_of(site, READ_FUNC, True), "the sample parser does not read its PCM data where the patch expects it") for site in READ_CALLS),
        (UDIV, UDIV_WORD, "the firmware's division is not where the patch expects it"),
        (UDIVMOD, UDIVMOD_WORD, "the firmware's division with remainder is not where the patch expects it"),
    )
    for addr, want, why in expected:
        if word(addr) != want:
            raise SystemExit(f"{why} in this VSB")
    card = card_picture()
    if card_at() + len(card) > LOAD_END:
        raise SystemExit(f"the card picture has {len(card)} bytes, room for {LOAD_END - card_at()}")
    free(STATE, STATE_END - STATE)
    free(LOOK_BACK, LOOK_END - LOOK_BACK)
    free(ANIM_SLOT, ANIM_SLOT_END - ANIM_SLOT)
    free(ANIM_VARS, ANIM_VARS_END - ANIM_VARS)
    free(ANIM_BUF, ANIM_BUF_END - ANIM_BUF)

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
            {"file": file_offset(ANIM_DEFAULT), "bytes": anim().hex(), "expect": free(ANIM_DEFAULT, len(anim())),
             "note": "the default loading animation (assets/blechy/loading.blla), shown when no custom one passes the checks"},
            {"file": file_offset(card_at()), "bytes": card.hex(), "expect": free(card_at(), len(card)),
             "note": "the pictures while the firmware's error box says 'No Card.' or 'Card Error' (Blechy in terror, run-length coded)"},
            {"file": file_offset(LOOK_CODE), "bytes": look.hex(), "expect": free(LOOK_CODE, len(look)),
             "note": "the look: tab corner, box corners and shadows, the dithered rim, drawn over every frame with DISPLAY INVERT ON"},
            {"file": file_offset(ANIM_CODE), "bytes": anim_code.hex(), "expect": free(ANIM_CODE, len(anim_code)),
             "note": "the animation: checks the file, picks the picture by the bytes read, counts the loader's reads"},
            hook(STAT_CALL, "lb_stat", True, "the question whether e2sSample.all exists goes through the hook"),
            hook(PROGRESS_CALL, "lb_progress", True, "the loader's text update goes through the hook"),
            *(hook(site, "lb_read", True, "the sample parser's read of PCM data goes through the hook") for site in READ_CALLS),
            hook(LOAD_CALL, "lb_load", True, "the call of the loader goes through the hook"),
            hook(FLUSH, "lb_frame", False, "the frame function's flush goes through the hook"),
            hook(PAGE_CALL, "lb_page", True, "the display send's page compare goes through the hook"),
        ],
        "hooks": [
            declare(STAT_CALL, "call", "start", "after", False, "after the original asks whether e2sSample.all exists, the hook remembers that a load is coming"),
            declare(PROGRESS_CALL, "call", "start", "before", False, "the hook notes the loader's position; while the overlay draws the text update is left out, otherwise it runs"),
            *(declare(site, "call", "start", "before", False, "while the overlay draws the hook notes where the read ends and when it began, then counts the bytes read; otherwise it is the plain read")
              for site in READ_CALLS),
            declare(LOAD_CALL, "call", "start", "after", False, "the loader runs, then the hook notes that it is done"),
            declare(FLUSH, "instruction", "frame", "before", False, "while a load is expected the hook puts the image over the frame, then the original flush runs"),
            declare(PAGE_CALL, "call", "display-send", "replace", False, "compares and copies the page as the firmware does, from the frame with the look when DISPLAY INVERT is ON"),
        ],
        "startPhase": [
            {"file": file_offset(STAT_CALL), "length": 4, "why": "the start task asks whether e2sSample.all exists, about 75 ms in, after the panel update and the start modes, and now calls lb_stat"},
            {"file": file_offset(PROGRESS_CALL), "length": 4, "why": "the loader updates its text for every sample and now calls lb_progress"},
            *({"file": file_offset(site), "length": 4, "why": "the sample parser reads the PCM data of every sample in chunks up to 64 KiB and now calls lb_read"}
              for site in READ_CALLS),
            {"file": file_offset(ANIM_CODE), "length": len(anim_code), "why": "lb_read and the animation: they count reads and draw only while a load is expected"},
            {"file": file_offset(LOAD_CALL), "length": 4, "why": "the start task calls the loader and now calls lb_load"},
            {"file": file_offset(FLUSH), "length": 4, "why": "every frame of the user interface task ends in this flush; from the first frame (about 170 ms) it calls lb_frame"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "the hooks and what they call: they note a load only when the file exists and EXIT was not held, and draw only then"},
            {"file": file_offset(PAGE_CALL), "length": 4, "why": "the display send compares every page from the first frame on and now calls lb_page"},
            {"file": file_offset(LOOK_CODE), "length": len(look), "why": "the look, drawn by lb_page only with the BLECH menu armed, DISPLAY INVERT ON and EXIT not held"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state of the overlay", "tools/patch/load_bar.py:STATE"),
            ramdecl.area(LOOK_BACK, 1024, "the frame as the firmware drew it, read by the look", "tools/patch/load_bar.py:LOOK_BACK"),
            ramdecl.area(LOOK_OUT, 1024, "the frame with the look, the display send takes its pages from it", "tools/patch/load_bar.py:LOOK_OUT"),
            ramdecl.area(LOOK_VARS, LOOK_END - LOOK_VARS, "the look's tab, boxes and the send's source", "tools/patch/load_bar.py:LOOK_NBOX"),
            ramdecl.area(ANIM_SLOT, ANIM_SLOT_END - ANIM_SLOT, "a custom loading animation, written by the app, FF without one", "tools/patch/load_bar.py:ANIM_SLOT"),
            ramdecl.area(ANIM_VARS, ANIM_VARS_END - ANIM_VARS, "the animation shown, the loader's reads, the progress shown", "tools/patch/load_bar.py:ANIM_VARS"),
            ramdecl.area(ANIM_BUF, ANIM_BUF_END - ANIM_BUF, "the progress picture on screen", "tools/patch/load_bar.py:ANIM_BUF"),
        ],
        "shares": [
            ramdecl.share(MENU_STATE, 4, "script-runtime", "read only: is the BLECH menu armed (M_ON)", "tools/patch/load_bar.py:MENU_STATE"),
            ramdecl.share(MENU_STATE + 0x1B8, 4, "script-runtime", "read only: DISPLAY INVERT (M_INV)", "tools/patch/load_bar.py:MENU_STATE"),
            ramdecl.share(APP_PICTURE, 1024, "script-runtime", "read only: the open app's picture, a frame equal to it gets no look", "tools/patch/load_bar.py:APP_PICTURE"),
            ramdecl.share(OFF_ACTIVE, 4, "power-off", "read only: 1 while Blechy says goodbye at power off, then no look", "tools/patch/load_bar.py:OFF_ACTIVE"),
            ramdecl.share(EDITOR_MODE, 4, "splash-editor", "read only: 1 while the start image editor is open, then no look", "tools/patch/load_bar.py:EDITOR_MODE"),
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
        at, code, symbols, look_at, look, anim_at, anim_code = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes, look {look_at:#x} + {len(look):#x}, animation {anim_at:#x} + {len(anim_code):#x}, "
              f"default {ANIM_DEFAULT:#x} + {len(anim()):#x}, card pictures {LOAD_AT:#x}, state {STATE:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
