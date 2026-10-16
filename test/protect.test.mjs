import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import PROTECTED from "../data/protected.mjs";
import { PROTECTED_REGIONS, accessOf, refusal, refuseSteps, RAM_WINDOW } from "../src/protect.mjs";
import { regionCheck, admit } from "../src/gate.mjs";
import { allowedRegions, plan } from "../src/plan.mjs";
import { head, writeRamAddress, readRam, readFlash, FLASH_END, FUNC } from "../src/protocol.mjs";
import { syxEnc, u32le } from "../src/bytes.mjs";
import { Sender } from "../src/sender.mjs";
import { DeviceSession } from "../src/session.mjs";
import { Terminal } from "../src/terminal.mjs";
import { sha256 } from "../src/firmware.mjs";
import EXEC from "../data/exec.mjs";
import { makeFirmware, simPort } from "./helpers.mjs";

const ROOT = new URL("../", import.meta.url);
const ram = PROTECTED_REGIONS.filter(r => r.space === "ram");
const flash = PROTECTED_REGIONS.filter(r => r.space === "flash");
const writeStep = (addr, length) => ({ msg: writeRamAddress(9, addr, length), expect: { kind: "ack" }, role: "write" });
const readStep = (addr, length) => ({ msg: readRam(9, addr, length), expect: { kind: "read", length }, role: "query" });
/** A frame the editor's builders refuse to make: a flash read past the end, or a command number nobody knows. */
const frame = (func, payload) => [0xf0, ...head(9), func, ...syxEnc(payload), 0xf7];
const flashReadAt = (addr, length) => frame(FUNC.READ_FLASH, [...u32le(addr), ...u32le(length)]);

test("every region names a measurement that exists, a status and a sane interval", () => {
  const ids = new Set();
  for (const r of PROTECTED_REGIONS) {
    assert.ok(!ids.has(r.id), `${r.id} twice`);
    ids.add(r.id);
    assert.ok(r.start < r.end, `${r.id}: empty interval`);
    assert.ok(["write", "any"].includes(r.deny), `${r.id}: deny`);
    assert.ok(["measured", "proposal"].includes(r.status), `${r.id}: status`);
    assert.ok(r.what && r.why, `${r.id}: needs a name and an observation`);
    const m = /^measure:(\d{4}-\d{2}-\d{2})\/(.+)$/.exec(r.evidence);
    assert.ok(m, `${r.id}: evidence ${r.evidence}`);
    assert.ok(existsSync(new URL(`docs/messungen/${m[1]}-${m[2]}.md`, ROOT)), `${r.id}: no measurement file for ${r.evidence}`);
  }
});

test("the flash entries cover the whole flash, in order, without a gap and without an overlap", () => {
  const inside = flash.filter(r => r.start < FLASH_END).sort((a, b) => a.start - b.start);
  assert.equal(inside[0].start, 0, "the bootloader starts at offset 0");
  for (let i = 1; i < inside.length; i++) assert.equal(inside[i].start, inside[i - 1].end, `${inside[i].id} follows ${inside[i - 1].id}`);
  assert.equal(inside.at(-1).end, FLASH_END);
  assert.equal(flash.find(r => r.id === "flash-beyond").start, FLASH_END);
});

test("the editor's declared writes all pass, so the protection costs no existing edit", () => {
  const declared = allowedRegions();
  assert.ok(declared.length > 200);
  for (const r of declared) {
    assert.equal(refusal({ space: "ram", op: "write", addr: r.start, length: r.end - r.start }, { declared }), null, `${r.what} is refused`);
  }
});

test("an exception names a declared region, and every declared region inside a protected one is named", () => {
  const declared = allowedRegions();
  const named = (what, p) => what === p || what.startsWith(`${p} `);
  for (const r of ram.filter(x => x.except)) {
    for (const p of r.except) assert.ok(declared.some(d => named(d.what, p)), `${r.id}: "${p}" is no declared region`);
  }
  for (const d of declared) {
    for (const r of ram.filter(x => d.start < x.end && d.end > x.start)) {
      assert.ok(r.except?.some(p => named(d.what, p)), `${d.what} lies in ${r.id} without an exception`);
    }
  }
});

test("a write into each listed RAM region is refused with the region's name, at its first byte, its last and across its edge", () => {
  assert.ok(ram.length >= 10);
  for (const r of ram) {
    const probes = [[r.start, 4], [r.end - 4, 4]];
    // Across the lower edge, only where the neighbour below is not a protected region itself.
    if (r.start >= RAM_WINDOW.start + 8) probes.push([r.start - 4, 8]);
    for (const [addr, length] of probes) {
      const found = regionCheck([writeStep(addr, length)]);
      assert.equal(found.length, 1, `${r.id} at 0x${addr.toString(16)}`);
      assert.equal(found[0].severity, "fatal");
      assert.equal(found[0].code, "region");
      assert.match(found[0].message, /geschützten Bereich|außerhalb/);
      assert.ok(found[0].protectedRegion, `${r.id}: the reason says which region`);
    }
  }
});

