import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { API, API_VERSION, EVENTS, INTERNAL_EVENTS } from "../data/script/contract.mjs";

const read = name => readFileSync(new URL(`../docs/${name}`, import.meta.url), "utf8");
const french = read("plugins.fr.md");
const names = source => new Set([...source.matchAll(/`(korg\.[A-Za-z0-9_.]+)/g)].map(m => m[1].replace(/\.$/, "")));

test("the full French reference covers every API call and public event", () => {
  const documented = names(french);
  for (const call of API) {
    assert.ok(documented.has(call.name), `${call.name}: not documented in French`);
    assert.ok(french.includes(`\`${call.name}(`), `${call.name}: missing call syntax`);
  }
  for (const event of EVENTS.filter(e => e.name !== "start" && !INTERNAL_EVENTS.includes(e.name))) {
    assert.ok(french.split("\n").some(line => line.startsWith("| `") && line.includes(`\`${event.name}\``)), `${event.name}: missing event row`);
  }
  assert.match(french, new RegExp(`API ${API_VERSION}\\b`));
});

test("French retains the API names of both existing references", () => {
  const documented = names(french);
  for (const file of ["plugins.md", "plugins.en.md"]) {
    assert.deepEqual([...names(read(file))].filter(name => !documented.has(name)), [], `${file}: missing French API names`);
  }
});

test("French reference keeps the existing executable examples without changing their code", () => {
  const examples = source => [...source.matchAll(/```js\n([\s\S]*?)```/g)].map(m =>
    m[1].split("\n").filter(line => !line.trimStart().startsWith("//")).join("\n").trim());
  assert.deepEqual(examples(french), examples(read("plugins.en.md")));
  assert.doesNotMatch(french, /@@(?:CODE|[A-Z]+_TABLE)/);
  assert.doesNotMatch(french, /\uFFFD/);
});

test("the complete French reference is linked from the index and both other editions", () => {
  for (const file of ["README.md", "plugins.md", "plugins.en.md"]) assert.ok(read(file).includes("(plugins.fr.md)"), file);
});
