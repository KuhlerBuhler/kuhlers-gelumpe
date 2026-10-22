import { test } from "node:test";
import assert from "node:assert/strict";
import { DeviceSession } from "../src/session.mjs";
import { Terminal, compile } from "../src/terminal.mjs";
import { isPassed, describeUnits } from "../src/rehearsal.mjs";
import { Sender } from "../src/sender.mjs";
import { sha256, identify } from "../src/firmware.mjs";
import { plan, allowedRegions, allowedExecutes } from "../src/plan.mjs";
import { executeCheck } from "../src/gate.mjs";
import { execute, withChannel, describeMessage, search } from "../src/protocol.mjs";
import { BLOCKS } from "../src/map/index.mjs";
import { ramToFile } from "../src/map/address.mjs";
import EXEC from "../data/exec.mjs";
import { makeFirmware, simPort } from "./helpers.mjs";

const DISPLAY = BLOCKS.get("display").meta.ram;
const TIMEOUTS = { search: 200, read: 200, ack: 200, pattern: 400, global: 200, quiet: 5 };
const SEARCH = Array.from(search());
const MOV_R0_1_BX_LR = "[0xE3A00001, 0xE12FFF1E]";
const isSearch = f => f.length === SEARCH.length && f.every((b, i) => b === SEARCH[i]);
const retarget = (frame, channel) => frame.map((b, i) => (i === 2 ? 0x30 + channel : b));

/**
 * An emulator on channel 9 and a device on channel 3, both serving the same
 * firmware, a session on each, and the terminal over both. Nothing here
 * touches hardware.
 */
async function rig({ deviceKnown, deviceVersion, deviceFirmware, emuExecute, devExecute, emuTamper, devTamper, original = 0xaa } = {}) {
  const bytes = await makeFirmware();
  const sha = await sha256(new Uint8Array(16));
  const known = [{ version: [2, 2], label: "simulation", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: sha }] }];
  const emu = await simPort({ bytes, channel: 9, name: "Emulator", emulator: true, execute: emuExecute ?? (() => true), tamper: emuTamper });
  const dev = await simPort({ bytes, channel: 3, name: "Electribe", execute: devExecute ?? (() => true), tamper: devTamper, version: deviceVersion });
  dev.sim.work.find(w => w.start === EXEC.stubAt).bytes.fill(original);       // what the device holds there, not what the emulator holds
  const emuSession = new DeviceSession({ port: emu.port, known, timeouts: TIMEOUTS });
  emuSession.execSettleMs = 0;
  await emuSession.connect();
  const devSession = new DeviceSession({ port: dev.port, known: deviceKnown ?? known, timeouts: TIMEOUTS });
  devSession.execSettleMs = 0;
  await devSession.connect();
  if (deviceFirmware) devSession.useFirmware(deviceFirmware, await identify(deviceFirmware), { units: null, profile: null });
  const emulator = { port: emu.port, baseFirmware: bytes, button: async () => {} };
  const terminal = new Terminal({ device: { get session() { return devSession; } }, emulator, probe: async () => emuSession, timing: { settleMs: 0, codeSettleMs: 0 } });
  return { bytes, emu, dev, emuSession, devSession, terminal, emulator, mark: () => ({ emu: emu.sent.length, dev: dev.sent.length }) };
}

const frames = (sent, from) => sent.slice(from).filter(f => !isSearch(f));

test("the terminal knows its target: the emulator, always, or a device through the emulator while forwarding is on", async () => {
  const r = await rig();
  assert.equal(r.terminal.mode, "device");
  const emulatorOnly = new Terminal({ device: { session: r.emuSession }, emulator: r.emulator, probe: async () => r.emuSession });
  assert.equal(emulatorOnly.mode, "emulator");
  assert.equal(new Terminal({ device: { session: null }, emulator: r.emulator, probe: async () => r.emuSession }).mode, "emulator", "nothing to connect: the emulator is the target");
  let on = false;
  const switched = new Terminal({ device: { session: r.devSession }, emulator: r.emulator, probe: async () => r.emuSession, forward: () => on });
  assert.equal(switched.mode, "emulator", "a connected device gets nothing while the switch is off");
  on = true;
  assert.equal(switched.mode, "device");
});

