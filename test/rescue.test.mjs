import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import RESCUE, { STATUS, LINKS } from "../data/rescue.mjs";

const ROOT = new URL("../", import.meta.url);
const steps = RESCUE.cases.flatMap(c => c.steps);

test("every step has a known status", () => {
  for (const s of steps) assert.ok(STATUS[s.status], `unknown status ${s.status}`);
});

test("the folders are the four device cards, and docs/rettung.md carries the same paths", () => {
  assert.deepEqual(RESCUE.folders.map(f => f.path), [
    "KORG/electribe sampler/System/SYSTEM.VSB",
    "KORG/electribe/System/SYSTEM.VSB",
    "KORG/hacktribe/System/SYSTEM.VSB",
    "KORG/blechtribe/System/SYSTEM.VSB",
  ]);
  const doc = readFileSync(new URL("docs/rettung.md", ROOT), "utf8");
  for (const f of RESCUE.folders) assert.ok(doc.includes(f.path), `${f.path} is missing in docs/rettung.md`);
});

test("00 goes through the update prompt with Korg's sampler file, and the stop sign names the bootloader and JTAG", () => {
  const zero = RESCUE.cases.find(c => c.id === "zero");
  assert.ok(zero.steps.some(s => s.act && s.text.includes("KORG/electribe sampler/System/SYSTEM.VSB")));
  assert.ok(zero.steps.some(s => s.act && /ENTER/.test(s.text)));
  const stop = RESCUE.stop.lines.flat().map(w => w.text ?? w).join(" ");
  assert.match(RESCUE.stop.title, /Bootloader.*nie/);
  assert.match(stop, /JTAG/);
});

test("the text has no em or en dash", () => {
  assert.doesNotMatch(JSON.stringify([RESCUE, STATUS, LINKS]), /[\u2013\u2014]/);
});
