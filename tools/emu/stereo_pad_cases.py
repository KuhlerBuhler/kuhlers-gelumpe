# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of the stereo-pad patch (tools/patch/stereo_pad.py, docs/messungen/2026-10-29-stereo-ein-pad.md).

A card with a mono sample (501), a stereo sample (502) and a second mono sample (503), all made from a formula (sampleset.py).
Part 1 gets the stereo sample through the SAMPLE dial, part 2 the second mono sample. With the patch part 1 plays one voice of
type 4 (the DSP's stereo-on-one-voice), part 2 stays its own part and plays its own sample, PART > goes from part 1 to part 2,
and the pattern in RAM changes only in part 1's sample. With EXIT held at power-on the firmware pairs part 1 and 2 again, and so
it does with BLECH > FEATURES > STEREO 1 PAD turned OFF, which WRITE keeps and the next start reads.
What the ARM sends to the DSP is read off the A34 mailbox; the DSP is not modelled, how type 4 sounds is not checked here.

    tools/emu/.venv/bin/python tools/emu/stereo_pad_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import menu_cases as mc  # noqa: E402
import sampleset  # noqa: E402
import stereo_pad as spec  # noqa: E402
from machine import load_flash  # noqa: E402
from mfx_cases import DspLog  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402

IMAGE = 0xC0000000
META = 0xC036AD88               # the sample table, 0x45C bytes per sample: +0 the audio's DSP offset, +9 stereo (docs/messungen/2026-10-07-sample-metadaten-ram.md)
PATTERN_IN_RAM = 0xC033E6A4     # pointer to the pattern in RAM, the part records from +4 + 0x800, 0x330 each, +8 the sample
PART_MODE = 0xC007ED5C          # (any, part): 0 mono, 1 stereo pair, 2 sliced
SEQUENCER = 0xC00431F0          # the sequencer object, +0x320 the selected part
MAILBOX = 0xFF900A34
PART_RIGHT = 0x0F
MONO, STEREO, MONO2 = 500, 501, 502


def has_hooks(payload):
    """True when the part's stereo mode calls our code."""
    word = struct.unpack_from("<I", payload, spec.MODE_SITE - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= (spec.MODE_SITE + 8 + (off << 2)) & 0xFFFFFFFF < spec.CODE_END


def folder(payload):
    """The folder this copy reads e2sSample.all from (as sample_error_cases.folder)."""
    if b"KORG/blechtribe/\0" in payload:
        return "blechtribe/Sample"
    return "electribe sampler/Sample" if b"KORG/electribe sampler/\0" in payload else "hacktribe/Sample"


def stereo_wave(slot, name, frames):
    """A 16-bit stereo sample with the record the firmware writes for one: the length in bytes of both channels, esli[65] 1."""
    wave = bytearray(sampleset.wav(slot, name, frames, kind="stereo16L"))
    at = wave.index(b"esli") + 8
    wave[at + 65] = 1
    return bytes(wave)


def bank():
    """e2sSample.all with the three samples."""
    waves = [(MONO, sampleset.wav(MONO, "mono", 2000)), (STEREO, stereo_wave(STEREO, "stereo", 2000)),
             (MONO2, sampleset.wav(MONO2, "mono2", 2000))]
    table, body = [0] * sampleset.SLOTS, bytearray()
    for slot, wave in waves:
        table[slot] = sampleset.HEADER + len(body)
        body += wave
    data = b"e2s sample all\x1a\0" + struct.pack(f"<{sampleset.SLOTS}I", *table)
    return data.ljust(sampleset.HEADER, b"\0") + bytes(body)


def card(payload):
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    volume.write(f"KORG/{folder(payload)}/e2sSample.all", bank())
    volume.close()
    return SDCard(MemoryMedium(image))


class Box:
    def __init__(self, payload, flash, held=0):
        self.dev = Dev(payload, flash, held)
        self.dev.m.insert_card(card(payload))
        self.dev.run(10)
        self.log = DspLog(self.dev.m)

    def record(self, part):
        return self.dev.u32(PATTERN_IN_RAM) + 4 + 0x800 + 0x330 * part

    def sample(self, part):
        return struct.unpack("<H", self.dev.read(self.record(part) + 8, 2))[0]

    def set_sample(self, part, slot):
        """Part `part` selected, its sample one below `slot`, then the SAMPLE dial one step up: the firmware's own change."""
        self.dev.m.uc.mem_write(self.record(part) + 8, struct.pack("<H", slot - 1))
        self.dev.m.send([0x01, 0x01, 0x00, 0x01, 0])
        self.dev.run(0.4)

    def selected(self):
        return self.dev.u32(self.dev.call(SEQUENCER) + 0x320)

    def modes(self):
        return [self.dev.call(PART_MODE, 0, part) for part in range(4)]

    def pad(self, n):
        """The messages to the DSP's A34 mailbox while pad `n` (0 based) is hit."""
        self.log.clear()
        self.dev.m.send([0x04, n, 0, 100, 1])
        self.dev.run(0.2)
        self.dev.m.send([0x04, n, 0, 0, 0])
        self.dev.run(0.3)
        return [tuple(x[3]) for x in self.log.xfers if x[0] == 0xAB and x[1] == MAILBOX and x[3] and x[3][0] & 2]


def voice_types(messages):
    """The voice types of the 0x2E messages (0 mono, 2 one channel of a pair, 4 stereo on one voice)."""
    return [m[3] for m in messages if len(m) > 3 and m[1] == 0x2E]


def voices(messages):
    """Voices the note takes: the 0x34 message's count word plus one."""
    return [m[2] + 1 for m in messages if len(m) > 2 and m[1] == 0x34]


def plays(messages, offset):
    """True when a 0x01 message hands the DSP the audio at `offset` (high word, low word)."""
    return any(len(m) > 5 and m[1] == 0x01 and (m[4] << 16 | m[5]) == offset for m in messages)


def entry(name, ok, detail):
    return {"id": f"stereo-pad:{name}", "ok": bool(ok), "detail": str(detail)}


def prepared(payload, flash, held=0):
    box = Box(payload, flash, held)
    before = box.dev.read(box.dev.u32(PATTERN_IN_RAM) + 4, 0x4000)
    box.set_sample(0, STEREO)
    box.dev.press(PART_RIGHT)
    second = box.selected()
    box.set_sample(second, MONO2)
    after = box.dev.read(box.dev.u32(PATTERN_IN_RAM) + 4, 0x4000)
    return box, before, after, second


def case_one_pad(payload, flash):
    box, before, after, second = prepared(payload, flash)
    out = []
    stereo = box.dev.read(META + STEREO * 0x45C + 9, 1)[0]
    out.append(entry("stereo-sample-geladen", stereo == 1, f"stereo flag of 502: {stereo}"))
    modes = box.modes()
    out.append(entry("kein-paar", modes[:2] == [0, 0], f"part modes {modes}"))
    out.append(entry("part-rechts-waehlt-part-2", second == 1, f"PART > from part 1 selects part {second + 1}"))
    first = box.pad(0)
    out.append(entry("pad-1-eine-stimme", voices(first) == [1] and voice_types(first) == [4],
                     f"voices {voices(first)}, types {voice_types(first)}"))
    offset = struct.unpack("<I", box.dev.read(META + MONO2 * 0x45C, 4))[0]
    own = box.pad(1)
    out.append(entry("pad-2-eigenes-sample", voices(own) == [1] and voice_types(own) == [0] and plays(own, offset),
                     f"voices {voices(own)}, types {voice_types(own)}, plays 503 at {offset:#x}: {plays(own, offset)}"))
    changed = [i for i in range(len(before)) if before[i] != after[i]]
    want = [0x800 + 8, 0x800 + 9, 0x800 + 0x330 + 8, 0x800 + 0x330 + 9]
    out.append(entry("pattern-nur-die-samples", set(changed) <= set(want), f"changed bytes of the pattern: {[hex(i) for i in changed]}"))
    out.append(entry("keine-assertion", not box.dev.m.asserts, box.dev.m.asserts))
    return out


def case_exit(payload, flash):
    box, _, _, second = prepared(payload, flash, held=spec.KILL_SWITCH)
    modes = box.modes()
    first = box.pad(0)
    return [entry("exit-paar-wie-firmware", modes[0] == 1 and second == 2 and voices(first) == [2] and voice_types(first) == [2],
                  f"part modes {modes}, PART > selects part {second + 1}, voices {voices(first)}, types {voice_types(first)}")]


def has_menu_page(payload):
    """True when the copy has the BLECH menu with the page STEREO 1 PAD (the set carries the runtime)."""
    return mc.has_menu(payload)


def case_page(payload, flash):
    """BLECH > FEATURES > STEREO 1 PAD: ON without a settings file, the dial turns the patch off at once (part 1 and 2 pair again),
    WRITE keeps OFF as bit 2 of byte 5 of the settings file, and the next start reads it."""
    if not has_menu_page(payload):
        return [entry("menu-seite", True, "no BLECH menu in this copy: nothing to check")]
    files = {f"/KORG/{folder(payload)}/e2sSample.all": bank(), **mc.CARD_FOLDER}
    setting = lambda dev: dev.u32(spec.SETTING)
    dev = mc.boot(payload, flash, files=files, adapter=True, seconds=10)
    page = mc.feature_count() - 1
    mc.goto_group(dev, mc.GROUP_FEATURES, page)
    shown = mc.texts_of(dev), mc.counter(dev), setting(dev)
    dev.turn(-1, wait=0.3)
    off = mc.texts_of(dev), setting(dev)
    out = [entry("menu-seite-an", mc.STEREO_PAGE and shown == (("STEREO 1 PAD", "ON", ""), (page, page + 1), 0xFFFFFFFF), f"{shown}"),
           entry("menu-rad-aus", off == (("STEREO 1 PAD", "OFF", ""), 0), f"{off}")]
    mc.press(dev, "write", wait=0.6)
    volume = fat32.Volume(bytes(dev.m.mmc.card.medium.data))
    raws = [volume.read(path) for path in mc.SETTINGS_PATHS if _exists(volume, path)]
    newest = max(raws, key=lambda raw: struct.unpack_from("<I", raw, 8)[0]) if raws else bytes(6)
    out.append(entry("write-bit-2-byte-5", newest[5] & 4, f"byte 5 of the newest settings file: {newest[5]:#x}"))
    for _ in range(3):
        mc.press(dev, "exit", wait=0.4)
    box = Box.__new__(Box)
    box.dev, box.log = dev, DspLog(dev.m)
    box.set_sample(0, STEREO)
    out.append(entry("aus-paart-wie-firmware", box.modes()[0] == 1 and voices(box.pad(0)) == [2], f"part modes {box.modes()}"))
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(dev.m.mmc.card.medium.data))))
    again.run(10)
    mc.goto_group(again, mc.GROUP_FEATURES, page)
    after = mc.texts_of(again), setting(again)
    out.append(entry("start-liest-aus", after == (("STEREO 1 PAD", "OFF", ""), 0) and not again.m.asserts, f"{after}"))
    return out


