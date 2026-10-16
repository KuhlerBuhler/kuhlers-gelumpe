import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { accessSync, constants, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startEmulator } from "./support/emu.mjs";
import { slots } from "./support/spawn.mjs";

// The virtual SD card with the user's firmware, driven through the card folder on the host, the
// service's /sd routes and the front panel, the way the page does it (docs/hintergrund/virtuelle-sd.md).
// The WAV files here are generated; no Korg data goes onto a card.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;

const MENU = 0x09, EDIT_LEFT = 0x08, EDIT_RIGHT = 0x0c, EXIT = 0x0d;
const poll = ms => new Promise(r => setTimeout(r, ms));

function wav(frames = 4800, rate = 48000) {
  const out = new Uint8Array(44 + frames * 2);
  const v = new DataView(out.buffer);
  const text = (at, s) => [...s].forEach((c, i) => { out[at + i] = c.charCodeAt(0); });
  text(0, "RIFF"); v.setUint32(4, 36 + frames * 2, true); text(8, "WAVEfmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  text(36, "data"); v.setUint32(40, frames * 2, true);
  for (let i = 0; i < frames; i++) v.setInt16(44 + i * 2, Math.round(12000 * Math.sin(2 * Math.PI * 440 * i / rate)), true);
  return out;
}

async function until(emu, what, fn, ms = 90_000) {
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
  /** DATA UTILITY, function n of 14: MENU, Edit left twice, MENU, then Edit right. */
  async dataUtility(n) {
    for (const b of [MENU, EDIT_LEFT, EDIT_LEFT, MENU]) await this.press(b);
    for (let i = 1; i < n; i++) await this.press(EDIT_RIGHT, 120, 250);
  },
});

const folderOf = emu => join(emu.cards, "card");
// The folder below KORG/ is the loaded firmware's own: "hacktribe", or "electribe sampler" in Korg's original.
const korg = (emu, ...rest) => join(folderOf(emu), "KORG", emu.status.firmware?.folder ?? "hacktribe", ...rest);
const writable = path => { try { accessSync(path, constants.W_OK); return true; } catch { return false; } };
/** An exported file the card folder has once the firmware closed it: the mirror may show it empty first. */
const mirrored = (path, size) => existsSync(path) && statSync(path).size > 0 && (!size || statSync(path).size === size) ? statSync(path) : null;
const idle = emu => until(emu, "the card to be idle", async () => !(await emu.request("GET", "/sd")).body.busy, 30_000);
// The IMPORT SAMPLE browser opens on the card root, and the key sequences below assume the one WAV (or
// folder) is its only entry; the empty KORG layout would be the first one (measured, 2026-10-13).
const noLayout = sdDir => rmSync(join(sdDir, "card", "KORG"), { recursive: true, force: true });
const insert = (emu, inserted = true) => emu.request("POST", inserted ? "/sd/insert" : "/sd/eject", "{}");

