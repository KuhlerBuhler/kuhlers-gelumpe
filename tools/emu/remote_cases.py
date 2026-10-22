# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the keys from the laptop (tools/patch/script_remote.s, KORG.press against the device).

check.py runs `cases` on every patched sampler copy that carries the BLECH menu. A command word in the card work area, as
KORG.exec leaves it, goes through the frame hook to the firmware's key and encoder handlers: MENU, the main dial and EXIT
then do what the same keys do on the panel, the counter counts every command once, and a word without the mark is not
taken (the area is FF at power-on).

    tools/emu/.venv/bin/python tools/emu/remote_cases.py cases --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import menu_cases  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

MAILBOX = script_hooks.CARD + 0xFC0     # RM_AT in script_remote.s
CMD, DONE = 0, 8
MARK = 0xA5000000
KEY, ENCODER = 1, 2
MENU, EDIT_NEXT, EXIT = 0x09, 0x0C, 0x0D


def has_hooks(payload):
    return menu_cases.has_menu(payload) and not synthaddr.is_synth(payload)


def entry(name, ok, detail):
    return {"id": f"remote:{name}", "ok": bool(ok), "detail": str(detail)}


def command(kind, index, value=0):
    return MARK | (value & 0xFF) << 16 | index << 8 | kind


def send(dev, word, wait=0.4):
    """What KORG.exec leaves behind: the command word, then time for the frame hook."""
    dev.m.uc.mem_write(MAILBOX + CMD, struct.pack("<I", word))
    dev.run(wait)


def done(dev):
    return dev.u32(MAILBOX + DONE)


def where(dev):
    s = dev.screen()
    return s["number"], menu_cases.counter(dev), hashlib.sha256(dev.fb()).hexdigest()[:8]


def panel(dev, steps):
    """The same steps with the panel's own keys."""
    out = []
    for kind, index, value in steps:
        if kind == KEY:
            dev.press(index, wait=0.4)
        else:
            dev.turn(value)
            dev.run(0.1)
        out.append(where(dev))
    return out


def remote(dev, steps):
    out = []
    for kind, index, value in steps:
        send(dev, command(kind, index, value))
        out.append(where(dev))
    return out


def cases(payload, flash=None):
    steps = [(KEY, MENU, 0), (KEY, EDIT_NEXT, 0), (ENCODER, 0, 1), (ENCODER, 0, 1), (ENCODER, 0, -1), (KEY, EXIT, 0)]
    want = panel(menu_cases.boot(payload, flash), steps)
    dev = menu_cases.boot(payload, flash)
    start, first = where(dev), done(dev)
    got = remote(dev, steps)
    counted = (done(dev) - first) & 0xFFFFFFFF
    out = [
        entry("same_as_panel", got == want and len({g[2] for g in got[1:5]}) == 3 and got[0] != start,
              f"remote {got}, panel {want}, start {start}"),
        entry("counts_each", counted == len(steps), f"{counted} of {len(steps)} commands counted"),
        entry("taken", dev.u32(MAILBOX + CMD) == 0, f"command word after the run {dev.u32(MAILBOX + CMD):#x}"),
    ]
    before, count = where(dev), done(dev)
    send(dev, command(KEY, MENU) & 0x00FFFFFF)
    send(dev, 0xFFFFFFFF)
    out.append(entry("unmarked_ignored", where(dev) == before and done(dev) == count, f"{where(dev)} after unmarked words, before {before}"))
    out.append(entry("no_assert", not dev.m.asserts, f"asserts {dev.m.asserts[:2]}"))
    return out


GROUPS = (cases,)


def cases_task(i):
    """One group in a worker (parallel.py)."""
    import parallel
    return GROUPS[i](parallel.shared["payload"], parallel.shared["flash"])


def main():
    import lifetime
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases",))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    if not has_hooks(payload):
        print(json.dumps([entry("present", False, "the copy has no BLECH menu on a sampler")], indent=1))
        return 1
    out = cases(payload, flash)
    print(json.dumps(out, indent=1))
    return 0 if all(e["ok"] for e in out) else 1


if __name__ == "__main__":
    sys.exit(main())
