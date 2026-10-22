import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { severeViolations } from "./support/axe.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const toastNow = (page, message, kind) => page.evaluate(([m, k]) => import("/app/toast.mjs").then(t => { t.toast(m, k); }), [message, kind]);

test("a status label has a gap before its text, shares the line, and its dot is centered", async () => {
  const page = await h.page();
  await page.goto(h.url);
  const r = await page.evaluate(() => {
    const p = document.createElement("p");
    p.id = "probe-status";
    p.innerHTML = '<span class="cee-status" data-tone="ok">sauber</span> Keine Befunde.';
    document.querySelector(".cee-main").append(p);
    p.parentElement.hidden = false;
    const label = p.firstElementChild;
    const s = getComputedStyle(label);
    const range = document.createRange();
    range.setStart(p.lastChild, 1);
    range.setEnd(p.lastChild, 5);
    const text = range.getBoundingClientRect();
    const box = label.getBoundingClientRect();
    const dot = getComputedStyle(label, "::before");
    const pad = parseFloat(s.paddingTop) - parseFloat(s.paddingBottom);
    const centered = Math.abs(parseFloat(dot.marginTop) || 0) < 1 && s.alignItems === "center" && Math.abs(pad) < 1;
    return { display: s.display, centered, apart: text.left - box.right, sameLine: Math.abs((box.top + box.bottom) / 2 - (text.top + text.bottom) / 2) < 4 };
  });
  assert.equal(r.display, "inline-flex", "one inline box with the text that follows");
  assert.equal(r.centered, true, "the dot sits in the middle of the label");
  assert.ok(r.apart >= 4, `a gap between the label and the text, got ${r.apart}`);
  assert.equal(r.sameLine, true, "label and text share the line");
});

test("the device drawing: LEVEL and PAN are as big as ATTACK and DECAY, and the touch indicator stays a circle", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu`);
  const size = async id => { const b = await page.locator(`#cee-e2-${id}`).boundingBox(); return [Math.round(b.width), Math.round(b.height)]; };
  const attack = await size("attack");
  for (const id of ["level", "pan", "decay"]) assert.deepEqual(await size(id), attack, `${id} has the size of attack`);
  const pad = await page.locator("#cee-e2-touchpad").boundingBox();
  const dot = () => page.locator(".cee-e2-touchpoint").evaluate(n => { const b = n.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; });
  const [w0, h0] = await dot();
  assert.equal(w0, h0, "a circle at rest");
  await page.mouse.move(pad.x + 30, pad.y + 30);
  await page.mouse.down();
  for (const [x, y] of [[pad.width - 5, pad.height - 5], [5, pad.height - 5], [pad.width / 2, 5]]) {
    await page.mouse.move(pad.x + x, pad.y + y);
    const [w, hgt] = await dot();
    assert.deepEqual([w, hgt], [w0, h0], "the indicator keeps its size while it is dragged");
  }
  await page.mouse.up();
});

test("settings: the button opens their page, particles go off and stay off, motion follows the system by default", async () => {
  const page = await h.page();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(h.url);
  assert.equal(await page.evaluate(() => document.documentElement.dataset.motion), "reduce", "the system preference is the default");
  await page.click("#cee-settings-button");
  const dialog = page.locator("#cee-area-settings:not([hidden])");
  await dialog.waitFor();
  assert.equal(await dialog.locator("#cee-set-motion").inputValue(), "system");
  assert.equal(await dialog.locator("#cee-set-particles").isChecked(), true);
  assert.deepEqual(await severeViolations(page), [], "settings page");
  await dialog.locator("#cee-set-motion").selectOption("full");
  assert.equal(await page.evaluate(() => document.documentElement.dataset.motion), "full");
  await dialog.locator("label.ui-switch").click();
  assert.equal(await page.locator("#bg-canvas").isHidden(), true);
  await page.reload();
  assert.equal(await page.locator("#bg-canvas").isHidden(), true, "kept in this browser");
  assert.equal(await page.evaluate(() => document.documentElement.dataset.motion), "full");
  await page.evaluate(() => localStorage.removeItem("cee.settings"));
  await page.reload();
  assert.equal(await page.locator("#bg-canvas").isHidden(), false);
  const blocked = await h.page();
  await blocked.addInitScript(() => { Storage.prototype.setItem = () => { throw new Error("blocked"); }; });
  await blocked.goto(h.url);
  assert.equal(await blocked.locator("#cee-settings-button").isVisible(), true, "the page works without storage");
  assert.deepEqual(blocked.errors.filter(e => !/blocked/.test(e)), []);
});

