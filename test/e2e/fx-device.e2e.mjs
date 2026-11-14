import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { makeFirmwareWithArrays, makeRecord } from "../helpers.mjs";
import { readUnits } from "../../src/node.mjs";
import { readFx, fxText } from "../../src/fx-v2.mjs";
import { collectionFor, parseCollection } from "../../src/fx-collection.mjs";
import { FX_CATALOG } from "../../data/fx/catalog.mjs";

// The export of e2sFx.all reads the effects from the connected Electribe (src/device-fx.mjs): its build, the names of
// its presets, and the e2sFx.all on its card, all over BLECH's reads. Here the device is the simulated one with a card.
let h;
let vsb;
const units = readUnits();
const catalog = FX_CATALOG.find(x => x.kind === "ifx");
before(async () => {
  h = await setUp();
  vsb = await makeFirmwareWithArrays([
    { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: 0x3b } }) },
    { kind: "ifx", slot: 1, record: makeRecord("ifx", { name: "Chorus", devices: { ifx1: 0x11 } }) },
  ], { patched: true });
  h.file("system.vsb", vsb);
});
after(async () => { await h.tearDown(); });

test("Vom Gerät lesen is off without a device", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#baukasten`);
  await page.click("#cee-baukasten-page-export");
  assert.equal(await page.locator("#cee-bk-device-read").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("Vom Gerät lesen: the device's build and preset names, e2sFx.all from its card on the places, the export from the device", async () => {
  const card = collectionFor("hacktribe", vsb, [{ kind: "ifx", slot: 5, preset: readFx(fxText(catalog), units).preset }], units);
  assert.equal(card.ok, true, card.reason);
  const page = await h.page({ device: true });
  await page.goto(`${h.url}?card#device`);
  await page.evaluate(() => window.__ceeStubReady);
  await page.evaluate(b => { window.__ceeCard.set("e2sFx.all", Uint8Array.from(b)); window.__ceeCard.set("e2sSample.all", new Uint8Array(4096)); }, Array.from(card.bytes));
  await page.click("#cee-connect");
  await page.locator("#cee-nav-state #cee-disconnect").waitFor();
  await page.click("#cee-tab-baukasten");
  await page.click("#cee-baukasten-page-export");
  await page.locator("#cee-bk-device-read:not([disabled])").waitFor();
  await page.click("#cee-bk-device-read");
  await page.locator("#app-toasts .cee-toast", { hasText: "Vom Gerät gelesen" }).waitFor();
  assert.match(await page.locator("#cee-bk-device-read-help").textContent(), /e2sFx\.all von der Karte: 1 Einträge/);
  assert.equal(await page.isChecked("#cee-bk-firmware-hacktribe input"), true, "the device's build is the one named");
  assert.equal(await page.locator("#cee-bk-slot-ifx-5 option:checked").textContent(), catalog.name, "the card's entry is on its place");
  assert.equal(await page.locator("#cee-bk-slots-ifx li[data-slot='1'] .cee-bk-slot-factory").textContent(), "Chorus", "the device's names");
  await page.click("#cee-bk-export-tab-mfx");
  await page.locator("#cee-bk-slots-mfx li[data-slot='1'] .cee-bk-grip").dragTo(page.locator("#cee-bk-slots-mfx li[data-slot='2']"));
  // No firmware file and no download of Korg's: the records come from the device.
  const bytes = await h.download(page, () => page.click("#cee-bk-collection"));
  const read = parseCollection(bytes);
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.build, "hacktribe");
  assert.equal(readFx(read.entries.find(e => e.kind === "mfx" && e.index === 1).text, units).preset.name, "Mod Delay", "a factory preset moved, read from the device");
  assert.ok(read.entries.some(e => e.kind === "ifx" && e.index === 4), "the card's entry goes back out");
  assert.deepEqual(page.errors, []);
});
