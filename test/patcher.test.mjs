import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync, mkdtempSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { classify, convertStock, cardFolder, sampleFolder, loadBlechSet, itemsFor, hasDoom, DOOM_FILES, DOOM_FOLDER, BLECH_SET_URL, BLECH_FOLDER, checkName, checkDetail, checkProgress, clock, CHECK_HOLD, newFlow, step, allowed, verifiedReport, VERIFIED_URL, STOCK_SHA256, HACKTRIBE_SHA256, HACKTRIBE_PATCH_URL, VSB_SIZE } from "../src/patcher.mjs";
import { applyPatches, splashPatch, patchesPresent, SPLASH_W, SPLASH_H } from "../src/patch.mjs";
import { sha256 } from "../src/firmware.mjs";
import { asStock, makeFirmware } from "./helpers.mjs";
import { expected, fixture, oldFile } from "./fixtures/bsdiff/data.mjs";

const FREE = 0x1a2100;
const pixels = flip => Uint8Array.from({ length: SPLASH_W * SPLASH_H }, (_, i) => ((i + flip) & 1));
const raw = bytes => ({ format: "gelumpe-patch", version: 1, id: "raw", changes: [{ file: FREE, bytes, expect: "" }] });

/** Two small patches of our own standing in for BLECH: a start image and a raw change over blank bytes. */
async function ours(vsb) {
  const rawPatch = raw("e12fff1e");
  rawPatch.changes[0].expect = await sha256(vsb.subarray(FREE, FREE + 4));
  return [splashPatch(pixels(0)), rawPatch];
}

test("a Hacktribe file without the patches is ready to be patched", async () => {
  const vsb = await makeFirmware();
  const res = await classify(vsb, await ours(vsb));
  assert.equal(res.kind, "hacktribe");
  assert.deepEqual(res.present, []);
});

test("a file that already carries every patch is BLECH, one with some of them is partial", async () => {
  const vsb = await makeFirmware();
  const patches = await ours(vsb);
  const all = await applyPatches(vsb, patches);
  assert.equal(all.ok, true, all.reasons.join(" "));
  const done = await classify(all.bytes, patches);
  assert.deepEqual([done.kind, done.present], ["blech", ["splash", "raw"]]);
  const some = await applyPatches(vsb, [patches[0]]);
  const half = await classify(some.bytes, patches);
  assert.deepEqual([half.kind, half.present], ["partial", ["splash"]]);
  assert.deepEqual((await patchesPresent(vsb, patches)).map(p => p.present), [false, false]);
});

test("the original Korg file is told apart by its hash, before any structure is looked at", async () => {
  const vsb = await makeFirmware();
  assert.equal((await classify(vsb, [], await sha256(vsb))).kind, "stock");
  assert.match(STOCK_SHA256, /^[0-9a-f]{64}$/);
});

test("Korg's build: the unchanged original is stock, an edited one is refused, one that already carries BLECH reads as BLECH", async () => {
  const hack = await makeFirmware();
  const stock = asStock(hack);
  const patches = [{ ...(await ours(hack))[1], builds: ["hacktribe", "stock"] }];
  assert.equal((await classify(stock, patches, await sha256(stock))).kind, "stock");
  const edited = Uint8Array.from(stock);
  edited[0x1000] ^= 1;
  const res = await classify(edited, patches);
  assert.equal(res.kind, "unknown");
  assert.match(res.reasons[0], /nicht die unveränderte Datei/);
  const done = await applyPatches(stock, patches);
  assert.equal(done.ok, true, done.reasons.join(" "));
  const again = await classify(done.bytes, patches);
  assert.deepEqual([again.kind, again.present], ["blech", ["raw"]]);
});

test("a file of the wrong size or without the measured layout is refused with the reason", async () => {
  assert.deepEqual(await classify(new Uint8Array(1000), []), { kind: "wrong-size", size: 1000, reasons: [], present: [] });
  const res = await classify(new Uint8Array(VSB_SIZE), []);
  assert.equal(res.kind, "unknown");
  assert.ok(res.reasons.length > 0);
});

test("the card folder is the one the running firmware reads: Hacktribe's own, or Korg's for the original", () => {
  assert.equal(cardFolder("hacktribe"), "KORG/hacktribe/System/");
  assert.equal(cardFolder("blech"), "KORG/hacktribe/System/");
  assert.equal(cardFolder("stock"), "KORG/electribe sampler/System/");
});

