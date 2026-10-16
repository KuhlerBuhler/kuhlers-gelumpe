import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { ERROR, LIMITS, BUDGET, HEADER, MAGIC, OP, EVENT_BY_NAME } from "../data/script/contract.mjs";
import { assemble } from "../src/script/asm.mjs";
import { encodeBlob, decodeBlob, crc32, lineAt, sectionOffsets, markProbed, isProbed } from "../src/script/blob.mjs";
import { verify } from "../src/script/verifier.mjs";
import { loadScript, ScriptFault } from "../src/script/vm.mjs";
import { ScriptRuntime } from "../src/script/runtime.mjs";
import { Coverage } from "../src/script/coverage.mjs";
import { compile, formatError } from "../src/script/compiler.mjs";
import * as contract from "../data/script/contract.mjs";

const EV = n => EVENT_BY_NAME.get(n).id;
const blobOf = (items, o = {}) => {
  const a = assemble(items);
  return encodeBlob({ code: a.code, lines: a.lines, varCount: 8, stackMax: 16, ...o });
};
const rejects = (bytes, code, opts) => {
  const l = loadScript(bytes, opts);
  assert.equal(l.ok, false, "the blob should have been refused");
  assert.equal(l.error.code, code, `${l.error.name}: ${l.error.message}`);
  return l.error;
};
const load = (items, o, opts) => {
  const l = loadScript(blobOf(items, o), opts);
  assert.ok(l.ok, l.error?.message);
  return l.script;
};
const fixture = name => fs.readFileSync(new URL(`./fixtures/scripts/${name}`, import.meta.url), "utf8");
const build = (src, name) => {
  const r = compile(src, { name });
  assert.ok(r.ok, r.errors?.map(formatError).join("\n"));
  return r;
};

/** A host that records every call and answers with `answers[name]`. */
function host(answers = {}) {
  const calls = [];
  const api = new Proxy({}, {
    get: (_, name) => (...args) => { calls.push([name, ...args]); return answers[name]?.(...args); },
    has: () => true,
  });
  return { api, calls, named: n => calls.filter(c => c[0] === n) };
}

// ---- failure modes ----

test("an endless loop runs out of fuel, switches the script off and leaves the exact count", () => {
  const s = load(["L:", ["JMP", "L"]]);
  const r = s.start({ fuel: 1000 });
  assert.equal(r.code, ERROR.FUEL);
  assert.equal(r.name, "FUEL");
  assert.equal(r.ops, 1000);
  assert.equal(s.state, "disabled");
  assert.equal(s.fault.code, ERROR.FUEL);
});

test("fuel is charged per instruction cost: exactly enough passes, one less stops before the last instruction", () => {
  const items = [["PUSHB", 1], ["DROP"], ["HALT"]];
  assert.equal(load(items).start({ fuel: 3 }).ok, true);
  const r = load(items).start({ fuel: 2 });
  assert.equal(r.code, ERROR.FUEL);
  assert.equal(r.ops, 2);
  assert.equal(load(items).start({ fuel: 3 }).cost, 3);
});

test("the time hook checks entry, periodic instruction boundaries and successful return", () => {
  const s = load(["L:", ["JMP", "L"]]);
  let asked = 0;
  const r = s.start({ fuel: 1e9, timeUp: () => { asked += 1; return asked === 4; } });
  assert.equal(r.code, ERROR.TIME);
  assert.equal(r.ops, 3 * LIMITS.timeCheckEvery);
  assert.equal(asked, 4);
  const short = load([["HALT"]]).start({ timeUp: () => true });
  assert.equal(short.code, ERROR.TIME);
  assert.equal(short.ops, 0);
  let shortChecks = 0;
  const end = load([["HALT"]]).start({ timeUp: () => { shortChecks += 1; return shortChecks === 2; } });
  assert.equal(end.code, ERROR.TIME);
  assert.equal(end.ops, 1);
  assert.equal(shortChecks, 2);
});

test("a short handler whose host call exceeds its deadline faults at successful return", () => {
  const script = load([["HALT"], "H:", ["CALLAPI", 2, 0], ["DROP"], ["HALT"]], { handlers: [{ event: EV("frame"), argc: 0, entry: 1 }] });
  assert.ok(script.start().ok);
  let elapsed = 0;
  const r = script.dispatch("frame", [], { api: { "korg.millis": () => { elapsed = 6; return elapsed; } }, timeUp: () => elapsed > 5 });
  assert.equal(r.code, ERROR.TIME);
  assert.equal(r.ops, 3);
  assert.equal(script.state, "disabled");
  assert.equal(script.fault.event, "frame");
});

test("a top-level RET also checks elapsed time and preserves the operation count", () => {
  let checks = 0;
  const script = load([["CALLAPI", 2, 0], ["RET"]]);
  const r = script.start({ timeUp: () => { checks += 1; return checks === 2; } });
  assert.equal(r.code, ERROR.TIME);
  assert.equal(r.ops, 2);
});

test("array access outside the array is refused, negative indices too", () => {
  const read = i => load([["PUSHK", 0], ["ALOAD", 2, 4], ["DROP"], ["HALT"]], { consts: [i] });
  assert.equal(read(3).start().ok, true);
  for (const i of [4, 7, -1, -2147483648]) assert.equal(read(i).start().code, ERROR.BOUNDS, `index ${i}`);
  const write = i => load([["PUSHK", 0], ["PUSHB", 9], ["ASTORE", 2, 4], ["HALT"]], { consts: [i] });
  assert.equal(write(0).start().ok, true);
  assert.equal(write(4).start().code, ERROR.BOUNDS);
  const s = load([["PUSHB", 1], ["PUSHB", 9], ["ASTORE", 2, 4], ["HALT"]]);
  s.start();
  assert.equal(s.vars[3], 9, "a write lands at base + index and nowhere else");
  assert.equal(s.vars.filter(v => v !== 0).length, 1);
});

test("variable slots up to 65535 are addressed, the one after the last is refused, in the verifier and at run time", () => {
  const top = LIMITS.vars - 1;
  const s = load([["PUSHB", 7], ["STORE", top], ["LOAD", top], ["DROP"], ["HALT"]], { varCount: LIMITS.vars });
  assert.equal(s.vars.length, LIMITS.vars);
  assert.equal(s.start().ok, true);
  assert.equal(s.vars[top], 7);
  assert.equal(s.vars.filter(v => v !== 0).length, 1, "the write lands in that slot and nowhere else");
  for (const [varCount, slot] of [[LIMITS.vars - 1, top], [256, 256], [256, 300], [1000, 1000], [1000, 65535]]) {
    for (const items of [[["LOAD", slot], ["DROP"], ["HALT"]], [["PUSHB", 1], ["STORE", slot], ["HALT"]]]) {
      rejects(blobOf(items, { varCount }), ERROR.BAD_VAR);
      assert.equal(load(items, { varCount }, { verify: false }).start().code, ERROR.BAD_VAR, `slot ${slot} of ${varCount}`);
    }
  }
  assert.equal(load([["LOAD", 999], ["DROP"], ["HALT"]], { varCount: 1000 }).start().ok, true, "a slot a byte could not name");
});

