import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import { makeFirmware } from "../helpers.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";

let h;
let fake;
let firmware;
before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin);
  firmware = await makeFirmware([]);
  h.file("system.vsb", firmware);
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

const toast = (page, text, kind) => page.locator(`#app-toasts .cee-toast${kind ? `[data-kind=${kind}]` : ""}`, { hasText: text });
const connected = page => page.locator("#cee-nav-state #cee-disconnect");

/** The real device (the Web MIDI stand-in); with `emulator` the page also gets the stand-in service. */
async function open({ emulator = false, run = false, query = "" } = {}) {
  const page = await h.page({ device: true });
  await page.goto(`${h.url}${query}${emulator ? `#emu=${fake.port}:${TOKEN}` : "#emu"}`);
  await page.evaluate(() => window.__ceeStubReady);
  if (run) {
    await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
    await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
    await page.click("#cee-e2-power");
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  }
  return page;
}

async function connect(page) {
  await go(page, "device");
  await page.click("#cee-connect");
  await connected(page).waitFor();
}

test("connected without an emulator: the navbar offers Trennen, it ends the connection and Verbinden is back", async () => {
  const page = await open();
  await connect(page);
  assert.equal(await page.locator("#cee-nav-state .cee-nav-fact").textContent(), "Gerät verbunden");
  await page.click("#cee-disconnect");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
  assert.equal(await connected(page).count(), 0);
  await toast(page, "Die Electribe ist getrennt.").waitFor();
  assert.equal(await page.evaluate(() => document.querySelector("#cee-rehearse-state").textContent), "", "the rehearsal line is gone with the connection");
  assert.equal(await page.locator("#cee-area-emu #cee-e2").isVisible(), true, "the drawing stays");
  assert.deepEqual(page.errors, []);
});

test("after Trennen the same device connects again", async () => {
  const page = await open();
  await connect(page);
  await page.click("#cee-disconnect");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
  await page.click("#cee-connect");
  await connected(page).waitFor();
  await page.click("#cee-disconnect");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
  assert.deepEqual(page.errors, []);
});

test("no firmware while connected: the hint asks for SYSTEM.VSB and Trennen still works", async () => {
  const page = await open();
  await connect(page);
  await page.locator("#cee-rehearse-state", { hasText: "noch keine Firmware" }).waitFor({ state: "attached" });
  assert.match(await page.locator("#cee-rehearse-state").textContent(), /SYSTEM\.VSB/);
  await page.click("#cee-disconnect");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
});

test("connected: the drawing shows the real device's display, also with the emulator off", async () => {
  const page = await open();
  await connect(page);
  await go(page, "emu");
  assert.equal(await page.locator("#cee-emu-lcd").isVisible(), true, "the display is not hidden as a switched-off emulator's");
  assert.deepEqual(page.errors, []);
});

test("firmware chosen, emulator off: connecting starts it behind the drawing and the rehearsal goes on, the connection stays", async () => {
  const page = await open({ emulator: true });
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await connect(page);
  await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ state: "attached", timeout: 15_000 });
  assert.equal(await connected(page).count(), 1, "the Electribe stays connected");
  assert.equal(await page.locator("#cee-emu-status", { hasText: "läuft" }).count(), 1);
  assert.deepEqual(page.errors, []);
});

test("firmware chosen after connecting: the emulator starts then and the rehearsal goes on", async () => {
  const page = await open({ emulator: true });
  await connect(page);
  await page.locator("#cee-rehearse-state", { hasText: "noch keine Firmware" }).waitFor({ state: "attached" });
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ state: "attached", timeout: 15_000 });
  assert.equal(await connected(page).count(), 1);
  assert.deepEqual(page.errors, []);
});

test("the power key while connected asks first; Abbrechen keeps the connection", async () => {
  const page = await open({ emulator: true, run: true });
  await connect(page);
  await go(page, "emu");
  await page.click("#cee-e2-power");
  const dialog = page.getByRole("button", { name: "Trennen und starten" });
  await dialog.waitFor();
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });
  await go(page, "device");
  assert.equal(await connected(page).count(), 1, "still connected");
});

test("the power key while connected: Trennen und starten ends the connection and starts the emulator", async () => {
  const page = await open({ emulator: true });
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await connect(page);
  await go(page, "emu");
  await page.click("#cee-e2-power");
  await page.getByRole("button", { name: "Trennen und starten" }).click();
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  await go(page, "device");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
  assert.equal(await page.locator("#cee-emu-lcd").isVisible(), true, "the display is there, not blank");
  assert.deepEqual(page.errors, []);
});

test("the power key while connected, no firmware chosen: the connection ends and the page says what is missing", async () => {
  const page = await open({ emulator: true });
  await connect(page);
  await go(page, "emu");
  await page.click("#cee-e2-power");
  await page.getByRole("button", { name: "Trennen und starten" }).click();
  await toast(page, "Erst eine Firmware laden", "error").waitFor();
  assert.equal(await page.locator("#cee-emu-offer").isVisible(), true, "the display offers the firmware again");
  assert.equal(await page.locator("#cee-e2-power").isVisible(), true);
});

test("no emulator service at all: starting after Trennen says why it cannot start", async () => {
  const page = await open();
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await connect(page);
  await go(page, "emu");
  await page.click("#cee-e2-power");
  await page.getByRole("button", { name: "Trennen und starten" }).click();
  await toast(page, "Der Emulator läuft nicht", "error").waitFor();
  await go(page, "device");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
});

test("with a running emulator, Trennen ends the rehearsal too and a new connection rehearses again", async () => {
  const page = await open({ emulator: true, run: true });
  await connect(page);
  await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
  await page.click("#cee-disconnect");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
  assert.equal(await page.locator("#cee-rehearse-state").textContent(), "");
  await page.click("#cee-connect");
  await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
  assert.equal(await page.locator("#cee-emu-status", { hasText: "läuft" }).count(), 1, "the emulator kept running");
});

test("unplugging while connected still ends in a state with a way forward", async () => {
  const page = await open();
  await connect(page);
  await page.evaluate(() => {
    const out = window.__ceeSim.access.outputs.get("sim-out");
    out.state = "disconnected";
    window.__ceeSim.access.onstatechange?.({ port: out });
  });
  await page.locator("#cee-nav-state #cee-connect").waitFor();
  assert.equal(await connected(page).count(), 0);
});

test("a device whose display cannot be read: the drawing says so instead of staying blank, and a tap disconnects", async () => {
  const page = await open({ query: "?noram" });
  await connect(page);
  await go(page, "emu");
  const offer = page.locator("#cee-emu-offer");
  await offer.waitFor();
  assert.match(await offer.textContent(), /Electribe verbunden/);
  await offer.click();
  await page.getByRole("button", { name: "Trennen und starten" }).click();
  await page.locator("#cee-emu-offer", { hasText: "SYSTEM.VSB" }).waitFor();
  await go(page, "device");
  await page.locator("#cee-nav-state #cee-connect").waitFor();
});
