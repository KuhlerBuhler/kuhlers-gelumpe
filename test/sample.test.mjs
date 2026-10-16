import { test } from "node:test";
import assert from "node:assert/strict";
import { BLOCKS, FIELDS, field, readRaw, typeOf, describe } from "../src/map/index.mjs";
import { ramEntry, fieldInRamEntry } from "../src/map/address.mjs";
import { plan, sampleWrites, allowedRegions } from "../src/plan.mjs";
import { regionCheck } from "../src/gate.mjs";
import { describeMessage, writeRamAddress } from "../src/protocol.mjs";
import { lintSample, TUNE_SEEN } from "../src/sample-rules.mjs";
import { readSample, readSampleNames, SAMPLE_COUNT } from "../src/samples.mjs";
import { DeviceSession, electribePorts } from "../src/session.mjs";
import { installWebMidiStub } from "../src/webmidi.mjs";
import { sha256 } from "../src/firmware.mjs";
import { readUnits } from "../src/node.mjs";
import { makeFirmware } from "./helpers.mjs";
import { putEntry } from "./support/samples.mjs";

const KNOWN = [{ version: [2, 2], label: "simulation", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: await sha256(new Uint8Array(16)) }] }];
const FAST = { search: 200, read: 200, ack: 200, pattern: 400, global: 200 };

// Addresses from the notes: Sample 653 (index 652) has its record at 0xC0480200 and its name at +12
// (2026-10-07-sample-name-ram), its metadata entry at 0xC041C7D8 and its tune at +21 (2026-10-07-sample-metadaten-ram).
test("the map puts sample 653 where the notes measured it", () => {
  assert.equal(ramEntry("sampleName", 652).ram, 0xc0480200);
  assert.equal(fieldInRamEntry(field("sample.name"), 652).ram, 0xc048020c);
  assert.equal(ramEntry("sampleMeta", 652).ram, 0xc041c7d8);
  assert.equal(fieldInRamEntry(field("sample.tune"), 652).ram, 0xc041c7ed);
  assert.equal(fieldInRamEntry(field("sample.name"), 0).ram, 0xc047b08c, "the first name, as the cache copy of the notes names it");
  assert.equal(ramEntry("samplePlayback", 5).ram, 0xc0362ee8 + 5 * 0x10);
  assert.throws(() => ramEntry("sampleName", SAMPLE_COUNT), /no entry/);
  assert.throws(() => ramEntry("sampleName", -1), /no entry/);
  assert.throws(() => ramEntry("pattern", 0), /not an entry of a RAM table/);
});

test("the tables end before the next one begins, so no entry reaches into a neighbour", () => {
  const end = name => { const t = BLOCKS.get(name).meta.table; return t.ram + t.count * t.stride; };
  assert.ok(end("samplePlayback") <= BLOCKS.get("sampleMeta").meta.table.ram);
  assert.ok(end("sampleMeta") <= BLOCKS.get("sampleName").meta.table.ram);
  for (const name of ["sampleName", "samplePlayback", "sampleMeta"]) {
    const block = BLOCKS.get(name);
    assert.equal(block.meta.table.stride, block.size, `${name}: an entry is the stride`);
  }
});

test("only the name and the tune can be edited; every other field of the tables is read only or unknown", () => {
  const sample = [...FIELDS.values()].filter(f => BLOCKS.get(f.block).meta.table);
  assert.ok(sample.length > 15);
  assert.deepEqual(sample.filter(f => !f.edit).map(f => f.id).sort(), ["sample.name", "sample.tune"]);
  for (const f of sample.filter(f => f.edit)) assert.ok(f.edit === "readonly" || f.source === "unknown", f.id);
  for (const f of sample.filter(f => f.source === "unknown")) assert.equal(f.edit, "expert", f.id);
});

test("the tune is a signed byte shown as the raw value, with no unit claimed", () => {
  const tune = field("sample.tune");
  assert.equal(typeOf(tune).name, "s8");
  assert.equal(describe(tune, -12).text, "-12");
  assert.equal(describe(tune, 0).text, "0");
  assert.equal(describe(tune, 5).unit, null);
});

