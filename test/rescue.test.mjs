import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FLOW, LINKS, FOLDERS, DEVICES, CASES, BUTTONS, checkVerdict } from "../data/rescue.mjs";
import { t } from "../site/app/i18n.mjs";

const ROOT = new URL("../", import.meta.url);
const nodes = Object.entries(FLOW);
/** A line as the page reads it in German: a key, link parts, a path, or a text with links in it. */
const line = l => {
  if (typeof l === "string") return t(l);
  if (Array.isArray(l)) return l.map(part => t(part.text)).join("");
  if (l.path) return l.path;
  return t(l.key, { ...l.vars, ...Object.fromEntries(Object.entries(l.links ?? {}).map(([name, part]) => [name, t(part.text)])) });
};
const text = node => [...node.say, ...(node.source ? [node.source] : [])].map(line).join("\n");
/** Everything the page can show, in German. */
const everything = () => [
  ...nodes.flatMap(([, n]) => [text(n), ...(n.choices ?? []).flatMap(c => [t(c.label), c.hint ? t(c.hint) : ""])]),
  ...Object.values(DEVICES).flatMap(d => [t(d.title), d.name]), ...FOLDERS.map(f => t(f.title)), ...Object.values(BUTTONS).map(b => t(b)),
].join("\n");

test("every text of the page is a key of the German table", () => {
  const keys = [];
  for (const [, n] of nodes) {
    for (const l of [...n.say, ...(n.source ? [n.source] : [])]) {
      if (typeof l === "string") keys.push(l);
      else if (Array.isArray(l)) keys.push(...l.map(part => part.text));
      else if (!l.path) keys.push(l.key, ...Object.values(l.links ?? {}).map(part => part.text));
    }
    for (const c of n.choices ?? []) keys.push(c.label, ...(c.hint ? [c.hint] : []));
  }
  keys.push(...Object.values(DEVICES).map(d => d.title), ...FOLDERS.map(f => f.title), ...Object.values(BUTTONS));
  assert.deepEqual(keys.filter(k => t(k) === k), []);
});

test("every answer and every follow-up leads to a node, and every node is reached", () => {
  const reached = new Set(["start"]);
  for (const [id, n] of nodes) {
    for (const c of n.choices ?? []) { assert.ok(FLOW[c.to], `${id} leads to missing ${c.to}`); reached.add(c.to); }
    if (n.next) { assert.ok(FLOW[n.next], `${id} follows on to missing ${n.next}`); reached.add(n.next); }
    for (const to of n.read ? [...Object.values(n.read.to), n.read.otherwise] : []) { assert.ok(FLOW[to], `${id} reads on to missing ${to}`); reached.add(to); }
    assert.equal([n.next, n.choices, n.read].filter(Boolean).length <= 1, true, `${id} both waits and follows on`);
    if (n.known) assert.ok(n.choices?.some(c => c.value), `${id} knows something but no answer has a value`);
  }
  assert.deepEqual(nodes.map(([id]) => id).filter(id => !reached.has(id)), []);
  assert.deepEqual(FLOW.start.choices.map(c => c.to), CASES.map(c => c.id));
});

