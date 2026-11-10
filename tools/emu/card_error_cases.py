# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases for what the firmware does with a card that is not the plain SDHC card: one that stops answering, a
locked one, an old SDSC card, a card that damages the data, and one that never mounts at the start (docs/emulator.md, "Fehlerfälle der Karte").

check.py runs `cases` on every patched copy that carries the BLECH menu. The faults come from the card model
(sdcard.py: `fail()`, `write_protect`, `kind`); a read fault names the blocks of the sample file, so the mount is not
hit. The cases that need the sample loader or DATA UTILITY of the red and Hacktribe do not run on the blue Electribe,
which has neither. Everything is made here, no Korg data.

    tools/emu/.venv/bin/python tools/emu/card_error_cases.py --vsb PATCHED.VSB [--only N]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import cardstore  # noqa: E402
import fat32  # noqa: E402
import load_bar as spec  # noqa: E402
import menu_cases  # noqa: E402
import sampleset  # noqa: E402
import synthaddr  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

SAMPLES = sampleset.build(sampleset.sized(3, 48000))
CARD_ERROR, WRITE_PROTECTED, RESTING = 4, 3, 0x26     # the firmware's error box codes (its text table at 0xC00E3280), 0x26: no box
EXPORT_ALL_PATTERN = 2                                # the second function of DATA UTILITY
DATA_UTILITY_PAGE = 28                                # its page in the pattern menu, with BLECH or without
MAIN_SCREEN = 1


def has_hooks(payload):
    return menu_cases.has_menu(payload)


def entry(name, ok, detail):
    return {"id": f"cardfault:{name}", "ok": bool(ok), "detail": str(detail)}


def blue(payload):
    return synthaddr.is_synth(payload)


class Rig:
    """A device on mains power with a card in: the sample file of its folder on it (not on the blue, which has no sample loader)."""

    def __init__(self, payload, files=None, held=0, image=None, **card):
        self.payload = payload
        self.folder = cardstore.card_folder(payload)
        self.dev = Dev(payload, None, held, adapter=True)
        files = {f"KORG/{self.folder}/Sample/e2sSample.all": SAMPLES} if files is None and not blue(payload) else files or {}
        self.card = SDCard(MemoryMedium(menu_cases.card_image(files) if image is None else image), **card)
        self.dev.m.insert_card(self.card)
        self.before = set(self.tree() or ())
        self.sample_lbas = self.file_lbas(f"KORG/{self.folder}/Sample/e2sSample.all")

    def file_lbas(self, path):
        """The card's blocks that hold a file, so a fault can hit what the firmware reads of it and nothing of the mount."""
        volume = None
        try:
            volume = fat32.Volume(bytes(self.card.medium.data))
            first = volume.data // 512
            return [first + (c - 2) * volume.spc + k for c in volume.chain(volume.stat(path).cluster) for k in range(volume.spc)]
        except fat32.FatError:
            return []
        finally:
            if volume:
                volume.close()

    def run(self, seconds):
        self.dev.run(seconds)

    def codes(self, seconds, stop=None, step=0.1):
        """Runs up to `seconds`, ends early at a box code for which `stop` is true; returns [(second, code)] of the box codes seen."""
        seen, end = [], self.dev.m.time_ns / 1e9 + seconds
        while self.dev.m.time_ns / 1e9 < end and not self.dev.m.asserts:
            self.dev.run(step)
            code = self.dev.u32(spec.ERR_CODE)
            if code != RESTING and (not seen or seen[-1][1] != code):
                seen.append((round(self.dev.m.time_ns / 1e9, 1), code))
                if stop and stop(code):
                    break
        return seen

    def screen(self):
        return self.dev.screen()["number"]

    def tree(self):
        """KORG/<folder>/ on the card as the firmware left it: {name: size or None for a folder}, None without the folder."""
        volume = None
        try:
            volume = fat32.Volume(bytes(self.card.medium.data))
            return {e.name: None if e.is_dir else e.size for e in volume.listdir(f"KORG/{self.folder}")}
        except fat32.FatError:
            return None
        finally:
            if volume:
                volume.close()

    def made(self):
        """The folders of KORG/<folder>/ that were not on the card at the start."""
        return sorted(n for n in (self.tree() or ()) if n not in self.before)

    def data_utility(self, n):
        """Function n of DATA UTILITY (page 28 of the pattern menu; BLECH adds pages behind it), up to its "press [Enter]" line."""
        menu_cases.for_build(self.payload)
        self.dev.press("menu", 0.4)
        for _ in range(8):
            page = menu_cases.counter(self.dev)
            if page and page[0] == DATA_UTILITY_PAGE:
                break
            self.dev.press("edit_prev", 0.3)
        self.dev.press("menu", 0.4)
        for _ in range(n - 1):
            self.dev.press("edit_next", 0.25)


