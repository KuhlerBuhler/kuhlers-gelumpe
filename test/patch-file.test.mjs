import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { applyPatches, toHex } from "../src/patch.mjs";
import { PATCH_FILE_HEADER, applyPatchFile, patchesFor, buildPatchFile, fingerprint, isPatchFile, parsePatchFile, userDataRanges } from "../src/patchfile.mjs";
import { TABLES, POINTER_TABLES } from "../src/map/index.mjs";
import { CODE, COPY_FROM, COPY_TO, fixture } from "./support/patch-set.mjs";
import { asStock, withHacktribeRun } from "./helpers.mjs";

const APPLY = new URL("../tools/patch/apply.mjs", import.meta.url).pathname;

test("a patch file holds the header, and the patches come back as they went in", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.2.3", id: "demo", name: "Demo" });
  assert.equal(isPatchFile(file), true);
  assert.equal(String.fromCharCode(...file.subarray(0, 7)), "GLMPPAT");
  assert.equal(isPatchFile(new Uint8Array([1, 2, 3])), false);
  const parsed = await parsePatchFile(file);
  assert.equal(parsed.formatVersion, 2);
  assert.equal(parsed.version, "1.2.3");
  const ranges = parsed.userData.map(([file, length]) => [file, file + length]);
  assert.equal(parsed.input, await fingerprint(vsb, ranges));
  const direct = await applyPatches(vsb, patches);
  const stillMasked = ranges.filter(([start, end]) => direct.spans.every(s => s.file >= end || s.file + s.length <= start));
  assert.equal(parsed.output, await fingerprint(direct.bytes, stillMasked), "the output fingerprint keeps what the patches write inside userData");
  assert.deepEqual([parsed.id, parsed.name], ["demo", "Demo"]);
  assert.deepEqual(parsed.patches, patches, "hooks, checks and start-phase exceptions stay in");
  assert.equal(file.length, PATCH_FILE_HEADER + new DataView(file.buffer, file.byteOffset).getUint32(12, true));
});

test("applying the file gives byte for byte what applying the set gives, and the same reports", async () => {
  const { vsb, patches } = await fixture();
  const direct = await applyPatches(vsb, patches);
  assert.equal(direct.ok, true, direct.reasons.join(" "));
  const viaFile = await applyPatchFile(vsb, await buildPatchFile(vsb, patches, { version: "1.0.0" }));
  assert.equal(viaFile.ok, true, viaFile.reasons.join(" "));
  assert.deepEqual(viaFile.bytes, direct.bytes);
  for (const key of ["spans", "allow", "allowCode", "dependencies"]) assert.deepEqual(viaFile[key], direct[key], key);
  assert.deepEqual(viaFile.allowCode, [[CODE, 16]]);
  assert.equal(viaFile.file.version, "1.0.0");
  assert.equal(toHex(viaFile.bytes.subarray(COPY_TO + 8, COPY_TO + 12)), "aabbccdd");
  assert.equal(toHex(viaFile.bytes.subarray(COPY_TO, COPY_TO + 8)), toHex(vsb.subarray(COPY_FROM, COPY_FROM + 8)));
});

test("the file carries no firmware: no stretch of the copy source and no byte of what it replaces", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0" });
  const text = Buffer.from(file.subarray(PATCH_FILE_HEADER)).toString("utf8");
  for (let at = 0; at + 8 <= 256; at += 4) assert.ok(!text.includes(toHex(vsb.subarray(COPY_FROM + at, COPY_FROM + at + 8))), `source at +${at}`);
  assert.ok(!Buffer.from(file).includes(Buffer.from(vsb.subarray(COPY_FROM, COPY_FROM + 16))));
});

test("a VSB other than the one the file was made for is refused before anything is written", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0" });
  const other = Uint8Array.from(vsb);
  other[0x1a5000] ^= 1;
  const res = await applyPatchFile(other, file);
  assert.equal(res.ok, false);
  assert.equal(res.bytes, undefined);
  assert.match(res.reasons[0], /keine SYSTEM\.VSB, auf die/);
});

