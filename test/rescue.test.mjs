import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import RESCUE, { STATUS, LINKS } from "../data/rescue.mjs";

const ROOT = new URL("../", import.meta.url);
const steps = RESCUE.cases.flatMap(c => c.steps);

test("every step and limit has a known status and a source file that exists", () => {
  for (const s of steps) {
    assert.ok(STATUS[s.status], `unknown status ${s.status}`);
    assert.ok(existsSync(new URL(s.source, ROOT)), `${s.source} does not exist`);
  }
  for (const c of RESCUE.cases) assert.ok(existsSync(new URL(c.limitSource, ROOT)), `${c.limitSource} does not exist`);
  for (const f of RESCUE.folders) assert.ok(existsSync(new URL(f.source, ROOT)), `${f.source} does not exist`);
  assert.ok(existsSync(new URL(RESCUE.stop.source, ROOT)));
});

test("the folders are the three the docs name, and docs/rettung.md carries the same paths", () => {
  assert.deepEqual(RESCUE.folders.map(f => f.path), [
    "KORG/hacktribe/System/SYSTEM.VSB",
    "KORG/blechtribe/System/SYSTEM.VSB",
    "KORG/electribe sampler/System/SYSTEM.VSB",
  ]);
  const doc = readFileSync(new URL("docs/rettung.md", ROOT), "utf8");
  for (const f of RESCUE.folders) assert.ok(doc.includes(f.path), `${f.path} is missing in docs/rettung.md`);
});

test("the Hacktribe and the BLECH folder are marked measured on the device, Korg's original is not", () => {
  assert.deepEqual(RESCUE.folders.map(f => f.status), ["gemessen", "gemessen", "offen"]);
});

test("nothing about 00 claims a measured way, and the stop sign names the bootloader and JTAG", () => {
  const zero = RESCUE.cases.find(c => c.id === "zero");
  assert.ok(zero.steps.every(s => s.status !== "gemessen"));
  const stop = RESCUE.stop.lines.join(" ");
  assert.match(RESCUE.stop.title, /Bootloader.*nie/);
  assert.match(stop, /JTAG/);
});

test("the text has no em or en dash", () => {
  assert.doesNotMatch(JSON.stringify([RESCUE, STATUS, LINKS]), /[\u2013\u2014]/);
});
