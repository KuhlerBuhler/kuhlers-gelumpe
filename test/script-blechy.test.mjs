import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { BLECHY_SOURCE } from "../data/script/blechy-source.mjs";
import { FRAMES, FRAME_ORDER } from "../data/script/blechy-art.mjs";
import { LIMITS } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice, probe, FRAME_MS } from "../src/script/sim.mjs";
import { Display } from "../src/script/display.mjs";
import { build, loadFrames } from "../tools/blechy-build.mjs";
import { blechyInputs } from "./support/blechy-inputs.mjs";

const root = new URL("../", import.meta.url);
const source = BLECHY_SOURCE;
const blob = (() => {
  const result = compile(source, { name: "Blechy" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
})();

const frames = loadFrames();
const KEY = { PLAY: 2, STOP: 1, TOUCHPAD: 34, EXIT: 13 };

/** The display the frame `name` leaves: its rows lit at its position plus the offset (ox, oy), nothing else. */
function expected(name, ox = 0, oy = 0) {
  const d = new Display();
  const f = frames[name];
  f.rows.forEach((row, y) => [...row].forEach((c, x) => { if (c === "#") d.pixel(f.x + x + ox, f.y + y + oy, 1); }));
  return d.rows();
}

const litLeft = rows => Math.min(...rows.map(r => (r.includes("#") ? r.indexOf("#") : Infinity)));
const LEFT = Object.fromEntries(FRAME_ORDER.map(n => [n, litLeft(expected(n))]));
/** Where the right edge of every picture he walks and stands in lies at offset 0: how far he can go. */
const WALK_RIGHT = Math.max(...FRAME_ORDER.filter(n => !n.startsWith("flail")).flatMap(n => expected(n).map(r => r.lastIndexOf("#"))));
const DX_MAX = 127 - WALK_RIGHT;

/** Which frame is on the display and where: { name, ox, oy }, or null (a bubble beside him is not part of the match). */
function locate(device, names = FRAME_ORDER, width = 128) {
  const rows = rowsOf(device).map(r => r.slice(0, width));
  const left = litLeft(rows);
  for (const name of names) {
    const ox = left - LEFT[name];
    for (const oy of [0, 1]) {
      if (ox >= 0 && ox <= 100 && same(rows, expected(name, ox, oy).map(r => r.slice(0, width)))) return { name, ox, oy };
    }
  }
  return null;
}

/** An opened device. */
function opened() {
  const device = new SimDevice();
  assert.ok(device.load(blob).ok);
  device.frame();
  assert.ok(device.openApp(0));
  return device;
}

const rowsOf = device => device.display.rows();
const wait = (device, ms) => device.run(Math.ceil(ms / FRAME_MS));
const touch = (device, points, hold = 3) => {
  device.post("buttonPress", KEY.TOUCHPAD);
  for (const [x, y] of points) { device.post("touch", x, y); device.frame(); }
  device.run(hold);
  device.post("buttonRelease", KEY.TOUCHPAD);
  device.frame();
};

test("the source, the fixtures and the preview are what the frame tables make", () => {
  const { files } = build();
  assert.equal(source, files["test/fixtures/scripts/blechy.js"].toString());
  for (const [path, data] of Object.entries(files)) {
    assert.ok(readFileSync(new URL(path, root)).equals(Buffer.from(data)), `${path} is stale: run node tools/blechy-build.mjs`);
  }
});

test("Blechy fits the code and constant limits with room to spare, and the frames are plain tables", () => {
  const parts = decodeBlob(blob);
  assert.ok(parts.ok);
  assert.ok(parts.code.length < LIMITS.code * 0.8, `${parts.code.length} bytes of code`);
  assert.ok(parts.header.constCount <= LIMITS.consts / 2 && parts.header.stringCount <= LIMITS.strings / 2);
  assert.deepEqual(Object.keys(FRAMES), FRAME_ORDER);
  for (const [name, f] of Object.entries(frames)) {
    assert.ok(f.rows.length === 56 && f.rows.every(r => /^[#.]{56}$/.test(r)), `${name} is a 56 x 56 sprite`);
    assert.ok(f.y + f.rows.length <= 64 && f.x + 56 <= 128, `${name} fits the display`);
  }
});

test("closed he draws nothing, opened he stands and draws once, then only when the picture changes", () => {
  const device = new SimDevice();
  assert.ok(device.load(blob).ok);
  assert.deepEqual(device.run(10), []);
  assert.ok(device.display.bytes.every(b => b === 0), "closed, nothing is drawn");
  assert.ok(device.shown.every(b => b === 0));
  assert.ok(device.openApp(0));
  device.frame();
  assert.deepEqual(rowsOf(device), expected("idle"));
  let redraws = 0;
  for (const call of ["clear", "clearRect"]) {
    const original = device.display[call].bind(device.display);
    device.display[call] = (...args) => { redraws += 1; original(...args); };
  }
  wait(device, 900);
  assert.ok(redraws <= 1, `${redraws} redraws in the first second of standing, only the twitch may change it`);
  wait(device, 4000);
  redraws = 0;
  wait(device, 20000);
  assert.ok(redraws > 20 && redraws < 400, `${redraws} redraws in 20 s of walking: a new picture when he has moved a pixel, not every frame`);
});

test("a tap near him makes him angry, then he stands again; a tap far from him does nothing", () => {
  const device = opened();
  device.run(2);
  touch(device, [[160, 500]]);
  assert.deepEqual(rowsOf(device), expected("angry"));
  wait(device, 1400);
  assert.ok(!rowsOf(device).every((r, y) => r === expected("angry")[y]), "angry wears off");
  const far = opened();
  far.run(2);
  const before = rowsOf(far);
  touch(far, [[900, 500]]);
  assert.deepEqual(rowsOf(far), before);
});

test("stroking makes him happy", () => {
  const device = opened();
  device.run(2);
  touch(device, [[100, 500], [160, 500], [220, 520], [280, 500]], 1);
  assert.deepEqual(rowsOf(device), expected("happy"));
  wait(device, 6000);
  assert.ok(!same(rowsOf(device), expected("happy")), "the happy face wears off");
});

const same = (a, b) => a.every((r, y) => r === b[y]);
const WAVE = ["wave0", "wave1"];

test("about a second after he opens he waves, the hand swings every 220 ms, and then he stands again", () => {
  const device = opened();
  const shown = [];
  for (let ms = 0; ms < 5000; ms += FRAME_MS) {
    device.frame();
    shown.push(WAVE.findIndex(n => same(rowsOf(device), expected(n))));
  }
  const first = shown.findIndex(i => i >= 0);
  assert.ok(first * FRAME_MS >= 960 && first * FRAME_MS <= 1100, `the wave starts after ${first * FRAME_MS} ms`);
  const last = shown.length - 1 - [...shown].reverse().findIndex(i => i >= 0);
  assert.ok((last - first + 1) * FRAME_MS >= 1600 && (last - first + 1) * FRAME_MS <= 1900, `the wave takes ${(last - first + 1) * FRAME_MS} ms`);
  const wave = shown.slice(first, last + 1);
  assert.ok(wave.every(i => i >= 0), "no other picture in between");
  const swings = wave.filter((v, i) => i > 0 && v !== wave[i - 1]).length;
  assert.ok(swings >= 6 && swings <= 9, `${swings} swings of the hand`);
  assert.ok(shown.slice(0, first).every(i => i < 0) && shown.slice(last + 1).every(i => i < 0), "he stands before and after");
});

test("he waves once per landing: not again while he stays open, again the next time he opens", () => {
  const device = opened();
  wait(device, 4000);
  const seen = new Set();
  for (let ms = 0; ms < 30000; ms += FRAME_MS) {
    device.frame();
    WAVE.forEach(n => same(rowsOf(device), expected(n)) && seen.add(n));
  }
  assert.equal(seen.size, 0, "no second wave while he stays");
  device.closeApp();
  device.frame();
  assert.ok(device.openApp(0));
  let waved = false;
  for (let ms = 0; ms < 3000; ms += FRAME_MS) {
    device.frame();
    if (WAVE.some(n => same(rowsOf(device), expected(n)))) waved = true;
  }
  assert.ok(waved, "he waves at the next landing");
});

test("a tap during the wait does not cancel the wave, it comes after the anger", () => {
  const device = opened();
  device.run(2);
  touch(device, [[160, 500]]);
  assert.deepEqual(rowsOf(device), expected("angry"));
  let waved = false;
  for (let ms = 0; ms < 4000; ms += FRAME_MS) {
    device.frame();
    if (WAVE.some(n => same(rowsOf(device), expected(n)))) waved = true;
  }
  assert.ok(waved);
});

test("a touch while he is closed counts for nothing", () => {
  const device = new SimDevice();
  device.load(blob);
  device.frame();
  touch(device, [[160, 500]]);
  assert.ok(device.display.bytes.every(b => b === 0));
  device.openApp(0);
  device.frame();
  assert.deepEqual(rowsOf(device), expected("idle"));
});

test("PLAY and STOP reach the firmware while he is open or closed, and he does not press them himself", () => {
  const device = opened();
  device.post("buttonPress", KEY.PLAY);
  device.frame();
  assert.equal(device.hardware.transport, 1);
  device.post("buttonPress", KEY.STOP);
  device.frame();
  assert.equal(device.hardware.transport, 0);
  assert.ok(!source.includes("korg.play()") && !source.includes("korg.stop()"), "the plugin passes no key on");
});

/** The text of a bubble, as lit pixels in the rows and columns it occupies (the box and the tail are not compared). */
const textRows = (lines, x) => {
  const d = new Display();
  lines.forEach(([text, y]) => d.text(text, x, y));
  return d.rows();
};
const region = (rows, x0, x1, y1 = 40) => rows.slice(10, y1).map(r => r.slice(x0, x1));

test("PLAY: he walks to the middle, says he listens, listens, and dances with the steps while it plays", () => {
  const device = opened();
  device.run(2);
  device.post("buttonPress", KEY.PLAY);
  const seen = [];
  let listenAt = null;
  const listen = textRows([["ich hoer", 11], ["mir das", 22], ["kurz an", 33]], 76);
  for (let ms = 0; ms < 20000 && listenAt === null; ms += FRAME_MS) {
    device.frame();
    seen.push(locate(device, ["walk", "idle"])?.ox);
    if (same(region(rowsOf(device), 76, 127), region(listen, 76, 127))) listenAt = ms;
  }
  assert.notEqual(listenAt, null, "the bubble comes");
  const walked = seen.filter(v => v !== undefined);
  assert.ok(walked.length > 5 && walked.every((v, i) => i === 0 || v >= walked[i - 1]), "he walks towards the middle, never back");
  const here = locate(device, ["idle", "twitch"], 70);
  assert.equal(here?.ox, 24, "he stands in the middle, a little left of it so that the bubble fits beside him");
  wait(device, 3000);
  const flail = FRAME_ORDER.filter(n => n.startsWith("flail")).map(n => expected(n, 24).join("\n"));
  const seenFlail = new Set();
  let flips = 0;
  let last = null;
  for (let i = 0; i < 100; i++) {
    device.frame();
    const now = rowsOf(device).join("\n");
    assert.ok(flail.includes(now), "he dances in the middle, flail frames only");
    seenFlail.add(now);
    if (last !== null && now !== last) flips += 1;
    last = now;
  }
  assert.ok(seenFlail.size >= 3, `${seenFlail.size} different poses`);
  assert.ok(flips >= 10 && flips <= 16, `${flips} flips in 4 s at 120 BPM: one per eighth, not per frame`);
});

test("on stop the dance ends and he walks again, no question", () => {
  const device = opened();
  device.post("buttonPress", KEY.PLAY);
  wait(device, 9000);
  device.post("buttonPress", KEY.STOP);
  device.run(2);
  const walking = new Set();
  for (let ms = 0; ms < 3000; ms += FRAME_MS) {
    device.frame();
    const at = locate(device, ["idle", "twitch", "walk", "back0", "back1"]);
    assert.ok(at, `only standing or walking pictures, no bubble, no dance (${ms} ms)`);
    if (at.name === "walk" || at.name.startsWith("back")) walking.add(at.ox);
  }
  assert.ok(walking.size > 5, "he walks on from the middle");
});

test("idle he walks from the left edge to the right edge and back, slowly, with the walk cycle", () => {
  const device = opened();
  const xs = [];
  for (let ms = 0; ms < 45000; ms += FRAME_MS) {
    device.frame();
    const at = locate(device, ["walk", "idle", "twitch", "wave0", "wave1", "back0", "back1"]);
    if (at) xs.push(at.ox);
  }
  const walking = xs.filter(v => v > 0);
  assert.ok(Math.max(...xs) >= DX_MAX - 1 && Math.max(...xs) <= DX_MAX, "he reaches the right edge");
  assert.equal(Math.min(...xs.slice(xs.indexOf(Math.max(...xs)))), 0, "and comes back to the left edge");
  const steps = xs.slice(1).filter((v, i) => v !== xs[i]);
  assert.ok(steps.every((v, i) => i === 0 || Math.abs(v - steps[i - 1]) <= 1), "one pixel at a time");
  assert.ok(walking.length > 200);
  const first = xs.findIndex(v => v > 0);
  assert.ok(first * FRAME_MS > 2500, "not before the wave is over");
});

test("the walk cycle: the calm and the walk picture in turn every 240 ms, mirrored when he goes left, the calm picture when he stands", () => {
  const device = opened();
  const runs = { right: [], left: [] };
  const standing = [];
  let last = null;
  let lastX = -1;
  for (let ms = 0; ms < 60000; ms += FRAME_MS) {
    device.frame();
    const at = locate(device, ["idle", "twitch", "walk", "back0", "back1", "wave0", "wave1"]);
    if (!at) continue;
    const moving = lastX >= 0 && at.ox !== lastX;
    lastX = at.ox;
    if (!moving) {
      if (at.name === "idle" || at.name === "twitch") standing.push(at.name);
      continue;
    }
    if (last?.name !== at.name) {
      if (last) runs[at.name.startsWith("back") ? "left" : "right"].push({ name: at.name, ms: ms - last.ms });
      last = { name: at.name, ms };
    }
  }
  const names = side => [...new Set(runs[side].map(r => r.name))].sort();
  assert.deepEqual(names("right"), ["idle", "walk"], "to the right: the calm and the walk picture");
  assert.deepEqual(names("left"), ["back0", "back1"], "to the left: the same two, mirrored");
  const lengths = [...runs.right, ...runs.left].map(r => r.ms).sort((a, b) => a - b);
  const median = lengths[Math.floor(lengths.length / 2)];
  assert.ok(median >= 200 && median <= 280, `one picture lasts about 240 ms, got ${median}`);
  assert.ok(standing.length > 20, "he also stands between the walks");
});

test("the mirrored pictures are the calm and the walk picture flipped left to right inside one box, so the walk limits do not change", () => {
  const box = rows => rows.reduce((b, r) => (r.includes("#") ? [Math.min(b[0], r.indexOf("#")), Math.max(b[1], r.lastIndexOf("#"))] : b), [999, -1]);
  const [a0, a1] = box([...frames.idle.rows, ...frames.walk.rows]);
  assert.deepEqual(box([...frames.back0.rows, ...frames.back1.rows]), [a0, a1]);
  for (const [back, front] of [["back0", "idle"], ["back1", "walk"]]) {
    frames[front].rows.forEach((row, y) => [...row].forEach((c, x) => {
      assert.equal(frames[back].rows[y][a0 + a1 - x] ?? ".", c, `${back} is ${front} flipped (${x}, ${y})`);
    }));
    assert.notDeepEqual(frames[back].rows, frames[front].rows);
  }
});

test("every now and then he stops at an edge and says something, the bubble on the side with room, and then walks on", () => {
  const device = opened();
  const talks = [];
  let was = false;
  for (let ms = 0; ms < 130000; ms += FRAME_MS) {
    device.frame();
    const rows = rowsOf(device);
    const bubble = rows[8].includes("#".repeat(60));
    if (bubble && !was) talks.push({ at: ms, left: rows[8].indexOf("#".repeat(60)) === 0, rows, figure: locate(device, ["idle", "twitch"].concat([])) });
    was = bubble;
  }
  assert.ok(talks.length >= 4 && talks.length <= 7, `${talks.length} bubbles in 130 s: not too often`);
  assert.ok(talks.every((t, i) => i === 0 || t.at - talks[i - 1].at >= 12000), "at least 12 s apart");
  assert.ok(talks[0].at >= 10000 && talks[0].at <= 14000, `the first one at ${talks[0].at} ms`);
  assert.ok(talks.some(t => t.left) && talks.some(t => !t.left), "at the right edge the bubble is on his left, at the left edge on his right");
  talks.forEach(t => {
    const edge = t.left ? { name: "idle", ox: DX_MAX } : { name: "idle", ox: 0 };
    const mine = [expected("idle", edge.ox), expected("twitch", edge.ox)];
    const away = t.left ? [80, 128] : [0, 49];
    assert.ok(mine.some(m => same(t.rows.map(r => r.slice(...away)), m.map(r => r.slice(...away)))), `he stands at the ${t.left ? "right" : "left"} edge, nothing of the bubble on his side`);
  });
});

test("the lines are a rotation of short texts: yo first, the favourite tempo, how long, and a few more, all in the own font", () => {
  const device = opened();
  device.hardware.tempo = 1400;
  device.post("buttonPress", KEY.PLAY);
  wait(device, 70000);
  device.post("buttonPress", KEY.STOP);
  const shown = [];
  let was = false;
  const lines = {
    yo: x => textRows([["yo", 14], ["na du?", 26]], x),
    tempo: x => textRows([["Lieblings-", 12], ["tempo 140", 26]], x),
    time: x => textRows([["Spielt seit", 12]], x),
  };
  for (let ms = 0; ms < 250000; ms += FRAME_MS) {
    device.frame();
    const rows = rowsOf(device);
    const bubble = rows[8].includes("#".repeat(60));
    if (bubble && !was) {
      const left = rows[8].indexOf("#".repeat(60)) === 0;
      const x = left ? 3 : 56;
      shown.push(Object.fromEntries(Object.entries(lines).map(([k, v]) => [k, same(region(rows, x, x + 71, k === "time" ? 21 : 40), region(v(x), x, x + 71, k === "time" ? 21 : 40))])));
    }
    was = bubble;
  }
  const kinds = Object.keys(lines).filter(k => shown.some(s => s[k]));
  assert.deepEqual(kinds.sort(), ["tempo", "time", "yo"].sort(), `bubbles seen: ${JSON.stringify(shown)}`);
});

test("the stats keep counting while he is closed, and he does not draw", () => {
  const device = opened();
  device.closeApp();
  device.display.clear();
  device.hardware.tempo = 1500;
  device.post("play");
  wait(device, 30000);
  device.post("stop");
  device.frame();
  assert.ok(device.display.bytes.every(b => b === 0), "closed, nothing drawn");
  assert.ok(device.openApp(0));
  device.frame();
  assert.deepEqual(rowsOf(device), expected("idle"), "no bubble when he was closed at the stop");
});

test("the probe with recorded touch and transport inputs passes and covers every line", () => {
  const result = probe(blob, blechyInputs());
  assert.equal(result.ok, true, JSON.stringify(result.faults));
  assert.deepEqual(result.lines.missing, []);
  assert.equal(result.warnings, 0);
});
