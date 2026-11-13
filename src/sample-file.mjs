/**
 * The sample file of the card, KORG/<folder>/Sample/e2sSample.all (docs/hintergrund/sample-datei.md): a 4096-byte header
 * with one offset per slot, then one RIFF/WAVE file per sample that carries the sampler's own record, "korg" with "esli".
 * Parsing, adding and removing work on bytes only, so the page can run them on a file from a card reader and the editor
 * can run the same plan on the card through the device.
 */
import { render, text, TextError } from "./text.mjs";

export const SLOTS = 1020;
export const HEADER = 4096;
export const FIRST_USER = 500;                  // zero-based slots 500 to 998 are shown as 501 to 999
export const LAST_USER = 998;
export const ESLI = 1172;
export const NAME_MAX = 15;
const MAGIC = "e2s sample all\x1a\0";
const WAV_FORMATS = new Set([16, 24]);

/** A problem with the sample file or a WAV; `key` and `vars` are a text (src/text.mjs). */
export class SampleFileError extends TextError {}

const u16 = (b, i) => b[i] | (b[i + 1] << 8);
const u32 = (b, i) => (b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24)) >>> 0;
const put32 = (b, i, n) => { b[i] = n & 255; b[i + 1] = (n >>> 8) & 255; b[i + 2] = (n >>> 16) & 255; b[i + 3] = (n >>> 24) & 255; };
const put16 = (b, i, n) => { b[i] = n & 255; b[i + 1] = (n >>> 8) & 255; };
const tag = (b, i) => String.fromCharCode(b[i], b[i + 1], b[i + 2], b[i + 3]);
const ascii = (b, i, n) => { let s = ""; for (let k = i; k < i + n && b[k]; k++) s += String.fromCharCode(b[k]); return s; };

/** Walks the chunks of one RIFF/WAVE: { fmt, data, korg } as { at, size } where `at` is the start of the chunk's body. */
export function wavChunks(bytes, start = 0, limit = bytes.length) {
  if (limit - start < 12 || tag(bytes, start) !== "RIFF" || tag(bytes, start + 8) !== "WAVE") throw new SampleFileError("samplefile.noWav");
  const found = {};
  const end = Math.min(limit, start + 8 + u32(bytes, start + 4));
  for (let at = start + 12; at + 8 <= end;) {
    const size = u32(bytes, at + 4);
    const name = tag(bytes, at).trim();
    if (!(name in found)) found[name] = { at: at + 8, size: Math.min(size, end - at - 8) };
    at += 8 + size + (size & 1);
  }
  return found;
}

function describe(bytes, start, limit) {
  const c = wavChunks(bytes, start, limit);
  if (!c.fmt || c.fmt.size < 16 || !c.data) throw new SampleFileError("samplefile.chunks");
  const tagNo = u16(bytes, c.fmt.at);
  const channels = u16(bytes, c.fmt.at + 2);
  const rate = u32(bytes, c.fmt.at + 4);
  const bits = u16(bytes, c.fmt.at + 14);
  const frames = Math.floor(c.data.size / Math.max(1, channels * (bits >> 3)));
  let name = "";
  if (c.korg && c.korg.size >= 4 + 4 + 18 && tag(bytes, c.korg.at) === "esli") name = ascii(bytes, c.korg.at + 8 + 2, 16);
  return { tagNo, channels, rate, bits, frames, name, esli: c.korg && tag(bytes, c.korg.at) === "esli" ? c.korg.at + 8 : null };
}

/**
 * The samples of a sample file, in slot order. `problem` is finished text in the page's language.
 * @returns {{ size: number, samples: { slot: number, offset: number, length: number, name: string, rate: number, channels: number, bits: number, frames: number, problem: string|null }[] }}
 */
export function parseSampleFile(bytes) {
  if (bytes.length < HEADER || ascii(bytes, 0, 14) !== "e2s sample all" || bytes[14] !== 0x1a) {
    throw new SampleFileError("samplefile.notAll");
  }
  const entries = [];
  for (let slot = 0; slot < SLOTS; slot++) {
    const offset = u32(bytes, 16 + 4 * slot);
    if (offset) entries.push({ slot, offset });
  }
  const byOffset = [...entries].sort((a, b) => a.offset - b.offset);
  const samples = entries.map(e => {
    const next = byOffset.find(o => o.offset > e.offset)?.offset ?? bytes.length;
    const base = { slot: e.slot, offset: e.offset, length: 0, name: "", rate: 0, channels: 0, bits: 0, frames: 0, problem: null };
    if (e.offset < HEADER || e.offset + 12 > bytes.length) return { ...base, problem: render(text("samplefile.outside")) };
    try {
      const length = 8 + u32(bytes, e.offset + 4);
      if (e.offset + length > bytes.length) return { ...base, length: bytes.length - e.offset, problem: render(text("samplefile.cut")) };
      const d = describe(bytes, e.offset, e.offset + length);
      return { ...base, length: Math.min(length, next - e.offset), name: d.name, rate: d.rate, channels: d.channels, bits: d.bits, frames: d.frames, problem: null };
    } catch (error) { return { ...base, length: Math.max(0, next - e.offset), problem: error.message }; }
  });
  return { size: bytes.length, samples };
}

