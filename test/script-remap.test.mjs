import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { KEY_NAMES, LED_NAMES } from "../data/script/names.mjs";
import { ERROR } from "../data/script/contract.mjs";

const key = name => KEY_NAMES.find(k => k.name === name).value;
const led = name => LED_NAMES.find(l => l.name === name).value;

function load(source, device = new SimDevice()) {
  const result = compile(source, { name: "remap" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  const loaded = device.load(result.blob);
  return { device, loaded, v: name => loaded.script?.vars[result.info.symbols[name].slot] };
}

const SPY = `korg.remapKey(korg.key.PART_ERASE, korg.key.PART_MUTE);
let last = -1;
korg.onEvent("buttonPress", (k) => { last = k; });`;

test("a remapped key reaches the scripts as the other key, other keys stay as they are", () => {
  const { device, loaded, v } = load(SPY);
  assert.ok(loaded.ok);
  device.run(1);
  device.post("buttonPress", key("PART_ERASE"));
  device.run(1);
  assert.equal(v("last"), key("PART_MUTE"));
  device.post("buttonPress", key("TAP"));
  device.run(1);
  assert.equal(v("last"), key("TAP"));
  assert.equal(device.runtime.remapped(key("PART_ERASE")), key("PART_MUTE"));
  assert.equal(device.runtime.remapped(key("TAP")), key("TAP"));
});

test("the remap ends with its plugin, and the same key twice takes it back", () => {
  const { device } = load(SPY);
  device.run(1);
  device.runtime.scripts[0].script.state = "disabled";
  assert.equal(device.runtime.remapped(key("PART_ERASE")), key("PART_ERASE"));

  const back = load(`korg.remapKey(korg.key.PART_ERASE, korg.key.PART_MUTE);
korg.remapKey(korg.key.TAP, korg.key.TAP);`).device;
  back.run(1);
  assert.equal(back.runtime.remapped(key("PART_ERASE")), key("PART_ERASE"));
});

test("EXIT can be neither the key nor the target", () => {
  for (const source of ["korg.remapKey(korg.key.EXIT, korg.key.TAP);", "korg.remapKey(korg.key.TAP, korg.key.EXIT);"]) {
    const { loaded } = load(source);
    assert.equal(loaded.ok, false);
    assert.equal(loaded.error.code, ERROR.API_ARG);
  }
});

// Part Mute on PART ERASE: a plugin made for one device with a broken PART MUTE key, not in the catalog.
test("Part Mute on PART ERASE: the key becomes PART MUTE and its LED follows the pad mode", () => {
  const { device, loaded } = load(readFileSync(new URL("./fixtures/scripts/partmute.js", import.meta.url), "utf8"));
  assert.ok(loaded.ok, loaded.error?.message);
  device.run(1);
  assert.equal(device.runtime.remapped(key("PART_ERASE")), key("PART_MUTE"));
  device.post("buttonPress", key("PART_ERASE"));
  device.run(1);
  assert.equal(device.leds[led("PART_ERASE")], 255, "PART MUTE mode on: the PART ERASE LED is lit");
  device.post("buttonPress", key("SEQUENCER"));
  device.run(1);
  assert.equal(device.leds[led("PART_ERASE")], 0, "another pad mode: the LED goes out");
  device.post("buttonPress", key("PART_ERASE"));
  device.run(13);
  assert.equal(device.leds[led("PART_ERASE")], 255);
  assert.deepEqual(device.status().scripts.map(s => s.fault ?? null), [null]);
});
