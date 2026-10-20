#!/usr/bin/env python3
"""Blechy loading gesture at up to 20 FPS, 128 x 64, one bit. No firmware is patched.

    python3 entwuerfe/design-1.3/geraet/anim.py
    python3 entwuerfe/design-1.3/geraet/anim.py --direction werkbank

render_frame() is pure: progress comes from the loader, pose from its caller.
motion_timeline() holds progress constant while showing the recurring gesture. The
separate loading demo is only an example, never a minimum boot duration. PNG black
means visibly dark. pack_frame() handles controller inversion and the two
different vertical bit orders explicitly. Only Pillow is required.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import render as r

W, H = 128, 64
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIGHT, DARK = 255, 0
LCD_DARK, LCD_LIGHT = r.LCD_DARK, r.LCD_LIGHT
DIRECTIONS = ("werkbank", "typenschild", "praegung")
NAMES = {"werkbank": "Werkbank", "typenschild": "Typenschild", "praegung": "Prägung"}
TABLE_Y, DASH_Y = 55, 54          # the line lies on the table, bumps reach row 53
DASH_START = 49                 # tube tip in the draw pose at the left end
SWEEP, SWEEP_STEP = 48, 1       # the line is the bar: one pass from 0 to 100 percent
DASH_LENGTH = SWEEP + 1
BODY_X, BODY_Y = 8, 18
NOSE = (29, 23)                 # lower edge of the original face, no new bulb
SHOULDER = (40, 25)             # exactly the attachment in make_blechy.py
TUBE_VECTOR = (12, 12)
WORK_TUBE_VECTOR = (12, 9)       # 15px; reaches the line only in the lowered pose
GRIP_FRACTION = 0.63
FINALE_AT = 0.95
MAX_FPS = 20                     # a pixel needs about 50 ms on the device LCD to go dark
MIN_FRAME_MS = 1000 // MAX_FPS

# Dark pupils inside the original light eyes. No jitter, no inverted face.
EYES_CLOSED, EYES_LOOK, EYES_WIDE = -1, 1, 5
PUPILS = (
    ((0, 0),),
    ((0, 0), (1, 0), (0, 1), (1, 1)),
    ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)),
    tuple((x, y) for y in range(-1, 2) for x in range(-1, 2)),
    tuple((x, y) for y in range(-2, 3) for x in range(-2, 3) if x*x + y*y <= 4),
    tuple((x, y) for y in range(-2, 3) for x in range(-2, 3) if x*x + y*y <= 6),
)


@dataclass(frozen=True)
class State:
    progress: float
    pose: str = "draw"
    started: bool = True
    done: bool = False
    shift: int = 0               # body travel along the line, 0 to SWEEP
    eaten: int = 0               # pixels of the current line already drawn up

    @property
    def value(self):
        # 100 is a completion signal, not a rounded-up 99.5% estimate.
        return 1.0 if self.done else min(0.99, max(0.0, self.progress))

    @property
    def percent(self):
        return 100 if self.done else min(99, int(self.value * 100 + 1e-8))

    @property
    def pupil(self):
        return min(5, int(self.value * 6))

    @property
    def finale(self):
        """From FINALE_AT on the end plays (eyes torn open, line gone) while the percent runs on."""
        return self.done or (self.started and self.value >= FINALE_AT)

    @property
    def eyes(self):
        """Looks at you on the still splash, shut while drawing, wide open when done."""
        if self.done:
            return EYES_WIDE
        return EYES_LOOK if not self.started else EYES_CLOSED


@dataclass(frozen=True)
class Tube:
    nose: tuple[float, float]
    start: tuple[float, float]
    tip: tuple[float, float]
    grip: tuple[float, float]
    shoulder: tuple[float, float]
    elbow: tuple[float, float]


@dataclass(frozen=True)
class Cue:
    state: State
    duration_ms: int


@dataclass(frozen=True)
class MotionPose:
    drop: int
    tube_offset: tuple[int, int]
    duration_ms: int


# At most five updates per second, not five images in total. One-pixel head
# steps support the hand's action; the planted hand and body X never travel.
# The return reuses the approach drawings. Every visible hold is at least 200ms.
MOTION_POSES = {
    "ready": MotionPose(0, (3, -3), 200),
    "lower": MotionPose(1, (2, -2), 200),
    "reach": MotionPose(2, (1, -1), 200),
    "draw": MotionPose(3, (0, 0), 200),
    "lift": MotionPose(2, (1, -1), 200),
    "rise": MotionPose(1, (2, -2), 200),
    "settle": MotionPose(0, (2, -2), 400),
}


def pass_state(progress, done=False):
    """The loader's value picks the frame: Blechy stands where his tip has eaten the line.

    The display caller must rate-limit updates to MIN_FRAME_MS; the position snaps to
    SWEEP_STEP, so most loader ticks change nothing on the screen.
    """
    if not math.isfinite(progress):
        raise ValueError("Progress must be finite")
    if done:
        return State(1, "settle", done=True, shift=SWEEP, eaten=SWEEP + 1)
    value = min(0.99, max(0.0, progress))
    if value >= FINALE_AT:
        return State(value, "settle", shift=SWEEP, eaten=SWEEP + 1)
    shift = SWEEP_STEP * round(value * SWEEP / SWEEP_STEP)
    return State(value, "draw", shift=shift, eaten=shift)


def werkbank_origin(pose, shift=0):
    return BODY_X + shift, BODY_Y + MOTION_POSES[pose].drop


def point(p):
    return tuple(round(v) for v in p)


def blank():
    return Image.new("1", (W, H), DARK)


def text(image, value, x, y, *, small=False, tall=False):
    """Use the repository's two pixel fonts, never host fonts or antialiasing."""
    bits = r.blank(1)
    if tall:
        r.tall(bits, value, x, y)
    elif small:
        r.text3(bits, value, x, y)
    else:
        r.text(bits, value, x, y, 0)
    px = image.load()
    for yy in range(H):
        for xx in range(W):
            if bits[yy][xx] == 0:
                px[xx, yy] = LIGHT


