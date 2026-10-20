import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const selectedTab = page => page.locator("#cee-areas [aria-selected='true']").getAttribute("data-tab");

test("the device drawing carries no brand name", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  assert.doesNotMatch(await page.locator("#cee-e2").innerHTML(), /korg|electribe sampler/i);
});

test("the sidebar lists only the entries, the navbar names the open page, up and down walk the list", async () => {
  const page = await h.page();
  await page.goto(h.url);
  assert.equal(await selectedTab(page), "start");
  assert.deepEqual(await page.locator("#cee-areas [role=tab]:visible").allTextContents(), ["Start", "Emulator", "Patcher", "Startbildschirm", "Plugins", "Presets", "Modulationen", "Rettung"]);
  assert.equal(await page.locator("#cee-sidebar .cee-nav-label").count(), 0, "no headings between the entries");
  await page.click("#cee-tab-patcher");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Patcher");
  assert.equal(await page.locator("#cee-area-patcher").getAttribute("hidden"), null);
  await page.keyboard.press("ArrowDown");
  assert.equal(await selectedTab(page), "splash");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Startbildschirm");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  assert.equal(await selectedTab(page), "emu");
  await page.click("#cee-brand");
  await page.waitForFunction(() => document.querySelector("#cee-areas [aria-selected='true']")?.dataset.tab === "start");
});

test("Pattern-Werkzeuge and Samples are not offered: no tab, and #ptools and #samples land on the start page", async () => {
  const page = await h.page();
  for (const id of ["ptools", "samples"]) {
    await page.goto(`${h.url}#${id}`);
    assert.equal(await page.locator(`#cee-tab-${id}`).count(), 0, `${id} has no tab`);
    assert.equal(await selectedTab(page), "start", `#${id} does not open the page`);
    assert.equal(await page.locator(`#cee-area-${id}`).isVisible(), false);
  }
  await page.evaluate(() => localStorage.setItem("cee.area", "samples"));
  await page.goto(h.url);
  assert.equal(await selectedTab(page), "start", "a remembered hidden page is ignored");
  await page.goto(`${h.url}?labs#ptools`);
  assert.equal(await selectedTab(page), "ptools", "with ?labs the pages stay reachable for tests");
  assert.deepEqual(await page.locator("#cee-areas [role=tab]:visible").allTextContents(), ["Start", "Emulator", "Patcher", "Startbildschirm", "Plugins", "Presets", "Modulationen", "Pattern-Werkzeuge", "Samples", "Rettung"]);
});

test("the navbar title of the emulator page is a menu: emulator or real device", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  assert.equal(await page.locator("#cee-nav-title").isVisible(), false);
  assert.equal(await page.locator("#cee-mode-label").textContent(), "Emulator");
  assert.equal(await page.locator("#cee-nav-state").textContent(), "", "the emulator page has no device state");
  assert.equal(await page.getAttribute("#cee-mode-button", "aria-expanded"), "false");
  await page.click("#cee-mode-button");
  assert.equal(await page.getAttribute("#cee-mode-button", "aria-expanded"), "true");
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#cee-mode-menu").isVisible(), false);
  assert.equal(await page.evaluate(() => document.activeElement.id), "cee-mode-button", "the focus goes back to the button");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  assert.equal(await page.locator("#cee-mode-label").textContent(), "Echtes Gerät");
  assert.equal(await page.locator("#cee-device").isVisible(), false, "with nothing to say, the area above the drawing takes no room (the connect button is in the navbar)");
  assert.equal(await page.locator("#cee-area-emu #cee-e2").isVisible(), true, "the real device is shown in the emulator's drawing");
  assert.equal(await page.getAttribute("#cee-tab-emu", "data-active"), "", "the sidebar still marks the emulator entry");
  assert.equal(await page.locator("#cee-nav-state #cee-connect").isVisible(), true, "on the device page the navbar carries the connect button instead of a not-connected text");
});

test("the options of the emulator page are sub-items under its entry; other pages show none", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  assert.deepEqual(await page.locator("#cee-sub-emu > .ui-details > summary").allTextContents(), ["Firmware (VSB)", "SD-Karte"]);
  assert.equal(await page.evaluate(() => Number(document.getElementById("cee-sub-emu").style.order) - Number(document.getElementById("cee-tab-emu").style.order)), 1, "the options sit right after the entry in the visual order");
  assert.equal(await page.getAttribute("#cee-sub-emu", "aria-label"), "Optionen Emulator");
  for (const id of ["cee-emu-setup", "cee-emu-card"]) {
    assert.equal(await page.locator(`#${id}`).evaluate(n => n.closest("#cee-sidebar") !== null), true, `${id} is in the sidebar`);
  }
  assert.equal(await page.locator(".cee-main #cee-e2-power").isVisible(), true, "the power key stays in the page");
  assert.equal(await page.locator("#cee-emu-setup").evaluate(n => n.open), false, "the blocks start closed");
  await page.locator("#cee-emu-setup > summary").focus();
  await page.keyboard.press("ArrowDown");
  assert.equal(await selectedTab(page), "emu", "arrow keys on an option do not walk the entries");
  for (const tab of ["patcher", "fx", "start"]) {
    await page.click(`#cee-tab-${tab}`);
    assert.equal(await page.locator(".cee-nav-sub:visible").count(), 0, `${tab} shows no options`);
  }
  await page.click("#cee-tab-scripts");
  assert.deepEqual(await page.locator("#cee-sub-scripts button").allTextContents(), ["Katalog", "Editor", "Lauf", "Konsole", "Dokumentation"], "Plugins shows its pages as sub-items");
  assert.equal(await page.getAttribute("#cee-sub-scripts", "aria-label"), "Optionen Plugins");
  assert.equal(await page.locator("#cee-sub-emu").isVisible(), false);
  await page.click("#cee-tab-emu");
  assert.equal(await page.locator("#cee-sub-emu").isVisible(), true);
});