test("a VSB whose FX presets, menu lengths, start image and tables were edited still takes the file, and the edits stay", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0" });
  const edited = Uint8Array.from(vsb);
  const { TABLES, field } = await import("../src/map/index.mjs");
  for (const id of ["table.mfx", "table.ifx", "table.groove", "table.modType"]) edited[TABLES.get(id).file + 20] ^= 0x55;
  edited[field("menu.mfxCount").where.offset] = 40;
  edited[field("splash").where.offset + 100] ^= 0xff;
  const res = await applyPatchFile(edited, file);
  assert.equal(res.ok, true, res.reasons.join(" "));
  for (const id of ["table.mfx", "table.ifx", "table.groove", "table.modType"]) assert.equal(res.bytes[TABLES.get(id).file + 20], edited[TABLES.get(id).file + 20]);
  assert.equal(res.bytes[field("menu.mfxCount").where.offset], 40);
  assert.deepEqual(res.bytes.subarray(CODE, CODE + 16), (await applyPatches(vsb, patches)).bytes.subarray(CODE, CODE + 16));
});

test("a change outside the user data is refused: a hook site, a free block, the init pattern", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0" });
  const { TABLES } = await import("../src/map/index.mjs");
  for (const at of [0x2847c, CODE, COPY_FROM, TABLES.get("table.initPattern").file + 9, 0x100]) {
    const other = Uint8Array.from(vsb);
    other[at] ^= 1;
    const res = await applyPatchFile(other, file);
    assert.equal(res.ok, false, `0x${at.toString(16)}`);
    assert.match(res.reasons[0], /keine SYSTEM\.VSB, auf die/);
  }
});

test("the user data ranges are the writable tables and fields, and no patch of the BLECH set reads or replaces bytes in them", () => {
  const ranges = userDataRanges();
  const hit = (file, length) => ranges.filter(([f, n]) => file < f + n && f < file + length);
  const [mfx, ifx] = ["table.mfx", "table.ifx"].map(id => hit(TABLES.get(id).file, 1));
  assert.equal(mfx.length, 1);
  assert.equal(ifx.length, 1);
  assert.equal(hit(0xf9954, 1024).length, 1, "the start image");
  assert.equal(hit(0x3f0e4, 1).length, 1, "the master menu length");
  const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
  const patches = read("data/patches/blech.json").patches.map(read);
  const pointerArrays = [...POINTER_TABLES.values()].flatMap(t => t.arrays.map(a => a.ram - 0xc0000000 + 0x100));
  for (const p of patches) {
    for (const c of p.changes ?? []) {
      if (c.field !== undefined) continue;
      assert.deepEqual(hit(c.file, c.bytes ? c.bytes.length / 2 : c.copy.length), [], `${p.id} writes at 0x${c.file.toString(16)}`);
      // The ranges are Hacktribe's tables; Korg's pointer arrays lie inside that span and hold pointers nobody edits.
      if (c.copy && !pointerArrays.includes(c.copy.file)) assert.deepEqual(hit(c.copy.file, c.copy.length), [], `${p.id} copies from 0x${c.copy.file.toString(16)}`);
    }
    for (const h of p.hooks ?? []) assert.deepEqual(hit(parseInt(h.site, 16) - 0xc0000000 + 0x100, 4), [], `${p.id} hooks ${h.site}`);
  }
});

test("a damaged, cut or foreign file is refused with a reason", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0" });
  const flipped = Uint8Array.from(file);
  flipped[PATCH_FILE_HEADER + 20] ^= 1;
  const newer = Uint8Array.from(file);
  newer[8] = 3;
  const flagged = Uint8Array.from(file);
  flagged[10] = 1;
  const cases = [
    [flipped, /Prüfsumme/], [file.subarray(0, file.length - 1), /Länge/], [file.subarray(0, 60), /zu kurz/],
    [newer, /Format 3/], [flagged, /Merkmale/], [new Uint8Array(200), /keine Patch-Datei/],
  ];
  for (const [bytes, reason] of cases) {
    const res = await applyPatchFile(vsb, bytes);
    assert.equal(res.ok, false);
    assert.match(res.reasons[0], reason);
  }
});

