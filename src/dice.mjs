/**
 * The dice: one drum or melody part of a pattern, rolled from a few controls.
 *
 * Records are edited, never built (AGENTS.md): the dice take a pattern that exists, write the steps of
 * one part into a copy of it (on, trigger, velocity, gate, note) and set the few pattern fields the
 * controls name (swing, length, name, and on request key and scale). Everything else stays byte for
 * byte. The same seed with the same controls and the same base gives the same bytes; no clock, no
 * Math.random in here, the seed is the caller's.
 *
 * Runs in the browser and in node. The page is site/app/pattern-tools.mjs.
 */
import { Pattern, cleanName, frameProblem } from "./pattern.mjs";
import { render } from "./text.mjs";
import { lintPattern } from "./pattern-rules.mjs";
import { NO_SAMPLE, PARTS, STEPS } from "./pattern-set.mjs";
import { noteLabel } from "./map/convert.mjs";

/**
 * The scales the dice know, with the notes of each over the root. `device` is the number of the same
 * scale in the device's own list (pattern.scale, korg-spec Scale List); the intervals are music theory,
 * not read from the device. Scales whose notes the device list does not spell out (Raga, Arabic,
 * Pelog and the rest) are left out on purpose.
 */
export const SCALES = [
  { name: "Chromatic", device: 0, intervals: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] },
  { name: "Ionian", device: 1, intervals: [0, 2, 4, 5, 7, 9, 11] },
  { name: "Dorian", device: 2, intervals: [0, 2, 3, 5, 7, 9, 10] },
  { name: "Phrygian", device: 3, intervals: [0, 1, 3, 5, 7, 8, 10] },
  { name: "Lydian", device: 4, intervals: [0, 2, 4, 6, 7, 9, 11] },
  { name: "Mixolydian", device: 5, intervals: [0, 2, 4, 5, 7, 9, 10] },
  { name: "Aeolian", device: 6, intervals: [0, 2, 3, 5, 7, 8, 10] },
  { name: "Locrian", device: 7, intervals: [0, 1, 3, 5, 6, 8, 10] },
  { name: "Harm minor", device: 8, intervals: [0, 2, 3, 5, 7, 8, 11] },
  { name: "Melo minor", device: 9, intervals: [0, 2, 3, 5, 7, 9, 11] },
  { name: "Major Blues", device: 10, intervals: [0, 2, 3, 4, 7, 9] },
  { name: "minor Blues", device: 11, intervals: [0, 3, 5, 6, 7, 10] },
  { name: "Diminished", device: 12, intervals: [0, 2, 3, 5, 6, 8, 9, 11] },
  { name: "Major Penta", device: 14, intervals: [0, 2, 4, 7, 9] },
  { name: "minor Penta", device: 15, intervals: [0, 3, 5, 7, 10] },
  { name: "Whole Tone", device: 29, intervals: [0, 2, 4, 6, 8, 10] },
];

export const ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

/** A step carries note + 1; the factory default note 60 (C4) is 61 (see site/app/steps.mjs). */
const DRUM_NOTE = 60;
/** Gate time runs 0 to 96 (korg-spec, Table 6); 127 means tie and is never written here. */
const GATE_MAX = 96;

/** mulberry32: a small seeded generator, 32 bits of state. */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** How likely a step position is to carry a note: the bar's beats first, the in-between steps last. */
function weight(s, kind) {
  if (kind === "drums") return s % 16 === 0 ? 8 : s % 8 === 0 ? 5 : s % 4 === 0 ? 3 : s % 2 === 0 ? 1.4 : 0.7;
  return s % 16 === 0 ? 3 : s % 8 === 0 ? 2.2 : s % 4 === 0 ? 1.6 : s % 2 === 0 ? 1.1 : 0.8;
}

/** `count` of the first `n` steps, drawn without replacement, the heavier positions more often; ascending. */
function pickSteps(rand, n, count, kind) {
  const keyed = Array.from({ length: n }, (_, s) => ({ s, key: Math.log(rand() || Number.MIN_VALUE) / weight(s, kind) }));
  return keyed.sort((x, y) => (y.key - x.key) || (x.s - y.s)).slice(0, count).map(x => x.s).sort((x, y) => x - y);
}

