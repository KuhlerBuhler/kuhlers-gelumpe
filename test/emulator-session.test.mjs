import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { DeviceSession } from "../src/session.mjs";
import { identify } from "../src/firmware.mjs";
import { VsbImage } from "../src/image.mjs";
import { buildProfile } from "../src/profile.mjs";
import { readUnits } from "../src/node.mjs";
import { tableEntry } from "../src/map/address.mjs";
import { field, writeRaw } from "../src/map/index.mjs";
import { plan } from "../src/plan.mjs";
import { TIMEOUTS } from "../src/sender.mjs";
import { startEmulator } from "./support/emu.mjs";

// DeviceSession, planner and gate against the user's firmware in the emulator,
// over the emulated DIN MIDI (plan 2026-10-08-emulator-im-editor, 3.2).
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;

let emu;
before(async () => { if (!skip) emu = await startEmulator(vsb); });
after(async () => { await emu?.stop(); });

// The service answers in device time, so on a loaded machine a reply can take longer than a real device's 3 s of wall time.
const PATIENT = Object.fromEntries(Object.entries(TIMEOUTS).map(([kind, ms]) => [kind, kind === "quiet" ? ms : ms * 10]));

async function session(opts = {}) {
  const s = new DeviceSession({ port: emu.port, timeouts: PATIENT, ...opts });
  const device = await s.connect();
  const bytes = new Uint8Array(readFileSync(vsb));
  const units = readUnits();
  s.useFirmware(bytes, await identify(bytes), { units, profile: buildProfile(new VsbImage(bytes), units) });
  return { s, device, bytes };
}

const mfxRecord = (bytes, slot) => {
  const e = tableEntry("table.mfx", slot - 1);
  return Uint8Array.from(bytes.subarray(e.file, e.file + e.size));
};

test("emulator session: the firmware is recognised by its RAM fingerprints", { skip }, async () => {
  const { device } = await session();
  assert.deepEqual([device.sampler, device.version, device.versionKnown, device.hacktribe], [true, [2, 2], true, true]);
});

test("emulator session: a gate warning waits for a yes, then the record is written, read back and undone", { skip }, async () => {
  const { s, bytes } = await session();
  const before = mfxRecord(bytes, 1);
  const changed = Uint8Array.from(before);
  changed[0x135 + 2] = (changed[0x135 + 2] + 1) & 0x7f;
  const edit = { kind: "fxRecord", table: "mfx", slot: 1, bytes: changed, before };
  const asked = await s.apply(edit);
  assert.equal(asked.needsConfirmation, true, JSON.stringify(asked.gate?.reasons));
  const done = await s.apply(edit, { confirmed: true });
  assert.equal(done.ok, true, done.error?.message);
  assert.equal((await s.undo()).ok, true);
});

test("emulator session: an unknown device version is only read", { skip }, async () => {
  const { s, bytes } = await session({ known: [] });
  const res = await s.apply({ kind: "fxRecord", table: "mfx", slot: 1, bytes: mfxRecord(bytes, 1) });
  assert.equal(res.ok, false);
  assert.equal(res.gate.reasons[0].code, "unknown-device");
});

const settle = ms => emu.settle(ms);               // device time: a key held for 150 wall ms can be 20 device ms on a loaded machine
async function press(index) {
  await emu.input({ kind: "button", index, down: true });
  await settle(150);
  await emu.input({ kind: "button", index, down: false });
  await settle(400);
}

test("emulator session: the screen read follows the menu to MFX TYPE and the IFX TYPE window", { skip }, async () => {
  const { s } = await session();
  assert.equal((await s.screen()).mode, 1, "main screen");
  await press(0x09);                               // MENU
  for (let i = 0; i < 5; i++) await press(0x0c);   // Edit ►
  const mfx = await s.screen();
  assert.deepEqual([mfx.mode, mfx.pageName, mfx.overlay, mfx.part], [3, "MFX TYPE", null, 0]);
  assert.equal(mfx.fx?.kind, "mfx");
  await press(0x0d);                               // EXIT
  await emu.input({ kind: "encoder", index: 4, delta: 1 });
  await settle(300);
  const ifx = await s.screen();
  assert.equal(ifx.mode, 1);
  assert.equal(ifx.overlay?.kind, 23, JSON.stringify(ifx));
  assert.equal(ifx.fx?.kind, "ifx");
});

