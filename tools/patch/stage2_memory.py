"""Builds the stage 2 memory patch: five instructions, the heap 1 length and one boot block of the DSP program of the red builds (Hacktribe and Korg's 2.02),
docs/messungen/2026-11-13-stufe2-speicher.md.

An insert effect has two stages, each one an effect unit of the DSP. At start the DSP fills one argument block per part
and stage (loop at 0x01F0C140, arguments at 0xFF902B7C + 0x50 * part): the unit's state, its coefficients and its delay
memory in the SDRAM. Unpatched, stage 2 gets coefficients 0x50 bytes behind those of stage 1, state 0x50 bytes behind the
state of stage 1, and delay memory at SDRAM address 0. Units use up to 0xA0 bytes of coefficients and 0x84 bytes of
state (measured in the DSP simulator, every unit in both stages), so most pairs write into each other, into the part's
mixer words or, with a delay line in stage 2, into the DSP program.

Patched:

    stage 2 state          0xFF906320 + 0x118 * part
    stage 2 coefficients   0xFF9074D4 + 0xB4 * part, up to the end of L1 data bank B (0xFF908000); stage 1 keeps
                           the part's whole 0xA0 bytes
    stage 2 delay memory   the part's SDRAM buffer
    heap 1                 0xFF904600 + 0x1D20 instead of 0x39FF bytes, so it ends where stage 2 starts
    zero fill at boot      0xFF900CD0 up to 0xFF908000 instead of 0xFF903FF0, so stage 2 starts on zeros

Unit 0x15 keeps a pointer to the word 0xC8 below its coefficients (in stage 1 the part block + 8), reads it every frame
and writes the same value back. The 0xB4 stride and the 0x34 bytes between the state and the coefficients make that
word, for every part, one no stage 2 unit uses: 0x14 bytes behind the coefficients two parts down, the gap, or the
unused end of part 15's state (units use up to 0x84 bytes of it).

Bank B from 0xFF904600 is the DSP's heap 1 (heap table at 0x01F02440: base, length, id); the RTOS takes its task stacks
and control blocks from it. Read on the device in idle, the heap is used up to 0xFF9054E0 (0xEC0 bytes); the shorter
heap leaves it 0x1D20. The simulator harness skips the RTOS start, so it never shows the heap.

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
STATE2, COEF2 = 0xFF906320, 0xFF9074D4
COEF2_STRIDE, STATE_STRIDE, PARTS, COEF_USED, STATE_USED = 0xB4, 0x118, 16, 0xA0, 0x84
COEF_BACK = 0xC8                        # unit 0x15 reads and rewrites the word this far below its coefficients
TAKEN = (STATE2, COEF2 + COEF2_STRIDE * (PARTS - 1) + COEF_USED)
HEAP1, HEAP1_LEN = 0xFF904600, 0x39FF          # heap table entry at 0x01F02444: base, length, id 1
HEAP1_NEW = STATE2 - HEAP1
FILL_AT, FILL_WAS, BANK_B_END = 0xFF900CD0, 0x3320, 0xFF908000   # the boot stream's zero fill of bank B

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
     "R4 = 0xB4, stage 2 coefficient stride (was 0x1B4, the part block)"),
    (0x01F02448, HEAP1_LEN.to_bytes(4, "little").hex(), HEAP1_NEW.to_bytes(4, "little").hex(),
     "heap 1 length, the heap ends where stage 2 starts (was 0x39FF, the rest of bank B)"),
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
    fill = zero_fill(vsb)
    if fill is None:
        return None
    return out + [fill]


def zero_fill(vsb):
    """The header of the boot stream's zero fill of bank B, made to reach the end of the bank: (file offset, before, after,
    note), or None when the stream has no such block. Bank B above the heap is never written otherwise, so stage 2 would
    start on whatever the RAM held at power on (read on the device: random bytes from 0xFF9054E0 up)."""
    try:
        blocks = list(dsp_extract.parse(vsb))
    except ValueError:
        return None
    for _, pos, flags, target, count, arg, _ in blocks:
        if flags & dsp_extract.F_FILL and target == FILL_AT and count == FILL_WAS and arg == 0:
            old = bytes(vsb[pos:pos + 16])
            new = bytearray(old)
            new[8:12] = (BANK_B_END - FILL_AT).to_bytes(4, "little")
            new[2] = 0
            for i, byte in enumerate(new):
                if i != 2:
                    new[2] ^= byte
            return pos, old, bytes(new), f"DSP boot block: zero fill {FILL_AT:#x} up to {BANK_B_END:#x} (was {FILL_AT + FILL_WAS:#x})"
    return None


def free_word(addr):
    """True when addr is in no part's used stage 2 state or coefficients, and inside the stage 2 area."""
    used = [(STATE2 + STATE_STRIDE * k, STATE_USED) for k in range(PARTS)] + [(COEF2 + COEF2_STRIDE * k, COEF_USED) for k in range(PARTS)]
    return TAKEN[0] <= addr < TAKEN[1] and not any(lo <= addr < lo + n for lo, n in used)


def build_patch(vsb):
    assert STATE2 + STATE_STRIDE * PARTS <= COEF2 and COEF2 - STATE1 < 0x8000 and TAKEN[1] == 0xFF908000
    assert all(free_word(COEF2 + COEF2_STRIDE * k - COEF_BACK) for k in range(PARTS))
    assert dsp_extract.vsb_offset(vsb, 0x01F02444) is not None and vsb[dsp_extract.vsb_offset(vsb, 0x01F02444):][:4] == HEAP1.to_bytes(4, "little")
    for _, _, flags, target, count, _, _ in dsp_extract.parse(vsb):
        if not flags & dsp_extract.F_IGNORE and not flags & dsp_extract.F_FILL and count and target < BANK_B_END and FILL_AT + FILL_WAS < target + count:
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
