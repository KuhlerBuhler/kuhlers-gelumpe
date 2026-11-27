# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the user samples patch of the synth (tools/patch/user_samples.py, docs/messungen/2026-11-12-blau-sample-import.md).

check.py runs `cases` on every patched copy that carries the patch's hook at the end of the PCM load (Korg's synth build only). A card
with `Sample/e2sSample.all` in the firmware's folder: its WAVs land in the DSP behind the factory waves, value for value (stereo averaged),
as new instruments with their name, loop and pitch, in the [User] group behind [Audio In]; the encoder reaches them from SAW and a pad
plays the sample's start address. A sample larger than the room left, or not 16-bit PCM, is skipped and counted. With EXIT held at
power-on, or without the file, nothing is loaded and the list ends at Korg's last oscillator.

    tools/emu/.venv/bin/python tools/emu/user_samples_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import user_samples as spec  # noqa: E402
import synth_probe as sp  # noqa: E402
from machine import load_flash  # noqa: E402
import fat32  # noqa: E402
import lifetime  # noqa: E402
import machine  # noqa: E402
import menu_cases as mc  # noqa: E402
import parallel  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

IMAGE = 0xC0000000
KILL = 0x2000                    # EXIT held at power-on
SLOTS = (500, 501, 502, 503)     # where the cases put their samples in the file


def has_hooks(payload):
    """True when the end of the PCM load calls into the patch's code."""
    if len(payload) < spec.HOOK - IMAGE + 4:
        return False
    word = struct.unpack_from("<I", payload, spec.HOOK - IMAGE)[0]
    return word >> 24 == 0xEB and spec.CODE_AT <= spec.HOOK + 8 + ((word & 0xFFFFFF) << 2) < spec.CODE_END


def entry(name, ok, detail):
    return {"id": f"usersamples:{name}", "ok": bool(ok), "detail": str(detail)}


# ---- the card
def wav(values, rate, channels=1, esli=None, bits=16, claim=None):
    """A RIFF/WAVE with 16-bit values (interleaved for stereo); `esli` = (name, start, loop, end, one_shot) adds the korg chunk;
    `claim` makes the data chunk say more bytes than follow."""
    data = b"".join(struct.pack("<h", v) for v in values)
    size = len(data) if claim is None else claim
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * 2 * channels, 2 * channels, bits)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", size) + data + (b"\0" if len(data) & 1 else b"")
    if esli is not None:
        record = bytearray(1172)
        name, start, loop, end, one_shot = esli
        record[2:2 + len(name)] = name.encode()
        struct.pack_into("<III", record, 40, start, loop, end)
        record[52] = one_shot
        struct.pack_into("<I", record, 72, rate)
        chunk = b"esli" + struct.pack("<I", len(record)) + bytes(record)
        body += b"korg" + struct.pack("<I", len(chunk)) + chunk
    return b"RIFF" + struct.pack("<I", len(body)) + body


def sample_file(wavs):
    """e2sSample.all with the WAVs in SLOTS."""
    out = bytearray(4096)
    out[:16] = b"e2s sample all\x1a\0"
    for w, slot in zip(wavs, SLOTS):
        struct.pack_into("<I", out, 16 + 4 * slot, len(out))
        out += w
    return bytes(out)


def card(data):
    """A card with the file in both folders the firmware can use (the plain one and BLECH's)."""
    img = fat32.format_image(128 * 1024 * 1024)
    vol = fat32.Volume(img)
    if data is not None:
        for folder in ("electribe", "blechtribe"):
            vol.write(f"/KORG/{folder}/Sample/e2sSample.all", data)
    vol.close()
    return SDCard(MemoryMedium(img))


SINE = [int(9000 * math.sin(2 * math.pi * i / 100)) for i in range(4000)]
LEFT = [int(5000 * math.sin(2 * math.pi * i / 50)) for i in range(3000)]
RIGHT = [int(3000 * math.sin(2 * math.pi * i / 30)) for i in range(3000)]
STEREO = [v for pair in zip(LEFT, RIGHT) for v in pair]


def mono(values):
    return b"".join(struct.pack("<h", v) for v in values)


def averaged(left, right):
    return b"".join(struct.pack("<h", (a + b) >> 1) for a, b in zip(left, right))


# ---- a booted device
def boot(payload, flash, data, held=0, seconds=4.0):
    if flash is None:
        flash = sp.blank_synth_flash(machine, sp.build_bank(sp.synthetic_waves()))
    probe = sp.Probe(payload, flash, card=card(data))
    probe.m.held = held
    probe.run_to(seconds)
    return probe


def state(p):
    keys = ("loaded", "rejected", "next", "last", "br", "status")
    return dict(zip(keys, (p.u32(spec.STATE + 4 * i) for i in range(len(keys)))))


def counts(p):
    return [p.u32(sp.RAM[k]) for k in ("count_instruments", "count_mspr", "count_msrl", "count_smpr")]


def record(p, index):
    raw = p.read(spec.OSC_TABLE + index * spec.OSC_STRIDE, spec.OSC_STRIDE)
    return {"name": raw[:16].split(b"\0")[0].decode("latin-1"), "group": raw[16], "wave": struct.unpack_from("<H", raw, 18)[0]}