test("check ids and details come out as words", () => {
  assert.equal(checkName("boot:normal"), "Start bis zum Hauptbildschirm");
  assert.equal(checkName("start_mode:00000400"), "Startmodus");
  assert.equal(checkName("something:new"), "something:new");
  assert.equal(checkDetail("ok"), "ok");
  assert.equal(checkDetail({ code: [["0x10", 4]], data: [["0x20", 2]] }), "Geändert in der Startphase: Code an 0x10 (4 Byte), Daten an 0x20 (2 Byte)");
});

test("the card folders: the one the running firmware reads now, and the one BLECH reads after the update", () => {
  assert.equal(sampleFolder("hacktribe"), "KORG/hacktribe/");
  assert.equal(sampleFolder("stock"), "KORG/electribe sampler/");
  assert.equal(BLECH_FOLDER, "blechtribe");
});

const readFile = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const BLECH_SET = await loadBlechSet(async url => readFile(url));
const BLECH = BLECH_SET.items;

test("Doom's files are offered when the set carries the loader, and they exist in third_party/doom", () => {
  assert.equal(hasDoom(BLECH_SET), true);
  assert.equal(hasDoom({ items: [{ id: "mfx-switch" }] }), false);
  assert.equal(DOOM_FOLDER, "KORG/blechtribe/Doom/");
  for (const file of DOOM_FILES) assert.ok(existsSync(new URL(`../${file}`, import.meta.url)), file);
});

test("itemsFor: the items of a set that apply to a build, one per id", () => {
  const set = { items: [{ id: "a" }, { id: "f" }, { id: "f" }], patches: [{ id: "a", builds: ["hacktribe", "stock"] }, { id: "f", builds: ["hacktribe"] }, { id: "f", builds: ["stock"] }] };
  assert.deepEqual(itemsFor(set, "hacktribe"), [set.items[0], set.items[1]]);
  assert.deepEqual(itemsFor(set, "stock"), [set.items[0], set.items[2]]);
  assert.deepEqual(itemsFor(BLECH_SET, "stock").map(p => p.id), ["splash-editor", "mfx-switch", "pattern-switch", "tap-motion", "note-assistant", "dice", "load-bar", "sample-errors", "script-runtime", "blechtribe", "splash", "blech-theme", "preset-tables", "synth-filters", "power-off", "doom-loader", "blech-sysex"]);
  assert.equal(itemsFor(BLECH_SET, "stock").length, itemsFor(BLECH_SET, "hacktribe").length + 1, "the synth filters are for Korg's build only");
});

test("BLECH is the set data/patches/blech.json: every patch it lists, in its order, with the id and name of the file", async () => {
  assert.equal(BLECH_SET_URL, "data/patches/blech.json");
  const listed = readFile(BLECH_SET_URL).patches;
  assert.deepEqual(BLECH.map(p => p.url), listed);
  assert.ok(BLECH.length > 3, "the whole set, not three of its patches");
  for (const id of ["splash-editor", "mfx-switch", "pattern-switch", "tap-motion", "note-assistant", "dice", "load-bar", "sample-errors", "script-runtime", "blechtribe", "splash", "blech-theme", "preset-tables", "synth-filters", "power-off", "blech-sysex"]) assert.ok(BLECH.some(p => p.id === id), id);
  BLECH.forEach((p, i) => {
    const file = readFile(p.url);
    assert.deepEqual([p.id, p.label], [file.id, file.name]);
    assert.equal(BLECH_SET.patches[i].id, p.id);
  });
});

test("a set that is not a patch set is refused with its address", async () => {
  await assert.rejects(loadBlechSet(async () => ({ format: "gelumpe-patch", version: 1 })), /data\/patches\/blech\.json ist kein Patch-Set/);
  await assert.rejects(loadBlechSet(async () => ({ format: "gelumpe-patch-set", version: 1, patches: [] })), /kein Patch-Set/);
});

const hacktribe = { kind: "hacktribe", size: VSB_SIZE, reasons: [], present: [] };
const checks = ok => ({ ok, checks: [{ id: "boot:normal", ok: true, detail: "x" }, { id: "kill_switch", ok, detail: "y" }] });

const snapshot = (done, total, groups) => ({ state: "running", total, done, ok: done, fail: 0, groups });
const group = (id, name, state, ok = 0, fail = 0) => ({ id, name, total: 1, done: state === "done" || state === "failed" ? 1 : 0, state, ok, fail });

