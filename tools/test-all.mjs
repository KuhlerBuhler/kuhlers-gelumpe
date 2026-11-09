#!/usr/bin/env node
/**
 * Every test there is, side by side: the unit and emulator tests and the browser tests.
 *
 *   npm run test:all
 *
 * With E2_VSB (and E2_PATTERNS) set the tests against your own files run too, as in
 * `test:local` and `test:emu`; without them only what runs everywhere runs, as in CI.
 * A suite's output is shown in full when it fails, as a summary when it passes.
 * Passing emulator results are kept per input (tools/emu/bootcache.py); GELUMPE_CACHE=off runs them again.
 */
import { planAll, runNode } from "./test-runner.mjs";

const plan = planAll();
const runSuite = async suite => ({ name: suite.name, ...await runNode(suite, { capture: true }) });
const results = [];
if (plan.parallel) results.push(...await Promise.all(plan.suites.map(runSuite)));
else for (const suite of plan.suites) results.push(await runSuite(suite));
for (const r of results) {
  const summary = r.output.split("\n").filter(l => /^ℹ (tests|pass|fail|cancelled|skipped|duration_ms)/.test(l)).join("  ").replaceAll("ℹ ", "");
  console.log(`${r.status === 0 ? "ok  " : "FAIL"} ${r.name}: ${r.seconds.toFixed(0)} s, ${summary}`);
  if (r.error) console.log(r.error.message);
  if (r.signal) console.log(`terminated by ${r.signal}`);
  if (r.status !== 0) console.log(r.output);
}
if (!process.env.E2_VSB) console.log("Without E2_VSB the emulator tests are skipped (see README).");
process.exitCode = results.every(r => r.status === 0) ? 0 : 1;
