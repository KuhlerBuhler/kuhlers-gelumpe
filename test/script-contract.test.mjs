import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  FORMAT_VERSION, API_VERSION, MAGIC, LIMITS, HEADER, SECTION, OPCODES, OPCODE_COUNT, OP, EVENTS, API, ERRORS, ERROR, BUDGET,
} from "../data/script/contract.mjs";
import { armTables, asmInclude, OPCODE_SLOTS, API_ENTRY_SIZE, FLOWS, OPERAND_KINDS, POP_ARGC } from "../src/script/arm-tables.mjs";
import { encodeBlob, decodeBlob } from "../src/script/blob.mjs";
import * as contract from "../data/script/contract.mjs";
import * as tables from "../src/script/arm-tables.mjs";

test("the shared script pool and entry layout are one declarative contract", () => {
  assert.equal(BUDGET.scriptBytes, 128 * 1024);
  assert.equal(BUDGET.variableSlots, BUDGET.scriptBytes / 4);
  assert.deepEqual(contract.SCRIPT_ENTRY.fields.map(f => [f.name, f.offset]), [
    ["next", 0], ["blob", 4], ["vars", 8], ["state", 12], ["fault", 16], ["offset", 20],
    ["line", 24], ["event", 28], ["ops", 32], ["cost", 36], ["maxTicks", 40], ["maxCost", 44], ["maxEventTicks", 132], ["readySent", 220],
    ["storeMask", 224], ["store", 228],
  ]);
  assert.equal(contract.SCRIPT_ENTRY.size, 48 + EVENTS.length * 8 + 4 + contract.STORE.slots * 4);
  assert.equal(contract.SCRIPT_ENTRY.size, 292);
  let offset = 0;
  for (const field of contract.SCRIPT_ENTRY.fields) {
    assert.equal(field.offset, offset);
    offset += field.words * 4;
  }
  assert.equal(offset, contract.SCRIPT_ENTRY.size);
  assert.deepEqual(contract.SCRIPT_STATE, { LOADED: 1, ARMED: 2, DISABLED: 3 });
  assert.equal(ERROR.VARS_BUDGET, 27);
  assert.equal(ERROR.POOL_BUDGET, 28);
});

test("the frame cursor and normalized event record share their generated layout", () => {
  assert.equal(contract.SCRIPT_CONTROL?.headerSize, 256);
  assert.deepEqual(contract.SCRIPT_CONTROL.fields.map(f => [f.name, f.offset, f.words]), [
    ["armed", 96, 1], ["ready", 100, 1], ["ringHead", 104, 1], ["ringTail", 108, 1],
    ["frameStart", 112, 1], ["frameActive", 116, 1], ["cursorEntry", 120, 1], ["cursorEvent", 124, 1],
    ["cursorArgs", 128, 3], ["cursorRingEnd", 140, 1], ["cursorPhase", 144, 1], ["captureMask", 148, 1],
    ["frames", 152, 1], ["paused", 156, 1], ["ledSent", 160, 1],
    ["cardStatus", 164, 1], ["cardLoaded", 168, 1], ["cardRejected", 172, 1], ["cardFirstError", 176, 1],
    ["displayActive", 180, 1], ["storePending", 184, 1], ["storeFrame", 188, 1], ["storeGeneration", 192, 1], ["storeBytes", 196, 1],
    ["storeErrors", 200, 1], ["storeWrites", 204, 1],
    ["clockInit", 208, 1], ["clockLast", 212, 1], ["clockRem", 216, 1], ["clockMs", 220, 1],
    ["seqInit", 224, 1], ["seqTransport", 228, 1], ["seqTempo", 232, 1], ["seqPattern", 236, 1], ["seqPart", 240, 1], ["seqStep", 244, 1], ["seqMutes", 248, 1],
    ["ledHold", 252, 1],
  ]);
  assert.deepEqual(contract.SCRIPT_PHASE, { READY: 0, QUEUED: 1, FRAME: 2, IDLE: 3 });
  assert.equal(contract.SCRIPT_EVENT_RECORD.size, 16);
  assert.deepEqual(contract.SCRIPT_EVENT_RECORD.fields.map(f => [f.name, f.offset, f.words]), [["event", 0, 1], ["args", 4, 3]]);
  assert.ok(EVENTS.every(e => e.argc <= 3));
  const equ = Object.fromEntries([...asmInclude().matchAll(/^\.equ (\w+), (\w+)$/gm)].map(m => [m[1], Number(m[2])]));
  assert.equal(equ.SCRIPT_CONTROL_HEADER_SIZE, 256);
  assert.equal(equ.SCRIPT_CONTROL_CURSOR_RING_END, 140);
  assert.equal(equ.SCRIPT_CONTROL_CAPTURE_MASK, 148);
  assert.equal(equ.SCRIPT_CONTROL_LED_SENT, 160);
  assert.equal(equ.SCRIPT_EVENT_RECORD_SIZE, 16);
  assert.equal(equ.SCRIPT_EVENT_RECORD_ARGS, 4);
  assert.equal(equ.SCRIPT_PHASE_READY, 0);
  assert.equal(equ.SCRIPT_PHASE_QUEUED, 1);
  assert.equal(equ.SCRIPT_PHASE_FRAME, 2);
  assert.equal(equ.SCRIPT_PHASE_IDLE, 3);
  let offset = 96;
  for (const field of contract.SCRIPT_CONTROL.fields) {
    assert.equal(field.offset, offset);
    assert.equal(equ[`SCRIPT_CONTROL_${field.name.replace(/([a-z])([A-Z])/g, "$1_$2").toUpperCase()}`], field.offset);
    offset += field.words * 4;
  }
  assert.ok(offset <= contract.SCRIPT_CONTROL.headerSize);
});