test("the reason names the region and carries its observation", () => {
  const [found] = regionCheck([writeStep(0xc0200000, 4)]);
  assert.match(found.message, /Task-Stacks/);
  assert.match(found.message, /Zehn Task-Stacks/);
  assert.match(found.message, /0xC0200000 bis 0xC03167A8/);
  const [proposal] = regionCheck([writeStep(0xc273aa40, 4)]);
  assert.match(proposal.message, /Startstack/);
  assert.match(proposal.message, /Schutzvorschlag/, "a boundary that is only a proposal says so");
  const [measured] = regionCheck([writeStep(0xc274aa40, 4)]);
  assert.doesNotMatch(measured.message, /Schutzvorschlag/);
});

test("the region that is entered first is the one the check names, for stacks inside the boot clear area", () => {
  const found = refusal({ space: "ram", op: "write", addr: 0xc0200100, length: 4 });
  assert.equal(found.region.id, "task-stacks");
});

test("a write into each flash region is refused, whatever the command that carries it", () => {
  for (const r of flash) {
    for (const addr of [r.start, Math.min(r.end, 0x100000000) - 4]) {
      const found = refusal({ space: "flash", op: "write", addr, length: 4 });
      assert.equal(found?.region.id, r.id, `a flash write at 0x${addr.toString(16)}`);
      assert.match(found.message, /Schreiben/);
    }
  }
  // The only commands the editor knows read flash. Any other command number could write, so it is refused.
  const unknown = [{ msg: frame(0x56, [...u32le(0x220000), ...u32le(4)]), expect: { kind: "ack" }, role: "write" }];
  assert.equal(accessOf(unknown[0].msg).unknown, true);
  assert.equal(regionCheck(unknown)[0].code, "unknown-command");
  assert.match(regionCheck(unknown)[0].message, /Flash/);
});

test("a flash read is fine below the end and refused from the end on", () => {
  const below = { msg: readFlash(9, FLASH_END - 0x4000, 0x4000), expect: { kind: "flash", length: 0x4000 }, role: "query" };
  assert.deepEqual(regionCheck([below]), []);
  assert.equal(accessOf(below.msg).addr, FLASH_END - 0x4000, "the flash read says where it reads");
  for (const [addr, length] of [[FLASH_END, 4], [FLASH_END - 2, 4], [0x7ffffff0, 4]]) {
    const found = regionCheck([{ msg: flashReadAt(addr, length), expect: { kind: "flash", length }, role: "query" }]);
    assert.equal(found.length, 1, `flash read at 0x${addr.toString(16)}`);
    assert.equal(found[0].protectedRegion, "flash-beyond");
  }
});

test("reads of the memory that holds code, stacks and the heap stay open: guards and backups need them", () => {
  for (const addr of [0xc0000040, 0xc0200000, 0xc06a2940, 0xc274aa40, 0xc1000000]) {
    assert.deepEqual(regionCheck([readStep(addr, 16)]), [], `a read at 0x${addr.toString(16)}`);
  }
});

test("a read of a port or of the loader is refused, and so is anything outside the measured RAM window", () => {
  for (const [addr, length, id] of [[0x60000000, 2, "dsp-ports"], [0x60000002, 2, "dsp-ports"], [0xffff0000, 16, "loader"], [0xffff1250, 16, "loader"]]) {
    const found = regionCheck([readStep(addr, length)]);
    assert.equal(found[0]?.protectedRegion, id, `a read at 0x${addr.toString(16)}`);
    assert.match(found[0].message, /Lesen/);
  }
  for (const [addr, length] of [[0xff900a34, 4], [0xbffffff0, 32], [0xc7fffff0, 32], [0, 4]]) {
    const found = regionCheck([readStep(addr, length)]);
    assert.equal(found[0]?.protectedRegion, "outside-window", `a read at 0x${addr.toString(16)}`);
    assert.match(found[0].message, /außerhalb des vermessenen RAM-Bereichs/);
  }
  assert.deepEqual(regionCheck([readStep(0xc7ffff00, 0x100)]), [], "the last bytes of the window are readable");
});

