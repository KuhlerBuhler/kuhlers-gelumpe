import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";
import { ERROR } from "../data/script/contract.mjs";
import { asmInclude } from "../src/script/arm-tables.mjs";
import { parseReadRam, parseBlechRead, parseSearch, readRam, blechRead, search } from "../src/protocol.mjs";
import { buildOf } from "../src/firmware.mjs";
import { runtimePrograms } from "./fixtures/script-runtime-programs.mjs";
import { applyPatches, PATCH_FORMAT } from "../src/patch.mjs";
import { checkHooks } from "../src/hooks.mjs";
import { packAll } from "../src/script/archive.mjs";
import { SimDevice } from "../src/script/sim.mjs";
import { buildRuntimePatch } from "../tools/patch/script_runtime.mjs";
import { slots } from "./support/spawn.mjs";
import { nativeTest } from "./support/native.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const venv = fileURLToPath(new URL(process.platform === "win32" ? "../tools/emu/.venv/Scripts/python.exe" : "../tools/emu/.venv/bin/python", import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : "python3");
const probe = spawnSync(python, ["-c", "import unicorn"], { encoding: "utf8" });
const available = !probe.error && probe.status === 0;
const nativeRequired = process.env.E2_ARM_REQUIRED === "1";
const firmwareRequired = process.env.E2_EMU_REQUIRED === "1" || process.env.E2_LOCAL_REQUIRED === "1";

