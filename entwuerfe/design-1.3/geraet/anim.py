#!/usr/bin/env python3
"""Loader draft 4 (dark mode): the whole display is set (dark) and only light pixels are drawn, because the LCD
smears far less when a pixel goes off and on again than when it goes on and off. Blechy is the sprite inverted.

    python3 entwuerfe/design-1.3/geraet/anim.py

- BLECH stays where it is. TRIBE and FEINSTES GELUMPE slide to the left behind BLECH, then LADEN comes in from the
  right and stays.
- The load is a row of short lines on the table. Blechy holds a straw in his right hand and takes one line after the
  other: the tip of the straw runs along the line and the line is gone behind it. Then the straw comes off, he pulls
  his nose up and slides on to the next line; only the lines move, he stays in place.
- His pupils grow with the load, a little with every line, until he stares at the end.

Writes vorschau/rotzen.gif (4x), vorschau/rotzen-strip.png (one line, frame by frame) and png/rotzen-*.png.
"""
from PIL import Image

import render as r

W, H = r.W, r.H
TABLE = 56                           # the table top, one light row; the lines lie just above it at nose height
DASH_Y, DASH_LEN, DASH_GAP = 53, 6, 12
DASHES = 10
HEAD_X = 6                           # screen x of sprite column 0; Blechy stays here
NOSE = (HEAD_X + 26, TABLE - 2)      # where the straw leaves the left nostril
FIRST_DASH = HEAD_X + 48             # screen x of the line he is working on, just right of his body
TEXT_X = 83


# ---- Blechy, inverted -------------------------------------------------------------------------------
PUPILS = [
    [(0, 0)],                                                                  # one pixel
    [(0, 0), (1, 0), (0, 1), (1, 1)],                                          # 2 x 2
    [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)],                                # cross
    [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1)],                          # 3 x 3
    [(x, y) for x in range(-2, 3) for y in range(-2, 3) if x * x + y * y <= 4],  # disc
    [(x, y) for x in range(-2, 3) for y in range(-2, 3) if x * x + y * y <= 6],  # fills the eye
]


def pupil_shape(p):
    return PUPILS[min(len(PUPILS) - 1, int(p * len(PUPILS)))]


def head(f, rise, p, look_down):
    """The sprite with the stub nose, inverted inside his outline: light body, dark face, light pupils.
    The pupils grow with p in steps: one pixel, 2 x 2, cross, 3 x 3, disc, the whole eye."""
    g = r.small_blechy(nose=False)
    r.stub_nose(g, 24)
    for ex, ey in [(21, 14), (33, 16)]:
        for y in range(ey - 3, ey + 4):
            for x in range(ex - 3, ex + 4):
                if (x - ex) ** 2 + (y - ey) ** 2 <= 6:
                    g[y][x] = 0
        dy = 1 if look_down and p < 0.9 else 0
        for x, y in pupil_shape(p):
            g[ey + y + dy][ex + x] = 1
        if p >= 0.8:
            g[ey - 1][ex - 1] = 0                            # a dark glint once the pupil is big
    out = set()
    todo = [(0, 0)]
    while todo:
        x, y = todo.pop()
        if (x, y) in out or not (0 <= x < 56 and 0 <= y < 56) or g[y][x]:
            continue
        out.add((x, y))
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    oy = TABLE - 1 - rise
    for y in range(3, rise + 1):
        for x in range(56):
            if (x, y) not in out:
                r.put(f, x + HEAD_X, y + oy, 0 if g[y][x] else 1)   # inverted: body light, face dark
    for k in (0, 2, 4):                                      # left hand flat on the table
        r.rect(f, HEAD_X + 6 + k, TABLE - 2, HEAD_X + 6 + k, TABLE - 1, 0)
    return oy


def straw_and_hand(f, oy, away):
    """The straw has one length and never leaves his hand. At the nose it runs from the nostril to the line; away, hand
    and straw sit 4 px further right and 2 px higher, off the nose and off the table."""
    dx, dy = (4, -2) if away else (0, 0)
    x0, y0 = NOSE[0] + dx, NOSE[1] + dy
    x1, y1 = FIRST_DASH + dx, DASH_Y + dy
    n = max(abs(x1 - x0), abs(y1 - y0))
    pts = [(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)) for i in range(n + 1)]
    for x, y in pts:
        for yy in (y, y - 1):                                # 2 px thick, inverted: dark across his light body
            if 0 <= x < W and 0 <= yy < H:
                f[yy][x] ^= 1
    hx, hy = HEAD_X + 47 + dx, DASH_Y - 3 + dy
    sx, sy = HEAD_X + 43, oy + 17                            # the arm out of his right side, down to the straw
    m = max(abs(hx - sx), abs(hy - sy), 1)
    for i in range(m + 1):
        r.put(f, round(sx + (hx - sx) * i / m), round(sy + (hy - sy) * i / m), 0)
    r.rect(f, hx - 1, hy, hx + 1, hy + 1, 0)                 # the fist on the straw


