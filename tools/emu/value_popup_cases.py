# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the value-popup patch (tools/patch/value_popup.py, docs/messungen/2026-11-27-werte-fenster-tasten.md): a key
pressed while the value window of a knob is on the screen closes the window and does what it does without the window.

Every case compares two runs of the same input from the same start: one right after a knob turn (the window is open), one after
the window has gone. Both have to end in the same state (screen, chosen and running pattern, transport, the live pattern, the
selected part). A key that reaches the window closes it; the filter keys and a further knob turn keep it. The main dial
closes it too, on the home screen and in a menu, and changes the value as without the window. The part keys,
TRIGGER, SEQUENCER, KEYBOARD, CHORD, PATTERN SET and the pads are taken by the firmware before the window: they act, and
the window stays until it times out, as in Korg's firmware.

    tools/emu/.venv/bin/python tools/emu/value_popup_cases.py --vsb PATCHED.VSB [--only N]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import synthaddr  # noqa: E402
import value_popup as spec  # noqa: E402
from pswitch_cases import Box  # noqa: E402
import lifetime  # noqa: E402
import parallel  # noqa: E402

IMAGE = 0xC0000000
PATPTR = 0xC033E6A4
LEDMGR = 0xC0345A1C                 # +0xB60 the selected part
PUSH = 0xE92D4070                   # push {r4, r5, r6, lr}: the first word of the patched handler
PLAY, LEFT, MENU, SHIFT, RIGHT, EXIT, WRITE = 0x02, 0x08, 0x09, 0x0A, 0x0C, 0x0D, 0x0E
LPF, HPF, BPF = 0x12, 0x14, 0x16
FILTERS = (LPF, HPF, BPF)
FILTER_AT = 0x80C                   # the filter type of part 1 in the live pattern
KNOB = 4                            # the knob the cases turn (cutoff)
# Keys the firmware takes before the window (measured): they act, and the window stays. REC, STOP, PLAY, TAP and 0x23 too.
EARLY = (0x0B, 0x0F, 0x11, 0x13, 0x15, 0x17, 0x18, 0x1B)
KEYS = [k for k in range(0x04, 0x23) if k not in FILTERS]
WAIT = 0.3                          # the window stays about 1.7 s in the emulator; inputs come well inside it
GONE = 2.5                          # and is gone after this


def for_build(payload):
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def handlers(payload):
    for_build(payload)
    return ([] if synthaddr.is_synth(payload) else [spec.KNOB_KEYS]) + [spec.SAMPLE_KEYS]


def has_hooks(payload):
    """True when every key handler of the value window starts with the patch's push {r4, r5, r6, lr}."""
    return all(struct.unpack_from("<I", payload, at - IMAGE)[0] == PUSH for at in handlers(payload))


def entry(name, ok, detail):
    return {"id": f"valuepopup:{name}", "ok": bool(ok), "detail": str(detail)}


# ------------------------------------------------------------------------------------------------- helpers

def window(box):
    return box.dev.screen()["window"] != 0


def state(box):
    s = box.dev.screen()
    live = bytes(box.m.uc.mem_read(box.u32(PATPTR) + 4, 0x4000))
    return {"screen": s["number"], "window": s["window"] != 0, "chosen": box.chosen(), "running": box.running(),
            "transport": box.transport(), "pattern": hashlib.sha1(live).hexdigest()[:8], "part": box.u32(box.u32(LEDMGR) + 0xB60)}


def knob(box, value=230, number=KNOB):
    box.m.send([2, number, 0, value, 0])
    box.run(WAIT)


def key(box, code, down, wait=0.15):
    box.m.press(code, down)
    box.run(wait)


def tap(box, code):
    key(box, code, True)
    key(box, code, False, WAIT)


def start(payload, popup, playing=False, open_with=None):
    """A booted device with the window open (`popup`) or gone again after the same knob turn."""
    box = Box(payload)
    if playing:
        tap(box, PLAY)
    (open_with or knob)(box)
    if not popup:
        box.run(GONE)
    return box


def compare(payload, name, act, playing=False, open_with=None, closes=True):
    """`act(box)` once with the window open and once without: the same end state, the window closed by the input (`closes`)
    or left to its time."""
    ends = []
    for popup in (False, True):
        box = start(payload, popup, playing, open_with)
        opened = window(box)
        act(box)
        ends.append((opened, state(box)))
    (closed_before, plain), (opened, after) = ends
    if not closes:
        plain, after = ({k: v for k, v in s.items() if k != "window"} for s in (plain, after))
    return entry(name, opened and not closed_before and after == plain, f"without window {plain}, with window {after}")


# ------------------------------------------------------------------------------------------------- cases

def case_menu_write(payload):
    """MENU and WRITE right after a knob open the menu and the Write window, as without the window."""
    return [compare(payload, "menu", lambda b: tap(b, MENU)), compare(payload, "write", lambda b: tap(b, WRITE)),
            compare(payload, "menu_playing", lambda b: tap(b, MENU), playing=True)]


