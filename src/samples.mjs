/**
 * Samples as the sampler holds them in RAM: the name list and one entry's measured fields
 * (data/map/sample.mjs). Reads only; `readRam(addr, length)` is the session's.
 */
import { BLOCKS, field, readRaw } from "./map/index.mjs";
import { ramEntry } from "./map/address.mjs";

export const SAMPLE_COUNT = BLOCKS.get("sampleName").meta.table.count;

const CHUNK = 0x1000;
/** The metadata entry is 0x45C bytes; the fields read here end with the repeated index at +22. */
const META_HEAD = 24;

/**
 * The names of all samples in table order, "" where an entry holds none.
 * @returns {Promise<string[]>}
 */
export async function readSampleNames(readRam, { onProgress } = {}) {
  const { ram, stride, count } = BLOCKS.get("sampleName").meta.table;
  const bytes = new Uint8Array(count * stride);
  for (let at = 0; at < bytes.length; at += CHUNK) {
    bytes.set(await readRam(ram + at, Math.min(CHUNK, bytes.length - at)), at);
    onProgress?.(Math.min(at + CHUNK, bytes.length), bytes.length);
  }
  const name = field("sample.name");
  return Array.from({ length: count }, (_, i) => readRaw(bytes, name, [], i * stride));
}

/** One sample's name, tune, and the read-only facts the notes measured. `index` is zero-based. */
export async function readSample(readRam, index) {
  const names = await readRam(ramEntry("sampleName", index).ram, BLOCKS.get("sampleName").size);
  const playback = await readRam(ramEntry("samplePlayback", index).ram, BLOCKS.get("samplePlayback").size);
  const meta = await readRam(ramEntry("sampleMeta", index).ram, META_HEAD);
  const get = (id, bytes) => readRaw(bytes, field(id));
  return {
    index,
    name: get("sample.name", names),
    category: get("sample.category", names),
    importNumber: get("sample.importNumber", names),
    start: get("sample.start", playback),
    loop: get("sample.loop", playback),
    end: get("sample.end", playback),
    oneShot: get("sample.oneShot", playback),
    pcmBytes: get("sample.pcmBytes", meta),
    stereo: get("sample.stereo", meta),
    rate: get("sample.rate", meta),
    tune: get("sample.tune", meta),
  };
}
