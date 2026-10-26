import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyPatches } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { makeFirmware } from "./helpers.mjs";
import {
  ArtError, FONT_SHAPE, FONT_TABLE, IMAGE_TABLE, buildThemePatch, checkArt, parseGlyph, parseIcon, readFonts, readImages,
} from "../tools/patch/blech_theme.mjs";
import { FONT_ART } from "../tools/patch/blech_theme_art.mjs";

const load = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const theme = load("data/patches/blech-theme.json");
const RAM = 0xC0000000;
const file = ram => ram - RAM + 0x100;

// A firmware shaped like the measured one at the places the theme reads: four fonts with their glyphs and 19 images, all made up.
const IMAGE_SIZES = [[66, 64], [10, 8], [10, 8], [10, 8], [10, 8], [11, 8], [6, 8], [11, 16], [11, 16], [11, 16], [4, 8], [14, 8], [13, 8], [128, 64], [5, 8], [22, 8], [15, 8], [8, 8], [15, 8]];
async function makeThemedBase() {
  const bytes = await makeFirmware();
  const view = new DataView(bytes.buffer);
  const put32 = (ram, v) => view.setUint32(file(ram), v, true);
  let pool = 0xC0100000;
  const take = n => { const at = pool; pool += (n + 3) & ~3; return at; };
  FONT_SHAPE.forEach((shape, id) => {
    const codes = id === 0 ? [0, ...Array.from({ length: 96 }, (_, i) => 32 + i), 160]
      : id === 2 ? [...Array.from({ length: 128 }, (_, i) => i), ...Array.from({ length: 96 }, (_, i) => 160 + i)]
        : Array.from({ length: 95 }, (_, i) => 32 + i);
    assert.equal(codes.length, shape.count);
    const head = take(16);
    const array = take(4 * codes.length);
    put32(FONT_TABLE + 4 * id, head);
    put32(head + 4, shape.count);
    put32(head + 8, shape.height);
    put32(head + 12, array);
    codes.forEach((code, k) => {
      const desc = take(16);
      const data = take(9);
      put32(array + 4 * k, desc);
      put32(desc, code);
      put32(desc + 4, 7);
      put32(desc + 8, data);
      bytes.set([5, 9, 0, 0], file(desc + 0xC));
      bytes.fill(0xA5, file(data), file(data) + 9);
    });
  });
  IMAGE_SIZES.forEach(([w, h], n) => {
    const desc = take(12);
    const data = take(w * ((h + 7) >> 3));
    put32(IMAGE_TABLE + 4 * n, desc);
    put32(desc, w);
    put32(desc + 4, h);
    put32(desc + 8, data);
    bytes.fill(0x5A, file(data), file(data) + w * ((h + 7) >> 3));
  });
  return bytes;
}

test("the art is complete and every drawing is a well-formed glyph", () => {
  assert.deepEqual(checkArt(), []);
  for (const id of [0, 1, 2, 3]) assert.ok(Object.keys(FONT_ART[id]).length >= 95, `font ${id}`);
});

test("a glyph is cropped to its ink and packed with bit 7 on the left", () => {
  const g = parseGlyph([-2, ".#.", ".##"]);
  assert.deepEqual([g.w, g.h, g.xo, g.yo], [2, 2, 1, -2]);
  assert.deepEqual([...g.bytes], [0x80, 0xC0]);
  const wide = parseGlyph(["#########"]);
  assert.deepEqual([...wide.bytes], [0xFF, 0x80]);
  assert.throws(() => parseGlyph(["...", "#.."]), ArtError);
  assert.throws(() => parseGlyph(["#.", "#"]), ArtError);
});

test("an icon is packed in columns of eight rows, bit 7 on top", () => {
  const icon = parseIcon(["#.", "..", "..", "..", "..", "..", "..", "..", ".#"]);
  assert.deepEqual([icon.w, icon.h], [2, 9]);
  assert.deepEqual([...icon.bytes], [0x80, 0x00, 0x00, 0x80]);
});

