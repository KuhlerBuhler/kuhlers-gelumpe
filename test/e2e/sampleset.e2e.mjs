import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp } from "./harness.mjs";
import { wav, file } from "../support/sample-file.mjs";
import { parseSampleFile, entryFromWav } from "../../src/sample-file.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

async function open(slots = { 500: "Kick", 501: "Snare", 502: "Hat" }) {
  const page = await h.page();
  await page.goto(`${h.url}#sampleset`);
  await page.setInputFiles("#cee-sf-file", h.file("e2sSample.all", file(slots)));
  await page.locator(".cee-sf-row").first().waitFor();
  return page;
}
const rows = page => page.locator(".cee-sf-row .cee-sf-name").allTextContents();
const saved = (page, click) => h.download(page, click);

test("the tab is in the sidebar, says to restart the device, and lists the samples of an opened file", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Samples");
  assert.match(await page.locator("#cee-sampleset").textContent(), /nur beim Start/);
  assert.deepEqual(await rows(page), ["Kick", "Snare", "Hat"]);
  assert.deepEqual(await page.locator(".cee-sf-nr").allTextContents(), ["501", "502", "503"]);
  assert.match(await page.locator("#cee-sf-summary").textContent(), /^3 Samples/);
  assert.match(await page.locator(".cee-sf-row").first().textContent(), /48 kHz, 16 Bit, Mono/);
  assert.equal(await page.locator("#cee-sf-save").isDisabled(), true, "nothing to save yet");
  assert.deepEqual(page.errors, []);
});

test("both files come in through the design's upload fields, and the intro reads as one paragraph", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#sampleset`);
  assert.equal(await page.locator("#cee-sampleset .ui-dropzone #cee-sf-file").count(), 1);
  assert.equal(await page.locator("#cee-sf-wav").isDisabled(), true, "WAVs only once a file is open");
  assert.equal(await page.locator("#cee-sf-wav").evaluate(i => i.closest(".cee-dropzone-wrap").hidden), true);
  assert.equal(await page.locator("#cee-sf-list").isHidden(), true, "no empty list frame before a file is open");
  assert.equal(await page.locator(".cee-sf-intro").evaluate(p => getComputedStyle(p).display), "block");
  assert.equal(await page.locator(".cee-sf-intro code").evaluate(c => getComputedStyle(c).display), "inline");
  await page.setInputFiles("#cee-sf-file", h.file("e2sSample.all", file({ 500: "Kick" })));
  await page.locator(".cee-sf-row").first().waitFor();
  assert.equal(await page.locator("#cee-sampleset .ui-dropzone #cee-sf-wav").isEnabled(), true);
  assert.equal(await page.locator(".cee-sf-row .ui-row-title").textContent(), "Kick");
});

test("a file that is no e2sSample.all is refused with a toast and the list stays empty", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#sampleset`);
  await page.setInputFiles("#cee-sf-file", h.file("bad.all", new Uint8Array(5000)));
  await page.locator("#app-toasts .cee-toast[data-kind=error]", { hasText: "e2s sample all" }).waitFor();
  assert.equal(await page.locator(".cee-sf-row").count(), 0);
  assert.equal(await page.locator("#cee-sf-wav").isDisabled(), true);
});

test("removing marks the row, can be taken back, and the saved file has no gap", async () => {
  const page = await open({ 500: "A", 501: "B", 502: "C", 503: "D" });
  await page.click("[data-slot='502']");
  assert.equal(await page.locator(".cee-sf-row[data-state=removed]").count(), 1);
  await page.click("[data-slot='502']");
  assert.equal(await page.locator(".cee-sf-row[data-state=removed]").count(), 0, "taken back");
  await page.click("[data-slot='502']");
  const bytes = await saved(page, () => page.click("#cee-sf-save"));
  const next = parseSampleFile(bytes);
  assert.deepEqual(next.samples.map(s => s.name), ["A", "C", "D"]);
  assert.ok(next.samples.every(s => s.problem === null));
  assert.equal(next.samples.at(-1).offset + next.samples.at(-1).length, bytes.length, "the file ends where the last sample does");
  await page.locator("#app-toasts .cee-toast", { hasText: "nur beim Start" }).waitFor();
  assert.equal(await page.locator("#cee-sf-save").isDisabled(), true, "the saved file is the new base");
  assert.deepEqual(await rows(page), ["A", "C", "D"]);
});

test("adding a WAV takes the first free user slot and the file name; save writes it behind the old samples", async () => {
  const page = await open();
  const old = readFileSync(h.file("e2sSample.all", file({ 500: "Kick", 501: "Snare", 502: "Hat" })));
  await page.setInputFiles("#cee-sf-wav", h.file("Dose.wav", wav({ frames: 120 })));
  await page.locator(".cee-sf-row[data-state=new]").waitFor();
  assert.deepEqual(await rows(page), ["Kick", "Snare", "Hat", "Dose"]);
  assert.equal(await page.locator(".cee-sf-row[data-state=new] .cee-sf-nr").textContent(), "504");
  const bytes = await saved(page, () => page.click("#cee-sf-save"));
  assert.deepEqual(Array.from(bytes.subarray(0, old.length)).slice(4096), Array.from(old.subarray(4096)), "what was there is untouched");
  assert.equal(parseSampleFile(bytes).samples.at(-1).name, "Dose");
});

