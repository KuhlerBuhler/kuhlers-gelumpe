# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the page BLECH > DEV MODE (tools/patch/script_menu.s, kind 56; docs/messungen/2026-11-14-dev-mode-sperrbereiche.md).

check.py runs `cases` on every patched copy with the BLECH menu. On the Sampler the row DEV MODE sits in front of VERSION and starts
OFF; the dial up writes DEV_FLAG's magic and INFO reports FLAG_DEV_ON, the dial down clears it; WRITE saves nothing (card and the flash
settings sectors stay as they were). With it on, a BLECH WRITE into the image changes a menu text the LCD then shows; with it off the
same write is refused. The synth has no row.

    tools/emu/.venv/bin/python tools/emu/dev_mode_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import blech_sysex as spec  # noqa: E402
import menu_cases as mc  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402

IMAGE = 0xC0000000
FLASH_SETTINGS = (0x7FD000, 0x7FF000)   # the two sectors of the BLECH settings in the flash (#521)
TITLE = b"DEV MODE\0"


def has_page(payload):
    """True when the copy has the BLECH menu; the cases pick Sampler or synth themselves."""
    return mc.has_menu(payload)


def entry(name, ok, detail):
    return {"id": f"devmode:{name}", "ok": bool(ok), "detail": str(detail)}


def flag(dev):
    return struct.unpack("<I", bytes(dev.m.uc.mem_read(spec.DEV_FLAG, 4)))[0]


def stored(dev):
    """What a save would change: the card's image and the flash settings sectors."""
    card = getattr(getattr(dev.m.mmc, "card", None), "medium", None)
    return (bytes(card.data) if card is not None else b""), bytes(dev.m.flash.mem[FLASH_SETTINGS[0]:FLASH_SETTINGS[1]])


def title_at(payload):
    """The image address of the page's title text, the bytes a hot patch changes in case_hottext."""
    at = bytes(payload).find(TITLE)
    return None if at < 0 else IMAGE + at


def case_page(payload, flash):
    """The row in front of VERSION: OFF after the start, the dial up ON (magic, INFO bit), down OFF (FF); WRITE stores nothing."""
    if synthaddr.is_synth(payload) or not mc.has_menu(payload):
        return []
    from sysex_cases import Link
    out = []
    dev = mc.boot(payload, flash)
    lk = Link(dev)
    mc.goto_top(dev, mc.LIST_DEV)
    start = (mc.state(dev, mc.S_PAGE), mc.texts_of(dev), flag(dev))
    out.append(entry("starts_off", start == (mc.LIST_DEV, ("DEV MODE", "OFF", ""), 0xFFFFFFFF) and mc.LIST_VERSION == mc.LIST_DEV + 1,
                     f"page, texts, DEV_FLAG after the start {start}"))
    before = stored(dev)
    dev.turn(1, wait=0.3)
    on = (mc.texts_of(dev), flag(dev))
    info = lk.info()
    out.append(entry("dial_up_turns_it_on", on == (("DEV MODE", "ON", ""), spec.DEV_MAGIC) and info and info["flags"] & spec.FLAG_DEV_ON,
                     f"texts, DEV_FLAG {on}, INFO flags {info and hex(info['flags'])}"))
    mc.press(dev, "write", wait=0.6)
    mc.press(dev, "menu", wait=0.4)
    kept = stored(dev) == before and flag(dev) == spec.DEV_MAGIC
    out.append(entry("write_saves_nothing", kept, "card image and flash settings sectors byte for byte as before WRITE and ENTER, still on"))
    dev.turn(-1, wait=0.3)
    off = (mc.texts_of(dev), flag(dev))
    info = lk.info()
    out.append(entry("dial_down_turns_it_off", off == (("DEV MODE", "OFF", ""), 0xFFFFFFFF) and info and not info["flags"] & spec.FLAG_DEV_ON
                     and stored(dev) == before and not dev.m.asserts, f"texts, DEV_FLAG {off}, INFO flags {info and hex(info['flags'])}"))
    return out


def case_absent(payload, flash):
    """The synth's list has no row DEV MODE and its runtime no DEV_FLAG."""
    if not synthaddr.is_synth(payload) or not mc.has_menu(payload):
        return []
    from tools.patch import script_hooks
    dev = mc.boot(payload, flash)
    mc.goto_top(dev, 0)
    titles = []
    for _ in range(mc.LIST_COUNT):
        titles.append(mc.texts_of(dev)[0])
        mc.press(dev, "edit_next")
    zero = script_hooks.runtime_profile("synth").actions["DEV_FLAG"] == 0
    return [entry("synth_has_no_row", "DEV MODE" not in titles and mc.LIST_DEV is None and zero and not dev.m.asserts,
                  f"rows {titles}, DEV_FLAG in the synth runtime 0: {zero}")]


def case_hottext(payload, flash):
    """ON via the dial, a BLECH WRITE of the page's title in the image: the LCD shows the new text; OFF, the same write is refused."""
    if synthaddr.is_synth(payload) or not mc.has_menu(payload):
        return []
    from sysex_cases import Link, OK, REFUSED
    at = title_at(payload)
    if at is None:
        return [entry("hot_text", False, "no DEV MODE text in the image")]
    dev = mc.boot(payload, flash)
    lk = Link(dev)
    mc.goto_top(dev, mc.LIST_DEV)
    dev.turn(1, wait=0.3)
    begin, data = lk.write(at, b"HOT MODE\0")
    mc.goto_top(dev, mc.LIST_VERSION)
    mc.goto_top(dev, mc.LIST_DEV)
    shown = mc.texts_of(dev)
    ok_on = bool(begin and begin["status"] == OK and data and data["status"] == OK) and shown[:2] == ("HOT MODE", "ON")
    dev.turn(-1, wait=0.3)
    refused, _ = lk.write(at, b"DEV MODE\0")
    still = bytes(dev.m.uc.mem_read(at, len(TITLE)))
    ok_off = bool(refused and refused["status"] == REFUSED) and still == b"HOT MODE\0"
    return [entry("hot_text_on", ok_on and not dev.m.asserts, f"title at {at:#x}: BEGIN {begin and begin['status']}, DATA {data and data['status']}, LCD {shown}"),
            entry("hot_text_off_refused", ok_off and not dev.m.asserts, f"off: BEGIN {refused and refused['status']}, RAM {still!r}")]


GROUPS = (case_page, case_absent, case_hottext)


def group_entries(payload, flash, i):
    try:
        return GROUPS[i](payload, flash)
    except Exception as e:   # a case that breaks is a red entry, not a lost run
        return [entry(GROUPS[i].__name__, False, f"{type(e).__name__}: {e}")]


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases",))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    entries = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
