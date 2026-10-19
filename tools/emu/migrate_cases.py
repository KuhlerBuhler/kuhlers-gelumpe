# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the folder copy at the first start (tools/patch/script_migrate.s,
docs/messungen/2026-10-19-ordner-uebernehmen.md).

check.py runs `cases` on every patched sampler copy that carries the BLECH menu. A card with a hacktribe folder and no
blechtribe folder gets the question before the samples load; MENU copies every file and folder (dot files left out) to
KORG/blechtribe and the start goes on with the copied samples; EXIT writes nothing; with both old folders the wheel chooses;
a card that already has KORG/blechtribe, and EXIT held at power-on, never see the question.

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

WORK = 0xC0190000               # MG_WORK of the sampler builds
MENU, EXIT = 0x09, 0x0D
KILL = menu_cases.KILL
SAMPLE = sampleset.build(sampleset.sized(3, 48000))
KICK = bytes(range(256)) * 300
OTHER = sampleset.build(sampleset.sized(2, 24000))


def has_hooks(payload):
    return menu_cases.has_menu(payload) and not synthaddr.is_synth(payload)


def entry(name, ok, detail):
    return {"id": f"migrate:{name}", "ok": bool(ok), "detail": str(detail)}


def card(files):
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    for path, data in files.items():
        volume.write(path, data)
    volume.close()
    return SDCard(MemoryMedium(bytearray(image)))


def old(folder):
    return {f"KORG/{folder}/Sample/e2sSample.all": SAMPLE, f"KORG/{folder}/Import/Kick One.wav": KICK,
            f"KORG/{folder}/Import/deep/x.bin": b"hello", f"KORG/{folder}/._junk": b"mac"}


def boot(payload, files, held=0):
    dev = Dev(payload, None, held)
    dev.card = card(files)
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


def case_copy(payload, flash):
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
    out = []
    has = boot(payload, {**old("hacktribe"), "KORG/blechtribe/Sample/e2sSample.all": SAMPLE})
    out.append(entry("blechtribe_there_no_question", state(has)[0] != 1 and not has.m.asserts, f"state {state(has)}"))
    held = boot(payload, old("hacktribe"), held=KILL)
    out.append(entry("exit_held_no_question", state(held)[0] != 1 and files_of(held, "blechtribe") == {} and not held.m.asserts,
                     f"EXIT held at power-on: state {state(held)}"))
    empty = boot(payload, {})
    out.append(entry("no_old_folder_no_question", state(empty)[0] != 1 and not empty.m.asserts, f"state {state(empty)}"))
    return out


GROUPS = (case_copy, case_choose, case_none)


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
