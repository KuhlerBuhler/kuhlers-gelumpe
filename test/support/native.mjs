/**
 * The Python modules of the native runtime (tools/patch/test_*.py) as node tests: one Python process per
 * test, skipped without Unicorn unless E2_ARM_REQUIRED=1 demands it, and failed when a module skipped a case.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { run } from "./spawn.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../../tools/emu/.venv/Scripts/python.exe" : "../../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const probe = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const available = !probe.error && probe.status === 0;
const required = process.env.E2_ARM_REQUIRED === "1";

/** `modules` are names in tools/patch/, run together in one process. */
export function nativeTest(name, modules, timeout = 300_000) {
  test(name, { skip: !available && !required ? "Unicorn not installed" : false }, async () => {
    assert.ok(available, probe.error?.message ?? probe.stderr);
    const result = await run(python, ["-m", "unittest", ...modules.map(module => `tools/patch/${module}.py`)], { cwd: root, timeout });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.doesNotMatch(result.stderr, /skipped=/);
  });
}