test("the API table retains a full 16-bit since value independently of cost", () => {
  assert.equal(typeof tables.apiTable, "function");
  assert.equal(tables.API_SINCE_OFFSET, 10);
  for (const since of [1, 255, 256, 0x1234, 65535]) {
    const api = { ...API[0], since };
    const bytes = tables.apiTable([api]);
    const offset = api.id * API_ENTRY_SIZE;
    assert.equal(bytes.length, (api.id + 1) * 48);
    assert.equal(bytes[offset + 2], 0);
    assert.equal(bytes[offset + 3], api.cost);
    assert.equal(bytes[offset + 10], since & 255);
    assert.equal(bytes[offset + 11], since >>> 8);
    assert.equal(new DataView(bytes.buffer).getUint16(offset + tables.API_SINCE_OFFSET, true), since);
  }
  for (const since of [0, -1, 0.5, NaN, 65536]) assert.throws(() => tables.apiTable([{ ...API[0], since }]), RangeError);
});

test("LED state and transport budgets share one generated contract", () => {
  const led = contract.SCRIPT_LED;
  assert.equal(led?.count, 88);
  assert.equal(led.levelMax, 255);
  assert.equal(led.packetBytes, 5);
  assert.equal(led.perFrame, 16);
  assert.equal(led.reserveBytes, 256);
  assert.equal(led.size, 356);
  assert.deepEqual(led.fields.map(f => [f.name, f.offset, f.bytes]), [
    ["desired", 0, 88], ["delivered", 88, 88], ["pending", 176, 88], ["valid", 264, 88], ["nextIndex", 352, 4],
  ]);
  assert.deepEqual(contract.SCRIPT_LED_VALID, { DESIRED: 1, DELIVERED: 2 });
  assert.equal(API.find(a => a.name === "korg.led").id, 1);
  assert.equal(API_VERSION, 8);
  const equ = Object.fromEntries([...asmInclude().matchAll(/^\.equ (\w+), (\w+)$/gm)].map(m => [m[1], Number(m[2])]));
  for (const [name, value] of Object.entries(led).filter(([, value]) => typeof value === "number")) {
    assert.equal(equ[`SCRIPT_LED_${name.replace(/([a-z])([A-Z])/g, "$1_$2").toUpperCase()}`], value);
  }
  for (const field of led.fields) assert.equal(equ[`SCRIPT_LED_${field.name.replace(/([a-z])([A-Z])/g, "$1_$2").toUpperCase()}`], field.offset);
  assert.equal(equ.SCRIPT_LED_VALID_DESIRED, 1);
  assert.equal(equ.SCRIPT_LED_VALID_DELIVERED, 2);
});


