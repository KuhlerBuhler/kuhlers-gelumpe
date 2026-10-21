import { test } from "node:test";
import assert from "node:assert/strict";
import { findInCss, findInJs, scan } from "../tools/raw-values.mjs";

const kinds = hits => hits.map(h => h.kind);

test("the rule finds raw colours, radii, font sizes and spacing in CSS", () => {
  assert.deepEqual(kinds(findInCss("#cee-x:hover { color: #fff; padding: 8px 2px; border-radius: 12px; font-size: 14px; }")), ["color", "spacing", "radius", "font-size"]);
  assert.deepEqual(kinds(findInCss(".a { padding: calc(var(--space-2) + 3px); background: linear-gradient(red, blue); }")), ["spacing", "gradient"]);
});

test("tokens, borders, ids and custom properties are no raw values", () => {
  assert.deepEqual(findInCss("#cee-tab { margin: 0 auto; gap: var(--space-2); border: 1px solid var(--color-border-muted); --cee-w: 22rem; }"), []);
  assert.deepEqual(findInJs('const tab = $("#cee-tab-start");'), []);
});

test("the rule finds colours and inline lengths in JS", () => {
  assert.deepEqual(kinds(findInJs('x.style.padding = "8px";')), ["inline-length"]);
  assert.deepEqual(kinds(findInJs('ctx.fillStyle = "#fff";')), ["color"]);
});

test("the editor's own code uses tokens (DESIGN.md)", () => {
  const hits = scan();
  assert.deepEqual(hits.map(h => `${h.file}:${h.line} [${h.kind}] ${h.text}`), []);
});
