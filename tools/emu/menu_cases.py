"""Emulator checks for the BLECH menu screen (tools/patch/script_menu.s).

check.py runs `menu_cases` on every patched copy that carries the menu: the
screen sits in the Edit ring between Global and Data Util, the page counter
stays gap-free, WRITE opens no pattern window, EXIT returns to the main screen,
and with EXIT held at power-on the firmware's ring is the stock one.

    tools/emu/.venv/bin/python tools/emu/menu_cases.py cases --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin]
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.patch import script_hooks  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
import fat32  # noqa: E402
import synthaddr  # noqa: E402
from splash_cases import Dev, SWITCH_SCREEN  # noqa: E402
from unicorn import arm_const  # noqa: E402

HEADER = 0x100
IMAGE = 0xC0000000
MENU = 0x2D
STATE = script_hooks.MENU_STATE
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
    global MENU, RING, BASE_RING
    synth = synthaddr.is_synth(payload)
    MENU = 37 if synth else 45
    BASE_RING = 28 if synth else 29
    RING = BASE_RING + 2


def card_image(files=None):
    img = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(img)
    for path, data in (files or {}).items():
        volume.write(path, data)
    volume.close()
    return img


def boot(payload, flash=None, held=0, files=None, adapter=False, card=True, seconds=1.2):
    """A device booted to the main screen; with `adapter` on mains power (the bottom LEDs and the backlight show their normal state)."""
    for_build(payload)
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


GROUP_PLUGINS, GROUP_GAMES, GROUP_TOOLS, GROUP_CUSTOM, GROUP_FEATURES, GROUP_COLORS = range(6)
CUSTOM_COLORS, CUSTOM_PAD = 1, 3                                       # the row COLORS in CUSTOMIZATION, and PAD COLOR (SELECT COLOR, SPLASH IMPORT and DRAW follow)
S_LEVEL, S_GROUP, S_RAW, S_TOP, S_TABW = 0xE0, 0xE4, 0xE8, 0xEC, 0xF0
TAB_TEXT_POINTER = 0x38                                               # the tab widget keeps a pointer to its text at this offset
LIST_PAGES = ["FEATURES", "CUSTOMIZATION", "PLUGINS"]                 # the groups of level 1 of a menu without apps, in this order; GAMES and TOOLS follow when an app is declared in them
LIST_GROUPS = LIST_PAGES
LIST_FEATURES, LIST_CUSTOM, LIST_PLUGINS = range(3)                   # their places in that list
FEATURE_PAGES = ["MFX 2", "PATTERN CONFIRM", "TAP MOTION", "NOTE ASSIST"]   # the pages of the group FEATURES, each with an ON/OFF value
FEAT_MFX, FEAT_PC, FEAT_TM, FEAT_NA = range(len(FEATURE_PAGES))
TAB_LABELS = ["BLECH", "Plugins", "Games", "Tools", "Custom", "Feature", "Colors"]
RING = 31                                                             # the total of the page counter with the page BLECH and the page of Blechy in the ring
BASE_RING = 29
LEVEL_BLECHY = 3                                                      # level 3 of the screen: the page of Blechy at the end of the ring
PRESS = "press  [ Enter ]"                                            # the third line of every Data Util page
VALUE_ROWS = range(30, 64)                                           # the pixel rows the value (and the firmware's third line) use
TAB_ROWS = range(1, 9)                                               # the rows of the tab's text, inside the black bar
MENU_WIDGET, COUNTER_WIDGET = 0x24, 0x28
SET_TITLE, SET_VALUE, SET_LINE3, SET_COUNTER = 0xC00857E4, 0xC0085828, 0xC0085888, 0xC008A8A8


def _enter(dev, level, group=0, page=0):
    go(dev, 8)
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


def draw_texts(dev, value, line3):
    """Draw only the given value and third line (zero-terminated texts) on the BLECH screen and return the display: the firmware's own text widget, nothing of ours."""
    widget = dev.u32(screen_object(dev) + MENU_WIDGET)
    scratch = script_hooks.CARD + 0xF00
    dev.m.uc.mem_write(scratch, value.encode() + b"\0")
    dev.m.uc.mem_write(scratch + 64, line3.encode() + b"\0")
    dev.call(SET_VALUE, widget, scratch)
    dev.call(SET_LINE3, widget, scratch + 64)
    dev.run(0.25)
    return dev.fb()