test("the collection file layout and the loader status codes share one generated contract", () => {
  const a = contract.ARCHIVE;
  assert.equal(a.magic, 0x4C415347);
  assert.deepEqual(a.fields.map(f => [f.name, f.offset, f.type]), [
    ["magic", 0, "u32"], ["version", 4, "u16"], ["count", 6, "u16"], ["totalSize", 8, "u32"], ["checksum", 12, "u32"],
  ]);
  assert.equal(a.headerSize, 16);
  assert.equal(a.checksumFrom, 16);
  assert.equal(a.version, 1);
  assert.equal(a.file, "e2sPlugin.all");
  assert.equal(a.folder, "KORG/blechtribe/Plugin");
  assert.equal(contract.SOURCE_TRAILER.magic, 0x43525347);
  assert.deepEqual(contract.CARD_STATUS, { LOADED: 1, NO_FILE: 2, BAD_HEADER: 3, BAD_CHECKSUM: 4, READ_ERROR: 5, BLOCK_SIZE: 6, KILL_SWITCH: 7, NO_PANEL: 8, SETTINGS_OFF: 9 });
  const equ = Object.fromEntries([...asmInclude().matchAll(/^\.equ (\w+), (\w+)$/gm)].map(m => [m[1], Number(m[2])]));
  assert.equal(equ.ARCHIVE_MAGIC, a.magic);
  assert.equal(equ.ARCHIVE_VERSION, 1);
  assert.equal(equ.ARCHIVE_HEADER_SIZE, 16);
  assert.equal(equ.ARCHIVE_MAX_BLOCK, a.maxBlock);
  assert.equal(equ.ARCHIVE_AT_COUNT, 6);
  assert.equal(equ.ARCHIVE_AT_TOTAL_SIZE, 8);
  assert.equal(equ.ARCHIVE_AT_CHECKSUM, 12);
  for (const [name, value] of Object.entries(contract.CARD_STATUS)) assert.equal(equ[`CARD_${name}`], value);
});

test("the generated timer deadline uses Timer3 at 150 MHz and the frame budget", () => {
  const equ = Object.fromEntries([...asmInclude().matchAll(/^\.equ (\w+), (\w+)$/gm)].map(m => [m[1], Number(m[2])]));
  assert.deepEqual(contract.TIMER3, { address: 0x01F0D010, hz: 150000000, period: 150000000 });
  assert.equal(equ.SCRIPT_TIMER_PERIOD, contract.TIMER3.period);
  assert.equal(equ.SCRIPT_TIMER_TICKS_PER_MS, contract.TIMER3.hz / 1000);
  assert.equal(equ.SCRIPT_TIMER_ADDRESS, contract.TIMER3.address);
  assert.equal(equ.SCRIPT_TIMER_HZ, contract.TIMER3.hz);
  assert.equal(equ.SCRIPT_FRAME_TICKS, Math.round(BUDGET.frameMs * contract.TIMER3.hz / 1000));
  assert.equal(equ.SCRIPT_FRAME_TICKS, 750000);
  assert.equal(equ.SCRIPT_EVENT_COUNT, EVENTS.length);
});

test("opcode numbers are pinned: they are in every blob ever exported", () => {
  const pinned = "HALT PUSHB PUSHK PUSHS LOAD STORE ALOAD ASTORE DUP DROP ADD SUB MUL DIV MOD AND OR XOR SHL SHR NEG NOT EQ NE LT LE GT GE JMP JZ JNZ CALL RET CALLAPI".split(" ");
  assert.deepEqual(OPCODES.map(o => o.name), pinned);
  OPCODES.forEach((o, i) => assert.equal(o.code, i));
  assert.equal(OPCODE_COUNT, 34);
});

