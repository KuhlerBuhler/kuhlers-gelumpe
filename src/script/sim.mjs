/**
 * A simulated Electribe for the scripts page: the reference VM behind a display
 * model, the LED ledger and a clock, one frame per call. It shows what a block
 * does, not what the firmware's drawing or timing do.
 */
import { QUEUED_EVENTS, EVENT_BY_NAME, SCRIPT_LED, SCRIPT_GIF, ERROR } from "../../data/script/contract.mjs";
import { ScriptRuntime } from "./runtime.mjs";
import { ScriptLeds } from "./led.mjs";
import { Display, drawFault } from "./display.mjs";
import { Coverage } from "./coverage.mjs";
import { SimHardware } from "./hardware.mjs";
import { KEY_NAMES } from "../../data/script/names.mjs";
import { ScriptFault } from "./vm.mjs";
import { gifPath, readGifFrame } from "./gif.mjs";

export const FRAME_MS = 40;
const KEY_EXIT = KEY_NAMES.find(n => n.name === "EXIT").value;

export class SimDevice {
  /** @param {{ now?: () => number, storage?: object, card?: Map<string, Uint8Array> }} [o] a clock in milliseconds (the default advances one frame per frame()), persistent values as ScriptRuntime takes them, and files on the card by path (gifPath) */
  constructor({ now, storage = null, card = new Map() } = {}) {
    this.card = card;
    this.clock = 0;
    this.now = now ?? (() => this.clock);
    this.display = new Display();
    this.blank = new Uint8Array(this.display.bytes.length);
    this.leds = new Uint8Array(SCRIPT_LED.count);
    this.ledModel = new ScriptLeds();
    this.runtime = null;
    this.hardware = new SimHardware((event, ...args) => this.runtime?.post(event, ...args));
    this.frames = 0;
    this.recording = null;
    this.coverage = [];
    // Real time says nothing about the device, and a loaded browser would fault a healthy script, so only the fuel limit applies.
    this.runtime = new ScriptRuntime({
      now: () => performance.now(),
      storage,
      frameMs: Infinity,
      handlerWarnMs: Infinity,
      api: {
        "korg.led": (index, level) => this.ledModel.request(index, level),
        "korg.millis": () => Math.floor(this.now()),
        "korg.display.clear": () => this.display.clear(),
        "korg.display.text": (text, x, y) => this.display.text(text, x, y),
        "korg.display.number": (value, x, y) => this.display.number(value, x, y),
        "korg.display.pixel": (x, y, on) => this.display.pixel(x, y, on),
        "korg.display.rect": (x, y, w, h) => this.display.rect(x, y, w, h),
        "korg.display.clearRect": (x, y, w, h) => this.display.clearRect(x, y, w, h),
        "korg.display.bitmap": (slots, x, y, width) => this.display.bitmap(slots, x, y, width),
        "korg.display.textNumber": (text, value, x, y) => this.display.textNumber(text, value, x, y),
        "korg.file.frame": (slots, file, index) => {
          if (slots.length < SCRIPT_GIF.frameBytes) throw new ScriptFault(ERROR.API_ARG, `korg.file.frame: das Feld hat ${slots.length} Plätze, ein Bild braucht ${SCRIPT_GIF.frameBytes}`);
          return readGifFrame(this.card.get(gifPath(file)), index, slots);
        },
        ...this.hardware.api(),
      },
    });
    this.runtime.onOwn = () => this.display.clear();
  }

  /** Load a block and run its body; the body runs inside add(), before the script object exists, so its steps are held back for the coverage. */
  load(blob) {
    let coverage = null;
    const early = new Set();
    const result = this.runtime.add(blob, { onStep: offset => (coverage ? coverage.step(offset) : early.add(offset)) });
    if (result.error && result.script) this.#showFault({ script: result.script.name, ...result.error });
    if (result.script) {
      coverage = new Coverage(result.script);
      for (const offset of early) coverage.step(offset);
      this.coverage.push(coverage);
    }
    return result;
  }

