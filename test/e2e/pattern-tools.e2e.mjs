import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { Pattern, PatternFile, parseSinglePattern } from "../../src/pattern.mjs";
import { rollPart } from "../../src/dice.mjs";
import { parsePatternDump } from "../../src/protocol.mjs";
import { SimDevice } from "../../src/device.mjs";
import { makeFirmware } from "../helpers.mjs";
import { setBackup } from "../support/pattern-set.mjs";

let h;
let fake;
let backup;
before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: h.dir });
  backup = setBackup(12);
  h.file("set.e2sallpat", backup.file.toBytes());
  h.file("system.vsb", await makeFirmware());
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

async function open() {
  const page = await h.page();
  await page.goto(`${h.url}?labs`);
  await page.click("#cee-tab-ptools");
  await page.locator("#cee-ptools").waitFor();
  return page;
}

async function load(page) {
  await page.setInputFiles("#cee-pt-file", `${h.dir}/set.e2sallpat`);
  await page.locator("#cee-pt-loaded", { hasText: "12 Patterns" }).waitFor();
}

test("the page is in the navigation and says what it needs before a file is loaded", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Pattern-Werkzeuge");
  assert.equal(await page.locator("#cee-pt-loaded").textContent(), "Noch keine Datei geladen.");
  assert.equal(await page.locator("#cee-pt-t-results").textContent(), "Wähle A und B.");
  assert.equal(await page.locator("#cee-pt-d-text").textContent(), "Wähle ein Basis-Pattern.");
  assert.equal(await page.locator("#cee-pt-d-save").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("transitions: A and B from a backup, a preview with the part table, names and slots", async () => {
  const page = await open();
  await load(page);
  assert.equal(await page.locator("#cee-pt-a").inputValue(), "1");
  assert.equal(await page.locator("#cee-pt-b").inputValue(), "2");
  assert.match(await page.locator("#cee-pt-t-summary").textContent(), /^Übergang von Pattern 1 A side .* zu Pattern 2 B side .*, 2 Patterns\.$/);
  assert.equal(await page.locator(".cee-pt-card").count(), 2);
  assert.doesNotMatch(await page.locator("#cee-pt-t-results").textContent(), /null|undefined/);
  // the table: A, two transitions, B
  assert.equal(await page.locator(".cee-pt-grid tbody tr").count(), 4);
  assert.equal(await page.locator(".cee-pt-grid tbody tr").first().locator("th").textContent(), "A");
  // free slots above A and B, chain to is on, B's slot is filled in
  assert.equal(await page.locator("#cee-pt-t-slot-0").inputValue(), "4");
  assert.equal(await page.locator("#cee-pt-t-slot-1").inputValue(), "5");
  assert.equal(await page.locator("#cee-pt-slot-b").inputValue(), "2");
  assert.equal(await page.locator("#cee-pt-t-name-0").inputValue(), "PREB side0");

  await page.fill("#cee-pt-t-name-0", "Intro Build");
  await page.press("#cee-pt-t-name-0", "Tab");
  assert.equal(await page.locator("#cee-pt-t-name-0").inputValue(), "Intro Build");
  await page.fill("#cee-pt-count", "3");
  assert.equal(await page.locator(".cee-pt-card").count(), 3);
  assert.equal(await page.locator("#cee-pt-t-name-0").inputValue(), "PREB side0", "a new count starts the names over");
  assert.deepEqual(page.errors, []);
});

test("transitions: a single file, a name of your own, chain to and the same bytes the generator makes", async () => {
  const page = await open();
  await load(page);
  await page.fill("#cee-pt-t-name-1", "Drop In");
  await page.press("#cee-pt-t-name-1", "Tab");
  const bytes = await h.download(page, () => page.click("#cee-pt-t-save-1"));
  const got = parseSinglePattern(bytes);
  assert.equal(got.name, "Drop In");
  assert.equal(got.raw("pattern.chainTo"), 2, "the last transition points at B");
  const { makeTransitions } = await import("../../src/transition.mjs");
  const expected = makeTransitions(backup.a, backup.b, { count: 2, slots: [4, 5], slotB: 2, chain: true, names: ["", "Drop In"] }).items[1].pattern;
  assert.deepEqual(got.bytes, expected.bytes);
  assert.match(await page.locator("#cee-pt-line").textContent(), /^Gespeichert: T2_005_Drop-In\.e2spat/);
  assert.deepEqual(page.errors, []);
});

test("transitions: into a copy of the backup, the original and the other slots stay, an occupied slot asks first", async () => {
  const page = await open();
  await load(page);
  const bytes = await h.download(page, () => page.click("#cee-pt-t-backup"));
  const all = PatternFile.parse(bytes);
  assert.equal(all.count, 12);
  assert.equal(all.name(4), "PREB side0");
  assert.equal(all.name(5), "PREB side1");
  assert.equal(all.pattern(4).raw("pattern.chainTo"), 5);
  assert.equal(all.pattern(5).raw("pattern.chainTo"), 2);
  assert.deepEqual(all.pattern(1).bytes, backup.file.pattern(1).bytes);
  assert.deepEqual(all.pattern(6).bytes, backup.file.pattern(6).bytes);

  // slot 3 holds content: the copy replaces it only after a yes
  await page.fill("#cee-pt-t-slot-0", "3");
  await page.press("#cee-pt-t-slot-0", "Tab");
  assert.equal(await page.locator("#cee-pt-t-slot-0").inputValue(), "3");
  await page.click("#cee-pt-t-backup");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  assert.match(await dialog.textContent(), /3 Kept/);
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.equal(await page.locator("dialog.ui-dialog[open]").count(), 0);
  const kept = await h.download(page, async () => {
    await page.click("#cee-pt-t-backup");
    await page.locator("dialog.ui-dialog[open]").getByRole("button", { name: "In Kopie einsetzen" }).click();
  });
  const replaced = PatternFile.parse(kept);
  assert.equal(replaced.name(3), "PREB side0");
  assert.equal(replaced.name(2), "B side");

  // A or B as a target is refused with a plain sentence
  await page.fill("#cee-pt-t-slot-1", "2");
  await page.press("#cee-pt-t-slot-1", "Tab");
  assert.match(await page.locator("#cee-pt-t-slots").textContent(), /Platz von A oder B/);
  assert.equal(await page.locator("#cee-pt-t-backup").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("dice: the same seed gives the same pattern as the generator, in the step view and in the saved file", async () => {
  const page = await open();
  await load(page);
  await page.selectOption("#cee-pt-kind", "melody");
  await page.selectOption("#cee-pt-part", "2");
  await page.selectOption("#cee-pt-scale", "Dorian");
  await page.selectOption("#cee-pt-root", "2");
  await page.fill("#cee-pt-seed", "123456");
  await page.fill("#cee-pt-d-name", "Roll One");
  await page.press("#cee-pt-d-name", "Tab");
  await page.locator("#cee-pt-density").fill("50");
  const options = { part: 2, kind: "melody", density: 0.5, seed: 123456, root: 2, scale: "Dorian", octave: 3, span: 2, gate: 0.5, accent: 0.5, swing: null, bars: null, unmute: true, writeScale: false, name: "Roll One" };
  const expected = rollPart(backup.a, options);
  assert.equal(await page.locator("#cee-pt-d-text").textContent(), `${expected.text} Name: Roll One.`);
  // the first page of the step view shows the steps of 1 to 16
  const onFirstPage = expected.steps.filter(s => s.step < 16).length;
  assert.equal(await page.locator(".cee-step[aria-pressed=true]").count(), onFirstPage);
  const bytes = await h.download(page, () => page.click("#cee-pt-d-save"));
  assert.deepEqual(parseSinglePattern(bytes).bytes, expected.pattern.bytes);
  assert.equal(await page.locator("#cee-pt-d-text").textContent(), `${expected.text} Name: Roll One.`);

  // another seed, then back: the step view follows and the result is the same again
  await page.fill("#cee-pt-seed", "7");
  assert.notEqual(await page.locator("#cee-pt-d-text").textContent(), `${expected.text} Name: Roll One.`);
  await page.fill("#cee-pt-seed", "123456");
  const again = await h.download(page, () => page.click("#cee-pt-d-save"));
  assert.deepEqual(again, bytes);
  assert.deepEqual(page.errors, []);
});

test("dice: a step changed in the step view is in the saved file, new dice replace it, the backup copy gets the slot", async () => {
  const page = await open();
  await load(page);
  await page.fill("#cee-pt-seed", "99");
  await page.locator("#cee-pt-density").fill("0");
  assert.equal(await page.locator(".cee-step[aria-pressed=true]").count(), 0);
  await page.locator(".cee-step").nth(4).click();
  const saved = parseSinglePattern(await h.download(page, () => page.click("#cee-pt-d-save")));
  assert.equal(saved.raw("step.on", [0, 4]), 1);
  assert.equal(saved.raw("step.trigger", [0, 4]), 1);
  await page.click("#cee-pt-reroll");
  assert.equal(await page.locator(".cee-step[aria-pressed=true]").count(), 0, "new dice start from the base again");

  await page.locator("#cee-pt-density").fill("25");
  assert.equal(await page.locator("#cee-pt-d-slot").inputValue(), "4", "the first free slot is suggested");
  assert.equal(await page.locator("#cee-pt-d-hint").textContent(), "Der Platz ist frei.");
  await page.fill("#cee-pt-d-slot", "3");
  assert.equal(await page.locator("#cee-pt-d-hint").textContent(), "Der Platz ist belegt und wird in der Kopie ersetzt.");
  await page.fill("#cee-pt-d-slot", "6");
  const copy = PatternFile.parse(await h.download(page, () => page.click("#cee-pt-d-backup")));
  assert.match(copy.name(6), /^DICE \d+$/);
  assert.deepEqual(copy.pattern(3).bytes, backup.file.pattern(3).bytes);
  assert.equal(copy.pattern(6).raw("part.sample", [0]), 10);
  await page.fill("#cee-pt-d-slot", "13");
  assert.equal(await page.locator("#cee-pt-d-backup").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("dice: an empty part without sample says so, a bad file is refused with its message", async () => {
  const page = await open();
  await load(page);
  await page.selectOption("#cee-pt-part", "9");
  await page.fill("#cee-pt-seed", "5");
  assert.match(await page.locator("#cee-pt-d-warnings").textContent(), /kein Sample/);
  await page.setInputFiles("#cee-pt-file", { name: "bad.e2sallpat", mimeType: "application/octet-stream", buffer: Buffer.from("nope") });
  await page.locator("#cee-pt-error").waitFor();
  assert.match(await page.locator("#cee-pt-error").textContent(), /Pattern-Sicherung/);
  assert.equal(await page.locator("#cee-pt-loaded").textContent(), "set.e2sallpat, 12 Patterns, 9 davon frei", "the loaded file stays");
  assert.deepEqual(page.errors.filter(e => !/bad|resource/i.test(e)), []);
});

test("device: fetch A and B from the buffer, send a rolled pattern through the gate and a confirmation", async () => {
  const page = await h.page();
  await page.goto(`${h.url}?labs#emu=${fake.port}:${TOKEN}`);
  await page.setInputFiles("#cee-emu-vsb", `${h.dir}/system.vsb`);
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-e2-power");
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  await page.click("#cee-tab-ptools");
  await page.click("#cee-pt-connect-emu");
  await page.locator("#cee-pt-a-fetch:enabled").waitFor();
  assert.equal(await page.locator("#cee-pt-a-fetch").isDisabled(), false);
  assert.equal(await page.locator("#cee-pt-d-send").isDisabled(), true, "nothing rolled yet");

  await page.click("#cee-pt-dice-base-fetch");
  await page.locator("#cee-pt-line", { hasText: "Geholt" }).waitFor();
  assert.match(await page.locator("#cee-pt-dice-base option:checked").textContent(), /^Gerät, Kopie 1/);
  await page.selectOption("#cee-pt-kind", "drums");
  await page.fill("#cee-pt-seed", "2024");
  await page.locator("#cee-pt-density").fill("50");
  assert.equal(await page.locator("#cee-pt-d-send").isDisabled(), false);
  fake.seen.midi.length = 0;
  await page.click("#cee-pt-d-send");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  assert.match(await dialog.textContent(), /Write am Gerät/);
  await dialog.getByRole("button", { name: "Senden" }).click();
  await page.locator("#cee-pt-line", { hasText: "Gesendet und zurückgelesen" }).waitFor();
  const dump = fake.seen.midi.map(hex => Uint8Array.from(Buffer.from(hex, "hex"))).find(m => m[6] === 0x40);
  const sent = new Pattern(parsePatternDump(dump, 9));
  const expected = rollPart(new Pattern(new SimDevice({}).pattern), { kind: "drums", seed: 2024, density: 0.5, name: "DICE 2024" });
  assert.deepEqual(sent.bytes, expected.pattern.bytes);
  assert.equal(await page.locator("#cee-pt-undo").isDisabled(), false);
  assert.deepEqual(page.errors, []);
});

test("axe and phone width: no serious or critical violation, no sideways scroll", async t => {
  // @axe-core/playwright is a dev dependency; a checkout without it still runs the rest of this file.
  const axe = await import("./support/axe.mjs").catch(() => null);
  const page = await open();
  if (axe) assert.deepEqual(await axe.severeViolations(page), [], "empty");
  await load(page);
  if (axe) assert.deepEqual(await axe.severeViolations(page), [], "loaded");
  else t.diagnostic("axe not installed, accessibility scan skipped");
  await page.setViewportSize({ width: 375, height: 800 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, "no sideways scroll of the page at phone width");
  assert.deepEqual(page.errors, []);
});
