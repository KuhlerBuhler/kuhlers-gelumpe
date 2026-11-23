import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { emuPython } from './support/emu.mjs';

test('the upper RAM probe excludes stacks, refuses cached memory and stops after an unconfirmed EXEC', () => {
  const result = spawnSync(emuPython(), ['-m', 'unittest', 'discover', '-s', 'tools/device', '-p', 'test_sample_ram_canary.py'], {
    encoding: 'utf8', timeout: 30000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('the RAM probe defaults to an offline plan without opening MIDI', () => {
  const result = spawnSync(emuPython(), ['tools/device/sample_ram_canary.py'], { encoding: 'utf8', timeout: 30000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const plan = JSON.parse(result.stdout);
  assert.equal(plan.hardware_contact, false);
  assert.equal(plan.start, 0xC274F000);
  assert.equal(plan.end, 0xC4000000);
});