test("an array can be longer than 255: element 0 and the last one work, the one after it is a bounds error", () => {
  const run = idx => load([["PUSHK", 0], ["PUSHB", 5], ["ASTORE", 300, 1000], ["PUSHK", 0], ["ALOAD", 300, 1000], ["DROP"], ["HALT"]], { varCount: 1300, consts: [idx] });
  for (const idx of [0, 255, 256, 999]) {
    const s = run(idx);
    assert.equal(s.start().ok, true, `index ${idx}`);
    assert.equal(s.vars[300 + idx], 5, "lands at base + index");
    assert.equal(s.vars.filter(v => v !== 0).length, 1);
  }
  for (const idx of [1000, 1300, 65535, -1]) assert.equal(run(idx).start().code, ERROR.BOUNDS, `index ${idx}`);
  const edge = (base, length, varCount) => [[["PUSHB", 0], ["ALOAD", base, length], ["DROP"], ["HALT"]], { varCount }];
  const whole = edge(0, LIMITS.arrayLength, LIMITS.vars);
  assert.equal(load(...whole).start().ok, true, "an array of 65535 slots at the bottom of a full area");
  for (const [base, length, varCount] of [[2, LIMITS.arrayLength, LIMITS.vars], [300, 1001, 1300], [0, 0, 1300], [1300, 1, 1300]]) {
    const [code, o] = edge(base, length, varCount);
    rejects(blobOf(code, o), ERROR.BAD_VAR);
    assert.equal(load(code, o, { verify: false }).start().code, ERROR.BAD_VAR, `${base}+${length} of ${varCount}`);
  }
});

test("a format 1 blob is refused with the version error, not as truncated or damaged", () => {
  const v1 = new Uint8Array(48 + 4);
  const dv = new DataView(v1.buffer);
  dv.setUint32(0, MAGIC, true);
  dv.setUint16(4, 1, true);
  dv.setUint16(6, 1, true);
  dv.setUint32(8, v1.length, true);
  dv.setUint32(12, crc32(v1, 16, v1.length), true);
  assert.equal(rejects(v1, ERROR.FORMAT_VERSION).name, "FORMAT_VERSION");
  assert.match(rejects(v1, ERROR.FORMAT_VERSION).message, /Block 1, diese Laufzeit 2/);
  assert.equal(rejects(v1.slice(0, 8), ERROR.FORMAT_VERSION).name, "FORMAT_VERSION");
});

test("the header carries the variable count as 32 bits and refuses flag bits it does not know", () => {
  const d = decodeBlob(blobOf([["HALT"]], { varCount: LIMITS.vars }));
  assert.equal(d.header.varCount, 65536);
  const bytes = blobOf([["HALT"]]);
  const at = HEADER.fields.find(f => f.name === "flags").offset;
  bytes[at] = 2;
  new DataView(bytes.buffer).setUint32(12, crc32(bytes, 16, bytes.length), true);
  rejects(bytes, ERROR.BAD_SIZE);
});

test("the editor marks a block as probed without changing anything else, and the marked block still loads", () => {
  const plain = blobOf([["HALT"]], { name: "marked" });
  assert.equal(isProbed(plain), false, "a compiled block is not marked");
  const marked = markProbed(plain);
  assert.equal(isProbed(marked), true);
  assert.equal(isProbed(plain), false, "the original is not touched");
  assert.equal(marked.length, plain.length);
  const differing = [...marked].flatMap((b, i) => (b === plain[i] ? [] : [i]));
  const flagsAt = HEADER.fields.find(f => f.name === "flags").offset;
  const checksumAt = HEADER.fields.find(f => f.name === "checksum").offset;
  assert.deepEqual(differing.filter(i => i < checksumAt || i >= checksumAt + 4), [flagsAt], "only the flag and the checksum differ");
  assert.equal(decodeBlob(marked).ok, true);
  assert.deepEqual(markProbed(marked), marked, "marking twice changes nothing");
  assert.equal(loadScript(marked).ok, true);
});

test("division and modulo by zero return their error, the rest of the arithmetic wraps and truncates", () => {
  const calc = (op, a, b) => {
    const s = load([["PUSHK", 0], ["PUSHK", 1], [op], ["STORE", 0], ["HALT"]], { consts: [a, b] });
    const r = s.start();
    return r.ok ? s.vars[0] : r.code;
  };
  assert.equal(calc("DIV", 1, 0), ERROR.DIV_ZERO);
  assert.equal(calc("MOD", 1, 0), ERROR.DIV_ZERO);
  const cases = [
    ["ADD", 2147483647, 1, -2147483648], ["SUB", -2147483648, 1, 2147483647], ["MUL", 65536, 65536, 0], ["MUL", 123456789, 987654321, Math.imul(123456789, 987654321)],
    ["DIV", -7, 2, -3], ["DIV", 7, -2, -3], ["DIV", -2147483648, -1, -2147483648], ["MOD", -7, 2, -1], ["MOD", 7, -2, 1], ["MOD", -2147483648, -1, 0],
    ["AND", 12, 10, 8], ["OR", 12, 10, 14], ["XOR", 12, 10, 6], ["SHL", 1, 33, 2], ["SHL", 1, 31, -2147483648], ["SHR", -8, 1, -4], ["SHR", -1, 31, -1],
    ["EQ", 3, 3, 1], ["NE", 3, 3, 0], ["LT", -1, 0, 1], ["LE", 2, 2, 1], ["GT", 2, 3, 0], ["GE", 3, 3, 1],
  ];
  for (const [op, a, b, want] of cases) assert.equal(calc(op, a, b), want, `${op}(${a}, ${b})`);
});

test("the operand stack: the verifier refuses over and underflow, the VM catches them when it is not told to verify", () => {
  const under = [["ADD"], ["HALT"]];
  const e = rejects(blobOf(under), ERROR.STACK);
  assert.equal(e.offset, 0);
  assert.equal(load(under, {}, { verify: false }).start().code, ERROR.STACK);

  const over = [...Array.from({ length: LIMITS.stack + 1 }, () => ["PUSHB", 1]), ...Array.from({ length: LIMITS.stack + 1 }, () => ["DROP"]), ["HALT"]];
  rejects(blobOf(over), ERROR.STACK);
  const r = load(over, {}, { verify: false }).start();
  assert.equal(r.code, ERROR.STACK);
  assert.equal(r.ops, LIMITS.stack);

  const grow = ["L:", ["PUSHB", 1], ["JMP", "L"]];
  rejects(blobOf(grow), ERROR.STACK_MISMATCH);
  assert.equal(load(grow, {}, { verify: false }).start({ fuel: 1e6 }).code, ERROR.STACK);
});

