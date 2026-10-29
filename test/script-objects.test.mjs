import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { API_BY_NAME } from "../data/script/contract.mjs";
import { OBJECTS, OBJECT_BY_PATH, objectChildren } from "../data/script/objects.mjs";
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
    assert.ok(o.since <= API_BY_NAME.get("korg.get").since || o.since === 10, o.path);
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
  assert.deepEqual(objectChildren("korg.menu.blech"), ["customizations"]);
  assert.deepEqual(objectChildren("korg.menu.blech.customizations.display"), ["intensity"]);
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
