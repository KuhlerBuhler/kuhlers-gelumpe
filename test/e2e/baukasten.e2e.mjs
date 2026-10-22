import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makeFirmwareWithArrays, makeRecord } from "../helpers.mjs";
import { readUnits } from "../../src/node.mjs";
import { readFx } from "../../src/fx-v2.mjs";
import { parseCollection } from "../../src/fx-collection.mjs";
import { FX_CATALOG } from "../../data/fx/catalog.mjs";
import { severeViolations } from "./support/axe.mjs";

// The Baukasten needs no firmware to build an effect: a ready one or an empty one, sliders, a name, a file. Only the
// collection for the card asks for the firmware, and then makes the records from it.
let h;
let fake;
const units = readUnits();
before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: h.dir });
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

async function open(page) {
  await page.goto(`${h.url}#baukasten`);
  await page.locator("#cee-bk-fx-catalog li").first().waitFor();
}

test("Baukasten is open without firmware; a ready effect opens with its blocks and saves under Meine Sachen", async () => {
  const page = await h.page();
  await open(page);
  assert.equal(await page.getAttribute("#cee-tab-baukasten", "aria-disabled"), null, "no firmware needed");
  assert.deepEqual(await page.locator("#cee-bk-fx-catalog h3").allTextContents(), FX_CATALOG.map(c => c.name));
  await page.locator("#cee-bk-fx-catalog li", { hasText: "Short Delay" }).getByRole("button", { name: "Öffnen und anpassen" }).click();
  await page.locator("#cee-bk-blocks .cee-bk-slider").first().waitFor();
  assert.equal(await page.inputValue("#cee-bk-fx-name"), "Short Delay");
  assert.equal(await page.locator("#cee-bk-blocks .cee-bk-slider").count(), 23, "every parameter of Mod Delay has a slider");
  assert.equal(await page.locator("#cee-bk-blocks label", { hasText: "Mischung" }).count(), 1, "parameters have plain names");
  await page.fill("#cee-bk-fx-name", "Mein Delay");
  await page.click("#cee-bk-fx-save");
  await page.locator("#cee-bk-mine li", { hasText: "Mein Delay" }).waitFor();
  assert.match(await page.locator("#cee-bk-mine li").first().textContent(), /Master-Effekt, Platz 100/);
  const download = page.waitForEvent("download");
  await page.locator("#cee-bk-mine li").first().getByRole("button", { name: "Herunterladen" }).click();
  const file = await download;
  assert.equal(file.suggestedFilename(), "Mein-Delay.e2fx");
  const text = (await (await file.createReadStream()).toArray()).join("");
  const read = readFx(text, units);
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.preset.name, "Mein Delay");
  assert.deepEqual(page.errors, []);
});

test("an effect from nothing: where it works, a block from the palette, a name; without a block or a name it says what is missing", async () => {
  const page = await h.page();
  await open(page);
  await page.locator("#cee-bk-where button", { hasText: "Auf eine Spur" }).click();
  assert.equal(await page.locator("#cee-bk-blocks .cee-bk-block").count(), 2, "an insert effect has two blocks");
  await page.click("#cee-bk-fx-save");
  await page.locator("#app-toasts .cee-toast", { hasText: "mindestens einen Baustein" }).waitFor();
  await page.locator("#cee-bk-block-1").getByRole("button", { name: "Baustein wählen" }).click();
  await page.locator("#cee-bk-palette[open]").waitFor();
  assert.ok(await page.locator("#cee-bk-palette .cee-bk-group h3").count() >= 4, "the blocks come by group");
  await page.locator("#cee-bk-palette .cee-bk-unit", { hasText: "Chorus" }).click();
  await page.locator("#cee-bk-block-1 h4", { hasText: "Chorus" }).waitFor();
  await page.click("#cee-bk-fx-save");
  await page.locator("#app-toasts .cee-toast", { hasText: "Namen" }).waitFor();
  await page.fill("#cee-bk-fx-name", "Breit");
  await page.fill("#cee-bk-fx-slot", "42");
  await page.click("#cee-bk-fx-save");
  await page.locator("#cee-bk-mine li", { hasText: "Breit" }).waitFor();
  assert.match(await page.locator("#cee-bk-mine li", { hasText: "Breit" }).textContent(), /Insert-Effekt, Platz 42/);
  assert.deepEqual(await severeViolations(page), [], "axe, the builder with a block");
  assert.deepEqual(page.errors, []);
});

test("a modulation: a wave, what moves what, saved; the card file asks for the firmware and then holds every saved one", async () => {
  const page = await h.page();
  await open(page);
  await page.click("#cee-bk-tab-mod");
  await page.locator("#cee-bk-mod-catalog li", { hasText: "Filter Wobble" }).getByRole("button", { name: "Öffnen und anpassen" }).click();
  await page.locator("#cee-bk-curve button", { hasText: "Dreieck" }).click();
  assert.equal(await page.getAttribute("#cee-bk-curve button[data-value='2']", "aria-checked"), "true");
  await page.fill("#cee-bk-mod-slot", "5");
  await page.click("#cee-bk-mod-save");
  await page.locator("#cee-bk-mine li", { hasText: "Filter Wobble" }).waitFor();
  await page.click("#cee-bk-tab-fx");
  await page.locator("#cee-bk-fx-catalog li", { hasText: "Short Delay" }).getByRole("button", { name: "Öffnen und anpassen" }).click();
  await page.locator("#cee-bk-blocks .cee-bk-slider").first().waitFor();
  await page.click("#cee-bk-fx-save");
  await page.locator("#cee-bk-mine li", { hasText: "Short Delay" }).waitFor();
  await page.click("#cee-bk-collection");
  await page.locator("#app-toasts .cee-toast", { hasText: "braucht die Seite deine Firmware" }).waitFor();

  const vsb = await makeFirmwareWithArrays([
    { kind: "mfx", slot: 1, record: makeRecord("mfx", { name: "Mod Delay", devices: { mfx: 0x3b } }) },
    { kind: "ifx", slot: 1, record: makeRecord("ifx", { name: "Chorus", devices: { ifx1: 0x11 } }) },
  ], { patched: true });
  await page.goto(`${h.url}?vsb#emu=${fake.port}:${TOKEN}`);
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", vsb));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-tab-baukasten");
  await page.locator("#cee-bk-card-note", { hasText: "geladen" }).waitFor();
  const bytes = await h.download(page, () => page.click("#cee-bk-collection"));
  const read = parseCollection(bytes);
  assert.equal(read.ok, true, read.reason);
  assert.deepEqual(read.entries.map(e => [e.kind, e.index]).sort(), [["mfx", 99], ["mod", 4]], "every saved one at its place, 0-based");
  assert.deepEqual(page.errors, []);
});
