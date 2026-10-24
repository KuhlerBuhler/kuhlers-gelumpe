#!/usr/bin/env node
/**
 * Build data/patches/blech-theme.json: the BLECH look for the device display. Our own glyph
 * and icon art (tools/patch/blech_theme_art.mjs) replaces the bitmaps of the firmware's four
 * fonts and of its status and tag icons, in place. It reads the VSB only for the addresses
 * the firmware keeps its font tables at and for the checksums of the bytes it replaces; no
 * firmware bytes go into the patch.
 *
 *   node tools/patch/blech_theme.mjs --vsb SYSTEM.VSB [--out data/patches/blech-theme.json]
 *   node tools/patch/blech_theme.mjs --vsb SYSTEM.VSB --report      what the art changes, glyph by glyph
 *   node tools/patch/blech_theme.mjs --check                        the art alone: format, character set, readability
 *
 * Layout facts and the reasons for every limit below are in docs/messungen/2026-10-14-display-schriften.md.
 * The firmware keeps each glyph as a descriptor (code, advance, pointer, width, height, offsets)
 * and a tightly packed bitmap; a themed glyph keeps its code, its advance and its place, gets its
 * own bitmap and, where the drawing is narrower or wider than the original, its own box. The
 * ink never leaves the rows of the original glyph and stays inside the advance, so no text
 * moves. A bitmap may not need more bytes than the slot it replaces.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { FONT_ART, ICON_ART } from "./blech_theme_art.mjs";
import { buildOf } from "../../src/firmware.mjs";
import { SAMPLER_OF_SYNTH } from "../../data/synth-sites.mjs";

const RAM = 0xC0000000;
const HEADER = 0x100;
const SIZE = 0x200100;
export const FONT_TABLE = 0xC00C2818;
export const IMAGE_TABLE = 0xC00C1C2C;
const SYNTH_OF_SAMPLER = new Map([...SAMPLER_OF_SYNTH].map(([synth, sampler]) => [sampler, synth]));
const tableFor = (vsb, address) => {
  if (buildOf(vsb) !== "synth") return address;
  const target = SYNTH_OF_SAMPLER.get(address);
  if (target === undefined) throw new ArtError(`no measured synth table for 0x${address.toString(16)}`);
  return target;
};
// The measured shape of the four fonts (docs/messungen/2026-10-14-display-schriften.md): glyph count and line height.
export const FONT_SHAPE = [{ count: 98, height: 8 }, { count: 95, height: 16 }, { count: 224, height: 12 }, { count: 95, height: 16 }];
const IMAGES = 19;
// The start image field and its size: no copy region may reach into it, the splash patch writes it.
const SPLASH = { start: 0xC00F9854, end: 0xC00F9854 + 1024 };
// Icons the firmware reads before the main screen (battery with one bar, EDIT tag; measured, same document).
const START_ICONS = new Set([4, 11]);
const ASCII_FIRST = 0x20;
const ASCII_LAST = 0x7E;

const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const hex = bytes => Buffer.from(bytes).toString("hex");

export class ArtError extends Error {}

/** A glyph or icon drawing: rows of "#" (ink) and "." (empty), top row first. */
function rowsOf(entry, where) {
  const rows = (Array.isArray(entry) ? entry : [entry]).filter(r => typeof r === "string");
  if (!rows.length) throw new ArtError(`${where}: no rows`);
  for (const r of rows) {
    if (!/^[#.]+$/.test(r)) throw new ArtError(`${where}: row "${r}" has characters other than # and .`);
    if (r.length !== rows[0].length) throw new ArtError(`${where}: rows differ in length`);
  }
  return rows;
}

/**
 * A font glyph from its art. An optional first number says how many rows the last row lies below the
 * baseline (as the firmware's y offset: g, p, q, y, j go -2). The box is the tight hull of the ink, the way
 * the firmware keeps it: leading empty columns become the x offset, rows may not be empty at the top or bottom.
 * @returns {{w: number, h: number, xo: number, yo: number, bytes: Uint8Array, rows: string[]}}
 */
export function parseGlyph(entry, where = "glyph") {
  const yo = typeof entry[0] === "number" ? entry[0] : 0;
  const rows = rowsOf(entry, where);
  if (!rows[0].includes("#") || !rows.at(-1).includes("#")) throw new ArtError(`${where}: the first and the last row need ink`);
  const left = Math.min(...rows.map(r => r.indexOf("#")).filter(i => i >= 0));
  const right = Math.max(...rows.map(r => r.lastIndexOf("#")));
  const w = right - left + 1;
  const h = rows.length;
  const stride = (w + 7) >> 3;
  const bytes = new Uint8Array(stride * h);
  rows.forEach((r, y) => {
    for (let x = 0; x < w; x++) if (r[left + x] === "#") bytes[y * stride + (x >> 3)] |= 0x80 >> (x & 7);
  });
  return { w, h, xo: left, yo, bytes, rows: rows.map(r => r.slice(left, right + 1)) };
}

/** An icon from its art: columns of pages of eight rows, bit 7 the top row of a page (the firmware's bitmap format). */
export function parseIcon(entry, where = "icon") {
  const rows = rowsOf(entry, where);
  const w = rows[0].length;
  const h = rows.length;
  const bytes = new Uint8Array(w * ((h + 7) >> 3));
  rows.forEach((r, y) => {
    for (let x = 0; x < w; x++) if (r[x] === "#") bytes[(y >> 3) * w + x] |= 0x80 >> (y & 7);
  });
  return { w, h, bytes, rows };
}

const codeOf = key => {
  if ([...key].length !== 1) throw new ArtError(`font art key "${key}" is not one character`);
  return key.codePointAt(0);
};

// ---- the firmware's tables, read from a VSB -------------------------------------------------------------
function reader(vsb) {
  if (vsb.length !== SIZE) throw new ArtError(`a VSB has 0x${SIZE.toString(16)} bytes, this one has ${vsb.length}`);
  const view = new DataView(vsb.buffer, vsb.byteOffset, vsb.byteLength);
  const at = ram => {
    const file = ram - RAM + HEADER;
    if (file < HEADER || file + 16 > SIZE) throw new ArtError(`0x${ram.toString(16)} is outside the image`);
    return file;
  };
  return {
    u32: ram => view.getUint32(at(ram), true),
    u8: ram => view.getUint8(at(ram)),
    i8: ram => view.getInt8(at(ram)),
    slice: (ram, n) => vsb.subarray(ram - RAM + HEADER, ram - RAM + HEADER + n),
  };
}

/** The four fonts: head, glyph table, and the span of descriptors and bitmaps. */
export function readFonts(vsb) {
  const r = reader(vsb);
  return FONT_SHAPE.map((shape, id) => {
    const head = r.u32(tableFor(vsb, FONT_TABLE) + 4 * id);
    const count = r.u32(head + 4);
    const height = r.u32(head + 8);
    const array = r.u32(head + 12);
    if (count !== shape.count || height !== shape.height) throw new ArtError(`font ${id}: ${count} glyphs of height ${height}, expected ${shape.count} of ${shape.height}: not the measured firmware`);
    const glyphs = new Map();
    let lo = Infinity;
    let hi = 0;
    for (let k = 0; k < count; k++) {
      const desc = r.u32(array + 4 * k);
      const w = r.u8(desc + 0xC);
      const h = r.u8(desc + 0xD);
      const g = { desc, code: r.u32(desc), adv: r.u8(desc + 4), data: r.u32(desc + 8), w, h, xo: r.i8(desc + 0xE), yo: r.i8(desc + 0xF), size: ((w + 7) >> 3) * h };
      if (glyphs.has(g.code)) throw new ArtError(`font ${id}: code ${g.code} twice`);
      glyphs.set(g.code, g);
      lo = Math.min(lo, desc, g.data);
      hi = Math.max(hi, desc + 16, g.data + g.size);
    }
    return { id, head, count, height, array, glyphs, lo, hi };
  });
}

/** The image table: number, descriptor, size and the address of the bitmap. */
export function readImages(vsb) {
  const r = reader(vsb);
  return Array.from({ length: buildOf(vsb) === "synth" ? 17 : IMAGES }, (_, n) => {
    const desc = r.u32(tableFor(vsb, IMAGE_TABLE) + 4 * n);
    const w = r.u32(desc);
    const h = r.u32(desc + 4);
    return { n, desc, w, h, data: r.u32(desc + 8), size: w * ((h + 7) >> 3) };
  });
}

// ---- the plan: what is written where ---------------------------------------------------------------------
/** Raw changes (src/patch.mjs) for writes at offsets `at` from the address `lo`; touching writes become one. */
function rawChanges(vsb, lo, overs) {
  const sorted = [...overs].sort((a, b) => a.at - b.at);
  const merged = [];
  for (const o of sorted) {
    const last = merged.at(-1);
    if (last && o.at < last.at + last.bytes.length) throw new ArtError(`two writes overlap at 0x${(lo + o.at).toString(16)}`);
    if (last && o.at === last.at + last.bytes.length) last.bytes = Uint8Array.from([...last.bytes, ...o.bytes]);
    else merged.push({ at: o.at, bytes: o.bytes });
  }
  return merged.flatMap(o => {
    const file = lo - RAM + HEADER + o.at;
    return changedRuns(vsb.subarray(file, file + o.bytes.length), o.bytes).map(([from, to]) =>
      ({ file: file + from, bytes: hex(o.bytes.subarray(from, to)), expect: sha(vsb.subarray(file + from, file + to)) }));
  });
}

/** Stretches of `next` that differ from `was`; equal stretches of MIN_SAME bytes or more stay out, no firmware bytes in the patch. */
const MIN_SAME = 4;
function changedRuns(was, next) {
  const runs = [];
  for (let i = 0; i < next.length; i++) {
    if (was[i] === next[i]) continue;
    const last = runs.at(-1);
    if (last && i - last[1] < MIN_SAME) last[1] = i + 1;
    else runs.push([i, i + 1]);
  }
  return runs;
}

/** What the art does to one font: the writes, plus a line per glyph for the report. */
export function planFont(font, art) {
  const overs = [];
  const lines = [];
  const problems = [];
  for (const [key, entry] of Object.entries(art)) {
    if (entry === null) continue;
    const where = `font ${font.id} "${key}"`;
    try {
      const stock = font.glyphs.get(codeOf(key));
      if (!stock) throw new ArtError(`${where}: the font has no such glyph`);
      const g = parseGlyph(entry, where);
      if (g.h + g.yo > stock.h + stock.yo) throw new ArtError(`${where}: rises above the original (top ${g.h + g.yo} rows over the baseline, original ${stock.h + stock.yo})`);
      if (g.yo < stock.yo) throw new ArtError(`${where}: sinks below the original (${g.yo}, original ${stock.yo})`);
      const room = Math.max(stock.adv - 1, stock.xo + stock.w);
      if (g.xo + g.w > room) throw new ArtError(`${where}: ink reaches column ${g.xo + g.w}, the advance ${stock.adv} leaves ${room}`);
      if (g.bytes.length > stock.size) throw new ArtError(`${where}: needs ${g.bytes.length} bytes, the slot has ${stock.size}`);
      overs.push({ at: stock.data, bytes: g.bytes });
      const same = g.w === stock.w && g.h === stock.h && g.xo === stock.xo && g.yo === stock.yo;
      if (!same) overs.push({ at: stock.desc + 0xC, bytes: Uint8Array.of(g.w, g.h, g.xo & 0xFF, g.yo & 0xFF) });
      lines.push({ key, box: `${g.w}x${g.h}@${g.xo},${g.yo}`, was: `${stock.w}x${stock.h}@${stock.xo},${stock.yo}`, adv: stock.adv, same, bytes: `${g.bytes.length}/${stock.size}` });
    } catch (error) {
      if (!(error instanceof ArtError)) throw error;
      problems.push(error.message);
    }
  }
  if (problems.length) throw new ArtError(problems.join("\n"));
  return { overs, lines };
}

/** Groups of icons whose bitmaps lie together and not across the start image. */
function iconGroups(icons, splash = SPLASH) {
  const sorted = [...icons].sort((a, b) => a.data - b.data);
  const groups = [];
  for (const icon of sorted) {
    const last = groups.at(-1);
    const crossesSplash = last && last.lo < splash.start && icon.data + icon.size > splash.start;
    if (last && !crossesSplash && icon.data - last.hi < 64) {
      last.icons.push(icon);
      last.hi = Math.max(last.hi, icon.data + icon.size);
    } else groups.push({ lo: icon.data, hi: icon.data + icon.size, icons: [icon] });
  }
  for (const g of groups) {
    if (g.lo < splash.end && g.hi > splash.start) throw new ArtError(`icon bitmaps 0x${g.lo.toString(16)} to 0x${g.hi.toString(16)} reach into the start image`);
  }
  return groups;
}

/** The theme as a patch (src/patch.mjs, format gelumpe-patch 1) for this VSB, with a report. */
export function buildThemePatch(vsb, { fontArt = FONT_ART, iconArt = ICON_ART } = {}) {
  const fonts = readFonts(vsb);
  const images = readImages(vsb);
  if (buildOf(vsb) === "synth" && iconArt === ICON_ART) {
    iconArt = Object.fromEntries(Object.entries(iconArt).filter(([n]) => Number(n) < 17));
  }
  const changes = [];
  const startPhase = [];
  const report = { fonts: [], icons: [] };
  const span = (lo, hi, why) => startPhase.push({ file: lo - RAM + HEADER, length: hi - lo, why });
  for (const font of fonts) {
    const art = fontArt[font.id];
    if (!art || !Object.keys(art).length) continue;
    const plan = planFont(font, art);
    changes.push(...rawChanges(vsb, font.lo, plan.overs.map(o => ({ ...o, at: o.at - font.lo }))));
    // Every font draws text in the start: the main screen, the update offer, the start modes.
    span(font.lo, font.hi, `the firmware draws text with font ${font.id} while it starts (main screen, update offer, start modes); the theme replaces glyph bitmaps in place and leaves codes, advances, tables and pointers as they are`);
    report.fonts.push({ id: font.id, glyphs: plan.lines });
  }
  const themed = Object.keys(iconArt).map(Number).map(n => {
    const image = images[n];
    if (!image) throw new ArtError(`icon ${n}: the firmware has no such image`);
    const icon = parseIcon(iconArt[n], `icon ${n}`);
    if (icon.w !== image.w || icon.h !== image.h) throw new ArtError(`icon ${n}: ${icon.w}x${icon.h}, the firmware's image is ${image.w}x${image.h}`);
    return { ...image, icon };
  });
  const splash = images[13];
  for (const group of iconGroups(themed, { start: splash.data, end: splash.data + splash.size })) {
    changes.push(...rawChanges(vsb, group.lo, group.icons.map(i => ({ at: i.data - group.lo, bytes: i.icon.bytes }))));
    if (group.icons.some(i => START_ICONS.has(i.n))) {
      span(group.lo, group.hi, "the firmware draws the battery and the EDIT tag while the main screen builds; the theme replaces their bitmaps in place, same size, same pointers");
    }
    report.icons.push(...group.icons.map(i => ({ n: i.n, box: `${i.w}x${i.h}`, bytes: i.size })));
  }
  const patch = { format: "gelumpe-patch", version: 1, id: "blech-theme", name: "BLECH Theme: Schriften und Symbole", builds: buildOf(vsb) === "synth" ? ["synth"] : ["hacktribe", "stock"], changes, startPhase, ram: [] };
  return { patch, report };
}

// ---- checks that need no firmware -------------------------------------------------------------------------
/**
 * Art-only checks: every drawing parses, every printable ASCII character (but the untouched ones) has a
 * glyph in every font, no two characters of a font look the same, and the pairs that get mixed up on a
 * small display stay apart by at least `minDiff` pixels.
 */
export function checkArt({ fontArt = FONT_ART, iconArt = ICON_ART } = {}) {
  const problems = [];
  const confusable = [["O", "0"], ["O", "Q"], ["O", "D"], ["I", "l", 1], ["I", "1"], ["l", "1"], ["l", "|"], ["I", "|"], ["S", "5"], ["B", "8"], ["Z", "2"], ["G", "6"], ["g", "9"], ["u", "v"], ["U", "V"], ["a", "e"], ["c", "e"], ["n", "h"], ["n", "r"], ["i", "j"], [",", "."], [";", ":"], ["'", "`"], ["(", "["], [")", "]"], ["{", "("], ["}", ")"], ["-", "_"]];
  for (const [id, art] of Object.entries(fontArt)) {
    const parsed = new Map();
    for (const [key, entry] of Object.entries(art)) {
      if (entry === null) continue;
      try { parsed.set(key, parseGlyph(entry, `font ${id} "${key}"`)); } catch (e) { problems.push(e.message); }
    }
    for (let c = ASCII_FIRST; c <= ASCII_LAST; c++) {
      const ch = String.fromCharCode(c);
      if (!(ch in art)) problems.push(`font ${id}: "${ch}" is neither drawn nor marked null`);
    }
    const keys = [...parsed.keys()];
    keys.forEach((a, i) => keys.slice(i + 1).forEach(b => {
      if (pixelDistance(parsed.get(a), parsed.get(b)) === 0) problems.push(`font ${id}: "${a}" and "${b}" look the same`);
    }));
    for (const [a, b, least = 2] of confusable) {
      const x = parsed.get(a);
      const y = parsed.get(b);
      if (x && y && pixelDistance(x, y) < least) problems.push(`font ${id}: "${a}" and "${b}" differ by less than ${least} pixels`);
    }
  }
  for (const [n, entry] of Object.entries(iconArt)) {
    try { parseIcon(entry, `icon ${n}`); } catch (e) { problems.push(e.message); }
  }
  return problems;
}

/** Number of pixels that differ when two glyphs sit on the same baseline, left aligned at their offsets. */
export function pixelDistance(a, b) {
  const cells = g => {
    const set = new Set();
    g.rows.forEach((row, y) => [...row].forEach((c, x) => { if (c === "#") set.add(`${g.xo + x},${g.h + g.yo - 1 - y}`); }));
    return set;
  };
  const sa = cells(a);
  const sb = cells(b);
  let d = 0;
  for (const p of sa) if (!sb.has(p)) d++;
  for (const p of sb) if (!sa.has(p)) d++;
  return d;
}

// ---- command line -------------------------------------------------------------------------------------------
function main() {
  const args = process.argv.slice(2);
  const take = name => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
  if (args.includes("--check")) {
    const problems = checkArt();
    for (const p of problems) console.error(p);
    console.log(problems.length ? `${problems.length} problems` : "art is fine");
    process.exit(problems.length ? 1 : 0);
  }
  const vsbPath = take("--vsb") ?? process.env.E2_VSB;
  if (!vsbPath) {
    console.error("usage: blech_theme.mjs --vsb SYSTEM.VSB [--out data/patches/blech-theme.json] [--report] | --check");
    process.exit(2);
  }
  const vsb = new Uint8Array(readFileSync(vsbPath));
  let built;
  try {
    built = buildThemePatch(vsb);
  } catch (error) {
    if (!(error instanceof ArtError)) throw error;
    console.error(error.message);
    process.exit(1);
  }
  const { patch, report } = built;
  if (args.includes("--report")) {
    for (const f of report.fonts) {
      const moved = f.glyphs.filter(g => !g.same);
      console.log(`font ${f.id}: ${f.glyphs.length} glyphs, ${moved.length} with another box`);
      for (const g of moved) console.log(`  "${g.key}" ${g.was} -> ${g.box} (advance ${g.adv}, ${g.bytes} bytes)`);
    }
    for (const i of report.icons) console.log(`icon ${i.n}: ${i.box}, ${i.bytes} bytes`);
    return;
  }
  const text = `${JSON.stringify(patch, null, 1)}\n`;
  if (take("--out")) {
    writeFileSync(take("--out"), text);
    console.log(`wrote ${take("--out")} (${text.length} bytes, ${patch.changes.length} changes)`);
  } else process.stdout.write(text);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
