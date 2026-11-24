"""Emulator cases of the plugin data files (korg.file.read and korg.file.write, API 32; a folder per plugin with numbered files
since API 39): a write puts bytes into one of the plugin's files on the card, which a read gives back after a power-off; without
a card both return -1; a short file reads up to its end and a write behind a gap fills the gap with 0; one plugin keeps several
files apart, a second file waits while the first still has to go to the card; a file number out of range stops the plugin and
touches nothing; two plugins never see each other's files; a file fills up to SCRIPT_DATA_FILE.maxBytes and no further; the card
is written only on the main screen and at most once in STORE_MIN_PAUSE_FRAMES.

    python3 tools/emu/plugin_api32_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api32-data-file.md and docs/messungen/2026-11-17-plugin-daten-heap.md.
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
import lifetime  # noqa: E402

FOLDER = "/KORG/blechtribe/Plugin/Data/"
SHORT = bytes([1, 2, 3, 4, 5])
MAX_BYTES = 32768               # SCRIPT_DATA_FILE.maxBytes
ERR_API_ARG = 15
STATE_FAULT = 3
MAIN_SCREEN = 1
DATA_UTILITY = 14

PROGRAMS = {
    "keeper": """const buf = new Array(8); let got = -9; let wrote = -9; let b0 = -9; let b3 = -9; let b7 = -9;
korg.onEvent("ready", () => {
  got = korg.file.read(buf, 0, 0);
  b0 = buf[0]; b3 = buf[3]; b7 = buf[7];
  if (got === 0) {
    buf[0] = 7; buf[1] = 8; buf[2] = 9; buf[3] = 300; buf[4] = 1; buf[5] = 0; buf[6] = 0; buf[7] = 255;
    wrote = korg.file.write(buf, 0, 0);
  }
});""",
    "writer": """const buf = new Array(4); let got = -9; let wrote = -9;
korg.onEvent("ready", () => { got = korg.file.read(buf, 0, 0); wrote = korg.file.write(buf, 2, 0); });""",
    "shorty": """const a = new Array(16); const b = new Array(16); const c = new Array(16); const d = [42, 43];
let all = -9; let tail = -9; let past = -9; let wrote = -9; let a4 = -9; let b0 = -9; let b2 = -9; let b3 = -9;
korg.onEvent("ready", () => {
  all = korg.file.read(a, 0, 0); tail = korg.file.read(b, 2, 0); past = korg.file.read(c, 9, 0);
  a4 = a[4]; b0 = b[0]; b2 = b[2]; b3 = b[3];
  wrote = korg.file.write(d, 10, 0);
});""",
    "multi": """const a = new Array(4); const w = [4, 4]; const z = [6, 6, 6];
let r5 = -9; let a5 = -9; let r15 = -9; let a15 = -9; let r7 = -9; let w2 = -9; let early = -9; let w3 = -9; let tries = 0;
korg.onEvent("ready", () => {
  r5 = korg.file.read(a, 0, 5); a5 = a[0];
  r15 = korg.file.read(a, 0, 15); a15 = a[0];
  r7 = korg.file.read(a, 0, 7);
  w2 = korg.file.write(w, 0, 2);
  early = korg.file.write(z, 0, 3);
});
korg.onEvent("frame", () => { if (w3 < 0) { w3 = korg.file.write(z, 0, 3); tries = tries + 1; } });""",
    "outer": """const b = new Array(4); let n = 16; let got = -9;
korg.onEvent("ready", () => { got = korg.file.read(b, 0, n); });""",
    "under": """const b = [1, 2]; let n = -1; let wrote = -9;
korg.onEvent("ready", () => { wrote = korg.file.write(b, 0, n); });""",
    "alpha": """const d = [1, 2, 3]; let wrote = -9;
korg.onEvent("ready", () => { wrote = korg.file.write(d, 0, 0); });""",
    "beta": """const b = new Array(4); let got = -9; let b0 = -9; let b1 = -9; let tries = 0;
