# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the MFX 2 patch (tools/patch/mfx_switch.py,
docs/messungen/2026-10-10-mfx-umschalter.md).

`switch_cases` are what check.py runs on every patched copy that carries the
key hook: the touch pad starts in master effect mode, TOUCH SCALE switches the
master effect, MASTER FX goes back, the DSP gets what the firmware's own type
change sends, EXIT held at power-on keeps the patch out (Touch Scale as start
mode). `run` is the long scripted check against the unpatched firmware:
pattern changes, WRITE, the table in flash, every other key.

    tools/emu/.venv/bin/python tools/emu/mfx_cases.py run --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin] [--b-type 7]
    tools/emu/.venv/bin/python tools/emu/mfx_cases.py cases --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import hashlib
import itertools
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

import bootcache  # noqa: E402
import mfx_switch as spec  # noqa: E402
import synthaddr  # noqa: E402
from firmware import USER_MARKS  # noqa: E402
from machine import DSP_CTRL, DSP_DATA, DSP_SYNC, UART1, Machine, blank_flash, load_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
SCREENS = 0xC03404C0
PATTERN = 0xC033E6A4
SEQ = 0xC034029C
CTL = 0xC06912E0
GLOBALS = 0xC0691334
SET_MFX = 0xC0048A64
PATTERN_SLOTS = 0x240000                # pattern n lives at 0x240000 + n * 0x4000 in flash
LED_PAD = (0x1A, 0x1B, 0x1C, 0x1D)      # GATE ARP, TOUCH SCALE, MASTER FX, MFX HOLD
LED_MANAGER = 0xC0345A1C                # pointer to the firmware's LED manager (docs/messungen/2026-10-14-led-zustand-ram.md)
LED_COPY = 0x88C                        # its copy of what it queued for the panel: 8 bytes per LED, byte 0 the number, byte 2 the brightness
KEYS ={"rec": 0, "stop": 1, "play": 2, "gate_arp": 4, "touch_scale": 5, "master_fx": 6, "mfx_hold": 7, "shift": 0x0A,
        "menu": 9, "edit_prev": 8, "edit_next": 0x0C, "exit": 0x0D, "write": 0x0E, "pattern_set": 0x1B}
TEMPO_LED = 0x14                        # TAP blinks with the tempo, so its last value depends on the moment
POLL = (0xFF900A34, 0xFF9030EC, 0xFF9030F4)     # the DSP level polling, always there
S_MODE, S_A, S_B, S_IDX, S_PEND, S_LOADED, S_DIRTY, S_TICK, S_BOOT = (4 * i for i in range(9))


def for_build(payload):
    """Put the patch module's places to the build of this image (the synth has its own addresses, data/synth-map/).
    The constants above (SCREENS, SEQ, CTL, ...) are Sampler places; Dev translates them through the same table."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def blank_for(payload):
    """A blank flash that carries the user data mark of the build of this image."""
    return blank_flash(USER_MARKS["synth"]) if synthaddr.is_synth(payload) else blank_flash()


def has_key_hook(payload):
    """True when the key dispatcher's first instruction branches into the patch's code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.KEY_HOOK - IMAGE)[0]
    if word >> 24 != 0xEA:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= spec.KEY_HOOK + 8 + (off << 2) < spec.CODE_END


class DspLog:
    """Transfers over the DSP host port: (command, address, words written)."""

    def __init__(self, machine):
        self.xfers, self.cur, self.ctl = [], None, []
        original = machine.write

        def write(a, v):
            if a == DSP_CTRL:
                if not self.ctl and v & 0xFFFF == DSP_SYNC:     # Korg's build writes a lone sync word between frames
                    return original(a, v)
                self.ctl.append(v & 0xFFFF)
                if len(self.ctl) == 7:
                    cmd, lo, hi, count = self.ctl[:4]
                    self.cur = [cmd, (hi << 16) | lo, count, []]
                    self.xfers.append(self.cur)
                    self.ctl = []
            elif a == DSP_DATA and self.cur is not None and self.cur[0] == 0xAB:
                self.cur[3].append(v & 0xFFFF)
            return original(a, v)
        machine.write = write

    def changes(self):
        """The writes that are not the DSP's level polling."""
        return [(x[0], x[1], tuple(x[3])) for x in self.xfers if x[1] not in POLL]

    def clear(self):
        self.xfers.clear()


def same_dsp(a, b):
    """True when two lists of DspLog.changes() carry the same transfers. The effect buffers
    alternate and their write pointers run in a ring of 0x8000 words, so two boots that differ
    by a few earlier transfers sit at different places; the odd-numbered words (pointers or
    constants) may differ by one shift for the whole list."""
    if len(a) != len(b):
        return False
    swap, shift = {}, set()
    for (c1, at1, w1), (c2, at2, w2) in zip(a, b):
        if c1 != c2 or len(w1) != len(w2) or swap.setdefault(at1, at2) != at2:
            return False
        for i, (x, y) in enumerate(zip(w1, w2)):
            if i % 2 == 0:
                if x != y:
                    return False
            elif x != y:
                shift.add((y - x) % 0x8000)
    return len(shift) <= 1


