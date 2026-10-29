# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for BLECH's own SysEx commands (tools/patch/blech_sysex.py,
docs/messungen/2026-10-15-blech-sysex.md).

check.py runs `cases` on every patched copy that carries the patch's hooks. The device is talked to over the
emulated DIN line, as the editor does through the emulator's `POST /midi`: INFO, READ and the two messages of a
write, every block with its CRC-32, large blocks, random writes read back over many blocks, every refusal of the
protection table (against the rule of src/protect.mjs, `--vectors`), a bad CRC, a DATA message nobody declared, other
SysEx and the panel unaffected, and with EXIT held at power-on no answer at all.

    tools/emu/.venv/bin/python tools/emu/sysex_cases.py cases --patched NEW.VSB [--flash dump.bin] [--vectors vectors.json]
    tools/emu/.venv/bin/python tools/emu/sysex_cases.py speed --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import json
import random
import struct
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import blech_sysex as spec  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
KILL = spec.KILL_SWITCH
OK, BAD_CRC, REFUSED, RANGE, VERIFY = spec.STATUS_OK, spec.STATUS_BAD_CRC, spec.STATUS_REFUSED, spec.STATUS_RANGE, spec.STATUS_VERIFY
SCRATCH = 0xC3000000            # RAM nothing uses: above the firmware's stacks and buffers, below the end of the window
NAMES = {OK: "ok", BAD_CRC: "bad crc", REFUSED: "refused", RANGE: "out of range", VERIFY: "readback differs"}
SEARCH = bytes([0xF0, 0x42, 0x50, 0x00, 0x00, 0xF7])


def has_hooks(payload):
    """True when both hooks branch into the patch's code."""
    for site in (spec.CLASSIFY_HOOK, spec.PROCESS_HOOK):
        if synthaddr.is_synth(payload):
            site = synthaddr.tr(site)
        word = struct.unpack_from("<I", payload, site - IMAGE)[0]
        if word >> 24 != 0xEA:
            return False
        off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
        if not spec.CODE_AT <= site + 8 + (off << 2) < spec.CODE_END:
            return False
    return True


def table_of(payload):
    """The protection table the patch carries, as bytes."""
    regions, windows = struct.unpack_from("<II", payload, spec.TABLE_AT - IMAGE)
    return bytes(payload[spec.TABLE_AT - IMAGE:spec.TABLE_AT - IMAGE + 4 * (2 + 3 * regions + 5 * windows)])


def build_of(payload):
    """Which build the table was cut for: Korg's records start at 0xC00A7F60, Hacktribe's insert table at 0xC00A80F0 (src/plan.mjs)."""
    table = table_of(payload)
    regions, windows = struct.unpack_from("<II", table, 0)
    starts = [struct.unpack_from("<5I", table, 4 * (2 + 3 * regions + 5 * i))[0] for i in range(windows)]
    return "stock" if 0xC00A7F60 in starts else "hacktribe"


def enc(raw):
    """The 7-bit packing of every Electribe SysEx payload (src/bytes.mjs): the high bits of seven bytes first, then the seven."""
    out = bytearray()
    for i in range(0, len(raw), 7):
        group = raw[i:i + 7]
        out.append(sum((v >> 7) << k for k, v in enumerate(group)))
        out += bytes(v & 0x7F for v in group)
    return bytes(out)


def dec(packed):
    out = bytearray()
    for i in range(0, len(packed), 8):
        group = packed[i:i + 8]
        out += bytes(group[k] | (((group[0] >> (k - 1)) & 1) << 7) for k in range(1, len(group)))
    return bytes(out)


MODEL = 0x24        # the model byte of the frame; the synth's firmware says 0x23 to the device search (synth_cases sets it)


def frame(channel, func, words=b""):
    return bytes([0xF0, 0x42, 0x30 + channel, 0x00, 0x01, MODEL, func]) + enc(words) + b"\xf7"


def entry(name, ok, detail):
    return {"id": f"sysex:{name}", "ok": bool(ok), "detail": detail}


