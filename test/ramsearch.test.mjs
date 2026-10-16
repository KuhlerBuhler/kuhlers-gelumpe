import { test } from "node:test";
import assert from "node:assert/strict";
import { knownRam, ramTools, needleBytes, Snapshot, MAX_CHUNK, GROUPS } from "../src/ramsearch.mjs";
import { makeKorg } from "../src/korg.mjs";
import { DeviceSession } from "../src/session.mjs";
import { describeMessage } from "../src/protocol.mjs";
import { sha256 } from "../src/firmware.mjs";
import { BLOCKS } from "../src/map/index.mjs";
import PROTECTED from "../data/protected.mjs";
import { FROM_PROTECTED, NOT_READ, AREAS, PATTERN_SLOTS } from "../data/known-ram.mjs";
import { makeFirmware, simPort } from "./helpers.mjs";

const DISPLAY = BLOCKS.get("display").meta.ram;
const META = BLOCKS.get("sampleMeta").meta.table;
const META_SIZE = BLOCKS.get("sampleMeta").size;
const TIMEOUTS = { search: 200, read: 200, ack: 200, pattern: 400, global: 200, quiet: 5 };

/** Memory of our own over [base, base + size), read the way a session reads: one call, at most MAX_CHUNK bytes. */
function fakeRam(base, size) {
  const mem = new Uint8Array(size);
  const calls = [];
  const read = async (addr, n) => {
    assert.ok(n >= 1 && n <= MAX_CHUNK, `a read carries 1 to ${MAX_CHUNK} bytes, not ${n}`);
    assert.ok(addr >= base && addr + n <= base + size, `read outside the fake memory: ${addr.toString(16)}`);
    calls.push([addr, n]);
    return mem.slice(addr - base, addr - base + n);
  };
  return { mem, calls, read, poke: (addr, bytes) => mem.set(bytes, addr - base) };
}

/** Unexplained system data with the display buffer (explained by the map) in the middle of it. */
const BASE = 0xc031a000;
const SIZE = 0x6000;

test("every RAM region of the protected list is classified, and nothing classified is stale", () => {
  const ids = PROTECTED.regions.filter(r => r.space === "ram").map(r => r.id);
  const classified = [...Object.keys(FROM_PROTECTED), ...NOT_READ];
  assert.deepEqual(ids.filter(id => !classified.includes(id)), [], "add the region to FROM_PROTECTED in data/known-ram.mjs");
  assert.deepEqual(classified.filter(id => !ids.includes(id)), [], "no such protected region");
  for (const how of Object.values(FROM_PROTECTED)) assert.ok(!how.explained || how.group in GROUPS);
  for (const a of [...AREAS, PATTERN_SLOTS]) assert.ok(a.group === undefined ? !a.explained : a.group in GROUPS);
});

test("the map hides what it explains, down to the field, and leaves what nobody understands", () => {
  const known = knownRam();
  assert.ok(known.hidden(DISPLAY, DISPLAY + 1024).every(Boolean), "the display buffer is one field");
  const meta = META.ram + 3 * META_SIZE;
  const hid = known.hidden(meta, meta + META_SIZE);
  const unknown = BLOCKS.get("sampleMeta").fields.find(f => f.id === "sample.meta.audioOffset");
  assert.equal(hid[unknown.where.offset], 0, "a field with source unknown stays visible");
  assert.equal(hid[BLOCKS.get("sampleMeta").fields.find(f => f.id === "sample.tune").where.offset], 1);
  assert.ok(known.hidden(0xc0000000, 0xc0001000).every(Boolean), "firmware code and static data");
  assert.ok(known.hidden(0xc0200000, 0xc0201000).every(Boolean), "a task stack");
  assert.ok(known.hidden(0xc06a2940, 0xc06a3940).every(b => !b), "the heap is a known area whose bytes nobody explains");
  assert.ok(known.hidden(0xc0d3a940, 0xc0d3b940).every(b => !b), "the work buffer too");
});

