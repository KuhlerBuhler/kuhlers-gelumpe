/**
 * A rehearsed script: what the emulator did, recorded so that exactly that,
 * and nothing else, can be sent to the real device afterwards.
 *
 * The terminal runs a script against a session on the emulator. Every
 * attempt to change something (a "unit": one planned list of messages that
 * went through the gate) is recorded with the messages and the answers. A
 * script passes when no unit failed, the firmware is still running and
 * answering afterwards, and it did not restart. Only a passed script is
 * sealed. DeviceSession.replay() takes sealed records only, so there is no
 * way from the terminal to the device that does not lead through here.
 *
 * Pure of the page: no DOM, no MIDI of its own.
 */
import { describeMessage } from "./protocol.mjs";
import { sha256 } from "./firmware.mjs";

/** The emulator reports a hanging firmware only after this long without a panel message (tools/emu/server.py, HANG_S). */
export const HANG_REPORT_MS = 2000;

const hex = msg => Array.from(msg, b => b.toString(16).padStart(2, "0")).join("");
const sleep = ms => new Promise(r => setTimeout(r, ms));

const SEALED = new WeakMap();

/** What a record consists of: the script, the target, and every frame in order. A changed byte changes it. */
function fingerprint(record) {
  return JSON.stringify([
    record.code, record.target,
    record.units.map(u => [u.edit?.kind, u.steps.map(s => [hex(s.msg), s.role]), u.cleanup ? u.cleanup.steps.map(s => hex(s.msg)) : null, u.acks]),
  ]);
}

function seal(record) {
  SEALED.set(record, fingerprint(record));
  Object.freeze(record.units);
  return Object.freeze(record);
}

/** True only for a record that came out of rehearse() as passed and has not been touched since. */
export function isPassed(record) {
  try { return SEALED.has(record) && SEALED.get(record) === fingerprint(record); } catch { return false; }
}

const ROLE = { guard: "Firmware-Code prüfen", backup: "Sichern", write: "Schreiben", verify: "Zurücklesen und vergleichen", execute: "Ausführen", query: "Abfragen" };
const hexAddr = n => `0x${n.toString(16).toUpperCase()}`;

/** One planned message in words, for the list next to the send button. */
export function describeStep(step) {
  const d = describeMessage(step.msg);
  const where = d.addr != null ? ` ${hexAddr(d.addr)}${d.length ? `, ${d.length} Byte` : ""}` : step.target ? ` ${hexAddr(step.target.addr)}, ${step.target.length} Byte` : "";
  const what = d.kind === "write-data" ? "Schreiben, Daten" : d.kind === "write-address" ? "Schreiben, Adresse" : (ROLE[step.role] ?? step.role);
  return `${what}${what === "Schreiben, Daten" ? ` (${step.target?.length ?? d.length} Byte)` : where}`;
}

const EDIT = { screenWrite: "Display beschreiben", exec: "Code ausführen", fxRecord: "Effekt-Record schreiben", sites: "Feld schreiben", sample: "Sample-Name oder Tune schreiben" };

/** Units of a record as rows: a headline, and the messages under it. */
export function describeUnits(record) {
  return record.units.map((u, i) => ({
    ok: u.ok,
    title: `${i + 1}. ${EDIT[u.edit?.kind] ?? u.edit?.kind ?? "Einheit"}${u.edit?.kind === "exec" ? ` bei ${hexAddr(u.edit.at)}, ${u.edit.code.length} Byte` : ""}`,
    note: u.ok ? `${u.steps.length} Nachrichten${u.cleanup ? " und das Zurückschreiben" : ""}, alle bestätigt` : `nicht bestanden: ${u.error}`,
    steps: u.steps.map((s, k) => ({ text: describeStep(s), failed: !u.ok && u.failedAt === k })),
  }));
}

let counter = 0;

/**
 * Run a script against an emulator session and record it.
 *
 * @param {object} o
 * @param {string} o.code the script text; a later change to it means a new rehearsal
 * @param {import("./session.mjs").DeviceSession} o.session on the emulator
 * @param {object} o.port the emulator's port: `running`, and `generation` if it counts restarts
 * @param {(hooks: {press: (why: string) => void, read: () => void}) => object} o.korg builds the library the script sees
 * @param {(korg: object) => Promise<any>} o.run runs the script with that library
 * @returns {Promise<object>} the record; `sendable` and sealed only when it passed
 */
export async function rehearse({ code, session, port, korg, run, settleMs = 500, codeSettleMs = HANG_REPORT_MS + 500 }) {
  const record = { id: ++counter, code, ok: false, sendable: false, reason: null, whyNot: null, units: [], blockers: [], reads: 0, value: undefined, target: null };
  const stop = reason => { record.reason = reason; record.whyNot = reason; return record; };
  if (port.running === false) return stop("Der Emulator läuft nicht. Starte ihn im Bereich Emulator.");
  const generation = port.generation;
  const hooks = { press: why => record.blockers.push(why), read: () => { record.reads++; } };
  session.onUnit = unit => record.units.push(unit);
  let error = null;
  try { record.value = await run(korg(hooks)); } catch (e) { error = e; } finally { session.onUnit = null; }
  if (error) return stop(`Das Skript ist im Emulator gescheitert: ${error.message}`);
  const bad = record.units.findIndex(u => !u.ok);
  if (bad !== -1) return stop(`Einheit ${bad + 1} ist im Emulator nicht bestanden: ${record.units[bad].error}`);
  // A hang shows up only after the service's own timeout; code gets that long to prove it did not hang.
  const runsCode = record.units.some(u => u.steps.some(s => s.role === "execute"));
  await sleep(runsCode ? codeSettleMs : settleMs);
  if (port.running === false) return stop("Die Firmware im Emulator ist danach stehen geblieben (Absturz, Assertion oder Hänger).");
  if (port.generation !== generation) return stop("Die Firmware im Emulator hat danach neu gestartet.");
  if (!await session.alive()) return stop("Die Firmware im Emulator antwortet danach nicht mehr.");
  record.ok = true;
  if (!record.units.length) { record.whyNot = "Nichts zu senden: das Skript hat nur gelesen."; return record; }
  if (record.blockers.length) { record.whyNot = `Das Skript nutzt ${[...new Set(record.blockers)].join(", ")}; das gibt es am Gerät nicht.`; return record; }
  if (!session.firmwareBytes || !session.device) { record.whyNot = "Dem Emulator fehlt die Firmware-Datei oder die Gerätesuche."; return record; }
  record.target = { version: [...session.device.version], firmwareSha: await sha256(session.firmwareBytes) };
  record.sendable = true;
  return seal(record);
}
