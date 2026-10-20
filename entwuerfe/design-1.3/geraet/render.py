#!/usr/bin/env python3
"""Draft screens for the device display (128 x 64, 1 bit): start image, loading frames, power-off sequence.

    python3 entwuerfe/design-1.3/geraet/render.py

Writes, next to this file:
  png/<name>.png       the raw frame, 128 x 64, black = set bit (same convention as assets/blechy/)
  vorschau/<name>.png  the frame on the LCD tint, 4x, for looking at
  vorschau/*-strip.png the sequences side by side

Built from the repo's own art only: assets/blechy/splash.bin, the Blechy sprites and the 5 x 7 script font
(data/script/font.mjs). Nothing is patched; these are drafts for the firmware session.
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
W, H = 128, 64
SPRITES = ROOT / "assets" / "blechy" / "sprites"
IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
LCD_DARK, LCD_LIGHT = (27, 36, 20), (196, 206, 178)

# ---- frame helpers (1 = set = dark on the display) ---------------------------------------------
def blank(v=0):
    return [[v] * W for _ in range(H)]


def copy(f):
    return [row[:] for row in f]


def put(f, x, y, v):
    if 0 <= x < W and 0 <= y < H:
        f[y][x] = v


def rect(f, x0, y0, x1, y1, v):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(f, x, y, v)


def splash():
    b = (ROOT / "assets" / "blechy" / "splash.bin").read_bytes()
    return [[1 if b[(y >> 3) * 128 + x] & (0x80 >> (y & 7)) else 0 for x in range(W)] for y in range(H)]


def sprite(name, invert=False):
    img = Image.open(SPRITES / f"blechy-{name}.png").convert("L")
    w, h = img.size
    px = img.load()
    return [[(1 if px[x, y] < 128 else 0) ^ invert for x in range(w)] for y in range(h)]


def blit(f, s, x0, y0, only_set=True, v=None):
    for y, row in enumerate(s):
        for x, on in enumerate(row):
            if on:
                put(f, x0 + x, y0 + y, 1 if v is None else v)
            elif not only_set:
                put(f, x0 + x, y0 + y, 0)


# ---- 5 x 7 font from data/script/font.mjs -----------------------------------------------------
def load_font():
    src = (ROOT / "data" / "script" / "font.mjs").read_text()
    rows = re.findall(r'"([0-9a-f]{10})"', src)
    return {chr(0x20 + i): [int(r[j:j + 2], 16) for j in range(0, 10, 2)] for i, r in enumerate(rows)}


FONT = load_font()
UMLAUT = {"ü": "u", "ä": "a", "ö": "o"}


def text(f, s, x, y, v=1):
    for ch in s:
        base = UMLAUT.get(ch, ch)
        cols = FONT.get(base, FONT["?"])
        for cx, col in enumerate(cols):
            for cy in range(7):
                if col >> cy & 1:
                    put(f, x + cx, y + cy, v)
        if ch in UMLAUT:                       # two dots over the lower-case letter
            put(f, x + 1, y, v)
            put(f, x + 3, y, v)
        x += 6
    return x


def text_width(s):
    return len(s) * 6 - 1


def impact(f, s, x, y, size, v=1):
    img = Image.new("L", (W, H), 0)
    ImageDraw.Draw(img).text((x, y), s, font=ImageFont.truetype(IMPACT, size), fill=255)
    px = img.load()
    for yy in range(H):
        for xx in range(W):
            if px[xx, yy] >= 128:
                f[yy][xx] = v


# ---- the BLECH eyes (positions measured from splash.bin) --------------------------------------
EYES = [(51, 15), (78, 15)]        # centres of the two sockets
PUPIL_TOP = 15


def eye_interior(f, cx, cy, v):
    for y in range(cy - 8, cy + 9):
        for x in range(cx - 8, cx + 9):
            if (x - cx) ** 2 + (y - cy) ** 2 <= 7.2 ** 2:
                put(f, x, y, v)


def pupils(f, dx, size=3, dy=0):
    for cx, _ in EYES:
        x0 = cx - 1 + dx
        rect(f, x0, PUPIL_TOP + dy, x0 + size - 1, PUPIL_TOP + dy + size - 1, 1)


def clear_pupils(f):
    for cx, cy in EYES:
        eye_interior(f, cx, cy, 0)


def closed_eyes(f):
    """Lids down: the open socket goes away, a thick sagging lid line with three lashes stays."""
    for cx, cy in EYES:
        rect(f, cx - 10, cy - 9, cx + 10, cy + 14, 1)      # socket and eye bags out, the dither around stays
        for x in range(cx - 7, cx + 8):
            y = cy + 2 + round((1 - ((x - cx) / 7) ** 2) * 3)
            rect(f, x, y, x, y + 1, 0)
        for lx, ly in ((-4, 7), (0, 8), (4, 7)):
            rect(f, cx + lx, cy + ly, cx + lx, cy + ly + 1, 0)


def happy_eyes(f):
    """Squeezed shut with joy: an upside-down U in each socket."""
    for cx, cy in EYES:
        eye_interior(f, cx, cy, 0)
        for x in range(cx - 5, cx + 6):
            y = cy + 2 - round((1 - ((x - cx) / 5) ** 2) * 5)
            rect(f, x, y, x, y + 1, 1)


# ---- start image and loader: BLECH turns into Blechy's nose -----------------------------------
# The eyes of the start image are Blechy's eyes. When the load begins the letters dissolve into his nose, the eyes and
# the underline stay where they are, and the underline is the line he takes in, from both ends towards the middle.
LINE_X0, LINE_X1, LINE_Y = 20, 107, 61      # the underline of BLECH (assets/blechy/splash.bin), rows 61 and 62
NOSTRILS = [(58, 50), (78, 50)]


def eyes(f, look=(0, 0), pupil=3):
    """Blechy's eye, scaled up from the sprite: dark socket, light eye, dark pupil, inside a thin light rim.
    The start image and the loader draw them alike, so they stay put when BLECH turns into Blechy."""
    for cx, cy in EYES:
        for y in range(cy - 11, cy + 12):
            for x in range(cx - 11, cx + 12):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if d <= 10.4 ** 2:
                    put(f, x, y, 0)
                if d <= 9.4 ** 2:
                    put(f, x, y, 1)
                if d <= 7.4 ** 2:
                    put(f, x, y, 0)
        if pupil <= 3:
            x0, y0 = cx - 1 + look[0], cy - 1 + look[1]
            rect(f, x0, y0, x0 + 2, y0 + 2, 1)
        else:                                               # the stare: a huge dark pupil with a light glint
            for y in range(cy - pupil, cy + pupil + 1):
                for x in range(cx - pupil, cx + pupil + 1):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= (pupil + 0.4) ** 2:
                        put(f, x, y, 1)
            rect(f, cx - 2, cy - 3, cx - 1, cy - 2, 0)


def start_blech():
    """The start image without the Kuhler's dither and the eye bags: Blechy's eyes, BLECH, underline."""
    f = splash()
    rect(f, 0, 0, W - 1, 32, 1)
    rect(f, 0, 33, 22, 59, 1)
    rect(f, 105, 33, W - 1, 59, 1)
    eyes(f)
    return f


# Blechy from tools/art/make_blechy.py, scaled so that his eyes land on the eyes of the start image: 2.25 wide (the eyes
# are 12 px apart in the sprite, 27 in the start image) and 1.4 high (he bends over the line, so he looks squat).
SX, SY, BX = 2.25, 1.4, 67


def X(dx):
    return BX + dx * SX


def Y(dy):
    return EYES[0][1] + (dy + 8) * SY


def ell(d, dx, dy, rx, ry, fill):
    d.ellipse([X(dx) - rx * SX, Y(dy) - ry * SY, X(dx) + rx * SX, Y(dy) + ry * SY], fill=fill)


def nose(f):
    """Blechy bent over the line, drawn like the sprite: dark body (the nose) on a light screen, light face patch,
    eye bags, brow, nostrils just above the line, a drip, stubble, sweat, the arms down to the table."""
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    ell(d, 0, 7, 13, 15, 0)
    ell(d, 0, 4, 15, 12, 0)
    ell(d, -7, -8, 8, 11, 0)
    ell(d, -2, -6, 11, 8, 255)                               # face patch
    for ex, ey in EYES:                                      # eye bags
        d.arc([ex - 8, ey + 3, ex + 8, ey + 13], 15, 165, fill=0)
        d.arc([ex - 7, ey + 6, ex + 7, ey + 15], 25, 155, fill=0)
    d.line([X(1), 3, X(9), 1], fill=0)                       # the brow, twitching up
    d.line([X(1), 4, X(9), 2], fill=0)
    for sx, sy in ((-9, 8), (0, 12), (9, 7), (-4, 13), (12, 2)):
        d.point((X(sx), Y(sy)), fill=255)                    # stubble
    d.line([X(-12), Y(3), 24, 57], fill=0)                   # arms down to the table, hands flat
    d.line([X(12), Y(3), 104, 57], fill=0)
    d.rectangle([20, 57, 27, 58], fill=0)
    d.rectangle([101, 57, 108, 58], fill=0)
    d.ellipse([X(-12) - 7, 6, X(-12) - 3, 10], fill=0)       # sweat
    d.polygon([(X(-12) - 6, 7), (X(-12) - 4, 7), (X(-12) - 5, 3)], fill=0)
    px = img.load()
    for y in range(H):
        for x in range(W):
            f[y][x] = 1 if px[x, y] < 128 else 0
    real_nose(f, top=(62, 67, 20), mid=(59, 70, 44), bulb=(64.5, 48, 8, 5), nostrils=((61, 51), (68, 51)))


def real_nose(f, top, mid, bulb, nostrils, outline_from=None):
    """The nose Blechy never had: light, outlined, from between the eyes down to a bulb with two nostrils, in front
    of the body. top and mid are (left x, right x, y) of the ridge, bulb is (cx, cy, rx, ry)."""
    m = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(top[0], top[2]), (top[1], top[2]), (mid[1], mid[2]), (mid[0], mid[2])], fill=1)
    cx, cy, rx, ry = bulb
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=1)
    mp = m.load()
    inside = lambda x, y: 0 <= x < W and 0 <= y < H and mp[x, y]
    edge_from = H if outline_from is None else outline_from     # no outline: the light ridge against the dark body is enough
    for y in range(H):
        for x in range(W):
            if inside(x, y):
                f[y][x] = 0
                if y >= edge_from and not all(inside(x + i, y + j) for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    f[y][x] = 1                              # outline
    for nx, ny in nostrils:
        rect(f, nx - 1, ny, nx, ny, 1)


NOSE_LENGTHS = {                                             # tip y of the bulb centre in the 56 x 56 sprite
    "kurz": dict(mid=(24, 30, 21), bulb=(27, 23, 4, 3), nostrils=((25, 25), (29, 25))),
    "mittel": dict(mid=(24, 30, 24), bulb=(27, 27, 4, 3), nostrils=((25, 29), (29, 29))),
    "lang": dict(mid=(24, 30, 28), bulb=(27, 31, 4, 3), nostrils=((25, 33), (29, 33))),
}


def stub_nose(g, nostril_row, x0=0, y0=0):
    """The sprite's own face patch, one pixel lower in the middle, with two nostrils: the smallest nose that reads."""
    rect(g, x0 + 24, y0 + 25, x0 + 28, y0 + 25, 0)
    put(g, x0 + 25, y0 + nostril_row, 1)
    put(g, x0 + 27, y0 + nostril_row, 1)


