# SPDX-License-Identifier: GPL-2.0-only
"""The SD card slot of the emulated Electribe: an MMC controller and an SDHC card on an image.

The firmware talks to the AM180x MMC0 block (base 0x01C40000) by polling the
FIFO, with one interrupt line (16). There is no DMA. Registers and the command
sequence are the ones measured in docs/hintergrund/virtuelle-sd.md.
Modelled beyond the plain SDHC card (docs/emulator.md, "Virtuelle SD-Karte"): SDSC cards (no CMD8 answer, byte
addresses, CSD version 1.0), the write-protect switch (GPIO 4.0, read by the firmware's disk status), CRC7 on the
answers and CRC16 on every data block, checked by the controller, and faults a test arms on a card: no answer, a bad
CRC on an answer or a data block, a read that times out or fails, a write the card refuses. Where the behaviour is
assumed and not measured it is marked "Modellannahme" here and in the docs.
"""

import binascii
import collections
import struct

SECTOR = 512
IRQ = 16                     # AINTC line the firmware enables for MMC0, handler 0xC0025BD0

CTL, CLK, ST0, ST1, IM = 0x00, 0x04, 0x08, 0x0C, 0x10
BLEN, NBLK, DRR, DXR, CMD, ARG = 0x1C, 0x20, 0x28, 0x2C, 0x30, 0x34
RSP01, RSP67, DRSP = 0x38, 0x44, 0x48

ST0_DATDNE, ST0_BSYDNE, ST0_RSPDNE, ST0_TOUTRD, ST0_TOUTRS = 0x1, 0x2, 0x4, 0x8, 0x10
ST0_CRCWR, ST0_CRCRD, ST0_CRCRS = 0x20, 0x40, 0x80      # AM1808 MMCST0: write-data, read-data and response CRC error
ST0_DXRDY, ST0_DRRDY = 0x200, 0x400
CHUNK = 64                   # FIFO level the firmware sets (FIFOCTL 0x5): one interrupt per 64 bytes, read or written in one go

STATES = {"idle": 0, "ready": 1, "ident": 2, "stby": 3, "tran": 4, "data": 5, "rcv": 6}

# bits of the card status in an R1 answer
R1_OUT_OF_RANGE, R1_ADDRESS_ERROR, R1_COM_CRC_ERROR, R1_ECC_FAILED, R1_ERROR = 1 << 31, 1 << 30, 1 << 23, 1 << 21, 1 << 19

KINDS = ("sdhc", "sdsc")
ANSWER_FAULTS = ("no_response", "response_crc")       # on a command's answer; `cmds` picks the commands (all when empty)
READ_FAULTS = ("read_timeout", "read_error", "read_crc")
WRITE_FAULTS = ("write_error", "write_crc")
FAULTS = ANSWER_FAULTS + READ_FAULTS + WRITE_FAULTS


class MemoryMedium:
    """A card image in memory. The store in cardstore.py has the same four members."""

    def __init__(self, data, read_only=False):
        self.data = data
        self.read_only = read_only

    @property
    def sectors(self):
        return len(self.data) // SECTOR

    def read(self, lba):
        return bytes(self.data[lba * SECTOR:(lba + 1) * SECTOR])

    def write(self, lba, block):
        if not self.read_only:
            self.data[lba * SECTOR:(lba + 1) * SECTOR] = block


def crc7(data):
    """CRC7 of the SD command and answer frames (x^7 + x^3 + 1), the 7 bits that go before the end bit."""
    crc = 0
    for byte in data:
        for i in range(7, -1, -1):
            top = (crc >> 6) & 1
            crc = (crc << 1) & 0x7F
            if top ^ ((byte >> i) & 1):
                crc ^= 0x09
    return crc


def crc16(data):
    """CRC16 of a data block as the card sends and expects it (CRC-CCITT, polynomial 0x1021, start value 0).
    Modellannahme: one CRC over the 512 bytes; a 4-bit bus has one CRC per data line, which the firmware never sees."""
    return binascii.crc_hqx(bytes(data), 0)


