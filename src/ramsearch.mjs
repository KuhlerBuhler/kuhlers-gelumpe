/**
 * Research help for unknown RAM (idea 11): snapshots, a comparison of two of them, and a search,
 * all of which leave out what is already explained.
 *
 * Reads only. Every read is one `read(addr, length)` call, which is how the terminal's
 * KORG.ram.read goes through the session, the sender and the protected list (src/protect.mjs):
 * no flash, no ports, RAM only inside the measured window. The range is checked against that rule
 * once up front so a refusal comes before the first read and not halfway through. A big range is
 * read in chunks, one after the other, each waiting for its answer.
 *
 * What counts as known is in data/known-ram.mjs: the device map down to the field, the memory
 * map and the protected list. By default a stretch that is entirely known is not read at all, and
 * a byte that is known is not reported. The mask belongs to the library and not to the reader, so
 * a session on the emulator and one on a device give the same answers for the same memory.
 *
 * Pure of the page and of node: no DOM, no MIDI, no `node:` imports.
 */
import { BLOCKS, TABLES, byteSpans, isUnknown } from "./map/index.mjs";
import { fileToRam, CURRENT_PATTERN } from "./map/address.mjs";
import { refusal, RAM_WINDOW } from "./protect.mjs";
import PROTECTED from "../data/protected.mjs";
import EXEC from "../data/exec.mjs";
import { GROUPS, FROM_PROTECTED, NOT_READ, AREAS, PATTERN_SLOTS } from "../data/known-ram.mjs";

export { GROUPS };

const hex = n => `0x${n.toString(16).toUpperCase()}`;
const bytesText = n => `${n} Byte`;
const hexBytes = (bytes, max = 8) => `${Array.from(bytes.subarray(0, max), b => b.toString(16).padStart(2, "0")).join(" ")}${bytes.length > max ? " ..." : ""}`;

/** The most a single read may carry: what KORG.ram.read allows. */
export const MAX_CHUNK = 0x4000;
export const DEFAULTS = { chunk: 0x1000, limit: 0x400000, maxMatches: 1000, maxLines: 25 };

/** Which bytes of one block the map explains: a field that nobody understands yet stays unflagged. */
const maskCache = new Map();
function blockMask(name) {
  let mask = maskCache.get(name);
  if (!mask) {
    const block = BLOCKS.get(name);
    mask = new Uint8Array(block.size);
    for (const f of block.fields) {
      if (isUnknown(f)) continue;
      for (const [from, to] of byteSpans(f)) mask.fill(1, Math.min(from, block.size), Math.min(to, block.size));
    }
    maskCache.set(name, mask);
  }
  return mask;
}

/** Every known region of CPU RAM, from the three sources in data/known-ram.mjs. */
function buildRegions() {
  const out = [];
  const add = r => out.push({ group: "area", explained: false, mask: null, ...r });

  for (const p of PROTECTED.regions) {
    if (p.space !== "ram" || NOT_READ.includes(p.id)) continue;
    const how = FROM_PROTECTED[p.id];
    if (!how) throw new Error(`data/known-ram.mjs does not classify the protected region ${p.id}`);
    add({ start: p.start, end: p.end, what: p.what, ...how });
  }
  for (const a of AREAS) add(a);
  add({ start: EXEC.stubAt, end: EXEC.stubAt + EXEC.stubSize, what: "Stub-Puffer" });

  const label = block => BLOCKS.get(block).label.de;
  const entries = (start, count, stride, size, what, block, group = "map") => {
    for (let i = 0; i < count; i++) {
      add({ start: start + i * stride, end: start + i * stride + size, what: count > 1 ? `${what} ${i + 1}` : what, group, explained: true, mask: blockMask(block) });
    }
  };
  for (const t of TABLES.values()) entries(fileToRam(t.file), t.count, t.stride, t.length ?? BLOCKS.get(t.block).size, t.label.de, t.block);
  for (const [name, block] of BLOCKS) {
    const { table, ram, pointer } = block.meta;
    if (table) entries(table.ram, table.count, table.stride, block.size, block.label.de, name);
    if (typeof ram === "number") entries(ram, 1, block.size, block.size, block.label.de, name);
    if (pointer && !out.some(r => r.start === pointer.at && r.end === pointer.at + 4)) {
      add({ start: pointer.at, end: pointer.at + 4, what: `Zeiger: ${label(name)}`, group: "map", explained: true });
    }
  }
  add({ start: CURRENT_PATTERN.at, end: CURRENT_PATTERN.at + 4, what: "Zeiger: bearbeitetes Pattern", group: "map", explained: true });
  const slots = PATTERN_SLOTS;
  entries(slots.start, slots.count, slots.stride, slots.stride, slots.what, slots.block, slots.group);
  return out;
}

