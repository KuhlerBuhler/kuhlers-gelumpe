import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { API_BY_NAME, BUDGET, CARD_READS, ERROR, SCRIPT_GIF, SCRIPT_MEDIA } from "../data/script/contract.mjs";
import { PRESETS } from "../data/script/presets.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { Display } from "../src/script/display.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
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
  const p = { device, step: (ms = 40) => { now += ms; device.frame(); }, v: name => loaded.script.vars[r.info.symbols[name].slot] };
  p.press = name => { device.post("buttonPress", key(name)); p.step(); };
  p.turn = delta => { device.post("encoder", 0, delta); p.step(); };
  return p;
}

/** The display a list of draw calls gives, to compare a screen with. */
function screen(draw) {
  const d = new Display();
  draw(d);
  return Array.from(d.bytes).join(",");
}
const shown = p => Array.from(p.device.display.bytes).join(",");
const picture = (bytes, kind, fr) => {
  const slots = new Int32Array(1024);
  readMediaPicture(bytes, kind, fr, slots, true);
  return Array.from(slots, v => v & 255).join(",");
};

test("the Image Viewer lists IMAGES and ANIMATIONS of Media/, pages through the files, steps and plays an animation", () => {
  const card = mediaCard();
  const p = viewer(card);
  assert.deepEqual([p.v("mode"), p.v("n0"), p.v("n1")], [0, 3, 2], "three .bmp and two .blla in Media/");
  assert.equal(shown(p), screen(d => { d.textNumber("IMAGES ", 3, 12, 18); d.textNumber("ANIMATIONS ", 2, 12, 32); d.text(">", 4, 18); }));
  p.turn(1);
  assert.equal(p.v("sel"), 1);
  p.press("PART_LEFT");
  assert.equal(p.v("sel"), 0);

  // IMAGES: the name and the place for two seconds, then the picture alone
  p.press("MENU");
  assert.deepEqual([p.v("mode"), p.v("file")], [1, 0]);
  const marker = picture(card.get(media("marker.bmp")), 0, 0);
  assert.notEqual(shown(p), marker, "the name covers the top");
  p.step(2000);
  assert.equal(shown(p), marker);
  p.turn(1);
  p.step(2000);
  assert.equal(p.v("file"), 1);
  assert.equal(shown(p), picture(card.get(media("top-down-picture-long.bmp")), 0, 0));
  p.press("PART_RIGHT");
  assert.equal(p.v("file"), 2);
  assert.ok(p.v("total") < 0, "broken.bmp is a 24 bit picture");
  const name = [...mediaNameBytes("broken"), 0];
  assert.equal(shown(p), screen(d => { d.chars(name, 4, 18, 17); d.text("BAD FILE", 4, 32); }));
  p.press("PART_RIGHT");
  p.step(2000);
  assert.equal(p.v("file"), 0, "past the last file comes the first");
  assert.equal(shown(p), marker);
  p.press("PART_LEFT");
  assert.equal(p.v("file"), 2, "back from the first goes to the last");
  p.turn(-2);
  assert.equal(p.v("file"), 0);
  p.press("TAP");
  p.step(5000);
  assert.notEqual(shown(p), marker, "TAP keeps the name");
  p.press("TAP");
  assert.equal(shown(p), marker, "a second TAP hides it");

  // ANIMATIONS: step, wrap, play at 96 ms, change the speed, pause
  p.press("MENU");
  assert.equal(p.v("mode"), 0, "MENU goes back to the list");
  p.turn(1);
  p.press("MENU");
  assert.deepEqual([p.v("mode"), p.v("file"), p.v("frame")], [2, 0, 0]);
  p.turn(1);
  const small = card.get(media("small.blla"));
  assert.deepEqual([p.v("file"), p.v("frame"), p.v("total")], [1, 0, 5], "3 progress and 2 loop pictures");
  p.step(2000);
  assert.equal(shown(p), picture(small, 1, 0));
  p.press("PART_RIGHT");
  p.step(2000);
  assert.equal(p.v("frame"), 1);
  assert.equal(shown(p), picture(small, 1, 1));
  p.press("PART_LEFT");
  p.press("PART_LEFT");
  p.step(2000);
  assert.equal(p.v("frame"), 4, "back from the first picture goes to the last");
  assert.equal(shown(p), picture(small, 1, 4));
  p.press("PART_RIGHT");
  assert.equal(p.v("frame"), 0);
  p.press("TAP");
  assert.equal(p.v("playing"), 1);
  const seen = [];
  for (let i = 0; i < 6; i++) {
    p.step(96);
    seen.push(p.v("frame"));
  }
  assert.deepEqual(seen, [1, 2, 3, 4, 0, 1], "a picture every 96 ms, after the last the first again");
  p.step(2000);
  const at = p.v("frame");
  assert.equal(shown(p), picture(small, 1, at), "the place goes away while it plays");
  p.press("PART_RIGHT");
  assert.equal(p.v("ms"), 48, "Part right plays twice as fast");
  p.press("PART_LEFT");
  p.press("PART_LEFT");
  p.press("PART_LEFT");
  p.press("PART_LEFT");
  assert.equal(p.v("ms"), 384, "and stops at 384 ms");
  p.press("TAP");
  const paused = p.v("frame");
  p.step(2000);
  assert.deepEqual([p.v("playing"), p.v("frame")], [0, paused], "TAP pauses");
  assert.equal(p.device.status().scripts[0].fault ?? null, null);
});

