import { before, after } from "node:test";
import assert from "node:assert/strict";
import { only } from "./parts.mjs";
import { setUp, go } from "../harness.mjs";
import { makeFirmware } from "../../helpers.mjs";
import * as rescue from "../../../data/rescue.mjs";
import { t } from "../../../site/app/i18n.mjs";
import { sha256 } from "../../../src/firmware.mjs";
import { SYNTH_SHA256 } from "../../../src/patcher.mjs";

// The data holds keys of the table; the page shows their German text.
const CASES = rescue.CASES.map(c => ({ ...c, label: t(c.label), hint: t(c.hint) }));
const FOLDERS = rescue.FOLDERS.map(f => ({ ...f, title: t(f.title) }));
const DEVICES = Object.fromEntries(Object.entries(rescue.DEVICES).map(([key, d]) => [key, { ...d, title: t(d.title) }]));
const label = id => CASES.find(c => c.id === id).label;

// axe is a dev dependency; without it only the checks that axe would add are skipped.
const axe = await import("./axe.mjs").catch(() => null);

export function rescueSuite(index, parts) {
  const test = only(index, parts);
  let h;
  before(async () => { h = await setUp(); h.file("system.vsb", await makeFirmware([])); });
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
  /** Answer Blechy with the button of that text; the first question by typing it and picking the suggestion. */
  async function answer(page, text) {
    if (await page.locator("#cee-rescue-search").count()) {
      await page.fill("#cee-rescue-search", text);
      return page.locator("#cee-rescue-suggest [role=option]", { hasText: text }).first().click();
    }
    return page.locator("#cee-rescue-answers button", { hasText: text }).first().click();
  }
  /** Every answer button until the flow ends, always the first one: one whole walk through a case. */
  async function walk(page) {
    for (let i = 0; i < 14; i++) {
      await settle(page);
      if (!await page.locator("#cee-rescue-answers button").count()) return;
      await page.locator("#cee-rescue-answers button").first().click();
    }
  }
  const said = async page => { await settle(page); return page.locator("#cee-rescue-chat .cee-rescue-say").last().textContent(); };
  const chatText = async page => { await settle(page); return page.locator("#cee-rescue-chat").textContent(); };
  const answersOf = page => page.locator("#cee-rescue-answers button").allTextContents();
  /** Answer by the label alone, where a hint of another answer holds the same word. */
  const pick = (page, text) => page.locator("#cee-rescue-answers button").filter({ has: page.locator(".cee-rescue-answer", { hasText: new RegExp(`^${text}$`) }) }).click();
  const lastPath = page => page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent();

  test("Blechy is an entry of the sidebar, and the navbar names the page", async () => {
    const page = await h.page();
    await page.goto(h.url);
    await go(page, "rescue");
    assert.equal(await page.locator("#cee-nav-title").textContent(), "Blechy");
    assert.equal(await page.locator("#cee-area-rescue").getAttribute("hidden"), null);
    assert.equal(await page.locator("#cee-rescue h1").textContent(), "Blechy");
    assert.deepEqual(page.errors, []);
  });

  test("Blechy greets and asks what is needed; a message field offers a few cases, all of them on request, and a card reader is named up front", async () => {
    const page = await open();
    assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1);
    const first = await said(page);
    assert.match(first, /Moin, ich bin Blechy\. Was brauchst du denn\?/);
    assert.doesNotMatch(first, /kriegen wir das wieder hin/);
    assert.match(first, /Computer mit SD-Kartenleser/);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-blechy").count(), 1, "Blechy speaks");
    assert.equal(await page.locator("#cee-rescue-answers button.btn:not(#cee-rescue-search-all)").count(), 0, "no wall of answer buttons");
    const field = page.locator("#cee-rescue-search");
    assert.equal(await field.getAttribute("role"), "combobox");
    assert.equal(await field.getAttribute("aria-controls"), "cee-rescue-suggest");
    assert.equal(await page.locator("label[for=cee-rescue-search]").textContent(), "Was ist los?");
    assert.deepEqual(await page.locator("#cee-rescue-suggest [role=option] .cee-rescue-answer").allTextContents(), rescue.FIRST_CASES.map(label));
    const above = await page.locator("#cee-rescue-suggest").boundingBox();
    assert.ok(above.y + above.height <= (await field.boundingBox()).y, "the suggestions stand above the field");
    await page.click("#cee-rescue-search-all");
    assert.deepEqual(await page.locator("#cee-rescue-suggest [role=option] .cee-rescue-answer").allTextContents(), CASES.map(c => c.label));
    assert.equal(await page.locator("#cee-rescue-search-all").isVisible(), false);
    assert.deepEqual(page.errors, []);
  });

  test("typing loose words brings up the case above the field, a pick starts its flow", async () => {
    const page = await open();
    await page.fill("#cee-rescue-search", "mein gerät startet nicht");
    const options = page.locator("#cee-rescue-suggest [role=option]");
    assert.equal(await options.first().locator(".cee-rescue-answer").textContent(), label("silent"));
    assert.equal(await page.locator("#cee-rescue-search").getAttribute("aria-expanded"), "true");
    assert.equal(await page.locator("#cee-rescue-search").getAttribute("aria-activedescendant"), "cee-rescue-case-silent");
    assert.match(await page.locator("#cee-rescue-search-status").textContent(), /Passende Themen: \d/);
    await page.fill("#cee-rescue-search", "back to korg firmware");
    assert.equal(await options.first().locator(".cee-rescue-answer").textContent(), label("back"));
    await page.fill("#cee-rescue-search", "qqqq zzzz");
    assert.equal(await options.count(), 0);
    assert.equal(await page.locator("#cee-rescue-search-none").isVisible(), true, "a plain line says nothing fits");
    assert.equal(await page.locator("#cee-rescue-search").getAttribute("aria-expanded"), "false");
    await page.fill("#cee-rescue-search", "bildschirm schwarz");
    await options.first().click();
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-you").last().textContent(), label("silent"));
    await settle(page);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), [DEVICES.red.title, DEVICES.blue.title, "Weiß ich nicht"], "the flow of the case goes on with the colour");
    assert.equal(await page.locator("#cee-rescue-search").count(), 0);
    assert.deepEqual(page.errors, []);
  });

  test("the field works by keyboard: arrows move the active suggestion, Enter picks it, Escape clears", async () => {
    const page = await open();
    const field = page.locator("#cee-rescue-search");
    await field.focus();
    await page.keyboard.press("ArrowDown");
    assert.equal(await field.getAttribute("aria-activedescendant"), `cee-rescue-case-${rescue.FIRST_CASES[0]}`);
    await page.keyboard.press("ArrowUp");
    assert.equal(await field.getAttribute("aria-activedescendant"), `cee-rescue-case-${rescue.FIRST_CASES.at(-1)}`, "up from the first wraps to the last");
    await page.keyboard.type("samples weg");
    assert.equal(await page.locator("#cee-rescue-suggest [aria-selected=true] .cee-rescue-answer").textContent(), label("samples"));
    await page.keyboard.press("Escape");
    assert.equal(await field.inputValue(), "");
    assert.equal(await field.getAttribute("aria-activedescendant"), null);
    await page.keyboard.type("00");
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-you").last().textContent(), label("zero"));
    await settle(page);
    await page.click("#cee-rescue-back");
    assert.equal(await page.evaluate(() => document.activeElement?.id), "cee-rescue-search", "back to the first question puts the cursor in the field");
    assert.equal(await page.locator("#cee-rescue-suggest [data-before] .cee-rescue-answer").textContent(), label("zero"), "the case picked before is offered first");
    if (axe) assert.deepEqual(await axe.severeViolations(page), []);
    assert.deepEqual(page.errors, []);
  });

  test("at 375px the field, the suggestions and a pick fit the width", async () => {
    const page = await open({ width: 375, height: 812 });
    await page.fill("#cee-rescue-search", "display zeigt 00");
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(width <= 375, `no sideways scroll, ${width}`);
    for (const box of [await page.locator("#cee-rescue-search").boundingBox(), await page.locator("#cee-rescue-suggest").boundingBox()]) assert.ok(box.x >= 0 && box.x + box.width <= 375);
    await page.locator("#cee-rescue-suggest [role=option]").first().click();
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-you").last().textContent(), label("zero"));
    assert.deepEqual(page.errors, []);
  });

  test("the colour is asked once, right after the case, with a description, and 'I don't know' explains where to look", async () => {
    const page = await open();
    await answer(page, label("zero"));
    assert.match(await said(page), /Welche Farbe/);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), [DEVICES.red.title, DEVICES.blue.title, "Weiß ich nicht"]);
    assert.match(await page.locator("#cee-rescue-answers").textContent(), /auf dem Gerät steht „electribe sampler“/);
    await answer(page, "Weiß ich nicht");
    assert.match(await said(page), /Schau auf das Gerät/);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), [DEVICES.red.title, DEVICES.blue.title]);
    await answer(page, DEVICES.blue.title);
    assert.match(await said(page), /Bedienfeld/, "the case goes on right after the colour");
    assert.deepEqual(page.errors, []);
  });

  test("it starts but something is off: EXIT first, then the backup or Korg's file, the folder of the running firmware, SOFTWARE UPDATE", async () => {
    const page = await open();
    await answer(page, label("starts"));
    await answer(page, DEVICES.red.title);
    assert.match(await said(page), /EXIT gedrückt halten/);
    await answer(page, "Hat geholfen");
    assert.match(await said(page), /SD-Karte raus/, "EXIT only helps once, so the card comes out next");
    await answer(page, "Ohne Karte läuft sie");
    assert.deepEqual(await page.locator("#cee-rescue-chat .cee-rescue-path").allTextContents(), ["KORG/blechtribe/Plugin/e2sPlugin.all", "KORG/blechtribe/settings.a.bin", "KORG/blechtribe/settings.b.bin"]);
    await answer(page, "Läuft jetzt");
    assert.match(await said(page), /das bleibt jetzt so/);
    await page.click("#cee-rescue-again");
    await answer(page, label("starts"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Hilft nicht");
    const backup = await chatText(page);
    assert.match(backup, /Original-SYSTEM\.VSB/);
    assert.match(backup, /Patterns im Gerät blieben im Emulator erhalten/, "what happens to patterns is said before any write");
    assert.equal(await page.locator("#cee-rescue-chat a", { hasText: "Pattern-Sicherung in der App" }).last().getAttribute("href"), "#patterns", "and a real backup is offered");
    await answer(page, "Ja, hab ich");
    assert.match(await said(page), /Welche Datei hast du zuletzt aufgespielt/);
    // by its label alone: the hint of Hacktribe names BLECHTRIBE too
    await pick(page, "BLECHTRIBE");
    assert.match(await said(page), /Was läuft gerade/);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), ["Korgs Original", "Hacktribe", "BLECHTRIBE", "Weiß ich nicht"], "user terms, no product names of colours again");
    assert.match(await page.locator("#cee-rescue-answers [data-known]").textContent(), /BLECHTRIBE/, "the file put on last is marked");
    assert.equal(await page.locator("#cee-rescue-answers .cee-rescue-folder").count(), 0);
    await answer(page, "BLECHTRIBE");
    assert.equal(await lastPath(page), FOLDERS[3].path);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-tree").count(), 1, "the path is shown as folders inside folders");
    assert.match(await said(page), /nach der Firmware, die jetzt auf der Electribe läuft, nicht nach der, die du haben willst/);
    const [firstAnswer, secondAnswer] = await answersOf(page);
    assert.match(firstAnswer, /^Zeig mir deine SD-Karte/, "the look at the card comes first");
    assert.match(secondAnswer, /^Habe ich selbst geprüft/, "'it is on the card' is not the same as the check");
    await answer(page, "Habe ich selbst geprüft");
    assert.match(await said(page), /SOFTWARE UPDATE.*FACTORY RESET, das nicht nehmen/s);
    await answer(page, "Läuft wieder");
    assert.match(await said(page), /läuft wieder/);
    await page.click("#cee-rescue-again");
    assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1, "Von vorn starts over");
    await answer(page, label("starts"));
    await answer(page, DEVICES.blue.title);
    await answer(page, "Hilft nicht");
    await answer(page, "Nein, oder weiß nicht");
    assert.match(await said(page), /Was läuft gerade/, "without a backup what runs comes first, the download only after that");
    await answer(page, "BLECHTRIBE");
    assert.match(await said(page), /Haken „auch Hacktribe“/, "a blue asks about Hacktribe, never about the colour again");
    await answer(page, "Nein, ohne Hacktribe");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say a", { hasText: "Korgs Download-Seite" }).last().getAttribute("href"), "https://www.korg.com/us/support/download/software/0/367/2578/", "the exact page of the file");
    assert.match(await said(page), /electribe_system_v202\.zip/);
    await answer(page, "Hab ich");
    assert.equal(await lastPath(page), FOLDERS[3].path, "what runs was said once, the folder follows without asking again");
    assert.deepEqual(page.errors, []);
  });

  test("only answers on the page: no evidence markers, no folds", async () => {
    const page = await open();
    for (const c of CASES) {
      await page.click("#cee-rescue-again");
      await answer(page, c.label);
      await walk(page);
    }
    assert.equal(await page.locator("#cee-rescue-chat .cee-state, #cee-rescue-chat .cee-status, #cee-rescue-chat details").count(), 0);
    assert.doesNotMatch(await page.locator("#cee-rescue-chat").textContent(), /gemessen|offline gelesen|Woher wir das wissen/);
  });

  test("00 goes through the update prompt with Korg's file for the colour, then the card is looked at once more, and where to ask", async () => {
    const page = await open();
    await answer(page, label("zero"));
    await answer(page, DEVICES.red.title);
    assert.match(await said(page), /warte/, "first wait for the panel update");
    await answer(page, "Es bleibt bei 00");
    assert.match(await chatText(page), /Original-Firmware auf der SD-Karte/, "the card follows by itself, and the colour is not asked again");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say", { hasText: "Welche Farbe" }).count(), 1);
    await answer(page, "Hab ich");
    assert.equal(await lastPath(page), DEVICES.red.path);
    await answer(page, "Habe ich selbst geprüft");
    assert.match(await said(page), /ENTER/);
    await answer(page, "Klappt nicht");
    await settle(page);
    assert.equal(await page.locator("#cee-rescue-answers #cee-rescue-case-card-pick").count(), 1, "a first failure goes back to the card check");
    await answer(page, "Habe ich selbst geprüft");
    await answer(page, "Klappt nicht");
    assert.match(await said(page), /Was zeigt die Electribe jetzt/, "the second failure asks what the display shows");
    await answer(page, "Es bleibt bei 00");
    await settle(page);
    assert.match(await chatText(page), /Flachbandkabel/);
    assert.match(await chatText(page), /GitHub Issue/, "the end follows by itself");
    const issue = new URL(await page.locator("#cee-rescue-chat a", { hasText: "als GitHub Issue" }).last().getAttribute("href"));
    assert.equal(issue.pathname, "/KuhlerBuhler/kuhlers-gelumpe/issues/new");
    assert.equal(issue.searchParams.get("title"), `Blechy: ${label("zero")}`);
    assert.match(issue.searchParams.get("body"), /- Rot: Electribe Sampler\n- Es bleibt bei 00\n- Hab ich\n- Habe ich selbst geprüft\n- Klappt nicht/, "the answers are in the issue");
    const chat = await page.locator("#cee-rescue-chat").textContent();
    assert.match(chat, /Bedienfeld/);
    assert.doesNotMatch(await page.locator("#cee-rescue-chat .cee-rescue-bubble > p").allTextContents().then(t => t.join(" ")), /Bootloader|JTAG|0x96/, "no jargon up front");
    assert.deepEqual(page.errors, []);
  });

  test("a device that shows nothing: first the power, then the exit with EXIT, then calm words, the contact and the official guide", async () => {
    const page = await open();
    await answer(page, label("silent"));
    await answer(page, DEVICES.red.title);
    const first = await said(page);
    assert.match(first, /Netzteil/);
    assert.match(first, /EXIT gedrückt halten/);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), ["Jetzt geht sie", "Mit EXIT startet sie", "Jetzt steht da 00", "Jetzt fragt sie nach einem Update", "Immer noch nichts"]);
    await answer(page, "Immer noch nichts");
    await settle(page);
    const chat = await page.locator("#cee-rescue-chat").textContent();
    assert.match(chat, /Foto vom Display/);
    assert.doesNotMatch(chat, /nichts auf eigene Faust/);
    assert.match(chat, /GitHub Issue/);
    const source = page.locator("#cee-rescue-chat .cee-rescue-source").last();
    assert.match(await source.textContent(), /Quelle: Debrick-Anleitung von Hacktribe/);
    assert.equal(await source.locator("a").getAttribute("href"), "https://github.com/bangcorrupt/hacktribe/wiki/Debrick");
    assert.equal(await page.locator("#cee-rescue-chat img[src$='angry.png']").count(), 0, "Blechy does not get angry");
  });

  test("'it runs' after the power or after EXIT does not claim a file was put back", async () => {
    const page = await open();
    await answer(page, label("silent"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Jetzt geht sie");
    const chat = await chatText(page);
    assert.match(chat, /Super, sie läuft wieder!/);
    assert.doesNotMatch(chat, /zurückgespielt/);
    await page.click("#cee-rescue-again");
    await answer(page, label("silent"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Mit EXIT startet sie");
    assert.match(await chatText(page), /es liegt an BLECHTRIBE/, "EXIT working leads on to the cause");
    assert.doesNotMatch(await chatText(page), /zurückgespielt/);
  });

  test("the prompt case names the factory path as folders, and no update question has its own answer", async () => {
    const page = await open();
    await answer(page, label("prompt"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Hab ich");
    const text = await page.locator("#cee-rescue-chat").textContent();
    assert.match(text, /KORG\/electribe sampler\/System\/SYSTEM\.VSB/);
    assert.match(text, /Beim Einschalten sucht sie immer in diesem Ordner/);
    await answer(page, "Habe ich selbst geprüft");
    await answer(page, "Es kommt keine Update-Frage");
    assert.match(await chatText(page), /Hacktribe und BLECHTRIBE fragen beim Einschalten fast nie/);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), ["Sie startet bis ins Menü", "Sie startet nicht bis ins Menü"]);
    await answer(page, "Sie startet nicht bis ins Menü");
    assert.match(await chatText(page), /EXIT gedrückt halten/, "the exit follows");
    assert.deepEqual(page.errors, []);
  });

  test("the start page and the patcher link to the page, and the link works", async () => {
    const page = await h.page();
    await page.goto(h.url);
    await page.click("#cee-start-rescue");
    await page.locator("#cee-area-rescue:not([hidden])").waitFor();
    assert.equal(await page.locator("#cee-nav-title").textContent(), "Blechy");
    await page.click("#cee-tab-patcher");
    assert.equal(await page.getAttribute("#cee-patch-step-4 #cee-patch-rescue", "href"), "#rescue", "the patcher names it where the copy goes onto the device");
    assert.equal(await page.locator("#cee-patch-step-1 #cee-patch-rescue").count(), 0, "not where only a file is loaded");
    assert.equal(await page.locator("#cee-rescue-answers").count(), 1);
  });

  test("no serious axe violation, wide and on a phone, at the start and deep in a case", { skip: axe ? false : "@axe-core/playwright is not installed" }, async () => {
    for (const viewport of [undefined, { width: 375, height: 800 }]) {
      const page = await open(viewport);
      assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}, the first question`);
      await answer(page, label("starts"));
      await answer(page, DEVICES.red.title);
      await answer(page, "Hilft nicht");
      await answer(page, "Ja, hab ich");
      assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}, what runs`);
      await answer(page, "BLECHTRIBE");
      assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}, the folder as a tree`);
      assert.deepEqual(page.errors, []);
    }
  });

  test("on a phone the page does not scroll sideways, nothing sticks out, and a path breaks only at a slash", async () => {
    const page = await open({ width: 375, height: 800 });
    await answer(page, label("starts"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Hilft nicht");
    await answer(page, "Ja, hab ich");
    await answer(page, "BLECHTRIBE");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 0, `the page scrolls sideways by ${overflow}px`);
    const wide = await page.evaluate(() => [...document.querySelectorAll("#cee-rescue *")].filter(n => n.getBoundingClientRect().right > innerWidth + 1).map(n => n.className || n.tagName));
    assert.deepEqual(wide, []);
    const broken = await page.evaluate(() => [...document.querySelectorAll("#cee-rescue .cee-rescue-path")].map(n => {
      const range = document.createRange();
      const words = [];
      for (const part of n.childNodes) {
        if (part.nodeType !== 3 || part.textContent === "/") continue;
        range.selectNodeContents(part);
        if (new Set([...range.getClientRects()].map(r => Math.round(r.top))).size > 1) words.push(part.textContent);
      }
      return words;
    }).flat());
    assert.deepEqual(broken, [], "no folder or file name is split over two lines");
    assert.deepEqual(page.errors, []);
  });

  test("what is only to read follows by itself after a second, a step to do waits for its answer, and back skips what came by itself", async () => {
    const page = await open();
    await answer(page, label("prompt"));
    await settle(page);
    await answer(page, DEVICES.red.title);
    assert.equal(await page.locator("#cee-rescue-answers").getAttribute("data-waiting"), "", "Blechy is still talking");
    const t0 = Date.now();
    await settle(page);
    assert.ok(Date.now() - t0 >= 800, "about a second before the next message");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say").count(), 4, "the case, the colour, the explanation and the download, no button in between");
    await page.click("#cee-rescue-back");
    assert.equal(await page.locator("#cee-rescue-chat > li").count() > 2, true, "back lands on the colour question");
    assert.match(await said(page), /Welche Farbe/);
    assert.equal(await page.locator("#cee-rescue-answers [data-before]").count(), 1, "the answer that was chosen is marked");
    assert.match(await page.locator("#cee-rescue-answers [data-before]").textContent(), /Rot/);
    await answer(page, DEVICES.red.title);
    await page.locator("#cee-rescue-answers button", { hasText: "Hab ich" }).waitFor();
    assert.match(await said(page), /Lade bei Korg/, "the step to do waits");
    assert.deepEqual(page.errors, []);
  });

  test("back takes an answer out again: another colour on the same way asks what it needs for that colour", async () => {
    const page = await open();
    await answer(page, label("invalid"));
    await answer(page, DEVICES.blue.title);
    await answer(page, "Beim Einschalten");
    assert.match(await said(page), /jemals Hacktribe/);
    await page.click("#cee-rescue-back");
    await page.click("#cee-rescue-back");
    assert.match(await said(page), /Welche Farbe/);
    await answer(page, DEVICES.red.title);
    await answer(page, "Beim Einschalten");
    assert.match(await said(page), /Lade bei Korg das Firmware-Update für die Electribe Sampler/, "a red is not asked about Hacktribe");
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

  /** The page with Web MIDI that lists these ports (granted, no Electribe answers) and the given system in the user agent. */
  async function withPorts(names, agent) {
    const page = await h.page();
    await page.addInitScript(([names, agent]) => {
      const port = name => ({ name, manufacturer: "KORG INC.", state: "connected", connection: "closed" });
      const access = new EventTarget();
      access.inputs = new Map(names.map((n, i) => [`i${i}`, port(n)]));
      access.outputs = new Map(names.map((n, i) => [`o${i}`, port(n)]));
      navigator.requestMIDIAccess = async () => access;
      const query = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = async d => (d.name === "midi" ? { state: "granted" } : query(d));
      if (agent) Object.defineProperty(navigator, "userAgent", { get: () => agent });
    }, [names, agent]);
    await page.goto(`${h.url}#rescue`);
    await page.locator("#cee-rescue .cee-rescue").waitFor();
    return page;
  }
  const notFound = async page => { await answer(page, label("app")); await answer(page, "Die App findet meine Electribe nicht"); return said(page); };

  test("Invalid File at the start on a blue that once had Hacktribe: Korg's Sampler file into the Sampler's folder", async () => {
    const page = await open();
    await answer(page, label("invalid"));
    await answer(page, DEVICES.blue.title);
    assert.match(await said(page), /Wann kommt die Meldung/);
    assert.match(await chatText(page), /neu auf die Karte zu kopieren/, "the cheap first step is named");
    await answer(page, "Beim Einschalten, nach press ENTER");
    assert.match(await said(page), /jemals Hacktribe/);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say", { hasText: "Welche Farbe" }).count(), 1, "the colour is not asked again");
    await answer(page, "Ja, Hacktribe war mal drauf");
    assert.match(await said(page), /Electribe Sampler/, "the download of the red's firmware follows by itself");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say a", { hasText: "Korgs Download-Seite" }).last().getAttribute("href"), "https://www.korg.com/us/support/download/software/0/368/2579/");
    await answer(page, "Hab ich");
    assert.equal(await lastPath(page), "KORG/electribe sampler/System/SYSTEM.VSB");
    assert.match(await page.locator("#cee-rescue-chat").textContent(), /SYSTEM \(1\)\.VSB/, "the card step names the file name");
    assert.deepEqual(page.errors, []);
  });

  test("Invalid File in the menu with Hacktribe on the blue leads to the file step, not to a guess, and asks nothing twice", async () => {
    const page = await open();
    await answer(page, label("invalid"));
    await answer(page, DEVICES.blue.title);
    await answer(page, "Im Menü bei SOFTWARE UPDATE");
    await answer(page, "Korgs Original-Firmware");
    assert.match(await said(page), /Was läuft gerade/);
    await answer(page, "Hacktribe");
    await settle(page);
    const chat = await page.locator("#cee-rescue-chat").textContent();
    assert.match(chat, /angepassten Form/);
    assert.doesNotMatch(chat, /zwei Bytes|Sampler-Code/, "no byte talk");
    assert.equal(await page.locator("#cee-rescue-input").count(), 1);
    assert.deepEqual(page.errors, []);
  });

  test("the file step is a drop zone like the patcher's, names the file it takes, and has no 'saved' answer without a file", async () => {
    const page = await open();
    await answer(page, label("back"));
    await answer(page, DEVICES.blue.title);
    await settle(page);
    assert.match(await chatText(page), /Pattern-Sicherung in der App/);
    await answer(page, "Hacktribe");
    await settle(page);
    const zone = page.locator("#cee-rescue-answers label.ui-dropzone");
    assert.equal(await zone.count(), 1, "a drop zone, not a button");
    assert.match(await zone.locator(".ui-dropzone-title").textContent(), /Korgs SYSTEM\.VSB für die blaue hierher ziehen oder auswählen/);
    assert.match(await zone.locator(".ui-dropzone-hint").textContent(), /electribe_system_v202\.zip/);
    assert.equal(await zone.locator("input[type=file]").getAttribute("accept"), ".VSB,.vsb");
    assert.equal(await page.locator("#cee-rescue-answers button").count(), 0, "no answer that goes on without a file");
    assert.equal(await page.locator("#cee-rescue-back").isEnabled(), true);
    assert.deepEqual(page.errors, []);
  });

  test("back to Korg's original on the blue with Hacktribe: Korg's file in, the same file with the Sampler head out, then the folder", async () => {
    const korg = await makeFirmware([]);
    korg.set([0x45, 0x32, 0], 0x10);
    korg[0x2e] = 0x23;
    const page = await h.page();
    await page.route(/\/src\/patcher\.mjs$/, async route => {
      const res = await route.fetch();
      await route.fulfill({ response: res, body: (await res.text()).replace(SYNTH_SHA256, await sha256(korg)) });
    });
    await page.goto(`${h.url}#rescue`);
    await page.locator("#cee-rescue .cee-rescue").waitFor();
    await answer(page, label("back"));
    await answer(page, DEVICES.blue.title);
    await settle(page);
    assert.match(await page.locator("#cee-rescue-chat").textContent(), /KORG\/blechtribe\//);
    await settle(page);
    await answer(page, "Hacktribe");
    await settle(page);
    const bytes = await h.download(page, () => page.setInputFiles("#cee-rescue-input", h.file("korg-blue.VSB", korg)));
    assert.deepEqual([bytes[0x12], bytes[0x2e], bytes.length], [0x53, 0x24, korg.length]);
    assert.equal(bytes.filter((b, i) => b !== korg[i]).length, 2, "only the head differs");
    await settle(page);
    assert.match(await chatText(page), /Korgs SYSTEM\.VSB ausgewählt/, "the chosen file is said, the talk goes on by itself");
    assert.equal(await lastPath(page), FOLDERS[2].path, "what runs was said before, so the folder follows without asking");
    assert.deepEqual(page.errors, []);
  });

  test("back to Korg's original: any other file is refused with a toast and nothing is saved", async () => {
    const page = await open();
    await answer(page, label("back"));
    await settle(page);
    await answer(page, DEVICES.blue.title);
    await settle(page);
    await answer(page, "Hacktribe");
    await settle(page);
    await page.setInputFiles("#cee-rescue-input", h.file("other.VSB", new Uint8Array(100)));
    await page.locator("#app-toasts .cee-toast", { hasText: "nicht die Größe" }).waitFor();
    assert.equal(await page.locator("#cee-rescue-answers label.ui-dropzone[data-invalid]").count(), 1, "the drop zone says it was not this file");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say", { hasText: "Super" }).count(), 0, "nothing was done, nothing is celebrated");
    assert.deepEqual(page.errors.filter(e => !/Failed to load resource/.test(e)), []);
  });

  test("back to Korg's original on a red: what runs, then the download, then the folder; Korg's own firmware needs nothing", async () => {
    const page = await open();
    await answer(page, label("back"));
    await answer(page, DEVICES.red.title);
    await settle(page);
    await settle(page);
    assert.match(await said(page), /Was läuft gerade/);
    await answer(page, "Korgs Original");
    assert.match(await said(page), /schon Korgs Original/);
    await page.click("#cee-rescue-back");
    await settle(page);
    await answer(page, "Weiß ich nicht");
    assert.match(await said(page), /Lade bei Korg das Firmware-Update für die Electribe Sampler/);
    await answer(page, "Hab ich");
    await settle(page);
    assert.deepEqual(await page.locator("#cee-rescue-chat .cee-rescue-treebox .cee-rescue-path").allTextContents().then(p => p.slice(-3)), [DEVICES.red.path, FOLDERS[2].path, FOLDERS[3].path], "not known what runs: the file in every folder");
    assert.match(await chatText(page), /sicherheitshalber in alle drei Ordner/);
    assert.deepEqual(page.errors, []);
  });

  test("No File in the menu: name, no renamed folder, the patcher's Electribe, then what runs, then the folder as a tree", async () => {
    const page = await open();
    await answer(page, label("nofile"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Im Menü bei SOFTWARE UPDATE");
    await settle(page);
    const chat = await page.locator("#cee-rescue-chat").textContent();
    for (const words of [/SYSTEM \(1\)\.VSB/, /Benenn keinen Ordner um/, /richtige Electribe gewählt/]) assert.match(chat, words);
    assert.match(await said(page), /Welche Datei hast du zuletzt aufgespielt/);
    assert.equal(await page.locator("#cee-rescue-answers [data-known]").count(), 0, "nothing connected, nothing patched: nothing is marked");
    await pick(page, "Korgs Update-Datei");
    assert.match(await said(page), /Welche Firmware läuft jetzt/);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), ["Korgs Original", "Hacktribe", "BLECHTRIBE", "Weiß ich nicht"]);
    assert.match(await page.locator("#cee-rescue-answers [data-known]").textContent(), /Korgs Original.*Passt zu deiner letzten Datei/, "only the answer about the last file is marked");
    await answer(page, "Hacktribe");
    assert.equal(await lastPath(page), FOLDERS[2].path);
    assert.deepEqual(await page.locator("#cee-rescue-chat .cee-rescue-tree li > span").allTextContents().then(s => s.slice(-4)), ["KORG", "hacktribe", "System", "SYSTEM.VSB"]);
    await answer(page, "Habe ich selbst geprüft");
    await answer(page, "Das Update ist durchgelaufen");
    assert.match(await said(page), /Update ist drauf/);
    assert.deepEqual(page.errors, []);
  });

  test("No File twice: the second time Blechy offers the look at the card again, the third time the contact", async () => {
    const page = await open();
    await answer(page, label("nofile"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Im Menü bei SOFTWARE UPDATE");
    await settle(page);
    await pick(page, "BLECHTRIBE");
    await settle(page);
    await answer(page, "BLECHTRIBE");
    await answer(page, "Habe ich selbst geprüft");
    await answer(page, "Wieder No File");
    await settle(page);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say", { hasText: "Welche Firmware läuft jetzt" }).count(), 1, "what runs is not asked again");
    assert.equal(await page.locator("#cee-rescue-answers #cee-rescue-case-card-pick").count(), 1, "the look at the card is offered again");
    await answer(page, "Habe ich selbst geprüft");
    await answer(page, "Wieder No File");
    assert.match(await chatText(page), /GitHub Issue/);
    assert.deepEqual(page.errors, []);
  });

  test("not known what runs: 'Weiß ich nicht' puts the file in every folder and still goes on", async () => {
    const page = await open();
    await answer(page, label("nofile"));
    await answer(page, DEVICES.blue.title);
    await answer(page, "Im Menü bei SOFTWARE UPDATE");
    await settle(page);
    await answer(page, "Weiß ich nicht");
    await settle(page);
    assert.deepEqual(await page.locator("#cee-rescue-chat .cee-rescue-treebox .cee-rescue-path").allTextContents().then(p => p.slice(-3)), [DEVICES.blue.path, FOLDERS[2].path, FOLDERS[3].path]);
    assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), ["Habe ich selbst geprüft"]);
    assert.deepEqual(page.errors, []);
  });

  test("the app does not find the Electribe: Korg's jack names on Windows lead to removing the driver", async () => {
    const page = await withPorts(["electribe2 sampler 1 PAD/KNOB", "electribe2 sampler 1 SOUND"], "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0");
    assert.match(await notFound(page), /Geräte-Manager/);
    assert.deepEqual(page.errors, []);
  });

  test("the same jack names on a Mac: no cause is claimed, the report goes to the team", async () => {
    const page = await withPorts(["electribe2 sampler PAD/KNOB", "electribe2 sampler SOUND"], "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130.0");
    await notFound(page);
    await settle(page);
    const chat = await page.locator("#cee-rescue-chat").textContent();
    assert.match(chat, /wissen wir noch nicht/);
    assert.doesNotMatch(chat, /Geräte-Manager/);
    assert.match(chat, /MIDI-Bericht/);
    assert.equal(await page.locator("#cee-rescue-chat a", { hasText: "Einstellungen" }).last().getAttribute("target"), null, "the settings open in the app");
    assert.deepEqual(page.errors, []);
  });

  test("an Electribe on MIDI while the app is in the emulator mode: choose Echtes Gerät", async () => {
    const page = await withPorts(["Electribe 3"]);
    assert.match(await notFound(page), /Echtes Gerät/);
    assert.deepEqual(page.errors, []);
  });

  test("without MIDI to read, Blechy asks for the mode himself", async () => {
    const page = await open();
    assert.match(await notFound(page), /Emulator oder Echtes Gerät/);
    await answer(page, "Echtes Gerät");
    assert.match(await said(page), /MIDI-Bericht/);
    assert.deepEqual(page.errors, []);
  });

  test("old patterns after an export: WRITE first, the folder KORG/blechtribe, the date of the device", async () => {
    const page = await open();
    await answer(page, label("app"));
    await answer(page, "Export oder Import zeigt alte Patterns");
    const text = await said(page);
    assert.match(text, /erst WRITE, dann EXPORT PATTERN/);
    assert.match(text, /01\.01\.2014/);
    assert.match(text, /KORG\/electribe/);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), "KORG/blechtribe/");
    assert.deepEqual(page.errors, []);
  });

  test("a red test in the patcher: what each kind means, the advice of a normal firmware with Korg's and Hacktribe's links", async () => {
    const page = await open();
    await answer(page, label("app"));
    await answer(page, "Der Test im Patcher wird rot oder läuft nicht");
    assert.deepEqual(await page.locator("#cee-rescue-answers button .cee-rescue-answer").allTextContents(),
      ["Das Patchen selbst klappt nicht", "Kopf, DSP-Programm oder Startphase", "Start oder ein Rettungsweg", "Der Test einer Funktion", "Der Test läuft gar nicht"]);
    await answer(page, "Das Patchen selbst klappt nicht");
    await settle(page);
    const chat = await page.locator("#cee-rescue-chat").textContent();
    assert.match(chat, /andere Bytes|andere, hört er auf/);
    assert.match(chat, /Nimm als Eingabe eine normale Firmware/);
    const links = await page.locator("#cee-rescue-chat a").evaluateAll(list => list.map(a => a.href));
    for (const l of [rescue.LINKS.hacktribe, rescue.LINKS.korgRed, rescue.LINKS.korgBlue]) assert.ok(links.includes(l), l);
    await answer(page, "Mit normaler Firmware immer noch rot");
    await settle(page);
    assert.match(await page.locator("#cee-rescue-chat").textContent(), /Screenshot vom Patcher[\s\S]*Kuhler Buhler/);
    assert.deepEqual(page.errors, []);
  });

  test("any error toast carries Frag Blechy: the page opens with the error quoted and asks what in the app sticks", async () => {
    const page = await h.page();
    await page.goto(h.url);
    await page.evaluate(() => import(new URL("app/toast.mjs", document.baseURI).href).then(m => m.toast("Etwas ist schiefgegangen.", "error")));
    const box = page.locator("#app-toasts .cee-toast", { hasText: "Etwas ist schiefgegangen." });
    assert.equal(await box.locator(".cee-toast-help").textContent(), "Frag Blechy");
    await box.locator(".cee-toast-help").click();
    await page.locator("#cee-rescue-quote").waitFor();
    await box.waitFor({ state: "detached" });
    assert.equal(await page.locator("#cee-rescue-quote").textContent(), "Etwas ist schiefgegangen.");
    await settle(page);
    assert.equal(await page.locator("#cee-rescue-answers button", { hasText: "Der Test im Patcher wird rot oder läuft nicht" }).count(), 1, "the app's question follows");
    assert.equal(await page.locator("#app-toasts .cee-toast-help").count(), 0);
    const info = await page.evaluate(() => import(new URL("app/toast.mjs", document.baseURI).href).then(m => { m.toast("Nur eine Info.", "info"); return document.querySelectorAll("#app-toasts .cee-toast-help").length; }));
    assert.equal(info, 0, "only errors ask Blechy");
    assert.deepEqual(page.errors, []);
  });

  test("a red full check in the browser: the flash.bin of older apps, then the log", async () => {
    const page = await open();
    await answer(page, label("app"));
    await answer(page, "Der Test im Patcher wird rot oder läuft nicht");
    await answer(page, "Der Test einer Funktion");
    await answer(page, "Mit normaler Firmware immer noch rot");
    assert.match(await said(page), /Ab Version 1\.3\.7/, "the browser has no app version, so both cases are named");
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), "~/.gelumpe/flash/flash.bin");
    await answer(page, "Immer noch rot");
    await settle(page);
    assert.match(await page.locator("#cee-rescue-chat").textContent(), /~\/\.gelumpe\/emu\.log/);
    assert.deepEqual(page.errors, []);
  });

  test("a connected BLECHTRIBE is named and taken as what runs: the question is not asked, the folder follows", async () => {
    const page = await h.page({ device: true });
    await page.goto(`${h.url}?card#emu`);
    await page.evaluate(() => window.__ceeStubReady);
    await go(page, "device");
    await page.click("#cee-connect");
    await page.locator("#cee-nav-state #cee-disconnect").waitFor();
    await go(page, "rescue");
    await page.click("#cee-rescue-again");
    await answer(page, label("starts"));
    await answer(page, "Rot");
    await answer(page, "Hilft nicht");
    await answer(page, "Ja, hab ich");
    await page.locator("#cee-rescue-chat .cee-rescue-path").last().waitFor();
    await settle(page);
    const chat = await page.locator("#cee-rescue-chat").textContent();
    assert.match(chat, /läuft BLECHTRIBE/);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-you", { hasText: "BLECHTRIBE" }).count(), 1, "the app answered for the device, nobody clicked");
    assert.equal(await lastPath(page), FOLDERS[3].path);
    await page.click("#cee-rescue-back");
    assert.match(await said(page), /Was läuft gerade/, "back brings the question, with the answer marked as the app's");
    assert.equal(await page.locator("#cee-rescue-answers [data-known] .cee-rescue-known").first().textContent(), "Sagt die App");
    assert.deepEqual(page.errors, []);
  });

  test("samples: 'it starts but something is off' leads there, a case asks for Hacktribe, then BLECHTRIBE without Hacktribe", async () => {
    const page = await open();
    await answer(page, label("starts"));
    await answer(page, DEVICES.red.title);
    await answer(page, "Meine Samples fehlen oder klingen falsch");
    assert.match(await chatText(page), /Hacktribe bringt eigene Klänge mit/);
    await answer(page, "Nein, nie");
    assert.match(await chatText(page), /Dann liegt es vermutlich nicht an Hacktribe/);
    assert.match(await said(page), /EXIT gedrückt halten/, "without Hacktribe the firmware itself is looked at first");

    await page.click("#cee-rescue-again");
    await answer(page, label("samples"));
    await answer(page, DEVICES.red.title);
    assert.match(await chatText(page), /Hacktribe bringt eigene Klänge mit/);
    await answer(page, "Ja, Hacktribe ist oder war drauf");
    assert.match(await said(page), /Datei namens e2sSample\.all/);
    await answer(page, "Ja, ich hab die Datei");
    await settle(page);
    assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), "KORG/blechtribe/Sample/e2sSample.all");
    assert.match(await said(page), /Was läuft gerade/, "what runs, asked once");
    await answer(page, "Hacktribe");
    assert.match(await said(page), /Original.*BLECH/s, "the way back goes through Korg's original");
    await answer(page, "Die Datei ist fertig");
    assert.equal(await lastPath(page), FOLDERS[2].path, "the folder of the Hacktribe that runs, without asking again");
    await answer(page, "Habe ich selbst geprüft");
    await answer(page, "Läuft wieder");
    assert.match(await said(page), /Update ist drauf/, "BLECHTRIBE was put on, not Korg's original");
    assert.deepEqual(page.errors, []);

    await page.click("#cee-rescue-again");
    await answer(page, label("samples"));
    await answer(page, DEVICES.blue.title);
    await answer(page, "Ja, Hacktribe ist oder war drauf");
    await answer(page, "Nein, ich habe nichts gesichert");
    await settle(page);
    assert.match(await page.locator("#cee-rescue-chat").textContent(), /Ohne Kopie kann die App sie nicht zurückholen/);
    await settle(page);
    await answer(page, "Hacktribe");
    assert.match(await chatText(page), /Läuft nur Hacktribe auf deiner blauen, geht es in zwei Schritten/);
    await settle(page);
    assert.equal(await page.locator("#cee-rescue-input").count(), 1, "then Korg's file is made for the blue with Hacktribe");
    assert.deepEqual(page.errors, []);
  });

  test("No File: the file put on last comes first and marks the folder, and the MENU step shows the drawn keys and Korg's button", async () => {
    const page = await open({ width: 390, height: 844 });
    await answer(page, label("nofile"));
    await settle(page);
    await answer(page, DEVICES.red.title);
    await settle(page);
    await answer(page, t("rescue.answer.inMenu"));
    await settle(page);
    assert.match(await said(page), new RegExp(t("rescue.say.last.1").slice(0, 30)));
    assert.equal((await answersOf(page)).length, 4);
    await pick(page, t("rescue.last.hacktribe"));
    await page.locator("#cee-rescue-answers [data-known]").waitFor();
    assert.match(await page.locator("#cee-rescue-answers [data-known]").textContent(), new RegExp(t("rescue.known.last")));
    // "not known" on the way back: all folders
    await page.click("#cee-rescue-back");
    await settle(page);
    await answer(page, t("rescue.answer.dontKnow"));
    await settle(page);
    assert.equal((await page.locator("#cee-rescue-chat .cee-rescue-tree").count()) >= 3, true, "the file goes into all folders");
    assert.deepEqual(page.errors, []);
  });

  test("the update steps show MENU on the drawn Electribe and the shot of Korg's download row", async () => {
    const page = await open();
    await answer(page, label("prompt"));
    await settle(page);
    await answer(page, DEVICES.red.title);
    await settle(page);
    const shot = page.locator("#cee-rescue-chat .cee-rescue-shot img").last();
    assert.equal(await shot.getAttribute("src"), rescue.DEVICES.red.shot);
    assert.ok(await shot.evaluate(img => img.complete && img.naturalWidth > 0 || new Promise(r => img.onload = () => r(img.naturalWidth > 0))));
    await answer(page, t("rescue.answer.gotIt"));
    await settle(page);
    await answer(page, t("rescue.answer.onCard"));
    await settle(page);
    const keys = page.locator("#cee-rescue-chat .cee-rescue-keys").last();
    assert.equal(await keys.locator(".cee-e2-press").count(), 1);
    assert.equal(await keys.locator("figcaption").textContent(), t("rescue.keys.enter"));
    assert.deepEqual(page.errors, []);
  });
}