korg.onEvent("frame", () => { if (got < 0) { got = korg.file.read(b, 0, 0); b0 = b[0]; b1 = b[1]; tries = tries + 1; } });""",
    "big": """const a = new Array(16000); const e = new Array(1000); let s = 0; let w1 = -9; let w2 = -9; let w3 = -9; let r = -9; let e0 = -9;
korg.onEvent("ready", () => { a[0] = 11; a[15999] = 22; e[760] = 77; });
korg.onEvent("frame", () => {
  s = s + 1;
  if (s === 1) { w1 = korg.file.write(a, 0, 1); }
  if (s === 2) { w2 = korg.file.write(a, 16000, 1); }
  if (s === 3) { w3 = korg.file.write(e, 32000, 1); }
  if (s === 4) { r = korg.file.read(e, 32760, 1); e0 = e[0]; }
});""",
    "timing": """const d = [1]; let t0 = -1; let first = -9; let second = -9; let third = -9;
korg.onEvent("ready", () => { t0 = korg.millis(); first = korg.file.write(d, 0, 0); });
korg.onEvent("frame", () => {
  if (second === -9 && korg.millis() - t0 > 2500) { d[0] = 2; second = korg.file.write(d, 0, 0); }
  if (third === -9 && korg.millis() - t0 > 7500) { d[0] = 3; third = korg.file.write(d, 0, 0); }
});""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api32:{name}", "ok": bool(ok), "detail": str(detail)}


def card_file(dev, path):
    """The bytes of a data file on the card in the device (`path` below Plugin/Data/), None when there is none."""
    volume = fat32.Volume(dev.m.mmc.card.medium.data)
    try:
        return volume.read(FOLDER + path)
    except fat32.FatError:
        return None
    finally:
        volume.close()


def show(data):
    return None if data is None else (data.hex() if len(data) <= 16 else f"{len(data)} bytes")


class Run:
    """A device booted to the main screen (from `files` or a card image, or without a card) that runs the programs `names`."""
    def __init__(self, vsb, flash, names, files=None, image=None, card=True):
        names = [names] if isinstance(names, str) else names
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled(PROGRAMS)
        self.built = script_hooks.build(self.request["include"], build=self.build)
        if image is None:
            self.dev = menu_cases.boot(self.payload, flash, files=files or menu_cases.CARD_FOLDER, card=card, seconds=2.0)
        else:
            self.dev = menu_cases.Dev(self.payload, flash, 0)
            self.dev.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
            self.dev.run(2.0)
        self.dev.run(1.0)
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], names)
        self.dev.run(0.5)

    def vars(self, name):
        return script_cases.variables(self.dev, self.at[name], self.request["programs"][name])

    def fault(self, name):
        """(state, fault) of a plugin's entry."""
        return self.dev.u32(self.at[name] + 12), self.dev.u32(self.at[name] + 16)


def keep_cases(vsb, flash):
    """No file: read gives 0, the write takes 8 bytes and the card has them in keeper/00.bin after the pause; after a power-off
    read gives them back."""
    first = Run(vsb, flash, "keeper")
    first.dev.run(3.0)
    v1, stored = first.vars("keeper"), card_file(first.dev, "keeper/00.bin")
    want = bytes([7, 8, 9, 300 & 255, 1, 0, 0, 255])
    image = bytes(first.dev.m.mmc.card.medium.data)
    again = Run(vsb, flash, "keeper", image=image)
    v2 = again.vars("keeper")
    ok = ((v1["got"], v1["wrote"]) == (0, 8) and stored == want
          and (v2["got"], v2["wrote"], v2["b0"], v2["b3"], v2["b7"]) == (8, -9, 7, 44, 255)
          and not first.dev.m.asserts and not again.dev.m.asserts)
    return [entry("write_power_off_read", ok, f"build {first.build}: first (read, write) {(v1['got'], v1['wrote'])}, card "
                  f"{show(stored)}, after power-off (read, write, [0], [3], [7]) "
                  f"{(v2['got'], v2['wrote'], v2['b0'], v2['b3'], v2['b7'])}")]


