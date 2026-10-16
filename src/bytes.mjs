/**
 * The 7-bit packing every Electribe SysEx payload uses.
 *
 * MIDI data bytes carry seven usable bits, so eight transmitted bytes carry
 * seven real ones: a leading byte collects the high bits, least significant
 * bit first, then follow the seven stripped bytes.
 *
 * The reference implementation in Hacktribe drops the final block when the
 * input length leaves a remainder of six. 524, the length of an effect
 * record, is such a length. Splitting a write in two halves of 256 and 268
 * hides it, which is why nobody noticed. This implementation keeps the block.
 */

export function syxEnc(bytes) {
  // Index into the input; slicing per block copies all of it every seven
  // bytes and turns a pattern transfer quadratic.
  const out = [];
  for (let i = 0; i < bytes.length; i += 7) {
    const end = Math.min(i + 7, bytes.length);
    let high = 0;
    for (let k = i; k < end; k++) high |= ((bytes[k] & 0x80) >> 7) << (k - i);
    out.push(high);
    for (let k = i; k < end; k++) out.push(bytes[k] & 0x7f);
  }
  return out;
}

export function syxDec(syx) {
  const out = [];
  for (let i = 0; i < syx.length; i += 8) {
    const end = Math.min(i + 8, syx.length);
    const high = syx[i];
    for (let k = i + 1; k < end; k++) out.push(syx[k] | (((high >> (k - i - 1)) & 1) << 7));
  }
  return out;
}

export const u32le = n => [n & 0xff, (n >>> 8) & 0xff, (n >>> 16) & 0xff, (n >>> 24) & 0xff];

export const readU32le = (a, i = 0) =>
  ((a[i] | (a[i + 1] << 8) | (a[i + 2] << 16) | (a[i + 3] << 24)) >>> 0);

/** Latin-1, stopping at the first NUL, the way the device stores names. */
export function readName(bytes) {
  const end = bytes.indexOf(0);
  return String.fromCharCode(...Array.from(end === -1 ? bytes : bytes.slice(0, end)));
}

export function writeName(target, offset, text, width) {
  for (let i = 0; i < width; i++) {
    target[offset + i] = i < text.length ? text.charCodeAt(i) & 0xff : 0;
  }
}
