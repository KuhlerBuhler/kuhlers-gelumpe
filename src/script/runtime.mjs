/**
 * The script runtime as the device will run it, on the JS VM: scripts are
 * loaded and started one by one, events queue in a ring, and a cycle runs
 * ready, a queue snapshot and frame. Each frame call has one deadline;
 * pending handlers survive an overrun. Only the faulty script is switched off.
 * Timers (korg.after, korg.every, korg.afterSteps) are checked at the start of each frame, as the frame hook does.
 */
import { BUDGET, LIMITS, ERROR, QUEUED_EVENTS, SCRIPT_ENTRY, SCRIPT_PHASE, EVENT_BY_NAME, STORE, SCRIPT_APPS, TIMERS } from "../../data/script/contract.mjs";
import { Script, ScriptFault } from "./vm.mjs";
import { decodeBlob, fail } from "./blob.mjs";
import { verifyParts } from "./verifier.mjs";
import { text, render } from "../text.mjs";
import { KEY_NAMES } from "../../data/script/names.mjs";

const KEY_EXIT = KEY_NAMES.find(n => n.name === "EXIT").value;

/** How many pages scripts may add to the device's menu. */
export const MENU_ITEMS = 12;

export class ScriptRuntime {
  /**
   * @param {object} [o]
   * @param {Record<string, Function>} [o.api] host functions by API name
   * @param {() => number} [o.now] milliseconds, for the frame budget
   * @param {number} [o.frameMs] all handlers of one frame together; going over ends the running script
   * @param {number} [o.handlerWarnMs] one handler over this is counted in the status, not stopped
   * @param {number} [o.fuel] fuel for one run of the body or one handler
   * @param {number} [o.varSlots] variable slots all scripts may use together
   * @param {number} [o.scriptBytes] bytes for blobs, variables and script entries together, at most BUDGET.scriptBytes
   * @param {{ load: (name: string) => { mask: number, values: ArrayLike<number> } | null, save: (records: { name: string, mask: number, values: Int32Array }[]) => void } | null} [o.storage]
   *   persistent values: `load` is asked when a script is added, `save` gets every script's record once `flushStore` runs
   * @param {() => number} [o.clock] milliseconds of the device clock the timers count in, by default korg.millis of `api`
   */
  constructor({ api = {}, now = () => performance.now(), frameMs = BUDGET.frameMs, handlerWarnMs = BUDGET.handlerWarnMs, fuel = LIMITS.fuel, varSlots = BUDGET.variableSlots, scriptBytes = BUDGET.scriptBytes, storage = null, clock = null } = {}) {
    if (!Number.isInteger(scriptBytes) || scriptBytes < 0 || scriptBytes > BUDGET.scriptBytes) throw new RangeError(`scriptBytes must be between 0 and ${BUDGET.scriptBytes}`);
    this.api = api;
    this.storage = storage;
    this.storePending = false;
    /** The menu pages scripts added with korg.menu.add, in the order they were added; an id is the index. */
    this.menus = [];
    /** korg.remapKey: the key `from` reaches the firmware and the scripts as `to` while `entry` is armed, else null. */
    this.remap = null;
    /** The apps scripts declared with korg.app, in the order they were declared; an id is the index. */
    this.apps = [];
    /** The script entry that owns the display (its app screen is open, or it took the display), or null. Only it draws. An app gets `frame` only while it is open. */
    this.open = null;
    /** Called with the entry when it becomes the owner of the display: the host clears the picture for it. */
    this.onOwn = null;
    this.now = now;
    this.clock = clock ?? (() => Math.floor(this.api["korg.millis"]?.() ?? now()));
    this.frameMs = frameMs;
    this.handlerWarnMs = handlerWarnMs;
    this.fuel = fuel;
    this.varSlots = varSlots;
    this.scriptBytes = scriptBytes;
    this.scripts = [];
    this.queue = [];
    this.overflows = 0;
    this.frames = 0;
    this.ready = false;
    this.cycle = null;
  }

  /** Variable slots of the scripts added so far. */
  get slotsUsed() { return this.scripts.reduce((n, e) => n + e.script.vars.length, 0); }

  /** Arena bytes held by every loaded script, including disabled ones. */
  get bytesUsed() { return this.scripts.reduce((n, e) => n + e.poolBytes, 0); }

