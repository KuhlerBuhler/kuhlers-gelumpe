import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { API, API_VERSION, API_BY_NAME, ARRAY_HANDLE, ERROR, EVENT_BY_NAME, HEADER, LIMITS, OP } from "../../data/script/contract.mjs";
import { PRESETS } from "../../data/script/presets.mjs";
import { assemble } from "../../src/script/asm.mjs";
import { compile, formatError } from "../../src/script/compiler.mjs";
import { crc32, decodeBlob, encodeBlob, sectionOffsets } from "../../src/script/blob.mjs";
import { loadScript, ScriptFault } from "../../src/script/vm.mjs";

const hex = bytes => Buffer.from(bytes).toString("hex");
const event = name => EVENT_BY_NAME.get(name).id;
const api = name => API_BY_NAME.get(name).id;
const blob = (items, options = {}) => {
  const a = assemble(items);
  return encodeBlob({ code: a.code, lines: a.lines, varCount: 8, stackMax: LIMITS.stack, ...options });
};
const program = (source, name) => {
  const result = compile(source, { name });
  if (!result.ok) throw new Error(result.errors.map(formatError).join("\n"));
  return result.blob;
};
const mutate = (bytes, edit, checksum = true) => {
  const out = bytes.slice();
  edit(out, new DataView(out.buffer));
  if (checksum) new DataView(out.buffer).setUint32(12, crc32(out, HEADER.checksumFrom), true);
  return out;
};

function oracle(c) {
  const calls = [];
  const host = Object.fromEntries(API.map(a => [a.name, (...args) => {
    calls.push([a.name, ...args.map(v => (ArrayBuffer.isView(v) ? Array.from(v) : v))]);
    if (c.apiFaults?.[a.name]) throw new ScriptFault(c.apiFaults[a.name]);
    return c.apiReturns?.[a.name] ?? 0;
  }]));
  const env = { api: host, fuel: c.fuel ?? LIMITS.fuel };
  const scripts = [];
  const loads = [];
  const runs = [];
  const record = (r, index, name, handled) => runs.push({
    script: index, event: name, code: r.code, offset: r.offset,
    line: r.line, ops: r.ops, cost: r.cost, handled,
  });
  c.scripts.forEach((input, index) => {
    const loaded = loadScript(Buffer.from(input.blob, "hex"), { verify: input.verify !== false });
    loads.push({ ok: loaded.ok, code: loaded.ok ? 0 : loaded.error.code, offset: loaded.ok ? null : loaded.error.offset ?? null });
    scripts.push(loaded.ok ? loaded.script : null);
    if (loaded.ok) record(loaded.script.start(env), index, "start", true);
  });
  for (const e of c.events ?? []) scripts.forEach((s, index) => {
    if (s) {
      const r = s.dispatch(e.name, e.args ?? [], env);
      record(r, index, e.name, r.handled);
    }
  });
  return {
    loads, runs, calls,
    scripts: scripts.map(s => s ? {
      state: s.state, vars: Array.from(s.vars),
      fault: s.fault ? { code: s.fault.code, offset: s.fault.offset, line: s.fault.line, event: s.fault.event } : null,
    } : null),
  };
}

