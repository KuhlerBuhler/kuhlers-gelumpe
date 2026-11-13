"""Emulator cases of the update guard (tools/patch/update_guard.py): DATA UTILITY > SOFTWARE UPDATE with a SYSTEM.VSB that is cut
short (10240 bytes, the file of 2026-11-12), empty or too long writes nothing to the flash; a whole file still updates, and
without the guard the cut short file is flashed (the control that the cases can see a write).

    python3 tools/emu/update_guard_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

Two cases restore the guard's first reads to Korg's bl f_read, so each later read (the header after "Are You Sure ?", then the
image) is shown to refuse the file on its own. The update offered at power-on goes through the same ug_read; the emulator does not
reach it (it needs a flash without firmware, where the bootloader does not start the image).
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import update_guard as spec  # noqa: E402
import synthaddr  # noqa: E402
import machine  # noqa: E402
from machine import load_flash  # noqa: E402

IMAGE = 0xC0000000
FOLDERS = ("blechtribe", "hacktribe", "electribe sampler", "electribe")
TRUNCATED = 10240
MARK = 0xC014EF80                    # FF in every build, behind the guard's code: the whole file's one changed byte


def for_build(payload):
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def calls_guard(payload, site):
    word = struct.unpack_from("<I", payload, site - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= (site + 8 + (off << 2)) & 0xFFFFFFFF < spec.CODE_END


def has_hooks(payload):
    """True when the image read of SOFTWARE UPDATE goes through ug_read."""
    for_build(payload)
    return calls_guard(payload, spec.MENU_IMAGE)


def entry(name, ok, detail):
    return {"id": f"updateguard:{name}", "ok": bool(ok), "detail": str(detail)}


def header(payload):
    synth = synthaddr.is_synth(payload)
    head = bytearray(b"\xff" * spec.HEAD_SIZE)
    head[:0x42] = (b"KORG SYSTEM FILE" + (b"E2" if synth else b"E2S").ljust(16, b"\0") + b"SYSTEM\0\0\0\x01\x02\x02\0\x01"
                   + bytes([0x23 if synth else 0x24, 0xFF]) + struct.pack("<II", 0, 0x200000) + struct.pack("<II", 0, 0x200000) + b"\x02\0")
    return bytes(head)


def with_reads_restored(payload, names):
    out = bytearray(payload)
    for name in names:
        site = getattr(spec, name)
        struct.pack_into("<I", out, site - IMAGE, spec.bl_word(site, spec.F_READ))
    return bytes(out)


def update(payload, flash, file):
    """SOFTWARE UPDATE with `file` in every folder the builds read; returns the erases and programs, the firmware area after,
    the screen, the asserts and whether the firmware opened SYSTEM.VSB."""
    import synth_update_probe as sup
    rig = sup.Rig(payload, flash, {f"/KORG/{f}/System/SYSTEM.VSB": file for f in FOLDERS}, None, "ug")
    sup.boot_to_main(rig)
    rig.to_software_update([])
    base = rig.flash_busy()
    rig.press("menu", 1.5)
    quiet, spent, presses, last = 0, 0, 0, base
    while spent < 240 and quiet < 6:
        rig.run(1.0)
        spent += 1
        now = rig.flash_busy()
        quiet = quiet + 1 if now == last else 0
        last = now
        if now == base and presses < 4 and spent >= 2:
            rig.press("menu", 1.5)
            presses += 1
    rig.run(2.0)
    erases, programs = rig.flash_busy()
    area = bytes(rig.m.flash.mem[sup.FIRMWARE[0]:sup.FIRMWARE[1]])
    opened = any(p.endswith("/SYSTEM.VSB") for p in rig.opened)
    return erases - base[0], programs - base[1], area, rig.m.screen(), list(rig.m.asserts), opened


def start_flash(payload, flash):
    """The flash of a device that runs `payload`: its image in the firmware area."""
    import synth_update_probe as sup
    if flash is None:
        flash = machine.hardware_flash("blue" if synthaddr.is_synth(payload) else "red")
    flash = bytearray(flash)
    flash[sup.FIRMWARE[0]:sup.FIRMWARE[1]] = payload
    return bytes(flash)


def refused(name, payload, flash, file, run=None):
    for_build(payload)
    flash = start_flash(payload, flash)
    running = run or payload                     # the emulator boots the image it runs from the flash's firmware area
    erases, programs, area, screen, asserts, opened = update(running, flash, file)
    return [entry(name, opened and erases == 0 and programs == 0 and area == running and not asserts,
                  f"{len(file)} bytes: SYSTEM.VSB opened {opened}, {erases} erases, {programs} programs, firmware area unchanged {area == running}, "
                  f"screen {screen}, asserts {asserts}")]


def whole(payload):
    new = bytearray(payload)
    new[MARK - IMAGE] ^= 0xFF
    return bytes(new)


def case_truncated(payload, flash):
    return refused("truncated", payload, flash, (header(payload) + payload)[:TRUNCATED])


def case_empty(payload, flash):
    return refused("empty", payload, flash, b"")


def case_oversize(payload, flash):
    return refused("oversize", payload, flash, header(payload) + payload + b"\xff" * 0x100)


def case_menu_header(payload, flash):
    """The version page reads as Korg's: the header read after "Are You Sure ?" refuses the file."""
    for_build(payload)
    return refused("menu_header_alone", payload, flash, (header(payload) + payload)[:TRUNCATED],
                   with_reads_restored(payload, ["VERSION_HEAD"]))


def case_menu_image(payload, flash):
    """Both header reads as Korg's: the image read refuses the file before the flash write."""
    for_build(payload)
    return refused("menu_image_alone", payload, flash, (header(payload) + payload)[:TRUNCATED],
                   with_reads_restored(payload, ["VERSION_HEAD", "MENU_HEAD"]))


def case_whole(payload, flash):
    for_build(payload)
    new = whole(payload)
    erases, programs, area, screen, asserts, _ = update(payload, start_flash(payload, flash), header(payload) + new)
    return [entry("whole_file_updates", erases > 0 and programs > 0 and area == new and not asserts,
                  f"{erases} erases, {programs} programs, firmware area is the new file {area == new}, screen {screen}, asserts {asserts}")]


def case_without_guard(payload, flash):
    """All five reads as Korg's: the cut short file goes into the flash, so the cases above can see a write."""
    for_build(payload)
    korg = with_reads_restored(payload, spec.READS)
    erases, programs, area, screen, asserts, _ = update(korg, start_flash(payload, flash), (header(payload) + payload)[:TRUNCATED])
    return [entry("without_guard_the_cut_file_is_flashed", erases > 0 and programs > 0 and area != korg,
                  f"{erases} erases, {programs} programs, firmware area changed {area != korg}, screen {screen}")]


GROUPS = (case_truncated, case_empty, case_oversize, case_menu_header, case_menu_image, case_whole, case_without_guard)


def group_entries(payload, flash, i):
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
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path, nargs="+")
    p.add_argument("--group", type=int, help="run one group only (index into GROUPS)")
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    result = group_entries(payload, flash, a.group) if a.group is not None else cases(payload, flash)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
