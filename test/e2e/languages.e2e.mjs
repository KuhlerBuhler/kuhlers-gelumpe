import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import en from "../../site/app/i18n-en.mjs";
import de from "../../site/app/i18n-de.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

test("a browser in English gets the English app, and the choice in the settings switches it after a fresh start of the page", async () => {
  const context = await h.browser.newContext({ locale: "en-US" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(h.url);
  await page.click("#cee-settings-button");
  await page.locator("#cee-area-settings:not([hidden]) #cee-set-language").waitFor();
  assert.equal(await page.locator("html").getAttribute("lang"), "en");
  assert.equal(await page.locator("#cee-settings-title").textContent(), en["settings.title"]);
  await Promise.all([page.waitForEvent("load"), page.selectOption("#cee-set-language", "de")]);
  await page.waitForFunction(text => document.getElementById("cee-settings-title")?.textContent === text, de["settings.title"]);
  assert.equal(await page.locator("html").getAttribute("lang"), "de");
  assert.deepEqual(errors, []);
  await context.close();
});
