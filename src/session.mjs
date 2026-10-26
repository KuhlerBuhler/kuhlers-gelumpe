/**
 * A connected device and everything sent to it in this sitting.
 *
 * All sending goes plan -> gate -> sender, one operation at a time. What
 * went wrong survives a reconnect: the page keeps a `carry` object per port
 * and hands it to the next session, so a blocked target stays blocked and
 * its backups stay available until the user has decided.
 *
 * After a failed send the backup is offered, not written on its own
 * (concept, "Senden"): first read back what arrived, show it, let the user
 * choose. The one exception is a field written to several places, which is
 * rolled back as a whole at once; half a menu length plays the wrong unit.
 */
import { plan, sampleWrites } from "./plan.mjs";
import { admit, regionCheck } from "./gate.mjs";
import { Sender, SendError, backupsOf } from "./sender.mjs";
import { withChannel, describeMessage } from "./protocol.mjs";
import { isPassed } from "./rehearsal.mjs";
import { SimDevice } from "./device.mjs";
import { VsbImage } from "./image.mjs";
import { sha256 } from "./firmware.mjs";
import KNOWN_DEVICES from "../data/devices.mjs";
import { tableEntry, RAM_BASE } from "./map/address.mjs";
import { BLOCKS } from "./map/index.mjs";
import { readContext } from "./screen.mjs";
import { readLeds } from "./leds.mjs";
import { readSampleNames, readSample } from "./samples.mjs";
import { FLASH_END, BLECH } from "./protocol.mjs";
import { protectTable } from "./sysex-table.mjs";

/** The size of one write message when BLECH's commands carry it: 16 times Hacktribe's, and a block that a 31250 baud line sends in 1.5 s. */
export const BLECH_WRITE = 0x1000;

const ELECTRIBE = /electribe/i;

/** Windows names a device's second MIDI jack "MIDIOUT2 (name)" and "MIDIIN2 (name)"; both become "MIDI2 (name)". */
const pairKey = name => name.replace(/^MIDI(?:IN|OUT)(\d+)/i, "MIDI$1");
/** The device a port belongs to: its name without Windows' jack number and without the jack's own name. */
const deviceOf = name => name.replace(/^MIDI(?:IN|OUT)\d+\s*\((.*)\)$/i, "$1").replace(/[\s_]*(PAD\/KNOB|SOUND)\s*$/i, "").trim();
/** The jack that answers SysEx comes first: the first one of the device, not PAD/KNOB. */
const jackRank = name => (/^MIDI(?:IN|OUT)\d+/i.test(name) ? 2 : 0) + (/PAD\/KNOB/i.test(name) ? 1 : 0);

/**
 * Ports that look like an Electribe, paired by name, one pair per device, so the page asks only when there are
 * really several. An Electribe has two jacks per direction (SOUND and PAD/KNOB); a jack without an input of its
 * name never answers and is left out.
 */
export function electribePorts(access) {
  const outs = [...access.outputs.values()].filter(p => ELECTRIBE.test(p.name));
  const ins = [...access.inputs.values()].filter(p => ELECTRIBE.test(p.name));
  const pairs = outs
    .map(out => ({ out, in: ins.find(i => i.name === out.name) ?? ins.find(i => pairKey(i.name) === pairKey(out.name)) ?? null, name: out.name }))
    .filter(p => p.in);
  const best = new Map();
  for (const p of pairs) {
    const device = deviceOf(p.name);
    const kept = best.get(device);
    if (!kept || jackRank(p.name) < jackRank(kept.name)) best.set(device, p);
  }
  return pairs.filter(p => best.get(deviceOf(p.name)) === p);
}

export const newCarry = () => ({ blocked: null, pending: null, history: [] });

const sleep = ms => new Promise(r => setTimeout(r, ms));

/** Sent and kept out of the undo history: pictures, restores, and code that puts its own bytes back. */
const UNTRACKED = new Set(["patternRestore", "restore", "screenWrite", "exec"]);

/** Steps by what they ask for, so a replay can tell that a re-planned restore has the shape of the recorded one. */
const shapeOf = steps => steps.map(s => { const d = describeMessage(s.msg); return `${d.kind}:${d.addr ?? ""}:${d.length ?? ""}`; });

