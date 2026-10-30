# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the sample swap (tools/patch/sample_swap.py, docs/messungen/2026-10-26-sample-swap-bau.md).

check.py runs `cases` on every patched copy that carries the swap's hooks. The cases boot the copy with an own
e2sSample.all (sampleset.py, a formula, no Korg data) and own patterns: the live pattern and the bank blocks get their
part samples while the loader starts. Most cases lower the swap's DSP budget (the word at `ss_cap`) in their own copy of
the firmware, so a set larger than the budget is a few hundred kilobytes and loads in seconds of device time; one case
runs with the real budget and a file larger than the DSP's user bank.

    tools/emu/.venv/bin/python tools/emu/swap_cases.py cases --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402

import cardstore  # noqa: E402
import fat32  # noqa: E402
import firmware  # noqa: E402
import sample_swap as spec  # noqa: E402
import sampleset  # noqa: E402
from machine import DSP_DATA, Machine, load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import SWITCH_SCREEN, Dev  # noqa: E402

IMAGE, HEADER = 0xC0000000, 0x100
NAMES, PLAYBACK, META = 0xC047B080, 0xC0362EE8, 0xC036AD88
CURSOR, DSP_MIN = 0xC00F9C80, 0x365EC0
WORK_BUFFER = 0xC0D3A940
PATPTR, BANK = 0xC033E6A4, 0xC08B2940
PLAYER_PTR, PSEL_PTR = 0xC034029C, 0xC03487E8
SET_NUMBER = 0xC0081F50
KEYS = {"rec": 0x00, "stop": 0x01, "play": 0x02, "menu": 0x09, "shift": 0x0A, "right": 0x0C, "exit": 0x0D}
CHAIN_TO, CHAIN_REPEAT = 0x3B00, 0x3B02         # in a pattern block: chain target plus one (u16), repeats (u8)
FRAMES = 40000                                   # 80000 bytes of 16-bit mono
# Title hashes of DATA UTILITY pages as the BLECH theme draws them (the same in both red builds; highram_watch.py --pages).
PAGES = {"export all pattern": "868ce04c3c50", "import all pattern": "dff1e7b7b71d", "import sample": "c08b8629e2ee",
         "export all sample": "2234a72878e5"}
_cards = {}


def has_hooks(payload):
    """True when the giver of the work buffer branches into the swap's code."""
    word = struct.unpack_from("<I", payload, 0xC00369F0 - IMAGE)[0]
    if word >> 24 != 0xEA:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE1 <= 0xC00369F0 + 8 + (off << 2) < spec.CODE1_END


def symbols(payload):
    return spec.build_code(firmware.identify(bytes(payload)).screens)[1]


def with_cap(payload, cap):
    data = bytearray(payload)
    if cap is not None:
        struct.pack_into("<I", data, symbols(payload)["ss_cap"] - IMAGE, cap)
    return bytes(data)


def card(payload, samples, extra=None):
    key = (json.dumps(samples, sort_keys=True), json.dumps(extra or {}, sort_keys=True))
    if key not in _cards:
        image = fat32.format_image(64 * 1024 * 1024)
        volume = fat32.Volume(image)
        volume.write(f"KORG/{cardstore.card_folder(bytes(payload))}/Sample/e2sSample.all",
                     sampleset.build({int(k): tuple(v) for k, v in samples.items()}))
        for path, data in (extra or {}).items():
            volume.write(path, bytes.fromhex(data))
        volume.close()
        _cards[key] = bytes(image)
    return SDCard(MemoryMedium(bytearray(_cards[key])))


def wav_pcm(slot, frames, kind="pcm16"):
    """The 16-bit audio the DSP should hold for a sample of sampleset.wav."""
    wave = sampleset.wav(slot, "x", frames, kind=kind)
    at = wave.index(b"data")
    size = struct.unpack_from("<I", wave, at + 4)[0]
    data = wave[at + 8:at + 8 + size]
    if kind == "pcm24":
        return b"".join(data[i + 1:i + 3] for i in range(0, len(data), 3))
    return data


