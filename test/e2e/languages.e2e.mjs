import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import en from "../../site/app/i18n-en.mjs";
import de from "../../site/app/i18n-de.mjs";
import { LANGUAGES } from "../../site/app/i18n.mjs";

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

test("the language menu in the navbar lists all languages in their own words, keeps the choice and needs no settings page", async () => {
  const context = await h.browser.newContext({ locale: "de-DE" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(h.url);
  assert.equal(await page.locator("#cee-lang-button").textContent(), "DE");
  await page.click("#cee-lang-button");
  const items = page.locator("#cee-lang-menu [role=menuitemradio]");
  assert.deepEqual(await items.evaluateAll(list => list.map(i => i.dataset.value)), LANGUAGES.map(([id]) => id));
  assert.equal(await page.locator("#cee-lang-menu [aria-checked=true]").getAttribute("data-value"), "de");
  await Promise.all([page.waitForEvent("load"), page.click("#cee-lang-menu [data-value=fr]")]);
  await page.waitForFunction(() => document.documentElement.lang === "fr" && document.getElementById("cee-lang-button")?.textContent === "FR");
  // the choice is the settings' own: a fresh start keeps it
  await page.reload();
  await page.waitForFunction(() => document.getElementById("cee-lang-button")?.textContent === "FR");
  assert.equal(await page.locator("html").getAttribute("lang"), "fr");
  assert.deepEqual(errors, []);
  await context.close();
});

test("anchors land below the navbar, also when it wraps on a phone", async () => {
  for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    const context = await h.browser.newContext({ locale: "de-DE", viewport });
    const page = await context.newPage();
    await page.goto(`${h.url}#scripts`);
    await page.locator("#cee-scripts").waitFor();
    const { top, bottom } = await page.evaluate(() => {
      document.getElementById("cee-plugin-catalog").scrollIntoView({ block: "start", behavior: "instant" });
      return { top: document.getElementById("cee-plugin-catalog").getBoundingClientRect().top, bottom: document.querySelector(".cee-navbar").getBoundingClientRect().bottom };
    });
    assert.ok(top >= bottom, `${viewport.width}: the target at ${top} is under the navbar ending at ${bottom}`);
    await context.close();
  }
});
