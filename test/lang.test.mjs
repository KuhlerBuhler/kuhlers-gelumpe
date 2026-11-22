import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import "./support/runtime.mjs";
import { applyPatches } from "../src/patch.mjs";
import { addRelease, emptyKnown, recogniseBlech } from "../src/blech-update.mjs";
import { buildOf } from "../src/firmware.mjs";
import { LANG_DE_URLS, optionFor } from "../src/patcher.mjs";
import {
  badCharacters, englishKeys, entryProblems, langFileProblems, placeholders, samePlaceholders, termForms, unknownAbbreviations,
} from "../src/lang.mjs";
import { CODES, FONTS, LANG, LANG_END, TOP, checkArt, fontFacts, glyphChanges, readArt } from "../tools/lang/glyphs.mjs";
import { FONT_SHAPE, FONT_TABLE, readFonts } from "../tools/patch/blech_theme.mjs";
import { makeFirmware } from "./helpers.mjs";

// The language files and the rules of docs/firmware-sprache.md, without the emulator.
const load = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const abbreviations = load("data/lang/de-abk.json").abbreviations;
const glossary = load("data/lang/de-glossar.json");
const context = { abbreviations, glossary };
const RAM = 0xC0000000;
const file = ram => ram - RAM + 0x100;

test("every language file in data/lang/de passes its checks", () => {
  const names = readdirSync(new URL("../data/lang/de/", import.meta.url)).filter(n => n.endsWith(".json"));
  assert.deepEqual(names.sort(), ["blech.json", "korg-hacktribe.json", "korg-stock.json", "korg-synth.json"]);
  for (const name of names) assert.deepEqual(langFileProblems(name, load(`data/lang/de/${name}`), context), []);
});

test("abbreviations, glossary and glyph art carry no English keys and stay consistent", () => {
  for (const path of ["data/lang/de-abk.json", "data/lang/de-glossar.json"]) assert.deepEqual(englishKeys(load(path)), [], path);
  for (const a of abbreviations) {
    assert.match(a.short, /\.$/, `${a.short} ends with a dot`);
    assert.deepEqual(unknownAbbreviations(`${a.example} x`, abbreviations), [], a.example);
  }
  assert.equal(new Set(abbreviations.map(a => a.short)).size, abbreviations.length, "each abbreviation once");
  const forms = Object.values(glossary.terms);
  for (const form of forms) assert.deepEqual(badCharacters(form), [], form);
  assert.deepEqual(checkArt(readArt()), []);
});

test("the character set is printable ASCII and ÄÖÜäöüß", () => {
  assert.deepEqual(badCharacters("Größe: Übersicht, ä/ö/ü %d"), []);
  assert.deepEqual(badCharacters("Café – é\n"), ["é", "–", "\n"]);
});

test("placeholders must match in number and order", () => {
  assert.deepEqual(placeholders("MFX:%s %3d %-02.1f 100%%"), ["%s", "%3d", "%-02.1f", "%%"]);
  assert.equal(samePlaceholders("Pitch:%d %s", "Tonhöhe:%d %s"), true);
  assert.equal(samePlaceholders("%d of %s", "%s von %d"), false);
  assert.equal(samePlaceholders("%d", "%d %d"), false);
});

test("a word with a dot needs the abbreviation list, a sentence end and an ellipsis do not", () => {
  assert.deepEqual(unknownAbbreviations("MIDI-Einst. Nr. 3", abbreviations), []);
  assert.deepEqual(unknownAbbreviations("Pattern gesperrt.", abbreviations), []);
  assert.deepEqual(unknownAbbreviations("Läuft...", abbreviations), []);
  assert.deepEqual(unknownAbbreviations("EINST.-EXPORT, kein e2sFx.all", abbreviations), []);
  assert.deepEqual(unknownAbbreviations("Ldg. Pattern", abbreviations), ["Ldg."]);
});

test("an entry has a text or a reason to stay English, and keeps the glossary", () => {
  assert.deepEqual(entryProblems("a", { text: "Datei bleibt auf Karte", glossar: ["file", "card"] }, context), []);
  assert.deepEqual(entryProblems("b", { keep: "no room: 3 px over" }, context), []);
  assert.match(entryProblems("c", {}, context)[0], /either text or keep/);
  assert.match(entryProblems("d", { text: "x", keep: "y" }, context)[0], /either text or keep/);
  assert.match(entryProblems("e", { text: "Muster kopieren", glossar: ["copy"] }, context)[0], /must read "Kopie"/);
  assert.match(entryProblems("f", { text: "x", glossar: ["nope"] }, context)[0], /does not exist/);
  assert.deepEqual(termForms("settings", glossary, abbreviations), ["Einstellungen", "Einst."]);
  assert.deepEqual(entryProblems("g", { text: "MIDI-Einst.", glossar: ["settings"] }, context), []);
});

