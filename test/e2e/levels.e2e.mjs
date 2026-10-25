import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go, pickPreset } from "./harness.mjs";
import { makeFirmware, makeRecord, makePattern } from "../helpers.mjs";
import { loadUnits } from "../../src/units.mjs";
import { Pattern } from "../../src/pattern.mjs";
import { tableEntry } from "../../src/map/address.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";

const units = loadUnits();
let h;
let fake;
let firmware;
let start;

const preset = (name, devices, params = {}) => {
  const r = makeRecord("ifx", { name, devices });
  for (const [stage, values] of Object.entries(params)) r.setParams(units, stage, values);
  r.setDevice("mfx", 0x27);
  return r;
};

before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin);
  firmware = await makeFirmware([
    { kind: "ifx", slot: 50, record: preset("Quiet Pump", { ifx1: 0x15 }, { ifx1: { output_gain: 34 } }) },
    { kind: "ifx", slot: 51, record: preset("Loud Fuzz", { ifx1: 0x0f }, { ifx1: { output_level: 124 } }) },
    { kind: "ifx", slot: 52, record: preset("Short Room", { ifx1: 0x18 }, { ifx1: { dry_level: 120, wet_level: 30, fb_depth: 36, high_damp: 0, low_damp: 0, off_delay_time: 24 } }) },
    { kind: "ifx", slot: 53, record: preset("Stage Two", { ifx1: 0x0a, ifx2: 0x18 }) },
  ]);
  h.file("system.vsb", firmware);

  const p = new Pattern(makePattern());
  p.setRaw("pattern.playLevel", [], 127 - 90);
  [100, 50, 25].forEach((v, i) => p.setRaw("part.level", [i], v));
  for (let i = 3; i < 16; i++) p.setRaw("part.level", [i], 0);
  // A pattern sent over SysEx comes back with glide 0, so the fixture starts there.
  for (let i = 0; i < 16; i++) { p.setRaw("part.mute", [i], 0); p.setRaw("part.ifxOn", [i], 0); p.setRaw("part.glide", [i], 0); }
  p.setRaw("part.mute", [2], 1);
  p.setRaw("part.ifxOn", [0], 1); p.setRaw("part.ifxType", [0], 49);   // slot 50
  p.setRaw("part.ifxOn", [1], 1); p.setRaw("part.ifxType", [1], 50);   // slot 51
  start = Uint8Array.from(p.bytes);
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

/** The Presets page with the stand-in device connected, as a person gets there; `connected: false` stops before the connection. */
async function open({ connected = true, running = true } = {}) {
  for (const context of h.browser.contexts()) await context.close();
  for (const index of [49, 50, 51, 52]) {
    const slot = tableEntry("table.ifx", index);
    fake.poke(slot.ram, Array.from(firmware.subarray(slot.file, slot.file + slot.size)));
  }
  const page = await h.page({ device: true });
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.evaluate(() => window.__ceeStubReady);
  await page.evaluate(bytes => { window.__ceeSim.device.pattern = Uint8Array.from(bytes); }, [...start]);
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  const since = Date.now();
  if (running) {
    await page.click("#cee-e2-power");
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  }
  if (connected) {
    await go(page, "device");
    await page.click("#cee-connect");
    await page.locator(".cee-device-status .cee-status").filter({ hasNotText: "getrennt" }).waitFor();
    await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
  }
  await page.evaluate(() => { location.hash = "fx"; });
  await page.locator("#cee-fx-slot").waitFor({ timeout: 15_000 });
  // The first status poll schedules a preset refresh 3 s later; an edit made before it would be redrawn.
  if (running) await new Promise(r => setTimeout(r, Math.max(0, 4500 - (Date.now() - since))));
  return page;
}

const sentPattern = page => page.evaluate(() => Array.from(window.__ceeSim.device.pattern));
const row = (page, id) => page.locator(`#cee-lv-row-${id}`);

