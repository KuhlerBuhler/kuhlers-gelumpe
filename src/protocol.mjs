/**
 * The SysEx messages the editor sends and the replies it accepts.
 *
 * Message bytes are built here and in the simulation, nowhere else in the
 * application: src/plan.mjs is the one caller that turns an edit into
 * messages, and test/plan.test.mjs checks that no other module builds them.
 *
 * Korg's commands (pattern and global dumps) and Hacktribe's extended ones
 * (RAM and flash) share one header, which carries the global channel. The
 * channel comes from the reply to the device search; assuming 0 makes every
 * command look unimplemented (measure:2026-09-14/sysex-channel).
 */
import { syxEnc, syxDec, u32le, readU32le } from "./bytes.mjs";
import { crc32 } from "./script/blob.mjs";

export const DEVICE_ID = 0x24;
export const FUNC = {
  PATTERN_REQUEST: 0x10,
  PATTERN_DUMP: 0x40,
  GLOBAL_REQUEST: 0x0e,
  GLOBAL_DUMP: 0x51,
  READ_RAM: 0x52,
  WRITE_ADDR: 0x53,
  WRITE_DATA: 0x54,
  READ_FLASH: 0x55,
  EXECUTE: 0x57,
};
/**
 * Hacktribe answers a RAM or flash read with function 0x54 in byte 6, not
 * with the command's own number (measure:2026-09-14/sysex-channel).
 */
export const READ_REPLY = 0x54;
/** A RAM read answer carries the asked command and a zero in bytes 7 and 8 (measure:2026-10-08/geraeteprotokoll). */
export const READ_ECHO = [0x52, 0x00];
/** A flash read answer carries the asked command and a zero in bytes 7 and 8; seen in the emulator only (measure:2026-10-09/flash-dump). */
export const FLASH_ECHO = [0x55, 0x00];
/** A flash read at or past this offset gets no answer until the device is switched off (measure:2026-09-14/sysex-channel). */
export const FLASH_END = 0x1000000;
/** Both halves of a RAM write are acknowledged with function 0x21 (measure:2026-10-07/sample-name-ram). */
export const WRITE_ACK = 0x21;
/** A pattern dump is acknowledged with function 0x23 (measure:2026-10-08/geraeteprotokoll). */
export const PATTERN_ACK = 0x23;
export const PATTERN_SIZE = 0x4000;
export const GLOBAL_SIZE = 256;

/**
 * BLECH's own commands (tools/patch/blech_sysex.py, docs/messungen/2026-10-15-blech-sysex.md): RAM in blocks of up to
 * `maxBlock` bytes, each with a CRC-32 and an answer that carries a status. Every field of a payload is a 32-bit little
 * endian word, packed like every Electribe payload. They exist beside Hacktribe's 0x52 to 0x57, with other function
 * bytes, and work on Korg's original with BLECH too.
 */
export const BLECH = {
  INFO: 0x60, READ: 0x61, BEGIN: 0x62, DATA: 0x63, FLASH: 0x64, FILE_READ: 0x65, FILE_BEGIN: 0x66, PLUGIN_BEGIN: 0x67,
  R_INFO: 0x68, R_READ: 0x69, R_BEGIN: 0x6a, R_DATA: 0x6b, R_FLASH: 0x6c, R_FILE_READ: 0x6d, R_FILE_BEGIN: 0x6e,
  STATUS: { OK: 0, BAD_CRC: 1, REFUSED: 2, RANGE: 3, FLASH: 4, VERIFY: 5, FILE: 6 },
  /** INFO flag: the update file on the card (KORG/<folder>/System/SYSTEM.VSB) can be read and written, nothing else of the card */
  FLAG_FILE: 0x10,
  /** INFO flag: plugin files can be written (PLUGIN BEGIN, SD:KORG/blechtribe/Plugin/<name>.blech) */
  FLAG_PLUGIN: 0x20,
  /** characters of a plugin file's name: letters, digits, "_" and "-" */
  NAME_MAX: 16,
  /** the largest offset + length of the update file: the size of a VSB */
  FILE_LIMIT: 0x200100,
  /** bit 31 of a FILE offset: ORIGINAL.BIN beside SYSTEM.VSB, the unpatched file the next update starts from */
  FILE_OTHER: 0x80000000,
  VERSION: 1,
};
const STATUS_TEXT = { 1: "Die Prüfsumme stimmt nicht", 2: "Das Gerät verweigert den Zugriff (geschützter Bereich)", 3: "Adresse oder Länge liegt außerhalb des erlaubten Bereichs", 4: "Die Flash-Funktion der Firmware meldet keinen Erfolg", 5: "Das Zurücklesen nach dem Schreiben weicht ab", 6: "Die Karte meldet einen Fehler (keine Karte, keine Datei oder voll)" };

