/**
 * A custom loading animation for the firmware (docs/hintergrund/ladeanimation.md): the first picture whole, every further one as
 * the bytes that change. Pictures are frame buffers as the loading overlay draws them (tools/patch/load_bar.py):
 * 8 pages of 128 bytes, bit 0 the top row of a page, a set bit lit on the reversed display (DISPLAY INVERT ON).
 *
 * Layout, little endian:
 *   0     "BLLA"
 *   4     u8 version (1), u8 loop from percent (0: the loop plays while the progress stands)
 *   6     u16 N, progress pictures (at least 1, picture 0 included)
 *   8     u16 M, loop pictures
 *   10    u16 offset of the list table
 *   12    u32 size of the file
 *   16    picture 0, 1024 bytes
 *   table N - 1 + M u16 offsets of the lists: progress 1 to N - 1, then loop 0 to M - 1
 *   list  u16 run count, then runs: u16 head (bits 0-9 offset, bits 10-15 length - 1), length bytes
 *
 * Progress picture k is picture k - 1 with list k written over it. Loop picture j is the progress picture on screen
 * with loop list j written over it; loop lists are taken against one picture (0, or the one of the loop's percent
 * when it plays from a percent on) and never chain, so the loop needs no buffer of its own and leaves the progress
 * picture untouched.
 */
import { pixelsToSplash, splashToPixels, toHex, PATCH_FORMAT, SPLASH_W, SPLASH_H } from "./patch.mjs";

export const MAGIC = "BLLA";
export const VERSION = 1;
export const MAX_BYTES = 16384;
export const FRAME_BYTES = 1024;
export const HEADER_BYTES = 16;
const RUN_MAX = 64;

function diffRuns(prev, next) {
  const runs = [];
  let i = 0;
  while (i < FRAME_BYTES) {
    if (prev[i] === next[i]) { i++; continue; }
    let end = i + 1;
    // A single equal byte between two changes costs 1 inside the run, a new run costs 2.
    while (end < FRAME_BYTES && end - i < RUN_MAX) {
      if (prev[end] !== next[end]) end++;
      else if (end + 1 < FRAME_BYTES && end + 1 - i < RUN_MAX && prev[end + 1] !== next[end + 1]) end += 2;
      else break;
    }
    runs.push([i, next.subarray(i, end)]);
    i = end;
  }
  return runs;
}

function listBytes(runs) {
  const out = new Uint8Array(2 + runs.reduce((n, [, data]) => n + 2 + data.length, 0));
  out[0] = runs.length & 0xff; out[1] = runs.length >> 8;
  let p = 2;
  for (const [at, data] of runs) {
    const head = at | (data.length - 1) << 10;
    out[p++] = head & 0xff; out[p++] = head >> 8;
    out.set(data, p); p += data.length;
  }
  return out;
}

function checkFrame(f, what) {
  if (!(f instanceof Uint8Array) || f.length !== FRAME_BYTES) throw new RangeError(`${what}: a picture has ${FRAME_BYTES} bytes`);
}

/** The progress picture the firmware shows at `permille` (0 to 1000; 1000 only when the loader is done). */
export function progressIndex(n, permille) {
  return Math.floor(permille * (n - 1) / 1000);
}

/** The progress picture the loop lists are taken against. */
function loopBase(n, loopFrom) {
  return progressIndex(n, 10 * loopFrom);
}

/** The change lists, in file order: progress 1 to N - 1 against the previous picture, loop against its base. */
function lists({ progress, loop = [], loopFrom = 0 }) {
  if (!progress?.length) throw new RangeError("at least one progress picture");
  if (!Number.isInteger(loopFrom) || loopFrom < 0 || loopFrom > 100) throw new RangeError("loop from 0 to 100 percent");
  progress.forEach((f, i) => checkFrame(f, `progress ${i}`));
  loop.forEach((f, i) => checkFrame(f, `loop ${i}`));
  const base = progress[loopBase(progress.length, loopFrom)];
  return [
    ...progress.slice(1).map((f, i) => listBytes(diffRuns(progress[i], f))),
    ...loop.map(f => listBytes(diffRuns(base, f))),
  ];
}

export function encodeAnimation(frames) {
  const parts = lists(frames);
  const n = frames.progress.length, m = frames.loop?.length ?? 0;
  const table = HEADER_BYTES + FRAME_BYTES;
  const size = table + 2 * parts.length + parts.reduce((s, l) => s + l.length, 0);
  if (size > 0xffff) throw new RangeError(`${size} bytes, the list offsets only reach 65535`);
  const bytes = new Uint8Array(size);
  const v = new DataView(bytes.buffer);
  bytes.set([...MAGIC].map(c => c.charCodeAt(0)), 0);
  bytes[4] = VERSION;
  bytes[5] = frames.loopFrom ?? 0;
  v.setUint16(6, n, true);
  v.setUint16(8, m, true);
  v.setUint16(10, table, true);
  v.setUint32(12, size, true);
  bytes.set(frames.progress[0], HEADER_BYTES);
  let at = table + 2 * parts.length;
  parts.forEach((l, i) => { v.setUint16(table + 2 * i, at, true); bytes.set(l, at); at += l.length; });
  return { bytes, size };
}