export class KnownRam {
  constructor(regions = buildRegions()) {
    this.regions = regions.slice().sort((a, b) => a.start - b.start || b.end - a.end);
    let top = -Infinity;
    this.reach = this.regions.map(r => (top = Math.max(top, r.end)));
  }

  /** One byte per address of [from, to): 1 where something explains it, unless its group is in `show`. */
  hidden(from, to, show = []) {
    const out = new Uint8Array(to - from);
    let lo = 0;
    let hi = this.regions.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.reach[mid] > from) hi = mid; else lo = mid + 1;
    }
    for (let i = lo; i < this.regions.length; i++) {
      const r = this.regions[i];
      if (r.start >= to) break;
      if (!r.explained || r.end <= from || show.includes(r.group)) continue;
      const a = Math.max(from, r.start);
      const b = Math.min(to, r.end);
      if (!r.mask) { out.fill(1, a - from, b - from); continue; }
      for (let x = a; x < b; x++) if (r.mask[x - r.start]) out[x - from] = 1;
    }
    return out;
  }

  /** What is around [addr, addr + length): the smallest region that holds it or touches it, else the nearest ones on either side. */
  around(addr, length = 1) {
    const end = addr + length;
    const mirror = PROTECTED.ram.mirror.distance;
    const mirrored = addr >= RAM_WINDOW.start + mirror && end <= RAM_WINDOW.end;
    const a = mirrored ? addr - mirror : addr;
    const b = a + length;
    const smaller = (x, y) => (!x || y.end - y.start < x.end - x.start ? y : x);
    let within = null;
    let touches = null;
    let before = null;
    let after = null;
    for (const r of this.regions) {
      if (r.start <= a && r.end >= b) within = smaller(within, r);
      else if (r.start < b && r.end > a) touches = smaller(touches, r);
      else if (r.end <= a && (!before || r.end > before.end || (r.end === before.end && smaller(before, r) === r))) before = r;
      else if (r.start >= b && (!after || r.start < after.start || (r.start === after.start && smaller(after, r) === r))) after = r;
    }
    return { mirrored, within, touches, before, after, at: a, end: b };
  }

  /** `around` in words. */
  describe(addr, length = 1) {
    const d = this.around(addr, length);
    const via = d.mirrored ? "im vermuteten Spiegel: " : "";
    if (d.within) return `${via}in ${d.within.what} (+${hex(d.at - d.within.start)})`;
    if (d.touches) return `${via}an ${d.touches.what} (${hex(d.touches.start)} bis ${hex(d.touches.end)})`;
    const gap = n => (n === 0 ? "direkt" : `${hex(n)} Byte`);
    const parts = [];
    if (d.before) parts.push(`${gap(d.at - d.before.end)} hinter ${d.before.what}`);
    if (d.after) parts.push(`${gap(d.after.start - d.end)} vor ${d.after.what}`);
    return `${via}${parts.join(", ") || "nichts Bekanntes in der Nähe"}`;
  }
}

