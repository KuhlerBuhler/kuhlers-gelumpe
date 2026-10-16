# SPDX-License-Identifier: GPL-2.0-only
"""The SD card slot of the emulated Electribe: an MMC controller and an SDHC card on an image.

The firmware talks to the AM180x MMC0 block (base 0x01C40000) by polling the
FIFO, with one interrupt line (16). There is no DMA. Registers and the command
sequence are the ones measured in docs/hintergrund/virtuelle-sd.md.
Not modelled: CRC (neither checked nor produced), SDSC byte addressing, write
protect, errors other than "no answer", and anything on a card larger than the
sizes tried there.
"""

import collections
import struct

SECTOR = 512
IRQ = 16                     # AINTC line the firmware enables for MMC0, handler 0xC0025BD0

CTL, CLK, ST0, ST1, IM = 0x00, 0x04, 0x08, 0x0C, 0x10
BLEN, NBLK, DRR, DXR, CMD, ARG = 0x1C, 0x20, 0x28, 0x2C, 0x30, 0x34
RSP01, RSP67, DRSP = 0x38, 0x44, 0x48

ST0_DATDNE, ST0_BSYDNE, ST0_RSPDNE, ST0_TOUTRS = 0x1, 0x2, 0x4, 0x10
ST0_DXRDY, ST0_DRRDY = 0x200, 0x400

STATES = {"idle": 0, "ready": 1, "ident": 2, "stby": 3, "tran": 4, "data": 5, "rcv": 6}


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
    c = 0
    for b in data:
        for i in range(8):
            c = ((c << 1) ^ 0x09) & 0xFF if ((c >> 7) ^ (b >> (7 - i))) & 1 else (c << 1) & 0xFF
    return c >> 1


class SDCard:
    """The card at command level: an SDHC card with 512-byte blocks addressed by block number."""

    def __init__(self, medium):
        self.medium = medium
        self.sectors_read = self.sectors_written = 0
        self.commands = collections.Counter()
        self.reset()

    def reset(self):
        self.state, self.rca, self.app, self.acmd41 = "idle", 0, False, 0

    def ocr(self):
        return 0x40FF8000 | (0x80000000 if self.acmd41 >= 2 else 0)

    def cid(self):
        b = bytearray(16)
        b[0], b[1:3], b[3:8], b[8] = 0x03, b"SD", b"EMUSD", 0x10
        b[9:13], b[13], b[14] = struct.pack(">I", 0x12345678), 0x01, 0x5A
        b[15] = (crc7(b[:15]) << 1) | 1
        return bytes(b)

    def csd(self):
        """CSD version 2.0: capacity in units of 512 KiB."""
        b = bytearray(16)
        b[0:6] = bytes([0x40, 0x0E, 0x00, 0x32, 0x5B, 0x59])
        c_size = self.medium.sectors // 1024 - 1
        b[7], b[8], b[9] = (c_size >> 16) & 0x3F, (c_size >> 8) & 0xFF, c_size & 0xFF
        b[10:15] = bytes([0x7F, 0x80, 0x0A, 0x40, 0])
        b[15] = (crc7(b[:15]) << 1) | 1
        return bytes(b)

    def status(self):
        return (STATES[self.state] << 9) | 0x100 | (0x20 if self.app else 0)

    def command(self, idx, arg):
        """One command: (kind, ...). Kinds: none, r1, r2, r3, r6, read, write, timeout."""
        self.commands[idx] += 1
        app, self.app = self.app, False
        if idx == 0:
            self.reset()
            return ("none", 0)
        if idx == 8:
            return ("r1", arg & 0xFFF)                    # R7: the check pattern echoed
        if idx == 55:
            self.app = True
            return ("r1", self.status() | 0x20)
        if app and idx == 41:
            self.acmd41 += 1
            if self.acmd41 >= 2:
                self.state = "ready"
            return ("r3", self.ocr())
        if app and idx == 6:
            return ("r1", self.status())                  # bus width, nothing to do for the model
        if idx == 2:
            self.state = "ident"
            return ("r2", self.cid())
        if idx == 3:
            self.rca, self.state = 0x1234, "stby"
            return ("r6", (self.rca << 16) | (self.status() & 0xFFFF))
        if idx == 9:
            return ("r2", self.csd())
        if idx == 10:
            return ("r2", self.cid())
        if idx == 7:
            self.state = "tran" if (arg >> 16) == self.rca else "stby"
            return ("r1", self.status())
        if idx == 12:
            self.state = "tran"
            return ("r1", self.status())
        if idx == 16:
            return ("r1", self.status())
        if idx in (17, 18, 24, 25):
            if arg >= self.medium.sectors:
                return ("timeout",)
            return ("read" if idx in (17, 18) else "write", arg, idx in (18, 25))
        return ("timeout",)


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
        self.cur_lba = 0
        self.blocks_left = 0

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
            self._flush()
            return
        self.regs[off] = v
        if off == CMD:
            self._command(v)

    def irq(self):
        """The interrupt line: asserted while an unmasked status bit is pending."""
        if self.card is None:
            return False
        pend = self.st0
        if self.rx:
            pend |= ST0_DRRDY
        if self.tx_lba is not None:
            pend |= ST0_DXRDY
        return bool(pend & self.regs.get(IM, 0))

    # ---- data phase ------------------------------------------------------------
    def _block(self):
        return self.regs.get(BLEN, SECTOR) or SECTOR

    def _load(self, lba):
        self.cur_lba = lba
        medium = self.card.medium
        self.rx = bytearray(medium.read(lba) if lba < medium.sectors else bytes(SECTOR))
        self.card.sectors_read += 1

    def _pop(self, size):
        if not self.rx:
            return 0
        n = 4 if size >= 4 else size
        chunk = self.rx[:n]
        del self.rx[:n]
        if not self.rx:
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
            self.card.medium.write(self.tx_lba, block)
            self.card.sectors_written += 1
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
        res = self.card.command(idx, self.regs.get(ARG, 0))
        kind = res[0]
        if kind == "timeout":
            self.st0 |= ST0_TOUTRS
            return
        if idx == 12:                      # stop: whatever is still moving is dropped
            self.rx, self.tx, self.tx_lba, self.blocks_left = bytearray(), bytearray(), None, 0
        if kind == "none":
            self._respond("none", 0)
            self.st0 |= ST0_RSPDNE
        elif kind == "r2":
            self._respond(kind, res[1])
            self.st0 |= ST0_RSPDNE
        elif kind in ("r1", "r3", "r6"):
            self._respond(kind, res[1])
            self.st0 |= ST0_RSPDNE | (ST0_BSYDNE if (word >> 8) & 1 else 0)
        elif kind in ("read", "write"):
            lba, multi = res[1], res[2]
            self._respond("r1", self.card.status())
            self.blocks_left = (self.regs.get(NBLK, 1) or 1) if multi else 1
            if kind == "read":
                self.card.state = "data"
                self._load(lba)
            else:
                self.tx, self.tx_lba = bytearray(), lba
            self.st0 |= ST0_RSPDNE
