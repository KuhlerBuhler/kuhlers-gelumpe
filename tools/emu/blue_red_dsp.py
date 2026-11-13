# SPDX-License-Identifier: GPL-2.0-only
"""The catalog's effects on the blue Electribe 2 against the red one, in the emulator (docs/messungen/2026-11-08-blau-eigene-effekte.md).

Takes two finished copies: Korg's red 2.02 with `data/patches/blech.json` and Korg's blue 2.02 with `data/patches/blech-synth.json`.
Both carry preset-tables and fx-catalog. For every slot behind the factory presets it selects the slot on each copy and compares
what the DSP gets (`same_dsp`: command, word count and data, a consistent shift of the target addresses allowed). The menus have
to be equally long, the names equal, and neither copy may assert.

    tools/emu/.venv/bin/python tools/emu/blue_red_dsp.py --red RED.VSB --blue BLUE.VSB
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

import preset_cases  # noqa: E402
from mfx_cases import blank_for, same_dsp  # noqa: E402

HEADER = 0x100
FACTORY = {"ifx": 38, "mfx": 32}        # Korg's 2.02, red and blue alike


def select(box, kind, index, n):
    """The DSP transfers of choosing `index` (0-based) in a menu of `n`."""
    if kind == "ifx":
        box.goto_ifx((index - 1) % n, n)
        box.dsp.clear()
        box.step_ifx(1)
    else:
        box.set_mfx(0 if index else 1)
        box.dsp.clear()
        box.set_mfx(index)
    box.dev.run(1.0)
    return box.dsp.changes()


def compare(red_payload, blue_payload):
    red = preset_cases.Box(red_payload, blank_for(red_payload))
    blue = preset_cases.Box(blue_payload, blank_for(blue_payload))
    out = []

    def add(name, ok, detail):
        out.append({"id": f"blue-red:{name}", "ok": bool(ok), "detail": detail})

    counts = {k: (red.count(k), blue.count(k)) for k in ("ifx", "mfx")}
    add("menus", all(r == b for r, b in counts.values()), f"menu lengths red/blue {counts}")
    for kind in ("ifx", "mfx"):
        n = counts[kind][1]
        for index in range(FACTORY[kind], n):
            name = lambda box: box.record(kind, index)[1:16].split(b"\0")[0].decode("latin1")
            a, b = select(red, kind, index, n), select(blue, kind, index, n)
            add(f"{kind}{index + 1}", name(red) == name(blue) and len(a) > 0 and same_dsp(a, b),
                f"{name(blue)!r}: {len(b)} transfers on the blue, {len(a)} on the red, the same: {same_dsp(a, b)}")
    add("no_assert", not red.dev.m.asserts and not blue.dev.m.asserts, f"red {red.dev.m.asserts[:2]}, blue {blue.dev.m.asserts[:2]}")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--red", required=True, type=Path)
    p.add_argument("--blue", required=True, type=Path)
    a = p.parse_args()
    checks = compare(a.red.read_bytes()[HEADER:], a.blue.read_bytes()[HEADER:])
    print(json.dumps(checks, indent=1, ensure_ascii=False))
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
