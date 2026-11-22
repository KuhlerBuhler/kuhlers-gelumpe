import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startEmulator } from "./support/emu.mjs";
import { makePattern, makePatternFile } from "./helpers.mjs";

// The emulator keeps one flash file, like the chip in the device: patterns imported with
// IMPORT ALL PATTERN are there after the service has been restarted. The backup file is built
// here; no Korg data goes onto the card.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;

const MENU = 0x09, EDIT_LEFT = 0x08, EDIT_RIGHT = 0x0c;
// MENU opens Pattern (1/32); DATA UTILITY (29/32) is the fourth page to the left, behind it come Event, BLECH and Blechy's page.
const toDataUtility = Array(4).fill(EDIT_LEFT);
const poll = ms => new Promise(r => setTimeout(r, ms));

async function until(emu, what, fn, ms = 120_000) {
  const end = Date.now() + ms;
  for (;;) {
    const got = await fn();
    if (got) return got;
    if (Date.now() > end) assert.fail(`timed out waiting for ${what}; the display shows\n${emu.screen()}`);
    await poll(100);
  }
}

const front = emu => ({
  async press(index, hold = 150, gap = 400) {
    await emu.input({ kind: "button", index, down: true });
    await emu.settle(hold);
    await emu.input({ kind: "button", index, down: false });
    await emu.settle(gap);
  },
  async value(delta) {
    await emu.input({ kind: "encoder", index: 0, delta });
    await emu.settle(500);
  },
  /** DATA UTILITY, function n of 14: MENU, Edit left to DATA UTILITY, MENU, then Edit right. */
  async dataUtility(n) {
    for (const b of [MENU, ...toDataUtility, MENU]) await this.press(b);
    for (let i = 1; i < n; i++) await this.press(EDIT_RIGHT, 120, 250);
  },
});

/** A backup file the firmware accepts: header with KORG / e2sampler, the globals block with its GLED mark, 250 framed patterns. */
function backup() {
  const file = makePatternFile(250);
  file.fill(0xff, 0x24, 0x10100);
  file[0x20] = 1;
  file.set([0x47, 0x4c, 0x45, 0x44], 0x1fc);
  file.set(makePattern({ name: "PERSIST6" }), 0x10100 + 5 * 0x4000);
  return file;
}

test("flash: patterns imported once are there after a restart of the emulator", { skip }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-flash-"));
  const sdDir = join(dir, "sd");
  const flashFile = join(dir, "flash", "flash.bin");
  const prepare = ({ withBackup }) => async ({ request }) => {
    if (withBackup) {
      rmSync(join(sdDir, "card", "KORG"), { recursive: true, force: true });   // the import browser opens on the card root
      writeFileSync(join(sdDir, "card", "backup.e2sallpat"), backup());
    }
    assert.equal((await request("POST", "/sd/insert", "{}")).status, 200);
  };
  let emu = await startEmulator(vsb, { sdDir, prepare: prepare({ withBackup: true }) });
  try {
    const panel = front(emu);
    await panel.dataUtility(4);
    await panel.press(MENU, 150, 1500);                                // IMPORT ALL PATTERN: the browser lists KORG first
    await panel.value(1);                                              // onto the backup
    for (let i = 0; i < 2; i++) await panel.press(MENU, 150, 1500);   // the file, confirm
    // Patterns sit in the flash at 0x240000, one 0x4000 block each, in the order of the backup. Stop only after the last
    // one: power off in the middle leaves the pattern being written half old, half new.
    const patterns = backup().subarray(0x10100);
    await until(emu, "the flash to hold all imported patterns", async () => existsSync(flashFile) &&
      readFileSync(flashFile).subarray(0x240000, 0x240000 + patterns.length).equals(patterns), 600_000);
    assert.equal(statSync(flashFile).size, 0x1000000);
    await emu.stop();

    // A new service over the same folders: the firmware boots from the flash file, with no import this time.
    emu = await startEmulator(vsb, { sdDir, prepare: prepare({ withBackup: false }) });
    const panel2 = front(emu);
    await panel2.dataUtility(2);                                       // EXPORT ALL PATTERN
    await panel2.press(MENU, 150, 1000);
    await panel2.press(MENU, 150, 1000);
    const exported = await until(emu, "the exported pattern backup", async () => {
      const where = join(sdDir, "card", "KORG");
      if (!existsSync(where)) return null;
      for (const folder of readdirSync(where)) {
        const dir = join(where, folder, "Patterns");
        const name = existsSync(dir) && readdirSync(dir).find(n => n.endsWith(".e2sallpat"));
        if (name && statSync(join(dir, name)).size === backup().length) return join(dir, name);
      }
      return null;
    });
    assert.ok(readFileSync(exported).includes("PERSIST6"), "pattern 6 of the import is in the new export");
  } finally {
    await emu.stop();
    rmSync(dir, { recursive: true, force: true });
  }
});
