import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setUp } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makeFirmware } from "../helpers.mjs";
import { TABLES } from "../../src/map/index.mjs";
import { readModType } from "../../src/modtable.mjs";

const READ = TABLES.get("table.modType").file;
const KORG = TABLES.get("table.modTypeStock").file;
const SD_DIR = mkdtempSync(join(tmpdir(), "cee-e2e-sd-"));
process.env.GELUMPE_SD_DIR = SD_DIR;
process.env.GELUMPE_FLASH_DIR = mkdtempSync(join(tmpdir(), "cee-e2e-flash-"));
let h;
let fake;

before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: SD_DIR });
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

/** The page on the Modulationen tab, the firmware loaded in the emulator sidebar the way a person does it. */
async function modulations(vsb) {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-emu");
  if (vsb) {
    await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", vsb));
    await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  }
  await page.evaluate(() => { location.hash = "mod"; });
  return page;
}

const form = page => page.locator("#cee-mod-form");
const depth = page => form(page).getByLabel("Vorgabe-Tiefe");

test("modulations: before a firmware is loaded the entry is shut and says where to get one", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-emu");
  const tab = page.locator("#cee-tab-mod");
  assert.equal(await tab.getAttribute("aria-disabled"), "true");
  assert.match(await tab.getAttribute("title"), /Erst im Emulator eine Firmware \(VSB\) wählen/);
  assert.equal(await page.locator("#cee-mod-split").isVisible(), false);
  assert.deepEqual(page.errors, []);
});

