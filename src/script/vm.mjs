/**
 * The JS reference VM. It runs a blob the way the ARM VM will: a stack
 * machine over 32-bit integers with fuel, a time hook, bounds and stack
 * checks and the contract's error codes. A run never throws for a script's
 * fault; it returns the code, and the script is switched off.
 *
 * Fuel is the sum of instruction costs (plus an API entry's cost per call).
 * The time hook `env.timeUp()` is asked at entry, at successful return and
 * every LIMITS.timeCheckEvery instructions. Both end a run with their own error code.
 */
import {
  ERROR, LIMITS, OPCODE_BY_CODE, OPCODE_COUNT, API_BY_ID, EVENT_BY_NAME, EVENT_BY_ID, OP, ARRAY_HANDLE,
} from "../../data/script/contract.mjs";
import { decodeBlob, fail, lineAt } from "./blob.mjs";
import { text, render } from "../text.mjs";

const say = (key, vars) => render(text(key, vars));
import { verifyParts } from "./verifier.mjs";
import { binary } from "./alu.mjs";

/** Thrown by a host API function to end the run with one of the contract's codes. */
export class ScriptFault extends Error {
  constructor(code, detail = "") {
    super(detail);
    this.code = code;
    this.detail = detail;
  }
}

const BINARY = new Set([OP.ADD, OP.SUB, OP.MUL, OP.DIV, OP.MOD, OP.AND, OP.OR, OP.XOR, OP.SHL, OP.SHR, OP.EQ, OP.NE, OP.LT, OP.LE, OP.GT, OP.GE]);

function operands(info, code, at) {
  let x = 0;
  let y = 0;
  let p = at + 1;
  info.operands.forEach((o, k) => {
    const v = o.size === 1 ? code[p] : code[p] | (code[p + 1] << 8);
    if (k === 0) x = v; else y = v;
    p += o.size;
  });
  return [x, y];
}

/**
 * Run code from `entry` with `args` on the stack.
 * @param {object} s the script's parts
 * @param {{ fuel?: number, timeUp?: () => boolean, onStep?: (offset: number) => void, api?: Record<string, Function> }} env
 */
