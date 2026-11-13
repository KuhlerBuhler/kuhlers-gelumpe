"""Watch the sample swap of a running BLECH firmware and report every sample it loads: RAM to DSP or card to DSP.

Read only: the tool sends BLECH INFO and READ, never WRITE or EXEC, and touches neither the card nor flash. It first
compares the swap's code on the device with what tools/patch/sample_swap.py builds for the own original VSB, then polls
the swap's state. Each finished load is one line: source, PCM bytes, the swap's own timer 3 ticks of that load (card read,
24 to 16 bit conversion or cache copy, and the bounded DSP writes, summed over its chunks) and the throughput.

    python tools/device/sample_swap_stats.py --plan
    python tools/device/sample_swap_stats.py --watch 120 --vsb "$OWN_VSB" [--json "$HOME/swap-stats.jsonl"]

Without --watch nothing is sent. Play patterns on the device while it watches: switching to a pattern whose samples are
only on the card measures card to DSP, switching to a neighbour the swap has read ahead measures RAM to DSP.
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "patch"))

import sample_swap  # noqa: E402

TIMER_HZ = 150_000_000
SOURCES = {0: "card", 1: "ram"}


def decode(raw):
    """The swap's state words by name."""
    return {name: struct.unpack_from("<I", raw, offset)[0] for name, offset in sample_swap.OFF.items()}


def load_line(state):
    ticks = state["STAT_TICKS"]
    length = state["STAT_BYTES"]
    seconds = ticks / TIMER_HZ if ticks else None
    return dict(count=state["STAT_COUNT"], source=SOURCES.get(state["STAT_SRC"], state["STAT_SRC"]), bytes=length, ticks=ticks,
                milliseconds=round(seconds * 1000, 3) if seconds else None,
                mib_per_second=round(length / 1048576 / seconds, 2) if seconds else None)


def verify_code(link, firmware):
    screens = sample_swap.screens_of(firmware)
    sections, _ = sample_swap.build_code(screens)
    for at, data in sections:
        if link.read(at, len(data)) != data:
            raise ValueError(f"the sample swap's code differs at {at:#x}: not this BLECH build, or the swap is not installed")


def watch(link, seconds, out=None, poll=0.5, clock=time.monotonic, sleep=time.sleep):
    state = decode(link.read(sample_swap.STATE, 4 * len(sample_swap.FIELDS)))
    if state["MODE"] != 1:
        raise ValueError(f"the swap is not on (mode {state['MODE']:#x}): the sample file is not larger than the user bank, "
                         "EXIT was held at power-on, or it switched itself off after a fault")
    lines, seen, end = [], state["STAT_COUNT"], clock() + seconds
    while clock() < end:
        sleep(poll)
        state = decode(link.read(sample_swap.STATE, 4 * len(sample_swap.FIELDS)))
        if state["MODE"] != 1:
            lines.append(dict(event="swap off", mode=state["MODE"]))
            break
        if state["STAT_COUNT"] != seen:
            seen = state["STAT_COUNT"]
            line = load_line(state)
            lines.append(line)
            print(json.dumps(line), flush=True)
            if out:
                with out.open("a") as f:
                    f.write(json.dumps(line) + "\n")
    return lines


def arguments(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--plan", action="store_true")
    p.add_argument("--watch", type=float, metavar="SECONDS")
    p.add_argument("--vsb", type=Path)
    p.add_argument("--json", type=Path)
    return p.parse_args(argv)


def main(argv=None):
    a = arguments(argv)
    if not a.watch:
        print(json.dumps(dict(mode="offline plan", device="no device contact", reads=f"{4 * len(sample_swap.FIELDS)} bytes at {sample_swap.STATE:#x}",
                              sends=["BLECH INFO", "BLECH READ"], never=["WRITE", "EXEC", "card", "flash"],
                              measures=["card to DSP per sample", "RAM to DSP per sample"]), indent=2))
        return
    if not a.vsb:
        raise ValueError("--watch needs --vsb, the own original Sampler 2.02 file")
    if a.json and any(parent.joinpath(".git").exists() for parent in [a.json.resolve().parent, *a.json.resolve().parents]):
        raise ValueError("write the report outside the repository")
    import sample_swap_probe as old
    from led_show import mido_ask
    firmware, _ = old.own_firmware(a.vsb)
    ask = mido_ask()
    found = ask([0xF0, 0x42, 0x50, 0, 0, 0xF7])
    if len(found) < 8 or found[:4] != [0xF0, 0x42, 0x50, 1]:
        raise ValueError("no Electribe discovery reply")
    link = old.Link(ask, found[4] & 15, found[6])
    link.info()
    verify_code(link, firmware)
    watch(link, a.watch, a.json)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, TimeoutError, OSError) as error:
        raise SystemExit(str(error))
