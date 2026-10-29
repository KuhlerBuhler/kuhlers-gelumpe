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
import { buildOf, sha256 } from "./firmware.mjs";

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
  const catalog = (known.catalog[build] ??= {});
  for (const patch of patches.filter(p => p?.format === APPEND_FORMAT)) {
    for (const { kind, name, record } of appendedRecords(res.bytes, patch)) {
      const hashes = (catalog[`${kind}|${name}`] ??= []);
      const hash = recordHash(record);
      if (!hashes.includes(hash)) hashes.push(hash);
    }
  }
}

/**
 * Whether `bytes` is a file one of the known releases patched, and what the current set needs to go over it.
 * Every region any known release writes must hold the original bytes or what a release wrote there. A region of a
 * release with another outline than the one that patched the file passes when its bytes are covered by regions that
 * hold written content and are otherwise fill. Any other content, or no trace of BLECH at all, is a refusal.
 * @returns {Promise<{ok: true, bytes: Uint8Array, present: string[], options: object} | {ok: false, why: string}>}
 *   `bytes` is the file with the free areas reset to their fill, `present` the patch ids whose hook sites are in it,
 *   `options` goes to applyPatches: the hook sites the file holds count as expected, and an effect preset an older
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
  regions.forEach(([file, length], i) => { if (states[i] === "new") covered.fill(1, file, file + length); });
  for (let i = 0; i < regions.length; i++) {
    const [file, length, , fill] = regions[i];
    if (states[i] !== "other") continue;
    for (let at = file; at < file + length; at++) if (!covered[at] && bytes[at] !== fill) return { ok: false, why: "region" };
  }
  if (!states.includes("new")) return { ok: false, why: "none" };
  const cleaned = Uint8Array.from(bytes);
  const present = new Set();
  regions.forEach(([file, length, id, fill], i) => {
    if (states[i] === "original" || (states[i] === "other" && fill < 0)) return;
    if (fill >= 0) cleaned.fill(fill, file, file + length);
    else present.add(id);
  });
  const byKey = new Map(regions.map(r => [`${r[0]}+${r[1]}`, r[5]]));
  const catalog = known.catalog?.[build] ?? {};
  return {
    ok: true,
    bytes: cleaned,
    present: [...present],
    options: {
      accept: (file, length, hash) => byKey.get(`${file}+${length}`)?.includes(short(hash)) ?? false,
      refresh: (kind, name, record) => catalog[`${kind}|${name}`]?.includes(recordHash(record)) ?? false,
    },
  };
}
