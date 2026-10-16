/**
 * Patches on a copy of the user's SYSTEM.VSB (docs/patcher.md).
 *
 * A patch carries only what it writes, never Korg bytes it leaves alone:
 *
 *   { format: "gelumpe-patch", version: 1, id, name,
 *     changes: [ { field: "splash", bytes: "<hex>" },
 *                { file: 0x1a2100, bytes: "<hex>", expect: "<sha256 of the bytes it replaces>" },
 *                { file: 0x1b3d00, copy: { file: 0xe3f8, length: 72, expect: "<sha256 of the source>" },
 *                  over: [ { at: 8, bytes: "<hex>" } ], expect: "<sha256 of the bytes it replaces>" } ],
 *     startPhase: [ { file, length, why } ],
 *     hooks: [ { site, kind, chain, position, swallow } ],
 *     ram: [ { at, length, what, source } ], shares: [ { at, length, with, what, source } ] }
 *
 * A field change goes where the device map puts that field and is data whose
 * format the map knows; the emulator check lets it be read at start. A raw
 * change only applies over exactly the bytes it was made for. A copy change
 * takes its bytes from the user's own VSB when it is applied, with `over`
 * written on top, so a patch can reuse firmware tables without carrying any.
 * `startPhase` names the spans that run or are read before the main screen
 * and says why; the patch only asks, whoever runs the emulator check passes
 * them on (`allowCode`). `hooks` is optional and says where a code patch hooks
 * in; src/hooks.mjs refuses patches that collide there. `ram` and `shares` are optional and name
 * the RAM the patch keeps at run time beyond its changes; src/ramspans.mjs refuses patches whose
 * areas overlap each other or a written byte. `builds` names the
 * firmware builds a patch is made for ("hacktribe", "stock"; default only
 * "hacktribe"). Patches that share an `id` are variants of one change, one
 * per build, and the base firmware picks the variant (`selectFor`). `notNeededOn` names builds that already have
 * what the patch adds ("hacktribe"); a set skips the patch there instead of refusing.
 */
import { field, typeOf } from "./map/index.mjs";
import { identifyBase, sha256 } from "./firmware.mjs";
import { checkHooks } from "./hooks.mjs";
import { checkRam } from "./ramspans.mjs";

export const PATCH_FORMAT = "gelumpe-patch";
export const BUILD_NAMES = { hacktribe: "Hacktribe 2.02", stock: "Korgs Original 2.02", synth: "der blauen Electribe 2 (Synth) 2.02" };
export const buildsOf = patch => (Array.isArray(patch?.builds) ? patch.builds : ["hacktribe"]);
const HEADER = 0x100;
const SIZE = 0x200100;

export function fromHex(text) {
  if (typeof text !== "string" || text.length % 2 || /[^0-9a-f]/i.test(text)) throw new TypeError("bytes are an even-length hex string");
  return Uint8Array.from(text.match(/../g) ?? [], h => parseInt(h, 16));
}

export const toHex = bytes => Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");

/** Where a change goes, as [file, bytes, allowed at start]. Throws on anything malformed. */
async function locate(change, vsb) {
  if (change.copy !== undefined) return locateCopy(change, vsb);
  const bytes = fromHex(change.bytes);
  if (change.field !== undefined) {
    const f = field(change.field);
    if (!f.transport.includes("firmware") || f.edit === "readonly" || f.where?.offset === undefined) {
      throw new Error(`${change.field} is not a firmware field a patch may write`);
    }
    if (bytes.length !== typeOf(f).width) throw new RangeError(`${change.field} takes ${typeOf(f).width} bytes, got ${bytes.length}`);
    return { file: f.where.offset, bytes, field: f.id };
  }
  if (!Number.isInteger(change.file) || typeof change.expect !== "string") throw new Error("a raw change needs file and expect");
  return { file: change.file, bytes, expect: change.expect.toLowerCase() };
}

async function locateCopy(change, vsb) {
  const { file: from, length, expect: sourceHash } = change.copy;
  if (!Number.isInteger(change.file) || typeof change.expect !== "string") throw new Error("a copy change needs file and expect");
  if (!Number.isInteger(from) || !Number.isInteger(length) || length <= 0 || from < HEADER || from + length > SIZE) {
    throw new RangeError("a copy reads from inside the image");
  }
  const source = vsb.subarray(from, from + length);
  if (typeof sourceHash !== "string" || await sha256(source) !== sourceHash.toLowerCase()) {
    throw new Error(`copy from 0x${from.toString(16)}: the source is not what the patch was made for`);
  }
  const bytes = Uint8Array.from(source);
  for (const part of change.over ?? []) {
    const over = fromHex(part.bytes);
    if (!Number.isInteger(part.at) || part.at < 0 || part.at + over.length > length) throw new RangeError("over lies inside the copy");
    bytes.set(over, part.at);
  }
  return { file: change.file, bytes, expect: change.expect.toLowerCase() };
}

/**
 * The patches of a list that apply to a base build: per `id` the variant whose `builds` name it.
 * A patch with no variant for the build is a reason, so a set never half-applies to firmware it was not made for,
 * unless the patch says the build does not need it (`notNeededOn`).
 */
export function selectFor(patches, build) {
  const reasons = [];
  const chosen = [];
  const ids = [...new Set(patches.map(p => p?.id))];
  for (const id of ids) {
    const variants = patches.filter(p => p?.id === id);
    const fit = variants.filter(p => buildsOf(p).includes(build));
    if (fit.length === 1) chosen.push(fit[0]);
    else if (fit.length > 1) reasons.push(`${id}: mehrere Fassungen für ${BUILD_NAMES[build] ?? build}`);
    else if (variants.some(p => Array.isArray(p.notNeededOn) && p.notNeededOn.includes(build))) continue;
    else reasons.push(`${id}: ist nicht für ${BUILD_NAMES[build] ?? build} gemacht`);
  }
  return { patches: chosen, reasons };
}