def draw_tab(dev, label, index=None, total=None):
    """Show `label` on the tab (optionally with another counter) and return the display."""
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
    return dev.fb()


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
    edge of the display (a text that is too wide is cut off), and the tab's label is whole beside its counter."""
    title, value, line3 = texts_of(dev)
    shown = dev.fb()
    wrong = []
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
    problem = label_problem(dev, tab(dev))
    if problem:
        wrong.append(problem)
    return wrong or None


APPS_STATE_SIZE = 120                                                 # SCRIPT_APPS.stateSize in data/script/contract.mjs: the table of apps ends the runtime


def apps_open_address():
    """Where the runtime keeps the word of the open app (its script entry, 0 when none): the app table is the end of the runtime area."""
    area = json.loads((ROOT / "data" / "patches" / "script-runtime.json").read_text())["ram"][0]
    return int(area["at"], 16) + area["length"] - APPS_STATE_SIZE


def open_app_entry(dev):
    """The script entry of the open app, 0 when none."""
    return dev.u32(apps_open_address())


def blechy_ring_cases(dev):
    """The page of Blechy, the last of the ring: after Event, before the Pattern menu, shown live and gone with EXIT."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    here = lambda: (dev.screen()["number"], state(dev, S_LEVEL), counter(dev), open_app_entry(dev) != 0)
    go(dev, 10)
    press(dev, "edit_next", wait=0.8)
    landed = here()
    picture = dev.fb()
    add("blechy_follows_event", landed == (MENU, LEVEL_BLECHY, (RING - 1, RING), True) and any(picture) and not dev.m.asserts, f"{landed}")
    add("blechy_page_shows_him_alone", len(lit(picture, range(64))) > 300 and not lit(picture, range(64)) & {(x, y) for y in range(64) for x in range(70, 128)}, f"{len(lit(picture, range(64)))} pixels")
    press(dev, "edit_next", wait=0.8)
    pattern = (dev.screen()["number"], counter(dev), open_app_entry(dev))
    add("blechy_right_goes_to_pattern", pattern == (3, (0, RING), 0), f"{pattern}")
    press(dev, "edit_prev", wait=0.8)
    back = here()
    add("blechy_pattern_left_comes_back", back == landed, f"{back}")
    press(dev, "edit_prev", wait=0.8)
    event = (dev.screen()["number"], counter(dev), open_app_entry(dev))
    add("blechy_left_goes_to_event", event == (10, (RING - 2, RING), 0), f"{event}")
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
    go(dev, 8)
    return out


def cases(payload, flash=None, settings=True):
    """The menu cases as check.py entries [{id, ok, detail}]; the settings cases (settings_cases) come last unless `settings` is False."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    dev = boot(payload, flash)
    add("armed", state(dev, S_ON) == 1 and state(dev, S_COUNT) == 1 and state(dev, S_LEVEL) == 0, f"on={state(dev, S_ON)}, ring pages={state(dev, S_COUNT)}")

    # the ring: BLECH is one page of it, between Global and Data Util, in the look of Data Util's page
    here = lambda: (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), counter(dev), texts_of(dev), tab(dev))
    go(dev, 8)
    press(dev, "edit_next")
    page = here()
    press(dev, "edit_next")
    after = dev.screen()["number"]
    press(dev, "edit_prev")
    again = here()
    press(dev, "edit_prev")
    add("ring_forward", page == (MENU, 0, 0, (RING - 4, RING), ("BLECH", "", PRESS), "BLECH") and after == 14, f"{page}, then screen {after}")
    add("ring_backward", again == page and dev.screen()["number"] == 8, f"{again}, then screen {dev.screen()['number']}")

    go(dev, 14)
    add("neighbour_counters", counter(dev) == (RING - 3, RING), f"Data Util {counter(dev)}")
    go(dev, 8)
    add("global_counter", counter(dev) == (RING - 5, RING), f"Global {counter(dev)}")
    go(dev, 10)
    add("event_counter", counter(dev) == (RING - 2, RING), f"Event {counter(dev)}")
    out.extend(blechy_ring_cases(dev))

    # ENTER opens the list of the groups, ENTER on a group its pages, EXIT goes up one level each time and leaves at the ring
    goto_ring(dev)
    press(dev, "menu")
    steps = []
    for _ in range(len(LIST_PAGES)):
        steps.append((dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), counter(dev), texts_of(dev), tab(dev)))
        press(dev, "edit_next")
    wrapped = (dev.screen()["number"], state(dev, S_PAGE))
    want = [(MENU, 1, page, (page, len(LIST_PAGES)), (title, "", PRESS), "BLECH") for page, title in enumerate(LIST_PAGES)]
    add("enter_opens_the_list_of_groups", steps == want and wrapped == (MENU, 0), f"{steps}, then {wrapped}")
    goto_top(dev, LIST_PLUGINS)
    press(dev, "menu")
    inside = (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_GROUP), state(dev, S_PAGE), counter(dev), texts_of(dev))
    add("enter_goes_into_the_group", inside == (MENU, 2, GROUP_PLUGINS, 0, (0, 3), ("RUNTIME", "ON", "")) and tab(dev) == "Plugins", str(inside))
    goto_top(dev, LIST_FEATURES)
    press(dev, "menu")
    features = (state(dev, S_LEVEL), state(dev, S_GROUP), counter(dev), tab(dev), [])
    for _ in FEATURE_PAGES:
        features[4].append(texts_of(dev)[:2])
        press(dev, "edit_next")
    add("features_group_lists_the_switches", features[:4] == (2, GROUP_FEATURES, (0, len(FEATURE_PAGES)), "Feature")
        and features[4] == [(title, "ON") for title in FEATURE_PAGES] and state(dev, S_PAGE) == 0, str(features))
    goto_top(dev, LIST_PLUGINS)
    press(dev, "menu")
    press(dev, "edit_prev")
    wrapped = (state(dev, S_PAGE), counter(dev), text(dev, S_TITLE))
    press(dev, "edit_next")
    forward = (state(dev, S_PAGE), counter(dev), text(dev, S_TITLE), dev.screen()["number"])
    add("group_pages_wrap_and_count_alone", wrapped == (2, (2, 3), "IMPORT PLUGIN") and forward == (0, (0, 3), "RUNTIME", MENU), f"{wrapped}, {forward}")
    press(dev, "exit")
    up = (dev.screen()["number"], state(dev, S_LEVEL), state(dev, S_PAGE), counter(dev), text(dev, S_TITLE))
    add("exit_goes_one_level_up", up == (MENU, 1, LIST_PLUGINS, (LIST_PLUGINS, len(LIST_PAGES)), "PLUGINS") and tab(dev) == "BLECH", str(up))
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
    goto_group(dev, GROUP_PLUGINS, 0)
    dev.turn(1, wait=0.2)
    dev.turn(-1, wait=0.2)
    turned = (state(dev, S_RUN), text(dev, S_TITLE), text(dev, S_VALUE))
    add("value_turns_the_first_page", turned == (0, "RUNTIME", "OFF, RESTART"), str(turned))
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

    # no page runs its texts together or into the edge, none shows a label that is cut off
    pages = [("ring", 0)] + [("list", page) for page in range(len(LIST_PAGES))] + [(GROUP_PLUGINS, page) for page in range(3)]
    pages += [(GROUP_CUSTOM, page) for page in range(3)] + [(GROUP_COLORS, page) for page in range(6)] + [(GROUP_FEATURES, page) for page in range(len(FEATURE_PAGES))]
    crowded = []
    for group, page in pages:
        if group == "ring":
            goto_ring(dev)
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


