# SPDX-License-Identifier: GPL-2.0-only
"""Every update path of BLECH + Hacktribe on the blue Electribe 2 in the emulator (docs/ideen/65-blech-hacktribe-blau.md).

    tools/emu/.venv/bin/python tools/emu/hacktribe_blue_probe.py --korg-blue SYSTEM.VSB --hacktribe HACKTRIBE.VSB \
        --blech BLECH-HACKTRIBE.VSB [--flash IMAGE.bin] [--shots DIR]

All files are the user's own and stay outside the repository. `--hacktribe` and `--blech` may carry either head; the tool
writes both heads itself (`with_head`). Without `--flash` the device starts from a blank flash of the blue hardware
(machine.hardware_flash): the blue's user-data mark, no PCM bank.

The paths, each SOFTWARE UPDATE on mains power with only that file on the card, in the folder the running firmware
asks for (measured with an empty card first):

  korg-blue    Korg's blue firmware runs: BLECH + Hacktribe with the blue head is written, with the Sampler head refused.
  hacktribe    Hacktribe runs on the blue: BLECH + Hacktribe with the Sampler head is written, with the blue head refused.
  blech        BLECH + Hacktribe runs: itself again with the Sampler head is written, with the blue head refused.
  way back     BLECH + Hacktribe runs: Korg's blue with the Sampler head is written and starts, unchanged it is refused.

A written file must end with the new image in the firmware area, nothing else of the flash changed, and a restart to
the main screen; a refused one with no erase and no program command.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

HEADS = {"sampler": (0x53, 0x24), "blue": (0x00, 0x23)}   # bytes 0x12 and 0x2E (Hacktribe's e2-header.py)
FIRMWARE = (0x20000, 0x220000)


def with_head(vsb, head):
    """The VSB with the head of the Sampler or of the blue: the two bytes the updaters look at, nothing else."""
    out = bytearray(vsb)
    out[0x12], out[0x2E] = HEADS[head]
    return bytes(out)


def head_of(vsb):
    return next((name for name, (a, b) in HEADS.items() if vsb[0x12] == a and vsb[0x2E] == b), None)


def paths(korg_blue, hacktribe, blech):
    """(name, running VSB, file on the card, written?) of every path, in the order they build on each other's flash."""
    return [
        ("korg-blue: BLECH blue head", korg_blue, with_head(blech, "blue"), True),
        ("korg-blue: BLECH Sampler head", korg_blue, with_head(blech, "sampler"), False),
        ("hacktribe: BLECH Sampler head", hacktribe, with_head(blech, "sampler"), True),
        ("hacktribe: BLECH blue head", hacktribe, with_head(blech, "blue"), False),
        ("blech: BLECH Sampler head", blech, with_head(blech, "sampler"), True),
        ("blech: BLECH blue head", blech, with_head(blech, "blue"), False),
        ("way back: Korg blue Sampler head", blech, with_head(korg_blue, "sampler"), True),
        ("way back: Korg blue unchanged", blech, korg_blue, False),
    ]


def verdict(report, written):
    """Whether one update did what the path expects, from run_update's report and the reboot after it."""
    commands = report["erase_commands"]["count"] + report["program_commands"]["count"]
    if not written:
        return commands == 0 and not report["asserts"]
    return (commands > 0 and report["firmware_area_is_the_new_file"] and report["user_area_identical"]
            and report["below_the_firmware_identical"] and report["bank_identical"] and not report["asserts"]
            and report.get("reboot", {}).get("main_screen") is True)


def device_flash(running, flash):
    """The flash of a blue device that runs `running`: its image in the firmware area, after one boot."""
    from synth_update_probe import Rig, boot_to_main
    mem = bytearray(flash)
    mem[FIRMWARE[0]:FIRMWARE[1]] = running[0x100:]
    rig = Rig(running[0x100:], bytes(mem), {}, None, "prime")
    boot_to_main(rig)
    return bytes(rig.m.flash.mem)


def run(korg_blue, hacktribe, blech, flash, shots=None, only=None):
    from synth_update_probe import probe_empty_card, reboot, run_update, update_folder
    out = []
    for i, (name, running, card, written) in enumerate(paths(korg_blue, hacktribe, blech)):
        if only and not any(name.startswith(o) for o in only):
            continue
        start = device_flash(running, flash)
        looked = probe_empty_card(running[0x100:], start, shots)
        folder = update_folder(looked["opened"])
        if folder is None:
            raise SystemExit(f"{name}: the firmware asked for no SYSTEM.VSB, opened {looked['opened']}")
        tag = f"{i + 1}-{name.split(':')[0].replace(' ', '-')}"
        report, after = run_update(tag, running[0x100:], start, folder, card, shots, card[0x100:])
        if written:
            report["reboot"] = reboot(f"{tag}-reboot", after[FIRMWARE[0]:FIRMWARE[1]], after, shots)
        out.append({"path": name, "folder": f"KORG/{folder}/System/", "head": head_of(card), "expect_written": written,
                    "erase_commands": report["erase_commands"]["count"], "program_commands": report["program_commands"]["count"],
                    "firmware_area_is_the_new_file": report["firmware_area_is_the_new_file"],
                    "rest_of_the_flash_unchanged": report["user_area_identical"] and report["below_the_firmware_identical"] and report["bank_identical"],
                    "main_screen_after_restart": report.get("reboot", {}).get("main_screen"),
                    "asserts": report["asserts"], "ok": verdict(report, written)})
        print(json.dumps(out[-1]), file=sys.stderr, flush=True)
    return out


def main():
    import machine
    from synth_update_probe import inside_repo
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--korg-blue", required=True, type=Path)
    p.add_argument("--hacktribe", required=True, type=Path)
    p.add_argument("--blech", required=True, type=Path)
    p.add_argument("--flash", type=Path, help="16 MiB flash of a blue device (synth_pcm_flash.py); default a blank one")
    p.add_argument("--only", action="append", help="only the paths whose name starts with this, e.g. blech or 'way back'")
    p.add_argument("--shots", type=Path, help="folder for a picture of the display at each step (outside the repository)")
    a = p.parse_args()
    if a.shots:
        if inside_repo(a.shots):
            raise SystemExit("the pictures show Korg's screens: write them outside the repository")
        a.shots.mkdir(parents=True, exist_ok=True)
    files = [x.read_bytes() for x in (a.korg_blue, a.hacktribe, a.blech)]
    flash = a.flash.read_bytes() if a.flash else bytes(machine.hardware_flash("blue"))
    if any(len(f) != 0x200100 for f in files) or len(flash) != machine.FLASH_SIZE:
        raise SystemExit("three VSBs of 0x200100 bytes and a flash of 16 MiB")
    result = run(*files, flash, a.shots, a.only)
    print(json.dumps(result, indent=1))
    return 0 if all(r["ok"] for r in result) else 1


if __name__ == "__main__":
    sys.exit(main())