test("the native runtime patch declares its actual hooks and composes with splash and MFX", {
  skip: probe.error && !nativeRequired ? "Python not available" : false,
}, async () => {
  const code = "import json,sys; from tools.patch.script_hooks import build; print(json.dumps(build(sys.stdin.read()).patch_manifest()))";
  const result = spawnSync(python, ["-c", code], { cwd: root, input: asmInclude(), encoding: "utf8", timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const runtime = JSON.parse(result.stdout);
  assert.equal(runtime.format, PATCH_FORMAT);
  assert.equal(runtime.version, 1);
  assert.equal(runtime.id, "script-runtime");
  assert.deepEqual(runtime.hooks.map(hook => hook.site), [
    "0xC002837C", "0xC00836FC", "0xC0038D68", "0xC004C1B4",
    "0xC006E8D8", "0xC006F094", "0xC008A83C", "0xC008A8A8", "0xC0064430", "0xC0067754", "0xC0067720", "0xC0065B8C", "0xC0064C20", "0xC0064C28", "0xC00623C0", "0xC0062448", "0xC0088284", "0xC0016C98", "0xC0016CE0", "0xC0016D28", "0xC00289F4", "0xC00161A4", "0xC006E664", "0xC006E68C", "0xC0038D34", "0xC00289D8",
  ]);
  // two code sections (the VM, then all our code behind it, from MORE3_START) and the block of Blechy, twenty-four branches, two words, and the menu's table (copy plus its extra entry) and class table (copy)
  assert.equal(runtime.changes.length, 32);
  const copies = runtime.changes.filter(change => change.copy !== undefined);
  assert.equal(copies.length, 2, "the menu copies the firmware's screen table and class table when applied, nothing of them is in the patch");
  for (const change of runtime.changes) assert.match(change.expect, /^[a-f0-9]{64}$/);
  const load = name => JSON.parse(readFileSync(new URL(`../data/patches/${name}.json`, import.meta.url), "utf8"));
  const patches = [load("splash-editor"), load("mfx-switch"), runtime];
  const registered = checkHooks(patches);
  assert.equal(registered.ok, true, registered.reasons.join(" "));
  // the splash editor's class of GLOBAL PARAMETERS keeps EDIT while its editor is open; only what it passes on reaches PLUGIN RUNTIME's edges
  assert.equal(registered.dependencies.length, 3);
  assert.equal(registered.dependencies.filter(text => /mfx-switch.*script-runtime.*0xC002837C/.test(text)).length, 1);
  assert.equal(registered.dependencies.filter(text => /script-runtime.*0xC0064C2[08].*splash-editor.*0xC0064D3C/.test(text)).length, 2);
  if (process.env.E2_VSB) {
    const applied = await applyPatches(new Uint8Array(readFileSync(process.env.E2_VSB)), patches);
    assert.equal(applied.ok, true, applied.reasons.join(" "));
  }
});

test("the Synth runtime uses its own startup and preserves the native instruction on every bypass", () => {
  const patch = JSON.parse(buildRuntimePatch("synth"));
  assert.deepEqual(patch.builds, ["synth"]);
  assert.ok(patch.hooks.some(hook => hook.site === "0xC0028170"));
  assert.ok(patch.hooks.some(hook => hook.site === "0xC0025E48"));
  assert.ok(!patch.hooks.some(hook => ["0xC0038D34", "0xC0038D68", "0xC00289D8"].includes(hook.site)));
  const registered = checkHooks([patch]);
  assert.equal(registered.ok, true, registered.reasons.join(" "));
  const result = spawnSync(python, ["-m", "unittest", "tools.patch.test_script_synth"], {
    cwd: root, encoding: "utf8", timeout: 60_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

// One Python process each, side by side; the input and frame hooks and the card loader, the two longest, have a file of their own.
describe("native runtime modules", { concurrency: slots }, () => {
  nativeTest("native LED glue stages commands and tries panel transport without waiting", ["test_script_led"]);
  nativeTest("native display calls match the browser model pixel for pixel, and a fault leaves its message on the display", ["test_script_display", "test_display_calibrate"]);
  nativeTest("native store glue, store file read and write match the browser's file builder", ["test_script_store"]);
  nativeTest("native korg.file.frame reads a frame of a picture file exactly as the browser does", ["test_script_file"]);
  nativeTest("native clock and read-only hardware views match the firmware's state words and the timer's period", ["test_script_hw"]);
  nativeTest("native sequencer events from state comparison and the save hook", ["test_script_events"]);
});

test("fault-status: native script hooks in firmware leave control usable and expose status over DIN", {
  skip: !firmwareRequired ? "firmware emulation requires test:emu" : false,
}, () => {
  const vsb = process.env.E2_VSB;
  assert.ok(vsb && existsSync(vsb), "E2_VSB must name the local firmware");
  assert.ok(available, "firmware emulation requires Unicorn");
  const runtime = 0xC01AE000;
  const pool = 0xC01D7000;
  const blech = buildOf(new Uint8Array(readFileSync(vsb))) !== "hacktribe";
  const model = buildOf(new Uint8Array(readFileSync(vsb))) === "synth" ? 0x23 : 0x24;
  const read = blech ? (channel, addr, length) => blechRead(channel, addr, length, model) : readRam;
  const reads = [
    { name: "overflow", message: read(0, runtime + 20, 4), value: 1 },
    { name: "armed", message: read(0, runtime + 96, 4), value: 0 },
    { name: "fault", message: read(0, pool + 16, 4), value: ERROR.DIV_ZERO },
  ];
  const flash = (process.env.E2_FLASH || "").split(delimiter).filter(Boolean);
  const programs = runtimePrograms();
  const packed = packAll(["healthy", "led"].map(name => Uint8Array.from(Buffer.from(programs[name].blob, "hex"))));
  assert.ok(packed.ok);
  const block = name => Uint8Array.from(Buffer.from(programs[name].blob, "hex"));
  const shown = device => Buffer.from(device.shown).toString("hex");
  // What the browser model shows for the apps and plugins script_cases.py opens through the menu: the app is opened, then a frame runs.
  const opened = (name, setup = () => {}, options) => {
    const device = new SimDevice(options);
    device.load(block(name));
    device.frame();
    device.openApp(0);
    device.frame();
    setup(device);
    return device;
  };
  const klicker = opened("klicker");
  const klickerReady = shown(klicker);
  klicker.post("buttonPress", 3);
  klicker.frame();
  const klickerOne = shown(klicker);
  klicker.post("buttonPress", 13);
  klicker.post("buttonPress", 3);
  klicker.frame();
  klicker.openApp(0);
  klicker.frame();
  const klickerTwo = shown(klicker);
  const kept = opened("klickerstore", () => {}, { storage: { load: name => (name === "klickerstore" ? { mask: 1, values: [3] } : null), save: () => {} } });
  const appFault = shown(opened("appfault"));
  const taker = new SimDevice();
  taker.load(block("taker"));
  taker.frame();
  taker.post("buttonPress", 3);
  taker.frame();
  const snake = new SimDevice();
  snake.load(block("snake"));
  snake.openApp(0);
  const SNAKE_INPUTS = [[20, 15], [60, 11], [100, 15], [130, 11]];
  while (snake.frames < 150) {
    for (const [at, key] of SNAKE_INPUTS) if (snake.frames === at) { snake.post("buttonPress", key); snake.post("buttonRelease", key); }
    snake.frame();
  }
  const bitmaps = new SimDevice();
  bitmaps.load(block("bitmaps"));
  bitmaps.frame();
  bitmaps.post("buttonPress", 3);
  bitmaps.frame();
  // The steps the browser model writes for seqwrite, after ready and after TAP: script_cases.py holds the pattern in RAM against them.
  const seqModel = new SimDevice();
  seqModel.load(block("seqwrite"));
  seqModel.frame();
  const seqSteps = () => Array.from({ length: 64 }, (_, step) => Object.values(seqModel.hardware.stepValue(0, step)));
  const seqReady = seqSteps();
  seqModel.post("buttonPress", 3);
  seqModel.frame();
  const seq = { ready: seqReady, tap: seqSteps() };
  const displays = { snake150: shown(snake), klickerReady, klickerOne, klickerTwo, klickerThree: shown(kept), appFault, taken: shown(taker), bitmaps: shown(bitmaps) };
  const result = spawnSync(python, ["tools/emu/script_cases.py", "--base", vsb, ...flash.length ? ["--flash", ...flash] : []], {
    cwd: root, input: JSON.stringify({ include: asmInclude(), programs, errors: ERROR, search: search(), reads, displays, seq, archive: Buffer.from(packed.bytes).toString("hex") }),
    encoding: "utf8", timeout: 1_200_000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.checks.filter(check => !check.ok), []);
  for (const id of ["boot-unscharf", "boot-nur-blechy", "exit-haken", "panel-argumente", "touch-lage-aus-der-panel-nachricht", "rahmen-25hz", "fault-isoliert", "fault-folgeskript", "fault-firmware-bedienbar", "fault-rahmenbudget", "fault-budget-fortsetzung", "ring-ueberlauf-status"]) {
    assert.ok(report.checks.some(check => check.id === id && check.ok), id);
  }
  for (const id of ["karte-leer-status", "karte-leer-nur-blechy-scharf", "karte-leer-wie-original", "karte-geladen-status", "karte-geladen-scharf",
    "karte-lader-dauer", "karte-start-lauf", "karte-ready-led", "karte-taste-255", "karte-taste-0", "karte-firmware-bedienbar", "karte-block-defekt",
    "karte-datei-pruefsumme", "karte-datei-kennung", "karte-datei-abgeschnitten", "karte-exit",
    "app-laden-laesst-das-display-in-ruhe", "app-ohne-oeffnen-zeichnet-nichts", "app-gruppen-im-menue", "app-oeffnet-aus-dem-menue", "app-zaehlt-und-zeigt",
    "app-tasten-gehoeren-der-offenen-app", "app-exit-zurueck-auf-den-hauptbildschirm", "app-zaehlt-auch-geschlossen", "app-oeffnet-wieder-mit-dem-stand",
    "snake-aus-dem-menue-in-der-firmware", "snake-part-tasten-aendern-die-part-nicht", "app-offen-play-stop-erreichen-die-firmware", "app-offen-sieht-play-stop-auch", "app-offen-andere-tasten-bleiben-bei-der-app", "part-tasten-nach-exit-wieder-der-firmware", "snake-exit", "snake-faengt-bei-open-neu-an", "app-fehler-auf-dem-eigenen-bildschirm", "fehler-ohne-app-zeichnet-nichts", "fehler-seite-im-menue",
    "exit-oeffnet-die-falle-nicht-zu", "exit-schliesst-trotz-fallen-app", "take-zeigt-das-bild", "exit-beendet-take", "laden-allein-zeichnet-nie", "bitmap-und-text-mit-zahl-wie-im-browser",
    "seq-schreibt-wie-der-browser", "seq-tap-wie-der-browser", "seq-pads-zeigen-die-steps", "seq-spielt-was-geschrieben-ist", "seq-schreibt-waehrend-es-laeuft", "seq-ungespeichert",
    "hw-lesen-ruhezustand", "hw-lesen-play", "hw-lesen-regler", "hw-uhr", "hw-handeln-tempo", "hw-handeln-pattern", "hw-handeln-part", "hw-handeln-mute", "hw-handeln-play-stop", "ereignis-play-schritte", "ereignis-stop", "ereignis-tempo-pattern-part-mute", "ereignis-save-haken-eingehaengt", "hw-backlight", "hw-led-halten-flag", "hw-led-halten-sperrt-firmware-leds", "hw-led-halten-loesen", "speicher-ohne-save-keine-datei", "speicher-schreibt-datei", "speicher-pause-zwischen-schreibvorgaengen", "speicher-neustart-zaehler", "speicher-defekte-datei-faellt-zurueck", "menu-skripte-gezaehlt", "menu-skriptseiten", "menu-eingaben-erreichen-skripte-nicht", "menu-skripte-laufen-wieder", "menu-skript-aus", "menu-skript-wieder-an", "menu-fehlerskript-bleibt-aus", "menu-export-seite", "menu-export-gleich-dem-browser-bauer", "menu-export-wird-wieder-geladen", "menu-plugin-bleibt-aus-nach-neustart", "menu-plugin-an-mit-write-gespeichert", "menu-plugin-aus-liste-behaelt-die-anderen", "menu-plugin-aus-bei-voller-liste", "plugin-verwalten-oeffnet-und-exit", "plugin-entfernen", "letztes-plugin-entfernen",
    "menu-einstellungen-v2-wird-v3", "menu-40-plugins-aus-nach-neustart", "menu-einstellungen-v1-gelesen",
    "fremd-wartet", "fremd-fragt", "fremd-erlaubt", "fremd-bekommt-ready-nach-ja", "fremd-lauft-nach-ja-ereignisse", "fremd-fragt-nicht-wieder", "fremd-liste-voll-schiebt",
    "liste-aus-den-dateien", "liste-versteckte-dateien-fehlen", "menu-liste-ohne-about", "menu-blechy-keine-plugin-seite", "liste-vor-dem-laden-nichts", "beschreibung-seite", "beschreibung-scrollt", "beschreibung-enter-tut-nichts", "dial-oben-laedt-und-startet", "laden-speicherbild-bleibt", "stand-aus-und-an", "fremd-wartet-nach-dem-laden", "fremd-erlaubt-in-der-liste", "abgelehnt", "beschreibung-verlassen-zeichnet-neu", "liste-geladene-zuerst-nichts-doppelt", "laden-verlassen", "geladenes-laeuft", "liste-plugin-ohne-datei", "entferntes-plugin-laedt-wieder", "liste-ohne-dateien", "laden-bei-ausgeschalteten-skripten",
    "menu-add-seiten-angelegt", "menu-add-seitentexte", "menu-add-werte-und-grenzen", "menu-add-ereignisse-erreichen-das-skript", "menu-add-keine-doppelten-seiten", "menu-add-zwoelf-seiten", "menu-add-bereich-verkehrt"]) {
    assert.ok(report.checks.some(check => check.id === id && check.ok), id);
  }
  for (const id of ["led-ready-nullwert", "led-tap-255", "led-tap-0", "led-88-pakete", "led-rahmen-fortgesetzt"]) {
    assert.ok(report.checks.some(check => check.id === id && check.ok), id);
  }
  assert.equal(report.layout.runtime, runtime);
  assert.equal(report.layout.pool, pool);
  const found = parseSearch(Buffer.from(report.search, "hex"));
  for (const read of reads) {
    const reply = report.reads.find(item => item.name === read.name);
    assert.equal(reply.messages.length, 1);
    const bytes = blech ? parseBlechRead(Buffer.from(reply.messages[0], "hex"), found.channel, 4, found.model)
      : parseReadRam(Buffer.from(reply.messages[0], "hex"), found.channel, 4);
    assert.equal(new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0, true), read.value);
  }
});
