# SPDX-License-Identifier: GPL-2.0-only
"""Boot the Sampler firmware on an emulated AM180x and watch its display.

Only the ARM side runs. Peripherals are modelled as far as the firmware needs
them to reach the main screen; the DSP is a stand-in that answers with fixed
values. Every device fact below is from docs/messungen/2026-10-08-emulator-boot.md.
"""

import argparse
import collections
import ctypes
import hashlib
import json
import math
import pickle
import struct
import sys
import types
import zlib
from pathlib import Path

import factorybank
from firmware import HARDWARE_MARKS, SAMPLER_USER_MARK, identify
from sdcard import IRQ as MMC_IRQ, MMCController

NS_PER_INSN = 5            # assumed: roughly 200 million instructions per second
SLICE = 20_000             # upper bound of instructions between interrupt checks
MMC_IRQ_NS = 100_000        # the card interrupt is looked at once per this much device time, as the 20000-instruction slices did
ISR_STEP = 256             # slice length while an interrupt handler runs, so the next pending one follows at once

AINTC = 0xFFFEE000
GPIO = 0x01E26000
MMC = 0x01C40000
SPI0, SPI1 = 0x01C41000, 0x01F0E000
UART0, UART1, UART2 = 0x01C42000, 0x01D0C000, 0x01D0D000
EV_UART = {UART0: 25, UART1: 53, UART2: 61}
# Time one byte (10 bits) takes on the wire: panel at 115200 baud, MIDI at 31250.
BYTE_NS = {UART0: 86_800, UART1: 320_000, UART2: 86_800}
TIMERS = {0x01C20000: (24e6, 21), 0x01C21000: (24e6, 23),
          0x01F0C000: (150e6, 68), 0x01F0D000: (150e6, 96)}
TIMER_COUNTERS = {t + off: (t, hz, off == 0x14) for t, (hz, _) in TIMERS.items() for off in (0x10, 0x14)}
CFGCHIP2 = 0x01C14184
DSP_DATA, DSP_CTRL = 0x60000000, 0x60000002
DSP_SYNC = 0x2C            # a one-word write to the control port that no transfer starts with (docs/messungen/2026-10-14-stock-blech.md)
# Where the firmware routines and variables below sit is a fact of the build, looked up when the image is loaded
# (firmware.py: Profile). What the model does for each of them:
#   assert_handler  the assertion handler; the run ends in front of it and the message is kept
#   flash_read      driver read(dev, address, length, destination), 1 on success; the bytes are copied in one go
#   dsp_upload      boot(dsp, image, length): 271008 bytes over SPI1, 1 on success; the DSP is a stand-in
#   tx_full         UART send loop: the byte did not fit the queue, retried up to 100000 times; ends the slice
#   screens         pointer to the screen manager: +0x2C number of the current screen
FLASH_SIZE = 0x1000000
FIRMWARE_AT = 0x20000      # flash offset of the firmware image (SOFTWARE UPDATE writes [0x20000, 0x220000), measured 2026-10-10)
USER_MARK = 0x220000       # flash offset the firmware checks at start; without the mark it offers the update
MAIN_SCREEN = 1            # the screen the firmware shows once it has started
LOADING_SCREEN = 46        # Korg's own build shows this screen while it loads the user data; 0 for a moment before the main screen
LOADING_SCREENS = {"stock": LOADING_SCREEN, "synth": 38}
LOADING_SCREEN_BY_S = 0.3  # ... and it is up by then (measured: 0.07 s)
STOCK_BOOT_LIMIT_S = 12.0  # ... which takes about 6 s with a used flash (finish_boot)
PANEL_VERSION = 0x96       # what the panel reports; the panel is hardware, so this is not read out of the firmware under test

# What a snapshot keeps (Machine.snapshot): the RAM the model maps, read in chunks, kept per non-zero page.
SNAP_REGIONS = ((0xC0000000, 0x08000000), (0xFFFF0000, 0x10000), (0x80000000, 0x20000), (0, 0x1000))
SNAP_SKIP = frozenset(("A", "uc", "_reg_read", "_uch", "_reg_buf", "_reg_ref", "profile", "ENTRIES"))     # the library's handles and the build's places, made again by __init__
SNAP_CHUNK = 0x100000
PAGE = 0x1000
ZERO_PAGE = bytes(PAGE)
ZERO_CHUNK = bytes(SNAP_CHUNK)


def card_in_memory(card):
    """A card whose image is a bytearray in memory (sdcard.MemoryMedium), which a snapshot can hold."""
    from sdcard import MemoryMedium
    return type(card.medium) is MemoryMedium and isinstance(card.medium.data, bytearray)


def _card_pages(data, base):
    """The pages of a card image that differ from `base` (an empty card without one), as an index and the pages."""
    index, pages = [], bytearray()
    for chunk in range(0, len(data), SNAP_CHUNK):
        have = bytes(data[chunk:chunk + SNAP_CHUNK])
        if have == (bytes(base[chunk:chunk + SNAP_CHUNK]) if base is not None else ZERO_CHUNK[:len(have)]):
            continue                    # a whole chunk at once; only a changed one is looked at page by page
        for off in range(0, len(have), PAGE):
            page = have[off:off + PAGE]
            if page != (bytes(base[chunk + off:chunk + off + PAGE]) if base is not None else ZERO_PAGE[:len(page)]):
                index.append(chunk + off)
                pages += page
    return {"index": index, "pages": zlib.compress(bytes(pages), 1)}


def _put(owner, name, value):
    """owner[name] = value, but a dict, list, set, deque or bytearray that is already there is filled in place."""
    held = owner.get(name)
    if type(held) is type(value) and isinstance(held, (dict, set)):
        held.clear()
        held.update(value)
    elif type(held) is type(value) and isinstance(held, (list, bytearray)):
        held[:] = value
    elif type(held) is type(value) and isinstance(held, collections.deque) and held.maxlen == value.maxlen:
        held.clear()
        held.extend(value)
    else:
        owner[name] = value

BOOT_STEPS = (1.0, 2.0, 3.0)   # device times a run can start from a kept boot (bootcache.py)

PANEL_ID = bytes.fromhex("0000000047454c55")   # made up; any value but 0 and all ones
INPUT_LEVEL = 0xFF9030EC  # DSP: audio input level, upper word drawn as 0-5 bars, CLIP above 0x5A7EF811


def pin(bank, number):
    """GPIO bank and pin as (register pair, bit mask)."""
    return bank // 2, 1 << ((bank % 2) * 16 + number)