test("a WAV the Electribe cannot take is refused with the reason", async () => {
  const page = await open();
  await page.setInputFiles("#cee-sf-wav", h.file("eight.wav", wav({ bits: 8 })));
  await page.locator("#app-toasts .cee-toast[data-kind=error]", { hasText: "8 Bit geht nicht" }).waitFor();
  assert.equal(await page.locator(".cee-sf-row[data-state=new]").count(), 0);
  await page.setInputFiles("#cee-sf-wav", h.file("float.wav", wav({ tagNo: 3, bits: 32 })));
  await page.locator("#app-toasts .cee-toast[data-kind=error]", { hasText: "kein PCM" }).waitFor();
});

test("Änderungen verwerfen puts the list back", async () => {
  const page = await open();
  await page.click("[data-slot='501']");
  await page.setInputFiles("#cee-sf-wav", h.file("x.wav", wav()));
  await page.locator(".cee-sf-row[data-state=new]").waitFor();
  await page.click("#cee-sf-reset");
  assert.deepEqual(await rows(page), ["Kick", "Snare", "Hat"]);
  assert.equal(await page.locator("#cee-sf-save").isDisabled(), true);
});

test("removing a new row drops it; remove one and add one in a single save", async () => {
  const page = await open();
  await page.setInputFiles("#cee-sf-wav", h.file("N.wav", wav()));
  await page.locator(".cee-sf-row[data-state=new]").waitFor();
  await page.click(".cee-sf-row[data-state=new] button");
  assert.equal(await page.locator(".cee-sf-row[data-state=new]").count(), 0);
  await page.click("[data-slot='501']");
  await page.setInputFiles("#cee-sf-wav", h.file("N2.wav", wav()));
  await page.locator(".cee-sf-row[data-state=new]").waitFor();
  const next = parseSampleFile(await saved(page, () => page.click("#cee-sf-save")));
  assert.deepEqual(next.samples.map(s => [s.slot, s.name]), [[500, "N2"], [501, "Snare"], [502, "Hat"]], "the new sample takes the slot that was freed");
});

test("the page has no a11y blockers of its own: buttons are named, rows are a list", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-sf-list").evaluate(l => l.tagName), "UL");
  for (const b of await page.locator("#cee-sampleset button").all()) assert.ok(((await b.textContent()).trim() || await b.getAttribute("aria-label") || "").length > 0);
});

test("for the blue a 24-bit stereo WAV is added as 16-bit mono, and the list says what the blue loads", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-sf-blue-note").isHidden(), true, "red is the default");
  await page.click("#cee-sf-model-blue");
  assert.match(await page.locator("#cee-sf-blue-note").textContent(), /höchstens 64 Samples, nur 16 Bit/);
  assert.match(await page.locator("#cee-sf-summary").textContent(), /Auf der blauen: 3 von höchstens 64 geladen/);
  await page.setInputFiles("#cee-sf-wav", h.file("Deep.wav", wav({ frames: 90, bits: 24, channels: 2 })));
  await page.locator("#app-toasts .cee-toast", { hasText: "16 Bit mono umgewandelt" }).waitFor();
  const added = page.locator(".cee-sf-row[data-state=new]");
  assert.match(await added.textContent(), /48 kHz, 16 Bit, Mono/);
  const next = parseSampleFile(await saved(page, () => page.click("#cee-sf-save")));
  assert.deepEqual(next.samples.map(s => [s.name, s.bits, s.channels, s.frames]).at(-1), ["Deep", 16, 1, 90]);
  assert.deepEqual(page.errors, []);
});

test("on the blue a 24-bit sample of the file is marked as skipped, and switching back to red keeps the WAV as it was", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#sampleset`);
  await page.click("#cee-sf-model-blue");
  const red = file({ 500: "Kick" });
  const deep = entryFromWav(wav({ frames: 30, bits: 24 }), 501, "Deep");
  const all = new Uint8Array(red.length + deep.length);
  all.set(red);
  all.set(deep, red.length);
  new DataView(all.buffer).setUint32(16 + 4 * 501, red.length, true);
  await page.setInputFiles("#cee-sf-file", h.file("e2sSample.all", all));
  await page.locator(".cee-sf-row").first().waitFor();
  assert.match(await page.locator(".cee-sf-row", { hasText: "Deep" }).textContent(), /lädt die blaue nicht \(kein 16 Bit\)/);
  assert.match(await page.locator("#cee-sf-summary").textContent(), /1 von höchstens 64/);
  await page.setInputFiles("#cee-sf-wav", h.file("St.wav", wav({ frames: 40, channels: 2 })));
  await page.locator(".cee-sf-row[data-state=new]", { hasText: "Mono" }).waitFor();
  await page.click("#cee-sf-model-red");
  await page.locator(".cee-sf-row[data-state=new]", { hasText: "Stereo" }).waitFor();
  assert.equal(await page.locator("#cee-sf-blue-note").isHidden(), true);
});
