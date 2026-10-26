import { test } from "node:test";
import assert from "node:assert/strict";
import { DeviceSession } from "../src/session.mjs";
import { SAMPLE_FILE, SAMPLE_TEMP } from "../src/device.mjs";
import { readDeviceSamples, writeDeviceChange, inspectTemp, finishTemp, discardTemp, needsCompaction } from "../src/usb-sample-file.mjs";
import { parseSampleFile, planChange, applyPlan, entryFromWav, HEADER } from "../src/sample-file.mjs";
import { simPort } from "./helpers.mjs";
import { wav, file } from "./support/sample-file.mjs";

// The sample file over USB (src/usb-sample-file.mjs) against the simulation of BLECH's sample file commands (src/device.mjs), which follows
// the firmware's (tools/patch/blech_sysex.py, checked in the emulator by sysex_cases.py sample_cases).
const FAST = { search: 200, read: 200, ack: 200, pattern: 400, global: 200, info: 100 };
const image = new Uint8Array(0x200100);

/** A card that notes what happens to the sample files, in order, and can damage a file as it is written. */
class Card extends Map {
  log = [];
  damage = null;
  set(key, value) {
    if (this.damage && key === this.damage.key && value.length >= this.damage.from) { value = Uint8Array.from(value); value[this.damage.at] ^= 1; this.damage = null; }
    this.log.push(["set", key, value.length]);
    return super.set(key, value);
  }
  delete(key) {
    this.log.push(["delete", key]);
    return super.delete(key);
  }
}

async function device(files = {}, options = {}) {
  const card = new Card();
  for (const [name, bytes] of Object.entries(files)) Map.prototype.set.call(card, name, bytes);
  const rig = await simPort({ bytes: image, blech: true, card, ...options });
  const session = new DeviceSession({ port: rig.port, known: [], timeouts: FAST });
  await session.connect();
  return { ...rig, card, session };
}

const names = parsed => parsed.samples.map(s => [s.slot, s.name]);

