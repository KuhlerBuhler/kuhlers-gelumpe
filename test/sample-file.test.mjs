import { test } from "node:test";
import assert from "node:assert/strict";
import { parseRemote, parseSampleFile, planChange, applyPlan, entryFromWav, freeSlot, cleanSampleName, SampleFileError, HEADER, ESLI, wavChunks } from "../src/sample-file.mjs";
import { wav, file, put32 } from "./support/sample-file.mjs";

test("parses the slots, names and formats of a file", () => {
  const parsed = parseSampleFile(file({ 500: "Kick", 502: "Snare", 900: "Hat" }));
  assert.deepEqual(parsed.samples.map(s => [s.slot, s.name, s.rate, s.channels, s.bits, s.problem]), [[500, "Kick", 48000, 1, 16, null], [502, "Snare", 48000, 1, 16, null], [900, "Hat", 48000, 1, 16, null]]);
  assert.equal(parsed.samples[0].frames, 50 + 500 % 7);
});

test("a file without the header, or cut off, is reported and not parsed into nonsense", () => {
  assert.throws(() => parseSampleFile(new Uint8Array(100)), SampleFileError);
  assert.throws(() => parseSampleFile(new Uint8Array(HEADER)), /e2s sample all/);
  const cut = file({ 500: "Kick", 501: "Snare" });
  const parsed = parseSampleFile(cut.subarray(0, cut.length - 20));
  assert.equal(parsed.samples[1].problem, "Der Eintrag ist abgeschnitten.");
  assert.equal(parsed.samples[0].problem, null);
});

test("adding keeps what is there and appends the new entry; only the header and the new bytes are in the plan", () => {
  const old = file({ 500: "Kick", 501: "Snare" });
  const parsed = parseSampleFile(old);
  const bytes = entryFromWav(wav({ frames: 80 }), 700, "Hat");
  const plan = planChange(old, parsed, { add: [{ slot: 700, bytes }] });
  assert.deepEqual(plan.moves, []);
  assert.equal(plan.appends.length, 1);
  assert.equal(plan.appends[0].at, old.length);
  const next = parseSampleFile(applyPlan(old, plan));
  assert.deepEqual(next.samples.map(s => [s.slot, s.name]), [[500, "Kick"], [501, "Snare"], [700, "Hat"]]);
});

test("removing compacts: later entries move down in order, the file ends where the last one does, no gap is left", () => {
  const old = file({ 500: "A", 501: "B", 502: "C", 503: "D" });
  const parsed = parseSampleFile(old);
  const plan = planChange(old, parsed, { remove: [501] });
  assert.deepEqual(plan.moves.map(m => m.from > m.to), [true, true]);
  assert.deepEqual(plan.moves.map(m => m.from), [parsed.samples[2].offset, parsed.samples[3].offset], "ascending, so a straight copy never overwrites unread data");
  const out = applyPlan(old, plan);
  assert.equal(out.length, old.length - parsed.samples[1].length);
  const next = parseSampleFile(out);
  assert.deepEqual(next.samples.map(s => s.name), ["A", "C", "D"]);
  assert.ok(next.samples.every(s => s.problem === null));
  assert.equal(next.samples.at(-1).offset + next.samples.at(-1).length, out.length);
});

test("removing and adding in one change gives one plan with both", () => {
  const old = file({ 500: "A", 501: "B", 502: "C" });
  const plan = planChange(old, parseSampleFile(old), { remove: [500], add: [{ slot: 500, bytes: entryFromWav(wav(), 500, "New") }] });
  const next = parseSampleFile(applyPlan(old, plan));
  assert.deepEqual(next.samples.map(s => [s.slot, s.name]), [[500, "New"], [501, "B"], [502, "C"]]);
});

test("an occupied or a factory slot is refused", () => {
  const old = file({ 500: "A" });
  const bytes = entryFromWav(wav(), 500, "X");
  assert.throws(() => planChange(old, parseSampleFile(old), { add: [{ slot: 500, bytes }] }), /Platz 501 ist belegt/);
  assert.throws(() => planChange(old, parseSampleFile(old), { add: [{ slot: 10, bytes }] }), /501 bis 999/);
});

test("new stereo records reserve both channels and end on the final complete DSP frame", () => {
  for (const bits of [16, 24]) {
    const entry = entryFromWav(wav({ frames: 100, channels: 2, bits }), 612, "Stereo");
    const record = wavChunks(entry).korg.at + 8;
    const view = new DataView(entry.buffer);
    assert.equal(entry[record + 65], 1);
    assert.equal(view.getUint32(record + 60, true), 400);
    assert.equal(view.getUint32(record + 44, true), 396);
    assert.equal(view.getUint32(record + 48, true), 396);
  }
});