let known = null;
/** The known regions, built on first use. */
export const knownRam = () => (known ??= new KnownRam());

/** A range of memory held by value, with the stretches that were actually read. */
export class Snapshot {
  constructor({ from, to, data, spans, mask, show, read, skipped }) {
    Object.assign(this, { from, to, data, spans, mask, show, read, skipped });
  }

  /** The bytes at [addr, addr + length), or null where this snapshot did not read them. */
  bytes(addr, length) {
    if (!this.spans.some(([a, b]) => addr >= a && addr + length <= b)) return null;
    return this.data.subarray(addr - this.from, addr - this.from + length);
  }

  summary() {
    const hid = this.mask ? `, ${bytesText(this.skipped)} bekannt und nicht gelesen` : "";
    return `Snapshot ${hex(this.from)} bis ${hex(this.to)}: ${bytesText(this.read)} gelesen${hid}.`;
  }

  toJSON() { return { from: this.from, to: this.to, read: this.read, skipped: this.skipped, spans: this.spans.length }; }
}

export class DiffResult {
  constructor(o, regions) {
    Object.assign(this, o);
    Object.defineProperty(this, "regions", { value: regions });
  }

  /** Where a run sits, in words. */
  near(run) { return this.regions.describe(run.from, run.length); }

  summary({ max = DEFAULTS.maxLines } = {}) {
    const head = `Vergleich ${hex(this.from)} bis ${hex(this.to)}: ${bytesText(this.changed)} von ${this.compared} verglichenen Byte geändert, in ${this.runs.length} ${this.runs.length === 1 ? "Lauf" : "Läufen"}.`
      + `${this.hiddenBytes ? ` ${bytesText(this.hiddenBytes)} bekannt und ausgeblendet.` : ""}`
      + `${this.notCompared ? ` ${bytesText(this.notCompared)} nicht in beiden Snapshots.` : ""}`;
    const lines = this.runs.slice(0, max).map(r =>
      `  ${hex(r.from)} bis ${hex(r.to)}  ${bytesText(r.length)}  ${hexBytes(r.before)} -> ${hexBytes(r.after)}  ${this.near(r)}`);
    if (this.runs.length > max) lines.push(`  und ${this.runs.length - max} weitere Läufe`);
    return [head, ...lines].join("\n");
  }

  toJSON() { return { from: this.from, to: this.to, changed: this.changed, compared: this.compared, hiddenBytes: this.hiddenBytes, notCompared: this.notCompared, runs: this.runs.length }; }
}

export class SearchResult {
  constructor(o, regions) {
    Object.assign(this, o);
    Object.defineProperty(this, "regions", { value: regions });
  }

  near(match) { return this.regions.describe(match.addr, this.needle.length); }

  summary({ max = DEFAULTS.maxLines } = {}) {
    const n = this.matches.length;
    const head = `Suche nach ${bytesText(this.needle.length)} (${hexBytes(this.needle, 16)}) von ${hex(this.from)} bis ${hex(this.to)}: ${n} Treffer`
      + `${this.truncated ? " (Suche bei der Obergrenze gestoppt)" : ""}.`
      + ` ${bytesText(this.read)} gelesen${this.skipped ? `, ${bytesText(this.skipped)} bekannt und nicht gelesen` : ""}`
      + `${this.hiddenMatches ? `, ${this.hiddenMatches} Treffer in Bekanntem ausgeblendet` : ""}.`;
    const lines = this.matches.slice(0, max).map(m => `  ${hex(m.addr)}  ${this.near(m)}`);
    if (n > max) lines.push(`  und ${n - max} weitere Treffer`);
    return [head, ...lines].join("\n");
  }

  toJSON() { return { needle: hexBytes(this.needle, 16), from: this.from, to: this.to, matches: this.matches.map(m => m.addr), read: this.read, skipped: this.skipped, hiddenMatches: this.hiddenMatches, truncated: this.truncated }; }
}