test("listing reads the header and a few bytes of each sample, not the audio", async () => {
  const old = file({ 500: "Kick", 501: "Snare", 900: "Hat" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  const { parsed, temp } = await readDeviceSamples(session);
  assert.deepEqual(names(parsed), names(parseSampleFile(old)));
  assert.deepEqual(parsed.samples.map(s => [s.offset, s.length, s.rate, s.bits]), parseSampleFile(old).samples.map(s => [s.offset, s.length, s.rate, s.bits]));
  assert.equal(temp, 0);
  assert.deepEqual(card.log, [], "nothing was written");
});

test("a card without a sample file lists nothing, and a first sample makes the file", async () => {
  const { session, card } = await device({});
  const { parsed } = await readDeviceSamples(session);
  assert.equal(parsed.samples.length, 0);
  const bytes = entryFromWav(wav({ frames: 70 }), 500, "First");
  const plan = planChange(parsed.header, parsed, { add: [{ slot: 500, bytes }] });
  assert.equal(needsCompaction(parsed, plan), false);
  await writeDeviceChange(session, parsed, plan);
  assert.deepEqual(names(parseSampleFile(card.get(SAMPLE_FILE))), [[500, "First"]]);
});

test("adding sends the new samples behind the old ones first and the header last, and what was there stays", async () => {
  const old = file({ 500: "Kick", 501: "Snare" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  const { parsed } = await readDeviceSamples(session);
  const bytes = entryFromWav(wav({ frames: 300 }), 700, "Hat");
  const plan = planChange(parsed.header, parsed, { add: [{ slot: 700, bytes }] });
  const seen = [];
  await writeDeviceChange(session, parsed, plan, p => seen.push(p.phase));
  const out = card.get(SAMPLE_FILE);
  assert.deepEqual(out, applyPlan(old, plan));
  assert.deepEqual(out.subarray(HEADER, old.length), old.subarray(HEADER), "the old samples are untouched");
  assert.deepEqual(card.log.map(([op, key, n]) => [op, key, n]).at(-1), ["set", SAMPLE_FILE, out.length], "the file ends the way it should");
  assert.equal(card.log.some(([, key]) => key === SAMPLE_TEMP), false, "no temp file for an add");
  assert.ok(seen.includes("Sende neue Samples") && seen.includes("Schreibe den Kopf"));
});

test("removing builds the new file beside the old one, checks it, then swaps; the temp file is gone at the end", async () => {
  const old = file({ 500: "A", 501: "B", 502: "C", 503: "D" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  const { parsed } = await readDeviceSamples(session);
  const plan = planChange(parsed.header, parsed, { remove: [501] });
  assert.equal(needsCompaction(parsed, plan), true);
  const seen = new Set();
  await writeDeviceChange(session, parsed, plan, p => seen.add(p.phase));
  assert.deepEqual(card.get(SAMPLE_FILE), applyPlan(old, plan));
  assert.equal(card.has(SAMPLE_TEMP), false);
  const ops = card.log.map(([op, key]) => `${op}:${key}`);
  const firstTemp = ops.indexOf(`set:${SAMPLE_TEMP}`);
  const deleteOld = ops.indexOf(`delete:${SAMPLE_FILE}`);
  assert.ok(firstTemp >= 0 && deleteOld > firstTemp, "the new file exists before the old one is deleted");
  assert.ok(ops.indexOf(`set:${SAMPLE_FILE}`) > deleteOld && ops.at(-1) === `delete:${SAMPLE_TEMP}`, "copied back, then the temp file goes");
  assert.deepEqual([...seen], ["Baue die neue Datei auf der Karte", "Prüfe die neue Datei", "Kopiere die neue Datei zurück"]);
});

test("removing the last sample and removing all shrink the file too", async () => {
  const old = file({ 500: "A", 501: "B" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  let { parsed } = await readDeviceSamples(session);
  await writeDeviceChange(session, parsed, planChange(parsed.header, parsed, { remove: [501] }));
  assert.deepEqual(names(parseSampleFile(card.get(SAMPLE_FILE))), [[500, "A"]]);
  ({ parsed } = await readDeviceSamples(session));
  await writeDeviceChange(session, parsed, planChange(parsed.header, parsed, { remove: [500] }));
  assert.equal(card.get(SAMPLE_FILE).length, HEADER);
  assert.equal(parseSampleFile(card.get(SAMPLE_FILE)).samples.length, 0);
});

test("remove and add in one change", async () => {
  const old = file({ 500: "A", 501: "B", 502: "C" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  const { parsed } = await readDeviceSamples(session);
  const bytes = entryFromWav(wav({ frames: 90 }), 500, "New");
  const plan = planChange(parsed.header, parsed, { remove: [500], add: [{ slot: 500, bytes }] });
  await writeDeviceChange(session, parsed, plan);
  assert.deepEqual(names(parseSampleFile(card.get(SAMPLE_FILE))), [[500, "New"], [501, "B"], [502, "C"]]);
});

test("a temp file that was damaged on the card is found by its CRC, the old file stays and the temp file goes", async () => {
  const old = file({ 500: "A", 501: "B", 502: "C" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  const { parsed } = await readDeviceSamples(session);
  card.damage = { key: SAMPLE_TEMP, from: HEADER + 100, at: HEADER + 40 };
  await assert.rejects(writeDeviceChange(session, parsed, planChange(parsed.header, parsed, { remove: [500] })), /Prüfsumme/);
  assert.deepEqual(card.get(SAMPLE_FILE), old, "the old file is as it was");
  assert.equal(card.has(SAMPLE_TEMP), false);
});

test("a copy back that was damaged leaves the finished temp file for finishing the swap", async () => {
  const old = file({ 500: "A", 501: "B", 502: "C" });
  const { session, card } = await device({ [SAMPLE_FILE]: old });
  const { parsed } = await readDeviceSamples(session);
  const plan = planChange(parsed.header, parsed, { remove: [500] });
  card.damage = null;
  // damage the file as it is copied back: the first write of the sample file after the old one is deleted
  const set = card.set.bind(card);
  let armed = false;
  card.delete = key => { if (key === SAMPLE_FILE) armed = true; return Map.prototype.delete.call(card, key); };
  card.set = (key, value) => (armed && key === SAMPLE_FILE ? set(key, Object.assign(Uint8Array.from(value), { [HEADER + 8]: value[HEADER + 8] ^ 1 })) : set(key, value));
  await assert.rejects(writeDeviceChange(session, parsed, plan), /Tauschdatei auf der Karte/);
  assert.equal(card.has(SAMPLE_TEMP), true, "the finished temp file is there");
  assert.equal(await inspectTemp(session), "finished");
  card.set = set;
  await finishTemp(session);
  assert.deepEqual(card.get(SAMPLE_FILE), applyPlan(old, plan));
  assert.equal(card.has(SAMPLE_TEMP), false);
});

test("a temp file with no sample file beside it is finished; a broken one is found and discarded", async () => {
  const done = file({ 500: "A", 502: "C" });
  const { session, card } = await device({ [SAMPLE_TEMP]: done });
  assert.equal((await readDeviceSamples(session)).temp, done.length, "listing says that a temp file lies there");
  assert.equal(await inspectTemp(session), "finished");
  await finishTemp(session);
  assert.deepEqual(card.get(SAMPLE_FILE), done);
  assert.equal(card.has(SAMPLE_TEMP), false);
  const broken = await device({ [SAMPLE_TEMP]: done.subarray(0, done.length - 50) });
  assert.equal(await inspectTemp(broken.session), "broken");
  await discardTemp(broken.session);
  assert.equal(broken.card.has(SAMPLE_TEMP), false);
  assert.equal(await inspectTemp(broken.session), "none");
});

test("a firmware without the sample file commands is told why", async () => {
  const old = await device({}, { card: null });
  await assert.rejects(readDeviceSamples(old.session), /zu alt für Updates über USB/);
});
