/**
 * A small GIF decoder (GIF87a and GIF89a): global and local color tables, LZW, interlace, transparency, disposal 0 to 3
 * and delays. Every frame comes out composed at canvas size as RGBA, the way a browser shows it; the canvas starts
 * transparent.
 */

function lzw(data, minSize, count) {
  const out = new Uint8Array(count);
  const clear = 1 << minSize, eoi = clear + 1;
  const prefix = new Uint16Array(4096), suffix = new Uint8Array(4096), stack = new Uint8Array(4097);
  for (let i = 0; i < clear; i++) suffix[i] = i;
  let size = minSize + 1, next = clear + 2, old = -1, first = 0, pos = 0, acc = 0, bits = 0, i = 0;
  while (pos < count) {
    while (bits < size && i < data.length) { acc |= data[i++] << bits; bits += 8; }
    if (bits < size) break;
    const code = acc & ((1 << size) - 1);
    acc >>>= size; bits -= size;
    if (code === clear) { size = minSize + 1; next = clear + 2; old = -1; continue; }
    if (code === eoi) break;
    if (old < 0) {
      if (code >= clear) throw new Error("GIF: bad first code");
      out[pos++] = first = code; old = code;
      continue;
    }
    let c = code, sp = 0;
    if (code >= next) {
      if (code > next) throw new Error("GIF: bad code");
      stack[sp++] = first; c = old;
    }
    while (c >= clear) { stack[sp++] = suffix[c]; c = prefix[c]; }
    stack[sp++] = first = c;
    if (next < 4096) {
      prefix[next] = old; suffix[next] = first; next++;
      if (next === 1 << size && size < 12) size++;
    }
    while (sp && pos < count) out[pos++] = stack[--sp];
    old = code;
  }
  return out;   // a short stream leaves the rest at index 0
}

function deinterlace(idx, w, h) {
  const out = new Uint8Array(idx.length);
  let row = 0;
  for (const [start, step] of [[0, 8], [4, 8], [2, 4], [1, 2]]) {
    for (let y = start; y < h; y += step) out.set(idx.subarray(row * w, ++row * w), y * w);
  }
  return out;
}

/** { width, height, loops, frames: [{ rgba, delay (ms), x, y, w, h, disposal }] } */
export function decodeGif(bytes) {
  const sig = String.fromCharCode(...bytes.subarray(0, 6));
  if (sig !== "GIF87a" && sig !== "GIF89a") throw new Error("not a GIF");
  let p = 6;
  const u16 = () => { p += 2; return bytes[p - 2] | bytes[p - 1] << 8; };
  const table = (flags) => {
    if (!(flags & 0x80)) return null;
    const n = 3 << ((flags & 7) + 1);
    p += n;
    return bytes.subarray(p - n, p);
  };
  const blocks = () => {
    const parts = [];
    for (let n = bytes[p++]; n; n = bytes[p++]) { parts.push(bytes.subarray(p, p + n)); p += n; }
    const all = new Uint8Array(parts.reduce((s, b) => s + b.length, 0));
    let at = 0;
    for (const b of parts) { all.set(b, at); at += b.length; }
    return all;
  };
  const width = u16(), height = u16(), flags = bytes[p];
  p += 3;
  const global = table(flags);
  const canvas = new Uint8ClampedArray(width * height * 4);
  const frames = [];
  let gce = null, loops = null;
  while (p < bytes.length) {
    const kind = bytes[p++];
    if (kind === 0x3b) break;
    if (kind === 0x21) {
      const label = bytes[p++];
      const data = blocks();
      if (label === 0xf9 && data.length >= 4) {
        gce = { disposal: data[0] >> 2 & 7, transparent: data[0] & 1 ? data[3] : -1, delay: (data[1] | data[2] << 8) * 10 };
      } else if (label === 0xff && String.fromCharCode(...data.subarray(0, 11)) === "NETSCAPE2.0" && data.length >= 14) {
        loops = data[12] | data[13] << 8;
      }
      continue;
    }
    if (kind !== 0x2c) throw new Error(`GIF: unknown block 0x${kind.toString(16)} at ${p - 1}`);
    const x = u16(), y = u16(), w = u16(), h = u16(), f = bytes[p++];
    const colors = table(f) ?? global;
    if (!colors) throw new Error("GIF: no color table");
    const minSize = bytes[p++];
    if (minSize < 2 || minSize > 11) throw new Error("GIF: bad LZW code size");
    let idx = lzw(blocks(), minSize, w * h);
    if (f & 0x40) idx = deinterlace(idx, w, h);
    const { disposal = 0, transparent = -1, delay = 0 } = gce ?? {};
    const saved = disposal === 3 ? canvas.slice() : null;
    for (let r = 0; r < h; r++) {
      const cy = y + r;
      if (cy >= height) break;
      for (let c = 0; c < w; c++) {
        const cx = x + c, k = idx[r * w + c];
        if (cx >= width || k === transparent || 3 * k + 2 >= colors.length) continue;
        const o = 4 * (cy * width + cx);
        canvas[o] = colors[3 * k]; canvas[o + 1] = colors[3 * k + 1]; canvas[o + 2] = colors[3 * k + 2]; canvas[o + 3] = 255;
      }
    }
    frames.push({ rgba: canvas.slice(), delay, x, y, w, h, disposal });
    if (disposal === 2) {
      for (let r = y; r < Math.min(y + h, height); r++) canvas.fill(0, 4 * (r * width + x), 4 * (r * width + Math.min(x + w, width)));
    } else if (saved) canvas.set(saved);
    gce = null;
  }
  return { width, height, loops, frames };
}
