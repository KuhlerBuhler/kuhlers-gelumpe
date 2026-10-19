#!/usr/bin/env python3
"""Three 128 x 64, one-bit Blechy screen studies. No firmware is patched.

    python3 entwuerfe/design-1.3/geraet/anim.py
    python3 entwuerfe/design-1.3/geraet/anim.py --direction werkbank

render_frame() is pure: progress comes from the loader, pose from its caller.
The demo timeline is only an example, never a minimum boot duration. PNG black
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
TABLE_Y, DASH_Y = 55, 53
DASH_START, DASH_LENGTH, DASH_PITCH, DASH_COUNT = 49, 5, 8, 3
NOSE = (29, 23)                 # lower edge of the original face, no new bulb
SHOULDER = (40, 25)             # exactly the attachment in make_blechy.py
TUBE_VECTOR = (12, 12)
GRIP_FRACTION = 0.63

# Dark pupils inside the original light eyes. No jitter, no inverted face.
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
    pose: str = "contact"
    travel: float = 0.0
    started: bool = True
    done: bool = False

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


@lru_cache(maxsize=16)
def character(pupil, pose="idle"):
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
    # The detached eyebrow is outside the original face silhouette.
    for y in range(5, 10):
        for x in range(29, 39):
            if original.getpixel((x, y)) == DARK:
                d.point((x, y), fill=LIGHT)
    for ex, ey in ((21, 14), (33, 16 if pose == "idle" else 14)):
        d.ellipse((ex - 3, ey - 3, ex + 3, ey + 3), fill=LIGHT)
        for dx, dy in PUPILS[pupil]:
            d.point((ex + dx, ey + dy), fill=DARK)
        if pupil == 5:
            d.point((ex - 1, ey - 1), fill=LIGHT)
    return result


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


def tube_geometry(origin, away=0.0):
    """A rigid tube and its gripping hand share the same floating point axis.

    Two 9px arm segments connect the original shoulder to the hand. The outer
    elbow solution keeps the forearm clear of the face. Round only for drawing.
    """
    ox, oy = origin
    nose = (ox + NOSE[0], oy + NOSE[1])
    start = (nose[0] + 13 * away, nose[1] - 7 * away)
    tip = (start[0] + TUBE_VECTOR[0], start[1] + TUBE_VECTOR[1])
    grip = (start[0] + TUBE_VECTOR[0] * GRIP_FRACTION,
            start[1] + TUBE_VECTOR[1] * GRIP_FRACTION)
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


def percent(image, state, y=58, right=123, *, small=True):
    value = f"{state.percent}%"
    width = r.width3(value) if small else r.text_width(value)
    text(image, value, right-width+1, y, small=small)


def dash_cursor(progress):
    """Cursor follows fixed material. At a boundary it stays at the last line."""
    units = min(1.0, max(0.0, progress)) * DASH_COUNT
    index = min(DASH_COUNT - 1, max(0, math.ceil(units - 1e-9) - 1))
    fraction = min(1.0, max(0.0, units - index))
    consumed = min(DASH_LENGTH, math.floor(fraction * DASH_LENGTH + 1e-8))
    return index, consumed, DASH_START + index * DASH_PITCH + consumed


def draw_dashes(image, state):
    d = ImageDraw.Draw(image)
    for index in range(DASH_COUNT):
        fraction = min(1.0, max(0.0, state.value * DASH_COUNT - index))
        consumed = min(DASH_LENGTH, math.floor(fraction * DASH_LENGTH + 1e-8))
        start = DASH_START + index * DASH_PITCH
        if consumed < DASH_LENGTH:
            d.line((start + consumed, DASH_Y, start + DASH_LENGTH - 1, DASH_Y), fill=LIGHT)


def werkbank(state):
    image = blank()
    title(image, (4, 2, 72, 17))
    status(image, state, 86, 1)
    text(image, "FEINSTES", 86, 13, small=True)
    text(image, "GELUMPE", 86, 19, small=True)
    d = ImageDraw.Draw(image)
    d.line((4, TABLE_Y, 123, TABLE_Y), fill=LIGHT)
    # Chamfered tray and unconsumed dashes stay on the table.
    d.line((45, TABLE_Y, 45, TABLE_Y-3, 46, TABLE_Y-4), fill=LIGHT)
    d.line((76, TABLE_Y, 76, TABLE_Y-3, 75, TABLE_Y-4), fill=LIGHT)
    draw_dashes(image, state)
    _, consumed, cursor = dash_cursor(state.value)
    shift = cursor - DASH_START
    if consumed == DASH_LENGTH and not state.done:
        shift += round((DASH_PITCH - DASH_LENGTH) * state.travel)
    raised = state.pose in ("lift", "move", "rest")
    origin = (8 + shift, 18)
    actor(image, origin, state.pupil, crop=37)
    hx = origin[0] + 8
    for finger in (0, 2, 4):
        d.line((hx+finger, TABLE_Y-2, hx+finger, TABLE_Y), fill=LIGHT)
    d.line((origin[0]+16, origin[1]+25, hx+3, TABLE_Y-2), fill=LIGHT)
    draw_tube(image, tube_geometry(origin, away=0.5 if raised else 0.0))
    text(image, "KUHLER_BUHLER", 4, 58, small=True)
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


def render_frame(direction, progress, *, pose="contact", travel=0.0, started=True, done=False):
    """Return a fresh 128x64 mode-1 image. Time never increases progress here.

    pose: contact, lift, move or rest; travel: 0..1 across the empty gap after
    a finished line (Werkbank only). A caller may skip to current progress.
    Completion/handoff may interrupt the scene immediately.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown direction: {direction}")
    if pose not in ("contact", "lift", "move", "rest"):
        raise ValueError(f"Unknown pose: {pose}")
    if not math.isfinite(progress) or not math.isfinite(travel):
        raise ValueError("Progress and travel must be finite")
    state = State(progress, pose, min(1.0, max(0.0, travel)), started, done)
    return {"werkbank": werkbank, "typenschild": typenschild, "praegung": praegung}[direction](state)