class MainsMachine(Machine):
    """A machine on mains power from power-on: on battery the firmware's power save dims, and with pad-colors every LED goes out at
    a quarter (menu_cases checks that); these checks compare the LEDs' own values with the firmware's copy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.adapter = True


class Box:
    """A booted device (on mains power) with what these checks look at."""

    def __init__(self, payload, flash=None, held=0, seconds=5.0, card=None):
        if card is None:
            self.m, self.dsp = bootcache.booted(bytes(payload), flash, held, seconds, cls=MainsMachine, observer=DspLog)
            self.dev = Dev(payload, flash, held, machine=self.m)
            return
        # a boot with a card in the slot is not kept as a snapshot (bootcache.py), so it is made here
        self.dev = Dev(bytes(payload), flash, held, adapter=True)
        self.m = self.dev.m
        self.m.insert_card(card)
        self.dsp = DspLog(self.m)
        self.dev.run(seconds)

    def run(self, seconds):
        self.dev.run(seconds)

    def key(self, name, wait=0.4):
        self.dev.press(KEYS[name] if isinstance(name, str) else name, wait)

    def shift_key(self, name, wait=0.4):
        self.m.press(KEYS["shift"], True)
        self.dev.run(0.2)
        self.key(name, wait)
        self.m.press(KEYS["shift"], False)
        self.dev.run(0.3)

    def pad(self, n, wait=1.0):
        self.m.send([0x04, n, 0, 100, 1])
        self.dev.run(0.1)
        self.m.send([0x04, n, 0, 0, 0])
        self.dev.run(wait)

    def program_change(self, number):
        from sysex_cases import Link, SEARCH
        replies, _ = Link(self.dev).exchange(SEARCH, wait=2.0)
        if len(replies) != 1 or len(replies[0]) < 6:
            raise ValueError('the firmware did not report its MIDI channel')
        self.m.midi(bytes([0xC0 | (replies[0][4] & 0x0F), number]))
        self.run(0.8)

    def turn(self, delta, wait=0.4):
        self.dev.turn(delta, wait)

    def raw(self, addr, n=4):
        """Bytes at an address read out of the running firmware (a heap pointer plus an offset): never put through the Sampler to synth table."""
        return bytes(self.m.uc.mem_read(addr, n))

    def raw32(self, addr):
        return struct.unpack("<I", self.raw(addr))[0]

    def pattern(self):
        return self.dev.u32(PATTERN)

    def mfx(self):
        return self.raw(self.pattern() + 4 + 61, 1)[0]

    def number(self):
        return self.raw32(self.dev.u32(SEQ) + 0x318)

    def mode(self):
        return self.raw32(self.dev.u32(CTL) + 0x334)

    def state(self, offset):
        return self.dev.u32(spec.STATE + offset)

    def leds(self):
        return tuple(self.m.leds.get(k, 0) for k in LED_PAD)

    def copy_entries(self, leds=LED_PAD):
        """The firmware's copy of the LEDs as 8-byte entries, what a device read of the LEDs shows."""
        mgr = self.dev.u32(LED_MANAGER)
        return tuple(self.raw(mgr + LED_COPY + 8 * led, 8) for led in leds)

    def copy_leds(self, leds=LED_PAD):
        """The brightness the copy holds, to hold against what went out on the panel UART (leds())."""
        return tuple(entry[2] for entry in self.copy_entries(leds))

    def copy_numbered(self, leds=LED_PAD):
        """True when every entry of the copy starts with its own LED number (the pointer found the right table)."""
        return all(entry[0] == led for entry, led in zip(self.copy_entries(leds), leds))

    def screen(self):
        return self.raw32(self.dev.u32(SCREENS) + 0x2C)

    def page(self):
        cur = self.raw32(self.dev.u32(SCREENS) + 0x20)
        return self.raw32(cur + 0x2C) if cur else None

    def look(self):
        """Everything a stray patch could change: screen, MFX type, LEDs (but the tempo blink), touch pad mode, display."""
        leds = tuple(sorted((k, v) for k, v in self.m.leds.items() if k < 0x30 and k != TEMPO_LED))
        return (self.screen(), self.mfx(), leds, self.mode(), hashlib.sha1(self.dev.fb()).hexdigest())

    def hold(self):
        return self.raw(self.pattern() + 4 + 65, 1)[0]

    def firmware_set(self, value):
        """The firmware's own type change, the call the MFX TYPE page makes."""
        self.dev.call(SET_MFX, self.dev.u32(GLOBALS) + 0x4004, value, 1)         # the object address is a heap value, Dev.call only translates the function
        self.dev.run(1.5)

    def flash_pattern(self, number):
        at = PATTERN_SLOTS + number * 0x4000
        return bytes(self.m.flash.mem[at:at + 0x4000])

    def flash_record(self):
        return bytes(self.m.flash.mem[spec.FLASH_RECORD:spec.FLASH_RECORD + spec.RECORD_SIZE])

    def write_pattern(self):
        self.key("write", 0.6)
        self.key("write", 3.0)


def open_mfx_type_page(box):
    """MENU opens the Pattern menu on the page it was left on; Edit right until MFX TYPE (page 5)."""
    box.key("menu")
    for _ in range(15):
        if box.page() == 5:
            break
        box.key("edit_next", 0.2)
    return box.page() == 5


def record_table(raw):
    """The 256 table bytes of a stored record when id, version, length and CRC fit, else None."""
    if len(raw) != spec.RECORD_SIZE:
        return None
    ident, ver_len = struct.unpack_from("<II", raw)
    crc = struct.unpack_from("<I", raw, spec.RECORD_SIZE - 4)[0]
    if ident != spec.RECORD_ID or ver_len != (spec.RECORD_VERSION | spec.TABLE_BYTES << 16) or zlib.crc32(raw[:-4]) & 0xFFFFFFFF != crc:
        return None
    return raw[8:8 + spec.TABLE_BYTES]


def make_record(table):
    head = struct.pack("<IHH", spec.RECORD_ID, spec.RECORD_VERSION, spec.TABLE_BYTES) + bytes(table).ljust(spec.TABLE_BYTES, b"\0")
    return head + struct.pack("<I", zlib.crc32(head) & 0xFFFFFFFF)


def flash_with(flash, at, data, blank=None):
    mem = bytearray(flash) if flash else (blank or blank_flash())
    mem[at:at + len(data)] = data
    return bytes(mem)


