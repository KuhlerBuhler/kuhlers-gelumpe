import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FLOW, LINKS, FOLDERS, DEVICES, CASES, BUTTONS, checkVerdict, ENTRIES, TEST_GROUPS, TEST_AREAS, testGroup, testFailure, destOf, passSteps } from "../data/rescue.mjs";
import { readdirSync } from "node:fs";
import { t } from "../site/app/i18n.mjs";

const ROOT = new URL("../", import.meta.url);
const nodes = Object.entries(FLOW);
/** A line as the page reads it in German: a key, link parts, a path, or a text with links in it. */
const line = l => {
  if (typeof l === "string") return t(l);
  if (Array.isArray(l)) return l.map(part => t(part.text)).join("");
  if (l.path) return l.path;
  if (l.tree) return l.tree;
  if (l.quote || l.keys || l.shot) return "";
  return t(l.key, { ...l.vars, ...Object.fromEntries(Object.entries(l.links ?? {}).map(([name, part]) => [name, t(part.text)])) });
};
const text = node => [...node.say, ...(node.source ? [node.source] : [])].map(line).join("\n");
/** Every answer the flow can lead to from a choice, whatever `toIf` says. */
const targets = c => [c.to, ...Object.values(c.toIf ?? {}).flatMap(map => Object.values(map))];
/** Everything the page can show, in German. */
const everything = () => [
  ...nodes.flatMap(([, n]) => [text(n), ...(n.choices ?? []).flatMap(c => [t(c.label), c.hint ? t(c.hint) : ""])]),
  ...Object.values(DEVICES).flatMap(d => [t(d.title), t(d.hint), d.name]), ...FOLDERS.map(f => t(f.title)), ...Object.values(BUTTONS).map(b => t(b)),
].join("\n");

test("every text of the page is a key of the German table", () => {
  const keys = [];
  for (const [, n] of nodes) {
    for (const l of [...n.say, ...(n.source ? [n.source] : [])]) {
      if (typeof l === "string") keys.push(l);
      else if (Array.isArray(l)) keys.push(...l.map(part => part.text));
      else if (!l.path && !l.tree && !l.quote && !l.keys && !l.shot) keys.push(l.key, ...Object.values(l.links ?? {}).map(part => part.text));
    }
    for (const c of n.choices ?? []) keys.push(c.label, ...(c.hint ? [c.hint] : []));
  }
  keys.push(...Object.values(DEVICES).flatMap(d => [d.title, d.hint]), ...FOLDERS.map(f => f.title), ...Object.values(BUTTONS));
  assert.deepEqual(keys.filter(k => t(k) === k), []);
});

test("every answer and every follow-up leads to a node, and every node is reached", () => {
  const reached = new Set(["start", ...ENTRIES]);
  for (const [id, n] of nodes) {
    for (const c of n.choices ?? []) for (const to of targets(c)) { assert.ok(FLOW[to], `${id} leads to missing ${to}`); reached.add(to); }
    if (n.next) { assert.ok(FLOW[n.next], `${id} follows on to missing ${n.next}`); reached.add(n.next); }
    if (n.done) { assert.ok(FLOW[n.done], `${id} goes on to missing ${n.done}`); reached.add(n.done); }
    for (const to of n.read ? [...Object.values(n.read.to), n.read.otherwise] : []) { assert.ok(FLOW[to], `${id} reads on to missing ${to}`); reached.add(to); }
    assert.equal([n.next, n.choices, n.read].filter(Boolean).length <= 1, true, `${id} both waits and follows on`);
    if (n.known) assert.ok(n.choices?.some(c => c.value), `${id} knows something but no answer has a value`);
  }
  assert.deepEqual(nodes.map(([id]) => id).filter(id => !reached.has(id)), []);
  assert.deepEqual(FLOW.start.choices.map(c => c.id), CASES.map(c => c.id));
});

