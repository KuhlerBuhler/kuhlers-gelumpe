# SPDX-License-Identifier: GPL-2.0-only
"""The texts the firmware draws, for the translation workbench (tools/lang/workbench.py, docs/firmware-sprache.md).

Boots the image, shows every screen of the screen manager once and on it turns the wheel and steps EDIT to the right,
with a hook on the text function that notes every text and the font it is drawn in. Also measures text widths with the
firmware's own width function. Returns the texts to the caller; it writes nothing.
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bootcache  # noqa: E402
import menu_cases  # noqa: E402
import parallel  # noqa: E402
from splash_cases import SWITCH_SCREEN  # noqa: E402
from theme_screens import SCRATCH, SET_FONT, TEXT, TEXT_WIDTH, Caller, set_font  # noqa: E402

SCREENS = range(45)          # the screen manager's numbers 0 to 44 (docs/messungen/2026-10-14-display-schriften.md)
TURNS = 32                   # wheel detents per screen
EDITS = 32                   # EDIT > presses per screen


def _cstring(uc, at, limit=96):
    raw = bytes(uc.mem_read(at, limit))
    return raw.split(b"\0", 1)[0]


def walk(dev, screen):
    """Show `screen`, turn the wheel, show it again and step EDIT to the right. Raises unicorn's UcError when the
    firmware runs off its memory there (Korg's red 2.02 does on screens 23 and 24 when switched to straight)."""
    dev.call(SWITCH_SCREEN, screen, 0)
    dev.run(0.4)
    for _ in range(TURNS):
        dev.turn(1, wait=0.08)
    dev.call(SWITCH_SCREEN, screen, 0)
    dev.run(0.2)
    for _ in range(EDITS):
        dev.press("edit_next", wait=0.08)


def shown_task(screen):
    """{"seen": [(text bytes as latin-1 str, font id)] drawn on one screen while it is shown, turned and stepped,
    "crashed": None or the emulator's error}."""
    import unicorn
    payload, flash = parallel.shared["payload"], parallel.shared["flash"]
    dev = menu_cases.boot(payload, flash)
    dev = Caller(payload, flash, 0, machine=dev.m)
    uc = dev.m.uc
    font = [-1]
    seen = set()

    def at_font(u, address, size, user):
        font[0] = struct.unpack("<i", bytes(u.mem_read(u.reg_read(dev.m.A.UC_ARM_REG_R0), 4)))[0]

    def at_text(u, address, size, user):
        text = _cstring(u, u.reg_read(dev.m.A.UC_ARM_REG_R0))
        if text:
            seen.add((text.decode("latin1"), font[0]))

    text_at, font_at = dev.a(TEXT), dev.a(SET_FONT)
    hooks = [uc.hook_add(unicorn.UC_HOOK_CODE, at_text, begin=text_at, end=text_at),
             uc.hook_add(unicorn.UC_HOOK_CODE, at_font, begin=font_at, end=font_at)]
    uc.ctl_flush_tb()
    crashed = None
    try:
        walk(dev, screen)
    except unicorn.UcError as error:
        crashed = str(error)
    finally:
        for hook in hooks:
            uc.hook_del(hook)
        uc.ctl_flush_tb()
    return {"seen": sorted(seen), "crashed": crashed}


def widths_task(items):
    """Pixel widths of [(text, font)] by the firmware's text width function, in one booted device."""
    payload, flash = parallel.shared["payload"], parallel.shared["flash"]
    machine, _ = bootcache.booted(payload, flash, 0, 3.0)
    dev = Caller(payload, flash, 0, machine=machine)
    out = []
    for text, font in items:
        set_font(dev, font)
        dev.m.uc.mem_write(SCRATCH, text.encode("latin1") + b"\0")
        out.append(dev.call_clean(TEXT_WIDTH, SCRATCH))
    return out


def shown(payload, flash=None):
    """({(text, font)} over all screens, {screen: error} of the screens the emulator could not show)."""
    tasks = [("lang_shown", "shown_task", (s,)) for s in SCREENS]
    seen, crashed = set(), {}
    for screen, part in zip(SCREENS, parallel.run_tasks(tasks, {"payload": payload, "flash": flash})):
        seen.update(tuple(x) for x in part["seen"])
        if part["crashed"]:
            crashed[screen] = part["crashed"]
    return seen, crashed


def widths(payload, items, flash=None):
    return parallel.run_tasks([("lang_shown", "widths_task", (list(items),))], {"payload": payload, "flash": flash})[0]


PIXEL = 0xC003F12C           # set one pixel: pointers to x and y (masked to the display there, so x 130 lands at 2)
GLYPH_PIXEL = 0xC003F278     # the return address of the glyph function's pixel call
PUT = (0xC0015824, 0xC0015900)  # the function that writes the frame buffer for one pixel
FB = 0xC031B310              # the frame buffer, 128 x 64, 8-pixel column strips
STRCPY = 0xC000AA64          # the copy Korg's text setters call (title, value, line 3, dialog text)
LANG = (0xC016D000, 0xC0170000)  # lang-de's area (script_hooks.LANG)


def layout_task(screen, german):
    """What one screen does while it is shown, turned and stepped: `problems`, a text from `german` that runs past the
    display or whose pixels land on pixels another text drew and nothing cleared in between; `drawn`, every text drawn;
    `copies`, (source, bytes with NUL, return address) of each strcpy out of lang-de's area; `crashed`, None or the
    emulator's error."""
    import unicorn
    payload, flash = parallel.shared["payload"], parallel.shared["flash"]
    dev = menu_cases.boot(payload, flash)
    dev = Caller(payload, flash, 0, machine=dev.m)
    uc, A = dev.m.uc, dev.m.A
    current = [""]
    owner = {}
    problems = set()
    drawn, copies = set(), set()
    glyph_pixel, put, fb = dev.a(GLYPH_PIXEL), tuple(dev.a(a) for a in PUT), dev.a(FB)

    def mine(text):
        return any(g in text for g in german)

    def at_text(u, address, size, user):
        current[0] = _cstring(u, u.reg_read(A.UC_ARM_REG_R0)).decode("latin1")
        drawn.add(current[0])

    def at_copy(u, address, size, user):
        source = u.reg_read(A.UC_ARM_REG_R1)
        if LANG[0] <= source < LANG[1]:
            copies.add((source, len(_cstring(u, source, 256)) + 1, u.reg_read(A.UC_ARM_REG_LR)))

    def at_pixel(u, address, size, user):
        x, y = (struct.unpack("<i", bytes(u.mem_read(u.reg_read(r), 4)))[0] for r in (A.UC_ARM_REG_R0, A.UC_ARM_REG_R1))
        if u.reg_read(A.UC_ARM_REG_LR) != glyph_pixel:
            owner.pop((x % 128, y % 64), None)   # a box or clear drawn pixel by pixel
            return
        text = current[0]
        if not 0 <= x < 128 or not 0 <= y < 64:
            if mine(text):
                problems.add(("edge", screen, text, ""))
            return
        prev = owner.get((x, y))
        lit = u.mem_read(fb + (y // 8) * 128 + x, 1)[0] >> (y % 8) & 1
        if prev is not None and prev != text and lit and (mine(text) or mine(prev)):
            problems.add(("overlap", screen, text, prev))
        owner[(x, y)] = text

    def at_write(u, access, address, size, value, user):
        pc = u.reg_read(A.UC_ARM_REG_PC)
        if put[0] <= pc < put[1]:
            return
        for off in range(address - fb, address - fb + size):
            x, page = off % 128, off // 128
            for y in range(page * 8, page * 8 + 8):
                owner.pop((x, y), None)

    text_at, pixel_at, copy_at = dev.a(TEXT), dev.a(PIXEL), dev.a(STRCPY)
    hooks = [uc.hook_add(unicorn.UC_HOOK_CODE, at_text, begin=text_at, end=text_at),
             uc.hook_add(unicorn.UC_HOOK_CODE, at_pixel, begin=pixel_at, end=pixel_at),
             uc.hook_add(unicorn.UC_HOOK_CODE, at_copy, begin=copy_at, end=copy_at),
             uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, at_write, begin=fb, end=fb + 1023)]
    uc.ctl_flush_tb()
    crashed = None
    try:
        walk(dev, screen)
    except unicorn.UcError as error:
        crashed = str(error)
    finally:
        for hook in hooks:
            uc.hook_del(hook)
        uc.ctl_flush_tb()
    return {"problems": sorted(problems), "drawn": sorted(drawn), "copies": sorted(copies), "crashed": crashed}


def layout(payload, german, flash=None):
    """[(kind, screen, text, other)] over all screens: German texts past the edge or over another text."""
    tasks = [("lang_shown", "layout_task", (s, sorted(german))) for s in SCREENS]
    out = set()
    for part in parallel.run_tasks(tasks, {"payload": payload, "flash": flash}):
        out.update(tuple(x) for x in part["problems"])
    return sorted(out)
