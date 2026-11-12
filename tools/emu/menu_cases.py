"""Emulator checks for the BLECH menu screen (tools/patch/script_menu.s).

check.py runs `menu_cases` on every patched copy that carries the menu: the
screen sits in the Edit ring between Global and Data Util, the page counter
stays gap-free, WRITE opens no pattern window, EXIT returns to the main screen,
and with EXIT held at power-on the firmware's ring is the stock one.

    tools/emu/.venv/bin/python tools/emu/menu_cases.py cases --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin]
"""
import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.patch import load_bar, script_hooks  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
import fat32  # noqa: E402
import synthaddr  # noqa: E402
import firmware  # noqa: E402
from splash_cases import Dev, SWITCH_SCREEN  # noqa: E402
from unicorn import arm_const  # noqa: E402

HEADER = 0x100
IMAGE = 0xC0000000
MENU = 0x2D
STATE = script_hooks.MENU_STATE
HW_TEMPO = 0xC0691518            # the tempo in tenths of a BPM (tools/patch/script_hw.s)
S_ON, S_PAGE, S_ENTER, S_COUNT, S_RUN, S_MFX = 0, 4, 8, 12, 16, 20
S_SET_RUN, S_SET_MFX = S_RUN, S_MFX
S_TITLE, S_VALUE, S_LINE3 = 0x40, 0x60, 0x80
COUNTER_VTABLE = 0xC00E5218
UI_MANAGER = 0xC06C2220
UI_REDRAW = 0xC06C226C
KILL = 0x2000
KEYS = {"menu": 0x09, "edit_prev": 0x08, "edit_next": 0x0C, "exit": 0x0D, "write": 0x0E}


def has_menu(payload):
    """True when the screen factory reads its table from our copy."""
    literal = 0xC0061B90 if synthaddr.is_synth(payload) else 0xC006E68C
    return struct.unpack_from("<I", payload, literal - IMAGE)[0] == script_hooks.MENU_TABLE


def for_build(payload):
    global MENU, RING, BASE_RING, SYNC_GROUP, DU_FUNCS, FX_EXPORT
    synth = synthaddr.is_synth(payload)
    FX_EXPORT = not synth              # EXPORT ALL EFFECTS: only the Sampler builds have the collection on the card
    DU_FUNCS = 11 if synth else 14     # the functions of DATA UTILITY's list (screen 15), the blue has no sample functions
    SYNC_GROUP = True                  # the page SYNC GROUP is in the ring on both (the synth since 24.10.)
    MENU = 37 if synth else 45
    BASE_RING = 28 if synth else 29
    RING = BASE_RING + 2 + (1 if SYNC_GROUP else 0)


def card_image(files=None):
    img = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(img)
    for path, data in (files or {}).items():
        volume.write(path, data)
    volume.close()
    return img


def boot(payload, flash=None, held=0, files=None, adapter=False, card=True, seconds=1.2):
    """A device booted to the main screen; with `adapter` on mains power (the bottom LEDs and the backlight show their normal state)."""
    global INIT_PAGE, LAST_PAGE, STEREO_PAGE
    for_build(payload)
    INIT_PAGE = payload[INIT_CODE - 0xC0000000:INIT_CODE - 0xC0000000 + 4] != b"\xff" * 4
    LAST_PAGE = payload[LAST_CODE - 0xC0000000:LAST_CODE - 0xC0000000 + 4] != b"\xff" * 4
    STEREO_PAGE = payload[STEREO_CODE - 0xC0000000:STEREO_CODE - 0xC0000000 + 4] != b"\xff" * 4
    dev = Dev(payload, flash, held)
    dev.m.adapter = adapter
    if card:
        dev.m.insert_card(SDCard(MemoryMedium(card_image(files))))
    dev.run(seconds)
    return dev


def state(dev, offset):
    return dev.u32(STATE + offset)


def text(dev, offset):
    return dev.read(STATE + offset, 32).split(b"\0")[0].decode("latin-1")


def screen_object(dev):
    return dev.m.u32(dev.a(UI_MANAGER) + 0x10)


def counter(dev):
    """(index, total) of the page counter of the screen shown, or None."""
    obj = screen_object(dev)
    if not obj:
        return None
    begin, end = dev.u32(obj + 0x10), dev.u32(obj + 0x14)
    for at in range(begin, end, 4):
        widget = dev.u32(at)
        if widget and dev.u32(widget) == dev.a(COUNTER_VTABLE):
            return dev.u32(widget + 0x38), dev.u32(widget + 0x3C)
    return None


def go(dev, number):
    dev.call(SWITCH_SCREEN, number, 0)
    dev.run(0.4)


def press(dev, key, wait=0.25):
    dev.press(key, wait=wait)


GROUP_PLUGINS, GROUP_GAMES, GROUP_TOOLS, GROUP_CUSTOM, GROUP_FEATURES, GROUP_DISPLAY, GROUP_LED, GROUP_PADS, GROUP_PSAVE, GROUP_SPLASH = range(10)
CUSTOM_DISPLAY, CUSTOM_LED, CUSTOM_PADS, CUSTOM_PSAVE, CUSTOM_SPLASH = 0, 1, 2, 3, 4   # the rows of CUSTOMIZATION, each a group; SPLASH holds IMPORT, DRAW and RESET
S_LEVEL, S_GROUP, S_RAW, S_TOP, S_TABW = 0xE0, 0xE4, 0xE8, 0xEC, 0xF0
TAB_TEXT_POINTER = 0x38                                               # the tab widget keeps a pointer to its text at this offset
LIST_PAGES = ["FEATURES", "PLUGINS", "CUSTOMIZATION"]                 # the groups of level 1 of a menu without apps, in this order; GAMES and TOOLS follow when an app is declared in them
LIST_GROUPS = LIST_PAGES
LIST_FEATURES, LIST_PLUGINS, LIST_CUSTOM = range(3)                   # their places in that list
FEATURE_PAGES = ["MFX 2", "PATTERN CONFIRM", "TAP MOTION", "NOTE ASSIST"]   # the pages of the group FEATURES, each with an ON/OFF value
FEAT_MFX, FEAT_PC, FEAT_TM, FEAT_NA = range(len(FEATURE_PAGES))
SYNC_GROUP = True
SYNC_GROUP_AT = 0x3B80                                                # the group in a pattern block, u16 little endian


INIT_CODE = 0xC014FD00                                               # the patch init-pattern (tools/patch/init_pattern.py); with it our pages of DATA UTILITY end with SET INIT PATTERN
INIT_PAGE = False                                                     # set by boot(): whether the copy has the patch
LAST_CODE = 0xC014FE00                                               # the patch last-pattern (tools/patch/last_pattern.py); with it FEATURES has LAST PATTERN
LAST_PAGE = False                                                     # set by boot(): whether the copy has the patch
STEREO_CODE = 0xC014FF00                                             # the patch stereo-pad (tools/patch/stereo_pad.py); with it FEATURES ends with STEREO 1 PAD
STEREO_PAGE = False                                                   # set by boot(): whether the copy has the patch


VERSION_TEXT = 0xC014FCF0                                            # the patch blech-version (tools/patch/blech_version.mjs): the title of VERSION
LIST_VERSION = len(LIST_PAGES)                                       # VERSION, the last row of the list (behind GAMES and TOOLS where an app is declared)
LIST_COUNT = LIST_VERSION + 1
BASE_NAMES = {"hacktribe": "HACKTRIBE", "stock": "KORG RED", "synth": "KORG BLUE"}   # the value of VERSION: the firmware the runtime is built for


def version_texts(payload):
    """(title, value) of BLECH > VERSION for a copy: the version text the set wrote (BLECH where it has no blech-version) and its firmware."""
    raw = bytes(payload[VERSION_TEXT - IMAGE:VERSION_TEXT - IMAGE + 16])
    title = "BLECH" if raw[0] == 0xFF else raw.split(b"\0")[0].decode("latin-1")
    build = "synth" if synthaddr.is_synth(payload) else firmware.build_of(payload)
    return title, BASE_NAMES[build]


def feature_pages():
    """The pages of FEATURES: the switches, LAST PATTERN and STEREO 1 PAD where the set has their patches, KEY PADS, FILTER
    TOGGLE and AUTO SAVE last (SYNC GROUP is a page of the ring, LEVEL_SYNC; SET INIT PATTERN is in DATA UTILITY)."""
    return FEATURE_PAGES + ["LAST PATTERN"] * LAST_PAGE + ["STEREO 1 PAD"] * STEREO_PAGE + ["KEY PADS", "FILTER TOGGLE", "AUTO SAVE"]


def feature_count():
    return len(feature_pages())


FX_EXPORT = True


def du_pages():
    """Our pages of DATA UTILITY, behind the firmware's functions: EXPORT ALL CUSTOMIZATIONS (its title is cut to fit), EXPORT ALL
    PLUGINS, EXPORT ALL EFFECTS on the Sampler builds, and SET INIT PATTERN where the set has the patch."""
    return ["EXPORT ALL CUSTOM", "EXPORT ALL PLUGINS"] + ["EXPORT ALL EFFECTS"] * FX_EXPORT + ["SET INIT PATTERN"] * INIT_PAGE
TAB_LABELS = ["BLECH", "Plugins", "Games", "Tools", "Custom", "Feature", "Display", "LED", "Pads", "Power", "Splash", "Pattern", "Global"]
FIRMWARE_TAB = "Data Util"                                            # the firmware's own label, already at the edge of its box: ours has to look the same, not have room to spare
RING = 32                                                             # the total of the page counter with the page BLECH, the page of Blechy and SYNC GROUP in the ring
BASE_RING = 29
SYNC_AT = 15                                                          # the counter's index of SYNC GROUP (16/32): behind CHAIN REPEAT, the Part menu moves up by one
LEVEL_BLECHY = 3                                                      # level 3 of the screen: the page of Blechy, the last of the ring
LEVEL_SYNC = 4                                                        # level 4: the page SYNC GROUP between the Pattern menu and the Part menu
LEVEL_PLUGIN = 5                                                      # level 5: MANAGE PLUGINS, one page a plugin
LEVEL_PSUB = 6                                                        # level 6: the pages of one plugin: ACTIVE, DESCRIPTION, the pages it added, REMOVE
LEVEL_GLOBAL = 7                                                      # level 7: PLUGIN RUNTIME, the last page of GLOBAL PARAMETERS (21/21)
LEVEL_DU = 8                                                          # level 8: our pages of DATA UTILITY, behind the firmware's functions
GLOBAL_PAGES = 20                                                     # the firmware's pages of GLOBAL PARAMETERS (screen 9)
S_PSEL = 0xFB                                                         # byte: the plugin the pages of level 6 are about (the page of level 5 it was opened from)
S_BRW_ON = 0x154                                                      # byte: M_BRW_ON, nonzero while the page shows as the firmware's file browser
PLUGIN_MANAGE = 0                                                     # the one page of PLUGINS: MANAGE PLUGINS
PLUGIN_ACTIVE = 0                                                     # the first page of one plugin: ACTIVE, the dial switches it ON and OFF
PLUGIN_DESCRIPTION = 1                                                # the second page; the pages it added follow, REMOVE is the last
PRESS = "press  [ Enter ]"                                            # the third line of every Data Util page
VALUE_ROWS = range(30, 64)                                           # the pixel rows the value (and the firmware's third line) use
TAB_ROWS = range(1, 9)                                               # the rows of the tab's text, inside the black bar
MENU_WIDGET, COUNTER_WIDGET = 0x24, 0x28
SET_TITLE, SET_VALUE, SET_LINE3, SET_COUNTER = 0xC00857E4, 0xC0085828, 0xC0085888, 0xC008A8A8


def _enter(dev, level, group=0, page=0):
    auto_save = dev.u32(STATE + 0x1FC)          # S_AS: the jump is no leaving by the player, AUTO SAVE stays out of it
    dev.m.uc.mem_write(STATE + 0x1FC, struct.pack("<I", 0))
    go(dev, 8)
    dev.m.uc.mem_write(STATE + 0x1FC, struct.pack("<I", auto_save))
    dev.m.uc.mem_write(STATE + S_LEVEL, struct.pack("<II", level, group))
    dev.m.uc.mem_write(STATE + S_ENTER, struct.pack("<I", page))
    go(dev, MENU)


def goto_ring(dev):
    """The one page BLECH in the ring of the firmware (level 0), entered fresh."""
    _enter(dev, 0)


def goto_blechy(dev):
    """The page of Blechy, the last of the ring (level 3 of the screen), entered fresh."""
    _enter(dev, LEVEL_BLECHY)


def goto_top(dev, page=0):
    """The list of the groups (level 1) at `page`, entered fresh."""
    _enter(dev, 1, 0, page)


def goto_group(dev, group, page=0):
    """The pages of `group` (level 2) at `page`, entered fresh (what ENTER on the group's row and some EDIT presses reach)."""
    _enter(dev, 2, group, page)


def goto_plugin(dev, plugin=0, page=None):
    """The page of a plugin in MANAGE PLUGINS (level 5: its name and its state, the dial moves through the list), or with `page` that
    page of its own pages (level 6: ACTIVE where the dial switches it, DESCRIPTION, the pages it added, REMOVE); `plugin` counted
    as the list counts (loaded ones first), entered fresh."""
    go(dev, 8)
    dev.m.uc.mem_write(STATE + S_PSEL, bytes([plugin]))
    if page is None:
        _enter(dev, LEVEL_PLUGIN, 0, plugin)
    else:
        _enter(dev, LEVEL_PSUB, 0, page)


def goto_global(dev):
    """PLUGIN RUNTIME, the page of GLOBAL PARAMETERS behind the firmware's last (level 7), entered fresh."""
    _enter(dev, LEVEL_GLOBAL)


def goto_du(dev, page=0):
    """Our page `page` of DATA UTILITY (level 8, du_pages()), entered fresh."""
    _enter(dev, LEVEL_DU, 0, page)


def tab(dev):
    """The text on the tab of the BLECH screen: BLECH above the groups, the group's name inside one (the tab widget points at it)."""
    widget = state(dev, S_TABW)
    return dev.read(dev.u32(widget + TAB_TEXT_POINTER), 16).split(b"\0")[0].decode("latin-1")


def texts_of(dev):
    return text(dev, S_TITLE), text(dev, S_VALUE), text(dev, S_LINE3)