function execute(s, entry, args, eventId, env) {
  const { code, consts, strings, vars } = s;
  const stack = new Int32Array(LIMITS.stack);
  const calls = [];
  let sp = 0;
  let pc = entry;
  let at = entry;
  let ops = 0;
  let cost = 0;
  let fuel = env.fuel ?? LIMITS.fuel;
  const finish = (c, detail = "") => {
    if (c === ERROR.OK && env.timeUp?.()) c = ERROR.TIME;
    const e = c === ERROR.OK ? null : fail(c, detail, at);
    return { ok: c === ERROR.OK, code: c, name: e?.name ?? "OK", message: e?.message ?? "", offset: at, line: lineAt(s.lines, at), ops, cost };
  };
  if (env.timeUp?.()) return finish(ERROR.TIME);
  if (args.length > LIMITS.stack) return finish(ERROR.STACK, say("script.fault.args"));
  for (const a of args) stack[sp++] = a | 0;

  for (;;) {
    if (pc >= code.length) return finish(ERROR.BAD_JUMP, say("script.fault.jump", { address: pc }));
    at = pc;
    const op = code[pc];
    if (op >= OPCODE_COUNT) return finish(ERROR.BAD_OPCODE, `0x${op.toString(16)} bei ${pc}`);
    const info = OPCODE_BY_CODE[op];
    if (pc + info.size > code.length) return finish(ERROR.TRUNCATED, `${info.name} bei ${pc}`);
    if (ops > 0 && ops % LIMITS.timeCheckEvery === 0 && env.timeUp?.()) return finish(ERROR.TIME);
    if (info.cost > fuel) return finish(ERROR.FUEL);
    const [x, y] = operands(info, code, pc);
    const pop = info.pop === "argc" ? y : info.pop;
    if (sp < pop) return finish(ERROR.STACK, say("script.fault.stackLow", { op: info.name, needed: pop, has: sp }));
    if (sp - pop + info.push > LIMITS.stack) return finish(ERROR.STACK, say("script.fault.stackFull"));
    fuel -= info.cost;
    cost += info.cost;
    ops += 1;
    env.onStep?.(pc);
    pc += info.size;

    switch (op) {
      case OP.HALT: return finish(ERROR.OK);
      case OP.PUSHB: stack[sp++] = x; break;
      case OP.PUSHK:
        if (x >= consts.length) return finish(ERROR.BAD_CONST, say("script.fault.const", { index: x }));
        stack[sp++] = consts[x];
        break;
      case OP.PUSHS:
        if (x >= strings.length) return finish(ERROR.BAD_STRING, say("script.fault.string", { index: x }));
        stack[sp++] = x;
        break;
      case OP.LOAD:
        if (x >= vars.length) return finish(ERROR.BAD_VAR, say("script.fault.var", { index: x }));
        stack[sp++] = vars[x];
        break;
      case OP.STORE:
        if (x >= vars.length) return finish(ERROR.BAD_VAR, say("script.fault.var", { index: x }));
        vars[x] = stack[--sp];
        break;
      case OP.ALOAD: {
        if (y === 0 || x + y > vars.length) return finish(ERROR.BAD_VAR, say("script.fault.array", { base: x, length: y }));
        const i = stack[sp - 1];
        if (i >>> 0 >= y) return finish(ERROR.BOUNDS, say("script.fault.bounds", { index: i, length: y }));
        stack[sp - 1] = vars[x + i];
        break;
      }
      case OP.ASTORE: {
        if (y === 0 || x + y > vars.length) return finish(ERROR.BAD_VAR, say("script.fault.array", { base: x, length: y }));
        const v = stack[--sp];
        const i = stack[--sp];
        if (i >>> 0 >= y) return finish(ERROR.BOUNDS, say("script.fault.bounds", { index: i, length: y }));
        vars[x + i] = v;
        break;
      }
      case OP.DUP: stack[sp] = stack[sp - 1]; sp += 1; break;
      case OP.DROP: sp -= 1; break;
      case OP.NEG: stack[sp - 1] = -stack[sp - 1] | 0; break;
      case OP.NOT: stack[sp - 1] = stack[sp - 1] === 0 ? 1 : 0; break;
      case OP.JMP: pc = x; break;
      case OP.JZ: if (stack[--sp] === 0) pc = x; break;
      case OP.JNZ: if (stack[--sp] !== 0) pc = x; break;
      case OP.CALL:
        if (calls.length >= LIMITS.callDepth) return finish(ERROR.CALL_DEPTH);
        calls.push(pc);
        pc = x;
        break;
      case OP.RET:
        if (calls.length === 0) return finish(ERROR.OK);
        pc = calls.pop();
        break;
      case OP.CALLAPI: {
        const api = API_BY_ID.get(x);
        if (!api) return finish(ERROR.API_UNKNOWN, `Id ${x}`);
        if (y !== api.args.length) return finish(ERROR.API_ARGC, say("script.fault.argc", { name: api.name, count: api.args.length, given: y }));
        if (api.since > s.header.apiVersion) return finish(ERROR.API_VERSION, api.name);
        if (eventId !== undefined && !(api.eventMask >> eventId & 1)) return finish(ERROR.API_EVENT, say("script.fault.event", { name: api.name, event: EVENT_BY_ID.get(eventId).name }));
        if (api.cost > fuel) return finish(ERROR.FUEL);
        fuel -= api.cost;
        cost += api.cost;
        const given = [];
        for (let i = 0; i < y; i++) {
          const v = stack[sp - y + i];
          const spec = api.args[i];
          if (spec.kind === "str") {
            if (v >>> 0 >= strings.length) return finish(ERROR.BAD_STRING, `${api.name}: ${spec.name}`);
            given.push(strings[v]);
          } else if (spec.kind === "arr") {
            const base = ARRAY_HANDLE.base(v);
            const length = ARRAY_HANDLE.length(v);
            if (length === 0 || base + length > vars.length) return finish(ERROR.BAD_VAR, `${api.name}: ${spec.name}`);
            const extra = length * api.perItem;
            if (extra > fuel) return finish(ERROR.FUEL);
            fuel -= extra;
            cost += extra;
            given.push(vars.subarray(base, base + length));
          } else {
            if (v < spec.min || v > spec.max) return finish(ERROR.API_ARG, `${api.name}: ${spec.name} = ${v}, erlaubt ${spec.min} bis ${spec.max}`);
            given.push(v);
          }
        }
        sp -= y;
        let result = 0;
        const fn = env.api?.[api.name];
        if (fn) {
          try { result = fn(...given) ?? 0; } catch (e) {
            if (e instanceof ScriptFault) return finish(e.code, e.detail);
            throw e;
          }
        }
        stack[sp++] = Number(result) | 0;
        break;
      }
      default: {
        if (!BINARY.has(op)) return finish(ERROR.BAD_OPCODE, `${info.name} nicht umgesetzt`);
        const b = stack[--sp];
        const r = binary(info.name, stack[sp - 1], b);
        if (r === null) return finish(ERROR.DIV_ZERO);
        stack[sp - 1] = r;
      }
    }
  }
}

