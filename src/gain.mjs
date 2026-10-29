/**
 * Gain staging: the verdict on an effect output level (shared by the linter
 * and the page) and the scaling of a pattern's levels. Scaling works on plain
 * values and leaves every other byte of the pattern alone.
 */
import { field } from "./map/index.mjs";
import { converter } from "./map/convert.mjs";
import { LOUDNESS, GAIN_STAGING } from "./layout.mjs";
import { unitFor } from "./units.mjs";
import { finding } from "./finding.mjs";
import { text } from "./text.mjs";

export const LEVEL_MAX = 127;
export const OUTPUT_PARAM = /^(output_level|output_gain)$/;

/**
 * Judge one output level of an effect unit. The scale differs from unit to
 * unit, so a value the factory presets of that unit reach themselves
 * (`factory`, its entry of the factory profile) is left alone. Between the
 * playable range and the ceiling nothing was heard, which is said as untested.
 *
 * @returns {{code: string, message: string, text: object, measured: boolean} | null} `message` renders `text` (src/finding.mjs)
 */
export function judgeOutput(device, param, value, factory = null) {
  if (!OUTPUT_PARAM.test(param)) return null;
  if (factory && value <= factory.max) return null;

  const [lo, hi] = GAIN_STAGING.usable;
  const heard = GAIN_STAGING.unplayable.find(u => u.param === param && u.unit === device && value >= u.value);
  if (heard) {
    return finding({ code: "output-too-loud", measured: true }, "lint.output.heard", { note: heard.note, value, lo, hi });
  }
  if (value > LOUDNESS.outputCeiling) {
    return finding({ code: "output-too-loud", measured: false }, "lint.output.korg", { typical: LOUDNESS.outputTypical.join(" to ") });
  }
  if (value > hi) {
    return finding({ code: "output-above-usable", measured: false }, "lint.output.untested", { lo, hi, ceiling: LOUDNESS.outputCeiling, value });
  }
  return null;
}

/** The output levels in a record's stages, by name, for the overview. */
export function outputLevels(record, units) {
  const out = [];
  for (const stage of record.stageNames) {
    const device = record.device(stage);
    if (!device) continue;
    const unit = unitFor(units, stage === "mfx" ? "mfx" : "ifx", device);
    if (!unit) continue;
    for (const p of unit.params) {
      if (OUTPUT_PARAM.test(p.name)) out.push({ stage, device, unit: unit.unit, param: p.name, value: record.paramAt(stage, p.index) });
    }
  }
  return out;
}

const read = (pattern, id, indices = []) => {
  const f = field(id);
  const plain = converter(f.convert).fromRaw(pattern.raw(id, indices));
  return Math.max(0, Math.min(LEVEL_MAX, plain));
};

/**
 * The levels of a pattern as plain values, 0 to 127, the way the device
 * shows them. `part.ifx` is the insert preset as the menu counts it from one
 * (the stored type counts from zero), derived from the menu length and the
 * observed types, not checked on a device; null when the insert is off.
 */
export function readLevels(pattern) {
  return {
    master: { id: "pattern.playLevel", indices: [], label: text("levels.label.pattern"), value: read(pattern, "pattern.playLevel") },
    parts: Array.from({ length: 16 }, (_, part) => ({
      id: "part.level", indices: [part], part, label: text("levels.label.part", { part: part + 1 }),
      value: read(pattern, "part.level", [part]),
      muted: pattern.raw("part.mute", [part]) === 1,
      ifx: pattern.raw("part.ifxOn", [part]) === 1 ? pattern.raw("part.ifxType", [part]) + 1 : null,
    })),
  };
}

/**
 * What scaling would do, without doing it: one factor for every level that
 * takes part, so the balance stays. `target` makes the loudest of them that
 * value. A factor that would push the loudest past 127 is held back to the
 * one that lands on 127 (clipping would squash the balance); a level above
 * zero never rounds down to zero.
 *
 * @param {ReturnType<typeof readLevels>} levels
 * @param {{mode?: "factor"|"target", value: number, master?: boolean}} options master: the play level takes part too
 */
export function planScale(levels, { mode = "factor", value, master = false } = {}) {
  const taking = [...(master ? [levels.master] : []), ...levels.parts];
  const peak = Math.max(...taking.map(l => l.value));
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    return { error: mode === "target" ? text("levels.error.target") : text("levels.error.factor") };
  }
  if (mode === "target" && number > LEVEL_MAX) return { error: text("levels.error.targetMax", { max: LEVEL_MAX }) };
  if (mode === "target" && peak === 0) return { error: text("levels.error.allZero") };

  const requested = mode === "target" ? number / peak : number;
  const limited = peak > 0 && peak * requested > LEVEL_MAX;
  const factor = limited ? LEVEL_MAX / peak : requested;
  const scaled = l => {
    const after = l.value === 0 ? 0 : Math.min(LEVEL_MAX, Math.max(1, Math.round(l.value * factor)));
    return { id: l.id, indices: l.indices, label: l.label, before: l.value, after, delta: after - l.value, muted: l.muted ?? false };
  };
  const rows = taking.map(scaled);
  return {
    factor, requested, limited, rows,
    changed: rows.some(r => r.delta !== 0),
    peakBefore: peak,
    peakAfter: Math.max(...rows.map(r => r.after)),
  };
}

/** Write a plan into a pattern, one byte per changed level; returns the changes for undo. */
export function applyScale(pattern, plan) {
  const changes = [];
  for (const r of plan.rows) {
    if (r.delta === 0) continue;
    const c = converter(field(r.id).convert);
    changes.push(pattern.setRaw(r.id, r.indices, c.toRaw(r.after)));
  }
  return changes;
}
