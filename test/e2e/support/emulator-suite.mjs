import { before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go, pickPreset } from "../harness.mjs";
import { tempDir } from "../../support/lifetime.mjs";
import { fakeService, TOKEN } from "./fake-emu.mjs";
import { makeFirmware, makeRecord } from "../../helpers.mjs";
import { field, writeRaw } from "../../../src/map/index.mjs";
import { tableEntry } from "../../../src/map/address.mjs";
import { only } from "./parts.mjs";

/** The tests of the emulator page, every `parts`-th one from `index`: the parts run as files of their own, side by side. */
export function emulatorSuite(index, parts) {
  const test = only(index, parts);
  // The service is a stand-in, but the folders it would use are throwaway ones: nothing here may touch ~/.gelumpe.
  const SD_DIR = tempDir("cee-e2e-sd-");
  const FLASH_DIR = tempDir("cee-e2e-flash-");
  process.env.GELUMPE_SD_DIR = SD_DIR;
  process.env.GELUMPE_FLASH_DIR = FLASH_DIR;
  let h;
  let fake;

  before(async () => {
    h = await setUp();
    fake = await fakeService(new URL(h.url).origin, { sdDir: SD_DIR });
  });
  after(async () => {
    fake.server.closeAllConnections?.();
    fake.server.close();
    await h.tearDown();
  });

  /** The sidebar blocks start closed (and remember it); open one the way a person does. */
  async function openSub(page, id) {
    if (!(await page.locator(`#${id}`).evaluate(n => n.open))) await page.click(`#${id} > summary`);
  }

  /** Load a firmware in the sidebar, then boot with the drawn power key. */
  async function powerOn(page, file) {
    await openSub(page, "cee-emu-setup");
    await page.setInputFiles("#cee-emu-vsb", typeof file === "string" ? file : h.file("system.vsb", file));
    await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
    await page.click("#cee-e2-power");
  }

  const pixel = (page, x, y) => page.evaluate(([px, py]) => {
    const c = document.querySelector("#cee-emu-lcd");
    return Array.from(c.getContext("2d").getImageData(px, py, 1, 1).data.slice(0, 3));
  }, [x, y]);

  test("emulator: the link connects, the firmware goes to the service and the display is drawn", async () => {
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.locator("#cee-area-emu").waitFor({ state: "visible" });
    assert.equal(new URL(page.url()).hash.includes(TOKEN), false, "the key leaves the address bar");
    assert.equal(await page.locator("#cee-emu-setup").evaluate(n => n.open), false, "the sidebar block starts closed");
    assert.equal(await page.locator("#cee-emu-vsb ~ .ui-dropzone-title").isVisible(), false, "the dropzone is hidden until the block is opened");
    await openSub(page, "cee-emu-setup");
    assert.equal(await page.locator("#cee-emu-vsb ~ .ui-dropzone-title").isVisible(), true);
    assert.equal(await page.locator("#cee-emu-flash").count(), 0, "there is no flash import any more");
    await powerOn(page, new Uint8Array(0x200100));
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    assert.equal(fake.seen.firmware, 0x200100);
    assert.equal(fake.seen.flash, 0, "the flash stays in the service; the page sends none");
    assert.deepEqual(fake.seen.start, {});
    await page.waitForFunction(() => document.querySelector("#cee-e2").dataset.power === "on");
    const lit = await pixel(page, 0, 0);
    const dark = await pixel(page, 1, 0);
    assert.notDeepEqual(lit, dark, "a set bit is drawn differently from a clear one");
    assert.deepEqual(await pixel(page, 127, 7), lit, "bit 7 is the bottom row of the page");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the SD card dialog behind the navbar talks to the service the page is linked to", async () => {
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    assert.equal(await page.locator("#cee-emu-card").evaluate(n => n.open), false, "the dialog starts closed");
    await page.click("#cee-nav-state #cee-emu-card-open");
    await page.locator("#cee-sd-status", { hasText: "Nicht eingelegt" }).waitFor();
    assert.ok(fake.seen.sd > 0, "the card state came from the linked service");
    const card = page.locator("#cee-sd-inserted");
    assert.equal(await card.isChecked(), false);
    await page.locator("label.ui-switch", { hasText: "Karte einlegen" }).click();
    await page.waitForFunction(() => document.querySelector("#cee-sd-inserted").checked && !document.querySelector("#cee-sd-inserted").disabled);
    await page.locator("#cee-sd-status", { hasText: "Eingelegt" }).waitFor();
    await page.click("#cee-sd-open");
    await page.waitForFunction(() => !document.querySelector("#cee-sd-open").disabled);
    await page.locator("label.ui-switch", { hasText: "Karte einlegen" }).click();
    await page.waitForFunction(() => !document.querySelector("#cee-sd-inserted").checked && !document.querySelector("#cee-sd-inserted").disabled);
    assert.deepEqual(fake.seen.sdCalls.slice(-3), ["/sd/insert", "/sd/open", "/sd/eject"], "insert, open and eject went to the linked service");
    assert.equal(await page.locator("#cee-emu-card").evaluate(n => n.tagName === "DIALOG" && n.closest("#cee-sidebar") === null), true, "the card is a dialog, not a sidebar block");
    assert.equal(await page.locator("#cee-emu-card-title").textContent(), "SD-Karte");
    assert.equal(await page.locator("#cee-area-emu #cee-emu-card").count(), 0, "nothing of it stays in the page");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: a wrong file size is refused before anything is sent, and a missing service is named", async () => {
    const page = await h.page();
    await page.goto(`${h.url}#emu=1:${TOKEN}`);
    await page.locator("#cee-emu-status", { hasText: "getrennt" }).waitFor();
    await openSub(page, "cee-emu-setup");
    await page.setInputFiles("#cee-emu-vsb", h.file("short.vsb", new Uint8Array(100)));
    await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "100 Byte" }).waitFor();

    // Against a live service: the power key finds no firmware and sends nothing.
    const linked = await h.page();
    await linked.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await openSub(linked, "cee-emu-setup");
    await linked.setInputFiles("#cee-emu-vsb", h.file("short.vsb", new Uint8Array(100)));
    await linked.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "100 Byte" }).waitFor();
    fake.seen.firmware = 0;
    fake.seen.start = null;
    await linked.click("#cee-e2-power");
    await linked.waitForFunction(() => document.querySelector("#cee-e2").dataset.power === "on");   // the NO FIRMWARE screen
    assert.equal(fake.seen.firmware, 0, "no firmware went out");
    assert.equal(fake.seen.start, null, "nothing was started");
  });

  test("emulator: Korg's original firmware is named as such, without a box of what it lacks", async () => {
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await openSub(page, "cee-emu-setup");
    const files = page.locator("#cee-emu-vsb ~ .ui-dropzone-files");
    // The stand-in image with the run Hacktribe's code sits in erased is what Korg's build looks like.
    const stock = await makeFirmware();
    stock.fill(0xff, 0x170100, 0x170140);
    await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", stock));
    await files.filter({ hasText: "Korgs Original-Firmware 2.02, erkannt" }).waitFor();
    assert.equal(await page.locator("#cee-emu-build").count(), 0, "no box listing what Korg's build lacks");
    assert.equal(await page.locator("#cee-script-build").count(), 0, "no note about what Korg's build lacks on the plugin page");
    // The same file with BLECH's SysEx hooks (two branches into 0xC0172100 to 0xC0173800) is still Korg's build, and still no box.
    const blech = Uint8Array.from(stock);
    const view = new DataView(blech.buffer);
    for (const [site, target] of [[0xc0026a8c, 0xc0172100], [0xc0026418, 0xc01721fc]]) view.setUint32(site - 0xc0000000 + 0x100, 0xea000000 | (((target - (site + 8)) >> 2) & 0xffffff), true);
    await page.setInputFiles("#cee-emu-vsb", h.file("blech.vsb", blech));
    await files.filter({ hasText: "blech.vsb: Korgs Original-Firmware 2.02, erkannt" }).waitFor();
    assert.equal(await page.locator("#cee-emu-build").count(), 0, "no box for the BLECH build either");
    // The next file is Hacktribe's build: the note goes.
    await page.setInputFiles("#cee-emu-vsb", h.file("hacktribe.vsb", await makeFirmware()));
    await files.filter({ hasText: "hacktribe.vsb: erkannt." }).waitFor();
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the device front sends panel inputs and shows the LEDs", async () => {
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await powerOn(page, new Uint8Array(0x200100));
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    await page.waitForFunction(() => document.querySelector("#cee-e2-sequencer").style.getPropertyValue("--cee-e2-glow") === "1");
    assert.equal(await page.locator("#cee-e2-pad1").evaluate(n => n.style.getPropertyValue("--cee-e2-blue")), "1", "a pad LED is on or off, as on the device");
    assert.equal(await page.getAttribute("#cee-e2-pad1", "data-tone"), "blue");
    fake.seen.inputs.length = 0;

    await page.click("#cee-e2-menu");
    await page.locator("#cee-e2-pad16").focus();
    await page.keyboard.down("Enter");
    await page.keyboard.up("Enter");
    await page.locator("#cee-e2-cutoff").focus();
    await page.keyboard.press("ArrowDown");
    await page.locator("#cee-e2-level").focus();
    await page.keyboard.press("End");
    await page.locator("#cee-e2-touchpad").scrollIntoViewIfNeeded();
    const pad = await page.locator("#cee-e2-touchpad").boundingBox();
    await page.mouse.move(pad.x + pad.width - 8, pad.y + 8);
    await page.mouse.down();
    await page.mouse.up();
    const until = Date.now() + 5000;
    while (fake.seen.inputs.length < 8 && Date.now() < until) await new Promise(r => setTimeout(r, 50));
    const touch = fake.seen.inputs[6];
    assert.ok(touch?.x > 950 && touch.y > 950, `top right corner, got ${JSON.stringify(touch)}`);
    assert.deepEqual(fake.seen.inputs, [
      { kind: "button", index: 9, down: true }, { kind: "button", index: 9, down: false },
      { kind: "pad", index: 15, down: true, velocity: 100 }, { kind: "pad", index: 15, down: false },
      { kind: "encoder", index: 2, delta: -1 },
      { kind: "knob", index: 0, value: 255 },
      { kind: "touch", x: touch.x, y: touch.y, down: true }, { kind: "touch", down: false },
    ]);
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the terminal page connects to the running emulator over its MIDI, and the device area shows it", async () => {
    for (const context of h.browser.contexts()) await context.close();   // pages of earlier tests also talk to the service
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.locator("#cee-emu-status", { hasText: "bereit" }).waitFor();
    fake.seen.midi.length = 0;
    await page.click("#cee-tab-scripts");
    await page.click("#cee-tab-console");
    await page.click("#cee-term-connect");
    await page.locator(".cee-device-status", { hasText: "Emulator läuft nicht" }).waitFor({ state: "attached" });
    assert.deepEqual(fake.seen.midi, [], "nothing sent to a stopped emulator");

    await go(page, "emu");
    await powerOn(page, new Uint8Array(0x200100));
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    await page.click("#cee-tab-scripts");
    await page.click("#cee-tab-console");
    await page.click("#cee-term-connect");
    await go(page, "device");
    await page.locator(".cee-facts", { hasText: "Globaler Kanal10" }).waitFor({ state: "attached", timeout: 10_000 });
    assert.equal(fake.seen.midi[0], "f042500000f7", "the device search went to the emulator");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the page sends no MIDI while the firmware starts and goes ahead when the service says it is booted", async t => {
    for (const context of h.browser.contexts()) await context.close();
    fake.hooks.holdBoot = true;
    t.after(() => { fake.hooks.holdBoot = false; });
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.locator("#cee-emu-status", { hasText: "bereit" }).waitFor();
    fake.seen.midi.length = 0;
    await go(page, "emu");
    await powerOn(page, new Uint8Array(0x200100));
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    await page.click("#cee-tab-scripts");
    await page.click("#cee-tab-console");
    await page.click("#cee-term-connect");
    await go(page, "device");
    await page.locator(".cee-device-status", { hasText: "Emulator läuft nicht" }).waitFor({ state: "attached" });
    await page.waitForTimeout(500);
    assert.deepEqual(fake.seen.midi, [], "nothing goes to a firmware that has not reached its main screen");
    fake.broadcast("status", { state: "running", booted: true, device_ms: 1500, speed: 1 });
    await page.click("#cee-tab-scripts");
    await page.click("#cee-tab-console");
    await page.click("#cee-term-connect");
    await go(page, "device");
    await page.locator(".cee-facts", { hasText: "Globaler Kanal10" }).waitFor({ state: "attached", timeout: 10_000 });
    assert.equal(fake.seen.midi[0], "f042500000f7", "the device search goes out once the service said booted");
    assert.deepEqual(page.errors, []);
  });

  const MANAGER = 0xc06c2210, SCREEN = 0xc06ca6a0, EDIT = 0xc06c41c0, PATTERN = 0xc06b2798;
  /** A master preset the gate lets through with one warning: switch cross-fade, no second unit. */
  function masterPreset() {
    const r = makeRecord("mfx", { name: "Short Delay", devices: { mfx: 0x3b } });
    r.map = [{ source: 0x41, chain: 0x0a, param: 4, low: 127, high: 0 }, { source: 0x41, chain: 0x0a, param: 0, low: 0, high: 127 }];
    for (const stage of [0, 1]) writeRaw(r.bytes, field("fx.stage.device"), [stage], 0);
    return r;
  }
  const sidebarFirmware = () => makeFirmware([
    { kind: "ifx", slot: 50, record: makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } }) },
    { kind: "ifx", slot: 7, record: makeRecord("ifx", { name: "Other Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } }) },
    { kind: "mfx", slot: 2, record: masterPreset() },
  ]);

  /** Main screen, part 1, part 1 on insert 50, pattern on master 2. */
  function baseScreen() {
    fake.word(0xc03404c0, MANAGER);
    fake.word(MANAGER + 0x20, SCREEN);
    fake.word(MANAGER + 0x24, 0);
    fake.word(MANAGER + 0x2c, 1);
    fake.word(0xc0348880, EDIT);
    fake.word(EDIT + 0x14, 0);
    fake.word(0xc033e6a4, PATTERN);
    fake.poke(PATTERN + 4 + 0x800 + 33, [49]);
    fake.poke(PATTERN + 4 + 61, [1]);
  }

  async function sidebarPage() {
    // Pages of earlier tests still poll the service, and its replies go to every page.
    for (const context of h.browser.contexts()) await context.close();
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await powerOn(page, await sidebarFirmware());
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    // No connect step: the sidebar and the terminal read the running emulator through the shared probe.
    return page;
  }

  test("terminal: KORG puts a picture into the emulator's display RAM and reads the screen state", async t => {
    baseScreen();
    const page = await sidebarPage();
    await page.click("#cee-tab-scripts");
    await page.click("#cee-tab-console");
    await page.click("#cee-term-connect");
    await page.locator(".cee-facts", { hasText: "Globaler Kanal10" }).waitFor({ state: "attached", timeout: 15_000 });
    fake.hooks.midiDelayMs = 200;
    t.after(() => { fake.hooks.midiDelayMs = 0; });
    const run = async code => {
      await page.fill("#cee-term-input", code);
      await page.press("#cee-term-input", "Enter");
      await page.locator(".cee-term-in", { hasText: `> ${code}` }).last().waitFor();
    };
    await run("KORG.screen.set((x, y) => y === 0)");
    // 1024 bytes at 200 ms per MIDI message: about 10 s here, a loaded CI runner needs more than 15 s.
    await page.locator(".cee-term-line", { hasText: "Bild steht im Display" }).waitFor({ timeout: 45_000 }).catch(async err => {
      const lines = await page.locator(".cee-term-line, .cee-term-in").allTextContents();
      throw new Error(`${err.message}\nterminal:\n${lines.slice(-12).join("\n")}`);
    });
    const display = Array.from({ length: 1024 }, (_, i) => fake.ram.get(0xc031b310 + i) ?? 0);
    assert.ok(display.slice(0, 128).every(b => b === 0x01) && display.slice(128).every(b => b === 0), "only the top row is lit");
    await run("KORG.screen.state()");
    await page.locator(".cee-term-line", { hasText: "Hauptbildschirm" }).waitFor();
    await page.click("#cee-term-connect");
    await run("KORG.screen.set((x, y) => y === 0)");
    await page.waitForFunction(() => [...document.querySelectorAll(".cee-term-out")].filter(n => n.textContent.includes("Bild steht im Display")).length === 2);
    await run("KORG.nope()");
    await page.locator(".cee-term-error").first().waitFor();
    assert.deepEqual(page.errors, []);
  });

  /** The Presets page with its switch "Folgt dem Gerät" on. */
  async function followPage() {
    const page = await sidebarPage();
    await page.click("#cee-tab-fx");
    await page.locator("#cee-fx-slot").waitFor();
    await page.locator("label:has(#cee-fx-follow)").click();
    return page;
  }

  test("emulator: with the switch on, the Presets page opens the effect the device shows", async () => {
    baseScreen();
    const page = await followPage();
    await page.locator("#cee-emu-where", { hasText: "Hauptbildschirm · Part 1" }).waitFor({ state: "attached", timeout: 5000 });
    const other = "7";
    await page.selectOption("#cee-fx-slot", other);
    await page.waitForTimeout(1500);
    assert.equal(await page.inputValue("#cee-fx-slot"), other, "the main screen shows no effect and leaves the choice alone");

    fake.word(MANAGER + 0x24, 0xc06cb2e0);           // the IFX TYPE window
    fake.word(MANAGER + 0x30, 23);
    await page.locator("#cee-emu-where", { hasText: "Fenster IFX TYPE" }).waitFor({ state: "attached", timeout: 5000 });
    await page.waitForFunction(() => document.querySelector("#cee-fx-slot")?.value === "50", null, { timeout: 5000 });
    assert.equal(await page.locator("input[name=cee-fx-kind]:checked").getAttribute("value"), "ifx");

    fake.word(MANAGER + 0x24, 0);                    // the window closes; the editor stays
    await page.locator("#cee-emu-where", { hasText: "Hauptbildschirm" }).waitFor({ state: "attached", timeout: 5000 });
    assert.equal(await page.inputValue("#cee-fx-slot"), "50");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: a change sent from the Presets page on MFX TYPE lands in RAM and the page is reopened", async () => {
    baseScreen();
    fake.word(MANAGER + 0x2c, 3);                    // pattern menu
    fake.word(SCREEN + 0x2c, 5);                     // MFX TYPE
    const master = tableEntry("table.mfx", 1);       // RAM holds what the firmware file holds
    fake.poke(master.ram, Array.from((await sidebarFirmware()).subarray(master.file, master.file + master.size)));
    const page = await followPage();
    await page.locator("#cee-emu-where", { hasText: "MFX TYPE" }).waitFor({ state: "attached", timeout: 5000 });
    await page.waitForFunction(() => document.querySelector("#cee-fx-slot")?.value === "2", null, { timeout: 5000 });
    const name = page.locator("#cee-fx-editor input[type=text]").first();
    await name.fill("Long Delay");
    await name.press("Enter");
    fake.seen.inputs.length = 0;
    await page.click("#cee-send");
    const ok = page.locator("dialog button[value=ok]");
    const job = page.locator("#cee-fx .ui-job .cee-status").filter({ hasText: /Fertig|Fehlgeschlagen/ });
    await Promise.race([ok.waitFor().then(() => ok.click(), () => {}), job.waitFor()]);   // a gate warning asks first
    await job.waitFor({ timeout: 15_000 });
    assert.equal(await job.textContent(), "Fertig");
    await page.locator("#app-toasts .cee-toast", { hasText: "EXIT, MENU" }).waitFor();
    const until = Date.now() + 3000;
    while (fake.seen.inputs.length < 4 && Date.now() < until) await new Promise(r => setTimeout(r, 50));
    assert.deepEqual(fake.seen.inputs, [
      { kind: "button", index: 0x0d, down: true }, { kind: "button", index: 0x0d, down: false },
      { kind: "button", index: 0x09, down: true }, { kind: "button", index: 0x09, down: false },
    ]);

    assert.deepEqual(page.errors, []);
  });

  test("emulator: with the device connected, an edit goes to the emulator first and then to the device", async () => {
    for (const context of h.browser.contexts()) await context.close();
    const gate = makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64, 64] } });
    gate.setDevice("mfx", 0x27);
    gate.map = [{ source: 0x42, chain: 0x00, param: 0, low: 0, high: 127 }];
    const firmware = await makeFirmware([{ kind: "ifx", slot: 50, record: gate }]);
    const vsb = h.file("system.vsb", firmware);           // the Web MIDI stand-in loads this one too
    const slot = tableEntry("table.ifx", 49);
    fake.poke(slot.ram, Array.from(firmware.subarray(slot.file, slot.file + slot.size)));

    const page = await h.page({ device: true });
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.evaluate(() => window.__ceeStubReady);
    await powerOn(page, vsb);
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    await go(page, "device");
    await page.click("#cee-connect");
    await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
    await page.click("#cee-tab-fx");
    await page.locator("#cee-fx-slot").waitFor({ timeout: 15_000 });   // the firmware comes from the emulator, there is no file picker here
    assert.equal(await page.locator("#cee-vsb").count(), 0);
    await pickPreset(page, 50);
    const slider = page.locator("#cee-fx-editor input.ui-range").first();
    await slider.focus();
    await slider.press("ArrowRight");
    fake.seen.midi.length = 0;
    await page.click("#cee-send");
    const ok = page.locator("dialog button[value=ok]");
    const job = page.locator("#cee-area-fx .ui-job .cee-status").filter({ hasText: /Fertig|Fehlgeschlagen/ });
    await Promise.race([ok.waitFor().then(() => ok.click(), () => {}), job.waitFor()]);
    await job.waitFor({ timeout: 15_000 });
    assert.equal(await job.textContent(), "Fertig");
    const writes = fake.seen.midi.filter(m => m.slice(12, 14) === "54");
    assert.ok(writes.length > 0, "the emulator got the record");
    const onDevice = await page.evaluate(([a, n]) => Array.from(window.__ceeSim.device.peek(a, n)), [slot.ram, slot.size]);
    const inEmulator = Array.from({ length: slot.size }, (_, i) => fake.ram.get(slot.ram + i) ?? 0);
    assert.deepEqual(onDevice, inEmulator, "device and emulator hold the same record");
    assert.notDeepEqual(onDevice, Array.from(firmware.subarray(slot.file, slot.file + slot.size)));
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the flash lives in the service; the page offers no flash import and sends none, also with a device connected", async () => {
    for (const context of h.browser.contexts()) await context.close();
    h.file("system.vsb", await makeFirmware());
    const page = await h.page({ device: true });
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.evaluate(() => window.__ceeStubReady);
    assert.deepEqual(await page.locator("#cee-sub-emu > .ui-details > summary").allTextContents(), ["Firmware (VSB)", "SD-Karte"], "no Flash block in the sidebar");
    fake.seen.flash = 0;
    fake.seen.firmware = 0;
    await powerOn(page, await makeFirmware());
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    await go(page, "device");
    await page.click("#cee-connect");
    await page.locator(".cee-facts", { hasText: "Hacktribe" }).waitFor({ state: "attached" });
    await go(page, "emu");
    assert.equal(await page.locator("#cee-emu-flash, #cee-emu-read-flash, #cee-emu-save-flash, #cee-emu-flash-job").count(), 0, "no flash controls anywhere");
    assert.ok(fake.seen.firmware > 0, "the firmware went to the service");
    assert.equal(fake.seen.flash, 0, "no flash went with it");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the attached device's display is read from its RAM and drawn in the emulator's drawing", async () => {
    for (const context of h.browser.contexts()) await context.close();
    const page = await h.page({ device: true });
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.evaluate(async () => {
      await window.__ceeStubReady;
      const at = window.__ceeSim.device.locate(0xc031b310, 1024, "test");
      at.buf[at.offset] = 0x01;                          // top-left pixel
    });
    await go(page, "device");
    await page.click("#cee-connect");
    await page.waitForFunction(() => { const c = document.querySelector("#cee-emu-lcd").getContext("2d"); const d = c.getImageData(0, 0, 2, 1).data; return d[0] !== d[4] || d[1] !== d[5] || d[2] !== d[6]; }, null, { timeout: 10_000 });
    assert.notDeepEqual(await pixel(page, 0, 0), await pixel(page, 1, 0), "the set bit is drawn");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: the attached device's LEDs are read from its RAM and drawn on the keys", async () => {
    for (const context of h.browser.contexts()) await context.close();
    const page = await h.page({ device: true });
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.evaluate(async () => {
      await window.__ceeStubReady;
      const at = window.__ceeSim.device.locate(0xc06c2b14, 0x4b * 8 + 3, "test");
      at.buf[at.offset + 0x09 * 8 + 2] = 255;            // PLAY, red/white side
      at.buf[at.offset + 0x12 * 8 + 2] = 255;            // REC
    });
    const lit = id => page.locator(`#cee-e2-${id}`).getAttribute("data-lit");
    assert.equal(await lit("play"), "off", "dark before the device is attached");
    await go(page, "device");
    await page.click("#cee-connect");
    await page.waitForFunction(() => document.querySelector("#cee-e2-play").dataset.lit === "on", null, { timeout: 10_000 });
    assert.equal(await lit("rec"), "on");
    assert.equal(await lit("stop"), "off");
    await page.evaluate(() => {
      const at = window.__ceeSim.device.locate(0xc06c2b14, 0x4b * 8 + 3, "test");
      at.buf[at.offset + 0x09 * 8 + 2] = 0;
    });
    await page.waitForFunction(() => document.querySelector("#cee-e2-play").dataset.lit === "off", null, { timeout: 10_000 });
    assert.equal(await lit("rec"), "on", "only the LED that changed went out");
    assert.equal(await page.locator("#cee-led-note").textContent(), "");
    assert.deepEqual(page.errors, []);
  });

  async function runningPage() {
    for (const context of h.browser.contexts()) await context.close();
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await powerOn(page, new Uint8Array(0x200100));
    await page.waitForFunction(() => document.querySelector("#cee-e2").dataset.power === "on");
    fake.seen.inputs.length = 0;
    return page;
  }

  const settle = ms => new Promise(r => setTimeout(r, ms));

  test("emulator: the drawn power key boots, the page stays quiet, the display is dark while it is off", async () => {
    for (const context of h.browser.contexts()) await context.close();
    const page = await h.page();
    await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
    await page.locator("#cee-e2-power").waitFor();
    assert.equal(await page.locator("#cee-emu-start, #cee-emu-stop").count(), 0, "no Start or Stop button; the power key does it");
    assert.equal(await page.locator("#cee-e2").getAttribute("data-power"), "off");
    assert.equal(await page.locator("#cee-emu-lcd").evaluate(n => getComputedStyle(n).visibility), "hidden", "no display while off");
    assert.equal(await page.locator("#cee-emu-intro, #cee-emu-facts, #cee-e2-adapter").count(), 0, "no intro text, no device time, no adapter switch");
    assert.equal(await page.locator("#cee-e2 #cee-e2-power").count(), 1, "the power key is part of the drawing");
    assert.equal(await page.getAttribute("#cee-e2-power", "title") !== null, true, "the hover text stays");

    fake.seen.start = null;
    await powerOn(page, new Uint8Array(0x200100));
    await page.waitForFunction(() => document.querySelector("#cee-e2").dataset.power === "on");
    assert.deepEqual(fake.seen.start, {}, "the key started the firmware in the service");
    assert.equal(await page.locator("#cee-emu-lcd").evaluate(n => getComputedStyle(n).visibility), "visible");
    assert.match(await page.locator("#cee-emu-status").getAttribute("class"), /ui-sr-only/, "a running device needs no status pill");
    assert.match(await page.locator("#cee-emu-status").textContent(), /läuft/, "a screen reader still hears it");
    assert.equal(await page.locator("#cee-emu-setup").evaluate(n => n.open), false, "the firmware block folds away once it runs");

    fake.broadcast("status", { state: "off" });
    await page.waitForFunction(() => document.querySelector("#cee-e2").dataset.power === "off");
    fake.broadcast("status", { state: "crashed", error: "Abgestürzt." });
    await page.locator("#cee-emu-status:not(.ui-sr-only)", { hasText: "abgestürzt" }).waitFor();
    assert.deepEqual(page.errors, []);
  });

  test("emulator: detented encoders click, the wheel is paced, a click on a knob opens a value popup", async () => {
    const page = await runningPage();
    const value = await page.locator("#cee-e2-value").boundingBox();
    const [x, y] = [value.x + value.width / 2, value.y + value.height / 2];
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x, y - 42, { steps: 6 });
    await page.mouse.up();
    await settle(200);
    assert.deepEqual(fake.seen.inputs, [1, 1, 1].map(delta => ({ kind: "encoder", index: 0, delta })), "42 px of drag is three clicks");

    fake.seen.inputs.length = 0;
    await page.locator("#cee-e2-value").evaluate(async n => {
      for (let i = 0; i < 6; i++) { n.dispatchEvent(new WheelEvent("wheel", { deltaY: -100, bubbles: true, cancelable: true })); await new Promise(r => setTimeout(r, 10)); }
    });
    await settle(200);
    assert.equal(fake.seen.inputs.length, 1, "six notches within 60 ms are one click");

    fake.seen.inputs.length = 0;
    await page.locator("#cee-e2-level").click();
    await page.locator("#cee-e2-pop").waitFor();
    assert.equal(await page.evaluate(() => document.activeElement.id), "cee-e2-pop-number");
    await page.fill("#cee-e2-pop-number", "100");
    await settle(200);
    assert.deepEqual(fake.seen.inputs, [{ kind: "knob", index: 0, value: 200 }]);
    assert.equal(await page.getAttribute("#cee-e2-level", "aria-valuenow"), "100");
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#cee-e2-pop").isHidden(), true);
    assert.equal(await page.evaluate(() => document.activeElement.id), "cee-e2-level");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: SHIFT latches on a short click and lets go on the next, and acts like the key when held", async () => {
    const page = await runningPage();
    await page.click("#cee-e2-shift");
    await settle(100);
    assert.equal(await page.getAttribute("#cee-e2-shift", "aria-pressed"), "true");
    await page.locator("#cee-e2-pitch").focus();
    await page.keyboard.press("ArrowUp");
    await settle(100);
    await page.click("#cee-e2-shift");
    await settle(100);
    assert.deepEqual(fake.seen.inputs, [
      { kind: "button", index: 10, down: true },
      { kind: "knob", index: 2, value: 130 },
      { kind: "button", index: 10, down: false },
    ]);
    assert.equal(await page.getAttribute("#cee-e2-shift", "aria-pressed"), "false");

    fake.seen.inputs.length = 0;
    const box = await page.locator("#cee-e2-shift").boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await settle(500);
    await page.mouse.up();
    await settle(100);
    assert.deepEqual(fake.seen.inputs, [{ kind: "button", index: 10, down: true }, { kind: "button", index: 10, down: false }], "held longer than a click it is released on letting go");
    assert.equal(await page.getAttribute("#cee-e2-shift", "data-latched"), "false");
  });

  test("emulator: whole buttons and pads light, a pressed pad is red, a pressed blue pad is purple", async () => {
    const page = await runningPage();
    fake.broadcast("leds", { 0x0b: 255, 0x2d: 255 });         // WRITE, blue LED of pad 1
    await page.waitForFunction(() => document.querySelector("#cee-e2-write").dataset.lit === "on");
    const fill = sel => page.locator(sel).evaluate(n => getComputedStyle(n).backgroundColor);
    // A pad stays dark; its LED is a glow on ::after, coloured by the tone.
    const dots = sel => page.locator(sel).evaluate(n => { const g = getComputedStyle(n, "::after"); return [g.backgroundImage, g.opacity]; });
    assert.notEqual(await fill("#cee-e2-write"), await fill("#cee-e2-menu"), "the whole button changes");
    assert.match(await page.getAttribute("#cee-e2-write", "aria-label"), /leuchtet/, "lit is also said in words");
    assert.equal(await page.getAttribute("#cee-e2-pad1", "data-tone"), "blue");

    const press = async sel => { const b = await page.locator(sel).boundingBox(); await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2); await page.mouse.down(); };
    await press("#cee-e2-pad2");
    assert.equal(await page.getAttribute("#cee-e2-pad2", "data-tone"), "red");
    await page.mouse.up();
    assert.equal(await page.getAttribute("#cee-e2-pad2", "data-tone"), "off", "letting go leaves the colour to the LEDs");
    await press("#cee-e2-pad1");
    assert.equal(await page.getAttribute("#cee-e2-pad1", "data-tone"), "purple");
    await settle(400);
    const purple = await dots("#cee-e2-pad1");
    await page.mouse.up();
    assert.equal(await page.getAttribute("#cee-e2-pad1", "data-tone"), "blue");
    await settle(400);
    assert.notDeepEqual(purple, await dots("#cee-e2-pad1"), "the glow turns from purple to blue when the press ends");

    fake.broadcast("leds", { [0x2c + 2 * 5]: 255 });            // part mute mode: the firmware lights pad 6 and switches it off again
    await page.waitForFunction(() => document.querySelector("#cee-e2-pad6").dataset.tone === "red");
    fake.broadcast("leds", { [0x2c + 2 * 5]: 0 });
    await page.waitForFunction(() => document.querySelector("#cee-e2-pad6").dataset.tone === "off");
    assert.deepEqual(page.errors, []);
  });

  test("emulator: REC, STOP and PLAY are symbols with a name, the keys below them are text", async () => {
    const page = await runningPage();
    for (const [id, name] of [["rec", "REC (Aufnahme)"], ["stop", "STOP"], ["play", "PLAY (Wiedergabe)"]]) {
      const b = page.locator(`#cee-e2-${id}`);
      assert.equal(await b.locator("svg").count(), 1, id);
      assert.equal((await b.textContent()).trim(), "", `${id} carries no text`);
      assert.equal(await b.getAttribute("aria-label"), name);
      assert.equal(await b.getAttribute("title"), name);
    }
    assert.equal((await page.locator("#cee-e2-tap").textContent()).trim(), "TAP");
    for (const [id, text] of [["gateArp", "GATE ARP"], ["touchScale", "TOUCH SCALE"], ["masterFx", "MASTER FX"], ["mfxHold", "MFX HOLD"]]) {
      const b = page.locator(`#cee-e2-${id}`);
      assert.equal(await b.locator("svg").count(), 0, `${id} is text again`);
      assert.equal((await b.textContent()).trim(), text);
      const label = b.locator(".cee-e2-label");
      const [box, text1] = await Promise.all([b.boundingBox(), label.evaluate(n => n.getBoundingClientRect().height < parseFloat(getComputedStyle(n).fontSize) * 1.6)]);
      assert.ok(text1, `${id} stays on one line`);
      assert.ok(await label.evaluate(n => n.scrollWidth <= n.parentElement.clientWidth), `${id} fits its key (${box.width}px)`);
    }
    assert.equal(await page.locator("#cee-e2-lcd, #cee-emu-lcd").evaluate(n => getComputedStyle(n).borderRadius), "0px", "the display has square corners");
  });

  test("emulator: the drawing puts labels, section titles and the AMP EG key where the device has them", async () => {
    const page = await runningPage();
    const box = sel => page.locator(sel).first().boundingBox();
    const centre = b => b.x + b.width / 2;
    for (const text of ["Volume", "Input Level"]) {
      const label = page.locator(".cee-e2-control", { has: page.locator(".cee-e2-label", { hasText: text }) });
      const [l, d] = [await label.locator(".cee-e2-label").boundingBox(), await label.locator(".cee-e2-dial").boundingBox()];
      assert.ok(Math.abs(centre(l) - centre(d)) < 1.5, `${text} sits over its knob`);
    }
    const frames = await page.locator(".cee-e2-section").evaluateAll(nodes => nodes.map(n => {
      const name = n.querySelector(".cee-e2-section-name");
      return { frame: n.getBoundingClientRect().toJSON(), name: name?.textContent ?? null, title: name?.getBoundingClientRect().toJSON(), size: name && parseFloat(getComputedStyle(name).fontSize) };
    }));
    assert.deepEqual(frames.map(f => f.name), ["Sample", "Filter", "Modulation", null, "Insert Fx"], "the AMP/EG group has no title");
    for (const f of frames.filter(f => f.name)) {
      assert.ok(f.title.bottom <= f.frame.top + 0.5, `${f.name} stands above its frame`);
      assert.ok(f.size >= 12, `${f.name} is readable (${f.size}px)`);
    }
    const [send, amp, level, pan] = await Promise.all(["#cee-e2-mfxSend", "#cee-e2-ampEg", "#cee-e2-level", "#cee-e2-pan"].map(box));
    assert.ok(Math.abs(send.y - amp.y) < 0.5 && Math.abs(send.height - amp.height) < 0.5, "MFX SEND and AMP EG share one row");
    assert.ok(Math.abs(centre(send) - centre(level)) < 2, "MFX SEND is centred under the LEVEL column");
    assert.ok(Math.abs(centre(amp) - centre(pan)) < 2, "AMP EG is centred under the PAN column");
  });

  const DISPLAY_RAM = 0xc031b310;
  const MOV_R0_1_BX_LR = "[0xE3A00001, 0xE12FFF1E]";

  /** The real device (the Web MIDI stand-in, which also takes execute) and the emulator, both connected. */
  async function deviceThroughEmulator() {
    for (const context of h.browser.contexts()) await context.close();
    fake.seen.exec.length = 0;
    fake.hooks.hangOnExec = false;
    fake.hooks.restartOnExec = false;
    const vsb = h.file("system.vsb", await makeFirmware());
    const page = await h.page({ device: true });
    await page.goto(`${h.url}?exec=1#emu=${fake.port}:${TOKEN}`);
    await page.evaluate(() => window.__ceeStubReady);
    await powerOn(page, vsb);
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    await go(page, "device");
    await page.click("#cee-connect");
    await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
    await page.click("#cee-tab-scripts");
    await page.click("#cee-tab-console");
    return page;
  }

  const deviceDisplay = page => page.evaluate(a => Array.from(window.__ceeSim.device.peek(a, 1024)), DISPLAY_RAM);

  test("terminal: with the real device a script is rehearsed in the emulator, shown step by step, and only a passed one can be sent", async () => {
    const page = await deviceThroughEmulator();
    assert.match(await page.locator("#cee-term-target").textContent(), /Gerät über Emulator/);
    assert.equal(await page.locator("#cee-term-run").textContent(), "Im Emulator proben");
    assert.equal(await page.locator("#cee-term-send").isDisabled(), true, "nothing to send before a rehearsal");

    const code = "KORG.screen.set((x, y) => y === 0)";
    fake.seen.midi.length = 0;
    await page.fill("#cee-term-input", code);
    await page.press("#cee-term-input", "Enter");
    await page.locator("#cee-term-rehearsal", { hasText: "Probe bestanden" }).waitFor({ timeout: 15_000 });
    const frames = fake.seen.midi.filter(m => m.slice(12, 14) === "54");
    assert.ok(frames.length > 0, "the emulator got the picture first");
    assert.equal((await deviceDisplay(page)).every(b => b === 0), true, "the device has seen nothing yet");
    await page.locator("#cee-term-rehearsal details summary").first().click();
    assert.ok(await page.locator("#cee-term-rehearsal li").count() > 2, "every message of the unit is listed");
    assert.equal(await page.locator("#cee-term-send").isDisabled(), false);

    // any change throws the rehearsal away, even when the text is put back
    await page.fill("#cee-term-input", `${code} `);
    await page.fill("#cee-term-input", code);
    assert.equal(await page.locator("#cee-term-send").isDisabled(), true);
    await page.locator(".cee-term-stale").waitFor({ state: "visible" });
    assert.equal((await deviceDisplay(page)).every(b => b === 0), true);

    await page.press("#cee-term-input", "Enter");
    await page.locator("#cee-term-rehearsal .cee-term-rehearsal-head", { hasText: "Probe bestanden" }).waitFor();
    await page.locator("#cee-term-send:not([disabled])").waitFor();
    await page.click("#cee-term-send");
    await page.locator("#app-toasts .cee-toast", { hasText: "Ans Gerät gesendet" }).waitFor({ timeout: 15_000 });
    const device = await deviceDisplay(page);
    const emulator = Array.from({ length: 1024 }, (_, i) => fake.ram.get(DISPLAY_RAM + i) ?? 0);
    assert.deepEqual(device.slice(0, 128), Array(128).fill(1));
    assert.deepEqual(device, emulator, "the device holds what the emulator held");
    assert.equal(await page.locator("#cee-term-send").isDisabled(), true, "a rehearsal is sent once");
    // The sidebar polls the attached device's screen state (0xc03404c0), which the stand-in's small image does not hold; any other fault is the script's.
    assert.deepEqual(await page.evaluate(() => window.__ceeSim.faults.map(f => f.message).filter(m => !m.startsWith("read at 0xc03404c0"))), []);
    assert.deepEqual(page.errors, []);
  });

  test("terminal: code runs in the emulator first, then on the device, and a firmware that hangs sends nothing", async () => {
    const page = await deviceThroughEmulator();
    const code = `KORG.exec(${MOV_R0_1_BX_LR})`;
    await page.fill("#cee-term-input", code);
    await page.press("#cee-term-input", "Enter");
    await page.locator("#cee-term-rehearsal .cee-term-rehearsal-head", { hasText: "Probe bestanden" }).waitFor({ timeout: 20_000 });
    assert.deepEqual(fake.seen.exec, [0xc00016a4, 0xc1000000], "the emulator ran the cache routine, then the stub");
    assert.equal(await page.evaluate(() => window.__ceeExec ?? null), null, "the device ran nothing yet");
    await page.click("#cee-term-send");
    await page.locator("#app-toasts .cee-toast", { hasText: "Ans Gerät gesendet" }).waitFor({ timeout: 15_000 });
    assert.deepEqual(await page.evaluate(() => window.__ceeExec), [0xc00016a4, 0xc1000000]);

    fake.hooks.hangOnExec = true;
    await page.fill("#cee-term-input", `${code} `);
    await page.press("#cee-term-input", "Enter");
    await page.locator("#cee-term-rehearsal .cee-term-rehearsal-head", { hasText: "Probe nicht bestanden" }).waitFor({ timeout: 20_000 });
    assert.match(await page.locator("#cee-term-rehearsal").textContent(), /stehen geblieben/);
    assert.equal(await page.locator("#cee-term-send").isDisabled(), true);
    assert.deepEqual(await page.evaluate(() => window.__ceeExec), [0xc00016a4, 0xc1000000], "the device was not spoken to again");

    // a firmware that starts over is no pass either; the emulator is running again after the hang
    fake.hooks.hangOnExec = false;
    fake.hooks.restartOnExec = true;
    fake.broadcast("status", { state: "running", device_ms: 5000 });
    await page.locator("#cee-emu-status", { hasText: "Die Firmware läuft" }).waitFor({ state: "attached" });
    await page.fill("#cee-term-input", `${code}  `);
    await page.press("#cee-term-input", "Enter");
    await page.locator("#cee-term-rehearsal .cee-term-rehearsal-head", { hasText: "Probe nicht bestanden" }).waitFor({ timeout: 20_000 });
    assert.match(await page.locator("#cee-term-rehearsal").textContent(), /neu gestartet/);
    assert.deepEqual(await page.evaluate(() => window.__ceeExec), [0xc00016a4, 0xc1000000], "still nothing more on the device");
    assert.deepEqual(page.errors, []);
  });
}