def flip(data):
    """The bytes with one bit turned over, a block or an answer hit on the wire."""
    out = bytearray(data)
    out[len(out) // 2] ^= 0x01
    return bytes(out)


def frame(idx, payload):
    """An R1, R6 or R7 answer as it is on the wire after the start and transmission bits: the command index, the 32
    bits, then CRC7 and the end bit (6 bytes)."""
    body = bytes([idx & 0x3F]) + struct.pack(">I", payload)
    return body + bytes([(crc7(body) << 1) | 1])


class Fault:
    """One thing that goes wrong on a card, from the moment it is armed on (`SDCard.fail`).

    `kind` is one of FAULTS. `cmds` (the command numbers) and `lbas` (a range, set or list of block numbers: the block
    of a data fault, the first block of the data command an answer fault meets) narrow what it hits, None means
    everything. `skip` events that match go through untouched first, then it hits
    `count` times (None: for good). `hits` counts what it hit."""

    def __init__(self, kind, cmds=None, lbas=None, skip=0, count=None):
        if kind not in FAULTS:
            raise ValueError(f"unknown card fault {kind!r}; known: {', '.join(FAULTS)}")
        self.kind, self.skip, self.count, self.hits = kind, int(skip), None if count is None else int(count), 0
        self.cmds = None if cmds is None else frozenset(int(c) for c in cmds)
        self.lbas = None if lbas is None else (lbas if isinstance(lbas, range) else frozenset(int(b) for b in lbas))

    def hit(self, group, idx=None, lba=None):
        if self.kind not in group or (self.cmds is not None and idx not in self.cmds) \
                or (self.lbas is not None and lba not in self.lbas):
            return False
        if self.skip > 0:
            self.skip -= 1
            return False
        if self.count is not None and self.hits >= self.count:
            return False
        self.hits += 1
        return True


    @staticmethod
    def parse(raw):
        """A fault from its JSON form: {"kind", "cmds": [..], "lbas": [..] or {"from", "to"}, "skip", "count"}."""
        if not isinstance(raw, dict) or set(raw) - {"kind", "cmds", "lbas", "skip", "count"}:
            raise ValueError("Ein Kartenfehler hat nur: kind, cmds, lbas, skip, count.")
        lbas = raw.get("lbas")
        if isinstance(lbas, dict):
            if set(lbas) != {"from", "to"}:
                raise ValueError("lbas als Bereich hat from und to.")
            lbas = range(int(lbas["from"]), int(lbas["to"]))
        elif lbas is not None and not isinstance(lbas, list):
            raise ValueError("lbas ist eine Liste oder ein Bereich mit from und to.")
        cmds = raw.get("cmds")
        if cmds is not None and not isinstance(cmds, list):
            raise ValueError("cmds ist eine Liste von Befehlsnummern.")
        return Fault(raw.get("kind"), cmds=cmds, lbas=lbas, skip=raw.get("skip", 0), count=raw.get("count"))

    def describe(self):
        lbas = self.lbas
        if isinstance(lbas, range):
            lbas = {"from": lbas.start, "to": lbas.stop}
        elif lbas is not None:
            lbas = sorted(lbas)[:64]
        return {"kind": self.kind, "cmds": sorted(self.cmds) if self.cmds is not None else None, "lbas": lbas,
                "skip": self.skip, "count": self.count, "hits": self.hits}


class SDCard:
    """The card at command level: 512-byte blocks, addressed by block number (SDHC) or by byte (SDSC).

    `kind` "sdsc" is an old standard-capacity card: it does not know CMD8 (no answer), reports no high-capacity bit
    in the OCR, has a version 1.0 CSD and takes byte addresses (Modellannahme: only multiples of 512, as the firmware
    sends them after CMD16 with 512). `write_protect` is the lock switch of the card, which the socket reports on
    GPIO 4.0 (machine.py). `never_ready` is a card whose power-up never ends (ACMD41 stays busy). `faults` are armed
    from the start; `fail()` arms more at any time."""

    def __init__(self, medium, kind="sdhc", write_protect=False, never_ready=False, faults=()):
        if kind not in KINDS:
            raise ValueError(f"unknown card kind {kind!r}; known: {', '.join(KINDS)}")
        if kind == "sdsc" and medium.sectors * SECTOR > 2 << 30:
            raise ValueError("an SDSC card holds 2 GiB at most")
        self.medium, self.kind = medium, kind
        self.write_protect, self.never_ready = bool(write_protect), bool(never_ready)
        self.faults = [f if isinstance(f, Fault) else Fault(**f) for f in faults]
        self.sectors_read = self.sectors_written = 0
        self.commands = collections.Counter()
        self.err = 0                # error bits for the next R1 (they describe the command before, as on a card)
        self.address_errors = 0     # data commands whose byte address was no whole block (SDSC)
        self.reset()

    OPTION_KEYS = {"kind", "writeProtect", "neverReady", "faults"}

    @classmethod
    def options(cls, raw, live=False):
        """The constructor arguments for the options of a request (JSON): "kind" ("sdhc", "sdsc"), "writeProtect",
        "neverReady", "faults" (see Fault.parse). `live` leaves "kind" out: a card in the slot keeps its kind."""
        raw = {} if raw is None else raw
        allowed = cls.OPTION_KEYS - ({"kind", "neverReady"} if live else set())
        if not isinstance(raw, dict) or set(raw) - allowed:
            raise ValueError("Mögliche Kartenoptionen: " + ", ".join(sorted(allowed)) + ".")
        out = {}
        if "kind" in raw:
            out["kind"] = raw["kind"]
        for key, name in (("writeProtect", "write_protect"), ("neverReady", "never_ready")):
            if key in raw:
                if not isinstance(raw[key], bool):
                    raise ValueError(f"{key} ist wahr oder falsch.")
                out[name] = raw[key]
        if "faults" in raw:
            if not isinstance(raw["faults"], list):
                raise ValueError("faults ist eine Liste.")
            out["faults"] = [Fault.parse(f) for f in raw["faults"]]
        if out.get("kind", "sdhc") not in KINDS:
            raise ValueError("Kartenart: " + ", ".join(KINDS) + ".")
        return out

    def describe(self):
        return {"kind": self.kind, "writeProtect": self.write_protect, "neverReady": self.never_ready,
                "faults": [f.describe() for f in self.faults]}

    def fail(self, kind, **narrow):
        """Arm a fault now (see Fault). Returns it, so a test can read `hits`."""
        fault = Fault(kind, **narrow)
        self.faults.append(fault)
        return fault

    def heal(self):
        """Take every armed fault away."""
        self.faults.clear()

    def fault_at(self, group, idx=None, lba=None):
        """The kind of the first armed fault of `group` that hits this event, or None."""
        for f in self.faults:
            if f.hit(group, idx, lba):
                return f.kind
        return None

    def reset(self):
        self.state, self.rca, self.app, self.acmd41 = "idle", 0, False, 0

    def ocr(self):
        ready = self.acmd41 >= 2 and not self.never_ready
        return (0x40FF8000 if self.kind == "sdhc" else 0x00FF8000) | (0x80000000 if ready else 0)

    def cid(self):
        b = bytearray(16)
        b[0], b[1:3], b[3:8], b[8] = 0x03, b"SD", b"EMUSD", 0x10
        b[9:13], b[13], b[14] = struct.pack(">I", 0x12345678), 0x01, 0x5A
        b[15] = (crc7(b[:15]) << 1) | 1
        return bytes(b)

    def csd(self):
        """CSD version 2.0 (SDHC): capacity in units of 512 KiB. SDSC: version 1.0."""
        if self.kind == "sdsc":
            return self._csd_v1()
        b = bytearray(16)
        b[0:6] = bytes([0x40, 0x0E, 0x00, 0x32, 0x5B, 0x59])
        c_size = self.medium.sectors // 1024 - 1
        b[7], b[8], b[9] = (c_size >> 16) & 0x3F, (c_size >> 8) & 0xFF, c_size & 0xFF
        b[10:15] = bytes([0x7F, 0x80, 0x0A, 0x40, 0])
        b[15] = (crc7(b[:15]) << 1) | 1
        return bytes(b)

    def _csd_v1(self):
        """CSD version 1.0: capacity is (C_SIZE + 1) * 2^(C_SIZE_MULT + 2) blocks of 2^READ_BL_LEN bytes, so up to 1 GiB
        with 512-byte blocks and up to 2 GiB with 1024-byte ones; the card still reads and writes 512 after CMD16."""
        size = self.medium.sectors * SECTOR
        bl_len = 9 if size <= 1 << 30 else 10
        blocks = size >> bl_len
        mult = max((m for m in range(8) if blocks % (1 << (m + 2)) == 0 and (blocks >> (m + 2)) <= 4096), default=0)
        value = int.from_bytes(bytes([0x00, 0x0E, 0x00, 0x32, 0x5B, 0x59, 0x00, 0, 0, 0, 0x7F, 0x80, 0x0A, 0x40, 0, 0]), "big")

        def put(hi, lo, v):
            nonlocal value
            width = hi - lo + 1
            value = (value & ~(((1 << width) - 1) << lo)) | ((v & ((1 << width) - 1)) << lo)

        put(83, 80, bl_len)                              # READ_BL_LEN
        put(73, 62, (blocks >> (mult + 2)) - 1)          # C_SIZE
        put(49, 47, mult)                                # C_SIZE_MULT
        put(45, 39, 0x7F)                                # SECTOR_SIZE
        put(25, 22, bl_len)                              # WRITE_BL_LEN
        b = bytearray(value.to_bytes(16, "big"))
        b[15] = (crc7(b[:15]) << 1) | 1
        return bytes(b)

    def status(self):
        return (STATES[self.state] << 9) | 0x100 | (0x20 if self.app else 0)

    def r1(self):
        """The status for an R1: the card's state with the error bits of the command before, which then clear."""
        out = self.status() | self.err
        self.err = 0
        return out

    def block_of(self, arg):
        """The block an address names: the block number itself on SDHC, the byte offset on SDSC. None when it is
        not a whole block (Modellannahme: the card then reports ADDRESS_ERROR and moves no data)."""
        if self.kind == "sdhc":
            return arg
        return arg // SECTOR if arg % SECTOR == 0 else None

    def command(self, idx, arg):
        """One command: (kind, ...). Kinds: none, r1, r2, r3, r6, read, write, timeout.
        An R1, R6 or R7 answer carries the 6 bytes of its frame as a third member (frame()); a data command is
        ("read" or "write", block, multiple, reason), reason "address" for a byte address that is no whole block."""
        self.commands[idx] += 1
        lba = self.block_of(arg) if idx in (17, 18, 24, 25) else None
        if self.fault_at(ANSWER_FAULTS[:1], idx, lba) == "no_response":
            return ("timeout",)                           # the card did not hear it: nothing changes
        res = self._command(idx, arg)
        if res[0] in ("r1", "r6", "r2") and self.fault_at(ANSWER_FAULTS[1:], idx, lba) == "response_crc":
            if res[0] == "r2":
                return ("r2", flip(res[1]))
            return (res[0], res[1], flip(res[2]))
        return res

    def _answer(self, kind, idx, payload):
        return (kind, payload, frame(idx, payload))

    def _command(self, idx, arg):
        app, self.app = self.app, False
        if idx == 0:
            self.reset()
            return ("none", 0)
        if idx == 8:
            if self.kind == "sdsc":
                return ("timeout",)                       # a version 1.x card does not know CMD8
            return self._answer("r1", 8, arg & 0xFFF)     # R7: the check pattern echoed
        if idx == 55:
            self.app = True
            return self._answer("r1", 55, self.r1() | 0x20)
        if app and idx == 41:
            self.acmd41 += 1
            if self.acmd41 >= 2 and not self.never_ready:
                self.state = "ready"
            return ("r3", self.ocr())
        if app and idx == 6:
            return self._answer("r1", 6, self.r1())       # bus width, nothing to do for the model
        if idx == 2:
            self.state = "ident"
            return ("r2", self.cid())
        if idx == 3:
            self.rca, self.state = 0x1234, "stby"
            return self._answer("r6", 3, (self.rca << 16) | (self.r1() & 0xFFFF))
        if idx == 9:
            return ("r2", self.csd())
        if idx == 10:
            return ("r2", self.cid())
        if idx == 7:
            self.state = "tran" if (arg >> 16) == self.rca else "stby"
            return self._answer("r1", 7, self.r1())
        if idx == 12:
            self.state = "tran"
            return self._answer("r1", 12, self.r1())
        if idx == 16:
            return self._answer("r1", 16, self.r1())
        if idx in (17, 18, 24, 25):
            block = self.block_of(arg)
            if block is not None and block >= self.medium.sectors:
                return ("timeout",)
            if block is None:
                self.err |= R1_ADDRESS_ERROR
                self.address_errors += 1
            return ("read" if idx in (17, 18) else "write", block, idx in (18, 25), None if block is not None else "address")
        return ("timeout",)

    # ---- data blocks ---------------------------------------------------------------
    def send_block(self, lba):
        """The block a read puts on the wire: (bytes, crc16 the card sends with them, fault). Bytes and CRC differ when
        a read_crc fault hit; a read_timeout or read_error fault gives no block (None) and, for the error, the
        ECC_FAILED bit in the next R1."""
        fault = self.fault_at(READ_FAULTS, lba=lba)
        if fault in ("read_timeout", "read_error"):
            if fault == "read_error":
                self.err |= R1_ECC_FAILED
            return None, 0, fault
        block = self.medium.read(lba) if lba < self.medium.sectors else bytes(SECTOR)
        self.sectors_read += 1
        crc = crc16(block)
        return (flip(block) if fault == "read_crc" else block), crc, fault

    def accept_block(self, lba, block, crc):
        """A block a write put on the wire with the CRC the host computed. Returns the CRC status token of the card:
        "ok" (010), "crc" (101, the CRC did not match) or "error" (110, programming error). Only "ok" stores it."""
        fault = self.fault_at(WRITE_FAULTS, lba=lba)
        if fault == "write_crc":
            block = flip(block)                           # hit on the wire after the host computed the CRC
        if crc16(block) != crc:
            self.err |= R1_COM_CRC_ERROR
            return "crc"
        if fault == "write_error":
            self.err |= R1_ERROR
            return "error"
        self.medium.write(lba, block)
        self.sectors_written += 1
        return "ok"


class MMCController:
    """MMC0 registers over an SDCard, or over no card at all (every command goes unanswered)."""

    def __init__(self, card=None):
        self.card = card
        self.regs = {}
        self.st0 = 0
        self.rsp = [0] * 8              # response as 16-bit words, RSP01 first
        self.rx = bytearray()           # block waiting in MMCDRR
        self.tx = bytearray()           # bytes written to MMCDXR
        self.tx_lba = None
        self.tx_drop = False            # the write has no valid address: the card takes the data and drops it
        self.rx_bad = False             # the block in MMCDRR arrived with a CRC that does not match
        self.cur_lba = 0
        self.blocks_left = 0
        self.chunk = False              # a 64-byte chunk is ready (read) or has room (write) and has not raised the interrupt yet
        self.slow_card = None           # a CLKRT the card cannot keep up with: reads at it go unanswered (a card unfit for that clock)

    # ---- registers -------------------------------------------------------------
    def read(self, off, size):
        if off == ST0:
            v = self.st0
            if self.rx:
                v |= ST0_DRRDY
            if self.tx_lba is not None and len(self.tx) < self._block():
                v |= ST0_DXRDY
            self.st0 = 0
            return v
        if off == ST1 or off == DRSP:
            return 0
        if off == DRR:
            return self._pop(size)
        if RSP01 <= off <= RSP67:
            i = (off - RSP01) // 4
            return self.rsp[2 * i] | (self.rsp[2 * i + 1] << 16)
        return self.regs.get(off, 0)

    def write(self, off, v, size):
        if off == DXR:
            n = 4 if size >= 4 else size
            self.tx += (v & ((1 << (8 * n)) - 1)).to_bytes(n, "little")
            if len(self.tx) % CHUNK == 0:
                self.chunk = True           # room for the next chunk
            self._flush()
            return
        self.regs[off] = v
        if off == CMD:
            self._command(v)

    def irq(self):
        """The interrupt line: asserted while an unmasked status bit is pending. Data ready (read) and room (write)
        count once per 64-byte chunk, as the FIFO raises them when it reaches its level: a chunk that has raised the
        line (`raised`) does not raise it again while the firmware is still taking it. Raised twice, the second
        interrupt can come after the firmware took the chunk and sent its next command, and the handler, which
        reads MMCST0, takes that command's answer away (the assertion at AM180xMMSDCardController.cpp line 228)."""
        if self.card is None:
            return False
        pend = self.st0
        if self.chunk and self.rx:
            pend |= ST0_DRRDY
        if self.chunk and self.tx_lba is not None:
            pend |= ST0_DXRDY
        return bool(pend & self.regs.get(IM, 0))

    def raised(self):
        """The interrupt controller took the line: the pending chunk has had its interrupt."""
        self.chunk = False

    # ---- data phase ------------------------------------------------------------
    def _block(self):
        return self.regs.get(BLEN, SECTOR) or SECTOR

    def _load(self, lba):
        """The next block of a read comes off the card. A block that fails (the card gives none) ends the transfer with
        the data timeout flag (Modellannahme: signalled at once, not after MMCTOD); a block whose CRC16 does not match
        is delivered and flagged when the last byte is taken, as the compare happens at the end of the block."""
        self.cur_lba = lba
        block, crc, fault = self.card.send_block(lba)
        if block is None:
            self.rx, self.rx_bad, self.chunk = bytearray(), False, False
            self.blocks_left = 0
            self.st0 |= ST0_TOUTRD
            return
        self.rx = bytearray(block)
        self.rx_bad = crc16(block) != crc
        self.chunk = True

    def _pop(self, size):
        if not self.rx:
            return 0
        n = 4 if size >= 4 else size
        chunk = self.rx[:n]
        del self.rx[:n]
        if len(self.rx) % CHUNK == 0:
            self.chunk = True               # the next chunk is up (or, with none left, nothing is pending)
        if not self.rx:
            if self.rx_bad:
                self.st0 |= ST0_CRCRD
                self.rx_bad = False
            if self.blocks_left > 1:
                self.blocks_left -= 1
                self._load(self.cur_lba + 1)
            else:
                self.blocks_left = 0
                self.st0 |= ST0_DATDNE
        return int.from_bytes(chunk.ljust(n, b"\0"), "little")

    def _flush(self):
        size = self._block()
        while self.tx_lba is not None and len(self.tx) >= size:
            block = bytes(self.tx[:size])
            del self.tx[:size]
            if not self.tx_drop:
                token = self.card.accept_block(self.tx_lba, block, crc16(block))
                if token != "ok":
                    self.st0 |= ST0_CRCWR       # Modellannahme: a CRC status token other than "ok" shows as CRCWR
            self.tx_lba += 1
            self.blocks_left -= 1
            if self.blocks_left <= 0:
                self.tx_lba = None
                self.st0 |= ST0_DATDNE

    # ---- commands --------------------------------------------------------------
    def _respond(self, kind, payload):
        r = [0] * 8
        if kind == "r2":                  # CID or CSD, bit 127 in the top half of RSP7, bit 0 in the bottom of RSP0
            n = int.from_bytes(payload, "big")
            for i in range(8):
                r[i] = (n >> (16 * i)) & 0xFFFF
        elif kind != "none":
            r[6], r[7] = payload & 0xFFFF, (payload >> 16) & 0xFFFF
        self.rsp = r

    def _command(self, word):
        idx, fmt = word & 0x3F, (word >> 9) & 3
        if self.card is None:
            self.st0 |= ST0_RSPDNE if fmt == 0 else ST0_TOUTRS
            return
        if idx in (17, 18) and self.slow_card is not None and self.regs.get(CLK, 0) & 0xFF == self.slow_card:
            self.st0 |= ST0_TOUTRS
            return
        res = self.card.command(idx, self.regs.get(ARG, 0))
        kind = res[0]
        if kind == "timeout":
            self.st0 |= ST0_RSPDNE if fmt == 0 else ST0_TOUTRS    # a command with no answer to wait for is done once sent
            return
        if idx == 12:                      # stop: whatever is still moving is dropped
            self.rx, self.tx, self.tx_lba, self.blocks_left, self.chunk = bytearray(), bytearray(), None, 0, False
        if kind == "none":
            self._respond("none", 0)
            self.st0 |= ST0_RSPDNE
        elif kind == "r2":
            self._respond(kind, res[1])
            self.st0 |= ST0_RSPDNE if fmt != 2 or crc7(res[1][:15]) == res[1][15] >> 1 else ST0_CRCRS
        elif kind in ("r1", "r3", "r6"):
            payload, ok = res[1], True
            if kind != "r3" and len(res) > 2:
                wire = res[2]                           # what came over the wire: it is the CRC7 that is compared
                payload = struct.unpack(">I", wire[1:5])[0]
                ok = fmt != 1 or crc7(wire[:5]) == wire[5] >> 1
            self._respond(kind, payload)
            self.st0 |= (ST0_RSPDNE | (ST0_BSYDNE if (word >> 8) & 1 else 0)) if ok else ST0_CRCRS
        elif kind in ("read", "write"):
            lba, multi = res[1], res[2]
            self._respond("r1", self.card.r1())
            self.blocks_left = (self.regs.get(NBLK, 1) or 1) if multi else 1
            if kind == "read":
                self.card.state = "data"
                if lba is None:                         # a byte address that is no whole block: the card sends nothing
                    self.st0 |= ST0_TOUTRD
                    self.blocks_left = 0
                else:
                    self._load(lba)
            else:
                self.tx, self.tx_lba, self.chunk, self.tx_drop = bytearray(), lba or 0, True, lba is None
            self.st0 |= ST0_RSPDNE
