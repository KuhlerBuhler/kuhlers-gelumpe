"""Emulator cases of BATTERY % (CUSTOMIZATION > DISPLAY, tools/patch/script_battery.s): the battery's charge in steps of 10
percent on the main screen's top row, left of LOAD METER's digits. Shown only on battery with Global BATTERY TYPE Alkali; on
mains power and with Ni-MH nothing is drawn. The battery reading comes in as panel message 6 (machine.battery), mains or
battery as message 7 (machine.power_source). The value is smoothed: a short dip leaves it, a lasting change walks there in
steps. The page is ON by default, OFF takes the digits away at once, WRITE keeps OFF as bit 4 of byte 7 (version 4), ON writes
version 3, and the next start reads it. With LOAD METER on and a card in, the digits, the load meter, the card and the battery
symbol each keep their own columns.

The mapping from reading to percent is a placeholder (derived, not measured): linear between the empty and the full threshold
of the firmware's Alkali table, read from the firmware's battery model at run time.

    python3 tools/emu/battery_percent_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--png DIR]

Measured in docs/messungen/2026-11-16-batterie-prozent.md.
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

from tools.patch import script_hooks  # noqa: E402
import menu_cases as mc  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402

BATT = script_hooks.BATT
BP_SHOWN, BP_DRAWN = BATT + 8, BATT + 9
LM = script_hooks.LOAD_METER
LM_VALUE = LM + 28
BATTERY_MODEL = 0xC03405C8                      # -> the firmware's battery model: +0x318 the threshold table, +0x320 the reading
GLOBALS = 0xC033E6A0                            # -> the Global object, its block at +4; byte 0x20 BATTERY TYPE (0 Ni-MH, 1 Alkali)
GLOBAL_SCREEN, BATTERY_TYPE_PAGE = 9, 14        # GLOBAL PARAMETERS and its page BATTERY TYPE (counted from 0)
COLS = range(83, 99)                            # page 0: four slots of 3 columns and a blank one (hundreds, tens, ones, %)
LOAD_COLS, CARD_COLS, SYMBOL_COLS = range(100, 108), range(109, 115), range(117, 128)
FLAGS2_BATT_OFF = 16                            # bit 4 of byte 7 of the settings (script_menu.s:FLAGS2_BATT_OFF)
FONT = bytes([0xFE, 0x82, 0xFE, 0, 0x84, 0xFE, 0x80, 0, 0xF2, 0x92, 0x9E, 0, 0x92, 0x92, 0xFE, 0, 0x1E, 0x10, 0xFE, 0,
              0x9E, 0x92, 0xF2, 0, 0xFE, 0x92, 0xF2, 0, 0x02, 0x02, 0xFE, 0, 0xFE, 0x92, 0xFE, 0, 0x9E, 0x92, 0xFE, 0])
PERCENT = bytes([0x42, 0x38, 0x84, 0])
STEP_S = 0.25                                   # one smoothing step (script_battery.s:BP_STEP_MS)


def entry(name, ok, detail):
    return {"id": f"battery_percent:{name}", "ok": bool(ok), "detail": str(detail)}


def digit(d):
    return FONT[d * 4:d * 4 + 4] if d is not None else bytes(4)


def glyphs(percent):
    """The sixteen columns the frame draws for `percent` (0 to 100 in steps of 10), row 0 left out."""
    hundreds = 1 if percent == 100 else None
    tens = percent // 10 % 10 if percent >= 10 else None
    return digit(hundreds) + digit(tens) + digit(percent % 10) + PERCENT


def columns(dev, cols=COLS):
    """The columns on the display, row 0 left out."""
    return bytes(b & 0xFE for b in bytes(dev.m.fb[0])[cols.start:cols.stop])


def newest_settings(image):
    files = [r for r in mc.settings_raw(image).values() if len(r) >= 24 and r[:4] == b"GSET"]
    return max(files, key=lambda r: struct.unpack_from("<I", r, 8)[0]) if files else None


class Battery:
    """A booted device on its main screen with the helpers of these cases."""

    def __init__(self, payload, flash=None, adapter=False, files=None, load=None):
        self.synth = synthaddr.is_synth(payload)
        self.wait = 10.0 if self.synth else 2.0
        if load is None:
            self.dev = mc.boot(payload, flash, files=files or mc.CARD_FOLDER, adapter=adapter, seconds=self.wait)
        else:
            self.dev = mc.Dev(payload, flash, 0)
            self.dev.m.adapter = adapter
            self.dev.m.insert_card(mc.SDCard(mc.MemoryMedium(load)))
            self.dev.run(self.wait + 2.0)
            mc.keep_awake(self.dev)

    def byte(self, addr):
        return self.dev.read(addr, 1)[0]

    def raw(self, addr, n):
        """Bytes at an address read out of the running firmware (no translation for the blue)."""
        return bytes(self.dev.m.uc.mem_read(addr, n))

    def word(self, addr):
        return struct.unpack("<I", self.raw(addr, 4))[0]

    def model(self):
        return self.dev.u32(BATTERY_MODEL)

    def table(self):
        """The four thresholds the battery model uses now, full first; a reading at or below the last one is empty."""
        return self.raw(self.word(self.model() + 0x318), 4)

    def thresholds(self):
        """(full, empty): the first and the last byte of that table."""
        table = self.table()
        return table[0], table[3]

    def window(self):
        """The window over the screen (the firmware's low battery warning is one), 0 without."""
        return self.word(self.dev.u32(mc.SCREEN_MANAGER) + 0x24)

    def dismiss(self):
        """EXIT on a window over the main screen (the low battery warning stays until then)."""
        if self.window():
            self.dev.press("exit", 0.4)
            self.dev.run(0.3)

    def battery_type(self):
        return self.raw(self.dev.u32(GLOBALS) + 4 + 0x20, 1)[0]

    def set_type(self, value):
        """BATTERY TYPE on its page of GLOBAL PARAMETERS, as a user turns it, then back to the main screen."""
        d = self.dev
        mc.go(d, GLOBAL_SCREEN)
        for _ in range(30):
            if mc.counter(d)[0] == BATTERY_TYPE_PAGE:
                break
            d.press(mc.KEYS["edit_next"], 0.25)
        d.turn(1 if value else -1, wait=0.4)
        mc.leave_to_main(d)
        d.run(0.5)
        return self.battery_type()

    def expected(self, raw):
        """The step the placeholder curve gives for a steady reading: linear between the table's empty and full threshold."""
        full, empty = self.thresholds()
        tenths = max(0, min(1000, (raw - empty) * 1000 // (full - empty)))
        return (tenths + 50) // 100 * 10

    def switch(self, on):
        flags = self.byte(mc.MX_FLAGS2)
        self.dev.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags & ~FLAGS2_BATT_OFF if on else flags | FLAGS2_BATT_OFF]))

    def fresh(self, raw):
        """`raw` as the reading, then the switch off and on again: the next frame starts from this reading, no smoothing. A
        reading of level 1 brings the firmware's low battery warning, it is closed before the columns are read."""
        self.dev.m.battery(raw)
        self.dev.run(0.3)
        self.switch(False)
        self.dev.run(0.1)
        self.switch(True)
        self.dev.run(0.3)
        self.dismiss()
        return self.byte(BP_SHOWN), columns(self.dev)

    def shown(self):
        return self.byte(BP_SHOWN), self.byte(BP_DRAWN), columns(self.dev)


