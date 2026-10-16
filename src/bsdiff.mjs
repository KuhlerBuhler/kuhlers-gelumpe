/**
 * Applying a bsdiff patch (the BSDIFF40 format that Python's bsdiff4 writes, as Hacktribe's firmware patch is).
 * Colin Percival's format: a 32-byte header, then three bzip2 streams (control, diff, extra). Written from the
 * format description, nothing is copied from bsdiff or bsdiff4.
 */
import { bunzip2 } from "./bzip2.mjs";

const MAGIC = "BSDIFF40";
const HEADER = 32;
const MAX_STREAM = 1 << 28;

/** An 8-byte sign-and-magnitude little-endian integer; the sign is the top bit. */
function offtin(b, at) {
  let y = b[at + 7] & 0x7f;
  for (let i = 6; i >= 0; i--) y = y * 256 + b[at + i];
  return b[at + 7] & 0x80 ? -y : y;
}

/** The header of a patch, checked: the sizes it announces have to fit the file. Throws with a reason. */
export function parseBsdiff(patch) {
  if (patch.length < HEADER) throw new Error("Die Datei ist zu kurz für einen bsdiff-Patch.");
  for (let i = 0; i < MAGIC.length; i++) {
    if (patch[i] !== MAGIC.charCodeAt(i)) throw new Error("Der Kopf BSDIFF40 fehlt, das ist kein bsdiff-Patch.");
  }
  const ctrlLength = offtin(patch, 8), diffLength = offtin(patch, 16), newSize = offtin(patch, 24);
  if (ctrlLength < 0 || diffLength < 0 || newSize < 0 || !Number.isSafeInteger(HEADER + ctrlLength + diffLength)) {
    throw new Error("Der Kopf des Patches hat unmögliche Größen.");
  }
  if (HEADER + ctrlLength + diffLength > patch.length) throw new Error("Der Patch ist abgeschnitten.");
  return { ctrlLength, diffLength, newSize };
}

/** The new file out of the old one and a patch. Throws with a reason when the patch does not fit. */
export function applyBsdiff(old, patch, { maxNewSize = MAX_STREAM } = {}) {
  const { ctrlLength, diffLength, newSize } = parseBsdiff(patch);
  if (newSize > maxNewSize) throw new Error("Der Patch will eine größere Datei bauen als erlaubt.");
  const read = (from, to, what) => {
    try { return bunzip2(patch.subarray(from, to), { maxSize: MAX_STREAM }); }
    catch (e) { throw new Error(`Der ${what}-Teil des Patches ist beschädigt (${e.message}).`); }
  };
  const ctrl = read(HEADER, HEADER + ctrlLength, "Steuer");
  const diff = read(HEADER + ctrlLength, HEADER + ctrlLength + diffLength, "Diff");
  const extra = read(HEADER + ctrlLength + diffLength, patch.length, "Extra");

  const out = new Uint8Array(newSize);
  let ctrlAt = 0, diffAt = 0, extraAt = 0, oldAt = 0, newAt = 0;
  while (newAt < newSize) {
    if (ctrlAt + 24 > ctrl.length) throw new Error("Die Steuerdaten des Patches enden zu früh.");
    const add = offtin(ctrl, ctrlAt), copy = offtin(ctrl, ctrlAt + 8), seek = offtin(ctrl, ctrlAt + 16);
    ctrlAt += 24;
    if (add < 0 || copy < 0 || newAt + add > newSize || diffAt + add > diff.length) throw new Error("Eine Steueranweisung des Patches passt nicht zur Datei.");
    for (let i = 0; i < add; i++) {
      const at = oldAt + i;
      out[newAt + i] = (diff[diffAt + i] + (at >= 0 && at < old.length ? old[at] : 0)) & 0xff;
    }
    newAt += add;
    diffAt += add;
    oldAt += add;
    if (newAt + copy > newSize || extraAt + copy > extra.length) throw new Error("Eine Steueranweisung des Patches passt nicht zur Datei.");
    out.set(extra.subarray(extraAt, extraAt + copy), newAt);
    newAt += copy;
    extraAt += copy;
    oldAt += seek;
  }
  return out;
}
