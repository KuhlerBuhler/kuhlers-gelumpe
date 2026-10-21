import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp } from "./harness.mjs";
import { parseAll, parseBlech, packBlech } from "../../src/script/archive.mjs";
import { compile } from "../../src/script/compiler.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

async function open(viewport) {
  const page = await h.page();
  if (viewport) await page.setViewportSize(viewport);
  await page.goto(`${h.url}#scripts`);
  await page.locator("#cee-scripts-page-editor").evaluate(n => n.click());
  await page.locator("#cee-script-text").waitFor();
  return page;
}

/** How many pixels of the simulated display are on (dark ink on light paper). */
const lit = page => page.evaluate(() => {
  const data = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
  let n = 0;
  for (let i = 0; i < data.length; i += 4) if (data[i] + data[i + 1] + data[i + 2] < 384) n += 1;
  return { n };
});

/** The text of the editor and a way to replace it, through the editor's own view (kept on its host element). */
const sourceOf = page => page.evaluate(() => document.getElementById("cee-script-editor").view.state.doc.toString());
const setSource = (page, text) => page.evaluate(t => {
  const view = document.getElementById("cee-script-editor").view;
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: t } });
}, text);

/** The pages of Plugins are sub-items of its sidebar entry: the editor, the run area, the console, the names, the catalog. */
const onEditor = page => page.click("#cee-scripts-page-editor");
const onRun = page => page.click("#cee-scripts-page-run");

const ownNames = page => page.locator("#cee-script-own .cee-pattern-item span:first-child").allTextContents();

const KLICKER = readFileSync(new URL("../fixtures/scripts/klicker.js", import.meta.url), "utf8");
const TITLES = ["BLECH Clicker", "Set-Timer", "Snake", "Tetris", "Game of Life", "Pong", "Simon", "Mandelbrot", "GIF Player", "Lauflicht", "Pulsieren"];

async function makeOwn(page, from = "snake") {
  await onEditor(page);
  await page.click(`#cee-script-presets [data-id=${from}]`);
  await page.click("#cee-script-copy");
  await page.locator("#cee-script-name:not([disabled])").waitFor();
}

test("the page replaces Terminal and FUN: templates, an editor, the run area and the console", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#scripts`);
  assert.equal(await page.locator("#cee-tab-terminal").count(), 0);
  assert.equal(await page.locator("#cee-tab-fun").count(), 0);
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Plugins");
  assert.deepEqual(await page.locator("#cee-scripts-pages button").allTextContents(), ["Katalog", "Editor", "Lauf", "Dokumentation"], "the pages are sub-items of the Plugins entry");
  assert.equal(await page.locator("#cee-scripts-page-catalog").getAttribute("aria-current"), "", "the catalog is the page that opens first");
  assert.equal(await page.locator("#cee-catalog").isVisible(), true);
  assert.equal(await page.locator("#cee-script-text").isVisible(), false);
  await onEditor(page);
  assert.deepEqual(await page.locator("#cee-script-presets .cee-pattern-item span:first-child").allTextContents(), TITLES);
  assert.equal(await page.locator("#cee-script-text").isVisible(), true, "the editor, once its page is open");
  assert.equal(await page.locator("#cee-term-input").isVisible(), false, "the console is a page of its own");
  assert.equal(await page.locator("#cee-script-run").isVisible(), false, "so is the run area");
  await page.click("#cee-tab-console");
  assert.equal(await page.locator("#cee-term-input").isVisible(), true);
  assert.equal(await page.locator("#cee-script-text").isVisible(), false, "the editor gives way to the page that is open");
  await page.click("#cee-tab-scripts");
  await onRun(page);
  assert.equal(await page.locator("#cee-script-run").isVisible(), true);
  await onEditor(page);
  assert.equal(await page.locator("#cee-script-readonly").isVisible(), true, "a template is read only");
  assert.equal(await page.locator("#cee-script-text").getAttribute("aria-readonly"), "true");
  assert.equal(await page.evaluate(() => document.getElementById("cee-script-editor").view.state.readOnly), true);
  assert.match(await page.locator("#cee-script-status").textContent(), /Block \d+ Byte.*Variablen \d+ von 32768/);
  assert.deepEqual(page.errors, []);
});