def small_blechy(nose=True, length="lang", pose="idle"):
    """The sprite with the nose, as a proposal for tools/art/make_blechy.py (56 x 56, set = dark)."""
    s = [[v for v in row] for row in sprite(pose)]
    g = blank(0)
    blit(g, s, 0, 0)
    if nose:
        real_nose(g, top=(25, 29, 16), **NOSE_LENGTHS[length])
    return [row[:56] for row in g[:56]]


def the_line(f, p):
    """What is left of the line: it shrinks from both ends towards the middle as the load goes on."""
    half = round((LINE_X1 - LINE_X0) / 2 * (1 - p))
    mid = (LINE_X0 + LINE_X1) // 2
    if half > 0:
        rect(f, mid - half, LINE_Y, mid + half, LINE_Y + 1, 1)
    return mid - half, mid + half


def dust(f, ends, frame):
    """A few grains on their way from the ends of the line up into the nostrils."""
    for (ex, nx) in ((ends[0], NOSTRILS[0][0]), (ends[1], NOSTRILS[1][0])):
        for k in (1, 2, 3):
            t = (k + (frame % 2) * 0.5) / 4
            put(f, round(ex + (nx - ex) * t), round(LINE_Y - 1 - (LINE_Y - 1 - NOSTRILS[0][1] - 3) * t), 1)