test("a file whose patches were changed behind its back does not produce the image it names", async () => {
  const { vsb, patches } = await fixture();
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0" });
  const body = JSON.parse(Buffer.from(file.subarray(PATCH_FILE_HEADER)).toString("utf8"));
  body.patches[0].changes[0].bytes = "0040a0e10150a0e1e12fff1e11111111";
  const payload = Buffer.from(JSON.stringify(body));
  const forged = new Uint8Array(PATCH_FILE_HEADER + payload.length);
  forged.set(file.subarray(0, PATCH_FILE_HEADER));
  forged.set(payload, PATCH_FILE_HEADER);
  new DataView(forged.buffer).setUint32(12, payload.length, true);
  forged.set(createHash("sha256").update(payload).digest(), 96);
  const res = await applyPatchFile(vsb, forged);
  assert.equal(res.ok, false);
  assert.equal(res.bytes, undefined);
  assert.match(res.reasons[0], /stimmt nicht mit der Patch-Datei überein/);
});

test("a set that does not apply, or a version that does not fit the header, is never written", async () => {
  const { vsb, patches } = await fixture();
  const broken = structuredClone(patches);
  broken[0].changes[0].expect = "00".repeat(32);
  await assert.rejects(buildPatchFile(vsb, broken, { version: "1.0.0" }), /does not apply/);
  for (const version of ["", "x".repeat(17), "1 0", undefined]) await assert.rejects(buildPatchFile(vsb, patches, { version }), TypeError);
});

test("apply.mjs reads a patch file given with --patch, alone, and writes the same image", async () => {
  const { vsb, patches } = await fixture();
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-patchfile-"));
  const [vsbPath, filePath, outPath, otherPath] = ["in.VSB", "SET.patch", "out.VSB", "other.json"].map(n => join(dir, n));
  writeFileSync(vsbPath, vsb);
  writeFileSync(filePath, await buildPatchFile(vsb, patches, { version: "1.0.0", name: "Demo" }));
  writeFileSync(otherPath, JSON.stringify(patches[1]));
  const ok = spawnSync("node", [APPLY, "--vsb", vsbPath, "--patch", filePath, "--out", outPath], { encoding: "utf8" });
  assert.equal(ok.status, 0, ok.stderr);
  assert.deepEqual(new Uint8Array(readFileSync(outPath)), (await applyPatches(vsb, patches)).bytes);
  assert.match(ok.stdout, /Demo 1\.0\.0: input and output match/);
  const mixed = spawnSync("node", [APPLY, "--vsb", vsbPath, "--patch", filePath, "--patch", otherPath, "--out", outPath], { encoding: "utf8" });
  assert.equal(mixed.status, 2);
  assert.match(mixed.stderr, /give it alone/);
  const wrong = join(dir, "wrong.VSB");
  writeFileSync(wrong, Uint8Array.from(vsb, (b, i) => (i === 0x1a5000 ? b ^ 1 : b)));
  const refused = spawnSync("node", [APPLY, "--vsb", wrong, "--patch", filePath, "--out", outPath], { encoding: "utf8" });
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /keine SYSTEM\.VSB, auf die/);
});

test("the BLECH set as one file gives the same image as the set, with the user's firmware", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, async () => {
  const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
  const patches = read("data/patches/blech.json").patches.map(read);
  const vsb = new Uint8Array(readFileSync(process.env.E2_VSB));
  const direct = await applyPatches(vsb, patches);
  assert.equal(direct.ok, true, direct.reasons.join(" "));
  const viaFile = await applyPatchFile(vsb, await buildPatchFile(vsb, patches, { version: "1.0.0", id: "blech", name: "BLECH" }));
  assert.equal(viaFile.ok, true, viaFile.reasons.join(" "));
  assert.deepEqual(viaFile.bytes, direct.bytes);
});

test("the BLECH set as one file takes Hacktribe's and Korg's own firmware, each with its folder variant", { skip: process.env.E2_VSB && process.env.E2_STOCK_VSB ? false : "set E2_VSB and E2_STOCK_VSB" }, async () => {
  const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
  const patches = read("data/patches/blech.json").patches.map(read);
  const vsb = new Uint8Array(readFileSync(process.env.E2_VSB));
  const stock = new Uint8Array(readFileSync(process.env.E2_STOCK_VSB));
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0", id: "blech", name: "BLECH", stock });
  for (const input of [vsb, stock]) {
    const direct = await applyPatches(input, patches);
    const viaFile = await applyPatchFile(input, file);
    assert.equal(viaFile.ok, true, viaFile.reasons.join(" "));
    assert.deepEqual(viaFile.bytes, direct.bytes);
  }
  const at = 0xC00A5678 - 0xC0000000 + 0x100;
  assert.equal(Buffer.from((await applyPatchFile(stock, file)).bytes.subarray(at, at + 17)).toString("latin1"), "KORG/blechtribe/\0");
});

