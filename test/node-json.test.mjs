import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The frozen app has no node. A case that runs a node snippet gets its result from node-results.json, which the sidecar
// build fills by running the calls record_node_json.py lists. A call missing there is a crash in the app's full check.
const root = fileURLToPath(new URL("../", import.meta.url));
const emu = `${root}tools/emu`;
const read = f => readFileSync(`${emu}/${f}`, "utf8");
// macro_cases.py is a research tool with its own report, not a module of the full check.
const cases = readdirSync(emu).filter(f => /_cases\.py$/.test(f) && f !== "macro_cases.py");
const squash = s => s.replace(/\s+/g, " ").trim();

/** The text of each call `name(...)` in source, with balanced parentheses; `def name(` excluded. */
function callsOf(source, name) {
  const out = [];
  for (const m of source.matchAll(new RegExp(`(?<![\\w.])((?:edit\\.)?${name})\\(`, "g"))) {
    if (/def\s+$/.test(source.slice(Math.max(0, m.index - 4), m.index))) continue;
    let depth = 0, at = m.index + m[1].length;
    for (; at < source.length; at++) {
      if (source[at] === "(") depth++;
      else if (source[at] === ")" && --depth === 0) break;
    }
    out.push(squash(source.slice(m.index, at + 1)));
  }
  return out;
}

/** CALLS of record_node_json.py: module -> its call texts. */
function recorded() {
  const block = /^CALLS = \{\n([\s\S]*?)^\}/m.exec(read("record_node_json.py"))[1];
  const out = {};
  for (const m of block.matchAll(/"(\w+)": \[([\s\S]*?)\],?\n(?=\s*"\w+": \[|$)/g)) out[m[1]] = [...m[2].matchAll(/'([^']*)'/g)].map(c => squash(c[1]));
  return out;
}

test("no case runs node itself: every snippet goes through node_json", () => {
  const raw = cases.filter(f => /["']node["']/.test(read(f)));
  assert.deepEqual(raw, [], "these cases start node directly and crash in the app");
});

test("record_node_json.py lists every call of a case that runs a node snippet", () => {
  // the functions that run a snippet: the def a call of node_json.run is in (one at module level runs on import)
  const runners = new Set();
  for (const f of cases) {
    const source = read(f);
    for (const m of source.matchAll(/^[ \t]+.*node_json\.run\(/gm)) runners.add([...source.slice(0, m.index).matchAll(/^def (\w+)\(/gm)].at(-1)[1]);
  }
  assert.deepEqual([...runners].sort(), ["compiled", "fields", "tree"]);
  const listed = recorded();
  const missing = [];
  for (const f of cases) {
    const module = f.slice(0, -3);
    for (const name of runners) {
      for (const call of callsOf(read(f), name)) if (!(listed[module] ?? []).includes(call)) missing.push(`${module}: ${call}`);
    }
  }
  assert.deepEqual(missing, []);
});

test("build-sidecar records the node results and bundles them", () => {
  const build = read("build-sidecar.mjs");
  assert.match(build, /record_node_json\.py/);
  assert.match(build, /"--add-data", `\$\{work\}\/node-results\.json\$\{sep\}\.`/);
});
