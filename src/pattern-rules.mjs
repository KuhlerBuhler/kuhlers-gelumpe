/**
 * What the gatekeeper checks in a pattern before it goes to the device.
 * Same severities as the effect rules in rules.mjs.
 */
import { field, readRaw } from "./map/index.mjs";

export function lintPattern(block) {
  const findings = [];
  const on = field("step.on");
  const trigger = field("step.trigger");
  const silent = [];
  for (let p = 0; p < 16; p++) {
    for (let s = 0; s < 64; s++) {
      if (readRaw(block, on, [p, s]) === 1 && readRaw(block, trigger, [p, s]) !== 1) silent.push(`Part ${p + 1} Step ${s + 1}`);
    }
  }
  if (silent.length) {
    findings.push({
      severity: "warn", code: "step-without-trigger", where: "steps",
      message: `${silent.length} Steps sind an, aber ohne Trigger, und klingen so nicht: ${silent.slice(0, 4).join(", ")}${silent.length > 4 ? " und weitere" : ""}.`,
    });
  }
  const glide = field("part.glide");
  const glides = [];
  for (let p = 0; p < 16; p++) if (readRaw(block, glide, [p]) !== 0) glides.push(p + 1);
  if (glides.length) {
    findings.push({
      severity: "warn", code: "glide-dropped", where: "parts",
      message: `Glide in Part ${glides.join(", ")} geht beim Senden verloren; das Gerät verwirft dieses Byte im Pattern-Dump. Am Gerät lässt es sich per CC 81 setzen, in der Sicherungsdatei bleibt es erhalten.`,
    });
  }
  return findings;
}
