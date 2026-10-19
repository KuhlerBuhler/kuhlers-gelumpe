import { test } from "node:test";
import assert from "node:assert/strict";
import { PRESETS } from "../data/script/presets.mjs";
import { LIMITS } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { Display } from "../src/script/display.mjs";
import { KEY_NAMES, LED_NAMES } from "../data/script/names.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;
/** 0.5 ms, the warning line for one handler, in cost units: the Snake frame measured 0.103 ms for 542 units (docs/messungen/2026-10-14-skript-snake.md). */
const WARN_UNITS = Math.floor(542 * 0.5 / 0.103);
const IDS = ["blechclicker", "settimer", "tetris", "life", "pong", "simon", "mandelbrot"];

function plugin(id, { open = true, storage = null } = {}) {
  const preset = PRESETS.find(p => p.id === id);
  const result = compile(preset.source, { name: id });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const device = new SimDevice({ storage });
  const loaded = device.load(result.blob);
  assert.ok(loaded.ok, loaded.error?.message);
  if (open) assert.ok(device.openApp(0));
  const sym = result.info.symbols;
  const vars = loaded.script.vars;
  return {
    device,
    blob: result.blob,
    info: result.info,
    v: name => vars[sym[name].slot],
    set: (name, value) => { vars[sym[name].slot] = value; },
    at: (name, i) => vars[sym[name].slot + i],
    put: (name, i, value) => { vars[sym[name].slot + i] = value; },
    cost: () => device.status().scripts[0].maxCost,
    resetCost: () => { device.runtime.scripts[0].maxCost = {}; },
  };
}
const press = (p, name, frames = 1) => { p.device.post("buttonPress", key(name)); p.device.run(frames); };
const release = (p, name, frames = 1) => { p.device.post("buttonRelease", key(name)); p.device.run(frames); };
const pixel = (device, x, y) => (device.display.bytes[(y >> 3) * 128 + x] >> (y & 7)) & 1;
const noFault = faults => assert.deepEqual(faults, []);
const withinWarn = (p, what) => {
  for (const [handler, units] of Object.entries(p.cost())) assert.ok(units <= WARN_UNITS, `${what} ${handler} costs ${units} units, the warning line is ${WARN_UNITS}`);
};

test("the new plugins are in the catalog, Klicker is not, and each is an app that compiles inside the limits", () => {
  const ids = PRESETS.map(p => p.id);
  for (const id of IDS) assert.ok(ids.includes(id), id);
  assert.ok(!ids.includes("klicker") && !ids.includes("klickerstore"));
  for (const id of IDS) {
    const p = plugin(id, { open: false });
    assert.ok(p.blob.length < 16 * 1024, `${id}: ${p.blob.length} bytes`);
    assert.ok(p.info.vars <= LIMITS.vars);
    assert.equal(p.device.apps.length, 1, id);
    assert.match(PRESETS.find(x => x.id === id).description, /^App in (GAMES|TOOLS):/);
  }
  assert.deepEqual(IDS.map(id => plugin(id, { open: false }).device.apps[0].group), ["GAMES", "TOOLS", "GAMES", "GAMES", "GAMES", "GAMES", "GAMES"]);
});

test("every new plugin draws something right after it opens and stays inside the handler budget", () => {
  for (const id of IDS) {
    const p = plugin(id);
    noFault(p.device.run(60));
    assert.ok(p.device.display.bytes.some(b => b), `${id} draws`);
    withinWarn(p, id);
  }
});

// ---- Set-Timer ----

const digitsOf = p => [1, 2, 3, 4].map(i => p.at("shown", i));

test("Set-Timer waits for the first PLAY, then counts with the app closed, and PLAY and STOP change nothing", () => {
  const p = plugin("settimer", { open: false });
  p.device.run(100);
  assert.equal(p.v("started"), 0, "it does not start by itself");
  p.device.post("buttonPress", key("STOP"));
  p.device.run(25);
  assert.equal(p.v("started"), 0, "STOP does not start it");
  p.device.post("buttonPress", key("PLAY"));
  assert.equal(p.device.hardware.transport, 1, "the key still reaches the transport");
  p.device.run(25 * 65 + 3);
  assert.equal(p.v("started"), 1);
  p.device.post("buttonPress", key("STOP"));
  p.device.run(25 * 10);
  p.device.post("buttonPress", key("PLAY"));
  p.device.run(25 * 10);
  assert.equal(p.device.hardware.transport, 1);
  assert.ok(p.device.openApp(0));
  p.device.run(3);
  assert.deepEqual(digitsOf(p), [0, 1, 2, 5], "65 + 20 seconds: 01:25, counted while it was closed and over STOP and PLAY");
  assert.equal(p.cost().frame <= WARN_UNITS, true);
});

test("Set-Timer draws each digit as a seven-segment shape, the same whether it counted on screen or was opened later", () => {
  const live = plugin("settimer");
  live.device.run(5);
  live.device.post("buttonPress", key("BAR_1"));
  live.device.run(25 * 754 + 4);
  const later = plugin("settimer", { open: false });
  later.device.post("buttonPress", key("PLAY"));
  later.device.run(25 * 754 + 4);
  later.device.openApp(0);
  later.device.run(3);
  assert.deepEqual(digitsOf(live), [1, 2, 3, 4], "12:34");
  assert.deepEqual(digitsOf(later), digitsOf(live));
  const picture = device => device.display.rows().slice(16, 48).join("\n");
  assert.equal(picture(live.device), picture(later.device));
  // The one at the left of the seconds: only the right-hand segments b and c are lit; the 8 has all of them.
  const x = live.at("DX", 1);
  assert.equal(pixel(live.device, x + 14, 20), 1);
  assert.equal(pixel(live.device, x + 14, 40), 1);
  assert.equal(pixel(live.device, x + 1, 20), 0, "a one has no left segments");
  assert.equal(pixel(live.device, x + 8, 17), 0, "and no top bar");
});

