/**
 * What the gatekeeper checks in a sample edit before it goes to the device. Same severities as the
 * effect rules in rules.mjs. Every rule is a warning: a name and a tune were written on the device
 * once each, so anything beyond what that showed is untested, not known to be wrong (data/findings.mjs,
 * sampleName.field and sampleTune.seen).
 *
 * @param {{ index: number, name?: string, tune?: number, before?: { name: string, tune: number, rate: number, pcmBytes: number } }} edit
 *   `before` is what the page read from the device; it lets the rules see an unused slot.
 */
import FINDINGS from "../data/findings.mjs";
import { finding as said } from "./finding.mjs";

const finding = id => {
  const f = FINDINGS.find(x => x.id === id);
  if (!f) throw new Error(`no finding ${id}`);
  return f;
};
const NAME_WIDTH = finding("sampleName.field").width;
const SEEN = finding("sampleTune.seen").seen;
export const TUNE_SEEN = [Math.min(...SEEN), Math.max(...SEEN)];

export function lintSample({ name, tune, before }) {
  const findings = [];
  const warn = (code, where, key, vars) => findings.push(said({ severity: "warn", code, where }, key, vars));
  if (name === "") {
    warn("sample-name-empty", "name", "lint.sample.nameEmpty");
  }
  if (name !== undefined && name.length === NAME_WIDTH) {
    warn("sample-name-full", "name", "lint.sample.nameFull", { width: NAME_WIDTH });
  }
  if (tune !== undefined && (tune < TUNE_SEEN[0] || tune > TUNE_SEEN[1])) {
    warn("sample-tune-unseen", "tune", "lint.sample.tuneUnseen", { tune, low: TUNE_SEEN[0], high: TUNE_SEEN[1] });
  }
  if (before && before.pcmBytes === 0) {
    warn("sample-slot-empty", "slot", "lint.sample.slotEmpty");
  }
  return findings;
}
