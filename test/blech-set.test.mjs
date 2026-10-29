import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { applyPatches, buildsOf, selectFor } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { buildRuntimePatch } from "../tools/patch/script_runtime.mjs";

const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const SET = read("data/patches/blech.json");
const patches = SET.patches.map(read);
const python = process.env.E2_EMU_PYTHON || new URL("../tools/emu/.venv/bin/python", import.meta.url).pathname;
const builderAvailable = existsSync(python);

test("the BLECH set lists patch files that exist, with unique ids per build, and the hook register accepts them together", () => {
  assert.equal(SET.format, "gelumpe-patch-set");
  assert.equal(SET.version, 1);
  assert.deepEqual(patches.map(p => p.id), ["splash-editor", "mfx-switch", "pattern-switch", "tap-motion", "note-assistant", "dice", "pad-colors", "load-bar", "sample-errors", "sample-swap", "script-runtime", "script-runtime", "blechtribe", "blechtribe", "splash", "blech-theme", "preset-tables", "preset-tables", "fx-catalog", "synth-filters", "power-off", "last-pattern", "init-pattern", "stereo-pad", "blech-version", "doom-loader", "blech-sysex", "blech-sysex"]);
  for (const build of ["hacktribe", "stock"]) {
    const chosen = selectFor(patches, build);
    assert.deepEqual(chosen.reasons, [], build);
    assert.deepEqual(chosen.patches.map(p => p.id), ["splash-editor", "mfx-switch", "pattern-switch", "tap-motion", "note-assistant", "dice", "pad-colors", "load-bar", "sample-errors", "sample-swap", "script-runtime", "blechtribe", "splash", "blech-theme", "preset-tables", "fx-catalog", ...(build === "stock" ? ["synth-filters"] : []), "power-off", "last-pattern", "init-pattern", "stereo-pad", "blech-version", "doom-loader", "blech-sysex"], build);
    const registered = checkHooks(chosen.patches);
    assert.equal(registered.ok, true, registered.reasons.join(" "));
  }
});

test("the build-specific patches have one variant per supported firmware", () => {
  const folder = patches.filter(p => p.id === "blechtribe");
  assert.deepEqual(folder.map(p => buildsOf(p)), [["hacktribe"], ["stock"]]);
  assert.match(folder[1].name, /electribe sampler/);
  assert.deepEqual(patches.filter(p => p.id === "preset-tables").map(p => buildsOf(p)), [["hacktribe"], ["stock"]]);
  assert.deepEqual(patches.filter(p => p.id === "blech-sysex").map(p => buildsOf(p)), [["hacktribe"], ["stock"]], "the protection table differs: Korg keeps its presets elsewhere");
  for (const p of patches.filter(p => !["blechtribe", "preset-tables", "synth-filters", "blech-sysex", "script-runtime"].includes(p.id))) assert.deepEqual(buildsOf(p), ["hacktribe", "stock"], p.id);
  assert.deepEqual(buildsOf(patches.find(p => p.id === "synth-filters")), ["stock"], "Hacktribe's firmware has the synth filters itself");
  assert.deepEqual(patches.filter(p => p.id === "script-runtime").map(p => buildsOf(p)), [["hacktribe"], ["stock"]]);
  // both variants fit their window: what the new text leaves of it is zeros, the text itself is the same
  const texts = folder.map(p => p.changes.map(c => Buffer.from(c.bytes, "hex")));
  const [hack, stock] = texts;
  assert.deepEqual(hack.map(t => t.toString("latin1").replace(/\0+$/, "")), ["blechtribe", "KORG/blechtribe/"]);
  assert.deepEqual(stock.map(t => t.toString("latin1").replace(/\0+$/, "")), ["blechtribe", "KORG/blechtribe/"]);
  assert.deepEqual([hack, stock].map(t => t.map(b => b.length)), [[11, 17], [18, 24]], "the windows of hacktribe + NUL and of electribe sampler + NUL");
  assert.equal(folder[0].changes[0].file, folder[1].changes[0].file, "same address in both builds");
});

for (const build of ["hacktribe", "stock"]) {
  const file = `data/patches/script-runtime${build === "stock" ? "-stock" : ""}.json`;
  test(`${file} is what the builder produces today`, { skip: builderAvailable ? false : "no python for the builder" }, () => {
    assert.deepEqual(JSON.parse(buildRuntimePatch(build)), read(file), `rebuild with node tools/patch/script_runtime.mjs --build ${build}`);
  });
}

test("the Synth set includes its reproducible native runtime and accepts the hooks together", { skip: builderAvailable ? false : "no python for the builder" }, () => {
  const synth = read("data/patches/blech-synth.json").patches.map(read);
  const runtime = synth.find(patch => patch.id === "script-runtime");
  assert.ok(runtime, "the Synth set includes the menu and plugin runtime");
  assert.deepEqual(runtime, JSON.parse(buildRuntimePatch("synth")));
  assert.deepEqual(selectFor(synth, "synth").patches, synth);
  const registered = checkHooks(synth);
  assert.equal(registered.ok, true, registered.reasons.join(" "));
});

test("the set applies to the user's firmware when one is given", { skip: process.env.E2_VSB ? false : "set E2_VSB" }, async () => {
  const applied = await applyPatches(new Uint8Array(readFileSync(process.env.E2_VSB)), patches);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
});

test("the set applies to Korg's own 2.02 when one is given, and the folder is the stock window", { skip: process.env.E2_STOCK_VSB ? false : "set E2_STOCK_VSB" }, async () => {
  const stock = new Uint8Array(readFileSync(process.env.E2_STOCK_VSB));
  const applied = await applyPatches(stock, patches);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
  const at = 0xC00A5656 - 0xC0000000 + 0x100;
  assert.equal(Buffer.from(applied.bytes.subarray(at, at + 18)).toString("latin1"), "blechtribe" + "\0".repeat(8));
  assert.deepEqual(applied.spans.filter(s => s.patch === "blechtribe").map(s => s.length), [18, 24]);
});

for (const [label, env, file] of [["Hacktribe", "E2_VSB", "data/patches/blechtribe.json"], ["Korg's own 2.02", "E2_STOCK_VSB", "data/patches/blechtribe-stock.json"], ["Korg's blue 2.02", "E2_BLUE_VSB", "data/patches/blechtribe-synth.json"]]) {
  test(`${file} is what tools/patch/blechtribe.py builds from your ${label} file`, { skip: process.env[env] && builderAvailable ? false : `set ${env}` }, () => {
    const out = spawnSync(python, ["tools/patch/blechtribe.py", "--vsb", process.env[env]], { cwd: new URL("..", import.meta.url).pathname, encoding: "utf8" });
    assert.equal(out.status, 0, out.stderr);
    assert.deepEqual(JSON.parse(out.stdout), read(file));
  });
}
