import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { emuPython } from "./support/emu.mjs";

test("sample swap probe validates offline guards, transfer bounds and CRC protocol", () => {
  const python = emuPython();
  const cwd = fileURLToPath(new URL("../tools/device/", import.meta.url));
  const result = spawnSync(python, ["-m", "unittest", "test_sample_swap_probe"], {
    cwd, encoding: "utf8", timeout: 30000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
