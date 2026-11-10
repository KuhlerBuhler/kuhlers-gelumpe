import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { buildSpettro } from "../tools/patch/spettro.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { checkRam, declaredAreas, writtenAreas } from "../src/ramspans.mjs";
import { applyPatches, selectFor } from "../src/patch.mjs";
import { SPETTRO_SITES } from "../data/spettro-sites.mjs";
import { run } from "./support/spawn.mjs";
import { tempDir, release } from "./support/lifetime.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const venv = path.join(root, "tools/emu/.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const probe = spawnSync(python, ["-c", "import unicorn,numpy"], { encoding: "utf8" });
const skip = probe.status === 0 ? false : "Python with Unicorn and NumPy is required for Spettro ARM checks";
if (skip && process.env.E2_ARM_REQUIRED) throw new Error(skip);
const cached = {};
const built = (build = "hacktribe") => cached[build] ??= buildSpettro(build);
const baseBuild = process.env.E2_SPETTRO_BUILD || "hacktribe";

for (const build of ["hacktribe", "stock"])
test(`Spettro derives its hooks from the current ${build} runtime and declares only that build`, { skip }, async () => {
  const { patch, layout, blob } = await built(build);
  assert.deepEqual(patch.builds, [build]);
  assert.deepEqual(patch.hooks.map(h => Number(h.site)), Object.values(SPETTRO_SITES));
  assert.equal(checkHooks([patch]).ok, true);
  assert.deepEqual(checkRam([patch]), []);
  assert.equal(layout.contextBytes, 103424);
  assert.ok(layout.codeAddress + layout.codeBytes <= 0xC014FE00);
  assert.ok(blob.length > 0);
  assert.equal(Buffer.from(blob.slice(36, 43)).toString(), "Spettro");
  assert.ok(selectFor([patch], build === "stock" ? "hacktribe" : "stock").reasons.length);
  assert.ok(selectFor([patch], "synth").reasons.length);
  await assert.rejects(buildSpettro("synth"), /only the red Sampler/);
});

for (const build of ["hacktribe", "stock"])
test(`Spettro on ${build} never overlaps any current patch allocation except its two intended runtime instructions`, { skip }, async () => {
  const { patch } = await built(build);
  const set = JSON.parse(readFileSync(new URL("../data/patches/blech.json", import.meta.url))).patches
    .map(p => JSON.parse(readFileSync(path.join(root, p))));
  const selected = selectFor(set, build);
  assert.deepEqual(selected.reasons, []);
  const runtime = selected.patches.find(p => p.id === "script-runtime");
  assert.ok(runtime);
  assert.equal(patch.shares.length, 2);
  // The second-stage add-on deliberately overlays two runtime instructions.
  // Keep its RAM owner present while checking shares, without applying its code twice.
  assert.deepEqual(checkRam([patch, { ...runtime, changes: [] }]), []);
  const code = writtenAreas(patch)[0];
  for (const other of selected.patches) {
    const spans = [...writtenAreas(other), ...declaredAreas(other).own];
    for (const area of spans) assert.ok(code.end <= area.start || area.end <= code.start, other.id);
  }
  const copies = patch.changes.filter(c => c.copy);
  assert.ok(copies.length > 3);
  assert.equal(copies.flatMap(c => c.over).length, 2);
  for (const c of copies) {
    assert.equal(c.copy.file, c.file);
    assert.equal(c.copy.expect, c.expect);
    assert.match(c.expect, /^[a-f0-9]{64}$/);
    assert.equal(c.bytes, undefined, "guards carry hashes and user-side copies, not native bytes");
  }
});

test("Spettro ARM stream, FFT and renderer match independent generated-signal references", { skip, timeout: 180000 }, async () => {
  const result = await run(python, ["-B", "-m", "unittest", "discover", "-s", "tools/emu/spettro", "-p", "test_*.py"], { cwd: root, timeout: 170000 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
});

test("Spettro accepts its exact BLECH base and rejects a changed runtime", { skip: !process.env.E2_SPETTRO_BASE || skip }, async () => {
  const image = new Uint8Array(readFileSync(process.env.E2_SPETTRO_BASE));
  const { patch } = await built(baseBuild);
  const result = await applyPatches(image, [patch]);
  assert.equal(result.ok, true, result.reasons?.join("\n"));
  const at = patch.changes.find(c => c.copy && c.over.length).file;
  const wrong = image.slice(); wrong[at] ^= 1;
  const rejected = await applyPatches(wrong, [patch]);
  assert.equal(rejected.ok, false);
  const before = image.slice(0xF9F10, 0x13C1B0);
  assert.deepEqual(result.bytes.slice(0xF9F10, 0x13C1B0), before);
  assert.deepEqual(result.bytes.slice(0, 256), image.slice(0, 256));
});

test("Spettro opens through the real plugin menu and preserves native controls", { skip: !process.env.E2_SPETTRO_BASE || skip, timeout: 180000 }, async () => {
  const { patch, layout, blob } = await built(baseBuild);
  const result = await applyPatches(new Uint8Array(readFileSync(process.env.E2_SPETTRO_BASE)), [patch]);
  assert.equal(result.ok, true, result.reasons?.join("\n"));
  const folder = tempDir("gelumpe-spettro-");
  try {
    const image = path.join(folder, "candidate.bin"), meta = path.join(folder, "layout.json"), plugin = path.join(folder, "Spettro.blech");
    writeFileSync(image, result.bytes); writeFileSync(meta, JSON.stringify(layout)); writeFileSync(plugin, blob);
    const check = await run(python, ["-B", "tools/emu/spettro_cases.py", "--patched", image, "--layout", meta, "--plugin", plugin], {
      cwd: root, timeout: 170000, env: { ...process.env, GELUMPE_CACHE_DIR: path.join(folder, "cache") },
    });
    assert.equal(check.status, 0, check.stderr || check.stdout);
    assert.match(check.stdout, /"ok": true/);
  } finally { release(folder); }
});
