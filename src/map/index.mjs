/**
 * The device map: every editable field of the Electribe, described once.
 *
 * The page is generated from it, the linter reads from it, and the
 * documentation does too. A new measurement is one more entry or one entry
 * made more precise; nothing else needs to change for the field to appear.
 *
 * A field says what it is and where it sits inside its block. Where a block
 * sits on a given transport (a pattern in a backup file, a record in RAM) is
 * decided in address.mjs, in one place per transport.
 */
import { checkInstruction } from "../guards.mjs";
import pattern from "../../data/map/pattern.mjs";
import global from "../../data/map/global.mjs";
import fx from "../../data/map/fx.mjs";
import fxParams from "../../data/map/fx-params.mjs";
import firmware from "../../data/map/firmware.mjs";
import screen from "../../data/map/screen.mjs";
import sample from "../../data/map/sample.mjs";
import { parseType } from "./types.mjs";
import { converter } from "./convert.mjs";

/** Generated files share defaults and name their repeats; spell them out. */
function expand(source) {
  if (!source.generated) return source.fields;
  return source.fields.map(f => ({
    ...source.defaults,
    ...f,
    repeat: typeof f.repeat === "string" ? source.repeats[f.repeat] : f.repeat,
  }));
}

const SOURCES = [pattern, global, fx, fxParams, ...firmware, ...screen, ...sample];

/** Shared parts (one range object serves 539 fields) must not be changeable through any of them. */
function deepFreeze(o) {
  if (o && typeof o === "object" && !Object.isFrozen(o)) {
    Object.freeze(o);
    for (const v of Object.values(o)) deepFreeze(v);
  }
  return o;
}

export const BLOCKS = new Map();
export const FIELDS = new Map();
export const TABLES = new Map();
export const POINTER_TABLES = new Map();

for (const source of SOURCES) {
  let block = BLOCKS.get(source.block);
  if (!block) {
    block = { name: source.block, size: source.size, label: source.label, firmware: source.firmware ?? null, meta: source.meta ?? {}, fields: [] };
    BLOCKS.set(source.block, block);
  }
  if (source.meta) block.meta = deepFreeze({ ...block.meta, ...source.meta });
  for (const raw of expand(source)) {
    if (FIELDS.has(raw.id)) throw new Error(`device map: ${raw.id} appears twice`);
    const field = deepFreeze({ ...raw, block: source.block, firmware: raw.firmware ?? source.firmware ?? null });
    FIELDS.set(field.id, field);
    block.fields.push(field);
  }
  for (const table of source.pointerTables || []) {
    if (POINTER_TABLES.has(table.id)) throw new Error(`device map: pointer table ${table.id} appears twice`);
    POINTER_TABLES.set(table.id, deepFreeze({ ...table, in: source.block }));
  }
  for (const table of source.tables || []) {
    if (TABLES.has(table.id)) throw new Error(`device map: table ${table.id} appears twice`);
    TABLES.set(table.id, deepFreeze({ ...table, in: source.block }));
  }
}

export function field(id) {
  const f = FIELDS.get(id);
  if (!f) throw new Error(`device map has no field ${id}`);
  return f;
}

export const fieldsOf = block => BLOCKS.get(block)?.fields ?? [];

export const typeOf = f => parseType(f.type);

/** Every combination of repeat indices, outermost first. */
export function instances(f) {
  let out = [[]];
  for (const level of f.repeat || []) {
    const next = [];
    for (const prefix of out) for (let i = 0; i < level.count; i++) next.push([...prefix, i]);
    out = next;
  }
  return out;
}

function checkIndices(f, indices) {
  const levels = f.repeat || [];
  if (indices.length !== levels.length) {
    throw new Error(`${f.id} needs ${levels.length} indices, got ${indices.length}`);
  }
  levels.forEach((level, i) => {
    if (!Number.isInteger(indices[i]) || indices[i] < 0 || indices[i] >= level.count) {
      throw new RangeError(`${f.id}: ${level.label?.en ?? "index"} ${indices[i]} is out of range`);
    }
  });
}

/** Offset of one instance inside its block. Fields with sites have several. */
export function offsetOf(f, indices = []) {
  checkIndices(f, indices);
  if (f.sites) throw new Error(`${f.id} sits in several places; use sitesOf`);
  return (f.repeat || []).reduce((at, level, i) => at + indices[i] * level.stride, f.where.offset);
}

/** Offset of the byte a conditional field depends on, in the same instance. */
export function conditionOffset(f, indices) {
  return (f.repeat || []).reduce((at, level, i) => at + indices[i] * level.stride, f.when.offset);
}

/** Whether a conditional field means anything in this instance of the block. */
export function applies(bytes, f, indices = [], base = 0) {
  checkIndices(f, indices);
  if (!f.when) return true;
  return bytes[base + conditionOffset(f, indices)] === f.when.equals;
}

/** Each site of a multi-site field, with the value it holds for a given count. */
export function sitesOf(f, value) {
  return f.sites.map(s => ({
    offset: s.file,
    value: s.value === "count" ? value : s.value === "count - 1" ? value - 1 : (() => {
      throw new Error(`${f.id}: unknown site rule ${s.value}`);
    })(),
    rule: s.value,
  }));
}

/** [start, end) of every byte the field can occupy, across all instances. */
export function byteSpans(f) {
  const width = typeOf(f).width;
  if (f.sites) return f.sites.map(s => [s.file, s.file + width]);
  return instances(f).map(ix => {
    const at = offsetOf(f, ix);
    return [at, at + width];
  });
}

export function readRaw(bytes, f, indices = [], base = 0) {
  const type = typeOf(f);
  if (f.sites) {
    const values = f.sites.map(s => type.read(bytes, base + s.file));
    const first = sitesOf(f, 0)[0];
    const count = values[0] - (first.rule === "count - 1" ? -1 : 0);
    const agreed = sitesOf(f, count).every((s, i) => values[i] === s.value);
    return { value: count, agreed, values };
  }
  return type.read(bytes, base + offsetOf(f, indices));
}

/**
 * Write one instance. Values outside the field's range are refused here, so
 * nothing downstream has to wonder whether a byte was checked.
 */
export function writeRaw(bytes, f, indices, raw, base = 0) {
  if (f.edit === "readonly") throw new Error(`${f.id} is read only`);
  if (!f.sites && !applies(bytes, f, indices, base)) {
    throw new Error(`${f.id}: unit 0x${f.when.equals.toString(16)} is not in this stage, so this byte means something else`);
  }
  if (f.range && typeof raw === "number" && (raw < f.range[0] || raw > f.range[1])) {
    throw new RangeError(`${f.id}: ${raw} is outside ${f.range[0]} to ${f.range[1]}`);
  }
  const type = typeOf(f);
  if (f.sites) {
    for (const s of sitesOf(f, raw)) type.write(bytes, base + s.offset, s.value);
    return;
  }
  const at = base + offsetOf(f, indices);
  if (f.instruction) checkInstruction(bytes.subarray(at, at + 4), f.instruction, f.id);
  type.write(bytes, at, raw);
}

/** The field's value in plain words, or null where it has no converter. */
export function describe(f, raw) {
  if (!f.convert || typeof raw !== "number") return null;
  const c = converter(f.convert);
  return { value: c.fromRaw(raw), text: c.format(raw), unit: c.unit ?? f.unit ?? null };
}

export const isUnknown = f => f.source === "unknown";
export const isExpert = f => f.edit === "expert";
