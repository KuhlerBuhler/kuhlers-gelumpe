import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const BUNDLE = "site/vendor/codemirror.mjs";

test("the CodeMirror bundle is built from the current entry file", () => {
  const entry = createHash("sha256").update(readFileSync(new URL("../tools/codemirror-entry.mjs", import.meta.url))).digest("hex").slice(0, 16);
  assert.match(read(BUNDLE).split("\n", 3)[1], new RegExp(`from tools/codemirror-entry\\.mjs \\(sha256 ${entry}\\)`), "tools/codemirror-entry.mjs changed: run npm run build:codemirror");
});

test("the bundle exports what the editor imports, and only that", async () => {
  const entry = read("tools/codemirror-entry.mjs");
  const wanted = [...entry.matchAll(/export \{([^}]+)\}/g)].flatMap(m => m[1].split(",").map(s => s.trim()));
  const module = await import(new URL(`../${BUNDLE}`, import.meta.url));
  assert.deepEqual(Object.keys(module).sort(), [...wanted].sort());
  const glue = read("site/app/script-editor.mjs");
  const imported = glue.match(/import \{([^}]+)\} from "\.\.\/vendor\/codemirror\.mjs"/)[1].split(",").map(s => s.trim()).filter(Boolean);
  for (const name of imported) assert.ok(wanted.includes(name), `${name} is imported by the editor but not in the bundle`);
});

test("the bundle is self contained: no network address to load from, no node module", () => {
  const code = read(BUNDLE);
  assert.doesNotMatch(code, /\bfrom\s*["'](?:node:|https?:|\/\/)/);
  assert.doesNotMatch(code, /\bimport\s*\(/);
  assert.deepEqual([...new Set(code.match(/https?:\/\/[^"'\s)]+/g) ?? [])], ["http://www.w3.org/2000/svg"], "only the SVG namespace, which is no request");
  assert.doesNotMatch(read("site/index.html"), /cdn|unpkg|jsdelivr/i);
});

test("the bundle stays small", () => {
  const kib = statSync(new URL(`../${BUNDLE}`, import.meta.url)).size / 1024;
  assert.ok(kib < 400, `${kib.toFixed(0)} KiB: look at what was added to tools/codemirror-entry.mjs`);
});

test("the licence of every bundled package ships next to the bundle, and the NOTICE names CodeMirror", () => {
  const code = read(BUNDLE);
  const packages = code.split("\n", 1)[0].replace(/^[^:]*: /, "").replace(/\. MIT.*$/, "").split(", ");
  assert.ok(packages.length >= 8, packages.join(", "));
  const licences = read("site/vendor/codemirror.LICENSE.txt");
  for (const name of packages) assert.match(licences, new RegExp(`^${name.replace(/[/@.]/g, "\\$&")} \\d+\\.\\d+\\.\\d+ \\(MIT\\)$`, "m"), `${name} has no licence text`);
  assert.match(licences, /Permission is hereby granted, free of charge/);
  const notice = read("NOTICE");
  assert.match(notice, /CodeMirror/);
  assert.match(notice, /site\/vendor\//);
  assert.match(notice, /MIT/);
});
