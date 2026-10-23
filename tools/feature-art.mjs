#!/usr/bin/env node
// Draws the pictures of the Features page as the display shows them: 128 x 64 pixels, text in the display font
// (data/script/font.mjs), pad colours where the feature is about pads. Each picture becomes an SVG of whole pixels.
//   node tools/feature-art.mjs [--doom frame.bin]
// --doom takes a frame of Doom running in the emulator (tools/doom/run_runtime.py writes frame.bin).
import { readFileSync, writeFileSync } from "node:fs";
import { FONT, FONT_FIRST, ADVANCE, GLYPH_HEIGHT } from "../data/script/font.mjs";

const W = 128;
const H = 64;
const OUT = new URL("../site/img/features/", import.meta.url);
const RED = "#ff4b4b";
const BLUE = "#4b8bff";
const PINK = "#ff5fa8";
/** Ü, which the font lacks: the U with two dots above. */
const EXTRA = { "Ü": [0x3c, 0x41, 0x40, 0x41, 0x3c] };

function picture() {
  const lit = Array.from({ length: H }, () => new Array(W).fill(null));
  const dot = (x, y, colour = "#fff") => { if (x >= 0 && x < W && y >= 0 && y < H) lit[y][x] = colour; };
  const p = {
    lit,
    fill(x, y, w, h, colour) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) dot(x + i, y + j, colour); },
    clear(x, y, w, h) { p.fill(x, y, w, h, null); },
    frame(x, y, w, h, t = 1) { p.fill(x, y, w, t); p.fill(x, y + h - t, w, t); p.fill(x, y, t, h); p.fill(x + w - t, y, t, h); },
    width: (text, s = 1) => (text.length * ADVANCE - 1) * s,
    text(text, x, y, { s = 1, align = "left", colour = "#fff" } = {}) {
      const left = align === "center" ? Math.round(x - p.width(text, s) / 2) : align === "right" ? x - p.width(text, s) : x;
      [...text].forEach((ch, n) => {
        const cols = EXTRA[ch] ?? FONT[ch.charCodeAt(0) - FONT_FIRST] ?? FONT[0];
        cols.forEach((bits, c) => {
          for (let r = 0; r < GLYPH_HEIGHT; r++) if (bits & (1 << r)) p.fill(left + (n * ADVANCE + c) * s, y + r * s, s, s, colour);
        });
      });
    },
  };
  return p;
}

function svg(p) {
  const runs = new Map();
  p.lit.forEach((row, y) => {
    for (let x = 0; x < W;) {
      const colour = row[x];
      if (!colour) { x++; continue; }
      let end = x;
      while (end < W && row[end] === colour) end++;
      runs.set(colour, (runs.get(colour) ?? "") + `M${x} ${y}h${end - x}v1h-${end - x}z`);
      x = end;
    }
  });
  const paths = [...runs].map(([colour, d]) => `<path fill="${colour}" d="${d}"/>`).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges"><rect width="${W}" height="${H}"/>${paths}</svg>\n`;
}

const pads = (p, colourOf) => {
  for (let i = 0; i < 16; i++) p.fill(6 + (i % 8) * 15, i < 8 ? 26 : 42, 12, 12, colourOf(i));
};

