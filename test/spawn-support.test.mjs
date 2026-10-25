import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

function slots(jobs) {
  const env = { ...process.env };
  if (jobs === undefined) delete env.GELUMPE_JOBS;
  else env.GELUMPE_JOBS = jobs;
  const probe = spawnSync(process.execPath, ["--input-type=module", "-e", `
    import { slots } from ${JSON.stringify(new URL("./support/spawn.mjs", import.meta.url).href)};
    import { availableParallelism } from "node:os";
    console.log(JSON.stringify({ slots, fallback: Math.max(2, Math.floor(availableParallelism() / 2)) }));
  `], { env, encoding: "utf8" });
  assert.equal(probe.status, 0, probe.stderr);
  return JSON.parse(probe.stdout);
}

test("Python test concurrency honors GELUMPE_JOBS, including a serial run", () => {
  for (const jobs of ["1", "2", "3"]) assert.equal(slots(jobs).slots, Number(jobs));
});

test("missing or invalid worker counts preserve the core-based default", () => {
  for (const jobs of [undefined, "", "0", "-1", "1.5", "bad", "Infinity"]) {
    const result = slots(jobs);
    assert.equal(result.slots, result.fallback, String(jobs));
  }
});