  /** Load a blob and run its body. A fault in the load or the body leaves the script switched off, with the fault kept for `ready`. */
  add(bytes, { onStep } = {}) {
    const parts = decodeBlob(bytes);
    if (!parts.ok) return { ok: false, error: parts.error };
    const verified = verifyParts(parts);
    if (!verified.ok) return { ok: false, error: verified.error };
    const poolBytes = Math.ceil(parts.header.totalSize / 4) * 4 + parts.header.varCount * 4 + SCRIPT_ENTRY.size;
    const bytesFree = this.scriptBytes - this.bytesUsed;
    if (poolBytes > bytesFree) {
      return { ok: false, error: fail(ERROR.POOL_BUDGET, render(text("script.load.bytes", { name: parts.header.name, needed: poolBytes, free: bytesFree, total: this.scriptBytes }))) };
    }
    const free = this.varSlots - this.slotsUsed;
    if (parts.header.varCount > free) {
      const kib = n => `${Math.round((n * 4) / 102.4) / 10} KiB`;
      return { ok: false, error: fail(ERROR.VARS_BUDGET, render(text("script.load.slots", { name: parts.header.name, needed: parts.header.varCount, size: kib(parts.header.varCount), free, total: this.varSlots, totalSize: kib(this.varSlots) }))) };
    }
    const script = new Script(parts, verified.info);
    const entry = { script, poolBytes, readySent: false, onStep, maxCost: {}, maxMs: {}, warnings: 0, slowest: { event: null, ms: 0 }, store: { mask: 0, values: new Int32Array(STORE.slots) },
      timers: Array.from({ length: TIMERS.slots }, () => ({ kind: TIMERS.KIND.FREE, due: 0, period: 0, callback: 0, generation: 0 })) };
    const saved = this.storage?.load(parts.header.name);
    if (saved) { entry.store.mask = saved.mask >>> 0; entry.store.values.set(Array.from(saved.values).slice(0, STORE.slots)); }
    entry.api = this.#apiFor(entry);
    this.scripts.push(entry);
    const r = script.start(this.#env(entry, null));
    return { ok: r.ok, script, error: r.ok ? null : script.fault, index: this.scripts.length - 1 };
  }

  #apiFor(entry) {
    const api = Object.create(this.api);
    api["korg.store.get"] = (slot, fallback) => ((entry.store.mask >>> slot) & 1 ? entry.store.values[slot] : fallback);
    api["korg.store.set"] = (slot, value) => { entry.store.values[slot] = value | 0; entry.store.mask = (entry.store.mask | (1 << slot)) >>> 0; return 0; };
    api["korg.store.save"] = () => { this.storePending = true; return 0; };
    api["korg.menu.add"] = (label, min, max, value) => {
      if (min > max) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.menuRange")));
      const name = String(label).slice(0, LIMITS.nameLength);
      const known = this.menus.findIndex(m => m.entry === entry && m.label === name);
      if (known >= 0) return known;
      if (this.menus.length >= MENU_ITEMS) return -1;
      this.menus.push({ entry, script: entry.script.name, label: name, min, max, value: Math.min(max, Math.max(min, value)) });
      return this.menus.length - 1;
    };
    api["korg.after"] = (ms, callback) => this.#timerStart(entry, TIMERS.KIND.MS, (this.clock() + ms) | 0, 0, callback);
    api["korg.every"] = (ms, callback) => this.#timerStart(entry, TIMERS.KIND.MS, (this.clock() + ms) | 0, ms, callback);
    api["korg.afterSteps"] = (steps, callback) => this.#timerStart(entry, TIMERS.KIND.STEPS, steps, 0, callback);
    api["korg.cancel"] = id => {
      const t = id < 0 ? null : entry.timers[id % TIMERS.slots];
      if (t && t.kind !== TIMERS.KIND.FREE && t.generation === Math.floor(id / TIMERS.slots)) t.kind = TIMERS.KIND.FREE;
      return 0;
    };
    api["korg.remapKey"] = (from, to) => {
      if (from === KEY_EXIT || to === KEY_EXIT) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.remapExit")));
      this.remap = from === to ? null : { entry, from, to };
      return 0;
    };
    api["korg.app"] = (name, group) => {
      const known = this.apps.findIndex(a => a.entry === entry);
      if (known >= 0) return known;
      if (!SCRIPT_APPS.groups.includes(group)) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.appGroup")));
      const label = String(name).slice(0, SCRIPT_APPS.nameLength);
      if (!label) throw new ScriptFault(ERROR.API_ARG, render(text("script.fault.appName")));
      if (this.apps.length >= SCRIPT_APPS.max) return -1;
      this.apps.push({ entry, script: entry.script.name, name: label, group });
      return this.apps.length - 1;
    };
    // Drawing is taken from the owner of the display only (the open app, or a plugin that took it); any other script's drawing calls do nothing.
    for (const name of Object.keys(this.api)) {
      if (name.startsWith("korg.display.")) api[name] = (...args) => (this.open === entry ? this.api[name](...args) : 0);
    }
    api["korg.display.take"] = () => {
      if (this.open === entry) return 1;
      if (this.open || this.apps.some(a => a.entry === entry)) return 0;
      this.open = entry;
      this.onOwn?.(entry);
      return 1;
    };
    api["korg.display.release"] = () => {
      if (this.open === entry) this.open = null;
      return 0;
    };
    return api;
  }