test("a template opens as an own script, edits are kept across a reload, and a compile error names its line", async () => {
  const page = await open();
  await makeOwn(page);
  assert.deepEqual(await ownNames(page), ["snake"]);
  await setSource(page, "let a = 1;\nlet = 2;\n");
  await page.locator("#cee-script-problems .cee-script-problem").waitFor();
  assert.match(await page.locator("#cee-script-problems").textContent(), /Zeile 2, Spalte/);
  assert.equal(await page.locator("#cee-script-editor .cee-script-gutter [data-state=error]").textContent(), "2");
  await onRun(page);
  assert.equal(await page.locator("#cee-script-run").isDisabled(), true);
  await onEditor(page);
  assert.ok(await page.locator(".cm-lintRange-error").count() > 0, "the error is underlined in the text");
  await page.click("#cee-script-problems .cee-script-problem");
  const caret = await page.evaluate(() => {
    const view = document.getElementById("cee-script-editor").view;
    const { from, to } = view.state.selection.main;
    return { line: view.state.doc.lineAt(from).number, from: from - view.state.doc.lineAt(from).from + 1, text: view.state.sliceDoc(from, to), focused: view.hasFocus };
  });
  assert.deepEqual(caret, { line: 2, from: Number(/Spalte (\d+)/.exec(await page.locator("#cee-script-problems").textContent())[1]), text: "=", focused: true }, "a click on the error puts the caret on its line and column");
  await setSource(page, "let a = 1;\nkorg.onEvent(\"frame\", () => { a += 1; });\n");
  await page.locator("#cee-script-problems .cee-script-problem").waitFor({ state: "detached" });
  await page.waitForTimeout(450);
  await page.reload();
  await onEditor(page);
  await page.locator("#cee-script-text").waitFor();
  assert.deepEqual(await ownNames(page), ["snake"]);
  assert.match(await sourceOf(page), /a \+= 1/, "the last open script and its text are back");
  await page.fill("#cee-script-name", "zaehler");
  await page.press("#cee-script-name", "Enter");
  await page.locator("#cee-script-own .cee-pattern-item", { hasText: "zaehler" }).waitFor();
  await page.fill("#cee-script-name", "bad name");
  await page.press("#cee-script-name", "Enter");
  assert.match(await page.locator("#app-toasts .cee-toast").last().textContent(), /ASCII|Name/);
  assert.equal(await page.inputValue("#cee-script-name"), "zaehler");
  assert.deepEqual(page.errors, []);
});

test("Klicker runs in the simulated device as an app: TAP counts on its screen and lights its LED", async () => {
  const page = await open();
  await makeOwn(page);
  await page.fill("#cee-script-name", "klicker");
  await page.press("#cee-script-name", "Enter");
  await setSource(page, KLICKER);
  await page.locator("#cee-script-status", { hasText: "Block" }).waitFor();
  await onRun(page);
  await page.click("#cee-script-run");
  await page.locator("#cee-sim-state", { hasText: "Lauf: klicker" }).waitFor();
  assert.match(await page.locator("#cee-sim-screen").textContent(), /zeigt die App „Klicker“/);
  await page.waitForFunction(() => {
    const c = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
    for (let i = 0; i < c.length; i += 4) if (c[i] + c[i + 1] + c[i + 2] < 384) return true;
    return false;
  });
  const before = (await lit(page)).n;
  const tap = page.locator("#cee-sim-tap");
  await tap.click();
  await page.waitForFunction(b => {
    const c = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
    let n = 0;
    for (let i = 0; i < c.length; i += 4) if (c[i] + c[i + 1] + c[i + 2] < 384) n += 1;
    return n !== b;
  }, before);
  assert.equal(await page.locator("#cee-sim-tap").getAttribute("data-lit"), "on", "the TAP key shows its LED");
  await page.click("#cee-script-stop");
  await page.locator("#cee-sim-state", { hasText: "Kein Lauf" }).waitFor();
  await onEditor(page);
  assert.ok(await page.locator("#cee-script-editor .cee-script-gutter [data-state=covered]").count() > 0, "a stopped run marks the lines it ran");
  assert.deepEqual(page.errors, []);
});

