"""Find the place of the blue Electribe 2's firmware that corresponds to a place of the Sampler's, when fwmap.py has none.

fwmap.py only knows code that is word for word the same. Where the synth's code was changed a little (another constant, a call
more, a window number), this compares the instructions around the Sampler's address with every position of a search range of the
synth image and lists the best matches with both listings side by side. The answer is a candidate, to be read and confirmed:
the evidence for an entry in data/synth-map/ is that listing, not the ratio.

    python3 tools/patch/synthfind.py --ref SAMPLER.VSB --vsb SYNTH.VSB 0xC002837C [--before 4] [--after 24] [--range 0xC0023000:0xC0027000] [--top 5]

Without --range the range is the stretch of the synth image between the two runs of equal code that surround the address
(fwmap.py). Needs the python module capstone (pip install capstone).
"""

import argparse
import bisect
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fwmap  # noqa: E402

BASE = 0xC0000000


def disassembler():
    try:
        import capstone
    except ImportError:
        raise SystemExit("this tool needs capstone: pip install capstone") from None
    return capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)


def listing(md, image, address, count):
    start = address - BASE
    return list(md.disasm(image[start:start + 4 * count], address))


def token(ins):
    """The mnemonic and the registers of an instruction, without constants and without addresses."""
    ops = re.sub(r"#?-?0x[0-9a-f]+|#-?\d+", "#", ins.op_str)
    return f"{ins.mnemonic} {ops}"


def search(md, ref, tgt, address, lo, hi, before=3, after=17, top=3):
    """[(ratio, synth address of `address`)] best first: the instructions around the Sampler address against every position of lo..hi."""
    want = listing(md, ref, address - 4 * before, before + after)
    if len(want) < before + after:
        return []
    tokens = [token(i) for i in want]
    first = tokens[min(before, len(tokens) - 1)].split(" ")[0]
    best = []
    for at in range(lo, hi - 4 * len(want), 4):
        got = listing(md, tgt, at, len(want))
        if len(got) < len(want) or got[min(before, len(got) - 1)].mnemonic != first.split(" ")[0]:
            continue
        ratio = difflib.SequenceMatcher(None, tokens, [token(i) for i in got], autojunk=False).ratio()
        best.append((ratio, at + 4 * before))
    best.sort(reverse=True)
    picked = []
    for ratio, at in best:                      # a position next to a better one is the same place seen from a word away
        if all(abs(at - other) > 16 for _, other in picked):
            picked.append((ratio, at))
    return picked[:top]


def surrounding(fm, address):
    w = (address - BASE) // 4
    i = bisect.bisect_right(fm._starts, w)
    low = fm.runs[i - 1] if i else None
    high = fm.runs[i] if i < len(fm.runs) else None
    start = BASE + (low[1] + low[2]) * 4 if low else BASE
    end = BASE + high[1] * 4 if high else BASE + fm.PAYLOAD if hasattr(fm, "PAYLOAD") else BASE + 0x200000
    return start, end


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ref", required=True, type=Path)
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--before", type=int, default=4, help="instructions before the address that take part in the comparison")
    p.add_argument("--after", type=int, default=24, help="instructions from the address on")
    p.add_argument("--range", help="START:END in the synth image (default: between the neighbouring runs)")
    p.add_argument("--top", type=int, default=4)
    p.add_argument("address")
    a = p.parse_args()
    ref, tgt = fwmap.load(a.ref), fwmap.load(a.vsb)
    fm = fwmap.FirmwareMap(ref, tgt)
    md = disassembler()
    address = int(a.address, 0)
    lo, hi = (int(x, 0) for x in a.range.split(":")) if a.range else surrounding(fm, address)
    want = listing(md, ref, address - 4 * a.before, a.before + a.after)
    tokens = [token(i) for i in want]
    print(f"Sampler {address:#x}; searching the synth image in {lo:#x}..{hi:#x}")
    best = []
    for at in range(lo, hi - 4 * len(want), 4):
        got = listing(md, tgt, at, len(want))
        if len(got) < len(want):
            continue
        ratio = difflib.SequenceMatcher(None, tokens, [token(i) for i in got], autojunk=False).ratio()
        best.append((ratio, at))
    best.sort(reverse=True)
    for ratio, at in best[:a.top]:
        print(f"\n--- candidate for {address:#x}: {at + 4 * a.before:#x}  ratio {ratio:.2f}")
        got = listing(md, tgt, at, len(want))
        for x, y in zip(want, got):
            print(f"  {x.address:#x} {x.mnemonic:8} {x.op_str:28} | {y.address:#x} {y.mnemonic:8} {y.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