test("the verifier checks balance at HALT and RET, at joins and against the declared depth", () => {
  rejects(blobOf([["PUSHB", 1], ["HALT"]]), ERROR.STACK_MISMATCH);
  rejects(blobOf([["PUSHB", 0], ["JZ", "A"], ["PUSHB", 1], "A:", ["HALT"]]), ERROR.STACK_MISMATCH);
  const deep = [["PUSHB", 1], ["PUSHB", 2], ["PUSHB", 3], ["DROP"], ["DROP"], ["DROP"], ["HALT"]];
  assert.equal(loadScript(blobOf(deep, { stackMax: 3 })).ok, true);
  rejects(blobOf(deep, { stackMax: 2 }), ERROR.STACK_MISMATCH);
  rejects(blobOf([["CALL", "F", 0], ["DROP"], ["HALT"], "F:", ["PUSHB", 1], ["PUSHB", 2], ["RET"]]), ERROR.STACK_MISMATCH);
});

test("a truncated blob is refused at every length", () => {
  const full = blobOf([["PUSHB", 1], ["DROP"], ["HALT"]], { strings: ["x"], consts: [1], lines: [{ offset: 0, line: 1 }] });
  assert.ok(loadScript(full).ok);
  for (let n = 0; n < full.length; n++) rejects(full.slice(0, n), ERROR.TRUNCATED);
  assert.ok(loadScript(Uint8Array.from([...full, 0xff, 0xff, 0xff])).ok, "an erased tail after totalSize is ignored");
});

test("a bad jump target is refused by the verifier and by the run-time range check", () => {
  rejects(blobOf([["JMP", 9999], ["HALT"]]), ERROR.BAD_JUMP);
  rejects(blobOf([["PUSHB", 1], ["JZ", 1], ["HALT"]]), ERROR.BAD_JUMP);
  rejects(blobOf([["PUSHB", 3], ["JMP", 1], ["HALT"]]), ERROR.BAD_JUMP);
  rejects(blobOf([["PUSHB", 1], ["DROP"]]), ERROR.BAD_JUMP);
  const r = load([["JMP", 9999], ["HALT"]], {}, { verify: false }).start();
  assert.equal(r.code, ERROR.BAD_JUMP);
  rejects(blobOf([["JMP", "A"], ["HALT"], "A:"]), ERROR.BAD_JUMP);
});

test("a constant, text or variable that is not there is refused, and caught at run time", () => {
  for (const [items, code] of [
    [[["PUSHK", 1], ["DROP"], ["HALT"]], ERROR.BAD_CONST],
    [[["PUSHS", 0], ["DROP"], ["HALT"]], ERROR.BAD_STRING],
    [[["LOAD", 8], ["DROP"], ["HALT"]], ERROR.BAD_VAR],
    [[["PUSHB", 1], ["STORE", 200], ["HALT"]], ERROR.BAD_VAR],
    [[["PUSHB", 0], ["ALOAD", 6, 4], ["DROP"], ["HALT"]], ERROR.BAD_VAR],
    [[["PUSHB", 0], ["ALOAD", 0, 0], ["DROP"], ["HALT"]], ERROR.BAD_VAR],
  ]) {
    const bytes = blobOf(items, { consts: [5] });
    rejects(bytes, code);
    assert.equal(load(items, { consts: [5] }, { verify: false }).start().code, code);
  }
});

test("an unknown opcode and a cut-off operand are refused, and caught at run time", () => {
  for (const [code, want] of [[[0x7f], ERROR.BAD_OPCODE], [[OP.PUSHB], ERROR.TRUNCATED], [[OP.JMP, 0], ERROR.TRUNCATED], [[OP.PUSHB, 1, OP.DROP, 34], ERROR.BAD_OPCODE]]) {
    const e = rejects(encodeBlob({ code }), want);
    assert.equal(typeof e.offset, "number");
  }
  const r = loadScript(encodeBlob({ code: [OP.PUSHB, 1, OP.DROP, 34] }), { verify: false }).script.start();
  assert.equal(r.code, ERROR.BAD_OPCODE);
  assert.equal(r.offset, 3);
  assert.equal(loadScript(encodeBlob({ code: [OP.PUSHB] }), { verify: false }).script.start().code, ERROR.TRUNCATED);
});

test("wrong format version, wrong API version, wrong magic, bad checksum, sizes that do not fit", () => {
  const good = blobOf([["HALT"]]);
  rejects(encodeBlob({ code: [0], formatVersion: 1 }), ERROR.FORMAT_VERSION);
  rejects(encodeBlob({ code: [0], formatVersion: 3 }), ERROR.FORMAT_VERSION);
  rejects(encodeBlob({ code: [0], apiVersion: 99 }), ERROR.API_VERSION);
  rejects(encodeBlob({ code: [0], apiVersion: 0 }), ERROR.API_VERSION);
  const magic = good.slice();
  magic[0] ^= 1;
  rejects(magic, ERROR.MAGIC);
  const rot = good.slice();
  rot[rot.length - 1] ^= 1;
  rejects(rot, ERROR.CHECKSUM);
  const size = good.slice();
  new DataView(size.buffer).setUint32(8, good.length + 4, true);
  rejects(size, ERROR.BAD_SIZE);
  rejects(encodeBlob({ code: [0], varCount: LIMITS.vars + 1 }), ERROR.LIMITS);
  rejects(encodeBlob({ code: [0], stackMax: LIMITS.stack + 1 }), ERROR.LIMITS);
  const sealed = bytes => { new DataView(bytes.buffer).setUint32(12, crc32(bytes, 16, bytes.length), true); return bytes; };
  const strings = blobOf([["HALT"]], { strings: ["ab"] });
  const slotAt = HEADER.size + decodeBlob(strings).header.handlerCount * 4;
  const noEnd = strings.slice();
  noEnd[slotAt + 31] = 0x41;
  rejects(sealed(noEnd), ERROR.BAD_STRING);
  const unprintable = strings.slice();
  unprintable[slotAt] = 0x07;
  rejects(sealed(unprintable), ERROR.BAD_STRING);
  const leftover = strings.slice();
  leftover[slotAt + 5] = 0x41;
  rejects(sealed(leftover), ERROR.BAD_STRING);
});

test("an unknown API id and a wrong argument count are refused, and caught at run time", () => {
  const unknown = [["CALLAPI", 99, 0], ["DROP"], ["HALT"]];
  rejects(blobOf(unknown), ERROR.API_UNKNOWN);
  assert.equal(load(unknown, {}, { verify: false }).start().code, ERROR.API_UNKNOWN);
  const few = [["PUSHB", 1], ["CALLAPI", 1, 1], ["DROP"], ["HALT"]];
  rejects(blobOf(few, { handlers: [{ event: EV("frame"), argc: 0, entry: 0 }] }), ERROR.API_ARGC);
  const opts = { verify: false };
  const s = load([["HALT"], "H:", ["PUSHB", 1], ["CALLAPI", 1, 1], ["DROP"], ["HALT"]], { handlers: [{ event: EV("frame"), argc: 0, entry: 1 }] }, opts);
  s.start();
  assert.equal(s.dispatch("frame").code, ERROR.API_ARGC);
});

