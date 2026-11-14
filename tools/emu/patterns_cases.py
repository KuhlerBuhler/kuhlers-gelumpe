"""Emulator cases of the Patterns folder (tools/patch/script_patterns.s, plan 2026-11-14-patterns-ordner): EXPORT PATTERN and
EXPORT ALL PATTERN of DATA UTILITY write into KORG/blechtribe/Patterns, a card without that folder gets it, and IMPORT PATTERN's
browser still starts at the card's root (it is Korg's own folder browser, Patterns is reached through it). Red and Hacktribe only;
on the blue the export is not redirected yet, the groups report that and pass.

The groups run inside migrate_cases (GROUPS there), which check.py runs on every BLECH set.

    python3 tools/emu/patterns_cases.py --vsb PATCHED.VSB
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import menu_cases  # noqa: E402
import synthaddr  # noqa: E402

DATA_UTIL = 14                  # the screen of the menu Data Util; MENU enters its list (screen 15) at EXPORT PATTERN
FOLDER = "/KORG/blechtribe/Patterns"
EXPORT_AT = 0xC00371B0          # EXPORT PATTERN's call of the folder string, branched to pat_export_hook by the runtime
SINGLE_SIZE = 0x4100            # a .e2spat: header 0x100 and one pattern
ALL_SIZE = 0x10100 + 250 * 0x4000


def entry(name, ok, detail):
    return {"id": f"patterns:{name}", "ok": bool(ok), "detail": str(detail)}


def redirected(payload):
    """True when EXPORT PATTERN's call is a branch into our code (the runtime of a red or Hacktribe set)."""
    if synthaddr.is_synth(payload):
        return False
    word = int.from_bytes(payload[EXPORT_AT - 0xC0000000:EXPORT_AT - 0xC0000000 + 4], "little")
    return word >> 24 == 0xEA


def files(dev):
    volume = fat32.Volume(bytes(dev.m.mmc.card.medium.data))
    try:
        return {path: e.size for path, e in volume.walk() if not e.attr & 0x10}
    finally:
        volume.close()


def export(payload, flash, keys, seconds):
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True)
    menu_cases.go(dev, DATA_UTIL)
    for key in keys:
        menu_cases.press(dev, key, wait=0.8)
    dev.run(seconds)
    return dev


def case_export(payload, flash):
    if not redirected(payload):
        return [entry("export_not_in_this_build", True, "the blue keeps the firmware's export folder")]
    dev = export(payload, flash, ("menu", "menu", "menu"), 0.5)
    single = files(dev)
    pats = {p: s for p, s in single.items() if p.endswith(".e2spat")}
    out = [entry("export_pattern_writes_into_patterns", list(pats) == [f"{FOLDER}/001_Init Pattern.e2spat"]
                 and list(pats.values()) == [SINGLE_SIZE] and not dev.m.asserts, pats)]
    dev = export(payload, flash, ("menu", "edit_next", "menu", "menu", "menu"), 15)
    every = {p: s for p, s in files(dev).items() if p.endswith(".e2sallpat")}
    out.append(entry("export_all_writes_into_patterns", every == {f"{FOLDER}/electribe_sampler_allpattern.e2sallpat": ALL_SIZE}
                     and not dev.m.asserts, every))
    return out


def case_import_browser(payload, flash):
    """IMPORT PATTERN opens Korg's browser at SD:, one MENU deeper is KORG: the folder Patterns is reached through it."""
    if not redirected(payload):
        return [entry("import_not_in_this_build", True, "the blue keeps the firmware's export folder")]
    import unicorn
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True)
    opened = []

    def hook(uc, address, size, data):
        opened.append(dev.read(uc.reg_read(unicorn.arm_const.UC_ARM_REG_R1), 64).split(b"\0")[0].decode("latin-1"))

    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, hook, begin=0xC009E660, end=0xC009E660)   # f_opendir
    menu_cases.go(dev, DATA_UTIL)
    for key in ("menu", "edit_next", "edit_next", "menu", "menu", "menu"):
        menu_cases.press(dev, key, wait=0.8)
    return [entry("import_browser_starts_at_the_root", opened[:2] == ["SD:", "SD:/KORG"] and not dev.m.asserts, opened)]


GROUPS = (case_export, case_import_browser)


def cases(payload, flash=None):
    return [e for group in GROUPS for e in group(payload, flash)]


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes()[0x100:])
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