def loader(p, frame=0, word="Tanken"):
    f = blank(0)
    nose(f)
    ends = the_line(f, p)
    if p >= 1:
        eyes(f, pupil=5)
        text(f, "Drauf.", 127 - text_width("Drauf."), 1, 1)
    else:
        eyes(f, look=((-1, 1)[frame % 2], 4))              # looking down, the pupils shiver one pixel each frame
        dust(f, ends, frame)
        text(f, word, 127 - text_width(word), 1, 1)
    label = f"{round(p * 100)}%"
    text(f, label, 127 - text_width(label), 10, 1)
    return f


def dissolve(a, b, level):
    """From a to b over the 4 x 4 Bayer grid: at level n of 16 the pixels whose threshold is below n show b."""
    return [[b[y][x] if BAYER[(y % 4) * 4 + x % 4] < level else a[y][x] for x in range(W)] for y in range(H)]


# ---- power off --------------------------------------------------------------------------------
def goodbye(pose, lines=("Na dann,", "tschüss", "atze...")):
    f = blank(0)
    blit(f, sprite(pose), 4, 4)
    for i, line in enumerate(lines):
        text(f, line, 66, 17 + i * 11)
    return f


def fade(f, level):
    """Ordered dither towards dark: at level n of 16 every pixel whose threshold is below n is set."""
    g = copy(f)
    for y in range(H):
        for x in range(W):
            if BAYER[(y % 4) * 4 + x % 4] < level:
                g[y][x] = 1
    return g


