import { test } from "node:test";
import assert from "node:assert/strict";
import { presetFile, readPresetFile, presetFileName } from "../src/preset-file.mjs";
import { RECORD } from "../src/presets.mjs";

const record = name => {
  const r = new Uint8Array(RECORD);
  r[0] = 2;
  for (let i = 0; i < name.length; i++) r[1 + i] = name.charCodeAt(i);
  for (let i = 0x20; i < RECORD; i++) r[i] = (i * 7) & 0x7f;
  return r;
};

test("a preset goes into a file and comes back byte for byte, with its kind and name", () => {
  const r = record("Short Delay");
  const back = readPresetFile(presetFile("mfx", r));
  assert.equal(back.ok, true);
  assert.equal(back.kind, "mfx");
  assert.equal(back.name, "Short Delay");
  assert.deepEqual(back.record, r);
  assert.equal(presetFileName("mfx", "Short Delay"), "Short-Delay.e2fx");
});

test("anything else is refused with a reason: not JSON, another format, a wrong kind, a short record, a changed byte", () => {
  const good = JSON.parse(presetFile("ifx", record("Pump")));
  const variants = ["kein json", JSON.stringify({ ...good, format: "x" }), JSON.stringify({ ...good, kind: "fx" }), JSON.stringify({ ...good, record: good.record.slice(2) }),
    JSON.stringify({ ...good, record: `${good.record.slice(0, -2)}00` }), JSON.stringify({ ...good, version: 2 })];
  for (const text of variants) {
    const r = readPresetFile(text);
    assert.equal(r.ok, false, text.slice(0, 40));
    assert.ok(r.reason.length > 10);
  }
});
