/**
 * The ARM VM's tables, generated from the contract so the VM source never
 * holds a number of its own. `armTables()` returns the tables as bytes,
 * `asmInclude()` the same as an include for tools/patch/arm.py: `.equ`
 * constants plus the tables as `.byte` and `.word` data. The VM source
 * supplies the labels `op_<name>`, `e_bad_opcode` and (per API id, patched
 * in at link time) the glue functions.
 *
 * Tables of OPCODE_SLOTS entries are indexed by opcode; slots at and above
 * OPCODE_COUNT are zero, the VM refuses those opcodes before it looks them
 * up. API entries are API_ENTRY_SIZE bytes, indexed by id up to the highest id:
 *   +0 present, +1 argc, +2 fuel for each slot of an array argument, +3 cost, +4 u32 event mask (bit = event id),
 *   +8 text mask (bit i: argument i is a text), +9 array mask (bit i: argument i is an array), +10 u16 since,
 *   +12 u32 glue pointer (0 here),
 *   +16 i32 min x4, +32 i32 max x4.
 */
import {
  FORMAT_VERSION, API_VERSION, MAGIC, LIMITS, HEADER, SECTION, OPCODES, OPCODE_COUNT, EVENTS, API, ERRORS, BUDGET, SCRIPT_ENTRY, SCRIPT_STATE, TIMER3,
  BLOCK_FLAGS, SCRIPT_CONTROL, SCRIPT_PHASE, SCRIPT_EVENT_RECORD, SCRIPT_LED, SCRIPT_LED_VALID, SCRIPT_DISPLAY, SCRIPT_GIF, SCRIPT_KNOBS, SCRIPT_APPS, STORE, ARCHIVE, DESC_TRAILER, CARD_STATUS,
} from "../../data/script/contract.mjs";
import { FONT } from "../../data/script/font.mjs";

export const OPCODE_SLOTS = 64;
const ERROR_NAME_SIZE = 16;
const GLYPH_BYTES = 5;
export const API_ENTRY_SIZE = 48;
export const API_SINCE_OFFSET = 10;
export const FLOWS = ["next", "jump", "branch", "call", "end"];
export const OPERAND_KINDS = ["none", "byte", "const", "string", "var", "arrayBase", "arrayLength", "target", "argc", "api"];
/** Value in the pop table for "taken from the argc operand". */
export const POP_ARGC = 0xff;

const byOpcode = f => Uint8Array.from({ length: OPCODE_SLOTS }, (_, i) => (i < OPCODE_COUNT ? f(OPCODES[i]) : 0));
const kind = (o, k) => (o.operands[k] ? OPERAND_KINDS.indexOf(o.operands[k].as) : 0);

export function apiTable(entries = API) {
  const top = Math.max(...entries.map(a => a.id));
  const out = new Uint8Array((top + 1) * API_ENTRY_SIZE);
  const dv = new DataView(out.buffer);
  for (const a of entries) {
    if (a.cost > 255) throw new RangeError(`${a.name}: cost ${a.cost} does not fit a byte`);
    if (!Number.isInteger(a.since) || a.since < 1 || a.since > 65535) throw new RangeError(`${a.name}: since ${a.since} does not fit a version word`);
    const o = a.id * API_ENTRY_SIZE;
    out[o] = 1;
    out[o + 1] = a.args.length;
    if (!Number.isInteger(a.perItem ?? 0) || a.perItem < 0 || a.perItem > 255) throw new RangeError(`${a.name}: perItem ${a.perItem} does not fit a byte`);
    out[o + 2] = a.perItem ?? 0;
    dv.setUint16(o + API_SINCE_OFFSET, a.since, true);
    out[o + 3] = a.cost;
    dv.setUint32(o + 4, a.eventMask, true);
    out[o + 8] = a.args.reduce((m, arg, i) => m | (arg.kind === "str" ? 1 << i : 0), 0);
    out[o + 9] = a.args.reduce((m, arg, i) => m | (arg.kind === "arr" ? 1 << i : 0), 0);
    for (let i = 0; i < LIMITS.apiArgs; i++) {
      const arg = a.args[i];
      dv.setInt32(o + 16 + 4 * i, arg?.kind === "int" ? arg.min : arg ? 0 : -2147483648, true);
      dv.setInt32(o + 32 + 4 * i, arg?.kind === "int" ? arg.max : arg ? 0 : 2147483647, true);
    }
  }
  return out;
}