test("an app is listed like the device's menu lists it, EXIT leaves it and a button opens it again", async () => {
  const page = await open();
  await page.click("#cee-script-presets [data-id=snake]");
  await onRun(page);
  await page.click("#cee-script-run");
  await page.locator("#cee-sim-state", { hasText: "Lauf: snake" }).waitFor();
  await page.locator("#cee-sim-apps-box").waitFor({ state: "visible" });
  assert.match(await page.locator("#cee-sim-apps").textContent(), /GAMES > Snake/);
  await page.waitForFunction(() => {
    const c = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
    for (let i = 0; i < c.length; i += 4) if (c[i] + c[i + 1] + c[i + 2] < 384) return true;
    return false;
  });
  assert.equal(await page.locator(".cee-sim-app").isDisabled(), true, "it is open already");
  await page.locator("#cee-sim-app-exit").click();
  await page.locator("#cee-sim-screen", { hasText: "Hauptbildschirm" }).waitFor();
  assert.equal((await lit(page)).n, 0, "the display is the device's again, a plugin draws nothing there");
  await page.locator(".cee-sim-app").click();
  await page.locator("#cee-sim-screen", { hasText: "zeigt die App" }).waitFor();
  await page.waitForFunction(() => {
    const c = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
    for (let i = 0; i < c.length; i += 4) if (c[i] + c[i + 1] + c[i + 2] < 384) return true;
    return false;
  });
  await page.click("#cee-script-stop");
  assert.deepEqual(page.errors, []);
});

test("a fault in a running script is listed with its line", async () => {
  const page = await open();
  await makeOwn(page);
  await setSource(page, "let z = 0;\nkorg.onEvent(\"frame\", () => {\n  z = 1 / z;\n});\n");
  await page.locator("#cee-script-status", { hasText: "Block" }).waitFor();
  await onRun(page);
  await page.click("#cee-script-run");
  await page.locator("#cee-script-log .cee-script-fault").first().waitFor();
  assert.match(await page.locator("#cee-script-log").textContent(), /Division durch null.*Zeile 3/);
  await page.click("#cee-script-stop");
  await onEditor(page);
  assert.equal(await page.locator("#cee-script-editor .cee-script-gutter [data-state=error]").textContent(), "3");
});

test("export needs a probe of this text; lines that never ran need a yes; a recorded input covers them", async () => {
  const page = await open();
  await makeOwn(page);
  await page.fill("#cee-script-name", "klick2");
  await page.press("#cee-script-name", "Enter");
  await setSource(page, KLICKER);
  await page.locator("#cee-script-status", { hasText: "Block" }).waitFor();
  assert.equal(await page.locator("#cee-script-export").isDisabled(), true, "no probe yet");
  assert.match(await page.locator("#cee-script-probe-info").textContent(), /nicht geprobt/);
  await onRun(page);
  await page.click("#cee-script-probe");
  await page.locator("#app-toasts .cee-toast", { hasText: "Probe über" }).last().waitFor();
  await onEditor(page);
  assert.ok(await page.locator("#cee-script-editor .cee-script-gutter [data-state=missing]").count() > 0, "the key handler never ran");
  assert.match(await page.locator("#cee-script-probe-info").textContent(), /Zeilen offen/);
  assert.equal(await page.locator("#cee-script-export").isDisabled(), false);

  await page.click("#cee-script-export");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  assert.match(await dialog.textContent(), /Zeilen ohne Lauf/);
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.equal(await page.locator("#app-toasts .cee-toast", { hasText: "gespeichert" }).count(), 0, "no file was written");

  const bytes = await h.download(page, async () => {
    await page.click("#cee-script-export");
    await page.locator("dialog.ui-dialog[open]").getByRole("button", { name: /trotzdem speichern/ }).click();
  });
  const parsed = parseBlech(bytes);
  assert.ok(parsed.ok);
  assert.equal(parsed.parts.header.name, "klick2");
  assert.match(parsed.source, /Klicker|klicker|buttonPress/);

  await onRun(page);
  await page.click("#cee-script-record");
  await page.locator("#cee-sim-state", { hasText: "Lauf: klick2" }).waitFor();
  const tap = page.locator("#cee-sim-tap");
  await tap.click();
  await page.click("#cee-script-record");
  await page.locator("#cee-script-inputs", { hasText: "Eingabefolge: 2 Eingaben" }).waitFor();
  await page.click("#cee-script-probe");
  await onEditor(page);
  await page.locator("#cee-script-probe-info", { hasText: "Probe bestanden" }).waitFor();
  assert.equal(await page.locator("#cee-script-editor .cee-script-gutter [data-state=missing]").count(), 0);
  const clean = await h.download(page, () => page.click("#cee-script-export"));
  assert.ok(parseBlech(clean).ok, "no question once every line with code ran");
  assert.equal(await page.locator("dialog.ui-dialog[open]").count(), 0);

  await setSource(page, `${await sourceOf(page)}\n// edit\n`);
  await page.waitForTimeout(400);
  assert.match(await page.locator("#cee-script-probe-info").textContent(), /nicht geprobt|geändert/, "an edit throws the probe away");
  assert.equal(await page.locator("#cee-script-export").isDisabled(), true);
  assert.deepEqual(page.errors, []);
});