class Link:
    """The editor's side of the line: messages in over DIN, replies and their device time out."""

    def __init__(self, dev, step=0.05):
        self.dev, self.m, self.step = dev, dev.m, step
        self.channel = 0
        self.log = []                # (what, device ms, wall seconds, bytes on the wire)
        import unicorn
        self.guard_start = spec.BUF_END
        self.guard = b'\xd3' * (spec.FILE_AREA - self.guard_start)
        self.m.uc.mem_write(self.guard_start, self.guard)
        self.m.uc.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, self.guard_access,
                           begin=self.guard_start, end=spec.FILE_AREA - 1)

    def guard_access(self, _uc, _access, address, size, _value, _data):
        raise AssertionError(f'SysEx released RAM accessed at {address:#x}+{size}')

    def exchange(self, msg, wait=60.0, quiet=0.2, fragments=None):
        """Send one message, collect what comes back until the line is quiet for `quiet` s after the first reply (or `wait` s pass)."""
        m, dev = self.m, self.dev
        t0, wall = m.time_ns, time.time()
        pending = []
        if fragments:
            at, i = 0, 0
            while at < len(msg):
                count = fragments[i % len(fragments)]
                pending.append(msg[at:at + count])
                at += count
                i += 1
        else:
            pending.append(msg)
        m.midi(pending.pop(0))
        replies, first = [], None
        end = m.time_ns / 1e9 + wait
        while m.time_ns / 1e9 < end:
            dev.run(self.step)
            if pending:
                m.midi(pending.pop(0))
            got = m.midi_out()
            replies += got
            if got and first is None:
                first = m.time_ns
            if first is not None and not pending and not got and (m.time_ns - first) / 1e9 >= quiet:
                break
        if bytes(m.uc.mem_read(self.guard_start, len(self.guard))) != self.guard:
            raise AssertionError('SysEx changed released RAM')
        done = first if first is not None else m.time_ns
        self.log.append((msg[6] if len(msg) > 6 else 0,(done - t0) / 1e6, time.time() - wall, len(msg) + sum(map(len, replies))))
        return replies, (done - t0) / 1e6

    def find_channel(self):
        replies, _ = self.exchange(SEARCH, wait=2.0)
        self.channel = replies[0][4] & 0x0F if replies else 0
        return self.channel

    def ask(self, func, words=b"", reply=None, wait=60.0):
        """The payload words of the reply to a message of ours, None when none came; and the device time it took."""
        replies, ms = self.exchange(frame(self.channel, func, words), wait=wait)
        ours = [r for r in replies if len(r) > 7 and r[6] == (reply or func + 8)]
        if not ours:
            return None, ms
        r = ours[0]
        return {"head": r[:7], "words": dec(r[7:-1]), "raw": r}, ms

    def info(self):
        r, ms = self.ask(spec.FUNC_INFO)
        if not r:
            return None
        s, version, flags, max_block, table_crc, max_flash = struct.unpack_from("<6I", r["words"])
        return {"status": s, "version": version, "flags": flags, "max_block": max_block, "table_crc": table_crc, "max_flash": max_flash, "ms": ms}

    def flash(self, addr, n, wait=60.0):
        """FLASH READ: the same answer as READ, from the flash."""
        r, ms = self.ask(spec.FUNC_FLASH, struct.pack("<II", addr, n), wait=wait)
        if not r:
            return None
        s, a, length, crc = struct.unpack_from("<4I", r["words"])
        data = r["words"][16:]
        return {"status": s, "addr": a, "length": length, "crc": crc, "data": data, "crc_ok": zlib.crc32(data) == crc, "ms": ms}

    def read(self, addr, n, wait=120.0):
        r, ms = self.ask(spec.FUNC_READ, struct.pack("<II", addr, n), wait=wait)
        if not r:
            return None
        w = r["words"]
        s, a, length, crc = struct.unpack_from("<4I", w)
        data = w[16:]
        return {"status": s, "addr": a, "length": length, "crc": crc, "data": data, "crc_ok": zlib.crc32(data) == crc, "ms": ms, "size": len(r["raw"])}

    def file_read(self, offset, n, wait=120.0):
        """FILE READ of the update file: status, offset, length, CRC, the file's size and the bytes."""
        r, ms = self.ask(spec.FUNC_FREAD, struct.pack("<II", offset, n), wait=wait)
        if not r:
            return None
        s, a, length, crc, size = struct.unpack_from("<5I", r["words"])
        data = r["words"][20:20 + length]
        return {"status": s, "offset": a, "length": length, "crc": crc, "size": size, "data": data, "crc_ok": zlib.crc32(data) == crc, "ms": ms}

    def file_write(self, offset, data, crc=None, wait=120.0):
        """FILE BEGIN, and when it says ok, DATA. Returns (begin reply, data reply or None)."""
        crc = zlib.crc32(data) if crc is None else crc
        r, _ = self.ask(spec.FUNC_FBEGIN, struct.pack("<III", offset, len(data), crc))
        if not r:
            return None, None
        s, a, length = struct.unpack_from("<3I", r["words"])
        begin = {"status": s, "offset": a, "length": length}
        if s != OK:
            return begin, None
        r, _ = self.ask(spec.FUNC_DATA, data, wait=wait)
        if not r:
            return begin, None
        s, a, length, crc2 = struct.unpack_from("<4I", r["words"])
        return begin, {"status": s, "offset": a, "length": length, "crc": crc2}

    def plugin_write(self, name, data, offset=0, wait=120.0):
        """PLUGIN BEGIN (the name as raw bytes, padded to 16), and when it says ok, DATA."""
        raw = name if isinstance(name, bytes) else name.encode("latin1")
        r, _ = self.ask(spec.FUNC_PBEGIN, struct.pack("<III", offset, len(data), zlib.crc32(data)) + raw.ljust(spec.NAME_MAX, b"\0")[:spec.NAME_MAX], reply=spec.REPLY_FBEGIN)
        if not r:
            return None, None
        s, a, length = struct.unpack_from("<3I", r["words"])
        begin = {"status": s, "offset": a, "length": length}
        if s != OK:
            return begin, None
        r, _ = self.ask(spec.FUNC_DATA, data, wait=wait)
        if not r:
            return begin, None
        s, a, length, crc2 = struct.unpack_from("<4I", r["words"])
        return begin, {"status": s, "offset": a, "length": length, "crc": crc2}

    def file_copy(self, source, target, n, wait=120.0):
        """FILE COPY between the two sample files: status, the bytes copied and their CRC-32."""
        r, _ = self.ask(spec.FUNC_COPY, struct.pack("<III", source, target, n), reply=spec.REPLY_COPY, wait=wait)
        if not r:
            return None
        s, copied, crc = struct.unpack_from("<3I", r["words"])
        return {"status": s, "copied": copied, "crc": crc}

    def file_delete(self, selector, wait=120.0):
        """FILE DELETE of a sample file: status and the word asked."""
        r, _ = self.ask(spec.FUNC_DELETE, struct.pack("<I", selector), reply=spec.REPLY_DELETE, wait=wait)
        if not r:
            return None
        s, word = struct.unpack_from("<2I", r["words"])
        return {"status": s, "selector": word}

    def file_crc(self, offset, n, wait=120.0):
        """FILE CRC of a range of a sample file: status, offset, the bytes read and their CRC-32."""
        r, _ = self.ask(spec.FUNC_CRC, struct.pack("<II", offset, n), reply=spec.REPLY_CRC, wait=wait)
        if not r:
            return None
        s, a, length, crc = struct.unpack_from("<4I", r["words"])
        return {"status": s, "offset": a, "length": length, "crc": crc}

    def write(self, addr, data, crc=None, send_data=True, wait=120.0):
        """BEGIN, and when it says ok, DATA. Returns (begin reply, data reply or None)."""
        crc = zlib.crc32(data) if crc is None else crc
        r, ms1 = self.ask(spec.FUNC_BEGIN, struct.pack("<III", addr, len(data), crc))
        if not r:
            return None, None
        s, a, length = struct.unpack_from("<3I", r["words"])
        begin = {"status": s, "addr": a, "length": length, "ms": ms1}
        if s != OK or not send_data:
            return begin, None
        r, ms2 = self.ask(spec.FUNC_DATA, data, wait=wait)
        if not r:
            return begin, None
        s, a, length, crc2 = struct.unpack_from("<4I", r["words"])
        return begin, {"status": s, "addr": a, "length": length, "crc": crc2, "ms": ms2, "size": len(r["raw"])}


def boot(payload, flash, held=0, run=1.0, link=True):
    dev = Dev(payload, flash, held)
    dev.run(run)
    if not link:
        return dev
    lk = Link(dev)
    lk.find_channel()
    return dev, lk


def mem(dev, addr, n):
    return bytes(dev.m.uc.mem_read(addr, n))


def case_protocol(payload, flash, vectors=None):
    """INFO, READ and WRITE of every size, random blocks read back, the refusals of the table, a bad CRC, a DATA message nobody declared."""
    dev, lk = boot(payload, flash)
    out = []
    info = lk.info()
    table = table_of(payload)
    out.append(entry("info", info and info["status"] == OK and info["version"] == spec.PROTOCOL_VERSION and info["flags"] == spec.FLAGS
                     and info["max_block"] == spec.MAX_BLOCK and info["table_crc"] == zlib.crc32(table) and info["max_flash"] == spec.FLASH_MAX,
                     f"version {info and info['version']}, flags {info and hex(info['flags'])}, largest block {info and info['max_block']}, "
                     f"largest flash block {info and info['max_flash']}, "
                     f"table CRC {info and hex(info['table_crc'])} against the table in the image {hex(zlib.crc32(table))} ({len(table)} bytes), answer after {info and round(info['ms'])} ms"))

    bad = []
    for size in (1, 4, 7, 8, 13, 524, 4096, 16384, spec.MAX_BLOCK):
        r = lk.read(IMAGE + 0x40, size)
        if not (r and r["status"] == OK and r["length"] == size and r["crc_ok"] and r["data"] == mem(dev, IMAGE + 0x40, size)):
            bad.append(size)
    out.append(entry("read_sizes", not bad, "reads of 1, 4, 7, 8, 13, 524, 4096, 16384 and 32768 bytes come back whole, with the CRC and the bytes of RAM" if not bad else f"sizes that failed: {bad}"))

    rng = random.Random(20261015)
    bad, total, begin_ms = [], 0, []
    for i in range(48):
        size = rng.choice([1, 2, 3, 5, 7, 8, 9, 15, 16, 100, 256, 524, 1000, 4096, 6000, spec.MAX_BLOCK]) if i < 40 else rng.randint(1, spec.MAX_BLOCK)
        addr = SCRATCH + rng.randint(0, 0x100000)
        data = bytes(rng.getrandbits(8) for _ in range(size))
        begin, done = lk.write(addr, data)
        okay = begin and begin["status"] == OK and done and done["status"] == OK and done["crc"] == zlib.crc32(data) and mem(dev, addr, size) == data
        if okay and i % 6 == 0:
            r = lk.read(addr, size)
            okay = r and r["status"] == OK and r["data"] == data and r["crc_ok"]
        if not okay:
            bad.append((i, size, begin and begin["status"], done and done["status"]))
        total += size
    out.append(entry("write_random", not bad, f"48 random blocks of 1 to {spec.MAX_BLOCK} bytes ({total} bytes), each written, its read-back CRC equal to the block's and the bytes of RAM equal; every sixth read again over the line" if not bad else f"failed: {bad[:5]}"))

    data = bytes(range(256)) * 2
    begin, done = lk.write(SCRATCH + 0x200000, data, crc=zlib.crc32(data) ^ 1)
    before = mem(dev, SCRATCH + 0x200000, len(data))
    out.append(entry("bad_crc", begin and begin["status"] == OK and done and done["status"] == BAD_CRC and done["crc"] == zlib.crc32(data) and before != data,
                     f"a DATA message whose CRC does not match is answered {done and NAMES.get(done['status'])}, with the CRC of what arrived, and nothing is written"))
    begin, done = lk.write(SCRATCH + 0x200000, data)
    out.append(entry("after_bad_crc", done and done["status"] == OK and mem(dev, SCRATCH + 0x200000, len(data)) == data, "the next write goes through"))

    r, ms = lk.ask(spec.FUNC_DATA, b"x" * 16, wait=1.5)
    again = lk.info()
    out.append(entry("data_without_begin", r is None and again and again["status"] == OK, "a DATA message that no BEGIN declared is not taken in and not answered, the next INFO is"))
    begin, done = lk.write(SCRATCH + 0x300000, b"abc")
    r, ms = lk.ask(spec.FUNC_DATA, b"abc", wait=1.5)
    out.append(entry("one_data_per_begin", begin and done and begin["status"] == OK and done["status"] == OK and r is None, "after its DATA a BEGIN is used up: a second DATA message gets no answer"))

    short = lk.ask(spec.FUNC_BEGIN, struct.pack("<III", SCRATCH + 0x300000, 64, 0))[0]
    replies, _ = lk.exchange(frame(lk.channel, spec.FUNC_DATA, b"y" * 10), wait=2.0)
    again = lk.info()
    out.append(entry("short_data", short and again and again["status"] == OK and not [x for x in replies if len(x) > 6 and x[6] == spec.REPLY_DATA],
                     f"a DATA message shorter than declared gets no DATA answer (the line answers {[x[6:7].hex() for x in replies]}), the next INFO is answered"))

    out.extend(range_cases(dev, lk))
    out.extend(protected_cases(dev, lk, payload, vectors))
    out.append(entry("no_asserts", not dev.m.asserts, "no assertion in the firmware during all of this" if not dev.m.asserts else str(list(dev.m.asserts))))
    return out


