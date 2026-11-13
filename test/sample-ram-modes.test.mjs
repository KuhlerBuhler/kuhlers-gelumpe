import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { emuPython } from './support/emu.mjs';

test('mode observation needs completed actions, valid files and actual capture discard', () => {
  const result = spawnSync(emuPython(), ['-m', 'unittest', 'discover', '-s', 'tools/emu', '-p', 'test_sample_ram_modes.py'], {
    encoding: 'utf8', timeout: 30000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
