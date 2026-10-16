/**
 * Byte types of the device map: width, sign and encoding of a field.
 *
 * A type reads and writes one value at one offset. What the value means in
 * plain words is the converter's business, not the type's.
 */
import { readName, writeName } from "../bytes.mjs";

const INT = {
  u8: { width: 1, min: 0, max: 0xff },
  s8: { width: 1, min: -128, max: 127 },
  u16le: { width: 2, min: 0, max: 0xffff },
  s16le: { width: 2, min: -0x8000, max: 0x7fff },
  u32le: { width: 4, min: 0, max: 0xffffffff },
};

function intType(name) {
  const { width, min, max } = INT[name];
  const signed = min < 0;
  return {
    name, width, min, max, kind: "int",
    read(bytes, at) {
      let v = 0;
      for (let i = width - 1; i >= 0; i--) v = v * 256 + bytes[at + i];
      if (signed && v > max) v -= 2 ** (8 * width);
      return v;
    },
    write(bytes, at, value) {
      if (!Number.isInteger(value) || value < min || value > max) {
        throw new RangeError(`${value} does not fit ${name}`);
      }
      let v = value < 0 ? value + 2 ** (8 * width) : value;
      for (let i = 0; i < width; i++) { bytes[at + i] = v % 256; v = Math.floor(v / 256); }
    },
  };
}

/** Latin-1 text, NUL-padded, the way the device stores names. */
function textType(name, width) {
  return {
    name, width, kind: "text",
    read: (bytes, at) => readName(bytes.subarray(at, at + width)),
    write(bytes, at, text) {
      const s = String(text);
      for (const ch of s) {
        const c = ch.charCodeAt(0);
        if (c < 0x20 || c > 0x7e) throw new RangeError(`the display cannot show ${JSON.stringify(ch)}`);
      }
      if (s.length > width) throw new RangeError(`"${s}" is longer than ${width} characters`);
      writeName(bytes, at, s, width);
    },
  };
}

/** A run of bytes nobody has decoded, or a bitmap; handled as a copy. */
function bytesType(name, width) {
  return {
    name, width, kind: "bytes",
    read: (bytes, at) => Uint8Array.from(bytes.subarray(at, at + width)),
    write(bytes, at, value) {
      if (value.length !== width) throw new RangeError(`expected ${width} bytes, got ${value.length}`);
      bytes.set(value, at);
    },
  };
}

const cache = new Map();

/**
 * @param {string} spec u8, s8, u16le, s16le, u32le, latin1:N, ascii:N,
 *   bytes:N, bitmap:WxH
 */
export function parseType(spec) {
  if (cache.has(spec)) return cache.get(spec);
  let type;
  if (INT[spec]) type = intType(spec);
  else {
    const m = /^(latin1|ascii|bytes|bitmap):(\d+)(?:x(\d+))?$/.exec(spec);
    if (!m) throw new Error(`unknown type ${spec}`);
    const [, kind, a, b] = m;
    if (kind === "bitmap") {
      if (!b || (Number(a) * Number(b)) % 8) throw new Error(`bad bitmap size ${spec}`);
      type = { ...bytesType(spec, (Number(a) * Number(b)) / 8), kind: "bitmap", pixels: [Number(a), Number(b)] };
    } else if (kind === "bytes") type = bytesType(spec, Number(a));
    else type = textType(spec, Number(a));
  }
  cache.set(spec, type);
  return type;
}
