import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { OBJECTS } from "../data/script/objects.mjs";
import { PATTERN_MOTION } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice } from "../src/script/sim.mjs";

/** The catalog plugins of plugin API 26 to 34 (Phase 11 of the plan): one per area, on the simulated device. */
function load(id) {
  const result = compile(PRESETS.find(p => p.id === id).source, { name: id });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  assert.deepEqual(result.warnings, [], `${id} uses a deprecated call`);
  const device = new SimDevice();
  assert.ok(device.load(result.blob).ok);
  device.run(1);
  return { device, hw: device.hardware, api: decodeBlob(result.blob).header.apiVersion };
}
const leaf = path => OBJECTS.findIndex(o => o.path === path);
const lit = (device, y0, y1, x0 = 0) => {
  let n = 0;
  for (let y = y0; y < y1; y++) for (let x = x0; x < 128; x++) n += (device.display.bytes[(y >> 3) * 128 + x] >> (y & 7)) & 1;
  return n;
};
const rows = (device, y0, y1) => Array.from({ length: y1 - y0 }, (_, i) =>
  Array.from({ length: 128 }, (_, x) => (device.display.bytes[((y0 + i) >> 3) * 128 + x] >> ((y0 + i) & 7)) & 1).join("")).join("\n");

test("System Info draws every line and follows the adapter while it is open", () => {
  const { device, hw, api } = load("sysinfo");
  assert.equal(api, 34);
  assert.ok(device.openApp(0));
  device.run(1);
  for (const [y0, y1] of [[2, 10], [26, 34], [38, 46], [50, 58]]) assert.ok(lit(device, y0, y1) > 0, `line at ${y0}`);
  const adapter = rows(device, 50, 58);
  hw.objects[leaf("korg.system.power")] = 0;
  hw.objects[leaf("korg.system.battery")] = 2;
  device.run(30);
  assert.notEqual(rows(device, 50, 58), adapter, "the battery line replaces the adapter line within a second");
});

test("VU Meter draws a bar as wide as the level and holds the peak mark", () => {
  const { device, hw, api } = load("vumeter");
  assert.equal(api, 31);
  assert.ok(device.openApp(0));
  hw.audioLevel = [254, 0];
  device.run(1);
  assert.ok(lit(device, 12, 26, 14) >= 108 * 14, "a full bar on side 1");
  assert.equal(lit(device, 38, 52, 14), 14, "side 2 shows only its peak mark at 0");
  hw.audioLevel = [0, 127];
  device.run(1);
  assert.equal(lit(device, 12, 26, 14), 14, "the peak mark of side 1 stays after the level fell");
  assert.ok(lit(device, 38, 52, 14) >= 54 * 14, "half a bar on side 2");
  device.run(30);
  assert.equal(lit(device, 12, 26, 14), 14, "after the hold the mark sits at the level, 0");
});

test("MIDI Echo sends the pads on the chosen channel only when one is set, the note off on the note on's channel", () => {
  const { device, hw, api } = load("midiecho");
  assert.equal(api, 30);
  const page = device.menus.find(m => m.label === "MIDI ECHO CH");
  device.post("pad", 0, 1, 100);
  device.run(1);
  assert.deepEqual(hw.midiSent, [], "channel 0 is off");
  device.menuSet(page.id, 10);
  device.run(1);
  device.post("pad", 3, 1, 90);
  device.run(1);
  device.menuSet(page.id, 2);
  device.run(1);
  device.post("pad", 3, 0, 0);
  device.run(1);
  assert.deepEqual(hw.midiSent, [[0x99, 39, 90], [0x89, 39, 0x40]]);
});

test("Motion Clear clears the selected part's lanes on reaching 3, once until it is turned below 3 again", () => {
  const { device, hw, api } = load("motionclear");
  assert.equal(api, 28);
  const page = device.menus.find(m => m.label === "CLEAR MOTION");
  const block = hw.patternBlock(-1);
  const own = () => [...block.subarray(PATTERN_MOTION.owner, PATTERN_MOTION.owner + 4)];
  block.set([3, 3, 5, 0], PATTERN_MOTION.owner);
  hw.part = 2;
  for (const v of [1, 2]) { device.menuSet(page.id, v); device.run(1); }
  assert.deepEqual(own(), [3, 3, 5, 0], "nothing below 3");
  device.menuSet(page.id, 3);
  device.run(1);
  assert.deepEqual(own(), [0, 0, 5, 0], "part 3 cleared, part 5 kept");
  block[PATTERN_MOTION.owner + 3] = 3;
  hw.part = 16;
  device.menuSet(page.id, 3);
  device.run(1);
  assert.deepEqual(own(), [0, 0, 5, 3], "3 again without going below does nothing");
  device.menuSet(page.id, 2);
  device.run(1);
  device.menuSet(page.id, 3);
  device.run(1);
  assert.deepEqual(own(), [0, 0, 0, 0], "with all parts selected every part's lanes go");
});
