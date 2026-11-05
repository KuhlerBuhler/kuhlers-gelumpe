/** The sequencer and panel state a script can read, for the simulated device. The values follow the firmware's ranges. */
import { SCRIPT_KNOBS, ERROR, PATTERN_FIELDS, PART_FIELDS, PART_WRITES, PATTERN_WRITES, PATTERN_PARTS, PATTERN_STEPS } from "../../data/script/contract.mjs";
import { ScriptFault } from "./vm.mjs";
import { text, render } from "../text.mjs";
import { KEY_NAMES } from "../../data/script/names.mjs";
import { OBJECTS } from "../../data/script/objects.mjs";

const LENGTH_FIELD = PATTERN_FIELDS.findIndex(f => f.name === "length");
const KEY_TOUCHPAD = KEY_NAMES.find(n => n.name === "TOUCHPAD").value;
const KEY_PLAY = KEY_NAMES.find(n => n.name === "PLAY").value;
const KEY_STOP = KEY_NAMES.find(n => n.name === "STOP").value;
const KEY_EXIT = KEY_NAMES.find(n => n.name === "EXIT").value;
const REPAIRS = OBJECTS.find(o => o.path === "korg.system.repairs").id;

export class SimHardware {
  /** @param {(event: string, ...args: number[]) => void} [emit] where hardware events go, in the page the runtime's ring */
  constructor(emit = () => {}) {
    this.emit = emit;
    this.stepFraction = 0;
    this.transport = 0;
    this.tempo = 1200;
    this.pattern = 0;
    this.part = 0;
    this.steps = new Int32Array(16);
    this.mutes = new Uint8Array(16);
    this.knobs = new Int32Array(SCRIPT_KNOBS);
    /** CHAIN MODE in Global, and the pattern blocks korg.read.patternValue reads (-1 the pattern in RAM, 0 to 249 the bank), made on first use. */
    this.chainMode = 1;
    this.patternBlocks = new Map();
    this.backlight = [1, 1, 1];
    this.ledHold = 0;
    /**
     * What plugins keep from the firmware is the fold of the holds of all armed plugins (`holders` gives their hold records, each
     * { keys, knobs, pad }; the device sets it), so an input stays away from the firmware while ANY plugin keeps it and a plugin
     * changes only its own records. padHold: 1 while pad presses reach the plugins only; an app's close gives the pads back.
     */
    this.holders = () => [];
    this.padHold = 0;
    /** korg.knobHold: one bit per knob whose moves reach the plugins only; korg.knob: the last value a plugin gave the firmware per knob. */
    this.knobHold = 0;
    this.firmwareKnobs = new Int32Array(11);
    /** korg.passKeys: per key 1 when it reaches the firmware while an app is open. REC, STOP and PLAY do by default; an app's close resets them. */
    this.keyPass = new Uint8Array(34);
    this.resetKeyPass();
    /** korg.touchLockX: the X the firmware sees while a finger is on the touchpad, -1 the finger's own. */
    this.touchLock = -1;
    /** korg.keyHold and korg.keyMask: per key 1 when its presses reach the plugins only, also without an app. */
    this.keyHold = new Uint8Array(34);
    /** korg.pressKey: the keys plugins passed to the firmware as a short press, in order. */
    this.pressedKeys = [];
    /** Set by the device before each input: whether an app is open, so the keys an app keeps do not reach the firmware. */
    this.appOpen = false;
    /** The leaves of the object tree by id (data/script/objects.mjs), at their factory values; `repairs` is korg.system.repairs. */
    this.objects = OBJECTS.map(o => o.factory);
    /** 0 finger up, 1 the press came and the first position has not, 2 the first position is out. */
    this.touch = 0;
  }

