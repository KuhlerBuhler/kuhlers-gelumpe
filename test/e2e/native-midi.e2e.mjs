import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { makeFirmware } from "../helpers.mjs";

let h;
before(async () => { h = await setUp(); h.file("system.vsb", await makeFirmware()); });
after(async () => { await h.tearDown(); });

async function nativePage({ listError = false, portCount = 1, sendError = false, quarantined = false, absentWebMidi = false } = {}) {
  const page = await h.page();
  await page.addInitScript(({ listError, portCount, sendError, quarantined, absentWebMidi }) => {
    window.__GELUMPE_APP = { nativeMidi: true };
    window.__nativeCalls = [];
    window.__nativeArgs = [];
    window.__browserRequests = 0;
    navigator.requestMIDIAccess = () => { window.__browserRequests++; throw new Error("Browser MIDI must not run"); };
    if (absentWebMidi) navigator.requestMIDIAccess = undefined;
    let events, sessionId, count = 0, sequence = 0;
    const payloads = new Map();
    window.__TAURI__ = { core: {
      Channel: class {},
      invoke: async (command, args) => {
        window.__nativeCalls.push(command);
        window.__nativeArgs.push({ command, inputId: args?.inputId, outputId: args?.outputId, sessionId: args?.sessionId, sequence: args?.sequence });
        if (command === "midi_list") {
          if (listError) throw "ALSA nicht verfügbar";
          return { inputs: Array.from({ length: portCount }, (_, i) => ({ id: `native-in-${i}`, name: `electribe synthetic ${i}` })), outputs: Array.from({ length: portCount }, (_, i) => ({ id: `native-out-${i}`, name: `electribe synthetic ${i}` })) };
        }
        if (command === "midi_open") { events = args.events; sessionId = `native-${++count}`; return { sessionId }; }
        if (command === "midi_send") {
          if (sendError) throw { code: "send_failed", message: "Synthetischer Sendefehler" };
          await (window.__nativeReady ??= (async () => {
            const { installWebMidiStub } = await import("/src/webmidi.mjs");
            const { VsbImage } = await import("/src/image.mjs");
            const image = new VsbImage(new Uint8Array(await (await fetch("/test-support/files/system.vsb")).arrayBuffer()));
            return installWebMidiStub({ image, channel: 9, target: {} });
          })());
          const sim = await window.__nativeReady;
          const reply = sim.device.handle(Uint8Array.from(args.bytes));
          if (reply) {
            payloads.set(`${sessionId}:${++sequence}`, [...reply]);
            events.onmessage({ sessionId, type: "message", sequence });
          }
        }
        if (command === "midi_read") return payloads.get(`${args.sessionId}:${args.sequence}`);
        if (command === "midi_ack") { payloads.delete(`${args.sessionId}:${args.sequence}`); return; }
        if (command === "midi_close") return { state: quarantined && !window.__nativeReleased ? "quarantined" : "closed" };
      },
    } };
    window.__nativeDisconnect = () => events.onmessage({ sessionId, type: "disconnected" });
  }, { listError, portCount, sendError, quarantined, absentWebMidi });
  await page.goto(`${h.url}#device`);
  return page;
}

test("desktop native MIDI connects through the existing UI, disconnects and reconnects without Web MIDI", async () => {
  const page = await nativePage({ absentWebMidi: true });
  await page.click("#cee-connect");
  await page.waitForFunction(() => document.querySelector(".cee-facts")?.textContent.includes("Globaler Kanal"));
  assert.equal(await page.evaluate(() => window.__browserRequests), 0);
  assert.equal(await page.evaluate(() => window.__nativeCalls.filter(c => c === "midi_open").length), 1);
  await page.evaluate(() => window.__nativeDisconnect());
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("abgesteckt"));
  await page.click("#cee-connect");
  await page.waitForFunction(() => window.__nativeCalls.filter(c => c === "midi_open").length === 2);
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));
  assert.ok(await page.evaluate(() => window.__nativeCalls.includes("midi_close")));
  assert.deepEqual(page.errors, []);
});

test("native enumeration failure uses the existing error toast without browser fallback", async () => {
  const page = await nativePage({ listError: true });
  await page.click("#cee-connect");
  await page.waitForFunction(() => document.body.textContent.includes("ALSA nicht verfügbar"));
  assert.equal(await page.evaluate(() => window.__browserRequests), 0);
  assert.equal(await page.evaluate(() => window.__nativeCalls.includes("midi_open")), false);
});

test("Chrome without Tauri still connects with Web MIDI", async () => {
  const page = await h.page({ device: true });
  await page.goto(`${h.url}#device`);
  await page.evaluate(() => window.__ceeStubReady);
  await page.click("#cee-connect");
  await page.waitForFunction(() => document.querySelector(".cee-facts")?.textContent.includes("Globaler Kanal"));
  assert.equal(await page.evaluate(() => window.__TAURI__ === undefined), true);
  assert.deepEqual(page.errors, []);
});


test("multiple native devices wait for explicit choice and switching closes the previous session", async () => {
  const page = await nativePage({ portCount: 2 });
  await page.click("#cee-connect");
  await page.locator("#cee-port").waitFor({ state: "visible" });
  assert.equal(await page.evaluate(() => window.__nativeCalls.includes("midi_open")), false);
  await page.selectOption("#cee-port", "0");
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));
  await page.selectOption("#cee-port", "1");
  await page.waitForFunction(() => window.__nativeCalls.filter(c => c === "midi_open").length === 2);
  const calls = await page.evaluate(() => window.__nativeCalls);
  assert.ok(calls.lastIndexOf("midi_close") < calls.lastIndexOf("midi_open"));
  assert.deepEqual(await page.evaluate(() => window.__nativeArgs.filter(c => c.command === "midi_open").map(c => [c.inputId, c.outputId])), [["native-in-0", "native-out-0"], ["native-in-1", "native-out-1"]]);
  assert.deepEqual(page.errors, []);
});

test("failed native handshake closes the port and reports quarantine as a toast", async () => {
  const page = await nativePage({ sendError: true, quarantined: true });
  await page.click("#cee-connect");
  await page.waitForFunction(() => document.body.textContent.includes("freigegeben"));
  assert.equal(await page.evaluate(() => window.__nativeCalls.filter(c => c === "midi_close").length), 1);
  assert.equal(await page.evaluate(() => window.__browserRequests), 0);
  assert.deepEqual(page.errors, []);
});

test("page teardown explicitly closes the native MIDI resource", async () => {
  const page = await nativePage();
  await page.click("#cee-connect");
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pagehide")));
  await page.waitForFunction(() => window.__nativeCalls.includes("midi_close"));
  assert.deepEqual(page.errors, []);
});


test("one reconnect click succeeds after a quarantined native port has been released", async () => {
  const page = await nativePage({ quarantined: true });
  await page.click("#cee-connect");
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));
  await page.evaluate(() => window.__nativeDisconnect());
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("freigegeben"));
  assert.doesNotMatch(await page.locator(".cee-device-status").textContent(), /object Object|undefined/);
  await page.evaluate(() => { window.__nativeReleased = true; });
  await page.click("#cee-connect");
  await page.waitForFunction(() => window.__nativeCalls.filter(c => c === "midi_open").length === 2);
  await page.waitForFunction(() => document.querySelector(".cee-device-status")?.textContent.includes("verbunden"));
  assert.ok(await page.evaluate(() => window.__nativeCalls.includes("midi_ack")));
  assert.deepEqual(page.errors, []);
});
