import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const badge = page => page.locator("#cee-usb");
const waitState = (page, want) => page.waitForFunction(w => document.querySelector("#cee-usb")?.dataset.state === w, want);

/** Native MIDI (Mac, Linux): the page lists the ports through the app; `window.__plugged` is the stand-in's list. */
async function nativePage() {
  const page = await h.page();
  await page.addInitScript(() => {
    window.__GELUMPE_APP = { nativeMidi: true };
    window.__plugged = false;
    window.__lists = 0;
    window.__TAURI__ = { core: { Channel: class {}, invoke: async command => {
      if (command !== "midi_list") return {};
      window.__lists++;
      return window.__plugged ? { inputs: [{ id: "i", name: "electribe2 sampler" }], outputs: [{ id: "o", name: "electribe2 sampler" }] } : { inputs: [], outputs: [] };
    } } };
  });
  await page.goto(h.url);
  return page;
}

/** Web MIDI (Windows): one access object that tells `statechange`; the permission is granted. */
async function webPage({ granted = true } = {}) {
  const page = await h.page();
  await page.addInitScript(granted => {
    const access = new EventTarget();
    access.inputs = new Map();
    access.outputs = new Map();
    window.__access = access;
    window.__requests = 0;
    window.__plug = on => {
      const port = { name: "electribe2 sampler", state: "connected" };
      for (const map of [access.inputs, access.outputs]) { if (on) map.set("p", port); else map.clear(); }
      access.dispatchEvent(new Event("statechange"));
    };
    navigator.requestMIDIAccess = async () => { window.__requests++; return access; };
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = async d => (d.name === "midi" ? { state: granted ? "granted" : "prompt" } : query(d));
  }, granted);
  await page.goto(h.url);
  return page;
}

test("native: the icon follows the USB port list, plugging in and out is shown within seconds", async () => {
  const page = await nativePage();
  await waitState(page, "absent");
  assert.equal(await badge(page).getAttribute("data-tone"), "off");
  assert.equal(await badge(page).getAttribute("title"), "Keine Electribe per USB angesteckt");
  await page.evaluate(() => { window.__plugged = true; });
  await waitState(page, "present");
  assert.equal(await badge(page).getAttribute("data-tone"), "ok");
  assert.equal(await page.locator("#cee-usb [role=status]").textContent(), "Electribe per USB angesteckt");
  await page.evaluate(() => { window.__plugged = false; });
  await waitState(page, "absent");
  assert.deepEqual(page.errors, []);
});

test("the icon stays in the navbar on every page", async () => {
  const page = await nativePage();
  await waitState(page, "absent");
  for (const tab of ["patcher", "emu", "start"]) {
    await page.click(`#cee-tab-${tab}`);
    assert.equal(await badge(page).isVisible(), true, tab);
  }
});

test("Web MIDI: statechange moves the icon at once, without polling the browser again", async () => {
  const page = await webPage();
  await waitState(page, "absent");
  await page.evaluate(() => window.__plug(true));
  await waitState(page, "present");
  await page.evaluate(() => window.__plug(false));
  await waitState(page, "absent");
  assert.equal(await page.evaluate(() => window.__requests), 1, "one access object, reused");
  assert.deepEqual(page.errors, []);
});

test("Web MIDI without the permission: the icon says it does not know, and MIDI is not requested", async () => {
  const page = await webPage({ granted: false });
  await waitState(page, "unknown");
  assert.match(await badge(page).getAttribute("title"), /unbekannt/);
  assert.equal(await page.evaluate(() => window.__requests), 0);
});

test("an open connection shows as verbunden", async () => {
  const page = await h.page({ device: true });
  await page.goto(`${h.url}#device`);
  await page.evaluate(() => window.__ceeStubReady);
  await page.click("#cee-connect");
  await waitState(page, "connected");
  assert.equal(await badge(page).getAttribute("title"), "Electribe verbunden");
  assert.equal(await badge(page).getAttribute("data-tone"), "ok");
});
