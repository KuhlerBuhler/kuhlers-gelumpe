"""Builds the update-guard patch: SOFTWARE UPDATE refuses a SYSTEM.VSB that is not whole (docs/messungen/2026-11-13-update-schutz.md).

Korg's update reads the file's 0x100 byte header, checks it ("SYSTEM", the image size equal to the flash block's) and then
reads the image with f_read into RAM and writes it to the flash. It never checks how many bytes f_read gave back: a file cut
short (an aborted copy left 10240 bytes on 2026-11-12) passes the header check, f_read returns FR_OK with fewer bytes, and the
update erases and programs all 2 MiB with whatever stood in the buffer. The device does not start any more.

With this patch every f_read of the update goes through ug_read. It calls f_read as before and then checks that the file is
exactly 0x200100 bytes (header plus 2 MiB image, FatFs keeps the size at +0x0C of the file object) and that f_read gave all the
bytes asked for. When not:

- the header read (0x100 bytes) clears the header's first word ("KORG"), so Korg's own header check fails and the firmware
  shows its own "Error / Invalid File" and stops before "Are You Sure ?";
- the image read returns FR_DISK_ERR (1), so the update stops with Korg's file error before the flash write.

Five reads per build: the version page of DATA UTILITY > SOFTWARE UPDATE (header), the update behind it (header, image) and the
update the firmware offers at power-on (header, image). No checksum is checked: the header has none, and only Korg's own images
sum to zero (16-bit words), Hacktribe and every BLECH build do not. The check does not depend on the kill switch (EXIT at
power-on): it is a safety check and never runs at the start.

    python3 tools/patch/update_guard.py --vsb SYSTEM.VSB [--build synth] [--out data/patches/update-guard.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import synthaddr  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC014EE00            # FF in all three builds, in the run 0xC0148880..0xC014F000 in front of ht-osc (0xC014F000)
CODE_END = 0xC014EF00

F_READ = 0xC009DD74             # FatFs f_read(fil, buf, n, &read)
VERSION_HEAD = 0xC00309E0       # the version page of SOFTWARE UPDATE: bl f_read of the 0x100 byte header
BOOT_HEAD = 0xC003A968          # the update offered at power-on: header
BOOT_IMAGE = 0xC003A9FC         # ... and the image (r2 = the size from the header)
MENU_HEAD = 0xC003AD4C          # the update of DATA UTILITY after "Are You Sure ?": header
MENU_IMAGE = 0xC003AE24         # ... and the image
READS = ("VERSION_HEAD", "BOOT_HEAD", "BOOT_IMAGE", "MENU_HEAD", "MENU_IMAGE")
FIL_SIZE = 0x0C                 # FatFs file object: the file size (docs/messungen/2026-10-18-update-ueber-usb.md, both builds)
VSB_SIZE = 0x200100
HEAD_SIZE = 0x100

FIRMWARE_PLACES = ["F_READ", *READS]


def use_build(build):
    """For the synth (the blue Electribe 2) the firmware's places have their own addresses (data/synth-map/update-guard.json)."""
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def source():
    return f"""
.equ F_READ, {F_READ:#x}
.equ FIL_SIZE, {FIL_SIZE:#x}
.equ VSB_SIZE, {VSB_SIZE:#x}
.equ HEAD_SIZE, {HEAD_SIZE:#x}
.org {CODE_AT:#x}

; replaces bl f_read in SOFTWARE UPDATE: (file object, buffer, bytes, &read) as the firmware passes them, returns the FatFs result
ug_read:
    push {{r4, r5, r6, r7, r8, lr}}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    bl F_READ
    cmp r0, #0
    bne ug_out
    ldr r1, [r4, #FIL_SIZE]
    ldr r2, =VSB_SIZE
    cmp r1, r2
    bne ug_broken
    ldr r1, [r7]
    cmp r1, r6
    beq ug_out
ug_broken:
    cmp r6, #HEAD_SIZE
    bne ug_image
    mov r0, #0
    str r0, [r5]
    b ug_out
ug_image:
    mov r0, #1
ug_out:
    pop {{r4, r5, r6, r7, r8, pc}}
.pool
"""


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bl_word(at, target):
    return 0xEB000000 | (((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb, build="hacktribe"):
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    if was(CODE_AT, len(code)) != b"\xff" * len(code):
        raise SystemExit(f"{CODE_AT:#x}..{CODE_AT + len(code):#x} is not free in this VSB")
    changes = [{"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": sha(was(CODE_AT, len(code))),
                "note": "update guard: f_read of SOFTWARE UPDATE, then the file must be 0x200100 bytes and read whole"}]
    hooks = []
    for name in READS:
        site = globals()[name]
        if struct.unpack("<I", was(site, 4))[0] != bl_word(site, F_READ):
            raise SystemExit(f"SOFTWARE UPDATE does not call f_read at {name} ({site:#x}) in this VSB")
        changes.append({"file": file_offset(site), "bytes": struct.pack("<I", bl_word(site, symbols["ug_read"])).hex(),
                        "expect": sha(was(site, 4)), "note": f"SOFTWARE UPDATE reads the file through ug_read ({name.lower()})"})
        hooks.append({"site": f"0x{site:08X}", "kind": "call", "chain": "update-read", "position": "after", "swallow": False,
                      "note": "f_read runs first; a file that is not 0x200100 bytes or not read whole fails the update before the flash"})
    return {
        "format": "gelumpe-patch", "version": 1, "id": "update-guard",
        "name": "SOFTWARE UPDATE prüft die Dateigröße",
        "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "changes": changes,
        "hooks": hooks,
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    use_build(a.build)
    raw = a.vsb.read_bytes()
    if len(raw) != VSB_SIZE:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw, a.build), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
