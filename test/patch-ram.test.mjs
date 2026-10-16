import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyPatches, selectFor } from "../src/patch.mjs";
import { checkRam, checkRamPlacement, declaredAreas, writtenAreas } from "../src/ramspans.mjs";
import PROTECTED from "../data/protected.mjs";
import { FREE_RUNS, SYNTH_FREE_RUNS, RESERVED } from "../data/patch-ram.mjs";

const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const SET = read("data/patches/blech.json");
const patches = SET.patches.map(read);
const BUILDS = ["hacktribe", "stock"];
const chosen = build => selectFor(patches, build).patches;
const byId = (list, id) => list.find(p => p.id === id);
const clone = value => structuredClone(value);
const hex = n => `0x${n.toString(16).toUpperCase()}`;

const IMAGE = PROTECTED.regions.find(r => r.id === "firmware-image");
const where = { free: FREE_RUNS, regions: PROTECTED.regions, window: PROTECTED.ram.window, image: IMAGE };

test("the synth set keeps its code and declared state inside the measured free image run", () => {
  const synth = read("data/patches/blech-synth.json").patches.map(read);
  assert.deepEqual(selectFor(synth, "synth").reasons, []);
  assert.deepEqual(checkRam(synth), []);
  assert.deepEqual(checkRamPlacement(synth, { ...where, free: SYNTH_FREE_RUNS }), []);
});

// The start image editor's state and buffers where they first were (tools/patch/splash_editor.py before 2026-10-15):
// 4 KiB at 0xC01A4000, over the picture and the code of the power-off patch at 0xC01A4A00. Same layout, 0x22000 higher up today.
const OLD_START_EDITOR = [
  { at: "0xC01A4000", length: 0x100, what: "STATE", source: "tools/patch/splash_editor.py:STATE" },
  { at: "0xC01A4100", length: 0x420, what: "RECBUF", source: "tools/patch/splash_editor.py:RECBUF" },
  { at: "0xC01A4520", length: 0x400, what: "ACTIVE", source: "tools/patch/splash_editor.py:ACTIVE" },
  { at: "0xC01A4920", length: 0x400, what: "EDIT", source: "tools/patch/splash_editor.py:EDIT" },
  { at: "0xC01A4D20", length: 0x2E0, what: "FIL", source: "tools/patch/splash_editor.py:FIL" },
];

/** A reserved area as a patch of its own, so the set's overlap check also guards it. */
const reservedPatch = r => ({ id: `reserved:${r.id}`, ram: [{ at: hex(r.start), length: r.end - r.start, what: r.what, source: "data/patch-ram.mjs:RESERVED" }] });

test("a patch that takes RAM of Doom's loader is refused, in every part of its area", () => {
  const loader = byId(patches, "doom-loader");
  const { own } = declaredAreas(loader);
  const code = loader.changes.find(c => c.file === 0xC017CC00 - 0xC0000000 + 0x100).bytes.length / 2;
  assert.deepEqual(own.map(a => [a.start, a.end]), [[0xC017CC00 + code, 0xC017DC00], [0xC017DC00, 0xC017F000], [0xC017F000, 0xC0180000]]);
  assert.ok(checkRam([loader, { id: "intruder", ram: [{ at: "0xC017CC10", length: 16, what: "test", source: "x:Y" }] }]).join().includes("overlaps doom-loader"), "its code is held by its written bytes");
  for (const area of own) {
    const intruder = { id: "intruder", ram: [{ at: hex(area.start + 0x10), length: 0x100, what: "test", source: "data/patch-ram.mjs:RESERVED" }] };
    assert.match(checkRam([loader, intruder]).join(), /(intruder: .* overlaps doom-loader: )|(doom-loader: .* overlaps intruder: )/);
  }
  assert.deepEqual(RESERVED, [], "nothing is reserved outside the set any more");
});

function withOldStartEditor(list) {
  const copy = clone(list);
  byId(copy, "splash-editor").ram = clone(OLD_START_EDITOR);
  return copy;
}