def case_load(payload, flash):
    """Two samples: mono with its esli record, stereo without one."""
    files = [wav(SINE, 44100, 1, ("SINE A", 0, 1000, 7998, 0)), wav(STEREO, 22050, 2)]
    plain = boot(payload, flash, None)
    p = boot(payload, flash, sample_file(files))
    base, s = counts(plain), state(p)
    first = record(p, spec.OSC_COUNT)
    second = record(p, spec.OSC_COUNT + 1)
    after = record(p, spec.OSC_COUNT + 2)
    a = p.chain(first["wave"])
    b = p.chain(second["wave"])
    pcm_a = p.dsp_bytes(a["smpr"][0], len(SINE) * 2)
    pcm_b = p.dsp_bytes(b["smpr"][0], len(LEFT) * 2)
    word = lambda rate: round(256 * (spec.ROOT_KEY + 12 * math.log2(48000 / rate)))   # noqa: E731
    return [
        entry("status", s["status"] == spec.ST_OK and s["loaded"] == 2 and s["rejected"] == 0, s),
        entry("tables", counts(p) == [c + 2 for c in base], f"counts {base} -> {counts(p)}"),
        entry("list_end", s["last"] == spec.OSC_LAST + 2, f"the list ends at {s['last']:#x}"),
        entry("records", first["name"] == "SINE A" and second["name"] == "USER" and first["group"] == second["group"] == spec.USER_GROUP
              and after["name"] == "SAW", f"{first} {second}, the next record {after}"),
        entry("pcm_mono", pcm_a == mono(SINE), f"{len(SINE)} values at {a['smpr'][0]:#x}: {'equal' if pcm_a == mono(SINE) else pcm_a and pcm_a[:16].hex()}"),
        entry("pcm_stereo", pcm_b == averaged(LEFT, RIGHT), f"{len(LEFT)} averaged values at {b['smpr'][0]:#x}"),
        entry("behind_factory", a["smpr"][0] >= 0x365AE0 and a["smpr"][0] % 32 == 0 and b["smpr"][0] >= a["smpr"][0] + len(SINE) * 2 + 64
              and b["smpr"][0] % 32 == 0, f"starts {a['smpr'][0]:#x}, {b['smpr'][0]:#x}"),
        entry("loop", a["smpr"][1:3] == [1000, 7998] and not a["smpr"][3] & 0x10000 and b["smpr"][1:3] == [5998, 5998] and b["smpr"][3] & 0x10000,
              f"esli loop 1000, end 7998 looped: {a['smpr']}; no esli, one-shot over all: {b['smpr']}"),
        entry("pitch", abs(a["pitch_word"] - word(44100)) <= 1 and abs(b["pitch_word"] - word(22050)) <= 1,
              f"{a['pitch_word']} for 44.1 kHz (exact {word(44100)}), {b['pitch_word']} for 22.05 kHz (exact {word(22050)})"),
    ]


def case_play(payload, flash):
    """The encoder walks from SAW over [Audio In] into [User]; a pad plays the sample's start."""
    p = boot(payload, flash, sample_file([wav(SINE, 48000, 1, ("PLAY", 0, 0, 7998, 0))]))
    want = p.chain(record(p, spec.OSC_COUNT)["wave"])["smpr"][0]
    p.select_osc(spec.OSC_COUNT)
    played = p.press_pad()["call"]
    # one more step wraps to the first oscillator, one back to the user sample again
    return [entry("pad_plays_sample", played is not None and played["start"] == want,
                  f"the voice starts at {played and hex(played['start'])}, the sample lies at {want:#x}")]


def case_reject(payload, flash):
    """Too large for the room and an 8-bit WAV are skipped; the sample behind them still loads."""
    files = [wav(SINE[:64], 48000, claim=0x1000000), wav(SINE[:64], 48000, bits=8), wav(SINE, 48000, 1, ("AFTER", 0, 0, 7998, 0))]
    p = boot(payload, flash, sample_file(files))
    s = state(p)
    first = record(p, spec.OSC_COUNT)
    return [entry("skips", s["status"] == spec.ST_OK and s["loaded"] == 1 and s["rejected"] == 2 and first["name"] == "AFTER",
                  f"{s}, record {spec.OSC_COUNT}: {first}")]


def case_off(payload, flash):
    """EXIT held at power-on, or no file: nothing loads, the tables and the list stay Korg's."""
    plain = boot(payload, flash, None)
    held = boot(payload, flash, sample_file([wav(SINE, 48000)]), held=KILL)
    out = []
    for name, p, status in (("kill_switch", held, spec.ST_EXIT), ("no_file", plain, spec.ST_NOFILE)):
        s = state(p)
        out.append(entry(name, s["status"] == status and s["loaded"] == 0 and s["last"] == spec.OSC_LAST
                         and record(p, spec.OSC_COUNT)["name"] == "SAW" and not p.m.asserts,
                         f"{s}, counts {counts(p)}, record {spec.OSC_COUNT}: {record(p, spec.OSC_COUNT)}"))
    out.append(entry("same_tables", counts(held) == counts(plain), f"{counts(held)} with EXIT held, {counts(plain)} without a file"))
    return out


