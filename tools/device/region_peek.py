"""Two idle reads of DSP L1 0xFF904000..0xFF908000 (stack + stage 2 area + rest of bank B) via the firmware host-port read.

    python3 region_peek.py --ref card-before-stage2.VSB
"""
import argparse
import json
import struct
import sys
import time

import dsp_peek as dp
from remote_press import Blech
from led_show import mido_ask

LO, HI = 0xFF904000, 0xFF908000


def read_range(dev):
    out = bytearray()
    addr = LO
    while addr < HI:
        n = min((HI - addr) // 2, dp.BUF_MAX // 2)
        h = dp.dsp_read(dev, addr, n)
        out += struct.pack(f"<{n}H", *h)
        addr += 2 * n
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    a = ap.parse_args()
    dev = Blech(mido_ask())
    ref = open(a.ref, "rb").read()[0x100:]
    for addr, n in dp.CHECK:
        if dev.read(addr, n) != ref[addr - 0xC0000000:addr - 0xC0000000 + n]:
            raise SystemExit(f"code at {addr:#x} differs from the reference; nothing written")
    original = dev.read(dp.STUB_AT, dp.BUF_AT - dp.STUB_AT + dp.BUF_MAX)
    try:
        dev.write(dp.STUB_AT, b"".join(struct.pack("<I", w) for w in dp.STUB))
        first = read_range(dev)
        time.sleep(2)
        second = read_range(dev)
    finally:
        dev.write(dp.STUB_AT, original)
        print("stub buffer restored", file=sys.stderr)
    open("bankb-1.bin", "wb").write(first)
    open("bankb-2.bin", "wb").write(second)
    report = {}
    for name, lo, hi in (("stack", 0xFF904000, 0xFF904600), ("stage2", 0xFF904600, 0xFF906180), ("rest", 0xFF906180, 0xFF908000)):
        a1, a2 = first[lo - LO:hi - LO], second[lo - LO:hi - LO]
        nz = [lo + i for i in range(0, len(a1), 4) if a1[i:i + 4] != b"\0\0\0\0"]
        report[name] = {"bytes": hi - lo, "nonzero_words": len(nz), "first_nonzero": [hex(x) for x in nz[:8]],
                        "last_nonzero": hex(nz[-1]) if nz else None,
                        "changed_bytes": sum(x != y for x, y in zip(a1, a2)), "distinct": len(set(a1))}
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
