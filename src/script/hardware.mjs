/** The sequencer and panel state a script can read, for the simulated device. The values follow the firmware's ranges. */
import { SCRIPT_KNOBS, ERROR, PATTERN_FIELDS, PART_FIELDS, PART_WRITES, PATTERN_WRITES, PATTERN_PARTS, PATTERN_STEPS, PATTERN_MOTION, SAMPLE_INFO } from "../../data/script/contract.mjs";
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
    /** The pattern the display shows (-1: the playing one) and the confirmed next pattern (-1: none), as the pattern switch sets them. */
    this.viewed = -1;
    this.next = -1;
    this.part = 0;
    this.steps = new Int32Array(16);
    this.mutes = new Uint8Array(16);
    this.knobs = new Int32Array(SCRIPT_KNOBS);
    /** CHAIN MODE in Global, and the pattern blocks korg.read.patternValue reads (-1 the pattern in RAM, 0 to 249 the bank), made on first use. */
    this.chainMode = 1;
    this.patternBlocks = new Map();
    /** The MFX 2 table of the patch mfx-switch, one entry per pattern: 1 to 100 the type as the display numbers it, 0 the default (7). */
    this.mfx2 = new Uint8Array(250);
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
    /**
     * The panel calls of API 25 (korg.keyDown and the others): the messages plugins gave the firmware, in order, as [call, ...args];
     * `down` the keys (34 the touchpad) and `padsDown` the pads a plugin holds down, so a second down or an up without a down sends
     * nothing, as on the device. `closeApp` is set by the device: EXIT closes an open app first.
     */
    this.firmwareInputs = [];
    this.down = new Uint8Array(35);
    this.padsDown = new Uint8Array(16);
    this.closeApp = () => {};
    /** Set by the device before each input: whether an app is open, so the keys an app keeps do not reach the firmware. */
    this.appOpen = false;
    /** The leaves of the object tree by id (data/script/objects.mjs), at their factory values; `repairs` is korg.system.repairs. */
    this.objects = OBJECTS.map(o => o.factory);
    /** 0 finger up, 1 the press came and the first position has not, 2 the first position is out. */
    this.touch = 0;
    /** korg.midi: the global MIDI channel (0 to 15), the MIDI SEND FILTER (0 Off, 1 Short, 2 Short + Program), the messages sent as byte arrays, a bit per message type kept from the firmware. */
    this.midiChannel = 0;
    this.midiFilter = 0;
    this.midiSent = [];
    this.midiHeld = 0;
    /** korg.audio.level: the two sides of the level meter, 0 to 254. */
    this.audioLevel = [0, 0];
    /** korg.read.sampleName and sampleInfo: the samples by slot, { name, start, end, loop, tune, stereo, length, oneShot, rate }; an empty slot reads as "" and 0. */
    this.samples = new Map();
  }

  /** A channel message out as the firmware's senders send it: 1 sent, 0 kept in by the MIDI SEND FILTER (program changes pass Short). */
  midiSend(status, channel, ...data) {
    if (status === 0xC0 ? this.midiFilter === 2 : this.midiFilter !== 0) return 0;
    this.midiSent.push([status | (channel < 0 ? this.midiChannel : channel), ...data]);
    return 1;
  }

  /** Host functions for the read API entries. */
  api() {
    return {
      "korg.read.transport": () => this.transport,
      "korg.read.tempo": () => this.tempo,
      "korg.read.pattern": () => this.pattern,
      "korg.read.viewedPattern": () => (this.viewed < 0 ? this.pattern : this.viewed),
      "korg.read.nextPattern": () => this.next,
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
      // whether this plugin's writes open the parameter window; the simulator has no window, it keeps the choice
      "korg.display.popups": (holds, on) => { holds.quiet = on ? 0 : 1; },
      "korg.read.popups": holds => (holds.quiet ? 0 : 1),
      "korg.touchLockX": x => { this.touchLock = x; },
      "korg.keyHold": (holds, key, on) => { this.keyExit("korg.keyHold", key); holds.keys[key] = on; this.syncHolds(holds); },
      "korg.keyMask": (holds, low, high) => {
        if ((low >>> KEY_EXIT) & 1) this.keyExit("korg.keyMask", KEY_EXIT);
        for (let key = 0; key < 34; key++) holds.keys[key] = key < 32 ? (low >>> key) & 1 : (high >>> (key - 32)) & 1;
        this.syncHolds(holds);
      },
      "korg.pressKey": key => { if (key === KEY_EXIT) this.closeApp(); this.pressedKeys.push(key); this.firmwareKey(key); },
      "korg.keyDown": key => {
        if (this.down[key]) return;
        if (key === KEY_EXIT) this.closeApp();
        this.down[key] = 1; this.firmwareInputs.push(["keyDown", key]); this.firmwareKey(key);
      },
      "korg.keyUp": key => { if (this.down[key]) { this.down[key] = 0; this.firmwareInputs.push(["keyUp", key]); } },
      "korg.padDown": (pad, velocity) => { if (!this.padsDown[pad]) { this.padsDown[pad] = 1; this.firmwareInputs.push(["padDown", pad, velocity]); } },
      "korg.padUp": pad => { if (this.padsDown[pad]) { this.padsDown[pad] = 0; this.firmwareInputs.push(["padUp", pad]); } },
      "korg.encoder": (index, delta) => { if (delta) this.firmwareInputs.push(["encoder", index, delta]); },
      "korg.touch": (x, y) => {
        if (x < 0) { if (this.down[KEY_TOUCHPAD]) { this.down[KEY_TOUCHPAD] = 0; this.firmwareInputs.push(["touchUp"]); } return; }
        this.down[KEY_TOUCHPAD] = 1; this.firmwareInputs.push(["touch", x, y]);
      },
      "korg.seq.setPatternValue": (field, value) => this.setPatternValue(field, value),
      "korg.read.patternBytes": (slots, pattern, offset) => this.patternBytes(slots, pattern, offset),
      "korg.read.patternName": (slots, pattern) => this.patternBytes(slots.subarray(0, 16), pattern, 16),
      "korg.seq.writeSteps": (slots, part, first) => this.writeSteps(slots, part, first),
      "korg.mute": (part, muted) => { if (this.mutes[part] !== muted) { this.mutes[part] = muted; this.emit("mute", part, muted); } },
      "korg.seq.getOn": (part, step) => this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.on],
      "korg.seq.getGate": (part, step) => this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.gate],
      "korg.seq.getNote": (part, step, slot) => this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.notes + slot] - 1,
      "korg.seq.getVelocity": (part, step) => this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.velocity],
      "korg.seq.setStep": (part, step, note, velocity) => this.setStep(part, step, note, velocity),
      "korg.seq.setGate": (part, step, gate) => { this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.gate] = gate; },
      "korg.get": leaf => this.objectGet(leaf),
      "korg.set": (leaf, index, value) => this.objectSet(leaf, value),
      "korg.motion.lane": lane => this.patternBlock(-1)[PATTERN_MOTION.owner + lane],
      "korg.motion.destination": lane => this.patternBlock(-1)[PATTERN_MOTION.destination + lane],
      "korg.motion.value": (lane, step) => this.patternBlock(-1)[PATTERN_MOTION.values + lane * PATTERN_MOTION.steps + step] - 1,
      "korg.motion.setValue": (lane, step, value) => {
        const block = this.patternBlock(-1);
        if (block[PATTERN_MOTION.owner + lane]) block[PATTERN_MOTION.values + lane * PATTERN_MOTION.steps + step] = value + 1;
      },
      // the simulator has no motion engine: every lane is silent
      "korg.motion.output": () => -1,
      "korg.midi.cc": (channel, cc, value) => this.midiSend(0xB0, channel, cc, value),
      "korg.midi.noteOn": (channel, note, velocity) => this.midiSend(0x90, channel, note, velocity),
      "korg.midi.noteOff": (channel, note) => this.midiSend(0x80, channel, note, 0x40),
      "korg.midi.program": (channel, program) => this.midiSend(0xC0, channel, program),
      "korg.audio.level": channel => this.audioLevel[channel],
      "korg.read.sampleName": (slots, slot) => {
        const name = (this.samples.get(slot)?.name ?? "").slice(0, 16), n = Math.min(name.length, slots.length);
        for (let i = 0; i < n; i++) slots[i] = name.charCodeAt(i) & 0xFF;
        return n;
      },
      "korg.read.sampleInfo": (slot, field) => this.samples.get(slot)?.[SAMPLE_INFO.fields[field]] ?? 0,
      // the simulator has no Write window: the pattern in RAM goes into its place in the bank at once
      "korg.pattern.write": () => { this.patternBlock(this.pattern).set(this.patternBlock(-1)); return 1; },
      "korg.part.copy": (pattern, from, to) => {
        const at = part => PATTERN_PARTS.base + part * PATTERN_PARTS.stride;
        const source = this.patternBlock(pattern === this.pattern ? -1 : pattern).slice(at(from), at(from + 1));
        this.patternBlock(-1).set(source, at(to));
      },
      "korg.midi.hold": (type, on) => { this.midiHeld = on ? this.midiHeld | (1 << type) : this.midiHeld & ~(1 << type); },
      "korg.motion.clearLane": lane => this.clearMotion(lane),
      "korg.motion.clearPart": part => this.clearMotionOf(part + 1),
      "korg.motion.clearMfx": () => this.clearMotionOf(PATTERN_MOTION.mfx),
      "korg.seq.clearPart": part => { for (let step = 0; step < PATTERN_STEPS.count; step++) this.patternBlock(-1)[this.stepAt(part, step) + PATTERN_STEPS.on] = 0; },
    };
  }

  /** A motion lane emptied as the firmware's clear_lane does: owner, destination and every value 0. */
  clearMotion(lane) {
    const block = this.patternBlock(-1);
    block[PATTERN_MOTION.owner + lane] = 0;
    block[PATTERN_MOTION.destination + lane] = 0;
    block.fill(0, PATTERN_MOTION.values + lane * PATTERN_MOTION.steps, PATTERN_MOTION.values + (lane + 1) * PATTERN_MOTION.steps);
  }

  /** Every motion lane of an owner (1 to 16 a part, 17 the master effect), as CLEAR MOTION and CLEAR MFX MOTION. */
  clearMotionOf(owner) {
    for (let lane = 0; lane < PATTERN_MOTION.lanes; lane++) if (this.patternBlock(-1)[PATTERN_MOTION.owner + lane] === owner) this.clearMotion(lane);
  }

  /** The Motion Sequence mode byte of the selected part in the pattern block. */
  motionModeAt() {
    return PATTERN_PARTS.base + this.part * PATTERN_PARTS.stride + PATTERN_MOTION.mode;
  }

  /** korg.get: the value of a leaf, as the runtime's table reads it. */
  objectGet(leaf) {
    if (!OBJECTS[leaf]) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectLeaf", { leaf })));
    if (OBJECTS[leaf].base === "motion") return this.patternBlock(-1)[this.motionModeAt()] ? 1 : 0;
    return this.objects[leaf];
  }

  /** korg.set: clamped to the leaf's range, one more repair when it was outside, as script_objects.s does. */
  objectSet(leaf, value) {
    const o = OBJECTS[leaf];
    if (!o) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectLeaf", { leaf })));
    if (!o.write) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectReadOnly", { path: o.path })));
    const clamped = Math.min(o.max, Math.max(o.min, value));
    if (clamped !== value) this.objects[REPAIRS] += 1;
    if (o.base === "touchpad") {
      // the simulator is a set with MFX 2 on: one key press reaches every mode but Gate Arp alone (0)
      if (clamped === 0 || clamped === this.objects[leaf]) return;
      this.objects[leaf] = clamped;
      this.emit("touchpadMode", clamped);
      return;
    }
    if (o.base === "motion") {
      // the simulator is a set with the patch tap-motion on: one TAP switches the selected part's motion, off and back to Smooth
      this.patternBlock(-1)[this.motionModeAt()] = clamped;
      return;
    }
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

  /**
   * korg.seq.setPartValue in the pattern in RAM: the value clamped to the field's range, a signed one as its byte, a u16 one
   * (sample) as its two bytes. The device writes a sample only to a slot that holds one; the simulator has no samples and
   * takes any slot in the range.
   */
  setPartValue(part, field, value) {
    const f = PART_FIELDS[field];
    const w = f && PART_WRITES[f.name];
    if (!w) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.objectReadOnly", { path: `korg.parts[${part}].${f?.name ?? field}` })));
    const at = PATTERN_PARTS.base + part * PATTERN_PARTS.stride + f.offset, v = Math.min(w[3], Math.max(w[2], value));
    const block = this.patternBlock(-1);
    block[at] = v & 255;
    if (f.kind === "u16") block[at + 1] = (v >> 8) & 255;
  }

  /** EXIT stays with the firmware: korg.keyHold and korg.keyMask refuse it, as the ARM runtime does. */
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
    if (f.kind === "mfx2") { this.mfx2[this.pattern] = v + 1; return; }
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
    // trigger 0 behind a step that is on with a TIE (gate above 96): the same note goes on without a new strike
    const before = at - PATTERN_STEPS.stride;
    block[at + PATTERN_STEPS.trigger] = step > 0 && block[before + PATTERN_STEPS.on] && block[before + PATTERN_STEPS.gate] > 96 ? 0 : 1;
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
    if (f.kind === "mfx2") {
      const entry = this.mfx2[pattern < 0 ? this.pattern : pattern] ?? 0;
      return entry >= 1 && entry <= 100 ? entry - 1 : 6;
    }
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
