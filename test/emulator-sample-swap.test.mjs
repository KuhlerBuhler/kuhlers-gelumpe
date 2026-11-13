import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { emuPython } from "./support/emu.mjs";
import { parseSampleFile, wavChunks } from "../src/sample-file.mjs";

test("generated sample collections describe both channels of their stereo PCM", () => {
  const result = spawnSync(emuPython(), ["-c", `
import sys
sys.path.insert(0,'tools/emu')
import sampleset
sys.stdout.buffer.write(sampleset.build({500:('Mono',100),501:('Stereo',100,48000,'stereo16'),502:('Wide',100,48000,'pcm24')}))
`], { timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr.toString());
  const bytes = new Uint8Array(result.stdout);
  const view = new DataView(bytes.buffer);
  for (const sample of parseSampleFile(bytes).samples) {
    assert.equal(sample.problem, null);
    const chunks = wavChunks(bytes, sample.offset, sample.offset + sample.length);
    const record = chunks.korg.at + 8;
    assert.equal(bytes[record + 65], Number(sample.channels === 2), sample.name);
    assert.equal(view.getUint32(record + 60, true), sample.frames * sample.channels * 2, sample.name);
  }
});

test("native sample allocation reclaims the tail but leaves interior holes", { skip: !process.env.E2_VSB && "E2_VSB not set" }, () => {
  const result = spawnSync(emuPython(), ["tools/emu/sample_swap_cases.py", "--vsb", process.env.E2_VSB], {
    encoding: "utf8", timeout: 60_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.hardware_contact, false);
  assert.equal(report.dsp_model, "not used");
  assert.equal(report.checks.length, 8);
  for (const check of report.checks) assert.equal(check.ok, true, check.id);
});
