import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import { makeFirmware } from "../helpers.mjs";
import * as rescue from "../../data/rescue.mjs";
import { t } from "../../site/app/i18n.mjs";

// The data holds keys of the table; the page shows their German text.
const CASES = rescue.CASES.map(c => ({ ...c, label: t(c.label), hint: t(c.hint) }));
const FOLDERS = rescue.FOLDERS.map(f => ({ ...f, title: t(f.title) }));
const DEVICES = Object.fromEntries(Object.entries(rescue.DEVICES).map(([key, d]) => [key, { ...d, title: t(d.title) }]));

// axe is a dev dependency; without it only the checks that axe would add are skipped.
const axe = await import("./support/axe.mjs").catch(() => null);

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

test("Blechy asks first what the device shows; the cases are the answers", async () => {
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
const notFound = async page => { await answer(page, CASES.find(c => c.id === "app").label); await answer(page, "Die App findet meine Electribe nicht"); return said(page); };

test("Invalid File at the start on a blue that once had Hacktribe: Korg's Sampler file into the Sampler's folder", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "invalid").label);
  assert.match(await said(page), /Wann kommt die Meldung/);
  await answer(page, "Beim Einschalten, nach press ENTER");
  assert.match(await said(page), /Welche Farbe/);
  await answer(page, DEVICES.blue.title);
  assert.match(await said(page), /jemals Hacktribe/);
  await answer(page, "Ja, Hacktribe war mal drauf");
  assert.match(await said(page), /Electribe Sampler/, "the download of the red's firmware follows by itself");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say a", { hasText: "Korgs Download-Seite" }).last().getAttribute("href"), "https://www.korg.com/us/support/download/product/0/368/#software");
  await answer(page, "Hab ich");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), "KORG/electribe sampler/System/SYSTEM.VSB");
  assert.match(await page.locator("#cee-rescue-chat").textContent(), /SYSTEM \(1\)\.VSB/, "the card step names the file name");
  assert.deepEqual(page.errors, []);
});

test("Invalid File in the menu with Hacktribe on the blue ends at Kuhler Buhler, not at a guess", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "invalid").label);
  await answer(page, "Im Menü bei SOFTWARE UPDATE");
  await answer(page, "Korgs Original-Firmware");
  await answer(page, "Blau, mit Hacktribe");
  await settle(page);
  const chat = await page.locator("#cee-rescue-chat").textContent();
  assert.match(chat, /zwei Bytes/);
  assert.match(chat, /GitHub Issue/);
  assert.deepEqual(page.errors, []);
});

test("No File in the menu: name, folder System, no renamed folder, the patcher's Electribe, then the folder of the running firmware", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "nofile").label);
  await answer(page, "Im Menü bei SOFTWARE UPDATE");
  await settle(page);
  const chat = await page.locator("#cee-rescue-chat").textContent();
  for (const words of [/SYSTEM \(1\)\.VSB/, /Unterordner System/, /Benenn keinen Ordner um/, /richtige Electribe gewählt/]) assert.match(chat, words);
  assert.match(await said(page), /Welche Firmware läuft jetzt/);
  assert.deepEqual(await page.locator("#cee-rescue-answers .cee-rescue-answer").allTextContents(), FOLDERS.map(f => f.title));
  assert.equal(await page.locator("#cee-rescue-answers [data-known]").count(), 0, "nothing connected, nothing patched: nothing is marked");
  await answer(page, FOLDERS[2].title);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), FOLDERS[2].path);
  await answer(page, "Liegt drauf");
  await answer(page, "Das Update ist durchgelaufen");
  assert.match(await said(page), /Update ist drauf/);
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
  await answer(page, CASES.find(c => c.id === "app").label);
  await answer(page, "Export oder Import zeigt alte Patterns");
  const text = await said(page);
  assert.match(text, /erst WRITE, dann EXPORT PATTERN/);
  assert.match(text, /01\.01\.2014/);
  assert.match(text, /KORG\/electribe/);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), "KORG/blechtribe/");
  assert.deepEqual(page.errors, []);
});

test("a red full check in the browser: the flash.bin of older apps, then the log", async () => {
  const page = await open();
  await answer(page, CASES.find(c => c.id === "app").label);
  await answer(page, "Die volle Prüfung im Patcher wird rot");
  assert.match(await said(page), /Ab Version 1\.3\.7/, "the browser has no app version, so both cases are named");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), "~/.gelumpe/flash/flash.bin");
  await answer(page, "Immer noch rot");
  await settle(page);
  assert.match(await page.locator("#cee-rescue-chat").textContent(), /~\/\.gelumpe\/emu\.log/);
  assert.deepEqual(page.errors, []);
});

test("a connected BLECHTRIBE is named, and its folder is marked among the answers", async () => {
  const page = await h.page({ device: true });
  await page.goto(`${h.url}?card#emu`);
  await page.evaluate(() => window.__ceeStubReady);
  await go(page, "device");
  await page.click("#cee-connect");
  await page.locator("#cee-nav-state #cee-disconnect").waitFor();
  await go(page, "rescue");
  await page.click("#cee-rescue-again");
  await answer(page, CASES[0].label);
  await answer(page, "Hilft nicht");
  await answer(page, "Ja, hab ich");
  await page.locator("#cee-rescue-answers [data-known]").waitFor();
  assert.match(await said(page), /läuft BLECHTRIBE/);
  assert.match(await page.locator("#cee-rescue-answers [data-known] .cee-rescue-answer").textContent(), new RegExp(FOLDERS[3].title.replace(/[()+]/g, "\\$&")));
  assert.equal(await page.locator("#cee-rescue-answers [data-known] .cee-rescue-known").textContent(), "Sagt die App");
  assert.deepEqual(page.errors, []);
});
