/**
 * The CRC-32 of two pieces put together, from the CRC-32 of each and the length of the second (zlib's crc32_combine). The editor
 * checks a file that was put together on the card out of pieces it never held, from the CRCs the device answers per piece.
 */
const times = (matrix, vector) => {
  let sum = 0;
  for (let i = 0; vector; vector >>>= 1, i++) if (vector & 1) sum ^= matrix[i];
  return sum >>> 0;
};
const square = (target, matrix) => { for (let n = 0; n < 32; n++) target[n] = times(matrix, matrix[n]); };

export function crc32Combine(first, second, length) {
  first >>>= 0;
  if (length <= 0) return first;
  const even = new Array(32);
  const odd = new Array(32);
  odd[0] = 0xedb88320;
  for (let n = 1, row = 1; n < 32; n++, row <<= 1) odd[n] = row;
  square(even, odd);
  square(odd, even);
  do {
    square(even, odd);
    if (length & 1) first = times(even, first);
    length >>>= 1;
    if (!length) break;
    square(odd, even);
    if (length & 1) first = times(odd, first);
    length >>>= 1;
  } while (length);
  return (first ^ second) >>> 0;
}

/** The CRC-32 of pieces in order: [{ crc, length }]. */
export const crc32Join = pieces => pieces.reduce((acc, p, i) => (i ? crc32Combine(acc, p.crc, p.length) : p.crc >>> 0), 0);
