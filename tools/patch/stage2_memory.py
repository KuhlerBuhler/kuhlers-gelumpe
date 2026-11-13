"""Builds the stage 2 memory patch: five instructions of the DSP program of the red builds (Hacktribe and Korg's 2.02),
docs/messungen/2026-11-13-stufe2-speicher.md.

An insert effect has two stages, each one an effect unit of the DSP. At start the DSP fills one argument block per part
and stage (loop at 0x01F0C140, arguments at 0xFF902B7C + 0x50 * part): the unit's state, its coefficients and its delay
memory in the SDRAM. Unpatched, stage 2 gets coefficients 0x50 bytes behind those of stage 1, state 0x50 bytes behind the
state of stage 1, and delay memory at SDRAM address 0. Units use up to 0xA0 bytes of coefficients and 0x84 bytes of
state (measured in the DSP simulator, every unit in both stages), so most pairs write into each other, into the part's
mixer words or, with a delay line in stage 2, into the DSP program.

Patched:

    stage 2 coefficients   0xFF904600 + 0xA0 * part; stage 1 keeps the part's whole 0xA0 bytes
    stage 2 state          0xFF905000 + 0x118 * part; stage 1 keeps 0xA0 bytes up to the mixer words
    stage 2 delay memory   the part's SDRAM buffer

0xFF904600..0xFF906180 is L1 data bank B above the DSP's stack (0xFF904000..0xFF9045FF). The DSP sets only bank A's
upper half as cache (DMEM_CONTROL 0x100B), no boot block loads there (build_patch checks it), and the simulator saw no
write there in 400 pairs.

Two limits stay: a unit with a delay line takes the whole buffer (0x2EE00 bytes), so two of them in one insert effect
share it; unit 0x16 reads four tempo resources the DSP sets for stage 1 only. Those pairs stay locked in
data/findings.mjs.

No kill switch: the DSP program is loaded once at start, before the panel can be read.

    python3 tools/patch/stage2_memory.py --vsb SYSTEM.VSB [--out data/patches/stage2-memory.json]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dsp"))
import dsp_extract  # noqa: E402

STATE1 = 0xFF9018AC                     # stage 1 state of part 0, R5 of the loop; the new stage 2 areas are offsets from it
COEF2, STATE2 = 0xFF904600, 0xFF905000
COEF2_STRIDE, STATE_STRIDE, PARTS = 0xA0, 0x118, 16
TAKEN = (COEF2, STATE2 + STATE_STRIDE * PARTS)

# DSP address, instruction before, instruction after, what it does
SITES = (
    (0x01F0C166, "22e15000", "22e1" + (COEF2 - STATE1).to_bytes(2, "little").hex(),
     "R2 = stage 2 coefficients - stage 1 state (was 0x50)"),
    (0x01F0C16A, "23e17000", "23e1" + (STATE2 - STATE1).to_bytes(2, "little").hex(),
     "R3 = stage 2 state - stage 1 state (was 0x70)"),
    (0x01F0C178, "04cc0a04", "04cc2a04",
     "R2 = R5 + R2, stage 2 coefficients from the state base (was R1 + R2, behind stage 1's coefficients)"),
    (0x01F0C1CC, "069e", "009e",
     "[I0++] = R0, stage 2 gets the part's SDRAM buffer (was R6, 0)"),
    (0x01F0C1EC, "24e1b401", "24e1" + COEF2_STRIDE.to_bytes(2, "little").hex(),
     "R4 = 0xA0, stage 2 coefficient stride (was 0x1B4, the part block)"),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sites(vsb):
    """(file offset, before, after, note) per instruction, or None when the VSB does not carry this DSP program."""
    out = []
    for addr, was, now, note in SITES:
        try:
            at = dsp_extract.vsb_offset(vsb, addr)
        except ValueError:
            return None
        old = bytes.fromhex(was)
        if at is None or vsb[at:at + len(old)] != old:
            return None
        out.append((at, old, bytes.fromhex(now), f"DSP {addr:#010x}: {note}"))
    return out


def build_patch(vsb):
    assert COEF2 + COEF2_STRIDE * PARTS <= STATE2 and STATE2 - STATE1 < 0x8000
    for _, _, flags, target, count, _, _ in dsp_extract.parse(vsb):
        if not flags & dsp_extract.F_IGNORE and count and target < TAKEN[1] and TAKEN[0] < target + count:
            raise SystemExit(f"a boot block loads {target:#x}..{target + count:#x}, inside the memory the patch takes")
    found = sites(vsb)
    if found is None:
        raise SystemExit("this VSB does not carry the DSP program the patch expects")
    changes = [{"file": at, "bytes": new.hex(), "expect": sha(old), "note": note} for at, old, new, note in found]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "stage2-memory",
        "name": "Eigener Speicher für Stufe 2 der Insert-Effekte",
        "builds": ["hacktribe", "stock"],
        "changes": changes,
        "startPhase": [],
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw), indent=1, ensure_ascii=False) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