test("event ids, API ids and error codes are pinned", () => {
  assert.deepEqual(EVENTS.map(e => e.name), ["start", "ready", "frame", "buttonPress", "buttonRelease", "knob", "encoder", "pad", "touch", "step", "beat", "play", "stop", "rec", "patternChange", "partChange", "mute", "tempo", "save", "menu", "open", "close"]);
  assert.deepEqual(Object.fromEntries(API.map(a => [a.id, a.name])), {
    1: "korg.led", 2: "korg.millis", 16: "korg.display.clear", 17: "korg.display.text", 18: "korg.display.number",
    19: "korg.display.pixel", 20: "korg.display.rect", 21: "korg.display.clearRect",
    22: "korg.display.take", 23: "korg.display.release", 24: "korg.display.bitmap", 25: "korg.display.textNumber",
    32: "korg.store.get", 33: "korg.store.set", 34: "korg.store.save",
    35: "korg.read.transport", 36: "korg.read.tempo", 37: "korg.read.pattern", 38: "korg.read.part", 39: "korg.read.step",
    40: "korg.read.mute", 41: "korg.read.knob",
    42: "korg.read.chainMode", 43: "korg.read.patternValue", 44: "korg.remapKey",
    48: "korg.play", 49: "korg.stop", 50: "korg.pattern", 51: "korg.tempo", 52: "korg.part", 53: "korg.mute",
    56: "korg.backlight", 57: "korg.ledHold", 58: "korg.menu.add", 59: "korg.app",
    60: "korg.file.frame",
  });
  assert.deepEqual(ERRORS.map(e => e.code), ERRORS.map((_, i) => i));
  assert.equal(ERROR.FUEL, 1);
  assert.equal(ERROR.BAD_OPCODE, 2);
  assert.equal(ERROR.BOUNDS, 3);
  assert.equal(ERROR.DIV_ZERO, 4);
  assert.equal(ERROR.STACK, 5);
  assert.equal(ERROR.BAD_JUMP, 6);
  assert.equal(FORMAT_VERSION, 2);
  assert.equal(API_VERSION, 8);
  assert.deepEqual(API.filter(a => a.since === 2).map(a => a.name), ["korg.store.get", "korg.store.set", "korg.store.save"]);
  assert.deepEqual(API.filter(a => a.since === 3).map(a => a.name).slice(0, 2), ["korg.read.transport", "korg.read.tempo"]);
  assert.deepEqual(API.filter(a => a.since === 4).map(a => a.name), ["korg.menu.add"]);
  assert.deepEqual(API.filter(a => a.since === 5).map(a => a.name), ["korg.display.take", "korg.display.release", "korg.app"]);
});

test("apps: the open and close events, the registration call and the runtime table share one generated contract", () => {
  assert.deepEqual(contract.APP_EVENTS, ["open", "close"]);
  assert.deepEqual([contract.EVENT_BY_NAME.get("open").id, contract.EVENT_BY_NAME.get("close").id], [20, 21]);
  assert.ok(!contract.QUEUED_EVENTS.includes("open") && !contract.QUEUED_EVENTS.includes("close"), "nothing outside the runtime posts them");
  const app = contract.API_BY_NAME.get("korg.app");
  assert.deepEqual([app.id, app.since, app.returns], [59, 5, "int"]);
  assert.deepEqual(app.args.map(a => a.kind), ["str", "str"]);
  assert.equal(app.eventMask, 1, "only the script body, `start`, may declare an app");
  assert.deepEqual(contract.SCRIPT_APPS.groups, ["GAMES", "TOOLS"]);
  const equ = Object.fromEntries([...asmInclude().matchAll(/^\.equ (\w+), (\w+)$/gm)].map(m => [m[1], Number(m[2])]));
  assert.deepEqual([equ.EV_OPEN, equ.EV_CLOSE, equ.API_KORG_APP], [20, 21, 59]);
  assert.deepEqual([equ.SCRIPT_APPS_MAX, equ.SCRIPT_APPS_BUILTIN, equ.SCRIPT_APPS_SLOTS, equ.SCRIPT_APPS_BUILTIN_GROUP, equ.SCRIPT_APPS_RECORD_SIZE, equ.SCRIPT_APPS_STATE_SIZE], [12, 1, 13, 2, 12, 168]);
  assert.deepEqual([equ.SCRIPT_APPS_OPEN, equ.SCRIPT_APPS_COUNT, equ.SCRIPT_APPS_TABLE, equ.SCRIPT_APPS_GRACE, equ.SCRIPT_APPS_OPEN_GRACE], [0, 4, 8, 164, 3]);
  assert.deepEqual([equ.SCRIPT_APP_ENTRY, equ.SCRIPT_APP_NAME, equ.SCRIPT_APP_GROUP, equ.SCRIPT_APP_GROUP_GAMES, equ.SCRIPT_APP_GROUP_TOOLS], [0, 4, 8, 0, 1]);
  assert.equal(contract.SCRIPT_APPS.slots, contract.SCRIPT_APPS.max + contract.SCRIPT_APPS.builtin, "one record is the app built into BLECH");
  assert.ok(contract.SCRIPT_APPS.builtinGroup >= contract.SCRIPT_APPS.groups.length, "its group is none a plugin can name");
  assert.equal(contract.SCRIPT_APPS.stateSize, 8 + contract.SCRIPT_APPS.slots * contract.SCRIPT_APPS.recordSize + 4);
});

