# SPDX-License-Identifier: GPL-2.0-only
"""Static check of the DSP stream of a patched copy (tools/patch/stage2_memory.py,
docs/messungen/2026-11-13-stufe2-speicher.md). The emulator stubs the DSP upload, so the DSP program never runs in a boot;
check.py accepts the original stream or the exact canonical stage-2 and native-recording patches.

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
    """Accept only canonical stage-2 and recording edits, including the extended upload."""
    import recording_dsp_check
    rec = recording_dsp_check.spec
    build = 'synth' if span.start == rec.file_offset(rec.configuration('synth')['stream']) else 'hacktribe'
    config = rec.configuration(build)
    length_at = rec.file_offset(config['length_word'])
    same_length = base[length_at:length_at + 4] == patched[length_at:length_at + 4]
    if base[span] == patched[span] and same_length:
        return True, "der DSP-Strom des Firmware-Builds ist unverändert"
    found = spec.sites(base)
    stage2 = bytearray(base)
    if found:
        for at, _, new, _ in found:
            stage2[at:at + len(new)] = new
        if stage2[span] == patched[span] and same_length:
            return True, "der DSP-Strom trägt genau die Änderungen von stage2-memory"
    try:
        recording = recording_dsp_check.canonical_patch(base, build)
        extended = slice(span.start, rec.file_offset(config['final'] + 16) + rec.PROGRAM_SIZE + 16)
        for candidate in (bytearray(base), stage2):
            for change in recording['changes']:
                data = bytes.fromhex(change['bytes'])
                candidate[change['file']:change['file'] + len(data)] = data
            if candidate[extended] == patched[extended] and candidate[length_at:length_at + 4] == patched[length_at:length_at + 4]:
                return True, "der DSP-Strom trägt genau den Aufnahme-Abgriff, gegebenenfalls mit stage2-memory; Block und Ladelänge stimmen"
    except (ValueError, KeyError, OSError) as error:
        return False, f"der Aufnahme-DSP-Strom ist nicht kanonisch: {error}"
    return False, "der DSP-Strom oder seine Ladelänge ist anders geändert als durch die geprüften DSP-Patches"


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
