# SPDX-License-Identifier: GPL-2.0-only
"""Screens and font specimens of two firmware copies, for the BLECH theme preview.

Boots both copies in the emulator, drives them through the same key presses to a list of
screens and returns what the display shows, plus every printable character of the four fonts
drawn by the firmware's own text function (so the advances are the firmware's). Used by
tools/patch/blech_theme_preview.mjs; it prints JSON and holds no firmware bytes of its own
(the frames are what the display shows, they are not written anywhere unless that tool does).

    tools/emu/.venv/bin/python tools/emu/theme_screens.py --a BLECH.VSB --b BLECH-THEMED.VSB [--flash dump.bin] > screens.json
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import bootcache  # noqa: E402
import menu_cases  # noqa: E402
import parallel  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import SWITCH_SCREEN, TICK, TRAP, Dev  # noqa: E402

# name, card in the slot, steps. Screen numbers are the firmware's (docs/messungen/2026-10-14-display-schriften.md).
SCENES = [
    ("main", True, []),
    ("pattern", True, [("press", "menu")]),
    ("pattern-bpm", True, [("press", "menu"), ("press", "edit_next"), ("press", "edit_next"), ("press", "edit_next")]),
    ("part-edit", True, [("go", 7)]),
    ("global", True, [("go", 8)]),
    ("global-page", True, [("go", 9), ("turn", 1)]),
    ("data-utility", True, [("go", 14)]),
    ("blech-menu", True, [("go", 45)]),
    ("select-destination", True, [("go", 18)]),
    ("enter-name", True, [("go", 40)]),
    ("xy-calibration", True, [("go", 32)]),
    ("import-error", False, [("go", 17)]),
    ("software-update", True, [("go", 44)]),
]

STATE_FONT = 0xC03487CC
SET_FONT = 0xC003F730
TEXT = 0xC003F7D0
TEXT_WIDTH = 0xC003F89C
RESET = 0xC003F0D4
PIXELS = 0xC031B310           # the display buffer, byte (y / 8) * 128 + x, bit y % 8
SCRATCH = 0xC01FF100          # inside the free run the callers' trap also lives in, never executed
FONT_LINE = {0: 11, 1: 17, 2: 14, 3: 14}   # line spacing used for each font's specimen


class Caller(Dev):
    """A device that can run a firmware function from inside the screen tick, with a cleared stack for stack arguments."""

    def call_clean(self, func, *args):
        import unicorn
        m, uc, arm = self.m, self.m.uc, self.m.A
        hit = []
        hook = uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: (hit.append(1), u.emu_stop()), begin=TICK, end=TICK)
        uc.ctl_flush_tb()
        end = m.time_ns / 1e9 + 2.0
        while not hit and m.time_ns / 1e9 < end:
            m.run_slice()
            if not hit:
                m.lines()
                m.irq()
        uc.hook_del(hook)
        uc.ctl_flush_tb()
        if not hit:
            raise RuntimeError("the screen tick did not come")
        regs = [arm.UC_ARM_REG_R0 + i for i in range(13)] + [arm.UC_ARM_REG_SP, arm.UC_ARM_REG_LR, arm.UC_ARM_REG_PC, arm.UC_ARM_REG_CPSR]
        saved = [uc.reg_read(r) for r in regs]
        sp = (saved[13] - 0x400) & ~7
        uc.mem_write(sp, bytes(64))
        for i, value in enumerate(args):
            uc.reg_write(arm.UC_ARM_REG_R0 + i, value & 0xFFFFFFFF)
        uc.reg_write(arm.UC_ARM_REG_SP, sp)
        uc.reg_write(arm.UC_ARM_REG_LR, TRAP)
        uc.reg_write(arm.UC_ARM_REG_PC, func)
        stop = m.time_ns + 2_000_000_000
        uc.ctl_set_exits([TRAP, *m.ENTRIES])
        try:
            while uc.reg_read(arm.UC_ARM_REG_PC) != TRAP and m.time_ns < stop and not m.asserts:
                m.run_slice(limit=stop)
                if uc.reg_read(arm.UC_ARM_REG_PC) != TRAP:
                    m.lines()
                    m.irq()
        finally:
            uc.ctl_set_exits(list(m.ENTRIES))
        result = uc.reg_read(arm.UC_ARM_REG_R0)
        for r, value in zip(regs, saved):
            uc.reg_write(r, value)
        return result

    def pixels(self):
        return self.read(PIXELS, 1024)


def screen_device(payload, flash, card):
    if card:
        dev = menu_cases.boot(payload, flash)
        return Caller(payload, flash, 0, machine=dev.m)
    machine, _ = bootcache.booted(payload, flash, 0, 3.0)
    return Caller(payload, flash, 0, machine=machine)


def scene(payload, flash, card, steps):
    dev = screen_device(payload, flash, card)
    for step in steps:
        if step[0] == "go":
            dev.call(SWITCH_SCREEN, step[1], 0)
            dev.run(0.5)
        elif step[0] == "press":
            dev.press(step[1], wait=0.4)
        elif step[0] == "turn":
            dev.turn(step[1], wait=0.4)
    dev.run(0.3)
    if dev.m.asserts:
        raise RuntimeError(f"assertion while showing the scene: {dev.m.asserts}")
    return dev.fb().hex()


def scene_task(index, which):
    name, card, steps = SCENES[index]
    return scene(parallel.shared[which], parallel.shared["flash"], card, steps)


def set_font(dev, font):
    dev.m.uc.mem_write(SCRATCH - 16, struct.pack("<I", font))
    dev.call_clean(SET_FONT, SCRATCH - 16)


def draw(dev, font, text, x, y):
    set_font(dev, font)
    dev.m.uc.mem_write(SCRATCH, text.encode("latin1") + b"\0")
    dev.call_clean(TEXT, SCRATCH, x, y, 0)


def wrap(dev, font, text, width=126):
    lines, current = [], ""
    for ch in text:
        if current:
            set_font(dev, font)
            dev.m.uc.mem_write(SCRATCH, (current + ch).encode("latin1") + b"\0")
            if dev.call_clean(TEXT_WIDTH, SCRATCH) > width:
                lines.append(current)
                current = ""
        current += ch
    return lines + [current] if current else lines


def specimen_task(font, which):
    """Every printable ASCII character of a font as display frames (hex), lines wrapped to the display."""
    payload = parallel.shared[which]
    dev = screen_device(payload, parallel.shared["flash"], False)
    dev.press("menu", wait=0.3)
    chars = "".join(chr(c) for c in range(32, 127))
    lines = wrap(dev, font, chars)
    spacing = FONT_LINE[font]
    per = 64 // spacing
    frames = []
    for i in range(0, len(lines), per):
        dev.call_clean(RESET)
        for k, line in enumerate(lines[i:i + per]):
            draw(dev, font, line, 1, k * spacing)
        frames.append(dev.pixels().hex())
    return frames


def pixel_frame(hexed):
    """Display frame (page-major bytes, bit 0 on top) to 64 rows of 128 0/1 values."""
    raw = bytes.fromhex(hexed)
    return [[(raw[(y >> 3) * 128 + x] >> (y & 7)) & 1 for x in range(128)] for y in range(64)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--a", required=True, type=Path, help="the copy without the theme")
    p.add_argument("--b", required=True, type=Path, help="the copy with the theme")
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", nargs="*", default=[], help="scene names; default all")
    a = p.parse_args()
    payload = {k: v.read_bytes()[0x100:] for k, v in (("a", a.a), ("b", a.b))}
    flash = load_flash(a.flash) if a.flash else None
    wanted = [i for i, s in enumerate(SCENES) if not a.only or s[0] in a.only]
    tasks = [("theme_screens", "scene_task", (i, which)) for i in wanted for which in ("a", "b")]
    tasks += [("theme_screens", "specimen_task", (font, which)) for font in (0, 1, 2, 3) for which in ("a", "b")]
    out = parallel.run_tasks(tasks, {**payload, "flash": flash})
    scenes = [{"name": SCENES[i][0], "a": out[2 * k], "b": out[2 * k + 1]} for k, i in enumerate(wanted)]
    rest = out[2 * len(wanted):]
    specimens = {str(font): {"a": rest[2 * font], "b": rest[2 * font + 1]} for font in range(4)}
    print(json.dumps({"scenes": scenes, "specimens": specimens}))


if __name__ == "__main__":
    main()
