import { test } from "node:test";
import assert from "node:assert/strict";
import { API, EVENTS, SCRIPT_APPS } from "../data/script/contract.mjs";
import { KEY_NAMES, LED_NAMES } from "../data/script/names.mjs";
import { PROPERTIES, KNOB_NAMES } from "../data/script/properties.mjs";
import { compile } from "../src/script/compiler.mjs";
import { render } from "../src/text.mjs";
import { completionsAt, callAt, hoverAt, errorRange, allowedIn, rangeText } from "../src/script/editor-model.mjs";

/** The text before the caret marker `|`, and the caret. */
const at = source => ({ text: source.replace("|", ""), pos: source.indexOf("|") });
const complete = source => { const { text, pos } = at(source); return completionsAt(text, pos); };
const labels = result => result?.options.map(o => o.label) ?? [];
const call = source => { const { text, pos } = at(source); return callAt(text, pos); };
const hover = source => { const { text, pos } = at(source); return hoverAt(text, pos); };

test("korg.disp offers every korg.display entry, each with a description, its parameters and where it may be called", () => {
  const result = complete("korg.disp|");
  assert.equal(result.from, 0);
  const display = result.options.filter(o => o.label.startsWith("korg.display."));
  assert.deepEqual(display.map(o => o.label), API.filter(a => a.name.startsWith("korg.display.")).map(a => a.name));
  const text = display.find(o => o.label === "korg.display.text");
  assert.equal(text.detail, "(text, x, y)");
  assert.equal(text.type, "function");
  assert.match(render(text.info.text), /Text/);
  assert.deepEqual(text.info.params, [{ name: "text", range: "Text, höchstens 31 Zeichen" }, { name: "x", range: "0 bis 127" }, { name: "y", range: "0 bis 63" }]);
  assert.equal(text.info.allowed, "in allen Ereignissen außer dem Rumpf und save");
  assert.equal(text.snippet, "korg.display.text(${1:text}, ${2:x}, ${3:y})");
  assert.equal(display.find(o => o.label === "korg.display.take").info.returns, "eine ganze Zahl");
});

test("the completions after korg. cover every property and API entry once, korg.onEvent and the key names, all described", () => {
  const result = complete("korg.|");
  const props = result.options.filter(o => o.type === "property");
  assert.deepEqual(props.map(o => o.label), PROPERTIES.map(p => p.path.replace("[]", "[i]")));
  assert.deepEqual(result.options.filter(o => o.type === "function").map(o => o.label).filter(l => l !== "korg.onEvent"), API.map(a => a.name));
  assert.ok(labels(result).includes("korg.onEvent"));
  for (const o of result.options) {
    assert.ok(render(o.info.text)?.trim(), `${o.label} has a description`);
    assert.ok(o.snippet || o.apply, `${o.label} says what goes in`);
  }
  assert.equal(result.options.find(o => o.label === "korg.menu.add").info.allowed, "nur im Rumpf und in ready");
  assert.equal(result.options.find(o => o.label === "korg.app").info.allowed, "nur im Rumpf");
  assert.equal(result.options.find(o => o.label === "korg.millis" && o.type === "function").info.allowed, "überall");
  assert.equal(props.find(o => o.label === "korg.tempo").info.allowed, "lesen überall; setzen in allen Ereignissen außer dem Rumpf und save");
  assert.equal(props.find(o => o.label === "korg.parts[i].muted").snippet, "korg.parts[${1:i}].muted");
  assert.equal(result.options.find(o => o.label === "korg.key").retrigger, true);
});

