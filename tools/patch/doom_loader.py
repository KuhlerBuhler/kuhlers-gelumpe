"""Builds the Doom loader patch (docs/doom-lizenz.md, docs/messungen/2026-10-15-doom-sd-lader.md) for firmware 2.02, Hacktribe and Korg's own build.

SHIFT + TAP held at power-on starts Doom from the card, everything else starts the sampler. The loader is our own code
(AGPL, tools/doom/bootstrap.S, bootstrap.c, sha256.c): it sits in the erased run at 0xC017CC00, just behind the preset
knob table, the start function's call of 0xC002A35C (0xC002ADB0) goes through it, and it calls that function first, so the
start is the firmware's own until the keys say Doom. Then it enables startup and the card, reads
KORG/blechtribe/Doom/doom.bin, checks the exact length and the SHA-256 built into it (the file in third_party/doom) and only then
jumps into the program. A wrong or missing file stops with DOOM ERROR and a code, never in the sampler's way: without SHIFT + TAP
nothing of it runs but the key check. EXIT held at power-on is not SHIFT + TAP, so it keeps the patch out like every other.

    python3 tools/patch/doom_loader.py --vsb SYSTEM.VSB --toolchain ARM_GNU_14_2 [--out data/patches/doom-loader.json]

The loader is linked for exactly one doom.bin: change the file and the pin changes, so the patch must be built again.
Every address is a RAM address of the measured build; the file offset in the VSB is address - 0xC0000000 + 0x100.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/doom"))
sys.path.insert(0, str(Path(__file__).parent))

import build_bootstrap  # noqa: E402
import ramdecl  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000
LAYOUT = build_bootstrap.LAYOUT
PROGRAM = ROOT / "third_party/doom/doom.bin"


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build_patch(vsb, loader):
    site, base, code_end = LAYOUT["site"], LAYOUT["bootstrap"], LAYOUT["codeEnd"]
    if len(vsb) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    if not loader or len(loader) > code_end - base:
        raise SystemExit("the loader does not fit its code area")
    was = vsb[file_offset(site):file_offset(site) + 4]
    if was != build_bootstrap.branch(site, LAYOUT["originalCall"]):
        raise SystemExit("the start function does not call 0xC002A35C at the hook site")
    if any(b != 0xFF for b in vsb[file_offset(base):file_offset(LAYOUT["end"])]):
        raise SystemExit("the loader's RAM areas are not erased in this VSB")
    return {
        "format": "gelumpe-patch", "version": 1, "id": "doom-loader",
        "name": "Doom vom SD-Lader (SHIFT + TAP beim Einschalten)",
        "builds": ["hacktribe", "stock"],
        "changes": [
            {"file": file_offset(base), "bytes": loader.hex(), "expect": sha(b"\xff" * len(loader)),
             "note": "the SD loader: key check, card read of doom.bin, length and SHA-256 check, jump into the program"},
            {"file": file_offset(site), "bytes": build_bootstrap.branch(site, base).hex(), "expect": sha(was),
             "note": "the start function's call of 0xC002A35C goes through the loader, which calls it first"},
        ],
        "hooks": [
            {"site": f"0x{site:08X}", "kind": "call", "chain": "start", "position": "replace", "swallow": False,
             "note": "calls the original first and returns to it unless exactly SHIFT + TAP is held (EXIT held at power-on is not that)"},
        ],
        "startPhase": [
            {"file": file_offset(site), "length": 4,
             "why": "the start function runs the call at about 0.2 s, after the rescue paths, and now enters the loader"},
            {"file": file_offset(base), "length": len(loader),
             "why": "the loader runs with the call; without SHIFT + TAP it only compares the held keys and returns"},
        ],
        "ram": [
            ramdecl.area(base + len(loader), code_end - base - len(loader), "Doom SD loader code area behind the code",
                         "tools/doom/bootstrap.ld:doom_boot"),
            ramdecl.area(code_end, LAYOUT["bssEnd"] - code_end, "Doom SD loader state", "tools/doom/bootstrap.ld:__bss_end"),
            ramdecl.area(LAYOUT["shared"], LAYOUT["end"] - LAYOUT["shared"], "Doom runtime telemetry",
                         "tools/doom/runtime_abi.h:DOOM_SHARED_ADDRESS"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--toolchain", required=True, type=Path, help="Arm GNU Toolchain 14.2.Rel1, arm-none-eabi")
    p.add_argument("--program", type=Path, default=PROGRAM)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    metadata = json.loads(a.program.with_name("manifest.json").read_text())
    with tempfile.TemporaryDirectory(prefix="gelumpe-doom-loader-") as work:
        binary, digest = build_bootstrap.compile_bootstrap(a.program.read_bytes(), metadata, a.toolchain, Path(work))
        loader = binary.read_bytes()
    patch = build_patch(a.vsb.read_bytes(), loader)
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)
    print(f"loader {len(loader)} bytes for doom.bin {digest}", file=sys.stderr)


if __name__ == "__main__":
    main()
