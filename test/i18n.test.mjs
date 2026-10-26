import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import de from "../site/app/i18n-de.mjs";
import { t, tNodes, setLanguage, language, locale, LANGUAGES } from "../site/app/i18n.mjs";
import { text, render, number, TextError } from "../src/text.mjs";
import { PRESETS } from "../data/script/presets.mjs";
import { literals, looksLikeUiText, htmlText } from "./ui-text.mjs";

const html = readFileSync(new URL("../site/index.html", import.meta.url), "utf8");
const code = readdirSync(new URL("../site/app/", import.meta.url))
  .filter(f => f.endsWith(".mjs") && !f.startsWith("i18n-"))
  .map(f => readFileSync(new URL(`../site/app/${f}`, import.meta.url), "utf8"))
  .join("\n");
/**
 * The parts of src/ and data/ that hand text to the page as keys (src/text.mjs), and so are held to the same scans as
 * site/app. Path relative to the repository root.
 */
const KEYED = [
  "src/text.mjs",
  "src/patcher.mjs",
  "src/script/parser.mjs",
  "src/script/compiler.mjs",
  "src/script/gate.mjs",
  "src/script/names.mjs",
  "src/script/workspace.mjs",
  "src/script/runtime.mjs",
  "src/script/editor-model.mjs",
  "src/script/vm.mjs",
  "src/script/sim.mjs",
  "src/script/hardware.mjs",
  "src/script/archive.mjs",
  "src/script/blob.mjs",
  "src/protocol.mjs",
  "src/sender.mjs",
  "src/session.mjs",
  "src/pattern.mjs",
  "src/sample-file.mjs",
  "src/usb-sample-file.mjs",
  "src/usb-update.mjs",
  "src/firmware.mjs",
  "data/script/presets.mjs",
  "data/script/describe.mjs",
  "data/script/contract.mjs",
  "data/script/templates.mjs",
  "data/script/properties.mjs",
  "data/script/names.mjs",
  "data/news.mjs",
  "data/rescue.mjs",
];
const keyed = KEYED.map(f => [f, readFileSync(new URL(`../${f}`, import.meta.url), "utf8")]);
// A literal like "nav.start" whose first part names a namespace of the table counts as a key, in t() or in a FIELDS label.
const spaces = new Set(Object.keys(de).map(k => k.split(".")[0]));
const used = new Set([
  ...[...[code, ...keyed.map(([, src]) => src)].join("\n").matchAll(/"([a-z]+(?:\.[A-Za-z0-9]+)+)"/g)].map(m => m[1]).filter(k => spaces.has(k.split(".")[0])),
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

test("t() renders a text from src/ or data/, also one nested in a value, and an error's message follows the language", () => {
  assert.equal(t(text("settings.version", { version: text("nav.start") })), "App-Version Start");
  assert.equal(render("schon fertig"), "schon fertig");
  const error = new TextError("settings.version", { version: "1.3.3" });
  assert.equal(error.message, "App-Version 1.3.3");
  assert.deepEqual(error.text, { key: "settings.version", vars: { version: "1.3.3" } });
  assert.equal(number(1234.5), "1.234,5");
  assert.equal(locale(), "de-DE");
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

// Literals that pass the heuristic but are no UI text: KeyboardEvent.key names, HTTP headers, and per file with the reason.
const KEYS = ["Escape", "Enter", "Home", "End", "Backspace", "Delete", "Content-Type"];
const AST = ["Array", "Assign", "Binary", "Block", "Break", "Call", "Cond", "Continue", "Func", "Ident", "Index", "Logical", "Member", "Program", "Return", "Unary", "While"];
const ALLOWED = {
  // The labels printed on the front of the Electribe, drawn as they are on the device.
  "panel.mjs": ["Volume", "Input Level", "Sample", "Filter", "Modulation", "Insert Fx"],
  // The default name of a sample as the device writes it.
  "sampleset.mjs": ["Sample{}"],
  "samples.mjs": ["Sample{}"],
  // A name: the BLECHTRIBE mascot.
  "splash.mjs": ["Blechy"],
  // A heading of docs/plugins.md, found by its text.
  "scripts.mjs": ["Namen für Tasten und LEDs"],
  // The file name of a saved profile picture.
  "support.mjs": ["Blechy{}"],
  // The node types of the plugin language's syntax tree.
  "src/script/parser.mjs": AST,
  "src/script/compiler.mjs": AST,
  // An unused table of family names, and the disassembly listing, which only the tools print.
  "src/script/editor-model.mjs": ["Taste"],
  "src/script/blob.mjs": ["; Zeile {}"],
  // Errors of a caller's mistake (RangeError, TypeError), for the developer, never shown on the page.
  "src/pattern.mjs": ["Pattern {} gibt es in dieser Datei nicht", "expected a Pattern"],
  // The names of the firmware builds, the same in every language.
  "src/firmware.mjs": ["Synth", "Sampler", "Bleched Hacktribe", "Hacktribe", "Blechtribe {}"],
  // Korg's product names, put into a sentence of the table as they are.
  "data/rescue.mjs": ["Electribe Sampler", "Electribe"],
};

// The plugin catalog: names of plugins and of their makers stay as they are, and so does the plugin code (it holds korg.).
ALLOWED["data/script/presets.mjs"] = PRESETS.flatMap(p => [p.title, p.creator]);
const PLUGIN_CODE = ["data/script/presets.mjs", "data/script/templates.mjs"];

const hardcoded = (file, src) => literals(src)
  .filter(l => looksLikeUiText(l.value) && !KEYS.includes(l.value) && !(ALLOWED[file] ?? []).includes(l.value))
  .filter(l => !(PLUGIN_CODE.includes(file) && l.value.includes("korg.")))
  .map(l => `${file}:${l.line}: ${l.value}`);

test("site/app has no hard-coded UI text: every German label, message and toast goes through t()", () => {
  const files = readdirSync(new URL("../site/app/", import.meta.url)).filter(f => f.endsWith(".mjs") && !f.startsWith("i18n"));
  assert.deepEqual(files.flatMap(f => hardcoded(f, readFileSync(new URL(`../site/app/${f}`, import.meta.url), "utf8"))), []);
});

test("the parts of src/ and data/ that hand text to the page have no hard-coded UI text either", () => {
  assert.deepEqual(keyed.flatMap(([f, src]) => hardcoded(f, src)), []);
});

test("index.html has no hard-coded UI text outside data-i18n, data-i18n-html and data-i18n-label", () => {
  assert.deepEqual(htmlText(html).filter(s => looksLikeUiText(s.value)).map(s => `${s.line}: ${s.value}`), []);
});

test("the scan catches a planted string, a template, an aria-label and a text node", () => {
  assert.deepEqual(hardcoded("x.mjs", 'toast("Datei gespeichert"); el("b", { textContent: `Noch ${n} Samples frei` }); t("nav.start");').length, 2);
  assert.deepEqual(hardcoded("x.mjs", 'el("div", { className: "cee-a cee-b" }); if (e.key === "Escape") x("data-tone");'), []);
  const page = '<body><p>Hallo Welt</p><p data-i18n="a.b">Schon im Table</p><button aria-label="Schließen"></button><div id="cee-area-emu"><p>Hier nicht</p></div></body>';
  assert.deepEqual(htmlText(page, ["cee-area-emu"]).filter(s => looksLikeUiText(s.value)).map(s => s.value), ["Hallo Welt", "Schließen"]);
});