class Box:
    """A booted copy with our samples and patterns. `live` are the part samples of the pattern in RAM at start,
    `bank` {pattern: part samples} the bank blocks."""

    def __init__(self, payload, flash, samples, live, bank=None, cap=None, held=0, record_dsp=False, extra=None,
                 before_boot=None):
        self.payload = with_cap(payload, cap)
        self.m = Machine(self.payload, flash)
        self.m.insert_card(card(payload, samples, extra))
        self.sym = symbols(payload)
        self.dsp = {}
        self.parses = 0
        if record_dsp:
            original = self.m.write

            def write(address, value):
                x = self.m.dsp_xfer
                if address == DSP_DATA and x and x[0] == 0xAB and x[2] > 0 and DSP_MIN <= x[1] < 0x1C65EC0:
                    self.dsp[x[1]] = value & 0xFFFF
                return original(address, value)
            self.m.write = write
        bank = dict(bank or {})
        bank.setdefault(0, live)

        def patterns(uc, *_):
            live_at = self.u32(PATPTR) + 4
            self.set_parts(live_at, live)
            for n, parts in bank.items():
                self.set_parts(BANK + n * 0x4000, parts)
        self.m.uc.hook_add(unicorn.UC_HOOK_CODE, patterns, begin=0xC00364F0, end=0xC00364F0)
        self.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: setattr(self, "parses", self.parses + 1),
                           begin=spec.FIRMWARE["PARSER"], end=spec.FIRMWARE["PARSER"])
        if before_boot is not None:
            before_boot(self)
        self.dev = Dev(self.payload, flash, held=held, machine=self.m)
        self.dev.run(1.0)

    def u32(self, addr):
        return struct.unpack("<I", bytes(self.m.uc.mem_read(addr, 4)))[0]

    def u16(self, addr):
        return struct.unpack("<H", bytes(self.m.uc.mem_read(addr, 2)))[0]

    def set_parts(self, block, parts):
        for p in range(16):
            self.m.uc.mem_write(block + 0x808 + 0x330 * p, struct.pack("<H", parts[p] if p < len(parts) else 0xFFFF))

    def chain(self, target, repeats):
        """Pattern 0, live and in the bank, chains to `target` after `repeats` rounds; CHAIN MODE on."""
        for block in (self.u32(PATPTR) + 4, BANK):
            self.m.uc.mem_write(block + CHAIN_TO, struct.pack("<HB", target + 1, repeats))
        for glob in (0xC06A2A94, 0xC08A2940):
            if bytes(self.m.uc.mem_read(glob, 4)) == b"GLST":
                self.m.uc.mem_write(glob + 31, bytes([1]))

    def state(self, name):
        return self.u32(spec.STATE + spec.OFF[name])

    def meta_index(self, slot):
        k = self.u16(NAMES + slot * 32 + 30) - 50
        a = self.u16(0xC035738C + k * 32 + 16)
        b = self.u16(0xC035F06C + a * 16 + 8)
        return self.u16(0xC0350644 + b * 8 + 2)

    def resident(self, slot):
        return self.m.uc.mem_read(META + self.meta_index(slot) * 0x45C + 11, 1)[0] == 1

    def residents(self, slots=range(500, 999)):
        return [s for s in slots if self.resident(s)]

    def extent(self, slot):
        i = self.meta_index(slot)
        return self.u32(META + i * 0x45C), self.u32(META + i * 0x45C + 4)

    def cached(self, slot):
        entry = spec.DIR + slot * 16
        return self.u32(entry) != 0 and self.u32(entry + 12) == self.state("GEN")

    def dsp_bytes(self, base, length):
        return b"".join(struct.pack("<H", self.dsp.get(base + i, 0)) for i in range(0, length, 2))

    def running(self):
        return self.u32(self.u32(PLAYER_PTR) + 0x318)

    def key(self, name, wait=0.3):
        self.dev.press(KEYS[name], wait)

    def run(self, seconds):
        self.dev.run(seconds)

    def choose(self, number):
        self.dev.call(SET_NUMBER, self.u32(PSEL_PTR), number, 1)

    def until(self, test, limit, step=0.05):
        end = self.m.time_ns / 1e9 + limit
        while self.m.time_ns / 1e9 < end and not self.m.asserts:
            if test():
                return True
            self.run(step)
        return test()

    def now(self):
        return self.m.time_ns / 1e9

    def watch_switches(self, slots):
        """Every time the running number changes at a sequence end or a chain step: (time, number, all `slots` in the DSP)."""
        seen = []

        def store(uc, *_):
            number = uc.reg_read(self.m.A.UC_ARM_REG_R5 if uc.reg_read(self.m.A.UC_ARM_REG_PC) == 0xC0079ACC else self.m.A.UC_ARM_REG_R0)
            seen.append((round(self.now(), 2), number, all(self.resident(s) for s in slots.get(number, ()))))
        for at in (0xC0079ACC, 0xC0079A74):
            self.m.uc.hook_add(unicorn.UC_HOOK_CODE, store, begin=at, end=at)
        self.m.uc.ctl_flush_tb()
        return seen

    def tap(self, name, wait=0.4, hold=0.1):
        self.m.press(KEYS[name], True)
        self.run(hold)
        self.m.press(KEYS[name], False)
        self.run(wait)

    def text(self):
        fb = self.dev.fb()
        px = lambda x, y: (fb[(y // 8) * 128 + x] >> (y % 8)) & 1
        return ["".join(" ▀▄█"[px(x, y) + 2 * px(x, y + 1)] for x in range(128)).rstrip() for y in range(0, 64, 2)]

    def title(self):
        return hashlib.sha1("\n".join(self.text()[8:12]).encode()).hexdigest()[:12]

    def data_utility(self, name):
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
            if self.m.screen() == 1:
                break
            self.tap("exit", 0.5)

    def no_overlap(self):
        """Active user samples in the DSP: none overlaps another, all lie in the user bank."""
        rows = []
        for i in range(spec.SAMPLE_COUNT):
            at = META + i * 0x45C
            if self.m.uc.mem_read(at + 11, 1)[0] == 1:
                base, length = self.u32(at), self.u32(at + 4)
                if base >= DSP_MIN:
                    rows.append((base, base + length))
        rows.sort()
        return all(a[1] <= b[0] for a, b in zip(rows, rows[1:])), rows


def entry(name, ok, detail):
    return {"id": f"swap:{name}", "ok": bool(ok), "detail": detail}


FILLER = {s: (f"f{s}", 300_000) for s in range(520, 524)}     # samples no pattern uses: the file is larger than a 2 MiB budget


def small(slots, frames=FRAMES):
    return {s: (f"s{s}", frames) for s in slots}


# ------------------------------------------------------------------ start
def case_start(payload, flash):
    out = []
    plain = Box(payload, flash, small(range(500, 504)), [500])
    out.append(entry("off_for_a_file_the_dsp_holds", plain.state("MODE") == 0 and plain.residents() == [500, 501, 502, 503]
                     and not plain.m.asserts, f"Modus {plain.state('MODE')}, im DSP {plain.residents()}: die Firmware lädt wie immer"))
    cap = 0x40000
    box = Box(payload, flash, small(range(500, 510)), [500, 501], cap=cap)
    out.append(entry("start_reads_the_header_and_the_first_pattern",
                     box.state("MODE") == 1 and box.residents() == [500, 501] and box.parses == 2 and not box.m.asserts,
                     f"Modus {box.state('MODE')}, im DSP {box.residents()}, {box.parses} Samples gelesen; zehn in der Datei"))
    held = Box(payload, flash, small(range(500, 510)), [500, 501], cap=cap, held=0x2000)
    held.until(lambda: len(held.residents()) == 10, 15.0, 0.5)
    out.append(entry("exit_at_power_on_keeps_the_firmware_load",
                     held.state("MODE") == 0 and held.residents() == list(range(500, 510)) and not held.m.asserts,
                     f"EXIT gehalten: Modus {held.state('MODE')}, im DSP {held.residents()}"))
    return out


def case_long_set(payload, flash):
    """The real budget and a file over 50 MB: sixteen unused samples of 3 MiB and four small ones."""
    samples = {**small(range(500, 504)), **{s: (f"big{s}", 1_572_864) for s in range(510, 526)}}
    box = Box(payload, flash, samples, [500], bank={1: [501, 502]})
    size = len(sampleset.build({int(k): tuple(v) for k, v in samples.items()}))
    started = box.state("MODE") == 1 and box.residents() == [500]
    box.key("play", 0.2)
    box.choose(1)
    switched = box.until(lambda: box.running() == 1, 12.0)
    after = box.residents()
    return [entry("a_set_larger_than_the_dsp_starts_and_switches",
                  size >= 50_000_000 and started and switched and after[:3] == [500, 501, 502] and not any(s >= 510 for s in after)
                  and not box.m.asserts,
                  f"Datei {size} Byte, Start mit {[500] if started else 'falsch'}, gewechselt {switched}, im DSP {after}")]


# ------------------------------------------------------------------ switching
def case_gate(payload, flash):
    big = 300_000                                # 600000 bytes each: the card needs seconds for the pair
    samples = {**small([500]), 501: ("g501", big), 502: ("g502", big), **FILLER}
    box = Box(payload, flash, samples, [500], bank={1: [501, 502]}, cap=0x200000)
    seen = box.watch_switches({1: (501, 502)})
    box.key("play", 0.2)
    t0 = box.now()
    box.choose(1)
    ends = []
    box.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, *_: ends.append((round(box.now(), 2), uc.reg_read(box.m.A.UC_ARM_REG_R1))),
                      begin=spec.FIRMWARE["SWITCH"], end=spec.FIRMWARE["SWITCH"])
    box.m.uc.ctl_flush_tb()
    switched = box.until(lambda: box.running() == 1, 30.0)
    first = next((s for s in seen if s[1] == 1), None)
    refused = [t for t, number in ends if number == 0 and first and t < first[0]]
    return [entry("a_switch_waits_until_the_samples_are_in",
                  switched and first is not None and first[2] and len(refused) >= 1 and not box.m.asserts,
                  f"gewählt bei {round(t0, 2)} s, Wechsel {first}, Sequenzenden ohne Wechsel {refused[:6]}")]


def case_chain(payload, flash):
    big = 300_000
    samples = {**small([500]), 503: ("c503", big), 504: ("c504", big), **FILLER}
    box = Box(payload, flash, samples, [500], bank={3: [503, 504]}, cap=0x200000)
    seen = box.watch_switches({3: (503, 504)})
    box.chain(3, 1)
    box.key("play", 0.2)
    switched = box.until(lambda: box.running() == 3, 30.0)
    first = next((s for s in seen if s[1] == 3 and s[2]), None)
    refused = [s for s in seen if s[1] == 3 and not s[2]]
    return [entry("the_chain_waits_until_the_samples_are_in",
                  switched and first is not None and len(refused) >= 1 and not box.m.asserts,
                  f"Kette nach 3: Versuche {seen[:6]}, gewechselt {switched}")]


def case_eviction(payload, flash):
    cap = 0x80000
    bank = {0: [500, 501], 1: [502, 503], 2: [504, 505], 3: [506, 507]}
    box = Box(payload, flash, small(range(500, 510)), [500, 501], bank=bank, cap=cap, record_dsp=True)
    box.key("play", 0.2)
    rows = []
    ok = True
    evicted = False
    for n in (1, 2, 3, 0, 1, 2, 3, 0):
        box.choose(n)
        hit = box.until(lambda: box.running() == n, 20.0)
        box.run(0.5)
        live = all(box.resident(s) for s in bank[n])
        pcm = live and all(box.dsp_bytes(*box.extent(s)) == wav_pcm(s, FRAMES) for s in bank[n])
        if n == 3:
            evicted |= not box.resident(500) and not box.resident(501)
        clean, extents = box.no_overlap()
        top = max((e for _, e in extents), default=DSP_MIN)
        rows.append(dict(pattern=n, switched=hit, live=live, pcm_equal=pcm, resident=box.residents(), top=hex(top)))
        ok = ok and hit and live and pcm and clean and top <= DSP_MIN + cap
    return [entry("the_dsp_holds_only_the_active_set", ok and evicted and not box.m.asserts, rows)]


def case_part_change(payload, flash):
    box = Box(payload, flash, small(range(500, 506)), [500], cap=0x40000)
    part = box.dev.call(spec.FIRMWARE["PART"], 0)
    before = box.resident(505)
    box.set_parts(box.u32(PATPTR) + 4, [505])
    box.m.uc.mem_write(box.u32(part + 8) + 8, struct.pack("<H", 505))
    box.dev.call(0xC0099FFC, part)
    held = box.u16(part + 0x34) == 500 and box.m.uc.mem_read(part + 0x39, 1)[0] != 0xFF
    loaded = box.until(lambda: box.resident(505), 5.0)
    published = box.u16(part + 0x34) == 505 and box.m.uc.mem_read(part + 0x39, 1)[0] != 0xFF
    return [entry("a_part_waits_for_pcm_before_publishing_its_new_sample",
                  not before and held and loaded and published and not box.m.asserts,
                  f"vorher geladen {before}, alter Part gehalten {held}, danach geladen {loaded}, Part veröffentlicht {published}")]


def case_osc_choice(payload, flash):
    samples = small([500, 501, 503, 504, 505])
    box = Box(payload, flash, samples, [500], cap=0x40000, record_dsp=True)
    part = box.dev.call(spec.FIRMWARE['PART'], 0)
    record = box.u32(part + 8)
    selections, premature = [], []

    def desired(uc, access, at, size, value, _):
        target = value & 0xFFFF
        selections.append(dict(target=target, actual=box.u16(part + 0x34), loaded=box.resident(target)))

    def actual(uc, access, at, size, value, _):
        target = value & 0xFFFF
        if target in (501, 503) and not box.resident(target):
            premature.append(target)

    hooks = [box.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, desired, begin=record + 8, end=record + 9),
             box.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, actual, begin=part + 0x34, end=part + 0x35)]
    rows = []
    try:
        for target, delta in ((501, 1), (503, 1), (501, -1)):
            previous = box.u16(part + 0x34)
            start = len(selections)
            box.m.send([1, 1, 0, delta & 255, 0])
            settled = box.until(lambda: box.u16(record + 8) == target and box.u16(part + 0x34) == target,
                                3.0)
            trace = selections[start:]
            accepted = any(item['target'] == target and item['actual'] == previous for item in trace)
            pcm = settled and box.dsp_bytes(*box.extent(target)) == wav_pcm(target, FRAMES)
            name = bytes(box.m.uc.mem_read(NAMES + target * 32 + 12, 16)).split(b'\0', 1)[0]
            rows.append(dict(target=target, delta=delta, selected=accepted, settled=settled,
                             pcm_equal=pcm, name_equal=name == samples[target][0].encode()))
    finally:
        for hook in hooks:
            box.m.uc.hook_del(hook)
    volume = fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        unchanged = volume.read(f'KORG/{cardstore.card_folder(payload)}/Sample/e2sSample.all') == sampleset.build(samples)
    finally:
        volume.close()
    return [entry('osc_selects_indexed_unloaded_samples_and_skips_empty_slots',
                  all(row['selected'] and row['settled'] and row['pcm_equal'] and row['name_equal'] for row in rows)
                  and unchanged and not box.m.asserts, dict(steps=rows, library_unchanged=unchanged)),
            entry('osc_keeps_the_previous_part_until_pcm_is_ready',
                  not premature and any(row['settled'] for row in rows) and not box.m.asserts,
                  dict(premature=premature, selections=selections))]


