/**
 * The 72 modulation types in the firmware image. Hacktribe's build holds two copies
 * and reads one, so an edit has to go to the copy the code points at: the table
 * readers load the address of the names of entry 0 from literals in the ARM code.
 * Runs in a browser.
 */
import { TABLES, field, readRaw, writeRaw, offsetOf, typeOf } from "./map/index.mjs";
import { fileToRam, ramToFile, RAM_BASE } from "./map/address.mjs";

const TABLE = TABLES.get("table.modType");
const HEADER = 0x100;
const NAME = field("modType.name");
const TARGET = field("modType.target");
const DEPTH = field("modType.depth");
const SPEED = field("modType.speed");
const CURVE = field("modType.curve");

/**
 * Fields of one type the page edits, in the order the form shows them. The target (+0x19) is not among them:
 * the firmware never reads it (measure:2026-10-15/modulation-stufe2), the real targets sit in the slots.
 */
export const MOD_FIELDS = Object.freeze({ name: NAME, depth: DEPTH, speed: SPEED, curve: CURVE });
/** Fields of one modulation slot; slot k is eight bytes from +0x2C, the editor reaches slots 0 to 4. */
export const SLOT_FIELDS = Object.freeze({
  source: field("modType.slot.source"), target: field("modType.slot.target"),
  lo: field("modType.slot.lo"), hi: field("modType.slot.hi"), follow: field("modType.slot.follow"),
});
export const SLOT_COUNT = SLOT_FIELDS.source.repeat[0].count;
export const MOD_COUNT = TABLE.count;

// One entry as far as the checks reach.
const TABLE_SIZE = Math.max(offsetOf(CURVE), ...TABLE.locate.flags) + 1;
const printable = b => b >= 0x20 && b <= 0x7e;

/**
 * Whether the bytes at `file` are 72 entries the firmware could use: a shown name, target 0 to 5,
 * depth and speed 0 to 127, the flag bytes 0 or 1. The flags matter: the structure one entry before
 * Korg's copy has a pointer of its own and would pass as a table shifted by one entry without them.
 */
function plausible(bytes, file) {
  const width = typeOf(NAME).width;
  if (file < HEADER || file + (TABLE.count - 1) * TABLE.stride + TABLE_SIZE > bytes.length) return false;
  for (let i = 0; i < TABLE.count; i++) {
    const e = file + i * TABLE.stride;
    const at = e + offsetOf(NAME);
    if (!printable(bytes[at])) return false;
    let k = 1;
    while (k < width && printable(bytes[at + k])) k++;
    for (; k < width; k++) if (bytes[at + k] !== 0) return false;
    if (TABLE.locate.flags.some(o => bytes[e + o] > 1)) return false;
    if (bytes[e + offsetOf(TARGET)] > 5 || bytes[e + offsetOf(DEPTH)] > 127 || bytes[e + offsetOf(SPEED)] > 127) return false;
  }
  return true;
}

/**
 * The copy of the table this image reads: the one whose entry 0 has its names
 * pointed at from the code (aligned words before the DSP stream).
 * @param {Uint8Array} bytes a whole SYSTEM.VSB
 * @returns {{ok: true, file: number, ram: number, place: string, readers: number[]}
 *   | {ok: false, reasons: string[]}} `place` is the map table when it is one of the known copies, else "other"; `readers` the file offsets of the pointing words
 */
export function locateModTable(bytes) {
  const { pointsAt, codeEnd } = TABLE.locate;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const found = new Map();      // candidate file -> reader offsets, or null when the bytes there are no table
  for (let at = HEADER; at + 4 <= Math.min(codeEnd, bytes.length); at += 4) {
    const word = view.getUint32(at, true);
    if (word < RAM_BASE) continue;
    const file = ramToFile(word) - pointsAt;
    if (file < HEADER || file >= bytes.length) continue;
    let readers = found.get(file);
    if (readers === undefined) {
      readers = plausible(bytes, file) ? [] : null;
      found.set(file, readers);
    }
    readers?.push(at);
  }
  const hits = [...found].filter(([, readers]) => readers);
  const hex = n => `0x${n.toString(16)}`;
  if (!hits.length) {
    return { ok: false, reasons: ["Die Tabelle mit den Modulationen ist in dieser Datei nicht zu finden."] };
  }
  if (hits.length > 1) {
    return { ok: false, reasons: [`Die Tabelle mit den Modulationen ist mehrfach drin (${hits.map(([f]) => hex(f)).join(", ")}), unklar welche gilt.`] };
  }
  const [[file, readers]] = hits;
  const place = [TABLE.id, ...TABLE.locate.others].find(id => TABLES.get(id).file === file) ?? "other";
  return { ok: true, file, ram: fileToRam(file), place, readers };
}

