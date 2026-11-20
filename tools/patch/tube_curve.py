"""Builds the tube curve patch: a DSP routine that runs the tube curve of tools/dsp/tube_model.py in place of Korg's soft
clipper on the master output, red (Hacktribe and Korg's 2.02) and blue (docs/messungen/2026-11-20-roehrenkurve.md).

Korg's clipper (red 0xFFA0135C, blue 0xFFA01348) takes no parameters. The frame code calls it once per sample through
a fixed address, P0.L = <clipper>; CALL (P0), with R0 pointing at the stereo pair. The patch changes that immediate to
a routine in two functions of the DSP program nothing calls, a head and a tail (red 0xFFA02186 and 0xFFA0A974, blue
0xFFA020F6 and 0xFFA0A75C: no call, jump, constant or data word in the program points there, and an exception planted
at their first instruction never fired in the QEMU DSP core over boot and play). The routine reads the 12-word block at
0xFF803FD0 (tube_model.py), the end of L1 data bank A, which no DSP code touches: with the word on = 0 it jumps to
Korg's clipper, so TUBE OFF is Korg's output bit for bit; else it runs the curve and the lowpass on both channels in
place. The boot stream's last zero fill of bank A stops short of the block (red at 0xFF803FD0, blue at 0xFF803F5C), so
the patch makes it reach the end of the bank: the block and the lowpass state start on zeros, OFF, whatever the RAM
held at power on.

The ARM writes the 10 words from 0xFF803FD8 over the host port (script_menu.s, tube_tick).

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

# build: DSP boot stream (ARM address, length), clipper, the caller's P0.L instruction, the routine's two places
TARGETS = {
    "red": dict(stream=(0xC00F9E10, 0x422A0), clipper=0xFFA0135C, caller=0xFFA01746, at=0xFFA02186, tail=0xFFA0A974,
                fill=(0xFF803DF4, 0x1DC), builds=["hacktribe", "stock"], id="tube-curve"),
    "blue": dict(stream=(0xC00DFB80, 0x41C74), clipper=0xFFA01348, caller=0xFFA01738, at=0xFFA020F6, tail=0xFFA0A75C,
                 fill=(0xFF803D80, 0x1DC), builds=["synth"], id="tube-curve-synth"),
}
BANK_A_END = 0xFF804000
ROOM = 130                              # bytes up to the next function at `at`, both builds
TAIL_ROOM = 56                          # bytes up to the next function at `tail`, both builds
P1_BLOCK = ("09e1" + (tube_model.BLOCK & 0xFFFF).to_bytes(2, "little").hex(),
            "49e1" + (tube_model.BLOCK >> 16).to_bytes(2, "little").hex())

# (instruction, encoding); branches are filled in by routine(). P1 = the block (tube_model.py), P5 = the channel's
# lowpass state, P0 = the sample, R7 = channels left.
BODY = [
    ("P1.L = 0x3fd0", P1_BLOCK[0]),
    ("P1.H = 0xff80", P1_BLOCK[1]),
    ("R1 = [P1 + 0x2c]  (on)", "c9a2"),
    ("CC = R1 == 0x0", "010c"),
    ("IF !CC JUMP go", "brcc:go"),
    ("JUMP.L clipper", "jumpl:clipper"),
    ("go: P0 = R0", "0032"),
    ("[--SP] = (R7:4, P5:5)", "e505"),
    ("P5 = P1  (lowpass state)", "6932"),
    ("R5 = [P1 + 0x14]  (s)", "4da1"),
    ("R7 = 0x2 (X)  (channels)", "1760"),
    ("loop: R0 = [P0]", "0091"),
    ("R3 = [P1 + 0x8]  (gp)", "8ba0"),
    ("R4 = [P1 + 0x10]  (g)", "0ca1"),
    ("CC = R0 < 0x0", "800c"),
    ("IF !CC R4 = R3  (the positive half: gp)", "2306"),
    ("A1 = R4.H * R0.L (M), A0 = R4.H * R0.H", "10c02086"),
    ("A1 = A1 >>> 0xf", "83c68811"),
    ("R0 = (A0 += A1)", "0bc43f00"),
    ("R0 = ASHIFT R0 BY R5.L (S)  (v)", "02c62840"),
    ("R2 = R0.H * R0.H  (w)", "08c28026"),
    ("R6 = [P1 + 0x1c]  (q7)", "cea1"),
    ("R6 = R6.H * R2.H", "08c2b227"),
    ("R3 = [P1 + 0x20]  (q5)", "0ba2"),
    ("R6 = R6 + R3 (S)", "04c4332c"),
    ("R6 = R6.H * R2.H", "08c2b227"),
    ("R3 = [P1 + 0x24]  (q3)", "4ba2"),
    ("R6 = R6 + R3 (S)", "04c4332c"),
    ("R6 = R6.H * R2.H", "08c2b227"),
    ("R3 = [P1 + 0x28]  (q1)", "8ba2"),
    ("R6 = R6 + R3 (S)", "04c4332c"),
    ("A1 = R6.H * R0.L (M), A0 = R6.H * R0.H", "10c03086"),
    ("A1 = A1 >>> 0xf", "83c68811"),
    ("R0 = (A0 += A1)", "0bc43f00"),
    ("R3 = [P1 + 0x18]  (e)", "8ba1"),
    ("R0 = ASHIFT R0 BY R3.L (S)  (t)", "02c61840"),
    ("JUMP.L tail", "jumpl:tail"),
]
TAIL = [
    ("tail: R1 = [P5]  (y)", "2991"),
    ("R0 = R0 - R1 (S)", "04c40160"),
    ("R3 = [P1 + 0xc]  (a)", "cba0"),
    ("A1 = R3.H * R0.L (M), A0 = R3.H * R0.H", "10c01886"),
    ("A1 = A1 >>> 0xf", "83c68811"),
    ("R0 = (A0 += A1)", "0bc43f00"),
    ("R0 = R0 + R1 (S)", "04c40120"),
    ("[P5++] = R0", "2892"),
    ("[P0++] = R0", "0092"),
    ("R7 += -0x1", "ff67"),
    ("CC = R7 == 0x0", "070c"),
    ("IF CC JUMP done", "brcs:done"),
    ("JUMP.L loop", "jumpl:loop"),
    ("done: (R7:4, P5:5) = [SP++]", "a505"),
    ("RTS", "1000"),
]


def _size(enc):
    return 2 if enc[:4] in ("brcc", "brcs") else 4 if enc.startswith("jumpl") else len(enc) // 2


def _encode(places, labels):
    out = []
    for at, body in places:
        code, pc = bytearray(), at
        for _, enc in body:
            if enc[:5] in ("brcc:", "brcs:"):
                off = (labels[enc[5:]] - pc) // 2
                assert -512 <= off < 512
                code += ((0x1800 if enc.startswith("brcs") else 0x1000) | off & 0x3FF).to_bytes(2, "little")
            elif enc.startswith("jumpl:"):
                off = (labels[enc[6:]] - pc) // 2 & 0xFFFFFF
                code += (0xE200 | off >> 16).to_bytes(2, "little") + (off & 0xFFFF).to_bytes(2, "little")
            else:
                code += bytes.fromhex(enc)
            pc += _size(enc)
        out.append(bytes(code))
    return out


def routine(at, clipper, tail):
    """Bytes of the routine: (at `at`, at `tail`)."""
    places = [(at, BODY), (tail, TAIL)]
    labels = {"clipper": clipper}
    for start, body in places:
        pc = start
        for text, enc in body:
            if ":" in text.split()[0]:
                labels[text.split(":")[0]] = pc
            pc += _size(enc)
    head, rest = _encode(places, labels)
    assert len(head) <= ROOM and len(rest) <= TAIL_ROOM, (len(head), len(rest))
    return head, rest


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
    code, tail = routine(t["at"], t["clipper"], t["tail"])
    call, place, clip, rest = (offset(vsb, t["stream"], a) for a in (t["caller"], t["at"], t["clipper"], t["tail"]))
    if None in (call, place, clip, rest) or vsb[call:call + 4] != caller_bytes(t["clipper"]):
        return None
    if vsb[clip:clip + 4] != bytes.fromhex("00326005"):       # P0 = R0; [--SP] = (R7:4)
        return None
    old_code, old_tail = vsb[place:place + len(code)], vsb[rest:rest + len(tail)]
    if offset(vsb, t["stream"], t["at"] + ROOM - 1) != place + ROOM - 1:
        return None
    if offset(vsb, t["stream"], t["tail"] + TAIL_ROOM - 1) != rest + TAIL_ROOM - 1:
        return None
    fill = zero_fill(vsb, t["stream"], t["fill"])
    if fill is None:
        return None
    assert sum(t["fill"]) <= tube_model.BLOCK and tube_model.BLOCK + tube_model.BLOCK_SIZE == BANK_A_END
    return [
        {"file": call, "bytes": caller_bytes(t["at"]).hex(), "expect": sha(vsb[call:call + 4]),
         "note": f"DSP {t['caller']:#010x}: P0.L = {t['at'] & 0xFFFF:#06x}, the master output calls the tube routine "
                 f"(was {t['clipper'] & 0xFFFF:#06x}, Korg's clipper)"},
        {"file": place, "bytes": code.hex(), "expect": sha(old_code),
         "note": f"DSP {t['at']:#010x}: tube routine, block at {tube_model.BLOCK:#010x}, "
                 f"on = 0 jumps to Korg's clipper"},
        {"file": rest, "bytes": tail.hex(), "expect": sha(old_tail),
         "note": f"DSP {t['tail']:#010x}: tube routine, the lowpass and the loop's end"},
        {"file": fill[0], "bytes": fill[2].hex(), "expect": sha(fill[1]),
         "note": f"DSP boot block: zero fill {t['fill'][0]:#x} up to {BANK_A_END:#x} (was {sum(t['fill']):#x}), "
                 f"the block starts on zeros"},
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
