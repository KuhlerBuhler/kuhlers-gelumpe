# SPDX-License-Identifier: GPL-2.0-only
"""Measure the start phase of a Sampler firmware in the emulator.

The start phase is all code that runs, and all image bytes that are read,
before the application shows its first screen, on every way the device can
start: normal, with the update offer, with a panel update, and with each
held-key start mode. A patch that changes a byte in there changes how the
device starts, including its ways back (docs/patcher.md, rule 2). Facts: docs/messungen/2026-10-10-startphase.md.

    tools/emu/.venv/bin/python tools/emu/bootmap.py --vsb SYSTEM.VSB [--flash dump.bin] [--out map.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from machine import FLASH_SIZE, STOCK_BOOT_LIMIT_S, Machine, blank_flash_like, load_flash

# The panel object (pointer found by firmware.py): +0x18 held buttons (64 bit), +0x20 start mode.
# The user-data check (a place of firmware.py) looks at the mark at flash 0x220000.
SPLASH = 0xC00F9854         # start image, 1024 bytes (VSB 0xF9954)
IMAGE, IMAGE_SIZE = 0xC0000000, 0x200000
SLICE_S = 0.02

# Held-button masks with their own start mode (0xC002882C) and what the display shows.
START_MODES = {
    0x18000000: (1, "[ALL]"), 0x28000000: (2, "[SHIP]"), 0x48000000: (3, "[MAIN]"),
    0x88000000: (4, "[PNL]"), 0x14000000: (5, "[EXT]"), 0x24000000: (6, "[SERV]"),
    0x0C000000: (7, "Switch-Tabelle 00-15"), 0x00140000: (8, "Data Util"),
    0x00000080: (9, "XYPad Check"), 0x0A000000: (11, "XY TEST"),
    0x00000400: (0, "normal, Merker +0x21"),
}
KILL_SWITCH = 0x00002000    # EXIT, no start mode of its own


class Probe(Machine):
    """Machine that notes when the start decisions happen."""

    def __init__(self, payload, flash):
        import unicorn
        super().__init__(payload, flash)
        self.blocks, self.events = {}, {}
        self.image_read = bytearray(IMAGE_SIZE)
        self.uc.hook_add(unicorn.UC_HOOK_EDGE_GENERATED, self._edge)
        check = self.profile.site("user_check")
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self._user_check, begin=check, end=check)
        self.uc.hook_add(unicorn.UC_HOOK_MEM_READ, self._read, begin=IMAGE, end=IMAGE + IMAGE_SIZE - 1)

    def note(self, name):
        self.events.setdefault(name, round(self.time_ns / 1e6, 1))

    def _edge(self, uc, cur, prev, user):
        # Fires when a block is first translated, so each block costs one call.
        self.blocks.setdefault(cur.pc, cur.size)

    def _user_check(self, uc, addr, size, user):
        self.note("user_mark_check")

    def _read(self, uc, access, addr, size, value, user):
        off = addr - IMAGE
        self.image_read[off:off + size] = b"\x01" * size
        if SPLASH <= addr < SPLASH + 1024:
            self.note("splash_read")

    def panel(self, msg):
        if msg[0] == 0x80:
            self.note("panel_version_query")
        if msg[0] == 0x91:
            self.note("held_buttons_query")
        super().panel(msg)

    def lcd(self, b):
        if self.gpio_out(8, 1):
            self.note("first_display_data")
        super().lcd(b)

    def panel_state(self):
        obj = self.u32(self.profile.value("panel"))
        if not obj:
            return None
        raw = bytes(self.uc.mem_read(obj + 0x18, 0x0B))
        return {"held": struct.unpack("<Q", raw[:8])[0], "mode": raw[8], "shift_flag": raw[9], "panel_update": raw[10]}


def run(payload, flash, held=0, panel_version=None, seconds=1.5):
    """Boot once; stop when screen 1 appears, else after `seconds`. Korg's own build is given the time it needs
    while it is still loading its user data (Machine.loading)."""
    m = Probe(payload, flash)
    m.held = held
    if panel_version is not None:
        m.panel_version = panel_version
    # Korg's build comes to the main screen at any moment of the screen tick, so its slices are short: the run must end
    # before the first tick of the main screen, which is not part of the start (Hacktribe's 20 ms slices are measured).
    slice_s = 0.002 if m.profile.build in ("stock", "synth") else SLICE_S
    while (m.time_ns < seconds * 1e9 or (m.loading() and m.time_ns < STOCK_BOOT_LIMIT_S * 1e9)) and not m.asserts and m.powered:
        m.run_until(m.time_ns / 1e9 + slice_s)
        if m.screen() == 1:
            m.note("screen_1")
            break
    return m


def scenarios():
    """(name, options) of every way to start. `flash` in the options is which flash it starts from:
    "own" (the one given, or a blank one without), "blank" (of the hardware of the own one), "erased" (no user-data mark)."""
    yield "normal", dict(flash="own")
    yield "normal_blank", dict(flash="blank")
    yield "update_offer", dict(flash="erased")
    yield "panel_update", dict(flash="own", panel_version=0x95)
    for mask, (mode, _) in START_MODES.items():
        yield f"held_{mask:08x}", dict(flash="own", held=mask)
    yield "kill_switch", dict(flash="own", held=KILL_SWITCH)


def scenario_names(flash):
    """Without a flash of the user's the normal start is already the blank one."""
    return [name for name, _ in scenarios() if name != "normal_blank" or flash is not None]