/** A sample file with no sample in it: the header only, as a first sample is added to a card that has none. */
export function emptySampleFile() {
  const out = new Uint8Array(HEADER);
  for (let i = 0; i < MAGIC.length; i++) out[i] = MAGIC.charCodeAt(i);
  return out;
}

/**
 * The same list as parseSampleFile, from a file that is not here: `read(offset, length)` returns the bytes (fewer at the end of the
 * file), `size` is the file's size. It reads the header and, for each sample, the first 44 bytes and the name in the record behind
 * the audio, a few bytes each, not the audio. An entry laid out otherwise than the firmware writes it (fmt, data, korg) is listed
 * with its length from the RIFF header and a problem, so it can still be removed.
 * @param {(offset: number, length: number) => Promise<Uint8Array>} read
 * @param {(done: number, total: number) => void} [onProgress]
 */
export async function parseRemote(read, size, onProgress) {
  if (size < HEADER) throw new SampleFileError("samplefile.short");
  const header = await read(0, HEADER);
  if (header.length < HEADER || ascii(header, 0, 14) !== "e2s sample all" || header[14] !== 0x1a) {
    throw new SampleFileError("samplefile.notAll");
  }
  const entries = [];
  for (let slot = 0; slot < SLOTS; slot++) {
    const offset = u32(header, 16 + 4 * slot);
    if (offset) entries.push({ slot, offset });
  }
  const samples = [];
  for (const [i, e] of entries.entries()) {
    onProgress?.(i, entries.length);
    const base = { slot: e.slot, offset: e.offset, length: 0, name: "", rate: 0, channels: 0, bits: 0, frames: 0, problem: null };
    if (e.offset < HEADER || e.offset + 12 > size) { samples.push({ ...base, problem: render(text("samplefile.outside")) }); continue; }
    const head = await read(e.offset, 44);
    if (head.length < 12 || tag(head, 0) !== "RIFF" || tag(head, 8) !== "WAVE") { samples.push({ ...base, problem: render(text("samplefile.noWav")) }); continue; }
    const length = 8 + u32(head, 4);
    if (e.offset + length > size) { samples.push({ ...base, length: size - e.offset, problem: render(text("samplefile.cut")) }); continue; }
    const layout = head.length >= 44 && tag(head, 12) === "fmt " && u32(head, 16) === 16 && tag(head, 36) === "data";
    if (!layout) { samples.push({ ...base, length, problem: render(text("samplefile.layout")) }); continue; }
    const channels = u16(head, 22);
    const bits = u16(head, 34);
    const dataSize = u32(head, 40);
    const korgAt = e.offset + 44 + dataSize + (dataSize & 1);
    let name = "";
    if (korgAt + 8 + 8 + 18 <= e.offset + length) {
      const record = await read(korgAt, 8 + 8 + 18);
      if (tag(record, 0) === "korg" && tag(record, 8) === "esli") name = ascii(record, 8 + 8 + 2, 16);
    }
    samples.push({ ...base, length, name, rate: u32(head, 24), channels, bits, frames: Math.floor(dataSize / Math.max(1, channels * (bits >> 3))), problem: null });
  }
  onProgress?.(entries.length, entries.length);
  return { size, samples, header };
}

/** The first empty user slot at or after `from`, or null when 501 to 999 are all taken. */
export function freeSlot(taken, from = FIRST_USER) {
  for (let slot = from; slot <= LAST_USER; slot++) if (!taken.has(slot)) return slot;
  return null;
}

/** Name as the sampler stores it: printable ASCII, at most 15 letters. */
export const cleanSampleName = text => text.replace(/[^\x20-\x7e]/g, "").trim().slice(0, NAME_MAX);

/**
 * One sample entry out of a WAV: fmt, data and the "korg" chunk with its 1172-byte "esli" record. An esli the WAV
 * brings is kept and only gets the slot and the name; without one the record is the one tools/emu/sampleset.py builds.
 * The loader of the firmware takes PCM with 1 or 2 channels at 16 or 24 bit (docs/messungen/2026-10-15-sample-fehler.md).
 */
