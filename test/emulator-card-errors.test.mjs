import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startEmulator } from "./support/emu.mjs";
import { slots } from "./support/spawn.mjs";

// The virtual card as a card that is not the plain SDHC one (docs/emulator.md, "Fehlerfälle der Karte"): an old SDSC card,
// a locked card, a card whose writes fail. Options go to POST /sd/insert and POST /sd/card, the firmware is driven from the
// front panel, the proof is what reaches the card folder. EXPORT ALL PATTERN is the probe: it writes about 4 MB.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : false;

const MENU = 0x09, EDIT_LEFT = 0x08, EDIT_RIGHT = 0x0c, EXIT = 0x0d;
const poll = ms => new Promise(r => setTimeout(r, ms));

async function until(emu, what, fn, ms = 90_000) {
  const end = Date.now() + ms;
  for (;;) {
    const got = await fn();
    if (got) return got;
    if (Date.now() > end) assert.fail(`timed out waiting for ${what}; the display shows\n${emu.screen()}`);
    await poll(100);
  }
}

const press = async (emu, index, hold = 150, gap = 400) => {
  await emu.input({ kind: "button", index, down: true });
  await emu.settle(hold);
  await emu.input({ kind: "button", index, down: false });
  await emu.settle(gap);
};
/** EXPORT ALL PATTERN: DATA UTILITY, function 2, ENTER. */
const exportAllPattern = async emu => {
  for (const b of [MENU, EDIT_LEFT, EDIT_LEFT, MENU, EDIT_RIGHT, MENU]) await press(emu, b, 120, 300);
};
const korg = (emu, ...rest) => join(emu.cards, "card", "KORG", emu.status.firmware?.folder ?? "hacktribe", ...rest);
const backup = emu => existsSync(korg(emu)) && readdirSync(korg(emu)).find(n => n.endsWith(".e2sallpat"));
const sd = async emu => (await emu.request("GET", "/sd")).body;
const insert = (emu, options = {}) => emu.request("POST", "/sd/insert", JSON.stringify(options));

async function withEmulator(fn) {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-card-"));
  const emu = await startEmulator(vsb, { sdDir: join(dir, "sd") });
  try {
    await fn(emu);
  } finally {
    await emu.stop();
    rmSync(dir, { recursive: true, force: true });
  }
}

describe("virtual card faults", { concurrency: slots }, () => {
  test("an SDSC card takes byte addresses and the firmware writes its backup on it", { skip }, async () => {
    await withEmulator(async emu => {
      const put = await insert(emu, { kind: "sdsc" });
      assert.equal(put.status, 200, JSON.stringify(put.body));
      assert.equal(put.body.card.kind, "sdsc");
      await exportAllPattern(emu);
      const name = await until(emu, "the pattern backup in the card folder", async () => {
        const n = backup(emu);
        return n && statSync(korg(emu, n)).size > 1_000_000 ? n : null;
      }, 120_000);
      await until(emu, "the card to be idle", async () => !(await sd(emu)).busy, 30_000);
      assert.ok(statSync(korg(emu, name)).size > 1_000_000, "the backup arrived whole through byte addresses");
      assert.equal((await sd(emu)).card.kind, "sdsc");
    });
  });

  test("a locked card: the export writes nothing, with the lock off the same export writes the backup", { skip }, async () => {
    await withEmulator(async emu => {
      assert.equal((await insert(emu, { writeProtect: true })).status, 200);
      await exportAllPattern(emu);
      await emu.settle(3000);
      let state = await sd(emu);
      assert.equal(state.card.writeProtect, true);
      assert.equal(state.stats.written, 0, "the firmware sent no write command to a locked card");
      assert.equal(backup(emu), undefined);
      const off = await emu.request("POST", "/sd/card", JSON.stringify({ writeProtect: false }));
      assert.equal(off.status, 200, JSON.stringify(off.body));
      await press(emu, EXIT, 150, 800);        // the box "Card Write Protected" goes
      await press(emu, MENU, 120, 300);
      await until(emu, "the backup after the lock came off", async () => {
        const n = backup(emu);
        return n && statSync(korg(emu, n)).size > 1_000_000 ? n : null;
      }, 120_000);
      state = await sd(emu);
      assert.ok(state.stats.written > 1000);
    });
  });

  test("a card that refuses the writes: the backup does not arrive and the fault says how often it hit", { skip }, async () => {
    await withEmulator(async emu => {
      assert.equal((await insert(emu)).status, 200);
      const set = await emu.request("POST", "/sd/card", JSON.stringify({ faults: [{ kind: "write_crc" }] }));
      assert.equal(set.status, 200, JSON.stringify(set.body));
      await exportAllPattern(emu);
      await until(emu, "the fault to hit", async () => (await sd(emu)).card.faults[0].hits > 0, 60_000);
      await emu.settle(8000);                  // the firmware gives up with "Card Error"
      await until(emu, "the card to be idle", async () => !(await sd(emu)).busy, 30_000);
      const n = backup(emu);
      assert.ok(!n || statSync(korg(emu, n)).size < 1_000_000, "no complete backup on a card that refused every block");
    });
  });

  test("bad card options are refused and change nothing", { skip }, async () => {
    await withEmulator(async emu => {
      for (const bad of [{ kind: "mmc" }, { writeProtect: "yes" }, { faults: [{ kind: "melt" }] }, { colour: 1 }]) {
        const r = await insert(emu, bad);
        assert.equal(r.status, 400, JSON.stringify(bad));
      }
      assert.equal((await sd(emu)).inserted, false);
      assert.equal((await emu.request("POST", "/sd/card", "{}")).status, 409, "no card in");
    });
  });
});