test("checkProgress: the bar is real work done over total, the groups carry a short state, nothing else", () => {
  const p = checkProgress(snapshot(40, 160, [group("a", "Start", "done", 42, 0), group("b", "Menü", "failed", 3, 2), group("c", "Würfeln", "running"), group("d", "Ladebalken", "waiting")]));
  assert.equal(p.value, 25);
  assert.equal(p.text, "40 von 160");
  assert.deepEqual(p.groups.map(g => [g.name, g.state, g.text]), [["Start", "done", "42/42"], ["Menü", "failed", "2 fehlgeschlagen"], ["Würfeln", "running", "läuft"], ["Ladebalken", "waiting", ""]]);
});

test("checkProgress: never 100 before the result, and a snapshot that is not a running one shows nothing", () => {
  assert.equal(checkProgress(snapshot(160, 160, [])).value, CHECK_HOLD);
  assert.equal(checkProgress({ ...snapshot(5, 10, []), state: "done" }), null, "left over from the run before");
  assert.equal(checkProgress({ state: "idle" }), null);
  assert.equal(checkProgress(null), null);
  assert.equal(checkProgress(snapshot(0, 0, [])), null);
});

test("clock: minutes and seconds", () => {
  assert.equal(clock(0), "0:00");
  assert.equal(clock(83_400), "1:23");
  assert.equal(clock(-5), "0:00");
});

test("flow: only a Hacktribe file can be patched; every other kind is rejected with its kind kept", () => {
  for (const kind of ["blech", "partial", "unknown", "wrong-size"]) {
    const flow = step(newFlow(), { type: "input", input: { ...hacktribe, kind } });
    assert.equal(flow.phase, "rejected");
    assert.equal(flow.input.kind, kind);
    assert.deepEqual(allowed(flow), { patch: false, download: false, test: false, busy: false });
  }
  const ready = step(newFlow(), { type: "input", input: hacktribe });
  assert.equal(ready.phase, "ready");
  assert.equal(allowed(ready).patch, true);
  assert.equal(allowed(ready).download, false);
});

const stockInput = { ...hacktribe, kind: "stock" };

test("flow: Korg's original is ready for BLECH directly, with the stock card folder", () => {
  let flow = step(newFlow(), { type: "input", input: stockInput });
  assert.deepEqual([flow.phase, flow.origin, flow.route], ["ready", "stock", "direct"]);
  assert.deepEqual(flow.steps.map(s => [s.id, s.status]), [["read", "ok"]]);
  assert.equal(allowed(flow).patch, true);
  assert.equal(cardFolder(flow.origin), "KORG/electribe sampler/System/");
  flow = step(flow, { type: "patching", patches: BLECH });
  assert.deepEqual(flow.steps.map(s => s.id).slice(0, 2), ["read", "patch:splash-editor"]);
  assert.equal(step(flow, { type: "route", route: "hacktribe", input: stockInput }), flow, "no change of route while it runs");
});

test("flow: the Hacktribe route waits for the user's hacktribe-2.patch, then goes on as a Hacktribe file with the stock card folder", () => {
  let flow = step(newFlow(), { type: "input", input: stockInput });
  flow = step(flow, { type: "route", route: "hacktribe", input: stockInput });
  assert.deepEqual([flow.phase, flow.origin, flow.route], ["needs-patch", "stock", "hacktribe"]);
  assert.deepEqual(allowed(flow), { patch: false, download: false, test: false, busy: false });
  assert.equal(step(flow, { type: "patching", patches: BLECH }), flow, "nothing to patch before the conversion");
  flow = step(flow, { type: "convert-failed", message: "falsche Datei" });
  assert.deepEqual([flow.phase, flow.error], ["needs-patch", "falsche Datei"]);
  flow = step(flow, { type: "converted", input: hacktribe, detail: "SHA-256 abc" });
  assert.deepEqual([flow.phase, flow.origin, flow.route, flow.error], ["ready", "stock", "hacktribe", null]);
  assert.deepEqual(flow.steps.map(s => [s.id, s.status]), [["read", "ok"], ["convert", "ok"]]);
  assert.equal(allowed(flow).patch, true);
  assert.equal(cardFolder(flow.origin), "KORG/electribe sampler/System/");
  flow = step(flow, { type: "patching", patches: BLECH });
  assert.deepEqual(flow.steps.map(s => s.id).slice(0, 3), ["read", "convert", "patch:splash-editor"], "the conversion stays in the list");
  const back = step(step(newFlow(), { type: "input", input: stockInput }), { type: "route", route: "direct", input: stockInput });
  assert.deepEqual([back.phase, back.route, back.steps.map(s => s.id)], ["ready", "direct", ["read"]], "back to the direct route");
  assert.equal(step(newFlow(), { type: "converted", input: hacktribe }).phase, "empty", "a conversion without a waiting original is ignored");
  assert.equal(step(step(newFlow(), { type: "input", input: hacktribe }), { type: "convert-failed", message: "x" }).error, null);
  assert.equal(step(newFlow(), { type: "input", input: hacktribe }).origin, "hacktribe");
  const hack = step(newFlow(), { type: "input", input: hacktribe });
  assert.equal(step(hack, { type: "route", route: "direct", input: stockInput }), hack, "a Hacktribe file has no route to choose");
});