def range_cases(dev, lk):
    out, bad = [], []
    big = spec.MAX_BLOCK
    for name, addr, n, want in (
        ("zero", SCRATCH, 0, RANGE), ("one past the largest", SCRATCH, big + 1, RANGE),
        ("below the window", IMAGE - 4, 4, RANGE), ("past the window", spec.WINDOW[1] - 4, 8, RANGE),
        ("the last byte", spec.WINDOW[1] - 1, 1, OK), ("wraps", 0xFFFFFFF0, 0x20, RANGE), ("flash-like address", 0x00020000, 16, RANGE),
    ):
        r = lk.read(addr, n, wait=3.0)
        begin, _ = lk.write(addr, bytes(n), send_data=False) if n else (None, None)
        if not r or r["status"] != want or (n and want != OK and (not begin or begin["status"] != want)):
            bad.append((name, r and r["status"], begin and begin["status"]))
    out.append(entry("ranges", not bad, "zero length, one byte over the largest block, below, past and across the end of the window and a wrapping range are out of range, the last byte of the window is read" if not bad else f"wrong: {bad}"))
    return out


def protected_cases(dev, lk, payload, vectors):
    out = []
    refused = []
    for name, addr, n in (
        ("firmware code", 0xC0100000, 16), ("the patch's own code", spec.CODE_AT, 16), ("the patch's buffer", spec.BUF + 64, 16),
        ("the patch's table", spec.TABLE_AT, 8), ("task stacks", 0xC0210000, 16), ("heap", 0xC0700000, 16), ("sample info cache", 0xC0D00000, 16),
        ("work buffer", 0xC1000400, 16), ("work buffer beyond the stub", 0xC2000000, 16), ("start stack", 0xC2740000, 16),
        ("mirror of the firmware image", 0xC4100000, 16), ("mirror of the heap", 0xC4700000, 16),
    ):
        before = mem(dev, addr, n)
        begin, _ = lk.write(addr, bytes(range(n)), send_data=False)
        if not begin or begin["status"] != REFUSED or mem(dev, addr, n) != before:
            refused.append((name, begin and begin["status"]))
    out.append(entry("refuses_writes", not refused, "a write into the firmware, the patch's own code, buffer and table, the stacks, heap, caches, work buffer and into the mirror of the image or the heap is refused at BEGIN, nothing changes" if not refused else f"not refused: {refused}"))

    allowed = []
    build = build_of(payload)
    # Hacktribe keeps its records in two tables at 0xC00A80F0 and 0xC00B4F30; Korg's build has them in three runs from 0xC00A7F60
    records = (("an insert record", 0xC00A80F0, 524), ("the second master record", 0xC00B513C, 524)) if build == "hacktribe" else (("the first record", 0xC00A7F60, 524), ("a record in the third run", 0xC00AF520 + 3 * 524, 524))
    for name, addr, n in (("display", 0xC031B310, 1024), ("the stub buffer", 0xC1000000, 1024), ("a sample name", 0xC047B08C, 16), ("a sample tune", 0xC036AD9D, 1), *records):
        data = bytes((i * 7 + 3) & 0xFF for i in range(n))
        before = mem(dev, addr, n)
        begin, done = lk.write(addr, data)
        # the display is redrawn all the time: its bytes are not compared, the answer's read-back CRC says the copy was exact
        if not (begin and begin["status"] == OK and done and done["status"] == OK and done["crc"] == zlib.crc32(data) and (name == "display" or mem(dev, addr, n) == data)):
            allowed.append((name, begin and begin["status"], done and done["status"]))
        lk.write(addr, before)
    out.append(entry("allows_declared", not allowed, "the windows the editor writes (display, stub buffer, a sample name and tune, two preset records of the build) pass the regions they lie in" if not allowed else f"refused: {allowed}"))

    edge = (0xC00A80F0 if build == "hacktribe" else 0xC00A7F60) + 524 - 8
    straddle = lk.write(edge, bytes(16), send_data=False)[0]
    # a whole record of the other build's grid lies across two records of this one
    other = lk.write(0xC00A816C if build == "hacktribe" else 0xC00A80F0, bytes(524), send_data=False)[0]
    out.append(entry("window_edges", straddle and straddle["status"] == REFUSED and other and other["status"] == REFUSED,
                     "a write over the edge between two records, wider than either window, is refused, and so is a record of the other build's grid"))

    reads = []
    for name, addr, n in (("firmware code", 0xC0100000, 64), ("heap", 0xC0700000, 64), ("stacks", 0xC0210000, 64), ("the patch's own code", spec.CODE_AT, 64)):
        r = lk.read(addr, n, wait=5.0)
        if not (r and r["status"] == OK and r["data"] == mem(dev, addr, n) and r["crc_ok"]):
            reads.append(name)
    out.append(entry("reads_everywhere_in_the_window", not reads, "a read is refused only where the access itself is the risk; firmware, heap, stacks and the patch's code read back" if not reads else f"reads that failed: {reads}"))

    if vectors:
        bad = []
        for v in vectors:
            r = lk.read(v["addr"], v["length"], wait=5.0) if v["op"] == "read" and v["length"] <= spec.MAX_BLOCK else None
            begin = lk.write(v["addr"], bytes(v["length"]), send_data=False)[0] if v["op"] == "write" and v["length"] <= spec.MAX_BLOCK else None
            got = (r or begin or {}).get("status")
            if got != v["status"]:
                bad.append((hex(v["addr"]), v["length"], v["op"], got, v["status"]))
        out.append(entry("same_rule_as_the_editor", not bad, f"{len(vectors)} ranges answered as src/protect.mjs rules for them" if not bad else f"differ from the editor's rule (addr, length, op, device, editor): {bad[:5]}"))
    return out


