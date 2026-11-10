#!/usr/bin/env node
// Draws the pictures of the Features page as the display shows them: 128 x 64 pixels, text in the display font
// (data/script/font.mjs), pad colours where the feature is about pads. Each picture becomes an SVG of whole pixels.
//   node tools/feature-art.mjs [--doom frame.bin]
// --doom takes a frame of Doom running in the emulator (tools/doom/run_runtime.py writes frame.bin).
import { readFileSync, writeFileSync } from "node:fs";
import { FONT, FONT_FIRST, ADVANCE, GLYPH_HEIGHT } from "../data/script/font.mjs";
import { FONT_ART, ICON_ART } from "./patch/blech_theme_art.mjs";
import { parseGlyph, parseIcon } from "./patch/blech_theme.mjs";

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

/** An arrow to the right, 14 pixels long, its middle at height y. */
const arrow = (p, x, y) => { p.fill(x, y, 10, 2); for (let i = 0; i < 6; i++) p.fill(x + 8 + i, y - 5 + i, 1, 12 - 2 * i); };
/** The power sign: a ring of radius r open at the top and a bar through the gap. */
const power = (p, cx, cy, r) => {
  for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
    const d = Math.hypot(x, y);
    if (d <= r && d > r - 3 && !(y < 0 && Math.abs(x) < r / 2)) p.fill(cx + x, cy + y, 1, 1);
  }
  p.fill(cx - 1, cy - r - 2, 3, r + 2);
};

/**
 * Text in one of the four fonts the BLECH theme puts on the device (tools/patch/blech_theme_art.mjs), not the display font
 * above: `baseline` is the bottom row of the capitals. A character the theme leaves to the firmware (the space) is a gap.
 */
const themeText = (p, text, x, baseline, font, { align = "left", colour = "#fff" } = {}) => {
  const glyphs = [...text].map(ch => (FONT_ART[font][ch] ? parseGlyph(FONT_ART[font][ch]) : null));
  const gap = font === 0 ? 3 : 5;
  const width = glyphs.reduce((n, g) => n + (g ? g.xo + g.w + 1 : gap), 0) - 1;
  let pen = align === "center" ? Math.round(x - width / 2) : align === "right" ? x - width : x;
  for (const g of glyphs) {
    if (!g) { pen += gap; continue; }
    const top = baseline - g.yo - g.h + 1;
    g.rows.forEach((row, r) => [...row].forEach((c, k) => { if (c === "#") p.fill(pen + g.xo + k, top + r, 1, 1, colour); }));
    pen += g.xo + g.w + 1;
  }
  return width;
};
/** One of the theme's icons by the firmware's image number, its top left corner at x, y. */
const themeIcon = (p, n, x, y) => parseIcon(ICON_ART[n]).rows.forEach((row, r) => [...row].forEach((c, k) => { if (c === "#") p.fill(x + k, y + r, 1, 1); }));