/**
 * One entry as plain values: name, the target label (read only), default depth, default speed, curve and the
 * slots 0 to 4 as { source, target, lo, hi, follow }. `file` is the table start from locateModTable.
 */
export function readModType(bytes, file, index) {
  checkIndex(index);
  const base = file + index * TABLE.stride;
  const get = (f, ix = []) => readRaw(bytes, f, ix, base);
  return {
    name: get(NAME), target: get(TARGET), depth: get(DEPTH), speed: get(SPEED), curve: get(CURVE),
    slots: Array.from({ length: SLOT_COUNT }, (_, k) => Object.fromEntries(Object.entries(SLOT_FIELDS).map(([key, f]) => [key, get(f, [k])]))),
  };
}

export const readModTypes = (bytes, file) => Array.from({ length: MOD_COUNT }, (_, i) => readModType(bytes, file, i));

/**
 * Write the listed values of one entry; anything else in the entry, known or not,
 * stays as it is. A value outside its range is refused by the map before a byte moves.
 * `slots` is a list of up to five partial slots ({ target: 3 }, or undefined to leave a slot alone).
 * @param {Partial<{name: string, depth: number, speed: number, curve: number, slots: Array<Partial<{source: number, target: number, lo: number, hi: number, follow: number}>|undefined>}>} values
 */
export function writeModType(bytes, file, index, values) {
  checkIndex(index);
  const base = file + index * TABLE.stride;
  const keys = Object.keys(values);
  const unknown = keys.find(k => !(k in MOD_FIELDS) && k !== "slots");
  if (unknown === "target") throw new Error("the target is a label the firmware never reads, the editor does not write it");
  if (unknown) throw new Error(`${unknown} is not a field of a modulation type`);
  if (typeof values.name === "string" && !values.name) throw new RangeError("a modulation type needs a name the display can show");
  const writes = keys.filter(k => k !== "slots").map(k => [MOD_FIELDS[k], [], values[k]]);
  const slots = values.slots ?? [];
  if (slots.length > SLOT_COUNT) throw new RangeError(`a type has ${SLOT_COUNT} slots the editor reaches`);
  slots.forEach((slot, k) => {
    for (const [key, raw] of Object.entries(slot ?? {})) {
      if (!(key in SLOT_FIELDS)) throw new Error(`${key} is not a field of a modulation slot`);
      writes.push([SLOT_FIELDS[key], [k], raw]);
    }
  });
  // A refused value must not leave a half-written entry.
  const probe = Uint8Array.from(bytes.subarray(base, base + TABLE.stride));
  for (const [f, ix, raw] of writes) writeRaw(probe, f, ix, raw);
  for (const [f, ix, raw] of writes) writeRaw(bytes, f, ix, raw, base);
}

/** [file offset, length] of the bytes of every field the page edits, slots included, for entry `index`. */
export function modFieldSpans(file, index) {
  const base = file + index * TABLE.stride;
  return [
    ...Object.values(MOD_FIELDS).map(f => [base + offsetOf(f), typeOf(f).width]),
    ...Array.from({ length: SLOT_COUNT }, (_, k) => Object.values(SLOT_FIELDS).map(f => [base + offsetOf(f, [k]), typeOf(f).width])).flat(),
  ];
}

function checkIndex(index) {
  if (!Number.isInteger(index) || index < 0 || index >= MOD_COUNT) throw new RangeError(`modulation type ${index} does not exist`);
}
