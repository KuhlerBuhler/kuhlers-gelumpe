#!/usr/bin/env node
/**
 * Build assets/blechy/theme-preview.png: key screens of the BLECH firmware with and without the
 * theme, side by side, and every printable character of the four fonts, all rendered by the
 * firmware in the emulator (tools/emu/theme_screens.py). Needs your own SYSTEM.VSB and the emulator setup.
 *
 *   E2_VSB=SYSTEM.VSB node tools/patch/blech_theme_preview.mjs [--flash dump.bin] [--out assets/blechy/theme-preview.png] [--compare dist-release/theme-compare.png]
 *
 * The preview in --out shows only the themed screens, drawn with our glyphs and icons. --compare also shows the
 * firmware's own text on the left; that sheet holds Korg's glyph bitmaps and stays out of the repository.
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { applyPatches } from "../../src/patch.mjs";
import { FONT_ART } from "./blech_theme_art.mjs";
import { parseGlyph } from "./blech_theme.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const INK = [0x10, 0x14, 0x10];
const LCD = [0xd6, 0xde, 0xcf];
const PAGE = [0x1b, 0x1d, 0x1f];
const LABEL = [0xe8, 0xea, 0xe6];
const SCALE = 3;

// ---- a tiny canvas and PNG writer --------------------------------------------------------------------------
class Canvas {
  constructor(w, h, fill) {
    this.w = w;
    this.h = h;
    this.px = new Uint8Array(w * h * 3);
    for (let i = 0; i < w * h; i++) this.px.set(fill, i * 3);
  }
  rect(x, y, w, h, color) {
    for (let j = Math.max(0, y); j < Math.min(this.h, y + h); j++) for (let i = Math.max(0, x); i < Math.min(this.w, x + w); i++) this.px.set(color, (j * this.w + i) * 3);
  }
  /** A 128 x 64 frame (page-major bytes, bit 0 the top row) at scale, dark pixels on the LCD colour. */
  frame(hex, x, y, scale = SCALE) {
    const raw = Buffer.from(hex, "hex");
    this.rect(x, y, 128 * scale, 64 * scale, LCD);
    for (let py = 0; py < 64; py++) for (let px = 0; px < 128; px++) if ((raw[(py >> 3) * 128 + px] >> (py & 7)) & 1) this.rect(x + px * scale, y + py * scale, scale, scale, INK);
  }
  /** Text in our own font 0 (the labels), one pixel per art pixel at `scale`. */
  text(str, x, y, color, scale = 2) {
    let pen = x;
    for (const ch of str) {
      const art = FONT_ART[0][ch];
      if (!art) { pen += 4 * scale; continue; }
      const g = parseGlyph(art);
      const bottom = y + 6 * scale - g.yo * scale;
      g.rows.forEach((row, r) => [...row].forEach((c, k) => { if (c === "#") this.rect(pen + (g.xo + k) * scale, bottom - (g.h - 1 - r) * scale, scale, scale, color); }));
      pen += (g.xo + g.w + 1) * scale;
    }
    return pen;
  }
  png() {
    const rows = Buffer.alloc((this.w * 3 + 1) * this.h);
    for (let y = 0; y < this.h; y++) {
      rows[y * (this.w * 3 + 1)] = 0;
      rows.set(this.px.subarray(y * this.w * 3, (y + 1) * this.w * 3), y * (this.w * 3 + 1) + 1);
    }
    const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
    const crc = buf => { let c = 0xFFFFFFFF; for (const b of buf) c = crcTable[(c ^ b) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
    const chunk = (type, data) => {
      const head = Buffer.alloc(8);
      head.writeUInt32BE(data.length, 0);
      head.write(type, 4, "latin1");
      const tail = Buffer.alloc(4);
      tail.writeUInt32BE(crc(Buffer.concat([head.subarray(4), data])), 0);
      return Buffer.concat([head, data, tail]);
    };
    const ihdr = Buffer.alloc(13);
    ihdr.writeUInt32BE(this.w, 0);
    ihdr.writeUInt32BE(this.h, 4);
    ihdr.set([8, 2, 0, 0, 0], 8);
    return Buffer.concat([Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(rows, { level: 9 })), chunk("IEND", Buffer.alloc(0))]);
  }
}

/**
 * The preview sheet from the screens and specimens theme_screens.py returns. With `compare` every screen
 * and specimen shows the firmware's own fonts on the left; without, only the themed side is drawn, so the
 * sheet holds none of the firmware's glyph bitmaps and may go into the repository.
 */
