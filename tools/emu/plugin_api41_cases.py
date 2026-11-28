"""Emulator cases of plugin API 41: the pages TUBE, TUBE DRIVE and TUBE ASYM of the patch tube-curve as the leaves
korg.menu.blech.features.tube, tubeDrive and tubeAsym (tools/patch/script_objects.s objects_tube_get and objects_tube_set).
A plugin reads and writes them as the pages show and set them: TUBE ON takes TUBE DRIVE into the field of byte 7 (MX_FLAGS2),
TUBE DRIVE while ON goes into the field at once, while OFF it is only kept, TUBE ASYM is stored xor its default 4, and each
change sends the DSP its block the next frame like a turn on the page (tube_cases.py reads the host port the same way). The
other bits of byte 7 stay. A copy whose DSP program has Korg's clipper reads TUBE 0 and a write changes nothing.
A block of API 40 still loads, one newer than the runtime is refused as before.

    python3 tools/emu/plugin_api41_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(ROOT / "tools" / "dsp"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks, synthaddr  # noqa: E402
import menu_cases as mc  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
import tube_cases  # noqa: E402
from mfx_cases import DspLog  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
import lifetime  # noqa: E402
from tools.patch.test_script_vm import contract_data  # noqa: E402

M_TUBE_DRIVE = mc.STATE + 0x1C5          # TUBE DRIVE 1 to 7, 0 before a file with TUBE ON was read (script_menu.s:M_TUBE_DRIVE)
OTHERS = 0x05                            # LOAD METER and GLIDE CHAIN: bits of byte 7 outside the TUBE field, a write leaves them
ERR_API_VERSION = 19                     # data/script/contract.mjs ERRORS
API_AT = 6                               # the block's apiVersion, u16 (src/script/blob.mjs HEADER)

LEAVES = ("korg.menu.blech.features.tube", "korg.menu.blech.features.tubeDrive", "korg.menu.blech.features.tubeAsym")
TU, TD, TA = LEAVES
# the test writes `leaf` and `want`; the next tick sets that leaf, every tick reads all three and korg.system.repairs
PROGRAMS = {
    "tube": f"""let want = -1; let leaf = 0; let tu = -9; let td = -9; let ta = -9; let rep = -9;
