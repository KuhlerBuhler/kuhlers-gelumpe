import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setUp, go } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makeFirmwareWithArrays, makeRecord, asStock } from "../helpers.mjs";
import { presetRoom, recordOf, nameAt, RECORD } from "../../src/presets.mjs";

const SD_DIR = mkdtempSync(join(tmpdir(), "cee-e2e-sd-"));
process.env.GELUMPE_SD_DIR = SD_DIR;
process.env.GELUMPE_FLASH_DIR = mkdtempSync(join(tmpdir(), "cee-e2e-flash-"));
let h;
let fake;

const presets = [
  { kind: "ifx", slot: 1, record: makeRecord("ifx", { name: "Punch", devices: { ifx1: 1 } }) },
  { kind: "ifx", slot: 2, record: makeRecord("ifx", { name: "Overdrive", devices: { ifx1: 2 } }) },
  { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: 1 } }) },
];

before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: SD_DIR });
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

/** The effect editor with the firmware loaded in the emulator sidebar, the way a person does it. */
async function effects(vsb) {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-emu");
  if (!(await page.locator("#cee-emu-setup").evaluate(n => n.open))) await page.click("#cee-emu-setup > summary");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", vsb));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await go(page, "fx");
  await page.locator("#cee-fx-slot").waitFor();
  return page;
}

test("presets: a firmware with room for 100 says so, adds a copy of the open preset, and hands out the copy after the emulator check", async () => {
  const vsb = await makeFirmwareWithArrays(presets);
  const page = await effects(vsb);
  await page.selectOption("#cee-fx-slot", "2");
  assert.match(await page.locator("#cee-fx-room").textContent(), /Insert: 52 von 100 Plätzen im Menü.*mit dem BLECHTRIBE-Patch preset-tables sind es 128/);
  assert.equal(await page.locator("#cee-export").isDisabled(), true, "nothing to write before an edit");
  await page.click("#cee-add");
  await page.locator("#cee-fx-slot option[value='53']").waitFor({ state: "attached" });
  assert.match(await page.locator("#cee-export-note").textContent(), /Insert 53 ist eine Kopie von 2/);
  assert.equal(await page.locator("#cee-fx-slot").inputValue(), "53");
  assert.match(await page.locator("#cee-fx-room").textContent(), /Insert: 53 von 100/);
  await page.click("#cee-export");
  await page.locator("#cee-download").waitFor();
  assert.match(await page.locator("#cee-export-note").textContent(), /alles in Ordnung/);
  const copy = new Uint8Array(fake.seen.check.pair.subarray(0x200100));
  assert.deepEqual(new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100)), vsb, "the original goes to the check unchanged");
  assert.ok(fake.seen.check.allow, "the check is told which data may change");
  assert.ok(fake.seen.check.allowCode, "and which menu length places");
  const bytes = await h.download(page, () => page.click("#cee-download"));
  assert.deepEqual(bytes, copy, "the download is the checked copy");
  assert.equal(presetRoom(bytes, "ifx").count, 53);
  assert.equal(presetRoom(bytes, "mfx").count, 33, "the master menu is untouched");
  const added = recordOf(bytes, "ifx", 53);
  const source = recordOf(vsb, "ifx", 2);
  assert.equal(nameAt(bytes, added.file), "Overdrive 53");
  assert.deepEqual(bytes.subarray(added.file + 16, added.file + RECORD), vsb.subarray(source.file + 16, source.file + RECORD));
  assert.deepEqual(page.errors, []);
});

test("presets: with the BLECH patch the room is 128 and no hint to get it", async () => {
  const page = await effects(await makeFirmwareWithArrays(presets, { patched: true }));
  assert.match(await page.locator("#cee-fx-room").textContent(), /Insert: 52 von 128 Plätzen im Menü\.$/);
  await page.click("#cee-fx-kind-master, label:has-text('Master')");
  assert.match(await page.locator("#cee-fx-room").textContent(), /Master: 33 von 128/);
  assert.deepEqual(page.errors, []);
});

test("presets: an edit of the open preset alone is enough to write a copy, and a failed check offers no download", async () => {
  const page = await effects(await makeFirmwareWithArrays(presets));
  assert.equal(await page.locator("#cee-export").isDisabled(), true);
  await page.locator("#cee-fx-editor input[type=text]").first().fill("Eigener Name");
  await page.locator("#cee-fx-editor input[type=text]").first().blur();
  await page.waitForFunction(() => !document.querySelector("#cee-export").disabled);
  fake.hooks.checkOk = false;
  try {
    await page.click("#cee-export");
    await page.locator("#cee-export-note", { hasText: "Die Prüfung hat" }).waitFor();
    assert.equal(await page.locator("#cee-download").isVisible(), false);
  } finally {
    fake.hooks.checkOk = true;
  }
  await page.click("#cee-export");
  await page.locator("#cee-download").waitFor();
  const bytes = await h.download(page, () => page.click("#cee-download"));
  assert.equal(nameAt(bytes, recordOf(bytes, "ifx", 1).file), "Eigener Name");
  assert.equal(presetRoom(bytes, "ifx").count, 52, "no preset added");
  assert.deepEqual(page.errors, []);
});

test("presets: Korg's own build without BLECH closes the Presets tab, no text about what it lacks", async () => {
  const stock = asStock(await makeFirmwareWithArrays(presets));
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-emu");
  if (!(await page.locator("#cee-emu-setup").evaluate(n => n.open))) await page.click("#cee-emu-setup > summary");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", stock));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.locator("#cee-tab-fx[title='Nicht mit Korgs Original-Firmware']").waitFor();
  assert.doesNotMatch(await page.locator("body").textContent(), /live ins RAM geht mit BLECH|Es fehlt:/);
  assert.deepEqual(page.errors, []);
});
