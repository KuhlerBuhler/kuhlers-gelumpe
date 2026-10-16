/**
 * Transition patterns between two patterns of a set, in the style of
 * docs/set/uebergaenge.md. Runs in the browser and in node: no file access here,
 * the command line is tools/set/transition.mjs, the page is site/app/pattern-tools.mjs.
 *
 * Every transition is an edit of a copy of pattern A (records are edited,
 * never built, see CLAUDE.md); B's parts come in as copies of B's own part
 * blocks.
 */
import { Pattern, frameProblem, cleanName } from "./pattern.mjs";
import { lintPattern } from "./pattern-rules.mjs";
import {
  DEST, MOTION_MFX, MOTION_SLOTS, PARTS, STEPS, NO_SAMPLE, summarize, onSteps, isFree, effectChanges, heavyInserts,
} from "./pattern-set.mjs";

const DIRECTIONS = new Set(["auto", "down", "up", "blend"]);
const PAD_MODES = new Set(["hold", "release", "corner", "none"]);
const SWEEP_MODES = new Set(["tail", "run", "none"]);
const TEMPO_MODES = new Set(["ease", "ramp", "keep"]);

const CUTOFF = { open: 127, closed: 12 };
/** Where the set's X/Y motion ends (patterns 77, 79, 85, 189, 193). */
const CORNER = { x: 127, y: 1 };
/** Master FX pad while Hold is on: the start of the corner curve (docs/set/uebergaenge.md). */
const HOLD_PAD = { first: { x: 48, y: 110 }, then: { x: 28, y: 110 } };
/** Share of its steps a part keeps in the transition before it leaves (only with thinBefore). */
const THIN = 0.6;
const ARRIVE_FILL = 0.5;
/** Shared parts stop at this fraction of the pattern in the last transition of a chain of 3 or more. */
const BREATH = 0.65;
/** Last-transition filter arc: share of the pattern, share spent rising, peak and end distance from the base cutoff. */
const TAIL = { span: 20 / 64, rise: 0.3, peak: 74, rest: 12 };
/** Header byte that matches Hold in 242 of 250 patterns of the set; the device wrote both when Hold went off. */
const HOLD_MIRROR = 60;
/** Tempo moves between these shares of the way through the transitions; a change of 5 BPM or less is one step. */
const TEMPO_WINDOW = { from: 0.3, to: 0.9, step: 50, stepAt: 0.6 };
/** Deepest point of the chain: share of the way, share of A's and B's steps left, audible parts left. */
const VALLEY = { at: 0.5, steps: 0.3, parts: 3 };
/** Decay of the part that plays on into B in the last transition. */
const CLIP_DECAY = 15;
/** An accent part has this many steps at most and comes in at 40 % of the transitions and in the last one. */
const ACCENT = { maxSteps: 8, at: 0.4 };
/** Report the heavy inserts of a transition from this many parts on. */
const HEAVY_REPORT = 4;
/** The last quarter of the last transition: the pad runs into the corner in release mode. */
const RELEASE_SPAN = 0.25;

const smooth = t => t * t * (3 - 2 * t);
const ease = t => t * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const partStride = Pattern.offset("part.lastStep", [1]) - Pattern.offset("part.lastStep", [0]);
const partStart = i => Pattern.offset("part.lastStep", [i]);

function stepPriority(i) {
  return (i % 16 === 0 ? 0 : i % 8 === 0 ? 1 : i % 4 === 0 ? 2 : i % 2 === 0 ? 3 : 4) * 64 + i;
}

/** Switch off all but the `count` highest-priority steps of a part; returns how many went. */
function thinPart(p, part, count) {
  const on = onSteps(p, part);
  if (count >= on.length) return 0;
  const drop = [...on].sort((a, b) => stepPriority(b) - stepPriority(a)).slice(0, on.length - count);
  for (const s of drop) p.setRaw("step.on", [part, s], 0);
  return drop.length;
}

const activeSteps = p => (p.raw("pattern.length") + 1) * 16;

