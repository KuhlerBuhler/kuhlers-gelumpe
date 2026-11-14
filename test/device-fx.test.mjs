import { test } from "node:test";
import assert from "node:assert/strict";
import { DeviceSession } from "../src/session.mjs";
import { readUnits } from "../src/node.mjs";
import { simPort, makeFirmwareWithArrays, makeRecord, asStock, putModTable } from "./helpers.mjs";
import { readDeviceEffects, deviceFxNames, FX_STATE } from "../src/device-fx.mjs";
import { collectionFor, buildCollection, parseCollection } from "../src/fx-collection.mjs";
import { locateModTable, readModType } from "../src/modtable.mjs";
import { modFromType } from "../src/fx-v2.mjs";
import { FX_FILE, SAMPLE_FILE } from "../src/device.mjs";
import { recordOf, nameAt, menuLength, RECORD } from "../src/presets.mjs";

// The export of e2sFx.all builds on what the connected device has in RAM, read over BLECH's READ, as it does on the
// user's SYSTEM.VSB: the same firmware gives the same file either way. Every device here is src/device.mjs's simulation.
const units = readUnits();
const FAST = { search: 200, read: 400, ack: 200, pattern: 400, global: 200, info: 100 };

async function firmware(build) {
  const presets = [
    { kind: "ifx", slot: 3, record: makeRecord("ifx", { name: "Drei", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } }) },
    { kind: "mfx", slot: 2, record: makeRecord("mfx", { name: "Zwei", devices: { mfx: 0x0a } }) },
  ];
  const bytes = await makeFirmwareWithArrays(presets, { patched: true });
  if (build !== "stock") return bytes;
  // Korg's build reads its own copy of the modulation types: the code words point there instead
  const stock = asStock(bytes);
  putModTable(stock, 0xd82ec);
  return stock;
}

async function connect(bytes, { card = null, state = null } = {}) {
  const device = Uint8Array.from(bytes);
  if (state) {
    const view = new DataView(device.buffer);
    view.setUint32(FX_STATE - 0xc0000000 + 0x100, state[0], true);
    view.setUint32(FX_STATE - 0xc0000000 + 0x104, state[1], true);
  }
  const rig = await simPort({ bytes: device, hacktribe: false, blech: true, card });
  const session = new DeviceSession({ port: rig.port, known: [], timeouts: FAST });
  await session.connect();
  return { ...rig, session };
}

const items = vsb => {
  const table = locateModTable(vsb);
  return [
    { kind: "ifx", slot: 5, from: 3 },
    { kind: "mfx", slot: 7, from: 2 },
    { kind: "mod", slot: 2, from: 1 },
    { kind: "mod", slot: 4, preset: { ...modFromType(readModType(vsb, table.file, 3)), name: "Karte Mod" } },
  ];
};

for (const build of ["hacktribe", "stock"]) {
  test(`${build}: e2sFx.all from the device's RAM is byte for byte the one from the same SYSTEM.VSB`, async () => {
    const vsb = await firmware(build);
    const { session } = await connect(vsb);
    const fx = await readDeviceEffects(session);
    assert.equal(fx.ok, true, fx.reason);
    assert.equal(fx.build, build);
    assert.deepEqual(fx.counts, { ifx: menuLength(vsb, "ifx").value, mfx: menuLength(vsb, "mfx").value }, "the menus the device has");
    const fromFile = collectionFor(build, vsb, items(vsb), units);
    const fromDevice = collectionFor(build, fx.image, items(vsb), units, { modTable: fx.modTable });
    assert.equal(fromDevice.ok, true, fromDevice.reason);
    assert.deepEqual(fromDevice.bytes, fromFile.bytes);
    assert.equal(deviceFxNames(fx, "ifx").get(3), "Drei");
    assert.equal(deviceFxNames(fx, "mfx").get(2), "Zwei");
    assert.equal(deviceFxNames(fx, "mod").get(1), "EG+ Filter");
  });
}

test("the device's own state counts: a record e2sFx.all put in and a menu the loader grew are what the page shows", async () => {
  const vsb = await firmware("hacktribe");
  const device = Uint8Array.from(vsb);
  const at = recordOf(device, "ifx", 40);
  device.set(makeRecord("ifx", { name: "Von der Karte", devices: { ifx1: 0x0a } }).bytes, at.file);
  // the master menu grown from 32 to 40 in RAM, as fx_grow does in every place of its length
  device[0x3f0e4] = 40;
  const { session } = await connect(device, { state: [2, 7] });
  const fx = await readDeviceEffects(session);
  assert.equal(fx.counts.mfx, 40);
  assert.equal(deviceFxNames(fx, "ifx").get(40), "Von der Karte");
  assert.equal(nameAt(fx.image, at.file), "Von der Karte");
  assert.deepEqual(fx.card, { status: "ok", loaded: 7 });
});

test("only reads go out, and the start state is left out where it says nothing", async () => {
  const { session, sent } = await connect(await firmware("hacktribe"));
  const before = sent.length;
  const fx = await readDeviceEffects(session);
  assert.equal(fx.card, null, "a firmware without the card loader leaves zeros there");
  assert.equal(fx.file, null, "no card, no FILE READ");
  const funcs = new Set(sent.slice(before).map(m => m[6]));
  assert.deepEqual([...funcs], [0x61], "BLECH READ only");
});

test("e2sFx.all comes along over FILE READ (bits 30 and 29) and parses against the device's menus", async () => {
  const vsb = await firmware("hacktribe");
  const file = buildCollection({ build: "hacktribe", entries: [{ kind: "ifx", index: 99, data: vsb.slice(recordOf(vsb, "ifx", 3).file, recordOf(vsb, "ifx", 3).file + RECORD), text: "x" }] });
  const { session, sent } = await connect(vsb, { card: new Map([[FX_FILE, file], [SAMPLE_FILE, new Uint8Array(4096)]]) });
  const before = sent.length;
  const fx = await readDeviceEffects(session);
  assert.equal(fx.file.present, true);
  assert.equal(fx.file.read.ok, true, fx.file.read.reason);
  assert.equal(fx.file.read.entries[0].index, 99);
  assert.deepEqual([...new Set(sent.slice(before).map(m => m[6]))].sort((a, b) => a - b), [0x61, 0x65], "READ and FILE READ, nothing that writes");
  const none = await connect(vsb, { card: new Map() });
  assert.deepEqual((await readDeviceEffects(none.session)).file, { present: false, read: null });
});

test("a firmware from before the read of e2sFx.all answers out of range; the page goes on without the file", async () => {
  const vsb = await firmware("hacktribe");
  const { session, sim } = await connect(vsb, { card: new Map([[FX_FILE, buildCollection({ build: "hacktribe", entries: [] })]]) });
  const handle = sim.handle.bind(sim);
  // the old rule: bits 30 and 29 together make the offset -1, which every range check refuses
  sim.handle = msg => (msg[6] === 0x65 ? sim.blechReply(0x6d, 3, 0, 0, 0, 0) : handle(msg));
  const fx = await readDeviceEffects(session);
  assert.equal(fx.ok, true);
  assert.equal(fx.file, null);
});
