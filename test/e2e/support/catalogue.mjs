/**
 * The fault catalogue of phase 3a, run inside the page against the Web MIDI
 * stand-in. Every row is tried twice: without the stage that should catch
 * it (the fault reaches the simulated device, or the bad record lands in
 * its RAM), and through the editor's own path, where that stage stops it.
 * Test code only; never part of the page.
 */
import KNOWN from "/data/devices.mjs";
import { DeviceSession, electribePorts } from "/src/session.mjs";
import { plan } from "/src/plan.mjs";
import { admit } from "/src/gate.mjs";
import { identify } from "/src/firmware.mjs";
import { FxRecord } from "/src/record.mjs";
import { VsbImage } from "/src/image.mjs";
import { parseUnits, setUnits } from "/src/units.mjs";
import { head, writeRamAddress, writeRamData } from "/src/protocol.mjs";
import { syxEnc, u32le } from "/src/bytes.mjs";
import { tableEntry } from "/src/map/address.mjs";

const frame = body => [0xf0, ...body, 0xf7];

export async function runCatalogue() {
  const units = setUnits(parseUnits(await (await fetch("/data/units.json")).json()));
  const bytes = new Uint8Array(await (await fetch("/test-support/files/system.vsb")).arrayBuffer());
  const sim = window.__ceeSim;
  const access = await navigator.requestMIDIAccess({ sysex: true });
  const session = new DeviceSession({ port: electribePorts(access)[0], known: KNOWN });
  await session.connect();
  session.useFirmware(bytes, await identify(bytes), { units, profile: null });
  const ch = session.device.channel;
  const image = new VsbImage(bytes);
  const base = image.read("ifx", 50);
  const rows = [];

  const record = (kind, edit) => {
    const r = kind === "ifx" ? base.clone() : new FxRecord(base.bytes, "mfx");
    edit(r);
    return r.bytes;
  };
  const faultsSince = n => sim.faults.slice(n).map(f => f.code);

  // Linter rows: without the gate the record arrives in RAM; with it, the send is refused.
  const lintRows = [
    ["stage2-fatal", "ifx", 52, r => r.setDevice("ifx2", 0x18)],
    ["stage2-silent", "ifx", 53, r => r.setDevice("ifx2", 0x16)],
    ["stage1-needs-solo", "ifx", 54, r => { r.setDevice("ifx1", 0x09); r.setDevice("ifx2", 0x0a); }],
    ["master-unit-in-insert", "ifx", 55, r => r.setDevice("ifx1", 0x36)],
    ["wrong-table", "mfx", 34, r => { r.setDevice("mfx", 0); r.setDevice("ifx1", 0x0a); }],
    ["no-switch-on-fade", "mfx", 35, r => { r.setDevice("ifx1", 0); r.setDevice("ifx2", 0); r.setDevice("mfx", 0x3b); r.map = []; }],
  ];
  for (const [code, table, slot, edit] of lintRows) {
    const rec = record(table, edit);
    const entry = tableEntry(`table.${table}`, slot - 1);
    const raw = await session.sender.run(plan({ kind: "fxRecord", table, slot, bytes: rec }, { channel: ch }));
    const arrived = raw.ok && sim.device.peek(entry.ram, rec.length).every((b, i) => b === rec[i]);
    const res = await session.apply({ kind: "fxRecord", table, slot, bytes: rec }, { confirmed: true });
    rows.push({ row: code, stage: "Prüfer", without: arrived, caught: !res.ok && res.gate?.reasons.some(r => r.code === code) });
  }

  // Gatekeeper rows: addresses the region check stops; the simulation's own check, tested on its own.
  const inside = 0xc0001000;
  const gateRows = [
    ["not-ram", 0x00001000, "not-ram"],
    ["out-of-range", 0xc0300000, "out-of-range"],
    ["outside-allowed-region", inside, null],
  ];
  for (const [row, addr, simCode] of gateRows) {
    const steps = [
      { msg: writeRamAddress(ch, addr, 4), expect: { kind: "ack" }, role: "write", target: { addr, length: 4 } },
      { msg: writeRamData(ch, new Uint8Array([1, 2, 3, 4])), expect: { kind: "ack" }, role: "write", target: { addr, length: 4 } },
    ];
    const n = sim.faults.length;
    // Straight to the port: the sender refuses protected regions as well, so it is not "without the gate".
    for (const s of steps) access.outputs.get("sim-out").send(s.msg);
    const without = simCode ? faultsSince(n).includes(simCode) : faultsSince(n).length === 0;
    const res = await admit({ kind: "raw" }, steps, session.context());
    rows.push({ row, stage: "Türsteher", without, caught: res.verdict === "blocked" && res.reasons[0].code === "region" });
  }

  // Dry-run rows: broken message lists through a test entry, the way plan() never builds them.
  const slot = tableEntry("table.ifx", 55);
  const bad13 = new Uint8Array(13).fill(7);
  const dropped = syxEnc(bad13).slice(0, 8);           // the reference encoder loses the last block
  const dryRows = [
    ["channel", [{ msg: writeRamAddress((ch + 1) % 16, slot.ram, 4), expect: { kind: "ack" }, role: "write", target: { addr: slot.ram, length: 4 } }]],
    ["write-without-header", [{ msg: writeRamData(ch, new Uint8Array(4)), expect: { kind: "ack" }, role: "write", target: { addr: slot.ram, length: 4 } }]],
    ["short-write", [
      { msg: writeRamAddress(ch, slot.ram, 13), expect: { kind: "ack" }, role: "write", target: { addr: slot.ram, length: 13 } },
      { msg: frame([...head(ch), 0x54, ...dropped]), expect: { kind: "ack" }, role: "write", target: { addr: slot.ram, length: 13 } },
    ]],
    ["execute", [{ msg: frame([...head(ch), 0x57, ...syxEnc(u32le(slot.ram))]), expect: { kind: "ack" }, role: "query" }]],
  ];
  for (const [code, steps] of dryRows) {
    const res = await admit({ kind: "raw" }, steps, session.context());
    // Without the dry run: hand the same messages to the device directly.
    const n = sim.faults.length;
    for (const s of steps) access.outputs.get("sim-out").send(s.msg);
    const without = faultsSince(n).includes(code);
    rows.push({ row: code, stage: "Probelauf", without, caught: res.verdict === "blocked" && res.reasons.some(r => r.code === code) });
  }
  // Last: once hung, the simulated device answers nothing more, like the real one. The protected-region
  // check refuses a flash read from 0x1000000 on before the dry run would see it.
  const hang = [{ msg: frame([...head(ch), 0x55, ...syxEnc([...u32le(0x1000000), ...u32le(16)])]), expect: { kind: "read", length: 16 }, role: "query" }];
  const res = await admit({ kind: "raw" }, hang, session.context());
  const n = sim.faults.length;
  access.outputs.get("sim-out").send(hang[0].msg);
  rows.push({ row: "hang", stage: "Türsteher", without: faultsSince(n).includes("hang"), caught: res.verdict === "blocked" && res.reasons[0].code === "region" });
  return rows;
}
