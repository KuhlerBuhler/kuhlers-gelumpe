import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
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
// These modules have a test of their own that also demands Unicorn in CI; running them here too doubled the slowest part of the suite.
const elsewhere = {
  "script-runtime.test.mjs": ["test_script_led", "test_script_display", "test_display_calibrate", "test_script_store", "test_script_file", "test_script_hw",
    "test_script_events", "test_script_synth"],
  "script-runtime-hooks.test.mjs": ["test_script_hooks", "test_script_vm_optimizations", "test_script_vm_validator"],
  "script-runtime-card.test.mjs": ["test_script_card"],
  "blech-sysex.test.mjs": ["test_blech_sysex_buffer"],
  "sample-swap-io.test.mjs": ["test_sample_swap_io"],
  "sample-swap.test.mjs": ["test_sample_swap"],
  "sample-transaction-native.test.mjs": ["test_sample_store"],
  "native-dsp-scope.test.mjs": ["test_native_dsp_scope"],
  "capture-fault.test.mjs": ["test_capture_fault"],
  "sample-export-fault.test.mjs": ["test_sample_export_fault"],
  "sample-owner.test.mjs": ["test_sample_owner"],
  "sample-snapshot.test.mjs": ["test_sample_snapshot"],
  "sample-versions.test.mjs": ["test_sample_versions"],
};
const owned = new Set(Object.values(elsewhere).flat().map(name => `${name}.py`));
const modules = readdirSync(dir).filter(f => /^test_.*\.py$/.test(f) && !owned.has(f)).sort();

test("every module left out here is run by the test that names it", () => {
  for (const [file, names] of Object.entries(elsewhere)) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    for (const name of names) {
      assert.ok(readdirSync(dir).includes(`${name}.py`), `${name}.py is gone; take it out of the list`);
      assert.match(source, new RegExp(`\\b${name}\\b`), `${file} does not run ${name}`);
    }
  }
});

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