const ART = {
  // the picture of every planned function on the page (group Geplant)
  soon: p => {
    p.frame(2, 2, 124, 60, 2);
    p.text("KOMMT", 64, 12, { s: 2, align: "center" });
    p.text("BALD", 64, 34, { s: 2, align: "center" });
  },
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
  "key-pads": p => {
    p.text("KEY", 4, 4, { s: 2 });
    p.text("D", 124, 4, { s: 2, align: "right" });
    pads(p, i => (i === 2 ? PINK : null));
    for (let i = 0; i < 12; i++) if (i !== 2) p.frame(6 + (i % 8) * 15, i < 8 ? 26 : 42, 12, 12);
  },
  "filter-toggle": p => {
    p.frame(4, 10, 50, 26, 2);
    p.text("LPF", 29, 17, { s: 2, align: "center" });
    arrow(p, 58, 23);
    p.fill(74, 10, 50, 26);
    p.text("OFF", 99, 17, { s: 2, align: "center", colour: null });
    p.text("SHIFT + LPF", 64, 50, { align: "center" });
  },
  preview: p => {
    p.text("VIEW:013", 4, 4, { s: 2 });
    pads(p, i => ([0, 1, 4].includes(i) ? "#fff" : null));
    for (const i of [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]) p.frame(6 + (i % 8) * 15, i < 8 ? 26 : 42, 12, 12);
    for (const i of [8, 11]) { p.frame(6 + (i % 8) * 15, 42, 12, 12); p.fill(9 + (i % 8) * 15, 45, 6, 6); }
  },
  "sync-group": p => {
    p.text("SYNC GROUP", 4, 3);
    p.text("A", 124, 3, { align: "right" });
    p.frame(4, 16, 58, 22, 2);
    p.text("012", 33, 20, { s: 2, align: "center" });
    p.fill(62, 26, 4, 2);
    p.frame(66, 16, 58, 22, 2);
    p.text("013", 95, 20, { s: 2, align: "center" });
    p.text("128 STEPS", 64, 50, { align: "center" });
  },
  "last-pattern": p => {
    power(p, 26, 30, 18);
    p.text("012", 92, 20, { s: 3, align: "center" });
    p.text("LAST PATTERN", 92, 50, { align: "center" });
  },
  "init-pattern": p => {
    p.text("SET INIT PATTERN", 4, 3);
    p.fill(0, 19, W, 1);
    p.fill(0, 23, W, 11);
    p.text("> 064 EMPTY", 4, 25, { colour: null });
    p.text("  FACTORY", 4, 39);
  },
  "stereo-pad": p => {
    p.text("STEREO 1 PAD", 4, 3);
    p.text("ON", 124, 3, { align: "right" });
    p.fill(4, 16, 56, 30);
    p.text("L+R", 32, 24, { s: 2, align: "center", colour: null });
    p.frame(68, 16, 56, 30, 2);
    p.text("FREE", 96, 24, { s: 2, align: "center" });
  },
  "ht-osc": p => {
    p.text("OSC", 4, 3, { s: 2 });
    p.text("422-497", 124, 7, { align: "right" });
    [["DUAL", 4, 22], ["OCT", 66, 22], ["CHIP", 4, 42], ["RING", 66, 42]].forEach(([name, x, y], i) => {
      if (i === 0) { p.fill(x, y, 58, 16); p.text(name, x + 29, y + 1, { s: 2, align: "center", colour: null }); }
      else { p.frame(x, y, 58, 16); p.text(name, x + 29, y + 1, { s: 2, align: "center" }); }
    });
  },
  "beat-eighth": p => {
    p.text("BEAT", 4, 3, { s: 2 });
    let x = 4;
    for (const v of ["16", "32", "8T", "16T"]) { p.text(v, x + 1, 28); x += p.width(v) + 8; }
    p.fill(x - 2, 24, p.width("8", 2) + 6, 18);
    p.text("8", x + 1, 26, { s: 2, colour: null });
    p.text("160 BPM = 80", 64, 52, { align: "center" });
  },
  "touch-scale-zero": p => {
    p.text("TOUCH SCALE RANGE", 4, 3);
    p.text("0 Oct", 64, 14, { s: 2, align: "center" });
    p.frame(4, 34, 120, 22, 2);
    p.fill(60, 34, 2, 22);
    p.text("C4", 64, 41);
  },
  "exit-pad": p => {
    p.frame(0, 12, 52, 26, 2);
    p.text("EXIT", 26, 18, { s: 2, align: "center" });
    p.text("+", 59, 18, { s: 2, align: "center" });
    p.fill(66, 12, 62, 26);
    p.text("PAD", 97, 18, { s: 2, align: "center", colour: null });
    p.text("PART RESET", 64, 50, { align: "center" });
  },
  // drawn with the theme's own fonts and icons, so the picture shows what the patch changes
  theme: p => {
    const tab = themeText(p, "BLECH", 8, 14, 3, { colour: null }) + 10;
    p.fill(4, 3, tab, 15);
    for (let i = 0; i < 5; i++) p.clear(4 + tab - 5 + i, 3, 5 - i, 1 + i);
    themeText(p, "BLECH", 8, 14, 3, { colour: null });
    themeIcon(p, 6, 100, 6);
    themeIcon(p, 2, 112, 6);
    p.fill(4, 18, 120, 1);
    themeText(p, "Aa Qq 0123", 64, 34, 1, { align: "center" });
    themeText(p, "> < + - %", 64, 53, 0, { align: "center" });
  },
  "power-off": p => {
    p.text("BYE", 64, 8, { s: 2, align: "center" });
    p.fill(16, 34, 96, 2);
    p.fill(48, 32, 32, 6);
    p.fill(58, 30, 12, 10);
  },
  "poly-pink": p => {
    p.text("SEQUENCER", 4, 6);
    p.text("POLY", 124, 6, { align: "right" });
    const on = new Set([0, 3, 4, 8, 11, 12, 14]);
    const chord = new Set([0, 8, 12]);
    for (let i = 0; i < 16; i++) {
      const x = 6 + (i % 8) * 15, y = i < 8 ? 26 : 42;
      if (chord.has(i)) { p.frame(x, y, 12, 12); for (const r of [2, 5, 8]) p.fill(x + 3, y + r, 6, 2, PINK); }
      else if (on.has(i)) p.fill(x, y, 12, 12);
      else p.frame(x, y, 12, 12);
    }
  },
  "play-plugins": p => {
    p.text("PLUGINS", 4, 3, { s: 2 });
    p.fill(0, 19, W, 1);
    p.fill(0, 23, W, 11);
    p.text("> GATE HOLD", 4, 25, { colour: null });
    p.text("  MOMENTARY MUTE", 4, 39);
    p.text("  STEP COPY", 4, 52);
  },
  "rescue-switch": p => {
    p.fill(0, 10, 56, 26);
    p.text("EXIT", 28, 16, { s: 2, align: "center", colour: null });
    p.text("+", 66, 16, { s: 2, align: "center" });
    power(p, 100, 23, 12);
    p.text("ORIGINAL", 64, 50, { align: "center" });
  },
  "sample-errors": p => {
    p.frame(4, 4, 120, 56, 2);
    p.text("SAMPLE 503", 64, 12, { align: "center" });
    p.text("KICK.WAV", 64, 24, { align: "center" });
    p.fill(4, 34, 120, 1);
    p.text("BAD FORMAT", 64, 42, { align: "center" });
  },
  migrate: p => {
    p.text("COPY HACKTRIBE", 64, 8, { align: "center" });
    p.text("FOLDER?", 64, 20, { align: "center" });
    p.fill(6, 36, 54, 16);
    p.text("MENU", 33, 41, { align: "center", colour: null });
    p.frame(68, 36, 54, 16);
    p.text("EXIT", 95, 41, { align: "center" });
  },
  "usb-update": p => {
    p.text("USB UPDATE", 4, 3, { s: 2 });
    p.frame(4, 28, 120, 12, 2);
    p.fill(6, 30, 80, 8);
    p.text("70%", 64, 48, { align: "center" });
  },
  "auto-save": p => {
    p.frame(0, 12, 52, 26, 2);
    p.text("EXIT", 26, 18, { s: 2, align: "center" });
    arrow(p, 56, 24);
    p.fill(72, 12, 56, 26);
    p.text("SAVE", 100, 18, { s: 2, align: "center", colour: null });
    p.text("AUTO SAVE", 64, 50, { align: "center" });
  },
  backup: p => {
    p.text("EXPORT ALL", 4, 3, { s: 2 });
    p.fill(0, 19, W, 1);
    p.fill(0, 23, W, 11);
    p.text("> CUSTOMIZATIONS", 4, 25, { colour: null });
    p.text("  PLUGINS", 4, 39);
    p.text("  EFFECTS", 4, 52);
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
