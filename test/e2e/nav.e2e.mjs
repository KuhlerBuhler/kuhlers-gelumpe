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
  assert.deepEqual(await page.locator("#cee-areas [role=tab]:visible").allTextContents(), ["Start", "Emulator", "Startbildschirm", "Konsole", "Rettung", "Firmware Patcher", "Changelogs", "Plugins", "Baukasten", "Doom", "Features"]);
  assert.equal(await page.locator("#cee-sidebar .cee-nav-label").count(), 0, "no headings between the entries");
  await page.click("#cee-tab-patcher");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Firmware Patcher");
  assert.equal(await page.locator("#cee-area-patcher").getAttribute("hidden"), null);
  await page.keyboard.press("ArrowDown");
  assert.equal(await selectedTab(page), "changelog");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Changelogs");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  assert.equal(await selectedTab(page), "rescue");
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
  assert.deepEqual(await page.locator("#cee-areas [role=tab]:visible").allTextContents(), ["Start", "Emulator", "Startbildschirm", "Konsole", "Rettung", "Firmware Patcher", "Changelogs", "Plugins", "Baukasten", "Doom", "Features", "Pattern-Werkzeuge", "Samples"]);
});

test("the navbar title of the emulator page is a menu: emulator or real device", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  assert.equal(await page.locator("#cee-nav-title").isVisible(), false);
  assert.equal(await page.locator("#cee-mode-label").textContent(), "Emulator");
  assert.deepEqual(await page.locator("#cee-nav-state").getByRole("button").allTextContents(), ["SD-Karte öffnen", "Eigenes Fenster"], "the emulator page has no device state, only the SD card and the button for its own window");
  assert.equal(await page.locator("#cee-nav-state #cee-sd-inserted").count(), 1, "the card's switch beside it");
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

test("the emulator page has no options in the sidebar: the firmware goes on its display, the SD card opens from the navbar", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  assert.equal(await page.locator("#cee-sub-emu").count(), 0, "nothing folds out under the entry");
  assert.equal(await page.locator("#cee-nav-state #cee-sd-open").textContent(), "SD-Karte öffnen", "the SD card opens from the navbar");
  assert.equal(await page.locator("#cee-nav-state #cee-sd-inserted").count(), 1, "and its switch sits next to it");
  assert.equal(await page.locator(".cee-main #cee-e2-power").isVisible(), true, "the power key stays in the page");
  assert.equal(await page.locator(".cee-main #cee-emu-offer").isVisible(), true, "a switched-off device offers the firmware on its display");
  assert.match(await page.locator("#cee-emu-offer").textContent(), /SYSTEM\.VSB/);
  assert.equal(await page.locator("#cee-emu-status").textContent().then(t => /npm run emu/.test(t)), false, "nobody is asked to run a command");
  await page.click("#cee-emu-start");
  await page.locator("#app-toasts .cee-toast[data-kind=error]", { hasText: "Der Emulator läuft nicht" }).waitFor();
  for (const tab of ["patcher", "start"]) {
    await page.click(`#cee-tab-${tab}`);
    assert.equal(await page.locator(".cee-nav-sub:visible").count(), 0, `${tab} shows no options`);
  }
  await page.click("#cee-tab-scripts");
  assert.deepEqual(await page.locator("#cee-sub-scripts button").allTextContents(), ["Katalog", "Meine Plugins", "Editor", "Dokumentation"], "Plugins shows its pages as sub-items");
  assert.equal(await page.getAttribute("#cee-sub-scripts", "aria-label"), "Optionen Plugins");
  await page.click("#cee-tab-emu");
  assert.equal(await page.locator("#cee-sub-scripts").isVisible(), false, "the options of Plugins go with its page");
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

test("another page starts at the top, not where the last one was scrolled to", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1280, height: 500 });
  await page.goto(`${h.url}#plugins`);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  assert.ok(await page.evaluate(() => window.scrollY) > 0, "the page scrolls");
  await page.click("#cee-tab-features");
  assert.equal(await page.evaluate(() => window.scrollY), 0);
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
  assert.equal(await page.locator("#cee-tab-console").isVisible(), true, "the entries are in the drawer");
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
  assert.deepEqual(await page.locator("#cee-start-page h2").allTextContents(), ["Wie installiere ich BLECHTRIBE?", "Geht was schief?", "Was kann BLECHTRIBE?", "Erkunden", "Spenden"]);
  assert.match(await page.locator("#cee-start-features").textContent(), /volle Liste/, "the start page says there is a lot and points to Features");
  assert.equal(await page.getAttribute("#cee-start-rescue-more", "href"), "#rescue", "Geht was schief? has its button to the rescue page");
  assert.equal(await page.getAttribute("#cee-start-more", "href"), "#features", "the button leads to the page of all functions");
  await page.click("#cee-start-more");
  assert.equal(await page.locator("#cee-feature-dice canvas.cee-catalog-thumb").count(), 1, "a function on the Features page carries its picture");
  await page.waitForFunction(() => {
    const d = document.querySelector("#cee-feature-dice canvas").getContext("2d").getImageData(0, 0, 128, 64).data;
    return new Set(Array.from({ length: d.length / 4 }, (_, i) => d[i * 4])).size === 2;
  }, null, { timeout: 5000 });
  const card = page.locator("#cee-feature-dice");
  assert.deepEqual(await card.evaluate(c => [...c.children].map(n => n.className || n.tagName)), ["cee-lcd cee-catalog-thumb", "H3", "P", "cee-feature-how", "cee-feature-where"], "picture, name, text, what to press, then the devices at the foot");
  assert.deepEqual(await card.locator(".cee-feature-where li").allTextContents(), ["Rot", "Blau"]);
  await page.goto(h.url);
  for (const id of ["#cee-donate", "#cee-donate-start"]) assert.equal(await page.getAttribute(id, "href"), "#support", "donating leads to the Unterstützen page first");
  assert.equal(await page.getAttribute("#cee-support-paypal", "target"), "_blank");
  const app = await h.page();
  await app.addInitScript(() => { window.__GELUMPE_APP = { version: "0.0.0" }; });
  await app.goto(h.url);
  for (const id of ["#cee-support-paypal", "#cee-support-issues", "#cee-support-instagram"]) assert.equal(await app.getAttribute(id, "target"), "_self", "in the app the navigation is caught and opened in the browser");
  assert.equal(await app.getAttribute("#cee-patch-korg-red", "target"), "_self");
});