/** A token for exactly what the user was shown, so a yes only covers that. */
export const verdictToken = checked => checked.reasons.map(r => `${r.severity}:${r.code}:${r.message}`).join("|");

export class DeviceSession {
  /**
   * @param {object} opts
   * @param {object} opts.port { out, in } from electribePorts()
   * @param {object} [opts.carry] state kept across reconnects, from newCarry()
   * @param {object[]} [opts.known] device versions known to carry the measured layout
   * @param {object} [opts.timeouts]
   */
  constructor({ port, carry = newCarry(), known = KNOWN_DEVICES, timeouts }) {
    if (!port?.out || !port?.in) throw new SendError("port", "Zu diesem MIDI-Ausgang gibt es keinen Eingang mit demselben Namen; so kommt keine Antwort an.");
    this.port = port;
    this.carry = carry;
    this.known = known;
    this.sender = new Sender({ send: msg => port.out.send(msg), timeouts });
    this.device = null;
    this.firmware = null;
    this.firmwareBytes = null;
    this.twin = null;
    this.units = null;
    this.profile = null;
    this.running = null;
    this.rehearsal = null;
    this.requireRehearsal = false;
    this.ledAt = null;
    // The listener is kept so that a second session on the same port can be told from this one.
    this.listener = e => this.sender.receive(e.data);
    this.listen();
    this.onUnit = null;
  }

  /** Take the port's single message handler (a second session on the same port takes it away; this takes it back). */
  listen() { this.port.in.onmidimessage = this.listener; }

  /** Whether this session still hears its port. */
  get listening() { return this.port.in.onmidimessage === this.listener; }

  /** Every edit tries the emulator's session first from now on (plan 5.1, 5.2). With `requireRehearsal` set, no edit goes out without one. */
  rehearseOn(session) {
    this.rehearsal = session;
    if (session && this.firmwareBytes) session.useFirmware(this.firmwareBytes, this.firmware, { units: this.units, profile: this.profile });
  }

  get blocked() { return this.carry.blocked; }
  set blocked(v) { this.carry.blocked = v; }
  get history() { return this.carry.history; }
  get pending() { return this.carry.pending; }
  get busy() { return !!this.running; }

  /**
   * One operation at a time: a double click or an undo during a send is refused, not interleaved. While an action holds a
   * reservation that waits (the terminal), its operations wait for one that already runs (a read of the sidebar or of the
   * connection) instead of being refused.
   */
  async exclusive(fn) {
    while (this.running && (this.waiters ?? 0) > 0) await this.idle();
    if (this.running) throw new SendError("busy", "Es läuft schon eine Sendung. Erst wenn sie fertig ist, geht die nächste.");
    this.running = fn();
    try { return await this.running; } finally { this.running = null; }
  }

  /** Resolves once nothing is running, e.g. after the sidebar's screen read. */
  async idle() {
    while (this.running) await this.running.catch(() => {});
  }

  /**
   * A user's action spans check, a confirmation dialog and the send. While
   * it is reserved, background reads (the sidebar) keep away; call the
   * returned function when the action is over.
   */
  reserve({ wait = false } = {}) {
    this.reservations = (this.reservations ?? 0) + 1;
    if (wait) this.waiters = (this.waiters ?? 0) + 1;
    let done = false;
    return () => { if (!done) { done = true; this.reservations--; if (wait) this.waiters--; } };
  }

  get reserved() { return (this.reservations ?? 0) > 0; }

  /** The Web MIDI port vanished: fail what is waiting, keep the history. */
  lost() { this.sender.disconnect(); }

  /** What a plan needs to know about this device: its channel and how large one write message may be. */
  planState(channel = this.device?.channel ?? 0) {
    return { channel, maxWrite: this.sender.blech ? Math.min(this.sender.blech.maxBlock, BLECH_WRITE) : undefined };
  }

  /** The device's signatures against the known builds; the first build whose every signature matches. */
  async identifyBuild(channel, candidates) {
    for (const profile of candidates) {
      let verified = !!profile.fingerprints?.length;
      for (const signature of profile.fingerprints ?? []) {
        const run = await this.sender.run(plan({ kind: "readRam", addr: signature.addr, length: signature.length }, this.planState(channel)));
        if (!run.ok || await sha256(run.results[0].value) !== signature.sha256) { verified = false; break; }
      }
      if (verified) return profile;
    }
    return null;
  }