  /** Host functions for the read API entries. */
  api() {
    return {
      "korg.read.transport": () => this.transport,
      "korg.read.tempo": () => this.tempo,
      "korg.read.pattern": () => this.pattern,
      "korg.read.part": () => this.part,
      "korg.read.step": part => this.steps[part],
      "korg.read.mute": part => this.mutes[part],
      "korg.read.knob": index => this.knobs[index],
      "korg.read.chainMode": () => this.chainMode,
      "korg.read.patternValue": (pattern, part, field) => this.patternValue(pattern, part, field),
      "korg.play": () => { if (this.transport !== 1) { this.transport = 1; this.emit("play"); } },
      "korg.stop": () => { if (this.transport !== 0) { this.transport = 0; this.steps.fill(0); this.emit("stop"); } },
      "korg.pattern": index => { this.pattern = index; this.emit("patternChange", index); },
      "korg.tempo": tenths => { this.tempo = tenths; this.emit("tempo", tenths); },
      "korg.part": part => { this.part = part; this.emit("partChange", part); },
      "korg.backlight": (red, green, blue) => { this.backlight = [red, green, blue]; },
      "korg.ledHold": on => { this.ledHold = on; },
      // the four hold calls get the calling plugin's hold record first (ScriptRuntime passes it)
      "korg.padHold": (holds, on) => { holds.pad = on; this.syncHolds(holds); },
      "korg.knobHold": (holds, index, on) => { holds.knobs = on ? holds.knobs | 1 << index : holds.knobs & ~(1 << index); this.syncHolds(holds); },
      "korg.knob": (index, value) => { this.firmwareKnobs[index] = value; },
      "korg.passKeys": (key, on) => { this.keyPass[key] = on; },
      "korg.seq.setPartValue": (part, field, value) => this.setPartValue(part, field, value),
      "korg.touchLockX": x => { this.touchLock = x; },
      "korg.keyHold": (holds, key, on) => { this.keyExit("korg.keyHold", key); holds.keys[key] = on; this.syncHolds(holds); },
      "korg.keyMask": (holds, low, high) => {
        if ((low >>> KEY_EXIT) & 1) this.keyExit("korg.keyMask", KEY_EXIT);
        for (let key = 0; key < 34; key++) holds.keys[key] = key < 32 ? (low >>> key) & 1 : (high >>> (key - 32)) & 1;
        this.syncHolds(holds);
      },
      "korg.pressKey": key => { this.keyExit("korg.pressKey", key); this.pressedKeys.push(key); this.firmwareKey(key); },
      "korg.seq.setPatternValue": (field, value) => this.setPatternValue(field, value),
      "korg.read.patternBytes": (slots, pattern, offset) => this.patternBytes(slots, pattern, offset),
      "korg.seq.writeSteps": (slots, part, first) => this.writeSteps(slots, part, first),
      "korg.mute": (part, muted) => { if (this.mutes[part] !== muted) { this.mutes[part] = muted; this.emit("mute", part, muted); } },
      "korg.seq.setStep": (part, step, note, velocity) => this.setStep(part, step, note, velocity),
      "korg.seq.setGate": (part, step, gate) => { this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.gate] = gate; },
      "korg.get": leaf => this.objectGet(leaf),
      "korg.set": (leaf, index, value) => this.objectSet(leaf, value),
      "korg.seq.clearPart": part => { for (let step = 0; step < PATTERN_STEPS.count; step++) this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.on] = 0; },
    };
  }

  /** korg.get: the value of a leaf, as the runtime's table reads it. */
  objectGet(leaf) {
    if (!OBJECTS[leaf]) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectLeaf", { leaf })));
    return this.objects[leaf];
  }

  /** korg.set: clamped to the leaf's range, one more repair when it was outside, as script_objects.s does. */
  objectSet(leaf, value) {
    const o = OBJECTS[leaf];
    if (!o) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectLeaf", { leaf })));
    if (!o.write) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectReadOnly", { path: o.path })));
    const clamped = Math.min(o.max, Math.max(o.min, value));
    if (clamped !== value) this.objects[REPAIRS] += 1;
    this.objects[leaf] = clamped;
  }

  /** Folds the holds of the armed plugins, and of `running` (a plugin whose body runs before it is armed), into what the input filter reads. */
  syncHolds(running = null) {
    const all = [...this.holders()];
    if (running && !all.includes(running)) all.push(running);
    this.keyHold.fill(0);
    this.padHold = 0;
    this.knobHold = 0;
    for (const h of all) {
      for (let key = 0; key < 34; key++) if (h.keys[key]) this.keyHold[key] = 1;
      if (h.pad) this.padHold = 1;
      this.knobHold |= h.knobs;
    }
  }

  /** The keys that reach the firmware while an app is open, as at power-on and after an app's close: REC, STOP and PLAY. */
  resetKeyPass() { this.keyPass.fill(0); this.keyPass.fill(1, 0, 3); }

  /** korg.passKeys as the input filter reads it: 1 when the key reaches the firmware while an app is open. */
  keyPasses(key) { return this.keyPass[key]; }

  /** korg.seq.setPartValue in the pattern in RAM: the value clamped to the field's range, a signed one as its byte. */
  setPartValue(part, field, value) {
    const f = PART_FIELDS[field];
    const w = f && PART_WRITES[f.name];
    if (!w) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectReadOnly", { path: `korg.parts[${part}].${f?.name ?? field}` })));
    this.patternBlock(-1)[PATTERN_PARTS.base + part * PATTERN_PARTS.stride + f.offset] = Math.min(w[3], Math.max(w[2], value)) & 255;
  }

  /** EXIT stays with the firmware: korg.keyHold and korg.pressKey refuse it, as the ARM runtime does. */
  keyExit(name, key) {
    if (key === KEY_EXIT) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.keyExit", { name })));
  }

  /** A key press the firmware gets: PLAY and STOP move the simulated transport. */
  firmwareKey(key) {
    if (key === KEY_PLAY) this.api()["korg.play"]();
    if (key === KEY_STOP) this.api()["korg.stop"]();
  }

  /**
   * korg.seq.setPatternValue in the pattern in RAM: the value clamped to the field's range and stored as korg.read.patternValue
   * decodes it. The device calls the Pattern menu's setter (tools/patch/script_hooks.py PATTERN_SETTERS), which stores the
   * same byte; its MFX TYPE ends at 31 on the synth, which the simulator does not know.
   */
  setPatternValue(field, value) {
    const f = PATTERN_FIELDS[field];
    const w = f && PATTERN_WRITES[f.name];
    if (!w) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectReadOnly", { path: `korg.current.${f?.name ?? field}` })));
    const v = Math.min(w[1], Math.max(w[0], value));
    const block = this.patternBlock(-1);
    if (f.kind === "u16") { block[f.offset] = v & 255; block[f.offset + 1] = v >> 8 & 255; return; }
    block[f.offset] = (f.kind === "bars" ? v - 1 : f.kind === "chain" ? v + 1 : v) & 255;
  }

  /** korg.read.patternBytes: one byte of the block per slot from `offset`, as far as the block goes; returns how many. */
  patternBytes(slots, pattern, offset) {
    const block = this.patternBlocks.get(pattern) ?? new Uint8Array(PATTERN_PARTS.bytes);
    const count = Math.min(slots.length, PATTERN_PARTS.bytes - offset);
    for (let i = 0; i < count; i++) slots[i] = block[offset + i];
    return count;
  }

  /**
   * korg.seq.writeSteps: whole step records of 12 slots each into part `part` of the pattern in RAM from step `first`, as far
   * as the slots and the 64 steps go; returns how many. Each value is clamped to its range (on and trigger 0 to 1, gate 0 to
   * 127, velocity 1 to 127, the note places 0 to 128); slots 8 to 11 of a record are not written.
   */
  writeSteps(slots, part, first) {
    const block = this.patternBlock(-1);
    const count = Math.min(Math.floor(slots.length / PATTERN_STEPS.stride), PATTERN_STEPS.count - first);
    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
    for (let i = 0; i < count; i++) {
      const at = this.stepAt(part, first + i);
      const r = slots.subarray(i * PATTERN_STEPS.stride, (i + 1) * PATTERN_STEPS.stride);
      block[at + PATTERN_STEPS.on] = clamp(r[0], 0, 1);
      block[at + PATTERN_STEPS.gate] = clamp(r[1], 0, 127);
      block[at + PATTERN_STEPS.velocity] = clamp(r[2], 1, 127);
      block[at + PATTERN_STEPS.trigger] = clamp(r[3], 0, 1);
      for (let n = 0; n < 4; n++) block[at + PATTERN_STEPS.notes + n] = clamp(r[4 + n], 0, 128);
    }
    return count;
  }

  /** Where a step's record starts in the pattern block. */
  stepAt(part, step) { return PATTERN_PARTS.base + part * PATTERN_PARTS.stride + PATTERN_STEPS.base + step * PATTERN_STEPS.stride; }

  /** korg.seq.setStep in the pattern in RAM, byte for byte what the ARM runtime writes: a note turns the step on, -1 or velocity 0 off. */
  setStep(part, step, note, velocity) {
    const block = this.patternBlock(-1);
    const at = this.stepAt(part, step);
    if (note < 0 || velocity < 1) { block[at + PATTERN_STEPS.on] = 0; return; }
    block[at + PATTERN_STEPS.velocity] = velocity;
    block.fill(0, at + PATTERN_STEPS.notes, at + PATTERN_STEPS.notes + 4);
    block[at + PATTERN_STEPS.notes] = note + 1;
    block[at + PATTERN_STEPS.trigger] = 1;
    block[at + PATTERN_STEPS.on] = 1;
  }

  /** A step of the pattern in RAM as korg.seq writes it: on, gate, velocity, trigger and the note (-1 for none) of its first place. */
  stepValue(part, step) {
    const block = this.patternBlock(-1);
    const at = this.stepAt(part, step);
    return { on: block[at + PATTERN_STEPS.on], gate: block[at + PATTERN_STEPS.gate], velocity: block[at + PATTERN_STEPS.velocity],
      trigger: block[at + PATTERN_STEPS.trigger], note: block[at + PATTERN_STEPS.notes] - 1 };
  }

  /** A named value of a pattern (PATTERN_FIELDS with part -1, PART_FIELDS with part 0 to 15), decoded as the ARM runtime does. */
  patternValue(pattern, part, field) {
    const f = (part < 0 ? PATTERN_FIELDS : PART_FIELDS)[field];
    if (!f) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.patternValue", { field })));
    const block = this.patternBlocks.get(pattern) ?? new Uint8Array(PATTERN_PARTS.bytes);
    const at = f.offset + (part < 0 ? 0 : PATTERN_PARTS.base + part * PATTERN_PARTS.stride);
    const raw = block[at];
    switch (f.kind) {
      case "s8": return (raw << 24) >> 24;
      case "u16": return raw | (block[at + 1] << 8);
      case "bars": return (raw & 3) + 1;
      case "chain": return raw >= 1 && raw <= 250 ? raw - 1 : -1;
      case "atLeast1": return Math.max(raw, 1);
      default: return raw;
    }
  }

  /** The block of a pattern (-1 the pattern in RAM), to fill in: korg.read.patternValue reads it. */
  patternBlock(pattern) {
    if (!this.patternBlocks.has(pattern)) this.patternBlocks.set(pattern, new Uint8Array(PATTERN_PARTS.bytes));
    return this.patternBlocks.get(pattern);
  }

  /** Steps until the counter wraps: the length of the pattern in RAM once a test gave it one, else 64. */
  stepCount() { return this.patternBlocks.has(-1) ? this.patternValue(-1, -1, LENGTH_FIELD) * 16 : 64; }

  /** The sequencer moves on by one frame: while playing, steps (16ths) and beats follow the tempo. */
  tick(frameMs) {
    if (this.transport !== 1) return;
    this.stepFraction += (this.tempo * 4 / 600) * (frameMs / 1000);
    while (this.stepFraction >= 1) {
      this.stepFraction -= 1;
      this.steps.fill((this.steps[0] + 1) % this.stepCount());
      this.emit("step", this.steps[0]);
      if (this.steps[0] % 4 === 0) this.emit("beat");
    }
  }

  /**
   * An input as the input filter sees it: the last value per knob stays readable, and a touch position gets its third value
   * `first`, 1 for the first position after the press (or after nothing, when a position comes without a press) and 0 for
   * the ones that follow. Returns the values the event carries.
   */
  input(event, ...args) {
    if (event === "knob" && args[0] >= 0 && args[0] < SCRIPT_KNOBS) this.knobs[args[0]] = args[1] | 0;
    // PLAY and STOP reach the firmware even while an app is open unless it keeps them (korg.passKeys), and the app sees the key as well
    // korg.keyHold keeps a key from the firmware with or without an app
    const firmware = !this.keyHold[args[0]] && (!this.appOpen || this.keyPass[args[0]]);
    if (event === "buttonPress" && firmware) this.firmwareKey(args[0]);
    if (event === "buttonPress" && args[0] === KEY_TOUCHPAD) this.touch = 1;
    if (event === "buttonRelease" && args[0] === KEY_TOUCHPAD) this.touch = 0;
    if (event === "touch") {
      const first = this.touch === 2 ? 0 : 1;
      this.touch = 2;
      return [args[0], args[1], first];
    }
    return args;
  }
}
