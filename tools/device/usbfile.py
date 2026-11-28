"""BLECH's FILE READ and FILE BEGIN over USB (tools/patch/blech_sysex.py): the update file on the card, or ORIGINAL.BIN beside it,
or the effect collection KORG/blechtribe/Presets/e2sFx.all.

    python3 usbfile.py sizes                          # SYSTEM.VSB and ORIGINAL.BIN on the card, in bytes
    python3 usbfile.py get FILE [--original | --fx]   # the file from the card into FILE
    python3 usbfile.py put FILE [--original | --fx]   # FILE onto the card, every block read back with its CRC, then all of it

`put` writes the card: a broken SYSTEM.VSB is flashed by the next SOFTWARE UPDATE, so `get` a backup first. `--fx put` takes a
collection only (src/fx-collection.mjs: magic GFXA, its size in the header, at most FX_LIMIT bytes) and only from a firmware whose
INFO has FLAG_FX_WRITE; the loader takes it at the next power-on.
"""
import argparse
import struct
import zlib

from flash_dump import enc, dec
from led_show import mido_ask

INFO, FILE_READ, FILE_BEGIN, DATA = 0x60, 0x65, 0x66, 0x63
R_INFO, R_FILE_READ, R_FILE_BEGIN, R_DATA = 0x68, 0x6D, 0x6E, 0x6B
ORIGINAL = 0x80000000            # bit 31: ORIGINAL.BIN instead of SYSTEM.VSB
FX = 0x60000000                  # bits 30 and 29: KORG/blechtribe/Presets/e2sFx.all
FLAG_FX_WRITE = 0x800            # INFO: FILE BEGIN takes e2sFx.all
FX_LIMIT = 0x500000
FX_MAGIC = 0x41584647            # "GFXA"
STATUS = {1: "CRC wrong", 2: "refused", 3: "out of range", 5: "read back differs", 6: "card error"}


class Link:
    def __init__(self, ask):
        self.ask = ask
        found = ask([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])
        if found[:4] != [0xF0, 0x42, 0x50, 0x01] or found[6] not in (0x23, 0x24):
            raise SystemExit(f"no Electribe answered the search: {bytes(found).hex()}")
        self.channel, self.model = found[4] & 15, found[6]
        status, version, self.flags, self.block = struct.unpack_from("<4I", self.call(INFO, b"", R_INFO))
        if status or version != 1:
            raise SystemExit(f"INFO: status {status}, version {version}; no BLECH SysEx")

    def call(self, func, words, reply):
        got = self.ask([0xF0, 0x42, 0x30 + self.channel, 0, 1, self.model, func, *enc(words), 0xF7])
        if got[:7] != [0xF0, 0x42, 0x30 + self.channel, 0, 1, self.model, reply]:
            raise SystemExit(f"an answer that is not ours: {bytes(got[:12]).hex()}")
        return dec(got[7:-1])


def size(link, select):
    """The file's size; 0 when the card has none."""
    status, _, _, code, total = struct.unpack_from("<5I", link.call(FILE_READ, struct.pack("<II", select, 0), R_FILE_READ))
    if status == 6:
        return 0
    if status:
        raise SystemExit(f"FILE READ: {STATUS.get(status, status)} (code {code:#x})")
    return total


def read(link, select, total):
    out = bytearray()
    while len(out) < total:
        n = min(link.block, total - len(out))
        raw = link.call(FILE_READ, struct.pack("<II", select | len(out), n), R_FILE_READ)
        status, _, length, crc, _ = struct.unpack_from("<5I", raw)
        data = raw[20:20 + length]
        if status or length != n or zlib.crc32(data) != crc:
            raise SystemExit(f"FILE READ at {len(out)}: {STATUS.get(status, status)}, {length} of {n} bytes")
        out += data
    return bytes(out)


def write(link, select, data, block=2048):
    for at in range(0, len(data), block):
        chunk = data[at:at + block]
        crc = zlib.crc32(chunk)
        status = struct.unpack_from("<I", link.call(FILE_BEGIN, struct.pack("<3I", select | at, len(chunk), crc), R_FILE_BEGIN))[0]
        if status:
            raise SystemExit(f"FILE BEGIN at {at}: {STATUS.get(status, status)}")
        status, _, _, back = struct.unpack_from("<4I", link.call(DATA, chunk, R_DATA))
        if status or back != crc:
            raise SystemExit(f"DATA at {at}: {STATUS.get(status, status)} (CRC word {back:#x})")
        if (at + len(chunk)) % (256 * 1024) < block:
            print(f"  written {at + len(chunk)} of {len(data)}", flush=True)


def collection_problem(data):
    if len(data) < 24 or struct.unpack_from("<I", data)[0] != FX_MAGIC:
        return "not an effect collection (no GFXA header)"
    if struct.unpack_from("<I", data, 8)[0] != len(data):
        return f"the header says {struct.unpack_from('<I', data, 8)[0]} bytes, the file has {len(data)}"
    if len(data) > FX_LIMIT:
        return f"{len(data)} bytes, the firmware takes at most {FX_LIMIT}"
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("sizes", "get", "put"))
    p.add_argument("file", nargs="?")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--original", action="store_true", help="ORIGINAL.BIN instead of SYSTEM.VSB")
    which.add_argument("--fx", action="store_true", help="KORG/blechtribe/Presets/e2sFx.all")
    a = p.parse_args()
    if a.what != "sizes" and not a.file:
        p.error("get and put need FILE")
    select = FX if a.fx else ORIGINAL if a.original else 0
    data = open(a.file, "rb").read() if a.what == "put" else None
    if a.what == "put" and a.fx and collection_problem(data):
        raise SystemExit(f"{a.file}: {collection_problem(data)}")
    link = Link(mido_ask())
    if a.what == "sizes":
        print("SYSTEM.VSB", size(link, 0), "ORIGINAL.BIN", size(link, ORIGINAL))
    elif a.what == "get":
        n = size(link, select)
        open(a.file, "wb").write(read(link, select, n))
        print("read", n)
    else:
        if a.fx and not link.flags & FLAG_FX_WRITE:
            raise SystemExit(f"INFO flags {link.flags:#x}: this firmware cannot write e2sFx.all over USB")
        write(link, select, data)
        print("wrote", len(data))
        back = read(link, select, size(link, select))
        print("read back equal:", back == data)


if __name__ == "__main__":
    main()
