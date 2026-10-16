import { test } from "node:test";
import assert from "node:assert/strict";
import { SCRIPT_LED, SCRIPT_LED_VALID } from "../data/script/contract.mjs";
import { ScriptLeds } from "../src/script/led.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
import { compile } from "../src/script/compiler.mjs";

function transport(free = 1024) {
  const calls = [];
  return {
    calls,
    queueFree: () => free,
    send: (index, level) => { calls.push([index, level]); free -= SCRIPT_LED.packetBytes; return true; },
  };
}

test("LED requests validate integers and bounds before changing state", () => {
  const leds = new ScriptLeds();
  for (const index of [-1, 88, NaN, 0.5, "1", true]) assert.throws(() => leds.request(index, 1), RangeError);
  for (const level of [-1, 256, NaN, 0.5, "1", true]) assert.throws(() => leds.request(1, level), RangeError);
  assert.ok(leds.valid.every(v => v === 0));
  assert.ok(leds.pending.every(v => v === 0));
  leds.request(0, 0);
  leds.request(87, 255);
  const tx = transport();
  assert.equal(leds.flushFrame(tx), 2);
  assert.deepEqual(tx.calls, [[0, 0], [87, 255]]);
});

test("the last level wins and an initial zero is still an explicit command", () => {
  const leds = new ScriptLeds();
  leds.request(4, 100);
  leds.request(4, 200);
  leds.request(4, 0);
  leds.request(4, 0);
  const tx = transport();
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[4, 0]]);
  assert.equal(leds.delivered[4], 0);
  assert.equal(leds.valid[4], SCRIPT_LED_VALID.DESIRED | SCRIPT_LED_VALID.DELIVERED);
  leds.request(4, 255);
  leds.request(4, 0);
  assert.equal(leds.pending[4], 0);
  assert.equal(leds.flushFrame(tx), 0);
});

test("beginFrame expires delivery knowledge without automatically resending old desires", () => {
  const leds = new ScriptLeds();
  const tx = transport();
  leds.request(76, 30);
  assert.equal(leds.flushFrame(tx), 1);
  leds.request(76, 30);
  assert.equal(leds.flushFrame(tx), 0);
  leds.beginFrame();
  assert.equal(leds.valid[76], SCRIPT_LED_VALID.DESIRED);
  assert.equal(leds.pending[76], 0);
  assert.equal(leds.flushFrame(tx), 0);
  leds.request(76, 30);
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[76, 30], [76, 30]]);
});

test("one frame sends at most sixteen packets, retaining the rest fairly", () => {
  const leds = new ScriptLeds();
  const tx = transport();
  for (let i = 0; i < SCRIPT_LED.count; i++) leds.request(i, i);
  assert.equal(leds.flushFrame(tx), 16);
  assert.equal(leds.flushFrame(tx), 0);
  assert.deepEqual(tx.calls.map(c => c[0]), Array.from({ length: 16 }, (_, i) => i));
  leds.beginFrame();
  for (let i = 0; i < 16; i++) leds.request(i, 255);
  assert.equal(leds.flushFrame(tx), 16);
  assert.deepEqual(tx.calls.slice(16).map(c => c[0]), Array.from({ length: 16 }, (_, i) => i + 16));
  assert.equal(leds.pending[87], 1);
});

test("the ledger bytes follow the generated array offsets and little-endian cursor", () => {
  const leds = new ScriptLeds();
  const fields = Object.fromEntries(SCRIPT_LED.fields.map(f => [f.name, f.offset]));
  for (let i = 0; i < 20; i++) leds.request(i, i + 1);
  assert.equal(leds.flushFrame(transport()), 16);
  assert.equal(leds.bytes.length, SCRIPT_LED.size);
  assert.equal(leds.bytes[fields.desired + 15], 16);
  assert.equal(leds.bytes[fields.delivered + 15], 16);
  assert.equal(leds.bytes[fields.pending + 16], 1);
  assert.equal(leds.bytes[fields.valid + 15], SCRIPT_LED_VALID.DESIRED | SCRIPT_LED_VALID.DELIVERED);
  assert.equal(new DataView(leds.bytes.buffer).getUint32(fields.nextIndex, true), 16);
  assert.equal(leds.nextIndex, 16);
});

test("a clogged queue does not spin, send or discard pending requests", () => {
  const leds = new ScriptLeds();
  leds.request(1, 99);
  let polls = 0;
  let sends = 0;
  const stalled = { queueFree: () => { polls += 1; return SCRIPT_LED.reserveBytes; }, send: () => { sends += 1; return false; } };
  assert.equal(leds.flushFrame(stalled), 0);
  assert.equal(polls, 1);
  assert.equal(sends, 0);
  assert.equal(leds.pending[1], 1);
  assert.equal(leds.valid[1], SCRIPT_LED_VALID.DESIRED);
  const tx = transport(SCRIPT_LED.reserveBytes + SCRIPT_LED.packetBytes);
  leds.request(2, 22);
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[1, 99]]);
  assert.equal(leds.pending[2], 1);
});

