import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { setUp } from "./harness.mjs";
import { tempDir } from "../support/lifetime.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makeFirmware, asStock } from "../helpers.mjs";
import { sha256 } from "../../src/firmware.mjs";
import { severeViolations } from "./support/axe.mjs";

// Korg's plain build has no Hacktribe tables and no SysEx: the emulator page shows nothing of the device state, and the pages
// that read those tables (Presets, Modulationen) stay shut. A build that carries BLECH, and Hacktribe's own, keep them.
// The page loads the BLECH set from fixed addresses, so these tests serve a set of their own with one patch for Korg's build.
const SD_DIR = tempDir("cee-e2e-sd-");
process.env.GELUMPE_SD_DIR = SD_DIR;
process.env.GELUMPE_FLASH_DIR = tempDir("cee-e2e-flash-");
const FREE = 0x1a2100;
const BYTES = "e12fff1e";
let patch;
let h;
let fake;

before(async () => {
  patch = {
    format: "gelumpe-patch", version: 1, id: "script-runtime", name: "Laufzeit", builds: ["stock"],
    changes: [{ file: FREE, bytes: BYTES, expect: await sha256(new Uint8Array(4)) }],
  };
  h = await setUp(dir => {
    mkdirSync(join(dir, "patches"));
    writeFileSync(join(dir, "patches", "script-runtime.json"), JSON.stringify(patch));
    writeFileSync(join(dir, "patches", "blech.json"), JSON.stringify({ format: "gelumpe-patch-set", version: 1, id: "blech", name: "BLECH", patches: ["data/patches/script-runtime.json"] }));
    return [["/data/patches/", `${dir}/patches/`]];
  });
  fake = await fakeService(new URL(h.url).origin, { sdDir: SD_DIR });
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

const withBlech = bytes => {
  const out = Uint8Array.from(bytes);
  out.set(Uint8Array.from(BYTES.match(/../g), b => parseInt(b, 16)), FREE);
  return out;
};

async function emulatorWith(vsb) {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-emu");
  if (!(await page.locator("#cee-emu-setup").evaluate(n => n.open))) await page.click("#cee-emu-setup > summary");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", vsb));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: /erkannt/ }).waitFor();
  return page;
}

const shut = (page, tab) => page.locator(`#cee-tab-${tab}`).getAttribute("aria-disabled");
const section = page => page.getByRole("heading", { name: "Was das Gerät gerade zeigt" });

test("Korg's plain build: no section about the device state, Presets and Modulationen are disabled with a short tooltip", async () => {
  const page = await emulatorWith(asStock(await makeFirmware()));
  // without a firmware every build has them shut; Korg's build is known a moment later and says why
  await page.waitForFunction(() => document.querySelector("#cee-tab-fx").getAttribute("title") === "Nicht mit Korgs Original-Firmware");
  assert.equal(await shut(page, "mod"), "true");
  for (const tab of ["fx", "mod"]) assert.equal(await page.locator(`#cee-tab-${tab}`).getAttribute("title"), "Nicht mit Korgs Original-Firmware");
  assert.equal(await shut(page, "patcher"), null, "no other entry is touched");
  await page.waitForTimeout(1300);   // the section follows the build on the next tick of the sidebar
  assert.equal(await section(page).isVisible(), false, "the whole section is gone");
  assert.equal(await page.locator("#cee-side-hint").isVisible(), false, "and its warning with it");
  assert.equal(await page.locator("body").evaluate(n => /Es fehlt:|Hacktribe-SysEx|0x52 bis 0x57/.test(n.textContent)), false, "no text about what Korg's build lacks");

  assert.deepEqual(await severeViolations(page), [], "the disabled entries are accessible");
  await page.click("#cee-tab-fx", { force: true });
  assert.equal(await page.locator("#cee-areas [aria-selected='true']").getAttribute("data-tab"), "emu", "a click on a disabled entry opens nothing");
  await page.click("#cee-tab-scripts");
  await page.keyboard.press("ArrowDown");
  assert.equal(await page.locator("#cee-areas [aria-selected='true']").getAttribute("data-tab"), "rescue", "the arrow keys skip the disabled entries");
  assert.deepEqual(page.errors, []);
});

test("Korg's build with BLECH keeps Presets and Modulationen open, Hacktribe's build too, and the section shows for Hacktribe", async () => {
  const blech = await emulatorWith(withBlech(asStock(await makeFirmware())));
  await blech.waitForFunction(() => document.querySelector("#cee-tab-fx").getAttribute("aria-disabled") === "false");
  assert.equal(await shut(blech, "mod"), "false");
  assert.equal(await blech.locator("#cee-tab-fx").getAttribute("title"), null);
  assert.deepEqual(blech.errors, []);

  const hacktribe = await emulatorWith(await makeFirmware());
  await hacktribe.waitForFunction(() => document.querySelector("#cee-tab-fx").getAttribute("aria-disabled") === "false");
  assert.equal(await shut(hacktribe, "mod"), "false");
  await section(hacktribe).waitFor();
  assert.deepEqual(hacktribe.errors, []);
});

test("while Korg's plain build is open the open Presets page gives way to the emulator page", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.setInputFiles("#cee-emu-vsb", h.file("hacktribe.vsb", await makeFirmware()));
  await page.waitForFunction(() => document.querySelector("#cee-tab-fx").getAttribute("aria-disabled") === "false");
  await page.click("#cee-tab-fx");
  assert.equal(await page.locator("#cee-areas [aria-selected='true']").getAttribute("data-tab"), "fx");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", asStock(await makeFirmware())));
  await page.waitForFunction(() => document.querySelector("#cee-areas [aria-selected='true']")?.dataset.tab === "emu");
  assert.equal(await shut(page, "fx"), "true");
});
