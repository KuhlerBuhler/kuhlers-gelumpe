/**
 * A tiny PNG writer for the Blechy previews: a 1-bit picture (rows of "#" and ".") shown as an LCD would,
 * every pixel a square with a thin gap. Only node:zlib, no dependency.
 */
import { deflateSync, inflateSync } from "node:zlib";

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, "ascii");
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}

/** An RGB picture of `width` x `height` from a function that gives the colour of each pixel as [r, g, b]. */
export function png(width, height, colourAt) {
  const raw = Buffer.alloc((width * 3 + 1) * height);
  let at = 0;
  for (let y = 0; y < height; y++) {
    raw[at++] = 0;
    for (let x = 0; x < width; x++) {
      const [r, g, b] = colourAt(x, y);
      raw[at++] = r; raw[at++] = g; raw[at++] = b;
    }
  }
  const head = Buffer.alloc(13);
  head.writeUInt32BE(width, 0);
  head.writeUInt32BE(height, 4);
  head[8] = 8; head[9] = 2;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", head), chunk("IDAT", deflateSync(raw, { level: 9 })), chunk("IEND", Buffer.alloc(0)),
  ]);
}

const PAPER = [212, 224, 196];
const GAP = [196, 209, 180];
const INK = [24, 32, 28];

/** Rows of "#" and "." as a PNG, `scale` device pixels per pixel with a one pixel gap, optional margin. */
export function pixelPng(rows, scale = 6, margin = 0) {
  const h = rows.length;
  const w = Math.max(...rows.map(r => r.length));
  return png(w * scale + margin * 2, h * scale + margin * 2, (x, y) => {
    const px = x - margin;
    const py = y - margin;
    if (px < 0 || py < 0 || px >= w * scale || py >= h * scale) return PAPER;
    if (px % scale === scale - 1 || py % scale === scale - 1) return GAP;
    return rows[Math.floor(py / scale)]?.[Math.floor(px / scale)] === "#" ? INK : PAPER;
  });
}

/** Several pictures side by side in one sheet, `gap` pixels of paper between them. */
export function sheet(pictures, gap = 2) {
  const h = Math.max(...pictures.map(p => p.length));
  const rows = Array.from({ length: h }, () => "");
  pictures.forEach((p, i) => {
    const w = Math.max(...p.map(r => r.length));
    for (let y = 0; y < h; y++) rows[y] += (p[y] ?? "").padEnd(w, ".") + (i < pictures.length - 1 ? ".".repeat(gap) : "");
  });
  return rows;
}

/** A grey scale PNG (not interlaced, 1 to 8 bits) as rows of "#" for the dark pixels and "." for the light ones. */
export function readPng(bytes) {
  const buf = Buffer.from(bytes);
  let at = 8;
  let head = null;
  const data = [];
  while (at < buf.length) {
    const size = buf.readUInt32BE(at);
    const type = buf.toString("ascii", at + 4, at + 8);
    const body = buf.subarray(at + 8, at + 8 + size);
    if (type === "IHDR") head = { width: body.readUInt32BE(0), height: body.readUInt32BE(4), depth: body[8], colour: body[9], interlace: body[12] };
    if (type === "IDAT") data.push(body);
    at += 12 + size;
  }
  if (!head || head.colour !== 0 || head.interlace !== 0 || head.depth > 8) throw new Error("only grey scale PNGs without interlacing are read");
  const raw = inflateSync(Buffer.concat(data));
  const stride = Math.ceil((head.width * head.depth) / 8);
  const out = Buffer.alloc(stride * head.height);
  for (let y = 0; y < head.height; y++) {
    const filter = raw[y * (stride + 1)];
    for (let x = 0; x < stride; x++) {
      const cur = raw[y * (stride + 1) + 1 + x];
      const left = x ? out[y * stride + x - 1] : 0;
      const up = y ? out[(y - 1) * stride + x] : 0;
      const upLeft = x && y ? out[(y - 1) * stride + x - 1] : 0;
      const paeth = () => { const p = left + up - upLeft; const pa = Math.abs(p - left); const pb = Math.abs(p - up); const pc = Math.abs(p - upLeft); return pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft; };
      out[y * stride + x] = (cur + [0, left, up, (left + up) >> 1, paeth()][filter]) & 255;
    }
  }
  const max = (1 << head.depth) - 1;
  return Array.from({ length: head.height }, (_, y) => Array.from({ length: head.width }, (_, x) => {
    const bit = x * head.depth;
    const sample = (out[y * stride + (bit >> 3)] >> (8 - head.depth - (bit & 7))) & max;
    return sample * 2 < max ? "#" : ".";
  }).join(""));
}
