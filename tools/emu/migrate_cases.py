# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the folder copy at the first start (tools/patch/script_migrate.s,
docs/messungen/2026-10-19-ordner-uebernehmen.md).

check.py runs `cases` on every patched copy that carries the BLECH menu. A card with samples in a hacktribe folder and
none in KORG/blechtribe gets the question before the samples load; MENU copies every file and folder (dot files left out) to
KORG/blechtribe, leaves files already there as they are, and the start goes on with the copied samples; EXIT writes nothing;
with both old folders the wheel chooses; a card that already has samples in KORG/blechtribe, and EXIT held at power-on, never
see the question. On the blue Electribe (synth build) the question comes over the main screen when KORG/electribe is there and
KORG/blechtribe is not (docs/messungen/2026-10-29-blau-ordner-uebernehmen.md); each group has its blue variant.

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


def korg_blue(leave_out=()):
    """What Korg's synth leaves in KORG/electribe: a pattern set, an audio export, its update file and a dot file of a Mac."""
    files = {"KORG/electribe/PatternSet/all.e2allpat": b"P" * 5000, "KORG/electribe/Audio/Take One.wav": KICK,
             "KORG/electribe/System/SYSTEM.VSB": b"S" * 3000, "KORG/electribe/._junk": b"mac"}
    return {k: v for k, v in files.items() if k not in leave_out}


BLUE_NAMES = ("PatternSet/all.e2allpat", "Audio/Take One.wav", "System/SYSTEM.VSB", "._junk")


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
    there = boot(payload, {**korg_blue(), "KORG/blechtribe/Plugin/e2sPlugin.all": b"plugins"})
    out.append(entry("blue_blechtribe_there_no_question", state(there)[0] != 1 and not there.m.asserts, f"state {state(there)}"))
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
    """Nothing but Korg's update file in KORG/electribe (the way BLECH came onto the blue) asks too: the copy brings
    System/SYSTEM.VSB to KORG/blechtribe, where BLECH's own update looks."""
    dev = boot(payload, korg_blue(leave_out=("KORG/electribe/PatternSet/all.e2allpat", "KORG/electribe/Audio/Take One.wav",
                                             "KORG/electribe/._junk")))
    asked = state(dev)[:3]
    dev.press(MENU, 0.5)
    wait(dev)
    copied = blue_files(dev, "blechtribe")
    return [entry("blue_update_file_only_asks_and_copies", asked == (1, 2, 4) and copied == {"System/SYSTEM.VSB": b"S" * 3000}
                  and not dev.m.asserts, f"asked {asked}, copied {sorted(copied)}")]


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
    goes into the folder and leaves both files as they were. An old folder without samples asks nothing."""
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
    bare = {k: v for k, v in old("hacktribe").items() if not k.endswith("e2sSample.all")}
    none = boot(payload, bare)
    out.append(entry("old_folder_without_samples_no_question", state(none)[0] != 1 and not none.m.asserts, f"state {state(none)}"))
    return out


GROUPS = (case_copy, case_choose, case_none, case_full, case_existing)


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
