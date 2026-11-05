import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { API_VERSION } from "../data/script/contract.mjs";
import { OBJECTS, OBJECT_BY_PATH, OBJECT_BASES, objectChildren } from "../data/script/objects.mjs";
import { PROPERTY_BY_PATH } from "../data/script/properties.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import { decodeBlob } from "../src/script/blob.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { asmInclude } from "../src/script/arm-tables.mjs";

// The object tree of API 10 (data/script/objects.mjs, thoughts plan 2026-10-28-plugin-api-objektbaum, phase 2).
const INTENSITY = "korg.menu.blech.customizations.display.intensity";
const build = source => {
  const result = compile(source, { name: "objects" });
  assert.ok(result.ok, result.errors?.map(formatError).join("\n"));
  return result.blob;
};
const refused = source => {
  const result = compile(source, { name: "objects" });
  assert.equal(result.ok, false);
  return result.errors.map(e => e.message).join("\n");
};
const run = source => {
  const device = new SimDevice();
  assert.ok(device.load(build(source)).ok);
  device.frame();
  device.frame();
  return device;
};
const stored = (device, slot) => device.runtime.scripts[0].store.values[slot];

test("ids are unique and dense, every leaf is a property with its range, an action is none", () => {
  assert.deepEqual(OBJECTS.map(o => o.id), OBJECTS.map((_, i) => i));
  for (const o of OBJECTS) {
    if (o.action) {
      assert.equal(PROPERTY_BY_PATH.get(o.path), undefined, o.path);
      assert.ok(o.write, o.path);
      continue;
    }
    const prop = PROPERTY_BY_PATH.get(o.path);
    assert.ok(prop, o.path);
    assert.deepEqual(prop.read, ["korg.get", [o.id, -1]]);
    assert.deepEqual(prop.write, o.write ? ["korg.set", [o.id, -1, "value"]] : null);
    assert.deepEqual(prop.range, [o.min, o.max]);
    assert.ok(o.min <= o.factory && o.factory <= o.max, o.path);
    assert.ok(o.since >= 10 && o.since <= API_VERSION, o.path);
  }
});

test("the INTENSITY leaf sits where the menu keeps it", () => {
  const menu = readFileSync(new URL("../tools/patch/script_menu.s", import.meta.url), "utf8");
  const at = parseInt(menu.match(/^\.equ MX_INTENS, (-?0x[0-9A-Fa-f]+)/m)[1], 16);
  assert.equal(OBJECT_BY_PATH.get(INTENSITY).offset, at);
});

test("the include carries one row of constants per leaf", () => {
  const equ = Object.fromEntries([...asmInclude().matchAll(/^\.equ (OBJ_\w+), (\S+)$/gm)].map(m => [m[1], Number(m[2])]));
  assert.equal(equ.OBJ_COUNT, OBJECTS.length);
  for (const o of OBJECTS) {
    assert.equal(equ[`OBJ_${o.id}_MIN`], o.min);
    assert.equal(equ[`OBJ_${o.id}_MAX`], o.max);
    assert.equal(equ[`OBJ_${o.id}_OFFSET`], o.offset);
  }
});

test("a path reads and sets through korg.get and korg.set and needs API 10", () => {
  const blob = build(`korg.onEvent("ready", () => { ${INTENSITY} = 3; korg.store.set(0, ${INTENSITY}); });`);
  assert.equal(decodeBlob(blob).header.apiVersion, 10);
  const device = run(`korg.onEvent("ready", () => { ${INTENSITY} = 3; korg.store.set(0, ${INTENSITY}); ${INTENSITY} += 2; korg.store.set(1, ${INTENSITY}); });`);
  assert.equal(stored(device, 0), 3);
  assert.equal(stored(device, 1), 5);
  assert.equal(device.hardware.objects[0], 5);
});

test("a value outside the range is clamped and counted at run time", () => {
  const device = run(`let v = 40; korg.onEvent("ready", () => { ${INTENSITY} = v; korg.store.set(0, ${INTENSITY}); v = -3; ${INTENSITY} = v; korg.store.set(1, ${INTENSITY}); korg.store.set(2, korg.system.repairs); });`);
  assert.deepEqual([stored(device, 0), stored(device, 1), stored(device, 2)], [15, 0, 2]);
});

