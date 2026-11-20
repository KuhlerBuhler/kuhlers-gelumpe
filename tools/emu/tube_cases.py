# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of BLECH > FEATURES > TUBE, TUBE DRIVE and TUBE ASYM (tools/patch/tube_curve.py, script_menu.s tube_*,
docs/messungen/2026-11-20-roehrenkurve.md).

The DSP is not modelled here; what is checked is what the ARM sends it over the host port: the parameter block of
tools/dsp/tube_model.py block() at PARAM (0xFF803FD8), 20 halfwords in 0xAB writes, each time the TUBE field of byte 7 or
TUBE ASYM changes and never otherwise. The pages sit right before KEY PADS, TUBE ON and OFF, TUBE DRIVE 1 to 7 and TUBE ASYM
0 to 7 act at once, TUBE DRIVE is kept while TUBE is OFF, WRITE keeps the field in byte 7 of a version 4 settings file and
TUBE ASYM in bits 5 to 7 of byte 4 of a version 5 one, and a start with TUBE ON sends its block once. A copy whose DSP program does not carry the routine has no pages and sends nothing, also with TUBE ON in its file.
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


HALVES = tube_model.PARAM_SIZE // 2


def words(step, asym=0):
    """The halfwords of the block of TUBE DRIVE `step` (0: OFF) and TUBE ASYM `asym` as the host port carries them."""
    return struct.unpack(f"<{HALVES}H", tube_model.block(step, asym))


def sent(log):
    """The blocks written to PARAM, in order: the TUBE DRIVE step for TUBE ASYM 0 (0 for OFF), (step, asym) otherwise. The writes
    into the block are laid over a copy of it; each time all its halfwords were written since the last block, the copy is one.
    A write that reaches past the block, or a copy that is no block, is kept as it is."""
    table = {}
    for step in range(8):
        for asym in range(tube_model.ASYM_STEPS):
            table.setdefault(words(step, asym), step if asym == 0 or step == 0 else (step, asym))
    shadow, seen, out = [0] * HALVES, set(), []
    for x in log.xfers:
        if x[0] != 0xAB or not PARAM - 2 * HALVES < x[1] < PARAM + 2 * HALVES:
            continue
        at = (x[1] - PARAM) // 2
        if at < 0 or at + len(x[3]) > HALVES:
            out.append((hex(x[1]), tuple(x[3])))
            continue
        shadow[at:at + len(x[3])] = x[3]
        seen.update(range(at, at + len(x[3])))
        if len(seen) == HALVES:
            out.append(table.get(tuple(shadow), tuple(shadow)))
            seen = set()
    return out


def entry(name, ok, detail):
    return {"id": f"tube:{name}", "ok": bool(ok), "detail": detail}


def flags2(dev):
    return dev.read(mc.MX_FLAGS2, 1)[0]


def asym(dev):
    return dev.read(mc.STATE + mc.M_TUBE_ASYM, 1)[0]


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
    out.append(entry("page_off", mc.TUBE_PAGE and pages[at + 1:at + 4] == ["TUBE DRIVE", "TUBE ASYM", "KEY PADS"]
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

    mc.goto_group(dev, mc.GROUP_FEATURES, at + 2)
    shapes = [mc.texts_of(dev)]
    for turn in (3, 10, -5):
        dev.turn(turn, wait=0.3)
        shapes.append(mc.texts_of(dev))
    out.append(entry("asym_live", shapes == [("TUBE ASYM", v, "") for v in ("0", "3", "7", "2")] and asym(dev) == 2
                     and sent(log) == [4, 6, 7, 1, 0, 3, (3, 3), (3, 7), (3, 2)] and flags2(dev) == 3 << 5,
                     f"{shapes}, writes {sent(log)}, TUBE ASYM {asym(dev)}"))

    mc.press(dev, "write", wait=0.6)
    dev.run(3.0)
    raw = newest_file(dev)
    out.append(entry("write_v5", raw is not None and raw[4] == 5 | 2 << 5 and raw[7] == 3 << 5 and not dev.m.asserts,
                     f"newest file: byte 4 {raw and hex(raw[4])}, byte 7 {raw and hex(raw[7])}"))

    nxt, nlog = started(payload, flash, dev.m.mmc.card.medium.data, wait_of(payload) + 1.0)
    first = sent(nlog)
    shown = []
    for k in range(3):
        mc.goto_group(nxt, mc.GROUP_FEATURES, at + k)
        shown.append(mc.texts_of(nxt))
    out.append(entry("start_sends_once", first == [(3, 2)] and sent(nlog) == [(3, 2)]
                     and shown == [("TUBE", "ON", ""), ("TUBE DRIVE", "3", ""), ("TUBE ASYM", "2", "")]
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
