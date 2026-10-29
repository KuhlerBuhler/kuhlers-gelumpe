"""Emulator cases of the last-pattern patch (tools/patch/last_pattern.py): the pattern selected before switching off is the
one the device opens at the next power-on; without a kept number it opens 001; with EXIT held at power-on it opens 001 and
keeps the number for the next start; with BLECH > FEATURES > LAST PATTERN OFF in the settings file it opens 001 and keeps the number
for a start with ON.

    python3 tools/emu/last_pattern_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import last_pattern as spec  # noqa: E402
import synthaddr  # noqa: E402
import menu_cases  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
POWER_KEY = [6, 1, 0, 0, 0]


def for_build(payload):
    """The patch module's places for the build of this image (the synth has its own, data/synth-map/)."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hooks(payload):
    """True when the start function's pattern goes through our code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.BOOT_SITE - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= (spec.BOOT_SITE + 8 + (off << 2)) & 0xFFFFFFFF < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"lastpattern:{name}", "ok": bool(ok), "detail": str(detail)}


def boot(payload, flash, held=0, files=None):
    """Booted to the main screen; every pattern selection's number is kept in dev.chosen (r5 two words behind the hooked site, where
    the selection passes it on as mov r1, r5)."""
    import unicorn
    from unicorn import arm_const
    for_build(payload)
    dev = Dev(payload, flash, held)
    dev.chosen = []
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: dev.chosen.append(uc.reg_read(arm_const.UC_ARM_REG_R5)),
                      begin=spec.SELECT_SITE + 8, end=spec.SELECT_SITE + 8)
    dev.m.adapter = False
    dev.m.insert_card(SDCard(MemoryMedium(menu_cases.card_image({**menu_cases.CARD_FOLDER, **(files or {})}))))
    dev.run(2.0)
    return dev


def selected(dev):
    """The pattern the firmware selected last, 0 to 249: r5 at the selection's mov r1, r5, behind the patch's code, which may have
    swapped in the kept number."""
    return dev.chosen[-1] if dev.chosen else 0


def switch_off(dev):
    """The power key, then the device runs until the power hold falls; returns the flash it kept."""
    dev.m.send(POWER_KEY)
    for _ in range(60):
        if not dev.m.powered:
            break
        dev.run(0.1)
    return bytes(dev.m.flash.mem) if not dev.m.powered else None


def case_kept(payload, flash):
    """001 without a kept number; the wheel to 006, off, on: 006; the wheel to 004, off, on with EXIT held: 001, then on: 004."""
    out = []
    dev = boot(payload, flash)
    out.append(entry("fresh", selected(dev) == 0 or flash, f"first start opens pattern {selected(dev) + 1}"))
    start = selected(dev)
    dev.turn(5, wait=1.0)
    chosen = selected(dev)
    kept = switch_off(dev)
    out.append(entry("off", kept is not None and chosen == start + 5, f"wheel +5 selects {chosen + 1}, switched off: {kept is not None}"))
    if kept is None:
        return out
    dev = boot(payload, kept)
    out.append(entry("reopen", selected(dev) == chosen, f"next start opens {selected(dev) + 1}, selected before was {chosen + 1}"))
    dev.turn(-2, wait=1.0)
    chosen = selected(dev)
    kept = switch_off(dev)
    if kept is None:
        out.append(entry("exit", False, "the second switch-off did not end"))
        return out
    dev = boot(payload, kept, held=spec.KILL_SWITCH)
    out.append(entry("exit", selected(dev) == 0, f"with EXIT held the start opens {selected(dev) + 1}"))
    kept = switch_off(dev)
    if kept is None:
        out.append(entry("after_exit", False, "the switch-off after the EXIT start did not end"))
        return out
    dev = boot(payload, kept)
    out.append(entry("after_exit", selected(dev) == chosen, f"after the EXIT start the next start opens {selected(dev) + 1}, kept was {chosen + 1}"))
    return out


def settings(off):
    """A settings file on the card: LAST PATTERN OFF (bit 3 of byte 5) or ON (the bit clear, METER LOUD RAINBOW set beside it)."""
    path = menu_cases.SETTINGS_PATHS[0]
    return {path: menu_cases.settings_file_v3(2, 3, menu_cases.look_word(), extras=menu_cases.LP_OFF if off else 1)}


def case_switch(payload, flash):
    """The wheel to 004, off; on with LAST PATTERN OFF in the settings file: 001, the setting word 0; off, on with ON in the file: 004."""
    out = []
    dev = boot(payload, flash)
    dev.turn(3, wait=1.0)
    chosen = selected(dev)
    kept = switch_off(dev)
    if kept is None:
        out.append(entry("switch_off", False, "the switch-off did not end"))
        return out
    dev = boot(payload, kept, files=settings(True))
    word = dev.u32(menu_cases.LP_SETTING)
    out.append(entry("switch_off", selected(dev) == 0 and word == 0 and chosen > 0 and not dev.m.asserts,
                     f"LAST PATTERN OFF: the start opens {selected(dev) + 1}, kept was {chosen + 1}, setting word {word:#x}"))
    kept = switch_off(dev)
    if kept is None:
        out.append(entry("switch_on", False, "the switch-off after the OFF start did not end"))
        return out
    dev = boot(payload, kept, files=settings(False))
    word = dev.u32(menu_cases.LP_SETTING)
    out.append(entry("switch_on", selected(dev) == chosen and word == 1,
                     f"LAST PATTERN ON again: the start opens {selected(dev) + 1}, kept was {chosen + 1}, setting word {word:#x}"))
    return out


GROUPS = (case_kept, case_switch)


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