export function armCases() {
  const cases = [];
  const add = (name, bytes, options = {}) => {
    const scripts = Array.isArray(bytes) ? bytes.map(b => ({ blob: hex(b) })) : [{ blob: hex(bytes) }];
    cases.push({ name, scripts, ...options });
  };
  const raw = (name, items, options = {}) => {
    const { blobOptions = {}, ...rest } = options;
    add(name, blob(items, blobOptions), { ...rest, scripts: [{ blob: hex(blob(items, blobOptions)), verify: false }] });
  };

  add("stack and variables", blob([["PUSHB", 7], ["DUP"], ["STORE", 1], ["DROP"], ["LOAD", 1], ["STORE", 0], ["HALT"]]));
  const pairs = [[0, 0], [1, -1], [-7, 3], [7, -3], [-7, -3], [-2147483648, -1], [2147483647, 2147483647], [-2147483648, 2147483647], [0x12345678, 33]];
  let seed = 0x4b75686c;
  const next = () => { seed = (Math.imul(seed, 1664525) + 1013904223) | 0; return seed; };
  for (let i = 0; i < 16; i++) pairs.push([next(), next()]);
  for (const name of ["ADD", "SUB", "MUL", "DIV", "MOD", "AND", "OR", "XOR", "SHL", "SHR", "EQ", "NE", "LT", "LE", "GT", "GE"]) {
    for (const [a, b] of pairs) add(`${name} ${a} ${b}`, blob([["PUSHK", 0], ["PUSHK", 1], [name], ["STORE", 0], ["HALT"]], { consts: [a, b] }));
  }
  for (const op of ["NEG", "NOT"]) for (const value of [0, 1, -1, -2147483648, 2147483647]) {
    add(`${op} ${value}`, blob([["PUSHK", 0], [op], ["STORE", 0], ["HALT"]], { consts: [value] }));
  }
  for (const op of ["JZ", "JNZ"]) for (const condition of [0, 1, -1]) {
    add(`${op} ${condition}`, blob([["PUSHK", 0], [op, "taken"], ["PUSHB", 2], ["JMP", "done"], "taken:", ["PUSHB", 3], "done:", ["STORE", 0], ["HALT"]], { consts: [condition] }));
  }
  add("nested function calls", program("let sum = 0; function twice(a) { return a * 2; } function more(a) { return twice(a) + 1; } sum = more(7);", "calls"));
  for (const depth of [1, LIMITS.callDepth, LIMITS.callDepth + 1]) {
    const items = [["CALL", "fn0", 0], ["STORE", 0], ["HALT"]];
    for (let i = 0; i < depth; i++) items.push(`fn${i}:`, ...(i + 1 < depth ? [["CALL", `fn${i + 1}`, 0]] : [["PUSHB", 9]]), ["RET"]);
    add(`call depth ${depth}`, blob(items));
    if (depth > LIMITS.callDepth) raw("runtime call depth", items);
  }
  for (const index of [0, 255, 256, 1023, 1024, -1]) {
    add(`array index ${index}`, blob([["PUSHK", 0], ["PUSHB", 7], ["ASTORE", 400, 1024], ["PUSHK", 0], ["ALOAD", 400, 1024], ["STORE", 0], ["HALT"]], { varCount: 1424, consts: [index] }));
  }
  raw("highest variable slot", [["PUSHB", 7], ["STORE", 65535], ["LOAD", 65535], ["STORE", 0], ["HALT"]], { blobOptions: { varCount: 65536 } });

  const ui = assemble([["HALT"], "ready:", ["PUSHS", 0], ["PUSHB", 7], ["PUSHB", 9], ["CALLAPI", api("korg.display.text"), 3], ["DROP"], ["PUSHB", 3], ["PUSHB", 255], ["CALLAPI", api("korg.led"), 2], ["DROP"], ["HALT"]]);
  const uiBlob = encodeBlob({ code: ui.code, varCount: 0, stackMax: 3, strings: ["BLECH"], handlers: [{ event: event("ready"), argc: 0, entry: ui.labels.get("ready") }], lines: [{ offset: 0, line: 1 }, { offset: ui.labels.get("ready"), line: 4 }] });
  add("text and LED arguments", uiBlob, { events: [{ name: "ready", args: [] }, { name: "frame", args: [] }] });
  add("API host fault", uiBlob, { apiFaults: { "korg.display.text": ERROR.TIME }, events: [{ name: "ready", args: [] }, { name: "ready", args: [] }] });
  add("API integer return", blob([["CALLAPI", api("korg.millis"), 0], ["STORE", 0], ["HALT"]]), { apiReturns: { "korg.millis": -2147483648 } });
  const apiItems = [["HALT"], "ready:"];
  for (const a of API) {
    if (a.name === "korg.app") continue;
    for (const arg of a.args) {
      if (arg.kind === "str") apiItems.push(["PUSHS", 0]);
      else if (arg.kind === "arr") apiItems.push(["PUSHK", 0]);
      else apiItems.push(["PUSHB", arg.min <= 0 && arg.max >= 0 ? 0 : arg.min]);
    }
    apiItems.push(["CALLAPI", a.id, a.args.length], ["DROP"]);
  }
  apiItems.push(["HALT"]);
  const allApis = assemble(apiItems);
  add("every API entry", encodeBlob({ apiVersion: API_VERSION, code: allApis.code, strings: ["BLECH"], consts: [ARRAY_HANDLE.make(0, 4)], varCount: 4, stackMax: 4, handlers: [{ event: event("ready"), argc: 0, entry: allApis.labels.get("ready") }] }), { events: [{ name: "ready", args: [] }] });
  add("an app declares itself in the body", blob([["PUSHS", 0], ["PUSHS", 1], ["CALLAPI", api("korg.app"), 2], ["STORE", 0], ["HALT"]], { apiVersion: API_VERSION, strings: ["Game", "GAMES"] }), { apiReturns: { "korg.app": 3 } });
  add("a take of the display returns whether it was given", blob([["CALLAPI", api("korg.display.take"), 0], ["STORE", 0], ["CALLAPI", api("korg.display.release"), 0], ["DROP"], ["HALT"]], { apiVersion: API_VERSION }), { apiReturns: { "korg.display.take": 1 } });
  for (const fuel of [4, 7, 8, 9]) add(`API fuel ${fuel}`, blob([["CALLAPI", api("korg.millis"), 0], ["STORE", 0], ["HALT"]]), { fuel });
  const handlerBlob = items => {
    const a = assemble([["HALT"], "handler:", ...items]);
    return encodeBlob({ code: a.code, stackMax: 4, strings: ["BLECH"], handlers: [{ event: event("ready"), argc: 0, entry: a.labels.get("handler") }], lines: [{ offset: 0, line: 1 }, { offset: a.labels.get("handler"), line: 23 }] });
  };
  add("API integer bounds", handlerBlob([["PUSHB", 88], ["PUSHB", 255], ["CALLAPI", api("korg.led"), 2], ["DROP"], ["HALT"]]), { events: [{ name: "ready", args: [] }] });
  add("API text index bounds", handlerBlob([["PUSHB", 1], ["PUSHB", 0], ["PUSHB", 0], ["CALLAPI", api("korg.display.text"), 3], ["DROP"], ["HALT"]]), { events: [{ name: "ready", args: [] }] });
  const eventSource = "let total = 0; korg.onEvent(\"buttonPress\", (key) => { total += key; }); korg.onEvent(\"knob\", (index, value) => { total += index + value; }); korg.onEvent(\"frame\", () => { total += 1; });";
  const events = [{ name: "buttonPress", args: [3] }, { name: "knob", args: [2, 1023] }, { name: "frame", args: [] }, { name: "ready", args: [] }];
  add("event argument order", program(eventSource, "events"), { events });
  add("independent scripts", [program(eventSource, "first"), program(eventSource, "second")], { events });
  add("more than sixteen scripts", Array.from({ length: 33 }, (_, i) => program("let count = 0; korg.onEvent(\"frame\", () => { count += 1; });", `script${i}`)), { events: [{ name: "frame", args: [] }] });
  add("a faulty script leaves another armed", [program("let divisor = 0; let result = 1 / divisor;", "fault"), program(eventSource, "healthy")], { events });
  add("a handler fault leaves another armed", [program("let divisor = 0; let result = 0; korg.onEvent(\"frame\", () => { result = 1 / divisor; });", "fault"), program(eventSource, "healthy")], { events: [{ name: "frame", args: [] }, { name: "frame", args: [] }] });
  for (const filename of ["klicker.js", "snake.js"]) {
    const source = fs.readFileSync(new URL(`./scripts/${filename}`, import.meta.url), "utf8");
    add(filename, program(source, filename.slice(0, -3)), { events: [{ name: "ready", args: [] }, { name: "buttonPress", args: [3] }, ...Array.from({ length: 6 }, () => ({ name: "frame", args: [] }))] });
  }
  // The app plugins of the catalog, opened and played with a mix of inputs: the native VM must leave the same variables and make the same calls as the JS one.
  const frames = n => Array.from({ length: n }, () => ({ name: "frame", args: [] }));
  const played = [
    { name: "ready", args: [] }, { name: "open", args: [] }, ...frames(3),
    { name: "buttonPress", args: [28] }, { name: "buttonPress", args: [15] }, { name: "buttonPress", args: [12] }, { name: "buttonRelease", args: [12] },
    { name: "pad", args: [3, 1, 90] }, { name: "pad", args: [3, 0, 0] }, { name: "play", args: [] }, ...frames(12),
    { name: "touch", args: [300, 400, 1] }, { name: "touch", args: [340, 420, 0] }, { name: "encoder", args: [0, 1] }, { name: "buttonPress", args: [31] },
    ...frames(60), { name: "buttonPress", args: [29] }, { name: "pad", args: [11, 1, 90] }, ...frames(40), { name: "close", args: [] }, ...frames(2),
  ];
  for (const id of ["blechclicker", "settimer", "tetris", "life", "pong", "simon", "mandelbrot"]) {
    add(`plugin ${id}`, program(PRESETS.find(p => p.id === id).source, id), { events: played });
  }
  const mandelbrot = PRESETS.find(p => p.id === "mandelbrot");
  add("Mandelbrot certified interior and reset", program(mandelbrot.source, "mandelbrot"), {
    events: [
      { name: "open", args: [] },
      ...Array.from({ length: 7 }, () => ({ name: "encoder", args: [0, 1] })),
      ...frames(80),
      { name: "buttonPress", args: [3] },
      ...frames(80),
    ],
  });
  add("Mandelbrot worklist wraps and discards pending rectangles", program(mandelbrot.source + `
korg.onEvent("ready", () => {
  cx = 32768;
  cy = 32768;
  zoom = 0;
  changed();
});`, "mandelbrot"), {
    events: [
      { name: "open", args: [] },
      { name: "ready", args: [] },
      ...frames(220),
      { name: "buttonPress", args: [3] },
      ...frames(30),
      ...Array.from({ length: 7 }, () => ({ name: "encoder", args: [0, 1] })),
      ...frames(2),
    ],
  });
  const life = PRESETS.find(p => p.id === "life");
  add("Life dense painting, one generation and interrupted edits", program(life.source, "life"), {
    events: [
      { name: "open", args: [] },
      { name: "buttonPress", args: [28] },
      { name: "buttonPress", args: [31] },
      ...frames(40),
      { name: "buttonPress", args: [29] },
      ...frames(30),
      { name: "touch", args: [1023, 1023, 1] },
      ...frames(3),
      { name: "buttonPress", args: [30] },
      { name: "buttonPress", args: [31] },
      ...frames(5),
      { name: "buttonPress", args: [30] },
      ...frames(5),
      { name: "buttonPress", args: [28] },
      ...frames(30),
    ],
  });
  const pong = PRESETS.find(p => p.id === "pong");
  add("Pong fast trail, wall reflection and point", program(pong.source + `
korg.onEvent("ready", () => {
  state = 1;
  bx = 100 * 4;
  by = 58 * 4;
  vx = 22;
  vy = 14;
});`, "pong"), {
    events: [{ name: "open", args: [] }, { name: "ready", args: [] }, ...frames(70)],
  });
  add("fuel exhaustion", blob(["loop:", { op: "JMP", args: ["loop"], line: 18 }]), { fuel: 100 });
  for (const fuel of [1, 2]) add(`exact HALT fuel ${fuel}`, blob([["HALT"]]), { fuel });
  add("empty fuel", blob([["HALT"]]), { fuel: 0 });
  add("a source appendix is ignored", uiBlob, { scripts: [{ blob: hex(uiBlob), appendix: hex(Buffer.from("\n// Quelltext\nlet a = 1;\n")) }], events: [{ name: "ready", args: [] }] });

  const bitmapBlob = (handle, varCount = 8) => {
    const a = assemble([["HALT"], "ready:", ["PUSHB", 1], ["PUSHB", 170], ["ASTORE", 2, 4], ["PUSHB", 3], ["PUSHB", 129], ["ASTORE", 2, 4], ["PUSHK", 0], ["PUSHB", 5], ["PUSHB", 6], ["PUSHB", 2], ["CALLAPI", api("korg.display.bitmap"), 4], ["DROP"], ["HALT"]]);
    return encodeBlob({ apiVersion: API_VERSION, code: a.code, consts: [handle], varCount, stackMax: 4, handlers: [{ event: event("ready"), argc: 0, entry: a.labels.get("ready") }], lines: [{ offset: 0, line: 1 }] });
  };
  const ready = [{ name: "ready", args: [] }];
  add("a bitmap call hands its array over", bitmapBlob(ARRAY_HANDLE.make(2, 4)), { events: ready });
  add("a bitmap array of one slot at the last variable", bitmapBlob(ARRAY_HANDLE.make(7, 1)), { events: ready });
  add("a bitmap array of zero slots", bitmapBlob(ARRAY_HANDLE.make(2, 0)), { events: ready });
  add("a bitmap array past the variables", bitmapBlob(ARRAY_HANDLE.make(5, 4)), { events: ready });
  add("a bitmap array of the largest length past the variables", bitmapBlob(ARRAY_HANDLE.make(0xFFFF, 0xFFFF)), { events: ready });
  for (const fuel of [15, 16, 29, 30, 41, 42, 43, 44]) add(`a bitmap call pays for each slot, fuel ${fuel}`, bitmapBlob(ARRAY_HANDLE.make(2, 4)), { events: ready, fuel });
  add("the touch event carries the first value", program("let a = 0; let b = 0; let c = 0; korg.onEvent(\"touch\", (x, y, first) => { a = x; b = y; c = first; });", "touch"), { events: [{ name: "touch", args: [300, 700, 1] }, { name: "touch", args: [310, 690, 0] }] });

  const minimal = blob([["HALT"]]);
  add("truncated header", minimal.subarray(0, HEADER.size - 1));
  add("wrong magic", mutate(minimal, b => { b[0] ^= 1; }, false));
  add("old format", mutate(minimal, (_, d) => d.setUint16(4, 1, true), false));
  add("new API version", mutate(minimal, (_, d) => d.setUint16(6, 65535, true), false));
  add("wrong checksum", mutate(minimal, b => { b[36] ^= 1; }, false));
  add("wrong total size", mutate(minimal, (_, d) => d.setUint32(8, minimal.length + 4, true), false));
  add("nonzero reserved", mutate(minimal, (_, d) => d.setUint16(34, 1, true)));
  add("too many variables", mutate(minimal, (_, d) => d.setUint32(16, LIMITS.vars + 1, true)));
  const data = [{ base: 1, bytes: Uint8Array.of(5, 0, 255) }, { base: 6, bytes: Uint8Array.of(9, 1) }];
  const withData = blob([["LOAD", 3], ["LOAD", 6], ["ADD"], ["STORE", 0], ["HALT"]], { data });
  add("the data section fills the arrays", withData);
  add("data past the variables", blob([["HALT"]], { data: [{ base: 7, bytes: Uint8Array.of(1, 2) }] }));
  add("an empty data record", blob([["HALT"]], { data: [{ base: 0, bytes: new Uint8Array(0) }] }));
  add("a data record past totalSize", mutate(withData.slice(0, withData.length - 4), (_, d) => d.setUint32(8, withData.length - 4, true)));
  add("the data flag without data", mutate(minimal, (_, d) => d.setUint16(34, 2, true)));
  add("invalid opcode", encodeBlob({ code: [255], stackMax: 0 }));
  add("truncated operand", encodeBlob({ code: [OP.LOAD, 0], varCount: 1, stackMax: 1 }));
  add("jump into operand", blob([["JMP", 2], ["HALT"]]));
  add("jump past code", blob([["JMP", 65535], ["HALT"]]));
  add("missing constant", blob([["PUSHK", 0], ["DROP"], ["HALT"]]));
  add("missing string", blob([["PUSHS", 0], ["DROP"], ["HALT"]]));
  add("variable outside declaration", blob([["LOAD", 8], ["DROP"], ["HALT"]]));
  add("array past variables", blob([["PUSHB", 0], ["ALOAD", 4, 5], ["DROP"], ["HALT"]]));
  add("unknown API", blob([["CALLAPI", 0, 0], ["DROP"], ["HALT"]]));
  add("API argument count", blob([["CALLAPI", api("korg.millis"), 1], ["DROP"], ["HALT"]]));
  add("korg.app in a handler", encodeBlob({ apiVersion: API_VERSION, code: assemble([["HALT"], "h:", ["PUSHS", 0], ["PUSHS", 1], ["CALLAPI", api("korg.app"), 2], ["DROP"], ["HALT"]]).code, strings: ["Game", "GAMES"], stackMax: 2, handlers: [{ event: event("ready"), argc: 0, entry: 1 }] }));
  add("API in forbidden event", blob([["PUSHB", 3], ["PUSHB", 255], ["CALLAPI", api("korg.led"), 2], ["DROP"], ["HALT"]]));
  add("stack underflow", blob([["DROP"], ["HALT"]]));
  add("stack overflow", blob([...Array.from({ length: 33 }, () => ["PUSHB", 1]), ...Array.from({ length: 33 }, () => ["DROP"]), ["HALT"]]));
  raw("runtime stack overflow", [...Array.from({ length: 33 }, () => ["PUSHB", 1]), ["HALT"]]);
  raw("runtime API argument count", [["PUSHB", 7], ["CALLAPI", api("korg.millis"), 1], ["DROP"], ["HALT"]]);
  raw("runtime API event", [["PUSHB", 3], ["PUSHB", 255], ["CALLAPI", api("korg.led"), 2], ["DROP"], ["HALT"]]);
  raw("runtime jump outside code", [["JMP", 65535], ["HALT"]]);
  add("return with leftover stack", blob([["PUSHB", 1], ["PUSHB", 2], ["RET"]]));
  add("HALT with leftover stack", blob([["PUSHB", 1], ["HALT"]]));
  add("code falls through", blob([["PUSHB", 1]]));
  add("declared stack too small", blob([["PUSHB", 1], ["STORE", 0], ["HALT"]], { stackMax: 0 }));
  add("branch stack mismatch", blob([["PUSHB", 1], ["JZ", "join"], ["PUSHB", 2], "join:", ["HALT"]]));
  add("function argument mismatch", blob([["CALL", "fn", 0], ["DROP"], ["PUSHB", 1], ["CALL", "fn", 1], ["DROP"], ["HALT"], "fn:", ["PUSHB", 1], ["RET"]]));
  add("indirect forbidden API", blob([["CALL", "fn", 0], ["DROP"], ["HALT"], "fn:", ["PUSHB", 1], ["PUSHB", 2], ["CALLAPI", api("korg.led"), 2], ["RET"]]));
  add("unreachable UI API", blob([["HALT"], ["PUSHB", 1], ["PUSHB", 2], ["CALLAPI", api("korg.led"), 2], ["RET"]]));
  add("recursive call", blob([["CALL", "function", 0], ["DROP"], ["HALT"], "function:", ["CALL", "function", 0], ["RET"]]));
  add("bad entry", blob([["HALT"]], { entry: 65535 }));
  add("duplicate handler", blob([["HALT"]], { handlers: [{ event: event("frame"), argc: 0, entry: 0 }, { event: event("frame"), argc: 0, entry: 0 }] }));
  add("bad event", blob([["HALT"]], { handlers: [{ event: 255, argc: 0, entry: 0 }] }));
  add("start is not a handler", blob([["HALT"]], { handlers: [{ event: event("start"), argc: 0, entry: 0 }] }));
  add("handler takes too many arguments", blob([["HALT"]], { handlers: [{ event: event("frame"), argc: 1, entry: 0 }] }));
  add("handler entry argument conflict", blob([["HALT"]], { handlers: [{ event: event("buttonPress"), argc: 1, entry: 0 }] }));
  add("bad line", blob([["HALT"]], { lines: [{ offset: 0, line: 0 }] }));
  add("line outside code", blob([["HALT"]], { lines: [{ offset: 1, line: 1 }] }));
  add("line inside operand", blob([["PUSHB", 1], ["DROP"], ["HALT"]], { lines: [{ offset: 1, line: 1 }] }));
  add("duplicate line position", blob([["HALT"]], { lines: [{ offset: 0, line: 1 }, { offset: 0, line: 2 }] }));
  add("unsorted line positions", blob([["PUSHB", 1], ["DROP"], ["HALT"]], { lines: [{ offset: 2, line: 1 }, { offset: 0, line: 2 }] }));
  const textBlob = blob([["HALT"]], { strings: ["abc"] });
  const textAt = sectionOffsets(decodeBlob(textBlob).header).strings;
  add("unterminated text", mutate(textBlob, b => b.fill(65, textAt, textAt + LIMITS.stringSlot)));
  add("text after terminator", mutate(textBlob, b => { b[textAt + 4] = 1; }));
  add("text below display character range", mutate(textBlob, b => { b[textAt] = 31; }));
  add("text above display character range", mutate(textBlob, b => { b[textAt] = 0x82; }));

  for (const [name, items] of [
    ["stack underflow", [["DROP"], ["HALT"]]],
    ["bad opcode", [["HALT"]]],
    ["variable", [["LOAD", 8], ["DROP"], ["HALT"]]],
    ["constant", [["PUSHK", 0], ["DROP"], ["HALT"]]],
    ["string", [["PUSHS", 0], ["DROP"], ["HALT"]]],
    ["unknown API", [["CALLAPI", 0, 0], ["DROP"], ["HALT"]]],
  ]) {
    raw(`runtime ${name}`, items);
    if (name === "bad opcode") cases.at(-1).scripts[0].blob = hex(encodeBlob({ code: [255], stackMax: 0 }));
  }
  return cases.map(c => ({ ...c, expected: oracle(c) }));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.stdout.write(JSON.stringify({ cases: armCases() }));