export function armTables() {
  const operandKinds = new Uint8Array(OPCODE_SLOTS * 2);
  OPCODES.forEach((o, i) => { operandKinds[2 * i] = kind(o, 0); operandKinds[2 * i + 1] = kind(o, 1); });
  return {
    opSize: byOpcode(o => o.size),
    opCost: byOpcode(o => o.cost),
    opPop: byOpcode(o => (o.pop === "argc" ? POP_ARGC : o.pop)),
    opPush: byOpcode(o => o.push),
    opFlow: byOpcode(o => FLOWS.indexOf(o.flow)),
    opOperands: operandKinds,
    apiTable: apiTable(),
    eventArgc: Uint8Array.from(EVENTS.map(e => e.argc)),
  };
}

const sym = name => name.replace(/([a-z0-9])([A-Z])/g, "$1_$2").replace(/\./g, "_").toUpperCase();
const hex = n => `0x${(n >>> 0).toString(16)}`;
const rows = (label, bytes, width = 16) => {
  const out = [`${label}:`];
  for (let i = 0; i < bytes.length; i += width) out.push(`    .byte ${Array.from(bytes.subarray(i, i + width)).join(", ")}`);
  return out;
};

export function asmInclude() {
  const t = armTables();
  const out = ["; generated from data/script/contract.mjs by src/script/arm-tables.mjs, do not edit"];
  const eq = (name, value) => out.push(`.equ ${name}, ${typeof value === "number" && value > 9 ? hex(value) : value}`);
  eq("SCRIPT_FORMAT_VERSION", FORMAT_VERSION);
  eq("SCRIPT_API_VERSION", API_VERSION);
  eq("SCRIPT_MAGIC", MAGIC);
  eq("SCRIPT_OPCODE_COUNT", OPCODE_COUNT);
  eq("SCRIPT_OPCODE_SLOTS", OPCODE_SLOTS);
  eq("SCRIPT_API_ENTRY_SIZE", API_ENTRY_SIZE);
  eq("SCRIPT_API_SINCE", API_SINCE_OFFSET);
  eq("SCRIPT_API_ENTRIES", t.apiTable.length / API_ENTRY_SIZE);
  eq("SCRIPT_POP_ARGC", POP_ARGC);
  eq("SCRIPT_RING", BUDGET.ring);
  eq("SCRIPT_ERROR_NAME_SIZE", ERROR_NAME_SIZE);
  eq("SCRIPT_ERROR_COUNT", ERRORS.length);
  eq("SCRIPT_KNOBS", SCRIPT_KNOBS);
  eq("SCRIPT_GIF_MAGIC", SCRIPT_GIF.magic);
  eq("SCRIPT_GIF_VERSION", SCRIPT_GIF.version);
  eq("SCRIPT_VAR_SLOTS", BUDGET.variableSlots);
  eq("SCRIPT_POOL_BYTES", BUDGET.scriptBytes);
  eq("SCRIPT_EVENT_COUNT", EVENTS.length);
  eq("SCRIPT_TIMER_ADDRESS", TIMER3.address);
  eq("SCRIPT_TIMER_HZ", TIMER3.hz);
  eq("SCRIPT_TIMER_PERIOD", TIMER3.period);
  eq("SCRIPT_TIMER_TICKS_PER_MS", TIMER3.hz / 1000);
  eq("SCRIPT_FRAME_TICKS", Math.round(BUDGET.frameMs * TIMER3.hz / 1000));
  eq("SCRIPT_ENTRY_SIZE", SCRIPT_ENTRY.size);
  for (const f of SCRIPT_ENTRY.fields) eq(`SCRIPT_ENTRY_${sym(f.name)}`, f.offset);
  for (const [name, value] of Object.entries(SCRIPT_STATE)) eq(`SCRIPT_STATE_${name}`, value);
  eq("SCRIPT_CONTROL_HEADER_SIZE", SCRIPT_CONTROL.headerSize);
  for (const f of SCRIPT_CONTROL.fields) eq(`SCRIPT_CONTROL_${sym(f.name)}`, f.offset);
  for (const [name, value] of Object.entries(SCRIPT_PHASE)) eq(`SCRIPT_PHASE_${name}`, value);
  eq("SCRIPT_EVENT_RECORD_SIZE", SCRIPT_EVENT_RECORD.size);
  for (const f of SCRIPT_EVENT_RECORD.fields) eq(`SCRIPT_EVENT_RECORD_${sym(f.name)}`, f.offset);
  for (const [name, value] of Object.entries(SCRIPT_LED)) if (typeof value === "number") eq(`SCRIPT_LED_${sym(name)}`, value);
  for (const f of SCRIPT_LED.fields) eq(`SCRIPT_LED_${sym(f.name)}`, f.offset);
  for (const [name, value] of Object.entries(SCRIPT_LED_VALID)) eq(`SCRIPT_LED_VALID_${name}`, value);
  for (const [name, value] of Object.entries(SCRIPT_DISPLAY)) eq(`SCRIPT_DISPLAY_${sym(name)}`, value);
  for (const [name, value] of Object.entries(SCRIPT_APPS)) if (typeof value === "number") eq(`SCRIPT_APPS_${sym(name)}`, value);
  for (const f of SCRIPT_APPS.fields) eq(`SCRIPT_APPS_${sym(f.name)}`, f.offset);
  for (const f of SCRIPT_APPS.recordFields) eq(`SCRIPT_APP_${sym(f.name)}`, f.offset);
  SCRIPT_APPS.groups.forEach((g, i) => eq(`SCRIPT_APP_GROUP_${g}`, i));
  for (const [name, value] of Object.entries(STORE)) if (typeof value === "number") eq(`STORE_${sym(name)}`, value);
  for (const [name, value] of Object.entries(ARCHIVE)) if (typeof value === "number") eq(`ARCHIVE_${sym(name)}`, value);
  for (const f of ARCHIVE.fields) eq(`ARCHIVE_AT_${sym(f.name)}`, f.offset);
  for (const [name, value] of Object.entries(DESC_TRAILER)) eq(`DESC_${sym(name)}`, value);
  for (const [name, value] of Object.entries(CARD_STATUS)) eq(`CARD_${name}`, value);
  for (const [k, v] of Object.entries(LIMITS)) eq(`LIM_${sym(k)}`, v);
  eq("BLOCK_KNOWN_FLAGS", BLOCK_FLAGS.KNOWN);
  eq("HDR_SIZE", HEADER.size);
  for (const f of HEADER.fields) eq(`HDR_${sym(f.name)}`, f.offset);
  for (const [k, v] of Object.entries(SECTION)) eq(`SEC_${sym(k)}`, v);
  for (const o of OPCODES) eq(`OP_${o.name}`, o.code);
  FLOWS.forEach((f, i) => eq(`FLOW_${f.toUpperCase()}`, i));
  OPERAND_KINDS.forEach((k, i) => eq(`ARG_${sym(k)}`, i));
  for (const e of ERRORS) eq(`ERR_${e.name}`, e.code);
  for (const e of EVENTS) eq(`EV_${sym(e.name)}`, e.id);
  for (const a of API) eq(`API_${sym(a.name)}`, a.id);
  out.push(".align 4");
  out.push("script_dispatch:");
  for (let i = 0; i < OPCODE_SLOTS; i += 8) {
    const names = Array.from({ length: Math.min(8, OPCODE_SLOTS - i) }, (_, k) => (i + k < OPCODE_COUNT ? `op_${OPCODES[i + k].name.toLowerCase()}` : "e_bad_opcode"));
    out.push(`    .word ${names.join(", ")}`);
  }
  for (const [name, bytes] of [
    ["script_op_size", t.opSize], ["script_op_cost", t.opCost], ["script_op_pop", t.opPop], ["script_op_push", t.opPush],
    ["script_op_flow", t.opFlow], ["script_op_operands", t.opOperands], ["script_event_argc", t.eventArgc],
  ]) out.push(...rows(name, bytes));
  const names = new Uint8Array(ERRORS.length * ERROR_NAME_SIZE);
  ERRORS.forEach(e => names.set(Uint8Array.from(e.name, c => c.charCodeAt(0)), e.code * ERROR_NAME_SIZE));
  out.push(...rows("script_font", Uint8Array.from(FONT.flatMap(g => [...g])), GLYPH_BYTES), ...rows("script_error_names", names, ERROR_NAME_SIZE));
  out.push(".align 4", ...rows("script_api_table", t.apiTable, API_ENTRY_SIZE));
  return `${out.join("\n")}\n`;
}