  /**
   * Device search, then BLECH's own INFO. A device that answers it is read and written through BLECH's commands, which
   * work on Korg's original with BLECH as well; the build is then told by its code signatures. One that does not answer it
   * gets a small RAM read with Hacktribe's command, as before; and a device that answers neither is read-only.
   */
  connect() {
    return this.exclusive(async () => {
      const found = await this.sender.run(plan({ kind: "search" }));
      if (!found.ok) throw found.error;
      const { channel, version, sampler, model } = found.results[0].value;
      this.sender.channel = channel;
      this.sender.blech = null;
      const info = sampler ? await this.sender.blechInfo() : null;
      const usable = info && info.version === BLECH.VERSION && (info.flags & 3) === 3 && info.maxBlock >= 256;
      if (usable) this.sender.blech = { maxBlock: info.maxBlock, flash: !!(info.flags & BLECH.FLAG_FLASH), exec: !!(info.flags & BLECH.FLAG_EXEC) };
      const candidates = sampler ? this.known.filter(k => k.version[0] === version[0] && k.version[1] === version[1]) : [];
      const profile = candidates.find(k => (k.build ?? "hacktribe") === "hacktribe");
      let hacktribe = false;
      let fingerprintVerified = false;
      let build = null;
      if (usable) {
        const found = await this.identifyBuild(channel, candidates);
        fingerprintVerified = !!found;
        build = found ? (found.build ?? "hacktribe") : null;
        hacktribe = build === "hacktribe";
      } else if (profile?.fingerprints?.length) {
        fingerprintVerified = true;
        for (const signature of profile.fingerprints) {
          const run = await this.sender.run(plan({ kind: "readRam", addr: signature.addr, length: signature.length }, { channel }));
          hacktribe = run.ok;
          if (!run.ok || await sha256(run.results[0].value) !== signature.sha256) {
            fingerprintVerified = false;
            break;
          }
        }
        if (fingerprintVerified) build = "hacktribe";
      } else {
        const probe = tableEntry("table.mfx", 0);
        const run = await this.sender.run(plan({ kind: "readRam", addr: probe.ram, length: 16 }, { channel }));
        hacktribe = run.ok;
      }
      this.sender.build = build;
      const blech = usable ? { ...info, tableMatches: info.tableCrc === protectTable({ build: build ?? undefined }).crc } : null;
      this.device = { channel, version, versionKnown: sampler && fingerprintVerified, fingerprintVerified, sampler, model, hacktribe, blech, build, ram: usable ? "blech" : hacktribe ? "hacktribe" : null };
      if (!this.twin) this.twin = new SimDevice({ channel });
      // A pattern is read back with Korg's own request, which needs no Hacktribe.
      if (this.pending && (this.device.ram || this.pending.pattern)) this.pending.now = await this.readBack(this.pending);
      return this.device;
    });
  }

  /**
   * The user's firmware file, copied for the twin. Rebuilt only when the file
   * changes: the twin follows every confirmed send and must not be reset.
   */
  useFirmware(bytes, identity, { units, profile }) {
    this.rehearsal?.useFirmware(bytes, identity, { units, profile });
    this.firmware = identity;
    this.units = units;
    this.profile = profile;
    if (this.firmwareBytes === bytes && this.twin?.image) return;
    this.firmwareBytes = bytes;
    this.twin = new SimDevice({ image: new VsbImage(bytes), channel: this.device?.channel ?? 0, pattern: this.twin?.pattern });
  }

  context() {
    if (this.twin && this.device) this.twin.channel = this.device.channel;
    // Code runs only in an emulator, or in a session that tries every edit in one first (plan 5.1).
    const rehearsed = this.port.emulator === true || !!this.rehearsal;
    return { device: this.device, firmware: this.firmware, session: this.twin, units: this.units, profile: this.profile, blocked: this.blocked, rehearsed };
  }

  /** Plan and check without sending. */
  async check(edit) {
    const steps = plan(edit, this.planState());
    const checked = { steps, ...(await admit(edit, steps, this.context())) };
    return { ...checked, token: verdictToken(checked) };
  }