test("flow: download and emulator test open only after the emulator check passed", () => {
  let flow = step(newFlow(), { type: "input", input: hacktribe });
  assert.equal(step(flow, { type: "downloaded" }), flow, "no download before patching");
  flow = step(flow, { type: "patching", patches: BLECH });
  assert.deepEqual(flow.steps.map(s => s.id), ["read", ...BLECH.map(p => `patch:${p.id}`), "check"]);
  assert.equal(allowed(flow).busy, true);
  assert.equal(step(flow, { type: "checking" }), flow, "not while a patch is still open");
  for (const p of BLECH) flow = step(flow, { type: "patch", id: p.id, ok: true, detail: "" });
  flow = step(flow, { type: "checking" });
  assert.equal(flow.phase, "checking");
  assert.equal(allowed(flow).download, false);
  flow = step(flow, { type: "checked", report: checks(true) });
  assert.equal(flow.phase, "passed");
  assert.deepEqual(flow.steps.at(-1), { id: "check", label: "Prüfung im Emulator", status: "ok", detail: "2 von 2 bestanden" });
  assert.deepEqual(allowed(flow), { patch: false, download: true, test: true, busy: false });
  flow = step(flow, { type: "downloaded" });
  assert.equal(flow.phase, "downloaded");
  assert.equal(allowed(flow).download, true);
});

test("flow: a failed check or patch blocks the download and can be run again", () => {
  let flow = step(newFlow(), { type: "input", input: hacktribe });
  flow = step(flow, { type: "patching", patches: BLECH });
  flow = step(flow, { type: "patch", id: "splash-editor", ok: false, detail: "andere Bytes" });
  assert.equal(step(flow, { type: "checking" }), flow);
  flow = step(flow, { type: "error", message: "Der Emulator antwortet nicht." });
  assert.equal(flow.phase, "failed");
  assert.equal(flow.error, "Der Emulator antwortet nicht.");
  assert.deepEqual([allowed(flow).download, allowed(flow).patch], [false, true]);

  flow = step(flow, { type: "patching", patches: BLECH });
  for (const p of BLECH) flow = step(flow, { type: "patch", id: p.id, ok: true, detail: "" });
  flow = step(flow, { type: "checking" });
  flow = step(flow, { type: "checked", report: checks(false) });
  assert.equal(flow.phase, "failed");
  assert.equal(flow.steps.at(-1).status, "error");
  assert.equal(flow.steps.at(-1).detail, "1 von 2 nicht bestanden");
  assert.equal(allowed(flow).download, false);
  assert.equal(step(flow, { type: "downloaded" }), flow);
});

test("flow: a new file mid-run is ignored, after it a new file starts over", () => {
  let flow = step(newFlow(), { type: "input", input: hacktribe });
  flow = step(flow, { type: "patching", patches: BLECH });
  assert.equal(step(flow, { type: "input", input: hacktribe }), flow);
  flow = step(flow, { type: "error", message: "x" });
  const fresh = step(flow, { type: "input", input: { ...hacktribe, kind: "unknown" } });
  assert.deepEqual([fresh.phase, fresh.steps, fresh.error], ["rejected", [], null]);
  assert.deepEqual(step(flow, { type: "reset" }), newFlow());
});

// ---- the user's own hacktribe-2.patch ---------------------------------------------------------------
// The made-up patch is written by bsdiff4 (test/fixtures/bsdiff/make.py); the hashes of the page are parameters here.
const patchBytes = () => fixture("./patch/edit.patch");
const fixtureHashes = { stockHash: expected.patch.old, targetHash: expected.patch.new };