test("the compiler refuses an unknown path, a read-only leaf and a known value outside the range", () => {
  assert.match(refused(`korg.onEvent("ready", () => { korg.menu.blech.customizations.display.intensitty = 1; });`),
    /korg\.menu\.blech\.customizations\.display\.intensitty.*intensity/);
  assert.match(refused(`korg.onEvent("ready", () => { korg.menu.blech.custom = 1; });`), /customizations/);
  assert.match(refused(`korg.onEvent("ready", () => { korg.system.repairs = 0; });`), /korg\.system\.repairs/);
  assert.match(refused(`korg.onEvent("ready", () => { ${INTENSITY} = 300; });`), /0.*15.*300/);
  assert.match(refused(`korg.onEvent("ready", () => { ${INTENSITY} = -1; });`), /-1/);
  assert.ok(build(`korg.onEvent("ready", () => { ${INTENSITY} = 15; });`));
});

test("the children of a branch are what error messages and the editor list", () => {
  assert.deepEqual(objectChildren("korg.menu.blech"), ["customizations", "features", "write"]);
  assert.deepEqual(objectChildren("korg.menu.blech.customizations"), ["display", "led", "padColor", "powerSave"]);
  assert.deepEqual(objectChildren("korg.menu.blech.customizations.display"), ["intensity", "red", "green", "blue", "invert"]);
  assert.deepEqual(objectChildren("korg.menu.blech.customizations.led.meter"), ["still", "low", "mid", "loud"]);
  assert.deepEqual(objectChildren(INTENSITY), []);
});

test("both plugin docs list every leaf with its range", () => {
  for (const [file, to] of [["docs/plugins.md", "bis"], ["docs/plugins.en.md", "to"]]) {
    const doc = readFileSync(new URL(`../${file}`, import.meta.url), "utf8");
    for (const o of OBJECTS) {
      const row = doc.split("\n").find(l => l.startsWith(`| \`${o.path}${o.action ? "()" : ""}\``));
      assert.ok(row, `${file}: ${o.path}`);
      if (o.action) continue;
      assert.match(row, new RegExp(`${o.min}( \\([^)]*\\))? ${to} ${o.max}`), `${file}: ${o.path}`);
    }
  }
});

test("korg.system.keepAwake() is a call that sets its leaf to 1, and it takes no values", () => {
  const device = run(`korg.onEvent("ready", () => { korg.system.keepAwake(); korg.store.set(0, korg.system.testMode); });`);
  assert.equal(device.hardware.objects[OBJECT_BY_PATH.get("korg.system.keepAwake").id], 1);
  assert.equal(stored(device, 0), 0);
  assert.match(refused(`korg.onEvent("ready", () => { korg.system.keepAwake(1); });`), /korg\.system\.keepAwake/);
  assert.match(refused(`korg.onEvent("ready", () => { let x = korg.system.keepAwake; });`), /keepAwake/);
});

test("a plugin reads the test mode but cannot switch it; the remote runtime writes the byte the leaf reads", () => {
  assert.match(refused(`korg.onEvent("ready", () => { korg.system.testMode = 1; });`), /korg\.system\.testMode/);
  assert.equal(OBJECT_BY_PATH.get("korg.system.testMode").write, false);
  const remote = readFileSync(new URL("../tools/patch/script_remote.s", import.meta.url), "utf8");
  assert.match(remote, /ldr r0, =objects_test_mode\n    strb r2, \[r0\]\n    bl testmode_apply/);
  const objects = readFileSync(new URL("../tools/patch/script_objects.s", import.meta.url), "utf8");
  const state = objects.slice(objects.indexOf("objects_state:"));
  assert.ok(state.indexOf("objects_test_mode:") > 0 && OBJECT_BY_PATH.get("korg.system.testMode").offset === 4);
});

// API 17: every page of CUSTOMIZATION and FEATURES (phase 8 of the plan).
const MENU_S = readFileSync(new URL("../tools/patch/script_menu.s", import.meta.url), "utf8");
const signed = name => { const v = MENU_S.match(new RegExp(`^\\.equ ${name}, (-?)(0x[0-9A-Fa-f]+|\\d+)`, "m")); return (v[1] ? -1 : 1) * Number(v[2]); };