test("every table is well formed", () => {
  assert.equal(new Set(API.map(a => a.id)).size, API.length);
  assert.equal(new Set(API.map(a => a.name)).size, API.length);
  for (const a of API) {
    assert.ok(a.id >= 1 && a.id < 256, a.name);
    assert.ok(a.args.length <= LIMITS.apiArgs, a.name);
    assert.ok(a.since >= 1 && a.since <= API_VERSION, a.name);
    assert.ok(a.events.length > 0 && a.eventMask > 0, a.name);
    assert.ok(a.cost > 0 && a.cost <= 255, a.name);
    for (const arg of a.args) assert.ok(arg.kind === "int" ? arg.min <= arg.max : arg.min === undefined, `${a.name}.${arg.name}`);
  }
  assert.equal(EVENTS[0].name, "start");
  EVENTS.forEach((e, i) => { assert.equal(e.id, i); assert.equal(e.argc, e.args.length); });
  assert.equal(new Set(ERRORS.map(e => e.name)).size, ERRORS.length);
  for (const o of OPCODES) {
    assert.equal(o.size, 1 + o.operands.reduce((n, x) => n + x.size, 0), o.name);
    assert.ok(o.pop === "argc" ? o.operands.some(x => x.as === "argc") : Number.isInteger(o.pop), o.name);
  }
  assert.ok(OPCODE_COUNT <= OPCODE_SLOTS);
  assert.ok(EVENTS.length <= 32, "the event mask is one 32-bit word");
});

test("the header fields tile the first 52 bytes", () => {
  const widths = { u16: 2, u32: 4, char16: 16 };
  let at = 0;
  for (const f of HEADER.fields) {
    assert.equal(f.offset, at, f.name);
    at += widths[f.type];
  }
  assert.equal(at, HEADER.size);
  assert.equal(HEADER.checksumFrom, HEADER.fields.find(f => f.name === "varCount").offset);
});

test("variable and array operands are 16 bits and the limits fit them", () => {
  const widthOf = new Map();
  for (const o of OPCODES) for (const x of o.operands) {
    assert.ok(!widthOf.has(x.as) || widthOf.get(x.as) === x.size, `${o.name}.${x.name}: one width per operand kind`);
    widthOf.set(x.as, x.size);
  }
  for (const k of ["var", "arrayBase", "arrayLength", "target"]) assert.equal(widthOf.get(k), 2, k);
  for (const k of ["byte", "const", "string", "argc", "api"]) assert.equal(widthOf.get(k), 1, k);
  assert.equal(LIMITS.vars, 65536, "slot numbers 0 to 65535 fit the 16-bit operand");
  assert.equal(LIMITS.arrayLength, 65535, "the length operand cannot say 65536");
  assert.ok(BUDGET.variableSlots <= LIMITS.vars && BUDGET.variableSlots * 4 <= 360 * 1024, "the budget sits in the FF block of the research");
  assert.equal(HEADER.fields.find(f => f.name === "varCount").type, "u32", "the count of a full 65536 slot area does not fit 16 bits");
});

