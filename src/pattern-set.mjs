/**
 * Reading a pattern set: the step helpers the dice and the pattern tools page share.
 * Everything works on Pattern objects from src/pattern.mjs, so a pattern is only
 * ever edited, never built. No file access: it runs in the browser too.
 */

export const PARTS = 16;
export const STEPS = 64;
/** A part that never had a sample holds this. */
export const NO_SAMPLE = 0xffff;

/** The steps of one part that are on, as indices. */
export function onSteps(p, part) {
  const out = [];
  for (let s = 0; s < STEPS; s++) if (p.raw("step.on", [part, s])) out.push(s);
  return out;
}

/**
 * A pattern is free to take a new pattern when no part has both a sample and a
 * step on. The factory init pattern has four steps on a part without a sample
 * and counts as free; "Init Pattern" with real content does not.
 */
export function isFree(p) {
  for (let i = 0; i < PARTS; i++) if (onSteps(p, i).length && p.raw("part.sample", [i]) !== NO_SAMPLE) return false;
  return true;
}
