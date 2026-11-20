"""Builds the tube curve patch: a DSP routine that runs the tube curve of tools/dsp/tube_model.py in place of Korg's soft
clipper on the master output, red (Hacktribe and Korg's 2.02) and blue (docs/messungen/2026-11-20-roehrenkurve.md).

Korg's clipper (red 0xFFA0135C, blue 0xFFA01348) takes no parameters. The frame code calls it once per sample through
a fixed address, P0.L = <clipper>; CALL (P0), with R0 pointing at the stereo pair. The patch changes that immediate to
a routine in a function of the DSP program nothing calls (red 0xFFA02186, blue 0xFFA020F6: no call, jump, constant or
data word in the program points there, and an exception planted at its first instruction never fired in the QEMU DSP
core over boot and play). The routine reads the parameter block at 0xFF803FE0, the end of L1 data bank A, which no
DSP code touches: with the word on = 0 it jumps to Korg's clipper, so TUBE OFF is Korg's output bit for bit; else it
runs the curve on both channels in place. The boot stream's last zero fill of bank A stops short of the block (red at
0xFF803FD0, blue at 0xFF803F5C), so the patch makes it reach the end of the bank: the block starts on zeros, OFF,
whatever the RAM held at power on.

The ARM writes the block over the host port (script_menu.s, tube_*).

    python3 tools/patch/tube_curve.py --vsb SYSTEM.VSB [--out data/patches/tube-curve.json]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dsp"))
import dsp_extract  # noqa: E402
import tube_model  # noqa: E402

# build: DSP boot stream (ARM address, length), clipper, the caller's P0.L instruction, the routine's place
TARGETS = {
    "red": dict(stream=(0xC00F9E10, 0x422A0), clipper=0xFFA0135C, caller=0xFFA01746, at=0xFFA02186,
                fill=(0xFF803DF4, 0x1DC), builds=["hacktribe", "stock"], id="tube-curve"),
    "blue": dict(stream=(0xC00DFB80, 0x41C74), clipper=0xFFA01348, caller=0xFFA01738, at=0xFFA020F6,
                 fill=(0xFF803D80, 0x1DC), builds=["synth"], id="tube-curve-synth"),
}
BANK_A_END = 0xFF804000
ROOM = 130                              # bytes up to the next function at both places
P1_PARAM = ("09e1" + (tube_model.PARAM & 0xFFFF).to_bytes(2, "little").hex(),
            "49e1" + (tube_model.PARAM >> 16).to_bytes(2, "little").hex())

# (instruction, encoding); branches are filled in by routine()
BODY = [
    ("P1.L = 0x3fe0", P1_PARAM[0]),
    ("P1.H = 0xff80", P1_PARAM[1]),
    ("R1 = [P1 + 0x1c]  (on)", "c9a1"),
    ("CC = R1 == 0x0", "010c"),
    ("IF !CC JUMP go", "brcc:go"),
    ("JUMP.L clipper", "jumpl:clipper"),
    ("go: P0 = R0", "0032"),
    ("[--SP] = (R7:4)", "6005"),
    ("R4 = [P1]  (g)", "0c91"),
    ("R5 = [P1 + 0x4]  (s)", "4da0"),
    ("R7 = 0x2 (X)  (channels)", "1760"),
    ("loop: R0 = [P0]", "0091"),
    ("A1 = R4.H * R0.L (M), A0 = R4.H * R0.H", "10c02086"),
    ("A1 = A1 >>> 0xf", "83c68811"),
    ("R0 = (A0 += A1)", "0bc43f00"),
    ("R0 = ASHIFT R0 BY R5.L (S)  (v)", "02c62840"),
    ("R2 = R0.H * R0.H  (w)", "08c28026"),
    ("R6 = [P1 + 0xc]  (q7)", "cea0"),
    ("R6 = R6.H * R2.H", "08c2b227"),
    ("R3 = [P1 + 0x10]  (q5)", "0ba1"),
    ("R6 = R6 + R3 (S)", "04c4332c"),
    ("R6 = R6.H * R2.H", "08c2b227"),
    ("R3 = [P1 + 0x14]  (q3)", "4ba1"),
    ("R6 = R6 + R3 (S)", "04c4332c"),
    ("R6 = R6.H * R2.H", "08c2b227"),
    ("R3 = [P1 + 0x18]  (q1)", "8ba1"),
    ("R6 = R6 + R3 (S)", "04c4332c"),
    ("A1 = R6.H * R0.L (M), A0 = R6.H * R0.H", "10c03086"),
    ("A1 = A1 >>> 0xf", "83c68811"),
    ("R0 = (A0 += A1)", "0bc43f00"),
    ("R3 = [P1 + 0x8]  (e)", "8ba0"),
    ("R0 = ASHIFT R0 BY R3.L (S)", "02c61840"),
    ("[P0++] = R0", "0092"),
    ("R7 += -0x1", "ff67"),
    ("CC = R7 == 0x0", "070c"),
    ("IF !CC JUMP loop", "brcc:loop"),
    ("(R7:4) = [SP++]", "2005"),
    ("RTS", "1000"),
]


def routine(at, clipper):
    """Bytes of the routine at DSP address `at`."""
    sizes = [2 if enc.startswith("brcc") else 4 if enc.startswith("jumpl") else len(enc) // 2 for _, enc in BODY]
    labels, pc = {"clipper": clipper}, at
    for (text, _), size in zip(BODY, sizes):
        if ":" in text.split()[0]:
            labels[text.split(":")[0]] = pc
        pc += size
    out, pc = bytearray(), at
    for (_, enc), size in zip(BODY, sizes):
        if enc.startswith("brcc:"):
            off = (labels[enc[5:]] - pc) // 2
            assert -512 <= off < 512
            out += (0x1000 | off & 0x3FF).to_bytes(2, "little")
        elif enc.startswith("jumpl:"):
            off = (labels[enc[6:]] - pc) // 2 & 0xFFFFFF
            out += (0xE200 | off >> 16).to_bytes(2, "little") + (off & 0xFFFF).to_bytes(2, "little")
        else:
            out += bytes.fromhex(enc)
        pc += size
    assert len(out) <= ROOM
    return bytes(out)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def offset(vsb, stream, addr):
    """File offset of the payload byte loaded at DSP address addr, or None (later blocks win, as on the DSP)."""
    found = None
    try:
        for _, pos, flags, target, count, _, payload in dsp_extract.parse(vsb, *stream):
            if payload and not flags & dsp_extract.F_IGNORE and target <= addr < target + count:
                found = pos + 16 + addr - target
    except ValueError:
        return None
    return found


def caller_bytes(clipper):
    return bytes.fromhex("08e1") + (clipper & 0xFFFF).to_bytes(2, "little")


def zero_fill(vsb, stream, fill):
    """The header of the zero fill `fill` = (target, count), made to reach the end of bank A: (file offset, before, after),
    or None when the stream has no such block."""
    try:
        blocks = list(dsp_extract.parse(vsb, *stream))
    except ValueError:
        return None
    for _, pos, flags, target, count, arg, _ in blocks:
        if flags & dsp_extract.F_FILL and (target, count) == fill and arg == 0:
            old = bytes(vsb[pos:pos + 16])
            new = bytearray(old)
            new[8:12] = (BANK_A_END - target).to_bytes(4, "little")
            new[2] = 0
            for i, byte in enumerate(new):
                if i != 2:
                    new[2] ^= byte
            return pos, old, bytes(new)
    return None


def changes(vsb, target):
    """Changes for one target, or None when the VSB does not carry that DSP program."""
    t = TARGETS[target]
    code = routine(t["at"], t["clipper"])
    call, place, clip = (offset(vsb, t["stream"], a) for a in (t["caller"], t["at"], t["clipper"]))
    if None in (call, place, clip) or vsb[call:call + 4] != caller_bytes(t["clipper"]):
        return None
    if vsb[clip:clip + 4] != bytes.fromhex("00326005"):       # P0 = R0; [--SP] = (R7:4)
        return None
    old_code = vsb[place:place + len(code)]
    if offset(vsb, t["stream"], t["at"] + ROOM - 1) != place + ROOM - 1:
        return None
    fill = zero_fill(vsb, t["stream"], t["fill"])
    if fill is None:
        return None
    assert sum(t["fill"]) <= tube_model.PARAM and tube_model.PARAM + tube_model.PARAM_SIZE == BANK_A_END
    return [
        {"file": call, "bytes": caller_bytes(t["at"]).hex(), "expect": sha(vsb[call:call + 4]),
         "note": f"DSP {t['caller']:#010x}: P0.L = {t['at'] & 0xFFFF:#06x}, the master output calls the tube routine "
                 f"(was {t['clipper'] & 0xFFFF:#06x}, Korg's clipper)"},
        {"file": place, "bytes": code.hex(), "expect": sha(old_code),
         "note": f"DSP {t['at']:#010x}: tube routine, parameters at {tube_model.PARAM:#010x}, "
                 f"on = 0 jumps to Korg's clipper"},
        {"file": fill[0], "bytes": fill[2].hex(), "expect": sha(fill[1]),
         "note": f"DSP boot block: zero fill {t['fill'][0]:#x} up to {BANK_A_END:#x} (was {sum(t['fill']):#x}), "
                 f"the parameter block starts on zeros"},
    ]


def build_patch(vsb):
    for target, t in TARGETS.items():
        found = changes(vsb, target)
        if found:
            return {"format": "gelumpe-patch", "version": 1, "id": t["id"],
                    "name": "Röhrenkurve statt Soft-Clipper am Ausgang (BLECH > FEATURES > TUBE)",
                    "builds": t["builds"], "changes": found, "startPhase": [], "ram": []}
    raise SystemExit("this VSB does not carry a DSP program the patch knows")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    patch = build_patch(a.vsb.read_bytes())
    text = json.dumps(patch, indent=1, ensure_ascii=False) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