test("the leaves of the menu pages sit where the menu keeps them", () => {
  const at = {
    "customizations.display.red": "M_BL_R", "customizations.display.green": "M_BL_G", "customizations.display.blue": "M_BL_B",
    "customizations.display.invert": "M_INV", "customizations.led.mode": "M_LED_MODE",
    "customizations.led.red": "M_LED_R", "customizations.led.green": "M_LED_G", "customizations.led.blue": "M_LED_B",
    "customizations.powerSave.displayLight": "MX_SAVE", "features.mfx2": "M_SET_MFX",
    "features.patternConfirm": "M_PC", "features.tapMotion": "M_TM", "features.noteAssist": "M_NA", "features.initPattern": "IP_SLOT",
  };
  for (const [path, name] of Object.entries(at)) assert.equal(OBJECT_BY_PATH.get(`korg.menu.blech.${path}`).offset, signed(name), path);
  const meter = signed("MX_METER");
  ["still", "low", "mid", "loud"].forEach((zone, i) => assert.equal(OBJECT_BY_PATH.get(`korg.menu.blech.customizations.led.meter.${zone}`).offset, meter + i, zone));
  for (const [path, name] of [["features.patternConfirm", "PS_SETTING"], ["features.tapMotion", "TM_SETTING"], ["features.noteAssist", "NA_SETTING"]]) {
    assert.equal(OBJECT_BY_PATH.get(`korg.menu.blech.${path}`).mirror, signed(name), path);
  }
  assert.equal(OBJECT_BY_PATH.get("korg.menu.blech.features.lastPattern").offset, signed("LP_SETTING"));
  assert.equal(OBJECT_BY_PATH.get("korg.menu.blech.features.stereo1Pad").offset, signed("SP_SETTING"));
});

test("the range of a leaf is the range the page's dial runs through", () => {
  const meter = MENU_S.slice(MENU_S.indexOf("menu_slot_value:"), MENU_S.indexOf("menu_value_byte:"));
  assert.match(meter, /METER_RAINBOW[^\n]*\n[^]*METER_OFF/);
  const top = name => OBJECT_BY_PATH.get(`korg.menu.blech.customizations.led.meter.${name}`).max;
  assert.deepEqual(["still", "low", "mid", "loud"].map(top), [signed("METER_OFF"), 7, 7, signed("METER_RAINBOW")]);
  assert.equal(OBJECT_BY_PATH.get("korg.menu.blech.features.tapMotion").max, 2);
  assert.equal(OBJECT_BY_PATH.get("korg.menu.blech.features.initPattern").max, 250);
  assert.equal(OBJECT_BY_PATH.get("korg.menu.blech.customizations.powerSave.ledDimming").max, MENU_S.match(/^led_dim_percent:[^]*?\.byte ([^\n]+)/m)[1].split(",").length - 1);
});

test("the bases of the table are the ones script_objects.s knows by number", () => {
  const objects = readFileSync(new URL("../tools/patch/script_objects.s", import.meta.url), "utf8");
  for (const [name, base] of [["OBJ_BASE_ABS", "abs"], ["OBJ_BASE_GLOBAL", "global"], ["OBJ_BASE_PAD", "pad"]]) {
    assert.equal(Number(objects.match(new RegExp(`^\\.equ ${name}, (\\d+)`, "m"))[1]), OBJECT_BASES.indexOf(base), name);
  }
});

test("a plugin sets a page and the simulated device keeps it inside the range", () => {
  const P = "korg.menu.blech";
  const device = run(`let v = 9; korg.onEvent("ready", () => { ${P}.features.tapMotion = 2; ${P}.customizations.padColor.select = v; ${P}.customizations.led.meter.still = v + 3;
    korg.store.set(0, ${P}.features.tapMotion); korg.store.set(1, ${P}.customizations.padColor.select); korg.store.set(2, ${P}.customizations.led.meter.still); korg.store.set(3, ${P}.features.stereo1Pad); });`);
  assert.deepEqual([0, 1, 2, 3].map(i => stored(device, i)), [2, 2, 9, 1]);
});

test("korg.menu.blech.write() is a call without values and needs API 17", () => {
  const device = run(`korg.onEvent("ready", () => { korg.menu.blech.write(); });`);
  assert.equal(device.hardware.objects[OBJECT_BY_PATH.get("korg.menu.blech.write").id], 1);
  assert.match(refused(`korg.onEvent("ready", () => { korg.menu.blech.write(1); });`), /korg\.menu\.blech\.write/);
  assert.match(refused(`korg.onEvent("ready", () => { korg.menu.blech.write = 1; });`), /write/);
});
