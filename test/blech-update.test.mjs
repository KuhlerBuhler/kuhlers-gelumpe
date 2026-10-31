import { test } from "node:test";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";
import { applyPatches } from "../src/patch.mjs";
import { addRelease, emptyKnown, recogniseBlech, KNOWN_FORMAT } from "../src/blech-update.mjs";
import { sha256 } from "../src/firmware.mjs";
import { encodeAnimation, loadingAnimPatch, FRAME_BYTES } from "../src/loading-anim.mjs";
import { field } from "../src/map/index.mjs";
import { asStock, makeFirmware } from "./helpers.mjs";

// Releases of our own standing in for BLECH's: a hook site (a word of "Korg's code" that is rewritten) and two free areas.
const HOOK = 0x2000;
const HOOK2 = 0x2100;
const AREA_A = 0x1a2100;
const AREA_B = 0x1a2400;
const hex = (...words) => words.map(w => w.toString(16).padStart(8, "0")).join("");

async function original() {
  const base = await makeFirmware();
  new DataView(base.buffer).setUint32(HOOK, 0xe1a01000, true);
  new DataView(base.buffer).setUint32(HOOK2, 0xe1a02000, true);
  return base;
}

const raw = async (base, id, file, bytes) => ({
  format: "gelumpe-patch", version: 1, id, name: id,
  changes: [{ file, bytes, expect: await sha256(base.subarray(file, file + bytes.length / 2)) }],
});

/** One release: the hook points at its code area, the code sits where that release put it. */
async function release(base, { hook, area, extra = [] }) {
  return [
    await raw(base, "runtime", HOOK, hex(hook)),
    await raw(base, "runtime-code", area, hex(0xe3a00001, 0xe12fff1e, 0x11111111, hook)),
    ...extra,
  ];
}

async function setup() {
  const base = await original();
  const old = await release(base, { hook: 0xea000100, area: AREA_A, extra: [await raw(base, "name", HOOK2, hex(0xe1a0ffff)), await raw(base, "gone", AREA_B, hex(0xdeadbeef))] });
  const now = await release(base, { hook: 0xea000200, area: AREA_B, extra: [await raw(base, "name", HOOK2, hex(0xe1a0ffff))] });
  const known = emptyKnown();
  await addRelease(known, "1.0", "hacktribe", base, old);
  await addRelease(known, "1.1", "hacktribe", base, now);
  return { base, old, now, known };
}

test("a file of an older release is updated to the current set, byte for byte as if patched from the original", async () => {
  const { base, old, now, known } = await setup();
  const patched = (await applyPatches(base, old)).bytes;
  const rec = await recogniseBlech(patched, known);
  assert.equal(rec.ok, true);
  assert.deepEqual(rec.present.sort(), ["name", "runtime"], "hook sites that are in the file");
  assert.equal(rec.bytes[AREA_A], 0, "the free areas are reset to their fill");
  assert.equal(rec.bytes[AREA_B], 0);
  assert.equal(await sha256(rec.bytes.subarray(HOOK, HOOK + 4)), await sha256(patched.subarray(HOOK, HOOK + 4)), "hook sites are left as they are");
  assert.equal((await applyPatches(rec.bytes, now)).ok, false, "the old hook is not what the current patch expects");
  const updated = await applyPatches(rec.bytes, now, rec.options);
  assert.equal(updated.ok, true, updated.reasons.join(" "));
  const direct = await applyPatches(base, now);
  assert.deepEqual(updated.bytes, direct.bytes);
  assert.equal(updated.bytes[AREA_A + 4], 0, "what the current set no longer writes is back to the fill");
});

test("a file with only some of the old features, and one of the current release, is recognised too", async () => {
  const { base, old, now, known } = await setup();
  const some = (await applyPatches(base, [old[2]])).bytes;
  const rec = await recogniseBlech(some, known);
  assert.deepEqual([rec.ok, rec.present], [true, ["name"]]);
  const current = (await applyPatches(base, now)).bytes;
  const again = await recogniseBlech(current, known);
  assert.equal(again.ok, true);
  assert.deepEqual((await applyPatches(again.bytes, now, again.options)).bytes, current);
});

test("a file that holds anything else in a region is not touched: edited hook, edited code, no BLECH, other build", async () => {
  const { base, old, known } = await setup();
  const patched = (await applyPatches(base, old)).bytes;
  const hook = Uint8Array.from(patched);
  hook[HOOK] ^= 0x55;
  assert.deepEqual(await recogniseBlech(hook, known), { ok: false, why: "region" });
  const code = Uint8Array.from(patched);
  code[AREA_A + 1] ^= 1;
  assert.deepEqual(await recogniseBlech(code, known), { ok: false, why: "region" });
  assert.deepEqual(await recogniseBlech(base, known), { ok: false, why: "none" });
  assert.deepEqual(await recogniseBlech(asStock(patched), known), { ok: false, why: "build" });
  assert.deepEqual(await recogniseBlech(patched, null), { ok: false, why: "build" });
});

