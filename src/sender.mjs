/**
 * Sends planned steps to a device, one at a time.
 *
 * Each step waits for its answer before the next goes out. No answer within
 * the waiting time is a result, not a reason to try again: on the device,
 * silence stands for every kind of no, and a blind repeat of a half-arrived
 * write makes things worse. After an abort the caller reads back what
 * arrived and decides.
 *
 * Only a reply of the kind the step asked for counts as its answer. A late
 * reply to an earlier, timed-out step is dropped, and after a timeout the
 * next step waits until the line has been quiet for a moment, so a reply can
 * never be taken for the answer to the step after it.
 */
import { checkReadGuard } from "./guards.mjs";
import * as P from "./protocol.mjs";
import { refuseSteps } from "./protect.mjs";
import { syxDec } from "./bytes.mjs";
import EXEC from "../data/exec.mjs";

/**
 * Waiting times in milliseconds. Measured over USB on Linux
 * (measure:2026-10-08/geraeteprotokoll): search 2.4 ms, a 16 KiB read 81 ms,
 * a small RAM write acknowledged after 187 ms at most, a pattern dump after
 * 183 ms. The limits keep a wide margin, because those are no worst cases
 * under load and nothing was measured over DIN, in Chrome or on Windows; a
 * pattern over DIN takes about six seconds by calculation. A 16 KiB flash
 * block took 105 ms on average (measure:2026-10-09/flash-dump). Global, quiet
 * and transport are not measured.
 */
export const TIMEOUTS = { search: 1500, read: 3000, ack: 3000, pattern: 12000, global: 3000, flash: 12000, quiet: 300, info: 400, transport: 3000 };

/**
 * A BLECH block is answered within the time of the line it travels on: the usual waiting time and 0.4 ms for every byte, which is
 * the DIN line (31250 baud, 0.37 ms per byte once the packing is counted). Over USB it is far less; nothing was measured on the device yet.
 */
const LINE_MS_PER_BYTE = 0.4;
/** How often a block whose CRC did not match is sent again before the run fails. Nothing is ever sent again after a timeout. */
export const BLECH_RETRIES = 2;

export class SendError extends Error {
  constructor(kind, message, details = {}) {
    super(message);
    this.name = "SendError";
    this.kind = kind;
    Object.assign(this, details);
  }
}

export class Sender {
  /**
   * @param {object} io
   * @param {(msg: number[]) => void | Promise<void>} io.send hands one message to the port
   * @param {number} [io.channel]
   * @param {object} [io.timeouts]
   */
  constructor({ send, channel = null, timeouts = TIMEOUTS }) {
    this.send = send;
    this.channel = channel;
    this.timeouts = { ...TIMEOUTS, ...timeouts };
    this.waiting = null;
    this.disconnected = false;
    this.unsynced = false;
    this.lastHeard = 0;
    this.stray = 0;
    /** Set by the session when the device answers BLECH's commands: { maxBlock, flash, exec }. Reads and writes then go as BLECH blocks. */
    this.blech = null;
    this.build = null;
  }

  /** Whether a reply is the kind of answer a step waits for. */
  accepts(step, data) {
    const kind = P.classify(data, this.channel);
    const want = step.expect.kind;
    if (want === "search") return kind === "search";
    if (want === "ack") return kind === "ack";
    if (want === "flash") return kind === "read";
    return kind === want;
  }

  /** Feed every incoming MIDI message here. Clock and active sensing are dropped. */
  receive(data) {
    if (P.isRealtime(data) || data[0] !== 0xf0) return;
    this.lastHeard = Date.now();
    const w = this.waiting;
    if (!w || w.phase === "quiet" || w.reply || !this.accepts(w.step, data)) { this.stray++; return; }
    w.reply = Array.from(data);
    if (w.phase === "reply") w.finish(null, w.reply);
  }

  /** The port went away. Whatever is waiting fails now instead of at its timeout. */
  disconnect() {
    this.disconnected = true;
    this.waiting?.finish(new SendError("disconnected", "Gerät während der Sendung abgezogen."));
  }

