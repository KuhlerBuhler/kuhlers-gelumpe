import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import RESCUE, { STATUS, TALK } from "../../data/rescue.mjs";

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

test("Blechy asks first what the device shows; the four cases are the answers, no box about the bootloader on top", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1);
  assert.match(await said(page), /Was zeigt deine Electribe/);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-blechy").count(), 1, "Blechy speaks");
  assert.deepEqual(await page.locator("#cee-rescue-answers button .cee-rescue-answer").allTextContents(), RESCUE.cases.map(c => c.label));
  assert.equal(await page.locator("#cee-rescue-stop").count(), 0, "the stop sign belongs to the case where it applies");
  assert.deepEqual(page.errors, []);
});

test("the recovery the docs measured reads as questions: EXIT, the backup, the folder of the running firmware, SOFTWARE UPDATE", async () => {
  const page = await open();
  await answer(page, RESCUE.cases[0].label);
  assert.match(await said(page), /gehaltenem EXIT/);
  await answer(page, TALK.helped);
  assert.match(await said(page), /nur dieses Mal ohne BLECHTRIBE/);
  await page.click("#cee-rescue-back");
  await answer(page, TALK.notHelped);
  assert.match(await said(page), /SYSTEM\.VSB bereit/);
  await answer(page, TALK.ready);
  const folders = page.locator("#cee-rescue-answers .cee-rescue-folder");
  assert.deepEqual(await folders.locator(".cee-rescue-answer").allTextContents(), RESCUE.folders.map(f => f.title));
  assert.equal(await folders.locator("svg.cee-e2-art").count(), RESCUE.folders.length, "each with its Electribe drawn");
  await answer(page, RESCUE.folders[2].title);
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-path").last().textContent(), RESCUE.folders[2].path);
  assert.match(await said(page), /Prüfsumme/);
  await answer(page, TALK.done);
  assert.match(await said(page), /SOFTWARE UPDATE.*FACTORY RESET.*nicht bestätigen/s);
  await walk(page);
  assert.match(await said(page), /Grenze:/);
  await page.click("#cee-rescue-again");
  assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1, "Von vorn starts over");
  await answer(page, RESCUE.cases[0].label);
  await answer(page, TALK.notHelped);
  await answer(page, TALK.notReady);
  assert.match(await said(page), /gibt es diesen Weg zurück nicht/);
  assert.deepEqual(page.errors, []);
});

test("every step says how sure it is, and what is open stays marked open", async () => {
  const page = await open();
  const tones = [];
  for (const c of RESCUE.cases) {
    await page.click("#cee-rescue-again");
    await answer(page, c.label);
    if (c.id === "starts") { await answer(page, TALK.notHelped); await answer(page, TALK.ready); await answer(page, RESCUE.folders[0].title); }
    await walk(page);
    tones.push(...await page.locator("#cee-rescue-chat .cee-status").evaluateAll(l => l.map(p => [p.textContent, p.dataset.tone])));
  }
  const words = new Set(Object.values(STATUS).map(s => s.text));
  for (const [text] of tones) assert.ok(words.has(text), `a step without a known status: ${text}`);
  await page.click("#cee-rescue-again");
  await answer(page, RESCUE.cases.find(c => c.id === "zero").label);
  await walk(page);
  const zero = await page.locator("#cee-rescue-chat").textContent();
  assert.match(zero, /Panel-Update/);
  assert.match(zero, /KORG\/electribe sampler\/System\/SYSTEM\.VSB.*ENTER/s, "00 goes through the update prompt with Korg's sampler file");
  assert.match(zero, /GitHub Issue/, "and says where to ask when it does not help");
});

test("a device that asks nothing gets the stop sign: the bootloader is never touched, beyond that only JTAG", async () => {
  const page = await open();
  await answer(page, RESCUE.cases.find(c => c.id === "silent").label);
  const stop = await page.locator("#cee-rescue-stop").textContent();
  assert.match(stop, /^Stopp/, "a word, not only a colour");
  assert.match(stop, /Bootloader/);
  assert.match(stop, /JTAG/);
  await walk(page);
  assert.match(await page.locator("#cee-rescue-chat").textContent(), /nichts weiter ausprobieren/i);
});

test("the prompt case names the factory path and the open result of the emulator", async () => {
  const page = await open();
  await answer(page, RESCUE.cases.find(c => c.id === "prompt").label);
  await walk(page);
  const text = await page.locator("#cee-rescue-chat").textContent();
  assert.match(text, /KORG\/electribe sampler\/System\/SYSTEM\.VSB/);
  assert.match(text, /ENTER/);
  assert.match(text, /Error, Invalid File/);
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
    await answer(page, RESCUE.cases[0].label);
    await answer(page, TALK.notHelped);
    await answer(page, TALK.ready);
    assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}, the folders`);
    assert.deepEqual(page.errors, []);
  }
});

test("on a phone the page does not scroll sideways and nothing sticks out", async () => {
  const page = await open({ width: 375, height: 800 });
  await answer(page, RESCUE.cases[0].label);
  await answer(page, TALK.notHelped);
  await answer(page, TALK.ready);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(overflow <= 0, `the page scrolls sideways by ${overflow}px`);
  const wide = await page.evaluate(() => [...document.querySelectorAll("#cee-rescue *")].filter(n => n.getBoundingClientRect().right > innerWidth + 1).map(n => n.className || n.tagName));
  assert.deepEqual(wide, []);
  assert.deepEqual(page.errors, []);
});

test("what is only to read follows by itself, a step to do waits for its answer, and back skips what came by itself", async () => {
  const page = await open();
  await answer(page, RESCUE.cases.find(c => c.id === "silent").label);
  await settle(page);
  const silent = RESCUE.cases.find(c => c.id === "silent");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-say").count(), silent.steps.length + 2, "every step and the limit, no button in between");
  assert.equal(await page.locator("#cee-rescue-chat .cee-rescue-you").count(), 1, "the person only answered once");
  await page.click("#cee-rescue-back");
  assert.equal(await page.locator("#cee-rescue-chat > li").count(), 1, "back lands on the first question");
  await answer(page, RESCUE.cases.find(c => c.id === "prompt").label);
  await page.locator("#cee-rescue-answers button", { hasText: TALK.done }).waitFor();
  assert.match(await said(page), /Original-Firmware/, "the step to do waits");
  assert.equal(await page.locator("#cee-rescue-sure").count(), 0, "no box explaining the markers, the marker says it");
  assert.deepEqual(page.errors, []);
});

test("the page text has no em or en dash and no absolute personal path", async () => {
  const page = await open();
  for (const c of RESCUE.cases) {
    await page.click("#cee-rescue-again");
    await answer(page, c.label);
    await walk(page);
    const text = await page.locator("#cee-rescue").textContent();
    assert.doesNotMatch(text, /[–—]/);
    assert.doesNotMatch(text, /\/Users\//);
  }
});
