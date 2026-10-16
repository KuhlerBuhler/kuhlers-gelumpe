#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prüft TAP-Motion und optional SysEx im normalen Start der Doom-Firmware."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/emu"), str(ROOT / "tools/patch")]
from artifacts import external_output

TAP_GROUPS = (0, 3, 6)


def doom_hook(payload):
    layout = json.loads((Path(__file__).parent / "layout.json").read_text())
    offset = layout["site"] - 0xC0000000
    if len(payload) < offset + 4:
        return False
    word = struct.unpack_from("<I", payload, offset)[0]
    delta = (word & 0xFFFFFF) - (0x1000000 if word & 0x800000 else 0)
    return word >> 24 == 0xEB and layout["site"] + 8 + delta * 4 == layout["bootstrap"]


def external_cases(path):
    path = path.resolve()
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("doom_external_sysex_cases", path)
    if spec is None or spec.loader is None:
        raise ValueError("SysEx-Fallquelle kann nicht geladen werden")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(image, flash_paths, sysex_path=None):
    started = time.monotonic()
    image_bytes = image.read_bytes()
    payload = image_bytes[0x100:]
    entries = []
    groups = {"tap_motion": [], "sysex": []}

    def add(name, ok, detail):
        entries.append(dict(id=name, ok=bool(ok), detail=str(detail)))

    def group(module, number, family, flash):
        before = len(entries)
        try:
            found = module.group_entries(payload, flash, number)
            if not found or any(not isinstance(entry.get("ok"), bool) or not entry.get("id") for entry in found):
                raise ValueError("Fallgruppe liefert keine gültigen Prüfeinträge")
            entries.extend(found)
        except Exception as exc:
            add(f"{family}:group-{number}", False, f"{type(exc).__name__}: {exc}")
        groups[family].append(number)
        print(json.dumps(dict(group=family, number=number, checks=len(entries)-before,
                              ok=all(entry["ok"] for entry in entries[before:]))), file=sys.stderr, flush=True)

    add("doom:boot-hook", doom_hook(payload), "Startaufruf verzweigt in den deklarierten Doom-Lader")
    sysex = None
    if entries[-1]["ok"]:
        try:
            import tap_motion_cases as tap
            from machine import load_flash
            flash = load_flash(flash_paths) if flash_paths else None
            add("tap_motion:hooks", tap.has_hooks(payload), "TAP-Hook der neuen Firmware vorhanden")
            if sysex_path is not None:
                sysex = external_cases(sysex_path)
                add("sysex:hooks", sysex.has_hooks(payload), "Beide SysEx-Hooks der neuen Firmware vorhanden")
            if all(entry["ok"] for entry in entries):
                for number in TAP_GROUPS:
                    group(tap, number, "tap_motion", flash)
                if sysex is not None:
                    for number in range(len(sysex.GROUPS)):
                        group(sysex, number, "sysex", flash)
        except Exception as exc:
            add("compatibility:setup", False, f"{type(exc).__name__}: {exc}")
    return dict(ok=bool(entries) and all(entry["ok"] for entry in entries), entries=entries, groups=groups,
                image_sha256=hashlib.sha256(image_bytes).hexdigest(),
                sysex_cases_sha256=hashlib.sha256(sysex_path.read_bytes()).hexdigest() if sysex_path else None,
                wall_seconds=time.monotonic()-started,
                scope="Normale Firmware im Emulator: TAP-Schalten, SHIFT+TAP, App-Tastenerfassung und optional SysEx; kein Gerätetest")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--flash", type=Path, nargs="*", default=[])
    parser.add_argument("--sysex-cases", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report_path = external_output(args.report or Path(tempfile.mkdtemp(prefix="gelumpe-doom-compat-")) / "report.json")
    import lifetime
    lifetime.exit_with_parent()
    report = check(args.image, args.flash, args.sysex_cases)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(ok=report["ok"], passed=sum(entry["ok"] for entry in report["entries"]),
                          count=len(report["entries"]), groups=report["groups"], report=str(report_path))))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
