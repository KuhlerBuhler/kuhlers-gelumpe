/**
 * The one place that turns an edit into the messages for the device.
 *
 *   plan(edit, state) -> [step, step, ...]
 *
 * The dry run and the real sender get the same list, which is what makes the
 * dry run worth anything. A step is a message plus what answer it waits for
 * and what that answer is for: a backup of what was there, the write itself,
 * or the read-back that proves it arrived.
 *
 * Pure: no MIDI, no clock, no page. Nothing else in the application builds
 * SysEx (test/plan.test.mjs checks that).
 */
import { u32le } from "./bytes.mjs";
import * as P from "./protocol.mjs";
import { BLOCKS, field, FIELDS, POINTER_TABLES, sitesOf, TABLES, typeOf } from "./map/index.mjs";
import { tableEntry, fileToRam, fieldInRamEntry } from "./map/address.mjs";
import EXEC from "../data/exec.mjs";

/** Conservative RAM chunk size across transports; larger Linux writes are measured separately. */
export const MAX_WRITE = 0x100;

const read = (channel, addr, length, role, extra = {}) =>
  ({ msg: P.readRam(channel, addr, length), expect: { kind: "read", length }, role, target: { addr, length }, ...extra });

/** `max` is the size of one write message: 256 bytes for Hacktribe, up to the device's largest block when BLECH's commands carry them. */
function writes(channel, addr, bytes, max = MAX_WRITE) {
  const steps = [];
  for (let at = 0; at < bytes.length; at += max) {
    const part = bytes.subarray(at, Math.min(at + max, bytes.length));
    steps.push({ msg: P.writeRamAddress(channel, addr + at, part.length), expect: { kind: "ack" }, role: "write", target: { addr: addr + at, length: part.length } });
    steps.push({ msg: P.writeRamData(channel, part), expect: { kind: "ack" }, role: "write", target: { addr: addr + at, length: part.length } });
  }
  return steps;
}

/**
 * A field whose byte is the immediate of an ARM instruction, such as the
 * master menu length (`mov r0, #n`, the word 0xE3A000nn, little endian).
 * The whole word is read and checked before the byte is written, and read
 * back whole afterwards.
 */
const instructionAt = addr =>
  [...FIELDS.values()].find(f => f.instruction && f.where && fileToRam(f.where.offset) === addr);
const wordGuard = (channel, f) => read(channel, fileToRam(f.where.offset), 4, "guard", { guard: f.instruction });
const wordVerify = (channel, f, value) => read(channel, fileToRam(f.where.offset), 4, "verify", {
  compare: Uint8Array.from(u32le((f.instruction.expected & f.instruction.mask) | value)),
});

/**
 * What a sample edit writes: the name field and the tune byte, each at its own address and nothing
 * else of the entry (docs/messungen/2026-10-07-sample-name-ram.md, ...-metadaten-ram.md).
 * The map's types refuse a name the display cannot show and a value that does not fit.
 */
export function sampleWrites({ index, name, tune }) {
  const out = [];
  for (const [fieldId, value] of [["sample.name", name], ["sample.tune", tune]]) {
    if (value === undefined) continue;
    const f = field(fieldId);
    const type = typeOf(f);
    const bytes = new Uint8Array(type.width);
    type.write(bytes, 0, value);
    out.push({ fieldId, addr: fieldInRamEntry(f, index).ram, bytes });
  }
  if (!out.length) throw new RangeError("a sample edit changes the name or the tune");
  return out;
}

const runAt = (channel, addr) =>
  ({ msg: P.execute(channel, addr), expect: { kind: "ack" }, role: "execute", target: { addr, length: 0 } });

