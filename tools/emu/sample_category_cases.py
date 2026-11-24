# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of CATEGORY in SAMPLE EDIT (tools/patch/script_sample_edit.s, docs/messungen/2026-11-21-sample-kategorie.md).

SAMPLE EDIT (screen 38) gets the page CATEGORY behind RENAME: a page of the BLECH menu (level 9) that shows itself as page 3 of
11. Checked: the counter of every page (1/11 to 11/11), also right after coming back from CATEGORY; EDIT left and right between
RENAME, CATEGORY and START POINT, and LOOP START for a sliced mono sample, which the firmware steps to from RENAME; the dial sets
the category byte of the sample's name entry, stops at 0 and 17 and shows the firmware's own texts; EXPORT ALL SAMPLE writes the
category into e2sSample.all; a factory slot with a sample from the card has the page as well; without any sample the page shows
"---" and the dial changes nothing; EXIT goes back to the entry screen (37); with EXIT held at power-on SAMPLE EDIT is Korg's 10
pages. The synth has no SAMPLE EDIT and no hooks for it.

    tools/emu/.venv/bin/python tools/emu/sample_category_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--only case_page,...]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import ht_osc_cases as hc  # noqa: E402
import menu_cases as mc  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import SWITCH_SCREEN  # noqa: E402
import lifetime  # noqa: E402
import parallel  # noqa: E402

IMAGE = 0xC0000000
SITES = (0xC0069BB8, 0xC0069C88)  # slots 4 and 5 of screen 38 (EDIT left and right), `push {r4, r5, r6, lr}` in the firmware
FIRST_WORD = 0xE92D4070
ENTRY, PAGES_SCREEN, MENU = 37, 38, 45
SE_PAGE = 0xC0691278
NAMES = 0xC047B08C
MODEL = 0xC0345A08
MANAGER = 0xC03404C0
CATEGORY_TEXTS = (0xC00A6E06, 0xC00A6E0F, 0xC00A6E1A, 0xC00A6E21, 0xC00A6E29, 0xC00A6E30, 0xC00A6E38, 0xC00A6E41, 0xC00A6E48,
                  0xC00A6E50, 0xC00A6E58, 0xC00A6E5D, 0xC00A6E62, 0xC00A6E68, 0xC00A6E70, 0xC00A6E79, 0xC00A6E80, 0xC00A6E86)
USER, FACTORY = 500, 100          # display 501, and a factory slot (101) a card sample can take on the Sampler (not on Hacktribe)
STEPS_AT = 1168                   # esli: the slice step count; with it a mono sample skips START POINT to LOOP START in SAMPLE EDIT


def has_hooks(payload):
    """True when both slots of screen 38 branch into our code (the Sampler's builds with the BLECH menu)."""
    if synthaddr.is_synth(payload):
        return False
    words = [struct.unpack_from("<I", payload, at - IMAGE)[0] for at in SITES]
    return all(w != FIRST_WORD and w >> 24 == 0xEA for w in words)


def entry(name, ok, detail):
    return {"id": f"samplecat:{name}", "ok": bool(ok), "detail": str(detail)}


def text_at(payload, address):
    raw = payload[address - IMAGE:address - IMAGE + 24]
    return raw.split(b"\0")[0].decode("latin-1")


def sliced(data, slot):
    """e2sSample.all with a slice step count on `slot`'s record."""
    out = bytearray(data)
    at = struct.unpack_from("<I", out, 16 + slot * 4)[0]
    esli = out.index(b"esli", at) + 8
    out[esli + STEPS_AT] = 8
    return bytes(out)


class Edit:
    """A device with a card, on SAMPLE EDIT's first page."""

    def __init__(self, payload, flash, slots=(USER,), data=None, held=0):
        mc.for_build(payload)
        if data is None and slots:
            data = hc.bank(list(slots))
        self.box = hc.Box(payload, flash, held=held, data=data, seconds=12)
        self.dev = self.box.dev
        self.dev.call(SWITCH_SCREEN, ENTRY, 0)
        self.dev.run(0.5)
        self.dev.press("menu")

    def screen(self):
        return self.dev.u32(self.dev.u32(MANAGER) + 0x2C)

    def page(self):
        return self.dev.u32(SE_PAGE)

    def slot(self):
        return self.dev.u32(self.dev.u32(MODEL) + 0x3FC)

    def category(self, slot=None):
        return self.dev.read(NAMES + (self.slot() if slot is None else slot) * 32 + 0x10, 2)

    def shown(self):
        """(screen, the page counter as shown, 1-based, the menu's title and value)."""
        index, total = mc.counter(self.dev)
        return self.screen(), (index + 1, total), mc.texts_of(self.dev)[:2]

    def key(self, name):
        self.dev.press(name, 0.5)
        return self.shown()

    def turn(self, step):
        self.dev.turn(step)
        return mc.texts_of(self.dev)[1]

    def select(self, slot):
        """SELECT SAMPLE's dial until `slot` (it steps only through slots with a sample)."""
        for _ in range(8):
            if self.slot() == slot:
                return True
            self.dev.turn(-1)
        return self.slot() == slot

    def asserts(self):
        return self.dev.m.asserts


