# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the sample error patch (tools/patch/sample_errors.py, docs/messungen/2026-10-15-sample-fehler.md).

check.py runs `cases` on every patched copy that carries the patch's hooks. The loader of e2sSample.all skips a sample
it cannot take (a format it does not know, a slot that is in use) and goes on, and the window afterwards names the first
one it skipped and why. Everything is made here: the samples are a formula (sampleset.py), no Korg data. The cases that
need a factory bank run on the empty flash of the emulator, which carries one of our own (factorybank.py).

    tools/emu/.venv/bin/python tools/emu/sample_error_cases.py cases --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import sample_errors as spec  # noqa: E402
import sampleset  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
HEADER = 0x100
META = 0xC036AD88               # the sample table: 0x45C bytes per sample, +11 is 1 for a sample in use (docs/speicherbereiche.md)
FRAMES = 2000
_cards = {}


def has_hooks(payload):
    """True when the loader's first instruction branches into the patch's code."""
    word = struct.unpack_from("<I", payload, spec.LOADER - IMAGE)[0]
    if word >> 24 != 0xEA:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= spec.LOADER + 8 + (off << 2) < spec.CODE_END


def folder(payload):
    """The folder the firmware of this copy reads e2sSample.all from (the BLECH set renames it)."""
    if b"KORG/blechtribe/\0" in payload:
        return "blechtribe/Sample"
    return "electribe sampler/Sample" if b"KORG/electribe sampler/\0" in payload else "hacktribe/Sample"


def card_with(payload, samples):
    key = (folder(payload), json.dumps(samples, sort_keys=True))
    if key not in _cards:
        image = fat32.format_image(64 * 1024 * 1024)
        volume = fat32.Volume(image)
        volume.write(f"KORG/{folder(payload)}/e2sSample.all", sampleset.build({int(k): tuple(v) for k, v in samples.items()}))
        volume.close()
        _cards[key] = bytes(image)
    return SDCard(MemoryMedium(bytearray(_cards[key])))


class Boot:
    """One start of the copy with a card that holds an e2sSample.all of the samples given, run until the load is over."""

    def __init__(self, payload, flash, samples, held=0, seconds=10, slow_card=None):
        samples = {str(k): list(v) for k, v in samples.items()}
        self.dev = Dev(payload, flash, held)
        self.dev.m.insert_card(card_with(payload, samples))
        self.dev.m.mmc.slow_card = slow_card
        self.dev.run(seconds)

    def active(self):
        """The user slots (zero based, 500 and up) the firmware shows as in use."""
        return [i for i in range(sampleset.FIRST_USER, 1000) if self.dev.read(META + i * 0x45C + 11, 1)[0] == 1]

    def active_all(self):
        return [i for i in range(1000) if self.dev.read(META + i * 0x45C + 11, 1)[0] == 1]

    def window(self):
        return self.dev.screen()["window"] != 0

    def word(self, offset):
        return self.dev.u32(spec.STATE + offset)

    def line(self, offset):
        return self.dev.read(spec.STATE + offset, 32).split(b"\0")[0].decode("latin-1")


def ok(slot, name=None, frames=FRAMES):
    return (name or f"s{slot + 1}", frames, 48000, "pcm16")


def bad(slot, kind, index=None):
    return (f"s{slot + 1}", FRAMES, 48000, kind) + ((index,) if index is not None else ())


def entry(name, good, detail):
    return {"id": f"sample-errors:{name}", "ok": bool(good), "detail": str(detail)}


def case_skips(payload, flash):
    """Three samples of a format the loader refuses between good ones: the good ones all load, the window names the first."""
    samples = {500: ok(500), 501: bad(501, "pcm8"), 502: bad(502, "float32"), 503: bad(503, "pcm32"), 504: ok(504), 505: ("s506", FRAMES, 48000, "stereo16"), 506: ("s507", FRAMES, 48000, "pcm24")}
    b = Boot(payload, flash, samples)
    active = b.active()
    return [
        entry("laedt-nach-dem-fehler-weiter", active == [500, 504, 505, 506], active),
        entry("fenster-nennt-das-erste", b.window() and b.line(spec.S_TITLE) == "Sample 502" and b.line(spec.S_TEXT) == "8 bit, use 16/24",
              dict(window=b.window(), title=b.line(spec.S_TITLE), text=b.line(spec.S_TEXT))),
        entry("zaehlt-drei-uebersprungene", b.word(spec.S_COUNT) == 3, b.word(spec.S_COUNT)),
        entry("stereo-und-24-bit-werden-genommen", {505, 506} <= set(active), active),
        entry("keine-assertion", not b.dev.m.asserts, b.dev.m.asserts),
    ]