test("convertStock: the original and a bsdiff patch make the file whose hash is the target", async () => {
  const res = await convertStock(oldFile(), patchBytes(), fixtureHashes);
  assert.equal(res.ok, true, res.reason);
  assert.equal(res.sha256, expected.patch.new);
  assert.equal(res.bytes.length, VSB_SIZE);
});

test("convertStock: the file has to be the original, the patch a bsdiff patch for a VSB, the result the known Hacktribe file", async () => {
  const other = oldFile();
  other[5] ^= 1;
  assert.match((await convertStock(other, patchBytes(), fixtureHashes)).reason, /nicht die originale/);
  const notPatch = patchBytes().slice();
  notPatch[0] = 0x58;
  assert.match((await convertStock(oldFile(), notPatch, fixtureHashes)).reason, /BSDIFF40/);
  assert.match((await convertStock(oldFile(), new Uint8Array(2 << 20), fixtureHashes)).reason, /falsche Datei/);
  const small = new Uint8Array(32);
  small.set(Array.from("BSDIFF40", c => c.charCodeAt(0)));
  small[24] = 5;                                                   // announces a 5-byte result
  assert.match((await convertStock(oldFile(), small, fixtureHashes)).reason, /nicht hacktribe-2\.patch/);
  assert.match((await convertStock(oldFile(), patchBytes(), { ...fixtureHashes, targetHash: "0".repeat(64) })).reason, /nicht die bekannte Hacktribe-2\.02-Datei/);
  assert.match((await convertStock(oldFile(), patchBytes().subarray(0, 100), fixtureHashes)).reason, /abgeschnitten/);
});

test("the known hashes and the link: Hacktribe's file on the web, the patch never shipped", () => {
  assert.match(HACKTRIBE_SHA256, /^[0-9a-f]{64}$/);
  assert.notEqual(HACKTRIBE_SHA256, STOCK_SHA256);
  assert.equal(HACKTRIBE_PATCH_URL, "https://github.com/bangcorrupt/hacktribe/raw/main/patch/hacktribe-2.patch");
  for (const dir of ["../data", "../assets", "../site", "../src"]) {
    assert.equal(readdirSync(new URL(`${dir}/`, import.meta.url), { recursive: true }).some(f => /hacktribe-2\.patch$/.test(f)), false, `${dir} holds no copy of it`);
  }
});

// With your own files: E2_VSB (Hacktribe) and E2_STOCK_VSB (Korg 2.02), as in test/local.test.mjs.
const VSB = process.env.E2_VSB;
const STOCK = process.env.E2_STOCK_VSB;

test("your Hacktribe file takes the real BLECH patches and then reads as BLECH", { skip: VSB ? false : "E2_VSB not set" }, async () => {
  const { patches } = BLECH_SET;
  const vsb = new Uint8Array(readFileSync(VSB));
  const before = await classify(vsb, patches);
  if (before.kind === "blech") return;             // a file that is BLECH already has nothing to apply
  assert.equal(before.kind, "hacktribe");
  const res = await applyPatches(vsb, patches);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal((await classify(res.bytes, patches)).kind, "blech");
  const some = await applyPatches(vsb, patches.slice(0, 2));
  const half = await classify(some.bytes, patches);
  assert.deepEqual([half.kind, half.present], ["partial", patches.slice(0, 2).map(p => p.id)], "a file with two of the five reads as partial");
});