def case_menu(payload, flash):
    """BLECH > USER SAMPLES, in front of VERSION: what the start loaded and left out; a bad file says so; without a file there is no
    row (menu_cases checks that list). Only where the copy has the BLECH menu."""
    if not mc.has_menu(payload):
        return []
    mc.for_build(payload)
    out = []
    files = [wav(SINE[:64], 48000, bits=8), wav(SINE, 48000, 1, ("A", 0, 0, 7998, 0)), wav(SINE, 48000, 1, ("B", 0, 0, 7998, 0))]
    for name, data, want in (("menu_counts", sample_file(files), "2 OK 1 SKIPPED"), ("menu_all_loaded", sample_file(files[1:]), "2 LOADED"),
                             ("menu_bad_file", b"not a sample file" + bytes(4096), "bad sample file")):
        dev = Dev(payload, machine=boot(payload, flash, data).m)
        mc.goto_top(dev, mc.LIST_VERSION)
        row = (mc.state(dev, mc.S_PAGE), mc.counter(dev), mc.texts_of(dev))
        mc.press(dev, "menu", wait=0.4)
        mc.press(dev, "write", wait=0.4)
        dev.turn(1, wait=0.2)
        after = (mc.state(dev, mc.S_LEVEL), mc.state(dev, mc.S_PAGE), mc.texts_of(dev))
        mc.goto_top(dev, mc.LIST_VERSION + 1)
        version = mc.texts_of(dev)[:2]
        ok = (row == (mc.LIST_VERSION, (mc.LIST_VERSION, mc.LIST_COUNT + 1), ("USER SAMPLES", want, "")) and after == (1, mc.LIST_VERSION, row[2])
              and version == mc.version_texts(payload) and not dev.m.asserts)
        out.append(entry(name, ok, f"row {row}, after ENTER, WRITE and the dial {after}, the next row {version}"))
    same = script_hooks.runtime_profile("synth").actions["US_STATE"] == spec.STATE
    out.append(entry("menu_state_address", same, f"the runtime reads {script_hooks.runtime_profile('synth').actions['US_STATE']:#x}, the patch writes {spec.STATE:#x}"))
    api = script_hooks.runtime_profile("synth").actions["US_API"]
    out.append(entry("menu_api_address", api == spec.CODE2, f"the runtime calls {api:#x}, the patch's vector is at {spec.CODE2:#x}"))
    return out


PATTERN_PTR = 0xC033E6A4         # -> the pattern object (the synth has it at the Sampler's address)
PART_OSC = 0x80C                 # the object + this: part 1's oscillator, u16 (the pattern block starts at +4)


def saved_with_user_osc(payload, flash, data):
    """Part 1 on the first [User] oscillator, WRITE twice: the flash after the pattern is stored, and where the sample lies."""
    p = boot(payload, flash, data)
    p.select_osc(spec.OSC_COUNT)
    p.run(2.0)       # the OSC value popup closes first; WRITE while it shows stores nothing
    chosen = p.u16(p.u32(PATTERN_PTR) + PART_OSC)
    start = p.chain(record(p, spec.OSC_COUNT)["wave"])["smpr"][0]
    dev = Dev(payload, machine=p.m)
    mc.press(dev, "write", wait=0.6)
    mc.press(dev, "write", wait=3.0)
    return bytes(p.m.flash.mem), chosen, start


def restarted(payload, saved, data, held=0):
    """A new start on the stored flash: part 1's oscillator, what a pad plays, and the oscillator one encoder step on."""
    p = sp.Probe(payload, saved, card=card(data))
    p.m.held = held
    p.run_to(4.0)
    osc = p.u16(p.u32(PATTERN_PTR) + PART_OSC)
    played = p.press_pad()["call"]
    name = record(p, osc)["name"]
    p.encoder_osc(1)
    p.run(1.0)
    return p, osc, played, name, p.u16(p.u32(PATTERN_PTR) + PART_OSC)


def case_pattern(payload, flash):
    """A pattern with a [User] oscillator, written and started again: with the same card it plays the same sample; without the
    file, or with EXIT held at power-on, the stored number stays and the part plays SAW (a free record), nothing breaks."""
    data = sample_file([wav(SINE, 48000, 1, ("PATTERN", 0, 0, 7998, 0))])
    saved, chosen, start = saved_with_user_osc(payload, flash, data)
    out = [entry("pattern_stores_user_osc", chosen == spec.OSC_COUNT, f"part 1 on {chosen} before WRITE")]
    p, osc, played, name, step = restarted(payload, saved, data)
    out.append(entry("pattern_same_sample_after_restart", osc == spec.OSC_COUNT and played is not None and played["start"] == start
                     and name == "PATTERN" and not p.m.asserts,
                     f"part 1 on {osc} ({name}), the voice starts at {played and hex(played['start'])}, the sample at {start:#x}"))
    for label, data_again, held in (("no_file", None, 0), ("exit", data, KILL)):
        p, osc, played, name, step = restarted(payload, saved, data_again, held)
        out.append(entry(f"pattern_{label}_plays_saw", osc == spec.OSC_COUNT and name == "SAW" and played is None and step <= spec.OSC_LAST
                         and not p.m.asserts,
                         f"part 1 on {osc} ({name}), PCM voice {played}, one encoder step on: {step}"))
    return out