test("Set-Timer goes to h:mm:ss after an hour and a key resets it only after a second press", () => {
  const p = plugin("settimer");
  p.device.post("buttonPress", key("PLAY"));
  p.device.run(25 * 3600 + 25 * 61 + 4);
  assert.deepEqual([p.v("longMode"), p.at("shown", 0), ...digitsOf(p)], [1, 1, 0, 1, 0, 1], "1:01:01");
  press(p, "BAR_4", 3);
  assert.equal(p.v("started"), 1, "the first press only asks");
  assert.ok(p.v("confirmUntil") > 0);
  press(p, "BAR_4", 3);
  assert.equal(p.v("started"), 0, "the second press resets");
  p.device.run(3);
  assert.deepEqual(digitsOf(p), [0, 0, 0, 0]);
  press(p, "BAR_4", 3);
  p.device.run(25 * 4);
  assert.equal(p.v("confirmUntil"), 0, "an unanswered question is dropped after 3 seconds");
  p.device.post("buttonPress", key("STOP"));
  p.device.post("buttonPress", key("PLAY"));
  p.device.run(25 * 5 + 6);
  assert.equal(p.at("shown", 4), 5, "the next PLAY starts it again");
});

test("Set-Timer costs nothing per frame while closed and next to nothing while a second goes by", () => {
  const p = plugin("settimer", { open: false });
  p.device.post("buttonPress", key("PLAY"));
  p.device.run(200);
  assert.equal(p.cost().frame, undefined, "a closed app gets no frame");
  p.device.run(25 * 300);
  assert.equal(p.cost().frame, undefined);
  p.device.openApp(0);
  p.device.run(10);
  p.resetCost();
  p.device.run(8);
  assert.ok(p.cost().frame < 400, `a frame without a change costs ${p.cost().frame} units`);
  p.device.run(25 * 20);
  assert.ok(p.cost().frame <= WARN_UNITS, `the worst frame (a digit changes) costs ${p.cost().frame}`);
  p.device.post("buttonPress", key("PLAY"));
  p.device.post("pad", 3, 1, 100);
  p.device.post("pad", 3, 0, 0);
  p.device.run(50);
  assert.equal(p.cost().pad, undefined, "it has no pad handler");
});

// ---- BLECH Clicker ----

test("BLECH Clicker counts pad presses while it is open, shows the number below the crystal and keeps it", () => {
  const saved = [];
  const p = plugin("blechclicker", { storage: { load: name => (name === "blechclicker" ? { mask: 1, values: [41] } : null), save: records => saved.push(records) } });
  p.device.run(2);
  assert.equal(p.v("count"), 41, "it starts from the stored count");
  p.device.post("pad", 5, 1, 90);
  p.device.post("pad", 5, 0, 0);
  p.device.post("pad", 9, 1, 90);
  p.device.run(2);
  assert.equal(p.v("count"), 43, "a press counts, a release does not");
  p.device.run(60);
  const expected = new Display();
  expected.number(43, 64 - 2 * 3, 50);
  assert.equal(p.device.display.rows().slice(50, 57).join("\n"), expected.rows().slice(50, 57).join("\n"));
  let crystal = 0;
  for (let y = 4; y < 44; y++) for (let x = 44; x < 84; x++) crystal += pixel(p.device, x, y);
  assert.ok(crystal > 150, `the crystal is in the middle: ${crystal} pixels`);
  assert.equal(pixel(p.device, 20, 20) + pixel(p.device, 100, 20), 0, "and nothing beside it");
  assert.equal(saved.at(-1)?.find(r => r.name === "blechclicker").values[0], 43, "the count is handed to korg.store");
  p.device.closeApp();
  p.device.post("pad", 5, 1, 90);
  p.device.run(2);
  assert.equal(p.v("count"), 43, "closed, it does not count");
  withinWarn(p, "clicker");
});

test("BLECH Clicker shakes the crystal for a few frames after a press and then holds still", () => {
  const p = plugin("blechclicker");
  p.device.run(5);
  const still = p.device.display.rows().slice(0, 44).join("\n");
  p.device.post("pad", 1, 1, 90);
  p.device.run(1);
  const shaken = p.device.display.rows().slice(0, 44).join("\n");
  assert.notEqual(shaken, still);
  p.device.run(10);
  assert.equal(p.device.display.rows().slice(0, 44).join("\n"), still);
});

// ---- Tetris ----

test("Tetris clears a full row: the stack drops, score and lines count, and the picture is redrawn from the board", () => {
  const p = plugin("tetris");
  p.device.run(8);
  assert.equal(p.v("state"), 0);
  for (let x = 0; x < 9; x++) p.put("board", 15 * 10 + x, 1);
  p.set("kind", 0);
  p.set("rot", 1);
  p.set("px", 7);
  p.set("py", 11);
  p.set("timer", 0);
  const limit = 20;
  for (let i = 0; i < limit * 8 && p.v("lines") == 0; i++) noFault(p.device.run(1));
  p.device.run(30);
  assert.equal(p.v("lines"), 1);
  assert.ok(p.v("score") > 0);
  const board = Array.from({ length: 160 }, (_, i) => p.at("board", i));
  assert.equal(board.slice(150).join(""), "0000000001", "what was above the cleared row is now the bottom row");
  assert.equal(board.reduce((a, b) => a + b, 0), 3, "the three cells of the I piece that stood above the row are left");
  for (let y = 2; y < 16; y++) {
    for (let x = 0; x < 10; x++) assert.equal(pixel(p.device, 6 + 4 * x + 1, 4 * y + 1), board[y * 10 + x], `cell ${x},${y}`);
  }
  withinWarn(p, "tetris");
});

