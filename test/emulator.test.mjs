import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import * as P from "../src/protocol.mjs";
import { run as exec, slots } from "./support/spawn.mjs";

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const runner = fileURLToPath(new URL("../tools/emu/runner.py", import.meta.url));
const machine = fileURLToPath(new URL("../tools/emu/machine.py", import.meta.url));
const checker = fileURLToPath(new URL("../tools/emu/check.py", import.meta.url));
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const venv = fileURLToPath(new URL(process.platform === "win32"
  ? "../tools/emu/.venv/Scripts/python.exe"
  : "../tools/emu/.venv/bin/python", import.meta.url));
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;

// Under test:emu a missing VSB is a failure, not a pass with nothing run.
if (process.env.E2_EMU_REQUIRED === "1" && !vsb) test("E2_VSB is set", () => assert.fail("E2_VSB is not set"));

const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");

function emulate(path) {
  return exec(python(), [runner, "--vsb", path], { timeout: 60_000, maxBuffer: 1024 * 1024 });
}

async function boot(args) {
  const result = await exec(python(), [machine, "--vsb", vsb, ...args], { timeout: 180_000, maxBuffer: 1024 * 1024 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const report = JSON.parse(result.stdout);
  assert.equal(report.suite, "boot");
  assert.equal(report.hardware_contact, false);
  assert.deepEqual(report.asserts, []);
  // The firmware asked the panel for its version and for held buttons.
  assert.ok(report.panel_messages.includes("80") && report.panel_messages.includes("91"));
  assert.ok(report.frames >= 2, "the display was drawn more than once");
  return report;
}

describe("the firmware in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-08/heap-and-buffer", { skip }, async () => {
    const result = await emulate(vsb);
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.schema, 1);
    assert.equal(report.suite, "heap-and-buffer");
    assert.equal(report.unicorn, "2.1.4");
    assert.equal(report.hardware_contact, false);
    assert.deepEqual(report.stubs, []);
    assert.equal(report.firmware_sha256,
      createHash("sha256").update(readFileSync(vsb)).digest("hex"));
    assert.deepEqual(report.cases.map(c => [c.name, c.result, c.final_cursor]), [
      ["initialize", 0xC06A2940, 0xC06A2948],
      ["fill-exactly", 0xC06A2940, 0xC08A2940],
      ["reject-past-end", 0, 0xC08A2940],
      ["grow-from-base", 0xC06A2940, 0xC06A3940],
      ["negative-lower-bound-missing", 0xC06A2940, 0xC06A2938],
    ]);
    assert.deepEqual(report.buffer, { address: 0xC0D3A940, capacity: 0x01A00100 });
  });

  test("emulator rejects a short file and a same-size synthetic blank image", { skip }, async () => {
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-emu-"));
    const file = join(directory, "synthetic.VSB");
    try {
      writeFileSync(file, Buffer.alloc(0x100));
      const short = await emulate(file);
      assert.ifError(short.error);
      assert.equal(short.status, 1);
      assert.equal(short.stdout, "");
      assert.match(short.stderr, /VSB must contain/);
      writeFileSync(file, Buffer.alloc(0x200100));
      const blank = await emulate(file);
      assert.ifError(blank.error);
      assert.equal(blank.status, 1);
      assert.equal(blank.stdout, "");
      assert.match(blank.stderr, /Routine did not return|Invalid|Unexpected|unexpected/);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });

  test("emulate:2026-10-08/emulator-boot, without a flash dump it boots to the main screen with empty patterns", { skip }, async () => {
    const report = await boot(["--seconds", "8"]);
    assert.equal(report.flash, false);
    assert.ok(report.flash_commands.includes("02"), "the firmware stored the panel identity itself");
    assert.ok(report.screens <= 3, `splash, then the main screen, saw ${report.screens} changes`);
    assert.ok(report.display_lit > 1000, "the main screen is drawn");
  });

  test("emulate:2026-10-08/emulator-boot, with the own flash it reaches the main screen and stays there", {
    skip: skip || (!flash.length && "E2_FLASH not set"),
  }, async () => {
    const report = await boot(["--seconds", "10", "--flash", ...flash]);
    assert.equal(report.flash, true);
    assert.ok(report.interrupts.includes(21), "the system timer runs");
    assert.ok(report.leds_on.length > 0, "the panel LEDs were set");
    assert.ok(report.screens <= 3, `splash, then the main screen only, saw ${report.screens} changes`);
  });

  test("emulate:2026-10-08/emulator-boot, a held power line turns the device off", {
    skip: skip || (!flash.length && "E2_FLASH not set"),
  }, async () => {
    const report = await boot(["--seconds", "10", "--hold-power", "--flash", ...flash]);
    assert.equal(report.powered, false, "Power Off, then the firmware let go of the power hold");
  });

  test("emulate:2026-10-10/startphase, a start-mode mask leaves the main screen out, the kill switch key does not", { skip }, async () => {
    const plain = await boot(["--seconds", "4"]);
    const kill = await boot(["--seconds", "4", "--held", "0x2000"]);
    const all = await boot(["--seconds", "4", "--held", "0x18000000"]);
    assert.equal(kill.display_sha256, plain.display_sha256, "EXIT held at power-on starts normally");
    assert.notEqual(all.display_sha256, plain.display_sha256, "the [ALL] start mode shows its version page");
    assert.deepEqual(all.leds_on, [], "the start modes skip the application");
  });

  test("emulate:2026-10-10/startphase, the export check lets a start image through and stops a change in the start code", { skip }, async () => {
    const { applyPatches, splashPatch, splashToPixels } = await import("../src/patch.mjs");
    const { sha256 } = await import("../src/firmware.mjs");
    const original = new Uint8Array(readFileSync(vsb));
    const splash = 0xf9954;
    const inverted = splashToPixels(original.subarray(splash, splash + 1024)).map(p => p ^ 1);
    const panelCheck = 0x28a40;      // compare with panel version 0x96 (0xC0028940)
    const raw = { format: "gelumpe-patch", version: 1, id: "panel", changes: [{ file: panelCheck, bytes: "95", expect: await sha256(original.subarray(panelCheck, panelCheck + 1)) }] };
    const res = await applyPatches(original, [splashPatch(inverted), raw]);
    assert.equal(res.ok, true, res.reasons.join(" "));
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-check-"));
    try {
      const patched = join(directory, "SYSTEM.VSB");
      writeFileSync(patched, res.bytes);
      const allow = res.allow.flatMap(([at, n]) => ["--allow", `0x${at.toString(16)}:${n}`]);
      const check = await exec(python(), [checker, "--base", vsb, "--patched", patched, ...allow], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
      assert.equal(check.status, 1, check.stderr);
      const report = JSON.parse(check.stdout);
      const phase = report.checks.find(c => c.id === "start_phase");
      assert.deepEqual(phase.detail, { code: [["0x28a40", 1]], data: [] }, "the start image is allowed data, the compare is start code");
      assert.ok(report.checks.find(c => c.id === "boot:normal").ok);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });

  const at = (hex, seconds) => ["--send", `${hex}@${seconds}`];

  test("emulate:2026-10-08/panel-bedienung, MENU opens the menu and SEQUENCER lights its LED", { skip }, async () => {
    const main = await boot(["--seconds", "4"]);
    const menu = await boot(["--seconds", "4", ...at("0009010000", 3), ...at("0009000000", 3.15)]);
    assert.notEqual(menu.display_sha256, main.display_sha256, "the menu replaced the main screen");
    const back = await boot(["--seconds", "5", ...at("0009010000", 3), ...at("0009000000", 3.15), ...at("000d010000", 4), ...at("000d000000", 4.15)]);
    assert.equal(back.display_sha256, main.display_sha256, "EXIT leads back to the main screen");
    const seq = await boot(["--seconds", "4", ...at("0015010000", 3), ...at("0015000000", 3.15)]);
    assert.ok(seq.leds_on.includes(0x23) && !seq.leds_on.includes(0x22), "SEQUENCER lit, TRIGGER off");
  });

  test("emulate:2026-10-08/panel-bedienung, the main dial changes the pattern without stopping the firmware", { skip }, async () => {
    const report = await boot(["--seconds", "4", ...at("0100000100", 3), ...at("0100000100", 3.2), ...at("0100000100", 3.4)]);
    assert.deepEqual(report.asserts, []);
    assert.ok(report.leds_on.includes(0x00), "the ring of the main dial lit");
  });

  test("emulate:2026-10-08/panel-bedienung, the power switch turns the device off", { skip }, async () => {
    const report = await boot(["--seconds", "5", ...at("0601000000", 3), ...at("0600000000", 3.3)]);
    assert.equal(report.powered, false);
    assert.equal(report.display_lit, 0);
  });

  const hex = bytes => Buffer.from(bytes).toString("hex");
  const midiAt = (bytes, seconds) => ["--midi", `${hex(bytes)}@${seconds}`];

  test("emulate:2026-10-09/din-sysex, search, RAM read and RAM write answer over DIN as on the device", { skip }, async () => {
    const code = 0xC003EFE4;                         // the MFX menu length, an instruction word
    const scratch = 0xC1000000;                      // Hacktribe's upload area
    const data = Array.from({ length: 524 }, (_, i) => (i * 37 + 11) & 0xff);   // 524 % 7 == 6, the packing trap
    const report = await boot(["--seconds", "6",
      ...midiAt(P.search(), 3.0),
      ...midiAt(P.readRam(0, code, 4), 3.2),
      ...midiAt(P.writeRamAddress(0, scratch, data.length), 3.4),
      ...midiAt(P.writeRamData(0, data), 3.8),
      ...midiAt(P.readRam(0, scratch, data.length), 4.6)]);
    const replies = report.midi_out.map(x => Buffer.from(x, "hex"));
    assert.equal(replies.length, 5, report.midi_out.join(" "));
    const found = P.parseSearch(replies[0]);
    assert.equal(replies[0].length, 15, "the long search reply of the device");
    assert.deepEqual([found.sampler, found.version], [true, [2, 2]]);
    const image = readFileSync(vsb).subarray(0x100);
    assert.deepEqual(Array.from(P.parseReadRam(replies[1], found.channel, 4)), Array.from(image.subarray(code - 0xC0000000, code - 0xC0000000 + 4)));
    P.parseAck(replies[2], found.channel);
    P.parseAck(replies[3], found.channel);
    assert.deepEqual(Array.from(P.parseReadRam(replies[4], found.channel, data.length)), data);
  });

  test("emulate:2026-10-14/midi-boot, SysEx while the firmware starts is dropped: no assertion, a normal start, later SysEx is answered", { skip }, async () => {
    // Measured: SysEx at 40 ms of device time ended in the assertion at MidiHandler.cpp line 85. The main screen
    // comes at about 0.35 s. Nothing can send MIDI to a device that has not started, so the model drops it.
    const early = [0.04, 0.1, 0.2, 0.3];
    const report = await boot(["--seconds", "4", ...early.flatMap(t => midiAt(P.search(), t)), ...midiAt(P.search(), 3.0)]);
    assert.deepEqual(report.asserts, []);
    assert.equal(report.midi_dropped, early.length, "every message before the main screen was dropped");
    assert.ok(report.booted_ms > 0 && report.booted_ms < 1000, `main screen at ${report.booted_ms} ms`);
    assert.equal(report.midi_out.length, 1, "only the message after the start is answered");
    const clean = await boot(["--seconds", "4"]);
    assert.equal(report.display_sha256, clean.display_sha256, "the start ends in the same main screen as without any MIDI");
  });

  test("emulate:2026-10-09/din-sysex, a 16 KiB read comes back whole and without the send loop stalling the emulator", { skip }, async () => {
    const table = 0xC00B4F30;                        // the MFX table
    const started = Date.now();
    const report = await boot(["--seconds", "13", ...midiAt(P.readRam(0, table, 0x4000), 3.0)]);
    assert.equal(report.midi_out.length, 1);
    const image = readFileSync(vsb).subarray(0x100);
    assert.deepEqual(Array.from(P.parseReadRam(Buffer.from(report.midi_out[0], "hex"), 0, 0x4000)),
      Array.from(image.subarray(table - 0xC0000000, table - 0xC0000000 + 0x4000)));
    assert.ok(Date.now() - started < 60_000, "the full send loop took minutes before TX_FULL ended its slice");
  });

  test("emulate:2026-10-09/firmware-export, an exported VSB boots and shows its change", { skip }, async () => {
    const { exportVsb } = await import("../src/export.mjs");
    const { VsbImage } = await import("../src/image.mjs");
    const { readUnits } = await import("../src/node.mjs");
    readUnits();
    const original = new Uint8Array(readFileSync(vsb));
    const record = new VsbImage(original).read("mfx", 1).bytes;   // without a flash dump the pattern plays master 1
    const renamed = Uint8Array.from(record);
    renamed.set(Buffer.from("GELUMPE Delay\0\0"), 1);
    const res = await exportVsb(original, [{ edit: { kind: "fxRecord", table: "mfx", slot: 1, bytes: renamed } }]);
    assert.equal(res.ok, true, res.reasons?.join(" "));
    const directory = mkdtempSync(join(tmpdir(), "gelumpe-export-"));
    try {
      const exported = join(directory, "SYSTEM.VSB");
      writeFileSync(exported, res.bytes);
      // MENU, then Edit ► five times: the MFX TYPE page, which names the pattern's master effect.
      const keys = [...at("0009010000", 3), ...at("0009000000", 3.1)];
      for (let i = 0; i < 5; i++) keys.push(...at("000c010000", 3.4 + i * 0.4), ...at("000c000000", 3.5 + i * 0.4));
      const run = file => exec(python(), [machine, "--vsb", file, "--seconds", "6", ...keys], { timeout: 180_000 });
      const [a, b] = await Promise.all([run(vsb), run(exported)]);
      const before = JSON.parse(a.stdout);
      const after = JSON.parse(b.stdout);
      assert.deepEqual(after.asserts, []);
      assert.notEqual(after.display_sha256, before.display_sha256, "the master effect's new name is on the display");
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
