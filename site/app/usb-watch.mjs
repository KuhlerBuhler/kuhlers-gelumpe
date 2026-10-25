import { electribePorts } from "../../src/session.mjs";

/**
 * Whether an Electribe is on the USB port right now: "present", "absent", "connected" (a session is open) or
 * "unknown" (the browser has not granted MIDI yet, or listing failed).
 * Native MIDI (Mac, Linux) lists the ports on a short timer. Web MIDI (Windows) holds one access object and is told
 * by its `statechange`, the timer only backs it up.
 */
export function createUsbWatch({ transport, permissions = null, every = 2000, hidden = () => false, timers = globalThis } = {}) {
  let state = "unknown";
  let access = null;
  let attached = null;
  let connected = false;
  let timer = null;
  let running = false;
  let again = false;
  const subscribers = new Set();
  const set = next => {
    if (next === state) return;
    state = next;
    for (const fn of subscribers) fn(state);
  };

  async function granted() {
    if (transport.native) return true;
    if (!permissions?.query) return false;
    try { return (await permissions.query({ name: "midi", sysex: true })).state === "granted"; } catch { return false; }
  }

  async function check() {
    if (connected) { set("connected"); return; }
    if (running) { again = true; return; }
    running = true;
    try {
      do {
        again = false;
        if (!transport.supported || !(await granted())) { access = attached = null; set("unknown"); continue; }
        if (transport.native || !access) access = await transport.requestAccess();
        if (!transport.native && attached !== access) {
          attached = access;
          access.addEventListener?.("statechange", check);
        }
        if (!connected) set(electribePorts(access).length ? "present" : "absent");
      } while (again);
    } catch {
      access = attached = null;
      set("unknown");
    } finally { running = false; }
  }

  return {
    get state() { return state; },
    subscribe(fn) { subscribers.add(fn); fn(state); return () => subscribers.delete(fn); },
    check,
    /** A session on the device is open: the port is in use, so the list is not asked. Closing it asks again at once. */
    setConnected(on) {
      connected = on;
      if (on) set("connected"); else check();
    },
    start() {
      if (timer) return;
      check();
      timer = timers.setInterval(() => { if (!hidden() && !connected) check(); }, every);
    },
    stop() { timers.clearInterval(timer); timer = null; },
  };
}