test("a sample edit writes the name field and the tune byte and nothing else of the entry", () => {
  const steps = plan({ kind: "sample", index: 652, name: "Blech", tune: -12 }, { channel: 9 });
  assert.deepEqual(steps.map(s => s.role), ["backup", "backup", "write", "write", "write", "write", "verify", "verify"]);
  const writes = steps.filter(s => describeMessage(s.msg).kind === "write-address").map(s => describeMessage(s.msg));
  assert.deepEqual(writes.map(w => [w.addr, w.length]), [[0xc048020c, 16], [0xc041c7ed, 1]], "header 16 bytes and the one tune byte, as measured");
  const verify = steps.filter(s => s.role === "verify");
  assert.deepEqual(Array.from(verify[0].compare), [..."Blech"].map(c => c.charCodeAt(0)).concat(Array(11).fill(0)), "NUL padded");
  assert.deepEqual(Array.from(verify[1].compare), [0xf4], "-12 as the device holds it (0xF4)");
  assert.deepEqual(plan({ kind: "sample", index: 652, tune: 3 }, { channel: 9 }).map(s => s.role), ["backup", "write", "write", "verify"]);
});

test("a sample edit the fields cannot hold is refused before anything is planned", () => {
  const edit = patch => () => plan({ kind: "sample", index: 652, ...patch }, { channel: 9 });
  assert.throws(edit({ name: "Ümlaut" }), /display cannot show/);
  assert.throws(edit({ name: "x".repeat(17) }), /longer than 16/);
  assert.throws(edit({ tune: 128 }), /does not fit/);
  assert.throws(edit({ tune: -129 }), /does not fit/);
  assert.throws(edit({ tune: 1.5 }), /does not fit/);
  assert.throws(edit({}), /name or the tune/);
  assert.throws(edit({ index: 998, tune: 0 }), /no entry/);
  assert.throws(edit({ index: -1, tune: 0 }), /no entry/);
  assert.equal(sampleWrites({ index: 0, name: "x".repeat(16) }).length, 1, "16 characters fit the field");
});

test("the regions allow the name and the tune of every sample and no other byte of an entry", () => {
  const regions = allowedRegions();
  const w = (addr, length) => regionCheck([{ msg: writeRamAddress(9, addr, length), expect: { kind: "ack" }, role: "write" }], regions);
  assert.deepEqual(w(0xc048020c, 16), [], "the name of sample 653");
  assert.deepEqual(w(0xc041c7ed, 1), [], "the tune of sample 653");
  assert.deepEqual(w(fieldInRamEntry(field("sample.name"), 997).ram, 16), [], "the last sample");
  assert.equal(w(0xc0480200, 32)[0].code, "region", "the whole name entry");
  assert.equal(w(0xc048020c, 17)[0].code, "region", "the name and the category's first byte");
  assert.equal(w(0xc0480200 + 28, 2)[0].code, "region", "the category");
  assert.equal(w(0xc041c7d8 + 11, 1)[0].code, "region", "a byte of the metadata that is not the tune");
  assert.equal(w(0xc041c7d8 + 16, 4)[0].code, "region", "the sample rate");
  assert.equal(w(0xc0362ee8 + 652 * 16 + 14, 1)[0].code, "region", "the one-shot byte of the playback table");
  assert.equal(w(ramEntry("sampleMeta", 998 - 1).ram + 22, 1)[0].code, "region");
  assert.equal(w(ramEntry("sampleName", 997).ram + 32 + 12, 16)[0].code, "region", "past the last sample");
});

