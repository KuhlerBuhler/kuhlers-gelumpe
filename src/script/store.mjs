/**
 * The persistent values of scripts as a file on the card (contract: STORE).
 * Two files alternate (`store.a.bin`, `store.b.bin`); each carries a
 * generation, a CRC-32 over everything behind the 16 byte header and one
 * record per script: name, mask of slots that hold a value, 16 values.
 */
import { STORE } from "../../data/script/contract.mjs";
import { crc32 } from "./blob.mjs";

const NAME = /^[A-Za-z][A-Za-z0-9_]{0,14}$/;

/**
 * @param {{ generation: number, records: { name: string, mask: number, values: ArrayLike<number> }[] }} store
 * @returns {Uint8Array}
 */
export function buildStore({ generation, records }) {
  const out = new Uint8Array(STORE.headerSize + records.length * STORE.recordSize);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, STORE.magic, true);
  dv.setUint16(4, STORE.version, true);
  dv.setUint16(6, records.length, true);
  dv.setUint32(8, generation >>> 0, true);
  records.forEach((r, i) => {
    if (!NAME.test(r.name)) throw new RangeError(`store record name: ${r.name}`);
    const at = STORE.headerSize + i * STORE.recordSize;
    for (let k = 0; k < r.name.length; k++) out[at + k] = r.name.charCodeAt(k);
    dv.setUint32(at + STORE.nameBytes, r.mask >>> 0, true);
    for (let s = 0; s < STORE.slots; s++) dv.setInt32(at + STORE.nameBytes + 4 + s * 4, r.values[s] | 0, true);
  });
  dv.setUint32(12, crc32(out, STORE.headerSize, out.length), true);
  return out;
}

/**
 * @returns {{ ok: true, generation: number, records: { name: string, mask: number, values: Int32Array }[] } | { ok: false, reason: string }}
 */
export function parseStore(bytes) {
  if (bytes.length < STORE.headerSize) return { ok: false, reason: "zu kurz" };
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (dv.getUint32(0, true) !== STORE.magic) return { ok: false, reason: "keine Kennung" };
  if (dv.getUint16(4, true) !== STORE.version) return { ok: false, reason: "andere Version" };
  const count = dv.getUint16(6, true);
  const size = STORE.headerSize + count * STORE.recordSize;
  if (bytes.length < size) return { ok: false, reason: "abgeschnitten" };
  if (crc32(bytes, STORE.headerSize, size) !== dv.getUint32(12, true)) return { ok: false, reason: "Prüfsumme" };
  const records = [];
  for (let i = 0; i < count; i++) {
    const at = STORE.headerSize + i * STORE.recordSize;
    let end = at;
    while (end < at + STORE.nameBytes && bytes[end] !== 0) end++;
    const name = String.fromCharCode(...bytes.subarray(at, end));
    const values = new Int32Array(STORE.slots);
    for (let s = 0; s < STORE.slots; s++) values[s] = dv.getInt32(at + STORE.nameBytes + 4 + s * 4, true);
    records.push({ name, mask: dv.getUint32(at + STORE.nameBytes, true), values });
  }
  return { ok: true, generation: dv.getUint32(8, true), records };
}

/** The newer of two store files that both check out; null when neither does. */
export function newestStore(...files) {
  const good = files.map(parseStore).filter(f => f.ok);
  return good.length ? good.reduce((a, b) => (b.generation > a.generation ? b : a)) : null;
}