def case_voice_residency(payload, flash):
    from sample_residency_probe import probe
    result = probe(payload, check_eviction=True)
    return [entry("old_native_voices_pin_their_import_until_cpu_cleanup", result["ok"], result)]


def case_alias_eviction(payload, flash):
    box = Box(payload, flash, {500: ("first", 1000), 501: ("second", 1000)}, [500, 501],
              cap=4096, record_dsp=True)
    number = bytes(box.m.uc.mem_read(NAMES + 500 * 32 + 30, 2))
    box.m.uc.mem_write(NAMES + 602 * 32 + 30, number)
    box.set_parts(box.u32(PATPTR) + 4, [602])
    box.set_parts(BANK, [602])
    for index in (0, 1):
        part = box.dev.call(spec.FIRMWARE["PART"], index)
        box.m.uc.mem_write(box.u32(part + 8) + 8, struct.pack("<H", 602))
        box.dev.call(spec.FIRMWARE["PART_UPDATE"], part)
    box.m.uc.mem_write(spec.STATE + spec.PROT, struct.pack("<32H", 602, *([0xFFFF] * 31)))
    before = box.dsp_bytes(*box.extent(500))
    wrapper = 0xC1000000
    box.m.uc.mem_write(wrapper, spec.arm.assemble(f"""
        push {{r11, lr}}
        ldr r11, ={spec.STATE}
        bl {box.sym['place']}
        pop {{r11, pc}}
        .pool
    """, origin=wrapper).bytes)
    chosen = box.dev.call(wrapper, 1000)
    kept = box.resident(500) and box.resident(602) and box.dsp_bytes(*box.extent(500)) == before
    other_removed = not box.resident(501)
    refused = box.dev.call(wrapper, 3000)
    protected = box.resident(500) and box.resident(602) and box.dsp_bytes(*box.extent(500)) == before
    return [entry("a_live_alias_protects_its_physical_dsp_sample",
                  chosen != 0 and kept and other_removed and not box.m.asserts,
                  dict(address=hex(chosen), alias_kept=kept, unused_slot_removed=other_removed)),
            entry("a_protected_physical_sample_is_not_evicted_to_make_room",
                  refused == 0 and protected and not box.m.asserts,
                  dict(address=hex(refused), alias_kept=protected))]


