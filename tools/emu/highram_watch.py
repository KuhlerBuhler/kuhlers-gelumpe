# SPDX-License-Identifier: GPL-2.0-only
"""Who writes and reads the RAM above the sample info cache, by program counter and phase.

The device measurement of 2026-10-22 (docs/messungen/2026-10-22-ram-frei.md) found that during normal play only
one 4 KiB block above 0xC1010000 changes. This probe boots a copy in the emulator, hooks every write and read of the
work buffer and of the RAM above the interrupt stack up to the end of the emulator's 128 MiB window, and attributes
each access to its program counter, CPU mode and the phase the script is in: boot with the sample load, play,
pattern switch, DATA UTILITY import and export, power off. The two stacks below the free RAM are hooked only in
short windows (every interrupt writes there) and otherwise compared block by block at each phase change. Everything
on the card is made here (sampleset.py), no Korg data. docs/messungen/2026-10-24-ram-task-stack.md has the measurement.

    tools/emu/.venv/bin/python tools/emu/highram_watch.py --vsb SYSTEM.VSB [--flash dump.bin] [--report out.json]
        [--samples 40] [--poison]

`--poison` fills the work buffer and everything above the interrupt stack with a pattern once the start is over;
the firmware must then behave the same (same export file, no assert) if it keeps nothing there between uses.
"""

import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

import unicorn

sys.path.insert(0, str(Path(__file__).parent))
import fat32  # noqa: E402
import sampleset  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import SWITCH_SCREEN, Dev  # noqa: E402

HEADER = 0x100
# The parts of the RAM above the sample info cache (docs/speicherbereiche.md, "Zusammenhängende Belegung").
REGIONS = [
    ("work buffer", 0xC0D3A940, 0xC273AA40),
    ("start stack (64 KiB below the reset SP)", 0xC273AA40, 0xC274AA40),
    ("interrupt and idle stack", 0xC274AA40, 0xC274EA3C),
    ("above the interrupt stack, real RAM", 0xC274EA3C, 0xC4000000),
    ("64 MiB alias (emulator maps it as RAM)", 0xC4000000, 0xC8000000),
]
WATCH = (REGIONS[0][1], REGIONS[-1][2])
READ_WATCH = [(REGIONS[0][1], REGIONS[0][2]), (REGIONS[3][1], REGIONS[4][2])]   # the stacks are read all the time, the rest should not be
POISON = 0xA5C3E10F
STACKS = (0xC273A000, 0xC274F000)   # the start stack and the interrupt stack, in whole 4 KiB blocks
CANARY = 0x5A5AA5A5                  # the device measurement used the same: word = address ^ 0x5A5AA5A5
IRQ_FILL_LITERAL = 0xC0029888        # literal of the boot loop that fills the interrupt stack (Hacktribe 2.02)
GIVER = 0xC00369F0       # returns the work buffer, 0xC0D3A940, and its size (docs/messungen/2026-10-08-systemspeicher-offline.md)
KEYS = {"stop": 0x01, "play": 0x02, "tap": 0x03, "left": 0x08, "menu": 0x09, "right": 0x0C, "exit": 0x0D}
POWER_KEY = [6, 1, 0, 0, 0]
# Title hashes of DATA UTILITY pages of Hacktribe 2.02 (measured with --pages; Probe.title). Another build draws other titles.
PAGES = {"export pattern": "f2355885be3d", "export all pattern": "e8c1c56e667d", "import all pattern": "65e955bfa6f4",
         "export all sample": "250d48b7aa1b", "import sample": "7befc1679a33", "software update": "c64ccc5f80bd"}
MODES = {0x10: "usr", 0x11: "fiq", 0x12: "irq", 0x13: "svc", 0x17: "abt", 0x1B: "und", 0x1F: "sys"}


def region(addr):
    for i, (_, lo, hi) in enumerate(REGIONS):
        if lo <= addr < hi:
            return i
    return None


