import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { makeFirmware } from "../helpers.mjs";
import { wav, file } from "../support/sample-file.mjs";
import { parseSampleFile } from "../../src/sample-file.mjs";

let h;
before(async () => { h = await setUp(); h.file("system.vsb", await makeFirmware()); });
after(async () => { await h.tearDown(); });

const SAMPLE = "e2sSample.all";
const TEMP = "e2sSample.tmp";
const rows = page => page.locator(".cee-sf-row .cee-sf-name").allTextContents();
const cardFile = (page, name) => page.evaluate(n => { const f = window.__ceeCard.get(n); return f ? Array.from(f) : null; }, name).then(a => (a ? Uint8Array.from(a) : null));

/** The page with the simulated Electribe attached, its card holding `files`, the Samples tab open. */
async function open(files = { [SAMPLE]: file({ 500: "Kick", 501: "Snare", 502: "Hat", 503: "Clap" }) }) {
  const page = await h.page({ device: true });
  await page.goto(`${h.url}?card#device`);
  await page.evaluate(() => window.__ceeStubReady);
  for (const [name, bytes] of Object.entries(files)) await page.evaluate(([n, b]) => window.__ceeCard.set(n, Uint8Array.from(b)), [name, Array.from(bytes)]);
  await page.click("#cee-connect");
  await page.locator("#cee-nav-state #cee-disconnect").waitFor();
  await page.click("#cee-tab-sampleset");
  return page;
}

test("Von der Electribe lesen is off without a device and on with one", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#sampleset`);
  assert.equal(await page.locator("#cee-sf-device").isDisabled(), true);
  const connected = await open();
  assert.equal(await connected.locator("#cee-sf-device").isDisabled(), false);
});

test("the samples of the card are listed over USB, the save button says where it writes", async () => {
  const page = await open();
  await page.click("#cee-sf-device");
  await page.locator(".cee-sf-row").first().waitFor();
  assert.deepEqual(await rows(page), ["Kick", "Snare", "Hat", "Clap"]);
  assert.match(await page.locator("#cee-sf-summary").textContent(), /^4 Samples/);
  await page.click("[data-slot='501']");
  assert.equal(await page.locator("#cee-sf-save").textContent(), "Auf die Karte schreiben");
  assert.deepEqual(page.errors, []);
});

test("adding a WAV over USB sends it behind the old samples and the header; the list is read again afterwards", async () => {
  const page = await open();
  await page.click("#cee-sf-device");
  await page.locator(".cee-sf-row").first().waitFor();
  const before = await cardFile(page, SAMPLE);
  await page.setInputFiles("#cee-sf-wav", h.file("Dose.wav", wav({ frames: 400 })));
  await page.locator(".cee-sf-row[data-state=new]").waitFor();
  await page.click("#cee-sf-save");
  await page.getByRole("button", { name: "Schreiben", exact: true }).click();
  await page.locator("#app-toasts .cee-toast", { hasText: "nur beim Start" }).first().waitFor();
  await page.waitForFunction(() => !document.querySelector(".cee-sf-row[data-state=new]") && !document.querySelector("#cee-sf-job:not([hidden])") && [...document.querySelectorAll(".cee-sf-name")].some(n => n.textContent === "Dose"));
  const after = await cardFile(page, SAMPLE);
  assert.deepEqual(after.subarray(4096, before.length), before.subarray(4096), "the old samples are untouched");
  assert.deepEqual(parseSampleFile(after).samples.map(s => s.name), ["Kick", "Snare", "Hat", "Clap", "Dose"]);
  assert.equal(await cardFile(page, TEMP), null);
  assert.equal(await page.locator("#cee-sf-job").isHidden(), true, "the progress goes away");
  assert.deepEqual(page.errors, []);
});

test("removing over USB compacts the file on the card and reads the list again", async () => {
  const page = await open();
  await page.click("#cee-sf-device");
  await page.locator(".cee-sf-row").first().waitFor();
  const before = await cardFile(page, SAMPLE);
  await page.click("[data-slot='502']");
  await page.click("#cee-sf-save");
  const dialog = page.getByRole("button", { name: "Schreiben", exact: true });
  await dialog.waitFor();
  assert.match(await page.locator("body").textContent(), /Tauschdatei/, "the question says how a removal is done");
  await dialog.click();
  await page.waitForFunction(() => [...document.querySelectorAll(".cee-sf-name")].map(n => n.textContent).join() === "Kick,Hat,Clap");
  const after = await cardFile(page, SAMPLE);
  const parsed = parseSampleFile(after);
  assert.deepEqual(parsed.samples.map(s => s.name), ["Kick", "Hat", "Clap"]);
  assert.ok(parsed.samples.every(s => !s.problem));
  assert.ok(after.length < before.length);
  assert.equal(parsed.samples.at(-1).offset + parsed.samples.at(-1).length, after.length, "no gap at the end");
  assert.equal(await cardFile(page, TEMP), null);
  assert.deepEqual(page.errors, []);
});