def lit(fb, rows=VALUE_ROWS):
    """The set of (x, y) pixels that are on in the given rows of a display (bytes, page-major)."""
    return {(x, y) for y in rows for x in range(128) if (fb[(y // 8) * 128 + x] >> (y % 8)) & 1}


def dark(fb, rows, left=0, right=128):
    """The pixels that are off in the given rows between two columns: the white glyphs on the black bar of the tab."""
    return {(x, y) for y in rows for x in range(left, right) if not (fb[(y // 8) * 128 + x] >> (y % 8)) & 1}


def frame(dev):
    """The frame as the firmware drew it: the frame buffer, not the display (the load bar's look changes only what is sent)."""
    return dev.read(0xC031B310, 1024)


def draw_texts(dev, value, line3):
    """Draw only the given value and third line (zero-terminated texts) on the BLECH screen and return the frame: the firmware's own text widget, nothing of ours."""
    widget = dev.u32(screen_object(dev) + MENU_WIDGET)
    scratch = script_hooks.CARD + 0xF00
    dev.m.uc.mem_write(scratch, value.encode() + b"\0")
    dev.m.uc.mem_write(scratch + 64, line3.encode() + b"\0")
    dev.m.uc.mem_write(widget + ORIG_FLAG, b"\0")      # the ORIG badge is not a text of the page: it would be in both frames and count as shared pixels
    dev.call(SET_VALUE, widget, scratch)
    dev.call(SET_LINE3, widget, scratch + 64)
    dev.run(0.25)
    return frame(dev)


def draw_tab(dev, label, index=None, total=None):
    """Show `label` on the tab (optionally with another counter) and return the frame."""
    scratch = script_hooks.CARD + 0xE00
    dev.m.uc.mem_write(scratch, label.encode() + b"\0")
    dev.m.uc.mem_write(state(dev, S_TABW) + TAB_TEXT_POINTER, struct.pack("<I", scratch))
    dev.m.uc.mem_write(dev.a(UI_REDRAW), b"\1")
    if index is not None:
        counter_widget = dev.u32(screen_object(dev) + COUNTER_WIDGET)
        dev.m.uc.mem_write(STATE + S_RAW, struct.pack("<I", 1))
        dev.call(SET_COUNTER, counter_widget, index, total)
        dev.m.uc.mem_write(STATE + S_RAW, struct.pack("<I", 0))
    dev.run(0.25)
    return frame(dev)


def label_problem(dev, label, index=None, total=None):
    """None when the tab shows `label` whole with room to spare beside its counter, else what is wrong. The text is white on the
    black bar. The counter is what is left with an empty label; the label is whole when a narrow letter more still shows up
    left of the counter (a label that runs into the counter, or into the edge of its box, shows nothing more)."""
    counter_ink = dark(draw_tab(dev, "", index, total), TAB_ROWS, 0, 80)
    plain = dark(draw_tab(dev, label, index, total), TAB_ROWS, 0, 80)
    more = dark(draw_tab(dev, label + "i", index, total), TAB_ROWS, 0, 80)
    counter_left = min((x for x, _ in counter_ink), default=80)
    label_ink = plain - counter_ink
    grown = more - plain
    if not label_ink:
        return f"{label!r}: nothing shows"
    if max(x for x, _ in label_ink) >= counter_left - 1:
        return f"{label!r} reaches the counter (column {max(x for x, _ in label_ink)} of {counter_left})"
    if not grown or max(x for x, _ in grown) >= counter_left - 1:
        return f"{label!r} is cut off: another letter does not fit before the counter at column {counter_left}"
    return None


def page_overlap(dev):
    """None when the page on screen is clean, else what is wrong with it. Clean means: the third line is empty or is the Data Util
    line `press  [ Enter ]` under an empty value (the firmware draws the line from column 28 on the row of the value, so any
    value runs into it), the value alone and the line alone share no pixel, neither the title, the value nor the line reach the
    edge of the display (a text that is too wide is cut off), and the tab's label is whole beside its counter. A page shown as the
    file browser (the plugin list, SPLASH IMPORT) does not draw the three lines, so only its label is checked."""
    title, value, line3 = texts_of(dev)
    shown = frame(dev)
    wrong = []
    if dev.read(STATE + S_BRW_ON, 1)[0]:
        problem = label_problem(dev, tab(dev))
        return [problem] if problem else None
    if line3 and (line3 != PRESS or value):
        wrong.append(f"third line {line3!r} beside value {value!r}")
    only_value = lit(draw_texts(dev, value, ""))
    only_line = lit(draw_texts(dev, "", line3))
    shared = only_value & only_line
    if shared:
        wrong.append(f"{len(shared)} pixels of value {value!r} and line {line3!r} on top of each other")
    for name, rows in (("title", range(13, 30)), ("value", range(30, 47)), ("line", range(30, 47))):
        xs = [x for x, _ in (lit(shown, rows) if name != "line" else only_line)]
        if xs and (min(xs) < 2 or max(xs) > 125):
            wrong.append(f"{name} reaches the edge: columns {min(xs)} to {max(xs)}")
    problem = label_problem(dev, tab(dev)) if tab(dev) != FIRMWARE_TAB else None
    if problem:
        wrong.append(problem)
    return wrong or None


def value_row_leftovers(dev):
    """The pixels of the value row on screen that the value alone does not draw (what an earlier text left there or the third line
    drew over it), and those of the value that are missing. Redraws the value row, so call it last before the next key.
    On a file browser page the rows hold the browser, not the value: everything below the tab is held against the page drawn again
    on a blank frame."""
    if dev.read(STATE + S_BRW_ON, 1)[0]:
        shown = lit(frame(dev), range(8, 64))
        dev.m.uc.mem_write(0xC031B310 + 128, b"\0" * (1024 - 128))
        dev.m.uc.mem_write(dev.a(UI_REDRAW), b"\1")
        dev.run(0.3)
        alone = lit(frame(dev), range(8, 64))
        return shown - alone, alone - shown
    shown = lit(frame(dev), range(30, 47))
    alone = lit(draw_texts(dev, texts_of(dev)[1], ""), range(30, 47))
    return shown - alone, alone - shown


APPS_STATE_SIZE = 168                                                # SCRIPT_APPS.stateSize in data/script/contract.mjs: the table of apps ends the runtime


def apps_open_address():
    """Where the runtime keeps the word of the open app (its script entry, 0 when none): the app table is the end of the runtime area."""
    area = json.loads((ROOT / "data" / "patches" / "script-runtime.json").read_text())["ram"][0]
    return int(area["at"], 16) + area["length"] - APPS_STATE_SIZE


def open_app_entry(dev):
    """The script entry of the open app, 0 when none."""
    return dev.u32(apps_open_address())


def blechy_dark(dev):
    """On his page, with DISPLAY INVERT ON and then OFF (the page is left as it was): what the controller RAM holds against his
    picture ("plain", "complement" or "other") and whether the controller is reversed (0xA7). Either way the panel shows him
    light on dark, the complement of his picture (the LCD clears a pixel slowly, so a dark figure on a clear field smears)."""
    app = load_bar.APP_PICTURE

    def look():
        for _ in range(10):        # his picture and the controller RAM compared after the same frame
            pic, ram = dev.read(app, 1024), dev.fb()
            kind = "plain" if ram == pic else "complement" if ram == bytes(b ^ 0xFF for b in pic) else None
            if kind and dev.m.shown() == bytes(b ^ 0xFF for b in pic):
                return kind, dev.m.lcd_reverse
            dev.run(0.02)
        return "other", dev.m.lcd_reverse

    was = state(dev, S_INVERT)
    out = {}
    for name, value in (("on", 1), ("off", 0)):
        dev.m.uc.mem_write(STATE + S_INVERT, struct.pack("<I", value))
        dev.run(0.3)
        out[name] = look()
    dev.m.uc.mem_write(STATE + S_INVERT, struct.pack("<I", was))
    dev.run(0.3)
    return out


DU_FUNCS = 14


def firmware_menu_cases(dev):
    """PLUGIN RUNTIME as the last page of GLOBAL PARAMETERS and our pages behind DATA UTILITY's functions (Pascal 29.10.): EDIT goes
    through them and the firmware's pages both ways, the counters count them, EXIT goes where the firmware's EXIT goes."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    here = lambda: (dev.screen()["number"], state(dev, S_LEVEL) if dev.screen()["number"] == MENU else None, counter(dev),
                    texts_of(dev)[:2] if dev.screen()["number"] == MENU else None, tab(dev) if dev.screen()["number"] == MENU else None)
    total = GLOBAL_PAGES + 1
    go(dev, 8)
    press(dev, "menu", wait=0.5)
    first = here()
    press(dev, "edit_prev", wait=0.6)
    ours = here()
    press(dev, "edit_next", wait=0.6)
    wrapped = here()
    press(dev, "edit_prev", wait=0.6)
    press(dev, "edit_prev", wait=0.6)
    last = here()
    press(dev, "edit_next", wait=0.6)
    again = here()
    press(dev, "write", wait=0.6)
    window = dev.screen()["window"]
    press(dev, "exit", wait=0.6)
    left = dev.screen()["number"]
    want = (MENU, LEVEL_GLOBAL, (GLOBAL_PAGES, total), ("PLUGIN RUNTIME", "ON"), "Global")
    add("global_has_plugin_runtime_last", first == (9, None, (0, total), None, None) and ours == want and wrapped == first
        and last == (9, None, (GLOBAL_PAGES - 1, total), None, None) and again == want and window == 0 and left == 8 and not dev.m.asserts,
        f"first {first}, left {ours}, right {wrapped}, left twice {last}, right {again}, WRITE window {window}, EXIT to {left}")

    pages = du_pages()
    total = DU_FUNCS + len(pages)
    go(dev, 14)
    press(dev, "menu", wait=0.5)
    first = here()
    firmware_tab = dark(frame(dev), TAB_ROWS, 0, 39)
    press(dev, "edit_prev", wait=0.6)
    seen = [here()]
    our_tab = dark(frame(dev), TAB_ROWS, 0, 39)
    for _ in pages:
        press(dev, "edit_prev", wait=0.6)
        seen.append(here())
    for _ in pages:
        press(dev, "edit_next", wait=0.6)
    press(dev, "edit_next", wait=0.6)
    round_trip = here()
    press(dev, "edit_prev", wait=0.6)
    press(dev, "exit", wait=0.6)
    left = dev.screen()["number"]
    want = [(MENU, LEVEL_DU, (DU_FUNCS + i, total), None, "Data Util") for i in reversed(range(len(pages)))] + [(15, None, (DU_FUNCS - 1, total), None, None)]
    shown = [(x[0], x[1], x[2], None, x[4]) for x in seen]
    titles = [x[3][0] for x in seen[:-1]]
    add("data_util_tab_as_the_firmware", our_tab == firmware_tab and len(our_tab) > 20, f"{len(our_tab)} label pixels, the firmware's {len(firmware_tab)}, "
        f"differ {len(our_tab ^ firmware_tab)}")
    add("data_util_has_our_pages_last", first == (15, None, (0, total), None, None) and shown == want and titles == list(reversed(pages))
        and round_trip == first and left == 14 and not dev.m.asserts, f"first {first}, left through {seen}, back {round_trip}, EXIT to {left}")
    return out


def blechy_ring_cases(dev):
    """The page of Blechy, the last of the ring: after Event, before the Pattern menu, shown live and gone with EXIT."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    here = lambda: (dev.screen()["number"], state(dev, S_LEVEL), counter(dev), open_app_entry(dev) != 0)
    go(dev, 10)
    press(dev, "edit_next", wait=0.8)
    press(dev, "edit_next", wait=0.8)
    landed = here()
    picture = dev.fb()
    add("blechy_follows_blech", landed == (MENU, LEVEL_BLECHY, (BASE_RING + 2, RING), True) and any(picture) and not dev.m.asserts, f"{landed}")
    add("blechy_page_shows_him_alone", len(lit(picture, range(64))) > 300 and not lit(picture, range(64)) & {(x, y) for y in range(64) for x in range(70, 128)}, f"{len(lit(picture, range(64)))} pixels")
    dark = blechy_dark(dev)
    add("blechy_page_dark_either_way", dark["on"] == ("plain", True) and dark["off"] == ("complement", False) and not dev.m.asserts, f"{dark}")
    press(dev, "edit_next", wait=0.8)
    pattern = (dev.screen()["number"], counter(dev), open_app_entry(dev))
    add("blechy_right_goes_to_pattern", pattern == (3, (0, RING), 0), f"{pattern}")
    if SYNC_GROUP:
        # SYNC GROUP sits between CHAIN REPEAT, the Pattern menu's last page (15), and the Part menu (17): 16 of the ring (Pascal 29.10.)
        group = lambda: bytes(dev.read(dev.u32(0xC033E6A4) + 4 + SYNC_GROUP_AT, 2))
        for _ in range(SYNC_AT - 1):
            press(dev, "edit_next", wait=0.3)
        chain = (dev.screen()["number"], counter(dev))
        press(dev, "edit_next", wait=0.8)
        sync = (dev.screen()["number"], state(dev, S_LEVEL), counter(dev), open_app_entry(dev), texts_of(dev)[:2], tab(dev))
        add("sync_group_follows_chain_repeat", chain == (3, (SYNC_AT - 1, RING)) and sync == (MENU, LEVEL_SYNC, (SYNC_AT, RING), 0, ("SYNC GROUP", "OFF"), "Pattern")
            and not dev.m.asserts, f"{chain}, then {sync}")
        dev.turn(3, wait=0.3)
        three = (texts_of(dev)[:2], group())
        dev.turn(-10, wait=0.3)
        off = (texts_of(dev)[:2], group())
        add("sync_group_page_sets_the_pattern", three == (("SYNC GROUP", "3"), b"\x03\x00") and off == (("SYNC GROUP", "OFF"), b"\x00\x00")
            and not dev.m.asserts, f"turned +3: {three}, then -10: {off}")
        press(dev, "edit_next", wait=0.8)
        part = (dev.screen()["number"], counter(dev))
        press(dev, "edit_prev", wait=0.8)
        back_sync = (dev.screen()["number"], state(dev, S_LEVEL), counter(dev))
        press(dev, "edit_prev", wait=0.8)
        back_chain = (dev.screen()["number"], counter(dev))
        add("sync_group_between_pattern_and_part", part == (7, (SYNC_AT + 1, RING)) and back_sync == (MENU, LEVEL_SYNC, (SYNC_AT, RING))
            and back_chain == (3, (SYNC_AT - 1, RING)) and not dev.m.asserts, f"right {part}, left {back_sync}, left {back_chain}")
        press(dev, "edit_next", wait=0.8)
        dev.turn(2, wait=0.3)
        press(dev, "write", wait=0.6)
        window = dev.screen()["number"]
        add("sync_group_write_saves_the_pattern", window == 18 and group() == b"\x02\x00" and not dev.m.asserts,
            f"WRITE on SYNC GROUP opens the firmware's pattern write screen (18, as on the Pattern menu's pages): {window}, the group {group()}")
        press(dev, "exit", wait=0.6)
        press(dev, "exit", wait=0.8)
        main = dev.screen()["number"]
        add("sync_group_exit_goes_to_main", main == 1 and not dev.m.asserts, f"screen {main}")
    go(dev, 10)
    for _ in range(3):                  # BLECH, Blechy, the Pattern menu on its first page (Event's EDIT right sets it)
        press(dev, "edit_next", wait=0.8)
    press(dev, "edit_prev", wait=0.8)
    back = here()
    add("blechy_pattern_left_comes_back", back == landed, f"{back}")
    press(dev, "edit_prev", wait=0.8)
    blech = (dev.screen()["number"], state(dev, S_LEVEL), counter(dev), open_app_entry(dev))
    add("blechy_left_goes_to_blech", blech == (MENU, 0, (BASE_RING + 1, RING), 0), f"{blech}")
    goto_blechy(dev)
    dev.run(0.5)
    before = bytes(dev.m.mmc.card.medium.data) if dev.m.mmc.card else b""
    for key in ("menu", "write"):
        press(dev, key, wait=0.5)
    after = here()
    add("blechy_enter_and_write_do_nothing", after[:2] == (MENU, LEVEL_BLECHY) and after[3] and dev.screen()["window"] == 0 and (not before or bytes(dev.m.mmc.card.medium.data) == before) and not dev.m.asserts, f"{after}")
    dev.turn(5, wait=0.4)
    dev.turn(-9, wait=0.4)
    turned = here()
    add("blechy_dial_changes_nothing", turned == after, f"{turned}")
    press(dev, "exit", wait=0.8)
    main = (dev.screen()["number"], open_app_entry(dev))
    add("blechy_exit_goes_to_main", main == (1, 0) and not dev.m.asserts, f"{main}")
    bad = []
    for key in range(0x30):
        goto_blechy(dev)
        dev.m.press(key, True)
        dev.run(0.05)
        dev.m.press(key, False)
        dev.run(0.15)
        if dev.m.asserts:
            bad.append(key)
            break
    add("blechy_all_keys_run", not bad, f"no assertion over 48 keys on his page" if not bad else f"assertion at key {bad}")
    # EDIT off his page: no frame shows a pixel of him that the next page does not have (Discord 26.10., blue with BLECH 1.3.3: his head
    # and feet stayed on SYNC GROUP; the page drew only its widgets over his last picture for 35 ms before the full redraw came). Here EDIT
    # right goes on to the Pattern menu and EDIT left back to the page BLECH.
    bits = lambda fb: {(i, k) for i, b in enumerate(fb) for k in range(8) if b >> k & 1}

    def sending(before, look, after):
        """Whether `look` caught the controller in the middle of one transfer: its first bytes are already those of the next look,
        the rest still those of the one before (a full frame goes in in order and can straddle a 5 ms look)."""
        if after is None or look == after:
            return False
        cut = next(j for j in range(len(look)) if look[j] != after[j])
        return look[cut:] == before[cut:]

    left = []
    for key in ("edit_next", "edit_prev"):
        goto_blechy(dev)
        dev.run(1.0)
        last = (frame(dev), dev.fb())
        dev.m.press(KEYS[key], True)
        looks = []
        for k in range(40):
            dev.run(0.005)
            if k == 10:
                dev.m.press(KEYS[key], False)
            looks.append((frame(dev), dev.fb()))
        dev.run(0.5)
        settled = (frame(dev), dev.fb())
        for i, kind in enumerate(("frame", "display")):
            his = bits(last[i]) - bits(settled[i])
            seq = [last[i]] + [look[i] for look in looks] + [None]
            # only his pixels in bytes still as in his picture: the next page draws in steps (its title bar solid first, the text cut in a
            # frame later), and that bar can cover a pixel of him in a byte that is neither his picture nor the settled page
            kept = lambda look: {(j, b) for j, b in his if look[j] == last[i][j]}
            stale = [5 * k for k in range(1, len(seq) - 1) if seq[k] != last[i] and kept(seq[k]) and not sending(seq[k - 1], seq[k], seq[k + 1])]
            if stale:
                left.append(f"{key} {kind} at {stale[:4]} ms")
    add("blechy_leaves_no_trace", not left and not dev.m.asserts,
        "EDIT right and left off his page: every look every 5 ms is his last picture or has none of his pixels the next page lacks"
        + (f"; his pixels on the next page: {left}" if left else ""))
    go(dev, 8)
    return out


def ring_cases(payload, flash=None):
    """The ring, the firmware's menus with our pages and the list that remembers its group, on one device."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash)
    add("armed", state(dev, S_ON) == 1 and state(dev, S_COUNT) == 1 and state(dev, S_LEVEL) == 0, f"on={state(dev, S_ON)}, ring pages={state(dev, S_COUNT)}")

    # the ring: BLECH is one page of it, the last menu behind Event, then the page of Blechy (device 18.10.), in the look of Data Util's page
    here = lambda: (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), counter(dev), texts_of(dev), tab(dev))
    go(dev, 10)
    press(dev, "edit_next")
    page = here()
    press(dev, "edit_next")
    after = (dev.screen()["number"], state(dev, S_LEVEL))
    press(dev, "edit_prev")
    again = here()
    press(dev, "edit_prev")
    add("ring_forward", page == (MENU, 0, 0, (BASE_RING + 1, RING), ("BLECH", "", PRESS), "BLECH") and after == (MENU, LEVEL_BLECHY), f"{page}, then {after}")
    add("ring_backward", again == page and dev.screen()["number"] == 10, f"{again}, then screen {dev.screen()['number']}")
    go(dev, 8)
    press(dev, "edit_next")
    right = dev.screen()["number"]
    press(dev, "edit_prev")
    add("global_and_data_util_are_neighbours", right == 14 and dev.screen()["number"] == 8, f"Global right {right}, then left {dev.screen()['number']}")

    go(dev, 14)
    add("neighbour_counters", counter(dev) == (BASE_RING - 1, RING), f"Data Util {counter(dev)}")
    go(dev, 8)
    add("global_counter", counter(dev) == (BASE_RING - 2, RING), f"Global {counter(dev)}")
    go(dev, 10)
    add("event_counter", counter(dev) == (BASE_RING, RING), f"Event {counter(dev)}")
    out.extend(firmware_menu_cases(dev))

    # the list opens on the group it was last left from, also after a trip through the other menus (device 18.10.)
    goto_ring(dev)
    press(dev, "menu", wait=0.4)
    for _ in range(LIST_PLUGINS):
        press(dev, "edit_next", wait=0.3)
    press(dev, "menu", wait=0.4)
    inside = (state(dev, S_LEVEL), state(dev, S_GROUP))
    press(dev, "exit", wait=0.4)
    press(dev, "exit", wait=0.4)
    go(dev, 8)
    go(dev, 10)
    press(dev, "edit_next", wait=0.4)
    press(dev, "menu", wait=0.4)
    back = (state(dev, S_LEVEL), state(dev, S_PAGE), texts_of(dev)[0])
    add("list_remembers_the_group", inside == (2, GROUP_PLUGINS) and back == (1, LIST_PLUGINS, LIST_PAGES[LIST_PLUGINS]), f"in {inside}, back {back}")
    return out


def list_cases(payload, flash=None):
    """The list of the groups, its pages, EXIT, WRITE, the value and every key, on a device of its own."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash)
    # ENTER opens the list of the groups, ENTER on a group its pages, EXIT goes up one level each time and leaves at the ring
    dev.m.uc.mem_write(STATE + S_TOP, struct.pack("<I", 0))     # the list as after power-on, on its first group
    goto_ring(dev)
    press(dev, "menu")
    steps = []
    for _ in range(LIST_COUNT):
        steps.append((dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), counter(dev), texts_of(dev), tab(dev)))
        press(dev, "edit_next")
    wrapped = (dev.screen()["number"], state(dev, S_PAGE))
    want = [(MENU, 1, page, (page, LIST_COUNT), (title, "", PRESS), "BLECH") for page, title in enumerate(LIST_PAGES)]
    want.append((MENU, 1, LIST_VERSION, (LIST_VERSION, LIST_COUNT), (*version_texts(payload), ""), "BLECH"))
    add("enter_opens_the_list_of_groups", steps == want and wrapped == (MENU, 0), f"{steps}, then {wrapped}")
    # VERSION, the last row: the version of the set this copy was patched with and the firmware it is for; ENTER, WRITE and the dial change nothing
    goto_top(dev, LIST_VERSION)
    shown = texts_of(dev)
    press(dev, "menu", wait=0.4)
    press(dev, "write", wait=0.4)
    dev.turn(1, wait=0.2)
    after = (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), texts_of(dev), dev.screen()["window"])
    title = version_texts(payload)[0]
    add("version_page", shown == (*version_texts(payload), "") and (title == "BLECH" or re.fullmatch(r"BLECH \d+\.\d+\.\d+", title))
        and after == (MENU, 1, LIST_VERSION, shown, 0) and not dev.m.asserts, f"{shown}, after ENTER, WRITE and the dial {after}")
    # ENTER on PLUGINS opens the list of MANAGE PLUGINS straight away; without plugins its one page says so, EXIT goes back to the row
    goto_top(dev, LIST_PLUGINS)
    press(dev, "menu", wait=0.4)
    inside = (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_GROUP), state(dev, S_PAGE), counter(dev), texts_of(dev))
    plugins_tab = tab(dev)
    press(dev, "exit", wait=0.4)
    out_again = (state(dev, S_LEVEL), state(dev, S_PAGE), text(dev, S_TITLE))
    add("enter_goes_into_the_group", inside == (MENU, 2, GROUP_PLUGINS, 0, (0, 1), ("MANAGE PLUGINS", "No Plugin", "")) and plugins_tab == "Plugins"
        and out_again == (1, LIST_PLUGINS, "PLUGINS"), f"{inside}, EXIT {out_again}")
    goto_top(dev, LIST_FEATURES)
    press(dev, "menu")
    features = (state(dev, S_LEVEL), state(dev, S_GROUP), counter(dev), tab(dev), [])
    want = [(title, "ON") for title in feature_pages()]
    for _ in want:
        features[4].append(texts_of(dev)[:2])
        press(dev, "edit_next")
    add("features_group_lists_the_switches", features[:4] == (2, GROUP_FEATURES, (0, len(want)), "Feature")
        and features[4] == want and state(dev, S_PAGE) == 0, str(features))
    goto_top(dev, LIST_FEATURES)
    press(dev, "menu")
    press(dev, "edit_prev")
    wrapped = (state(dev, S_PAGE), counter(dev), text(dev, S_TITLE))
    press(dev, "edit_next")
    forward = (state(dev, S_PAGE), counter(dev), text(dev, S_TITLE), dev.screen()["number"])
    last = feature_count() - 1
    add("group_pages_wrap_and_count_alone", wrapped == (last, (last, last + 1), feature_pages()[last]) and forward == (0, (0, last + 1), FEATURE_PAGES[0], MENU),
        f"{wrapped}, {forward}")
    press(dev, "exit")
    up = (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), counter(dev), text(dev, S_TITLE))
    add("exit_goes_one_level_up", up == (MENU, 1, LIST_FEATURES, (LIST_FEATURES, LIST_COUNT), "FEATURES") and tab(dev) == "BLECH", str(up))
    goto_top(dev, LIST_CUSTOM)
    press(dev, "menu")
    press(dev, "edit_next")
    press(dev, "exit")
    back_at = (state(dev, S_LEVEL), state(dev, S_PAGE), text(dev, S_TITLE))
    add("exit_returns_to_the_groups_row", back_at == (1, LIST_CUSTOM, "CUSTOMIZATION"), str(back_at))
    press(dev, "exit")
    to_ring = (dev.screen()["number"], state(dev, S_LEVEL), text(dev, S_TITLE))
    press(dev, "exit")
    add("exit_to_main", to_ring == (MENU, 0, "BLECH") and dev.screen()["number"] == 1 and not dev.m.asserts, f"{to_ring}, then screen {dev.screen()['number']}")
    press(dev, "menu")
    add("menu_key_returns", dev.screen()["number"] == MENU and state(dev, S_LEVEL) == 0, f"screen {dev.screen()['number']}, level {state(dev, S_LEVEL)}")

    goto_group(dev, GROUP_FEATURES, FEAT_MFX)
    first = dev.screen()
    press(dev, "write", wait=0.4)
    window = dev.screen()
    add("write_opens_nothing", first["number"] == MENU and window["number"] == MENU and window["window"] == 0 and not dev.m.asserts,
        f"screen {window['number']}, window {window['window']}")
    goto_global(dev)
    dev.turn(1, wait=0.2)
    dev.turn(-1, wait=0.2)
    turned = (state(dev, S_RUN), text(dev, S_TITLE), text(dev, S_VALUE))
    add("value_turns_plugin_runtime", turned == (0, "PLUGIN RUNTIME", "OFF, RESTART"), str(turned))
    seen_keys = set()
    for key in range(0x30):
        go(dev, MENU)
        dev.m.press(key, True)
        dev.run(0.05)
        dev.m.press(key, False)
        dev.run(0.15)
        seen_keys.add(dev.screen()["number"])
        if dev.m.asserts:
            break
    add("all_keys_run", not dev.m.asserts, f"no assertion over 48 keys, screens {sorted(seen_keys)}" if not dev.m.asserts else f"asserts {dev.m.asserts}")
    return out


def page_cases(payload, flash=None):
    """No page is crowded or shows a cut-off label, on a device of its own."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash)
    # no page runs its texts together or into the edge, none shows a label that is cut off
    pages = [("ring", 0), ("global", 0)] + [("du", page) for page in range(len(du_pages()))] + [("list", page) for page in range(LIST_COUNT)] + [(GROUP_PLUGINS, 0)]
    pages += [(GROUP_CUSTOM, page) for page in range(2)] + [(GROUP_DISPLAY, page) for page in range(5)] + [(GROUP_LED, page) for page in range(8 + (custom_extra(dev) > 0))]
    pages += [(GROUP_PADS, page) for page in range(3)] + [(GROUP_PSAVE, page) for page in range(2)] + [(GROUP_FEATURES, page) for page in range(feature_count())]
    crowded = []
    for group, page in pages:
        if group == "ring":
            goto_ring(dev)
        elif group == "global":
            goto_global(dev)
        elif group == "du":
            goto_du(dev, page)
        elif group == "list":
            goto_top(dev, page)
        else:
            goto_group(dev, group, page)
        found = page_overlap(dev)
        if found:
            crowded.append((group, page, texts_of(dev)[0], found))
    add("pages_are_clean", not crowded, f"{len(pages)} pages, crowded: {crowded}")
    goto_blechy(dev)
    add("blechy_page_has_no_text", texts_of(dev) == ("", "", ""), f"{texts_of(dev)}")
    goto_ring(dev)
    clipped =[problem for label in TAB_LABELS for problem in [label_problem(dev, label, 38, 40)] if problem]
    add("tab_labels_fit", not clipped, f"{len(TAB_LABELS)} labels beside the widest counter (39/40): {clipped}")
    return out


def exit_held_cases(payload, flash=None):
    """With EXIT held at power-on the firmware's menus stay stock."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    stock = boot(payload, flash, held=KILL)
    go(stock, 8)
    press(stock, "edit_next")
    add("exit_held_is_stock", state(stock, S_ON) != 1 and stock.screen()["number"] == 14 and counter(stock) == (BASE_RING - 2, BASE_RING) and not stock.m.asserts,
        f"on={state(stock, S_ON):#x}, screen {stock.screen()['number']}, Data Util {counter(stock)}")
    press(stock, "edit_prev")
    press(stock, "edit_next")
    go(stock, 14)
    press(stock, "edit_prev")
    add("exit_held_left_is_stock", stock.screen()["number"] == 8 and not stock.m.asserts, f"screen {stock.screen()['number']}")
    # the ring of the firmware is untouched: Event goes straight on to the Pattern menu and back, there is no page of Blechy
    go(stock, 10)
    press(stock, "edit_next", wait=0.5)
    on_right = (stock.screen()["number"], counter(stock))
    press(stock, "edit_prev", wait=0.5)
    on_left = (stock.screen()["number"], counter(stock))
    add("exit_held_has_no_blechy_page", on_right == (3, (0, BASE_RING)) and on_left == (10, (BASE_RING - 1, BASE_RING)) and state(stock, S_ON) != 1 and not stock.m.asserts,
        f"Event right {on_right}, Pattern left {on_left}")
    # CHAIN REPEAT goes straight on to the Part menu, GLOBAL PARAMETERS and DATA UTILITY wrap round their own pages
    go(stock, 7)
    press(stock, "edit_prev", wait=0.5)
    part_left = (stock.screen()["number"], counter(stock))
    press(stock, "edit_next", wait=0.5)
    chain_right = (stock.screen()["number"], counter(stock))
    go(stock, 8)
    press(stock, "menu", wait=0.5)
    press(stock, "edit_prev", wait=0.5)
    global_left = (stock.screen()["number"], counter(stock))
    go(stock, 14)
    press(stock, "menu", wait=0.5)
    press(stock, "edit_prev", wait=0.5)
    du_left = (stock.screen()["number"], counter(stock))
    add("exit_held_firmware_menus_are_stock", part_left == (3, (14, BASE_RING)) and chain_right == (7, (15, BASE_RING)) and global_left == (9, (GLOBAL_PAGES - 1, GLOBAL_PAGES))
        and du_left == (15, (DU_FUNCS - 1, DU_FUNCS)) and not stock.m.asserts, f"Part left {part_left}, then right {chain_right}, Global left {global_left}, Data Util left {du_left}")
    return out


def blechy_ring_part(payload, flash=None):
    """blechy_ring_cases on a device of its own."""
    return blechy_ring_cases(boot(payload, flash))


ORIG_X, ORIG_ROWS = range(36, 51), range(55, 62)     # where the firmware draws its ORIG badge (15 x 8 at 36, 55); the last row of the plate is left out, the theme's checker runs through it
ORIG_FLAG = 0x49                                     # the byte of the text widget (the screen's widget at 0x24) that the firmware's draw reads


def orig_pixels(dev):
    """The lit pixels of the ORIG badge's place."""
    return {(x, y) for x, y in lit(dev.fb(), ORIG_ROWS) if x in ORIG_X}


def orig_shown(dev):
    """True when the page shows the ORIG badge (the widget's flag is set and the badge is on the display), False when it shows none;
    None when the flag and the display disagree."""
    flag = dev.read(dev.u32(screen_object(dev) + MENU_WIDGET) + ORIG_FLAG, 1)[0]
    pixels = len(orig_pixels(dev))
    return True if flag and pixels > 20 else False if not flag and not pixels else None


def orig_pages():
    """(name, how to reach it) of every page of the BLECH menu that shows a setting."""
    pages = [("PLUGIN RUNTIME", lambda dev: goto_global(dev))]
    for group, count in ((GROUP_DISPLAY, 5), (GROUP_LED, 9), (GROUP_PADS, 3), (GROUP_PSAVE, 2), (GROUP_FEATURES, feature_count())):
        pages += [(f"{group}:{page}", lambda dev, group=group, page=page: goto_group(dev, group, page)) for page in range(count)]
    return pages


def orig_cases(payload, flash=None):
    """The ORIG badge on the pages of the BLECH menu, as the firmware shows it on its own: on the value that is stored (the file's, the
    defaults without one), gone after the dial changed it, back when it is turned back; at the place and in the look of the
    firmware's badge (GLOBAL PARAMETERS); a changed value kept with WRITE is the stored one afterwards; pages that show no setting
    have no badge."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:orig_{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    start, changed, back, stuck = {}, {}, {}, []
    for name, reach in orig_pages():
        reach(dev)
        before = texts_of(dev)
        start[name] = orig_shown(dev)
        for step in (1, -1):
            dev.turn(step, wait=0.3)
            if texts_of(dev) != before:
                break
        else:
            stuck.append(name)
            continue
        changed[name] = orig_shown(dev)
        dev.turn(-step, wait=0.3)
        back[name] = (orig_shown(dev), texts_of(dev) == before)
        if not back[name][1]:       # the colour pages are hue, saturation and brightness over three levels: a step back need not be the value before; the next page starts on a device of its own
            dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    add("shown_on_the_stored_value", start and all(v is True for v in start.values()), f"{start}")
    add("gone_after_a_change", changed and not any(changed.values()) and not stuck, f"changed {changed}, pages where the dial changed nothing {stuck}")
    add("back_on_returning", back and all(shown == restored for shown, restored in back.values()) and sum(restored for _, restored in back.values()) > 20, f"(badge, the value is the one before) {back}")

    # the same plate in the same place as on the firmware's own pages
    goto_group(dev, GROUP_FEATURES, FEAT_PC)
    ours = orig_pixels(dev)
    go(dev, 9)
    dev.run(0.4)
    theirs = orig_pixels(dev)
    add("look_of_the_firmware", ours and ours == theirs, f"ours {len(ours)} pixels, GLOBAL PARAMETERS {len(theirs)}, same {ours == theirs}")

    # a changed value kept with WRITE is the stored one; the old one is a change then
    goto_group(dev, GROUP_FEATURES, FEAT_TM)
    dev.turn(-1, wait=0.3)
    off = orig_shown(dev), texts_of(dev)[1]
    press(dev, "write", wait=0.6)
    kept = orig_shown(dev)
    dev.turn(1, wait=0.3)
    on = orig_shown(dev), texts_of(dev)[1]
    dev.turn(-1, wait=0.3)
    off_again = orig_shown(dev), texts_of(dev)[1]
    add("write_keeps_the_new_value", off == (False, "OFF") and kept is True and on == (False, "ON") and off_again == (True, "OFF"),
        f"changed {off}, after WRITE {kept}, back to the old value {on}, to the kept one {off_again}")

    # the value a settings file holds at the start: PATTERN CONFIRM off and the display not inverted are the file's, the other pages are the defaults
    stored = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | PC_OFF_BIT, look_word(0, invert=0))}, adapter=True)
    goto_group(stored, GROUP_FEATURES, FEAT_PC)
    file_off = texts_of(stored)[1], orig_shown(stored)
    stored.turn(1, wait=0.3)
    file_on = texts_of(stored)[1], orig_shown(stored)
    stored.turn(-1, wait=0.3)
    file_off_again = texts_of(stored)[1], orig_shown(stored)
    goto_group(stored, GROUP_DISPLAY, 4)
    inverted_off = texts_of(stored)[1], orig_shown(stored)
    add("file_value_is_the_stored_one", file_off == ("OFF", True) and file_on == ("ON", False) and file_off_again == ("OFF", True) and inverted_off[1] is True and not stored.m.asserts,
        f"PATTERN CONFIRM {file_off}, turned up {file_on}, back {file_off_again}; DISPLAY INVERT {inverted_off}")

    # without a card the defaults are the stored values
    bare = boot(payload, flash, adapter=True, card=False)
    goto_group(bare, GROUP_FEATURES, FEAT_TM)
    bare_page = orig_shown(bare)
    bare.turn(-1, wait=0.3)
    add("no_card_shows_the_defaults", bare_page is True and orig_shown(bare) is False and not bare.m.asserts, f"at the start {bare_page}, after the dial {orig_shown(bare)}")

    # the pages that show no setting have none: the list of the groups, the groups themselves, VERSION
    plain = {}
    for name, reach in (("groups", lambda: goto_top(dev, 0)), ("plugins", lambda: goto_group(dev, GROUP_PLUGINS, 0)), ("version", lambda: goto_top(dev, LIST_VERSION)),
                        ("sync_group", lambda: _enter(dev, LEVEL_SYNC)), ("ring", lambda: goto_ring(dev))):
        reach()
        plain[name] = orig_shown(dev)
    add("not_on_pages_without_a_setting", not any(plain.values()), f"{plain}")
    return out


# What cases_task(i) runs, in the order of cases(). Each boots its own device, so they run side by side.
CASES_PARTS = (ring_cases, blechy_ring_part, list_cases, page_cases, exit_held_cases, orig_cases)


def cases(payload, flash=None, settings=True):
    """The menu cases as check.py entries [{id, ok, detail}]; the settings cases (settings_cases) come last unless `settings` is False."""
    out = [entry for part in CASES_PARTS for entry in part(payload, flash)]
    if settings:
        out.extend(settings_cases(payload, flash))
    return out


S_EFF_RUN, S_EFF_MFX, S_GEN, S_STATUS = 24, 28, 32, 36
RUNTIME = script_hooks.RUNTIME
CARD_STATUS = 164
SETTINGS_PATHS = ("/KORG/blechtribe/settings.a.bin", "/KORG/blechtribe/settings.b.bin")
CARD_FOLDER = {"/KORG/blechtribe/Sample/placeholder": b"1"}
FS_OPEN = 0xC009DB60


def settings_file(generation, flags, bad_crc=False, trusted=(), count=None):
    head = struct.pack("<IHHII", 0x54455347, 1, len(trusted) if count is None else count, generation, flags) + struct.pack(f"<{len(trusted)}I", *trusted)
    crc = zlib.crc32(head) & 0xFFFFFFFF
    return head + struct.pack("<I", crc ^ (1 if bad_crc else 0))


def settings_file_v2(generation, flags, look, bad_crc=False, trusted=()):
    """A version 2 settings file: version 1 plus the look word (bottom LEDs and backlight)."""
    head = struct.pack("<IHHIII", 0x54455347, 2, len(trusted), generation, flags, look) + struct.pack(f"<{len(trusted)}I", *trusted)
    crc = zlib.crc32(head) & 0xFFFFFFFF
    return head + struct.pack("<I", crc ^ (1 if bad_crc else 0))


def look_word(mode=0, led=(0, 0, 0), backlight=(0, 0, 0), invert=0):
    """The look word of a settings file: mode (0 METER, 1 COLOR, 2 OFF), LED red/green/blue, backlight red/green/blue, 0 to 15 each, bit 28 the display inverted."""
    return mode | led[0] << 4 | led[1] << 8 | led[2] << 12 | backlight[0] << 16 | backlight[1] << 20 | backlight[2] << 24 | invert << 28


def read_settings(image):
    """The settings files on a card image as {name: (generation, flags)} for the valid ones."""
    return {name: (generation, flags) for name, (generation, flags, _) in read_settings_full(image).items()}


def settings_extras(image):
    """Byte 5 of each settings file on a card image (bit 0: METER LOUD RAINBOW, bit 1: METER STILL OFF), valid or not."""
    volume = fat32.Volume(bytes(image))
    out = {}
    for path in SETTINGS_PATHS:
        try:
            raw = volume.read(path)
        except fat32.FatError:
            continue
        if len(raw) >= 20 and raw[:4] == b"GSET":
            out[path.rsplit(".", 2)[1]] = raw[5]
    volume.close()
    return out


def read_settings_full(image):
    """The valid settings files as {name: (generation, flags, trusted checksums)}."""
    return {name: (generation, flags, trusted) for name, (generation, flags, trusted, _) in read_settings_look(image).items()}


def read_settings_look(image):
    """The valid settings files as {name: (generation, flags, trusted checksums, look)}, look None for version 1. Version 3 (BLECH
    1.3.8) is version 2 with up to 64 checksums instead of 16."""
    volume = fat32.Volume(bytes(image))
    out = {}
    for path in SETTINGS_PATHS:
        try:
            raw = volume.read(path)
        except fat32.FatError:
            continue
        if len(raw) < 20 or raw[:4] != b"GSET":
            continue
        version, extras, count = raw[4], raw[5], struct.unpack_from("<H", raw, 6)[0]
        head = {1: 16, 2: 20, 3: 20}.get(version)
        if head is None or extras & ~0xFF:   # byte 5: bit 0 is METER LOUD RAINBOW, bit 1 METER STILL OFF, bit 2 STEREO 1 PAD OFF, bit 3 LAST PATTERN OFF, bit 4 KEY PADS OFF, bit 5 FILTER TOGGLE OFF, bit 6 KNOB LEDS OFF (once HT OSC OFF), bit 7 AUTO SAVE OFF
            continue
        size = head + 4 * count
        if count > (64 if version == 3 else 16) or len(raw) != size + 4 or zlib.crc32(raw[:size]) & 0xFFFFFFFF != struct.unpack_from("<I", raw, size)[0]:
            continue
        look = struct.unpack_from("<I", raw, 16)[0] if version >= 2 else None
        out[path.rsplit(".", 2)[1]] = (*struct.unpack_from("<II", raw, 8), list(struct.unpack_from(f"<{count}I", raw, head)), look)
    volume.close()
    return out


def custom_export_cases(payload, flash=None):
    """EXPORT ALL CUSTOMIZATIONS (DATA UTILITY) writes KORG/blechtribe/e2sCustom.all: the settings record without the plugin
    checksums. Nothing reads that file at start; copied over settings.a.bin the settings loader takes it, and the look is back."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(dev, led=(15, 7, 0), backlight=(3, 9, 12))
    look = [state(dev, at) for at in (S_LED_MODE, S_LED_R, S_LED_G, S_LED_B, S_BL_R, S_BL_G, S_BL_B, S_INVERT)]
    dev.m.uc.mem_write(STATE + 44, struct.pack("<I", 1))              # one allowed checksum: the export leaves it out
    dev.m.uc.mem_write(STATE + 0x1C0, struct.pack("<I", 0x12345678))
    goto_du(dev, du_pages().index("EXPORT ALL CUSTOM"))
    page = texts_of(dev)
    before = read_settings(dev.m.mmc.card.medium.data)
    press(dev, "menu", wait=0.8)
    shown = texts_of(dev)[:2]
    volume = fat32.Volume(bytes(dev.m.mmc.card.medium.data))
    try:
        written = volume.read("/KORG/blechtribe/e2sCustom.all")
    except fat32.FatError:
        written = None
    volume.close()
    ok_file = written is not None and written[:4] == b"GSET" and struct.unpack_from("<H", written, 6)[0] == 0 \
        and struct.unpack_from("<I", written, len(written) - 4)[0] == zlib.crc32(written[:-4]) & 0xFFFFFFFF
    add("export_custom_writes_the_file", page == ("EXPORT ALL CUSTOM", "", PRESS) and shown == ("EXPORT ALL CUSTOM", "exported") and ok_file
        and read_settings(dev.m.mmc.card.medium.data) == before and not dev.m.asserts,
        f"{page}, then {shown}, file {len(written or b'')} bytes, settings files untouched {read_settings(dev.m.mmc.card.medium.data) == before}")
    again = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: written or b""}, adapter=True)
    back = [state(again, at) for at in (S_LED_MODE, S_LED_R, S_LED_G, S_LED_B, S_BL_R, S_BL_G, S_BL_B, S_INVERT)]
    add("export_custom_reads_back_as_settings", back == look and state(again, 44) == 0 and not again.m.asserts, f"look {back}, wanted {look}, checksums {state(again, 44)}")
    return out


def settings_cases(payload, flash=None):
    out = custom_export_cases(payload, flash)

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    # defaults without a settings file, the script loader sees no file
    dev = boot(payload, flash, files=CARD_FOLDER)
    add("settings_defaults", (state(dev, S_SET_RUN), state(dev, S_SET_MFX), state(dev, S_EFF_RUN), state(dev, S_EFF_MFX)) == (1, 1, 1, 1)
        and dev.u32(RUNTIME + CARD_STATUS) == 2,
        f"set {state(dev, S_SET_RUN)}/{state(dev, S_SET_MFX)}, effective {state(dev, S_EFF_RUN)}/{state(dev, S_EFF_MFX)}, card status {dev.u32(RUNTIME + CARD_STATUS)}")

    # edit, show the hint, save: generation 1 goes to settings.b.bin, nothing else on the card changes
    goto_global(dev)
    dev.turn(-1, wait=0.2)
    first = (text(dev, S_TITLE), text(dev, S_VALUE), text(dev, S_LINE3))
    goto_group(dev, GROUP_FEATURES, FEAT_MFX)
    dev.turn(-1, wait=0.2)
    second = (text(dev, S_TITLE), text(dev, S_VALUE), text(dev, S_LINE3))
    before = bytes(dev.m.mmc.card.medium.data)
    press(dev, "write", wait=0.6)
    saved = text(dev, S_VALUE), state(dev, S_STATUS)
    card = bytes(dev.m.mmc.card.medium.data)
    files = read_settings(card)
    add("settings_edit_and_save", first == ("PLUGIN RUNTIME", "OFF, RESTART", "") and second == ("MFX 2", "OFF, RESTART", "")
        and saved == ("saved", 1) and files == {"b": (1, 0)} and state(dev, S_EFF_RUN) == 1 and state(dev, S_GEN) == 1 and card != before,
        f"{first}, {second}, after WRITE {saved}, files {files}")
    press(dev, "write", wait=0.6)
    files = read_settings(dev.m.mmc.card.medium.data)
    add("settings_second_write_alternates", files == {"a": (2, 0), "b": (1, 0)}, f"files {files}")
    page = state(dev, S_PAGE)
    press(dev, "edit_next")
    add("settings_status_clears_with_the_page", state(dev, S_STATUS) == 0 and page == 0, f"status {state(dev, S_STATUS)}, page {page}")

    # the next start reads the file: scripts and MFX 2 are off, the loader reports it
    image = bytes(dev.m.mmc.card.medium.data)
    again = Dev(payload, flash, 0)
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(1.2)
    add("settings_read_at_start", (state(again, S_SET_RUN), state(again, S_SET_MFX), state(again, S_EFF_RUN), state(again, S_EFF_MFX), state(again, S_GEN)) == (0, 0, 0, 0, 2)
        and again.u32(RUNTIME + CARD_STATUS) == 9,
        f"effective {state(again, S_EFF_RUN)}/{state(again, S_EFF_MFX)}, generation {state(again, S_GEN)}, card status {again.u32(RUNTIME + CARD_STATUS)}")

    # no card at all: the menu still arms with the defaults, and a save says so and writes nothing
    bare = Dev(payload, flash, 0)
    bare.run(1.2)
    goto_group(bare, GROUP_FEATURES, FEAT_MFX)
    press(bare, "write", wait=0.6)
    add("settings_without_card", state(bare, S_ON) == 1 and (state(bare, S_EFF_RUN), state(bare, S_EFF_MFX)) == (1, 1) and text(bare, S_VALUE) == "no card" and not bare.m.asserts,
        f"on={state(bare, S_ON)}, value {text(bare, S_VALUE)!r}, status {state(bare, S_STATUS):#x}")

    # a protected card: FatFs refuses the open for writing with 10, as the real one would (the emulator's card has no write protect)
    import unicorn
    from unicorn import arm_const
    prot = boot(payload, flash, files=CARD_FOLDER)
    before = bytes(prot.m.mmc.card.medium.data)

    def refuse(uc, address, size, user):
        if uc.reg_read(arm_const.UC_ARM_REG_R2) & 0x1E:
            uc.reg_write(arm_const.UC_ARM_REG_R0, 10)
            uc.reg_write(arm_const.UC_ARM_REG_PC, uc.reg_read(arm_const.UC_ARM_REG_LR))

    prot.m.uc.hook_add(unicorn.UC_HOOK_CODE, refuse, begin=prot.a(FS_OPEN), end=prot.a(FS_OPEN))
    prot.m.uc.ctl_flush_tb()
    goto_group(prot, GROUP_FEATURES, FEAT_MFX)
    press(prot, "write", wait=0.6)
    add("settings_protected_card", text(prot, S_VALUE) == "card protected" and bytes(prot.m.mmc.card.medium.data) == before and not prot.m.asserts,
        f"value {text(prot, S_VALUE)!r}, card unchanged {bytes(prot.m.mmc.card.medium.data) == before}")

    # no BLECH folder on the card, as on the blue, which keeps KORG/electribe: the save makes KORG/blechtribe, the next start reads it
    nofolder = boot(payload, flash, files={"/KORG/electribe/Sample/placeholder": b"1"})
    if nofolder.u32(0xC0190100) == 1:          # the blue asks to copy KORG/electribe first (migrate_cases.py); EXIT starts without
        press(nofolder, "exit", wait=0.6)
    goto_group(nofolder, GROUP_FEATURES, FEAT_MFX)
    nofolder.turn(-1, wait=0.2)
    press(nofolder, "write", wait=0.6)
    made = read_settings(nofolder.m.mmc.card.medium.data)
    later = Dev(payload, flash, 0)
    later.m.insert_card(SDCard(MemoryMedium(bytearray(nofolder.m.mmc.card.medium.data))))
    later.run(1.2)
    add("settings_without_folder", text(nofolder, S_VALUE) == "saved" and made == {"b": (1, 1)} and state(later, S_SET_MFX) == 0 and not nofolder.m.asserts and not later.m.asserts,
        f"value {text(nofolder, S_VALUE)!r}, files {made}, MFX 2 after the restart {state(later, S_SET_MFX)}")

    # MFX 2 off in the file: the touch pad starts as in the stock firmware and TOUCH SCALE stays the stock key
    from mfx_cases import Box, S_MODE as MFX_MODE, S_BOOT as MFX_BOOT
    medium = MemoryMedium(card_image({**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file(1, 1)}))
    off = Box(payload, flash, card=SDCard(medium))
    on = Box(payload, flash, card=SDCard(MemoryMedium(card_image({**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file(1, 3)}))))
    off.key("touch_scale", 1.0)
    on.key("touch_scale", 1.2)
    add("settings_mfx_off_is_stock", off.mode() == 1 and off.state(MFX_BOOT) != 1 and off.state(MFX_MODE) != 1 and on.state(MFX_MODE) == 1 and not off.m.asserts,
        f"off: mode {off.mode()}, MFX 2 mode {off.state(MFX_MODE):#x}; on: MFX 2 mode {on.state(MFX_MODE)}")

    # export with nothing loaded says so and writes nothing
    empty = boot(payload, flash, files=CARD_FOLDER)
    before = bytes(empty.m.mmc.card.medium.data)
    goto_du(empty, du_pages().index("EXPORT ALL PLUGINS"))
    page = text(empty, S_TITLE), text(empty, S_VALUE)
    press(empty, "write", wait=0.6)
    add("export_without_scripts", page == ("EXPORT ALL PLUGINS", "") and text(empty, S_VALUE) == "no plugins" and bytes(empty.m.mmc.card.medium.data) == before,
        f"{page}, then {text(empty, S_VALUE)!r}")
    goto_top(empty, LIST_PLUGINS)
    edit = texts_of(empty)
    press(empty, "menu", wait=0.4)
    add("manage_plugins_without_plugins", edit == ("PLUGINS", "", PRESS) and texts_of(empty) == ("MANAGE PLUGINS", "No Plugin", "")
        and (state(empty, S_LEVEL), state(empty, S_PAGE)) == (2, PLUGIN_MANAGE) and not empty.m.asserts,
        f"{edit}, ENTER says {texts_of(empty)} and stays: level {state(empty, S_LEVEL)}, page {state(empty, S_PAGE)}")

    # one valid and one corrupt file: the valid one is used, a newer corrupt one is ignored
    for name, files, want in [
        ("older_valid_newer_corrupt", {SETTINGS_PATHS[0]: settings_file(5, 2), SETTINGS_PATHS[1]: settings_file(6, 0, bad_crc=True)}, (0, 1, 5)),
        ("newer_valid_wins", {SETTINGS_PATHS[0]: settings_file(5, 2), SETTINGS_PATHS[1]: settings_file(4, 1)}, (0, 1, 5)),
        ("truncated_is_ignored", {SETTINGS_PATHS[0]: settings_file(5, 3)[:19]}, (1, 1, 0)),
        ("trusted_list_is_read", {SETTINGS_PATHS[0]: settings_file(2, 3, trusted=[11, 22])}, (1, 1, 2)),
        ("count_larger_than_the_file_is_ignored", {SETTINGS_PATHS[0]: settings_file(2, 0, trusted=[11], count=3)}, (1, 1, 0)),
        ("seventeen_checksums_are_ignored", {SETTINGS_PATHS[0]: settings_file(2, 0, trusted=list(range(17)))}, (1, 1, 0)),
        ("garbage_is_ignored", {SETTINGS_PATHS[0]: b"\xff" * 20, SETTINGS_PATHS[1]: bytes(range(20))}, (1, 1, 0)),
    ]:
        probe = boot(payload, flash, files={**CARD_FOLDER, **files})
        got = (state(probe, S_EFF_RUN), state(probe, S_EFF_MFX), state(probe, S_GEN) if "trusted" not in name else state(probe, 44))
        add(f"settings_{name}", got == want, f"effective scripts/MFX/{'generation' if 'trusted' not in name else 'trusted'} {got}, wanted {want}")
    return out


# the pages of the group CUSTOMIZATION
PAGE_LED_MODE, PAGE_LED_R, PAGE_LED_G, PAGE_LED_B, PAGE_BL_R, PAGE_BL_G, PAGE_BL_B, PAGE_INVERT = range(0, 8)
S_PC = 0x158                          # the page PATTERN CONFIRM: 1 on (the default), 0 off
S_TM = 0x15C                          # the page TAP MOTION: 1 on (the default), 0 off
TM_SETTING = 0xC0188F00               # the word of the patch tap-motion: FFFFFFFF never written, 1 on, 0 off
TM_ONCE_BIT = 32                      # bit 5 of the flags of the settings file: TAP MOTION is ONCE (bit 3, off, wins)
TM_OFF_BIT = 8                        # bit 3 of the flags of the settings file: TAP MOTION is off
S_NA = 0xFC                           # the page NOTE ASSIST: 1 on (the default), 0 off
S_KP = 0x104                          # the page KEY PADS: 1 on (the default), 0 off
S_FT = 0x1C0                          # the page FILTER TOGGLE: 1 on (the default), 0 off
S_AS = 0x1FC                          # the page AUTO SAVE: 1 on (the default), 0 off
NA_SETTING = 0xC0189F00               # the word of the patch note-assistant: FFFFFFFF never written, 1 on, 0 off
NA_OFF_BIT = 16                       # bit 4 of the flags of the settings file: NOTE ASSIST is off
PS_SETTING = 0xC0180F10               # the word of the patch pattern-switch: FFFFFFFF never written, 1 on, 0 off
PC_OFF_BIT = 4                        # bit 2 of the flags of the settings file: the confirmation is off
S_INVERT, S_INVERT_SENT = 0x1B8, 0x1BC
INVERT_BIT = 1 << 28
S_LED_MODE, S_LED_R, S_LED_G, S_LED_B, S_BL_R, S_BL_G, S_BL_B, S_LED_EFF, S_LED_V, S_BL_ON, S_BL_PWM = 0xA0, 0xA4, 0xA8, 0xAC, 0xB0, 0xB4, 0xB8, 0xBC, 0xC0, 0xC4, 0xC8
LED_FIRST, LED_COUNT = 0x4C, 12
GPIO_PINS = 0x38                      # GP6P3, P4 and P5: backlight red, green, blue
DIM_FLAG = 0xC00F9310
POWER_CONNECT = 0xC0028AB4             # the firmware sets the dimming for power save (1) or the normal light (0)
SMOOTH = 0xC0088220                   # the level smoothing the meter calls; its arguments are the two levels
LED_LOCK = 0xB98                      # LED manager + 0xB98: the lock a plugin holds
LED_MANAGER = 0xC0345A1C
POWER_SAVE_OBJECT = 0xC0691324        # Global power save (0 off, 1 auto, 2 always) is the byte at +0x29 of the object this points to


def leds(dev):
    return [dev.m.leds.get(i) for i in range(LED_FIRST, LED_FIRST + LED_COUNT)]


def steady_leds(dev, tries=20):
    """The lower LEDs once the firmware has written all four: it sets them one after another, and a colour that moves every
    frame (RAINBOW at LOUD) can be read between two of them."""
    for _ in range(tries):
        now = leds(dev)
        if now[:3] * (LED_COUNT // 3) == now:
            return now
        dev.run(0.005)
    return now


def pins(dev):
    return dev.m.gpio.get(3, 0) & GPIO_PINS


def custom_extra(dev):
    """The rows of CUSTOMIZATION behind DISPLAY and LED: PAD COLOR and POWER SAVE where the set has the pad colours, SPLASH where it
    also has the splash editor (the blue Electribe has the pad colours only)."""
    import pad_colors
    import splash_editor
    if dev.u32(pad_colors.CODE_AT) == 0xFFFFFFFF:
        return 0
    return 2 if dev.u32(splash_editor.IMPORT_ENTRY) == 0xFFFFFFFF else 3


def goto_page(dev, number):
    """Open a look page: the bottom LEDs and their levels in LED, the backlight levels and DISPLAY INVERT in DISPLAY."""
    if number <= PAGE_LED_B:
        goto_group(dev, GROUP_LED, number - PAGE_LED_MODE)
    elif number <= PAGE_BL_B:
        goto_group(dev, GROUP_DISPLAY, number - PAGE_BL_R)
    else:
        goto_group(dev, GROUP_DISPLAY, 4)


def set_look(dev, mode=None, led=None, backlight=None):
    """Set the look: the mode through the main dial, the colours as red, green, blue (0 to 15, 0 0 0 the stock state) in the menu's state,
    which the pages show as hue, saturation and brightness; a step of the mode page and back makes the menu apply them."""
    if mode is not None:
        goto_page(dev, PAGE_LED_MODE)
        dev.turn(mode - state(dev, S_LED_MODE), wait=0.25)
    for values, at in ((led, S_LED_R), (backlight, S_BL_R)):
        if values is not None:
            dev.m.uc.mem_write(STATE + at, struct.pack("<III", *values))
    if led is not None or backlight is not None:
        goto_page(dev, PAGE_LED_MODE)
        here = state(dev, S_LED_MODE)
        step = -1 if here else 1
        dev.turn(step, wait=0.25)
        dev.turn(-step, wait=0.25)


def meter_level(dev, level):
    """Feed the meter a level: the level smoothing the meter calls is handed the same number for both sides."""
    import unicorn
    dev._level = level
    if getattr(dev, "_level_hook", None) is None:
        def poke(uc, address, size, user):
            for reg in (arm_const.UC_ARM_REG_R0, arm_const.UC_ARM_REG_R1):
                uc.mem_write(uc.reg_read(reg), struct.pack("<i", dev._level))
        dev._level_hook = dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, poke, begin=dev.a(SMOOTH), end=dev.a(SMOOTH))
        dev.m.uc.ctl_flush_tb()


def watch_pins(dev):
    """Record every change of the backlight pins as (device time ns, pins) in dev.pin_log."""
    dev.pin_log = []
    write = dev.m.gpio_write

    def traced(off, value):
        before = dev.m.gpio.get(3, 0)
        write(off, value)
        after = dev.m.gpio.get(3, 0)
        if (before ^ after) & GPIO_PINS:
            dev.pin_log.append((dev.m.time_ns, after & GPIO_PINS))

    dev.m.gpio_write = traced


def duty(dev, seconds):
    """Fraction of the next `seconds` of device time each backlight pin was on, as {'R': .., 'G': .., 'B': ..}, and the number of pin changes."""
    dev.pin_log.clear()
    first, at = dev.m.gpio.get(3, 0) & GPIO_PINS, dev.m.time_ns
    dev.run(seconds)
    end = dev.m.time_ns
    on = {8: 0, 16: 0, 32: 0}
    now, since = first, at
    for when, value in dev.pin_log:
        for bit in on:
            if now & bit:
                on[bit] += when - since
        now, since = value, when
    for bit in on:
        if now & bit:
            on[bit] += end - since
    return {name: round(on[bit] / (end - at), 3) for name, bit in zip("RGB", on)}, len(dev.pin_log)


def look_cases(payload, flash=None, rest=True):
    """The options of the group CUSTOMIZATION: bottom LEDs (METER, COLOR, OFF, a colour), backlight colour mixed from three levels,
    the file, a missing card, EXIT at power-on, the firmware's own switches (the lock a plugin holds, power save)."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:look_{name}", "ok": bool(ok), "detail": detail})

    # defaults: nothing changes, with a card and without one
    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    add("defaults_are_stock", state(dev, S_LED_EFF) == 0 and state(dev, S_BL_ON) == 0x38 and state(dev, S_BL_PWM) == 0 and leds(dev) == [120] * 12 and pins(dev) == GPIO_PINS and not dev.m.asserts,
        f"effective LED kind {state(dev, S_LED_EFF)}, pins {pins(dev):#x}, LEDs {leds(dev)}")
    bare = boot(payload, flash, adapter=True, card=False)
    add("without_card_is_stock", state(bare, S_ON) == 1 and leds(bare) == [120] * 12 and pins(bare) == GPIO_PINS and state(bare, S_LED_EFF) == 0, f"LEDs {leds(bare)}, pins {pins(bare):#x}")

    # the pages
    texts = []
    for page in range(PAGE_LED_MODE, PAGE_BL_B + 1):
        goto_page(dev, page)
        texts.append((text(dev, S_TITLE), text(dev, S_VALUE), text(dev, S_LINE3)))
    add("pages", texts == [("BOTTOM LEDS", "METER", ""),
                           ("LED HUE", "STOCK", ""), ("LED SAT", "STOCK", ""), ("LED BRIGHT", "STOCK", ""),
                           ("BACKLIGHT HUE", "STOCK", ""), ("BACKLIGHT SAT", "STOCK", ""), ("BACKLIGHT BRIGHT", "STOCK", "")], str(texts))

    # the colour pages are hue (0 to 95, 16 to a sector of the wheel), saturation and brightness (0 to 15) of the stored red, green, blue
    rgb = lambda at: [state(dev, at + 4 * k) for k in range(3)]
    def shown(first):
        out = []
        for k in range(3):
            goto_page(dev, first + k)
            out.append(text(dev, S_VALUE))
        return out
    def dial(page, steps, at):
        goto_page(dev, page)
        dev.turn(steps, wait=0.25)
        return rgb(at)
    set_look(dev, backlight=(0, 0, 0))
    from_stock_up = [dial(PAGE_BL_G, 3, S_BL_R), dial(PAGE_BL_B, 3, S_BL_R)]
    from_stock_down = dial(PAGE_BL_B, -1, S_BL_R)
    set_look(dev, backlight=(0, 0, 0))
    first_hue = dial(PAGE_BL_R, 1, S_BL_R)
    set_look(dev, backlight=(15, 7, 0))
    orange = shown(PAGE_BL_R)
    next_sector = dial(PAGE_BL_R, 16, S_BL_R)
    set_look(dev, backlight=(15, 14, 14))
    white = dial(PAGE_BL_G, -1, S_BL_R)
    set_look(dev, backlight=(8, 8, 8))
    grey = dial(PAGE_BL_R, 1, S_BL_R)
    set_look(dev, backlight=(0, 0, 1))
    floor = dial(PAGE_BL_B, -8, S_BL_R)
    set_look(dev, backlight=(1, 0, 0))
    skipped = dial(PAGE_BL_R, 1, S_BL_R)
    set_look(dev, backlight=(0, 0, 0))
    add("hue_pages", from_stock_up == [[0, 0, 0]] * 2 and from_stock_down == [14, 0, 0] and first_hue == [15, 1, 0] and orange == ["7", "15", "15"]
        and next_sector == [8, 15, 0] and white == [0, 0, 0] and grey == [8, 8, 8] and floor == [0, 0, 1] and skipped == [1, 1, 0],
        f"up on SAT and BRIGHT {from_stock_up}, down on BRIGHT {from_stock_down}, HUE up {first_hue}, 15 7 0 shows {orange}, a sector on {next_sector}, "
        f"15 14 14 less saturated {white}, grey {grey}, brightness floor {floor}, small colour {skipped}")

    # DISPLAY, LED and PAD COLOR are rows of CUSTOMIZATION: ENTER opens their pages, EXIT goes back to the row (device 18.10.)
    rows, ins, backs = [], [], []
    for row, group, title, tag in ((CUSTOM_DISPLAY, GROUP_DISPLAY, "BACKLIGHT HUE", "Display"), (CUSTOM_LED, GROUP_LED, "BOTTOM LEDS", "LED")):
        goto_group(dev, GROUP_CUSTOM, row)
        rows.append(texts_of(dev))
        press(dev, "menu", 0.4)
        ins.append((state(dev, S_LEVEL), state(dev, S_GROUP), state(dev, S_PAGE), tab(dev), text(dev, S_TITLE), counter(dev)[1]))
        press(dev, "exit", 0.4)
        backs.append((state(dev, S_LEVEL), state(dev, S_GROUP), state(dev, S_PAGE), tab(dev)))
    press(dev, "exit", 0.4)
    top = (state(dev, S_LEVEL), state(dev, S_PAGE))
    add("customization_groups", rows == [("DISPLAY", "", PRESS), ("LED", "", PRESS)]
        and ins == [(2, GROUP_DISPLAY, 0, "Display", "BACKLIGHT HUE", 5), (2, GROUP_LED, 0, "LED", "BOTTOM LEDS", 9)]
        and backs == [(2, GROUP_CUSTOM, CUSTOM_DISPLAY, "Custom"), (2, GROUP_CUSTOM, CUSTOM_LED, "Custom")] and top[0] == 1 and not dev.m.asserts,
        f"rows {rows}, ENTER {ins}, EXIT {backs}, EXIT {top}")

    # bottom LEDs: a fixed colour, the colour as meter, off, and back to the stock meter
    set_look(dev, mode=1, led=(15, 7, 0))
    dev.run(0.4)
    color = leds(dev)
    set_look(dev, mode=0)
    meter_level(dev, 0)
    dev.run(1.0)
    quiet = leds(dev)
    meter_level(dev, 254)
    dev.run(1.0)
    loud = leds(dev)
    set_look(dev, mode=2)
    dev.run(0.5)
    off = leds(dev)
    set_look(dev, mode=0, led=(0, 0, 0))
    meter_level(dev, 254)
    dev.run(1.0)
    stock_loud = leds(dev)
    set_look(dev, mode=1)
    dev.run(0.5)
    stock_color = leds(dev)
    add("led_color", color == [255, 119, 0] * 4, f"{color}")
    add("led_meter_in_a_colour", quiet == [63, 29, 0] * 4 and loud[:3] == loud[3:6] == loud[6:9] == loud[9:] and loud[0] > 200 and loud[1] > quiet[1] and loud[2] == 0, f"quiet {quiet}, loud {loud}")
    add("led_off", off == [0] * 12, f"{off}")
    add("led_stock_meter_keeps_its_colours", stock_loud[:3] == stock_loud[3:6] and stock_loud[0] > 200 and stock_loud[1] == 0, f"{stock_loud}")
    add("led_color_without_a_colour_is_the_stock_white", stock_color == [120] * 12, f"{stock_color}")
    set_look(dev, mode=0)

    # the meter in four colours (device 18.10.): STILL red, LOUD pink from the palette, the zones left at STOCK keep the firmware's
    goto_group(dev, GROUP_LED, 4)
    still_page = texts_of(dev)
    dev.turn(2, wait=0.3)
    goto_group(dev, GROUP_LED, 7)
    dev.turn(7, wait=0.3)
    loud_page = texts_of(dev)
    meter_level(dev, 0)
    dev.run(1.0)
    m_still = leds(dev)
    meter_level(dev, 254)
    dev.run(1.0)
    m_loud = leds(dev)
    goto_group(dev, GROUP_LED, 4)
    dev.turn(-2, wait=0.3)
    goto_group(dev, GROUP_LED, 7)
    dev.turn(-7, wait=0.3)
    meter_level(dev, 254)
    dev.run(1.0)
    m_stock = leds(dev)
    add("led_meter_four_colours", still_page == ("METER STILL", "STOCK", "") and loud_page == ("METER LOUD", "PINK", "")
        and m_still == [255, 0, 0] * 4 and m_loud == [255, 0, 160] * 4 and m_stock[:3] == m_stock[3:6] and m_stock[0] > 200 and m_stock[1] == 0
        and state(dev, S_LED_EFF) == 0 and not dev.m.asserts, f"pages {still_page} {loud_page}, still {m_still}, loud {m_loud}, back to STOCK {m_stock}")

    # METER STILL RAINBOW (device wish 19.10.): the still meter turns round the colour wheel; WRITE keeps it as bit 30 of the flags
    goto_group(dev, GROUP_LED, 4)
    dev.turn(8, wait=0.3)
    rainbow_page = texts_of(dev)
    meter_level(dev, 0)
    dev.run(0.5)
    first = steady_leds(dev)     # the hue moves every tick: a read between two of the twelve channels mixes two hues
    dev.run(1.0)
    second = steady_leds(dev)
    wheel = lambda l: l[:3] * 4 == l and sorted(l[:3])[0] == 0 and sum(l[:3]) in (255, 256)      # 256: a 1 goes out as 2
    # RAINBOW with a colour on the LED pages (device 22.10.: the LED colour had no effect any more): the zones left at STOCK
    # take that colour, as bright as the level, the still meter stays on the wheel
    set_look(dev, mode=0, led=(15, 7, 0))
    meter_level(dev, 254)
    dev.run(1.0)
    r_loud = leds(dev)
    meter_level(dev, 0)
    dev.run(0.5)
    r_still = leds(dev)
    set_look(dev, mode=0, led=(0, 0, 0))
    add("led_meter_rainbow_keeps_the_led_colour", r_loud == loud and sorted(r_still[:3])[0] == 0 and sum(r_still[:3]) in (255, 256) and not dev.m.asserts,
        f"loud {r_loud} (the meter in that colour {loud}), still {r_still[:3]}")
    press(dev, "write", wait=0.6)
    files = read_settings(dev.m.mmc.card.medium.data)
    flags = max(files.values())[1] if files else 0
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(dev.m.mmc.card.medium.data))))
    again.run(1.5)
    kept = again.read(STATE - 0x1C, 1)[0]
    add("led_meter_still_rainbow", rainbow_page == ("METER STILL", "RAINBOW", "") and wheel(first) and wheel(second) and first != second
        and flags >> 30 & 1 == 1 and flags >> 16 & 7 == 0 and kept == 8 and not dev.m.asserts and not again.m.asserts,
        f"page {rainbow_page}, still {first[:3]} then {second[:3]} 1 s later, flags {flags:#x}, after a restart STILL {kept}")
    goto_group(dev, GROUP_LED, 4)
    dev.turn(-8, wait=0.3)

    # METER LOUD RAINBOW (device wish 24.10.): the full meter turns round the wheel too, a round a bar at the tempo;
    # WRITE keeps it as bit 0 of byte 5 of the file, the three bits of LOUD stay 0
    goto_group(dev, GROUP_LED, 7)
    dev.turn(8, wait=0.3)
    loud_rainbow_page = texts_of(dev)
    meter_level(dev, 254)
    dev.run(0.5)
    l_first = steady_leds(dev)
    dev.run(0.5)
    l_second = steady_leds(dev)
    tempo_at = synthaddr.tr(HW_TEMPO) if synthaddr.is_synth(payload) else HW_TEMPO
    tempo = dev.u32(tempo_at)
    phase = lambda d: int.from_bytes(d.read(STATE - 0x17, 2), "little")
    def turn(at, seconds=1.0):
        dev.m.uc.mem_write(tempo_at, struct.pack("<I", at))
        before = phase(dev)
        dev.run(seconds)
        dev.m.uc.mem_write(tempo_at, struct.pack("<I", tempo))
        return (phase(dev) - before) & 0xFFFF
    slow, fast = turn(600), turn(1200)
    press(dev, "write", wait=0.6)
    image = dev.m.mmc.card.medium.data
    files = read_settings(image)
    newest = max(files, key=lambda n: files[n][0]) if files else None
    l_flags = files[newest][1] if newest else 0
    extras = settings_extras(image).get(newest, 0)
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(1.5)
    l_kept = again.read(STATE - 0x1C, 4)
    add("led_meter_loud_rainbow", loud_rainbow_page == ("METER LOUD", "RAINBOW", "") and wheel(l_first) and wheel(l_second) and l_first != l_second
        and 1.6 < fast / max(slow, 1) < 2.4 and extras == 1 and l_flags >> 25 & 7 == 0 and l_kept[3] == 8 and l_kept[0] == 0
        and not dev.m.asserts and not again.m.asserts,
        f"page {loud_rainbow_page}, loud {l_first[:3]} then {l_second[:3]}, hue steps in 1 s at 60 BPM {slow}, at 120 BPM {fast}, "
        f"byte 5 {extras}, flags {l_flags:#x}, after a restart the meter bytes {list(l_kept)}")
    goto_group(dev, GROUP_LED, 7)
    dev.turn(-8, wait=0.3)

    # METER STILL OFF: the still meter stays dark, the louder zones keep their colours; WRITE keeps it as bit 1 of byte 5 of the
    # file, the three bits of STILL stay 0 (and STOCK, the page's first value, lights the still meter)
    goto_group(dev, GROUP_LED, 4)
    meter_level(dev, 0)
    dev.run(0.5)
    still_stock = leds(dev)
    dev.turn(9, wait=0.3)
    off_page = texts_of(dev)
    dev.run(0.5)
    off_still = leds(dev)
    dev.turn(1, wait=0.3)
    clamp_page = texts_of(dev)
    meter_level(dev, 254)
    dev.run(1.0)
    off_loud = leds(dev)
    meter_level(dev, 0)
    press(dev, "write", wait=0.6)
    image = dev.m.mmc.card.medium.data
    files = read_settings(image)
    newest = max(files, key=lambda n: files[n][0]) if files else None
    off_flags = files[newest][1] if newest else 0
    off_extras = settings_extras(image).get(newest, 0)
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(1.5)
    off_kept = again.read(STATE - 0x1C, 4)
    add("led_meter_still_off", off_page == ("METER STILL", "OFF", "") and clamp_page == off_page and any(still_stock)
        and off_still == [0] * 12 and off_loud[0] > 200 and off_extras & 2 == 2 and off_flags >> 16 & 7 == 0 and off_flags >> 30 & 1 == 0
        and off_kept[0] == 9 and not dev.m.asserts and not again.m.asserts,
        f"page {off_page}, one more turn {clamp_page}, STOCK still {still_stock[:3]}, OFF still {off_still}, loud {off_loud[:3]}, "
        f"byte 5 {off_extras}, flags {off_flags:#x}, after a restart the meter bytes {list(off_kept)}")
    goto_group(dev, GROUP_LED, 4)
    dev.turn(-9, wait=0.3)

    # the firmware's own switches stay: nothing changes while a plugin holds the lock, nothing lights with Global power save
    lock = boot(payload, flash, adapter=True)
    set_look(lock, mode=1, led=(15, 7, 0))
    lock.run(0.4)
    lock.m.uc.mem_write(lock.u32(LED_MANAGER) + LED_LOCK, b"\x01")
    set_look(lock, mode=2)
    lock.run(0.5)
    add("led_lock_of_a_plugin_wins", leds(lock) == [255, 119, 0] * 4, f"{leds(lock)}")
    save = boot(payload, flash, adapter=True)
    set_look(save, mode=1, led=(15, 7, 0))
    save.run(0.4)
    save.m.uc.mem_write(save.u32(POWER_SAVE_OBJECT) + 0x29, b"\x02")
    save.run(0.6)
    add("led_power_save_stays", leds(save) == [0] * 12 and not save.m.asserts, f"{leds(save)}")

    # backlight: a level of 0 or 15 is a plain pin, a level between is a software PWM of 16 ticks
    mix = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    watch_pins(mix)
    results, flags, lights = {}, {}, {}
    for name, levels in (("green", (0, 15, 0)), ("red5", (5, 0, 0)), ("mix", (3, 8, 12)), ("one_of_16", (1, 14, 0))):
        set_look(mix, backlight=levels)
        mix.run(0.3)
        results[name] = duty(mix, 1.0)
        flags[name] = state(mix, S_BL_PWM)
        lights[name] = mix.m.backlight.levels(mix.m.time_ns)   # what the emulator page draws the display in (backlight.py)
    near = lambda got, want: all(abs(got[k] - want[k]) <= 0.02 for k in "RGB")
    add("backlight_plain_pin", results["green"][0] == {"R": 0.0, "G": 1.0, "B": 0.0} and results["green"][1] == 0 and flags["green"] == 0 and flags["mix"] == 1, f"{results['green']}")
    add("backlight_pwm_duty", near(results["red5"][0], {"R": 5 / 16, "G": 0, "B": 0}) and near(results["mix"][0], {"R": 3 / 16, "G": 8 / 16, "B": 12 / 16})
        and near(results["one_of_16"][0], {"R": 1 / 16, "G": 14 / 16, "B": 0}), f"{results}")
    drawn = lambda got, want: got is not None and all(abs(g - w * 255) <= 3 for g, w in zip(got, want))
    add("backlight_colour_reaches_the_page", drawn(lights["green"], (0, 1, 0)) and drawn(lights["red5"], (5 / 16, 0, 0))
        and drawn(lights["mix"], (3 / 16, 8 / 16, 12 / 16)) and drawn(lights["one_of_16"], (1 / 16, 14 / 16, 0)), f"{lights}")
    # power save: the firmware's own dimming, as without our patch (red and green for 2 of 18 ticks in turn, never blue)
    set_look(mix, backlight=(0, 0, 12))
    mix.call(POWER_CONNECT, 1)
    mix.run(0.3)
    dimmed = duty(mix, 1.0)
    mix.call(POWER_CONNECT, 0)
    mix.run(0.3)
    resumed = duty(mix, 1.0)
    set_look(mix, backlight=(0, 0, 0))
    mix.run(0.3)
    stock = duty(mix, 1.0)
    lights["stock"] = mix.m.backlight.levels(mix.m.time_ns)
    add("backlight_power_save_stays", abs(dimmed[0]["R"] - 0.037) < 0.02 and abs(dimmed[0]["G"] - 0.037) < 0.02 and dimmed[0]["B"] == 0 and not mix.m.asserts, f"{dimmed}")
    add("backlight_back_from_power_save", near(resumed[0], {"R": 0, "G": 0, "B": 12 / 16}), f"{resumed}")
    add("backlight_zero_is_stock_white", stock[0] == {"R": 1.0, "G": 1.0, "B": 1.0} and stock[1] == 0 and state(mix, S_BL_PWM) == 0
        and lights["stock"] == [255, 255, 255], f"{stock} {lights['stock']}")
    # INTENSITY scales every level and keeps the mix; POWER SAVE, DISPLAY LIGHT gives power save the colour at its own intensity
    # (device 18.10.), 1 to 15 lighting at 3 to 15 (device 19.10.: 1 was dark on battery)
    set_look(mix, backlight=(0, 0, 12))
    goto_group(mix, GROUP_DISPLAY, 3)
    page = texts_of(mix)
    mix.turn(-7, wait=0.3)
    mix.run(0.3)
    scaled = duty(mix, 1.0)[0], texts_of(mix)[1]
    goto_group(mix, GROUP_PSAVE, 0)
    save_page = texts_of(mix)
    mix.turn(4, wait=0.3)
    mix.call(POWER_CONNECT, 1)
    mix.run(0.3)
    saved = duty(mix, 1.0)[0]
    mix.call(POWER_CONNECT, 0)
    mix.run(0.3)
    after = duty(mix, 1.0)[0]
    add("backlight_intensity", page == ("INTENSITY", "15", "") and scaled[1] == "8" and near(scaled[0], {"R": 0, "G": 0, "B": 6 / 16}), f"page {page}, at 8 {scaled}")
    add("backlight_save_light", save_page == ("DISPLAY LIGHT", "STOCK", "") and near(saved, {"R": 0, "G": 0, "B": 4 / 16}) and near(after, {"R": 0, "G": 0, "B": 6 / 16})
        and not mix.m.asserts, f"page {save_page}, power save at 4 {saved}, back {after}")
    mix.turn(-4, wait=0.3)
    goto_group(mix, GROUP_DISPLAY, 3)
    mix.turn(7, wait=0.3)
    set_look(mix, backlight=(0, 0, 0))

    # WRITE keeps everything in the file, the next start reads it
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, mode=0, led=(15, 7, 0), backlight=(0, 15, 6))
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    size = len(fat32.Volume(bytes(keep.m.mmc.card.medium.data)).read(SETTINGS_PATHS[1]))
    add("file_holds_the_look", files.get("b", (0, 0, 0, None))[3] == look_word(0, (15, 7, 0), (0, 15, 6), 1) and files["b"][:2] == (1, 3) and size == 24, f"{files}, {size} bytes")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(keep.m.mmc.card.medium.data))))
    watch_pins(again)
    again.run(1.5)
    meter_level(again, 0)
    again.run(1.0)
    got = [state(again, o) for o in (S_LED_MODE, S_LED_R, S_LED_G, S_LED_B, S_BL_R, S_BL_G, S_BL_B)]
    shown = duty(again, 1.0)[0]
    add("start_reads_and_applies_the_look", got == [0, 15, 7, 0, 0, 15, 6] and state(again, S_LED_EFF) == 1 and leds(again) == [63, 29, 0] * 4
        and shown["R"] == 0 and abs(shown["G"] - 1.0) < 0.02 and abs(shown["B"] - 6 / 16) < 0.02 and not again.m.asserts, f"{got}, LEDs {leds(again)}, light {shown}")

    # an old file (version 1) leaves the look at the stock settings, a damaged one is ignored, a look word out of range falls back
    old = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file(3, 3)}, adapter=True)
    add("version1_file_is_stock", (state(old, S_LED_MODE), state(old, S_LED_EFF), state(old, S_BL_ON), state(old, S_GEN)) == (0, 0, 0x38, 3) and leds(old) == [120] * 12,
        f"mode {state(old, S_LED_MODE)}, generation {state(old, S_GEN)}")
    bad = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, 3)}, adapter=True)
    add("mode_out_of_range_is_meter", state(bad, S_LED_MODE) == 0 and state(bad, S_LED_EFF) == 0, f"mode {state(bad, S_LED_MODE)}")
    flawed = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(1, (15, 0, 0)), bad_crc=True)}, adapter=True)
    add("bad_checksum_is_ignored", state(flawed, S_LED_MODE) == 0 and state(flawed, S_GEN) == 0 and leds(flawed) == [120] * 12, f"mode {state(flawed, S_LED_MODE)}")

    # EXIT at power-on: all of it stays stock, whatever the file says
    held = boot(payload, flash, held=KILL, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(4, 3, look_word(1, (15, 7, 0), (3, 8, 12)))}, adapter=True)
    watch_pins(held)
    held.run(0.5)
    kept = duty(held, 1.0)
    add("exit_held_is_stock", state(held, S_ON) != 1 and leds(held) == [120] * 12 and kept[0] == {"R": 1.0, "G": 1.0, "B": 1.0} and kept[1] == 0 and not held.m.asserts,
        f"on={state(held, S_ON):#x}, LEDs {leds(held)}, light {kept}")
    if rest:                                   # the suites after it; check.py runs each as a task of its own (LOOK_PARTS)
        for suite in look_rest():
            out.extend(suite(payload, flash))
    return out


def cases_task(i):
    """Part `i` of the screen cases in a worker (parallel.py, CASES_PARTS)."""
    import parallel
    return CASES_PARTS[i](parallel.shared["payload"], parallel.shared["flash"])


def splash_menu_cases(payload, flash=None):
    """CUSTOMIZATION, where the build has the splash editor: SPLASH IMPORT lists the .bmp files in KORG/blechtribe, the dial picks one
    and ENTER reads it into the start image; the value row shows the name alone (a name of more than 11 characters without ".bmp", cut
    to 11), SPLASH DRAW opens the editor (Global, page SPLASH SCREEN), SPLASH RESET drops the stored image and the VSB's own comes back; the
    three are a group of their own, the row SPLASH of CUSTOMIZATION opens it.
    Without the editor (the synth) the group keeps its 8 pages."""
    from splash_cases import bmp, image_of
    import splash_editor
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:splash_{name}", "ok": bool(ok), "detail": detail})

    pic = [[1 if (x + 2 * y) % 7 == 0 else 0 for x in range(128)] for y in range(64)]
    dev = boot(payload, flash, files={**CARD_FOLDER, "/KORG/blechtribe/splash.bmp": bmp(pic)})
    if dev.u32(splash_editor.IMPORT_ENTRY) == 0xFFFFFFFF:
        goto_group(dev, GROUP_CUSTOM, 0)
        add("no_pages_without_the_editor", counter(dev) is not None and counter(dev)[1] == 2 + custom_extra(dev), f"counter {counter(dev)}")
        return out
    goto_group(dev, GROUP_CUSTOM, CUSTOM_SPLASH)
    row = texts_of(dev)
    press(dev, "menu", 0.4)
    inside = (state(dev, S_LEVEL), state(dev, S_GROUP), counter(dev), tab(dev))
    press(dev, "exit", 0.4)
    out_again = (state(dev, S_GROUP), state(dev, S_PAGE), texts_of(dev)[0])
    add("group_of_its_own", row == ("SPLASH", "", PRESS) and inside == (2, GROUP_SPLASH, (0, 1), "Splash") and out_again == (GROUP_CUSTOM, CUSTOM_SPLASH, "SPLASH")
        and not dev.m.asserts, f"row {row}, ENTER {inside}, EXIT {out_again}")
    goto_group(dev, GROUP_SPLASH, 0)
    before = texts_of(dev)
    press(dev, "menu", 0.6)
    after = texts_of(dev)
    stored = dev.read(splash_editor.RECBUF + 8, 1024) == image_of(pic)
    add("import", before == ("SPLASH IMPORT", "splash.bmp", "") and after[:2] == ("SPLASH IMPORT", "loaded") and stored and not dev.m.asserts,
        f"{before} -> {after}, image {'stored' if stored else 'not stored'}")
    press(dev, "edit_next", 0.4)
    page = texts_of(dev)
    press(dev, "menu", 0.8)
    st = dev.u32(splash_editor.STATE + 4)
    battery = range(84, 98)                  # the status bar's battery symbol redraws itself in page 0 (docs/hintergrund/startbild-editor.md)
    want = splash_cases_display(image_of(pic))
    differ = [i for i, (a, b) in enumerate(zip(dev.fb(), want)) if a != b and i not in battery]
    add("draw_opens_the_editor", page == ("SPLASH DRAW", "", PRESS) and dev.screen()["number"] == 9 and dev.screen()["page"] == splash_editor.PAGE and st == 1
        and len(differ) <= 1 and not dev.m.asserts, f"{page}, screen {dev.screen()}, editor mode {st}, display bytes not the image (battery aside): {differ}")
    bare = boot(payload, flash, files=CARD_FOLDER)
    # the value row shows the value alone: no "press  [ Enter ]" on its row, nothing left of SPLASH DRAW's line from before the key
    goto_group(bare, GROUP_SPLASH, 1)
    press(bare, "edit_prev", 0.4)
    nofile = texts_of(bare)
    extra, missing = value_row_leftovers(bare)
    add("no_file_value_clean", nofile == ("SPLASH IMPORT", "no .bmp file", "") and not extra and not missing and not bare.m.asserts,
        f"{nofile}, {len(extra)} pixels beside the value, {len(missing)} of it missing")
    goto_group(bare, GROUP_SPLASH, 0)
    press(bare, "menu", 0.6)
    add("import_without_file", texts_of(bare)[1] == "no .bmp file", str(texts_of(bare)))
    lit_rows = {y for y in range(10, 62) for x in range(3, 120) if (bare.fb()[(y // 8) * 128 + x] >> (y % 8)) & 1}
    add("browser_empty", bare.read(STATE + S_BRW_ON, 1)[0] == 2 and lit_rows and max(lit_rows) - min(lit_rows) < 10,
        f"browser {bare.read(STATE + S_BRW_ON, 1)[0]}, rows lit between the edges {sorted(lit_rows)}")
    differ = browser_against_import_sample(payload, flash)
    add("browser_like_import_sample", differ == 0, f"{differ} pixels differ from the firmware's IMPORT SAMPLE (rows 10 to 63)")

    # the list: only .bmp files, no names starting with a dot (macOS ._ files), the dial walks them and stops at the ends, ENTER takes
    # the one shown; a name like Windows gives a second download
    other = [[1 if (x * y) % 5 == 0 else 0 for x in range(128)] for y in range(64)]
    files = {**CARD_FOLDER, "/KORG/blechtribe/splash.bmp": bmp(pic), "/KORG/blechtribe/._splash.bmp": b"\0" * 4096,
             "/KORG/blechtribe/notes.txt": b"x", "/KORG/blechtribe/splash (1).bmp": bmp(other)}
    dev = boot(payload, flash, files=files)
    goto_group(dev, GROUP_SPLASH, 0)
    seen = [texts_of(dev)[1]]
    for step in (1, 1, -1, -1, -1):
        dev.turn(step, wait=0.3)
        seen.append(texts_of(dev)[1])
    names = {"splash.bmp": pic, "splash (1)": other}   # a name of more than 11 characters is shown without ".bmp"
    walked = sorted(seen[:2]) == sorted(names) and seen[2] == seen[1] and seen[3] == seen[0] and seen[4] == seen[5] == seen[0]
    dev.turn(1, wait=0.3)
    shown = texts_of(dev)[1]
    press(dev, "menu", 0.6)
    taken = texts_of(dev)[1]
    stored = shown in names and dev.read(splash_editor.RECBUF + 8, 1024) == image_of(names[shown])
    dev.turn(-1, wait=0.3)
    add("list", walked and taken == "loaded" and stored and texts_of(dev)[1] == seen[0] and not dev.m.asserts,
        f"dial {seen}, ENTER on {shown!r} -> {taken!r}, image {'stored' if stored else 'not stored'}, then {texts_of(dev)[1]!r}")
    clean = []
    for step in (0, 1):                      # a name, the next name over it, then what ENTER said over that
        if step:
            dev.turn(step, wait=0.3)
        clean.append((texts_of(dev), *map(len, value_row_leftovers(dev))))
    dev.turn(-1, wait=0.3)
    press(dev, "menu", 0.6)
    clean.append((texts_of(dev), *map(len, value_row_leftovers(dev))))
    add("list_value_clean", [c[0][1:] for c in clean] == [(seen[0], ""), (seen[1], ""), ("loaded", "")] and all(c[1:] == (0, 0) for c in clean)
        and not dev.m.asserts, f"(texts, pixels beside the value, missing): {clean}")
    # a long name is cut to 11 characters (12 of the widest letter run into each other), ENTER still reads the file of that name
    dev = boot(payload, flash, files={**CARD_FOLDER, "/KORG/blechtribe/a-very-long-name-here.bmp": bmp(other)})
    goto_group(dev, GROUP_SPLASH, 0)
    long_texts, long_crowded = texts_of(dev), page_overlap(dev)
    if dev.read(STATE + S_BRW_ON, 1)[0]:     # the browser row: ".." after the cut name, clear of the scrollbar (x 120 on)
        near_bar = {p for p in lit(frame(dev), range(10, 51)) if 108 <= p[0] < 120}
        long_crowded = long_crowded or (f"row ink next to the scrollbar {sorted(near_bar)[:4]}" if near_bar else None)
        long_crowded = long_crowded or (lambda e, m: f"{len(e)} pixels left over, {len(m)} missing" if e or m else None)(*value_row_leftovers(dev))
    press(dev, "menu", 0.6)
    stored = dev.read(splash_editor.RECBUF + 8, 1024) == image_of(other)
    add("long_name_cut", long_texts == ("SPLASH IMPORT", "a-very-long", "") and long_crowded is None and texts_of(dev)[1] == "loaded" and stored
        and not dev.m.asserts, f"{long_texts}, {long_crowded}, ENTER -> {texts_of(dev)[1]!r}, image {'stored' if stored else 'not stored'}")
    from splash_cases import DESC13
    desc = lambda d: d.u32(DESC13)
    record_id = lambda d: struct.unpack_from("<I", d.m.flash.mem, splash_editor.FLASH_RECORD)[0]
    dev = boot(payload, flash, files={**CARD_FOLDER, "/KORG/blechtribe/splash.bmp": bmp(pic)})
    goto_group(dev, GROUP_SPLASH, 0)
    press(dev, "menu", 0.6)
    imported = (desc(dev), record_id(dev))
    press(dev, "edit_next", 0.4)
    press(dev, "edit_next", 0.4)
    reset_page = texts_of(dev)
    press(dev, "menu", 0.8)
    reset_after = texts_of(dev)
    orig = dev.u32(splash_editor.STATE + 0x34)
    add("reset", imported == (splash_editor.RECBUF + 8, splash_editor.RECORD_ID) and reset_page == ("SPLASH RESET", "", PRESS)
        and reset_after[:2] == ("SPLASH RESET", "original back") and desc(dev) == orig != splash_editor.RECBUF + 8 and record_id(dev) == 0 and not dev.m.asserts,
        f"after import image {imported[0]:#x}, record id {imported[1]:#x}; {reset_page} -> {reset_after}, image {desc(dev):#x} (VSB's {orig:#x}), record id {record_id(dev):#x}")
    again = Dev(payload, flash, 0)
    again.m.flash.mem[:] = dev.m.flash.mem
    again.m.insert_card(SDCard(MemoryMedium(card_image(CARD_FOLDER))))
    again.run(1.2)
    add("reset_kept_after_restart", desc(again) == orig and not again.m.asserts, f"next start draws {desc(again):#x}, the VSB's image is {orig:#x}")
    return out


def wheel_burst(dev, delta, steps=20, gap=0.015):
    """`steps` dial events `gap` seconds apart, as a fast turn sends them, then run until the display stays the same for 0.3 s
    -> ms from the last event to the last change of the display (the lag)."""
    for _ in range(steps):
        dev.turn(delta, wait=gap)
    last_event = dev.m.time_ns
    shown, stable_since, changed_at = dev.fb(), dev.m.time_ns, dev.m.time_ns
    while dev.m.time_ns - stable_since < 300e6 and dev.m.time_ns - last_event < 10e9:
        dev.run(0.01)
        if dev.fb() != shown:
            shown, stable_since, changed_at = dev.fb(), dev.m.time_ns, dev.m.time_ns
    return (changed_at - last_event) / 1e6


WHEEL_LAG_MS = 150     # IMPORT SAMPLE of DATA UTILITY measured 60 to 70 ms with 30 files (docs/messungen/2026-11-09-menue-liste-rad.md)


def wheel_cases(payload, flash=None):
    """The value dial on the lists with a browser look: PLUGINS (MANAGE PLUGINS) moves through its plugins with the dial and stops at
    the ends, SPLASH IMPORT and PLUGINS keep up with a fast turn (20 steps 15 ms apart, display settled within WHEEL_LAG_MS of the last
    step), and SPLASH IMPORT still reads names past the 64 it keeps in its list."""
    from splash_cases import bmp
    import splash_editor
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:wheel_{name}", "ok": bool(ok), "detail": detail})

    def blech(name):
        block = bytearray(256)
        struct.pack_into("<I", block, 0, 0x52435347)
        block[36:52] = name.encode().ljust(16, b"\0")
        return bytes(block)

    names = [f"file{i:02d}" for i in range(30)]
    dev = boot(payload, flash, files={**CARD_FOLDER, **{f"/KORG/blechtribe/Plugin/{n}.blech": blech(n) for n in names}})
    goto_top(dev, LIST_PLUGINS)
    press(dev, "menu", 1.5)
    opened = (state(dev, S_LEVEL), counter(dev), texts_of(dev))
    seen = []
    for step in (1, 1, -1, -1):
        dev.turn(step, wait=0.4)
        seen.append((state(dev, S_LEVEL), counter(dev)[0], texts_of(dev)[0]))
    add("plugin_list_moves", opened == (LEVEL_PLUGIN, (0, 30), ("file00", "OFF", "")) and seen == [(LEVEL_PLUGIN, 1, "file01"), (LEVEL_PLUGIN, 2, "file02"),
        (LEVEL_PLUGIN, 1, "file01"), (LEVEL_PLUGIN, 0, "file00")] and not dev.m.asserts, f"opened {opened}, dial {seen}")
    lag = wheel_burst(dev, 1)
    up = (counter(dev)[0], texts_of(dev)[0], dev.read(STATE + 0x14C, 1)[0])
    lag_down = wheel_burst(dev, -1)
    add("plugin_list_fast", up == (20, "file20", 20) and counter(dev)[0] == 0 and max(lag, lag_down) <= WHEEL_LAG_MS and not dev.m.asserts,
        f"20 steps up -> {up}, lag {lag:.0f} ms; 20 down -> {counter(dev)}, lag {lag_down:.0f} ms (bound {WHEEL_LAG_MS})")
    dev.turn(-3, wait=0.4)
    low = counter(dev)
    goto_plugin(dev, 29)
    dev.turn(2, wait=0.4)
    add("plugin_list_stops_at_the_ends", low == (0, 30) and counter(dev) == (29, 30) and texts_of(dev)[0] == "file29", f"below the first {low}, past the last {counter(dev)}")
    goto_plugin(dev, 0, PLUGIN_ACTIVE)
    page = texts_of(dev)
    dev.turn(1, wait=0.4)
    add("plugin_active_page", page == ("ACTIVE", "OFF", "") and state(dev, S_LEVEL) == LEVEL_PSUB and counter(dev) == (0, 3), f"{page}, then dial up {texts_of(dev)}, counter {counter(dev)}")

    pic = [[0] * 128 for _ in range(64)]
    dev = boot(payload, flash, files={**CARD_FOLDER, **{f"/KORG/blechtribe/{n}.bmp": bmp(pic) for n in names}})
    if dev.u32(splash_editor.IMPORT_ENTRY) == 0xFFFFFFFF:
        return out
    goto_group(dev, GROUP_SPLASH, 0)
    lag = wheel_burst(dev, 1)
    up = texts_of(dev)[1]
    lag_down = wheel_burst(dev, -1)
    add("splash_import_fast", up == "file20.bmp" and texts_of(dev)[1] == "file00.bmp" and max(lag, lag_down) <= WHEEL_LAG_MS and not dev.m.asserts,
        f"20 steps up -> {up!r}, lag {lag:.0f} ms; 20 down -> {texts_of(dev)[1]!r}, lag {lag_down:.0f} ms (bound {WHEEL_LAG_MS})")
    # past the 64 names kept in the list the name is read from the card, ENTER loads that file
    other = [[1 if (x * y) % 5 == 0 else 0 for x in range(128)] for y in range(64)]
    many = {f"/KORG/blechtribe/f{i:02d}.bmp": bmp(other if i == 66 else pic) for i in range(70)}
    dev = boot(payload, flash, files={**CARD_FOLDER, **many})
    goto_group(dev, GROUP_SPLASH, 0)
    for _ in range(66):
        dev.turn(1, wait=0.05)
    dev.run(0.5)
    shown = texts_of(dev)[1]
    press(dev, "menu", 0.8)
    from splash_cases import image_of
    stored = dev.read(splash_editor.RECBUF + 8, 1024) == image_of(other)
    add("splash_import_past_64", shown == "f66.bmp" and texts_of(dev)[1] == "loaded" and stored and not dev.m.asserts,
        f"66 steps -> {shown!r}, ENTER -> {texts_of(dev)[1]!r}, image {'stored' if stored else 'not stored'}")
    return out


def browser_against_import_sample(payload, flash=None, turns=4):
    """SPLASH IMPORT against the firmware's own file browser (DATA UTILITY, IMPORT SAMPLE, screen 39) with the same names: five
    .wav files and the folder KORG there, KORG.bmp and the five names as .bmp here. After `turns` steps of the dial the folder row is
    out of sight (its icon is the folder's), so rows 10 to 63 (below the header with its tab) are compared -> the pixels that differ,
    or None when IMPORT SAMPLE was not reached."""
    import highram_watch as hw
    import fat32
    from splash_cases import bmp
    names =["Clap Melodic Long", "Claps Synthwave", "Deep House Tom", "Kick", "Snare 909 roomy"]
    rows = lambda fb: {(x, y) for y in range(10, 64) for x in range(128) if (fb[(y // 8) * 128 + x] >> (y % 8)) & 1}
    img = fat32.format_image(64 * 1024 * 1024)
    vol = fat32.Volume(img)
    for name in names:
        vol.write(f"/{name}.wav", hw.plain_wav(2000))
    vol.write(f"/KORG/{hw.folder(payload)}/Sample/x.txt", b"x")
    vol.close()
    ref = Dev(payload, flash, 0)
    ref.m.insert_card(SDCard(MemoryMedium(img)))
    ref.run(1.2)
    for _ in range(40):
        if ref.m.screen() == 1:
            break
        ref.run(0.5)
    ref.run(2)
    ref.call(SWITCH_SCREEN, 14, 0)
    ref.run(0.4)
    for key, count, wait in (("menu", 1, 0.5), ("right", 8, 0.25), ("menu", 1, 1.5)):
        for _ in range(count):
            ref.m.press(hw.KEYS[key], True)
            ref.run(0.1)
            ref.m.press(hw.KEYS[key], False)
            ref.run(wait)
    if ref.m.screen() != 39:
        return None
    for _ in range(turns):
        ref.turn(1, 0.8)
    pic = [[0] * 128 for _ in range(64)]
    files = {**CARD_FOLDER, "/KORG/blechtribe/KORG.bmp": bmp(pic), **{f"/KORG/blechtribe/{name}.bmp": bmp(pic) for name in names}}
    ours = boot(payload, flash, files=files)
    goto_group(ours, GROUP_SPLASH, 0)
    for _ in range(turns):
        ours.turn(1, wait=0.4)
    return len(rows(ref.fb()) ^ rows(ours.fb()))


def splash_cases_display(image):
    from splash_cases import display_of
    return display_of(image)


def pad_colour_cases(payload, flash=None):
    """CUSTOMIZATION, PAD COLOR and SELECT COLOR (patch pad-colors): the pads take the chosen colours at once, both together take the
    colour that is left, the two pages never hold the same colour, WRITE keeps them for the next start, EXIT at power-on is stock."""
    import pad_colors as PC
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:padcolor_{name}", "ok": bool(ok), "detail": detail})

    pad = lambda d, n: (d.m.leds.get(0x2C + 2 * n, 0), d.m.leds.get(0x2D + 2 * n, 0))
    wait = 10.0 if synthaddr.is_synth(payload) else 1.2       # the synth reaches its main screen after about 8 s (docs/messungen/2026-10-16-blech-synth.md)
    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True, seconds=wait)
    if dev.u32(PC.CODE_AT) == 0xFFFFFFFF:
        return out
    stock = pad(dev, 0)
    goto_group(dev, GROUP_PADS, 0)
    p8 = texts_of(dev)
    press(dev, "edit_next", wait=0.4)
    p9 = texts_of(dev)
    add("pages", p8 == ("PAD COLOR", "RED", "") and p9 == ("SELECT COLOR", "BLUE", "") and stock == (0, 255),
        f"{p8} {p9}, pad 1 (the selected part) {stock}")
    dev.turn(1, wait=0.4)
    pink = texts_of(dev)[1], pad(dev, 0)
    dev.turn(1, wait=0.4)
    skipped = texts_of(dev)[1]
    add("select_at_once", pink == ("PINK", (255, 255)), f"SELECT one step up: {pink}")
    add("never_the_same", skipped == "BLUE", f"one more step from PINK skips RED (the PAD COLOR): {skipped}")
    press(dev, "edit_prev", wait=0.4)
    dev.turn(1, wait=0.4)
    pad_pink = texts_of(dev)[1]
    press(dev, "edit_next", wait=0.4)
    dev.turn(1, wait=0.4)
    sel_red = texts_of(dev)[1], pad(dev, 0)
    add("pad_skips_select", pad_pink == "PINK" and sel_red == ("RED", (255, 0)), f"PAD COLOR from RED skips BLUE: {pad_pink}; SELECT then RED: {sel_red}")
    go(dev, 1)
    dev.m.send([4, 3, 0, 100, 1])
    dev.run(0.15)
    both = pad(dev, 3)
    dev.m.send([4, 3, 0, 0, 0])
    dev.run(0.3)
    add("overlap_is_the_colour_left", both == (0, 255), f"pad 4 held and selected (PINK and RED): {both}, the colour left is blue")
    # OVERLAP chosen (device 18.10.): red instead of the colour left
    goto_group(dev, GROUP_PADS, 2)
    over_page = texts_of(dev)
    dev.turn(1, wait=0.4)
    over_red = texts_of(dev)[1]
    go(dev, 1)
    dev.m.send([4, 3, 0, 100, 1])
    dev.run(0.15)
    both_red = pad(dev, 3)
    dev.m.send([4, 3, 0, 0, 0])
    dev.run(0.3)
    add("overlap_chosen", over_page == ("OVERLAP", "AUTO", "") and over_red == "RED" and both_red == (255, 0), f"page {over_page}, then {over_red}, pad 4 held and selected {both_red}")
    goto_group(dev, GROUP_PADS, 0)
    press(dev, "write", wait=0.6)
    word = read_settings_look(dev.m.mmc.card.medium.data).get("b", (0, 0, 0, None))[3]
    add("file_holds_them", word is not None and (word >> 2) & 3 == PC.PINK and (word >> 29) & 3 == 1, f"look word {word:#x}" if word is not None else "no file")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(dev.m.mmc.card.medium.data))))
    again.run(wait + 0.8)
    add("start_reads_them", again.u32(PC.PC_SETTING) == PC.PINK | PC.RED << 4 | 1 << 8 and pad(again, 0) == (255, 0) and not again.m.asserts,
        f"setting {again.u32(PC.PC_SETTING):#x}, pad 1 {pad(again, 0)}")
    held = Dev(payload, flash, KILL)
    held.m.adapter = True
    held.m.insert_card(SDCard(MemoryMedium(bytearray(dev.m.mmc.card.medium.data))))
    held.run(wait + 0.8)
    add("exit_held_is_stock", pad(held, 0) == (0, 255) and not held.m.asserts, f"pad 1 {pad(held, 0)}")

    # power save: while the firmware dims (its switch 0xC0028AB4 with 1), every LED goes out at a quarter, at once; back with 0
    def dimmed(d):
        before = dict(d.m.leds)
        d.call(PC.DIM_SWITCH, 1)
        d.run(0.3)
        during = dict(d.m.leds)
        d.call(PC.DIM_SWITCH, 0)
        d.run(0.3)
        return before, during, dict(d.m.leds)
    plain = boot(payload, flash, files=CARD_FOLDER, adapter=True, seconds=wait)
    before, during, after = dimmed(plain)
    lit = {led: v for led, v in before.items() if v and not 0x4C <= led <= 0x57}   # the bottom RGB LEDs: power save switches them off itself
    quarter = {led: during.get(led, 0) for led in lit}
    # the knob LEDs 0 to 4 go out, every other one is at a quarter (device 18.10.)
    add("power_save_dims_every_led", lit and any(led <= 4 for led in lit) and all(quarter[led] == (0 if led <= 4 else (v + 3) >> 2) for led, v in lit.items())
        and {led: after.get(led, 0) for led in lit} == lit
        and not plain.m.asserts, f"lit before {lit}, while dimmed {quarter}, after {({led: after.get(led, 0) for led in lit})}")
    before, during, after = dimmed(again)
    add("power_save_with_colours", pad(again, 0) == (255, 0) and (during.get(0x2C, 0), during.get(0x2D, 0)) == (64, 0) and not again.m.asserts,
        f"pad 1 in RED while dimmed {(during.get(0x2C, 0), during.get(0x2D, 0))}, after {pad(again, 0)}")
    battery = boot(payload, flash, files=CARD_FOLDER, seconds=wait)
    dims = battery.read(PC.DIM_FLAG, 1)[0] != 0      # whether the firmware dims on battery depends on POWER SAVE in the flash (Auto in the dump)
    want = (0, 64) if dims else (0, 255)
    add("power_save_on_battery_from_the_start", pad(battery, 0) == want and not battery.m.asserts,
        f"on battery the firmware {'dims' if dims else 'does not dim (POWER SAVE of this flash)'} from power-on: pad 1 {pad(battery, 0)}, TAP LED {battery.m.leds.get(0x14, 0)}")
    before, during, after = dimmed(held)
    add("power_save_exit_held_is_stock", during.get(0x2D, 0) == 255 and not held.m.asserts, f"EXIT held: pad 1 blue while dimmed {during.get(0x2D, 0)}")
    # POWER SAVE, LED DIMMING: 75 percent when never set; 0 percent leaves every LED (the knobs too), 100 percent puts all out (device wish 19.10.)
    goto_group(plain, GROUP_PSAVE, 1)
    first = texts_of(plain)
    def at(turn):
        plain.turn(turn, wait=0.4)
        b, d, _ = dimmed(plain)
        shown = {led: v for led, v in b.items() if v and not 0x4C <= led <= 0x57}
        return texts_of(plain)[1], shown, {led: d.get(led, 0) for led in shown}
    none, full, part = at(-8), at(11), at(-4)
    # at 0 percent BLECH leaves every LED as the firmware sends it; the knob LEDs then show the firmware's own power save value
    knobless = lambda d: {led: v for led, v in d.items() if led > 4}
    add("power_save_led_dimming", first == ("LED DIMMING", "75%", "") and none[0] == "0%" and knobless(none[1]) and knobless(none[2]) == knobless(none[1])
        and full[0] == "100%" and set(full[2].values()) == {0}
        and part[0] == "70%" and all(part[2][led] == (0 if led <= 4 else (v * 30 + 99) // 100) for led, v in part[1].items()) and not plain.m.asserts,
        f"page {first}; at {none[0]} {none[1]} -> {none[2]}; at {full[0]} -> {full[2]}; at {part[0]} {part[1]} -> {part[2]}")
    press(plain, "write", wait=0.6)
    look = read_settings_look(plain.m.mmc.card.medium.data).get("b", (0, 0, 0, None))
    keep = Dev(payload, flash, 0)
    keep.m.adapter = True
    keep.m.insert_card(SDCard(MemoryMedium(bytearray(plain.m.mmc.card.medium.data))))
    keep.run(wait + 0.8)
    goto_group(keep, GROUP_PSAVE, 1)
    add("power_save_led_dimming_kept", texts_of(keep)[1] == "70%" and not keep.m.asserts, f"after WRITE and a new start: {texts_of(keep)}, file {look}")
    out += chord_cases(payload, flash, add, pad, wait)
    return out


def chord_cases(payload, flash, add, pad, wait):
    """SEQUENCER mode, part 1 Poly 1: the steps that hold 2 or more notes show pink, the others red (device wish 18.10.); the same
    steps of a Mono part and with EXIT held at power-on stay red. Part 1 gets chords on steps 5, 9 and 13, one note on 3, 7, 11 and 15."""
    def chords(held, voice):
        dev = boot(payload, flash, held=held, files=CARD_FOLDER, adapter=True, seconds=wait)
        live = dev.u32(0xC033E6A4) + 4 + 0x800
        dev.m.uc.mem_write(live + 2, bytes([voice]))
        for step in range(16):
            notes = [61, 65] if step in (4, 8, 12) else [63] if step % 4 == 2 else []
            dev.m.uc.mem_write(live + 0x30 + 12 * step, bytes([1 if notes else 0, 60, 100, 1, *notes, *[0] * (4 - len(notes))]))
        press(dev, 0x15, wait=0.5)
        return dev, [pad(dev, n) for n in range(16)]
    poly, lit = chords(0, 2)
    pink = [n for n in range(16) if lit[n] == (255, 255)]
    red = [n for n in range(16) if lit[n] == (255, 0)]
    add("chord_pink", pink == [4, 8, 12] and red == [2, 6, 10, 14] and not poly.m.asserts, f"Poly 1: pink {pink}, red {red}, all {lit}")
    mono, lit = chords(0, 0)
    add("chord_mono_red", [n for n in range(16) if lit[n] == (255, 0)] == [2, 4, 6, 8, 10, 12, 14] and not mono.m.asserts, f"Mono 1: {lit}")
    held, lit = chords(KILL, 2)
    add("chord_exit_held_is_stock", [n for n in range(16) if lit[n] == (255, 0)] == [2, 4, 6, 8, 10, 12, 14] and not held.m.asserts,
        f"EXIT held at power-on, Poly 1: {lit}")
    tie_cases(payload, flash, add, pad, wait)
    return []


def tie_cases(payload, flash, add, pad, wait):
    """SEQUENCER mode: a note tied over several steps (TIE, gate 127, the note on both steps) shows its trigger as the firmware does
    and the steps it is held through as a tail in pink that fades over the note's length, tails of notes that overlap add up (device
    wishes 17.10. and 19.10.). Part 1, Mono 1: steps 1 to 5 one tied note, step 7 tied into step 8 on another note (two triggers),
    step 10 tied into nothing. Setting a tie on step 12 shows the tail on step 13 once the firmware sends pad 12 again (a press on it
    twice). Poly 1: one note held over steps 1 to 4, a second from step 3 to 6."""
    def steps(held, voice=0, plan=None):
        dev = boot(payload, flash, held=held, files=CARD_FOLDER, adapter=True, seconds=wait)
        live = dev.u32(0xC033E6A4) + 4 + 0x800
        dev.m.uc.mem_write(live + 2, bytes([voice]))
        plan = plan or {0: (127, [61]), 1: (127, [61]), 2: (127, [61]), 3: (127, [61]), 4: (60, [61]), 6: (127, [61]), 7: (60, [65]),
                        9: (127, [61]), 11: (60, [61]), 12: (60, [61])}
        for step in range(64):
            gate, notes = plan.get(step, (0, []))
            dev.m.uc.mem_write(live + 0x30 + 12 * step, bytes([1 if notes else 0, gate, 100, 1, *notes, *[0] * (4 - len(notes))]))
        press(dev, 0x15, wait=0.5)
        return dev, live, [pad(dev, n) for n in range(16)]
    dev, live, lit = steps(0)
    want = {0: (255, 255), 1: (203, 203), 2: (152, 152), 3: (101, 101), 4: (50, 50), 6: (255, 0), 7: (255, 0), 9: (255, 0), 11: (255, 0), 12: (255, 0)}
    # pad 1 is blue as well: the firmware's cursor on the first step while it stands
    got = {n: lit[n] for n in want}
    add("tie_tail_gets_darker", got == want and all(lit[n] == (0, 0) for n in range(16) if n not in want) and not dev.m.asserts,
        f"Mono 1, tied 1 to 5, 7 into 8 on another note, 10 into nothing: {lit}")
    dev.m.uc.mem_write(live + 0x30 + 12 * 11 + 1, bytes([127]))
    for _ in range(2):
        dev.m.send([4, 11, 0, 100, 1])
        dev.run(0.1)
        dev.m.send([4, 11, 0, 0, 0])
        dev.run(0.3)
    add("tie_tail_follows_an_edit", pad(dev, 12) == (127, 127) and pad(dev, 11) == (255, 0) and not dev.m.asserts,
        f"step 12 tied, pad 12 sent again: pad 12 {pad(dev, 11)}, pad 13 {pad(dev, 12)}")
    poly, _, lit = steps(0, 2, {0: (127, [61]), 1: (127, [61]), 2: (127, [61, 65]), 3: (127, [61, 65]), 4: (127, [65]), 5: (60, [65])})
    added = [(255, 255), (191, 191), (255, 255), (255, 255), (127, 127), (63, 63)]
    add("tie_tails_add_up", lit[:6] == added and not poly.m.asserts,
        f"Poly 1, one note over steps 1 to 4, one over 3 to 6: {lit[:6]}, want {added} (step 3 a trigger, step 4 a quarter and three quarters)")
    held, _, lit = steps(KILL)
    add("tie_exit_held_is_stock", [n for n in range(16) if lit[n] == (255, 0)] == sorted(want)[1:] and lit[0] == (255, 255) and not held.m.asserts,
        f"EXIT held at power-on: {lit}")
    if synthaddr.is_synth(payload):
        return      # the race below drives the Sampler's UART queue directly; the colour code it checks is the same on the synth
    from unicorn import UC_HOOK_CODE
    from machine import UART0
    from tools.patch import arm
    changing, live, _ = steps(0, 0, {i: (127, [61]) for i in range(64)})
    manager = changing.u32(0xC0345A1C)
    sent, full = [], []
    producer = arm.assemble(f""".org 0x10000
    push {{r4-r8, lr}}
    mov r4, r0
    mov r5, r1
    mov r6, #4096
    ldr r7, ={changing.a(0xC0087578):#x}
    ldr r8, =0x10FF0
produce:
    mov r0, r4
    mov r1, r5
    mov lr, pc
    bx r7
    ldr r0, [r8]
    cmp r0, #0
    bne produced
    subs r6, r6, #1
    bne produce
produced:
    pop {{r4-r8, pc}}
    .pool
""").sections[0][1]
    changing.m.uc.mem_map(0x10000, 0x1000)
    changing.m.uc.mem_write(0x10000, producer)

    def sending(uc, address, size, data):
        if not sent:
            uart = changing.m.uart[UART0]
            uart["thre"], uart["busy"] = False, changing.m.time_ns + 2_000_000
            sent.append("stalled")
        message = changing.read(uc.reg_read(arm_const.UC_ARM_REG_R1), 3)
        if message[0] == 0x2C and "edited" not in sent:
            uc.mem_write(live + 0x30 + 16*12 + 1, bytes([126]))
            sent.append("edited")

    sender = changing.a(0xC0087578)        # the LED sender, the synth's from data/synth-map/
    sender_hook = changing.m.uc.hook_add(UC_HOOK_CODE, sending, begin=sender, end=sender)
    def queue_full(*args):
        full.append(1)
        changing.m.uc.mem_write(0x10FF0, struct.pack("<I", 1))

    full_hook = changing.m.uc.hook_add(UC_HOOK_CODE, queue_full,
                                      begin=changing.m.profile.tx_full, end=changing.m.profile.tx_full)
    try:
        changing.call(0x10000, changing.u32(manager+0xB54), 0x10FF4)
        changing.m.uc.mem_write(0xC018BF3C, struct.pack("<I", 1))
        changing.call(changing.a(0xC00875F4), manager, 0x2C, 1)
        changing.run(0.3)
    finally:
        changing.m.uc.hook_del(sender_hook)
        changing.m.uc.hook_del(full_hook)
        changing.m.uc.ctl_flush_tb()
    add("tie_unseen_edit_during_full_queue", sent == ["stalled", "edited"] and bool(full)
        and pad(changing, 15) == (29, 29) and not changing.m.asserts,
        f"edit outside the visible bar while sending: {sent}, full queue {len(full)}, pad 16 {pad(changing,15)}")


def invert_cases(payload, flash=None):
    """The page DISPLAY INVERT of the group CUSTOMIZATION: ON is the default (a card without a file, no card, a version 1 file, a
    damaged file), the controller is told 0xA7 (reverse display) or 0xA6 (normal) once per change, the file keeps it (bit 28 of
    the look word, a version 2 file without the bit is OFF), and EXIT at power-on leaves the controller alone. The emulator's
    controller (machine.py) swaps dark and clear on 0xA7: shown() is the complement of the RAM."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:look_invert_{name}", "ok": bool(ok), "detail": detail})

    ram = lambda dev: bytes(b for row in dev.m.fb for b in row)
    flipped = lambda dev: dev.m.shown() == bytes(b ^ 0xFF for b in ram(dev)) and ram(dev) != bytes(len(ram(dev)))
    plain = lambda dev: dev.m.shown() == ram(dev)
    status = lambda dev: (state(dev, S_INVERT), dev.m.lcd_reverse, dev.m.lcd_reverse_sent)

    # ON is the default, with a card without a file and without a card: the controller is told 0xA7 once
    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    bare = boot(payload, flash, adapter=True, card=False)
    add("default_on", status(dev) == (1, True, 1) and status(bare) == (1, True, 1) and flipped(dev) and flipped(bare) and state(bare, S_ON) == 1,
        f"with card {status(dev)}, without {status(bare)}")

    # the page, off and on through the main dial: one command per change, the whole display swaps, the main screen too
    goto_page(dev, PAGE_INVERT)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(-1, wait=0.4)
    dev.run(0.3)
    off = texts_of(dev), status(dev), plain(dev)
    dev.turn(-1, wait=0.3)
    dev.run(0.3)
    still = status(dev)
    go(dev, 1)
    dev.run(0.5)
    main_off = dev.screen()["number"], status(dev), plain(dev)
    add("page", page == (("DISPLAY INVERT", "ON", ""), (4, 5), "Display"), f"{page}")
    add("off_swaps_the_display", off == (("DISPLAY INVERT", "OFF", ""), (0, False, 2), True) and still == (0, False, 2),
        f"{off}, dial again {still}")
    add("main_screen_plain", main_off == (1, (0, False, 2), True) and not dev.m.asserts, f"{main_off}")
    goto_page(dev, PAGE_INVERT)
    dev.turn(1, wait=0.4)
    dev.run(0.3)
    on = texts_of(dev), status(dev), flipped(dev)
    add("on_swaps_back", on == (("DISPLAY INVERT", "ON", ""), (1, True, 3), True), f"{on}")

    # WRITE keeps it in the same file as the other CUSTOMIZATION values (bit 28), the next start reads it and shows it
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, led=(15, 7, 0))
    goto_page(keep, PAGE_INVERT)
    keep.turn(-1, wait=0.4)
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    word = files.get("b", (0, 0, 0, None))[3]
    add("file_holds_off", word is not None and word == look_word(0, (15, 7, 0), (0, 0, 0), 0), f"{files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(keep.m.mmc.card.medium.data))))
    again.run(2.0)
    add("start_reads_off", status(again) == (0, False, 0) and plain(again) and not again.m.asserts, f"{status(again)}, screen {again.screen()['number']}")

    # a version 1 file says nothing about it and a damaged file is ignored: ON; a version 2 file without the bit is OFF
    quiet = []
    for name, files in (("v1", {SETTINGS_PATHS[0]: settings_file(3, 3)}),
                        ("bad_crc", {SETTINGS_PATHS[0]: settings_file_v2(3, 3, look_word(1, (15, 0, 0)), bad_crc=True)})):
        probe = boot(payload, flash, files={**CARD_FOLDER, **files}, adapter=True)
        quiet.append((name, status(probe)))
    add("files_without_it_stay_on", all(got == (1, True, 1) for _, got in quiet), f"{quiet}")
    plain_file = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(3, 3, look_word(1, (15, 0, 0)))}, adapter=True)
    add("file_without_the_bit_is_off", status(plain_file) == (0, False, 0) and plain(plain_file), f"{status(plain_file)}")

    # EXIT at power-on: stock, the controller is never told anything, whatever the file says
    held = boot(payload, flash, held=KILL, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(4, 3, look_word(invert=1))}, adapter=True)
    held.run(0.5)
    add("exit_held_is_stock", state(held, S_ON) != 1 and status(held)[1:] == (False, 0) and plain(held) and not held.m.asserts, f"on={state(held, S_ON):#x}, {status(held)}")
    return out