test("the app opens on the start page although its address carries the emulator link; the browser goes to the emulator", async () => {
  const app = await h.page();
  await app.addInitScript(() => { window.__GELUMPE_APP = { version: "1.2.0" }; });
  await app.goto(`${h.url}#emu=1:x`);
  await app.waitForFunction(() => document.documentElement.dataset.ceeReady === "1");
  assert.equal(await app.locator("#cee-areas [aria-selected='true']").getAttribute("data-tab"), "start");
  const page = await h.page();
  await page.goto(`${h.url}#emu=1:x`);
  await page.waitForFunction(() => document.documentElement.dataset.ceeReady === "1");
  assert.equal(await page.locator("#cee-areas [aria-selected='true']").getAttribute("data-tab"), "emu");
});

test("the settings page names the app's version in the app, and has no such line in the browser", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#settings`);
  await page.locator("#cee-settings-title").waitFor({ state: "attached" });
  assert.equal(await page.locator("#cee-version").count(), 0);
  const app = await h.page();
  await app.addInitScript(() => { window.__GELUMPE_APP = { version: "1.2.0" }; });
  await app.goto(`${h.url}#settings`);
  assert.equal(await app.locator("#cee-version").textContent(), "App-Version 1.2.0");
});

test("the start page sends to the patcher for Korg's firmware, and to Plugins and the Baukasten under Erkunden", async () => {
  const page = await h.page();
  await page.goto(h.url);
  assert.equal(await page.getAttribute("#cee-start-step-firmware", "href"), "#patcher");
  assert.equal(await page.locator("#cee-start-page .cee-device-card").count(), 0, "Korg's cards live on the patcher");
  const explore = page.locator("#cee-start-explore a");
  assert.deepEqual(await explore.evaluateAll(list => list.map(a => a.getAttribute("href"))), ["#scripts", "#baukasten"]);
});