const planners = {
  /** Find the device and its channel. */
  search: () => [{ msg: P.search(), expect: { kind: "search" }, role: "query" }],

  /** Read a block of flash, only below P.FLASH_END. */
  flashRead: ({ addr, length }, { channel }) => [{ msg: P.readFlash(channel, addr, length), expect: { kind: "flash", length }, role: "query", target: { addr, length } }],

  /** Read some RAM, for probing Hacktribe or fetching a record. */
  readRam: ({ addr, length }, { channel }) => [read(channel, addr, length, "query")],

  /**
   * Put one effect record into its table slot: back up what is there, write
   * the new record, read it back.
   */
  fxRecord: ({ table, slot, bytes, ram }, { channel, maxWrite }) => {
    // `ram` is where Korg's build keeps this record (found through its pointer arrays, src/presets.mjs); Hacktribe's sit in one table.
    const entry = ram === undefined ? tableEntry(`table.${table}`, slot - 1) : { ram, size: BLOCKS.get("fxRecord").size };
    if (!Number.isInteger(entry.ram)) throw new RangeError("the record's address is not a number");
    if (bytes.length !== entry.size) throw new RangeError(`a record is ${entry.size} bytes, got ${bytes.length}`);
    return [
      read(channel, entry.ram, entry.size, "backup"),
      ...writes(channel, entry.ram, bytes, maxWrite),
      read(channel, entry.ram, entry.size, "verify", { compare: Uint8Array.from(bytes) }),
    ];
  },

  /**
   * A field that lives in several places, such as the insert menu length:
   * every site backed up, every site written, every site read back, in one
   * pass, so a failure can roll all of them back together.
   */
  sites: ({ fieldId, value }, { channel, maxWrite }) => {
    const f = field(fieldId);
    if (!Number.isInteger(value) || (f.range && (value < f.range[0] || value > f.range[1]))) {
      throw new RangeError(`${fieldId}: ${value} is outside ${f.range}`);
    }
    const sites = (f.sites ? sitesOf(f, value) : [{ offset: f.where.offset, value }]).map(s => ({ addr: fileToRam(s.offset), value: s.value }));
    return [
      ...(f.instruction ? [wordGuard(channel, f)] : []),
      ...sites.map(s => read(channel, s.addr, 1, "backup")),
      ...sites.flatMap(s => writes(channel, s.addr, Uint8Array.of(s.value), maxWrite)),
      ...(f.instruction ? [wordVerify(channel, f, value)] : sites.map(s => read(channel, s.addr, 1, "verify", { compare: Uint8Array.of(s.value) }))),
    ];
  },

  immediate: (edit, context) => {
    if (!field(edit.fieldId).instruction) throw new Error(`${edit.fieldId} is no instruction immediate`);
    return planners.sites(edit, context);
  },

  /** A sample's name and/or tune in RAM: every address backed up, written, read back. */
  sample: (edit, { channel, maxWrite }) => {
    const parts = sampleWrites(edit);
    return [
      ...parts.map(p => read(channel, p.addr, p.bytes.length, "backup")),
      ...parts.flatMap(p => writes(channel, p.addr, p.bytes, maxWrite)),
      ...parts.map(p => read(channel, p.addr, p.bytes.length, "verify", { compare: Uint8Array.from(p.bytes) })),
    ];
  },

  /** Put back what a backup step read. Used for undo and for rolling back. */
  restore: ({ backups }, { channel, maxWrite }) => {
    const guarded = backups.map(b => ({ b, f: instructionAt(b.addr) }));
    return [
      ...guarded.filter(g => g.f).map(g => wordGuard(channel, g.f)),
      ...backups.flatMap(b => writes(channel, b.addr, b.bytes, maxWrite)),
      ...guarded.map(({ b, f }) => f && b.bytes.length === 1 ? wordVerify(channel, f, b.bytes[0])
        : read(channel, b.addr, b.bytes.length, "verify", { compare: Uint8Array.from(b.bytes) })),
    ];
  },

  /**
   * Run a small piece of ARM code (tools/device/led_show.py, as steps): the
   * firmware code it relies on is compared with the firmware file first, the
   * bytes under the stub are backed up, the stub is written and read back,
   * the instruction cache is cleared once and the stub runs. The stub must
   * return r0 = 1, or no acknowledgement comes. Putting the original bytes
   * back is the session's job afterwards, because only the run knows them.
   *
   * edit: { code: Uint8Array, at, guards: [{ addr, bytes }], invalidate }
   */
  exec: ({ code, at = EXEC.stubAt, guards = [], invalidate = true }, { channel, maxWrite }) => {
    if (!(code instanceof Uint8Array) || code.length < 4 || code.length % 4) throw new RangeError("code is whole 32-bit words, at least one");
    if (!Number.isInteger(at) || at % 4) throw new RangeError("the stub address is a multiple of four");
    return [
      ...guards.map(g => read(channel, g.addr, g.bytes.length, "guard", { compare: Uint8Array.from(g.bytes) })),
      read(channel, at, code.length, "backup"),
      ...writes(channel, at, code, maxWrite),
      read(channel, at, code.length, "verify", { compare: Uint8Array.from(code) }),
      ...(invalidate ? [runAt(channel, EXEC.icache.addr)] : []),
      runAt(channel, at),
    ];
  },

  patternFetch: (_, { channel }) => [{ msg: P.patternRequest(channel), expect: { kind: "pattern" }, role: "query" }],

  /**
   * Send a pattern into the device's buffer. The buffer is fetched first and
   * kept because a send replaces unsaved edits. The measured 0x23 reply
   * is awaited before requesting the read-back.
   */
  patternSend: ({ block }, { channel }) => [
    { msg: P.patternRequest(channel), expect: { kind: "pattern" }, role: "backup" },
    { msg: P.patternDump(channel, block), expect: { kind: "ack", func: P.PATTERN_ACK, timeout: "pattern" }, role: "write" },
    { msg: P.patternRequest(channel), expect: { kind: "pattern" }, role: "verify", compare: Uint8Array.from(block), ignore: patternVerifyIgnore() },
  ],

  /** Put a kept pattern buffer back, for undo and for rolling back a failed send. */
  patternRestore: ({ block }, { channel }) => [
    { msg: P.patternDump(channel, block), expect: { kind: "ack", func: P.PATTERN_ACK, timeout: "pattern" }, role: "write" },
    { msg: P.patternRequest(channel), expect: { kind: "pattern" }, role: "verify", compare: Uint8Array.from(block), ignore: patternVerifyIgnore() },
  ],

  globalFetch: (_, { channel }) => [{ msg: P.globalRequest(channel), expect: { kind: "global" }, role: "query" }],

  /**
   * A whole picture into the display buffer. It shows at once and stays until
   * the firmware draws its next screen (measure:2026-10-09/menuezustand).
   */
  screenWrite: ({ bytes }, { channel, maxWrite }) => {
    const display = BLOCKS.get("display");
    if (bytes.length !== display.size) throw new RangeError(`a screen is ${display.size} bytes, got ${bytes.length}`);
    return [
      ...writes(channel, display.meta.ram, bytes, maxWrite),
      read(channel, display.meta.ram, display.size, "verify", { compare: Uint8Array.from(bytes) }),
    ];
  },
};

