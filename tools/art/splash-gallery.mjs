#!/usr/bin/env node
/**
 * Draws the extra start images of the Startbild gallery (site/img/splash/*.png, GALLERY in site/app/splash.mjs):
 * 128 x 64 pixels, 1 bit, a drawn pixel is black. Own code, no dependency, a 5 x 7 pixel font like the device's display.
 *
 *   node tools/art/splash-gallery.mjs              # writes the PNGs into site/img/splash/
 *   node tools/art/splash-gallery.mjs --preview D  # also writes 5x enlarged copies into the folder D, to look at
 */
import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const W = 128;
const H = 64;
const OUT = fileURLToPath(new URL("../../site/img/splash/", import.meta.url));

const FONT = {
  A: "01110 10001 10001 11111 10001 10001 10001", B: "11110 10001 10001 11110 10001 10001 11110",
  C: "01110 10001 10000 10000 10000 10001 01110", D: "11110 10001 10001 10001 10001 10001 11110",
  E: "11111 10000 10000 11110 10000 10000 11111", F: "11111 10000 10000 11110 10000 10000 10000",
  G: "01110 10001 10000 10111 10001 10001 01111", H: "10001 10001 10001 11111 10001 10001 10001",
  I: "01110 00100 00100 00100 00100 00100 01110", J: "00111 00010 00010 00010 00010 10010 01100",
  K: "10001 10010 10100 11000 10100 10010 10001", L: "10000 10000 10000 10000 10000 10000 11111",
  M: "10001 11011 10101 10101 10001 10001 10001", N: "10001 11001 10101 10011 10001 10001 10001",
  O: "01110 10001 10001 10001 10001 10001 01110", P: "11110 10001 10001 11110 10000 10000 10000",
  R: "11110 10001 10001 11110 10100 10010 10001", S: "01111 10000 10000 01110 00001 00001 11110",
  T: "11111 00100 00100 00100 00100 00100 00100", U: "10001 10001 10001 10001 10001 10001 01110",
  V: "10001 10001 10001 10001 10001 01010 00100", W: "10001 10001 10001 10101 10101 11011 10001",
  X: "10001 10001 01010 00100 01010 10001 10001", Y: "10001 10001 01010 00100 00100 00100 00100",
  Z: "11111 00001 00010 00100 01000 10000 11111",
  0: "01110 10001 10011 10101 11001 10001 01110", 1: "00100 01100 00100 00100 00100 00100 01110",
  2: "01110 10001 00001 00010 00100 01000 11111", 3: "11110 00001 00001 01110 00001 00001 11110",
  4: "00010 00110 01010 10010 11111 00010 00010", 5: "11111 10000 11110 00001 00001 10001 01110",
  6: "00110 01000 10000 11110 10001 10001 01110", 7: "11111 00001 00010 00100 01000 01000 01000",
  8: "01110 10001 10001 01110 10001 10001 01110", 9: "01110 10001 10001 01111 00001 00010 01100",
  "'": "00100 00100 01000 00000 00000 00000 00000", "-": "00000 00000 00000 11111 00000 00000 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
};

