# SPDX-License-Identifier: GPL-2.0-only
"""The same SYSTEM.VSB in every folder of the card, in the emulator (docs/messungen/2026-11-08-rettung-alle-ordner.md).

    tools/emu/.venv/bin/python tools/emu/rescue_folders_probe.py --korg-red RED.VSB --korg-blue BLUE.VSB \
        --hacktribe HACKTRIBE.VSB --blech BLECH-HACKTRIBE.VSB --blech-stock BLECH-KORG-RED.VSB \
        --blech-blue BLECH-SYNTH.VSB [--only NAME] [--shots DIR]

The Rettung page (data/rescue.mjs, `folder:all:*`) tells someone who does not know what runs to put the SYSTEM.VSB into
Korg's folder of the colour, `KORG/hacktribe/System/` and `KORG/blechtribe/System/`, and says that does not hurt because
the update reads only the folder of the running firmware. This tool checks that for every firmware that can run, on a
blank flash of its colour, each on mains power with DATA UTILITY, SOFTWARE UPDATE:

  empty   an empty card: which files the firmware asks for
  own     the file only in the folder of the running firmware
  all     the same file in all three folders (the page's advice)
  others  the file in the two other folders only

`all` has to do byte for byte what `own` does (the same flash after), `others` must not erase or program anything. A start
with the file in all three folders must reach the main screen without one flash command (copies do not start an update).
All files are the user's own and stay outside the repository; the tool writes nothing to disk except pictures (--shots).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

from hacktribe_blue_probe import FIRMWARE, device_flash, head_of, with_head  # noqa: E402

KORG = {"red": "electribe sampler", "blue": "electribe"}
FOLDERS = {colour: [korg, "hacktribe", "blechtribe"] for colour, korg in KORG.items()}


def card(folders, vsb):
    return {f"/KORG/{f}/System/SYSTEM.VSB": vsb for f in folders}


def runners(f):
    """(name, colour, running VSB, the folder it is expected to read, [(file name, file on the card)])."""
    korg_red, korg_blue = f["korg_red"], f["korg_blue"]
    blue_sampler = with_head(korg_blue, "sampler")
    blech_s = with_head(f["blech"], "sampler")
    return [
        ("korg-red", "red", korg_red, "electribe sampler", [("korg-red", korg_red), ("blech", blech_s)]),
        ("hacktribe-red", "red", f["hacktribe"], "hacktribe", [("korg-red", korg_red), ("blech", blech_s)]),
        ("blech-red", "red", f["blech"], "blechtribe", [("korg-red", korg_red), ("blech", blech_s)]),
        ("blech-stock-red", "red", f["blech_stock"], "blechtribe", [("korg-red", korg_red), ("blech", blech_s)]),
        ("korg-blue", "blue", korg_blue, "electribe", [("korg-blue", korg_blue), ("korg-blue-sampler-head", blue_sampler)]),
        ("blech-blue", "blue", f["blech_blue"], "blechtribe", [("korg-blue", korg_blue), ("korg-blue-sampler-head", blue_sampler)]),
        ("hacktribe-blue", "blue", f["hacktribe"], "hacktribe", [("korg-blue", korg_blue), ("korg-blue-sampler-head", blue_sampler)]),
        ("blech-ht-blue", "blue", f["blech"], "blechtribe", [("korg-blue", korg_blue), ("korg-blue-sampler-head", blue_sampler)]),
    ]


def asks_to_copy(running, files):
    """BLECH's synth build asks at start to copy KORG/electribe when KORG/blechtribe is not there (script_migrate.s, MG_BLUE)."""
    names = {p.split("/")[2] for p in files}
    return head_of(running) == "blue" and "electribe" in names and "blechtribe" not in names


def update(tag, running, flash, files, shots, blech=False):
    """SOFTWARE UPDATE with `files` on the card, driven like synth_update_probe.run_update; a short report and the flash after.
    The copy question of BLECH on the blue is answered with EXIT, which writes nothing (docs/messungen/2026-10-29-blau-ordner-uebernehmen.md)."""
    from synth_update_probe import Rig, boot_to_main
    rig = Rig(running[0x100:], flash, files, shots, tag)
    main = boot_to_main(rig)
    question = blech and asks_to_copy(running, files)
    if question:
        rig.shot("copy-question")
        rig.press("exit", 1.0)
    log = []
    rig.to_software_update(log)
    base = rig.flash_busy()
    opened_before = len(rig.opened)
    rig.press("menu", 1.5)
    quiet, spent, presses, last = 0, 0, 0, base
    while spent < 240 and quiet < 6:
        rig.run(1.0)
        spent += 1
        now = rig.flash_busy()
        quiet, last = (quiet + 1 if now == last else 0), now
        if now == base and presses < 4 and spent >= 2:
            rig.press("menu", 1.5)
            presses += 1
    rig.run(2.0)
    end = rig.shot("end")
    after = bytes(rig.m.flash.mem)
    return {"booted": main, "copy_question_answered_exit": question, "opened": [p for p in rig.opened[opened_before:] if p.upper().endswith(".VSB")],
            "erases": len(rig.erases) - base[0], "programs": len(rig.programs) - base[1],
            "final_screen": end["screen"], "asserts": list(rig.m.asserts)}, after