/** Ramp over the steps the pattern plays, held at the end value for the rest of the 64. */
function ramp(p, from, to, curve) {
  const n = activeSteps(p);
  const out = [];
  for (let s = 0; s < STEPS; s++) {
    const t = n > 1 ? Math.min(s, n - 1) / (n - 1) : 1;
    out.push(clamp(Math.round(from + (to - from) * curve(t)), 0, 127));
  }
  return out;
}

/** Slot already on this target, else the first empty one, else null. */
function slotFor(p, part, dest) {
  let empty = null;
  for (let s = 0; s < MOTION_SLOTS; s++) {
    const sp = p.raw("motion.part", [s]);
    if (sp === part && p.raw("motion.destination", [s]) === dest) return s;
    if (sp === 0 && empty === null) empty = s;
  }
  return empty;
}

function writeMotion(p, part, dest, values) {
  const slot = slotFor(p, part, dest);
  if (slot === null) return null;
  p.setRaw("motion.part", [slot], part);
  p.setRaw("motion.destination", [slot], dest);
  values.forEach((v, s) => p.setRaw("motion.value", [slot, s], v));
  return slot;
}

function setHold(p, on) {
  p.setRaw("pattern.mfx.hold", [], on);
  p.bytes[HOLD_MIRROR] = on;
}

/** Filter sweep target of the "run" sweep: audible, filter not off or high pass (type 7), most open, then most distinct notes. */
function leadPart(sum, keep = []) {
  const audible = sum.parts.filter(x => x.audible);
  const pool = audible.filter(x => !keep.length || keep.includes(x.index + 1));
  const lowpassy = pool.filter(x => x.filterType !== 0 && x.filterType !== 7);
  return [...(lowpassy.length ? lowpassy : pool)].sort((x, y) => (y.cutoff - x.cutoff) || (y.notes.length - x.notes.length) || (y.on.length - x.on.length))[0] ?? null;
}

/**
 * Cutoff values for the last steps of a pattern: constant at the base, then a quick move
 * away from it into the larger half of the range (up from a low cutoff, down from a high one), a slow way back to a point near the base.
 */
export function tailArc(base, steps) {
  const dir = base < 64 ? 1 : -1;
  const peak = clamp(base + dir * TAIL.peak, 0, 127), rest = clamp(base + dir * TAIL.rest, 0, 127);
  const span = Math.max(2, Math.min(steps, Math.round(steps * TAIL.span)));
  const rise = Math.max(1, Math.round(span * TAIL.rise));
  const out = Array(STEPS).fill(rest);
  for (let s = 0; s < steps - span; s++) out[s] = base;
  for (let k = 0; k < span; k++) {
    const v = k < rise ? base + (peak - base) * smooth((k + 1) / rise) : peak + (rest - peak) * ((k - rise + 1) / (span - rise));
    out[steps - span + k] = clamp(Math.round(v), 0, 127);
  }
  return { values: out, span, peak, rest };
}

const bpm = raw => `${(raw / 10).toLocaleString("de-DE", { maximumFractionDigits: 1 })} BPM`;
const partsText = xs => `${xs.length > 1 ? "Parts" : "Part"} ${xs.map(x => x.index + 1).join(", ")}`;
const nameOf = (n, p) => (p.name && p.name !== "Init Pattern" ? `${n || ""} ${p.name}`.trim() : `${n || "ohne Nummer"}`);

function tempoAt(from, to, i, count, mode) {
  const u = i / count;
  const f = mode === "ramp" ? i / (count + 1)
    : Math.abs(to - from) <= TEMPO_WINDOW.step ? (u >= TEMPO_WINDOW.stepAt ? 1 : 0)
      : smooth(clamp((u - TEMPO_WINDOW.from) / (TEMPO_WINDOW.to - TEMPO_WINDOW.from), 0, 1));
  return clamp(Math.round((from + (to - from) * f) / 10) * 10, 200, 3000);
}

/** Share of a part's steps that sit on a quarter of the bar; parts below one half are offbeat parts. */
const pulse = x => (x.on.length ? x.on.filter(s => s % 4 === 0).length / x.on.length : 0);