# ---- IMPORT SAMPLE and SAMPLE EDIT at run time (the vector at spec.CODE2; the BLECH menu calls it)
SCRATCH = 0xC013FA00             # free image RAM behind the patch's run time areas: the path the cases pass
US_IMPORT, US_SET, US_STORE = spec.CODE2, spec.CODE2 + 4, spec.CODE2 + 8


def wav_raw(channels, rate, bits, frames, tag=1):
    """A WAV whose fmt chunk comes behind a LIST chunk, with `frames` frames of a formula; -> (file, the 16-bit mono values the
    import must make of it: 24 bit keeps the upper 16, stereo is (left + right) >> 1)."""
    width = bits // 8
    data, want = bytearray(), []
    for i in range(frames):
        chans = [int(7000 * math.sin(2 * math.pi * i / (40 + 13 * c))) * (256 if bits == 24 else 1) for c in range(channels)]
        for v in chans:
            data += (v & ((1 << bits) - 1)).to_bytes(width, "little")
        top = [v >> 8 if bits == 24 else v for v in chans]
        want.append(top[0] if channels == 1 else (top[0] + top[1]) >> 1)
    fmt = struct.pack("<HHIIHH", tag, channels, rate, rate * width * channels, width * channels, bits)
    body = (b"WAVE" + b"LIST" + struct.pack("<I", 6) + b"INFOab" + b"fmt " + struct.pack("<I", 16) + fmt
            + b"data" + struct.pack("<I", len(data)) + bytes(data))
    return b"RIFF" + struct.pack("<I", len(body)) + body, mono(want)


def card_image(files):
    """{path: bytes} -> the card image (a bytearray the emulator writes into)."""
    img = fat32.format_image(128 * 1024 * 1024)
    vol = fat32.Volume(img)
    for path, data in files.items():
        vol.write(path, data)
    vol.close()
    return img


def boot_image(payload, flash, img, seconds=4.0):
    if flash is None:
        flash = sp.blank_synth_flash(machine, sp.build_bank(sp.synthetic_waves()))
    probe = sp.Probe(payload, flash, card=SDCard(MemoryMedium(img)))
    probe.run_to(seconds)
    return probe


def sample_dir(p):
    """The folder of the sample file as the loader wrote its path (PATH), with the slash."""
    path = p.read(spec.PATH, 0x100).split(b"\0")[0].decode("latin-1")
    return path[:path.rindex("/") + 1]


def import_wav(p, name, k):
    path = (sample_dir(p) + name).encode() + b"\0"
    p.uc.mem_write(SCRATCH, path)
    return p.call(US_IMPORT, SCRATCH, k, limit_s=30.0)


def card_file(img, path):
    vol = fat32.Volume(img)
    try:
        return vol.read(path)
    except Exception:
        return None


def last_dsp(p, address, length):
    """What the last write that covers `address` put there (a sample written again in its place)."""
    for start, data in reversed(p.dsp_segments()):
        if start <= address and address + length <= start + len(data):
            return data[address - start:address - start + length]
    return None


def entry_of(data, slot):
    """(head offset, fmt, data bytes, esli record) of a slot of a sample file."""
    off = struct.unpack_from("<I", data, 16 + 4 * slot)[0]
    if not off:
        return None
    fmt = struct.unpack_from("<HHIIHH", data, off + 20)
    size = struct.unpack_from("<I", data, off + 40)[0]
    pcm = data[off + 44:off + 44 + size]
    esli = data[off + 44 + size + 16:off + 44 + size + 16 + 1172]
    return {"off": off, "fmt": fmt, "pcm": pcm, "esli": esli, "riff": struct.unpack_from("<I", data, off + 4)[0], "tag": data[off + 44 + size:off + 44 + size + 4]}


def user(p, k):
    raw = p.read(spec.UT + (k - 1) * 64, 64)
    slot, ch = struct.unpack_from("<HB", raw, 0)
    ix = struct.unpack_from("<4H", raw, 4)
    entry_, esli, size, base, start, loop, end, rate, flags = struct.unpack_from("<9I", raw, 12)
    return {"slot": slot, "ch": ch, "ix": ix, "entry": entry_, "bytes": size, "base": base, "start": start, "loop": loop, "end": end,
            "rate": rate, "flags": flags}


SAMPLE_PATH = "/KORG/blechtribe/Sample/"