def case_reasons(payload, flash):
    """Each reason has its own words: not PCM, a slot that is in use, a file that is no WAV at all."""
    out = []
    for name, samples, text in [
        ("kein-pcm", {500: ok(500), 501: bad(501, "float32"), 502: ok(502)}, "not PCM, tag 3"),
        ("slot-belegt", {500: ok(500), 501: bad(501, "pcm16", 500), 502: ok(502)}, "slot in use"),
        ("keine-wav", {500: ok(500), 501: bad(501, "junk"), 502: ok(502)}, "bad WAV file"),
    ]:
        b = Boot(payload, flash, samples)
        out.append(entry(f"grund-{name}", b.window() and b.line(spec.S_TITLE) == "Sample 502" and b.line(spec.S_TEXT) == text and b.active() == [500, 502],
                         dict(title=b.line(spec.S_TITLE), text=b.line(spec.S_TEXT), active=b.active())))
    return out


def case_clean(payload, flash):
    """Samples the loader takes make no window and leave the state empty: 24 bit, stereo and 16 bit mono. The card runs at 25 MHz
    once the loader starts (MMCCLK 0x102 instead of the firmware's 0x105)."""
    b = Boot(payload, flash, {500: ok(500), 501: ("s502", FRAMES, 48000, "pcm24"), 502: ("s503", FRAMES, 48000, "stereo16")})
    return [
        entry("sauber-kein-fenster", not b.window() and b.active() == [500, 501, 502], dict(window=b.window(), active=b.active())),
        entry("sauber-nichts-gezaehlt", b.word(spec.S_COUNT) == 0, b.word(spec.S_COUNT)),
        entry("karte-mit-25-mhz", b.dev.m.mmc.regs.get(4) == 0x102, f"MMCCLK {b.dev.m.mmc.regs.get(4, 0):#x}"),
    ]


def case_slow_card(payload, flash):
    """A card that cannot read at 25 MHz: the load at 25 MHz ends in a card error, the loader runs once more at 12.5 MHz and
    every sample loads, without a window."""
    b = Boot(payload, flash, {500: ok(500), 501: ok(501)}, slow_card=spec.CLKRT_FAST)
    return [entry("karte-zu-langsam-laedt-mit-12-5-mhz", b.active() == [500, 501] and not b.window() and b.dev.m.mmc.regs.get(4) == 0x105
                  and not b.dev.m.asserts, dict(active=b.active(), window=b.window(), mmcclk=hex(b.dev.m.mmc.regs.get(4, 0))))]


def case_kill(payload, flash):
    """With EXIT held at power-on every hook passes on: the load stops at the first bad sample as before, nothing is counted."""
    b = Boot(payload, flash, {500: ok(500), 501: bad(501, "pcm8"), 502: ok(502)}, held=spec.KILL_SWITCH)
    return [
        entry("exit-beim-einschalten-wie-vorher", b.active() == [500] and b.window() and b.word(spec.S_COUNT) in (0, 0xFFFFFFFF),
              dict(active=b.active(), window=b.window(), count=hex(b.word(spec.S_COUNT)))),
        entry("exit-beim-einschalten-takt-der-firmware", b.dev.m.mmc.regs.get(4) == 0x105, f"MMCCLK {b.dev.m.mmc.regs.get(4, 0):#x}"),
    ]


def case_factory_slots(payload, flash):
    """Korg's build: the emulator's empty flash has a factory bank of its own (factorybank.py), so samples for three factory
    slots all load. Hacktribe's build refuses most factory slots even with a real flash image (measured), nothing to check there."""
    b = Boot(payload, None, {150: ok(150), 250: ok(250), 350: ok(350), 500: ok(500)})
    if b.dev.m.profile.build != "stock":
        return [entry("werksplaetze-leerer-flash", True, "Hacktribe's build: nicht anwendbar")]
    active = b.active_all()
    return [entry("werksplaetze-leerer-flash", not b.window() and len(active) == 4, dict(window=b.window(), active=active))]


def case_seek_anchor(payload, flash):
    import sample_seek_cases
    return sample_seek_cases.cases(payload, flash, folder(payload))


GROUPS = (case_skips, case_reasons, case_clean, case_kill, case_factory_slots, case_slow_card, case_seek_anchor)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own devices, so they can run side by side."""
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=["cases"])
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    a = p.parse_args()
    payload = a.patched.read_bytes()[HEADER:]
    flash = load_flash(a.flash) if a.flash else None
    result = cases(payload, flash)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if all(e["ok"] for e in result) else 1


if __name__ == "__main__":
    sys.exit(main())
