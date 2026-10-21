import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import RESCUE, { STATUS } from "../../data/rescue.mjs";

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

const openAll = page => page.locator("#cee-rescue details").evaluateAll(list => list.forEach(d => d.setAttribute("open", "")));

test("Rettung is an entry of the sidebar, and the navbar names the page", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await go(page, "rescue");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Rettung");
  assert.equal(await page.locator("#cee-area-rescue").getAttribute("hidden"), null);
  assert.equal(await page.locator("#cee-rescue h1").textContent(), "Rettung");
  assert.deepEqual(page.errors, []);
});

test("the stop sign says the bootloader is never touched and that beyond that only JTAG helps", async () => {
  const page = await open();
  const stop = page.locator("#cee-rescue-stop");
  assert.equal(await stop.isVisible(), true);
  assert.equal(await stop.getAttribute("role"), "note");
  assert.equal(await stop.getAttribute("aria-labelledby"), "cee-rescue-stop-title");
  assert.match(await page.locator("#cee-rescue-stop-title").textContent(), /^Stopp/, "a word, not only a colour");
  const text = await stop.textContent();
  assert.match(text, /Bootloader/);
  assert.match(text, /nie/);
  assert.match(text, /JTAG/);
  assert.match(text, /nichts weiter ausprobieren/i);
  const first = await page.evaluate(() => [...document.querySelectorAll("#cee-rescue .cee-rescue > *")].findIndex(n => n.id === "cee-rescue-stop"));
  assert.ok(first <= 2, "the sign stands above the steps");
});

test("the folders are four device cards with a drawing, a title and the path", async () => {
  const page = await open();
  const rows = await page.locator("#cee-rescue-folders > li").evaluateAll(list => list.map(li => ({
    title: li.querySelector("strong").textContent,
    path: li.querySelector("code.cee-rescue-path").textContent,
    art: !!li.querySelector("svg.cee-e2-art"),
  })));
  assert.deepEqual(rows, RESCUE.folders.map(f => ({ title: f.title, path: f.path, art: true })));
});

test("four cases open from the keyboard, and every step says how sure it is", async () => {
  const page = await open();
  assert.deepEqual(await page.locator("#cee-rescue .cee-rescue-case").evaluateAll(l => l.map(d => d.id)), RESCUE.cases.map(c => `cee-rescue-case-${c.id}`));
  const summary = page.locator("#cee-rescue-case-zero > summary");
  await summary.focus();
  assert.equal(await page.locator("#cee-rescue-case-zero").evaluate(d => d.open), false);
  await page.keyboard.press("Enter");
  assert.equal(await page.locator("#cee-rescue-case-zero").evaluate(d => d.open), true);
  await openAll(page);
  const steps = page.locator("#cee-rescue .cee-rescue-step");
  assert.equal(await steps.count(), RESCUE.cases.reduce((n, c) => n + c.steps.length, 0));
  const words = new Set(Object.values(STATUS).map(s => s.text));
  for (const pill of await steps.evaluateAll(l => l.map(li => li.querySelector(".cee-status")?.textContent))) {
    assert.ok(words.has(pill), `a step without a status: ${pill}`);
  }
});

test("the recovery the docs measured reads as steps: EXIT, the file in the folder, SOFTWARE UPDATE", async () => {
  const page = await open();
  await openAll(page);
  const starts = await page.locator("#cee-rescue-case-starts").textContent();
  for (const part of [/gehaltenem EXIT/, /SYSTEM\.VSB/, /Prüfsumme/, /SOFTWARE UPDATE/, /FACTORY RESET/, /nicht bestätigen/]) assert.match(starts, part);
  const prompt = await page.locator("#cee-rescue-case-prompt").textContent();
  assert.match(prompt, /KORG\/electribe sampler\/System\/SYSTEM\.VSB/);
  assert.match(prompt, /ENTER/);
  assert.match(prompt, /Error, Invalid File/);
  const zero = await page.locator("#cee-rescue-case-zero").textContent();
  assert.match(zero, /Panel-Update/);
  assert.match(zero, /nicht gemessen/, "no recovery for 00 is claimed");
  assert.match(await page.locator("#cee-rescue-case-silent").textContent(), /JTAG/);
});