  /**
   * Send an edit that passed the gate. A verdict that needs confirmation
   * goes out only with the token of exactly that verdict, or `true` from a
   * caller that showed nothing, such as a test.
   */
  apply(edit, { confirmed = false, onStep } = {}) {
    return this.exclusive(() => this.applyNow(edit, { confirmed, onStep }));
  }

  /** Every attempt is reported to `onUnit`, what ran and what came back, so a script can be recorded and replayed. */
  async applyNow(edit, { confirmed, onStep }) {
    const unit = { edit, steps: null, ok: false, error: null, cleanup: null, run: null };
    let res = null;
    let thrown = null;
    try { res = await this.applyInner(edit, { confirmed, onStep }, unit); } catch (e) { thrown = e; }
    unit.ok = !!res?.ok;
    unit.error ??= thrown ? thrown.message : res.ok ? null : (res.error?.message ?? res.gate?.reasons?.map(r => r.message).join(" ") ?? "abgelehnt");
    if (this.onUnit) {
      const { run, ...rest } = unit;
      const acks = {};
      for (const [i, r] of (run?.results ?? []).entries()) if (r.step.expect.kind === "ack") acks[i] = Array.from(r.value);
      this.onUnit({ ...rest, acks, failedAt: run && !run.ok ? run.failedAt : null });
    }
    if (thrown) throw thrown;
    return res;
  }

  async applyInner(edit, { confirmed, onStep }, unit) {
    const checked = await this.check(edit);
    unit.steps = checked.steps;
    if (checked.verdict === "blocked") return { ok: false, gate: checked };
    if (checked.verdict === "confirm" && confirmed !== true && confirmed !== checked.token) {
      return { ok: false, gate: checked, needsConfirmation: true };
    }
    if (this.requireRehearsal && !this.rehearsal && this.port.emulator !== true) {
      return { ok: false, gate: checked, rolledBack: false,
        error: new SendError("rehearsal", "Jede Änderung geht erst durch den Emulator, und der läuft nicht. Starte ihn im Bereich Emulator und verbinde neu. Ans Gerät ging nichts.") };
    }
    if (this.rehearsal) {
      const probe = await this.rehearsal.rehearse(edit);
      // The emulator is scratch space: a failed probe must not block every later edit.
      if (this.rehearsal.blocked) this.rehearsal.carry = { ...newCarry(), history: this.rehearsal.history };
      if (!probe.ok) {
        return { ok: false, gate: checked, rehearsal: probe, rolledBack: false,
          error: new SendError("rehearsal", `Im Emulator nicht bestanden: ${probe.reason} Ans Gerät ging nichts.`) };
      }
    }
    const run = await this.sender.run(checked.steps, { onStep });
    unit.run = run;
    if (!run.ok && this.rehearsal && !UNTRACKED.has(edit.kind)) await this.rehearsal.undo().catch(() => {});   // keep the emulator in step with the device
    if (edit.kind === "exec") return this.finishExec(edit, checked, run, unit);
    const pattern = edit.kind === "patternSend" || edit.kind === "patternRestore";
    const backups = pattern ? null : backupsOf(run.results);
    const patternBackup = pattern ? (run.results.find(r => r.step.role === "backup")?.value ?? edit.backup ?? null) : null;

    if (run.ok) {
      for (const step of checked.steps) if (step.role === "write") this.twin.handle(step.msg);
      if (pattern) this.twin.pattern = Uint8Array.from(run.results.at(-1).value);
      if (!UNTRACKED.has(edit.kind)) this.history.push({ edit, backups, pattern: patternBackup });
      return { ok: true, gate: checked, backups, backup: patternBackup };
    }

    // A write that failed may still have arrived in part, so it counts.
    const wrote = checked.steps.slice(0, run.failedAt + 1).some(s => s.role === "write");
    if (!wrote) return { ok: false, gate: checked, error: run.error, rolledBack: false };

    if (edit.kind === "sites" && backups.length) {
      const rollback = await this.sender.run(plan({ kind: "restore", backups }, this.planState()));
      if (rollback.ok) return { ok: false, gate: checked, error: run.error, rolledBack: true };
    }
    const pending = await this.holdAfterFailure(edit, backups, patternBackup, run.error);
    return { ok: false, gate: checked, error: run.error, rolledBack: false, pending };
  }

