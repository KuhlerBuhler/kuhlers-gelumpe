"""Idle read of the DSP heap 1 head 0xFF904600..0xFF904620 via the firmware host-port read."""
import struct, sys
import dsp_peek as dp
from remote_press import Blech
from led_show import mido_ask
dev = Blech(mido_ask())
ref = open(sys.argv[1], "rb").read()[0x100:]
for addr, n in dp.CHECK:
    if dev.read(addr, n) != ref[addr - 0xC0000000:addr - 0xC0000000 + n]:
        raise SystemExit("code differs; nothing written")
orig = dev.read(dp.STUB_AT, dp.BUF_AT - dp.STUB_AT + dp.BUF_MAX)
try:
    dev.write(dp.STUB_AT, b"".join(struct.pack("<I", w) for w in dp.STUB))
    h = dp.dsp_read(dev, 0xFF904600, 16)
finally:
    dev.write(dp.STUB_AT, orig); print("stub buffer restored", file=sys.stderr)
print([hex(h[2 * i] | h[2 * i + 1] << 16) for i in range(8)])