  async exchange(step) {
    if (this.disconnected) throw new SendError("disconnected", "Kein Gerät verbunden.");
    if (this.waiting) throw new SendError("busy", "Es läuft schon eine Sendung.");
    return new Promise((resolve, reject) => {
      const w = { step, phase: "quiet", reply: null, timer: null, finish: (error, reply) => {
        if (this.waiting !== w) return;
        clearTimeout(w.timer);
        this.waiting = null;
        if (error) reject(error);
        else resolve(reply);
      } };
      this.waiting = w;
      const failed = error => {
        if (this.waiting !== w) return;
        this.unsynced = true;
        w.finish(new SendError("send", error?.message ?? String(error)));
      };
      const sent = () => {
        if (this.waiting !== w) return;
        clearTimeout(w.timer);
        if (step.expect.kind === "none") { w.finish(null, null); return; }
        if (w.reply) { w.finish(null, w.reply); return; }
        w.phase = "reply";
        const wanted = step.expect.timeout ?? step.expect.kind;
        const ms = typeof wanted === "number" ? wanted : this.timeouts[wanted];
        w.timer = setTimeout(() => {
          if (this.waiting !== w) return;
          this.unsynced = true;
          w.finish(new SendError("timeout", `Keine Antwort innerhalb von ${ms} ms. Auf dem Gerät heißt Schweigen jede Art von Nein.`));
        }, ms);
      };
      const send = () => {
        w.phase = "send";
        const ms = this.timeouts.transport + Math.ceil(step.msg.length * LINE_MS_PER_BYTE);
        w.timer = setTimeout(() => {
          if (this.waiting !== w) return;
          this.unsynced = true;
          this.disconnected = true;
          w.finish(new SendError("send-timeout", `Versand nach ${ms} ms nicht abgeschlossen. Verbindung neu öffnen.`));
        }, ms);
        try { Promise.resolve(this.send(step.msg)).then(sent, failed); }
        catch (error) { failed(error); }
      };
      const quiet = () => {
        if (this.waiting !== w) return;
        const ms = this.timeouts.quiet;
        if (Date.now() - this.lastHeard < ms) { w.timer = setTimeout(quiet, ms); return; }
        this.unsynced = false;
        send();
      };
      if (this.unsynced) {
        this.lastHeard = Math.max(this.lastHeard, Date.now());
        quiet();
      } else send();
    });
  }

  /** Check and decode an answer for what the step asked. */
  decode(step, reply) {
    switch (step.expect.kind) {
      case "none": return null;
      case "search": return P.parseSearch(reply);
      case "ack": return P.parseAck(reply, this.channel, step.expect.func);
      case "read": return P.parseReadRam(reply, this.channel, step.expect.length);
      case "flash": return P.parseReadFlash(reply, this.channel, step.expect.length);
      case "pattern": return P.parsePatternDump(reply, this.channel);
      case "global": return P.parseGlobalDump(reply, this.channel);
      default: throw new Error(`unknown expectation ${step.expect.kind}`);
    }
  }

  /** One BLECH message and the one reply of its kind; a timeout is not retried. */
  blechExchange(msg, kind, bytes = 0) {
    return this.exchange({ msg, expect: { kind, timeout: kind === "blech-info" ? "info" : this.timeouts.ack + Math.ceil(bytes * LINE_MS_PER_BYTE) } });
  }

  /** What the device says about its BLECH commands, or null when it does not answer them (a timeout is the answer of a device without them). */
  async blechInfo(model) {
    try { return P.parseBlechInfo(await this.blechExchange(P.blechInfo(this.channel, model), "blech-info"), this.channel, model); }
    catch (e) {
      // A late INFO reply cannot be taken for another step's answer (kinds differ), so no quiet wait is needed.
      if (e instanceof SendError && e.kind === "timeout") { this.unsynced = false; return null; }
      throw e;
    }
  }

  /** A failed attempt as the run reports it: a refusal is the device's rule, anything else a reply that was wrong. */
  blechFailure(e, what) {
    if (!(e instanceof P.BlechError)) return e;
    const refused = e.status === P.BLECH.STATUS.REFUSED || e.status === P.BLECH.STATUS.RANGE;
    return new SendError(refused ? "protected" : e.retry ? "crc" : "verify", e.message, { status: e.status, what });
  }

  /** Whole attempts with a CRC that did not fit are repeated, the first other failure ends it. */
  async blechAttempts(what, attempt) {
    for (let n = 0; ; n++) {
      try { return await attempt(); }
      catch (e) {
        if (!(e instanceof P.BlechError) || !e.retry || n >= BLECH_RETRIES) {
          const error = this.blechFailure(e, what);
          if (error.kind === "crc") error.message = `${e.message} ${n + 1} Versuche, jeder mit anderer Prüfsumme als gesendet. Nichts wurde geschrieben, die Verbindung ist unsicher.`;
          throw error;
        }
      }
    }
  }

