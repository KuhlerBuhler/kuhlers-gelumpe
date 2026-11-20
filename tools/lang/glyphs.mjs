#!/usr/bin/env node
/**
 * Adds ÄÖÜäöüß (our art, data/lang/glyphs/) to fonts 0, 1 and 3 without carrying firmware bytes: copies of the
 * font head and glyph array, our descriptors and bitmaps, and the font table word pointed at the copy.
 * The text function reads characters with ldrsb and searches the array signed, so the umlauts get negative
 * codes and go first (docs/messungen/2026-11-19-firmware-sprache.md).
 *
 * What it needs of the firmware (addresses, counts, the SHA-256 of the copied bytes, the spacing of the base letters)
 * is in data/lang/fonts.json, measured with --facts from each build's own file.
 *
 *   node tools/lang/glyphs.mjs --check | --facts hacktribe=HT.VSB stock=RED.VSB synth=BLUE.VSB
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { FONT_TABLE, parseGlyph, readFonts, tableFor } from "../patch/blech_theme.mjs";

const RAM = 0xC0000000;
const HEADER = 0x100;
export const LANG = 0xC016C000;   // tools/patch/script_hooks.py:LANG
export const LANG_END = 0xC0170000;
export const FONTS = [0, 1, 3];
/** Latin-1 code of each letter as the firmware's ldrsb sees it. */
export const CODES = { "Ä": -60, "Ö": -42, "Ü": -36, "ß": -33, "ä": -28, "ö": -10, "ü": -4 };
/** The letter whose spacing each new letter takes. */
const BASE = { "Ä": "A", "Ö": "O", "Ü": "U", "ä": "a", "ö": "o", "ü": "u", "ß": "b" };
/** Rows above the baseline of the tallest glyph per font, measured on all three builds (the art stays inside). */
export const TOP = { 0: 9, 1: 12, 3: 10 };

const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const hex = bytes => Buffer.from(bytes).toString("hex");
const le32 = n => { const b = new Uint8Array(4); new DataView(b.buffer).setInt32(0, n, true); return b; };
const fileOf = ram => ram - RAM + HEADER;

export class GlyphError extends Error {}

export const FACTS = new URL("../../data/lang/fonts.json", import.meta.url);

/** What the glyph changes need of a firmware file: per font its head, array and the spacing of the base letters. */
export function fontFacts(vsb) {
  const fonts = readFonts(vsb);
  const view = new DataView(vsb.buffer, vsb.byteOffset, vsb.byteLength);
  const table = tableFor(vsb, FONT_TABLE);
  const span = (ram, n) => sha(vsb.subarray(fileOf(ram), fileOf(ram) + n));
  return {
    fonts: Object.fromEntries(FONTS.map(f => {
      const font = fonts[f];
      const word = table + 4 * f;
      if (view.getUint32(fileOf(word), true) !== font.head) throw new GlyphError(`font ${f}: the table word does not point at its head`);
      const base = Object.fromEntries([...new Set(Object.values(BASE))].map(c => {
        const g = font.glyphs.get(c.charCodeAt(0));
        return [c, { adv: g.adv, xo: g.xo, w: g.w }];
      }));
      return [f, { word: hex32(word), head: hex32(font.head), headSha: span(font.head, 16), count: font.count,
        array: hex32(font.array), arraySha: span(font.array, 4 * font.count), base }];
    })),
  };
}

const hex32 = n => `0x${(n >>> 0).toString(16).padStart(8, "0")}`;

export function readFacts(build, path = FACTS) {
  const facts = JSON.parse(readFileSync(path, "utf8"))[build];
  if (!facts) throw new GlyphError(`no font facts for the build ${build} in data/lang/fonts.json`);
  return facts;
}

export function readArt(dir = new URL("../../data/lang/glyphs/", import.meta.url)) {
  return Object.fromEntries(FONTS.map(f => [f, JSON.parse(readFileSync(new URL(`font${f}.json`, dir), "utf8"))]));
}

/** Problems of the art alone: letters, format, height. */
export function checkArt(art) {
  const problems = [];
  for (const f of FONTS) {
    const font = art[f] ?? {};
    const keys = Object.keys(font).sort().join("");
    if (keys !== Object.keys(CODES).sort().join("")) problems.push(`font ${f}: letters ${keys}, expected ${Object.keys(CODES).join("")}`);
    const seen = new Map();
    for (const [key, entry] of Object.entries(font)) {
      try {
        const g = parseGlyph(entry, `font ${f} "${key}"`);
        if (g.h + g.yo > TOP[f]) problems.push(`font ${f} "${key}": ${g.h + g.yo} rows above the baseline, the font has ${TOP[f]}`);
        const look = g.rows.join("/");
        if (seen.has(look)) problems.push(`font ${f}: "${key}" looks like "${seen.get(look)}"`);
        seen.set(look, key);
      } catch (error) {
        problems.push(error.message);
      }
    }
  }
  return problems;
}