test("without a session of its own the terminal runs a script in the emulator through the shared probe", async () => {
  const r = await rig();
  const t = new Terminal({ device: { session: null }, emulator: r.emulator, probe: async () => r.emuSession });
  assert.equal(await t.runDirect("1 + 1"), 2);
  const off = new Terminal({ device: { session: null }, emulator: { ...r.emulator, port: { running: false } }, probe: async () => r.emuSession });
  await assert.rejects(off.runDirect("1"), /Tippe „start“/);
});

test("a rehearsal records the frames the emulator received, in order, and seals the record", async () => {
  const r = await rig();
  const m = r.mark();
  const code = "KORG.screen.set((x, y) => y === 0)";
  const record = await r.terminal.rehearse(code);
  assert.equal(record.ok, true, record.reason);
  assert.equal(record.sendable, true);
  assert.equal(isPassed(record), true);
  const got = frames(r.emu.sent, m.emu);
  assert.deepEqual(record.units[0].steps.map(s => Array.from(s.msg)), got, "exactly what the emulator was sent");
  assert.equal(record.units[0].steps.at(-1).role, "verify");
  assert.deepEqual(Array.from(r.emu.sim.peek(DISPLAY, 128)), Array(128).fill(1), "the emulator holds the picture");
  assert.deepEqual(frames(r.dev.sent, m.dev), [], "the device saw nothing of it");
  assert.ok(describeUnits(record)[0].steps.length > 2);
});

test("replay sends the same frames to the device, only the channel byte differs, and the device ends up with the picture", async () => {
  const r = await rig();
  const code = "KORG.screen.set((x, y) => y === 0)";
  const record = await r.terminal.rehearse(code);
  const m = r.mark();
  const res = await r.terminal.send(record, code);
  assert.equal(res.ok, true, res.error?.message);
  const sent = frames(r.dev.sent, m.dev);
  assert.deepEqual(sent, record.units[0].steps.map(s => retarget(Array.from(s.msg), 3)));
  assert.deepEqual(Array.from(r.dev.sim.peek(DISPLAY, 128)), Array(128).fill(1));
  assert.deepEqual(r.dev.sim.faults, []);
  assert.deepEqual(r.devSession.history, [], "a picture is not an edit to undo");
});

test("a record cannot be sent twice, and a record that was never rehearsed is refused by the session itself", async () => {
  const r = await rig();
  const code = "KORG.screen.set((x, y) => y === 0)";
  const record = await r.terminal.rehearse(code);
  assert.equal((await r.terminal.send(record, code)).ok, true);
  const m = r.mark();
  const again = await r.terminal.send(record, code);
  assert.equal(again.refused, true);
  assert.match(again.error.message, /schon gesendet/);
  const forged = { code, ok: true, sendable: true, target: record.target, units: record.units.map(u => ({ ...u })) };
  const res = await r.devSession.replay(forged);
  assert.equal(res.refused, true);
  assert.equal(res.error.kind, "not-rehearsed");
  assert.deepEqual(frames(r.dev.sent, m.dev), [], "nothing went out");
});

test("a record whose frames were touched after the pass is no longer a pass", async () => {
  const r = await rig();
  const code = "KORG.screen.set((x, y) => y === 0)";
  const record = await r.terminal.rehearse(code);
  record.units[0].steps[1].msg[12] ^= 0x01;
  assert.equal(isPassed(record), false);
  const m = r.mark();
  const res = await r.terminal.send(record, code);
  assert.equal(res.refused, true);
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
});

test("changing the script invalidates the rehearsal", async () => {
  const r = await rig();
  const code = "KORG.screen.set((x, y) => y === 0)";
  const record = await r.terminal.rehearse(code);
  assert.equal(r.terminal.canSend(record, code).ok, true);
  const edited = `${code} `;
  assert.equal(r.terminal.canSend(record, edited).ok, false);
  const m = r.mark();
  const res = await r.terminal.send(record, edited);
  assert.equal(res.refused, true);
  assert.match(res.error.message, /geändert/);
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
});