  /** Takes a free timer slot of the script: its number (slot plus 8 times the slot's generation), or -1 when all are taken. */
  #timerStart(entry, kind, due, period, callback) {
    const slot = entry.timers.findIndex(t => t.kind === TIMERS.KIND.FREE);
    if (slot < 0) return -1;
    const t = entry.timers[slot];
    Object.assign(t, { kind, due, period, callback, generation: (t.generation + 1) % 32 });
    return slot + TIMERS.slots * t.generation;
  }

  /** The clock timers that are due go into the ring for their script; a full ring leaves them due for the next frame. */
  #timersDue() {
    if (!this.scripts.some(e => e.timers.some(t => t.kind === TIMERS.KIND.MS))) return;
    const now = this.clock();
    for (const entry of this.scripts) {
      if (entry.script.state !== "armed") continue;
      for (const t of entry.timers) {
        if (t.kind !== TIMERS.KIND.MS || ((now - t.due) | 0) < 0) continue;
        if (!this.#postTimer(entry, t)) return;
        if (!t.period) { t.kind = TIMERS.KIND.FREE; continue; }
        t.due = (t.due + t.period) | 0;
        if (((now - t.due) | 0) >= 0) t.due = (now + t.period) | 0;
      }
    }
  }

  /** A step came: every step timer counts it, and the ones that reach 0 go into the ring. */
  #timersStep() {
    for (const entry of this.scripts) {
      if (entry.script.state !== "armed") continue;
      for (const t of entry.timers) {
        if (t.kind !== TIMERS.KIND.STEPS || --t.due > 0) continue;
        if (this.#postTimer(entry, t)) t.kind = TIMERS.KIND.FREE;
        else t.due = 1;
      }
    }
  }

  #postTimer(entry, t) {
    if (this.queue.length >= BUDGET.ring) { this.overflows += 1; return false; }
    this.queue.push({ name: "timer", args: [t.callback], target: entry });
    return true;
  }

  /** The apps in the order of the BLECH menu: GAMES first, then TOOLS, each in the order they were declared. */
  get appList() {
    return SCRIPT_APPS.groups.flatMap(group => this.apps.flatMap((a, id) => (a.group === group
      ? [{ id, script: a.script, name: a.name, group, state: a.entry.script.state, open: this.open === a.entry }] : [])));
  }

  /** The user opens an app from the menu: it owns the display, gets `open`, and `frame` from now on. Returns whether it opened. */
  openApp(id) {
    const app = this.apps[id];
    if (!app || app.entry.script.state !== "armed") return false;
    if (this.open) this.closeApp();
    this.open = app.entry;
    this.onOwn?.(app.entry);
    this.#postTo(app.entry, "open");
    return true;
  }

  /** The user leaves the app or ends a takeover (EXIT, or the screen is gone): it gets `close` and the display is the device's again. */
  closeApp() {
    if (!this.open) return false;
    const entry = this.open;
    this.open = null;
    this.#postTo(entry, "close");
    return true;
  }

  /** An app event goes to one script only and does not merge with anything. */
  #postTo(entry, name) {
    if (this.queue.length >= BUDGET.ring) { this.overflows += 1; return false; }
    this.queue.push({ name, args: [], target: entry });
    return true;
  }

  /** Hand every script's record to the storage when a script asked to save; the host picks the moment. Returns whether it wrote. */
  flushStore() {
    if (!this.storePending || !this.storage) return false;
    this.storePending = false;
    this.storage.save(this.scripts.map(e => ({ name: e.script.name, mask: e.store.mask, values: Int32Array.from(e.store.values) })));
    return true;
  }

  #env(entry, deadline) {
    return { api: entry.api, fuel: this.fuel, onStep: entry.onStep, timeUp: deadline === null ? undefined : () => this.now() > deadline };
  }

  /** The user turns a page a script added: the value moves within its range and the script gets `menu`(id, value). Returns the new value, or null for an id that does not exist. */
  /** The key code an input of `key` arrives as, after korg.remapKey. */
  remapped(key) {
    const r = this.remap;
    return r && r.from === key && r.entry.script.state === "armed" && this.scripts.includes(r.entry) ? r.to : key;
  }

  menuSet(id, value) {
    const item = this.menus[id];
    if (!item) return null;
    const next = Math.min(item.max, Math.max(item.min, value | 0));
    if (next !== item.value) { item.value = next; this.post("menu", id, next); }
    return next;
  }

  /** Queue an event from outside. A full ring drops the new event and counts it; a knob turned again right after itself keeps only the last value. */
  post(name, ...args) {
    if (!QUEUED_EVENTS.includes(name)) throw new Error(`${name} cannot be posted`);
    const last = this.queue.at(-1);
    if (name === "knob" && last?.name === "knob" && last.args[0] === args[0]) { last.args = args; return true; }
    if (this.queue.length >= BUDGET.ring) { this.overflows += 1; return false; }
    this.queue.push({ name, args });
    if (name === "step") this.#timersStep();
    return true;
  }

  /** A cycle runs ready, a queue snapshot and frame; a timed-out handler leaves the remainder for the next call. */
  frame({ ready = true } = {}) {
    this.frames += 1;
    this.ready ||= ready;
    if (!this.ready) return { handled: 0, faults: [], ms: 0, queued: 0 };
    this.#timersDue();
    const t0 = this.now();
    const deadline = t0 + this.frameMs;
    const faults = [];
    let handled = 0;
    let queued = 0;
    const cycle = this.cycle ??= { phase: SCRIPT_PHASE.READY, next: 0, event: null, remaining: 0 };
    for (;;) {
      let event;
      if (cycle.phase === SCRIPT_PHASE.READY) {
        if (cycle.next >= this.scripts.length) {
          cycle.phase = SCRIPT_PHASE.QUEUED;
          cycle.next = 0;
          cycle.remaining = this.queue.length;
          continue;
        }
        event = { name: "ready", args: [] };
      } else if (cycle.phase === SCRIPT_PHASE.QUEUED) {
        if (cycle.event && cycle.next >= this.scripts.length) cycle.event = null;
        if (!cycle.event) {
          if (cycle.remaining === 0) {
            cycle.phase = SCRIPT_PHASE.FRAME;
            cycle.next = 0;
            continue;
          }
          cycle.event = this.queue.shift();
          cycle.remaining -= 1;
          cycle.next = 0;
          queued += 1;
        }
        event = cycle.event;
      } else {
        if (cycle.next >= this.scripts.length) { this.cycle = null; break; }
        event = { name: "frame", args: [] };
      }
      const entry = this.scripts[cycle.next++];
      if (entry.script.state !== "armed") continue;
      if (cycle.phase === SCRIPT_PHASE.READY ? entry.readySent : !entry.readySent) continue;
      const { name, args } = event;
      if (event.target && event.target !== entry) continue;
      if (name === "frame" && this.open !== entry && this.apps.some(a => a.entry === entry)) continue;
      const hasHandler = entry.script.handlers.has(EVENT_BY_NAME.get(name).id);
      if (!hasHandler) {
        if (cycle.phase === SCRIPT_PHASE.READY) entry.readySent = true;
        continue;
      }
      if (this.now() > deadline) { cycle.next -= 1; break; }
      if (cycle.phase === SCRIPT_PHASE.READY) entry.readySent = true;
      const t = this.now();
      const r = entry.script.dispatch(name, args, this.#env(entry, deadline));
      handled += 1;
      const ms = this.now() - t;
      entry.maxCost[name] = Math.max(entry.maxCost[name] ?? 0, r.cost);
      entry.maxMs[name] = Math.max(entry.maxMs[name] ?? 0, ms);
      if (ms > this.handlerWarnMs) {
        entry.warnings += 1;
        if (ms > entry.slowest.ms) entry.slowest = { event: name, ms };
      }
      if (!r.ok) faults.push({ script: entry.script.name, ...entry.script.fault });
      if (r.code === ERROR.TIME) break;
    }
    return { handled, faults, ms: this.now() - t0, queued };
  }

  /** What the status block on the device will hold: per script its state and last fault, the cost of its biggest handler per event, slow handlers; plus the ring overflows. */
  status() {
    return {
      frames: this.frames,
      slots: { used: this.slotsUsed, budget: this.varSlots },
      memory: { used: this.bytesUsed, budget: this.scriptBytes },
      overflows: this.overflows,
      scripts: this.scripts.map(e => ({
        name: e.script.name,
        state: e.script.state,
        fault: e.script.fault,
        maxCost: { ...e.maxCost },
        maxMs: { ...e.maxMs },
        slowHandlers: e.warnings,
        slowest: { ...e.slowest },
      })),
    };
  }
}
