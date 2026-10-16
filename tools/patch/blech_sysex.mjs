#!/usr/bin/env node
/**
 * Build data/patches/blech-sysex.json (Hacktribe) and data/patches/blech-sysex-stock.json (Korg's original): BLECH's own
 * SysEx commands for reading and writing RAM (tools/patch/blech_sysex.py). The protection table the firmware carries is
 * cut from data/protected.mjs here (src/sysex-table.mjs), one for each build, and handed to the builder; it is never
 * copied by hand. The patch carries our own code and the checksums of the bytes it replaces, no firmware bytes; the two
 * files differ in `builds` and in the table.
 *
 *   node tools/patch/blech_sysex.mjs --vsb SYSTEM.VSB
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { protectTable } from "../../src/sysex-table.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));

/** The patch for one build as text. `vsb` is the path of the user's own SYSTEM.VSB, read for the hashes of the bytes the patch replaces (the same in both builds). */
export function buildSysexPatch(vsb, { build = "hacktribe", table = protectTable({ build }).bytes, ref = null } = {}) {
  const venv = `${root}tools/emu/.venv/bin/python`;
  const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
  const dir = mkdtempSync(join(tmpdir(), "blech-sysex-"));
  try {
    const file = join(dir, "table.bin");
    writeFileSync(file, table);
    const result = spawnSync(python, [`${root}tools/patch/blech_sysex.py`, "--vsb", vsb, "--table", file, "--build", build, ...(ref ? ["--ref", ref] : [])], { encoding: "utf8", maxBuffer: 1 << 26 });
    if (result.error || result.status) throw new Error(result.error?.message ?? result.stderr);
    return result.stdout;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const arg = name => (process.argv.includes(name) ? process.argv[process.argv.indexOf(name) + 1] : null);
  const vsb = arg("--vsb");
  if (!vsb) {
    process.stderr.write("usage: blech_sysex.mjs --vsb SYSTEM.VSB\n");
    process.exit(2);
  }
  for (const [build, name] of [["hacktribe", "blech-sysex.json"], ["stock", "blech-sysex-stock.json"]]) {
    const out = `${root}data/patches/${name}`;
    writeFileSync(out, buildSysexPatch(vsb, { build }));
    console.log(`wrote ${out}`);
  }
  // The synth's file is made from the synth's own SYSTEM.VSB and the Sampler's (to find the places), see tools/patch/fwmap.py.
  const synth = arg("--synth"), ref = arg("--ref") ?? vsb;
  if (synth) {
    const out = `${root}data/patches/blech-sysex-synth.json`;
    writeFileSync(out, buildSysexPatch(synth, { build: "synth", ref }));
    console.log(`wrote ${out}`);
  }
}