test("a blob round trips through the container", () => {
  const blob = encodeBlob({
    name: "demo", apiVersion: 1, entry: 0, code: [OP.HALT], varCount: 3, stackMax: 2,
    handlers: [{ event: 2, argc: 0, entry: 0 }], consts: [-5, 1000], strings: ["hi", "x".repeat(31)], lines: [{ offset: 0, line: 7 }],
  });
  const d = decodeBlob(blob);
  assert.ok(d.ok);
  assert.equal(d.header.magic, MAGIC);
  assert.equal(d.header.name, "demo");
  assert.deepEqual(d.strings, ["hi", "x".repeat(31)]);
  assert.deepEqual(Array.from(d.consts), [-5, 1000]);
  assert.deepEqual(d.handlers, [{ event: 2, argc: 0, entry: 0 }]);
  assert.deepEqual(d.lines, [{ offset: 0, line: 7 }]);
  assert.equal(blob.length % 4, 0, "sections stay word aligned");
  assert.equal(SECTION.string, LIMITS.stringSlot);
});

/** Read a generated byte table back the way the ARM VM will index it. */
test("the generated ARM tables say what the contract says", () => {
  const t = armTables();
  for (const name of ["opSize", "opCost", "opPop", "opPush", "opFlow"]) assert.equal(t[name].length, OPCODE_SLOTS, name);
  for (const o of OPCODES) {
    assert.equal(t.opSize[o.code], o.size, `${o.name} size`);
    assert.equal(t.opCost[o.code], o.cost, `${o.name} cost`);
    assert.equal(t.opPop[o.code], o.pop === "argc" ? POP_ARGC : o.pop, `${o.name} pop`);
    assert.equal(t.opPush[o.code], o.push, `${o.name} push`);
    assert.equal(FLOWS[t.opFlow[o.code]], o.flow, `${o.name} flow`);
    for (const k of [0, 1]) assert.equal(OPERAND_KINDS[t.opOperands[2 * o.code + k]], o.operands[k]?.as ?? "none", `${o.name} operand ${k}`);
  }
  for (let i = OPCODE_COUNT; i < OPCODE_SLOTS; i++) assert.equal(t.opSize[i] + t.opCost[i] + t.opPush[i], 0, `slot ${i} is empty`);

  assert.deepEqual(Array.from(t.eventArgc), EVENTS.map(e => e.argc));
  const top = Math.max(...API.map(a => a.id));
  assert.equal(t.apiTable.length, (top + 1) * API_ENTRY_SIZE);
  const dv = new DataView(t.apiTable.buffer);
  for (let id = 0; id <= top; id++) {
    const o = id * API_ENTRY_SIZE;
    const a = API.find(x => x.id === id);
    if (!a) { assert.ok(t.apiTable.subarray(o, o + API_ENTRY_SIZE).every(b => b === 0), `id ${id} is empty`); continue; }
    assert.equal(t.apiTable[o], 1);
    assert.equal(t.apiTable[o + 1], a.args.length, `${a.name} argc`);
    assert.equal(t.apiTable[o + 2], a.perItem, `${a.name} fuel for each array slot`);
    assert.equal(dv.getUint16(o + 10, true), a.since);
    assert.equal(t.apiTable[o + 3], a.cost);
    assert.equal(dv.getUint32(o + 4, true), a.eventMask, `${a.name} events`);
    a.args.forEach((arg, i) => {
      assert.equal((t.apiTable[o + 8] >> i) & 1, arg.kind === "str" ? 1 : 0, `${a.name} text mask ${i}`);
      assert.equal((t.apiTable[o + 9] >> i) & 1, arg.kind === "arr" ? 1 : 0, `${a.name} array mask ${i}`);
      if (arg.kind === "int") {
        assert.equal(dv.getInt32(o + 16 + 4 * i, true), arg.min);
        assert.equal(dv.getInt32(o + 32 + 4 * i, true), arg.max);
      }
    });
    assert.equal(dv.getUint32(o + 12, true), 0, "glue pointers are patched in at link time");
  }
});

