#!/usr/bin/env python3
"""Render Blechy sprites as 1-bit PNGs, from the prototype draw code.
Figure = black (lit / set bit). Canvas 56x56, figure centred at cx,cy."""
from PIL import Image, ImageDraw, ImageChops
import sys, math, os

CW, CH = 56, 56
CX, CY = 28, 22

def E(d, cx, cy, rx, ry, fill):
    d.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=fill)

def hand(d, x, y, tilt):
    """A raised hand at the end of the arm (x, y): a small palm and three fingers fanning out, leaning with `tilt`."""
    d.rectangle([x-1, y-3, x+1, y-1], fill=0)
    for k in (-1, 0, 1):
        d.line([x+k, y-4, x+k+tilt*(k+2)//2, y-8], fill=0)

def blechy(d, cx, cy, aL, aR, lp, twitch, sweat, face=None, wave=None, face_only=False):
    # body + nose (black silhouette)
    if not face_only:
        E(d, cx, cy+7, 13, 15, 0)
        E(d, cx, cy+4, 15, 12, 0)
    E(d, cx-7, cy-8, 8, 11, 0)          # bridge (rotation dropped)
    E(d, cx-2, cy-6, 11, 8, 255)        # white face patch
    ey = cy-8
    for ox, oy in ((-7, 0), (5, 2 if twitch else 0)):
        ex, eyy = cx+ox, ey+oy
        E(d, ex, eyy, 4, 4, 0)          # socket
        E(d, ex, eyy, 3, 3, 255)        # white
        if face == "happy":
            d.arc([ex-3, eyy-1, ex+3, eyy+5], 200, 340, fill=0)  # eye closed, content
            d.arc([ex-3, eyy, ex+3, eyy+6], 200, 340, fill=0)
        elif face == "sad":
            d.rectangle([ex-1, eyy+1, ex+1, eyy+3], fill=0)      # pupil low, looking down
            lid = [(ex-4, eyy-4), (ex+4, eyy-4), (ex+4, eyy-3), (ex-4, eyy)] if ox < 0 else [(ex-4, eyy-4), (ex+4, eyy-4), (ex+4, eyy), (ex-4, eyy-3)]
            d.polygon(lid, fill=0)                               # heavy lid, slanting down to the outside
        else:
            d.rectangle([ex-1, eyy-1, ex+1, eyy+1], fill=0)  # pupil
        d.arc([ex-3, eyy+1, ex+3, eyy+7], 10, 170, fill=0)   # eyebag 1
        d.arc([ex-3, eyy+3, ex+3, eyy+9], 17, 163, fill=0)   # eyebag 2
    tw = 1 if twitch else 0
    if face == "angry":                                     # both brows down towards the nose
        for dy in (0, 1):
            d.line([cx-12, ey-5+dy, cx-3, ey-2+dy], fill=0)
            d.line([cx+9, ey-6+dy, cx+1, ey-2+dy], fill=0)
    elif face == "sad":                                     # inner ends up, outer ends down, no mouth
        for dy in (0, 1):
            d.line([cx-12, ey-3+dy, cx-4, ey-7+dy], fill=0)
            d.line([cx+9, ey-4+dy, cx+2, ey-8+dy], fill=0)
    elif face == "happy":                                   # relaxed, level brows
        d.line([cx-11, ey-6, cx-4, ey-6], fill=0)
        d.line([cx+2, ey-6, cx+8, ey-6], fill=0)
    else:
        d.line([cx+1, ey-5-tw, cx+9, ey-6-2*tw], fill=0)    # brow
    if face_only:
        return
    # nostrils + drip
    E(d, cx-4, cy+11, 2, 3, 0)
    E(d, cx+5, cy+11, 2, 3, 0)
    d.rectangle([cx+5, cy+13, cx+5, cy+19], fill=0)
    E(d, cx+5, cy+20, 2, 2, 0)
    for sx, sy in ((-9, 8), (0, 12), (9, 7), (-4, 13)):     # stubble
        d.point((cx+sx, cy+sy), fill=0)
    # limbs
    d.line([cx-12, cy+3, cx+aL[0], cy+aL[1]], fill=0)
    d.line([cx+12, cy+3, cx+aR[0], cy+aR[1]], fill=0)
    d.line([cx-5, cy+18, cx-7-lp, cy+30], fill=0)
    d.line([cx+5, cy+18, cx+7+lp, cy+30], fill=0)
    d.rectangle([cx-10-lp, cy+30, cx-6-lp, cy+31], fill=0)
    d.rectangle([cx+5+lp, cy+30, cx+9+lp, cy+31], fill=0)
    if wave is not None:
        hand(d, cx+aR[0], cy+aR[1], wave)
    if sweat:
        E(d, cx-12, cy-14, 2, 2, 0)
        d.rectangle([cx-12, cy-17, cx-11, cy-15], fill=0)

POSES = {
    "idle":     dict(aL=(-20, 10),  aR=(20, 9),   lp=0,  twitch=1, lean=0,     sweat=0),
    # the idle pose with the face changed, nothing else: calm (no twitch), angry (tap), happy (stroke), sad (power off)
    "calm":     dict(aL=(-20, 10),  aR=(20, 9),   lp=0,  twitch=0, lean=0,     sweat=0),
    "angry":    dict(aL=(-20, 10),  aR=(20, 9),   lp=0,  twitch=0, lean=0,     sweat=0, face="angry"),
    "happy":    dict(aL=(-20, 10),  aR=(20, 9),   lp=0,  twitch=0, lean=0,     sweat=0, face="happy"),
    "sad":      dict(aL=(-20, 10),  aR=(20, 9),   lp=0,  twitch=0, lean=0,     sweat=0, face="sad"),
    # waving hello: the calm pose with the right arm raised, the hand leaning one way and the other (made once, for the ring page)
    "wave-1":   dict(aL=(-20, 10),  aR=(17, -9),  lp=0,  twitch=0, lean=0,     sweat=0, wave=-1),
    "wave-2":   dict(aL=(-20, 10),  aR=(21, -9),  lp=0,  twitch=0, lean=0,     sweat=0, wave=1),
    "walk":     dict(aL=(-18, 8),   aR=(20, 6),   lp=5,  twitch=0, lean=0,     sweat=1),
    "terror-1": dict(aL=(-22, -10), aR=(20, -12), lp=5,  twitch=1, lean=-7,    sweat=1),
    "terror-2": dict(aL=(-18, 12),  aR=(24, -14), lp=-6, twitch=0, lean=8,     sweat=1),
    "terror-3": dict(aL=(-24, -14), aR=(18, 8),   lp=4,  twitch=1, lean=3,     sweat=1),
    "terror-4": dict(aL=(-16, -16), aR=(22, -16), lp=-3, twitch=0, lean=-9,    sweat=1),
}

def render(p):
    img = Image.new("L", (CW, CH), 255)
    d = ImageDraw.Draw(img)
    blechy(d, CX, CY, p["aL"], p["aR"], p["lp"], p["twitch"], p["sweat"], p.get("face"), p.get("wave"))
    if p["lean"]:
        img = img.rotate(p["lean"], resample=Image.BILINEAR, fillcolor=255)
    return img.point(lambda v: 0 if v < 128 else 255, mode="1")

if sys.argv[1] == "--head":
    image = Image.new("L", (CW, CH), 255)
    blechy(ImageDraw.Draw(image), CX, CY, (-20, 10), (20, 9), 0, 0, 0, face_only=True)
    image = image.crop(ImageChops.invert(image).getbbox()).convert("1")
    image.save(sys.argv[2])
    sys.exit(0)

outdir = sys.argv[1]
os.makedirs(outdir, exist_ok=True)
frames = {}
for name, p in POSES.items():
    bw = render(p)
    bw.save(os.path.join(outdir, f"blechy-{name}.png"))
    frames[name] = bw

# preview strip on LCD tint, 4x
order = ["idle", "calm", "angry", "happy", "sad", "wave-1", "wave-2", "walk", "terror-1", "terror-2", "terror-3", "terror-4"]
gap = 2
strip = Image.new("RGB", (len(order)*(CW+gap)-gap, CH), (174, 183, 154))
for i, name in enumerate(order):
    px = frames[name].load()
    tile = Image.new("RGB", (CW, CH), (174, 183, 154))
    tp = tile.load()
    for y in range(CH):
        for x in range(CW):
            if px[x, y] == 0:
                tp[x, y] = (27, 36, 20)
    strip.paste(tile, (i*(CW+gap), 0))
strip.resize((strip.width*4, strip.height*4), Image.NEAREST).save(sys.argv[2])
print("wrote", len(frames), "sprites")
