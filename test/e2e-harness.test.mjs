import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";

test("a browser setup failure closes its HTTP server and lets the test process exit", () => {
  const result = spawnSync(process.execPath, ["--input-type=module", "-e", `
import { setUp } from "./test/e2e/harness.mjs";
try {
  await setUp(dir => { console.log(JSON.stringify({ dir })); return []; });
  process.exitCode = 1;
} catch (error) {
  if (!/channel/i.test(error.message)) throw error;
  console.log("browser-failure-reported");
}
`], { env: { ...process.env, E2E_CHANNEL: "gelumpe-invalid-channel" }, encoding: "utf8", timeout: 10_000, killSignal: "SIGKILL" });
  try {
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /browser-failure-reported/);
  } finally {
    const line = result.stdout?.split("\n").find(value => value.startsWith('{"dir":'));
    if (line) rmSync(JSON.parse(line).dir, { recursive: true, force: true });
  }
});