def display_cases(payload, flash, png):
    out = []
    build = "synth" if synthaddr.is_synth(payload) else mc.firmware.build_of(payload)
    b = Battery(payload, flash)
    d = b.dev
    full, empty = b.thresholds()

    # Ni-MH (the emulator's start): nothing drawn, with a full reading in (no low battery warning)
    d.m.battery(full + 1)
    d.run(1.0)
    nimh = b.battery_type(), b.shown()
    out.append(entry("hidden_with_nimh", nimh[0] == 0 and nimh[1][1] != 1 and not any(nimh[1][2]) and not d.m.asserts,
                     f"build {build}: BATTERY TYPE {nimh[0]}, (shown, drawn, columns) {nimh[1][0]}, {nimh[1][1]}, {nimh[1][2].hex()}"))

    kind = b.set_type(1)
    full, empty = b.thresholds()
    mid = (full + empty) // 2
    b.fresh(mid)                # the Ni-MH reading above is past Alkali's full: smoothed, the value would walk down from 100
    d.run(0.7)
    got = b.shown()
    want = b.expected(mid)
    out.append(entry("shown_on_alkali_battery", kind == 1 and got[0] == want and got[1] == 1 and got[2] == glyphs(want) and not d.m.asserts,
                     f"build {build}: BATTERY TYPE {kind}, table full {full} empty {empty}, reading {mid}: shown {got[0]} (want {want}), "
                     f"drawn {got[1]}, columns {got[2].hex()}"))
    if png:
        d.m.png(str(Path(png) / f"{build}-battery-shown.png"))

    # steps of 10: every reading from just above empty to past full gives the placeholder's step, drawn as such
    steps, bad = [], []
    for raw in sorted({empty + 1, empty + (full - empty) // 4, mid, full - 2, full, full + 20, 255}):
        value, cols = b.fresh(raw)
        steps.append((raw, value))
        if value != b.expected(raw) or value % 10 or cols != glyphs(value):
            bad.append((raw, value, b.expected(raw), cols.hex()))
    out.append(entry("steps_of_10", not bad and steps[0][1] == 0 and steps[-1][1] == 100 and not d.m.asserts,
                     f"build {build}: (reading, shown) {steps}, wrong {bad}"))

    # smoothing: one dip of a smoothing step (to level 2, no warning) leaves the value, a lasting change walks there in steps
    start, _ = b.fresh(mid)
    d.m.battery(b.table()[2] + 1)
    d.run(STEP_S)
    d.m.battery(mid)
    d.run(2.0)
    after_dip = b.byte(BP_SHOWN)
    d.m.battery(full)
    d.run(0.1)
    right_after = b.byte(BP_SHOWN)
    walk = []
    for _ in range(40):
        d.run(STEP_S)
        if not walk or walk[-1] != b.byte(BP_SHOWN):
            walk.append(b.byte(BP_SHOWN))
    out.append(entry("smoothed", after_dip == start and right_after == start and walk[-1] == 100 and len(walk) >= 3
                     and walk == sorted(walk) and all(v % 10 == 0 for v in walk) and columns(d) == glyphs(100) and not d.m.asserts,
                     f"build {build}: steady {start}, after one dip {after_dip}, 0.1 s after the reading went up {right_after}, "
                     f"then {walk}"))

    # mains: gone at once, back on battery it comes again
    d.m.power_source(True)
    d.run(0.4)
    mains = b.shown()
    d.m.power_source(False)
    d.m.battery(mid)
    d.run(0.6)
    back = b.shown()
    out.append(entry("hidden_on_mains", mains[1] != 1 and not any(mains[2]) and back[1] == 1 and back[2] == glyphs(b.expected(mid))
                     and not d.m.asserts,
                     f"build {build}: on mains (drawn, columns) {mains[1]}, {mains[2].hex()}; on battery again {back[0]}, {back[2].hex()}"))

    # LOAD METER on and a card in: every one keeps its columns
    flags = b.byte(mc.MX_FLAGS2)
    d.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags | 1]))
    d.run(2.5)
    load = b.byte(LM_VALUE)
    tens = FONT[load // 10 * 4:load // 10 * 4 + 4] if load >= 10 else bytes(4)
    layout = (columns(d) == glyphs(b.expected(mid)), columns(d, LOAD_COLS) == tens + FONT[load % 10 * 4:load % 10 * 4 + 4],
              any(columns(d, CARD_COLS)), any(columns(d, SYMBOL_COLS)), not any(columns(d, range(99, 100))))
    out.append(entry("layout_with_load_meter_and_card", all(layout) and not d.m.asserts,
                     f"build {build}: (battery digits, load meter {load}, card, battery symbol, column 99 free) {layout}, "
                     f"page 0 {bytes(d.m.fb[0]).hex()}"))
    if png:
        d.m.png(str(Path(png) / f"{build}-battery-with-load-meter.png"))

    # OFF while shown: gone at the next frame
    b.switch(False)
    d.run(0.2)
    off = b.shown()
    out.append(entry("off_hides_at_once", off[1] == 0 and not any(off[2]) and not d.m.asserts,
                     f"build {build}: (drawn, columns) {off[1]}, {off[2].hex()}"))
    return out


def page_cases(payload, flash):
    out = []
    build = "synth" if synthaddr.is_synth(payload) else mc.firmware.build_of(payload)
    b = Battery(payload, flash)
    d = b.dev
    b.set_type(1)
    full, empty = b.thresholds()
    mid = (full + empty) // 2
    d.m.battery(mid)
    d.run(1.0)
    before = b.shown()

    mc.goto_group(d, mc.GROUP_DISPLAY, 6)
    first = mc.texts_of(d), mc.counter(d), b.byte(mc.MX_FLAGS2) & FLAGS2_BATT_OFF
    in_menu = b.byte(BP_DRAWN)  # the menu's own header is in those columns
    mc.press(d, "write", wait=0.6)
    d.run(3.0)
    on_rec = newest_settings(d.m.mmc.card.medium.data)
    out.append(entry("page_default_on", first == (("BATTERY %", "ON", ""), (6, 7), 0) and before[1] == 1 and in_menu == 0
                     and on_rec is not None and on_rec[4] == 3 and not on_rec[7] & FLAGS2_BATT_OFF and not d.m.asserts,
                     f"build {build}: on the main screen before (shown, drawn) {before[:2]}, page {first}, drawn in the menu "
                     f"{in_menu}, WRITE with ON wrote (version, byte 7) {None if on_rec is None else (on_rec[4], on_rec[7])}"))

    d.turn(-1, wait=0.4)
    off_page = mc.texts_of(d)[1], b.byte(mc.MX_FLAGS2) & FLAGS2_BATT_OFF
    mc.press(d, "write", wait=0.6)
    d.run(3.0)
    rec = newest_settings(d.m.mmc.card.medium.data)
    written = bytearray(d.m.mmc.card.medium.data)
    mc.leave_to_main(d)
    d.run(1.0)
    main = b.shown()
    out.append(entry("page_off_hides_on_the_main_screen", off_page == ("OFF", FLAGS2_BATT_OFF) and main[1] == 0 and not any(main[2])
                     and not d.m.asserts,
                     f"build {build}: page after the dial down {off_page}, on the main screen (drawn, columns) {main[1]}, {main[2].hex()}"))
    out.append(entry("write_off_is_version_4", rec is not None and rec[4] == 4 and rec[7] & FLAGS2_BATT_OFF,
                     f"build {build}: newest file (version, byte 7) {None if rec is None else (rec[4], rec[7])}"))

    again = Battery(payload, flash, load=written)
    a = again.dev
    flags = again.byte(mc.MX_FLAGS2)
    again.set_type(1)
    a.m.battery(mid)
    a.run(1.0)
    stays_off = again.shown()
    again.switch(True)
    a.run(0.5)
    on_again = again.shown()
    out.append(entry("next_start_reads_off", flags & FLAGS2_BATT_OFF and stays_off[1] != 1 and not any(stays_off[2])
                     and on_again[1] == 1 and on_again[2] == glyphs(again.expected(mid)) and not a.m.asserts,
                     f"build {build}: byte 7 {flags:#x}, Alkali on battery (drawn, columns) {stays_off[1]}, {stays_off[2].hex()}, "
                     f"the bit cleared {on_again[0]}, {on_again[2].hex()}"))
    return out


def cases(payload, flash=None, png=None):
    """All BATTERY % cases on `payload` (the image behind the 256-byte header), as menu_cases.look_parts calls them."""
    mc.for_build(payload)
    return display_cases(payload, flash, png) + page_cases(payload, flash)


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