def hacktribe_flash_write(dev, lk, at=0x7F0000):
    """Hacktribe's 0x53 sets address and length, its 0x56 then carries the bytes and writes them to the flash. Measured over
    0x56 alone (0x53 of its own rewrites a pattern slot, see docs/messungen/2026-10-24-hacktribe-flash.md): no program or erase,
    the flash at the address unchanged."""
    data = bytes(range(16))
    lk.exchange(frame(lk.channel, 0x53, struct.pack("<II", at, len(data))), wait=3.0)
    was = bytes(dev.m.flash.mem[at:at + len(data)])
    before_counts, _ = flash_counts(dev)
    lk.exchange(frame(lk.channel, 0x56, data), wait=3.0)
    after_counts, _ = flash_counts(dev)
    changing = (0x01, 0x02, 0x20, 0x52, 0xD8, 0x60, 0xC7)
    written = {hex(k): after_counts.get(k, 0) - before_counts.get(k, 0) for k in changing if after_counts.get(k, 0) != before_counts.get(k, 0)}
    return not written and bytes(dev.m.flash.mem[at:at + len(data)]) == was, written


STUB_MARK = SCRATCH + 0x100
# The code EXEC runs in the checks: keeps its argument at STUB_MARK and returns it plus one.
STUB = struct.pack("<5I", 0xE59F1008, 0xE5810000, 0xE2800001, 0xE12FFF1E, STUB_MARK)   # ldr r1, [pc, #8]; str r0, [r1]; add r0, r0, #1; bx lr


def has_hacktribe(payload):
    return any(b != 0xFF for b in payload[0x170000:0x170040])


def hacktribe_read(lk):
    """Whether Hacktribe's 0x52 answers a RAM read."""
    r, _ = lk.exchange(frame(lk.channel, 0x52, struct.pack("<II", IMAGE + 0x40, 16)), wait=2.0)
    return any(len(x) > 9 and x[6] == 0x54 and x[7] == 0x52 for x in r)


def hacktribe_write_and_run(dev, lk):
    """Hacktribe's 0x53 and 0x54 write 16 bytes to SCRATCH, its 0x57 runs the stub BLECH put into the stub buffer before. True when
    none of it happened: SCRATCH, the stub buffer and the stub's mark as they were."""
    data = bytes(range(0x40, 0x50))
    before, stub_was, mark_was = mem(dev, SCRATCH, 16), mem(dev, spec.EXEC_START, 0x40), mem(dev, STUB_MARK, 4)
    lk.exchange(frame(lk.channel, 0x53, struct.pack("<II", SCRATCH, len(data))), wait=2.0)
    lk.exchange(frame(lk.channel, 0x54, data), wait=2.0)
    lk.exchange(frame(lk.channel, 0x57, struct.pack("<II", spec.EXEC_START, 0)), wait=2.0)
    return mem(dev, SCRATCH, 16) == before and mem(dev, spec.EXEC_START, 0x40) == stub_was and mem(dev, STUB_MARK, 4) == mark_was


def exec_cases(dev, lk):
    """EXEC runs a word of the stub buffer after BLECH wrote it there, with its argument, and answers what it returned; anywhere else
    it refuses and runs nothing. Hacktribe's own commands are dropped."""
    out = []
    begin, done = lk.write(spec.EXEC_START, STUB)
    wrote = bool(done and done["status"] == OK and mem(dev, spec.EXEC_START, len(STUB)) == STUB)
    out.append(entry("exec_stub_written", wrote, "the stub goes into the stub buffer through WRITE"))
    r, _ = lk.ask(spec.FUNC_EXEC, struct.pack("<II", spec.EXEC_START, 0x1234), reply=spec.REPLY_EXEC)
    words = struct.unpack_from("<3I", r["words"]) if r else None
    out.append(entry("exec_runs", words == (OK, spec.EXEC_START, 0x1235) and mem(dev, STUB_MARK, 4) == struct.pack("<I", 0x1234),
                     f"EXEC runs the stub with its argument in r0 and answers ok and what it returned ({words})"))
    bad = []
    for addr in (spec.EXEC_START + 2, spec.EXEC_END, spec.EXEC_START - 4, SCRATCH, IMAGE + 0x40, 0):
        dev.m.uc.mem_write(STUB_MARK, b"\0\0\0\0")
        r, _ = lk.ask(spec.FUNC_EXEC, struct.pack("<II", addr, 7), reply=spec.REPLY_EXEC)
        words = struct.unpack_from("<3I", r["words"]) if r else None
        if words != (REFUSED, addr, 0) or mem(dev, STUB_MARK, 4) != b"\0\0\0\0":
            bad.append((hex(addr), words))
    out.append(entry("exec_refused", not bad, "EXEC outside the words of the stub buffer is refused and runs nothing" if not bad else f"failed: {bad}"))
    out.append(entry("hacktribe_read_dropped", not hacktribe_read(lk), "Hacktribe's RAM read 0x52 gets no answer"))
    out.append(entry("hacktribe_write_run_dropped", hacktribe_write_and_run(dev, lk), "Hacktribe's 0x53, 0x54 and 0x57 write nothing, not even into the stub buffer, and run nothing"))
    again = lk.info()
    out.append(entry("exec_info_after", again and again["status"] == OK and again["flags"] & 0x40 and not dev.m.asserts, "INFO says EXEC (flag bit 6) and still answers after all of it, no assertion"))
    return out


def case_kill_switch(payload, flash):
    """With EXIT held at power-on both hooks pass everything on but 0x56: our function bytes get no answer, Korg's own and Hacktribe's do."""
    dev, lk = boot(payload, flash, held=KILL)
    out = []
    silent = []
    for func, words in ((spec.FUNC_INFO, b""), (spec.FUNC_READ, struct.pack("<II", IMAGE + 0x40, 16)), (spec.FUNC_BEGIN, struct.pack("<III", SCRATCH, 4, 0)),
                        (spec.FUNC_FLASH, struct.pack("<II", 0x220000, 16)), (spec.FUNC_EXEC, struct.pack("<II", spec.EXEC_START, 0))):
        r, _ = lk.ask(func, words, wait=1.5, reply=spec.REPLY_EXEC if func == spec.FUNC_EXEC else None)
        silent.append(r is None)
    out.append(entry("kill_switch_silent", all(silent), "with EXIT held at power-on INFO, READ, BEGIN, FLASH READ and EXEC get no answer"))
    out.append(entry("kill_switch_hacktribe", hacktribe_read(lk) == has_hacktribe(payload), "with EXIT held at power-on Hacktribe's RAM read 0x52 answers again" if has_hacktribe(payload) else "without Hacktribe 0x52 stays unanswered"))
    r, _ = lk.exchange(frame(lk.channel, 0x10), wait=20.0)
    out.append(entry("kill_switch_korg_still_answers", any(len(x) > 7000 for x in r), f"with EXIT held at power-on Korg's own pattern request is answered ({[len(x) for x in r]} bytes)"))
    blocked, written = hacktribe_flash_write(dev, lk)
    out.append(entry("kill_switch_no_flash_write", blocked, f"with EXIT held at power-on Hacktribe's flash write 0x56 still writes nothing ({written or 'no program or erase'})"))
    out.append(entry("kill_switch_no_asserts", not dev.m.asserts, "no assertion"))
    return out