describe("virtual card", { concurrency: slots }, () => {
  test("virtual card: a WAV put into the card folder imports, exports reach the folder, and the folder is the card after a restart", { skip }, async () => {
    const dir = mkdtempSync(join(tmpdir(), "gelumpe-card-"));
    const sdDir = join(dir, "sd");
    const source = wav();
    let emu = await startEmulator(vsb, {
      sdDir,
      prepare: async ({ request }) => {
        noLayout(sdDir);
        writeFileSync(join(sdDir, "card", "my kick.wav"), source);
        const put = await request("POST", "/sd/insert", "{}");
        assert.equal(put.status, 200, JSON.stringify(put.body));
      },
    });
    try {
      assert.equal(emu.status.card?.name, "SD-Karte");
      assert.equal(writable(folderOf(emu)), false, "the inserted card is write-protected");
      const panel = front(emu);

      // IMPORT SAMPLE: the browser shows the one WAV; open it, take slot 501.
      await panel.dataUtility(9);
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      await emu.settle(8000);

      // EXPORT SAMPLE: the exported file, in the folder the firmware names, is the proof that the import worked.
      await panel.press(EXIT);
      await panel.press(EDIT_RIGHT, 120, 300);
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      await until(emu, "the exported WAV in the card folder", async () => mirrored(korg(emu, "Sample", "501_my kick.wav"), 10832));
      await idle(emu);
      const wavOut = readFileSync(korg(emu, "Sample", "501_my kick.wav"));
      assert.equal(wavOut.subarray(0, 4).toString(), "RIFF");
      assert.equal(wavOut.readUInt32LE(24), 48000, "sample rate");
      assert.ok(wavOut.includes("my kick"), "the name travels in the korg chunk");

      // EXPORT ALL PATTERN: the whole pattern memory as one backup file.
      await panel.press(EXIT);
      for (let i = 0; i < 8; i++) await panel.press(EDIT_LEFT, 120, 250);
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      const backup = await until(emu, "the pattern backup", async () => readdirSync(korg(emu)).find(n => n.endsWith(".e2sallpat") && mirrored(korg(emu, n))), 120_000);
      await idle(emu);
      await until(emu, "the whole backup", async () => statSync(korg(emu, backup)).size > 1_000_000);

      // Switch off: the card is still in, still protected, and the folder holds everything.
      assert.equal((await emu.request("POST", "/stop")).status, 200);
      assert.equal(writable(folderOf(emu)), false);
      assert.equal(readFileSync(join(folderOf(emu), "my kick.wav")).length, source.length);

      // Take it out: the folder is free again.
      assert.equal((await insert(emu, false)).status, 200);
      assert.equal(writable(folderOf(emu)), true);

      // The service goes away and comes back: the folder is the card, and it is out.
      await emu.stop();
      emu = await startEmulator(vsb, { sdDir });
      assert.equal(emu.status.card, null);
      assert.equal(readFileSync(korg(emu, "Sample", "501_my kick.wav")).includes("my kick"), true);
      assert.equal(writable(folderOf(emu)), true);
    } finally {
      await emu.stop();
      rmSync(dir, { recursive: true, force: true });
    }
  });

  test("virtual card: a folder in the card folder boots, the firmware browses into it and imports from it", { skip }, async () => {
    const dir = mkdtempSync(join(tmpdir(), "gelumpe-card-"));
    const sdDir = join(dir, "sd");
    const emu = await startEmulator(vsb, {
      sdDir,
      prepare: async ({ request }) => {
        noLayout(sdDir);
        mkdirSync(join(sdDir, "card", "drums"), { recursive: true });
        writeFileSync(join(sdDir, "card", "drums", "snare hit.wav"), wav(4800));
        assert.equal((await request("POST", "/sd/insert", "{}")).status, 200);
      },
    });
    try {
      const panel = front(emu);
      await panel.dataUtility(9);
      await panel.press(MENU);                 // the browser starts at the card root: folder drums
      await emu.settle(1000);
      await panel.press(MENU);                 // into drums: Upper Folder, then the file
      await emu.settle(1000);
      await panel.value(1);                    // onto the file
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      await emu.settle(8000);
      await panel.press(EXIT);
      await panel.press(EDIT_RIGHT, 120, 300);
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      const exported = await until(emu, "the exported WAV", async () => mirrored(korg(emu, "Sample", "501_snare hit.wav"), 10832));
      assert.equal(exported.size, 10832);
      assert.ok(existsSync(join(folderOf(emu), "drums", "snare hit.wav")), "the file is still where it was");
    } finally {
      await emu.stop();
      rmSync(dir, { recursive: true, force: true });
    }
  });

  // The firmware polls the card-detect input (GPIO 4.1) and shows a card symbol left of the battery
  // (columns 108 to 115 of the top two display pages, measured 2026-10-13).
  const cardSymbol = emu => {
    const raw = emu.rawDisplay();
    return [0, 1].some(page => raw.subarray(page * 128 + 108, page * 128 + 116).some(b => b));
  };

  test("virtual card: inserted while the device runs, the firmware sees it and imports from it; pulled, the symbol goes", { skip }, async () => {
    const dir = mkdtempSync(join(tmpdir(), "gelumpe-card-"));
    const sdDir = join(dir, "sd");
    const emu = await startEmulator(vsb, {
      sdDir,
      prepare: async () => {
        noLayout(sdDir);
        writeFileSync(join(sdDir, "card", "my kick.wav"), wav());
      },
    });
    try {
      const panel = front(emu);
      for (const b of [MENU, EDIT_LEFT, EDIT_LEFT]) await panel.press(b);   // the DATA UTILITY page, whose top row is quiet
      await emu.settle(1000);
      assert.equal(cardSymbol(emu), false, "no card, no symbol");
      assert.equal((await insert(emu)).status, 200);
      await until(emu, "the card symbol", async () => cardSymbol(emu), 20_000);
      await panel.press(MENU);                   // IMPORT SAMPLE lists the card that was put in while running
      for (let i = 1; i < 9; i++) await panel.press(EDIT_RIGHT, 120, 250);
      await panel.press(MENU, 150, 1500);        // the browser: KORG, which the firmware made on mounting, then the WAV
      await emu.input({ kind: "encoder", index: 0, delta: 1 });
      await emu.settle(500);
      await panel.press(MENU, 150, 1000);
      await panel.press(MENU);
      await emu.settle(8000);
      await panel.press(EXIT);
      await panel.press(EDIT_RIGHT, 120, 300);   // EXPORT SAMPLE: the exported file proves the import
      await panel.press(MENU);
      await emu.settle(1000);
      await panel.press(MENU);
      await until(emu, "the exported WAV", async () => mirrored(korg(emu, "Sample", "501_my kick.wav"), 10832));
      await idle(emu);

      await panel.press(EXIT);
      await emu.settle(1000);
      assert.equal(cardSymbol(emu), true, "still in");
      assert.equal((await insert(emu, false)).status, 200);
      await until(emu, "the card symbol to go", async () => !cardSymbol(emu), 20_000);
      assert.equal(writable(folderOf(emu)), true, "the folder is free again");
      assert.ok(existsSync(korg(emu, "Sample", "501_my kick.wav")), "what the firmware wrote is in the folder");
    } finally {
      await emu.stop();
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
