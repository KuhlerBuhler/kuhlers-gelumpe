import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// The assembler behind the patches (tools/patch/arm.py) needs only Python. With
// Capstone installed its lines are also disassembled, and with E2_VSB set it
// has to reproduce the user's firmware instruction by instruction.
const dir = fileURLToPath(new URL("../tools/patch/", import.meta.url));
const python = process.env.E2_EMU_PYTHON || "python3";
const probe = spawnSync(python, ["--version"], { encoding: "utf8" });
const skip = probe.error ? `${python} not available` : false;

test("assembler: known encodings, pools, sections and refusals", { skip }, () => {
  const r = spawnSync(python, ["-m", "unittest", "discover", "-s", dir, "-p", "test_*.py"], {
    encoding: "utf8", timeout: 300_000, cwd: dir,
  });
  assert.ifError(r.error);
  assert.equal(r.status, 0, r.stderr);
});
