import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { plan, allowedRegions, MAX_WRITE } from "../src/plan.mjs";
import { regionCheck, admit } from "../src/gate.mjs";
import { DeviceSession, electribePorts } from "../src/session.mjs";
import { installWebMidiStub } from "../src/webmidi.mjs";
import { describeMessage, writeRamAddress, writeRamData } from "../src/protocol.mjs";
import { tableEntry } from "../src/map/address.mjs";
import { field } from "../src/map/index.mjs";
import { readUnits } from "../src/node.mjs";
import { sha256 } from "../src/firmware.mjs";
import { makeImage, makeRecord, IMAGE_SIZE } from "./helpers.mjs";
import { withFaults } from "./support/faults.mjs";

const units = readUnits();
const KNOWN = [{ version: [2, 2], label: "simulation", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: await sha256(new Uint8Array(16)) }] }];
const FAST = { search: 200, read: 200, ack: 200, pattern: 400, global: 200 };

function firmwareImage() {
  // The real image is 0x200100 bytes; the map's checks need that size.
  const image = makeImage([
    { kind: "ifx", slot: 50, record: makeRecord("ifx", { name: "Gate Filter", devices: { ifx1: 0x0a }, params: { ifx1: [0, 64, 64, 64] } }) },
  ]);
  const bytes = new Uint8Array(0x200100);
  bytes.set(image.bytes.subarray(0, Math.min(IMAGE_SIZE, bytes.length)));
  return bytes;
}

async function connected({ faults = null, nav = {} } = {}) {
  const bytes = firmwareImage();
  const sim = installWebMidiStub({ image: { bytes }, channel: 9, latencyMs: 1, target: nav });
  const access = await nav.requestMIDIAccess({ sysex: true });
  let port = electribePorts(access)[0];
  if (faults) port = withFaults(port, faults);
  const session = new DeviceSession({ port, known: KNOWN, timeouts: FAST });
  await session.connect();
  session.useFirmware(bytes, { known: true, reasons: [], original: false }, { units, profile: null });
  return { session, sim, bytes };
}

const record = (bytes, slot) => {
  const e = tableEntry("table.ifx", slot - 1);
  return Uint8Array.from(bytes.subarray(e.file, e.file + e.size));
};

test("a record goes out in writes no larger than the measured limit, with backup and read-back", () => {
  const bytes = new Uint8Array(0x20c).fill(1);
  const steps = plan({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { channel: 9 });
  assert.equal(steps[0].role, "backup");
  assert.equal(steps.at(-1).role, "verify");
  for (const s of steps.filter(x => x.role === "write")) assert.ok(s.target.length <= MAX_WRITE);
  const written = steps.filter(s => describeMessage(s.msg).kind === "write-address").reduce((n, s) => n + s.target.length, 0);
  assert.equal(written, 0x20c);
});

test("a multi-site field plans all backups, then all writes, then all read-backs", () => {
  const steps = plan({ kind: "sites", fieldId: "menu.ifxCount", value: 61 }, { channel: 9 });
  const roles = steps.map(s => s.role);
  assert.equal(roles.indexOf("write"), 13);
  assert.equal(roles.lastIndexOf("write"), 13 + 2 * 13 - 1);
  assert.equal(roles.filter(r => r === "verify").length, 13);
});

test("plan refuses to work without a channel", () => {
  assert.throws(() => plan({ kind: "readRam", addr: 0xc0000000, length: 1 }, {}), /channel/);
});

test("a write outside every declared region is blocked before the dry run", () => {
  const stray = [{ msg: writeRamAddress(9, 0xc0001000, 4), expect: { kind: "ack" }, role: "write" }];
  assert.equal(regionCheck(stray, allowedRegions({ build: "hacktribe" }))[0].code, "region");
  const crossing = tableEntry("table.ifx", 0);
  const over = [{ msg: writeRamAddress(9, crossing.ram + 0x200, 0x20), expect: { kind: "ack" }, role: "write" }];
  assert.equal(regionCheck(over, allowedRegions({ build: "hacktribe" }))[0].code, "region", "a write that runs into the next record");
  const korg = [{ msg: writeRamAddress(9, 0xc00a7f60 + 0x200, 0x20), expect: { kind: "ack" }, role: "write" }];
  assert.equal(regionCheck(korg, allowedRegions({ build: "stock" }))[0].code, "region", "a write that runs into the next record of Korg's build");
  assert.deepEqual(regionCheck(korg.map(s => ({ ...s, msg: writeRamAddress(9, 0xc00a7f60 + 0x20, 0x20) })), allowedRegions({ build: "stock" })), [], "inside one of them it passes");
  assert.ok(allowedRegions().length > 200);
});

test("live: a record written, read back, and taken back with one undo", async () => {
  const { session, sim, bytes } = await connected();
  const before = record(bytes, 50);
  const after = Uint8Array.from(before);
  after[0x135 + 2] = 99;
  const unconfirmed = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after, before });
  assert.equal(unconfirmed.needsConfirmation, true, "a warning waits for a yes");
  assert.equal(sim.device.peek(tableEntry("table.ifx", 49).ram + 0x135 + 2, 1)[0], before[0x135 + 2], "and nothing went out");
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after, before }, { confirmed: true });
  assert.equal(res.ok, true, JSON.stringify(res.gate?.reasons || res.error?.message));
  const e = tableEntry("table.ifx", 49);
  assert.equal(sim.device.peek(e.ram + 0x135 + 2, 1)[0], 99);
  assert.equal(session.twin.peek(e.ram + 0x135 + 2, 1)[0], 99);
  assert.equal((await session.undo()).ok, true);
  assert.equal(sim.device.peek(e.ram + 0x135 + 2, 1)[0], before[0x135 + 2]);
  assert.deepEqual(sim.faults, []);
});

