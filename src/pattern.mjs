/**
 * Patterns: the backup file (.e2sallpat), the single pattern file (.e2spat)
 * and the 0x4000-byte block both of them carry.
 *
 * A pattern is always an edit of bytes that came from the device. Fields the
 * map does not know, the file header, byte 38 of every part, all of it is
 * kept as it was; only the field that was changed is written. That is the
 * approach Electribe Studio already took and it is kept here.
 */
import { BLOCKS, field, readRaw, writeRaw, describe, offsetOf, typeOf } from "./map/index.mjs";
import { converter } from "./map/convert.mjs";
import { PATTERN_FILE, SINGLE_PATTERN_FILE } from "./map/address.mjs";
import { render, text, TextError } from "./text.mjs";

export const BLOCK_SIZE = BLOCKS.get("pattern").size;
const FRAME_START = "PTST";
const FRAME_END_AT = 15356;
const FRAME_END = "PTED";

const ascii = (bytes, at, n) => String.fromCharCode(...bytes.subarray(at, at + n));

/** A problem with a file, said in a way the page can show as it is: `key` and `vars` are a text (src/text.mjs). */
export class FileError extends TextError {
  constructor(key, vars, details = {}) {
    super(key, vars);
    this.name = "FileError";
    Object.assign(this, details);
  }
}

/** Why a block is not a pattern (a text), or null when it is one. */
export function frameProblem(block) {
  if (block.length !== BLOCK_SIZE) return text("patternfile.frame.size", { got: block.length, want: BLOCK_SIZE });
  if (ascii(block, 0, 4) !== FRAME_START) return text("patternfile.frame.start");
  if (ascii(block, FRAME_END_AT, 4) !== FRAME_END) return text("patternfile.frame.end");
  return null;
}

/** Longest pattern name: the name field is 16 characters (measure:2026-09-16/pattern-diff). */
export const NAME_LENGTH = 16;

/**
 * A pattern name as the device can show it: printable ASCII only (the name entry of the device offers nothing
 * else, derived), at most 16 characters, no spaces at either end. Empty when nothing is left.
 */
export function cleanName(text) {
  return String(text ?? "").replace(/[^\x20-\x7e]/g, "").trim().slice(0, NAME_LENGTH).trimEnd();
}

export class Pattern {
  /** @param {Uint8Array} bytes a copy is taken */
  constructor(bytes) {
    const problem = frameProblem(bytes);
    if (problem) throw new FileError("patternfile.block", { problem });
    this.bytes = Uint8Array.from(bytes);
  }

  raw(id, indices = []) { return readRaw(this.bytes, field(id), indices); }

  /**
   * Write a raw value. Returns the change, so the caller can undo it. The
   * old bytes are kept as bytes: a device may hold a value outside the range
   * the editor lets anyone write, and undo must put exactly that back.
   */
  setRaw(id, indices, raw) {
    const f = field(id);
    const at = offsetOf(f, indices);
    const width = typeOf(f).width;
    const before = readRaw(this.bytes, f, indices);
    const beforeBytes = this.bytes.slice(at, at + width);
    writeRaw(this.bytes, f, indices, raw);
    return { id, indices, before, after: raw, at, beforeBytes };
  }

  /** The value in plain words. */
  plain(id, indices = []) { return describe(field(id), this.raw(id, indices)); }

  /**
   * Set a value given in plain words. When the field already shows that
   * value, nothing is written: several bytes can show the same note value,
   * and rewriting would replace the one the device chose.
   */
  setPlain(id, indices, value) {
    const f = field(id);
    const c = converter(f.convert);
    const current = this.raw(id, indices);
    if (c.fromRaw(current) === value) return null;
    return this.setRaw(id, indices, c.toRaw(value));
  }

  undo(change) { this.bytes.set(change.beforeBytes, change.at); }

  get name() { return this.raw("pattern.name"); }

  /** The byte offset of a field instance inside the block, for diffs and reports. */
  static offset(id, indices = []) { return offsetOf(field(id), indices); }
}

/** A pattern backup: a header the device wrote, then up to 250 patterns. */
export class PatternFile {
  constructor(header, blocks) {
    this.header = header;
    this.blocks = blocks;
  }

