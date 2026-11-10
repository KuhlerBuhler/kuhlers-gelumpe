# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the folder copy at the first start (tools/patch/script_migrate.s,
docs/messungen/2026-10-19-ordner-uebernehmen.md).

check.py runs `cases` on every patched copy that carries the BLECH menu. A card with samples in a hacktribe folder and
none in KORG/blechtribe gets the question before the samples load; MENU copies every file and folder (dot files left out) to
KORG/blechtribe, leaves files already there as they are, and the start goes on with the copied samples; EXIT writes nothing;
with both old folders the wheel chooses; a card that already has samples in KORG/blechtribe, and EXIT held at power-on, never
see the question. On the blue Electribe (synth build) the question comes over the main screen when KORG/electribe holds a
pattern backup (*.e2allpat) and KORG/blechtribe holds none (docs/messungen/2026-10-29-blau-ordner-uebernehmen.md,
docs/messungen/2026-11-09-blechtribe-ordner.md); each group has its blue variant. A start without KORG/blechtribe makes it and
its folders (case_folders).

    tools/emu/.venv/bin/python tools/emu/migrate_cases.py cases --patched NEW.VSB [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import menu_cases  # noqa: E402
import sampleset  # noqa: E402
import synthaddr  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

WORK = 0xC0190100               # MG_WORK of the sampler builds
MENU, EXIT = 0x09, 0x0D
KILL = menu_cases.KILL
SAMPLE = sampleset.build(sampleset.sized(3, 48000))
KICK = bytes(range(256)) * 300
OTHER = sampleset.build(sampleset.sized(2, 24000))
FINE_CARD_NS = 2000             # the card interrupt looked at every 2 us instead of every 100 us (case_card_interrupt)


def has_hooks(payload):
    return menu_cases.has_menu(payload)


def entry(name, ok, detail):
    return {"id": f"migrate:{name}", "ok": bool(ok), "detail": str(detail)}


def card(files, leave=None):
    """A card with these files; with `leave`, a filler file takes all but that many bytes of the free space."""
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    for path, data in files.items():
        volume.write(path, data)
    if leave is not None:
        volume.write("FILLER.BIN", bytes(volume.free_bytes() - leave))
    volume.close()
    return SDCard(MemoryMedium(bytearray(image)))


def old(folder):
    return {f"KORG/{folder}/Sample/e2sSample.all": SAMPLE, f"KORG/{folder}/Import/Kick One.wav": KICK,
            f"KORG/{folder}/Import/deep/x.bin": b"hello", f"KORG/{folder}/._junk": b"mac"}


def boot(payload, files, held=0, leave=None):
    dev = Dev(payload, None, held)
    dev.card = card(files, leave)
    dev.m.insert_card(dev.card)
    dev.run(1.0)
    return dev


def state(dev):
    """(active, choice, have, key, phase, bytes)"""
    return struct.unpack("<6I", bytes(dev.m.uc.mem_read(WORK, 24)))


def wait(dev, limit=30.0):
    t = 0.0
    while state(dev)[0] == 1 and t < limit:
        dev.run(0.5)
        t += 0.5
    dev.run(2.0)
    return t


def files_of(dev, folder):
    volume = fat32.Volume(bytes(dev.card.medium.data))
    out = {}
    for name in ("Sample/e2sSample.all", "Import/Kick One.wav", "Import/deep/x.bin", "._junk"):
        try:
            out[name] = volume.read(f"KORG/{folder}/{name}")
        except fat32.FatError:
            pass
    volume.close()
    return out


def blue(payload):
    return synthaddr.is_synth(payload)


ALLPAT = "KORG/electribe/electribe_allpattern.e2allpat"     # where Korg's blue writes EXPORT ALL PATTERN (measured 2026-11-09)
RED_FOLDERS = ("Plugin", "Presets", "Gif", "Doom", "Sample", "System")
BLUE_FOLDERS = ("Plugin", "Gif", "System")


def korg_blue(leave_out=()):
    """What Korg's synth leaves in KORG/electribe: a pattern set, an audio export, its update file and a dot file of a Mac."""
    files = {ALLPAT: b"P" * 5000, "KORG/electribe/Audio/Take One.wav": KICK,
             "KORG/electribe/System/SYSTEM.VSB": b"S" * 3000, "KORG/electribe/._junk": b"mac"}
    return {k: v for k, v in files.items() if k not in leave_out}


BLUE_NAMES = ("electribe_allpattern.e2allpat", "Audio/Take One.wav", "System/SYSTEM.VSB", "._junk")


def blue_files(dev, folder):
    volume = fat32.Volume(bytes(dev.card.medium.data))
    out = {}
    for name in BLUE_NAMES:
        try:
            out[name] = volume.read(f"KORG/{folder}/{name}")
        except fat32.FatError:
            pass
    volume.close()
    return out


def title_shown(dev):
    """Pixels of the question's first line (NEW: BLECHTRIBE, rows 2 to 8 from x 4) on the display."""
    return sum(dev.px(x, y) for y in range(2, 9) for x in range(4, 94))


def blue_copy(payload):
    out = []
    files = korg_blue()
    dev = boot(payload, files)
    asked, shown, fb = state(dev), title_shown(dev), dev.fb()
    dev.press(MENU, 0.5)
    took = wait(dev)
    copied = blue_files(dev, "blechtribe")
    want = {k.split("/", 2)[2]: v for k, v in files.items() if not k.endswith("._junk")}
    out.append(entry("blue_menu_copies_the_folder", asked[:3] == (1, 2, 4) and shown and copied == want and state(dev)[0] == 0
                     and state(dev)[4] == 2 and dev.screen()["number"] == 1 and dev.fb() != fb
                     and blue_files(dev, "electribe").keys() == {*want, "._junk"} and not dev.m.asserts,
                     f"asked {asked[:3]} over screen {dev.screen()['number']}, {shown} pixels of the title; after MENU {took} s: copied "
                     f"{sorted(copied)}, phase {state(dev)[4]}, {state(dev)[5]} bytes, the firmware's screen back {dev.fb() != fb}; "
                     f"the old folder kept"))
    skip = boot(payload, files)
    fb = skip.fb()
    skip.press(EXIT, 0.5)
    wait(skip)
    out.append(entry("blue_exit_writes_nothing", blue_files(skip, "blechtribe") == {} and state(skip)[0] == 0 and skip.fb() != fb
                     and skip.screen()["number"] == 1 and not skip.m.asserts,
                     f"after EXIT: blechtribe {sorted(blue_files(skip, 'blechtribe'))}, state {state(skip)[0]}, the firmware's screen "
                     f"back {skip.fb() != fb}"))
    return out


def blue_keys(payload):
    """The wheel and the other keys do nothing while the question is up."""
    dev = boot(payload, korg_blue())
    dev.turn(1, wait=0.3)
    dev.press("write", 0.3)
    after = state(dev)
    dev.press(EXIT, 0.5)
    wait(dev)
    return [entry("blue_other_keys_taken", after[:3] == (1, 2, 4) and after[4] == 0 and blue_files(dev, "blechtribe") == {}
                  and state(dev)[0] == 0 and not dev.m.asserts, f"after a turn and WRITE: {after[:5]}, after EXIT {state(dev)[:1]}")]


def blue_none(payload):
    out = []
    there = boot(payload, {**korg_blue(), "KORG/blechtribe/electribe_allpattern.e2allpat": b"mine"})
    out.append(entry("blue_blechtribe_backup_there_no_question", state(there)[0] != 1 and not there.m.asserts, f"state {state(there)}"))
    plugin = boot(payload, {**korg_blue(), "KORG/blechtribe/Plugin/e2sPlugin.all": b"plugins"})
    out.append(entry("blue_blechtribe_without_backup_asks", state(plugin)[:3] == (1, 2, 4) and not plugin.m.asserts,
                     f"blechtribe with a plugin only: state {state(plugin)[:3]}"))
    held = boot(payload, korg_blue(), held=KILL)
    out.append(entry("blue_exit_held_no_question", state(held)[0] != 1 and blue_files(held, "blechtribe") == {} and not held.m.asserts,
                     f"EXIT held at power-on: state {state(held)}"))
    empty = boot(payload, {})
    out.append(entry("blue_no_old_folder_no_question", state(empty)[0] != 1 and not empty.m.asserts, f"state {state(empty)}"))
    return out


def blue_full(payload):
    out = []
    full = boot(payload, korg_blue(), leave=64 * 1024)
    full.press(MENU, 0.5)
    wait(full)
    out.append(entry("blue_card_full_copies_nothing", state(full)[4] == 4 and blue_files(full, "blechtribe") == {}
                     and full.screen()["number"] == 1 and not full.m.asserts,
                     f"64 KiB free: phase {state(full)[4]} (4 card full), blechtribe {sorted(blue_files(full, 'blechtribe'))}"))
    room = boot(payload, korg_blue(), leave=1024 * 1024)
    room.press(MENU, 0.5)
    wait(room)
    out.append(entry("blue_enough_room_copies", state(room)[4] == 2 and len(blue_files(room, "blechtribe")) == 3 and not room.m.asserts,
                     f"1 MiB free: phase {state(room)[4]}, copied {sorted(blue_files(room, 'blechtribe'))}"))
    return out


def blue_update_only(payload):
    """The question hangs on the pattern backup alone: only it in KORG/electribe asks, every other file without it does not
    (Korg's update file, an audio export; the blue never looks for a sample file)."""
    out = []
    dev = boot(payload, {ALLPAT: b"P" * 5000})
    asked = state(dev)[:3]
    dev.press(MENU, 0.5)
    wait(dev)
    copied = blue_files(dev, "blechtribe")
    out.append(entry("blue_backup_only_asks_and_copies", asked == (1, 2, 4) and copied == {"electribe_allpattern.e2allpat": b"P" * 5000}
                     and not dev.m.asserts, f"asked {asked}, copied {sorted(copied)}"))
    none = boot(payload, {**korg_blue(leave_out=(ALLPAT,)), "KORG/electribe/._x.e2allpat": b"mac",
                          "KORG/electribe/Sample/e2sSample.all": SAMPLE})
    out.append(entry("blue_without_backup_no_question", state(none)[0] != 1 and blue_files(none, "blechtribe") == {}
                     and not none.m.asserts, f"update file, audio, a dot file named .e2allpat, a sample file: state {state(none)[:3]}"))
    return out


def case_copy(payload, flash):
    if blue(payload):
        return blue_copy(payload)
    out = []
    dev = boot(payload, old("hacktribe"))
    asked, screen = state(dev), dev.screen()["number"]
    dev.press(MENU, 0.5)
    took = wait(dev)
    copied = files_of(dev, "blechtribe")
    want = {"Sample/e2sSample.all": SAMPLE, "Import/Kick One.wav": KICK, "Import/deep/x.bin": b"hello"}
    out.append(entry("menu_copies_the_folder", asked[:3] == (1, 0, 1) and screen == 0 and copied == want and state(dev)[4] == 2
                     and dev.screen()["number"] == 1 and files_of(dev, "hacktribe").keys() == {*want, "._junk"} and not dev.m.asserts,
                     f"asked {asked[:3]} on screen {screen}; after MENU {took} s: copied {sorted(copied)}, phase {state(dev)[4]}, "
                     f"{state(dev)[5]} bytes, then screen {dev.screen()['number']}; the old folder kept"))
    skip = boot(payload, old("hacktribe"))
    skip.press(EXIT, 0.5)
    wait(skip)
    out.append(entry("exit_writes_nothing", files_of(skip, "blechtribe") == {} and skip.screen()["number"] == 1 and not skip.m.asserts,
                     f"after EXIT: blechtribe {sorted(files_of(skip, 'blechtribe'))}, screen {skip.screen()['number']}"))
    return out


def case_choose(payload, flash):
    if blue(payload):
        return blue_keys(payload)
    out = []
    both = {**old("hacktribe"), "KORG/electribe sampler/Sample/e2sSample.all": OTHER}
    dev = boot(payload, both)
    first = state(dev)[:3]
    dev.turn(1, wait=0.3)
    chosen = state(dev)[1]
    dev.press(MENU, 0.5)
    wait(dev)
    copied = files_of(dev, "blechtribe")
    out.append(entry("wheel_chooses_the_other_folder", first == (1, 0, 3) and chosen == 1
                     and copied.get("Sample/e2sSample.all") == both["KORG/electribe sampler/Sample/e2sSample.all"]
                     and "Import/Kick One.wav" not in copied and not dev.m.asserts,
                     f"both folders: {first}, after a turn choice {chosen}, copied {sorted(copied)}"))
    return out


def case_none(payload, flash):
    if blue(payload):
        return blue_none(payload)
    out = []
    has = boot(payload, {**old("hacktribe"), "KORG/blechtribe/Sample/e2sSample.all": SAMPLE})
    out.append(entry("blechtribe_there_no_question", state(has)[0] != 1 and not has.m.asserts, f"state {state(has)}"))
    held = boot(payload, old("hacktribe"), held=KILL)
    out.append(entry("exit_held_no_question", state(held)[0] != 1 and files_of(held, "blechtribe") == {} and not held.m.asserts,
                     f"EXIT held at power-on: state {state(held)}"))
    empty = boot(payload, {})
    out.append(entry("no_old_folder_no_question", state(empty)[0] != 1 and not empty.m.asserts, f"state {state(empty)}"))
    return out


def case_full(payload, flash):
    """Not room enough for the old folder: CARD FULL, nothing written, the start goes on; with just enough room it copies."""
    if blue(payload):
        return blue_full(payload)
    out = []
    full = boot(payload, old("hacktribe"), leave=64 * 1024)
    full.press(MENU, 0.5)
    wait(full)
    out.append(entry("card_full_copies_nothing", state(full)[4] == 4 and files_of(full, "blechtribe") == {} and full.screen()["number"] == 1
                     and not full.m.asserts, f"64 KiB free for {len(SAMPLE) + len(KICK)} bytes: phase {state(full)[4]} (4 card full), "
                     f"blechtribe {sorted(files_of(full, 'blechtribe'))}, screen {full.screen()['number']}"))
    room = boot(payload, old("hacktribe"), leave=1024 * 1024)
    room.press(MENU, 0.5)
    wait(room)
    out.append(entry("enough_room_copies", state(room)[4] == 2 and len(files_of(room, "blechtribe")) == 3 and not room.m.asserts,
                     f"1 MiB free: phase {state(room)[4]}, copied {sorted(files_of(room, 'blechtribe'))}"))
    return out


def case_existing(payload, flash):
    """KORG/blechtribe already there with a plugin and a file of the same name, but without samples: the question comes, the copy
    goes into the folder and leaves both files as they were. An old folder without samples and without a pattern backup asks
    nothing."""
    if blue(payload):
        return blue_update_only(payload)
    out = []
    mine = b"my own kick"
    there = {**old("hacktribe"), "KORG/blechtribe/Plugin/e2sPlugin.all": b"plugins", "KORG/blechtribe/Import/Kick One.wav": mine}
    dev = boot(payload, there)
    asked = state(dev)[:3]
    dev.press(MENU, 0.5)
    wait(dev)
    copied = files_of(dev, "blechtribe")
    volume = fat32.Volume(bytes(dev.card.medium.data))
    plugin = volume.read("KORG/blechtribe/Plugin/e2sPlugin.all")
    volume.close()
    out.append(entry("folder_without_samples_asks_and_keeps_files", asked == (1, 0, 1) and state(dev)[4] == 2
                     and copied.get("Sample/e2sSample.all") == SAMPLE and copied.get("Import/Kick One.wav") == mine
                     and copied.get("Import/deep/x.bin") == b"hello" and plugin == b"plugins" and dev.screen()["number"] == 1
                     and not dev.m.asserts,
                     f"blechtribe with a plugin, no samples: asked {asked}; after MENU phase {state(dev)[4]}, samples copied "
                     f"{copied.get('Sample/e2sSample.all') == SAMPLE}, own Kick One.wav kept {copied.get('Import/Kick One.wav') == mine}, "
                     f"plugin kept {plugin == b'plugins'}"))
    bare = {**{k: v for k, v in old("hacktribe").items() if not k.endswith("e2sSample.all")},
            "KORG/hacktribe/x.e2allpat": b"P", "KORG/hacktribe/._x.e2sallpat": b"mac", "KORG/hacktribe/renamed.e2sallpat": b"P"}
    none = after_start(boot(payload, bare))
    out.append(entry("old_folder_without_samples_or_backup_no_question", state(none)[0] != 1 and not none.m.asserts,
                     f"no samples; a blue backup, a dot file and a renamed file ending in .e2sallpat: state {state(none)}"))
    return out


def case_card_interrupt(payload, flash):
    """The copy with the card interrupt looked at every 2 us: the controller raises it once per 64-byte chunk. Raised again for
    a chunk the firmware is still taking, the interrupt came after the stop command (CMD12) that follows the last chunk, and the
    handler, which reads MMCST0, took the command's answer away: assertion AM180xMMSDCardController.cpp line 228, seen in the
    app on SOFTWARE UPDATE. Every 100 us that is rare, every 2 us it comes within the first second of the copy."""
    files = korg_blue() if blue(payload) else old("hacktribe")
    dev = boot(payload, files)
    dev.m.mmc_irq_ns = FINE_CARD_NS          # after the kept boot, which restores the machine's own value
    dev.press(MENU, 0.5)
    took = wait(dev)
    copied = blue_files(dev, "blechtribe") if blue(payload) else files_of(dev, "blechtribe")
    want = len(files) - 1                    # all but the dot file
    return [entry("copy_with_the_card_interrupt_every_2_us", state(dev)[4] == 2 and len(copied) == want and not dev.m.asserts,
                  f"after MENU {took} s: phase {state(dev)[4]}, copied {len(copied)} of {want} files, asserts {dev.m.asserts}")]


def folders_of(dev):
    volume = fat32.Volume(bytes(dev.card.medium.data))
    try:
        return {e.name for e in volume.listdir("KORG/blechtribe") if e.is_dir and not e.name.startswith(".")}
    except fat32.FatError:
        return None
    finally:
        volume.close()


def after_start(dev):
    dev.run(2.0)
    return dev


def case_folders(payload, flash):
    """A start without KORG/blechtribe makes it and the folders BLECH uses in it; a KORG/blechtribe that is there gets the folders of
    that list it lacks (many make the folder by hand before they have the firmware), and what is in it stays; not with EXIT held at
    power-on. On the red and Hacktribe the folders come in the first frame after the start, so each card runs to the main screen."""
    want = set(BLUE_FOLDERS if blue(payload) else RED_FOLDERS)
    out = []
    fresh = after_start(boot(payload, {}))
    got = folders_of(fresh)
    out.append(entry("fresh_card_gets_the_folders", got == want and state(fresh)[0] != 1 and not fresh.m.asserts,
                     f"empty card: KORG/blechtribe holds {sorted(got) if got is not None else None}, want {sorted(want)}"))
    bare = after_start(boot(payload, {"KORG/blechtribe/readme.txt": b"hello"}))
    got = folders_of(bare)
    out.append(entry("folder_without_subfolders_gets_them", got == want and state(bare)[0] != 1 and not bare.m.asserts,
                     f"blechtribe with a file only: now {sorted(got) if got is not None else None}, want {sorted(want)}"))
    some = after_start(boot(payload, {"KORG/blechtribe/Plugin/mine.blech": b"mine", "KORG/blechtribe/gif/own.gif": b"gif"}))
    volume = fat32.Volume(bytes(some.card.medium.data))
    kept = volume.read("KORG/blechtribe/Plugin/mine.blech"), volume.read("KORG/blechtribe/gif/own.gif")
    volume.close()
    got = folders_of(some)
    out.append(entry("folders_there_left_alone", got == (want - {"Gif"}) | {"gif"} and kept == (b"mine", b"gif") and not some.m.asserts,
                     f"blechtribe with Plugin and gif (lower case): now {sorted(got) if got is not None else None}, own files kept "
                     f"{kept == (b'mine', b'gif')}"))
    held = after_start(boot(payload, {}, held=KILL))
    out.append(entry("exit_held_makes_no_folders", folders_of(held) is None and not held.m.asserts,
                     f"EXIT held at power-on: KORG/blechtribe {folders_of(held)}"))
    held = after_start(boot(payload, {"KORG/blechtribe/readme.txt": b"hello"}, held=KILL))
    out.append(entry("exit_held_adds_no_folders", folders_of(held) == set() and not held.m.asserts,
                     f"EXIT held at power-on, blechtribe with a file only: folders {folders_of(held)}"))
    return out


RED_PAT = "electribe_sampler_allpattern.e2sallpat"     # what the red and Hacktribe write with EXPORT ALL PATTERN, in the folder itself


def pattern_of(dev, folder):
    volume = fat32.Volume(bytes(dev.card.medium.data))
    try:
        return {e.name: volume.read(f"KORG/{folder}/{e.name}") for e in volume.listdir(f"KORG/{folder}")
                if not e.is_dir and e.name.lower().endswith(".e2sallpat")}
    except fat32.FatError:
        return {}
    finally:
        volume.close()


def case_pattern(payload, flash):
    """The red and Hacktribe ask for the pattern backup too (the name EXPORT ALL PATTERN gives it, upper or lower case): an old folder
    with it while KORG/blechtribe has none asks even without a sample file, and the copy takes it with the samples; the backup in
    KORG/blechtribe asks nothing more. The backup alone asks in the card hook, after the sample loader, so those cards run on."""
    if blue(payload):
        return []
    out = []
    pat = b"P" * 5000
    only = after_start(boot(payload, {f"KORG/hacktribe/{RED_PAT}": pat}))
    asked = state(only)[:3]
    only.press(MENU, 0.5)
    wait(only)
    got = pattern_of(only, "blechtribe")
    out.append(entry("pattern_only_asks_and_copies", asked == (1, 0, 1) and got == {RED_PAT: pat} and state(only)[4] == 2
                     and not only.m.asserts, f"only a backup in hacktribe: asked {asked}, copied {sorted(got)}"))
    both = boot(payload, {**old("hacktribe"), f"KORG/hacktribe/{RED_PAT}": pat})
    asked = state(both)[:3]
    both.press(MENU, 0.5)
    wait(both)
    got, files = pattern_of(both, "blechtribe"), files_of(both, "blechtribe")
    out.append(entry("pattern_and_samples_both_copied", asked == (1, 0, 1) and got == {RED_PAT: pat}
                     and files.get("Sample/e2sSample.all") == SAMPLE and not both.m.asserts,
                     f"asked {asked}, copied backup {sorted(got)}, samples {files.get('Sample/e2sSample.all') == SAMPLE}"))
    lacks = after_start(boot(payload, {**old("electribe sampler"), f"KORG/electribe sampler/{RED_PAT}": pat,
                                       "KORG/blechtribe/Sample/e2sSample.all": OTHER}))
    asked = state(lacks)[:3]
    lacks.press(MENU, 0.5)
    wait(lacks)
    got, files = pattern_of(lacks, "blechtribe"), files_of(lacks, "blechtribe")
    out.append(entry("samples_there_pattern_missing_asks", asked == (1, 1, 2) and got == {RED_PAT: pat}
                     and files.get("Sample/e2sSample.all") == OTHER and not lacks.m.asserts,
                     f"blechtribe with samples, no backup: asked {asked}, copied backup {sorted(got)}, own samples kept "
                     f"{files.get('Sample/e2sSample.all') == OTHER}"))
    skip = boot(payload, {**old("hacktribe"), f"KORG/hacktribe/{RED_PAT}": pat})
    skip.press(EXIT, 0.5)
    wait(skip)
    after_start(skip)
    out.append(entry("exit_asks_once_a_start", state(skip)[0] != 1 and pattern_of(skip, "blechtribe") == {} and not skip.m.asserts,
                     f"samples and backup, EXIT on the question: then state {state(skip)[:3]}, blechtribe backup {sorted(pattern_of(skip, 'blechtribe'))}"))
    there = after_start(boot(payload, {f"KORG/hacktribe/{RED_PAT}": pat, f"KORG/blechtribe/{RED_PAT.upper()}": b"mine"}))
    out.append(entry("pattern_in_blechtribe_no_question", state(there)[0] != 1 and not there.m.asserts,
                     f"a backup in both: state {state(there)[:3]}"))
    return out


GROUPS = (case_copy, case_choose, case_none, case_full, case_existing, case_card_interrupt, case_folders, case_pattern)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own device, so they can run side by side."""
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
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases",))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    entries = group_entries(payload, None, a.only) if a.only is not None else cases(payload, None)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
