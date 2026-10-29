#!/usr/bin/env python3
"""Writes the device pictures of the chosen design into assets/blechy:

    splash.bin, splash.png, splash.json   the fixed start image (Blechy tipping the tube), as the display shows it
                                          before DISPLAY INVERT is sent: a set bit is dark
    loading.bin                           the parts of the loading animation (base, line, figure, digits, finale)
    loading.blla                          the loading animation in the firmware's format (docs/hintergrund/ladeanimation.md),
                                          made from those parts: the default the patch writes (tools/patch/load_bar.py)

    python3 tools/art/loading/firmware_assets.py

Every picture comes from anim.py, the renderer of the previews. Before writing, the overlay's way of putting a frame
together (load_bar.compose_reference) is checked against the renderer for every percent and every finale picture, and
so is every picture of loading.blla. Encoding goes through src/loading-anim.mjs, so node is needed.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import anim
import render as r

ROOT = anim.ROOT
sys.path.insert(0, str(ROOT / "tools" / "patch"))
import load_bar as lb  # noqa: E402
import loading_anim  # noqa: E402

ASSETS = ROOT / "assets" / "blechy"


def lit(image):
    """Frame buffer order, a set bit for every lit pixel (the reversed display shows it light)."""
    return anim.pack_frame(image, bit_order="lsb", controller_inverted=True)


def frame(pct, done=False, tick=0):
    state = anim.pass_state(1, done=True) if done else anim.pass_state(pct / 100)
    return anim.render_frame("werkbank", state.progress, pose=state.pose, started=True, done=state.done,
                             shift=state.shift, eaten=state.eaten, t_ms=tick * anim.MIN_FRAME_MS)


def base_image():
    image = anim.backdrop()
    ImageDraw.Draw(image).line((4, anim.TABLE_Y, 123, anim.TABLE_Y), fill=anim.LIGHT)
    anim.text(image, "LADE SAMPLES...", 4, 58, small=True)
    return image


def figure():
    """The drawing pose at shift 0 as anim.werkbank pastes it: the layer and its opaque coverage, rows 20 to 54."""
    state = anim.pass_state(0)
    origin = anim.werkbank_origin("draw", 0)
    gesture = anim.blank()
    anim.actor(gesture, origin, anim.unhinged_look(state, 0), crop=anim.TABLE_Y - origin[1])
    anim.draw_tube(gesture, anim.werkbank_tube("draw", 0))
    coverage = anim.blank()
    coverage.paste(anim.body_mask().filter(ImageFilter.MaxFilter(3)), anim.point(origin))
    coverage = ImageChops.logical_or(coverage, gesture)
    keep = anim.blank()
    keep.paste(anim.LIGHT, (0, 20, anim.W, anim.TABLE_Y))
    coverage = ImageChops.logical_and(coverage, keep)
    bits, mask = lit(ImageChops.logical_and(gesture, coverage)), lit(coverage)
    cols = [x for x in range(128) if any(mask[(lb.SPRITE_PAGE + p) * 128 + x] for p in range(lb.SPRITE_PAGES))]
    x0, w = cols[0], cols[-1] - cols[0] + 1
    pick = lambda data: b"".join(data[(lb.SPRITE_PAGE + p) * 128 + x0:(lb.SPRITE_PAGE + p) * 128 + x0 + w]
                                 for p in range(lb.SPRITE_PAGES))
    return x0, w, pick(bits), pick(mask)


def finale(base):
    shots = [lit(frame(lb.FINALE_AT, tick=t)) for t in range(lb.TICKS_N)]
    area = range(lb.SPRITE_PAGE * 128, (lb.SPRITE_PAGE + lb.SPRITE_PAGES) * 128)
    cols = sorted({i % 128 for shot in shots for i in area if shot[i] != base[i]})
    x0, w = cols[0], cols[-1] - cols[0] + 1
    first = shots[0]
    fin = b"".join(first[(lb.SPRITE_PAGE + p) * 128 + x0:(lb.SPRITE_PAGE + p) * 128 + x0 + w] for p in range(lb.SPRITE_PAGES))
    ticks = [[(i, shot[i]) for i in area if shot[i] != first[i]] for shot in shots]
    return (x0, w, fin), ticks


def digits():
    out = []
    for ch in lb.GLYPHS:
        glyph = r.F3[ch]
        out.append(bytes(sum(1 << row for row in range(5) if glyph[row * 3 + col] == "1") for col in range(3)))
    return out


def animation(art):
    """loading.blla: a progress picture per percent 0 to 99 and the one when done, the finale's 8 pictures as the loop
    from FINALE_AT on, its lists taken against the picture of FINALE_AT (the percent stays as it is under them)."""
    key = lambda pct, done=False, tick=0: lb.compose_reference(art, lb.loading_key(pct, done, tick)).hex()
    frames = {"progress": [key(pct) for pct in range(100)] + [key(100, True)],
              "loop": [key(lb.FINALE_AT, tick=t) for t in range(lb.TICKS_N)], "loopFrom": lb.FINALE_AT}
    out = subprocess.run(["node", str(ROOT / "tools" / "art" / "loading" / "encode_blla.mjs")], input=json.dumps(frames),
                         capture_output=True, text=True, check=True).stdout
    return bytes.fromhex(out.strip())


def main():
    base = lit(base_image())
    done_page = anim.blank()
    anim.text(done_page, "FERTIG", 4, 58, small=True)
    fig = figure()
    fin, ticks = finale(base)
    blob = lb.pack_loading(base, lit(done_page)[896:], anim.LUMPS, digits(), fig, fin, ticks)
    art = lb.parse_loading(blob)
    bad = []
    for pct in range(100):
        for tick in (range(lb.TICKS_N) if pct >= lb.FINALE_AT else (0,)):
            if lb.compose_reference(art, lb.loading_key(pct, False, tick)) != lit(frame(pct, tick=tick)):
                bad.append((pct, tick))
    for tick in range(lb.TICKS_N):
        if lb.compose_reference(art, lb.loading_key(100, True, tick)) != lit(frame(100, True, tick)):
            bad.append(("done", tick))
    if bad:
        raise SystemExit(f"the overlay's composition differs from the renderer at {bad[:8]}")
    blla = animation(art)
    n = len(loading_anim.decode(blla)[0])
    for permille in range(1001):
        pct, done = permille // 10, permille == 1000
        for tick in (range(lb.TICKS_N) if done or pct >= lb.FINALE_AT else (None,)):
            if loading_anim.picture(blla, loading_anim.progress_index(n, permille), tick) != lit(frame(pct, done, tick or 0)):
                bad.append((permille, tick))
    if bad:
        raise SystemExit(f"loading.blla differs from the renderer at {bad[:8]}")
    (ASSETS / "loading.bin").write_bytes(blob)
    (ASSETS / "loading.blla").write_bytes(blla)

    still = anim.still_splash()
    splash = anim.pack_frame(still, bit_order="msb", controller_inverted=False)
    (ASSETS / "splash.bin").write_bytes(splash)
    still.convert("1").save(ASSETS / "splash.png")             # black where a bit is set, like the old one
    patch = json.loads((ASSETS / "splash.json").read_text())
    patch["changes"][0]["bytes"] = splash.hex()
    (ASSETS / "splash.json").write_text(json.dumps(patch, indent=1) + "\n")
    print(f"loading.bin {len(blob)} bytes (figure {fig[1]} columns at x {fig[0]}, finale {fin[1]} columns at x {fin[0]}, "
          f"finale changes {[len(t) for t in ticks]}), loading.blla {len(blla)} bytes, splash.bin 1024 bytes; "
          f"composition and loading.blla equal the renderer for all 108 pictures")


if __name__ == "__main__":
    main()