test("the BLECH set as one file takes all four firmwares, gives each what its set gives, and lists each patch once", { skip: process.env.E2_VSB && process.env.E2_STOCK_VSB && process.env.E2_BLUE_VSB ? false : "set E2_VSB, E2_STOCK_VSB and E2_BLUE_VSB" }, async () => {
  const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
  const patches = read("data/patches/blech.json").patches.map(read);
  const synthPatches = read("data/patches/blech-synth.json").patches.map(read);
  const vsb = new Uint8Array(readFileSync(process.env.E2_VSB));
  const stock = new Uint8Array(readFileSync(process.env.E2_STOCK_VSB));
  const synth = new Uint8Array(readFileSync(process.env.E2_BLUE_VSB));
  const blue = Uint8Array.from(vsb);
  blue[0x12] = 0x00;
  blue[0x2e] = 0x23;
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0", id: "blech", name: "BLECH", stock, synth, synthPatches });
  const parsed = await parsePatchFile(file);
  for (const [input, list] of [[vsb, patches], [blue, patches], [stock, patches], [synth, synthPatches]]) {
    const direct = await applyPatches(input, list);
    const viaFile = await applyPatchFile(input, file);
    assert.equal(viaFile.ok, true, viaFile.reasons.join(" "));
    assert.deepEqual(viaFile.bytes, direct.bytes);
    const ids = patchesFor(parsed, input).map(p => p.id);
    assert.equal(new Set(ids).size, ids.length, "each patch once in the list");
    assert.ok(ids.length < parsed.patches.length || input === synth, "variants of the other builds are left out");
  }
});

test("a patch file for both builds: Hacktribe's fingerprints in the head, Korg's in the payload, each base gets its own variant", async () => {
  const { vsb, patches } = await fixture();
  const stock = asStock(vsb);
  const at = COPY_TO + 0x180;
  const was = createHash("sha256").update(vsb.subarray(at, at + 4)).digest("hex");
  const variant = (builds, bytes) => ({ format: "gelumpe-patch", version: 1, id: "folder", builds, changes: [{ file: at, bytes, expect: was }] });
  const set = [...patches.map(p => ({ ...p, builds: ["hacktribe", "stock"] })), variant(["hacktribe"], "11111111"), variant(["stock"], "22222222")];
  const file = await buildPatchFile(vsb, set, { version: "1.0.0", id: "demo", stock });
  const parsed = await parsePatchFile(file);
  assert.deepEqual(Object.keys(parsed.alternates), ["hacktribe-blue", "stock"]);
  const ranges = parsed.userData.map(([from, length]) => [from, from + length]);
  assert.equal(parsed.input, await fingerprint(vsb, ranges));
  assert.equal(parsed.alternates.stock.input, await fingerprint(stock, ranges));
  assert.notEqual(parsed.alternates.stock.input, parsed.input, "the two builds differ in the run that tells them apart");
  const onHack = await applyPatchFile(vsb, file);
  const onStock = await applyPatchFile(stock, file);
  assert.equal(onHack.ok, true, onHack.reasons.join(" "));
  assert.equal(onStock.ok, true, onStock.reasons.join(" "));
  assert.equal(toHex(onHack.bytes.subarray(at, at + 4)), "11111111");
  assert.equal(toHex(onStock.bytes.subarray(at, at + 4)), "22222222");
  assert.deepEqual(onStock.bytes, (await applyPatches(stock, set)).bytes, "the file gives what the set gives");
  const other = Uint8Array.from(stock);
  other[0x1000] ^= 1;
  assert.match((await applyPatchFile(other, file)).reasons[0], /Korgs Original 2\.02 ab/);
});

