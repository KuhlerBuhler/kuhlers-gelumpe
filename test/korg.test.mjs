import { test } from "node:test";
import assert from "node:assert/strict";
import { toDisplay, toRows, makeKorg, SCREEN_W } from "../src/korg.mjs";
import { DeviceSession } from "../src/session.mjs";
import { SimDevice } from "../src/device.mjs";
import { plan, allowedRegions } from "../src/plan.mjs";
import { BLOCKS } from "../src/map/index.mjs";
import { sha256 } from "../src/firmware.mjs";
import { VsbImage } from "../src/image.mjs";
import { makeFirmware } from "./helpers.mjs";

const DISPLAY = BLOCKS.get("display").meta.ram;

test("pictures in every accepted form become the same display bytes", () => {
  const rows = Array.from({ length: 64 }, (_, y) => Array.from({ length: SCREEN_W }, (_, x) => (x === y ? "#" : ".")).join(""));
  const px = Uint8Array.from({ length: SCREEN_W * 64 }, (_, i) => (i % SCREEN_W === Math.floor(i / SCREEN_W) ? 1 : 0));
  const a = toDisplay(rows);
  assert.deepEqual(toDisplay(px), a);
  assert.deepEqual(toDisplay((x, y) => x === y), a);
  assert.deepEqual(toDisplay(a), a);
  assert.equal(a[0], 0x01, "bit 0 is the top row");
  assert.equal(a[SCREEN_W + 9], 0x02, "row 9 is the second row of page 1");
  assert.deepEqual(toRows(a), rows);
  assert.throws(() => toDisplay("x"), TypeError);
});

test("a screen write is planned into the display buffer only, and that buffer is a declared region", () => {
  const steps = plan({ kind: "screenWrite", bytes: new Uint8Array(1024) }, { channel: 0 });
  const writes = steps.filter(s => s.role === "write");
  assert.ok(writes.every(s => s.target.addr >= DISPLAY && s.target.addr + s.target.length <= DISPLAY + 1024));
  assert.equal(steps.at(-1).role, "verify");
  assert.ok(allowedRegions().some(r => r.what === "display" && r.start === DISPLAY && r.end === DISPLAY + 1024));
  assert.throws(() => plan({ kind: "screenWrite", bytes: new Uint8Array(10) }, { channel: 0 }), RangeError);
});

/** A port pair talking to a SimDevice, as the emulator would. */
async function simPort() {
  const bytes = await makeFirmware();
  const sim = new SimDevice({ image: new VsbImage(bytes), channel: 0 });
  const port = { name: "Emulator", in: { onmidimessage: null }, out: { send: data => queueMicrotask(() => { const r = sim.handle(Array.from(data)); if (r) port.in.onmidimessage?.({ data: Uint8Array.from(r) }); }) }, running: true };
  return { port, bytes };
}

test("KORG writes a picture through the gate into the emulator's display RAM and refuses any other session", async () => {
  const { port, bytes } = await simPort();
  const known = [{ version: [2, 2], label: "simulation", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: await sha256(new Uint8Array(16)) }] }];
  const session = new DeviceSession({ port, known, timeouts: { search: 200, read: 200, ack: 200, pattern: 400, global: 200 } });
  await session.connect();
  const korg = makeKorg({ session: () => session, emulator: { port, baseFirmware: bytes, button: async () => {} } });
  await korg.screen.set((x, y) => y === 0);
  const back = await korg.ram.read(DISPLAY, 128);
  assert.ok(back.every(b => b === 0x01), "the top row of page 0 is lit");
  assert.deepEqual(session.history, [], "a picture is not a change to undo or export");
  const other = makeKorg({ session: () => session, emulator: { port: {}, button: async () => {} } });
  await assert.rejects(other.screen.get(), /Emulator verbinden/);
  await assert.rejects(korg.press("nope"), /Keine Taste/);
});
