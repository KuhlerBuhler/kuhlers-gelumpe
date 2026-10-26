/**
 * Test fixtures built from nothing.
 *
 * No firmware is shipped with this project, so the tests construct their own
 * records and images. That is fine here: these tests check the code's own
 * arithmetic, not what the hardware does with it.
 */
import { RECORD_SIZE, REC, TABLE, ramToFile } from "../src/layout.mjs";
import { FxRecord } from "../src/record.mjs";
import { VsbImage } from "../src/image.mjs";
import { writeName } from "../src/bytes.mjs";
import { readUnits } from "../src/node.mjs";

readUnits();

export const IMAGE_SIZE = 0x200000;

/** A record with recognisable filler everywhere we do not understand. */
export function makeRecord(kind, { name = "Test", devices = {}, params = {} } = {}) {
  const bytes = new Uint8Array(RECORD_SIZE);
  for (let i = 0; i < RECORD_SIZE; i++) bytes[i] = 0xa5;
  bytes.fill(0, REC.map, REC.map + REC.mapEntries * REC.mapEntrySize);
  writeName(bytes, REC.name, name, REC.nameWidth);
  const record = new FxRecord(bytes, kind);
  for (const [stage, id] of Object.entries(devices)) record.setDevice(stage, id);
  for (const stage of record.stageNames) {
    if (!(stage in devices)) record.setDevice(stage, 0);
  }
  // Korg leaves the insert fields of a master preset at zero (src/rules.mjs, master-extra-stage).
  if (kind === "mfx") for (const stage of ["ifx1", "ifx2"]) if (!(stage in devices)) record.setDevice(stage, 0);
  for (const [stage, values] of Object.entries(params)) {
    values.forEach((v, i) => record.setParamAt(stage, i, v));
  }
  return record;
}

export function makeImage(presets = []) {
  const image = new VsbImage(new Uint8Array(IMAGE_SIZE));
  for (const { kind, slot, record } of presets) image.write(kind, slot, record);
  return image;
}

export const slotRam = (kind, slot) => TABLE[kind].ram + (slot - 1) * RECORD_SIZE;

const PATTERN_HEADER = 0x10100;
const BLOCK = 0x4000;
const putAscii = (bytes, at, text) => [...text].forEach((c, i) => { bytes[at + i] = c.charCodeAt(0); });

/**
 * One pattern block: the frame and a few known fields set, filler 0xA5
 * everywhere else so a byte that should not change stands out.
 */
export function makePattern({ name = "Test", tempo = 1200 } = {}) {
  const b = new Uint8Array(BLOCK).fill(0xa5);
  putAscii(b, 0, "PTST");
  b.set([0x00, 0x40, 0x00, 0x00], 4);
  b.fill(0, 16, 34);
  putAscii(b, 16, name);
  b[34] = tempo & 0xff;
  b[35] = tempo >> 8;
  putAscii(b, 15356, "PTED");
  return b;
}

/** A backup file: header with KORG / e2sampler, then `count` framed patterns. */
export function makePatternFile(count = 250) {
  const out = new Uint8Array(PATTERN_HEADER + count * BLOCK).fill(0x5a, 0, PATTERN_HEADER);
  out.fill(0, 0, 0x20);
  putAscii(out, 0, "KORG");
  putAscii(out, 0x10, "e2sampler");
  for (let n = 0; n < count; n++) out.set(makePattern({ name: `P${n + 1}` }), PATTERN_HEADER + n * BLOCK);
  return out;
}

/**
 * A firmware image the editor recognises as the measured layout: the right
 * size, the markers it looks for at their places, agreeing menu lengths,
 * and a few presets of our own. None of it is Korg's: markers are four
 * letters and a name, records are built from filler.
 */
export async function makeFirmware(presets = []) {
  const { TABLES, field, writeRaw } = await import("../src/map/index.mjs");
  const bytes = new Uint8Array(0x200100);
  putAsciiAt(bytes, TABLES.get("table.initPattern").file, "PTST");
  const groove = TABLES.get("table.groove").file;
  putAsciiAt(bytes, groove, "GVST");
  putAsciiAt(bytes, groove + 0x13c, "GVED");
  putModTable(bytes, TABLES.get("table.modType").file);
  writeRaw(bytes, field("menu.ifxCount"), [], 52);
  const mfx = field("menu.mfxCount");
  new DataView(bytes.buffer).setUint32(mfx.where.offset, mfx.instruction.expected, true);
  writeRaw(bytes, mfx, [], 33);
  const image = new VsbImage(bytes);
  for (const { kind, slot, record } of presets) image.write(kind, slot, record);
  return image.bytes;
}

/**
 * makeFirmware with the getters and the pointer arrays of the real firmware (src/presets.mjs), laid out the way Hacktribe
 * does it: arrays in front of the two tables. `patched` gives arrays of 128 entries and clamps of 127, the extra entries
 * pointing at the first record, as the BLECH patch preset-tables leaves them.
 */
export async function makeFirmwareWithArrays(presets = [], { patched = false } = {}) {
  const { POINTER_TABLES } = await import("../src/map/index.mjs");
  const bytes = await makeFirmware(presets);
  const view = new DataView(bytes.buffer);
  const file = ram => ram - 0xc0000000 + 0x100;
  for (const [kind, array] of [["ifx", 0xc01b0000], ["mfx", 0xc01b0400]]) {
    const g = POINTER_TABLES.get(`presets.${kind}`).getter;
    view.setUint32(file(g.literal), array, true);
    view.setUint32(file(g.clamp), 0x23a00000 | (patched ? 127 : 99), true);
    for (let i = 0; i < (patched ? 128 : 100); i++) view.setUint32(file(array + 4 * i), TABLE[kind].ram + (i < 100 ? i : 0) * RECORD_SIZE, true);
  }
  view.setUint32(0x98184, 0xe3a02000 | 52, true);
  return bytes;
}

