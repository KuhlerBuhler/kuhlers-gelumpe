/**
 * Suggested parameter sets for a preset the user already has (data/suggestions.mjs).
 *
 * Records are edited, never built: a suggestion sets named parameters on a
 * record that exists and leaves every other byte as it is.
 */
import SUGGESTIONS from "../data/suggestions.mjs";
import { STAGE2 } from "./layout.mjs";
import { unitFor } from "./units.mjs";

export const suggestion = id => SUGGESTIONS.find(s => s.id === id) ?? null;

/** Why this record cannot take the suggestion, or null when it can. */
export function refusal(record, s) {
  if (record.kind !== "ifx") return "Nur ein Insert-Preset nimmt diesen Vorschlag.";
  if (record.device("ifx2") === s.unit && STAGE2[s.unit]?.verdict === "fatal") {
    return `Dieser Baustein in Stufe 2 ist gesperrt: ${STAGE2[s.unit].note}. Der Vorschlag gilt nur für Stufe 1.`;
  }
  if (record.device(s.stage) !== s.unit) return "Der Vorschlag gilt für ein Preset mit diesem Baustein in Stufe 1.";
  if (record.device("ifx2")) return "Hinter dem Baustein steht eine zweite Stufe, damit ist der Vorschlag nicht gehört worden.";
  return null;
}

/** Every suggestion with the reason this record cannot take it, null where it can. */
export function suggestionsFor(record) {
  return SUGGESTIONS.map(s => ({ suggestion: s, refusal: refusal(record, s) }));
}

/**
 * Set the suggestion's parameters on `record`, in place.
 * @returns {{param: string, before: number, after: number}[]} what changed
 */
export function applySuggestion(record, s, units) {
  const why = refusal(record, s);
  if (why) throw new Error(why);
  const unit = unitFor(units, "ifx", s.unit);
  const changes = [];
  for (const [param, after] of Object.entries(s.params)) {
    const p = unit.params.find(x => x.name === param);
    if (!p) throw new Error(`${unit.unit} has no parameter ${param}`);
    changes.push({ param, before: record.paramAt(s.stage, p.index), after });
  }
  record.setParams(units, s.stage, s.params);
  return changes;
}
