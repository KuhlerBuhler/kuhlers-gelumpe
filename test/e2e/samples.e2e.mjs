import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makeFirmware } from "../helpers.mjs";
import { sampleRam } from "../support/samples.mjs";
import { fieldInRamEntry, ramEntry } from "../../src/map/address.mjs";
import { field } from "../../src/map/index.mjs";

let h;
let fake;
let firmware;

const BLECH = { index: 652, name: "Blech", tune: 0, rate: 48000, pcmBytes: 9600, stereo: 0, category: 3, importNumber: 17, oneShot: 1 };
const KICK = { index: 500, name: "Kick", tune: -16, rate: 44100, pcmBytes: 4000 };

const NAME_AT = index => fieldInRamEntry(field("sample.name"), index).ram;
const TUNE_AT = index => fieldInRamEntry(field("sample.tune"), index).ram;

before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: h.dir });
  firmware = await makeFirmware();
  h.file("system.vsb", firmware);
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

const peekFake = (addr, n = 1) => Array.from({ length: n }, (_, i) => fake.ram.get(addr + i) ?? 0);

/** The emulator's RAM starts each test with the given samples and empty slots elsewhere. */
async function seedFake(...entries) {
  for (const context of h.browser.contexts()) await context.close();   // pages of earlier tests also listen to the service
  for (const index of [BLECH.index, KICK.index, 700, 900]) for (const { addr, bytes } of sampleRam({ index })) fake.poke(addr, Array.from(bytes));
  for (const e of entries) for (const { addr, bytes } of sampleRam(e)) fake.poke(addr, Array.from(bytes));
}