export class Script {
  constructor(parts, info) {
    this.header = parts.header;
    this.name = parts.header.name;
    this.code = parts.code;
    this.consts = parts.consts;
    this.strings = parts.strings;
    this.lines = parts.lines;
    this.handlers = new Map(parts.handlers.map(h => [h.event, h]));
    this.vars = new Int32Array(parts.header.varCount);
    for (const r of parts.data ?? []) this.vars.set(r.bytes, r.base);
    this.info = info;
    this.state = "loaded";
    this.fault = null;
  }

  #run(entry, args, eventId, env) {
    const r = execute(this, entry, args, eventId, env);
    if (!r.ok) {
      this.state = "disabled";
      this.fault = { code: r.code, name: r.name, message: r.message, line: r.line, offset: r.offset, event: EVENT_BY_ID.get(eventId)?.name ?? null };
    }
    return r;
  }

  /** Run the script body (the top-level statements). The handlers become active when it finishes without a fault. */
  start(env = {}) {
    if (this.state !== "loaded") throw new Error(`start in state ${this.state}`);
    const r = this.#run(this.header.entry, [], 0, env);
    if (r.ok) this.state = "armed";
    return r;
  }

  /** Run the handler registered for an event, if there is one and the script is armed. */
  dispatch(event, args = [], env = {}) {
    const ev = typeof event === "number" ? EVENT_BY_ID.get(event) : EVENT_BY_NAME.get(event);
    if (!ev || ev.name === "start") throw new Error(`no such event: ${event}`);
    const skipped = { ok: true, code: ERROR.OK, name: "OK", message: "", offset: 0, line: 0, ops: 0, cost: 0 };
    if (this.state !== "armed") return { ...skipped, handled: false };
    const h = this.handlers.get(ev.id);
    if (!h) return { ...skipped, handled: false };
    return { ...this.#run(h.entry, args.slice(0, h.argc), ev.id, env), handled: true };
  }
}

/**
 * Check a blob, and with `verify` (the default) its code, and make a script of it.
 * `verify: false` exists so tests can watch the run-time checks catch what the verifier would have refused.
 * @returns {{ ok: true, script: Script } | { ok: false, error: object }}
 */
export function loadScript(bytes, { verify = true } = {}) {
  const parts = decodeBlob(bytes);
  if (!parts.ok) return parts;
  let info = null;
  if (verify) {
    const v = verifyParts(parts);
    if (!v.ok) return v;
    info = v.info;
  }
  return { ok: true, script: new Script(parts, info) };
}
