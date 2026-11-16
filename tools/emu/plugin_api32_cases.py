"""Emulator cases of plugin API 32: korg.file.write puts bytes into the plugin's data file on the card, which korg.file.read
gives back after a power-off; without a card both return -1; a short file reads up to its end and a write behind a gap fills
the gap with 0.

    python3 tools/emu/plugin_api32_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api32-data-file.md.
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
import fat32  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402

FOLDER = "/KORG/blechtribe/Plugin/Data/"
SHORT = bytes([1, 2, 3, 4, 5])

PROGRAMS = {
    "keeper": """const buf = new Array(8); let got = -9; let wrote = -9; let b0 = -9; let b3 = -9; let b7 = -9;
korg.onEvent("ready", () => {
  got = korg.file.read(buf, 0);
  b0 = buf[0]; b3 = buf[3]; b7 = buf[7];
  if (got === 0) {
    buf[0] = 7; buf[1] = 8; buf[2] = 9; buf[3] = 300; buf[4] = 1; buf[5] = 0; buf[6] = 0; buf[7] = 255;
    wrote = korg.file.write(buf, 0);
  }
});""",
    "writer": """const buf = new Array(4); let got = -9; let wrote = -9;
korg.onEvent("ready", () => { got = korg.file.read(buf, 0); wrote = korg.file.write(buf, 2); });""",
    "shorty": """const a = new Array(16); const b = new Array(16); const c = new Array(16); const d = [42, 43];
let all = -9; let tail = -9; let past = -9; let wrote = -9; let a4 = -9; let b0 = -9; let b2 = -9; let b3 = -9;
korg.onEvent("ready", () => {
  all = korg.file.read(a, 0); tail = korg.file.read(b, 2); past = korg.file.read(c, 9);
  a4 = a[4]; b0 = b[0]; b2 = b[2]; b3 = b[3];
  wrote = korg.file.write(d, 10);
});""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api32:{name}", "ok": bool(ok), "detail": str(detail)}


def card_file(dev, name):
    """The bytes of a plugin's data file on the card in the device, None when there is none."""
    volume = fat32.Volume(dev.m.mmc.card.medium.data)
    try:
        return volume.read(FOLDER + name + ".bin")
    except fat32.FatError:
        return None
    finally:
        volume.close()


class Run:
    """A device booted to the main screen (from `files` or a card image, or without a card) that runs one program."""
    def __init__(self, vsb, flash, name, files=None, image=None, card=True):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"][name]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        if image is None:
            self.dev = menu_cases.boot(self.payload, flash, files=files or menu_cases.CARD_FOLDER, card=card, seconds=2.0)
        else:
            self.dev = menu_cases.Dev(self.payload, flash, 0)
            self.dev.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
            self.dev.run(2.0)
        self.dev.run(1.0)
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], [name])[name]
        self.dev.run(0.5)

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)


def keep_cases(vsb, flash):
    """No file: read gives 0, the write takes 8 bytes and the card has them after the pause; after a power-off read gives them back."""
    first = Run(vsb, flash, "keeper")
    first.dev.run(3.0)
    v1, stored = first.vars(), card_file(first.dev, "keeper")
    want = bytes([7, 8, 9, 300 & 255, 1, 0, 0, 255])
    image = bytes(first.dev.m.mmc.card.medium.data)
    again = Run(vsb, flash, "keeper", image=image)
    v2 = again.vars()
    ok = ((v1["got"], v1["wrote"]) == (0, 8) and stored == want
          and (v2["got"], v2["wrote"], v2["b0"], v2["b3"], v2["b7"]) == (8, -9, 7, 44, 255)
          and not first.dev.m.asserts and not again.dev.m.asserts)
    return [entry("write_power_off_read", ok, f"build {first.build}: first (read, write) {(v1['got'], v1['wrote'])}, card "
                  f"{None if stored is None else stored.hex()}, after power-off (read, write, [0], [3], [7]) "
                  f"{(v2['got'], v2['wrote'], v2['b0'], v2['b3'], v2['b7'])}")]


def card_missing_cases(vsb, flash):
    """No card: read and write both -1."""
    w = Run(vsb, flash, "writer", card=False)
    v = w.vars()
    return [entry("card_missing", (v["got"], v["wrote"]) == (-1, -1) and not w.dev.m.asserts,
                  f"build {w.build}: (read, write) {(v['got'], v['wrote'])}")]


def short_cases(vsb, flash):
    """A file of 5 bytes: read from 0 gives 5, from 2 gives 3, from 9 gives 0; a write at 10 leaves a gap of zeros on the card."""
    files = dict(menu_cases.CARD_FOLDER)
    files[FOLDER + "shorty.bin"] = SHORT
    s = Run(vsb, flash, "shorty", files=files)
    s.dev.run(3.0)
    v, stored = s.vars(), card_file(s.dev, "shorty")
    got = (v["all"], v["tail"], v["past"], v["a4"], v["b0"], v["b2"], v["b3"], v["wrote"])
    want = SHORT + bytes(5) + bytes([42, 43])
    ok = got == (5, 3, 0, 5, 3, 5, 0, 2) and stored == want and not s.dev.m.asserts
    return [entry("short_file_and_gap", ok, f"build {s.build}: (from 0, from 2, from 9, a[4], b[0], b[2], b[3], write) {got}, "
                  f"card {None if stored is None else stored.hex()}")]


def cases(vsb, flash=None):
    return keep_cases(vsb, flash) + card_missing_cases(vsb, flash) + short_cases(vsb, flash)


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
