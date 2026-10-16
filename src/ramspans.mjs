/**
 * The RAM a patch uses beyond the bytes it writes (docs/patcher.md, "RAM der Patches").
 *
 * A patch says what it keeps in RAM at run time next to `changes`:
 *
 *   ram:    [ { at: "0xC0182000", length: 256, what, source } ]
 *   shares: [ { at: "0xC0180F10", length: 4, with: "<patch id>", what, source } ]
 *
 * `ram` is memory of the patch's own: state words, buffers, a pool. `source` names where the size
 * comes from, "<file>:<SYMBOL>" in the tool that builds the patch. `shares` is a word of another
 * patch's area that this one reads or writes; with that patch in the set it has to lie inside an area it declares.
 * A patch without RAM of its own says `ram: []`. What a patch writes into firmware objects it
 * does not own (the display buffer, panel ring) is not declared here.
 *
 * Nothing in here reads firmware. A change lands at RAM `file - 0x100 + 0xC0000000`.
 */
import { field, typeOf } from "./map/index.mjs";

const IMAGE_BASE = 0xC0000000;
const HEADER = 0x100;
const hex = n => `0x${n.toString(16).toUpperCase()}`;
const span = a => `${hex(a.start)}..${hex(a.end)}`;

/** The bytes of the image a patch writes, as { patch, start, end, what } in RAM addresses. */
export function writtenAreas(patch) {
  const out = [];
  for (const change of patch.changes ?? []) {
    try {
      let file = change.file;
      let length = change.copy !== undefined ? change.copy.length : change.bytes.length / 2;
      if (change.field !== undefined) {
        const f = field(change.field);
        file = f.where.offset;
        length = typeOf(f).width;
      }
      if (!Number.isInteger(file) || !Number.isInteger(length)) continue;
      const start = file - HEADER + IMAGE_BASE;
      out.push({ patch: patch.id, start, end: start + length, what: change.note ?? change.field ?? "change" });
    } catch {
      continue; // applyPatches reports a change it cannot place
    }
  }
  return out;
}

const parseAt = (entry, patch, key) => {
  const at = typeof entry.at === "string" && /^0x[0-9a-f]+$/i.test(entry.at) ? Number(entry.at) : NaN;
  if (!Number.isInteger(at) || !Number.isInteger(entry.length) || entry.length <= 0) {
    throw new TypeError(`${patch.id}: ${key} needs at as a hex string and a length above 0 (${JSON.stringify(entry)})`);
  }
  return { patch: patch.id, start: at, end: at + entry.length, what: entry.what ?? "?", with: entry.with, source: entry.source };
};

/** Own areas and shares a patch declares. Throws on an entry that is not well formed. */
export function declaredAreas(patch) {
  return {
    own: (patch.ram ?? []).map(e => parseAt(e, patch, "ram")),
    shares: (patch.shares ?? []).map(e => parseAt(e, patch, "shares")),
  };
}

const clash = (a, b) => a.start < b.end && b.start < a.end;
const label = a => `${a.patch}: ${a.what} ${span(a)}`;

/**
 * Reasons why a set of patches (one per id, already chosen for a build) does not fit together in RAM.
 * Compared are the declared areas with each other, with the bytes every patch writes, and the shares
 * with the area they name. `written: false` leaves out the pairs of two written spans, which
 * applyPatches finds on the file itself.
 * @param {object[]} patches
 * @param {{ written?: boolean }} [options]
 * @returns {string[]}
 */
export function checkRam(patches, { written = true } = {}) {
  const reasons = [];
  const ids = new Set(patches.map(p => p.id));
  const writes = [];
  const own = [];
  const shares = [];
  for (const patch of patches) {
    let declared;
    try {
      declared = declaredAreas(patch);
    } catch (error) {
      reasons.push(error.message);
      continue;
    }
    writes.push(...writtenAreas(patch));
    own.push(...declared.own);
    shares.push(...declared.shares);
  }
  const pairs = (xs, ys, same) => {
    for (let i = 0; i < xs.length; i++) {
      for (let j = same ? i + 1 : 0; j < ys.length; j++) {
        if (clash(xs[i], ys[j])) reasons.push(`${label(xs[i])} overlaps ${label(ys[j])}`);
      }
    }
  };
  pairs(own, own, true);
  pairs(own, writes, false);
  if (written) pairs(writes, writes, true);
  for (const s of shares) {
    if (typeof s.with !== "string" || s.with === s.patch) {
      reasons.push(`${label(s)} shares with ${s.with ?? "nobody"}, which is not another patch`);
      continue;
    }
    // an owner that is not in this list leaves the word to nobody: a patch may be applied without it
    if (ids.has(s.with) && !own.some(o => o.patch === s.with && o.start <= s.start && s.end <= o.end)) {
      reasons.push(`${label(s)} lies in no area that ${s.with} declares`);
    }
    for (const o of own) if (o.patch !== s.with && clash(s, o)) reasons.push(`${label(s)} overlaps ${label(o)}`);
    for (const w of writes) if (clash(s, w)) reasons.push(`${label(s)} overlaps ${label(w)}`);
  }
  return reasons;
}

/**
 * Reasons why a declared area sits where it must not. It has to lie wholly in one free run
 * (data/patch-ram.mjs): RAM nobody has explained stays blocked, as in docs/speicherbereiche.md. Where it
 * misses, the reason says which protected region it hits (data/protected.mjs), and whether it is the image.
 * @param {object[]} patches
 * @param {{ free: {start: number, end: number}[], regions: object[], window: {start: number, end: number}, image: {start: number, end: number} }} where
 * @returns {string[]}
 */
export function checkRamPlacement(patches, { free, regions, window, image }) {
  const reasons = [];
  for (const patch of patches) {
    let own;
    try {
      ({ own } = declaredAreas(patch));
    } catch (error) {
      reasons.push(error.message);
      continue;
    }
    for (const area of own) {
      if (free.some(run => run.start <= area.start && area.end <= run.end)) continue;
      if (area.start < window.start || area.end > window.end) reasons.push(`${label(area)} is outside the RAM window`);
      else if (clash(area, image)) reasons.push(`${label(area)} is in the firmware image but not in one free run of it`);
      else reasons.push(`${label(area)} is in no free run, RAM nobody has explained stays blocked`);
      for (const region of regions) {
        if (region.space === "ram" && region.deny && region.id !== image.id && clash(area, region)) {
          reasons.push(`${label(area)} overlaps the protected region ${region.id} ${span(region)}`);
        }
      }
    }
  }
  return reasons;
}