/** The page with the emulator running, on the Samples tab. */
async function samples() {
  await seedFake(BLECH, KICK);
  const page = await h.page();
  await page.goto(`${h.url}?labs#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-emu");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-e2-power");
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  await page.click("#cee-tab-samples");
  return page;
}

const name = page => page.locator("#cee-sample-name");
const tune = page => page.locator("#cee-sample-tune");
const job = page => page.locator("#cee-sample-job .cee-status");

async function openBlech(page) {
  await page.click("#cee-sample-list");
  await page.locator("#cee-sample-names li", { hasText: "Blech" }).click();
  await name(page).waitFor();
}

test("samples: the page says what it does and that a change lives in RAM only, before anything is read", async () => {
  const page = await samples();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Samples");
  const note = await page.locator("#cee-sample-note").textContent();
  assert.match(note, /Nur im RAM/);
  assert.match(note, /SD-Datei mit den Samples blieb dabei unverändert/);
  assert.match(note, /Nicht gemessen ist, ob eine Änderung einen Neustart überlebt/);
  assert.match(await page.locator("#cee-sample-status").textContent(), /Noch nichts gelesen/);
  assert.equal(await page.locator("#cee-sample-split").isVisible(), false);
  assert.deepEqual(page.errors, []);
});

test("samples: the names are read from the emulator and listed with their numbers, an entry opens with its facts", async () => {
  const page = await samples();
  await page.click("#cee-sample-list");
  await page.locator("#cee-sample-status", { hasText: "2 Samples mit Namen, gelesen aus dem Emulator" }).waitFor();
  assert.deepEqual(await page.locator("#cee-sample-names li").allTextContents(), ["501Kick", "653Blech"]);
  await page.locator("#cee-sample-names li", { hasText: "Blech" }).click();
  await name(page).waitFor();
  assert.equal(await name(page).inputValue(), "Blech");
  assert.equal(await tune(page).inputValue(), "0");
  assert.match(await page.locator("#cee-sample-form h3").textContent(), /Sample 653: Blech/);
  const facts = await page.locator("#cee-sample-facts").textContent();
  assert.match(facts, /Samplerate48000 Hz/);
  assert.match(facts, /Länge9600 Byte PCM/);
  assert.match(facts, /KanäleMono/);
  assert.match(facts, /Kategorie3/);
  assert.match(facts, /Import-Nummer17/);
  assert.match(facts, /One-Shotja/);
  assert.equal(await page.locator("#cee-sample-send").isDisabled(), true, "nothing changed yet");
  assert.equal(await page.locator("#cee-sample-names li:has-text('Blech') button").getAttribute("aria-current"), "true");
  assert.deepEqual(page.errors, []);
});

test("samples: the default names of unused slots (SampleNNN, as the emulator measured) stay out of the list until asked for", async () => {
  const page = await samples();
  for (const { addr, bytes } of sampleRam({ index: 700, name: "Sample701", rate: 48000 })) fake.poke(addr, Array.from(bytes));
  await page.click("#cee-sample-list");
  await page.locator("#cee-sample-status", { hasText: "2 Samples mit Namen" }).waitFor();
  assert.deepEqual(await page.locator("#cee-sample-names li").allTextContents(), ["501Kick", "653Blech"]);
  await page.locator("label.ui-switch", { hasText: "Standardnamen" }).click();
  await page.locator("#cee-sample-status", { hasText: "3 Samples in der Liste" }).waitFor();
  assert.deepEqual(await page.locator("#cee-sample-names li").allTextContents(), ["501Kick", "653Blech", "701Sample701"]);
  await page.locator("#cee-sample-names li", { hasText: "Sample701" }).click();
  await page.locator("#cee-sample-form .cee-hint", { hasText: "sieht unbenutzt aus" }).waitFor();
  assert.deepEqual(page.errors, []);
});

test("samples: a slot is read by its number, and one without audio is called unused", async () => {
  const page = await samples();
  await page.fill("#cee-sample-number", "901");
  await page.click("#cee-sample-open");
  await page.locator("#cee-sample-form h3", { hasText: "Sample 901" }).waitFor();
  assert.match(await page.locator("#cee-sample-form").textContent(), /Der Platz sieht unbenutzt aus: die PCM-Länge ist 0/);
  await page.fill("#cee-sample-number", "999");
  await page.click("#cee-sample-open");
  assert.match(await page.locator("#cee-sample-status").textContent(), /Die Sample-Nummer geht von 1 bis 998/);
  assert.deepEqual(page.errors, []);
});

test("samples: a name is sent with the gate's yes, read back, and one click takes it back", async () => {
  const page = await samples();
  await openBlech(page);
  await name(page).fill("Dose");
  assert.equal(await page.locator("#cee-sample-verdict").textContent().then(t => /sauber/.test(t)), true);
  await page.click("#cee-sample-send");
  await job(page).filter({ hasText: /Fertig|Fehlgeschlagen/ }).waitFor();
  assert.equal(await job(page).textContent(), "Fertig", await page.locator("#cee-sample-job .ui-job-meta").textContent());
  assert.match(await page.locator("#cee-sample-job .ui-job-meta").textContent(), /Nur im RAM, nicht gespeichert/);
  assert.deepEqual(peekFake(NAME_AT(652), 6), [..."Dose"].map(c => c.charCodeAt(0)).concat([0, 0]));
  assert.equal(await name(page).inputValue(), "Dose", "the page shows what was read back");
  assert.match(await page.locator("#cee-sample-form h3").textContent(), /Sample 653: Dose/);
  assert.deepEqual(peekFake(TUNE_AT(652)), [0], "the tune was not touched");
  await page.click("#cee-sample-undo");
  await page.locator("#cee-sample-job .ui-job-meta", { hasText: "Alter Stand" }).waitFor();
  assert.deepEqual(peekFake(NAME_AT(652), 6), [..."Blech"].map(c => c.charCodeAt(0)).concat([0]));
  assert.equal(await name(page).inputValue(), "Blech");
  assert.equal(await page.locator("#cee-sample-undo").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("samples: a tune nobody has seen on the device waits for a yes, and a no sends nothing", async () => {
  const page = await samples();
  await openBlech(page);
  await tune(page).fill("12");
  assert.match(await page.locator("#cee-sample-verdict").textContent(), /Tune 12 liegt außerhalb der Werte, die am Gerät gesehen wurden \(-16 bis 0\)/);
  await page.click("#cee-sample-send");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  assert.match(await dialog.textContent(), /Skala ist nicht gemessen/);
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.deepEqual(peekFake(TUNE_AT(652)), [0], "nothing went out on no");
  assert.equal(await tune(page).inputValue(), "12", "the unsent edit stays");
  await page.click("#cee-sample-send");
  await page.locator("dialog.ui-dialog[open]").getByRole("button", { name: "Senden" }).click();
  await job(page).filter({ hasText: "Fertig" }).waitFor();
  assert.deepEqual(peekFake(TUNE_AT(652)), [12]);
  assert.deepEqual(peekFake(NAME_AT(652), 5), [..."Blech"].map(c => c.charCodeAt(0)), "the name was not touched");
  await tune(page).fill("-12");
  await page.click("#cee-sample-send");
  await job(page).filter({ hasText: "Fertig" }).waitFor();
  assert.deepEqual(peekFake(TUNE_AT(652)), [0xf4], "-12 as the device holds it");
  assert.equal(await page.locator("dialog.ui-dialog[open]").count(), 0, "-12 was seen on the device: no question");
  assert.deepEqual(page.errors, []);
});

test("samples: a name the display cannot show is refused in the field and cannot be sent", async () => {
  const page = await samples();
  await openBlech(page);
  await name(page).fill("Ümlaut");
  assert.equal(await page.locator("#cee-sample-send").isDisabled(), true);
  assert.match(await page.locator("#cee-sample-form .ui-field").first().textContent(), /display cannot show/);
  await name(page).fill("Blech 2");
  assert.equal(await page.locator("#cee-sample-send").isDisabled(), false);
  assert.deepEqual(peekFake(NAME_AT(652), 5), [..."Blech"].map(c => c.charCodeAt(0)));
});

test("samples: without an emulator or a device the page says so and reads nothing", async () => {
  const page = await h.page();
  await page.goto(`${h.url}?labs`);
  await page.click("#cee-tab-samples");
  await page.click("#cee-sample-list");
  assert.match(await page.locator("#cee-sample-status").textContent(), /Nichts verbunden/);
  assert.equal(await page.locator("#cee-sample-split").isVisible(), false);
});

/**
 * The real device (the Web MIDI stand-in) with the emulator in front of it: a change goes through the emulator first.
 * The stand-in is the SimDevice; its sample tables are filled from here.
 */
async function device() {
  await seedFake(BLECH, KICK);
  const page = await h.page({ device: true });
  await page.goto(`${h.url}?labs#emu=${fake.port}:${TOKEN}`);
  await page.evaluate(() => window.__ceeStubReady);
  for (const e of [BLECH, KICK]) {
    await page.evaluate(parts => { for (const p of parts) window.__ceeSim.device.poke(p.addr, Uint8Array.from(p.bytes)); },
      sampleRam(e).map(p => ({ addr: p.addr, bytes: Array.from(p.bytes) })));
  }
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-e2-power");
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  await go(page, "device");
  await page.click("#cee-connect");
  await page.locator(".cee-device-status .cee-status").filter({ hasNotText: "getrennt" }).waitFor();
  await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
  await page.click("#cee-tab-samples");
  return page;
}

const stub = (page, addr, n = 1) => page.evaluate(([a, k]) => Array.from(window.__ceeSim.device.peek(a, k)), [addr, n]);
const stubFaults = page => page.evaluate(() => window.__ceeSim.faults.map(f => f.message).filter(m => !m.startsWith("read at 0xc03404c0")));

test("samples on the device: read from the device, tried in the emulator first, sent, read back and taken back", async () => {
  const page = await device();
  await openBlech(page);
  assert.match(await page.locator("#cee-sample-status").textContent(), /gelesen aus dem Gerät/);
  await name(page).fill("Dose");
  fake.seen.midi.length = 0;
  await page.click("#cee-sample-send");
  await job(page).filter({ hasText: /Fertig|Fehlgeschlagen/ }).waitFor({ timeout: 20_000 });
  assert.equal(await job(page).textContent(), "Fertig");
  const want = [..."Dose"].map(c => c.charCodeAt(0)).concat([0, 0]);
  assert.deepEqual(await stub(page, NAME_AT(652), 6), want, "the device holds the new name");
  assert.deepEqual(peekFake(NAME_AT(652), 6), want, "and the emulator took it first");
  assert.ok(fake.seen.midi.length > 0, "the rehearsal went over the emulator's port");
  await page.click("#cee-sample-undo");
  await page.locator("#cee-sample-job .ui-job-meta", { hasText: "Alter Stand" }).waitFor({ timeout: 20_000 });
  assert.deepEqual(await stub(page, NAME_AT(652), 6), [..."Blech"].map(c => c.charCodeAt(0)).concat([0]));
  assert.deepEqual(await stubFaults(page), []);
  assert.deepEqual(page.errors, []);
});

test("samples on the device: a tune nobody has seen waits for a yes and nothing reaches the device or the emulator before it", async () => {
  const page = await device();
  await openBlech(page);
  await tune(page).fill("12");
  await page.click("#cee-sample-send");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.deepEqual(await stub(page, TUNE_AT(652)), [0]);
  assert.deepEqual(peekFake(TUNE_AT(652)), [0]);
  await page.click("#cee-sample-send");
  await page.locator("dialog.ui-dialog[open]").getByRole("button", { name: "Senden" }).click();
  await job(page).filter({ hasText: "Fertig" }).waitFor({ timeout: 20_000 });
  assert.deepEqual(await stub(page, TUNE_AT(652)), [12]);
  assert.deepEqual(await stub(page, ramEntry("sampleMeta", 652).ram + 16, 4), [0x80, 0xbb, 0, 0], "the sample rate next to it is untouched (48000)");
  assert.deepEqual(await stubFaults(page), []);
});