def confirm_cases(payload, flash=None):
    """The page PATTERN CONFIRM on level 1 of the BLECH menu: ON is the default and writes nothing to the word of the pattern switch,
    the dial changes the word at once, WRITE keeps OFF as bit 2 of the flags (the look word and the other flags stay), the next start
    reads it, EXIT at power-on leaves the word alone."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:confirm_{name}", "ok": bool(ok), "detail": detail})

    status = lambda dev: (state(dev, S_PC), dev.u32(PS_SETTING))

    # defaults: with a card without a file and without a card the word is never written, with a file without the bit it is written ON
    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    bare = boot(payload, flash, adapter=True, card=False)
    plain = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(1, (15, 0, 0)))}, adapter=True)
    add("default_on", status(dev) == (1, 0xFFFFFFFF) and status(bare) == (1, 0xFFFFFFFF) and status(plain) == (1, 1), f"card {status(dev)}, no card {status(bare)}, file without the bit {status(plain)}")

    # the page: the same style as the others, the dial acts at once, a second turn the same way changes nothing
    goto_group(dev, GROUP_FEATURES, FEAT_PC)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(-1, wait=0.3)
    off = texts_of(dev), status(dev)
    dev.turn(-1, wait=0.3)
    still = status(dev)
    dev.turn(1, wait=0.3)
    back = texts_of(dev), status(dev)
    add("page", page == (("PATTERN CONFIRM", "ON", ""), (FEAT_PC, feature_count()), "Feature"), f"{page}")
    add("dial_acts_at_once", off == (("PATTERN CONFIRM", "OFF", ""), (0, 0)) and still == (0, 0) and back == (("PATTERN CONFIRM", "ON", ""), (1, 1)) and not dev.m.asserts, f"{off}, again {still}, back {back}")

    # WRITE keeps OFF in the flags and leaves the look word and the other flags alone
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, led=(15, 7, 0))
    goto_group(keep, GROUP_FEATURES, FEAT_PC)
    keep.turn(-1, wait=0.3)
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    got = files.get("b", (0, 0, 0, None))
    add("file_holds_off", got[:2] == (1, 3 | PC_OFF_BIT) and got[3] == look_word(0, (15, 7, 0), invert=1), f"{files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(keep.m.mmc.card.medium.data))))
    again.run(2.0)
    add("start_reads_off", status(again) == (0, 0) and not again.m.asserts, f"{status(again)}")
    goto_group(again, GROUP_FEATURES, FEAT_PC)
    add("start_shows_off", texts_of(again) == ("PATTERN CONFIRM", "OFF", ""), f"{texts_of(again)}")

    # ON written again clears the bit; a damaged file and a file of version 1 with the bit behave as the format says
    on = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | PC_OFF_BIT, look_word())}, adapter=True)
    goto_group(on, GROUP_FEATURES, FEAT_PC)
    on.turn(1, wait=0.3)
    press(on, "write", wait=0.6)
    kept = read_settings_look(on.m.mmc.card.medium.data)
    newest = max(kept.values(), key=lambda v: v[0])
    add("file_holds_on", status(on) == (1, 1) and newest[:2] == (3, 3), f"{status(on)}, {kept}")
    flawed = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | PC_OFF_BIT, 0, bad_crc=True)}, adapter=True)
    old = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file(3, 3 | PC_OFF_BIT)}, adapter=True)
    add("old_and_damaged_files", status(flawed) == (1, 0xFFFFFFFF) and status(old) == (0, 0), f"damaged {status(flawed)}, version 1 {status(old)}")

    # EXIT at power-on: the menu stays unarmed, the word is never written
    held = boot(payload, flash, held=KILL, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(4, 3 | PC_OFF_BIT, 0)}, adapter=True)
    held.run(0.5)
    add("exit_held_is_stock", state(held, S_ON) != 1 and held.u32(PS_SETTING) == 0xFFFFFFFF and not held.m.asserts, f"on={state(held, S_ON):#x}, word {held.u32(PS_SETTING):#x}")
    return out


def tap_motion_cases(payload, flash=None):
    """The page TAP MOTION on level 1 of the BLECH menu, the same style as PATTERN CONFIRM: ON is the default and writes nothing to the word of the
    TAP motion patch, the dial changes the word at once, WRITE keeps OFF as bit 3 of the flags (the other flags and the look word stay), the
    next start reads it, EXIT at power-on leaves the word alone."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:tap_motion_{name}", "ok": bool(ok), "detail": detail})

    status = lambda dev: (state(dev, S_TM), dev.u32(TM_SETTING))

    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    bare = boot(payload, flash, adapter=True, card=False)
    plain = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(1, (15, 0, 0)))}, adapter=True)
    add("default_on", status(dev) == (1, 0xFFFFFFFF) and status(bare) == (1, 0xFFFFFFFF) and status(plain) == (1, 1), f"card {status(dev)}, no card {status(bare)}, file without the bit {status(plain)}")

    goto_group(dev, GROUP_FEATURES, FEAT_TM)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(-1, wait=0.3)
    off = texts_of(dev), status(dev)
    dev.turn(-1, wait=0.3)
    still = status(dev)
    dev.turn(1, wait=0.3)
    back = texts_of(dev), status(dev)
    add("page", page == (("TAP MOTION", "ON", ""), (FEAT_TM, feature_count()), "Feature"), f"{page}")
    add("dial_acts_at_once", off == (("TAP MOTION", "OFF", ""), (0, 0)) and still == (0, 0) and back == (("TAP MOTION", "ON", ""), (1, 1)) and not dev.m.asserts, f"{off}, again {still}, back {back}")

    # ONCE: one step up from ON, the word is 2, the page says ONCE; WRITE keeps it as bit 5, a start reads it back, bit 3 wins
    dev.turn(1, wait=0.3)
    once = texts_of(dev), status(dev)
    dev.turn(1, wait=0.3)
    capped = status(dev)
    keep_once = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    goto_group(keep_once, GROUP_FEATURES, FEAT_TM)
    keep_once.turn(1, wait=0.3)
    press(keep_once, "write", wait=0.6)
    stored = read_settings_look(keep_once.m.mmc.card.medium.data).get("b", (0, 0, 0, None))
    again_once = Dev(payload, flash, 0)
    again_once.m.adapter = True
    again_once.m.insert_card(SDCard(MemoryMedium(bytearray(keep_once.m.mmc.card.medium.data))))
    again_once.run(2.0)
    both = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | TM_OFF_BIT | TM_ONCE_BIT, look_word())}, adapter=True)
    add("once_value", once == (("TAP MOTION", "ONCE", ""), (2, 2)) and capped == (2, 2) and stored[:2] == (1, 3 | TM_ONCE_BIT)
        and status(again_once) == (2, 2) and status(both) == (0, 0) and not dev.m.asserts, f"{once}, again {capped}, file {stored}, start {status(again_once)}, bit 3 and 5 {status(both)}")
    dev.turn(-1, wait=0.3)
    dev.turn(-1, wait=0.3)
    dev.turn(1, wait=0.3)
    # NOTE ASSIST follows: EDIT next goes there, EDIT previous comes back
    press(dev, "edit_next", wait=0.4)
    nxt = texts_of(dev)[0], counter(dev)
    press(dev, "edit_prev", wait=0.4)
    add("page_before_note_assist", nxt == ("NOTE ASSIST", (FEAT_NA, feature_count())) and texts_of(dev)[0] == "TAP MOTION", f"after EDIT next {nxt}, after EDIT previous {texts_of(dev)}")

    # WRITE keeps OFF in the flags, next to the other bits and the look word
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, led=(15, 7, 0))
    goto_group(keep, GROUP_FEATURES, FEAT_PC)
    keep.turn(-1, wait=0.3)
    goto_group(keep, GROUP_FEATURES, FEAT_TM)
    keep.turn(-1, wait=0.3)
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    got = files.get("b", (0, 0, 0, None))
    add("file_holds_off", got[:2] == (1, 3 | PC_OFF_BIT | TM_OFF_BIT) and got[3] == look_word(0, (15, 7, 0), invert=1), f"{files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(keep.m.mmc.card.medium.data))))
    again.run(2.0)
    add("start_reads_off", status(again) == (0, 0) and not again.m.asserts, f"{status(again)}")
    goto_group(again, GROUP_FEATURES, FEAT_TM)
    add("start_shows_off", texts_of(again) == ("TAP MOTION", "OFF", ""), f"{texts_of(again)}")

    # ON written again clears the bit and leaves the pattern confirmation's bit
    on = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | PC_OFF_BIT | TM_OFF_BIT, look_word())}, adapter=True)
    goto_group(on, GROUP_FEATURES, FEAT_TM)
    on.turn(1, wait=0.3)
    press(on, "write", wait=0.6)
    kept = read_settings_look(on.m.mmc.card.medium.data)
    newest = max(kept.values(), key=lambda v: v[0])
    add("file_holds_on", status(on) == (1, 1) and newest[:2] == (3, 3 | PC_OFF_BIT), f"{status(on)}, {kept}")

    # EXIT at power-on: the menu stays unarmed, the word is never written
    held = boot(payload, flash, held=KILL, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(4, 3 | TM_OFF_BIT, 0)}, adapter=True)
    held.run(0.5)
    add("exit_held_is_stock", state(held, S_ON) != 1 and held.u32(TM_SETTING) == 0xFFFFFFFF and not held.m.asserts, f"on={state(held, S_ON):#x}, word {held.u32(TM_SETTING):#x}")
    return out


