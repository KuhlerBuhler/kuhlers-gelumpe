import { test } from "node:test";
import assert from "node:assert/strict";
import { makeRecord } from "./helpers.mjs";
import { loadUnits } from "../src/units.mjs";
import { REC } from "../src/layout.mjs";

const units = loadUnits();

test("name is written, read back and clipped to fifteen characters", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x3b } });
  r.name = "A very long preset name";
  assert.equal(r.name, "A very long pre");
});

test("parameters are read by name once the unit is known", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x3b } });
  r.setParams(units, "mfx", { dry_wet: 122, fb_depth: 70 });
  const params = Object.fromEntries(r.params(units, "mfx").map(p => [p.name, p.value]));
  assert.equal(params.dry_wet, 122);
  assert.equal(params.fb_depth, 70);
});

test("an unknown parameter name is refused rather than written somewhere", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x3b } });
  assert.throws(() => r.setParams(units, "mfx", { nonsense: 1 }), /no parameter nonsense/);
});

test("the bytes nobody has decoded are left alone by an edit", () => {
  const r = makeRecord("mfx", { devices: { mfx: 0x3b } });
  const before = Uint8Array.from(r.bytes);
  r.name = "Short Delay";
  r.setParams(units, "mfx", { dry_wet: 122 });
  let changed = 0;
  for (let i = 0; i < before.length; i++) if (before[i] !== r.bytes[i]) changed++;
  // fifteen name bytes plus one parameter byte, nothing else
  assert.equal(changed <= 16, true, `${changed} bytes changed`);
});

test("a stage block can be adopted from the same stage of another record", () => {
  const ring = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  ring.setParams(units, "ifx1", { feedback: 108 });
  const target = makeRecord("ifx", { devices: { ifx1: 0x0a, ifx2: 0x0a } });
  target.adoptStage("ifx1", ring);
  assert.equal(target.device("ifx1"), 0x16);
  assert.equal(target.device("ifx2"), 0x0a);
  const p = Object.fromEntries(target.params(units, "ifx1").map(x => [x.name, x.value]));
  assert.equal(p.feedback, 108);
});

test("moving a stage block to the other stage is refused", () => {
  // Doing this by hand produced a preset that loaded and played nothing.
  const source = makeRecord("ifx", { devices: { ifx1: 0x16, ifx2: 0x0a } });
  const target = makeRecord("ifx", { devices: { ifx1: 0x0a, ifx2: 0x0a } });
  assert.throws(() => target.adoptStage("ifx1", source, "ifx2"), /position dependent/);
});

test("map rows round trip and clearing a row switches it off", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  r.map = [{ source: 0x45, chain: 0, param: 0, low: 0, high: 100 }];
  assert.equal(r.map.length, 1);
  assert.deepEqual(
    { source: 0x45, chain: 0, param: 0, low: 0, high: 100 },
    (({ index, ...rest }) => rest)(r.map[0]),
  );
  r.map = [];
  assert.equal(r.map.length, 0);
});

test("more rows than the record holds is refused", () => {
  const r = makeRecord("ifx", { devices: { ifx1: 0x16 } });
  const row = { source: 0x45, chain: 0, param: 0, low: 0, high: 1 };
  assert.throws(() => { r.map = Array(REC.mapEntries + 1).fill(row); }, /the record holds/);
});
