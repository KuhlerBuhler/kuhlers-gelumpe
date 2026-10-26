import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import * as rescue from "../../data/rescue.mjs";
import { t } from "../../site/app/i18n.mjs";

// The data holds keys of the table; the page shows their German text.
const CASES = rescue.CASES.map(c => ({ ...c, label: t(c.label), hint: t(c.hint) }));
const FOLDERS = rescue.FOLDERS.map(f => ({ ...f, title: t(f.title) }));
const DEVICES = Object.fromEntries(Object.entries(rescue.DEVICES).map(([key, d]) => [key, { ...d, title: t(d.title) }]));

// axe is a dev dependency; without it only the checks that axe would add are skipped.
const axe = await import("./support/axe.mjs").catch(() => null);

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

async function open(viewport) {
  const page = await h.page();
  if (viewport) await page.setViewportSize(viewport);
  await page.goto(`${h.url}#rescue`);
  await page.locator("#cee-rescue .cee-rescue").waitFor();
  return page;
}

/** Until Blechy has said everything that follows by itself. */
const settle = page => page.locator("#cee-rescue-answers:not([data-waiting])").waitFor({ state: "attached" });
/** Answer Blechy with the button of that text. */
const answer = (page, text) => page.locator("#cee-rescue-answers button", { hasText: text }).first().click();
/** Every answer button until the flow ends, always the first one: one whole walk through a case. */
async function walk(page) {
  for (let i = 0; i < 12; i++) {
    await settle(page);
    if (!await page.locator("#cee-rescue-answers button").count()) return;
    await page.locator("#cee-rescue-answers button").first().click();
  }
}
const said = async page => { await settle(page); return page.locator("#cee-rescue-chat .cee-rescue-say").last().textContent(); };

test("Rettung is an entry of the sidebar, and the navbar names the page", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await go(page, "rescue");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Rettung");
  assert.equal(await page.locator("#cee-area-rescue").getAttribute("hidden"), null);
  assert.equal(await page.locator("#cee-rescue h1").textContent(), "Rettung");
  assert.deepEqual(page.errors, []);
});

test("Blechy asks first what the device shows; the four cases are the answers", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1);
  assert.match(await said(page), /Was siehst du/);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-blechy").count(), 1, "Blechy speaks");
  assert.deepEqual(await page.locator("#cee-rescue-answers button .cee-rescue-answer").allTextContents(), CASES.map(c => c.label));
  assert.deepEqual(page.errors, []);
});

test("it starts but something is off: EXIT first, then the backup or Korg's file, the folder of the running firmware, SOFTWARE UPDATE", async () => {
  const page = await open();
  await answer(page, CASES[0].label);
  assert.match(await said(page), /EXIT gedrückt halten/);
  await answer(page, "Hat geholfen");
  assert.match(await said(page), /SD-Karte raus/, "EXIT only helps once, so the card comes out next");
  await answer(page, "Ohne Karte läuft sie");
  assert.deepEqual(await page.locator("#cee-rescue-chat .cee-rescue-path").allTextContents(), ["KORG/blechtribe/Plugin/e2sPlugin.all", "KORG/blechtribe/settings.a.bin", "KORG/blechtribe/settings.b.bin"]);
  await answer(page, "Läuft jetzt");
  assert.match(await said(page), /das bleibt jetzt so/);
  await page.click("#cee-rescue-again");
  await answer(page, CASES[0].label);
  await answer(page, "Hilft nicht");
  assert.match(await said(page), /Original-SYSTEM\.VSB/);
  await answer(page, "Ja, hab ich");
  const folders = page.locator("#cee-rescue-answers .cee-rescue-folder");
  assert.deepEqual(await folders.locator(".cee-rescue-answer").allTextContents(), FOLDERS.map(f => f.title));
  assert.equal(await folders.locator("svg.cee-e2-outline").count(), FOLDERS.length, "each with its Electribe drawn in lines, like on the Features page");
  await answer(page, FOLDERS[3].title);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), FOLDERS[3].path);
  await answer(page, "Liegt drauf");
  assert.match(await said(page), /SOFTWARE UPDATE.*FACTORY RESET, das nicht nehmen/s);
  await answer(page, "Läuft wieder");
  assert.match(await said(page), /läuft wieder/);
  await page.click("#cee-rescue-again");
  assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1, "Von vorn starts over");
  await answer(page, CASES[0].label);
  await answer(page, "Hilft nicht");
  await answer(page, "Nein, oder weiß nicht");
  assert.match(await said(page), /Welche Farbe/, "without a backup Korg's own file comes from Korg's page");
  await answer(page, DEVICES.blue.title);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say a", { hasText: "Korgs Download-Seite" }).last().getAttribute("href"), "https://www.korg.com/us/support/download/product/0/367/#software");
  await answer(page, "Hab ich");
  assert.match(await said(page), /Welche Firmware läuft/);
  assert.deepEqual(page.errors, []);
});

test("only answers on the page: no evidence markers, no folds", async () => {
  const page = await open();
  for (const c of CASES) {
    await page.click("#cee-rescue-again");
    await answer(page, c.label);
    await walk(page);
  }
  assert.equal(await page.locator("#cee-rescue-chat .cee-status, #cee-rescue-chat details").count(), 0);
  assert.doesNotMatch(await page.locator("#cee-rescue-chat").textContent(), /gemessen|offline gelesen|Woher wir das wissen/);
});