export const head = (channel, model = DEVICE_ID) => {
  if (!Number.isInteger(channel) || channel < 0 || channel > 15) throw new RangeError(`channel ${channel}`);
  if (![0x23, 0x24].includes(model)) throw new RangeError(`model ${model}`);
  return [0x42, 0x30 + channel, 0x00, 0x01, model];
};

const frame = body => [0xf0, ...body, 0xf7];

export const search = () => frame([0x42, 0x50, 0x00, 0x00]);

/** A reply problem, with a reason the page can show. */
export class ReplyError extends Error {
  constructor(message) { super(message); this.name = "ReplyError"; }
}

/** A BLECH answer that is not a plain ok: `status` is the device's, `retry` says that nothing was written and the block may be sent again. */
export class BlechError extends ReplyError {
  constructor(status, what) {
    super(`${what}: ${STATUS_TEXT[status] ?? `Status ${status}`}.`);
    this.name = "BlechError";
    this.status = status;
    this.retry = status === BLECH.STATUS.BAD_CRC;
  }
}

/** MIDI realtime bytes arrive on the same line and are not part of any reply. */
export const isRealtime = data => data.length === 1 && data[0] >= 0xf8;

function checkFrame(msg) {
  const data = Array.from(msg);
  if (data[0] !== 0xf0 || data[data.length - 1] !== 0xf7) throw new ReplyError("Antwort ist keine vollständige SysEx-Nachricht.");
  return data;
}

/**
 * The search reply starts F0 42 50 01; byte 4 is the global channel and
 * byte 6 the model, 0x24 for the Sampler. Bytes 10 and 11 read 2 and 2 on a
 * Sampler 2.02 with Hacktribe, and the reply is 15 bytes long
 * (measure:2026-10-08/geraeteprotokoll). That does not identify a build;
 * the session checks RAM fingerprints for that.
 */
export function parseSearch(msg) {
  const d = checkFrame(msg);
  if (d.length < 13 || d[1] !== 0x42 || d[2] !== 0x50 || d[3] !== 0x01) throw new ReplyError("Antwort auf die Gerätesuche hat nicht die erwartete Form.");
  return { channel: d[4] & 0x0f, model: d[6], sampler: d[6] === DEVICE_ID, version: [d[10], d[11]] };
}

/** What kind of reply a message is, so a stray one is never taken for another. */
export function classify(msg, channel) {
  const d = Array.from(msg);
  if (d[0] !== 0xf0 || d[d.length - 1] !== 0xf7) return "other";
  if (d[1] === 0x42 && d[2] === 0x50 && d[3] === 0x01) return "search";
  // the Sampler's model byte, or the blue Electribe 2's for BLECH's own replies (its update file goes the same way)
  const ours = channel != null && [DEVICE_ID, 0x23].some(model => head(channel, model).every((b, i) => d[1 + i] === b));
  if (!ours) return "other";
  if (d[5] !== DEVICE_ID && ![BLECH.R_INFO, BLECH.R_DATA, BLECH.R_FILE_READ, BLECH.R_FILE_BEGIN].includes(d[6])) return "other";
  return { [READ_REPLY]: "read", [FUNC.PATTERN_DUMP]: "pattern", [FUNC.GLOBAL_DUMP]: "global", [WRITE_ACK]: "ack", [PATTERN_ACK]: "ack",
    [BLECH.R_INFO]: "blech-info", [BLECH.R_READ]: "blech-read", [BLECH.R_BEGIN]: "blech-begin", [BLECH.R_DATA]: "blech-data",
    [BLECH.R_FILE_READ]: "blech-file-read", [BLECH.R_FILE_BEGIN]: "blech-file-begin" }[d[6]] ?? "other";
}

function checkHead(d, channel, func, model = DEVICE_ID) {
  const h = head(channel, model);
  for (let i = 0; i < h.length; i++) {
    if (d[1 + i] !== h[i]) throw new ReplyError(`Antwort kommt nicht von einer Electribe Sampler auf Kanal ${channel + 1}.`);
  }
  if (d[6] !== func) throw new ReplyError(`Antwort hat Funktion 0x${d[6].toString(16)}, erwartet 0x${func.toString(16)}.`);
}