test("live: an unknown device is only read", async () => {
  const bytes = firmwareImage();
  const nav = {};
  installWebMidiStub({ image: { bytes }, channel: 9, latencyMs: 1, target: nav });
  const port = electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0];
  const session = new DeviceSession({ port, known: [], timeouts: FAST });
  await session.connect();
  session.useFirmware(bytes, { known: true, reasons: [] }, { units });
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: record(bytes, 50) });
  assert.equal(res.ok, false);
  assert.equal(res.gate.reasons[0].code, "unknown-device");
});

test("live: no answer within the waiting time is reported, never repeated, and the backup offered", async () => {
  // Replies: search, probe, backup, first ack, first data ack; the second write's ack never comes.
  const { session, sim } = await connected({ faults: { swallow: [6] } });
  const sent = [];
  const send = session.sender.send;
  session.sender.send = m => { sent.push(m); send(m); };
  const before = sim.device.peek(tableEntry("table.ifx", 49).ram, 0x20c);
  const bytes = record(session.twin.image.bytes, 50);
  bytes.fill(0x11, 0x135, 0x135 + 40);
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "timeout");
  const writes = sent.filter(m => describeMessage(m).kind === "write-address").map(m => describeMessage(m).addr);
  assert.equal(new Set(writes).size, writes.length, "no write address sent twice");
  assert.equal(res.rolledBack, false, "the backup is offered, not written on its own");
  assert.ok(session.blocked);
  assert.match(res.pending.now.text, /Gemisch|neue Stand|alte Stand/);
  assert.equal((await session.resolve("restore")).ok, true);
  assert.deepEqual(sim.device.peek(tableEntry("table.ifx", 49).ram, 0x20c), before);
  assert.equal(session.blocked, null);
});

test("live: a reply that arrives after its timeout is never taken for the next answer", async () => {
  // The backup read's reply (third) comes after the read timeout of 200 ms.
  const { session, sim } = await connected({ faults: { delay: { 3: 350 } } });
  const bytes = record(session.twin.image.bytes, 50);
  bytes[0x135] = 33;
  const first = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  assert.equal(first.ok, false);
  assert.equal(first.error.kind, "timeout");
  const second = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  assert.equal(second.ok, true, second.error?.message);
  assert.deepEqual(second.backups[0].bytes, record(firmwareImage(), 50), "the backup is the slot's own content, not a stale reply");
  assert.equal(sim.device.peek(tableEntry("table.ifx", 49).ram + 0x135, 1)[0], 33);
});

test("live: a second operation while one runs is refused, not interleaved", async () => {
  const { session } = await connected();
  const bytes = record(session.twin.image.bytes, 50);
  const a = session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  await assert.rejects(session.apply({ kind: "fxRecord", table: "ifx", slot: 51, bytes }, { confirmed: true }), /läuft schon/);
  await assert.rejects(session.undo(), /läuft schon/);
  assert.equal((await a).ok, true);
});