test("00 goes through the update prompt with Korg's file for the colour, and says where to ask when it does not help", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "zero").label);
  assert.match(await said(page), /warte/, "first wait for the panel update");
  await answer(page, "Es bleibt bei 00");
  assert.match(await said(page), /Welche Farbe/, "the card follows by itself, then the question");
  await answer(page, DEVICES.red.title);
  await answer(page, "Hab ich");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), DEVICES.red.path);
  await answer(page, "Liegt drauf");
  assert.match(await said(page), /ENTER/);
  await answer(page, "Klappt nicht");
  assert.match(await said(page), /GitHub Issue/, "the end follows by itself");
  const issue = new URL(await page.locator("#cee-rescue-chat a", { hasText: "als GitHub Issue" }).last().getAttribute("href"));
  assert.equal(issue.pathname, "/KuhlerBuhler/kuhlers-gelumpe/issues/new");
  assert.equal(issue.searchParams.get("title"), `Rettung: ${CASES.find(c => c.id === "zero").label}`);
  assert.match(issue.searchParams.get("body"), /- Es bleibt bei 00\n- Rot: Electribe Sampler\n- Hab ich\n- Liegt drauf\n- Klappt nicht/, "the answers are in the issue");
  const chat = await page.locator("#cee-rescue-chat").textContent();
  assert.match(chat, /Bedienfeld/);
  assert.doesNotMatch(await page.locator("#cee-rescue-chat .cee-rescue-bubble > p").allTextContents().then(t => t.join(" ")), /Bootloader|JTAG|0x96/, "no jargon up front");
  assert.deepEqual(page.errors, []);
});

test("a device that shows nothing: first the power, then calm words and the official guide", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "silent").label);
  assert.match(await said(page), /Netzteil/);
  await answer(page, "Immer noch nichts");
  await settle(page);
  const chat = await page.locator("#cee-rescue-chat").textContent();
  assert.match(chat, /nichts auf eigene Faust/);
  assert.match(chat, /GitHub Issue/);
  const source = page.locator("#cee-rescue-chat .cee-rescue-source").last();
  assert.match(await source.textContent(), /Quelle: Debrick-Anleitung von Hacktribe/);
  assert.equal(await source.locator("a").getAttribute("href"), "https://github.com/bangcorrupt/hacktribe/wiki/Debrick");
  assert.equal(await page.locator("#cee-rescue-chat img[src$='angry.png']").count(), 0, "Blechy does not get angry");
});

test("the prompt case names the factory path", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "prompt").label);
  await answer(page, DEVICES.red.title);
  await answer(page, "Hab ich");
  const text = await page.locator("#cee-rescue-chat").textContent();
  assert.match(text, /KORG\/electribe sampler\/System\/SYSTEM\.VSB/);
});

test("the start page and the patcher link to the page, and the link works", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.click("#cee-start-rescue");
  await page.locator("#cee-area-rescue:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Rettung");
  await page.click("#cee-tab-patcher");
  assert.equal(await page.getAttribute("#cee-patch-step-4 #cee-patch-rescue", "href"), "#rescue", "the patcher names it where the copy goes onto the device");
  assert.equal(await page.locator("#cee-patch-step-1 #cee-patch-rescue").count(), 0, "not where only a file is loaded");
  assert.equal(await page.locator("#cee-rescue-answers").count(), 1);
});

test("no serious axe violation, wide and on a phone, at the start and deep in a case", { skip: axe ? false : "@axe-core/playwright is not installed" }, async () => {
  for (const viewport of [undefined, { width: 375, height: 800 }]) {
    const page = await open(viewport);
    assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}, the first question`);
    await answer(page, CASES[0].label);
    await answer(page, "Hilft nicht");
    await answer(page, "Ja, hab ich");
    assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}, the folders`);
    assert.deepEqual(page.errors, []);
  }
});

test("on a phone the page does not scroll sideways and nothing sticks out", async () => {
  const page = await open({ width: 375, height: 800 });
  await answer(page, CASES[0].label);
  await answer(page, "Hilft nicht");
  await answer(page, "Ja, hab ich");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(overflow <= 0, `the page scrolls sideways by ${overflow}px`);
  const wide = await page.evaluate(() => [...document.querySelectorAll("#cee-rescue *")].filter(n => n.getBoundingClientRect().right > innerWidth + 1).map(n => n.className || n.tagName));
  assert.deepEqual(wide, []);
  assert.deepEqual(page.errors, []);
});

test("what is only to read follows by itself after a second, a step to do waits for its answer, and back skips what came by itself", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "prompt").label);
  assert.equal(await page.locator("#cee-rescue-answers").getAttribute("data-waiting"), "", "Blechy is still talking");
  const t0 = Date.now();
  await settle(page);
  assert.ok(Date.now() - t0 >= 800, "about a second before the next message");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say").count(), 3, "the explanation and the question, no button in between");
  await page.click("#cee-rescue-back");
  assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1, "back lands on the first question");
  await answer(page, CASES.find(c => c.id === "prompt").label);
  await settle(page);
  await answer(page, DEVICES.red.title);
  await page.locator("#cee-rescue-answers button", { hasText: "Hab ich" }).waitFor();
  assert.match(await said(page), /Lade bei Korg/, "the step to do waits");
  assert.deepEqual(page.errors, []);
});

test("the page text has no em or en dash and no absolute personal path", async () => {
  const page = await open();
  for (const c of CASES) {
    await page.click("#cee-rescue-again");
    await answer(page, c.label);
    await walk(page);
    const text = await page.locator("#cee-rescue").textContent();
    assert.doesNotMatch(text, /[–—]/);
    assert.doesNotMatch(text, /\/Users\//);
  }
});
