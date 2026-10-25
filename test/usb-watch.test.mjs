import { test } from "node:test";
import assert from "node:assert/strict";
import { createUsbWatch } from "../site/app/usb-watch.mjs";

const port = name => ({ name, state: "connected" });
const access = (...names) => {
  const target = new EventTarget();
  target.inputs = new Map(names.map((n, i) => [`i${i}`, port(n)]));
  target.outputs = new Map(names.map((n, i) => [`o${i}`, port(n)]));
  return target;
};
const quietTimers = { setInterval: () => 1, clearInterval: () => {} };
const granted = { query: async () => ({ state: "granted" }) };

test("native: the port list decides, a plug-in and a pull show on the next check", async () => {
  let ports = [];
  const transport = { native: true, supported: true, requestAccess: async () => access(...ports) };
  const watch = createUsbWatch({ transport, timers: quietTimers });
  const seen = [];
  watch.subscribe(s => seen.push(s));
  await watch.check();
  ports = ["electribe2 sampler"];
  await watch.check();
  ports = ["USB Keyboard"];
  await watch.check();
  assert.deepEqual(seen, ["unknown", "absent", "present", "absent"]);
});

test("native: the timer re-checks, a hidden page and an open session do not", async () => {
  let listed = 0;
  let tick;
  let hidden = false;
  const transport = { native: true, supported: true, requestAccess: async () => { listed++; return access("electribe2 sampler"); } };
  const watch = createUsbWatch({ transport, hidden: () => hidden, timers: { setInterval: fn => { tick = fn; return 1; }, clearInterval: () => {} } });
  watch.start();
  await new Promise(r => setImmediate(r));
  assert.equal(listed, 1);
  tick();
  await new Promise(r => setImmediate(r));
  assert.equal(listed, 2);
  hidden = true;
  tick();
  hidden = false;
  watch.setConnected(true);
  tick();
  await new Promise(r => setImmediate(r));
  assert.equal(listed, 2, "neither a hidden page nor a connected session lists the ports");
  assert.equal(watch.state, "connected");
  watch.setConnected(false);
  await new Promise(r => setImmediate(r));
  assert.equal(listed, 3, "closing the session asks again at once");
  assert.equal(watch.state, "present");
});

test("Web MIDI: statechange updates the state with no timer, one access object is reused", async () => {
  const live = access();
  let requests = 0;
  const transport = { native: false, supported: true, requestAccess: async () => { requests++; return live; } };
  const watch = createUsbWatch({ transport, permissions: granted, timers: quietTimers });
  await watch.check();
  assert.equal(watch.state, "absent");
  live.inputs.set("in", port("electribe2 sampler"));
  live.outputs.set("out", port("electribe2 sampler"));
  live.dispatchEvent(new Event("statechange"));
  await new Promise(r => setImmediate(r));
  assert.equal(watch.state, "present");
  live.inputs.clear();
  live.outputs.clear();
  live.dispatchEvent(new Event("statechange"));
  await new Promise(r => setImmediate(r));
  assert.equal(watch.state, "absent");
  assert.equal(requests, 1);
});

test("Web MIDI: without the permission the state stays unknown and MIDI is never requested", async () => {
  let requests = 0;
  const transport = { native: false, supported: true, requestAccess: async () => { requests++; return access(); } };
  for (const permissions of [{ query: async () => ({ state: "prompt" }) }, null, { query: async () => { throw new Error("no midi"); } }]) {
    const watch = createUsbWatch({ transport, permissions, timers: quietTimers });
    await watch.check();
    assert.equal(watch.state, "unknown");
  }
  assert.equal(requests, 0);
});

test("a failing port list leaves the state unknown and the next check recovers", async () => {
  let fail = true;
  const transport = { native: true, supported: true, requestAccess: async () => { if (fail) throw new Error("ALSA"); return access("electribe2 sampler"); } };
  const watch = createUsbWatch({ transport, timers: quietTimers });
  await watch.check();
  assert.equal(watch.state, "unknown");
  fail = false;
  await watch.check();
  assert.equal(watch.state, "present");
});

test("two electribes still count as present, an unsupported browser is unknown", async () => {
  const two = createUsbWatch({ transport: { native: true, supported: true, requestAccess: async () => access("electribe2 sampler", "electribe2 synth") }, timers: quietTimers });
  await two.check();
  assert.equal(two.state, "present");
  const none = createUsbWatch({ transport: { native: false, supported: false }, timers: quietTimers });
  await none.check();
  assert.equal(none.state, "unknown");
});
