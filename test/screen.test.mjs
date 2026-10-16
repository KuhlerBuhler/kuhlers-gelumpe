import { test } from "node:test";
import assert from "node:assert/strict";
import { readScreen, readContext } from "../src/screen.mjs";
import { u32le } from "../src/bytes.mjs";

/** A RAM made of aligned words, read the way the device answers a RAM read. */
function ram(words) {
  return async (addr, length) => {
    const out = new Uint8Array(length);
    for (let i = 0; i < length; i++) out[i] = u32le(words[addr + i - ((addr + i) % 4)] ?? 0)[(addr + i) % 4];
    return out;
  };
}

const MANAGER = 0xc06c2210;
const SCREEN = 0xc06ca6a0;

test("the MFX TYPE page of the pattern menu is read through the screen manager", async () => {
  const s = await readScreen(ram({ 0xc03404c0: MANAGER, [MANAGER + 0x20]: SCREEN, [MANAGER + 0x2c]: 3, [MANAGER + 0x30]: 46, [SCREEN + 0x2c]: 5 }));
  assert.deepEqual(s, { mode: 3, name: { de: "Menü Pattern", en: "Pattern menu" }, page: 5, pageName: "MFX TYPE", overlay: null });
});

test("the IFX TYPE window shows as an overlay on the main screen, without a page", async () => {
  const s = await readScreen(ram({ 0xc03404c0: MANAGER, [MANAGER + 0x20]: SCREEN, [MANAGER + 0x24]: 0xc06cb2e0, [MANAGER + 0x2c]: 1, [MANAGER + 0x30]: 23, [SCREEN + 0x2c]: 0xc06ca6b0 }));
  assert.equal(s.page, null);
  assert.deepEqual(s.overlay, { kind: 23, name: { de: "IFX TYPE", en: "IFX TYPE" } });
});

test("an unknown screen number and a page past the list stay unnamed", async () => {
  const s = await readScreen(ram({ 0xc03404c0: MANAGER, [MANAGER + 0x20]: SCREEN, [MANAGER + 0x2c]: 99 }));
  assert.deepEqual([s.mode, s.name, s.page], [99, null, null]);
  const far = await readScreen(ram({ 0xc03404c0: MANAGER, [MANAGER + 0x20]: SCREEN, [MANAGER + 0x2c]: 7, [SCREEN + 0x2c]: 8 }));
  assert.equal(far.page, null);
});

test("a manager pointer outside RAM is refused instead of read", async () => {
  await assert.rejects(readScreen(ram({ 0xc03404c0: 0 })), /outside RAM/);
});

const PATTERN = 0xc06b2798;
const base = { 0xc03404c0: MANAGER, [MANAGER + 0x20]: SCREEN, 0xc0348880: 0xc06c41c0, 0xc033e6a4: PATTERN };

test("on MFX TYPE the context names the pattern's master effect, numbered as the display", async () => {
  const words = { ...base, [MANAGER + 0x2c]: 3, [SCREEN + 0x2c]: 5, [0xc06c41c0 + 0x14]: 2 };
  words[PATTERN + 4 + 60] = 1 << 8;                // byte 61 of the pattern block = 1
  const c = await readContext(ram(words));
  assert.deepEqual([c.part, c.fx], [2, { kind: "mfx", slot: 2 }]);
});

test("with the IFX TYPE window the context names the selected part's insert", async () => {
  const words = { ...base, [MANAGER + 0x2c]: 1, [MANAGER + 0x24]: 0xc06cb2e0, [MANAGER + 0x30]: 23, [0xc06c41c0 + 0x14]: 1 };
  const at = PATTERN + 4 + 0x800 + 33 + 0x330;     // part 2, IFX type
  words[at - (at % 4)] = 15 * 2 ** (8 * (at % 4));
  const c = await readContext(ram(words));
  assert.deepEqual([c.part, c.fx], [1, { kind: "ifx", slot: 16 }]);
});

test("other screens carry no effect", async () => {
  const c = await readContext(ram({ ...base, [MANAGER + 0x2c]: 3, [SCREEN + 0x2c]: 4 }));
  assert.equal(c.fx, null);
});