  /** Check identity, size and every pattern's frame before anything is shown. */
  static parse(input) {
    const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
    const min = PATTERN_FILE.header + BLOCK_SIZE;
    if (bytes.length < min) {
      throw new FileError("patternfile.small", { size: bytes.length, min });
    }
    if (ascii(bytes, 0, 4) !== PATTERN_FILE.magic || ascii(bytes, 0x10, 9) !== PATTERN_FILE.device) {
      throw new FileError("patternfile.notBackup");
    }
    const rest = bytes.length - PATTERN_FILE.header;
    if (rest % BLOCK_SIZE) {
      throw new FileError("patternfile.cut", { rest });
    }
    const count = rest / BLOCK_SIZE;
    if (count > PATTERN_FILE.count) {
      throw new FileError("patternfile.many", { count, max: PATTERN_FILE.count });
    }
    const broken = [];
    const blocks = [];
    for (let n = 0; n < count; n++) {
      const at = PATTERN_FILE.header + n * BLOCK_SIZE;
      const block = bytes.slice(at, at + BLOCK_SIZE);
      const problem = frameProblem(block);
      if (problem) broken.push({ pattern: n + 1, problem });
      blocks.push(block);
    }
    if (broken.length) {
      const list = broken.slice(0, 5).map(b => text("patternfile.brokenOne", { n: b.pattern, problem: b.problem }));
      throw new FileError(broken.length > 5 ? "patternfile.brokenMore" : "patternfile.broken", { count: broken.length, list: list.map(render).join(", ") }, { broken });
    }
    return new PatternFile(bytes.slice(0, PATTERN_FILE.header), blocks);
  }

  get count() { return this.blocks.length; }

  /** Pattern n, counted from 1 as on the device. The pattern works on its own copy. */
  pattern(n) {
    if (!Number.isInteger(n) || n < 1 || n > this.count) throw new RangeError(`Pattern ${n} gibt es in dieser Datei nicht`);
    return new Pattern(this.blocks[n - 1]);
  }

  /** Put an edited pattern back into slot n. */
  replace(n, pattern) {
    if (!(pattern instanceof Pattern)) throw new TypeError("expected a Pattern");
    if (n < 1 || n > this.count) throw new RangeError(`Pattern ${n} gibt es in dieser Datei nicht`);
    this.blocks[n - 1] = Uint8Array.from(pattern.bytes);
  }

  /** Name of pattern n without building a Pattern, for long lists. */
  name(n) { return readRaw(this.blocks[n - 1], field("pattern.name")); }

  toBytes() {
    const out = new Uint8Array(this.header.length + this.blocks.length * BLOCK_SIZE);
    out.set(this.header, 0);
    this.blocks.forEach((b, i) => out.set(b, this.header.length + i * BLOCK_SIZE));
    return out;
  }
}

/**
 * The wrapper a device writes around one pattern. Byte-identical across the
 * device-written files Electribe Studio compared; the slot lives only in the
 * file name.
 */
function singlePatternHeader() {
  const h = new Uint8Array(SINGLE_PATTERN_FILE.header);
  h.fill(0xff, 0x24);
  [..."KORG"].forEach((c, i) => { h[i] = c.charCodeAt(0); });
  [..."e2sampler"].forEach((c, i) => { h[0x10 + i] = c.charCodeAt(0); });
  h[0x20] = 0x01;
  return h;
}

/** The pattern, and the header as the device wrote it, so saving keeps it. */
export function parseSinglePattern(input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (bytes.length !== SINGLE_PATTERN_FILE.header + BLOCK_SIZE || ascii(bytes, 0, 4) !== "KORG" || ascii(bytes, 0x10, 9) !== "e2sampler") {
    throw new FileError("patternfile.notSingle");
  }
  const pattern = new Pattern(bytes.subarray(SINGLE_PATTERN_FILE.header));
  pattern.header = bytes.slice(0, SINGLE_PATTERN_FILE.header);
  return pattern;
}

export function toSinglePattern(pattern, header = pattern.header ?? singlePatternHeader()) {
  const out = new Uint8Array(SINGLE_PATTERN_FILE.header + BLOCK_SIZE);
  out.set(header, 0);
  out.set(pattern.bytes, SINGLE_PATTERN_FILE.header);
  return out;
}
