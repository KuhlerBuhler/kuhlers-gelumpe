import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { API_BY_NAME, ERROR, SCRIPT_GIF } from "../data/script/contract.mjs";
import { PRESETS } from "../data/script/presets.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { gifPath, packGif, readGifFrame } from "../src/script/gif.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;
const frameOf = seed => Uint8Array.from({ length: 1024 }, (_, i) => (i * seed + seed) & 255);
const build = source => {
  const r = compile(source, { name: "file" });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  return r.blob;
};

test("a picture file reads back frame by frame, with the delay, 0 past the end and -1 for anything that is not one", () => {
  const file = packGif([{ delay: 40, bytes: frameOf(3) }, { delay: 0, bytes: frameOf(5) }, { delay: 70000, bytes: frameOf(7) }]);
  assert.equal(file.length, SCRIPT_GIF.header + 3 * 1028);
  assert.deepEqual(Array.from(file.subarray(0, 8)), [0x47, 0x47, 0x49, 0x46, 1, 0, 3, 0], "GGIF, version 1, three frames");
  const slots = new Int32Array(1024);
  assert.equal(readGifFrame(file, 1, slots), 1, "a delay of 0 is stored as 1");
  assert.deepEqual(Array.from(slots), Array.from(frameOf(5)));
  assert.equal(readGifFrame(file, 2, slots), 65535);
  assert.equal(readGifFrame(file, 0, slots), 40);
  assert.equal(readGifFrame(file, 3, slots), 0);
  assert.deepEqual(Array.from(slots), Array.from(frameOf(3)), "past the end nothing is read");
  assert.equal(readGifFrame(undefined, 0, slots), -1);
  assert.equal(readGifFrame(file.subarray(0, 8 + 1028 + 10), 1, slots), -1, "cut short");
  const foreign = file.slice();
  foreign[4] = 2;
  assert.equal(readGifFrame(foreign, 0, slots), -1, "another version");
  assert.equal(gifPath(7), "KORG/blechtribe/Gif/GIF07.E2G");
});

test("korg.file.frame needs API version 7 and an array of a whole display", () => {
  assert.equal(API_BY_NAME.get("korg.file.frame").since, 7);
  const blob = build('const pic = new Array(1024); let got = 0; korg.onEvent("buttonPress", (k) => { got = korg.file.frame(pic, 1, 0); });');
  assert.equal(decodeBlob(blob).header.apiVersion, 7);
  const device = new SimDevice({ card: new Map([[gifPath(1), packGif([{ delay: 90, bytes: frameOf(9) }])]]) });
  const loaded = device.load(blob);
  device.frame();
  device.post("buttonPress", 3);
  device.frame();
  assert.equal(loaded.script.vars[1024], 90);
  assert.deepEqual(Array.from(loaded.script.vars.subarray(0, 1024)), Array.from(frameOf(9)));
  const small = new SimDevice();
  const short = small.load(build('const pic = new Array(512); korg.onEvent("buttonPress", (k) => { korg.file.frame(pic, 1, 0); });'));
  small.frame();
  small.post("buttonPress", 3);
  small.frame();
  assert.equal(short.script.fault?.code ?? small.status().scripts[0].fault?.code, ERROR.API_ARG);
});

function player(card) {
  const r = compile(PRESETS.find(p => p.id === "gifplayer").source, { name: "gifplayer" });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  let now = 0;
  const device = new SimDevice({ card, now: () => now });
  const loaded = device.load(r.blob);
  assert.ok(loaded.ok);
  device.frame();
  assert.ok(device.openApp(0));
  return { device, step: (ms = 40) => { now += ms; device.frame(); }, v: name => loaded.script.vars[r.info.symbols[name].slot] };
}

test("the GIF Player plays the frames at their delay, loops, changes speed, pauses and says when a file is missing", () => {
  const a = frameOf(3), b = frameOf(5);
  const p = player(new Map([[gifPath(0), packGif([{ delay: 80, bytes: a }, { delay: 120, bytes: b }])]]));
  p.device.frame();
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(a), "the first frame right on open");
  p.step(40);
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(a), "still inside its 80 ms");
  p.step(40);
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(b));
  p.step(120);
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(a), "it loops");
  p.device.post("buttonPress", key("PART_RIGHT"));
  p.step(40);
  assert.equal(p.v("speed"), 200);
  p.step(40);
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(b), "the frame shown keeps the time it had");
  p.step(40);
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(b));
  p.step(20);
  assert.deepEqual(Array.from(p.device.display.bytes), Array.from(a), "120 ms at double speed are 60");
  p.device.post("buttonPress", key("TAP"));
  p.step(40);
  assert.equal(p.v("paused"), 1);
  const paused = Array.from(p.device.display.bytes);
  p.step(400);
  assert.deepEqual(Array.from(p.device.display.bytes), paused, "nothing moves while paused");
  p.device.post("buttonPress", key("TAP"));
  p.device.post("encoder", 0, 1);
  p.step(40);
  assert.equal(p.v("file"), 1);
  assert.ok(p.device.display.rows().join("\n").includes("#"), "the missing file is said in text");
  assert.notDeepEqual(Array.from(p.device.display.bytes), Array.from(a));
});

test("gif2e2g turns a GIF into frames the runtime reads, pixel for pixel and with its delays", t => {
  const dir = mkdtempSync(join(tmpdir(), "e2g-"));
  const make = `
from PIL import Image
a = Image.new("L", (128, 64), 0); a.putpixel((0, 0), 255); a.putpixel((127, 63), 255); a.putpixel((5, 9), 255)
b = Image.new("L", (128, 64), 255)
a.save("${dir}/in.gif", save_all=True, append_images=[b], duration=[30, 250], loop=0)
Image.new("L", (64, 32), 255).save("${dir}/half.png")
`;
  const made = spawnSync("python3", ["-c", make], { encoding: "utf8" });
  if (made.status) { t.skip(`Pillow: ${made.stderr.trim().split("\n").pop()}`); return; }
  const run = spawnSync("python3", ["tools/gif/gif2e2g.py", `${dir}/in.gif`, "4", "--out", dir], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const file = new Uint8Array(readFileSync(`${dir}/GIF04.E2G`));
  const slots = new Int32Array(1024);
  assert.equal(readGifFrame(file, 0, slots), 30);
  const lit = [];
  slots.forEach((v, i) => { for (let bit = 0; bit < 8; bit++) if ((v >> bit) & 1) lit.push([i % 128, (i >> 7) * 8 + bit]); });
  assert.deepEqual(lit, [[0, 0], [5, 9], [127, 63]]);
  assert.equal(readGifFrame(file, 1, slots), 250);
  assert.ok(Array.from(slots).every(v => v === 255), "a white frame lights everything");
  assert.equal(readGifFrame(file, 2, slots), 0);
  const half = spawnSync("python3", ["tools/gif/gif2e2g.py", `${dir}/half.png`, "5", "--out", dir, "--delay", "60"], { encoding: "utf8" });
  assert.equal(half.status, 0, half.stderr);
  assert.equal(readGifFrame(new Uint8Array(readFileSync(`${dir}/GIF05.E2G`)), 0, slots), 60);
  assert.ok(Array.from(slots).every(v => v === 255), "a picture of half the size scales up to the whole display");
});
