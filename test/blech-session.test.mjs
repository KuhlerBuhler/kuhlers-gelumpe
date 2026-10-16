import { test } from "node:test";
import assert from "node:assert/strict";
import { DeviceSession, BLECH_WRITE } from "../src/session.mjs";
import { sha256 } from "../src/firmware.mjs";
import { BLECH, head, crc32 } from "../src/protocol.mjs";
import { syxEnc, u32le } from "../src/bytes.mjs";
import { BLOCKS } from "../src/map/index.mjs";
import { readUnits } from "../src/node.mjs";
import { simPort, makeStockLikeFirmware, makeFirmwareWithArrays, makeRecord } from "./helpers.mjs";
import { VsbImage } from "../src/image.mjs";
import { buildProfile, STOCK_SLOTS } from "../src/profile.mjs";
import { recordOf, pointersMatch, RECORD } from "../src/presets.mjs";
import { protectTable } from "../src/sysex-table.mjs";
import { tableEntry } from "../src/map/address.mjs";

// The session prefers BLECH's own SysEx commands when the device answers INFO, falls back to Hacktribe's 0x52 to 0x57, and else reads only
// (docs/messungen/2026-10-15-blech-sysex.md). Every device here is the simulation of src/device.mjs.
const units = readUnits();
const FAST = { search: 200, read: 200, ack: 200, pattern: 400, global: 200, info: 100 };
const bytes = new Uint8Array(0x200100);
const ZERO = await sha256(new Uint8Array(16));
const FIVES = await sha256(new Uint8Array(16).fill(0x55));
// Hacktribe's signature matches the zeroed image, Korg's does not; the second profile is the other way round.
const KNOWN = [
  { version: [2, 2], fingerprints: [{ addr: 0xc0000040, length: 16, sha256: ZERO }] },
  { version: [2, 2], build: "stock", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: FIVES }] },
];
const DISPLAY = BLOCKS.get("display").meta.ram;

const func = msg => msg[6];
const connect = async (options = {}) => {
  const img = options.stock ? Uint8Array.from(bytes).fill(0x55, 0xc0000040 - 0xc0000000 + 0x100, 0xc0000040 - 0xc0000000 + 0x110) : bytes;
  const rig = await simPort({ bytes: img, ...options });
  const session = new DeviceSession({ port: rig.port, known: KNOWN, timeouts: FAST });
  await session.connect();
  return { ...rig, session };
};

/** A device reply made from words, as the firmware builds it. */
const reply = (channel, fn, ...values) => [0xf0, ...head(channel), fn, ...syxEnc(values.flatMap(u32le)), 0xf7];

test("a device that answers INFO is used through BLECH's commands, with the build told by its signatures", async () => {
  const { session, sent } = await connect({ blech: true });
  const d = session.device;
  assert.equal(d.ram, "blech");
  assert.deepEqual([d.blech.version, d.blech.maxBlock, d.blech.tableMatches], [1, 0x8000, true]);
  assert.equal(d.hacktribe, true, "Hacktribe's code is there too");
  assert.equal(d.build, "hacktribe");
  assert.equal(d.versionKnown, true);
  assert.equal(sent.filter(m => func(m) === BLECH.INFO).length, 1);
  assert.ok(sent.filter(m => func(m) === BLECH.READ).length >= 1, "the signatures were read with BLECH's READ");
  assert.equal(sent.filter(m => func(m) === 0x52).length, 0, "and not with Hacktribe's");
});

test("a device that does not answer INFO but Hacktribe's read is used the old way", async () => {
  const { session, sent } = await connect();
  assert.deepEqual([session.device.ram, session.device.blech, session.device.hacktribe, session.device.build], ["hacktribe", null, true, "hacktribe"]);
  assert.ok(sent.some(m => func(m) === 0x52));
});

test("a device that answers neither is read-only", async () => {
  const { session } = await connect({ hacktribe: false });
  assert.deepEqual([session.device.ram, session.device.hacktribe, session.device.versionKnown], [null, false, false]);
  const checked = await session.check({ kind: "screenWrite", bytes: new Uint8Array(1024) });
  assert.equal(checked.verdict, "blocked");
  assert.ok(checked.reasons.some(r => r.code === "no-hacktribe"));
});