/** A picture: `px[y * W + x]` is 1 for a drawn (black) pixel. */
function canvas() {
  const px = new Uint8Array(W * H);
  const api = {
    px,
    set(x, y, v = 1) { if (x >= 0 && x < W && y >= 0 && y < H) px[y * W + x] = v; },
    rect(x, y, w, h, v = 1) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) api.set(x + i, y + j, v); },
    frame(x, y, w, h, v = 1) { api.rect(x, y, w, 1, v); api.rect(x, y + h - 1, w, 1, v); api.rect(x, y, 1, h, v); api.rect(x + w - 1, y, 1, h, v); },
    line(x0, y0, x1, y1, v = 1) {
      const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) || 1;
      for (let i = 0; i <= n; i++) api.set(Math.round(x0 + (x1 - x0) * i / n), Math.round(y0 + (y1 - y0) * i / n), v);
    },
    disc(cx, cy, r, v = 1) { for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) if (x * x + y * y <= r * r + r * 0.5) api.set(cx + x, cy + y, v); },
    ellipse(cx, cy, rx, ry, v = 1) { for (let y = -ry; y <= ry; y++) for (let x = -rx; x <= rx; x++) if ((x * x) / (rx * rx) + (y * y) / (ry * ry) <= 1) api.set(cx + x, cy + y, v); },
    /** Text with its top left at (x, y); a letter is 5 pixels wide, one blank column between. Returns the width. */
    text(x, y, s, scale = 1, v = 1) {
      let at = x;
      for (const ch of s) {
        const rows = (FONT[ch] ?? FONT[" "]).split(" ");
        rows.forEach((row, j) => [...row].forEach((c, i) => { if (c === "1") api.rect(at + i * scale, y + j * scale, scale, scale, v); }));
        at += 6 * scale;
      }
      return at - x - scale;
    },
    width: (s, scale = 1) => s.length * 6 * scale - scale,
    centred(y, s, scale = 1, v = 1) { api.text(Math.round((W - api.width(s, scale)) / 2), y, s, scale, v); },
    invert() { for (let i = 0; i < px.length; i++) px[i] ^= 1; },
  };
  return api;
}

/** Seeded, so a picture is the same on every run. */
const rng = seed => () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;

const PICTURES = {
  /** The wordmark in big letters, light on dark, between two rows of dashes. */
  gelumpe() {
    const c = canvas();
    c.rect(0, 0, W, H);
    for (let x = 0; x < W; x += 4) { c.rect(x, 3, 2, 2, 0); c.rect(x + 2, H - 5, 2, 2, 0); }
    c.centred(15, "KUHLER'S", 1, 0);
    c.centred(26, "GELUMPE", 2, 0);
    c.rect(22, 46, 84, 1, 0);
    c.centred(51, "FOR BLECHTRIBE", 1, 0);
    return c;
  },

  /** Holstein spots around a plate with the name. */
  kuhler() {
    const c = canvas();
    const r = rng(7);
    for (let i = 0; i < 9; i++) {
      const cx = Math.floor(r() * W);
      const cy = Math.floor(r() * H);
      c.ellipse(cx, cy, 6 + Math.floor(r() * 9), 4 + Math.floor(r() * 6));
      c.ellipse(cx + 6, cy + 3, 4 + Math.floor(r() * 5), 3 + Math.floor(r() * 4));
    }
    c.rect(14, 13, 100, 38, 0);
    c.frame(14, 13, 100, 38);
    c.frame(16, 15, 96, 34);
    c.centred(21, "KUHLER", 2);
    c.centred(38, "BUHLER", 1);
    return c;
  },

  /** The sixteen pads as two rows of eight, a pattern lit, the playhead above the fifth step. */
  pads() {
    const c = canvas();
    c.rect(0, 0, W, H);
    const lit = [1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1];
    for (let i = 0; i < 16; i++) {
      const x = 8 + (i % 8) * 14;
      const y = 8 + Math.floor(i / 8) * 15;
      if (lit[i]) c.rect(x, y, 12, 12, 0);
      else { c.frame(x, y, 12, 12, 0); }
    }
    c.rect(8 + 4 * 14 + 4, 2, 4, 3, 0);
    c.rect(8, 40, 112, 1, 0);
    c.centred(45, "BLECHTRIBE", 1, 0);
    c.centred(54, "16 STEPS", 1, 0);
    return c;
  },

  /** A sample's waveform on dark: a decaying burst around the centre line. */
  wave() {
    const c = canvas();
    c.rect(0, 0, W, H);
    for (let x = 0; x < W; x += 3) c.set(x, 28, 0);
    let last = null;
    for (let x = 4; x < W - 4; x++) {
      const t = (x - 4) / (W - 8);
      const y = 28 - Math.round(21 * Math.exp(-2.6 * t) * Math.sin(70 * (1 - Math.exp(-2.2 * t))));
      if (last !== null) c.line(x - 1, last, x, y, 0);
      last = y;
    }
    c.text(4, 55, "SAMPLE", 1, 0);
    c.text(W - 4 - c.width("BLECH"), 55, "BLECH", 1, 0);
    c.rect(4, 52, W - 8, 1, 0);
    return c;
  },

  /** One big knob with its scale: the value stands next to it. */
  knob() {
    const c = canvas();
    const cx = 36;
    const cy = 32;
    c.disc(cx, cy, 22);
    c.disc(cx, cy, 18, 0);
    c.disc(cx, cy, 15);
    const a = (-135 + 0.72 * 270) * Math.PI / 180;
    c.line(cx, cy, cx + Math.round(Math.sin(a) * 15), cy - Math.round(Math.cos(a) * 15), 0);
    c.line(cx + 1, cy, cx + 1 + Math.round(Math.sin(a) * 15), cy - Math.round(Math.cos(a) * 15), 0);
    for (let i = 0; i <= 10; i++) {
      const t = (-135 + i * 27) * Math.PI / 180;
      c.line(cx + Math.round(Math.sin(t) * 26), cy - Math.round(Math.cos(t) * 26), cx + Math.round(Math.sin(t) * (i % 5 ? 28 : 30)), cy - Math.round(Math.cos(t) * (i % 5 ? 28 : 30)));
    }
    c.text(78, 14, "CUTOFF", 1);
    c.text(78, 26, "73", 3);
    c.rect(78, 50, 40, 1);
    c.text(78, 54, "BLECH", 1);
    return c;
  },

  /** Level bars in LED segments rising from the bottom. */
  bars() {
    const c = canvas();
    c.rect(0, 0, W, H);
    const heights = [5, 9, 6, 12, 15, 11, 8, 13, 16, 10, 7, 12, 14, 9, 6, 4];
    for (let i = 0; i < 16; i++) {
      for (let s = 0; s < heights[i]; s++) c.rect(2 + i * 8, H - 3 - (s + 1) * 3, 6, 2, 0);
    }
    c.centred(3, "BLECHTRIBE", 1, 0);
    c.rect(2, 12, W - 4, 1, 0);
    return c;
  },
};