  /** The fault picture goes on the display only for the app that owns it; for any other script the BLECH menu shows the fault. */
  #showFault(fault) {
    if (this.runtime.open?.script.name === fault.script) drawFault(this.display, fault.script, fault.line ?? 0, fault.name);
  }

  /** The apps scripts declared, in the order of the BLECH menu (GAMES, then TOOLS): id, name, group, script, state, open. */
  get apps() { return this.runtime.appList; }

  /** What the device's display shows: the picture of the open app, nothing of a plugin otherwise (the device shows its own screen). */
  get shown() { return this.runtime.open ? this.display.bytes : this.blank; }

  /** The user opens an app from the BLECH menu: the display is cleared for it, it gets `open`. */
  openApp(id) {
    const app = this.runtime.apps[id];
    if (!app || app.entry.script.state !== "armed") return false;
    return this.runtime.openApp(id);
  }

  /** EXIT, or any way back to the device's own screen. */
  closeApp() { return this.runtime.closeApp(); }

  /** One input as the panel sends it. EXIT with an app open closes it, in the input filter, before any script sees the key. */
  #deliver(event, args) {
    if (event === "buttonPress" || event === "buttonRelease") args = [this.runtime.remapped(args[0]), ...args.slice(1)];
    if (event === "buttonPress" && args[0] === KEY_EXIT && this.runtime.open) { this.runtime.closeApp(); return true; }
    return this.runtime.post(event, ...this.hardware.input(event, ...args));
  }

  /** The pages scripts added to the device's menu: label, range and the value shown. */
  get menus() { return this.runtime.menus.map((m, id) => ({ id, script: m.script, label: m.label, min: m.min, max: m.max, value: m.value })); }

  /** The user turns a menu page: the script gets `menu`(id, value) on its next frame. */
  menuSet(id, value) { return this.runtime.menuSet(id, value); }

  /** Queue an input as the panel would send it. */
  post(event, ...args) {
    if (!QUEUED_EVENTS.includes(event)) throw new Error(`${event} is not an input event`);
    this.recording?.push({ frame: this.frames, event, args });
    return this.#deliver(event, args);
  }

  /** One frame: ready on the first, queued inputs, frame handlers, then the LED packets the transport takes. */
  frame() {
    this.ledModel.beginFrame();
    this.hardware.tick(FRAME_MS);
    const result = this.runtime.frame();
    for (const fault of result.faults) this.#showFault(fault);
    this.ledModel.flushFrame({
      queueFree: () => 1024,
      send: (index, level) => { this.leds[index] = level; return true; },
    });
    this.runtime.flushStore();
    this.frames += 1;
    this.clock += FRAME_MS;
    return result;
  }

  /** Run `count` frames; `inputs` are recorded events whose frame number is reached on the way. */
  run(count, inputs = []) {
    const pending = inputs.slice().sort((a, b) => a.frame - b.frame);
    const faults = [];
    for (let i = 0; i < count; i++) {
      while (pending.length && pending[0].frame <= this.frames) {
        const { event, args } = pending.shift();
        this.#deliver(event, args);
      }
      faults.push(...this.frame().faults);
    }
    return faults;
  }

  startRecording() { this.recording = []; }

  stopRecording() {
    const taken = this.recording ?? [];
    this.recording = null;
    return taken;
  }

  /** Source lines with code, covered and missing across this device's scripts, for the script at `index`. */
  lines(index = 0) { return this.coverage[index]?.lines() ?? { all: [], covered: [], missing: [] }; }

  status() { return this.runtime.status(); }
}

/** Input events with their argument names, for building controls and for validating a recorded sequence. */
export function inputEvents() {
  return QUEUED_EVENTS.map(name => ({ name, args: EVENT_BY_NAME.get(name).args }));
}

/**
 * The probe the export gate reads: a fresh device, the block loaded, the
 * recorded inputs played at their frames, run long enough to cover them.
 * @returns {{ ok: boolean, loadError: object | null, faults: object[], lines: { all: number[], covered: number[], missing: number[] }, frames: number, warnings: number }}
 */
export function probe(blob, inputs = [], { minFrames = 100, tail = 50 } = {}) {
  const device = new SimDevice();
  const loaded = device.load(blob);
  if (loaded.ok && device.apps.length) device.openApp(device.apps[0].id);
  if (!loaded.script) return { ok: false, loadError: loaded.error, faults: [], lines: { all: [], covered: [], missing: [] }, frames: 0, warnings: 0 };
  const last = inputs.reduce((n, input) => Math.max(n, input.frame), 0);
  const frames = Math.max(minFrames, last + tail);
  const faults = device.run(frames, inputs);
  if (loaded.error) faults.unshift({ script: loaded.script.name, ...loaded.error });
  const status = device.status().scripts[0];
  return { ok: faults.length === 0 && status.state === "armed", loadError: null, faults, lines: device.lines(0), frames, warnings: status.slowHandlers };
}
