/**
 * The protection table of BLECH's own SysEx commands (docs/messungen/2026-10-15-blech-sysex.md), as the bytes the
 * firmware patch carries. It is cut from data/protected.mjs and the editor's declared regions (src/plan.mjs) here
 * and nowhere else: the builder (tools/patch/blech_sysex.mjs) writes these bytes into the patch, the tests read the
 * firmware's answer against them, and the editor compares the table CRC the device reports.
 *
 * Layout, 32-bit little endian words:
 *   word 0       number of regions R
 *   word 1       number of windows W
 *   R regions    start, end, flags              flags: bits 0 to 7 the class of exception windows that may lie
 *                                               inside it (0 for none), bit 8 set when the region is refused for reads too
 *   W windows    start, width, stride, count, class
 *                count windows of `width` bytes, `stride` apart; a class bit of a region lets a write that lies
 *                wholly inside one window pass that region (the `except` list of data/protected.mjs)
 *
 * Only RAM regions go in: the commands touch RAM and nothing else, and there is no flash command at all. The same
 * rule as src/protect.mjs: the RAM window first, every region a write touches (a read only those with deny "any"),
 * and for a write the mirror of the range in the other half of the window, where no exception counts.
 */
import PROTECTED from "../data/protected.mjs";
import { allowedRegions } from "./plan.mjs";
import { crc32 } from "./script/blob.mjs";

/** An exception names a declared region by `what` up to the first space, as in src/protect.mjs. */
const covers = (what, prefixes) => prefixes.some(p => what === p || what.startsWith(`${p} `));

/** Declared regions as strided runs: neighbours of one width that lie one stride apart become one window. */
function runsOf(list) {
  const sorted = [...list].sort((a, b) => a.start - b.start);
  const runs = [];
  for (const r of sorted) {
    const width = r.end - r.start;
    const last = runs.at(-1);
    if (last && last.width === width && last.count === 1 && r.start - last.start >= width) {
      last.stride = r.start - last.start;
      last.count = 2;
    } else if (last && last.width === width && last.count > 1 && r.start === last.start + last.count * last.stride) {
      last.count++;
    } else {
      runs.push({ start: r.start, width, stride: width, count: 1 });
    }
  }
  return runs;
}

/**
 * @param {object} [o]
 * @param {object} [o.protectedData] data/protected.mjs
 * @param {"hacktribe"|"stock"} [o.build] the build the table is for: the records it keeps its presets in differ (src/plan.mjs)
 * @param {{start: number, end: number, what: string}[]} [o.declared] the regions the editor writes
 * @returns {{bytes: Uint8Array, crc: number, regions: object[], windows: object[]}}
 */
export function protectTable({ protectedData = PROTECTED, build, declared = build === "synth" ? [] : allowedRegions({ build }) } = {}) {
  // The synth's RAM map (heap, stacks, patterns) is not measured, so for its firmware the whole window is one region
  // with no exception: every write is refused, reading works. Flash reading has its own range check in the firmware.
  if (build === "synth") {
    const words = [1, 0, 0xc0000000, 0xc8000000, 0];
    const bytes = new Uint8Array(words.length * 4);
    const view = new DataView(bytes.buffer);
    words.forEach((w, i) => view.setUint32(i * 4, w >>> 0, true));
    return { bytes, crc: crc32(bytes), regions: [{ start: 0xc0000000, end: 0xc8000000, flags: 0, id: "synth-ram" }], windows: [] };
  }
  const regions = protectedData.regions.filter(r => r.space === "ram");
  const classes = new Map();
  for (const r of regions) if (r.except?.length) classes.set(r.id, 1 << classes.size);
  if (classes.size > 8) throw new RangeError("at most eight regions can name exceptions");
  const windows = [];
  for (const r of regions) {
    const bit = classes.get(r.id);
    if (!bit) continue;
    // Korg's records lie on a grid of their own, so they are merged apart from Hacktribe's tables, or the runs fall apart.
    const mine = declared.filter(d => covers(d.what, r.except));
    for (const group of [mine.filter(d => !d.what.startsWith("preset.stock ")), mine.filter(d => d.what.startsWith("preset.stock "))]) {
      for (const run of runsOf(group)) windows.push({ ...run, cls: bit });
    }
  }
  const table = [
    ...regions.map(r => ({ start: r.start, end: r.end, flags: (classes.get(r.id) ?? 0) | (r.deny === "any" ? 0x100 : 0), id: r.id })),
  ];
  const words = [table.length, windows.length];
  for (const r of table) words.push(r.start, r.end, r.flags);
  for (const w of windows) words.push(w.start, w.width, w.stride, w.count, w.cls);
  const bytes = new Uint8Array(words.length * 4);
  const view = new DataView(bytes.buffer);
  words.forEach((w, i) => view.setUint32(i * 4, w >>> 0, true));
  return { bytes, crc: crc32(bytes), regions: table, windows };
}