test("all own scripts leave as one e2sPlugin.all that the loader's format check accepts, and a .blech opens again", async () => {
  const page = await open();
  await makeOwn(page, "lauflicht");
  await onRun(page);
  await page.click("#cee-script-probe");
  await page.locator("#app-toasts .cee-toast", { hasText: "Probe über" }).last().waitFor();
  await makeOwn(page, "pulsieren");
  await onRun(page);
  await page.click("#cee-script-probe");
  await page.locator("#app-toasts .cee-toast", { hasText: "Probe über" }).last().waitFor();
  await onEditor(page);
  const bytes = await h.download(page, async () => {
    await page.click("#cee-script-export-all");
    const dialog = page.locator("dialog.ui-dialog[open]");
    if (await dialog.count()) await dialog.getByRole("button", { name: /trotzdem speichern/ }).click();
  });
  const parsed = parseAll(bytes);
  assert.ok(parsed.ok, JSON.stringify(parsed));
  assert.deepEqual(parsed.blocks.map(b => b.name).sort(), ["lauflicht", "pulsieren"]);
  assert.deepEqual(parsed.blocks.map(b => b.error), [null, null]);

  const source = "let n = 0;\nkorg.onEvent(\"frame\", () => { n += 1; });\n";
  const file = packBlech(compile(source, { name: "geladen" }).blob, source).bytes;
  await page.setInputFiles("#cee-script-open", { name: "geladen.blech", mimeType: "application/octet-stream", buffer: Buffer.from(file) });
  await page.locator("#cee-script-own .cee-pattern-item", { hasText: "geladen" }).waitFor();
  assert.equal(await sourceOf(page), source);
  const bare = packBlech(compile(source, { name: "ohnetext" }).blob).bytes;
  await page.setInputFiles("#cee-script-open", { name: "ohnetext.blech", mimeType: "application/octet-stream", buffer: Buffer.from(bare) });
  await page.locator("#app-toasts .cee-toast", { hasText: "keinen Quelltext" }).last().waitFor();
  assert.deepEqual(page.errors, []);
});

test("the console runs a saved script by name and a line of script language on the simulated device", async () => {
  const page = await open();
  await page.click("#cee-tab-console");
  await page.fill("#cee-term-input", 'run("snake")');
  await page.press("#cee-term-input", "Enter");
  await page.locator("#cee-sim-state", { hasText: "Lauf: snake" }).waitFor();
  assert.equal(await page.locator("#cee-plugin-run").isVisible(), true, "a run from the console shows the run area");
  await page.click("#cee-tab-console");
  await page.locator(".cee-term-line", { hasText: "„snake“ läuft" }).waitFor();
  await page.fill("#cee-term-input", 'run("gibtsnicht")');
  await page.press("#cee-term-input", "Enter");
  await page.locator(".cee-term-error", { hasText: "Kein Plugin" }).waitFor();
  await page.fill("#cee-term-input", 'korg.display.text("Hi", 0, 0)');
  await page.press("#cee-term-input", "Enter");
  await page.locator("#cee-sim-state", { hasText: "Lauf: einzeiler" }).waitFor();
  assert.equal(await page.locator("#cee-plugin-run").isVisible(), true);
  await page.waitForFunction(() => {
    const c = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
    let n = 0;
    for (let i = 0; i < c.length; i += 4) if (c[i] + c[i + 1] + c[i + 2] < 384) n += 1;
    return n > 5 && n < 60;
  });
  assert.deepEqual(page.errors, []);
});