test("show brings a hidden kind back, and the other kinds stay hidden", () => {
  const known = knownRam();
  const slot = PATTERN_SLOTS.start + 0x4000 * 5;
  assert.equal(known.hidden(0xc0000000, 0xc0001000).reduce((a, b) => a + b), 0x1000);
  assert.equal(known.hidden(0xc0000000, 0xc0001000, ["image"]).reduce((a, b) => a + b), 0, "no table sits in this stretch");
  assert.ok(known.hidden(slot, slot + 0x4000).some(Boolean) && known.hidden(slot, slot + 0x4000).some(b => !b), "a pattern slot: fields hidden, gaps not");
  assert.ok(known.hidden(slot, slot + 0x4000, ["patterns"]).every(b => !b));
  assert.equal(known.hidden(0xc0200000, 0xc0201000, ["image"]).reduce((a, b) => a + b), 0x1000, "showing the image does not show the stacks");
});

test("a place is named by what holds it, else by its nearest known neighbours, and an address in the supposed mirror says so", () => {
  const known = knownRam();
  assert.match(known.describe(DISPLAY + 5), /^in Displaybild \(\+0x5\)$/);
  assert.match(known.describe(0xc0348884, 4), /in Boot-Löschbereich/);
  assert.equal(known.describe(0xc06a3000), "in Heap (+0x6C0)");
  assert.equal(known.describe(0xc1000010), "in Stub-Puffer (+0x10)");
  assert.match(known.describe(0xc0200000 - 4, 8), /^an /, "a run across an edge touches both");
  assert.match(known.describe(0xc3000000), /^0x[0-9A-F]+ Byte hinter Interrupt- und Idle-Stack$/, "past the last known region");
  assert.equal(known.describe(0xc0000000 + 0x4000000 + 0x40), "im vermuteten Spiegel: in Firmware-Abbild (+0x40)");
});

test("needles: a number is a 32 bit word, little endian; width, bytes and text; bad ones are refused", () => {
  assert.deepEqual(Array.from(needleBytes(0x12345678)), [0x78, 0x56, 0x34, 0x12]);
  assert.deepEqual(Array.from(needleBytes(0xc0348880)), [0x80, 0x88, 0x34, 0xc0]);
  assert.deepEqual(Array.from(needleBytes(0x1234, { width: 2 })), [0x34, 0x12]);
  assert.deepEqual(Array.from(needleBytes(-1, { width: 1 })), [0xff]);
  assert.deepEqual(Array.from(needleBytes("Hi")), [0x48, 0x69]);
  assert.deepEqual(Array.from(needleBytes([1, 2, 3])), [1, 2, 3]);
  assert.throws(() => needleBytes(0x100, { width: 1 }), RangeError);
  assert.throws(() => needleBytes(1.5), RangeError);
  assert.throws(() => needleBytes(5, { width: 3 }), RangeError);
  assert.throws(() => needleBytes([]), RangeError);
  assert.throws(() => needleBytes([300]), TypeError);
  assert.throws(() => needleBytes("ä€"), TypeError);
  assert.throws(() => needleBytes({}), TypeError);
});

test("a snapshot reads in chunks, one at a time, and does not read what is known all through", async () => {
  const r = fakeRam(BASE, SIZE);
  const tools = ramTools({ read: r.read });
  const snap = await tools.snapshot({ from: BASE, to: BASE + SIZE, chunk: 0x800 });
  assert.ok(snap instanceof Snapshot);
  assert.equal(r.calls.length, SIZE / 0x800, "every chunk holds unexplained bytes, so all are read");
  assert.ok(r.calls.every(([a, n], i) => n === 0x800 && a === BASE + i * 0x800));
  assert.deepEqual(snap.spans, [[BASE, BASE + SIZE]]);
  const known = fakeRam(0xc0000000, 0x10000);
  const quiet = await ramTools({ read: known.read }).snapshot({ from: 0xc0000000, to: 0xc0010000 });
  assert.equal(known.calls.length, 0, "firmware code is explained: nothing goes out");
  assert.equal(quiet.read, 0);
  assert.equal(quiet.skipped, 0x10000);
  await ramTools({ read: known.read }).snapshot({ from: 0xc0000000, to: 0xc0010000, mask: false });
  assert.equal(known.calls.length, 0x10000 / 0x1000, "with mask false everything is read");
  known.calls.length = 0;
  await ramTools({ read: known.read }).snapshot({ from: 0xc0000000, to: 0xc0010000, show: ["image"] });
  assert.ok(known.calls.length > 0, "showing the image reads it");
});