def case_import(payload, flash):
    """IMPORT SAMPLE: a 24-bit stereo WAV (fmt behind a LIST chunk) becomes [User] 2 behind the one the start loaded: 16-bit mono in
    the file behind the old samples, the head last, the values in the DSP behind the first sample, its record and name in the list;
    a new start loads both. Then a mono WAV over [User] 1: same slot, new place in the file and the DSP, the list stays 2 long."""
    first = wav(SINE, 48000, 1, ("FIRST", 0, 0, 7998, 0))
    src, want = wav_raw(2, 32000, 24, 1500)
    over, want_over = wav_raw(1, 44100, 16, 900)
    img = card_image({SAMPLE_PATH + "e2sSample.all": sample_file([first]), SAMPLE_PATH + "Stereo24.wav": src,
                      SAMPLE_PATH + "OVER.WAV": over})
    p = boot_image(payload, flash, img)
    old_size = len(card_file(img, SAMPLE_PATH + "e2sSample.all"))
    result = import_wav(p, "Stereo24.wav", 2)
    s, rec = state(p), record(p, spec.OSC_COUNT + 1)
    chain = p.chain(rec["wave"])
    in_dsp = last_dsp(p, chain["smpr"][0], len(want))
    data = card_file(img, SAMPLE_PATH + "e2sSample.all")
    e = entry_of(data, 501)
    played = (p.select_osc(spec.OSC_COUNT + 1), p.press_pad()["call"])[1]
    out = [
        entry("import_result", result == spec.E_OK and s["loaded"] == 2 and s["last"] == spec.OSC_LAST + 2,
              f"result {result}, state {s}"),
        entry("import_record", rec["name"] == "Stereo24" and rec["group"] == spec.USER_GROUP, rec),
        entry("import_dsp", in_dsp == want and chain["smpr"][1:3] == [len(want) - 2] * 2 and chain["smpr"][3] & spec.ONE_SHOT,
              f"{len(want)} bytes at {chain['smpr'][0]:#x}: {'equal' if in_dsp == want else in_dsp and in_dsp[:16].hex()}, smpr {chain['smpr']}"),
        entry("import_file", e is not None and e["off"] == old_size and e["fmt"] == (1, 1, 32000, 64000, 2, 16) and e["pcm"] == want
              and e["tag"] == b"korg" and e["esli"][2:10] == b"Stereo24" and struct.unpack_from("<I", e["esli"], 48)[0] == len(want) - 2
              and e["riff"] + 8 == len(data) - old_size,
              f"entry {e and (e['off'], e['fmt'], e['riff'], e['tag'], e['esli'][:18])}, file {old_size} -> {len(data)}"),
        entry("import_plays", played is not None and played["start"] == chain["smpr"][0], f"voice {played}"),
    ]
    again = boot_image(payload, flash, bytearray(img))
    rec2 = record(again, spec.OSC_COUNT + 1)
    out.append(entry("import_after_restart", state(again)["loaded"] == 2 and rec2["name"] == "Stereo24"
                     and again.dsp_bytes(again.chain(rec2["wave"])["smpr"][0], len(want)) == want, f"{state(again)}, {rec2}"))
    before = user(p, 1)
    result = import_wav(p, "OVER.WAV", 1)
    after, rec1 = user(p, 1), record(p, spec.OSC_COUNT)
    chain1 = p.chain(rec1["wave"])
    data = card_file(img, SAMPLE_PATH + "e2sSample.all")
    e = entry_of(data, 500)
    out.append(entry("import_replace", result == spec.E_OK and state(p)["loaded"] == 2 and rec1["name"] == "OVER"
                     and after["slot"] == 500 and after["ix"] == before["ix"] and after["base"] > before["base"]
                     and last_dsp(p, chain1["smpr"][0], len(want_over)) == want_over and e["pcm"] == want_over and e["off"] > old_size,
                     f"result {result}, before {before}, after {after}, record {rec1}"))
    errors = {"k_too_far": import_wav(p, "OVER.WAV", 4), "no_file": import_wav(p, "MISSING.WAV", 3)}
    out.append(entry("import_refused", errors == {"k_too_far": spec.E_K, "no_file": spec.E_SRC} and state(p)["loaded"] == 2,
                     f"{errors}, {state(p)}"))
    return out


def case_import_new_file(payload, flash):
    """IMPORT SAMPLE on a card without the sample file and without the folder Sample: both are made, the sample plays as [User] 1;
    a WAV of 8 bits is refused and leaves nothing."""
    src, want = wav_raw(1, 48000, 16, 700)
    img = card_image({"/KORG/blechtribe/Media/IMPORT.wav": src, "/KORG/blechtribe/Media/EIGHT.wav": wav(SINE[:64], 48000, bits=8)})
    p = boot_image(payload, flash, img)
    folder = sample_dir(p)
    p.uc.mem_write(SCRATCH, (folder[:-len("Sample/")] + "Media/EIGHT.wav").encode() + b"\0")
    eight = p.call(US_IMPORT, SCRATCH, 1, limit_s=30.0)
    p.uc.mem_write(SCRATCH, (folder[:-len("Sample/")] + "Media/IMPORT.wav").encode() + b"\0")
    result = p.call(US_IMPORT, SCRATCH, 1, limit_s=30.0)
    data = card_file(img, SAMPLE_PATH + "e2sSample.all")
    e = data and entry_of(data, 500)
    rec = record(p, spec.OSC_COUNT)
    return [entry("new_file", eight == spec.E_FMT and result == spec.E_OK and state(p)["loaded"] == 1 and rec["name"] == "IMPORT"
                  and data is not None and data[:16] == b"e2s sample all\x1a\0" and e and e["off"] == 4096 and e["pcm"] == want,
                  f"8 bit: {eight}, import {result}, {state(p)}, record {rec}, file {data and len(data)}")]


