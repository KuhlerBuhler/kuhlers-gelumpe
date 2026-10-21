/**
 * Picture files for korg.file.frame (SCRIPT_GIF in data/script/contract.mjs): packing them for the card and reading one frame
 * the way the runtime does, into the slots of an array, one byte to a slot.
 */
import { SCRIPT_GIF } from "../../data/script/contract.mjs";

const FRAME = SCRIPT_GIF.frameHeader + SCRIPT_GIF.frameBytes;

/** The card path of file `n` (0 to 99), without the volume prefix. */
export const gifPath = n => `${SCRIPT_GIF.folder}GIF${String(n).padStart(2, "0")}.E2G`;

/** @param {{ delay: number, bytes: Uint8Array }[]} frames delay in ms (1 to 65535) and 1024 bytes of display memory each */
export function packGif(frames) {
  if (frames.length < 1 || frames.length > 0xFFFF) throw new Error(`${frames.length} frames, 1 to 65535 allowed`);
  const out = new Uint8Array(SCRIPT_GIF.header + frames.length * FRAME);
  const view = new DataView(out.buffer);
  view.setUint32(0, SCRIPT_GIF.magic, true);
  view.setUint16(4, SCRIPT_GIF.version, true);
  view.setUint16(6, frames.length, true);
  frames.forEach(({ delay, bytes }, i) => {
    if (bytes.length !== SCRIPT_GIF.frameBytes) throw new Error(`frame ${i}: ${bytes.length} bytes, not ${SCRIPT_GIF.frameBytes}`);
    const at = SCRIPT_GIF.header + i * FRAME;
    view.setUint16(at, Math.max(1, Math.min(0xFFFF, Math.round(delay))), true);
    out.set(bytes, at + SCRIPT_GIF.frameHeader);
  });
  return out;
}

/**
 * Reads frame `index` of `file` (the bytes of the card file, or undefined when there is none) into `slots`, one byte to a slot.
 * -> its delay in ms (at least 1), 0 past the last frame, -1 when the file is missing, not a picture file or cut short.
 * After -1 the device may have changed the last quarter of the slots (it reads there first); the browser leaves them.
 */
export function readGifFrame(file, index, slots) {
  if (!file || file.length < SCRIPT_GIF.header) return -1;
  const view = new DataView(file.buffer, file.byteOffset, file.byteLength);
  if (view.getUint32(0, true) !== SCRIPT_GIF.magic || view.getUint16(4, true) !== SCRIPT_GIF.version) return -1;
  if (index >= view.getUint16(6, true)) return 0;
  const at = SCRIPT_GIF.header + index * FRAME;
  if (at + FRAME > file.length) return -1;
  for (let i = 0; i < SCRIPT_GIF.frameBytes; i++) slots[i] = file[at + SCRIPT_GIF.frameHeader + i];
  return Math.max(1, view.getUint16(at, true));
}
