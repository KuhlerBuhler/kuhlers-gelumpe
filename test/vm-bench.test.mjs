import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { encodeBlob } from "../src/script/blob.mjs";
import { loadScript } from "../src/script/vm.mjs";

// tools/device/vm_bench.py measures a bytecode VM on the device. Its opcode
// table must match the contract, its ARM stub must agree with its own
// reference VM (the stub runs need Unicorn, E2_EMU_PYTHON points at the
// emulator's venv), and that reference must agree with the JS reference VM.
const dir = fileURLToPath(new URL("../tools/device/", import.meta.url));
const python = process.env.E2_EMU_PYTHON || "python3";
const probe = spawnSync(python, ["--version"], { encoding: "utf8" });
const skip = probe.error ? `${python} not available` : false;

test("vm_bench: opcode table, ARM stub against the reference VM, write window", { skip }, () => {
  const r = spawnSync(python, ["-m", "unittest", "test_vm_bench"], { encoding: "utf8", timeout: 300_000, cwd: dir });
  assert.ifError(r.error);
  assert.equal(r.status, 0, r.stderr);
});

test("vm_bench: the bench programs give the same result in the JS reference VM", { skip }, () => {
  const r = spawnSync(python, ["vm_bench.py", "--dump-programs"], { encoding: "utf8", timeout: 60_000, cwd: dir });
  assert.ifError(r.error);
  assert.equal(r.status, 0, r.stderr);
  const programs = JSON.parse(r.stdout);
  let checked = 0;
  for (const [name, p] of Object.entries(programs)) {
    if (p.bench_only) continue;
    const bytes = encodeBlob({ code: Buffer.from(p.code, "hex"), varCount: 12, stackMax: 4, lines: [] });
    for (const c of p.cases) {
      const l = loadScript(bytes);
      assert.ok(l.ok, `${name}: ${l.error?.message}`);
      l.script.vars[0] = c.n;
      const run = l.script.start({ fuel: 1e9 });
      assert.equal(run.ok, true, `${name} n=${c.n}: ${run.message}`);
      assert.deepEqual(Array.from(l.script.vars, v => v >>> 0), c.vars, `${name} n=${c.n}`);
      assert.equal(run.ops, c.ops, `${name} n=${c.n} operations`);
      assert.equal(run.cost, c.cost, `${name} n=${c.n} cost`);
      checked += 1;
    }
  }
  assert.ok(checked >= 30, `only ${checked} cases checked`);
});
