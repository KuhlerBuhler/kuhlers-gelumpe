import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { emuPython } from './support/emu.mjs';

test('physical sample protection covers playback, aliases, native mutations and bounded scans in ARM', () => {
  const result = spawnSync(emuPython(), ['-m', 'unittest', 'test_sample_protection'], {
    cwd: fileURLToPath(new URL('../tools/patch/', import.meta.url)),
    encoding: 'utf8', timeout: 60000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