export function parseAck(msg, channel, func = WRITE_ACK) {
  const data = checkFrame(msg);
  checkHead(data, channel, func);
  if (data.length !== 8) throw new ReplyError("Schreibbestätigung hat nicht die erwartete Länge.");
  return data;
}

function decodeExact(d, from, size, what) {
  const bytes = syxDec(d.slice(from, -1));
  if (bytes.length !== size) throw new ReplyError(`${what} hat ${bytes.length} Byte statt ${size}.`);
  return Uint8Array.from(bytes);
}

export const patternRequest = channel => frame([...head(channel), FUNC.PATTERN_REQUEST]);

export function patternDump(channel, block) {
  if (block.length !== PATTERN_SIZE) throw new RangeError(`a pattern is ${PATTERN_SIZE} bytes, got ${block.length}`);
  return frame([...head(channel), FUNC.PATTERN_DUMP, ...syxEnc(block)]);
}

export function parsePatternDump(msg, channel) {
  const d = checkFrame(msg);
  checkHead(d, channel, FUNC.PATTERN_DUMP);
  return decodeExact(d, 7, PATTERN_SIZE, "Pattern-Dump");
}

export const globalRequest = channel => frame([...head(channel), FUNC.GLOBAL_REQUEST]);

export function globalDump(channel, block) {
  if (block.length !== GLOBAL_SIZE) throw new RangeError(`the global block is ${GLOBAL_SIZE} bytes, got ${block.length}`);
  return frame([...head(channel), FUNC.GLOBAL_DUMP, ...syxEnc(block)]);
}

export function parseGlobalDump(msg, channel) {
  const d = checkFrame(msg);
  checkHead(d, channel, FUNC.GLOBAL_DUMP);
  return decodeExact(d, 7, GLOBAL_SIZE, "Global-Dump");
}

export const readRam = (channel, addr, length) =>
  frame([...head(channel), FUNC.READ_RAM, ...syxEnc([...u32le(addr), ...u32le(length)])]);

export function parseReadRam(msg, channel, length) {
  const d = checkFrame(msg);
  checkHead(d, channel, READ_REPLY);
  if (d[7] !== READ_ECHO[0] || d[8] !== READ_ECHO[1]) throw new ReplyError("Leseantwort trägt in Byte 7 und 8 nicht das gelesene Kommando.");
  return decodeExact(d, 9, length, "Lesen");
}

/** Read flash, never at or past FLASH_END. */
export function readFlash(channel, addr, length) {
  if (!Number.isInteger(addr) || !Number.isInteger(length) || addr < 0 || length <= 0 || addr + length > FLASH_END) {
    throw new RangeError(`flash read 0x${addr.toString(16)}+0x${length.toString(16)} reaches past 0x${FLASH_END.toString(16)}, where the device stops answering`);
  }
  return frame([...head(channel), FUNC.READ_FLASH, ...syxEnc([...u32le(addr), ...u32le(length)])]);
}

export function parseReadFlash(msg, channel, length) {
  const d = checkFrame(msg);
  checkHead(d, channel, READ_REPLY);
  if (d[7] !== FLASH_ECHO[0] || d[8] !== FLASH_ECHO[1]) throw new ReplyError("Leseantwort trägt in Byte 7 und 8 nicht das Flash-Kommando.");
  return decodeExact(d, 9, length, "Flash lesen");
}

export const writeRamAddress = (channel, addr, length) =>
  frame([...head(channel), FUNC.WRITE_ADDR, ...syxEnc([...u32le(addr), ...u32le(length)])]);

export const writeRamData = (channel, bytes) =>
  frame([...head(channel), FUNC.WRITE_DATA, ...syxEnc(bytes)]);

/** Run code at a RAM address. The payload is the address and a zero word, as measured (measure:2026-10-08/led-execute). */
export const execute = (channel, addr) =>
  frame([...head(channel), FUNC.EXECUTE, ...syxEnc([...u32le(addr), ...u32le(0)])]);

const words = (...values) => values.flatMap(u32le);
const blechFrame = (channel, func, payload = [], model = DEVICE_ID) => frame([...head(channel, model), func, ...syxEnc(payload)]);