test("a failing run in the emulator sends nothing: a script error, a gate refusal, a unit that failed and was caught", async () => {
  let tamperOn = false;
  const r = await rig({ emuTamper: reply => (tamperOn && reply.length > 1000 ? reply.map((b, i) => (i === 20 ? b ^ 1 : b)) : null) });
  const m = r.mark();
  const thrown = await r.terminal.rehearse("await KORG.screen.set((x, y) => true); throw new Error('kaputt')");
  assert.equal(thrown.ok, false);
  assert.match(thrown.reason, /gescheitert/);
  // the emulator's read-back comes back wrong, and the script swallows the error
  tamperOn = true;
  const caught = await r.terminal.rehearse("try { await KORG.screen.set((x, y) => true); } catch {} return 1");
  assert.equal(caught.ok, false);
  assert.match(caught.reason, /nicht bestanden/);
  tamperOn = false;
  const refused = await r.terminal.rehearse(`KORG.exec(${MOV_R0_1_BX_LR}, { at: 0xC0200000 })`);
  assert.equal(refused.ok, false);
  assert.match(refused.reason, /Bereich|region|Gerätekarte/i);
  for (const rec of [thrown, caught, refused]) {
    assert.equal(rec.sendable, false);
    const res = await r.terminal.send(rec, rec.code);
    assert.equal(res.refused, true);
  }
  assert.deepEqual(frames(r.dev.sent, m.dev), [], "the device was never spoken to");
});

test("a firmware that stops, restarts or goes silent after code ran fails the rehearsal", async () => {
  for (const [name, hook, text] of [
    ["stops", (a, sim, port) => { port.running = false; }, /stehen geblieben/],
    ["restarts", (a, sim, port) => { port.generation++; }, /neu gestartet/],
    ["goes silent", (a, sim) => { if (a === EXEC.stubAt) sim.faults.push({ code: "hang", message: "x" }); }, /Keine Antwort|antwortet/],
  ]) {
    const r = await rig({ emuExecute: hook });
    const m = r.mark();
    const record = await r.terminal.rehearse(`KORG.exec(${MOV_R0_1_BX_LR})`);
    assert.equal(record.ok, false, name);
    assert.match(record.reason, text, name);
    assert.equal((await r.terminal.send(record, record.code)).refused, true, name);
    assert.deepEqual(frames(r.dev.sent, m.dev), [], name);
  }
});

test("a stub that does not return r0 = 1 gets no acknowledgement and does not pass", async () => {
  const r = await rig({ emuExecute: addr => (addr === EXEC.stubAt ? false : true) });
  const record = await r.terminal.rehearse(`KORG.exec(${MOV_R0_1_BX_LR})`);
  assert.equal(record.ok, false);
  assert.match(record.reason, /Keine Antwort/);
  assert.equal(record.units[0].cleanup?.ok, true, "the bytes under the stub went back anyway");
  assert.deepEqual(Array.from(r.emu.sim.peek(EXEC.stubAt, 8)), Array(8).fill(0));
});

test("code runs as one unit: guard, backup, write, read-back, cache, run, restore; on the device with the device's own original bytes", async () => {
  const emuRan = [];
  const devRan = [];
  const r = await rig({
    emuExecute: (a, sim) => { emuRan.push([a, Array.from(sim.peek(EXEC.stubAt, 8))]); return true; },
    devExecute: (a, sim) => { devRan.push([a, Array.from(sim.peek(EXEC.stubAt, 8))]); return true; },
  });
  const code = `KORG.exec(${MOV_R0_1_BX_LR})`;
  const record = await r.terminal.rehearse(code);
  assert.equal(record.ok, true, record.reason);
  const unit = record.units[0];
  assert.deepEqual(unit.steps.map(s => s.role), ["guard", "backup", "write", "write", "verify", "execute", "execute"]);
  assert.equal(unit.cleanup.ok, true);
  const wantCode = [0x01, 0x00, 0xa0, 0xe3, 0x1e, 0xff, 0x2f, 0xe1];
  assert.deepEqual(emuRan, [[EXEC.icache.addr, wantCode], [EXEC.stubAt, wantCode]], "cache first, then the stub; the stub stood in the buffer both times");
  assert.deepEqual(Array.from(r.emu.sim.peek(EXEC.stubAt, 8)), Array(8).fill(0), "the emulator's stub buffer is as it was");

  const m = r.mark();
  const res = await r.terminal.send(record, code);
  assert.equal(res.ok, true, res.error?.message);
  assert.deepEqual(devRan.map(x => x[0]), [EXEC.icache.addr, EXEC.stubAt]);
  assert.deepEqual(devRan[1][1], wantCode, "the stub stood in the device's buffer when it ran");
  assert.deepEqual(Array.from(r.dev.sim.peek(EXEC.stubAt, 8)), Array(8).fill(0xaa), "the device's own bytes are back, not the emulator's zeros");
  const sent = frames(r.dev.sent, m.dev);
  const wanted = unit.steps.map(s => retarget(Array.from(s.msg), 3));
  assert.deepEqual(sent.slice(0, wanted.length), wanted, "the recorded frames, in order");
  const restore = sent.slice(wanted.length);
  assert.deepEqual(restore.map(f => describeMessage(f).kind), unit.cleanup.steps.map(s => describeMessage(s.msg).kind));
  assert.deepEqual(restore.map(f => describeMessage(f).addr), unit.cleanup.steps.map(s => describeMessage(s.msg).addr));
});

