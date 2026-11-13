# SPDX-License-Identifier: GPL-2.0-only
"""The interface between CPU and DSP, checked on every patched copy (check.py, also --quick): the DSP model (dsp_model.py)
listens from power-on while the copy starts, plays part 1 from its pad and runs the pattern once.

Asked on the DSP's side of the host port, for any build and any patch, since they hold for Korg's firmware, Hacktribe and
BLECH on the red and the blue device alike (docs/messungen/2026-11-12-dsp-modell.md, "Schnittstelle im Patcher"):

- start: every part's insert field and the master field get an effect unit, no field stays muted, no part is switched off
- pad: pad 1 opens a voice of part 1 and its release closes it
- play: the pattern opens voices and closes each of them again by STOP
- transfers: every mailbox message has its header and a command the build's DSP takes, no transfer ends short, every FIFO
  buffer has its end mark

    tools/emu/.venv/bin/python tools/emu/dsp_cases.py --vsb SYSTEM.VSB [--flash dump.bin]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dsp_model import MASTER_FX, PARTS, DspModel  # noqa: E402
from machine import load_flash  # noqa: E402
from menu_cases import card_image  # noqa: E402
from pswitch_cases import KEYS  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402


def entry(name, ok, detail):
    return {"id": f"dsp:{name}", "ok": bool(ok), "detail": str(detail)}


def cases(payload, flash=None):
    dev = Dev(payload, flash)
    m = dev.m
    dsp = DspModel.attach(m)
    m.insert_card(SDCard(MemoryMedium(card_image())))
    dev.run(3.0)
    fields = [2 * p for p in range(PARTS)] + [MASTER_FX]
    units = {f: (dsp.effect(f) or {}).get("unit") for f in fields}
    empty = [f for f, u in units.items() if u is None]
    muted = sorted(f for f, v in dsp.muted.items() if v)
    off = dsp.parts_switched_off()
    out = [entry("start_reaches_the_dsp", dsp.messages and not empty and not muted and not off and not m.asserts,
                 f"{dsp.messages} mailbox messages, fields without a unit {empty}, fields muted {muted}, parts switched off {off}")]

    gates = len(dsp.gates)
    m.send([4, 0, 0, 100, 1])
    dev.run(0.1)
    m.send([4, 0, 0, 0, 0])
    dev.run(0.5)
    pad = [(part, on) for _, _, part, on in dsp.gates[gates:]]
    out.append(entry("pad_opens_and_closes_a_voice", pad[:1] == [(0, 1)] and (0, 0) in pad and not dsp.voices(),
                     f"gates of pad 1 (part, on) {pad}, voices open after {dsp.voices()}"))

    gates = len(dsp.gates)
    dev.press(KEYS["play"], 1.5)
    dev.press(KEYS["play"], 0.5)
    played = [(part, on) for _, _, part, on in dsp.gates[gates:]]
    opened = sum(on for _, on in played)
    out.append(entry("play_opens_and_closes_voices", opened and opened * 2 == len(played) and not dsp.voices(),
                     f"{opened} notes opened, {len(played) - opened} closed, voices open after STOP {dsp.voices()}"))

    out.append(entry("transfers_are_well_formed", not dsp.faults and not m.asserts,
                     f"{dsp.messages} mailbox messages, {len(dsp.fifo)} FIFO entries, faults {dsp.faults[:5]}"))
    return out


def cases_task():
    """cases in a worker (parallel.py)."""
    import parallel
    return cases(parallel.shared["payload"], parallel.shared["flash"])


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    args = p.parse_args()
    result = cases(args.vsb.read_bytes()[0x100:], load_flash(args.flash) if args.flash else None)
    print(json.dumps(result, indent=1))
    return 0 if all(e["ok"] for e in result) else 1


if __name__ == "__main__":
    sys.exit(main())