def case_edit(payload, flash):
    """SAMPLE EDIT: START and TUNE act at once on the tables and reach the file only with the store, a new start keeps them;
    REVERSE and PLAY LEVEL store at once and write the values again in their place, reversed or times 4 held at 16 bits."""
    loud = [min(32767, max(-32768, 3 * v)) for v in SINE]
    img = card_image({SAMPLE_PATH + "e2sSample.all": sample_file([wav(loud, 48000, 1, ("EDIT", 0, 1000, 7998, 0))])})
    p = boot_image(payload, flash, img)
    rec = record(p, spec.OSC_COUNT)
    u = user(p, 1)
    base_pitch = p.chain(rec["wave"])["pitch_word"]
    results = [p.call(US_SET, 1, spec.F_START, 200), p.call(US_SET, 1, spec.F_TUNE, 12)]
    live = p.chain(rec["wave"])
    file_before = entry_of(card_file(img, SAMPLE_PATH + "e2sSample.all"), 500)["esli"]
    results.append(p.call(US_STORE, 1, limit_s=20.0))
    stored = entry_of(card_file(img, SAMPLE_PATH + "e2sSample.all"), 500)["esli"]
    out = [entry("edit_live", results == [0, 0, 0] and live["smpr"][:3] == [u["base"] + 200, 800, 7798]
                 and live["pitch_word"] == base_pitch + (12 << spec.TUNE_SHIFT), f"results {results}, chain {live}, base {u['base']:#x}"),
           entry("edit_store", struct.unpack_from("<I", file_before, 40)[0] == 0 and struct.unpack_from("<I", stored, 40)[0] == 200
                 and stored[77] == 12, f"start {struct.unpack_from('<I', stored, 40)[0]}, tune {stored[77]}")]
    again = boot_image(payload, flash, bytearray(img))
    c = again.chain(record(again, spec.OSC_COUNT)["wave"])
    out.append(entry("edit_after_restart", c["smpr"][1:3] == [800, 7798] and c["pitch_word"] == base_pitch + (12 << spec.TUNE_SHIFT),
                     f"chain {c}"))
    reverse = p.call(US_SET, 1, spec.F_REVERSE, 1, limit_s=30.0)
    rev = last_dsp(p, u["base"], len(loud) * 2)
    want_rev = mono(loud[::-1])
    flag = entry_of(card_file(img, SAMPLE_PATH + "e2sSample.all"), 500)["esli"][54]
    c = p.chain(rec["wave"])
    out.append(entry("edit_reverse", reverse == 0 and rev == want_rev and flag & 1 and c["smpr"][0] == u["base"] + 200 and state(p)["loaded"] == 1,
                     f"result {reverse}, {'reversed' if rev == want_rev else rev and rev[:16].hex()}, esli[54] {flag}, chain {c}"))
    rev_boot = boot_image(payload, flash, bytearray(img))
    rb = rev_boot.dsp_bytes(user(rev_boot, 1)["base"], len(loud) * 2)
    out.append(entry("edit_reverse_after_restart", rb == want_rev, "reversed" if rb == want_rev else rb and rb[:16].hex()))
    level = [p.call(US_SET, 1, spec.F_REVERSE, 0, limit_s=30.0), p.call(US_SET, 1, spec.F_LEVEL, 1, limit_s=30.0)]
    got = last_dsp(p, u["base"], len(loud) * 2)
    want_level = mono([min(32767, max(-32768, 4 * v)) for v in loud])
    out.append(entry("edit_level", level == [0, 0] and got == want_level, f"results {level}, {'x4 held' if got == want_level else got and got[:16].hex()}"))
    return out


