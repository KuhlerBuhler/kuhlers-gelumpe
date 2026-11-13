import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp } from "./harness.mjs";
import { severeViolations } from "./support/axe.mjs";
import { makeFirmware } from "../helpers.mjs";

let h;
before(async () => { h = await setUp(); h.file("system.vsb", await makeFirmware()); });
after(async () => { await h.tearDown(); });

test("the Doom page hands out both files for the card and says where they go and how to start", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.click("#cee-tab-doom");
  await page.locator("#cee-doom-page").waitFor();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Doom");
  assert.match(await page.locator("#cee-doom-files").textContent(), /KORG\/blechtribe\/Doom\//);
  assert.match(await page.locator("#cee-doom-start").textContent(), /SHIFT und TAP/);
  for (const name of ["bin", "wad"]) {
    const file = await h.download(page, () => page.click(`#cee-doom-${name}`));
    assert.equal(file.length, readFileSync(new URL(`../../third_party/doom/doom.${name}`, import.meta.url)).length, `doom.${name} comes whole`);
    // through saveFile like every download, so the app window saves it too and the page says so
    await page.locator("#app-toasts .cee-toast", { hasText: `„doom.${name}“ gespeichert` }).waitFor();
  }
  assert.deepEqual(await severeViolations(page), [], "axe, the Doom page");
  assert.deepEqual(page.errors, []);
});

/** The page with the simulated Electribe and its card attached, connected, the Doom tab open; doom.wad comes as `wad`, so the test stays short. */
async function connected(wad, query = "card") {
  const page = await h.page({ device: true });
  await page.route("**/third_party/doom/doom.wad", route => route.fulfill({ status: 200, contentType: "application/octet-stream", body: Buffer.from(wad) }));
  await page.goto(`${h.url}?${query}#device`);
  await page.evaluate(() => window.__ceeStubReady);
  await page.click("#cee-connect");
  await page.locator("#cee-nav-state #cee-disconnect").waitFor();
  await page.click("#cee-tab-doom");
  await page.locator("#cee-doom-page").waitFor();
  return page;
}
const cardFile = (page, name) => page.evaluate(n => { const f = window.__ceeCard.get(n); return f ? Array.from(f) : null; }, name).then(a => (a ? Uint8Array.from(a) : null));
const fakeWad = length => Uint8Array.from({ length }, (_, i) => (i * 7 + 3) & 0xff);

test("Per USB auf die Electribe is off without a device and writes both Doom files onto the card with one", async () => {
  const off = await h.page();
  await off.goto(h.url);
  await off.click("#cee-tab-doom");
  assert.equal(await off.locator("#cee-doom-usb").isDisabled(), true);
  assert.equal(await off.locator("#cee-doom-usb-help").isVisible(), true, "the help says to connect first");

  const wad = fakeWad(0x24000);
  const page = await connected(wad);
  assert.equal(await page.locator("#cee-doom-usb").isDisabled(), false);
  assert.equal(await page.locator("#cee-doom-usb-help").isHidden(), true);
  await page.click("#cee-doom-usb");
  await page.locator("#app-toasts .cee-toast", { hasText: "Doom ist auf der Karte" }).waitFor();
  assert.deepEqual(await cardFile(page, "doom.bin"), new Uint8Array(readFileSync(new URL("../../third_party/doom/doom.bin", import.meta.url))), "doom.bin comes whole");
  assert.deepEqual(await cardFile(page, "doom.wad"), wad);
  assert.equal(await cardFile(page, "SYSTEM.VSB"), null, "the firmware stays alone");
  assert.equal(await page.locator("#cee-doom-job").isHidden(), true, "the progress goes away");
  assert.equal(await page.locator("#cee-doom-usb").isDisabled(), false);
  assert.deepEqual(page.errors, []);
});

test("Abbrechen stops the Doom transfer and says the files must go again", async () => {
  const page = await connected(fakeWad(0x200000), "card&latency=20");
  await page.click("#cee-doom-usb");
  await page.locator("#cee-doom-cancel").waitFor();
  await page.waitForFunction(() => (window.__ceeCard.get("doom.wad")?.length ?? 0) > 0);
  await page.click("#cee-doom-cancel");
  await page.locator("#app-toasts .cee-toast", { hasText: "Abgebrochen" }).waitFor();
  assert.equal(await cardFile(page, "doom.bin"), null, "the wad goes first, so doom.bin was not written");
  assert.equal(await page.locator("#cee-doom-job").isHidden(), true);
  assert.equal(await page.locator("#cee-doom-usb").isDisabled(), false);
  assert.deepEqual(page.errors, []);
});