test("live: a read-back that does not match is shown, blocks the target, and the backup can be put back", async () => {
  // Replies: search, probe, backup, six acks, then the read-back as the tenth.
  const { session, sim, bytes: image } = await connected({ faults: { corruptRead: [10] } });
  const before = sim.device.peek(tableEntry("table.ifx", 49).ram, 0x20c);
  const bytes = record(image, 50);
  bytes[0x135] = 12;
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "mismatch");
  assert.equal(res.pending.now.text, "Der neue Stand ist vollständig angekommen.");
  const next = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  assert.ok(next.gate.reasons.some(r => r.code === "target-blocked"));
  assert.equal((await session.resolve("restore")).ok, true);
  assert.deepEqual(sim.device.peek(tableEntry("table.ifx", 49).ram, 0x20c), before);
});

test("live: what failed survives a reconnect; the next session is still blocked and reads back", async () => {
  const nav = {};
  const { session, sim } = await connected({ faults: { corruptRead: [10] }, nav });
  const bytes = record(session.twin.image.bytes, 50);
  bytes[0x135] = 44;
  await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes }, { confirmed: true });
  const again = new DeviceSession({ port: electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0], carry: session.carry, known: KNOWN, timeouts: FAST });
  await again.connect();
  assert.ok(again.blocked, "still blocked after reconnecting");
  assert.match(again.pending.now.text, /neue Stand/);
  assert.equal((await again.resolve("keep")).ok, true);
  assert.equal(again.blocked, null);
  assert.equal(sim.device.peek(tableEntry("table.ifx", 49).ram + 0x135, 1)[0], 44);
});

test("live: a multi-site field half written is rolled back as a whole", async () => {
  const { session, sim, bytes } = await connected({ faults: { swallow: [20] } });
  const f = field("menu.ifxCount");
  const res = await session.apply({ kind: "sites", fieldId: "menu.ifxCount", value: 61 });
  assert.equal(res.ok, false);
  assert.equal(res.rolledBack, true);
  for (const s of f.sites) assert.equal(sim.device.image.bytes[s.file], bytes[s.file], `site 0x${s.file.toString(16)}`);
});

test("live: unplugged during a send fails at once, and a failed rollback blocks the target", async () => {
  const nav = {};
  const { session } = await connected({ faults: { unplugAfter: 4 }, nav });
  session.port.unplugged = () => session.lost();
  const rec = record(session.twin.image.bytes, 50);
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: rec }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "disconnected");
  assert.ok(session.blocked, "nothing more goes to this target");
  const next = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: rec }, { confirmed: true });
  assert.equal(next.gate.reasons.some(r => r.code === "target-blocked"), true);
});

test("dry run: broken messages are caught by the simulation, even past the region check", async () => {
  const { session } = await connected();
  const e = tableEntry("table.ifx", 49);
  const cases = [
    { code: "write-without-header", steps: [{ msg: writeRamData(9, new Uint8Array(4)), expect: { kind: "ack" }, role: "write", target: { addr: e.ram, length: 4 } }] },
    { code: "channel", steps: [{ msg: writeRamAddress(0, e.ram, 4), expect: { kind: "ack" }, role: "write", target: { addr: e.ram, length: 4 } }] },
  ];
  for (const c of cases) {
    const res = await admit({ kind: "raw" }, c.steps, session.context());
    assert.equal(res.verdict, "blocked");
    assert.equal(res.reasons[0].code, c.code);
  }
});

test("the gate downgrades only errors a byte-identical factory slot already had", async () => {
  const { session, bytes } = await connected();
  // A record that maps a parameter past the end of its unit's list: an error.
  const bad = makeRecord("ifx", { devices: { ifx1: 0x0a } });
  bad.map = [{ source: 0x42, chain: 0x00, param: 30, low: 0, high: 127 }];
  const res = await session.check({ kind: "fxRecord", table: "ifx", slot: 50, bytes: bad.bytes, before: bad.bytes });
  assert.equal(res.verdict, "blocked", "slot 50 is no factory slot, so the error stays an error");
});

