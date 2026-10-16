import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const python = process.env.E2_EMU_PYTHON || "python3";
const available = [spawnSync(python, ["--version"]), spawnSync("cc", ["--version"])].every(result => !result.error && result.status === 0);
const required = process.env.E2_DOOM_REQUIRED === "1" || process.env.E2_ARM_REQUIRED === "1";

test("Doom loader verifies SHA256 vectors and refuses unknown firmware or occupied memory", {
  skip: !available && !required ? "requires Python and a host C compiler" : false,
}, () => {
  assert.ok(available, "Python and a host C compiler are required for the loader checks");
  const output = mkdtempSync(join(tmpdir(), "gelumpe-doom-loader-"));
  const result = spawnSync(python, ["tools/doom/loader_tests.py", "--output", output, "-v"], {
    cwd: fileURLToPath(new URL("../", import.meta.url)), encoding: "utf8", timeout: 60_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