# The touch pad's mode keys. The firmware's order of modes (0 Gate Arp alone, 1 Touch Scale alone, 2 Master FX,
# 3 Gate Arp + Touch Scale): GATE ARP from 1 gives 3, else 0; TOUCH SCALE from 0 gives 3, else 1; MASTER FX gives 2.
# With the patch GATE ARP gives 3 from every mode (and stays there when pressed again), TOUCH SCALE is MFX 2,
# SHIFT + TOUCH SCALE is the firmware's TOUCH SCALE. Mode 3 shows only the GATE ARP LED with the patch (the firmware lights both).
SEQ_KEYS = ("gate_arp", "touch_scale", "shift_touch_scale", "master_fx")
STOCK_SETUP = {1: (), 2: ("master_fx",), 3: ("gate_arp",), 0: ("master_fx", "gate_arp")}     # from the firmware's start mode 1


def press_seq(box, name, wait=0.4):
    if name == "shift_touch_scale":
        box.shift_key("touch_scale", wait)
    else:
        box.key(name, wait)


def stock_modes(make):
    """What the unpatched firmware does: {(mode, key): (mode, LEDs)} for GATE ARP, TOUCH SCALE and MASTER FX from each of the four
    touch pad modes. `make()` returns a box in the firmware's start mode (Touch Scale)."""
    table = {}
    for mode, setup in STOCK_SETUP.items():
        for key in ("gate_arp", "touch_scale", "master_fx"):
            box = make()
            for name in setup:
                box.key(name, 0.4)
            assert box.mode() == mode, (mode, setup, box.mode())
            box.key(key, 0.5)
            table[(mode, key)] = (box.mode(), box.leds())
    return table


def mode_sequences(make, table, bval, keys=SEQ_KEYS, depth=3, kill=False):
    """Every key sequence of the given depth on a patched box, checked after each key against the firmware's table:
    touch pad mode, LEDs, effect type, MFX 2 flag, and that the firmware's LED copy (what a device read shows) equals the LEDs sent to the panel. With the patch on: GATE ARP gives mode 3 from every mode and leaves MFX 2 (in mode 3
    nothing happens), TOUCH SCALE is MFX 2 (nothing when MFX 2 is on), SHIFT + TOUCH SCALE is the firmware's TOUCH SCALE, MASTER FX is
    the firmware's. With `kill` (EXIT held at power-on) every key is the firmware's. Returns the failing sequences."""
    leds_of = {mode: leds for mode, leds in table.values()}
    if not kill:        # the patch shows Gate Arp + Touch Scale with GATE ARP alone: TOUCH SCALE stays dark
        leds_of[3] = (leds_of[3][0], 0, *leds_of[3][2:])
    bad = []
    for seq in itertools.product(keys, repeat=depth):
        box = make()
        mode, flag, own = box.mode(), 0, box.mfx()
        for i, name in enumerate(seq):
            press_seq(box, name)
            if kill or name in ("shift_touch_scale", "master_fx"):
                mode, flag = table[(mode, {"shift_touch_scale": "touch_scale"}.get(name, name))][0], 0
            elif name == "gate_arp":
                mode, flag = 3, 0
            elif not flag:
                mode, flag = 2, 1
            expect = ((0, 255, 0, 0) if flag else leds_of[mode], bval if flag else own)
            got = (box.leds(), box.mfx())
            copy = box.copy_leds()      # what a device read of the LEDs shows must be what went out on the panel
            if box.mode() != mode or got != expect or copy != got[0] or (box.state(S_MODE) == 1) != bool(flag) or box.m.asserts:
                bad.append((seq[:i + 1], f"expected mode {mode} {expect}", f"got mode {box.mode()} {got} copy {copy} flag {box.state(S_MODE)}"))
                break
    return bad


def arp_capture(box, keys, pad=2):
    """(touch pad mode, bytes on MIDI out) while the sequencer plays, a trigger pad is held and the touch pad is touched, after the mode keys."""
    for name in keys:
        press_seq(box, name)
    mode = box.mode()
    box.key("play", 0.5)
    tx = box.m.uart[UART1]["tx"]
    start = len(tx)
    box.m.send([0x04, pad, 0, 100, 1])
    box.run(0.2)
    box.m.press(0x22, True)
    box.m.send([0x05, 500 >> 8, 500 & 0xFF, 500 >> 8, 500 & 0xFF])
    box.run(2.0)
    box.m.press(0x22, False)
    box.m.send([0x04, pad, 0, 0, 0])
    box.run(0.3)
    return mode, bytes(tx[start:])


def arp_notes(box, keys, pad=2):
    """Note-on messages (note, velocity) of arp_capture."""
    mode, data = arp_capture(box, keys, pad)
    return mode, [(data[i + 1], data[i + 2]) for i in range(len(data) - 2) if data[i] & 0xF0 == 0x90 and data[i + 2] > 0]


def arp_messages(box, keys, pad=2):
    """Every channel message of arp_capture, note-ons, note-offs and the rest, as (status, data bytes); real time bytes (clock) left out."""
    mode, data = arp_capture(box, keys, pad)
    out, cur, status = [], [], None
    for byte in data:
        if byte >= 0xF8:
            continue
        if byte & 0x80:
            status, cur = byte, []
            continue
        if status is None:
            continue
        cur.append(byte)
        if len(cur) == (1 if status & 0xF0 in (0xC0, 0xD0) else 2):
            out.append((status, tuple(cur)))
            cur = []
    return mode, out