/** The notes (0 to 127) a melody may use: the scale from the root in the base octave, `span` octaves up, ending on the root. */
export function scalePool(scale, root, octave, span) {
  const def = SCALES.find(x => x.name === scale);
  const low = 12 * (octave + 1) + root;
  const pool = [];
  for (let o = 0; o < span; o++) for (const iv of def.intervals) pool.push(low + 12 * o + iv);
  pool.push(low + 12 * span);
  return pool.filter(n => n <= 127);
}

const LEAPS = [[-1, 3], [1, 3], [-2, 2], [2, 2], [0, 1.5], [3, 1], [-3, 1], [4, 0.5], [-4, 0.5]];

function walk(rand, pool, count) {
  const out = [];
  let at = rand() < 0.7 ? 0 : Math.floor(rand() * pool.length);
  const total = LEAPS.reduce((a, [, w]) => a + w, 0);
  for (let i = 0; i < count; i++) {
    if (i > 0) {
      if (rand() < 0.12) at = Math.floor(rand() * pool.length);
      else {
        let r = rand() * total;
        let delta = 0;
        for (const [d, w] of LEAPS) { r -= w; if (r <= 0) { delta = d; break; } }
        at = clamp(at + delta, 0, pool.length - 1);
      }
    }
    out.push(pool[at]);
  }
  return out;
}

function check(o) {
  const bad = text => { throw new RangeError(text); };
  if (!Number.isInteger(o.part) || o.part < 0 || o.part >= PARTS) bad("part must be 0 to 15");
  if (o.kind !== "drums" && o.kind !== "melody") bad(`kind must be drums or melody, not ${o.kind}`);
  if (!(o.density >= 0 && o.density <= 1)) bad("density must be 0 to 1");
  if (!Number.isInteger(o.seed) || o.seed < 0 || o.seed > 0xffffffff) bad("seed must be a whole number from 0 to 4294967295");
  if (!Number.isInteger(o.root) || o.root < 0 || o.root > 11) bad("root must be 0 to 11");
  if (!SCALES.some(x => x.name === o.scale)) bad(`scale ${o.scale} is not one of the dice scales`);
  if (!Number.isInteger(o.octave) || o.octave < 0 || o.octave > 8) bad("octave must be 0 to 8");
  if (!Number.isInteger(o.span) || o.span < 1 || o.span > 3) bad("span must be 1 to 3 octaves");
  if (!(o.gate >= 0 && o.gate <= 1)) bad("gate must be 0 to 1");
  if (!(o.accent >= 0 && o.accent <= 1)) bad("accent must be 0 to 1");
  if (o.swing !== null && !(Number.isInteger(o.swing) && o.swing >= -48 && o.swing <= 48)) bad("swing must be -48 to 48 or null");
  if (o.bars !== null && !(Number.isInteger(o.bars) && o.bars >= 1 && o.bars <= 4)) bad("bars must be 1 to 4 or null");
}

export const DEFAULTS = {
  part: 0, kind: "drums", density: 0.5, seed: 1, root: 0, scale: "minor Penta", octave: 3, span: 2,
  gate: 0.5, accent: 0.5, swing: null, bars: null, unmute: true, writeScale: false, name: undefined,
};

/**
 * Roll one part into a copy of `base`.
 *
 * @param {Pattern} base  a pattern that exists; it is not changed
 * @param {object} [options]
 * @param {number} [options.part=0]  0 to 15
 * @param {"drums"|"melody"} [options.kind="drums"]  drums: one note (C4, the sample's own pitch), heavy beats first; melody: notes from the scale, stepwise with leaps
 * @param {number} [options.density=0.5]  share of the pattern's steps that get a note, 0 to 1
 * @param {number} [options.seed=1]  whole number, 0 to 4294967295
 * @param {number} [options.root=0]  0 (C) to 11 (B), melody only
 * @param {string} [options.scale="minor Penta"]  a name from SCALES, melody only
 * @param {number} [options.octave=3]  the octave of the lowest root, melody only (C3 is note 48)
 * @param {number} [options.span=2]  octaves the melody may cover, 1 to 3
 * @param {number} [options.gate=0.5]  mean gate length as a share of 96, 0 to 1
 * @param {number} [options.accent=0.5]  how far the velocities spread, 0 to 1
 * @param {number|null} [options.swing=null]  pattern swing, -48 to 48; null keeps the pattern's own
 * @param {number|null} [options.bars=null]  pattern length 1 to 4 bars; null keeps the pattern's own
 * @param {boolean} [options.unmute=true]  switch the part's mute off so it is heard
 * @param {boolean} [options.writeScale=false]  also set the pattern's key and scale (melody; the scale must exist in the device list)
 * @param {string} [options.name]  pattern name (printable ASCII, 16 characters); undefined keeps the pattern's own
 * @returns {{ pattern: Pattern, count: number, steps: {step: number, note: number|null, velocity: number, gate: number}[], warnings: string[], text: string }}
 */