test("on a phone the page does not scroll sideways and the list is a drawer", async () => {
  const page = await open({ width: 375, height: 812 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
  assert.equal(await page.locator("#cee-scripts-side").isVisible(), false);
  await page.click("#cee-scripts-split .ui-split-toggle");
  assert.equal(await page.locator("#cee-scripts-side").isVisible(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
});

test("a page a script adds with korg.menu.add shows under the run area, and turning it reaches the script", async () => {
  const page = await open();
  await makeOwn(page);
  await setSource(page, `
    korg.app("Test", "TOOLS");
    let shown = 0;
    let id = korg.menu.add("Speed", 1, 10, 3);
    korg.onEvent("menu", (which, value) => { shown = value; });
    korg.onEvent("frame", () => { korg.display.clear(); korg.display.number(shown, 0, 0); });
  `);
  await page.locator("#cee-script-problems .cee-script-problem").waitFor({ state: "detached" });
  await onRun(page);
  await page.click("#cee-script-run");
  await page.locator("#cee-sim-state", { hasText: "Lauf:" }).waitFor();
  await page.locator("#cee-sim-menu-box").waitFor({ state: "visible" });
  await page.locator("#cee-sim-menu-box summary").click();
  assert.match(await page.locator("#cee-sim-menu-pages").textContent(), /Speed \(.+\)/);
  assert.equal(await page.locator("#cee-sim-menu-0").inputValue(), "3");
  await page.locator("#cee-sim-menu-0").fill("8");
  await page.waitForTimeout(250);
  assert.equal(await page.locator("#cee-sim-menu-pages output").textContent(), "8");
  const before = (await lit(page)).n;
  assert.ok(before > 0, "the script drew the value it got");
  await page.click("#cee-script-stop");
  assert.deepEqual(page.errors, []);
});

/** Put the caret at the character after `needle`'s first letter in the editor, the way a click would. */
const caretIn = (page, needle) => page.evaluate(word => {
  const view = document.getElementById("cee-script-editor").view;
  const at = view.state.doc.toString().indexOf(word) + 1;
  view.focus();
  view.dispatch({ selection: { anchor: at } });
}, needle);

/** Click into the editor, empty it and type like a person does, with the completion running. */
async function typeFresh(page, text) {
  await setSource(page, "");
  await page.locator("#cee-script-text").click();
  await page.keyboard.type(text);
}

const options = page => page.locator(".cm-tooltip-autocomplete li");

/**
 * Wait until the completion list shows exactly `labels`. The list follows the text with a short delay; under load
 * it can still show the list of an earlier prefix when the typing is done, and Enter would then take a stale entry.
 */
const offered = (page, labels) => page.waitForFunction(want => {
  const got = [...document.querySelectorAll(".cm-tooltip-autocomplete li .cm-completionLabel")].map(n => n.textContent);
  return got.length === want.length && got.every((label, i) => label === want[i]);
}, labels);

/**
 * CodeMirror ignores Enter for `interactionDelay` ms (default 75, site/app/script-editor.mjs keeps it) after the list
 * opened, so a quick Enter is not taken by accident. A test that presses Enter right after the list appears hits that
 * window when the machine is busy and gets a line break instead. Wait out the delay, measured from the moment the
 * list is known to be open, then press Enter.
 */
const INTERACTION_DELAY_MS = 75;
async function accept(page, key = "Enter") {
  await page.waitForTimeout(INTERACTION_DELAY_MS + 25);
  await page.keyboard.press(key);
}

test("the editor names a number under the caret and puts a name from the list of names at the caret", async () => {
  const page = await open();
  await makeOwn(page);
  await setSource(page, "korg.onEvent(\"buttonPress\", (key) => {\n  if (key == 11) korg.led(20, 255);\n});\n");
  await caretIn(page, "11");
  await page.locator("#cee-script-hint", { hasText: "11 ist die Taste ◄ Part (korg.key.PART_LEFT)." }).waitFor();
  await caretIn(page, "20");
  assert.match(await page.locator("#cee-script-hint").textContent(), /korg\.led\.TAP/);
  await setSource(page, "const K = ");
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.click("#cee-scripts-page-docs");
  await page.locator("#cee-names-body").waitFor();
  await page.fill("#cee-names-filter", "pad 3");
  assert.deepEqual(await page.locator("#cee-names-body td:nth-child(2)").allTextContents(), ["48", "49"]);
  await page.fill("#cee-names-filter", "");
  await page.locator("#cee-names-body button", { hasText: "korg.key.TAP" }).click();
  await page.locator("#app-toasts .cee-toast", { hasText: "korg.key.TAP kopiert" }).waitFor();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), "korg.key.TAP");
  assert.deepEqual(page.errors, []);
});

test("typing korg.disp offers the display functions, each with its parameters and a German description", async () => {
  const page = await open();
  await makeOwn(page);
  await typeFresh(page, "korg.disp");
  await options(page).first().waitFor();
  const labels = await options(page).locator(".cm-completionLabel").allTextContents();
  assert.ok(labels.includes("korg.display.text") && labels.includes("korg.display.clear") && labels.includes("korg.display.rect"), labels.join(", "));
  const text = options(page).filter({ has: page.locator(".cm-completionLabel", { hasText: /^korg\.display\.text$/ }) });
  assert.match(await text.locator(".cm-completionDetail").textContent(), /\(text, x, y\)/);
  await page.keyboard.type("lay.te");
  await page.locator(".cm-completionInfo .cee-script-tip-text", { hasText: "Schreibt einen Text" }).waitFor();
  const info = await page.locator(".cm-completionInfo").textContent();
  assert.match(info, /korg\.display\.text\(text, x, y\)/);
  assert.match(info, /x: 0 bis 127/);
  assert.match(info, /y: 0 bis 63/);
  assert.match(info, /Erlaubt: in allen Ereignissen außer dem Rumpf und save/);
  await accept(page);
  assert.equal(await sourceOf(page), "korg.display.text(text, x, y)", "the call goes in with its parameters as fields");
  await page.keyboard.type("\"Hi\"");
  await page.keyboard.press("Tab");
  assert.equal(await sourceOf(page), "korg.display.text(\"Hi\", x, y)");
  await page.locator(".cm-tooltip .cee-script-tip-active", { hasText: "x" }).waitFor();
  assert.match(await page.locator(".cm-tooltip .cee-script-tip-note").textContent(), /x: 0 bis 127/);
  assert.deepEqual(page.errors, []);
});

test("the names after korg.key. and korg.led. and the events inside korg.onEvent are offered with a description", async () => {
  const page = await open();
  await makeOwn(page);
  await typeFresh(page, "korg.key.PART_L");
  await offered(page, ["PART_LEFT"]);
  assert.deepEqual(await options(page).locator(".cm-completionLabel").allTextContents(), ["PART_LEFT"]);
  assert.match(await page.locator(".cm-completionInfo").textContent(), /Taste ◄ Part, Code 11/);
  await accept(page);
  assert.equal(await sourceOf(page), "korg.key.PART_LEFT");

  await typeFresh(page, "korg.onEvent(\"buttonP");
  await offered(page, ["buttonPress"]);
  assert.deepEqual(await options(page).locator(".cm-completionLabel").allTextContents(), ["buttonPress"]);
  assert.match(await options(page).locator(".cm-completionDetail").textContent(), /\(key\)/);
  assert.match(await page.locator(".cm-completionInfo").textContent(), /Eine Taste wurde gedrückt/);
  await accept(page);
  assert.equal(await sourceOf(page), "korg.onEvent(\"buttonPress\", (key) => {\n  \n});");
  await typeFresh(page, "korg.app(\"Spiel\", \"G");
  await offered(page, ["GAMES"]);
  await accept(page);
  assert.equal(await sourceOf(page), "korg.app(\"Spiel\", \"GAMES\");");
  // Tab takes a suggestion like Enter
  await typeFresh(page, "korg.app(\"Spiel\", \"T");
  await offered(page, ["TOOLS"]);
  await accept(page, "Tab");
  assert.equal(await sourceOf(page), "korg.app(\"Spiel\", \"TOOLS\");");
  assert.equal(await page.evaluate(() => document.activeElement?.id), "cee-script-text", "Tab with a list open stays in the editor");
  await setSource(page, "let a = 1;");
  await page.locator("#cee-script-text").click();
  await page.keyboard.press("End");
  await page.keyboard.press("Tab");
  assert.equal(await sourceOf(page), "let a = 1;", "Tab without a list inserts nothing");
  assert.notEqual(await page.evaluate(() => document.activeElement?.id), "cee-script-text", "and moves on to the next control");
  assert.deepEqual(page.errors, []);
});

test("hovering a name shows its description, and a compile error is underlined in the text", async () => {
  const page = await open();
  await makeOwn(page);
  await setSource(page, "korg.display.text(\"a\", 1, 2);\nlet = 3;\n");
  await page.locator(".cm-lintRange-error").first().waitFor();
  await page.locator("#cee-script-editor").scrollIntoViewIfNeeded();
  const at = await page.evaluate(() => {
    const view = document.getElementById("cee-script-editor").view;
    const box = view.coordsAtPos(8);
    return { x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 };
  });
  await page.mouse.move(at.x, at.y);
  await page.locator(".cm-tooltip .cee-script-tip-text", { hasText: "Schreibt einen Text" }).waitFor();
  assert.match(await page.locator(".cm-tooltip .cee-script-tip-sig").textContent(), /korg\.display\.text\(text, x, y\)/);
  assert.deepEqual(page.errors, []);
});

test("the editor is a labelled, keyboard reachable text box: Tab leaves it, the page stays one column on a phone", async () => {
  const page = await open();
  await makeOwn(page);
  await page.setViewportSize({ width: 375, height: 812 });
  const box = page.locator("#cee-script-text");
  assert.equal(await box.getAttribute("role"), "textbox");
  assert.equal(await box.getAttribute("aria-multiline"), "true");
  assert.equal(await box.getAttribute("aria-label"), "Plugin-Code");
  await box.focus();
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => !!document.activeElement.closest("#cee-script-editor")), false, "Tab is no trap");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
});

