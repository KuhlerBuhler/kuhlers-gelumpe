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
const openCard = (page, list, name) => page.locator(`${list} li`, { hasText: name }).locator(".cee-catalog-open").click();

test("Baukasten is open without firmware; four sub-pages; a card opens in the editor and saves under Meine Effekte", async () => {
  const page = await h.page();
  await open(page);
  assert.equal(await page.getAttribute("#cee-tab-baukasten", "aria-disabled"), null, "no firmware needed");
  assert.deepEqual(await page.locator("#cee-baukasten-pages button").allTextContents(), ["Katalog", "Editor", "Meine Effekte", "Export"]);
  assert.deepEqual(await page.locator("#cee-bk-fx-catalog h3").allTextContents(), FX_CATALOG.map(c => c.name));
  const first = page.locator("#cee-bk-fx-catalog li").first();
  assert.equal(await first.locator(".cee-catalog-category").textContent(), "Echo", "the tag under the title");
  assert.match(await first.textContent(), /von Kuhler Buhler/, "and the creator beside it");
  assert.equal(await first.locator(".btn").count(), 0, "the whole card opens it, no button");
  await openCard(page, "#cee-bk-fx-catalog", "Short Delay");
  await page.locator("#cee-bk-blocks .cee-bk-slider").first().waitFor();
  assert.equal(await page.locator("#cee-bk-page-editor").isVisible(), true);
  assert.equal(await page.inputValue("#cee-bk-fx-name"), "Short Delay", "the title is the name");
  assert.equal(await page.locator("#cee-bk-where").isVisible(), false, "where it works is chosen only for a new one");
  assert.equal(await page.locator("#cee-bk-blocks .cee-bk-slider").count(), 23, "every parameter of Mod Delay has a slider");
  assert.equal(await page.locator("#cee-bk-blocks h5", { hasText: "Erweiterte Parameter" }).count(), 1, "the rest under a heading, not folded");
  assert.equal(await page.locator(".cee-shelf-tabs").isVisible(), false, "with an effect open there is no switch to Modulationen");
  assert.equal(await page.locator("#cee-bk-fx-help").isVisible(), false, "an effect with its blocks needs no explanation");
  assert.equal(await page.locator("#cee-bk-blocks details").count(), 0);
  await page.fill("#cee-bk-fx-name", "Mein Delay");
  // a slider set without dragging (a change event only) counts as well: a user test lost such a value
  await page.locator("#cee-bk-p-0-fb_depth").evaluate(n => { n.value = "70"; n.dispatchEvent(new Event("change")); });
  await page.fill("#cee-bk-p-0-dry_wet-value", "40");
  assert.equal(await page.inputValue("#cee-bk-p-0-dry_wet"), "40", "a typed value moves the slider");
  await page.click("#cee-bk-fx-save");
  assert.match(await page.locator("#cee-bk-fx-saved").textContent(), /Gespeichert: „Mein Delay“ steht unter Meine Effekte/, "the page says it was saved, not only a toast");
  await page.click("#cee-bk-fx-save");
  await page.click("#cee-baukasten-page-mine");
  assert.equal(await page.locator("#cee-bk-mine li").count(), 1, "saving again changes the same one");
  const download = page.waitForEvent("download");
  await page.click("#cee-baukasten-page-editor");
  await page.click("#cee-bk-fx-download");
  const file = await download;
  assert.equal(file.suggestedFilename(), "Mein-Delay.e2fx");
  const text = (await (await file.createReadStream()).toArray()).join("");
  const read = readFx(text, units);
  assert.equal(read.ok, true, read.reason);
  assert.equal(read.preset.stages[0].params.fb_depth, 70);
  assert.equal(read.preset.stages[0].params.dry_wet, 40, "a typed value is saved");
  assert.deepEqual(page.errors, []);
});

