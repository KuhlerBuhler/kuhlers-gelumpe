import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { API, ERROR, OPCODES } from "../data/script/contract.mjs";
import { decodeBlob, decodeInstructions } from "../src/script/blob.mjs";
import { armCases } from "./fixtures/script-arm-programs.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const localPython = fileURLToPath(new URL("../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (fs.existsSync(localPython) ? localPython : "python3");
const probe = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const available = !probe.error && probe.status === 0;
const required = process.env.E2_ARM_REQUIRED === "1";
const cases = armCases();

test("ARM comparison corpus covers every opcode, every API and both fault stages", () => {
  const used = new Set();
  const called = new Set();
  for (const c of cases) {
    for (const s of c.scripts) {
      const parts = decodeBlob(Buffer.from(s.blob, "hex"));
      if (parts.ok) for (const i of decodeInstructions(parts.code).list ?? []) used.add(i.info.name);
    }
    for (const call of c.expected.calls) called.add(call[0]);
  }
  assert.deepEqual([...used].sort(), OPCODES.map(o => o.name).sort());
  assert.deepEqual([...called].sort(), API.map(a => a.name).sort());
  assert.ok(cases.some(c => c.expected.loads.some(l => !l.ok)));
  assert.ok(cases.some(c => c.expected.runs.some(r => r.code === ERROR.FUEL)));
  assert.ok(cases.some(c => c.expected.runs.some(r => r.code === ERROR.DIV_ZERO)));
  assert.ok(cases.some(c => c.expected.scripts.some(s => s?.vars.length === 65536)));
  assert.ok(cases.some(c => c.expected.scripts.length > 16 && c.expected.scripts.every(s => s.state === "armed")));
});

test("native ARM loader and VM agree with the JS oracle", {
  skip: !available && !required ? `${python}: Unicorn not installed` : false,
}, () => {
  assert.ok(available, `Unicorn required: ${probe.error?.message ?? probe.stderr}`);
  const result = spawnSync(python, ["tools/patch/test_script_vm.py", "--cases"], {
    cwd: root, input: JSON.stringify({ cases }), encoding: "utf8", timeout: 300_000,
    maxBuffer: 32 * 1024 * 1024,
  });
  if (result.error) assert.fail(`${result.error.message}\n${result.stderr}`);
  assert.equal(result.status, 0, result.stderr);
  const snapshots = JSON.parse(result.stdout);
  assert.equal(snapshots.length, cases.length);
  cases.forEach((c, i) => assert.deepEqual(snapshots[i], c.expected, c.name));
});
