import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { severeViolations } from "./support/axe.mjs";
import { makeFirmware, makeRecord } from "../helpers.mjs";

// Findings and what is not covered here: docs/barrierefreiheit.md
let h;
let fake;
let firmware;
before(async () => {
  h = await setUp();
  fake = await fakeService(new URL(h.url).origin, { sdDir: h.dir });
  const gate = makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64, 64] } });
  gate.setDevice("mfx", 0x27);
  firmware = await makeFirmware([{ kind: "ifx", slot: 50, record: gate }]);
  h.file("system.vsb", firmware);
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

async function open(viewport, labs = false) {
  // The shared MIDI service broadcasts replies to every open context.
  for (const context of h.browser.contexts()) await context.close();
  const page = await h.page();
  if (viewport) await page.setViewportSize(viewport);
  await page.goto(`${h.url}${labs ? "?labs" : ""}#emu=${fake.port}:${TOKEN}`);
  await page.locator("#cee-e2-power").waitFor();
  return page;
}

async function powerOn(page) {
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.click("#cee-e2-power");
  await page.locator("#cee-emu-status", { hasText: "läuft" }).waitFor();
  await page.waitForFunction(() => document.querySelector("#cee-e2-sequencer").style.getPropertyValue("--cee-e2-glow") === "1");
}

test("axe: start page, emulator (off, with options open, running), no serious or critical violation", async () => {
  const page = await open();
  await page.click("#cee-tab-start");
  assert.deepEqual(await severeViolations(page), [], "start");
  await page.click("#cee-tab-emu");
  assert.deepEqual(await severeViolations(page), [], "emulator off");
  await powerOn(page);
  assert.deepEqual(await severeViolations(page), [], "emulator running, a lit key and a blue pad");
  assert.deepEqual(page.errors, []);
});

test("axe: device mode, patcher, presets, plugins with a running plugin, and the hidden samples page with ?labs", async () => {
  const page = await open(undefined, true);
  await powerOn(page);
  await go(page, "device");
  assert.deepEqual(await severeViolations(page), [], "device mode, not connected");
  await page.click("#cee-tab-patcher");
  assert.deepEqual(await severeViolations(page), [], "patcher");
  await page.evaluate(() => { location.hash = "fx"; });
  await page.locator("#cee-fx-slot").waitFor({ timeout: 15_000 });
  assert.deepEqual(await severeViolations(page), [], "presets");
  await page.click("#cee-tab-samples");
  assert.deepEqual(await severeViolations(page), [], "samples, nothing read");
  await page.click("#cee-sample-open");
  await page.locator("#cee-sample-form h3").waitFor();
  assert.deepEqual(await severeViolations(page), [], "samples, a slot open");
  await page.click("#cee-tab-scripts");
  assert.deepEqual(await severeViolations(page), [], "plugins, catalog");
  await page.click("#cee-scripts-page-editor");
  assert.deepEqual(await severeViolations(page), [], "plugins, editor");
  await page.click("#cee-scripts-page-catalog");
  await page.click("#cee-catalog-blechclicker .cee-catalog-open");
  await page.click("#cee-detail-copy");
  await page.click("#cee-script-preview");
  await page.locator("#cee-sim-state", { hasText: "Lauf:" }).waitFor();
  assert.deepEqual(await severeViolations(page), [], "plugins, running in the preview");
  await page.click("#cee-plugin-run-close");
  await page.click("#cee-scripts-page-catalog");
  await page.click("#cee-catalog-snake .cee-catalog-open");
  await page.locator("#cee-sim-state", { hasText: "Lauf: snake" }).waitFor();
  assert.deepEqual(await severeViolations(page), [], "plugins, the page of a plugin");
  await page.click("#cee-detail-view-code");
  assert.deepEqual(await severeViolations(page), [], "plugins, the code of a plugin");
  await page.click("#cee-tab-console");
  assert.deepEqual(await severeViolations(page), [], "console");
  await page.click("#cee-tab-scripts");
  for (const id of ["docs", "catalog"]) {
    await page.click(`#cee-scripts-page-${id}`);
    assert.deepEqual(await severeViolations(page), [], `plugins, ${id}`);
  }
  assert.deepEqual(page.errors, []);
});

