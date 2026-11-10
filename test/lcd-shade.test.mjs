import { test } from "node:test";
import assert from "node:assert/strict";
import { shadeImage } from "../site/app/emulator.mjs";

const ON = [10, 20, 30];
const OFF = [250, 240, 230];

test("level 0 is the off colour, 15 the on colour, and the levels between mix them", () => {
  const levels = new Uint8Array(128 * 64);
  levels[1] = 15;
  levels[2] = 8;
  const px = shadeImage(levels, ON, OFF);
  const at = i => [...px.slice(i * 4, i * 4 + 4)];
  assert.deepEqual(at(0), [...OFF, 255]);
  assert.deepEqual(at(1), [...ON, 255]);
  assert.deepEqual(at(2), [Math.round(250 - 240 * 8 / 15), Math.round(240 - 220 * 8 / 15), Math.round(230 - 200 * 8 / 15), 255]);
});

test("a level above 15 is drawn as 15", () => {
  const levels = new Uint8Array(128 * 64).fill(200);
  assert.deepEqual([...shadeImage(levels, ON, OFF).slice(0, 4)], [...ON, 255]);
});

test("the image is 128 by 64 pixels", () => {
  assert.equal(shadeImage(new Uint8Array(128 * 64), ON, OFF).length, 128 * 64 * 4);
});

test("the display light tints both colours: white keeps them, a dimmer red keeps only red at its share, dark is black", async () => {
  const { lit } = await import("../site/app/emulator.mjs");
  assert.deepEqual(lit(OFF, null), OFF, "no light from the emulator: the theme's colours");
  assert.deepEqual(lit(OFF, [255, 255, 255]), OFF, "stock white");
  assert.deepEqual(lit([255, 255, 255], [80, 0, 0]), [80, 0, 0], "red at 5 of 16");
  assert.deepEqual(lit(ON, [0, 0, 0]), [0, 0, 0], "light off");
  const px = shadeImage(new Uint8Array(128 * 64), lit(ON, [0, 255, 0]), lit(OFF, [0, 255, 0]));
  assert.deepEqual([...px.slice(0, 4)], [0, 240, 0, 255], "a clear pixel in green light");
});
