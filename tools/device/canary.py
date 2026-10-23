"""RAM only. fill: puts two stubs at 0xC1008000 / 0xC1008100 and fills 0xC1010000..0xC4000000 with addr ^ 0x5A5AA5A5.
check: runs the check stub, reads the per-4-KiB map at 0xC1009000 and prints the blocks that changed."""
import os, struct, sys, time, hashlib
from pathlib import Path
from led_show import Device, mido_ask, emulator_ask, ICACHE_INVALIDATE, EXPECTED
HERE = Path(__file__).parent / "canary"
FILL, CHECK, MAP = 0xC1008000, 0xC1008100, 0xC1009000   # Hacktribe's write stages its payload at 0xC1000000
START, END = 0xC1010000, int(os.environ.get("CANARY_END", "0xC4000000"), 0)
N = (END - START) // 4096
def main(mode, emu=None):
    dev = Device(emulator_ask(emu)[0] if emu else mido_ask())
    if hashlib.sha256(dev.read(ICACHE_INVALIDATE, 0x34)).hexdigest() != EXPECTED[(ICACHE_INVALIDATE, 0x34)]:
        raise SystemExit("cache routine differs, nothing written")
    if mode == "fill":
        fill = bytearray((HERE / "fill.bin").read_bytes()); struct.pack_into("<I", fill, 0x28, END)
        check = bytearray((HERE / "check.bin").read_bytes()); struct.pack_into("<I", check, 0x54, END); struct.pack_into("<I", check, 0x5C, MAP)
        dev.write(FILL, bytes(fill))
        dev.write(CHECK, bytes(check))
        dev.execute(ICACHE_INVALIDATE)
        t = time.time(); dev.execute(FILL); print(f"filled {(END-START)>>20} MiB in {time.time()-t:.2f} s (incl. USB)", flush=True)
        for a in (START, 0xC2000000, END - 16):
            print(hex(a), dev.read(a, 8).hex(), flush=True)
    if os.environ.get("CANARY_POKE"):
        dev.write(int(os.environ["CANARY_POKE"], 0), b"\x01\x02\x03\x04")
    t = time.time(); dev.execute(CHECK); dt = time.time() - t
    m = dev.read(MAP, N)
    bad = [(START + i * 4096, v) for i, v in enumerate(m) if v]
    print(f"check {dt:.2f} s: {len(bad)} of {N} blocks changed", flush=True)
    runs = []
    for a, v in bad:
        if runs and runs[-1][1] == a: runs[-1][1] = a + 4096; runs[-1][2] = max(runs[-1][2], v)
        else: runs.append([a, a + 4096, v])
    for s, e, v in runs[:60]: print(f"  {s:#x}-{e:#x} {(e-s)>>10} KiB, up to {v} words per block")
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