test("what is open is marked open: the BLECH notch, the factory path and 00 carry the open status", async () => {
  const page = await open();
  await openAll(page);
  const open_ = await page.locator("#cee-rescue .cee-rescue-step").evaluateAll(l => l.filter(li => li.querySelector(".cee-status").dataset.tone === "warn").length);
  const wanted = RESCUE.cases.flatMap(c => c.steps).filter(s => s.status === "offen").length;
  assert.equal(open_, wanted);
  assert.ok(wanted >= 5);
  assert.equal(await page.locator("#cee-rescue-case-zero .cee-status[data-tone=ok]").count(), 0, "nothing about 00 is measured on the device");
});

test("the start page and the patcher link to the page, and the link works", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.click("#cee-start-rescue");
  await page.locator("#cee-area-rescue:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Rettung");
  await page.click("#cee-tab-patcher");
  assert.equal(await page.getAttribute("#cee-patch-rescue", "href"), "#rescue");
  await page.click("#cee-patch-rescue");
  await page.locator("#cee-area-rescue:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-rescue-stop").isVisible(), true);
});

test("no serious axe violation, wide and on a phone", { skip: axe ? false : "@axe-core/playwright is not installed" }, async () => {
  for (const viewport of [undefined, { width: 375, height: 800 }]) {
    const page = await open(viewport);
    await openAll(page);
    assert.deepEqual(await axe.severeViolations(page), [], `axe at ${viewport?.width ?? "desktop"}`);
    assert.deepEqual(page.errors, []);
  }
});

test("on a phone the page does not scroll sideways and nothing sticks out", async () => {
  const page = await open({ width: 375, height: 800 });
  await openAll(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(overflow <= 0, `the page scrolls sideways by ${overflow}px`);
  const wide = await page.evaluate(() => [...document.querySelectorAll("#cee-rescue *")].filter(n => n.getBoundingClientRect().right > innerWidth + 1).map(n => n.className || n.tagName));
  assert.deepEqual(wide, []);
  assert.deepEqual(page.errors, []);
});

test("the page text has no em or en dash and no absolute personal path", async () => {
  const page = await open();
  await openAll(page);
  const text = await page.locator("#cee-rescue").textContent();
  assert.doesNotMatch(text, /[\u2013\u2014]/);
  assert.doesNotMatch(text, /\/Users\//);
});

test("every accordion chevron sits inside its summary, vertically centred, with the text left-aligned", async () => {
  const page = await open({ width: 1440, height: 900 });
  await openAll(page);
  const rows = await page.locator("#cee-rescue details.ui-details > summary").evaluateAll(list => list.map(s => {
    const box = s.getBoundingClientRect();
    const after = getComputedStyle(s, "::after");
    const parts = [...s.children].map(c => c.getBoundingClientRect());
    return {
      display: getComputedStyle(s).display, align: getComputedStyle(s).textAlign, alignItems: getComputedStyle(s).alignItems,
      column: after.gridColumnStart, rows: after.gridRowEnd,
      textRight: Math.max(...parts.map(p => p.right)), summaryRight: box.right, labelLeft: parts[0].left, summaryLeft: box.left,
    };
  }));
  assert.ok(rows.length >= 4);
  for (const r of rows) {
    assert.equal(r.display, "grid");
    assert.equal(r.alignItems, "center", "the chevron is centred on the row");
    assert.match(r.align, /left|start/);
    assert.equal(r.column, "2", "the chevron has a column of its own");
    assert.ok(r.textRight < r.summaryRight - 8, "the text does not run under the chevron");
    assert.ok(r.labelLeft - r.summaryLeft < 40, "the title starts at the left");
  }
});
