import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { planSuite, planAll, runNode } from "../tools/test-runner.mjs";

test("normal suites cap file concurrency and both nested Python layers within their CPU allocation", () => {
  for (const cores of [1, 2, 4, 8, 10, 16, 32]) {
    for (const mode of ["unit", "browser", "ci", "local", "emu"]) {
      const plan = planSuite(mode, { cores, env: {} });
      const jobs = Number(plan.env.GELUMPE_JOBS);
      assert.ok(plan.files >= 1 && plan.files <= 2);
      assert.ok(jobs >= 1 && jobs <= 2);
      assert.ok(plan.files * jobs * jobs <= cores, `${mode} on ${cores} cores`);
      assert.ok(plan.args.indexOf(`--test-concurrency=${plan.files}`) < plan.args.findIndex(a => a.startsWith("test/")));
    }
  }
});

test("the explicit one-process preference stays one; larger preferences remain bounded", () => {
  for (const cores of [1, 4, 10, 32]) {
    assert.equal(planSuite("unit", { cores, env: { GELUMPE_JOBS: "1" } }).env.GELUMPE_JOBS, "1");
    const plan = planSuite("unit", { cores, env: { GELUMPE_JOBS: "30" } });
    assert.ok(plan.files * Number(plan.env.GELUMPE_JOBS) ** 2 <= cores);
  }
  assert.equal(planSuite("unit", { cores: 10, env: {} }).env.GELUMPE_JOBS, "2");
  assert.equal(planSuite("unit", { cores: 4, env: {} }).env.GELUMPE_JOBS, "1");
});

test("timeouts, patterns and local-required flags survive planning", () => {
  assert.deepEqual(planSuite("unit", { cores: 4, env: {} }).args.slice(-1), ["test/*.test.mjs"]);
  assert.ok(planSuite("ci", { cores: 4, env: {} }).args.includes("--test-timeout=300000"));
  const browser = planSuite("browser", { cores: 4, env: {} });
  assert.ok(browser.args.includes("--test-timeout=180000"));
  assert.equal(browser.args.at(-1), "test/e2e/*.e2e.mjs");
  assert.equal(planSuite("local", { cores: 4, env: {} }).env.E2_LOCAL_REQUIRED, "1");
  const emu = planSuite("emu", { cores: 4, env: {} });
  assert.equal(emu.env.E2_EMU_REQUIRED, "1");
  assert.ok(emu.args.includes("test/emulator-fxcard.test.mjs"));
  assert.ok(emu.args.includes("test/emu-service.test.mjs"));
});

test("additional Node test options are placed before the file patterns", () => {
  const plan = planSuite("unit", { cores: 4, env: {}, args: ["--test-name-pattern", "some name", "--test-shard=1/2"] });
  assert.deepEqual(plan.args.slice(-4), ["--test-name-pattern", "some name", "--test-shard=1/2", "test/*.test.mjs"]);
});

test("test:all divides the budget and chooses sequential execution on one core", () => {
  for (const cores of [1, 2, 4, 10, 32]) {
    const all = planAll({ cores, env: {} });
    assert.equal(all.parallel, cores > 1);
    if (all.parallel) assert.ok(all.suites.reduce((sum, p) => sum + p.budget, 0) <= cores);
    else assert.ok(all.suites.every(p => p.budget === 1));
  }
  assert.equal(planAll({ cores: 4, env: { E2_VSB: "own", E2_PATTERNS: "own" } }).suites[0].env.E2_LOCAL_REQUIRED, "1");
  assert.equal(planAll({ cores: 4, env: { E2_VSB: "own" } }).suites[0].env.E2_EMU_REQUIRED, "1");
});

test("the launcher forwards a child failure and reports a launch error", async () => {
  const failed = await runNode({ args: ["-e", "process.exit(7)"], env: {} }, { capture: true });
  assert.equal(failed.status, 7);
  assert.equal(failed.signal, null);
  const missing = await runNode({ args: [], env: {} }, { executable: "gelumpe-no-such-test-node", capture: true });
  assert.equal(missing.status, null);
  assert.equal(missing.error.code, "ENOENT");
});

test("a child signal is preserved for the CLI exit handling", { skip: process.platform === "win32" }, async () => {
  const killed = await runNode({ args: ["-e", "process.kill(process.pid, 'SIGTERM')"], env: {} }, { capture: true });
  assert.equal(killed.status, null);
  assert.equal(killed.signal, "SIGTERM");
});

test("the package routes the normal test commands through the shared budget planner", () => {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  for (const name of ["test", "test:ci", "test:local", "test:e2e", "test:emu"]) {
    assert.match(pkg.scripts[name], /^node tools\/test-runner\.mjs /, name);
  }
});