/** The checks the firmware makes before the first picture. Returns null when the file is good, else the reason. */
export function validateAnimation(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < HEADER_BYTES) return "shorter than the header";
  if (String.fromCharCode(...bytes.subarray(0, 4)) !== MAGIC) return "wrong magic";
  if (bytes[4] !== VERSION) return `version ${bytes[4]}`;
  if (bytes[5] > 100) return `loop from ${bytes[5]} percent`;
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const n = v.getUint16(6, true), m = v.getUint16(8, true), table = v.getUint16(10, true), size = v.getUint32(12, true);
  if (size > MAX_BYTES) return `${size} bytes, more than ${MAX_BYTES}`;
  if (size > bytes.length) return "the file is shorter than its size";
  if (n < 1) return "no progress picture";
  const count = n - 1 + m;
  if (table < HEADER_BYTES + FRAME_BYTES || table + 2 * count > size) return "list table outside the file";
  for (let i = 0; i < count; i++) {
    let p = v.getUint16(table + 2 * i, true);
    if (p + 2 > size) return `list ${i} outside the file`;
    let runs = v.getUint16(p, true);
    p += 2;
    while (runs--) {
      if (p + 2 > size) return `list ${i} outside the file`;
      const head = v.getUint16(p, true), at = head & 0x3ff, len = (head >> 10) + 1;
      if (at + len > FRAME_BYTES) return `list ${i} writes past byte 1023`;
      p += 2 + len;
      if (p > size) return `list ${i} outside the file`;
    }
  }
  return null;
}

function apply(frame, bytes, at) {
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let runs = v.getUint16(at, true), p = at + 2;
  while (runs--) {
    const head = v.getUint16(p, true), len = (head >> 10) + 1;
    frame.set(bytes.subarray(p + 2, p + 2 + len), head & 0x3ff);
    p += 2 + len;
  }
  return frame;
}

/** The pictures of a file, as the firmware shows them (the reference for the tests). */
export function decodeAnimation(bytes) {
  const bad = validateAnimation(bytes);
  if (bad) throw new Error(`no loading animation: ${bad}`);
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const n = v.getUint16(6, true), m = v.getUint16(8, true), table = v.getUint16(10, true);
  const list = i => v.getUint16(table + 2 * i, true);
  const progress = [bytes.slice(HEADER_BYTES, HEADER_BYTES + FRAME_BYTES)];
  for (let k = 1; k < n; k++) progress.push(apply(progress[k - 1].slice(), bytes, list(k - 1)));
  const loopFrom = bytes[5], base = progress[loopBase(n, loopFrom)];
  const loop = [];
  for (let j = 0; j < m; j++) loop.push(apply(base.slice(), bytes, list(n - 1 + j)));
  return { progress, loop, loopFrom };
}

/**
 * What the overlay draws (before the complement): progress picture `index` with loop list `loop` written over it, or the
 * progress picture alone without one (tools/patch/loading_anim.py:picture, load_bar.py draw).
 */
export function shownPicture(bytes, index, loop = null) {
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const n = v.getUint16(6, true), table = v.getUint16(10, true);
  const list = i => v.getUint16(table + 2 * i, true);
  const frame = bytes.slice(HEADER_BYTES, HEADER_BYTES + FRAME_BYTES);
  for (let k = 1; k <= index; k++) apply(frame, bytes, list(k - 1));
  return loop === null ? frame : apply(frame, bytes, list(n - 1 + loop));
}

/**
 * The same from the pictures, without a file: loop picture `loop`, as the encoder lists it against `base`, written over
 * the progress picture `shown`. The runs also write the bytes they bridge, so those come from the base, as on the device.
 */
export function loopPicture(shown, base, loop) {
  return apply(shown.slice(), listBytes(diffRuns(base, loop)), 0);
}

/** Every second progress picture dropped (0, 2, 4 ... stay, the last one always), the loop kept. */
export function thinAnimation({ progress, loop = [], loopFrom = 0 }) {
  return { progress: progress.filter((_, i) => i % 2 === 0 || i === progress.length - 1), loop, loopFrom };
}

/** What each picture adds to the file in bytes, in file order, so the app can name the most expensive ones. */
export function costPerFrame(frames) {
  const parts = lists(frames);
  const n = frames.progress.length;
  return [
    { kind: "progress", index: 0, bytes: FRAME_BYTES },
    ...parts.map((l, i) => i < n - 1
      ? { kind: "progress", index: i + 1, bytes: 2 + l.length }
      : { kind: "loop", index: i - (n - 1), bytes: 2 + l.length }),
  ];
}