/** Motion value 128 (on) is outside the map's range; the device has it in 987 factory values. */
function writeSwitchMotion(p, part, dest, from, to) {
  const slot = slotFor(p, part, dest);
  if (slot === null) return null;
  p.setRaw("motion.part", [slot], part);
  p.setRaw("motion.destination", [slot], dest);
  for (let s = 0; s < STEPS; s++) p.bytes[Pattern.offset("motion.value", [slot, s])] = s >= from && s <= to ? 128 : 0;
  return slot;
}

/**
 * Plan and build the transitions between pattern A (end state) and B (start).
 *
 * Parts that sound in A and not in B leave in groups; parts that sound in B and not in A
 * come in as copies of B's part blocks, the sparsest first, offbeat parts only with B. The
 * chain has a valley in the middle (few parts, few steps). Insert and master effect types stay
 * as A has them in every transition: each switch whose effect state differs from the last one
 * costs a gap, so all differences between A and B land in the single switch into B.
 *
 * @param {Pattern} a
 * @param {Pattern} b
 * @param {object} [o]
 * @param {number} [o.count=2]
 * @param {"auto"|"down"|"up"|"blend"} [o.direction="auto"]  down: A's parts leave, up: B's parts come in, blend: both; auto: blend when both sides have parts of their own, else up or down
 * @param {"keep"|"auto"|number} [o.mfx="keep"]  master effect type; a number sets it in the last transition and costs an effect change at two switches
 * @param {"ease"|"ramp"|"keep"} [o.tempo="ease"]  ease: stay, move in the middle, settle (a change of 5 BPM or less is one step); ramp: straight line
 * @param {"hold"|"release"|"corner"|"none"} [o.pad="hold"]  hold: master FX hold on after the first transition, off in the last; release: also run the pad into the corner in the last quarter of the last transition; corner: pad motion into the corner across all transitions
 * @param {"tail"|"run"|"none"} [o.sweep="tail"]  tail: one filter arc in the last transition on a part that carries over into B; run: one sweep across all transitions
 * @param {"auto"|"none"|number} [o.valley="auto"]  share of the steps left at the deepest point, none: no valley
 * @param {number} [o.valleyParts=3]  audible parts at the deepest point
 * @param {"auto"|"none"|number} [o.accent="auto"]  a muted part of A that sounds in neither A nor B comes in twice (part 1 to 16)
 * @param {"none"|number} [o.clip=15]  decay of the carrying part in the last transition
 * @param {number} [o.leaveMax=2]  most parts of A that leave in one transition
 * @param {number|null} [o.thinBefore=null]  share of its steps a leaving part keeps in the transition before it goes
 * @param {"pulse"|"all"} [o.arrive="pulse"]  pulse: offbeat parts of B wait for B; all: every part of B comes in early
 * @param {boolean} [o.insertMotion=false]  switch the insert of the carrying part on for one bar of the last transition when it is off
 * @param {number[]} [o.keep]  parts (1 to 16) that never leave and get the "run" sweep
 * @param {number[]} [o.drop]  parts (1 to 16) that leave first
 * @param {number[]|null} [o.slots]  slot numbers of the transitions, for Chain To
 * @param {number} [o.slotB]  slot number of B
 * @param {boolean} [o.chain=false]  set Chain To: each transition to the next, the last to B
 * @param {string} [o.label]  name stem, default from B
 * @param {string[]} [o.names]  names of the transitions, in order; an empty or missing one keeps the generated name (printable ASCII, 16 characters)
 */
