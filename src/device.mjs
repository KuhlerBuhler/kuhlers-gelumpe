/**
 * A stand-in for the hardware.
 *
 * It answers the extended SysEx commands Hacktribe adds, out of a real
 * firmware image, so the addresses are the ones the device would use.
 *
 * What makes it worth having is not that it answers, but that it refuses.
 * The hardware has exactly one way of saying no, which is to say nothing at
 * all, and a silent device looks the same whether the address was wrong, the
 * length was wrong, or the global channel did not match. Here every refusal
 * comes with a reason.
 */
import { syxEnc, syxDec, u32le, readU32le } from "./bytes.mjs";
import { ramToFile, fileToRam, RAM_BASE } from "./layout.mjs";
import { BLOCKS } from "./map/index.mjs";
import EXEC from "../data/exec.mjs";
import { BLECH, crc32 } from "./protocol.mjs";
import { refusal, RAM_WINDOW } from "./protect.mjs";
import { protectTable } from "./sysex-table.mjs";

/** Where the emulator's firmware kept the LED table (measure:2026-10-14/led-zustand-ram); the stand-in starts with all LEDs dark. */
const LED = BLOCKS.get("ledState");
const LED_TABLE = 0xc06c2b14;

/** The three sample tables sit behind the image; each is plain memory of count * stride bytes. */
const SAMPLE_TABLES = ["sampleName", "samplePlayback", "sampleMeta"].map(name => BLOCKS.get(name).meta.table);

/** RAM outside the image that the map declares (the display buffer, the LED table, the sample tables) or the editor uses (the stub buffer), modelled as plain memory. */
const WORK_RAM = [
  ...[BLOCKS.get("display")].map(b => ({ start: b.meta.ram, size: b.size })),
  ...SAMPLE_TABLES.map(t => ({ start: t.ram, size: t.count * t.stride })),
  { start: EXEC.stubAt, size: EXEC.stubSize },
  { start: LED.meta.pointer.at, size: 4 },
  { start: LED_TABLE, size: LED.size },
];