test("a patch file built for Hacktribe alone refuses Korg's own 2.02", async () => {
  const { vsb, patches } = await fixture();
  const stock = asStock(vsb);
  const marked = patches.map(p => ({ ...p, builds: ["hacktribe", "stock"] }));
  const file = await buildPatchFile(vsb, marked, { version: "1.0.0", id: "demo" });
  assert.deepEqual(Object.keys((await parsePatchFile(file)).alternates), ["hacktribe-blue"], "Hacktribe with the blue head comes from the same file");
  const refused = await applyPatchFile(stock, file);
  assert.equal(refused.ok, false);
  assert.match(refused.reasons[0], /nicht für Korgs Original 2\.02 gebaut/);
  await assert.rejects(buildPatchFile(stock, marked, { version: "1.0.0" }), /Hacktribe 2\.02/);
  await assert.rejects(buildPatchFile(vsb, marked, { version: "1.0.0", stock: vsb }), /not Korg's own/);
  await assert.rejects(buildPatchFile(vsb, patches, { version: "1.0.0", stock }), /does not apply to Korg's own 2\.02/);
});

test("alternates in a patch file name only the known firmwares, with two sha256, the synth with its own patches", async () => {
  const { vsb, patches } = await fixture();
  const marked = patches.map(p => ({ ...p, builds: ["hacktribe", "stock"] }));
  const file = await buildPatchFile(vsb, marked, { version: "1.0.0", id: "demo", stock: asStock(vsb) });
  const body = JSON.parse(new TextDecoder().decode(file.subarray(PATCH_FILE_HEADER)));
  for (const bad of [{ synth: body.alternates.stock }, { stock: { input: "00" } }, [], { red: body.alternates.stock }, { stock: { ...body.alternates.stock, patches: body.patches } }]) {
    const payload = new TextEncoder().encode(JSON.stringify({ ...body, alternates: bad }));
    const out = new Uint8Array(PATCH_FILE_HEADER + payload.length);
    out.set(file.subarray(0, PATCH_FILE_HEADER));
    out.set(payload, PATCH_FILE_HEADER);
    new DataView(out.buffer).setUint32(12, payload.length, true);
    out.set(createHash("sha256").update(payload).digest(), 96);
    await assert.rejects(parsePatchFile(out), /alternates/);
  }
});

test("a patch file for Hacktribe, Hacktribe with the blue head and the blue's own firmware: each gets its own fingerprints and list", async () => {
  const { vsb: plain, patches } = await fixture();
  const vsb = withHacktribeRun(plain);
  vsb.set([0x45, 0x32, 0x53], 0x10);
  vsb[0x2e] = 0x24;
  const blue = Uint8Array.from(vsb);
  blue[0x12] = 0x00;
  blue[0x2e] = 0x23;
  const synth = asStock(plain);
  synth.set([0x45, 0x32, 0x00], 0x10);
  const at = COPY_TO + 0x180;
  const was = createHash("sha256").update(vsb.subarray(at, at + 4)).digest("hex");
  const synthPatches = [{ format: "gelumpe-patch", version: 1, id: "folder", builds: ["synth"], changes: [{ file: at, bytes: "33333333", expect: was }] }];
  const file = await buildPatchFile(vsb, patches, { version: "1.0.0", id: "demo", synth, synthPatches });
  const parsed = await parsePatchFile(file);
  assert.deepEqual(Object.keys(parsed.alternates).sort(), ["hacktribe-blue", "synth"]);
  assert.deepEqual(parsed.alternates.synth.patches, synthPatches);
  const onBlue = await applyPatchFile(blue, file);
  const onSynth = await applyPatchFile(synth, file);
  assert.equal(onBlue.ok, true, onBlue.reasons.join(" "));
  assert.equal(onSynth.ok, true, onSynth.reasons.join(" "));
  assert.deepEqual(onBlue.bytes, (await applyPatches(blue, patches)).bytes, "the blue head gets the set as it is");
  assert.equal(toHex(onSynth.bytes.subarray(at, at + 4)), "33333333", "the blue's own firmware gets its own list");
  assert.deepEqual(patchesFor(parsed, synth).map(p => p.id), ["folder"]);
  assert.deepEqual(patchesFor(parsed, vsb).map(p => p.id), patches.map(p => p.id));
  const refused = await applyPatchFile(asStock(plain), file);
  assert.match(refused.reasons[0], /nicht für Korgs Original 2\.02 gebaut/);
});
