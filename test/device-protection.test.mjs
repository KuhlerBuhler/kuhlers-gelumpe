import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DeviceSession, electribePorts } from '../src/session.mjs';
import { installWebMidiStub } from '../src/webmidi.mjs';
import { SimDevice } from '../src/device.mjs';
import { VsbImage } from '../src/image.mjs';
import { plan, MAX_WRITE } from '../src/plan.mjs';
import { Sender } from '../src/sender.mjs';
import { describeMessage, readRam } from '../src/protocol.mjs';
import { field } from '../src/map/index.mjs';
import { fileToRam } from '../src/map/address.mjs';
import DEVICES from '../data/devices.mjs';

const hash = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
const fast = { search: 100, read: 100, ack: 30 };
const mfx = field('menu.mfxCount');
const address = fileToRam(mfx.where.offset);
const image = () => new Uint8Array(0x200100);

async function connected({ mismatch = false, fingerprints = true } = {}) {
  const bytes = image();
  const regions = [{ addr: 0xc0000040, length: 64 }, { addr: 0xc017059c, length: 512 }];
  const profile = { version: [2, 2], fingerprints: fingerprints ? await Promise.all(regions.map(async r => ({ ...r, sha256: await hash(new Uint8Array(r.length)) }))) : [] };
  if (mismatch) bytes[0x140] = 1;
  const nav = {};
  const sim = installWebMidiStub({ image: { bytes }, channel: 9, target: nav });
  const session = new DeviceSession({ port: electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0], known: [profile], timeouts: fast });
  return { device: await session.connect(), session, sim };
}

test('matching measured firmware fingerprints permit the known device', async () => {
  const { device } = await connected();
  assert.equal(device.versionKnown, true);
  assert.equal(device.fingerprintVerified, true);
  assert.equal(device.hacktribe, true);
  assert.equal(MAX_WRITE, 256);
});

test('a matching version with different code remains read-only', async () => {
  const { device } = await connected({ mismatch: true });
  assert.equal(device.versionKnown, false);
});

test('a version profile without fingerprints remains read-only', async () => {
  const { device } = await connected({ fingerprints: false });
  assert.equal(device.versionKnown, false);
});

test('production profile carries measured version, fingerprints and source', () => {
  assert.equal(DEVICES.length, 2);
  assert.deepEqual(DEVICES[0].version, [2, 2]);
  assert.equal(DEVICES[0].fingerprints.length, 2);
  assert.match(DEVICES[0].evidence, /^measure:/);
  assert.equal(DEVICES[1].build, 'stock', 'Korg\'s original with BLECH is the second profile, the first stays Hacktribe\'s');
  assert.equal(DEVICES[1].fingerprints.length, 3);
  assert.match(DEVICES[1].evidence, /^measure:/);
});

function simulatedRun(steps, word) {
  const bytes = image();
  new DataView(bytes.buffer).setUint32(mfx.where.offset, word, true);
  const device = new SimDevice({ image: new VsbImage(bytes), channel: 9 });
  const sent = [];
  const sender = new Sender({ channel: 9, timeouts: fast, send(msg) {
    sent.push(describeMessage(msg));
    const reply = device.handle(msg);
    if (reply) queueMicrotask(() => sender.receive(reply));
  }});
  return { device, sent, result: sender.run(steps) };
}

test('wrong MFX opcode prevents all writes', async () => {
  const run = simulatedRun(plan({ kind: 'sites', fieldId: mfx.id, value: 61 }, { channel: 9 }), 0xe3a01032);
  assert.equal((await run.result).ok, false);
  assert.equal(run.sent.some(s => s.kind === 'write-address'), false);
});

test('MFX immediate changes preserve and verify the complete instruction', async () => {
  const steps = plan({ kind: 'sites', fieldId: mfx.id, value: 62 }, { channel: 9 });
  const run = simulatedRun(steps, 0xe3a0003d);
  assert.equal((await run.result).ok, true);
  assert.deepEqual([...run.device.peek(address, 4)], [62, 0, 160, 227]);
  assert.equal(steps.at(-1).expect.length, 4);
});

test('restoring an MFX menu byte also checks the opcode before writing', async () => {
  const steps = plan({ kind: 'restore', backups: [{ addr: address, bytes: Uint8Array.of(50) }] }, { channel: 9 });
  const run = simulatedRun(steps, 0xe3a01032);
  assert.equal((await run.result).ok, false);
  assert.equal(run.sent.some(s => s.kind === 'write-address'), false);
});

test('RAM error reply is never a successful write acknowledgement', async () => {
  const sender = new Sender({ channel: 9, timeouts: fast, send() {
    queueMicrotask(() => sender.receive([240,66,57,0,1,36,38,247]));
  }});
  const result = await sender.run([{ msg: readRam(9, address, 1), expect: { kind: 'ack' } }]);
  assert.equal(result.ok, false);
});

test('invalid MFX menu counts in RAM prevent all writes', async () => {
  for (const word of [0xe3a00000, 0xe3a00065]) {
    const run = simulatedRun(plan({ kind: 'sites', fieldId: mfx.id, value: 61 }, { channel: 9 }), word);
    assert.equal((await run.result).ok, false);
    assert.equal(run.sent.some(s => s.kind === 'write-address'), false);
  }
});

test('a synchronous transport error clears the pending exchange', async () => {
  const sender = new Sender({ channel: 9, timeouts: fast, send() { throw new Error('send failed'); } });
  const result = await sender.run(plan({ kind: 'readRam', addr: address, length: 4 }, { channel: 9 }));
  assert.equal(result.ok, false);
  assert.equal(sender.waiting, null);
});

test('firmware-file MFX edits also reject a different instruction', async () => {
  const { writeRaw } = await import('../src/map/index.mjs');
  const bytes = image();
  new DataView(bytes.buffer).setUint32(mfx.where.offset, 0xe3a01032, true);
  const before = bytes.slice();
  assert.throws(() => writeRaw(bytes, mfx, [], 61), /Instruktion/);
  assert.deepEqual(bytes, before);
});

test('pattern writes await the measured 0x23 reply before requesting readback', () => {
  const steps = plan({ kind: 'patternRestore', block: new Uint8Array(0x4000) }, { channel: 9 });
  assert.equal(steps[0].expect.kind, 'ack');
  assert.equal(steps[0].expect.func, 0x23);
  assert.equal(steps[0].expect.timeout, 'pattern');
});

test('missing fingerprint reply stops probing and leaves the device read-only', async () => {
  const nav = {};
  const sim = installWebMidiStub({ image: { bytes: image() }, channel: 9, target: nav });
  const port = electribePorts(await nav.requestMIDIAccess({ sysex: true }))[0];
  const sent = [];
  const send = port.out.send;
  port.out.send = msg => {
    const description = describeMessage(msg);
    sent.push(description);
    if (description.kind === 'search') send(msg);
  };
  const profile = { version: [2, 2], fingerprints: [
    { addr: 0xc0000040, length: 64, sha256: await hash(new Uint8Array(64)) },
    { addr: 0xc017059c, length: 512, sha256: await hash(new Uint8Array(512)) },
  ] };
  const session = new DeviceSession({ port, known: [profile], timeouts: fast });
  const result = await session.connect();
  assert.equal(result.versionKnown, false);
  assert.equal(result.fingerprintVerified, false);
  assert.equal(sent.length, 3, "the search, BLECH's INFO that nobody answers, and the first signature");
  assert.equal(sim.device.faults.length, 0);
});
