/**
 * What the gatekeeper checks in a pattern before it goes to the device.
 * Same severities as the effect rules in rules.mjs.
 */
import { field, readRaw } from "./map/index.mjs";
import { finding } from "./finding.mjs";
import { render, text } from "./text.mjs";

export function lintPattern(block) {
  const findings = [];
  const on = field("step.on");
  const trigger = field("step.trigger");
  const silent = [];
  for (let p = 0; p < 16; p++) {
    for (let s = 0; s < 64; s++) {
      if (readRaw(block, on, [p, s]) === 1 && readRaw(block, trigger, [p, s]) !== 1) silent.push(text("lint.pattern.step", { part: p + 1, step: s + 1 }));
    }
  }
  if (silent.length) {
    findings.push(finding({ severity: "warn", code: "step-without-trigger", where: "steps" }, "lint.pattern.noTrigger", {
      count: silent.length, steps: silent.slice(0, 4).map(render).join(", "), more: silent.length > 4 ? text("lint.pattern.more") : "",
    }));
  }
  const glide = field("part.glide");
  const glides = [];
  for (let p = 0; p < 16; p++) if (readRaw(block, glide, [p]) !== 0) glides.push(p + 1);
  if (glides.length) {
    findings.push(finding({ severity: "warn", code: "glide-dropped", where: "parts" }, "lint.pattern.glide", { parts: glides.join(", ") }));
  }
  return findings;
}
