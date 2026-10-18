# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the idle insert effect patch (tools/patch/ifx_idle.py, docs/messungen/2026-10-18-ifx-ruht.md).

check.py runs `cases` on every patched copy that carries the patch's hook. A part that is muted or has its IFX off for 5 s gets
Punch (index 0) and its own effect back the moment it is heard again; the DSP gets the change. A part whose effect is Punch is left
alone, the switch waits for the main screen, a reload of the firmware in between is noticed, and with EXIT held at power-on nothing
changes. What a part has is read where the firmware's effect setter keeps it (0xC034680E + 2 * part, the index of stage 1).

    tools/emu/.venv/bin/python tools/emu/ifx_idle_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import ifx_idle as spec  # noqa: E402
from machine import load_flash  # noqa: E402
from mfx_cases import DspLog  # noqa: E402
from pswitch_cases import Box  # noqa: E402

IMAGE = 0xC0000000
PATPTR = 0xC033E6A4
FIELDS = 0xC034680E             # the effect setter's index per stage: part n at 2n (stage 1) and 2n + 1
PART_OBJ, REMEMBERED, RELOAD = 0xC009AF20, 0xC0097D18, 0xC0097E70
MUTE_AT, ON_AT, TYPE_AT, STRIDE = 0x805, 0x824, 0x825, 0x330
OVERDRIVE, DISTORTION = 1, 2    # indices of insert presets 2 and 3 (Overdrive, Distortion); any effect that is not Punch
KEYS = {"menu": 0x09, "exit": 0x0D}


def has_hooks(payload):
    """True when the LED manager's timer literal points into the patch's code."""
    word = struct.unpack_from("<I", payload, spec.TIMER_LITERAL - IMAGE)[0]
    return spec.CODE_AT <= word < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"ifxidle:{name}", "ok": bool(ok), "detail": str(detail)}


class IBox(Box):
    """A booted device on mains power with the helpers of these cases."""

    def __init__(self, payload, flash=None, held=0):
        super().__init__(payload, flash, held, True, 3.0, adapter=True)

    def byte(self, addr, value=None):
        if value is None:
            return self.dev.read(addr, 1)[0]
        self.m.uc.mem_write(addr, bytes([value]))

    def part(self, n):
        return self.u32(PATPTR) + STRIDE * n

    def loaded(self, n):
        return self.byte(FIELDS + 2 * n)

    def remembered(self, n):
        return self.byte(self.dev.call(REMEMBERED, n))

    def give(self, n, index, on=1, mute=0):
        """The part's effect as an edit leaves it and the firmware's reload, the way a pattern change runs it; then the IFX switch and
        mute. The part is heard for a tick in between, so the silent time counts from here (a part of the flash's pattern may have
        been silent since the start)."""
        obj = self.dev.call(PART_OBJ, n)
        self.byte(self.u32(obj + 8) + 0x1D, index)
        self.byte(self.part(n) + TYPE_AT, index)
        self.byte(self.part(n) + ON_AT, 1)
        self.byte(self.part(n) + MUTE_AT, 0)
        self.dev.call(RELOAD, obj, self.dev.call(REMEMBERED, n))
        self.run(0.1)
        self.byte(self.part(n) + ON_AT, on)
        self.byte(self.part(n) + MUTE_AT, mute)

    def mute(self, n, value):
        self.byte(self.part(n) + MUTE_AT, value)

    def switch(self, n, value):
        self.byte(self.part(n) + ON_AT, value)


def case_switch(payload, flash):
    out = []
    box = IBox(payload, flash)
    box.give(0, OVERDRIVE)
    box.give(1, DISTORTION, mute=1)
    box.give(2, 0, mute=1)
    out.append(entry("setup", (box.loaded(0), box.loaded(1), box.loaded(2)) == (OVERDRIVE, DISTORTION, 0),
                     (box.loaded(0), box.loaded(1), box.loaded(2))))
    box.run(4.0)
    out.append(entry("wait_hold", (box.loaded(0), box.loaded(1)) == (OVERDRIVE, DISTORTION), "4 s muted: still its own effect"))
    log = DspLog(box.m)
    box.run(1.5)
    sent = len(log.changes())
    out.append(entry("muted_punch", box.loaded(1) == 0 and box.remembered(1) == 0 and sent > 0,
                     dict(loaded=box.loaded(1), remembered=box.remembered(1), dsp_writes=sent)))
    out.append(entry("heard_untouched", box.loaded(0) == OVERDRIVE, box.loaded(0)))
    out.append(entry("punch_untouched", box.loaded(2) == 0 and box.byte(spec.STATE + spec.S_SWAP + 2) != 1,
                     box.byte(spec.STATE + spec.S_SWAP + 2)))
    box.mute(1, 0)
    box.run(0.1)
    out.append(entry("unmute_back", box.loaded(1) == DISTORTION and box.remembered(1) == DISTORTION, (box.loaded(1), box.remembered(1))))
    box.switch(0, 0)
    box.run(5.5)
    off = box.loaded(0)
    box.switch(0, 1)
    box.run(0.1)
    out.append(entry("ifx_off_punch_and_back", off == 0 and box.loaded(0) == OVERDRIVE, (off, box.loaded(0))))
    box.mute(1, 1)
    box.run(5.5)
    first = box.loaded(1)
    box.give(1, DISTORTION, mute=1)             # a pattern change while the part has Punch: the firmware loads its effect again
    reloaded = box.loaded(1)
    box.run(4.0)
    kept = box.loaded(1)
    box.run(1.5)
    out.append(entry("firmware_reload", (first, reloaded, kept, box.loaded(1)) == (0, DISTORTION, DISTORTION, 0),
                     dict(punch=first, reloaded=reloaded, after_4s=kept, after_5_5s=box.loaded(1))))
    out.append(entry("clean", not box.m.asserts, box.m.asserts[:3]))
    return out


def case_screen(payload, flash):
    box = IBox(payload, flash)
    box.give(1, DISTORTION)
    box.dev.press(KEYS["menu"], 0.5)
    box.mute(1, 1)
    box.run(6.0)
    in_menu = box.loaded(1)
    box.dev.press(KEYS["exit"], 0.5)
    box.run(0.3)
    return [entry("main_screen_only", in_menu == DISTORTION and box.loaded(1) == 0, dict(in_menu=in_menu, after_exit=box.loaded(1)))]


def case_kill(payload, flash):
    box = IBox(payload, flash, held=spec.KILL_SWITCH)
    box.give(1, DISTORTION, mute=1)
    box.run(6.0)
    return [entry("kill_switch", box.loaded(1) == DISTORTION and box.byte(spec.STATE + spec.S_SWAP + 1) == 0xFF,
                  dict(loaded=box.loaded(1), state=box.byte(spec.STATE + spec.S_SWAP + 1)))]


GROUPS = (case_switch, case_screen, case_kill)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own device, so they can run side by side."""
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases",))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    entries = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
