/**
 * Tests against your own files. They never run in CI, which stays free of
 * Korg data:
 *
 *   E2_VSB=/path/SYSTEM.VSB E2_PATTERNS=/path/backup.e2sallpat npm run test:local
 *
 * In `npm test` they are skipped when the variables are missing. Under
 * `npm run test:local` a missing variable is a failure, so a criterion that
 * rests on these tests cannot pass with none of them run. The emulator alone
 * runs with `npm run test:emu`, which needs only E2_VSB.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { readImage, readUnits } from "../src/node.mjs";
import { VSB_CHECKS, PATTERN_CHECKS } from "./factory-checks.mjs";

const REQUIRED = process.env.E2_LOCAL_REQUIRED === "1";
const VSB = process.env.E2_VSB;
const PATTERNS = process.env.E2_PATTERNS;

export function localFile(name, value) {
  if (value) return { skip: false };
  if (REQUIRED) return { fail: `${name} is not set` };
  return { skip: `${name} not set` };
}

for (const [name, value] of [["E2_VSB", VSB], ["E2_PATTERNS", PATTERNS]]) {
  const state = localFile(name, value);
  if (state.fail) test(`${name} is set`, () => assert.fail(state.fail));
}

for (const [name, check] of Object.entries(VSB_CHECKS)) {
  test(`factory-check:${name}`, { skip: VSB ? false : "E2_VSB not set" }, t => {
    t.diagnostic(check({ image: readImage(VSB), units: readUnits() }));
  });
}

for (const [name, check] of Object.entries(PATTERN_CHECKS)) {
  test(`factory-check:${name}`, { skip: PATTERNS ? false : "E2_PATTERNS not set" }, t => {
    t.diagnostic(check({ bytes: new Uint8Array(readFileSync(PATTERNS)) }));
  });
}

test("your backup loads and saves byte for byte unchanged", { skip: PATTERNS ? false : "E2_PATTERNS not set" }, async () => {
  const { PatternFile } = await import("../src/pattern.mjs");
  const bytes = new Uint8Array(readFileSync(PATTERNS));
  assert.deepEqual(PatternFile.parse(bytes).toBytes(), bytes);
});

test("one cutoff changed in your backup is one byte changed", { skip: PATTERNS ? false : "E2_PATTERNS not set" }, async () => {
  const { PatternFile } = await import("../src/pattern.mjs");
  const bytes = new Uint8Array(readFileSync(PATTERNS));
  const file = PatternFile.parse(bytes);
  const p = file.pattern(1);
  const now = p.raw("part.cutoff", [0]);
  p.setRaw("part.cutoff", [0], now === 127 ? 126 : now + 1);
  file.replace(1, p);
  const out = file.toBytes();
  const changed = [...out.keys()].filter(i => out[i] !== bytes[i]);
  assert.deepEqual(changed, [0x10100 + 0x800 + 13]);
});

test("every field of every pattern in your backup reads and describes", { skip: PATTERNS ? false : "E2_PATTERNS not set" }, async t => {
  const { PatternFile } = await import("../src/pattern.mjs");
  const { fieldsOf, instances, describe } = await import("../src/map/index.mjs");
  const file = PatternFile.parse(new Uint8Array(readFileSync(PATTERNS)));
  let reads = 0;
  const outside = new Map();
  for (let n = 1; n <= file.count; n++) {
    const p = file.pattern(n);
    for (const f of fieldsOf("pattern")) {
      for (const ix of instances(f)) {
        const raw = p.raw(f.id, ix);
        describe(f, raw);
        reads++;
        if (f.range && typeof raw === "number" && (raw < f.range[0] || raw > f.range[1])) {
          outside.set(f.id, (outside.get(f.id) || 0) + 1);
        }
      }
    }
  }
  t.diagnostic(`${reads} values read; outside the editable range: ${[...outside].map(([k, v]) => `${k} x${v}`).join(", ") || "none"}`);
});

// The baseline rule on real data: a factory slot that already fails the
// linter (IFX 7 maps a parameter past the end of its unit) is downgraded,
// but only while it is byte for byte the release.
test("an error a pristine factory slot already has is downgraded to a warning", { skip: VSB ? false : "E2_VSB not set" }, async t => {
  const { lintCheck } = await import("../src/gate.mjs");
  const { isOriginalSlot } = await import("../src/firmware.mjs");
  const units = readUnits();
  const image = readImage(VSB);
  const before = image.read("ifx", 7);
  if (!(await isOriginalSlot(before.bytes, "ifx", 7))) return t.skip("IFX 7 in this file is not the release");
  const edited = before.clone();
  edited.name = "Sustainer 2";
  const found = await lintCheck({ kind: "fxRecord", table: "ifx", slot: 7, bytes: edited.bytes, before: before.bytes }, { units, profile: null });
  const param = found.find(f => f.code === "map-param-out-of-range");
  assert.ok(param, "the known gap shows up");
  assert.equal(param.severity, "warn");
  assert.match(param.message, /Werkszustand/);
  const elsewhere = await lintCheck({ kind: "fxRecord", table: "ifx", slot: 60, bytes: edited.bytes, before: before.bytes }, { units, profile: null });
  assert.equal(elsewhere.find(f => f.code === "map-param-out-of-range").severity, "error", "outside a factory slot it stays an error");
});
