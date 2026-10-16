import { test } from "node:test";
import assert from "node:assert/strict";
import {
  Accumulator, WheelGovernor, DETENTS_PER_TURN, DETENT_DEG, FREE_MAX, FREE_CENTER, rawOf, withCatch, angleOfValue, wheelPixels,
} from "../site/app/dials.mjs";

test("a detented encoder clicks 24 times per turn", () => {
  assert.equal(DETENTS_PER_TURN, 24);
  assert.equal(DETENT_DEG * DETENTS_PER_TURN, 360);
});

test("a slow drag arrives in whole clicks and keeps its remainder", () => {
  const acc = new Accumulator(14);
  let clicks = 0;
  for (let i = 0; i < 30; i++) clicks += acc.add(1);
  assert.equal(clicks, 2);
  assert.equal(new Accumulator(14).add(-30), -2);
});

test("the wheel gives one click per notch and never more often than every 70 ms", () => {
  const wheel = new WheelGovernor(100);
  assert.equal(wheel.step(-100, 1000), 1, "wheel up turns clockwise");
  assert.equal(wheel.step(-100, 1020), 0, "inside the pause");
  assert.equal(wheel.step(-100, 1040), 0);
  assert.equal(wheel.step(100, 1200), -1, "wheel down turns back");
  assert.equal(wheel.step(-40, 1400), 0, "a small trackpad move is not a click yet");
  assert.equal(wheel.step(-70, 1500), 1);
});

test("wheel distance is pixels whatever the browser reports", () => {
  assert.equal(wheelPixels({ deltaMode: 0, deltaY: 100 }), 100);
  assert.equal(wheelPixels({ deltaMode: 1, deltaY: 3 }), 120);
});

test("free controls show 0 to 127 and send up to 255", () => {
  assert.equal(rawOf(0), 0);
  assert.equal(rawOf(64), 128);
  assert.equal(rawOf(FREE_MAX), 255);
  assert.ok(Math.abs(angleOfValue(FREE_CENTER)) < 2, "the middle points up");
});

test("PAN, PITCH and EG INT catch briefly in the middle", () => {
  for (const p of [61, 62, 64, 66.4, 67]) assert.equal(withCatch(p), FREE_CENTER, String(p));
  assert.equal(withCatch(68), 68);
  assert.equal(withCatch(60), 60);
  assert.equal(withCatch(-5), 0);
  assert.equal(withCatch(500), FREE_MAX);
});
