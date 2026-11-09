/**
 * What the gatekeeper checks in a pattern before it goes to the device.
 * Same severities as the effect rules in rules.mjs.
 */
import { field, readRaw } from "./map/index.mjs";
import { finding } from "./finding.mjs";

export function lintPattern(block) {
  const findings = [];
  const glide = field("part.glide");
  const glides = [];
  for (let p = 0; p < 16; p++) if (readRaw(block, glide, [p]) !== 0) glides.push(p + 1);
  if (glides.length) {
    findings.push(finding({ severity: "warn", code: "glide-dropped", where: "parts" }, "lint.pattern.glide", { parts: glides.join(", ") }));
  }
  return findings;
}