test("Tetris moves, turns and drops a piece with the keys, keeps it inside the walls and ends the game when the stack is full", () => {
  const p = plugin("tetris");
  p.device.run(8);
  p.set("kind", 2);
  p.set("rot", 0);
  p.set("px", 3);
  p.set("py", 0);
  p.set("timer", 0);
  press(p, "PART_RIGHT", 2);
  assert.equal(p.v("px"), 4);
  press(p, "PART_LEFT", 2);
  press(p, "PART_LEFT", 2);
  assert.equal(p.v("px"), 2);
  for (let i = 0; i < 6; i++) press(p, "PART_LEFT", 2);
  assert.equal(p.v("px"), 0, "the wall stops it, the T mask starts in column 0");
  press(p, "EDIT_RIGHT", 2);
  assert.equal(p.v("rot"), 1);
  press(p, "EDIT_LEFT", 1);
  const before = p.v("py");
  p.device.run(8);
  assert.ok(p.v("py") >= before + 3, "held, EDIT left drops it faster than gravity");
  release(p, "EDIT_LEFT", 1);
  // a stack up to the spawn rows ends the game
  for (let i = 0; i < 160; i++) p.put("board", i, 1);
  p.set("state", 5);
  p.device.run(3);
  assert.equal(p.v("state"), 2);
  const text = new Display();
  text.text("GAME OVER", 54, 55);
  assert.equal(p.device.display.rows().slice(55, 62).map(r => r.slice(54, 110)).join("\n"), text.rows().slice(55, 62).map(r => r.slice(54, 110)).join("\n"));
  press(p, "TAP", 6);
  assert.equal(p.v("state"), 0, "a key starts a new game");
  assert.equal(Array.from({ length: 160 }, (_, i) => p.at("board", i)).reduce((a, b) => a + b, 0), 0);
});

test("Tetris plays 4000 frames of mixed input without a fault and every frame stays under the warning line", () => {
  const p = plugin("tetris");
  const keys = ["PART_LEFT", "PART_RIGHT", "EDIT_RIGHT", "EDIT_LEFT", "TAP"];
  for (let f = 0; f < 4000; f++) {
    if (f % 6 == 0) p.device.post("buttonPress", key(keys[(f / 6 | 0) % 5]));
    if (f % 5 == 0) p.device.post("buttonRelease", key("EDIT_LEFT"));
    noFault(p.device.run(1));
  }
  withinWarn(p, "tetris");
});

// ---- Game of Life ----

const cellAt = (p, col, row) => (p.at("cur", row) >> col) & 1;
const touchCell = (p, col, row, first = 1) => p.device.post("touch", col * 32 + 16, (15 - row) * 64 + 32, first);
const settle = p => { for (let i = 0; i < 60; i++) p.device.run(1); };

test("Life: a touch sets the cell under the finger, a blinker oscillates and wraps around the edge", () => {
  const p = plugin("life");
  press(p, "BAR_1", 2);
  assert.equal(p.v("running"), 0, "key 1 pauses");
  press(p, "BAR_3", 2);
  assert.deepEqual(Array.from({ length: 16 }, (_, i) => p.at("cur", i)).filter(Boolean), [], "key 3 clears");
  touchCell(p, 5, 5);
  touchCell(p, 6, 5, 0);
  touchCell(p, 7, 5, 0);
  p.device.run(8);
  assert.deepEqual([cellAt(p, 4, 5), cellAt(p, 5, 5), cellAt(p, 6, 5), cellAt(p, 7, 5), cellAt(p, 8, 5)], [0, 1, 1, 1, 0]);
  assert.equal(pixel(p.device, 5 * 4 + 1, 5 * 4 + 1), 1, "and the cell is drawn");
  assert.equal(pixel(p.device, 4 * 4 + 1, 5 * 4 + 1), 0);
  press(p, "BAR_2", 40);
  assert.deepEqual([cellAt(p, 6, 4), cellAt(p, 6, 5), cellAt(p, 6, 6), cellAt(p, 5, 5), cellAt(p, 7, 5)], [1, 1, 1, 0, 0], "one step: the blinker stands up");
  assert.equal(pixel(p.device, 6 * 4 + 1, 4 * 4 + 1), 1);
  assert.equal(pixel(p.device, 5 * 4 + 1, 5 * 4 + 1), 0);
  press(p, "BAR_2", 40);
  assert.deepEqual([cellAt(p, 5, 5), cellAt(p, 6, 5), cellAt(p, 7, 5), cellAt(p, 6, 4), cellAt(p, 6, 6)], [1, 1, 1, 0, 0], "two steps: back");
  settle(p);
  assert.equal(Array.from({ length: 16 }, (_, i) => p.at("cur", i)).filter(Boolean).length, 1, "paused, nothing else moves");
  press(p, "BAR_3", 2);
  touchCell(p, 31, 3);
  touchCell(p, 0, 3, 0);
  touchCell(p, 1, 3, 0);
  p.device.run(4);
  press(p, "BAR_2", 40);
  assert.deepEqual([cellAt(p, 0, 2), cellAt(p, 0, 3), cellAt(p, 0, 4), cellAt(p, 31, 3), cellAt(p, 1, 3)], [1, 1, 1, 0, 0], "the blinker across the edge is the same blinker on the other side");
});

