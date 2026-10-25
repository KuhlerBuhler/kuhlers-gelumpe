/**
 * Ready effects written behind the presets the firmware has, at patch time (data/patches/fx-catalog.json, made by
 * tools/fx-catalog-patch.mjs). Each record is a copy of a record of the user's own firmware with the preset written
 * into it, so the patch carries no firmware bytes. The slots depend on how many presets the firmware has already:
 * the writes stay userData and are left out of `spans`, so the patch file's fingerprints do not depend on them.
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

/** Whether every preset of the patch is in the menu already, by name. */
export function appendPresent(bytes, patch) {
  return Boolean(locatePresets(bytes)) && patch.presets.every(p => names(bytes, p.kind).includes(shown(p)));
}

/**
 * The presets of an append patch behind the last slot of each menu, in a copy of `bytes`. A preset whose name the
 * menu has already is left out, so applying twice adds nothing.
 * @returns {{ok: boolean, bytes?: Uint8Array, added: {kind: string, slot: number, name: string}[], allow: number[][], allowCode: number[][], reasons: string[]}}
 */
export function appendPresets(bytes, patch) {
  const none = reasons => ({ ok: false, added: [], allow: [], allowCode: [], reasons });
  if (patch?.format !== APPEND_FORMAT || patch.version !== 1 || !Array.isArray(patch.presets)) return none([`${patch?.id ?? "?"}: kein Patch im Format ${APPEND_FORMAT} 1`]);
  if (!locatePresets(bytes)) return none([`${patch.id}: Die Preset-Tabellen dieser Datei sind nicht erkannt.`]);
  const units = parseUnits(patch.units ?? {});
  let out = bytes;
  const added = [];
  for (const preset of patch.presets) {
    if (preset.kind !== "ifx" && preset.kind !== "mfx") return none([`${patch.id}: ${preset.name} ist kein Insert- oder Master-Preset`]);
    if (names(out, preset.kind).includes(shown(preset))) continue;
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
