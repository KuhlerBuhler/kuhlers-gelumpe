import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp, go } from "./harness.mjs";
import { startService } from "../support/emu.mjs";
import { applyPatches } from "../../src/patch.mjs";

// The effect editor on Korg's original firmware with BLECH, against the emulator service itself (not the stand-in of
// support/fake-emu.mjs): the records are found through the firmware's pointer arrays, read and written with BLECH's SysEx
// commands. Needs the user's own Korg 2.02 (E2_STOCK_VSB) and the emulator (tools/emu/.venv); docs/messungen/2026-10-15-effekt-editor-original.md.
const local = process.env.E2_LOCAL_REQUIRED === "1" || process.env.E2_EMU_REQUIRED === "1";
const stock = process.env.E2_STOCK_VSB;
const skip = !stock ? "E2_STOCK_VSB not set" : !local ? "emulation only runs in test:local or test:emu" : false;
const SET = JSON.parse(readFileSync(new URL("../../data/patches/blech.json", import.meta.url), "utf8"));
const patches = SET.patches.map(p => JSON.parse(readFileSync(new URL(`../../${p}`, import.meta.url), "utf8")));

let h;
let service;
before(async () => {
  if (skip) return;
  h = await setUp(() => [], { realDevices: true });
  service = await startService({ allowOrigin: [new URL(h.url).origin] });
});
after(async () => {
  await service?.stop();
  await h?.tearDown();
});

test("effect editor on Korg's original with BLECH: a name is written into the running emulator and read back from it", { skip, timeout: 240_000 }, async () => {
  const patched = await applyPatches(new Uint8Array(readFileSync(stock)), patches);
  assert.equal(patched.ok, true, patched.reasons.join(" "));
  const page = await h.page();
  await page.goto(`${h.url}#emu=${service.port}:${service.token}`);
  await page.click("#cee-tab-emu");
  if (!(await page.locator("#cee-emu-setup").evaluate(n => n.open))) await page.click("#cee-emu-setup > summary");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", patched.bytes));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "Korgs Original-Firmware 2.02, erkannt" }).waitFor();
  await page.click("#cee-e2-power");
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor({ timeout: 60_000 });
  await go(page, "fx");
  await page.locator("#cee-fx-slot").waitFor({ timeout: 30_000 });
  assert.match(await page.locator("#cee-vsb-identity").textContent(), /live ins RAM geht mit BLECH/);

  // The firmware has to be up before BLECH answers; a read that did not come from the emulator is tried again.
  const source = page.locator("#cee-fx-source");
  const name = page.locator("#cee-fx-editor input[type=text]").first();
  const options = await page.locator("#cee-fx-slot option").evaluateAll(list => list.map(o => o.value));
  assert.ok(options.length >= 2, "the file has presets to pick");
  const [first, second] = options;
  const open = async slot => {
    await page.selectOption("#cee-fx-slot", slot);
    await source.waitFor();
  };
  const deadline = Date.now() + 120_000;
  for (;;) {
    await open(second);
    await open(first);
    if (/Gelesen aus dem laufenden Emulator/.test(await source.textContent())) break;
    assert.ok(Date.now() < deadline, `the emulator did not answer: ${await source.textContent()}`);
    await page.waitForTimeout(3000);
  }
  const was = await name.inputValue();
  const edited = was.startsWith("QQ") ? "ZZ" + was.slice(2) : "QQ" + was.slice(2);
  await name.fill(edited);
  await name.press("Tab");

  await page.click("#cee-send");
  const ok = page.locator("dialog button[value=ok]");
  const job = page.locator("#cee-area-fx .ui-job .cee-status").filter({ hasText: /Fertig|Fehlgeschlagen/ });
  await Promise.race([ok.waitFor().then(() => ok.click(), () => {}), job.waitFor()]);
  await job.waitFor({ timeout: 60_000 });
  assert.equal(await job.textContent(), "Fertig", await page.locator("#cee-area-fx .ui-job").textContent());
  assert.match(await page.locator("#cee-area-fx .ui-job").textContent(), /Gesendet und zurückgelesen/);

  // Another preset, then this one again: it is read from the emulator's RAM, and holds the new name.
  const holds = async text => {
    await open(second);
    await open(first);
    await page.waitForFunction(v => document.querySelector("#cee-fx-editor input[type=text]")?.value === v, text, { timeout: 90_000 });
    assert.match(await source.textContent(), /Gelesen aus dem laufenden Emulator/);
  };
  await holds(edited);

  // and the edit is taken back, again through the pointer array's record
  await page.click("#cee-live-undo");
  await page.locator("#cee-area-fx .ui-job .cee-status", { hasText: "Fertig" }).waitFor({ timeout: 60_000 });
  await holds(was);
  assert.deepEqual(page.errors, []);
});