test("the Image Viewer says NO IMAGES, NO ANIMATIONS and NO CARD", () => {
  const p = viewer(new Map([["KORG/blechtribe/splash.bmp", new Uint8Array(10)]]));
  assert.deepEqual([p.v("n0"), p.v("n1")], [0, 0], "a picture outside Media/ does not count");
  p.press("MENU");
  assert.equal(shown(p), screen(d => d.text("NO IMAGES", 4, 26)));
  p.turn(1);
  p.press("PART_RIGHT");
  p.press("TAP");
  assert.equal(shown(p), screen(d => d.text("NO IMAGES", 4, 26)), "nothing to page through");
  p.press("MENU");
  p.turn(1);
  p.press("MENU");
  assert.equal(shown(p), screen(d => d.text("NO ANIMATIONS", 4, 26)));
  p.press("TAP");
  assert.equal(p.v("playing"), 0);
  const none = viewer(null);
  assert.equal(none.v("n0"), -1);
  assert.equal(shown(none), screen(d => d.text("NO CARD", 4, 26)));
  none.press("MENU");
  assert.equal(none.v("mode"), 0, "with no card MENU stays on the list");
  for (const q of [p, none]) assert.equal(q.device.status().scripts[0].fault ?? null, null);
});

test("no Image Viewer handler costs more than the warning line of 0.5 ms besides drawing the picture", () => {
  const near = i => { const f = frameOf(3); f[i * 4] ^= 0xff; return f; };
  const big = encodeAnimation({ progress: Array.from({ length: 200 }, (_, i) => near(i)), loop: Array.from({ length: 55 }, (_, i) => near(i + 200)) }).bytes;
  const card = mediaCard();
  card.set(media("zz-big.blla"), big);
  const p = viewer(card);
  p.press("MENU");
  for (const n of [1, 1, 1]) p.turn(n);
  p.press("PART_RIGHT");
  p.press("PART_LEFT");
  p.press("PART_LEFT");
  p.press("MENU");
  p.turn(1);
  p.press("MENU");
  p.turn(2);
  assert.equal(p.v("total"), 255, "the most pictures a .blla holds");
  p.press("PART_LEFT");
  assert.equal(p.v("frame"), 254, "the jump back to the last picture of a big BLLA");
  p.press("TAP");
  for (let i = 0; i < 70; i++) p.step(48);
  p.press("TAP");
  // The warning line in units is derived (docs/plugins.md, Snake: 542 units in 0.103 ms). A whole-display korg.display.bitmap
  // alone is 14 + 3 x 1024 units, above it, as in the GIF Player; the emulator draws it in far less (docs/plugins.md), so
  // everything else a handler does has to stay under the line.
  const warn = Math.floor(542 * BUDGET.handlerWarnMs / 0.103);
  const bitmap = API_BY_NAME.get("korg.display.bitmap");
  const picture = bitmap.cost + 1024 * bitmap.perItem;
  for (const [handler, units] of Object.entries(p.device.status().scripts[0].maxCost)) {
    assert.ok(units - picture <= warn, `${handler} costs ${units} units, ${units - picture} without the picture, the warning line is ${warn}`);
  }
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
        // DISPLAY INVERT is ON from the factory, so the bits come turned
        assert.equal(p.v("got"), readMediaPicture(bytes, kind, fr, want, true), `${entry.name} picture ${fr}`);
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

test("a card read does not count against the frame budget, up to CARD_READS.cardMs a frame", () => {
  let ms = 0;
  const card = name => (...args) => { ms += 9; return name === "korg.file.picture" && args.length === 4 ? 1 : 0; };
  const api = Object.fromEntries(CARD_READS.calls.map(name => [name, card(name)]));
  const run = source => {
    const rt = new ScriptRuntime({ api, now: () => ms });
    const r = compile(source, { name: "budget" });
    assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
    assert.ok(rt.add(r.blob).ok);
    for (let i = 0; i < 30; i++) rt.frame();
    return rt.status().scripts[0];
  };
  const every = run(`const pic = new Array(1024); let got = 0;
korg.onEvent("frame", () => { got = korg.file.picture(pic, 0, 0, 0); korg.file.frame(pic, 0, 0); korg.file.count(0); });`);
  assert.equal(every.state, "armed", "27 ms of card reads in each frame, 5 ms budget");
  assert.equal(every.slowHandlers, 0, `nothing over ${BUDGET.handlerWarnMs} ms`);
  const many = run(`const pic = new Array(1024);
korg.onEvent("frame", () => { for (let i = 0; i < 10; i = i + 1) { korg.file.picture(pic, 0, 0, 0); } });`);
  assert.equal(many.state, "disabled", `90 ms of card reads in one frame, ${CARD_READS.cardMs} ms left out`);
  assert.equal(many.fault.name, "TIME");
});