# ------------------------------------------------------------------ cache
def case_cache(payload, flash):
    out = []
    box = Box(payload, flash, small(range(500, 506)), [500], bank={1: [502], 2: [503]}, cap=0x40000, record_dsp=True)
    box.key("play", 0.2)
    filled = box.until(lambda: box.cached(502), 8.0)
    box.choose(1)
    switched = box.until(lambda: box.running() == 1, 10.0)
    base, length = box.extent(502)
    pcm_ok = box.dsp_bytes(base, length) == wav_pcm(502, FRAMES)
    out.append(entry("neighbours_are_read_ahead_and_copied_from_ram",
                     filled and switched and box.state("STAT_SRC") == 1 and pcm_ok and not box.m.asserts,
                     f"im Cache {filled}, gewechselt {switched}, Quelle des letzten Ladens {box.state('STAT_SRC')} (1 = RAM), PCM gleich {pcm_ok}"))
    gen = box.state("GEN")
    box.dev.call(SWITCH_SCREEN, 14, 0)
    box.run(0.5)
    dropped = box.state("GEN") != gen and box.state("SESSION") == 0 and not box.cached(502)
    box.to_main()
    box.run(3.0)
    no_refill = box.state("CFILL") == 0
    box.key("stop", 0.3)
    box.key("play", 0.3)
    refilled = box.until(lambda: box.state("CFILL") == 1, 8.0)
    out.append(entry("another_screen_drops_the_cache_until_the_next_play",
                     dropped and no_refill and refilled and not box.m.asserts,
                     f"verworfen {dropped}, ohne PLAY nicht neu gefüllt {no_refill}, nach STOP und PLAY gefüllt {refilled}"))
    return out


