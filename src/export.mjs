/**
 * The firmware edits of a sitting, listed field by field and applied to a
 * copy of the user's own SYSTEM.VSB (plan 4.1, 4.2). Nothing here flashes
 * anything; the result is a file for the user to keep or try.
 *
 * Only edits that live in the firmware image count: effect records and
 * menu lengths. A pattern lives in pattern memory and is listed as skipped.
 */
import { field, fieldsOf, instances, offsetOf, readRaw, typeOf, applies, sitesOf, describe } from "./map/index.mjs";
import { tableEntry, ramToFile } from "./map/address.mjs";
import { identify, identifyBase } from "./firmware.mjs";
import { presetRoom, presetSpans, RECORD } from "./presets.mjs";
import { locateModTable, readModType, writeModType, modFieldSpans, MOD_FIELDS, SLOT_FIELDS, SLOT_COUNT, MOD_COUNT } from "./modtable.mjs";

const RECORD_FIELDS = fieldsOf("fxRecord");

const show = (f, raw) => describe(f, raw)?.text ?? (raw instanceof Uint8Array ? Array.from(raw, b => b.toString(16).padStart(2, "0")).join(" ") : String(raw));
const same = (a, b) => (a instanceof Uint8Array ? a.length === b.length && a.every((x, i) => x === b[i]) : a === b);

/** Field-by-field differences of two records; changed bytes no field explains are listed by offset. */
export function recordChanges(before, after) {
  const changed = new Set();
  for (let i = 0; i < after.length; i++) if (before[i] !== after[i]) changed.add(i);
  const out = [];
  const covered = new Set();
  for (const f of RECORD_FIELDS) {
    const width = typeOf(f).width;
    for (const ix of instances(f)) {
      if (f.when && !applies(after, f, ix) && !applies(before, f, ix)) continue;
      const at = offsetOf(f, ix);
      let touched = false;
      for (let k = at; k < at + width; k++) if (changed.has(k)) touched = true;
      if (!touched) continue;
      const old = readRaw(before, f, ix);
      const now = readRaw(after, f, ix);
      for (let k = at; k < at + width; k++) covered.add(k);
      if (same(old, now)) continue;
      out.push({ field: f.id, label: f.label.de, indices: ix, old: show(f, old), new: show(f, now) });
    }
  }
  for (const k of [...changed].sort((a, b) => a - b)) {
    if (!covered.has(k)) out.push({ field: null, label: `Byte +0x${k.toString(16)}`, indices: [], old: String(before[k]), new: String(after[k]) });
  }
  return out;
}

/**
 * What each live edit of a session changed, oldest first. `history` is
 * DeviceSession.history: what was undone is no longer in it.
 */
export function sessionChanges(history) {
  return history.map(({ edit, backups }) => {
    if (edit.kind === "fxRecord") {
      const before = backups?.[0]?.bytes ?? edit.before;
      return { target: `${edit.table === "ifx" ? "IFX" : "MFX"} ${edit.slot}`, firmware: true, fields: before ? recordChanges(before, edit.bytes) : [] };
    }
    if (edit.kind === "sites" || edit.kind === "immediate") {
      const f = field(edit.fieldId);
      const old = backups?.[0]?.bytes?.[0];
      return { target: f.label.de, firmware: true, fields: [{ field: f.id, label: f.label.de, indices: [], old: old === undefined ? "?" : show(f, old), new: show(f, edit.value) }] };
    }
    return { target: edit.kind.startsWith("pattern") ? "Pattern-Puffer" : edit.kind, firmware: false, fields: [] };
  });
}

/**
 * The user's VSB with every firmware edit of the session written in, at the
 * file addresses of the device map. Refused when the copy no longer passes
 * the firmware check.
 * @returns {Promise<{ok: boolean, bytes?: Uint8Array, reasons?: string[], applied: number, skipped: number}>}
 */
export async function exportVsb(vsb, history) {
  const bytes = Uint8Array.from(vsb);
  let applied = 0;
  let skipped = 0;
  for (const { edit } of history) {
    if (edit.kind === "fxRecord") {
      const entry = edit.ram === undefined ? tableEntry(`table.${edit.table}`, edit.slot - 1) : { file: ramToFile(edit.ram), size: RECORD };
      if (edit.bytes.length !== entry.size) throw new RangeError(`${edit.table} ${edit.slot}: a record is ${entry.size} bytes`);
      bytes.set(edit.bytes, entry.file);
      applied++;
    } else if (edit.kind === "sites" || edit.kind === "immediate") {
      const f = field(edit.fieldId);
      for (const s of f.sites ? sitesOf(f, edit.value) : [{ offset: f.where.offset, value: edit.value }]) bytes[s.offset] = s.value;
      applied++;
    } else {
      skipped++;
    }
  }
  const stock = history.some(({ edit }) => edit.kind === "fxRecord" && edit.ram !== undefined);
  const id = stock ? await identifyBase(bytes) : await identify(bytes);
  if (!(stock ? id.ok : id.known)) return { ok: false, reasons: id.reasons, applied, skipped };
  return { ok: true, bytes, applied, skipped };
}

/**
 * The user's VSB with an edited set of FX presets: records written, presets added, menu lengths raised. Only the bytes
 * src/presets.mjs says a preset edit may touch are allowed to differ; the result has to be an image whose arrays and menus
 * still make sense. `allow` and `allowCode` are the changed bytes as [file offset, length] runs, for the emulator check
 * (data the firmware reads at start, and the immediates of the menu lengths, which are code it runs at start).
 * @returns {Promise<{ok: boolean, bytes?: Uint8Array, reasons?: string[], changed: number, allow: number[][], allowCode: number[][]}>}
 */