test("Korg's original with BLECH: known by its own signatures, RAM through BLECH, edits only where no Hacktribe table is needed", async () => {
  const { session } = await connect({ stock: true, hacktribe: false, blech: true });
  const d = session.device;
  assert.deepEqual([d.ram, d.build, d.hacktribe, d.versionKnown], ["blech", "stock", false, true]);
  session.useFirmware(bytes, { known: false, build: "stock", reasons: ["Original"] }, { units, profile: null });
  const screen = await session.check({ kind: "screenWrite", bytes: new Uint8Array(1024) });
  assert.ok(!screen.reasons.some(r => r.code === "unknown-firmware" || r.code === "no-hacktribe"), JSON.stringify(screen.reasons));
  const fx = await session.check({ kind: "fxRecord", table: "ifx", slot: 50, bytes: new Uint8Array(0x20c) });
  assert.ok(fx.reasons.some(r => r.code === "unknown-firmware"), "an effect record needs Hacktribe's tables");
  const exec = await session.check({ kind: "exec", code: Uint8Array.of(0, 0, 0xa0, 0xe1), guards: [] });
  assert.ok(exec.reasons.some(r => r.code === "exec-needs-hacktribe"), "BLECH has no execute command");
});

test("a write goes as one BLECH block and a read comes back checked, in blocks of the device's size", async () => {
  const { session, sent } = await connect({ stock: true, hacktribe: false, blech: true });
  session.useFirmware(bytes, { known: false, build: "stock", reasons: [] }, { units, profile: null });
  const picture = Uint8Array.from({ length: 1024 }, (_, i) => (i * 7) & 0xff);
  sent.length = 0;
  const res = await session.apply({ kind: "screenWrite", bytes: picture }, { confirmed: true });
  assert.equal(res.ok, true, res.error?.message ?? JSON.stringify(res.gate?.reasons));
  assert.deepEqual(sent.map(func), [BLECH.BEGIN, BLECH.DATA, BLECH.READ], "one pair for 1024 bytes and one read-back, not 4 + 4 messages");
  const back = await session.readRamBlock(DISPLAY, 1024);
  assert.deepEqual(Uint8Array.from(back), picture);
  assert.ok(BLECH_WRITE <= 0x8000);
});

test("a block that is bigger than the device takes goes in several, each with its own CRC", async () => {
  const { session, sent } = await connect({ blech: 0x400 });
  sent.length = 0;
  const data = await session.sender.blechRead(0xc0000100, 0x1000);
  assert.equal(data.length, 0x1000);
  assert.equal(sent.filter(m => func(m) === BLECH.READ).length, 4);
});

/** Once `armed.on` is set, the first `n` answers to a message of function `fn` are replaced by `make(reply)`; the rest pass. */
const armed = { on: false };
const spoil = (fn, n, make) => {
  let left = n;
  return (answer, message) => (armed.on && func(message) === fn && left-- > 0 ? make(answer, message) : undefined);
};
const spoiled = async (fn, n, make) => {
  armed.on = false;
  const rig = await connect({ blech: true, tamper: spoil(fn, n, make) });
  armed.on = true;
  rig.sent.length = 0;
  return rig;
};

test("a DATA answer that says bad CRC is retried, up to three attempts, then it fails loudly with nothing written", async () => {
  const badCrc = () => reply(9, BLECH.R_DATA, BLECH.STATUS.BAD_CRC, 0, 0, 0);
  const once = await spoiled(BLECH.DATA, 2, badCrc);
  const ok = await once.session.sender.blechWrite(DISPLAY, new Uint8Array(64).fill(7));
  assert.equal(ok.length, 8, "reported as the acknowledgement Hacktribe sends");
  assert.equal(once.sent.filter(m => func(m) === BLECH.BEGIN).length, 3, "two failures, the third attempt went through");

  const always = await spoiled(BLECH.DATA, 99, badCrc);
  await assert.rejects(always.session.sender.blechWrite(DISPLAY, new Uint8Array(64)), e => e.kind === "crc" && /3 Versuche/.test(e.message));
  assert.equal(always.sent.filter(m => func(m) === BLECH.BEGIN).length, 3);
});

test("a READ whose bytes do not fit their CRC is asked again, and fails loudly after three", async () => {
  const flip = answer => { const out = [...answer]; out[out.length - 3] ^= 0x01; return out; };
  const once = await spoiled(BLECH.READ, 1, flip);
  assert.equal((await once.session.sender.blechRead(0xc0000100, 64)).length, 64);
  assert.equal(once.sent.filter(m => func(m) === BLECH.READ).length, 2);

  const broken = await spoiled(BLECH.READ, 99, flip);
  await assert.rejects(broken.session.sender.blechRead(0xc0000100, 64), e => e.kind === "crc");
  assert.equal(broken.sent.filter(m => func(m) === BLECH.READ).length, 3);
});

