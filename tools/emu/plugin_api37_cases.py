"""Emulator cases of plugin API 37: korg.system.powerSave reads 1 while the firmware dims for its power save, korg.system.idle
the stage of IDLE POWER SAVE (tools/patch/script_idle.s), and the event idle brings each new stage, also on waking. The four
switches of byte 7 of the settings (MX_FLAGS2) are leaves: LOAD METER draws its digits at once, IDLE SAVE OFF wakes a dark
device and ON starts the time again, GLIDE CHAIN and GLIDE SWITCH set their bits; the other bits, also a reserved one, stay.
A block of API 36 still loads, one newer than the runtime is refused as before. The time is set ahead in RAM (the tick of the
last touch, as idle_save_cases.py does), not run.

    python3 tools/emu/plugin_api37_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

Measured in docs/messungen/2026-11-15-plugin-api37-energie.md.
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

from tools.patch import script_hooks, synthaddr  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
import load_meter_cases as lm  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
import lifetime  # noqa: E402
from tools.patch.test_script_vm import contract_data  # noqa: E402

IDLE = script_hooks.IDLE
IS_STAGE = IDLE + 4
TICKS = 0xC06A292C                       # the OS tick, 1 ms (script_hw.s:OS_TICKS)
POWER_CONNECT = menu_cases.POWER_CONNECT  # the firmware's switch of power save: 1 dims light and LEDs, 0 back
DIM_FLAG = menu_cases.DIM_FLAG           # its flag, not 0 while it dims (script_menu.s:BL_DIM_FLAG)
MX_FLAGS2 = menu_cases.STATE - 0x15      # byte 7 of the settings (script_menu.s:MX_FLAGS2)
LOAD_METER, IDLE_OFF, GLIDE_CHAIN, GLIDE_SWITCH = 1, 2, 4, 8
RESERVED = 0x40                          # a bit no firmware sets yet; a write of a leaf leaves it
AGES = (0, 121_000, 181_000, 241_000, 301_000)   # ms since the last touch: stage 0 to 4
EXIT = 0x0D
ERR_API_VERSION = 19                     # data/script/contract.mjs ERRORS
API_AT = 6                               # the block's apiVersion, u16 (src/script/blob.mjs HEADER)

LEAVES = ("korg.menu.blech.customizations.display.loadMeter", "korg.menu.blech.customizations.powerSave.idleSave",
          "korg.menu.blech.features.glideChain", "korg.menu.blech.features.glideSwitch")
LM, IS, GC, GS = LEAVES
# the test writes `leaf` and `want`; the next tick sets that leaf, every tick reads all six; the event idle is logged in `log`
PROGRAMS = {
    "idle": f"""let want = -1; let leaf = 0; let n = 0; let ps = -9; let st = -9; let lm = -9; let isv = -9; let gc = -9; let gs = -9;
let log = [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9];
korg.onEvent("idle", (stage) => {{ if (n < 16) {{ log[n] = stage; }} n = n + 1; }});
korg.every(20, () => {{
  if (want >= 0) {{
    if (leaf == 0) {LM} = want;
    if (leaf == 1) {IS} = want;
    if (leaf == 2) {GC} = want;
    if (leaf == 3) {GS} = want;
    want = -1;
  }}
  ps = korg.system.powerSave; st = korg.system.idle; lm = {LM}; isv = {IS}; gc = {GC}; gs = {GS};
}});""",
    "old": """let k = -9;