def note_assist_menu_cases(payload, flash=None):
    """The page NOTE ASSIST on level 1 of the BLECH menu, the same style as TAP MOTION: ON is the default and writes nothing to the word of the
    note assistant patch, the dial changes the word at once, WRITE keeps OFF as bit 4 of the flags (the other flags and the look word stay),
    the next start reads it, EXIT at power-on leaves the word alone."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:note_assist_{name}", "ok": bool(ok), "detail": detail})

    status = lambda dev: (state(dev, S_NA), dev.u32(NA_SETTING))

    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    bare = boot(payload, flash, adapter=True, card=False)
    plain = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | TM_OFF_BIT, look_word(1, (15, 0, 0)))}, adapter=True)
    add("default_on", status(dev) == (1, 0xFFFFFFFF) and status(bare) == (1, 0xFFFFFFFF) and status(plain) == (1, 1), f"card {status(dev)}, no card {status(bare)}, file without the bit {status(plain)}")

    goto_group(dev, GROUP_FEATURES, FEAT_NA)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(-1, wait=0.3)
    off = texts_of(dev), status(dev)
    dev.turn(-1, wait=0.3)
    still = status(dev)
    dev.turn(1, wait=0.3)
    back = texts_of(dev), status(dev)
    add("page", page == (("NOTE ASSIST", "ON", ""), (FEAT_NA, feature_count()), "Feature"), f"{page}")
    add("dial_acts_at_once", off == (("NOTE ASSIST", "OFF", ""), (0, 0)) and still == (0, 0) and back == (("NOTE ASSIST", "ON", ""), (1, 1)) and not dev.m.asserts, f"{off}, again {still}, back {back}")

    # EDIT next goes to the next page of FEATURES (LAST PATTERN or STEREO 1 PAD where the set has them, else it wraps to the first), EDIT previous comes back
    press(dev, "edit_next", wait=0.4)
    wrapped = texts_of(dev)[0], counter(dev)
    press(dev, "edit_prev", wait=0.4)
    nxt = (FEAT_NA + 1) % feature_count()
    after = (feature_pages()[nxt], (nxt, feature_count()))
    add("page_is_last", wrapped == after and texts_of(dev)[0] == "NOTE ASSIST", f"after EDIT next {wrapped}, after EDIT previous {texts_of(dev)}")

    # WRITE keeps OFF in the flags, next to the other bits and the look word
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, led=(15, 7, 0))
    goto_group(keep, GROUP_FEATURES, FEAT_TM)
    keep.turn(-1, wait=0.3)
    goto_group(keep, GROUP_FEATURES, FEAT_NA)
    keep.turn(-1, wait=0.3)
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    got = files.get("b", (0, 0, 0, None))
    add("file_holds_off", got[:2] == (1, 3 | TM_OFF_BIT | NA_OFF_BIT) and got[3] == look_word(0, (15, 7, 0), invert=1), f"{files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(keep.m.mmc.card.medium.data))))
    again.run(2.0)
    add("start_reads_off", status(again) == (0, 0) and state(again, S_TM) == 0 and not again.m.asserts, f"{status(again)}, TAP MOTION {state(again, S_TM)}")
    goto_group(again, GROUP_FEATURES, FEAT_NA)
    add("start_shows_off", texts_of(again) == ("NOTE ASSIST", "OFF", ""), f"{texts_of(again)}")

    # ON written again clears the bit and leaves the other bits
    on = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3 | PC_OFF_BIT | NA_OFF_BIT, look_word())}, adapter=True)
    goto_group(on, GROUP_FEATURES, FEAT_NA)
    on.turn(1, wait=0.3)
    press(on, "write", wait=0.6)
    kept = read_settings_look(on.m.mmc.card.medium.data)
    newest = max(kept.values(), key=lambda v: v[0])
    add("file_holds_on", status(on) == (1, 1) and newest[:2] == (3, 3 | PC_OFF_BIT), f"{status(on)}, {kept}")

    # EXIT at power-on: the menu stays unarmed, the word is never written
    held = boot(payload, flash, held=KILL, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(4, 3 | NA_OFF_BIT, 0)}, adapter=True)
    held.run(0.5)
    add("exit_held_is_stock", state(held, S_ON) != 1 and held.u32(NA_SETTING) == 0xFFFFFFFF and not held.m.asserts, f"on={state(held, S_ON):#x}, word {held.u32(NA_SETTING):#x}")
    return out

LP_SETTING = 0xC014FEFC               # the word of the patch last-pattern: FFFFFFFF never written, 1 on, 0 off
LP_OFF = 8                            # bit 3 of byte 5 of the settings file: LAST PATTERN is off


def settings_file_v3(generation, flags, look, extras=0):
    """A version 3 settings file without plugin checksums, `extras` its byte 5."""
    head = struct.pack("<IBBHIII", 0x54455347, 3, extras, 0, generation, flags, look)
    return head + struct.pack("<I", zlib.crc32(head) & 0xFFFFFFFF)


def last_pattern_menu_cases(payload, flash=None):
    """The page LAST PATTERN of FEATURES where the set has the patch last-pattern: ON is the default and writes nothing to the
    patch's word, the dial changes the word at once, WRITE keeps OFF as bit 3 of byte 5 of the settings file (next to the meter's bits),
    the next start reads it, EXIT at power-on leaves the word alone."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:last_pattern_{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    if not LAST_PAGE:
        add("no_page_without_patch", "LAST PATTERN" not in feature_pages(), "the set has no last-pattern")
        return out
    word = lambda d: d.u32(LP_SETTING)
    bare = boot(payload, flash, adapter=True, card=False)
    plain = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v3(2, 3, look_word(), extras=1)}, adapter=True)
    add("default_on", word(dev) == 0xFFFFFFFF and word(bare) == 0xFFFFFFFF and word(plain) == 1,
        f"card {word(dev):#x}, no card {word(bare):#x}, file without the bit {word(plain):#x}")

    page_at = feature_pages().index("LAST PATTERN")
    goto_group(dev, GROUP_FEATURES, page_at)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(-1, wait=0.3)
    off = texts_of(dev), word(dev)
    dev.turn(1, wait=0.3)
    back = texts_of(dev), word(dev)
    add("page", page == (("LAST PATTERN", "ON", ""), (page_at, feature_count()), "Feature"), f"{page}")
    add("dial_acts_at_once", off == (("LAST PATTERN", "OFF", ""), 0) and back == (("LAST PATTERN", "ON", ""), 1) and not dev.m.asserts,
        f"{off}, back {back}")

    # WRITE keeps OFF in byte 5 next to METER LOUD RAINBOW, which writes the byte whole
    keep = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v3(2, 3, look_word(), extras=1)}, adapter=True)
    goto_group(keep, GROUP_FEATURES, page_at)
    keep.turn(-1, wait=0.3)
    press(keep, "write", wait=0.6)
    image = keep.m.mmc.card.medium.data
    files = read_settings_look(image)
    extras = settings_extras(image).get("b", 0)
    add("file_holds_off", "b" in files and extras == 1 | LP_OFF, f"byte 5 {extras:#x}, {files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(2.0)
    goto_group(again, GROUP_FEATURES, page_at)
    add("start_reads_off", word(again) == 0 and texts_of(again) == ("LAST PATTERN", "OFF", "") and not again.m.asserts,
        f"{word(again):#x}, {texts_of(again)}")

    # ON written again clears the bit and leaves the meter's
    goto_group(again, GROUP_FEATURES, page_at)
    again.turn(1, wait=0.3)
    press(again, "write", wait=0.6)
    newest = max(read_settings_look(again.m.mmc.card.medium.data).items(), key=lambda kv: kv[1][0])[0]
    extras = settings_extras(again.m.mmc.card.medium.data).get(newest, 0)
    add("file_holds_on", word(again) == 1 and extras == 1, f"{word(again):#x}, byte 5 {extras:#x}")

    # EXIT at power-on: the menu stays unarmed, the word is never written
    held = boot(payload, flash, held=KILL, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v3(4, 3, 0, extras=LP_OFF)}, adapter=True)
    held.run(0.5)
    add("exit_held_is_stock", state(held, S_ON) != 1 and word(held) == 0xFFFFFFFF and not held.m.asserts,
        f"on={state(held, S_ON):#x}, word {word(held):#x}")
    return out


