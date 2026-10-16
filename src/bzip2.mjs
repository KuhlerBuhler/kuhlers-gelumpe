/**
 * bzip2 decompression, written for this project (no dependency): the three sections of a bsdiff patch are
 * bzip2 streams, and the Patcher page applies Hacktribe's patch in the browser.
 *
 * Decodes what the reference bzip2 writes: the stream header BZh1 to BZh9, any number of blocks, each block's
 * CRC and the stream's combined CRC checked. Randomised blocks (obsolete since bzip2 0.9.5) are refused.
 * `maxSize` bounds the output so a small hostile file cannot ask for gigabytes.
 */

const CRC = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i << 24;
    for (let k = 0; k < 8; k++) c = c & 0x80000000 ? (c << 1) ^ 0x04c11db7 : c << 1;
    table[i] = c >>> 0;
  }
  return table;
})();

class Bits {
  constructor(data) { this.data = data; this.pos = 0; this.buf = 0; this.n = 0; }
  /** Up to 24 bits, most significant first. */
  read(k) {
    while (this.n < k) {
      if (this.pos >= this.data.length) throw new Error("bzip2: the data ends too early");
      this.buf = ((this.buf << 8) | this.data[this.pos++]) >>> 0;
      this.n += 8;
    }
    this.n -= k;
    const out = (this.buf >>> this.n) & ((1 << k) - 1);
    this.buf &= (1 << this.n) - 1;
    return out;
  }
  bit() { return this.read(1); }
}

/** Canonical Huffman table of one coding group, in the order bzip2 assigns codes (by length, then symbol). */
function huffman(lengths, alphaSize) {
  const count = new Int32Array(22);
  for (let i = 0; i < alphaSize; i++) count[lengths[i]]++;
  const first = new Int32Array(22), offset = new Int32Array(22), perm = new Int32Array(alphaSize);
  let code = 0, at = 0;
  for (let len = 1; len <= 20; len++) {
    first[len] = code;
    offset[len] = at;
    for (let s = 0; s < alphaSize; s++) if (lengths[s] === len) perm[at++] = s;
    code = (code + count[len]) << 1;
  }
  return { count, first, offset, perm };
}

function symbol(bits, table) {
  let code = 0;
  for (let len = 1; len <= 20; len++) {
    code = (code << 1) | bits.bit();
    const d = code - table.first[len];
    if (d >= 0 && d < table.count[len]) return table.perm[table.offset[len] + d];
  }
  throw new Error("bzip2: bad Huffman code");
}

class Out {
  constructor(max) { this.max = max; this.buf = new Uint8Array(1 << 16); this.len = 0; }
  need(extra) {
    if (this.len + extra > this.max) throw new Error("bzip2: the output is larger than allowed");
    if (this.len + extra <= this.buf.length) return;
    let size = this.buf.length;
    while (size < this.len + extra) size *= 2;
    const next = new Uint8Array(Math.min(size, Math.max(this.max, this.len + extra)));
    next.set(this.buf.subarray(0, this.len));
    this.buf = next;
  }
}

