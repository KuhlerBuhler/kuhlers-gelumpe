/**
 * What the factory presets actually do with each parameter.
 *
 * Korg's own presets are the only ground truth available for "is this value
 * sane". A parameter that never leaves 32 to 36 across every factory preset
 * is telling you something, and a value of 95 in that slot is worth a second
 * look even though the byte is perfectly legal.
 *
 * Built from the user's own firmware image and written to a local file. It is
 * a summary of ranges, but it is derived from Korg's firmware, so it stays
 * out of the repository.
 */
import { loadUnits, unitFor, hex } from "./units.mjs";
import { TABLE } from "./layout.mjs";

/**
 * How sure we have to be before calling something a list of choices.
 *
 * With two factory presets behind a unit every parameter looks like an enum,
 * because two values are all there are. Only a unit that appears often enough
 * for the values to have had a chance to spread says anything.
 */
const ENUM_MIN_SAMPLES = 4;
const ENUM_MAX_DISTINCT = 5;
/**
 * A list of choices is numbered from zero and stays small. A continuous
 * parameter that happens to sit on five different values across the factory
 * presets, say a resonance of 0, 82, 95, 97 and 110, is not a list of
 * choices, and treating it as one buries every real finding under noise.
 */
const ENUM_MAX_VALUE = 8;


/**
 * Where the factory presets stop and ours begin.
 *
 * A profile built over our own presets would learn our own mistakes and then
 * approve of them, so only the slots that shipped count. The Sampler leaves
 * the factory with 32 master and 49 insert presets; everything above that is
 * something somebody added.
 */
export const FACTORY_SLOTS = { mfx: 32, ifx: 49 };

/** Korg's own build: its 38 insert and 32 master presets (measure:2026-10-15/preset-tabellen). */
export const STOCK_SLOTS = { mfx: 32, ifx: 38 };

export function buildProfile(image, units = loadUnits(), limit = FACTORY_SLOTS) {
  const stats = new Map();

  const note = (kind, device, param, value) => {
    const key = `${kind}:${hex(device)}:${param}`;
    let s = stats.get(key);
    if (!s) { s = { kind, device, param, min: value, max: value, samples: 0, values: new Set() }; stats.set(key, s); }
    s.min = Math.min(s.min, value);
    s.max = Math.max(s.max, value);
    s.samples++;
    if (s.values.size <= ENUM_MAX_DISTINCT) s.values.add(value);
  };

  for (const kind of Object.keys(TABLE)) {
    for (const { slot, record } of image.list(kind)) {
      if (slot > limit[kind]) continue;
      for (const stage of record.stageNames) {
        const device = record.device(stage);
        if (!device) continue;
        const unit = unitFor(units, stage === "mfx" ? "mfx" : "ifx", device);
        if (!unit) continue;
        for (const p of unit.params) note(kind, device, p.name, record.paramAt(stage, p.index));
      }
    }
  }

  const params = {};
  for (const s of stats.values()) {
    // A parameter that never moves is not a list of choices, it is a
    // parameter nobody had a reason to touch. Two distinct values at least.
    const isEnum = s.samples >= ENUM_MIN_SAMPLES
      && s.values.size >= 2
      && s.values.size <= ENUM_MAX_DISTINCT
      && s.max <= ENUM_MAX_VALUE;
    params[`${s.kind}:${hex(s.device)}:${s.param}`] = {
      samples: s.samples,
      // Only meaningful with enough presets behind it; the linter checks.
      min: s.min,
      max: s.max,
      // A parameter that only ever takes a handful of values is a list of
      // choices, and an invented choice has taken the device's output down.
      enum: isEnum ? [...s.values].sort((a, b) => a - b) : null,
    };
  }
  return { source: image.fingerprint, built: new Date().toISOString(), factorySlots: limit, params };
}

export const profileKey = (kind, device, param) => `${kind}:${hex(device)}:${param}`;