def blank_flash(mark=SAMPLER_USER_MARK):
    """An erased flash with the user-data mark at 0x220000 and, for the Sampler, a factory sample bank of our own
    (factorybank.py) at 0x800000. The firmware boots from it with empty patterns and no samples, and fills in what
    it needs; the factory bank is what gives each factory slot its own entry, so a sample for one of them can be
    loaded. The synth has no sample slots and keeps its own PCM flash (synth_pcm_flash.py), so it gets no bank."""
    mem = bytearray(b"\xff" * FLASH_SIZE)
    mem[USER_MARK:USER_MARK + 16] = mark + bytes(16 - len(mark))
    if mark == SAMPLER_USER_MARK:
        bank = factorybank.build()
        mem[factorybank.BASE:factorybank.BASE + len(bank)] = bank
    return mem


def hardware_of_flash(flash):
    """"red" or "blue" by the user-data mark of a flash, None when it has neither (erased, or a mark we do not know)."""
    mark = bytes(flash[USER_MARK:USER_MARK + 12]) if flash else b""
    return next((name for name, m in HARDWARE_MARKS.items() if m == mark), None)


def hardware_flash(hardware):
    """A blank flash of the red or the blue hardware."""
    return blank_flash(HARDWARE_MARKS[hardware])


def blank_flash_like(flash):
    """A blank flash of the hardware `flash` belongs to; None (the build decides) for no flash or an unknown mark."""
    hardware = hardware_of_flash(flash)
    return hardware_flash(hardware) if hardware else None


class SysexReader:
    """Complete SysEx messages out of a MIDI byte stream. Realtime bytes and
    channel messages (notes from the pads, clock) are dropped."""

    def __init__(self):
        self.buf = None

    def feed(self, data):
        out = []
        for b in data:
            if b >= 0xF8:
                continue
            if b == 0xF0:
                self.buf = bytearray([b])
            elif self.buf is not None:
                if b == 0xF7:
                    out.append(bytes(self.buf + b"\xf7"))
                    self.buf = None
                elif b & 0x80:
                    self.buf = None
                else:
                    self.buf.append(b)
        return out


class Flash:
    """Serial NOR flash on SPI1, selected while GPIO 2.14 is low."""

    def __init__(self, image, mark=SAMPLER_USER_MARK):
        self.mem = bytearray(image) if image else blank_flash(mark)
        self.selected = False
        self.cmd = None
        self.buf = []
        self.addr = 0
        self.wel = False
        self.dirty = False          # erased or programmed since the host last saved it
        self.commands = collections.Counter()

    def select(self, on):
        self.selected = on
        self.cmd, self.buf = None, []

    def byte(self, b):
        if self.cmd is None:
            self.cmd = b
            self.commands[b] += 1
            if b == 0x06: self.wel = True
            if b == 0x04: self.wel = False
            return 0xFF
        self.buf.append(b)
        c, n = self.cmd, len(self.buf)
        if c == 0x05: return 0x02 if self.wel else 0x00
        if c == 0x9F: return (0x01, 0x20, 0x18)[min(n - 1, 2)]
        if n == 3:
            self.addr = int.from_bytes(bytes(self.buf), "big")
            if self.wel and c == 0x20: self.erase(0x1000)
            if self.wel and c == 0x52: self.erase(0x8000)
            if self.wel and c == 0xD8: self.erase(0x10000)
            return 0xFF
        if n > 3 and c == 0x03:
            v = self.mem[self.addr]
            self.addr = (self.addr + 1) % FLASH_SIZE
            return v
        if n > 3 and c == 0x02 and self.wel:
            self.mem[self.addr] &= b
            self.dirty = True
            self.addr = (self.addr & ~0xFF) | ((self.addr + 1) & 0xFF)
        return 0xFF

    def erase(self, size):
        start = self.addr & ~(size - 1)
        self.mem[start:start + size] = b"\xff" * size
        self.dirty = True
        self.wel = False


