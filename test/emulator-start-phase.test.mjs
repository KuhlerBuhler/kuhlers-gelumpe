import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { applyPatches } from "../src/patch.mjs";
import { buildOf, hardwareOf } from "../src/firmware.mjs";
import { BLECH_SET_URL, BLECH_SYNTH_SET_URL, loadBlechSet, samplerHead } from "../src/patcher.mjs";
import { run } from "./support/spawn.mjs";

// The app's copy with bootmap's poll slice raised to 100 ms, so the start scenarios run far past the main screen into code
// that only runs there (the script runtime's gated frame path): the start phase has to end at the main screen anyway.
// E2_VSB Hacktribe's original, E2_STOCK_VSB Korg's red 2.02, E2_BLUE_VSB Korg's blue 2.02; each skipped without its file.
const root = fileURLToPath(new URL("../", import.meta.url));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const unicorn = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const skipFor = file => (!local ? "emulation only runs in test:local or test:emu" : !file ? "firmware not set" : unicorn.status !== 0 ? "Unicorn not installed" : false);

const LONG_SLICE_S = 0.1;
const CHECK = `import sys
sys.path.insert(0, "tools/emu")
import bootmap
bootmap.SLICE_S = ${LONG_SLICE_S}
import check
sys.argv = ["check.py", *sys.argv[1:]]
sys.exit(check.main())`;

const hex = n => `0x${n.toString(16)}`;

/** The copy as the Patcher page makes it: a Hacktribe file with the blue head gets the Sampler head first, the blue build its own set. */
async function appCopy(file, blue) {
  let input = new Uint8Array(readFileSync(file));
  const build = buildOf(input);
  if (build === "hacktribe") input = samplerHead(input);
  const set = await loadBlechSet(async url => JSON.parse(readFileSync(join(root, url), "utf8")), build === "synth" ? BLECH_SYNTH_SET_URL : BLECH_SET_URL);
  const res = await applyPatches(input, set.patches);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  return { base: input, res, hardware: build === "hacktribe" && blue ? ["--hardware", "blue"] : [] };
}

function suite(name, file, { blue = false } = {}) {
  describe(`the start phase ends at the main screen: ${name}`, { skip: skipFor(file) }, () => {
    test("the app's copy passes the quick check with a 100 ms poll slice", async () => {
      const dir = mkdtempSync(join(tmpdir(), "gelumpe-start-phase-"));
      try {
        const { base, res, hardware } = await appCopy(file, blue || hardwareOf(new Uint8Array(readFileSync(file))) === "blue");
        writeFileSync(join(dir, "base.VSB"), base);
        writeFileSync(join(dir, "patched.VSB"), res.bytes);
        const allow = [...res.allow.map(([at, n]) => ["--allow", `${hex(at)}:${n}`]), ...res.allowCode.map(([at, n]) => ["--allow-code", `${hex(at)}:${n}`])].flat();
        const check = await run(python, ["-c", CHECK, "--quick", "--base", join(dir, "base.VSB"), "--patched", join(dir, "patched.VSB"), ...hardware, ...allow],
          { cwd: root, env: { ...process.env, GELUMPE_JOBS: "1", GELUMPE_CACHE: "off" }, maxBuffer: 64 * 1024 * 1024, timeout: 3_600_000 });
        assert.ifError(check.error);
        const report = JSON.parse(check.stdout);
        assert.deepEqual(report.checks.filter(c => !c.ok), [], check.stderr.slice(-3000));
        assert.equal(report.ok, true);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });
}

suite("Hacktribe", process.env.E2_VSB);
suite("Hacktribe on the blue", process.env.E2_VSB, { blue: true });
suite("Korg's red 2.02", process.env.E2_STOCK_VSB);
suite("Korg's blue 2.02", process.env.E2_BLUE_VSB);
