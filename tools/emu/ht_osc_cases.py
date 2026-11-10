# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the ht-osc patch (tools/patch/ht_osc.py, docs/messungen/2026-11-08-ht-osc-freie-plaetze.md).

Korg's own firmware gets 76 of Hacktribe's oscillators on the empty slots 421 to 496 (display 422 to 497). Checked: the names
after a start without a card and after a start from e2sSample.all (the factory names 0 to 420 stay the firmware's table, 497 to
499 stay empty sample slots); a file entry for slot 449 (display 450) is skipped while every other entry of the file loads; the
OSC dial goes from 420 through 421..496 to the first user sample and back; the voice's slot lookup gives the entry and a note on
slot 421 sends the DSP the messages a note on the firmware's own oscillator slot 0 sends; a pattern with slot 430 keeps it
through WRITE and a new start; EXPORT ALL SAMPLE writes no entry for 421 to 499; EXIT held at power-on gives the firmware's
empty slots again; a settings file with bit 6 of byte 5 set (once HT OSC OFF) still gives the oscillators. There is no switch.
What the DSP makes of a wave is not modelled: how each oscillator sounds is not checked here.

    tools/emu/.venv/bin/python tools/emu/ht_osc_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import ht_osc as spec  # noqa: E402
import menu_cases as mc  # noqa: E402
import sampleset  # noqa: E402
from machine import load_flash  # noqa: E402
from mfx_cases import PATTERN_SLOTS, DspLog  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
NAMES = spec.NAMES
TABLE = 0xC00D9AB0              # the firmware's table of the slots 0 to 420, copied to NAMES at the start
META = 0xC036AD88               # the sample table, 0x45C bytes per sample, +0x0B used
PATTERN_IN_RAM = 0xC033E6A4     # pointer to the pattern in RAM, the part records from +4 + 0x800, 0x330 each, +8 the sample
VOICE_SLOT = spec.VOICE_SITE - 0x1C   # 0xC0099788 (slot) -> the slot's entry or 0
SWITCH_SCREEN = 0xC0083D28
MAILBOX = 0xFF900A34
CRAFTED = 449                   # display 450: a file entry on an oscillator slot
USERS = (500, 501, 600)         # display 501, 502, 601
LOW = 18                        # the first factory sample slot (display 19)