def case_import_menu(payload, flash):
    """DATA UTILITY > IMPORT SAMPLE, the blue's last page there: the firmware's file browser lists the .wav files of the Sample
    folder, ENTER picks one and asks for the number, the dial walks [User] 1 up to one past the last (an existing one shows its
    name, a new one "(new)"), ENTER imports and says so; EXIT on the number goes back to the list. Without a .wav file the page
    says so and ENTER changes nothing."""
    if not mc.has_menu(payload):
        return []
    mc.for_build(payload)
    mc.INIT_PAGE = payload[mc.INIT_CODE - IMAGE:mc.INIT_CODE - IMAGE + 4] != b"\xff" * 4     # as mc.boot() sets it
    if not mc.US_PAGE:
        return [entry("import_menu_page", False, "no IMPORT SAMPLE page in a copy with the user samples")]
    first = wav(SINE, 48000, 1, ("FIRST", 0, 0, 7998, 0))
    src, want = wav_raw(1, 44100, 16, 1200)
    img = card_image({SAMPLE_PATH + "e2sSample.all": sample_file([first]), SAMPLE_PATH + "Kick.wav": src,
                      SAMPLE_PATH + "notes.txt": b"x"})
    p = boot_image(payload, flash, img)
    dev = Dev(payload, machine=p.m)
    page = mc.du_pages().index("IMPORT SAMPLE")
    mc.goto_du(dev, page)
    listed = mc.texts_of(dev)
    mc.press(dev, "menu", wait=0.6)
    target = mc.texts_of(dev)
    dev.turn(-1, wait=0.3)
    existing = mc.texts_of(dev)
    dev.turn(-1, wait=0.3)
    floor = mc.texts_of(dev)
    dev.turn(3, wait=0.3)
    ceiling = mc.texts_of(dev)
    mc.press(dev, "exit", wait=0.6)
    back = (mc.state(dev, mc.S_LEVEL), mc.texts_of(dev))
    mc.press(dev, "menu", wait=0.6)
    mc.press(dev, "menu", wait=3.0)
    done = mc.texts_of(dev)
    s, rec = state(p), record(p, spec.OSC_COUNT + 1)
    e = entry_of(card_file(img, SAMPLE_PATH + "e2sSample.all"), 501)
    out = [
        entry("import_menu_lists_wav", listed[:2] == ("IMPORT SAMPLE", "Kick.wav") and not dev.m.asserts, listed),
        entry("import_menu_number", target == ("IMPORT SAMPLE", "[User] 2", "(new)") and existing == ("IMPORT SAMPLE", "[User] 1", "FIRST")
              and floor == existing and ceiling == target and not dev.m.asserts, f"{target}, {existing}, at 1 {floor}, up {ceiling}"),
        entry("import_menu_exit_to_list", back == (mc.LEVEL_DU, listed), back),
        entry("import_menu_imports", done[:2] == ("IMPORT SAMPLE", "imported") and s["loaded"] == 2 and rec["name"] == "Kick"
              and e is not None and e["pcm"] == want and not dev.m.asserts, f"{done}, state {s}, record {rec}, file entry {e is not None}"),
    ]
    mc.press(dev, "menu", wait=0.6)
    again = mc.texts_of(dev)
    out.append(entry("import_menu_next_number", again == ("IMPORT SAMPLE", "[User] 3", "(new)"), again))
    bare_img = card_image({SAMPLE_PATH + "e2sSample.all": sample_file([first])})
    bare = Dev(payload, machine=boot_image(payload, flash, bare_img).m)
    mc.goto_du(bare, page)
    empty = mc.texts_of(bare)
    mc.press(bare, "menu", wait=0.6)
    after = (mc.texts_of(bare), mc.state(bare, mc.S_LEVEL))
    out.append(entry("import_menu_no_file", empty[:2] == ("IMPORT SAMPLE", "no .wav file") and after == (("IMPORT SAMPLE", "no .wav file", ""), mc.LEVEL_DU)
                     and card_file(bare_img, SAMPLE_PATH + "e2sSample.all") == sample_file([first]) and not bare.m.asserts, f"{empty}, ENTER {after}"))
    return out