test("korg.knobs. offers the knob names, and a property reads differently from the call of the same name", () => {
  assert.deepEqual(labels(complete("let a = korg.knobs.|")), KNOB_NAMES.map(k => k.name));
  const text = "korg.tempo = 1200;\nkorg.tempo(1200);\nlet a = korg.parts[2].step + korg.knobs.LEVEL;";
  assert.equal(hoverAt(text, 3).info.signature, "korg.tempo");
  assert.equal(hoverAt(text, 22).info.signature, "korg.tempo(tenthsBpm)");
  assert.match(render(hoverAt(text, text.indexOf("parts") + 1).info.text), /korg\.parts\[i\]\.step: .*korg\.parts\[i\]\.muted: /);
  assert.equal(hoverAt(text, text.indexOf("LEVEL") + 1).info.signature, "korg.knobs.LEVEL");
});

test("a short start offers korg, and ordinary words offer nothing", () => {
  assert.deepEqual(labels(complete("let a = ko|")), ["korg"]);
  assert.equal(complete("let a = k|"), null);
  assert.equal(complete("let count = 0;\nlet cou|"), null);
  assert.equal(complete("let a = foo.|"), null);
  assert.equal(complete("|"), null);
});

test("after korg.key. and korg.led. every name is offered with its number and its label", () => {
  const keys = complete("korg.key.|");
  assert.deepEqual(labels(keys), KEY_NAMES.map(n => n.name));
  const tap = keys.options.find(o => o.label === "TAP");
  assert.equal(tap.detail, "3");
  assert.match(render(tap.info.text), /Taste TAP, Code 3/);
  const leds = complete("korg.led(korg.led.PAD_1|");
  assert.equal(leds.from, "korg.led(korg.led.".length);
  assert.deepEqual(labels(leds), LED_NAMES.map(n => n.name));
  assert.match(render(leds.options.find(o => o.label === "PAD_1_RED").info.text), /Pad 1, rote LED, Nummer 44/);
});

test("inside korg.onEvent(\"...\") every event but the body is offered with its handler values, and the handler goes in", () => {
  const result = complete(`korg.onEvent("bu|`);
  assert.deepEqual(labels(result), EVENTS.filter(e => e.name !== "start").map(e => e.name));
  assert.equal(result.from, `korg.onEvent("`.length);
  const press = result.options.find(o => o.label === "buttonPress");
  assert.equal(press.detail, "(key)");
  assert.deepEqual(press.info.params.map(p => ({ ...p, range: render(p.range) })), [{ name: "key", range: "Der Tastencode, zum Vergleichen mit einem Namen wie korg.key.TAP." }]);
  assert.match(render(press.info.text), /Taste/);
  assert.equal(press.snippet, 'buttonPress", (key) => {\n  ${}\n});');
  assert.equal(result.options.find(o => o.label === "frame").snippet, 'frame", () => {\n  ${}\n});');
  const closed = complete(`korg.onEvent("fr|", () => {});`);
  assert.equal(closed.options.find(o => o.label === "frame").snippet, undefined, "the quote and the handler are there already");
  assert.equal(complete(`korg.onEvent(1, "fr|`), null, "only the first argument names an event");
  assert.equal(complete(`korg.led("fr|`), null);
});

test("the second argument of korg.app offers the groups", () => {
  const result = complete(`korg.app("Snake", "G|`);
  assert.deepEqual(labels(result), [...SCRIPT_APPS.groups]);
  assert.equal(result.options[0].apply, 'GAMES");');
  assert.equal(complete(`korg.app("Sn|`), null);
});

test("nothing is offered in a comment, and a string that is no event name offers nothing", () => {
  assert.equal(complete("// korg.disp|"), null);
  assert.equal(complete("/* korg.disp|"), null);
  assert.equal(complete(`let a = "korg.disp|`), null);
  assert.notEqual(complete("// one\nkorg.disp|"), null);
});

