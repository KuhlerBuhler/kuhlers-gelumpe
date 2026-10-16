import { test } from "node:test";
import assert from "node:assert/strict";
import { buildSplashPatch } from "../tools/patch/splash_synth.mjs";
import { applyPatches } from "../src/patch.mjs";
import { sha256 } from "../src/firmware.mjs";

test("the synth splash follows descriptor 13 and guards the original bitmap", async () => {
  const bytes = new Uint8Array(0x200100);
  bytes.set([0x45, 0x32, 0], 0x10);
  const view = new DataView(bytes.buffer);
  for (let n = 0; n < 17; n++) {
    const desc = 0x100000 + n * 12;
    view.setUint32(0xAC724 + n * 4, 0xC0000000 + desc, true);
    view.setUint32(desc + 0x100, n === 13 ? 128 : 10, true);
    view.setUint32(desc + 0x104, n === 13 ? 64 : 8, true);
    view.setUint32(desc + 0x108, 0xC0110002, true);
  }
  const art = new Uint8Array(1024).fill(0xA5);
  const patch = buildSplashPatch(bytes, art);
  assert.deepEqual(patch.builds, ["synth"]);
  assert.equal(patch.changes[0].file, 0x110102);
  assert.equal(patch.changes[0].expect, await sha256(new Uint8Array(1024)));
  const applied = await applyPatches(bytes, [patch]);
  assert.equal(applied.ok, true, applied.reasons.join(" "));
  assert.deepEqual(applied.bytes.subarray(0x110102, 0x110502), art);
  assert.deepEqual(applied.bytes.subarray(0, 0x100), bytes.subarray(0, 0x100));
  bytes[0x110102] = 1;
  assert.equal((await applyPatches(bytes, [patch])).ok, false);
  assert.throws(() => buildSplashPatch(bytes, art.subarray(1)), /1024/);
});