def case_edit_menu(payload, flash):
    """DATA UTILITY > SAMPLE EDIT, behind IMPORT SAMPLE: ENTER opens its eight pages (counter n/8, the tab says Sample) on SELECT
    SAMPLE; the dial picks the [User] sample, EDIT walks START POINT, END POINT, LOOP START, SAMPLE TUNE, PLAY LEVEL, ONE SHOT and
    REVERSE (the red's order) and wraps. The points play at once and stay in order, TUNE stops at -63, ONE SHOT keeps the loop
    point and is stored at once, REVERSE turns the values at once; EXIT writes the points and TUNE into the file and goes back to
    the page, a new start has them. Without a [User] sample ENTER says so."""
    if not mc.has_menu(payload):
        return []
    mc.for_build(payload)
    mc.INIT_PAGE = payload[mc.INIT_CODE - IMAGE:mc.INIT_CODE - IMAGE + 4] != b"\xff" * 4     # as mc.boot() sets it
    if not mc.US_PAGE:
        return [entry("edit_menu_page", False, "no SAMPLE EDIT page in a copy with the user samples")]
    loud = SINE[:4000]
    files = [wav(loud, 48000, 1, ("FIRST", 0, 0, 7998, 0)), wav(SINE[:2000], 48000, 1, ("SECOND", 0, 0, 3998, 0))]
    img = card_image({SAMPLE_PATH + "e2sSample.all": sample_file(files)})
    p = boot_image(payload, flash, img)
    dev = Dev(payload, machine=p.m)
    page = mc.du_pages().index("SAMPLE EDIT")
    mc.goto_du(dev, page)
    start_page = mc.texts_of(dev)
    mc.press(dev, "menu", wait=0.6)
    select = (mc.texts_of(dev), mc.counter(dev), mc.tab(dev), mc.state(dev, mc.S_LEVEL))
    picks = []
    for step in (1, 1, -1):
        dev.turn(step)
        picks.append(mc.texts_of(dev)[1:])
    walk = []
    for _ in range(7):
        mc.press(dev, "edit_next", wait=0.4)
        walk.append((mc.counter(dev)[0], mc.texts_of(dev)[:2]))
    mc.press(dev, "edit_next", wait=0.4)
    wrapped = (mc.counter(dev)[0], mc.texts_of(dev)[0])
    mc.press(dev, "edit_next", wait=0.4)
    dev.turn(1)
    dev.turn(3)
    moved = mc.texts_of(dev)[1]
    u = user(p, 1)
    rec = record(p, spec.OSC_COUNT)
    live = p.chain(rec["wave"])["smpr"][0]
    for _ in range(2):
        mc.press(dev, "edit_next", wait=0.4)
    loop = mc.texts_of(dev)[1]
    mc.press(dev, "edit_next", wait=0.4)
    dev.turn(5)
    tune_up = mc.texts_of(dev)[1]
    dev.turn(-80)
    tune_floor = mc.texts_of(dev)[1]
    for _ in range(2):
        mc.press(dev, "edit_next", wait=0.4)
    loop_before = user(p, 1)["loop"]
    dev.turn(1, wait=3.0)
    smpr = p.chain(rec["wave"])["smpr"]
    one_shot = (mc.texts_of(dev)[:2], user(p, 1)["flags"] >> 24, user(p, 1)["loop"] == loop_before,
                entry_of(card_file(img, SAMPLE_PATH + "e2sSample.all"), 500)["esli"][52], smpr[1] == smpr[2], bool(smpr[3] & spec.ONE_SHOT))
    mc.press(dev, "edit_next", wait=0.4)
    dev.turn(1, wait=3.0)
    reverse = (mc.texts_of(dev)[1], user(p, 1)["flags"] & 0xFF)
    rev = last_dsp(p, u["base"], len(loud) * 2)
    mc.press(dev, "exit", wait=3.0)
    back = (mc.state(dev, mc.S_LEVEL), mc.texts_of(dev))
    esli = entry_of(card_file(img, SAMPLE_PATH + "e2sSample.all"), 500)["esli"]
    stored = (struct.unpack_from("<I", esli, 40)[0], struct.unpack_from("b", esli, 77)[0], esli[54] & 1)
    out = [
        entry("edit_menu_opens", start_page == ("SAMPLE EDIT", "", mc.PRESS)
              and select == (("SELECT SAMPLE", "FIRST", "[User] 1"), (0, 8), "Sample", 10) and not dev.m.asserts, f"{start_page}, {select}"),
        entry("edit_menu_select", picks == [("SECOND", "[User] 2"), ("SECOND", "[User] 2"), ("FIRST", "[User] 1")], picks),
        entry("edit_menu_pages", [w[0] for w in walk] == list(range(1, 8)) and [w[1][0] for w in walk]
              == ["START POINT", "END POINT", "LOOP START", "SAMPLE TUNE", "PLAY LEVEL", "ONE SHOT", "REVERSE"]
              and [w[1][1] for w in walk] == ["0", "3999", "0", "0", "+0dB", "OFF", "OFF"] and wrapped == (0, "SELECT SAMPLE"), f"{walk}, wrap {wrapped}"),
        entry("edit_menu_start_live", moved == "10" and u["start"] == 20 and live == u["base"] + 20 and loop == "10",
              f"START {moved}, record {u['start']}, voice start {live:#x} (base {u['base']:#x}), LOOP START {loop}"),
        entry("edit_menu_tune", tune_up == "5" and tune_floor == "-63", f"{tune_up}, {tune_floor}"),
        entry("edit_menu_one_shot", one_shot == (("ONE SHOT", "ON"), 1, True, 1, True, True), one_shot),
        entry("edit_menu_reverse", reverse == ("ON", 1) and rev == mono(loud[::-1]), f"{reverse}, {'reversed' if rev == mono(loud[::-1]) else rev and rev[:16].hex()}"),
        entry("edit_menu_exit_stores", back == (mc.LEVEL_DU, ("SAMPLE EDIT", "", mc.PRESS)) and stored == (20, -63, 1) and not dev.m.asserts,
              f"{back}, file start {stored[0]}, tune {stored[1]}, reverse {stored[2]}"),
    ]
    again = boot_image(payload, flash, bytearray(img))
    a = user(again, 1)
    out.append(entry("edit_menu_after_restart", a["start"] == 20 and again.chain(record(again, spec.OSC_COUNT)["wave"])["smpr"][0] == a["base"] + 20,
                     f"record {a}"))
    bare = Dev(payload, machine=boot_image(payload, flash, card_image({})).m)
    mc.goto_du(bare, page)
    mc.press(bare, "menu", wait=0.6)
    none = (mc.state(bare, mc.S_LEVEL), mc.texts_of(bare)[:2])
    out.append(entry("edit_menu_no_sample", none == (mc.LEVEL_DU, ("SAMPLE EDIT", "no user sample")) and not bare.m.asserts, none))
    return out


GROUPS = (case_load, case_play, case_reject, case_off, case_menu, case_pattern, case_import, case_import_new_file, case_edit,
          case_import_menu, case_edit_menu)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own devices, so they can run side by side."""
    try:
        return GROUPS[i](payload, flash)
    except Exception as e:   # a case that breaks is a red entry, not a lost run
        return [entry(GROUPS[i].__name__, False, f"{type(e).__name__}: {e}")]


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases",))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    entries = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