def case_checksum(payload, flash):
    box = Box(payload, flash, small(range(500, 506)), [500], bank={1: [502]}, cap=0x40000, record_dsp=True)
    box.key("play", 0.2)
    filled = box.until(lambda: box.cached(502), 8.0)
    entry_at = box.u32(spec.DIR + 502 * 16)
    box.m.uc.mem_write(entry_at + 0x4A0 + 0x100, b"\x5a\xa5\x5a\xa5")
    gen = box.state("GEN")
    box.choose(1)
    switched = box.until(lambda: box.running() == 1, 15.0)
    base, length = box.extent(502)
    pcm_ok = box.dsp_bytes(base, length) == wav_pcm(502, FRAMES)
    return [entry("a_foreign_write_in_the_cache_is_never_used",
                  filled and switched and box.state("GEN") != gen and box.state("STAT_SRC") == 0 and pcm_ok and not box.m.asserts,
                  f"im Cache {filled}, gewechselt {switched}, Cache verworfen {box.state('GEN') != gen}, "
                  f"Quelle {box.state('STAT_SRC')} (0 = Karte), PCM gleich {pcm_ok}")]


def case_equal(payload, flash):
    """A sample the swap loads gets the same tables and the same PCM as the firmware's own loader gives it."""
    samples = {500: ("e500", 9000), 501: ("e501", 7001, 48000, "pcm24"), 502: ("e502", 5000, 44100, "stereo16"), 503: ("e503", 3333)}
    plain = Box(payload, flash, samples, [500], record_dsp=True)
    box = Box(payload, flash, samples, [500], cap=0x10000, record_dsp=True)
    box.set_parts(box.u32(PATPTR) + 4, [500, 501, 502, 503])
    loaded = box.until(lambda: all(box.resident(s) for s in (501, 502, 503)), 8.0)
    rows, ok = [], loaded and plain.state("MODE") == 0 and box.state("MODE") == 1
    for s in (501, 502, 503):
        pi, bi = plain.meta_index(s), box.meta_index(s)
        pm = bytearray(plain.m.uc.mem_read(META + pi * 0x45C, 0x45C))
        bm = bytearray(box.m.uc.mem_read(META + bi * 0x45C, 0x45C))
        pp = bytearray(plain.m.uc.mem_read(PLAYBACK + pi * 16, 16))
        bp = bytearray(box.m.uc.mem_read(PLAYBACK + bi * 16, 16))
        pcm_plain = plain.dsp_bytes(*plain.extent(s))
        pcm_box = box.dsp_bytes(*box.extent(s))
        for t in (pm, bm, pp, bp):
            t[0:4] = b"\0\0\0\0"
        kind = samples[s][3] if len(samples[s]) > 3 else 'pcm16'
        expected = wav_pcm(s, samples[s][1], kind)
        same = (pm == bm and pp == bp and pcm_plain == pcm_box == expected
                and pm[9] == int(kind == 'stereo16')
                and plain.m.uc.mem_read(NAMES + s * 32, 32) == box.m.uc.mem_read(NAMES + s * 32, 32))
        rows.append(dict(slot=s, same=same, pcm=len(pcm_box)))
        ok = ok and same
    return [entry("the_swap_loads_like_the_firmware", ok and not box.m.asserts and not plain.m.asserts, rows)]


