#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Baut den Doom-SD-Lader und eine lokale, streng begrenzte Firmwarekopie."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from artifacts import external_output

HERE = Path(__file__).resolve().parent
LAYOUT = json.loads((HERE / "layout.json").read_text())
BASE, SITE = LAYOUT["bootstrap"], LAYOUT["site"]
RESERVED_END = LAYOUT["end"]
SUPPORTED = {LAYOUT["originalSha256"]}


def validate_base(vsb, original=None, patch_set=None, extra_patches=()):
    if hashlib.sha256(vsb).hexdigest() in SUPPORTED:
        return {"original_sha256": hashlib.sha256(vsb).hexdigest(), "patches": []}
    if original is None:
        raise ValueError("Unbekannte Firmware; aktuelle BLECH-Basis braucht --original")
    command = ["node", str(HERE / "validate_baseline.mjs"), str(original.resolve())]
    command.append(str(patch_set.resolve()) if patch_set is not None else "data/patches/blech.json")
    command.extend(str(path.resolve()) for path in extra_patches)
    result = subprocess.run(command, input=bytes(vsb), capture_output=True, check=False)
    if result.returncode:
        raise ValueError("Firmware-Herkunft oder Speicherbelegung ungültig: " + result.stderr.decode().strip())
    return json.loads(result.stdout)


def branch(source, target):
    delta = target - source - 8
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError("ARM-Sprungziel außerhalb des Bereichs")
    return struct.pack("<I", 0xEB000000 | ((delta >> 2) & 0xFFFFFF))


def validate_delta(base, image):
    if len(base) != len(image):
        raise ValueError("Basis und Produktimage haben unterschiedliche Länge")
    site, arena, end = (LAYOUT[key] - 0xC0000000 + 0x100
                        for key in ("site", "bootstrap", "end"))
    if any(base[start:stop] != image[start:stop]
           for start, stop in [(0, site), (site + 4, arena), (end, len(base))]):
        raise ValueError("Falsche Referenzbasis: Produktimage unterscheidet sich außerhalb der Doom Bereiche")


def patch_image(vsb, bootstrap, *, original=None, patch_set=None, extra_patches=()):
    validate_base(vsb, original, patch_set, extra_patches)
    if not bootstrap or len(bootstrap) > LAYOUT["codeEnd"] - BASE:
        raise ValueError("SD-Lader passt nicht in seinen Codebereich")
    offset = lambda a: a - 0xC0000000 + 0x100
    if len(vsb) < offset(RESERVED_END):
        raise ValueError("Firmware ist für den reservierten Bereich zu kurz")
    if vsb[offset(SITE):offset(SITE) + 4] != branch(SITE, LAYOUT["originalCall"]):
        raise ValueError("Unerwarteter Originalaufruf")
    if any(b != 255 for b in vsb[offset(BASE):offset(RESERVED_END)]):
        raise ValueError("Reservierter Code- oder Zustandsbereich ist belegt")
    out = bytearray(vsb)
    out[offset(SITE):offset(SITE) + 4] = branch(SITE, BASE)
    out[offset(BASE):offset(BASE) + len(bootstrap)] = bootstrap
    return bytes(out)


def validate_program(program, metadata):
    digest = hashlib.sha256(program).hexdigest()
    if metadata["sha256"] != digest or metadata["length"] != len(program):
        raise ValueError("Programm und Buildmanifest stimmen nicht überein")
    if metadata["entry"] != 0xC1000000 or len(program) > 0x7F0000:
        raise ValueError("Programm verletzt Ladegrenzen")
    if metadata.get("shared_address") != LAYOUT["shared"]:
        raise ValueError("Programm verwendet eine veraltete oder unbekannte Shared-Adresse")
    return digest


def compile_bootstrap(program, metadata, toolchain, output):
    """Compile the SD loader for exactly this program (pinned by length and SHA-256); returns the binary's path and the digest."""
    here = Path(__file__).resolve().parent
    digest = validate_program(program, metadata)
    output.mkdir(parents=True, exist_ok=True)
    header = "#define EXPECTED_PROGRAM_BYTES " + str(len(program)) + "u\n"
    header += "#define EXPECTED_PROGRAM_SHA256 {" + ",".join("0x" + digest[i:i+2] for i in range(0,64,2)) + "}\n"
    (output / "expected_program.h").write_text(header)
    gcc = toolchain / "bin/arm-none-eabi-gcc"
    flags = ["-mcpu=arm926ej-s", "-marm", "-mfloat-abi=soft", "-Os", "-ffreestanding", "-fno-builtin", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-I", str(output), "-I", str(here)]
    elf = output / "doom-bootstrap.elf"
    subprocess.run([str(gcc), *flags, "-nostdlib", "-Wl,-T," + str(here / "bootstrap.ld"), "-Wl,-Map," + str(output / "doom-bootstrap.map"), str(here / "bootstrap.S"), str(here / "bootstrap.c"), str(here / "sha256.c"), "-o", str(elf), "-lgcc"], check=True)
    binary = output / "doom-bootstrap.bin"
    subprocess.run([str(toolchain / "bin/arm-none-eabi-objcopy"), "-O", "binary", str(elf), str(binary)], check=True)
    undefined = subprocess.check_output([str(toolchain / "bin/arm-none-eabi-nm"), "-u", str(elf)], text=True)
    if undefined.strip():
        raise ValueError("Nicht aufgelöste Symbole: " + undefined)
    return binary, digest


def build(args):
    args.output = external_output(args.output)
    original, patch_set = getattr(args, "original", None), getattr(args, "patch_set", None)
    extra_patches = getattr(args, "extra_patch", ())
    base_image = args.base.read_bytes()
    provenance = validate_base(base_image, original, patch_set, extra_patches)
    program = args.program.read_bytes()
    metadata = json.loads(args.program.with_name("manifest.json").read_text())
    binary, digest = compile_bootstrap(program, metadata, args.toolchain, args.output)
    image = patch_image(base_image, binary.read_bytes(), original=original, patch_set=patch_set, extra_patches=extra_patches)
    target = args.output / "SYSTEM-doom-emulator.VSB"
    target.write_bytes(image)
    report = dict(base_sha256=hashlib.sha256(base_image).hexdigest(), sha256=hashlib.sha256(image).hexdigest(), program_sha256=digest, program_bytes=len(program), bootstrap_bytes=binary.stat().st_size, image=str(target), site=hex(SITE), bootstrap=hex(BASE), reserved_end=hex(RESERVED_END), provenance=provenance, hardware_verified=False)
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--original", type=Path, help="Hashgepinntes Original für den vollständigen aktuellen BLECH-Wiederaufbau")
    parser.add_argument("--patch-set", type=Path, help="BLECH-Patchsatz, standardmäßig data/patches/blech.json")
    parser.add_argument("--extra-patch", type=Path, action="append", default=[], help="Zusätzlicher geprüfter Patch, Teil des vollständigen Wiederaufbaus")
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(parser.parse_args()), indent=2))