/**
 * The patch changes (src/patch.mjs) that add the letters to fonts 0, 1 and 3 of `vsb`, laid out from `at`.
 * @returns {{changes: object[], startPhase: object[], end: number}}
 */
export function glyphChanges(facts, art = readArt(), at = LANG) {
  const problems = checkArt(art);
  if (problems.length) throw new GlyphError(problems.join("\n"));
  const ff = n => sha(new Uint8Array(n).fill(0xFF));
  const changes = [];
  const startPhase = [];
  let cursor = at;
  const raw = (ram, bytes, expect = ff(bytes.length)) => changes.push({ file: fileOf(ram), bytes: hex(bytes), expect });
  const letters = Object.keys(CODES).sort((a, b) => CODES[a] - CODES[b]);
  for (const f of FONTS) {
    const fact = facts.fonts[f];
    const font = { head: Number(fact.head), array: Number(fact.array), count: fact.count };
    const head = cursor;
    const array = head + 16;
    const descs = array + 4 * (letters.length + font.count);
    let bitmap = descs + 16 * letters.length;
    const ours = new Uint8Array(16 * letters.length);
    const bitmaps = [];
    const pointers = new Uint8Array(4 * letters.length);
    letters.forEach((key, i) => {
      const g = parseGlyph(art[f][key], `font ${f} "${key}"`);
      const base = fact.base[BASE[key]];
      const adv = g.xo + g.w + (base.adv - base.xo - base.w);
      const d = new DataView(ours.buffer, 16 * i, 16);
      d.setInt32(0, CODES[key], true);
      d.setUint8(4, adv);
      d.setUint32(8, bitmap, true);
      d.setUint8(12, g.w);
      d.setUint8(13, g.h);
      d.setInt8(14, g.xo);
      d.setInt8(15, g.yo);
      pointers.set(le32(descs + 16 * i), 4 * i);
      bitmaps.push(g.bytes);
      bitmap += g.bytes.length;
    });
    const end = Math.ceil(bitmap / 4) * 4;
    if (end > LANG_END) throw new GlyphError(`the glyphs end at 0x${end.toString(16)}, past 0x${LANG_END.toString(16)}`);
    changes.push({
      file: fileOf(head), copy: { file: fileOf(font.head), length: 16, expect: fact.headSha },
      over: [{ at: 4, bytes: hex(le32(font.count + letters.length)) }, { at: 12, bytes: hex(le32(array)) }],
      expect: ff(16),
    });
    raw(array, pointers);
    const old = 4 * font.count;
    changes.push({
      file: fileOf(array + pointers.length), copy: { file: fileOf(font.array), length: old, expect: fact.arraySha },
      expect: ff(old),
    });
    const tail = new Uint8Array(end - descs);
    tail.set(ours, 0);
    let o = ours.length;
    for (const b of bitmaps) { tail.set(b, o); o += b.length; }
    raw(descs, tail);
    const word = Number(fact.word);
    raw(word, le32(head), sha(le32(font.head)));
    startPhase.push({ file: fileOf(word), length: 4, why: `the font table word of font ${f}: the start screen draws text` });
    startPhase.push({ file: fileOf(head), length: end - head, why: `the copy of font ${f} with the new letters: the start screen draws text with it` });
    cursor = end;
  }
  return { changes, startPhase, end: cursor };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const value = name => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
  const problems = checkArt(readArt());
  if (problems.length) {
    console.error(problems.join("\n"));
    process.exit(1);
  }
  if (args.includes("--check")) {
    console.log(`glyph art ok: ${Object.keys(CODES).length} letters in fonts ${FONTS.join(", ")}`);
  } else if (args[0] === "--facts" && args.length > 1) {
    const all = Object.fromEntries(args.slice(1).map(a => {
      const [build, path] = a.split("=");
      return [build, fontFacts(new Uint8Array(readFileSync(path)))];
    }));
    writeFileSync(FACTS, `${JSON.stringify(all, null, 1)}\n`);
    for (const build of Object.keys(all)) {
      const { end } = glyphChanges(all[build]);
      console.log(`${build}: glyphs from 0x${LANG.toString(16)} to 0x${end.toString(16)} (${end - LANG} bytes)`);
    }
  } else {
    console.error("usage: glyphs.mjs --check | --facts hacktribe=HT.VSB stock=RED.VSB synth=BLUE.VSB");
    process.exit(2);
  }
}