def has_hooks(payload):
    """True when the OSC selector calls our code."""
    word = struct.unpack_from("<I", payload, spec.SEL_SITE - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= (spec.SEL_SITE + 8 + (off << 2)) & 0xFFFFFFFF < spec.CODE_END


def folder(payload):
    """The folder this copy reads e2sSample.all from (as stereo_pad_cases.folder)."""
    if b"KORG/blechtribe/\0" in payload:
        return "blechtribe/Sample"
    return "electribe sampler/Sample" if b"KORG/electribe sampler/\0" in payload else "hacktribe/Sample"


def name_of(slot):
    return f"S{slot + 1}"


def bank(slots):
    """e2sSample.all with a short sample on each slot, named after the slot (S<display number>)."""
    return sampleset.build({slot: (name_of(slot), 200) for slot in slots})


def full_bank():
    """A file as an export of a full device holds it: the factory samples 18 to 420, the user samples 500 to 998, and one
    entry crafted for the oscillator slot 449."""
    return bank(list(range(LOW, 421)) + [CRAFTED] + list(range(500, 999)))


def card(payload, data, extra=None):
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    if data is not None:
        volume.write(f"KORG/{folder(payload)}/e2sSample.all", data)
    for path, raw in (extra or {}).items():
        volume.write(path.lstrip("/"), raw)
    volume.close()
    return SDCard(MemoryMedium(image))


class Box:
    def __init__(self, payload, flash, held=0, data=None, extra=None, seconds=10, medium=None):
        self.dev = Dev(payload, flash, held)
        self.dev.m.adapter = True
        if medium is not None:
            self.dev.m.insert_card(SDCard(MemoryMedium(bytearray(medium))))
        elif data is not None or extra:
            self.dev.m.insert_card(card(payload, data, extra))
        self.dev.run(seconds)

    def entry(self, slot):
        return self.dev.read(NAMES + slot * 32, 32)

    def name(self, slot):
        return self.entry(slot)[:16].split(b"\0")[0].decode("latin-1")

    def wave(self, slot):
        return struct.unpack_from("<H", self.entry(slot), 0x12)[0]

    def oscillators(self):
        return [self.entry(slot) for slot in range(spec.FIRST, spec.LAST + 1)]

    def record(self, part):
        return self.dev.u32(PATTERN_IN_RAM) + 4 + 0x800 + 0x330 * part

    def sample(self, part=0):
        return struct.unpack("<H", self.dev.read(self.record(part) + 8, 2))[0]

    def set_sample(self, slot, part=0):
        """Part `part`'s sample one below `slot`, then the OSC dial one step up: the firmware's own change."""
        self.dev.m.uc.mem_write(self.record(part) + 8, struct.pack("<H", slot - 1))
        self.turn(1)

    def turn(self, step):
        self.dev.m.send([0x01, 0x01, 0x00, step & 0xFF, 0])
        self.dev.run(0.3)

    def walk(self, start, step, n):
        """The samples the OSC dial gives from `start` on, n steps of `step`."""
        self.dev.m.uc.mem_write(self.record(0) + 8, struct.pack("<H", start))
        out = []
        for _ in range(n):
            self.turn(step)
            out.append(self.sample())
        return out

    def note(self):
        """The message kinds the A34 mailbox gets while pad 1 is hit."""
        log = DspLog(self.dev.m)
        log.clear()
        self.dev.m.send([0x04, 0, 0, 100, 1])
        self.dev.run(0.2)
        self.dev.m.send([0x04, 0, 0, 0, 0])
        self.dev.run(0.3)
        return sorted({x[3][1] for x in log.xfers if x[0] == 0xAB and x[1] == MAILBOX and len(x[3]) > 1 and x[3][0] & 2})


def table(payload):
    return bytes(payload[TABLE - IMAGE:TABLE - IMAGE + 421 * 32])


def factory_names_kept(box, payload):
    """Slots 0 to 17 are the firmware's table: the start copies the table before it clears 421 on."""
    return all(box.entry(slot) == table(payload)[slot * 32:slot * 32 + 32] for slot in range(LOW))


def stock_slots(box, slots):
    """The firmware's empty sample slot: SampleNNN, category 0x11, import number slot + 50."""
    return all(box.name(s) == f"Sample{s + 1}" and box.wave(s) == s + 50 for s in slots)


def entry(name, ok, detail):
    return {"id": f"ht-osc:{name}", "ok": bool(ok), "detail": str(detail)}


def case_names(payload, flash):
    """No card: the factory start fills 421 to 496, 497 to 499 and the user slots stay empty sample slots."""
    box = Box(payload, flash)
    want = spec.entries()
    got = box.oscillators()
    wrong = [spec.FIRST + i for i, (a, b) in enumerate(zip(got, want)) if a != b]
    return [entry("ohne-karte-oszillatoren", not wrong, f"{len(want)} entries, wrong at {wrong[:5]}, 421 {box.name(421)}, 496 {box.name(496)}"),
            entry("ohne-karte-rest-wie-firmware", factory_names_kept(box, payload) and stock_slots(box, (497, 498, 499, 500, 998)),
                  f"497 {box.name(497)}, 500 {box.name(500)}"),
            entry("keine-assertion", not box.dev.m.asserts, box.dev.m.asserts)]


def case_card(payload, flash):
    """A full e2sSample.all with an entry for 449: that entry is skipped, every other one loads."""
    box = Box(payload, flash, data=full_bank(), seconds=40)
    missing = [s for s in list(range(LOW, 421)) + list(range(500, 999)) if box.name(s) != name_of(s)]
    return [entry("datei-oszillatoren", box.oscillators() == spec.entries(), f"449 {box.name(CRAFTED)!r}, wave {box.wave(CRAFTED)}"),
            entry("datei-eintrag-450-abgelehnt-rest-geladen", box.name(CRAFTED) != name_of(CRAFTED) and not missing,
                  f"449 {box.name(CRAFTED)!r}, not loaded: {missing[:8]} ({len(missing)})"),
            entry("datei-497-bis-499-leer", stock_slots(box, (497, 498, 499)), f"497 {box.name(497)}"),
            entry("datei-keine-assertion", not box.dev.m.asserts, box.dev.m.asserts)]


def case_knob(payload, flash):
    """The OSC dial from 420 up through the oscillators to the first user sample (500), and from there back down to 496."""
    box = Box(payload, flash, data=bank(USERS))
    up = box.walk(420, 1, spec.COUNT + 2)
    want = list(range(spec.FIRST, spec.LAST + 1)) + [500, 501]
    down = box.walk(501, -1, 3)
    return [entry("regler-hoch", up == want, f"{up[:3]} ... {up[-4:]}"),
            entry("regler-runter", down == [500, spec.LAST, spec.LAST - 1], f"{down}")]


def case_voice(payload, flash):
    """The voice's slot lookup gives the entry of 421 and a note there sends the kinds of messages of slot 0 (SAW, an
    oscillator of the firmware's own table)."""
    box = Box(payload, flash)
    found = box.dev.call(VOICE_SLOT, spec.FIRST)
    past = box.dev.call(VOICE_SLOT, spec.LAST + 1)
    box.set_sample(1)
    box.turn(-1)
    own = box.note(), box.sample()
    box.set_sample(spec.FIRST)
    ours = box.note(), box.sample()
    return [entry("stimme-findet-421", found == NAMES + spec.FIRST * 32 and past == 0, f"421 -> {found:#x}, 497 -> {past:#x}"),
            entry("note-wie-oszillator-0", own[1] == 0 and ours[1] == spec.FIRST and ours[0] == own[0] and ours[0],
                  f"slot 0 {own}, slot 421 {ours}")]


def case_pattern(payload, flash):
    """Part 1 on slot 430, WRITE: the stored pattern holds 430, and a new start shows it with the oscillator on 430."""
    box = Box(payload, flash)
    box.set_sample(430)
    live = box.sample()
    box.dev.run(2.0)      # the OSC value popup closes first; WRITE while it shows stores nothing
    mc.press(box.dev, "write", wait=0.6)
    mc.press(box.dev, "write", wait=3.0)
    stored = bytes(box.dev.m.flash.mem[PATTERN_SLOTS:PATTERN_SLOTS + 0x4000])
    kept = struct.unpack_from("<H", stored, 0x800 + 8)[0]
    again = Box(payload, bytes(box.dev.m.flash.mem))
    return [entry("pattern-430-geschrieben", live == 430 and kept == 430, f"live {live}, stored {kept}"),
            entry("pattern-430-nach-neustart", again.sample() == 430 and again.name(430) == spec.entries()[430 - spec.FIRST][:16].split(b"\0")[0].decode(),
                  f"part 1 {again.sample()}, 430 {again.name(430)!r}")]


def case_export(payload, flash):
    """EXPORT ALL SAMPLE (DATA UTILITY): the file holds the user samples and no entry for 421 to 499."""
    box = Box(payload, flash, data=bank(USERS))
    box.dev.call(SWITCH_SCREEN, 14, 0)
    box.dev.run(0.4)
    mc.press(box.dev, "menu")
    for _ in range(10):
        mc.press(box.dev, "edit_next")
    mc.press(box.dev, "menu", wait=1.0)
    mc.press(box.dev, "menu", wait=1.0)
    box.dev.run(30)
    volume = fat32.Volume(bytes(box.dev.m.mmc.card.medium.data))
    try:
        data = volume.read(f"/KORG/{folder(payload)}/e2sSample.all")
    finally:
        volume.close()
    offsets = struct.unpack_from(f"<{sampleset.SLOTS}I", data, 16)
    written = [i for i, at in enumerate(offsets) if at]
    ours = [i for i in written if 421 <= i <= 499]
    return [entry("export-ohne-421-bis-499", not ours and set(USERS) <= set(written), f"entries {len(written)}, in 421..499: {ours[:5]}, users {[u for u in USERS if u in written]}")]


def case_exit(payload, flash):
    """EXIT held at power-on: the firmware's empty slots, the entry for 449 loads as on the firmware, the dial skips 421 on."""
    box = Box(payload, flash, held=spec.KILL_SWITCH, data=bank([CRAFTED] + list(USERS)))
    up = box.walk(420, 1, 2)
    return [entry("exit-wie-firmware", stock_slots(box, (421, 496, 497)) and box.name(CRAFTED) == name_of(CRAFTED)
                  and box.dev.call(VOICE_SLOT, spec.FIRST) == 0 and up == [500, 501],
                  f"421 {box.name(421)}, 449 {box.name(CRAFTED)}, dial from 420 {up}")]


def case_old_setting(payload, flash):
    """A settings file with bit 6 of byte 5 set (an earlier build wrote it for a page HT OSC OFF): the bit is read as nothing,
    the file still loads (KEY PADS OFF, bit 4, is read), the slots hold the oscillators and the entry for 449 is skipped."""
    if not mc.has_menu(payload):
        return [entry("alte-einstellung", True, "no BLECH menu in this copy: nothing to check")]
    raw = mc.settings_file_v3(2, 3, mc.look_word(), extras=0x50)
    files = {f"/KORG/{folder(payload)}/e2sSample.all": bank([CRAFTED] + list(USERS)), **mc.CARD_FOLDER, mc.SETTINGS_PATHS[0]: raw}
    dev = mc.boot(payload, flash, files=files, adapter=True, seconds=10)
    got = [bytes(dev.read(NAMES + slot * 32, 32)) for slot in range(spec.FIRST, spec.LAST + 1)]
    crafted = bytes(dev.read(NAMES + CRAFTED * 32, 16)).split(b"\0")[0].decode("latin-1")
    pages = mc.feature_pages()
    mc.goto_group(dev, mc.GROUP_FEATURES, pages.index("KEY PADS"))
    kp = mc.texts_of(dev)
    return [entry("alte-einstellung-bit-6-oszillatoren", got == spec.entries() and crafted != name_of(CRAFTED) and not dev.m.asserts,
                  f"421 {got[0][:16].split(bytes(1))[0]!r}, 449 {crafted!r}"),
            entry("alte-einstellung-datei-gelesen", kp == ("KEY PADS", "OFF", "") and "HT OSC" not in pages, f"{kp}, pages {pages}")]


def case_without(payload, flash):
    """A copy without the patch (the Hacktribe and the blue set): no site calls into the code area, the area stays FF,
    and the start runs without an assertion. Run by hand on such a copy; check.py runs the groups only where has_hooks."""
    sites = (spec.FACTORY_SITE, spec.FILE_SITE, spec.SKIP_SITE, spec.SEL_SITE, spec.VOICE_SITE)
    words = [struct.unpack_from("<I", payload, at - IMAGE)[0] for at in sites]
    area = payload[spec.CODE_AT - IMAGE:spec.CODE_END - IMAGE]
    box = Box(payload, flash)
    return [entry("ohne-patch-unberuehrt", not has_hooks(payload) and set(area) == {0xFF} and not box.dev.m.asserts,
                  f"sites {[hex(w) for w in words]}, area FF {set(area) == {0xFF}}, 421 {box.name(421)!r}, 496 {box.name(496)!r}")]


GROUPS = (case_names, case_card, case_knob, case_voice, case_pattern, case_export, case_exit, case_old_setting)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path, nargs="+")
    p.add_argument("--only", help="comma-separated group names (case_names, ...)")
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    groups = [g for g in GROUPS if not a.only or g.__name__ in a.only.split(",")] if has_hooks(payload) else [case_without]
    result = [e for g in groups for e in g(payload, flash)]
    print(json.dumps(result, indent=1, ensure_ascii=False))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