@lru_cache(maxsize=8)
def title_mask(width, height):
    """Always read the checked-in title, including on macOS. Never rewrite it."""
    with Image.open(HERE / "blech-titel.png") as source:
        mask = ImageChops.invert(source.convert("L")).point(lambda v: 255 if v >= 128 else 0, "1")
    return mask.crop(mask.getbbox()).resize((width, height), Image.Resampling.NEAREST)


def title(image, box, fill=1.0):
    x, y, width, height = box
    mask = title_mask(width, height)
    if fill < 1.0:
        padded = Image.new("1", (width + 2, height + 2), DARK)
        padded.paste(mask, (1, 1))
        inner = padded.filter(ImageFilter.MinFilter(3)).crop((1, 1, width + 1, height + 1))
        outline = ImageChops.subtract(mask.convert("L"), inner.convert("L")).convert("1")
        boundary = math.floor(width * fill)
        if boundary:
            outline.paste(mask.crop((0, 0, boundary, height)), (0, 0))
        mask = outline
    image.paste(LIGHT, (x, y), mask)


@lru_cache(maxsize=1)
def body_mask():
    silhouette = Image.new("1", (56, 56), DARK)
    d = ImageDraw.Draw(silhouette)
    for box in ((15, 14, 41, 44), (13, 14, 43, 38), (13, 3, 29, 25), (15, 8, 37, 24)):
        d.ellipse(box, fill=LIGHT)
    return silhouette


def character(pupil, pose="idle"):
    """pupil: one PUPILS index or EYES_CLOSED for both eyes, or a look tuple
    (left, right, jitter_x, jitter_y, brow_up, veins) for the unhinged face."""
    look = pupil if isinstance(pupil, tuple) else (pupil, pupil, 0, 0, 0, False)
    return _character(look, pose)


@lru_cache(maxsize=64)
def _character(look, pose):
    """Original 56px sprite, original face polarity, one-pixel body rim.

    The body ellipses and open face patch follow tools/art/make_blechy.py. The
    face, brow and bags come directly from the checked-in sprite. Flood fill
    alone would lose its open face patch, which joins the outside.
    """
    with Image.open(r.SPRITES / f"blechy-{pose}.png") as source:
        original = source.convert("1")
    silhouette = body_mask()
    rim = ImageChops.subtract(
        silhouette.filter(ImageFilter.MaxFilter(3)).convert("L"), silhouette.convert("L")
    ).convert("1")
    face = ImageChops.logical_and(original, silhouette)
    result = ImageChops.logical_or(rim, face)
    d = ImageDraw.Draw(result)
    left, right, jx, jy, brow, veins = look
    # The detached eyebrow is outside the original face silhouette; brow lifts it for a twitch.
    for y in range(5, 10):
        for x in range(29, 39):
            if original.getpixel((x, y)) == DARK:
                d.point((x, y - brow), fill=LIGHT)
    for (ex, ey), pupil in zip(((21, 14), (33, 16 if pose == "idle" else 14)), (left, right)):
        d.ellipse((ex - 3, ey - 3, ex + 3, ey + 3), fill=LIGHT)
        if pupil == EYES_CLOSED:
            # A shut lid: one dark row, the corners a pixel higher.
            d.line((ex - 2, ey + 1, ex + 2, ey + 1), fill=DARK)
            d.point((ex - 3, ey), fill=DARK)
            d.point((ex + 3, ey), fill=DARK)
            continue
        for dx, dy in PUPILS[pupil]:
            dx, dy = dx + jx, dy + jy
            if dx * dx + dy * dy <= 9:          # a shaking pupil stays inside the eye
                d.point((ex + dx, ey + dy), fill=DARK)
        if pupil == 5:
            d.point((ex - 1 + jx, ey - 1 + jy), fill=LIGHT)
        elif veins:
            # Bloodshot: dark threads from the rim into the white.
            for vx, vy in ((-3, 1), (-2, 2), (3, -1), (2, -2), (1, 3)):
                d.point((ex + vx, ey + vy), fill=DARK)
    return result


character.cache_clear = _character.cache_clear


JITTER = ((0, 0), (1, 0), (0, 1), (-1, 0), (1, -1), (0, 0), (-1, 1), (0, -1))