test("every patch of the BLECH set declares its RAM, and every entry names where its size comes from", () => {
  for (const patch of patches) {
    assert.ok(Array.isArray(patch.ram), `${patch.id} has no ram list (an empty one says it needs none)`);
    const { own, shares } = declaredAreas(patch);
    for (const entry of [...(patch.ram ?? []), ...(patch.shares ?? [])]) {
      const [file, symbol] = String(entry.source).split(":");
      assert.match(entry.what ?? "", /\S/, `${patch.id}: an entry without what`);
      const text = readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
      assert.match(text, new RegExp(`\\b${symbol}\\b`), `${patch.id}: ${entry.source} does not name a symbol of ${file}`);
    }
    for (const share of shares) assert.ok(patches.some(p => p.id === share.with), `${patch.id}: shares with ${share.with}, not in the set`);
    assert.equal(own.length, patch.ram.length);
  }
  assert.deepEqual(patches.filter(p => p.ram.length).map(p => p.id).sort(), ["blech-sysex", "blech-sysex", "dice", "doom-loader", "load-bar", "mfx-switch", "note-assistant", "pattern-switch", "preset-tables", "preset-tables", "sample-errors", "script-runtime", "script-runtime", "splash-editor", "tap-motion"]);
});

for (const build of BUILDS) {
  test(`no two patches of the BLECH set overlap in written bytes or declared RAM (${build})`, () => {
    const set = chosen(build);
    assert.ok(set.length >= 9, "the set picks a variant of every patch");
    assert.deepEqual(checkRam(set), []);
  });

  test(`no patch of the set writes or keeps RAM in an area reserved for something outside the set (${build})`, () => {
    assert.deepEqual(checkRam([...chosen(build), ...RESERVED.map(reservedPatch)]), []);
  });

  test(`every declared area lies in a free run of the image or clear of protected RAM (${build})`, () => {
    assert.deepEqual(checkRamPlacement(chosen(build), where), []);
  });
}

test("the free runs lie in the image and touch no protected region but the image itself", () => {
  for (const run of FREE_RUNS) {
    assert.ok(IMAGE.start <= run.start && run.end <= IMAGE.end, `${hex(run.start)} lies in the image`);
    for (const region of PROTECTED.regions.filter(r => r.space === "ram" && r.id !== IMAGE.id)) {
      assert.ok(run.end <= region.start || region.end <= run.start, `${hex(run.start)}..${hex(run.end)} overlaps ${region.id}`);
    }
  }
});

test("the declared areas are the ones the docs name: the editor's 4 KiB, the plugin pool, the card work area", () => {
  const area = (id, at) => declaredAreas(byId(patches, id)).own.find(a => a.start === at);
  assert.equal(area("splash-editor", 0xC0182000).end, 0xC0182100);
  assert.equal(declaredAreas(byId(patches, "splash-editor")).own.at(-1).end, 0xC0183000);
  assert.equal(area("script-runtime", 0xC01D7000).end - 0xC01D7000, 131072, "pool, docs/messungen/2026-10-14-skript-haken.md");
  assert.equal(area("script-runtime", 0xC01F7000).end, 0xC01F8000, "card work area");
  assert.equal(area("script-runtime", 0xC01F8000).end, 0xC01FFFF0, "block buffer ends where the free run ends");
});

test("a start editor at its old address overlaps the power-off patch, and the check says so", () => {
  const set = withOldStartEditor(chosen("hacktribe"));
  const reasons = checkRam(set);
  assert.ok(reasons.length >= 3, reasons.join("\n"));
  assert.ok(reasons.some(r => /splash-editor: (EDIT|FIL|RECBUF) .* overlaps power-off: .*power-off picture/.test(r)), reasons.join("\n"));
  assert.ok(reasons.some(r => /splash-editor: FIL .* overlaps (mfx-switch|power-off): /.test(r)), reasons.join("\n"));
  for (const r of reasons) assert.match(r, /overlaps/);
  assert.deepEqual(checkRam(chosen("hacktribe")), [], "the set as it is passes");
});

test("applyPatches refuses the BLECH set with the start editor at its old address", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, async () => {
  const vsb = new Uint8Array(readFileSync(process.env.E2_VSB));
  const good = await applyPatches(vsb, patches);
  assert.equal(good.ok, true, good.reasons.join(" "));
  const bad = await applyPatches(vsb, withOldStartEditor(patches));
  assert.equal(bad.ok, false);
  assert.ok(bad.reasons.some(r => /overlaps power-off/.test(r)), bad.reasons.join("\n"));
});

