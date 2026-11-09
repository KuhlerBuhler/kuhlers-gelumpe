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

test("French renders device fields, effect metadata, accessible values and the plugin guide", async () => {
  const context = await h.browser.newContext({ locale: "fr-FR" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(`${h.url}#baukasten`);
  await page.locator("#cee-bk-fx-catalog li").first().waitFor();
  assert.match(await page.locator("#cee-bk-fx-catalog li").first().innerText(), /Un écho stéréo court/);
  await page.locator("#cee-bk-fx-catalog li").first().locator(".cee-catalog-open").click();
  await page.locator("#cee-bk-detail-blocks .cee-knob").first().waitFor();
  assert.match(await page.locator("#cee-bk-detail-head").innerText(), /Un écho stéréo court/);
  assert.deepEqual(await page.locator("#cee-bk-detail-blocks .cee-bk-knob-group h5").allTextContents(), ["Mixage et niveaux", "Écho et durée", "Modulation", "Timbre", "EQ"]);
  assert.ok((await page.locator("#cee-bk-detail-map select option:checked").allTextContents()).includes("Pavé tactile enfoncé"));
  assert.doesNotMatch(await page.locator("#cee-bk-detail-map").innerText(), /losgelassen|gedrückt|Pegel/);

  const fields = await page.evaluate(async () => {
    const { control } = await import("/app/fields.mjs");
    const { field } = await import("/src/map/index.mjs");
    const make = (id, value) => control(field(id), () => value, () => {}).node;
    const length = make("pattern.length", 1);
    const pitch = make("part.pitch", 24);
    return {
      name: make("fx.name", "Test").querySelector("label").textContent,
      lengths: [...length.querySelectorAll(".ui-segmented-option")].map(n => n.textContent),
      pitch: pitch.querySelector("input").getAttribute("aria-valuetext"),
      help: make("fx.stage.device", 24).querySelector(".ui-field-help")?.textContent,
    };
  });
  assert.equal(fields.name, "Nom");
  assert.deepEqual(fields.lengths, ["1 mesure", "2 mesures", "3 mesures", "4 mesures"]);
  assert.equal(fields.pitch, "+6 demi-tons");
  assert.match(fields.help, /Un bloc ne se remplace jamais seul/);

  await page.click("#cee-tab-scripts");
  await page.click("#cee-scripts-page-docs");
  await page.locator("#cee-docs-article h2", { hasText: "Plugins pour l’Electribe" }).waitFor();
  assert.equal(await page.locator("#cee-names-body table").count(), 3);
  await page.fill("#cee-docs-search", "sauvegarde");
  assert.ok(await page.locator("#cee-docs-article .cee-doc-section:not([hidden])").count() > 0);
  await page.click("#cee-tab-console");
  await page.fill("#cee-term-input", "help");
  await page.press("#cee-term-input", "Enter");
  await page.locator(".cee-term-line", { hasText: "KORG.screen.get()" }).waitFor();
  assert.match(await page.locator("#cee-term-log").innerText(), /Lire l’écran sous forme de 64 lignes/);
  assert.doesNotMatch(await page.locator("#cee-term-log").innerText(), /eine Taste drücken|Bild aufs Display/);
  assert.deepEqual(errors, []);
  await context.close();
});

test("French release notes are shown online and offline", async () => {
  const context = await h.browser.newContext({ locale: "fr-FR" });
  let releases = [{ tag_name: "v1.4.2", name: "v1.4.2", body: "Foreign release body", published_at: "2026-11-01T12:00:00Z", assets: [] }];
  await context.route("https://api.github.com/**", route => route.fulfill({ contentType: "application/json", body: JSON.stringify(releases) }));
  const page = await context.newPage();
  for (const online of [true, false]) {
    if (!online) releases = [];
    await page.goto(`${h.url}#changelog`);
    await page.locator(".cee-release").first().waitFor();
    assert.match(await page.locator(".cee-release").first().innerText(), /Corrections/);
    assert.match(await page.locator(".cee-release").first().innerText(), /vérification complète/);
    assert.doesNotMatch(await page.locator(".cee-release").first().innerText(), /Foreign release body|Behoben/);
    if (online) await page.goto("about:blank");
  }
  await context.close();
});