def demo_timeline():
    cues = [Cue(State(0, "rest", started=False), 800), Cue(State(0), 320)]
    for index in range(DASH_COUNT):
        for step in range(1, DASH_LENGTH+1):
            progress = (index + step/DASH_LENGTH)/DASH_COUNT
            cues.append(Cue(State(min(progress, 0.99)), 280))
        if index < DASH_COUNT-1:
            boundary = (index+1)/DASH_COUNT
            cues.append(Cue(State(boundary, "lift"), 280))
            cues.append(Cue(State(boundary, "move", travel=1.0), 280))
            cues.append(Cue(State(boundary+1e-7), 280))
    cues.append(Cue(State(1, "rest", done=True), 1600))
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
    """Exactly 1000 ms for the device. GIF loop pause is added only by export."""
    waves = [goodbye_frame(0), goodbye_frame(1)]
    frames = [waves[0], waves[1], waves[0], waves[1]]
    durations = [150]*4
    for rows, duration in ((24, 80), (8, 70)):
        frame = blank()
        squeezed = waves[1].resize((W, rows), Image.Resampling.NEAREST)
        frame.paste(squeezed, (0, (H-rows)//2))
        frames.append(frame)
        durations.append(duration)
    for width, duration in ((88, 80), (24, 60), (2, 50)):
        frame = blank()
        ImageDraw.Draw(frame).line(((W-width)//2, 32, (W+width)//2-1, 32), fill=LIGHT)
        frames.append(frame)
        durations.append(duration)
    frames.append(blank())
    durations.append(60)
    return frames, durations


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


def metrics(frames, durations):
    """Compare distinct consecutive images, matching GIF frame coalescing."""
    unique_steps = []
    for frame in frames:
        if not unique_steps or frame.tobytes() != unique_steps[-1].tobytes():
            unique_steps.append(frame)
    changes, byte_changes, pages = [], [], []
    for previous, current in zip(unique_steps, unique_steps[1:]):
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
        "changed_pixels_max": max(changes, default=0),
        "changed_pixels_mean": round(sum(changes)/len(changes), 2) if changes else 0,
        "changed_bytes_max": max(byte_changes, default=0),
        "changed_pages_max": max(pages, default=0),
        "full_frame_bytes": 1024, "full_frame_table_bytes": unique_count*1024,
        "dynamic_byte_positions": len(dynamic),
        "base_plus_indexed_states_estimate_bytes": 1024+2*len(dynamic)+len(dynamic)*len(overlay_states),
        "estimate_excludes": "renderer code, timing, metadata, controller I/O; not ARM or hardware measurements",
    }


def export_sequence(name, frames, durations, preview_dir, raw_dir, *, palette="lcd", loop_pause=0):
    frame_dir = raw_dir / name
    frame_dir.mkdir(parents=True, exist_ok=True)
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
    return metrics(frames, durations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direction", choices=(*DIRECTIONS, "all"), default="all")
    parser.add_argument("--output", type=Path, default=HERE,
                        help="output root containing png/neu and vorschau/neu")
    parser.add_argument("--palette", choices=("lcd", "mono"), default="lcd")
    parser.add_argument("--pack", action="store_true", help="also write preview framebuffer snapshots, not patches")
    parser.add_argument("--controller-inverted", action="store_true", help="complement packed bits for display A7")
    args = parser.parse_args()
    preview_dir, raw_dir = args.output / "vorschau/neu", args.output / "png/neu"
    preview_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    timeline = demo_timeline()
    manifest = {"width": W, "height": H, "bit_depth": 1, "raw_png_black": "visibly dark",
                "preview_palette": args.palette, "device_timing_measured": False,
                "demo_timing_only": True, "directions": {}}
    directions = DIRECTIONS if args.direction == "all" else (args.direction,)
    for direction in directions:
        frames = [render_frame(direction, cue.state.progress, pose=cue.state.pose, travel=cue.state.travel,
                               started=cue.state.started, done=cue.state.done) for cue in timeline]
        durations = [cue.duration_ms for cue in timeline]
        result = export_sequence(direction, frames, durations, preview_dir, raw_dir, palette=args.palette)
        result["timeline"] = [{"frame": f"{i:03d}.png", "duration_ms": cue.duration_ms,
                               "progress": cue.state.value, "pose": cue.state.pose,
                               "travel": cue.state.travel, "done": cue.state.done,
                               "started": cue.state.started} for i, cue in enumerate(timeline)]
        if args.pack:
            for label, index in (("start", 0), ("mitte", len(frames)//2), ("ende", len(frames)-1)):
                for order in ("msb", "lsb"):
                    data = pack_frame(frames[index], bit_order=order, controller_inverted=args.controller_inverted)
                    (raw_dir / f"{direction}-{label}-{order}.bin").write_bytes(data)
            result["packed_controller_inverted"] = args.controller_inverted
        manifest["directions"][direction] = result
        print(f"{NAMES[direction]}: {result['unique_frames']} unique frames; "
              f"max {result['changed_pixels_max']} changed pixels, {result['changed_pages_max']} LCD pages")
    off_frames, off_durations = shutdown_timeline()
    manifest["shutdown"] = export_sequence("ausschalten", off_frames, off_durations, preview_dir, raw_dir,
                                           palette=args.palette, loop_pause=1400)
    manifest["shutdown"]["gif_only_loop_pause_ms"] = 1400
    manifest["shutdown"]["timeline_ms"] = off_durations
    (preview_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Previews: {preview_dir.relative_to(args.output)}; shutdown core: {sum(off_durations)} ms")


if __name__ == "__main__":
    main()