test("only answers: no evidence markers on the page, and links point at LINKS", () => {
  for (const [id, n] of nodes) assert.ok(!("status" in n) && !("note" in n), `${id} still carries a marker`);
  assert.doesNotMatch(everything(), /gemessen|offline gelesen|hergeleitet|offline \(|im Emulator geprüft/);
  const parts = JSON.stringify(FLOW).match(/"link":"(\w+)"/g) ?? [];
  for (const p of parts) assert.ok(LINKS[p.slice(8, -1)] || p === '"link":"issueNew"', p);
});

test("no way ends without help: every end is a device that runs again, or the way to Kuhler Buhler with the answers in a new issue", () => {
  const ends = nodes.filter(([, n]) => !n.choices && !n.next && !n.read && !n.done).map(([id]) => id).sort();
  assert.deepEqual(ends, ["app:fixed", "ask", "cardfixed", "ok", "updated", "works"]);
  assert.match(JSON.stringify(FLOW.ask.say), /issueNew.*instagram/);
  assert.doesNotMatch(text(FLOW.ask), /Foto vom Display/, "the dark case ends here too, its display shows nothing");
  for (const id of ["dark", "zero:cable"]) assert.equal(FLOW[id].next, "ask", id);
  assert.ok(FLOW.stuck.choices.some(c => c.to === "ask"), "stuck has a way to the contact");
});

test("no way tells the person to leave it alone and then hands over an English guide", () => {
  assert.doesNotMatch(everything(), /Probier bitte nichts auf eigene Faust|nichts auf eigene Faust/);
  assert.deepEqual(FLOW.dark.source.map(p => p.link), ["debrick"]);
  assert.match(text(FLOW.dark), /auf eigene Gefahr/);
  assert.match(text(FLOW.dark), /Foto vom Display/);
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

test("a path on the card is shown as folders, and says the folder belongs to the firmware that runs now", () => {
  for (const id of ["folder:korg:red", "folder:korg:blue", "folder:hacktribe", "folder:blech"]) {
    assert.ok(FLOW[id].say.some(l => l.tree), `${id} shows a tree`);
    assert.match(text(FLOW[id]), /nach der Firmware, die jetzt auf der Electribe läuft, nicht nach der, die du haben willst/, id);
    assert.equal(FLOW[id].choices[0].to, `sd:${id}`, `${id}: the look at the card comes first`);
    assert.equal(FLOW[id].choices[1].label, "rescue.answer.onCard");
  }
  assert.deepEqual(FLOW["folder:all:red"].say.filter(l => l.tree).map(l => l.tree), [DEVICES.red.path, FOLDERS[2].path, FOLDERS[3].path]);
  assert.deepEqual(FLOW["folder:all:blue"].say.filter(l => l.tree).map(l => l.tree), [DEVICES.blue.path, FOLDERS[2].path, FOLDERS[3].path]);
  assert.match(text(FLOW["card:red"]), /Beim Einschalten sucht sie immer in diesem Ordner/);
});

test("Korg's file: the exact page of the 2.02 update, named by its ZIP, and only after it is clear which one is needed", () => {
  assert.match(LINKS.korgRed, /\/software\/0\/368\/2579\/$/);
  assert.match(LINKS.korgBlue, /\/software\/0\/367\/2578\/$/);
  for (const key of ["red", "blue"]) {
    assert.match(text(FLOW[`download:${key}:go`]), new RegExp(DEVICES[key].zip.replace(/\./g, "\\.")));
    assert.equal(FLOW[`download:${key}:go`].choices[0].to, "firmware:last", "after the download the folder of what runs now");
  }
  // the way back asks what runs before it sends anyone to a download
  assert.equal(FLOW.back.next, "back:firmware");
  assert.ok(FLOW["back:firmware"].choices.every(c => !targets(c).some(to => to.startsWith("download:update"))));
});

test("every step that asks for a fact lets each answer carry it, so a known fact is never asked again", () => {
  for (const [id, n] of nodes.filter(([, n]) => n.ask)) {
    const carrying = (n.choices ?? []).filter(c => c.set && n.ask in c.set);
    assert.ok(carrying.length >= 2, `${id} asks ${n.ask} but its answers do not set it`);
  }
  // the colour and what runs are each asked in one kind of step only
  assert.deepEqual(nodes.filter(([, n]) => n.ask === "color").map(([id]) => id).sort(), ["color", "color:update", "recheck:prompt"]);
  assert.deepEqual(nodes.filter(([, n]) => n.ask === "firmware").map(([id]) => id).sort(), ["back:firmware", "firmware:file", "nofile:which", "recheck", "samples:firmware"]);
  // every one of them has "I don't know" and a safe way on
  for (const id of ["firmware:file", "back:firmware", "nofile:which", "samples:firmware", "recheck"]) {
    assert.ok(FLOW[id].choices.some(c => c.value === "unknown" && c.label === "rescue.answer.dontKnow"), `${id} has the answer "not known"`);
  }
  assert.ok(FLOW.color.choices.some(c => c.label === "rescue.answer.dontKnow" && c.to === "color:help"));
});

/** Walks every way through the talk with the facts it carries, each state once; calls `visit(id, facts, trail)` at each step shown. */
function explore(visit) {
  const seen = new Set();
  const stack = [{ id: "start", facts: {}, trail: [] }];
  while (stack.length) {
    const s = stack.pop();
    const passed = passSteps(s.id, s.facts);
    const key = `${passed.id}|${JSON.stringify(passed.facts)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const trail = [...s.trail, passed.id];
    visit(passed.id, passed.facts, trail);
    const n = FLOW[passed.id];
    if (n.next) stack.push({ id: n.next, facts: passed.facts, trail });
    if (n.done) stack.push({ id: n.done, facts: passed.facts, trail });
    if (n.read) for (const to of [...Object.values(n.read.to), n.read.otherwise]) stack.push({ id: to, facts: passed.facts, trail });
    for (const c of n.choices ?? []) stack.push({ id: destOf(c, passed.facts), facts: { ...passed.facts, ...c.set }, trail });
  }
  return seen.size;
}

test("no step that asks is shown when its fact is known", () => {
  const shown = explore((id, facts) => {
    const ask = FLOW[id].ask;
    if (ask) assert.equal(facts[ask], undefined, `${id} is shown although ${ask} is known: ${JSON.stringify(facts)}`);
  });
  assert.ok(shown > 100, `only ${shown} states explored`);
});

test("every case about the device asks the colour once, first, and never again on any way", () => {
  for (const c of FLOW.start.choices.filter(c => c.id !== "app")) {
    assert.equal(c.to, "color", c.id);
    assert.equal(c.set.case, c.id);
  }
  assert.equal(FLOW.start.choices.find(c => c.id === "app").to, "app");
  let colourSteps = 0;
  explore((id, facts, trail) => {
    if (FLOW[id].ask === "color") { colourSteps++; assert.ok(!facts.color); }
    // a colour step shown twice on one trail would be a second question
    assert.ok(trail.filter(x => FLOW[x].ask === "color").length <= 1, trail.join(" > "));
  });
  assert.ok(colourSteps > 0);
  const red = passSteps("color", { case: "zero", color: "red" });
  assert.equal(red.id, "zero");
  assert.equal(passSteps("color", { case: "nofile", color: "blue" }).id, "nofile");
});

test("what runs is asked once on a way, and the file goes where the answer says", () => {
  explore((id, facts, trail) => {
    assert.ok(trail.filter(x => FLOW[x].ask === "firmware").length <= 1, trail.join(" > "));
  });
  const to = (firmware, color) => passSteps("firmware:file", { firmware, color }).id;
  assert.equal(to("korg", "red"), "folder:korg:red");
  assert.equal(to("korg", "blue"), "folder:korg:blue");
  assert.equal(to("hacktribe", "blue"), "folder:hacktribe");
  assert.equal(to("blech", "red"), "folder:blech");
  assert.equal(to("unknown", "red"), "folder:all:red");
  assert.equal(to("unknown", "blue"), "folder:all:blue");
});

test("EXIT helping is not the end: without the card, then the plugin and settings files, else the firmware back", () => {
  assert.equal(FLOW.fixed.next, "nocard");
  assert.deepEqual(FLOW.nocard.choices.map(c => c.to), ["cardfiles", "backup"]);
  assert.deepEqual(FLOW.cardfiles.say.filter(l => l.path).map(l => l.path), ["KORG/blechtribe/Plugin/e2sPlugin.all", "KORG/blechtribe/settings.a.bin", "KORG/blechtribe/settings.b.bin"]);
  assert.deepEqual(FLOW.cardfiles.choices.map(c => c.to), ["cardfixed", "backup"]);
});

test("nothing at all: the power, the emergency exit with EXIT, then the other ways, and no 'it runs' without a reason", () => {
  assert.match(text(FLOW.silent), /Netzteil/);
  assert.match(text(FLOW.silent), /EXIT gedrückt halten/);
  assert.deepEqual(FLOW.silent.choices.map(c => c.to), ["ok", "fixed", "zero", "prompt", "dark"]);
  assert.equal(FLOW.fixed.next, "nocard", "EXIT working leads on to the cause, it does not end");
  assert.notEqual(FLOW.ok.say[0], FLOW.works.say[0]);
  assert.doesNotMatch(text(FLOW.ok), /zurückgespielt/, "no file was chosen, so nothing was put back");
  assert.deepEqual(FLOW.reboot.choices.map(c => c.to), ["ok", "prompt", "zero:card"], "after Please Reboot no file was chosen either");
});

test("00 and the update prompt go through Korg's file of the device's colour", () => {
  for (const id of ["zero:card", "prompt"]) assert.equal(FLOW[id].next, "color:update");
  assert.deepEqual(FLOW.zero.choices.map(c => c.to), ["reboot", "zero:card"], "00 waits first, the card only when it stays");
  assert.equal(FLOW["card:red"].say.find(l => l.tree).tree, "KORG/electribe sampler/System/SYSTEM.VSB");
  assert.equal(FLOW["card:blue"].say.find(l => l.tree).tree, "KORG/electribe/System/SYSTEM.VSB");
  assert.match(text(FLOW["update:prompt"]), /ENTER/);
  assert.equal(passSteps("color:update", { color: "red" }).id, "download:update:red");
  assert.equal(passSteps("color:update", { color: "blue" }).id, "hacktribe:blue");
});

test("a way that did not work looks at the card once more, then asks what the display shows, then the contact", () => {
  const fails = id => FLOW[id].choices.find(c => c.label === "rescue.answer.fails");
  assert.equal(destOf(fails("update:menu"), {}), "recheck");
  assert.equal(destOf(fails("update:menu"), { again: "yes" }), "stuck");
  assert.equal(destOf(fails("update:prompt"), {}), "recheck:prompt");
  assert.equal(destOf(fails("update:prompt"), { again: "yes" }), "stuck");
  assert.equal(passSteps("recheck", { firmware: "hacktribe" }).id, "sd:folder:hacktribe", "the look at the card is offered again");
  assert.equal(passSteps("recheck:prompt", { color: "blue" }).id, "sd:card:blue");
  assert.deepEqual(FLOW.stuck.choices.map(c => c.to), ["zero:cable", "prompt", "nofile", "invalid", "dark", "ask"]);
  assert.ok(FLOW["update:prompt"].choices.some(c => c.label === "rescue.answer.noPrompt" && c.to === "noprompt"), "no update question has its own answer");
  assert.deepEqual(FLOW.noprompt.choices.map(c => c.to), ["firmware:last", "silent"]);
});

test("Blechy speaks plainly, nobody gets shouted at, and the hard cases name the official guide", () => {
  for (const [id, n] of nodes) {
    assert.doesNotMatch(text(n), /Bootloader|JTAG|OpenOCD|0x|Panel-Controller|Flash|Sampler-Code|zwei Bytes/, `${id} says it up front`);
    assert.notEqual(n.mood, "angry", id);
  }
  for (const id of ["dark", "zero:cable"]) assert.deepEqual(FLOW[id].source.map(p => p.link), ["debrick"], id);
});

test("the text has no em or en dash", () => {
  assert.doesNotMatch(everything(), /[–—]/);
});

test("the start says a computer with a card reader is needed, and patterns and samples are named before anything is written", () => {
  assert.match(text(FLOW.start), /Computer mit SD-Kartenleser/);
  for (const id of ["backup", "back"]) {
    assert.match(text(FLOW[id]), /Patterns/, id);
    assert.ok(FLOW[id].say.some(l => l.links?.patterns), `${id} offers the backup`);
  }
  assert.equal(LINKS.patterns, "#patterns");
});

test("the update prompt on a blue asks whether Hacktribe was ever on it; yes leads to a Sampler file in the Sampler's folder", () => {
  assert.deepEqual(FLOW["hacktribe:blue"].choices.map(c => c.to), ["download:update:blue", "sampler:blue", "download:update:blue"]);
  assert.equal(FLOW["sampler:blue"].next, "download:update:red");
  assert.equal(FLOW["card:red"].say.find(l => l.tree).tree, "KORG/electribe sampler/System/SYSTEM.VSB");
  assert.match(text(FLOW["sampler:blue"]), /Sampler/);
  assert.ok(FLOW["hacktribe:blue"].choices.some(c => c.label === "rescue.answer.dontKnow"));
});

test("Invalid File: at the start through the colour; in the menu the patcher's colour or Korg's file, which asks nothing twice", () => {
  assert.deepEqual(FLOW.invalid.choices.map(c => c.to), ["invalid:prompt", "invalid:menu"]);
  assert.match(text(FLOW.invalid), /neu auf die Karte zu kopieren/);
  assert.equal(FLOW["invalid:prompt"].next, "color:update");
  assert.deepEqual(FLOW["invalid:menu"].choices.map(c => c.to), ["invalid:patcher", "back:firmware"]);
  assert.match(text(FLOW["invalid:patcher"]), /Farbe, die du mir vorhin genannt hast/);
  for (const id of ["update:prompt", "update:menu", "nofile:update"]) assert.ok(FLOW[id].choices.some(c => c.to.startsWith("invalid:")), `${id} knows Invalid File`);
});

test("No File: the name SYSTEM.VSB, the folder of the running firmware, no renamed folder, the Electribe chosen in the patcher", () => {
  const menu = text(FLOW["nofile:menu"]);
  assert.match(menu, /SYSTEM \(1\)\.VSB/);
  assert.match(menu, /Benenn keinen Ordner um/);
  assert.match(menu, /blechtribe/);
  assert.match(menu, /richtige Electribe gewählt/);
  assert.equal(FLOW["nofile:menu"].next, "nofile:last");
  assert.equal(FLOW["nofile:which"].known, "firmware", "the folder the patcher named, or the running BLECHTRIBE, is marked");
  assert.match(t("rescue.say.card"), /SYSTEM \(1\)\.VSB/, "every card step names the file name");
  assert.equal(FLOW["nofile:prompt"].next, "color:update");
  const again = FLOW["nofile:update"].choices.find(c => c.label === "rescue.answer.againNoFile");
  assert.equal(destOf(again, {}), "recheck");
  assert.equal(destOf(again, { again: "yes" }), "ask", "the second No File goes to the contact");
  // after the card step the talk goes on in the No File way, not in the menu update of the other cases
  const pick = FLOW["sd:folder:hacktribe"].choices.find(c => c.pick);
  assert.equal(destOf(pick, { case: "nofile" }), "nofile:update");
  assert.equal(destOf(pick, { case: "starts" }), "update:menu");
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
  for (const key of ["settings", "patcher", "discord", "patterns"]) assert.match(LINKS[key], /^#\w+$/);
});

test("the patcher's test: every red check has a group, every case module an area, the advice is a normal firmware", () => {
  assert.deepEqual(FLOW.test.choices.map(c => c.to), TEST_GROUPS.map(g => `test:${g}`));
  assert.equal(testGroup("header"), "start");
  assert.equal(testGroup("start_phase"), "start");
  assert.equal(testGroup("boot:normal"), "boot");
  assert.equal(testGroup("start_mode:00000001"), "boot");
  assert.equal(testGroup("kill_switch"), "boot");
  assert.equal(testGroup("menu:open"), "feature");
  assert.equal(testGroup("verified"), null);
  assert.equal(testFailure({ ok: true, checks: [] }), null);
  assert.deepEqual(testFailure({ ok: false, checks: [{ id: "quick", ok: true }, { id: "pswitch:next", ok: false }] }), { group: "feature", id: "pswitch:next", area: "rescue.area.pattern" });
  assert.deepEqual(testFailure({ ok: false, checks: [{ id: "update_offer", ok: false }] }), { group: "boot", id: "update_offer", area: null });
  const emu = new URL("tools/emu/", ROOT);
  const prefixes = new Set(readdirSync(emu).filter(f => f.endsWith("_cases.py"))
    .flatMap(f => [...readFileSync(new URL(f, emu), "utf8").matchAll(/"id":\s*f?"([\w-]+):/g)].map(m => m[1])));
  assert.ok(prefixes.size > 10, `only ${prefixes.size} case modules found`);
  assert.deepEqual([...prefixes].filter(p => !TEST_AREAS[p]), []);
  for (const g of ["patch", "start", "boot", "feature"]) {
    assert.equal(FLOW[`test:${g}`].next, `normal:${g}`);
    const links = JSON.stringify(FLOW[`normal:${g}`].say);
    for (const l of ["hacktribe", "korgRed", "korgBlue"]) assert.match(links, new RegExp(`"link":"${l}"`), `normal:${g} links ${l}`);
  }
  assert.equal(FLOW.app.choices.find(c => c.label === "rescue.answer.checkFails").to, "test");
});

test("a reported error opens with the app's own words and goes on to the app's questions", () => {
  assert.ok(FLOW.error.say.some(l => l.quote));
  assert.equal(FLOW.error.next, "app");
});

test("samples: a case of the first question, also behind 'it starts but something is off', asked for Hacktribe, then the way to BLECHTRIBE without Hacktribe", () => {
  assert.ok(CASES.some(c => c.id === "samples"));
  assert.ok(FLOW.starts.choices.some(c => c.to === "samples"), "reachable from the case 'it starts but something is off'");
  assert.deepEqual(FLOW.samples.choices.map(c => c.to), ["samples:flash", "samples:other", "samples:other"]);
  assert.equal(FLOW["samples:other"].next, "starts", "without Hacktribe the firmware itself is looked at first");
  assert.equal(FLOW["samples:flash"].next, "samples:firmware");
  assert.match(text(FLOW["samples:flash"]), /Speicher im Gerät.*nicht überschrieben/s, "the sounds stay in the device and come back");
  assert.doesNotMatch(text(FLOW.samples) + text(FLOW["samples:flash"]), /Ohne Kopie|verloren/, "no talk of lost samples");
  assert.match(text(FLOW["samples:way"]), /Original.*BLECH/s, "the way back goes through Korg's original, not the Hacktribe file");
  const doc = readFileSync(new URL("docs/rettung.md", ROOT), "utf8");
  assert.match(doc, /Hacktribe aus Versehen/);
  assert.equal(FLOW["samples:head"].next, "back:head");
  // the file is made, the folder follows from the one answer, and the end says BLECHTRIBE runs, not that Korg's original does
  assert.equal(FLOW["samples:way"].choices[0].set.goal, "blech");
  assert.equal(destOf(FLOW["update:menu"].choices[0], { goal: "blech" }), "updated");
  assert.equal(destOf(FLOW["update:menu"].choices[0], {}), "works");
});

test("back to Korg's original: what runs decides the file, a blue with Hacktribe gets the file with the Sampler head, nothing is asked twice", () => {
  assert.ok(CASES.some(c => c.id === "back"));
  assert.equal(FLOW.back.next, "back:firmware");
  const way = (color, firmware, ht) => passSteps("back:firmware", { color, firmware, ...(ht ? { ht } : {}) }).id;
  assert.equal(way("red", "blech"), "download:red:go");
  assert.equal(way("red", "hacktribe"), "download:red:go");
  assert.equal(way("blue", "hacktribe"), "back:head");
  assert.equal(way("blue", "blech"), "back:blueHt");
  assert.equal(way("blue", "blech", "yes"), "back:head");
  assert.equal(way("blue", "blech", "no"), "download:blue:go");
  assert.equal(way("blue", "unknown"), "back:blueHt");
  assert.equal(way("red", "korg"), "back:already");
  assert.equal(FLOW["back:head"].file, "korgBlueHead", "the head bytes are done for the user: the app makes the file from Korg's own");
  assert.equal(FLOW["back:head"].done, "firmware:last", "after the file only the folder, what runs is already known");
  assert.equal(FLOW["back:head"].choices, undefined, "no 'saved' answer without a file");
  assert.match(text(FLOW.back), /Original-Firmware/);
  assert.match(text(FLOW.back), /KORG\/blechtribe\//);
  assert.doesNotMatch(text(FLOW["back:head"]), /zwei Bytes|Sampler-Code|Kopf/);
});

test("the file put on last is asked before the folder, only when what runs is not known, and \"not known\" leads to all folders", () => {
  for (const [id, to] of [["firmware:last", "firmware:file"], ["nofile:last", "nofile:which"]]) {
    const n = FLOW[id];
    assert.equal(n.ask, "last", id);
    assert.equal(n.passTo, to, id);
    assert.deepEqual(n.choices.map(c => c.value), ["korg", "hacktribe", "blech", "unknown"], id);
    assert.ok(n.choices.slice(0, 3).every(c => c.to === to), `${id} goes on to the folder question`);
    assert.equal(n.choices[3].label, "rescue.answer.dontKnow");
    // what runs known: the question is skipped
    assert.equal(passSteps(id, { firmware: "blech", color: "red" }).id, to === "firmware:file" ? "folder:blech" : passSteps(to, { firmware: "blech", color: "red" }).id);
  }
  // "not known" sets what runs to unknown, so the folder question is skipped and all folders follow
  const dontKnow = FLOW["firmware:last"].choices[3];
  const facts = { color: "blue", ...dontKnow.set };
  assert.equal(passSteps(destOf(dontKnow, facts), facts).id, "folder:all:blue");
  // an answer is only a hint: the folder question is still asked
  assert.equal(passSteps("firmware:last", { color: "red", last: "hacktribe" }).id, "firmware:file");
});

test("the steps with MENU show the drawn keys, and Korg's download steps show the shot of the button", () => {
  for (const id of ["update:menu", "nofile:update"]) assert.ok(FLOW[id].say.some(l => l.keys === "menu"), id);
  assert.ok(FLOW["update:prompt"].say.some(l => l.keys === "enter"));
  for (const key of Object.keys(DEVICES)) {
    assert.match(DEVICES[key].shot, /^img\/rescue\/korg-download-(red|blue)\.webp$/);
    assert.ok(readdirSync(new URL("site/img/rescue/", ROOT)).includes(DEVICES[key].shot.split("/").pop()), key);
    for (const id of [`download:update:${key}`, `download:${key}:go`]) assert.ok(FLOW[id].say.some(l => l.shot === DEVICES[key].shot), id);
  }
  assert.ok(FLOW["back:head"].say.some(l => l.shot === DEVICES.blue.shot));
});

/**
 * Which firmware takes which head on SOFTWARE UPDATE (docs/messungen/2026-11-08-rettung-alle-ordner.md, emulator): on the
 * red every firmware takes the Sampler head; on the blue Korg's own and BLECHTRIBE without Hacktribe take only the blue
 * head, Hacktribe and BLECHTRIBE with Hacktribe only the Sampler head. The patcher's BLECH from Korg's original carries
 * the head of that original (headFor in src/patcher.mjs): Sampler on the red, blue on the blue.
 */
const TAKES = { red: { korg: "sampler", hacktribe: "sampler", blech: "sampler", blechHt: "sampler" }, blue: { korg: "blue", hacktribe: "sampler", blech: "blue", blechHt: "sampler" } };

test("samples: the patcher's way is offered only where what runs takes its file, every other way goes over Korg's file with the Sampler head", () => {
  // [colour, what runs as answered, Hacktribe in BLECHTRIBE as answered, what really runs (null: not known), where it ends]
  const cases = [
    ["red", "korg", null, "korg", "samples:way"],
    ["red", "hacktribe", null, "hacktribe", "samples:way"],
    ["red", "blech", null, "blechHt", "samples:way"],
    ["red", "blech", null, "blech", "samples:way"],
    ["red", "unknown", null, null, "samples:way"],
    ["blue", "korg", null, "korg", "samples:way"],
    ["blue", "hacktribe", null, "hacktribe", "samples:head"],
    ["blue", "blech", "yes", "blechHt", "samples:head"],
    ["blue", "blech", "no", "blech", "samples:way"],
    ["blue", "blech", "dontKnow", null, "samples:head"],
    ["blue", "unknown", null, null, "samples:head"],
  ];
  for (const [color, firmware, ht, runs, end] of cases) {
    let at = passSteps("samples:firmware", { color, firmware });
    if (color === "blue" && firmware === "blech") {
      assert.equal(at.id, "samples:blueHt", "a BLECHTRIBE on the blue: the app cannot tell whether Hacktribe is in it, so it asks");
      const c = FLOW["samples:blueHt"].choices.find(c => ({ yes: "rescue.answer.blueHt", no: "rescue.answer.blueNoHt", dontKnow: "rescue.answer.dontKnow" })[ht] === c.label);
      at = passSteps(destOf(c, at.facts), { ...at.facts, ...c.set });
    }
    assert.equal(at.id, end, `${color}, ${firmware}${ht ? `, ${ht}` : ""}`);
    // the patcher's file has the head of Korg's original of that colour; it may only be offered where it is taken
    if (end === "samples:way" && runs) assert.equal(TAKES[color][runs], color === "red" ? "sampler" : "blue", `${color} ${runs} would say Invalid File`);
    // Korg's blue with the Sampler head is taken by every firmware with Hacktribe on the blue
    if (end === "samples:head" && runs) assert.equal(TAKES.blue[runs], "sampler", `${runs} would say Invalid File`);
  }
  // the way over Korg's file says that it is about Hacktribe in BLECHTRIBE too, and only the blue gets it
  assert.match(text(FLOW["samples:head"]), /allein oder in BLECHTRIBE/);
  assert.match(text(FLOW["samples:blueHt"]), /auch Hacktribe/);
});

test("the folder note names only the folder that is shown", () => {
  const shown = id => text(FLOW[id]);
  assert.match(shown("folder:hacktribe"), /„hacktribe“ im Pfad heißt nur: Hacktribe läuft gerade/);
  assert.doesNotMatch(shown("folder:hacktribe"), /„blechtribe“/);
  assert.match(shown("folder:blech"), /„blechtribe“ im Pfad heißt: BLECHTRIBE läuft gerade/);
  for (const id of ["folder:blech", "folder:korg:red", "folder:korg:blue", "folder:all:red", "folder:all:blue"]) assert.doesNotMatch(shown(id), /„hacktribe“ im Pfad/, id);
  // after the patcher's file, what runs decides the folder: BLECHTRIBE reads KORG/blechtribe/System/, Hacktribe KORG/hacktribe/System/
  const ready = FLOW["samples:way"].choices[0];
  for (const [firmware, folder] of [["blech", FOLDERS[3]], ["hacktribe", FOLDERS[2]]]) {
    const facts = { color: "red", firmware, ...ready.set };
    const at = passSteps(destOf(ready, facts), facts).id;
    assert.equal(at, firmware === "blech" ? "folder:blech" : "folder:hacktribe");
    assert.equal(FLOW[at].say.find(l => l.tree).tree, folder.path);
  }
});

test("the answer that opens the look at the card is said the way a person says it", () => {
  assert.equal(t("rescue.answer.showCard"), "Schau dir meine SD-Karte an");
  assert.doesNotMatch(t("rescue.answer.showCard"), /deine/);
});

test("the drawn keys of the MENU step sit where panel.mjs puts them, and no two marks touch", async () => {
  const { keyRect } = await import("../site/app/e2-art.mjs");
  const panel = readFileSync(new URL("site/app/panel.mjs", ROOT), "utf8");
  // the drawing maps the panel's front (screen at 135, 175) onto 200 units: x' = 9.5 + (x - 135) * 200 / 1021
  const scale = 200 / 1021;
  const ids = ["editLeft", "editRight", "menu", "exit", "shift", "write"];
  for (const id of ids) {
    const m = panel.match(new RegExp(`button\\(B\\.${id}\\), (\\d+), (\\d+), (\\d+), (\\d+)\\)`));
    assert.ok(m, `${id} in panel.mjs`);
    const [x, y, w, h] = m.slice(1).map(Number);
    const want = [9.5 + (x - 135) * scale, 21 + (y - 175) * scale, w * scale, h * scale];
    keyRect(id).forEach((v, i) => assert.ok(Math.abs(v - want[i]) < 0.1, `${id}[${i}] ${v} vs ${want[i].toFixed(2)}`));
  }
  // the marks stay inside their key, so the gap between two keys keeps them apart
  const overlap = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
  for (const a of ids) for (const b of ids) if (a !== b) assert.ok(!overlap(keyRect(a), keyRect(b)), `${a} and ${b} overlap`);
});