export async function exportPresets(original, edited) {
  const fail = reasons => ({ ok: false, reasons, changed: 0, allow: [], allowCode: [] });
  if (original.length !== edited.length) return fail(["Die Datei hat eine andere Größe."]);
  const spans = presetSpans(original);
  const after = presetSpans(edited);
  if (!spans || !after) return fail(["Die Preset-Tabellen dieser Datei sind nicht erkannt."]);
  const within = (list, at) => list.some(([file, length]) => at >= file && at < file + length);
  const allowed = [...spans.data, ...after.data];
  const allow = [];
  const allowCode = [];
  let changed = 0;
  for (let at = 0; at < original.length; at++) {
    if (original[at] === edited[at]) continue;
    const code = within(spans.code, at);
    if (!code && !within(allowed, at)) return fail([`Byte 0x${at.toString(16)} liegt außerhalb der Presets und wird nicht angefasst.`]);
    const runs = code ? allowCode : allow;
    const last = runs[runs.length - 1];
    if (last && last[0] + last[1] === at) last[1]++;
    else runs.push([at, 1]);
    changed++;
  }
  for (const kind of ["ifx", "mfx"]) {
    const room = presetRoom(edited, kind);
    if (!room.agreed) return fail([`Die Stellen der ${kind === "ifx" ? "Insert" : "Master"}-Menülänge sind sich nicht einig.`]);
    if (room.count < 1 || room.count > room.capacity) return fail([`Die Menülänge ${room.count} passt nicht zur Tabelle (${room.capacity} Plätze).`]);
  }
  const base = await identifyBase(edited);
  if (!base.ok) return fail(base.reasons);
  return { ok: true, bytes: Uint8Array.from(edited), changed, allow, allowCode };
}

/**
 * The user's VSB with edited modulation types written into the copy of the table the firmware reads
 * (locateModTable), and nowhere else. Only the fields of the editor move (name, default depth and speed, curve, and
 * the five fields of slots 0 to 4); every other byte of every entry, known or not, the target label and the other copy stay as they are. Refused when no single copy is
 * read, a value does not fit its field, or the result no longer passes the firmware check.
 * `types` is all 72 entries in the shape of readModTypes; entries equal to the file are not written, and a changed
 * `target` is refused.
 * `allow` is the changed bytes as [file offset, length] runs, for the emulator check.
 * @returns {Promise<{ok: boolean, bytes?: Uint8Array, reasons?: string[], changed: number, allow: number[][], file?: number, place?: string}>}
 */
export async function exportModTypes(vsb, types) {
  const found = locateModTable(vsb);
  if (!found.ok) return { ok: false, reasons: found.reasons, changed: 0, allow: [] };
  if (!Array.isArray(types) || types.length !== MOD_COUNT) throw new TypeError(`${MOD_COUNT} modulation types expected`);
  const bytes = Uint8Array.from(vsb);
  let changed = 0;
  for (let i = 0; i < MOD_COUNT; i++) {
    const now = readModType(vsb, found.file, i);
    const want = types[i];
    if (want.target !== now.target) return { ok: false, reasons: [`Modulationsart ${i + 1}: das Ziel ist nur ein Etikett, die Firmware liest es nie, der Editor schreibt es nicht.`], changed, allow: [] };
    const diff = Object.fromEntries(Object.keys(MOD_FIELDS).filter(k => want[k] !== now[k]).map(k => [k, want[k]]));
    const slots = Array.from({ length: SLOT_COUNT }, (_, k) => Object.fromEntries(Object.keys(SLOT_FIELDS).filter(key => want.slots?.[k]?.[key] !== now.slots[k][key]).map(key => [key, want.slots[k][key]])));
    if (slots.some(s => Object.keys(s).length)) diff.slots = slots;
    if (!Object.keys(diff).length) continue;
    try {
      writeModType(bytes, found.file, i, diff);
    } catch (e) {
      return { ok: false, reasons: [`Modulationsart ${i + 1}: ${e.message}`], changed, allow: [] };
    }
    changed++;
  }
  const inFields = new Set(Array.from({ length: MOD_COUNT }, (_, i) => modFieldSpans(found.file, i)).flat()
    .flatMap(([at, n]) => Array.from({ length: n }, (_, k) => at + k)));
  const allow = [];
  for (let at = 0; at < bytes.length; at++) {
    if (bytes[at] === vsb[at]) continue;
    if (!inFields.has(at)) return { ok: false, reasons: [`Byte 0x${at.toString(16)} liegt außerhalb der Felder der Modulationsarten und wird nicht angefasst.`], changed, allow: [] };
    const last = allow[allow.length - 1];
    if (last && last[0] + last[1] === at) last[1]++;
    else allow.push([at, 1]);
  }
  const after = locateModTable(bytes);
  if (!after.ok || after.file !== found.file) {
    return { ok: false, reasons: ["Nach den Änderungen liest die Firmware die Modulationstabelle nicht mehr von derselben Stelle."], changed, allow };
  }
  const id = await identify(bytes);
  if (!id.known) return { ok: false, reasons: id.reasons, changed, allow };
  return { ok: true, bytes, changed, allow, file: found.file, place: found.place };
}