test("the rules warn about what was never tried and are quiet about what was", () => {
  assert.deepEqual(TUNE_SEEN, [-16, 0]);
  assert.deepEqual(lintSample({ name: "Blech", tune: -12 }), []);
  assert.deepEqual(lintSample({ tune: -16 }), []);
  assert.deepEqual(lintSample({ tune: 0 }), []);
  const above = lintSample({ tune: 12 });
  assert.deepEqual(above.map(f => [f.severity, f.code]), [["warn", "sample-tune-unseen"]]);
  assert.match(above[0].message, /außerhalb der Werte, die am Gerät gesehen wurden \(-16 bis 0\)/);
  assert.match(above[0].message, /Skala ist nicht gemessen/);
  assert.equal(lintSample({ tune: -17 })[0].code, "sample-tune-unseen");
  assert.equal(lintSample({ name: "" })[0].code, "sample-name-empty");
  assert.equal(lintSample({ name: "A".repeat(16) })[0].code, "sample-name-full");
  assert.deepEqual(lintSample({ name: "A".repeat(15) }), []);
  assert.equal(lintSample({ tune: 0, before: { name: "Sample701", tune: 0, rate: 48000, pcmBytes: 0 } })[0].code, "sample-slot-empty", "a default name and a rate do not make a slot used");
  assert.deepEqual(lintSample({ tune: 0, before: { name: "No!!", tune: 0, rate: 48000, pcmBytes: 9600 } }), []);
  assert.deepEqual(lintSample({ tune: 0, before: { name: "", tune: 0, rate: 0, pcmBytes: 4000 } }), [], "an unnamed slot with audio is not unused");
});

const units = readUnits();

async function connected(seed = []) {
  const bytes = await makeFirmware();
  const nav = {};
  const sim = installWebMidiStub({ image: { bytes }, channel: 9, latencyMs: 1, target: nav });
  for (const entry of seed) putEntry(sim.device, entry);
  const port = electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0];
  const session = new DeviceSession({ port, known: KNOWN, timeouts: FAST });
  await session.connect();
  session.useFirmware(bytes, { known: true, reasons: [], original: false }, { units, profile: null });
  return { session, sim };
}

const BLECH = { index: 652, name: "Blech", tune: 0, rate: 48000, pcmBytes: 9600, stereo: 0, category: 3, importNumber: 17, oneShot: 1, loop: 100, end: 200, start: 4 };

test("the list and one entry are read back the way they were put into the tables", async () => {
  const { session, sim } = await connected([BLECH, { index: 654, name: "No!!", tune: -16, rate: 44100 }]);
  const names = await session.readSampleNames();
  assert.equal(names.length, SAMPLE_COUNT);
  assert.deepEqual([names[652], names[654], names[0]], ["Blech", "No!!", ""]);
  const one = await session.readSample(652);
  assert.deepEqual(one, { index: 652, name: "Blech", category: 3, importNumber: 17, start: 4, loop: 100, end: 200, oneShot: 1, pcmBytes: 9600, stereo: 0, rate: 48000, tune: 0 });
  assert.equal((await session.readSample(654)).tune, -16);
  assert.deepEqual(sim.faults, []);
  await assert.rejects(() => session.readSample(998), /no entry/);
});

test("the name table is read in blocks that stay inside it", async () => {
  const { sim } = await connected();
  const asked = [];
  await readSampleNames(async (addr, length) => { asked.push([addr, length]); return sim.device.peek(addr, length); });
  const t = BLOCKS.get("sampleName").meta.table;
  assert.equal(asked[0][0], t.ram);
  assert.equal(asked.reduce((n, [, length]) => n + length, 0), t.count * t.stride);
  assert.ok(asked.every(([addr, length]) => addr >= t.ram && addr + length <= t.ram + t.count * t.stride));
  assert.equal((await readSample(async (a, n) => sim.device.peek(a, n), 3)).name, "");
});

