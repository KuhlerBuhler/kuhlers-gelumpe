import { test } from "node:test";
import assert from "node:assert/strict";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice, probe } from "../src/script/sim.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SCRIPT_APPS } from "../data/script/contract.mjs";

const build = (source, name = "app") => {
  const result = compile(source, { name });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const failure = source => formatError(compile(source).errors[0]);
const ink = bytes => bytes.reduce((n, b) => n + (b ? 1 : 0), 0);

const COUNTER = `korg.app("Zaehler", "TOOLS");
let frames = 0;
let opens = 0;
let closes = 0;
let presses = 0;
korg.onEvent("open", () => { opens += 1; frames = 0; korg.display.clear(); korg.display.text("auf", 0, 0); });
korg.onEvent("close", () => { closes += 1; });
korg.onEvent("frame", () => { frames += 1; korg.display.number(frames, 0, 16); });
korg.onEvent("buttonPress", (key) => { presses += 1; });
`;

/** The global variables of a script by name, read from the device's runtime. */
const variables = (device, index = 0) => {
  const entry = device.runtime.scripts[index];
  const symbols = compile(COUNTER).info.symbols;
  return Object.fromEntries(Object.entries(symbols).map(([name, s]) => [name, entry.script.vars[s.slot]]));
};

test("korg.app declares the plugin as an app: top level, once, a name of 1 to 15 characters and a group", () => {
  const result = compile(COUNTER, { name: "zaehler" });
  assert.ok(result.ok);
  assert.deepEqual(result.info.app, { name: "Zaehler", group: "TOOLS" });
  assert.equal(result.info.apiVersion, 5);
  assert.equal(compile("let a = 1;").info.app, null, "a plugin without korg.app is no app");
  assert.ok(compile(`korg.app("GAMES ONLY", "GAMES");`).ok);
  assert.match(failure(`korg.app("A", "GAMES");\nkorg.app("B", "TOOLS");`), /Zeile 2, Spalte 1: Ein Plugin ist höchstens eine App/);
  assert.match(failure(`function f() { korg.app("A", "GAMES"); }`), /korg\.app steht ganz oben/);
  assert.match(failure(`if (1) { korg.app("A", "GAMES"); }`), /nicht in einem Block/);
  assert.match(failure(`let a = korg.app("A", "GAMES");`), /als eigene Anweisung ganz oben/);
  assert.match(failure(`korg.app("A", "MUSIC");`), /Die Gruppe „MUSIC“ gibt es nicht\. Es gibt: GAMES, TOOLS\./);
  assert.match(failure(`korg.app("A");`), /nimmt zwei Argumente/);
  assert.match(failure(`const N = "A";\nkorg.app(N, "GAMES");`), /Der Name der App muss ein Text in Anführungszeichen sein/);
  assert.match(failure(`korg.app("", "GAMES");`), /1 bis 15 Zeichen/);
  assert.match(failure(`korg.app("0123456789abcdef", "GAMES");`), /1 bis 15 Zeichen/);
  assert.match(failure(`korg.onEvent("nope", () => {});`), /close, .*open/, "the event list names open and close");
  assert.match(failure(`korg.onEvent("open", (a) => {});`), /liefert 0 Werte/);
});

test("the block of an app carries the call in the body, so the device registers it when the plugin starts", () => {
  const parts = decodeBlob(build(COUNTER, "zaehler"));
  assert.ok(parts.ok);
  assert.equal(parts.header.apiVersion, 5);
  assert.deepEqual(parts.strings.slice(0, 2), ["Zaehler", "TOOLS"]);
});

test("a plugin that is no app cannot draw: its display calls do nothing, its LEDs work", () => {
  const device = new SimDevice();
  assert.ok(device.load(build(`korg.onEvent("frame", () => { korg.display.clear(); korg.display.rect(0, 0, 128, 64); korg.led(korg.led.TAP, 255); });`, "tool")).ok);
  assert.deepEqual(device.run(5), []);
  assert.equal(ink(device.display.bytes), 0, "nothing reaches the display model");
  assert.equal(ink(device.shown), 0);
  assert.equal(device.leds[20], 255);
  assert.deepEqual(device.apps, []);
});

test("loading an app leaves the display alone: nothing is shown and nothing runs until the user opens it", () => {
  const device = new SimDevice();
  assert.ok(device.load(build(COUNTER, "zaehler")).ok);
  assert.deepEqual(device.run(10), []);
  assert.deepEqual(device.apps.map(a => [a.name, a.group, a.open]), [["Zaehler", "TOOLS", false]]);
  assert.equal(ink(device.display.bytes), 0);
  assert.equal(ink(device.shown), 0, "the device's own screen stays");
  assert.deepEqual(variables(device), { frames: 0, opens: 0, closes: 0, presses: 0 }, "frame does not run for a closed app");
  device.post("buttonPress", 3);
  device.frame();
  assert.equal(variables(device).presses, 1, "other events reach it all the time");
});

test("an open app owns the display, gets open and then frame, and EXIT closes it before the plugin sees the key", () => {
  const device = new SimDevice();
  device.load(build(COUNTER, "zaehler"));
  device.run(3);
  assert.equal(device.openApp(0), true);
  device.run(4);
  assert.deepEqual(variables(device), { frames: 4, opens: 1, closes: 0, presses: 0 });
  assert.ok(ink(device.shown) > 5, "the picture shows");
  device.post("buttonPress", 13);
  assert.equal(device.apps[0].open, false, "EXIT closes at once");
  assert.equal(ink(device.shown), 0, "the display is the device's again");
  device.run(3);
  assert.deepEqual(variables(device), { frames: 4, opens: 1, closes: 1, presses: 0 }, "the plugin got close, never EXIT, and no frame while closed");
  device.post("buttonPress", 13);
  device.frame();
  assert.equal(variables(device).presses, 1, "with no app open EXIT is an ordinary key");
  device.openApp(0);
  device.run(2);
  assert.equal(variables(device).opens, 2);
  assert.equal(variables(device).frames, 2, "open starts it anew");
});

test("EXIT cannot be swallowed: a plugin that catches every key still lets the user out", () => {
  const device = new SimDevice();
  device.load(build(`korg.app("Falle", "GAMES");
let exits = 0;
korg.onEvent("open", () => { korg.display.rect(0, 0, 128, 64); });
korg.onEvent("buttonPress", (key) => { if (key == korg.key.EXIT) exits += 1; });
korg.onEvent("frame", () => { korg.display.rect(0, 0, 128, 64); });`, "falle"));
  device.openApp(0);
  device.run(3);
  assert.ok(ink(device.shown) > 1000);
  device.post("buttonPress", 13);
  assert.equal(device.apps[0].open, false);
  device.run(2);
  assert.equal(device.runtime.scripts[0].script.vars[0], 0, "the plugin never saw the key");
  assert.equal(ink(device.shown), 0);
});

test("open and close go to their own app only, and drawing stays with the open one", () => {
  const device = new SimDevice();
  const one = build(`korg.app("Eins", "GAMES");\nlet opens = 0;\nkorg.onEvent("open", () => { opens += 1; korg.display.text("EINS", 0, 0); });`, "eins");
  const two = build(`korg.app("Zwei", "TOOLS");\nlet opens = 0;\nkorg.onEvent("open", () => { opens += 1; korg.display.text("ZWEI", 0, 0); });\nkorg.onEvent("frame", () => { korg.display.rect(0, 40, 128, 8); });`, "zwei");
  device.load(one);
  device.load(two);
  assert.deepEqual(device.apps.map(a => [a.id, a.name, a.group]), [[0, "Eins", "GAMES"], [1, "Zwei", "TOOLS"]]);
  device.run(2);
  device.openApp(1);
  device.run(2);
  const opens = () => device.runtime.scripts.map(e => e.script.vars[0]);
  assert.deepEqual(opens(), [0, 1], "only the opened app got open");
  const picture = [...device.shown];
  device.openApp(0);
  device.run(2);
  assert.deepEqual(opens(), [1, 1]);
  assert.notDeepEqual([...device.shown], picture);
  assert.equal(device.apps.filter(a => a.open).length, 1, "one app is open at a time");
});

test("the menu lists GAMES before TOOLS, each in the order the apps were declared, and at most eight apps", () => {
  const rt = new ScriptRuntime({ frameMs: Infinity });
  const groups = ["TOOLS", "GAMES", "TOOLS", "GAMES"];
  groups.forEach((g, i) => assert.ok(rt.add(build(`korg.app("App${i}", "${g}");`, `app${i}`)).ok));
  assert.deepEqual(rt.appList.map(a => [a.name, a.group]), [["App1", "GAMES"], ["App3", "GAMES"], ["App0", "TOOLS"], ["App2", "TOOLS"]]);
  for (let i = 4; i < 12; i++) rt.add(build(`korg.app("App${i}", "GAMES");`, `app${i}`));
  assert.equal(rt.apps.length, SCRIPT_APPS.max, "the ninth app is not listed");
  assert.equal(rt.apps.length, 8);
});

test("a fault of the open app shows on its screen, a fault of another script does not disturb it", () => {
  const device = new SimDevice();
  device.load(build(`korg.app("Kaputt", "GAMES");\nlet z = 0;\nkorg.onEvent("frame", () => { z = 1 / z; });`, "kaputt"));
  device.load(build(`korg.app("Heil", "TOOLS");\nkorg.onEvent("open", () => { korg.display.rect(0, 0, 128, 64); });`, "heil"));
  device.load(build(`let z = 0;\nkorg.onEvent("frame", () => { z = 1 / z; });`, "ohne"));
  device.openApp(1);
  device.run(3);
  assert.equal(ink(device.shown), 1024, "the other scripts' faults left the open app's picture alone");
  device.closeApp();
  device.openApp(0);
  const faults = device.run(2);
  assert.equal(faults.some(f => f.script === "kaputt"), true);
  assert.ok(ink(device.shown) > 0 && ink(device.shown) < 600, "the open app's own fault shows its name, line and error");
});

test("the probe opens the app, so the lines of its screen are run", () => {
  const result = probe(build(COUNTER, "zaehler"), []);
  assert.equal(result.ok, true);
  assert.deepEqual(result.lines.missing.length > 0, true, "the buttonPress body was not reached");
  assert.ok(!result.lines.missing.includes(8), "open and frame ran");
});

const TAKER = `let opens = 0;
let closes = 0;
let granted = 0;
korg.onEvent("close", () => { closes += 1; });
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) {
    granted = korg.display.take();
    korg.display.text("mine", 0, 0);
  }
  if (key == korg.key.PLAY) korg.display.release();
});
korg.onEvent("frame", () => { korg.display.number(7, 0, 16); });`;

test("a plugin that is no app can take the display with korg.display.take(), and EXIT ends the takeover", () => {
  const device = new SimDevice();
  device.load(build(TAKER, "taker"));
  assert.deepEqual(device.run(5), []);
  assert.equal(ink(device.display.bytes), 0, "loading and running alone never draws");
  device.post("buttonPress", 3);
  device.run(2);
  assert.equal(device.runtime.scripts[0].script.vars[2], 1, "take was granted");
  assert.ok(ink(device.shown) > 10, "now it draws");
  device.post("buttonPress", 13);
  assert.equal(ink(device.shown), 0, "EXIT ends it at once");
  device.run(2);
  assert.equal(device.runtime.scripts[0].script.vars[1], 1, "the plugin got close, never the key");
  device.post("buttonPress", 3);
  device.post("buttonPress", 2);
  device.run(2);
  assert.equal(ink(device.shown), 0, "release gives the display back");
});

test("take is refused for an app and while another script owns the display", () => {
  const device = new SimDevice();
  device.load(build(TAKER, "taker"));
  device.load(build(`korg.app("Spiel", "GAMES");\nlet got = 5;\nkorg.onEvent("buttonPress", (key) => { got = korg.display.take(); });`, "spiel"));
  device.post("buttonPress", 3);
  device.run(2);
  assert.equal(device.runtime.scripts[1].script.vars[0], 0, "an app does not take, it is opened from the menu");
  assert.ok(ink(device.shown) > 0, "the taker still owns the display");
});

test("the examples in docs/plugins.md, docs/plugins.en.md and the device test compile", async () => {
  const { readFileSync } = await import("node:fs");
  for (const file of ["../docs/plugins.md", "../docs/plugins.en.md", "../docs/geraetetests/blech-datei.md"]) {
    const text = readFileSync(new URL(file, import.meta.url), "utf8");
    const examples = [...text.matchAll(/```js\n([\s\S]*?)```/g)].map(m => m[1]).filter(code => !code.includes("..."));
    assert.ok(examples.length > 0, file);
    for (const code of examples) {
      const result = compile(code, { name: "beispiel" });
      assert.ok(result.ok, `${file}: ${result.errors?.map(formatError).join(" ")}\n${code}`);
    }
  }
});