def switch_cases(patched, flash=None):
    """check.py entries [{id, ok, detail}]."""
    for_build(patched)
    out = []

    def add(name, ok, detail):
        out.append({"id": f"mfx:{name}", "ok": bool(ok), "detail": detail})

    b = Box(patched, flash)
    add("boot", b.screen() == 1 and not b.m.asserts, "main screen reached, no assertion")
    stock = Box(patched, flash, held=spec.KILL_SWITCH)      # patch off: the firmware's start mode
    stock.key("master_fx", 0.8)
    add("boot_mode", b.mode() == 2 and b.leds() == (0, 0, 255, 0) and b.state(S_BOOT) == 1 and b.state(S_MODE) != 1
        and b.mode() == stock.mode() and b.leds() == stock.leds() and b.mfx() == stock.mfx(),
        f"after power-on the touch pad is in master effect mode ({b.mode()}), MASTER FX lit, the pattern's own type {b.mfx()}, as after a MASTER FX press")
    a0 = b.mfx()
    b.dsp.clear()
    b.key("touch_scale", 1.2)
    target = b.mfx()
    lit = b.leds() == (0, 1 * 255, 0, 0) and b.mode() == 2
    ref = Box(patched, flash, held=spec.KILL_SWITCH)       # patch off, so the stock call is the reference
    ref.dsp.clear()
    ref.firmware_set(target)
    b.key("master_fx", 1.2)
    add("switch", target != a0 and lit and b.mfx() == a0 and b.leds() == (0, 0, 255, 0) and not b.m.asserts,
        f"TOUCH SCALE: type {a0} -> {target}, TOUCH SCALE LED lit, MASTER FX dark; MASTER FX: back to {b.mfx()}")
    add("dsp_messages", b.dsp.changes() != [] and same_dsp(b.dsp.changes()[:len(ref.dsp.changes())], ref.dsp.changes()),
        f"the first {len(ref.dsp.changes())} DSP transfers equal the firmware's own type change to {target}")
    k = Box(patched, flash, held=spec.KILL_SWITCH)
    k.key("touch_scale", 1.0)
    k.key("master_fx", 1.0)
    add("exit_held", k.mfx() == a0 and k.m.asserts == [] and k.state(S_MODE) != 1,
        "with EXIT held at power-on TOUCH SCALE is the stock key")
    g, gk = Box(patched, flash), Box(patched, flash, held=spec.KILL_SWITCH)
    gk.key("gate_arp", 0.5)                      # the firmware's GATE ARP from Touch Scale: Gate Arp + Touch Scale
    seen = []
    for name in ("gate_arp", "gate_arp", "touch_scale", "gate_arp"):
        press_seq(g, name)
        seen.append((name, g.mode(), g.leds(), g.mfx()))
    add("gate_arp", seen[0][1] == gk.mode() == 3 and seen[0][2] == (255, 0, 0, 0) and gk.leds() == (255, 255, 0, 0) and seen[1][1:3] == seen[0][1:3]
        and seen[2][1] == 2 and seen[3][1:3] == seen[0][1:3] and seen[3][3] == seen[0][3] and g.state(S_MODE) != 1 and not g.m.asserts,
        f"GATE ARP from master effect mode gives the firmware's Gate Arp + Touch Scale (mode 3, as with EXIT held) with GATE ARP lit and TOUCH SCALE dark (EXIT held: both lit), pressed again nothing changes, from MFX 2 the pattern's own type returns: {seen}")
    c, seen, bad = Box(patched, flash), [], []
    for name in (None, "touch_scale", "touch_scale", "master_fx", "touch_scale", "gate_arp", "touch_scale", "shift_touch_scale", "gate_arp", "turn", "touch_scale", "turn", "master_fx"):
        if name == "turn":
            c.turn(1, 0.6)
        elif name:
            press_seq(c, name)
        seen.append((name, c.mode(), c.leds(), c.copy_leds()))
        if c.copy_leds() != c.leds() or not c.copy_numbered():
            bad.append(seen[-1])
    only_gate = [s for s in seen if s[1] == 3]
    add("led_copy", not bad and seen[2][2] == (0, 255, 0, 0) and len(only_gate) == 3 and all(s[3] == (255, 0, 0, 0) for s in only_gate) and not c.m.asserts,
        f"after every key of a sequence through MFX 2, MASTER FX, GATE ARP (mode 3) and a pattern change, the firmware's LED copy (manager + 0x88c, what a device read shows) equals what went out on the panel UART for GATE ARP, TOUCH SCALE, MASTER FX and MFX HOLD; "
        f"mode 3 shows only GATE ARP; differences: {bad}")
    k0 = Box(patched, flash, held=spec.KILL_SWITCH)
    add("exit_held_boot_mode", k0.mode() == 1 and k0.leds() == (0, 255, 0, 0) and k0.state(S_BOOT) != 1 and k0.screen() == 1 and not k0.m.asserts,
        "with EXIT held at power-on the touch pad starts in Touch Scale mode, TOUCH SCALE lit, as in the stock firmware")
    return out


def switch_cases_task():
    """switch_cases in a worker (parallel.py)."""
    import parallel
    return switch_cases(parallel.shared["payload"], parallel.shared["flash"])


class _Run:
    """What the scripted check's sections share: the two firmwares, the flash, the steps so far and the ways to boot."""

    def __init__(self, base, patched, flash, b_type):
        self.base, self.patched, self.flash = base, patched, flash
        for_build(patched)
        self.bval = b_type - 1
        self.steps = []

    def step(self, name, ok, detail=""):
        self.steps.append({"step": name, "ok": bool(ok), "detail": str(detail)})

    def stock_box(self, held=0, started=True, seconds=5.0):
        """The unpatched firmware; with `started` it is put into the patched copy's start mode (a MASTER FX press) so look() can be compared."""
        wait = started and not held
        box = Box(self.base, self.flash, held, seconds - 0.5 if wait else seconds)     # the press takes 0.5 s, so the box has the patched copy's age
        if wait:
            box.key("master_fx", 0.45)
        return box

    def patched_box(self, table_flash=None, held=0, seconds=5.0):
        return Box(self.patched, table_flash if table_flash is not None else self.flash, held, seconds)


