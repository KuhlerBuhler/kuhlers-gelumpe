import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const dir = fileURLToPath(new URL('../tools/device/', import.meta.url));
const venv = fileURLToPath(new URL(process.platform === 'win32' ? '../tools/emu/.venv/Scripts/python.exe' : '../tools/emu/.venv/bin/python', import.meta.url));
const python = process.env.E2_EMU_PYTHON || (existsSync(venv) ? venv : 'python3');
const available = spawnSync(python, ['--version'], { encoding: 'utf8' });

test('hot_patch sorts, groups, orders, journals and reverts a hot patch', { skip: available.error ? 'Python unavailable' : false }, () => {
  const result = spawnSync(python, ['-m', 'unittest', 'discover', '-s', dir, '-p', 'test_hot_patch.py'], { encoding: 'utf8', timeout: 60_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