def unhinged_look(state, t_ms):
    """Shut eyes while drawing; at 100 one huge and one tiny
    pupil that shake, the small eye bloodshot. Deterministic in t_ms."""
    if not state.started:
        return EYES_LOOK
    tick = t_ms // MIN_FRAME_MS
    if not state.finale:
        return EYES_CLOSED
    jx, jy = JITTER[tick % len(JITTER)]
    return (4, 0, jx, jy, 1 if tick % 6 < 3 else 0, True)


def still_splash():
    """The fixed splash before loading: Blechy where the pass starts, an oversized
    capsule in his hand, pouring the last of the line out in front of himself."""
    image = backdrop()
    d = ImageDraw.Draw(image)
    d.line((4, TABLE_Y, 123, TABLE_Y), fill=LIGHT)
    # The line is laid from the far end; the near part still trickles out of the capsule.
    laid = State(0, "draw", eaten=STILL_LAID_FROM)
    draw_dashes(image, laid)
    px = image.load()
    for x, y in STILL_HEAP:
        px[x, y] = LIGHT
    origin = werkbank_origin("ready")
    gesture = blank()
    # Looking down at the capsule, a bit off: one pupil low, one wandering.
    actor(gesture, origin, (1, 1, 1, 1, 0, False), crop=TABLE_Y - origin[1])
    g = ImageDraw.Draw(gesture)
    shoulder = (origin[0] + SHOULDER[0], origin[1] + SHOULDER[1])
    grip = STILL_GRIP
    elbow = (shoulder[0] + 8, shoulder[1] - 6)
    g.line((shoulder, elbow, grip), fill=DARK, width=3)
    g.line((shoulder, elbow, grip), fill=LIGHT, width=1)
    cap = capsule()
    gesture.paste(cap, (grip[0] - cap.width // 2, grip[1] - cap.height // 2), capsule_mask())
    gx, gy = grip
    g.rectangle((gx - 2, gy - 2, gx + 2, gy + 2), fill=DARK)
    g.rectangle((gx - 1, gy - 1, gx + 1, gy + 1), fill=LIGHT)
    g.point((gx - 1, gy), fill=DARK)
    gp = gesture.load()
    for x, y in STILL_STREAM:
        gp[x, y] = LIGHT
    coverage = blank()
    coverage.paste(body_mask().filter(ImageFilter.MaxFilter(3)), point(origin))
    coverage = ImageChops.logical_or(coverage, gesture.filter(ImageFilter.MaxFilter(3)))
    box = (0, 18, W, TABLE_Y)
    image.paste(gesture.crop(box), (0, 18), coverage.crop(box))
    text(image, TAGLINE, 4, 58, small=True)
    return image


STILL_GRIP = (66, 37)
STILL_LAID_FROM = 18                  # line pixels from DASH_START + 18 on are already down
STILL_STREAM = ((56, 44), (57, 45), (56, 46), (55, 47), (56, 48), (57, 49), (55, 50), (56, 51), (58, 47), (54, 49))
STILL_HEAP = ((54, 53), (55, 53), (56, 52), (57, 52), (58, 53), (59, 53),
              (51, 54), (52, 54), (53, 54), (54, 54), (55, 54), (56, 54), (57, 54), (58, 54), (59, 54),
              (60, 54), (61, 54), (62, 54), (63, 54), (64, 54), (65, 54), (66, 54))


@lru_cache(maxsize=1)
def capsule():
    """An oversized two-tone capsule, tilted so its open end points down-left: the lower
    half hollow (an outline, open at the end), the upper half solid, a dark seam between."""
    img = Image.new("1", (24, 17), DARK)
    d = ImageDraw.Draw(img)
    end, mid, top = (4, 13), (12, 8), (19, 4)
    d.line((end, top), fill=LIGHT, width=10)
    d.ellipse((top[0] - 5, top[1] - 5, top[0] + 5, top[1] + 5), fill=LIGHT)
    d.line(((end[0] - 3, end[1] + 2), mid), fill=DARK, width=5)     # hollow inside, open past the end
    d.line(((mid[0] - 2, mid[1] - 4), (mid[0] + 2, mid[1] + 3)), fill=DARK)   # seam
    return img.crop(img.getbbox())


@lru_cache(maxsize=1)
def capsule_mask():
    return capsule().filter(ImageFilter.MaxFilter(3))


def shake_lines(image, origin, t_ms):
    """Terror-sprite tremor marks beside the head, on every other frame."""
    if (t_ms // MIN_FRAME_MS) % 2:
        return
    d = ImageDraw.Draw(image)
    x, y = origin
    for a, b in (((x + 6, y + 6), (x + 4, y + 9)), ((x + 5, y + 13), (x + 3, y + 16)),
                 ((x + 46, y + 4), (x + 48, y + 7)), ((x + 47, y + 11), (x + 49, y + 14))):
        d.line((a, b), fill=LIGHT)


def actor(image, origin, pupil, *, crop=56, legs=False, sprite_pose="idle"):
    x, y = point(origin)
    body = character(pupil, sprite_pose).crop((0, 0, 56, crop))
    coverage = ImageChops.logical_or(body_mask().filter(ImageFilter.MaxFilter(3)),
                                    character(pupil, sprite_pose)).crop((0, 0, 56, crop))
    image.paste(body, (x, y), coverage)
    if legs:
        d = ImageDraw.Draw(image)
        for a, b in (((23, 40), (21, 52)), ((33, 40), (35, 52))):
            d.line((x+a[0], y+a[1], x+b[0], y+b[1]), fill=LIGHT)
        d.line((x+18, y+53, x+22, y+53), fill=LIGHT)
        d.line((x+33, y+53, x+37, y+53), fill=LIGHT)


def tube_geometry(origin, away=0.0, *, vector=TUBE_VECTOR, offset=None):
    """A rigid tube and its gripping hand share the same floating point axis.

    Two 9px arm segments connect the original shoulder to the hand. The outer
    elbow solution keeps the forearm clear of the face. Round only for drawing.
    """
    ox, oy = origin
    nose = (ox + NOSE[0], oy + NOSE[1])
    dx, dy = offset if offset is not None else (13 * away, -7 * away)
    start = (nose[0] + dx, nose[1] + dy)
    tip = (start[0] + vector[0], start[1] + vector[1])
    grip = (start[0] + vector[0] * GRIP_FRACTION,
            start[1] + vector[1] * GRIP_FRACTION)
    shoulder = (ox + SHOULDER[0], oy + SHOULDER[1])
    dx, dy = grip[0] - shoulder[0], grip[1] - shoulder[1]
    distance = math.hypot(dx, dy)
    if not 0 < distance <= 18:
        raise ValueError("Unreachable hand pose")
    middle = ((grip[0]+shoulder[0])/2, (grip[1]+shoulder[1])/2)
    offset = math.sqrt(9**2 - (distance/2)**2)
    elbows = [(middle[0]+sign*dy/distance*offset,
               middle[1]-sign*dx/distance*offset) for sign in (-1, 1)]
    elbow = max(elbows, key=lambda p: p[0])
    return Tube(nose, start, tip, grip, shoulder, elbow)


@lru_cache(maxsize=256)
def werkbank_tube(pose, shift=0):
    return tube_geometry(werkbank_origin(pose, shift), vector=WORK_TUBE_VECTOR,
                         offset=MOTION_POSES[pose].tube_offset)


def draw_tube(image, geometry):
    d = ImageDraw.Draw(image)
    shoulder, elbow, grip = map(point, (geometry.shoulder, geometry.elbow, geometry.grip))
    d.line((shoulder, elbow, grip), fill=DARK, width=3)
    d.line((shoulder, elbow, grip), fill=LIGHT, width=1)
    # Explicit dark clearance, never XOR: the straw remains a single object.
    d.line((point(geometry.start), point(geometry.tip)), fill=DARK, width=4)
    d.line((point(geometry.start), point(geometry.tip)), fill=LIGHT, width=2)
    if geometry.start == geometry.nose:
        d.point(point(geometry.nose), fill=DARK)  # small nostril, no projecting nose
    gx, gy = grip
    d.rectangle((gx-2, gy-2, gx+2, gy+2), fill=DARK)
    d.rectangle((gx-1, gy-1, gx+1, gy+1), fill=LIGHT)
    d.point((gx-2, gy-2), fill=LIGHT)
    d.point((gx+2, gy+2), fill=LIGHT)
    d.point((gx-1, gy), fill=DARK)        # finger notch, not a detached fist


def status(image, state, x, y, *, small=False, tall=False):
    word = "LAEUFT" if state.done else "LADEN" if state.started and state.value >= 0.18 else "TRIBE"
    text(image, word, x, y, small=small, tall=tall)


TAGLINE = "MEINE ELECTRIBE ROOCHT BLECH!"


def status_line(state):
    """Footer text; the firmware fills in what it is doing."""
    return "FERTIG" if state.done else "LADE SAMPLES..."


WORDMARK_SHIFT = 0                # make_wordmark() already centres it
IMPACT = Path("/System/Library/Fonts/Supplemental/Impact.ttf")


def make_wordmark():
    """Write blechtribe-titel.png: Impact stretched to 118 x 15 at (4, 2), with a
    dithered shadow 2 px right and down, kept clear of the letters by one pixel.
    Needs Impact (macOS); everyone else reads the checked-in PNG."""
    from PIL import ImageFont
    for size in range(40, 8, -1):
        font = ImageFont.truetype(str(IMPACT), size)
        l, t, rr, b = font.getbbox("BLECHTRIBE")
        if b - t <= 15:
            break
    glyphs = Image.new("L", (rr - l, b - t), 0)
    ImageDraw.Draw(glyphs).text((-l, -t), "BLECHTRIBE", font=font, fill=255)
    glyphs = glyphs.resize((118, b - t), Image.Resampling.NEAREST).point(lambda v: 255 if v >= 128 else 0, "1")
    letters = blank()
    letters.paste(glyphs, (4, 2))
    halo = letters.filter(ImageFilter.MaxFilter(3))
    shadow = ImageChops.offset(letters, 2, 2)
    out = letters.copy()
    po, ps, ph = out.load(), shadow.load(), halo.load()
    for y in range(H):
        for x in range(W):
            if ps[x, y] and not ph[x, y] and (x + y) % 2 == 0:
                po[x, y] = LIGHT
    ImageChops.invert(out.convert("L")).convert("1").save(HERE / "blechtribe-titel.png")


@lru_cache(maxsize=1)
def wordmark():
    """BLECHTRIBE with its dithered shadow, read from the checked-in PNG (black = lit)."""
    with Image.open(HERE / "blechtribe-titel.png") as source:
        return ImageChops.invert(source.convert("L")).point(lambda v: 255 if v >= 128 else 0, "1")


def percent(image, state, y=58, right=123, *, small=True):
    value = f"{state.percent}%"
    width = r.width3(value) if small else r.text_width(value)
    text(image, value, right-width+1, y, small=small)


def draw_dashes(image, state):
    """One line per loop. Blechy draws it up from the left, the tip eats it.

    The line is a gesture, not the progress bar: percent and pupils carry the
    loader's value. Done shows no line.
    """
    if state.finale:
        return
    px = image.load()
    for x in range(DASH_START + state.eaten, DASH_START + SWEEP + 1):
        for k in range(LUMPS[x - DASH_START] + 1):
            px[x, DASH_Y - k] = LIGHT


# Height above the base row per column (from DASH_START): uneven lumps, a few two pixels high, no ruler.
LUMPS = tuple(int(c) for c in "0111001100012210001110011221000110001221100011100")

BAYER4 = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)
BAND_WIDTH, BAND_TOP, BAND_BOTTOM = 14, 0, 53


def draw_bands(image):
    """Static dither bands at both sides, as in the app background (bandDensity in site/design/bg.js):
    dots on a 2 pixel pitch, denser towards the edge. Drawn first, everything else covers it."""
    px = image.load()
    for y in range(BAND_TOP, BAND_BOTTOM, 2):
        for x in range(0, W, 2):
            edge = min(x, W - 1 - x)
            if edge >= BAND_WIDTH:
                continue
            density = (1 - edge / BAND_WIDTH) ** 1.4 * 0.9
            if density > (BAYER4[((y >> 1) & 3) * 4 + ((x >> 1) & 3)] + 0.5) / 16:
                px[x, y] = LIGHT


def backdrop():
    """Bands to the very top, kept a pixel clear of the wordmark and its shadow."""
    image = blank()
    draw_bands(image)
    clear = blank()
    clear.paste(LIGHT, (WORDMARK_SHIFT, 0), wordmark())
    image = ImageChops.subtract(image.convert("L"), clear.filter(ImageFilter.MaxFilter(3)).convert("L")).convert("1")
    image.paste(LIGHT, (WORDMARK_SHIFT, 0), wordmark())
    return image


def werkbank(state, t_ms=0):
    if not state.started:
        return still_splash()
    image = backdrop()
    d = ImageDraw.Draw(image)
    d.line((4, TABLE_Y, 123, TABLE_Y), fill=LIGHT)
    # Chamfered tray and material stay at the same screen location.
    draw_dashes(image, state)
    pose = "settle" if state.finale else state.pose
    shift = SWEEP if state.finale else state.shift
    origin = werkbank_origin(pose, shift)
    # The figure dips behind the fixed table. Clip the complete arm/figure
    # layer, not just the body, so no pose can alter the edge or footer.
    gesture = blank()
    actor(gesture, origin, unhinged_look(state, t_ms), crop=TABLE_Y-origin[1])
    if state.finale:
        shake_lines(gesture, origin, t_ms)
    draw_tube(gesture, werkbank_tube(pose, shift))
    # Opaque body coverage keeps the tray from showing through the dark body.
    coverage = blank()
    coverage.paste(body_mask().filter(ImageFilter.MaxFilter(3)), point(origin))
    coverage = ImageChops.logical_or(coverage, gesture)
    box = (0, 20, W, TABLE_Y)
    image.paste(gesture.crop(box), (0, 20), coverage.crop(box))
    text(image, status_line(state), 4, 58, small=True)
    percent(image, state)
    return image


def progress_ticks(image, progress, x, y, count=8, pitch=7):
    d = ImageDraw.Draw(image)
    filled = min(count, math.floor(progress * count + 1e-8))
    for i in range(count):
        left = x + i * pitch
        if i < filled:
            d.rectangle((left, y, left+4, y+3), fill=LIGHT)
        else:
            d.line((left, y+3, left+4, y+3), fill=LIGHT)


def typenschild(state):
    image = blank()
    origin = (0, 3)
    actor(image, origin, state.pupil, legs=True)
    d = ImageDraw.Draw(image)
    d.line((16, 28, 9, 37), fill=LIGHT)
    # Still, clearly held straw. No pretend consumption unrelated to the bar.
    draw_tube(image, tube_geometry(origin, away=1.0))
    title(image, (60, 7, 64, 23))
    status(image, state, 62, 35)
    progress_ticks(image, state.value, 62, 47, count=9, pitch=7)
    text(image, "BLECH 1.3", 4, 58, small=True)
    percent(image, state, y=57, small=False)
    return image


def praegung(state):
    image = blank()
    origin = (7, -1)
    actor(image, origin, state.pupil, crop=34)
    d = ImageDraw.Draw(image)
    d.line((23, 24, 17, 32), fill=LIGHT)
    for finger in (0, 2, 4):
        d.line((15+finger, 31, 15+finger, 33), fill=LIGHT)
    draw_tube(image, tube_geometry(origin, away=1.0))
    status(image, state, 82, 3, tall=True)
    text(image, "FEINSTES", 82, 22, small=True)
    text(image, "GELUMPE", 82, 28, small=True)
    d.line((4, 34, 123, 34), fill=LIGHT)
    title(image, (4, 38, 89, 23), fill=state.value)
    percent(image, state, y=49, small=False)
    return image


def render_frame(direction, progress, *, pose="draw", started=True, done=False, shift=0, eaten=0, t_ms=0):
    """Return a fresh 128x64 mode-1 image. Time never increases progress here.

    pose: one of MOTION_POSES. There is no continuous travel parameter and
    progress never relocates the figure. Completion may interrupt any pose.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown direction: {direction}")
    if pose not in MOTION_POSES:
        raise ValueError(f"Unknown pose: {pose}")
    if not math.isfinite(progress):
        raise ValueError("Progress must be finite")
    state = State(progress, pose, started, done, shift, eaten)
    if direction == "werkbank":
        return werkbank(state, t_ms)
    return {"typenschild": typenschild, "praegung": praegung}[direction](state)


def demo_timeline():
    """0 to 100 percent in one pass at <=20 FPS: set the tube, draw the line, done.

    Example pacing only. The real loader decides the time, pass_state() the frame.
    """
    cues = [Cue(pass_state(i / 100), MIN_FRAME_MS) for i in range(0, 100, 2)]
    cues += [Cue(pass_state(0.99), MIN_FRAME_MS)] * 8
    cues += [Cue(pass_state(1, done=True), MIN_FRAME_MS)] * 16
    return cues


def percent_timeline():
    """Every percent from 0 to 99 as its own 200ms frame, then done: what each loader value shows."""
    cues = [Cue(pass_state(p / 100), 200) for p in range(100)]
    cues += [
             Cue(pass_state(1, done=True), 1200)]
    return cues


def motion_timeline():
    """The same single pass; kept so the review page keeps its second slot."""
    return demo_timeline()


def layout_timeline():
    """Keep the two earlier layout studies reproducible as review references."""
    cues = [Cue(State(0, "ready", started=False), 800), Cue(State(0), 320)]
    for index in range(3):
        for step in range(1, 6):
            cues.append(Cue(State(min((index + step/5)/3, 0.99)), 280))
        if index < 2:
            boundary = (index+1)/3
            cues.extend((Cue(State(boundary, "lift"), 280),
                         Cue(State(boundary, "lower"), 280),
                         Cue(State(boundary+1e-7), 280)))
    cues.append(Cue(State(1, "settle", done=True), 1600))
    return cues


def goodbye_frame(pose):
    image = blank()
    origin = (3, 4)
    actor(image, origin, 1, legs=True, sprite_pose="calm")
    d = ImageDraw.Draw(image)
    d.line((19, 29, 11, 36), fill=LIGHT)
    wrist = (origin[0] + (45 if pose == 0 else 49), origin[1] + 13)
    d.line((origin[0]+40, origin[1]+25, *wrist), fill=LIGHT)
    wx, wy = wrist
    d.rectangle((wx-1, wy-3, wx+1, wy-1), fill=LIGHT)
    tilt = -1 if pose == 0 else 1
    for k in (-1, 0, 1):
        d.line((wx+k, wy-4, wx+k+tilt*(k+2)//2, wy-8), fill=LIGHT)
    for i, line in enumerate(("Haus'te", "rin mein", "Akh")):
        text(image, line, 65, 16+i*11)
    return image


def shutdown_timeline():
    """1000 ms, five pictures of 200 ms. GIF loop pause is added only by export."""
    waves = [goodbye_frame(0), goodbye_frame(1)]
    squeezed = blank()
    squeezed.paste(waves[1].resize((W, 16), Image.Resampling.NEAREST), (0, 24))
    line = blank()
    ImageDraw.Draw(line).line((52, 32, 75, 32), fill=LIGHT)
    return [*waves, squeezed, line, blank()], [200]*5


def pack_frame(frame, *, bit_order="lsb", controller_inverted=False):
    """1024 bytes, page major. 'msb' = splash.bin, 'lsb' = display RAM.

    The visible image is canonical. An A7-inverted controller needs its
    complement once, not an inverted picture inverted a second time.
    """
    if frame.mode != "1" or frame.size != (W, H):
        raise ValueError("Expected a 128x64 mode-1 image")
    if bit_order not in ("lsb", "msb"):
        raise ValueError("bit_order must be lsb or msb")
    result = bytearray(1024)
    px = frame.load()
    for y in range(H):
        bit = 1 << ((y & 7) if bit_order == "lsb" else 7-(y & 7))
        for x in range(W):
            if (px[x, y] == DARK) ^ controller_inverted:
                result[(y//8)*W+x] |= bit
    return bytes(result)


def unpack_frame(data, *, bit_order="lsb", controller_inverted=False):
    if len(data) != 1024 or bit_order not in ("lsb", "msb"):
        raise ValueError("Expected 1024 bytes and a valid bit order")
    image = blank()
    px = image.load()
    for y in range(H):
        bit = 1 << ((y & 7) if bit_order == "lsb" else 7-(y & 7))
        for x in range(W):
            dark = bool(data[(y//8)*W+x] & bit) ^ controller_inverted
            px[x, y] = DARK if dark else LIGHT
    return image


def preview(frame, scale=4, palette="lcd"):
    colors = ((0, 0, 0), (255, 255, 255)) if palette == "mono" else (LCD_DARK, LCD_LIGHT)
    image = Image.new("P", (W, H))
    image.putpalette(list(colors[0])+list(colors[1])+[0, 0, 0]*254)
    image.putdata([int(value != 0) for value in frame.convert("L").tobytes()])
    return image.resize((W*scale, H*scale), Image.Resampling.NEAREST)


def metrics(frames, durations, *, include_loop=False):
    """Compare distinct images; recurring motion also counts last-to-first."""
    unique_steps = []
    for frame in frames:
        if not unique_steps or frame.tobytes() != unique_steps[-1].tobytes():
            unique_steps.append(frame)
    changes, byte_changes, pages = [], [], []
    pairs = list(zip(unique_steps, unique_steps[1:]))
    if include_loop and len(unique_steps) > 1:
        pairs.append((unique_steps[-1], unique_steps[0]))
    for previous, current in pairs:
        changes.append(sum(a != b for a, b in zip(previous.convert("L").tobytes(),
                                                 current.convert("L").tobytes())))
        a, b = pack_frame(previous), pack_frame(current)
        touched = [i for i, (aa, bb) in enumerate(zip(a, b)) if aa != bb]
        byte_changes.append(len(touched))
        pages.append(len({i//128 for i in touched}))
    packed = [pack_frame(f) for f in frames]
    dynamic = [i for i in range(1024) if any(p[i] != packed[0][i] for p in packed[1:])]
    overlay_states = {bytes(p[i] for i in dynamic) for p in packed}
    unique_count = len({f.tobytes() for f in frames})
    return {
        "logical_frames": len(frames), "gif_frames": len(unique_steps),
        "unique_frames": unique_count, "duration_ms": sum(durations),
        "includes_loop_transition": include_loop,
        "minimum_frame_duration_ms": min(durations),
        "maximum_update_fps": round(1000/min(durations), 3),
        "changed_pixels_max": max(changes, default=0),
        "changed_pixels_mean": round(sum(changes)/len(changes), 2) if changes else 0,
        "changed_bytes_max": max(byte_changes, default=0),
        "changed_pages_max": max(pages, default=0),
        "full_frame_bytes": 1024, "full_frame_table_bytes": unique_count*1024,
        "dynamic_byte_positions": len(dynamic),
        "base_plus_indexed_states_estimate_bytes": 1024+2*len(dynamic)+len(dynamic)*len(overlay_states),
        "estimate_excludes": "renderer code, timing, metadata, controller I/O; not ARM or hardware measurements",
    }


def export_sequence(name, frames, durations, preview_dir, raw_dir, *, palette="lcd", loop_pause=0,
                    include_loop=False):
    if not frames or len(frames) != len(durations):
        raise ValueError("Every frame must have one duration")
    if any(duration < MIN_FRAME_MS for duration in durations):
        raise ValueError(f"LCD limit: every frame must last at least {MIN_FRAME_MS}ms ({MAX_FPS} FPS)")
    frame_dir = raw_dir / name
    frame_dir.mkdir(parents=True, exist_ok=True)
    # Remove only this renderer's numbered frames left over from a longer take.
    for previous in frame_dir.glob("[0-9][0-9][0-9].png"):
        previous.unlink()
    for i, frame in enumerate(frames):
        frame.save(frame_dir / f"{i:03d}.png")
    gif_durations = durations.copy()
    gif_durations[-1] += loop_pause
    for scale, suffix in ((1, "-1x"), (4, "")):
        images = [preview(f, scale, palette) for f in frames]
        images[0].save(preview_dir / f"{name}{suffix}.gif", save_all=True,
                       append_images=images[1:], duration=gif_durations,
                       loop=0, optimize=False, disposal=1)
    indices = sorted({0, len(frames)//4, len(frames)//2, 3*len(frames)//4, len(frames)-1})
    strip = Image.new("RGB", (len(indices)*(W*4+12)-12, H*4), LCD_DARK)
    for column, index in enumerate(indices):
        strip.paste(preview(frames[index], 4, palette).convert("RGB"), (column*(W*4+12), 0))
    strip.save(preview_dir / f"{name}-strip.png")
    for label, index in (("start", 0), ("mitte", len(frames)//2), ("ende", len(frames)-1)):
        frames[index].save(raw_dir / f"{name}-{label}.png")
        preview(frames[index], 4, palette).save(preview_dir / f"{name}-{label}.png")
    return metrics(frames, durations, include_loop=include_loop)


def sequence_frames(direction, timeline):
    frames, clock = [], 0
    for cue in timeline:
        # The still splash is the firmware's fixed picture: no star time before loading starts.
        t = clock if cue.state.started else 0
        frames.append(render_frame(direction, cue.state.progress, pose=cue.state.pose,
                                   started=cue.state.started, done=cue.state.done,
                                   shift=cue.state.shift, eaten=cue.state.eaten, t_ms=t))
        clock += cue.duration_ms
    return frames


def timeline_metadata(timeline):
    return [{"frame": f"{i:03d}.png", "duration_ms": cue.duration_ms,
             "progress": cue.state.value, "pose": cue.state.pose,
             "done": cue.state.done, "started": cue.state.started,
             "shift": cue.state.shift, "eaten": cue.state.eaten}
            for i, cue in enumerate(timeline)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direction", choices=(*DIRECTIONS, "all"), default="all")
    parser.add_argument("--output", type=Path, default=HERE,
                        help="output root containing png/neu and vorschau/neu")
    parser.add_argument("--palette", choices=("lcd", "mono"), default="lcd")
    parser.add_argument("--pack", action="store_true", help="also write preview framebuffer snapshots, not patches")
    parser.add_argument("--wordmark", action="store_true", help="rewrite blechtribe-titel.png from Impact first")
    parser.add_argument("--controller-inverted", action="store_true", help="complement packed bits for display A7")
    args = parser.parse_args()
    if args.wordmark:
        make_wordmark()
        wordmark.cache_clear()
    preview_dir, raw_dir = args.output / "vorschau/neu", args.output / "png/neu"
    preview_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"width": W, "height": H, "bit_depth": 1, "raw_png_black": "visibly dark",
                "preview_palette": args.palette, "device_timing_measured": False,
                "demo_timing_only": True, "maximum_fps": MAX_FPS,
                "motion_steps": len(MOTION_POSES), "directions": {}}
    directions = DIRECTIONS if args.direction == "all" else (args.direction,)
    for direction in directions:
        timeline = demo_timeline() if direction == "werkbank" else layout_timeline()
        frames = sequence_frames(direction, timeline)
        durations = [cue.duration_ms for cue in timeline]
        result = export_sequence(direction, frames, durations, preview_dir, raw_dir, palette=args.palette)
        result["kind"] = ("loading example at up to 20 FPS"
                          if direction == "werkbank" else "earlier layout study")
        result["timeline"] = timeline_metadata(timeline)
        if direction == "werkbank":
            motion = motion_timeline()
            motion_frames = sequence_frames(direction, motion)
            loop_result = export_sequence("werkbank-loop", motion_frames,
                                          [cue.duration_ms for cue in motion], preview_dir, raw_dir,
                                          palette=args.palette, include_loop=True)
            loop_result["kind"] = "same single pass as werkbank"
            loop_result["timeline"] = timeline_metadata(motion)
            result["motion_loop"] = loop_result
            every = percent_timeline()
            every_result = export_sequence("werkbank-prozent", sequence_frames(direction, every),
                                           [cue.duration_ms for cue in every], preview_dir, raw_dir,
                                           palette=args.palette)
            every_result["kind"] = "one frame per percent, 200ms each"
            result["every_percent"] = every_result
            # Stable, explicit links for reviewing the corrected frame rate.
            for stem in ("werkbank", "werkbank-loop"):
                (preview_dir / f"{stem}-5fps.gif").write_bytes((preview_dir / f"{stem}.gif").read_bytes())
            if args.pack:
                for order in ("msb", "lsb"):
                    data = b"".join(pack_frame(frame, bit_order=order,
                                               controller_inverted=args.controller_inverted)
                                    for frame in motion_frames)
                    (raw_dir / f"werkbank-loop-{order}.bin").write_bytes(data)
        if args.pack:
            for label, index in (("start", 0), ("mitte", len(frames)//2), ("ende", len(frames)-1)):
                for order in ("msb", "lsb"):
                    data = pack_frame(frames[index], bit_order=order, controller_inverted=args.controller_inverted)
                    (raw_dir / f"{direction}-{label}-{order}.bin").write_bytes(data)
            result["packed_controller_inverted"] = args.controller_inverted
        manifest["directions"][direction] = result
        print(f"{NAMES[direction]}: {result['unique_frames']} unique frames; "
              f"max {result['changed_pixels_max']} changed pixels, {result['changed_pages_max']} LCD pages")
    still = still_splash()
    still.save(raw_dir / "startbild.png")
    preview(still, 4, args.palette).save(preview_dir / "startbild.png")
    if args.pack:
        for order in ("msb", "lsb"):
            (raw_dir / f"startbild-{order}.bin").write_bytes(
                pack_frame(still, bit_order=order, controller_inverted=args.controller_inverted))
    off_frames, off_durations = shutdown_timeline()
    manifest["shutdown"] = export_sequence("ausschalten", off_frames, off_durations, preview_dir, raw_dir,
                                           palette=args.palette, loop_pause=1400)
    manifest["shutdown"]["gif_only_loop_pause_ms"] = 1400
    manifest["shutdown"]["timeline_ms"] = off_durations
    (preview_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Previews: {preview_dir.relative_to(args.output)}; shutdown core: {sum(off_durations)} ms")


if __name__ == "__main__":
    main()