const ART = {
  "pattern-switch": p => {
    p.text("PATTERN", 4, 3);
    p.frame(4, 15, 48, 28, 2);
    p.text("012", 28, 22, { s: 2, align: "center" });
    p.fill(58, 28, 10, 2); for (let i = 0; i < 6; i++) p.fill(66 + i, 23 + i, 1, 12 - 2 * i);
    p.fill(76, 15, 48, 28);
    p.text("013", 100, 22, { s: 2, align: "center", colour: null });
    p.text("MENU=OK EXIT=ZURÜCK", 64, 52, { align: "center" });
  },
  mfx2: p => {
    for (const [x, name, level] of [[4, "MFX1", 40], [68, "MFX2", 26]]) {
      p.frame(x, 4, 56, 40, 2);
      p.text(name, x + 28, 11, { s: 2, align: "center" });
      p.frame(x + 8, 32, 40, 6); p.fill(x + 8, 32, level, 6);
    }
    p.text("TOUCH SCALE", 64, 52, { align: "center" });
  },
  "exit-write": p => {
    p.frame(0, 12, 52, 26, 2);
    p.text("EXIT", 26, 18, { s: 2, align: "center" });
    p.text("+", 59, 18, { s: 2, align: "center" });
    p.fill(66, 12, 62, 26);
    p.text("WRITE", 97, 18, { s: 2, align: "center", colour: null });
    p.text("GESPEICHERT", 64, 50, { align: "center" });
  },
  menu: p => {
    p.text("BLECH", 4, 3, { s: 2 });
    p.fill(0, 19, W, 1);
    p.fill(0, 23, W, 11);
    p.text("> SNAKE", 4, 25, { colour: null });
    p.text("  TETRIS", 4, 39);
    p.text("  LAUFLICHT", 4, 52);
  },
  dice: p => {
    p.frame(8, 8, 48, 48, 3);
    for (const [x, y] of [[16, 16], [41, 16], [28, 28], [16, 41], [41, 41]]) p.fill(x, y, 7, 7);
    p.text("SHIFT", 66, 8, { s: 2 });
    p.text("+", 66, 26);
    p.text("PART", 66, 38);
    p.text("ERASE", 66, 48);
  },
  "tap-motion": p => {
    for (let y = -21; y <= 21; y++) { const w = Math.round(Math.sqrt(441 - y * y)); p.fill(23 - w, 25 + y, 2 * w + 1, 1); }
    p.text("TAP", 23, 18, { s: 2, align: "center", colour: null });
    for (let x = 0; x < 74; x++) p.fill(52 + x, 24 + Math.round(-9 * Math.sin((x / 18) * Math.PI)), 1, 3);
    p.text("MOTION ON", 50, 52);
  },
  colors: p => {
    p.text("PAD COLOR", 4, 6, { s: 2 });
    pads(p, i => [RED, RED, RED, RED, BLUE, BLUE, BLUE, PINK, RED, RED, PINK, PINK, BLUE, BLUE, BLUE, PINK][i]);
  },
  "note-assist": p => {
    p.text("KEYBOARD", 4, 8);
    p.text("C MAJ", 124, 8, { align: "right" });
    const on = new Set([0, 2, 4, 5, 7, 9, 11, 12, 13]);
    pads(p, i => (on.has(i) ? PINK : null));
    for (let i = 0; i < 16; i++) if (!on.has(i)) p.frame(6 + (i % 8) * 15, i < 8 ? 26 : 42, 12, 12);
  },
  presets: p => {
    p.text("EIGENE MFX", 4, 3);
    [[30, "TIME"], [14, "FDBK"], [38, "TONE"], [22, "MIX"]].forEach(([at, name], i) => {
      const x = 12 + i * 30;
      p.fill(x + 4, 14, 2, 36);
      p.fill(x, at, 10, 6);
      p.text(name, x + 5, 54, { align: "center" });
    });
  },
};

function fromFrame(path) {
  const frame = readFileSync(path);
  const p = picture();
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (frame[(y >> 3) * W + x] & (1 << (y & 7))) p.fill(x, y, 1, 1);
  return p;
}

const doom = process.argv.indexOf("--doom");
const jobs = Object.entries(ART).map(([name, draw]) => { const p = picture(); draw(p); return [name, p]; });
if (doom > 0) jobs.push(["doom", fromFrame(process.argv[doom + 1])]);
for (const [name, p] of jobs) {
  writeFileSync(new URL(`${name}.svg`, OUT), svg(p));
  console.log(`site/img/features/${name}.svg`);
}
