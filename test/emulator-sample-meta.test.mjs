import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DeviceSession } from "../src/session.mjs";
import { identify } from "../src/firmware.mjs";
import { VsbImage } from "../src/image.mjs";
import { buildProfile } from "../src/profile.mjs";
import { readUnits } from "../src/node.mjs";
import { ramEntry } from "../src/map/address.mjs";
import { plan } from "../src/plan.mjs";
import { TIMEOUTS } from "../src/sender.mjs";
import { SAMPLE_COUNT } from "../src/samples.mjs";
import { startEmulator } from "./support/emu.mjs";

// The sample tables (data/map/sample.mjs) in the firmware itself: its RAM answers at the mapped addresses, and a name
// and a tune go in through planner and gate, are read back, and come out again, with every other byte of the entries
// as it was. The emulator starts without a sample card, so slot 701 is unused and nothing of the user's is touched.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;

let emu;
before(async () => { if (!skip) emu = await startEmulator(vsb); });
after(async () => { await emu?.stop(); });

// The service answers in device time, so on a loaded machine a reply can take longer than a real device's 3 s of wall time.
const PATIENT = Object.fromEntries(Object.entries(TIMEOUTS).map(([kind, ms]) => [kind, kind === "quiet" ? ms : ms * 10]));
const INDEX = 700;

async function session() {
  const s = new DeviceSession({ port: emu.port, timeouts: PATIENT });
  await s.connect();
  const bytes = new Uint8Array(readFileSync(vsb));
  const units = readUnits();
  s.useFirmware(bytes, await identify(bytes), { units, profile: buildProfile(new VsbImage(bytes), units) });
  return s;
}

const ram = async (s, addr, length) => {
  const run = await s.sender.run(plan({ kind: "readRam", addr, length }, { channel: s.device.channel }));
  assert.equal(run.ok, true, run.error?.message);
  return Uint8Array.from(run.results[0].value);
};
const changed = (a, b) => [...a.keys()].filter(i => a[i] !== b[i]);

test("emulator samples: the name table, the playback table and the metadata table answer at the mapped addresses", { skip }, async () => {
  const s = await session();
  const names = await s.readSampleNames();
  assert.equal(names.length, SAMPLE_COUNT);
  const entry = await s.readSample(INDEX);
  assert.deepEqual([entry.name, entry.rate, entry.pcmBytes, entry.tune], ["Sample701", 48000, 0, 0], "an unused slot of a device without a sample card holds a default name, 48000 Hz and no audio");
  assert.ok(names.slice(499).every((n, i) => n === `Sample${500 + i}`), "so do all the user slots from 500 on");
  assert.equal((await ram(s, ramEntry("samplePlayback", INDEX).ram, 16)).length, 16);
  assert.equal((await ram(s, ramEntry("sampleMeta", INDEX).ram, 0x45c)).length, 0x45c);
});

test("emulator samples: a name and a tune are written, read back and taken back, and no other byte of the entries moves", { skip }, async () => {
  const s = await session();
  const at = block => ramEntry(block, INDEX).ram;
  const before = { name: await ram(s, at("sampleName"), 0x20), play: await ram(s, at("samplePlayback"), 0x10), meta: await ram(s, at("sampleMeta"), 0x45c) };
  const edit = { kind: "sample", index: INDEX, name: "Emu Test", tune: -12, before: { name: "Sample701", tune: 0, rate: 48000, pcmBytes: 0 } };
  const asked = await s.apply(edit);
  assert.equal(asked.needsConfirmation, true, "an unused slot asks first");
  const done = await s.apply(edit, { confirmed: true });
  assert.equal(done.ok, true, done.error?.message ?? JSON.stringify(done.gate?.reasons));
  assert.deepEqual(await s.readSample(INDEX).then(e => [e.name, e.tune]), ["Emu Test", -12]);
  const after = { name: await ram(s, at("sampleName"), 0x20), play: await ram(s, at("samplePlayback"), 0x10), meta: await ram(s, at("sampleMeta"), 0x45c) };
  assert.deepEqual(changed(before.name, after.name), [12, 13, 14, 15, 16, 18, 19, 20], "the name bytes that differ between Sample701 and Emu Test");
  assert.deepEqual(changed(before.play, after.play), []);
  assert.deepEqual(changed(before.meta, after.meta), [21], "the tune byte");
  assert.equal((await s.undo()).ok, true);
  assert.deepEqual(await ram(s, at("sampleName"), 0x20), before.name);
  assert.deepEqual(await ram(s, at("sampleMeta"), 0x45c), before.meta);
  assert.equal(await s.alive(), true, "the firmware still answers");
});