/** A value, bytes or text as the bytes to look for. A number is a 32 bit word, little endian, unless `width` says 1 or 2. */
export function needleBytes(value, { width = 4 } = {}) {
  if (typeof value === "number") {
    if (![1, 2, 4].includes(width)) throw new RangeError("width ist 1, 2 oder 4");
    const top = 2 ** (8 * width);
    if (!Number.isInteger(value) || value < -top / 2 || value >= top) throw new RangeError(`${value} passt nicht in ${width} Byte`);
    const word = value < 0 ? value + top : value;
    return Uint8Array.from({ length: width }, (_, i) => Math.floor(word / 256 ** i) % 256);
  }
  if (typeof value === "string") {
    if (!value.length || [...value].some(c => c.charCodeAt(0) > 0xff)) throw new TypeError("Text, der gesucht wird, besteht aus Zeichen bis 0xFF");
    return Uint8Array.from(value, c => c.charCodeAt(0));
  }
  if (value instanceof Uint8Array || (Array.isArray(value) && value.every(b => Number.isInteger(b) && b >= 0 && b <= 0xff))) {
    if (!value.length) throw new RangeError("Es gibt nichts zu suchen");
    return Uint8Array.from(value);
  }
  throw new TypeError("search nimmt eine Zahl, einen Text, eine Uint8Array oder ein Array aus Bytes");
}

const sleepFor = ms => new Promise(r => setTimeout(r, ms));

/** Progress lines for a run: one at the start and then one for each tenth. */
export function progressPrinter(print, { from, to, chunk, mask }) {
  const blocks = Math.ceil((to - from) / chunk);
  print(`Lese ${hex(from)} bis ${hex(to)} in ${blocks} ${blocks === 1 ? "Block" : "Blöcken"} zu ${bytesText(chunk)}${mask ? ", Bekanntes wird übersprungen" : ""}.`);
  let shown = 0;
  return ({ done, total, read, skipped, addr }) => {
    const tenth = Math.floor((done / total) * 10);
    if (tenth > shown && done < total) {
      shown = tenth;
      print(`  ${tenth * 10} %: bis ${hex(addr)}, ${bytesText(read)} gelesen, ${bytesText(skipped)} übersprungen`);
    }
  };
}

/**
 * @param {object} o
 * @param {(addr: number, length: number) => Promise<Uint8Array | number[]>} o.read one read of at most MAX_CHUNK bytes
 * @param {(text: string) => void} [o.print] where progress goes; without it a run is silent
 * @param {(ms: number) => Promise<void>} [o.sleep] for `pauseMs`, replaceable in tests
 * @param {KnownRam} [o.regions]
 */
