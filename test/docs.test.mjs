import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

// Keeps the docs fit to be read by anyone: no dead links, no personal paths,
// no names of people or of the agents that helped, no em or en dashes.
// README*, AGENTS.md and CLAUDE.md may say that agents work on the project.

const ROOT = new URL("../", import.meta.url).pathname;
const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "dist-release", "design", "target", ".venv", "build"]);

function walk(dir) {
  return readdirSync(dir).flatMap(name => {
    if (SKIP_DIRS.has(name) || name.startsWith(".venv")) return [];
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const top = ["README.md", "README.en.md", "AGENTS.md", "CLAUDE.md"].map(n => join(ROOT, n));
const docs = [
  ...top,
  ...walk(join(ROOT, "docs")),
  ...walk(join(ROOT, "tools")).filter(p => p.endsWith(".md")),
  ...walk(join(ROOT, "assets")).filter(p => p.endsWith(".md")),
].filter(p => /\.(md|txt)$/.test(p) && existsSync(p));
const prose = docs.filter(p => !top.includes(p));
const rel = p => relative(ROOT, p);

/** The text without fenced code blocks, which show commands and paths on purpose. */
function withoutFences(text) {
  return text.replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, "");
}

test("the docs exist", () => {
  assert.ok(docs.length > 20, `only ${docs.length} doc files found`);
  for (const f of ["README.md", "README.en.md", "AGENTS.md", "CLAUDE.md", "docs/README.md"]) {
    assert.ok(existsSync(join(ROOT, f)), `${f} is missing`);
  }
});

test("relative links point at files that exist", () => {
  const dead = [];
  for (const file of docs.filter(p => p.endsWith(".md"))) {
    const text = withoutFences(readFileSync(file, "utf8")).replace(/`[^`\n]*`/g, "");
    for (const m of text.matchAll(/\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
      let target = m[1].replace(/^<|>$/g, "");
      if (/^([a-z][a-z0-9+.-]*:|#|\/\/)/i.test(target)) continue;
      target = decodeURIComponent(target.split("#")[0].split("?")[0]);
      if (!target) continue;
      if (!existsSync(resolve(dirname(file), target))) dead.push(`${rel(file)}: ${m[1]}`);
    }
  }
  assert.deepEqual(dead, [], `dead links:\n${dead.join("\n")}`);
});

test("no absolute personal paths", () => {
  const found = [];
  const patterns = [
    /\/Users\/[A-Za-z]/, /\/home\/[a-z][a-z0-9_-]*\//, /[A-Za-z]:\\Users\\/, /claude-\d+/,
    /~\/(Desktop|Downloads|Documents|Library\/CloudStorage)/, /\/tmp\/gelumpe/, /Nextcloud/i,
    /[A-Za-z0-9._%+-]+@(?!example\.)[A-Za-z0-9-]+\.[a-z]{2,}/,
  ];
  for (const file of docs) {
    const text = readFileSync(file, "utf8");
    for (const re of patterns) if (re.test(text)) found.push(`${rel(file)}: ${re}`);
  }
  assert.deepEqual(found, [], `personal paths or addresses:\n${found.join("\n")}`);
});

test("no people and no agent working vocabulary in the docs", () => {
  const found = [];
  const names = /\b(Pascal|Codex|Claude|Koordinator|Teilauftrag|Hauptauftrag|Subagent|agentkit|hardtekkhub)\b|thoughts\//;
  // The artist name may stand where the project name is explained.
  const nameAllowed = new Set(["docs/entscheidungen.md"]);
  for (const file of prose) {
    const text = readFileSync(file, "utf8");
    const hit = text.match(names);
    if (hit) found.push(`${rel(file)}: ${hit[0]}`);
    if (!nameAllowed.has(rel(file)) && /\bBuhler\b/.test(text)) found.push(`${rel(file)}: Buhler`);
  }
  assert.deepEqual(found, [], `names or vocabulary that do not belong:\n${found.join("\n")}`);
});

test("no em or en dashes", () => {
  const found = [];
  for (const file of docs) {
    const lines = readFileSync(file, "utf8").split("\n");
    lines.forEach((line, i) => { if (/[\u2013\u2014]/.test(line)) found.push(`${rel(file)}:${i + 1}`); });
  }
  assert.deepEqual(found, [], `dashes at:\n${found.join("\n")}`);
});

test("the measurement index lists every measurement", () => {
  const dir = join(ROOT, "docs/messungen");
  const index = readFileSync(join(dir, "README.md"), "utf8");
  const missing = readdirSync(dir).filter(n => /^\d{4}-\d\d-\d\d-.+\.md$/.test(n) && !index.includes(`(${n})`));
  assert.deepEqual(missing, [], `not in docs/messungen/README.md:\n${missing.join("\n")}`);
});

test("the docs index links the main pages", () => {
  const index = readFileSync(join(ROOT, "docs/README.md"), "utf8");
  for (const page of ["plugins.md", "patcher.md", "emulator.md", "geraetekarte.md", "messungen/README.md", "ideen.md", "development.md"]) {
    assert.ok(index.includes(`(${page})`), `docs/README.md does not link ${page}`);
  }
});

test("the English pages are linked both ways and README.en.md points at them", () => {
  const read = f => readFileSync(join(ROOT, f), "utf8");
  for (const name of ["plugins", "patcher"]) {
    assert.ok(read(`docs/${name}.md`).includes(`(${name}.en.md)`), `docs/${name}.md does not link the English version`);
    assert.ok(read(`docs/${name}.en.md`).includes(`(${name}.md)`), `docs/${name}.en.md does not link the German version`);
    assert.ok(read("README.en.md").includes(`(docs/${name}.en.md)`), `README.en.md does not link docs/${name}.en.md`);
  }
  const lines = read("README.en.md").split("\n").filter(l => /docs\/(plugins|patcher)/.test(l)).join("\n");
  assert.ok(!lines.includes("(German)"), "README.en.md still marks the plugins or patcher link as German");
});

test("plugins.en.md names every korg.* call and event that plugins.md names", () => {
  const de = readFileSync(join(ROOT, "docs/plugins.md"), "utf8");
  const en = readFileSync(join(ROOT, "docs/plugins.en.md"), "utf8");
  const names = text => new Set([...text.matchAll(/`(korg\.[A-Za-z0-9_.]+)/g)].map(m => m[1].replace(/\.$/, "")));
  const known = names(en);
  const missing = [...names(de)].filter(n => !known.has(n));
  assert.deepEqual(missing, [], `named in plugins.md but not in plugins.en.md:\n${missing.join("\n")}`);
  const events = [...de.matchAll(/^\| `([a-zA-Z]+)`/gm)].map(m => m[1]);
  const missingEvents = events.filter(e => !en.includes(`\`${e}\``));
  assert.deepEqual(missingEvents, [], `events missing in plugins.en.md: ${missingEvents.join(", ")}`);
});
