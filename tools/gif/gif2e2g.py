#!/usr/bin/env python3
"""Turn an animated GIF (or any picture Pillow reads) into a picture file for korg.file.frame and the GIF Player.

    python3 tools/gif/gif2e2g.py in.gif 3            -> GIF03.E2G, copy it to KORG/blechtribe/Gif/ on the card
    python3 tools/gif/gif2e2g.py in.gif 3 --invert --threshold 100 --out somewhere/

Format (SCRIPT_GIF in data/script/contract.mjs): "GGIF", version 1 (u16), frame count (u16), then per frame its delay in
ms (u16), two zero bytes and 1024 bytes of display memory: byte (y // 8) * 128 + x, bit y % 8. A picture that is not
128 x 64 is scaled to fit and centred. Lit is a pixel brighter than the threshold (with --invert: darker). The device shows
a new frame at most every 40 ms (one frame of the plugin runtime), shorter delays play at that pace.
"""
import argparse
import struct
import sys
from pathlib import Path

from PIL import Image, ImageSequence

W, H = 128, 64
MAGIC, VERSION = b"GGIF", 1


def frame_bytes(picture, threshold=128, invert=False):
    """1024 bytes of display memory for one picture."""
    grey = picture.convert("RGBA")
    flat = Image.new("RGBA", grey.size, (0, 0, 0, 255))
    flat.alpha_composite(grey)
    grey = flat.convert("L")
    if grey.size != (W, H):
        scale = min(W / grey.width, H / grey.height)
        size = (max(1, round(grey.width * scale)), max(1, round(grey.height * scale)))
        canvas = Image.new("L", (W, H), 255 if invert else 0)
        canvas.paste(grey.resize(size, Image.NEAREST if scale >= 1 else Image.LANCZOS), ((W - size[0]) // 2, (H - size[1]) // 2))
        grey = canvas
    out = bytearray(W * H // 8)
    px = grey.load()
    for y in range(H):
        for x in range(W):
            if (px[x, y] < threshold) if invert else (px[x, y] >= threshold):
                out[(y // 8) * W + x] |= 1 << (y % 8)
    return bytes(out)


def pack(frames):
    """frames: (delay ms, 1024 bytes) -> the file."""
    if not 1 <= len(frames) <= 0xFFFF:
        raise ValueError(f"{len(frames)} frames, 1 to 65535 allowed")
    out = bytearray(MAGIC + struct.pack("<HH", VERSION, len(frames)))
    for delay, data in frames:
        out += struct.pack("<HH", max(1, min(0xFFFF, round(delay))), 0) + data
    return bytes(out)


def convert(path, threshold=128, invert=False, delay=None):
    with Image.open(path) as picture:
        return pack([(delay or f.info.get("duration") or 100, frame_bytes(f, threshold, invert)) for f in ImageSequence.Iterator(picture)])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("source")
    p.add_argument("number", type=int, help="file number 0 to 99, the GIF Player picks it with the encoder")
    p.add_argument("--threshold", type=int, default=128)
    p.add_argument("--invert", action="store_true", help="dark pixels are lit")
    p.add_argument("--delay", type=int, help="ms for every frame instead of the GIF's own")
    p.add_argument("--out", default=".", help="folder for GIFnn.E2G")
    a = p.parse_args(argv)
    if not 0 <= a.number <= 99:
        p.error("number 0 to 99")
    data = convert(a.source, a.threshold, a.invert, a.delay)
    target = Path(a.out) / f"GIF{a.number:02d}.E2G"
    target.write_bytes(data)
    print(f"{target}: {struct.unpack_from('<H', data, 6)[0]} frames, {len(data)} bytes")


if __name__ == "__main__":
    sys.exit(main())