export function rollPart(base, options = {}) {
  const o = { ...DEFAULTS, ...options };
  check(o);
  const pattern = new Pattern(base.bytes);
  const warnings = [];
  const rand = rng(o.seed);

  if (o.bars !== null) pattern.setRaw("pattern.length", [], o.bars - 1);
  const n = Math.min(STEPS, (pattern.raw("pattern.length") + 1) * 16);
  const count = Math.round(o.density * n);
  const at = pickSteps(rand, n, count, o.kind);
  const pool = o.kind === "melody" ? scalePool(o.scale, o.root, o.octave, o.span) : null;
  const notes = o.kind === "melody" ? walk(rand, pool, at.length) : at.map(() => DRUM_NOTE);

  for (let s = 0; s < STEPS; s++) pattern.setRaw("step.on", [o.part, s], 0);
  const steps = at.map((s, i) => {
    const strong = s % 4 === 0;
    const velocity = clamp(Math.round((strong ? 108 : 84) + (rand() - 0.5) * (24 + 56 * o.accent)), 1, 127);
    const gate = clamp(Math.round(GATE_MAX * o.gate + (rand() - 0.5) * 0.3 * GATE_MAX), 1, GATE_MAX);
    const note = notes[i];
    pattern.setRaw("step.on", [o.part, s], 1);
    pattern.setRaw("step.trigger", [o.part, s], 1);
    pattern.setRaw("step.velocity", [o.part, s], velocity);
    pattern.setRaw("step.gate", [o.part, s], gate);
    pattern.setRaw("step.note", [o.part, s, 0], note + 1);
    for (let k = 1; k < 4; k++) pattern.setRaw("step.note", [o.part, s, k], 0);
    return { step: s, note, velocity, gate };
  });

  if (o.swing !== null) pattern.setRaw("pattern.swing", [], o.swing);
  if (o.unmute && pattern.raw("part.mute", [o.part]) === 1) {
    pattern.setRaw("part.mute", [o.part], 0);
    warnings.push(`Part ${o.part + 1} war gemutet und ist jetzt an.`);
  } else if (pattern.raw("part.mute", [o.part]) === 1) warnings.push(`Part ${o.part + 1} ist gemutet und bleibt es.`);
  if (pattern.raw("part.sample", [o.part]) === NO_SAMPLE) warnings.push(`Part ${o.part + 1} hat kein Sample, die Steps klingen nicht, bis ein Sample gewählt ist.`);
  if (o.writeScale && o.kind === "melody") {
    pattern.setRaw("pattern.key", [], o.root);
    pattern.setRaw("pattern.scale", [], SCALES.find(x => x.name === o.scale).device);
  }
  if (o.name !== undefined) {
    const name = cleanName(o.name);
    if (name) pattern.setRaw("pattern.name", [], name);
  }

  const shown = o.kind === "melody" && steps.length
    ? `, Noten ${noteLabel(Math.min(...steps.map(x => x.note)))} bis ${noteLabel(Math.max(...steps.map(x => x.note)))} (${ROOTS[o.root]} ${o.scale})`
    : "";
  const text = `Part ${o.part + 1}, ${o.kind === "drums" ? "Drums" : "Melodie"}: ${steps.length} von ${n} Steps${shown}, Seed ${o.seed}.`;
  return { pattern, count: steps.length, steps, warnings, text };
}

/** Findings on a rolled pattern; empty means fine. The same frame and step checks the gate runs before a send. */
export function checkRoll(pattern) {
  const out = [];
  const fp = frameProblem(pattern.bytes);
  if (fp) out.push({ severity: "error", message: `Rahmen: ${render(fp)}` });
  for (const f of lintPattern(pattern.bytes)) out.push({ severity: f.severity, message: f.message });
  return out;
}