def flash_for(kind, own):
    if kind == "blank":
        blank = blank_flash_like(own)
        return bytes(blank) if blank is not None else None
    return {"own": own, "erased": b"\xff" * FLASH_SIZE}[kind]


def scenario_task(name):
    """One scenario in a worker (parallel.py): what start_phase takes from it. Picklable."""
    import parallel
    opts = dict(dict(scenarios())[name])
    m = run(parallel.shared["payload"], flash_for(opts.pop("flash"), parallel.shared["flash"]), **opts)
    return {"blocks": m.blocks, "image_read": bytes(m.image_read), "events_ms": m.events, "panel": m.panel_state(),
            "asserts": m.asserts, "dsp_uploads_ms": m.dsp_uploads}


def merge(blocks):
    """{start: size} as sorted, joined [start, end) ranges."""
    ranges = []
    for start, size in sorted(blocks.items()):
        if ranges and start <= ranges[-1][1]:
            ranges[-1][1] = max(ranges[-1][1], start + size)
        else:
            ranges.append([start, start + size])
    return ranges


def runs(mask):
    """Set bytes of a mask as {start: size}, addresses in RAM."""
    out, i = {}, mask.find(1)
    while i >= 0:
        j = mask.find(0, i)
        j = len(mask) if j < 0 else j
        out[IMAGE + i] = j - i
        i = mask.find(1, j)
    return out


def combine(results):
    """Code and data ranges of the start phase over the scenarios' results ({name: scenario_task result}, in
    order) as RAM addresses, [start, end), and a report per scenario."""
    code, read, report = {}, bytearray(IMAGE_SIZE), {}
    for name, r in results.items():
        for pc, size in r["blocks"].items():
            code[pc] = max(size, code.get(pc, 0))
        read = bytearray((int.from_bytes(read, "big") | int.from_bytes(r["image_read"], "big")).to_bytes(IMAGE_SIZE, "big"))
        report[name] = {"events_ms": r["events_ms"], "panel": r["panel"], "asserts": r["asserts"],
                        "blocks": len(r["blocks"]), "bytes": sum(r["blocks"].values()), "dsp_uploads_ms": r["dsp_uploads_ms"]}
    return {"code": merge(code), "data": merge(runs(read))}, report


def start_phase(payload, flash=None, jobs=None):
    """Code and data ranges of the start phase over all scenarios (RAM addresses,
    [start, end)), and a report per scenario. The scenarios are independent boots and run side by side."""
    import parallel
    names = scenario_names(flash)
    out = parallel.run_tasks([("bootmap", "scenario_task", (n,)) for n in names], {"payload": payload, "flash": flash}, jobs)
    return combine(dict(zip(names, out)))


def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--out", type=Path, help="write ranges and report as JSON (holds no firmware bytes)")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("VSB must contain a 0x100-byte header and 0x200000-byte payload")
    ranges, report = start_phase(raw[0x100:], load_flash(a.flash) if a.flash else None)
    hexed = {k: [[f"0x{s:08x}", f"0x{e:08x}"] for s, e in v] for k, v in ranges.items()}
    for name, r in report.items():
        print(f"{name:16} {json.dumps(r['events_ms'])} panel={r['panel']} bytes={r['bytes']}"
              + (f" ASSERT {r['asserts']}" if r["asserts"] else ""))
    for kind, rs in ranges.items():
        print(f"start phase {kind}: {len(rs)} ranges, {sum(e - s for s, e in rs)} bytes")
    if a.out:
        a.out.write_text(json.dumps({
            "schema": 1, "firmware_sha256": hashlib.sha256(raw).hexdigest(), "flash": bool(a.flash),
            "ranges": hexed, "scenarios": report,
        }, indent=1))


if __name__ == "__main__":
    sys.exit(main())