test("Life runs by itself, a glider crosses the torus back to where it was, and a closed app ignores the touchpad", () => {
  const p = plugin("life");
  press(p, "BAR_3", 2);
  for (const [c, r] of [[1, 0], [2, 1], [0, 2], [1, 2], [2, 2]]) touchCell(p, c, r, 0);
  p.device.run(4);
  const shapeAt = (dx, dy) => [[1, 0], [2, 1], [0, 2], [1, 2], [2, 2]].every(([c, r]) => cellAt(p, (c + dx) % 32, (r + dy) % 16));
  assert.ok(shapeAt(0, 0));
  assert.equal(p.v("running"), 1);
  let frames = 0;
  while (!shapeAt(1, 1) && frames < 600) { p.device.run(1); frames += 1; }
  assert.ok(frames < 600, "four generations move a glider by one cell diagonally");
  while (!shapeAt(16, 16 % 16) && frames < 20000) { p.device.run(1); frames += 1; }
  assert.ok(shapeAt(16, 0), "after 64 generations the glider is 16 cells to the right on a torus of 16 rows");
  p.device.closeApp();
  const before = Array.from({ length: 16 }, (_, i) => p.at("cur", i)).join();
  p.set("running", 0);
  touchCell(p, 20, 10);
  p.device.run(5);
  assert.equal(Array.from({ length: 16 }, (_, i) => p.at("cur", i)).join(), before, "closed: the touch changes nothing");
  assert.equal(p.device.leds[LED_NAMES.find(l => l.name === "BAR_1").value], 0, "closing turns the key LED off");
});

test("Life: key 4 fills the grid with random cells, and the picture follows the grid within a few frames", () => {
  const p = plugin("life");
  press(p, "BAR_1", 1);
  press(p, "BAR_4", 1);
  p.device.run(300);
  const rows = Array.from({ length: 16 }, (_, i) => p.at("cur", i));
  const alive = rows.reduce((n, r) => { let c = 0; for (let x = 0; x < 32; x++) c += (r >> x) & 1; return n + c; }, 0);
  assert.ok(alive > 60 && alive < 250, `${alive} cells`);
  for (let y = 0; y < 16; y++) for (let x = 0; x < 32; x++) assert.equal(pixel(p.device, 4 * x + 1, 4 * y + 1), (rows[y] >> x) & 1, `cell ${x},${y}`);
  withinWarn(p, "life");
  p.set("running", 1);
  noFault(p.device.run(600));
  withinWarn(p, "life");
});

function nextLife(rows) {
  return rows.map((row, y) => {
    let next = 0;
    for (let x = 0; x < 32; x++) {
      let neighbours = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if (dx || dy) neighbours += (rows[(y + dy + 16) % 16] >>> ((x + dx + 32) % 32)) & 1;
      }
      if (neighbours === 3 || neighbours === 2 && ((row >>> x) & 1)) next |= 1 << x;
    }
    return next;
  });
}

function seedLife(rows) {
  const p = plugin("life");
  noFault(p.device.run(1));
  p.set("running", 0);
  press(p, "BAR_3", 1);
  for (let y = 0; y < 16; y++) p.put("cur", y, rows[y]);
  p.set("idle", 0);
  p.resetCost();
  return p;
}

function lifePicture(p) {
  for (let y = 0; y < 64; y++) for (let x = 0; x < 128; x++) {
    const on = x % 4 < 3 && y % 4 < 3 ? cellAt(p, x >> 2, y >> 2) : 0;
    assert.equal(pixel(p.device, x, y), on, `Life pixel ${x},${y}`);
  }
}

test("Life paints a dense grid and its extinction in bounded frames without residual pixels", () => {
  const p = seedLife(Array(16).fill(-1));
  noFault(p.device.run(10));
  assert.deepEqual(Array.from({ length: 16 }, (_, y) => p.at("shown", y)), Array(16).fill(-1));
  lifePicture(p);
  press(p, "BAR_2", 15);
  assert.deepEqual(Array.from({ length: 16 }, (_, y) => p.at("cur", y)), Array(16).fill(0));
  assert.deepEqual(Array.from({ length: 16 }, (_, y) => p.at("shown", y)), Array(16).fill(0));
  lifePicture(p);
  withinWarn(p, "Life dense paint and extinction");
});

test("Life advances sparse and dense worlds faster and preserves every reference generation", () => {
  let seed = 17;
  const rand = () => { seed = (Math.imul(seed, 1103515245) + 12345) | 0; return seed; };
  for (const [name, initial, limit] of [
    ["glider", Array.from({ length: 16 }, (_, y) => [2, 4, 7][y] || 0), 100],
    ["soup", Array.from({ length: 16 }, () => rand() & rand()), 250],
  ]) {
    const p = seedLife(initial);
    p.set("running", 1);
    let current = initial;
    let generations = 0;
    let frames = 0;
    while (generations < 20 && frames < limit) {
      noFault(p.device.run(1));
      frames += 1;
      const rows = Array.from({ length: 16 }, (_, y) => p.at("cur", y));
      if (rows.some((row, y) => row !== current[y])) {
        assert.deepEqual(rows, nextLife(current), `${name} generation ${generations + 1}`);
        current = rows;
        generations += 1;
      }
    }
    assert.equal(generations, 20, `${name}: only ${generations} generations within ${limit} frames`);
    p.set("running", 0);
    noFault(p.device.run(40));
    lifePicture(p);
    withinWarn(p, `Life ${name}`);
  }
});

// ---- Pong ----

