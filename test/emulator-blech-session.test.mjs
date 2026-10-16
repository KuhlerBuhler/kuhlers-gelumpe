import { describe, test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { applyPatches } from "../src/patch.mjs";
import { DeviceSession } from "../src/session.mjs";
import { identify } from "../src/firmware.mjs";
import { VsbImage } from "../src/image.mjs";
import { buildProfile } from "../src/profile.mjs";
import { readUnits } from "../src/node.mjs";
import { TIMEOUTS } from "../src/sender.mjs";
import { recordOf, pointersMatch, RECORD } from "../src/presets.mjs";
import { tableEntry } from "../src/map/address.mjs";
import { STOCK_SLOTS } from "../src/profile.mjs";
import { startEmulator } from "./support/emu.mjs";

// The editor's session on the emulator with BLECH's own SysEx commands, on Hacktribe's firmware and on Korg's original
// (docs/messungen/2026-10-15-blech-sysex.md): it prefers them, knows the build by its signatures, and on the original
// reads the RAM and writes the display, which Korg's build alone does not answer.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const SET = JSON.parse(readFileSync(new URL("../data/patches/blech.json", import.meta.url), "utf8"));
const patches = SET.patches.map(p => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url), "utf8")));
const PATIENT = Object.fromEntries(Object.entries(TIMEOUTS).map(([kind, ms]) => [kind, kind === "quiet" ? ms : ms * 10]));

describe("a session on the emulator with BLECH", { concurrency: 2 }, () => {
  for (const [name, source, expected] of [
    ["Hacktribe 2.02", process.env.E2_VSB, { build: "hacktribe", hacktribe: true }],
    ["Korg's original 2.02", process.env.E2_STOCK_VSB, { build: "stock", hacktribe: false }],
  ]) {
    const skip = !local ? "emulation only runs in test:local or test:emu" : !source ? "the firmware file is not set" : false;
    describe(name, { skip, concurrency: 1 }, () => {
      let emu;
      let directory;
      let bytes;
      before(async () => {
        directory = mkdtempSync(join(tmpdir(), "gelumpe-blech-session-"));
        const res = await applyPatches(new Uint8Array(readFileSync(source)), patches);
        assert.equal(res.ok, true, res.reasons.join(" "));
        bytes = res.bytes;
        const path = join(directory, "SYSTEM.VSB");
        writeFileSync(path, bytes);
        emu = await startEmulator(path);
        await emu.settle(8000);
      });
      after(async () => { await emu?.stop(); rmSync(directory, { recursive: true, force: true }); });

      const connect = async () => {
        const s = new DeviceSession({ port: emu.port, timeouts: PATIENT });
        const device = await s.connect();
        const units = readUnits();
        s.useFirmware(bytes, await identify(bytes), { units, profile: buildProfile(new VsbImage(bytes), units, expected.build === "stock" ? STOCK_SLOTS : undefined) });
        return { s, device };
      };

      test("it answers INFO, is told apart by its code, and RAM goes through BLECH", async () => {
        const { device } = await connect();
        assert.equal(device.ram, "blech");
        assert.deepEqual([device.build, device.hacktribe, device.versionKnown], [expected.build, expected.hacktribe, true]);
        assert.equal(device.blech.maxBlock, 0x8000);
        assert.equal(device.blech.tableMatches, true, "the protection table in the device is the one the editor cuts from data/protected.mjs");
      });

      test("a read of 4 KiB, with its CRC, is what the RAM holds", async () => {
        const { s } = await connect();
        const read = await s.readRamBlock(0xc0000100, 4096);
        assert.deepEqual(Uint8Array.from(read), bytes.subarray(0x200, 0x200 + 4096), "the image where the firmware does not change it");
      });

      test("a picture goes into the display in one block and is read back by the same run", async () => {
        const { s } = await connect();
        const picture = Uint8Array.from({ length: 1024 }, (_, i) => (i * 3) & 0xff);
        const res = await s.apply({ kind: "screenWrite", bytes: picture }, { confirmed: true });
        assert.equal(res.ok, true, res.error?.message ?? JSON.stringify(res.gate?.reasons));
        assert.equal(res.gate.verdict !== "blocked", true);
      });

      test("an effect record is read, written and read back through BLECH where the build keeps it, and taken back", async () => {
        const { s } = await connect();
        const stockBuild = expected.build === "stock";
        // Korg's build keeps its records where its pointer arrays say; the device's arrays have to be the file's first
        assert.equal(await pointersMatch(bytes, (addr, length) => s.readRamBlock(addr, length)), true, "the device's pointer arrays are the file's");
        const ram = stockBuild ? recordOf(bytes, "ifx", 1).ram : tableEntry("table.ifx", 0).ram;
        const before = Uint8Array.from(await s.readRamBlock(ram, RECORD));
        assert.deepEqual(before, bytes.subarray(ram - 0xc0000000 + 0x100, ram - 0xc0000000 + 0x100 + RECORD), "the record in the running firmware is the file's");
        const after = Uint8Array.from(before);
        after[1] = after[1] === 0x58 ? 0x59 : 0x58;
        const edit = { kind: "fxRecord", table: "ifx", slot: 1, bytes: after, before, ...(stockBuild ? { ram } : {}) };
        const res = await s.apply(edit, { confirmed: true });
        assert.equal(res.ok, true, res.error?.message ?? JSON.stringify(res.gate?.reasons));
        assert.deepEqual(Uint8Array.from(await s.readRamBlock(ram, RECORD)), after);
        assert.equal((await s.undo()).ok, true);
        assert.deepEqual(Uint8Array.from(await s.readRamBlock(ram, RECORD)), before);
        // the other build's grid: a whole record of it lies across two of this build's, and the device says no
        await assert.rejects(s.sender.blechWrite(stockBuild ? 0xc00a80f0 : 0xc00a816c, new Uint8Array(RECORD)), e => e.kind === "protected");
      });

      test("the device's own refusal reaches the editor with the reason, past the editor's own check", async () => {
        const { s } = await connect();
        await assert.rejects(s.sender.blechWrite(0xc0100000, new Uint8Array(16)), e => e.kind === "protected" && /verweigert/.test(e.message));
        await assert.rejects(s.sender.blechRead(0xc7fffff0, 32), e => e.kind === "protected");
      });
    });
  }
});