test("a range is checked against the read rule before the first read, and a big one needs a limit", async () => {
  const r = fakeRam(BASE, SIZE);
  const tools = ramTools({ read: r.read });
  await assert.rejects(tools.snapshot({ from: 0x60000000, to: 0x60000004 }), /Gesperrt/);
  await assert.rejects(tools.snapshot({ from: 0xc7fff000, to: 0xc8001000 }), /außerhalb des vermessenen/);
  await assert.rejects(tools.snapshot({ from: 0x1000000, to: 0x1000100 }), /außerhalb des vermessenen/, "a flash offset is no RAM address");
  await assert.rejects(tools.search(1, { from: 0x60000000, to: 0x60000100 }), /Gesperrt/);
  assert.equal(r.calls.length, 0, "nothing was read");
  await assert.rejects(tools.snapshot({ from: BASE, to: BASE + 0x500000 }), /mehr als limit/);
  await assert.rejects(tools.snapshot({ from: BASE, to: BASE + 16, chunk: MAX_CHUNK + 1 }), RangeError);
  await assert.rejects(tools.snapshot({ from: BASE, to: BASE }), /from und to/);
  await assert.rejects(tools.snapshot({ from: BASE, to: BASE + 16, show: ["nope"] }), /show kennt/);
  assert.deepEqual((await tools.snapshot(BASE, BASE + 16)).spans, [[BASE, BASE + 16]], "(from, to) works too");
  assert.deepEqual((await tools.snapshot({ from: BASE, length: 16 })).spans, [[BASE, BASE + 16]], "so does { from, length }");
});

test("diff lists the runs that changed with their neighbours and leaves out what the map explains", async () => {
  const r = fakeRam(BASE, SIZE);
  const tools = ramTools({ read: r.read });
  const range = { from: BASE, to: BASE + SIZE };
  const a = await tools.snapshot(range);
  r.poke(DISPLAY + 8, [1, 2, 3, 4]);              // explained: the display field
  r.poke(BASE + 0x2000, [0xaa, 0xbb]);
  r.poke(BASE + 0x2003, [0xcc]);                    // one apart from the run before
  r.poke(BASE + 0x5000, [0x11, 0x22, 0x33]);
  const b = await tools.snapshot(range);
  const d = tools.diff(a, b);
  assert.deepEqual(d.runs.map(x => [x.from, x.length]), [[BASE + 0x2000, 2], [BASE + 0x2003, 1], [BASE + 0x5000, 3]]);
  assert.equal(d.changed, 6);
  assert.equal(d.hiddenBytes, 1024, "the display bytes were not compared");
  assert.deepEqual(Array.from(d.runs[0].before), [0, 0]);
  assert.deepEqual(Array.from(d.runs[0].after), [0xaa, 0xbb]);
  assert.match(d.near(d.runs[0]), /in Boot-Löschbereich/);
  assert.equal(tools.diff(a, b, { gap: 1 }).runs.length, 2, "a gap of one byte joins the first two");
  assert.deepEqual(tools.diff(a, b, { gap: 1 }).runs[0].length, 4);
  const everything = tools.diff(a, b, { mask: false });
  assert.equal(everything.changed, 10, "unmasked, the display change counts");
  assert.equal(tools.diff(a, b, { show: ["map"] }).changed, 10);
  assert.equal(tools.diff(a, a).changed, 0);
  const text = d.summary();
  assert.match(text, /6 Byte von \d+ verglichenen Byte geändert, in 3 Läufen/);
  assert.match(text, /1024 Byte bekannt und ausgeblendet/);
  assert.match(text, new RegExp(`0x${(BASE + 0x2000).toString(16).toUpperCase()} bis .*2 Byte  00 00 -> aa bb`));
  assert.match(d.summary({ max: 1 }), /und 2 weitere Läufe/);
  assert.equal(JSON.parse(JSON.stringify(d)).runs, 3, "a result prints compactly");
});