test("the device's refusal is not retried and is named; a read-back that differs is not retried either", async () => {
  const { session, sent } = await connect({ blech: true });
  sent.length = 0;
  await assert.rejects(session.sender.blechWrite(0xc0100000, new Uint8Array(16)), e => e.kind === "protected" && /verweigert/.test(e.message));
  assert.deepEqual(sent.map(func), [BLECH.BEGIN], "refused at BEGIN, no byte sent");
  await assert.rejects(session.sender.blechRead(0xc7fffff0, 32), e => e.kind === "protected" && /außerhalb/.test(e.message));

  const differs = await spoiled(BLECH.DATA, 1, () => reply(9, BLECH.R_DATA, 0, DISPLAY, 8, 0xdeadbeef));
  await assert.rejects(differs.session.sender.blechWrite(DISPLAY, new Uint8Array(8)), e => e.kind === "verify");
  assert.equal(differs.sent.filter(m => func(m) === BLECH.BEGIN).length, 1);
});

test("silence is a timeout and is never repeated", async () => {
  const quiet = await connect({ blech: true });
  const realSend = quiet.port.out.send;
  quiet.port.out.send = data => { if (func(data) === BLECH.DATA) { quiet.sent.push(Array.from(data)); return; } realSend(data); };
  quiet.sent.length = 0;
  await assert.rejects(quiet.session.sender.blechWrite(DISPLAY, new Uint8Array(8)), e => e.kind === "timeout");
  assert.equal(quiet.sent.filter(m => func(m) === BLECH.DATA).length, 1, "the DATA message went out once");
});

test("a BLECH write leaves the RAM as written, read back through BLECH with the CRC the device computed", async () => {
  const { session } = await connect({ blech: true });
  const data = Uint8Array.from({ length: 1024 }, (_, i) => (i * 13 + 5) & 0xff);
  await session.sender.blechWrite(DISPLAY, data);
  assert.deepEqual(await session.sender.blechRead(DISPLAY, 1024), data);
  assert.equal(crc32(data) >>> 0, crc32(await session.sender.blechRead(DISPLAY, 1024)) >>> 0);
});

/** A device that runs Korg's build, whose records lie where the map says (test/helpers.mjs), and a session with the same file loaded. */
async function korgWithRecords() {
  const presets = [{ kind: "ifx", slot: 3, record: makeRecord("ifx", { name: "Korg Three", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } }) }];
  const file = await makeStockLikeFirmware(presets);
  const device = Uint8Array.from(file).fill(0x55, 0xc0000040 - 0xc0000000 + 0x100, 0xc0000040 - 0xc0000000 + 0x110);
  const rig = await simPort({ bytes: device, hacktribe: false, blech: true });
  const session = new DeviceSession({ port: rig.port, known: KNOWN, timeouts: FAST });
  await session.connect();
  const image = new VsbImage(file);
  session.useFirmware(file, { known: false, build: "stock", reasons: [] }, { units, profile: buildProfile(image, units, STOCK_SLOTS) });
  return { ...rig, session, file };
}

test("Korg's original with BLECH: the device's table is the one for its build, and its pointer arrays are the file's", async () => {
  const { session, file } = await korgWithRecords();
  assert.equal(session.device.blech.tableMatches, true);
  assert.notEqual(protectTable({ build: "stock" }).crc, protectTable({ build: "hacktribe" }).crc);
  assert.equal(await pointersMatch(file, (addr, length) => session.readRamBlock(addr, length)), true);
  const other = Uint8Array.from(file);
  new DataView(other.buffer).setUint32(0xc00adf94 - 0xc0000000 + 0x100 + 4, 0xc00a7f60, true);
  assert.equal(await pointersMatch(other, (addr, length) => session.readRamBlock(addr, length)), false, "an array that differs from the device's");
});