export const blechInfo = (channel, model = DEVICE_ID) => blechFrame(channel, BLECH.INFO, [], model);
export const blechRead = (channel, addr, length, model = DEVICE_ID) => blechFrame(channel, BLECH.READ, words(addr, length), model);
export const blechBegin = (channel, addr, length, crc) => blechFrame(channel, BLECH.BEGIN, words(addr, length, crc));
export const blechData = (channel, bytes, model = DEVICE_ID) => blechFrame(channel, BLECH.DATA, bytes, model);
/** The update file on the card: `length` bytes from `offset`; and the announcement of a write to it (DATA follows as for RAM). */
export const blechFileRead = (channel, offset, length, model = DEVICE_ID) => blechFrame(channel, BLECH.FILE_READ, words(offset, length), model);
export const blechFileBegin = (channel, offset, length, crc, model = DEVICE_ID) => blechFrame(channel, BLECH.FILE_BEGIN, words(offset, length, crc), model);
/** A plugin file's name as the device takes it, or null: 1 to NAME_MAX letters, digits, "_" or "-". */
export const pluginName = name => (typeof name === "string" && new RegExp(`^[A-Za-z0-9_-]{1,${BLECH.NAME_MAX}}$`).test(name) ? name : null);
/** The announcement of a write to a plugin file; the answer is the one of FILE BEGIN, DATA follows the same way. */
export function blechPluginBegin(channel, offset, length, crc, name, model = DEVICE_ID) {
  if (!pluginName(name)) throw new RangeError(`plugin name ${name}`);
  const raw = Array.from(name, c => c.charCodeAt(0));
  return blechFrame(channel, BLECH.PLUGIN_BEGIN, [...words(offset, length, crc), ...raw, ...new Array(BLECH.NAME_MAX - raw.length).fill(0)], model);
}

function blechWords(msg, channel, func, count, what, model = DEVICE_ID) {
  const d = checkFrame(msg);
  checkHead(d, channel, func, model);
  const payload = syxDec(d.slice(7, -1));
  if (payload.length < count * 4) throw new ReplyError(`${what}: Antwort ist zu kurz.`);
  return { payload, word: i => readU32le(payload, i * 4) };
}

/** What the device says about itself: protocol version, flags (1 read, 2 write, 4 CRC-32, 8 FLASH READ), the largest block and the CRC of its protection table. */
export function parseBlechInfo(msg, channel, model = DEVICE_ID) {
  const { word } = blechWords(msg, channel, BLECH.R_INFO, 5, "BLECH INFO", model);
  if (word(0) !== BLECH.STATUS.OK) throw new BlechError(word(0), "BLECH INFO");
  return { version: word(1), flags: word(2), maxBlock: word(3), tableCrc: word(4) };
}

/** The bytes of a READ answer, checked against the length asked for and the CRC the device sent. */
export function parseBlechRead(msg, channel, length, model = DEVICE_ID) {
  const { payload, word } = blechWords(msg, channel, BLECH.R_READ, 4, "BLECH Lesen", model);
  if (word(0) !== BLECH.STATUS.OK) throw new BlechError(word(0), "BLECH Lesen");
  const bytes = Uint8Array.from(payload.slice(16));
  if (bytes.length !== length || word(2) !== length) throw new ReplyError(`BLECH Lesen hat ${bytes.length} Byte statt ${length}.`);
  if (crc32(bytes) !== word(3)) throw new BlechError(BLECH.STATUS.BAD_CRC, "BLECH Lesen");
  return bytes;
}

/** A FILE READ answer: the bytes, checked against the length and the CRC, and the size of the whole file. */
export function parseBlechFileRead(msg, channel, length, model = DEVICE_ID) {
  const { payload, word } = blechWords(msg, channel, BLECH.R_FILE_READ, 5, "Datei lesen", model);
  if (word(0) !== BLECH.STATUS.OK) throw new BlechError(word(0), "Datei lesen");
  const bytes = Uint8Array.from(payload.slice(20));
  if (bytes.length !== word(2) || word(2) > length) throw new ReplyError(`Datei lesen hat ${bytes.length} Byte statt ${word(2)}.`);
  if (crc32(bytes) !== word(3)) throw new BlechError(BLECH.STATUS.BAD_CRC, "Datei lesen");
  return { offset: word(1), bytes, size: word(4) };
}

/** The answer to FILE BEGIN: ok, or why the write was refused before any byte was sent. */
export function parseBlechFileBegin(msg, channel, model = DEVICE_ID) {
  const { word } = blechWords(msg, channel, BLECH.R_FILE_BEGIN, 3, "Datei schreiben", model);
  if (word(0) !== BLECH.STATUS.OK) throw new BlechError(word(0), "Datei schreiben");
  return { offset: word(1), length: word(2) };
}

