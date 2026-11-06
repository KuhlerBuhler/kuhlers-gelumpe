import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { emuPython } from "./support/emu.mjs";
import { run, slots } from "./support/spawn.mjs";

// The service itself needs no firmware and no Unicorn, so it runs everywhere
// Python does; the tests drive it with a stand-in machine. One Python process per
// module, side by side; the timer test, which boots the firmware, one per case.
const dir = fileURLToPath(new URL("../tools/emu/", import.meta.url));
const python = emuPython();
const probe = spawnSync(python, ["--version"], { encoding: "utf8" });
const skip = probe.error ? `${python} not available` : false;
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";

const modules = readdirSync(dir).filter(f => /^test_\w+\.py$/.test(f)).map(f => f.slice(0, -3)).sort();
const cases = module => [...readFileSync(`${dir}${module}.py`, "utf8").matchAll(/^    def (test_\w+)\(/gm)].map(m => m[1]);
// The timer and snapshot tests need the firmware (E2_VSB), and only the emulation runs ask for that.
const env = !local ? { ...process.env, E2_VSB: "" } : process.env;

async function unittest(target) {
  const r = await run(python, ["-m", "unittest", target], { timeout: 600_000, cwd: dir, env });
  assert.ifError(r.error);
  // A run the system ended has no exit status, and "null" alone hides whether it was killed for memory.
  const why = r.signal ? `was killed by ${r.signal}` : `exited ${r.status}`;
  assert.equal(r.status, 0, `${target} ${why}\n${r.stderr || r.stdout}`);
}

describe("emulator service and models", { concurrency: slots, skip }, () => {
  for (const module of modules) {
    if (module === "test_timer") {
      for (const name of cases(module)) test(`emulator models: ${module} ${name}`, () => unittest(`${module}.TimerTest.${name}`));
    } else {
      test(`emulator service and models: ${module}`, () => unittest(module));
    }
  }
});