export function makeTransitions(a, b, o = {}) {
  const count = o.count ?? 2;
  if (!Number.isInteger(count) || count < 1 || count > 8) throw new RangeError("count must be 1 to 8");
  const wanted = o.direction ?? "auto";
  if (!DIRECTIONS.has(wanted)) throw new RangeError(`direction must be auto, down, up or blend, not ${wanted}`);
  const padMode = o.pad ?? "hold", sweepMode = o.sweep ?? "tail", tempoMode = o.tempo ?? "ease";
  if (!PAD_MODES.has(padMode)) throw new RangeError(`pad must be hold, release, corner or none, not ${padMode}`);
  if (!SWEEP_MODES.has(sweepMode)) throw new RangeError(`sweep must be tail, run or none, not ${sweepMode}`);
  if (!TEMPO_MODES.has(tempoMode)) throw new RangeError(`tempo must be ease, ramp or keep, not ${tempoMode}`);
  const arriveMode = o.arrive ?? "pulse";
  if (arriveMode !== "pulse" && arriveMode !== "all") throw new RangeError(`arrive must be pulse or all, not ${arriveMode}`);
  const leaveMax = o.leaveMax ?? 2;
  if (!Number.isInteger(leaveMax) || leaveMax < 1) throw new RangeError("leaveMax must be 1 or more");
  const keep = o.keep ?? [], dropFirst = o.drop ?? [];
  const sa = summarize(a), sb = summarize(b);
  const valleySteps = o.valley === "none" ? null : typeof o.valley === "number" ? o.valley : VALLEY.steps;
  const valleyParts = o.valleyParts ?? VALLEY.parts;
  const clip = o.clip === "none" ? null : o.clip ?? CLIP_DECAY;

  const ownA = sa.parts.filter(x => x.audible && !sb.parts[x.index].audible && !keep.includes(x.index + 1));
  const ownB = sb.parts.filter(x => x.audible && !sa.parts[x.index].audible);
  const shared = sb.parts.filter(x => x.audible && sa.parts[x.index].audible);
  const direction = wanted === "auto" ? (ownA.length && ownB.length ? "blend" : ownB.length ? "up" : "down") : wanted;
  const lead = sweepMode === "run" ? leadPart(sa, keep) : null;

  const melodic = x => (x.notes.length > 1 ? 1 : 0);
  const leaveOrder = (list) => [...list].sort((x, y) => (dropFirst.includes(y.index + 1) - dropFirst.includes(x.index + 1)) || (melodic(x) - melodic(y)) || (y.on.length - x.on.length));
  let leavers = [];
  if (direction !== "up") {
    const exclusive = ownA.filter(x => x !== lead);
    const pool = sa.parts.filter(x => x.audible && !keep.includes(x.index + 1) && x !== lead);
    leavers = leaveOrder(direction === "blend" || exclusive.length ? exclusive : pool).slice(0, direction === "blend" || exclusive.length ? undefined : Math.ceil(pool.length * 0.5));
  }
  const lastLeave = Math.max(1, count - 1);
  const leaveAt = leavers.map((_, j) => Math.min(lastLeave, Math.max(Math.ceil(((j + 1) * lastLeave) / leavers.length), Math.floor(j / leaveMax) + 1)));
  const arrivers = direction === "down" ? [] : [...ownB].filter(x => arriveMode === "all" || pulse(x) >= 0.5).sort((x, y) => x.on.length - y.on.length);
  const waiting = direction === "down" ? [] : ownB.filter(x => !arrivers.includes(x));
  const arriveAt = arrivers.map((_, k) => Math.ceil((count * (k + 1)) / (arrivers.length + 1)));
  const byDensity = (x, y) => y.on.length - x.on.length;
  const carry = [...arrivers].sort(byDensity)[0] ?? [...shared].sort(byDensity)[0] ?? null;
  const accent = (() => {
    if (o.accent === "none" || count < 3 || direction === "up") return null;
    const spare = sa.parts.filter(x => x.sample !== NO_SAMPLE && x.on.length >= 2 && x.on.length <= ACCENT.maxSteps && !sa.parts[x.index].audible && !sb.parts[x.index].audible && !ownB.includes(x) && !leavers.includes(x));
    if (typeof o.accent === "number") return spare.find(x => x.index === o.accent - 1) ?? sa.parts[o.accent - 1];
    return [...spare].sort((x, y) => (x.on.length - y.on.length) || (y.index - x.index))[0] ?? null;
  })();
  const accentAt = new Set(accent ? [Math.ceil(count * ACCENT.at), count] : []);
  const maxParts = Math.max(sa.audible, valleyParts);

  const stem = (o.label ?? (b.name && b.name !== "Init Pattern" ? b.name : `${o.slotB ?? ""}`)).trim().slice(0, 10);
  const items = [];
  const held = (padMode === "hold" || padMode === "release") && count >= 2 && sa.hold === 0;
  let previous = a;

  for (let i = 1; i <= count; i++) {
    const last = i === count;
    const t = new Pattern(a.bytes);
    const notes = [];
    const change = (line) => notes.push(line);

    const gone = leavers.filter((_, j) => i >= leaveAt[j]);
    for (const x of gone) t.setRaw("part.mute", [x.index], 1);
    if (typeof o.thinBefore === "number") {
      const thinning = leavers.filter((_, j) => leaveAt[j] > 1 && i === leaveAt[j] - 1);
      for (const x of thinning) thinPart(t, x.index, Math.max(1, Math.round(x.on.length * o.thinBefore)));
      if (thinning.length) change(`${partsText(thinning)} auf etwa ${Math.round(o.thinBefore * 100)} % der Steps ausgedünnt, geht im nächsten Übergang`);
    }
    if (leavers.length) change(gone.length ? `${partsText(gone)} gemutet` : "kein Part gemutet");

    const arrived = arrivers.filter((_, k) => i >= arriveAt[k]);
    for (const x of arrived) {
      const k = arrivers.indexOf(x);
      const fill = ARRIVE_FILL + (1 - ARRIVE_FILL) * ((i - arriveAt[k]) / Math.max(1, count - arriveAt[k]));
      t.bytes.set(b.bytes.subarray(partStart(x.index), partStart(x.index) + partStride), partStart(x.index));
      t.setRaw("part.mute", [x.index], 0);
      for (const id of ["part.ifxOn", "part.ifxType", "part.ifxEdit"]) t.setRaw(id, [x.index], a.raw(id, [x.index]));
      thinPart(t, x.index, Math.max(1, Math.round(x.on.length * fill)));
      change(`Part ${x.index + 1} von B kommt herein${i === arriveAt[k] ? "" : " (fester)"}, auf etwa ${Math.round(fill * 100)} % seiner Steps, Insert-Effekt wie in A`);
    }
    if (i === 1 && waiting.length) change(`${partsText(waiting)} von B (Gegenschläge) kommt erst mit B`);
    if (shared.length && direction !== "down" && i === 1) change(`${partsText(shared)} in A und B hörbar: der Part von B wird nicht kopiert, er bleibt wie in A`);

    if (valleySteps !== null && count >= 2 && !lead) {
      const u = i / (count + 1);
      const weight = (1 - Math.abs(u - VALLEY.at) / Math.max(VALLEY.at, 1 - VALLEY.at)) * clamp((count - 1) / 2, 0, 1);
      const cap = Math.max(Math.min(valleyParts, maxParts), Math.round(maxParts - weight * (maxParts - valleyParts)));
      const audible = () => summarize(t).parts.filter(x => x.audible);
      const rank = x => (leavers.includes(x) ? [0, leaveAt[leavers.indexOf(x)]] : shared.includes(x) ? [1, -x.on.length] : [2, -arriveAt[arrivers.indexOf(x)]]);
      const muteNow = [];
      for (let now = audible(); now.length > cap; now = audible()) {
        const pick = now.filter(x => x.index !== carry?.index).sort((x, y) => { const rx = rank(sa.parts[x.index]), ry = rank(sa.parts[y.index]); return (rx[0] - ry[0]) || (rx[1] - ry[1]); })[0];
        if (!pick) break;
        t.setRaw("part.mute", [pick.index], 1);
        muteNow.push(sa.parts[pick.index]);
      }
      if (muteNow.length) change(`Tal: ${partsText(muteNow)} gemutet (höchstens ${cap} Parts)`);
      const budget = (sa.audibleSteps + (sb.audibleSteps - sa.audibleSteps) * u) * (1 - weight * (1 - valleySteps));
      const now = summarize(t);
      if (now.audibleSteps > budget) {
        const ratio = budget / now.audibleSteps;
        let cut = 0;
        for (const x of now.parts.filter(y => y.audible)) cut += thinPart(t, x.index, Math.max(1, Math.round(x.on.length * ratio)));
        if (cut) change(`Tal: Steps auf etwa ${Math.round(budget)} (${cut} Steps aus)`);
      }
    }

    if (last && count >= 3 && direction !== "up" && shared.length) {
      const cut = Math.ceil(activeSteps(t) * BREATH);
      let cleared = 0;
      for (const x of shared) for (const s of onSteps(t, x.index)) if (s >= cut) { t.setRaw("step.on", [x.index, s], 0); cleared++; }
      if (cleared) change(`${partsText(shared)} (in A und B hörbar): Steps ab ${Math.round(BREATH * 100)} % des Patterns aus (${cleared} Steps)`);
    }

    if (accentAt.has(i)) {
      t.setRaw("part.mute", [accent.index], 0);
      change(`Akzent: Part ${accent.index + 1} (in A und B gemutet) klingt mit ${onSteps(t, accent.index).length} Steps`);
    }

    if (sweepMode === "run" && lead) {
      const open = direction === "down" ? Math.max(a.raw("part.cutoff", [lead.index]), CUTOFF.closed) : CUTOFF.open;
      const sweep = k => (direction === "down" ? open + (CUTOFF.closed - open) * smooth(k) : CUTOFF.closed + (CUTOFF.open - CUTOFF.closed) * smooth(k));
      const from = sweep((i - 1) / count), to = sweep(i / count);
      const slot = writeMotion(t, lead.index + 1, DEST.cutoff, ramp(t, from, to, k => k));
      if (slot !== null) {
        t.setRaw("part.motionMode", [lead.index], 1);
        change(`Part ${lead.index + 1}: Cutoff ${direction === "down" ? "schließt" : "öffnet"} von ${Math.round(from)} auf ${Math.round(to)} (Motion Sequence)`);
      } else change("kein freier Motion-Slot für den Filter");
    }
    const live = last && carry && summarize(t).parts[carry.index].audible ? carry : null;
    if (sweepMode === "tail" && last) {
      if (live && t.raw("part.filterType", [live.index]) !== 0) {
        const steps = activeSteps(t);
        const arc = tailArc(t.raw("part.cutoff", [live.index]), steps);
        if (writeMotion(t, live.index + 1, DEST.cutoff, arc.values) !== null) {
          t.setRaw("part.motionMode", [live.index], 1);
          change(`Part ${live.index + 1} (geht in B weiter): Cutoff-Bogen über die letzten ${arc.span} Steps, ${t.raw("part.cutoff", [live.index])} auf ${arc.peak}, zurück auf ${arc.rest} (Motion Sequence)`);
        } else change("kein freier Motion-Slot für den Filterbogen");
      } else change("kein Part, der in B weiterklingt und einen Filter hat, kein Filterbogen");
    }
    if (last && live && clip !== null && t.raw("part.decay", [live.index]) > clip) {
      change(`Part ${live.index + 1}: Decay ${t.raw("part.decay", [live.index])} auf ${clip}`);
      t.setRaw("part.decay", [live.index], clip);
    }
    if (last && live && o.insertMotion && t.raw("part.ifxOn", [live.index]) === 0) {
      const n = activeSteps(t);
      if (writeSwitchMotion(t, live.index + 1, DEST.ifxOn, Math.round(n * 0.5), Math.round(n * 0.75)) !== null) {
        t.setRaw("part.motionMode", [live.index], 1);
        change(`Part ${live.index + 1}: Insert-Effekt von Step ${Math.round(n * 0.5)} bis ${Math.round(n * 0.75)} an (Motion Sequence)`);
      } else change("kein freier Motion-Slot für den Insert");
    }

    if (padMode === "corner") {
      const x0 = a.raw("pattern.mfx.padX"), y0 = a.raw("pattern.mfx.padY");
      const px = k => x0 + (CORNER.x - x0) * ease(k), py = k => y0 + (CORNER.y - y0) * ease(k);
      const sx = writeMotion(t, MOTION_MFX, DEST.mfxX, ramp(t, px((i - 1) / count), px(i / count), ease));
      const sy = writeMotion(t, MOTION_MFX, DEST.mfxY, ramp(t, py((i - 1) / count), py(i / count), ease));
      if (sx !== null && sy !== null) {
        t.setRaw("pattern.mfx.padX", [], clamp(Math.round(px(i / count)), 0, 127));
        t.setRaw("pattern.mfx.padY", [], clamp(Math.round(py(i / count)), 0, 127));
        change(`Master FX Pad: X ${Math.round(px((i - 1) / count))} auf ${Math.round(px(i / count))}, Y ${Math.round(py((i - 1) / count))} auf ${Math.round(py(i / count))} (Motion Sequence)`);
      } else change("kein freier Motion-Slot für den Master-FX-Pad");
    }
    if (held) {
      const pad = i === 1 ? HOLD_PAD.first : HOLD_PAD.then;
      t.setRaw("pattern.mfx.padX", [], pad.x);
      t.setRaw("pattern.mfx.padY", [], pad.y);
      if (!last) { setHold(t, 1); change(`Master FX Hold an, Pad X ${pad.x} / Y ${pad.y}`); }
      else if (sa.hold === 0) { setHold(t, 0); change(`MFX Hold aus, Pad bleibt bei X ${pad.x} / Y ${pad.y}`); }
    } else if (last && t.raw("pattern.mfx.hold") === 1) { setHold(t, 0); change("MFX Hold aus"); }
    if (padMode === "release" && last) {
      const n = activeSteps(t), from = Math.round(n * (1 - RELEASE_SPAN));
      const x0 = t.raw("pattern.mfx.padX"), y0 = t.raw("pattern.mfx.padY");
      const run = (v0, v1) => Array.from({ length: STEPS }, (_, s) => clamp(Math.round(v0 + (v1 - v0) * ease(clamp((s - from) / Math.max(1, n - 1 - from), 0, 1))), 0, 127));
      const sx = writeMotion(t, MOTION_MFX, DEST.mfxX, run(x0, CORNER.x)), sy = writeMotion(t, MOTION_MFX, DEST.mfxY, run(y0, CORNER.y));
      if (sx !== null && sy !== null) {
        t.setRaw("pattern.mfx.padX", [], CORNER.x);
        t.setRaw("pattern.mfx.padY", [], CORNER.y);
        change(`Master FX Pad läuft in den letzten ${n - from} Steps von X ${x0} / Y ${y0} in die Ecke X ${CORNER.x} / Y ${CORNER.y} (Motion Sequence)`);
      } else change("kein freier Motion-Slot für den Master-FX-Pad");
    }

    const mfxSetting = o.mfx ?? "keep";
    if (last && typeof mfxSetting === "number" && mfxSetting !== sa.mfx) {
      t.setRaw("pattern.mfx.type", [], mfxSetting);
      change(`Master-FX-Typ ${sa.mfx} auf ${mfxSetting}`);
    }

    if (tempoMode !== "keep" && sa.tempo !== sb.tempo) {
      const raw = tempoAt(sa.tempo, sb.tempo, i, count, tempoMode);
      if (raw !== sa.tempo) { t.setRaw("pattern.tempo", [], raw); change(`Tempo ${bpm(sa.tempo)} auf ${bpm(raw)}`); }
    }

    const name = cleanName(o.names?.[i - 1]) || `PRE${stem}${i - 1}`.slice(0, 16);
    t.setRaw("pattern.name", [], name);
    if (o.chain && o.slots) {
      const target = i < count ? o.slots[i] : o.slotB;
      if (target) { t.setRaw("pattern.chainTo", [], target); t.setRaw("pattern.chainRepeat", [], 0); change(`Chain To ${target}`); }
    } else t.setRaw("pattern.chainTo", [], 0);

    const fx = effectChanges(previous, t);
    if (fx.length) change(`Effekt-Wechsel gegenüber dem Vorgänger: ${fx.join(", ")}`);
    items.push({ index: i, name, slot: o.slots?.[i - 1] ?? null, pattern: t, notes, fx });
    previous = t;
  }
  return { direction, items, arrivalFx: effectChanges(previous, b), heavy: heavyInserts(previous) };
}

