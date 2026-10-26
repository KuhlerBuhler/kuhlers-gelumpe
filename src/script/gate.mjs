/** Whether a script may leave the editor: probed without a fault, the probe is of this text, lines that never ran need a yes (SK-04). */
import { sourceKey } from "./workspace.mjs";
import { text, render } from "../text.mjs";

/**
 * @param {{ source: string, probe: { key: string, ok: boolean, missing: number[] } | null }} script
 * @returns {{ ok: boolean, confirm: boolean, missing: number[], reason: string | null }}
 */
export function exportGate(script) {
  const { probe } = script;
  if (!probe) return { ok: false, confirm: false, missing: [], reason: render(text("script.gate.notProbed")) };
  if (probe.key !== sourceKey(script.source)) return { ok: false, confirm: false, missing: [], reason: render(text("script.gate.changed")) };
  if (!probe.ok) return { ok: false, confirm: false, missing: probe.missing, reason: render(text("script.gate.fault")) };
  if (probe.missing.length) {
    return { ok: true, confirm: true, missing: probe.missing, reason: render(text("script.gate.missing", { lines: probe.missing.join(", ") })) };
  }
  return { ok: true, confirm: false, missing: [], reason: null };
}
