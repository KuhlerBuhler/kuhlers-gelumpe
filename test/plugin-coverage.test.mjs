import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { API, EVENTS } from "../data/script/contract.mjs";
import { OBJECTS } from "../data/script/objects.mjs";
import { AREAS, COVERAGE, COVERAGE_OUTSIDE } from "../data/script/coverage.mjs";
import { DOCS, withTable } from "../tools/plugin-coverage.mjs";

const named = COVERAGE.flatMap(r => [...r.read, ...r.write, ...r.events]);
const covers = name => named.some(n => n === name || (n.endsWith(".*") && name.startsWith(n.slice(0, -1))));

test("every call, event and leaf of the object tree is in a row of the coverage, or outside on purpose", () => {
  const all = [...API.map(a => a.name), ...EVENTS.map(e => e.name), ...OBJECTS.map(o => o.path)];
  const missing = all.filter(name => !covers(name) && !COVERAGE_OUTSIDE.includes(name));
  assert.deepEqual(missing, []);
  assert.deepEqual(COVERAGE_OUTSIDE.filter(covers), [], "a name outside on purpose is in no row");
});

test("every name in the coverage is a call, an event or a path of the object tree", () => {
  const known = new Set([...API.map(a => a.name), ...EVENTS.map(e => e.name), ...OBJECTS.map(o => o.path)]);
  const unknown = named.filter(n => n.endsWith(".*") ? ![...known].some(k => k.startsWith(n.slice(0, -1))) : !known.has(n));
  assert.deepEqual(unknown, []);
  assert.ok(COVERAGE.every(r => r.area in AREAS));
});

test("the three plugin docs show the current coverage table", () => {
  for (const [lang, path] of Object.entries(DOCS)) {
    const doc = readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
    assert.equal(doc, withTable(doc, lang), `${path}: run node tools/plugin-coverage.mjs`);
  }
});
