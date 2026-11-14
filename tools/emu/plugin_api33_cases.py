"""Emulator cases of plugin API 33: korg.read.sampleName reads the name the firmware shows for the part's sample, korg.read.sampleInfo
the values of the sampler's tables (both -1 on the blue synth), korg.pattern.write saves the running pattern into its place as
EXIT + WRITE does (through the firmware's Write window, without it while korg.display.popups is 0), korg.part.copy copies a part
as Part Util COPY PART.

    python3 tools/emu/plugin_api33_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api33-samples.md.
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

from tools.patch import script_hooks  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from shortcut_cases import PART, STEPS, STRIDE, WINDOW, SBox  # noqa: E402

NAMES, PLAY, META, META_SIZE = 0xC047B08C, 0xC0362EE8, 0xC036AD88, 0x45C
SLOT = 900                      # a slot the case fills with values of its own
OFFSET, START, LOOP, END, TUNE, LENGTH, RATE = 0x00123400, 0x1234, 0x2000, 0x8000, -12, 0x10000, 44100

PROGRAMS = {
    "namer": """const a = new Array(16); const b = new Array(4); let slot = -9; let n = -9; let short = -9; let a0 = -9; let a1 = -9; let b3 = -9;
korg.onEvent("ready", () => {
  slot = korg.parts[0].sample; n = korg.read.sampleName(a, slot); short = korg.read.sampleName(b, 400);
  a0 = a[0]; a1 = a[1]; b3 = b[3];
});""",
    "infoer": f"""let i0 = -9; let i1 = -9; let i2 = -9; let i3 = -9; let i4 = -9; let i5 = -9; let i6 = -9; let i7 = -9;
korg.onEvent("ready", () => {{
  i0 = korg.read.sampleInfo({SLOT}, 0); i1 = korg.read.sampleInfo({SLOT}, 1); i2 = korg.read.sampleInfo({SLOT}, 2); i3 = korg.read.sampleInfo({SLOT}, 3);
  i4 = korg.read.sampleInfo({SLOT}, 4); i5 = korg.read.sampleInfo({SLOT}, 5); i6 = korg.read.sampleInfo({SLOT}, 6); i7 = korg.read.sampleInfo({SLOT}, 7);
}});""",
    "saver": """let first = -9; let again = -9; let wrote = -9;
korg.onEvent("write", pattern => { wrote = pattern; });
korg.onEvent("ready", () => { first = korg.pattern.write(); again = korg.pattern.write(); });""",
    "quietsaver": """let first = -9; let again = -9; let wrote = -9;
korg.onEvent("write", pattern => { wrote = pattern; });
korg.onEvent("ready", () => { korg.display.popups = 0; first = korg.pattern.write(); again = korg.pattern.write(); });""",
    "copier": """korg.onEvent("ready", () => { korg.part.copy(1, 3, 0); });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api33:{name}", "ok": bool(ok), "detail": str(detail)}


class Run:
    """A device booted to the main screen with a card (shortcut_cases.SBox); `before` may change it before the program starts."""
    def __init__(self, vsb, flash, name, before=None):
        payload = vsb[0x100:]
        self.build = identify(payload).build
        self.box = SBox(payload, flash)
        self.dev = self.box.dev
        if before:
            before(self)
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"][name]
        built = script_hooks.build(self.request["include"], build=self.build)
        self.at = script_cases.install(self.dev, built, self.request["programs"], [name])[name]
        self.dev.run(1.0)

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)


def name_cases(vsb, flash):
    """The name of the part's sample (the slot is the part value, the display shows slot + 1 and this name) and a short array."""
    r = Run(vsb, flash, "namer")
    v = r.vars()
    if r.build == "synth":
        ok = (v["n"], v["short"]) == (-1, -1)
        return [entry("sample_name", ok and not r.dev.m.asserts, f"build {r.build}: (part's, slot 400) {(v['n'], v['short'])}")]
    name = r.dev.read(NAMES + v["slot"] * 32, 16).split(b"\0")[0]
    other = r.dev.read(NAMES + 400 * 32, 16)
    ok = (v["n"] == len(name) and v["a0"] == name[0] and v["a1"] == name[1] and v["short"] == min(4, len(other.split(b"\0")[0]))
          and v["b3"] == other[3] and not r.dev.m.asserts)
    return [entry("sample_name", ok, f"build {r.build}: part sample {v['slot']} {name!r}: got {v['n']} chars [{v['a0']}, {v['a1']}]; "
                  f"slot 400 into 4 slots {v['short']}, [3] {v['b3']} ({other[:4]!r})")]


def fill(r):
    if r.build == "synth":
        return
    uc = r.box.m.uc
    uc.mem_write(PLAY + SLOT * 16, struct.pack("<III", OFFSET + START, LOOP, END) + bytes([0, 0, 1, 0]))
    meta = META + SLOT * META_SIZE
    uc.mem_write(meta, struct.pack("<II", OFFSET, LENGTH))
    uc.mem_write(meta + 9, bytes([1]))
    uc.mem_write(meta + 16, struct.pack("<I", RATE))
    uc.mem_write(meta + 21, bytes([TUNE & 255]))


def info_cases(vsb, flash):
    """Values written into the three tables come back by field: start without the audio offset, tune signed."""
    r = Run(vsb, flash, "infoer", before=fill)
    v = r.vars()
    got = tuple(v[f"i{i}"] for i in range(8))
    want = (-1,) * 8 if r.build == "synth" else (START, END, LOOP, TUNE, 1, LENGTH, 1, RATE)
    return [entry("sample_info", got == want and not r.dev.m.asserts, f"build {r.build}: fields 0 to 7 {got}, want {want}")]


