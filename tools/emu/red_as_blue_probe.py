# SPDX-License-Identifier: GPL-2.0-only
"""Korg's blue firmware on a red Electribe 2 and back to BLECH, in the emulator (docs/messungen/2026-11-08-rot-als-blau.md).

    tools/emu/.venv/bin/python tools/emu/red_as_blue_probe.py --blech BLECH.VSB --korg-blue SYSTEM.VSB \
        --flash RED-DUMP.bin [--shots DIR]

All files are the user's own and stay outside the repository: the BLECH + Hacktribe file that runs on the red device, Korg's
blue 2.02 unchanged, and a 16 MiB flash of a red device (a dump with its patterns, or a blank one without --flash). The tool
writes the blue file with the one word below itself, and nothing to disk except pictures (--shots).

The steps, each on mains power with only that file on the card, in the folder the running firmware asks for:

  1  BLECH runs: Korg's blue unchanged is refused, with the Sampler head it is written.
  2  Korg's blue then starts on the red flash: plain it stops at SOFTWARE UPDATE; with the word it reaches the main screen.
     From the stop, BLECH with the Sampler head in KORG/electribe sampler/System is written and starts.
  3  What the blue does with the red flash while it runs: what it reads at start, the PCM tables it builds from the Sampler's
     sample bank, what a pattern WRITE and a switch-off on batteries write, which card files it opens.
  4  The blue with the word runs: BLECH with the Sampler head is refused, with the blue head it is written and starts, and the
     user area is the one from before the blue, except what step 3 wrote.
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

from hacktribe_blue_probe import FIRMWARE, device_flash, with_head  # noqa: E402

BASE = 0xC0000000 - 0x100     # file offset = CPU address - BASE
# The user-data mark check of Korg's blue 2.02 (0xC00270BC): `elec2USR` gives the literal 0x123 at 0xC0027128, `ele2sUSR` gives
# `moveq r0, #0x124` at 0xC0027114, the start accepts only 0x123. The word makes `ele2sUSR` load the same 0x123 literal
# (`ldreq r0, [pc, #0xc]`), the mirror of what Hacktribe changes in the Sampler (docs/ideen/65-blech-hacktribe-blau.md).
MARK_FIX = 0xC0027114
MARK_FIX_OLD = 0x03A00F49
MARK_FIX_NEW = 0x059F000C
MARK_LITERAL = 0xC0027128
USER = (0x220000, 0x1000000)
POWER_KEY = [6, 1, 0, 0, 0]


def word(vsb, address):
    return struct.unpack_from("<I", vsb, address - BASE)[0]


def mark_fix(vsb):
    """Korg's blue 2.02 with the one word; refuses any other file."""
    if word(vsb, MARK_FIX) != MARK_FIX_OLD or word(vsb, MARK_LITERAL) != 0x123:
        raise ValueError("not Korg's blue 2.02: the mark check is not where it is measured")
    out = bytearray(vsb)
    struct.pack_into("<I", out, MARK_FIX - BASE, MARK_FIX_NEW)
    return bytes(out)


def changed(a, b, at=0):
    from synth_update_probe import hexr, merge, ranges
    return hexr([[x + at, y + at] for x, y in merge(ranges(a, b))])


def update(tag, running, flash, card, shots):
    """SOFTWARE UPDATE in the folder the running firmware asks for; returns a short report and the flash after."""
    from synth_update_probe import probe_empty_card, run_update, update_folder
    folder = update_folder(probe_empty_card(running[0x100:], flash, shots)["opened"])
    report, after = run_update(tag, running[0x100:], flash, folder, card, shots, card[0x100:])
    return {"folder": f"KORG/{folder}/System/", "erases": report["erase_commands"]["count"],
            "written": report["firmware_area_is_the_new_file"],
            "rest_of_the_flash_unchanged": report["user_area_identical"] and report["below_the_firmware_identical"] and report["bank_identical"],
            "asserts": report["asserts"]}, after


