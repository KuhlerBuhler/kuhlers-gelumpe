import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { run as exec, slots } from "./support/spawn.mjs";
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { applyPatches, PATCH_FORMAT, fromHex } from "../src/patch.mjs";
import { identify, sha256 } from "../src/firmware.mjs";
import { makeFirmware } from "./helpers.mjs";

// The splash editor patch (docs/ideen.md idea 35, docs/messungen/2026-10-10-startbild-editor.md).
const PATCH = JSON.parse(readFileSync(new URL("../data/patches/splash-editor.json", import.meta.url), "utf8"));
const FREE_RUN = 0x1a2200;           // file offset of 0xC01A2100, the free run our code goes into
const FREE_END = 0x1a4b00;

const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const vsb = process.env.E2_VSB;
const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
const dir = fileURLToPath(new URL("../tools/", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = () => process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const skip = !vsb ? "E2_VSB not set" : false;
const skipEmu = skip || (!local ? "emulation only runs in test:local or test:emu" : false);
const flashArgs = flash.length ? ["--flash", ...flash] : [];

test("the splash editor patch has the v1 format and every change says what it replaces", () => {
  assert.equal(PATCH.format, PATCH_FORMAT);
  assert.equal(PATCH.version, 1);
  assert.equal(PATCH.id, "splash-editor");
  for (const change of PATCH.changes) {
    assert.match(change.expect, /^[0-9a-f]{64}$/, `${change.note}: expect`);
    assert.ok(change.note);
  }
});

test("the patch carries our own code and a few words, never a firmware table", () => {
  const raw = PATCH.changes.filter(c => c.copy === undefined);
  for (const c of raw) {
    const n = fromHex(c.bytes).length;
    // Only the two code blocks are larger than a word, and both sit in the free run.
    assert.ok(n === 4 || (c.file >= FREE_RUN && c.file + n <= FREE_END), `${c.note}: ${n} bytes at 0x${c.file.toString(16)}`);
  }
  const copies = PATCH.changes.filter(c => c.copy !== undefined);
  assert.equal(copies.length, 1, "the table of virtual functions is copied from the user's file");
  assert.equal(copies[0].bytes, undefined);
  assert.ok(copies[0].file >= FREE_RUN && copies[0].copy.length === 72);
  assert.match(copies[0].copy.expect, /^[0-9a-f]{64}$/);
});

test("the spans the patch asks to run at start are inside its changes and name a reason", () => {
  assert.equal(PATCH.startPhase.length, 3);
  for (const span of PATCH.startPhase) {
    assert.ok(span.why.length > 10);
    const inside = PATCH.changes.some(c => span.file >= c.file && span.file + span.length <= c.file + (c.bytes ? c.bytes.length / 2 : c.copy.length));
    assert.ok(inside, `0x${span.file.toString(16)} is not written by the patch`);
  }
  // Nothing of the editor itself is on the list: that code must not run before the main screen.
  const editor = PATCH.changes.find(c => c.note.startsWith("editor"));
  assert.ok(!PATCH.startPhase.some(s => s.file >= editor.file && s.file < editor.file + editor.bytes.length / 2));
});

test("the start code never calls the DSP boot", () => {
  // 0xC0015C78 resets the DSP and uploads its program; the firmware's own early path already does that once.
  const start = PATCH.changes.find(c => c.note.startsWith("start code"));
  const code = fromHex(start.bytes);
  const base = 0xC0000000 + start.file - 0x100;
  const targets = [];
  for (let i = 0; i + 4 <= code.length; i += 4) {
    const word = (code[i] | code[i + 1] << 8 | code[i + 2] << 16 | code[i + 3] << 24) >>> 0;
    if (word >>> 24 !== 0xEB) continue;
    const offset = (word & 0x7FFFFF) - (word & 0x800000);
    targets.push((base + i + 8 + offset * 4) >>> 0);
  }
  assert.ok(targets.includes(0xC0015DD0), "the display output is called");
  for (const dsp of [0xC0015C78, 0xC0011A04, 0xC0011A5C, 0xC0011AB8]) assert.ok(!targets.includes(dsp), `0x${dsp.toString(16)} is the DSP boot`);
});

test("a copy change reads the user's bytes when it is applied and writes them with its own words on top", async () => {
  const image = await makeFirmware();
  const from = 0x1000;
  image.set([1, 2, 3, 4, 5, 6, 7, 8], from);
  const to = 0x1a2200;
  const patch = (over = [], sourceHash) => ({
    format: PATCH_FORMAT, version: 1, id: "copy",
    changes: [{ file: to, copy: { file: from, length: 8, expect: sourceHash }, over, expect: "" }],
    startPhase: [{ file: to, length: 8, why: "test" }],
  });
  const source = await sha256(image.subarray(from, from + 8));
  const free = await sha256(image.subarray(to, to + 8));
  const good = patch([{ at: 4, bytes: "aabbccdd" }], source);
  good.changes[0].expect = free;
  const res = await applyPatches(image, [good]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual([...res.bytes.subarray(to, to + 8)], [1, 2, 3, 4, 0xaa, 0xbb, 0xcc, 0xdd]);
  assert.deepEqual(res.allowCode, [[to, 8]]);
  assert.equal(res.allow.length, 0);

  const other = patch([], "00".repeat(32));
  other.changes[0].expect = free;
  assert.match((await applyPatches(image, [other])).reasons[0], /not what the patch was made for/);
  const overrun = patch([{ at: 6, bytes: "aabbccdd" }], source);
  overrun.changes[0].expect = free;
  assert.match((await applyPatches(image, [overrun])).reasons[0], /over lies inside the copy/);
  const header = patch([], await sha256(image.subarray(0, 8)));
  header.changes[0].copy.file = 0;
  header.changes[0].expect = free;
  assert.match((await applyPatches(image, [header])).reasons[0], /inside the image/);
  const wrongTarget = patch([], source);
  wrongTarget.changes[0].expect = "00".repeat(32);
  assert.match((await applyPatches(image, [wrongTarget])).reasons[0], /andere Bytes/);
});

test("the assembler and the patch builder agree with the committed patch", { skip }, () => {
  const run = spawnSync(python(), [join(dir, "patch/splash_editor.py"), "--vsb", vsb], { encoding: "utf8", timeout: 60_000 });
  assert.ifError(run.error);
  assert.equal(run.status, 0, run.stderr);
  assert.deepEqual(JSON.parse(run.stdout), PATCH, "rebuild with tools/patch/splash_editor.py --vsb SYSTEM.VSB --out data/patches/splash-editor.json");
});

test("applied to the own firmware it changes only what it names and the copy is the real table", { skip }, async () => {
  const original = new Uint8Array(readFileSync(vsb));
  const res = await applyPatches(original, [PATCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal((await identify(res.bytes)).known, true);
  const named = PATCH.changes.map(c => [c.file, c.bytes ? c.bytes.length / 2 : c.copy.length]);
  for (let i = 0; i < original.length; i++) {
    if (original[i] !== res.bytes[i]) assert.ok(named.some(([at, n]) => i >= at && i < at + n), `0x${i.toString(16)} changed without being named`);
  }
  const table = PATCH.changes.find(c => c.copy);
  const copied = res.bytes.subarray(table.file, table.file + 72);
  const source = original.subarray(table.copy.file, table.copy.file + 72);
  const slots = table.over.map(o => o.at / 4);
  for (let word = 0; word < 18; word++) {
    const same = Buffer.compare(copied.subarray(4 * word, 4 * word + 4), source.subarray(4 * word, 4 * word + 4)) === 0;
    assert.equal(same, !slots.includes(word), `vtable word ${word}`);
  }
  assert.deepEqual(res.allowCode.length, 3);
});

describe("the splash editor in the emulator", { concurrency: slots }, () => {
  test("emulate:2026-10-10/startbild-editor, the storage cases and the kill switch", { skip: skipEmu }, async () => {
    const patched = await patchedCopy();
    try {
      const run = await exec(python(), [join(dir, "emu/splash_cases.py"), "cases", "--base", vsb, "--patched", patched.path, ...flashArgs], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      for (const id of ["empty", "valid", "bit_flipped", "half_written", "exit_held"]) assert.ok(report.checks.some(c => c.id === `splash:${id}`), id);
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-10/startbild-editor, the storage cases pass on a fresh device with no flash file too", { skip: skipEmu }, async () => {
    // The start image is up for about 0.13 s, and how long depends on the flash the firmware finds (a used one
    // takes a few ms longer). The cases look at every frame of that window, so the verdict does not hang on it.
    const patched = await patchedCopy();
    try {
      const run = await exec(python(), [join(dir, "emu/splash_cases.py"), "cases", "--base", vsb, "--patched", patched.path], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      const valid = report.checks.find(c => c.id === "splash:valid");
      assert.match(valid.detail, /start image stored \(seen stored x\d+\)/, "the stored image, and nothing else, for the whole time it is up");
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-10/startbild-editor, a start hook that boots the DSP a second time is refused", { skip: skipEmu }, async () => {
    const script = [
      "import json, sys",
      "sys.path.insert(0, sys.argv[1])",
      "import splash_editor as s",
      "old = '    mov r1, #3\\n    mov r2, #0\\n    bl 0xC0015DD0\\n'",
      "assert old in s.SOURCE",
      "s.SOURCE = s.SOURCE.replace(old, old + '    bl 0xC0015C78\\n')",
      "print(json.dumps(s.build_patch(open(sys.argv[2], 'rb').read())))",
    ].join("\n");
    const build = await exec(python(), ["-c", script, join(dir, "patch"), vsb], { timeout: 60_000 });
    assert.ifError(build.error);
    assert.equal(build.status, 0, build.stderr);
    const patched = await patchedCopy(JSON.parse(build.stdout));
    try {
      const run = await exec(python(), [join(dir, "emu/splash_cases.py"), "cases", "--base", vsb, "--patched", patched.path, ...flashArgs], { timeout: 600_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.equal(run.status, 1);
      assert.ok(report.checks.filter(c => !c.ok).every(c => /DSP booted 2 time/.test(c.detail) || c.id === "splash:exit_held_menu"), "only the DSP count fails");
      assert.ok(report.checks.some(c => !c.ok && /DSP booted 2 time/.test(c.detail)));
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-10/startbild-editor, page index 20 opens the editor, WRITE stores, EXIT leaves", { skip: skipEmu }, async () => {
    const patched = await patchedCopy();
    try {
      const run = await exec(python(), [join(dir, "emu/splash_cases.py"), "run", "--base", vsb, "--patched", patched.path, ...flashArgs], { timeout: 900_000, maxBuffer: 4 * 1024 * 1024 });
      assert.ifError(run.error);
      const report = JSON.parse(run.stdout);
      assert.deepEqual(report.steps.filter(s => !s.ok), []);
      assert.ok(report.steps.length >= 30);
      assert.equal(run.status, 0);
    } finally {
      patched.remove();
    }
  });

  test("emulate:2026-10-10/startbild-editor, the export check passes with the patch's own start exceptions and fails without", { skip: skipEmu }, async () => {
    const patched = await patchedCopy();
    try {
      const allow = patched.allowCode.flatMap(([at, n]) => ["--allow-code", `0x${at.toString(16)}:${n}`]);
      const args = ["--base", vsb, "--patched", patched.path, ...flashArgs];
      const ok = await exec(python(), [join(dir, "emu/check.py"), ...args, ...allow], { timeout: 900_000, maxBuffer: 8 * 1024 * 1024 });
      assert.ifError(ok.error);
      const report = JSON.parse(ok.stdout);
      assert.deepEqual(report.checks.filter(c => !c.ok), []);
      assert.ok(report.checks.some(c => c.id === "start_phase_exceptions"), "the exceptions are listed");
      assert.ok(report.checks.some(c => c.id === "splash:valid"), "the patch's own cases ran");
      assert.ok(report.checks.some(c => c.id === "dsp_boot_once" && c.ok), "the DSP boots once on every start path");
      assert.equal(ok.status, 0);
      const refused = await exec(python(), [join(dir, "emu/check.py"), ...args], { timeout: 900_000, maxBuffer: 8 * 1024 * 1024 });
      assert.equal(refused.status, 1, "without the exceptions the start hook is a change in the start code");
      const phase = JSON.parse(refused.stdout).checks.find(c => c.id === "start_phase");
      assert.equal(phase.ok, false);
      const hit = phase.detail.code.map(([at]) => at);
      for (const at of ["0x2ad38", "0x2aeac", "0x1a2200"]) assert.ok(hit.includes(at), `${at} is start code`);
    } finally {
      patched.remove();
    }
  });
});

function patchedCopy(patch = PATCH) {
  const original = new Uint8Array(readFileSync(vsb));
  const directory = mkdtempSync(join(tmpdir(), "gelumpe-splash-"));
  const path = join(directory, "SYSTEM.VSB");
  return applyPatches(original, [patch]).then(res => {
    assert.equal(res.ok, true, res.reasons.join(" "));
    writeFileSync(path, res.bytes);
    return { path, allowCode: res.allowCode, remove: () => rmSync(directory, { recursive: true, force: true }) };
  });
}
