import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { setUp } from "./harness.mjs";
import { tempDir } from "../support/lifetime.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";
import { makeFirmware } from "../helpers.mjs";
import { applyPatches, splashPatch, SPLASH_W, SPLASH_H } from "../../src/patch.mjs";
import { sha256 } from "../../src/firmware.mjs";
import { field } from "../../src/map/index.mjs";
import { STOCK_SHA256, HACKTRIBE_SHA256, HACKTRIBE_PATCH_URL, SYNTH_SHA256 } from "../../src/patcher.mjs";
import { expected, fakeFirmware, fixture, sha } from "../fixtures/bsdiff/data.mjs";

// The real BLECH patches only fit Korg's bytes, which never come into the repository. The page
// loads the set data/patches/blech.json and the patches it lists from fixed addresses, so these
// tests serve a set of their own there, with four small patches.
const SD_DIR = tempDir("cee-e2e-sd-");
const SPLASH = field("splash").where.offset;
const FREE = 0x1a2100;
const checker = Uint8Array.from({ length: SPLASH_W * SPLASH_H }, (_, i) => (i & 1));
const raw = async (id, name, at, bytes, startPhase) => ({
  format: "gelumpe-patch", version: 1, id, name,
  changes: [{ file: at, bytes, expect: await sha256(new Uint8Array(4)) }],
  ...(startPhase ? { startPhase: [{ file: at, length: 4, why: "test" }] } : {}),
});
let patches;
let h;
let fake;

