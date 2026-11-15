"""Emulator cases of BPM GLIDE (FEATURES > GLIDE CHAIN and GLIDE SWITCH, tools/patch/script_glide.s): with GLIDE CHAIN on the
tempo of a chained pattern glides over its bar to the next pattern's and lands on it at the last step, Chain Repeat stretches it,
STOP gives back the start tempo, OFF leaves the firmware's jump; with GLIDE SWITCH on a pattern confirmed with MENU glides over
the steps left and plays at its own tempo, EXIT takes the confirmation back and the tempo returns; the pages are OFF by default,
the dial switches them and WRITE keeps them in byte 7 of a version 4 settings file.

    python3 tools/emu/bpm_glide_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The same rules as the catalog plugin bpmglide (test/script-bpm-glide.test.mjs); measured in docs/messungen/2026-11-15-bpm-glide.md.
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

import menu_cases as mc  # noqa: E402
import pswitch_cases as ps  # noqa: E402
from machine import load_flash  # noqa: E402

HW_TEMPO, HW_STEP = 0xC0691518, 0xC06904B0         # the tempo in tenths of a BPM, part 1's step counter (script_hw.s)
CHAIN, SWITCH = 4, 8                                # bits of byte 7 (script_menu.s FLAGS2_GLIDE_*)
TEMPO, LENGTH = 34, 37                              # pattern block: tempo u16, length in bars minus one
START, NEXT, OTHER = 4, 6, 9                        # the pattern that plays, the one it chains to, the one confirmed
START_TEMPO, NEXT_TEMPO, OTHER_TEMPO = 1200, 1600, 900


def entry(name, ok, detail):
    return {"id": f"bpm_glide:{name}", "ok": bool(ok), "detail": str(detail)}


def box(payload, flash, flags, chain=True, repeat=1):
    """A device stopped on pattern START (one bar, START_TEMPO) that chains to NEXT (`chain`), byte 7 set to `flags`."""
    b = ps.Box(payload, flash)
    for n, tempo in ((START, START_TEMPO), (NEXT, NEXT_TEMPO), (OTHER, OTHER_TEMPO)):
        b.pattern_bytes(n, TEMPO, struct.pack("<H", tempo))
        b.pattern_bytes(n, LENGTH, [0])
    b.pattern_bytes(START, ps.CHAIN_TO, [NEXT + 1 if chain else 0])
    b.pattern_bytes(START, ps.CHAIN_REPEAT, [repeat])
    b.turn(START)
    b.m.uc.mem_write(mc.MX_FLAGS2, bytes([flags]))
    b.run(0.2)
    return b


def play(b):
    """PLAY, back as soon as the key is up: the steps of the first bar are all still to come."""
    b.t_play = b.m.time_ns
    b.key("play", 0.05)


def tempo(b):
    return b.u32(HW_TEMPO)


def steps(b, count, limit=12.0):
    """Runs until part 1's step counter moved `count` times; the tempo seen at each move, read 60 ms after it (a frame later; a step at 160 BPM is 94 ms)."""
    seen, last, t = [], b.u32(HW_STEP), 0.0
    while len(seen) < count and t < limit:
        b.run(0.01)
        t += 0.01
        now = b.u32(HW_STEP)
        if now != last:
            last = now
            b.run(0.06)
            t += 0.06
            seen.append((now, tempo(b)))
    return seen


def rising(values):
    return all(b >= a for a, b in zip(values, values[1:]))


def chain_cases(payload, flash):
    out = []
    b = box(payload, flash, CHAIN)
    play(b)
    seen = steps(b, 15)
    t = [v for _, v in seen]
    end = b.until_change()
    out.append(entry("chain_glides_and_lands", len(t) == 15 and rising(t) and START_TEMPO < t[0] < t[7] < NEXT_TEMPO and t[-1] == NEXT_TEMPO
                     and b.running() == NEXT and tempo(b) == NEXT_TEMPO and not b.m.asserts,
                     f"tempo at steps 2 to 16 {t}, then pattern {b.running()} after {end} s at {tempo(b)}"))

    b = box(payload, flash, CHAIN, repeat=2)
    play(b)
    first = [v for _, v in steps(b, 16)]
    second = [v for _, v in steps(b, 15)]
    out.append(entry("chain_repeat_stretches_it", rising(first + second) and 1350 <= first[-1] <= 1450 and second[-1] == NEXT_TEMPO and not b.m.asserts,
                     f"Chain Repeat 2: first pass ends at {first[-1]}, second at {second[-1]}"))

    b = box(payload, flash, CHAIN)
    play(b)
    mid = steps(b, 8)[-1][1]
    b.key("stop", 0.5)
    out.append(entry("stop_gives_the_start_tempo_back", START_TEMPO < mid < NEXT_TEMPO and tempo(b) == START_TEMPO and not b.m.asserts,
                     f"tempo at step 9 {mid}, after STOP {tempo(b)}"))

    b = box(payload, flash, 0)
    play(b)
    t = [v for _, v in steps(b, 15)]
    b.until_change()
    out.append(entry("off_leaves_the_jump", set(t) == {START_TEMPO} and b.running() == NEXT and tempo(b) == NEXT_TEMPO and not b.m.asserts,
                     f"both OFF: tempo over the bar {sorted(set(t))}, then pattern {b.running()} at {tempo(b)}"))
    return out


