# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of BLECH > FEATURES > TUBE and TUBE DRIVE (tools/patch/tube_curve.py, script_menu.s tube_*,
docs/messungen/2026-11-20-roehrenkurve.md).

The DSP is not modelled here; what is checked is what the ARM sends it over the host port: the parameter block of
tools/dsp/tube_model.py block() at 0xFF803FE0, 16 halfwords in one 0xAB write, each time the TUBE field of byte 7 changes
and never otherwise. The pages sit right before KEY PADS, TUBE ON and OFF and TUBE DRIVE 1 to 7 act at once, TUBE DRIVE is
kept while TUBE is OFF, WRITE keeps the field in byte 7 of a version 4 settings file, and a start with TUBE ON sends its
block once. A copy whose DSP program does not carry the routine has no pages and sends nothing, also with TUBE ON in its file.
What the curve does to the sound is checked in the QEMU DSP core (tools/dsp/tube_qemu.py).

    tools/emu/.venv/bin/python tools/emu/tube_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(ROOT / "tools" / "dsp"))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases as mc  # noqa: E402
import synthaddr  # noqa: E402
import tube_model  # noqa: E402
from machine import load_flash  # noqa: E402
from mfx_cases import DspLog  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

PARAM = tube_model.PARAM
KORG_CALLER = {False: 0x135C, True: 0x1348}      # the caller's P0.L without the patch: Korg's clipper, red and blue


def words(step):
    """The halfwords of the block of TUBE DRIVE `step` (0: OFF) as the host port carries them."""
    return struct.unpack("<16H", tube_model.block(step))


def sent(log):
    """The TUBE DRIVE steps of the blocks written to PARAM, in order; a write that is no whole block is kept as it is."""
    table = {words(step): step for step in range(8)}
    return [table.get(tuple(x[3]), (x[2], tuple(x[3]))) for x in log.xfers if x[0] == 0xAB and x[1] == PARAM]


def entry(name, ok, detail):
    return {"id": f"tube:{name}", "ok": bool(ok), "detail": detail}


def flags2(dev):
    return dev.read(mc.MX_FLAGS2, 1)[0]


def newest_file(dev):
    raws = [r for r in mc.settings_raw(dev.m.mmc.card.medium.data).values() if len(r) >= 24 and r[:4] == b"GSET"]
    return max(raws, key=lambda r: struct.unpack_from("<I", r, 8)[0]) if raws else None


def started(payload, flash, image, seconds):
    """A device started from a card image with the host port logged from power-on."""
    dev = Dev(payload, flash, 0)
    dev.m.adapter = True
    log = DspLog(dev.m)
    dev.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    dev.run(seconds)
    return dev, log


def wait_of(payload):
    return 10.0 if synthaddr.is_synth(payload) else 1.2