def read_settings_full(image):
    """The valid settings files as {name: (generation, flags, trusted checksums)}."""
    return {name: (generation, flags, trusted) for name, (generation, flags, trusted, _) in read_settings_look(image).items()}


def read_settings_look(image):
    """The valid settings files as {name: (generation, flags, trusted checksums, look)}, look None for version 1."""
    volume = fat32.Volume(bytes(image))
    out = {}
    for path in SETTINGS_PATHS:
        try:
            raw = volume.read(path)
        except fat32.FatError:
            continue
        if len(raw) < 20 or raw[:4] != b"GSET":
            continue
        version, count = struct.unpack_from("<HH", raw, 4)
        head = {1: 16, 2: 20}.get(version)
        if head is None:
            continue
        size = head + 4 * count
        if count > 16 or len(raw) != size + 4 or zlib.crc32(raw[:size]) & 0xFFFFFFFF != struct.unpack_from("<I", raw, size)[0]:
            continue
        look = struct.unpack_from("<I", raw, 16)[0] if version == 2 else None
        out[path.rsplit(".", 2)[1]] = (*struct.unpack_from("<II", raw, 8), list(struct.unpack_from(f"<{count}I", raw, head)), look)
    volume.close()
    return out


def settings_cases(payload, flash=None):
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:{name}", "ok": bool(ok), "detail": detail})

    # defaults without a settings file, the script loader sees no file
    dev = boot(payload, flash, files=CARD_FOLDER)
    add("settings_defaults", (state(dev, S_SET_RUN), state(dev, S_SET_MFX), state(dev, S_EFF_RUN), state(dev, S_EFF_MFX)) == (1, 1, 1, 1)
        and dev.u32(RUNTIME + CARD_STATUS) == 2,
        f"set {state(dev, S_SET_RUN)}/{state(dev, S_SET_MFX)}, effective {state(dev, S_EFF_RUN)}/{state(dev, S_EFF_MFX)}, card status {dev.u32(RUNTIME + CARD_STATUS)}")

    # edit, show the hint, save: generation 1 goes to settings.b.bin, nothing else on the card changes
    goto_group(dev, GROUP_PLUGINS, 0)
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
    add("settings_edit_and_save", first == ("RUNTIME", "OFF, RESTART", "") and second == ("MFX 2", "OFF, RESTART", "")
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

    # no BLECH folder on the card: the open fails with 4 or 5
    nofolder = boot(payload, flash, files={"/KORG/other/file": b"1"})
    goto_group(nofolder, GROUP_FEATURES, FEAT_MFX)
    press(nofolder, "write", wait=0.6)
    add("settings_without_folder", text(nofolder, S_VALUE) == "folder missing" and not nofolder.m.asserts, f"value {text(nofolder, S_VALUE)!r}")

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
    goto_group(empty, GROUP_PLUGINS, 1)
    page = text(empty, S_TITLE), text(empty, S_VALUE)
    press(empty, "write", wait=0.6)
    add("export_without_scripts", page == ("EXPORT ALL", "") and text(empty, S_VALUE) == "no plugins" and bytes(empty.m.mmc.card.medium.data) == before,
        f"{page}, then {text(empty, S_VALUE)!r}")

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


def pins(dev):
    return dev.m.gpio.get(3, 0) & GPIO_PINS


def goto_page(dev, number):
    """Open a look page: BOTTOM LEDS and DISPLAY INVERT in CUSTOMIZATION, the six levels in its group COLORS."""
    if PAGE_LED_R <= number <= PAGE_BL_B:
        goto_group(dev, GROUP_COLORS, number - PAGE_LED_R)
    else:
        goto_group(dev, GROUP_CUSTOM, 0 if number == PAGE_LED_MODE else 2)


def shown_levels(dev, at):
    """What the three level pages of a triple (S_LED_R or S_BL_R) show: the stock state, all zero, shows 15 each."""
    levels = [state(dev, at + 4 * k) for k in range(3)]
    return levels if any(levels) else [15, 15, 15]


def set_look(dev, mode=None, led=None, backlight=None):
    """Set the look pages through the main dial, from wherever the menu is."""
    if mode is not None:
        goto_page(dev, PAGE_LED_MODE)
        dev.turn(mode - state(dev, S_LED_MODE), wait=0.25)
    for first, values, at in ((PAGE_LED_R, led, S_LED_R), (PAGE_BL_R, backlight, S_BL_R)):
        order = sorted(range(len(values or ())), key=lambda k: values[k] == 0)      # channels that stay lit first: going through all zero would be the stock state
        for i in order:
            value = values[i]
            goto_page(dev, first + i)
            shown = shown_levels(dev, at)[i]
            while value != shown:
                step = max(-8, min(8, value - shown))              # the dial reports at most a few steps at once
                dev.turn(step, wait=0.25)
                shown += step
            if not any(state(dev, at + 4 * k) for k in range(3)) and not any(values):
                break                  # all three at 0 is the stock state, the pages show 15 each from there on


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


def look_cases(payload, flash=None):
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
                           ("LED RED", "15 stock", ""), ("LED GREEN", "15 stock", ""), ("LED BLUE", "15 stock", ""),
                           ("BACKLIGHT RED", "15 stock", ""), ("BACKLIGHT GREEN", "15 stock", ""), ("BACKLIGHT BLUE", "15 stock", "")], str(texts))

    # the six levels sit behind the row COLORS of CUSTOMIZATION: ENTER opens them, EXIT goes back to that row
    goto_group(dev, GROUP_CUSTOM, CUSTOM_COLORS)
    row = texts_of(dev), counter(dev)
    press(dev, "menu", 0.4)
    inside = (state(dev, S_LEVEL), state(dev, S_GROUP), state(dev, S_PAGE), tab(dev), text(dev, S_TITLE), counter(dev))
    press(dev, "edit_next", 0.4)
    second = text(dev, S_TITLE)
    press(dev, "exit", 0.4)
    back = (state(dev, S_LEVEL), state(dev, S_GROUP), state(dev, S_PAGE), texts_of(dev)[0], tab(dev))
    press(dev, "exit", 0.4)
    top = (state(dev, S_LEVEL), state(dev, S_PAGE))
    add("colors_submenu", row[0] == ("COLORS", "", PRESS) and row[1][0] == CUSTOM_COLORS
        and inside == (2, GROUP_COLORS, 0, "Colors", "LED RED", (0, 6)) and second == "LED GREEN"
        and back == (2, GROUP_CUSTOM, CUSTOM_COLORS, "COLORS", "Custom") and top[0] == 1 and not dev.m.asserts,
        f"row {row}, ENTER {inside}, EDIT {second}, EXIT {back}, EXIT {top}")

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
    results, flags = {}, {}
    for name, levels in (("green", (0, 15, 0)), ("red5", (5, 0, 0)), ("mix", (3, 8, 12)), ("one_of_16", (1, 14, 0))):
        set_look(mix, backlight=levels)
        mix.run(0.3)
        results[name] = duty(mix, 1.0)
        flags[name] = state(mix, S_BL_PWM)
    near = lambda got, want: all(abs(got[k] - want[k]) <= 0.02 for k in "RGB")
    add("backlight_plain_pin", results["green"][0] == {"R": 0.0, "G": 1.0, "B": 0.0} and results["green"][1] == 0 and flags["green"] == 0 and flags["mix"] == 1, f"{results['green']}")
    add("backlight_pwm_duty", near(results["red5"][0], {"R": 5 / 16, "G": 0, "B": 0}) and near(results["mix"][0], {"R": 3 / 16, "G": 8 / 16, "B": 12 / 16})
        and near(results["one_of_16"][0], {"R": 1 / 16, "G": 14 / 16, "B": 0}), f"{results}")
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
    add("backlight_power_save_stays", abs(dimmed[0]["R"] - 0.037) < 0.02 and abs(dimmed[0]["G"] - 0.037) < 0.02 and dimmed[0]["B"] == 0 and not mix.m.asserts, f"{dimmed}")
    add("backlight_back_from_power_save", near(resumed[0], {"R": 0, "G": 0, "B": 12 / 16}), f"{resumed}")
    add("backlight_zero_is_stock_white", stock[0] == {"R": 1.0, "G": 1.0, "B": 1.0} and stock[1] == 0 and state(mix, S_BL_PWM) == 0, f"{stock}")

    # WRITE keeps everything in the file, the next start reads it
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, mode=0, led=(15, 7, 0), backlight=(0, 15, 6))
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    size = len(fat32.Volume(bytes(keep.m.mmc.card.medium.data)).read(SETTINGS_PATHS[1]))
    add("file_holds_the_look", files.get("b", (0, 0, 0, None))[3] == look_word(0, (15, 7, 0), (0, 15, 6)) and files["b"][:2] == (1, 3) and size == 24, f"{files}, {size} bytes")
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
    out.extend(invert_cases(payload, flash))
    out.extend(confirm_cases(payload, flash))
    out.extend(tap_motion_cases(payload, flash))
    out.extend(note_assist_menu_cases(payload, flash))
    out.extend(default_level_cases(payload, flash))
    out.extend(early_look_cases(payload, flash))
    return out


