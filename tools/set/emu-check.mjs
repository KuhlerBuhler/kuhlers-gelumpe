#!/usr/bin/env node
/**
 * Shows that the emulated device takes a pattern set with transitions in it:
 * the set goes on a virtual SD card, DATA UTILITY > IMPORT ALL PATTERN reads
 * it, and the main screen is photographed for each pattern given. The user's
 * own firmware and flash are needed; nothing is written outside --out and a
 * temporary card folder.
 *
 *   E2_VSB=SYSTEM.VSB E2_FLASH=flash_full.bin node tools/set/emu-check.mjs NEW.e2sallpat --show 190,201,202,192 --out DIR
 */
import { readFileSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { startEmulator } from "../../test/support/emu.mjs";
import { displaySheet } from "./png.mjs";

const MENU = 0x09, EDIT_LEFT = 0x08, EDIT_RIGHT = 0x0c, EXIT = 0x0d;
const settle = ms => new Promise(r => setTimeout(r, ms));

const args = process.argv.slice(2);
const opt = name => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : undefined; };
const setPath = args[0];
const show = (opt("show") ?? "").split(",").filter(Boolean).map(Number);
const out = resolve(opt("out") ?? ".");
if (!process.env.E2_VSB || !process.env.E2_FLASH || !setPath || !show.length) {
  console.error("usage: E2_VSB=... E2_FLASH=... node tools/set/emu-check.mjs NEW.e2sallpat --show 190,201,202,192 [--out DIR]");
  process.exit(2);
}
mkdirSync(out, { recursive: true });

const emu = await startEmulator(process.env.E2_VSB, {
  bootSeconds: 12,
  prepare: async ({ post, request }) => {
    await post("/flash", readFileSync(process.env.E2_FLASH));
    await post("/sd/cards", JSON.stringify({ name: "set", insert: true, size_mb: 128 }));
    const put = await request("PUT", "/sd/file?path=/SET.e2sallpat", readFileSync(setPath));
    if (put.status !== 200) throw new Error(`card upload failed: ${JSON.stringify(put.body)}`);
  },
});
const press = async (index, hold = 150, gap = 400) => {
  await emu.input({ kind: "button", index, down: true }); await settle(hold);
  await emu.input({ kind: "button", index, down: false }); await settle(gap);
};
const turn = async delta => { await emu.input({ kind: "encoder", index: 0, delta }); await settle(350); };

try {
  for (const b of [MENU, EDIT_LEFT, EDIT_LEFT, MENU]) await press(b);
  for (let i = 1; i < 4; i++) await press(EDIT_RIGHT, 120, 250);
  await press(MENU); await settle(2000);
  await press(MENU); await settle(2000);
  await press(MENU); await settle(40_000);
  if (emu.status.state === "crashed") throw new Error(`the emulated device crashed: ${emu.status.error}`);
  for (let i = 0; i < 3; i++) await press(EXIT, 150, 1000);

  const shots = [];
  let at = 1;
  for (const n of show) {
    for (let d = n - at; d !== 0; d = n - at) {
      const step = Math.max(-10, Math.min(10, d));
      await turn(step);
      at += step;
    }
    await settle(800);
    shots.push(Uint8Array.from(emu.rawDisplay()));
  }
  displaySheet(shots, join(out, "emulator-anzeige.png"));
  console.log(`${show.length} Anzeigen nach ${join(out, "emulator-anzeige.png")}; Zustand des Geräts: ${emu.status.state}`);
} finally {
  await emu.stop();
}