test("the sidebar tablist holds tabs only, and the options still sit under their entry", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-areas > :not([role=tab])").count(), 0);
  await page.click("#cee-tab-scripts");
  const order = await page.evaluate(() => {
    const y = id => document.getElementById(id).getBoundingClientRect().top;
    return [y("cee-tab-scripts"), y("cee-sub-scripts"), y("cee-tab-baukasten")];
  });
  assert.ok(order[0] < order[1] && order[1] < order[2], `the options are between Plugins and Baukasten: ${order}`);
});

test("the status line does not rebuild itself when the service repeats the same state", async () => {
  const page = await open();
  await powerOn(page);
  await page.evaluate(() => {
    window.__statusMutations = 0;
    new MutationObserver(list => { window.__statusMutations += list.length; }).observe(document.getElementById("cee-emu-status"), { childList: true, subtree: true, characterData: true });
  });
  for (let i = 0; i < 4; i++) fake.broadcast("status", { state: "running", device_ms: 2000 + i * 1000, speed: 1 });
  await page.waitForTimeout(400);
  assert.equal(await page.evaluate(() => window.__statusMutations), 0, "a screen reader would read the line again each second");
  fake.broadcast("status", { state: "hung", error: "Die Firmware hängt." });
  await page.locator("#cee-emu-status", { hasText: "hängt" }).waitFor();
  assert.ok(await page.evaluate(() => window.__statusMutations) > 0, "a real change still goes through");
});

test("the display has a text for what it shows: a screen line only screen readers hear", async () => {
  const page = await open();
  assert.equal(await page.getAttribute("#cee-emu-lcd", "aria-describedby"), "cee-emu-where");
  assert.equal(await page.locator("#cee-emu-where.ui-sr-only").count(), 1);
});

test("the plugin run area touchpad works from the keyboard", async () => {
  const page = await open();
  await page.click("#cee-tab-scripts");
  await page.click("#cee-scripts-page-catalog");
  await page.click("#cee-catalog-blechclicker .cee-catalog-open");
  await page.click("#cee-detail-copy");
  await page.click("#cee-script-preview");
  await page.locator("#cee-sim-state", { hasText: "Lauf:" }).waitFor();
  await page.locator("#cee-sim-touchpad").focus();
  await page.keyboard.down("Space");
  assert.equal(await page.getAttribute("#cee-sim-touchpad", "data-down"), "true");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.up("Space");
  assert.equal(await page.getAttribute("#cee-sim-touchpad", "data-down"), "false");
});

test("below 60rem the menu button moves the focus into the drawer, and Escape gives it back", async () => {
  const page = await open({ width: 600, height: 800 });
  await page.locator("#cee-menu").focus();
  await page.keyboard.press("Enter");
  assert.equal(await page.evaluate(() => !!document.activeElement.closest("#cee-sidebar")), true, "focus is in the drawer");
  await page.keyboard.press("Escape");
  assert.equal(await page.evaluate(() => document.activeElement.id), "cee-menu");
});

test("a file button whose input is hidden shows the keyboard focus on the button", async () => {
  const page = await open();
  await page.click("#cee-tab-scripts");
  await page.click("#cee-scripts-page-catalog");
  await page.click("#cee-scripts-page-mine");
  await page.locator("#cee-script-open").focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  const style = await page.locator("label[for=cee-script-open]").evaluate(n => { const s = getComputedStyle(n); return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) }; });
  assert.notEqual(style.style, "none");
  assert.ok(style.width >= 2);
});

test("the Patcher title is German like the page, no language override", async () => {
  const page = await open();
  await page.click("#cee-tab-patcher");
  assert.equal(await page.getAttribute("#cee-area-patcher h1", "lang"), null);
  assert.equal(await page.locator("#cee-area-patcher h1").textContent(), "Firmware Patcher");
});

