import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { run as exec, slots } from "./support/spawn.mjs";
import { emuPython } from "./support/emu.mjs";
import { buildOf, identify } from "../src/firmware.mjs";

// The blue Electribe 2 (the synth), SYSTEM.VSB from Korg's system update, in the emulator
// (docs/messungen/2026-10-15-blaue-electribe.md). Needs the user's own file, E2_BLUE_VSB; skipped without it.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const blue = process.env.E2_BLUE_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !blue ? "E2_BLUE_VSB not set" : false;
const machine = fileURLToPath(new URL("../tools/emu/machine.py", import.meta.url));

async function boot(args) {
  const result = await exec(emuPython(), [machine, "--vsb", blue, ...args], { timeout: 180_000, maxBuffer: 1024 * 1024 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.asserts, []);
  return report;
}

const at = (hex, seconds) => ["--send", `${hex}@${seconds}`];

describe("the blue Electribe 2 in the emulator", { concurrency: slots, skip }, () => {
  test("the page side tells it from the Sampler by its file head and says it is not the Sampler", async () => {
    const bytes = new Uint8Array(readFileSync(blue));
    assert.equal(buildOf(bytes), "synth");
    const id = await identify(bytes);
    assert.equal(id.build, "synth");
    assert.equal(id.known, false);
    assert.match(id.reasons[0], /blauen Electribe 2/);
  });

  test("firmware.py finds every place, moved from the Sampler's addresses, and names the build", async () => {
    const result = await exec(emuPython(), [fileURLToPath(new URL("../tools/emu/firmware.py", import.meta.url)), blue], { timeout: 60_000 });
    assert.equal(result.status, 0, result.stderr);
    const profile = JSON.parse(result.stdout);
    assert.equal(profile.build, "synth");
    assert.deepEqual([profile.moved, profile.missing], [[], []]);
    assert.notEqual(profile.sites.flash_read, "0xc001e4ac", "the places are not the Sampler's");
    assert.ok(Object.keys(profile.values).includes("screens"));
  });

  test("it boots to its main screen from an empty flash and draws the display", async () => {
    const report = await boot(["--seconds", "4"]);
    assert.equal(report.build, "synth");
    assert.ok(report.booted_ms > 0 && report.booted_ms < 2000, `main screen at ${report.booted_ms} ms`);
    assert.ok(report.display_lit > 1000, "the main screen is drawn");
    assert.ok(report.panel_messages.includes("80") && report.panel_messages.includes("91"), "it asked the panel for its version and held keys");
    assert.ok(report.leds_on.length > 0, "the panel LEDs were set");
    assert.ok(report.interrupts.includes(21), "the system timer runs");
    assert.equal(report.powered, true);
  });

  test("the panel works: MENU and EXIT, the main dial, the power switch", async () => {
    const main = await boot(["--seconds", "4"]);
    const menu = await boot(["--seconds", "4", ...at("0009010000", 3), ...at("0009000000", 3.15)]);
    assert.notEqual(menu.display_sha256, main.display_sha256, "the menu replaced the main screen");
    const back = await boot(["--seconds", "5", ...at("0009010000", 3), ...at("0009000000", 3.15), ...at("000d010000", 4), ...at("000d000000", 4.15)]);
    assert.equal(back.display_sha256, main.display_sha256, "EXIT leads back to the main screen");
    const dial = await boot(["--seconds", "4", ...at("0100000100", 3), ...at("0100000100", 3.2), ...at("0100000100", 3.4)]);
    assert.notEqual(dial.display_sha256, main.display_sha256, "the dial changed the display");
    const off = await boot(["--seconds", "5", ...at("0601000000", 3), ...at("0600000000", 3.3)]);
    assert.equal(off.powered, false);
    assert.equal(off.display_lit, 0);
  });
});
