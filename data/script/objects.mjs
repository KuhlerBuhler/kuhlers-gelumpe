/**
 * The object tree of the plugin API (API 10): every value a plugin reads or sets by its path, such as
 * `korg.menu.blech.customizations.display.intensity`. The one source for the compiler (data/script/properties.mjs turns
 * each leaf into a property that calls korg.get or korg.set with the leaf's id), the ARM runtime (src/script/arm-tables.mjs
 * emits the table, tools/patch/script_objects.s reads and writes through it), the browser model and the docs.
 *
 * Change rules: ids are never reused or renumbered, a new leaf goes at the end with its `since`.
 *   base     where the value lives: "menu" MENU_STATE + offset (tools/patch/script_menu.s), "runtime" the state words of
 *            the object runtime + offset (script_objects.s)
 *   type     "u8" one byte, "u32" one word
 *   min, max the valid range; a set outside it is clamped and counted, so is a stored value found outside it at start
 *   factory  the value when the menu starts without a settings file
 *   write    a plugin may set it
 *   stored   saved somewhere (settings file, Globals, pattern): the runtime checks it at start and after loading
 *   reset    a stored value outside the range goes back to `factory` instead of the nearest valid value
 *   apply    what makes a written value take effect: "none", "look" (the firmware's LEDs and backlight, menu_look_apply)
 */
import { text } from "../../src/text.mjs";

export const OBJECT_BASES = Object.freeze(["menu", "runtime"]);
export const OBJECT_TYPES = Object.freeze(["u8", "u32"]);
export const OBJECT_APPLY = Object.freeze(["none", "look"]);
/** Bytes of one row of the runtime's table: offset, min, max, factory (words), then base, type, apply, flags (bytes). */
export const OBJECT_ROW_SIZE = 20;
export const OBJECT_FLAGS = Object.freeze({ write: 1, reset: 2, stored: 4 });

const leaf = (id, path, o) => Object.freeze({ id, path, reset: false, stored: false, apply: "none", ...o });

export const OBJECTS = Object.freeze([
  leaf(0, "korg.menu.blech.customizations.display.intensity", {
    base: "menu", offset: -0x20, type: "u8", min: 0, max: 15, factory: 15, write: true, stored: true, apply: "look", since: 10,
    unit: "0 off, 15 full", text: text("api.object.display.intensity"),
  }),
  leaf(1, "korg.system.repairs", {
    base: "runtime", offset: 0, type: "u32", min: 0, max: 0x7fffffff, factory: 0, write: false, since: 10,
    unit: "count", text: text("api.object.system.repairs"),
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
