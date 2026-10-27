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

test("a plugged-in Electribe connects by itself, again after a pull, and not after a manual disconnect", async () => {
  const page = await plugged();
  await go(page, "device");
  await waitState(page, "connected");
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));

  await page.evaluate(() => window.__pull());
  await waitState(page, "absent");
  await page.evaluate(() => window.__plug());
  await waitState(page, "connected");

  await page.click("#cee-nav-state #cee-disconnect");
  await waitState(page, "present");
  await page.waitForTimeout(4000);
  assert.equal(await page.locator("#cee-usb").getAttribute("data-state"), "present", "the manual disconnect holds");

  await page.evaluate(() => window.__pull());
  await waitState(page, "absent");
  await page.evaluate(() => window.__plug());
  await waitState(page, "connected");
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
