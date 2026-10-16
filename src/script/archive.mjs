/**
 * Script files for the card: the collection `e2sPlugin.all` (many blocks) and
 * the single `.blech` file (one block plus an optional source trailer). The
 * layouts are data/script/contract.mjs (ARCHIVE, SOURCE_TRAILER). The device
 * reads the blocks only; the source trailer is for the editor.
 */
import { ARCHIVE, SOURCE_TRAILER, MAGIC, ERROR } from "../../data/script/contract.mjs";
import { crc32, decodeBlob, fail } from "./blob.mjs";

// Returns the decoded parts, or the error when the block cannot be loaded from a file.
function checkBlock(bytes, label) {
  if (bytes.length > ARCHIVE.maxBlock) {
    return { ok: false, error: fail(ERROR.LIMITS, `${label}: Block ${bytes.length} Bytes, die Karte nimmt höchstens ${ARCHIVE.maxBlock}`) };
  }
  const parts = decodeBlob(bytes);
  if (!parts.ok) return { ok: false, error: { ...parts.error, message: `${label}: ${parts.error.message}` } };
  if (parts.header.totalSize !== bytes.length) {
    return { ok: false, error: fail(ERROR.BAD_SIZE, `${label}: Block ${parts.header.totalSize} Bytes, Datei ${bytes.length}`) };
  }
  return { ok: true, parts };
}

/**
 * Build `e2sPlugin.all` from blocks.
 * @param {Uint8Array[]} blocks
 * @returns {{ ok: true, bytes: Uint8Array } | { ok: false, error: object }}
 */
export function packAll(blocks) {
  if (blocks.length > 0xffff) return { ok: false, error: fail(ERROR.LIMITS, `${blocks.length} Plugins, höchstens 65535`) };
  const names = new Set();
  let size = ARCHIVE.headerSize;
  for (const [i, block] of blocks.entries()) {
    const checked = checkBlock(block, `Plugin ${i + 1}`);
    if (!checked.ok) return checked;
    const name = checked.parts.header.name;
    if (names.has(name)) return { ok: false, error: { code: null, name: "DUPLICATE_NAME", message: `der Name "${name}" kommt zweimal vor`, offset: null } };
    names.add(name);
    size += block.length;
  }
  const out = new Uint8Array(size);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, ARCHIVE.magic, true);
  dv.setUint16(4, ARCHIVE.version, true);
  dv.setUint16(6, blocks.length, true);
  dv.setUint32(8, size, true);
  let at = ARCHIVE.headerSize;
  for (const block of blocks) {
    out.set(block, at);
    at += block.length;
  }
  dv.setUint32(12, crc32(out, ARCHIVE.checksumFrom, size), true);
  return { ok: true, bytes: out };
}

/**
 * Read `e2sPlugin.all`. The file is rejected as a whole when its header or
 * checksum is wrong; a bad block is reported on its own and the others stay
 * usable, as the device does.
 * @returns {{ ok: true, blocks: { name: string, offset: number, size: number, bytes: Uint8Array, error: object | null }[] } | { ok: false, error: object }}
 */
export function parseAll(bytes) {
  const bad = (code, detail) => ({ ok: false, error: fail(code, detail) });
  if (bytes.length < ARCHIVE.headerSize) return bad(ERROR.TRUNCATED, `${bytes.length} Bytes, der Kopf braucht ${ARCHIVE.headerSize}`);
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (dv.getUint32(0, true) !== ARCHIVE.magic) return bad(ERROR.MAGIC, "keine Sammeldatei e2sPlugin.all");
  const version = dv.getUint16(4, true);
  if (version !== ARCHIVE.version) return bad(ERROR.FORMAT_VERSION, `Datei ${version}, diese Laufzeit ${ARCHIVE.version}`);
  const count = dv.getUint16(6, true);
  const total = dv.getUint32(8, true);
  if (total < ARCHIVE.headerSize + count * 52) return bad(ERROR.BAD_SIZE, `Kopf nennt ${total} Bytes für ${count} Plugins`);
  if (bytes.length < total) return bad(ERROR.TRUNCATED, `${bytes.length} von ${total} Bytes`);
  if (crc32(bytes, ARCHIVE.checksumFrom, total) !== dv.getUint32(12, true)) return bad(ERROR.CHECKSUM);
  const blocks = [];
  let at = ARCHIVE.headerSize;
  for (let i = 0; i < count; i++) {
    if (at + 52 > total) return bad(ERROR.TRUNCATED, `Plugin ${i + 1} fehlt`);
    const size = dv.getUint32(at + 8, true);
    if (size < 52 || size > ARCHIVE.maxBlock || size % 4 || at + size > total) return bad(ERROR.BAD_SIZE, `Plugin ${i + 1} nennt ${size} Bytes`);
    const block = bytes.slice(at, at + size);
    const checked = checkBlock(block, `Plugin ${i + 1}`);
    blocks.push({ name: checked.ok ? checked.parts.header.name : "", offset: at, size, bytes: block, error: checked.ok ? null : checked.error });
    at += size;
  }
  if (at !== total) return bad(ERROR.BAD_SIZE, `Kopf nennt ${total} Bytes, die Plugins brauchen ${at}`);
  return { ok: true, blocks };
}

/**
 * Build a `.blech` file: one block, then optionally the source.
 * @param {Uint8Array} block
 * @param {string} [source]
 */
export function packBlech(block, source) {
  const checked = checkBlock(block, "Plugin");
  if (!checked.ok) return checked;
  const text = source === undefined ? new Uint8Array(0) : new TextEncoder().encode(source);
  const trailer = source === undefined ? 0 : SOURCE_TRAILER.headerSize + text.length;
  const out = new Uint8Array(block.length + trailer);
  out.set(block);
  if (source !== undefined) {
    const dv = new DataView(out.buffer);
    dv.setUint32(block.length, SOURCE_TRAILER.magic, true);
    dv.setUint32(block.length + 4, text.length, true);
    out.set(text, block.length + SOURCE_TRAILER.headerSize);
  }
  return { ok: true, bytes: out };
}

/**
 * Read a `.blech` file. The device ignores everything after the block, so a
 * missing or damaged trailer only means there is no source to show.
 * @returns {{ ok: true, block: Uint8Array, source: string | null, parts: object } | { ok: false, error: object }}
 */
export function parseBlech(bytes) {
  if (bytes.length < 12) return { ok: false, error: fail(ERROR.TRUNCATED, `${bytes.length} Bytes`) };
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (dv.getUint32(0, true) !== MAGIC) return { ok: false, error: fail(ERROR.MAGIC) };
  const size = dv.getUint32(8, true);
  if (size > bytes.length) return { ok: false, error: fail(ERROR.TRUNCATED, `${bytes.length} von ${size} Bytes`) };
  const block = bytes.slice(0, size);
  const checked = checkBlock(block, "Plugin");
  if (!checked.ok) return checked;
  let source = null;
  const at = size;
  if (bytes.length >= at + SOURCE_TRAILER.headerSize && dv.getUint32(at, true) === SOURCE_TRAILER.magic) {
    const length = dv.getUint32(at + 4, true);
    if (at + SOURCE_TRAILER.headerSize + length <= bytes.length) {
      try {
        source = new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(at + SOURCE_TRAILER.headerSize, at + SOURCE_TRAILER.headerSize + length));
      } catch {
        source = null;
      }
    }
  }
  return { ok: true, block, source, parts: checked.parts };
}