export const CMD = {
  SEARCH: 0x50,
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

/** Hacktribe's reply to a RAM or flash read carries 0x54 (measure:2026-09-14/sysex-channel). */
const READ_REPLY = 0x54;

/** Reading at or above this address hangs the real device. */
export const HANG_ABOVE = 0x1000000;

const PATTERN_SIZE = 0x4000;
const GLOBAL_SIZE = 256;
const ascii = (bytes, at, n) => String.fromCharCode(...bytes.slice(at, at + n));
/** Part byte 37, glide, is dropped by a pattern dump (measure:2026-09-22/pattern-write-glide). */
const GLIDE = { at: 0x800 + 37, stride: 0x330, parts: 16 };

/** An empty but well-formed pattern buffer, for a device nobody gave one. */
function blankPattern() {
  const b = new Uint8Array(PATTERN_SIZE);
  [..."PTST"].forEach((c, i) => { b[i] = c.charCodeAt(0); });
  [..."PTED"].forEach((c, i) => { b[15356 + i] = c.charCodeAt(0); });
  return b;
}

function blankGlobal(channel) {
  const b = new Uint8Array(GLOBAL_SIZE);
  [..."GLST"].forEach((c, i) => { b[i] = c.charCodeAt(0); });
  b[41] = channel;
  return b;
}

export class SimDevice {
  /**
   * @param {object} opts
   * @param {import("./image.mjs").VsbImage} opts.image the firmware to serve
   * @param {number} [opts.channel] global channel; the default is deliberately
   *   not zero, because Hacktribe's own scripts assume zero and this is the
   *   trap most worth reproducing
   * @param {(addr: number) => boolean|void} [opts.execute] stands in for running
   *   code, for tests: called with the address, a result of false stays silent.
   *   Without it an execute is a fault, as in the twin the gate dry-runs on.
   * @param {boolean} [opts.hacktribe] answers Hacktribe's commands 0x52 to 0x57; off, the device is Korg's original
   * @param {boolean|number} [opts.blech] answers BLECH's own commands (docs/messungen/2026-10-15-blech-sysex.md); a number is the largest block
   */
  constructor({ image = null, channel = 9, flash = null, pattern = null, global = null, version = [2, 2], execute = null, hacktribe = true, blech = false } = {}) {
    this.execute = execute;
    this.hacktribe = hacktribe;
    this.blech = blech ? { maxBlock: blech === true ? 0x8000 : blech, build: hacktribe ? "hacktribe" : "stock" } : null;
    this.blechPending = null;
    this.image = image;
    this.version = version;
    this.flash = flash;
    this.channel = channel;
    this.faults = [];
    this.pendingWrite = null;
    this.work = WORK_RAM.map(w => ({ ...w, bytes: new Uint8Array(w.size) }));
    this.work.find(w => w.start === LED.meta.pointer.at).bytes.set(u32le(LED_TABLE - LED.meta.offset));
    const leds = this.work.find(w => w.start === LED_TABLE).bytes;
    for (let i = 0; i < LED.meta.count; i++) leds[i * LED.meta.stride] = i;
    this.pattern = pattern ? Uint8Array.from(pattern) : blankPattern();
    this.global = global ? Uint8Array.from(global) : blankGlobal(channel);
  }

  get head() { return [0x42, 0x30 + this.channel, 0x00, 0x01, 0x24]; }

  get ram() { return this.image?.bytes ?? null; }

  fault(code, message) {
    const entry = { code, message };
    this.faults.push(entry);
    return entry;
  }

  /** True while the device would still be answering at all. */
  get hung() { return this.faults.some(f => f.code === "hang"); }

  /**
   * Take one SysEx message and give back what the device would send, or null
   * for the silence that stands for every kind of no.
   */
  handle(message) {
    const data = Array.from(message);
    if (this.hung) return null;
    if (data[0] !== 0xf0 || data[data.length - 1] !== 0xf7) {
      this.fault("framing", "not a SysEx message: it must start with F0 and end with F7");
      return null;
    }
    const body = data.slice(1, -1);

    if (body[0] === 0x42 && body[1] === CMD.SEARCH) {
      // 15 bytes as measured; bytes 7 to 9 are not recorded and stay as they were.
      return [0xf0, 0x42, 0x50, 0x01, this.channel, 0x00, 0x24, 0x01, 0x00, 0x00, this.version[0], this.version[1], 0x00, 0x00, 0xf7];
    }

    if (body.length < 6) {
      this.fault("truncated", "the message is too short to hold a command");
      return null;
    }

    const channel = body[1] - 0x30;
    if (body[0] !== 0x42 || channel !== this.channel) {
      this.fault("channel",
        `addressed to global channel ${channel}, this device is on ${this.channel}. ` +
        `The real device answers nothing, which looks exactly like an unimplemented command.`);
      return null;
    }

    const cmd = body[5];
    const payload = syxDec(body.slice(6));

    if (cmd >= BLECH.INFO && cmd <= BLECH.DATA) return this.blech ? this.blechCommand(cmd, body.slice(6)) : null;
    if (!this.hacktribe && cmd >= CMD.READ_RAM && cmd <= 0x58) return this.unknown(cmd);

    if ([CMD.READ_RAM, CMD.WRITE_ADDR, CMD.WRITE_DATA].includes(cmd) && !this.image) {
      this.fault("no-image",
        "the simulation was started without a firmware image, so it answers patterns and globals and " +
        "refuses everything that reads or writes RAM. Load a SYSTEM.VSB to try RAM edits.");
      return null;
    }

    switch (cmd) {
      case CMD.PATTERN_REQUEST: return [0xf0, ...this.head, CMD.PATTERN_DUMP, ...syxEnc(this.pattern), 0xf7];
      case CMD.PATTERN_DUMP: return this.loadPattern(payload);
      case CMD.GLOBAL_REQUEST: return [0xf0, ...this.head, CMD.GLOBAL_DUMP, ...syxEnc(this.global), 0xf7];
      case CMD.GLOBAL_DUMP: return this.loadGlobal(payload);
      case CMD.READ_RAM: return this.readRam(payload);
      case CMD.WRITE_ADDR: return this.writeAddr(payload);
      case CMD.WRITE_DATA: return this.writeData(body.slice(6));
      case CMD.READ_FLASH: return this.readFlash(payload);
      case CMD.EXECUTE:
        // Only a test that brings its own stand-in for running code gets an answer; the twin never does.
        if (this.execute) return this.execute(readU32le(payload, 0)) === false ? null : [0xf0, ...this.head, 0x21, 0xf7];
        this.fault("execute",
          "this command runs code at an address on the device. Nothing here simulates that, and " +
          "on hardware a wrong address is not a failed read, it is whatever the processor does next.");
        return null;
      default:
        return this.unknown(cmd);
    }
  }

  unknown(cmd) {
    this.fault("unknown-command", `command ${cmd.toString(16)} is not one this device knows`);
    return null;
  }

  /** What BLECH's firmware says about a range: the rule of src/protect.mjs, with 3 for out of range and 2 for refused. */
  blechStatus(op, addr, length) {
    // The firmware tests the window first, so the loader and the DSP ports, which lie outside it, are out of range rather than refused.
    if (length < 1 || length > this.blech.maxBlock || addr < RAM_WINDOW.start || addr + length > RAM_WINDOW.end) return BLECH.STATUS.RANGE;
    return refusal({ space: "ram", op, addr, length }, { build: this.blech.build }) ? BLECH.STATUS.REFUSED : BLECH.STATUS.OK;
  }

  blechReply(func, ...values) {
    return [0xf0, ...this.head, func, ...syxEnc(values.flatMap(u32le)), 0xf7];
  }

  /**
   * BLECH's four commands (INFO, READ, WRITE BEGIN, WRITE DATA). Like the firmware: a write is declared first and its range
   * checked then, the bytes are checked against their CRC before anything is copied, and the answer to DATA carries the CRC of
   * what is in RAM afterwards. A DATA message without a declaration, or a short one, is not answered.
   */
  blechCommand(cmd, encoded) {
    const payload = syxDec(encoded);
    const word = i => readU32le(payload, i * 4);
    if (cmd === BLECH.INFO) return this.blechReply(BLECH.R_INFO, 0, BLECH.VERSION, 7, this.blech.maxBlock, protectTable({ build: this.blech.build }).crc, 0);
    if (!this.image) {
      this.fault("no-image", "the simulation was started without a firmware image, so BLECH's commands have no RAM to work on.");
      return null;
    }
    if (cmd === BLECH.READ) {
      if (payload.length < 8) return null;
      const addr = word(0);
      const length = word(1);
      let status = this.blechStatus("read", addr, length);
      let bytes = new Uint8Array(0);
      if (status === BLECH.STATUS.OK) {
        const at = this.locate(addr, length, "read");
        if (at.ok) bytes = at.buf.slice(at.offset, at.offset + length);
        else status = BLECH.STATUS.RANGE;
      }
      return [0xf0, ...this.head, BLECH.R_READ, ...syxEnc([...[status, addr, length, status === 0 ? crc32(bytes) : 0].flatMap(u32le), ...bytes]), 0xf7];
    }
    if (cmd === BLECH.BEGIN) {
      if (payload.length < 12) return null;
      this.blechPending = null;
      const [addr, length, crc] = [word(0), word(1), word(2)];
      const status = this.blechStatus("write", addr, length);
      if (status === BLECH.STATUS.OK) this.blechPending = { addr, length, crc };
      return this.blechReply(BLECH.R_BEGIN, status, addr, length);
    }
    const pending = this.blechPending;
    if (!pending) {
      this.fault("write-without-header", "BLECH data arrived with no BEGIN in front of it; the device does not answer it");
      return null;
    }
    this.blechPending = null;
    if (payload.length < pending.length) {
      this.fault("short-write", `BEGIN announced ${pending.length} bytes but only ${payload.length} arrived; the device answers with its own error`);
      return null;
    }
    const bytes = Uint8Array.from(payload.slice(0, pending.length));
    const { addr, length } = pending;
    if (crc32(bytes) !== pending.crc) return this.blechReply(BLECH.R_DATA, BLECH.STATUS.BAD_CRC, addr, length, crc32(bytes));
    const at = this.locate(addr, length, "write");
    if (!at.ok) return this.blechReply(BLECH.R_DATA, BLECH.STATUS.RANGE, addr, length, 0);
    at.buf.set(bytes, at.offset);
    return this.blechReply(BLECH.R_DATA, BLECH.STATUS.OK, addr, length, crc32(at.buf.subarray(at.offset, at.offset + length)));
  }

  /**
   * A whole pattern into the buffer. A dump of the wrong size or without its
   * frame is refused; on the device it would be silence or worse. Glide goes
   * missing the way it does on the hardware.
   */
  loadPattern(bytes) {
    if (bytes.length !== PATTERN_SIZE) {
      this.fault("pattern-length", `a pattern dump carries ${PATTERN_SIZE} bytes; this one carried ${bytes.length}`);
      return null;
    }
    if (ascii(bytes, 0, 4) !== "PTST" || ascii(bytes, 15356, 4) !== "PTED") {
      this.fault("pattern-frame", "the dump is not framed PTST ... PTED, so it is no pattern block");
      return null;
    }
    this.pattern = Uint8Array.from(bytes);
    for (let p = 0; p < GLIDE.parts; p++) this.pattern[GLIDE.at + p * GLIDE.stride] = 0;
    return [0xf0, ...this.head, 0x23, 0xf7];
  }

  loadGlobal(bytes) {
    if (bytes.length !== GLOBAL_SIZE) {
      this.fault("global-length", `a global dump carries ${GLOBAL_SIZE} bytes; this one carried ${bytes.length}`);
      return null;
    }
    if (ascii(bytes, 0, 4) !== "GLST") {
      this.fault("global-frame", "the dump does not start with GLST");
      return null;
    }
    this.global = Uint8Array.from(bytes);
    this.channel = this.global[41];
    return null;
  }

  /**
   * Turn a CPU address into an offset in the image.
   *
   * Note which address space this is. CPU RAM starts at 0xC0000000; the flash
   * commands take plain offsets, and it is a flash read past 0x1000000 that
   * hangs the hardware, not a high RAM address.
   *
   * @returns {{ok: true, offset: number}|{ok: false}}
   */
  locate(addr, length, what) {
    if (addr < RAM_BASE) {
      this.fault("not-ram",
        `${what} at 0x${addr.toString(16)} is not a CPU address. RAM starts at ` +
        `0x${RAM_BASE.toString(16)}; flash offsets go to the flash commands instead.`);
      return { ok: false };
    }
    const work = this.work.find(w => addr >= w.start && addr + length <= w.start + w.size);
    if (work) return { ok: true, buf: work.bytes, offset: addr - work.start };
    const offset = ramToFile(addr);
    if (offset < 0 || offset + length > this.ram.length) {
      this.fault("out-of-range",
        `${what} at 0x${addr.toString(16)} for ${length} bytes falls outside the image, which ` +
        `covers 0x${fileToRam(0).toString(16)} to 0x${fileToRam(this.ram.length).toString(16)}`);
      return { ok: false };
    }
    return { ok: true, buf: this.ram, offset };
  }

  readRam(payload) {
    if (payload.length < 8) {
      this.fault("truncated", "a read needs four bytes of address and four of length");
      return null;
    }
    const addr = readU32le(payload, 0);
    const length = readU32le(payload, 4);
    if (length === 0) { this.fault("zero-length", "a read of zero bytes"); return null; }

    const at = this.locate(addr, length, "read");
    if (!at.ok) return null;

    const slice = at.buf.subarray(at.offset, at.offset + length);
    return [0xf0, ...this.head, READ_REPLY, CMD.READ_RAM, 0x00, ...syxEnc(slice), 0xf7];
  }

  writeAddr(payload) {
    if (payload.length < 8) {
      this.fault("truncated", "a write header needs four bytes of address and four of length");
      return null;
    }
    const addr = readU32le(payload, 0);
    const length = readU32le(payload, 4);
    const at = this.locate(addr, length, "write");
    if (!at.ok) { this.pendingWrite = null; return null; }
    this.pendingWrite = { addr, length, offset: at.offset, buf: at.buf };
    return [0xf0, ...this.head, 0x21, 0xf7];
  }

  writeData(encoded) {
    if (!this.pendingWrite) {
      this.fault("write-without-header",
        "data arrived with no address in front of it; a write is two messages, 0x53 then 0x54");
      return null;
    }
    const { length, offset, buf } = this.pendingWrite;
    const bytes = syxDec(encoded);

    // The packing rounds up to whole blocks of seven, so a few trailing bytes
    // are expected. Anything short of the announced length is a real mistake,
    // and is precisely what the reference encoder produces when the length
    // leaves a remainder of six.
    if (bytes.length < length) {
      this.fault("short-write",
        `announced ${length} bytes but only ${bytes.length} arrived. If the length leaves a ` +
        `remainder of six when divided by seven, the encoder dropped the last block.`);
      this.pendingWrite = null;
      return null;
    }

    buf.set(Uint8Array.from(bytes.slice(0, length)), offset);
    this.pendingWrite = null;
    return [0xf0, ...this.head, 0x21, 0xf7];
  }

  /**
   * Flash lives in its own address space, with plain offsets rather than CPU
   * addresses, and this is where the dangerous edge is: a read at or above
   * 0x1000000 gets no answer, the display goes black and the device has to be
   * power cycled. Nothing is damaged, but the sweep that finds the edge costs
   * a restart every time, so this device goes unresponsive the same way
   * instead of politely declining.
   */
  readFlash(payload) {
    if (payload.length < 8) {
      this.fault("truncated", "a flash read needs four bytes of address and four of length");
      return null;
    }
    const addr = readU32le(payload, 0);
    if (addr >= HANG_ABOVE) {
      this.fault("hang",
        `flash read at 0x${addr.toString(16)}: at or above 0x${HANG_ABOVE.toString(16)} the ` +
        `device stops answering and the display goes black. Power cycle. Do not look for the ` +
        `edge by sweeping.`);
      return null;
    }
    if (!this.flash) {
      this.fault("no-flash-image",
        "no flash contents were given to the simulation, so the address is checked and the read " +
        "is not answered. Pass { flash } to serve it.");
      return null;
    }
    const length = readU32le(payload, 4);
    if (addr + length > this.flash.length) {
      this.fault("out-of-range", `flash read at 0x${addr.toString(16)} runs past the image`);
      return null;
    }
    return [0xf0, ...this.head, READ_REPLY, CMD.READ_FLASH, 0x00,
      ...syxEnc(this.flash.subarray(addr, addr + length)), 0xf7];
  }

  /** Convenience for tests: put bytes into RAM without a message. */
  poke(addr, bytes) {
    const at = this.locate(addr, bytes.length, "poke");
    if (at.ok) at.buf.set(bytes, at.offset);
    return at.ok;
  }

  /** Convenience for tests and scripts: read without building a message. */
  peek(addr, length) {
    const at = this.locate(addr, length, "peek");
    return at.ok ? Uint8Array.from(at.buf.subarray(at.offset, at.offset + length)) : null;
  }
}

export { u32le };