KP_OFF = 16                           # bit 4 of byte 5 of the settings file: KEY PADS is off
FT_OFF = 32                           # bit 5 of byte 5: FILTER TOGGLE is off
AS_OFF = 128                          # bit 7 of byte 5: AUTO SAVE is off


def switch_menu_cases(payload, flash, name, title, slot, bit, from_end):
    """A switch page near the end of FEATURES (KEY PADS, FILTER TOGGLE, AUTO SAVE): ON is the default (no file, a file without the bit), the
    dial switches it at once, WRITE keeps OFF as its bit of byte 5 of the settings file (next to the meter's bits), the next start
    reads it."""
    out = []

    def add(case, ok, detail):
        out.append({"id": f"menu:{name}_{case}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    bare = boot(payload, flash, adapter=True, card=False)
    plain = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v3(2, 3, look_word(), extras=1)}, adapter=True)
    add("default_on", state(dev, slot) == 1 and state(bare, slot) == 1 and state(plain, slot) == 1,
        f"card {state(dev, slot)}, no card {state(bare, slot)}, file without the bit {state(plain, slot)}")

    page_at = feature_pages().index(title)
    goto_group(dev, GROUP_FEATURES, page_at)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(-1, wait=0.3)
    off = texts_of(dev), state(dev, slot)
    dev.turn(1, wait=0.3)
    back = texts_of(dev), state(dev, slot)
    add("page", page == ((title, "ON", ""), (page_at, feature_count()), "Feature") and page_at == feature_count() - from_end, f"{page}")
    add("dial_acts_at_once", off == ((title, "OFF", ""), 0) and back == ((title, "ON", ""), 1) and not dev.m.asserts,
        f"{off}, back {back}")

    # WRITE keeps OFF in byte 5 next to METER LOUD RAINBOW, which writes the byte whole
    keep = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v3(2, 3, look_word(), extras=1)}, adapter=True)
    goto_group(keep, GROUP_FEATURES, page_at)
    keep.turn(-1, wait=0.3)
    press(keep, "write", wait=0.6)
    image = keep.m.mmc.card.medium.data
    files = read_settings_look(image)
    extras = settings_extras(image).get("b", 0)
    add("file_holds_off", "b" in files and extras == 1 | bit, f"byte 5 {extras:#x}, {files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(2.0)
    goto_group(again, GROUP_FEATURES, page_at)
    add("start_reads_off", state(again, slot) == 0 and texts_of(again) == (title, "OFF", "") and not again.m.asserts,
        f"{state(again, slot)}, {texts_of(again)}")

    # ON written again clears the bit and leaves the meter's
    again.turn(1, wait=0.3)
    press(again, "write", wait=0.6)
    newest = max(read_settings_look(again.m.mmc.card.medium.data).items(), key=lambda kv: kv[1][0])[0]
    extras = settings_extras(again.m.mmc.card.medium.data).get(newest, 0)
    add("file_holds_on", state(again, slot) == 1 and extras == 1, f"{state(again, slot)}, byte 5 {extras:#x}")
    return out


def key_pads_menu_cases(payload, flash=None):
    """The page KEY PADS, third to last of FEATURES (bit 4 of byte 5)."""
    return switch_menu_cases(payload, flash, "key_pads", "KEY PADS", S_KP, KP_OFF, 3)


def filter_toggle_menu_cases(payload, flash=None):
    """The page FILTER TOGGLE, second to last of FEATURES (bit 5 of byte 5)."""
    return switch_menu_cases(payload, flash, "filter_toggle", "FILTER TOGGLE", S_FT, FT_OFF, 2)


def knob_leds_cases(payload, flash=None):
    """CUSTOMIZATION, LED, KNOB LEDS (patch pad-colors, wish 12.11.): ON is stock (no file, a file without the bit), OFF sends the five
    knob LEDs 0 to 4 dark at once while the firmware keeps its own values, a knob turned on the main screen lights none of them, ON
    sends them again; WRITE keeps OFF as bit 6 of byte 5 next to the meter's bit 0, the next start has them dark, EXIT held at
    power-on lights them as stock."""
    import pad_colors as PC
    out = []

    def add(case, ok, detail):
        out.append({"id": f"menu:knob_leds_{case}", "ok": bool(ok), "detail": detail})

    wait = 10.0 if synthaddr.is_synth(payload) else 1.2       # the synth reaches its main screen after about 8 s
    knobs = lambda d: [d.m.leds.get(led, 0) for led in range(5)]
    # -> the LED manager (0xC0345A1C, the synth's own place there), + 0x4E + 8 * LED the brightness the firmware wants
    manager = synthaddr.tr(0xC0345A1C) if synthaddr.is_synth(payload) else 0xC0345A1C
    wanted = lambda d: [d.read(d.u32(manager) + 0x4E + 8 * led, 1)[0] for led in range(5)]
    meter_file = {**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v3(2, 3, look_word(), extras=1)}
    dev = boot(payload, flash, files=meter_file, adapter=True, seconds=wait)
    if dev.u32(PC.CODE_AT) == 0xFFFFFFFF:
        return out
    stock = knobs(dev)
    add("default_on", any(stock[1:]) and stock[1:] == wanted(dev)[1:], f"knob LEDs {stock}, the firmware wants {wanted(dev)}")

    goto_group(dev, GROUP_LED, 8)
    page = texts_of(dev), counter(dev)
    dev.turn(-1, wait=0.4)
    off = texts_of(dev), knobs(dev), wanted(dev)
    add("page", page == (("KNOB LEDS", "ON", ""), (8, 9)), f"{page}")
    add("off_at_once", off[0] == ("KNOB LEDS", "OFF", "") and off[1] == [0] * 5 and off[2][1:] == stock[1:] and not dev.m.asserts,
        f"{off[0]}, sent {off[1]}, the firmware still wants {off[2]}")
    leave_to_main(dev)
    dev.m.send([2, 1, 0, 100, 0])
    dev.run(0.05)
    dev.m.send([2, 1, 0, 40, 0])
    dev.run(0.4)
    add("knob_turned_stays_dark", knobs(dev) == [0] * 5 and not dev.m.asserts, f"after PAN turned on the main screen {knobs(dev)}")
    dev.run(1.5)                # the firmware's PAN window closes first, a menu key during it goes to the window
    goto_group(dev, GROUP_LED, 8)
    dev.turn(1, wait=0.4)
    on = texts_of(dev), knobs(dev)
    add("on_again", on[0] == ("KNOB LEDS", "ON", "") and on[1][1:] == stock[1:] and not dev.m.asserts, f"{on}")

    dev.turn(-1, wait=0.4)
    press(dev, "write", wait=0.6)
    image = dev.m.mmc.card.medium.data
    newest = max(read_settings_look(image).items(), key=lambda kv: kv[1][0])[0]
    extras = settings_extras(image).get(newest, 0)
    add("file_holds_off", extras == 1 | 0x40, f"byte 5 {extras:#x}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(wait + 0.8)
    dark = knobs(again)
    goto_group(again, GROUP_LED, 8)
    add("start_reads_off", dark == [0] * 5 and texts_of(again)[1] == "OFF" and not again.m.asserts, f"knob LEDs {dark}, page {texts_of(again)}")
    held = Dev(payload, flash, KILL)
    held.m.adapter = True
    held.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    held.run(wait + 0.8)
    add("exit_held_is_stock", knobs(held)[1:] == stock[1:] and not held.m.asserts, f"knob LEDs {knobs(held)}")
    again.turn(1, wait=0.4)
    press(again, "write", wait=0.6)
    newest = max(read_settings_look(again.m.mmc.card.medium.data).items(), key=lambda kv: kv[1][0])[0]
    extras = settings_extras(again.m.mmc.card.medium.data).get(newest, 0)
    add("file_holds_on", extras == 1 and knobs(again)[1:] == stock[1:], f"byte 5 {extras:#x}, knob LEDs {knobs(again)}")
    return out


GLOBAL_PAGE_OBJECT = 0xC0691240       # -> the object of GLOBAL PARAMETERS; SET_GLOBAL_PAGE(object, page) sets the page screen 9 opens on
SET_GLOBAL_PAGE = 0xC007B084
CHAIN_MODE_PAGE, CHAIN_MODE_BYTE = 18, 0x1F   # page 19/20 of GLOBAL PARAMETERS and its byte in the Global values (docs/messungen/2026-10-13)
GLOBAL_LIVE = 0xC033E6A0              # -> the Global object, its 0x100 bytes of values at +4
GLOBAL_FLASH = 0x230000               # the flash sector the firmware saves them to


def global_values(dev):
    return dev.read(dev.u32(GLOBAL_LIVE) + 4, 0x100)


def count_erases(dev):
    """Counts the sector erases of the flash from now on, in dev.erases."""
    dev.erases = []
    flash = dev.m.flash
    erase = flash.erase

    def counted(size, _erase=erase):
        dev.erases.append(flash.addr & ~(size - 1))
        _erase(size)
    flash.erase = counted


def leave_to_main(dev):
    """EXIT until the main screen (GLOBAL PARAMETERS: 9, 8, 1; BLECH: up through its levels, then 1)."""
    for _ in range(5):
        if dev.m.screen() == 1:
            break
        press(dev, "exit", wait=0.4)
    dev.run(0.5)


def auto_save_cases(payload, flash=None):
    """AUTO SAVE (issue 391): leaving GLOBAL PARAMETERS with a changed value saves the Globals as WRITE there does (one erase of
    the sector at 0x230000), leaving BLECH with a changed setting writes the settings file as WRITE there does; no change writes
    nothing, WRITE and then EXIT save once, and with the page OFF leaving saves nothing (stock). A start that only reads the flash
    and the card (no switch-off, as a cut of the power) shows what was saved."""
    out = switch_menu_cases(payload, flash, "auto_save", "AUTO SAVE", S_AS, AS_OFF, 1)

    def add(case, ok, detail):
        out.append({"id": f"menu:auto_save_{case}", "ok": bool(ok), "detail": detail})

    import last_pattern_cases
    first = boot(payload, flash, files=CARD_FOLDER)
    kept = last_pattern_cases.switch_off(first)  # a flash whose Global sector holds the values of this start
    if kept is None:
        add("switch_off", False, "the device did not switch off")
        return out
    card = bytearray(first.m.mmc.card.medium.data)

    def start(flash_image, card_image):
        dev = Dev(payload, flash_image, 0)
        dev.m.insert_card(SDCard(MemoryMedium(bytearray(card_image))))
        dev.run(1.5)
        count_erases(dev)
        return dev

    def global_page(dev):
        go(dev, 9)
        dev.call(SET_GLOBAL_PAGE, dev.u32(GLOBAL_PAGE_OBJECT), CHAIN_MODE_PAGE)
        go(dev, 9)

    dev = start(kept, card)
    global_page(dev)
    leave_to_main(dev)
    add("global_unchanged_no_write", dev.erases == [] and not dev.m.asserts, f"erases {dev.erases}")

    global_page(dev)
    was = global_values(dev)[CHAIN_MODE_BYTE]
    dev.turn(1, wait=0.4)
    now = global_values(dev)[CHAIN_MODE_BYTE]
    leave_to_main(dev)
    saved = dev.erases == [GLOBAL_FLASH]
    again = start(bytes(dev.m.flash.mem), dev.m.mmc.card.medium.data)
    add("global_saved_on_leave", was != now and saved and global_values(again)[CHAIN_MODE_BYTE] == now and not dev.m.asserts,
        f"CHAIN MODE {was} -> {now}, erases on leaving {dev.erases}, after a start without switch-off {global_values(again)[CHAIN_MODE_BYTE]}")

    global_page(again)
    again.turn(-1, wait=0.4)
    press(again, "write", wait=1.5)
    leave_to_main(again)
    add("write_then_exit_saves_once", again.erases == [GLOBAL_FLASH], f"erases {again.erases}")

    dev = start(kept, card)
    before = bytes(dev.m.mmc.card.medium.data)
    goto_group(dev, GROUP_DISPLAY, 4)
    leave_to_main(dev)
    add("blech_unchanged_no_write", bytes(dev.m.mmc.card.medium.data) == before and dev.erases == [], f"erases {dev.erases}")

    goto_group(dev, GROUP_DISPLAY, 4)
    inverted = state(dev, S_INVERT)
    dev.turn(-1 if inverted else 1, wait=0.4)
    now = state(dev, S_INVERT)
    leave_to_main(dev)
    files = read_settings_look(dev.m.mmc.card.medium.data)
    newest = max(files.items(), key=lambda kv: kv[1][0])[1] if files else None
    again = start(bytes(dev.m.flash.mem), dev.m.mmc.card.medium.data)
    add("blech_saved_on_leave", now != inverted and newest is not None and (newest[3] >> 28 & 1) == now and state(again, S_INVERT) == now
        and not dev.m.asserts, f"DISPLAY INVERT {inverted} -> {now}, the newest file's look {newest and hex(newest[3])}, after a start without switch-off {state(again, S_INVERT)}")

    # AUTO SAVE OFF, kept with WRITE: leaving saves neither the Globals nor the settings
    page_at = feature_pages().index("AUTO SAVE")
    goto_group(again, GROUP_FEATURES, page_at)
    again.turn(-1, wait=0.3)
    press(again, "write", wait=0.6)
    off = start(bytes(again.m.flash.mem), again.m.mmc.card.medium.data)
    before = bytes(off.m.mmc.card.medium.data)
    global_page(off)
    off.turn(1, wait=0.4)
    leave_to_main(off)
    goto_group(off, GROUP_DISPLAY, 4)
    off.turn(1 if state(off, S_INVERT) == 0 else -1, wait=0.4)
    leave_to_main(off)
    add("off_is_stock", state(off, S_AS) == 0 and off.erases == [] and bytes(off.m.mmc.card.medium.data) == before and not off.m.asserts,
        f"AUTO SAVE {state(off, S_AS)}, erases {off.erases}, card {'changed' if bytes(off.m.mmc.card.medium.data) != before else 'unchanged'}")
    return out


EARLY_SITE = 0xC0038D34               # the first instruction of the command that loads e2sSample.all: the early hook of the menu
SAMPLE_LOADER = 0xC00364F0            # the sample loader itself, called from that command


def early_card(payload, files):
    """A card with a sample file (so the loader runs for a good second) and the given files."""
    import cardstore
    import sampleset
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    if not synthaddr.is_synth(payload):
        volume.write(f"KORG/{cardstore.card_folder(payload)}/Sample/e2sSample.all", sampleset.build(sampleset.sized(20, 4 * 48000)))
    for path, data in files.items():
        volume.write(path, data)
    volume.close()
    return SDCard(MemoryMedium(bytearray(image)))


def early_run(payload, flash, files, held=0):
    """Boots with a sample file on the card and notes, at the moment the sample loader starts, the look words of the menu, the backlight
    pins and the screen, and the device time of the loader's start and of the main screen. Returns a dict."""
    import unicorn
    dev = Dev(payload, flash, held)
    m = dev.m
    m.adapter = True
    m.insert_card(early_card(payload, files))
    seen = {}

    def at_loader(uc, address, size, user):
        if "loader_ms" not in seen:
            seen.update(loader_ms=m.time_ns / 1e6, on=state(dev, S_ON), led_eff=state(dev, S_LED_EFF), bl_on=state(dev, S_BL_ON), bl_pwm=state(dev, S_BL_PWM),
                        led_v=dev.read(STATE + S_LED_V, 3), pins=pins(dev), screen=dev.screen()["number"])
    m.uc.hook_add(unicorn.UC_HOOK_CODE, at_loader, begin=SAMPLE_LOADER, end=SAMPLE_LOADER)
    m.uc.ctl_flush_tb()
    while m.time_ns / 1e9 < 3.0 and not m.asserts:
        m.run_until(m.time_ns / 1e9 + 0.002)
        if dev.screen()["number"] == 1 and "main_ms" not in seen:
            seen["main_ms"] = m.time_ns / 1e6
            break
    seen["asserts"] = list(m.asserts)
    return seen


def default_level_cases(payload, flash=None):
    """The colour pages show STOCK for a state in which nothing is set (the device is at full light then): no file, or a file whose look word has
    zeros, shows that and acts as the firmware does; a file with values shows them as hue, saturation and brightness; the dial turns down from
    full brightness and zero stored is that state again."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:look_default_{name}", "ok": bool(ok), "detail": detail})

    levels = lambda dev: [(text(dev, S_TITLE), text(dev, S_VALUE)) for page in range(PAGE_LED_R, PAGE_BL_B + 1) if goto_page(dev, page) is None]
    fresh = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    zero = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(0))}, adapter=True)
    mixed = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(0, (0, 0, 5), (0, 7, 0)))}, adapter=True)
    want_stock = [(title, "STOCK") for title in ("LED HUE", "LED SAT", "LED BRIGHT", "BACKLIGHT HUE", "BACKLIGHT SAT", "BACKLIGHT BRIGHT")]
    add("no_file_shows_15", levels(fresh) == want_stock, f"{levels(fresh)}")
    add("zero_word_shows_15_and_acts_as_before", levels(zero) == want_stock and state(zero, S_LED_EFF) == 0 and state(zero, S_BL_ON) == 0x38 and state(zero, S_BL_PWM) == 0,
        f"{levels(zero)}, LED kind {state(zero, S_LED_EFF)}, light pins {state(zero, S_BL_ON):#x}")
    add("file_with_values_reads_as_before", levels(mixed) == [("LED HUE", "64"), ("LED SAT", "15"), ("LED BRIGHT", "5"), ("BACKLIGHT HUE", "32"), ("BACKLIGHT SAT", "15"), ("BACKLIGHT BRIGHT", "7")]
        and state(mixed, S_LED_EFF) == 1, f"{levels(mixed)}, LED kind {state(mixed, S_LED_EFF)}")

    # the dial: up on the brightness from the state changes nothing, down starts at 15 each, zero stored is the state again
    goto_page(fresh, PAGE_LED_B)
    fresh.turn(3, wait=0.3)
    up = [state(fresh, S_LED_R + 4 * k) for k in range(3)]
    fresh.turn(-1, wait=0.3)
    down = [state(fresh, S_LED_R + 4 * k) for k in range(3)], texts_of(fresh)[:2]
    set_look(fresh, led=(0, 0, 0))
    goto_page(fresh, PAGE_LED_B)
    back = [state(fresh, S_LED_R + 4 * k) for k in range(3)], texts_of(fresh)[:2], state(fresh, S_LED_EFF)
    add("dial_from_the_default", up == [0, 0, 0] and down == ([14, 0, 0], ("LED BRIGHT", "14")) and back == ([0, 0, 0], ("LED BRIGHT", "STOCK"), 0), f"up {up}, down {down}, back {back}")
    return out


def card_later_cases(payload, flash=None):
    """A card put in after the start, and another card for the one pulled (menu_card_watch in tools/patch/script_menu.s): the
    whole settings file is read as at the start, CUSTOMIZATION included (backlight, bottom LEDs, display polarity, pad colours),
    and every switch with it. Each step is compared with a device that started with that card. What the power-on runs with
    stays (the plugin runtime and MFX 2), a card without a settings file changes nothing, nothing is written to the card."""
    import pad_colors as PC
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:card_later_{name}", "ok": bool(ok), "detail": detail})

    wait = 10.0 if synthaddr.is_synth(payload) else 1.2
    pad = lambda d: (d.m.leds.get(0x2C, 0), d.m.leds.get(0x2D, 0))

    def look(d):
        return {"led": (state(d, S_LED_EFF), state(d, S_LED_V)), "light": (state(d, S_BL_ON), state(d, S_BL_PWM), pins(d)),
                "leds": steady_leds(d), "invert": (state(d, S_INVERT), d.m.lcd_reverse), "pads": (d.u32(PC.PC_SETTING), pad(d)),
                "switches": (state(d, S_SET_RUN), state(d, S_SET_MFX), state(d, S_PC), state(d, S_TM), state(d, S_NA), state(d, S_KP),
                             state(d, S_FT), state(d, S_AS))}

    # scripts off, MFX 2 on, TAP MOTION and NOTE ASSIST off; LED COLOR orange, a blue backlight, DISPLAY INVERT OFF, pads PINK
    first = settings_file_v2(4, 0x2 | 0x8 | 0x10, look_word(1, (15, 7, 0), (0, 0, 15), 0) | PC.PINK << 2 | 1 << 29)
    # scripts on, PATTERN CONFIRM off; bottom LEDs OFF, a red backlight, DISPLAY INVERT ON, pads BLUE
    second = settings_file_v2(9, 0x1 | 0x4, look_word(2, (0, 0, 0), (15, 0, 0), 1) | PC.BLUE << 2)
    files_a = {**CARD_FOLDER, SETTINGS_PATHS[0]: first}
    files_b = {**CARD_FOLDER, SETTINGS_PATHS[0]: second}
    ref_a = look(boot(payload, flash, files=files_a, adapter=True, seconds=wait))
    ref_b = look(boot(payload, flash, files=files_b, adapter=True, seconds=wait))

    dev = boot(payload, flash, adapter=True, card=False, seconds=wait)
    bare = look(dev)
    eff = state(dev, S_EFF_RUN), state(dev, S_EFF_MFX)
    card_a = SDCard(MemoryMedium(card_image(files_a)))
    untouched = bytes(card_a.medium.data)
    dev.m.insert_card(card_a)
    dev.run(1.0)
    got_a = look(dev)
    kept = state(dev, S_EFF_RUN), state(dev, S_EFF_MFX)
    add("reads_the_whole_file", bare != ref_a and got_a == ref_a and not dev.m.asserts, f"without card {bare}; card put in {got_a}; started with it {ref_a}")
    add("runtime_stays", kept == eff, f"plugin runtime and MFX 2 in effect before {eff}, after {kept}")
    add("card_not_written", bytes(dev.m.mmc.card.medium.data) == untouched, "the card was " + ("not written" if bytes(dev.m.mmc.card.medium.data) == untouched else "written"))

    dev.m.eject_card()
    dev.run(0.5)
    pulled = look(dev)
    dev.m.insert_card(SDCard(MemoryMedium(card_image(files_b))))
    dev.run(1.0)
    got_b = look(dev)
    add("swap_reads_the_other_card", pulled == ref_a and got_b == ref_b and not dev.m.asserts, f"pulled {pulled}; other card {got_b}; started with it {ref_b}")

    blank = boot(payload, flash, adapter=True, card=False, seconds=wait)
    before = look(blank)
    blank.m.insert_card(SDCard(MemoryMedium(card_image(CARD_FOLDER))))
    blank.run(1.0)
    after = look(blank)
    add("card_without_file_keeps", before == after and not blank.m.asserts, f"before {before}, after {after}")

    started = boot(payload, flash, files=files_a, adapter=True, seconds=wait)
    gen = state(started, S_GEN)
    started.m.uc.mem_write(STATE + S_LED_R, struct.pack("<I", 3))
    started.run(1.0)
    add("card_at_start_read_once", gen == 4 and state(started, S_LED_R) == 3 and not started.m.asserts, f"generation {gen}, a level set after the start {state(started, S_LED_R)}")
    return out


def early_look_cases(payload, flash=None):
    """The look (backlight colour, bottom LED colour) is set by the time the sample loader starts, not only after it ends: the menu arms and
    reads its settings from a hook on the loading command, before the loader. Compared with the same copy without that hook (the
    instruction put back), which arms behind the loader, and with the main screen's time, which must not get later."""
    if synthaddr.is_synth(payload):
        return synth_start_cases(payload, flash) + boot_light_cases(payload, flash)
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:early_look_{name}", "ok": bool(ok), "detail": detail})

    files = {**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(1, (15, 7, 0), (5, 0, 0)))}
    late_payload = bytearray(payload)
    struct.pack_into("<I", late_payload, EARLY_SITE - IMAGE, 0xE3A03000)          # mov r3, #0, the instruction the hook replaced
    early = early_run(payload, flash, files)
    late = early_run(bytes(late_payload), flash, files)
    add("armed_before_the_loader", early.get("on") == 1 and early.get("screen") != 1 and late.get("on") != 1, f"at the loader's start: early copy armed {early.get('on')}, copy without the hook {late.get('on')}")
    add("look_applied_before_the_loader", early.get("led_eff") == 2 and tuple(early.get("led_v", b"")) == (255, 119, 0) and early.get("bl_pwm") == 1 and early.get("bl_on") == 0x08
        and early.get("pins", 0) & 0x38 in (0, 0x08) and late.get("led_eff") != 2, f"LED kind {early.get('led_eff')}, colour {tuple(early.get('led_v', b''))}, light pins {early.get('bl_on')}, PWM {early.get('bl_pwm')}; without the hook {late.get('led_eff')}")
    # The loader waits for the early hook (menu_arm_load and migrate_start read the card): 10.2 ms at GELUMPE_PACE=flat, 17.2 ms at the
    # device pace (measured 2026-11-10 from the hook's entry to its return; the loader then starts 4 to 5 ms later in both copies). 25 ms holds that with room for the emulator's noise. The main screen below gets the same 25 ms: the hook's 17.2 ms can reach it in full (a copy
    # without the hook was 17.2 ms earlier on the main screen after the dead card change, 5.6 ms before it, the hooked copy the same both times).
    add("loader_starts_at_the_same_time", abs(early["loader_ms"] - late["loader_ms"]) < 25, f"loader {early['loader_ms']:.1f} ms with the hook, {late['loader_ms']:.1f} ms without (the settings are read first now, not afterwards)")
    add("main_screen_not_later", early["main_ms"] <= late["main_ms"] + 25 and not early["asserts"], f"main screen at {early['main_ms']:.1f} ms with the hook, {late['main_ms']:.1f} ms without")
    held = early_run(payload, flash, files, held=KILL)
    add("exit_held_stays_stock", held.get("on") != 1 and held.get("pins") == GPIO_PINS and not held["asserts"], f"armed {held.get('on'):#x}, light pins {held.get('pins'):#x}")
    return out + boot_light_cases(payload, flash)


BOOT_LIGHT_SITE = 0xC00289D8          # behind the firmware's first flash read in the start: the hook that sets the colour at power-on
BOOT_LIGHT_SYNTH = 0xC0025E48         # the same place on the blue (`cmp r0, r3`)
BOOT_SLOT = 250                       # *GLOBALS + 250, Global byte 250 (byte 246 of the block in the flash): 0x80 plus the pins of the colour
BOOT_FLASH = 0x2300F6                 # that byte in the flash
DRAW_IMAGE = 0xC003F650               # the firmware's picture function; its first call in the start draws the start image


def boot_light_run(payload, flash, files, held=0):
    """Boots on mains power and notes every change of the backlight pins and the time of the first picture (the start image).
    Returns (dev, pin changes [(ms, pins)], ms of the start image, pins at that moment). dev.image_shown is (first, last ms) the
    display shows a full picture (more than 2000 pixels lit) in the first 0.5 s, in 2 ms steps: the start image."""
    import unicorn
    draw = synthaddr.tr(DRAW_IMAGE) if synthaddr.is_synth(payload) else DRAW_IMAGE
    dev = Dev(payload, flash, held)
    dev.m.adapter = True
    dev.m.insert_card(SDCard(MemoryMedium(card_image(files))))
    watch_pins(dev)
    seen = {}

    def at_draw(uc, address, size, user):
        if "ms" not in seen:
            seen.update(ms=dev.m.time_ns / 1e6, pins=pins(dev))
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, at_draw, begin=draw, end=draw)
    dev.m.uc.ctl_flush_tb()
    shown = []
    for step in range(1, 251):
        dev.m.run_until(step * 0.002)
        if sum(bin(b).count("1") for row in dev.m.fb for b in row) > 2000:
            shown.append(step * 2)
        elif shown:
            break
    dev.image_shown = (shown[0], shown[-1]) if shown else None
    dev.m.run_until(1.2)
    return dev, [(round(t / 1e6, 2), v) for t, v in dev.pin_log], seen.get("ms"), seen.get("pins")


