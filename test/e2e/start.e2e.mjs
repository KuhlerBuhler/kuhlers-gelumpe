import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { makeFirmware } from "../helpers.mjs";
import { RELEASE_NOTES } from "../../data/release-notes.mjs";
import { VERSION_FILE } from "../../tools/patch/blech_version.mjs";

let h;
let firmware;
before(async () => {
  h = await setUp();
  firmware = await makeFirmware();
  h.file("system.vsb", firmware);
});
after(async () => { await h.tearDown(); });

const APP = RELEASE_NOTES[0].version;
const view = page => page.locator("#cee-start-page").getAttribute("data-view");
const text = (page, selector) => page.locator(selector).evaluate(node => node.textContent.trim());

/** The firmware the simulated Electribe runs, with "BLECH <version>" where the patch blech-version puts it. */
function withVersion(version) {
  const bytes = Uint8Array.from(firmware);
  bytes.fill(0, VERSION_FILE, VERSION_FILE + 16);
  bytes.set(new TextEncoder().encode(`BLECH ${version}`), VERSION_FILE);
  return bytes;
}

/** The simulated Electribe with BLECH, connected, then the start page. */
async function connected(version) {
  h.file("system.vsb", withVersion(version));
  const page = await h.page({ device: true });
  await page.goto(`${h.url}?card#device`);
  await page.evaluate(() => window.__ceeStubReady);
  await page.click("#cee-connect");
  await page.locator("#cee-nav-state #cee-disconnect").waitFor();
  await page.click("#cee-tab-start");
  await page.locator("#cee-start-hub").waitFor();
  return page;
}

test("first visit: the welcome, no hub, the install guide in place", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.locator("#cee-start-welcome").waitFor();
  assert.equal(await view(page), "welcome");
  assert.equal(await page.locator("#cee-start-hub").isHidden(), true);
  assert.equal(await page.locator("#cee-start-welcome #cee-start-entry").count(), 1, "the install steps stand in the welcome");
  assert.deepEqual(page.errors, []);
});

test("a firmware in the emulator turns the start page into the hub, and it stays the hub after a reload", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  await page.setInputFiles("#cee-emu-vsb", h.file("load.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-tab-start");
  await page.waitForFunction(() => document.querySelector("#cee-start-page").dataset.view === "hub");
  assert.equal(await page.locator("#cee-start-welcome").isHidden(), true);
  assert.equal(await page.locator("#cee-start-hub h1").textContent(), "Deine BLECHTRIBE");
  await page.waitForFunction(() => document.querySelector("#cee-start-emu-state")?.textContent === "Firmware geladen");
  assert.match(await text(page, "#cee-start-emu-name"), /Sampler$/);
  assert.equal(await text(page, "#cee-start-emu-go"), "Emulator öffnen");
  assert.equal(await page.locator("#cee-start-emu-card").getAttribute("data-device"), "red");
  assert.equal(await text(page, "#cee-start-device-state"), "Keine Electribe verbunden");
  assert.equal(await page.locator("#cee-start-next-update").isHidden(), true, "nothing to update without a device");
  assert.deepEqual(await page.locator("#cee-start-next a").evaluateAll(a => a.filter(n => !n.closest("[hidden]")).map(n => n.getAttribute("href"))), ["#scripts", "#baukasten", "#splash", "#sampleset", "#patcher"]);
  // the news come from the newest release notes
  assert.equal(await text(page, "#cee-start-news-version"), `BLECHTRIBE ${APP} bringt unter anderem:`);
  assert.ok(await page.locator("#cee-start-news-list li").count() >= 1);
  // the install steps fold into the hub's guide, the ids stay unique
  assert.equal(await page.locator("#cee-start-guide #cee-start-entry").count(), 1);
  assert.equal(await page.locator("#cee-start-entry").count(), 1);
  await page.click("#cee-start-guide > summary");
  assert.equal(await page.locator("#cee-start-guide h2").isVisible(), true);
  // every state is an icon and a word
  assert.equal(await page.locator("#cee-start-hub .cee-state:not([hidden])").evaluateAll(s => s.filter(n => !n.querySelector("svg")).length), 0);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.reload();
  await page.locator("#cee-start-hub").waitFor();
  assert.equal(await view(page), "hub", "the merker keeps the hub without the firmware");
  assert.deepEqual(page.errors, []);
});

test("an Electribe with an older BLECHTRIBE: the hub says the update is due and puts it first", async () => {
  const page = await connected("1.0.0");
  await page.waitForFunction(() => /fällig/.test(document.querySelector("#cee-start-device-version")?.textContent ?? ""));
  assert.equal(await text(page, "#cee-start-device-state"), "Verbunden");
  assert.equal(await text(page, "#cee-start-device-version"), `Update auf ${APP} fällig`);
  assert.match(await text(page, "#cee-start-device-facts"), /^Korg \d\.\d\d, BLECHTRIBE 1\.0\.0$/);
  assert.equal(await page.locator("#cee-start-next-update").isVisible(), true);
  assert.equal(await page.locator("#cee-start-next li:first-child a").getAttribute("href"), "#patcher");
  assert.equal(await text(page, "#cee-start-update-title"), `Update auf BLECHTRIBE ${APP}`);
  assert.deepEqual(page.errors, []);
});

test("an Electribe with this app's BLECHTRIBE is up to date, a newer one is said so, no update card", async () => {
  for (const [version, word] of [[APP, "Aktuell"], ["99.0.0", "Neuer als diese App"]]) {
    const page = await connected(version);
    await page.waitForFunction(w => document.querySelector("#cee-start-device-version")?.textContent === w, word);
    assert.equal(await page.locator("#cee-start-next-update").isHidden(), true, version);
    assert.deepEqual(page.errors, []);
  }
});

test("the device card reads red from the Electribe's flash at once, the read does not hold the session", async () => {
  const page = await connected(APP);
  // an unanswered flash read holds the session until the sender gives up after 12 s
  await page.waitForFunction(() => document.querySelector("#cee-start-device")?.dataset.device === "red", null, { timeout: 5000 });
  assert.equal(await text(page, "#cee-start-device-name"), "Electribe, rot");
  assert.deepEqual(page.errors, []);
});