test("the device's firmware code is checked before anything is written: a differing routine stops the run at once", async () => {
  const r = await rig();
  const code = `KORG.exec(${MOV_R0_1_BX_LR})`;
  const record = await r.terminal.rehearse(code);
  assert.equal(record.ok, true, record.reason);
  // the device's cache routine is not what the firmware file holds
  r.dev.sim.image.bytes[ramToFile(EXEC.icache.addr)] ^= 0xff;
  const m = r.mark();
  const res = await r.terminal.send(record, code);
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "mismatch", "the dry run against the device's twin cannot see it, the guard read can");
  assert.equal(res.step, 1);
  assert.equal(res.pending ?? null, null, "nothing was written, so nothing is held");
  assert.equal(r.devSession.blocked, null);
  assert.ok(frames(r.dev.sent, m.dev).every(f => describeMessage(f).kind !== "write-address" && describeMessage(f).kind !== "execute"));
});

test("a reply that is not right stops the replay on the spot and the rest of the script is not sent", async () => {
  let reads = 0;
  const r = await rig({ devTamper: reply => (reply.length > 1000 && ++reads === 1 ? reply.map((b, i) => (i === 20 ? b ^ 1 : b)) : null) });
  const code = "await KORG.screen.set((x, y) => y === 0); await KORG.screen.set((x, y) => y === 1)";
  const record = await r.terminal.rehearse(code);
  assert.equal(record.units.length, 2);
  const m = r.mark();
  const res = await r.terminal.send(record, code);
  assert.equal(res.ok, false);
  assert.equal(res.unit, 0);
  assert.equal(res.error.kind, "mismatch");
  assert.equal(frames(r.dev.sent, m.dev).length, record.units[0].steps.length, "the second unit never went out");
  assert.ok(r.devSession.blocked, "the device is held until the user decides, like after any failed send");
});

test("the replay refuses a device whose firmware is not the one the rehearsal ran on", async () => {
  const code = "KORG.screen.set((x, y) => y === 0)";
  // 1. a device the version table does not know
  let r = await rig({ deviceKnown: [] });
  let record = await r.terminal.rehearse(code);
  let m = r.mark();
  let res = await r.terminal.send(record, code);
  assert.equal(res.refused, true);
  assert.match(res.error.message, /nicht bestätigt/);
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
  // 2. a device that reports another version
  const sha = await sha256(new Uint8Array(16));
  const both = [{ version: [2, 2], fingerprints: [{ addr: 0xc0000040, length: 16, sha256: sha }] }, { version: [2, 3], fingerprints: [{ addr: 0xc0000040, length: 16, sha256: sha }] }];
  r = await rig({ deviceKnown: both, deviceVersion: [2, 3] });
  record = await r.terminal.rehearse(code);
  m = r.mark();
  res = await r.terminal.send(record, code);
  assert.equal(res.refused, true);
  assert.match(res.error.message, /2\.3/);
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
  // 3. the device session has another firmware file loaded
  const other = await makeFirmware();
  other[0x1000] ^= 0xff;
  r = await rig({ deviceFirmware: other });
  record = await r.terminal.rehearse(code);
  m = r.mark();
  res = await r.terminal.send(record, code);
  assert.equal(res.refused, true);
  assert.match(res.error.message, /andere Firmware-Datei/);
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
});

