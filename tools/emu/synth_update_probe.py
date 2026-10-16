# SPDX-License-Identifier: GPL-2.0-only
"""SOFTWARE UPDATE of the blue Electribe 2 (the synth) in the emulator: which flash ranges it erases and programs,
where the firmware looks for the update file, and the way there and back.

    tools/emu/.venv/bin/python tools/emu/synth_update_probe.py --original SYSTEM.VSB --patched BLECH-SYNTH.VSB \
        --flash IMAGE.bin [--shots DIR]

All three files are the user's own and stay outside the repository (the tool refuses a screenshot folder inside it, and
writes nothing else). The flash image is the 16 MiB image of tools/emu/synth_pcm_flash.py or any other synth flash.

What it does, each step on mains power (the adapter) with a virtual card that holds only SYSTEM.VSB:

  1. The original firmware on the flash, an empty card: DATA UTILITY, SOFTWARE UPDATE, ENTER. The files the firmware tries to
     open are logged (the folder it reads is measured, not assumed).
  2. The same with the patched VSB on the card where the firmware looked, driven by key presses through to the end. Every
     erase and every page program of the flash chip is logged, the 16 MiB before and after are compared byte for byte.
  3. Reboot (a new machine from the flash, as the bootloader would load it): is it the patched firmware, does it reach the
     main screen, does the PCM load accept the bank, does FLASH READ (0x64) answer with the bytes of the flash.
  4. The way back from the running patched firmware with the original VSB on the card in the folder the patched build reads:
     the same logging and comparison, reboot, the original again.

Display text is not read by the tool but saved as pictures (`--shots`), step by step, for a person to look at; the tool records
the screen number of the firmware and the number of lit pixels at each step.
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools" / "patch"))

import fat32  # noqa: E402
import machine  # noqa: E402
import sysex_cases  # noqa: E402
import synth_probe as sp  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

FIRMWARE = (0x20000, 0x220000)          # where SOFTWARE UPDATE writes the firmware (the Sampler's measurement, docs/messungen/2026-10-13-globals-zurueckgesetzt.md)
BANK = (0x800000, 0x1000000)
USER = (0x220000, 0x800000)
SOFTWARE_UPDATE_PAGE = 10               # DATA UTILITY 11 of 11: ten steps right from page 1 (measured, the picture of each step is in --shots)
FILES_TRIED = ("BOOT.VSB", "USER.VSB", "PCM.VSB", "SYSTEM.VSB")


def inside_repo(path):
    return any((p / ".git").exists() for p in [path.resolve(), *path.resolve().parents])


class Rig:
    """A synth device on mains power with a virtual card, its flash chip logged, the files the firmware opens logged."""

    def __init__(self, payload, flash, files, shots=None, tag=""):
        import unicorn
        self.dev = Dev(payload, flash)
        self.m = self.dev.m
        self.m.adapter = True
        self.shots, self.tag, self.step = shots, tag, 0
        img = fat32.format_image(128 * 1024 * 1024)
        volume = fat32.Volume(img)
        for path, data in files.items():
            volume.write(path, data)
        volume.close()
        self.card = SDCard(MemoryMedium(img))
        self.m.insert_card(self.card)
        self.erases, self.programs, self.opened = [], [], []
        fl = self.m.flash
        erase, byte = fl.erase, fl.byte

        def logged_erase(size):
            self.erases.append({"address": fl.addr & ~(size - 1), "size": size})
            return erase(size)

        def logged_byte(b):
            r = byte(b)
            if fl.cmd == 0x02 and fl.wel:
                if len(fl.buf) == 3:
                    self.programs.append({"address": fl.addr, "bytes": 0})
                elif len(fl.buf) > 3 and self.programs:
                    self.programs[-1]["bytes"] += 1
            return r

        fl.erase, fl.byte = logged_erase, logged_byte
        self.pcm_result = []
        uc = self.m.uc

        def on_open(u, a, s, d):
            p = u.reg_read(unicorn.arm_const.UC_ARM_REG_R1)
            self.opened.append(bytes(u.mem_read(p, 80)).split(b"\0")[0].decode("latin1"))

        def on_pcm(u, a, s, d):
            self.pcm_result.append(u.reg_read(unicorn.arm_const.UC_ARM_REG_R6))

        uc.hook_add(unicorn.UC_HOOK_CODE, on_open, begin=sp.FUNCS["f_open"], end=sp.FUNCS["f_open"])
        uc.hook_add(unicorn.UC_HOOK_CODE, on_pcm, begin=sp.FUNCS["pcm_loaded"], end=sp.FUNCS["pcm_loaded"])
        uc.ctl_flush_tb()

    def shot(self, name):
        """Record the screen number and the lit pixels, and save the picture."""
        shown = self.m.shown()
        lit = sum(bin(b).count("1") for b in shown)
        if self.shots:
            self.step += 1
            self.m.png(str(self.shots / f"{self.tag}-{self.step:02d}-{name}.png"), 3)
        return {"step": name, "screen": self.m.screen(), "lit_pixels": lit}

    def run(self, seconds):
        self.dev.run(seconds)

    def press(self, key, wait=0.5):
        self.dev.press(key, wait)

    def to_software_update(self, log):
        """MENU, two steps left, MENU: DATA UTILITY page 1; then to the last page, SOFTWARE UPDATE."""
        for key in ("menu", "edit_prev", "edit_prev", "menu"):
            self.press(key)
        log.append(self.shot("data-utility-1"))
        for _ in range(SOFTWARE_UPDATE_PAGE):
            self.press("edit_next", 0.25)
        log.append(self.shot("software-update-page"))

    def flash_busy(self):
        return (len(self.erases), len(self.programs))


def boot_to_main(rig, limit=20.0):
    t = 0.0
    while t < limit and rig.m.screen() != 1:
        rig.run(0.5)
        t += 0.5
    rig.run(1.0)
    return rig.m.screen() == 1


def ranges(a, b):
    """Byte ranges where the two images differ, as [start, end) lists."""
    out, i, n = [], 0, len(a)
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            out.append([i, j])
            i = j
        else:
            i += 1
    return out


def merge(items, gap=0):
    out = []
    for start, end in sorted(items):
        if out and start <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def hexr(rs):
    return [[f"{a:#08x}", f"{b:#08x}"] for a, b in rs]


def probe_empty_card(original, flash, shots):
    """Step 1: where the firmware looks for the update file."""
    rig = Rig(original, flash, {}, shots, "1-empty")
    log = [{"booted_to_main": boot_to_main(rig)}]
    rig.to_software_update(log)
    before = rig.flash_busy()
    rig.press("menu", 1.5)
    log.append(rig.shot("enter-without-a-card-file"))
    rig.run(1.0)
    return {"opened": rig.opened, "steps": log, "flash_commands_during_enter": [len(rig.erases) - before[0], len(rig.programs) - before[1]]}


def run_update(name, payload, flash, folder, new_vsb, shots, expect_new_payload):
    """Steps 2 and 4: SOFTWARE UPDATE with `new_vsb` on the card in `folder`, driven by key presses; returns the report and the flash after."""
    files = {f"/KORG/{folder}/System/SYSTEM.VSB": new_vsb}
    rig = Rig(payload, flash, files, shots, name)
    log = [{"booted_to_main": boot_to_main(rig)}]
    before = bytes(rig.m.flash.mem)
    rig.to_software_update(log)
    base = rig.flash_busy()           # what the boot itself did to the chip is not the update's
    rig.press("menu", 1.5)
    log.append(rig.shot("after-enter"))
    # the firmware asks, then works: keep confirming with MENU while it asks, shoot every step, stop when the flash is quiet
    quiet, spent = 0, 0.0
    last = base
    presses = 0
    while spent < 240 and quiet < 6:
        rig.run(1.0)
        spent += 1.0
        now = rig.flash_busy()
        quiet = quiet + 1 if now == last else 0
        last = now
        if spent % 10 == 0:
            log.append(rig.shot(f"t{int(spent)}s"))
        if now == base and presses < 4 and spent >= 2:
            rig.press("menu", 1.5)
            presses += 1
            log.append(rig.shot(f"menu-press-{presses}"))
    rig.run(2.0)
    log.append(rig.shot("end"))
    after = bytes(rig.m.flash.mem)
    changed = merge(ranges(before, after))
    erases, programs = rig.erases[base[0]:], rig.programs[base[1]:]
    chip = merge([[e["address"], e["address"] + e["size"]] for e in erases] + [[p["address"], p["address"] + p["bytes"]] for p in programs])
    erase_sizes = {}
    for e in erases:
        erase_sizes[e["size"]] = erase_sizes.get(e["size"], 0) + 1
    new_payload = after[FIRMWARE[0]:FIRMWARE[1]]
    report = {
        "files_opened": rig.opened,
        "final_screen": rig.m.screen(),
        "erase_commands": {"count": len(erases), "by_size": {hex(k): v for k, v in erase_sizes.items()}, "first": erases[:2], "last": erases[-2:]},
        "program_commands": {"count": len(programs), "bytes": sum(p["bytes"] for p in programs), "first": programs[:2], "last": programs[-2:]},
        "chip_commands_during_the_boot_before_it": {"erases": base[0], "programs": base[1]},
        "ranges_touched_by_the_chip_commands": hexr(chip),
        "ranges_changed_in_the_16_MiB": hexr(changed),
        "bank_identical": before[BANK[0]:BANK[1]] == after[BANK[0]:BANK[1]],
        "user_area_identical": before[USER[0]:USER[1]] == after[USER[0]:USER[1]],
        "below_the_firmware_identical": before[:FIRMWARE[0]] == after[:FIRMWARE[0]],
        "firmware_area_is_the_new_file": new_payload == expect_new_payload,
        "asserts": list(rig.m.asserts),
        "steps": log,
    }
    return report, after


def reboot(name, payload, flash, shots, check_flash_read=False):
    """A new machine from the flash, as the bootloader loads it: main screen, PCM load, FLASH READ."""
    rig = Rig(payload, flash, {}, shots, name)
    out = {"main_screen": boot_to_main(rig), "pcm_load_result_r6": rig.pcm_result, "asserts": list(rig.m.asserts)}
    out["picture"] = rig.shot("main")
    if check_flash_read:
        sysex_cases.MODEL = 0x23
        try:
            lk = sysex_cases.Link(rig.dev)
            lk.find_channel()
            info = lk.info()
            read = {}
            for addr, n in ((0x20000, 64), (0x220000, 16), (0x800000, 4096), (0xFFFFFF, 1)):
                r = lk.flash(addr, n)
                read[hex(addr)] = bool(r and r["status"] == 0 and r["crc_ok"] and r["data"] == bytes(rig.m.flash.mem[addr:addr + n]))
            out["blech_info"] = {"flags": hex(info["flags"]) if info else None, "flash_block": info["max_flash"] if info else None}
            out["flash_read_equals_the_flash"] = read
        finally:
            sysex_cases.MODEL = 0x24
    out["opened"] = rig.opened[-6:]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--original", required=True, type=Path)
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", required=True, type=Path)
    p.add_argument("--shots", type=Path, help="folder for a picture of the display at each step (outside the repository)")
    a = p.parse_args()
    if a.shots:
        if inside_repo(a.shots):
            raise SystemExit("the pictures show Korg's screens: write them outside the repository")
        a.shots.mkdir(parents=True, exist_ok=True)
    orig, patched = a.original.read_bytes(), a.patched.read_bytes()
    flash = a.flash.read_bytes()
    if len(orig) != 0x200100 or len(patched) != 0x200100 or len(flash) != machine.FLASH_SIZE:
        raise SystemExit("two VSBs of 0x200100 bytes and a flash of 16 MiB")
    # the flash starts as it is on a device that runs the original: the original's image in 0x20000..0x220000
    flash = bytearray(flash)
    flash[FIRMWARE[0]:FIRMWARE[1]] = orig[0x100:]
    flash = bytes(flash)
    # a device that has run before: one boot of the original first (the firmware writes its own 8 byte mark at 0x7EF000 on a flash
    # that never had one, and the image of synth_pcm_flash.py has none); the flash after that boot is where the measurement starts
    prime = Rig(orig[0x100:], flash, {}, None, "0-prime")
    boot_to_main(prime)
    flash = bytes(prime.m.flash.mem)
    report = {"first_boot_of_the_image_wrote": {"erases": prime.erases, "program_bytes": sum(p["bytes"] for p in prime.programs)},
              "flash_sha256_before": __import__("hashlib").sha256(flash).hexdigest()}
    report["1_where_the_firmware_looks"] = probe_empty_card(orig[0x100:], flash, a.shots)
    folder = report["1_where_the_firmware_looks"]["opened"][0].split("/")[1] if report["1_where_the_firmware_looks"]["opened"] else None
    if folder is None:
        raise SystemExit("the firmware did not open any file")
    report["folder"] = f"KORG/{folder}/System/"
    up, flash2 = run_update("2-update", orig[0x100:], flash, folder, patched, a.shots, patched[0x100:])
    report["2_update_to_the_patched_firmware"] = up
    report["3_reboot_into_the_patched_firmware"] = reboot("3-reboot", flash2[FIRMWARE[0]:FIRMWARE[1]], flash2, a.shots, True)
    # the folder the patched build reads: measured on the running patched firmware, with an empty card
    back_folder = probe_empty_card(patched[0x100:], flash2, a.shots)
    report["4_where_the_patched_firmware_looks"] = back_folder
    folder2 = back_folder["opened"][0].split("/")[1] if back_folder["opened"] else folder
    back, flash3 = run_update("5-back", patched[0x100:], flash2, folder2, orig, a.shots, orig[0x100:])
    report["5_way_back_to_the_original"] = back
    report["6_reboot_into_the_original"] = reboot("6-reboot", flash3[FIRMWARE[0]:FIRMWARE[1]], flash3, a.shots)
    report["flash_changed_over_the_whole_round_trip"] = hexr(merge(ranges(flash, flash3)))
    report["flash_equal_to_the_start_after_the_way_back"] = flash == flash3
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
