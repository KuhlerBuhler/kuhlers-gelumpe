import { test } from "node:test";
import assert from "node:assert/strict";
import { readLeds } from "../src/leds.mjs";
import { u32le } from "../src/bytes.mjs";

const POINTER = 0xc0345a1c;
const MANAGER = 0xc06c2288;
const TABLE = MANAGER + 0x88c;
const COUNT = 0x4c;

/** A device whose LED manager is at `manager`, with `lit` (number to brightness) in its table; counts the reads. */
function device(manager, lit, { numbered = true } = {}) {
  const table = new Uint8Array(0x4b * 8 + 3);
  for (let i = 0; i < COUNT; i++) table[i * 8] = numbered ? i : 0xff;
  for (const [i, v] of Object.entries(lit)) table[i * 8 + 2] = v;
  const reads = [];
  const read = async (addr, length) => {
    reads.push([addr, length]);
    if (addr === POINTER) return Uint8Array.from(u32le(manager));
    if (addr === TABLE && manager === MANAGER) return table;
    return new Uint8Array(length).fill(0xff);
  };
  return { read, reads };
}

test("the lit LEDs come out of one table read after the pointer", async () => {
  const { read, reads } = device(MANAGER, { 0: 255, 0x09: 255, 0x15: 120, 0x4b: 5 });
  const res = await readLeds(read);
  assert.deepEqual(res.leds, { 0: 255, 9: 255, 21: 120, 75: 5 });
  assert.equal(res.at, TABLE);
  assert.deepEqual(reads, [[POINTER, 4], [TABLE, 0x4b * 8 + 3]]);
});

test("with the address of an earlier call it is a single read", async () => {
  const { read, reads } = device(MANAGER, { 2: 255 });
  const res = await readLeds(read, TABLE);
  assert.deepEqual(res.leds, { 2: 255 });
  assert.deepEqual(reads, [[TABLE, 0x4b * 8 + 3]]);
});

test("a stale address is looked up again once", async () => {
  const { read, reads } = device(MANAGER, { 2: 255 });
  const res = await readLeds(read, TABLE + 0x100);
  assert.deepEqual(res.leds, { 2: 255 });
  assert.equal(res.at, TABLE);
  assert.deepEqual(reads.map(r => r[0]), [TABLE + 0x100, POINTER, TABLE]);
});

test("a table whose entries are not numbered is no LED table", async () => {
  const { read } = device(MANAGER, { 2: 255 }, { numbered: false });
  await assert.rejects(readLeds(read), /nicht zu erkennen/);
});

test("a pointer outside RAM is refused before the table is read", async () => {
  const { read, reads } = device(0, {});
  await assert.rejects(readLeds(read), /outside RAM/);
  assert.equal(reads.length, 1);
});
