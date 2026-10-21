#!/usr/bin/env python3
"""README animations from complete frames of our own firmware art."""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/patch'))
import load_bar as lb
import power_off as po
import anim

OUT = ROOT / 'docs/images/readme'


def pixels(data):
    return Image.frombytes('P', (128, 64), bytes(
        (data[(y // 8) * 128 + x] >> (y % 8)) & 1
        for y in range(64) for x in range(128)))


def save_gif(name, frames, durations):
    palette = [0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254
    scaled = []
    for frame in frames:
        frame.putpalette(palette)
        scaled.append(frame.resize((512, 256), Image.Resampling.NEAREST))
    scaled[0].save(OUT / name, save_all=True, append_images=scaled[1:],
                   duration=durations, loop=0, disposal=2, optimize=False)


def main():
    art = lb.parse_loading(lb.art())
    frames = [pixels(lb.compose_reference(art, lb.loading_key(p, False, 0)))
              for p in range(0, 95, 2)]
    durations = [80] * len(frames)
    for tick, pct in enumerate(range(95, 100)):
        frames.append(pixels(lb.compose_reference(art, lb.loading_key(pct, False, tick))))
        durations.append(120)
    for tick in range(16):
        frames.append(pixels(lb.compose_reference(art, lb.loading_key(100, True, tick))))
        durations.append(120)
    durations[-1] += 1000
    save_gif('blechtribe-start.gif', frames, durations)
    times = list(range(0, 700, 125)) + [700, 760, 820, 880, 930, 970]
    save_gif('blechtribe-aus.gif', [pixels(po.sequence(t, True)) for t in times],
             [times[i + 1] - t if i + 1 < len(times) else 700 for i, t in enumerate(times)])
    image = anim.blank()
    anim.text(image, 'POWER OFF', 37, 27)
    anim.text(image, 'SCHEMA', 101, 56, small=True)
    path = ''.join(f'M{x} {y}h1v1h-1z' for y in range(64) for x in range(128) if image.getpixel((x, y)))
    (OUT / 'ausschalten-normal.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 64" width="512" height="256" role="img" aria-label="Normales Ausschalten, schematisch">'
        '<rect width="128" height="64" fill="#d4e0c4"/>'
        '<g fill="none" stroke="#1b2414"><rect x="13.5" y="18.5" width="101" height="24"/></g>'
        f'<path fill="#1b2414" shape-rendering="crispEdges" d="{path}"/></svg>\n')


if __name__ == '__main__':
    main()