def case_other_sysex(payload, flash):
    """Korg's SysEx and the panel work as they did; Hacktribe's own commands are dropped."""
    dev, lk = boot(payload, flash)
    out = []
    replies, _ = lk.exchange(SEARCH, wait=2.0)
    out.append(entry("search", replies and len(replies[0]) == 15, "the device search is answered"))
    pattern, _ = lk.exchange(frame(lk.channel, 0x10), wait=10.0)
    dump = next((x for x in pattern if x[6:7] == b"\x40"), None)
    out.append(entry("pattern_request", dump and len(dec(dump[7:-1])) == 0x4000, "Korg's pattern request returns the 16384 bytes of the pattern"))
    glob, _ = lk.exchange(frame(lk.channel, 0x0E), wait=5.0)
    out.append(entry("global_request", any(x[6:7] == b"\x51" for x in glob), "Korg's global request is answered with the dump"))
    if synthaddr.is_synth(payload):
        out.append(entry("hacktribe_read_dropped", not hacktribe_read(lk), "Hacktribe's RAM read 0x52 gets no answer"))
    else:
        out.extend(exec_cases(dev, lk))
    blocked, written = hacktribe_flash_write(dev, lk)
    out.append(entry("hacktribe_flash_write_dropped", blocked, f"Hacktribe's flash write 0x56 after 0x53 writes nothing ({written or 'no program or erase'})"))
    before = mem(dev, 0xC0000040, 64)
    for note in (0x3C, 0x40, 0x43):
        dev.m.midi(bytes([0x90 | lk.channel, note, 100]))
        dev.run(0.05)
        dev.m.midi(bytes([0x80 | lk.channel, note, 0]))
        dev.run(0.05)
    dev.run(0.5)
    again = lk.info()
    out.append(entry("notes", again and again["status"] == OK and not dev.m.asserts and mem(dev, 0xC0000040, 64) == before, "MIDI notes on the global channel go through, an INFO after them is answered, no assertion"))
    return out


def flash_counts(dev):
    """What the emulated flash chip was asked to do: {command: count}, and whether anything was programmed or erased."""
    f = dev.m.flash
    return dict(f.commands), f.dirty


def flash_cases(dev, lk):
    """FLASH READ on a running device (any build): sizes, the content equal to the flash, the limits, and no write or erase."""
    out = []
    mem_flash = dev.m.flash.mem
    before_counts, before_dirty = flash_counts(dev)
    bad = []
    for addr, n in ((0x220000, 16), (0, 1), (0x5E74 - 7, 7), (0x20000, 256), (0x800000, 4096), (0xFFF000, 4096), (0xFFFFFF, 1), (0x123457, 1000)):
        r = lk.flash(addr, n)
        if not (r and r["status"] == OK and r["addr"] == addr and r["length"] == n and r["crc_ok"] and r["data"] == bytes(mem_flash[addr:addr + n])):
            bad.append((hex(addr), n, r and r["status"]))
    out.append(entry("flash_read", not bad, "FLASH READ of 1 to 4096 bytes at the start (the boot image), the user-data mark, the firmware, the PCM bank and the last byte comes back whole, with the CRC-32 and the bytes of the flash" if not bad else f"failed: {bad}"))
    bad = []
    for name, addr, n, want in (("zero", 0x220000, 0, RANGE), ("over the largest block", 0, spec.FLASH_MAX + 1, RANGE), ("starts at the end", 0x1000000, 1, RANGE),
                                ("ends past the end", 0xFFFFFF, 2, RANGE), ("long past the end", 0xFFF000, 0x1001, RANGE), ("wraps", 0xFFFFFFF0, 0x20, RANGE),
                                ("far away", 0x80000000, 16, RANGE)):
        r = lk.flash(addr, n, wait=3.0)
        if not (r and r["status"] == want and r["crc"] == 0 and not r["data"]):
            bad.append((name, r and r["status"]))
    out.append(entry("flash_limits", not bad, "zero length, one byte over the largest block, a start at or past 0x1000000, a range across the end and a wrapping range are answered out of range, with no data" if not bad else f"wrong: {bad}"))
    again = lk.info()
    after_counts, after_dirty = flash_counts(dev)
    changing = (0x01, 0x02, 0x20, 0x52, 0xD8, 0x60, 0xC7)      # write status, page program, the erases
    written = {hex(k): after_counts.get(k, 0) - before_counts.get(k, 0) for k in changing if after_counts.get(k, 0) != before_counts.get(k, 0)}
    out.append(entry("flash_untouched", not written and after_dirty == before_dirty and again and again["status"] == OK,
                     f"during all of these the flash chip saw no program or erase command ({written or 'none'}), its content was not marked changed, INFO is answered"))
    out.append(entry("flash_no_asserts", not dev.m.asserts, "no assertion in the firmware"))
    return out