export function entryFromWav(wav, slot, name) {
  const c = wavChunks(wav);
  if (!c.fmt || c.fmt.size < 16 || !c.data) throw new SampleFileError("samplefile.chunks");
  const d = describe(wav, 0, wav.length);
  if (d.tagNo !== 1) throw new SampleFileError("samplefile.notPcm", { format: d.tagNo });
  if (!WAV_FORMATS.has(d.bits)) throw new SampleFileError("samplefile.bits", { bits: d.bits });
  if (d.channels < 1 || d.channels > 2) throw new SampleFileError("samplefile.channels", { channels: d.channels });
  if (!d.frames) throw new SampleFileError("samplefile.noAudio");
  const pcm = wav.subarray(c.data.at, c.data.at + c.data.size);
  const record = new Uint8Array(ESLI);
  const kept = d.esli !== null && c.korg.size >= 8 + ESLI;
  if (kept) record.set(wav.subarray(d.esli, d.esli + ESLI));
  else {
    const frameBytes = d.channels * 2;
    const bytesOf16 = d.frames * frameBytes;
    put16(record, 18, 2);
    put16(record, 20, 0x226 + slot % 100);
    record[25] = 0x7f; record[27] = 1;
    put16(record, 34, 0x42e6);
    put16(record, 36, 0xffff);
    put32(record, 44, Math.max(bytesOf16 - frameBytes, 0));
    put32(record, 48, Math.max(bytesOf16 - frameBytes, 0));
    record[52] = 1;
    put32(record, 60, bytesOf16);
    record[64] = 1; record[67] = 1;
    put16(record, 68, 0x04b0);
    put32(record, 72, d.rate);
    if (d.channels === 2) record[65] = 1;
  }
  put16(record, 0, slot);
  put16(record, 78, slot);
  record.fill(0, 2, 18);
  for (let i = 0; i < Math.min(name.length, NAME_MAX); i++) record[2 + i] = name.charCodeAt(i);
  const fmt = new Uint8Array(16);
  fmt.set(wav.subarray(c.fmt.at, c.fmt.at + 16));
  const korgBody = 4 + 4 + ESLI;
  const body = 4 + (8 + 16) + (8 + pcm.length + (pcm.length & 1)) + (8 + korgBody);
  const out = new Uint8Array(8 + body);
  let at = 0;
  const text = s => { for (const ch of s) out[at++] = ch.charCodeAt(0); };
  text("RIFF"); put32(out, at, body); at += 4; text("WAVE");
  text("fmt "); put32(out, at, 16); at += 4; out.set(fmt, at); at += 16;
  text("data"); put32(out, at, pcm.length); at += 4; out.set(pcm, at); at += pcm.length + (pcm.length & 1);
  text("korg"); put32(out, at, korgBody); at += 4; text("esli"); put32(out, at, ESLI); at += 4; out.set(record, at);
  return out;
}

/**
 * What a change to the file comes to, as little as possible to move: the new header, the entries that stay and where they
 * go (compacted, in the order they lie in the file), and the new entries appended behind them. Removing leaves no gap.
 * @param {Uint8Array} header the first 4096 bytes of the old file (or the whole file)
 * @param {{ samples: { slot: number, offset: number, length: number }[], size: number }} parsed
 * @param {{ remove?: Iterable<number>, add?: { slot: number, bytes: Uint8Array }[] }} change
 * @returns {{ header: Uint8Array, keeps: { from: number, to: number, length: number }[], moves: { from: number, to: number, length: number }[], appends: { at: number, bytes: Uint8Array }[], size: number }}
 */
export function planChange(header, parsed, { remove = [], add = [] } = {}) {
  const gone = new Set(remove);
  const slots = new Set(parsed.samples.map(s => s.slot).filter(s => !gone.has(s)));
  for (const a of add) {
    if (slots.has(a.slot)) throw new SampleFileError("samplefile.slotTaken", { slot: a.slot + 1 });
    if (a.slot < FIRST_USER || a.slot > LAST_USER) throw new SampleFileError("samplefile.slotRange", { slot: a.slot + 1 });
    slots.add(a.slot);
  }
  const out = new Uint8Array(HEADER);
  out.set(header.subarray(0, 16));
  const keeps = [];
  const moves = [];
  let end = HEADER;
  for (const s of [...parsed.samples].filter(x => !gone.has(x.slot)).sort((a, b) => a.offset - b.offset)) {
    put32(out, 16 + 4 * s.slot, end);
    keeps.push({ from: s.offset, to: end, length: s.length });
    if (s.offset !== end) moves.push({ from: s.offset, to: end, length: s.length });
    end += s.length;
  }
  const appends = [];
  for (const a of add) {
    put32(out, 16 + 4 * a.slot, end);
    appends.push({ at: end, bytes: a.bytes });
    end += a.bytes.length;
  }
  return { header: out, keeps, moves, appends, size: end };
}

/** Runs a plan on the whole old file in memory (the card reader path); the device runs the same plan on the card. */
export function applyPlan(file, plan) {
  const out = new Uint8Array(plan.size);
  out.set(plan.header, 0);
  for (const k of plan.keeps) out.set(file.subarray(k.from, k.from + k.length), k.to);
  for (const a of plan.appends) out.set(a.bytes, a.at);
  return out;
}