test("your Hacktribe file: the page's result is apply.mjs --set data/patches/blech.json, byte for byte", { skip: VSB ? false : "E2_VSB not set" }, async () => {
  const vsb = new Uint8Array(readFileSync(VSB));
  if ((await classify(vsb, BLECH_SET.patches)).kind === "blech") return;
  const res = await applyPatches(vsb, BLECH_SET.patches);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const dir = mkdtempSync(join(tmpdir(), "cee-patcher-"));
  try {
    const out = join(dir, "NEW.VSB");
    execFileSync(process.execPath, [fileURLToPath(new URL("../tools/patch/apply.mjs", import.meta.url)), "--vsb", VSB, "--set", fileURLToPath(new URL(`../${BLECH_SET_URL}`, import.meta.url)), "--out", out], { stdio: "pipe" });
    assert.equal(await sha256(res.bytes), await sha256(new Uint8Array(readFileSync(out))));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("your original Korg 2.02 file is recognised as the original", { skip: STOCK ? false : "E2_STOCK_VSB not set" }, async () => {
  assert.equal((await classify(new Uint8Array(readFileSync(STOCK)), [])).kind, "stock");
});

test("your Korg 2.02 takes BLECH directly, reads as BLECH afterwards, and every patch of its variant is in", { skip: STOCK ? false : "E2_STOCK_VSB not set" }, async () => {
  const stock = new Uint8Array(readFileSync(STOCK));
  const res = await applyPatches(stock, BLECH_SET.patches);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual([...new Set(res.spans.map(s => s.patch))], itemsFor(BLECH_SET, "stock").map(p => p.id));
  const after = await classify(res.bytes, BLECH_SET.patches);
  assert.deepEqual([after.kind, after.present], ["blech", itemsFor(BLECH_SET, "stock").map(p => p.id)]);
});

// With the user's own hacktribe-2.patch as well: E2_HACKTRIBE_PATCH, from Hacktribe's repository (never in this one).
const PATCH_FILE = process.env.E2_HACKTRIBE_PATCH;

test("your Korg 2.02 and your hacktribe-2.patch make the known Hacktribe 2.02", { skip: STOCK && PATCH_FILE ? false : "E2_STOCK_VSB and E2_HACKTRIBE_PATCH not set" }, async () => {
  const res = await convertStock(new Uint8Array(readFileSync(STOCK)), new Uint8Array(readFileSync(PATCH_FILE)));
  assert.equal(res.ok, true, res.reason);
  assert.equal(res.sha256, HACKTRIBE_SHA256);
});

test("the blue original selects the synth route and its update directory", async () => {
  const vsb = new Uint8Array(VSB_SIZE);
  vsb.set([0x45, 0x32, 0], 0x10);
  const patch = { ...raw("e12fff1e"), builds: ["synth"] };
  patch.changes[0].expect = await sha256(vsb.subarray(FREE, FREE + 4));
  const originalHash = await sha256(vsb);
  const kind = await classify(vsb, [patch], STOCK_SHA256, originalHash);
  assert.equal(kind.kind, "synth");
  const flow = step(newFlow(), { type: "input", input: kind });
  assert.equal(flow.origin, "synth");
  assert.equal(flow.phase, "ready");
  assert.equal(allowed(flow).patch, true);
  assert.equal(cardFolder("synth"), "KORG/electribe/System/");
  const changed = Uint8Array.from(vsb);
  changed[0x1000] = 1;
  assert.equal((await classify(changed, [patch], STOCK_SHA256, originalHash)).kind, "unknown");
  const patched = await applyPatches(vsb, [patch]);
  assert.equal(patched.ok, true);
  assert.equal((await classify(patched.bytes, [patch], STOCK_SHA256, originalHash)).kind, "blech");
});

test("a copy that passed before is not checked again, any other copy is", async () => {
  const input = Uint8Array.of(1, 2, 3);
  const output = Uint8Array.of(1, 2, 4);
  const list = { format: "gelumpe-verified", version: 1, results: [{ input: await sha256(input), output: await sha256(output), set: "blech", checks: 87, date: "2026-10-17" }] };
  const report = await verifiedReport(input, output, list);
  assert.equal(report.ok, true);
  assert.deepEqual(report.checks.map(c => [c.id, c.ok]), [["verified", true]]);
  assert.match(report.checks[0].detail, /87 Prüfungen/);
  assert.equal(checkName("verified"), "Schon geprüft");
  assert.equal(await verifiedReport(input, Uint8Array.of(9), list), null, "a different result");
  assert.equal(await verifiedReport(Uint8Array.of(9), output, list), null, "a different input");
  assert.equal(await verifiedReport(input, output, null), null);
  assert.equal(await verifiedReport(input, output, { ...list, format: "x" }), null);
});

test("the list of checked copies holds only hashes", () => {
  const list = JSON.parse(readFileSync(fileURLToPath(new URL(`../${VERIFIED_URL}`, import.meta.url)), "utf8"));
  assert.equal(list.format, "gelumpe-verified");
  for (const r of list.results) {
    assert.match(r.input, /^[0-9a-f]{64}$/);
    assert.match(r.output, /^[0-9a-f]{64}$/);
    assert.ok(r.checks > 0);
  }
});