// Only plan() builds messages for the device. The simulation answers, the
// command line and the tests are their own matter.
test("no application module builds SysEx except through plan", () => {
  const root = new URL("../", import.meta.url).pathname;
  const allowed = new Set(["src/protocol.mjs", "src/plan.mjs", "src/device.mjs", "src/webmidi.mjs", "src/bytes.mjs"]);
  const builders = /\b(search|patternRequest|patternDump|globalRequest|globalDump|readRam|writeRamAddress|writeRamData|execute)\s*\(/;
  const walk = d => readdirSync(d).flatMap(n => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
  for (const file of [...walk(join(root, "src")), ...walk(join(root, "site/app"))].filter(f => f.endsWith(".mjs"))) {
    const rel = file.slice(root.length);
    if (allowed.has(rel)) continue;
    const code = readFileSync(file, "utf8");
    assert.doesNotMatch(code, /\[\s*0xf0\b/i, `${rel} assembles a SysEx message`);
    if (/from\s+["'][./]*protocol\.mjs["']/.test(code)) {
      assert.doesNotMatch(code.replace(/parse\w+\(/g, ""), builders, `${rel} builds a message itself`);
    }
  }
});

// ---- phase 3b: patterns at the device ----

import { patternDump, patternRequest, globalDump } from "../src/protocol.mjs";
import { makePattern } from "./helpers.mjs";
import { Pattern } from "../src/pattern.mjs";

async function patternSession({ known = KNOWN, faults = null, image = { bytes: firmwareImage() } } = {}) {
  const nav = {};
  const start = makePattern({ name: "Am Geraet" });
  const sim = installWebMidiStub({ image, channel: 9, latencyMs: 1, target: nav, pattern: start });
  let port = electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0];
  if (faults) port = withFaults(port, faults);
  const session = new DeviceSession({ port, known, timeouts: FAST });
  await session.connect();
  return { session, sim, start, nav };
}

const edited = () => {
  const p = new Pattern(makePattern({ name: "Neu" }));
  for (let part = 0; part < 16; part++) p.setRaw("part.glide", [part], 0);
  return p.bytes;
};

test("patterns: the buffer is fetched, sent, read back, and the old one restored with undo", async () => {
  const { session, sim, start } = await patternSession();
  assert.equal(new Pattern(await session.fetchPattern()).name, "Am Geraet");
  const res = await session.apply({ kind: "patternSend", block: edited() });
  assert.equal(res.ok, true, JSON.stringify(res.gate?.reasons || res.error?.message));
  assert.equal(new Pattern(sim.device.pattern).name, "Neu");
  assert.equal(new Pattern(res.backup).name, "Am Geraet", "the buffer was kept before it was replaced");
  assert.equal((await session.undo()).ok, true);
  assert.deepEqual(sim.device.pattern.subarray(0, 64), start.subarray(0, 64));
});

test("patterns without a verified code fingerprint remain read-only", async () => {
  const ok = await patternSession({ image: null });
  assert.equal(ok.session.device.hacktribe, false, "no image, so RAM reads go unanswered");
  assert.equal((await ok.session.apply({ kind: "patternSend", block: edited() })).ok, false);
  const unknown = await patternSession({ known: [] });
  const res = await unknown.session.apply({ kind: "patternSend", block: edited() });
  assert.equal(res.gate.reasons[0].code, "unknown-device");
});

test("patterns: a send without a backup first is stopped by the gatekeeper", async () => {
  const { session } = await patternSession();
  const steps = [{ msg: patternDump(9, edited()), expect: { kind: "none" }, role: "write" }];
  const res = await admit({ kind: "patternSend", block: edited() }, steps, session.context());
  assert.equal(res.verdict, "blocked");
  assert.equal(res.reasons[0].code, "no-pattern-backup");
});

test("patterns: a dump of the wrong length or frame, or for another channel, fails the dry run", async () => {
  const { session } = await patternSession();
  const backup = { msg: patternRequest(9), expect: { kind: "pattern" }, role: "backup" };
  const broken = edited(); broken[0] = 0;
  const cases = [
    ["pattern-frame", patternDump(9, broken)],
    ["pattern-length", [...patternDump(9, edited()).slice(0, 2000), 0xf7]],
    ["channel", patternDump(3, edited())],
  ];
  for (const [code, msg] of cases) {
    const res = await admit({ kind: "patternSend", block: edited() }, [backup, { msg, expect: { kind: "none" }, role: "write" }], session.context());
    assert.equal(res.verdict, "blocked", code);
    assert.equal(res.reasons[0].code, code);
  }
});

test("globals: a dump of the wrong length or frame fails the dry run", async () => {
  const { session } = await patternSession();
  const good = new Uint8Array(256); good.set([0x47, 0x4c, 0x53, 0x54]); good[41] = 9;
  const bad = Uint8Array.from(good); bad[0] = 0;
  for (const [code, msg] of [["global-frame", globalDump(9, bad)], ["global-length", [...globalDump(9, good).slice(0, 100), 0xf7]]]) {
    const res = await admit({ kind: "globalSend" }, [{ msg, expect: { kind: "none" }, role: "write" }], session.context());
    assert.equal(res.verdict, "blocked", code);
    assert.equal(res.reasons[0].code, code);
  }
});

test("patterns: a step on without trigger is a warning that waits for a yes", async () => {
  const { session, sim } = await patternSession();
  const p = new Pattern(edited());
  p.setRaw("step.on", [0, 0], 1);
  p.setRaw("step.trigger", [0, 0], 0);
  const res = await session.apply({ kind: "patternSend", block: p.bytes });
  assert.equal(res.needsConfirmation, true);
  assert.equal(res.gate.reasons[0].code, "step-without-trigger");
  assert.equal(new Pattern(sim.device.pattern).name, "Am Geraet", "nothing sent before the yes");
});

test("patterns: glide is reported as lost, and a read-back without it still counts as arrived", async () => {
  const { session, sim } = await patternSession();
  const p = new Pattern(edited());
  p.setRaw("part.glide", [2], 64);
  const res = await session.apply({ kind: "patternSend", block: p.bytes }, { confirmed: true });
  assert.equal(res.ok, true);
  assert.ok(res.gate.reasons.some(r => r.code === "glide-dropped"));
  assert.equal(new Pattern(sim.device.pattern).raw("part.glide", [2]), 0);
});

test("patterns: a read-back that does not match blocks, and the kept buffer can be sent back", async () => {
  const { session, sim, start } = await patternSession({ faults: { corruptRead: [5] } });
  const res = await session.apply({ kind: "patternSend", block: edited() });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "mismatch");
  assert.equal(res.rolledBack, false);
  assert.ok(session.blocked);
  assert.equal((await session.resolve("restore")).ok, true);
  assert.deepEqual(sim.device.pattern.subarray(0, 64), start.subarray(0, 64));
});

test("patterns: a failed send is read back after a reconnect even when RAM reads go unanswered", async () => {
  const { session, sim, nav } = await patternSession({ faults: { corruptRead: [5] } });
  await session.apply({ kind: "patternSend", block: edited() });
  // Meanwhile the old pattern is back in the buffer, so only a fresh read-back can tell.
  sim.device.pattern = Uint8Array.from(session.pending.pattern);
  // Reply 2 is the first fingerprint read; without it the device counts as no Hacktribe.
  const port = withFaults(electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0], { swallow: [2] });
  const again = new DeviceSession({ port, carry: session.carry, known: KNOWN, timeouts: FAST });
  await again.connect();
  assert.equal(again.device.hacktribe, false);
  assert.ok(again.blocked, "still blocked after reconnecting");
  assert.equal(again.pending.now.text, "Im Puffer steht noch das alte Pattern.");
});

test("an undo of an instruction immediate checks the whole word before and after", () => {
  const f = field("menu.mfxCount");
  const at = 0xc0000000 + f.where.offset - 0x100;
  const other = tableEntry("table.mfx", 0).ram;
  const steps = plan({ kind: "restore", backups: [{ addr: at, bytes: Uint8Array.of(33) }, { addr: other, bytes: Uint8Array.of(1, 2) }] }, { channel: 9 });
  const guards = steps.filter(s => s.role === "guard");
  assert.equal(guards.length, 1, "only the instruction gets a guard");
  assert.equal(guards[0].target.addr, at);
  assert.equal(guards[0].expect.length, 4);
  assert.equal(steps.indexOf(guards[0]), 0, "the guard comes before any write");
  const verify = steps.filter(s => s.role === "verify");
  assert.deepEqual([...verify[0].compare], [33, 0x00, 0xa0, 0xe3]);
  assert.equal(verify[1].compare.length, 2);
});

// ---- measured 2026-10-07/08: write acknowledgement, read echo, instruction immediate ----

import { classify, parseAck, parseReadRam as parseRead, ReplyError as RE } from "../src/protocol.mjs";

test("write acknowledgements distinguish RAM 0x21 from pattern 0x23", () => {
  assert.equal(classify([0xf0, 0x42, 0x39, 0x00, 0x01, 0x24, 0x21, 0xf7], 9), "ack");
  assert.equal(classify([0xf0, 0x42, 0x39, 0x00, 0x01, 0x24, 0x23, 0xf7], 9), "ack");
  assert.throws(() => parseAck([0xf0, 0x42, 0x39, 0x00, 0x01, 0x24, 0x23, 0xf7], 9, 0x21), RE);
  assert.equal(classify([0xf0, 0x42, 0x23, 0xf7], 9), "other");
});

test("a read answer must echo the read command in bytes 7 and 8", () => {
  const good = [0xf0, 0x42, 0x39, 0x00, 0x01, 0x24, 0x54, 0x52, 0x00, 0x00, 1, 2, 3, 4, 0xf7];
  assert.deepEqual(Array.from(parseRead(good, 9, 4)), [1, 2, 3, 4]);
  const bad = [...good]; bad[7] = 0x00;
  assert.throws(() => parseRead(bad, 9, 4), RE);
});

test("the master menu length is written only where the expected instruction stands", async () => {
  const fw = await makeFirmware();
  const nav = {};
  const stub = installWebMidiStub({ image: { bytes: fw }, channel: 9, latencyMs: 1, target: nav });
  const port = electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0];
  const session = new DeviceSession({ port, known: KNOWN, timeouts: FAST });
  await session.connect();
  assert.equal(session.device.versionKnown, true, "code fingerprint is verified");
  session.useFirmware(fw, { known: true, reasons: [] }, { units });
  const at = field("menu.mfxCount").where.offset;
  const ram = 0xc0000000 + at - 0x100;

  const res = await session.apply({ kind: "immediate", fieldId: "menu.mfxCount", value: 40 }, { confirmed: true });
  assert.equal(res.ok, true, res.error?.message ?? JSON.stringify(res.gate?.reasons));
  assert.deepEqual(Array.from(stub.device.peek(ram, 4)), [40, 0x00, 0xa0, 0xe3]);
  assert.deepEqual(Array.from(session.twin.peek(ram, 4)), [40, 0x00, 0xa0, 0xe3]);
  assert.equal((await session.undo()).ok, true);
  assert.deepEqual(Array.from(session.twin.peek(ram, 4)), [33, 0x00, 0xa0, 0xe3]);

  // The device holds something else than the file said: the sender reads the
  // word first and writes nothing.
  stub.device.image.bytes[at + 3] = 0xe1;
  const onDevice = await session.apply({ kind: "immediate", fieldId: "menu.mfxCount", value: 40 }, { confirmed: true });
  assert.equal(onDevice.ok, false);
  assert.equal(onDevice.error.kind, "unexpected-code");
  assert.equal(stub.device.image.bytes[at], 33, "nothing written");
  assert.equal(session.blocked, null, "nothing was written, so nothing to decide");

  // The file itself carries another instruction: the dry run already stops it.
  session.twin.image.bytes[at + 3] = 0xe1;
  const inFile = await session.apply({ kind: "immediate", fieldId: "menu.mfxCount", value: 40 }, { confirmed: true });
  assert.equal(inFile.gate.reasons[0].code, "unexpected-code");
});

import { makeFirmware } from "./helpers.mjs";

test("the whole flash is read in blocks below the end the device hangs at", async () => {
  const flash = new Uint8Array(0x1000000);
  for (let i = 0; i < flash.length; i += 0x1000) flash[i] = (i >> 12) & 0xff;
  const nav = {};
  const bytes = firmwareImage();
  const sim = installWebMidiStub({ image: { bytes }, channel: 9, latencyMs: 0, target: nav });
  sim.device.flash = flash;
  const session = new DeviceSession({ port: electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0], known: KNOWN, timeouts: FAST });
  await session.connect();
  let last = 0;
  const read = await session.readFlash({ block: 0x40000, onProgress: done => { last = done; } });
  assert.deepEqual(read, flash);
  assert.equal(last, 0x1000000);
  assert.deepEqual(sim.faults, [], "no read at or past 0x1000000");
  assert.throws(() => plan({ kind: "flashRead", addr: 0xffc000, length: 0x8000 }, { channel: 9 }), /past 0x1000000/);
});

