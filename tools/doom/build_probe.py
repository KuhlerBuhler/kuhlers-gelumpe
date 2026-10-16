#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Baut die gepinnte Doom-Engine als eigenständige ARM926-Emulatorprobe."""
import argparse
import json
from pathlib import Path
import re
import subprocess

REVISION = "e257a09527062bfb986b6e5e0780839b6cbd5b71"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--zone-mib", default=16, type=int, choices=range(4,33))
    parser.add_argument("--monsters", action="store_true")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise SystemExit(f"Andere Engineversion: {revision}, erwartet {REVISION}")
    if subprocess.check_output(["git", "-C", str(args.source), "status", "--porcelain"], text=True).strip():
        raise SystemExit("Die Enginequelle enthält lokale Änderungen")
    source = args.source / "doomgeneric"
    here = Path(__file__).resolve().parent
    args.output.mkdir(parents=True, exist_ok=True)
    gcc = args.toolchain / "bin/arm-none-eabi-gcc"
    flags = ["-mcpu=arm926ej-s", "-marm", "-mfloat-abi=soft", "-Os", "-ffunction-sections", "-fdata-sections", "-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE", "-DDOOMGENERIC_RESX=320", "-DDOOMGENERIC_RESY=200", "-Wno-error=implicit-function-declaration", '-DPROBE_ZONE_MIB="' + str(args.zone_mib) + '"', "-I", str(source)]
    if args.monsters:
        flags.append("-DPROBE_MONSTERS=1")
    object_names = re.search(r"^SRC_DOOM = (.+)$", (source / "Makefile").read_text(), re.M)[1].split()
    c_sources = [source / name.replace(".o", ".c") for name in object_names if name != "doomgeneric_xlib.o"]
    c_sources.append(here / "probe.c")
    objects = []
    for path in c_sources:
        obj = args.output / (path.stem + ".o")
        subprocess.run([str(gcc), *flags, "-c", str(path), "-o", str(obj)], check=True)
        objects.append(str(obj))
    elf = args.output / "doom-probe.elf"
    subprocess.run([str(gcc), *flags, "-nostartfiles", "-Wl,--gc-sections", "-Wl,-T," + str(here / "probe.ld"), "-Wl,-Map," + str(args.output / "doom-probe.map"), *objects, "-o", str(elf), "-lm", "-lc", "-lgcc"], check=True)
    subprocess.run([str(args.toolchain / "bin/arm-none-eabi-objcopy"), "-O", "binary", str(elf), str(args.output / "doom-probe.bin")], check=True)
    for tool, options, destination in [("size", [str(elf)], "size.txt"), ("readelf", ["-h", "-A", str(elf)], "architecture.txt"), ("nm", ["-n", str(elf)], "symbols.txt"), ("nm", ["-u", str(elf)], "undefined.txt")]:
        (args.output / destination).write_bytes(subprocess.check_output([str(args.toolchain / ("bin/arm-none-eabi-" + tool)), *options]))
    (args.output / "build.json").write_text(json.dumps({"revision":revision, "monsters":args.monsters, "sound":False, "objects":len(objects), "flags":flags, "compiler":subprocess.check_output([str(gcc), "--version"], text=True).splitlines()[0]}, indent=2) + "\n")
    print((args.output / "size.txt").read_text())


if __name__ == "__main__":
    main()
