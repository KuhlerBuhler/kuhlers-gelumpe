# SPDX-License-Identifier: GPL-2.0-only
"""Research project paths with native Sampler imports and synthetic files on a virtual card.

No firmware output is built. Boot path arguments and command invocation are model assumptions;
FatFs, the sample parser and sample replacement run as ARM code. See docs/ideen/64-projekte.md.

    tools/emu/.venv/bin/python tools/emu/project_probe.py --vsb SYSTEM.VSB --report report.json
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

import fat32
import sampleset
import unicorn
from sdcard import MemoryMedium, SDCard
from splash_cases import Dev, user_flash

BASE = 0xC0000000
SCRATCH = 0xC3F00000
F_OPEN, F_READ, F_CLOSE, F_SEEK, F_STAT = 0xC009DB60, 0xC009DD74, 0xC009E3DC, 0xC009E404, 0xC009E7DC
SAMPLE_COMMAND, SAMPLE_PATH = 0xC0038D80, 0xC0345A24
SAMPLE_META, SAMPLE_NAMES = 0xC036AD88, 0xC047B08C
PATTERNS = 0xC08B2940
PROJECTS = {
    "A": {500: ("A-501", 32), 501: ("A-502", 48)},
    "B live 02": {500: ("B-501", 96), 502: ("B-503", 16)},
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def project_path(name, filename):
    return f"SD:KORG/blechtribe/Projects/{name}/{filename}"


def pattern_file(name):
    """Self-made records with framing and names; no firmware presets or recordings."""
    head = bytearray(0x10100)
    head[:4], head[0x10:0x19] = b"KORG", b"e2sampler"
    head[0x100:0x104], head[0x1FC:0x200] = b"GLST", b"GLED"
    bank = bytearray(250 * 0x4000)
    for index in range(250):
        at = index * 0x4000
        bank[at:at + 4] = b"PTST"
        struct.pack_into("<I", bank, at + 4, 0x4000)
        label = f"{name[:8]}-{index + 1:03}".encode("ascii")
        bank[at + 16:at + 16 + len(label)] = label
        struct.pack_into("<H", bank, at + 34, 1200)
        bank[at + 0x3BFC:at + 0x3C00] = b"PTED"
    return bytes(head + bank)


def probe(payload):
    dev = Dev(payload)
    machine, uc, arm = dev.m, dev.m.uc, dev.m.A
    if machine.profile.build == "synth":
        raise ValueError("This probe only has measured import addresses for stock Sampler and Hacktribe.")
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    files = {}
    for name, samples in PROJECTS.items():
        for filename, data in (("e2sSample.all", sampleset.build(samples)), ("e2sPattern.all", pattern_file(name))):
            path = project_path(name, filename)
            files[path] = data
            volume.write(path[3:], data)
    volume.close()
    machine.insert_card(SDCard(MemoryMedium(image)))
    operations, redirects = [], []
    phase = "boot"

    def cstring(address):
        return bytes(uc.mem_read(address, 256)).split(b"\0")[0].decode("ascii")

    def observe(cpu, address, size, context):
        register = arm.UC_ARM_REG_R0 if address == F_STAT else arm.UC_ARM_REG_R1
        path = cstring(cpu.reg_read(register))
        if phase == "boot" and path.endswith("/Sample/e2sSample.all"):
            replacement = project_path("A", "e2sSample.all")
            uc.mem_write(SCRATCH, replacement.encode("ascii") + b"\0")
            cpu.reg_write(register, SCRATCH)
            redirects.append(dict(api="stat" if address == F_STAT else "open", original=path, selected=replacement))
            path = replacement
        operations.append(dict(phase=phase, api="stat" if address == F_STAT else "open", path=path,
                               mode=cpu.reg_read(arm.UC_ARM_REG_R2) if address == F_OPEN else None))

    for address in (F_STAT, F_OPEN):
        uc.hook_add(unicorn.UC_HOOK_CODE, observe, begin=address, end=address)
    dev.run(2)
    flash_before, card_before = user_flash(machine), digest(image)
    bank_before = digest(dev.read(PATTERNS, 250 * 0x4000))
    checks = []

    def check(name, ok, observed):
        checks.append(dict(name=name, ok=bool(ok), observed=observed))

    def active():
        return {str(index): dev.read(SAMPLE_NAMES + index * 32, 16).split(b"\0")[0].decode("ascii")
                for index in range(500, 1000) if dev.read(SAMPLE_META + index * 0x45C + 11, 1)[0] == 1}

    def wanted(name):
        return {str(index): sample[0] for index, sample in PROJECTS[name].items()}

    check("boot-from-project-A", active() == wanted("A"), active())
    check("boot-stat-and-open-redirected", {item["api"] for item in redirects} == {"stat", "open"}, redirects)

    for name in ("B live 02", "A", "missing"):
        phase = f"sample-command-{name}"
        old = active()
        uc.mem_write(SCRATCH, project_path(name, "e2sSample.all").encode("ascii") + b"\0")
        dev.call(0xC00A26C0, SAMPLE_PATH, SCRATCH)
        uc.mem_write(SCRATCH + 0x200, bytes(0x80))
        uc.mem_write(SCRATCH + 0x300, struct.pack("<6I", SCRATCH + 0x310, 0, 0, 0, 0, 501))
        dev.call(SAMPLE_COMMAND, SCRATCH + 0x200, SCRATCH + 0x300)
        status = dev.read(SCRATCH + 0x218, 1)[0]
        now = active()
        expected = wanted(name) if name in PROJECTS else {}
        check(f"native-sample-command-{name}", status == 0 and now == expected if name in PROJECTS else status != 0,
              dict(status=status, before=old, after=now, cursor=hex(dev.u32(0xC00F9C80))))
        if name == "missing":
            check("missing-sample-file-clears-old-bank", not now and bool(old), now)

    for name in PROJECTS:
        phase = f"pattern-file-{name}"
        path = project_path(name, "e2sPattern.all")
        uc.mem_write(SCRATCH, path.encode("ascii") + b"\0")
        file_object, output, count = SCRATCH + 0x1000, SCRATCH + 0x2000, SCRATCH + 0x7000
        uc.mem_write(file_object, bytes(0x840))
        opened = dev.call(F_OPEN, file_object, SCRATCH, 1)
        header_status = dev.call(F_READ, file_object, output, 0x100, count)
        header_ok = dev.u32(count) == 0x100 and dev.read(output, 0x100) == files[path][:0x100]
        reads = []
        for index in (0, 249):
            offset = 0x10100 + index * 0x4000
            seek_status = dev.call(F_SEEK, file_object, offset)
            read_status = dev.call(F_READ, file_object, output, 0x4000, count)
            matches = dev.u32(count) == 0x4000 and dev.read(output, 0x4000) == files[path][offset:offset + 0x4000]
            reads.append(dict(index=index, seek=seek_status, read=read_status, matches=matches))
        closed = dev.call(F_CLOSE, file_object)
        check(f"native-fatfs-pattern-path-{name}", opened == header_status == closed == 0 and header_ok
              and all(item["seek"] == item["read"] == 0 and item["matches"] for item in reads),
              dict(open=opened, header=header_status, header_matches=header_ok, records=reads, close=closed))

    check("file-path-does-not-replace-pattern-bank", digest(dev.read(PATTERNS, 250 * 0x4000)) == bank_before, bank_before)
    check("no-flash-change", user_flash(machine) == flash_before, dict(sha256=digest(flash_before)))
    check("no-card-change-after-boot", digest(image) == card_before, dict(before=card_before, after=digest(image)))
    check("no-firmware-assert", not machine.asserts, machine.asserts)
    return dict(build=machine.profile.build, checks=checks, operations=operations,
                assumptions=["Boot redirects only FatFs path arguments in emulator RAM.",
                             "Runtime commands use a synthetic command object from the UI tick, not the native command queue.",
                             "Pattern paths use native FatFs reads, not a project loader or native all-pattern import.",
                             "Emulated DSP, synthetic factory bank, no sound or hardware verification."])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vsb", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.vsb.read_bytes()[0x100:])
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(build=result["build"], checks=len(result["checks"]),
                          failed=[item["name"] for item in result["checks"] if not item["ok"]])))
    return 0 if all(item["ok"] for item in result["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
