import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { emuPython } from './support/emu.mjs';

test('MMU candidates require an explicit alias and never imply free RAM', () => {
  const result = spawnSync(emuPython(), ['-m', 'unittest', 'discover', '-s', 'tools/device', '-p', 'test_sample_ram_mmu.py'], {
    encoding: 'utf8', timeout: 30000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('the MMU diagnostic defaults to a plan without device access', () => {
  const result = spawnSync(emuPython(), ['tools/device/sample_ram_mmu.py'], { encoding: 'utf8', timeout: 30000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const plan = JSON.parse(result.stdout);
  assert.equal(plan.hardware_contact, false);
  assert.equal(plan.configuration_writes, false);
  assert.equal(plan.automatic_table_read, false);
});