async function rehearsed({ faults = null } = {}) {
  const device = await connected();
  const emuNav = {};
  const emuSim = installWebMidiStub({ image: { bytes: device.bytes }, channel: 9, latencyMs: 1, target: emuNav });
  let port = electribePorts(await emuNav.requestMIDIAccess({ sysex: true }))[0];
  if (faults) port = withFaults(port, faults);
  port.running = true;
  const emu = new DeviceSession({ port, known: KNOWN, timeouts: FAST });
  emu.settleMs = 0;
  await emu.connect();
  device.session.rehearseOn(emu);
  return { ...device, emu, emuSim, port };
}

test("live with a required rehearsal: no emulator, no edit at the device", async () => {
  const { session, sim, bytes } = await connected();
  session.requireRehearsal = true;
  const e = tableEntry("table.ifx", 49);
  const before = sim.device.peek(e.ram, e.size);
  const after = record(bytes, 50);
  after[0x135 + 2] = 33;
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "rehearsal");
  assert.deepEqual(sim.device.peek(e.ram, e.size), before, "nothing went to the device");
});

test("live with rehearsal: the emulator gets the edit first, then the device, and undo takes back both", async () => {
  const { session, sim, emu, emuSim, bytes } = await rehearsed();
  const e = tableEntry("table.ifx", 49);
  const after = record(bytes, 50);
  after[0x135 + 2] = 77;
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(res.ok, true, res.error?.message);
  assert.equal(emuSim.device.peek(e.ram + 0x135 + 2, 1)[0], 77);
  assert.equal(sim.device.peek(e.ram + 0x135 + 2, 1)[0], 77);
  assert.equal((await session.undo()).ok, true);
  assert.notEqual(emuSim.device.peek(e.ram + 0x135 + 2, 1)[0], 77, "the emulator is taken back too");
  assert.equal(emu.history.length, 0);
});