def file_cases(payload, flash):
    """FILE READ and FILE BEGIN: exactly the update file KORG/<folder>/System/SYSTEM.VSB, written in blocks that are read back from
    the card, a first block that makes the file anew, the size limit of a VSB, a card error without card or folder, silence with EXIT
    held at power-on. The file on the card image is compared byte for byte."""
    import cardstore
    import fat32
    from sdcard import MemoryMedium, SDCard
    folder = cardstore.card_folder(bytes(payload))
    path = f"KORG/{folder}/System/SYSTEM.VSB"
    out = []

    def device(files=None, card=True, held=0):
        dev = Dev(payload, flash, held)
        if card:
            img = fat32.format_image(64 * 1024 * 1024)
            vol = fat32.Volume(img)
            for name, data in (files or {}).items():
                vol.write(name, data)
            vol.close()
            dev.m.insert_card(SDCard(MemoryMedium(bytearray(img))))
        dev.run(1.0)
        lk = Link(dev)
        lk.find_channel()
        return dev, lk

    def on_card(dev, name=path):
        try:
            vol = fat32.Volume(dev.m.mmc.card.medium.data)
            return vol.read(name)
        except Exception:
            return None

    rng = random.Random(20261018)
    data = bytes(rng.getrandbits(8) for _ in range(70000))
    dev, lk = device({f"KORG/{folder}/System/keep.txt": b"x", "KORG/blechtribe/Plugin/keep.txt": b"x"})
    none = lk.file_read(0, 0)
    out.append(entry("file_missing", none and none["status"] == spec.STATUS_FILE and none["size"] == 0, f"no update file yet: status {none and none['status']}"))
    results = []
    for at in range(0, len(data), spec.MAX_BLOCK):
        results.append(lk.file_write(at, data[at:at + spec.MAX_BLOCK]))
    ok = all(b and b["status"] == OK and d and d["status"] == OK and d["crc"] == zlib.crc32(data[i * spec.MAX_BLOCK:(i + 1) * spec.MAX_BLOCK]) for i, (b, d) in enumerate(results))
    out.append(entry("file_write_blocks", ok and on_card(dev) == data and not dev.m.asserts,
                     f"{len(data)} bytes in {len(results)} blocks, each read back from the card with its CRC: {ok}; the file {path} equals them: {on_card(dev) == data}"))
    size = lk.file_read(0, 0)
    back = b"".join(lk.file_read(at, min(spec.MAX_BLOCK, len(data) - at))["data"] for at in range(0, len(data), spec.MAX_BLOCK))
    tail = lk.file_read(len(data) - 100, 4096)
    out.append(entry("file_read_back", size and size["status"] == OK and size["size"] == len(data) and back == data and tail and tail["length"] == 100 and tail["crc_ok"],
                     f"size {size and size['size']}, read back equal {back == data}, a read past the end gives the {tail and tail['length']} bytes there are"))
    short = bytes(range(256)) * 20
    lk.file_write(0, short)
    out.append(entry("file_offset_zero_makes_it_anew", on_card(dev) == short, f"a first block at offset 0 makes the file anew: {len(on_card(dev) or b'')} bytes on the card, written {len(short)}"))
    other = f"KORG/{folder}/System/ORIGINAL.BIN"
    keep = bytes(rng.getrandbits(8) for _ in range(9000))
    ob, od = lk.file_write(spec.FILE_OTHER | 0, keep)
    oread = lk.file_read(spec.FILE_OTHER | 0, len(keep))
    out.append(entry("file_original_beside", ob and ob["status"] == OK and od and od["status"] == OK and on_card(dev, other) == keep and on_card(dev) == short
                     and oread and oread["data"] == keep and oread["size"] == len(keep),
                     f"bit 31 of the offset: ORIGINAL.BIN beside it written and read back ({on_card(dev, other) == keep}), SYSTEM.VSB untouched ({on_card(dev) == short})"))
    far, _ = lk.file_write(spec.FILE_LIMIT - 0x100, bytes(0x200))
    empty, _ = lk.file_write(0, b"")
    big = lk.file_read(0, spec.MAX_BLOCK + 1)
    out.append(entry("file_limits", far and far["status"] == RANGE and empty and empty["status"] == RANGE and big and big["status"] == RANGE and on_card(dev) == short,
                     f"past the size of a VSB {far and far['status']}, no bytes {empty and empty['status']}, a read over the largest block {big and big['status']}; the file unchanged"))
    blob = bytes(rng.getrandbits(8) for _ in range(5000))
    pb, pd = lk.plugin_write("Short-Delay_2", blob)
    plugin = "KORG/blechtribe/Plugin/Short-Delay_2.blech"
    bad = [lk.plugin_write(n, b"x")[0] for n in (b"../../x", b"a/b", b"", b"a\0b", b"a.b", "ä".encode("latin1"))]
    out.append(entry("file_plugin", pb and pb["status"] == OK and pd and pd["status"] == OK and pd["crc"] == zlib.crc32(blob) and on_card(dev, plugin) == blob
                     and all(r and r["status"] == RANGE for r in bad) and on_card(dev) == short and not dev.m.asserts,
                     f"PLUGIN BEGIN writes {plugin} ({on_card(dev, plugin) == blob}), read back with its CRC; a name with a slash, dots, nothing, a zero inside, "
                     f"a dot or a letter beyond ASCII is refused: {[r and r['status'] for r in bad]}"))
    bare, lk4 = device({f"KORG/{folder}/System/keep.txt": b"x"})
    made = "KORG/blechtribe/Plugin/Made-Folder.blech"
    nb, nd = lk4.plugin_write("Made-Folder", blob[:300])
    out.append(entry("file_plugin_makes_folders", nb and nb["status"] == OK and nd and nd["status"] == OK and on_card(bare, made) == blob[:300] and not bare.m.asserts,
                     f"a card without KORG/blechtribe (the blue's has only KORG/electribe): PLUGIN BEGIN makes the folders and writes {made} ({on_card(bare, made) == blob[:300]})"))
    nocard, lk2 = device(card=False)
    r = lk2.file_read(0, 0)
    out.append(entry("file_no_card", r and r["status"] == spec.STATUS_FILE and not nocard.m.asserts, f"without a card: status {r and r['status']}"))
    held, lk3 = device(held=KILL)
    r = lk3.file_read(0, 0)
    out.append(entry("file_kill_switch_silent", r is None, "with EXIT held at power-on FILE READ gets no answer"))
    return out


