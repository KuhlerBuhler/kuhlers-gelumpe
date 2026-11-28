import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../src/patch.mjs";
import { emuPython } from "./support/emu.mjs";
import { run } from "./support/spawn.mjs";

// The watchdog stub over BLECH WRITE and EXEC, the path it takes to the device (docs/messungen/2026-11-16-watchdog-neustart.md).
// The model cases without firmware are tools/emu/test_watchdog.py.
const root = fileURLToPath(new URL("../", import.meta.url));
const read = path => JSON.parse(readFileSync(join(root, path), "utf8"));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !vsb ? "E2_VSB not set" : !local ? "emulation only runs in test:local or test:emu" : false;

test("emulate:2026-11-16/watchdog-neustart, the stub through BLECH EXEC resets the chip after 100 ms and it starts again", { skip }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-watchdog-"));
  try {
    const set = read("data/patches/blech.json");
    const res = await applyPatches(new Uint8Array(readFileSync(vsb)), set.patches.map(read));
    assert.equal(res.ok, true, res.reasons.join(" "));
    const path = join(dir, "SYSTEM.VSB");
    writeFileSync(path, res.bytes);
    const r = await run(emuPython(), [join(root, "tools/device/watchdog_restart.py"), "--emu", path, "--reboot"], { timeout: 900_000 });
    assert.ifError(r.error);
    assert.equal(r.status, 0, r.stderr);
    const out = JSON.parse(r.stdout);
    assert.deepEqual(out.before_exec, { reset: null, watchdog: "off", asserts: 0 }, "the firmware has not armed it by itself");
    assert.equal(out.exec_value, 1, "EXEC answers: armed");
    assert.equal(out.reset?.cause, "timeout");
    assert.ok(out.reset_after_answer_ms > 50 && out.reset_after_answer_ms <= 100, `reset ${out.reset_after_answer_ms} ms after the answer`);
    assert.deepEqual(out.asserts, []);
    assert.ok(out.reboot.booted_ms > 0, "the new start reaches the main screen");
    assert.deepEqual([out.reboot.asserts, out.reboot.reset, out.reboot.watchdog], [[], null, "off"]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
