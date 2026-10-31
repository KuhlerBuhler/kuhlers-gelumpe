import { test } from "node:test";
import assert from "node:assert/strict";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice, FRAME_MS } from "../src/script/sim.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
import { API_BY_NAME, EVENT_BY_NAME, QUEUED_EVENTS, TIMERS, SCRIPT_ENTRY } from "../data/script/contract.mjs";

const build = source => {
  const r = compile(source, { name: "timers" });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  return r;
};

/** A simulated device with the block loaded; `v(name)` reads a global. */
function device(source) {
  const r = build(source);
  const d = new SimDevice();
  const loaded = d.load(r.blob);
  assert.ok(loaded.ok, String(loaded.error?.message));
  const v = name => d.runtime.scripts[0].script.vars[r.info.symbols[name].slot];
  return { d, v, info: r.info };
}

const fails = (source, pattern) => {
  const r = compile(source);
  assert.equal(r.ok, false, source);
  assert.match(r.errors[0].message, pattern);
};

test("the timer calls are API 11, take the callback as a number and have their own internal event", () => {
  for (const name of ["korg.after", "korg.every", "korg.afterSteps", "korg.cancel"]) assert.equal(API_BY_NAME.get(name).since, 11, name);
  assert.deepEqual(EVENT_BY_NAME.get("timer").args, ["callback"]);
  assert.ok(!QUEUED_EVENTS.includes("timer"), "nothing outside the runtime posts timer");
  assert.ok(!(API_BY_NAME.get("korg.after").eventMask >> EVENT_BY_NAME.get("save").id & 1), "not in save, another task");
  assert.equal(SCRIPT_ENTRY.fields.find(f => f.name === "timers").words * 4, TIMERS.slots * TIMERS.recordSize);
  const { info } = device("function f() {} korg.after(10, f);");
  assert.equal(info.apiVersion, 11);
  assert.deepEqual(info.handlers.map(h => [h.event, h.argc]), [["timer", 1]]);
});

test("korg.after fires once at the first frame at or after its time, korg.every again and again", () => {
  const { d, v } = device(`let once = 0; let at = 0; let ticks = 0;
function done() { once = once + 1; at = korg.millis(); }
korg.after(1000, done);
korg.every(500, () => { ticks = ticks + 1; });`);
  d.run(1000 / FRAME_MS);
  assert.equal(v("once"), 0, "not before 1000 ms");
  d.run(1);
  assert.equal(v("once"), 1);
  assert.equal(v("at"), 1000);
  assert.equal(v("ticks"), 2);
  d.run(100);
  assert.equal(v("once"), 1, "once is once");
  assert.equal(v("ticks"), Math.floor((101 * FRAME_MS + 1000) / 500));
});

test("a frame grid of 40 ms: a time between two frames fires at the next one, never early", () => {
  const { d, v } = device(`let at = -1;
korg.onEvent("ready", () => { korg.after(1010, () => { at = korg.millis(); }); });`);
  d.run(60);
  assert.equal(v("at"), 1040);
});

test("korg.cancel stops a timer, and a stale number does not stop the timer that took its slot since", () => {
  const { d, v } = device(`let a = 0; let b = 0; let first = -1; let second = -1;
first = korg.after(100, () => { a = a + 1; });
korg.onEvent("frame", () => {
  if (korg.millis() == 200) { second = korg.after(100, () => { b = b + 1; }); korg.cancel(first); }
});
let gone = korg.every(40, () => { a = a + 100; });
korg.cancel(gone);
korg.cancel(-1);`);
  d.run(20);
  assert.equal(v("a"), 1, "the cancelled korg.every never ran, the korg.after once");
  assert.equal(v("second") % TIMERS.slots, v("first") % TIMERS.slots, "the same slot again");
  assert.notEqual(v("second"), v("first"), "but another number");
  assert.equal(v("b"), 1, "cancelling the old number left the new timer alone");
});

test("eight slots per plugin, -1 when all are taken; a slot is free again once its timer ran", () => {
  const { d, v } = device(`let last = 0; let again = 0; let ran = 0;
for (let i = 0; i < 8; i++) last = korg.after(40, () => { ran = ran + 1; });
let ninth = korg.after(40, () => { ran = ran + 1; });
korg.onEvent("frame", () => { if (korg.millis() == 120) again = korg.after(40, () => { ran = ran + 1; }); });`);
  assert.equal(v("ninth"), -1);
  assert.ok(v("last") >= 0);
  d.run(10);
  assert.equal(v("ran"), 9);
  assert.ok(v("again") >= 0);
});

