/**
 * Where the firmware finds its FX presets, in any build, and how to add one
 * (docs/messungen/2026-10-15-preset-tabellen.md).
 *
 * Both builds read a preset through two small getters. Each takes a pointer out of an array and clamps the index.
 * The array's address sits in a literal word behind the getter, the clamp is an immediate in the two instructions
 * in front of it. Korg's own build keeps the records scattered, Hacktribe's keeps them in two tables of 100
 * records; the arrays say which. The BLECH patch `preset-tables` points the getters at arrays of 128 entries and
 * leaves room for 28 more records per table (tools/patch/preset_tables.py, the constants RES_IFX and RES_MFX).
 *
 * Nothing here is Korg data. A preset is only ever added as a copy of an existing record.
 */
import { field, sitesOf, readRaw, POINTER_TABLES } from "./map/index.mjs";
import { checkInstruction } from "./guards.mjs";
import { ramToFile, RAM_BASE } from "./map/address.mjs";

export const RECORD = 0x20c;
const IMAGE = 0x200100;

const GETTER = Object.fromEntries(["ifx", "mfx"].map(kind => [kind, POINTER_TABLES.get(`presets.${kind}`).getter]));
export const RESERVE = Object.fromEntries(["ifx", "mfx"].map(kind => [kind, POINTER_TABLES.get(`presets.${kind}`).reserve]));

/** `mov r2, #length` before the `mla` that finds a part's row in the insert knob memory; not among the map's sites (the length edit of the map leaves it). */
const IFX_ROW = 0x98184;

const u32 = (bytes, file) => new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(file, true);
const setU32 = (bytes, file, v) => new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).setUint32(file, v >>> 0, true);

/** `mov r0, #n` and `cmp r0, #n` with the condition and registers of the firmware's clamp; the immediate is the last byte. */
const clampOf = (bytes, kind) => {
  const word = u32(bytes, ramToFile(GETTER[kind].clamp));
  return (word & 0xffffff00) === 0x23a00000 ? (word & 0xff) : null;
};

/**
 * The preset arrays of an image, or null when the getters are not where they were measured
 * (a synthetic image, another firmware).
 * @returns {null | {ifx: {array: number, capacity: number}, mfx: {array: number, capacity: number}}}
 */
export function locatePresets(bytes) {
  if (bytes.length !== IMAGE) return null;
  const out = {};
  for (const kind of ["ifx", "mfx"]) {
    const array = u32(bytes, ramToFile(GETTER[kind].literal));
    const top = clampOf(bytes, kind);
    if (top === null || top < 1 || array < RAM_BASE || array % 4 || array + 4 * (top + 1) > RAM_BASE + IMAGE - 0x100) return null;
    for (let i = 0; i <= top; i++) {
      const p = u32(bytes, ramToFile(array) + 4 * i);
      if (p < RAM_BASE || p + RECORD > RAM_BASE + IMAGE - 0x100) return null;
    }
    out[kind] = { array, capacity: top + 1 };
  }
  return out;
}

/** The array slot (1-based, as the display counts) to the record's RAM address and file offset; null beyond the capacity. */
export function recordOf(bytes, kind, slot) {
  const where = locatePresets(bytes)?.[kind];
  if (!where || !Number.isInteger(slot) || slot < 1 || slot > where.capacity) return null;
  const ram = u32(bytes, ramToFile(where.array) + 4 * (slot - 1));
  return { ram, file: ramToFile(ram) };
}

/** Whether the pointer arrays in a running device are the file's (read through `readRam(addr, length)`): live access to Korg's records goes where the file says only then. */
export async function pointersMatch(bytes, readRam) {
  const where = locatePresets(bytes);
  if (!where) return false;
  for (const kind of ["ifx", "mfx"]) {
    const { array, capacity } = where[kind];
    const live = await readRam(array, 4 * capacity);
    const file = bytes.subarray(ramToFile(array), ramToFile(array) + 4 * capacity);
    if (live.length !== file.length || file.some((b, i) => live[i] !== b)) return false;
  }
  return true;
}

/** What the menu offers now. The insert length is stored in several places; `agreed` says whether they match. */
export function menuLength(bytes, kind) {
  if (kind === "mfx") return { value: readRaw(bytes, field("menu.mfxCount")), agreed: true };
  const { value, agreed } = readRaw(bytes, field("menu.ifxCount"));
  return { value, agreed };
}

/** Write the menu length, in every place it lives. The map's range (100) is the firmware's old one, the capacity here is the patch's. */
function setMenuLength(bytes, kind, n) {
  if (kind === "mfx") {
    const f = field("menu.mfxCount");
    const at = f.where.offset;
    checkInstruction(bytes.subarray(at, at + 4), { ...f.instruction, range: [1, 255] }, f.id);
    bytes[at] = n;
    return;
  }
  for (const s of sitesOf(field("menu.ifxCount"), n)) bytes[s.offset] = s.value;
  if (((u32(bytes, IFX_ROW) & 0xffffff00) >>> 0) === 0xe3a02000) bytes[IFX_ROW] = n;
}