test("levels: nothing is shown before the pattern is fetched, and without a device the page says so", async () => {
  const page = await open({ connected: false, running: false });
  assert.equal(await page.locator("#cee-lv-body").isHidden(), true);
  assert.match(await page.locator("#cee-levels h2").textContent(), /Pegel/);
  await page.click("#cee-lv-fetch");
  await page.locator("#app-toasts .cee-toast", { hasText: "Nichts verbunden" }).waitFor();
  assert.equal(await page.locator("#cee-lv-body").isHidden(), true);
  assert.deepEqual(page.errors, []);
});

test("levels: the pattern's levels side by side, the heard-too-loud insert named, its preset one click away", async () => {
  const page = await open();
  await page.click("#cee-lv-fetch");
  await page.locator("#cee-lv-body").waitFor();
  assert.equal(await row(page, "pattern").locator(".cee-level-value").textContent(), "90");
  assert.equal(await row(page, 0).locator(".cee-level-value").textContent(), "100");
  assert.equal(await row(page, 1).locator(".cee-level-value").textContent(), "50");
  assert.match(await row(page, 2).textContent(), /stumm/);
  assert.equal(await page.locator("#cee-lv-rows .cee-level-row").count(), 17);
  assert.equal(await page.locator("#cee-lv-send").isDisabled(), true, "nothing to send before anything changes");

  const fxList = page.locator("#cee-lv-fx");
  await fxList.locator("[data-fx-slot='50']").waitFor();
  assert.match(await fxList.locator("[data-fx-slot='50']").textContent(), /Part 1: IFX 50 Quiet Pump\. output_gain 34/);
  assert.equal(await fxList.locator("[data-fx-slot='50'] .cee-status").count(), 0, "a level in the playable range carries no warning");
  assert.match(await fxList.locator("[data-fx-slot='51']").textContent(), /output_level 124/);
  assert.match(await fxList.locator("[data-fx-slot='51'] .cee-status").textContent(), /gehört, zu laut/);
  assert.match(await fxList.textContent(), /Gelesen aus dem RAM/);

  await fxList.locator("[data-fx-slot='51'] button").click();
  await pickPreset(page, 51);
  assert.equal(await page.locator("#cee-fx-slot").inputValue(), "51");
  assert.deepEqual(page.errors, []);
});

test("levels: a factor previews the change first and sends only the part levels, and the send is taken back", async () => {
  const page = await open();
  await page.click("#cee-lv-fetch");
  await page.locator("#cee-lv-body").waitFor();

  await page.locator("#cee-lv-value").fill("0.5");
  assert.match(await page.locator("#cee-lv-summary").textContent(), /Faktor 0,5: der lauteste Pegel geht von 100 auf 50, 3 Pegel ändern sich/);
  assert.equal(await row(page, 0).locator(".cee-level-value").textContent(), "100 zu 50");
  assert.equal(await row(page, 2).locator(".cee-level-value").textContent(), "25 zu 13");
  assert.equal(await row(page, "pattern").locator(".cee-level-value").textContent(), "90", "the play level stays out unless asked");
  assert.deepEqual(await sentPattern(page), [...start], "a preview sends nothing");

  await page.click("#cee-lv-send");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  assert.match(await dialog.textContent(), /Part 1 100 zu 50, Part 2 50 zu 25, Part 3 25 zu 13/);
  await dialog.getByRole("button", { name: "Senden" }).click();
  await page.locator("#app-toasts .cee-toast", { hasText: "Gesendet und zurückgelesen" }).waitFor({ timeout: 30_000 });

  const after = await sentPattern(page);
  const changed = [...after.keys()].filter(i => after[i] !== start[i]);
  const expected = [0, 1, 2].map(k => Pattern.offset("part.level", [k]));
  assert.deepEqual(changed, expected);
  assert.deepEqual([50, 25, 13], expected.map(i => after[i]));
  assert.equal(await row(page, 0).locator(".cee-level-value").textContent(), "50", "the overview shows what is in the buffer now");
  assert.equal(await page.locator("#cee-lv-value").inputValue(), "1", "the factor is back at 1, so the same click does not scale twice");

  await page.click("#cee-lv-undo");
  await page.locator("#app-toasts .cee-toast", { hasText: "wieder am Gerät" }).waitFor({ timeout: 30_000 });
  assert.deepEqual(await sentPattern(page), [...start]);
  assert.deepEqual(page.errors, []);
});