test("an API entry is refused in an event it is not meant for, an argument out of range or a text index that is not there", () => {
  const ledInStart = [["PUSHB", 1], ["PUSHB", 1], ["CALLAPI", 1, 2], ["DROP"], ["HALT"]];
  const e = rejects(blobOf(ledInStart), ERROR.API_EVENT);
  assert.match(e.message, /korg\.led im Ereignis start/);
  assert.equal(load(ledInStart, {}, { verify: false }).start().code, ERROR.API_EVENT);

  const handler = args => load([["HALT"], "H:", ...args, ["DROP"], ["HALT"]], { consts: [200, 88, -1], strings: ["hi"], handlers: [{ event: EV("frame"), argc: 0, entry: 1 }] });
  const calls = host();
  const ok = handler([["PUSHB", 87], ["PUSHB", 255], ["CALLAPI", 1, 2]]);
  ok.start();
  assert.equal(ok.dispatch("frame", [], { api: calls.api }).ok, true);
  assert.deepEqual(calls.calls, [["korg.led", 87, 255]]);
  for (const [first, second] of [[["PUSHK", 1], ["PUSHB", 0]], [["PUSHK", 2], ["PUSHB", 0]], [["PUSHB", 0], ["PUSHK", 2]]]) {
    const s = handler([first, second, ["CALLAPI", 1, 2]]);
    s.start();
    const r = s.dispatch("frame", [], { api: calls.api });
    assert.equal(r.code, ERROR.API_ARG);
    assert.match(r.message, /korg\.led/);
  }
  const text = handler([["PUSHS", 0], ["PUSHB", 0], ["PUSHB", 0], ["CALLAPI", 17, 3]]);
  text.start();
  assert.equal(text.dispatch("frame", [], { api: calls.api }).ok, true);
  assert.deepEqual(calls.calls.at(-1), ["korg.display.text", "hi", 0, 0], "the host gets the text, not its index");
  const wrong = handler([["PUSHB", 3], ["PUSHB", 0], ["PUSHB", 0], ["CALLAPI", 17, 3]]);
  wrong.start({ api: calls.api });
  assert.equal(wrong.dispatch("frame", [], { api: calls.api }).code, ERROR.BAD_STRING);
});

test("a host function can end the run with a contract code; a host function that throws otherwise is a bug and propagates", () => {
  const items = [["HALT"], "H:", ["CALLAPI", 2, 0], ["DROP"], ["HALT"]];
  const o = { handlers: [{ event: EV("frame"), argc: 0, entry: 1 }] };
  const s = load(items, o);
  s.start();
  const r = s.dispatch("frame", [], { api: { "korg.millis": () => { throw new ScriptFault(ERROR.API_ARG, "kaputt"); } } });
  assert.equal(r.code, ERROR.API_ARG);
  const t = load(items, o);
  t.start();
  assert.throws(() => t.dispatch("frame", [], { api: { "korg.millis": () => { throw new TypeError("bug"); } } }), TypeError);
});

test("calls are bounded: recursion is refused by the verifier, caught by the VM, and the depth is limited", () => {
  rejects(blobOf([["CALL", "F", 0], ["DROP"], ["HALT"], "F:", ["CALL", "F", 0], ["RET"]]), ERROR.RECURSION);
  rejects(blobOf([["CALL", "F", 0], ["DROP"], ["HALT"], "F:", ["CALL", "G", 0], ["RET"], "G:", ["CALL", "F", 0], ["RET"]]), ERROR.RECURSION);
  const r = load([["CALL", "F", 0], ["DROP"], ["HALT"], "F:", ["CALL", "F", 0], ["RET"]], {}, { verify: false }).start();
  assert.equal(r.code, ERROR.CALL_DEPTH);
  const chain = n => [
    ["CALL", "F1", 0], ["DROP"], ["HALT"],
    ...Array.from({ length: n }, (_, i) => [`F${i + 1}:`, ...(i + 1 < n ? [["CALL", `F${i + 2}`, 0]] : [["PUSHB", 0]]), ["RET"]]).flat(),
  ];
  const ok = chain(LIMITS.callDepth);
  assert.equal(loadScript(blobOf(ok)).ok, true);
  rejects(blobOf(chain(LIMITS.callDepth + 1)), ERROR.CALL_DEPTH);
});

test("a function call hands arguments to the callee and the result back", () => {
  const s = load([
    ["PUSHB", 7], ["PUSHB", 5], ["CALL", "SUB", 2], ["STORE", 0], ["HALT"],
    "SUB:", ["STORE", 2], ["STORE", 1], ["LOAD", 1], ["LOAD", 2], ["SUB"], ["RET"],
  ]);
  assert.equal(s.start().ok, true);
  assert.equal(s.vars[0], 2);
});

test("the handler table: unknown event, the body as a handler, a duplicate, too many arguments, a bad entry", () => {
  const code = [["HALT"], "H:", ["STORE", 1], ["STORE", 0], ["HALT"]];
  const make = handlers => blobOf(code, { handlers });
  assert.ok(loadScript(make([{ event: EV("knob"), argc: 2, entry: 1 }])).ok);
  assert.ok(loadScript(blobOf([["HALT"], "H:", ["STORE", 0], ["HALT"]], { handlers: [{ event: EV("knob"), argc: 1, entry: 1 }] })).ok);
  rejects(blobOf([["HALT"], "H:", ["HALT"]], { handlers: [{ event: EV("knob"), argc: 1, entry: 1 }] }), ERROR.STACK_MISMATCH);
  rejects(make([{ event: 99, argc: 0, entry: 1 }]), ERROR.BAD_HANDLER);
  rejects(make([{ event: 0, argc: 0, entry: 1 }]), ERROR.BAD_HANDLER);
  rejects(make([{ event: EV("frame"), argc: 0, entry: 1 }, { event: EV("frame"), argc: 0, entry: 1 }]), ERROR.BAD_HANDLER);
  rejects(make([{ event: EV("knob"), argc: 3, entry: 1 }]), ERROR.BAD_HANDLER);
  rejects(make([{ event: EV("frame"), argc: 0, entry: 99 }]), ERROR.BAD_HANDLER);
  rejects(blobOf(code, { entry: 2 }), ERROR.BAD_HANDLER);
});

test("the line table must be ordered, inside the code and on instruction starts", () => {
  const code = [["PUSHB", 1], ["DROP"], ["HALT"]];
  assert.ok(loadScript(blobOf(code, { lines: [{ offset: 0, line: 1 }, { offset: 2, line: 2 }] })).ok);
  rejects(blobOf(code, { lines: [{ offset: 2, line: 1 }, { offset: 0, line: 2 }] }), ERROR.BAD_LINES);
  rejects(blobOf(code, { lines: [{ offset: 1, line: 1 }] }), ERROR.BAD_LINES);
  rejects(blobOf(code, { lines: [{ offset: 99, line: 1 }] }), ERROR.BAD_LINES);
  rejects(blobOf(code, { lines: [{ offset: 0, line: 0 }] }), ERROR.BAD_LINES);
  assert.equal(lineAt([{ offset: 0, line: 3 }, { offset: 4, line: 5 }], 3), 3);
  assert.equal(lineAt([{ offset: 0, line: 3 }, { offset: 4, line: 5 }], 4), 5);
  assert.equal(lineAt([], 0), 0);
});