# ------------------------------------------------------------------ the cache's owner
EXPORT_PATTERNS = [("menu", 1), ("menu", 30), ("menu", 1)]
FLOWS = [
    # (name, page, steps, a flow that makes the file it needs) as highram_watch.py measured them with Hacktribe 2.02
    ("import sample", "import sample", [("menu", 1), ("turn1", 1), ("menu", 6), ("menu", 30), ("menu", 1)], None),
    ("export all sample", "export all sample", [("menu", 1), ("menu", 1), ("menu", 60), ("menu", 1)], None),
    ("export all pattern", "export all pattern", EXPORT_PATTERNS, None),
    ("import all pattern", "import all pattern", [("menu", 1), ("menu", 1), ("turn1", 1), ("menu", 1), ("turn2", 1), ("menu", 30), ("menu", 1)],
     ("export all pattern", EXPORT_PATTERNS)),
    ("sampling and resampling", None, None, None),
]


def plain_wav(frames):
    data = sampleset.pcm(frames, 3)
    return (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


WRITERS = ("import sample", "export all sample", "import all pattern")   # flows that measurably write the work buffer


def steps_on(box, page, steps):
    found = box.data_utility(page)
    for k, wait in steps:
        if k.startswith("turn"):
            box.dev.turn(int(k[4:]), wait)
        else:
            box.tap(k, wait)
    box.to_main()
    return found


def perform_flow(box, page, steps):
    if page:
        return steps_on(box, page, steps)
    box.m.press(KEYS["shift"], True)
    box.run(0.1)
    box.tap("rec", 0.2)
    box.m.press(KEYS["shift"], False)
    box.run(1.0)
    for _ in range(3):
        box.tap("right", 0.5)
    box.tap("rec", 2.0)
    box.tap("rec", 2.0)
    box.run(5.0)
    box.tap("stop", 1.0)
    box.tap("exit", 1.0)
    return True


def flow_task(payload, flash, index, *, box_type=Box):
    name, page, steps, before = FLOWS[index]
    box = box_type(payload, flash, small(range(500, 506)), [500], bank={1: [501, 502], 249: [503]}, cap=0x40000,
              extra={"/imp.wav": plain_wav(20000).hex()} if name == "import sample" else None)
    if before:
        steps_on(box, *before)
    box.key("play", 0.2)
    filled = box.until(lambda: box.state("CFILL") == 1 and box.cached(501), 10.0)
    box.key("stop", 0.5)
    gen = box.state("GEN")
    ours = [(lo, hi) for lo, hi, _ in spec.AREAS]
    writes = []

    def write(uc, access, addr, size, value, _):
        pc = uc.reg_read(box.m.A.UC_ARM_REG_PC)
        if not any(lo <= pc < hi for lo, hi in ours):
            writes.append((hex(pc), hex(addr), box.state("GEN") != gen))
    handles = [box.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write, begin=lo, end=hi - 1)
               for lo, hi in ((WORK_BUFFER, spec.ARENA_L_END), (spec.ARENA_U, spec.ARENA_U_END))]
    box.m.uc.ctl_flush_tb()
    found = perform_flow(box, page, steps)
    for h in handles:
        box.m.uc.hook_del(h)
    box.to_main()
    early = [w for w in writes if not w[2]]
    return [entry(f"{name.replace(' ', '_')}_drops_the_cache_before_writing",
                  filled and found and box.state("GEN") != gen and not early and not box.m.asserts
                  and (writes or name not in WRITERS),
                  f"Cache gefüllt {filled}, Seite gefunden {found}, verworfen {box.state('GEN') != gen}, "
                  f"fremde Schreibzugriffe im Arbeitspuffer {len(writes)}, davon vor dem Verwerfen {early[:3]}")]