class Machine:
    def __init__(self, payload, flash=None, profile=None):
        """`profile` is the build's Profile (firmware.py); without it the payload is looked at, and a payload that
        is not a Sampler 2.02 build the emulator knows raises firmware.ProfileError."""
        self.profile = profile or identify(payload)
        p = self.profile
        self.ENTRIES = (p.assert_handler, p.flash_read, p.dsp_upload, p.tx_full)
        import unicorn
        from unicorn import arm_const

        if unicorn.__version__ != "2.1.4":
            raise RuntimeError("Install unicorn==2.1.4")
        self.A = arm_const
        uc = self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        from unicorn.unicorn_py3 import unicorn as _lib
        self._reg_read, self._uch = _lib.uclib.uc_reg_read, uc._uch
        self._reg_buf = ctypes.c_uint32()
        self._reg_ref = ctypes.byref(self._reg_buf)
        uc.ctl_set_cpu_model(arm_const.UC_CPU_ARM_926)
        uc.mem_map(0xC0000000, 0x08000000, unicorn.UC_PROT_ALL)
        uc.mem_write(0xC0000000, payload)
        uc.mem_map(0xFFFF0000, 0x10000, unicorn.UC_PROT_ALL)
        uc.mem_map(0x80000000, 0x20000, unicorn.UC_PROT_ALL)
        # Assumption: the bootloader leaves the image's vector page visible at 0,
        # where the firmware reads its exception vectors.
        uc.mem_map(0, 0x1000, unicorn.UC_PROT_ALL)
        uc.mem_write(0, payload[:0x1000])

        self.regs = {}
        self.recent = collections.deque(maxlen=3000)
        self.time_ns = 0
        self.insns = 0
        self.asserts = []
        self.raw, self.enabled, self.cmr = set(), set(), {}
        self._tcfg, self._tper = {}, {}      # timer configuration as read from regs; see _wr
        self.timer_last = {}
        self.deadline, self.poll_stop, self.tx_idle = math.inf, False, False
        # One byte shifts while the next waits in the TX buffer; SPIBUF holds one result.
        self.spi = {b: {"wire": collections.deque(), "buf": 0, "full": False} for b in (SPI0, SPI1)}
        self.uart = {b: {"tx": bytearray(), "rx": collections.deque(), "thre": False, "busy": 0,
                         "wire": collections.deque(), "arrive": 0} for b in EV_UART}
        self.gpio = {}
        self.handshake = 0
        # Pins driven from outside: power button released, no SD card.
        self.inputs = {pin(7, 15): 1, pin(4, 1): 1}
        self.adapter = False       # panel message 7: plug symbol, power switch ignored; meaning open
        self.held = 0              # buttons held at power-on, answer to 0x91; bit n = button n is assumed
        self.panel_version = PANEL_VERSION
        self.powered = True        # false once the firmware lets go of the power hold
        self.report_power = False
        self.flash = Flash(flash, p.user_mark)
        self.image_size = len(payload)     # restore() clears what the payload wrote
        self.image_sha = hashlib.sha256(payload).digest()
        # The device runs what its flash holds there, so the flash holds the image this machine runs; an
        # update then shows as a change of that region, and a restart can boot from it (server.py).
        self.flash.mem[FIRMWARE_AT:FIRMWARE_AT + len(payload)] = payload
        self.sysex, self.midi_seen = SysexReader(), 0
        self.tx_waiting = False
        self.mmc = MMCController()  # no card until insert_card()
        self.mmc_cell = -1         # the MMC_IRQ_NS interval in which the card interrupt was last looked at
        self.dsp_ctl, self.dsp_xfer = [], None
        self.dsp_uploads = []      # device time in ms of every DSP program upload, i.e. every DSP boot
        self.dsp_mem = {INPUT_LEVEL: 0, INPUT_LEVEL + 2: 0}     # nothing plugged into the input
        self.leds, self.panel_log = {}, []
        self.panel_count = 0       # messages to the panel; the running firmware sends LEDs ~265 per second
        self.fb = [[0] * 128 for _ in range(8)]
        self.lcd_page = self.lcd_col = 0
        self.lcd_reverse_sent = 0  # how many 0xA6 or 0xA7 the controller has been sent
        self.lcd_reverse = False   # 0xA7 sent: the controller shows every pixel the other way round, 0xA6 normal
        self.lcd_on = True         # 0xAE switches the controller's display off (all pixels clear, RAM kept), 0xAF on again
        self.frames = 0
        self.screens = 0           # display changes, sampled every 100 ms of device time
        self._seen = None
        self.booted = False        # the main screen has been shown; looked at every 100 ms of device time and at the end of a run_until
        self.boot_ms = None        # device time of that look, in ms
        self.midi_dropped = 0      # messages that came before the device had started

        for base, size in [(0x01C00000, 0x400000), (AINTC, 0x2000), (DSP_DATA, 0x10000),
                           (0x62000000, 0x10000), (0x64000000, 0x10000), (0x66000000, 0x10000),
                           (0x68000000, 0x8000), (0xB0000000, 0x8000), (0x11800000, 0x100000)]:
            self._mmio_map(base, size)
        # Four firmware entry points are handled here, not by code hooks: a code hook with a Python
        # callback makes every instruction of the run cost about 20 ns more (measured, 2026-10-13).
        # An exit address costs nothing while the code runs; the run stops in front of it.
        uc.ctl_exits_enabled(True)
        uc.ctl_set_exits(list(self.ENTRIES))

    def reg(self, reg_id):
        """A 32-bit register, read straight through the library: Unicorn's reg_read costs about
        1.7 us in Python and the slice loop reads four registers per slice."""
        self._reg_read(self._uch, reg_id, self._reg_ref)
        return self._reg_buf.value

    def _mmio_map(self, base, size):
        """uc.mmio_map with the one Python frame this model needs per access. Unicorn's own wrapper
        adds two, and the firmware makes millions of accesses a second while it polls."""
        from unicorn.unicorn_py3 import unicorn as u
        uc, rd, wr = self.uc, self._rd, self._wr

        def guard(error):
            if uc._hook_exception is None:
                uc._hook_exception = error
            uc.emu_stop()

        def read(handle, off, size, key):
            try:
                return rd(uc, off, size, base)
            except BaseException as error:
                guard(error)
                return 0

        def write(handle, off, size, value, key):
            try:
                wr(uc, off, size, value, base)
            except BaseException as error:
                guard(error)

        rf, wf = u.MMIO_READ_CFUNC(read), u.MMIO_WRITE_CFUNC(write)
        status = u.uclib.uc_mmio_map(uc._uch, base, size, rf, 0, wf, 0)
        if status:
            raise u.UcError(status)
        uc._mmio_callbacks[(base, base + size)] = (rf, wf)       # unicorn keeps no reference of its own

    def insert_card(self, card):
        """Put an SDCard (sdcard.py) into the slot; GPIO 4.1 goes low. Call before running."""
        self.mmc.card = card
        self.inputs[pin(4, 1)] = 0

    def eject_card(self):
        self.mmc.card = None
        self.inputs[pin(4, 1)] = 1

    # ---- snapshots ---------------------------------------------------------
    def snapshot(self, card_base=None):
        """Everything this machine has built up so far, as bytes: the CPU, the RAM pages that are not
        zero, the model's own state and a card in the slot. `from_snapshot` gives a machine that goes on exactly
        as this one would. A card is kept when it is an image in memory (sdcard.MemoryMedium), as its pages that
        differ from `card_base` (the image as it was when the machine started, bootcache.py) or, without it, from
        an empty card. A card on a folder of the host (cardstore.py) is the host's and cannot be kept. Without
        instance methods that someone wrapped around the model (their owner puts them back after restoring)."""
        card = self.mmc.card
        if card is not None and not card_in_memory(card):
            raise ValueError("a card on a folder of the host cannot be snapshotted")
        image = card.medium.data if card is not None else None
        if card is not None:
            card.medium.data = b""              # its pages are kept next to the RAM's
        try:
            state = {k: v for k, v in self.__dict__.items()
                     if k not in SNAP_SKIP and not isinstance(v, (types.FunctionType, types.MethodType))}
            flash = state.pop("flash")
            state["flash"] = {k: v for k, v in flash.__dict__.items() if k != "mem"}
            pages = bytearray()
            index = []
            for base, size in SNAP_REGIONS:
                for chunk in range(0, size, SNAP_CHUNK):
                    data = bytes(self.uc.mem_read(base + chunk, min(SNAP_CHUNK, size - chunk)))
                    if data == ZERO_CHUNK[:len(data)]:
                        continue
                    for off in range(0, len(data), PAGE):
                        page = data[off:off + PAGE]
                        if page != ZERO_PAGE:
                            index.append(base + chunk + off)
                            pages += page
            blob = {
                "ctx": self.uc.context_save(), "state": state,
                "flash_sha": hashlib.sha256(flash.mem).digest(),
                "flash_mem": zlib.compress(bytes(flash.mem), 1) if flash.dirty else None,
                "index": index, "pages": zlib.compress(bytes(pages), 1),
                "card": None if card is None else {"size": len(image), **_card_pages(image, card_base)},
            }
            return pickle.dumps(blob, pickle.HIGHEST_PROTOCOL)
        finally:
            if card is not None:
                card.medium.data = image

    @classmethod
    def from_snapshot(cls, snap, payload, flash=None):
        """A machine in the state `snapshot` was taken in. `payload` and `flash` are what the original was
        made with (the snapshot holds only what changed since); a kept card comes into the slot as well, from an
        empty card (a snapshot with `card_base` needs that card: `restore`)."""
        m = cls(payload, flash)
        card = pickle.loads(snap).get("card")
        if card is not None:
            from sdcard import MemoryMedium, SDCard
            m.insert_card(SDCard(MemoryMedium(bytearray(card["size"]))))
        m.restore(snap)
        return m

    def restore(self, snap):
        """Put this machine into the state `snapshot` was taken in. It has to be made with the same payload and
        flash and not have run, and a card in its slot has to be the image the snapshot's `card_base` was (an empty
        one without). The objects the caller may hold stay the same: the machine, its flash, the card and its
        image, and the dicts, lists and sets of the model."""
        blob = pickle.loads(snap)
        uc = self.uc
        if blob["flash_mem"] is not None:
            self.flash.mem[:] = zlib.decompress(blob["flash_mem"])
        elif hashlib.sha256(self.flash.mem).digest() != blob["flash_sha"]:
            raise ValueError("the snapshot was taken with another flash")
        held_card = self.mmc.card
        if (blob.get("card") is None) != (held_card is None):
            raise ValueError("the snapshot and this machine differ in the card in the slot")
        if held_card is not None and (not card_in_memory(held_card) or len(held_card.medium.data) != blob["card"]["size"]):
            raise ValueError("the card in the slot is not the snapshot's")
        uc.mem_write(0xC0000000, bytes(self.image_size))  # what the machine was built with and the RAM then changed
        uc.mem_write(0, bytes(0x1000))
        pages = zlib.decompress(blob["pages"])
        for i, at in enumerate(blob["index"]):
            uc.mem_write(at, pages[i * PAGE:(i + 1) * PAGE])
        uc.context_restore(blob["ctx"])
        state = blob["state"]
        flash_state = state.pop("flash")
        mmc = state.pop("mmc")
        for k, v in state.items():
            _put(self.__dict__, k, v)
        self.flash.__dict__.update(flash_state)
        kept_card, mmc.card = mmc.card, held_card
        held_mmc = self.mmc
        held_mmc.__dict__.update(mmc.__dict__)
        if held_card is not None:
            medium, data = held_card.medium, held_card.medium.data
            held_card.__dict__.update({**kept_card.__dict__, "medium": medium})
            medium.__dict__.update({**kept_card.medium.__dict__, "data": data})
            changed = zlib.decompress(blob["card"]["pages"])
            for i, at in enumerate(blob["card"]["index"]):
                data[at:at + PAGE] = changed[i * PAGE:(i + 1) * PAGE]

    # ---- register access ---------------------------------------------------
    def _rd(self, uc, off, size, base):
        a = base + off
        self.recent.append(a)
        timer = TIMER_COUNTERS.get(a)
        if timer:                                    # the hottest read: firmware delay loops
            self.time_ns += 200                      # poll_time()
            if self.time_ns >= self.deadline:
                self.poll_stop = True
                uc.emu_stop()
            return self.timer_count(*timer) & 0xFFFFFFFF
        if MMC <= a < MMC + 0x100:
            return self.mmc.read(a - MMC, size) & 0xFFFFFFFF
        v = self.read(a)
        return (self.regs.get(a, 0) if v is None else v) & 0xFFFFFFFF

    def _wr(self, uc, off, size, value, base):
        a = base + off
        self.recent.append(a)
        if MMC <= a < MMC + 0x100:
            self.mmc.write(a - MMC, value, size)
        elif not self.write(a, value):
            self.regs[a] = value
            if a & ~0xFFF in TIMERS:             # the timers' configuration is read far more often than it is written
                self._tcfg.clear()
                self._tper.clear()

    def read(self, a):
        timer = TIMER_COUNTERS.get(a)
        if timer:
            self.poll_time()
            return self.timer_count(*timer)
        if a == DSP_CTRL: return 0x85                # assumption: DSP always ready; bit 2 is the one Korg's own build waits for before a host-port write
        if a == DSP_DATA: return self.dsp_read()
        if a in (SPI0 + 0x40, SPI1 + 0x40):          # SPIBUF, RXEMPTY once read
            s = self.spi[a - 0x40]
            self.spi_settle(s)
            if s["full"]:
                s["full"] = False
                return s["buf"]
            return s["buf"] | 0x80000000
        if a in (SPI0 + 0x10, SPI1 + 0x10):          # SPIFLG
            s = self.spi[a - 0x10]
            self.spi_settle(s)
            return 0x200 | (0x100 if s["full"] else 0)
        base = a & ~0xFF
        if base in self.uart:
            u, reg = self.uart[base], a & 0xFF
            if reg == 0x00: return u["rx"].popleft() if u["rx"] else 0
            if reg == 0x14: return (0 if u["busy"] else 0x60) | (1 if u["rx"] else 0)
            if reg == 0x08:
                ier = self.regs.get(base + 0x04, 0)
                fifo = 0xC0 if self.regs.get(base + 0x08, 0) & 1 else 0
                if ier & 1 and u["rx"]: return fifo | 0x04
                if ier & 2 and u["thre"]:
                    u["thre"] = False
                    return fifo | 0x02
                return fifo | 0x01
        if GPIO <= a < GPIO + 0x100:
            return self.gpio_read(a - GPIO)
        if a == 0x01E00004: return self.regs.get(a, 0) & ~1          # USB reset clears itself
        if a == CFGCHIP2: return self.regs.get(a, 0) | 0x20000        # USB PHY clock good
        if a == 0x01E00460:
            # OTGMODE 2 in CFGCHIP2 forces device mode; the chip then reports a
            # session by itself. No cable is modelled.
            forced = (self.regs.get(CFGCHIP2, 0) >> 13) & 3 == 2
            return self.regs.get(a, 0) | (1 if forced else 0)
        if a in (AINTC + 0x900, AINTC + 0x904):     # HIPIR1 / HIPIR2
            return self.highest(fiq=a == AINTC + 0x900)
        return None

    def write(self, a, v):
        if a == DSP_CTRL:
            if not self.dsp_ctl and v & 0xFFFF == DSP_SYNC:      # Korg's build writes a lone sync word between frames
                return True
            self.dsp_ctl.append(v & 0xFFFF)
            if len(self.dsp_ctl) == 7:
                cmd, lo, hi, count = self.dsp_ctl[:4]
                self.dsp_xfer = [cmd, (hi << 16) | lo, count]
                self.dsp_ctl = []
            return True
        if a == DSP_DATA:
            if self.dsp_xfer and self.dsp_xfer[2] > 0:
                self.dsp_xfer[1] += 2
                self.dsp_xfer[2] -= 1
            return True
        if a in (SPI0 + 0x38, SPI0 + 0x3C, SPI1 + 0x38, SPI1 + 0x3C):
            base = a & ~0xFF
            s = self.spi[base]
            if base == SPI0:
                self.lcd(v & 0xFF)
            if len(s["wire"]) >= 2:
                s["buf"], s["full"] = s["wire"].popleft(), True
            s["wire"].append(self.flash.byte(v & 0xFF) if base == SPI1 and self.flash.selected else 0)
            return True
        base = a & ~0xFF
        if base in self.uart:
            u, reg = self.uart[base], a & 0xFF
            if reg == 0x00:
                # The holding register empties only when the byte is out; the
                # interrupt handler gives up after eight rounds in one go.
                u["tx"].append(v & 0xFF)
                u["thre"], u["busy"] = False, self.time_ns + BYTE_NS[base]
                self.deadline = min(self.deadline, u["busy"])
                if base == UART0 and len(u["tx"]) % 5 == 0:
                    self.panel(bytes(u["tx"][-5:]))
                return True
            if reg == 0x04:
                if v & 2 and not self.regs.get(a, 0) & 2 and not u["busy"]: u["thre"] = True
                self.regs[a] = v
                return True
        if GPIO <= a < GPIO + 0x100:
            self.regs[a] = v
            self.gpio_write(a - GPIO, v)
            return True
        if AINTC <= a < AINTC + 0x2000:
            off = a - AINTC
            if off == 0x20: self.raw.add(v & 0x7F)
            elif off == 0x24: self.raw.discard(v & 0x7F)
            elif off == 0x28: self.enabled.add(v & 0x7F)
            elif off == 0x2C: self.enabled.discard(v & 0x7F)
            elif 0x200 <= off < 0x210: self._bits(self.raw, off - 0x200, v, True)
            elif 0x280 <= off < 0x290: self._bits(self.raw, off - 0x280, v, False)
            elif 0x300 <= off < 0x310: self._bits(self.enabled, off - 0x300, v, True)
            elif 0x380 <= off < 0x390: self._bits(self.enabled, off - 0x380, v, False)
            elif 0x400 <= off < 0x500:
                for i in range(4): self.cmr[off - 0x400 + i] = (v >> (8 * i)) & 0xFF
            self.regs[a] = v
            return True
        return False

    @staticmethod
    def _bits(target, word_off, v, add):
        for i in range(32):
            if v >> i & 1:
                (target.add if add else target.discard)(word_off * 8 + i)

    def spi_settle(self, s):
        # The SPI driver writes the next byte before it collects the previous one.
        # Each poll lets the oldest byte on the wire finish into SPIBUF.
        if s["wire"]:
            s["buf"], s["full"] = s["wire"].popleft(), True

    # ---- GPIO ----------------------------------------------------------------
    def gpio_read(self, off):
        if off < 0x10: return self.regs.get(GPIO + off, 0)
        pair, reg = divmod(off - 0x10, 0x28)
        w = self.gpio.get(pair, 0)
        if reg == 0x04: return w
        if reg == 0x10:
            for (p, bit), level in self.inputs.items():
                if p == pair: w = (w | bit) if level else (w & ~bit)
            if pair == 3:                # GPIO 6.1, DSP handshake: toggles (assumption)
                self.handshake ^= 2
                w = (w & ~2) | self.handshake
            return w
        return self.regs.get(GPIO + off, 0)

    def gpio_write(self, off, v):
        if off < 0x10: return
        pair, reg = divmod(off - 0x10, 0x28)
        old = w = self.gpio.get(pair, 0)
        if reg == 0x04: w = v
        elif reg == 0x08: w |= v
        elif reg == 0x0C: w &= ~v
        self.gpio[pair] = w & 0xFFFFFFFF
        if pair == 1 and (old ^ w) & 0x4000:        # GPIO 2.14: flash chip select
            self.flash.select(not w & 0x4000)
        hold = pin(7, 11)[1]
        if pair == 3 and old & hold and not w & hold:   # GPIO 7.11: power hold let go
            self.powered = False
            self.fb = [[0] * 128 for _ in range(8)]
            self.lcd_reverse = False
            self.lcd_on = True
            self.uc.emu_stop()

    def gpio_out(self, bank, number):
        p, bit = pin(bank, number)
        return 1 if self.gpio.get(p, 0) & bit else 0

    # ---- DSP host port -------------------------------------------------------
    def dsp_read(self):
        # Transfers start with 7 control words [0xA9 read | 0xAB write, address low,
        # address high, count of 16-bit words, 2, 0, 0]. Unmodelled words read 0,
        # which leaves bit 31 of the DSP outboxes clear, so the CPU stops waiting.
        x = self.dsp_xfer
        if not x or x[2] <= 0: return 0
        addr = x[1]
        x[1] += 2
        x[2] -= 1
        return self.dsp_mem.get(addr, 0)

    # ---- panel controller: UART0, 5-byte messages ----------------------------
    def panel(self, msg):
        self.panel_count += 1
        rx = self.uart[UART0]["wire"]
        if msg[0] == 0x80:
            rx.extend(bytes([0x80, 0, 0, 0, self.panel_version]))
            self.report_power = True
        elif msg[0] == 0x91:
            # Big-endian words; 0x91 carries buttons 0x00-0x1F, 0x92 the rest (0xC0028040).
            rx.extend(b"\x91" + (self.held & 0xFFFFFFFF).to_bytes(4, "big")
                      + b"\x92" + (self.held >> 32).to_bytes(4, "big"))
        elif msg[0] == 0x90:
            # The panel's 64-bit identity, low word in 0xA0, high in 0xA1. With an
            # empty record at flash 0x7EF000 the firmware stores this one there.
            rx.extend(bytes([0xA0]) + PANEL_ID[4:] + bytes([0xA1]) + PANEL_ID[:4])
        elif msg[0] == 0x00:
            self.leds[msg[1]] = msg[2]
        if self.report_power and msg[0] != 0x80:
            # The power source follows the version handshake. Boot asks twice;
            # only the application, the second time, takes it in.
            self.report_power = False
            self.send([0x07, 1 if self.adapter else 0, 0, 0, 0])
        self.panel_log.append(msg)

    def send(self, msg):
        """A 5-byte message from the panel, as if a control was used."""
        self.receive(UART0, msg)

    def receive(self, base, data):
        """Bytes coming in on a UART line; they arrive one byte time apart."""
        self.uart[base]["wire"].extend(bytes(data))

    def u32(self, addr):
        return struct.unpack("<I", bytes(self.uc.mem_read(addr, 4)))[0]

    def screen(self):
        """Number of the screen the firmware shows, None while there is no screen manager yet."""
        try:
            mgr = self.u32(self.profile.screens)
            return self.u32(mgr + 0x2C) if mgr else None
        except Exception:                # unmapped: not our firmware, or too early
            return None

    def midi(self, data):
        """A MIDI message into the DIN input. Returns False when it was dropped.

        Nothing can send MIDI to a device that has not started, so a message that comes before the main
        screen is dropped. The firmware does not take it: the receive interrupt before the MIDI handler
        exists ends in the assertion at MidiHandler.cpp line 85 (measured, MIDI at 40 ms of device time)."""
        if not self.booted:
            self.midi_dropped += 1
            return False
        self.receive(UART1, data)
        return True

    def midi_out(self):
        """SysEx messages the firmware sent on DIN out since the last call."""
        tx = self.uart[UART1]["tx"]
        new, self.midi_seen = bytes(tx[self.midi_seen:]), len(tx)
        return self.sysex.feed(new)

    def press(self, button, down=True):
        self.send([0x00, button, 1 if down else 0, 0, 0])

    # ---- display: SPI0, command or data by GPIO 8.1 --------------------------
    def lcd(self, b):
        if self.gpio_out(8, 1):
            if self.lcd_col < 128: self.fb[self.lcd_page][self.lcd_col] = b
            self.lcd_col += 1
        elif 0xB0 <= b <= 0xB7:
            self.lcd_page = b - 0xB0
            if self.lcd_page == 0: self.frames += 1
        elif 0x10 <= b <= 0x1F:
            self.lcd_col = (self.lcd_col & 0x0F) | ((b & 0x0F) << 4)
        elif b <= 0x0F:
            self.lcd_col = (self.lcd_col & 0xF0) | b
        elif b in (0xA6, 0xA7):
            self.lcd_reverse = b == 0xA7
            self.lcd_reverse_sent += 1
        elif b in (0xAE, 0xAF):
            self.lcd_on = b == 0xAF

    def shown(self):
        """The display as the panel shows it, page-major bytes with a set bit for a dark pixel: the controller RAM, or its
        complement after 0xA7 (reverse display); nothing after 0xAE (display off)."""
        if not self.lcd_on:
            return bytes(1024)
        flat = bytes(b for row in self.fb for b in row)
        return bytes(b ^ 0xFF for b in flat) if self.lcd_reverse else flat

    def png(self, path, scale=4):
        rows = b""
        for y in range(64):
            shown = self.shown()
            line = bytes(0 if (shown[(y // 8) * 128 + x] >> (y % 8)) & 1 else 255
                         for x in range(128) for _ in range(scale))
            rows += (b"\0" + line) * scale

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n"
                               + chunk(b"IHDR", struct.pack(">IIBBBBB", 128 * scale, 64 * scale, 8, 0, 0, 0, 0))
                               + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))

    # ---- interrupts ----------------------------------------------------------
    def highest(self, fiq=False):
        live = [i for i in self.raw & self.enabled if (self.cmr.get(i, 0) < 2) == fiq]
        return min(live, key=lambda i: (self.cmr.get(i, 0), i)) if live else 0x80000000

    def poll_time(self):
        """A polling loop lets time pass, but not past the next timer edge, UART byte or card answer."""
        self.time_ns += 200
        if self.time_ns >= self.deadline:
            self.poll_stop = True
            self.uc.emu_stop()

    def timer_count(self, base, hz, upper):
        """TIM12 (TIM34 when `upper`) as the device shows it: 0 while that half is in reset or not enabled, and
        for a timer the firmware sets to watchdog mode (TGCR timer mode 2: 0x01C21000, measured on the device,
        whose counter stays 0); else counting at hz from time 0, wrapping at PRD + 1 in continuous mode."""
        cfg = self._tcfg.get((base, upper))
        if cfg is None:
            tgcr, tcr = self.regs.get(base + 0x24, 0), self.regs.get(base + 0x20, 0)
            mode = 0 if (tgcr >> 2) & 3 == 2 or not tgcr >> upper & 1 else (tcr >> (22 if upper else 6)) & 3
            cfg = self._tcfg[(base, upper)] = (mode, self.regs.get(base + (0x1C if upper else 0x18), 0) or 0xFFFFFFFF)
        mode, prd = cfg
        if not mode:
            return 0
        ticks = int(self.time_ns * hz / 1e9)
        return ticks % (prd + 1) if mode == 2 else min(ticks, prd)

    def timer_period(self, base):
        """Period in ns of a timer that raises its interrupt (TINT12 enabled, continuous), else None."""
        try:
            return self._tper[base]
        except KeyError:
            pass
        period = None
        if self.regs.get(base + 0x44, 0) & 1 and (self.regs.get(base + 0x20, 0) >> 6) & 3 == 2:
            period = (self.regs.get(base + 0x18, 0) + 1) / TIMERS[base][0] * 1e9
        self._tper[base] = period
        return period

    def next_event(self):
        """Device time in ns of the next timer edge or UART byte, inf when none is pending."""
        at = [math.inf]
        for base in TIMERS:
            period = self.timer_period(base)
            if period is not None:
                at.append((int(self.time_ns // period) + 1) * period)
        for u in self.uart.values():
            if u["busy"]: at.append(u["busy"])
            if u["wire"]: at.append(u["arrive"])
        return min(at)

    def slice_length(self, in_isr):
        """Instructions to run next: at most SLICE, ending where the next timer edge or UART byte
        falls so that it happens at its own time, and short while a handler runs so that the next
        pending interrupt is taken when it returns, as the controller does, not one slice later."""
        self.deadline = self.next_event()
        left = self.deadline - self.time_ns
        return max(1, min(ISR_STEP if in_isr else SLICE, math.ceil(left / NS_PER_INSN) if left < math.inf else SLICE))

    def waiting(self, pc):
        """True when the slice ended in a wait: wait-for-interrupt (mcr p15, 0, Rd, c7, c0, 4) just
        executed, or the UART send loop gave up its slice."""
        if self.tx_idle:
            return True
        if pc < 4 or self.reg(self.A.UC_ARM_REG_CPSR) & 0x20:
            return False
        return int.from_bytes(self.uc.mem_read(pc - 4, 4), "little") & 0xFFFF0FFF == 0xEE070F90

    def lines(self):
        for base, u in self.uart.items():
            if u["busy"] and self.time_ns >= u["busy"]:
                u["thre"], u["busy"] = True, 0
            # The interrupt handler gives up after eight rounds, so a whole
            # message landing in the receiver at once aborts the firmware.
            if u["wire"] and self.time_ns >= u["arrive"]:
                u["rx"].append(u["wire"].popleft())
                u["arrive"] = self.time_ns + BYTE_NS[base]
            ier = self.regs.get(base + 0x04, 0)
            if (ier & 1 and u["rx"]) or (ier & 2 and u["thre"]):
                self.raw.add(EV_UART[base])
        for base, (hz, event) in TIMERS.items():
            period = self.timer_period(base)
            if period is None: continue
            n = int(self.time_ns // period)
            if n != self.timer_last.get(base, n):
                self.raw.add(event)
            self.timer_last[base] = n
        cell = self.time_ns // MMC_IRQ_NS
        if cell != self.mmc_cell:
            self.mmc_cell = cell
            if self.mmc.irq():
                self.raw.add(MMC_IRQ)

    def irq(self):
        uc, A = self.uc, self.A
        cpsr = self.reg(A.UC_ARM_REG_CPSR)
        if cpsr & 0x80 or not self.regs.get(AINTC + 0x10, 0) & 1: return
        if not self.regs.get(AINTC + 0x1500, 0) & 2 or self.highest() & 0x80000000: return
        pc = self.reg(A.UC_ARM_REG_PC)
        uc.reg_write(A.UC_ARM_REG_CPSR, (cpsr & ~0x3F) | 0x92)
        uc.reg_write(A.UC_ARM_REG_SPSR, cpsr)
        uc.reg_write(A.UC_ARM_REG_LR, pc + 4)
        uc.reg_write(A.UC_ARM_REG_PC, 0x18)

    # ---- running -------------------------------------------------------------
    def service(self):
        """The CPU stands in front of one of ENTRIES (an exit address: the run stops there before the
        instruction, and starting there again stops at once). Do what the model does for it, then move
        on. Returns True when the slice is over."""
        uc, A = self.uc, self.A
        pc = uc.reg_read(A.UC_ARM_REG_PC)
        p = self.profile
        if pc == p.assert_handler:
            self._assert()
            return True
        if pc == p.tx_full:
            # On the device the transmit interrupt empties the queue while this loop
            # spins; here interrupts come only between slices, so end the slice.
            # It is reached again when the slice resumes at this address; let that pass.
            self.tx_waiting = not self.tx_waiting
            if self.tx_waiting:
                self.tx_idle = True
                return True
        elif pc == p.flash_read and self._flash_read():
            return False
        elif pc == p.dsp_upload:
            self._dsp_upload()
            return False
        self.step_over(pc)
        return False

    def step_over(self, pc):
        """Run the one instruction at an exit address."""
        uc = self.uc
        uc.ctl_exits_enabled(False)
        try:
            uc.emu_start(pc, pc + 4, count=1)
        finally:
            uc.ctl_exits_enabled(True)

    def _assert(self):
        uc = self.uc
        r1, r2 = uc.reg_read(self.A.UC_ARM_REG_R1), uc.reg_read(self.A.UC_ARM_REG_R2)
        try:
            name = bytes(uc.mem_read(r1, 80)).split(b"\0")[0].decode("latin1")
        except Exception:
            name = "?"
        polled = [hex(a) for a, _ in collections.Counter(self.recent).most_common(3)]
        self.asserts.append({"file": name, "line": r2, "polled": polled})

    def _flash_read(self):
        # Byte by byte over the SPI model, booting reads 4 MiB of patterns at
        # about a tenth of device speed; the same bytes copied in one go.
        # True when done, False to let the driver run (out of range).
        uc, A = self.uc, self.A
        start, length, dest = (uc.reg_read(r) for r in (A.UC_ARM_REG_R1, A.UC_ARM_REG_R2, A.UC_ARM_REG_R3))
        if start + length > FLASH_SIZE:
            return False
        uc.mem_write(dest, bytes(self.flash.mem[start:start + length]))
        self.flash.commands[0x03] += 1
        uc.reg_write(A.UC_ARM_REG_R0, 1)
        uc.reg_write(A.UC_ARM_REG_PC, uc.reg_read(A.UC_ARM_REG_LR))
        return True

    def _dsp_upload(self):
        # The DSP is a stand-in, so its program has nowhere to go; sending it
        # byte by byte took most of the boot.
        uc = self.uc
        self.dsp_uploads.append(round(self.time_ns / 1e6, 2))
        uc.reg_write(self.A.UC_ARM_REG_R0, 1)
        uc.reg_write(self.A.UC_ARM_REG_PC, uc.reg_read(self.A.UC_ARM_REG_LR))

    def run_slice(self, limit=math.inf):
        """Run the CPU for one slice and let device time pass, an idle CPU up to the next event
        but not past limit (ns). Returns the time the slice began."""
        uc, A = self.uc, self.A
        cpsr = self.reg(A.UC_ARM_REG_CPSR)
        count = self.slice_length(cpsr & 0x1F == 0x12)
        start, self.poll_stop, self.tx_idle = self.time_ns, False, False
        if not (self.reg(A.UC_ARM_REG_PC) in self.ENTRIES and self.service()):
            pc = self.reg(A.UC_ARM_REG_PC)
            uc.emu_start(pc | (1 if cpsr & 0x20 else 0), 0, count=count)
        self.insns += count
        if self.waiting(self.reg(A.UC_ARM_REG_PC)) and self.highest() & 0x80000000:
            self.time_ns = max(self.time_ns, min(self.next_event(), limit))
        elif not self.poll_stop:        # a stopped poll loop has already spent its time on the reads
            self.time_ns += count * NS_PER_INSN
        return start

    def run_until(self, seconds):
        uc, A = self.uc, self.A
        if self.insns == 0:
            uc.reg_write(A.UC_ARM_REG_CPSR, 0xD3)
            uc.reg_write(A.UC_ARM_REG_PC, 0xC0000070)
        while self.time_ns < seconds * 1e9 and not self.asserts and self.powered:
            start = self.run_slice(seconds * 1e9)
            self.lines()
            self.irq()
            if self.time_ns // 100_000_000 != start // 100_000_000:
                shot = self.shown()
                if shot != self._seen:
                    self.screens += 1
                    self._seen = shot
                self._look_booted()
        self._look_booted()

    def loading(self):
        """True while a Korg build is loading behind its progress bar: its loading screen is up,
        or the screen manager is between that and the main screen. A start mode that sits on another screen is not loading."""
        loading_screen = LOADING_SCREENS.get(self.profile.build)
        if loading_screen is None:
            return False
        number = self.screen()
        if number == loading_screen:
            self._saw_loading = True
        return number == loading_screen or (getattr(self, "_saw_loading", False) and number in (None, 0))

    def finish_boot(self, limit_s=STOCK_BOOT_LIMIT_S):
        """Wait through the Korg builds' loading screens, at most `limit_s` in total,
        then run one second past the main screen so its state is ready for interaction."""
        if self.profile.build not in LOADING_SCREENS:
            return
        if self.time_ns < LOADING_SCREEN_BY_S * 1e9:
            self.run_until(LOADING_SCREEN_BY_S)
        loaded = False
        while self.loading() and self.time_ns < limit_s * 1e9 and not self.asserts and self.powered:
            self.run_until(self.time_ns / 1e9 + 0.02)
            loaded = True
        if loaded:
            self.run_until(self.time_ns / 1e9 + 1.0)

    def _look_booted(self):
        screen = self.screen()
        loading_screen = LOADING_SCREENS.get(self.profile.build)
        if loading_screen is not None and screen == loading_screen:
            self._saw_loading = True
        if not self.booted and screen == MAIN_SCREEN:
            self.booted, self.boot_ms = True, round(self.time_ns / 1e6, 1)


def load_flash(paths):
    data = b"".join(Path(p).read_bytes() for p in paths)
    if len(data) != FLASH_SIZE:
        raise ValueError(f"flash files must add up to 16 MiB, got {len(data)} bytes")
    return data


def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vsb", required=True, type=Path)
    parser.add_argument("--flash", nargs="*", default=[], type=Path,
                        help="own flash dump, one file or parts in address order; "
                             "without it the flash is blank: empty patterns, no samples")
    parser.add_argument("--hardware", choices=sorted(HARDWARE_MARKS),
                        help="without --flash: a blank flash of this hardware instead of the one of the build")
    parser.add_argument("--seconds", type=float, default=6.0, help="device time to run")
    parser.add_argument("--hold-power", action="store_true", help="keep the power button pressed")
    parser.add_argument("--held", type=lambda x: int(x, 0), default=0,
                        help="buttons held at power-on as a bit mask, e.g. 0x18000000")
    parser.add_argument("--png", type=Path, help="write the display here")
    parser.add_argument("--send", action="append", default=[], metavar="HEX@SECONDS",
                        help="panel message at a device time, e.g. 0009010000@3.0")
    parser.add_argument("--midi", action="append", default=[], metavar="HEX@SECONDS",
                        help="SysEx into the DIN input at a device time, e.g. f042500000f7@3.0")
    args = parser.parse_args()
    try:
        raw = args.vsb.read_bytes()
        if len(raw) != 0x200100:
            raise ValueError("VSB must contain a 0x100-byte header and 0x200000-byte payload")
        flash = load_flash(args.flash) if args.flash else bytes(hardware_flash(args.hardware)) if args.hardware else None
        sends = sorted((float(at), bytes.fromhex(msg), "panel") for msg, at in (x.split("@") for x in args.send))
        if any(len(msg) != 5 for _, msg, _ in sends):
            raise ValueError("a panel message has 5 bytes")
        sends += [(float(at), bytes.fromhex(msg), "midi") for msg, at in (x.split("@") for x in args.midi)]
        if any(kind == "midi" and (msg[:1] != b"\xf0" or msg[-1:] != b"\xf7") for _, msg, kind in sends):
            raise ValueError("a MIDI message here is one SysEx, F0 to F7")
        # Every run starts the same way, so the start up to the first event is made once and kept (bootcache.py);
        # a run from a snapshot goes on exactly as one from power-on.
        first = min([at for at, _, _ in sends] + [args.seconds])
        start = max([t for t in BOOT_STEPS if t <= first] or [0])
        if start:
            import bootcache
            m, _ = bootcache.booted(raw[0x100:], flash, args.held, start, hold_power=args.hold_power)
        else:
            m = Machine(raw[0x100:], flash)
            if args.hold_power:
                m.inputs[pin(7, 15)] = 0
            m.held = args.held
        midi_out = []
        for at, msg, kind in sorted(sends, key=lambda x: x[0]):
            m.run_until(at)
            if kind == "panel":
                m.send(msg)
            else:
                m.midi(msg)
            midi_out += m.midi_out()
        m.run_until(args.seconds)
        midi_out += m.midi_out()
        if args.png:
            m.png(args.png)
    except ImportError:
        print("Install tools/emu/requirements.txt in tools/emu/.venv", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Emulation failed: {error}", file=sys.stderr)
        return 1
    report = {
        "schema": 1, "suite": "boot", "unicorn": "2.1.4", "hardware_contact": False,
        "firmware_sha256": hashlib.sha256(raw).hexdigest(), "build": m.profile.build,
        "flash": bool(args.flash), "hardware": hardware_of_flash(m.flash.mem),
        "device_ms": round(m.time_ns / 1e6), "instructions": m.insns,
        "asserts": m.asserts, "frames": m.frames, "screens": m.screens,
        "display_lit": sum(bin(b).count("1") for row in m.fb for b in row),
        "display_sha256": hashlib.sha256(bytes(b for row in m.fb for b in row)).hexdigest(),
        "powered": m.powered,
        "panel_messages": sorted({f"{x[0]:02x}" for x in m.panel_log}),
        "leds_on": sorted(k for k, v in m.leds.items() if v),
        "flash_commands": sorted(f"{c:02x}" for c in m.flash.commands),
        "interrupts": sorted(m.enabled),
        "midi_out": [x.hex() for x in midi_out],
        "booted_ms": m.boot_ms, "midi_dropped": m.midi_dropped,
    }
    print(json.dumps(report, sort_keys=True))
    return 1 if m.asserts else 0


if __name__ == "__main__":
    sys.exit(main())