for (const [label, group, draws] of [["App in GAMES", "GAMES", true], ["App in TOOLS", "TOOLS", true], ["Hintergrund", null, false]]) {
  test(`Neues Plugin asks for the name, then the kind, and the "${label}" template runs in the Lauf area`, async () => {
    const page = await open();
    const name = `neu_${label.split(" ").at(-1).toLowerCase()}`;
    await page.click("#cee-script-new");
    const prompt = page.locator("dialog.ui-dialog[open]");
    await prompt.locator("input[name=value]").fill(name);
    await prompt.getByRole("button", { name: "Übernehmen" }).click();
    const kind = page.locator("#cee-script-kind[open]");
    await kind.waitFor();
    assert.deepEqual(await kind.locator(".ui-segmented-option").allTextContents(), ["App in GAMES", "App in TOOLS", "Hintergrund"]);
    await kind.locator("label.ui-segmented-option", { hasText: label }).click();
    await page.locator("#cee-script-kind-hint", { hasText: group ? "Menü BLECH" : "ohne Display" }).waitFor();
    await kind.getByRole("button", { name: "Anlegen" }).click();
    await page.locator("#cee-script-own .cee-pattern-item", { hasText: name }).waitFor();
    const source = await sourceOf(page);
    assert.match(source, group ? new RegExp(`korg\\.app\\("${name}", "${group}"\\)`) : /^(?!.*korg\.app)/s);
    assert.match(source, /korg\.key\.TAP/);
    assert.match(await page.locator("#cee-script-status").textContent(), /^Block \d+ Byte/);
    assert.equal(await page.locator("#cee-script-problems .cee-script-problem").count(), 0, "the template compiles");
    await onRun(page);
    await page.click("#cee-script-probe");
    await page.locator("#app-toasts .cee-toast", { hasText: "Probe über" }).last().waitFor();
    await page.click("#cee-script-run");
    await page.locator("#cee-sim-state", { hasText: `Lauf: ${name}` }).waitFor();
    if (draws) {
      await page.waitForFunction(() => {
        const c = document.getElementById("cee-sim-lcd").getContext("2d").getImageData(0, 0, 128, 64).data;
        for (let i = 0; i < c.length; i += 4) if (c[i] + c[i + 1] + c[i + 2] < 384) return true;
        return false;
      });
      assert.match(await page.locator("#cee-sim-apps").textContent(), new RegExp(`${group} > ${name}`));
    } else {
      await page.waitForTimeout(300);
      assert.equal((await lit(page)).n, 0, "a background plugin draws nothing");
      assert.equal(await page.locator("#cee-sim-apps-box").isVisible(), false, "and has no menu entry");
    }
    assert.equal(await page.locator("#cee-script-log .cee-script-fault").count(), 0);
    await page.click("#cee-script-stop");
    assert.deepEqual(page.errors, []);
  });
}