def cases_task():
    """The screen cases in a worker (parallel.py)."""
    import parallel
    return cases(parallel.shared["payload"], parallel.shared["flash"], settings=False)


def splash_menu_cases(payload, flash=None):
    """CUSTOMIZATION, where the build has the splash editor: SPLASH IMPORT reads KORG/blechtribe/splash.bmp into the start image,
    SPLASH DRAW opens the editor (Global, page SPLASH SCREEN). Without the editor (the synth) the group keeps its 8 pages."""
    from splash_cases import bmp, image_of
    import splash_editor
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:splash_{name}", "ok": bool(ok), "detail": detail})

    pic = [[1 if (x + 2 * y) % 7 == 0 else 0 for x in range(128)] for y in range(64)]
    dev = boot(payload, flash, files={**CARD_FOLDER, "/KORG/blechtribe/splash.bmp": bmp(pic)})
    if dev.u32(splash_editor.IMPORT_ENTRY) == 0xFFFFFFFF:
        goto_group(dev, GROUP_CUSTOM, 0)
        add("no_pages_without_the_editor", counter(dev) is not None and counter(dev)[1] == 3, f"counter {counter(dev)}")
        return out
    goto_group(dev, GROUP_CUSTOM, CUSTOM_PAD + 2)
    before = texts_of(dev)
    press(dev, "menu", 0.6)
    after = texts_of(dev)
    stored = dev.read(splash_editor.RECBUF + 8, 1024) == image_of(pic)
    add("import", before == ("SPLASH IMPORT", "", PRESS) and after[:2] == ("SPLASH IMPORT", "loaded") and stored and not dev.m.asserts,
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
    goto_group(bare, GROUP_CUSTOM, CUSTOM_PAD + 2)
    press(bare, "menu", 0.6)
    add("import_without_file", texts_of(bare)[1] == "no splash.bmp", str(texts_of(bare)))
    return out


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
    goto_group(dev, GROUP_CUSTOM, CUSTOM_PAD)
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
    goto_group(dev, GROUP_CUSTOM, CUSTOM_PAD)
    press(dev, "write", wait=0.6)
    word = read_settings_look(dev.m.mmc.card.medium.data).get("b", (0, 0, 0, None))[3]
    add("file_holds_them", word is not None and (word >> 2) & 3 == PC.PINK and (word >> 29) & 3 == 1, f"look word {word:#x}" if word is not None else "no file")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(dev.m.mmc.card.medium.data))))
    again.run(wait + 0.8)
    add("start_reads_them", again.u32(PC.PC_SETTING) == PC.PINK | PC.RED << 4 and pad(again, 0) == (255, 0) and not again.m.asserts,
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
    add("power_save_dims_every_led", lit and all(quarter[led] == (v + 3) >> 2 for led, v in lit.items()) and {led: after.get(led, 0) for led in lit} == lit
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
    return out


def invert_cases(payload, flash=None):
    """The page DISPLAY INVERT of the group CUSTOMIZATION: the controller is told 0xA7 (reverse display) or 0xA6 (normal) once per
    change, never when the setting stays OFF, the file keeps it (bit 28 of the look word), and EXIT at power-on leaves the controller
    alone. The emulator's controller (machine.py) swaps dark and clear on 0xA7: shown() is the complement of the RAM."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:look_invert_{name}", "ok": bool(ok), "detail": detail})

    ram = lambda dev: bytes(b for row in dev.m.fb for b in row)
    flipped = lambda dev: dev.m.shown() == bytes(b ^ 0xFF for b in ram(dev)) and ram(dev) != bytes(len(ram(dev)))
    plain = lambda dev: dev.m.shown() == ram(dev)
    status = lambda dev: (state(dev, S_INVERT), dev.m.lcd_reverse, dev.m.lcd_reverse_sent)

    # OFF is the default, with a card without a file and without a card: the controller is never told anything
    dev = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    bare = boot(payload, flash, adapter=True, card=False)
    add("default_off", status(dev) == (0, False, 0) and status(bare) == (0, False, 0) and plain(dev) and plain(bare) and state(bare, S_ON) == 1,
        f"with card {status(dev)}, without {status(bare)}")

    # the page, on and off through the main dial: one command per change, the whole display swaps, the main screen too
    goto_page(dev, PAGE_INVERT)
    page = texts_of(dev), counter(dev), tab(dev)
    dev.turn(1, wait=0.4)
    dev.run(0.3)
    on = texts_of(dev), status(dev), flipped(dev)
    menu_screen = flipped(dev)
    dev.turn(1, wait=0.3)
    dev.run(0.3)
    still = status(dev)
    go(dev, 1)
    dev.run(0.5)
    main_on = dev.screen()["number"], status(dev), flipped(dev)
    import splash_editor
    custom = 3 if dev.u32(splash_editor.IMPORT_ENTRY) == 0xFFFFFFFF else 7      # PAD COLOR, SELECT COLOR, SPLASH IMPORT and SPLASH DRAW follow where the set has them
    add("page", page == (("DISPLAY INVERT", "OFF", ""), (2, custom), "Custom"), f"{page}")
    add("on_swaps_the_display", on == (("DISPLAY INVERT", "ON", ""), (1, True, 1), True) and menu_screen and still == (1, True, 1),
        f"{on}, dial again {still}")
    add("main_screen_inverted", main_on == (1, (1, True, 1), True) and not dev.m.asserts, f"{main_on}")
    goto_page(dev, PAGE_INVERT)
    dev.turn(-1, wait=0.4)
    dev.run(0.3)
    off = texts_of(dev), status(dev), plain(dev)
    add("off_swaps_back", off == (("DISPLAY INVERT", "OFF", ""), (0, False, 2), True), f"{off}")

    # WRITE keeps it in the same file as the other CUSTOMIZATION values (bit 28), the next start reads it and shows it
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, led=(15, 7, 0))
    goto_page(keep, PAGE_INVERT)
    keep.turn(1, wait=0.4)
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    word = files.get("b", (0, 0, 0, None))[3]
    add("file_holds_it", word is not None and word & INVERT_BIT and word == look_word(0, (15, 7, 0), (0, 0, 0), 1), f"{files}")
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(keep.m.mmc.card.medium.data))))
    again.run(2.0)
    add("start_reads_and_shows_it", status(again) == (1, True, 1) and flipped(again) and not again.m.asserts, f"{status(again)}, screen {again.screen()['number']}")

    # files that say nothing about it (version 1, a look word without the bit) stay OFF; a damaged file is ignored
    quiet = []
    for name, files in (("v1", {SETTINGS_PATHS[0]: settings_file(3, 3)}), ("no_bit", {SETTINGS_PATHS[0]: settings_file_v2(3, 3, look_word(1, (15, 0, 0)))}),
                        ("bad_crc", {SETTINGS_PATHS[0]: settings_file_v2(3, 3, look_word(invert=1), bad_crc=True)})):
        probe = boot(payload, flash, files={**CARD_FOLDER, **files}, adapter=True)
        quiet.append((name, status(probe)))
    add("files_without_it_stay_off", all(got == (0, False, 0) for _, got in quiet), f"{quiet}")
    wanted = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(3, 3, look_word(invert=1))}, adapter=True)
    add("file_with_the_bit_is_on", status(wanted) == (1, True, 1) and flipped(wanted), f"{status(wanted)}")

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
    add("page", page == (("PATTERN CONFIRM", "ON", ""), (FEAT_PC, len(FEATURE_PAGES)), "Feature"), f"{page}")
    add("dial_acts_at_once", off == (("PATTERN CONFIRM", "OFF", ""), (0, 0)) and still == (0, 0) and back == (("PATTERN CONFIRM", "ON", ""), (1, 1)) and not dev.m.asserts, f"{off}, again {still}, back {back}")

    # WRITE keeps OFF in the flags and leaves the look word and the other flags alone
    keep = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    set_look(keep, led=(15, 7, 0))
    goto_group(keep, GROUP_FEATURES, FEAT_PC)
    keep.turn(-1, wait=0.3)
    press(keep, "write", wait=0.6)
    files = read_settings_look(keep.m.mmc.card.medium.data)
    got = files.get("b", (0, 0, 0, None))
    add("file_holds_off", got[:2] == (1, 3 | PC_OFF_BIT) and got[3] == look_word(0, (15, 7, 0)), f"{files}")
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
    add("page", page == (("TAP MOTION", "ON", ""), (FEAT_TM, len(FEATURE_PAGES)), "Feature"), f"{page}")
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
    add("page_before_note_assist", nxt == ("NOTE ASSIST", (FEAT_NA, len(FEATURE_PAGES))) and texts_of(dev)[0] == "TAP MOTION", f"after EDIT next {nxt}, after EDIT previous {texts_of(dev)}")

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
    add("file_holds_off", got[:2] == (1, 3 | PC_OFF_BIT | TM_OFF_BIT) and got[3] == look_word(0, (15, 7, 0)), f"{files}")
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
    add("page", page == (("NOTE ASSIST", "ON", ""), (FEAT_NA, len(FEATURE_PAGES)), "Feature"), f"{page}")
    add("dial_acts_at_once", off == (("NOTE ASSIST", "OFF", ""), (0, 0)) and still == (0, 0) and back == (("NOTE ASSIST", "ON", ""), (1, 1)) and not dev.m.asserts, f"{off}, again {still}, back {back}")

    # the page is the last of the group FEATURES: EDIT next wraps to the first, EDIT previous from there comes back
    press(dev, "edit_next", wait=0.4)
    wrapped = texts_of(dev)[0], counter(dev)
    press(dev, "edit_prev", wait=0.4)
    add("page_is_last", wrapped == ("MFX 2", (0, len(FEATURE_PAGES))) and texts_of(dev)[0] == "NOTE ASSIST", f"after EDIT next {wrapped}, after EDIT previous {texts_of(dev)}")

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
    add("file_holds_off", got[:2] == (1, 3 | TM_OFF_BIT | NA_OFF_BIT) and got[3] == look_word(0, (15, 7, 0)), f"{files}")
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
    """The level pages show 15 for a state in which nothing is set (the device is at full light then): no file, or a file whose look word has
    zeros, shows 15 each and acts as the firmware does; a file with values shows them; the dial turns down from 15 and the last channel
    turned down to 0 is that state again."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:look_default_{name}", "ok": bool(ok), "detail": detail})

    levels = lambda dev: [(text(dev, S_TITLE), text(dev, S_VALUE)) for page in range(PAGE_LED_R, PAGE_BL_B + 1) if goto_page(dev, page) is None]
    fresh = boot(payload, flash, files=CARD_FOLDER, adapter=True)
    zero = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(0))}, adapter=True)
    mixed = boot(payload, flash, files={**CARD_FOLDER, SETTINGS_PATHS[0]: settings_file_v2(2, 3, look_word(0, (0, 0, 5), (0, 7, 0)))}, adapter=True)
    want_stock = [(title, "15 stock") for title in ("LED RED", "LED GREEN", "LED BLUE", "BACKLIGHT RED", "BACKLIGHT GREEN", "BACKLIGHT BLUE")]
    add("no_file_shows_15", levels(fresh) == want_stock, f"{levels(fresh)}")
    add("zero_word_shows_15_and_acts_as_before", levels(zero) == want_stock and state(zero, S_LED_EFF) == 0 and state(zero, S_BL_ON) == 0x38 and state(zero, S_BL_PWM) == 0,
        f"{levels(zero)}, LED kind {state(zero, S_LED_EFF)}, light pins {state(zero, S_BL_ON):#x}")
    add("file_with_values_reads_as_before", levels(mixed) == [("LED RED", "0"), ("LED GREEN", "0"), ("LED BLUE", "5"), ("BACKLIGHT RED", "0"), ("BACKLIGHT GREEN", "7"), ("BACKLIGHT BLUE", "0")]
        and state(mixed, S_LED_EFF) == 1, f"{levels(mixed)}, LED kind {state(mixed, S_LED_EFF)}")

    # the dial: up from the state changes nothing, down starts at 15 each, the last channel to 0 is the state again
    goto_page(fresh, PAGE_LED_R)
    fresh.turn(3, wait=0.3)
    up = [state(fresh, S_LED_R + 4 * k) for k in range(3)]
    fresh.turn(-1, wait=0.3)
    down = [state(fresh, S_LED_R + 4 * k) for k in range(3)], texts_of(fresh)[:2]
    set_look(fresh, led=(0, 0, 0))
    back = [state(fresh, S_LED_R + 4 * k) for k in range(3)], texts_of(fresh)[:2], state(fresh, S_LED_EFF)
    add("dial_from_the_default", up == [0, 0, 0] and down == ([14, 15, 15], ("LED RED", "14")) and back == ([0, 0, 0], ("LED BLUE", "15 stock"), 0), f"up {up}, down {down}, back {back}")
    return out