korg.every(20, () => {{
  if (want >= 0) {{
    if (leaf == 0) {TU} = want;
    if (leaf == 1) {TD} = want;
    if (leaf == 2) {TA} = want;
    want = -1;
  }}
  tu = {TU}; td = {TD}; ta = {TA}; rep = korg.system.repairs;
}});""",
    "old": """korg.onEvent("ready", () => { korg.display.popup.begin(); });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api41:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to the main screen with a card without a settings file, the host port logged, running the program tube."""
    def __init__(self, payload, flash):
        self.synth = synthaddr.is_synth(payload)
        self.build = identify(payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"]["tube"]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        wait = 10.0 if self.synth else 2.0        # the synth reaches its main screen after about 8 s
        self.dev = mc.boot(payload, flash, files=mc.CARD_FOLDER, adapter=True, seconds=wait)
        self.dev.run(1.0)
        self.log = DspLog(self.dev.m)
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], ["tube"])["tube"]
        self.dev.run(0.3)

    def vars(self):
        v = script_cases.variables(self.dev, self.at, self.program)
        return v["tu"], v["td"], v["ta"]

    def repairs(self):
        return script_cases.variables(self.dev, self.at, self.program)["rep"]

    def poke(self, name, value):
        slot = self.program["symbols"][name]["slot"]
        self.dev.m.uc.mem_write(self.dev.u32(self.at + 8) + slot * 4, struct.pack("<i", value))

    def set(self, leaf, value, wait=0.4):
        self.poke("leaf", leaf)
        self.poke("want", value)
        self.dev.run(wait)

    def ram(self):
        """(byte 7, M_TUBE_DRIVE, M_TUBE_ASYM) as the firmware holds them."""
        return (self.dev.read(mc.MX_FLAGS2, 1)[0], self.dev.read(M_TUBE_DRIVE, 1)[0],
                self.dev.read(mc.STATE + mc.M_TUBE_ASYM, 1)[0])

    def sent(self):
        return tube_cases.sent(self.log)


def write_cases(r):
    out = []
    first = r.vars(), r.ram(), r.sent()
    out.append(entry("reads_at_start", first == ((0, 5, 4), (0, 0, 0), []) and not r.dev.m.asserts,
                     f"build {r.build}: (tube, drive, asym) {first[0]}, (byte 7, M_TUBE_DRIVE, M_TUBE_ASYM) {first[1]}, blocks {first[2]}"))
    r.dev.m.uc.mem_write(mc.MX_FLAGS2, bytes([OTHERS]))
    r.dev.run(0.1)

    r.set(0, 1)
    on = r.vars(), r.ram(), r.sent()
    out.append(entry("tube_on_takes_drive", on == ((1, 5, 4), (OTHERS | 5 << 5, 5, 0), [(5, 4)]) and not r.dev.m.asserts,
                     f"build {r.build}: (tube, drive, asym) {on[0]}, (byte 7, M_TUBE_DRIVE, M_TUBE_ASYM) {on[1]}, blocks {on[2]}"))

    r.set(1, 3)
    drive = r.vars(), r.ram(), r.sent()
    out.append(entry("drive_while_on_acts", drive == ((1, 3, 4), (OTHERS | 3 << 5, 3, 0), [(5, 4), (3, 4)]) and not r.dev.m.asserts,
                     f"build {r.build}: (tube, drive, asym) {drive[0]}, (byte 7, M_TUBE_DRIVE, M_TUBE_ASYM) {drive[1]}, blocks {drive[2]}"))

    r.set(2, 2)
    asym = r.vars(), r.ram(), r.sent()
    out.append(entry("asym_stored_xor_default", asym == ((1, 3, 2), (OTHERS | 3 << 5, 3, 2 ^ 4), [(5, 4), (3, 4), (3, 2)])
                     and not r.dev.m.asserts,
                     f"build {r.build}: (tube, drive, asym) {asym[0]}, (byte 7, M_TUBE_DRIVE, M_TUBE_ASYM) {asym[1]}, blocks {asym[2]}"))

    r.set(0, 0)
    off = r.vars(), r.ram(), r.sent()
    r.set(1, 6)
    kept = r.vars(), r.ram(), r.sent()
    r.set(0, 1)
    again = r.vars(), r.ram(), r.sent()
    out.append(entry("off_keeps_drive", off[:2] == ((0, 3, 2), (OTHERS, 3, 2 ^ 4)) and kept[:2] == ((0, 6, 2), (OTHERS, 6, 2 ^ 4))
                     and kept[2] == off[2] and again[:2] == ((1, 6, 2), (OTHERS | 6 << 5, 6, 2 ^ 4))
                     and again[2] == [(5, 4), (3, 4), (3, 2), 0, (6, 2)] and not r.dev.m.asserts,
                     f"build {r.build}: OFF {off}, TUBE DRIVE 6 while OFF {kept}, ON again {again}"))

    before = r.repairs()
    r.set(1, 0)
    low = r.vars(), r.ram(), r.repairs() - before
    r.set(2, 9)
    high = r.vars(), r.ram(), r.repairs() - before
    out.append(entry("clamps_to_the_range", low[:2] == ((1, 1, 2), (OTHERS | 1 << 5, 1, 2 ^ 4)) and high[:2] == ((1, 1, 7), (OTHERS | 1 << 5, 1, 7 ^ 4))
                     and high[2] == 2 and not r.dev.m.asserts,
                     f"build {r.build}: TUBE DRIVE 0 gives {low}, TUBE ASYM 9 gives {high} (leaves, RAM, repairs since)"))
    r.dev.m.uc.mem_write(mc.MX_FLAGS2, bytes([0]))
    return out


def version_cases(r):
    """A block of API 40 still loads and runs; the same block marked one newer than the runtime is refused (API_VERSION)."""
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
    return [entry("api40_loads_newer_refused", version == 40 and api >= 41 and loaded == 0 and refused == ERR_API_VERSION
                  and not r.dev.m.asserts,
                  f"build {r.build}: block of API {version} loads with {loaded}, marked API {api + 1} gives {refused} (runtime API {api})")]


def without_patch_cases(payload, flash):
    """The same runtime in a copy whose DSP program has Korg's clipper (as tube_cases.case_without_patch makes it): TUBE reads
    0 although the field is set, a write changes nothing and sends nothing."""
    plain = bytearray(payload)
    synth = synthaddr.is_synth(payload)
    struct.pack_into("<H", plain, (0xC01176D6 if synth else 0xC0131F90) - mc.IMAGE, tube_cases.KORG_CALLER[synth])
    r = Run(bytes(plain), flash)
    r.dev.m.uc.mem_write(mc.MX_FLAGS2, bytes([OTHERS | 5 << 5]))
    r.dev.run(0.3)
    read = r.vars()
    r.set(0, 0)
    r.set(1, 2)
    r.set(2, 7)
    after = r.ram(), r.sent()
    return [entry("without_patch", read[0] == 0 and after == ((OTHERS | 5 << 5, 0, 0), []) and not r.dev.m.asserts,
                  f"build {r.build}: (tube, drive, asym) {read}, after three writes (byte 7, M_TUBE_DRIVE, M_TUBE_ASYM) {after[0]}, "
                  f"blocks {after[1]}")]


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    mc.for_build(payload)
    if not mc.has_menu(payload) or not mc.has_tube(payload):
        return [entry("tube_patch", False, "this copy has no BLECH menu or no tube-curve patch")]
    r = Run(payload, flash)
    out = write_cases(r) + version_cases(r)
    return out + without_patch_cases(payload, flash)


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
