/** The sequencer and panel state a script can read, for the simulated device. The values follow the firmware's ranges. */
import { SCRIPT_KNOBS, ERROR, PATTERN_FIELDS, PART_FIELDS, PATTERN_PARTS, PATTERN_STEPS } from "../../data/script/contract.mjs";
import { ScriptFault } from "./vm.mjs";
import { text, render } from "../text.mjs";
import { KEY_NAMES } from "../../data/script/names.mjs";
import { OBJECTS } from "../../data/script/objects.mjs";

const LENGTH_FIELD = PATTERN_FIELDS.findIndex(f => f.name === "length");
const KEY_TOUCHPAD = KEY_NAMES.find(n => n.name === "TOUCHPAD").value;
const KEY_PLAY = KEY_NAMES.find(n => n.name === "PLAY").value;
const KEY_STOP = KEY_NAMES.find(n => n.name === "STOP").value;
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
    // PLAY and STOP reach the firmware even while an app is open, and the app sees the key as well
    if (event === "buttonPress" && args[0] === KEY_PLAY) this.api()["korg.play"]();
    if (event === "buttonPress" && args[0] === KEY_STOP) this.api()["korg.stop"]();
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