  /** After a failed write that left something on the device: keep the backups, block the target until the user decides. */
  async holdAfterFailure(edit, backups, patternBackup, error) {
    const target = describeTarget(edit);
    this.carry.pending = { edit, backups, pattern: patternBackup, error: error.message, target };
    this.blocked = `${target}: ${error.message} Was angekommen ist, zeigt das Zurücklesen. Bis du entschieden hast (Sicherung zurückspielen oder so lassen), geht an dieses Gerät nichts mehr.`;
    if (!this.sender.disconnected) this.carry.pending.now = await this.readBack(this.carry.pending);
    return this.carry.pending;
  }

  /**
   * Code ran, or tried to: the bytes that were under the stub go back
   * whatever happened, as tools/device/led_show.py does in its finally
   * block. A short wait first, so a stub still running is not written under.
   * An exec is neither undone nor exported, so it leaves no history entry.
   */
  async finishExec(edit, checked, run, unit) {
    const wrote = run.ok || checked.steps.slice(0, run.failedAt + 1).some(s => s.role === "write");
    if (!wrote) return { ok: false, gate: checked, error: run.error, rolledBack: false };
    if (run.ok) for (const step of checked.steps) if (step.role === "write") this.twin.handle(step.msg);
    await sleep(this.execSettleMs ?? 200);
    const backups = backupsOf(run.results);
    const back = await this.restore({ backups });
    unit.cleanup = { steps: back.steps, ok: back.ok };
    if (back.ok) return run.ok ? { ok: true, gate: checked, backups: null } : { ok: false, gate: checked, error: run.error, rolledBack: true };
    const pending = await this.holdAfterFailure(edit, backups, null, back.error);
    return { ok: false, gate: checked, error: run.error ?? back.error, rolledBack: false, pending };
  }

  /**
   * Send what a rehearsal recorded, and nothing else (the terminal's way to
   * the device). Every unit passes the gate again with this device's
   * context before anything goes out, and the frames are the recorded ones
   * with only the channel byte changed. Reads the script made for itself
   * are not sent; they ran in the emulator and their values are its values.
   * The bytes put back under a stub are this device's own, read at replay.
   */
  replay(record, { onStep } = {}) {
    return this.exclusive(() => this.replayNow(record, { onStep }));
  }

  async replayNow(record, { onStep }) {
    const refuse = (code, message, extra = {}) => ({ ok: false, refused: true, error: new SendError(code, message), ...extra });
    if (!isPassed(record)) return refuse("not-rehearsed", "Das ist keine bestandene Probe im Emulator. Ans Gerät geht nichts.");
    const d = this.device;
    if (!d) return refuse("no-device", "Kein Gerät verbunden.");
    if (!d.versionKnown || !d.fingerprintVerified) return refuse("firmware", "Der Gerätestand ist nicht bestätigt: Die Firmware im Gerät ist nicht die, auf der die Probe lief.");
    if (d.version[0] !== record.target.version[0] || d.version[1] !== record.target.version[1]) {
      return refuse("firmware", `Das Gerät meldet ${d.version.join(".")}, die Probe lief auf ${record.target.version.join(".")}.`);
    }
    if (this.firmwareBytes && await sha256(this.firmwareBytes) !== record.target.firmwareSha) {
      return refuse("firmware", "Für das Gerät ist eine andere Firmware-Datei geladen als die, auf der die Probe lief.");
    }
    const channel = d.channel;
    const ctx = { ...this.context(), rehearsed: true };
    const prepared = [];
    for (const [n, unit] of record.units.entries()) {
      const steps = unit.steps.map(s => ({ ...s, msg: withChannel(s.msg, channel) }));
      const checked = await admit(unit.edit, steps, ctx);
      if (checked.verdict !== "clean") {
        const why = checked.reasons.map(r => r.message).join(" ") || "Der Türsteher will eine Bestätigung.";
        return refuse("gate", `Einheit ${n + 1}: ${why}`, { unit: n, gate: checked });
      }
      prepared.push({ unit, steps });
    }
    const results = [];
    for (const [n, { unit, steps }] of prepared.entries()) {
      const sameAck = (step, value, i) => {
        const want = unit.acks[i];
        if (step.expect.kind !== "ack" || !want) return null;
        const wanted = withChannel(want, channel);
        return wanted.length === value.length && wanted.every((b, k) => b === value[k]) ? null : "Die Bestätigung weicht von der in der Probe ab.";
      };
      const run = await this.sender.run(steps, { onStep: (i, total) => onStep?.({ unit: n, step: i, of: total, units: prepared.length }), check: sameAck });
      if (!run.ok) {
        const failure = { unit: n, step: run.failedAt + 1, error: run.error };
        const wrote = steps.slice(0, run.failedAt + 1).some(s => s.role === "write");
        let pending = null;
        if (wrote) {
          const backups = backupsOf(run.results);
          if (unit.edit.kind === "exec") {
            await sleep(this.execSettleMs ?? 200);
            const back = await this.restore({ backups });
            if (!back.ok) pending = await this.holdAfterFailure(unit.edit, backups, null, back.error);
          } else {
            pending = await this.holdAfterFailure(unit.edit, backups, null, run.error);
          }
        }
        return { ok: false, ...failure, pending, done: results };
      }
      for (const step of steps) if (step.role === "write") this.twin.handle(step.msg);
      const done = { unit: n, steps: steps.length };
      if (unit.cleanup) {
        await sleep(this.execSettleMs ?? 200);
        const back = await this.restore({ backups: backupsOf(run.results) });
        if (!back.ok || shapeOf(back.steps).join() !== shapeOf(unit.cleanup.steps).join()) {
          const error = back.error ?? new SendError("replay-mismatch", "Das Zurückschreiben hat nicht die Form wie in der Probe.");
          const pending = await this.holdAfterFailure(unit.edit, backupsOf(run.results), null, error);
          return { ok: false, unit: n, step: steps.length, error, pending, done: results };
        }
        done.restored = true;
      }
      results.push(done);
    }
    return { ok: true, done: results };
  }

