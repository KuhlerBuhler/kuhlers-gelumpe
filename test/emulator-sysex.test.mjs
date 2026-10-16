import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { applyPatches } from "../src/patch.mjs";
import { run as exec, slots } from "./support/spawn.mjs";
import { sysexVectors } from "./support/sysex-vectors.mjs";

// BLECH's own SysEx commands in the emulator (tools/emu/sysex_cases.py, docs/messungen/2026-10-15-blech-sysex.md): the BLECH set is
// applied to the own firmware, Hacktribe's and Korg's original, and the cases talk to it over the emulated DIN line.
const read = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), "utf8"));
const SET = read("data/patches/blech.json");
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const stock = process.env.E2_STOCK_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skipEmu = !vsb ? "E2_VSB not set" : !local ? "emulation only runs in test:local or test:emu" : false;
const flashArgs = flash.length ? ["--flash", ...flash] : [];

async function withCopy(source, build, fn) {
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-sysex-"));
  try {
    const res = await applyPatches(new Uint8Array(readFileSync(source)), SET.patches.map(read));
    assert.equal(res.ok, true, res.reasons.join(" "));
    const path = join(directory, "SYSTEM.VSB");
    writeFileSync(path, res.bytes);
    // Reads of 2000 bytes take a second of line time each; the rest of the vectors are the same rule at other places.
    const vectors = join(directory, "vectors.json");
    writeFileSync(vectors, JSON.stringify(sysexVectors(build).filter((v, i) => v.length <= 16 && i % 5 === 0)));
    return await fn(path, vectors);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

async function cases(path, vectors, ...extra) {
  const result = await exec(python(), [join(dir, "emu/sysex_cases.py"), "cases", "--patched", path, "--vectors", vectors, ...flashArgs, ...extra], {
    timeout: 1_200_000, maxBuffer: 4 * 1024 * 1024, env: { ...process.env, GELUMPE_JOBS: process.env.GELUMPE_JOBS || "4" },
  });
  assert.ifError(result.error);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.filter(c => !c.ok), []);
  assert.equal(result.status, 0, result.stderr);
  return report;
}

const IDS = ["info", "read_sizes", "write_random", "bad_crc", "after_bad_crc", "data_without_begin", "one_data_per_begin", "short_data", "ranges", "refuses_writes",
  "allows_declared", "window_edges", "reads_everywhere_in_the_window", "same_rule_as_the_editor", "no_asserts"];

describe("BLECH's SysEx commands in the emulator", { concurrency: slots }, () => {
  for (const [name, source, skip, build] of [["Hacktribe", vsb, skipEmu, "hacktribe"], ["Korg's original", stock, skipEmu || (stock ? false : "E2_STOCK_VSB not set"), "stock"]]) {
    test(`emulate:2026-10-15/blech-sysex, the protocol and its refusals on ${name}`, { skip }, async () => {
      await withCopy(source, build, async (path, vectors) => {
        const report = await cases(path, vectors, "--only", "0");
        for (const id of IDS) assert.ok(report.some(c => c.id === `sysex:${id}`), id);
      });
    });

    test(`emulate:2026-10-15/blech-sysex, EXIT at power-on and other SysEx on ${name}`, { skip }, async () => {
      await withCopy(source, build, async (path, vectors) => {
        for (const group of ["1", "2"]) {
          const report = await cases(path, vectors, "--only", group);
          assert.ok(report.length >= 3);
        }
      });
    });
  }
});
