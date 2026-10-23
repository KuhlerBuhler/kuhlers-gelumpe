#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Baut einen geprüften Quellsnapshot ohne Git oder Netzwerk erneut."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from artifacts import external_output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = external_output(args.output)
    bundle = Path(__file__).resolve().parents[3]
    inventory = json.loads((bundle / "sources.json").read_text())
    for name, expected in inventory["files"].items():
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != expected:
            raise SystemExit("Veränderte Snapshotdatei: " + name)
    build = json.loads((bundle / "build.json").read_text())
    gcc = args.toolchain / "bin/arm-none-eabi-gcc"
    if subprocess.check_output([str(gcc), "--version"], text=True).splitlines()[0] != build["compiler"]:
        raise SystemExit("Compiler stimmt nicht mit dem Snapshot überein")
    manifests = sorted(args.toolchain.glob("*-manifest.txt"))
    if len(manifests) != 1 or manifests[0].read_bytes() != (bundle / "toolchain/manifest.txt").read_bytes():
        raise SystemExit("Toolchainmanifest stimmt nicht mit dem Snapshot überein")
    source = bundle / "doomgeneric/doomgeneric"
    here = bundle / "gelumpe/tools/doom"
    substitutions = {build["engine_source"]: str(source), build["adapter_source"]: str(here)}
    flags = list(build["flags"])
    for index, flag in enumerate(flags):
        for previous, current in substitutions.items():
            flag = flag.replace(previous, current)
        flags[index] = flag
    object_names = re.search(r"^SRC_DOOM = (.+)$", (source / "Makefile").read_text(), re.M)[1].split()
    paths = [source / name.replace(".o", ".c") for name in object_names if name != "doomgeneric_xlib.o"]
    paths.append(here / "runtime.c")
    output.mkdir(parents=True, exist_ok=True)
    objects = []
    for path in paths:
        obj = output / (path.stem + ".o")
        subprocess.run([str(gcc), *flags, "-c", str(path), "-o", str(obj)], check=True)
        objects.append(str(obj))
    elf = output / "doom-runtime.elf"
    subprocess.run([str(gcc), *flags, "-nostartfiles", "-Wl,--gc-sections", "-Wl,--wrap=I_Quit", "-Wl,--wrap=R_RenderPlayerView",
                    "-Wl,-T," + str(here / "runtime.ld"), "-Wl,-Map," + str(output / "doom-runtime.map"),
                    *objects, "-o", str(elf), "-lm", "-lc", "-lgcc"], check=True)
    binary = output / "doom-runtime.bin"
    subprocess.run([str(args.toolchain / "bin/arm-none-eabi-objcopy"), "-O", "binary", str(elf), str(binary)], check=True)
    actual = hashlib.sha256(binary.read_bytes()).hexdigest()
    report = {"expected_sha256": build["binary_sha256"], "actual_sha256": actual,
              "matches": actual == build["binary_sha256"], "network_used": False}
    (output / "rebuild.json").write_text(json.dumps(report, indent=2) + "\n")
    if not report["matches"]:
        raise SystemExit("Neubau weicht von der ursprünglichen Binärdatei ab")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