def sample_cases(payload, flash, held_only=False):
    """The sample file Sample/e2sSample.all and its temp file beside it (bit 30 of a FILE offset, bit 31 for the temp file): read, written
    in place without cutting the file, FILE COPY between the two, FILE CRC, FILE DELETE, and the whole way the editor takes to compact the
    file: the temp file complete and checked, the old file deleted, the temp file copied back, deleted. The card image is read back with the
    FAT reader after every step. Nothing else of the card may change: SYSTEM.VSB stays."""
    import cardstore
    import fat32
    from sdcard import MemoryMedium, SDCard
    folder = cardstore.card_folder(bytes(payload))
    sample = f"KORG/{folder}/Sample/e2sSample.all"
    temp = f"KORG/{folder}/Sample/e2sSample.tmp"
    vsb = f"KORG/{folder}/System/SYSTEM.VSB"
    ALL, TMP = spec.FILE_SAMPLE, spec.FILE_SAMPLE | spec.FILE_OTHER
    out = []

    def device(files=None, card=True, held=0):
        dev = Dev(payload, flash, held)
        if card:
            img = fat32.format_image(64 * 1024 * 1024)
            vol = fat32.Volume(img)
            for name, data in (files or {}).items():
                vol.write(name, data)
            vol.close()
            dev.m.insert_card(SDCard(MemoryMedium(bytearray(img))))
        dev.run(1.0)
        lk = Link(dev)
        lk.find_channel()
        return dev, lk

    def on_card(dev, name):
        try:
            return fat32.Volume(dev.m.mmc.card.medium.data).read(name)
        except Exception:
            return None

    rng = random.Random(20261026)
    blob = lambda n: bytes(rng.getrandbits(8) for _ in range(n))
    old = blob(40000)
    system = blob(3000)
    if held_only:
        held, lk3 = device({sample: old}, held=KILL)
        answers = [lk3.file_read(ALL | 0, 0), lk3.file_copy(ALL | 0, TMP | 0, 10), lk3.file_delete(ALL), lk3.file_crc(ALL | 0, 10)]
        out.append(entry("sample_kill_switch_silent", all(a is None for a in answers) and on_card(held, sample) == old,
                         "with EXIT held at power-on READ, COPY, DELETE and CRC get no answer and the file is still there"))
        return out
    dev, lk = device({sample: old, vsb: system, f"KORG/{folder}/Sample/keep.txt": b"x"})
    size = lk.file_read(ALL | 0, 0)
    head = lk.file_read(ALL | 100, 500)
    out.append(entry("sample_read", size and size["status"] == OK and size["size"] == len(old) and head and head["data"] == old[100:600] and head["crc_ok"],
                     f"the sample file {sample} is read through bit 30: size {size and size['size']}, 500 bytes from offset 100 equal: {bool(head) and head['data'] == old[100:600]}"))
    big = lk.file_read(ALL | (spec.SAMPLE_LIMIT - 10), 100)
    ok_far = lk.file_read(ALL | 0x0FFF0000, 100)
    out.append(entry("sample_read_limits", big and big["status"] == RANGE and ok_far and ok_far["status"] == OK and ok_far["length"] == 0,
                     f"past the limit of a sample file {big and big['status']}; a read inside the limit but past the end of the file gives {ok_far and ok_far['length']} bytes"))
    # in place: the header block at offset 0 does not cut the file
    header = blob(4096)
    b, d = lk.file_write(ALL | 0, header)
    new = header + old[4096:]
    out.append(entry("sample_header_in_place", b and b["status"] == OK and d and d["status"] == OK and d["crc"] == zlib.crc32(header) and on_card(dev, sample) == new,
                     f"a block at offset 0 rewrites the header and the rest of the file stays: {on_card(dev, sample) == new}, {len(on_card(dev, sample) or b'')} bytes on the card"))
    tail = blob(5000)
    b, d = lk.file_write(ALL | len(new), tail)
    new += tail
    out.append(entry("sample_append", b and b["status"] == OK and d and d["status"] == OK and on_card(dev, sample) == new,
                     f"a block at the end appends: {len(on_card(dev, sample) or b'')} bytes on the card, expected {len(new)}"))
    # the temp file: offset 0 makes it anew
    b, d = lk.file_write(TMP | 0, header)
    stale = on_card(dev, temp)
    b2, d2 = lk.file_write(TMP | 0, header[:1000])
    out.append(entry("sample_temp_anew", b and d and stale == header and b2 and d2 and on_card(dev, temp) == header[:1000] and on_card(dev, sample) == new,
                     f"the temp file is made at offset 0 and made anew by the next block at 0 ({len(on_card(dev, temp) or b'')} bytes); the sample file stays"))
    # copy, with the CRC of what was copied
    lk.file_write(TMP | 0, header)
    r1 = lk.file_copy(ALL | 4096, TMP | 4096, 12345)
    r2 = lk.file_copy(ALL | 20000, TMP | 4096 + 12345, 9000)
    want = header + new[4096:4096 + 12345] + new[20000:29000]
    out.append(entry("sample_copy", r1 and r2 and r1["status"] == OK and r2["status"] == OK and r1["copied"] == 12345 and r2["copied"] == 9000
                     and r1["crc"] == zlib.crc32(new[4096:4096 + 12345]) and r2["crc"] == zlib.crc32(new[20000:29000]) and on_card(dev, temp) == want and on_card(dev, sample) == new,
                     f"two pieces copied to the temp file, each with the CRC of its bytes ({r1 and r1['status']}, {r2 and r2['status']}); the temp file equals the pieces: {on_card(dev, temp) == want}"))
    c1 = lk.file_crc(TMP | 0, len(want))
    c2 = lk.file_crc(TMP | 4096, 12345)
    out.append(entry("sample_crc", c1 and c2 and c1["status"] == OK and c1["length"] == len(want) and c1["crc"] == zlib.crc32(want) and c2["crc"] == zlib.crc32(new[4096:4096 + 12345]),
                     f"FILE CRC reads the card and answers the CRC-32 of {c1 and c1['length']} bytes without sending them: {bool(c1) and c1['crc'] == zlib.crc32(want)}"))
    if MODEL == 0x23:
        # the blue Electribe 2's image has no f_unlink: DELETE says 6, the files stay, and INFO does not claim the sample file commands
        info = lk.info()
        d1 = lk.file_delete(ALL)
        out.append(entry("sample_synth_no_delete", d1 and d1["status"] == spec.STATUS_FILE and on_card(dev, sample) == new and info and not info["flags"] & 0x80 and not dev.m.asserts,
                         f"the synth's FatFs has no unlink: DELETE says {d1 and d1['status']}, the sample file stays ({on_card(dev, sample) == new}), the INFO flags {info and hex(info['flags'])} do not carry bit 7"))
        return out
    # the way back: delete the old, copy the temp file back, delete the temp file
    d1 = lk.file_delete(ALL)
    gone = on_card(dev, sample) is None
    back = lk.file_copy(TMP | 0, ALL | 0, len(want))
    done = lk.file_delete(TMP)
    out.append(entry("sample_swap", d1 and d1["status"] == OK and gone and back and back["status"] == OK and back["crc"] == zlib.crc32(want) and done and done["status"] == OK
                     and on_card(dev, sample) == want and on_card(dev, temp) is None and on_card(dev, vsb) == system and not dev.m.asserts,
                     f"delete the old file ({d1 and d1['status']}, gone {gone}), copy the temp file back ({back and back['status']}), delete it ({done and done['status']}): the sample file equals the compacted one "
                     f"({on_card(dev, sample) == want}), the temp file is gone, SYSTEM.VSB is untouched ({on_card(dev, vsb) == system}), no assertion in the firmware"))
    # refusals
    other = lk.file_delete(0)
    plain = lk.file_delete(spec.FILE_OTHER | 0)
    same = lk.file_copy(ALL | 0, ALL | 100, 10)
    from_vsb = lk.file_copy(0, TMP | 0, 10)
    to_vsb = lk.file_copy(ALL | 0, 0, 10)
    nothing = lk.file_copy(ALL | 0, TMP | 0, 0)
    toolong = lk.file_copy(ALL | 0, TMP | 0, spec.COPY_MAX + 1)
    beyond = lk.file_copy(ALL | 0, TMP | (spec.SAMPLE_LIMIT - 5), 10)
    short = lk.file_copy(ALL | len(want) - 100, TMP | 0, 500)
    missing = lk.file_delete(TMP)
    crc_bad = [lk.file_crc(0, 10), lk.file_crc(ALL | 0, 0), lk.file_crc(ALL | 0, spec.COPY_MAX + 1), lk.file_crc(ALL | len(want) - 10, 100)]
    statuses = [r and r["status"] for r in (other, plain, same, from_vsb, to_vsb, nothing, toolong, beyond, short, missing)] + [r and r["status"] for r in crc_bad]
    wanted = [REFUSED, REFUSED, REFUSED, REFUSED, REFUSED, RANGE, RANGE, RANGE, RANGE, spec.STATUS_FILE, REFUSED, RANGE, RANGE, RANGE]
    out.append(entry("sample_refusals", statuses == wanted and on_card(dev, vsb) == system and on_card(dev, sample) == want and on_card(dev, temp) is None,
                     f"DELETE of SYSTEM.VSB or ORIGINAL.BIN, COPY inside one file or from or to a file that is no sample file, no bytes, over COPY_MAX, past the limit, a source that ends early, "
                     f"DELETE of a missing file, and the bad CRC ranges: {statuses}, wanted {wanted}; SYSTEM.VSB and the sample file are unchanged"))
    # no card, EXIT held
    nocard, lk2 = device(card=False)
    r = lk2.file_read(ALL | 0, 0)
    c = lk2.file_copy(ALL | 0, TMP | 0, 10)
    dl = lk2.file_delete(ALL)
    out.append(entry("sample_no_card", r and c and dl and r["status"] == spec.STATUS_FILE and c["status"] == spec.STATUS_FILE and dl["status"] == spec.STATUS_FILE and not nocard.m.asserts,
                     f"without a card READ, COPY and DELETE say 6: {[x and x['status'] for x in (r, c, dl)]}"))
    return out


def case_flash(payload, flash):
    """FLASH READ, on the flash the check was given (blank, or the user's own dump)."""
    dev, lk = boot(payload, flash)
    return flash_cases(dev, lk)