const reverse = b => {
  let r = 0;
  for (let i = 0; i < 8; i++) r |= (b >> i & 1) << (7 - i);
  return r;
};

/**
 * Pixels in the start image's form (row by row, 128 x 64, 1 drawn = dark, as toMono gives them) to a picture: the
 * same pages with the bits the other way round (bit 0 on top), and lit where nothing is drawn, as the reversed
 * display needs it.
 */
export function pixelsToFrame(px) {
  return pixelsToSplash(px).map(b => reverse(b) ^ 0xff);
}

export function frameToPixels(frame) {
  checkFrame(frame, "picture");
  return splashToPixels(frame.map(b => reverse(b ^ 0xff)));
}

export { SPLASH_W, SPLASH_H };

/**
 * The app edits an animation as 100 slots, slot n for n percent: the firmware shows progress picture
 * progressIndex(100, permille), so with 100 progress pictures slot n is on screen from about n percent on.
 * An empty slot keeps the picture before it (its list is empty, 2 bytes); an empty slot 0 is a blank display.
 */
export const SLOTS = 100;
const LOOP_DEFAULT = 95;

/**
 * Which of `k` imported pictures slot `slot` takes, or -1 for an empty slot.
 *   stretch: the pictures spread evenly over the slots, the first at slot 0; with more than 100 every slot takes the
 *            picture at its share of the run, so some are left out.
 *   repeat:  slot n takes picture n % k, the run repeats from 0 to 100 percent (more than 100 pictures: stretch).
 */
export function slotSource(slot, k, mode = "stretch") {
  if (k <= 0) return -1;
  if (k > SLOTS) return Math.floor(slot * k / SLOTS);
  if (mode === "repeat") return slot % k;
  const j = Math.ceil(slot * k / SLOTS);
  return j < k && Math.floor(j * SLOTS / k) === slot ? j : -1;
}

/**
 * The 100 slots (a picture or null each) to the frames the encoder takes. `loopFrom` 1 to 99 makes the filled slots
 * from there on the loop pictures, which play over the progress while it stands from that percent on; the progress
 * holds the picture before. `invert` turns every picture, the blank one too; the slots stay as they are.
 */
export function slotsToAnimation(slots, { loopFrom = 0, invert = false } = {}) {
  const turn = f => (invert ? f.map(b => b ^ 0xff) : f);
  const cut = loopFrom > 0 && loopFrom < SLOTS ? loopFrom : SLOTS;
  const loop = slots.slice(cut, SLOTS).filter(Boolean).map(turn);
  const progress = [];
  let shown = turn(new Uint8Array(FRAME_BYTES).fill(0xff));
  for (let s = 0; s < SLOTS; s++) {
    if (s < cut && slots[s]) shown = turn(slots[s]);
    progress.push(shown);
  }
  return { progress, loop, loopFrom: loop.length ? cut : 0 };
}

const same = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

/**
 * A file's frames back to slots: a picture where it changes, null where it repeats the one before (or is blank at
 * slot 0). Other progress counts than 100 (older files) spread over the slots; a loop on a stall (0) gets 95 percent.
 */
export function animationToSlots({ progress, loop = [], loopFrom = 0 }) {
  const n = progress.length;
  const slots = Array(SLOTS).fill(null);
  const from = loop.length ? Math.min(SLOTS - 1, loopFrom || LOOP_DEFAULT) : 0;
  const blank = new Uint8Array(FRAME_BYTES).fill(0xff);
  let prev = blank;
  for (let s = 0; s < (from || SLOTS); s++) {
    const j = n === SLOTS ? s : slotSource(s, n, "stretch");
    if (j < 0) continue;
    if (!same(progress[j], prev)) slots[s] = progress[j].slice();
    prev = progress[j];
  }
  loop.slice(0, SLOTS - from).forEach((f, j) => { slots[from + j] = f.slice(); });
  return { slots, loopFrom: from };
}

export const LOADING_ANIM_ID = "loading-anim";

/**
 * A custom animation as a patch, the way the start image is one (splashPatch): the map field `loadingAnim` is the slot
 * load-bar reads (tools/patch/load_bar.py:ANIM_SLOT), the file at its start, FF behind it. Made for load-bar's builds;
 * only worth applying on top of load-bar (src/patcher.mjs, withLoadingAnim). Throws on a file the firmware would reject.
 */
export function loadingAnimPatch(bytes, name = "Eigene Ladeanimation") {
  const bad = validateAnimation(bytes);
  if (bad) throw new Error(`loading animation: ${bad}`);
  const slot = new Uint8Array(MAX_BYTES).fill(0xff);
  slot.set(bytes.subarray(0, new DataView(bytes.buffer, bytes.byteOffset).getUint32(12, true)));
  return {
    format: PATCH_FORMAT, version: 1, id: LOADING_ANIM_ID, name, builds: ["hacktribe", "stock"],
    changes: [{ field: "loadingAnim", bytes: toHex(slot) }],
  };
}