/** The answer to BEGIN: ok, or the reason the write was refused before any byte was sent. */
export function parseBlechBegin(msg, channel) {
  const { word } = blechWords(msg, channel, BLECH.R_BEGIN, 3, "BLECH Schreiben, Adresse");
  if (word(0) !== BLECH.STATUS.OK) throw new BlechError(word(0), "BLECH Schreiben, Adresse");
  return { addr: word(1), length: word(2) };
}

/** The answer to DATA: ok with the CRC the device read back, which has to be the one that was sent. */
export function parseBlechData(msg, channel, crc, model = DEVICE_ID) {
  const { word } = blechWords(msg, channel, BLECH.R_DATA, 4, "BLECH Schreiben, Daten", model);
  if (word(0) !== BLECH.STATUS.OK) throw new BlechError(word(0), "BLECH Schreiben, Daten");
  if (word(3) !== crc) throw new BlechError(BLECH.STATUS.VERIFY, "BLECH Schreiben, Daten");
  return { addr: word(1), length: word(2), crc: word(3) };
}

/** The 8-byte acknowledgement Hacktribe sends for a write, which a BLECH write is reported as, so that a recording replays on either. */
export const ackFor = channel => frame([...head(channel), WRITE_ACK]);

/** CRC-32 as the device computes it, for the one who builds the DATA message. */
export { crc32 };

/**
 * The same message for another global channel: only the channel byte of the
 * header changes, every other byte stays. The device search carries no
 * channel and comes back unchanged.
 */
export function withChannel(msg, channel) {
  const d = Array.from(msg);
  if (d[0] !== 0xf0 || d[d.length - 1] !== 0xf7) throw new ReplyError("Keine vollständige SysEx-Nachricht.");
  if (d[1] === 0x42 && d[2] === 0x50) return d;
  const h = head(channel);
  if (d[1] !== h[0] || (d[2] & 0xf0) !== 0x30 || d.slice(3, 6).some((b, i) => b !== h[2 + i])) throw new ReplyError("Die Nachricht hat keinen Kopf der Electribe Sampler.");
  return [d[0], ...h, ...d.slice(6)];
}

/** What a message asks for, read back from its bytes; for reports and tests. */
export function describeMessage(msg) {
  const d = Array.from(msg);
  if (d[1] === 0x42 && d[2] === 0x50) return { kind: "search" };
  const func = d[6];
  const payload = syxDec(d.slice(7, -1));
  // BLECH's commands mean what Hacktribe's do for the rules that look at a message: a read, the announcement of a write, its data.
  if (func === BLECH.INFO) return { kind: "blech-info", channel: d[2] - 0x30, length: 0 };
  if (func === BLECH.READ || func === BLECH.BEGIN) return { kind: func === BLECH.READ ? "read-ram" : "write-address", channel: d[2] - 0x30, addr: readU32le(payload, 0), length: readU32le(payload, 4) };
  if (func === BLECH.DATA) return { kind: "write-data", channel: d[2] - 0x30, length: payload.length };
  if (func === BLECH.FILE_READ || func === BLECH.FILE_BEGIN || func === BLECH.PLUGIN_BEGIN) return { kind: func === BLECH.FILE_READ ? "file-read" : "file-write", channel: d[2] - 0x30, offset: readU32le(payload, 0), length: readU32le(payload, 4) };
  if (func === FUNC.EXECUTE) return { kind: "execute", channel: d[2] - 0x30, addr: readU32le(payload, 0), length: 0 };
  if (func === FUNC.READ_RAM || func === FUNC.WRITE_ADDR || func === FUNC.READ_FLASH) {
    const kind = { [FUNC.READ_RAM]: "read-ram", [FUNC.WRITE_ADDR]: "write-address", [FUNC.READ_FLASH]: "read-flash" }[func];
    return { kind, channel: d[2] - 0x30, addr: readU32le(payload, 0), length: readU32le(payload, 4) };
  }
  const kinds = { 0x10: "pattern-request", 0x40: "pattern-dump", 0x0e: "global-request", 0x51: "global-dump", 0x54: "write-data", 0x57: "execute" };
  return { kind: kinds[func] ?? "unknown", channel: d[2] - 0x30, length: payload.length };
}
