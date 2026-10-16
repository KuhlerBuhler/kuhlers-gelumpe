/**
 * A pattern set built from nothing for the pattern tools: framed blank patterns, a few with parts.
 * Own data, no Korg bytes (CLAUDE.md).
 */
import { Pattern, PatternFile } from "../../src/pattern.mjs";
import { makePatternFile } from "../helpers.mjs";

const BLOCK = 0x4000;

/** A valid, silent pattern: framed, no sample on any part, nothing on. */
export function blankPattern(name = "Init Pattern") {
  const b = new Uint8Array(BLOCK);
  [..."PTST"].forEach((c, i) => { b[i] = c.charCodeAt(0); });
  [..."PTED"].forEach((c, i) => { b[15356 + i] = c.charCodeAt(0); });
  const p = new Pattern(b);
  p.setRaw("pattern.name", [], name);
  p.setRaw("pattern.tempo", [], 1200);
  p.setRaw("pattern.length", [], 3);
  for (let i = 0; i < 16; i++) p.bytes.fill(0xff, Pattern.offset("part.sample", [i]), Pattern.offset("part.sample", [i]) + 2);
  return p;
}

/** Give a part a sample and steps; `notes` are cycled over the steps. */
export function addPart(p, i, { sample, steps, notes = [60], cutoff = 100, filterType = 1, mute = 0 }) {
  p.setRaw("part.sample", [i], sample);
  p.setRaw("part.cutoff", [i], cutoff);
  p.setRaw("part.filterType", [i], filterType);
  p.setRaw("part.mute", [i], mute);
  p.setRaw("part.motionMode", [i], 1);
  p.setRaw("part.level", [i], 100);
  steps.forEach((s, k) => {
    p.setRaw("step.on", [i, s], 1);
    p.setRaw("step.trigger", [i, s], 1);
    p.setRaw("step.gate", [i, s], 48);
    p.setRaw("step.velocity", [i, s], 100);
    p.setRaw("step.note", [i, s, 0], notes[k % notes.length] + 1);
  });
}

export const every = n => Array.from({ length: 64 / n }, (_, k) => k * n);

/** Pattern 1: a busy end state "A side", pattern 2: a sparse start "B side", pattern 3: content that is not free; the rest is blank. */
export function setBackup(count = 12) {
  const file = PatternFile.parse(makePatternFile(1));
  const a = blankPattern("A side");
  addPart(a, 0, { sample: 10, steps: every(2) });
  addPart(a, 1, { sample: 11, steps: every(4), notes: [36, 43] });
  addPart(a, 2, { sample: 12, steps: every(1), notes: [60, 63, 67], cutoff: 120 });
  a.setRaw("pattern.tempo", [], 1500);
  const b = blankPattern("B side");
  addPart(b, 4, { sample: 20, steps: every(16) });
  addPart(b, 5, { sample: 21, steps: every(8) });
  b.setRaw("pattern.tempo", [], 1600);
  const keep = blankPattern("Kept");
  addPart(keep, 0, { sample: 30, steps: every(8) });
  const blocks = [a, b, keep, ...Array.from({ length: count - 3 }, () => blankPattern())].map(p => Uint8Array.from(p.bytes));
  return { file: new PatternFile(file.header.slice(), blocks), a, b, keep };
}
