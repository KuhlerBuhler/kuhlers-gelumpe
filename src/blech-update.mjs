/**
 * Updating a file that already carries BLECH (docs/patcher.md): the current set goes straight over the patches of an
 * older release, no original needed. A change is a hook site of Korg's code (the patch writes a branch) or a free area
 * (0xFF or 0x00 in the original) with new code. The current set rewrites every hook site an earlier release wrote, at
 * the same place and length; free areas go back to their fill first. `data/known-releases.json` keeps per build only
 * hashes: of the original bytes of each region, of what each release wrote there, and of the effect presets
 * (`catalog`). tools/known-releases.mjs makes it from the release tags.
 */
import { applyPatches } from "./patch.mjs";
import { APPEND_FORMAT, appendedRecords } from "./fx-append.mjs";
import { locatePresets, menuLength, nameAt, recordOf, RECORD, RESERVE, setMenuLength } from "./presets.mjs";
import { FxRecord } from "./record.mjs";
import { buildOf, sha256 } from "./firmware.mjs";
import { field } from "./map/index.mjs";
import { MAX_BYTES, validateAnimation } from "./loading-anim.mjs";

export const KNOWN_FORMAT = "gelumpe-known-releases";
/** Hashes of regions are kept as their first 16 hex digits. */
const short = hash => hash.slice(0, 16);