def case_flows(payload, flash):
    return [e for i in range(len(FLOWS)) for e in flow_task(payload, flash, i)]


def case_failure_gates(payload, flash):
    box = Box(payload, flash, small(range(500, 506)), [500], bank={1: [501], 2: [502]}, cap=0x20000)
    box.key("play", 0.2)
    box.choose(1)
    box.run(6.0)
    failed = bool(box.u32(spec.STATE + spec.FAILED + 4 * (501 >> 5)) & (1 << (501 & 31)))
    out = [entry("a_temporarily_full_dsp_keeps_the_running_pattern",
                 not failed and box.state("MODE") == 1 and box.state("REQ") == 1 and box.running() == 0 and box.resident(500) and not box.resident(501) and not box.m.asserts,
                 f"Platz gescheitert {failed}, laufendes Pattern {box.running()}, Ziel geladen {box.resident(501)}")]
    box.m.uc.mem_write(spec.STATE + spec.OFF["TSTATE"], struct.pack("<I", 1))
    box.choose(2)
    box.run(6.0)
    out.append(entry("a_latched_transport_fault_keeps_the_running_pattern",
                     box.state("MODE") == 2 and box.running() == 0 and box.state("REQ") == 2
                     and not box.resident(502) and not box.m.asserts,
                     f"Modus {box.state('MODE')}, laufendes Pattern {box.running()}, angefordert {box.state('REQ')}"))
    return out


def case_full_session(payload, flash, *, box_type=Box):
    box = box_type(payload, flash, small(range(500, 506)), [500], bank={1: [501, 502], 249: [503]}, cap=0x40000,
              extra={"/imp.wav": plain_wav(20000).hex()})
    ours = [(lo, hi) for lo, hi, _ in spec.AREAS]
    state = dict(generation=None, writes=0, cache_writes=0, early=[])

    def write(uc, access, addr, size, value, _):
        pc = uc.reg_read(box.m.A.UC_ARM_REG_PC)
        if not any(lo <= pc < hi for lo, hi in ours):
            state["writes"] += 1
            if spec.ARENA_L <= addr < spec.ARENA_L_END or spec.ARENA_U <= addr < spec.ARENA_U_END:
                state["cache_writes"] += 1
            if box.state("GEN") == state["generation"] and len(state["early"]) < 3:
                state["early"].append((hex(pc), hex(addr)))

    handles = [box.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write, begin=lo, end=hi - 1)
               for lo, hi in ((WORK_BUFFER, spec.ARENA_L_END), (spec.ARENA_U, spec.ARENA_U_END))]
    box.m.uc.ctl_flush_tb()
    rows = []
    try:
        for index in (4, 2, 3, 0, 1):
            name, page, steps, _ = FLOWS[index]
            box.to_main()
            box.key("stop", 0.3)
            box.key("play", 0.2)
            filled = box.until(lambda: box.cached(503), 10.0)
            box.key("stop", 0.5)
            gen = box.state("GEN")
            state["generation"] = gen if filled else None
            before = state["writes"]
            before_cache = state["cache_writes"]
            if index == 0:
                # IMPORT ALL PATTERN leaves the browser two folders below the card root, on Upper Folder.
                steps = [("menu", 1), ("menu", 1), *steps]
            found = perform_flow(box, page, steps)
            box.to_main()
            rows.append(dict(mode=name, filled=filled, found=found, dropped=box.state("GEN") != gen,
                             writes=state["writes"] - before, cache_writes=state["cache_writes"] - before_cache))
            if index == 1:
                volume = fat32.Volume(bytes(box.m.mmc.card.medium.data))
                exported = volume.read(f"KORG/{cardstore.card_folder(payload)}/Sample/e2sSample.all")
                volume.close()
                rows[-1]["source_bytes_after_export"] = len(exported)
                rows[-1]["source_slots_after_export"] = (sum(offset != 0 for offset in struct.unpack_from("<1000I", exported, 16))
                                                         if len(exported) >= 4096 else None)
    finally:
        for handle in handles:
            box.m.uc.hook_del(handle)
    ok = all(r["filled"] and r["found"] and r["dropped"] and (r["writes"] or r["mode"] not in WRITERS)
             and r.get("source_slots_after_export", 0) is not None for r in rows)
    return [entry("one_session_drops_each_cache_before_foreign_writes",
                  ok and not state["early"] and not box.m.asserts,
                  dict(modes=rows, writes=state["writes"], early=state["early"]))]