def case_pages(payload, flash):
    """The pages, the live writes, WRITE and the next start."""
    if not mc.has_menu(payload) or not mc.has_tube(payload):
        return [entry("pages", False, "this copy has no BLECH menu or no tube-curve patch")]
    out = []
    dev = mc.boot(payload, flash, files=mc.CARD_FOLDER, adapter=True, seconds=wait_of(payload))
    log = DspLog(dev.m)
    pages = mc.feature_pages()
    at = pages.index("TUBE")
    mc.goto_group(dev, mc.GROUP_FEATURES, at)
    page = mc.texts_of(dev), mc.counter(dev)
    out.append(entry("page_off", mc.TUBE_PAGE and pages[at + 1:at + 3] == ["TUBE DRIVE", "KEY PADS"]
                     and page == (("TUBE", "OFF", ""), (at, mc.feature_count())) and flags2(dev) == 0 and sent(log) == [],
                     f"{page}, byte 7 {flags2(dev):#x}, writes {sent(log)}, pages {pages}"))

    dev.turn(1, wait=0.3)
    on = mc.texts_of(dev), flags2(dev), sent(log)
    out.append(entry("on_sends_default", on == (("TUBE", "ON", ""), 4 << 5, [4]), f"{on}"))

    mc.goto_group(dev, mc.GROUP_FEATURES, at + 1)
    steps = [mc.texts_of(dev)]
    for turn in (2, 5, -10):
        dev.turn(turn, wait=0.3)
        steps.append(mc.texts_of(dev))
    out.append(entry("drive_live", [t[1] for t in steps] == ["4", "6", "7", "1"] and steps[0][0] == "TUBE DRIVE"
                     and sent(log) == [4, 6, 7, 1] and flags2(dev) == 1 << 5, f"{steps}, writes {sent(log)}, byte 7 {flags2(dev):#x}"))

    mc.goto_group(dev, mc.GROUP_FEATURES, at)
    dev.turn(-1, wait=0.3)
    off = mc.texts_of(dev), flags2(dev)
    mc.goto_group(dev, mc.GROUP_FEATURES, at + 1)
    dev.turn(2, wait=0.3)
    kept = mc.texts_of(dev), flags2(dev)
    mc.goto_group(dev, mc.GROUP_FEATURES, at)
    dev.turn(1, wait=0.3)
    again = mc.texts_of(dev), flags2(dev)
    out.append(entry("off_keeps_drive", off == (("TUBE", "OFF", ""), 0) and kept == (("TUBE DRIVE", "3", ""), 0)
                     and again == (("TUBE", "ON", ""), 3 << 5) and sent(log) == [4, 6, 7, 1, 0, 3] and not dev.m.asserts,
                     f"OFF {off}, DRIVE while OFF {kept}, ON again {again}, writes {sent(log)}"))

    mc.press(dev, "write", wait=0.6)
    dev.run(3.0)
    raw = newest_file(dev)
    out.append(entry("write_byte_7", raw is not None and raw[4] == 4 and raw[7] == 3 << 5,
                     f"newest file: version {raw and raw[4]}, byte 7 {raw and hex(raw[7])}"))

    nxt, nlog = started(payload, flash, dev.m.mmc.card.medium.data, wait_of(payload) + 1.0)
    first = sent(nlog)
    mc.goto_group(nxt, mc.GROUP_FEATURES, at)
    shown = [mc.texts_of(nxt)]
    mc.goto_group(nxt, mc.GROUP_FEATURES, at + 1)
    shown.append(mc.texts_of(nxt))
    out.append(entry("start_sends_once", first == [3] and sent(nlog) == [3] and shown == [("TUBE", "ON", ""), ("TUBE DRIVE", "3", "")]
                     and not nxt.m.asserts, f"writes at the start {first}, after the pages {sent(nlog)}, pages {shown}"))
    return out


def case_without_patch(payload, flash):
    """The same runtime in a copy whose DSP program has Korg's clipper: no pages, no write, also with TUBE ON in the file."""
    if not mc.has_menu(payload):
        return [entry("without_patch", False, "this copy has no BLECH menu")]
    plain = bytearray(payload)
    synth = synthaddr.is_synth(payload)
    mark = 0xC01176D6 if synth else 0xC0131F90
    struct.pack_into("<H", plain, mark - mc.IMAGE, KORG_CALLER[synth])
    plain = bytes(plain)
    files = {**mc.CARD_FOLDER, mc.SETTINGS_PATHS[0]: mc.settings_file_v4(2, 3, mc.look_word(), 5 << 5)}
    image = mc.card_image(files)
    mc.boot(plain, flash, card=False, seconds=0.1)      # sets the build and the page flags of this copy for feature_pages()
    pages = mc.feature_pages()
    dev, log = started(plain, flash, image, wait_of(plain) + 1.0)
    mc.goto_group(dev, mc.GROUP_FEATURES, len(pages) - 3)
    shown = mc.texts_of(dev), mc.counter(dev)
    return [entry("without_patch", not mc.TUBE_PAGE and "TUBE" not in pages and shown == (("KEY PADS", "ON", ""), (len(pages) - 3, len(pages)))
                  and flags2(dev) == 5 << 5 and sent(log) == [] and not dev.m.asserts,
                  f"pages {pages}, {shown}, byte 7 {flags2(dev):#x}, writes {sent(log)}")]


GROUPS = (case_pages, case_without_patch)


def has_hooks(payload):
    """True when the copy has the BLECH menu and the tube-curve patch."""
    return mc.has_menu(payload) and mc.has_tube(payload)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    result = cases(payload, load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
