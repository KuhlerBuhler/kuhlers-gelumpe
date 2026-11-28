# SPDX-License-Identifier: GPL-2.0-only
"""Emulator cases of CATEGORY in SAMPLE EDIT (tools/patch/script_sample_edit.s, docs/messungen/2026-11-21-sample-kategorie.md).

SAMPLE EDIT (screen 38) gets the page CATEGORY behind RENAME and the page ONE SHOT behind PLAY LEVEL: pages of the BLECH menu
(level 9) that show themselves as pages 3 and 11 of 12. Checked: the counter of every page (1/12 to 12/12), also right after
coming back from CATEGORY; EDIT left and right between RENAME, CATEGORY and START POINT, and LOOP START for a sliced mono sample,
which the firmware steps to from RENAME; ONE SHOT between PLAY LEVEL and DELETE SAMPLE, its dial sets LOOP START to END POINT
(ON) or to START POINT (OFF) through the firmware's own LOOP START, a one-shot note leaves the gate open, EXPORT ALL SAMPLE
writes it; the dial sets
the category byte of the sample's name entry, stops at 0 and 17 and shows the firmware's own texts; EXPORT ALL SAMPLE writes the
category into e2sSample.all; a factory slot with a sample from the card has the page as well; without any sample the page shows
"---" and the dial changes nothing; EXIT goes back to the entry screen (37); with EXIT held at power-on SAMPLE EDIT is Korg's 10
pages. A stereo sample also gets TURN MONO behind PLAY LEVEL (14 of 15): after "Are You Sure ?" it is mixed in the DSP's
memory to (L + R) / 2 with the points on the same frame (case_turn_mono, with the DSP model). REVERSE sits behind ONE SHOT: it
turns the PCM round in the DSP, the points stay (case_reverse, with the DSP model). DECLICK sits behind REVERSE: a
note of a sample with it starts, loops and ends on the nearest common zero crossing within 128 frames, else on the quietest
frame, while the stored points stay (case_declick, with the DSP model, against a reference in Python). The synth has no SAMPLE
EDIT and no hooks for it.

    tools/emu/.venv/bin/python tools/emu/sample_category_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN] [--only case_page,...]
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import unicorn

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import ht_osc_cases as hc  # noqa: E402
import menu_cases as mc  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import SWITCH_SCREEN  # noqa: E402
import lifetime  # noqa: E402
import sampleset  # noqa: E402
import parallel  # noqa: E402
from dsp_model import DspModel  # noqa: E402

IMAGE = 0xC0000000
SITES = (0xC0069BB8, 0xC0069C88)  # slots 4 and 5 of screen 38 (EDIT left and right), `push {r4, r5, r6, lr}` in the firmware
FIRST_WORD = 0xE92D4070
ENTRY, PAGES_SCREEN, MENU = 37, 38, 45
SE_PAGE = 0xC0691278
NAMES = 0xC047B08C
MODEL = 0xC0345A08
MANAGER = 0xC03404C0
CATEGORY_TEXTS = (0xC00A6E06, 0xC00A6E0F, 0xC00A6E1A, 0xC00A6E21, 0xC00A6E29, 0xC00A6E30, 0xC00A6E38, 0xC00A6E41, 0xC00A6E48,
                  0xC00A6E50, 0xC00A6E58, 0xC00A6E5D, 0xC00A6E62, 0xC00A6E68, 0xC00A6E70, 0xC00A6E79, 0xC00A6E80, 0xC00A6E86)
USER, FACTORY = 500, 100          # display 501, and a factory slot (101) a card sample can take on the Sampler (not on Hacktribe)
STEPS_AT = 1168                   # esli: the slice step count; with it a mono sample skips START POINT to LOOP START in SAMPLE EDIT
LOOP_AT, END_AT, ONE_SHOT_AT = 44, 48, 52   # esli: loop start, end (frames), the one-shot byte
PLAY = 0xC0362EE8                 # the firmware's play table, 16 bytes a sample index: +14 one-shot
TRANSPORT = 0xC06BC318            # the firmware's transport word, 0 stopped (script_hw.s:HW_TRANSPORT)
META, FREE = 0xC036AD88, 0xC00F9C80   # its metadata (0x45C a physical index: +0 DSP offset, +4 PCM bytes, +9 stereo), its DSP allocation pointer
SAMPLE_INDEX, START_SET, END_SET, LOOP_SET, ONE_SHOT_GET = 0xC004E4EC, 0xC004E63C, 0xC004E710, 0xC004E7E8, 0xC004EA38
NOTE_ON = 0xC0099BCC              # the voice start behind DECLICK's hook: r7 the physical index, r6 start, r3 loop and r2 end from it
DECLICK_AT, DECLICK_WIN = 53, 128 # esli: the byte DECLICK keeps in bit 0 (play table +15); the search window, frames either side


def has_hooks(payload):
    """True when both slots of screen 38 branch into our code (the Sampler's builds with the BLECH menu)."""
    if synthaddr.is_synth(payload):
        return False
    words = [struct.unpack_from("<I", payload, at - IMAGE)[0] for at in SITES]
    return all(w != FIRST_WORD and w >> 24 == 0xEA for w in words)


def entry(name, ok, detail):
    return {"id": f"samplecat:{name}", "ok": bool(ok), "detail": str(detail)}


def text_at(payload, address):
    raw = payload[address - IMAGE:address - IMAGE + 24]
    return raw.split(b"\0")[0].decode("latin-1")


def esli_of(data, slot):
    """The offset of `slot`'s esli record in e2sSample.all."""
    return data.index(b"esli", struct.unpack_from("<I", data, 16 + slot * 4)[0]) + 8


def looped(data, slot, loop=100):
    """e2sSample.all with `slot` looped: loop start before the end, the one-shot byte 0."""
    out = bytearray(data)
    at = esli_of(out, slot)
    struct.pack_into("<I", out, at + LOOP_AT, loop)
    out[at + ONE_SHOT_AT] = 0
    return bytes(out)


def sliced(data, slot):
    """e2sSample.all with a slice step count on `slot`'s record."""
    out = bytearray(data)
    at = struct.unpack_from("<I", out, 16 + slot * 4)[0]
    esli = out.index(b"esli", at) + 8
    out[esli + STEPS_AT] = 8
    return bytes(out)


class Edit:
    """A device with a card, on SAMPLE EDIT's first page."""

    def __init__(self, payload, flash, slots=(USER,), data=None, held=0, dsp=False):
        mc.for_build(payload)
        self.payload = payload
        if data is None and slots:
            data = hc.bank(list(slots))
        if dsp:                   # the model of the DSP listens from power-on, so it holds the PCM the start loads
            self.box = hc.Box.__new__(hc.Box)
            self.box.dev = hc.Dev(payload, flash, held)
            self.box.dev.m.adapter = True
            self.dsp = DspModel.attach(self.box.dev.m)
            self.box.dev.m.insert_card(hc.card(payload, data))
            self.box.dev.run(12)
        else:
            self.box = hc.Box(payload, flash, held=held, data=data, seconds=12)
        self.dev = self.box.dev
        self.dev.call(SWITCH_SCREEN, ENTRY, 0)
        self.dev.run(0.5)
        self.dev.press("menu")

    def screen(self):
        return self.dev.u32(self.dev.u32(MANAGER) + 0x2C)

    def page(self):
        return self.dev.u32(SE_PAGE)

    def slot(self):
        return self.dev.u32(self.dev.u32(MODEL) + 0x3FC)

    def category(self, slot=None):
        return self.dev.read(NAMES + (self.slot() if slot is None else slot) * 32 + 0x10, 2)

    def shown(self):
        """(screen, the page counter as shown, 1-based, the menu's title and value)."""
        index, total = mc.counter(self.dev)
        return self.screen(), (index + 1, total), mc.texts_of(self.dev)[:2]

    def key(self, name):
        self.dev.press(name, 0.5)
        return self.shown()

    def turn(self, step):
        self.dev.turn(step)
        return mc.texts_of(self.dev)[1]

    def select(self, slot):
        """SELECT SAMPLE's dial until `slot` (it steps only through slots with a sample)."""
        for _ in range(8):
            if self.slot() == slot:
                return True
            self.dev.turn(-1)
        return self.slot() == slot

    def asserts(self):
        return self.dev.m.asserts

    def points(self):
        """(start, end, loop start, one-shot) of SAMPLE EDIT's sample from the firmware's getters, and its play table byte."""
        index = self.dev.call(SAMPLE_INDEX, self.slot()) & 0xFFFF
        signed = [v - (1 << 32) if v & 0x80000000 else v for v in (self.dev.call(f, index, 0) for f in (START_SET, END_SET, LOOP_SET))]
        return (*signed, self.dev.call(ONE_SHOT_GET, index), self.dev.read(PLAY + index * 16 + 14, 1)[0])

    def gate(self):
        """The gate values the DSP gets for one pad note on part 0: [1, 0] for a looped sample, [1] for a one-shot one."""
        dsp = DspModel.attach(self.dev.m)
        first = len(dsp.gates)
        self.dev.m.send([0x04, 0, 0, 100, 1])
        self.dev.run(0.2)
        self.dev.m.send([0x04, 0, 0, 0, 0])
        self.dev.run(0.5)
        return [g[3] for g in dsp.gates[first:]]

    def export(self):
        """EXIT, then EXPORT ALL SAMPLE in DATA UTILITY: e2sSample.all as it is on the card after it."""
        dev = self.dev
        dev.press("exit", 0.5)
        dev.call(SWITCH_SCREEN, 14, 0)
        dev.run(0.4)
        mc.press(dev, "menu")
        for _ in range(10):
            mc.press(dev, "edit_next")
        mc.press(dev, "menu", wait=1.0)
        mc.press(dev, "menu", wait=1.0)
        dev.run(30)
        volume = fat32.Volume(bytes(dev.m.mmc.card.medium.data))
        try:
            return volume.read(f"/KORG/{hc.folder(self.payload)}/e2sSample.all")
        finally:
            volume.close()


def case_page(payload, flash):
    """The counter of every page, EDIT left and right around CATEGORY, EXIT to the entry screen."""
    e = Edit(payload, flash)
    first = e.shown()
    rename = e.key("edit_next")
    category = e.key("edit_next")
    start = e.key("edit_next")
    back = e.key("edit_prev")
    rename_again = (e.key("edit_prev"), e.key("edit_next"))
    walk = [e.key("edit_next")[1] for _ in range(11)]
    last = e.shown()
    wrap = e.key("edit_next")
    out = e.key("exit")
    again = e.key("menu")
    ok_counter = (first[:2] == (PAGES_SCREEN, (1, 14)) and rename[:2] == (PAGES_SCREEN, (2, 14)) and category[1] == (3, 14)
                  and start[:2] == (PAGES_SCREEN, (4, 14)) and back[1] == (3, 14) and rename_again[0][:2] == (PAGES_SCREEN, (2, 14)))
    ok_menu = category[0] == MENU and category[2][0] == "CATEGORY" and back[0] == MENU and rename_again[1][0] == MENU
    ok_walk = walk == [(i, 14) for i in range(4, 15)] and last[1] == (14, 14)
    return [entry("counter_and_steps", ok_counter and ok_menu and not e.asserts(),
                  dict(first=first, rename=rename, category=category, start=start, back=back, rename_again=rename_again)),
            entry("pages_4_to_14", ok_walk and wrap[:2] == (PAGES_SCREEN, (1, 14)) and not e.asserts(), dict(walk=walk, last=last, wrap=wrap)),
            entry("exit_to_entry", out[0] == ENTRY and again[:2] == (PAGES_SCREEN, (1, 14)) and not e.asserts(), dict(exit=out, again=again))]


def case_wheel(payload, flash):
    """The dial sets the category byte, stops at 0 and 17, the value is the firmware's text."""
    e = Edit(payload, flash)
    e.key("edit_next")
    e.key("edit_next")
    texts = [text_at(payload, a) for a in CATEGORY_TEXTS]
    start = (mc.texts_of(e.dev)[1], e.category().hex())
    seen = []
    for step in (1, -1, -1, -1, -40, 40, 1, -15):
        seen.append((e.turn(step), e.category()[0], e.category()[1]))
    values = [v for v, _, _ in seen]
    cats = [c for _, c, _ in seen]
    ok = (start == (texts[2], "0200") and cats == [3, 2, 1, 0, 0, 17, 17, 2] and all(v == texts[c] for v, c in zip(values, cats))
          and all(hi == 0 for _, _, hi in seen))
    e.key("edit_next")
    kept = e.category()[0]
    return [entry("dial_sets_category", ok and kept == 2 and not e.asserts(), dict(start=start, seen=seen, kept=kept))]


def case_export(payload, flash):
    """EXPORT ALL SAMPLE writes the category the dial set into the sample's record."""
    e = Edit(payload, flash)
    e.key("edit_next")
    e.key("edit_next")
    e.turn(5)
    set_to = e.category()[0]
    data = e.export()
    at = struct.unpack_from("<I", data, 16 + USER * 4)[0] if data else 0
    written = None
    if at:
        esli = data.index(b"esli", at) + 8
        written = struct.unpack_from("<H", data, esli + 18)[0]
    return [entry("export_writes_category", set_to == 7 and written == 7 and not e.asserts(), dict(set_to=set_to, written=written))]


def case_sliced(payload, flash):
    """A sliced mono sample: the firmware steps from RENAME to LOOP START (page 5), CATEGORY sits in between both ways."""
    e = Edit(payload, flash, data=sliced(hc.bank([USER]), USER))
    sliced_now = e.dev.call(0xC007DE74, e.dev.u32(MODEL))
    rename = e.key("edit_next")
    category = e.key("edit_next")
    loop = (e.key("edit_next"), e.page())
    back = e.key("edit_prev")
    back2 = (e.key("edit_prev"), e.page())
    ok = (sliced_now and rename[1] == (2, 14) and category[0] == MENU and category[1] == (3, 14) and loop[1] == 5
          and loop[0][:2] == (PAGES_SCREEN, (7, 14)) and back[0] == MENU and back2[1] == 1 and back2[0][1] == (2, 14))
    return [entry("sliced_skips_to_loop_start", ok and not e.asserts(), dict(sliced=sliced_now, rename=rename, category=category, loop=loop, back=back, back2=back2))]


def case_one_shot(payload, flash):
    """ONE SHOT between PLAY LEVEL and DELETE SAMPLE. ON sets LOOP START to END POINT, OFF to START POINT, both through the
    firmware's own LOOP START, which derives one-shot from loop start == end; the play table follows. As on the firmware's own
    pages the dial is heard at once, WRITE keeps it and EXIT without WRITE gives the old points back; EXPORT ALL SAMPLE writes
    what WRITE kept. A one-shot note leaves the gate open; a looped one closes it, once SAMPLE EDIT is left (the firmware's own
    LOOP START does the same). An oscillator slot shows "---" and the dial changes nothing."""
    e = Edit(payload, flash, data=looped(hc.bank([USER]), USER))
    e.box.set_sample(USER)
    before = (e.points(), e.gate())
    delete = e.key("edit_prev")
    declick = e.key("edit_prev")
    reverse = e.key("edit_prev")
    page = e.key("edit_prev")
    level = e.key("edit_prev")
    again = e.key("edit_next")
    on = (e.turn(1), e.points(), e.gate())
    kept = (e.turn(1), e.points())
    off = (e.turn(-1), e.points())
    e.turn(1)
    write = e.key("write")
    e.dev.run(3)                  # the firmware's WRITE takes the keys again once it is done
    e.turn(-1)
    nxt = e.key("edit_next")
    out = e.key("exit")
    after = e.points()
    data = e.export()
    at = esli_of(data, USER) if data else 0
    written = struct.unpack_from("<II", data, at + LOOP_AT) + (data[at + ONE_SHOT_AT],) if at else None
    start, end = before[0][0], before[0][1]
    ok_before = before[0][2] < end and before[0][3:] == (0, 0) and before[1] == [1, 0]
    ok_ring = (delete[1] == (14, 14) and declick[:3] == (MENU, (13, 14), ("DECLICK", "OFF"))
               and reverse[:3] == (MENU, (12, 14), ("REVERSE", "OFF"))
               and page[:3] == (MENU, (11, 14), ("ONE SHOT", "OFF")) and level[:2] == (PAGES_SCREEN, (10, 14))
               and again[:2] == (MENU, (11, 14)) and nxt[:2] == (MENU, (12, 14)))
    ok_on = on[0] == "ON" and on[1][:3] == (start, end, end) and on[1][3:] == (1, 1) and on[2] == [1]
    ok_kept = kept[0] == "ON" and kept[1] == on[1]
    ok_off = off[0] == "OFF" and off[1][2] == start and off[1][3:] == (0, 0)
    ok_write = write[0] == MENU and write[2] == ("ONE SHOT", "saved") and out[0] == ENTRY and after == on[1]
    ok_written = written is not None and written[0] == written[1] == 2 * end and written[2] != 0
    g = Edit(payload, flash)
    g.box.set_sample(USER)
    g.key("edit_prev")
    g.key("edit_prev")
    g.key("edit_prev")
    shown_on = g.key("edit_prev")
    g.turn(-1)
    g.key("write")
    g.dev.run(3)
    g.key("exit")
    g.dev.press("exit", 0.5)
    left = (g.screen(), g.points(), g.gate())
    g.dev.call(SWITCH_SCREEN, ENTRY, 0)
    g.dev.run(0.5)
    g.key("menu")
    g.key("edit_prev")
    g.key("edit_prev")
    g.key("edit_prev")
    g.key("edit_prev")
    g.dev.m.uc.mem_write(g.dev.u32(MODEL) + 0x3FC, struct.pack("<I", 0))
    g.dev.run(0.3)
    plays = g.dev.read(PLAY, 1000 * 16)
    value = g.turn(1)
    guard = value == "---" and g.shown()[2] == ("ONE SHOT", "---") and g.dev.read(PLAY, 1000 * 16) == plays
    ok_left = (shown_on[2] == ("ONE SHOT", "ON") and left[0] not in (ENTRY, PAGES_SCREEN, MENU) and left[1][2] == left[1][0]
               and left[1][3:] == (0, 0) and left[2] == [1, 0])
    return [entry("one_shot_page_in_the_ring", ok_ring and not e.asserts(), dict(delete=delete, declick=declick, reverse=reverse, page=page, level=level, again=again, next=nxt)),
            entry("one_shot_on_off", ok_before and ok_on and ok_kept and ok_off and not e.asserts(), dict(before=before, on=on, kept=kept, off=off)),
            entry("one_shot_write_keeps_exit_drops", ok_write and ok_written and not e.asserts(),
                  dict(write=write, exit=out, after=after, written=written, end=end)),
            entry("one_shot_off_closes_the_gate", ok_left and not g.asserts(), dict(shown=shown_on, left=left)),
            entry("one_shot_oscillator_dashes", guard and not g.asserts(), dict(value=value, shown=g.shown()))]


def stereo_bank(frames, start=40, loop=400):
    """e2sSample.all with one stereo sample on USER whose left and right differ, start and loop start inside it (bytes of
    both channels, as the esli record keeps them for stereo). -> (file, left, right)."""
    data = bytearray(sampleset.build({USER: (hc.name_of(USER), frames, 48000, "stereo16")}))
    left = [(37 * i) % 20001 - 10000 for i in range(frames)]
    right = [(-91 * i + 5000) % 30001 - 15000 for i in range(frames)]
    at = data.index(b"data", struct.unpack_from("<I", data, 16 + USER * 4)[0]) + 8
    for i in range(frames):
        struct.pack_into("<hh", data, at + 4 * i, left[i], right[i])
    esli = esli_of(data, USER)
    struct.pack_into("<II", data, esli + 40, start, loop)
    data[esli + ONE_SHOT_AT] = 0
    return bytes(data), left, right


def case_turn_mono(payload, flash):
    """TURN MONO, behind DECLICK for a stereo sample only. ENTER asks the firmware's "Are You Sure ?", EXIT takes it back,
    the second ENTER mixes the sample in the DSP's memory to (L+R)/2 rounded down (two blocks of the firmware's DSP read), the
    points stay on the same frame, the metadata says mono with half the bytes and the allocation pointer of the last sample
    moves back. EXIT without WRITE keeps it (the snapshot is taken again), EXPORT ALL SAMPLE writes a mono file. While the
    sequencer runs ENTER only says "stop PLAY". A mono sample has no TURN MONO (case_one_shot counts 14 pages)."""
    frames = 20000                # 80000 bytes: one full block of 0x10000 and a part one
    data, left, right = stereo_bank(frames)
    e = Edit(payload, flash, data=data, dsp=True)
    e.box.set_sample(USER)
    index = e.dev.call(SAMPLE_INDEX, e.slot()) & 0xFFFF
    phys = e.dev.call(0xC004E2F0, index) & 0xFFFF
    meta = META + phys * 0x45C
    base, size = struct.unpack("<II", e.dev.read(meta, 8))
    free = e.dev.u32(FREE)
    before = (e.points(), e.dev.read(meta + 9, 1)[0], size, base + size == free)
    words = e.dsp.samples(base, 2 * frames)
    ok_loaded = words == [v for pair in zip(left, right) for v in pair]
    delete = e.key("edit_prev")
    page = e.key("edit_prev")
    shot = e.key("edit_prev")
    again = e.key("edit_next")
    ask = e.key("menu")
    back = e.key("exit")
    e.key("menu")
    e.dev.run(0.3)
    done = e.key("menu")
    e.dev.run(1)
    done = e.shown()
    meta_after = struct.unpack("<II", e.dev.read(meta, 8)) + (e.dev.read(meta + 9, 1)[0],)
    mono = e.dsp.samples(base, frames)
    want = [(a + b) >> 1 for a, b in zip(left, right)]
    wrong = sum(1 for a, b in zip(mono, want) if a != b)
    after = (e.points(), e.dev.u32(FREE))
    nxt = e.key("edit_next")
    prev = e.key("edit_prev")
    out = e.key("exit")
    kept = (struct.unpack("<II", e.dev.read(meta, 8)) + (e.dev.read(meta + 9, 1)[0],), e.points())
    gate = e.gate()
    written = e.export()
    at = esli_of(written, USER) if written else 0
    riff = struct.unpack_from("<I", written, 16 + USER * 4)[0] if written else 0
    channels = struct.unpack_from("<H", written, written.index(b"fmt ", riff) + 10)[0] if written else None
    dat = written.index(b"data", riff) if written else 0
    pcm = list(struct.unpack_from(f"<{struct.unpack_from('<I', written, dat + 4)[0] // 2}h", written, dat + 8)) if written else []
    record = (struct.unpack_from("<III", written, at + 40), struct.unpack_from("<I", written, at + 60)[0], written[at + 65]) if at else None
    ok_ring = (delete[:2] == (PAGES_SCREEN, (15, 15)) and page[:3] == (MENU, (14, 15), ("TURN MONO", "Stereo"))
               and shot[:3] == (MENU, (13, 15), ("DECLICK", "OFF")) and again[:3] == page[:3])
    ok_ask = ask[2] == ("TURN MONO", "Are You Sure ?") and back[:3] == page[:3]
    ok_mix = (done[2] == ("TURN MONO", "Mono") and meta_after == (base, size // 2, 0) and wrong == 0 and after[0] == before[0]
              and after[1] == base + size // 2)
    ok_leave = (nxt[:2] == (PAGES_SCREEN, (14, 14)) and prev[:3] == (MENU, (13, 14), ("DECLICK", "OFF")) and out[0] == ENTRY
                and kept == (meta_after, before[0]) and gate == [1, 0])
    first, end, loop = before[0][:3]   # the export starts the file at START POINT, as the firmware's EXPORT ALL SAMPLE always does
    ok_file = (channels == 1 and pcm == want[first:end + 1] and record is not None and record[1] == 2 * (end - first + 1)
               and record[2] == 0 and record[0] == (0, 2 * (loop - first), 2 * (end - first)))
    p = Edit(payload, flash, data=data, dsp=True)
    p.box.set_sample(USER)
    p.key("edit_prev")
    p.key("edit_prev")
    p.dev.m.uc.mem_write(TRANSPORT, struct.pack("<I", 1))   # the sequencer runs (PLAY itself does not start it on SAMPLE EDIT's screens)
    play = p.key("menu")
    p.dev.m.uc.mem_write(TRANSPORT, struct.pack("<I", 0))
    still = p.dev.read(META + (p.dev.call(0xC004E2F0, p.dev.call(SAMPLE_INDEX, p.slot()) & 0xFFFF) & 0xFFFF) * 0x45C + 9, 1)[0]
    ok_play = play[2] == ("TURN MONO", "stop PLAY") and still == 1
    return [entry("turn_mono_page_for_stereo_only", ok_loaded and ok_ring and before[1] == 1 and before[3] and not e.asserts(),
                  dict(before=before, loaded=ok_loaded, delete=delete, page=page, shot=shot, again=again)),
            entry("turn_mono_asks_and_exit_takes_it_back", ok_ask and not e.asserts(), dict(ask=ask, back=back)),
            entry("turn_mono_mixes_in_the_dsp", ok_mix and not e.asserts(),
                  dict(done=done, meta=meta_after, size=size, differing=wrong, points=(before[0], after[0]), free=(free, after[1]))),
            entry("turn_mono_kept_without_write", ok_leave and not e.asserts(), dict(next=nxt, prev=prev, exit=out, kept=kept, gate=gate)),
            entry("turn_mono_export_writes_mono", ok_file and not e.asserts(),
                  dict(channels=channels, record=record, pcm_differing=sum(1 for a, b in zip(pcm, want[first:]) if a != b))),
            entry("turn_mono_refused_while_playing", ok_play and not p.asserts(), dict(play=play, stereo=still))]


def wave_bank(frames, start, loop, end, stereo):
    """e2sSample.all with one sample on USER made of sines of 300 frames (stereo: the right channel a quarter period on, so the
    two never cross zero on the same frame), START POINT, LOOP START and END POINT at the frames given. -> (file, channels)."""
    data = bytearray(sampleset.build({USER: (hc.name_of(USER), frames, 48000, "stereo16" if stereo else "pcm16")}))
    left = [round(12000 * math.sin(2 * math.pi * (i + 7) / 300)) for i in range(frames)]
    right = [round(9000 * math.sin(2 * math.pi * (i + 82) / 300)) for i in range(frames)]
    at = data.index(b"data", struct.unpack_from("<I", data, 16 + USER * 4)[0]) + 8
    fb = 4 if stereo else 2
    for i in range(frames):
        if stereo:
            struct.pack_into("<hh", data, at + 4 * i, left[i], right[i])
        else:
            struct.pack_into("<h", data, at + 2 * i, left[i])
    esli = esli_of(data, USER)
    struct.pack_into("<III", data, esli + 40, fb * start, fb * (loop - start), fb * (end - start))
    data[esli + ONE_SHOT_AT] = 0
    data[esli + DECLICK_AT] = 0
    return bytes(data), (left, right) if stereo else (left,)


def declick_reference(words, base, fb, row, pcm):
    """The points DECLICK plays at, worked out in Python from the sample's words in the DSP (from its offset `base`): START
    POINT, END POINT, then LOOP START (staying on a start or end it sits on). Each moves to the nearest frame within
    DECLICK_WIN frames where every channel changes sign or is 0, else to the frame with the smallest |L| + |R|, the nearer
    one on a tie. -> ((start, loop from it, end from it) in DSP bytes, {point: True when it found a crossing})."""
    def frame(at):
        i = (at - base) // 2
        return words[i:i + fb // 2] + [0] * (2 - fb // 2)

    def snap(t, lo, hi):
        a, b = max(lo, t - DECLICK_WIN * fb), min(hi, t + DECLICK_WIN * fb)
        if a > b:
            return t, False
        cross, quiet = None, None
        for at in range(a, b + 1, fb):
            now, was = frame(at), frame(at - fb if at > lo else at)
            dist, level = abs(at - t), sum(abs(v) for v in now)
            if all(v == 0 or (v < 0) != (w < 0) for v, w in zip(now, was)) and (cross is None or dist < cross[0]):
                cross = (dist, at)
            if quiet is None or level < quiet[0] or (level == quiet[0] and dist < quiet[1]):
                quiet = (level, dist, at)
        return (cross[1], True) if cross else (quiet[2], False)

    s, l, e = row[0], row[0] + row[1], row[0] + row[2]
    s2, cs = snap(s, base, e)
    e2, ce = snap(e, s2, base + (pcm & ~(fb - 1)) - fb)
    l2, cl = (s2, cs) if l == s else (e2, ce) if l == e else snap(l, s2, e2)
    return (s2, l2 - s2, e2 - s2), dict(start=cs, loop=cl, end=ce)


def case_declick(payload, flash):
    """DECLICK, behind REVERSE (13 of 14). ON sets bit 0 of the play table's byte 15; a note then starts, loops and ends on
    the points of declick_reference, worked out from the sample's PCM in the DSP model: on a zero crossing for a mono sine,
    on the quietest frame for a stereo one whose channels never cross together. The stored points stay as they were, OFF
    plays them again. WRITE keeps ON, EXPORT ALL SAMPLE writes it (esli byte 53); EXIT without WRITE takes it back. For a stereo
    sample TURN MONO sits between DECLICK and DELETE (13 and 14 of 15). An
    oscillator shows "---"."""
    frames, start, loop, end = 6000, 50, 1000, 5000
    out = []
    for stereo in (False, True):
        data, _ = wave_bank(frames, start, loop, end, stereo)
        e = Edit(payload, flash, data=data, dsp=True)
        e.box.set_sample(USER)
        notes = []
        regs = e.dev.m.A
        e.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s_, d: notes.append(
            tuple(u.reg_read(getattr(regs, f"UC_ARM_REG_R{n}")) for n in (7, 6, 3, 2))), begin=NOTE_ON, end=NOTE_ON)
        index = e.dev.call(SAMPLE_INDEX, e.slot()) & 0xFFFF
        phys = e.dev.call(0xC004E2F0, index) & 0xFFFF
        row = PLAY + phys * 16
        base, pcm = struct.unpack("<II", e.dev.read(META + phys * 0x45C, 8))
        fb = 4 if stereo else 2
        words = e.dsp.samples(base, pcm // 2)
        stored = struct.unpack("<III", e.dev.read(row, 12))
        want, crossed = declick_reference(words, base, fb, stored, pcm)

        def note():
            first = len(notes)
            e.gate()
            mine = [n[1:] for n in notes[first:] if n[0] == phys]
            return mine[0] if mine else None

        raw = note()
        delete = e.key("edit_prev")
        if stereo:
            e.key("edit_prev")    # TURN MONO, 14 of 15
        page = e.key("edit_prev")
        on = (e.turn(1), e.dev.read(row + 15, 1)[0])
        moved = note()
        kept = struct.unpack("<III", e.dev.read(row, 12))
        off = (e.turn(-1), note())
        e.turn(1)
        write = e.key("write")
        e.dev.run(3)
        left = e.key("exit")      # EXIT gives part 1 its own oscillator back, as the firmware's EXIT does
        e.key("menu")             # ENTER: SAMPLE EDIT of the same sample plays it again
        after = (e.dev.read(row + 15, 1)[0], note())
        name = "stereo" if stereo else "mono"
        ok_page = (page[:3] == (MENU, (13, 15 if stereo else 14), ("DECLICK", "OFF")) and delete[1][0] == delete[1][1]
                   and on == ("ON", 1))
        ok_moved = (raw == stored and moved == want and kept == stored and off == ("OFF", stored) and want != stored
                    and list(crossed.values()) == [not stereo] * 3)
        ok_write = write[2] == ("DECLICK", "saved") and left[0] == ENTRY and after == (1, want)
        out += [entry(f"declick_{name}_page", ok_page and not e.asserts(), dict(delete=delete, page=page, on=on)),
                entry(f"declick_{name}_moves_points", ok_moved and not e.asserts(),
                      dict(raw=raw, moved=moved, want=want, crossed=crossed, kept=kept, off=off)),
                entry(f"declick_{name}_write_keeps", ok_write and not e.asserts(), dict(write=write, exit=left, after=after))]
        if stereo:
            continue
        written = e.export()
        at = esli_of(written, USER) if written else 0
        out.append(entry("declick_export_writes_byte_53", at and written[at + DECLICK_AT] == 1 and not e.asserts(),
                         dict(byte=written[at + DECLICK_AT] if at else None)))
        g = Edit(payload, flash, data=data, dsp=True)
        g.box.set_sample(USER)
        g.key("edit_prev")
        g.key("edit_prev")
        g.key("write")            # a fresh snapshot of this sample (OFF), as selecting it on SELECT SAMPLE takes one
        g.dev.run(3)
        g.turn(1)
        g.key("exit")
        g.dev.run(0.5)
        dropped = g.dev.read(row + 15, 1)[0]
        g.dev.call(SWITCH_SCREEN, ENTRY, 0)
        g.dev.run(0.5)
        g.key("menu")
        g.key("edit_prev")
        g.key("edit_prev")
        g.dev.m.uc.mem_write(g.dev.u32(MODEL) + 0x3FC, struct.pack("<I", 0))
        g.dev.run(0.3)
        plays = g.dev.read(PLAY, 1000 * 16)
        value = g.turn(1)
        out += [entry("declick_exit_without_write_drops", dropped == 0 and not g.asserts(), dict(byte=dropped)),
                entry("declick_oscillator_dashes", value == "---" and g.shown()[2] == ("DECLICK", "---")
                      and g.dev.read(PLAY, 1000 * 16) == plays and not g.asserts(), dict(value=value, shown=g.shown()))]
    return out


def case_reverse(payload, flash):
    """REVERSE, behind ONE SHOT (12 of 14, stereo 12 of 15). ON turns the sample's PCM round in the DSP frame by frame (a stereo
    frame keeps L before R; more than two blocks of the firmware's DSP read, so block pairs swap and a rest turns in the middle)
    and sets bit 1 of the play table's byte 15; the points stay. OFF gives the PCM back bit for bit. With DECLICK on, the next
    note plays the points worked out on the reversed PCM. EXIT without WRITE keeps REVERSE (the snapshot's byte follows) and takes
    the unwritten DECLICK back, EXPORT ALL
    SAMPLE writes the reversed PCM and the bit (esli byte 53). An oscillator shows "---"."""
    out = []
    for stereo, frames in ((False, 70001), (True, 40001)):
        fb = 4 if stereo else 2
        data, _ = wave_bank(frames, 0, 1000, frames - 1, stereo)
        e = Edit(payload, flash, data=data, dsp=True)
        e.box.set_sample(USER)
        notes = []
        regs = e.dev.m.A
        e.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s_, d: notes.append(
            tuple(u.reg_read(getattr(regs, f"UC_ARM_REG_R{n}")) for n in (7, 6, 3, 2))), begin=NOTE_ON, end=NOTE_ON)
        index = e.dev.call(SAMPLE_INDEX, e.slot()) & 0xFFFF
        phys = e.dev.call(0xC004E2F0, index) & 0xFFFF
        row = PLAY + phys * 16
        base, pcm = struct.unpack("<II", e.dev.read(META + phys * 0x45C, 8))
        words = e.dsp.samples(base, pcm // 2)
        per = fb // 2
        turned = [v for i in range(len(words) // per - 1, -1, -1) for v in words[i * per:(i + 1) * per]]
        stored = struct.unpack("<III", e.dev.read(row, 12))

        def note():
            first = len(notes)
            e.gate()
            mine = [n[1:] for n in notes[first:] if n[0] == phys]
            return mine[0] if mine else None

        delete = e.key("edit_prev")
        if stereo:
            e.key("edit_prev")    # TURN MONO, 14 of 15
        declick = e.key("edit_prev")
        if not stereo:
            e.turn(1)             # DECLICK on: its points follow the reversed PCM
        page = e.key("edit_prev")
        on = (e.turn(1), e.dev.read(row + 15, 1)[0], e.dev.read(0xC0345A61, 1)[0])
        now = e.dsp.samples(base, pcm // 2)
        points = struct.unpack("<III", e.dev.read(row, 12))
        played = note()
        want = declick_reference(now, base, fb, stored, pcm)[0] if not stereo else None
        kept = (e.turn(1), now == e.dsp.samples(base, pcm // 2))
        off = (e.turn(-1), e.dev.read(row + 15, 1)[0], e.dsp.samples(base, pcm // 2) == words)
        e.turn(1)
        left = e.key("exit")
        e.dev.run(0.5)
        after = (e.dev.read(row + 15, 1)[0], e.dsp.samples(base, pcm // 2) == turned)
        name = "stereo" if stereo else "mono"
        total = 15 if stereo else 14
        bit = 0 if stereo else 1
        ok_page = (page[:3] == (MENU, (12, total), ("REVERSE", "OFF")) and declick[:2] == (MENU, (13, total))
                   and delete[1] == (total, total))
        ok_on = (on == ("ON", 2 | bit, on[2]) and on[2] & 2 and now == turned and now != words and points == stored
                 and kept == ("ON", True))
        ok_declick = stereo or (played == want and want != stored)
        ok_off = off == ("OFF", bit, True)
        ok_exit = left[0] == ENTRY and after == (2, True)    # DECLICK without WRITE goes back with EXIT, REVERSE stays
        out += [entry(f"reverse_{name}_page", ok_page and not e.asserts(), dict(delete=delete, declick=declick, page=page)),
                entry(f"reverse_{name}_turns_the_pcm", ok_on and ok_declick and not e.asserts(),
                      dict(on=on, differing=sum(1 for a, b in zip(now, turned) if a != b), points=(stored, points), kept=kept,
                           played=played, want=want)),
                entry(f"reverse_{name}_off_gives_it_back", ok_off and not e.asserts(), dict(off=off)),
                entry(f"reverse_{name}_kept_without_write", ok_exit and not e.asserts(), dict(exit=left, after=after))]
        if stereo:
            continue
        written = e.export()
        at = esli_of(written, USER) if written else 0
        riff = struct.unpack_from("<I", written, 16 + USER * 4)[0] if written else 0
        dat = written.index(b"data", riff) if written else 0
        pcm_file = list(struct.unpack_from(f"<{struct.unpack_from('<I', written, dat + 4)[0] // 2}h", written, dat + 8)) if written else []
        out.append(entry("reverse_export_writes_pcm_and_bit", at and written[at + DECLICK_AT] == 2 and pcm_file == turned
                         and not e.asserts(), dict(byte=written[at + DECLICK_AT] if at else None,
                                                   differing=sum(1 for a, b in zip(pcm_file, turned) if a != b), size=len(pcm_file))))
        g = Edit(payload, flash, data=data, dsp=True)
        g.box.set_sample(USER)
        for _ in range(3):
            g.key("edit_prev")
        g.dev.m.uc.mem_write(g.dev.u32(MODEL) + 0x3FC, struct.pack("<I", 0))
        g.dev.run(0.3)
        plays = g.dev.read(PLAY, 1000 * 16)
        value = g.turn(1)
        out.append(entry("reverse_oscillator_dashes", value == "---" and g.shown()[2] == ("REVERSE", "---")
                         and g.dev.read(PLAY, 1000 * 16) == plays and not g.asserts(), dict(value=value, shown=g.shown())))
    return out


def case_factory_slot(payload, flash):
    """A card sample on a factory slot (the Sampler: 101) has the page; on Hacktribe that slot is an oscillator the loader refuses."""
    e = Edit(payload, flash, slots=(FACTORY, USER))
    reached = e.select(FACTORY)
    e.key("edit_next")
    shown = e.key("edit_next")
    value = e.turn(1)
    after = e.category(FACTORY).hex()
    if reached:
        ok = shown[2][0] == "CATEGORY" and value == text_at(payload, CATEGORY_TEXTS[3]) and after == "0300"
    else:
        ok = e.slot() == USER   # Hacktribe: slot 100 is an oscillator, SELECT SAMPLE never gets there
    return [entry("factory_slot_with_card_sample", ok and not e.asserts(), dict(reached=reached, slot=e.slot(), shown=shown, value=value, after=after))]


def case_no_sample(payload, flash):
    """Without any sample on the card the firmware does not open SAMPLE EDIT at all, as without the patch. CATEGORY's own guard
    (a slot without a sample or an oscillator shows "---", the dial changes nothing) is checked by putting an oscillator slot
    (0, SAW) into the model while the page is open: no key gets there, the guard is for whatever the firmware leaves behind."""
    empty = Edit(payload, flash, slots=())
    stays_out = empty.screen() != PAGES_SCREEN
    e = Edit(payload, flash)
    e.key("edit_next")
    e.key("edit_next")
    e.dev.m.uc.mem_write(e.dev.u32(MODEL) + 0x3FC, struct.pack("<I", 0))
    e.dev.run(0.3)
    before = e.dev.read(NAMES, 1000 * 32)
    value = e.turn(3)
    shown = e.shown()
    after = e.dev.read(NAMES, 1000 * 32)
    return [entry("no_sample_no_sample_edit", stays_out and not empty.asserts(), dict(screen=empty.screen())),
            entry("oscillator_shows_dashes", shown[2] == ("CATEGORY", "---") and value == "---" and before == after and not e.asserts(),
                  dict(shown=shown, value=value, changed=before != after))]


def case_without(payload, flash):
    """EXIT held at power-on: Korg's 10 pages, EDIT right on RENAME goes to START POINT."""
    e = Edit(payload, flash, held=mc.KILL)
    first = e.shown()
    rename = e.key("edit_next")
    start = (e.key("edit_next"), e.page())
    ok = first[:2] == (PAGES_SCREEN, (1, 10)) and rename[:2] == (PAGES_SCREEN, (2, 10)) and start[0][:2] == (PAGES_SCREEN, (3, 10)) and start[1] == 2
    return [entry("exit_held_is_stock", ok and not e.asserts(), dict(first=first, rename=rename, start=start))]


GROUPS = (case_page, case_wheel, case_export, case_sliced, case_one_shot, case_factory_slot, case_no_sample, case_without, case_turn_mono,
          case_declick, case_reverse)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own device, so they can run side by side."""
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path, nargs="+")
    p.add_argument("--only", help="comma-separated group names (case_page, ...)")
    a = p.parse_args()
    payload = a.vsb.read_bytes()[0x100:]
    if not has_hooks(payload):
        print("no CATEGORY hooks in this copy")
        return 1
    flash = load_flash(a.flash) if a.flash else None
    groups = [g for g in GROUPS if not a.only or g.__name__ in a.only.split(",")]
    result = [e for g in groups for e in g(payload, flash)]
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if all(e["ok"] for e in result) else 1


if __name__ == "__main__":
    sys.exit(main())
