/**
 * Reading a pattern set: chains, a plain summary of one pattern, and the step
 * and motion helpers the transition generator and the style analysis share.
 * Everything works on Pattern objects from src/pattern.mjs, so a pattern is only
 * ever edited, never built. No file access: it runs in the browser too, and
 * tools/set/lib.mjs adds loading a backup from disk.
 */
import findings from "../data/findings.mjs";

export const PARTS = 16;
export const STEPS = 64;
export const MOTION_SLOTS = 24;
/** Motion destinations by name, as the map lists them (data/map convert.mjs). */
export const DEST = { pitch: 2, glide: 3, oscEdit: 4, cutoff: 5, resonance: 6, egInt: 7, modDepth: 8, modSpeed: 9, level: 10, pan: 11, attack: 12, decay: 13, ifxEdit: 14, mfxX: 15, mfxY: 16, ifxOn: 17, mfxSend: 18, mfxPad: 19 };
export const DEST_NAME = Object.fromEntries(Object.entries(DEST).map(([k, v]) => [v, k]));
/** Motion part value that addresses the master effect. */
export const MOTION_MFX = 17;
/** A part that never had a sample holds this. */
export const NO_SAMPLE = 0xffff;

/** Chain target of pattern n (1-based), or 0. */
export const chainTarget = (file, n) => file.blocks[n - 1] && file.pattern(n).raw("pattern.chainTo");

/** Every chain as a list of pattern numbers, starting at a pattern nothing chains into. Cycles are cut. */
export function chainsOf(file) {
  const to = n => file.pattern(n).raw("pattern.chainTo");
  const into = new Set();
  for (let n = 1; n <= file.count; n++) { const t = to(n); if (t) into.add(t); }
  const out = [];
  for (let n = 1; n <= file.count; n++) {
    if (!to(n) || into.has(n)) continue;
    const chain = [n];
    for (let c = n; to(c) && to(c) <= file.count && !chain.includes(to(c)); c = to(c)) chain.push(to(c));
    out.push(chain);
  }
  return out;
}

/** The steps of one part that are on, as indices. */
export function onSteps(p, part) {
  const out = [];
  for (let s = 0; s < STEPS; s++) if (p.raw("step.on", [part, s])) out.push(s);
  return out;
}

/** The notes (0 to 127) a part plays, sorted, without duplicates. */
export function notesOf(p, part) {
  const set = new Set();
  for (const s of onSteps(p, part)) for (let k = 0; k < 4; k++) { const r = p.raw("step.note", [part, s, k]); if (r) set.add(r - 1); }
  return [...set].sort((a, b) => a - b);
}

/** One motion slot as { slot, part (1 to 16, 17 = master), dest (name), values }. */
export function motionSlots(p) {
  const out = [];
  for (let slot = 0; slot < MOTION_SLOTS; slot++) {
    const part = p.raw("motion.part", [slot]);
    if (!part) continue;
    const values = [];
    for (let s = 0; s < STEPS; s++) values.push(p.raw("motion.value", [slot, s]));
    out.push({ slot, part, dest: DEST_NAME[p.raw("motion.destination", [slot])] ?? `?${p.raw("motion.destination", [slot])}`, values });
  }
  return out;
}

/** A plain summary of one pattern, the shape the analysis and the generator work from. */
export function summarize(p) {
  const parts = [];
  for (let i = 0; i < PARTS; i++) {
    const on = onSteps(p, i);
    const sample = p.raw("part.sample", [i]);
    parts.push({
      index: i, sample, on, muted: p.raw("part.mute", [i]) === 1, notes: notesOf(p, i),
      active: on.length > 0 && sample !== NO_SAMPLE,
      audible: on.length > 0 && sample !== NO_SAMPLE && p.raw("part.mute", [i]) === 0,
      cutoff: p.raw("part.cutoff", [i]), level: p.raw("part.level", [i]), filterType: p.raw("part.filterType", [i]),
    });
  }
  const motion = motionSlots(p);
  return {
    name: p.name,
    tempo: p.raw("pattern.tempo"), length: p.raw("pattern.length"), swing: p.raw("pattern.swing"),
    key: p.raw("pattern.key"), mfx: p.raw("pattern.mfx.type"), hold: p.raw("pattern.mfx.hold"),
    padX: p.raw("pattern.mfx.padX"), padY: p.raw("pattern.mfx.padY"),
    chainTo: p.raw("pattern.chainTo"), chainRepeat: p.raw("pattern.chainRepeat"),
    parts, motion,
    steps: parts.reduce((a, x) => a + (x.sample !== NO_SAMPLE ? x.on.length : 0), 0),
    audible: parts.filter(x => x.audible).length,
    audibleSteps: parts.reduce((a, x) => a + (x.audible ? x.on.length : 0), 0),
  };
}

/** The effect slots a pattern switch can re-initialise: every part's insert (flag and type) and the master type. */
export function effectState(p) {
  const out = [];
  for (let i = 0; i < PARTS; i++) out.push({ slot: `Part ${i + 1}`, key: `${p.raw("part.ifxOn", [i])}/${p.raw("part.ifxType", [i])}` });
  out.push({ slot: "Master", key: `${p.raw("pattern.mfx.type")}` });
  return out;
}

const HEAVY_IFX = new Set(findings.find(f => f.id === "heavyIfx").ifx);

/** The parts whose insert type is a high-load one; the effects run whether on, off or not heard. */
export function heavyInserts(p) {
  const out = [];
  for (let i = 0; i < PARTS; i++) if (HEAVY_IFX.has(p.raw("part.ifxType", [i]))) out.push(`Part ${i + 1}`);
  return out;
}

/** Names of the effect slots that differ between two patterns; a switch between them re-initialises these. */
export function effectChanges(p, q) {
  const b = effectState(q);
  return effectState(p).filter((x, i) => x.key !== b[i].key).map(x => x.slot);
}

/**
 * A pattern is free to take a transition when no part has both a sample and a
 * step on. The factory init pattern has four steps on a part without a sample
 * and counts as free; "Init Pattern" with real content does not.
 */
export function isFree(p) {
  for (let i = 0; i < PARTS; i++) if (onSteps(p, i).length && p.raw("part.sample", [i]) !== NO_SAMPLE) return false;
  return true;
}
