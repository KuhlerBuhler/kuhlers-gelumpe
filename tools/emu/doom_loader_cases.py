"""Emulator cases of the Doom loader patch (tools/patch/doom_loader.py, tools/doom/bootstrap.c): SHIFT + TAP at power-on starts Doom
only when doom.bin and doom.wad are on the card; without them, or without a card, the sampler starts as without the keys.

    python3 tools/emu/doom_loader_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "doom"))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import build_bootstrap  # noqa: E402
import menu_cases  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
SITE, BASE, SHARED = build_bootstrap.SITE, build_bootstrap.BASE, build_bootstrap.LAYOUT["shared"]
SHIFT_TAP = 0x408
MAIN = 1                                 # the screen number of the main screen
FOLDER = "/KORG/blechtribe/Doom/"
PROGRAM = ROOT / "third_party/doom"
STAGE_VERIFIED = 3                       # tools/doom/runtime_abi.h: doom.bin read and its SHA-256 matched


def has_hooks(payload):
    """True when the start function's call behind the sample-file query goes into the loader."""
    word = struct.unpack_from("<I", payload, SITE - IMAGE)[0]
    return word >> 24 == 0xEB and (SITE + 8 + ((((word & 0xFFFFFF) ^ 0x800000) - 0x800000) << 2)) & 0xFFFFFFFF == BASE


def entry(name, ok, detail):
    return {"id": f"doom:{name}", "ok": bool(ok), "detail": str(detail)}


def boot(payload, flash, files=None, card=True, held=SHIFT_TAP, seconds=2.0):
    dev = Dev(payload, flash, held)
    dev.m.adapter = False
    if card:
        dev.m.insert_card(SDCard(MemoryMedium(menu_cases.card_image({**menu_cases.CARD_FOLDER, **(files or {})}))))
    dev.run(seconds)
    return dev


def stage(dev):
    """magic, stage and error of the loader's shared state (tools/doom/runtime_abi.h); all 0 when the loader let the start go on."""
    magic, _, at, error = struct.unpack("<4I", dev.read(SHARED, 16))
    return magic, at, error


def normal_start(dev, keys=True):
    """The main screen, no assertion; with the keys the loader cleared its state and gave up, without them it never ran (FF)."""
    left = (0, 0, 0) if keys else (0xFFFFFFFF,) * 3
    return dev.m.screen() == MAIN and dev.m.powered and stage(dev) == left and not dev.m.asserts


def case_without_files(payload, flash):
    """SHIFT + TAP with a card without the Doom folder, with doom.bin but no doom.wad, and without a card: the sampler starts."""
    out = []
    bin_only = {FOLDER + "doom.bin": (PROGRAM / "doom.bin").read_bytes()}
    for name, dev in (("no_files", boot(payload, flash)), ("no_wad", boot(payload, flash, bin_only)),
                      ("no_card", boot(payload, flash, card=False))):
        out.append(entry(name, normal_start(dev), f"screen {dev.m.screen()}, powered {dev.m.powered}, loader state {stage(dev)}, asserts {dev.m.asserts}"))
    return out


def case_with_files(payload, flash):
    """SHIFT + TAP with doom.bin and doom.wad on the card: the loader checks doom.bin and jumps into the engine; without the keys the
    same card starts the sampler."""
    files = {FOLDER + "doom.bin": (PROGRAM / "doom.bin").read_bytes(), FOLDER + "doom.wad": (PROGRAM / "doom.wad").read_bytes()}
    dev = boot(payload, flash, files)
    magic, at, error = stage(dev)
    out = [entry("with_files", magic == 0x4D4F4F44 and at >= STAGE_VERIFIED and error == 0 and dev.m.screen() != MAIN,
                 f"loader state {stage(dev)}, screen {dev.m.screen()}")]
    plain = boot(payload, flash, files, held=0)
    out.append(entry("with_files_no_keys", normal_start(plain, keys=False), f"screen {plain.m.screen()}, loader state {stage(plain)}"))
    return out


GROUPS = (case_without_files, case_with_files)


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
