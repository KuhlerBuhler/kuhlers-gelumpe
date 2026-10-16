"""List a Sampler function and its synth twin side by side, with the literal-pool words each loads.

For finding the synth's address of a RAM variable: the Sampler function that loads the variable and its twin in the synth load their
variables in the same order, so the pairs of loaded words are candidates (to be confirmed by what the code does with them).

    python3 tools/patch/synthtwin.py --ref SAMPLER.VSB --vsb SYNTH.VSB 0xC0081BB4 [0xC0072E10] [--count 40]

Without the second address the twin is taken from data/synth-map/. Needs capstone (pip install capstone).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fwmap  # noqa: E402
import synthaddr  # noqa: E402
from synthfind import disassembler, listing  # noqa: E402

BASE = 0xC0000000


def literals(image, instructions):
    """{index: loaded word} for every `ldr rX, [pc, #n]` among the instructions."""
    out = {}
    for k, ins in enumerate(instructions):
        if ins.mnemonic.startswith("ldr") and "[pc, #" in ins.op_str and ins.op_str.endswith("]"):
            offset = int(ins.op_str.split("#")[1].rstrip("]"), 0)
            at = ins.address + 8 + offset - BASE
            if 0 <= at + 4 <= len(image):
                out[k] = int.from_bytes(image[at:at + 4], "little")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ref", required=True, type=Path)
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--count", type=int, default=48)
    p.add_argument("sampler")
    p.add_argument("synth", nargs="?")
    a = p.parse_args()
    ref, tgt = fwmap.load(a.ref), fwmap.load(a.vsb)
    md = disassembler()
    s_at = int(a.sampler, 0)
    t_at = int(a.synth, 0) if a.synth else synthaddr.tr(s_at)
    want, got = listing(md, ref, s_at, a.count), listing(md, tgt, t_at, a.count)
    lit_s, lit_t = literals(ref, want), literals(tgt, got)
    print(f"Sampler {s_at:#x}  |  synth {t_at:#x}")
    for k, (x, y) in enumerate(zip(want, got)):
        print(f"  {x.address:#x} {x.mnemonic:8} {x.op_str:30} | {y.address:#x} {y.mnemonic:8} {y.op_str}")
    print("\nliteral pairs (Sampler word -> synth word):")
    for k in sorted(set(lit_s) | set(lit_t)):
        x, y = lit_s.get(k), lit_t.get(k)
        print(f"  insn {k:3}: {x:#010x} -> {y:#010x}" if x is not None and y is not None else f"  insn {k:3}: {x} -> {y}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