def case_keys_a(payload):
    """Every key of the first half acts as without the window."""
    return [compare(payload, f"key_{k:02x}", lambda b, k=k: tap(b, k), closes=k not in EARLY) for k in KEYS[:len(KEYS) // 2]]


def case_keys_b(payload):
    """Every key of the second half acts as without the window."""
    return [compare(payload, f"key_{k:02x}", lambda b, k=k: tap(b, k), closes=k not in EARLY) for k in KEYS[len(KEYS) // 2:]]


def case_shift(payload):
    """SHIFT closes the window like any key, so SHIFT + a key and SHIFT + a knob do what they do without the window."""
    def combo(k):
        def act(b):
            key(b, SHIFT, True)
            tap(b, k)
            key(b, SHIFT, False, WAIT)
        return act

    def shift_knob(b):
        key(b, SHIFT, True)
        knob(b, 40)
        key(b, SHIFT, False, WAIT)
    out = [compare(payload, "shift_knob", shift_knob)]
    out += [compare(payload, f"shift_{k:02x}", combo(k), closes=k not in EARLY) for k in (MENU, WRITE, LEFT, RIGHT, EXIT, 0x10, 0x1B)]
    return out


def case_filters(payload):
    """LPF, HPF and BPF keep the window and set the filter as without it."""
    out = []
    for k in FILTERS:
        ends = []
        for popup in (False, True):
            box = start(payload, popup)
            tap(box, k)
            live = bytes(box.m.uc.mem_read(box.u32(PATPTR) + 4, 0x4000))
            ends.append((window(box), live[FILTER_AT], state(box)["pattern"]))
        (_, plain, plain_sha), (kept, after, after_sha) = ends
        out.append(entry(f"filter_{k:02x}", kept and after == plain and after_sha == plain_sha,
                         f"window kept {kept}, filter type {after} (without window {plain}), pattern {after_sha} / {plain_sha}"))
    return out


def case_knobs(payload):
    """A further knob turn keeps the window and changes the value; EXIT closes it and stays on the main screen."""
    box = start(payload, True)
    before = state(box)["pattern"]
    knob(box, 40)
    kept = window(box)
    changed = state(box)["pattern"] != before
    tap(box, EXIT)
    s = state(box)
    return [entry("knob_keeps_window", kept and changed, f"window {kept}, pattern changed {changed}"),
            entry("exit_closes", not s["window"] and s["screen"] == 1, f"after EXIT {s}")]


def case_pads_dial(payload):
    """Pads and the main dial act as without the window, stopped and playing."""
    def pad(n):
        def act(b):
            b.m.send([4, n, 0, 100, 1])
            b.run(0.15)
            b.m.send([4, n, 0, 0, 0])
            b.run(WAIT)
        return act

    def dial(b):
        b.m.send([1, 0, 0, 1, 0])
        b.run(WAIT)
    out = []
    for playing in (False, True):
        tag = "_playing" if playing else ""
        out += [compare(payload, f"pad_0{tag}", pad(0), playing, closes=False), compare(payload, f"pad_5{tag}", pad(5), playing, closes=False),
                compare(payload, f"dial{tag}", dial, playing)]
    return out


def case_sample(payload):
    """The window of the sample encoder (encoder 1) lets MENU and WRITE through too."""
    def sample(b):
        b.m.send([1, 1, 0, 1, 0])
        b.run(WAIT)
    return [compare(payload, "sample_menu", lambda b: tap(b, MENU), open_with=sample),
            compare(payload, "sample_write", lambda b: tap(b, WRITE), open_with=sample)]


def case_menu_dial(payload):
    """In a menu page the main dial right after a knob closes the window and changes the menu value, LEFT and RIGHT move the
    cursor, as without the window."""
    def in_menu(b):
        tap(b, MENU)
        tap(b, RIGHT)
        knob(b)

    def turn(step):
        def act(b):
            b.m.send([1, 0, 0, step, 0])
            b.run(WAIT)
        return act
    return [compare(payload, "menu_dial_up", turn(1), open_with=in_menu), compare(payload, "menu_dial_down", turn(0xFF), open_with=in_menu),
            compare(payload, "menu_left", lambda b: tap(b, LEFT), open_with=in_menu),
            compare(payload, "menu_right", lambda b: tap(b, RIGHT), open_with=in_menu)]


GROUPS = (case_menu_write, case_keys_a, case_keys_b, case_shift, case_filters, case_knobs, case_pads_dial, case_sample, case_menu_dial)


def group_entries(payload, flash, i):
    for_build(payload)
    return GROUPS[i](payload) if i < len(GROUPS) else []


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--only", type=int)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    payload = raw[0x100:] if len(raw) == 0x200100 else raw
    if not has_hooks(payload):
        raise SystemExit("this copy does not carry the value-popup patch")
    found = group_entries(payload, None, a.only) if a.only is not None else cases(payload)
    print(json.dumps(found, indent=1))
    raise SystemExit(0 if all(e["ok"] for e in found) else 1)


if __name__ == "__main__":
    main()
