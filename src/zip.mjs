/**
 * One file out of a zip archive, for Korg's System Updater: the user can drop the zip as Korg ships it and the page takes
 * SYSTEM.VSB out of it. Stored and deflated entries (the browser's DecompressionStream), read through the central
 * directory; no zip64, no encryption, which Korg's archives do not use.
 */

const u16 = (b, at) => b[at] | (b[at + 1] << 8);
const u32 = (b, at) => (b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)) >>> 0;

/** Whether the bytes start like a zip archive (a local file header). */
export const isZip = bytes => bytes.length >= 4 && u32(bytes, 0) === 0x04034b50;

async function inflate(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/**
 * {name, bytes} of the first entry whose path `wanted` accepts (default: a SYSTEM.VSB, not the "__MACOSX" copies),
 * or null when there is none. Throws on an archive it cannot read.
 */
export async function unzipEntry(zip, wanted = name => /(^|\/)SYSTEM\.VSB$/i.test(name) && !name.startsWith("__MACOSX/")) {
  let end = -1;
  for (let at = zip.length - 22; at >= Math.max(0, zip.length - 22 - 0xffff); at--) {
    if (u32(zip, at) === 0x06054b50) { end = at; break; }
  }
  if (end < 0) throw new Error("Das ist kein lesbares Zip-Archiv.");
  const count = u16(zip, end + 10);
  let at = u32(zip, end + 16);
  for (let i = 0; i < count; i++) {
    if (at + 46 > zip.length || u32(zip, at) !== 0x02014b50) throw new Error("Das Inhaltsverzeichnis des Zip-Archivs ist beschädigt.");
    const method = u16(zip, at + 10), packed = u32(zip, at + 20), size = u32(zip, at + 24);
    const nameLength = u16(zip, at + 28), extra = u16(zip, at + 30), comment = u16(zip, at + 32), local = u32(zip, at + 42);
    const name = new TextDecoder().decode(zip.subarray(at + 46, at + 46 + nameLength));
    at += 46 + nameLength + extra + comment;
    if (!wanted(name)) continue;
    if (u32(zip, local) !== 0x04034b50) throw new Error("Das Zip-Archiv ist beschädigt.");
    const start = local + 30 + u16(zip, local + 26) + u16(zip, local + 28);
    const data = zip.subarray(start, start + packed);
    if (data.length !== packed) throw new Error("Das Zip-Archiv ist unvollständig.");
    const bytes = method === 0 ? Uint8Array.from(data) : method === 8 ? await inflate(data) : null;
    if (!bytes) throw new Error(`${name} ist im Zip-Archiv mit einem unbekannten Verfahren gepackt.`);
    if (bytes.length !== size) throw new Error(`${name} hat ausgepackt nicht die erwartete Größe.`);
    return { name, bytes };
  }
  return null;
}