test("a write into the other half of the window is checked against the protected regions of the first", () => {
  const distance = PROTECTED.ram.mirror.distance;
  for (const id of ["task-stacks", "heap", "irq-stack", "firmware-image"]) {
    const r = ram.find(x => x.id === id);
    const found = regionCheck([writeStep(r.start + distance, 4)]);
    assert.equal(found[0]?.protectedRegion, id, `the mirror of ${id}`);
    assert.match(found[0].message, /Spiegel/);
  }
  // What the editor declares is not hit by its own mirror: the display and the stub stay writable.
  assert.deepEqual(regionCheck([writeStep(EXEC.stubAt, 8)]), []);
});

test("the gate refuses a protected write before the simulation, with nothing else in the verdict but the reasons", async () => {
  const edit = { kind: "exec", code: Uint8Array.of(1, 0, 0xa0, 0xe3), at: 0xc0200000, guards: [], invalidate: false };
  const steps = plan(edit, { channel: 9 });
  const verdict = await admit(edit, steps, { device: { versionKnown: true, hacktribe: true, version: [2, 2] }, firmware: { known: true }, rehearsed: true, session: null });
  assert.equal(verdict.verdict, "blocked");
  assert.ok(verdict.reasons.some(r => r.code === "region" && r.protectedRegion === "task-stacks"));
});

test("a run whose step touches a protected region sends nothing at all", async () => {
  const sent = [];
  const sender = new Sender({ channel: 9, send: m => sent.push(m), timeouts: { ack: 20, read: 20, quiet: 1 } });
  const steps = [readStep(0xc0000040, 4), writeStep(0xc0200000, 4)];
  const run = await sender.run(steps);
  assert.equal(run.ok, false);
  assert.equal(run.error.kind, "protected");
  assert.equal(run.failedAt, 1);
  assert.equal(run.error.region, "task-stacks");
  assert.deepEqual(sent, [], "the clean step in front went nowhere either");
  assert.equal(refuseSteps([readStep(0xc0000040, 4)]), null);
});

/** An emulator session with the terminal over it; no hardware, no Korg data. */
async function terminalRig() {
  const bytes = await makeFirmware();
  const known = [{ version: [2, 2], label: "simulation", fingerprints: [{ addr: 0xc0000040, length: 16, sha256: await sha256(new Uint8Array(16)) }] }];
  const emu = await simPort({ bytes, channel: 9, name: "Emulator", emulator: true, execute: () => true });
  const session = new DeviceSession({ port: emu.port, known, timeouts: { search: 200, read: 200, ack: 200, pattern: 400, global: 200, quiet: 5 } });
  session.execSettleMs = 0;
  await session.connect();
  const emulator = { port: emu.port, baseFirmware: bytes, button: async () => {} };
  const terminal = new Terminal({ device: { session }, emulator, probe: async () => session, timing: { settleMs: 0, codeSettleMs: 0 } });
  return { emu, session, terminal };
}

const MOV_R0_1_BX_LR = "[0xE3A00001, 0xE12FFF1E]";

test("the terminal meets the same rule: a stub below the stack area and a read of a port are refused, a read of code is not", async () => {
  const { emu, terminal } = await terminalRig();
  const before = emu.sent.length;
  await assert.rejects(() => terminal.runDirect(`KORG.exec(${MOV_R0_1_BX_LR}, { at: 0xC0200000 })`), /geschützten Bereich „Task-Stacks“/);
  await assert.rejects(() => terminal.runDirect("KORG.ram.read(0x60000000, 2)"), /DSP-Ports/);
  await assert.rejects(() => terminal.runDirect("KORG.ram.read(0xFF900A34, 4)"), /außerhalb des vermessenen RAM-Bereichs/);
  assert.equal(emu.sent.length, before, "nothing of it reached the port");
  const code = await terminal.runDirect("KORG.ram.read(0xC0000040, 4)");
  assert.equal(code.length, 4);
});

test("a rehearsal of such a script fails and cannot be sent", async () => {
  const { terminal } = await terminalRig();
  const record = await terminal.rehearse(`KORG.exec(${MOV_R0_1_BX_LR}, { at: 0xC03167A0 })`);
  assert.equal(record.ok, false);
  assert.equal(record.sendable, false);
  assert.match(record.reason, /Task-Stacks/);
  const reads = await terminal.rehearse("KORG.ram.read(0x60000000, 2)");
  assert.equal(reads.ok, false);
  assert.match(reads.reason, /DSP-Ports/);
});

test("docs/speicherbereiche.md lists every region of the rule by its id", () => {
  const doc = readFileSync(new URL("docs/speicherbereiche.md", ROOT), "utf8");
  for (const r of PROTECTED_REGIONS) assert.ok(doc.includes(`\`${r.id}\``), `${r.id} is missing in docs/speicherbereiche.md`);
});
