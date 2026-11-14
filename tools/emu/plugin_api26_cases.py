"""Emulator cases of plugin API 26: korg.system.device, korg.system.version and korg.system.limits.* read what the runtime knows
about the device it runs on. The device is the build the runtime was made for, the version the text of the patch blech-version,
the effect counts what the firmware's own count functions return at the time of the read, the sample slots 1000 on the
Sampler and 0 on the blue Synth. None of them can be set.

    python3 tools/emu/plugin_api26_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api26-device-info.md.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
import synthaddr  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

VERSION_TEXT = 0xC014FCF0       # the patch blech-version: "BLECH x.y.z", NUL padded, FF where the set does not have it
COUNT_IFX, COUNT_MFX = 0xC003EFDC, 0xC003EFE4
LEAVES = {"device": "korg.system.device", "version": "korg.system.version", "ifx": "korg.system.limits.ifxTypes",
          "mfx": "korg.system.limits.mfxTypes", "samples": "korg.system.limits.samples"}

PROGRAM = "let device = -9; let version = -9; let ifx = -9; let mfx = -9; let samples = -9;\n" + \
    "korg.onEvent(\"ready\", () => {\n" + \
    "".join(f"  {name} = {path};\n" for name, path in LEAVES.items()) + "});"


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"api26": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"plugin_api26:{name}", "ok": bool(ok), "detail": str(detail)}


def version_number(text):
    """What objects_info_version makes of the 16 bytes: x * 10000 + y * 100 + z, 0 without "BLECH "."""
    if not text.startswith(b"BLECH "):
        return 0
    parts = (text[6:].split(b"\0")[0].decode("latin1").split(".") + ["0", "0", "0"])[:3]
    return int(parts[0] or 0) * 10000 + int(parts[1] or 0) * 100 + int(parts[2] or 0)


class World:
    def __init__(self, vsb, flash=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled({"api26": PROGRAM})
        self.built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(0.3)

    def address(self, sampler):
        return synthaddr.tr(sampler) if self.build == "synth" else sampler

    def want(self):
        return {"device": script_hooks.BUILD_DEVICES[self.build], "version": version_number(self.dev.read(VERSION_TEXT, 16)),
                "ifx": self.dev.call(self.address(COUNT_IFX)), "mfx": self.dev.call(self.address(COUNT_MFX)),
                "samples": 0 if self.build == "synth" else 1000}


def plugin_cases(w):
    want = w.want()
    program = w.request["programs"]["api26"]
    at = script_cases.install(w.dev, w.built, w.request["programs"], ["api26"])["api26"]
    w.dev.run(0.5)
    seen = script_cases.variables(w.dev, at, program)
    return [entry("plugin_reads_the_device", {k: seen.get(k) for k in want} == want and not w.dev.m.asserts,
                  f"build {w.build}: read {dict((k, seen.get(k)) for k in want)}, want {want}, asserts {w.dev.m.asserts}")]


def glue_cases(w):
    """korg.get on each leaf as the VM calls it, and korg.set refused: the leaves are read only."""
    ids = {name: 48 + i for i, name in enumerate(LEAVES)}
    get, put = w.built.symbols["script_object_get_glue"], w.built.symbols["script_object_set_glue"]
    seen = {name: w.dev.call(get, leaf, 0xFFFFFFFF) for name, leaf in ids.items()}
    want = w.want()
    out = [entry("glue_reads", seen == want and not w.dev.m.asserts, f"read {seen}, want {want}")]
    before = {name: w.dev.call(get, leaf, 0xFFFFFFFF) for name, leaf in ids.items()}
    for leaf in ids.values():
        w.dev.call(put, leaf, 0xFFFFFFFF, 7)
    after = {name: w.dev.call(get, leaf, 0xFFFFFFFF) for name, leaf in ids.items()}
    out.append(entry("set_changes_nothing", before == after and not w.dev.m.asserts, f"before {before}, after korg.set(leaf, -1, 7) {after}"))
    return out


def cases(vsb, flash=None):
    w = World(vsb, flash)
    out = glue_cases(w)
    out += plugin_cases(World(vsb, flash))
    return out


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