test("Abbrechen in the question writes nothing", async () => {
  const page = await open();
  await page.click("#cee-sf-device");
  await page.locator(".cee-sf-row").first().waitFor();
  const before = await cardFile(page, SAMPLE);
  await page.click("[data-slot='501']");
  await page.click("#cee-sf-save");
  await page.getByRole("button", { name: "Schreiben", exact: true }).waitFor();
  await page.keyboard.press("Escape");
  assert.deepEqual(await cardFile(page, SAMPLE), before);
  assert.equal(await page.locator("#cee-sf-save").isDisabled(), false, "the change is still staged");
});

test("a finished temp file of an interrupted swap is offered to finish; yes completes it", async () => {
  const done = file({ 500: "Kick", 502: "Hat" });
  const page = await open({ [TEMP]: done });
  await page.click("#cee-sf-device");
  const finish = page.getByRole("button", { name: "Fertigstellen", exact: true });
  await finish.waitFor();
  await finish.click();
  await page.waitForFunction(() => [...document.querySelectorAll(".cee-sf-name")].map(n => n.textContent).join() === "Kick,Hat");
  assert.deepEqual(await cardFile(page, SAMPLE), done);
  assert.equal(await cardFile(page, TEMP), null);
});

test("a broken temp file is offered to delete; the sample file beside it is not touched", async () => {
  const old = file({ 500: "A", 501: "B" });
  const page = await open({ [SAMPLE]: old, [TEMP]: file({ 500: "A", 501: "B" }).subarray(0, 4500) });
  await page.click("#cee-sf-device");
  const drop = page.getByRole("button", { name: "Löschen", exact: true });
  await drop.waitFor();
  await drop.click();
  await page.waitForFunction(() => [...document.querySelectorAll(".cee-sf-name")].map(n => n.textContent).join() === "A,B");
  assert.equal(await cardFile(page, TEMP), null);
  assert.deepEqual(await cardFile(page, SAMPLE), old);
});

test("Als Datei speichern is off without a device; with one it saves the whole sample file of the card", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#sampleset`);
  assert.equal(await page.locator("#cee-sf-download").isDisabled(), true);
  const old = file({ 500: "Kick", 501: "Snare", 502: "Hat", 503: "Clap" });
  const connected = await open({ [SAMPLE]: old });
  const download = connected.waitForEvent("download");
  await connected.click("#cee-sf-download");
  const saved = await download;
  assert.equal(saved.suggestedFilename(), SAMPLE);
  const fs = await import("node:fs/promises");
  assert.deepEqual(new Uint8Array(await fs.readFile(await saved.path())), old);
  await connected.locator("#cee-sf-job").waitFor({ state: "hidden" });
  assert.equal(await cardFile(connected, TEMP), null);
  assert.deepEqual(await cardFile(connected, SAMPLE), old, "nothing on the card changed");
  assert.deepEqual(connected.errors, []);
});

test("a download of the sample file can be cancelled while it runs; nothing is saved", async () => {
  const page = await open({});
  // a big file made in the page: a header and 16 MB behind it, so the download runs long enough to be cancelled
  await page.evaluate(head => { const f = new Uint8Array(16 << 20); f.set(head); window.__ceeCard.set("e2sSample.all", f); }, Array.from(file({}).subarray(0, 4096)));
  let saved = false;
  page.on("download", () => { saved = true; });
  await page.click("#cee-sf-download");
  await page.click("#cee-sf-cancel");
  await page.locator("#app-toasts .cee-toast", { hasText: "Abgebrochen." }).waitFor();
  await page.locator("#cee-sf-job").waitFor({ state: "hidden" });
  assert.equal(await page.locator("#cee-sf-download").isDisabled(), false, "the buttons are free again");
  assert.equal(saved, false);
  assert.deepEqual(page.errors, []);
});

test("a card without a sample file says so instead of saving", async () => {
  const page = await open({});
  await page.click("#cee-sf-download");
  await page.locator("#app-toasts .cee-toast", { hasText: "noch keine Sample-Datei" }).waitFor();
});
