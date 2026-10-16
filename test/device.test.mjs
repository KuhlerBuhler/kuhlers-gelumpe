import { test } from "node:test";
import assert from "node:assert/strict";
import { makeImage, makeRecord, slotRam } from "./helpers.mjs";
import { SimDevice } from "../src/device.mjs";
import { syxEnc, syxDec, u32le } from "../src/bytes.mjs";
import { RECORD_SIZE } from "../src/layout.mjs";

const build = (channel = 9) => {
  const record = makeRecord("mfx", { name: "Short Delay", devices: { mfx: 0x3b } });
  const image = makeImage([{ kind: "mfx", slot: 50, record }]);
  return { image, dev: new SimDevice({ image, channel }), record };
};

const ask = (dev, cmd, payload) =>
  dev.handle([0xf0, ...dev.head, cmd, ...syxEnc(payload), 0xf7]);

test("the device search answers with its global channel", () => {
  const { dev } = build(11);
  const reply = dev.handle([0xf0, 0x42, 0x50, 0x00, 0x00, 0xf7]);
  assert.equal(reply[4], 11);
});

test("a read returns exactly what is in the image", () => {
  const { dev, image, record } = build();
  const reply = ask(dev, 0x52, [...u32le(slotRam("mfx", 50)), ...u32le(RECORD_SIZE)]);
  const got = Uint8Array.from(syxDec(reply.slice(9, -1))).slice(0, RECORD_SIZE);
  assert.deepEqual([...got], [...record.bytes]);
  assert.deepEqual(dev.faults, []);
});

test("a write in two messages lands where it was announced", () => {
  const { dev } = build();
  const at = slotRam("mfx", 50);
  ask(dev, 0x53, [...u32le(at), ...u32le(4)]);
  dev.handle([0xf0, ...dev.head, 0x54, ...syxEnc([1, 2, 3, 4]), 0xf7]);
  assert.deepEqual([...dev.peek(at, 4)], [1, 2, 3, 4]);
  assert.deepEqual(dev.faults, []);
});

test("a RAM write header acknowledges with 0x21 and the device channel", () => {
  const { dev } = build(9);
  const reply = ask(dev, 0x53, [...u32le(slotRam("mfx", 50)), ...u32le(16)]);
  assert.deepEqual(reply, [0xf0, ...dev.head, 0x21, 0xf7]);
  assert.deepEqual(dev.faults, []);
});

test("RAM write data acknowledges with 0x21 and the device channel", () => {
  const { dev } = build(9);
  const at = slotRam("mfx", 50);
  ask(dev, 0x53, [...u32le(at), ...u32le(4)]);
  const reply = dev.handle([0xf0, ...dev.head, 0x54, ...syxEnc([1, 2, 3, 4]), 0xf7]);
  assert.deepEqual(reply, [0xf0, ...dev.head, 0x21, 0xf7]);
  assert.deepEqual([...dev.peek(at, 4)], [1, 2, 3, 4]);
});

test("the wrong global channel is refused, and says so", () => {
  const { dev } = build(9);
  const reply = dev.handle([0xf0, 0x42, 0x30, 0x00, 0x01, 0x24, 0x52,
    ...syxEnc([...u32le(slotRam("mfx", 50)), ...u32le(4)]), 0xf7]);
  assert.equal(reply, null);
  assert.equal(dev.faults.at(-1).code, "channel");
});

test("an address outside the image is refused", () => {
  const { dev } = build();
  assert.equal(ask(dev, 0x52, [...u32le(0xc0800000), ...u32le(4)]), null);
  assert.equal(dev.faults.at(-1).code, "out-of-range");
});

test("a flash offset sent to the RAM command is refused", () => {
  const { dev } = build();
  assert.equal(ask(dev, 0x52, [...u32le(0x240000), ...u32le(4)]), null);
  assert.equal(dev.faults.at(-1).code, "not-ram");
});

test("data without an address in front of it is refused", () => {
  const { dev } = build();
  assert.equal(dev.handle([0xf0, ...dev.head, 0x54, ...syxEnc([1, 2]), 0xf7]), null);
  assert.equal(dev.faults.at(-1).code, "write-without-header");
});

test("a write that arrives short is named, not silently accepted", () => {
  const { dev } = build();
  const at = slotRam("mfx", 50);
  ask(dev, 0x53, [...u32le(at), ...u32le(13)]);
  // What the reference encoder produces for a length with a remainder of six:
  // the final block missing.
  const crippled = syxEnc(Array.from({ length: 13 }, (_, i) => i)).slice(0, 8);
  dev.handle([0xf0, ...dev.head, 0x54, ...crippled, 0xf7]);
  assert.equal(dev.faults.at(-1).code, "short-write");
});

test("an unknown command is named", () => {
  const { dev } = build();
  assert.equal(ask(dev, 0x7b, [0]), null);
  assert.equal(dev.faults.at(-1).code, "unknown-command");
});

test("a flash read past the edge takes the device down, as it does in the room", () => {
  const { dev } = build();
  assert.equal(ask(dev, 0x55, [...u32le(0x1000000), ...u32le(4)]), null);
  assert.equal(dev.faults.at(-1).code, "hang");
  // and it stays down, so a sweep does not quietly carry on
  assert.equal(dev.hung, true);
  assert.equal(dev.handle([0xf0, 0x42, 0x50, 0x00, 0x00, 0xf7]), null);
});

test("running code on the device is refused rather than pretended", () => {
  const { dev } = build();
  assert.equal(ask(dev, 0x57, [...u32le(0xc0000000)]), null);
  assert.equal(dev.faults.at(-1).code, "execute");
});

test("the web MIDI stand-in never writes into the image it was given", async () => {
  const { installWebMidiStub } = await import("../src/webmidi.mjs");
  const { image } = build();
  const before = Uint8Array.from(image.bytes);
  const nav = {};
  const sim = installWebMidiStub({ image, target: nav, latencyMs: 0 });
  const at = slotRam("mfx", 50);
  const out = [...sim.access.outputs.values()][0];
  out.send([0xf0, ...sim.device.head, 0x53, ...syxEnc([...u32le(at), ...u32le(4)]), 0xf7]);
  out.send([0xf0, ...sim.device.head, 0x54, ...syxEnc([9, 9, 9, 9]), 0xf7]);
  assert.deepEqual([...sim.device.peek(at, 4)], [9, 9, 9, 9]);
  assert.deepEqual(image.bytes, before);
});