def after_white(changes):
    """The pin changes behind the first time all three pins were on."""
    first = next((i for i, (_, v) in enumerate(changes) if v == GPIO_PINS), len(changes))
    return changes[first + 1:]


def boot_light_cases(payload, flash=None):
    """The backlight colour at power-on: the colour the settings file holds goes into Global byte 250 when the menu reads it, the
    firmware saves the Globals at switch-off, and the next start sets the pins of that colour before the start image is drawn, then
    keeps them through the firmware's own light calls until the menu is armed. EXIT at power-on stays stock white, a card without a
    settings file goes back to white once the menu is armed, WRITE of another colour updates the byte."""
    import last_pattern_cases
    synth = synthaddr.is_synth(payload)
    site, word = (BOOT_LIGHT_SYNTH, 0xE1500003) if synth else (BOOT_LIGHT_SITE, 0xE3500F49)
    if struct.unpack_from("<I", payload, site - IMAGE)[0] == word:
        return []
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:boot_light_{name}", "ok": bool(ok), "detail": detail})

    red = {**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(0, (0, 0, 0), (15, 0, 0)))}
    dev = boot(payload, flash, files=red)
    globals_at = dev.u32(synthaddr.tr(POWER_SAVE_OBJECT) if synth else POWER_SAVE_OBJECT)
    slot = dev.read(globals_at + BOOT_SLOT, 1)[0] if globals_at else None
    kept = last_pattern_cases.switch_off(dev)
    add("kept_at_switch_off", slot == 0x88 and kept is not None and kept[BOOT_FLASH] == 0x88,
        f"Global byte 250 after the settings {slot}, in the flash after switch-off {kept[BOOT_FLASH] if kept else 'no switch-off'}")
    if kept is None:
        return out
    dev, changes, image_ms, image_pins = boot_light_run(payload, kept, red)
    white = after_white(changes)                # the firmware lights red, green, blue one after the other at about 52 ms
    first_red = next((t for t, v in white if v == 0x08), None)
    if synth:                                   # the blue draws its start image before the flash answers: the colour comes while it is shown
        shown = dev.image_shown
        add("colour_while_the_start_image", shown is not None and first_red is not None and shown[0] <= first_red < shown[1],
            f"red from {first_red} ms, start image drawn at {image_ms} ms, on the display from {shown and shown[0]} to {shown and shown[1]} ms, changes {changes[:6]}")
    else:
        add("colour_before_the_start_image", image_ms is not None and image_pins == 0x08 and first_red is not None and first_red < image_ms,
            f"red from {first_red} ms, start image at {image_ms} ms with pins {image_pins}, changes {changes[:6]}")
    add("colour_until_armed", first_red is not None and all(v == 0x08 for t, v in white if t >= first_red) and pins(dev) == 0x08 and state(dev, S_ON) == 1
        and not dev.m.asserts, f"pin changes after the white {white[:6]}, pins now {pins(dev):#x}")
    held, changes, image_ms, image_pins = boot_light_run(payload, kept, red, held=KILL)
    add("exit_held_stays_white", image_pins == GPIO_PINS and after_white(changes) == [] and pins(held) == GPIO_PINS and state(held, S_ON) != 1,
        f"start image pins {image_pins}, changes {changes[:6]}, pins now {pins(held):#x}")
    bare, changes, image_ms, image_pins = boot_light_run(payload, kept, CARD_FOLDER)
    lit = (0x08 in [v for _, v in after_white(changes)]) if synth else image_pins == 0x08
    add("no_settings_file_back_to_white", lit and pins(bare) == GPIO_PINS and state(bare, S_ON) == 1,
        f"start image pins {image_pins}, changes after the white {after_white(changes)[:4]}, pins once armed {pins(bare):#x}")
    dev = boot(payload, kept, files=red, adapter=True)
    set_look(dev, backlight=(0, 15, 0))
    before = dev.read(globals_at + BOOT_SLOT, 1)[0]
    press(dev, "write", wait=0.6)
    after = dev.read(globals_at + BOOT_SLOT, 1)[0]
    add("write_updates_the_byte", before == 0x88 and after == 0x90 and state(dev, S_STATUS) == 1,
        f"Global byte 250 after the change {before:#x}, after WRITE {after:#x}, status {state(dev, S_STATUS)}")
    # Device report 30.10.: HUE 15, SAT 13, BRIGHT 14 (stored 14, 13, 2) and DISPLAY INVERT on kept the start white, because all three
    # levels are above 0. The start only has on and off per channel: a channel stays on when it is at least half of the strongest.
    set_look(dev, backlight=(0, 0, 0))
    goto_page(dev, PAGE_BL_R)
    dev.turn(15, wait=0.25)
    goto_page(dev, PAGE_BL_G)
    dev.turn(-2, wait=0.25)
    goto_page(dev, PAGE_BL_B)
    dev.turn(-1, wait=0.25)
    levels = [state(dev, S_BL_R + 4 * k) for k in range(3)]
    press(dev, "write", wait=0.6)
    after = dev.read(globals_at + BOOT_SLOT, 1)[0]
    add("hsv_15_13_14_byte", levels == [14, 13, 2] and after == 0x98 and state(dev, S_BL_ON) == 0x38 and state(dev, S_STATUS) == 1,
        f"HUE 15, SAT 13, BRIGHT 14 stores {levels}, Global byte 250 after WRITE {after:#x} (red and green), pins of the menu {state(dev, S_BL_ON):#x}")
    rule = []
    for colour, want in (((15, 7, 0), 0x88), ((15, 8, 0), 0x98), ((8, 8, 8), 0xB8), ((0, 0, 1), 0xA0), ((15, 1, 14), 0xA8), ((1, 15, 1), 0x90)):
        set_look(dev, backlight=colour)
        press(dev, "write", wait=0.6)
        rule.append((colour, dev.read(globals_at + BOOT_SLOT, 1)[0], want))
    add("pins_follow_the_strongest", all(got == want for _, got, want in rule), f"colour, byte, wanted: {[(c, hex(g), hex(w)) for c, g, w in rule]}")
    his = {**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(0, (0, 0, 0), (14, 13, 2), invert=1))}
    mine = boot(payload, kept, files=his)
    kept_his = last_pattern_cases.switch_off(mine)
    if kept_his is None:
        add("his_colour_starts_yellow", False, "no switch-off")
        return out
    mine, changes, image_ms, image_pins = boot_light_run(payload, kept_his, his)
    lit = [v for t, v in after_white(changes) if v]
    first = image_pins if not synth else (lit[0] if lit else None)
    add("his_colour_starts_yellow", kept_his[BOOT_FLASH] == 0x98 and first == 0x18,
        f"flash byte {kept_his[BOOT_FLASH]:#x} after the settings 14, 13, 2 with INVERT on, start image pins {image_pins}, first lit pins {first}, changes {changes[:6]}")
    # Device 30.10.: the flash still holds 0xB8 from the build before the pin rule. The first start is white (the card cannot be read
    # before the start image), the menu then rewrites the byte, the next switch-off saves it and the start after that is yellow.
    old = bytearray(kept_his)
    old[BOOT_FLASH] = 0xB8
    stale, changes, image_ms, first_pins = boot_light_run(payload, bytes(old), his)
    stale_lit = [v for t, v in after_white(changes) if v]
    stale_first = first_pins if not synth else (stale_lit[0] if stale_lit else None)
    again = boot(payload, bytes(old), files=his)
    healed = last_pattern_cases.switch_off(again)
    byte_now = healed[BOOT_FLASH] if healed else None
    # the blue reads its first lit pins only after the white phase (see first above), so only the Sampler builds show the stale white
    add("old_byte_heals_after_one_switch_off", (synth or stale_first == 0x38) and byte_now == 0x98,
        f"flash byte 0xb8 starts with pins {stale_first}, after one switch-off the flash holds {byte_now}")
    return out