def start(tag, vsb, flash, shots, files=None, seconds=5.0):
    """A start from `flash` with `vsb` in the firmware area: screen, flash reads, chip commands, PCM load, card files opened."""
    from synth_update_probe import Rig, boot_to_main, hexr, merge
    mem = bytearray(flash)
    mem[FIRMWARE[0]:FIRMWARE[1]] = vsb[0x100:]
    rig = Rig(vsb[0x100:], bytes(mem), files or {}, shots, tag)
    reads, read = [], rig.m._flash_read

    def logged():
        reads.append([rig.m.reg(rig.m.A.UC_ARM_REG_R1), rig.m.reg(rig.m.A.UC_ARM_REG_R2)])
        return read()

    rig.m._flash_read = logged
    main = boot_to_main(rig)
    rig.run(seconds)
    shot = rig.shot("start")
    return rig, {"main_screen": main, "screen": shot["screen"], "pcm_load_r6": rig.pcm_result, "asserts": list(rig.m.asserts),
                 "flash_read": hexr(merge([[a, a + n] for a, n in reads])), "erases": len(rig.erases),
                 "flash_changed": changed(bytes(mem), bytes(rig.m.flash.mem)), "card_files_opened": rig.opened}


def from_the_stop(blue, blech, flash, shots):
    """Plain blue on a red flash stops at SOFTWARE UPDATE: ENTER with BLECH (Sampler head) in the Sampler's folder."""
    from synth_update_probe import Rig
    card = with_head(blech, "sampler")
    rig = Rig(blue[0x100:], flash, {"/KORG/electribe sampler/System/SYSTEM.VSB": card}, shots, "2-stop")
    rig.run(6.0)
    screen = rig.m.screen()
    rig.press("menu", 1.5)
    quiet, last, spent = 0, (0, 0), 0
    while spent < 120 and quiet < 6:
        rig.run(1.0)
        spent += 1
        now = (len(rig.erases), len(rig.programs))
        quiet, last = (quiet + 1 if now == last else 0), now
    after = bytes(rig.m.flash.mem)
    return {"screen_at_start": screen, "asked_for": rig.opened, "erases": len(rig.erases),
            "written": after[FIRMWARE[0]:FIRMWARE[1]] == blech[0x100:],
            "rest_of_the_flash_unchanged": after[:FIRMWARE[0]] == flash[:FIRMWARE[0]] and after[FIRMWARE[1]:] == flash[FIRMWARE[1]:]}, after


def run(blech, blue, flash, shots=None):
    import synth_probe as sp
    from synth_update_probe import Rig, boot_to_main
    fixed = mark_fix(blue)
    out = {}
    red = device_flash(blech, flash)
    out["1_blue_unchanged"], _ = update("1-blue-unchanged", blech, red, blue, shots)
    out["1_blue_sampler_head"], on_blue = update("1-blue-sampler-head", blech, red, with_head(blue, "sampler"), shots)
    out["2_plain_blue_starts"] = start("2-plain", blue, on_blue, shots)[1]
    out["2_from_the_stop"], stop_after = from_the_stop(blue, blech, on_blue, shots)
    out["2_from_the_stop"]["blech_starts"] = start("2-stop-blech", blech, stop_after, shots)[1]["main_screen"]
    _, out["2_blue_with_the_word_starts"] = start("2-fixed", fixed, on_blue, shots, {
        "/KORG/blechtribe/Sample/e2sSample.all": b"\x11" * 0x10000, "/KORG/blechtribe/settings.a.bin": b"\x22" * 64})
    probe = sp.Probe(fixed[0x100:], on_blue[:FIRMWARE[0]] + fixed[0x100:] + on_blue[FIRMWARE[1]:])
    probe.run_to(8.0)
    bank = sp.parse_bank(on_blue[0x800000:0x1000000])
    osc = sp.osc_table(fixed[0x100:])
    out["3_pcm"] = {"tables": probe.tables(1)["counts"], "bank_on_the_flash": {n: s["count"] for n, s in bank["sections"].items() if s},
                    "oscillators": len(osc), "pcm_oscillators": sum(1 for o in osc if o["wave"] >= sp.PCM_FIRST_WAVE)}
    base = on_blue[:FIRMWARE[0]] + fixed[0x100:] + on_blue[FIRMWARE[1]:]
    rig = Rig(fixed[0x100:], base, {}, shots, "3-write")
    boot_to_main(rig)
    before = bytes(rig.m.flash.mem)
    rig.press("write", 1.0)
    rig.press("write", 3.0)
    used = bytes(rig.m.flash.mem)
    out["3_pattern_write"] = {"erases": len(rig.erases), "changed": changed(before[USER[0]:], used[USER[0]:], USER[0])}
    off = Rig(fixed[0x100:], used, {}, shots, "3-off")
    off.m.adapter = False                  # the power source is reported at start, so batteries from the first moment
    boot_to_main(off)
    before = bytes(off.m.flash.mem)
    off.m.send(POWER_KEY)
    t0 = off.m.time_ns
    while off.m.powered and (off.m.time_ns - t0) / 1e9 < 4:
        off.run(0.01)
    out["3_switch_off"] = {"off": not off.m.powered, "erases": len(off.erases),
                           "changed": changed(before[USER[0]:], bytes(off.m.flash.mem)[USER[0]:], USER[0])}
    out["4_blech_sampler_head"], _ = update("4-blech-sampler-head", fixed, used, with_head(blech, "sampler"), shots)
    out["4_blech_blue_head"], back = update("4-blech-blue-head", fixed, used, with_head(blech, "blue"), shots)
    out["4_blech_starts"] = start("4-blech", blech, back, shots)[1]["main_screen"]
    out["4_user_area_against_before_the_blue"] = changed(red[USER[0]:], back[USER[0]:], USER[0])
    return out