  /** `length` bytes at `addr` in blocks of the device's largest size, each checked against its CRC. */
  async blechRead(addr, length) {
    const out = new Uint8Array(length);
    const max = this.blech.maxBlock;
    for (let at = 0; at < length; at += max) {
      const n = Math.min(max, length - at);
      out.set(await this.blechAttempts("read", async () =>
        P.parseBlechRead(await this.blechExchange(P.blechRead(this.channel, addr + at, n), "blech-read", n), this.channel, n)), at);
    }
    return out;
  }

  /** Bytes to `addr`: BEGIN says where and what CRC, DATA carries them, and the device answers with the CRC it read back. */
  async blechWrite(addr, bytes) {
    const max = this.blech.maxBlock;
    for (let at = 0; at < bytes.length; at += max) {
      const part = bytes.subarray(at, Math.min(at + max, bytes.length));
      const crc = P.crc32(part);
      await this.blechAttempts("write", async () => {
        P.parseBlechBegin(await this.blechExchange(P.blechBegin(this.channel, addr + at, part.length, crc), "blech-begin"), this.channel);
        P.parseBlechData(await this.blechExchange(P.blechData(this.channel, part), "blech-data", part.length), this.channel, crc);
      });
    }
    return P.ackFor(this.channel);
  }

  /** `length` bytes of the flash at `addr`, in pieces of FLASH_MAX bytes, each checked against its CRC. */
  async blechFlash(addr, length) {
    const out = new Uint8Array(length);
    for (let at = 0; at < length; at += P.BLECH.FLASH_MAX) {
      const n = Math.min(P.BLECH.FLASH_MAX, length - at);
      out.set(await this.blechAttempts("read", async () =>
        P.parseBlechFlash(await this.blechExchange(P.blechFlash(this.channel, addr + at, n), "blech-flash", n), this.channel, n)), at);
    }
    return out;
  }

  /**
   * Runs the code at `addr` through EXEC. BLECH's EXEC clears the instruction cache itself, so the step that runs the firmware's
   * own routine for it is answered here. The code must return 1, as with Hacktribe's execute, whose answer came only then.
   */
  async blechExecute(addr) {
    if (addr === EXEC.icache.addr) return P.ackFor(this.channel);
    const { result } = await this.blechAttempts("execute", async () => P.parseBlechExec(await this.blechExchange(P.blechExec(this.channel, addr), "blech-exec"), this.channel));
    if (result !== 1) throw new SendError("reply", `Der Code bei 0x${addr.toString(16)} meldet ${result} statt 1.`);
    return P.ackFor(this.channel);
  }

  /** A read, flash read or execute step through BLECH's commands where the device has them; null where it does not. */
  blechStep(sent) {
    if (sent?.kind === "read-ram") return this.blechRead(sent.addr, sent.length);
    if (sent?.kind === "read-flash" && this.blech.flash) return this.blechFlash(sent.addr, sent.length);
    if (sent?.kind === "execute" && this.blech.exec) return this.blechExecute(sent.addr);
    return null;
  }

  /** The size of a file of the update folder on the card (`other`: ORIGINAL.BIN, else SYSTEM.VSB); 0 when there is none. */
  async fileSize(model, other = false) {
    const at = other ? P.BLECH.FILE_OTHER : 0;
    try {
      return (await this.blechAttempts("read", async () => P.parseBlechFileRead(await this.blechExchange(P.blechFileRead(this.channel, at, 0, model), "blech-file-read"), this.channel, 0, model))).size;
    } catch (e) {
      if (e instanceof SendError && e.status === P.BLECH.STATUS.FILE) return 0;
      throw e;
    }
  }

  /** The whole file, in blocks of the device's largest size, each checked against its CRC. `onProgress(done, total)`. */
  async fileRead(size, model, onProgress, other = false) {
    const out = new Uint8Array(size);
    const max = this.blech.maxBlock;
    for (let at = 0; at < size; at += max) {
      const n = Math.min(max, size - at);
      const r = await this.blechAttempts("read", async () =>
        P.parseBlechFileRead(await this.blechExchange(P.blechFileRead(this.channel, (other ? P.BLECH.FILE_OTHER : 0) | at, n, model), "blech-file-read", n), this.channel, n, model));
      if (r.offset !== at || r.bytes.length !== n) throw new SendError("reply", `Datei lesen: ${r.bytes.length} Byte bei ${r.offset} statt ${n} bei ${at}.`);
      out.set(r.bytes, at);
      onProgress?.(at + n, size);
    }
    return out;
  }