test("a fault names the source line of the instruction that caused it", () => {
  const r = build("let a = 0;\nlet b = 5;\nlet c = b / a;\n", "line");
  const l = loadScript(r.blob);
  const res = l.script.start();
  assert.equal(res.code, ERROR.DIV_ZERO);
  assert.equal(res.line, 3);
  assert.equal(l.script.fault.line, 3);
});

test("events: arguments arrive in order, a handler that takes fewer gets the first ones, an unarmed script ignores events", () => {
  const items = [["HALT"], "H:", ["STORE", 1], ["STORE", 0], ["HALT"]];
  const s = load(items, { handlers: [{ event: EV("knob"), argc: 2, entry: 1 }] });
  assert.equal(s.dispatch("knob", [3, 4]).handled, false, "not armed before start");
  s.start();
  assert.equal(s.dispatch("knob", [3, 4]).handled, true);
  assert.deepEqual([s.vars[0], s.vars[1]], [3, 4]);
  const t = load([["HALT"], "H:", ["STORE", 0], ["HALT"]], { handlers: [{ event: EV("knob"), argc: 1, entry: 1 }] });
  t.start();
  t.dispatch("knob", [9, 8]);
  assert.equal(t.vars[0], 9);
  assert.equal(t.dispatch("encoder", [1, 1]).handled, false, "no handler for this event");
  assert.throws(() => t.dispatch("nonsense"), /no such event/);
  assert.throws(() => t.dispatch("start"), /no such event/);
});

test("an error in start leaves the handlers inactive and the script switched off", () => {
  const src = "let x = 1 / (2 - 2);\nkorg.onEvent(\"frame\", () => { korg.led(1, 1); });\n";
  const r = compile(src);
  assert.equal(r.ok, false, "a constant division by zero is caught at compile time");
  const ok = build("let z = 0;\nlet x = 1 / z;\nkorg.onEvent(\"frame\", () => { korg.led(1, 1); });\n", "faulty");
  const rt = new ScriptRuntime({ now: () => 0 });
  const added = rt.add(ok.blob);
  assert.equal(added.ok, false);
  assert.equal(added.error.code, ERROR.DIV_ZERO);
  assert.equal(added.script.state, "disabled");
  const h = host();
  const f = new ScriptRuntime({ now: () => 0, api: h.api });
  f.add(ok.blob);
  f.frame();
  assert.equal(h.calls.length, 0, "the handler never ran");
  assert.equal(f.status().scripts[0].fault.name, "DIV_ZERO");
});

test("two scripts: only the faulty one is switched off, the other keeps running", () => {
  const good = build("let n = 0;\nkorg.onEvent(\"frame\", () => { n += 1; korg.led(5, n); });\n", "good");
  const bad = build("let k = 0;\nkorg.onEvent(\"frame\", () => {\n  while (true) { k += 1; }\n});\n", "bad");
  const h = host();
  const rt = new ScriptRuntime({ now: () => 0, api: h.api, fuel: 5000 });
  assert.ok(rt.add(good.blob).ok);
  assert.ok(rt.add(bad.blob).ok);
  const first = rt.frame();
  assert.equal(first.faults.length, 1);
  assert.equal(first.faults[0].script, "bad");
  assert.equal(first.faults[0].name, "FUEL");
  assert.equal(first.faults[0].line, 3);
  assert.equal(first.faults[0].event, "frame");
  rt.frame();
  rt.frame();
  assert.deepEqual(h.named("korg.led").map(c => c[2]), [1, 2, 3]);
  const st = rt.status();
  assert.deepEqual(st.scripts.map(s => s.state), ["armed", "disabled"]);
  assert.equal(st.scripts[1].fault.code, ERROR.FUEL);
});

test("the variables of all scripts share one budget: a script that does not fit is refused with a German message and takes nothing", () => {
  const rt = new ScriptRuntime({ now: () => 0, varSlots: 100 });
  const sized = n => build(`const a = new Array(${n});`, `s${n}`).blob;
  assert.ok(rt.add(sized(60)).ok);
  assert.equal(rt.slotsUsed, 60);
  const refused = rt.add(sized(41));
  assert.equal(refused.ok, false);
  assert.equal(refused.error.code, ERROR.VARS_BUDGET);
  assert.match(refused.error.message, /Variablenbudget aller Plugins reicht nicht: „s41“ braucht 41 Variablenplätze \(0.2 KiB\), frei sind noch 40 von 100/);
  assert.equal(rt.slotsUsed, 60);
  assert.equal(rt.status().scripts.length, 1);
  assert.ok(rt.add(sized(40)).ok, "what the refused script did not take is still free");
  assert.deepEqual(rt.status().slots, { used: 100, budget: 100 });
  assert.equal(rt.add(sized(1)).error.code, ERROR.VARS_BUDGET);

});

test("blocks, variables and entries share 128 KiB; an appendix costs no pool space", () => {
  const metadata = contract.SCRIPT_ENTRY.size;
  const empty = blobOf([["HALT"]], { varCount: 0 });
  const vars = (128 * 1024 - empty.length - metadata) / 4;
  const fullBlob = blobOf([["HALT"]], { varCount: vars });
  const bytes = Uint8Array.from([...fullBlob, ...new TextEncoder().encode("source appendix")]);
  const rt = new ScriptRuntime({ now: () => 0 });
  const added = rt.add(bytes);
  assert.ok(added.ok, added.error?.message);
  assert.equal(rt.slotsUsed, vars);
  assert.equal(rt.bytesUsed, 128 * 1024);
  assert.deepEqual(rt.status().memory, { used: 128 * 1024, budget: 128 * 1024 });
  const before = rt.status();
  const refused = rt.add(empty);
  assert.equal(refused.error.name, "POOL_BUDGET");
  assert.match(refused.error.message, /Plugin-Budget aller Plugins reicht nicht/);
  assert.deepEqual(rt.status(), before);
  assert.equal(new ScriptRuntime({ now: () => 0 }).add(blobOf([["HALT"]], { varCount: vars + 1 })).error.name, "POOL_BUDGET");
});

test("a pool refusal happens before variable allocation or start", t => {
  const bytes = blobOf([["CALLAPI", 2, 0], ["DROP"], ["HALT"]], { varCount: 33 });
  const needed = bytes.length + 33 * 4 + contract.SCRIPT_ENTRY.size;
  let allocations = 0;
  let calls = 0;
  const original = globalThis.Int32Array;
  globalThis.Int32Array = new Proxy(original, {
    construct(target, args) { if (args[0] === 33) allocations += 1; return Reflect.construct(target, args); },
  });
  t.after(() => { globalThis.Int32Array = original; });
  const rt = new ScriptRuntime({ now: () => 0, scriptBytes: needed - 1, api: { "korg.millis": () => { calls += 1; return 1; } } });
  const result = rt.add(bytes);
  assert.equal(result.ok, false);
  assert.equal(result.error.name, "POOL_BUDGET");
  assert.equal(allocations, 0);
  assert.equal(calls, 0);
  assert.equal(rt.scripts.length, 0);
  assert.deepEqual(rt.status().memory, { used: 0, budget: needed - 1 });
});