test("diff compares what both snapshots hold and says what it could not compare", async () => {
  const r = fakeRam(BASE, SIZE);
  const tools = ramTools({ read: r.read });
  const a = await tools.snapshot({ from: BASE, to: BASE + 0x3000 });
  r.poke(BASE + 0x2800, [9]);
  r.poke(BASE + 0x100, [9]);
  const b = await tools.snapshot({ from: BASE + 0x1000, to: BASE + 0x5000 });
  const d = tools.diff(a, b);
  assert.equal(d.from, BASE + 0x1000);
  assert.equal(d.to, BASE + 0x3000);
  assert.deepEqual(d.runs.map(x => x.from), [BASE + 0x2800], "a change outside the overlap is not seen");
  assert.equal(d.notCompared, 0);
  const far = await tools.snapshot({ from: BASE + 0x5000, to: BASE + 0x5100 });
  assert.throws(() => tools.diff(a, far), /überlappen/);
  assert.throws(() => tools.diff(a, { from: 1 }), TypeError);
  // a snapshot that skipped known stretches leaves holes
  const k = fakeRam(0xc0000000, 0x10000);
  const known = ramTools({ read: k.read });
  const holes = await known.snapshot({ from: 0xc0000000, to: 0xc0003000 });
  const full = await known.snapshot({ from: 0xc0000000, to: 0xc0003000, mask: false });
  const dh = known.diff(holes, full, { mask: false });
  assert.equal(dh.compared, 0);
  assert.equal(dh.notCompared, 0x3000, "nothing is in both");
  assert.match(dh.summary(), /0 Byte von 0 verglichenen Byte geändert/);
  const twice = known.diff(holes, await known.snapshot({ from: 0xc0000000, to: 0xc0003000 }));
  assert.equal(twice.notCompared, 0, "a stretch both snapshots left out because it is known is not a hole");
  assert.equal(twice.hiddenBytes, 0x3000);
});

test("search finds a word across a chunk edge, and hides a match that lies in known bytes", async () => {
  const r = fakeRam(BASE, SIZE);
  const tools = ramTools({ read: r.read });
  const range = { from: BASE, to: BASE + SIZE };
  r.poke(BASE + 0x0ffe, [0x78, 0x56, 0x34, 0x12]);   // runs over the edge of the first chunk
  r.poke(BASE + 0x3000, [0x78, 0x56, 0x34, 0x12]);
  r.poke(DISPLAY + 16, [0x78, 0x56, 0x34, 0x12]);    // inside the display field, explained
  const res = await tools.search(0x12345678, range);
  assert.deepEqual(res.matches.map(m => m.addr), [BASE + 0x0ffe, BASE + 0x3000]);
  assert.equal(res.hiddenMatches, 1);
  assert.equal(res.truncated, false);
  const open = await tools.search(0x12345678, { ...range, mask: false });
  assert.deepEqual(open.matches.map(m => m.addr), [BASE + 0x0ffe, DISPLAY + 16, BASE + 0x3000].sort((x, y) => x - y));
  assert.equal(open.hiddenMatches, 0);
  for (const chunk of [3, 4, 7, 0x100, 0x1000]) {
    const odd = await tools.search(0x12345678, { ...range, mask: false, chunk });
    assert.deepEqual(odd.matches.map(m => m.addr), open.matches.map(m => m.addr), `chunk ${chunk}`);
  }
  assert.equal((await tools.search(0x34, { ...range, width: 1, maxMatches: 1 })).truncated, true);
  assert.deepEqual((await tools.search([0x56, 0x34], { ...range })).matches.map(m => m.addr), [BASE + 0x0fff, BASE + 0x3001]);
  assert.deepEqual((await tools.search("xyz!", { from: BASE, to: BASE + 0x100 })).matches, []);
  const text = res.summary();
  assert.match(text, /^Suche nach 4 Byte \(78 56 34 12\) von .*: 2 Treffer\./);
  assert.match(text, /1 Treffer in Bekanntem ausgeblendet/);
  assert.match(text, new RegExp(`0x${(BASE + 0xffe).toString(16).toUpperCase()}  in Boot-Löschbereich`));
});