def case_page(payload, flash):
    """The counter of every page, EDIT left and right around CATEGORY, EXIT to the entry screen."""
    e = Edit(payload, flash)
    first = e.shown()
    rename = e.key("edit_next")
    category = e.key("edit_next")
    start = e.key("edit_next")
    back = e.key("edit_prev")
    rename_again = (e.key("edit_prev"), e.key("edit_next"))
    walk = [e.key("edit_next")[1] for _ in range(8)]
    last = e.shown()
    wrap = e.key("edit_next")
    out = e.key("exit")
    again = e.key("menu")
    ok_counter = (first[:2] == (PAGES_SCREEN, (1, 11)) and rename[:2] == (PAGES_SCREEN, (2, 11)) and category[1] == (3, 11)
                  and start[:2] == (PAGES_SCREEN, (4, 11)) and back[1] == (3, 11) and rename_again[0][:2] == (PAGES_SCREEN, (2, 11)))
    ok_menu = category[0] == MENU and category[2][0] == "CATEGORY" and back[0] == MENU and rename_again[1][0] == MENU
    ok_walk = walk == [(4, 11), (5, 11), (6, 11), (7, 11), (8, 11), (9, 11), (10, 11), (11, 11)] and last[1] == (11, 11)
    return [entry("counter_and_steps", ok_counter and ok_menu and not e.asserts(),
                  dict(first=first, rename=rename, category=category, start=start, back=back, rename_again=rename_again)),
            entry("pages_4_to_11", ok_walk and wrap[:2] == (PAGES_SCREEN, (1, 11)) and not e.asserts(), dict(walk=walk, last=last, wrap=wrap)),
            entry("exit_to_entry", out[0] == ENTRY and again[:2] == (PAGES_SCREEN, (1, 11)) and not e.asserts(), dict(exit=out, again=again))]


def case_wheel(payload, flash):
    """The dial sets the category byte, stops at 0 and 17, the value is the firmware's text."""
    e = Edit(payload, flash)
    e.key("edit_next")
    e.key("edit_next")
    texts = [text_at(payload, a) for a in CATEGORY_TEXTS]
    start = (mc.texts_of(e.dev)[1], e.category().hex())
    seen = []
    for step in (1, -1, -1, -1, -40, 40, 1, -15):
        seen.append((e.turn(step), e.category()[0], e.category()[1]))
    values = [v for v, _, _ in seen]
    cats = [c for _, c, _ in seen]
    ok = (start == (texts[2], "0200") and cats == [3, 2, 1, 0, 0, 17, 17, 2] and all(v == texts[c] for v, c in zip(values, cats))
          and all(hi == 0 for _, _, hi in seen))
    e.key("edit_next")
    kept = e.category()[0]
    return [entry("dial_sets_category", ok and kept == 2 and not e.asserts(), dict(start=start, seen=seen, kept=kept))]


def case_export(payload, flash):
    """EXPORT ALL SAMPLE writes the category the dial set into the sample's record."""
    e = Edit(payload, flash)
    e.key("edit_next")
    e.key("edit_next")
    e.turn(5)
    set_to = e.category()[0]
    e.key("exit")
    dev = e.dev
    dev.call(SWITCH_SCREEN, 14, 0)
    dev.run(0.4)
    mc.press(dev, "menu")
    for _ in range(10):
        mc.press(dev, "edit_next")
    mc.press(dev, "menu", wait=1.0)
    mc.press(dev, "menu", wait=1.0)
    dev.run(30)
    volume = fat32.Volume(bytes(dev.m.mmc.card.medium.data))
    try:
        data = volume.read(f"/KORG/{hc.folder(payload)}/e2sSample.all")
    finally:
        volume.close()
    at = struct.unpack_from("<I", data, 16 + USER * 4)[0] if data else 0
    written = None
    if at:
        esli = data.index(b"esli", at) + 8
        written = struct.unpack_from("<H", data, esli + 18)[0]
    return [entry("export_writes_category", set_to == 7 and written == 7 and not e.asserts(), dict(set_to=set_to, written=written))]