def case_stream(payload, flash):
    """DIN parser fragmentation, malformed requests and recovery with released RAM guarded."""
    dev, lk = boot(payload, flash)
    out = []
    for length in (1, 6, 7, 8, 63, 64, 127, 32768):
        msg = frame(lk.channel, spec.FUNC_READ, struct.pack('<II', SCRATCH, length))
        replies, _ = lk.exchange(msg, fragments=(1, 6, 7, 8, 63, 64, 127), wait=120)
        words = dec(replies[0][7:-1]) if replies else b''
        expected = mem(dev, SCRATCH, length)
        good = len(words) == length + 16 and struct.unpack_from('<4I', words) == (OK, SCRATCH, length, zlib.crc32(expected)) and words[16:] == expected
        out.append(entry(f'fragmented_read_{length}', good, 'DIN request fragmented across header and packing groups; reply and CRC exact'))
    for length in (1, 7, 256, 32768):
        data = bytes((i * 73 ^ i >> 3 ^ 0xa5) & 255 for i in range(length))
        before = mem(dev, SCRATCH, length)
        begin, _ = lk.write(SCRATCH, data, send_data=False)
        if MODEL == 0x23:
            good = begin and begin['status'] == REFUSED and mem(dev, SCRATCH, length) == before
        else:
            replies, _ = lk.exchange(frame(lk.channel, spec.FUNC_DATA, data), fragments=(1, 6, 7, 8, 63, 64, 127, 4096), wait=120)
            words = dec(replies[0][7:-1]) if replies else b''
            good = begin and begin['status'] == OK and words == struct.pack('<4I', OK, SCRATCH, length, zlib.crc32(data)) and mem(dev, SCRATCH, length) == data
        out.append(entry(f'fragmented_write_{length}', good, 'fragmented DATA writes exact bytes and CRC; synth refuses the declaration'))
    for name, request in (
        ('short', frame(lk.channel, spec.FUNC_READ, bytes(7))),
        ('long', frame(lk.channel, spec.FUNC_READ, struct.pack('<II', SCRATCH, 7) + b'\x7f'))):
        replies, _ = lk.exchange(request, wait=0.5)
        again = lk.info()
        out.append(entry(f'parser_{name}_recovery', replies == [frame(lk.channel, 0x26)] and again and again['status'] == OK and not dev.m.asserts,
                         'malformed request gets the original format-error reply; next INFO succeeds'))
    replies, _ = lk.exchange(frame(lk.channel, spec.FUNC_READ, bytes(8))[:-3], wait=0.5)
    first, retry = lk.info(), lk.info()
    out.append(entry('parser_interrupted_recovery', not replies and first is None and retry and retry['status'] == OK and not dev.m.asserts,
                     'without F7 the original parser consumes the first retry through its terminator; second INFO succeeds'))
    begin, _ = lk.write(SCRATCH, bytes(spec.MAX_BLOCK + 1), send_data=False)
    replies, _ = lk.exchange(frame(lk.channel, spec.FUNC_DATA, b'\x01' * 8), wait=0.5)
    again = lk.info()
    out.append(entry('oversize_then_retry', begin and begin['status'] == RANGE and not replies and again and again['status'] == OK,
                     '32769-byte BEGIN refused, undeclared DATA silent, next INFO succeeds'))
    return out


def sample_kill_switch_cases(payload, flash):
    """sample_cases with EXIT held at power-on, a group of its own: each of its four requests waits 120 s for no answer."""
    return sample_cases(payload, flash, held_only=True)


GROUPS = (case_protocol, case_kill_switch, case_other_sysex, case_flash, file_cases, sample_cases, sample_kill_switch_cases,
          case_stream)   # each its own task in check.py


def synth_cases(payload, flash):
    """A smoke check of the patch on the blue Electribe 2 (the synth): INFO, RAM read, writes refused (its RAM map is not
    measured, so the table refuses every write), FLASH READ with its limits and no flash write, EXIT at power-on, Korg's own
    SysEx and no assertion. `payload` is the patched synth's 0x200000 bytes behind the head."""
    global MODEL
    MODEL = 0x23
    try:
        dev, lk = boot(payload, flash)
        out = []
        out.append(entry("synth_main_screen", dev.m.screen() == 1 and not dev.m.asserts, f"the patched synth firmware is on screen {dev.m.screen()} (1 is the main screen)"))
        info = lk.info()
        table = table_of(payload)
        out.append(entry("synth_info", info and info["status"] == OK and info["version"] == spec.PROTOCOL_VERSION and info["flags"] == spec.FLAGS & ~0x80
                         and info["max_block"] == spec.MAX_BLOCK and info["max_flash"] == spec.FLASH_MAX and info["table_crc"] == zlib.crc32(table),
                         f"INFO answered with model byte 0x23: flags {info and hex(info['flags'])}, flash block {info and info['max_flash']}, table {len(table)} bytes, CRC equal to the image's: {bool(info) and info['table_crc'] == zlib.crc32(table)}"))
        bad = []
        for size in (1, 7, 524, 4096):
            r = lk.read(IMAGE + 0x40, size)
            if not (r and r["status"] == OK and r["crc_ok"] and r["data"] == mem(dev, IMAGE + 0x40, size)):
                bad.append(size)
        out.append(entry("synth_read", not bad, "READ of RAM comes back whole with its CRC" if not bad else f"failed: {bad}"))
        before = mem(dev, SCRATCH, 64)
        begin, _ = lk.write(SCRATCH, bytes(range(64)), send_data=False)
        again = lk.info()
        out.append(entry("synth_writes_refused", begin and begin["status"] == REFUSED and mem(dev, SCRATCH, 64) == before and again and again["status"] == OK,
                         "a write is refused already at BEGIN, because the synth's RAM map is not measured; the RAM stays"))
        r, _ = lk.ask(spec.FUNC_EXEC, struct.pack("<II", spec.EXEC_START, 0), reply=spec.REPLY_EXEC)
        words = struct.unpack_from("<3I", r["words"]) if r else None
        out.append(entry("synth_exec_refused", words == (REFUSED, spec.EXEC_START, 0), f"EXEC is refused, because nothing may be written there ({words})"))
        out.extend(flash_cases(dev, lk))
        out.extend(case_kill_switch(payload, flash))
        out.extend(case_other_sysex(payload, flash))
        out.extend(file_cases(payload, flash))
        out.extend(sample_cases(payload, flash))
        out.extend(case_stream(payload, flash))
        return out
    finally:
        MODEL = 0x24


def group_entries(payload, flash, i, vectors=None):
    """check.py entries of case group i; each boots its own device, so they can run side by side."""
    if synthaddr.is_synth(payload):
        return synth_cases(payload, flash) if i == 0 else []
    return GROUPS[i](payload, flash, vectors) if i == 0 else GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i, parallel.shared.get("sysex_vectors"))


def cases(payload, flash=None, vectors=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i, vectors)]


def speed(payload, flash=None, sizes=(16, 256, 1024, 4096, 8192, 16384, 24576, 32768)):
    """Device time and wall time of READ and WRITE per block size, over the emulated DIN line (about 3.1 KB/s: the line, not the patch, is the limit)."""
    dev, lk = boot(payload, flash)
    rows = []
    for size in sizes:
        addr = SCRATCH
        data = bytes((i * 31 + 7) & 0xFF for i in range(size))
        wall = time.time()
        r = lk.read(IMAGE + 0x40, size)
        read_wall = time.time() - wall
        wall = time.time()
        begin, done = lk.write(addr, data)
        write_wall = time.time() - wall
        rows.append({"size": size, "read_ok": bool(r and r["status"] == OK and r["crc_ok"]), "read_device_ms": round(r["ms"]) if r else None,
                     "read_wall_s": round(read_wall, 2), "write_ok": bool(done and done["status"] == OK and mem(dev, addr, size) == data),
                     "write_device_ms": round(begin["ms"] + done["ms"]) if done else None, "write_wall_s": round(write_wall, 2),
                     "read_wire_bytes": r["size"] + 7 + 14 if r else None, "write_wire_bytes": 7 + 14 + 2 + 7 + (size + 6) // 7 * 8 + 1 if done else None})
    return rows


def main():
    import lifetime
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases", "speed", "synth"))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--vectors", type=Path, help="ranges and what src/protect.mjs says about them, JSON")
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    vectors = json.loads(a.vectors.read_text()) if a.vectors else None
    if a.what == "speed":
        print(json.dumps(speed(payload, flash), indent=1))
        return 0
    if a.what == "synth":
        import machine
        entries = synth_cases(payload, flash or bytes(machine.blank_flash(b"KORGelec2USR")))
        print(json.dumps(entries, indent=1))
        return 0 if all(e["ok"] for e in entries) else 1
    entries = group_entries(payload, flash, a.only, vectors) if a.only is not None else cases(payload, flash, vectors)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