  /** The bytes as the new file: the first block makes it anew, the others follow; the device reads every block back from the card. */
  async fileWrite(bytes, model, onProgress, other = false) {
    const max = this.blech.maxBlock;
    for (let at = 0; at < bytes.length; at += max) {
      const part = bytes.subarray(at, Math.min(at + max, bytes.length));
      const crc = P.crc32(part);
      await this.blechAttempts("write", async () => {
        P.parseBlechFileBegin(await this.blechExchange(P.blechFileBegin(this.channel, (other ? P.BLECH.FILE_OTHER : 0) | at, part.length, crc, model), "blech-file-begin"), this.channel, model);
        P.parseBlechData(await this.blechExchange(P.blechData(this.channel, part, model), "blech-data", part.length), this.channel, crc, model);
      });
      onProgress?.(at + part.length, bytes.length);
    }
  }

  /** The bytes as the plugin file `name` on the card (KORG/blechtribe/Plugin/<name>.blech), in blocks, each read back from the card. */
  async pluginWrite(bytes, name, model, onProgress) {
    const max = this.blech.maxBlock;
    for (let at = 0; at < bytes.length; at += max) {
      const part = bytes.subarray(at, Math.min(at + max, bytes.length));
      const crc = P.crc32(part);
      await this.blechAttempts("write", async () => {
        P.parseBlechFileBegin(await this.blechExchange(P.blechPluginBegin(this.channel, at, part.length, crc, name, model), "blech-file-begin"), this.channel, model);
        P.parseBlechData(await this.blechExchange(P.blechData(this.channel, part, model), "blech-data", part.length), this.channel, crc, model);
      });
      onProgress?.(at + part.length, bytes.length);
    }
  }

  /** A FILE offset of the sample file (`temp`: its temp file) at `at`. */
  sampleSelector(temp, at = 0) {
    return (P.BLECH.FILE_SAMPLE | (temp ? P.BLECH.FILE_OTHER : 0) | at) >>> 0;
  }

  /** The size of the sample file (`temp`: its temp file); 0 when there is none. */
  async sampleFileSize(model, temp = false) {
    try {
      return (await this.blechAttempts("read", async () => P.parseBlechFileRead(await this.blechExchange(P.blechFileRead(this.channel, this.sampleSelector(temp), 0, model), "blech-file-read"), this.channel, 0, model))).size;
    } catch (e) {
      if (e instanceof SendError && e.status === P.BLECH.STATUS.FILE) return 0;
      throw e;
    }
  }

  /** `length` bytes of the sample file from `at`, in blocks of the device's largest size, each checked against its CRC; fewer come back at the end of the file. */
  async sampleFileRead(at, length, model, onProgress, temp = false) {
    const out = new Uint8Array(length);
    const max = this.blech.maxBlock;
    let got = 0;
    for (; got < length; ) {
      const n = Math.min(max, length - got);
      const r = await this.blechAttempts("read", async () =>
        P.parseBlechFileRead(await this.blechExchange(P.blechFileRead(this.channel, this.sampleSelector(temp, at + got), n, model), "blech-file-read", n), this.channel, n, model));
      out.set(r.bytes, got);
      got += r.bytes.length;
      onProgress?.(got, length);
      if (r.bytes.length < n) break;
    }
    return out.subarray(0, got);
  }

  /**
   * `bytes` into the sample file from `at` (the file is made when it is not there and never cut: a block at 0 rewrites the header
   * in place), in blocks of the largest size, each read back from the card with its CRC. In the temp file a block at 0 makes it anew.
   */
  async sampleFileWrite(at, bytes, model, onProgress, temp = false) {
    const max = this.blech.maxBlock;
    for (let done = 0; done < bytes.length; done += max) {
      const part = bytes.subarray(done, Math.min(done + max, bytes.length));
      const crc = P.crc32(part);
      await this.blechAttempts("write", async () => {
        P.parseBlechFileBegin(await this.blechExchange(P.blechFileBegin(this.channel, this.sampleSelector(temp, at + done), part.length, crc, model), "blech-file-begin"), this.channel, model);
        P.parseBlechData(await this.blechExchange(P.blechData(this.channel, part, model), "blech-data", part.length), this.channel, crc, model);
      });
      onProgress?.(done + part.length, bytes.length);
    }
  }