test("Neues Plugin: cancelling the kind dialog creates nothing", async () => {
  const page = await open();
  await page.click("#cee-script-new");
  const prompt = page.locator("dialog.ui-dialog[open]");
  await prompt.locator("input[name=value]").fill("abbruch");
  await prompt.getByRole("button", { name: "Übernehmen" }).click();
  const kind = page.locator("#cee-script-kind[open]");
  await kind.waitFor();
  await page.keyboard.press("Escape");
  await kind.waitFor({ state: "detached" });
  assert.deepEqual(await ownNames(page), []);
});

test("the catalog shows each bundled plugin as a card with a picture of its display, a .blech to download and its code to look at", async () => {
  const page = await open();
  await page.click("#cee-scripts-page-catalog");
  const cards = page.locator("#cee-catalog .cee-catalog-card");
  assert.deepEqual(await cards.locator("h3").allTextContents(), TITLES);
  assert.equal(await cards.locator("p.muted").count(), TITLES.length, "one short description each");
  // The picture is the display after some frames of the browser VM; a plugin that only lights LEDs shows its pads.
  const inked = await page.locator(".cee-catalog-thumb").evaluateAll(list => list.map(c => {
    const data = c.getContext("2d").getImageData(0, 0, 128, 64).data;
    let n = 0;
    for (let i = 0; i < data.length; i += 4) if (data[i] + data[i + 1] + data[i + 2] < 384) n += 1;
    return n;
  }));
  assert.ok(inked.every(n => n > 0), `every thumbnail has something drawn: ${inked}`);
  const bytes = await h.download(page, () => cards.nth(2).getByRole("button", { name: "Herunterladen" }).click());
  const parsed = parseBlech(bytes);
  assert.ok(parsed.ok);
  assert.equal(parsed.parts.header.name, "snake");
  assert.match(parsed.source, /korg\.app/);
  await cards.nth(2).getByRole("button", { name: "Code ansehen" }).click();
  assert.equal(await page.locator("#cee-script-text").isVisible(), true, "the code opens in the editor");
  assert.match(await sourceOf(page), /korg\.app\("Snake"/);
  assert.equal(await page.locator("#cee-script-text").getAttribute("aria-readonly"), "true", "read only");
  assert.equal(await page.locator("#cee-scripts-page-editor").getAttribute("aria-current"), "");
  assert.deepEqual(page.errors, []);
});

test("without own plugins the list says so as a plain line, and the editor takes the whole height of the page", async () => {
  const page = await open();
  assert.equal(await page.locator("#cee-script-own").isVisible(), false);
  assert.equal(await page.locator(".cee-ws-empty").textContent(), "Noch keine eigenen.");
  assert.equal(await page.locator(".cee-ws-empty").evaluate(n => n.closest("li") === null && n.matches("p")), true);
  const box = await page.locator("#cee-script-editor").boundingBox();
  const view = page.viewportSize();
  assert.ok(box.y + box.height > view.height - 120, `the editor reaches down the page: bottom ${box.y + box.height} of ${view.height}`);
  await makeOwn(page);
  assert.equal(await page.locator(".cee-ws-empty").isVisible(), false);
  assert.equal(await page.locator("#cee-script-own").isVisible(), true);
});