test("toasts: success goes by itself, an error stays until it is closed, live regions say polite and assertive", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await toastNow(page, "Alles gut", "ok");
  await toastNow(page, "Das ging schief", "error");
  const ok = page.locator("#cee-toasts-polite .cee-toast", { hasText: "Alles gut" });
  const bad = page.locator("#cee-toasts-assertive .cee-toast", { hasText: "Das ging schief" });
  await ok.waitFor();
  await bad.waitFor();
  assert.equal(await page.getAttribute("#cee-toasts-polite", "aria-live"), "polite");
  assert.equal(await page.getAttribute("#cee-toasts-assertive", "aria-live"), "assertive");
  assert.deepEqual(await severeViolations(page), [], "toasts");
  await ok.waitFor({ state: "detached", timeout: 8000 });
  assert.equal(await bad.count(), 1, "the error is still there");
  await bad.getByRole("button", { name: "Schließen" }).click();
  await bad.waitFor({ state: "detached" });
});

test("the documentation page shows docs/plugins.md, is searchable and carries the names table", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#scripts`);
  await page.click("#cee-scripts-page-docs");
  await page.locator("#cee-docs-article h2", { hasText: "Plugins für die Electribe" }).waitFor();
  assert.ok(await page.locator("#cee-docs-article .cee-doc-section").count() > 10, "all the sections");
  assert.ok(await page.locator("#cee-docs-article .cee-doc-code").count() >= 3, "code blocks");
  assert.equal(await page.locator("#cee-docs-article a[href]:not([href^=http])").count(), 0, "no link out to files the page does not have");
  assert.equal(await page.locator("#cee-names-body table").count(), 2, "the names table is one section, live");
  await page.fill("#cee-docs-search", "korg.display.take");
  const shown = await page.locator("#cee-docs-article .cee-doc-section:not([hidden])").count();
  assert.ok(shown >= 1 && shown < 10, `the search narrows the page, got ${shown}`);
  await page.fill("#cee-docs-search", "gibtesnirgends");
  await page.locator("#cee-docs-empty").waitFor();
  await page.fill("#cee-docs-search", "");
  assert.ok(await page.locator("#cee-docs-article kbd.cee-key", { hasText: "EXIT" }).count() > 0, "keys of the device stand out in the text");
  assert.equal(await page.locator("#cee-docs-toc").evaluate(n => n.open && getComputedStyle(n).position), "sticky", "on a wide window the contents stay open beside the text");
  assert.deepEqual(await page.locator("#cee-nav-title .cee-crumb").allTextContents(), ["Dokumentation"]);
  await page.locator("#cee-plugin-docs").evaluate(n => { n.scrollTop = n.scrollHeight / 2; n.dispatchEvent(new Event("scroll")); });
  await page.waitForFunction(() => document.querySelectorAll("#cee-nav-title .cee-crumb").length === 2);
  assert.deepEqual(await severeViolations(page), [], "documentation");
});

test("the console greets with one line, help lists the commands and Tab completes korg and KORG names", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#scripts`);
  await page.click("#cee-tab-console");
  assert.equal(await page.locator("#cee-term-help").count(), 0, "no Hilfe disclosure");
  assert.equal(await page.locator("#cee-term-log .cee-term-line").first().textContent(), "Tippe „help“ für die Befehlsliste, „start“ schaltet den Emulator ein.");
  await page.fill("#cee-term-input", "help");
  await page.press("#cee-term-input", "Enter");
  await page.locator(".cee-term-line", { hasText: "KORG.screen.set" }).waitFor();
  await page.fill("#cee-term-input", "KORG.ram.rea");
  await page.press("#cee-term-input", "Tab");
  assert.equal(await page.inputValue("#cee-term-input"), "KORG.ram.read");
  await page.fill("#cee-term-input", "korg.display.te");
  await page.press("#cee-term-input", "Tab");
  assert.equal(await page.inputValue("#cee-term-input"), "korg.display.text");
  await page.fill("#cee-term-input", "KORG.ram.");
  await page.press("#cee-term-input", "Tab");
  await page.locator(".cee-term-line", { hasText: "KORG.ram.snapshot" }).last().waitFor();
});

