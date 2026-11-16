"""Emulator cases of plugin API 27: korg.pattern.current.mfx2Type (and korg.patterns[i].mfx2Type) read and set the MFX 2 type
of the patch mfx-switch, korg.touchpad.mode reads the touch pad mode and sets it with one key press, the event touchpadMode
reports every change of it. Each runs with MFX 2 on (the BLECH set's start) and off (the BLECH menu's MFX 2 setting 0, which
the patch reads at every hook), and a WRITE followed by a power cycle keeps mfx2Type.

    python3 tools/emu/plugin_api27_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api27-mfx2-touchpad.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import mfx_switch as spec  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

CTL, SEQ, PATTERN = 0xC06912E0, 0xC034029C, 0xC033E6A4   # Sampler places; Dev.a gives the synth's (data/synth-map/)
TYPE_AT = 0x41                                # the MFX type in the pattern being edited, as enter_mfx2 reads it
BLECH_MFX = spec.BLECH_MFX                    # the BLECH menu's effective MFX 2 setting, 0 off
MFX2_FIELD = 18                               # PATTERN_FIELDS index of mfx2Type (data/script/contract.mjs)
TOUCHPAD_LEAF = 53
KEYS = {"gate_arp": 4, "touch_scale": 5, "master_fx": 6, "shift": 10, "write": 14}
NO_MODE = 0xFF
FIRMWARE_NEXT = ((0, 3, 2), (3, 1, 2), (0, 1, 2), (0, 1, 2))   # the mode after GATE ARP, TOUCH SCALE, MASTER FX (2026-10-10-mfx-umschalter.md)

PROGRAM = "let changes = 0; let last = -9;\n" + \
    "korg.onEvent(\"touchpadMode\", mode => { changes = changes + 1; last = mode; });"


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled({"api27": PROGRAM})


def entry(name, ok, detail):
    return {"id": f"plugin_api27:{name}", "ok": bool(ok), "detail": str(detail)}


class World:
    def __init__(self, vsb, flash=None):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        spec.use_build("synth" if self.build == "synth" else "hacktribe")
        self.request = edit.compiled({"api27": PROGRAM})
        self.built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(1.5)                     # the patch sets its start mode at the first tick of the main screen
        self.sym = self.built.symbols

    # what the firmware and the patch hold, read past the runtime
    def mode(self):
        obj = self.dev.u32(CTL)
        return self.dev.m.u32(obj + 0x334) if obj else NO_MODE

    def mfx2_active(self):
        return self.dev.u32(spec.STATE + 0) == 1

    def want_mode(self):
        mode = self.mode()
        return 4 if mode == 2 and self.mfx2_active() else mode

    def pattern(self):
        return self.dev.m.u32(self.dev.u32(SEQ) + 0x318)

    def table(self, pattern):
        return self.dev.read(spec.RECBUF + 8 + pattern, 1)[0]

    def want_type(self, pattern):
        entry = self.table(pattern)
        return entry - 1 if 1 <= entry <= 100 else spec.DEFAULT_TYPE - 1

    # the runtime, as the VM calls it
    def read_type(self, pattern=-1):
        return self.dev.call(self.sym["script_read_pattern_value_glue"], pattern, 0xFFFFFFFF, MFX2_FIELD)

    def set_type(self, value):
        self.dev.call(self.sym["script_seq_set_pattern_value_glue"], MFX2_FIELD, value)
        self.dev.run(0.6)

    def read_mode(self):
        return self.dev.call(self.sym["script_object_get_glue"], TOUCHPAD_LEAF, 0xFFFFFFFF)

    def set_mode(self, value):
        self.dev.call(self.sym["script_object_set_glue"], TOUCHPAD_LEAF, 0xFFFFFFFF, value)
        self.dev.run(0.6)                     # the press goes out with the panel's queue, the release one frame later

    def own_type(self):
        return self.dev.m.u32(self.dev.u32(PATTERN) + TYPE_AT) & 0xFF

    def key(self, name):
        self.dev.press(KEYS[name], 0.6)

    def mfx2_setting(self, on):
        self.dev.m.uc.mem_write(BLECH_MFX, (1 if on else 0).to_bytes(4, "little"))
        self.dev.run(0.2)


def type_cases(w):
    out = []
    p = w.pattern()
    first = (w.read_type(), w.read_type(p), w.want_type(p))
    out.append(entry("type_reads_the_table", first[0] == first[1] == first[2] and not w.dev.m.asserts,
                     f"build {w.build}: pattern {p}, current {first[0]}, patterns[{p}] {first[1]}, table says {first[2]}"))
    # MFX 2 on, not active (Master FX with the pattern's own type): the table entry changes, the effect does not
    w.key("master_fx")
    own = w.own_type()
    w.set_type(12)
    own_after = w.own_type()
    out.append(entry("type_set_while_inactive", w.read_type() == 12 and w.table(p) == 13 and w.dev.u32(spec.STATE + 24) == 1
                     and own_after == own and not w.dev.m.asserts,
                     f"read {w.read_type()}, table {w.table(p)}, dirty {w.dev.u32(spec.STATE + 24)}, own type {own} -> {own_after}"))
    # MFX 2 active: the firmware's type setter runs, the patch stores it and the effect follows
    w.key("touch_scale")
    active = w.mfx2_active()
    w.set_type(20)
    applied = w.own_type()
    out.append(entry("type_set_while_active", active and w.read_type() == 20 and w.table(p) == 21 and applied == 20 and not w.dev.m.asserts,
                     f"MFX 2 active {active}, read {w.read_type()}, table {w.table(p)}, type in the pattern object {applied}"))
    # past the top: the write range's 39, the synth's last type 31 (the setter's limit in script_hooks)
    top = 31 if w.build == "synth" else 39
    w.set_type(99)
    out.append(entry("type_set_clamps", w.read_type() == top and w.own_type() == top and not w.dev.m.asserts,
                     f"set 99, read {w.read_type()}, type in the pattern object {w.own_type()} (want {top})"))
    w.set_type(20)
    # MFX 2 off in BLECH: nothing changes
    w.mfx2_setting(False)
    w.set_type(30)
    out.append(entry("type_set_with_mfx2_off_changes_nothing", w.read_type() == 20 and w.table(p) == 21 and not w.dev.m.asserts,
                     f"read {w.read_type()}, table {w.table(p)}"))
    w.mfx2_setting(True)
    return out


def mode_cases(w, on):
    """Each target from the mode the last step left; with MFX 2 on the patch's keys, off the firmware's (one press each)."""
    if not on:
        w.mfx2_setting(False)
        w.key("master_fx")
    steps = [4, 3, 1, 2, 0] if on else [1, 3, 0, 2, 3]
    seen, ok = [], True
    for target in steps:
        before = w.read_mode()
        w.set_mode(target)
        after, firmware = w.read_mode(), w.want_mode()
        expect = target if (target != 0 if on else target in FIRMWARE_NEXT[before]) else before
        seen.append((target, before, after, firmware))
        ok = ok and after == firmware == expect
    if not on:
        w.mfx2_setting(True)
    return [entry(f"mode_set_mfx2_{'on' if on else 'off'}", ok and not w.dev.m.asserts,
                  f"build {w.build}: (target, before, after, firmware) {seen}")]


def event_cases(w):
    at = script_cases.install(w.dev, w.built, w.request["programs"], ["api27"])["api27"]
    program = w.request["programs"]["api27"]
    w.dev.run(0.5)
    start = script_cases.variables(w.dev, at, program)
    w.key("gate_arp")
    by_key = script_cases.variables(w.dev, at, program)
    w.set_mode(4)
    by_set = script_cases.variables(w.dev, at, program)
    ok = start["changes"] == 0 and by_key == {"changes": 1, "last": 3} and by_set == {"changes": 2, "last": 4} and w.read_mode() == 4
    return [entry("event_follows_key_and_set", ok and not w.dev.m.asserts, f"start {start}, after GATE ARP {by_key}, after mode = 4 {by_set}")]


def write_cases(vsb, flash):
    w = World(vsb, flash)
    p = w.pattern()
    w.key("master_fx")
    w.set_type(25)
    w.key("write")
    w.key("write")
    w.dev.run(3.0)
    kept = bytes(w.dev.m.flash.mem)
    again = World(vsb, kept)
    return [entry("type_survives_write_and_power_cycle", again.read_type(p) == 25 and not again.dev.m.asserts,
                  f"pattern {p}: set 25, after WRITE and a new boot reads {again.read_type(p)} (table {again.table(p)})")]


def cases(vsb, flash=None):
    out = type_cases(World(vsb, flash))
    out += mode_cases(World(vsb, flash), True)
    out += mode_cases(World(vsb, flash), False)
    out += event_cases(World(vsb, flash))
    out += write_cases(vsb, flash)
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
