import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { emuPython } from './support/emu.mjs';

test('bounded sample DSP transport executes success, contention and failure cases in ARM', () => {
  const result = spawnSync(emuPython(), ['-m', 'unittest', 'test_sample_swap_io'], {
    cwd: fileURLToPath(new URL('../tools/patch/', import.meta.url)),
    encoding: 'utf8', timeout: 60000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('generated DSP transport composes through applyPatches without self-overlap', async () => {
  const { makeFirmware } = await import('./helpers.mjs');
  const { applyPatches } = await import('../src/patch.mjs');
  const { sha256 } = await import('../src/firmware.mjs');
  const vsb = await makeFirmware();
  vsb.fill(0xff, 0x19e100, 0x19e900);
  vsb.fill(0xff, 0x19f0f0, 0x19f0f4);
  const generate = [
    'import json, sys',
    'from unittest.mock import patch',
    'import sample_swap_io as io',
    "with patch.object(io, 'validate_firmware', return_value='hacktribe'):",
    '    print(json.dumps(io.build_patch(sys.stdin.buffer.read())))',
  ].join('\n');
  const result = spawnSync(emuPython(), ['-c', generate], {
    cwd: fileURLToPath(new URL('../tools/patch/', import.meta.url)),
    input: Buffer.from(vsb), encoding: 'utf8', timeout: 60000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const transport = JSON.parse(result.stdout);
  const companion = {
    format: 'gelumpe-patch', version: 1, id: 'companion', builds: ['hacktribe'],
    changes: [{ file: 0x19d100, bytes: '01020304', expect: await sha256(vsb.subarray(0x19d100, 0x19d104)) }],
    ram: [],
  };
  const applied = await applyPatches(vsb, [companion, transport]);
  assert.equal(applied.ok, true, applied.reasons.join('\n'));
  const tailWriter = {
    ...companion, id: 'reserved-tail-writer',
    changes: [{ file: 0x19e8fc, bytes: '01020304', expect: await sha256(vsb.subarray(0x19e8fc, 0x19e900)) }],
  };
  const refused = await applyPatches(vsb, [transport, tailWriter]);
  assert.equal(refused.ok, false, 'the unused transport code budget remains reserved');
  assert.match(refused.reasons.join('\n'), /overlaps/);
  for (const change of transport.changes) {
    assert.deepEqual(applied.bytes.subarray(change.file, change.file + change.bytes.length / 2), Uint8Array.from(Buffer.from(change.bytes, 'hex')));
  }
});