test("Korg's original with BLECH: an effect record is read and written at the address the pointer array gives, and taken back", async () => {
  const { session, sim, file } = await korgWithRecords();
  const { ram } = recordOf(file, "ifx", 3);
  assert.notEqual(ram, 0xc00a80f0 + 2 * RECORD, "not where Hacktribe's table would have it");
  const before = Uint8Array.from(await session.readRamBlock(ram, RECORD));
  assert.deepEqual(before, file.subarray(ram - 0xc0000000 + 0x100, ram - 0xc0000000 + 0x100 + RECORD));
  const after = Uint8Array.from(before);
  after[0x135 + 2] = 99;
  const edit = { kind: "fxRecord", table: "ifx", slot: 3, bytes: after, before, ram };
  const checked = await session.check(edit);
  assert.notEqual(checked.verdict, "blocked", JSON.stringify(checked.reasons));
  const res = await session.apply(edit, { confirmed: true });
  assert.equal(res.ok, true, res.error?.message ?? JSON.stringify(res.gate?.reasons));
  assert.deepEqual(Uint8Array.from(await session.readRamBlock(ram, RECORD)), after);
  assert.equal(sim.peek(ram + 0x135 + 2, 1)[0], 99);
  assert.equal(session.twin.peek(ram + 0x135 + 2, 1)[0], 99, "the twin follows");
  assert.equal((await session.undo()).ok, true);
  assert.deepEqual(Uint8Array.from(await session.readRamBlock(ram, RECORD)), before);
  assert.deepEqual(sim.faults, []);
});

test("Korg's original with BLECH: a record goes only where the file's pointer array puts that slot, and only in Korg's records", async () => {
  const { session, file } = await korgWithRecords();
  const record = Uint8Array.from(file.subarray(0x100, 0x100 + RECORD));
  const slot3 = recordOf(file, "ifx", 3).ram;
  const slot4 = recordOf(file, "ifx", 4).ram;
  const wrong = await session.check({ kind: "fxRecord", table: "ifx", slot: 3, bytes: record, ram: slot4 });
  assert.equal(wrong.verdict, "blocked");
  assert.ok(wrong.reasons.some(r => r.code === "record-address"), JSON.stringify(wrong.reasons));
  const hacktribe = await session.check({ kind: "fxRecord", table: "ifx", slot: 3, bytes: record });
  assert.equal(hacktribe.verdict, "blocked", "without an address the edit means Hacktribe's table");
  const pointer = await session.check({ kind: "fxRecord", table: "ifx", slot: 3, bytes: record, ram: 0xc00adf94 });
  assert.equal(pointer.verdict, "blocked", "the pointer array is no record");
  assert.ok(pointer.reasons.some(r => r.code === "record-address" || r.code === "region"));
  const ok = await session.check({ kind: "fxRecord", table: "ifx", slot: 3, bytes: record, ram: slot3 });
  assert.ok(!ok.reasons.some(r => r.code === "record-address" || r.code === "region" || r.code === "unknown-firmware"), JSON.stringify(ok.reasons));
});

test("Korg's original with BLECH: the device itself refuses the pointer array and a write across the edge of two records", async () => {
  const { session, file } = await korgWithRecords();
  await assert.rejects(session.sender.blechWrite(0xc00adf94, new Uint8Array(16)), e => e.kind === "protected", "the array of insert pointers");
  const first = 0xc00a7f60;
  await assert.rejects(session.sender.blechWrite(first + RECORD - 8, new Uint8Array(16)), e => e.kind === "protected", "across two records");
  await session.sender.blechWrite(first + 4, Uint8Array.from(file.subarray(first - 0xc0000000 + 0x104, first - 0xc0000000 + 0x108)));
});

test("Hacktribe with BLECH: its record goes through BLECH by the table of its build, which refuses Korg's records", async () => {
  const file = await makeFirmwareWithArrays([{ kind: "ifx", slot: 50, record: makeRecord("ifx", { name: "Hack Fifty", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } }) }]);
  const rig = await simPort({ bytes: file, blech: true });
  const session = new DeviceSession({ port: rig.port, known: KNOWN, timeouts: FAST });
  await session.connect();
  session.useFirmware(file, { known: true, reasons: [] }, { units, profile: null });
  assert.equal(session.device.build, "hacktribe");
  assert.equal(session.device.blech.tableMatches, true);
  const e = tableEntry("table.ifx", 49);
  const before = Uint8Array.from(file.subarray(e.file, e.file + e.size));
  const after = Uint8Array.from(before);
  after[0x135 + 2] = 99;
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after, before }, { confirmed: true });
  assert.equal(res.ok, true, res.error?.message ?? JSON.stringify(res.gate?.reasons));
  await assert.rejects(session.sender.blechWrite(0xc00a7f60 + 0x20c, new Uint8Array(0x20c)), e2 => e2.kind === "protected", "Korg's second record lies across two of Hacktribe's");
});