const SLOT = field("loadingAnim").where.offset;
const animation = seed => {
  const frame = k => Uint8Array.from({ length: FRAME_BYTES }, (_, i) => ((i * seed + k) % 7 === 0 ? 0xff : 0));
  return encodeAnimation({ progress: [frame(0), frame(1), frame(2)], loop: [], loopFrom: 0 }).bytes;
};

test("the loading animation in its slot is the user's: kept, replaced when one is chosen, never taken for release bytes", async () => {
  const base = await original();
  // an older release kept code where the slot is now; the current one does not write there
  const old = [await raw(base, "runtime-code", SLOT, hex(0xe3a00001, 0xe12fff1e)), await raw(base, "runtime", HOOK, hex(0xea000100))];
  const now = [await raw(base, "runtime", HOOK, hex(0xea000200)), await raw(base, "code", AREA_A, hex(0xe3a00001))];
  const known = emptyKnown();
  await addRelease(known, "1.0", "hacktribe", base, old);
  await addRelease(known, "1.1", "hacktribe", base, now);
  const [mine, other] = [animation(3), animation(5)];
  const withAnimation = async (bytes, a) => (a ? (await applyPatches(bytes, [loadingAnimPatch(a)])).bytes : bytes);
  const direct = async a => withAnimation((await applyPatches(base, now)).bytes, a);
  const file = await direct(mine);
  const rec = await recogniseBlech(file, known);
  assert.equal(rec.ok, true, "a file of the current release with an animation is known");
  const update = async a => withAnimation((await applyPatches(rec.bytes, now, rec.options)).bytes, a);
  assert.deepEqual(await update(mine), await direct(mine), "the same animation again");
  assert.deepEqual(await update(other), await direct(other), "another animation replaces it");
  const kept = await update(null);
  assert.deepEqual(kept, file, "no choice keeps it, everything else as it was");
  // without an animation the slot of an older file is code, and goes back to FF
  const older = await recogniseBlech((await applyPatches(base, old)).bytes, known);
  assert.equal(older.ok, true);
  assert.equal(older.bytes[SLOT], 0);
  // bytes in the slot that are no animation are not user data
  const junk = Uint8Array.from(file);
  junk[SLOT + 20] ^= 0xff;
  junk[SLOT + 4] ^= 1;
  assert.deepEqual(await recogniseBlech(junk, known), { ok: false, why: "region" });
  for (const regions of Object.values(known.builds)) assert.ok(!regions.some(r => r[2] === "loading-anim"));
});

test("data/known-releases.json holds only hashes and offsets, for the three builds and the releases from 1.3.3 on", () => {
  const known = JSON.parse(readFileSync(new URL("../data/known-releases.json", import.meta.url), "utf8"));
  assert.equal(known.format, KNOWN_FORMAT);
  for (const release of ["1.3.3", "1.3.4", "1.3.5", "1.3.6", "1.3.7"]) assert.ok(known.releases.includes(release), release);
  for (const build of ["hacktribe", "stock", "synth"]) {
    assert.ok(known.builds[build].length > 300, build);
    for (const [file, length, id, fill, original, written] of known.builds[build]) {
      assert.ok(Number.isInteger(file) && Number.isInteger(length) && length > 0 && file + length <= 0x200100);
      assert.equal(typeof id, "string");
      assert.ok([-1, 0, 0xff].includes(fill));
      for (const hash of [original, ...written]) assert.match(hash, /^[0-9a-f]{16}$/);
      assert.notEqual(id, "loading-anim");
    }
  }
  assert.ok(readFileSync(new URL("../data/known-releases.json", import.meta.url)).length < 200_000, "stays small");
});

// A Hacktribe 2.02 file patched with a release's own set (from its git tag) must be found in data/known-releases.json.
// 1.3.2 and older are left out of it on purpose: their regions would make 1.3.7 files ambiguous.
const tagSet = tag => {
  const show = path => JSON.parse(execFileSync("git", ["show", `${tag}:${path}`], { cwd: new URL("..", import.meta.url).pathname, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }));
  return show("data/patches/blech.json").patches.map(show);
};
for (const [tag, found] of [["v1.3.3", true], ["v1.3.7", true], ["v1.3.0", false]]) {
  test(`a Hacktribe file with BLECH ${tag} is ${found ? "" : "not "}recognised for the update`, { skip: process.env.E2_VSB ? false : "set E2_VSB" }, async t => {
    const known = JSON.parse(readFileSync(new URL("../data/known-releases.json", import.meta.url), "utf8"));
    let set;
    try { set = tagSet(tag); } catch { t.skip(`no tag ${tag} in this clone`); return; }
    const old = await applyPatches(new Uint8Array(readFileSync(process.env.E2_VSB)), set);
    assert.equal(old.ok, true, old.reasons.join(" "));
    const k = await recogniseBlech(old.bytes, known);
    assert.equal(k.ok, found, k.why);
  });
}
