import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { applyPatches } from "../src/patch.mjs";
import { BLECH_SET_URL, loadBlechSet, withLoadingAnim } from "../src/patcher.mjs";
import { encodeAnimation, decodeAnimation, loopPicture, progressIndex, FRAME_BYTES } from "../src/loading-anim.mjs";
import { run } from "./support/spawn.mjs";

// An animation of the user's own, the way the Patcher page makes the copy: the BLECH set, then withLoadingAnim. The overlay
// has to play exactly the app's pictures and not Blechy (tools/emu/loadbar_cases.py app_file), and the copy has to pass the
// start check (check.py --quick). E2_VSB is Hacktribe's original, E2_STOCK_VSB Korg's red 2.02; each is skipped without its file.
const root = fileURLToPath(new URL("../", import.meta.url));
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const unicorn = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const skipFor = file => (!local ? "emulation only runs in test:local or test:emu" : !file ? "firmware not set" : unicorn.status !== 0 ? "Unicorn not installed" : false);

const LOOP_FROM = 50;

/**
 * Eight progress pictures with a bar growing in pages 3 and 4 and a counter byte at page 0, column 40; three loop pictures
 * with a block moving in page 6 and two bytes either side of the counter, which the encoder bridges with the base's
 * counter: on screen the counter of the loop's base, not of the progress picture under it.
 */
function testAnimation() {
  const progress = Array.from({ length: 8 }, (_, k) => {
    const f = new Uint8Array(FRAME_BYTES);
    for (const page of [3, 4]) f.fill(0xff, page * 128 + 8, page * 128 + 8 + 14 * (k + 1));
    f[40] = 0x10 + k;
    return f;
  });
  const base = progress[progressIndex(progress.length, 10 * LOOP_FROM)];
  const loop = [0, 1, 2].map(j => {
    const f = base.slice();
    f.fill(0x3c, 6 * 128 + 20 + 30 * j, 6 * 128 + 28 + 30 * j);
    f[39] = 0x81; f[41] = 0x81;
    return f;
  });
  return { progress, loop, loopFrom: LOOP_FROM };
}

/** The file and every picture the overlay may show, as the app's preview computes them ("index,loop", -1 for none). */
function expected(bytes) {
  const { progress, loop, loopFrom } = decodeAnimation(bytes);
  const base = progress[progressIndex(progress.length, 10 * loopFrom)];
  const pictures = {};
  progress.forEach((shown, k) => {
    pictures[`${k},-1`] = Buffer.from(shown).toString("hex");
    loop.forEach((l, j) => { pictures[`${k},${j}`] = Buffer.from(loopPicture(shown, base, l)).toString("hex"); });
  });
  return { anim: Buffer.from(bytes).toString("hex"), pictures };
}

const hex = n => `0x${n.toString(16)}`;

async function appCopy(file) {
  const set = await loadBlechSet(async url => JSON.parse(readFileSync(join(root, url), "utf8")), BLECH_SET_URL);
  const first = await applyPatches(new Uint8Array(readFileSync(file)), set.patches);
  assert.equal(first.ok, true, first.reasons?.join(" "));
  assert.ok(first.spans.some(s => s.patch === "load-bar"), "load-bar is in the set for this build");
  const { bytes } = encodeAnimation(testAnimation());
  const res = await withLoadingAnim(first, bytes);
  assert.equal(res.ok, true, res.reasons?.join(" "));
  assert.ok(res.spans.some(s => s.patch === "loading-anim"));
  return { res, bytes };
}

function suite(name, file) {
  describe(`an own loading animation through the app's path: ${name}`, { skip: skipFor(file) }, () => {
    test("the overlay plays the app's pictures, not Blechy, and the copy passes the start check", async () => {
      const dir = mkdtempSync(join(tmpdir(), "gelumpe-loading-anim-"));
      try {
        const { res, bytes } = await appCopy(file);
        const patched = join(dir, "BLECH.VSB");
        const expect = join(dir, "expect.json");
        writeFileSync(patched, res.bytes);
        writeFileSync(expect, JSON.stringify(expected(bytes)));
        const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
        const opts = { cwd: root, env: { ...process.env, GELUMPE_JOBS: process.env.GELUMPE_JOBS || "4" }, maxBuffer: 16 * 1024 * 1024 };
        const shown = await run(python, ["tools/emu/loadbar_cases.py", "app", "--patched", patched, "--expect", expect, ...flash.length ? ["--flash", ...flash] : []],
          { ...opts, timeout: 900_000 });
        assert.ifError(shown.error);
        assert.equal(shown.status, 0, shown.stdout.slice(-4000) + shown.stderr.slice(-3000));
        const entries = JSON.parse(shown.stdout);
        assert.deepEqual(entries.filter(e => !e.ok), []);
        assert.equal(entries.length, 5);
        const allow = [...res.allow.map(([at, n]) => ["--allow", `${hex(at)}:${n}`]), ...res.allowCode.map(([at, n]) => ["--allow-code", `${hex(at)}:${n}`])].flat();
        const check = await run(python, ["tools/emu/check.py", "--quick", "--base", file, "--patched", patched, ...allow, ...flash.length ? ["--flash", ...flash] : []],
          { ...opts, timeout: 3_600_000 });
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
suite("Korg's red 2.02", process.env.E2_STOCK_VSB);
