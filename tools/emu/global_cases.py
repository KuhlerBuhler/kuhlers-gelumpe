"""Emulator cases of the Global leaves of the plugin API 20 (`korg.global.*`, data/script/objects.mjs): every leaf takes a value
through the firmware's own setter and the Global menu shows it as if the menu had turned it, a plugin sets them by path, the
firmware keeps them through WRITE and through the switch-off, and a stored value outside the menu's limits is repaired at start.

    PYTHONPATH=tools/patch python3 tools/emu/global_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-05-plugin-api16.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R2, UC_ARM_REG_R3  # noqa: E402
from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import node_json  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import Dev, user_flash  # noqa: E402

GLOBALS_PTR = 0xC0691324        # the pointer to the Global settings object, its block (GLST) starts 4 bytes in (the same value as [0xC033E6A0])
GLOBALS_PTR_TWIN = 0xC033E6A0
BLOCK = 4
FLASH_AT = 0x230000             # where the firmware keeps the block: WRITE on the Global menu and the switch-off write it there
PARAM_WRITER = 0xC004B208       # the sound engine copy writer the setters report to: (object, x, parameter, value) in r0 to r3
TOUCH_SCALE = 0xC06911E4        # the Touch Scale object, +0x14 the range the firmware copies from the Global byte
POWER_KEY = [6, 1, 0, 0, 0]
KEYS = menu_cases.KEYS
GLOBAL_SCREEN = 9
# the parameter each setter reports to the sound engine (measure:2026-11-03/live-schreibwege), none for the plain ones
PARAMS = {"clockMode": 0x31, "midiChannel": 0x32, "receiveFilter": 0x39, "sendFilter": 0x38, "syncPolarity": 0x2D, "syncResolution": 0x3A,
          "tempoLock": 0x37, "touchScaleRange": 0x35, "lcdContrast": 0x36, "audioInThru": 0x2E, "autoPowerOff": 0x34, "powerSave": 0x33}
ERR_API_ARG = 15
# Not stored on in the restart cases: with TEMPO LOCK on in the stored block the emulator does not reach the main screen again, with
# Korg's unpatched firmware just the same (measured with the Hacktribe image), so that is not what these cases are about.
NOT_STORED_ON = {"tempoLock"}

PROGRAM = """let metronome = -1; let contrast = -1; let channel = -1; let range = -1; let knob = -1; let repairs = -1; let big = 7;
korg.onEvent("ready", () => {
  korg.global.metronome = 3;
  korg.global.lcdContrast = korg.global.lcdContrast + 2;
  korg.global.midiChannel = 9;
  korg.global.touchScaleRange = 0;
  metronome = korg.global.metronome;
  contrast = korg.global.lcdContrast;
  channel = korg.global.midiChannel;
  range = korg.global.touchScaleRange;
  knob = korg.global.knobMode;
  korg.global.sendFilter = big;
  repairs = korg.system.repairs;
});"""


def entry(name, ok, detail):
    return {"id": f"global:{name}", "ok": bool(ok), "detail": str(detail)}


def tree():
    """The leaves of korg.global: [id, name, dump offset (the leaf's offset is 4 more, behind the word in front of the block), min, max, factory, writable]."""
    code = ("import {OBJECTS} from './data/script/objects.mjs';"
            "process.stdout.write(JSON.stringify(OBJECTS.filter(o => o.path.startsWith('korg.global.')).map(o => "
            "[o.id, o.path.split('.').pop(), o.offset - 4, o.min, o.max, o.factory, o.write])))")
    return node_json.run(code)


class World:
    """A booted device with the runtime's symbols; `again` boots another one on the flash this one left."""

    def __init__(self, vsb, flash=None, leaves=None, built=None, adapter=True):
        self.vsb, self.payload = vsb, vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.leaves = leaves or tree()
        self.built = built or script_hooks.build(edit.compiled({"global": PROGRAM})["include"], build=identify(self.payload).build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, adapter=adapter, seconds=2.0)
        self.adapter = adapter
        self.s = self.built.symbols

    def again(self, flash):
        return World(self.vsb, flash, self.leaves, self.built, self.adapter)

    @property
    def g(self):
        return self.dev.u32(GLOBALS_PTR) + BLOCK

    def byte(self, offset):
        return self.dev.read(self.g + offset, 1)[0]

    def block(self):
        return self.dev.read(self.g - BLOCK, 0x104)

    def put(self, offset, value):
        self.dev.m.uc.mem_write(self.g + offset, bytes([value]))

    def set(self, leaf, value, wait=0.15):
        self.dev.call(self.s["script_object_set_glue"], leaf, 0xFFFFFFFF, value & 0xFFFFFFFF)
        self.dev.run(wait)

    def repairs(self):
        return self.dev.u32(self.s["objects_repairs"])

    def watch(self):
        """Record every report to the sound engine as (parameter, value) in the returned list."""
        calls = []
        self.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: calls.append((uc.reg_read(UC_ARM_REG_R2) & 0xFF, uc.reg_read(UC_ARM_REG_R3) & 0xFF)),
                               begin=self.dev.a(PARAM_WRITER), end=self.dev.a(PARAM_WRITER))
        self.dev.m.uc.ctl_flush_tb()
        return calls

    def page(self, k):
        """The page k (0 to 18) of GLOBAL PARAMETERS, entered fresh (the menu keeps the last page)."""
        menu_cases.go(self.dev, GLOBAL_SCREEN)
        for _ in range(30):
            if menu_cases.counter(self.dev)[0] == k:
                return
            self.dev.press(KEYS["edit_next"], 0.25)
        raise AssertionError(f"page {k} not reached")

    def reenter(self, k):
        """Leave the page and come back: the page draws the value it finds in the block."""
        self.dev.press(KEYS["edit_next"], 0.25)
        self.dev.press(KEYS["edit_prev"], 0.25)
        assert menu_cases.counter(self.dev)[0] == k, menu_cases.counter(self.dev)
        return self.dev.fb()

    def pages(self):
        """The picture of every page 0 to 18 without the bottom nine pixel rows (a status line that differs between two starts, not
        with the value) and without LCD CONTRAST (page 12), whose picture is not the same twice in a row either."""
        keep = bytearray(0xFF if row < 6 else 0x7F if row == 6 else 0 for row in range(8) for _ in range(128))      # rows 0 to 54
        out = []
        self.page(0)
        for k in range(19):
            fb = bytes(b & m for b, m in zip(self.dev.fb(), keep))
            out.append(None if k == 12 else fb)
            self.dev.press(KEYS["edit_next"], 0.25)
        return out

    def write(self):
        """WRITE on the Global menu: the firmware saves the block."""
        menu_cases.go(self.dev, GLOBAL_SCREEN)
        self.dev.press("write", wait=0.8)

    def switch_off(self):
        self.dev.m.send(POWER_KEY)
        for _ in range(900):
            if not self.dev.m.powered:
                break
            self.dev.run(0.005)
        return not self.dev.m.powered

    def saved(self):
        return bytes(self.dev.m.flash.mem[FLASH_AT:FLASH_AT + 0x100])


def leaf_cases(w):
    """Each leaf set to its top, bottom and a value above the top (clamped and counted); every report to the sound engine."""
    out = []
    calls = w.watch()
    for leaf, name, offset, lo, hi, _, write in w.leaves:
        seen, bad = [], []
        for want, value in ((hi, hi), (lo, lo), (hi, hi + 7)):
            before = w.repairs()
            calls.clear()
            w.set(leaf, value)
            got = w.byte(offset)
            seen.append((value, got, list(calls)))
            if got != want or (value != want) != (w.repairs() == before + 1):
                bad.append(value)
            if PARAMS.get(name) and (PARAMS[name], want) not in calls:
                bad.append(f"no report {PARAMS[name]:#x}")
        out.append(entry(f"{name}_set", write and not bad and not w.dev.m.asserts, f"{seen}, asserts {w.dev.m.asserts}"))
    return out


def pointer_case(w):
    """The two places the firmware keeps the Global object's address hold the same one, and the block starts with GLST."""
    a, b = w.dev.u32(GLOBALS_PTR), w.dev.u32(GLOBALS_PTR_TWIN)
    return [entry("pointer_is_the_global_object", a == b and w.dev.read(a + BLOCK, 4) == b"GLST", f"{a:#x} and {b:#x}")]


def read_only_cases(w):
    """A leaf a plugin may not set: korg.set leaves the byte alone and reports nothing."""
    out = []
    calls = w.watch()
    for leaf, name, offset, lo, hi, factory, write in w.leaves:
        if write:
            continue
        before = w.byte(offset)
        calls.clear()
        w.set(leaf, hi if before != hi else lo)
        out.append(entry(f"{name}_read_only", w.byte(offset) == before and not calls and not w.dev.m.asserts, f"byte {before} -> {w.byte(offset)}"))
    return out


def twin_cases(w):
    """The page of each leaf turned up by one in the menu, and the same value set by a plugin: the same reports to the sound engine,
    the same block and, after leaving the page and coming back, the same picture. Where the firmware copies the value, the copy."""
    out = []
    calls = w.watch()
    for k, (leaf, name, offset, lo, hi, _, write) in enumerate(w.leaves):
        if not write:
            continue
        w.set(leaf, lo)
        w.page(k)
        calls.clear()
        w.dev.turn(1, 0.4)
        want = w.byte(offset)
        menu = (list(calls), w.block(), w.reenter(k))
        w.set(leaf, lo)
        w.reenter(k)
        calls.clear()
        w.set(leaf, want)
        plugin = (list(calls), w.block(), w.reenter(k))
        copy = None
        if name == "touchScaleRange" and not w.dev.synth:
            copy = w.dev.u32(TOUCH_SCALE + 0x14)
        out.append(entry(f"{name}_like_the_menu", want == lo + 1 and menu[:2] == plugin[:2] and (name == "lcdContrast" or menu[2] == plugin[2]) and (copy is None or copy == want) and not w.dev.m.asserts,
                         f"menu turned {lo} to {want}: reports {menu[0]}, plugin {plugin[0]}, block equal {menu[1] == plugin[1]}, "
                         f"page equal {menu[2] == plugin[2]}" + ("" if copy is None else f", touch scale object {copy}")))
    return out


def plugin_cases(w):
    """A plugin sets and reads the leaves by path; a value above the top is clamped and counted (korg.system.repairs)."""
    request = edit.compiled({"global": PROGRAM})
    program = request["programs"]["global"]
    entry_at = script_cases.install(w.dev, w.built, request["programs"], ["global"])["global"]
    w.dev.run(0.5)
    seen = script_cases.variables(w.dev, entry_at, program)
    block = {name: w.byte(offset) for _, name, offset, *_ in w.leaves}
    ok = (block["metronome"] == 3 and block["midiChannel"] == 9 and block["touchScaleRange"] == 0 and block["lcdContrast"] == 36
          and block["sendFilter"] == 2 and block["knobMode"] == 0)
    read = [seen[k] for k in ("metronome", "contrast", "channel", "range", "knob")] == [3, 36, 9, 0, 0] and seen["repairs"] == 1
    return [entry("plugin_sets_and_reads_by_path", ok and read and not w.dev.m.asserts,
                  f"block {block}, read back {seen}, asserts {w.dev.m.asserts}")]


def extreme_cases(w, which):
    """All writable leaves at their lowest ("lo") or highest ("hi"): WRITE, restart on the saved flash, no assert, the menu shows them."""
    out = []
    index = 3 if which == "lo" else 4
    for x in w.leaves:
        if x[6] and x[1] not in NOT_STORED_ON:
            w.set(x[0], x[index], wait=0.05)
    w.dev.run(0.3)
    want = {x[1]: x[index] for x in w.leaves if x[6] and x[1] not in NOT_STORED_ON}
    before = w.pages()
    w.write()
    saved = w.saved()
    kept = all(saved[x[2]] == want[x[1]] for x in w.leaves if x[1] in want)
    again = w.again(bytearray(w.dev.m.flash.mem))
    got = {x[1]: again.byte(x[2]) for x in w.leaves if x[1] in want}
    after = again.pages()
    out.append(entry(f"write_restart_{which}", kept and got == want and not again.dev.m.asserts and not w.dev.m.asserts and again.repairs() == 0
                     and after == before, f"saved by WRITE {kept}, after restart {got}, asserts {again.dev.m.asserts}, repairs {again.repairs()}, "
                     f"pages show the same {after == before}"))
    return out, again


def switch_off_case(w):
    """The firmware saves what a plugin set when the device is switched off, without WRITE."""
    for leaf, name, offset, lo, hi, factory, write in w.leaves:
        if write:
            w.set(leaf, hi if factory != hi else lo, wait=0.05)
    want = {x[1]: w.byte(x[2]) for x in w.leaves}
    before = w.saved()
    off = w.switch_off()
    saved = w.saved()
    ok = off and all(saved[x[2]] == want[x[1]] for x in w.leaves)
    return [entry("saved_at_switch_off", ok and not w.dev.m.asserts, f"powered off {off}, flash block changed {saved != before}, equals RAM {ok}")]


def repair_cases(w):
    """A flash whose block holds a value outside the menu's limits for every leaf: after the start each one is inside, the count is
    right, the menu pages still draw, and a switch-off keeps the repaired block."""
    base = bytearray(w.dev.m.flash.mem)
    block = bytearray(base[FLASH_AT:FLASH_AT + 0x100])
    block[0:4], block[252:256] = b"GLST", b"GLED"
    wrong = {}
    for _, name, offset, lo, hi, *_ in w.leaves:
        wrong[name] = lo if name in NOT_STORED_ON else (hi + 1) if hi < 200 and lo == 0 else 0 if lo > 0 else 255
        block[offset] = wrong[name]
    base[FLASH_AT:FLASH_AT + 0x100] = block
    again = w.again(base)
    got = {x[1]: again.byte(x[2]) for x in w.leaves}
    inside = {x[1]: min(x[4], max(x[3], wrong[x[1]])) for x in w.leaves}
    pages = again.pages()
    off = again.switch_off()
    saved = again.saved()
    kept = all(saved[x[2]] == inside[x[1]] for x in w.leaves)
    return [entry("out_of_range_repaired_at_start", got == inside and again.repairs() == len(w.leaves) - len(NOT_STORED_ON) and len(pages) == 19 and not again.dev.m.asserts,
                  f"stored {wrong}, after start {got}, repairs {again.repairs()}, asserts {again.dev.m.asserts}"),
            entry("repaired_block_is_saved", off and kept, f"powered off {off}, flash block inside the limits {kept}")]


def cases(vsb, flash=None):
    leaves = tree()
    out = []
    w = World(vsb, flash, leaves)
    out += pointer_case(w) + leaf_cases(w) + read_only_cases(w)
    w = World(vsb, flash, leaves, w.built)
    out += twin_cases(w)
    w = World(vsb, flash, leaves, w.built)
    out += plugin_cases(w)
    w = World(vsb, flash, leaves, w.built)
    for which in ("hi", "lo"):
        more, w = extreme_cases(w, which)
        out += more
    w = World(vsb, flash, leaves, w.built, adapter=False)     # mains power ignores the power key
    out += switch_off_case(w)
    w = World(vsb, flash, leaves, w.built, adapter=False)
    out += repair_cases(w)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
