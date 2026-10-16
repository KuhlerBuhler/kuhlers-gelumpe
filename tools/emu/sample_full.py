# SPDX-License-Identifier: GPL-2.0-only
"""Does the firmware write into BLECH's RAM when the sample memory is full?

Boots a patched copy with a made-up e2sSample.all that fills the user slots 501 to 999 up to the sampler's
sample memory, with a write watch on every BLECH range (ramwatch.py), then runs a plugin, a pattern, the
firmware's menus and the DATA UTILITY import. Everything is synthetic: the audio is a formula
(sampleset.py), no Korg data. docs/messungen/2026-10-14-sample-speicher-voll.md has the measurement.

    tools/emu/.venv/bin/python tools/emu/sample_full.py --base SYSTEM.VSB --patched BLECH.VSB [--flash dump.bin] \
        --scenario regression|full|snake|over|import|export|map [--report out.json] [--request request.json | < request.json]

`request.json` is what test/emulator-sample-full.test.mjs builds: `include` (the assembler include of the
script contract), `programs` (the plugin blocks) and `displays` (what the browser model draws).
"""

import argparse
import collections
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.patch import script_hooks  # noqa: E402
import fat32  # noqa: E402
import ramwatch  # noqa: E402
import sampleset  # noqa: E402
from machine import DSP_DATA, load_flash  # noqa: E402
from script_cases import CARD_FILE, archive  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import SWITCH_SCREEN, Dev  # noqa: E402

HEADER = 0x100
SAMPLE_FILE = "/KORG/blechtribe/Sample/e2sSample.all"
LIMIT = 0x01C65EC0            # end of the DSP sample memory (docs/hintergrund/virtuelle-sd.md, "Kapazität")
FACTORY_END = 0x365EC0        # where the first user sample goes: the DSP cursor after a start without samples
CAPACITY = LIMIT - FACTORY_END   # 26,214,400 bytes = 25 MiB of audio for the user slots
CURSOR = 0xC00F9C80           # where the next sample goes in the DSP memory (docs/speicherbereiche.md)
NAMES, PLAYBACK, META = 0xC047B080, 0xC0362EE8, 0xC036AD88
CARD_BYTES = 128 * 1024 * 1024
LOAD_RATE = 190_000           # bytes of e2sSample.all the firmware loads per second of device time (measured: 18.8 MB in 97 s)
KEYS = {"rec": 0x00, "stop": 0x01, "play": 0x02, "tap": 0x03, "left": 0x08, "menu": 0x09, "shift": 0x0A,
        "right": 0x0C, "exit": 0x0D, "write": 0x0E}

# The big parts of the RAM the firmware sets up (docs/speicherbereiche.md, "Zusammenhängende Belegung").
KNOWN = [
    ("image: code, constants, BLECH free block", 0xC0000000, 0xC0200000),
    ("task stacks, kernel data, heap (boot clears it)", 0xC0200000, 0xC08A2940),
    ("globals", 0xC08A2940, 0xC08B2940),
    ("250 pattern slots", 0xC08B2940, 0xC0C9A940),
    ("sample info cache", 0xC0C9A940, 0xC0D3A940),
    ("file and sample work buffer", 0xC0D3A940, 0xC273AA40),
    ("start stack", 0xC273AA40, 0xC274AA40),
    ("interrupt and idle stack", 0xC274AA40, 0xC274EA3C),
]


def card(files, size=CARD_BYTES):
    img = fat32.format_image(size)
    volume = fat32.Volume(img)
    for path, data in files.items():
        volume.write(path, data)
    volume.close()
    return img


def plain_wav(frames, rate=48000):
    """A WAV file as IMPORT SAMPLE takes it: fmt and data only."""
    data = sampleset.pcm(frames, 3)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