test("the emulator opens in a window of its own; the page shows a note, and Hier anzeigen or closing the window brings it back", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  await page.locator("#cee-emu-pop").waitFor();
  // what is seen, not the attribute: a display rule can show an element that is hidden
  const shown = async () => ({ device: await page.locator("#cee-emu-device").isVisible(), note: await page.locator("#cee-emu-away").isVisible() });
  assert.deepEqual(await shown(), { device: true, note: false }, "before the window opens, only the device");
  assert.equal(await page.locator(".cee-navbar #cee-emu-pop").isVisible(), true, "the button sits in the navbar");
  const [win] = await Promise.all([page.context().waitForEvent("page"), page.click("#cee-emu-pop")]);
  await win.locator("#cee-emu-device").waitFor();
  assert.deepEqual(await shown(), { device: false, note: true });
  assert.equal(await page.locator("#cee-emu-away p").textContent(), "Der Emulator ist in einem eigenen Fenster geöffnet.");

  await page.click("#cee-emu-back");
  await page.locator("#cee-emu-device").waitFor({ state: "visible" });
  assert.deepEqual(await shown(), { device: true, note: false });
  await win.waitForEvent("close", { timeout: 3000 }).catch(() => {});
  assert.equal(win.isClosed(), true, "Hier anzeigen closes the window");

  const [again] = await Promise.all([page.context().waitForEvent("page"), page.click("#cee-emu-pop")]);
  await again.locator("#cee-emu-device").waitFor();
  await page.locator("#cee-emu-away").waitFor();
  await again.close();
  await page.locator("#cee-emu-device").waitFor({ state: "visible", timeout: 6000 });
  assert.deepEqual(await shown(), { device: true, note: false });
  assert.deepEqual(page.errors, []);
});

test("changelogs: a new release puts a ! on the entry, opening it shows the release like GitHub and the ! goes", async () => {
  const page = await h.page();
  const releases = [{ tag_name: "v1.3.0", name: "v1.3.0", html_url: "https://github.com/KuhlerBuhler/kuhlers-gelumpe/releases/tag/v1.3.0", published_at: "2026-11-01T12:00:00Z", prerelease: false, draft: false, body: "## Neu\n- **Changelogs** im Menü\n\nMehr auf [GitHub](https://github.com/KuhlerBuhler/kuhlers-gelumpe).", assets: ["GELUMPE_1.3.0_aarch64.dmg", "GELUMPE_1.3.0_x64-setup.exe", "gelumpe_1.3.0_amd64.AppImage", "gelumpe_1.3.0_amd64.deb", "BLECH.patch", "BLECH-for-0a1b2c3d.bsdiff", "SHA256SUMS"].map(name => ({ name, browser_download_url: `https://example.invalid/${name}` })) }];
  await page.route("https://api.github.com/**", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(releases) }));
  await page.goto(h.url);
  await page.locator("#cee-tab-changelog .cee-nav-badge").waitFor();
  await page.click("#cee-tab-changelog");
  const release = page.locator("#cee-changelog .cee-release");
  assert.equal(await release.count(), 1);
  assert.equal(await release.locator("h2 a").textContent(), "v1.3.0", "the version is the heading and the link to GitHub");
  assert.equal(await release.locator(".cee-status").count(), 0, "no Aktuell: the newest stands on top anyway");
  const buttons = await release.locator(".cee-release-get a").allTextContents();
  assert.equal(buttons.length, 2, "one app for this system and the patch, not every file");
  assert.equal(buttons[1], "Patch herunterladen");
  assert.match(buttons[0], /^App für (macOS|Windows|Linux)$/);
  assert.equal(await release.locator("li strong").textContent(), "Changelogs");
  assert.equal(await release.locator("a[href='https://github.com/KuhlerBuhler/kuhlers-gelumpe']").count(), 1);
  assert.equal(await page.locator("#cee-tab-changelog .cee-nav-badge").count(), 0);
  await page.reload();
  await page.locator("#cee-changelog .cee-release").first().waitFor({ state: "attached" });
  assert.equal(await page.locator("#cee-tab-changelog .cee-nav-badge").count(), 0, "seen stays seen");
  assert.deepEqual(page.errors, []);
});