def squash(f, rows):
    """The picture pressed into `rows` rows around the middle, like an old tube switching off."""
    g = blank(1)
    top = 32 - rows // 2
    for y in range(rows):
        src = f[min(H - 1, int((y + 0.5) * H / rows))]
        g[top + y] = src[:]
    return g


def line(width):
    g = blank(1)
    x0 = 64 - width // 2
    rect(g, x0, 31, x0 + width - 1, 32, 0)
    return g


def no_card():
    f = blank(0)
    blit(f, sprite("calm"), 4, 4)
    text(f, "Keine", 66, 17)
    text(f, "Karte,", 66, 28)
    text(f, "atze?", 66, 39)
    return f


# ---- layout 2 (19.10.): BLECH TRIBE on top, Blechy peeking over the line below --------------------
# 3 x 5 capitals for small type; one column of space between letters.
F3 = {
    "A": "111101111101101", "B": "110101110101110", "C": "111100100100111", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "111100101101111", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101111", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "110101101101101", "O": "111101101101111", "P": "111101111100100",
    "Q": "111101101111001", "R": "110101110101101", "S": "111100111001111", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111", "0": "111101101101111", "1": "010110010010111",
    "2": "111001111100111", "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001001010010", "8": "111101111101111", "9": "111101111001111",
    "%": "101001010100101", ".": "000000000000010", "_": "000000000000111", " ": "000000000000000",
    "'": "010010000000000",
    "!": "010010010000010",
}


