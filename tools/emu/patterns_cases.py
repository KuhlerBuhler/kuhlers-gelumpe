"""Emulator cases of the Patterns folder (tools/patch/script_patterns.s, plan 2026-11-14-patterns-ordner): EXPORT PATTERN and
EXPORT ALL PATTERN of DATA UTILITY write into KORG/blechtribe/Patterns, a card without that folder gets it, and IMPORT PATTERN's
browser still starts at the card's root (it is Korg's own folder browser, Patterns is reached through it). At power-on the backup
in that folder goes into the pattern bank: only the patterns that differ are written to the flash, one without its frame is left
out, a shorter file changes only its own patterns, EXIT held at power-on reads nothing, and the pattern the device opens is the
file's. Red and Hacktribe only; on the blue neither is built yet, the groups report that and pass.

The groups run inside migrate_cases (GROUPS there), which check.py runs on every BLECH set.

    python3 tools/emu/patterns_cases.py --vsb PATCHED.VSB
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
import fat32  # noqa: E402
import menu_cases  # noqa: E402
import synthaddr  # noqa: E402

DATA_UTIL = 14                  # the screen of the menu Data Util; MENU enters its list (screen 15) at EXPORT PATTERN
FOLDER = "/KORG/blechtribe/Patterns"
EXPORT_AT = 0xC00371B0          # EXPORT PATTERN's call of the folder string, branched to pat_export_hook by the runtime
SINGLE_SIZE = 0x4100            # a .e2spat: header 0x100 and one pattern
ALL_SIZE = 0x10100 + 250 * 0x4000
BACKUP = f"{FOLDER}/electribe_sampler_allpattern.e2sallpat"
BANK = 0xC08B2940               # the 250 patterns in RAM, 0x4000 each (0xC004A350), read from the flash at about 80 ms
BLOCK = 0x4000
PATTERN_WRITE = 0xC004C28C      # (_, n, source, copy): the firmware's pattern write, slot and flash
PATTERN_PTR = 0xC033E6A4        # the pattern being edited, its block from +4


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


def backup(bank, count):
    """A .e2sallpat with the first `count` patterns of `bank`: header with KORG, the globals area left empty."""
    return b"KORG" + bytes(0xFC) + bytes(0x10000) + bytes(bank[:count * BLOCK])


def start(payload, files, held=0, seconds=1.5):
    """Power-on with `files` on the card, noting every pattern write; runs past the first pattern selection."""
    dev = menu_cases.Dev(payload, None, held)
    dev.m.adapter = True
    dev.m.insert_card(menu_cases.SDCard(menu_cases.MemoryMedium(menu_cases.card_image(files))))
    writes = []
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, a, s, d: writes.append(uc.reg_read(unicorn.arm_const.UC_ARM_REG_R1)),
                      begin=PATTERN_WRITE, end=PATTERN_WRITE)
    dev.m.run_until(seconds)
    return dev, writes


def changed(bank, patterns):
    out = bytearray(bank)
    for n in patterns:
        out[n * BLOCK + 0x100] ^= 0x55
    return out


def case_boot_load(payload, flash):
    if not redirected(payload):
        return [entry("boot_load_not_in_this_build", True, "the blue reads no backup at power-on")]
    menu_cases.for_build(payload)
    plain, _ = start(payload, menu_cases.CARD_FOLDER, seconds=1.2)
    bank = plain.read(BANK, 250 * BLOCK)
    out = []
    # the whole file: patterns 1, 8 and 250 changed, 4 changed without its end mark (left out)
    every = changed(bank, (0, 7, 249, 3))
    every[3 * BLOCK + 15356:3 * BLOCK + 15360] = b"XXXX"
    dev, writes = start(payload, {**menu_cases.CARD_FOLDER, BACKUP: backup(every, 250)}, seconds=12)
    want = bytearray(every)
    want[3 * BLOCK:4 * BLOCK] = bank[3 * BLOCK:4 * BLOCK]
    ram = dev.read(BANK, 250 * BLOCK)
    edit = dev.read(dev.u32(PATTERN_PTR) + 4, BLOCK)
    out.append(entry("boot_load_writes_only_changed_patterns", writes == [0, 7, 249] and ram == bytes(want) and not dev.m.asserts,
                     f"writes {writes}, bank as the file without pattern 4: {ram == bytes(want)}"))
    out.append(entry("boot_load_opens_the_file_pattern", edit == bytes(every[:BLOCK]), f"edit buffer = pattern 1 of the file: {edit == bytes(every[:BLOCK])}"))
    # a shorter file: 12 patterns, 6 changed; the same file again writes nothing
    short = backup(changed(bank, (5,)), 12)
    dev, writes = start(payload, {**menu_cases.CARD_FOLDER, BACKUP: short}, seconds=2.5)
    out.append(entry("boot_load_short_file", writes == [5] and dev.read(BANK + 12 * BLOCK, 238 * BLOCK) == bank[12 * BLOCK:],
                     f"writes {writes}"))
    same = backup(bank, 12)
    dev, writes = start(payload, {**menu_cases.CARD_FOLDER, BACKUP: same}, seconds=2.5)
    out.append(entry("boot_load_same_file_writes_nothing", writes == [], f"writes {writes}"))
    dev, writes = start(payload, {**menu_cases.CARD_FOLDER, BACKUP: short}, held=menu_cases.KILL, seconds=2.5)
    out.append(entry("boot_load_not_with_exit_held", writes == [] and dev.read(BANK, 250 * BLOCK) == bank, f"writes {writes}"))
    return out


GROUPS = (case_export, case_import_browser, case_boot_load)


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
