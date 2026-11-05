/**
 * The object tree of the plugin API (API 10): every value a plugin reads or sets by its path, such as
 * `korg.menu.blech.customizations.display.intensity`. The one source for the compiler (data/script/properties.mjs turns
 * each leaf into a property that calls korg.get or korg.set with the leaf's id), the ARM runtime (src/script/arm-tables.mjs
 * emits the table, tools/patch/script_objects.s reads and writes through it), the browser model and the docs.
 *
 * Change rules: ids are never reused or renumbered, a new leaf goes at the end with its `since`.
 *   base     where the value lives: "menu" MENU_STATE + offset (tools/patch/script_menu.s), "runtime" the state words of
 *            the object runtime + offset (script_objects.s), "global" the block of the Global settings behind the pointer
 *            at 0xC033E6A0, + 4 + offset (the dump offsets of data/map/global.mjs)
 *   type     "u8" one byte, "u32" one word
 *   min, max the valid range; a set outside it is clamped and counted, so is a stored value found outside it at start
 *   factory  the value when the menu starts without a settings file
 *   write    a plugin may set it
 *   stored   saved somewhere (settings file, Globals, pattern): the runtime checks it at start and after loading
 *   reset    a stored value outside the range goes back to `factory` instead of the nearest valid value
 *   apply    what makes a written value take effect: "none", "look" (the firmware's LEDs and backlight, menu_look_apply),
 *            "keepAwake" (Auto Power Off starts its 4 hours again), "setter" (the Global menu's own setter for the byte, per
 *            firmware in tools/patch/script_hooks.py GLOBAL_SETTERS; none on a build: the byte is written alone)
 *   action   a call instead of a value: `korg.system.keepAwake()` compiles to korg.set(id, -1, 1), it is not read
 */
import { text } from "../../src/text.mjs";
import globalMap from "../map/global.mjs";

export const OBJECT_BASES = Object.freeze(["menu", "runtime", "global"]);
export const OBJECT_TYPES = Object.freeze(["u8", "u32"]);
export const OBJECT_APPLY = Object.freeze(["none", "look", "keepAwake", "setter"]);
/** Bytes of one row of the runtime's table: offset, min, max, factory, setter (words), then base, type, apply, flags (bytes). */
export const OBJECT_ROW_SIZE = 24;
export const OBJECT_FLAGS = Object.freeze({ write: 1, reset: 2, stored: 4 });

const leaf = (id, path, o) => Object.freeze({ id, path, reset: false, stored: false, apply: "none", action: false, ...o });

/**
 * korg.global.*: one leaf per known field of data/map/global.mjs (no `unknown` run, not the two markers), in the order of the
 * Global menu's pages. [leaf name, field id in the map, page, factory (the firmware's default table, same on all three
 * builds)]. The range is the map's, which is the menu's (measure:2026-10-14/global-felder).
 * The ids go on after the leaves above and are never changed: a new field goes at the end of this list.
 */
const GLOBALS = [
  ["triggerMode", "triggerMode", "TRIGGER MODE", 0],
  ["velocityCurve", "velocityCurve", "VELOCITY CURVE", 0],
  ["clockMode", "clockMode", "CLOCK MODE", 0],
  ["midiChannel", "channel", "GLOBAL MIDI CH.", 0],
  ["receiveFilter", "receiveFilter", "MIDI RECEIVE FILTER", 0],
  ["sendFilter", "sendFilter", "MIDI SEND FILTER", 0],
  ["syncPolarity", "syncPolarity", "SYNC POLARITY", 0],
  ["syncResolution", "syncResolution", "SYNC UNIT", 1],
  ["metronome", "metronome", "METRONOME", 1],
  ["tempoLock", "tempoLock", "TEMPO LOCK", 0],
  ["knobMode", "knobMode", "KNOB MODE", 0],
  ["touchScaleRange", "touchScaleRange", "TOUCH SCALE RANGE", 1],
  ["lcdContrast", "lcdContrast", "LCD CONTRAST", 34],
  ["audioInThru", "audioInThru", "AUDIO IN THRU", 0],
  ["batteryType", "batteryMode", "BATTERY TYPE", 0],
  ["autoPowerOff", "autoPowerOff", "AUTO POWER OFF", 1],
  ["powerSave", "powerSave", "POWER SAVE MODE", 0],
  ["patternChangeLock", "patternChangeLock", "PTN. CHANGE LOCK", 0],
  ["chainMode", "chainMode", "CHAIN MODE", 0],
];
/** The Global leaves a plugin may set: the ones measured in the emulator to take the value without a restart (docs/messungen/2026-11-05-plugin-api16.md). */
const GLOBAL_WRITABLE = new Set(GLOBALS.map(g => g[0]));

function globalLeaves() {
  return GLOBALS.map(([name, field, page, factory], i) => {
    const f = globalMap.fields.find(x => x.id === `global.${field}`);
    if (!f?.range || f.source === "unknown") throw new Error(`korg.global.${name}: no known field ${field} in data/map/global.mjs`);
    return leaf(4 + i, `korg.global.${name}`, {
      base: "global", offset: f.where.offset, type: "u8", min: f.range[0], max: f.range[1], factory, write: GLOBAL_WRITABLE.has(name),
      stored: true, apply: "setter", since: 16, unit: "value", field, page, text: text("api.object.global", { page }),
    });
  });
}

export const OBJECTS = Object.freeze([
  leaf(0, "korg.menu.blech.customizations.display.intensity", {
    base: "menu", offset: -0x20, type: "u8", min: 0, max: 15, factory: 15, write: true, stored: true, apply: "look", since: 10,
    unit: "0 off, 15 full", text: text("api.object.display.intensity"),
  }),
  leaf(1, "korg.system.repairs", {
    base: "runtime", offset: 0, type: "u32", min: 0, max: 0x7fffffff, factory: 0, write: false, since: 10,
    unit: "count", text: text("api.object.system.repairs"),
  }),
  leaf(2, "korg.system.testMode", {
    // read only for plugins: one that switched it on at start would leave the device dark at every power-on; the console and
    // remote_press.py set it over USB (tools/patch/script_remote.s, RM_TEST)
    base: "runtime", offset: 4, type: "u8", min: 0, max: 1, factory: 0, write: false, since: 10,
    unit: "0 off, 1 on", text: text("api.object.system.testMode"),
  }),
  leaf(3, "korg.system.keepAwake", {
    base: "runtime", offset: 5, type: "u8", min: 0, max: 1, factory: 0, write: true, apply: "keepAwake", action: true, since: 10,
    unit: "action", text: text("api.object.system.keepAwake"),
  }),
  ...globalLeaves(),
]);

export const OBJECT_BY_PATH = new Map(OBJECTS.map(o => [o.path, o]));

/** The flags byte of a leaf's row. */
export const objectFlags = o => (o.write ? OBJECT_FLAGS.write : 0) | (o.reset ? OBJECT_FLAGS.reset : 0) | (o.stored ? OBJECT_FLAGS.stored : 0);

/** The children of a branch, for error messages and the editor: "korg.menu.blech" -> ["customizations"]. */
export function objectChildren(path) {
  const prefix = `${path}.`;
  return [...new Set(OBJECTS.filter(o => o.path.startsWith(prefix)).map(o => o.path.slice(prefix.length).split(".")[0]))];
}

/** True when the path is a branch of the tree (not a leaf): the compiler then names the children. */
export const isObjectBranch = path => objectChildren(path).length > 0;
