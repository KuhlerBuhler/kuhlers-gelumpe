#!/usr/bin/env python3
"""Draft board: the firmware's screens with the look of the start image, as the firmware draws it.

    python3 entwuerfe/design-1.3/geraet/ui_look.py SCREENS.json OUT.png [BEFORE.json]

SCREENS.json is what tools/emu/theme_screens.py prints. The look itself is tools/patch/load_bar.py:restyle_reference,
the same rules the patch runs at the display send:

  tab     the inverted page tab gets a stamped corner
  box     a box outline gets cut corners and a dithered shadow down and right, like the wordmark
  plate   a filled box (the main screen's pattern name) becomes an outline box with the same shadow,
          so the screen stays dark (less ghosting)
  rim     a dithered rim, dense at the lit glass edge and fading inward, on the bottom, left and right,
          only along long clear stretches, so it never breaks up between words

Pixels are the frame buffer's: set means lit on the reversed display. Two columns: today, with the look.
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "patch"))
from load_bar import restyle_reference  # noqa: E402

W, H = 128, 64
GLASS = 6                                              # the always lit glass around the pixels, as on the device


def frame(hexed):
    raw = bytes.fromhex(hexed)
    return [[(raw[(y >> 3) * W + x] >> (y & 7)) & 1 for x in range(W)] for y in range(H)]


def image(px, scale=3, lit=(235, 235, 230), dark=(28, 28, 30)):
    im = Image.new("RGB", (W + 2 * GLASS, H + 2 * GLASS), lit)
    inner = Image.new("RGB", (W, H))
    inner.putdata([lit if px[y][x] else dark for y in range(H) for x in range(W)])
    im.paste(inner, (GLASS, GLASS))
    return im.resize(((W + 2 * GLASS) * scale, (H + 2 * GLASS) * scale), Image.NEAREST)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    scenes = json.load(open(src))["scenes"]
    before = json.load(open(sys.argv[3]))["scenes"] if len(sys.argv) > 3 else scenes
    scale, gap = 3, 8
    cw, ch = (W + 2 * GLASS) * scale + gap, (H + 2 * GLASS) * scale + gap
    board = Image.new("RGB", (2 * cw, len(scenes) * ch), (40, 40, 40))
    for i, s in enumerate(scenes):
        looked = restyle_reference(bytes.fromhex(s["b"])).hex()
        for k, shown in enumerate((frame(before[i]["b"]), frame(looked))):
            board.paste(image(shown, scale), (k * cw, i * ch))
    board.save(dst)


if __name__ == "__main__":
    main()