OTHER_PATTERN = 5                # a running pattern other than the first one (the wheel, stopped, as a player would choose it)
BANK = range(16)                # the places of the bank in RAM


def changed(r, pattern=0):
    """Chooses `pattern` with the wheel, keeps the places of the bank in r.bank before the program can save, changes three sound
    bytes of part 1 in RAM (shortcut_cases.edit) so the pattern differs from its place in the bank, and notes every screen the
    firmware switches to from then on (the number at +0x2C of the screen manager) in r.screens."""
    import shortcut_cases
    import unicorn
    if pattern:
        r.box.turn(pattern)
        r.box.run(1.0)
    r.bank = [r.box.saved(n) for n in BANK]
    shortcut_cases.edit(r.box, 0)
    r.edited = r.box.live() != r.box.saved()
    r.screens = []
    at = r.box.u32(r.box.m.profile.screens) + 0x2C
    r.box.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, lambda uc, access, addr, size, value, data: r.screens.append(value),
                        begin=at, end=at + 3)


def untouched(r):
    """The places of the bank other than the running pattern's are as before the program started."""
    return [n for n in BANK if n != r.box.running() and r.box.saved(n) != r.bank[n]] == []


def write_cases(vsb, flash, pattern=0):
    """korg.pattern.write on the main screen: 1, a second call while the save waits 0, the write event, the bank equals RAM."""
    r = Run(vsb, flash, "saver", before=lambda r: changed(r, pattern))
    r.dev.run(1.0)
    v, box = r.vars(), r.box
    others = untouched(r)
    ok = (r.edited and (v["first"], v["again"]) == (1, 0) and v["wrote"] == box.running() == pattern and box.live() == box.saved()
          and box.screen() == 1 and others and not r.dev.m.asserts)
    window = WINDOW in r.screens
    name = "pattern_write_saves" + (f"_pattern_{pattern + 1}" if pattern else "")
    return [entry(name, ok and window, f"build {r.build}: edited {r.edited}, (first, again) {(v['first'], v['again'])}, "
                  f"write event {v['wrote']} (running {box.running()}, chosen {pattern}), saved {box.live() == box.saved()}, "
                  f"other places untouched {others}, screen {box.screen()}, screens on the way {r.screens}")]


def quiet_write_cases(vsb, flash, pattern=0):
    """korg.display.popups = 0, then korg.pattern.write: the same save without the Write window (no switch to screen 18), 1 and a
    second call 0, the write event; a new start from the flash the save wrote has the edited pattern in its place."""
    r = Run(vsb, flash, "quietsaver", before=lambda r: changed(r, pattern))
    r.dev.run(1.5)
    v, box = r.vars(), r.box
    live = box.live()
    others = untouched(r)
    ok = (r.edited and (v["first"], v["again"]) == (1, 0) and v["wrote"] == box.running() == pattern and live == box.saved()
          and box.screen() == 1 and others and not r.dev.m.asserts)
    again = SBox(vsb[0x100:], bytes(box.m.flash.mem))
    kept = again.saved(box.running()) == live
    name = "pattern_write_quiet" + (f"_pattern_{pattern + 1}" if pattern else "")
    return [entry(name, ok and WINDOW not in r.screens and kept,
                  f"build {r.build}: edited {r.edited}, (first, again) {(v['first'], v['again'])}, write event {v['wrote']} "
                  f"(running {box.running()}, chosen {pattern}), saved {live == box.saved()}, other places untouched {others}, "
                  f"screen {box.screen()}, screens on the way {r.screens}, in its place after a new start {kept}")]


def marked(r):
    """Part 4 of pattern 2 in the bank gets three sound bytes and a step byte of its own."""
    box = r.box
    base = box.slots + 0x4000 + PART + STRIDE * 3
    for a in (13, 24, 25, STEPS):
        box.m.uc.mem_write(base + a, bytes([box.dev.read(base + a, 1)[0] ^ 0x15]))
    r.source = box.saved(1)[PART + STRIDE * 3:PART + STRIDE * 4]
    r.before = box.live()


def copy_cases(vsb, flash):
    """korg.part.copy(1, 3, 0): part 1 of the pattern in RAM becomes part 4 of pattern 2 in the bank, the other parts stay."""
    r = Run(vsb, flash, "copier", before=marked)
    live = r.box.live()
    part = live[PART:PART + STRIDE]
    same = [i for i in range(STRIDE) if part[i] == r.source[i]]
    rest = live[PART + STRIDE:PART + 16 * STRIDE] == r.before[PART + STRIDE:PART + 16 * STRIDE]
    ok = len(same) == STRIDE and rest and not r.dev.m.asserts
    differ = [hex(i) for i in range(STRIDE) if part[i] != r.source[i]][:8]
    return [entry("part_copy", ok, f"build {r.build}: bytes equal to the source {len(same)} of {STRIDE} (differ {differ}), "
                  f"other parts unchanged {rest}")]


def cases(vsb, flash=None):
    return (name_cases(vsb, flash) + info_cases(vsb, flash) + write_cases(vsb, flash) + quiet_write_cases(vsb, flash)
            + write_cases(vsb, flash, OTHER_PATTERN) + quiet_write_cases(vsb, flash, OTHER_PATTERN) + copy_cases(vsb, flash))


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
