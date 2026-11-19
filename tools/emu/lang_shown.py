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


def shown_task(screen):
    """[(text bytes as latin-1 str, font id)] drawn on one screen while it is shown, turned and stepped."""
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
    try:
        dev.call(SWITCH_SCREEN, screen, 0)
        dev.run(0.4)
        for _ in range(TURNS):
            dev.turn(1, wait=0.08)
        dev.call(SWITCH_SCREEN, screen, 0)
        dev.run(0.2)
        for _ in range(EDITS):
            dev.press("edit_next", wait=0.08)
    finally:
        for hook in hooks:
            uc.hook_del(hook)
        uc.ctl_flush_tb()
    return sorted(seen)


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
    """{(text, font)} over all screens."""
    tasks = [("lang_shown", "shown_task", (s,)) for s in SCREENS]
    seen = set()
    for part in parallel.run_tasks(tasks, {"payload": payload, "flash": flash}):
        seen.update(tuple(x) for x in part)
    return seen


def widths(payload, items, flash=None):
    return parallel.run_tasks([("lang_shown", "widths_task", (list(items),))], {"payload": payload, "flash": flash})[0]
