import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { BUTTONS, ENCODERS, PADS, TOUCH_BUTTON } from "../data/panel.mjs";
import { PRESETS } from "../data/script/presets.mjs";
import { KEY_NAMES, LED_NAMES } from "../data/script/names.mjs";
import { API_BY_NAME } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { hintAt, suggestAt } from "../src/script/names.mjs";
import { SimDevice } from "../src/script/sim.mjs";

const build = (source, name = "names") => {
  const result = compile(source, { name });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const bytes = blob => Buffer.from(blob).toString("hex");
const failure = source => formatError(compile(source).errors[0]);
const numbers = id => readFileSync(new URL(`./fixtures/scripts/numbers/${id}.js`, import.meta.url), "utf8");

test("the names are the panel table: every key and every LED of it has one, each once", () => {
  assert.deepEqual(KEY_NAMES.map(n => n.value), [...BUTTONS.map(b => b.index), TOUCH_BUTTON]);
  const leds = [...BUTTONS.flatMap(b => [b.led, ...(b.ledBlue === undefined ? [] : [b.ledBlue])]), ...ENCODERS.map(e => e.led), ...PADS.flatMap(p => [p.ledRed, p.ledBlue])];
  assert.deepEqual(LED_NAMES.map(n => n.value).sort((a, b) => a - b), leds.sort((a, b) => a - b));
  for (const list of [KEY_NAMES, LED_NAMES]) {
    assert.equal(new Set(list.map(n => n.name)).size, list.length);
    for (const n of list) assert.match(n.name, /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$/, n.name);
  }
  const key = name => KEY_NAMES.find(n => n.name === name)?.value;
  const led = name => LED_NAMES.find(n => n.name === name)?.value;
  assert.deepEqual([key("TAP"), key("PLAY"), key("PART_LEFT"), key("PART_RIGHT"), key("TOUCHPAD")], [3, 2, 11, 15, 34]);
  assert.deepEqual([led("TAP"), led("PLAY"), led("PLAY_BLUE"), led("PAD_1_RED"), led("PAD_1_BLUE"), led("PAD_16_BLUE"), led("CUTOFF")], [20, 9, 21, 44, 45, 75, 2]);
});

test("every LED name is a valid argument of korg.led and lights that LED", () => {
  const max = API_BY_NAME.get("korg.led").args[0].max;
  for (const n of LED_NAMES) assert.ok(n.value >= 0 && n.value <= max, n.name);
  const device = new SimDevice();
  const body = LED_NAMES.map(n => `  korg.led(korg.led.${n.name}, 255);`).join("\n");
  assert.ok(device.load(build(`korg.onEvent("ready", () => {\n${body}\n});`)).ok);
  assert.deepEqual(device.run(40), []);
  assert.deepEqual([...device.leds].flatMap((v, i) => (v === 255 ? [i] : [])), LED_NAMES.map(n => n.value).sort((a, b) => a - b));
});

test("a name compiles to its number: the block is byte for byte the one with numbers", () => {
  const withNames = `const BASE = korg.led.PAD_1_RED;
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.led(korg.led.TAP, 255);
  if (key != korg.key.PART_RIGHT) korg.led(BASE + 2, korg.key.TOUCHPAD);
});`;
  const withNumbers = `const BASE = 44;
korg.onEvent("buttonPress", (key) => {
  if (key == 3) korg.led(20, 255);
  if (key != 15) korg.led(BASE + 2, 34);
});`;
  assert.equal(bytes(build(withNames)), bytes(build(withNumbers)));
  assert.equal(bytes(build(`korg.onEvent("ready", () => korg.led(20, 255));`)), bytes(build(`korg.onEvent("ready", () => korg.led(korg.led.TAP, 255));`)), "korg.led is still the function");
});

test("the example plugins use names and compile to the same blocks as with numbers", () => {
  for (const p of PRESETS) {
    assert.doesNotMatch(p.source, /key == \d|korg\.led\(\d/, `${p.id} still has a bare number`);
    if (!/buttonPress|korg\.led\(/.test(p.source)) continue;
    assert.match(p.source, /korg\.(key|led)\.[A-Z]/, `${p.id} uses no name`);
    assert.equal(bytes(build(p.source, p.id)), bytes(build(numbers(p.id), p.id)), p.id);
  }
});

test("an unknown name or the bare list is an error with the way out, a number stays allowed", () => {
  assert.match(failure(`korg.onEvent("ready", () => korg.led(korg.led.TAPP, 1));`), /Zeile 1, Spalte \d+: Es gibt keinen Namen „korg\.led\.TAPP“\. Ähnlich: korg\.led\.TAP\./);
  assert.match(failure(`korg.onEvent("buttonPress", (key) => { if (key == korg.key.NOPE) korg.led(0, 1); });`), /korg\.key\.NOPE/);
  assert.match(failure(`let a = korg.key;`), /ist eine Liste von Namen/);
  assert.ok(compile(`korg.onEvent("buttonPress", (key) => { if (key == 99) korg.led(0, 1); });`).ok, "an unknown number is no error");
  assert.ok(compile(`let a = 1; korg.onEvent("ready", () => { a = korg.key.TAP + 1; });`).ok, "a name is a number in a sum");
});

test("the editor names the number under the caret in a key or LED position and suggests names", () => {
  const src = `if (key == 11) {\n  korg.led(20, 255);\n  let x = 3;\n}\nkorg.led(99, 1);\nconst K = korg.key.PA`;
  const at = (needle, shift = 0) => src.indexOf(needle) + shift;
  assert.equal(hintAt(src, at("11")), "11 ist die Taste ◄ Part (korg.key.PART_LEFT).");
  assert.equal(hintAt(src, at("11", 2)), "11 ist die Taste ◄ Part (korg.key.PART_LEFT).", "caret right behind the number");
  assert.equal(hintAt(src, at("20")), "20 ist die LED TAP (korg.led.TAP).");
  assert.equal(hintAt(src, at("3;")), "", "a number in no key or LED position is left alone");
  assert.equal(hintAt(src, at("99")), "99 ist keine LED des Geräts.");
  assert.equal(hintAt(`3 == key`, 0), "3 ist die Taste TAP (korg.key.TAP).");
  const s = suggestAt(src, src.length);
  assert.equal(s.kind, "key");
  assert.deepEqual(s.names.map(n => n.name), ["PART_LEFT", "PART_RIGHT", "PART_MUTE", "PART_ERASE", "PATTERN_SET"]);
  assert.equal(suggestAt("korg.led.TAP", 12), null, "a finished name needs no suggestion");
  assert.equal(suggestAt("let a = 1;", 10), null);
});

for (const page of ["plugins.md", "plugins.en.md"]) test(`docs/${page} lists every name with its number`, () => {
  const doc = readFileSync(new URL(`../docs/${page}`, import.meta.url), "utf8");
  const missing = [];
  for (const [kind, list] of [["key", KEY_NAMES], ["led", LED_NAMES.filter(n => !n.name.startsWith("PAD_"))]]) {
    for (const n of list) if (!doc.includes(`| \`korg.${kind}.${n.name}\` | ${n.value} |`)) missing.push(`korg.${kind}.${n.name} = ${n.value}`);
  }
  assert.deepEqual(missing, []);
  assert.ok(doc.includes("`korg.led.PAD_n_RED` | 44 + 2 (n - 1)") && doc.includes("`korg.led.PAD_n_BLUE` | 45 + 2 (n - 1)"));
  assert.deepEqual([PADS[0].ledRed, PADS[0].ledBlue, PADS[1].ledRed - PADS[0].ledRed], [44, 45, 2]);
});