def card_missing_cases(vsb, flash):
    """No card: read and write both -1."""
    w = Run(vsb, flash, "writer", card=False)
    v = w.vars("writer")
    return [entry("card_missing", (v["got"], v["wrote"]) == (-1, -1) and not w.dev.m.asserts,
                  f"build {w.build}: (read, write) {(v['got'], v['wrote'])}")]


def short_cases(vsb, flash):
    """A file of 5 bytes: read from 0 gives 5, from 2 gives 3, from 9 gives 0; a write at 10 leaves a gap of zeros on the card."""
    files = dict(menu_cases.CARD_FOLDER)
    files[FOLDER + "shorty/00.bin"] = SHORT
    s = Run(vsb, flash, "shorty", files=files)
    s.dev.run(3.0)
    v, stored = s.vars("shorty"), card_file(s.dev, "shorty/00.bin")
    got = (v["all"], v["tail"], v["past"], v["a4"], v["b0"], v["b2"], v["b3"], v["wrote"])
    want = SHORT + bytes(5) + bytes([42, 43])
    ok = got == (5, 3, 0, 5, 3, 5, 0, 2) and stored == want and not s.dev.m.asserts
    return [entry("short_file_and_gap", ok, f"build {s.build}: (from 0, from 2, from 9, a[4], b[0], b[2], b[3], write) {got}, "
                  f"card {show(stored)}")]


def multi_cases(vsb, flash):
    """Files 5 and 15 on the card read back on their own, file 7 is empty; file 2 takes a write, file 3 gives -1 until file 2 is on
    the card, then takes its own; the card ends with 02, 03, 05 and 15 apart and no 07."""
    files = dict(menu_cases.CARD_FOLDER)
    files[FOLDER + "multi/05.bin"] = bytes([9, 9, 9])
    files[FOLDER + "multi/15.bin"] = bytes([1])
    m = Run(vsb, flash, "multi", files=files)
    m.dev.run(6.0)
    v = m.vars("multi")
    cards = {n: card_file(m.dev, f"multi/{n:02d}.bin") for n in (2, 3, 5, 7, 15)}
    got = (v["r5"], v["a5"], v["r15"], v["a15"], v["r7"], v["w2"], v["early"], v["w3"])
    ok = (got == (3, 9, 1, 1, 0, 2, -1, 3) and v["tries"] > 1
          and cards == {2: bytes([4, 4]), 3: bytes([6, 6, 6]), 5: bytes([9, 9, 9]), 7: None, 15: bytes([1])}
          and not m.dev.m.asserts)
    return [entry("several_files", ok, f"build {m.build}: (read 5, [0], read 15, [0], read 7, write 2, write 3 at once, write 3) "
                  f"{got} after {v['tries']} tries, card { {n: show(d) for n, d in cards.items()} }")]


def range_cases(vsb, flash):
    """File 16 and file -1 stop the plugin with API_ARG before any card access: no folder of theirs on the card."""
    r = Run(vsb, flash, ["outer", "under"])
    r.dev.run(3.0)
    faults = {n: r.fault(n) for n in ("outer", "under")}
    values = (r.vars("outer")["got"], r.vars("under")["wrote"])
    volume = fat32.Volume(r.dev.m.mmc.card.medium.data)
    try:
        listed = sorted(e.name for e in volume.listdir(FOLDER.rstrip("/")))
    except fat32.FatError:
        listed = []
    finally:
        volume.close()
    ok = (faults == {"outer": (STATE_FAULT, ERR_API_ARG), "under": (STATE_FAULT, ERR_API_ARG)} and values == (-9, -9)
          and not any(n.lower() in ("outer", "under") for n in listed) and not r.dev.m.asserts)
    return [entry("file_out_of_range", ok, f"build {r.build}: (state, fault) {faults}, results {values}, Data/ holds {listed}")]