test("emulator session: a master preset with a second unit is blocked and nothing reaches RAM", { skip }, async () => {
  const { s, bytes } = await session();
  const before = mfxRecord(bytes, 1);
  const bad = Uint8Array.from(before);
  writeRaw(bad, field("fx.stage.device"), [0], 0x0a);   // an insert unit in a master slot
  const res = await s.apply({ kind: "fxRecord", table: "mfx", slot: 1, bytes: bad, before }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.equal(res.gate?.verdict, "blocked", JSON.stringify(res.gate?.reasons));
  const e = tableEntry("table.mfx", 0);
  const read = await s.sender.run(plan({ kind: "readRam", addr: e.ram, length: e.size }, { channel: s.device.channel }));
  assert.deepEqual(Array.from(read.results[0].value), Array.from(before));
});

test("emulator session: as the rehearsal for a device, the firmware gets each edit first", { skip }, async () => {
  const { installWebMidiStub } = await import("../src/webmidi.mjs");
  const { electribePorts } = await import("../src/session.mjs");
  const bytes = new Uint8Array(readFileSync(vsb));
  const nav = {};
  const sim = installWebMidiStub({ image: { bytes }, channel: 9, latencyMs: 1, target: nav });
  const device = new DeviceSession({ port: electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0] });
  assert.equal((await device.connect()).versionKnown, true, "the simulation carries the same fingerprints");
  const { s: probe } = await session();
  emu.port.running = true;
  device.rehearseOn(probe);
  const units = readUnits();
  device.useFirmware(bytes, await identify(bytes), { units, profile: buildProfile(new VsbImage(bytes), units) });
  const before = mfxRecord(bytes, 1);
  const changed = Uint8Array.from(before);
  changed[0x135 + 2] = (changed[0x135 + 2] + 3) & 0x7f;
  const res = await device.apply({ kind: "fxRecord", table: "mfx", slot: 1, bytes: changed, before }, { confirmed: true });
  assert.equal(res.ok, true, res.error?.message);
  const e = tableEntry("table.mfx", 0);
  assert.deepEqual(Array.from(sim.device.peek(e.ram, e.size)), Array.from(changed));
  assert.equal(probe.history.length, 1, "the emulator ran it first");
  assert.equal((await device.undo()).ok, true);
  assert.equal(probe.history.length, 0, "and took it back with the device");
});

test("emulator session: the display read from RAM is the screen and follows the menu", { skip }, async () => {
  const { s } = await session();
  await press(0x0d);                               // EXIT to the main screen
  const lit = img => img.reduce((n, b) => n + b.toString(2).replace(/0/g, "").length, 0);
  const main = await s.readDisplay();
  assert.ok(lit(main) > 1000, "the main screen is drawn");
  await press(0x09);                               // MENU
  const menu = await s.readDisplay();
  assert.notDeepEqual(Array.from(menu), Array.from(main));
  await press(0x0d);
  assert.deepEqual(Array.from(await s.readDisplay()), Array.from(main), "back on the main screen");
});

test("emulator session: the LEDs read from RAM are the ones the firmware sent the panel, and follow the keys", { skip }, async () => {
  const { s } = await session();
  const onPanel = leds => Object.fromEntries(Object.entries(leds).filter(([i, v]) => v && Number(i) < 0x4c));
  // One read of the LED table takes about 250 ms of device time (measured), and a blinking LED (TAP, 0x14)
  // toggles inside that window, so the read cannot be held against the state at one instant. It has to be one of the
  // states the firmware sent the panel from the start of the read until a moment after its end (the panel message
  // follows the table write by a little). The wait is in device time, which load does not stretch.
  const agree = async () => {
    const mark = emu.ledMark();
    const read = await s.readLeds();
    await emu.settle(100);
    const states = emu.ledsSince(mark).map(onPanel);
    assert.ok(states.some(state => isDeepStrictEqual(read, state)),
      `the table read ${JSON.stringify(read)} is none of the states the panel was sent ${JSON.stringify(states)}`);
    return read;
  };
  await press(0x0d);                               // EXIT to the main screen
  const idle = await agree();
  assert.equal(idle[1], 255, "the OSC encoder LED is lit on the main screen");
  assert.equal(idle[0x09], undefined, "PLAY is dark");
  await press(0x02);                               // PLAY
  const playing = await agree();
  assert.equal(playing[0x09], 255, "PLAY is lit");
  assert.equal(playing[0x15], 255, "and its blue LED");
  await press(0x01);                               // STOP
  assert.equal((await agree())[0x09], undefined, "PLAY is dark again");
  assert.notEqual(s.ledAt, null, "the table address is kept for the next read");
});

