import { before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go, pickPreset } from "../harness.mjs";
import { makeFirmware, makeRecord } from "../../helpers.mjs";
import { tableEntry } from "../../../src/map/address.mjs";
import { fakeService, TOKEN } from "./fake-emu.mjs";
import { only } from "./parts.mjs";

/** The tests of the live page, every `parts`-th one from `index`: the parts run as files of their own, side by side. */
export function liveSuite(index, parts) {
  const test = only(index, parts);
  let h;
  let fake;
  let firmware;
  before(async () => {
    h = await setUp();
    fake = await fakeService(new URL(h.url).origin);
    const gate = makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64, 64] } });
    gate.setDevice("mfx", 0x27);
    gate.map = [{ source: 0x42, chain: 0x00, param: 0, low: 0, high: 127 }];
    const bad = makeRecord("ifx", { name: "Delay Stage", devices: { ifx1: 0x0a, ifx2: 0x18 } });
    bad.setDevice("mfx", 0x27);
    firmware = await makeFirmware([{ kind: "ifx", slot: 50, record: gate }, { kind: "ifx", slot: 51, record: bad }]);
    h.file("system.vsb", firmware);
  });
  after(async () => {
    fake.server.closeAllConnections?.();
    fake.server.close();
    await h.tearDown();
  });

  const SLOT50 = tableEntry("table.ifx", 49).ram;

  /**
   * A page with the real device (the Web MIDI stand-in) attached. A change to a real device goes through the
   * emulator first, so the page also gets a running emulator (the stand-in service) with the same firmware.
   */
  async function open(query = "", { route } = {}) {
    for (const context of h.browser.contexts()) await context.close();   // pages of earlier tests also talk to the service
    for (const table of ["table.ifx"]) for (const index of [49, 50]) {
      const slot = tableEntry(table, index);
      fake.poke(slot.ram, Array.from(firmware.subarray(slot.file, slot.file + slot.size)));
    }
    const page = await h.page({ device: true });
    if (route) await page.route("**/data/devices.mjs", r => r.fulfill({ contentType: "text/javascript", body: route }));
    await page.goto(`${h.url}${query}#emu=${fake.port}:${TOKEN}`);
    await page.evaluate(() => window.__ceeStubReady);
    await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
    await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
    await page.click("#cee-e2-power");
    await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
    const running = Date.now();
    await go(page, "device");
    await page.click("#cee-connect");
    await page.locator(".cee-device-status .cee-status").filter({ hasNotText: "getrennt" }).waitFor();
    await page.locator("#cee-rehearse-state", { hasText: "Probe im Emulator: an" }).waitFor({ timeout: 15_000 });
    // The Presets page has no file picker: it takes the firmware chosen in the sidebar of the emulator page.
    await page.evaluate(() => { location.hash = "fx"; });
    await page.locator("#cee-fx-slot").waitFor({ timeout: 15_000 });
    // The initial emulator status poll schedules a preset refresh 3 s later.
    await new Promise(r => setTimeout(r, Math.max(0, 4500 - (Date.now() - running))));
    return page;
  }

  /**
   * Start counting the stand-in's messages for the failure injection. The page polls the device (screen state, display) unless it is
   * hidden, so it is made hidden first and given a moment to finish what is in flight; then only the send is counted.
   */
  async function arm(page) {
    await page.evaluate(() => Object.defineProperty(document, "hidden", { configurable: true, get: () => true }));
    await new Promise(r => setTimeout(r, 500));
    await page.evaluate(() => window.__ceeArm());
  }

  const peek = (page, addr, n = 1) => page.evaluate(([a, k]) => Array.from(window.__ceeSim.device.peek(a, k)), [addr, n]);

  const pick = pickPreset;

  async function nudgeFirstParam(page) {
    const slider = page.locator("#cee-fx-editor input.ui-range").first();
    await slider.focus();
    await slider.press("ArrowRight");
  }

  test("connect: the page asks for SysEx, finds the device, knows its state", async () => {
    const page = await open();
    await go(page, "device");
    const facts = await page.locator(".cee-facts").textContent();
    assert.match(facts, /Globaler Kanal\s*10/);
    const pills = await page.locator(".cee-facts .cee-status").allTextContents();
    assert.deepEqual(pills, ["bekannt", "Hacktribe"]);
    // The sidebar polls the device's screen state (0xc03404c0), which the stand-in's small image does not hold; any other fault is a real one.
    assert.deepEqual(await page.evaluate(() => window.__ceeSim.faults.map(f => f.message).filter(m => !m.startsWith("read at 0xc03404c0"))), []);
  });

  test("a preset sent live lands in RAM, and one click takes it back", async () => {
    const page = await open();
    await pick(page, 50);
    const before = await peek(page, SLOT50 + 0x135);
    await nudgeFirstParam(page);
    await page.click("#cee-send");
    await page.locator(".ui-job .cee-status").filter({ hasText: /Fertig|Fehlgeschlagen/ }).waitFor();
    assert.equal(await page.locator(".ui-job .cee-status").textContent(), "Fertig");
    assert.equal((await peek(page, SLOT50 + 0x135))[0], before[0] + 1);
    await page.click("#cee-live-undo");
    await page.locator(".ui-job-meta").filter({ hasText: "Alter Stand" }).waitFor();
    assert.deepEqual(await peek(page, SLOT50 + 0x135), before);
  });

  test("a fatal combination is blocked with its reason in words", async () => {
    const page = await open("?latency=80");
    await pick(page, 51);
    assert.equal(await page.locator("#cee-fx-editor input[type=text]").first().inputValue(), "Delay Stage");
    const before = await peek(page, tableEntry("table.ifx", 50).ram, 0x20c);
    await page.click("#cee-send");
    await page.locator("#cee-blocked").waitFor();
    const text = await page.locator("#cee-blocked").textContent();
    assert.match(text, /tödlich/);
    assert.match(text, /0x18 in stage 2/);
    assert.deepEqual(await peek(page, tableEntry("table.ifx", 50).ram, 0x20c), before, "a blocked preset never reaches RAM");
  });

  test("an unknown device is only read", async () => {
    const page = await open("", { route: "export default [];" });
    await go(page, "device");
    assert.match(await page.locator(".cee-device-status").textContent(), /nur lesen/);
    await page.evaluate(() => { location.hash = "fx"; });
    await pick(page, 50);
    await nudgeFirstParam(page);
    await page.click("#cee-send");
    await page.locator("#cee-blocked").waitFor();
    assert.match(await page.locator("#cee-blocked").textContent(), /Unbekannter Gerätestand/);
  });

  test("an unknown firmware file is refused before anything is shown", async () => {
    const page = await h.page({ device: true });
    await page.goto(h.url);
    await page.setInputFiles("#cee-emu-vsb", h.file("other.vsb", new Uint8Array(0x200100)));
    await page.evaluate(() => { location.hash = "fx"; });
    await page.locator("#cee-vsb-identity .cee-status").waitFor({ timeout: 15_000 });
    assert.equal(await page.locator("#cee-vsb-identity .cee-status").textContent(), "unbekannt");
    assert.equal(await page.locator("#cee-fx-slot").count(), 0);
  });

  async function decideRestore(page) {
    await go(page, "device");
    await page.locator("#cee-decide").waitFor({ state: "visible" });
    await page.click("#cee-decide-restore");
    await page.locator("#cee-decide").waitFor({ state: "hidden" });
  }

  test("no answer in time: reported with what arrived, and the backup put back on request", async () => {
    // Replies from the arming on: backup, first ack, first data ack; the second write's ack never comes.
    const page = await open("?swallow=4");
    await pick(page, 50);
    const before = await peek(page, SLOT50, 0x20c);
    await nudgeFirstParam(page);
    await arm(page);
    await page.click("#cee-send");
    await page.locator(".ui-job .cee-status").filter({ hasText: "Fehlgeschlagen" }).waitFor({ timeout: 15000 });
    const meta = await page.locator(".ui-job-meta").textContent();
    assert.match(meta, /Keine Antwort/);
    assert.match(meta, /Stand/, "what the read-back found is said");
    await decideRestore(page);
    assert.deepEqual(await peek(page, SLOT50, 0x20c), before);
  });

  test("a read-back that does not match: shown, the device blocked, the backup offered", async () => {
    // Replies from the arming on: backup, six acknowledgements, read-back.
    const page = await open("?corrupt=8");
    await pick(page, 50);
    const before = await peek(page, SLOT50, 0x20c);
    await nudgeFirstParam(page);
    await arm(page);
    await page.click("#cee-send");
    await page.locator(".ui-job .cee-status").filter({ hasText: "Fehlgeschlagen" }).waitFor();
    assert.match(await page.locator(".ui-job-meta").textContent(), /Zurückgelesen passt nicht/);
    await page.click("#cee-send");
    await page.locator("#cee-blocked").waitFor();
    assert.match(await page.locator("#cee-blocked").textContent(), /nichts mehr/);
    await decideRestore(page);
    assert.deepEqual(await peek(page, SLOT50, 0x20c), before);
  });

  test("unplugged during a send: reported at once, and the device takes nothing more", async () => {
    // Sent from the arming on: backup, then the plug is pulled.
    const page = await open("?unplugAfter=1");
    await pick(page, 50);
    await nudgeFirstParam(page);
    await arm(page);
    await page.click("#cee-send");
    await page.locator(".ui-job .cee-status").filter({ hasText: "Fehlgeschlagen" }).waitFor();
    assert.match(await page.locator(".ui-job-meta").textContent(), /abgezogen/);
    await page.locator("#cee-blocked").waitFor();
    assert.match(await page.locator("#cee-blocked").textContent(), /geht an dieses Gerät nichts mehr/);
  });

  test("expert changes and warnings only go out after a yes", async () => {
    const page = await open("?latency=80");
    await pick(page, 50);
    const before = await peek(page, SLOT50, 0x20c);
    await page.locator("label.ui-switch", { hasText: "Experte" }).click();   // the unknown bytes wait behind the expert switch
    await page.locator("#cee-expert summary").click();
    const byte = page.locator("#cee-expert input.cee-byte").first();
    await byte.fill("7");
    await byte.press("Tab");
    await page.click("#cee-send");
    const dialog = page.locator("dialog.ui-dialog[open]");
    await dialog.waitFor();
    assert.match(await dialog.textContent(), /deren Wirkung niemand kennt/);
    await dialog.getByRole("button", { name: "Abbrechen" }).click();
    assert.deepEqual(await peek(page, SLOT50, 0x20c), before, "nothing went out on no");
    assert.equal(await byte.inputValue(), "7", "cancellation keeps the unsent edit");
    await page.click("#cee-send");
    await page.locator("dialog.ui-dialog[open]").getByRole("button", { name: "Senden" }).click();
    await page.locator(".ui-job .cee-status").filter({ hasText: "Fertig" }).waitFor();
    assert.notDeepEqual(await peek(page, SLOT50, 0x20c), before);
  });

  test("the preset component keeps an expert edit through refresh and cancellation", async () => {
    const page = await h.page({ device: true });
    await page.goto(h.url);
    await page.evaluate(async () => {
      await window.__ceeStubReady;
      const { DeviceSession, electribePorts } = await import("/src/session.mjs");
      const { fxPanel } = await import("/app/fx.mjs");
      const access = await navigator.requestMIDIAccess({ sysex: true });
      const session = new DeviceSession({ port: electribePorts(access)[0] });
      await session.connect();
      const root = document.createElement("section");
      document.body.append(root);
      const panel = fxPanel(root, { device: { session }, prefix: "cee-refresh", embedded: true });
      const bytes = new Uint8Array(await (await fetch("/test-support/files/system.vsb")).arrayBuffer());
      await panel.loadBytes(bytes);
      window.__ceeRefreshPanel = panel;
      window.__ceeRefreshSession = session;
    });
    await page.locator("#cee-refresh-fx-slot").waitFor();
    await pickPreset(page, 50, "cee-refresh");
    await page.locator("label.ui-switch", { has: page.locator("#cee-refresh-expert-toggle") }).click();
    await page.click("#cee-refresh-expert > summary");
    const byte = page.locator("#cee-refresh-expert input.cee-byte").first();
    const duringRead = await page.evaluate(async () => {
      const reading = window.__ceeRefreshPanel.refresh();
      await Promise.resolve();
      const busy = window.__ceeRefreshSession.busy;
      const input = document.querySelector("#cee-refresh-expert input.cee-byte");
      input.value = "7";
      input.dispatchEvent(new Event("change", { bubbles: true }));
      await reading;
      return { busy, value: document.querySelector("#cee-refresh-expert input.cee-byte").value };
    });
    assert.deepEqual(duringRead, { busy: true, value: "7" }, "an in-flight refresh must preserve a new edit");
    const before = await peek(page, SLOT50, 0x20c);
    await page.click("#cee-refresh-send");
    const dialog = page.locator("dialog.ui-dialog[open]");
    await dialog.waitFor();
    await page.evaluate(() => window.__ceeRefreshPanel.refresh());
    assert.equal(await byte.inputValue(), "7", "refresh must preserve the edit behind the confirmation");
    await dialog.getByRole("button", { name: "Abbrechen" }).click();
    assert.deepEqual(await peek(page, SLOT50, 0x20c), before);
    await page.evaluate(() => window.__ceeRefreshPanel.refresh());
    assert.equal(await byte.inputValue(), "7", "cancel must preserve the unsent edit");
    await page.click("#cee-refresh-send");
    await dialog.getByRole("button", { name: "Senden" }).click();
    await page.locator("#cee-refresh-send:not([disabled])").waitFor();
    assert.notDeepEqual(await peek(page, SLOT50, 0x20c), before);
    assert.deepEqual(page.errors, []);
  });
}
