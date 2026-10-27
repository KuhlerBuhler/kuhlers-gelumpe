# SPDX-License-Identifier: GPL-2.0-only
"""Blechy in the firmware, built into BLECH: he is the last page of the menu ring (after Event), loaded from the image
at start with no card and no plugin file. A second after you land on his page he waves, once per landing, then he walks
slowly between the two edges and now and then says something there; a tap makes him angry, stroking happy; PLAY sends him
to the middle, he listens (bubble) and dances with the steps until STOP, then he walks again. EXIT and EDIT leave the page. Writes a picture of each state and the cost of each handler in Timer3 ticks. The request carries
his variable slots: `{"symbols": ...}`, made by the test from the compiled source.

    tools/emu/.venv/bin/python tools/emu/blechy_cases.py --base BLECH.VSB --request FILE --png-dir DIR [--flash flash.bin]
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

import menu_cases  # noqa: E402
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

RUNTIME = 0xC01AE000
HW_TRANSPORT = 0xC06BC318      # the firmware's transport word, as tools/patch/script_hw.s reads it
EVENTS = ["start", "ready", "frame", "buttonPress", "buttonRelease", "knob", "encoder", "pad", "touch", "step", "beat",
          "play", "stop", "rec", "patternChange", "partChange", "mute", "tempo", "save", "menu", "open", "close"]
MAX_EVENT_TICKS = 44 + len(EVENTS) * 4
KEY = dict(stop=1, play=2, touchpad=34, exit=13)
TICKS_PER_MS = 150000
FRAME_NAMES = ["idle", "twitch", "angry", "happy", "flail0", "flail1", "flail2", "flail3", "wave0", "wave1", "walk", "back0", "back1"]
WAVE = (FRAME_NAMES.index("wave0"), FRAME_NAMES.index("wave1"))
WALK = FRAME_NAMES.index("walk")
BACK = (FRAME_NAMES.index("back0"), FRAME_NAMES.index("back1"))
ON_FOOT = (0, 1, WALK) + BACK        # the pictures of standing and walking
FLAIL = range(4, 8)
B_LISTEN = 9
STATE_STARTED, STATE_ARMED = 1, 2


class Run:
    def __init__(self, vsb, flash, request, png_dir):
        self.request, self.png_dir, self.checks, self.shots = request, png_dir, [], {}
        self.dev = menu_cases.boot(vsb[0x100:], flash, card=False, seconds=2)
        self.entry = self.dev.u32(RUNTIME)

    def check(self, name, ok, detail=None):
        self.checks.append(dict(id=name, ok=bool(ok), detail=detail))

    def var(self, name):
        base = self.dev.u32(self.entry + 8)
        return struct.unpack("<i", self.dev.read(base + self.request["symbols"][name]["slot"] * 4, 4))[0]

    def shot(self, name):
        path = self.png_dir / ("blechy-emu-" + name + ".png")
        self.dev.m.png(path, scale=5)
        self.shots[name] = self.dev.fb().hex()
        return self.dev.fb()

    def strip(self, name, pictures, scale=3, gap=2):
        """Several displays (1024 bytes each, as fb() returns them) side by side in one PNG, a lit pixel black."""
        width = (128 + gap) * len(pictures) - gap
        rows = b""
        for y in range(64):
            line = b""
            for i, fb in enumerate(pictures):
                line += (b"\x80" * gap if i else b"") + bytes(0 if (fb[(y // 8) * 128 + x] >> (y % 8)) & 1 else 255 for x in range(128))
            rows += (b"\0" + b"".join(bytes([c]) * scale for c in line)) * scale

        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        (self.png_dir / ("blechy-emu-" + name + ".png")).write_bytes(
            b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width * scale, 64 * scale, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))

    def key(self, code, hold=0.08, wait=0.15):
        self.dev.m.send([0, code, 1, 0, 0])
        self.dev.run(hold)
        self.dev.m.send([0, code, 0, 0, 0])
        self.dev.run(wait)

    def touch(self, points, hold=0.0):
        self.dev.m.send([0, KEY["touchpad"], 1, 0, 0])
        for x, y in points:
            self.dev.m.send([5, x >> 8, x & 255, y >> 8, y & 255])
            self.dev.run(0.06)
        self.dev.run(hold)
        self.dev.m.send([0, KEY["touchpad"], 0, 0, 0])
        self.dev.run(0.12)

    def frame(self):
        return self.var("lastSig") & 15

    def bubble(self):
        return (self.var("lastSig") >> 4) & 15

    def pos(self):
        return self.var("posX")

    def touch_him(self, dx=0):
        """A tap or stroke on the touchpad where he stands (FIG_LEFT 5, FIG_RIGHT 45 at offset 0; a pad column is 8 units)."""
        return (self.pos() + 25 + dx) * 8

    def ticks(self):
        return {name: self.dev.u32(self.entry + MAX_EVENT_TICKS + i * 4) for i, name in enumerate(EVENTS)}

    def land(self):
        """The way a user gets to his page: EDIT right from Event. Returns the device time of the landing, in ms."""
        menu_cases.go(self.dev, 10)
        self.dev.m.send([0, menu_cases.KEYS["edit_next"], 1, 0, 0])
        self.dev.run(0.08)
        self.dev.m.send([0, menu_cases.KEYS["edit_next"], 0, 0, 0])
        t0 = self.dev.m.time_ns / 1e6
        for _ in range(60):
            if self.dev.screen()["number"] == menu_cases.MENU and self.var("isOpen") == 1:
                break
            self.dev.run(0.02)
        return t0

    def leave_and_return(self):
        """EDIT right to the Pattern menu and EDIT left back: a new landing."""
        menu_cases.press(self.dev, "edit_next", wait=0.5)
        menu_cases.press(self.dev, "edit_prev", wait=0.3)


def run(vsb, flash, request, png_dir):
    r = Run(vsb, flash, request, png_dir)
    dev = r.dev
    page = dev.read(script_hooks.MENU_STATE, 4)
    blob = dev.u32(r.entry + 4)
    r.check("blechy-geladen-ohne-karte", dev.u32(RUNTIME) not in (0, 0xffffffff) and dev.u32(r.entry + 12) == STATE_ARMED and dev.u32(RUNTIME + 96) == 1
            and struct.unpack("<I", page)[0] == 1 and dev.u32(RUNTIME + 164) == 2, dict(entry=hex(r.entry), state=dev.u32(r.entry + 12)))
    r.check("blechy-block-liegt-im-abbild-nicht-im-pool", blob == script_hooks.BLECHY_BLOCK and blob < script_hooks.POOL, hex(blob))
    r.check("blechy-nicht-in-den-plugin-seiten", dev.u32(script_hooks.MENU_STATE + 40) == 0, dev.u32(script_hooks.MENU_STATE + 40))
    stock = menu_cases.boot(vsb[0x100:], flash, held=menu_cases.KILL, card=False, seconds=2)
    r.check("blechy-zu-zeichnet-nichts", dev.screen()["number"] == 1 and r.var("isOpen") == 0 and dev.fb() == stock.fb() and not dev.m.asserts,
            dict(screen=dev.screen(), same_display=dev.fb() == stock.fb()))

    t0 = r.land()
    landed_at = dev.m.time_ns / 1e6
    r.check("blechy-oeffnet-auf-der-ringseite", dev.screen()["number"] == menu_cases.MENU and dev.u32(script_hooks.MENU_STATE + menu_cases.S_LEVEL) == 3
            and r.var("isOpen") == 1 and r.frame() in (0, 1) and not dev.m.asserts, dict(screen=dev.screen(), counter=menu_cases.counter(dev)))
    idle = r.shot("idle")
    r.check("blechy-idle-gezeichnet", any(idle), "the display holds a picture")

    # the wave: not before about a second, then the hand swings, then he stands again; once per landing
    seen, start, end = [], None, None
    while dev.m.time_ns / 1e6 - t0 < 5200:
        dev.run(0.04)
        now = dev.m.time_ns / 1e6 - t0
        frame = r.frame()
        seen.append((now, frame))
        if frame in WAVE:
            start = now if start is None else start
            end = now
            if "wave-%d" % (frame - WAVE[0]) not in r.shots:
                dev.run(0.06)           # the display follows the variable by a frame
                r.shot("wave-%d" % (frame - WAVE[0]))
    waves = [f for _, f in seen if f in WAVE]
    swings = sum(1 for a, b in zip(waves, waves[1:]) if a != b)
    r.check("blechy-winkt-nach-einer-sekunde", start is not None and 900 <= start <= 1400, dict(start_ms=start))
    r.check("blechy-winkt-die-hand-schwingt", end is not None and 1500 <= end - start <= 2100 and 6 <= swings <= 10, dict(duration_ms=None if start is None else end - start, swings=swings))
    wave_a, wave_b = r.shots.get("wave-0"), r.shots.get("wave-1")
    r.check("blechy-wink-bilder-verschieden", wave_a is not None and wave_b is not None and len({idle.hex(), wave_a, wave_b}) == 3)
    r.check("blechy-steht-danach", r.frame() in ON_FOOT, r.frame())
    dev.run(6.0)
    again_waving = 0
    for _ in range(150):
        dev.run(0.04)
        again_waving += r.frame() in WAVE
    r.check("blechy-winkt-nur-einmal", again_waving == 0, again_waving)

    # a second landing: he waves again
    r.leave_and_return()
    again = False
    t1 = dev.m.time_ns / 1e6
    while dev.m.time_ns / 1e6 - t1 < 3000:
        dev.run(0.04)
        again = again or r.frame() in WAVE
    r.check("blechy-winkt-bei-jeder-landung", again and r.var("isOpen") == 1, r.var("isOpen"))
    dev.run(2.0)

    r.touch([(r.touch_him(), 500)])
    dev.run(0.1)
    r.check("blechy-tippen-wuetend", r.frame() == 2, r.frame())
    angry = r.shot("angry")
    dev.run(1.6)
    r.check("blechy-wuetend-vorbei", r.frame() in ON_FOOT, r.frame())

    x = r.touch_him()
    r.touch([(x, 500), (x + 70, 500), (x + 140, 520), (x + 200, 500)], hold=0.05)
    dev.run(0.1)
    r.check("blechy-streicheln-froh", r.frame() == 3, r.frame())
    happy = r.shot("happy")
    r.check("blechy-bilder-verschieden", len({idle.hex(), angry.hex(), happy.hex()}) == 3)
    r.check("blechy-bleibt-auf-seiner-seite", dev.screen()["number"] == menu_cases.MENU and dev.u32(script_hooks.MENU_STATE + menu_cases.S_LEVEL) == 3 and not dev.m.asserts)
    dev.run(2.0)

    # PLAY from the panel reaches the firmware with his page shown (the plugin sees the key too, it passes nothing on itself)
    # while he is open and idle he walks: not at the same place twice in a row, one pixel at a time
    xs = []
    for _ in range(100):
        dev.run(0.2)
        xs.append(r.pos())
    r.check("blechy-geht-langsam", len(set(xs)) >= 10 and all(abs(b - a) <= 3 for a, b in zip(xs, xs[1:])) and r.frame() in ON_FOOT, dict(first=xs[:5], last=xs[-5:]))
    r.shot("geht")

    # the walk cycle: the calm and the walk picture in turn about every 240 ms, mirrored while he goes left, the plain calm
    # picture when he stands (also right after the turn at an edge). One display of each, taken from the display RAM.
    names = {(1, 0): "rechts-ruhig", (1, WALK): "rechts-gehen", (-1, BACK[0]): "links-ruhig", (-1, BACK[1]): "links-gehen", (-1, 0): "wende"}
    cycle, changes, last, seen_pairs = {}, [], None, set()
    end = dev.m.time_ns + 120e9
    while dev.m.time_ns < end and len(cycle) < len(names):
        dev.run(0.03)
        frame, way, x, y, bubble = r.frame(), r.var("dir"), r.pos(), r.var("posY"), r.bubble()
        if bubble or frame not in ON_FOOT:
            continue
        seen_pairs.add((way, frame, x >= 60))
        if last and last[0] != frame and last[1] == way and frame != 1 and last[0] != 1:
            changes.append(dev.m.time_ns / 1e6 - last[2])
        if not last or last[0] != frame or last[1] != way:
            last = (frame, way, dev.m.time_ns / 1e6)
        key = names.get((way, frame))
        if key and key not in cycle and (key == "wende" and x >= 60 or key != "wende" and 6 <= x <= 60):
            dev.run(0.06)           # the display follows the variable by a frame
            if (r.frame(), r.var("dir"), r.pos(), r.var("posY")) == (frame, way, x, y):
                cycle[key] = dict(frame=frame, dir=way, posX=x, posY=y, hex=r.shot("gang-" + key).hex())
    changes.sort()
    r.check("blechy-gang-alle-fuenf-bilder", sorted(cycle) == sorted(names.values()), dict(have=sorted(cycle), seen=sorted(seen_pairs)))
    r.check("blechy-gang-wechselt-etwa-alle-240ms", len(changes) >= 8 and 180 <= changes[len(changes) // 2] <= 300, dict(n=len(changes), median=changes[len(changes) // 2] if changes else None))
    r.check("blechy-gang-gespiegelt-nach-links", all(cycle.get(k, {}).get("dir") == -1 for k in ("links-ruhig", "links-gehen")) and len({cycle[k]["hex"] for k in cycle}) == len(cycle), None)
    if len(cycle) == len(names):
        r.strip("gang", [bytes.fromhex(cycle[k]["hex"]) for k in ("rechts-ruhig", "rechts-gehen", "wende", "links-ruhig", "links-gehen")])
    r.cycle = cycle

    # PLAY from the panel reaches the firmware with his page shown (the plugin sees the key too, it passes nothing on itself)
    r.key(KEY["play"])
    dev.run(0.5)
    r.check("blechy-play-startet-den-sequencer", dev.u32(HW_TRANSPORT) == 1, dev.u32(HW_TRANSPORT))
    r.check("blechy-play-taste-gereicht", r.var("playing") == 1, r.var("playing"))
    r.check("blechy-play-geht-zur-mitte", r.var("mode") in (1, 2), r.var("mode"))
    end = dev.m.time_ns + 20e9
    while dev.m.time_ns < end and r.bubble() != B_LISTEN:
        dev.run(0.05)
    r.check("blechy-hoert-zu", r.bubble() == B_LISTEN and r.pos() == 24 and r.var("mode") == 2, dict(bubble=r.bubble(), pos=r.pos(), mode=r.var("mode")))
    dev.run(0.1)
    r.shot("play-zuhoeren")
    flail = {}
    end = dev.m.time_ns + 15e9
    while dev.m.time_ns < end and len(flail) < 4:
        dev.run(0.05)
        if r.frame() in FLAIL and r.frame() not in flail:
            flail[r.frame()] = r.shot("schranz-%d" % (r.frame() - 4))
    r.check("blechy-schranz-nach-dem-zuhoeren", len(flail) >= 3 and r.pos() == 24 and r.bubble() == 0, dict(flail=sorted(flail), pos=r.pos()))
    flips = 0
    last = r.frame()
    for _ in range(100):
        dev.run(0.04)
        now = r.frame()
        flips += now != last
        last = now
    r.check("blechy-schranz-wechselt-mit-den-steps", flips >= 5, flips)

    r.key(KEY["stop"])
    dev.run(0.3)
    r.check("blechy-stop-stoppt-den-sequencer", dev.u32(HW_TRANSPORT) == 0, dev.u32(HW_TRANSPORT))
    dev.run(1.5)
    r.check("blechy-stop-keine-frage-er-geht-weiter", r.bubble() == 0 and r.frame() in ON_FOOT and r.var("mode") == 0, dict(frame=r.frame(), bubble=r.bubble()))

    # he walks to an edge and says something there; the bubble is on the side that has room
    talked = []
    end = dev.m.time_ns + 90e9
    while dev.m.time_ns < end and len(talked) < 2:
        dev.run(0.1)
        if 1 <= r.bubble() <= 8 and (not talked or talked[-1] != r.var("talkNo")):
            dev.run(0.1)
            talked.append(r.var("talkNo"))
            r.shot("redet-%d" % len(talked))
            r.check("blechy-redet-am-rand-%d" % len(talked), r.pos() == 0 or r.pos() >= 70, dict(pos=r.pos(), side=r.var("talkSide"), kind=r.bubble()))
    r.check("blechy-redet-von-selbst", len(talked) >= 1, talked)

    ticks = r.ticks()
    r.check("blechy-frame-im-budget", 0 < ticks["frame"] / TICKS_PER_MS < 5.0 and not dev.m.asserts, dict(frame_ms=ticks["frame"] / TICKS_PER_MS))
    r.key(KEY["exit"])
    dev.run(0.6)
    r.check("blechy-exit-schliesst", dev.screen()["number"] == 1 and r.var("isOpen") == 0 and not dev.m.asserts, dict(screen=dev.screen()))
    r.check("blechy-keine-asserts", not dev.m.asserts, dev.m.asserts)

    # closed he draws nothing, and while closed he only counts
    dev.run(0.5)
    r.check("blechy-draussen-keine-frames", r.var("isOpen") == 0, r.var("isOpen"))

    # EXIT held at power-on: he is not there, nothing of the runtime was set up
    held = menu_cases.boot(vsb[0x100:], flash, held=menu_cases.KILL, card=False, seconds=2)
    r.check("blechy-fehlt-mit-exit-beim-einschalten", held.u32(RUNTIME) == 0xffffffff and held.u32(RUNTIME + 96) == 0xffffffff and held.screen()["number"] == 1 and not held.m.asserts,
            dict(head=hex(held.u32(RUNTIME)), armed=hex(held.u32(RUNTIME + 96))))
    return dict(ok=all(c["ok"] for c in r.checks), checks=r.checks,
                ms={k: round(v / TICKS_PER_MS, 4) for k, v in ticks.items() if v},
                frames=r.var("lastSig"), shots=sorted(r.shots),
                cycle={k: {kk: vv for kk, vv in v.items()} for k, v in getattr(r, "cycle", {}).items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--flash", nargs="*", default=[], type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--png-dir", required=True, type=Path)
    args = parser.parse_args()
    args.png_dir.mkdir(parents=True, exist_ok=True)
    flash = load_flash(args.flash) if args.flash else None
    result = run(args.base.read_bytes(), flash, json.loads(args.request.read_text()), args.png_dir)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
