import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FLOW, LINKS, FOLDERS, DEVICES, CASES } from "../data/rescue.mjs";

const ROOT = new URL("../", import.meta.url);
const nodes = Object.entries(FLOW);
const text = node => JSON.stringify(node.say);

test("every answer and every follow-up leads to a node, and every node is reached", () => {
  const reached = new Set(["start"]);
  for (const [id, n] of nodes) {
    for (const c of n.choices ?? []) { assert.ok(FLOW[c.to], `${id} leads to missing ${c.to}`); reached.add(c.to); }
    if (n.next) { assert.ok(FLOW[n.next], `${id} follows on to missing ${n.next}`); reached.add(n.next); }
    assert.ok(!(n.next && n.choices), `${id} both waits and follows on`);
  }
  assert.deepEqual(nodes.map(([id]) => id).filter(id => !reached.has(id)), []);
  assert.deepEqual(FLOW.start.choices.map(c => c.to), CASES.map(c => c.id));
});

test("only answers: no evidence markers on the page, and links point at LINKS", () => {
  for (const [id, n] of nodes) assert.ok(!("status" in n) && !("note" in n), `${id} still carries a marker`);
  assert.doesNotMatch(JSON.stringify(FLOW), /gemessen|offline gelesen|hergeleitet|Emulator/);
  const parts = JSON.stringify(FLOW).match(/"link":"(\w+)"/g) ?? [];
  for (const p of parts) assert.ok(LINKS[p.slice(8, -1)] || p === '"link":"issueNew"', p);
});

test("no way ends without help: every end is a device that runs again, or the way to Kuhler Buhler with the answers in a new issue", () => {
  const ends = nodes.filter(([, n]) => !n.choices && !n.next).map(([id]) => id).sort();
  assert.deepEqual(ends, ["ask", "cardfixed", "works"]);
  assert.match(JSON.stringify(FLOW.ask.say), /issueNew.*instagram/);
  for (const id of ["stuck", "dark"]) assert.equal(FLOW[id].next, "ask", id);
});

test("the folders are the four device cards, and docs/rettung.md carries the same paths", () => {
  assert.deepEqual(FOLDERS.map(f => f.path), [
    "KORG/electribe sampler/System/SYSTEM.VSB",
    "KORG/electribe/System/SYSTEM.VSB",
    "KORG/hacktribe/System/SYSTEM.VSB",
    "KORG/blechtribe/System/SYSTEM.VSB",
  ]);
  const doc = readFileSync(new URL("docs/rettung.md", ROOT), "utf8");
  for (const f of FOLDERS) assert.ok(doc.includes(f.path), `${f.path} is missing in docs/rettung.md`);
});

test("EXIT helping is not the end: without the card, then the plugin and settings files, else the firmware back", () => {
  assert.equal(FLOW.fixed.next, "nocard");
  assert.deepEqual(FLOW.nocard.choices.map(c => c.to), ["cardfiles", "backup"]);
  assert.deepEqual(FLOW.cardfiles.say.filter(l => l.path).map(l => l.path), ["KORG/blechtribe/Plugin/e2sPlugin.all", "KORG/blechtribe/settings.a.bin", "KORG/blechtribe/settings.b.bin"]);
  assert.deepEqual(FLOW.cardfiles.choices.map(c => c.to), ["cardfixed", "backup"]);
});

test("00 and the update prompt go through Korg's file of the device's colour", () => {
  for (const id of ["zero:card", "prompt"]) assert.equal(FLOW[id].next, "color:update");
  assert.deepEqual(FLOW.zero.choices.map(c => c.to), ["reboot", "zero:card"], "00 waits first, the card only when it stays");
  assert.equal(FLOW["card:red"].say.at(-1).path, "KORG/electribe sampler/System/SYSTEM.VSB");
  assert.equal(FLOW["card:blue"].say.at(-1).path, "KORG/electribe/System/SYSTEM.VSB");
  assert.match(text(FLOW["update:prompt"]), /ENTER/);
});

test("Blechy speaks plainly, nobody gets shouted at, and the hard cases name the official guide", () => {
  for (const [id, n] of nodes) {
    assert.doesNotMatch(text(n), /Bootloader|JTAG|OpenOCD|0x|Panel-Controller|Flash/, `${id} says it up front`);
    assert.notEqual(n.mood, "angry", id);
  }
  for (const id of ["dark", "stuck"]) assert.deepEqual(FLOW[id].source.map(p => p.link), ["debrick"], id);
});

test("the text has no em or en dash", () => {
  assert.doesNotMatch(JSON.stringify([FLOW, LINKS, FOLDERS, DEVICES, CASES]), /[–—]/);
});