def start(tag, running, flash, files, shots):
    """A start from `flash` with `files` on the card: main screen, flash commands, .VSB files opened."""
    from synth_update_probe import Rig, boot_to_main
    rig = Rig(running[0x100:], flash, files, shots, tag)
    main = boot_to_main(rig)
    rig.run(3.0)
    return {"main_screen": main, "erases": len(rig.erases), "programs": len(rig.programs),
            "opened_vsb": [p for p in rig.opened if p.upper().endswith(".VSB")]}


def probe(name, colour, running, own, files, blank, shots):
    blech = name.startswith("blech")
    from synth_update_probe import probe_empty_card
    flash = device_flash(running, blank)
    out = {"runner": name, "colour": colour, "empty": [p for p in probe_empty_card(running[0x100:], flash, shots)["opened"]
                                                       if p.upper().endswith(".VSB")]}
    others = [f for f in FOLDERS[colour] if f != own]
    out["start_with_all_copies"] = start(f"{name}-start", running, flash, card(FOLDERS[colour], files[0][1]), shots)
    out["files"] = []
    for label, vsb in files:
        r = {"file": label, "head": head_of(vsb)}
        r["own"], own_after = update(f"{name}-{label}-own", running, flash, card([own], vsb), shots, blech)
        r["all"], all_after = update(f"{name}-{label}-all", running, flash, card(FOLDERS[colour], vsb), shots, blech)
        r["others"], others_after = update(f"{name}-{label}-others", running, flash, card(others, vsb), shots, blech)
        r["written"] = r["own"]["programs"] > 0 and own_after[FIRMWARE[0]:FIRMWARE[1]] == vsb[0x100:]
        r["rest_unchanged"] = own_after[:FIRMWARE[0]] == flash[:FIRMWARE[0]] and own_after[FIRMWARE[1]:] == flash[FIRMWARE[1]:]
        r["all_equals_own"] = all_after == own_after and r["all"]["erases"] == r["own"]["erases"]
        r["others_untouched"] = others_after == flash and r["others"]["erases"] == 0 and r["others"]["programs"] == 0
        out["files"].append(r)
        print(json.dumps({"runner": name, **r}), file=sys.stderr, flush=True)
    return out


def verdict(result):
    """The page's claim holds for a runner: copies change nothing, a wrong folder is never written from, a start stays quiet."""
    s = result["start_with_all_copies"]
    return (s["main_screen"] and s["erases"] == 0 and s["programs"] == 0
            and all(r["all_equals_own"] and r["others_untouched"] for r in result["files"]))


def main():
    import machine
    from synth_update_probe import inside_repo
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for arg in ("korg-red", "korg-blue", "hacktribe", "blech", "blech-stock", "blech-blue"):
        p.add_argument(f"--{arg}", required=True, type=Path)
    p.add_argument("--only", action="append", help="only these runners, e.g. korg-red or blech-blue")
    p.add_argument("--shots", type=Path, help="folder for pictures of the display (outside the repository)")
    a = p.parse_args()
    if a.shots:
        if inside_repo(a.shots):
            raise SystemExit("the pictures show Korg's screens: write them outside the repository")
        a.shots.mkdir(parents=True, exist_ok=True)
    files = {k: getattr(a, k).read_bytes() for k in ("korg_red", "korg_blue", "hacktribe", "blech", "blech_stock", "blech_blue")}
    if any(len(v) != 0x200100 for v in files.values()):
        raise SystemExit("six VSBs of 0x200100 bytes")
    out = []
    for name, colour, running, own, card_files in runners(files):
        if a.only and name not in a.only:
            continue
        r = probe(name, colour, running, own, card_files, bytes(machine.hardware_flash(colour)), a.shots)
        r["ok"] = verdict(r)
        out.append(r)
    print(json.dumps(out, indent=1))
    return 0 if all(r["ok"] for r in out) else 1


if __name__ == "__main__":
    sys.exit(main())