test("levels: a target sets the loudest part, the play level can join, and a factor that would clip is held back", async () => {
  const page = await open();
  await page.click("#cee-lv-fetch");
  await page.locator("#cee-lv-body").waitFor();

  await page.locator("label.ui-segmented-option", { hasText: "Zielwert" }).click();
  assert.equal(await page.locator("#cee-lv-value").inputValue(), "100", "the target starts at the loudest part");
  await page.locator("#cee-lv-value").fill("80");
  assert.equal(await row(page, 1).locator(".cee-level-value").textContent(), "50 zu 40");
  await page.locator("label.ui-switch", { hasText: "Pattern-Lautstärke" }).click();
  assert.equal(await row(page, "pattern").locator(".cee-level-value").textContent(), "90 zu 72");

  await page.locator("label.ui-segmented-option", { hasText: "Faktor" }).click();
  await page.locator("#cee-lv-value").fill("2");
  assert.match(await page.locator("#cee-lv-summary").textContent(), /auf 127.*begrenzt|begrenzt.*Verhältnis/);
  assert.equal(await row(page, 0).locator(".cee-level-value").textContent(), "100 zu 127");
  assert.equal(await row(page, 1).locator(".cee-level-value").textContent(), "50 zu 64");

  await page.locator("#cee-lv-value").fill("0");
  assert.match(await page.locator("#cee-lv-summary").textContent(), /größer als 0/);
  assert.equal(await page.locator("#cee-lv-send").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("pseudo reverb: offered on a short delay, marked untested, applies its values and leaves the name", async () => {
  const page = await open({ connected: false });
  await pickPreset(page, 52);
  const box = page.locator("#cee-suggest-pseudoReverb");
  await box.waitFor();
  assert.match(await box.textContent(), /Vorschlag: Pseudo Reverb/);
  assert.match(await box.locator(".cee-status").textContent(), /am Gerät ungetestet/);
  assert.match(await box.textContent(), /Kein echter Hall/);
  const feedback = page.locator("#cee-fx-editor .ui-field", { hasText: "Feedback" }).locator("input.ui-range");
  assert.equal(await feedback.inputValue(), "36");

  await page.click("#cee-suggest-pseudoReverb-apply");
  await page.waitForFunction(() => document.querySelector("#cee-fx-editor .ui-field input.ui-range") !== null);
  assert.equal(await page.locator("#cee-fx-editor .ui-field", { hasText: "Feedback" }).locator("input.ui-range").inputValue(), "64");
  assert.equal(await page.locator("#cee-fx-editor input[type=text]").first().inputValue(), "Short Room", "the user's own name stays");
  assert.deepEqual(page.errors, []);
});

test("pseudo reverb: not offered on another unit, and refused where short delay sits in stage 2", async () => {
  const page = await open({ connected: false });
  await pickPreset(page, 50);
  assert.equal(await page.locator("#cee-suggest-pseudoReverb").count(), 0);

  await pickPreset(page, 53);
  const box = page.locator("#cee-suggest-pseudoReverb");
  await box.waitFor();
  assert.match(await page.locator("#cee-suggest-pseudoReverb-refusal").textContent(), /Stufe 2.*kills sound device-wide/);
  assert.equal(await page.locator("#cee-suggest-pseudoReverb-apply").count(), 0);
  assert.match(await page.locator("#cee-verdict").textContent(), /tödlich/, "the gatekeeper calls the record itself fatal");
  assert.deepEqual(page.errors, []);
});