/** The name of a record, for messages. */
export const nameAt = (bytes, file) => {
  let s = "";
  for (let i = 1; i < 16 && bytes[file + i] >= 0x20 && bytes[file + i] < 0x7f; i++) s += String.fromCharCode(bytes[file + i]);
  return s;
};

/**
 * How many presets the image can hold, how many the menu shows, and whether the image carries the BLECH patch
 * that lifts the firmware's limit of 100.
 */
export function presetRoom(bytes, kind) {
  const where = locatePresets(bytes)?.[kind];
  if (!where) return null;
  const length = menuLength(bytes, kind);
  return { capacity: where.capacity, count: length.value, agreed: length.agreed, patched: where.capacity > 100 };
}

/**
 * A copy of the image with one more preset: `from` (1-based) copied into the slot after the last one the menu shows,
 * the menu length raised in every place it lives. The slot gets a record of its own: the one its array entry points
 * at, or, for a slot of the patch's reserve whose entry still points at an earlier record, the reserve record of
 * that slot. The name of the copy is the old one with a number, cut to the width the display has.
 * Refused when the menu is full, the new slot's record holds a preset already (unless `overwrite`), or the image is not one we know.
 * @returns {{ok: boolean, bytes?: Uint8Array, slot?: number, name?: string, file?: number, reasons: string[]}}
 */
export function addPreset(bytes, kind, from, { overwrite = false } = {}) {
  const room = presetRoom(bytes, kind);
  if (!room) return { ok: false, reasons: ["Die Preset-Tabellen dieser Datei sind nicht erkannt."] };
  if (!room.agreed) return { ok: false, reasons: ["Die Stellen der Menülänge sind sich nicht einig."] };
  const slot = room.count + 1;
  if (slot > room.capacity) {
    return { ok: false, reasons: [room.patched
      ? `Die Tabelle ist voll: ${room.capacity} Plätze, mehr kann die Firmware nicht ansprechen.`
      : `Die Tabelle ist voll: ${room.capacity} Plätze. Mit dem Patch preset-tables sind es ${RESERVE[kind].first - 1 + RESERVE[kind].slots}.`] };
  }
  const source = recordOf(bytes, kind, from);
  if (!source || from > room.count) return { ok: false, reasons: [`Preset ${from} gibt es nicht.`] };
  const out = Uint8Array.from(bytes);
  const where = locatePresets(bytes)[kind];
  const entryAt = ramToFile(where.array) + 4 * (slot - 1);
  let target = recordOf(bytes, kind, slot);
  const earlier = Array.from({ length: slot - 1 }, (_, i) => u32(bytes, ramToFile(where.array) + 4 * i));
  if (slot >= RESERVE[kind].first && earlier.includes(target.ram)) {
    const own = RESERVE[kind].ram + (slot - RESERVE[kind].first) * RECORD;
    if (!room.patched || slot - RESERVE[kind].first >= RESERVE[kind].slots) return { ok: false, reasons: ["Für diesen Platz gibt es keinen eigenen Eintrag."] };
    setU32(out, entryAt, own);
    target = { ram: own, file: ramToFile(own) };
  } else if (earlier.includes(target.ram)) {
    return { ok: false, reasons: [`Der Platz ${slot} zeigt auf den Eintrag eines anderen Presets.`] };
  }
  const was = nameAt(bytes, target.file);
  if (was && !overwrite) return { ok: false, reasons: [`Der Platz ${slot} hält schon ein Preset (${was}); es liegt hinter der Menülänge und wird nicht überschrieben.`] };
  out.set(bytes.subarray(source.file, source.file + RECORD), target.file);
  const base = nameAt(bytes, source.file);
  const suffix = ` ${slot}`;
  const name = (base.slice(0, 15 - suffix.length) + suffix);
  for (let i = 0; i < 15; i++) out[target.file + 1 + i] = i < name.length ? name.charCodeAt(i) : 0;
  setMenuLength(out, kind, slot);
  return { ok: true, bytes: out, slot, name, file: target.file, reasons: [] };
}

/**
 * The bytes an edit of presets may change in an image: every record any array entry points at, the reserve, the array
 * entries beyond the firmware's own 100, and the places that hold the menu lengths (`code`, they are immediates in code
 * the firmware runs at start). As [file offset, length] runs.
 */
export function presetSpans(bytes) {
  const where = locatePresets(bytes);
  if (!where) return null;
  const data = [];
  for (const kind of ["ifx", "mfx"]) {
    for (let slot = 1; slot <= where[kind].capacity; slot++) data.push([recordOf(bytes, kind, slot).file, RECORD]);
    data.push([ramToFile(RESERVE[kind].ram), RESERVE[kind].slots * RECORD]);
    if (where[kind].capacity > 100) data.push([ramToFile(where[kind].array) + 400, 4 * (where[kind].capacity - 100)]);
  }
  const code = [...field("menu.ifxCount").sites.map(s => [s.file, 1]), [IFX_ROW, 1], [field("menu.mfxCount").where.offset, 1]];
  return { data, code };
}