/**
 * The patches written into a copy of the VSB, or the reasons why not.
 * `allow` lists the field spans for the emulator check (check.py --allow).
 * `allowCode` is what the patches say runs at start, [file, length] spans for check.py --allow-code.
 * `dependencies` are hook dependencies between the patches, reported and not refused.
 * @returns {Promise<{ok: boolean, bytes?: Uint8Array, reasons: string[], dependencies: string[], spans: object[], allow: number[][], allowCode: number[][]}>}
 */
export async function applyPatches(vsb, patchList) {
  const reasons = [];
  const spans = [];
  const none = (why, dependencies = []) => ({ ok: false, reasons: why, dependencies, spans, allow: [], allowCode: [] });
  const base = await identifyBase(vsb);
  if (!base.ok) return none(base.reasons);
  const picked = selectFor(patchList, base.build);
  if (picked.reasons.length) return none(picked.reasons);
  const patches = picked.patches;
  const { dependencies, ...hooks } = checkHooks(patches);
  if (!hooks.ok) return none(hooks.reasons, dependencies);
  const bytes = Uint8Array.from(vsb);
  for (const patch of patches) {
    if (patch?.format !== PATCH_FORMAT || patch.version !== 1 || !Array.isArray(patch.changes) || !patch.changes.length) {
      reasons.push(`${patch?.id ?? "?"}: kein Patch im Format ${PATCH_FORMAT} 1`);
      continue;
    }
    for (const change of patch.changes) {
      let at;
      try { at = await locate(change, vsb); } catch (error) { reasons.push(`${patch.id}: ${error.message}`); continue; }
      const end = at.file + at.bytes.length;
      if (at.file < HEADER || end > SIZE || at.bytes.length === 0) {
        reasons.push(`${patch.id}: 0x${at.file.toString(16)} liegt außerhalb des Abbilds`);
        continue;
      }
      const clash = spans.find(s => at.file < s.file + s.length && s.file < end);
      if (clash) {
        reasons.push(`${patch.id}: 0x${at.file.toString(16)} überschneidet sich mit ${clash.patch}`);
        continue;
      }
      if (at.expect && await sha256(vsb.subarray(at.file, end)) !== at.expect) {
        reasons.push(`${patch.id}: an 0x${at.file.toString(16)} stehen andere Bytes, als der Patch erwartet`);
        continue;
      }
      bytes.set(at.bytes, at.file);
      spans.push({ patch: patch.id, file: at.file, length: at.bytes.length, field: at.field ?? null });
    }
  }
  reasons.push(...checkRam(patches.filter(p => p?.format === PATCH_FORMAT && Array.isArray(p.changes)), { written: false }));
  if (reasons.length) return { ok: false, reasons, dependencies, spans, allow: [], allowCode: [] };
  const after = await identifyBase(bytes);
  if (!after.ok) return none(after.reasons, dependencies);
  const allowCode = patches.flatMap(p => (p.startPhase ?? []).map(s => [s.file, s.length]));
  return { ok: true, bytes, reasons, dependencies, spans, allow: spans.filter(s => s.field).map(s => [s.file, s.length]), allowCode };
}

/** Per patch: whether every change of it is already in the VSB byte for byte; an unreadable change counts as absent. */
export async function patchesPresent(vsb, patches) {
  const out = [];
  for (const patch of patches) {
    let present = patch?.format === PATCH_FORMAT && Array.isArray(patch.changes) && patch.changes.length > 0;
    for (const change of present ? patch.changes : []) {
      try {
        const at = await locate(change, vsb);
        const end = at.file + at.bytes.length;
        if (at.file < HEADER || end > vsb.length || !at.bytes.every((b, i) => vsb[at.file + i] === b)) present = false;
      } catch {
        present = false;
      }
      if (!present) break;
    }
    out.push({ id: patch?.id, present });
  }
  return out;
}

// The start image: 8 pages of 128 columns, bit 7 the top row of a page
// (measure:2026-10-10/startphase). Pixels here are row by row, 1 = lit.
export const SPLASH_W = 128;
export const SPLASH_H = 64;

export function splashToPixels(bytes) {
  const px = new Uint8Array(SPLASH_W * SPLASH_H);
  for (let y = 0; y < SPLASH_H; y++) {
    for (let x = 0; x < SPLASH_W; x++) px[y * SPLASH_W + x] = (bytes[(y >> 3) * SPLASH_W + x] >> (7 - (y & 7))) & 1;
  }
  return px;
}

export function pixelsToSplash(px) {
  if (px.length !== SPLASH_W * SPLASH_H) throw new RangeError(`a start image has ${SPLASH_W * SPLASH_H} pixels`);
  const bytes = new Uint8Array(SPLASH_W * SPLASH_H / 8);
  for (let y = 0; y < SPLASH_H; y++) {
    for (let x = 0; x < SPLASH_W; x++) if (px[y * SPLASH_W + x]) bytes[(y >> 3) * SPLASH_W + x] |= 0x80 >> (y & 7);
  }
  return bytes;
}

export const splashPatch = (px, name = "Startbild") => ({
  format: PATCH_FORMAT, version: 1, id: "splash", name,
  changes: [{ field: "splash", bytes: toHex(pixelsToSplash(px)) }],
});