test("only answers: no evidence markers on the page, and links point at LINKS", () => {
  for (const [id, n] of nodes) assert.ok(!("status" in n) && !("note" in n), `${id} still carries a marker`);
  assert.doesNotMatch(everything(), /gemessen|offline gelesen|hergeleitet|offline \(|im Emulator geprüft/);
  const parts = JSON.stringify(FLOW).match(/"link":"(\w+)"/g) ?? [];
  for (const p of parts) assert.ok(LINKS[p.slice(8, -1)] || p === '"link":"issueNew"', p);
});

test("no way ends without help: every end is a device that runs again, or the way to Kuhler Buhler with the answers in a new issue", () => {
  const ends = nodes.filter(([, n]) => !n.choices && !n.next && !n.read).map(([id]) => id).sort();
  assert.deepEqual(ends, ["app:fixed", "ask", "cardfixed", "updated", "works"]);
  assert.match(JSON.stringify(FLOW.ask.say), /issueNew.*instagram/);
  assert.doesNotMatch(text(FLOW.ask), /Foto vom Display/, "the dark case ends here too, its display shows nothing");
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
  assert.doesNotMatch(everything(), /[–—]/);
});

/** The ids of a walk that always takes the answer leading to the next id given, from `from`, following what comes by itself. */
const walk = (from, ...picks) => {
  const seen = [from];
  let id = from;
  for (let guard = 0; guard < 20; guard++) {
    const n = FLOW[id];
    if (n.next) id = n.next;
    else if (picks.length && n.choices?.some(c => c.to === picks[0])) id = picks.shift();
    else break;
    seen.push(id);
  }
  return seen;
};

test("the update prompt on a blue asks whether Hacktribe was ever on it; yes leads to a Sampler file in the Sampler's folder", () => {
  assert.deepEqual(FLOW["color:update"].choices.map(c => c.to), ["download:update:red", "hacktribe:blue"]);
  assert.deepEqual(FLOW["hacktribe:blue"].choices.map(c => c.to), ["download:update:blue", "sampler:blue", "download:update:blue"]);
  const way = walk("prompt", "hacktribe:blue", "sampler:blue", "card:red");
  assert.deepEqual(way.slice(-3), ["sampler:blue", "download:update:red", "card:red"]);
  assert.equal(FLOW["card:red"].say.at(-1).path, "KORG/electribe sampler/System/SYSTEM.VSB");
  assert.match(text(FLOW["sampler:blue"]), /Sampler/);
});

test("Invalid File: at the start through the colour and the Hacktribe question; in the menu the patcher's colour or Korg's file", () => {
  assert.deepEqual(FLOW.invalid.choices.map(c => c.to), ["invalid:prompt", "invalid:menu"]);
  assert.equal(FLOW["invalid:prompt"].next, "color:update");
  assert.deepEqual(FLOW["invalid:menu"].choices.map(c => c.to), ["invalid:patcher", "invalid:korg"]);
  assert.match(text(FLOW["invalid:patcher"]), /Farbe deiner Electribe/);
  assert.deepEqual(FLOW["invalid:korg"].choices.map(c => c.to), ["download:starts:red", "download:starts:blue", "invalid:head"]);
  assert.equal(FLOW["invalid:head"].next, "ask", "the head bytes are not done for the user, the way leads to Kuhler Buhler");
  for (const id of ["update:prompt", "update:menu", "nofile:update"]) assert.ok(FLOW[id].choices.some(c => c.to.startsWith("invalid:")), `${id} knows Invalid File`);
});

test("No File: the name SYSTEM.VSB, the folder System, the folder of the running firmware, no renamed folder, the Electribe chosen in the patcher", () => {
  const menu = text(FLOW["nofile:menu"]);
  assert.match(menu, /SYSTEM \(1\)\.VSB/);
  assert.match(menu, /Unterordner System/);
  assert.match(menu, /Benenn keinen Ordner um/);
  assert.match(menu, /blechtribe/);
  assert.match(menu, /richtige Electribe gewählt/);
  assert.equal(FLOW["nofile:menu"].next, "nofile:which");
  assert.deepEqual(FLOW["nofile:which"].choices.map(c => c.value), FOLDERS.map(f => f.path));
  assert.equal(FLOW["nofile:which"].known, "folder", "the folder the patcher named, or the running BLECHTRIBE, is marked");
  assert.match(t("rescue.say.card"), /SYSTEM \(1\)\.VSB/, "every card step names the file name");
  assert.equal(FLOW["nofile:prompt"].next, "color:update");
});

test("the app does not find the Electribe: the MIDI report decides, without it Blechy asks", () => {
  const read = FLOW.notfound.read;
  assert.equal(read.from, "midi");
  assert.equal(read.otherwise, "notfound:mode");
  assert.match(text(FLOW["notfound:korgWindows"]), /Geräte-Manager/);
  assert.doesNotMatch(text(FLOW["notfound:korgOther"]), /Geräte-Manager|deinstall/, "on the Mac nothing is claimed");
  assert.match(text(FLOW["notfound:korgOther"]), /wissen wir noch nicht/);
  assert.equal(FLOW["notfound:korgOther"].next, "notfound:report");
  assert.match(text(FLOW["notfound:emu"]), /Echtes Gerät/);
  assert.match(text(FLOW["notfound:report"]), /MIDI-Bericht/);
});

test("old patterns after export: WRITE first, KORG/blechtribe, the old folder stays, the blue has no copy, the date is always 01.01.2014", () => {
  const all = text(FLOW.export);
  assert.match(all, /erst WRITE, dann EXPORT PATTERN/);
  assert.match(all, /KORG\/blechtribe\//);
  assert.match(all, /KORG\/electribe\b/);
  assert.match(all, /01\.01\.2014/);
});

test("the full check: the app's version decides whether flash.bin is the cause, the log goes to the team", () => {
  assert.deepEqual(FLOW.check.read, { from: "version", to: { fixed: "check:fixed", old: "check:old" }, otherwise: "check:unknown" });
  for (const id of ["check:old", "check:unknown"]) assert.ok(FLOW[id].say.some(l => l.path === "~/.gelumpe/flash/flash.bin"), id);
  assert.ok(FLOW["check:report"].say.some(l => l.path === "~/.gelumpe/emu.log"));
  assert.equal(checkVerdict("1.3.6"), "old");
  assert.equal(checkVerdict("1.2.9"), "old");
  assert.equal(checkVerdict("1.3.7"), "fixed");
  assert.equal(checkVerdict("1.3.10"), "fixed");
  assert.equal(checkVerdict("2.0.0"), "fixed");
  assert.equal(checkVerdict(undefined), null);
});

test("in-app links stay in the app, links of the page go to LINKS", () => {
  for (const key of ["settings", "patcher", "discord"]) assert.match(LINKS[key], /^#\w+$/);
});
