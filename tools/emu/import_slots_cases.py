# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the import-slots patch (tools/patch/import_slots.py, docs/messungen/2026-11-16-import-werks-slots.md).

A card with one mono WAV in its root. DATA UTILITY > IMPORT SAMPLE picks it, then the destination selector is turned:
from the lowest number the import takes (19 in Korg's build, 275 in Hacktribe's) one step down lands on 999 and one step
up from 999 on the lowest number again. The import onto the lowest number, a factory slot, puts the sample's name into
that slot. The import writes nothing to the card (the firmware writes e2sSample.all only with EXPORT ALL SAMPLE); a start
from an e2sSample.all with samples for the lowest number and the next one puts them into those factory slots.

    tools/emu/.venv/bin/python tools/emu/import_slots_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import import_slots as spec  # noqa: E402
import menu_cases as mc  # noqa: E402
import sample_error_cases as se  # noqa: E402
from highram_watch import KEYS, plain_wav  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
DEST = 0xC00F9CCC               # the destination selector's number (the slot plus one)
NAMES = 0xC047B080              # the slot records, 0x20 each, the name from +12
IMPORT_SCREEN = 39              # the screen of IMPORT SAMPLE's file browser and destination
DATA_UTILITY = 14
WAV = "/Kick.wav"


def has_hooks(payload):
    """True when the selector's range test is ours (sub r3, r1, #imm instead of cmp r1, #500)."""
    word = struct.unpack_from("<I", payload, spec.SITE - IMAGE)[0]
    return word & 0xFFFFF000 == 0xE2413000


def lowest(payload):
    raw = b"\0" * 0x100 + payload
    return spec.LOWEST[spec.build_of(raw)]


def entry(name, ok, detail):
    return {"id": f"import-slots:{name}", "ok": bool(ok), "detail": str(detail)}


def name_of(dev, slot):
    return dev.read(NAMES + slot * 0x20 + 12, 16).split(b"\0")[0].decode("latin-1")


def dest(dev):
    return dev.u32(DEST)


def card():
    files = {WAV: plain_wav(2000), **mc.CARD_FOLDER}
    return mc.card_image(files)


def boot(payload, flash, image):
    dev = Dev(payload, flash, 0)
    dev.m.adapter = True
    dev.m.insert_card(SDCard(MemoryMedium(image)))
    dev.run(1.2)
    for _ in range(40):
        if dev.m.screen() == 1:
            break
        dev.run(0.5)
    dev.run(2)
    mc.keep_awake(dev)
    return dev


def destination_screen(dev):
    """DATA UTILITY > IMPORT SAMPLE, the WAV picked: the destination selector is up."""
    mc.go(dev, DATA_UTILITY)
    dev.press(KEYS["menu"], 0.5)
    for _ in range(8):
        dev.press(KEYS["right"], 0.25)
    dev.press(KEYS["menu"], 1.5)
    dev.turn(1, 0.8)
    dev.press(KEYS["menu"], 1.0)
    for _ in range(30):
        dev.run(0.5)
        if dev.m.screen() != IMPORT_SCREEN:
            break
    dev.run(1.0)


def step_to(dev, number):
    """Turn the selector until it shows `number` (at most 1000 steps), one detent at a time."""
    for _ in range(1000):
        now = dest(dev)
        if now == number:
            return True
        dev.turn(-1 if now > number else 1, 0.05)
    return dest(dev) == number


def case_range(payload, flash):
    low = lowest(payload)
    dev = boot(payload, flash, card())
    destination_screen(dev)
    first = dest(dev)
    reached = step_to(dev, low)
    dev.turn(-1, 0.3)
    below = dest(dev)
    dev.turn(1, 0.3)
    back = dest(dev)
    step_to(dev, low + 1)
    dev.turn(-1, 0.3)
    down = dest(dev)
    return [entry("startwert", 1 <= first <= spec.TOP, f"the selector opens on {first}"),
            entry("untergrenze-erreichbar", reached, f"turned down to {low}: {dest(dev) if not reached else low}"),
            entry("unter-untergrenze-999", below == spec.TOP, f"one step below {low}: {below}"),
            entry("ueber-999-untergrenze", back == low, f"one step above {spec.TOP}: {back}"),
            entry("schritt-auf-untergrenze", down == low, f"one step down from {low + 1}: {down}"),
            entry("keine-assertion", not dev.m.asserts, dev.m.asserts)]


def case_import(payload, flash):
    low = lowest(payload)
    slot = low - 1
    dev = boot(payload, flash, card())
    before = name_of(dev, slot)
    destination_screen(dev)
    reached = step_to(dev, low)
    dev.press(KEYS["menu"], 1.0)
    for _ in range(40):
        dev.run(1.0)
        if name_of(dev, slot) == "Kick":
            break
    dev.run(3.0)
    after = name_of(dev, slot)
    return [entry("werks-slot-gewaehlt", reached, f"selector on {dest(dev)}"),
            entry("import-auf-werks-slot", after == "Kick" and before != "Kick", f"slot {low}: {before!r} before, {after!r} after"),
            entry("keine-assertion", not dev.m.asserts, dev.m.asserts)]


def case_restore(payload, flash):
    """The import writes nothing to the card (EXPORT ALL SAMPLE writes e2sSample.all); a start from an e2sSample.all with a
    sample for the lowest number and one for the next puts both into their factory slots, without an error window."""
    low = lowest(payload)
    slots = [low - 1, low]
    b = se.Boot(payload, None, {s: se.ok(s) for s in slots})
    names = [name_of(b.dev, s) for s in slots]
    want = [f"s{s + 1}" for s in slots]
    return [entry("start-laedt-werks-slots", names == want and not b.window() and not b.dev.m.asserts,
                  f"slots {low} and {low + 1}: {names}, window {b.window()}")]


GROUPS = (case_range, case_import, case_restore)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    if not has_hooks(payload):
        raise SystemExit("this copy does not have the import-slots patch")
    out = [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]
    print(json.dumps(out, indent=1))
    sys.exit(0 if all(e["ok"] for e in out) else 1)


if __name__ == "__main__":
    main()
