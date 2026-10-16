import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

const python = process.env.E2_EMU_PYTHON || "python3";

test("Doom source inventory rejects stale adapters, changed binaries and altered archives", () => {
  const result = spawnSync(python, ["-c", String.raw`
import io, json, sys, tarfile, tempfile
from pathlib import Path
sys.path.insert(0, 'tools/doom')
from source_package import OWN_SOURCES, source_hashes, digest, add_bytes, validate_build
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / 'repo'
    build = Path(tmp) / 'build'
    build.mkdir()
    for name in OWN_SOURCES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('own-source:' + name)
    binary = b'own test executable'
    (build / 'doom-runtime.bin').write_bytes(binary)
    meta = {'own_source_sha256': source_hashes(root), 'binary_sha256': digest(binary)}
    (build / 'build.json').write_text(json.dumps(meta))
    sources = {'binary_sha256': digest(binary), 'files': {'own.c': digest(b'own test source')}}
    (build / 'sources.json').write_text(json.dumps(sources))
    with tarfile.open(build / 'doom-sources.tar.gz', 'w:gz') as archive:
        add_bytes(archive, 'own.c', b'own test source')
    validate_build(build, root)
    def rejects():
        try:
            validate_build(build, root)
        except ValueError:
            return
        raise AssertionError('changed artifact accepted')
    adapter = root / 'tools/doom/runtime.c'
    old = adapter.read_bytes()
    adapter.write_bytes(old + b'changed')
    rejects()
    adapter.write_bytes(old)
    (build / 'doom-runtime.bin').write_bytes(binary + b'changed')
    rejects()
    (build / 'doom-runtime.bin').write_bytes(binary)
    with tarfile.open(build / 'doom-sources.tar.gz', 'w:gz') as archive:
        add_bytes(archive, 'own.c', b'changed source')
    rejects()
`], { encoding: "utf8", timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("Doom source archive contains every quoted adapter header and a Git-free rebuild entry", () => {
  const result = spawnSync(python, ["-c", String.raw`
import io, re, sys, tarfile
from pathlib import Path
sys.path.insert(0, 'tools/doom')
from source_package import own_sources, add_bytes, validate_local_includes
files = {'gelumpe/' + name: data for name, data in own_sources(Path.cwd()).items()}
for name, data in list(files.items()):
    if name.endswith(('.c', '.h')):
        for include in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"', data.decode(), re.M):
            if str(Path(name).parent / include) not in files:
                assert include in {'doomgeneric.h', 'doomkeys.h', 'doomstat.h', 'm_controls.h', 'd_player.h'}, include
                files['doomgeneric/doomgeneric/' + include] = b'/* synthetic engine header */'
stream = io.BytesIO()
with tarfile.open(fileobj=stream, mode='w') as archive:
    for name, data in files.items():
        add_bytes(archive, name, data)
stream.seek(0)
with tarfile.open(fileobj=stream) as archive:
    packed = {item.name: archive.extractfile(item).read() for item in archive.getmembers()}
validate_local_includes(packed)
assert 'gelumpe/tools/doom/rebuild_runtime.py' in packed
for required in ('native_power.h', 'status_display.h'):
    missing = dict(packed)
    del missing['gelumpe/tools/doom/' + required]
    try:
        validate_local_includes(missing)
    except ValueError:
        continue
    raise AssertionError('missing adapter header accepted: ' + required)
`], { encoding: "utf8", timeout: 30_000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