/**
 * Bytes a pattern read-back may legitimately differ in: the device drops
 * glide when a whole pattern is written (measure:2026-09-22/pattern-write-glide).
 */
export function patternVerifyIgnore() {
  const glide = field("part.glide");
  return Array.from({ length: glide.repeat[0].count }, (_, p) => glide.where.offset + p * glide.repeat[0].stride);
}

export function plan(edit, state) {
  const planner = planners[edit.kind];
  if (!planner) throw new Error(`no plan for ${edit.kind}`);
  if (edit.kind !== "search" && !Number.isInteger(state?.channel)) throw new Error("no channel: search for the device first");
  return planner(edit, state || {});
}

/** The record addresses of Korg's own build, as the map lists their runs (data/map/firmware.mjs, `records`). */
export function stockRecordRuns() {
  const stock = POINTER_TABLES.get("presets.ifx").arrays.find(a => a.build === "stock");
  const size = BLOCKS.get("fxRecord").size;
  return stock.records.flatMap(run => Array.from({ length: run.count }, (_, i) => run.ram + i * size));
}

/** The RAM ranges the editor may write: whole records of RAM tables, and the declared sites. `build` leaves out the other build's record tables; without it the list is the union a table fixed in a patch needs. */
export function allowedRegions({ build } = {}) {
  const regions = [];
  for (const t of TABLES.values()) {
    // Only tables whose RAM writes were measured; groove templates are
    // derived from hacktribe-editor and have never been written live.
    if (!t.transport.includes("ram") || t.source !== "measured") continue;
    if (build === "stock" && (t.id === "table.ifx" || t.id === "table.mfx")) continue;
    for (let i = 0; i < t.count; i++) {
      const e = tableEntry(t.id, i);
      regions.push({ start: e.ram, end: e.ram + e.size, what: `${t.id} ${i + 1}` });
    }
  }
  for (const id of ["menu.ifxCount"]) {
    for (const s of field(id).sites) regions.push({ start: fileToRam(s.file), end: fileToRam(s.file) + 1, what: id });
  }
  const mfx = field("menu.mfxCount");
  regions.push({ start: fileToRam(mfx.where.offset), end: fileToRam(mfx.where.offset) + 1, what: mfx.id });
  // Per field, not per record: the notes proved a write of the name and of the tune, nothing else of an entry.
  for (const block of BLOCKS.values()) {
    const t = block.meta.table;
    if (!t) continue;
    for (const f of block.fields) {
      if (f.edit || f.source !== "measured" || !f.transport.includes("ram") || f.repeat) continue;
      for (let i = 0; i < t.count; i++) {
        const { ram } = fieldInRamEntry(f, i);
        regions.push({ start: ram, end: ram + typeOf(f).width, what: `${f.id} ${i + 1}` });
      }
    }
  }
  if (build !== "hacktribe") {
    const size = BLOCKS.get("fxRecord").size;
    stockRecordRuns().forEach((start, i) => regions.push({ start, end: start + size, what: `preset.stock ${i + 1}` }));
  }
  const display = BLOCKS.get("display");
  regions.push({ start: display.meta.ram, end: display.meta.ram + display.size, what: "display" });
  regions.push({ start: EXEC.stubAt, end: EXEC.stubAt + EXEC.stubSize, what: "stub buffer" });
  return regions;
}

/**
 * Where the device may be told to run code: inside the stub buffer, where
 * the editor put it, and the one firmware routine that clears the
 * instruction cache. Nothing else, whatever a script asks for.
 */
export function allowedExecutes() {
  return [
    { start: EXEC.stubAt, end: EXEC.stubAt + EXEC.stubSize, what: "stub buffer", stub: true },
    { start: EXEC.icache.addr, end: EXEC.icache.addr + 4, what: "instruction cache invalidation", stub: false },
  ];
}
