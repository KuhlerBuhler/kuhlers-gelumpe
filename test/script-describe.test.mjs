import { test } from "node:test";
import assert from "node:assert/strict";
import { API, EVENTS, SCRIPT_APPS } from "../data/script/contract.mjs";
import { render, isText } from "../src/text.mjs";
import { API_DOCS, EVENT_DOCS, GROUP_DOCS, NAME_FAMILY_DOCS, ON_EVENT_DOC } from "../data/script/describe.mjs";

const texts = () => [
  ...Object.entries(API_DOCS).map(([k, v]) => [`API ${k}`, v]),
  ...Object.entries(EVENT_DOCS).flatMap(([k, v]) => [[`event ${k}`, v.text], ...Object.entries(v.args).map(([a, t]) => [`event ${k}, ${a}`, t])]),
  ...Object.entries(GROUP_DOCS).map(([k, v]) => [`group ${k}`, v]),
  ...Object.entries(NAME_FAMILY_DOCS).map(([k, v]) => [`names ${k}`, v]),
  ["korg.onEvent", ON_EVENT_DOC.text],
];

test("every API entry of the contract has a description, and the file names no entry the contract lacks", () => {
  const missing = API.filter(a => !isText(API_DOCS[a.name]) || !render(API_DOCS[a.name]).trim()).map(a => a.name);
  assert.deepEqual(missing, [], `API entries without a description in data/script/describe.mjs: ${missing.join(", ")}`);
  assert.deepEqual(Object.keys(API_DOCS).filter(n => !API.some(a => a.name === n)), [], "descriptions of entries the contract does not have");
});

test("every event has a description, and so has every value it hands to its handler", () => {
  for (const e of EVENTS) {
    const doc = EVENT_DOCS[e.name];
    assert.ok(doc && render(doc.text)?.trim(), `event ${e.name} has no description`);
    assert.deepEqual(Object.keys(doc.args), [...e.args], `event ${e.name}: the described values are ${Object.keys(doc.args)}, the contract's are ${e.args}`);
    for (const a of e.args) assert.ok(doc.args[a] && render(doc.args[a]).trim(), `event ${e.name}, value ${a} has no description`);
  }
  assert.deepEqual(Object.keys(EVENT_DOCS).filter(n => !EVENTS.some(e => e.name === n)), [], "descriptions of events the contract does not have");
});

test("every app group has a description", () => {
  assert.deepEqual(Object.keys(GROUP_DOCS), [...SCRIPT_APPS.groups]);
});

test("a description is one or two German sentences with no em or en dash", () => {
  for (const [what, raw] of texts()) {
    assert.ok(isText(raw), `${what} is a key of the table`);
    const text = render(raw);
    assert.match(text, /[.!]$/, `${what} ends like a sentence`);
    assert.doesNotMatch(text, /[\u2013\u2014]/, what);
    assert.ok(text.length <= 190, `${what} is ${text.length} characters, a description is short`);
    assert.match(text, /[a-zäöüß]/, what);
  }
});