  /** Whether the firmware still answers the device search. */
  alive() {
    return this.exclusive(() => this.sender.run(plan({ kind: "search" }))).then(r => r.ok, () => false);
  }

  /**
   * "red" or "blue": the Electribe on the cable, or null when it cannot be told. Korg's blue firmware answers the search
   * as model 0x23; Sampler code answers 0x24 on both, Hacktribe on the blue too, so then the user-data mark in the flash
   * at 0x220000 decides (KORGelec2USR blue, KORGele2sUSR red), read with Hacktribe's or BLECH's flash read.
   */
  hardware() {
    return this.exclusive(async () => {
      if (!this.device) return null;
      if (this.device.model === 0x23) return "blue";
      if (!this.device.hacktribe && !this.sender.blech?.flash) return null;
      const run = await this.sender.run(plan({ kind: "flashRead", addr: 0x220000, length: 12 }, { channel: this.device.channel }));
      if (!run.ok) return null;
      const mark = String.fromCharCode(...run.results[0].value);
      return { KORGelec2USR: "blue", KORGele2sUSR: "red" }[mark] ?? null;
    });
  }

  /**
   * The whole flash, read only, in blocks up to but never past P.FLASH_END.
   * Stops at the first block without an answer.
   */
  readFlash({ block = 0x4000, onProgress } = {}) {
    return this.exclusive(async () => {
      if (!this.device?.hacktribe && !this.sender.blech?.flash) throw new SendError("no-hacktribe", "Flash lesen geht nur mit Hacktribe oder BLECH.");
      const out = new Uint8Array(FLASH_END);
      for (let addr = 0; addr < FLASH_END; addr += block) {
        const run = await this.sender.run(plan({ kind: "flashRead", addr, length: Math.min(block, FLASH_END - addr) }, { channel: this.device.channel }));
        if (!run.ok) throw run.error;
        out.set(run.results[0].value, addr);
        onProgress?.(addr + block, FLASH_END);
      }
      return out;
    });
  }

  /**
   * Try an edit on this session's device (the emulator) before it goes to
   * the real one: it passes when it is read back intact and the firmware is
   * still running and answering afterwards (plan 5.2).
   */
  async rehearse(edit) {
    if (this.port.running === false) return { ok: false, reason: "Der Emulator läuft nicht." };
    const res = await this.apply(edit, { confirmed: true });
    if (!res.ok) {
      const why = res.error?.message ?? res.gate?.reasons?.map(r => r.message).join(" ") ?? "abgelehnt";
      return { ok: false, reason: why };
    }
    await new Promise(r => setTimeout(r, this.settleMs ?? 500));
    if (this.port.running === false) return { ok: false, reason: "Die Firmware im Emulator ist danach stehen geblieben (Absturz oder Assertion)." };
    const alive = await this.exclusive(() => this.sender.run(plan({ kind: "search" })));
    if (!alive.ok) {
      await this.undo().catch(() => {});              // the device does not get it, so the emulator should not keep it
      return { ok: false, reason: "Die Firmware im Emulator antwortet danach nicht mehr." };
    }
    return { ok: true };
  }