/** Findings on a transition that A did not already have; empty means fine. */
export function checkTransition(t, a) {
  const out = [];
  const fp = frameProblem(t.bytes);
  if (fp) out.push({ severity: "error", message: `Rahmen: ${fp}` });
  const before = new Set(lintPattern(a.bytes).map(f => f.code));
  for (const f of lintPattern(t.bytes)) if (!before.has(f.code)) out.push({ severity: f.severity, message: f.message });
  const tempo = t.raw("pattern.tempo");
  if (tempo < 200 || tempo > 3000) out.push({ severity: "error", message: `Tempo ${tempo} liegt außerhalb von 200 bis 3000` });
  if (t.raw("pattern.chainTo") > 250) out.push({ severity: "error", message: "Chain To liegt über 250" });
  for (let s = 0; s < MOTION_SLOTS; s++) {
    const part = t.raw("motion.part", [s]);
    if (part > 17) out.push({ severity: "error", message: `Motion-Slot ${s}: Part ${part}` });
    if (part && t.raw("motion.destination", [s]) > 19) out.push({ severity: "error", message: `Motion-Slot ${s}: Ziel ${t.raw("motion.destination", [s])}` });
    if (part && part <= PARTS && t.raw("part.motionMode", [part - 1]) === 0) out.push({ severity: "warn", message: `Motion-Slot ${s} liegt auf Part ${part}, dessen Motion Sequence aus ist` });
  }
  return out;
}

