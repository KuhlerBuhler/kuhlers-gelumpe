/**
 * Where a block sits on each way to the device, one function per way.
 *
 * The map says where a field sits inside its block. Whether that block is
 * pattern 17 in a backup file, the pattern buffer behind SysEx 0x40, or
 * record 51 of the master table in RAM, is decided here and nowhere else.
 */
import { TABLES, BLOCKS, offsetOf } from "./index.mjs";

export const RAM_BASE = 0xc0000000;
export const ramToFile = a => a - RAM_BASE + 0x100;
export const fileToRam = f => f - 0x100 + RAM_BASE;

/** measure:2026-09-16/pattern-diff */
export const PATTERN_FILE = { header: 0x10100, count: 250, magic: "KORG", device: "e2sampler" };
export const SINGLE_PATTERN_FILE = { header: 0x100 };

/** Byte offset of pattern n (0-based) in a .e2sallpat. */
export function patternInBackup(n) {
  if (!Number.isInteger(n) || n < 0 || n >= PATTERN_FILE.count) throw new RangeError(`pattern ${n + 1} does not exist`);
  return PATTERN_FILE.header + n * BLOCKS.get("pattern").size;
}

/** Where entry `index` (0-based) of a firmware table sits, in the file and in RAM. */
export function tableEntry(tableId, index) {
  const t = TABLES.get(tableId);
  if (!t) throw new Error(`no table ${tableId}`);
  if (!Number.isInteger(index) || index < 0 || index >= t.count) throw new RangeError(`${tableId} has no entry ${index}`);
  const file = t.file + index * t.stride;
  return { file, ram: fileToRam(file), size: t.length ?? BLOCKS.get(t.block).size };
}

/** A field of a table entry, as a file offset and a RAM address. */
export function fieldInTable(tableId, index, f, indices = []) {
  const entry = tableEntry(tableId, index);
  if (f.block !== TABLES.get(tableId).block) throw new Error(`${f.id} is not part of ${tableId}`);
  const at = offsetOf(f, indices);
  if (at >= entry.size) throw new RangeError(`${f.id} lies beyond the ${entry.size} bytes ${tableId} keeps per entry`);
  return { file: entry.file + at, ram: entry.ram + at };
}

/** Entry `index` (zero-based, the display shows index + 1) of a block that is one entry of a RAM table, such as the sample tables. */
export function ramEntry(blockName, index) {
  const block = BLOCKS.get(blockName);
  const t = block?.meta.table;
  if (!t) throw new Error(`${blockName} is not an entry of a RAM table`);
  if (!Number.isInteger(index) || index < 0 || index >= t.count) throw new RangeError(`${blockName} has no entry ${index}`);
  return { ram: t.ram + index * t.stride, size: block.size };
}

/** RAM address of a field of such an entry. */
export function fieldInRamEntry(f, index, indices = []) {
  return { ram: ramEntry(f.block, index).ram + offsetOf(f, indices) };
}

/** The pattern being edited: a pointer to it, then a 4-byte header (measure:2026-10-09/menuezustand). */
export const CURRENT_PATTERN = { at: 0xc033e6a4, header: 4 };

/**
 * RAM address of a block reached through pointers (`meta.pointer`), with
 * `readU32(addr)` reading one word from the device.
 */
export async function pointerBlock(blockName, readU32) {
  const p = BLOCKS.get(blockName)?.meta.pointer;
  if (!p) throw new Error(`${blockName} is not reached through a pointer`);
  let addr = await readU32(p.at);
  for (const off of p.then) addr = await readU32(addr + off);
  if (addr < RAM_BASE || addr >= RAM_BASE + 0x8000000) throw new RangeError(`${blockName}: pointer 0x${addr.toString(16)} is outside RAM`);
  return addr;
}

/** A field that lives directly in the firmware image. */
export function firmwareField(f, indices = []) {
  if (f.block !== "firmware") throw new Error(`${f.id} is not a firmware field`);
  const file = offsetOf(f, indices);
  return { file, ram: fileToRam(file) };
}
