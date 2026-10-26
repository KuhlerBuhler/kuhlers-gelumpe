import { test } from "node:test";
import assert from "node:assert/strict";
import { render } from "../src/text.mjs";
import { TEMPLATES, templateSource } from "../data/script/templates.mjs";
import { KEY_NAMES } from "../data/script/names.mjs";
import { ARCHIVE } from "../data/script/contract.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice, probe } from "../src/script/sim.mjs";
import { validName } from "../src/script/workspace.mjs";

const NAMES = ["plugin", "Klick_2", "ABCDEFGHIJKLMNO"];
const key = name => KEY_NAMES.find(n => n.name === name).value;

/** Inputs that make every handler of a template run: TAP early and while the game's block crosses the middle of its lane. */
const INPUTS = [3, 14, 15, 16, 17, 20].map(frame => ({ frame, event: "buttonPress", args: [key("TAP")] }));

test("there is one template for each kind: App in GAMES, App in TOOLS, Hintergrund", () => {
  assert.deepEqual(TEMPLATES.map(t => t.id), ["games", "tools", "background"]);
  assert.deepEqual(TEMPLATES.map(t => render(t.label)), ["App in GAMES", "App in TOOLS", "Hintergrund"]);
  assert.deepEqual(TEMPLATES.map(t => t.group), ["GAMES", "TOOLS", null]);
  assert.throws(() => templateSource("nope", "x"), /Keine Vorlage/);
});

test("every template compiles, fits on the card and uses named keys, a few German comments and the handlers open, frame and buttonPress", () => {
  for (const t of TEMPLATES) {
    for (const name of NAMES) {
      assert.ok(validName(name));
      const source = templateSource(t.id, name);
      const result = compile(source, { name });
      assert.ok(result.ok, `${t.id} as ${name}: ${result.errors?.map(formatError).join("\n")}`);
      assert.ok(result.blob.length < ARCHIVE.maxBlock / 4, `${t.id} is a short template, not ${result.blob.length} bytes`);
      assert.match(source, /korg\.key\.TAP/, `${t.id} compares key with a name`);
      assert.match(source, /korg\.onEvent\("buttonPress"/);
      assert.match(source, /korg\.onEvent\("frame"/);
      if (t.app) assert.match(source, /korg\.onEvent\("open"/);
      const comments = source.split("\n").filter(l => l.trim().startsWith("//"));
      assert.ok(comments.length >= 4 && comments.length <= 9, `${t.id}: ${comments.length} comment lines`);
      assert.match(comments.join(" "), /Menü|Display|Rahmen/, `${t.id} explains itself in German`);
      assert.doesNotMatch(source, /[\u2013\u2014]/, "no em or en dashes");
    }
  }
});

test("an app template declares the chosen name in its group, the background template declares no app", () => {
  for (const t of TEMPLATES) {
    const device = new SimDevice();
    const loaded = device.load(compile(templateSource(t.id, "Mein_Plugin"), { name: "Mein_Plugin" }).blob);
    assert.ok(loaded.ok, JSON.stringify(loaded.error));
    if (t.app) {
      assert.equal(device.apps.length, 1, t.id);
      assert.equal(device.apps[0].name, "Mein_Plugin");
      assert.equal(device.apps[0].group, t.group);
    } else {
      assert.equal(device.apps.length, 0, "a background plugin is no menu entry");
    }
  }
});

test("every template passes the probe, and with a few TAP presses every line with code has run", () => {
  for (const t of TEMPLATES) {
    const { blob } = compile(templateSource(t.id, "probe"), { name: "probe" });
    const bare = probe(blob);
    assert.ok(bare.ok, `${t.id}: ${JSON.stringify(bare.faults)}`);
    assert.ok(bare.lines.covered.length > 0, `${t.id} runs something without any input`);
    const full = probe(blob, INPUTS);
    assert.ok(full.ok, `${t.id}: ${JSON.stringify(full.faults)}`);
    assert.deepEqual(full.lines.missing, [], `${t.id}: lines that never ran`);
  }
});

test("the templates do what they say on the simulated device", () => {
  const run = (id, frames, inputs = []) => {
    const device = new SimDevice();
    const { blob } = compile(templateSource(id, "demo"), { name: "demo" });
    assert.ok(device.load(blob).ok);
    if (device.apps.length) device.openApp(device.apps[0].id);
    assert.deepEqual(device.run(frames, inputs), []);
    return device;
  };
  const lit = device => device.shown.reduce((n, b) => n + b.toString(2).replaceAll("0", "").length, 0);
  assert.ok(lit(run("games", 30)) > 0, "the game draws its block");
  assert.ok(lit(run("tools", 5)) > 0, "the tool draws tempo and count");
  const tapLed = run("tools", 10, INPUTS.slice(0, 1)).leds;
  assert.equal(tapLed[20], 255, "TAP lights the TAP LED once");
  const background = run("background", 60, INPUTS.slice(0, 1));
  assert.equal(lit(background), 0, "no display for a background plugin");
  assert.ok([...background.leds].some(v => v === 255) || background.leds[20] === 0, "the TAP LED is driven");
});