test("live: a name and a tune go out with a yes where the rules warn, are read back, and one undo takes both back", async () => {
  const { session, sim } = await connected([BLECH]);
  const before = await session.readSample(652);
  const edit = { kind: "sample", index: 652, name: "Dose", tune: 7, before: { name: before.name, tune: before.tune, rate: before.rate, pcmBytes: before.pcmBytes } };
  const asked = await session.apply(edit);
  assert.equal(asked.needsConfirmation, true, "tune 7 was never seen on the device");
  assert.match(asked.gate.reasons.map(r => r.message).join(" "), /Tune 7/);
  assert.equal((await session.readSample(652)).name, "Blech", "and nothing went out");
  const done = await session.apply(edit, { confirmed: asked.gate.token });
  assert.equal(done.ok, true, JSON.stringify(done.gate?.reasons ?? done.error?.message));
  assert.deepEqual(await session.readSample(652), { ...before, name: "Dose", tune: 7 });
  assert.equal(session.twin.peek(fieldInRamEntry(field("sample.tune"), 652).ram, 1)[0], 7, "the twin follows what was confirmed");
  assert.equal(session.history.at(-1).edit.kind, "sample");
  assert.equal((await session.undo()).ok, true);
  assert.deepEqual(await session.readSample(652), before, "both bytes are back");
  assert.deepEqual(sim.faults, []);
});

test("live: a clean edit needs no yes, and only the name's bytes change", async () => {
  const { session, sim } = await connected([BLECH]);
  const entry = sim.device.peek(ramEntry("sampleName", 652).ram, 32);
  const meta = sim.device.peek(ramEntry("sampleMeta", 652).ram, 0x45c);
  const done = await session.apply({ kind: "sample", index: 652, name: "Blech 2", tune: -12, before: { name: "Blech", tune: 0, rate: 48000, pcmBytes: 9600 } });
  assert.equal(done.ok, true, JSON.stringify(done.gate?.reasons));
  const after = sim.device.peek(ramEntry("sampleName", 652).ram, 32);
  assert.deepEqual([...after.keys()].filter(i => after[i] !== entry[i]), [12 + 5, 12 + 6], "only the two new name bytes differ");
  const metaAfter = sim.device.peek(ramEntry("sampleMeta", 652).ram, 0x45c);
  assert.deepEqual([...metaAfter.keys()].filter(i => metaAfter[i] !== meta[i]), [21], "only the tune byte differs");
  assert.deepEqual(sim.faults, []);
});

test("live: a slot that looks empty asks first, and the read-only fields are never written", async () => {
  const { session, sim } = await connected();
  const edit = { kind: "sample", index: 900, name: "Neu", before: { name: "Sample901", tune: 0, rate: 48000, pcmBytes: 0 } };
  const asked = await session.apply(edit);
  assert.equal(asked.needsConfirmation, true);
  assert.equal(asked.gate.reasons[0].code, "sample-slot-empty");
  assert.equal(sim.device.peek(fieldInRamEntry(field("sample.name"), 900).ram, 16).every(b => b === 0), true);
  const rate = readRaw(sim.device.peek(ramEntry("sampleMeta", 900).ram, 24), field("sample.rate"));
  assert.equal(rate, 0);
});

test("live: an unknown device is only read, and a sample edit does not get round that", async () => {
  const bytes = await makeFirmware();
  const nav = {};
  installWebMidiStub({ image: { bytes }, channel: 9, latencyMs: 1, target: nav });
  const port = electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0];
  const session = new DeviceSession({ port, known: [], timeouts: FAST });
  await session.connect();
  session.useFirmware(bytes, { known: true, reasons: [] }, { units });
  const res = await session.apply({ kind: "sample", index: 652, tune: 0 });
  assert.equal(res.ok, false);
  assert.equal(res.gate.reasons[0].code, "unknown-device");
});

test("live: a failed write is reported with the sample it hit and what the read-back found", async () => {
  const { session, sim } = await connected([BLECH]);
  const original = session.sender.send;
  let writes = 0;
  session.sender.send = msg => { if (describeMessage(msg).kind === "write-data" && ++writes === 2) return; original(msg); };
  const res = await session.apply({ kind: "sample", index: 652, name: "Dose", tune: 0, before: { name: "Blech", tune: 0, rate: 48000, pcmBytes: 9600 } });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "timeout");
  assert.match(session.blocked, /^Sample 653:/);
  assert.match(res.pending.now.text, /Gemisch|neue Stand|alte Stand/);
  assert.equal((await session.resolve("restore")).ok, true);
  assert.equal((await session.readSample(652)).name, "Blech");
  assert.deepEqual(sim.faults, []);
});
