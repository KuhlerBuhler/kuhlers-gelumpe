/** The 128x64 display bytes (8 pages, bit 0 the top row) as grey PNGs, several to a sheet. */
import { deflateSync } from "node:zlib";
import { writeFileSync } from "node:fs";

const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1; return c >>> 0; });
const crc32 = buf => { let c = ~0; for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8); return ~c >>> 0; };
const chunk = (type, data) => {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4);
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
};

export function displaySheet(displays, file, { columns = 2, scale = 3, gap = 8 } = {}) {
  const w = 128 * scale, h = 64 * scale;
  const rows = Math.ceil(displays.length / columns);
  const W = columns * (w + gap) - gap, H = rows * (h + gap) - gap;
  const raw = Buffer.alloc((W + 1) * H, 128);
  for (let y = 0; y < H; y++) raw[y * (W + 1)] = 0;
  displays.forEach((d, i) => {
    const ox = (i % columns) * (w + gap), oy = Math.floor(i / columns) * (h + gap);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const px = Math.floor(x / scale), py = Math.floor(y / scale);
      raw[(oy + y) * (W + 1) + 1 + ox + x] = (d[(py >> 3) * 128 + px] >> (py & 7)) & 1 ? 0 : 255;
    }
  });
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4); ihdr[8] = 8;
  writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]));
}