# ---- the top: BLECH fixed, the words beside it change ---------------------------------------------
def blech(f):
    r.BLECH = r.BLECH or r.blech_mask()
    for x, y in r.BLECH:
        r.put(f, x, y, 0)


def words(f, dx, kind):
    """kind 'tribe': TRIBE / FEINSTES GELUMPE, kind 'laden': LADEN and the percent. Anything left of the gap after BLECH
    is hidden, so the old words slide in behind it."""
    t = r.blank(1)
    if kind == "tribe":
        r.tall(t, "TRIBE", TEXT_X + dx, 2)
        r.text3(t, "FEINSTES", TEXT_X + dx, 18)
        r.text3(t, "GELUMPE", TEXT_X + dx, 24)
    else:
        r.tall(t, "LADEN", TEXT_X + dx, 2)
        r.text3(t, kind, TEXT_X + dx, 21)
    edge = max(x for x, _ in r.BLECH) + 3
    for y in range(30):
        for x in range(edge, W):
            if not t[y][x]:
                f[y][x] = 0


# ---- frames ----------------------------------------------------------------------------------------
def frame(top, shift, rise, p, away):
    """shift: how far the world has moved left; the lines left of the straw tip are gone."""
    f = r.blank(1)
    blech(f)
    words(f, *top)
    r.rect(f, 0, TABLE, W - 1, TABLE, 0)
    for i in range(DASHES):
        x0 = FIRST_DASH + i * DASH_GAP - shift
        for x in range(max(x0, FIRST_DASH), x0 + DASH_LEN):  # what reached the tip is gone
            r.put(f, x, DASH_Y, 0)
            r.put(f, x, DASH_Y + 1, 0)
    oy = head(f, rise, p, look_down=not away)
    straw_and_hand(f, oy, away)
    return f


TOPS = [(-10, "tribe"), (-22, "tribe"), (-40, "tribe"), (40, None), (20, None), (8, None)]


def main():
    frames = []
    state = {"top": 0, "wait": 2}                            # TRIBE stays for the first 2 lines, then LADEN comes

    def top(p):
        kind = f"{round(p * 100)}%"
        if state["wait"] > 0 or state["top"] >= len(TOPS):
            return (0, "tribe") if state["top"] == 0 else (0, kind)
        dx, k = TOPS[state["top"]]
        state["top"] += 1
        return (dx, k or kind)

    def add(shift, rise, away, p):
        frames.append(frame(top(p), shift, rise, p, away))

    for rise in (18, 20, 23, 25):                            # from the start image: he comes up, straw in hand
        add(0, rise, True, 0.0)
    add(0, 25, True, 0.0)
    for i in range(DASHES):
        base = i * DASH_GAP
        add(base, 25, False, i / DASHES)                     # straw to the nose
        for k, step in enumerate((2, 4, 6)):                 # he runs along the line, fast
            add(base + step, 25, False, (i + step / DASH_LEN) / DASHES)
        p1 = (i + 1) / DASHES
        add(base + 6, 26, True, p1)                          # straw off, nose up, a short pause
        add(base + 6, 26, True, p1)
        if i == 1:
            state["wait"] = 0
        if i < DASHES - 1:
            add(base + 9, 25, True, p1)                      # quickly over to the next line
            add(base + 12, 25, True, p1)
            add(base + 12, 25, True, p1)                     # pause
    end = frame((0, "100%"), DASHES * DASH_GAP - 6, 25, 1.0, True)
    frames += [end] * 10

    def big(f):
        img = Image.new("RGB", (W, H), r.LCD_LIGHT)
        px = img.load()
        for y in range(H):
            for x in range(W):
                if f[y][x]:
                    px[x, y] = r.LCD_DARK
        return img.resize((W * 4, H * 4), Image.NEAREST)

    imgs = [big(f) for f in frames]
    durations = [400] + [90] * (len(frames) - 11) + [200] * 10
    imgs[0].save(r.HERE / "vorschau" / "rotzen.gif", save_all=True, append_images=imgs[1:], duration=durations, loop=0)
    one = frames[5 + 9 * 4:5 + 9 * 5]
    r.strip("rotzen", [(f"rotzen-{k}", f) for k, f in enumerate(one)])
    r.save("rotzen-start", frames[0])
    r.save("rotzen-ende", end)
    print(len(frames), "frames")


if __name__ == "__main__":
    main()
