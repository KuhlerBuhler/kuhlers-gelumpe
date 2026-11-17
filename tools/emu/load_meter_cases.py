"""Emulator cases of LOAD METER (CUSTOMIZATION > DISPLAY, tools/patch/script_load_meter.s): the ARM's load in percent as two
digits left of the card symbol. Off it draws nothing and its two hooks cost almost nothing; on, the value matches method A
recomputed here from the same two firmware places (the idle loop's store in front of wfi, the IRQ entry), idle and with 16
parts playing; the page switches it, WRITE keeps it in byte 7 of a version 4 settings file and the next start reads it; the
digits stay off the BLECH menu and the WRITE window and are gone after OFF on the page; with EXIT held at power-on nothing
is measured.

    python3 tools/emu/load_meter_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--png DIR]

Measured in docs/messungen/2026-11-14-energie-befunde.md ("Lastanzeige").
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases as mc  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402

LM = script_hooks.LOAD_METER
LM_VALUE, LM_DRAWN, LM_SLEEP, LM_ARMED = LM + 28, LM + 29, LM + 8, LM + 32
TICKS = 150_000_000                              # Timer3 ticks a second
COLS = range(86, 94)                             # page 0, the eight columns the digits use (row 0 stays the firmware's)
IDLE_SITE, IRQ_SITE = 0xC00017F0, 0xC000159C     # the idle loop's store of 1 in front of wfi, the IRQ entry's store of the word + 1
FONT = bytes([0xFE, 0x82, 0xFE, 0, 0x84, 0xFE, 0x80, 0, 0xF2, 0x92, 0x9E, 0, 0x92, 0x92, 0xFE, 0, 0x1E, 0x10, 0xFE, 0,
              0x9E, 0x92, 0xF2, 0, 0xFE, 0x92, 0xF2, 0, 0x02, 0x02, 0xFE, 0, 0xFE, 0x92, 0xFE, 0, 0x9E, 0x92, 0xFE, 0])
NS = 5                                           # ns an instruction (arm_load's model, docs/messungen 0.1)
OFF_COST = 0.1                                   # percentage points the hooks may cost with the switch off (plan SC-5.1)
PATTERN = 0xC033E6A4                             # -> the pattern in RAM, + 4 the pattern block


def entry(name, ok, detail):
    return {"id": f"load_meter:{name}", "ok": bool(ok), "detail": str(detail)}


def glyphs(value):
    """The eight columns the frame draws for `value` (0 to 99), row 0 left out."""
    tens = FONT[value // 10 * 4:value // 10 * 4 + 4] if value >= 10 else bytes(4)
    return tens + FONT[value % 10 * 4:value % 10 * 4 + 4]


def shown(dev):
    """The columns on the display, row 0 left out."""
    return bytes(b & 0xFE for b in bytes(dev.m.fb[0])[COLS.start:COLS.stop])


def branch_target(dev, site):
    word = dev.u32(site)
    if word >> 24 != 0xEA:
        return None
    off = word & 0xFFFFFF
    off -= (off & 0x800000) << 1
    return dev.a(site) + 8 + off * 4


class Meter:
    """A booted device on its main screen, with method A recomputed from the firmware's two places and every value the frame
    stores, and the instructions run in the meter's own code counted."""

    def __init__(self, payload, flash=None, files=None):
        self.synth = synthaddr.is_synth(payload)
        self.wait = 10.0 if self.synth else 2.0
        self.dev = mc.boot(payload, flash, files=files or mc.CARD_FOLDER, adapter=True, seconds=self.wait)
        m, uc, dev = self.dev.m, self.dev.m.uc, self.dev
        self.code = branch_target(dev, IDLE_SITE)
        end = bytes(m.uc.mem_read(self.code, 0x800)).find(FONT) if self.code else -1
        self.code_end = self.code + end if end > 0 else None
        self.stamp, self.idle, self.values, self.counted = None, 0, [], 0
        idle_at, irq_at = dev.a(IDLE_SITE), dev.a(IRQ_SITE)

        def code(u, at, size, _):
            if at == idle_at:
                self.stamp = m.time_ns
            elif at == irq_at:
                if u.reg_read(m.A.UC_ARM_REG_R3) == 1 and self.stamp is not None:
                    self.idle += m.time_ns - self.stamp
                self.stamp = None

        def wrote(u, kind, at, size, value, _):
            if value != 0xFF:
                self.values.append((m.time_ns, value & 0xFF, self.idle))

        def block(u, at, size, _):
            self.counted += size // 4

        for at in (idle_at, irq_at):
            uc.hook_add(unicorn.UC_HOOK_CODE, code, begin=at, end=at)
        uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, wrote, begin=LM_VALUE, end=LM_VALUE)
        if self.code_end:
            uc.hook_add(unicorn.UC_HOOK_BLOCK, block, begin=self.code, end=self.code_end)
        uc.ctl_flush_tb()

    def switch(self, on):
        flags = self.dev.read(mc.MX_FLAGS2, 1)[0]
        self.dev.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags | 1 if on else flags & ~1]))

    def cost(self, seconds=2.0):
        """Percentage points of the ARM's time spent in the meter's code over `seconds`."""
        self.counted, t0 = 0, self.dev.m.time_ns
        self.dev.run(seconds)
        return self.counted * NS / (self.dev.m.time_ns - t0) * 100

    def compare(self, seconds):
        """Run `seconds` -> [(the value stored, method A over the same window)] for every window wholly inside the run."""
        first = len(self.values)
        self.dev.run(seconds)
        got = self.values[first:]
        out = []
        for (t0, _, idle0), (t1, value, idle1) in zip(got, got[1:]):
            out.append((value, min(99, round(100 - (idle1 - idle0) / (t1 - t0) * 100))))
        return out

    def byte(self, addr):
        return self.dev.read(addr, 1)[0]


