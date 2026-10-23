/**
 * .e2fx version 2: one FX preset or one modulation type as plain values, the same on every build. A preset is its
 * kind, its name, the building block (DSP unit) of each stage by its id with the parameters by name, and the control
 * map; a modulation type is its name, default depth and speed, curve and five slots. No byte of the firmware is in it.
 *
 * Turning it into the bytes a firmware uses goes through a record of that firmware (docs/patcher.md, "Records are
 * edited, never built"): the record already at the slot, and for a stage whose building block differs, a record of
 * the same firmware that has that block in the same stage. A block no record of the firmware carries takes the stage
 * block most records of that stage share, with only the device byte changed (factory-check:stage-block-shared).
 */
import { FxRecord } from "./record.mjs";
import { REC, STAGE_BLOCK_SIZE } from "./layout.mjs";
import { unitFor } from "./units.mjs";
import { crc32 } from "./script/blob.mjs";
import { readPresetFile, PRESET_EXT } from "./preset-file.mjs";
import { SLOT_COUNT } from "./modtable.mjs";

export const FX_FORMAT = "gelumpe-fx";
export const FX_VERSION = 2;
export { PRESET_EXT };

const KINDS = ["ifx", "mfx", "mod"];
const unitKind = stage => (stage === "mfx" ? "mfx" : "ifx");
const utf8 = text => new TextEncoder().encode(text);

/** The values without the checksum, in a fixed order, so the same preset always gives the same text and CRC. */
function canonical(preset) {
  if (preset.kind === "mod") {
    return {
      format: FX_FORMAT, version: FX_VERSION, kind: "mod", name: preset.name,
      depth: preset.depth, speed: preset.speed, curve: preset.curve,
      slots: preset.slots.map(s => ({ source: s.source, target: s.target, lo: s.lo, hi: s.hi, follow: s.follow })),
    };
  }
  return {
    format: FX_FORMAT, version: FX_VERSION, kind: preset.kind, name: preset.name,
    stages: preset.stages.map(s => ({ stage: s.stage, unit: s.unit, unitName: s.unitName ?? null, params: { ...s.params } })),
    map: (preset.map ?? []).map(m => ({ source: m.source, chain: m.chain, param: m.param, low: m.low, high: m.high })),
  };
}

const checksum = preset => crc32(utf8(JSON.stringify(canonical(preset))));

/** The file text of a v2 preset or modulation type. */
export function fxText(preset) {
  return `${JSON.stringify({ ...canonical(preset), crc32: checksum(preset) }, null, 1)}\n`;
}

/** An FX record (bytes of a firmware) as v2 values. `units` comes from src/units.mjs. */
export function fxFromRecord(record, kind, units) {
  const rec = record instanceof FxRecord ? record : new FxRecord(record, kind);
  return {
    kind: rec.kind,
    name: rec.name,
    stages: rec.stageNames.map(stage => {
      const unit = unitFor(units, unitKind(stage), rec.device(stage));
      return { stage, unit: rec.device(stage), unitName: unit?.unit ?? null, params: Object.fromEntries(rec.params(units, stage).map(p => [p.name, p.value])) };
    }),
    map: rec.map.map(({ source, chain, param, low, high }) => ({ source, chain, param, low, high })),
  };
}

/** A modulation type (src/modtable.mjs readModType) as v2 values. */
export const modFromType = type => ({ kind: "mod", name: type.name, depth: type.depth, speed: type.speed, curve: type.curve, slots: type.slots.map(s => ({ ...s })) });

const byte = v => Number.isInteger(v) && v >= 0 && v <= 255;
const signed = v => Number.isInteger(v) && v >= -128 && v <= 127;      // a slot's strength (lo, hi) is s8 in the table

/**
 * The preset in a file, or why it is not one. A version 1 file (the raw record, src/preset-file.mjs) is turned into v2
 * with the unit table, so both come out the same.
 * @returns {{ok: true, preset: object} | {ok: false, reason: string}}
 */
