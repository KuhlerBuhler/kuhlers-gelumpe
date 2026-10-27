import { test } from "node:test";
import assert from "node:assert/strict";
import { createAutoConnect } from "../site/app/auto-connect.mjs";

/** Timers that run only when the test says so. */
function fakeTimers() {
  let next = 1;
  const due = new Map();
  return {
    setTimeout(fn, ms) { due.set(next, { fn, ms }); return next++; },
    clearTimeout(id) { due.delete(id); },
    get pending() { return [...due.values()].map(d => d.ms); },
    async fire() {
      const [[id, { fn }]] = due;
      due.delete(id);
      await fn();
    },
  };
}

function fakeUsb(state = "unknown") {
  const subs = new Set();
  return {
    get state() { return state; },
    subscribe(fn) { subs.add(fn); fn(state); },
    set(next) { state = next; for (const fn of subs) fn(state); },
  };
}

function setUp(results) {
  const timers = fakeTimers();
  const usb = fakeUsb();
  const toasts = [];
  let attempts = 0;
  let diagnosed = 0;
  const auto = createAutoConnect({
    usb, timers,
    attempt: async () => { attempts++; return results.shift() ?? "failed"; },
    toast: (text, kind, options) => toasts.push({ text, kind, action: options?.action }),
    diagnose: () => diagnosed++,
  });
  return { auto, usb, timers, toasts, get attempts() { return attempts; }, get diagnosed() { return diagnosed; } };
}

test("a plugged-in Electribe connects after a short wait, without a toast of its own", async () => {
  const s = setUp(["ok"]);
  s.usb.set("present");
  assert.deepEqual(s.timers.pending, [1500]);
  await s.timers.fire();
  assert.equal(s.attempts, 1);
  assert.deepEqual(s.toasts, []);
  assert.deepEqual(s.timers.pending, []);
});

test("a failing series says so three times, the last with the way to the diagnostics, then stops", async () => {
  const s = setUp([]);
  s.usb.set("present");
  await s.timers.fire();
  assert.deepEqual(s.timers.pending, [3000]);
  await s.timers.fire();
  assert.deepEqual(s.timers.pending, [6000]);
  await s.timers.fire();
  assert.equal(s.attempts, 3);
  assert.deepEqual(s.timers.pending, [], "no fourth try");
  assert.deepEqual(s.toasts.map(x => [x.text, x.kind]), [
    ["Konnte nicht verbinden, versuche es erneut.", "info"],
    ["Immer noch keine Verbindung.", "info"],
    ["Verbinden hat nicht geklappt. Schau in die MIDI-Diagnose in den Einstellungen.", "error"],
  ]);
  assert.equal(s.toasts[2].action.label, "MIDI-Diagnose");
  s.toasts[2].action.run();
  assert.equal(s.diagnosed, 1);
  // The watch says present again (a check after a session) and still nothing happens.
  s.usb.set("present");
  assert.deepEqual(s.timers.pending, []);
});

test("after giving up, a pull and a plug start a new series", async () => {
  const s = setUp(["failed", "failed", "failed", "ok"]);
  s.usb.set("present");
  for (let i = 0; i < 3; i++) await s.timers.fire();
  s.usb.set("absent");
  s.usb.set("present");
  await s.timers.fire();
  assert.equal(s.attempts, 4);
  assert.equal(s.toasts.length, 3);
});

test("after giving up, the connect button starts a new series", async () => {
  const s = setUp([]);
  s.usb.set("present");
  for (let i = 0; i < 3; i++) await s.timers.fire();
  s.auto.manualConnect();
  s.usb.set("present");
  await s.timers.fire();
  assert.equal(s.attempts, 4);
  assert.equal(s.toasts.at(-1).text, "Konnte nicht verbinden, versuche es erneut.");
});

test("a success in the middle ends the series, the next failure counts from one", async () => {
  const s = setUp(["failed", "ok", "failed"]);
  s.usb.set("present");
  await s.timers.fire();
  await s.timers.fire();
  s.usb.set("connected");
  s.usb.set("present");
  await s.timers.fire();
  assert.deepEqual(s.toasts.map(x => x.text), ["Konnte nicht verbinden, versuche es erneut.", "Konnte nicht verbinden, versuche es erneut."]);
});

test("a manual disconnect holds until the cable comes back or the button is clicked", async () => {
  const s = setUp(["ok", "ok", "ok"]);
  s.usb.set("connected");
  s.auto.manualDisconnect();
  s.usb.set("present");
  assert.deepEqual(s.timers.pending, []);
  s.usb.set("absent");
  s.usb.set("present");
  assert.deepEqual(s.timers.pending, [1500]);
  await s.timers.fire();
  s.usb.set("connected");
  s.auto.manualDisconnect();
  s.usb.set("present");
  assert.deepEqual(s.timers.pending, []);
  s.auto.manualConnect();
  s.usb.set("connected");
  s.usb.set("present");
  assert.deepEqual(s.timers.pending, [1500]);
});

test("a lost session (connected, then present again) tries again", async () => {
  const s = setUp(["ok", "ok"]);
  s.usb.set("present");
  await s.timers.fire();
  s.usb.set("connected");
  s.usb.set("present");
  await s.timers.fire();
  assert.equal(s.attempts, 2);
});

test("skip is no failure, a pull cancels a waiting try, and switched off nothing runs", async () => {
  const s = setUp(["skip"]);
  s.usb.set("present");
  await s.timers.fire();
  assert.deepEqual(s.toasts, []);
  assert.deepEqual(s.timers.pending, []);
  s.usb.set("absent");
  s.usb.set("present");
  s.usb.set("absent");
  assert.deepEqual(s.timers.pending, []);

  const timers = fakeTimers();
  const usb = fakeUsb();
  createAutoConnect({ usb, timers, enabled: () => false, attempt: async () => "ok", toast: () => {}, diagnose: () => {} });
  usb.set("present");
  assert.deepEqual(timers.pending, []);
});