class Session:
    """One boot of the patched copy with the card made from `files`, the watch on and the DSP writes logged."""

    def __init__(self, base, patched, flash, request, files, plugin="klicker", watch=True, held=0):
        self.request = request
        self.built = script_hooks.build(request["include"])
        self.layout = self.built.layout
        self.runtime = self.layout["runtime"]
        self.programs = request["programs"]
        self.displays = {k: bytes.fromhex(v) for k, v in request.get("displays", {}).items()}
        self.checks = []
        self.phases = []
        files = dict(files)
        if plugin:
            files[CARD_FILE] = archive([bytes.fromhex(self.programs[plugin]["blob"])])
        self.dev = Dev(patched[HEADER:], flash, held)
        self.m = self.dev.m
        self.m.insert_card(SDCard(MemoryMedium(card(files))))
        self.dsp_log, self.dsp_words = [], collections.Counter()
        words = [(a, b) for a, b in ramwatch.diff_runs(base, patched) if b <= ramwatch.FREE_BASE]
        self.watch = ramwatch.Watch(self.m, ramwatch.areas(self.layout), words) if watch else None
        ramwatch.dsp_transfers(self.m, self.dsp_log)
        original = self.m.write

        def write(a, v):
            if a == DSP_DATA:
                self.dsp_words["data"] += 1
            return original(a, v)
        self.m.write = write
        self.payload = patched[HEADER:]

    # ---- driving ----------------------------------------------------------------------------
    def check(self, name, ok, detail=None):
        self.checks.append(dict(id=name, ok=bool(ok), detail=detail))
        print("check", name, bool(ok), file=sys.stderr, flush=True)

    def word(self, name):
        return self.dev.u32(self.runtime + self.built.symbols["SCRIPT_CONTROL_" + name])

    def armed(self):
        """The loader has read the plugin file and armed the runtime (Blechy, built into BLECH, arms it earlier, before the card is read)."""
        return self.word("ARMED") == 1 and self.word("CARD_STATUS") == 1

    def until(self, test, limit_s, step=0.5):
        end = self.m.time_ns / 1e9 + limit_s
        while not test() and self.m.time_ns / 1e9 < end and not self.m.asserts:
            self.dev.run(step)
        return test()

    def load(self, limit_s, ready=False):
        """Run until the plugin loader has armed the runtime, which comes right after the samples. With `ready` until the
        plugin got its ready event, looked at every 10 ms of device time so that a plugin with a model sees the frames from there."""
        t0 = self.m.time_ns / 1e9
        if ready:
            ok = self.until(lambda: self.word("READY") == 1, limit_s, 0.01)
        else:
            ok = self.until(self.armed, limit_s)
        return dict(done=ok, seconds=round(self.m.time_ns / 1e9 - t0, 2))

    def tap(self, key, wait=0.4, hold=0.1):
        code = KEYS[key] if isinstance(key, str) else key
        self.m.press(code, True)
        self.dev.run(hold)
        self.m.press(code, False)
        self.dev.run(wait)

    def phase(self, name):
        w = self.watch
        self.phases.append(dict(phase=name, device_s=round(self.m.time_ns / 1e9, 2), writes=w.total if w else None,
                                foreign=sum(v for (k, _), v in w.counts.items() if k == "foreign") if w else None,
                                foreign_io=sum(v for (k, _), v in w.counts.items() if k == "foreign io") if w else None))
        print(json.dumps(self.phases[-1]), file=sys.stderr, flush=True)

    def screen_text(self, rows=range(0, 64, 2)):
        """The display as half-block characters, for the report."""
        fb = self.dev.fb()
        px = lambda x, y: (fb[(y // 8) * 128 + x] >> (y % 8)) & 1
        return ["".join(" ▀▄█"[px(x, y) + 2 * px(x, y + 1)] for x in range(128)).rstrip() for y in rows]

    # ---- what the firmware says about the samples ---------------------------------------------
    def slots(self):
        """Zero-based slots the firmware shows as in use, and the DSP allocation cursor."""
        active = [i for i in range(1000) if self.dev.read(META + i * 0x45C + 11, 1)[0] == 1]
        return dict(active=len(active), first=active[0] if active else None, last=active[-1] if active else None,
                    cursor=self.dev.u32(CURSOR))

    def names(self, count=40):
        return self.dev.read(NAMES, count * 0x20)

    def dsp_summary(self):
        data = [x for x in self.dsp_log if x[1] < LIMIT]
        top = max((x[1] + 2 * x[3] for x in data), default=0)
        return dict(sample_writes=len(data), bytes=sum(2 * x[3] for x in data), first_offset=min((x[1] for x in data), default=None),
                    high_water=top, port_words=self.dsp_words["data"],
                    sources=sorted({hex(x[2]) for x in data})[:6], callers=sorted({hex(x[4]) for x in data}))

    # ---- invariants ------------------------------------------------------------------------------
    def static_ranges(self):
        """What must be the file's bytes in RAM: the code areas, tables and every word the patches changed."""
        keep = {"splash editor code", "splash editor vtable copy", "power-off picture code and frame", "MFX 2 code", "runtime code (VM, hooks, card, menu)",
                "menu screen table and class copy", "Blechy's block (read only, the app built into BLECH)"}
        out = [(lo, hi) for name, lo, hi in ramwatch.areas(self.layout) if name in keep]
        return out + (list(self.watch.words) if self.watch else [])

    def invariants(self):
        """The BLECH image as it stands in RAM against the patched file: no byte of our code or of a word we changed moved."""
        mem = bytes(self.m.uc.mem_read(0xC0000000, 0x200000))
        ranges = self.static_ranges()
        bad = [(hex(a), hex(b)) for a, b in ranges if mem[a - 0xC0000000:b - 0xC0000000] != self.payload[a - 0xC0000000:b - 0xC0000000]]
        return dict(static_ranges=len(ranges), static_bytes=sum(b - a for a, b in ranges), changed=bad,
                    asserts=self.m.asserts, screen=self.dev.screen()["number"])

    def conclude(self):
        report = dict(checks=self.checks, phases=self.phases, slots=self.slots(), dsp=self.dsp_summary(),
                      invariants=self.invariants(), device_s=round(self.m.time_ns / 1e9, 1))
        if self.watch:
            report["watch"] = self.watch.report()
        report["ok"] = all(c["ok"] for c in self.checks)
        return report


# ---- sets of samples ------------------------------------------------------------------------------
def fill(total_bytes, count=499, first=sampleset.FIRST_USER):
    """`count` samples from slot 501 that together hold `total_bytes` bytes of audio."""
    return sampleset.sized(count, total_bytes // 2, first)


def boot_full(base, patched, flash, request, plugin, total, extra=None, watch=True):
    files = {SAMPLE_FILE: sampleset.build(fill(total))}
    files.update(extra or {})
    s = Session(base, patched, flash, request, files, plugin, watch)
    limit = (total + 499 * sampleset.FIXED) / LOAD_RATE * 1.5 + 30
    loaded = s.load(limit, ready=plugin == "snake")
    s.phase("boot with samples")
    return s, loaded


def boot_plain(base, patched, flash, request, total, extra=None):
    """Like boot_full, but BLECH's runtime is not armed (no plugin file), so the firmware's own screens show unobstructed;
    the start is over when the main screen is up."""
    files = {SAMPLE_FILE: sampleset.build(fill(total))}
    files.update(extra or {})
    s = Session(base, patched, flash, request, files, None, True)
    t0 = s.m.time_ns / 1e9
    ok = s.until(lambda: s.dev.screen()["number"] == 1, (total + 499 * sampleset.FIXED) / LOAD_RATE * 1.5 + 30, 0.5)
    s.dev.run(2.0)
    s.phase("boot with samples, no plugin")
    return s, dict(done=ok, seconds=round(s.m.time_ns / 1e9 - t0, 2))


def load_checks(s, loaded, total, slots_expected=499):
    slots = s.slots()
    s.check("laden-fertig", loaded["done"] and not s.m.asserts, loaded)
    s.check("alle-slots-belegt", slots["active"] == slots_expected and slots["first"] == 500, slots)
    s.check("dsp-zeiger-am-limit", slots["cursor"] == FACTORY_END + total, dict(cursor=hex(slots["cursor"]), want=hex(FACTORY_END + total)))
    dsp = s.dsp_summary()
    s.check("samples-gehen-ueber-den-dsp-port", dsp["bytes"] == total and dsp["high_water"] <= LIMIT, dsp)


def open_klicker(s):
    """The Klicker is an app under TOOLS: opened the way a user does, from the BLECH menu with ENTER."""
    import menu_cases
    from script_cases import open_app
    open_app(s.dev, menu_cases.GROUP_TOOLS)


def plugin_checks(s):
    """Klicker, an app, as the browser model draws it once it is open, before and after a tap, and the firmware's own menu still works."""
    shows = lambda name: s.dev.fb() == s.displays[name]
    s.dev.run(1.0)
    open_klicker(s)
    s.check("klicker-bereit", shows("klickerReady") and s.armed(), dict(screen=s.dev.screen()))
    before = len(s.m.panel_log)
    s.m.send([0, 3, 1, 0, 0])
    s.dev.run(0.12)
    s.m.send([0, 3, 0, 0, 0])
    s.dev.run(0.12)
    one = shows("klickerOne")
    # the firmware blinks the TAP LED to the tempo, so the LED's value a moment later is not the plugin's: the packet is
    led = [m for m in s.m.panel_log[before:] if m == bytes([0, 20, 255, 0, 0])]
    s.check("klicker-tap", one and len(led) >= 1, dict(display=one, led_packets=len(led), screen=s.dev.screen()))
    s.tap("exit", 0.5)
    s.tap("menu", 0.3)
    s.check("firmware-menue-bedienbar", s.dev.screen()["number"] != 1 and not s.m.asserts, dict(screen=s.dev.screen()))
    s.tap("exit", 0.3)
    open_klicker(s)
    s.check("zurueck-auf-dem-hauptbildschirm", s.dev.screen()["number"] == 1 and shows("klickerOne"), dict(screen=s.dev.screen()))
    s.tap("exit", 0.5)
    s.phase("plugin klicker")


def snake_checks(s):
    """Snake for 150 frames with the same inputs the browser model got; the display must be the model's."""
    import unicorn
    import menu_cases
    from script_cases import open_app
    frames = lambda: s.word("FRAMES")
    s.until(lambda: s.word("READY") == 1, 30, 0.002)
    opened = []
    at_open = s.built.symbols["script_app_open"]
    s.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, size, d: opened.append(frames()), begin=at_open, end=at_open)
    s.m.uc.ctl_flush_tb()
    open_app(s.dev, menu_cases.GROUP_GAMES)
    first = opened[0] + 1       # the frame that handles open and runs the first frame: the browser model's frame 0
    schedule = {first - 1 + at: key for at, key in {20: 15, 60: 11, 100: 15, 130: 11}.items()}
    sent = set()
    end = s.m.time_ns + 30e9
    while frames() < first + 149 and s.m.time_ns < end and not s.m.asserts:
        s.dev.run(0.002)
        now = frames()
        if now in schedule and now not in sent:
            sent.add(now)
            s.m.send([0, schedule[now], 1, 0, 0])
            s.m.send([0, schedule[now], 0, 0, 0])
    s.dev.run(0.006)
    drawn = s.dev.read(0xC031B310, 1024)
    s.check("snake-150-rahmen", frames() == first + 149 and drawn == s.displays["snake150"] and not s.m.asserts,
            dict(frames=frames() - first, equal=drawn == s.displays["snake150"]))
    s.phase("plugin snake")


def play_pattern(s, seconds=8.0):
    """Play the pattern the flash holds with pads struck on and off; the sequencer and the voice task run."""
    s.m.press(KEYS["play"], True)
    s.dev.run(0.1)
    s.m.press(KEYS["play"], False)
    t = 0.0
    pad = 0
    while t < seconds:
        s.m.send([4, pad % 16, 0, 100, 1])
        s.dev.run(0.12)
        s.m.send([4, pad % 16, 0, 0, 0])
        s.dev.run(0.38)
        pad += 1
        t += 0.5
    s.m.send([2, 3, 1, 244, 0])
    s.dev.run(0.5)
    playing = s.dev.u32(0xC06BC318)
    s.tap("stop", 0.5)
    s.check("pattern-spielt-und-stoppt", playing == 1 and s.dev.u32(0xC06BC318) == 0 and not s.m.asserts, dict(transport=playing))
    s.phase("pattern play")


def import_sample(s, entry_turns, wait=6.0):
    """DATA UTILITY, IMPORT SAMPLE: the file browser on the card root, the entry `entry_turns` below KORG, destination as offered."""
    s.dev.call(SWITCH_SCREEN, 14, 0)         # the DATA UTILITY page, whatever was open before
    s.dev.run(0.4)
    s.tap("menu")
    for _ in range(8):
        s.tap("right", 0.25)
    s.tap("menu", 1.0)
    s.dev.turn(entry_turns, 0.5)
    s.tap("menu", 0.5)
    working = s.dev.fb()
    s.until(lambda: s.dev.fb() != working, 180.0, 0.5)      # the file is read first, slowly for a big one; then the destination is asked
    s.dev.run(1.0)
    before = s.screen_text()
    start = s.slots()["cursor"]
    s.tap("menu", 1.0)
    # the importer is slow with the DSP stand-in (rough 100 KB in a minute of device time): wait for the cursor to move or an error window
    s.until(lambda: s.slots()["cursor"] != start or s.dev.screen()["window"] != 0, wait, 1.0)
    s.dev.run(3.0)
    after = s.screen_text()
    for _ in range(8):          # an error window stays until a key; leave to the main screen
        s.tap("exit", 0.5)
        screen = s.dev.screen()
        if screen["number"] == 1 and not screen["window"]:
            break
    return before, after


# ---- scenarios ----------------------------------------------------------------------------------------
def scenario_full(base, patched, flash, request, plugin="klicker", total=CAPACITY):
    s, loaded = boot_full(base, patched, flash, request, plugin, total)
    load_checks(s, loaded, total)
    if plugin == "klicker":
        plugin_checks(s)
    else:
        snake_checks(s)
    play_pattern(s)
    s.tap("menu", 0.3)
    s.tap("exit", 0.3)
    s.check("keine-fremden-schreibzugriffe", s.watch.report()["foreign_count"] == 0, s.watch.report()["foreign"][:5])
    s.check("blech-bytes-unveraendert", not s.invariants()["changed"], s.invariants()["changed"])
    return s


def scenario_over(base, patched, flash, request, extra_bytes=100_000):
    """More audio than the memory holds: the loader has to stop somewhere, and BLECH must not care."""
    total = CAPACITY + extra_bytes
    s, loaded = boot_full(base, patched, flash, request, "klicker", total)
    s.check("laden-fertig", loaded["done"] and not s.m.asserts, loaded)
    slots = s.slots()
    s.check("dsp-zeiger-nicht-ueber-limit", slots["cursor"] <= LIMIT, dict(cursor=hex(slots["cursor"]), limit=hex(LIMIT)))
    # 499 samples of 52,5xx bytes and 100,000 bytes too many: the loader stops at the first one that does not fit
    s.check("laden-stoppt-beim-ersten-der-nicht-passt", slots["active"] == 497 and slots["last"] == 996 and LIMIT - slots["cursor"] < 52_000, slots)
    s.dev.run(5.0)
    window = s.dev.screen()["window"]
    s.check("memory-full-fenster-bleibt-offen", window != 0, dict(window=hex(window)))
    s.tap("tap", 0.5)
    s.check("fenster-schluckt-tap", s.dev.screen()["window"] == window, s.dev.screen())
    for _ in range(6):          # the error window goes with MENU or EXIT
        s.tap("exit", 0.5)
        if not s.dev.screen()["window"]:
            break
    s.check("fenster-geschlossen", s.dev.screen()["window"] == 0 and s.dev.screen()["number"] == 1, s.dev.screen())
    # the plugin saw the TAP the window swallowed: the Klicker counts one
    open_klicker(s)
    s.check("plugin-sah-den-tap-trotz-fenster", s.dev.fb() == s.displays["klickerOne"], None)
    s.tap("tap", 0.3)
    s.check("plugin-laeuft-weiter", s.dev.fb() != s.displays["klickerOne"] and not s.m.asserts, None)
    s.tap("exit", 0.5)
    s.tap("menu", 0.3)
    s.check("firmware-menue-bedienbar", s.dev.screen()["number"] != 1 and not s.m.asserts, s.dev.screen())
    s.tap("exit", 0.3)
    s.phase("plugin klicker")
    s.check("keine-fremden-schreibzugriffe", s.watch.report()["foreign_count"] == 0, s.watch.report()["foreign"][:5])
    s.check("blech-bytes-unveraendert", not s.invariants()["changed"], s.invariants()["changed"])
    return s


def scenario_import(base, patched, flash, request, left=200_000):
    """Memory filled to `left` bytes short of the limit, then IMPORT SAMPLE: too big (Memory Full), fits, too big again,
    exact fit, and one more once the memory is full to the last byte."""
    total = CAPACITY - left
    sizes = [("imp1_big", left * 3 // 2), ("imp2_a", left // 2), ("imp3_c", left * 3 // 5), ("imp4_b", left // 2), ("imp5_d", 2000)]
    extra = {"/%s.wav" % name: plain_wav(size // 2) for name, size in sizes}
    s, loaded = boot_full(base, patched, flash, request, "klicker", total, extra)
    load_checks(s, loaded, total)
    plugin_checks(s)
    shots, cursors = {}, [s.slots()["cursor"]]
    expect = [False, True, False, True, False]           # which of the five files may go in, as the memory fills
    for n, (name, size) in enumerate(sizes):
        shots[name + "_before"], shots[name + "_after"] = import_sample(s, n + 1, wait=240.0)
        cursors.append(s.slots()["cursor"])
        s.check("import-" + name, cursors[-1] == cursors[-2] + (size if expect[n] else 0) and not s.m.asserts,
                dict(size=size, cursor=hex(cursors[-1]), before=hex(cursors[-2]), screen=s.dev.screen()))
        s.phase("import " + name)
    s.check("speicher-am-ende-voll", cursors[-1] == LIMIT, dict(cursor=hex(cursors[-1])))
    s.check("keine-fremden-schreibzugriffe", s.watch.report()["foreign_count"] == 0, s.watch.report()["foreign"][:5])
    s.check("blech-bytes-unveraendert", not s.invariants()["changed"], s.invariants()["changed"])
    s.shots = shots
    return s


def scenario_window(base, patched, flash, request, left=0):
    """What the firmware shows after the start with the memory `left` bytes short of full (negative: more audio than fits),
    without any plugin: a window, or not."""
    total = CAPACITY - left
    s = Session(base, patched, flash, request, {SAMPLE_FILE: sampleset.build(fill(total))}, None, watch=False)
    s.until(lambda: s.dev.screen()["number"] == 1, (total + 499 * sampleset.FIXED) / LOAD_RATE * 1.5 + 30, 0.5)
    shots = {}
    for n in range(4):
        s.dev.run(1.0)
        screen = s.dev.screen()
        win = screen["window"]
        shots["t%d" % n] = dict(screen=screen, window_vtable=hex(s.dev.u32(win)) if win else None,
                                window_words=[hex(s.dev.u32(win + 4 * i)) for i in range(12)] if win else None, text=s.screen_text())
    s.tap("tap", 0.5)
    screen = s.dev.screen()
    shots["after_tap"] = dict(screen=screen, text=s.screen_text())
    s.shots = shots
    s.check("hauptbildschirm", s.dev.screen()["number"] == 1 and not s.m.asserts, s.dev.screen())
    return s


def scenario_sampling(base, patched, flash, request, total=CAPACITY):
    """SAMPLING (SHIFT + REC) with the memory full: the firmware answers Error, Memory Full. With room left (total smaller)
    the window opens and recording waits for audio the DSP stand-in never sends."""
    s, loaded = boot_plain(base, patched, flash, request, total)
    load_checks(s, loaded, total)
    shots = {}
    s.m.press(KEYS["shift"], True)
    s.dev.run(0.1)
    s.tap("rec", 0.2)
    s.m.press(KEYS["shift"], False)
    s.dev.run(1.0)
    shots["opened"] = s.screen_text()
    for n in range(3):
        s.tap("right", 0.5)
        shots["option%d" % n] = s.screen_text()
    s.tap("rec", 2.0)
    shots["rec1"] = s.screen_text()
    s.tap("rec", 2.0)
    shots["rec2"] = s.screen_text()
    s.dev.run(10.0)
    shots["after10s"] = s.screen_text()
    s.tap("stop", 1.0)
    s.tap("exit", 1.0)
    shots["end"] = s.screen_text()
    s.check("sampling-ohne-assert", not s.m.asserts, s.m.asserts)
    s.check("keine-neuen-slots", s.slots()["active"] == 499 and s.slots()["cursor"] == FACTORY_END + total, s.slots())
    s.check("keine-fremden-schreibzugriffe", s.watch.report()["foreign_count"] == 0, s.watch.report()["foreign"][:5])
    s.check("blech-bytes-unveraendert", not s.invariants()["changed"], s.invariants()["changed"])
    s.shots = shots
    s.phase("sampling")
    return s


def scenario_export(base, patched, flash, request):
    """EXPORT ALL SAMPLE with the memory full: the DSP read path stages the whole memory through the work buffer."""
    s, loaded = boot_plain(base, patched, flash, request, CAPACITY)
    load_checks(s, loaded, CAPACITY)
    s.dev.call(SWITCH_SCREEN, 14, 0)
    s.dev.run(0.4)
    s.tap("menu")
    for _ in range(10):
        s.tap("right", 0.25)
    s.tap("menu", 1.0)
    s.tap("menu", 1.0)
    s.until(lambda: False, 240.0, 1.0)          # a fixed 240 s of device time, the export is ~45 s
    volume = fat32.Volume(bytes(s.m.mmc.card.medium.data))
    try:
        data = volume.read("/KORG/blechtribe/Sample/e2sSample.all")
    finally:
        volume.close()
    table = [v for v in struct.unpack_from("<%dI" % sampleset.SLOTS, data, 16) if v]
    riffs = [at for at in table if data[at:at + 4] == b"RIFF"]
    audio = sum(struct.unpack_from("<I", data, at + 40)[0] for at in riffs)
    mine = len(sampleset.build(fill(CAPACITY)))
    s.check("export-datei-vollstaendig", len(riffs) == 499 == len(table) and audio == CAPACITY,
            dict(size=len(data), input_size=mine, entries=len(table), riff=len(riffs), audio_bytes=audio))
    s.check("keine-fremden-schreibzugriffe", s.watch.report()["foreign_count"] == 0, s.watch.report()["foreign"][:5])
    s.check("blech-bytes-unveraendert", not s.invariants()["changed"], s.invariants()["changed"])
    s.phase("export all sample")
    return s


def scenario_map(base, patched, flash, request):
    """Which pages of the RAM hold something after a start without samples and after a start with a full memory."""
    empty = Session(base, patched, flash, request, {}, "klicker", watch=False)
    empty.load(30)
    empty.dev.run(1.0)
    empty_pages = ramwatch.non_zero_pages(empty.m)
    empty_names = empty.names()
    s, loaded = boot_full(base, patched, flash, request, "klicker", CAPACITY, watch=True)
    load_checks(s, loaded, CAPACITY)
    play_pattern(s, 4.0)
    full_pages = ramwatch.non_zero_pages(s.m)
    s.check("namen-der-niedrigen-slots-unveraendert", s.names() == empty_names, None)
    rows = []
    for name, lo, hi in KNOWN[1:]:
        span = range(lo // ramwatch.PAGE, hi // ramwatch.PAGE)
        e = sum(1 for p in span if p in empty_pages)
        f = sum(1 for p in span if p in full_pages)
        hi_page = max((p for p in span if p in full_pages), default=None)
        rows.append(dict(area=name, start=hex(lo), end=hex(hi), pages=len(span), nonzero_empty=e, nonzero_full=f,
                         highest_nonzero=hex((hi_page + 1) * ramwatch.PAGE) if hi_page is not None else None))
    known = {p for _, lo, hi in KNOWN for p in range(lo // ramwatch.PAGE, hi // ramwatch.PAGE)}
    outside = [(hex(a), hex(b)) for a, b in ramwatch.page_runs(p for p in full_pages if p not in known)]
    outside_empty = [(hex(a), hex(b)) for a, b in ramwatch.page_runs(p for p in empty_pages if p not in known)]
    new = [(hex(a), hex(b)) for a, b in ramwatch.page_runs(full_pages - empty_pages, gap=16)]
    s.check("keine-fremden-schreibzugriffe", s.watch.report()["foreign_count"] == 0, None)
    s.map = dict(areas=rows, outside_known_full=outside, outside_known_empty=outside_empty, new_runs=new[:60], new_runs_total=len(new))
    return s


SCENARIOS = dict(
    regression=lambda *a, **k: scenario_full(*a, plugin="klicker", **k),
    full=lambda *a, **k: scenario_full(*a, plugin="klicker", **k),
    snake=lambda *a, **k: scenario_full(*a, plugin="snake", **k),
    over=scenario_over,
    **{"import": scenario_import},
    sampling=scenario_sampling,
    sampling_free=lambda *a, **k: scenario_sampling(*a, total=2_000_000, **k),
    window=scenario_window,
    window_over=lambda *a, **k: scenario_window(*a, left=-100_000, **k),
    export=scenario_export,
    map=scenario_map,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--patched", required=True, type=Path)
    parser.add_argument("--flash", nargs="*", default=[], type=Path)
    parser.add_argument("--scenario", default="regression", choices=sorted(SCENARIOS))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--request", type=Path, help="the request as a file instead of standard input")
    parser.add_argument("--total", type=lambda x: int(x, 0), help="bytes of audio instead of the whole memory (full, snake, regression), to try the script")
    args = parser.parse_args()
    request = json.loads(args.request.read_text()) if args.request else json.load(sys.stdin)
    flash = load_flash(args.flash) if args.flash else None
    extra = {"total": args.total} if args.total else {}
    session = SCENARIOS[args.scenario](args.base.read_bytes(), args.patched.read_bytes(), flash, request, **extra)
    report = session.conclude()
    report["scenario"] = args.scenario
    for extra in ("shots", "map"):
        if hasattr(session, extra):
            report[extra] = getattr(session, extra)
    text = json.dumps(report, indent=1, default=str, ensure_ascii=False)
    if args.report:
        args.report.write_text(text)
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