  /** The display image from RAM, 1024 bytes as the LCD takes them (plan 5.3). */
  readDisplay() {
    const display = BLOCKS.get("display");
    return this.exclusive(async () => {
      const run = await this.sender.run(plan({ kind: "readRam", addr: display.meta.ram, length: display.size }, { channel: this.device.channel }));
      if (!run.ok) throw run.error;
      return run.results[0].value;
    });
  }

  /** Read a stretch of RAM in blocks; only reads go out. */
  readRamBlock(addr, length, { chunk = 0x1000 } = {}) {
    return this.exclusive(async () => {
      const out = new Uint8Array(length);
      for (let at = 0; at < length; at += chunk) {
        const n = Math.min(chunk, length - at);
        const run = await this.sender.run(plan({ kind: "readRam", addr: addr + at, length: n }, { channel: this.device.channel }));
        if (!run.ok) throw run.error;
        out.set(run.results[0].value, at);
      }
      return out;
    });
  }

  /** Which screen, menu page, part and effect the device shows (src/screen.mjs). */
  screen() {
    return this.exclusive(() => readContext(async (addr, length) => {
      if (addr < RAM_BASE || addr + length > RAM_BASE + 0x8000000) throw new SendError("pointer", `Zeiger 0x${addr.toString(16)} zeigt nicht ins RAM; nicht gelesen.`);
      const run = await this.sender.run(plan({ kind: "readRam", addr, length }, { channel: this.device.channel }));
      if (!run.ok) throw run.error;
      return run.results[0].value;
    }));
  }

  /** The lit front LEDs, number to brightness (src/leds.mjs). One RAM read per call; the table's address is looked up the first time. */
  readLeds() {
    return this.exclusive(async () => {
      const res = await readLeds(async (addr, length) => {
        if (addr < RAM_BASE || addr + length > RAM_BASE + 0x8000000) throw new SendError("pointer", `Zeiger 0x${addr.toString(16)} zeigt nicht ins RAM; nicht gelesen.`);
        const run = await this.sender.run(plan({ kind: "readRam", addr, length }, { channel: this.device.channel }));
        if (!run.ok) throw run.error;
        return run.results[0].value;
      }, this.ledAt);
      this.ledAt = res.at;
      return res.leds;
    });
  }

  /** One RAM read, for code that decodes what it reads; inside `exclusive`, only reads go out. */
  ramReader() {
    return async (addr, length) => {
      if (addr < RAM_BASE || addr + length > RAM_BASE + 0x8000000) throw new SendError("pointer", `Adresse 0x${addr.toString(16)} liegt nicht im RAM; nicht gelesen.`);
      const run = await this.sender.run(plan({ kind: "readRam", addr, length }, { channel: this.device.channel }));
      if (!run.ok) throw run.error;
      return run.results[0].value;
    };
  }

  /** The names of all samples (src/samples.mjs). */
  readSampleNames(opts) { return this.exclusive(() => readSampleNames(this.ramReader(), opts)); }

  /** One sample's name, tune and measured facts; `index` is zero-based. */
  readSample(index) { return this.exclusive(() => readSample(this.ramReader(), index)); }

