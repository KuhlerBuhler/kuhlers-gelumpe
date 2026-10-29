/** Append-only sample updates and recovery through an exclusively owned, durable file adapter. */
import { HEADER, FIRST_USER, LAST_USER, ESLI, emptySampleFile } from "./sample-file.mjs";
import { crc32 } from "./script/blob.mjs";
import { crc32Combine } from "./crc-combine.mjs";

const BLOCK = 65536;
const MAX_FILE = 0xFFFFFFFF;
const PREFIX = 64;
const JOURNAL_BYTES = PREFIX + HEADER;
const MAGIC = new TextEncoder().encode("BLECHTX1");
const u32 = (bytes, at) => new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(at, true);
const put32 = (bytes, at, value) => new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).setUint32(at, value, true);
const equal = (a, b) => a.length === b.length && a.every((value, i) => value === b[i]);
const tag = (bytes, at) => String.fromCharCode(...bytes.subarray(at, at + 4));

export class SampleStoreError extends Error {}

function slotNumber(slot) {
  if (!Number.isInteger(slot) || slot < FIRST_USER || slot > LAST_USER) throw new SampleStoreError("Der Sample-Platz muss zwischen 501 und 999 liegen.");
}

function fileSize(size) {
  if (!Number.isInteger(size) || size < HEADER || size > MAX_FILE) throw new SampleStoreError("Die Dateigröße passt nicht zum 32-Bit-Sampleformat.");
}

function headerValid(header, size) {
  fileSize(size);
  if (header.length !== HEADER || !equal(header.subarray(0, 16), emptySampleFile().subarray(0, 16))) throw new SampleStoreError("Der Kopf der Sample-Datei ist ungültig.");
  for (let at = 16; at < HEADER; at += 4) {
    const offset = u32(header, at);
    if (offset && (offset < HEADER || offset + 12 > size)) throw new SampleStoreError("Der Sample-Index zeigt außerhalb der Datei.");
  }
}

function newHeader(record) {
  const header = record.header.slice();
  put32(header, 16 + record.slot * 4, record.kind === 1 ? record.offset : 0);
  return header;
}

function encode(record) {
  const bytes = new Uint8Array(JOURNAL_BYTES);
  bytes.set(MAGIC);
  for (const [at, value] of [[8, 1], [12, record.kind], [16, record.slot], [20, record.oldSize],
    [24, record.size], [28, record.offset], [32, record.length], [36, record.crc],
    [40, crc32(record.header)], [44, crc32(newHeader(record))]]) put32(bytes, at, value);
  bytes.set(record.header, PREFIX);
  put32(bytes, 60, crc32(bytes));
  return bytes;
}

function decode(bytes) {
  if (bytes.length !== JOURNAL_BYTES || !equal(bytes.subarray(0, 8), MAGIC) || u32(bytes, 8) !== 1) throw new SampleStoreError("Die Wiederherstellungsdatei ist ungültig.");
  const copy = bytes.slice();
  put32(copy, 60, 0);
  if (crc32(copy) !== u32(bytes, 60) || bytes.subarray(48, 60).some(Boolean)) throw new SampleStoreError("Die Wiederherstellungsdatei hat eine falsche Prüfsumme.");
  const record = { kind: u32(bytes, 12), slot: u32(bytes, 16), oldSize: u32(bytes, 20), size: u32(bytes, 24),
    offset: u32(bytes, 28), length: u32(bytes, 32), crc: u32(bytes, 36), header: bytes.slice(PREFIX) };
  slotNumber(record.slot);
  headerValid(record.header, record.oldSize);
  fileSize(record.size);
  if (record.kind === 1) {
    if (record.offset !== record.oldSize || record.length < 12 || record.oldSize + record.length !== record.size) throw new SampleStoreError("Die Wiederherstellungsdatei beschreibt keinen gültigen Anhang.");
  } else if (record.kind !== 2 || record.offset || record.length || record.crc || record.size !== record.oldSize) {
    throw new SampleStoreError("Die Wiederherstellungsdatei beschreibt keine gültige Löschung.");
  }
  if (crc32(record.header) !== u32(bytes, 40) || crc32(newHeader(record)) !== u32(bytes, 44)) throw new SampleStoreError("Der gesicherte Sample-Index ist beschädigt.");
  return record;
}

/**
 * io: exclusive(work), size(role) (null when absent), read(role, at, length), write(role, at, bytes) (completed count),
 * flush(role) and remove(role). Roles are "library" and "journal". Flush and remove must complete durably; every writer
 * must use the same exclusive owner. A source is a canonical RIFF/fmt/data/korg-esli entry with size and read(at, length).
 */
export class SampleStore {
  constructor(io) {
    for (const name of ["exclusive", "size", "read", "write", "flush", "remove"]) {
      if (typeof io?.[name] !== "function") throw new SampleStoreError(`Der Dateizugriff unterstützt ${name} nicht.`);
    }
    this.io = io;
  }

