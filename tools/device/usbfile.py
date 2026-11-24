"""BLECH's FILE READ and FILE BEGIN over USB (tools/patch/blech_sysex.py): the update file on the card, or ORIGINAL.BIN beside it,
or the effect collection KORG/blechtribe/Presets/e2sFx.all, and the native recording's takes in SD:Recordings (read only).

    python3 usbfile.py sizes                          # SYSTEM.VSB and ORIGINAL.BIN on the card, in bytes
    python3 usbfile.py get FILE [--original | --fx]   # the file from the card into FILE
    python3 usbfile.py put FILE [--original | --fx]   # FILE onto the card, every block read back with its CRC, then all of it
    python3 usbfile.py list-rec                       # the takes in SD:Recordings: number, size, "busy" for the one being written
    python3 usbfile.py get-rec N FILE                 # take N (REC<N>.WAV) into FILE; refused while it is being written

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
REC = 0xE0000000                 # bits 31, 30 and 29 of FILE READ: a take; offset in 8 bytes, number in the length word's bits 16 up
FLAG_REC = 0x1000                # INFO: FILE READ reads and lists the takes
STATUS = {1: "CRC wrong", 2: "refused", 3: "out of range", 5: "read back differs", 6: "card error", 7: "the take is being written"}


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


def rec_call(link, number, offset, n):
    raw = link.call(FILE_READ, struct.pack("<II", REC | offset // 8, number << 16 | n), R_FILE_READ)
    status, _, length, crc, total = struct.unpack_from("<5I", raw)
    data = raw[20:20 + length]
    if status or zlib.crc32(data) != crc:
        what = "the list" if number == 0 else f"REC{number:04d}.WAV"
        raise SystemExit(f"FILE READ of {what} at {offset}: {STATUS.get(status, status)} (code {crc:#x})")
    return data, total


def rec_read(link, number):
    """Take `number` (0: the list of the folder, 8 bytes per take) whole, in blocks of a multiple of 8 bytes."""
    if not link.flags & FLAG_REC:
        raise SystemExit(f"INFO flags {link.flags:#x}: this firmware cannot read the recordings over USB")
    _, total = rec_call(link, number, 0, 0)
    out, block = bytearray(), link.block & ~7
    while len(out) < total:
        data, _ = rec_call(link, number, len(out), min(block, total - len(out)))
        if not data:
            raise SystemExit(f"FILE READ stopped at {len(out)} of {total} bytes")
        out += data
    return bytes(out)


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
    p.add_argument("what", choices=("sizes", "get", "put", "list-rec", "get-rec"))
    p.add_argument("file", nargs="?", help="FILE, or for get-rec the take's number")
    p.add_argument("out", nargs="?", help="get-rec: the file to write")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--original", action="store_true", help="ORIGINAL.BIN instead of SYSTEM.VSB")
    which.add_argument("--fx", action="store_true", help="KORG/blechtribe/Presets/e2sFx.all")
    a = p.parse_args()
    if a.what == "get-rec":
        if not (a.file and a.file.isdigit() and 1 <= int(a.file) <= 9999 and a.out):
            p.error("get-rec needs N (1 to 9999) and FILE")
        link = Link(mido_ask())
        data = rec_read(link, int(a.file))
        open(a.out, "wb").write(data)
        print("read", len(data))
        return
    if a.what == "list-rec":
        listing = rec_read(Link(mido_ask()), 0)
        for number, total in sorted(struct.iter_unpack("<II", listing)):
            print(f"REC{number & 0x7FFFFFFF:04d}.WAV {total}" + (" busy" if number >> 31 else ""))
        return
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
