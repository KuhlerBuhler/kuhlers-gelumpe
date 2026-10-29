import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import { makeFirmware } from "../helpers.mjs";

let h;
before(async () => { h = await setUp(); h.file("system.vsb", await makeFirmware()); });
after(async () => { await h.tearDown(); });

const waitState = (page, want) => page.waitForFunction(w => document.querySelector("#cee-usb")?.dataset.state === w, want);

/** The simulated Electribe as Web MIDI ports, MIDI allowed once it is in place; `__pull` and `__plug` move the cable. */
async function plugged() {
  const page = await h.page({ device: true, autoConnect: true });
  await page.addInitScript(() => {
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = async d => (d.name === "midi" ? { state: window.__ceeSim ? "granted" : "prompt" } : query(d));
    window.__pull = () => {
      const { access } = window.__ceeSim;
      window.__ports = [access.inputs.get("sim-in"), access.outputs.get("sim-out")];
      access.inputs.clear();
      access.outputs.clear();
      for (const port of window.__ports) port.state = "disconnected";
      access.onstatechange?.({ port: window.__ports[1] });
    };
    window.__plug = () => {
      const { access } = window.__ceeSim;
      const [input, output] = window.__ports;
      input.state = output.state = "connected";
      access.inputs.set(input.id, input);
      access.outputs.set(output.id, output);
    };
    // Whether the page ever said "connected" while the navbar still offered to connect.
    window.__gap = false;
    new MutationObserver(() => {
      const ok = document.querySelector(".cee-device-status .cee-status[data-tone=ok]");
      if (ok && !document.querySelector("#cee-nav-state #cee-disconnect")) window.__gap = true;
    }).observe(document, { subtree: true, childList: true, characterData: true });
  });
  await page.goto(h.url);
  await page.evaluate(() => window.__ceeStubReady);
  return page;
}

test("with Emulator as the mode a plugged-in Electribe is left alone; Echtes Gerät connects it, also after a fresh start", async () => {
  const page = await plugged();
  await waitState(page, "present");
  await page.waitForTimeout(4000);
  assert.equal(await page.locator("#cee-usb").getAttribute("data-state"), "present");
  await go(page, "device");
  await waitState(page, "connected");
  await page.reload();
  await page.evaluate(() => window.__ceeStubReady);
  await waitState(page, "connected");
  await go(page, "emu");
  assert.deepEqual(page.errors, []);
});

const autoSetting = page => page.evaluate(() => JSON.parse(localStorage.getItem("cee.settings") ?? "{}").autoConnect);
const pullAndPlug = async page => {
  await page.evaluate(() => window.__pull());
  await waitState(page, "absent");
  await page.evaluate(() => window.__plug());
};

test("a plugged-in Electribe connects by itself and again after a pull; the navbar button disconnects at once", async () => {
  const page = await plugged();
  await go(page, "device");
  await waitState(page, "connected");
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));
  const button = page.locator("#cee-nav-state #cee-disconnect");
  assert.equal(await button.textContent(), "Trennen", "while connected the button disconnects");
  assert.equal(await page.locator("#cee-nav-state #cee-connect").count(), 0, "no connect button while connected");
  assert.equal(await page.evaluate(() => window.__gap), false, "the button turns with the session, not later");

  await pullAndPlug(page);
  await waitState(page, "connected");
  await page.locator("#cee-nav-state #cee-disconnect").waitFor();
  assert.deepEqual(page.errors, []);
});

test("the disconnect button switches Automatisch verbinden off until the next connect", async () => {
  const page = await plugged();
  await go(page, "device");
  await waitState(page, "connected");

  await page.click("#cee-nav-state #cee-disconnect");
  await waitState(page, "present");
  const connect = page.locator("#cee-nav-state #cee-connect");
  assert.equal(await connect.textContent(), "Mit Electribe verbinden");
  assert.equal(await autoSetting(page), false, "the setting is off");
  await page.locator(".cee-toast .cee-toast-text", { hasText: "„Automatisch verbinden“ ist aus, bis du wieder verbindest." }).waitFor();
  assert.equal(await page.locator("#cee-set-autoConnect").isChecked(), false, "the settings page shows it off");

  await pullAndPlug(page);
  await waitState(page, "present");
  await page.waitForTimeout(4000);
  assert.equal(await page.locator("#cee-usb").getAttribute("data-state"), "present", "no automatic connect, also after a pull");

  await connect.click();
  await waitState(page, "connected");
  assert.equal(await autoSetting(page), true, "connecting by hand switches it back on");
  assert.equal(await page.locator("#cee-set-autoConnect").isChecked(), true);
  await pullAndPlug(page);
  await waitState(page, "connected");
  assert.deepEqual(page.errors, []);
});

test("a switch turned off in the settings stays off after connecting by hand", async () => {
  const page = await plugged();
  await go(page, "device");
  await waitState(page, "connected");
  await page.click("#cee-nav-state #cee-disconnect");
  await waitState(page, "present");
  // The person's own choice on the settings page: on, then off again.
  await page.evaluate(() => { const box = document.querySelector("#cee-set-autoConnect"); box.click(); box.click(); });
  assert.equal(await autoSetting(page), false);
  await page.click("#cee-nav-state #cee-connect");
  await waitState(page, "connected");
  assert.equal(await autoSetting(page), false, "the button only gives back what it switched off");
  assert.deepEqual(page.errors, []);
});

test("a device that never answers gets three toasts, the last opens the MIDI diagnostics", async () => {
  const page = await h.page({ autoConnect: true });
  await page.addInitScript(() => {
    const port = (id, type) => ({ id, type, name: "electribe2 sampler", state: "connected", open: async () => { throw new Error("Port belegt"); }, close: async () => {} });
    const access = { inputs: new Map([["i", port("i", "input")]]), outputs: new Map([["o", port("o", "output")]]), addEventListener() {}, onstatechange: null };
    window.__opens = 0;
    navigator.requestMIDIAccess = async () => access;
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = async d => (d.name === "midi" ? { state: "granted" } : query(d));
  });
  await page.goto(h.url);
  await go(page, "device");
  const toasts = page.locator(".cee-toast .cee-toast-text");
  await toasts.filter({ hasText: "Konnte nicht verbinden, versuche es erneut." }).waitFor();
  await toasts.filter({ hasText: "Immer noch keine Verbindung." }).waitFor();
  const last = page.locator(".cee-toast", { hasText: "Verbinden hat nicht geklappt." });
  await last.waitFor({ timeout: 20_000 });
  await page.waitForTimeout(8000);
  assert.equal(await page.locator(".cee-toast.err").count(), 1, "no fourth toast");
  await last.locator(".cee-toast-action").click();
  await page.locator("#cee-area-settings:not([hidden]) #cee-midi").waitFor();
  await page.waitForFunction(() => document.activeElement?.id === "cee-midi-rescan");
});
