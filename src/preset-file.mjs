/**
 * One FX preset as a file of its own (.e2fx), to pass a preset on: a short JSON with the kind, the name and the record
 * (0x20C bytes, hex) and a CRC-32 over the record. It holds what the user built, nothing of the firmware's code; on
 * import it becomes a new slot of the user's own file, and the copy goes through the emulator check like every other edit.
 */
import { RECORD } from "./presets.mjs";
import { crc32 } from "./script/blob.mjs";
import { FxRecord } from "./record.mjs";

export const PRESET_FORMAT = "gelumpe-fx-preset";
export const PRESET_EXT = ".e2fx";

const hex = bytes => Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");

/** The file text for a record of `kind` ("ifx" or "mfx"). */
export function presetFile(kind, record) {
  const rec = new FxRecord(record, kind);
  return `${JSON.stringify({ format: PRESET_FORMAT, version: 1, kind, name: rec.name, crc32: crc32(rec.bytes), record: hex(rec.bytes) }, null, 1)}\n`;
}

/** A file name for the preset: its name with every character a card or a mail would trip over as "-". */
export const presetFileName = (kind, name) => `${(name || kind).replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || kind}${PRESET_EXT}`;

/**
 * The preset in a file, or why it is not one.
 * @returns {{ok: true, kind: string, name: string, record: Uint8Array} | {ok: false, reason: string}}
 */
export function readPresetFile(text) {
  let data;
  try { data = JSON.parse(text); } catch { return { ok: false, reason: "Die Datei ist kein Preset (kein JSON)." }; }
  if (!data || data.format !== PRESET_FORMAT) return { ok: false, reason: "Die Datei ist kein GELUMPE-Preset." };
  if (data.version !== 1) return { ok: false, reason: `Preset-Format Version ${data.version} kennt diese Seite nicht.` };
  if (data.kind !== "ifx" && data.kind !== "mfx") return { ok: false, reason: "Das Preset sagt nicht, ob es ein Insert- oder ein Master-Effekt ist." };
  if (typeof data.record !== "string" || !/^[0-9a-f]+$/i.test(data.record) || data.record.length !== 2 * RECORD) return { ok: false, reason: "Der Datensatz des Presets hat nicht die Länge eines Presets." };
  const record = Uint8Array.from(data.record.match(/../g), h => parseInt(h, 16));
  if (crc32(record) !== data.crc32) return { ok: false, reason: "Die Prüfsumme des Presets stimmt nicht, die Datei ist beschädigt." };
  return { ok: true, kind: data.kind, name: new FxRecord(record, data.kind).name, record };
}