  async #read(role, at, length) {
    const bytes = await this.io.read(role, at, length);
    if (!(bytes instanceof Uint8Array) || bytes.length !== length) throw new SampleStoreError("Die Karte lieferte nicht alle angeforderten Bytes.");
    return bytes;
  }

  async #write(role, at, bytes) {
    if (await this.io.write(role, at, bytes) !== bytes.length) throw new SampleStoreError("Die Karte hat nicht alle Bytes geschrieben.");
  }

  async #crc(role, offset, length) {
    let sum = 0;
    for (let done = 0; done < length; done += BLOCK) {
      const n = Math.min(BLOCK, length - done);
      const bytes = await this.#read(role, offset + done, n);
      sum = crc32Combine(sum, crc32(bytes), n);
    }
    return sum;
  }

  async #source(source, slot) {
    if (!source || typeof source.read !== "function" || !Number.isInteger(source.size) || source.size < 1232 || source.size > MAX_FILE - HEADER) throw new SampleStoreError("Das Sample hat keine gültige Eintragsgröße.");
    const head = await source.read(0, 44);
    if (!(head instanceof Uint8Array) || head.length !== 44 || tag(head, 0) !== "RIFF" || tag(head, 8) !== "WAVE"
      || tag(head, 12) !== "fmt " || u32(head, 16) !== 16 || tag(head, 36) !== "data" || u32(head, 4) + 8 !== source.size) throw new SampleStoreError("Das Sample ist kein vollständiger normalisierter WAV-Eintrag.");
    if ((head[20] | head[21] << 8) !== 1 || ![1, 2].includes(head[22] | head[23] << 8)
      || ![16, 24].includes(head[34] | head[35] << 8) || !u32(head, 24)) throw new SampleStoreError("Das Sample muss PCM mit 16 oder 24 Bit und einem oder zwei Kanälen enthalten.");
    const tailAt = 44 + u32(head, 40) + (u32(head, 40) & 1);
    if (tailAt + 16 + ESLI !== source.size) throw new SampleStoreError("Der Sample-Datensatz fehlt oder ist abgeschnitten.");
    const tail = await source.read(tailAt, 16 + ESLI);
    if (!(tail instanceof Uint8Array) || tail.length !== 16 + ESLI || tag(tail, 0) !== "korg" || tag(tail, 8) !== "esli"
      || u32(tail, 4) !== ESLI + 8 || u32(tail, 12) !== ESLI
      || (tail[16] | tail[17] << 8) !== slot || (tail[94] | tail[95] << 8) !== slot) throw new SampleStoreError("Der Sample-Datensatz gehört nicht zum gewählten Platz.");
  }

  recover() { return this.io.exclusive(() => this.#recover()); }

  async #recover() {
    const size = await this.io.size("journal");
    if (size === null) return { state: "none" };
    if (size !== JOURNAL_BYTES) throw new SampleStoreError("Die Wiederherstellungsdatei ist unvollständig; nichts geändert.");
    const record = decode(await this.#read("journal", 0, JOURNAL_BYTES));
    const librarySize = await this.io.size("library");
    if (librarySize === null || librarySize < record.oldSize) throw new SampleStoreError("Die ursprüngliche Sample-Datei fehlt oder wurde gekürzt.");
    const current = await this.#read("library", 0, HEADER);
    const sector = Math.floor((16 + record.slot * 4) / 512);
    if (current.some((value, i) => Math.floor(i / 512) !== sector && value !== record.header[i])) throw new SampleStoreError("Die Sample-Datei wurde außerhalb des betroffenen Indexsektors verändert.");
    const complete = record.kind === 2 || (librarySize >= record.size && await this.#crc("library", record.offset, record.length) === record.crc);
    const header = complete ? newHeader(record) : record.header;
    await this.#write("library", 0, header);
    await this.io.flush("library");
    if (!equal(await this.#read("library", 0, HEADER), header)) throw new SampleStoreError("Der wiederhergestellte Index stimmt beim Zurücklesen nicht.");
    await this.io.remove("journal");
    return { state: complete ? "new" : "old", slot: record.slot };
  }

  async #change(slot, source) {
    slotNumber(slot);
    if (source !== null) await this.#source(source, slot);
    await this.#recover();
    let oldSize = await this.io.size("library");
    if (oldSize === null) {
      if (source === null) return { slot, size: 0 };
      await this.#write("library", 0, emptySampleFile());
      await this.io.flush("library");
      oldSize = HEADER;
    }
    const header = await this.#read("library", 0, HEADER);
    headerValid(header, oldSize);
    const length = source?.size ?? 0;
    const size = oldSize + length;
    fileSize(size);
    let sum = 0;
    for (let done = 0; done < length; done += BLOCK) {
      const n = Math.min(BLOCK, length - done);
      const bytes = await source.read(done, n);
      if (!(bytes instanceof Uint8Array) || bytes.length !== n) throw new SampleStoreError("Das neue Sample wurde beim Lesen abgeschnitten.");
      await this.#write("library", oldSize + done, bytes);
      sum = crc32Combine(sum, crc32(bytes), n);
    }
    if (length) {
      await this.io.flush("library");
      if (await this.#crc("library", oldSize, length) !== sum) throw new SampleStoreError("Das angehängte Sample stimmt beim Zurücklesen nicht.");
    }
    const record = { kind: source === null ? 2 : 1, slot, oldSize, size, offset: length ? oldSize : 0, length, crc: sum, header };
    const journal = encode(record);
    await this.#write("journal", 0, journal);
    await this.io.flush("journal");
    if (!equal(await this.#read("journal", 0, journal.length), journal)) throw new SampleStoreError("Die Wiederherstellungsdatei stimmt beim Zurücklesen nicht.");
    const next = newHeader(record);
    const indexAt = 16 + slot * 4;
    await this.#write("library", indexAt, next.subarray(indexAt, indexAt + 4));
    await this.io.flush("library");
    if (!equal(await this.#read("library", 0, HEADER), next)) throw new SampleStoreError("Der neue Sample-Index stimmt beim Zurücklesen nicht.");
    await this.io.remove("journal");
    return { slot, size };
  }

  async put(slot, source) {
    if (!source) throw new SampleStoreError("Das neue Sample fehlt.");
    return this.io.exclusive(() => this.#change(slot, source));
  }
  delete(slot) { return this.io.exclusive(() => this.#change(slot, null)); }
}
