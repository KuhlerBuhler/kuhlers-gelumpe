import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync, utimesSync } from "node:fs";
import { join } from "node:path";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tempDir } from "./support/lifetime.mjs";
import { runtimePatchPath, runtimePatchStale, RUNTIME_BUILDS } from "../tools/patch/ensure-runtime.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));

test("the three builds have one file each, and Korg's own build carries no suffix", () => {
  assert.deepEqual(RUNTIME_BUILDS, ["hacktribe", "stock", "synth"]);
  assert.equal(runtimePatchPath("hacktribe", "/r"), "/r/data/patches/script-runtime.json");
  assert.equal(runtimePatchPath("stock", "/r"), "/r/data/patches/script-runtime-stock.json");
  assert.equal(runtimePatchPath("synth", "/r"), "/r/data/patches/script-runtime-synth.json");
  assert.throws(() => runtimePatchPath("blue", "/r"), /unknown runtime build: blue/);
});

test("a file that is missing or older than the sources is built, a fresh one is left alone", () => {
  const dir = tempDir("cee-ensure-runtime-");
  for (const source of ["tools/patch", "src/script", "data/script"]) mkdirSync(join(dir, source, "nested"), { recursive: true });
  writeFileSync(join(dir, "tools/patch/script_hooks.py"), "x");
  writeFileSync(join(dir, "data/script/nested/contract.mjs"), "x");
  const older = new Date(Date.now() - 60_000);
  const newer = new Date(Date.now() + 60_000);
  utimesSync(join(dir, "tools/patch/script_hooks.py"), older, older);
  utimesSync(join(dir, "data/script/nested/contract.mjs"), older, older);

  const out = runtimePatchPath("stock", dir);
  assert.equal(runtimePatchStale("stock", dir), true, "no file yet");
  mkdirSync(join(dir, "data/patches"), { recursive: true });
  writeFileSync(out, "{}");
  utimesSync(out, older, older);
  assert.equal(runtimePatchStale("stock", dir), true, "as old as the sources");
  const future = new Date(Date.now() + 120_000);
  utimesSync(out, future, future);
  assert.equal(runtimePatchStale("stock", dir), false, "built after the sources");
});

test("the files are built by whoever needs them, not committed", () => {
  const ignore = readFileSync(join(root, ".gitignore"), "utf8");
  for (const name of ["script-runtime.json", "script-runtime-stock.json", "script-runtime-synth.json"]) {
    assert.match(ignore, new RegExp(`^data/patches/${name.replace(".", "\\.")}$`, "m"), `${name} is gitignored`);
  }
  for (const file of ["tools/test-runner.mjs", "tools/start.mjs", "tools/serve.mjs", "tools/build-site.mjs", "tools/emu/build-sidecar.mjs"]) {
    assert.match(readFileSync(join(root, file), "utf8"), /ensureRuntimePatches/, `${file} builds what is missing first`);
  }
  // The image carries them too, and data/patches belongs to the container's user: the container runs as node and
  // died on the lock file of a folder root owns (workflow Test, job docker).
  const dockerfile = readFileSync(join(root, "Dockerfile"), "utf8");
  assert.match(dockerfile, /node tools\/patch\/ensure-runtime\.mjs/, "the image builds the patches");
  assert.match(dockerfile, /^\s*&& chown -R node:node .*data\/patches$/m, "data/patches belongs to node");
});