export function readFx(text, units) {
  let data;
  try { data = JSON.parse(text); } catch { return { ok: false, reason: "Die Datei ist kein Effekt (kein JSON)." }; }
  if (data?.format === "gelumpe-fx-preset") {
    const v1 = readPresetFile(text);
    return v1.ok ? { ok: true, preset: fxFromRecord(v1.record, v1.kind, units) } : v1;
  }
  if (data?.format !== FX_FORMAT) return { ok: false, reason: "Die Datei ist kein GELUMPE-Effekt." };
  if (data.version !== FX_VERSION) return { ok: false, reason: `Effekt-Format Version ${data.version} kennt diese Seite nicht.` };
  if (!KINDS.includes(data.kind)) return { ok: false, reason: "Die Datei sagt nicht, ob sie ein Insert-, Master-Effekt oder eine Modulation ist." };
  if (typeof data.name !== "string") return { ok: false, reason: "Der Effekt hat keinen Namen." };
  if (data.kind === "mod") {
    if (!byte(data.depth) || !byte(data.speed) || !byte(data.curve) || !Array.isArray(data.slots) || data.slots.length > SLOT_COUNT
        || data.slots.some(s => !["source", "target", "follow"].every(k => byte(s?.[k])) || !signed(s.lo) || !signed(s.hi))) {
      return { ok: false, reason: "Die Werte der Modulation sind unvollständig." };
    }
  } else {
    const want = data.kind === "mfx" ? ["mfx"] : ["ifx1", "ifx2"];
    if (!Array.isArray(data.stages) || data.stages.length !== want.length || data.stages.some((s, i) => s?.stage !== want[i] || !byte(s.unit) || typeof s.params !== "object" || !Object.values(s.params).every(byte))) {
      return { ok: false, reason: "Die Bausteine des Effekts sind unvollständig." };
    }
    if (!Array.isArray(data.map) || data.map.some(m => !["source", "chain", "param", "low", "high"].every(k => byte(m?.[k])))) {
      return { ok: false, reason: "Die Steuerung des Effekts ist unvollständig." };
    }
  }
  if (checksum(data) !== data.crc32) return { ok: false, reason: "Die Prüfsumme stimmt nicht, die Datei ist beschädigt." };
  return { ok: true, preset: canonical(data) };
}

/**
 * The record carrying the stage block most records share at `stage`, leaving out the device byte and the parameter
 * values: the donor for a building block that sits in no record of the firmware. Null when no record uses the stage.
 */
function sharedBlock(records, kind, stage) {
  const { device: at, params } = REC.stage[stage];
  const groups = new Map();
  for (const bytes of records) {
    if (!bytes[at]) continue;
    const rest = bytes.slice(at, at + STAGE_BLOCK_SIZE);
    rest[0] = 0;
    for (let i = params - at; i < rest.length; i += 2) rest[i] = 0;
    const key = rest.join(",");
    const group = groups.get(key) ?? { count: 0, bytes };
    group.count++;
    groups.set(key, group);
  }
  const best = [...groups.values()].sort((a, b) => b.count - a.count)[0];
  return best ? new FxRecord(best.bytes, kind) : null;
}

/**
 * The record for slot `base` (the bytes the firmware has there now) with the preset written into it. `records` are
 * all records of the same kind in that firmware, the donors for a stage whose building block differs.
 * @returns {{ok: true, record: Uint8Array} | {ok: false, reason: string}}
 */
export function fxToRecord(preset, base, records, units) {
  const rec = new FxRecord(base, preset.kind);
  for (const s of preset.stages) {
    const unit = unitFor(units, unitKind(s.stage), s.unit);
    if (!unit) return { ok: false, reason: `Den Baustein ${s.unitName ?? s.unit} kennt diese Seite nicht.` };
    if (rec.device(s.stage) !== s.unit) {
      const donor = records.map(r => new FxRecord(r, preset.kind)).find(r => r.device(s.stage) === s.unit) ?? sharedBlock(records, preset.kind, s.stage);
      if (!donor) return { ok: false, reason: `In dieser Firmware steht an dieser Stelle in keinem Preset ein Baustein. Ohne ein solches Preset lässt sich ${unit.unit} nicht einsetzen.` };
      rec.adoptStage(s.stage, donor);
      rec.setDevice(s.stage, s.unit);
    }
    const missing = Object.keys(s.params).find(name => !unit.params.some(p => p.name === name));
    if (missing) return { ok: false, reason: `Der Baustein ${unit.unit} hat keinen Parameter ${missing}.` };
    rec.setParams(units, s.stage, s.params);
  }
  rec.name = preset.name;
  // A new control row copies a used one where there is any; the firmware's own presets nearly always have some.
  if (preset.map.length > rec.map.length) rec.growMap(preset.map.length, records.map(r => new FxRecord(r, preset.kind)).find(r => r.map.length));
  rec.map = preset.map;
  return { ok: true, record: rec.bytes };
}

/** A file name for the preset: its name with every character a card or a mail would trip over as "-". */
export const fxFileName = preset => `${(preset.name || preset.kind).replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || preset.kind}${PRESET_EXT}`;
