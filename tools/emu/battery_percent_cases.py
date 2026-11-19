"""Emulator cases of BATTERY % (CUSTOMIZATION > DISPLAY, tools/patch/script_battery.s): the battery's charge in steps of 10
percent on the main screen's top row, right before the battery symbol. Shown only on battery with Global BATTERY TYPE Alkali; on
mains power and with Ni-MH nothing is drawn. The battery reading comes in as panel message 6 (machine.battery), mains or
battery as message 7 (machine.power_source). The value is smoothed: a short dip leaves it, a lasting change walks there in
steps. The page is ON by default, OFF takes the digits away at once, WRITE keeps OFF as bit 4 of byte 7 (version 4), ON writes
version 3, and the next start reads it. With LOAD METER on and a card in, the digits, the load meter, the card and the battery
symbol each keep their own columns.

The card symbol sits at 94 on the main screen while the percent is wanted and at the firmware's 109 everywhere else and without
the percent (script_battery.s:card_place, card_main_x): in the menus the EDIT icon fills 84 to 97. The card cases boot with and
without a card, move the card back and forth with mains, Ni-MH and the switch, pull and put in a card on the main screen,
go into the BLECH menu and GLOBAL PARAMETERS and back, open the firmware's WRITE question and Blechy's app, with LOAD METER off
and on. The card's picture is taken from the display at 109 in a menu, the menus' columns 84 to 99 from the boot without a card.

The mapping from reading to percent is batt_curve (measured on a device, its top estimated) between the empty and the full
threshold of the firmware's Alkali table, read from the firmware's battery model at run time.

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
COLS = range(101, 117)                          # page 0: four slots of 3 columns and a blank one (hundreds, tens, ones, %)
LOAD_COLS, CARD_COLS, SYMBOL_COLS = range(86, 94), range(94, 100), range(117, 128)
KORG_CARD_COLS, MENU_COLS = range(109, 115), range(84, 100)   # the card where the firmware has it, the EDIT icon and right of it
FLAGS2_BATT_OFF = 16                            # bit 4 of byte 7 of the settings (script_menu.s:FLAGS2_BATT_OFF)
FONT = bytes([0xFE, 0x82, 0xFE, 0, 0x84, 0xFE, 0x80, 0, 0xF2, 0x92, 0x9E, 0, 0x92, 0x92, 0xFE, 0, 0x1E, 0x10, 0xFE, 0,
              0x9E, 0x92, 0xF2, 0, 0xFE, 0x92, 0xF2, 0, 0x02, 0x02, 0xFE, 0, 0xFE, 0x92, 0xFE, 0, 0x9E, 0x92, 0xFE, 0])
PERCENT = bytes([0x42, 0x38, 0x84, 0])
STEP_S = 0.25                                   # one smoothing step (script_battery.s:BP_STEP_MS)
FULL = int((ROOT / "tools/patch/script_battery.s").read_text().split(".equ BP_FULL,")[1].split(";")[0])
CURVE = [int(v) for v in (ROOT / "tools/patch/script_battery.s").read_text().split("batt_curve:")[1].split(".word")[1]
         .splitlines()[0].split(",")]           # batt_curve, the charge in per mille at 0, 10, ... 100 percent of the way


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


def no_digits(cols, card):
    """The digit columns without the percent: blank but for the card back at Korg's 109 (`card` its picture, blank without one)."""
    return cols == bytes(KORG_CARD_COLS.start - COLS.start) + card + bytes(COLS.stop - KORG_CARD_COLS.stop)


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
        """(full, empty): BP_FULL from the patch and the last byte of that table."""
        return FULL, self.table()[3]

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
        """The step `batt_curve` gives for a steady reading, as the frame computes it: the place between the table's empty and
        full threshold in per mille, the curve's segment and the place in it, rounded to 10."""
        full, empty = self.thresholds()
        place = max(0, min(1000, (raw - empty) * 1000 // (full - empty)))
        seg, rest = divmod(place, 100)
        charge = CURVE[seg] if seg == 10 else CURVE[seg] + (CURVE[seg + 1] - CURVE[seg]) * rest // 100
        return (charge + 50) // 100 * 10

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
    card = columns(d, KORG_CARD_COLS)       # without the percent the card is at Korg's 109
    out.append(entry("hidden_with_nimh", nimh[0] == 0 and nimh[1][1] != 1 and any(card) and no_digits(nimh[1][2], card)
                     and not d.m.asserts,
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

    # steps of 10: every reading from just above empty to past full gives batt_curve's step, drawn as such
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
    out.append(entry("hidden_on_mains", mains[1] != 1 and no_digits(mains[2], card) and back[1] == 1 and back[2] == glyphs(b.expected(mid))
                     and not d.m.asserts,
                     f"build {build}: on mains (drawn, columns) {mains[1]}, {mains[2].hex()}; on battery again {back[0]}, {back[2].hex()}"))

    # LOAD METER on and a card in: every one keeps its columns
    flags = b.byte(mc.MX_FLAGS2)
    d.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags | 1]))
    d.run(2.5)
    load = b.byte(LM_VALUE)
    tens = FONT[load // 10 * 4:load // 10 * 4 + 4] if load >= 10 else bytes(4)
    layout = (columns(d) == glyphs(b.expected(mid)), columns(d, LOAD_COLS) == tens + FONT[load % 10 * 4:load % 10 * 4 + 4],
              any(columns(d, CARD_COLS)), any(columns(d, SYMBOL_COLS)), not any(columns(d, range(100, 101))))
    out.append(entry("layout_with_load_meter_and_card", all(layout) and not d.m.asserts,
                     f"build {build}: (battery digits, load meter {load}, card, battery symbol, column 100 free) {layout}, "
                     f"page 0 {bytes(d.m.fb[0]).hex()}"))
    if png:
        d.m.png(str(Path(png) / f"{build}-battery-with-load-meter.png"))

    # OFF while shown: gone at the next frame
    b.switch(False)
    d.run(0.2)
    off = b.shown()
    out.append(entry("off_hides_at_once", off[1] == 0 and no_digits(off[2], card) and not d.m.asserts,
                     f"build {build}: (drawn, columns) {off[1]}, {off[2].hex()}"))
    return out


def card_cases(payload, flash, png):
    """The card symbol moved to 94 on the main screen only: with and without a card, through the menus, a window and an app."""
    out = []
    build = "synth" if synthaddr.is_synth(payload) else mc.firmware.build_of(payload)
    wait = 10.0 if synthaddr.is_synth(payload) else 2.0

    def main(d):
        return columns(d, CARD_COLS), columns(d, KORG_CARD_COLS)

    def menus(d):
        """(BLECH menu, GLOBAL PARAMETERS): columns 84 to 99 and 109 to 114 in each, back on the main screen after each."""
        got = []
        for enter in (lambda: mc.goto_group(d, mc.GROUP_DISPLAY, 6), lambda: mc.go(d, GLOBAL_SCREEN)):
            enter()
            d.run(0.5)
            got.append((columns(d, MENU_COLS), columns(d, KORG_CARD_COLS)))
            mc.leave_to_main(d)
            d.run(0.5)
            got.append(main(d))
        return got

    # without a card: nothing at 94 or 109 on the main screen, the menus' columns as reference for the boot with a card
    n = mc.boot(payload, flash, card=False, seconds=wait)
    empty_boot = main(n)
    bare = menus(n)
    blank = bytes(6)
    out.append(entry("card_none", empty_boot == (blank, blank) and all(m[1] == blank for m in bare[0::2])
                     and all(m == (blank, blank) for m in bare[1::2]) and not n.m.asserts,
                     f"build {build}: main (94, 109) {empty_boot[0].hex()} {empty_boot[1].hex()}, menus and back "
                     f"{[(a.hex(), b.hex()) for a, b in bare]}"))

    # with a card: its picture at 109 in GLOBAL PARAMETERS; on the main screen at 109 after the boot (Ni-MH, no percent), at 94
    # once Alkali brings the percent; the menus' 84 to 99 as without a card
    b = Battery(payload, flash)
    d = b.dev
    booted = main(d)
    mc.go(d, GLOBAL_SCREEN)
    d.run(0.5)
    card = columns(d, KORG_CARD_COLS)
    mc.leave_to_main(d)
    d.run(0.5)
    kind = b.set_type(1)
    full, empty = b.thresholds()
    d.m.battery((full + empty) // 2)
    d.run(1.0)
    alkali = main(d)
    digits = glyphs(b.expected((full + empty) // 2))[KORG_CARD_COLS.start - COLS.start:KORG_CARD_COLS.stop - COLS.start]
    out.append(entry("card_boot_at_94", any(card) and booted == (blank, card) and kind == 1 and alkali == (card, digits)
                     and not d.m.asserts,
                     f"build {build}: the card at 109 in a menu {card.hex()}, on the main screen after the boot (94, 109) "
                     f"{booted[0].hex()} {booted[1].hex()}, with Alkali {alkali[0].hex()} {alkali[1].hex()}"))

    # the percent gone and back: the card goes to 109 and comes back to 94, with nothing left at the other place
    moves = []
    for name, gone, back in (("mains", lambda: d.m.power_source(True), lambda: d.m.power_source(False)),
                             ("switch", lambda: b.switch(False), lambda: b.switch(True))):
        gone()
        d.run(0.6)
        away = main(d)
        back()
        d.m.battery((full + empty) // 2)
        d.run(0.6)
        moves.append((name, away, main(d), b.shown()[2]))
    kind = b.set_type(0)
    d.run(0.6)
    nimh = main(d)
    b.set_type(1)
    d.run(0.6)
    moves.append(("nimh", nimh, main(d), b.shown()[2]))
    want = glyphs(b.expected((full + empty) // 2))
    out.append(entry("card_follows_the_percent", all(m[1] == (blank, card) and m[2] == (card, digits) and m[3] == want for m in moves)
                     and kind == 0 and not d.m.asserts,
                     f"build {build}: (what, without the percent (94, 109), with it again, digits) "
                     f"{[(m[0], m[1][0].hex(), m[1][1].hex(), m[2][0].hex(), m[2][1].hex(), m[3].hex()) for m in moves]}"))

    flags = b.byte(mc.MX_FLAGS2)
    for meter in (0, 1):
        d.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags & ~1 | meter]))
        d.run(1.0)
        got = menus(d)
        ok = all(m == (bare[2 * i][0], card) for i, m in enumerate(got[0::2])) and all(m == (card, digits) for m in got[1::2])
        out.append(entry(f"card_menus_load_meter_{'on' if meter else 'off'}", ok and not d.m.asserts,
                         f"build {build}: BLECH menu (84 to 99, 109) {got[0][0].hex()} {got[0][1].hex()} (without a card "
                         f"{bare[0][0].hex()}), back (94, 109) {got[1][0].hex()} {got[1][1].hex()}; GLOBAL PARAMETERS "
                         f"{got[2][0].hex()} {got[2][1].hex()} (without a card {bare[2][0].hex()}), back {got[3][0].hex()} "
                         f"{got[3][1].hex()}"))
    d.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags]))

    # pulled and put in on the main screen
    d.m.eject_card()
    d.run(1.5)
    pulled = main(d)
    d.m.insert_card(mc.SDCard(mc.MemoryMedium(mc.card_image(mc.CARD_FOLDER))))
    d.run(3.0)
    inserted = main(d)
    out.append(entry("card_pull_and_insert_on_main", pulled == (blank, digits) and inserted == (card, digits) and not d.m.asserts,
                     f"build {build}: pulled (94, 109) {pulled[0].hex()} {pulled[1].hex()}, put in {inserted[0].hex()} "
                     f"{inserted[1].hex()}"))

    # the WRITE question (its own screen): the card at 109, then back at 94
    mc.press(d, "write", wait=0.6)
    question = main(d)
    mc.press(d, "exit", wait=0.6)
    d.run(1.0)
    after = main(d)
    out.append(entry("card_write_question", question == (blank, card) and after == (card, digits) and not d.m.asserts,
                     f"build {build}: in the question (94, 109) {question[0].hex()} {question[1].hex()}, after it "
                     f"{after[0].hex()} {after[1].hex()}"))

    # Blechy's app open: no card at 94 over it; closed, the card is back at 94
    mc.goto_blechy(d)
    mc.press(d, "menu", wait=0.8)
    d.run(1.0)
    app = mc.open_app_entry(d), main(d)
    if png:
        d.m.png(str(Path(png) / f"{build}-card-app.png"))
    mc.press(d, "exit", wait=0.6)
    d.run(1.0)
    closed = mc.open_app_entry(d), main(d)
    out.append(entry("card_app", app[0] and app[1][0] != card and closed == (0, (card, digits)) and not d.m.asserts,
                     f"build {build}: app {app[0]:#x} (94, 109) {app[1][0].hex()} {app[1][1].hex()}, closed {closed[0]:#x} "
                     f"{closed[1][0].hex()} {closed[1][1].hex()}"))
    return out


def page_cases(payload, flash):
    out = []
    build = "synth" if synthaddr.is_synth(payload) else mc.firmware.build_of(payload)
    b = Battery(payload, flash)
    d = b.dev
    card = columns(d, KORG_CARD_COLS)       # Ni-MH after the boot: the card at Korg's 109
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
    out.append(entry("page_off_hides_on_the_main_screen", off_page == ("OFF", FLAGS2_BATT_OFF) and main[1] == 0 and no_digits(main[2], card)
                     and not d.m.asserts,
                     f"build {build}: page after the dial down {off_page}, on the main screen (drawn, columns) {main[1]}, {main[2].hex()}"))
    out.append(entry("write_off_is_version_4", rec is not None and rec[4] == 4 and rec[7] & FLAGS2_BATT_OFF,
                     f"build {build}: newest file (version, byte 7) {None if rec is None else (rec[4], rec[7])}"))

    again = Battery(payload, flash, load=written)
    a = again.dev
    flags = again.byte(mc.MX_FLAGS2)
    card = columns(a, KORG_CARD_COLS)
    again.set_type(1)
    a.m.battery(mid)
    a.run(1.0)
    stays_off = again.shown()
    again.switch(True)
    a.run(0.5)
    on_again = again.shown()
    out.append(entry("next_start_reads_off", flags & FLAGS2_BATT_OFF and stays_off[1] != 1 and no_digits(stays_off[2], card)
                     and on_again[1] == 1 and on_again[2] == glyphs(again.expected(mid)) and not a.m.asserts,
                     f"build {build}: byte 7 {flags:#x}, Alkali on battery (drawn, columns) {stays_off[1]}, {stays_off[2].hex()}, "
                     f"the bit cleared {on_again[0]}, {on_again[2].hex()}"))
    return out


def cases(payload, flash=None, png=None):
    """All BATTERY % cases on `payload` (the image behind the 256-byte header), as menu_cases.look_parts calls them."""
    mc.for_build(payload)
    return display_cases(payload, flash, png) + card_cases(payload, flash, png) + page_cases(payload, flash)


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