test("Pong: the ball bounces off the walls and off a paddle, and a miss is a point for the other side; the ball moves on every second frame", () => {
  const p = plugin("pong");
  p.device.run(40);
  assert.equal(p.v("state"), 1, "the ball is served after a short wait");
  const x0 = p.v("bx");
  p.device.run(2);
  assert.equal(Math.abs(p.v("bx") - x0), 12, "two frames are one step of three pixels");
  p.set("bx", 60 * 4);
  p.set("by", 1 * 4);
  p.set("vx", 8);
  p.set("vy", -6);
  p.device.run(2);
  assert.ok(p.v("vy") > 0, "the top wall turns it round");
  p.set("by", 58 * 4);
  p.set("vy", 10);
  p.device.run(2);
  assert.ok(p.v("vy") < 0, "so does the bottom wall");
  p.set("py", 20);
  p.set("bx", 9 * 4);
  p.set("by", 25 * 4);
  p.set("vx", -10);
  p.set("vy", 0);
  p.device.run(2);
  assert.ok(p.v("vx") > 0, "the paddle returns it");
  assert.ok(p.v("vx") >= 10, "and a little faster");
  p.set("py", 0);
  p.set("bx", 6 * 4);
  p.set("by", 45 * 4);
  p.set("vx", -12);
  p.device.run(8);
  assert.equal(p.v("botScore"), 1, "a miss on the left is the bot's point");
  assert.equal(p.v("state"), 0);
  p.device.run(40);
  assert.equal(p.v("state"), 1, "and the next ball is served");
});

test("Pong keeps two previous ball positions across fast moves and clears the trail on a point and restart", () => {
  const p = plugin("pong");
  noFault(p.device.run(1));
  p.set("state", 1);
  p.set("tick", 1);
  p.set("bx", 40 * 4);
  p.set("by", 40 * 4);
  p.set("vx", 22);
  p.set("vy", 0);
  noFault(p.device.run(1));
  noFault(p.device.run(4));
  assert.equal(pixel(p.device, 41, 41), 1, "the first position stays lit for three movement steps");
  assert.equal(pixel(p.device, 46, 41), 1, "the intermediate position is visible too");
  assert.equal(pixel(p.device, 52, 41), 1, "the current ball is still drawn");
  noFault(p.device.run(2));
  assert.equal(pixel(p.device, 41, 41), 0, "the oldest position expires");
  assert.equal(pixel(p.device, 46, 41), 1, "the trail follows the ball");
  p.set("bx", 126 * 4);
  noFault(p.device.run(2));
  assert.equal(p.v("state"), 0);
  for (let y = 40; y < 43; y++) for (let x = 40; x < 60; x++) assert.equal(pixel(p.device, x, y), 0, "a point removes the complete trail");
  noFault(p.device.run(30));
  for (let y = 40; y < 43; y++) for (let x = 40; x < 60; x++) assert.equal(pixel(p.device, x, y), 0, "a serve never reuses the previous trail");
  p.set("state", 2);
  press(p, "TAP", 1);
  assert.equal(p.v("state"), 0);
  for (let y = 40; y < 43; y++) for (let x = 40; x < 60; x++) assert.equal(pixel(p.device, x, y), 0, "a restart clears the trail");
  withinWarn(p, "Pong trail");
});

test("Pong: touchpad, Part keys and encoder move the paddle, the paddle stays on the screen", () => {
  const p = plugin("pong");
  p.device.post("touch", 500, 1023, 1);
  p.device.run(1);
  assert.equal(p.v("py"), 0, "finger at the top of the pad");
  p.device.post("touch", 500, 0, 0);
  p.device.run(1);
  assert.equal(p.v("py"), 50, "finger at the bottom");
  p.device.post("touch", 500, 512, 0);
  p.device.run(1);
  assert.ok(Math.abs(p.v("py") - 25) <= 1);
  const held = p.v("py");
  p.device.post("buttonPress", key("PART_LEFT"));
  p.device.run(3);
  assert.equal(p.v("py"), held - 9, "held, Part left moves up three pixels a frame");
  p.device.post("buttonRelease", key("PART_LEFT"));
  p.device.post("buttonPress", key("PART_RIGHT"));
  p.device.run(40);
  assert.equal(p.v("py"), 50, "and Part right down to the stop");
  p.device.post("buttonRelease", key("PART_RIGHT"));
  p.device.post("encoder", 0, -4);
  p.device.run(1);
  assert.equal(p.v("py"), 38);
});

test("Pong: first to 9 wins and the result is shown, a key starts a new game", () => {
  const p = plugin("pong");
  p.device.run(2);
  p.set("botScore", 8);
  p.set("state", 1);
  p.set("py", 0);
  p.set("bx", 6 * 4);
  p.set("by", 45 * 4);
  p.set("vx", -12);
  p.device.run(8);
  assert.equal(p.v("state"), 2);
  assert.equal(p.v("botScore"), 9);
  const text = new Display();
  text.text("BOT WINS", 40, 30);
  const rows = p.device.display.rows();
  for (let y = 30; y < 37; y++) for (let x = 40; x < 90; x++) if (text.get(x, y)) assert.equal(rows[y][x], "#", `text pixel ${x},${y}`);
  press(p, "TAP", 2);
  assert.deepEqual([p.v("myScore"), p.v("botScore"), p.v("state")], [0, 0, 0]);
});

test("Pong: the bot can be beaten, a player who returns with the edge of the paddle scores against it", () => {
  const p = plugin("pong");
  let best = 0;
  for (let f = 0; f < 12000 && best < 9; f++) {
    const ball = p.v("by") >> 2;
    p.set("py", Math.min(50, Math.max(0, ball - 12)));
    noFault(p.device.run(1));
    best = Math.max(best, p.v("myScore"));
    if (p.v("state") == 2) p.device.post("buttonPress", key("TAP"));
  }
  assert.ok(best >= 3, `the tracking player got only ${best} points`);
  withinWarn(p, "pong");
});

// ---- Simon ----