def verdict(r):
    """True when every step did what the measurement of 2026-11-08 found."""
    return all([
        not r["1_blue_unchanged"]["written"] and r["1_blue_unchanged"]["erases"] == 0,
        r["1_blue_sampler_head"]["written"] and r["1_blue_sampler_head"]["rest_of_the_flash_unchanged"],
        not r["2_plain_blue_starts"]["main_screen"] and r["2_plain_blue_starts"]["erases"] == 0,
        r["2_from_the_stop"]["written"] and r["2_from_the_stop"]["rest_of_the_flash_unchanged"] and r["2_from_the_stop"]["blech_starts"],
        r["2_blue_with_the_word_starts"]["main_screen"] and r["2_blue_with_the_word_starts"]["erases"] == 0,
        not r["2_blue_with_the_word_starts"]["card_files_opened"],
        not r["4_blech_sampler_head"]["written"] and r["4_blech_sampler_head"]["erases"] == 0,
        r["4_blech_blue_head"]["written"] and r["4_blech_blue_head"]["rest_of_the_flash_unchanged"] and r["4_blech_starts"],
        all(0x240000 <= int(a, 16) and int(b, 16) <= 0x244000 for a, b in r["4_user_area_against_before_the_blue"]),
    ])


def main():
    import machine
    from synth_update_probe import inside_repo
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--blech", required=True, type=Path, help="the BLECH + Hacktribe file of the red device (either head)")
    p.add_argument("--korg-blue", required=True, type=Path, help="Korg's blue 2.02, unchanged")
    p.add_argument("--flash", type=Path, help="16 MiB flash of the red device; default a blank red one")
    p.add_argument("--shots", type=Path, help="folder for a picture of the display at each step (outside the repository)")
    a = p.parse_args()
    if a.shots:
        if inside_repo(a.shots):
            raise SystemExit("the pictures show Korg's screens: write them outside the repository")
        a.shots.mkdir(parents=True, exist_ok=True)
    blech, blue = a.blech.read_bytes(), a.korg_blue.read_bytes()
    flash = a.flash.read_bytes() if a.flash else bytes(machine.hardware_flash("red"))
    if len(blech) != 0x200100 or len(blue) != 0x200100 or len(flash) != machine.FLASH_SIZE:
        raise SystemExit("two VSBs of 0x200100 bytes and a flash of 16 MiB")
    if machine.hardware_of_flash(flash) != "red":
        raise SystemExit("the flash has to carry the red mark KORGele2sUSR")
    result = run(blech, blue, flash, a.shots)
    print(json.dumps(result, indent=1))
    return 0 if verdict(result) else 1


if __name__ == "__main__":
    sys.exit(main())