def text3(f, s, x, y, v=0):
    for ch in s.upper():
        g = F3.get(ch, F3[" "])
        for i, b in enumerate(g):
            if b == "1":
                put(f, x + i % 3, y + i // 3, v)
        x += 4
    return x


def width3(s):
    return len(s) * 4 - 1


def tall(f, s, x, y, v=0, gap=3):
    """5 x 7 letters stretched to 5 x 14: the thin, tall TRIBE."""
    for ch in s:
        cols = FONT.get(ch, FONT["?"])
        for cx, col in enumerate(cols):
            for cy in range(7):
                if col >> cy & 1:
                    rect(f, x + cx, y + 2 * cy, x + cx, y + 2 * cy + 1, v)
        x += 5 + gap
    return x


TITLE_PNG = HERE / "blech-titel.png"           # the title as rendered on macOS, for machines without Impact


def blech_mask(box=(1, 1, 78, 29)):
    """BLECH in Impact, as large as fits the box. Returns a set of (x, y). Without Impact (not macOS) the title comes
    from blech-titel.png, which this function writes whenever Impact is there."""
    if not Path(IMPACT).exists():
        px = Image.open(TITLE_PNG).convert("L").load()
        return {(x, y) for y in range(H) for x in range(W) if px[x, y] < 128}
    x0, y0, x1, y1 = box
    for size in range(60, 10, -1):
        font = ImageFont.truetype(IMPACT, size)
        l, t, r, b = font.getbbox("BLECH")
        if r - l <= x1 - x0 and b - t <= y1 - y0:
            break
    img = Image.new("L", (W, H), 0)
    ImageDraw.Draw(img).text((x0 - l, y0 - t), "BLECH", font=font, fill=255)
    px = img.load()
    mask = {(x, y) for y in range(H) for x in range(W) if px[x, y] >= 128}
    out = Image.new("1", (W, H), 1)
    for x, y in mask:
        out.putpixel((x, y), 0)
    out.save(TITLE_PNG)
    return mask


BLECH = None


def lockup(f, p, words=("FEINSTES", "GELUMPE"), word_y=20):
    """BLECH fills from left to right with the load (hollow at 0, solid at 1), TRIBE and two words beside it."""
    global BLECH
    BLECH = BLECH or blech_mask()
    xs = [x for x, _ in BLECH]
    left, right = min(xs), max(xs)
    edge = left + (right - left + 1) * p
    for x, y in BLECH:
        rim = any((x + i, y + j) not in BLECH for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        k = (edge - x) * 4                                   # 4 dither steps over the last pixel column of the fill
        filled = x < edge - 1 or (x < edge + 3 and BAYER[(y % 4) * 4 + x % 4] < 16 - (x - edge + 1) * 4)
        if rim or filled:
            put(f, x, y, 0)
    tall(f, "TRIBE", 83, 2)
    for i, word in enumerate(words):
        text3(f, word, 83, word_y + i * 6)


# Three bands: dark top with BLECH TRIBE, a light stage with Blechy exactly as in the sprite, peeking over a dark wall
# like Kilroy, and the line lying on top of the wall. His nose hangs over the line.
STAGE = 32                                                    # first light row
WALL = 53                                                     # first dark row of the wall
HEAD_X = 4


def kilroy(f, rise, look=(0, 0), stare=False):
    """rise: sprite row that rests on the wall (25 = up, 17 = only the eyes over it)."""
    g = small_blechy(length="mittel")
    for ex, ey in [(21, 14), (33, 16)]:
        for y in range(ey - 2, ey + 3):
            for x in range(ex - 2, ex + 3):
                if (x - ex) ** 2 + (y - ey) ** 2 <= 6:
                    g[y][x] = 0
        if stare:
            for y in range(ey - 2, ey + 3):
                for x in range(ex - 2, ex + 3):
                    if (x - ex) ** 2 + (y - ey) ** 2 <= 5:
                        g[y][x] = 1
            g[ey - 1][ex - 1] = 0
        else:
            rect(g, ex - 1 + look[0], ey - 1 + look[1], ex + 1 + look[0], ey + 1 + look[1], 1)
    oy = WALL - 1 - rise
    for y in range(3, 56):
        for x in range(56):
            sy, sx = y + oy, x + HEAD_X
            if sy < STAGE:
                continue
            if y <= rise:
                put(f, sx, sy, g[y][x])
            elif rise >= 23 and 24 <= x <= 30 and y <= 30 and not g[y][x]:   # the nose hangs over the wall
                put(f, sx, sy, 0)
    for nx, ny in ((25, 29), (29, 29)):                       # nostrils of "mittel", if they show
        if rise >= 23 and ny > rise and ny + oy < H:
            put(f, nx + HEAD_X - 1, ny + oy, 1)
    for hx in (HEAD_X + 10, HEAD_X + 45):                     # fingers over the wall
        for k in (0, 2, 4):
            rect(f, hx + k - 2, WALL - 2, hx + k - 2, WALL - 1, 1)


def line2(f, p=0.0):
    rect(f, 0, STAGE, W - 1, WALL - 1, 0)


NOSE_X = HEAD_X + 27


def the_line2(f, p=0.0):
    """The line on the wall, from under his nose to the right; it gets shorter towards the nose as the load goes on."""
    end = NOSE_X + 6 + round((120 - NOSE_X - 6) * (1 - p))
    for x in range(NOSE_X + 6, end + 1):
        if f[WALL + 2][x]:
            put(f, x, WALL + 2, 0)


def start2():
    f = blank(1)
    lockup(f, 0.0)
    line2(f)
    kilroy(f, 18)
    the_line2(f)
    text3(f, "BY KUHLER_BUHLER", 126 - width3("BY KUHLER_BUHLER"), 58)
    return f


def loader2(p, frame=0, rise=25):
    f = blank(1)
    lockup(f, p, ("TANKEN", f"{round(p * 100)}%") if p < 1 else ("DRAUF.", "100%"))
    line2(f)
    if p >= 1:
        kilroy(f, rise, stare=True)
    else:
        kilroy(f, rise, look=((-1, 1)[frame % 2], 1))
    the_line2(f, p)
    text3(f, "BY KUHLER_BUHLER", 126 - width3("BY KUHLER_BUHLER"), 58)
    return f


# ---- output -----------------------------------------------------------------------------------
def save(name, f):
    (HERE / "png").mkdir(exist_ok=True)
    (HERE / "vorschau").mkdir(exist_ok=True)
    raw = Image.new("1", (W, H), 1)
    lcd = Image.new("RGB", (W, H), LCD_LIGHT)
    rp, lp = raw.load(), lcd.load()
    for y in range(H):
        for x in range(W):
            if f[y][x]:
                rp[x, y] = 0
                lp[x, y] = LCD_DARK
    raw.save(HERE / "png" / f"{name}.png")
    big = lcd.resize((W * 4, H * 4), Image.NEAREST)
    big.save(HERE / "vorschau" / f"{name}.png")
    return big


def strip(name, frames, labels=None):
    gap = 12
    imgs = [save(n, f) for n, f in frames]
    out = Image.new("RGB", (len(imgs) * (W * 4 + gap) - gap, H * 4), (14, 14, 16))
    for i, im in enumerate(imgs):
        out.paste(im, (i * (W * 4 + gap), 0))
    out.save(HERE / "vorschau" / f"{name}-strip.png")


def main():
    save("start-aktuell", splash())
    first = start_blech()
    target = loader(0.0, 0)
    strip("uebergang", [("start-blech", first), ("uebergang-1", dissolve(first, target, 5)),
                        ("uebergang-2", dissolve(first, target, 10)), ("uebergang-3", target)])
    strip("laden", [("laden-000", loader(0.0, 0)), ("laden-020", loader(0.2, 1)), ("laden-050", loader(0.5, 2)),
                    ("laden-080", loader(0.8, 3)), ("laden-100", loader(1.0))])

    strip("layout2-start", [("l2-start", start2()), ("l2-hoch-1", loader2(0.0, 0, 20)), ("l2-hoch-2", loader2(0.0, 1, 23)),
                            ("l2-laden-000", loader2(0.0, 0))])
    strip("layout2-laden", [("l2-laden-025", loader2(0.25, 1)), ("l2-laden-060", loader2(0.6, 0)),
                            ("l2-laden-090", loader2(0.9, 1)), ("l2-laden-100", loader2(1.0))])

    lines = ("Haus'te", "rin mein", "Akh")
    wave = [goodbye("wave-1", lines), goodbye("wave-2", lines)]
    off = [("aus-1-winken", wave[0]), ("aus-2-winken", wave[1]),
           ("aus-3-blende", fade(wave[1], 6)), ("aus-4-blende", fade(wave[1], 11)),
           ("aus-5-roehre", squash(fade(wave[1], 4), 8)), ("aus-6-strich", line(72)),
           ("aus-7-punkt", line(6)), ("aus-8-dunkel", blank(1))]
    strip("aus", off)
    save("aus-traurig-aktuell", goodbye("sad"))
    pair = blank(0)
    blit(pair, small_blechy(False), 8, 4)
    blit(pair, small_blechy(True), 66, 4)
    save("blechy-nase-vorher-nachher", pair)
    variants = [("ohne", lambda g: None), ("stups-a", lambda g: stub_nose(g, 24)), ("stups-b", lambda g: stub_nose(g, 25)),
                ("mittel", None)]
    sheet = Image.new("RGB", (4 * 64 * 4, 64 * 4), (14, 14, 16))
    for i, (name, draw) in enumerate(variants):
        g = blank(0)
        if draw is None:
            blit(g, small_blechy(length="mittel"), 4, 0)
        else:
            blit(g, small_blechy(nose=False), 4, 0)
            sub = [[g[y][x + 4] for x in range(56)] for y in range(56)]
            draw(sub)
            for y in range(56):
                for x in range(56):
                    g[y][x + 4] = sub[y][x]
        text(g, name, 32 - text_width(name) // 2, 56)
        tile = save(f"blechy-nase-{name}", [row[:64] + [0] * 64 for row in g])
        sheet.paste(tile.crop((0, 0, 64 * 4, 64 * 4)), (i * 64 * 4, 0))
    sheet.save(HERE / "vorschau" / "blechy-nase-laengen.png")
    save("extra-keine-karte", no_card())


if __name__ == "__main__":
    main()
