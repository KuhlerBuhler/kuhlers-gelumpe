/**
 * The collection on the card, KORG/blechtribe/Presets/e2sFx.all: presets and modulation types BLECHTRIBE loads into
 * RAM at power-on (tools/patch/fx_card.s), never into the flash. Every entry carries its .e2fx v2 text, so the file
 * reads back on any build, and the bytes for the build it was made for, which is what the firmware copies.
 *
 *   header  24 bytes: magic "GFXA", version u16, count u16, total size u32, CRC-32 of the rest u32, build u32, 0 u32
 *   entry    8 bytes: kind u8 (1 insert, 2 master, 3 modulation), index u8 (0-based), text length u16,
 *                     data length u16, 0 u16; then the data, the text, and zeros to a multiple of 4
 *
 * The firmware checks all of it before it writes a byte: a file that is short, too long, has a wrong checksum, the
 * wrong build, an index past the menu or a data length that is not a record leaves the presets of the firmware.
 */
import { crc32 } from "./script/blob.mjs";
import { RECORD, recordOf, locatePresets } from "./presets.mjs";
import { TABLES } from "./map/index.mjs";
import { locateModTable, writeModType } from "./modtable.mjs";
import { buildOf } from "./firmware.mjs";
import { fxText, fxToRecord } from "./fx-v2.mjs";
import { FxRecord } from "./record.mjs";
import { lint } from "./rules.mjs";

export const COLLECTION_FILE = "e2sFx.all";
export const COLLECTION_FOLDER = "KORG/blechtribe/Presets";
export const COLLECTION_MAGIC = 0x41584647;       // "GFXA" little-endian
export const COLLECTION_VERSION = 1;
export const HEADER_SIZE = 24;
export const ENTRY_HEAD = 8;
export const MAX_TEXT = 0x2000;
export const BUILDS = { hacktribe: 1, stock: 2 };
export const KIND = { ifx: 1, mfx: 2, mod: 3 };
export const MOD_RECORD = TABLES.get("table.modType").stride;
export const MOD_COUNT = TABLES.get("table.modType").count;
const DATA = { 1: RECORD, 2: RECORD, 3: MOD_RECORD };
const KIND_NAME = Object.fromEntries(Object.entries(KIND).map(([k, v]) => [v, k]));

/**
 * @param {{build: string, entries: {kind: "ifx"|"mfx"|"mod", index: number, data: Uint8Array, text: string}[]}} c
 * @returns {Uint8Array}
 */
export function buildCollection({ build, entries }) {
  if (!(build in BUILDS)) throw new Error(`no collection for the build ${build}`);
  const parts = entries.map(e => {
    const kind = KIND[e.kind];
    if (!kind) throw new Error(`unknown kind ${e.kind}`);
    if (e.data.length !== DATA[kind]) throw new Error(`${e.kind} ${e.index}: ${e.data.length} bytes, a record has ${DATA[kind]}`);
    if (!Number.isInteger(e.index) || e.index < 0 || e.index > (kind === 3 ? MOD_COUNT - 1 : 255)) throw new Error(`index ${e.index} is out of range`);
    const text = new TextEncoder().encode(e.text);
    if (text.length > MAX_TEXT) throw new Error(`the text of ${e.kind} ${e.index} is longer than ${MAX_TEXT} bytes`);
    const size = (ENTRY_HEAD + e.data.length + text.length + 3) & ~3;
    const out = new Uint8Array(size);
    const view = new DataView(out.buffer);
    out[0] = kind;
    out[1] = e.index;
    view.setUint16(2, text.length, true);
    view.setUint16(4, e.data.length, true);
    out.set(e.data, ENTRY_HEAD);
    out.set(text, ENTRY_HEAD + e.data.length);
    return out;
  });
  const total = HEADER_SIZE + parts.reduce((n, p) => n + p.length, 0);
  const file = new Uint8Array(total);
  let at = HEADER_SIZE;
  for (const p of parts) { file.set(p, at); at += p.length; }
  const view = new DataView(file.buffer);
  view.setUint32(0, COLLECTION_MAGIC, true);
  view.setUint16(4, COLLECTION_VERSION, true);
  view.setUint16(6, entries.length, true);
  view.setUint32(8, total, true);
  view.setUint32(12, crc32(file, HEADER_SIZE, total), true);
  view.setUint32(16, BUILDS[build], true);
  return file;
}

/**
 * The entries of a collection, by the same rules the firmware applies. `counts` (ifx, mfx) are the menu lengths of
 * the firmware the file is for; without them the index is only checked against what a byte can hold.
 * @returns {{ok: true, build: string, entries: {kind: string, index: number, data: Uint8Array, text: string}[]} | {ok: false, reason: string}}
 */