def case_page_rainbow(payload, flash):
    """STEREO 1 PAD OFF next to METER LOUD RAINBOW (bit 0 of the same byte 5) and, where the set has it, LAST PATTERN OFF (bit 3):
    WRITE keeps every bit, the next start reads both pages OFF."""
    if not has_menu_page(payload):
        return [entry("menu-seite-rainbow", True, "no BLECH menu in this copy: nothing to check")]
    raw = bytearray(mc.settings_file_v2(5, 3, mc.look_word()))
    last = payload[mc.LAST_CODE - 0xC0000000:mc.LAST_CODE - 0xC0000000 + 4] != b"\xff" * 4
    bits = 1 | 4 | (8 if last else 0)
    raw[5] = bits
    raw[-4:] = struct.pack("<I", zlib.crc32(bytes(raw[:-4])) & 0xFFFFFFFF)
    files = {f"/KORG/{folder(payload)}/e2sSample.all": bank(), mc.SETTINGS_PATHS[0]: bytes(raw), **mc.CARD_FOLDER}
    dev = mc.boot(payload, flash, files=files, adapter=True, seconds=10)
    page = mc.feature_count() - 1

    def pages(d):
        mc.goto_group(d, mc.GROUP_FEATURES, page)
        out = [(mc.texts_of(d), d.u32(spec.SETTING))]
        if last:
            mc.goto_group(d, mc.GROUP_FEATURES, page - 1)
            out.append(mc.texts_of(d))
        return out

    want = [(("STEREO 1 PAD", "OFF", ""), 0)] + [("LAST PATTERN", "OFF", "")] * last
    before = pages(dev)
    mc.press(dev, "write", wait=0.6)
    volume = fat32.Volume(bytes(dev.m.mmc.card.medium.data))
    raws = [volume.read(path) for path in mc.SETTINGS_PATHS if _exists(volume, path)]
    newest = max(raws, key=lambda r: struct.unpack_from("<I", r, 8)[0])
    again = Dev(payload, flash, 0)
    again.m.adapter = True
    again.m.insert_card(SDCard(MemoryMedium(bytearray(dev.m.mmc.card.medium.data))))
    again.run(10)
    after = pages(again)
    return [entry("rainbow-start-liest-aus", before == want, f"{before}"),
            entry("rainbow-write-byte-5", newest[5] & bits == bits, f"byte 5 of the newest settings file: {newest[5]:#x}, wanted {bits:#x}"),
            entry("rainbow-neustart-aus", after == want and not again.m.asserts, f"{after}")]


def _exists(volume, path):
    try:
        volume.stat(path)
        return True
    except fat32.FatError:
        return False


GROUPS = (case_one_pad, case_exit, case_page, case_page_rainbow)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    result = cases(payload, load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
