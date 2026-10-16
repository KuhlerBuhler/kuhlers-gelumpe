import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { makeFirmware, makeRecord } from "../helpers.mjs";

let h;
before(async () => {
  h = await setUp();
  const gate = makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64, 64] } });
  gate.setDevice("mfx", 0x27);
  gate.map = [{ source: 0x42, chain: 0x00, param: 0, low: 0, high: 127 }];
  h.file("system.vsb", await makeFirmware([{ kind: "ifx", slot: 50, record: gate }]));
});
after(async () => { await h.tearDown(); });

// The catalogue rows of phase 3a that a page can only reach through a test
// entry. The sender rows (no answer, read-back, unplugged, half-written
// multi-site) and "MIDI without SysEx" are in live.e2e.mjs through the page.
const EXPECTED = {
  "stage2-fatal": "Prüfer", "stage2-silent": "Prüfer", "stage1-needs-solo": "Prüfer",
  "master-unit-in-insert": "Prüfer", "wrong-table": "Prüfer", "no-switch-on-fade": "Prüfer",
  "not-ram": "Türsteher", "out-of-range": "Türsteher", "outside-allowed-region": "Türsteher",
  channel: "Probelauf", "write-without-header": "Probelauf", "short-write": "Probelauf", hang: "Türsteher", execute: "Probelauf",
};

test("every row of the 3a catalogue reaches the device without its check, and is stopped at its stage with it", async () => {
  const page = await h.page({ device: true });
  await page.goto(h.url);
  await page.evaluate(() => window.__ceeStubReady);
  const rows = await page.evaluate(async () => (await import("/test-support/catalogue.mjs")).runCatalogue());
  assert.deepEqual(Object.fromEntries(rows.map(r => [r.row, r.stage])), EXPECTED);
  for (const r of rows) {
    assert.equal(r.without, true, `${r.row}: without the ${r.stage} the fault should reach the device`);
    assert.equal(r.caught, true, `${r.row}: not stopped by the ${r.stage}`);
  }
});
