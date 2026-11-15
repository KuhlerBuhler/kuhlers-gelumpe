"""Idle dump of DSP L1 data A and B (0xFF800000..0xFF804000, 0xFF900000..0xFF908000) via the firmware host-port read."""
import struct, sys
import dsp_peek as dp
from remote_press import Blech
from led_show import mido_ask
import region_peek as rp

def rd(dev, lo, hi):
    out = bytearray(); a = lo
    while a < hi:
        n = min((hi - a) // 2, dp.BUF_MAX // 2)
        out += struct.pack(f"<{n}H", *dp.dsp_read(dev, a, n)); a += 2 * n
    return bytes(out)

dev = Blech(mido_ask())
ref = open(sys.argv[1], "rb").read()[0x100:]
for addr, n in dp.CHECK:
    if dev.read(addr, n) != ref[addr - 0xC0000000:addr - 0xC0000000 + n]:
        raise SystemExit("code differs; nothing written")
orig = dev.read(dp.STUB_AT, dp.BUF_AT - dp.STUB_AT + dp.BUF_MAX)
try:
    dev.write(dp.STUB_AT, b"".join(struct.pack("<I", w) for w in dp.STUB))
    open("l1a.bin", "wb").write(rd(dev, 0xFF800000, 0xFF804000))
    open("l1b.bin", "wb").write(rd(dev, 0xFF900000, 0xFF908000))
finally:
    dev.write(dp.STUB_AT, orig); print("stub buffer restored", file=sys.stderr)
