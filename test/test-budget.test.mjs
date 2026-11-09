import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { run } from "./support/spawn.mjs";

test("the assembler suite respects the shared Python process budget", { skip: process.platform === "win32" }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-test-budget-"));
  try {
    const executable = join(dir, "python");
    const events = join(dir, "events");
    writeFileSync(executable, `#!${process.execPath}\n` + `
import { appendFileSync } from "node:fs";
if (!process.argv.includes("--version")) {
  const file = ${JSON.stringify(events)};
  appendFileSync(file, "+" + process.pid + "\\n");
  setTimeout(() => appendFileSync(file, "-" + process.pid + "\\n"), 30);
}
`, { mode: 0o755 });
    const env = { ...process.env, E2_EMU_PYTHON: executable, GELUMPE_JOBS: "1" };
    delete env.NODE_TEST_CONTEXT;
    const result = await run(process.execPath, ["--test", "test/patch-arm.test.mjs"], {
      cwd: fileURLToPath(new URL("../", import.meta.url)), env, timeout: 30_000,
    });
    assert.equal(result.status, 0, result.stderr || result.stdout);
    let active = 0, peak = 0, started = 0;
    for (const line of readFileSync(events, "utf8").trim().split("\n")) {
      if (line.startsWith("+")) { active++; started++; } else active--;
      peak = Math.max(peak, active);
    }
    assert.ok(started > 5, "the suite must exercise its independent Python modules");
    assert.equal(active, 0);
    assert.equal(peak, 1, "GELUMPE_JOBS=1 allows one Python process at a time");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