test("a smaller test pool is allowed but cannot bypass the 128 KiB limit", () => {
  for (const scriptBytes of [-1, 0.5, NaN, Infinity, 128 * 1024 + 1]) {
    assert.throws(() => new ScriptRuntime({ scriptBytes }), RangeError);
  }
  const rt = new ScriptRuntime({ now: () => 0, scriptBytes: 0 });
  assert.equal(rt.add(blobOf([["HALT"]], { varCount: 0 })).error.name, "POOL_BUDGET");
});

test("script count grows past sixteen and stops only at the shared pool", () => {
  const bytes = blobOf([["HALT"]], { varCount: 0 });
  const each = bytes.length + contract.SCRIPT_ENTRY.size;
  const rt = new ScriptRuntime({ now: () => 0, scriptBytes: each * 20 });
  for (let i = 0; i < 20; i++) {
    const added = rt.add(blobOf([["HALT"]], { name: `script${i}`, varCount: 0 }));
    assert.ok(added.ok, added.error?.message);
    assert.equal(added.index, i);
  }
  assert.equal(rt.status().scripts.length, 20);
  assert.equal(rt.bytesUsed, each * 20);
  assert.equal(rt.add(bytes).error.name, "POOL_BUDGET");
});

test("a disabled script retains its block, variables and entry allocation", () => {
  const bytes = blobOf([["PUSHB", 1], ["PUSHB", 0], ["DIV"], ["STORE", 0], ["HALT"]]);
  const each = bytes.length + 8 * 4 + contract.SCRIPT_ENTRY.size;
  const rt = new ScriptRuntime({ now: () => 0, scriptBytes: each });
  const result = rt.add(bytes);
  assert.equal(result.ok, false);
  assert.equal(result.error.name, "DIV_ZERO");
  assert.equal(rt.bytesUsed, each);
  assert.equal(rt.slotsUsed, 8);
  assert.equal(rt.status().scripts[0].state, "disabled");
  assert.equal(rt.add(blobOf([["HALT"]], { varCount: 0 })).error.name, "POOL_BUDGET");
});

test("the frame budget ends a script that keeps the UiTask too long; one slow handler under it only counts", () => {
  const slow = build("let k = 0;\nkorg.onEvent(\"frame\", () => { while (true) { k += 1; } });\n", "slow");
  let t = 0;
  const rt = new ScriptRuntime({ now: () => (t += 1), fuel: 1e9, frameMs: 5 });
  rt.add(slow.blob);
  const r = rt.frame();
  assert.equal(r.faults[0].name, "TIME");

  const fine = build("let k = 0;\nkorg.onEvent(\"frame\", () => { k += 1; });\n", "fine");
  let u = 0;
  const rt2 = new ScriptRuntime({ now: () => (u += 0.6), handlerWarnMs: 0.5, frameMs: 100 });
  rt2.add(fine.blob);
  rt2.frame();
  const st = rt2.status().scripts[0];
  assert.equal(st.state, "armed");
  assert.equal(st.slowHandlers, 1);
  assert.equal(st.slowest.event, "frame");
});

test("status retains the highest elapsed milliseconds separately for each handler", () => {
  const r = build([
    'korg.onEvent("ready", () => { korg.millis(); });',
    'korg.onEvent("buttonPress", () => { korg.millis(); });',
    'korg.onEvent("frame", () => { korg.millis(); });',
  ].join("\n"), "times");
  let clock = 0;
  const durations = [2, 3, 5, 1, 4, 7, 1];
  const rt = new ScriptRuntime({ now: () => clock, frameMs: 100, api: { "korg.millis": () => { clock += durations.shift(); return clock; } } });
  assert.ok(rt.add(r.blob).ok);
  rt.post("buttonPress", 1);
  rt.frame();
  assert.deepEqual(rt.status().scripts[0].maxMs, { ready: 2, buttonPress: 3, frame: 5 });
  rt.post("buttonPress", 1);
  rt.frame();
  assert.deepEqual(rt.status().scripts[0].maxMs, { ready: 2, buttonPress: 3, frame: 5 });
  rt.post("buttonPress", 1);
  rt.frame();
  const snapshot = rt.status().scripts[0];
  assert.deepEqual(snapshot.maxMs, { ready: 2, buttonPress: 7, frame: 5 });
  snapshot.maxMs.buttonPress = 100;
  assert.equal(rt.status().scripts[0].maxMs.buttonPress, 7);
  assert.equal(durations.length, 0);
});

test("a frame budget covers many short handlers and only disables the one crossing it", () => {
  let clock = 0;
  const calls = [];
  const rt = new ScriptRuntime({ now: () => clock, frameMs: 5, api: { "korg.led": id => { calls.push(id); clock += 2; } } });
  for (let id = 1; id <= 4; id++) assert.ok(rt.add(build(`korg.onEvent("frame", () => { korg.led(${id}, 1); });`, `s${id}`).blob).ok);
  const first = rt.frame();
  assert.deepEqual(calls, [1, 2, 3]);
  assert.deepEqual(first.faults.map(f => [f.script, f.name, f.event]), [["s3", "TIME", "frame"]]);
  assert.deepEqual(rt.status().scripts.map(s => s.state), ["armed", "armed", "disabled", "armed"]);
  assert.deepEqual(rt.status().scripts.map(s => s.maxMs.frame ?? 0), [2, 2, 2, 0]);
  const second = rt.frame();
  assert.deepEqual(second.faults, []);
  assert.deepEqual(calls, [1, 2, 3, 4]);
});

test("a timed-out event continues with the next script and retains later events for the next frame", () => {
  let clock = 0;
  const calls = [];
  const rt = new ScriptRuntime({ now: () => clock, frameMs: 5, api: { "korg.led": (id, event) => {
    calls.push([id, event]);
    if (id === 2 && event === 7) clock += 6;
  } } });
  const source = id => [
    `korg.onEvent("ready", () => { korg.led(${id}, 100); });`,
    `korg.onEvent("buttonPress", key => { korg.led(${id}, key); });`,
    `korg.onEvent("frame", () => { korg.led(${id}, 200); });`,
  ].join("\n");
  for (let id = 1; id <= 3; id++) assert.ok(rt.add(build(source(id), `s${id}`).blob).ok);
  rt.post("buttonPress", 7);
  rt.post("buttonPress", 8);
  const first = rt.frame();
  assert.deepEqual(first.faults.map(f => [f.script, f.name]), [["s2", "TIME"]]);
  assert.deepEqual(calls, [[1, 100], [2, 100], [3, 100], [1, 7], [2, 7]]);
  assert.deepEqual(rt.queue.map(e => e.args), [[8]]);
  assert.ok(rt.add(build(source(4), "s4").blob).ok);
  assert.deepEqual(rt.frame().faults, []);
  assert.deepEqual(calls.slice(5), [[3, 7], [1, 8], [3, 8], [1, 200], [3, 200]]);
  assert.equal(rt.queue.length, 0);
  rt.frame();
  assert.deepEqual(calls.slice(10), [[4, 100], [1, 200], [3, 200], [4, 200]]);
});