test("the sidebar stays put while the page scrolls", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1280, height: 500 });
  await page.goto(`${h.url}#emu`);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  assert.ok(await page.evaluate(() => window.scrollY) > 0, "the page scrolls");
  assert.equal(Math.abs(Math.round((await page.locator("#cee-sidebar").boundingBox()).y)), 0);
  assert.equal(await page.locator("#cee-tab-start").isVisible(), true);
});

test("on a phone the sidebar is a drawer behind the menu button and the page does not scroll sideways", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(h.url);
  assert.equal(await page.locator("#cee-tab-emu").isVisible(), false);
  await page.click("#cee-menu");
  assert.equal(await page.getAttribute("#cee-menu", "aria-expanded"), "true");
  await page.click("#cee-tab-emu");
  assert.equal(await page.getAttribute("#cee-menu", "aria-expanded"), "false", "choosing a page closes the drawer");
  assert.equal(await page.locator("#cee-area-emu").isVisible(), true);
  await page.click("#cee-menu");
  await page.keyboard.press("Escape");
  assert.equal(await page.getAttribute("#cee-menu", "aria-expanded"), "false");
  await page.click("#cee-menu");
  assert.equal(await page.locator("#cee-sub-emu").isVisible(), true, "the options are in the drawer");
  await page.click("#cee-emu-setup > summary");
  assert.equal(await page.locator("#cee-emu-setup").evaluate(n => n.open), true);
  assert.equal(await page.getAttribute("#cee-menu", "aria-expanded"), "true", "using an option keeps the drawer open");
  assert.ok((await page.locator("#cee-sidebar").boundingBox()).width <= 375 * 0.85 + 1);
  await page.mouse.click(370, 400);
  assert.equal(await page.getAttribute("#cee-menu", "aria-expanded"), "false", "a tap beside the drawer closes it");
  for (const tab of ["start", "emu", "device", "patcher", "fx", "patterns", "scripts"]) {
    await page.evaluate(id => { location.hash = id; }, tab);
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.equal(wide, 0, `${tab} scrolls sideways by ${wide}px`);
  }
});

test("the page title and the sidebar toggle share one centre line in the navbar, expanded and folded", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${h.url}#rescue`);
  const centres = () => page.evaluate(() => {
    const mid = s => { const r = document.querySelector(s).getBoundingClientRect(); return r.top + r.height / 2; };
    return { bar: mid(".cee-navbar"), title: mid("#cee-nav-title"), toggle: mid("#cee-collapse"), brand: mid("#cee-brand") };
  });
  for (const state of ["expanded", "folded"]) {
    if (state === "folded") { await page.click("#cee-collapse"); await page.waitForTimeout(300); }
    const c = await centres();
    for (const key of ["title", "toggle", "brand"]) assert.ok(Math.abs(c[key] - c.bar) <= 1, `${state}: ${key} at ${c[key]}, navbar centre ${c.bar}`);
  }
});

test("the device drawing fits its box: no sideways scrollbar under the electribe, at any window size", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  for (const [width, height] of [[1440, 900], [1280, 800], [1642, 986], [1920, 1080], [1100, 900]]) {
    await page.setViewportSize({ width, height });
    const over = await page.locator(".cee-e2-viewport").evaluate(n => n.scrollWidth - n.clientWidth);
    assert.equal(over, 0, `${width} x ${height}: the drawing is ${over}px wider than its box`);
  }
});


test("the drawing sits at the same height on the emulator page and on the real device page while nothing is connected", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1440, height: 900 });
  const top = async hash => {
    await page.goto(`${h.url}${hash}`);
    await page.waitForFunction(id => document.querySelector("#cee-areas [aria-selected='true']")?.dataset.tab === id, hash.slice(1));
    await page.locator(".cee-e2-body").first().waitFor();
    await page.locator("#cee-area-emu").evaluate(n => Promise.all(n.getAnimations().map(a => a.finished)));
    return page.evaluate(() => Math.round([...document.querySelectorAll(".cee-e2-body")].find(n => n.getBoundingClientRect().height > 0).getBoundingClientRect().top));
  };
  assert.equal(await top("#device"), await top("#emu"));
});

test("the start page has its sections in heading order and the donate link opens outside the app", async () => {
  const page = await h.page();
  await page.goto(h.url);
  assert.deepEqual(await page.locator("#cee-start-page h2").allTextContents(), ["Was ist das?", "Was man damit machen kann", "Wer ich bin", "Wieso", "Spenden", "Was du brauchst", "Woher es kommt"]);
  for (const id of ["#cee-donate", "#cee-donate-start"]) {
    assert.equal(await page.getAttribute(id, "href"), "https://www.paypal.me/kuhlerbuhler");
    assert.equal(await page.getAttribute(id, "target"), "_blank");
  }
  const app = await h.page();
  await app.addInitScript(() => { window.__GELUMPE_APP = { version: "0.0.0" }; });
  await app.goto(h.url);
  assert.equal(await app.getAttribute("#cee-donate", "target"), "_self", "in the app the navigation is caught and opened in the browser");
});