def synth_start_cases(payload, flash=None):
    """Settings and startup ordering at the native Synth user-data continuation."""
    import unicorn
    files = {**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(1, (15, 7, 0), (5, 0, 0)))}
    observed = []
    for held in (0, KILL):
        dev = Dev(payload, flash, held)
        dev.m.adapter = True
        dev.m.insert_card(early_card(payload, files))
        seen = {}

        def record(uc, address, size, user):
            seen[user] = dict(on=state(dev, S_ON), led=state(dev, S_LED_EFF),
                colour=tuple(dev.read(STATE + S_LED_V, 3)), pwm=state(dev, S_BL_PWM),
                screen=dev.m.screen(), ms=round(dev.m.time_ns / 1e6, 3))

        for address, label in ((0xC0028170, 'before'), (0xC0028174, 'native')):
            dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, record, user_data=label, begin=address, end=address)
        dev.run(1.2)
        observed.append((dev, seen))
    dev, normal = observed[0]
    killed, bypass = observed[1]
    before, native = normal.get('before', {}), normal.get('native', {})
    return [
        dict(id='menu:synth_start_after_user_data', ok=before.get('on') != 1 and native.get('on') == 1,
             detail=normal),
        dict(id='menu:synth_start_settings', ok=native.get('led') == 2 and native.get('colour') == (255,119,0) and native.get('pwm') == 1,
             detail=native),
        dict(id='menu:synth_start_before_main', ok=native.get('screen') != 1 and dev.m.screen() == 1,
             detail=dict(at_hook=native.get('screen'), final=dev.m.screen())),
        dict(id='menu:synth_start_exit', ok=bypass.get('native', {}).get('on') != 1 and state(killed, S_ON) != 1 and killed.m.screen() == 1,
             detail=bypass),
        dict(id='menu:synth_start_native_once', ok=all(not d.m.asserts and len(d.m.dsp_uploads) == 1 for d, _ in observed),
             detail=[dict(asserts=d.m.asserts, dsp_uploads=len(d.m.dsp_uploads)) for d, _ in observed]),
    ]


