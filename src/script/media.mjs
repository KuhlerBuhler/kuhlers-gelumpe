/**
 * Pictures from the card for the plugin calls korg.file.count, korg.file.name and korg.file.picture: start images (.bmp, kind 0)
 * and loading animations (.blla, kind 1) in KORG/blechtribe/Media/. This is the reference the simulator, the firmware and the
 * app are held against.
 */
import { SCRIPT_MEDIA } from "../../data/script/contract.mjs";
import { decodeBmp } from "../splash-bmp.mjs";
import { decodeAnimation } from "../loading-anim.mjs";
import { frameOfPixels } from "./gif.mjs";

/** The file endings of each kind, in lower case: 0 images, 1 animations. */
export const MEDIA_KINDS = SCRIPT_MEDIA.endings;
/** The one folder that is searched, no other. */
export const MEDIA_FOLDER = SCRIPT_MEDIA.folder;
/** At most this many files of a kind are listed, the rest is left out. */
export const MEDIA_MAX_FILES = SCRIPT_MEDIA.maxFiles;
/** The longest name korg.file.name gives; a longer one is cut to MEDIA_NAME_MAX - 2 characters and "..". */
export const MEDIA_NAME_MAX = SCRIPT_MEDIA.nameMax;
/** Longest file name the folder walk takes, as the BLECH menu's list (tools/patch/script_menu.s, menu_dir_next). */
const FILE_NAME_MAX = 31;

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

/**
 * The characters of a name as korg.file.name writes them, one byte each; a character beyond ASCII becomes "?". The firmware's
 * FatFs gives a long name in code page 932 (its Shift JIS tables are in the image), so the device turns every byte from 0x80 on
 * into "?": a name with such characters can differ in length there (two bytes a character, or the short name instead).
 */
export function mediaNameBytes(name) {
  return Uint8Array.from(name, c => (c.charCodeAt(0) < 0x80 ? c.charCodeAt(0) : 0x3f));
}

/**
 * Every picture of a file in the slot layout of frameOfPixels, or null when the file is none of its kind. A drawn pixel sets its
 * bit, as frameOfPixels does: drawn is the darker palette entry of a .bmp, and for a .blla what frameToPixels
 * (src/loading-anim.mjs) calls drawn, the complement of the bits the loading overlay writes (frameOfPixels(frameToPixels(f)) is
 * f with every bit turned).
 */
function pictures(bytes, kind) {
  if (!(bytes instanceof Uint8Array)) return null;
  if (kind === 0) {
    const px = decodeBmp(bytes);
    return typeof px === "string" ? null : [frameOfPixels(px)];
  }
  let anim;
  try { anim = decodeAnimation(bytes); } catch { return null; }
  return [...anim.progress, ...anim.loop].map(f => f.map(b => b ^ 0xff));
}

/**
 * Picture `frame` of a file (its bytes, or undefined when it is gone) into `slots`, one byte to a slot (1024 slots).
 * Kind 0 has one picture; kind 1 has the progress pictures 0 to N - 1, then the loop pictures N to N + M - 1, each
 * as decodeAnimation gives it. -> the number of pictures in the file, 0 when `frame` is past the last (the slots stay),
 * -1 when the file is missing or not one of its kind (any list of a .blla out of bounds makes the whole file bad).
 * `reversed` is the display as DISPLAY INVERT ON leaves it (controller command 0xA7): every bit is turned, so a drawn pixel is
 * dark either way, as the start image at power-on (drawn before the 0xA7) and the loading animation (which turns its own bits
 * with DISPLAY INVERT OFF) show it. Measured in the emulator, docs/messungen/2026-11-16-media-polaritaet.md.
 */
export function readMediaPicture(bytes, kind, frame, slots, reversed = false) {
  const all = pictures(bytes, kind);
  if (!all) return -1;
  if (frame >= all.length) return 0;
  const f = all[frame], turn = reversed ? 0xff : 0;
  for (let i = 0; i < f.length; i++) slots[i] = f[i] ^ turn;
  return all.length;
}
