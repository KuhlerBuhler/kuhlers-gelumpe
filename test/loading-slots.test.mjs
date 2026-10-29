import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SLOTS, slotSource, slotsToAnimation, animationToSlots, encodeAnimation, decodeAnimation, progressIndex, FRAME_BYTES,
} from "../src/loading-anim.mjs";

const frame = fill => new Uint8Array(FRAME_BYTES).fill(fill);
const sources = (k, mode) => Array.from({ length: SLOTS }, (_, s) => slotSource(s, k, mode));

test("100 slots, slot n stands for n percent", () => {
  assert.equal(SLOTS, 100);
  // the firmware's picture at n percent is slot n (up to 1 % below 100, where 99 % already shows slot 98)
  assert.equal(progressIndex(SLOTS, 0), 0);
  assert.equal(progressIndex(SLOTS, 500), 49);
  assert.equal(progressIndex(SLOTS, 1000), 99);
});

test("stretch: fewer than 100 pictures spread evenly, the first at slot 0, the others empty between them", () => {
  const map = sources(3, "stretch");
  assert.deepEqual(map.map((j, s) => [s, j]).filter(([, j]) => j >= 0), [[0, 0], [33, 1], [66, 2]]);
  assert.equal(map.filter(j => j < 0).length, 97);
  const ten = sources(10, "stretch");
  assert.deepEqual(ten.flatMap((j, s) => (j >= 0 ? [s] : [])), [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]);
});

test("stretch: exactly 100 pictures are slot for slot, more are thinned evenly, the first and order kept", () => {
  assert.deepEqual(sources(100, "stretch"), Array.from({ length: 100 }, (_, s) => s));
  const many = sources(250, "stretch");
  assert.equal(many[0], 0);
  assert.equal(many.every(j => j >= 0), true, "no empty slot");
  assert.equal(many.every((j, s) => !s || j > many[s - 1]), true, "rising");
  assert.equal(many[99], 247);
});

test("repeat: slot n shows picture n % k, more than 100 pictures fall back to stretch", () => {
  assert.deepEqual(sources(3, "repeat").slice(0, 7), [0, 1, 2, 0, 1, 2, 0]);
  assert.equal(sources(3, "repeat")[99], 0);
  assert.deepEqual(sources(250, "repeat"), sources(250, "stretch"));
  assert.deepEqual(sources(0, "repeat"), Array(100).fill(-1));
});

test("an empty slot shows the slot before it and costs only its empty list; slot 0 empty is a blank display", () => {
  const slots = Array(SLOTS).fill(null);
  slots[10] = frame(0x0f);
  slots[60] = frame(0x00);
  const anim = slotsToAnimation(slots);
  assert.equal(anim.progress.length, 100);
  assert.equal(anim.loop.length, 0);
  assert.equal(anim.loopFrom, 0);
  assert.deepEqual(anim.progress[0], frame(0xff), "blank: every pixel lit on the reversed display, nothing drawn");
  assert.deepEqual(anim.progress[9], frame(0xff));
  assert.deepEqual(anim.progress[10], frame(0x0f));
  assert.deepEqual(anim.progress[59], frame(0x0f), "carried");
  assert.deepEqual(anim.progress[99], frame(0x00));
  const { size } = encodeAnimation(anim);
  // header, picture 0, 99 table entries, 97 empty lists of 2 bytes and two lists of whole pictures
  assert.ok(size < 16 + 1024 + 99 * 2 + 97 * 2 + 2 * 1100, String(size));
});

test("invert turns every picture, the blank one too", () => {
  const slots = Array(SLOTS).fill(null);
  slots[50] = frame(0x0f);
  const anim = slotsToAnimation(slots, { invert: true });
  assert.deepEqual(anim.progress[0], frame(0x00));
  assert.deepEqual(anim.progress[50], frame(0xf0));
  assert.deepEqual(slots[50], frame(0x0f), "the slot itself stays as it is");
});

test("a loop from n percent: the slots from n on are the loop pictures, the progress holds the picture before", () => {
  const slots = Array(SLOTS).fill(null);
  slots[0] = frame(0x01);
  slots[90] = frame(0x02);
  slots[95] = frame(0x03);
  slots[97] = frame(0x04);
  const anim = slotsToAnimation(slots, { loopFrom: 95 });
  assert.equal(anim.loopFrom, 95);
  assert.deepEqual(anim.loop, [frame(0x03), frame(0x04)]);
  assert.deepEqual(anim.progress[94], frame(0x02));
  assert.deepEqual(anim.progress[99], frame(0x02), "the progress stands at the last picture before the loop");
  const empty = slotsToAnimation([frame(0x01), ...Array(SLOTS - 1).fill(null)], { loopFrom: 95 });
  assert.equal(empty.loop.length, 0, "no picture from n on: no loop");
  assert.equal(empty.loopFrom, 0);
});

test("a saved file comes back as the same slots: what is saved is what is shown", () => {
  const slots = Array(SLOTS).fill(null);
  slots[0] = frame(0x11);
  slots[30] = frame(0x22);
  slots[96] = frame(0x33);
  slots[98] = frame(0x44);
  const bytes = encodeAnimation(slotsToAnimation(slots, { loopFrom: 96 })).bytes;
  const back = animationToSlots(decodeAnimation(bytes));
  assert.equal(back.loopFrom, 96);
  assert.deepEqual(back.slots.flatMap((f, s) => (f ? [s] : [])), [0, 30, 96, 97]);
  assert.deepEqual(encodeAnimation(slotsToAnimation(back.slots, { loopFrom: back.loopFrom })).bytes, bytes);
});

test("an older file with other picture counts spreads over the slots; a loop on a stall gets 95 %", () => {
  const old = { progress: [frame(0x01), frame(0x02), frame(0x03)], loop: [frame(0x04)], loopFrom: 0 };
  const back = animationToSlots(old);
  assert.equal(back.loopFrom, 95);
  assert.deepEqual(back.slots.flatMap((f, s) => (f ? [s] : [])), [0, 33, 66, 95]);
  const blank = animationToSlots({ progress: [frame(0xff), frame(0x00)], loop: [], loopFrom: 0 });
  assert.equal(blank.slots[0], null, "a blank first picture is an empty slot 0");
  assert.equal(blank.loopFrom, 0);
});
