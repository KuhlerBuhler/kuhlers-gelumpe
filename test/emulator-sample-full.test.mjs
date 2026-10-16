import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { ERROR } from "../data/script/contract.mjs";
import { asmInclude } from "../src/script/arm-tables.mjs";
import { applyPatches } from "../src/patch.mjs";
import { BLECH_SET_URL, loadBlechSet } from "../src/patcher.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { runtimePrograms } from "./fixtures/script-runtime-programs.mjs";
import { run } from "./support/spawn.mjs";

// Sample memory completely full (user slots 501 to 999, all 25 MiB of it): the firmware must not write into
// the RAM BLECH uses (docs/messungen/2026-10-14-sample-speicher-voll.md). The e2sSample.all is made here
// (tools/emu/sampleset.py, audio from a formula); no Korg data goes onto the card.
const root = fileURLToPath(new URL("../", import.meta.url));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const unicorn = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : unicorn.status !== 0 ? "Unicorn not installed" : false;

const block = (programs, name) => Uint8Array.from(Buffer.from(programs[name].blob, "hex"));
const shown = device => Buffer.from(device.shown).toString("hex");

/** What the browser model draws for the Klicker app once it is open, the same two displays script_cases.py compares. */
function request() {
  const programs = runtimePrograms();
  const klicker = new SimDevice();
  klicker.load(block(programs, "klicker"));
  klicker.frame();
  klicker.openApp(0);
  klicker.frame();
  const klickerReady = shown(klicker);
  klicker.post("buttonPress", 3);
  klicker.frame();
  return { include: asmInclude(), programs: { klicker: programs.klicker }, errors: ERROR, displays: { klickerReady, klickerOne: shown(klicker) } };
}

test("full sample memory: the firmware writes nothing into BLECH's RAM and the plugin still runs", { skip }, async () => {
  const set = await loadBlechSet(async url => JSON.parse(readFileSync(join(root, url), "utf8")), BLECH_SET_URL);
  const base = readFileSync(vsb);
  const patched = await applyPatches(new Uint8Array(base), set.patches);
  assert.equal(patched.ok, true, patched.reasons?.join(" "));
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-full-"));
  try {
    const out = join(dir, "BLECH.VSB");
    writeFileSync(out, patched.bytes);
    writeFileSync(join(dir, "request.json"), JSON.stringify(request()));
    const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
    const result = await run(python, ["tools/emu/sample_full.py", "--base", vsb, "--patched", out, "--scenario", "regression", "--request", join(dir, "request.json"), ...flash.length ? ["--flash", ...flash] : []], {
      cwd: root, env: { ...process.env, GELUMPE_JOBS: process.env.GELUMPE_JOBS || "4" }, timeout: 1_800_000, maxBuffer: 64 * 1024 * 1024,
    });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr.slice(-4000));
    const report = JSON.parse(result.stdout);
    assert.deepEqual(report.checks.filter(check => !check.ok), []);
    for (const id of ["laden-fertig", "alle-slots-belegt", "dsp-zeiger-am-limit", "samples-gehen-ueber-den-dsp-port", "klicker-bereit", "klicker-tap",
      "firmware-menue-bedienbar", "pattern-spielt-und-stoppt", "keine-fremden-schreibzugriffe", "blech-bytes-unveraendert"]) {
      assert.ok(report.checks.some(check => check.id === id && check.ok), id);
    }
    assert.equal(report.slots.active, 499, "all user slots 501 to 999 hold a sample");
    assert.equal(report.slots.cursor, 0x01C65EC0, "the DSP memory is full to its last byte");
    assert.equal(report.watch.foreign_count, 0, JSON.stringify(report.watch.foreign.slice(0, 5)));
    assert.equal(report.watch.alias_count, 0, "nothing wrote through the 64 MiB alias");
    assert.deepEqual(report.invariants.changed, []);
    assert.ok(report.watch.writes_total > 0, "the watch saw the firmware's writes into the image");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