def look_rest():
    """The suites look_cases runs after its own cases, in that order."""
    return (invert_cases, confirm_cases, tap_motion_cases, note_assist_menu_cases, last_pattern_menu_cases, key_pads_menu_cases, filter_toggle_menu_cases, knob_leds_cases, auto_save_cases, default_level_cases, early_look_cases, card_later_cases)


def look_parts():
    """What look_cases_task(i) runs: the look cases themselves, the suites after them, then the splash, pad colour and
    calibration cases. Each boots devices of its own, so they run side by side."""
    from calibrate_cases import cases as calibration_cases
    return ((lambda payload, flash: look_cases(payload, flash, rest=False)), *look_rest(), splash_menu_cases, wheel_cases,
            pad_colour_cases, calibration_cases)


LOOK_PARTS = 1 + len(look_rest()) + 4      # look_parts() without importing calibrate_cases


def look_cases_task(i):
    """Part `i` of the look cases in a worker (parallel.py, look_parts)."""
    import parallel
    return look_parts()[i](parallel.shared["payload"], parallel.shared["flash"])


def settings_cases_task():
    """The settings cases in a worker (parallel.py)."""
    import parallel
    return settings_cases(parallel.shared["payload"], parallel.shared["flash"])


def main():
    import lifetime
    lifetime.load_gate()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["cases"])
    parser.add_argument("--base", required=True)
    parser.add_argument("--patched", required=True)
    parser.add_argument("--flash", nargs="*")
    args = parser.parse_args()
    payload = Path(args.patched).read_bytes()[HEADER:]
    flash = load_flash(args.flash) if args.flash else None
    # The same tasks as in check.py (without the calibration), side by side and kept as there (taskcache.py)
    import parallel
    tasks = [("menu_cases", "cases_task", (i,)) for i in range(len(CASES_PARTS))] + [("menu_cases", "settings_cases_task", ())]
    tasks += [("menu_cases", "look_cases_task", (i,)) for i in range(LOOK_PARTS - 1)]
    data = {"payload": payload, "flash": flash, "base": Path(args.base).read_bytes()[HEADER:]}
    result = [c for part in parallel.run_tasks(tasks, data, cache="check") for c in part]
    print(json.dumps(result, indent=1))
    return 0 if all(c["ok"] for c in result) else 1


if __name__ == "__main__":
    sys.exit(main())