/** The first run of n free slots above `near`, else any n free ones. */
export function pickSlots(set, n, near = 0, taken = []) {
  const free = [];
  for (let s = 1; s <= set.count; s++) if (!taken.includes(s) && isFree(set.pattern(s))) free.push(s);
  const run = start => { for (let k = 0; k < n; k++) if (!free.includes(start + k)) return false; return true; };
  const starts = [...free.filter(s => s > near), ...free.filter(s => s <= near)];
  const at = starts.find(run);
  return at ? Array.from({ length: n }, (_, k) => at + k) : free.slice(0, n);
}

const DIRECTION_TEXT = { down: "ausdünnen (build-down)", up: "aufbauen (build-up)", blend: "überblenden (A geht, B kommt)" };

export function describe(result, sa, sb, a, b, nA, nB) {
  const { items, direction, arrivalFx, heavy } = result;
  const lines = [];
  lines.push(`Übergang von Pattern ${nameOf(nA, a)} (${bpm(sa.tempo)}) zu Pattern ${nameOf(nB, b)} (${bpm(sb.tempo)}), Richtung ${DIRECTION_TEXT[direction]}, ${items.length} Pattern${items.length > 1 ? "s" : ""}.`);
  for (const it of items) {
    lines.push("");
    lines.push(`${it.slot ? `Slot ${it.slot}` : `Übergang ${it.index}`}, Name ${it.name}`);
    for (const n of it.notes) lines.push(`  - ${n}`);
  }
  lines.push("");
  if (heavy.length >= HEAVY_REPORT) lines.push(`Die Übergänge tragen ${heavy.length} Parts mit schweren Insert-Typen (${heavy.join(", ")}). Die Effekte rechnen immer, auch aus und stumm, und kosten Polyphonie; Korg rät zu IFX 1 (Punch) auf Parts ohne Insert. Der Generator ändert keinen Typ.`);
  lines.push(arrivalFx.length
    ? `Wechsel in B: Effekt-Wechsel in ${arrivalFx.length} Slots (${arrivalFx.join(", ")}). Dabei baut das Gerät diese Effekte neu auf; hergeleitet, am Gerät nicht gemessen: eine kurze Lücke im Ton, einmal in der ganzen Kette.`
    : "Wechsel in B: kein Effekt-Wechsel.");
  return lines.join("\n");
}
