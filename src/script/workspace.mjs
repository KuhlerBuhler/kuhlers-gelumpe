/** Own scripts in the browser. Storage is injected and may throw or be missing; the workspace then lives in memory. */
import { LIMITS } from "../../data/script/contract.mjs";
import { TextError, text, render } from "../text.mjs";

const NAME = new RegExp(`^[A-Za-z][A-Za-z0-9_]{0,${LIMITS.nameLength - 1}}$`);
export const STORAGE_KEY = "cee.scripts.v1";

export const validName = name => typeof name === "string" && NAME.test(name);

/** A short fingerprint of the source text, to tell whether a probe belongs to it. */
export function sourceKey(source) {
  let h = 0x811c9dc5;
  for (let i = 0; i < source.length; i++) h = Math.imul(h ^ source.charCodeAt(i), 0x01000193) >>> 0;
  return `${source.length}:${h.toString(16)}`;
}

/**
 * What the user tells about an own plugin: description, creator, a link to their profile, and a picture of 128 x 64
 * pixels for its card (the display's 1024 bytes, base64). Only strings are kept.
 */
function metaOf(meta) {
  const out = {};
  for (const key of ["description", "creator", "creatorUrl", "image"]) if (typeof meta?.[key] === "string" && meta[key]) out[key] = meta[key];
  return out;
}

export class Workspace {
  constructor(storage = null, key = STORAGE_KEY) {
    this.storage = storage;
    this.key = key;
    this.items = this.#load();
  }

  #load() {
    try {
      const raw = this.storage?.getItem(this.key);
      const data = raw ? JSON.parse(raw) : [];
      return Array.isArray(data) ? data.filter(s => validName(s?.name) && typeof s.source === "string").map(s => ({ name: s.name, source: s.source, inputs: Array.isArray(s.inputs) ? s.inputs : [], probe: s.probe ?? null, meta: metaOf(s.meta) })) : [];
    } catch { return []; }
  }

  #store() {
    try { this.storage?.setItem(this.key, JSON.stringify(this.items)); } catch { /* the workspace stays in memory */ }
  }

  list() { return this.items.map(s => ({ ...s })); }

  get(name) { const s = this.items.find(i => i.name === name); return s ? { ...s } : null; }

  /** A name nobody uses yet, built from `base`. */
  freeName(base = "plugin") {
    const stem = (base.replace(/[^A-Za-z0-9_]/g, "") || "plugin").replace(/^[^A-Za-z]+/, "s").slice(0, LIMITS.nameLength - 3);
    if (!this.get(stem)) return stem;
    for (let n = 2; ; n++) if (!this.get(`${stem}${n}`)) return `${stem}${n}`;
  }

  /** Create or replace the script `name`. A changed source drops the recorded probe, which belongs to the old text. */
  save({ name, source, inputs, probe, meta }) {
    if (!validName(name)) throw new RangeError(render(text("script.name.rule", { max: LIMITS.nameLength })));
    const at = this.items.findIndex(s => s.name === name);
    const old = at >= 0 ? this.items[at] : null;
    const next = {
      name, source,
      inputs: inputs ?? old?.inputs ?? [],
      probe: probe !== undefined ? probe : old && old.source === source ? old.probe : null,
      meta: metaOf(meta ?? old?.meta),
    };
    if (at >= 0) this.items[at] = next; else this.items.push(next);
    this.#store();
    return { ...next };
  }

  rename(from, to) {
    if (!validName(to)) throw new RangeError(render(text("script.name.rule", { max: LIMITS.nameLength })));
    if (this.get(to)) throw new TextError("script.name.taken", { name: to });
    const item = this.items.find(s => s.name === from);
    if (!item) throw new TextError("script.name.missing", { name: from });
    item.name = to;
    this.#store();
  }

  remove(name) {
    this.items = this.items.filter(s => s.name !== name);
    this.#store();
  }
}
