# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the device from the computer (tools/patch/script_remote.s, KORG.press against the device).

check.py runs the groups on every patched copy that carries the BLECH menu, red and blue. A command word in the card work
area, as KORG.exec leaves it, goes through the frame hook into the queue of panel messages: MENU, the main dial and EXIT
then do what the same keys do on the panel, the counter counts every command once, and a word without the mark is not
taken (the area is FF at power-on). A whole panel message (knob, encoder, pad press and release, touchpad, a key held)
reaches the firmware's dispatcher byte for byte as from the panel and leaves the device where the panel leaves it. What the
computer holds down is let go on the release command, and by the device itself after 10 s without a command (a dropped
link). The test mode's cases (testmode_cases.py) run as a group of their own.

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
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

MAILBOX = script_hooks.CARD + 0xFC0     # RM_AT in script_remote.s
MESSAGE_AT = script_hooks.CARD + 0xFA0  # RM_MSG_AT
CMD, DONE = 0, 8
MARK = 0xA5000000
KEY, ENCODER, MESSAGE, RELEASE = 1, 2, 3, 5
MENU, EDIT_NEXT, EXIT, SHIFT, TOUCH = 0x09, 0x0C, 0x0D, 0x0A, 0x22
DISPATCH = 0xC002837C                   # the firmware's dispatcher of panel messages (msg + 0xC: type, four data bytes)
# (what it is, the panel messages): a knob, an encoder that is not the main dial, a pad pressed and let go, a touch, a key held
MESSAGES = [
    ("knob LEVEL", [[2, 0, 0, 200, 0]]),
    ("encoder CUTOFF -3", [[1, 2, 0, 0xFD, 0]]),
    ("pad 5", [[4, 4, 0, 100, 1], [4, 4, 0, 0, 0]]),
    ("touchpad", [[0, TOUCH, 1, 0, 0], [5, 1, 144, 1, 144], [5, 2, 88, 0, 200], [0, TOUCH, 0, 0, 0]]),
    ("SHIFT held, Edit ►", [[0, SHIFT, 1, 0, 0], [0, EDIT_NEXT, 1, 0, 0], [0, EDIT_NEXT, 0, 0, 0], [0, SHIFT, 0, 0, 0]]),
]


def has_hooks(payload):
    return menu_cases.has_menu(payload)


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


def watch_dispatch(dev):
    """Every message the dispatcher gets from now on, as its five bytes, in dev.dispatched."""
    import unicorn
    dev.dispatched = []
    hook = lambda uc, address, size, data: dev.dispatched.append(list(uc.mem_read(uc.reg_read(unicorn.arm_const.UC_ARM_REG_R0) + 0xC, 5)))
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, hook, begin=dev.a(DISPATCH), end=dev.a(DISPATCH))
    dev.m.uc.ctl_flush_tb()


def message_cases(payload, flash=None):
    out = []
    for name, messages in MESSAGES:
        panel_dev, dev = menu_cases.boot(payload, flash), menu_cases.boot(payload, flash)
        watch_dispatch(dev)
        first = done(dev)
        for message in messages:
            panel_dev.m.send(message)
            panel_dev.run(0.3)
            dev.m.uc.mem_write(MESSAGE_AT, bytes(message).ljust(8, b"\0"))
            send(dev, command(MESSAGE, 0), wait=0.3)
        got, want = where(dev), where(panel_dev)
        counted = (done(dev) - first) & 0xFFFFFFFF
        out.append(entry(f"message:{name}", dev.dispatched == messages and got == want and counted == len(messages)
                         and not dev.m.asserts and not panel_dev.m.asserts,
                         f"dispatched {dev.dispatched}, sent {messages}; remote {got}, panel {want}; {counted} counted"))
    return out


def message(dev, data, wait=0.3):
    dev.m.uc.mem_write(MESSAGE_AT, bytes(data).ljust(8, b"\0"))
    send(dev, command(MESSAGE, 0), wait=wait)


def release_cases(payload, flash=None):
    held = [[0, SHIFT, 1, 0, 0], [4, 2, 0, 90, 1]]
    dev = menu_cases.boot(payload, flash)
    watch_dispatch(dev)
    for data in held:
        message(dev, data)
    first = done(dev)
    send(dev, command(RELEASE, 0), wait=0.3)
    released = dev.dispatched[len(held):]
    out = [entry("release_all", released == [[0, SHIFT, 0, 0, 0], [4, 2, 0, 0, 0]] and (done(dev) - first) & 0xFFFFFFFF == 1,
                 f"after holding {held}: {released}")]
    dev = menu_cases.boot(payload, flash)
    watch_dispatch(dev)
    message(dev, [4, 4, 0, 100, 1])
    dev.run(9.0)
    early = list(dev.dispatched)
    dev.run(1.5)
    out.append(entry("released_after_10s", early == [[4, 4, 0, 100, 1]] and dev.dispatched[1:] == [[4, 4, 0, 0, 0]] and not dev.m.asserts,
                     f"after 9 s {early}, after 10.5 s {dev.dispatched}"))
    return out


def testmode_group(payload, flash=None):
    import testmode_cases
    return testmode_cases.cases(bytes(0x100) + payload, flash)


GROUPS = (cases, message_cases, release_cases, testmode_group)


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
        print(json.dumps([entry("present", False, "the copy has no BLECH menu")], indent=1))
        return 1
    out = [e for group in GROUPS for e in group(payload, flash)]
    print(json.dumps(out, indent=1))
    return 0 if all(e["ok"] for e in out) else 1


if __name__ == "__main__":
    sys.exit(main())