def isolation_cases(vsb, flash):
    """alpha writes its file 0 while beta reads its own file 0: beta gets -1 while alpha's write waits for the card, then its own
    byte, never alpha's; the card keeps alpha/00.bin and beta/00.bin apart."""
    files = dict(menu_cases.CARD_FOLDER)
    files[FOLDER + "beta/00.bin"] = bytes([7])
    i = Run(vsb, flash, ["alpha", "beta"], files=files)
    i.dev.run(5.0)
    a, b = i.vars("alpha"), i.vars("beta")
    cards = (card_file(i.dev, "alpha/00.bin"), card_file(i.dev, "beta/00.bin"))
    got = (a["wrote"], b["got"], b["b0"], b["b1"])
    ok = got == (3, 1, 7, 0) and cards == (bytes([1, 2, 3]), bytes([7])) and not i.dev.m.asserts
    return [entry("two_plugins_apart", ok, f"build {i.build}: (alpha write, beta read, [0], [1]) {got} after {b['tries']} tries, "
                  f"card (alpha, beta) {tuple(show(c) for c in cards)}")]


def size_cases(vsb, flash):
    """Two writes of 16000 and one at 32000 fill the file exactly to SCRIPT_DATA_FILE.maxBytes (the last takes 768 of 1000);
    a read near the end gives the 8 bytes left; the card has all of it."""
    s = Run(vsb, flash, "big")
    s.dev.run(4.0)
    v, stored = s.vars("big"), card_file(s.dev, "big/01.bin")
    got = (v["w1"], v["w2"], v["w3"], v["r"], v["e0"])
    ok = (got == (16000, 16000, MAX_BYTES - 32000, 8, 77) and stored is not None and len(stored) == MAX_BYTES
          and (stored[0], stored[15999], stored[32760]) == (11, 22, 77) and not s.dev.m.asserts)
    return [entry("size_limit_edge", ok, f"build {s.build}: (write 0, write 16000, write 32000, read 32760, [0]) {got}, card "
                  f"{show(stored)}")]


def timing_cases(vsb, flash):
    """The card is written as before: the first write after the pause, the second not sooner than STORE_MIN_PAUSE_FRAMES (2 s)
    after the first card write; a write while another screen is up stays off the card until the main screen is back."""
    t = Run(vsb, flash, "timing")
    seen, last, at = [], None, 0.0
    for _ in range(22):                        # 5.5 s on the main screen, every 0.25 s
        t.dev.run(0.25)
        at += 0.25
        now = card_file(t.dev, "timing/00.bin")
        if now != last:
            seen.append((at, show(now)))
            last = now
    menu_cases.go(t.dev, DATA_UTILITY)
    t.dev.run(4.0)
    away = card_file(t.dev, "timing/00.bin")
    written_away = t.vars("timing")["third"]
    menu_cases.go(t.dev, MAIN_SCREEN)
    t.dev.run(3.0)
    back = card_file(t.dev, "timing/00.bin")
    v = t.vars("timing")
    firsts = [s for s in seen if s[1] == "01"]
    seconds = [s for s in seen if s[1] == "02"]
    gap = seconds[0][0] - firsts[0][0] if firsts and seconds else None
    ok = ((v["first"], v["second"], v["third"]) == (1, 1, 1) and gap is not None and gap >= 1.9
          and written_away == 1 and away == bytes([2]) and back == bytes([3]) and not t.dev.m.asserts)
    return [entry("write_timing", ok, f"build {t.build}: writes {(v['first'], v['second'], v['third'])}, card over time {seen}, "
                  f"gap {gap}, on another screen write {written_away} card {show(away)}, back on the main screen {show(back)}")]


def cases(vsb, flash=None):
    return (keep_cases(vsb, flash) + card_missing_cases(vsb, flash) + short_cases(vsb, flash) + multi_cases(vsb, flash)
            + range_cases(vsb, flash) + isolation_cases(vsb, flash) + size_cases(vsb, flash) + timing_cases(vsb, flash))


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