def case_stops_answering(payload, flash):
    """A card that stops answering reads after it mounted (a card that gave up, or a loose one): the loader fails and the
    firmware's box says "Card Error" (code 4), the same for a command that is not answered and for data that never comes.
    Nothing is written, no folder is made."""
    if blue(payload):
        return []
    out = []
    for name, kind, narrow in (("no_answer", "no_response", {"cmds": [17, 18]}), ("data_timeout", "read_timeout", {})):
        rig = Rig(payload)
        fault = rig.card.fail(kind, lbas=rig.sample_lbas, **narrow)
        seen = rig.codes(40, stop=lambda c: c == CARD_ERROR)
        out.append(entry(f"read_stops_{name}", seen and seen[-1][1] == CARD_ERROR and fault.hits and rig.card.sectors_written == 0
                         and rig.made() == [] and not rig.dev.m.asserts,
                         f"{kind}: box codes {seen}, fault hit {fault.hits} times, sectors written {rig.card.sectors_written}, "
                         f"BLECH folders made {rig.made()}"))
    return out


def case_write_protect(payload, flash):
    """A locked card (the switch is GPIO 4.0, which the firmware's disk status reads): the start sends no write command and
    makes no folder, the device runs on. EXPORT ALL PATTERN shows "Card Write Protected" (code 3) at once and writes
    nothing; with the lock off the same export writes its file."""
    out = []
    rig = Rig(payload, write_protect=True)
    rig.run(8)
    writes = rig.card.commands[24] + rig.card.commands[25]
    out.append(entry("locked_start_writes_nothing", writes == 0 and rig.made() == [] and rig.screen() == MAIN_SCREEN
                     and not rig.dev.m.asserts,
                     f"write commands {writes}, BLECH folders made {rig.made()}, screen {rig.screen()}"))
    if blue(payload):
        return out
    rig.data_utility(EXPORT_ALL_PATTERN)
    rig.dev.press("menu", 0.3)
    seen = rig.codes(3)
    writes = rig.card.commands[24] + rig.card.commands[25]
    name = "electribe_sampler_allpattern.e2sallpat"
    out.append(entry("locked_export_says_so", seen and seen[0][1] == WRITE_PROTECTED and writes == 0 and name not in (rig.tree() or {})
                     and not rig.dev.m.asserts,
                     f"box codes {seen}, write commands {writes}, export file on the card {name in (rig.tree() or {})}"))
    rig.card.write_protect = False
    rig.dev.press("exit", 0.5)
    rig.dev.press("menu", 0.3)
    rig.run(12)
    size = (rig.tree() or {}).get(name)
    out.append(entry("unlocked_export_writes", size and rig.card.sectors_written > 100 and not rig.dev.m.asserts,
                     f"lock off: export file {size} bytes, sectors written {rig.card.sectors_written}"))
    return out