test("a WAV becomes an entry the loader takes: PCM 16 or 24 bit, 1 or 2 channels, the slot and the name in the record", () => {
  for (const o of [{ bits: 16 }, { bits: 24 }, { channels: 2 }, { rate: 44100 }, { list: true }]) {
    const entry = entryFromWav(wav(o), 612, "Dose");
    const parsed = parseSampleFile((() => { const f = file({}); const out = new Uint8Array(HEADER + entry.length); out.set(f.subarray(0, HEADER)); put32(out, 16 + 4 * 612, HEADER); out.set(entry, HEADER); return out; })());
    assert.deepEqual([parsed.samples[0].name, parsed.samples[0].bits, parsed.samples[0].channels, parsed.samples[0].rate], ["Dose", o.bits ?? 16, o.channels ?? 1, o.rate ?? 48000]);
  }
  assert.throws(() => entryFromWav(wav({ bits: 8 }), 600, "x"), /8 Bit geht nicht/);
  assert.throws(() => entryFromWav(wav({ bits: 32 }), 600, "x"), /32 Bit/);
  assert.throws(() => entryFromWav(wav({ tagNo: 3, bits: 32 }), 600, "x"), /kein PCM/);
  assert.throws(() => entryFromWav(wav({ channels: 3 }), 600, "x"), /3 Kanäle/);
  assert.throws(() => entryFromWav(new Uint8Array(40), 600, "x"), /keine WAV-Datei/);
});

test("an esli record the WAV brings is kept, only the slot and the name change", () => {
  const esli = new Uint8Array(ESLI); esli[52] = 0; esli[60] = 77; esli[100] = 9;
  const entry = entryFromWav(wav({ esli }), 650, "Mine");
  const at = entry.length - ESLI;
  assert.equal(entry[at + 100], 9);
  assert.equal(entry[at + 60], 77);
  assert.equal(entry[at + 52], 0);
  assert.equal(entry[at] | (entry[at + 1] << 8), 650);
  assert.equal(entry[at + 78] | (entry[at + 79] << 8), 650);
});

test("free slots and names", () => {
  assert.equal(freeSlot(new Set([500, 501])), 502);
  assert.equal(freeSlot(new Set(Array.from({ length: 499 }, (_, i) => 500 + i))), null);
  assert.equal(cleanSampleName("  Kick Drum Ünï mit sehr langem Namen "), "Kick Drum n mit");
});

test("a file read in pieces lists the same samples as the file in memory, from the header and a few bytes of each sample", async () => {
  const bytes = file({ 500: "Kick", 501: "Snare", 700: "Hat" });
  const asked = [];
  const read = async (at, n) => { asked.push(n); return bytes.slice(at, at + n); };
  const remote = await parseRemote(read, bytes.length);
  const local = parseSampleFile(bytes);
  assert.deepEqual(remote.samples.map(s => [s.slot, s.offset, s.length, s.name, s.rate, s.channels, s.bits, s.frames, s.problem]), local.samples.map(s => [s.slot, s.offset, s.length, s.name, s.rate, s.channels, s.bits, s.frames, s.problem]));
  assert.deepEqual(asked.slice(0, 1), [HEADER]);
  assert.ok(Math.max(...asked.slice(1)) <= 44, "no read of audio");
  assert.equal(remote.header.length, HEADER);
});

test("an entry laid out in another order is listed with a problem and its length, and can be removed", async () => {
  const bytes = file({ 500: "Kick" });
  const entry = wav({ frames: 20, list: true, esli: new Uint8Array(1172) });
  const odd = new Uint8Array(HEADER + entry.length);
  odd.set(bytes.subarray(0, HEADER));
  put32(odd, 16 + 4 * 500, HEADER);
  odd.set(entry, HEADER);
  const remote = await parseRemote(async (at, n) => odd.slice(at, at + n), odd.length);
  assert.equal(remote.samples[0].length, entry.length);
  assert.equal(remote.samples[0].problem, "Aufbau nicht erkannt");
  const plan = planChange(odd, remote, { remove: [500] });
  assert.equal(plan.size, HEADER);
});

test("a remote file that is no sample file or shorter than a header is refused", async () => {
  await assert.rejects(parseRemote(async () => new Uint8Array(HEADER), HEADER), /e2s sample all/);
  await assert.rejects(parseRemote(async () => new Uint8Array(10), 10), /kürzer als ein Kopf/);
});
