import { test } from "node:test";
import assert from "node:assert/strict";
import { DeviceSession } from "../src/session.mjs";
import { fetchUpdateFile, storeUpdateFile, storeDoom } from "../src/usb-update.mjs";
import { simPort } from "./helpers.mjs";

// The update over USB (src/usb-update.mjs) against the simulation of BLECH's FILE commands (src/device.mjs), which follows the
// firmware's (tools/patch/blech_sysex.py, checked in the emulator by sysex_cases.py file_cases).
const FAST = { search: 200, read: 200, ack: 200, pattern: 400, global: 200, info: 100 };
const image = new Uint8Array(0x200100);
const fill = (n, seed) => Uint8Array.from({ length: n }, (_, i) => (i * 31 + seed) & 0xff);

async function device(card, options = {}) {
  const rig = await simPort({ bytes: image, blech: true, card, ...options });
  const session = new DeviceSession({ port: rig.port, known: [], timeouts: FAST });
  await session.connect();
  return { ...rig, session };
}

test("the first update over USB reads SYSTEM.VSB, writes the patched file and keeps the unpatched one beside it", async () => {
  const unpatched = fill(70000, 1);
  const card = new Map([["SYSTEM.VSB", unpatched]]);
  const { session } = await device(card);
  const seen = [];
  const got = await fetchUpdateFile(session, (done, total) => seen.push([done, total]));
  assert.equal(got.fromOriginal, false);
  assert.deepEqual(got.bytes, unpatched);
  assert.deepEqual(seen.at(-1), [70000, 70000]);
  assert.ok(seen.length >= 3, "read in blocks");
  const patched = fill(70000, 2);
  await storeUpdateFile(session, patched, got.bytes);
  assert.deepEqual(card.get("SYSTEM.VSB"), patched);
  assert.deepEqual(card.get("ORIGINAL.BIN"), unpatched);
});

test("a later update starts from ORIGINAL.BIN and leaves it as it is", async () => {
  const unpatched = fill(5000, 3);
  const card = new Map([["SYSTEM.VSB", fill(5000, 4)], ["ORIGINAL.BIN", unpatched]]);
  const { session } = await device(card);
  const got = await fetchUpdateFile(session);
  assert.equal(got.fromOriginal, true);
  assert.deepEqual(got.bytes, unpatched);
  const patched = fill(4000, 5);
  await storeUpdateFile(session, patched, null);
  assert.deepEqual(card.get("SYSTEM.VSB"), patched, "a shorter file replaces the longer one whole");
  assert.deepEqual(card.get("ORIGINAL.BIN"), unpatched);
});

test("without SYSTEM.VSB on the card, or without the FILE commands on the device, the page is told why", async () => {
  const { session } = await device(new Map());
  await assert.rejects(fetchUpdateFile(session), /fehlt die Datei SYSTEM\.VSB/);
  const old = await device(null);
  await assert.rejects(fetchUpdateFile(old.session), /zu alt für Updates über USB/);
});

test("Doom goes onto the card as KORG/blechtribe/Doom/doom.wad and doom.bin, the wad first, the update file stays", async () => {
  const system = fill(3000, 6);
  const card = new Map([["SYSTEM.VSB", system], ["doom.bin", fill(90000, 7)]]);
  const { session } = await device(card);
  const bin = fill(70000, 8), wad = fill(0x210000, 9);
  const seen = [];
  await storeDoom(session, { bin, wad }, (done, total) => seen.push([done, total]));
  assert.deepEqual(card.get("doom.wad"), wad, "past the size of a VSB");
  assert.deepEqual(card.get("doom.bin"), bin, "an older, longer doom.bin is made anew");
  assert.deepEqual(card.get("SYSTEM.VSB"), system);
  assert.deepEqual(seen.at(-1), [bin.length + wad.length, bin.length + wad.length]);
  assert.ok(seen.findIndex(([done]) => done > wad.length) > seen.findIndex(([done]) => done === wad.length), "doom.bin after the wad");
});

test("a stopped Doom send leaves no doom.bin, and a BLECHTRIBE from before the Doom files is told so", async () => {
  const card = new Map();
  const { session } = await device(card);
  const stop = new AbortController();
  const wad = fill(100000, 10);
  await assert.rejects(storeDoom(session, { bin: fill(100, 11), wad }, done => { if (done >= 0x8000) stop.abort(); }, stop.signal));
  assert.equal(card.has("doom.bin"), false);
  const old = await device(new Map());
  old.sim.doom = false;
  await assert.rejects(storeDoom(old.session, { bin: fill(100, 12), wad: fill(100, 13) }), /kann Doom noch nicht über USB/);
});