export function parseCollection(bytes, { counts = null } = {}) {
  if (bytes.length < HEADER_SIZE) return { ok: false, reason: "Die Sammeldatei ist zu kurz." };
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (view.getUint32(0, true) !== COLLECTION_MAGIC) return { ok: false, reason: "Das ist keine Sammeldatei für Effekte." };
  if (view.getUint16(4, true) !== COLLECTION_VERSION) return { ok: false, reason: "Diese Version der Sammeldatei kennt die Seite nicht." };
  const total = view.getUint32(8, true);
  if (total !== bytes.length) return { ok: false, reason: "Die Sammeldatei ist nicht vollständig." };
  if (crc32(bytes, HEADER_SIZE, total) !== view.getUint32(12, true)) return { ok: false, reason: "Die Prüfsumme der Sammeldatei stimmt nicht." };
  const build = Object.keys(BUILDS).find(k => BUILDS[k] === view.getUint32(16, true));
  if (!build) return { ok: false, reason: "Die Sammeldatei ist für eine unbekannte Firmware." };
  const entries = [];
  let at = HEADER_SIZE;
  for (let i = 0; i < view.getUint16(6, true); i++) {
    if (at + ENTRY_HEAD > total) return { ok: false, reason: "Ein Eintrag der Sammeldatei ist abgeschnitten." };
    const kind = bytes[at];
    const index = bytes[at + 1];
    const textLength = view.getUint16(at + 2, true);
    const dataLength = view.getUint16(at + 4, true);
    if (!DATA[kind] || dataLength !== DATA[kind] || textLength > MAX_TEXT) return { ok: false, reason: `Eintrag ${i + 1} der Sammeldatei ist kein Preset und keine Modulation.` };
    const limit = kind === 3 ? MOD_COUNT : counts?.[KIND_NAME[kind]] ?? 256;
    if (index >= limit) return { ok: false, reason: `Eintrag ${i + 1} zeigt auf Platz ${index + 1}, die Firmware hat ${limit}.` };
    const size = (ENTRY_HEAD + dataLength + textLength + 3) & ~3;
    if (at + size > total) return { ok: false, reason: "Ein Eintrag der Sammeldatei ist abgeschnitten." };
    const data = bytes.slice(at + ENTRY_HEAD, at + ENTRY_HEAD + dataLength);
    const text = new TextDecoder().decode(bytes.subarray(at + ENTRY_HEAD + dataLength, at + ENTRY_HEAD + dataLength + textLength));
    entries.push({ kind: KIND_NAME[kind], index, data, text });
    at += size;
  }
  if (at !== total) return { ok: false, reason: "Die Sammeldatei hat Bytes hinter dem letzten Eintrag." };
  return { ok: true, build, entries };
}

/**
 * One entry for the firmware in `vsb` (the user's SYSTEM.VSB): the preset written over what that firmware has at
 * `index` (0-based), or the modulation type over the type at `index`.
 * @returns {{ok: true, entry: object} | {ok: false, reason: string}}
 */
/** What the user can free on purpose (Baukasten, "Gesperrte Bausteine freigeben"): the measured bad block combinations. */
const RISKY_CODES = new Set(["stage2-fatal", "stage2-silent", "stage1-needs-solo"]);

/** @param {{risky?: boolean}} [options] risky: let the measured bad block combinations through, the rest stays barred */
export function collectionEntry(preset, vsb, index, units, { risky = false } = {}) {
  const build = buildOf(vsb);
  if (!(build in BUILDS)) return { ok: false, reason: "Die Sammeldatei gibt es für den roten Sampler, mit Korgs Firmware oder mit Hacktribe." };
  if (preset.kind === "mod") {
    const table = locateModTable(vsb);
    if (!table.ok) return { ok: false, reason: table.reasons[0] };
    if (index < 0 || index >= MOD_COUNT) return { ok: false, reason: `Modulation ${index + 1} gibt es nicht, es sind ${MOD_COUNT}.` };
    const data = vsb.slice(table.file + index * MOD_RECORD, table.file + (index + 1) * MOD_RECORD);
    try {
      writeModType(data, 0, 0, { name: preset.name, depth: preset.depth, speed: preset.speed, curve: preset.curve, slots: preset.slots });
    } catch (e) {
      return { ok: false, reason: e.message };
    }
    return { ok: true, entry: { kind: "mod", index, data, text: fxText(preset) } };
  }
  const where = locatePresets(vsb)?.[preset.kind];
  const at = recordOf(vsb, preset.kind, index + 1);
  if (!where || !at) return { ok: false, reason: `Platz ${index + 1} gibt es in dieser Firmware nicht.` };
  const records = Array.from({ length: where.capacity }, (_, i) => recordOf(vsb, preset.kind, i + 1)).map(r => vsb.slice(r.file, r.file + RECORD));
  const made = fxToRecord(preset, vsb.slice(at.file, at.file + RECORD), records, units);
  if (!made.ok) return made;
  // The Türsteher's rules (src/rules.mjs), as for a live write: what crashes the device, stays silent or is broken
  // does not go on the card either, where it would load at every start.
  const bad = lint(new FxRecord(made.record, preset.kind), { units }).find(f => ["fatal", "silent", "error"].includes(f.severity) && !(risky && RISKY_CODES.has(f.code)));
  if (bad) return { ok: false, reason: `Vom Türsteher gesperrt: ${bad.message}${RISKY_CODES.has(bad.code) ? " Mit „Gesperrte Bausteine freigeben (RISIKO)“ bei der Wahl des Bausteins geht es trotzdem." : ""}` };
  return { ok: true, entry: { kind: preset.kind, index, data: made.record, text: fxText(preset) } };
}