test("the theme replaces glyph and icon bitmaps in place and leaves everything else", async () => {
  const base = await makeThemedBase();
  const fonts = readFonts(base);
  const images = readImages(base);
  const art = { 0: { A: ["#.#", "###", "#.#"] }, 1: {}, 2: {}, 3: {} };
  const battery = Array.from({ length: 8 }, (_, y) => (y === 0 ? "##########" : ".........."));
  const { patch } = buildThemePatch(base, { fontArt: art, iconArt: { 4: battery } });
  const res = await applyPatches(base, [patch]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const stock = fonts[0].glyphs.get(65);
  assert.deepEqual([...res.bytes.subarray(file(stock.data), file(stock.data) + 3)], [0xA0, 0xE0, 0xA0]);
  assert.deepEqual([...res.bytes.subarray(file(stock.desc + 0xC), file(stock.desc + 0x10))], [3, 3, 0, 0]);
  const changed = res.bytes.reduce((n, b, i) => n + (b !== base[i] ? 1 : 0), 0);
  assert.ok(changed <= 3 + 4 + images[4].size, `${changed} bytes changed`);
  assert.deepEqual([...res.bytes.subarray(file(images[4].data), file(images[4].data) + 10)], Array(10).fill(0x80));
  assert.ok(patch.startPhase.length >= 2, "fonts and the battery icon are read in the start");
});

test("a drawing that would move text or does not fit is refused", async () => {
  const base = await makeThemedBase();
  const build = art => buildThemePatch(base, { fontArt: art, iconArt: {} });
  assert.throws(() => build({ 0: { A: Array(10).fill("#") } }), /rises above|needs/);
  assert.throws(() => build({ 0: { A: [-1, "#"] } }), /sinks below/);
  assert.throws(() => build({ 0: { A: ["########"] } }), /advance/);
  assert.throws(() => build({ 0: { "é": ["#"] } }), /no such glyph/);
  assert.throws(() => buildThemePatch(base, { fontArt: {}, iconArt: { 4: ["##"] } }), /icon 4/);
});

test("the committed patch is a data patch with our bytes only and fits the set", () => {
  assert.equal(theme.id, "blech-theme");
  assert.equal(theme.format, "gelumpe-patch");
  assert.ok(theme.changes.length >= 100 && theme.changes.every(c => /^[0-9a-f]+$/.test(c.bytes) && /^[0-9a-f]{64}$/.test(c.expect) && c.copy === undefined));
  assert.equal(checkHooks([theme]).ok, true);
  const size = JSON.stringify(theme).length;
  assert.ok(size < 200_000, `${size} bytes`);
});

test("the committed patch is what the generator makes from the user's firmware", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, () => {
  const vsb = new Uint8Array(readFileSync(process.env.E2_VSB));
  assert.deepEqual(buildThemePatch(vsb).patch, theme, "rebuild with node tools/patch/blech_theme.mjs --vsb SYSTEM.VSB --out data/patches/blech-theme.json");
  // Where the drawing equals the firmware's for four bytes or more, the patch leaves the bytes out.
  for (const c of theme.changes) {
    const bytes = Buffer.from(c.bytes, "hex");
    let same = 0;
    for (let i = 0; i < bytes.length; i++) {
      same = vsb[c.file + i] === bytes[i] ? same + 1 : 0;
      assert.ok(same < 4, `firmware bytes at file 0x${(c.file + i).toString(16)}`);
    }
  }
});

test("the theme applies together with the BLECH set to the user's firmware", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, async () => {
  const patches = load("data/patches/blech.json").patches.map(load);
  assert.ok(patches.some(p => p.id === "blech-theme"));
  const res = await applyPatches(new Uint8Array(readFileSync(process.env.E2_VSB)), patches);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(res.allowCode.filter(([at]) => at >= file(0xC00C1CCC) && at < file(0xC00C5610)).length, 4);
});

test("every character the firmware prints has an entry in every font", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, () => {
  const vsb = readFileSync(process.env.E2_VSB);
  const used = new Set();
  // The firmware's text tables (docs/messungen/2026-10-14-display-schriften.md): UI strings, FX places, Hacktribe strings.
  for (const [from, to] of [[0xC00A3000, 0xC00A8000], [0xC00DA000, 0xC00DC000], [0xC011F000, 0xC0124000]]) {
    for (const m of vsb.subarray(file(from), file(to)).toString("latin1").matchAll(/[\x20-\x7e]{3,}/g)) for (const ch of m[0]) used.add(ch);
  }
  assert.ok(used.size >= 90, `${used.size} characters`);
  for (const [id, art] of Object.entries(FONT_ART)) {
    for (const ch of used) assert.ok(ch in art, `font ${id} has no entry for "${ch}"`);
  }
});

test("the synth theme uses its own measured font and image tables", async () => {
  const bytes = await makeThemedBase();
  bytes.set([0x45, 0x32, 0], 0x10);
  bytes.fill(0xff, 0x170100, 0x170140); // Korg's blue leaves Hacktribe's code run erased
  bytes.copyWithin(file(0xC00AD208), file(FONT_TABLE), file(FONT_TABLE) + 16);
  bytes.copyWithin(file(0xC00AC624), file(IMAGE_TABLE), file(IMAGE_TABLE) + 19 * 4);
  bytes.fill(0, file(FONT_TABLE), file(FONT_TABLE) + 16);
  bytes.fill(0, file(IMAGE_TABLE), file(IMAGE_TABLE) + 19 * 4);
  const { patch } = buildThemePatch(bytes, { fontArt: { 0: { A: ["#.#", "###", "#.#"] } }, iconArt: {} });
  assert.deepEqual(patch.builds, ["synth"]);
  const applied = await applyPatches(bytes, [patch]);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
  assert.deepEqual(applied.bytes.subarray(0, 0x100), bytes.subarray(0, 0x100));
  bytes.fill(0, file(0xC00AD208), file(0xC00AD208) + 16);
  assert.throws(() => buildThemePatch(bytes), ArtError);
});
