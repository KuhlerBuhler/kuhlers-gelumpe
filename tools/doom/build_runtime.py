#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Baut die gepinnte Doom-Engine als eigenständige ARM926-Firmwareanwendung."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import struct
from artifacts import external_output
from source_package import snapshot, source_hashes

REVISION = "e257a09527062bfb986b6e5e0780839b6cbd5b71"



def generate_layout(gcc, toolchain, flags, here, output):
    obj = output / "runtime-layout.o"
    binary = output / "runtime-layout.bin"
    subprocess.run([str(gcc), *flags, "-c", str(here / "runtime_layout.c"), "-o", str(obj)], check=True)
    subprocess.run([str(toolchain / "bin/arm-none-eabi-objcopy"), "--only-section", ".doom_layout", "-O", "binary", str(obj), str(binary)], check=True)
    names = ["version", "player_size", "player_mo_offset", "player_ammo_offset",
             "player_readyweapon_offset", "player_health_offset", "mobj_x_offset",
             "mobj_y_offset", "ammo_slot_size", "player_usedown_offset",
             "player_readyweapon_size", "player_usedown_size", "boolean_size"]
    values = struct.unpack("<" + "I" * len(names), binary.read_bytes())
    layout = dict(zip(names, values))
    layout["revision"] = REVISION
    (output / "layout.json").write_text(json.dumps(layout, indent=2) + "\n")
    return layout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--layout-only", action="store_true")
    args = parser.parse_args()
    args.output = external_output(args.output)
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise SystemExit(f"Andere Engineversion: {revision}, erwartet {REVISION}")
    if subprocess.check_output(["git", "-C", str(args.source), "status", "--porcelain"], text=True).strip():
        raise SystemExit("Die Enginequelle enthält lokale Änderungen")
    source = args.source / "doomgeneric"
    here = Path(__file__).resolve().parent
    args.output.mkdir(parents=True, exist_ok=True)
    gcc = args.toolchain / "bin/arm-none-eabi-gcc"
    flags = ["-mcpu=arm926ej-s", "-marm", "-mfloat-abi=soft", "-Os", "-ffunction-sections", "-fdata-sections", "-DNORMALUNIX", "-DLINUX", "-DSNDSERV", "-D_DEFAULT_SOURCE", "-DDOOMGENERIC_RESX=320", "-DDOOMGENERIC_RESY=200", "-Wno-error=implicit-function-declaration", "-I", str(source), "-ffile-prefix-map=" + str(source) + "=doomgeneric",
             "-ffile-prefix-map=" + str(here) + "=gelumpe/tools/doom"]
    layout = generate_layout(gcc, args.toolchain, flags, here, args.output)
    if args.layout_only:
        print(json.dumps(layout))
        return
    object_names = re.search(r"^SRC_DOOM = (.+)$", (source / "Makefile").read_text(), re.M)[1].split()
    c_sources = [source / name.replace(".o", ".c") for name in object_names if name != "doomgeneric_xlib.o"]
    c_sources.append(here / "runtime.c")
    initial_sources = source_hashes(here.parents[1])
    objects = []
    for path in c_sources:
        obj = args.output / (path.stem + ".o")
        subprocess.run([str(gcc), *flags, "-c", str(path), "-o", str(obj)], check=True)
        objects.append(str(obj))
    elf = args.output / "doom-runtime.elf"
    subprocess.run([str(gcc), *flags, "-nostartfiles", "-Wl,--gc-sections", "-Wl,--wrap=I_Quit", "-Wl,-T," + str(here / "runtime.ld"), "-Wl,-Map," + str(args.output / "doom-runtime.map"), *objects, "-o", str(elf), "-lm", "-lc", "-lgcc"], check=True)
    subprocess.run([str(args.toolchain / "bin/arm-none-eabi-objcopy"), "-O", "binary", str(elf), str(args.output / "doom-runtime.bin")], check=True)
    for tool, options, destination in [("size", [str(elf)], "size.txt"), ("readelf", ["-h", "-A", str(elf)], "architecture.txt"), ("nm", ["-n", str(elf)], "symbols.txt"), ("nm", ["-u", str(elf)], "undefined.txt")]:
        (args.output / destination).write_bytes(subprocess.check_output([str(args.toolchain / ("bin/arm-none-eabi-" + tool)), *options]))
    undefined = (args.output / "undefined.txt").read_text().strip()
    if undefined:
        raise SystemExit("Nicht aufgelöste Symbole: " + undefined)
    symbols = {}
    for line in (args.output / "symbols.txt").read_text().splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    blob = (args.output / "doom-runtime.bin").read_bytes()
    shared_address = int(re.search(r"^#define DOOM_SHARED_ADDRESS (0x[0-9A-Fa-f]+)u$",
                                   (here / "runtime_abi.h").read_text(), re.M)[1], 16)
    manifest = {"shared_address": shared_address, "revision": REVISION, "length": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
                "entry": symbols["doom_runtime_start"], "base": 0xC1000000, "end": 0xC1800000,
                "bss_start": symbols["__bss_start"], "bss_end": symbols["__bss_end"],
                "heap_start": symbols["__heap_start"], "heap_limit": symbols["__heap_limit"],
                "stack_bottom": symbols["__stack_bottom"], "stack_top": symbols["__stack_top"]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if source_hashes(here.parents[1]) != initial_sources:
        raise SystemExit("Buildquellen während des Builds verändert; erneut bauen")
    build = {"revision": revision, "monsters": True, "sound": False,
             "objects": len(objects), "flags": flags,
             "engine_source": str(source), "adapter_source": str(here),
             "compiler": subprocess.check_output([str(gcc), "--version"], text=True).splitlines()[0],
             "compiler_configuration": subprocess.check_output([str(gcc), "-v"], text=True, stderr=subprocess.STDOUT),
             "own_source_sha256": source_hashes(here.parents[1]),
             "binary_sha256": manifest["sha256"]}
    (args.output / "build.json").write_text(json.dumps(build, indent=2) + "\n")
    snapshot(args.source, REVISION, args.toolchain, args.output, build)
    print((args.output / "size.txt").read_text())
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