test("a language file refuses English text, a wrong format and malformed Korg entries", () => {
  const korg = (texts, extra = {}) => ({ format: "gelumpe-lang-korg", version: 1, lang: "de", build: "hacktribe", texts, ...extra });
  const good = { text: "Import", fonts: [3], length: 6, expect: "a".repeat(64), pointers: [{ at: "0xc00c1000", expect: "b".repeat(64) }], space: 120, buffer: null };
  assert.deepEqual(langFileProblems("k", korg({ "0xc00a3010": good }), context), []);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, en: "IMPORT" } }), context).join("\n"), /no English text/);
  assert.match(langFileProblems("k", korg({}, { english: {} }), context).join("\n"), /no English text/);
  assert.match(langFileProblems("k", korg({ "C00A3010": good }), context).join("\n"), /template address/);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, fonts: [4] } }), context).join("\n"), /fonts lists/);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, text: "Lösch", fonts: [2] } }), context).join("\n"), /no umlauts/);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, text: "Importieren" } }), context).join("\n"), /longer than the old text/);
  assert.deepEqual(langFileProblems("k", korg({ "0xc00a3010": { ...good, text: "Importieren", buffer: 32 } }), context), []);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, text: "Importieren", buffer: 8 } }), context).join("\n"), /buffer holds 7/);
  assert.deepEqual(langFileProblems("k", korg({ "0xc00a3010": { ...good, text: "Importieren", buffer: "string" } }), context), []);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, buffer: "str" } }), context).join("\n"), /positive whole number/);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, expect: "x" } }), context).join("\n"), /expect is the SHA-256/);
  assert.match(langFileProblems("k", korg({ "0xc00a3010": { ...good, space: -1 } }), context).join("\n"), /space is a positive/);
  const field = { ...good, text: "Tempo", length: 5, pointers: [], inPlace: true };
  assert.deepEqual(langFileProblems("k", korg({ "0xc011f0c0": field }), context), []);
  assert.match(langFileProblems("k", korg({ "0xc011f0c0": { ...field, text: "Geschwindigkeit" } }), context).join("\n"), /longer than the old text/);
  assert.match(langFileProblems("k", korg({ "0xc011f0c0": { ...field, pointers: good.pointers } }), context).join("\n"), /no pointer words/);
  assert.match(langFileProblems("k", korg({ "0xc011f0c0": { ...field, inPlace: "yes" } }), context).join("\n"), /inPlace is true/);
  assert.match(langFileProblems("x", { format: "other", texts: {} }, context).join("\n"), /format is not/);
  const blech = { format: "gelumpe-lang-blech", version: 1, texts: { "str-bad": { text: "x" } } };
  assert.match(langFileProblems("b", blech, context).join("\n"), /label of the text/);
});

// Four made-up fonts at the measured places, shaped like the firmware's: codes, 9-byte bitmaps.
async function fontBase() {
  const bytes = await makeFirmware();
  const view = new DataView(bytes.buffer);
  const put32 = (ram, v) => view.setUint32(file(ram), v, true);
  let pool = 0xC0100000;
  const take = n => { const at = pool; pool += (n + 3) & ~3; return at; };
  FONT_SHAPE.forEach((shape, id) => {
    const codes = id === 0 ? [0, ...Array.from({ length: 96 }, (_, i) => 32 + i), 160]
      : id === 2 ? [...Array.from({ length: 128 }, (_, i) => i), ...Array.from({ length: 96 }, (_, i) => 160 + i)]
        : Array.from({ length: 95 }, (_, i) => 32 + i);
    const head = take(16);
    const array = take(4 * codes.length);
    put32(FONT_TABLE + 4 * id, head);
    put32(head, codes[0]);
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
    });
  });
  bytes.fill(0xFF, file(LANG), file(LANG_END));
  return bytes;
}

