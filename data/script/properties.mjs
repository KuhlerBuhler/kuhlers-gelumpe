/**
 * The Electribe as objects: `korg.tempo`, `korg.parts[3].muted`, `korg.knobs.LEVEL`, `korg.store[2]`. The compiler
 * turns reading a property into a call of its `read` entry of the API table and setting it into a call of its `write`
 * entry, so the block format stays as it is. The arguments: "index" is the bracket, "value" the assigned value.
 */
import { text } from "../../src/text.mjs";
import { KNOBS } from "../panel.mjs";
import { PATTERN_FIELDS, PART_FIELDS } from "./contract.mjs";
import { OBJECTS } from "./objects.mjs";

const knobName = id => id.replace(/([a-z])([A-Z0-9])/g, "$1_$2").toUpperCase();

/** `korg.knobs.LEVEL`: the knob names, from the panel table, as the index the knob event and korg.read.knob use. */
export const KNOB_NAMES = Object.freeze(KNOBS.map(k => Object.freeze({ name: knobName(k.id), value: k.index, label: k.label })));

const p = (path, read, write, text, range = null) => Object.freeze({ path, read, write, text, range });

export const PROPERTIES = Object.freeze([
  p("korg.tempo", ["korg.read.tempo", []], ["korg.tempo", ["value"]], text("api.property.tempo")),
  p("korg.transport", ["korg.read.transport", []], null, text("api.property.transport")),
  p("korg.selectedPattern", ["korg.read.pattern", []], ["korg.pattern", ["value"]], text("api.property.selectedPattern")),
  p("korg.selectedPart", ["korg.read.part", []], ["korg.part", ["value"]], text("api.property.selectedPart")),
  p("korg.parts[].step", ["korg.read.step", ["index"]], null, text("api.property.parts.step")),
  p("korg.parts[].muted", ["korg.read.mute", ["index"]], ["korg.mute", ["index", "value"]], text("api.property.parts.muted")),
  p("korg.knobs[]", ["korg.read.knob", ["index"]], null, text("api.property.knobs")),
  p("korg.store[]", ["korg.store.get", ["index", 0]], ["korg.store.set", ["index", "value"]], text("api.property.store")),
  p("korg.leds[]", null, ["korg.led", ["index", "value"]], text("api.property.leds")),
  p("korg.chainMode", ["korg.read.chainMode", []], null, text("api.property.chainMode")),
  ...PATTERN_FIELDS.map((f, i) => p(`korg.current.${f.name}`, ["korg.read.patternValue", [-1, -1, i]], null, text("api.property.current", { field: f.text }))),
  ...PATTERN_FIELDS.map((f, i) => p(`korg.patterns[].${f.name}`, ["korg.read.patternValue", ["index", -1, i]], null, text("api.property.patterns", { field: f.text }))),
  ...PART_FIELDS.map((f, i) => p(`korg.parts[].${f.name}`, ["korg.read.patternValue", [-1, "index", i]], null, text("api.property.parts", { field: f.text }))),
  // the object tree (data/script/objects.mjs): one call each way with the leaf's id, the runtime checks the range; actions are calls
  ...OBJECTS.filter(o => !o.action).map(o => p(o.path, ["korg.get", [o.id, -1]], o.write ? ["korg.set", [o.id, -1, "value"]] : null, o.text, [o.min, o.max])),
]);

export const PROPERTY_BY_PATH = new Map(PROPERTIES.map(x => [x.path, x]));