const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc32 = bytes => { let c = 0xffffffff; for (const b of bytes) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function chunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, "ascii");
  Buffer.from(data).copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}

/** A 1-bit grayscale PNG; a drawn pixel is black (bit 0), like the pictures that are there already. */
function png(px, w, h) {
  const stride = Math.ceil(w / 8);
  const raw = Buffer.alloc((stride + 1) * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) if (!px[y * w + x]) raw[y * (stride + 1) + 1 + (x >> 3)] |= 0x80 >> (x & 7);
  }
  const head = Buffer.alloc(13);
  head.writeUInt32BE(w, 0);
  head.writeUInt32BE(h, 4);
  head[8] = 1; // bit depth
  head[9] = 0; // grayscale
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", head), chunk("IDAT", deflateSync(raw, { level: 9 })), chunk("IEND", Buffer.alloc(0))]);
}

const preview = process.argv[2] === "--preview" ? process.argv[3] : null;
mkdirSync(OUT, { recursive: true });
if (preview) mkdirSync(preview, { recursive: true });
for (const [name, draw] of Object.entries(PICTURES)) {
  const { px } = draw();
  writeFileSync(`${OUT}${name}.png`, png(px, W, H));
  if (preview) {
    const big = new Uint8Array(W * 5 * H * 5);
    for (let y = 0; y < H * 5; y++) for (let x = 0; x < W * 5; x++) big[y * W * 5 + x] = px[Math.floor(y / 5) * W + Math.floor(x / 5)];
    writeFileSync(`${preview}/${name}.png`, png(big, W * 5, H * 5));
  }
}