test("ready is gated until the first ready frame, then stays enabled", () => {
  const calls = [];
  const rt = new ScriptRuntime({ now: () => 0, api: { "korg.led": (_, value) => calls.push(value) } });
  assert.ok(rt.add(build([
    'korg.onEvent("ready", () => { korg.led(1, 100); });',
    'korg.onEvent("buttonPress", key => { korg.led(1, key); });',
    'korg.onEvent("frame", () => { korg.led(1, 200); });',
  ].join("\n"), "gated").blob).ok);
  rt.post("buttonPress", 7);
  assert.equal(rt.frame({ ready: false }).handled, 0);
  assert.deepEqual(calls, []);
  assert.equal(rt.queue.length, 1);
  rt.frame({ ready: true });
  assert.deepEqual(calls, [100, 7, 200]);
  rt.frame({ ready: false });
  assert.deepEqual(calls, [100, 7, 200, 200]);
});

test("a time fault during ready retains the remaining ready handlers exactly once", () => {
  let clock = 0;
  const calls = [];
  const rt = new ScriptRuntime({ now: () => clock, api: { "korg.led": (id, value) => {
    calls.push([id, value]);
    if (id === 2 && value === 100) clock += 6;
  } } });
  for (let id = 1; id <= 3; id++) assert.ok(rt.add(build([
    `korg.onEvent("ready", () => { korg.led(${id}, 100); });`,
    `korg.onEvent("frame", () => { korg.led(${id}, 200); });`,
  ].join("\n"), `s${id}`).blob).ok);
  assert.deepEqual(rt.frame().faults.map(f => f.script), ["s2"]);
  assert.deepEqual(calls, [[1, 100], [2, 100]]);
  rt.frame();
  assert.deepEqual(calls, [[1, 100], [2, 100], [3, 100], [1, 200], [3, 200]]);
  rt.frame();
  assert.deepEqual(calls.slice(5), [[1, 200], [3, 200]]);
});

test("an elapsed frame before handler entry pauses without disabling an uninvolved script", () => {
  let clock = 0;
  let advancing = true;
  const calls = [];
  const rt = new ScriptRuntime({ now: () => advancing ? clock++ : clock, frameMs: 0, api: { "korg.led": id => calls.push(id) } });
  assert.ok(rt.add(build('korg.onEvent("frame", () => { korg.led(1, 1); });', "waiting").blob).ok);
  const paused = rt.frame();
  assert.deepEqual(paused.faults, []);
  assert.equal(paused.handled, 0);
  assert.equal(rt.status().scripts[0].state, "armed");
  advancing = false;
  const resumed = rt.frame();
  assert.deepEqual(resumed.faults, []);
  assert.deepEqual(calls, [1]);
});

test("events posted after the ready phase belong to the next cycle snapshot", () => {
  const calls = [];
  const rt = new ScriptRuntime({ now: () => 0, api: { "korg.led": (_, value) => {
    calls.push(value);
    if (value === 1) rt.post("buttonPress", 2);
  } } });
  assert.ok(rt.add(build('korg.onEvent("buttonPress", key => { korg.led(1, key); });', "snapshot").blob).ok);
  rt.post("buttonPress", 1);
  rt.frame();
  assert.deepEqual(calls, [1]);
  assert.deepEqual(rt.queue.map(e => e.args), [[2]]);
  rt.frame();
  assert.deepEqual(calls, [1, 2]);
});

test("the frame deadline allows exactly the configured duration", () => {
  for (const duration of [4, 5, 6]) {
    let clock = 0;
    const rt = new ScriptRuntime({ now: () => clock, frameMs: 5, api: { "korg.millis": () => { clock += duration; return clock; } } });
    assert.ok(rt.add(build('korg.onEvent("frame", () => { korg.millis(); });', "edge").blob).ok);
    const result = rt.frame();
    assert.deepEqual(result.faults.map(f => f.name), duration > 5 ? ["TIME"] : []);
  }
});

test("the event ring holds 64, counts what it drops, merges a knob turned again and keeps order", () => {
  const rt = new ScriptRuntime({ now: () => 0 });
  for (let i = 0; i < BUDGET.ring; i++) assert.equal(rt.post("buttonPress", i), true);
  assert.equal(rt.post("buttonPress", 99), false);
  assert.equal(rt.post("buttonPress", 100), false);
  assert.equal(rt.status().overflows, 2);
  assert.equal(rt.queue.length, BUDGET.ring);
  assert.deepEqual(rt.queue.slice(0, 3).map(e => e.args[0]), [0, 1, 2]);

  const k = new ScriptRuntime({ now: () => 0 });
  k.post("knob", 3, 10);
  k.post("knob", 3, 11);
  k.post("knob", 3, 12);
  k.post("knob", 4, 1);
  k.post("knob", 3, 13);
  assert.deepEqual(k.queue.map(e => e.args), [[3, 12], [4, 1], [3, 13]]);
  assert.throws(() => k.post("frame"), /cannot be posted/);
  assert.throws(() => k.post("start"), /cannot be posted/);
});

test("events reach the handlers in order, ready runs once before them, frame runs last", () => {
  const src = [
    "let order = new Array(8);",
    "let n = 0;",
    "function note(v) { order[n] = v; n += 1; }",
    "korg.onEvent(\"ready\", () => note(100));",
    "korg.onEvent(\"buttonPress\", (key) => note(key));",
    "korg.onEvent(\"frame\", () => note(200));",
  ].join("\n");
  const r = build(src, "order");
  const rt = new ScriptRuntime({ now: () => 0 });
  const a = rt.add(r.blob);
  rt.post("buttonPress", 1);
  rt.post("buttonPress", 2);
  rt.frame();
  rt.post("buttonPress", 3);
  rt.frame();
  const o = r.info.symbols.order.slot;
  assert.deepEqual(Array.from(a.script.vars.slice(o, o + 7)), [100, 1, 2, 200, 3, 200, 0]);
});

test("coverage lists the source lines that had code and never ran", () => {
  const src = [
    "let a = 0;",
    "korg.onEvent(\"buttonPress\", (key) => {",
    "  if (key == 1) {",
    "    a = 1;",
    "  } else {",
    "    a = 2;",
    "  }",
    "});",
  ].join("\n");
  const r = build(src, "cov");
  const l = loadScript(r.blob);
  const cov = new Coverage(l.script);
  l.script.start({ onStep: cov.step });
  l.script.dispatch("buttonPress", [1], { onStep: cov.step });
  const first = cov.lines();
  assert.deepEqual(first.missing, [6]);
  assert.ok(first.covered.includes(4));
  l.script.dispatch("buttonPress", [2], { onStep: cov.step });
  assert.deepEqual(cov.lines().missing, []);
  assert.deepEqual(r.info.lines.slice().sort((x, y) => x - y), first.all);
});