test("live with rehearsal: an edit the emulator does not read back never reaches the device", async () => {
  // Replies 1 and 2 on the emulator port are the search and the fingerprint; every read after them comes back altered.
  const { session, sim, bytes } = await rehearsed({ faults: { corruptRead: Array.from({ length: 30 }, (_, i) => i + 3) } });
  const e = tableEntry("table.ifx", 49);
  const before = sim.device.peek(e.ram, e.size);
  const after = record(bytes, 50);
  after[0x135 + 2] = 66;
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.equal(res.error.kind, "rehearsal");
  assert.deepEqual(sim.device.peek(e.ram, e.size), before, "nothing went to the device");
});

test("live with rehearsal: a firmware that stopped after the edit keeps it from the device", async () => {
  const { session, sim, bytes, port } = await rehearsed();
  const e = tableEntry("table.ifx", 49);
  const before = sim.device.peek(e.ram, e.size);
  const after = record(bytes, 50);
  after[0x135 + 2] = 55;
  const realSend = port.out.send;
  port.out.send = msg => { realSend(msg); if (msg[6] === 0x52) port.running = false; };   // stops after the read-back
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.match(res.error.message, /stehen geblieben/);
  assert.deepEqual(sim.device.peek(e.ram, e.size), before);
});

test("live with rehearsal: an emulator that stops answering after the edit takes it back, and stays usable", async () => {
  const { session, sim, emu, emuSim, bytes, port } = await rehearsed();
  const e = tableEntry("table.ifx", 49);
  const original = emuSim.device.peek(e.ram, e.size);
  const after = record(bytes, 50);
  after[0x135 + 2] = 44;
  const realSend = port.out.send;
  let mute = false;
  port.out.send = msg => { if (msg[2] === 0x50 && mute) return; realSend(msg); if (msg[6] === 0x52) mute = true; };   // search goes unanswered after the read-back
  const res = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(res.ok, false);
  assert.match(res.error.message, /antwortet danach nicht mehr/);
  assert.deepEqual(emuSim.device.peek(e.ram, e.size), original, "the emulator was taken back");
  assert.equal(emu.history.length, 0);
  assert.equal(sim.device.peek(e.ram + 0x135 + 2, 1)[0] === 44, false, "the device never got it");
});

test("live with rehearsal: a probe that failed half-way does not block the next edit", async () => {
  // Reply 4 on the emulator port is the first write's ack: swallowed, so the write may have half arrived.
  const { session, emu, bytes } = await rehearsed({ faults: { swallow: [4] } });
  const after = record(bytes, 50);
  after[0x135 + 2] = 33;
  const first = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(first.ok, false);
  assert.equal(emu.blocked, null, "the scratch emulator is not left blocked");
  const second = await session.apply({ kind: "fxRecord", table: "ifx", slot: 50, bytes: after }, { confirmed: true });
  assert.equal(second.ok, true, second.error?.message);
});