def switch_cases(payload, flash):
    out = []
    b = box(payload, flash, SWITCH, chain=False)
    play(b)
    steps(b, 4)
    b.turn(OTHER - START)
    b.key("menu", 0.05)
    t = [v for _, v in steps(b, 16)]
    b.until_change()
    out.append(entry("switch_glides_to_the_confirmed", t and rising([-v for v in t]) and t[0] < START_TEMPO and OTHER_TEMPO in t
                     and b.running() == OTHER and tempo(b) == OTHER_TEMPO and not b.m.asserts,
                     f"confirmed {OTHER} after 4 steps: tempo at the next 16 {t}, then pattern {b.running()} at {tempo(b)}"))

    b = box(payload, flash, SWITCH, chain=False)
    play(b)
    steps(b, 2)
    b.turn(OTHER - START)
    b.key("menu", 0.05)
    gone = steps(b, 3)[-1][1]
    b.key("exit", 0.05)
    back = [v for _, v in steps(b, 2)]
    out.append(entry("exit_takes_it_back", gone < START_TEMPO and back[-1] == START_TEMPO and b.running() == START and not b.m.asserts,
                     f"after the confirmation {gone}, after EXIT {back}, pattern {b.running()}"))

    b = box(payload, flash, SWITCH | CHAIN)
    play(b)
    steps(b, 4)
    b.turn(OTHER - START)
    b.key("menu", 0.05)
    t = [v for _, v in steps(b, 4)]
    out.append(entry("confirmed_beats_the_chain", len(t) == 4 and rising([-v for v in t]) and t[-1] < t[0] and not b.m.asserts,
                     f"chain to {NEXT} up, {OTHER} confirmed: tempo {t}"))

    b = box(payload, flash, SWITCH, chain=False)
    play(b)
    steps(b, 4)
    b.turn(OTHER - START)
    b.key("menu", 0.05)
    steps(b, 2)
    b.key("stop", 0.5)
    out.append(entry("stop_applies_the_confirmed_tempo", b.running() == OTHER and tempo(b) == OTHER_TEMPO and not b.m.asserts,
                     f"STOP after the confirmation: pattern {b.running()} at {tempo(b)}"))

    b = box(payload, flash, CHAIN)
    play(b)
    mid = steps(b, 6)[-1][1]
    b.m.uc.mem_write(mc.MX_FLAGS2, bytes([0]))
    b.run(0.1)
    out.append(entry("chain_off_while_gliding", START_TEMPO < mid and tempo(b) == START_TEMPO and not b.m.asserts,
                     f"tempo {mid}, GLIDE CHAIN OFF: {tempo(b)}"))
    return out


def page_cases(payload, flash):
    """The two pages are the last of FEATURES, OFF by default; the dial switches at once, WRITE keeps the bits (version 4)."""
    dev = mc.boot(payload, flash, files=mc.CARD_FOLDER, adapter=True, seconds=3.0)
    last = mc.feature_count() - 1
    mc.goto_group(dev, mc.GROUP_FEATURES, last - 1)
    chain_page = mc.texts_of(dev)[:2]
    dev.turn(1, wait=0.4)
    chain_on = mc.texts_of(dev)[:2], dev.read(mc.MX_FLAGS2, 1)[0]
    mc.press(dev, "edit_next")
    switch_page = mc.texts_of(dev)[:2]
    dev.turn(1, wait=0.4)
    switch_on = mc.texts_of(dev)[:2], dev.read(mc.MX_FLAGS2, 1)[0]
    mc.press(dev, "write", wait=0.6)
    dev.run(3.0)
    files = [r for r in mc.settings_raw(dev.m.mmc.card.medium.data).values() if len(r) >= 24 and r[:4] == b"GSET"]
    rec = max(files, key=lambda r: struct.unpack_from("<I", r, 8)[0]) if files else None
    dev.turn(-1, wait=0.4)
    switch_off = dev.read(mc.MX_FLAGS2, 1)[0]
    return [entry("pages_off_by_default", chain_page == ("GLIDE CHAIN", "OFF") and switch_page == ("GLIDE SWITCH", "OFF"),
                  f"FEATURES pages {last - 1} and {last}: {chain_page}, {switch_page}"),
            entry("dial_switches_at_once", chain_on == (("GLIDE CHAIN", "ON"), CHAIN) and switch_on == (("GLIDE SWITCH", "ON"), CHAIN | SWITCH)
                  and switch_off == CHAIN and not dev.m.asserts,
                  f"dial up: {chain_on}, {switch_on}; dial down on GLIDE SWITCH: byte 7 {switch_off}"),
            entry("write_keeps_them_in_byte_7", rec is not None and rec[4] == 4 and rec[7] & (CHAIN | SWITCH) == CHAIN | SWITCH,
                  f"newest file (version, byte 7) {None if rec is None else (rec[4], rec[7])}")]


def cases(payload, flash=None):
    mc.for_build(payload)
    return page_cases(payload, flash) + chain_cases(payload, flash) + switch_cases(payload, flash)


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes()[0x100:], load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