def early_look_cases(payload, flash=None):
    """The look (backlight colour, bottom LED colour) is set by the time the sample loader starts, not only after it ends: the menu arms and
    reads its settings from a hook on the loading command, before the loader. Compared with the same copy without that hook (the
    instruction put back), which arms behind the loader, and with the main screen's time, which must not get later."""
    if synthaddr.is_synth(payload):
        return synth_start_cases(payload, flash)
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
    add("loader_starts_at_the_same_time", abs(early["loader_ms"] - late["loader_ms"]) < 15, f"loader {early['loader_ms']:.1f} ms with the hook, {late['loader_ms']:.1f} ms without (the settings are read first now, not afterwards)")
    add("main_screen_not_later", early["main_ms"] <= late["main_ms"] + 15 and not early["asserts"], f"main screen at {early['main_ms']:.1f} ms with the hook, {late['main_ms']:.1f} ms without")
    held = early_run(payload, flash, files, held=KILL)
    add("exit_held_stays_stock", held.get("on") != 1 and held.get("pins") == GPIO_PINS and not held["asserts"], f"armed {held.get('on'):#x}, light pins {held.get('pins'):#x}")
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


def look_cases_task():
    """The look cases in a worker (parallel.py)."""
    import parallel
    return (look_cases(parallel.shared["payload"], parallel.shared["flash"]) + splash_menu_cases(parallel.shared["payload"], parallel.shared["flash"])
            + pad_colour_cases(parallel.shared["payload"], parallel.shared["flash"]))


def settings_cases_task():
    """The settings cases in a worker (parallel.py)."""
    import parallel
    return settings_cases(parallel.shared["payload"], parallel.shared["flash"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["cases"])
    parser.add_argument("--base", required=True)
    parser.add_argument("--patched", required=True)
    parser.add_argument("--flash", nargs="*")
    args = parser.parse_args()
    payload = Path(args.patched).read_bytes()[HEADER:]
    flash = load_flash(args.flash) if args.flash else None
    result = cases(payload, flash) + look_cases(payload, flash) + splash_menu_cases(payload, flash) + pad_colour_cases(payload, flash)
    print(json.dumps(result, indent=1))
    return 0 if all(c["ok"] for c in result) else 1


if __name__ == "__main__":
    sys.exit(main())