before(async () => {
  patches = [
    await raw("splash-editor", "Startbild-Editor", FREE, "e12fff1e", true),
    await raw("mfx-switch", "MFX 2", FREE + 0x100, "e3a00000"),
    await raw("blechtribe", "Kartenordner blechtribe", FREE + 0x200, "626c6563", true),
    { ...splashPatch(checker), name: "Blech-Startbild" },
    await raw("doom-loader", "Doom-Lader", FREE + 0x300, "e3a00001"),
  ];
  h = await setUp(dir => {
    mkdirSync(join(dir, "patches"));
    mkdirSync(join(dir, "blechy"));
    writeFileSync(join(dir, "patches", "splash-editor.json"), JSON.stringify(patches[0]));
    writeFileSync(join(dir, "patches", "mfx-switch.json"), JSON.stringify(patches[1]));
    writeFileSync(join(dir, "patches", "blechtribe.json"), JSON.stringify(patches[2]));
    writeFileSync(join(dir, "blechy", "splash.json"), JSON.stringify(patches[3]));
    writeFileSync(join(dir, "patches", "doom-loader.json"), JSON.stringify(patches[4]));
    writeFileSync(join(dir, "patches", "blech.json"), JSON.stringify({
      format: "gelumpe-patch-set", version: 1, id: "blech", name: "BLECH",
      patches: ["data/patches/splash-editor.json", "data/patches/mfx-switch.json", "data/patches/blechtribe.json", "assets/blechy/splash.json", "data/patches/doom-loader.json"],
    }));
    const synthPatch = { ...patches[1], id: "synth-test", name: "Synth-Testpatch", builds: ["synth"] };
    writeFileSync(join(dir, "patches", "synth-test.json"), JSON.stringify(synthPatch));
    writeFileSync(join(dir, "patches", "blech-synth.json"), JSON.stringify({
      format: "gelumpe-patch-set", version: 1, id: "blech-synth", name: "BLECH Synth",
      patches: ["data/patches/synth-test.json"],
    }));
    // no copy of these test files has passed before: the check runs (src/patcher.mjs, verifiedReport)
    writeFileSync(join(dir, "patches", "verified.json"), JSON.stringify({ format: "gelumpe-verified", version: 1, results: [] }));
    return [["/data/patches/", `${dir}/patches/`], ["/assets/blechy/", `${dir}/blechy/`]];
  });
  fake = await fakeService(new URL(h.url).origin, { sdDir: SD_DIR });
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

async function patcherPage() {
  const page = await h.page();
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-patcher");
  await page.locator(".cee-patch-title").waitFor();
  return page;
}

const drop = (page, bytes) => page.setInputFiles("#cee-patch-file", h.file("SYSTEM.VSB", bytes));

async function patched(page, vsb) {
  await drop(page, vsb);
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  await page.click("#cee-patch-next");
}

test("patcher: the page holds the title, no big image, a drop zone and nothing of the old export", async () => {
  const page = await patcherPage();
  assert.equal(await page.locator(".cee-patch-title").textContent(), "Firmware Patcher");
  assert.equal(await page.locator("#cee-patch-hero-view, #cee-patcher canvas").count(), 0, "no picture on the page");
  assert.equal(await page.locator("#cee-patch-file").count(), 1);
  assert.equal(await page.locator("#cee-export-check, #cee-export-download, #cee-export-splash").count(), 0);
  assert.equal(await page.isDisabled("#cee-patch-download").catch(() => true), true);
  assert.deepEqual(page.errors, []);
});

test("patcher: Weiter and Zurück walk the four steps, Korg's firmware cards sit on the first", async () => {
  const page = await patcherPage();
  const cards = page.locator("#cee-patch-step-1 #cee-patch-firmware a.cee-device-card");
  assert.deepEqual(await cards.evaluateAll(list => list.map(a => [a.dataset.device, a.href, a.target])), [
    ["red", "https://www.korg.com/us/support/download/product/0/368/#software", "_blank"],
    ["blue", "https://www.korg.com/us/support/download/product/0/367/#software", "_blank"],
  ]);
  const tone = await cards.evaluateAll(list => list.map(a => getComputedStyle(a.querySelector(".cee-e2-outline")).color));
  assert.notEqual(tone[0], tone[1], "each card draws its Electribe in the device's colour");
  assert.equal(await page.isVisible("#cee-patch-back"), false, "no way back from the first step");
  assert.equal(await page.isDisabled("#cee-patch-next"), true, "Weiter waits for a file");
  await drop(page, await makeFirmware());
  await page.waitForFunction(() => document.querySelector("#cee-patch-file-info").textContent === "SYSTEM.VSB: Hacktribe 2.02 erkannt");
  assert.equal(await page.locator("#cee-patcher .ui-dropzone:has(#cee-patch-file)").getAttribute("data-filled"), "", "the field shows that it holds a file");
  await page.click("#cee-patch-next");
  assert.equal(await page.isVisible("#cee-patch-step-2"), true);
  assert.equal(await page.locator("#cee-patch-way [aria-current=step]").textContent(), "2Patches anwenden");
  assert.ok(await page.locator("#cee-patch-plan li").count() > 0, "the patches that go on are listed");
  assert.equal(await page.isVisible("#cee-patch-latest"), true, "the second step chooses the patches");
  assert.equal(await page.isVisible("#cee-patch-run"), false, "the run is on the third step, with the test");
  await page.click("#cee-patch-back");
  assert.equal(await page.isVisible("#cee-patch-step-1"), true);
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.locator("#cee-patch-step-3").waitFor();
  await page.waitForFunction(() => !document.querySelector("#cee-patch-next").disabled);
  await page.click("#cee-patch-next");
  assert.equal(await page.isVisible("#cee-patch-download"), true);
  assert.equal(await page.isVisible("#cee-patch-next"), false, "the last step has no Weiter");
  assert.deepEqual(page.errors, []);
});

test("patcher: a file that is no VSB, or not the measured firmware, is named and cannot be patched", async () => {
  const page = await patcherPage();
  await drop(page, new Uint8Array(100));
  await page.locator("#app-toasts .cee-toast", { hasText: "Das ist keine Firmware-Datei" }).waitFor();
  assert.equal(await page.isDisabled("#cee-patch-next"), true);
  await drop(page, new Uint8Array(0x200100));
  await page.locator("#app-toasts .cee-toast", { hasText: "Diese Firmware kennt der Patcher nicht" }).waitFor();
  assert.equal(await page.locator("#cee-patch-verdict").evaluate(n => n.classList.contains("ui-sr-only")), true, "on the page it is only the toast");
  assert.equal(await page.isDisabled("#cee-patch-next"), true);
  assert.deepEqual(page.errors, []);
});

test("patcher: a file that already carries the patches reads as BLECH and is not patched again", async () => {
  const page = await patcherPage();
  const done = await applyPatches(await makeFirmware(), patches);
  assert.equal(done.ok, true, done.reasons.join(" "));
  await drop(page, done.bytes);
  await page.locator("#app-toasts .cee-toast", { hasText: "BLECHTRIBE schon drauf" }).waitFor();
  assert.equal(await page.isDisabled("#cee-patch-next"), true);
  assert.equal(await page.locator("#cee-patch-download").isVisible(), false);
});

test("patcher: patching, the emulator check, then the download and the guide", async () => {
  const page = await patcherPage();
  const vsb = await makeFirmware();
  await drop(page, vsb);
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-next");
  assert.equal(await page.locator("#cee-patch-result").isVisible(), false, "nothing to download before the check");
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  assert.equal(await page.locator("#cee-patch-steps").count(), 0, "no list of what was done");
  assert.equal(await page.locator("#cee-patch-verdict").isVisible(), false, "no line about what was recognised");
  await page.locator("#app-toasts .cee-toast", { hasText: "Im Emulator bestanden." }).waitFor();
  assert.equal(await page.locator("#cee-patch-bar").getAttribute("aria-valuenow"), "100");
  await page.locator("#cee-patch-details > summary").click();
  assert.match(await page.locator("#cee-patch-checks").textContent(), /bestanden Notschalter/, "the single checks stay behind the disclosure");
  assert.equal(await page.locator("#cee-patch-done").isVisible(), false, "the guide comes after the download");

  const { length, allow, allowCode, pair, hardware } = fake.seen.check;
  assert.equal(length, 2 * 0x200100);
  assert.equal(hardware, null, "the red's file names no hardware, the service takes its own");
  assert.equal(allow, `0x${SPLASH.toString(16)}:1024`);
  assert.equal(allowCode, `0x${FREE.toString(16)}:4,0x${(FREE + 0x200).toString(16)}:4`, "the start-phase spans of every patch in the set reach the check");
  assert.deepEqual(new Uint8Array(pair.subarray(0, 0x200100)), vsb, "the check gets the user's file as the original");

  await page.click("#cee-patch-next");
  const bytes = await h.download(page, () => page.click("#cee-patch-download"));
  assert.deepEqual(bytes, new Uint8Array(pair.subarray(0x200100)), "the download is the copy that was checked");
  const changed = [];
  for (let i = 0; i < bytes.length; i++) if (bytes[i] !== vsb[i]) changed.push(i);
  assert.ok(changed.length > 0 && changed.every(i => (i >= SPLASH && i < SPLASH + 1024) || (i >= FREE && i < FREE + 4) || (i >= FREE + 0x100 && i < FREE + 0x104) || (i >= FREE + 0x200 && i < FREE + 0x204) || (i >= FREE + 0x300 && i < FREE + 0x304)));

  const guide = page.locator("#cee-patch-done");
  await guide.waitFor();
  assert.equal(await guide.locator("h2").textContent(), "Viel Spaß beim BLECHEN");
  const text = await guide.textContent();
  assert.match(text, /KORG\/hacktribe\/System\//);
  assert.match(await guide.locator("#cee-patch-guide-copy").textContent(), /Kopiere auf der Karte den Ordner KORG\/hacktribe\/ nach KORG\/blechtribe\/\. Kopieren, nicht umbenennen/);
  assert.match(await guide.locator("#cee-patch-guide-vsb").textContent(), /nach KORG\/hacktribe\/System\/, also in den Ordner der Firmware, die jetzt auf dem Gerät läuft, nicht nach blechtribe/);
  const doom = guide.locator("#cee-patch-guide-doom");
  assert.match(await doom.textContent(), /Für Doom \(SHIFT \+ TAP beim Einschalten\): doom\.bin und doom\.wad laden und auf der Karte nach KORG\/blechtribe\/Doom\/ legen\./);
  assert.deepEqual(await doom.locator("a[download]").evaluateAll(links => links.map(a => [a.getAttribute("href"), a.getAttribute("download")])), [["third_party/doom/doom.bin", "doom.bin"], ["third_party/doom/doom.wad", "doom.wad"]]);
  assert.match(text, /Sichere die SD-Karte/);
  assert.ok(text.indexOf("Sichere die SD-Karte") < text.indexOf("Kopiere auf der Karte den Ordner") && text.indexOf("Kopiere auf der Karte den Ordner") < text.indexOf("SYSTEM.VSB"), "backup, then the folder copy, then the file");
  assert.match(text, /DATA UTILITY/);
  assert.match(text, /SOFTWARE UPDATE/);
  assert.match(text, /EXIT/);
  assert.deepEqual(page.errors, []);
});

test("patcher: a progress response parsed after completion cannot reset the finished bar", async () => {
  const page = await patcherPage();
  await page.evaluate(() => {
    const fetch = window.fetch;
    window.fetch = (input, ...args) => {
      if (String(input).includes("/check/progress?")) return Promise.resolve({
        ok: true,
        json: () => new Promise(resolve => {
          window.__releaseCheckProgress = () => resolve({ state: "idle" });
        }),
      });
      return fetch(input, ...args);
    };
  });
  fake.hooks.checkDelayMs = 2000;
  try {
    await drop(page, await makeFirmware());
    await page.click("#cee-patch-next");
    await page.click("#cee-patch-next");
    await page.click("#cee-patch-run");
    await page.waitForFunction(() => typeof window.__releaseCheckProgress === "function");
    await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
    const bar = page.locator("#cee-patch-bar");
    assert.equal(await bar.getAttribute("aria-valuenow"), "100");
    await page.evaluate(() => window.__releaseCheckProgress());
    assert.equal(await bar.getAttribute("aria-valuenow"), "100");
    assert.equal(await page.locator("#cee-patch-groups").isVisible(), false);
    assert.deepEqual(page.errors, []);
  } finally {
    fake.hooks.checkDelayMs = 0;
  }
});

test("patcher: Korg's original asks for the user's own hacktribe-2.patch, converts it in the browser and goes on to the stock card folder", async () => {
  const { original, hacktribe } = await fakeFirmware();
  assert.equal(sha(original), expected.fake.original, "the stand-in original; run test/fixtures/bsdiff/make.py again if makeFirmware changed");
  assert.equal(sha(hacktribe), expected.fake.hacktribe, "the made-up Hacktribe file; run test/fixtures/bsdiff/make.py again if makeFirmware changed");
  const page = await h.page();
  // The real hashes belong to Korg's and Hacktribe's files; the page gets those of the made-up ones.
  await page.route(/\/src\/patcher\.mjs$/, async route => {
    const res = await route.fetch();
    const text = (await res.text()).replace(STOCK_SHA256, expected.fake.original).replace(HACKTRIBE_SHA256, expected.fake.hacktribe);
    await route.fulfill({ response: res, body: text });
  });
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-patcher");
  await page.locator(".cee-patch-title").waitFor();
  const requests = [];
  page.on("request", r => requests.push(r.url()));

  assert.equal(await page.locator("#cee-patch-route").isVisible(), false);
  await drop(page, original);
  await page.waitForFunction(() => !document.querySelector("#cee-patch-next").disabled);
  assert.equal(await page.locator("#cee-patch-verdict").isVisible(), false, "no line about what was recognised");
  await page.click("#cee-patch-next");
  await page.locator("#cee-patch-route").waitFor();
  const needs = page.locator("#cee-patch-needs");
  assert.equal(await page.isDisabled("#cee-patch-hacktribe-file"), true, "BLECH direkt is the default, nothing to bring");
  await page.click("#cee-patch-hacktribe-use");
  assert.equal(await page.isDisabled("#cee-patch-hacktribe-file"), false);
  assert.match(await needs.textContent(), /Lizenz erlaubt keine Weitergabe/);
  assert.equal(await page.locator("#cee-patch-hacktribe-link").getAttribute("href"), HACKTRIBE_PATCH_URL, "a direct link to the file");
  assert.equal(await page.isDisabled("#cee-patch-next"), true, "nothing to patch before the conversion");

  const patchFile = (name, bytes) => page.setInputFiles("#cee-patch-hacktribe-file", h.file(name, bytes));
  await patchFile("hacktribe-2.patch", new Uint8Array(100));
  await page.locator("#app-toasts .cee-toast", { hasText: "BSDIFF40" }).waitFor();
  assert.equal(await page.isDisabled("#cee-patch-next"), true, "the wrong file converts nothing");
  await patchFile("hacktribe-2.patch", fixture("./patch/edit.patch"));       // a valid patch, for another file
  await page.locator("#app-toasts .cee-toast", { hasText: "nicht die bekannte Hacktribe-2.02-Datei" }).waitFor();

  await patchFile("hacktribe-2.patch", fixture("./patch/fake-original-to-hacktribe.patch"));
  await page.click("#cee-patch-next");
  assert.equal(await needs.isVisible(), false);
  assert.equal(await page.locator("#app-toasts .cee-toast[data-kind=error]").count(), 2, "the two wrong files told their error, the conversion adds none");
  for (const close of await page.locator("#app-toasts .cee-toast-close").all()) await close.click();
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  assert.deepEqual(new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100)), hacktribe, "the check gets the converted Hacktribe file as the original");
  await page.click("#cee-patch-next");
  const bytes = await h.download(page, () => page.click("#cee-patch-download"));
  assert.deepEqual(bytes, new Uint8Array(fake.seen.check.pair.subarray(0x200100)));
  const guide = page.locator("#cee-patch-done");
  await guide.waitFor();
  assert.match(await guide.textContent(), /KORG\/electribe sampler\/System\//);
  assert.doesNotMatch(await guide.textContent(), /KORG\/hacktribe\/System\//);
  assert.match(await guide.locator("#cee-patch-guide-copy").textContent(), /den Ordner KORG\/electribe sampler\/ nach KORG\/blechtribe\//, "the samples of the stock firmware move too");
  assert.deepEqual(requests.filter(u => /github\.com|hacktribe-2\.patch/.test(u)), [], "the page never fetches the patch");

  // The same for the blue: Korg's firmware runs there, so the copy gets the blue's head and goes to KORG/electribe.
  await page.click("#cee-patch-back");
  await page.click("#cee-patch-back");
  await page.locator("#cee-patch-device-box").waitFor();
  await page.check("#cee-patch-device input[value=blue]");
  assert.match(await page.locator("#cee-patch-device-note").textContent(), /Kopf der blauen/);
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  const blueBase = new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100));
  assert.deepEqual([blueBase[0x12], blueBase[0x2e]], [0x00, 0x23], "the check gets Hacktribe with the blue's head");
  assert.equal(fake.seen.check.hardware, "blue");
  await page.click("#cee-patch-next");
  assert.equal(await page.locator("#cee-patch-path").textContent(), "KORG/electribe/System/SYSTEM.VSB");
  assert.equal(await page.locator("#cee-patch-afraid").isVisible(), false, "the update test would run Korg's red file");
  assert.deepEqual(page.errors, []);
});

test("patcher: Korg's original takes BLECH directly, with no hacktribe-2.patch, and goes on to the stock card folder", async () => {
  const { original } = await fakeFirmware();
  const page = await h.page();
  await page.route(/\/src\/patcher\.mjs$/, async route => {
    const res = await route.fetch();
    await route.fulfill({ response: res, body: (await res.text()).replace(STOCK_SHA256, expected.fake.original) });
  });
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-patcher");
  await page.locator(".cee-patch-title").waitFor();
  const requests = [];
  page.on("request", r => requests.push(r.url()));

  await drop(page, original);
  await page.waitForFunction(() => !document.querySelector("#cee-patch-next").disabled);
  assert.equal(await page.locator("#cee-patch-verdict").isVisible(), false, "no line about what was recognised");
  await page.click("#cee-patch-next");
  await page.locator("#cee-patch-route").waitFor();
  const route = page.locator("#cee-patch-route");
  assert.equal(await page.locator("#cee-patch-hacktribe-use").isChecked(), false, "BLECH direkt is the default");
  assert.equal(await page.isDisabled("#cee-patch-hacktribe-file"), true);
  assert.match(await route.textContent(), /Patche auch Hacktribe/);
  assert.match(await route.textContent(), /Hacktribe ergänzt Filter für den Synth und zusätzliche Effekte\. Den Live-Modus des Editors bringt BLECHTRIBE selbst mit\./);
  assert.equal(await page.locator("#cee-patch-bar").isVisible(), false, "no progress before the run");

  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  assert.deepEqual(new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100)), original, "the check gets Korg's file as the original, nothing converted");
  await page.click("#cee-patch-next");
  const bytes = await h.download(page, () => page.click("#cee-patch-download"));
  assert.deepEqual(bytes, new Uint8Array(fake.seen.check.pair.subarray(0x200100)));
  const guide = page.locator("#cee-patch-done");
  await guide.waitFor();
  assert.match(await guide.textContent(), /KORG\/electribe sampler\/System\//);
  assert.doesNotMatch(await guide.textContent(), /KORG\/hacktribe\/System\//);
  assert.match(await guide.locator("#cee-patch-guide-copy").textContent(), /den Ordner KORG\/electribe sampler\/ nach KORG\/blechtribe\//);
  assert.deepEqual(requests.filter(u => /github\.com|hacktribe-2\.patch/.test(u)), [], "the page fetches nothing of Hacktribe's");
  assert.deepEqual(page.errors, []);
});

test("patcher: a failed emulator check leaves no download", async () => {
  const page = await patcherPage();
  fake.hooks.checkOk = false;
  try {
    await drop(page, await makeFirmware());
    await page.click("#cee-patch-next");
    await page.click("#cee-patch-next");
    await page.click("#cee-patch-run");
    await page.locator("#app-toasts .cee-toast", { hasText: "Die Prüfung hat einen Fehler gefunden (Notschalter" }).waitFor();
    assert.equal(await page.locator("#cee-patch-bar").isVisible(), false, "no bar that looks done after a failure");
    assert.equal(await page.locator("#cee-patch-result").isVisible(), false);
    assert.equal(await page.locator("#cee-patch-done").isVisible(), false);
    assert.equal(await page.locator("#cee-patch-run").textContent(), "Noch einmal patchen und prüfen");
    await page.locator("#cee-patch-details > summary").click();
    assert.match(await page.locator("#cee-patch-checks").textContent(), /nicht bestanden Notschalter/);
  } finally {
    fake.hooks.checkOk = true;
  }
});

test("patcher: while the check runs the bar and the groups follow the service's progress, and it is not done before the result", async () => {
  const page = await patcherPage();
  fake.hooks.checkDelayMs = 4000;
  fake.hooks.checkProgress = { state: "running", total: 10, done: 4, ok: 4, fail: 0, groups: [
    { id: "bootmap", name: "Start", total: 3, done: 3, state: "done", ok: 3, fail: 0 },
    { id: "menu_cases", name: "Menü", total: 2, done: 1, state: "running", ok: 1, fail: 0 },
    { id: "dice_cases", name: "Würfeln", total: 5, done: 0, state: "waiting", ok: 0, fail: 0 }] };
  try {
    await drop(page, await makeFirmware());
    await page.click("#cee-patch-next");
    await page.click("#cee-patch-next");
    await page.click("#cee-patch-run");
    await page.locator("#cee-patch-groups li", { hasText: "Menü" }).waitFor();
    assert.match(await page.locator("#cee-patch-note").textContent(), /^4 von 10, \d+:\d\d$/);
    assert.equal(await page.locator("#cee-patch-bar").getAttribute("aria-valuenow"), "40", "the bar is checks done over total");
    assert.equal(await page.locator("#cee-patch-groups li").count(), 3);
    assert.match(await page.locator("#cee-patch-groups li").first().textContent(), /Start\s*3\/3/);
    assert.equal(await page.locator("#cee-patch-groups li").nth(1).getAttribute("data-state"), "running");
    assert.equal(await page.locator("#cee-patch-steps").count(), 0, "one line of text, no list");
    assert.equal(await page.isDisabled("#cee-patch-download").catch(() => true), true, "no download before the result");
    await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
    // the bar takes the result on the next frame, which a loaded runner can show a moment later than the button
    await page.waitForFunction(() => document.querySelector("#cee-patch-bar").getAttribute("aria-valuenow") === "100", null, { timeout: 5000 });
    assert.equal(await page.locator("#cee-patch-groups").isVisible(), false, "the groups are gone with the result");
    await page.locator("#app-toasts .cee-toast", { hasText: "Im Emulator bestanden." }).waitFor();
  } finally {
    fake.hooks.checkDelayMs = 0;
    fake.hooks.checkProgress = { state: "idle" };
  }
});

test("patcher: with no emulator service the check cannot run and the reason is shown", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#emu=1:${TOKEN}`);
  await page.click("#cee-tab-patcher");
  await drop(page, await makeFirmware());
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.locator("#app-toasts .cee-toast.err", { hasText: "antwortet nicht" }).waitFor();
  assert.equal(await page.locator("#cee-patch-result").isVisible(), false);
});

test("patcher: the fear button puts the copy on the virtual card, runs the user's file in the emulator and shows the hint above it", async () => {
  const page = await patcherPage();
  const vsb = await makeFirmware();
  await patched(page, vsb);
  fake.seen.start = null;
  fake.seen.system = null;
  await page.click("#cee-patch-afraid");
  await page.locator("#cee-area-emu").waitFor({ state: "visible" });
  const hint = page.locator("#cee-patch-hint");
  await hint.waitFor();
  assert.doesNotMatch(await hint.textContent(), /kopiert/, "no folder is copied on the card");
  assert.equal(await hint.textContent(), "Die gepatchte Datei liegt auf der Karte im Emulator unter KORG/hacktribe/System. Am Gerät Menü -> DATA UTILITY -> SOFTWARE UPDATE, MENU drücken, danach neu starten.");
  assert.equal(await page.locator("#cee-area-emu > :first-child").getAttribute("id"), "cee-patch-hint", "the hint stands above the emulator");
  assert.deepEqual(new Uint8Array(fake.seen.firmwareBody), vsb, "the emulator runs the user's own file");
  assert.deepEqual(new Uint8Array(fake.seen.system), new Uint8Array(fake.seen.check.pair.subarray(0x200100)), "the card holds the checked copy");
  assert.deepEqual(fake.seen.start, {});
  await page.click("#cee-patch-hint-close");
  assert.equal(await page.locator("#cee-patch-hint").count(), 0);
  assert.deepEqual(page.errors, []);
});

test("patcher: the hint names the folder the running firmware reads, not a guess", async () => {
  const page = await patcherPage();
  await patched(page, await makeFirmware());
  fake.hooks.korg = "electribe sampler";
  try {
    await page.click("#cee-patch-afraid");
    await page.locator("#cee-patch-hint", { hasText: "KORG/electribe sampler/System" }).waitFor();
  } finally {
    fake.hooks.korg = null;
  }
});


test("patcher: the blue original gets its synth set and trials the copy in electribe/System", async () => {
  const original = await makeFirmware();
  original.set([0x45, 0x32, 0], 0x10);
  original.fill(0xff, 0x170100, 0x170140); // Korg's blue leaves Hacktribe's code run erased
  const hash = await sha256(original);
  const page = await h.page();
  await page.route(/\/src\/patcher\.mjs$/, async route => {
    const res = await route.fetch();
    await route.fulfill({ response: res, body: (await res.text()).replace(SYNTH_SHA256, hash) });
  });
  await page.goto(`${h.url}#emu=${fake.port}:${TOKEN}`);
  await page.click("#cee-tab-patcher");
  await page.locator(".cee-patch-title").waitFor();
  await drop(page, original);
  assert.equal(await page.locator("#cee-patch-route").isVisible(), false);
  await page.click("#cee-patch-next");
  assert.match(await page.locator("#cee-patch-blue-hacktribe:visible").textContent(), /Aus der Firmware der blauen geht kein Hacktribe/);
  assert.equal(await page.locator("#cee-patch-device-box").isVisible(), false, "the blue's own file needs no choice");
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  assert.deepEqual(new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100)), original);
  assert.match(await page.locator("#cee-patch-synth-set").textContent(), /Synth-Testpatch/);
  await page.click("#cee-patch-next");
  const downloaded = await h.download(page, () => page.click("#cee-patch-download"));
  assert.deepEqual(downloaded, new Uint8Array(fake.seen.check.pair.subarray(0x200100)));
  assert.match(await page.locator("#cee-patch-done").textContent(), /KORG\/electribe\/System\//);
  assert.equal(await page.locator("#cee-patch-guide-copy").count(), 0);
  fake.hooks.korg = "electribe";
  try {
    await page.click("#cee-patch-afraid");
    await page.locator("#cee-patch-hint", { hasText: "KORG/electribe/System" }).waitFor();
    assert.deepEqual(new Uint8Array(fake.seen.firmwareBody), original);
    assert.deepEqual(new Uint8Array(fake.seen.system), downloaded);
  } finally {
    fake.hooks.korg = null;
  }
  assert.deepEqual(page.errors, []);
});

test("patcher: Hacktribe for the blue is patched with the Sampler head, checked on the blue and goes to KORG/hacktribe/System", async () => {
  const red = await makeFirmware();
  red.set([0x45, 0x32, 0x53], 0x10);
  red[0x2e] = 0x24;
  const blue = Uint8Array.from(red);
  blue[0x12] = 0x00;
  blue[0x2e] = 0x23;
  const page = await patcherPage();
  await drop(page, blue);
  await page.locator("#cee-patch-file-info", { hasText: "Hacktribe 2.02 für die blaue erkannt" }).waitFor();
  assert.equal(await page.locator("#cee-patch-blue-hacktribe").isVisible(), false, "the hint is for Korg's blue file");
  await page.click("#cee-patch-next");
  assert.equal(await page.locator("#cee-patch-device input[value=blue]").isChecked(), true, "the head says blue");
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-download").disabled);
  assert.deepEqual(new Uint8Array(fake.seen.check.pair.subarray(0, 0x200100)), red, "the check gets the file with the Sampler head");
  assert.equal(fake.seen.check.hardware, "blue", "and runs it on the blue's flash");
  await page.click("#cee-patch-next");
  assert.equal(await page.locator("#cee-patch-path").textContent(), "KORG/hacktribe/System/SYSTEM.VSB");
  const downloaded = await h.download(page, () => page.click("#cee-patch-download"));
  assert.deepEqual([downloaded[0x12], downloaded[0x2e]], [0x53, 0x24], "the copy has the head Hacktribe's updater on the blue takes");
  fake.seen.firmwareBody = null;
  await page.click("#cee-patch-afraid");
  await page.locator("#cee-patch-hint").waitFor();
  assert.deepEqual(new Uint8Array(fake.seen.firmwareBody), blue, "the update test runs the user's own file, blue head and all");
  assert.deepEqual(page.errors, []);
});

test("patcher: the test is a choice; no test needs the consent and goes straight to step 4, full runs the whole check", async () => {
  const page = await patcherPage();
  await drop(page, await makeFirmware());
  await page.click("#cee-patch-next");
  await page.click("#cee-patch-next");
  assert.equal(await page.locator("#cee-patch-test input:checked").getAttribute("value"), "quick", "the quick test of today is the default");
  assert.equal(await page.locator("#cee-patch-run").textContent(), "Patchen und testen");
  await page.locator("#cee-patch-test label", { hasText: "Kein Test" }).click();
  assert.equal(await page.isVisible("#cee-patch-consent-box"), true);
  assert.equal(await page.isDisabled("#cee-patch-run"), true, "no run without the consent");
  await page.check("#cee-patch-consent");
  assert.equal(await page.locator("#cee-patch-run").textContent(), "Patchen");
  const checks = fake.seen.check;
  await page.click("#cee-patch-run");
  await page.locator("#cee-patch-step-4").waitFor();
  assert.equal(fake.seen.check, checks, "nothing ran in the emulator");
  assert.match(await page.locator("#cee-patch-path").textContent(), /^KORG\/.+\/System\/SYSTEM\.VSB$/, "the place on the card, before anything is saved");
  assert.equal(await page.isVisible("#cee-patch-untested"), true, "the copy says it is untested");
  assert.equal(await page.locator("#cee-patch-download").textContent(), "Speichern");
  assert.equal(await page.isDisabled("#cee-patch-download"), false);
  await page.click("#cee-patch-back");
  assert.equal(await page.isVisible("#cee-patch-test"), true, "back from the end is the test again, ready to run once more");
  await page.locator("#cee-patch-test label", { hasText: "Voller Test" }).click();
  await page.click("#cee-patch-run");
  await page.waitForFunction(() => !document.querySelector("#cee-patch-next").disabled);
  assert.equal(fake.seen.check.quick, null, "the full test asks the emulator for every check");
  await page.click("#cee-patch-next");
  assert.equal(await page.isVisible("#cee-patch-untested"), false, "a tested copy says nothing of that");
  assert.deepEqual(page.errors, []);
});