korg.every(20, () => { k = korg.menu.blech.customizations.led.knobLeds; });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api37:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to the main screen with a card on the adapter, IDLE POWER SAVE not held awake, running the program idle."""
    def __init__(self, vsb, flash):
        payload = vsb[0x100:]
        self.synth = synthaddr.is_synth(payload)
        self.build = identify(payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"]["idle"]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        wait = 10.0 if self.synth else 2.0        # the synth reaches its main screen after about 8 s
        self.dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=wait, idle=True)
        self.dev.run(1.0)
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], ["idle"])["idle"]
        self.dev.run(0.3)

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)

    def log(self):
        """The stages the event idle brought, in order."""
        v = self.vars()
        base, slot = self.dev.u32(self.at + 8), self.program["symbols"]["log"]["slot"]
        return [struct.unpack("<i", self.dev.read(base + (slot + i) * 4, 4))[0] for i in range(min(v["n"], 16))]

    def poke(self, name, value):
        slot = self.program["symbols"][name]["slot"]
        self.dev.m.uc.mem_write(self.dev.u32(self.at + 8) + slot * 4, struct.pack("<i", value))

    def set(self, leaf, value, wait=0.4):
        self.poke("leaf", leaf)
        self.poke("want", value)
        self.dev.run(wait)

    def clear_log(self):
        self.poke("n", 0)

    def age(self, ms, wait=0.4):
        """The last touch `ms` ago, then `wait` s for the next frames."""
        now = self.dev.u32(self.dev.a(TICKS))
        self.dev.m.uc.mem_write(IDLE, struct.pack("<I", (now - ms) & 0xFFFFFFFF))
        self.dev.run(wait)

    def stage(self):
        return self.dev.read(IS_STAGE, 1)[0]

    def flags2(self):
        return self.dev.read(MX_FLAGS2, 1)[0]


def read_cases(r):
    out = []
    v = r.vars()
    first = (v["ps"], v["st"], v["lm"], v["isv"], v["gc"], v["gs"])
    out.append(entry("reads_at_start", first == (0, 0, 0, 1, 0, 0) and r.flags2() == 0 and r.log() == [] and not r.dev.m.asserts,
                     f"build {r.build}: (powerSave, idle, loadMeter, idleSave, glideChain, glideSwitch) {first}, byte 7 "
                     f"{r.flags2():#x}, events {r.log()}"))
    r.dev.call(POWER_CONNECT, 1)
    r.dev.run(0.4)
    on = r.vars()["ps"], r.dev.read(r.dev.a(DIM_FLAG), 1)[0]
    r.dev.call(POWER_CONNECT, 0)
    r.dev.run(0.4)
    off = r.vars()["ps"], r.dev.read(r.dev.a(DIM_FLAG), 1)[0]
    out.append(entry("power_save_reads_the_firmware_dim", on[0] == 1 and on[1] != 0 and off == (0, 0) and not r.dev.m.asserts,
                     f"build {r.build}: firmware dims (leaf, flag) {on}, back {off}"))
    return out


def stage_cases(r):
    """Stage 1 to 4 and awake again: the leaf reads each stage and the event brings each one, then 0."""
    out = []
    r.age(0)
    r.clear_log()
    seen = []
    for stage, ms in enumerate(AGES[1:], 1):
        r.age(ms)
        seen.append((r.stage(), r.vars()["st"]))
    r.age(0)
    seen.append((r.stage(), r.vars()["st"]))
    events = r.log()
    out.append(entry("idle_reads_each_stage", seen == [(1, 1), (2, 2), (3, 3), (4, 4), (0, 0)] and not r.dev.m.asserts,
                     f"build {r.build}: (stage, leaf) {seen}"))
    out.append(entry("event_each_stage_and_wake", events == [1, 2, 3, 4, 0] and not r.dev.m.asserts,
                     f"build {r.build}: events {events}"))
    # a key wakes the dark device: the press is swallowed, the event brings 0
    r.age(AGES[4])
    r.clear_log()
    dark = r.stage(), r.vars()["st"]
    r.dev.m.send([0, EXIT, 1, 0, 0])
    r.dev.run(0.1)
    r.dev.m.send([0, EXIT, 0, 0, 0])
    r.dev.run(0.4)
    woke = r.stage(), r.vars()["st"], r.log()
    out.append(entry("event_on_key_wake", dark == (4, 4) and woke == (0, 0, [0]) and not r.dev.m.asserts,
                     f"build {r.build}: dark (stage, leaf) {dark}, after a key (stage, leaf, events) {woke}"))
    return out


def flag_cases(r):
    out = []
    r.age(0)
    r.dev.m.uc.mem_write(MX_FLAGS2, bytes([RESERVED]))
    r.dev.run(0.1)
    # IDLE SAVE OFF while dark: awake at the next frame, the event brings 0, the time no longer counts
    r.age(AGES[4])
    r.clear_log()
    dark = r.stage()
    r.set(1, 0)
    off = r.stage(), r.vars()["isv"], r.flags2(), r.log()
    r.age(AGES[4])
    held = r.stage(), r.vars()["st"]
    out.append(entry("idle_save_off_wakes", dark == 4 and off == (0, 0, RESERVED | IDLE_OFF, [0]) and held == (0, 0)
                     and not r.dev.m.asserts,
                     f"build {r.build}: dark {dark}, after the write (stage, leaf, byte 7, events) {off}, 5 minutes on (stage, leaf) {held}"))
    # IDLE SAVE ON with the last touch long ago: the write starts the time again, the device stays awake
    r.set(1, 1)
    on = r.stage(), r.vars()["isv"], r.flags2()
    r.age(AGES[1])
    dims = r.stage()
    out.append(entry("idle_save_on_starts_the_time", on == (0, 1, RESERVED) and dims == 1 and not r.dev.m.asserts,
                     f"build {r.build}: after the write (stage, leaf, byte 7) {on}, 2 minutes on stage {dims}"))
    r.age(0)
    # LOAD METER: the digits on the main screen at once, gone after 0
    before = lm.shown(r.dev)
    r.set(0, 1, wait=1.5)
    drawn = r.dev.read(lm.LM_DRAWN, 1)[0], lm.shown(r.dev), r.vars()["lm"], r.flags2()
    r.set(0, 0, wait=0.5)
    gone = r.dev.read(lm.LM_DRAWN, 1)[0], lm.shown(r.dev), r.vars()["lm"], r.flags2()
    out.append(entry("load_meter_shows_at_once", not any(before) and drawn[0] == 1 and any(drawn[1]) and drawn[2:] == (1, RESERVED | LOAD_METER)
                     and gone[0] == 0 and not any(gone[1]) and gone[2:] == (0, RESERVED) and not r.dev.m.asserts,
                     f"build {r.build}: columns before {before.hex()}, on (drawn, columns, leaf, byte 7) "
                     f"({drawn[0]}, {drawn[1].hex()}, {drawn[2]}, {drawn[3]:#x}), off ({gone[0]}, {gone[1].hex()}, {gone[2]}, {gone[3]:#x})"))
    # GLIDE CHAIN and GLIDE SWITCH: their bits, one after the other, the reserved bit stays
    steps = []
    for leaf, value in ((2, 1), (3, 1), (2, 0), (3, 0)):
        r.set(leaf, value)
        v = r.vars()
        steps.append((v["gc"], v["gs"], r.flags2()))
    want = [(1, 0, RESERVED | GLIDE_CHAIN), (1, 1, RESERVED | GLIDE_CHAIN | GLIDE_SWITCH), (0, 1, RESERVED | GLIDE_SWITCH), (0, 0, RESERVED)]
    out.append(entry("glide_bits", steps == want and not r.dev.m.asserts, f"build {r.build}: (glideChain, glideSwitch, byte 7) "
                     + str([(a, b, hex(c)) for a, b, c in steps])))
    r.dev.m.uc.mem_write(MX_FLAGS2, bytes([0]))
    return out


def version_cases(r):
    """A block of API 36 still loads and runs; the same block marked one newer than the runtime is refused (API_VERSION)."""
    api = int(contract_data()["include"].split(".equ SCRIPT_API_VERSION, ", 1)[1].split()[0], 0)
    old = bytearray(bytes.fromhex(r.request["programs"]["old"]["blob"]))
    version = struct.unpack_from("<H", old, API_AT)[0]
    runtime = r.built.layout["runtime"]
    r.dev.m.uc.mem_write(script_hooks.INPUT, bytes(old))
    loaded = r.dev.call(r.built.symbols["script_load_block"], runtime, script_hooks.INPUT, len(old))
    newer = bytearray(old)
    struct.pack_into("<H", newer, API_AT, api + 1)
    r.dev.m.uc.mem_write(script_hooks.INPUT, bytes(newer))
    refused = r.dev.call(r.built.symbols["script_load_block"], runtime, script_hooks.INPUT, len(newer))
    return [entry("api36_loads_newer_refused", version == 36 and api >= 37 and loaded == 0 and refused == ERR_API_VERSION
                  and not r.dev.m.asserts,
                  f"build {r.build}: block of API {version} loads with {loaded}, marked API {api + 1} gives {refused} (runtime API {api})")]


def cases(vsb, flash=None):
    menu_cases.for_build(vsb[0x100:])
    r = Run(vsb, flash)
    out = []
    for part in (read_cases, stage_cases, flag_cases, version_cases):
        out += part(r)
    return out


def main():
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