def heavy(dev):
    """16 parts, each with a note on every other step (the first four on every step), playing (docs/messungen 0.1)."""
    uc = dev.m.uc
    pattern = dev.u32(PATTERN) + 4
    uc.mem_write(pattern + 37, bytes([3]))
    for part in range(16):
        for step in range(64):
            trig = step % 2 == part % 2 or part < 4
            uc.mem_write(pattern + 0x830 + part * 0x330 + step * 12, bytes([1, 96, 96, int(trig), 61, 0, 0, 0, 0, 0, 0, 0]))
    dev.press(2, 0.4)


def newest_settings(image):
    files = [r for r in mc.settings_raw(image).values() if len(r) >= 24 and r[:4] == b"GSET"]
    return max(files, key=lambda r: struct.unpack_from("<I", r, 8)[0]) if files else None


def cases(payload, flash=None, png=None):
    out = []
    build = "synth" if synthaddr.is_synth(payload) else mc.firmware.build_of(payload)
    mc.for_build(payload)
    r = Meter(payload, flash)
    dev = r.dev
    if r.code_end is None:
        return [entry("hooked", False, f"build {build}: no branch to the meter's code at {IDLE_SITE:#x}")]

    before = shown(dev)
    sleep0 = dev.u32(LM_SLEEP)
    off_cost = r.cost()
    slept = (dev.u32(LM_SLEEP) - sleep0) & 0xFFFFFFFF          # 2 s idle: most of it asleep
    out.append(entry("off_draws_nothing_and_costs_little",
                     off_cost <= OFF_COST and r.byte(LM_DRAWN) != 1 and not r.values and not any(before) and shown(dev) == before
                     and slept > 1.5 * TICKS and not dev.m.asserts,
                     f"build {build}: {off_cost:.3f} points in the meter's code over 2 s idle (at most {OFF_COST}), drawn "
                     f"{r.byte(LM_DRAWN)}, values {len(r.values)}, columns {before.hex()} -> {shown(dev).hex()}, sleep summed {slept / TICKS:.3f} s"))

    r.switch(True)
    idle = r.compare(4.5)
    on_cost = r.cost(1.0)
    dev.run(0.1)
    value = r.byte(LM_VALUE)
    out.append(entry("idle_matches_method_a", len(idle) >= 2 and all(abs(a - b) <= 1 for a, b in idle) and shown(dev) == glyphs(value)
                     and not dev.m.asserts,
                     f"build {build}: (shown, method A) {idle}, display {shown(dev).hex()} for {value}, on {on_cost:.3f} points"))
    if png:
        dev.m.png(str(Path(png) / f"{build}-load-idle.png"))

    heavy(dev)
    dev.run(1.2)
    busy = r.compare(4.5)
    dev.run(0.1)
    value = r.byte(LM_VALUE)
    out.append(entry("playing_matches_method_a", len(busy) >= 2 and all(abs(a - b) <= 1 for a, b in busy)
                     and max(a for a, _ in busy) > max(a for a, _ in idle) and shown(dev) == glyphs(value) and not dev.m.asserts,
                     f"build {build}: 16 parts playing, (shown, method A) {busy}, display {shown(dev).hex()} for {value}"))
    if png:
        dev.m.png(str(Path(png) / f"{build}-load-playing.png"))
    dev.press(1, 0.3)

    dev.press(0x0E, 0.6)                             # WRITE on the main screen: the firmware's window
    in_window = r.byte(LM_DRAWN), shown(dev)
    if png:
        dev.m.png(str(Path(png) / f"{build}-load-write-window.png"))
    dev.press("exit", 0.6)
    dev.run(1.2)
    back = r.byte(LM_DRAWN), shown(dev) == glyphs(r.byte(LM_VALUE))
    out.append(entry("not_over_the_write_window", in_window[0] == 0 and not any(in_window[1]) and back == (1, True) and not dev.m.asserts,
                     f"build {build}: in the window (drawn, columns) ({in_window[0]}, {in_window[1].hex()}), back on the main screen {back}"))

    r.switch(False)
    dev.run(0.3)
    out.append(entry("off_takes_the_digits_away", r.byte(LM_DRAWN) == 0 and not any(shown(dev)) and not dev.m.asserts,
                     f"build {build}: drawn {r.byte(LM_DRAWN)}, columns {shown(dev).hex()}"))

    # the page: OFF by default, the dial switches it at once, the BLECH menu has no digits, WRITE keeps it in byte 7 (version 4)
    page = Meter(payload, flash)
    d = page.dev
    mc.goto_group(d, mc.GROUP_DISPLAY, 5)
    first = mc.texts_of(d), mc.counter(d)
    d.turn(1, wait=0.4)
    on = mc.texts_of(d), page.byte(mc.MX_FLAGS2) & 1
    d.run(1.5)
    in_menu = page.byte(LM_DRAWN)
    mc.press(d, "write", wait=0.6)
    d.run(3.0)
    rec = newest_settings(d.m.mmc.card.medium.data)
    written = bytearray(d.m.mmc.card.medium.data)  # the card as WRITE left it (OFF further down is saved again on leaving)
    mc.leave_to_main(d)
    d.run(1.5)
    main = page.byte(LM_DRAWN), shown(d) == glyphs(page.byte(LM_VALUE)) and page.byte(LM_VALUE) != 0xFF
    out.append(entry("page_switches_at_once", first == (("LOAD METER", "OFF", ""), (5, 7)) and on == (("LOAD METER", "ON", ""), 1)
                     and in_menu == 0 and main == (1, True) and not d.m.asserts,
                     f"build {build}: page {first}, dial up {on}, drawn in the menu {in_menu}, on the main screen (drawn, digits right) {main}"))
    out.append(entry("write_keeps_it_in_byte_7", rec is not None and rec[4] == 4 and rec[7] & 1,
                     f"build {build}: newest file (version, byte 7) {None if rec is None else (rec[4], rec[7])}"))

    # OFF on the page while the digits were shown: back on the main screen they are gone
    mc.goto_group(d, mc.GROUP_DISPLAY, 5)
    d.turn(-1, wait=0.4)
    off_page = mc.texts_of(d)[1], page.byte(mc.MX_FLAGS2) & 1
    mc.leave_to_main(d)
    d.run(1.5)
    out.append(entry("off_on_the_page_leaves_no_digits", main == (1, True) and off_page == ("OFF", 0) and page.byte(LM_DRAWN) == 0
                     and not any(shown(d)) and not d.m.asserts,
                     f"build {build}: page after the dial down {off_page}, on the main screen drawn {page.byte(LM_DRAWN)}, columns {shown(d).hex()}"))

    again = mc.Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(mc.SDCard(mc.MemoryMedium(written)))
    again.run(r.wait + 2.0)
    out.append(entry("next_start_reads_it", again.read(mc.MX_FLAGS2, 1)[0] & 1 and again.read(LM_DRAWN, 1)[0] == 1 and not again.m.asserts,
                     f"build {build}: byte 7 {again.read(mc.MX_FLAGS2, 1)[0]:#x}, drawn {again.read(LM_DRAWN, 1)[0]}, value {again.read(LM_VALUE, 1)[0]}"))

    # EXIT held at power-on: the menu is not armed, the hooks measure nothing
    held = mc.boot(payload, flash, held=mc.KILL, files=mc.CARD_FOLDER, adapter=True, seconds=r.wait)
    sleep0 = held.u32(LM_SLEEP)
    held.run(2.0)
    out.append(entry("exit_at_power_on_measures_nothing", held.u32(LM_SLEEP) == sleep0 and held.read(LM_ARMED, 1)[0] != 1
                     and held.read(LM_DRAWN, 1)[0] != 1 and not held.m.asserts,
                     f"build {build}: sleep sum {sleep0:#x} -> {held.u32(LM_SLEEP):#x}, armed byte {held.read(LM_ARMED, 1)[0]:#x}"))
    return out


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    p.add_argument("--png", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes()[0x100:], load_flash(a.flash) if a.flash else None, a.png)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
