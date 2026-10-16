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
  const warn = (code, where, message) => findings.push({ severity: "warn", code, where, message });
  if (name === "") {
    warn("sample-name-empty", "name",
      "Der Name ist leer. Am Gerät wurde nur ein benannter Platz geschrieben; wie das Display einen leeren Namen zeigt, ist nicht gemessen.");
  }
  if (name !== undefined && name.length === NAME_WIDTH) {
    warn("sample-name-full", "name",
      `Der Name füllt alle ${NAME_WIDTH} Byte, ohne abschließendes NUL. Gemessen ist nur ein kürzerer Name, mit NUL aufgefüllt; ob die Firmware einen vollen Namen richtig anzeigt, ist nicht gemessen.`);
  }
  if (tune !== undefined && (tune < TUNE_SEEN[0] || tune > TUNE_SEEN[1])) {
    warn("sample-tune-unseen", "tune",
      `Tune ${tune} liegt außerhalb der Werte, die am Gerät gesehen wurden (${TUNE_SEEN[0]} bis ${TUNE_SEEN[1]}). ` +
      "Gemessen ist nur, dass -12 die Tonhöhe hörbar änderte; die Skala ist nicht gemessen, auch nicht, ob ein Wert Halbtöne meint.");
  }
  if (before && before.pcmBytes === 0) {
    warn("sample-slot-empty", "slot",
      "Der Platz sieht unbenutzt aus: die PCM-Länge ist 0. Im Emulator ohne Karte tragen solche Plätze einen Standardnamen (Sample701) und die Samplerate 48000, ein leerer Name ist also kein Zeichen. Name oder Tune an einem unbenutzten Platz sind nicht gemessen.");
  }
  return findings;
}
