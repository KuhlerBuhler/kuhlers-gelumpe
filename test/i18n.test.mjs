import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import de from "../site/app/i18n-de.mjs";
import { t, tNodes, setLanguage, language, LANGUAGES } from "../site/app/i18n.mjs";

const html = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
const code = readdirSync(new URL("../site/app/", import.meta.url))
  .filter(f => f.endsWith(".mjs") && !f.startsWith("i18n-"))
  .map(f => readFileSync(new URL(`../site/app/${f}`, import.meta.url), "utf8"))
  .join("\n");
// A literal like "nav.start" whose first part names a namespace of the table counts as a key, in t() or in a FIELDS label.
const spaces = new Set(Object.keys(de).map(k => k.split(".")[0]));
const used = new Set([
  ...[...code.matchAll(/"([a-z]+(?:\.[A-Za-z0-9]+)+)"/g)].map(m => m[1]).filter(k => spaces.has(k.split(".")[0])),
  ...[...html.matchAll(/data-i18n(?:-label|-html)?="([^"]+)"/g)].map(m => m[1]),
]);

test("every key the app uses is in the German table", () => {
  assert.deepEqual([...used].filter(k => !(k in de)), []);
});

test("the German table has no key the app does not use", () => {
  assert.deepEqual(Object.keys(de).filter(k => !used.has(k) && k !== "language.name"), []);
});

test("index.html's own German text matches the table, so the page reads the same before and after translate()", () => {
  for (const [, key, text] of html.matchAll(/data-i18n="([^"]+)"[^>]*>([^<]*)</g)) assert.equal(text, de[key], key);
  for (const [, tag, key, inner] of html.matchAll(/<(\w+)[^>]*data-i18n-html="([^"]+)"[^>]*>([\s\S]*?)<\/\1>/g)) {
    assert.doesNotMatch(inner, new RegExp(`<${tag}[\\s>]`), `${key}: no nested <${tag}>`);
    assert.equal(inner, de[key], key);
  }
  for (const [tag] of html.matchAll(/<[^>]*data-i18n-label="[^"]+"[^>]*>/g)) {
    const key = tag.match(/data-i18n-label="([^"]+)"/)[1];
    assert.equal(tag.match(/aria-label="([^"]+)"/)?.[1], de[key], key);
  }
});

test("t() fills in values, falls back to German and then to the key", () => {
  assert.equal(t("settings.version", { version: "1.3.3" }), "App-Version 1.3.3");
  assert.equal(t("settings.version"), "App-Version {version}");
  assert.equal(t("no.such.key"), "no.such.key");
  setLanguage("xx");
  assert.equal(language(), "de");
  assert.deepEqual(LANGUAGES, [["de", "Deutsch"]]);
});

test("every file that calls t() or tNodes() imports it, so no page breaks on a missing import", () => {
  for (const f of readdirSync(new URL("../site/app/", import.meta.url)).filter(f => f.endsWith(".mjs") && !f.startsWith("i18n"))) {
    const src = readFileSync(new URL(`../site/app/${f}`, import.meta.url), "utf8");
    const imported = src.match(/import \{([^}]*)\} from "\.\/i18n\.mjs"/)?.[1].split(",").map(name => name.trim()) ?? [];
    for (const name of ["t", "tNodes"]) {
      if (new RegExp(`(?:^|[^\\w$.]|\\.\\.\\.)${name}\\(`, "m").test(src)) assert.ok(imported.includes(name), `${f} calls ${name}() without importing it`);
    }
  }
});

test("tNodes() puts nodes where the text names them", () => {
  const node = { node: true };
  assert.deepEqual(tNodes("no.such {a} key {b}", { a: node, b: "x" }), ["no.such ", node, " key ", "x"]);
  assert.deepEqual(tNodes("{a}.", { a: [node, "y"] }), [node, "y", "."]);
});