test("the generated include names every constant of the contract", () => {
  const text = asmInclude();
  const equ = Object.fromEntries([...text.matchAll(/^\.equ (\w+), (\w+)$/gm)].map(m => [m[1], Number(m[2])]));
  assert.equal(equ.SCRIPT_FORMAT_VERSION, FORMAT_VERSION);
  assert.equal(equ.SCRIPT_API_VERSION, API_VERSION);
  assert.equal(equ.SCRIPT_MAGIC, MAGIC);
  assert.equal(equ.SCRIPT_RING, BUDGET.ring);
  assert.equal(equ.HDR_SIZE, HEADER.size);
  assert.equal(equ.HDR_TOTAL_SIZE, 8);
  assert.equal(equ.HDR_VAR_COUNT, 16);
  assert.equal(equ.LIM_VARS, LIMITS.vars);
  assert.equal(equ.LIM_ARRAY_LENGTH, LIMITS.arrayLength);
  assert.equal(equ.SCRIPT_VAR_SLOTS, BUDGET.variableSlots);
  assert.equal(equ.SCRIPT_POOL_BYTES, 128 * 1024);
  assert.equal(equ.SCRIPT_API_SINCE, 10);
  assert.equal(equ.SCRIPT_ENTRY_SIZE, contract.SCRIPT_ENTRY.size);
  for (const f of contract.SCRIPT_ENTRY.fields) assert.equal(equ[`SCRIPT_ENTRY_${f.name.replace(/([a-z])([A-Z])/g, "$1_$2").toUpperCase()}`], f.offset);
  assert.equal(equ.SCRIPT_STATE_LOADED, 1);
  assert.equal(equ.SCRIPT_STATE_ARMED, 2);
  assert.equal(equ.SCRIPT_STATE_DISABLED, 3);
  assert.equal(equ.LIM_STACK, LIMITS.stack);
  assert.equal(equ.LIM_STRING_LENGTH, LIMITS.stringLength);
  for (const o of OPCODES) assert.equal(equ[`OP_${o.name}`], o.code, o.name);
  for (const e of ERRORS) assert.equal(equ[`ERR_${e.name}`], e.code, e.name);
  assert.equal(equ.API_KORG_DISPLAY_CLEAR_RECT, 21);
  assert.equal(equ.EV_PATTERN_CHANGE, 14);
  assert.match(text, /^script_dispatch:$/m);
  assert.equal((text.match(/e_bad_opcode/g) ?? []).length, OPCODE_SLOTS - OPCODE_COUNT);
  assert.ok(!/[\u2013\u2014]/.test(text));
});

// The include is meant for tools/patch/arm.py; assembling it there must give back the same table bytes.
const dir = fileURLToPath(new URL("../tools/patch/", import.meta.url));
const python = process.env.E2_EMU_PYTHON || "python3";
const skip = spawnSync(python, ["--version"], { encoding: "utf8" }).error ? `${python} not available` : false;

test("the include assembles in the repository's ARM assembler to the same bytes", { skip }, () => {
  const stubs = `${OPCODES.map(o => `op_${o.name.toLowerCase()}:`).join("\n")}\ne_bad_opcode:\n    bx lr\n`;
  const program = `import sys, json\nsys.path.insert(0, ${JSON.stringify(dir)})\nimport arm\na = arm.assemble(sys.stdin.read(), 0xC0000000)\nb = a.bytes\ns = a.symbols\nprint(json.dumps({k: b[s[k] - 0xC0000000:s[k] - 0xC0000000 + n].hex() for k, n in json.loads(sys.argv[1]).items()}))\n`;
  const t = armTables();
  const sizes = { script_op_size: 64, script_op_cost: 64, script_op_pop: 64, script_op_push: 64, script_op_flow: 64, script_op_operands: 128, script_event_argc: EVENTS.length, script_api_table: t.apiTable.length };
  const r = spawnSync(python, ["-I", "-c", program, JSON.stringify(sizes)], { input: `.org 0xC0000000\n${stubs}${asmInclude()}`, encoding: "utf8", timeout: 60_000 });
  assert.ifError(r.error);
  assert.equal(r.status, 0, r.stderr);
  const got = JSON.parse(r.stdout);
  const hex = bytes => Buffer.from(bytes).toString("hex");
  assert.equal(got.script_op_size, hex(t.opSize));
  assert.equal(got.script_op_cost, hex(t.opCost));
  assert.equal(got.script_op_operands, hex(t.opOperands));
  assert.equal(got.script_event_argc, hex(t.eventArgc));
  assert.equal(got.script_api_table, hex(t.apiTable));
});