test("a closed app still gets its timers, and they go to the plugin that set them only", () => {
  const app = build(`korg.app("Clock", "TOOLS");
let n = 0;
korg.every(200, () => { n = n + 1; });`);
  const other = build(`let n = 0;
function tick() { n = n + 1; }
korg.after(10000, tick);`);
  const d = new SimDevice();
  d.load(app.blob);
  d.load(other.blob);
  d.run(50);
  const vars = i => d.runtime.scripts[i].script.vars[0];
  assert.equal(vars(0), 9, "200, 400 ... 1800 ms; the 50th frame is at 1960");
  assert.equal(vars(1), 0, "the other plugin's callback 0 did not run");
});

test("korg.afterSteps fires on the n-th step after the call, stands while stopped and follows the tempo", () => {
  const { d, v } = device(`let at = -1; let from = -1;
korg.onEvent("play", () => { from = korg.read.step(0); korg.afterSteps(4, () => { at = korg.read.step(0); }); });`);
  d.run(2);
  d.hardware.api()["korg.play"]();
  d.run(2);
  assert.equal(v("from"), 0);
  d.run(12);
  assert.equal(v("at"), 4, "four steps of 125 ms at 120 BPM");
  const stopped = device(`let at = -1;
korg.onEvent("play", () => { korg.afterSteps(2, () => { at = korg.read.step(0); }); });`);
  stopped.d.hardware.api()["korg.play"]();
  stopped.d.run(4);
  stopped.d.hardware.api()["korg.stop"]();
  stopped.d.run(100);
  assert.equal(stopped.v("at"), -1, "no steps while stopped");
  stopped.d.hardware.api()["korg.play"]();
  stopped.d.run(4);
  assert.equal(stopped.v("at"), 1, "the second step counts after PLAY again");
});

test("a timer may set itself again from its callback, an arrow in a handler is a callback too", () => {
  const { d, v } = device(`let n = 0; let at = 0;
function blink() { n = n + 1; at = korg.millis(); korg.after(500, blink); }
korg.onEvent("ready", () => { korg.after(500, blink); korg.after(100, () => { n = n + 1000; }); });`);
  d.run(51);
  assert.equal(v("n"), 1003, "the arrow once, blink three times");
  assert.equal(v("at"), 1560, "each new korg.after counts from the frame it ran in: 520, 1040, 1560");
});

test("the compiler refuses what cannot be a callback and constant values outside the range", () => {
  fails("korg.after(100, 5);", /korg\.after/);
  fails("function f(x) { return x; } korg.after(100, f);", /korg\.after/);
  fails("korg.every(100, (x) => { });", /korg\.every/);
  fails("korg.after(-1, () => { });", /-1/);
  fails("korg.every(0, () => { });", /0/);
  fails("korg.afterSteps(0, () => { });", /0/);
  fails("korg.onEvent(\"timer\", (c) => { });", /timer/);
  fails("korg.onEvent(\"save\", () => { korg.after(1, () => { }); });", /korg\.after/);
});

test("a value only known at run time is checked by the VM: a fault, not a timer", () => {
  const { d } = device(`let ms = -5;
korg.onEvent("ready", () => { korg.after(ms, () => { }); });`);
  d.run(2);
  assert.equal(d.status().scripts[0].state, "disabled");
});

test("the runtime takes its clock from korg.millis, and a full ring leaves a due timer for the next frame", () => {
  let ms = 0;
  const rt = new ScriptRuntime({ api: { "korg.millis": () => ms }, frameMs: Infinity, handlerWarnMs: Infinity });
  const r = build(`let n = 0; korg.after(5, () => { n = n + 1; });`);
  rt.add(r.blob);
  for (let i = 0; i < 64; i++) rt.post("beat");
  ms = 10;
  rt.frame();
  assert.equal(rt.scripts[0].script.vars[0], 0, "the ring was full");
  rt.frame();
  assert.equal(rt.scripts[0].script.vars[0], 1);
});
