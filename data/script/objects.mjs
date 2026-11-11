/**
 * The object tree of the plugin API (API 10): every value a plugin reads or sets by its path, such as
 * `korg.menu.blech.customizations.display.intensity`. The one source for the compiler (data/script/properties.mjs turns
 * each leaf into a property that calls korg.get or korg.set with the leaf's id), the ARM runtime (src/script/arm-tables.mjs
 * emits the table, tools/patch/script_objects.s reads and writes through it), the browser model and the docs.
 *
 * Change rules: ids are never reused or renumbered, a new leaf goes at the end with its `since`.
 *   base     where the value lives: "menu" MENU_STATE + offset (tools/patch/script_menu.s), "runtime" the state words of
 *            the object runtime + offset (script_objects.s), "abs" the absolute address `offset` (a setting word of a patch,
 *            in our own code area), "global" the Global settings the firmware keeps + offset (a pointer read at each access),
 *            "pad" no address: `offset` picks a call into the patch pad-colors (0 PAD COLOR, 1 SELECT COLOR, 2 OVERLAP, 3 LED DIMMING),
 *            "info" no address, read only: `offset` picks what the runtime knows about the device it runs on (INFO),
 *            "touchpad" no address: the touch pad mode, read from the firmware and the patch mfx-switch, set with one key press
 *            "motion" no address: whether the selected part plays its motion, set with one TAP press of the patch tap-motion
 *   type     "u8" one byte, "u32" one word
 *   min, max the valid range; a set outside it is clamped and counted, so is a stored value found outside it at start
 *   factory  the value when the menu starts without a settings file
 *   write    a plugin may set it
 *   stored   saved somewhere (settings file, Globals, pattern): the runtime checks it at start and after loading
 *   reset    a stored value outside the range goes back to `factory` instead of the nearest valid value
 *   apply    what makes a written value take effect: "none", "look" (the firmware's LEDs and backlight, menu_look_apply),
 *            "keepAwake" (Auto Power Off starts its 4 hours again), "setter" (the Global menu's own setter for the byte, per
 *            firmware in tools/patch/script_hooks.py GLOBAL_SETTERS; none on a build: the byte is written alone)
 *   mirror   a second place the written value goes to as a word (the setting word the patch behind a page reads), 0 none
 *   action   a call instead of a value: `korg.system.keepAwake()` compiles to korg.set(id, -1, 1), it is not read
 */
import { text } from "../../src/text.mjs";
import globalMap from "../map/global.mjs";

export const OBJECT_BASES = Object.freeze(["menu", "runtime", "abs", "global", "pad", "info", "touchpad", "motion"]);
/**
 * What a leaf of the base "info" reads, by its `offset` (tools/patch/script_objects.s, objects_info_get): the build the runtime
 * was made for, the version of the set (the text of the patch blech-version), and the counts the firmware's own functions
 * return, so an fx catalog with more types raises them. `factory` is what the editor's simulator reads.
 */
export const INFO = Object.freeze({ device: 0, version: 1, ifxTypes: 2, mfxTypes: 3, samples: 4 });
export const OBJECT_TYPES = Object.freeze(["u8", "u32"]);
export const OBJECT_APPLY = Object.freeze(["none", "look", "keepAwake", "setter"]);
/** Bytes of one row of the runtime's table: offset, min, max, factory (words), then base, type, apply, flags (bytes), then mirror and setter (words). */
export const OBJECT_ROW_SIZE = 28;
export const OBJECT_FLAGS = Object.freeze({ write: 1, reset: 2, stored: 4 });

const leaf = (id, path, o) => Object.freeze({ id, path, reset: false, stored: false, apply: "none", action: false, mirror: 0, ...o });

/**
 * korg.global.*: one leaf per known field of data/map/global.mjs (no `unknown` run, not the two markers), in the order of the
 * Global menu's pages. [leaf name, field id in the map, page, factory (the firmware's default table, same on all three
 * builds)]. The range is the map's, which is the menu's (measure:2026-10-14/global-felder). `offset` is the one of the base
 * "global", the object the firmware keeps, so the dump offset of the map plus the word in front of the block. Slots 247 to 249 of
 * the object belong to our patches and have no leaf here. The ids go on after the leaves above and are never changed: a new
 * field goes at the end of this list.
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

/** The id of the first Global leaf: the ones before it are the leaves of API 10 to 17. */
const GLOBAL_FIRST = 29;

