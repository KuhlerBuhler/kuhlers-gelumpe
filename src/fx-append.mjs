/**
 * Ready effects written behind the presets the firmware has, at patch time (data/patches/fx-catalog.json, made by
 * tools/fx-catalog-patch.mjs). Each record is a copy of a record of the user's own firmware with the preset written
 * into it, so the patch carries no firmware bytes. The slots depend on how many presets the firmware has already:
 * the writes stay userData and are left out of `spans`, so the patch file's fingerprints do not depend on them.
 * With `first` ({ifx, mfx}) the patch also says where its presets go: one after the other from that slot, so Korg's 2.02
 * and Hacktribe have them on the same slots. A preset marked `hacktribe` is a remake of one Hacktribe has as its own:
 * Hacktribe keeps its own, found by name on that very slot.
 */
import { addPreset, locatePresets, menuLength, presetSpans, recordOf, RECORD } from "./presets.mjs";
import { FxRecord } from "./record.mjs";
import { fxToRecord } from "./fx-v2.mjs";
import { parseUnits } from "./units.mjs";

export const APPEND_FORMAT = "gelumpe-fx-append";

const nameOf = (bytes, kind, slot) => {
  const r = recordOf(bytes, kind, slot);
  return new FxRecord(bytes.slice(r.file, r.file + RECORD), kind).name;
};
const names = (bytes, kind) => Array.from({ length: menuLength(bytes, kind).value }, (_, i) => nameOf(bytes, kind, i + 1));
/** The name as the record keeps it, cut to the display. */
const shown = preset => {
  const r = new FxRecord(new Uint8Array(RECORD), preset.kind);
  r.name = preset.name;
  return r.name;
};

/** The records the menu holds for the presets of the patch, by name: [{kind, name, record}]. */
export function appendedRecords(bytes, patch) {
  if (!locatePresets(bytes)) return [];
  return patch.presets.flatMap(p => {
    const i = names(bytes, p.kind).indexOf(shown(p));
    if (i < 0) return [];
    const r = recordOf(bytes, p.kind, i + 1);
    return [{ kind: p.kind, name: shown(p), record: bytes.subarray(r.file, r.file + RECORD), hacktribe: Boolean(p.hacktribe) }];
  });
}

/** Whether every preset of the patch is in the menu already, by name. */
export function appendPresent(bytes, patch) {
  return Boolean(locatePresets(bytes)) && patch.presets.every(p => names(bytes, p.kind).includes(shown(p)));
}

/**
 * The presets of an append patch behind the last slot of each menu, in a copy of `bytes`. A preset whose name the
 * menu has already is left out, so applying twice adds nothing. With the patch's `first`, a slot that holds another
 * preset of the patch (an older release put the catalog in another order) gets the one that belongs there; a slot
 * with anything else ends the fixed order for that kind, and the rest goes behind the last slot as before.
 * @returns {{ok: boolean, bytes?: Uint8Array, added: {kind: string, slot: number, name: string}[], allow: number[][], allowCode: number[][], reasons: string[]}}
 */
export function appendPresets(bytes, patch, { refresh = null } = {}) {
  const none = reasons => ({ ok: false, added: [], allow: [], allowCode: [], reasons });
  if (patch?.format !== APPEND_FORMAT || patch.version !== 1 || !Array.isArray(patch.presets)) return none([`${patch?.id ?? "?"}: kein Patch im Format ${APPEND_FORMAT} 1`]);
  if (!locatePresets(bytes)) return none([`${patch.id}: Die Preset-Tabellen dieser Datei sind nicht erkannt.`]);
  const units = parseUnits(patch.units ?? {});
  let out = bytes;
  const added = [];
  const next = { ...(patch.first ?? {}) };
  const ours = kind => new Set(patch.presets.filter(p => p.kind === kind).map(shown));
  const rebuild = (preset, slot) => {
    const at = recordOf(out, preset.kind, slot);
    const capacity = locatePresets(out)[preset.kind].capacity;
    const records = Array.from({ length: capacity }, (_, i) => recordOf(out, preset.kind, i + 1)).map(r => out.slice(r.file, r.file + RECORD));
    const made = fxToRecord(preset, records[0], records, units);
    if (!made.ok) return made;
    out = Uint8Array.from(out);
    out.set(made.record, at.file);
    added.push({ kind: preset.kind, slot, name: shown(preset) });
    return made;
  };
  for (const preset of patch.presets) {
    if (preset.kind !== "ifx" && preset.kind !== "mfx") return none([`${patch.id}: ${preset.name} ist kein Insert- oder Master-Preset`]);
    const has = names(out, preset.kind).indexOf(shown(preset));
    const want = next[preset.kind] ? next[preset.kind]++ : 0;
    if (want && has + 1 !== want && want <= menuLength(out, preset.kind).value) {
      if (ours(preset.kind).has(nameOf(out, preset.kind, want))) {
        const made = rebuild(preset, want);
        if (!made.ok) return none([`${patch.id}, ${preset.name}: ${made.reason}`]);
        continue;
      }
      next[preset.kind] = 0;
    }
    const at = has >= 0 ? recordOf(out, preset.kind, has + 1) : null;
    if (at && refresh?.(preset.kind, shown(preset), out.subarray(at.file, at.file + RECORD))) {
      const capacity = locatePresets(out)[preset.kind].capacity;
      const records = Array.from({ length: capacity }, (_, i) => recordOf(out, preset.kind, i + 1)).map(r => out.slice(r.file, r.file + RECORD));
      const made = fxToRecord(preset, records[0], records.slice(0, has + 1), units);
      if (!made.ok) return none([`${patch.id}, ${preset.name}: ${made.reason}`]);
      out = Uint8Array.from(out);
      out.set(made.record, at.file);
      added.push({ kind: preset.kind, slot: has + 1, name: shown(preset) });
      continue;
    }
    if (has >= 0) continue;
    const slot = addPreset(out, preset.kind, 1);
    if (!slot.ok) return none(slot.reasons.map(r => `${patch.id}, ${preset.name}: ${r}`));
    const capacity = locatePresets(slot.bytes)[preset.kind].capacity;
    const records = Array.from({ length: capacity }, (_, i) => recordOf(slot.bytes, preset.kind, i + 1))
      .map(r => slot.bytes.slice(r.file, r.file + RECORD));
    const made = fxToRecord(preset, slot.bytes.slice(slot.file, slot.file + RECORD), records, units);
    if (!made.ok) return none([`${patch.id}, ${preset.name}: ${made.reason}`]);
    slot.bytes.set(made.record, slot.file);
    out = slot.bytes;
    added.push({ kind: preset.kind, slot: slot.slot, name: shown(preset) });
  }
  const spans = presetSpans(out);
  return { ok: true, bytes: out, added, allow: added.length ? spans.data : [], allowCode: added.length ? spans.code : [], reasons: [] };
}
