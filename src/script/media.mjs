/**
 * Pictures from the card for the plugin calls korg.file.count, korg.file.name and korg.file.picture: start images (.bmp, kind 0)
 * and loading animations (.blla, kind 1) in KORG/blechtribe/Media/. This is the reference the simulator, the firmware and the
 * app are held against.
 */
import { decodeBmp } from "../splash-bmp.mjs";
import { decodeAnimation } from "../loading-anim.mjs";
import { frameOfPixels } from "./gif.mjs";

/** The file endings of each kind, in lower case: 0 images, 1 animations. */
export const MEDIA_KINDS = Object.freeze([".bmp", ".blla"]);
/** The one folder that is searched, no other. */
export const MEDIA_FOLDER = "KORG/blechtribe/Media/";
/** At most this many files of a kind are listed, the rest is left out. */
export const MEDIA_MAX_FILES = 64;
/** The longest name korg.file.name gives; a longer one is cut to MEDIA_NAME_MAX - 2 characters and "..". */
export const MEDIA_NAME_MAX = 17;
/** Longest file name the folder walk takes, as the BLECH menu's list (tools/patch/script_menu.s, menu_dir_next). */
const FILE_NAME_MAX = 31;

/**
 * The polarity of a picture in the slots, one switch for both kinds until it is measured on the device: true sets the bit of a
 * pixel that is drawn, as frameOfPixels does. Drawn is the darker palette entry of a .bmp, and for a .blla what
 * frameToPixels (src/loading-anim.mjs) calls drawn, the complement of the bits the loading overlay writes.
 */
export const DRAWN_IS_SET = true;

/** The name korg.file.name shows for a file name: without its ending, longer than MEDIA_NAME_MAX cut and marked with "..". */
export function mediaName(fileName, kind) {
  const base = fileName.slice(0, fileName.length - MEDIA_KINDS[kind].length);
  return base.length > MEDIA_NAME_MAX ? base.slice(0, MEDIA_NAME_MAX - 2) + ".." : base;
}

/**
 * The files of a kind on a card (a Map of path to bytes, in the order the files were written, as FatFs walks a folder):
 * only those right in MEDIA_FOLDER (folder name in any case), not starting with a dot, at most 31 characters that end in the
 * kind's ending (any case) behind at least one more, the first MEDIA_MAX_FILES of them. -> [{ path, name }]
 */
export function listMedia(card, kind) {
  const suffix = MEDIA_KINDS[kind];
  const out = [];
  for (const path of card.keys()) {
    if (out.length === MEDIA_MAX_FILES) break;
    if (path.length <= MEDIA_FOLDER.length || path.slice(0, MEDIA_FOLDER.length).toLowerCase() !== MEDIA_FOLDER.toLowerCase()) continue;
    const file = path.slice(MEDIA_FOLDER.length);
    if (file.includes("/") || file.startsWith(".") || file.length > FILE_NAME_MAX || file.length <= suffix.length) continue;
    if (file.slice(-suffix.length).toLowerCase() !== suffix) continue;
    out.push({ path, name: mediaName(file, kind) });
  }
  return out;
}

/** The characters of a name as korg.file.name writes them, one byte each; a character beyond one byte becomes "?". */
export function mediaNameBytes(name) {
  return Uint8Array.from(name, c => (c.charCodeAt(0) < 256 ? c.charCodeAt(0) : 0x3f));
}

/** Every picture of a file in the slot layout of frameOfPixels, or null when the file is none of its kind. */
function pictures(bytes, kind) {
  if (!(bytes instanceof Uint8Array)) return null;
  if (kind === 0) {
    const px = decodeBmp(bytes);
    if (typeof px === "string") return null;
    const frame = frameOfPixels(px);
    return [DRAWN_IS_SET ? frame : frame.map(b => b ^ 0xff)];
  }
  let anim;
  try { anim = decodeAnimation(bytes); } catch { return null; }
  // frameOfPixels(frameToPixels(f)) is f with every bit turned: the overlay's bits are lit, not drawn
  return [...anim.progress, ...anim.loop].map(f => (DRAWN_IS_SET ? f.map(b => b ^ 0xff) : f));
}

/**
 * Picture `frame` of a file (its bytes, or undefined when it is gone) into `slots`, one byte to a slot (1024 slots).
 * Kind 0 has one picture; kind 1 has the progress pictures 0 to N - 1, then the loop pictures N to N + M - 1, each
 * as decodeAnimation gives it. -> the number of pictures in the file, 0 when `frame` is past the last (the slots stay),
 * -1 when the file is missing or not one of its kind (any list of a .blla out of bounds makes the whole file bad).
 */
export function readMediaPicture(bytes, kind, frame, slots) {
  const all = pictures(bytes, kind);
  if (!all) return -1;
  if (frame >= all.length) return 0;
  const f = all[frame];
  for (let i = 0; i < f.length; i++) slots[i] = f[i];
  return all.length;
}