/** A hash of a record that works without await (cyrb53); only tells the few catalog presets of a menu apart. */
function recordHash(bytes) {
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (const b of bytes) {
    h1 = Math.imul(h1 ^ b, 2654435761);
    h2 = Math.imul(h2 ^ b, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return ((h2 >>> 0) * 0x100000000 + (h1 >>> 0)).toString(16);
}

const fillOf = bytes => (bytes.every(b => b === 0xff) ? 0xff : bytes.every(b => b === 0) ? 0 : -1);

export const emptyKnown = () => ({ format: KNOWN_FORMAT, version: 1, releases: [], builds: {}, catalog: {} });

/**
 * Adds what `patches` write on `base` (a file in the original state of `build`) to `known` as release `release`.
 * A region is [file, length, patch id, fill (0xFF, 0 or -1 for a hook site), original hash, [written hashes]].
 */
export async function addRelease(known, release, build, base, patches) {
  const res = await applyPatches(base, patches);
  if (!res.ok) throw new Error(`${release}: ${res.reasons.join(" ")}`);
  if (!known.releases.includes(release)) known.releases.push(release);
  const regions = (known.builds[build] ??= []);
  for (const s of res.spans) {
    if (s.field) continue;
    const before = base.subarray(s.file, s.file + s.length);
    const written = short(await sha256(res.bytes.subarray(s.file, s.file + s.length)));
    const found = regions.find(r => r[0] === s.file && r[1] === s.length);
    if (!found) regions.push([s.file, s.length, s.patch, fillOf(before), short(await sha256(before)), [written]]);
    else if (!found[5].includes(written)) found[5].push(written);
  }
  regions.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  addCatalog(known, build, base, res.bytes, patches);
}

/**
 * Adds the hashes of the effect presets `patches` put into `patched` (made from `base`) to `known.catalog`. A preset the
 * base has by name already is the firmware's own (Hacktribe's remakes, its Short Delay) and is left out. tools/known-releases.mjs
 * also calls it alone for further Hacktribe files: their presets borrow units from the firmware's own records, so the
 * records, and with them the hashes, differ between Hacktribe versions.
 */
export function addCatalog(known, build, base, patched, patches) {
  const catalog = (known.catalog[build] ??= {});
  for (const patch of patches.filter(p => p?.format === APPEND_FORMAT)) {
    const own = new Set(appendedRecords(base, patch).map(r => `${r.kind}|${r.name}`));
    for (const { kind, name, record } of appendedRecords(patched, patch)) {
      if (own.has(`${kind}|${name}`)) continue;
      const hashes = (catalog[`${kind}|${name}`] ??= []);
      const hash = recordHash(record);
      if (!hashes.includes(hash)) hashes.push(hash);
    }
  }
}

/**
 * Takes the presets a release put behind the firmware's menu back out of `bytes` (in place), so the current set lays
 * them out again as on a file straight from the original: a preset a later release dropped leaves no gap, and the slots
 * come out the same however the file got here (docs/effekt-katalog.md). The records are found through `bytes`:
 * preset-tables keeps its array in a free area, which `cleaned` has back at its fill. Only the run of slots at the end of a menu whose
 * every record is one a release wrote (by its hash) goes; it stops at the first other record, so the firmware's own
 * presets and the user's own behind ours stay, and then nothing behind them moves.
 * least-code: a freed slot gets the record of Korg's last own slot (100), which is the empty one on Korg 2.02 and
 * Hacktribe. A slot in the reserve of preset-tables (beyond 100) is never freed; a catalog that big needs the reserve's
 * own empty record and its array entry put back.
 */
function dropCatalogTail(bytes, cleaned, catalog) {
  if (!locatePresets(bytes)) return;
  for (const kind of ["ifx", "mfx"]) {
    const length = menuLength(bytes, kind).value;
    let from = length + 1;
    while (from > 1) {
      const at = recordOf(bytes, kind, from - 1);
      const record = bytes.slice(at.file, at.file + RECORD);
      if (!catalog[`${kind}|${new FxRecord(record, kind).name}`]?.includes(recordHash(record))) break;
      from--;
    }
    const last = RESERVE[kind].first - 1;
    const empty = recordOf(bytes, kind, last);
    if (from > length || length >= last || nameAt(bytes, empty.file)) continue;
    const blank = bytes.slice(empty.file, empty.file + RECORD);
    for (let slot = from; slot <= length; slot++) cleaned.set(blank, recordOf(bytes, kind, slot).file);
    setMenuLength(cleaned, kind, from - 1);
  }
}

/**
 * The bytes of the user's own loading animation in its slot (the map field loadingAnim), as [from, to), or null. The slot
 * is user data: FF without an animation, a file the firmware accepts with one. Earlier releases kept code there, which
 * is not an animation and so not user data.
 */
function animationAt(bytes) {
  const from = field("loadingAnim").where.offset;
  const slot = bytes.subarray(from, from + MAX_BYTES);
  if (validateAnimation(slot) !== null) return null;
  return [from, from + new DataView(slot.buffer, slot.byteOffset).getUint32(12, true)];
}

/**
 * Whether `bytes` is a file one of the known releases patched, and what the current set needs to go over it.
 * Every region any known release writes must hold the original bytes or what a release wrote there. A region of a
 * release with another outline than the one that patched the file passes when its bytes are covered by regions that
 * hold written content and are otherwise fill; the user's loading animation is neither checked nor reset. Any other content, or no trace of BLECH at all, is a refusal.
 * @returns {Promise<{ok: true, bytes: Uint8Array, present: string[], options: object} | {ok: false, why: string}>}
 *   `bytes` is the file with the free areas reset to their fill, `present` the patch ids whose hook sites are in it,
 *   `options` goes to applyPatches: the hook sites the file holds count as expected and must all be written again (a
 *   branch left at a site the set no longer writes jumps into code that is gone), and an effect preset an older
 *   release wrote is written again, a preset of the user's own with the same name stays.
 */
export async function recogniseBlech(bytes, known) {
  const build = buildOf(bytes);
  const regions = known?.format === KNOWN_FORMAT && known.version === 1 ? known.builds?.[build] : null;
  if (!regions?.length) return { ok: false, why: "build" };
  const states = [];
  for (const [file, length, , , original, written] of regions) {
    const hash = short(await sha256(bytes.subarray(file, file + length)));
    states.push(hash === original ? "original" : written.includes(hash) ? "new" : "other");
  }
  const covered = new Uint8Array(bytes.length);
  const own = animationAt(bytes);
  if (own) covered.fill(1, own[0], own[1]);
  regions.forEach(([file, length], i) => { if (states[i] === "new") covered.fill(1, file, file + length); });
  for (let i = 0; i < regions.length; i++) {
    const [file, length, , fill] = regions[i];
    if (states[i] !== "other") continue;
    for (let at = file; at < file + length; at++) if (!covered[at] && bytes[at] !== fill) return { ok: false, why: "region" };
  }
  if (!states.includes("new")) return { ok: false, why: "none" };
  const cleaned = Uint8Array.from(bytes);
  const present = new Set();
  const held = [];
  regions.forEach(([file, length, id, fill], i) => {
    if (states[i] === "original" || (states[i] === "other" && fill < 0)) return;
    if (fill < 0) { present.add(id); held.push([file, length, id]); return; }
    const end = file + length;
    if (!own || end <= own[0] || file >= own[1]) cleaned.fill(fill, file, end);
    else {
      if (file < own[0]) cleaned.fill(fill, file, own[0]);
      if (end > own[1]) cleaned.fill(fill, own[1], end);
    }
  });
  const byKey = new Map(regions.map(r => [`${r[0]}+${r[1]}`, r[5]]));
  const catalog = known.catalog?.[build] ?? {};
  dropCatalogTail(bytes, cleaned, catalog);
  return {
    ok: true,
    bytes: cleaned,
    present: [...present],
    options: {
      accept: (file, length, hash) => byKey.get(`${file}+${length}`)?.includes(short(hash)) ?? false,
      refresh: (kind, name, record) => catalog[`${kind}|${name}`]?.includes(recordHash(record)) ?? false,
      held,
    },
  };
}
