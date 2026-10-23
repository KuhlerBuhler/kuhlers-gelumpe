import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { availableParallelism } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// The assembler behind the patches (tools/patch/arm.py) needs only Python. With
// Capstone installed its lines are also disassembled, and with E2_VSB set it
// has to reproduce the user's firmware instruction by instruction.
// One test per module, side by side: all of them in one run took 210 s on a fast Mac and outran the 300 s a test may take in CI.
const dir = fileURLToPath(new URL("../tools/patch/", import.meta.url));
const root = fileURLToPath(new URL("../", import.meta.url));
const python = process.env.E2_EMU_PYTHON || "python3";
const probe = spawnSync(python, ["--version"], { encoding: "utf8" });
const skip = probe.error ? `${python} not available` : false;
const modules = readdirSync(dir).filter(f => /^test_.*\.py$/.test(f)).sort();

const run = module => new Promise((resolve, reject) => {
  const child = spawn(python, ["-m", "unittest", "discover", "-s", dir, "-p", module], {
    cwd: dir,
    // Some modules import tools.patch.*; alone they need the repository on the path that another module used to put there.
    env: { ...process.env, PYTHONPATH: [root, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
  });
  let err = "";
  child.stderr.on("data", d => { err += d; });
  child.on("error", reject);
  child.on("close", status => resolve({ status, err }));
});

describe("assembler: known encodings, pools, sections and refusals", { concurrency: Math.max(1, availableParallelism() - 1) }, () => {
  test("there are Python tests to run", { skip }, () => assert.ok(modules.length > 0));
  for (const module of modules) {
    test(module, { skip }, async () => {
      const r = await run(module);
      assert.equal(r.status, 0, r.err);
    });
  }
});
