# SPDX-License-Identifier: GPL-2.0-only
"""Test images for hot_patch.py, each a patched Hacktribe VSB with one small change.

    python3 make_hot_fixtures.py --vsb out/devmode/ht.VSB --out out/devmode

ht-text.VSB   the BLECH page title "DEV MODE" reads "HOT MODE": runtime text, a hot patch
ht-code.VSB   the page DEV MODE shows OFF while it is on (menu_text_dev with ldreq/ldrne swapped): runtime code, a hot patch
ht-start.VSB  one byte of the start image (read at every start): full update, start phase
ht-dsp.VSB    one byte of the DSP program (uploaded at the start): full update, DSP
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hot_patch as hp  # noqa: E402

SPLASH = 0xC00F9854         # the start image (tools/emu/bootmap.py SPLASH)
TITLE, HOT = b"DEV MODE\0", b"HOT MODE\0"
CMP_R0_0, LDR_R1_PC = 0xE3500000, 0x059F1000     # cmp r0, #0; ldreq r1, [pc, #x] (menu_text_dev)


def fixtures(raw):
    """{name: VSB bytes} for the four test images."""
    hp.payload_of(raw)
    at = raw.find(TITLE, hp.HEADER)
    if at < 0:
        raise SystemExit("the VSB has no DEV MODE page (a Sampler build with the BLECH menu is needed)")
    text = raw[:at] + HOT + raw[at + len(HOT):]

    def flip(addr):
        off = addr - hp.IMAGE + hp.HEADER
        return raw[:off] + bytes([raw[off] ^ 0xFF]) + raw[off + 1:]
    return {"ht-text.VSB": text, "ht-code.VSB": swap_on_off(raw, at - hp.HEADER + hp.IMAGE), "ht-start.VSB": flip(SPLASH + 0x40), "ht-dsp.VSB": flip(hp.DSP[0] + 0x100)}


def swap_on_off(raw, title):
    """menu_text_dev: cmp r0, #0 / ldreq r1, =str_off / ldrne r1, =str_on after the ldr of the title; swap eq and ne."""
    word = lambda off: int.from_bytes(raw[off:off + 4], "little")
    hits = []
    for off in range(hp.HEADER, len(raw) - 12, 4):
        if word(off) != CMP_R0_0 or word(off + 4) & 0xFFFFF000 != LDR_R1_PC or word(off + 8) & 0xFFFFF000 != LDR_R1_PC | 0x10000000:
            continue
        for back in range(4, 24, 4):
            w = word(off - back)
            if w & 0xFFFFF000 == 0xE59F1000 and word(off - back + 8 + (w & 0xFFF)) == title:
                hits.append(off)
    if len(hits) != 1:
        raise SystemExit(f"menu_text_dev not found once ({len(hits)} hits)")
    out = bytearray(raw)
    for off in (hits[0] + 4, hits[0] + 8):
        out[off + 3] ^= 0x10
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vsb", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for name, data in fixtures(a.vsb.read_bytes()).items():
        (a.out / name).write_bytes(data)
        print(a.out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