const SIMON_PADS = [...Array(16).keys()];
const padLed = i => 44 + 2 * SIMON_PADS[i];

test("Simon lights one of the 16 pads at a time, takes the sequence back on the pads and grows it by a step each round", () => {
  const p = plugin("simon");
  p.device.run(1);
  assert.equal(p.device.hardware.ledHold, 1, "it holds the panel LEDs while it is open");
  const seen = [];
  for (let round = 1; round <= 6; round++) {
    let frames = 0;
    while (p.v("state") != 2 && frames++ < 1000) {
      p.device.run(1);
      const on = SIMON_PADS.map((_, i) => p.device.leds[padLed(i)]).filter(Boolean).length;
      assert.ok(on <= 1, "never two pads at once");
      if (on) seen.push(round);
    }
    assert.equal(p.v("state"), 2, `round ${round} waits for the player`);
    assert.equal(p.v("len"), round);
    for (let i = 0; i < round; i++) {
      const want = p.at("seq", i);
      p.device.post("pad", SIMON_PADS[want], 1, 100);
      p.device.run(2);
      assert.equal(p.device.leds[padLed(want)], 255, "the pressed pad lights");
      p.device.post("pad", SIMON_PADS[want], 0, 0);
      p.device.run(2);
      assert.equal(p.device.leds[padLed(want)], 0);
    }
    p.device.run(1);
    assert.equal(p.v("score"), round);
  }
  assert.ok(seen.length > 10);
  assert.ok(new Set(Array.from({ length: 6 }, (_, i) => p.at("seq", i))).size > 1, "the sequence uses more than one pad");
  withinWarn(p, "simon");
});

test("Simon: a wrong pad ends the game with the score, all LEDs go dark, a pad or TAP starts anew, closing gives the LEDs back", () => {
  const p = plugin("simon");
  for (let round = 1; round <= 3; round++) {
    while (p.v("state") != 2) p.device.run(1);
    for (let i = 0; i < round; i++) {
      p.device.post("pad", SIMON_PADS[p.at("seq", i)], 1, 100);
      p.device.run(2);
      p.device.post("pad", SIMON_PADS[p.at("seq", i)], 0, 0);
      p.device.run(2);
    }
    p.device.run(1);
  }
  while (p.v("state") != 2) p.device.run(1);
  const wrong = (p.at("seq", 0) + 1) & 15;
  p.device.post("pad", SIMON_PADS[wrong], 1, 100);
  p.device.run(1);
  assert.equal(p.v("state"), 3);
  p.device.run(80);
  assert.equal(p.v("state"), 5);
  assert.equal(p.v("score"), 3, "three rounds were got through");
  assert.deepEqual(SIMON_PADS.map((_, i) => p.device.leds[padLed(i)]), Array(16).fill(0));
  const text = new Display();
  text.textNumber("SCORE ", 3, 83, 2);
  assert.equal(p.device.display.rows().slice(0, 10).map(r => r.slice(60, 128)).join("\n"), text.rows().slice(0, 10).map(r => r.slice(60, 128)).join("\n"));
  press(p, "TAP", 40);
  assert.ok(p.v("state") <= 1 && p.v("len") <= 1, "TAP starts a new game");
  p.device.closeApp();
  p.device.run(2);
  assert.equal(p.device.hardware.ledHold, 0);
  assert.deepEqual([...p.device.leds].slice(44, 76).filter(Boolean), []);
});

// ---- Mandelbrot ----

/** The same fixed-point arithmetic as the plugin, in JavaScript, for comparing the picture. */
function reference(cx, cy, ds, maxIter, px, py) {
  const cr = cx + (px - 64) * ds;
  const ci = cy + (py - 32) * ds;
  if (cr > -12288 && cr < 6144 && ci > -11000 && ci < 11000) {
    const xq = cr - 4096;
    const q = ((xq * xq) >> 14) + ((ci * ci) >> 14);
    if (((q * (q + xq)) >> 14) < ((ci * ci) >> 16)) return maxIter;
  }
  if (cr > -20480 && cr < -12288 && ci > -4096 && ci < 4096) {
    const xp = cr + 16384;
    if (((xp * xp) >> 14) + ((ci * ci) >> 14) < 1024) return maxIter;
  }
  let zx = 0, zy = 0, n = 0;
  while (n < maxIter) {
    if (zx > 32768 || zx < -32768 || zy > 32768 || zy < -32768) break;
    const zx2 = (zx * zx) >> 14;
    const zy2 = (zy * zy) >> 14;
    if (zx2 + zy2 > 65536) break;
    zy = ((zx * zy) >> 13) + ci;
    zx = zx2 - zy2 + cr;
    n += 1;
  }
  return n;
}
const ink = (n, maxIter) => (n == maxIter || (n > 2 && (n & 3) == 0) ? 1 : 0);
const finishRender = p => { let f = 0; while (!p.v("done") && f < 12000) { noFault(p.device.run(1)); f += 1; } assert.equal(p.v("done"), 1, `render finished at ${p.v("cx")},${p.v("cy")},${p.v("zoom")},${p.v("maxIter")}`); return f; };
const picture = p => Buffer.from(p.device.display.bytes).toString("hex");

