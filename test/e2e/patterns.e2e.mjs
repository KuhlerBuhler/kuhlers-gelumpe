import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { setUp } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makePatternFile } from "../helpers.mjs";

let h;
let fake;
before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: h.dir });
});
after(async () => {
  fake.server.closeAllConnections();
  fake.server.close();
  await h.tearDown();
});

test("patterns have no file editor in the navigation, including the old deep link", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.locator("#cee-e2-power").waitFor();
  assert.equal(await page.locator("#cee-tab-patterns").count(), 0);
  await page.evaluate(() => { location.hash = "patterns"; });
  assert.equal(await page.locator("#cee-area-patterns").isVisible(), false);
  assert.equal(await page.locator("input[accept*='.e2s']:visible").count(), 0);
  assert.deepEqual(page.errors, []);
});

test("pattern backups stay in the card folder; the page inserts the card and opens its folder", async () => {
  const original = makePatternFile(3);
  mkdirSync(join(h.dir, "card"));
  const file = join(h.dir, "card", "backup.e2sallpat");
  writeFileSync(file, original);
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.locator("#cee-sd-status", { hasText: "Nicht eingelegt" }).waitFor();
  assert.equal(await page.locator("#cee-emu-card input[type=file]").count(), 0);
  await page.click("#cee-sd-open");
  await page.waitForFunction(() => !document.querySelector("#cee-sd-open").disabled);
  await page.locator("label.ui-switch", { hasText: "Karte eingelegt" }).click();
  await page.waitForFunction(() => document.querySelector("#cee-sd-inserted").checked && !document.querySelector("#cee-sd-inserted").disabled);
  await page.locator("label.ui-switch", { hasText: "Karte eingelegt" }).click();
  await page.waitForFunction(() => !document.querySelector("#cee-sd-inserted").checked && !document.querySelector("#cee-sd-inserted").disabled);
  assert.deepEqual(fake.seen.sdCalls, ["/sd/open", "/sd/insert", "/sd/eject"]);
  assert.deepEqual(new Uint8Array(readFileSync(file)), original);
  assert.deepEqual(page.errors, []);
});

test("the card in the navbar is a switch and one button, nothing about folders or the firmware", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.locator("#cee-sd-status", { hasText: "Nicht eingelegt" }).waitFor();
  await page.locator("label.ui-switch", { hasText: "Karte eingelegt" }).click();
  await page.locator("#cee-sd-status", { hasText: "Eingelegt" }).waitFor();
  const text = await page.locator("#cee-emu-card").innerText();
  assert.doesNotMatch(text, /KORG\/|e2sSample|BLECH übernehmen|CARD FORMAT|IMPORT SAMPLE/);
  assert.equal(await page.locator("#cee-emu-card button:visible").count(), 1, "only SD-Karte öffnen, nothing to copy a folder");
  assert.deepEqual(page.errors, []);
});