test("a script that only reads, or presses keys, can be tried but not sent", async () => {
  const r = await rig();
  const reads = await r.terminal.rehearse("KORG.ram.read(0xC0000040, 4)");
  assert.equal(reads.ok, true);
  assert.equal(reads.sendable, false);
  assert.match(reads.whyNot, /nur gelesen/);
  const press = await r.terminal.rehearse("await KORG.screen.set((x, y) => y === 0); await KORG.press('menu')");
  assert.equal(press.ok, true, press.reason);
  assert.equal(press.sendable, false);
  assert.match(press.whyNot, /Tastendrücke/);
  const m = r.mark();
  assert.equal((await r.terminal.send(press, press.code)).refused, true);
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
});

test("RAM search runs in the terminal, prints its progress while it runs, and counts as a read that cannot be sent", async () => {
  const r = await rig();
  const meta = BLOCKS.get("sampleMeta").meta.table.ram;
  const code = `const a = await KORG.ram.snapshot({ from: ${meta}, to: ${meta + 0x2000}, chunk: 0x400 }); return KORG.ram.search(0, { snapshot: a, width: 1, maxMatches: 3 })`;
  const lines = [];
  const m = r.mark();
  const record = await r.terminal.rehearse(code, { print: t => lines.push(t) });
  assert.equal(record.ok, true, record.reason);
  assert.equal(record.sendable, false);
  assert.match(record.whyNot, /nur gelesen/);
  assert.match(lines[0], /^Lese /);
  assert.match(record.value.summary(), /^Suche nach 1 Byte \(00\)/);
  assert.ok(frames(r.emu.sent, m.emu).every(f => describeMessage(f).kind === "read-ram"), "only reads reached the emulator");
  assert.deepEqual(frames(r.dev.sent, m.dev), [], "the device saw nothing");
  const direct = new Terminal({ device: { session: r.emuSession }, emulator: r.emulator, probe: async () => r.emuSession });
  const out = [];
  await direct.runDirect(`KORG.ram.snapshot({ from: ${meta}, to: ${meta + 0x1000} })`, { print: t => out.push(t) });
  assert.match(out[0], /^Lese /);
});

test("code can be run directly only where it was tried first: not on a device session, and not outside the stub buffer", async () => {
  const r = await rig();
  const code = Uint8Array.from([1, 0, 0xa0, 0xe3, 0x1e, 0xff, 0x2f, 0xe1]);
  for (const s of [r.devSession, r.emuSession]) s.useFirmware(r.bytes, await identify(r.bytes), { units: null, profile: null });
  const m = r.mark();
  const onDevice = await r.devSession.apply({ kind: "exec", code, at: EXEC.stubAt, guards: [], invalidate: false }, { confirmed: true });
  assert.equal(onDevice.ok, false);
  assert.equal(onDevice.gate.reasons[0].code, "exec-needs-emulator");
  assert.deepEqual(frames(r.dev.sent, m.dev), []);
  const outside = await r.emuSession.apply({ kind: "exec", code, at: 0xc0200000, guards: [], invalidate: false }, { confirmed: true });
  assert.equal(outside.ok, false);
  assert.ok(outside.gate.reasons.some(x => x.code === "region"));
  assert.deepEqual(frames(r.emu.sent, m.emu), []);
});

test("the gate only lets code run in the stub buffer or at the cache routine, and only after read-back", () => {
  const ok = plan({ kind: "exec", code: Uint8Array.of(1, 0, 0xa0, 0xe3), guards: [], invalidate: true }, { channel: 0 });
  assert.deepEqual(executeCheck(ok), []);
  const elsewhere = [{ msg: execute(0, 0xc0200000), role: "execute", expect: { kind: "ack" } }];
  assert.equal(executeCheck(elsewhere)[0].code, "execute-region");
  const unverified = plan({ kind: "exec", code: Uint8Array.of(1, 0, 0xa0, 0xe3), invalidate: false }, { channel: 0 }).filter(s => s.role !== "verify");
  assert.equal(executeCheck(unverified)[0].code, "execute-unverified");
  assert.ok(allowedRegions().some(r => r.what === "stub buffer" && r.start === EXEC.stubAt));
  assert.ok(allowedExecutes().every(e => e.start === EXEC.stubAt || e.start === EXEC.icache.addr));
  assert.throws(() => plan({ kind: "exec", code: Uint8Array.of(1, 2, 3) }, { channel: 0 }), RangeError);
  assert.throws(() => plan({ kind: "exec", code: Uint8Array.of(1, 2, 3, 4), at: EXEC.stubAt + 2 }, { channel: 0 }), RangeError);
});