test("the parameter hint names the call and the argument being written", () => {
  assert.equal(call("let a = 1;|"), null);
  const first = call("korg.display.text(|");
  assert.equal(first.info.signature, "korg.display.text(text, x, y)");
  assert.equal(first.index, 0);
  assert.equal(call(`korg.display.text("a, b", 4, |`).index, 2, "a comma in a string does not count");
  assert.equal(call("korg.display.text(korg.read.tempo(), |").info.name, "korg.display.text");
  assert.equal(call("korg.display.text(korg.read.tempo(), |").index, 1);
  assert.equal(call("korg.display.text(korg.read.tempo(|").info.name, "korg.read.tempo");
  assert.equal(call("korg.led(korg.key.TAP, 2, 3, |").index, -1, "more arguments than the call takes");
  assert.equal(call("korg.display.number(1, 2, 3); |"), null, "a finished call");
  assert.equal(call("korg.onEvent(\"frame\", () => {\n  let a = 1;\n  |"), null, "a block inside a call is no call");
  assert.equal(call("korg.onEvent(|").index, 0);
  assert.equal(call("korg.onEvent(\"frame\", |").index, 1);
});

test("the hint is silent inside a handler's body and inside brackets", () => {
  assert.equal(call("korg.onEvent(\"frame\", () => {\n  |\n});"), null);
  assert.equal(call("const a = [1, 2, |"), null);
  assert.equal(call("korg.led(korg.key.TAP, [1, |"), null);
  assert.equal(call("korg.onEvent(\"frame\", () => {\n  korg.led(|\n});").info.name, "korg.led");
  assert.equal(call("korg.led(1, 2) // note, (|"), null);
});

test("hovering names the API entry, a key, an LED, an event, a group, a handler value and a code number", () => {
  assert.equal(hover("korg.disp|lay.text(1)").info.signature, "korg.display.text(text, x, y)");
  assert.deepEqual([hover("korg.disp|lay.text(1)").from, hover("korg.disp|lay.text(1)").to], [0, "korg.display.text".length]);
  assert.match(render(hover("if (key == korg.key.T|AP)").info.text), /Taste TAP, Code 3/);
  assert.match(render(hover("korg.led(korg.l|ed.TAP, 1)").info.text), /LED TAP, Nummer 20/);
  assert.equal(hover("korg.l|ed(20, 1)").info.signature, "korg.led(index, level)");
  assert.match(render(hover(`korg.onEvent("butt|onPress", (key) => {})`).info.text), /Taste/);
  assert.match(render(hover(`korg.onEvent("buttonPress", (ke|y) => {})`).info.text), /Tastencode/);
  assert.match(render(hover(`korg.app("A", "GA|MES");`).info.text), /GAMES/);
  assert.match(render(hover("if (key == 1|1) {}").info.text), /11 ist die Taste/);
  assert.equal(hover("korg.on|Event(\"x\", y)").info.name, "korg.onEvent");
  assert.equal(hover("let some|thing = 1;"), null);
  assert.equal(hover("// korg.led|"), null);
  assert.equal(hover(`let s = "korg.led|";`), null);
  assert.equal(hover("korg.led.NOPE|"), null);
});

test("an error range starts at the error's column and covers the word there", () => {
  const text = "let a = 1;\nlet = 2;\nkorg.nope(3);\n";
  assert.deepEqual(errorRange(text, { line: 2, column: 5 }), { from: 15, to: 16 });
  assert.deepEqual(errorRange(text, { line: 3, column: 1 }), { from: 20, to: 29 });
  const wide = errorRange(text, { line: 1, column: 99 });
  assert.ok(wide.from >= 0 && wide.to <= text.indexOf("\n") && wide.to - wide.from === 1, "a column past the line end stays on the line");
  const result = compile("let a = 1;\nlet = 2;\n", { name: "x" });
  const range = errorRange("let a = 1;\nlet = 2;\n", result.errors[0]);
  assert.equal(range.from >= 11 && range.to <= 19 && range.to > range.from, true, "the compiler's own error lands on its line");
});

test("how a range and a place read", () => {
  assert.equal(rangeText({ kind: "int", min: 0, max: 87 }), "0 bis 87");
  assert.equal(rangeText({ kind: "int", min: -2147483648, max: 2147483647 }), "ganze Zahl");
  assert.equal(allowedIn(API.find(a => a.name === "korg.store.get")), "überall");
});