test("Mandelbrot shows final interior pixels early and finishes pixel for pixel like the fixed-point reference", () => {
  const p = plugin("mandelbrot");
  const first = 16;
  noFault(p.device.run(first));
  assert.ok(p.device.display.bytes.some(b => b), "non-blank");
  assert.equal(pixel(p.device, 64, 32), 1, "the middle of the main cardioid is in the set");
  assert.equal(pixel(p.device, 2, 2), 0, "a corner is outside");
  const frames = finishRender(p);
  assert.ok(first + frames < 3000, `the full picture takes ${first + frames} frames`);
  const picked = [];
  for (let y = 0; y < 64; y += 3) for (let x = 0; x < 128; x += 3) if (y < 53 || x < 76) picked.push([x, y]);
  const mismatches = picked.filter(([x, y]) => pixel(p.device, x, y) !== ink(reference(p.v("cx"), p.v("cy"), p.v("ds"), p.v("maxIter"), x, y), p.v("maxIter")));
  assert.deepEqual(mismatches, [], "every sampled pixel equals the reference");
  const hud = new Display();
  hud.textNumber("Z", 0, 80, 55);
  hud.textNumber("I", 24, 104, 55);
  for (let y = 53; y < 64; y++) for (let x = 76; x < 128; x++) assert.equal(pixel(p.device, x, y), hud.get(x, y), `the zoom and iteration read-out at ${x},${y}`);
  const on = p.device.display.bytes.reduce((n, b) => n + b.toString(2).replace(/0/g, "").length, 0);
  assert.ok(on > 800 && on < 5000, `${on} pixels lit`);
  withinWarn(p, "mandelbrot");
});

test("Mandelbrot resolves each image pixel once, without guessed coarse colours", () => {
  const p = plugin("mandelbrot");
  const writes = new Uint16Array(128 * 64);
  const paint = p.device.display.pixel.bind(p.device.display);
  p.device.display.pixel = (x, y, on) => {
    if (x >= 0 && x < 128 && y >= 0 && y < 64 && (y < 53 || x < 76)) {
      writes[y * 128 + x] += 1;
      assert.ok(writes[y * 128 + x] <= 1, `pixel ${x},${y} is already resolved`);
      assert.equal(on, ink(reference(-8192, 0, 384, 24, x, y), 24), `final colour ${x},${y}`);
    }
    paint(x, y, on);
  };
  finishRender(p);
  for (let y = 0; y < 64; y++) for (let x = 0; x < 128; x++) {
    if (y < 53 || x < 76) assert.equal(writes[y * 128 + x], 1, `resolved ${x},${y}`);
  }
  withinWarn(p, "Mandelbrot worklist");
});

test("Mandelbrot fills a certified interior view without refining its individual pixels", () => {
  for (const [cx, zoom] of [[-8192, 7], [-16384, 4]]) {
    const p = plugin("mandelbrot");
    noFault(p.device.run(1));
    p.set("cx", cx);
    p.set("zoom", zoom + 1);
    p.set("maxIter", 64);
    p.device.post("encoder", 0, -1);
    noFault(p.device.run(1));
    const frames = finishRender(p);
    assert.ok(frames < 100, `interior ${cx} at zoom ${zoom}: ${frames} frames`);
    for (let y = 0; y < 53; y++) for (let x = 0; x < 128; x++) {
      assert.equal(pixel(p.device, x, y), 1, `${cx}: ${x},${y}`);
    }
    withinWarn(p, "mandelbrot interior");
  }
});

test("Mandelbrot block fills preserve every reference pixel across boundaries, zooms and iteration limits", () => {
  const views = [
    [-8192, 0, 7, 64], [-8192, 0, 0, 8], [-8192, 0, 0, 64],
    [-12288, 0, 3, 40], [-20480, 0, 4, 64],
    [4096, 0, 4, 64], [6000, 0, 5, 64],
    [-8192, 10800, 3, 64], [-8192, -10800, 3, 64],
    [-12800, 1700, 7, 64], [-12800, -1700, 6, 8],
    [-40960, -40960, 0, 24], [40960, 40960, 0, 24],
  ];
  const p = plugin("mandelbrot");
  noFault(p.device.run(1));
  for (const [cx, cy, zoom, limit] of views) {
    p.set("cx", cx);
    p.set("cy", cy);
    p.set("zoom", zoom + 1);
    p.set("maxIter", limit);
    p.device.post("encoder", 0, -1);
    noFault(p.device.run(1));
    finishRender(p);
    assert.equal(p.v("done"), 1, `finished ${cx},${cy},${zoom},${limit}`);
    let wrong = 0;
    for (let y = 0; y < 64; y++) for (let x = 0; x < 128; x++) {
      if (y >= 53 && x >= 76) continue;
      if (pixel(p.device, x, y) !== ink(reference(cx, cy, 384 >> zoom, limit, x, y), limit)) wrong += 1;
    }
    assert.equal(wrong, 0, `reference ${cx},${cy},${zoom},${limit}`);
    withinWarn(p, `mandelbrot ${cx},${cy},${zoom},${limit}`);
  }
});

test("Mandelbrot discards unfinished work when the view changes", () => {
  const p = plugin("mandelbrot");
  noFault(p.device.run(100));
  assert.equal(p.v("done"), 0);
  p.set("cx", -8192);
  p.set("cy", 0);
  p.set("zoom", 8);
  p.device.post("encoder", 0, -1);
  noFault(p.device.run(1));
  assert.equal(p.v("done"), 1, "the fully interior view completes in one frame");
  for (let y = 0; y < 53; y++) for (let x = 0; x < 128; x++) assert.equal(pixel(p.device, x, y), 1);
  p.set("cx", 32768);
  p.set("cy", 32768);
  p.set("zoom", 1);
  p.device.post("encoder", 0, -1);
  noFault(p.device.run(1));
  assert.equal(p.v("done"), 0);
  for (let y = 0; y < 53; y++) for (let x = 0; x < 128; x++) assert.equal(pixel(p.device, x, y), 0, "old white tiles disappear immediately");
  noFault(p.device.run(30));
  press(p, "TAP", 1);
  finishRender(p);
  for (let y = 0; y < 53; y++) for (let x = 0; x < 128; x++) {
    assert.equal(pixel(p.device, x, y), ink(reference(-8192, 0, 384, 24, x, y), 24), `reset ${x},${y}`);
  }
  withinWarn(p, "Mandelbrot restarted worklist");
});