test("lit keys keep 4.5:1 for their label, the lit blue PLAY key 3:1 for its symbol", async () => {
  const page = await open();
  await powerOn(page);
  const ratio = await page.evaluate(() => {
    const lum = rgb => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]); };
    const parse = s => {
      const n = s.match(/[\d.]+(?:e-?\d+)?/g).map(Number);
      const rgb = s.startsWith("color(") ? n.slice(0, 3).map(v => v * 255) : n.slice(0, 3);
      const a = n[3] ?? 1;
      return rgb.map((v, i) => v * a + [10, 10, 11][i] * (1 - a));
    };
    const worst = id => {
      const b = document.getElementById(id);
      b.style.setProperty("--cee-e2-glow", "1");
      const cs = getComputedStyle(b);
      const a = lum(parse(cs.backgroundColor)); const t = lum(parse(cs.color));
      return (Math.max(a, t) + 0.05) / (Math.min(a, t) + 0.05);
    };
    return { red: worst("cee-e2-sequencer"), blue: worst("cee-e2-play") };
  });
  assert.ok(ratio.red >= 4.5, `red key at full glow: ${ratio.red}`);
  assert.ok(ratio.blue >= 3, `blue key at full glow: ${ratio.blue}`);
});

test("a focused element is never hidden behind the sticky navbar", async () => {
  const page = await open({ width: 1280, height: 500 });
  await page.click("#cee-tab-scripts");
  await page.click("#cee-scripts-page-catalog");
  await page.click("#cee-catalog-blechclicker .cee-catalog-open");
  await page.click("#cee-detail-copy");
  await page.locator("#cee-script-name:not([disabled])").waitFor();
  await page.evaluate(() => document.activeElement?.blur());
  const hidden = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const at = await page.evaluate(() => {
      const e = document.activeElement;
      if (!e || e === document.body || e.closest(".cee-sidebar, .cee-navbar") || e.tagName === "TEXTAREA" || e.classList.contains("cee-visually-hidden") || e.matches("[role=tabpanel]")) return null;
      const b = e.getBoundingClientRect();
      const top = document.elementFromPoint(Math.min(Math.max(b.left + b.width / 2, 0), innerWidth - 1), Math.min(Math.max(b.top + b.height / 2, 0), innerHeight - 1));
      return top && !top.closest("#app-toasts") && !e.contains(top) && !top.contains(e) ? `${e.id || e.tagName} at ${Math.round(b.top)}` : null;
    });
    if (at) hidden.push(at);
  }
  assert.deepEqual(hidden, []);
});

test("axe: the plugin editor with a completion list, its description, a parameter hint and an error underline", async () => {
  const page = await open();
  await page.click("#cee-tab-scripts");
  await page.click("#cee-scripts-page-catalog");
  await page.click("#cee-catalog-blechclicker .cee-catalog-open");
  await page.click("#cee-detail-copy");
  await page.locator("#cee-script-name:not([disabled])").waitFor();
  await page.evaluate(() => {
    const v = document.getElementById("cee-script-editor").view;
    v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: "let = 3;\nkorg.led(korg.key.TAP, " } });
  });
  await page.locator("#cee-script-text").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("korg.display.te");
  await page.locator(".cm-completionInfo").waitFor();
  assert.deepEqual(await severeViolations(page), [], "completion list open");
  await page.keyboard.press("Escape");
  await page.locator(".cm-tooltip.cee-script-tip").waitFor();
  assert.deepEqual(await severeViolations(page), [], "parameter hint and error underline");
  assert.deepEqual(page.errors, []);
});

test("axe: modulations with the slots, and with a hint showing", async () => {
  const page = await open();
  await page.click("#cee-tab-emu");
  await page.setInputFiles("#cee-emu-vsb", h.file("system.vsb", firmware));
  await page.locator("#cee-emu-vsb ~ .ui-dropzone-files", { hasText: "erkannt" }).waitFor();
  await page.evaluate(() => { location.hash = "mod"; });
  await page.locator("#cee-mod-split").waitFor();
  assert.deepEqual(await severeViolations(page), [], "modulations, nothing edited");
  const slot = page.locator("#cee-mod-slot-0");
  await slot.getByLabel("Quelle").selectOption("1");
  await slot.getByLabel("Ziel").selectOption("5");
  await slot.getByLabel("Stärke bis").fill("30");
  await page.locator("#cee-mod-hint-box").waitFor();
  assert.deepEqual(await severeViolations(page), [], "modulations, a slot with a code of open meaning and its hint");
  assert.deepEqual(page.errors, []);
});
