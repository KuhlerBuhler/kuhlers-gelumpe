#!/usr/bin/env python3
"""Makes the fixtures of test/bzip2.test.mjs, test/bsdiff.test.mjs and the patcher tests.

    pip install bsdiff4 && python3 test/fixtures/bsdiff/make.py

Everything is made-up data from a tiny generator (xorshift32); no Korg or Hacktribe bytes. The
bzip2 streams come from Python's bz2, the patch from the bsdiff4 package, the same tools that
make Hacktribe's patch, so the JS decoder is held against the real writers. The JS tests build the
same inputs with the same generator and compare checksums from expected.json.
"""
import bz2
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import bsdiff4

here = Path(__file__).parent
SIZE = 0x200100            # a VSB, so the patcher's size check is the real one
NOISE_AT, BYTE_AT = 0x1F0000, 0x1F8000      # where the stand-in original differs (data.mjs has the same)


def noise(n, seed, alphabet=256):
    out, x = bytearray(n), seed
    for i in range(n):
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        out[i] = (x >> 8) % alphabet
    return bytes(out)


def runs():
    out = bytearray()
    for n in list(range(1, 40)) + [254, 255, 256, 259, 260, 300, 1000]:
        out += bytes([n & 0xFF]) * n
        out += bytes([(n * 7) & 0xFF])
    return bytes(out)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def edited(old):
    new = bytearray(old)
    new[100_000:100_064] = noise(64, 3)                    # replaced bytes
    new[400_000:400_003] = b"\x01\x02\x03"                 # a few
    new[900_000:905_000] = old[1_500_000:1_505_000]        # a block moved: needs a seek
    new[2_000_000:2_000_010] = noise(10, 9)
    return bytes(new)


def main():
    expected = {"bzip2": {}}
    cases = {
        "empty": (b"", 9),
        "one": (b"a", 9),
        "runs": (runs(), 9),
        "small-alphabet-3-blocks": (noise(250_000, 7, 5), 1),
        "noise-level-9": (noise(70_000, 11), 9),
        "zeros-2mib": (bytes(2 * 1024 * 1024), 9),
    }
    (here / "bzip2").mkdir(exist_ok=True)
    for name, (data, level) in cases.items():
        (here / "bzip2" / f"{name}.bz2").write_bytes(bz2.compress(data, level))
        expected["bzip2"][name] = {"length": len(data), "sha256": sha(data)}

    old = noise(SIZE, 1)
    new = edited(old)
    patch = bsdiff4.diff(old, new)
    assert bsdiff4.patch(old, patch) == new
    (here / "patch").mkdir(exist_ok=True)
    (here / "patch" / "edit.patch").write_bytes(patch)

    # A stand-in for Korg's original that differs from the made-up Hacktribe firmware (makeFirmware in
    # test/helpers.mjs) in a few bytes, and the patch between them: the page test runs the conversion with it. Needs node.
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "fw.bin"
        subprocess.run(["node", str(here / "dump-firmware.mjs"), str(target)], check=True)
        fw = target.read_bytes()
    original = bytearray(fw)
    original[NOISE_AT:NOISE_AT + 64] = noise(64, 5)
    original[BYTE_AT] = 0x77
    original = bytes(original)
    expected["fake"] = {"original": sha(original), "hacktribe": sha(fw)}
    (here / "patch" / "fake-original-to-hacktribe.patch").write_bytes(bsdiff4.diff(original, fw))
    expected["patch"] = {"old": sha(old), "new": sha(new), "size": SIZE, "patchBytes": len(patch)}
    (here / "expected.json").write_text(json.dumps(expected, indent=1) + "\n")
    print(json.dumps(expected, indent=1))


main()
