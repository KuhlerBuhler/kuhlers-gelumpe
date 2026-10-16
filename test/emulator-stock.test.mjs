import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import * as P from "../src/protocol.mjs";
import { run as exec, slots } from "./support/spawn.mjs";
import { emuPython, startEmulator } from "./support/emu.mjs";
import { applyPatches } from "../src/patch.mjs";

// Korg's own electribe sampler 2.02 (SYSTEM.VSB from Korg's system update) in the emulator. The emulator is
// built on Hacktribe's build; this file holds what has to be true for the original as well (docs/emulator.md,
// "Original-Firmware"). Needs the user's own file, E2_STOCK_VSB; skipped without it. The Hacktribe suites run on E2_VSB.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const stock = process.env.E2_STOCK_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !stock ? "E2_STOCK_VSB not set" : false;
const machine = fileURLToPath(new URL("../tools/emu/machine.py", import.meta.url));
const checker = fileURLToPath(new URL("../tools/emu/check.py", import.meta.url));

async function boot(args) {
  const result = await exec(emuPython(), [machine, "--vsb", stock, ...args], { timeout: 180_000, maxBuffer: 1024 * 1024 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.asserts, []);
  return report;
}

const at = (hex, seconds) => ["--send", `${hex}@${seconds}`];
const hex = bytes => Buffer.from(bytes).toString("hex");
const midiAt = (bytes, seconds) => ["--midi", `${hex(bytes)}@${seconds}`];

describe("Korg's original firmware in the emulator", { concurrency: slots, skip }, () => {
  test("it is told apart from Hacktribe's build and boots to the main screen", async () => {
    const report = await boot(["--seconds", "6"]);
    assert.equal(report.build, "stock");
    assert.ok(report.booted_ms > 0 && report.booted_ms < 2000, `main screen at ${report.booted_ms} ms`);
    assert.ok(report.panel_messages.includes("80") && report.panel_messages.includes("91"), "it asked the panel for its version and held keys");
    assert.ok(report.frames >= 2, "the display was drawn more than once");
    assert.ok(report.display_lit > 1000, "the main screen is drawn");
    assert.ok(report.flash_commands.includes("02"), "the firmware stored the panel identity itself");
    assert.ok(report.leds_on.length > 0, "the panel LEDs were set");
    assert.ok(report.interrupts.includes(21), "the system timer runs");
  });

  test("every way to start is as in Hacktribe's build: update offer, panel update, each start mode, the kill switch key, one DSP boot", async () => {
    const result = await exec(emuPython(), [checker, "--base", stock, "--patched", stock], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
    assert.ifError(result.error);
    const report = JSON.parse(result.stdout);
    const failed = report.checks.filter(c => !c.ok).map(c => `${c.id}: ${JSON.stringify(c.detail)}`);
    assert.deepEqual(failed, []);
    assert.equal(result.status, 0);
    for (const id of ["boot:normal", "update_offer", "panel_update", "kill_switch", "dsp_boot_once", "start_mode:00000400"]) {
      assert.ok(report.checks.some(c => c.id === id), `${id} was checked`);
    }
    assert.equal(report.checks.filter(c => c.id.startsWith("start_mode:")).length, 11, "all 11 start modes");
  });

  test("the panel works: MENU and EXIT, a key's LED, the main dial, the power switch", async () => {
    const main = await boot(["--seconds", "4"]);
    const menu = await boot(["--seconds", "4", ...at("0009010000", 3), ...at("0009000000", 3.15)]);
    assert.notEqual(menu.display_sha256, main.display_sha256, "the menu replaced the main screen");
    const back = await boot(["--seconds", "5", ...at("0009010000", 3), ...at("0009000000", 3.15), ...at("000d010000", 4), ...at("000d000000", 4.15)]);
    assert.equal(back.display_sha256, main.display_sha256, "EXIT leads back to the main screen");
    const seq = await boot(["--seconds", "4", ...at("0015010000", 3), ...at("0015000000", 3.15)]);
    assert.ok(seq.leds_on.includes(0x23) && !seq.leds_on.includes(0x22), "SEQUENCER lit, TRIGGER off");
    const dial = await boot(["--seconds", "4", ...at("0100000100", 3), ...at("0100000100", 3.2), ...at("0100000100", 3.4)]);
    assert.ok(dial.leds_on.includes(0x00), "the ring of the main dial lit");
    assert.notEqual(dial.display_sha256, main.display_sha256, "the dial changed the pattern shown");
    const off = await boot(["--seconds", "5", ...at("0601000000", 3), ...at("0600000000", 3.3)]);
    assert.equal(off.powered, false);
    assert.equal(off.display_lit, 0);
  });

  test("MIDI after the start: Korg's device search is answered, Hacktribe's RAM commands are not, and MIDI before the start is dropped", async () => {
    const early = [0.04, 0.2, 0.3];
    const report = await boot(["--seconds", "5", ...early.flatMap(t => midiAt(P.search(), t)),
      ...midiAt(P.search(), 3.0), ...midiAt(P.readRam(0, 0xC003EFE4, 4), 3.4), ...midiAt(P.writeRamAddress(0, 0xC1000000, 4), 3.8)]);
    assert.equal(report.midi_dropped, early.length, "every message before the main screen was dropped");
    assert.equal(report.midi_out.length, 1, `only the device search is answered: ${report.midi_out.join(" ")}`);
    const found = P.parseSearch(Buffer.from(report.midi_out[0], "hex"));
    assert.deepEqual([found.sampler, found.version], [true, [2, 2]]);
  });
});

describe("the emulator's own tools with Korg's original", { skip }, () => {
  test("firmware.py finds the same places and names the build", async () => {
    const result = await exec(emuPython(), [fileURLToPath(new URL("../tools/emu/firmware.py", import.meta.url)), stock], { timeout: 60_000 });
    assert.equal(result.status, 0, result.stderr);
    const profile = JSON.parse(result.stdout);
    assert.equal(profile.build, "stock");
    assert.deepEqual([profile.moved, profile.missing], [[], []]);
    assert.equal(profile.sites.flash_read, "0xc001e4ac");
    assert.equal(profile.values.screens, "0xc03404c0");
  });
});

describe("SOFTWARE UPDATE with Korg's original", { skip }, () => {
  const MENU = 0x09, EDIT_LEFT = 0x08, EDIT_RIGHT = 0x0c;

  /** Starts the original with a card, optionally with an update file put where the service puts it, and opens
   *  DATA UTILITY 14 (SOFTWARE UPDATE) and presses ENTER. Returns the sectors the firmware read and the folder. */
  async function enter(withUpdate, update = readFileSync(stock)) {
    const emu = await startEmulator(stock, {
      prepare: async ({ request }) => {
        await request("POST", "/firmware", readFileSync(stock));
        if (withUpdate) assert.equal((await request("POST", "/sd/system", update)).status, 200);
        else assert.equal((await request("POST", "/sd/insert", "{}")).status, 200);
      },
    });
    try {
      const press = async (index, hold = 150, gap = 400) => {
        await emu.input({ kind: "button", index, down: true });
        await emu.settle(hold);
        await emu.input({ kind: "button", index, down: false });
        await emu.settle(gap);
      };
      for (const b of [MENU, EDIT_LEFT, EDIT_LEFT, MENU]) await press(b);
      for (let i = 1; i < 14; i++) await press(EDIT_RIGHT, 120, 250);
      const before = (await emu.request("GET", "/sd")).body.stats.read;
      await press(MENU, 150, 1500);
      const sd = (await emu.request("GET", "/sd")).body;
      return { read: sd.stats.read - before, folder: sd.korg, file: existsSync(join(emu.cards, "card", "KORG", sd.korg, "System", "SYSTEM.VSB")) };
    } finally {
      await emu.stop();
    }
  }

  test("the update file is put in KORG/electribe sampler/System/ and the firmware reads its head from there", async () => {
    const [with_, without] = await Promise.all([enter(true), enter(false)]);
    assert.equal(with_.folder, "electribe sampler");
    assert.equal(with_.file, true, "the service put SYSTEM.VSB into the folder of the loaded firmware");
    assert.equal(without.file, false);
    assert.ok(with_.read > without.read, `ENTER read ${with_.read} sectors with the file, ${without.read} without`);
  });

  test("the fear button with Korg's original as the running firmware: BLECH made from it is found as the update", async () => {
    const set = JSON.parse(readFileSync(new URL("../data/patches/blech.json", import.meta.url), "utf8"));
    const patches = set.patches.map(p => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url), "utf8")));
    const built = await applyPatches(new Uint8Array(readFileSync(stock)), patches);
    assert.equal(built.ok, true, built.reasons.join(" "));
    const [with_, without] = await Promise.all([enter(true, Buffer.from(built.bytes)), enter(false)]);
    assert.equal(with_.folder, "electribe sampler", "the running firmware is still Korg's");
    assert.equal(with_.file, true, "BLECH is put where Korg's firmware looks for its update");
    assert.ok(with_.read > without.read, `ENTER read ${with_.read} sectors with BLECH as the update, ${without.read} without`);
  });
});