test("fuzz: whatever a mutated blob does after it passes the verifier, it never trips a check the verifier claims to have made", () => {
  let seed = 20261012;
  const rnd = n => { seed = (Math.imul(seed, 1103515245) + 12345) >>> 0; return (seed >>> 8) % n; };
  // The verifier does not track value types, so a number handed to a text parameter is still caught at run time.
  const allowed = new Set([ERROR.OK, ERROR.FUEL, ERROR.BOUNDS, ERROR.DIV_ZERO, ERROR.API_ARG, ERROR.BAD_STRING]);
  const seal = bytes => { new DataView(bytes.buffer).setUint32(12, crc32(bytes, 16, bytes.length), true); return bytes; };
  const events = Object.keys(Object.fromEntries([...EVENT_BY_NAME].filter(([n]) => n !== "start"))).filter(n => n !== "save");
  let verified = 0;
  let ran = 0;
  const big = [
    "const buf = new Array(3000);",
    "let at = 0;",
    "korg.onEvent(\"frame\", () => {",
    "  buf[at] = at;",
    "  at = (at + 1) % 3000;",
    "  korg.led(5, buf[(at + 2999) % 3000] & 255);",
    "});",
  ].join("\n");
  for (const [name, src] of [["klicker.js", fixture("klicker.js")], ["snake.js", fixture("snake.js")], ["bigarray", big]]) {
    const good = build(src, name).blob;
    const { header } = decodeBlob(good);
    const codeFrom = sectionOffsets(header).code;
    for (let round = 0; round < 2000; round++) {
      const bytes = good.slice();
      for (let k = 0, n = 1 + rnd(3); k < n; k++) bytes[round % 4 === 0 ? 16 + rnd(bytes.length - 16) : codeFrom + rnd(header.codeSize)] = rnd(256);
      const l = loadScript(seal(bytes));
      if (!l.ok) continue;
      verified += 1;
      const calls = host();
      const env = { api: calls.api, fuel: 4000 };
      const results = [l.script.start(env)];
      for (const ev of events) results.push(l.script.dispatch(ev, [rnd(20), rnd(1024), rnd(128)], env));
      for (const r of results) {
        ran += 1;
        assert.ok(allowed.has(r.code), `${name} round ${round}: ${r.name} ${r.message}`);
      }
    }
  }
  assert.ok(verified > 100, `only ${verified} mutants passed the verifier, the fuzz is too weak`);
  assert.ok(ran > verified);
});

// ---- programs ----

test("Korg Klicker logic: TAP counts, the display and the LED follow", () => {
  const r = build(fixture("klicker.js"), "klicker");
  const h = host();
  const rt = new ScriptRuntime({ now: () => 0, api: h.api });
  assert.ok(rt.add(r.blob).ok);
  assert.ok(rt.openApp(0));
  rt.frame();
  assert.deepEqual(h.named("korg.display.number").at(-1), ["korg.display.number", 0, 0, 16], "open draws the starting state");
  assert.deepEqual(h.named("korg.display.text").at(-1), ["korg.display.text", "Klicks", 0, 0]);
  for (const key of [3, 4, 3, 9, 3]) rt.post("buttonPress", key);
  rt.frame();
  assert.deepEqual(h.named("korg.display.number").map(c => c[1]), [0, 1, 2, 3]);
  assert.deepEqual(h.named("korg.led").map(c => [c[1], c[2]]), [[20, 255], [20, 0], [20, 255]]);
  assert.equal(rt.status().scripts[0].state, "armed");
});

test("Snake step function on a 16 x 8 grid: moving, wrapping, turning, eating, hitting itself", () => {
  const r = build(fixture("snake.js"), "snake");
  const sym = r.info.symbols;
  const h = host();
  const rt = new ScriptRuntime({ now: () => 0, api: h.api });
  const a = rt.add(r.blob);
  assert.ok(a.ok, a.error?.message);
  assert.ok(rt.openApp(0));
  const vars = a.script.vars;
  const v = n => vars[sym[n].slot];
  const at = (arr, i) => vars[sym[arr].slot + i];
  const headX = () => at("bx", v("head"));
  const headY = () => at("by", v("head"));
  const frames = n => { for (let i = 0; i < n; i++) { const f = rt.frame(); assert.deepEqual(f.faults, []); } };

  frames(1);
  assert.deepEqual([headX(), headY(), v("len")], [2, 0, 3], "open starts a new game, then the first frame runs");
  frames(1);
  assert.equal(headX(), 2, "the snake moves on every third frame");
  frames(1);
  assert.equal(headX(), 3);
  frames(3 * 13);
  assert.equal(headX(), 0, "it wraps at the right edge: 3 + 13 = 16");

  rt.post("buttonPress", 15);
  frames(3);
  assert.deepEqual([headX(), headY()], [0, 1], "Part right turns clockwise: now down");
  rt.post("buttonPress", 11);
  frames(3);
  assert.deepEqual([headX(), headY()], [1, 1], "Part left turns back to the right");

  vars[sym.fx.slot] = headX() + 1;
  vars[sym.fy.slot] = headY();
  frames(3);
  assert.equal(v("len"), 4);
  assert.equal(v("score"), 1);
  assert.notDeepEqual([v("fx"), v("fy")], [headX(), headY()], "new food is placed elsewhere");
  assert.equal(at("cell", v("fy") * 16 + v("fx")), 0, "and never on the snake");

  const cellsOn = Array.from({ length: 128 }, (_, i) => at("cell", i)).reduce((s, x) => s + x, 0);
  assert.equal(cellsOn, v("len"), "the occupancy grid and the ring buffer agree");

  // Block the cell in front of the head: the next step ends the game and starts over.
  const hx = headX();
  const hy = headY();
  vars[sym.cell.slot + hy * 16 + ((hx + 1) % 16)] = 1;
  frames(3);
  assert.deepEqual([v("len"), v("score")], [3, 0]);
  assert.deepEqual([headX(), headY()], [2, 0]);
});

test("Snake stays far inside the per-handler budget, with room left for the display", () => {
  const r = build(fixture("snake.js"), "snake");
  const h = host();
  const rt = new ScriptRuntime({ now: () => 0, api: h.api });
  rt.add(r.blob);
  rt.openApp(0);
  for (let i = 0; i < 300; i++) rt.frame();
  const st = rt.status().scripts[0];
  assert.equal(st.state, "armed");
  assert.ok(st.maxCost.frame < LIMITS.fuel / 4, `frame handler cost ${st.maxCost.frame}`);
  assert.equal(h.named("korg.display.clear").length, 301, "300 frames and the open that starts the game");
  assert.ok(r.info.vars <= LIMITS.vars);
});

test("every blob the compiler makes passes the verifier again from its bytes", () => {
  for (const name of ["klicker.js", "snake.js"]) {
    const r = build(fixture(name), name);
    const v = verify(r.blob);
    assert.ok(v.ok, v.error?.message);
    assert.equal(v.info.stackMax, r.info.stackMax);
  }
});