/**
 * makeFirmware with the getters and pointer arrays of Korg's own build: the 200 records in the three runs the map lists
 * (data/map/firmware.mjs, `records`), insert slot i at run entry 2i, master slot i at 2i + 1, so no two slots are neighbours.
 * Not Korg's bytes: the records are ours, the rest of the image is makeFirmware's.
 */
export async function makeStockLikeFirmware(presets = []) {
  const { POINTER_TABLES } = await import("../src/map/index.mjs");
  const { stockRecordRuns } = await import("../src/plan.mjs");
  const bytes = await makeFirmware();
  const view = new DataView(bytes.buffer);
  const file = ram => ram - 0xc0000000 + 0x100;
  const runs = stockRecordRuns();
  for (const [n, kind] of [[0, "ifx"], [1, "mfx"]]) {
    const t = POINTER_TABLES.get(`presets.${kind}`);
    const array = t.arrays.find(a => a.build === "stock").ram;
    view.setUint32(file(t.getter.literal), array, true);
    view.setUint32(file(t.getter.clamp), 0x23a00000 | 99, true);
    for (let i = 0; i < 100; i++) view.setUint32(file(array + 4 * i), runs[2 * i + n], true);
  }
  view.setUint32(0x98184, 0xe3a02000 | 52, true);
  const image = new VsbImage(bytes);
  for (const { kind, slot, record } of presets) image.write(kind, slot, record);
  return image.bytes;
}

/**
 * A modulation table of our own at `file`: 72 entries named "Type 2" and on (the first "EG+ Filter"), targets
 * 3 1 2 4 0 5 around, and the two code words that point at its names, where the firmware keeps them. Not Korg's bytes.
 */
export function putModTable(bytes, file, { readers = [0x98e3c, 0x99598] } = {}) {
  for (let i = 0; i < 72; i++) {
    const e = file + i * 0x58;
    putAsciiAt(bytes, e + 4, i === 0 ? "EG+ Filter" : `Type ${i + 1}`);
    bytes[e + 25] = [3, 1, 2, 4, 0, 5][i % 6];
    bytes[e + 26] = 20 + i;
    bytes[e + 27] = 100 - i;
    bytes[e + 28] = 2;
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset);
  for (const at of readers) view.setUint32(at, file - 0x100 + 0xc0000000 + 4, true);
}

function putAsciiAt(bytes, at, text) { [...text].forEach((c, i) => { bytes[at + i] = c.charCodeAt(0); }); }

/**
 * A port pair talking to a SimDevice, shaped like the emulator's or a
 * device's Web MIDI ports, with a log of every frame sent to it. `execute`
 * stands in for running code; `tamper(reply, message)` may change a reply.
 */
export async function simPort({ bytes, channel = 9, name = "electribe2 sampler", emulator = false, execute = null, tamper = null, version, hacktribe = true, blech = false, card = null } = {}) {
  const { SimDevice } = await import("../src/device.mjs");
  const sim = new SimDevice({ image: new VsbImage(Uint8Array.from(bytes)), channel, version, hacktribe, blech, card, execute: execute ? addr => execute(addr, sim, port) : null });
  const sent = [];
  const port = {
    name, running: true, generation: 0,
    in: { onmidimessage: null },
    out: {
      send: data => {
        sent.push(Array.from(data));
        queueMicrotask(() => {
          let reply = sim.handle(Array.from(data));
          if (reply && tamper) reply = tamper(reply, Array.from(data)) ?? reply;
          if (reply) port.in.onmidimessage?.({ data: Uint8Array.from(reply) });
        });
      },
    },
  };
  if (emulator) port.emulator = true;
  return { port, sim, sent };
}

/** Korg's own build leaves the run Hacktribe puts its code in erased (0xFF); the stand-in image has it zeroed. */
export function asStock(bytes) {
  const out = Uint8Array.from(bytes);
  out.fill(0xff, 0x170100, 0x170140);
  return out;
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

/**
 * The image with a run at 0x170100 that src/firmware.mjs takes for Hacktribe's code: not Hacktribe's bytes, 60 of ours and
 * four that give the same CRC-32 (a CRC can be steered by four bytes, run backwards through its table).
 */
export function withHacktribeRun(bytes, crc = 0x12224d92) {
  const out = Uint8Array.from(bytes);
  const run = Uint8Array.from({ length: 64 }, (_, i) => (i * 37 + 11) & 0xff);
  let state = ~0 >>> 0;
  for (const b of run.subarray(0, 60)) state = (CRC_TABLE[(state ^ b) & 0xff] ^ (state >>> 8)) >>> 0;
  let want = ~crc >>> 0;
  for (let i = 0; i < 4; i++) {
    const idx = CRC_TABLE.findIndex(t => t >>> 24 === want >>> 24);
    want = (((want ^ CRC_TABLE[idx]) << 8) | idx) >>> 0;
  }
  const tail = (want ^ state) >>> 0;
  run.set([tail & 0xff, (tail >>> 8) & 0xff, (tail >>> 16) & 0xff, tail >>> 24], 60);
  out.set(run, 0x170100);
  return out;
}
