# SPDX-License-Identifier: GPL-2.0-only
"""Static check of the DSP stream of a patched copy (tools/patch/stage2_memory.py,
docs/messungen/2026-11-13-stufe2-speicher.md). The emulator stubs the DSP upload, so the DSP program never runs in a boot;
check.py takes the stream as it is in the original, or with exactly the changes of the stage 2 memory patch.

    tools/emu/.venv/bin/python tools/emu/stage2_memory_check.py --base ORIGINAL.VSB --patched PATCHED.VSB
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))

import stage2_memory as spec  # noqa: E402


def dsp_stream(base, patched, span):
    """(ok, detail) for the DSP stream in `span` (file offsets): unchanged, or changed in exactly the patch's instructions."""
    if base[span] == patched[span]:
        return True, "der DSP-Strom des Firmware-Builds ist unverändert"
    found = spec.sites(base)
    if found is None:
        return False, "der DSP-Strom ist geändert, und dieser Build trägt nicht das DSP-Programm von stage2-memory"
    expected = bytearray(base)
    for at, _, new, _ in found:
        expected[at:at + len(new)] = new
    if bytes(expected[span]) != patched[span]:
        return False, "der DSP-Strom ist anders geändert als durch stage2-memory"
    return True, "der DSP-Strom trägt genau die Änderungen von stage2-memory (Speicher für Stufe 2, kürzerer Heap 1), sonst unverändert"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--patched", required=True, type=Path)
    a = p.parse_args()
    from check import DSP_STREAM, SYNTH_DSP_STREAM, HEADER, is_synth
    base, patched = a.base.read_bytes(), a.patched.read_bytes()
    ok, detail = dsp_stream(base, patched, SYNTH_DSP_STREAM if is_synth(base[HEADER:]) else DSP_STREAM)
    print(json.dumps({"id": "dsp_stream", "ok": ok, "detail": detail}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
