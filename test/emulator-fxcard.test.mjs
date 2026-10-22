import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { applyPatches } from "../src/patch.mjs";
import { BLECH_SET_URL, loadBlechSet } from "../src/patcher.mjs";
import { buildOf } from "../src/firmware.mjs";
import { readUnits } from "../src/node.mjs";
import { recordOf, RECORD } from "../src/presets.mjs";
import { locateModTable, readModType } from "../src/modtable.mjs";
import { fxFromRecord, modFromType } from "../src/fx-v2.mjs";
import { buildCollection, collectionEntry } from "../src/fx-collection.mjs";
import { run } from "./support/spawn.mjs";

// The collection on the card, end to end: the editor builds e2sFx.all for the user's firmware, BLECHTRIBE loads it at
// power-on into RAM (tools/patch/fx_card.s), and the records the getters return are the ones in the file. The cases of
// tools/emu/fx_card_cases.py add the refusals (missing, broken, wrong build, bad index, cut, EXIT held) and the flash.
const root = fileURLToPath(new URL("../", import.meta.url));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const unicorn = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const skip = !local ? "emulation only runs in test:local or test:emu" : !vsb ? "E2_VSB not set" : unicorn.status !== 0 ? "Unicorn not installed" : false;

test("a collection the editor built loads into RAM at power-on; broken ones and EXIT leave the firmware's presets", { skip }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "gelumpe-fxcard-"));
  try {
    const base = new Uint8Array(readFileSync(vsb));
    const set = await loadBlechSet(async url => JSON.parse(readFileSync(join(root, url), "utf8")), BLECH_SET_URL);
    const patched = await applyPatches(base, set.patches.filter(p => !p.builds || p.builds.includes(buildOf(base))));
    assert.equal(patched.ok, true, patched.reasons?.join(" "));
    const firmware = join(dir, "BLECH.VSB");
    writeFileSync(firmware, patched.bytes);
    const units = readUnits();
    const at = recordOf(patched.bytes, "mfx", 1);
    const preset = fxFromRecord(patched.bytes.slice(at.file, at.file + RECORD), "mfx", units);
    preset.name = "Karte MFX";
    const fx = collectionEntry(preset, patched.bytes, 0, units);
    assert.equal(fx.ok, true, fx.reason);
    const table = locateModTable(patched.bytes);
    const mod = collectionEntry({ ...modFromType(readModType(patched.bytes, table.file, 5)), name: "Karte Mod" }, patched.bytes, 5, units);
    assert.equal(mod.ok, true, mod.reason);
    const file = join(dir, "e2sFx.all");
    writeFileSync(file, buildCollection({ build: buildOf(base), entries: [fx.entry, mod.entry] }));
    const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
    const loaded = await run(python, ["tools/emu/fx_card_cases.py", "load", "--patched", firmware, "--file", file, ...flash.length ? ["--flash", ...flash] : []], { cwd: root, timeout: 300_000 });
    assert.equal(loaded.status, 0, loaded.stdout + loaded.stderr);
    const report = JSON.parse(loaded.stdout);
    assert.equal(report.status, "loaded");
    assert.equal(report.loaded, 2);
    assert.equal(report.asserts, 0);
    const hex = bytes => Buffer.from(bytes).toString("hex");
    assert.deepEqual(report.records.map(r => r.ram), [hex(fx.entry.data), hex(mod.entry.data)], "the RAM holds the records of the file");
    const cases = await run(python, ["tools/emu/fx_card_cases.py", "cases", "--patched", firmware], { cwd: root, timeout: 900_000 });
    assert.equal(cases.status, 0, cases.stdout.slice(-3000) + cases.stderr.slice(-3000));
    assert.deepEqual(JSON.parse(cases.stdout).filter(c => !c.ok), []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