test("the rules: own areas, written bytes and shares", () => {
  const A = { format: "gelumpe-patch", version: 1, id: "a", changes: [{ file: 0x1a2100 + 0x100, bytes: "00".repeat(16), note: "code" }] };
  const B = { format: "gelumpe-patch", version: 1, id: "b", changes: [{ file: 0x1b0000, bytes: "00".repeat(16) }] };
  const area = (at, length, what = "buffer") => ({ at: hex(at), length, what, source: "x:Y" });
  assert.deepEqual(writtenAreas(A), [{ patch: "a", start: 0xC01A2100, end: 0xC01A2110, what: "code" }]);
  assert.deepEqual(checkRam([A, B]), []);
  assert.match(checkRam([{ ...A, ram: [area(0xC01A2108, 16)] }, B]).join(), /a: buffer .* overlaps a: code/, "a patch's own buffer over its own code");
  assert.match(checkRam([{ ...A, ram: [area(0xC01AFF08, 4)] }, B]).join(), /a: buffer .* overlaps b: change/, "over another patch's bytes");
  assert.match(checkRam([{ ...A, ram: [area(0xC0182000, 16)] }, { ...B, ram: [area(0xC018200F, 16)] }]).join(), /overlaps/, "two buffers share a byte");
  assert.deepEqual(checkRam([{ ...A, ram: [area(0xC0182000, 16)] }, { ...B, ram: [area(0xC0182010, 16)] }]), [], "next to each other is fine");
  const owner = { ...A, ram: [area(0xC0182000, 64)] };
  const word = (at, owner_ = "a") => ({ ...B, shares: [{ ...area(at, 4, "word"), with: owner_ }] });
  assert.deepEqual(checkRam([owner, word(0xC0182010)]), [], "a share inside the owner's area");
  assert.match(checkRam([owner, word(0xC0182040)]).join(), /lies in no area that a declares/, "a share past the area");
  assert.deepEqual(checkRam([word(0xC0182010, "c")]), [], "the owner is not applied: nobody keeps the word, a patch may go in without it");
  assert.match(checkRam([owner, word(0xC0182010, "c")]).join(), /overlaps a: buffer/, "a word of an absent owner over another patch's area");
  assert.match(checkRam([{ ...owner, shares: [{ ...area(0xC0182010, 4), with: "a" }] }]).join(), /not another patch/, "a patch cannot share with itself");
  assert.match(checkRam([{ ...A, ram: [{ at: 12, length: 4 }] }]).join(), /needs at as a hex string/, "a malformed entry is a reason, not a throw");
});

test("placement: erased runs of the image, the RAM window and protected regions", () => {
  const only = (at, length) => [{ format: "gelumpe-patch", version: 1, id: "p", changes: [], ram: [{ at: hex(at), length, what: "area", source: "x:Y" }] }];
  const reasons = (at, length) => checkRamPlacement(only(at, length), where);
  assert.deepEqual(reasons(0xC01A5C00, 0x40), [], "in the big run");
  assert.deepEqual(reasons(0xC0180F00, 0x40), [], "in the run before it");
  assert.match(reasons(0xC0100000, 16).join(), /firmware image but not in one free run/, "over firmware code");
  assert.match(reasons(0xC01A1000, 16).join(), /firmware image but not in one free run/, "Hacktribe code between the runs");
  assert.match(reasons(0xC0170800, 16).join(), /firmware image but not in one free run/, "the SysEx hook");
  assert.match(reasons(0xC01FFFE0, 0x20).join(), /firmware image but not in one free run/, "past the end of the run");
  // the block buffer when the store read 0x4000 bytes into its second image: 0xC01F8000 + 0x8000 is 16 bytes too long
  assert.match(reasons(0xC01F8000, 0x8000).join(), /firmware image but not in one free run/);
  assert.deepEqual(reasons(0xC01F8000, 0x7FF0), []);
  assert.match(reasons(0xC06A3000, 16).join(), /protected region heap/);
  assert.match(reasons(0xC0D3A940, 16).join(), /protected region work-buffer/);
  assert.match(reasons(0xC0200000, 16).join(), /protected region/, "just behind the image");
  assert.match(reasons(0xC8000000, 16).join(), /outside the RAM window/);
  assert.match(reasons(0xC2800000, 16).join(), /in no free run/, "RAM nobody has explained stays blocked");
});

test("with your own firmware every declared area in the image is erased in the base", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, () => {
  const bases = [["hacktribe", process.env.E2_VSB], ["stock", process.env.E2_STOCK_VSB]].filter(([, path]) => path);
  for (const [build, path] of bases) {
    const vsb = new Uint8Array(readFileSync(path));
    for (const patch of chosen(build)) {
      for (const area of declaredAreas(patch).own) {
        const at = area.start - 0xC0000000 + 0x100;
        assert.ok(vsb.subarray(at, at + area.end - area.start).every(b => b === 0xff), `${build}: ${patch.id} ${area.what} ${hex(area.start)} is not FF in your firmware`);
      }
    }
  }
});