test("modulations: 72 types, the copy that is read named, the first type as form fields with their meaning", async () => {
  const page = await modulations(await makeFirmware());
  await page.locator("#cee-mod-split").waitFor();
  assert.equal(await page.locator("#cee-mod-list li").count(), 72);
  assert.match(await page.locator("#cee-mod-list li").first().textContent(), /1\s*EG\+ Filter/);
  assert.equal(await page.locator("#cee-mod-where").count(), 0, "no line about the file offset");
  assert.equal(await page.locator("#cee-mod-list li:first-child button").getAttribute("aria-current"), "true");
  assert.equal(await form(page).getByLabel("Name", { exact: true }).inputValue(), "EG+ Filter");
  assert.equal(await page.locator("#cee-mod-target-value").textContent(), "Filter", "the target label");
  assert.match(await page.locator("#cee-mod-target").textContent(), /Ziel \(nur Etikett\).*liest dieses Byte nie/);
  assert.equal(await page.locator("#cee-mod-target select, #cee-mod-target input").count(), 0, "the label cannot be edited");
  assert.equal(await depth(page).inputValue(), "20");
  assert.equal(await form(page).getByLabel("Vorgabe-Speed").inputValue(), "100");
  assert.equal(await form(page).getByLabel("Kurve").inputValue(), "2");
  assert.deepEqual(await form(page).getByLabel("Kurve").locator("option:not([hidden])").allTextContents(), ["Sägezahn fallend", "Rechteck", "Dreieck", "Sample and Hold", "Zufall", "Rechteck einpolig", "Sinus"], "the seven measured waveforms");
  assert.equal(await form(page).locator(".cee-mod-slot").count(), 5, "slots 1 to 5");
  assert.equal(await page.locator("#cee-mod-slot-0-state").textContent(), "Ohne Wirkung: kein Ziel.");
  assert.match(await page.locator("#cee-mod-measured").textContent(), /Im Emulator gemessen, nicht gehört/);
  assert.match(await form(page).textContent(), /setzt die Firmware auf MOD\. DEPTH, wenn du die Art mit MOD\. TYPE wählst/);
  assert.match(await page.locator("#cee-mod-intro").textContent(), /Wirkt erst mit der neuen Firmware/);
  assert.equal(await page.locator("#cee-mod-count").textContent(), "Nichts geändert");
  assert.equal(await page.locator("#cee-mod-run").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("modulations: an edit is counted and marked, the check gets only the changed bytes, the download is the checked copy", async () => {
  const vsb = await makeFirmware();
  const page = await modulations(vsb);
  await page.locator("#cee-mod-split").waitFor();
  await page.click("#cee-mod-list li:nth-child(13) button");
  assert.equal(await form(page).getByLabel("Name", { exact: true }).inputValue(), "Type 13");
  await depth(page).fill("99");
  await page.locator("#cee-mod-count", { hasText: "1 Art geändert" }).waitFor();
  assert.equal(await page.locator("#cee-mod-list li:nth-child(13) .cee-mod-changed").isVisible(), true);
  assert.equal(await page.locator("#cee-mod-list li:nth-child(12) .cee-mod-changed").isVisible(), false);
  assert.equal(await page.locator("#cee-mod-download").isVisible(), false, "nothing to download before the check");
  await page.click("#cee-mod-run");
  await page.locator("#cee-mod-download").waitFor();
  await page.locator("#app-toasts .cee-toast", { hasText: /alles in Ordnung/ }).waitFor();
  const at = READ + 12 * 0x58 + 26;
  assert.equal(fake.seen.check.allow, `0x${at.toString(16)}:1`, "the check is told which byte may change");
  assert.deepEqual(new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100)), vsb, "the original goes to the check unchanged");
  const bytes = await h.download(page, () => page.click("#cee-mod-download"));
  assert.deepEqual(bytes, new Uint8Array(fake.seen.check.pair.subarray(0x200100)));
  const diff = [...bytes.keys()].filter(i => bytes[i] !== vsb[i]);
  assert.deepEqual(diff, [at], "one byte differs, in the copy that is read");
  assert.equal(readModType(bytes, READ, 12).depth, 99);
  assert.deepEqual(bytes.subarray(KORG, KORG + 72 * 0x58), vsb.subarray(KORG, KORG + 72 * 0x58), "the other copy stays");
  assert.deepEqual(page.errors, []);
});

test("modulations: name, curve and speed change too; resetting a type and everything puts the file's values back", async () => {
  const vsb = await makeFirmware();
  const page = await modulations(vsb);
  await page.locator("#cee-mod-split").waitFor();
  await page.click("#cee-mod-list li:nth-child(5) button");
  const name = form(page).getByLabel("Name", { exact: true });
  await name.fill("Mein Typ");
  await name.blur();
  await form(page).getByLabel("Kurve").selectOption("6");
  await form(page).getByLabel("Vorgabe-Speed").fill("7");
  assert.match(await page.locator("#cee-mod-list li:nth-child(5)").textContent(), /Mein Typ/);
  assert.equal(await page.locator("#cee-mod-count").textContent(), "1 Art geändert");
  await page.click("#cee-mod-run");
  await page.locator("#cee-mod-download").waitFor();
  const bytes = await h.download(page, () => page.click("#cee-mod-download"));
  assert.deepEqual(readModType(bytes, READ, 4), { ...readModType(vsb, READ, 4), name: "Mein Typ", speed: 7, curve: 6 });
  await page.click("#cee-mod-reset");
  assert.equal(await form(page).getByLabel("Name", { exact: true }).inputValue(), "Type 5");
  assert.equal(await page.locator("#cee-mod-count").textContent(), "Nichts geändert");
  assert.equal(await page.locator("#cee-mod-download").isVisible(), false, "an edit that is gone leaves no download");
  await depth(page).fill("3");
  await page.click("#cee-mod-reset-all");
  assert.equal(await depth(page).inputValue(), String(readModType(vsb, READ, 4).depth));
  assert.equal(await page.locator("#cee-mod-count").textContent(), "Nichts geändert");
  assert.deepEqual(page.errors, []);
});

test("modulations: a name the display cannot show or an empty one is refused and changes nothing", async () => {
  const page = await modulations(await makeFirmware());
  await page.locator("#cee-mod-split").waitFor();
  const name = form(page).getByLabel("Name", { exact: true });
  for (const bad of ["", "Ümlaut"]) {
    await name.fill(bad);
    await name.blur();
    assert.equal(await page.locator("#cee-mod-count").textContent(), "Nichts geändert", JSON.stringify(bad));
    assert.match(await page.locator("#cee-mod-list li:first-child").textContent(), /EG\+ Filter/);
  }
});

test("modulations: a failed emulator check offers no download", async () => {
  const page = await modulations(await makeFirmware());
  await page.locator("#cee-mod-split").waitFor();
  fake.hooks.checkOk = false;
  try {
    await depth(page).fill("50");
    await page.click("#cee-mod-run");
    await page.locator("#app-toasts .cee-toast", { hasText: "Die Prüfung hat 1 Fehler gefunden" }).waitFor();
    assert.equal(await page.locator("#cee-mod-download").isVisible(), false);
    await page.locator("#cee-mod-details > summary").click();
    assert.match(await page.locator("#cee-mod-checks").textContent(), /nicht bestanden Notschalter/);
  } finally {
    fake.hooks.checkOk = true;
  }
});

test("modulations: with no emulator service the check cannot run and the reason is shown", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu=1:${TOKEN}`);
  await page.click("#cee-tab-emu");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", await makeFirmware()));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.evaluate(() => { location.hash = "mod"; });
  await page.locator("#cee-mod-split").waitFor();
  await depth(page).fill("50");
  await page.click("#cee-mod-run");
  await page.locator("#app-toasts .cee-toast", { hasText: "antwortet nicht" }).waitFor();
  assert.equal(await page.locator("#cee-mod-download").isVisible(), false);
});

test("modulations: a slot gets source, target, strength and the depth flag; the check and the download hold exactly those bytes", async () => {
  const vsb = await makeFirmware();
  const page = await modulations(vsb);
  await page.locator("#cee-mod-split").waitFor();
  await page.click("#cee-mod-list li:nth-child(3) button");
  const slot = page.locator("#cee-mod-slot-1");
  await slot.getByLabel("Quelle").selectOption("1");
  await slot.getByLabel("Ziel").selectOption("3");
  assert.equal(await page.locator("#cee-mod-slot-1-state").textContent(), "Ohne Wirkung: die Stärke ist 0.");
  await slot.getByLabel("Stärke von").fill("-20");
  await slot.getByLabel("Stärke bis").fill("40");
  await slot.locator("label.ui-switch", { hasText: "Tiefe folgt MOD. DEPTH" }).click();
  assert.equal(await page.locator("#cee-mod-slot-1-state").textContent(), "", "now it does something");
  assert.equal(await page.locator("#cee-mod-count").textContent(), "1 Art geändert");
  assert.equal(await page.locator("#cee-mod-list li:nth-child(3) .cee-mod-changed").isVisible(), true);
  // The hint for "von" below 0 with "bis" above 0.
  assert.equal(await page.locator("#cee-mod-hint-box").isVisible(), true);
  assert.match(await page.locator("#cee-mod-hints").textContent(), /Slot 2.*immer von 0 bis 63/);
  assert.match(await page.locator("#cee-mod-warnings").textContent(), /1 Hinweis zu den Änderungen/);
  await page.click("#cee-mod-run");
  await page.locator("#cee-mod-download").waitFor();
  const at = READ + 2 * 0x58 + 0x2c + 8;
  assert.equal(fake.seen.check.allow, `0x${at.toString(16)}:2,0x${(at + 3).toString(16)}:3`, "the check is told these five bytes may change");
  const bytes = await h.download(page, () => page.click("#cee-mod-download"));
  assert.deepEqual([...bytes.keys()].filter(i => bytes[i] !== vsb[i]), [at, at + 1, at + 3, at + 4, at + 5]);
  assert.deepEqual(readModType(bytes, READ, 2).slots[1], { source: 1, target: 3, lo: -20, hi: 40, follow: 1 });
  assert.deepEqual(readModType(bytes, READ, 2).slots[0], readModType(vsb, READ, 2).slots[0], "the other slots stay");
  assert.equal(readModType(bytes, READ, 2).target, readModType(vsb, READ, 2).target, "the label stays");
  assert.deepEqual(page.errors, []);
});

test("modulations: source off, the codes with an open meaning only as expert values with a hint, a curve with no LFO slot", async () => {
  const page = await modulations(await makeFirmware());
  await page.locator("#cee-mod-split").waitFor();
  const slot = page.locator("#cee-mod-slot-2");
  assert.deepEqual(await slot.getByLabel("Quelle").locator("option:not([hidden])").allTextContents(), ["Hüllkurve", "LFO", "Aus"]);
  assert.deepEqual(await slot.getByLabel("Ziel").locator(":scope > option:not([hidden])").allTextContents(), ["Kein Ziel", "Pitch", "OSC", "Filter", "Level", "Pan", "IFX"]);
  assert.deepEqual(await slot.getByLabel("Ziel").locator("optgroup option").allTextContents(), ["Code 4, Wirkung unklar", "Code 5, Wirkung unklar", "Code 6, Wirkung unklar", "Code 7, Wirkung unklar"]);
  assert.equal(await slot.getByLabel("Ziel").locator("optgroup").getAttribute("label"), "Expertenwerte, Wirkung am Klang unklar");
  await slot.getByLabel("Quelle").selectOption("2");
  await slot.getByLabel("Ziel").selectOption("2");
  await slot.getByLabel("Stärke bis").fill("30");
  assert.equal(await page.locator("#cee-mod-slot-2-state").textContent(), "Ohne Wirkung: die Quelle ist aus.");
  assert.match(await page.locator("#cee-mod-hints").textContent(), /Slot 3 hat ein Ziel, tut im Emulator aber nichts: die Quelle ist aus/);
  await slot.getByLabel("Quelle").selectOption("1");
  await slot.getByLabel("Ziel").selectOption("6");
  assert.match(await page.locator("#cee-mod-hints").textContent(), /Ziel-Code 6 wirkt im Emulator.*nicht gemessen/);
  assert.equal(await page.locator("#cee-mod-slot-2-state").textContent(), "");
  await form(page).getByLabel("Kurve").selectOption("4");
  assert.doesNotMatch(await page.locator("#cee-mod-hints").textContent(), /nur bei Slots mit der Quelle LFO/, "an LFO slot is there");
  await slot.getByLabel("Quelle").selectOption("0");
  assert.match(await page.locator("#cee-mod-hints").textContent(), /nur bei Slots mit der Quelle LFO/);
  await page.click("#cee-mod-reset");
  assert.equal(await page.locator("#cee-mod-hint-box").isVisible(), false, "resetting the type clears the hints");
  assert.equal(await page.locator("#cee-mod-count").textContent(), "Nichts geändert");
  assert.equal(await page.locator("#cee-mod-warnings").textContent(), "");
  assert.deepEqual(page.errors, []);
});
