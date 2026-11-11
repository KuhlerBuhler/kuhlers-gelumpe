import { test } from "node:test";
import assert from "node:assert/strict";
import { readUnits } from "../src/node.mjs";
import { buildOf } from "../src/firmware.mjs";
import { modFromType } from "../src/fx-v2.mjs";
import { locateModTable, readModType } from "../src/modtable.mjs";
import { collectionFor, targetFirmware, parseCollection, BUILDS, TARGETS } from "../src/fx-collection.mjs";
import { makeFirmwareWithArrays } from "./helpers.mjs";

// The export of e2sFx.all is for the firmware on the device, which the user names, never for the one the emulator
// happens to run: a Hacktribe device refuses a file with Korg's build (tools/patch/fx_card.s, cmp r0, #FX_BUILD).
const units = readUnits();

/** makeFirmware's image as Hacktribe (its run at 0x170100 is not erased) or as Korg's 2.02 (the run erased). */
async function firmware(build) {
  const bytes = await makeFirmwareWithArrays();
  if (build === "stock") bytes.fill(0xff, 0x170100, 0x170140);
  assert.equal(buildOf(bytes), build);
  return bytes;
}

const headerBuild = bytes => new DataView(bytes.buffer, bytes.byteOffset).getUint32(16, true);

async function items(vsb) {
  const table = locateModTable(vsb);
  return [
    { kind: "mod", slot: 2, from: 1 },
    { kind: "mod", slot: 4, preset: { ...modFromType(readModType(vsb, table.file, 3)), name: "Karte Mod" } },
  ];
}

test("the target picks the build in the header: Hacktribe 1, Korg's original 2", async () => {
  assert.deepEqual(TARGETS, ["hacktribe", "stock"]);
  for (const target of TARGETS) {
    const vsb = await firmware(target);
    const made = collectionFor(target, vsb, await items(vsb), units);
    assert.equal(made.ok, true, made.reason);
    assert.equal(headerBuild(made.bytes), BUILDS[target], target);
    const read = parseCollection(made.bytes);
    assert.equal(read.ok, true, read.reason);
    assert.equal(read.build, target);
    assert.deepEqual(read.entries.map(e => [e.kind, e.index]), [["mod", 1], ["mod", 3]]);
  }
  assert.equal(BUILDS.hacktribe, 1);
  assert.equal(BUILDS.stock, 2);
});

test("a firmware of the other build is refused, not built for the wrong device", async () => {
  // what an emulator running Korg's original would hand over, while the device runs Hacktribe, and the other way round
  const stock = await firmware("stock");
  const hacktribe = await firmware("hacktribe");
  assert.deepEqual(collectionFor("hacktribe", stock, await items(stock), units), { ok: false, code: "build" });
  assert.deepEqual(collectionFor("stock", hacktribe, await items(hacktribe), units), { ok: false, code: "build" });
  assert.deepEqual(collectionFor("synth", hacktribe, [], units), { ok: false, code: "build" });
  assert.deepEqual(collectionFor("hacktribe", null, [], units), { ok: false, code: "build" });
});

test("targetFirmware takes a file of the target's build, refuses the blue and another build", async () => {
  const stock = await firmware("stock");
  const hacktribe = await firmware("hacktribe");
  assert.equal((await targetFirmware("hacktribe", hacktribe)).bytes, hacktribe);
  assert.equal((await targetFirmware("stock", stock)).bytes, stock);
  assert.deepEqual(await targetFirmware("stock", hacktribe), { ok: false, code: "build" });
  // Korg's 2.02 turns into Hacktribe only with hacktribe-2.patch; without the patch the target is not reached
  assert.deepEqual(await targetFirmware("hacktribe", stock), { ok: false, code: "build" });
  let asked = 0;
  const wrong = await targetFirmware("hacktribe", stock, { hacktribePatch: async () => { asked++; return new Uint8Array(8); } });
  assert.equal(asked, 1, "the patch is loaded when Korg's file has to become Hacktribe");
  assert.equal(wrong.ok, false, "a file that is not Korg's original 2.02 is not converted");
  const blue = Uint8Array.from(hacktribe);
  blue.set([0x45, 0x32, 0x00], 0x10);
  assert.deepEqual(await targetFirmware("hacktribe", blue), { ok: false, code: "device" });
});