def case_prefetch_targets(payload, flash):
    box = Box(payload, flash, small(range(500, 507)), [500],
              bank={1: [500, 501], 249: [500, 502], 3: [500, 503], 2: [500, 504]},
              cap=0x40000, record_dsp=True)
    box.chain(3, 255)
    box.key("play", 0.2)
    filled = box.until(lambda: box.resident(503) and box.cached(501) and box.cached(502), 10.0)
    outside = not box.cached(504) and not box.resident(504)
    box.choose(1)
    box.choose(2)
    switched = box.until(lambda: box.running() == 2, 15.0)
    intact = box.dsp_bytes(*box.extent(500)) == wav_pcm(500, FRAMES)
    target = box.dsp_bytes(*box.extent(504)) == wav_pcm(504, FRAMES)
    clean, _ = box.no_overlap()
    return [entry("both_neighbours_and_the_chain_target_survive_a_new_choice",
                  filled and outside and switched and intact and target and clean and not box.m.asserts,
                  dict(prefetched=filled, distant_not_prefetched=outside, switched=switched,
                       shared_pcm_intact=intact, target_pcm_equal=target, no_overlap=clean))]


def case_store(payload, flash):
    at = spec.STORE_CODE - IMAGE
    if payload[at:at + 4] == b"\xff" * 4:
        return []
    import sample_persistence_cases
    import sample_store_cases
    checks = sample_persistence_cases.cases(payload) + sample_store_cases.cases(payload)
    return [entry("store:" + c["id"], c["ok"], {k: v for k, v in c.items() if k not in ("id", "ok")})
            for c in checks]


def case_file_owner(payload, flash):
    import reader_lifecycle_cases
    return [entry(f'file_owner:{i}', row['ok'], row) for i, row in enumerate(reader_lifecycle_cases.cases(payload))]


def case_integrity(payload, flash):
    import swap_integrity_cases
    return [entry(row['id'], row['ok'], row) for row in swap_integrity_cases.cases(payload, flash)]


def case_native_dsp(payload, flash):
    import native_dsp_scope_cases
    return [entry(row['id'], row['ok'], row) for row in native_dsp_scope_cases.runtime_cases(payload, flash)]


def case_native_sample_faults(payload, flash):
    import capture_fault_cases
    import sample_export_fault_cases
    rows = [('capture', failure, capture_fault_cases.case(payload, failure))
            for failure in ('none', 'preexisting', 'stop', 'end')]
    rows += [('export', failure, sample_export_fault_cases.case(payload, failure))
             for failure in ('none', 'preexisting', 'read')]
    return [entry(f'native_{kind}_{failure}', row['ok'], row) for kind, failure, row in rows]


GROUPS = (case_start, case_long_set, case_gate, case_chain, case_eviction, case_part_change, case_cache, case_checksum,
          case_equal, *[(lambda i: lambda payload, flash: flow_task(payload, flash, i))(i) for i in range(len(FLOWS))],
          case_failure_gates, case_full_session, case_prefetch_targets, case_alias_eviction, case_voice_residency, case_store,
          case_file_owner, case_integrity, case_native_dsp, case_native_sample_faults, case_osc_choice)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=["cases"])
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--group", type=int, action="append")
    a = p.parse_args()
    payload = a.patched.read_bytes()[HEADER:]
    flash = load_flash(a.flash) if a.flash else None
    groups = a.group if a.group else range(len(GROUPS))
    result = [e for i in groups for e in group_entries(payload, flash, i)]
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if all(e["ok"] for e in result) else 1


if __name__ == "__main__":
    sys.exit(main())