def case_sliced(payload, flash):
    """A sliced mono sample: the firmware steps from RENAME to LOOP START (page 5), CATEGORY sits in between both ways."""
    e = Edit(payload, flash, data=sliced(hc.bank([USER]), USER))
    sliced_now = e.dev.call(0xC007DE74, e.dev.u32(MODEL))
    rename = e.key("edit_next")
    category = e.key("edit_next")
    loop = (e.key("edit_next"), e.page())
    back = e.key("edit_prev")
    back2 = (e.key("edit_prev"), e.page())
    ok = (sliced_now and rename[1] == (2, 11) and category[0] == MENU and category[1] == (3, 11) and loop[1] == 5
          and loop[0][:2] == (PAGES_SCREEN, (7, 11)) and back[0] == MENU and back2[1] == 1 and back2[0][1] == (2, 11))
    return [entry("sliced_skips_to_loop_start", ok and not e.asserts(), dict(sliced=sliced_now, rename=rename, category=category, loop=loop, back=back, back2=back2))]


def case_factory_slot(payload, flash):
    """A card sample on a factory slot (the Sampler: 101) has the page; on Hacktribe that slot is an oscillator the loader refuses."""
    e = Edit(payload, flash, slots=(FACTORY, USER))
    reached = e.select(FACTORY)
    e.key("edit_next")
    shown = e.key("edit_next")
    value = e.turn(1)
    after = e.category(FACTORY).hex()
    if reached:
        ok = shown[2][0] == "CATEGORY" and value == text_at(payload, CATEGORY_TEXTS[3]) and after == "0300"
    else:
        ok = e.slot() == USER   # Hacktribe: slot 100 is an oscillator, SELECT SAMPLE never gets there
    return [entry("factory_slot_with_card_sample", ok and not e.asserts(), dict(reached=reached, slot=e.slot(), shown=shown, value=value, after=after))]


def case_no_sample(payload, flash):
    """Without any sample on the card the firmware does not open SAMPLE EDIT at all, as without the patch. CATEGORY's own guard
    (a slot without a sample or an oscillator shows "---", the dial changes nothing) is checked by putting an oscillator slot
    (0, SAW) into the model while the page is open: no key gets there, the guard is for whatever the firmware leaves behind."""
    empty = Edit(payload, flash, slots=())
    stays_out = empty.screen() != PAGES_SCREEN
    e = Edit(payload, flash)
    e.key("edit_next")
    e.key("edit_next")
    e.dev.m.uc.mem_write(e.dev.u32(MODEL) + 0x3FC, struct.pack("<I", 0))
    e.dev.run(0.3)
    before = e.dev.read(NAMES, 1000 * 32)
    value = e.turn(3)
    shown = e.shown()
    after = e.dev.read(NAMES, 1000 * 32)
    return [entry("no_sample_no_sample_edit", stays_out and not empty.asserts(), dict(screen=empty.screen())),
            entry("oscillator_shows_dashes", shown[2] == ("CATEGORY", "---") and value == "---" and before == after and not e.asserts(),
                  dict(shown=shown, value=value, changed=before != after))]


def case_without(payload, flash):
    """EXIT held at power-on: Korg's 10 pages, EDIT right on RENAME goes to START POINT."""
    e = Edit(payload, flash, held=mc.KILL)
    first = e.shown()
    rename = e.key("edit_next")
    start = (e.key("edit_next"), e.page())
    ok = first[:2] == (PAGES_SCREEN, (1, 10)) and rename[:2] == (PAGES_SCREEN, (2, 10)) and start[0][:2] == (PAGES_SCREEN, (3, 10)) and start[1] == 2
    return [entry("exit_held_is_stock", ok and not e.asserts(), dict(first=first, rename=rename, start=start))]


GROUPS = (case_page, case_wheel, case_export, case_sliced, case_factory_slot, case_no_sample, case_without)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own device, so they can run side by side."""
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path, nargs="+")
    p.add_argument("--only", help="comma-separated group names (case_page, ...)")
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    if not has_hooks(payload):
        print("no CATEGORY hooks in this copy")
        return 1
    flash = load_flash(a.flash) if a.flash else None
    groups = [g for g in GROUPS if not a.only or g.__name__ in a.only.split(",")]
    result = [e for g in groups for e in g(payload, flash)]
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if all(e["ok"] for e in result) else 1


if __name__ == "__main__":
    sys.exit(main())
