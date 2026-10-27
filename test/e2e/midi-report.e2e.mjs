import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

/** Web MIDI with a Korg port that is no Electribe; `__plug` adds the Electribe and tells `statechange`. */
async function webPage() {
  const page = await h.page();
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.addInitScript(() => {
    const access = new EventTarget();
    const port = name => ({ name, manufacturer: "KORG INC.", state: "connected", connection: "closed" });
    access.inputs = new Map([["k", port("KORG USB-MIDI Device")]]);
    access.outputs = new Map([["k", port("KORG USB-MIDI Device")]]);
    window.__plug = () => {
      access.inputs.set("e", port("MIDIIN2 (electribe2 sampler)"));
      access.outputs.set("e", port("MIDIOUT2 (electribe2 sampler)"));
      access.dispatchEvent(new Event("statechange"));
    };
    navigator.requestMIDIAccess = async () => access;
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = async d => (d.name === "midi" ? { state: "granted" } : query(d));
  });
  await page.goto(h.url);
  await page.click("#cee-settings-button");
  await page.locator("#cee-area-settings:not([hidden]) #cee-midi").waitFor();
  return page;
}

const report = page => page.locator("#cee-midi-report");

test("the settings show what MIDI sees, follow a plug-in, and copy the report as text", async () => {
  const page = await webPage();
  await page.waitForFunction(() => /KORG USB-MIDI Device/.test(document.querySelector("#cee-midi-report")?.textContent));
  const before = await report(page).textContent();
  assert.match(before, /^Übertragung: Web MIDI \(Browser\)$/m);
  assert.match(before, /^MIDI-Zugriff: erlaubt$/m);
  assert.match(before, /^Als Electribe erkannt \(0\):\n {2}keine$/m);

  await page.evaluate(() => window.__plug());
  await page.waitForFunction(() => /Als Electribe erkannt \(1\)/.test(document.querySelector("#cee-midi-report")?.textContent));
  assert.match(await report(page).textContent(), /Ausgang „MIDIOUT2 \(electribe2 sampler\)“ mit Eingang „MIDIIN2 \(electribe2 sampler\)“/);

  await page.click("#cee-midi-rescan");
  await page.click("#cee-midi-copy");
  await page.locator(".cee-toast", { hasText: "MIDI-Bericht kopiert" }).waitFor();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), await report(page).textContent());
  assert.deepEqual(page.errors, []);
});
