import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { API_BY_NAME, ERROR, SCRIPT_GIF, SCRIPT_MEDIA } from "../data/script/contract.mjs";
import { PRESETS } from "../data/script/presets.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { gifPath, packGif, readGifFrame, frameOfPixels } from "../src/script/gif.mjs";
import { listMedia, mediaNameBytes, readMediaPicture } from "../src/script/media.mjs";
import { encodeBmp } from "../src/splash-bmp.mjs";
import { encodeAnimation } from "../src/loading-anim.mjs";

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

test("a picture of 128 x 64 pixels becomes one frame of display memory, column bytes eight rows high", () => {
  const pixels = new Uint8Array(128 * 64);
  pixels[0] = 1;                  // x 0, y 0: byte 0, bit 0
  pixels[7 * 128 + 5] = 1;        // x 5, y 7: byte 5, bit 7
  pixels[63 * 128 + 127] = 1;     // x 127, y 63: byte 7 * 128 + 127, bit 7
  const frame = frameOfPixels(pixels);
  assert.equal(frame.length, 1024);
  assert.deepEqual([frame[0], frame[5], frame[7 * 128 + 127]], [1, 0x80, 0x80]);
  assert.equal(frame.reduce((n, b) => n + b.toString(2).split("1").length - 1, 0), 3, "no other pixel set");
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

function viewer(card) {
  const r = compile(PRESETS.find(p => p.id === "bmpviewer").source, { name: "bmpviewer" });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  let now = 0;
  const device = new SimDevice({ card, now: () => now });
  const loaded = device.load(r.blob);
  assert.ok(loaded.ok);
  device.frame();
  assert.ok(device.openApp(0));
  device.frame();
  return { device, step: (ms = 40) => { now += ms; device.frame(); }, v: name => loaded.script.vars[r.info.symbols[name].slot] };
}

test("the Image Viewer pages through the pictures of a file with Part, shows the number for two seconds and wraps around", () => {
  const pics = [3, 5, 7].map(frameOf);
  const shows = (p, i) => Array.from(p.device.display.bytes).every((b, at) => b === pics[i][at]);
  const corner = p => Array.from(p.device.display.bytes.subarray(0, 30)).join(",");
  const p = viewer(new Map([[gifPath(2), packGif(pics.map(bytes => ({ delay: 100, bytes })))]]));
  assert.ok(p.device.display.rows().join("\n").includes("#"), "no file 0: it says so in text");
  assert.equal(p.v("shown"), 0);
  p.device.post("encoder", 0, 2);
  p.step();
  assert.equal(p.v("file"), 2);
  assert.equal(p.v("index"), 0);
  assert.ok(!shows(p, 0), "the number covers the corner");
  const one = corner(p);
  p.step(2000);
  assert.ok(shows(p, 0), "after two seconds the picture alone");
  p.device.post("buttonPress", key("PART_RIGHT"));
  p.step();
  assert.equal(p.v("index"), 1);
  assert.ok(!shows(p, 1));
  assert.notEqual(corner(p), one, "another number on another picture");
  p.step(2000);
  assert.ok(shows(p, 1));
  p.device.post("buttonPress", key("PART_RIGHT"));
  p.step();
  p.step(2000);
  assert.ok(shows(p, 2));
  assert.equal(p.v("count"), 0, "the count is not known yet");
  p.device.post("buttonPress", key("PART_RIGHT"));
  p.step();
  p.step(2000);
  assert.equal(p.v("index"), 0, "past the last picture it starts again");
  assert.equal(p.v("count"), 3);
  assert.ok(shows(p, 0));
  p.device.post("buttonPress", key("PART_LEFT"));
  p.step();
  p.step(2000);
  assert.equal(p.v("index"), 2, "back from the first goes to the last once the count is known");
  assert.ok(shows(p, 2));
  p.device.post("buttonPress", key("PART_LEFT"));
  p.step();
  p.step(2000);
  assert.ok(shows(p, 1));
  p.device.post("buttonPress", key("TAP"));
  p.step();
  p.step(5000);
  assert.ok(!shows(p, 1), "TAP keeps the number");
  p.device.post("buttonPress", key("TAP"));
  p.step();
  assert.ok(shows(p, 1), "a second TAP hides it");
  p.device.post("encoder", 0, -1);
  p.step();
  assert.equal(p.v("shown"), 0, "file 1 is missing");
  assert.equal(p.v("count"), 0, "a new file forgets the count");
  assert.equal(p.device.status().scripts[0].fault ?? null, null);
});

test("gif2e2g puts several BMPs into one file, one frame each in the order given", t => {
  const dir = mkdtempSync(join(tmpdir(), "e2g-bmp-"));
  const make = `
from PIL import Image
a = Image.new("1", (128, 64), 0); a.putpixel((3, 4), 1); a.save("${dir}/a.bmp")
Image.new("1", (128, 64), 1).save("${dir}/b.bmp")
c = Image.new("L", (128, 64), 0); c.putpixel((127, 0), 255); c.save("${dir}/c.bmp")
`;
  const made = spawnSync("python3", ["-c", make], { encoding: "utf8" });
  if (made.status) { t.skip(`Pillow: ${made.stderr.trim().split("\n").pop()}`); return; }
  const run = spawnSync("python3", ["tools/gif/gif2e2g.py", `${dir}/a.bmp`, `${dir}/b.bmp`, `${dir}/c.bmp`, "6", "--out", dir], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const file = new Uint8Array(readFileSync(`${dir}/GIF06.E2G`));
  const slots = new Int32Array(1024);
  const lit = () => { const out = []; slots.forEach((v, i) => { for (let bit = 0; bit < 8; bit++) if ((v >> bit) & 1) out.push([i % 128, (i >> 7) * 8 + bit]); }); return out; };
  assert.equal(readGifFrame(file, 0, slots), 100, "a still picture gets 100 ms");
  assert.deepEqual(lit(), [[3, 4]]);
  assert.equal(readGifFrame(file, 1, slots), 100);
  assert.ok(Array.from(slots).every(v => v === 255));
  assert.equal(readGifFrame(file, 2, slots), 100);
  assert.deepEqual(lit(), [[127, 0]]);
  assert.equal(readGifFrame(file, 3, slots), 0);
});

const media = name => SCRIPT_MEDIA.folder + name;
function mediaCard() {
  const marker = new Uint8Array(128 * 64);
  marker[0] = 1; marker[128 * 64 - 1] = 1;
  const topDown = encodeBmp(marker);
  new DataView(topDown.buffer).setInt32(22, -64, true);
  const broken = encodeBmp(marker);
  new DataView(broken.buffer).setUint16(28, 24, true);
  return new Map([
    [media("marker.bmp"), encodeBmp(marker)],
    [media("loading.blla"), new Uint8Array(readFileSync(new URL("../assets/blechy/loading.blla", import.meta.url)))],
    [media("top-down-picture-long.bmp"), topDown],
    [media("broken.bmp"), broken],
    [media("small.blla"), encodeAnimation({ progress: [frameOf(1), frameOf(2), frameOf(3)], loop: [frameOf(5), frameOf(7)] }).bytes],
    ["KORG/blechtribe/splash.bmp", encodeBmp(marker)],
  ]);
}

function mediaPlugin(card) {
  const r = compile(`const pic = new Array(1024); const nm = new Array(20);
    let kind = 0; let idx = 0; let fr = 0; let n0 = 0; let n1 = 0; let len = 0; let got = 0; let listed = 0;
    korg.onEvent("buttonPress", (k) => {
      if (listed == 0) { n0 = korg.file.count(0); n1 = korg.file.count(1); listed = 1; }
      len = korg.file.name(nm, kind, idx);
      got = korg.file.picture(pic, kind, idx, fr);
    });`, { name: "media" });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  const device = new SimDevice({ card });
  const loaded = device.load(r.blob);
  device.frame();
  const slot = name => r.info.symbols[name].slot;
  const vars = loaded.script.vars;
  return {
    blob: r.blob, device,
    v: name => vars[slot(name)],
    slots: name => Array.from(vars.subarray(slot(name), slot(name) + r.info.symbols[name].length)),
    call(kind, idx, fr) {
      vars[slot("kind")] = kind; vars[slot("idx")] = idx; vars[slot("fr")] = fr;
      device.post("buttonPress", 3);
      device.frame();
    },
  };
}

test("korg.file.count, name and picture need API 38", () => {
  for (const name of ["korg.file.count", "korg.file.name", "korg.file.picture"]) assert.equal(API_BY_NAME.get(name).since, 38, name);
  assert.equal(decodeBlob(mediaPlugin(new Map()).blob).header.apiVersion, 38);
});

test("the simulator lists Media/ and gives each picture exactly as readMediaPicture, with the name", () => {
  const card = mediaCard();
  const p = mediaPlugin(card);
  p.call(0, 0, 0);
  assert.deepEqual([p.v("n0"), p.v("n1")], [3, 2], "three .bmp and two .blla in Media/, the root left out");
  for (const kind of [0, 1]) {
    listMedia(card, kind).forEach((entry, idx) => {
      const bytes = card.get(entry.path);
      const total = Math.max(1, readMediaPicture(bytes, kind, 0, new Int32Array(1024)));
      for (const fr of [0, 1, total - 1, total]) {
        const want = new Int32Array(1024);
        p.call(kind, idx, fr);
        const before = p.slots("pic");
        want.set(before);
        assert.equal(p.v("got"), readMediaPicture(bytes, kind, fr, want), `${entry.name} picture ${fr}`);
        assert.deepEqual(p.slots("pic"), Array.from(want), `${entry.name} picture ${fr}`);
        const name = mediaNameBytes(entry.name);
        assert.equal(p.v("len"), name.length);
        assert.deepEqual(p.slots("nm").slice(0, name.length + 1), [...name, 0]);
      }
    });
  }
  p.call(0, 1, 0);
  assert.equal(p.v("len"), 17, "a long name is cut");
  assert.equal(p.v("got"), 1, "rows from the top");
  p.call(0, 2, 0);
  assert.equal(p.v("got"), -1, "a 24 bit .bmp is broken");
  p.call(1, 1, 4);
  assert.equal(p.v("got"), 5, "3 progress and 2 loop pictures");
  p.call(0, 3, 0);
  assert.deepEqual([p.v("len"), p.v("got")], [0, -1], "past the list");
});

test("korg.file.picture reads the list of the last count: a file gone since is -1, an array under 1024 slots a fault", () => {
  const card = mediaCard();
  const p = mediaPlugin(card);
  p.call(0, 0, 0);
  assert.equal(p.v("got"), 1);
  card.delete(media("marker.bmp"));
  p.call(0, 0, 0);
  assert.deepEqual([p.v("len"), p.v("got")], [6, -1], "the name stays in the list, the file is gone");
  const before = new SimDevice();
  const fresh = before.load(build('const pic = new Array(1024); let got = 7; korg.onEvent("buttonPress", (k) => { got = korg.file.picture(pic, 0, 0, 0); });'));
  before.frame();
  before.post("buttonPress", 3);
  before.frame();
  assert.equal(fresh.script.vars[1024], -1, "nothing listed before the first count");
  const small = new SimDevice();
  const short = small.load(build('const pic = new Array(512); korg.onEvent("buttonPress", (k) => { korg.file.picture(pic, 0, 0, 0); });'));
  small.frame();
  small.post("buttonPress", 3);
  small.frame();
  assert.equal(short.script.fault?.code ?? small.status().scripts[0].fault?.code, ERROR.API_ARG);
});