test("the run page shows the device drawing and sends keys, pads, knobs and the touchpad to the browser VM", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#scripts`);
  await page.click("#cee-scripts-page-editor");
  await page.click("#cee-script-presets [data-id=snake]");
  await page.click("#cee-script-copy");
  await page.locator("#cee-script-name:not([disabled])").waitFor();
  await page.evaluate(() => {
    const v = document.getElementById("cee-script-editor").view;
    v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: [
      'korg.app("T", "TOOLS");', "let a = 0;", "let b = 0;", "let c = 0;",
      'korg.onEvent("pad", (i, down) => { if (down) a = i + 1; });',
      'korg.onEvent("knob", (i, v) => { b = v; });',
      'korg.onEvent("touch", (x, y, first) => { c = x; });',
      'korg.onEvent("frame", () => { korg.display.clear(); korg.display.number(a, 0, 0); korg.display.number(b, 0, 20); korg.display.number(c, 0, 40); });',
    ].join("\n") } });
  });
  await page.locator("#cee-script-problems .cee-script-problem").waitFor({ state: "detached" });
  await page.click("#cee-scripts-page-run");
  assert.equal(await page.locator("#cee-sim .cee-e2-viewport").count(), 1, "the same drawing as the emulator page");
  assert.equal(await page.locator("#cee-sim-level").count(), 1);
  assert.equal(await page.locator("#cee-e2-level").count(), 1, "the emulator drawing keeps its own ids");
  await page.click("#cee-script-run");
  await page.locator("#cee-sim-state", { hasText: "Lauf: " }).waitFor();
  const picture = () => page.evaluate(() => document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data.join(",").length + ":" + [...document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data].reduce((n, v, i) => (n + v * (i % 97 + 1)) % 1000003, 0));
  const settle = () => page.waitForTimeout(350);
  await settle();
  const start = await picture();
  await page.locator("#cee-sim-pad16").dispatchEvent("pointerdown", { button: 0, pointerId: 1 });
  await page.locator("#cee-sim-pad16").dispatchEvent("pointerup", { button: 0, pointerId: 1 });
  await settle();
  const afterPad = await picture();
  assert.notEqual(afterPad, start, "a pad reached the plugin");
  const knob = page.locator("#cee-sim-level");
  await knob.focus();
  for (let i = 0; i < 12; i++) await page.keyboard.press("ArrowUp");
  await settle();
  const afterKnob = await picture();
  assert.notEqual(afterKnob, afterPad, "a knob reached the plugin");
  const pad = await page.locator("#cee-sim-touchpad").boundingBox();
  await page.mouse.move(pad.x + pad.width * 0.8, pad.y + pad.height / 2);
  await page.mouse.down();
  await settle();
  await page.mouse.up();
  const afterTouch = await picture();
  assert.notEqual(afterTouch, afterKnob, "the touchpad reached the plugin");
  assert.deepEqual(await severeViolations(page), [], "run page");
  await page.click("#cee-script-stop");
  assert.deepEqual(page.errors, []);
});

test("the console is a terminal: the line you type stands in the output, help is quoted, no connect button, the forward switch sits in the navbar", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#console`);
  assert.equal(await page.locator("#cee-term-log #cee-term-input").count(), 1, "the input is part of the output box");
  assert.equal(await page.locator("#cee-term-connect, #cee-term-run").count(), 0);
  assert.equal(await page.locator("#cee-term-target").isVisible(), false, "no target line while nothing goes to a device");
  assert.equal(await page.locator("#cee-nav-state label.cee-term-forward").textContent(), "An echtes Gerät weiterleiten");
  await page.click("label.cee-term-forward");
  assert.equal(await page.isChecked("#cee-term-forward"), false, "no device connected: the switch stays off");
  await page.locator("#app-toasts .cee-toast", { hasText: "Echtes Gerät" }).waitFor();
  await page.fill("#cee-term-input", "1 + 1");
  await page.press("#cee-term-input", "Enter");
  await page.locator(".cee-term-error", { hasText: "Tippe „start“" }).waitFor();
  assert.deepEqual(page.errors, []);
});
