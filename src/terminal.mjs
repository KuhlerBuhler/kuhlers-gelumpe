/**
 * What the terminal page does with a script, apart from drawing it.
 *
 * Three targets. With a session on the emulator the script runs there, as a
 * script always did. With a session on the real Electribe it runs in the
 * emulator first (a rehearsal, src/rehearsal.mjs) and only a script that
 * passed there can be sent: the device then gets the recorded messages, in
 * order, through DeviceSession.replay(). There is no switch to skip the
 * rehearsal and no call that reaches the device session with anything else.
 *
 * Reads: a script's own reads (ram.read, screen.get, screen.state, fx names)
 * run in the emulator only, and what they return is the emulator's. The send
 * does not repeat them on the device; what the device checks itself are the
 * reads that belong to a write (the backup, the read-back of what was
 * written, the check of firmware code before code runs). Keys pressed in a
 * script have no counterpart on the device, so a script that presses keys
 * can be tried in the emulator but not sent.
 */
import { makeKorg, ensureFirmware } from "./korg.mjs";
import { rehearse, isPassed } from "./rehearsal.mjs";
import { SendError } from "./sender.mjs";
import { newCarry } from "./session.mjs";

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;

/** An expression is returned; anything else runs as statements. */
export function compile(code) {
  try { return new AsyncFunction("KORG", `return (${code}\n);`); } catch { return new AsyncFunction("KORG", code); }
}

export const NOTE_LIMIT = "Der Emulator kennt den Zustand des Geräts nicht: nicht die Patterns, nicht die offene Seite. Das ändert sich nur, wenn er mit dem Flash vom Gerät läuft (Emulator, Flash, „Flash vom Gerät lesen“). Lesen im Skript zeigt den Emulator, nicht das Gerät.";

export class Terminal {
  /**
   * @param {object} o
   * @param {{ session: object | null, reserve?: Function }} o.device the device area; `session` is the connected session or null
   * @param {{ port: object, baseFirmware: Uint8Array | null, button: (index: number) => Promise<void> }} o.emulator
   * @param {() => Promise<object>} o.probe the shared session on the emulator port, for rehearsals
   * @param {object} [o.timing] settleMs and codeSettleMs for rehearse(), for tests
   * @param {() => boolean} [o.forward] whether scripts go on to a connected real device (the switch of the console)
   */
  constructor({ device, emulator, probe, timing = {}, forward = () => true }) {
    this.device = device;
    this.emulator = emulator;
    this.probe = probe;
    this.timing = timing;
    this.forward = forward;
    this.used = new WeakSet();
  }

  /** "emulator", always there, or "device": forwarding is on and a real device is connected, so everything goes through the emulator first. */
  get mode() {
    const s = this.device.session;
    return this.forward() && s && s.port !== this.emulator.port ? "device" : "emulator";
  }

  /** Run a script in the emulator; nothing involves the device. `print` gets a script's progress lines while it runs. */
  async runDirect(code, { print = null } = {}) {
    if (this.emulator.port.running === false) throw new Error("Der Emulator ist aus. Tippe „start“, dann läuft er.");
    const own = this.device.session;
    const s = own && own.port === this.emulator.port ? own : await this.probe();
    const release = s.reserve?.({ wait: true }) ?? (() => {});
    try {
      await s.idle?.();
      return await compile(code)(makeKorg({ session: () => s, emulator: this.emulator }, { print }));
    } finally { release(); }
  }

  /** Run a script in the emulator and record it. Resolves with the record; `record.sendable` says whether it may go on. */
  async rehearse(code, { print = null } = {}) {
    if (this.emulator.port.running === false) return { ok: false, sendable: false, code, units: [], reason: "Der Emulator läuft nicht. Starte ihn im Bereich Emulator.", whyNot: "Der Emulator läuft nicht." };
    const session = await this.probe();
    await ensureFirmware(session, this.emulator.baseFirmware);
    await session.idle();
    // The emulator is scratch space: a rehearsal that failed must not hold it for the next one.
    const scratch = () => { if (session.blocked || session.pending) session.carry = { ...newCarry(), history: session.history }; };
    scratch();
    try {
      return await rehearse({
        code, session, port: this.emulator.port,
        korg: hooks => makeKorg({ session: () => session, emulator: this.emulator }, { hooks, print }),
        run: korg => compile(code)(korg),
        ...this.timing,
      });
    } finally { scratch(); }
  }

  /** Whether `record` may go to the device now, with the reason in words when it may not. */
  canSend(record, code) {
    if (this.mode !== "device") return { ok: false, why: "Kein echtes Gerät verbunden." };
    if (!record?.sendable || !isPassed(record)) return { ok: false, why: record?.whyNot ?? "Keine bestandene Probe." };
    if (code !== record.code) return { ok: false, why: "Das Skript ist geändert. Erst neu im Emulator proben." };
    if (this.used.has(record)) return { ok: false, why: "Diese Probe ist schon gesendet. Soll es noch einmal gehen, erst neu proben." };
    return { ok: true, why: null };
  }

  /** Send a passed rehearsal to the device. `code` is the script as it stands now. */
  async send(record, code, { onStep } = {}) {
    const can = this.canSend(record, code);
    if (!can.ok) return { ok: false, refused: true, error: new SendError("not-rehearsed", can.why) };
    const s = this.device.session;
    await ensureFirmware(s, this.emulator.baseFirmware);
    const release = s.reserve?.() ?? (() => {});
    try {
      await s.idle?.();
      const res = await s.replay(record, { onStep });
      if (!res.refused) this.used.add(record);
      return res;
    } finally { release(); }
  }
}