test("a new insert effect: two blocks from the palette, a name; Meine Effekte opens it again and the trash can asks first", async () => {
  const page = await h.page();
  await open(page);
  await page.click("#cee-baukasten-page-editor");
  await page.click("#cee-bk-new-ifx");
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
  await page.click("#cee-bk-fx-save");
  await page.click("#cee-baukasten-page-mine");
  const own = page.locator("#cee-bk-mine li", { hasText: "Breit" });
  assert.match(await own.textContent(), /Insert-Effekt/);
  await own.locator(".cee-catalog-open").click();
  assert.equal(await page.inputValue("#cee-bk-fx-name"), "Breit");
  assert.deepEqual(await severeViolations(page), [], "axe, the editor with a block");
  await page.click("#cee-baukasten-page-mine");
  await own.getByRole("button", { name: "Breit löschen" }).click();
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.equal(await own.count(), 1, "cancel keeps it");
  await own.getByRole("button", { name: "Breit löschen" }).click();
  await dialog.getByRole("button", { name: "Löschen" }).click();
  await own.waitFor({ state: "detached" });
  assert.deepEqual(page.errors, []);
});

test("export: places per slot, a drop swaps two, the trash can empties one; Exportieren asks for the firmware, reads an e2sFx.all back", async () => {
  const page = await h.page();
  await open(page);
  await page.click("#cee-bk-tab-mod");
  await openCard(page, "#cee-bk-mod-catalog", "Filter Wobble");
  await page.locator("#cee-bk-curve button", { hasText: "Dreieck" }).click();
  assert.equal(await page.getAttribute("#cee-bk-curve button[data-value='2']", "aria-checked"), "true");
  await page.click("#cee-bk-mod-save");
  await page.click("#cee-baukasten-page-catalog");
  await page.click("#cee-bk-tab-fx");
  await openCard(page, "#cee-bk-fx-catalog", "Short Delay");
  await page.locator("#cee-bk-blocks .cee-bk-slider").first().waitFor();
  await page.click("#cee-bk-fx-save");

  await page.click("#cee-baukasten-page-export");
  assert.equal(await page.locator("#cee-nav-state #cee-bk-collection").isVisible(), true, "Exportieren sits in the navbar");
  assert.equal(await page.locator("#cee-bk-slots-ifx li").count(), 100);
  await page.selectOption("#cee-bk-slot-mfx-3", { label: "Short Delay" });
  await page.locator("#cee-bk-slots-mfx li[data-slot='3'] .cee-bk-grip").dragTo(page.locator("#cee-bk-slots-mfx li[data-slot='100']"));
  assert.equal(await page.locator("#cee-bk-slot-mfx-100 option:checked").textContent(), "Short Delay", "A takes the place of B");
  assert.equal(await page.locator("#cee-bk-slot-mfx-3 option:checked").textContent(), "Werks-Preset", "and B the place of A");
  await page.selectOption("#cee-bk-slot-mfx-1", { label: "Short Delay" });
  await page.getByRole("button", { name: "Master-Effekt Platz 1 leeren" }).click();
  assert.equal(await page.locator("#cee-bk-slot-mfx-1 option:checked").textContent(), "Werks-Preset");
  await page.click("#cee-bk-tab-mod");
  assert.equal(await page.locator("#cee-bk-slots-ifx").count(), 0, "Modulationen show only their places");
  await page.selectOption("#cee-bk-slot-mod-5", { label: "Filter Wobble" });
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
  await page.click("#cee-baukasten-page-export");
  await page.locator("#cee-bk-card-note", { hasText: "geladen" }).waitFor();
  const bytes = await h.download(page, () => page.click("#cee-bk-collection"));
  const read = parseCollection(bytes);
  assert.equal(read.ok, true, read.reason);
  assert.deepEqual(read.entries.map(e => [e.kind, e.index]).sort(), [["mfx", 99], ["mod", 4]], "every place at its index, 0-based");

  // the file read back: a fresh browser gets the effects and their places
  await page.evaluate(() => { localStorage.removeItem("cee.baukasten"); localStorage.removeItem("cee.baukasten.slots"); });
  await page.reload();
  await page.click("#cee-tab-baukasten");
  await page.click("#cee-baukasten-page-export");
  await page.setInputFiles("#cee-bk-all", h.file("e2sFx.all", bytes));
  await page.locator("#app-toasts .cee-toast", { hasText: "2 Einträge" }).waitFor();
  assert.equal(await page.locator("#cee-bk-slot-mfx-100 option:checked").textContent(), "Short Delay");
  assert.deepEqual(page.errors, []);
});