export function renderPreview({ scenes, specimens }, { compare = false } = {}) {
  const tile = 128 * SCALE;
  const gap = 12;
  const unit = compare ? tile * 2 + gap : tile;
  const cols = compare ? 2 : 3;
  const width = cols * unit + (cols + 1) * 24;
  const sceneRows = Math.ceil(scenes.length / cols);
  const rowH = 64 * SCALE + 30;
  const fonts = Object.keys(specimens);
  const specCols = compare ? 1 : 3;
  const specH = fonts.reduce((n, f) => n + Math.ceil(specimens[f].b.length / specCols) * (64 * SCALE + gap) + 34, 0);
  const canvas = new Canvas(width, 90 + sceneRows * rowH + 60 + specH + 20, PAGE);
  const accent = [0x9e, 0xc3, 0xd1];
  canvas.text("BLECH THEME", 24, 18, LABEL, 4);
  canvas.text(compare ? "left: BLECH with the firmware's own fonts, right: with the theme (emulator, not the device)" : "key screens with the theme (emulator, not the device)", 24, 52, accent, 2);
  scenes.forEach((s, i) => {
    const x = 24 + (i % cols) * (unit + 24);
    const y = 90 + Math.floor(i / cols) * rowH;
    canvas.text(s.name, x, y, LABEL, 2);
    if (compare) canvas.frame(s.a, x, y + 22);
    canvas.frame(s.b, compare ? x + tile + gap : x, y + 22);
  });
  let y = 90 + sceneRows * rowH + 10;
  canvas.text(compare ? "every printable character, drawn by the firmware (left without, right with the theme)" : "every printable character of the four fonts", 24, y, accent, 2);
  y += 54;
  for (const f of fonts) {
    canvas.text(`font ${f}`, 24, y - 22, LABEL, 2);
    const list = specimens[f].b;
    list.forEach((b, k) => {
      const x = 24 + (compare ? 0 : (k % specCols) * (unit + 24));
      const yy = y + (compare ? k : Math.floor(k / specCols)) * (64 * SCALE + gap);
      if (compare) canvas.frame(specimens[f].a[k], x, yy);
      canvas.frame(b, compare ? x + tile + gap : x, yy);
    });
    y += (compare ? list.length : Math.ceil(list.length / specCols)) * (64 * SCALE + gap) + 34;
  }
  return canvas.png();
}

async function main() {
  const args = process.argv.slice(2);
  const take = name => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
  const vsbPath = take("--vsb") ?? process.env.E2_VSB;
  if (!vsbPath) {
    console.error("usage: blech_theme_preview.mjs --vsb SYSTEM.VSB [--flash dump.bin] [--out assets/blechy/theme-preview.png]");
    process.exit(2);
  }
  const flash = take("--flash") ?? process.env.E2_FLASH;
  const out = take("--out") ?? join(root, "assets/blechy/theme-preview.png");
  const load = path => JSON.parse(readFileSync(join(root, path), "utf8"));
  const set = load("data/patches/blech.json");
  const patches = set.patches.map(load);
  const theme = load("data/patches/blech-theme.json");
  const vsb = new Uint8Array(readFileSync(vsbPath));
  const without = await applyPatches(vsb, patches.filter(p => p.id !== "blech-theme"));
  const withTheme = await applyPatches(vsb, [...patches.filter(p => p.id !== "blech-theme"), theme]);
  for (const r of [without, withTheme]) if (!r.ok) { console.error(r.reasons.join("\n")); process.exit(1); }
  const dir = mkdtempSync(join(tmpdir(), "blech-theme-"));
  try {
    writeFileSync(join(dir, "a.VSB"), without.bytes);
    writeFileSync(join(dir, "b.VSB"), withTheme.bytes);
    const venv = join(root, "tools/emu/.venv/bin/python");
    const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
    const run = spawnSync(python, [join(root, "tools/emu/theme_screens.py"), "--a", join(dir, "a.VSB"), "--b", join(dir, "b.VSB"), ...(flash ? ["--flash", flash] : [])],
      { encoding: "utf8", maxBuffer: 1 << 28, timeout: 1_800_000 });
    if (run.error || run.status) { console.error(run.error?.message ?? run.stderr); process.exit(1); }
    const shown = JSON.parse(run.stdout);
    writeFileSync(out, renderPreview(shown));
    console.log(`wrote ${out}`);
    if (take("--compare")) {
      writeFileSync(take("--compare"), renderPreview(shown, { compare: true }));
      console.log(`wrote ${take("--compare")} (with the firmware's own glyphs: keep it out of the repository)`);
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