class HighWatch:
    """Counts every access into WATCH: per phase and (kind, region, pc) the count, the address range, the modes and SPs."""

    def __init__(self, machine):
        self.m = machine
        self.A = machine.A
        self.phase = "boot"
        self.rows = collections.OrderedDict()      # phase -> {(kind, region, pc): [count, lo, hi, modes, sp_lo, sp_hi, lr]}
        self.low = {}                               # region -> lowest address written, over the whole run
        self.low_boot = {}
        self.blocks = collections.OrderedDict()     # phase -> 4 KiB blocks of the two stacks that changed in it
        self.marks = collections.OrderedDict()      # phase -> lowest changed word of each stack at the end of the phase
        uc = machine.uc
        # A hook on every stack write makes the run some ten times slower, so the stacks are hooked only while
        # sample_stacks() is on, and otherwise compared block by block at each phase change.
        for lo, hi in ((WATCH[0], REGIONS[0][2]), (REGIONS[3][1], WATCH[1])):
            uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, self._access, begin=lo, end=hi - 1, user_data="w")
        for lo, hi in READ_WATCH:
            uc.hook_add(unicorn.UC_HOOK_MEM_READ, self._access, begin=lo, end=hi - 1, user_data="r")
        self.stack_hook = None
        self.givers = collections.OrderedDict()     # phase -> Counter of return addresses of calls to the work buffer giver
        uc.hook_add(unicorn.UC_HOOK_CODE, self._giver, begin=GIVER, end=GIVER)
        uc.ctl_flush_tb()
        # Our own canary in the start stack before the first instruction: the firmware does not fill that one.
        lo, hi = REGIONS[1][1], REGIONS[1][2]
        uc.mem_write(lo, b"".join(struct.pack("<I", (a ^ CANARY) & 0xFFFFFFFF) for a in range(lo, hi, 4)))
        self.stacks = self._stack_bytes()

    def _stack_bytes(self):
        return bytes(self.m.uc.mem_read(STACKS[0], STACKS[1] - STACKS[0]))

    def sample_stacks(self, on):
        uc = self.m.uc
        if on and self.stack_hook is None:
            self.stack_hook = uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, self._access, begin=REGIONS[1][1], end=REGIONS[2][2] - 1, user_data="w")
        elif not on and self.stack_hook is not None:
            uc.hook_del(self.stack_hook)
            self.stack_hook = None
        uc.ctl_flush_tb()

    def stack_marks(self):
        """Lowest word of the start stack that is no longer our canary, and of the interrupt stack that is no longer
        the firmware's fill word (read from the image: the literal the boot fill loop at 0xC00296D8 stores)."""
        data = self._stack_bytes()
        fill = struct.unpack("<I", bytes(self.m.uc.mem_read(IRQ_FILL_LITERAL, 4)))[0]
        out = {}
        lo, hi = REGIONS[1][1], REGIONS[1][2]
        for a in range(lo, hi, 4):
            if struct.unpack_from("<I", data, a - STACKS[0])[0] != (a ^ CANARY) & 0xFFFFFFFF:
                out["start stack lowest changed"] = hex(a)
                break
        lo, hi = REGIONS[2][1], REGIONS[2][2]
        for a in range(lo, hi, 4):
            if struct.unpack_from("<I", data, a - STACKS[0])[0] != fill:
                out["interrupt stack lowest not fill"] = hex(a)
                break
        out["interrupt stack fill word"] = hex(fill)
        return out

    def _giver(self, uc, addr, size, _):
        self.givers.setdefault(self.phase, collections.Counter())[uc.reg_read(self.A.UC_ARM_REG_LR)] += 1

    def set_phase(self, name):
        now = self._stack_bytes()
        changed = sorted({(STACKS[0] + i) & ~0xFFF for i in range(0, len(now), 4) if now[i:i + 4] != self.stacks[i:i + 4]})
        self.blocks[self.phase] = [hex(b) for b in changed]
        self.marks[self.phase] = self.stack_marks()
        self.stacks = now
        self.phase = name

    def _access(self, uc, access, addr, size, value, kind):
        r = region(addr)
        if r is None:
            return
        A = self.A
        pc = uc.reg_read(A.UC_ARM_REG_PC)
        sp = uc.reg_read(A.UC_ARM_REG_SP)
        mode = uc.reg_read(A.UC_ARM_REG_CPSR) & 0x1F
        table = self.rows.setdefault(self.phase, {})
        key = (kind, r, pc)
        row = table.get(key)
        if row is None:
            table[key] = [1, addr, addr + size, {mode}, sp, sp, uc.reg_read(A.UC_ARM_REG_LR)]
        else:
            row[0] += 1
            if addr < row[1]:
                row[1] = addr
            if addr + size > row[2]:
                row[2] = addr + size
            row[3].add(mode)
            if sp < row[4]:
                row[4] = sp
            if sp > row[5]:
                row[5] = sp
        if kind == "w":
            if addr < self.low.get(r, 1 << 33):
                self.low[r] = addr
            if self.phase.startswith("boot") and addr < self.low_boot.get(r, 1 << 33):
                self.low_boot[r] = addr

    def report(self):
        out = []
        for phase, table in self.rows.items():
            rows = []
            for (kind, r, pc), (n, lo, hi, modes, sp_lo, sp_hi, lr) in sorted(table.items(), key=lambda x: (x[0][1], x[0][0], -x[1][0])):
                rows.append(dict(kind=kind, region=REGIONS[r][0], pc=hex(pc), lr=hex(lr), count=n, start=hex(lo), end=hex(hi),
                                 modes=sorted(MODES.get(m, hex(m)) for m in modes), sp=[hex(sp_lo), hex(sp_hi)]))
            out.append(dict(phase=phase, accesses=rows))
        givers = {ph: {hex(lr - 4): n for lr, n in c.items()} for ph, c in self.givers.items()}
        return dict(phases=out, giver_calls=givers, stack_blocks_changed=self.blocks, stack_marks=self.marks, lowest_write={REGIONS[r][0]: hex(a) for r, a in sorted(self.low.items())},
                    lowest_write_boot={REGIONS[r][0]: hex(a) for r, a in sorted(self.low_boot.items())})


