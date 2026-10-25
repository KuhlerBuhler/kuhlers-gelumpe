import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { emuPython } from "./support/emu.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));
test("bounded sample path probe guards and ARM drivers", () => {
  const run = spawnSync(emuPython(), ["tools/device/test_sample_swap_paths.py"], {
    cwd: root, encoding: "utf8", timeout: 60000,
  });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stdout + run.stderr);
});