test("protocol: execute carries the address and a zero word, and a frame can be re-addressed to another channel", () => {
  const frame = execute(9, 0xc1000000);
  assert.deepEqual(describeMessage(frame), { kind: "execute", channel: 9, addr: 0xc1000000, length: 0 });
  const moved = withChannel(frame, 2);
  assert.deepEqual(moved.slice(0, 2).concat(moved.slice(3)), frame.slice(0, 2).concat(frame.slice(3)).map((b, i) => b));
  assert.equal(moved[2], 0x32);
  assert.deepEqual(withChannel(search(), 5), Array.from(search()), "the device search has no channel");
  assert.throws(() => withChannel([0xf0, 0x41, 0x30, 0xf7], 1));
});

test("the sender's check hook can stop a run after a step that answered", async () => {
  const sent = [];
  const sender = new Sender({ send: m => { sent.push(m); queueMicrotask(() => sender.receive(Uint8Array.from([0xf0, 0x42, 0x50, 0x01, 0x00, 0x00, 0x24, 0x01, 0x00, 0x00, 0x02, 0x02, 0x00, 0x00, 0xf7]))); }, timeouts: { search: 100 } });
  const steps = plan({ kind: "search" }).concat(plan({ kind: "search" }));
  const run = await sender.run(steps, { check: (step, value, i) => (i === 0 ? "stop" : null) });
  assert.equal(run.ok, false);
  assert.equal(run.error.kind, "replay-mismatch");
  assert.equal(sent.length, 1);
});

test("compile returns an expression and runs anything else as statements", async () => {
  assert.equal(await compile("1 + 1")({}), 2);
  assert.equal(await compile("const a = 3; return a")({}), 3);
});

test("only a step that is an execute may call itself one, and an execute under another name is left to the dry run that refuses it", async () => {
  const r = await rig();
  const { admit } = await import("../src/gate.mjs");
  const mislabelled = [{ msg: plan({ kind: "readRam", addr: EXEC.stubAt, length: 4 }, { channel: 9 })[0].msg, role: "execute", expect: { kind: "ack" } }];
  assert.equal(executeCheck(mislabelled)[0].code, "execute-label");
  const query = [{ msg: execute(9, EXEC.stubAt), role: "query", expect: { kind: "ack" } }];
  assert.deepEqual(executeCheck(query), [], "not this check's business");
  const ctx = { ...r.emuSession.context(), firmware: { known: true, reasons: [] } };
  const verdict = await admit({ kind: "readRam" }, query, ctx);
  assert.equal(verdict.verdict, "blocked");
  assert.equal(verdict.reasons[0].code, "execute", "the twin never runs code, so the dry run refuses it");
});

test("the emulator probe is one session per port, takes the port back, and meets a restarted firmware again", async () => {
  const { sharedProbe } = await import("../site/app/probe.mjs");
  const emu = await simPort({ bytes: await makeFirmware(), channel: 9, name: "Emulator", emulator: true });
  const get = sharedProbe(() => emu.port);
  emu.port.running = false;
  await assert.rejects(get(), /läuft nicht/);
  emu.port.running = true;
  // this image is not one the real version table knows, but the probe still connects and answers the search
  const first = await get();
  assert.equal(first.port, emu.port);
  assert.equal(await get(), first, "the same session for the effect editor and the terminal");
  const other = new DeviceSession({ port: emu.port, known: [], timeouts: TIMEOUTS });
  assert.equal(first.listening, false, "another session on the port took the handler");
  assert.equal(await get(), first);
  assert.equal(first.listening, true, "and the probe took it back");
  other.lost();
  emu.port.generation++;
  const connects = emu.sent.length;
  assert.equal(await get(), first, "the session stays, the editor holds it");
  assert.ok(emu.sent.length > connects, "but it met the firmware again");
  const carry = first.carry;
  first.lost();
  emu.port.generation++;
  const reconnected = await get();
  assert.notEqual(reconnected, first, "a disconnected sender is replaced");
  assert.equal(reconnected.carry, carry, "the port keeps its history and pending state");
  assert.equal(reconnected.sender.disconnected, false);
});