function block(bits, level, out) {
  if (bits.bit()) throw new Error("bzip2: randomised blocks are not supported");
  const origPtr = bits.read(24);
  const used = [];
  const groups16 = bits.read(16);
  for (let i = 0; i < 16; i++) {
    if (!(groups16 & (0x8000 >> i))) continue;
    const bitsOf = bits.read(16);
    for (let j = 0; j < 16; j++) if (bitsOf & (0x8000 >> j)) used.push(i * 16 + j);
  }
  if (!used.length) throw new Error("bzip2: a block without symbols");
  const alphaSize = used.length + 2, end = used.length + 1;

  const nGroups = bits.read(3);
  if (nGroups < 2 || nGroups > 6) throw new Error("bzip2: bad number of coding tables");
  const nSelectors = bits.read(15);
  if (nSelectors < 1) throw new Error("bzip2: no selectors");
  const order = Array.from({ length: nGroups }, (_, i) => i);
  const selectors = new Uint8Array(nSelectors);
  for (let i = 0; i < nSelectors; i++) {
    let j = 0;
    while (bits.bit()) if (++j >= nGroups) throw new Error("bzip2: bad selector");
    const g = order[j];
    order.splice(j, 1);
    order.unshift(g);
    selectors[i] = g;
  }
  const tables = [];
  for (let t = 0; t < nGroups; t++) {
    const lengths = new Uint8Array(alphaSize);
    let len = bits.read(5);
    for (let s = 0; s < alphaSize; s++) {
      for (;;) {
        if (len < 1 || len > 20) throw new Error("bzip2: bad code length");
        if (!bits.bit()) break;
        len += bits.bit() ? -1 : 1;
      }
      lengths[s] = len;
    }
    tables.push(huffman(lengths, alphaSize));
  }

  // Huffman symbols, run-length (RUNA/RUNB) and move-to-front decoding.
  const limit = level * 100000;
  const data = new Uint8Array(limit);
  const counts = new Int32Array(256);
  const mtf = Uint8Array.from(used.map((_, i) => i));
  let n = 0, run = 0, weight = 1, group = -1, left = 0, table = null;
  for (;;) {
    if (left === 0) {
      if (++group >= nSelectors) throw new Error("bzip2: the selectors ran out");
      table = tables[selectors[group]];
      left = 50;
    }
    left--;
    const s = symbol(bits, table);
    if (s <= 1) {
      run += (s + 1) * weight;
      weight <<= 1;
      if (run > limit) throw new Error("bzip2: a run is longer than a block");
      continue;
    }
    if (run) {
      if (n + run > limit) throw new Error("bzip2: the block is too long");
      const byte = used[mtf[0]];
      data.fill(byte, n, n + run);
      counts[byte] += run;
      n += run;
      run = 0;
      weight = 1;
    }
    if (s === end) break;
    if (n >= limit) throw new Error("bzip2: the block is too long");
    const index = s - 1, value = mtf[index];
    mtf.copyWithin(1, 0, index);
    mtf[0] = value;
    const byte = used[value];
    data[n++] = byte;
    counts[byte]++;
  }
  if (origPtr >= n && n > 0) throw new Error("bzip2: bad start pointer");

  // Inverse Burrows-Wheeler transform, then the first run-length stage (four equal bytes and a repeat count).
  const start = new Int32Array(256);
  for (let i = 0, sum = 0; i < 256; i++) { start[i] = sum; sum += counts[i]; }
  const next = new Uint32Array(n);
  for (let i = 0; i < n; i++) next[start[data[i]]++] = i;
  let crc = 0xffffffff, pos = n ? next[origPtr] : 0, same = 0, last = -1;
  const put = (byte, times) => {
    out.need(times);
    const buf = out.buf;
    for (let k = 0; k < times; k++) {
      buf[out.len++] = byte;
      crc = ((crc << 8) ^ CRC[(crc >>> 24) ^ byte]) >>> 0;
    }
  };
  for (let k = 0; k < n; k++) {
    const byte = data[pos];
    pos = next[pos];
    if (same === 4) {
      if (byte) put(last, byte);
      same = 0;
      last = -1;
      continue;
    }
    if (byte === last) same++;
    else { last = byte; same = 1; }
    put(byte, 1);
  }
  return (~crc) >>> 0;
}

/** Decompress one bzip2 stream. */
export function bunzip2(input, { maxSize = 1 << 28 } = {}) {
  const data = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (data.length < 4 || data[0] !== 0x42 || data[1] !== 0x5a || data[2] !== 0x68 || data[3] < 0x31 || data[3] > 0x39) {
    throw new Error("bzip2: the stream header BZh1 to BZh9 is missing");
  }
  const level = data[3] - 0x30;
  const bits = new Bits(data);
  bits.pos = 4;
  const out = new Out(maxSize);
  let combined = 0;
  for (;;) {
    const magic = [bits.read(24), bits.read(24)];
    if (magic[0] === 0x314159 && magic[1] === 0x265359) {
      const stored = (bits.read(16) << 16 | bits.read(16)) >>> 0;
      const crc = block(bits, level, out);
      if (crc !== stored) throw new Error("bzip2: a block's checksum does not match");
      combined = (((combined << 1) | (combined >>> 31)) ^ crc) >>> 0;
    } else if (magic[0] === 0x177245 && magic[1] === 0x385090) {
      const stored = (bits.read(16) << 16 | bits.read(16)) >>> 0;
      if (stored !== combined) throw new Error("bzip2: the stream's checksum does not match");
      return out.buf.slice(0, out.len);
    } else {
      throw new Error("bzip2: bad block header");
    }
  }
}
