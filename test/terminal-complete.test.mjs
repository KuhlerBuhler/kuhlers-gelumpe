import { test } from "node:test";
import assert from "node:assert/strict";
import { completionsFor } from "../site/app/terminal.mjs";

test("Tab completes the library names from the help lines", () => {
  const found = completionsFor("KORG.ram.", 9);
  assert.equal(found.from, 0);
  assert.deepEqual(found.names.sort(), ["KORG.ram.diff", "KORG.ram.read", "KORG.ram.search", "KORG.ram.snapshot", "KORG.ram.where"]);
  assert.deepEqual(completionsFor("KORG.ram.rea", 12).names, ["KORG.ram.read"]);
  assert.deepEqual(completionsFor("ru", 2)?.names, ["run"]);
});

test("Tab completes korg.* with the source of the plugin editor, also after other text", () => {
  const text = "const a = 1; korg.display.te";
  const found = completionsFor(text, text.length);
  assert.equal(found.from, text.indexOf("korg."));
  assert.ok(found.names.includes("korg.display.text") && found.names.every(n => n.startsWith("korg.display.te")));
  const key = completionsFor("korg.key.TA", 11);
  assert.deepEqual(key.names, ["TAP"]);
});

test("nothing to complete: no token, a finished name, or an unknown word", () => {
  assert.equal(completionsFor("", 0), null);
  assert.equal(completionsFor("KORG.ram.read", 13), null);
  assert.equal(completionsFor("zzz", 3), null);
});