test("a match is dropped only when every byte of it is known, and a known stretch is not read for it", async () => {
  const r = fakeRam(0xc0000000, 0x20000);
  const tools = ramTools({ read: r.read });
  r.poke(0xc0000100, [0xde, 0xad, 0xbe, 0xef]);
  const res = await tools.search([0xde, 0xad, 0xbe, 0xef], { from: 0xc0000000, to: 0xc0010000 });
  assert.deepEqual(res.matches, []);
  assert.equal(res.read, 0, "firmware code is explained, so it was not even read");
  assert.equal(r.calls.length, 0);
  const shown = await tools.search([0xde, 0xad, 0xbe, 0xef], { from: 0xc0000000, to: 0xc0010000, show: ["image"] });
  assert.deepEqual(shown.matches.map(m => m.addr), [0xc0000100]);
});

test("search can look into a snapshot without reading anything", async () => {
  const r = fakeRam(BASE, SIZE);
  const tools = ramTools({ read: r.read });
  r.poke(BASE + 0x1234, [0xef, 0xbe, 0xad, 0xde]);
  const snap = await tools.snapshot({ from: BASE, to: BASE + SIZE });
  const calls = r.calls.length;
  const res = await tools.search(0xdeadbeef, { snapshot: snap });
  assert.deepEqual(res.matches.map(m => m.addr), [BASE + 0x1234]);
  assert.equal(r.calls.length, calls, "no read went out");
  assert.deepEqual((await tools.search(0xdeadbeef, { snapshot: snap, from: BASE + 0x1235, to: BASE + SIZE })).matches, []);
  await assert.rejects(tools.search(1, { snapshot: {} }), TypeError);
});

test("progress goes to print, once at the start and then by tenths, and can be turned off or taken over", async () => {
  const r = fakeRam(BASE, SIZE);
  const lines = [];
  const tools = ramTools({ read: r.read, print: t => lines.push(t) });
  await tools.snapshot({ from: BASE, to: BASE + SIZE, chunk: 0x400 });
  assert.match(lines[0], /^Lese 0x.* in 24 Blöcken zu 1024 Byte, Bekanntes wird übersprungen\.$/);
  assert.ok(lines.length >= 5 && lines.length <= 11, `${lines.length} lines`);
  assert.match(lines.at(-1), /^  \d0 %: bis 0x/);
  lines.length = 0;
  await tools.snapshot({ from: BASE, to: BASE + SIZE, progress: false });
  assert.deepEqual(lines, []);
  const seen = [];
  await tools.search(1, { from: BASE, to: BASE + 0x2000, chunk: 0x400, progress: p => seen.push(p) });
  assert.deepEqual(seen.map(p => p.done), [0x400, 0x800, 0xc00, 0x1000, 0x1400, 0x1800, 0x1c00, 0x2000]);
  assert.equal(ramTools({ read: r.read }).snapshot({ from: BASE, to: BASE + 16 }) instanceof Promise, true, "without print a run is silent");
});

test("pauseMs waits between reads and not after the last skipped chunk", async () => {
  const r = fakeRam(BASE, SIZE);
  const waits = [];
  const tools = ramTools({ read: r.read, sleep: async ms => { waits.push(ms); } });
  await tools.snapshot({ from: BASE, to: BASE + 0x3000, pauseMs: 20 });
  assert.deepEqual(waits, [20, 20, 20]);
});

test("a reader that returns the wrong length is an error, not a silent hole", async () => {
  const tools = ramTools({ read: async (a, n) => new Uint8Array(n - 1) });
  await assert.rejects(tools.snapshot({ from: BASE, to: BASE + 16 }), /statt 16/);
});

