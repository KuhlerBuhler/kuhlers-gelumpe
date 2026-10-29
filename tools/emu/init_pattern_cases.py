"""Emulator cases of the init-pattern patch (tools/patch/init_pattern.py) and its page SET INIT PATTERN in DATA UTILITY (behind the firmware's functions):
the page shows FACTORY, the dial sets Global byte 247, and DATA UTILITY's INITIALIZE PATTERN then copies that pattern; with
FACTORY, or EXIT held at power-on, it is the firmware's template.

    python3 tools/emu/init_pattern_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import init_pattern as spec  # noqa: E402
import synthaddr  # noqa: E402
import menu_cases  # noqa: E402
from machine import load_flash  # noqa: E402

IMAGE = 0xC0000000
DATA_UTIL = 14                       # the screen number of the menu Data Util (docs/messungen/2026-10-09-menuezustand.md)
PATTERN_IN_RAM = 0xC033E6A4          # pointer to the pattern in RAM, its block from +4 (SC_PATPTR in tools/patch/script_hooks.py)
MARK_NAME = b"TEMPLATE SEVEN\0\0"      # put into the bank block of pattern 7, so the copy shows on the display


def for_build(payload):
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")
    global PATTERN_IN_RAM
    PATTERN_IN_RAM = synthaddr.tr(0xC033E6A4) if synthaddr.is_synth(payload) else 0xC033E6A4


def has_hooks(payload):
    """True when INITIALIZE PATTERN calls our code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.INIT_CALL - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= (spec.INIT_CALL + 8 + (off << 2)) & 0xFFFFFFFF < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"initpattern:{name}", "ok": bool(ok), "detail": str(detail)}


def slot(dev):
    return dev.read(dev.u32(spec.GLOBALS) + spec.SLOT, 1)[0]


def initialize(dev):
    """DATA UTILITY 5 INITIALIZE PATTERN on the pattern in RAM, confirmed, back on the main screen; returns the pattern's name.
    No wheel before it: with the pattern switch the wheel only browses, and MENU would confirm instead of opening the menu."""
    menu_cases.go(dev, DATA_UTIL)                       # the ring differs with BLECH's pages in it, so the screen is called by number
    dev.press("menu", 0.5)
    for _ in range(4):
        dev.press("edit_next", 0.3)
    for key, wait in (("menu", 0.6), ("menu", 1.2), ("exit", 0.4), ("exit", 0.4), ("exit", 0.6)):
        dev.press(key, wait)
    name = dev.read(dev.u32(PATTERN_IN_RAM) + 4 + 16, 16)  # the name of the pattern in RAM (as script_menu.s reads its sync group)
    return name.split(b"\0")[0].decode("latin-1")


def case_page(payload, flash):
    for_build(payload)
    out = []
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True)
    menu_cases.goto_du(dev, menu_cases.du_pages().index("SET INIT PATTERN"))
    first = menu_cases.texts_of(dev)[:2], slot(dev)
    out.append(entry("page_factory", first == (("SET INIT PATTERN", "FACTORY"), 0), first))
    dev.turn(7, wait=0.4)
    seven = menu_cases.texts_of(dev)[:2], slot(dev)
    out.append(entry("dial_sets_the_slot", seven == (("SET INIT PATTERN", "7"), 7), seven))
    dev.turn(-20, wait=0.4)
    low = menu_cases.texts_of(dev)[:2], slot(dev)
    dev.turn(127, wait=0.2)
    dev.turn(127, wait=0.2)
    dev.turn(10, wait=0.4)
    high = menu_cases.texts_of(dev)[:2], slot(dev)
    out.append(entry("dial_stops_at_the_ends", low == (("SET INIT PATTERN", "FACTORY"), 0) and high == (("SET INIT PATTERN", "250"), 250),
                     f"down {low}, up {high}"))
    return out


def case_init(payload, flash):
    for_build(payload)
    out = []
    for name, value, held, want in (("template", 7, 0, "TEMPLATE SEVEN"), ("factory", 0, 0, "Init Pattern"),
                                    ("exit", 7, spec.KILL_SWITCH, "Init Pattern")):
        dev = menu_cases.boot(payload, flash, held=held, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
        dev.m.uc.mem_write(spec.BANK + 6 * spec.BLOCK + 16, MARK_NAME)
        dev.m.uc.mem_write(dev.u32(spec.GLOBALS) + spec.SLOT, bytes([value]))
        shown = initialize(dev)
        out.append(entry(f"initialize_{name}", shown == want and not dev.m.asserts, f"INIT PATTERN {value}, EXIT held {bool(held)}: {shown!r}"))
    return out


GROUPS = (case_page, case_init)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    result = cases(payload, load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