def _section_start(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    # ---- the start mode
    raw, p, k = stock_box(started=False), patched_box(), patched_box(held=0x2000)
    after_press = stock_box()
    step("start: touch pad in master effect mode, MASTER FX lit, the pattern's own type, no assertion, applied once",
         p.mode() == 2 and p.leds() == (0, 0, 255, 0) and p.mfx() == raw.mfx() and p.state(S_BOOT) == 1 and p.state(S_MODE) != 1 and p.screen() == 1 and not p.m.asserts,
         (p.mode(), p.leds(), p.mfx(), raw.mfx()))
    step("start: the same screen, LEDs, mode and display as the stock firmware after a MASTER FX press", p.look() == after_press.look(), (p.leds(), after_press.leds()))
    step("start: the stock firmware starts in Touch Scale mode with TOUCH SCALE lit (what EXIT held keeps)", raw.mode() == 1 and raw.leds() == (0, 255, 0, 0), (raw.mode(), raw.leds()))
    step("start with EXIT held: Touch Scale mode, TOUCH SCALE lit, nothing of the patch ran, same as the stock firmware",
         k.mode() == 1 and k.leds() == raw.leds() and k.state(S_BOOT) != 1 and k.look() == raw.look() and not k.m.asserts, (k.mode(), k.leds()))
    bad = []
    for mask in (0x400, 0x80, 0x1):
        held, held_stock = patched_box(held=mask), stock_box(mask)
        if held.look() != held_stock.look() or held.mode() != 1 or held.m.asserts:
            bad.append((hex(mask), held.screen(), held.mode(), held.leds()))
    step("start with a key held (SHIFT, REC, the XY pad check start mode): the touch pad stays in Touch Scale mode, as in the stock firmware", not bad, bad)


def _section_keys(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    # ---- the other keys are stock
    bad = []
    for k in (0, 1, 2, 3, 6, 7, 9, 0x0D, 0x0E, 0x12, 0x15, 0x1A, 0x1B, 0x21):
        r, p = stock_box(), patched_box()
        p.run((r.m.time_ns - p.m.time_ns) / 1e9)
        for box in (r, p):
            box.m.press(k, True)
            box.run(0.2)
            box.m.press(k, False)
            box.run(0.6)
        if r.look() != p.look():
            bad.append(hex(k))
    step("14 keys alone (MASTER FX among them, not GATE ARP and TOUCH SCALE) act as in the stock firmware: screen, MFX type, LEDs, touch pad mode, display", not bad, bad)
    bad = []
    for k in (0, 4, 6, 7, 9, 0x0E, 0x12, 0x1A, 0x21):
        r, p = stock_box(), patched_box()
        p.run((r.m.time_ns - p.m.time_ns) / 1e9)
        for box in (r, p):
            box.shift_key(k)
        if r.look() != p.look():
            bad.append(hex(k))
    step("SHIFT + 9 other keys act as in the stock firmware", not bad, bad)
    r, p = stock_box(started=False), patched_box()
    for box, press in ((r, lambda b: b.key("touch_scale", 0.5)), (p, lambda b: b.shift_key("touch_scale", 0.5))):
        box.key("gate_arp", 0.5)
        press(box)
        press(box)
    step("SHIFT + TOUCH SCALE is the stock TOUCH SCALE: GATE ARP (Gate Arp + Touch Scale), then it twice (Touch Scale alone), same LEDs and mode", r.look() == p.look() and p.mode() == 1, (r.leds(), p.leds()))


def _section_modes(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    # ---- the touch pad's order of modes
    table = stock_modes(lambda: Box(base, flash, 0, 1.5))
    step("the firmware's order of modes, measured: GATE ARP 1 to 3 else 0, TOUCH SCALE 0 to 3 else 1, MASTER FX to 2",
         all(table[(m, "gate_arp")][0] == (3 if m == 1 else 0) and table[(m, "touch_scale")][0] == (3 if m == 0 else 1) and table[(m, "master_fx")][0] == 2 for m in range(4)),
         {k: v[0] for k, v in sorted(table.items())})
    bad = mode_sequences(lambda: patched_box(seconds=1.5), table, bval)
    step("all 64 sequences of three keys from GATE ARP, TOUCH SCALE, SHIFT + TOUCH SCALE, MASTER FX: mode, LEDs (panel UART and the firmware's LED copy alike) and effect type right after each key: "
         "GATE ARP gives Gate Arp + Touch Scale from every mode with only the GATE ARP LED lit, TOUCH SCALE is MFX 2, SHIFT + TOUCH SCALE and MASTER FX are the firmware's keys, MFX 2 goes off with every other mode change", not bad, bad[:3])


def _section_kill_modes(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    table = stock_modes(lambda: Box(base, flash, 0, 1.5))
    bad = mode_sequences(lambda: patched_box(held=0x2000, seconds=1.5), table, bval, ("gate_arp", "touch_scale", "master_fx"), 2, kill=True)
    step("EXIT held at power-on: all 9 sequences of GATE ARP, TOUCH SCALE and MASTER FX, two deep, follow the firmware's order of modes (LED copy equal to the panel LEDs)", not bad, bad[:3])


def _section_arp(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    alone, both = (arp_notes(stock_box(started=False, seconds=1.5), keys) for keys in (("master_fx", "gate_arp"), ("gate_arp",)))
    pad_note = max(set(n[0] for n in alone[1]), key=[n[0] for n in alone[1]].count)
    extra = {mode: {n[0] for n in notes} - {pad_note, 62, 67} for mode, notes in ((0, alone[1]), (3, both[1]))}     # 62 and 67 are the pattern's own notes
    step("firmware: Gate Arp alone (mode 0) with the sequencer playing, a trigger pad held and the touch pad touched repeats the pad's note and plays no scale note; "
         "Gate Arp + Touch Scale (mode 3) repeats it and adds a scale note per step",
         alone[0] == 0 and both[0] == 3 and not extra[0] and extra[3] and [n[0] for n in alone[1]].count(pad_note) > 5 and [n[0] for n in both[1]].count(pad_note) > 5,
         (pad_note, len(alone[1]), len(both[1]), extra))
    for label, keys, stock_keys in (("GATE ARP from the start", ("gate_arp",), ("gate_arp",)),
                                    ("GATE ARP twice", ("gate_arp", "gate_arp"), ("gate_arp",)),
                                    ("TOUCH SCALE (MFX 2), then GATE ARP", ("touch_scale", "gate_arp"), ("gate_arp",)),
                                    ("SHIFT + TOUCH SCALE after GATE ARP", ("gate_arp", "shift_touch_scale"), ("gate_arp", "touch_scale"))):
        mode_p, notes_p = arp_messages(patched_box(seconds=1.5), keys)
        mode_s, notes_s = arp_messages(stock_box(started=False, seconds=1.5), stock_keys)
        ons = [d for st, d in notes_p if st & 0xF0 == 0x90 and d[1] > 0]
        step(f"{label}: playing, a trigger pad held and the touch pad touched sends the same MIDI messages (note-ons, note-offs, all the rest) as the firmware in the same mode",
             mode_p == mode_s and notes_p == notes_s and len(ons) > 0, (mode_p, len(notes_p), len(notes_s), len(ons), notes_p[:4]))
    r, p = stock_box(started=False), patched_box()
    r.key("gate_arp", 0.5)
    p.key("gate_arp", 0.5)
    (rs, rm, rl, rmode, rfb), (ps, pm, pl, pmode, pfb) = r.look(), p.look()
    diff = sorted(set(rl) ^ set(pl))
    step("GATE ARP: the only difference to the firmware's Gate Arp + Touch Scale is the TOUCH SCALE LED (dark, the firmware lights it): same mode, screen, type and display",
         (rs, rm, rmode, rfb) == (ps, pm, pmode, pfb) and pmode == 3 and diff == [(0x1b, 0), (0x1b, 255)] and not p.m.asserts
         and p.copy_leds() == p.leds() == (255, 0, 0, 0) and p.copy_numbered(),
         f"TOUCH SCALE LED: firmware {dict(rl).get(0x1b)}, patched {dict(pl).get(0x1b)}; differing LEDs {diff}; the LED copy shows only GATE ARP: {p.copy_leds()}")


def _section_kill(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    # ---- kill switch
    r, p = stock_box(0x2000), patched_box(held=0x2000)
    for box in (r, p):
        box.key("touch_scale", 0.8)
        box.key("gate_arp", 0.5)
        box.key("touch_scale", 0.8)
        box.shift_key("touch_scale", 0.5)
    step("EXIT held at power-on: TOUCH SCALE, SHIFT + TOUCH SCALE and the rest act as in the stock firmware",
         r.look() == p.look() and p.state(S_MODE) != 1 and not p.m.asserts, p.leds())


def _section_buttons(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    # ---- the buttons
    d = patched_box()
    own = d.mfx()
    step("boot: main screen, no assertion, pattern 1 has its own type", d.screen() == 1 and not d.m.asserts, f"type {own}")
    ref = stock_box()
    d.dsp.clear()
    ref.dsp.clear()
    d.key("touch_scale", 1.2)
    ref.firmware_set(bval)
    step("TOUCH SCALE: touch pad in master effect mode, type is MFX 2", d.mode() == 2 and d.mfx() == bval, f"mode {d.mode()}, type {d.mfx()} (display {d.mfx() + 1})")
    step("TOUCH SCALE: its LED lit, MASTER FX dark, GATE ARP dark", d.leds() == (0, 255, 0, 0), d.leds())
    step("TOUCH SCALE: DSP transfers equal the firmware's own type change", same_dsp(d.dsp.changes(), ref.dsp.changes()) and d.dsp.changes() != [], f"{len(d.dsp.changes())} transfers")
    before, seen = d.look(), len(d.dsp.xfers)
    d.key("touch_scale", 1.0)
    step("TOUCH SCALE again: nothing changes", d.look() == before and same_dsp(d.dsp.changes(), ref.dsp.changes()))
    d.dsp.clear()
    ref.dsp.clear()
    d.key("master_fx", 1.2)
    ref.firmware_set(own)
    step("MASTER FX: the pattern's own type, MASTER FX LED lit, TOUCH SCALE dark", d.mfx() == own and d.leds() == (0, 0, 255, 0) and d.mode() == 2, (d.mfx(), d.leds()))
    step("MASTER FX: DSP transfers equal the firmware's own type change back", same_dsp(d.dsp.changes(), ref.dsp.changes()) and d.dsp.changes() != [])
    d.key("touch_scale", 1.0)
    d.key("gate_arp", 1.0)
    step("GATE ARP from MFX 2: own type, Gate Arp + Touch Scale (mode 3), GATE ARP lit and TOUCH SCALE dark, MFX 2 off", d.mfx() == own and d.leds() == (255, 0, 0, 0) and d.mode() == 3 and d.state(S_MODE) != 1, (d.mfx(), d.leds(), d.mode()))
    d.key("touch_scale", 1.0)
    d.shift_key("touch_scale", 0.6)
    r = stock_box()
    r.key("master_fx", 0.6)
    r.key("touch_scale", 0.6)
    step("SHIFT + TOUCH SCALE from MFX 2: own type, then what the stock TOUCH SCALE does from master effect mode",
         d.look() == r.look() and d.mfx() == own, (d.leds(), d.mode()))
    d.key("touch_scale", 1.0)
    d.shift_key("master_fx", 1.0)
    step("SHIFT + MASTER FX (stock jump to MFX TYPE) keeps MFX 2 on and the page shows it",
         d.state(S_MODE) == 1 and d.screen() == 3 and d.page() == 5 and d.mfx() == bval, (d.screen(), d.page(), d.mfx()))
    d.key("exit", 0.5)
    d.key("master_fx", 1.0)


def _section_patterns(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    # ---- pattern changes
    d = patched_box()
    d.key("touch_scale", 1.0)
    results = []
    for delta in (1, 1, -2, 5):
        d.turn(delta, 0.5)
        n = d.number()
        results.append((n, d.mfx(), d.mode(), d.leds(), d.state(S_A)))
    bad = [r for r in results if not (r[1] == bval and r[2] == 2 and r[3] == (0, 255, 0, 0))]
    step("pattern changes with the wheel while MFX 2 is on: MFX 2 of the new pattern, mode and LEDs right 0.5 s after", not bad, results)
    stock = stock_box()
    owns = []
    for delta in (1, 1, -2, 5):
        stock.turn(delta, 1.0)
        owns.append((stock.number(), stock.mfx()))
    step("the pattern's own type is kept for each pattern (stock values read back)", [(r[0], r[4]) for r in results] == owns, (owns, [(r[0], r[4]) for r in results]))
    d.key("master_fx", 1.0)
    step("MASTER FX after pattern changes: the new pattern's own type, nothing leaked", d.mfx() == owns[-1][1], (d.mfx(), owns[-1]))
    d = patched_box()
    d.key("touch_scale", 1.0)
    d.key("pattern_set", 0.5)
    d.pad(7)
    stock = stock_box()
    stock.key("pattern_set", 0.5)
    stock.pad(7)
    step("pattern selected with a pad: MFX 2 of that pattern, own type kept", d.number() == stock.number() and d.mfx() == bval and d.mode() == 2 and d.leds() == (0, 255, 0, 0)
         and d.state(S_A) == stock.mfx(), (d.number(), d.mfx(), d.state(S_A), stock.mfx()))
    d = patched_box()
    d.key("touch_scale", 1.0)
    d.program_change(12)
    ref = stock_box()
    ref.program_change(12)
    step("pattern changed by MIDI program change: MFX 2 of that pattern, own type kept, LEDs right", d.number() == ref.number() == 12 and d.mfx() == bval
         and d.mode() == 2 and d.leds()[:3] == (0, 255, 0) and d.state(S_A) == ref.mfx(), (d.number(), d.mfx(), d.state(S_A), ref.mfx(), d.leds()))
    d = patched_box()
    d.key("play", 0.5)
    d.key("touch_scale", 1.0)
    d.turn(1, 0.6)
    ok_play = d.mfx() == bval and d.leds() == (0, 255, 0, 0) and not d.m.asserts
    ref = stock_box()
    ref.key("play", 0.5)
    ref.turn(1, 0.6)
    for box in (d, ref):
        for _ in range(30):             # the change comes at the end of the bar, wherever the bar began
            if box.number() != 0:
                break
            box.run(0.5)
        box.run(0.5)
    ok_play = ok_play and d.number() == ref.number()
    d.key("master_fx", 1.0)
    step("while the sequencer plays: switching and a pattern change (it takes effect at the end of the bar)", ok_play and d.mfx() == ref.mfx(), (d.number(), ref.number(), d.mfx(), ref.mfx(), d.leds()))
    d.key("play", 0.5)


def _section_write(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    own = patched_box().mfx()          # the pattern's own type, as the section of the buttons reads it
    # ---- WRITE keeps MFX 1
    d = patched_box()
    n = d.number()
    r = stock_box()
    r.write_pattern()
    d.key("touch_scale", 1.0)
    d.write_pattern()
    step("WRITE while MFX 2 is on: the stored pattern is byte for byte the stock one (own type, not MFX 2)", d.flash_pattern(n) == r.flash_pattern(n) and d.flash_pattern(n)[61] == own,
         (d.flash_pattern(n)[61], r.flash_pattern(n)[61]))
    step("WRITE: MFX 2 stays on afterwards", d.mfx() == bval and d.state(S_MODE) == 1 and d.leds() == (0, 255, 0, 0), (d.mfx(), d.leds()))
    step("WRITE without a changed table leaves the table sector alone", d.flash_record() == b"\xff" * spec.RECORD_SIZE)
    d.key("master_fx", 1.0)
    step("after WRITE, MASTER FX: the pattern's own type", d.mfx() == own)


def _section_flash(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    own = patched_box().mfx()          # the pattern's own type, as the section of the buttons reads it
    # ---- MFX 2 chosen on the device, stored in flash
    d = patched_box()
    start = bytes(d.m.flash.mem)
    n = d.number()
    open_mfx_type_page(d)
    d.turn(1, 0.8)
    own_edit = d.mfx()
    step("the MFX TYPE page changes the type when MFX 2 is off (stock) and does not touch the table", d.state(S_DIRTY) != 1 and own_edit == own + 1, own_edit)
    d.turn(-1, 0.8)
    d.key("exit", 0.5)
    d.key("touch_scale", 1.0)
    open_mfx_type_page(d)
    d.turn(1, 0.8)
    picked = d.mfx()
    step("MFX TYPE page while MFX 2 is on: VALUE picks MFX 2 of this pattern", picked == bval + 1 and d.state(S_DIRTY) == 1 and d.state(S_MODE) == 1, (picked, d.state(S_DIRTY)))
    d.key("exit", 0.5)
    d.key("master_fx", 1.0)
    d.key("touch_scale", 1.0)
    step("MASTER FX, then TOUCH SCALE: the picked MFX 2 comes back, the pattern's own type is kept", d.mfx() == picked and d.state(S_A) == own, (d.mfx(), d.state(S_A)))
    d.write_pattern()
    table = record_table(d.flash_record())
    step("WRITE stores the table: record with id, version, length and CRC-32, the entry for this pattern, all others empty",
         table is not None and table[n] == picked + 1 and not any(table[:n]) and not any(table[n + 1:]), (picked + 1, None if table is None else table[n]))
    step("WRITE stores the pattern's own type in the pattern", d.flash_pattern(n)[61] == own, d.flash_pattern(n)[61])
    step("after WRITE the table counts as saved", d.state(S_DIRTY) != 1)
    saved = bytes(d.m.flash.mem)
    q = patched_box(saved)
    q.key("touch_scale", 1.0)
    other = patched_box(saved)
    other.turn(1, 1.0)
    other.key("touch_scale", 1.0)
    step("after a restart: MFX 2 is the picked one for that pattern and the default for another", q.mfx() == picked and other.mfx() == bval and q.number() == n != other.number(), (q.mfx(), other.mfx()))
    bad_flash = bytearray(saved)
    bad_flash[spec.FLASH_RECORD + 20] ^= 1
    q2 = patched_box(bytes(bad_flash))
    q2.key("touch_scale", 1.0)
    step("a record with a flipped bit is ignored: default MFX 2", q2.mfx() == bval, q2.mfx())
    for label, record in (("wrong id", make_record(range(256)).replace(b"MFX2", b"MFX3", 1)), ("half written", make_record([picked + 1] * 250)[:128] + b"\xff" * (spec.RECORD_SIZE - 128))):
        q3 = patched_box(flash_with(flash, spec.FLASH_RECORD, record, blank_for(patched)))
        q3.key("touch_scale", 1.0)
        step(f"a {label} record is ignored: default MFX 2", q3.mfx() == bval, q3.mfx())
    q4 = patched_box(flash_with(flash, spec.FLASH_RECORD, make_record([200, 0, 101] + [0] * 253), blank_for(patched)))
    q4.key("touch_scale", 1.0)
    step("a valid record with an entry out of range or empty: default MFX 2", q4.mfx() == bval, q4.mfx())
    changed = {i >> 14 for i in range(0, len(saved), 4) if saved[i:i + 4] != start[i:i + 4]}
    allowed = {(PATTERN_SLOTS + n * 0x4000) >> 14, spec.FLASH_RECORD >> 14}
    step("the only flash the patch and WRITE changed is the pattern's slot and the table sector", changed <= allowed, sorted(hex(c << 14) for c in changed - allowed))


def _section_hold(c):
    base, patched, flash, bval = c.base, c.patched, c.flash, c.bval
    step, stock_box, patched_box = c.step, c.stock_box, c.patched_box
    own = patched_box().mfx()          # the pattern's own type, as the section of the buttons reads it
    # ---- MFX HOLD, the page, equal types
    d = patched_box()
    d.key("mfx_hold", 0.5)
    h = d.hold()
    d.key("touch_scale", 1.0)
    held_on = d.hold() == h and d.mfx() == bval
    d.key("master_fx", 1.0)
    step("MFX HOLD: the held state is untouched by the switch", held_on and d.hold() == h and d.mfx() == own, h)
    d = patched_box()
    open_mfx_type_page(d)
    before = hashlib.sha1(d.dev.fb()).hexdigest()
    d.key("touch_scale", 1.0)
    after = hashlib.sha1(d.dev.fb()).hexdigest()
    d.key("edit_next", 0.3)
    d.key("edit_prev", 0.3)
    step("the MFX TYPE page shows the new type at once (as when it is built again)", before != after and after == hashlib.sha1(d.dev.fb()).hexdigest())
    seq = []
    for _ in range(10):
        d.key("touch_scale", 0.4)
        seq.append(d.mfx())
        d.key("master_fx", 0.4)
        seq.append(d.mfx())
    step("on the MFX TYPE page ten quick pairs rebuild it each time without trouble", seq == [bval, own] * 10 and d.page() == 5 and not d.m.asserts, seq[:4])
    d = patched_box()
    d.firmware_set(bval)
    d.dsp.clear()
    d.key("touch_scale", 1.0)
    step("pattern already on the MFX 2 type: no effect change, mode on", d.mfx() == bval and d.mode() == 2 and d.leds() == (0, 255, 0, 0) and d.dsp.changes() == [])
    d = patched_box()
    seq = []
    for _ in range(6):
        d.key("touch_scale", 0.5)
        seq.append(d.mfx())
        d.key("master_fx", 0.5)
        seq.append(d.mfx())
    step("six quick TOUCH SCALE and MASTER FX pairs alternate", seq == [bval, own] * 6, seq)
    step("no assertion at any point", not d.m.asserts, d.m.asserts)


# What the scripted check does, in the order it reports. The sections boot their own devices and do not
# depend on each other, so they run side by side; `modes` and `keys` are the long ones.
SECTIONS = ("start", "keys", "modes", "kill_modes", "arp", "kill", "buttons", "patterns", "write", "flash", "hold")
LONGEST_FIRST = ("modes", "keys", "arp", "patterns", "flash", "buttons", "kill_modes", "start", "write", "hold", "kill")


def run_section(name):
    """One section of `run` in a worker (parallel.py): its steps."""
    import parallel
    c = _Run(parallel.shared["base"], parallel.shared["patched"], parallel.shared["flash"], parallel.shared["b_type"])
    globals()[f"_section_{name}"](c)
    return c.steps


def run(base, patched, flash=None, b_type=7, jobs=None):
    """The scripted check against the unpatched firmware. Returns {ok, steps}."""
    import parallel
    done = parallel.run_tasks([("mfx_cases", "run_section", (name,)) for name in LONGEST_FIRST],
                              {"base": base, "patched": patched, "flash": flash, "b_type": b_type}, jobs)
    by_name = dict(zip(LONGEST_FIRST, done))
    steps = [s for name in SECTIONS for s in by_name[name]]
    return {"ok": all(s["ok"] for s in steps), "steps": steps}



def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=["run", "cases"])
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--b-type", type=int, default=7)
    a = p.parse_args()
    base = a.base.read_bytes()[0x100:]
    patched = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    parts = (a.cmd, base, patched, flash or b"", a.b_type)
    if a.cmd == "cases":
        def compute():
            result = {"ok": True, "checks": switch_cases(patched, flash)}
            result["ok"] = all(c["ok"] for c in result["checks"])
            return result
    else:
        def compute():
            return run(base, patched, flash, a.b_type)
    result = bootcache.cached_result("mfx_cases", parts, compute)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