test("Mandelbrot: a drag pans, the Part keys and the encoder zoom, the keys change the iteration limit, TAP resets, each change redraws", () => {
  const p = plugin("mandelbrot");
  finishRender(p);
  const start = picture(p);
  p.device.post("touch", 400, 500, 1);
  p.device.post("touch", 480, 500, 0);
  p.device.run(1);
  assert.equal(p.v("cx"), -8192 - 10 * 384, "a finger moving right by 80 touch units drags the picture 10 pixels to the right");
  assert.equal(p.v("done"), 0, "the changed view starts a new render");
  finishRender(p);
  assert.notEqual(picture(p), start, "and it is another picture");
  p.device.post("touch", 480, 560, 0);
  p.device.run(1);
  assert.equal(p.v("cy"), 3 * 384, "up on the pad (touch y grows) moves the view up");
  press(p, "TAP", 1);
  assert.deepEqual([p.v("cx"), p.v("cy"), p.v("zoom")], [-8192, 0, 0]);
  finishRender(p);
  assert.equal(picture(p), start, "reset: the first picture again");
  press(p, "PART_RIGHT", 1);
  assert.deepEqual([p.v("zoom"), p.v("ds")], [1, 192]);
  finishRender(p);
  assert.notEqual(picture(p), start, "zoomed");
  p.device.post("encoder", 0, 3);
  p.device.run(1);
  assert.equal(p.v("zoom"), 2);
  p.device.post("encoder", 0, -1);
  p.device.run(1);
  assert.equal(p.v("zoom"), 1);
  for (let i = 0; i < 10; i++) press(p, "PART_RIGHT", 1);
  assert.equal(p.v("zoom"), 7, "zoom stops at 7");
  for (let i = 0; i < 10; i++) press(p, "PART_LEFT", 1);
  assert.equal(p.v("zoom"), 0);
  press(p, "BAR_2", 1);
  assert.equal(p.v("maxIter"), 32);
  for (let i = 0; i < 20; i++) press(p, "BAR_2", 1);
  assert.equal(p.v("maxIter"), 64);
  for (let i = 0; i < 20; i++) press(p, "BAR_1", 1);
  assert.equal(p.v("maxIter"), 8);
  p.device.closeApp();
  const cx = p.v("cx");
  p.device.post("touch", 100, 100, 1);
  p.device.post("touch", 300, 100, 0);
  p.device.run(2);
  assert.equal(p.v("cx"), cx, "closed, it ignores the touchpad");
});

test("Mandelbrot: a deep zoom still matches the reference and no frame of the whole run passes the warning line", () => {
  const p = plugin("mandelbrot");
  p.device.run(2);
  p.set("cx", -12800);
  p.set("cy", 1700);
  for (let i = 0; i < 4; i++) press(p, "PART_RIGHT", 1);
  press(p, "BAR_2", 1);
  press(p, "BAR_2", 1);
  p.set("cx", -12800);
  p.set("cy", 1700);
  finishRender(p);
  let wrong = 0;
  for (let y = 0; y < 53; y += 5) for (let x = 0; x < 128; x += 5) if (pixel(p.device, x, y) !== ink(reference(p.v("cx"), p.v("cy"), p.v("ds"), p.v("maxIter"), x, y), p.v("maxIter"))) wrong += 1;
  assert.equal(wrong, 0);
  assert.ok(p.device.display.bytes.some(b => b));
  withinWarn(p, "mandelbrot");
});

// ---- Snake (catalog) ----

test("Snake: a tap above, below, left or right of the touchpad centre steers, never straight back", () => {
  const p = plugin("snake");
  p.device.run(1);
  assert.equal(p.v("dir"), 0, "heads right");
  assert.equal(pixel(p.device, 6 * 8 + 4, 4 * 8 + 4), 1, "the snake starts in the middle");
  assert.equal(pixel(p.device, 4, 4), 0, "not in the corner");
  const tap = (x, y) => {
    p.device.post("buttonPress", key("TOUCHPAD"));
    p.device.post("touch", x, y, 1);
    p.device.post("buttonRelease", key("TOUCHPAD"));
  };
  tap(512, 1000); p.device.run(1);
  assert.equal(p.v("dir"), 3, "above the centre is up");
  p.device.run(6);
  tap(100, 512); p.device.run(1);
  assert.equal(p.v("dir"), 2, "left");
  p.device.run(6);
  tap(1000, 512); p.device.run(1);
  assert.equal(p.v("dir"), 2, "straight back is ignored");
  p.device.run(6);
  p.device.post("buttonPress", key("TOUCHPAD"));
  p.device.post("touch", 512, 20, 1);
  p.device.run(1);
  assert.equal(p.v("dir"), 1, "below is down");
  p.device.post("touch", 100, 512, 0);
  p.device.run(1);
  assert.equal(p.v("dir"), 1, "the finger moving on, without lifting, does not steer");
  p.device.post("buttonRelease", key("TOUCHPAD"));
});

test("Snake: PART left and right turn it a quarter from the direction of its last step", () => {
  const p = plugin("snake");
  p.device.run(1);
  assert.equal(p.v("dir"), 0, "heads right");
  p.device.post("buttonPress", key("PART_LEFT"));
  p.device.run(1);
  assert.equal(p.v("dir"), 3, "PART left: up");
  p.device.run(6);
  p.device.post("buttonPress", key("PART_RIGHT"));
  p.device.run(1);
  assert.equal(p.v("dir"), 0, "PART right: right again");
});
