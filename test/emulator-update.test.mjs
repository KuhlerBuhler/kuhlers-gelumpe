import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { applyPatches } from "../src/patch.mjs";
import { startEmulator } from "./support/emu.mjs";

// The trial of the Patcher page, end to end in the emulator: the user's own file runs, the patched copy sits on the
// virtual card where that firmware looks for it, SOFTWARE UPDATE flashes it and the restart runs the patched firmware.
// Needs the user's own file (E2_VSB for Hacktribe's build, E2_STOCK_VSB for Korg's original).
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const SET = JSON.parse(readFileSync(new URL("../data/patches/blech.json", import.meta.url), "utf8"));
const patches = SET.patches.map(p => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url), "utf8")));
const MENU = 0x09, EDIT_LEFT = 0x08, EDIT_RIGHT = 0x0c;
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const until = async (what, ok, ms = 60_000) => {
  const end = Date.now() + ms;
  while (!ok()) {
    if (Date.now() > end) throw new Error(`waited for ${what}`);
    await new Promise(r => setTimeout(r, 20));
  }
};

for (const [name, source, folder] of [
  ["Hacktribe 2.02", process.env.E2_VSB, "hacktribe"],
  ["Korg's original 2.02", process.env.E2_STOCK_VSB, "electribe sampler"],
]) {
  const skip = !local ? "emulation only runs in test:local or test:emu" : !source ? "the firmware file is not set" : false;
  describe(`the update test on the page, with ${name}`, { skip }, () => {
    test("SOFTWARE UPDATE installs the patched file from the card and the restart runs it", async () => {
      const original = new Uint8Array(readFileSync(source));
      const res = await applyPatches(original, patches);
      assert.equal(res.ok, true, res.reasons.join(" "));
      const patched = res.bytes;
      const emu = await startEmulator(source, {
        bootSeconds: 1,
        prepare: async ({ request }) => {      // what rehearseUpdate does: the user's own file, then the patched copy on the card
          await request("POST", "/firmware", original);
          const put = await request("POST", "/sd/system", patched);
          assert.equal(put.status, 200);
          assert.equal(put.body.korg, folder, "the file goes where the running firmware looks");
        },
      });
      try {
        assert.equal(emu.status.firmware.sha256, sha(original.subarray(0x100)), "the trial starts with the user's own file");
        assert.deepEqual(readFileSync(join(emu.cards, "card", "KORG", folder, "System", "SYSTEM.VSB")), Buffer.from(patched));
        assert.equal(existsSync(join(emu.cards, "card", "KORG", folder, "SYSTEM-vorher.VSB")), false, "nothing was replaced on the card");
        await emu.settle(2000);
        const press = async (index, hold = 150, gap = 400) => {
          await emu.input({ kind: "button", index, down: true });
          await emu.settle(hold);
          await emu.input({ kind: "button", index, down: false });
          await emu.settle(gap);
        };
        for (const b of [MENU, EDIT_LEFT, EDIT_LEFT, MENU]) await press(b);
        for (let i = 1; i < 14; i++) await press(EDIT_RIGHT, 120, 250);
        for (let i = 0; i < 3; i++) await press(MENU, 150, 1200);      // versions, "Are You Sure ?", the update
        await emu.settle(8000);
        const flash = () => readFileSync(join(emu.cards, "flash", "flash.bin"));
        await until("the flash to hold the patched firmware", () => sha(flash().subarray(0x20000, 0x220000)) === sha(patched.subarray(0x100)));

        // The device is asked to restart: the firmware lets go of the power, then the key starts it again.
        await emu.input({ kind: "power", down: true });
        await until("the device to switch off", () => emu.status.state === "off", 30_000);
        await emu.input({ kind: "power", down: true });          // the key of a switched-off device starts it
        await until("the restart", () => emu.status.state === "running" && emu.status.booted, 60_000);
        assert.equal(emu.status.firmware.sha256, sha(patched.subarray(0x100)), "after the restart the patched firmware runs");
        assert.notEqual(emu.status.firmware.sha256, sha(original.subarray(0x100)));
        assert.equal(emu.status.error, null);
      } finally {
        await emu.stop();
      }
    });
  });
}