test("terminal: code is rehearsed in the real emulator, and the recorded frames then go to a stand-in device", { skip }, async () => {
  const { Terminal } = await import("../src/terminal.mjs");
  const { simPort } = await import("./helpers.mjs");
  const { s } = await session();
  const bytes = new Uint8Array(readFileSync(vsb));
  // the service's port, dressed as the page's emulator port: it runs while the service says so
  Object.defineProperties(emu.port, { running: { get: () => emu.status.state === "running", configurable: true }, emulator: { value: true, configurable: true }, generation: { value: 0, configurable: true } });
  const dev = await simPort({ bytes, channel: 5, name: "Electribe", execute: () => true });
  const device = new DeviceSession({ port: dev.port, timeouts: { search: 500, read: 2000, ack: 2000 } });
  device.execSettleMs = 0;
  await device.connect();
  assert.equal(device.device.versionKnown, true, "the stand-in carries the fingerprints of the real build");
  const terminal = new Terminal({ device: { get session() { return device; } }, emulator: { port: emu.port, baseFirmware: bytes, button: async () => {} }, probe: async () => s });
  s.execSettleMs = 200;

  const code = "KORG.exec([0xE3A00001, 0xE12FFF1E])";
  const ran = await terminal.rehearse(code);
  assert.equal(ran.ok, true, ran.reason);
  assert.deepEqual(ran.units[0].steps.map(x => x.role), ["guard", "backup", "write", "write", "verify", "execute", "execute"]);
  assert.equal(ran.units[0].cleanup.ok, true);
  assert.equal(emu.status.state, "running", "the firmware is still running after the stub");
  assert.equal((await s.screen()).mode, 1, "and is on its main screen");

  device.useFirmware(bytes, await identify(bytes), { units: null, profile: null });
  const sent = await terminal.send(ran, code);
  assert.equal(sent.ok, true, sent.error?.message);
  assert.deepEqual(dev.sim.faults, []);
});

test("terminal: a stub that never returns hangs the real emulator's firmware, fails the rehearsal and sends nothing", { skip }, async () => {
  const { Terminal } = await import("../src/terminal.mjs");
  const { simPort } = await import("./helpers.mjs");
  const { s } = await session({ timeouts: TIMEOUTS });       // the silence of the hung firmware is what this test waits for
  const bytes = new Uint8Array(readFileSync(vsb));
  Object.defineProperties(emu.port, { running: { get: () => emu.status.state === "running", configurable: true }, emulator: { value: true, configurable: true }, generation: { value: 0, configurable: true } });
  const dev = await simPort({ bytes, channel: 5, name: "Electribe", execute: () => true });
  const device = new DeviceSession({ port: dev.port, timeouts: { search: 500, read: 2000, ack: 2000 } });
  await device.connect();
  device.useFirmware(bytes, await identify(bytes), { units: null, profile: null });
  const terminal = new Terminal({ device: { get session() { return device; } }, emulator: { port: emu.port, baseFirmware: bytes, button: async () => {} }, probe: async () => s });
  s.execSettleMs = 200;
  const code = "KORG.exec([0xEAFFFFFE])";               // b .
  const before = dev.sent.length;
  const record = await terminal.rehearse(code);
  assert.equal(record.ok, false);
  assert.match(record.reason, /Keine Antwort|stehen geblieben|antwortet/);
  const res = await terminal.send(record, code);
  assert.equal(res.refused, true);
  assert.equal(dev.sent.length, before, "the stand-in device was never spoken to");
});