test("where names an address and says whether a search would hide it", () => {
  const tools = ramTools({ read: async () => new Uint8Array(0) });
  assert.match(tools.where(DISPLAY + 2), /^0xC031B312: in Displaybild \(\+0x2\) \(erklärt, wird ausgeblendet\)$/);
  assert.doesNotMatch(tools.where(0xc06a3000), /ausgeblendet/);
  assert.throws(() => tools.where(1.5), RangeError);
});

/** A session on a simulated device or emulator, with a record of what was sent. */
async function rig(channel, emulator) {
  const bytes = await makeFirmware();
  const known = [{ version: [2, 2], label: "simulation", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: await sha256(new Uint8Array(16)) }] }];
  const sim = await simPort({ bytes, channel, name: emulator ? "Emulator" : "Electribe", emulator });
  const session = new DeviceSession({ port: sim.port, known, timeouts: TIMEOUTS });
  await session.connect();
  const from = META.ram;
  const to = META.ram + 5 * META_SIZE;
  sim.sim.poke(META.ram + 2 * META_SIZE + 0x0b, [0x78, 0x56, 0x34, 0x12]);      // bytes +11 to +14 of an entry, which no field covers
  sim.sim.poke(META.ram + 4 * META_SIZE + 0x00, [0x78, 0x56, 0x34, 0x12]);      // the unknown audio offset
  return { ...sim, session, bytes, from, to, emulator: { port: sim.port, baseFirmware: bytes, button: async () => {} } };
}

test("the library in the terminal and the same tools on a device session give the same answers, and only reads go out", async () => {
  const emu = await rig(9, true);
  const dev = await rig(3, false);
  const korg = makeKorg({ session: () => emu.session, emulator: emu.emulator });
  const viaTerminal = await korg.ram.snapshot({ from: emu.from, to: emu.to });
  const sent = emu.sent.length;
  const onDevice = await dev.session.exclusive(() => ramTools({ read: dev.session.ramReader() }).snapshot({ from: dev.from, to: dev.to }));
  assert.deepEqual(Array.from(onDevice.data), Array.from(viaTerminal.data));
  assert.deepEqual(onDevice.spans, viaTerminal.spans);
  assert.equal(viaTerminal.read, emu.to - emu.from, "a chunk with any unexplained byte is read whole");
  const kinds = new Set([...emu.sent, ...dev.sent].map(f => describeMessage(f).kind));
  assert.ok([...kinds].every(k => k === "read-ram" || k === "search" || k === "blech-info"), `only reads: ${[...kinds]}`);
  assert.ok(sent > 0);
  const found = await korg.ram.search(0x12345678, { from: emu.from, to: emu.to });
  assert.deepEqual(found.matches.map(m => m.addr), [emu.from + 2 * META_SIZE + 0x0b, emu.from + 4 * META_SIZE], "both words lie in bytes the map does not explain");
  assert.match(found.near(found.matches[0]), /Sample, Metadaten 3/);
  assert.deepEqual(emu.sim.faults, []);
  assert.deepEqual(dev.sim.faults, []);
});

test("through the session an out-of-window range is refused before anything is sent", async () => {
  const emu = await rig(9, true);
  const korg = makeKorg({ session: () => emu.session, emulator: emu.emulator });
  const before = emu.sent.length;
  await assert.rejects(korg.ram.snapshot({ from: 0xc7fffff0, to: 0xc8000100 }), /außerhalb des vermessenen/);
  await assert.rejects(korg.ram.search(1, { from: 0x60000000, to: 0x60000010 }), /Gesperrt/);
  assert.equal(emu.sent.length, before);
  await assert.rejects(makeKorg({ session: () => emu.session, emulator: { port: {} } }).ram.snapshot({ from: emu.from, to: emu.from + 16 }), /Emulator verbinden/);
});

test("a script's progress reaches print through makeKorg", async () => {
  const emu = await rig(9, true);
  const lines = [];
  const korg = makeKorg({ session: () => emu.session, emulator: emu.emulator }, { print: t => lines.push(t) });
  await korg.ram.snapshot({ from: emu.from, to: emu.to, chunk: 0x400 });
  assert.match(lines[0], /^Lese /);
  assert.ok(lines.length > 1);
});