function globalLeaves() {
  return GLOBALS.map(([name, field, page, factory], i) => {
    const f = globalMap.fields.find(x => x.id === `global.${field}`);
    if (!f?.range || f.source === "unknown") throw new Error(`korg.global.${name}: no known field ${field} in data/map/global.mjs`);
    return leaf(GLOBAL_FIRST + i, `korg.global.${name}`, {
      base: "global", offset: f.where.offset + 4, type: "u8", min: f.range[0], max: f.range[1], factory, write: true,
      stored: true, apply: "setter", since: 20, unit: "value", field, page, text: text("api.object.global", { page }),
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

  // API 17: every other page of CUSTOMIZATION and FEATURES. The look pages (apply "look") take effect like the page does; the
  // values are in RAM until WRITE in the menu (or korg.menu.blech.write()) keeps them. Where the page shows a derived value
  // (the colours as hue, saturation, brightness) the leaf is the stored one (red, green, blue, 0 to 15 each).
  leaf(4, "korg.menu.blech.customizations.display.red", {
    base: "menu", offset: 0xB0, type: "u32", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 to 15, all three 0 the stock white", text: text("api.object.display.red"),
  }),
  leaf(5, "korg.menu.blech.customizations.display.green", {
    base: "menu", offset: 0xB4, type: "u32", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 to 15", text: text("api.object.display.green"),
  }),
  leaf(6, "korg.menu.blech.customizations.display.blue", {
    base: "menu", offset: 0xB8, type: "u32", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 to 15", text: text("api.object.display.blue"),
  }),
  leaf(7, "korg.menu.blech.customizations.display.invert", {
    base: "menu", offset: 0x1B8, type: "u32", min: 0, max: 1, factory: 1, write: true, apply: "look", since: 17,
    unit: "0 off, 1 on", text: text("api.object.display.invert"),
  }),
  leaf(8, "korg.menu.blech.customizations.led.mode", {
    base: "menu", offset: 0xA0, type: "u32", min: 0, max: 2, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 meter, 1 color, 2 off", text: text("api.object.led.mode"),
  }),
  leaf(9, "korg.menu.blech.customizations.led.red", {
    base: "menu", offset: 0xA4, type: "u32", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 to 15, all three 0 the stock colours", text: text("api.object.led.red"),
  }),
  leaf(10, "korg.menu.blech.customizations.led.green", {
    base: "menu", offset: 0xA8, type: "u32", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 to 15", text: text("api.object.led.green"),
  }),
  leaf(11, "korg.menu.blech.customizations.led.blue", {
    base: "menu", offset: 0xAC, type: "u32", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 to 15", text: text("api.object.led.blue"),
  }),
  leaf(12, "korg.menu.blech.customizations.led.meter.still", {
    base: "menu", offset: -0x1C, type: "u8", min: 0, max: 9, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 stock, 1 to 7 colour, 8 rainbow, 9 off", text: text("api.object.led.meter.still"),
  }),
  leaf(13, "korg.menu.blech.customizations.led.meter.low", {
    base: "menu", offset: -0x1B, type: "u8", min: 0, max: 7, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 stock, 1 to 7 colour", text: text("api.object.led.meter.low"),
  }),
  leaf(14, "korg.menu.blech.customizations.led.meter.mid", {
    base: "menu", offset: -0x1A, type: "u8", min: 0, max: 7, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 stock, 1 to 7 colour", text: text("api.object.led.meter.mid"),
  }),
  leaf(15, "korg.menu.blech.customizations.led.meter.loud", {
    base: "menu", offset: -0x19, type: "u8", min: 0, max: 8, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 stock, 1 to 7 colour, 8 rainbow", text: text("api.object.led.meter.loud"),
  }),
  leaf(16, "korg.menu.blech.customizations.padColor.part", {
    base: "pad", offset: 0, type: "u8", min: 0, max: 2, factory: 0, write: true, since: 17,
    unit: "0 red, 1 blue, 2 pink", text: text("api.object.padColor.part"),
  }),
  leaf(17, "korg.menu.blech.customizations.padColor.select", {
    base: "pad", offset: 1, type: "u8", min: 0, max: 2, factory: 1, write: true, since: 17,
    unit: "0 red, 1 blue, 2 pink", text: text("api.object.padColor.select"),
  }),
  leaf(18, "korg.menu.blech.customizations.padColor.overlap", {
    base: "pad", offset: 2, type: "u8", min: 0, max: 3, factory: 0, write: true, since: 17,
    unit: "0 the colour left, 1 red, 2 blue, 3 pink", text: text("api.object.padColor.overlap"),
  }),
  leaf(19, "korg.menu.blech.customizations.powerSave.displayLight", {
    base: "menu", offset: -0x1F, type: "u8", min: 0, max: 15, factory: 0, write: true, apply: "look", since: 17,
    unit: "0 the firmware's dim, 1 to 15", text: text("api.object.powerSave.displayLight"),
  }),
  leaf(20, "korg.menu.blech.customizations.powerSave.ledDimming", {
    base: "pad", offset: 3, type: "u8", min: 0, max: 11, factory: 8, write: true, since: 17,
    unit: "step: 0, 10, 20, 30, 40, 50, 60, 70, 75, 80, 90, 100 percent", text: text("api.object.powerSave.ledDimming"),
  }),
  leaf(21, "korg.menu.blech.features.mfx2", {
    base: "menu", offset: 20, type: "u32", min: 0, max: 1, factory: 1, write: true, since: 17,
    unit: "0 off, 1 on, from the next start", text: text("api.object.features.mfx2"),
  }),
  leaf(22, "korg.menu.blech.features.patternConfirm", {
    base: "menu", offset: 0x158, type: "u32", min: 0, max: 1, factory: 1, write: true, mirror: 0xC0180F10, since: 17,
    unit: "0 off, 1 on", text: text("api.object.features.patternConfirm"),
  }),
  leaf(23, "korg.menu.blech.features.tapMotion", {
    base: "menu", offset: 0x15C, type: "u32", min: 0, max: 2, factory: 1, write: true, mirror: 0xC0188F00, since: 17,
    unit: "0 off, 1 on, 2 once", text: text("api.object.features.tapMotion"),
  }),
  leaf(24, "korg.menu.blech.features.noteAssist", {
    base: "menu", offset: 0xFC, type: "u32", min: 0, max: 1, factory: 1, write: true, mirror: 0xC0189F00, since: 17,
    unit: "0 off, 1 on", text: text("api.object.features.noteAssist"),
  }),
  leaf(25, "korg.menu.blech.features.lastPattern", {
    base: "abs", offset: 0xC014FEFC, type: "u32", min: 0, max: 1, factory: 1, write: true, since: 17,
    unit: "0 off, 1 on", text: text("api.object.features.lastPattern"),
  }),
  leaf(26, "korg.menu.blech.features.stereo1Pad", {
    base: "abs", offset: 0xC014FFFC, type: "u32", min: 0, max: 1, factory: 1, write: true, since: 17,
    unit: "0 off, 1 on", text: text("api.object.features.stereo1Pad"),
  }),
  leaf(27, "korg.menu.blech.features.initPattern", {
    base: "global", offset: 247, type: "u8", min: 0, max: 250, factory: 0, write: true, since: 17,
    unit: "0 factory, 1 to 250 the pattern", text: text("api.object.features.initPattern"),
  }),
  leaf(28, "korg.menu.blech.write", {
    // the byte is the request: the frame hook (objects_write_flush) writes the settings file once the main screen or BLECH is up
    base: "runtime", offset: 6, type: "u8", min: 0, max: 1, factory: 0, write: true, action: true, since: 17,
    unit: "action", text: text("api.object.menu.write"),
  }),
  ...globalLeaves(),

  // API 26: the device a plugin runs on, so it adapts its ranges instead of hardcoding them (base "info", read only)
  leaf(48, "korg.system.device", {
    base: "info", offset: INFO.device, type: "u32", min: 0, max: 2, factory: 0, write: false, since: 26,
    unit: "0 hacktribe, 1 red, 2 blue", text: text("api.object.system.device"),
  }),
  leaf(49, "korg.system.version", {
    base: "info", offset: INFO.version, type: "u32", min: 0, max: 999999, factory: 0, write: false, since: 26,
    unit: "x * 10000 + y * 100 + z, 0 unknown", text: text("api.object.system.version"),
  }),
  leaf(50, "korg.system.limits.ifxTypes", {
    base: "info", offset: INFO.ifxTypes, type: "u32", min: 0, max: 255, factory: 73, write: false, since: 26,
    unit: "count", text: text("api.object.system.limits.ifxTypes"),
  }),
  leaf(51, "korg.system.limits.mfxTypes", {
    base: "info", offset: INFO.mfxTypes, type: "u32", min: 0, max: 255, factory: 43, write: false, since: 26,
    unit: "count", text: text("api.object.system.limits.mfxTypes"),
  }),
  leaf(52, "korg.system.limits.samples", {
    base: "info", offset: INFO.samples, type: "u32", min: 0, max: 1000, factory: 1000, write: false, since: 26,
    unit: "count, 0 on blue", text: text("api.object.system.limits.samples"),
  }),

  // API 27: the touch pad mode; the factory value is the start mode of the patch mfx-switch
  leaf(53, "korg.touchpad.mode", {
    base: "touchpad", offset: 0, type: "u32", min: 0, max: 4, factory: 2, write: true, since: 27,
    unit: "0 gate arp, 1 touch scale, 2 master fx, 3 both, 4 mfx 2", text: text("api.object.touchpad.mode"),
  }),

  // API 28: the motion switch of the selected part, as TAP switches it with the patch tap-motion
  leaf(54, "korg.motion.enabled", {
    base: "motion", offset: 0, type: "u32", min: 0, max: 1, factory: 1, write: true, since: 28,
    unit: "0 off, 1 on", text: text("api.object.motion.enabled"),
  }),
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