  /** Read what the target of a failed send holds now, and compare it with before and intended. */
  async readBack(pending) {
    const ch = this.device?.channel;
    if (ch == null) return null;
    const same = (a, b) => !!a && !!b && a.length === b.length && a.every((x, i) => x === b[i]);
    if (pending.pattern) {
      const run = await this.sender.run(plan({ kind: "patternFetch" }, { channel: ch }));
      if (!run.ok) return { ok: false, text: run.error.message };
      const now = run.results[0].value;
      const text = same(pending.pattern, now) ? "Im Puffer steht noch das alte Pattern."
        : same(pending.edit.block, now) ? "Das neue Pattern ist vollständig angekommen."
          : "Im Puffer steht weder das alte noch das neue Pattern.";
      return { ok: true, text };
    }
    const parts = new Set();
    for (const b of pending.backups) {
      const run = await this.sender.run(plan({ kind: "readRam", addr: b.addr, length: b.bytes.length }, { channel: ch }));
      if (!run.ok) return { ok: false, text: run.error.message };
      const now = run.results[0].value;
      const intended = pending.edit.kind === "sample" ? sampleWrites(pending.edit).find(w => w.addr === b.addr)?.bytes : pending.edit.bytes ?? pending.edit.code;
      parts.add(same(now, b.bytes) ? "alt" : same(now, intended) ? "neu" : "gemischt");
    }
    const text = parts.size === 1 && parts.has("alt") ? "Am Gerät steht noch der alte Stand."
      : parts.size === 1 && parts.has("neu") ? "Der neue Stand ist vollständig angekommen."
        : "Am Gerät steht ein Gemisch aus altem und neuem Stand.";
    return { ok: true, text };
  }

  /**
   * The user's decision after a failed send: put the backup back, or leave
   * the device as it is. Either way the target is free again afterwards.
   */
  resolve(choice) {
    return this.exclusive(async () => {
      const p = this.carry.pending;
      if (!p || choice === "keep") { this.carry.pending = null; this.blocked = null; return { ok: true }; }
      const res = await this.restore(p);
      if (res.ok) { this.carry.pending = null; this.blocked = null; }
      return res;
    });
  }

  /** Write a kept backup: RAM bytes or a pattern buffer. Region-checked like any write. */
  async restore({ backups, pattern }, { onStep } = {}) {
    const ch = this.device.channel;
    const steps = pattern ? plan({ kind: "patternRestore", block: pattern }, { channel: ch }) : plan({ kind: "restore", backups }, this.planState(ch));
    const regions = regionCheck(steps);
    if (regions.length) return { ok: false, error: new SendError("region", regions[0].message), steps };
    const run = await this.sender.run(steps, { onStep });
    if (!run.ok) return { ok: false, error: run.error, steps };
    for (const step of steps) if (step.role === "write") this.twin.handle(step.msg);
    if (pattern) this.twin.pattern = Uint8Array.from(pattern);
    return { ok: true, steps };
  }

  /** Fetch the pattern in the device's buffer, and let the twin know it. */
  fetchPattern() {
    return this.exclusive(async () => {
      const run = await this.sender.run(plan({ kind: "patternFetch" }, { channel: this.device.channel }));
      if (!run.ok) throw run.error;
      this.twin.pattern = Uint8Array.from(run.results[0].value);
      return run.results[0].value;
    });
  }

  /** Take back the last live change by writing its backup. A failed undo blocks like a failed send. */
  undo({ onStep } = {}) {
    return this.exclusive(async () => {
      if (this.blocked) return { ok: false, error: new SendError("blocked", this.blocked) };
      const last = this.history[this.history.length - 1];
      if (!last) return { ok: false, error: new SendError("empty", "Nichts zurückzunehmen.") };
      const res = await this.restore(last, { onStep });
      if (res.ok) {
        this.history.pop();
        if (this.rehearsal?.history.length) await this.rehearsal.undo().catch(() => {});
        return res;
      }
      const target = describeTarget(last.edit);
      this.carry.pending = { edit: { kind: "restore" }, backups: last.backups, pattern: last.pattern, error: res.error.message, target };
      this.blocked = `Zurücknehmen von ${target} ist abgebrochen (${res.error.message}). Bis du entschieden hast, geht an dieses Gerät nichts mehr.`;
      return res;
    });
  }
}

function describeTarget(edit) {
  if (edit.kind === "fxRecord") return `${edit.table === "ifx" ? "IFX" : "MFX"} ${edit.slot}`;
  if (edit.kind === "sites" || edit.kind === "immediate") return edit.fieldId;
  if (edit.kind === "sample") return `Sample ${edit.index + 1}`;
  if (edit.kind === "patternSend" || edit.kind === "patternRestore") return "Pattern-Puffer";
  if (edit.kind === "exec") return "Code im Stub-Puffer";
  return edit.kind;
}