def folder(payload):
    if b"KORG/blechtribe/\0" in payload:
        return "blechtribe"
    return "electribe sampler" if b"KORG/electribe sampler/\0" in payload else "hacktribe"


def plain_wav(frames, rate=48000):
    data = sampleset.pcm(frames, 3)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


class Probe:
    def __init__(self, payload, flash, samples, wav_frames):
        self.payload = payload
        self.dev = Dev(payload, flash)
        self.m = self.dev.m
        self.root = folder(payload)
        img = fat32.format_image(128 * 1024 * 1024)
        vol = fat32.Volume(img)
        if samples:
            vol.write(f"KORG/{self.root}/Sample/e2sSample.all", sampleset.build(sampleset.sized(samples, samples * 20000)))
        vol.write("/imp.wav", plain_wav(wav_frames))
        vol.close()
        self.m.insert_card(SDCard(MemoryMedium(img)))
        self.watch = HighWatch(self.m)
        self.log = []

    def run(self, s):
        self.dev.run(s)

    def tap(self, key, wait=0.4, hold=0.1):
        self.m.press(KEYS[key], True)
        self.run(hold)
        self.m.press(KEYS[key], False)
        self.run(wait)

    def text(self):
        fb = self.dev.fb()
        px = lambda x, y: (fb[(y // 8) * 128 + x] >> (y % 8)) & 1
        return ["".join(" ▀▄█"[px(x, y) + 2 * px(x, y + 1)] for x in range(128)).rstrip() for y in range(0, 64, 2)]

    def until(self, test, limit_s, step=0.5):
        end = self.m.time_ns / 1e9 + limit_s
        while self.m.time_ns / 1e9 < end and not self.m.asserts and self.m.powered:
            if test():
                return True
            self.run(step)
        return test()

    def phase(self, name):
        self.watch.set_phase(name)
        self.log.append(dict(phase=name, device_s=round(self.m.time_ns / 1e9, 2), screen=self.m.screen(), asserts=len(self.m.asserts)))
        print(json.dumps(self.log[-1]), file=sys.stderr, flush=True)

    def read_card(self, path):
        vol = fat32.Volume(bytes(self.m.mmc.card.medium.data))
        try:
            return vol.read(path)
        except Exception:
            return None
        finally:
            vol.close()

    def slots(self):
        """Samples the firmware shows as in use: +11 of each record of the sample table is 1 (docs/speicherbereiche.md)."""
        meta = bytes(self.m.uc.mem_read(0xC036AD88, 1000 * 0x45C))
        return sum(1 for i in range(1000) if meta[i * 0x45C + 11] == 1)

    def poison(self):
        word = struct.pack("<I", POISON)
        for lo, hi in ((REGIONS[0][1], REGIONS[0][2]), (REGIONS[3][1], REGIONS[4][2])):
            lo = (lo + 3) & ~3
            chunk = 0x100000
            for a in range(lo, hi, chunk):
                n = min(chunk, hi - a) // 4
                self.m.uc.mem_write(a, word * n)

    def title(self):
        """Short hash of the title rows of a DATA UTILITY page, to find a page without counting (the firmware remembers the last one)."""
        return hashlib.sha1("\n".join(self.text()[8:12]).encode()).hexdigest()[:12]

    def data_utility(self, name):
        """DATA UTILITY, the page `name` of PAGES, found by its title; False when it did not come up."""
        self.dev.call(SWITCH_SCREEN, 14, 0)
        self.run(0.4)
        self.tap("menu")
        for _ in range(14):
            if self.title() == PAGES[name]:
                return True
            self.tap("right", 0.25)
        return False

    def to_main(self):
        for _ in range(8):
            self.tap("exit", 0.5)
            if self.m.screen() == 1:
                break


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vsb", required=True)
    ap.add_argument("--flash")
    ap.add_argument("--report")
    ap.add_argument("--samples", type=int, default=40, help="samples in e2sSample.all on the card, 20,000 frames each")
    ap.add_argument("--wav-frames", type=int, default=50_000, help="length of the WAV for IMPORT SAMPLE")
    ap.add_argument("--poison", action="store_true")
    ap.add_argument("--pages", action="store_true", help="only print the title hash and title rows of every DATA UTILITY page")
    ap.add_argument("--skip", default="", help="comma list of phases to leave out: play,switch,pattern,import,export,poweroff")
    a = ap.parse_args()
    raw = Path(a.vsb).read_bytes()
    payload = raw[HEADER:]
    flash = load_flash([a.flash]) if a.flash else None
    skip = set(filter(None, a.skip.split(",")))
    p = Probe(payload, flash, a.samples, a.wav_frames)
    shots = {}

    p.phase("boot")
    p.until(lambda: p.m.screen() == 1, 120, 0.5)
    p.phase("boot: main screen up, wait until the sample count settles")
    last = [-1]

    def settled():                      # the loader marks a slot in use (+11) as it goes; done when the count stops moving
        n = p.slots()
        done = n == last[0]
        last[0] = n
        return done and n >= a.samples
    p.until(settled, 60 + a.samples, 2.0)
    shots["slots_after_boot"] = p.slots()
    p.run(2.0)
    if a.pages:
        p.watch.set_phase("pages")
        p.dev.call(SWITCH_SCREEN, 14, 0)
        p.run(0.4)
        p.tap("menu")
        for _ in range(12):
            print("PAGE", p.title(), *p.text()[8:12], sep="\n")
            p.tap("right", 0.25)
        return
    if a.poison:
        p.poison()
    p.phase("idle on main screen (stack writes hooked)")
    p.watch.sample_stacks(True)
    p.run(2.0)
    p.watch.sample_stacks(False)
    p.phase("idle on main screen")
    p.run(2.0)
    if "play" not in skip:
        p.phase("play pattern and pads (stack writes hooked)")
        p.watch.sample_stacks(True)
        p.tap("play", 0.3)
        for i in range(16):
            if i == 4:
                p.watch.sample_stacks(False)
                p.phase("play pattern and pads")
            p.m.send([4, i % 16, 0, 100, 1])
            p.run(0.12)
            p.m.send([4, i % 16, 0, 0, 0])
            p.run(0.38)
        p.phase("menus")
        p.tap("menu", 0.4)
        for _ in range(6):
            p.tap("right", 0.3)
        p.tap("exit", 0.4)
        p.tap("exit", 0.4)
    if "switch" not in skip:
        p.phase("pattern switch while playing")
        p.dev.turn(1, 0.5)
        p.run(6.0)
        p.tap("stop", 0.5)
        p.phase("pattern switch while stopped")
        for _ in range(3):
            p.dev.turn(1, 0.6)
        p.run(1.0)
    flows = [
        # (phase, page, steps, skip key); steps are (key or "turnN", seconds to wait after it), measured with Hacktribe 2.02
        # IMPORT SAMPLE first: the file browser keeps the folder it was left in, and the WAV is on the card root
        ("import sample", "import sample", [("menu", 1), ("turn1", 1), ("menu", 6), ("menu", 30), ("menu", 1)], "import"),
        ("export all sample", "export all sample", [("menu", 1), ("menu", 1), ("menu", 60), ("menu", 1)], "export"),
        ("export all pattern", "export all pattern", [("menu", 1), ("menu", 30), ("menu", 1)], "pattern"),
        ("import all pattern", "import all pattern",
         [("menu", 1), ("menu", 1), ("turn1", 1), ("menu", 1), ("turn2", 1), ("menu", 30), ("menu", 1)], "pattern"),
    ]
    for phase, page, steps, key in flows:
        if key in skip:
            continue
        p.to_main()
        p.phase(phase)
        found = p.data_utility(page)
        trail = []
        for k, wait in steps:
            if k.startswith("turn"):
                p.dev.turn(int(k[4:]), wait)
            else:
                p.tap(k, wait)
            trail.append(p.m.screen())
        shots[phase] = dict(page_found=found, screens=trail, last=p.text())
        p.to_main()
    p.phase("after DATA UTILITY: play and switch again")
    p.tap("play", 0.3)
    p.run(5.0)
    p.tap("stop", 0.5)
    for _ in range(2):
        p.dev.turn(1, 0.6)
    p.run(1.0)
    if "poweroff" not in skip:
        p.phase("power off (key)")
        p.m.send(POWER_KEY)
        p.until(lambda: not p.m.powered, 5.0, 0.005)
    files = {}
    for path in (f"/KORG/{p.root}/Sample/e2sSample.all", f"/KORG/{p.root}/electribe_sampler_allpattern.e2sallpat"):
        data = p.read_card(path)
        files[path] = dict(size=len(data), sha=hashlib.sha256(data).hexdigest()[:16]) if data is not None else None
    out = dict(vsb=a.vsb, sha256=hashlib.sha256(raw).hexdigest(), poison=a.poison, samples=a.samples, log=p.log,
               asserts=[str(x) for x in p.m.asserts[:5]], powered=p.m.powered, slots_end=p.slots(), files=files,
               patterns_sha=hashlib.sha256(bytes(p.m.uc.mem_read(0xC08B2940, 250 * 0x4000))).hexdigest()[:16],
               watch=(p.phase("end"), p.watch.report())[1], shots=shots)
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if a.report:
        Path(a.report).write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
