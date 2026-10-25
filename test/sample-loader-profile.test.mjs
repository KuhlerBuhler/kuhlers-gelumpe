import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const dir = fileURLToPath(new URL('../tools/device/', import.meta.url));
const venv = fileURLToPath(new URL(process.platform === 'win32' ? '../tools/emu/.venv/Scripts/python.exe' : '../tools/emu/.venv/bin/python', import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : 'python3');
const available = spawnSync(python, ['--version'], { encoding: 'utf8' });

test('sample loader counters relocate code and preserve PCM and calling convention', { skip: available.error ? 'Python unavailable' : false }, () => {
  const result = spawnSync(python, ['-m', 'unittest', 'discover', '-s', dir, '-p', 'test_sample_loader_profile.py'], { encoding: 'utf8', timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('sample seek checkpoints stay local to a read-only parser frame', { skip: available.error ? 'Python unavailable' : false }, () => {
  const patchDir = fileURLToPath(new URL('../tools/patch/', import.meta.url));
  const result = spawnSync(python, ['-m', 'unittest', 'discover', '-s', patchDir, '-p', 'test_sample_seek.py'], { encoding: 'utf8', timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