test("the glyph changes add ÄÖÜäöüß to fonts 0, 1 and 3 with copies, and carry no firmware bytes", async () => {
  const base = await fontBase();
  const before = readFonts(base);
  const { changes, startPhase, end } = glyphChanges(fontFacts(base));
  assert.ok(end <= LANG_END, `ends at 0x${end.toString(16)}`);
  const written = changes.filter(c => c.bytes !== undefined).map(c => Buffer.from(c.bytes, "hex"));
  for (const f of FONTS) {
    const old = base.subarray(file(before[f].array), file(before[f].array) + 4 * before[f].count);
    assert.ok(!written.some(b => Buffer.from(b).includes(Buffer.from(old.subarray(0, 16)))), `font ${f}: no copied glyph pointers in raw bytes`);
  }
  assert.equal(startPhase.length, 2 * FONTS.length, "per font the table word and the copy the start screen reads");
  const res = await applyPatches(base, [{ format: "gelumpe-patch", version: 1, id: "glyph-test", name: "glyphs", changes, startPhase }]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const after = readFontsLoose(res.bytes);
  const art = readArt();
  for (const f of FONTS) {
    const font = after[f];
    assert.equal(font.count, before[f].count + 7);
    assert.ok(font.head >= LANG && font.head < LANG_END, `font ${f} head in the language area`);
    const codes = font.codes;
    assert.deepEqual(codes, [...codes].sort((a, b) => a - b), `font ${f}: codes sorted signed`);
    assert.deepEqual(codes.slice(0, 7), Object.values(CODES).sort((a, b) => a - b));
    assert.deepEqual(codes.slice(7), [...before[f].glyphs.keys()], `font ${f}: the old glyphs follow unchanged`);
    for (const [key, code] of Object.entries(CODES)) {
      const g = font.glyphs.get(code);
      const rows = art[f][key].filter(r => typeof r === "string");
      assert.equal(g.h, rows.length, `font ${f} ${key} height`);
      assert.ok(g.h + g.yo <= TOP[f]);
      assert.equal(g.adv, g.w + 2, `font ${f} ${key}: spacing of its base letter (advance 7, width 5)`);
    }
  }
});

/** Like readFonts, without the measured glyph counts (the copy has seven more). */
function readFontsLoose(vsb) {
  const view = new DataView(vsb.buffer, vsb.byteOffset, vsb.byteLength);
  const u32 = ram => view.getUint32(file(ram), true);
  return FONT_SHAPE.map((_, id) => {
    const head = u32(FONT_TABLE + 4 * id);
    const count = u32(head + 4);
    const array = u32(head + 12);
    const glyphs = new Map();
    const codes = [];
    for (let k = 0; k < count; k++) {
      const desc = u32(array + 4 * k);
      const code = view.getInt32(file(desc), true);
      codes.push(code);
      glyphs.set(code, { adv: vsb[file(desc + 4)], w: vsb[file(desc + 0xC)], h: vsb[file(desc + 0xD)], yo: view.getInt8(file(desc + 0xF)) });
    }
    return { head, count, codes, glyphs };
  });
}

for (const [label, env, set] of [["Hacktribe", "E2_VSB", "blech"], ["Korg's red 2.02", "E2_STOCK_VSB", "blech"], ["Korg's blue 2.02", "E2_BLUE_VSB", "blech-synth"]]) {
  const skip = process.env[env] && existsSync(process.env[env]) ? false : `set ${env}`;
  test(`an update of your ${label} file keeps its language: English stays English, German stays German`, { skip }, async () => {
    const base = new Uint8Array(readFileSync(process.env[env]));
    const build = buildOf(base);
    const patches = load(`data/patches/${set}.json`).patches.map(load);
    const de = optionFor(LANG_DE_URLS.map(load), build);
    assert.ok(de, `a lang-de variant for ${build}`);
    const known = emptyKnown();
    await addRelease(known, "develop", build, base, patches);
    await addRelease(known, "develop", build, base, [de]);
    for (const [name, options] of [["English", []], ["German", [de]]]) {
      const file = await applyPatches(base, [...patches, ...options]);
      assert.equal(file.ok, true, file.reasons.join(" "));
      const rec = await recogniseBlech(file.bytes, known);
      assert.equal(rec.ok, true, `${name}: ${rec.why}`);
      assert.equal(rec.present.includes("lang-de"), options.length > 0, `${name}: lang-de ${options.length ? "found" : "not found"}`);
      // the app puts lang-de back on exactly when it found it (site/app/patcher.mjs)
      const again = await applyPatches(rec.bytes, [...patches, ...(rec.present.includes("lang-de") ? [de] : [])], rec.options);
      assert.equal(again.ok, true, again.reasons.join(" "));
      assert.deepEqual(again.bytes, file.bytes, `${name}: the update gives the same file`);
    }
  });
}