def case_sdsc(payload, flash):
    """An old SDSC card (no CMD8 answer, no high-capacity bit, byte addresses) mounts and reads: the start does the same
    as with the SDHC card, it reads as many sectors, writes as many and makes the same folders; every address was a whole block."""
    ref, old = Rig(payload), Rig(payload, kind="sdsc")
    for rig in (ref, old):
        rig.run(12)
    a, b = ref.card, old.card
    same = (b.sectors_read, b.sectors_written) == (a.sectors_read, a.sectors_written) and a.sectors_read > 0
    out = [entry("sdsc_mounts_and_reads", same and ref.tree() == old.tree() and old.screen() == MAIN_SCREEN and b.address_errors == 0
                 and b.commands[8] == 1 and not old.dev.m.asserts and not ref.dev.m.asserts,
                 f"SDSC read {b.sectors_read} wrote {b.sectors_written}, SDHC read {a.sectors_read} wrote {a.sectors_written}, "
                 f"same files {ref.tree() == old.tree()}, address errors {b.address_errors}, screen {old.screen()}")]
    return out


def case_damaged_data(payload, flash):
    """A card whose data arrives with a bad CRC. The firmware's driver never looks at the CRC flags (it takes DATDNE for a
    finished transfer and RSPDNE, TOUTRS and CRCRS for an answer), so a damaged read is not a card error: the start goes on
    with the damaged bytes, and whatever they break shows up later (the sample loader's own box). A write the card refused
    leaves its data out; FatFs finds the missing data and the box says "Card Error"."""
    if blue(payload):
        return []
    out = []
    rig = Rig(payload)
    fault = rig.card.fail("read_crc", lbas=rig.sample_lbas)
    seen = rig.codes(30)
    out.append(entry("read_crc_is_not_a_card_error", fault.hits > 0 and all(c != CARD_ERROR for _, c in seen) and rig.screen() == MAIN_SCREEN
                     and not rig.dev.m.asserts,
                     f"{fault.hits} blocks damaged, box codes {seen}, screen {rig.screen()}"))
    for name, kind, narrow in (("write_crc", "write_crc", {}), ("write_no_answer", "no_response", {"cmds": [24, 25]})):
        rig = Rig(payload)
        rig.run(8)
        fault = rig.card.fail(kind, **narrow)
        rig.data_utility(EXPORT_ALL_PATTERN)
        rig.dev.press("menu", 0.3)
        seen = rig.codes(40, stop=lambda c: c == CARD_ERROR)
        out.append(entry(f"{name}_ends_in_card_error", seen and seen[-1][1] == CARD_ERROR and fault.hits and rig.card.sectors_written < 200
                         and not rig.dev.m.asserts,
                         f"{kind}: box codes {seen}, fault hit {fault.hits} times, sectors written {rig.card.sectors_written}"))
    return out


def case_dead_card(payload, flash):
    """A card in the slot that never mounts: one without a filesystem (all zeros) and one that answers no command at all.
    The start goes on to the main screen as the firmware's does (the same run with EXIT held at power-on, every patch off),
    with the same box codes (not on the blue, whose box code is elsewhere), nothing written and no folder made (2026-11-10: the loading bar's mount retry slept before the
    operating system's tick runs and the start hung at the start image)."""
    out = []
    for name, card in (("no_filesystem", {"image": bytearray(64 << 20)}),
                       ("answers_nothing", {"files": {}, "faults": [{"kind": "no_response"}]})):
        runs = []
        for held in (0, spec.KILL_SWITCH):
            rig = Rig(payload, held=held, **card)
            runs.append((rig, rig.codes(15)))
        (rig, seen), (_, ref) = runs
        out.append(entry(f"dead_card_{name}", rig.screen() == MAIN_SCREEN and (blue(payload) or seen == ref) and rig.card.sectors_written == 0
                         and rig.made() == [] and not rig.dev.m.asserts,
                         f"screen {rig.screen()}, box codes {seen} (with EXIT held {ref}), sectors written {rig.card.sectors_written}, "
                         f"BLECH folders made {rig.made()}"))
    return out


GROUPS = (case_stops_answering, case_write_protect, case_sdsc, case_damaged_data, case_dead_card)


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
    import lifetime
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    entries = group_entries(payload, None, a.only) if a.only is not None else cases(payload)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
