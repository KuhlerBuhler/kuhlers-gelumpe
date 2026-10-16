/**
 * The one session on the emulator's port that tries things there first: for
 * the effect editor's optional "Probe im Emulator" and for the terminal's
 * rehearsal, which cannot be switched off. A port has a single message
 * handler, so two sessions on it would take it from each other; both ask here.
 * It needs Hacktribe's SysEx commands; `unsupported()` gives the reason when the loaded firmware lacks them.
 */
import { DeviceSession, newCarry } from "../../src/session.mjs";

// Over emulated DIN a pattern takes about 6 s of device time; wall time can be more.
const TIMEOUTS = { read: 8000, ack: 8000, pattern: 30000 };

/**
 * @param {() => object | null} port the emulator's port, once the page has one
 * @param {() => string | null} [unsupported] why the loaded firmware cannot be probed, or null
 */
export function sharedProbe(port, unsupported = () => null) {
  let probe = null;
  let making = null;
  let seen = null;
  const get = () => {
    const emu = port();
    if (!emu?.running) return Promise.reject(new Error("Der Emulator läuft nicht. Starte ihn im Bereich Emulator."));
    const lack = unsupported();
    if (lack) return Promise.reject(new Error(lack));
    if (probe && probe.port === emu && seen === emu.generation && !probe.sender.disconnected) {
      if (!probe.listening) probe.listen();
      return Promise.resolve(probe);
    }
    making ??= (async () => {
      // A restarted firmware may not be the one the session met; meet it again, keeping the session the editor holds.
      if (!probe || probe.port !== emu || probe.sender.disconnected) {
        const carry = probe?.port === emu ? probe.carry : newCarry();
        probe = new DeviceSession({ port: emu, carry, timeouts: TIMEOUTS });
      }
      else probe.listen();
      await probe.connect();
      seen = emu.generation;
      return probe;
    })().finally(() => { making = null; });
    return making;
  };
  /** Current shared session, without connecting. */
  get.current = () => probe;
  return get;
}
