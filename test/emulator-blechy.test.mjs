import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { applyPatches } from "../src/patch.mjs";
import { BLECHY_SOURCE } from "../data/script/blechy-source.mjs";
import { compile } from "../src/script/compiler.mjs";
import { BLECH_SET_URL, loadBlechSet } from "../src/patcher.mjs";
import { run } from "./support/spawn.mjs";
import { Display } from "../src/script/display.mjs";
import { loadFrames } from "../tools/blechy-build.mjs";

// Blechy in the firmware, built into BLECH: the last page of the menu ring, no card needed, the wave after landing, tap, stroke,
// schranz, STOP with the bubble, EXIT, absent with EXIT held at power-on (tools/emu/blechy_cases.py).
// E2_VSB may be the original firmware (the BLECH set is applied here) or a file that already carries BLECH.
const root = fileURLToPath(new URL("../", import.meta.url));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const unicorn = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : unicorn.status !== 0 ? "Unicorn not installed" : false;

test("Blechy runs in the firmware: the ring page, the wave, every state shows, the frame stays inside its budget, EXIT leaves", { skip }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-blechy-"));
  try {
    const set = await loadBlechSet(async url => JSON.parse(readFileSync(join(root, url), "utf8")), BLECH_SET_URL);
    const base = readFileSync(vsb);
    const patched = await applyPatches(new Uint8Array(base), set.patches);
    const firmware = join(dir, "BLECH.VSB");
    writeFileSync(firmware, patched.ok ? patched.bytes : base);
    const request = join(dir, "request.json");
    const built = compile(BLECHY_SOURCE, { name: "Blechy" });
    assert.ok(built.ok);
    writeFileSync(request, JSON.stringify({ symbols: built.info.symbols }));
    const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
    const result = await run(python, ["tools/emu/blechy_cases.py", "--base", firmware, "--request", request, "--png-dir", join(dir, "png"), ...flash.length ? ["--flash", ...flash] : []], {
      cwd: root, env: { ...process.env, GELUMPE_JOBS: process.env.GELUMPE_JOBS || "4" }, timeout: 900_000, maxBuffer: 16 * 1024 * 1024,
    });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stdout.slice(-3000) + result.stderr.slice(-3000));
    const report = JSON.parse(result.stdout);
    assert.deepEqual(report.checks.filter(check => !check.ok), []);
    assert.ok(report.checks.length >= 25);
    // the walk cycle on the display RAM equals what the generator makes of the sprites, at the place and the row he is at
    const frames = loadFrames();
    const named = { "rechts-ruhig": "idle", "rechts-gehen": "walk", wende: "idle", "links-ruhig": "back0", "links-gehen": "back1" };
    assert.deepEqual(Object.keys(report.cycle).sort(), Object.keys(named).sort());
    for (const [key, name] of Object.entries(named)) {
      const shot = report.cycle[key];
      const want = new Display();
      frames[name].rows.forEach((row, y) => [...row].forEach((c, x) => { if (c === "#") want.pixel(frames[name].x + x + shot.posX, frames[name].y + y + shot.posY, 1); }));
      assert.equal(shot.hex, Buffer.from(want.bytes).toString("hex"), `${key} shows ${name} at ${shot.posX}, ${shot.posY}`);
    }
    assert.ok(report.ms.frame < 5, `${report.ms.frame} ms for the slowest frame`);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