export function ramTools({ read, print = null, sleep = sleepFor, regions = knownRam() }) {
  /** `(from, to, opts)` or `({ from, to, ...opts })` or `({ from, length })`, checked. */
  function parse(args, what) {
    const [first, second, third] = args;
    const opts = first !== null && typeof first === "object" ? { ...first } : { ...(third ?? {}), from: first, to: second };
    if (opts.to === undefined && opts.length !== undefined) opts.to = opts.from + opts.length;
    const { from, to } = opts;
    if (!Number.isInteger(from) || !Number.isInteger(to) || to <= from) throw new RangeError(`${what}: from und to angeben, to ist das Ende ohne das Byte selbst (${what}({ from: 0xC0300000, to: 0xC0340000 }))`);
    const o = { mask: true, show: [], chunk: DEFAULTS.chunk, limit: DEFAULTS.limit, pauseMs: 0, progress: true, ...opts };
    if (!Number.isInteger(o.chunk) || o.chunk < 1 || o.chunk > MAX_CHUNK) throw new RangeError(`chunk ist 1 bis ${MAX_CHUNK}`);
    if (to - from > o.limit) throw new RangeError(`${what}: ${bytesText(to - from)} sind mehr als limit (${bytesText(o.limit)}). Den Bereich kleiner wählen oder limit erhöhen, das Fenster hat ${bytesText(RAM_WINDOW.end - RAM_WINDOW.start)}.`);
    const bad = o.show.filter(g => !(g in GROUPS));
    if (bad.length) throw new RangeError(`show kennt ${Object.keys(GROUPS).join(", ")}, nicht ${bad.join(", ")}`);
    return o;
  }

  /** The same rule the sender applies, asked once for the whole range, so a refusal comes before the first read. */
  function readable(from, to) {
    const r = refusal({ space: "ram", op: "read", addr: from, length: to - from });
    if (r) throw new Error(r.message);
  }

  const reporter = (o) => (typeof o.progress === "function" ? o.progress : o.progress && print ? progressPrinter(print, o) : null);

  /**
   * Go over [from, to) in chunks. A chunk that is known all through, with `margin` bytes around it,
   * is not read. `onRead(addr, bytes)` gets every chunk that is.
   */
  async function sweep(o, margin, onRead, stop = () => false) {
    const { from, to, chunk } = o;
    const total = to - from;
    const report = reporter(o);
    let done = 0;
    let readBytes = 0;
    let skipped = 0;
    for (let at = from; at < to && !stop(); at += chunk) {
      const n = Math.min(chunk, to - at);
      const lo = Math.max(from, at - margin);
      const hi = Math.min(to, at + n + margin);
      if (o.mask && regions.hidden(lo, hi, o.show).every(Boolean)) {
        skipped += n;
      } else {
        const got = await read(at, n);
        if (got.length !== n) throw new Error(`Gelesen: ${got.length} Byte statt ${n} bei ${hex(at)}.`);
        onRead(at, got instanceof Uint8Array ? got : Uint8Array.from(got));
        readBytes += n;
        if (o.pauseMs) await sleep(o.pauseMs);
      }
      done += n;
      report?.({ addr: at + n, done, total, read: readBytes, skipped });
    }
    return { read: readBytes, skipped };
  }

  async function snapshot(...args) {
    const o = parse(args, "snapshot");
    readable(o.from, o.to);
    const data = new Uint8Array(o.to - o.from);
    const spans = [];
    const { read: got, skipped } = await sweep(o, 0, (at, bytes) => {
      data.set(bytes, at - o.from);
      const last = spans.at(-1);
      if (last && last[1] === at) last[1] = at + bytes.length; else spans.push([at, at + bytes.length]);
    });
    return new Snapshot({ from: o.from, to: o.to, data, spans, mask: o.mask, show: o.show, read: got, skipped });
  }

  function diff(a, b, opts = {}) {
    if (!(a instanceof Snapshot) || !(b instanceof Snapshot)) throw new TypeError("diff nimmt zwei Snapshots aus KORG.ram.snapshot");
    const { mask = true, show = [], gap = 0 } = opts;
    const bad = show.filter(g => !(g in GROUPS));
    if (bad.length) throw new RangeError(`show kennt ${Object.keys(GROUPS).join(", ")}, nicht ${bad.join(", ")}`);
    const from = Math.max(a.from, b.from);
    const to = Math.min(a.to, b.to);
    if (from >= to) throw new RangeError("Die beiden Snapshots überlappen sich nicht");
    const common = [];
    for (const [s1, e1] of a.spans) for (const [s2, e2] of b.spans) {
      const s = Math.max(s1, s2, from);
      const e = Math.min(e1, e2, to);
      if (s < e) common.push([s, e]);
    }
    const runs = [];
    let changed = 0;
    let compared = 0;
    let hiddenBytes = 0;
    let notCompared = 0;
    let open = null;
    let lastChange = -Infinity;
    const close = () => {
      if (!open) return;
      open.length = open.to - open.from;
      open.before = a.data.subarray(open.from - a.from, open.to - a.from);
      open.after = b.data.subarray(open.from - b.from, open.to - b.from);
      runs.push(open);
      open = null;
    };
    const PIECE = 0x10000;
    for (let p = from; p < to; p += PIECE) {
      const q = Math.min(to, p + PIECE);
      const hid = mask ? regions.hidden(p, q, show) : null;
      const held = new Uint8Array(q - p);
      for (const [s, e] of common) if (s < q && e > p) held.fill(1, Math.max(s, p) - p, Math.min(e, q) - p);
      for (let x = p; x < q; x++) {
        if (hid?.[x - p]) { hiddenBytes++; continue; }
        if (!held[x - p]) { notCompared++; close(); continue; }
        compared++;
        if (a.data[x - a.from] === b.data[x - b.from]) continue;
        changed++;
        if (open && x - lastChange <= gap + 1) open.to = x + 1;
        else { close(); open = { from: x, to: x + 1 }; }
        lastChange = x;
      }
    }
    close();
    return new DiffResult({ from, to, changed, compared, hiddenBytes, notCompared, runs }, regions);
  }

  async function search(value, opts = {}) {
    const needle = needleBytes(value, opts);
    if (opts.snapshot !== undefined && !(opts.snapshot instanceof Snapshot)) throw new TypeError("snapshot ist ein Ergebnis von KORG.ram.snapshot");
    const from0 = opts.snapshot?.from ?? opts.from;
    const to0 = opts.snapshot?.to ?? opts.to;
    const o = parse([{ ...opts, from: opts.from ?? from0, to: opts.to ?? to0 }], "search");
    const { maxMatches = DEFAULTS.maxMatches } = opts;
    const found = [];
    let hiddenMatches = 0;
    let truncated = false;
    const len = needle.length;
    const take = addr => {
      if (o.mask && regions.hidden(addr, addr + len, o.show).every(Boolean)) { hiddenMatches++; return; }
      if (found.length >= maxMatches) { truncated = true; return; }
      found.push({ addr });
    };
    // Matches are looked for in the bytes of one buffer; the end of the previous chunk goes in front when it ran right up to this one.
    const scan = (buf, base, skipBefore) => {
      for (let i = buf.indexOf(needle[0]); i !== -1 && i + len <= buf.length; i = buf.indexOf(needle[0], i + 1)) {
        if (i + len <= skipBefore) continue;
        let k = 1;
        while (k < len && buf[i + k] === needle[k]) k++;
        if (k === len) take(base + i);
      }
    };
    let result;
    if (opts.snapshot) {
      const snap = opts.snapshot;
      for (const [s, e] of snap.spans) {
        const a = Math.max(s, o.from);
        const b = Math.min(e, o.to);
        if (a < b) scan(snap.data.subarray(a - snap.from, b - snap.from), a, 0);
      }
      result = { read: 0, skipped: 0 };
    } else {
      readable(o.from, o.to);
      let tail = null;
      result = await sweep(o, len - 1, (at, bytes) => {
        const keep = tail && tail.end === at ? tail.bytes : new Uint8Array(0);
        const buf = new Uint8Array(keep.length + bytes.length);
        buf.set(keep);
        buf.set(bytes, keep.length);
        scan(buf, at - keep.length, keep.length);
        tail = { end: at + bytes.length, bytes: bytes.slice(Math.max(0, bytes.length - (len - 1))) };
      }, () => truncated);
    }
    return new SearchResult({ needle, from: o.from, to: o.to, matches: found, hiddenMatches, truncated, ...result }, regions);
  }

  const where = (addr, length = 1) => {
    if (!Number.isInteger(addr) || !Number.isInteger(length) || length < 1) throw new RangeError("where(adresse, anzahl)");
    const note = regions.hidden(addr, addr + 1)[0] ? " (erklärt, wird ausgeblendet)" : "";
    return `${hex(addr)}: ${regions.describe(addr, length)}${note}`;
  };

  return { snapshot, diff, search, where };
}