test("an atomic rejection after a free-space probe keeps the command for a later frame", () => {
  const leds = new ScriptLeds();
  leds.request(1, 99);
  let attempts = 0;
  assert.equal(leds.flushFrame({ queueFree: () => 1024, send: () => { attempts += 1; return false; } }), 0);
  assert.equal(attempts, 1);
  assert.equal(leds.pending[1], 1);
  assert.equal(leds.valid[1], SCRIPT_LED_VALID.DESIRED);
  leds.beginFrame();
  const tx = transport();
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[1, 99]]);
});

test("an expired frame budget prevents any transport attempt or delivered state", () => {
  const leds = new ScriptLeds();
  leds.request(1, 99);
  let polls = 0;
  let sends = 0;
  assert.equal(leds.flushFrame({ canSend: () => false, queueFree: () => { polls += 1; return 1024; }, send: () => { sends += 1; return true; } }), 0);
  assert.equal(polls, 0);
  assert.equal(sends, 0);
  assert.equal(leds.pending[1], 1);
  assert.equal(leds.valid[1], SCRIPT_LED_VALID.DESIRED);
});

test("a budget exhausted after the first packet retains all unsent requests", () => {
  const leds = new ScriptLeds();
  leds.request(1, 99);
  leds.request(2, 20);
  let budget = 1;
  const sent = [];
  assert.equal(leds.flushFrame({ canSend: () => budget > 0, queueFree: () => 1024, send: (index, level) => { sent.push([index, level]); budget -= 1; return true; } }), 1);
  assert.deepEqual(sent, [[1, 99]]);
  assert.equal(leds.pending[1], 0);
  assert.equal(leds.pending[2], 1);
  assert.equal(leds.valid[2], SCRIPT_LED_VALID.DESIRED);
  leds.beginFrame();
  const tx = transport();
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[2, 20]]);
});

test("transport contract errors propagate without marking the request delivered", () => {
  const leds = new ScriptLeds();
  leds.request(1, 20);
  assert.throws(() => leds.flushFrame({ queueFree: () => NaN, send: () => true }), RangeError);
  assert.throws(() => leds.flushFrame({ queueFree: () => 1024, send: () => undefined }), TypeError);
  assert.throws(() => leds.flushFrame({ queueFree: () => 1024, send: () => { throw new Error("broken transport"); } }), /broken transport/);
  assert.equal(leds.pending[1], 1);
  assert.equal(leds.valid[1], SCRIPT_LED_VALID.DESIRED);
});

test("a replaced request during successful sending stays pending with the newer level", () => {
  const leds = new ScriptLeds();
  leds.request(1, 20);
  assert.equal(leds.flushFrame({ queueFree: () => 1024, send: () => { leds.request(1, 30); return true; } }), 1);
  assert.equal(leds.delivered[1], 20);
  assert.equal(leds.desired[1], 30);
  assert.equal(leds.pending[1], 1);
  const tx = transport();
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[1, 30]]);
});

test("the runtime explicitly queues korg.led and the frame owner flushes it", () => {
  const leds = new ScriptLeds();
  const rt = new ScriptRuntime({ now: () => 0, api: { "korg.led": leds.request.bind(leds) } });
  const compiled = compile('korg.onEvent("frame", () => { korg.led(4, 10); korg.led(4, 20); korg.led(4, 20); });');
  assert.ok(compiled.ok);
  assert.ok(rt.add(compiled.blob).ok);
  const tx = transport();
  leds.beginFrame();
  assert.deepEqual(rt.frame().faults, []);
  assert.deepEqual(tx.calls, []);
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[4, 20]]);
  leds.beginFrame();
  assert.deepEqual(rt.frame().faults, []);
  assert.equal(leds.flushFrame({ queueFree: () => 1024, send: () => false }), 0);
  assert.equal(rt.status().scripts[0].state, "armed");
  assert.equal(leds.pending[4], 1);
  leds.beginFrame();
  assert.equal(leds.flushFrame(tx), 1);
  assert.deepEqual(tx.calls, [[4, 20], [4, 20]]);
});

test("the VM rejects invalid LED arguments before the host ledger sees them", () => {
  for (const [index, level] of [[88, 1], [1, 256], [-1, 1], [1, -1]]) {
    const leds = new ScriptLeds();
    const rt = new ScriptRuntime({ now: () => 0, api: { "korg.led": leds.request.bind(leds) } });
    const compiled = compile(`korg.onEvent("frame", () => { korg.led(${index}, ${level}); });`);
    assert.ok(compiled.ok);
    assert.ok(rt.add(compiled.blob).ok);
    assert.deepEqual(rt.frame().faults.map(f => f.name), ["API_ARG"]);
    assert.ok(leds.valid.every(v => v === 0));
    assert.ok(leds.pending.every(v => v === 0));
  }
});
