/**
 * A start image for the card: 128 x 64 pixels, 1 bit, as the BLECH menu's SPLASH IMPORT reads it
 * (KORG/blechtribe/splash.bmp, tools/patch/splash_editor.py, splash_import). Black is drawn: on the
 * device a set pixel is dark.
 */
import { SPLASH_W, SPLASH_H } from "./patch.mjs";

export { SPLASH_W, SPLASH_H };
export const SPLASH_FILE = "splash.bmp";
export const SPLASH_FOLDER = "KORG/blechtribe/Media/";

/**
 * Brightness 0 (black) to 255 (white), one value per pixel, row by row, to 1 for a drawn pixel and 0 for an empty one.
 * `dither` spreads the error (Floyd-Steinberg), so grey areas become patterns; `invert` swaps drawn and empty.
 */
export function toMono(gray, { threshold = 128, dither = false, invert = false } = {}) {
  const n = SPLASH_W * SPLASH_H;
  if (gray.length !== n) throw new Error(`${gray.length} Werte, ein Startbild hat ${n}`);
  const g = Float32Array.from(gray);
  const out = new Uint8Array(n);
  for (let y = 0; y < SPLASH_H; y++) {
    for (let x = 0; x < SPLASH_W; x++) {
      const i = y * SPLASH_W + x;
      const dark = g[i] < threshold;
      out[i] = dark !== invert ? 1 : 0;
      if (!dither) continue;
      const err = g[i] - (dark ? 0 : 255);
      if (x + 1 < SPLASH_W) g[i + 1] += err * 7 / 16;
      if (y + 1 < SPLASH_H) {
        if (x > 0) g[i + SPLASH_W - 1] += err * 3 / 16;
        g[i + SPLASH_W] += err * 5 / 16;
        if (x + 1 < SPLASH_W) g[i + SPLASH_W + 1] += err / 16;
      }
    }
  }
  return out;
}

/** Brightness of RGBA bytes (canvas ImageData), transparent counts as white. */
export function grayOf(rgba) {
  const out = new Uint8Array(rgba.length / 4);
  for (let i = 0; i < out.length; i++) {
    const a = rgba[4 * i + 3] / 255;
    const lum = 0.299 * rgba[4 * i] + 0.587 * rgba[4 * i + 1] + 0.114 * rgba[4 * i + 2];
    out[i] = Math.round(lum * a + 255 * (1 - a));
  }
  return out;
}

/** The pixels (1 drawn) as a Windows bitmap: 1 bit, palette white and black, rows from the bottom, 1086 bytes. */
export function encodeBmp(pixels) {
  if (pixels.length !== SPLASH_W * SPLASH_H) throw new Error("kein Startbild mit 128 x 64 Pixeln");
  const stride = SPLASH_W / 8;
  const off = 14 + 40 + 8;
  const size = off + stride * SPLASH_H;
  const b = new Uint8Array(size);
  const v = new DataView(b.buffer);
  b[0] = 0x42; b[1] = 0x4d;
  v.setUint32(2, size, true);
  v.setUint32(10, off, true);
  v.setUint32(14, 40, true);
  v.setInt32(18, SPLASH_W, true);
  v.setInt32(22, SPLASH_H, true);
  v.setUint16(26, 1, true);
  v.setUint16(28, 1, true);
  v.setUint32(34, stride * SPLASH_H, true);
  v.setUint32(38, 2835, true);
  v.setUint32(42, 2835, true);
  v.setUint32(46, 2, true);
  b.set([0xff, 0xff, 0xff, 0, 0, 0, 0, 0], 54);       // index 0 white, index 1 black (drawn)
  for (let y = 0; y < SPLASH_H; y++) {
    const row = off + (SPLASH_H - 1 - y) * stride;
    for (let x = 0; x < SPLASH_W; x++) {
      if (pixels[y * SPLASH_W + x]) b[row + (x >> 3)] |= 0x80 >> (x & 7);
    }
  }
  return b;
}

/**
 * A Windows bitmap -> its 128 x 64 pixels (1 drawn, row by row), or a text that says why it is none. The checks are those of
 * SPLASH IMPORT (tools/patch/splash_editor.py, imp_parse): "BM", width 128, height 64 (rows from the bottom) or -64 (from the
 * top), 1 plane, 1 bit, no compression, the two palette entries before the pixels, the pixels from byte 54 to 0x200 and all
 * 1024 bytes of them in the file. The darker palette entry is drawn (the sum of blue, green and red; on a tie entry 0).
 */
export function decodeBmp(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 54) return "shorter than the header";
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes[0] !== 0x42 || bytes[1] !== 0x4d) return "not BM";
  const off = v.getUint32(10, true), info = v.getUint32(14, true);
  if (v.getInt32(18, true) !== SPLASH_W) return "not 128 pixels wide";
  const height = v.getInt32(22, true);
  if (height !== SPLASH_H && height !== -SPLASH_H) return "not 64 pixels high";
  if (v.getUint32(28, true) !== 1 || v.getUint16(32, true) !== 0) return "not 1 bit without compression";
  if (bytes[26] !== 1) return "not one plane";
  if (info + 22 > off) return "the palette does not end before the pixels";
  if (off < 54 || off > 0x200) return "the pixels do not start between byte 54 and 0x200";
  const stride = SPLASH_W / 8;
  if (off + stride * SPLASH_H > bytes.length) return "the pixels are cut short";
  const pal = 14 + info;
  const bright = i => bytes[pal + 4 * i] + bytes[pal + 4 * i + 1] + bytes[pal + 4 * i + 2];
  const ink = bright(1) < bright(0) ? 1 : 0;
  const px = new Uint8Array(SPLASH_W * SPLASH_H);
  for (let y = 0; y < SPLASH_H; y++) {
    const row = off + (height === SPLASH_H ? SPLASH_H - 1 - y : y) * stride;
    for (let x = 0; x < SPLASH_W; x++) px[y * SPLASH_W + x] = ((bytes[row + (x >> 3)] >> (7 - (x & 7))) & 1) === ink ? 1 : 0;
  }
  return px;
}