  /** `length` bytes (at most COPY_MAX) from one sample file to the other, on the card; the CRC-32 of the bytes copied comes back. */
  async sampleFileCopy(from, to, length, model) {
    const r = await this.blechAttempts("write", async () =>
      P.parseBlechFileCopy(await this.blechExchange(P.blechFileCopy(this.channel, this.sampleSelector(from.temp, from.at), this.sampleSelector(to.temp, to.at), length, model), "blech-file-copy", length / 4), this.channel, model));
    if (r.copied !== length) throw new SendError("reply", `Datei kopieren: ${r.copied} Byte statt ${length}.`);
    return r.crc;
  }

  /** Deletes the sample file (`temp`: its temp file). */
  async sampleFileDelete(model, temp = false) {
    await this.blechAttempts("write", async () => P.parseBlechFileDelete(await this.blechExchange(P.blechFileDelete(this.channel, this.sampleSelector(temp), model), "blech-file-delete"), this.channel, model));
  }

  /** The CRC-32 of `length` bytes (at most COPY_MAX) of a sample file, read from the card by the device and not sent. */
  async sampleFileCrc(at, length, model, temp = false) {
    const r = await this.blechAttempts("read", async () =>
      P.parseBlechFileCrc(await this.blechExchange(P.blechFileCrc(this.channel, this.sampleSelector(temp, at), length, model), "blech-file-crc", length / 4), this.channel, model));
    if (r.length !== length) throw new SendError("reply", `Datei prüfen: ${r.length} Byte statt ${length}.`);
    return r.crc;
  }

  /**
   * Run the steps. Stops at the first failure and says where. `check(step, value, i)` may return a
   * reason to stop after a step that answered.
   * @returns {Promise<{ok: true, results: object[]} | {ok: false, results: object[], failedAt: number, error: SendError}>}
   */
  async run(steps, { onStep, check } = {}) {
    // The last line of the rule in data/protected.mjs: nothing of a run goes out when one step would touch a protected region.
    const refused = refuseSteps(steps, { build: this.build });
    if (refused) return { ok: false, results: [], failedAt: refused.step, error: new SendError("protected", refused.message, { region: refused.region.id }) };
    const results = [];
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      let value;
      try {
        const sent = this.blech ? P.describeMessage(step.msg) : null;
        if (sent?.kind === "write-address") {
          // A Hacktribe write is two steps, address and data; BLECH sends them as one block with its CRC.
          const next = steps[i + 1];
          const data = next && P.describeMessage(next.msg);
          if (data?.kind !== "write-data") throw new SendError("reply", "Eine Schreib-Adresse ohne Daten dahinter.");
          const bytes = Uint8Array.from(syxDec(next.msg.slice(7, -1))).subarray(0, sent.length);
          value = await this.blechWrite(sent.addr, bytes);
          results.push({ step, value }, { step: next, value });
          onStep?.(i + 2, steps.length);
          i++;
          continue;
        }
        const blech = this.blech && this.blechStep(sent);
        value = blech ? await blech : this.decode(step, await this.exchange(step));
        checkReadGuard(step, value);
      } catch (e) {
        const error = e instanceof SendError ? e : new SendError(step.guard ? "unexpected-code" : "reply", e.message);
        return { ok: false, results, failedAt: i, error };
      }
      if ((step.role === "verify" || step.role === "guard") && step.compare) {
        const ignore = new Set(step.ignore || []);
        const bad = [];
        for (let k = 0; k < step.compare.length; k++) if (!ignore.has(k) && value[k] !== step.compare[k]) bad.push(k);
        if (bad.length) {
          const what = step.role === "guard"
            ? `Der Code im Gerät bei 0x${step.target.addr.toString(16)} ist nicht der der geladenen Firmware: ${bad.length} Byte weichen ab.`
            : `Zurückgelesen passt nicht: ${bad.length} Byte weichen ab, das erste bei Versatz ${bad[0]}.`;
          return { ok: false, results, failedAt: i, error: new SendError("mismatch", what, { bad, got: value }) };
        }
      }
      // A caller that knows what answer to expect (a replay) can stop the run here.
      const unexpected = check?.(step, value, i);
      if (unexpected) return { ok: false, results, failedAt: i, error: new SendError("replay-mismatch", unexpected) };
      results.push({ step, value });
      onStep?.(i + 1, steps.length);
    }
    return { ok: true, results };
  }
}

/** The backups a run collected, ready for plan({ kind: "restore" }). */
export const backupsOf = results => results
  .filter(r => r.step.role === "backup" && r.step.target)
  .map(r => ({ addr: r.step.target.addr, bytes: Uint8Array.from(r.value) }));
