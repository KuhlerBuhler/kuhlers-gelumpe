#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sichert die tatsächlich gebauten Quellen ohne Firmware oder Spieldaten."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
import tarfile
from artifacts import external_output

OWN_SOURCES = ("LICENSE", "tools/doom/runtime.c", "tools/doom/runtime.ld",
               "tools/doom/runtime_abi.h", "tools/doom/runtime_layout.c",
               "tools/doom/native_power.h", "tools/doom/status_display.h",
               "tools/doom/rebuild_runtime.py",
               "tools/doom/build_runtime.py", "tools/doom/artifacts.py",
               "tools/doom/source_package.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def own_sources(root):
    return {name: (root / name).read_bytes() for name in OWN_SOURCES}


def validate_local_includes(files):
    for name, data in files.items():
        if not name.startswith("gelumpe/"):
            continue
        if not name.endswith((".c", ".h")):
            continue
        for include in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"', data.decode(errors="replace"), re.M):
            local = str(Path(name).parent / include)
            engine = "doomgeneric/doomgeneric/" + include
            if local not in files and engine not in files:
                raise ValueError("Snapshot enthält Include nicht: " + name + ": " + include)


def source_hashes(root):
    return {name: digest(data) for name, data in own_sources(root).items()}


def add_bytes(archive, name, data):
    item = tarfile.TarInfo(name)
    item.size = len(data)
    item.mode = 0o644
    archive.addfile(item, io.BytesIO(data))


def snapshot(engine, revision, toolchain, output, build):
    root = Path(__file__).resolve().parents[2]
    files = {"gelumpe/" + name: data for name, data in own_sources(root).items()}
    upstream = subprocess.check_output(["git", "-C", str(engine), "archive", revision])
    with tarfile.open(fileobj=io.BytesIO(upstream)) as source:
        for item in source.getmembers():
            if item.isfile():
                files["doomgeneric/" + item.name] = source.extractfile(item).read()
    validate_local_includes(files)
    manifests = sorted(toolchain.glob("*-manifest.txt"))
    if len(manifests) != 1:
        raise ValueError("Genau ein Toolchain-Manifest erforderlich")
    files["toolchain/manifest.txt"] = manifests[0].read_bytes()
    for notice in sorted((toolchain / "share/doc").glob("*/Copying.html")):
        files["toolchain/notices/" + notice.parent.name + "-Copying.html"] = notice.read_bytes()
    files["build.json"] = json.dumps(build, indent=2).encode() + b"\n"
    files["REBUILD.md"] = ("# Doom erneut bauen\n\n"
        "Python 3 und die in build.json benannte Arm-GNU-Toolchain bereitstellen.\n"
        "Das gesamte Archiv in ein neues Verzeichnis außerhalb eines Git-Repos entpacken.\n"
        "Keine Enginequelle herunterladen und kein Git-Repository anlegen.\n\n"
        "```sh\npython3 gelumpe/tools/doom/rebuild_runtime.py \\\n"
        "  --toolchain \"$doom_toolchain\" --output \"$doom_rebuild\"\n```\n\n"
        "Der Befehl prüft alle archivierten Quellen, Compiler und Toolchainmanifest,\n"
        "übernimmt SRC_DOOM aus dem archivierten Makefile und versetzt Quellpfade.\n"
        "Er baut nur aus diesem Archiv, vergleicht den Binärhash mit build.json\n"
        "und bricht bei Abweichung ab. Ergebnis steht in rebuild.json.\n"
        "Compiler, Laufzeitbibliotheken und deren Lizenzprüfung sind separat bereitzustellen.\n"
        "redistribution_ready bleibt false; dieses Archiv ist keine Distributionsfreigabe.\n").encode()
    metadata = {"engine_revision": revision, "files": {name: digest(data) for name, data in sorted(files.items())},
                "binary_sha256": build["binary_sha256"], "redistribution_ready": False,
                "missing": ["applicable runtime license notices and source obligations", "distribution review"]}
    files["sources.json"] = json.dumps(metadata, indent=2).encode() + b"\n"
    target = output / "doom-sources.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        for name, data in sorted(files.items()):
            add_bytes(archive, name, data)
    (output / "sources.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return target


def validate_build(build_dir, root):
    build = json.loads((build_dir / "build.json").read_text())
    if build.get("own_source_sha256") != source_hashes(root):
        raise ValueError("Buildquellen weichen vom aktuellen Arbeitsstand ab; neu bauen")
    if digest((build_dir / "doom-runtime.bin").read_bytes()) != build.get("binary_sha256"):
        raise ValueError("Enginebinärdatei passt nicht zum Build")
    sources = json.loads((build_dir / "sources.json").read_text())
    if sources["binary_sha256"] != build["binary_sha256"]:
        raise ValueError("Quellenpaket passt nicht zum Build")
    with tarfile.open(build_dir / "doom-sources.tar.gz") as archive:
        for name, expected in sources["files"].items():
            if digest(archive.extractfile(name).read()) != expected:
                raise ValueError("Quellenpaket verändert: " + name)
    return build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = external_output(args.output)
    root = Path(__file__).resolve().parents[2]
    build = validate_build(args.build, root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "distribution-review.json").write_text(json.dumps({
        "binary_sha256": build["binary_sha256"], "redistribution_ready": False,
        "sources": str((args.build / "doom-sources.tar.gz").resolve()),
        "required": ["GPLv3 license text", "GCC Runtime Library Exception notice",
                     "matching newlib file-license notices; assess any applicable source obligations",
                     "verify libgcc Runtime Library Exception applicability",
                     "WAD license and credits if distributed", "distribution review"],
    }, indent=2) + "\n")
    print("Quellen und Binärdatei stimmen überein; Weitergabe bleibt bis zur Distributionsprüfung gesperrt.")


if __name__ == "__main__":
    main()
