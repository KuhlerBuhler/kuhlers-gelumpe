# SPDX-License-Identifier: GPL-2.0-only
"""Builds a 16 MiB flash image for the emulator that carries a PCM bank made from the blue Electribe 2's own waves
(WAV files in a zip, one per oscillator entry) and checks in the emulator that the synth firmware takes it.

The image is local data: the zip and the firmware are the user's own Korg files, the image is Korg data. It is written
outside the repository and never into it (the tool refuses a path below the repository). Nothing of it is kept here.

    tools/emu/.venv/bin/python tools/emu/synth_pcm_flash.py --zip "samples.zip" --vsb SYSTEM.VSB [--out FILE] [--no-verify]

What is derived from the files and what is not (docs/messungen/2026-10-15-synth-pcm-flash.md):

  numbering   file name "N name group.wav": N is the 1-based place in the oscillator table of the firmware (name checked), the
              table gives the wave id, the instrument is the wave id minus 0x32. Entries below 0x32 are waves the DSP makes itself
              and get no instrument. A wave id nothing uses (a gap) gets a silent filler instrument, so that the numbering holds.
  audio       the WAVs are 24-bit, mono, 44100 Hz. The bank holds 12-bit values: one gain for all (the loudest sample peak becomes
              2047, so the levels between the waves stay), rounded. The rate stays 44100: the firmware adds the 44.1 to 48 kHz
              step to the pitch word itself.
  not in a WAV  loop points, root key and key zones are not in these files (no smpl chunk). Every wave is a one-shot (the
              firmware's own form: loop start equal to the end, flag bit 16), plays from one zone over the whole keyboard and
              carries the pitch word 0x4800 that the bank format shows in the factory data (an assumption about the root key).
  size        the raw block format (mode 7) is the only one this repository can write; the factory bank also uses the packed modes
              0 to 4, whose encoder is not here. In raw blocks the waves are about 0.9 per cent too much for 8 MiB, so the longest
              waves lose their last samples (with a short fade), as much as is needed and no more. `--strict` fails instead.
"""

import argparse
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import synth_probe as sp  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
USER_MARK_AT = 0x220000                 # tools/emu/machine.py USER_MARK
USER_MARK = b"KORGelec2USR"             # what the synth's firmware looks for there (docs/messungen/2026-10-15-blaue-electribe.md)
DEFAULT_OUT = Path.home() / "Desktop" / "electribe-flash" / "blue-pcm-from-wavs.bin"
FILE = re.compile(r"(?:.*/)?(\d+) (.*)\.wav$", re.I)
PEAK = 2047                             # the largest 12-bit value
ROOT_WORD = 0x4800                      # the pitch word of the factory data (a wave at its root key plays 1:1 at the file's rate)
FILLER = ("(free)", [0] * 32)
LONG = 60000                            # waves longer than this (values) give up their tails when the bank is too big
FADE = 1024
OVERHEAD = 0x8000                       # room for the heads and the tables (72 bytes per instrument) when the fit is computed


class BankError(Exception):
    pass


def parse_wav(data):
    """(rate, channels, values) of a PCM WAV with 16 or 24 bits, stereo averaged to mono; anything else is refused."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise BankError("not a RIFF WAVE file")
    pos, fmt, body = 12, None, None
    while pos + 8 <= len(data):
        tag, size = struct.unpack_from("<4sI", data, pos)
        if tag == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", data, pos + 8)
        elif tag == b"data":
            body = data[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)
    if fmt is None or body is None:
        raise BankError("no fmt or data chunk")
    tag, channels, rate, _, _, bits = fmt
    if tag != 1 or bits not in (16, 24) or channels not in (1, 2):
        raise BankError(f"format {tag}, {channels} channels, {bits} bits: only PCM 16 or 24 bit, mono or stereo")
    width = bits // 8
    frame = width * channels
    out = []
    for at in range(0, len(body) - frame + 1, frame):
        ch = [int.from_bytes(body[at + c * width:at + (c + 1) * width], "little", signed=True) for c in range(channels)]
        out.append(sum(ch) // channels)
    return rate, bits, out


def quantise(values, bits, gain):
    """Values of the WAV as signed 12-bit numbers: `gain` is 2047 divided by the loudest peak of all waves, in WAV units."""
    return [max(-PEAK - 1, min(PEAK, round(v * gain))) for v in values]


def trim_zero_tail(values, keep=32):
    end = len(values)
    while end > keep and values[end - 1] == 0:
        end -= 1
    return values[:end]


def fade_out(values, cut):
    """`values` without its last `cut` samples, its new end faded over FADE samples."""
    out = values[:len(values) - cut]
    n = min(FADE, len(out))
    for i in range(n):
        out[len(out) - n + i] = round(out[len(out) - n + i] * (n - 1 - i) / n)
    return out


def raw_bytes(count):
    """Size of a raw stream of `count` values: a two byte head per block of BLOCK_VALUES, 12 bits per value."""
    blocks, rest = divmod(count, sp.BLOCK_VALUES)
    return blocks * (2 + sp.BLOCK_VALUES * 12 // 8) + ((2 + (rest * 12 + 7) // 8) if rest else 0)


def fit(waves, strict=False):
    """The waves, shortened where the raw stream would not fit the bank. Returns (waves, report of what was cut)."""
    total = sum(len(v) for _, v in waves)
    room = sp.BANK_SIZE - OVERHEAD
    if raw_bytes(total) <= room:
        return waves, []
    over = raw_bytes(total) - room
    if strict:
        raise BankError(f"the waves need {raw_bytes(total)} bytes in raw blocks, the bank has room for about {room}")
    need = -(-over * 8 // 12)                       # values to take away, rounded up
    long_ones = [i for i, (_, v) in enumerate(waves) if len(v) > LONG]
    weight = sum(len(waves[i][1]) for i in long_ones)
    out, report, left = list(waves), [], need
    for i in long_ones:
        cut = min(left, -(-need * len(waves[i][1]) // weight))
        left -= cut
        name, v = waves[i]
        out[i] = (name, fade_out(v, cut))
        report.append({"instrument": i, "name": name, "values": len(v), "cut": cut})
    if left > 0:
        raise BankError(f"cannot make the waves fit, {left} values too many")
    return out, report


def read_zip(path, table):
    """Waves by instrument from the zip, read in place. Returns (waves, files, skipped DSP entries, gaps)."""
    z = zipfile.ZipFile(path)
    by_instrument, files, dsp_entries = {}, {}, 0
    for info in z.infolist():
        m = FILE.match(info.filename)
        if info.is_dir() or not m:
            continue
        n = int(m.group(1))
        if not 1 <= n <= len(table):
            raise BankError(f"{info.filename}: number {n} is not an oscillator")
        entry = table[n - 1]
        if not m.group(2).startswith(entry["name"]):
            raise BankError(f"{info.filename}: the firmware calls oscillator {n} {entry['name']!r}")
        if entry["wave"] < sp.PCM_FIRST_WAVE:
            dsp_entries += 1
            continue
        rate, bits, values = parse_wav(z.read(info))
        if rate != 44100:
            raise BankError(f"{info.filename}: {rate} Hz, the bank format here is 44100 Hz")
        instrument = entry["wave"] - sp.PCM_FIRST_WAVE
        if instrument in by_instrument:
            raise BankError(f"{info.filename}: wave {entry['wave']} is already taken")
        by_instrument[instrument] = (entry["name"], bits, values)
        files[n] = instrument
    return by_instrument, files, dsp_entries


def make_waves(by_instrument):
    peak = max(max(abs(v) for v in values) for _, _, values in by_instrument.values())
    bits = {b for _, b, _ in by_instrument.values()}
    if len(bits) != 1:
        raise BankError("the files have different bit depths, one gain would not hold")
    gain = PEAK / peak
    top = max(by_instrument)
    waves, gaps = [], []
    for i in range(top + 1):
        if i in by_instrument:
            name, b, values = by_instrument[i]
            waves.append((name, trim_zero_tail(quantise(values, b, gain))))
        else:
            gaps.append(i)
            waves.append(FILLER)
    return waves, gaps, gain, peak


def flash_image(bank):
    flash = bytearray(b"\xff" * sp.FLASH_SIZE)
    flash[USER_MARK_AT:USER_MARK_AT + 16] = USER_MARK + bytes(16 - len(USER_MARK))
    flash[sp.BANK_FLASH:sp.BANK_FLASH + sp.BANK_SIZE] = bank
    return bytes(flash)


def wave_bytes(values):
    return b"".join(struct.pack("<H", (v << 4) & 0xFFFF) for v in values)


# ---- the check in the emulator ---------------------------------------------------------------------------
def verify(vsb, flash, waves, table, files, seconds=14.0, voices=(324, 310, 399)):
    """Boot the firmware on the image and compare what it reads and sends: the PCM load, the tables, the DSP memory, the
    oscillators by number and, for a few, a voice. Everything it returns was measured in the emulator."""
    import machine
    if bytes(machine.blank_flash(USER_MARK)[USER_MARK_AT:USER_MARK_AT + 16]) != flash[USER_MARK_AT:USER_MARK_AT + 16]:
        raise BankError("the user-data mark is not the one machine.blank_flash writes")
    payload = sp.load_payload(vsb)
    probe = sp.Probe(payload, flash)
    loaded = probe.run_to_pc(sp.FUNCS["pcm_loaded"], seconds)
    accepted = probe.reg(6) if loaded else None
    load_ms = round(probe.m.time_ns / 1e6, 1)
    if loaded:
        probe.leave()
    probe.run_to(seconds)
    m = probe.m
    segs = probe.dsp_segments()
    expected = sp.expected_dsp(waves)
    got = dict(segs).get(sp.DSP_BASE, b"")
    counts = probe.tables()["counts"]
    report = {"build": m.profile.build, "screen": m.screen(), "booted_ms": m.boot_ms, "asserts": m.asserts,
              "pcm_load": {"reached": loaded, "r6": accepted, "at_ms": load_ms},
              "flash_reads": {"count": len(probe.flash_reads), "first_ms": probe.flash_reads[0]["ms"] if probe.flash_reads else None,
                              "bytes": sum(r["bytes"] for r in probe.flash_reads)},
              "tables": counts,
              "dsp": {"transactions": sum(1 for t in probe.tx if t["cmd"] == 0xAB and t["address"] < 0xFF000000),
                      "segments": [{"start": hex(s), "end": hex(s + len(d)), "bytes": len(d)} for s, d in segs],
                      "equals_the_values_made_from_the_wavs": got == expected, "expected_bytes": len(expected),
                      "writes_below_the_wave_base": [hex(s) for s, _ in segs if s < sp.DSP_BASE]}}
    # oscillators by number: the firmware's own table in RAM, its chain of tables, and the DSP bytes at the sample's start
    checked, wrong, names = 0, [], 0
    for index in range(sp.OSC_COUNT):
        rec = probe.read(sp.OSC_BASE + index * sp.OSC_STRIDE, sp.OSC_STRIDE)
        wave = struct.unpack_from("<H", rec, 0x12)[0]
        if wave < sp.PCM_FIRST_WAVE:
            continue
        chain = probe.chain(wave)
        start = chain["smpr"][0]                      # the firmware keeps the DSP address of the wave in its SMPR row (stream offset + 0x365B00)
        values = waves[wave - sp.PCM_FIRST_WAVE][1]
        end = chain["smpr"][2] + 2
        ok = end == 2 * len(values) and chain["pitch_word"] == ROOT_WORD + sp.PITCH_ADDED_AT_LOAD
        ok = ok and probe.dsp_bytes(start, min(64, 2 * len(values))) == wave_bytes(values)[:min(64, 2 * len(values))]
        ok = ok and probe.dsp_bytes(start + 2 * len(values) - 32, 32) == wave_bytes(values)[-32:]
        checked += 1
        if not ok:
            wrong.append({"oscillator": index + 1, "name": rec[:16].split(b"\0")[0].decode("latin1"), "wave": wave})
        if files.get(index + 1) == wave - sp.PCM_FIRST_WAVE:
            names += 1
    report["oscillators"] = {"pcm_entries_checked": checked, "files_matched_to_an_entry": names, "wrong": wrong[:10], "wrong_count": len(wrong)}
    # a few by name and number, through the panel: select the oscillator, press a pad, read what the voice sends
    voice_report = []
    current = sp.OSC_SAW                    # a new pattern starts with SAW; select_osc counts from there
    for index in voices:
        rec = probe.read(sp.OSC_BASE + index * sp.OSC_STRIDE, sp.OSC_STRIDE)
        wave = struct.unpack_from("<H", rec, 0x12)[0]
        name = rec[:16].split(b"\0")[0].decode("latin1")
        probe.select_osc(sp.OSC_SAW + index - current)
        current = index
        note = probe.press_pad()
        call = note["call"]
        chain = probe.chain(call["wave"]) if call and call["wave"] >= sp.PCM_FIRST_WAVE else None
        values = waves[wave - sp.PCM_FIRST_WAVE][1] if wave >= sp.PCM_FIRST_WAVE else None
        dsp = probe.dsp_bytes(call["start"], 32) if call else None
        voice_report.append({"oscillator": index + 1, "name": name, "wave_in_table": wave, "wave_sent_to_dsp": call["wave"] if call else None,
                             "start_sent": hex(call["start"]) if call else None,
                             "start_equals_the_chain": bool(chain) and call["start"] == chain["smpr"][0],
                             "dsp_holds_the_wave_there": values is not None and dsp == wave_bytes(values)[:32],
                             "loop_length": call["loop_length"] if call else None})
    report["voices"] = voice_report
    report["asserts_after_the_voices"] = probe.m.asserts
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--zip", required=True, type=Path, help="the zip with the WAVs, read in place")
    p.add_argument("--vsb", required=True, type=Path, help="the synth's SYSTEM.VSB (the oscillator table gives the numbering)")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--strict", action="store_true", help="fail when the waves do not fit the bank in raw blocks")
    p.add_argument("--no-verify", action="store_true")
    a = p.parse_args()
    out = a.out.expanduser().resolve()
    if ROOT in out.parents or out == ROOT:
        raise SystemExit("the image is Korg data: write it outside the repository")
    payload = sp.load_payload(a.vsb)
    if not sp.check_osc(payload):
        raise SystemExit("this is not the synth's 2.02 image: the oscillator table is not where it was measured")
    table = sp.osc_table(payload)
    try:
        by_instrument, files, dsp_entries = read_zip(a.zip, table)
        waves, gaps, gain, peak = make_waves(by_instrument)
        waves, cut = fit(waves, a.strict)
        bank = sp.build_bank(waves, pitch_word=ROOT_WORD)
    except (BankError, ValueError) as error:
        raise SystemExit(f"stopped: {error}")
    flash = flash_image(bank)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(flash)
    info = {"image": "written", "files_used": len(files), "dsp_entries_without_a_wave_in_the_bank": dsp_entries,
            "instruments": len(waves), "filler_instruments": gaps, "values": sum(len(v) for _, v in waves),
            "gain_in_wav_units": gain, "loudest_peak": peak, "shortened": cut, "bank": sp.parse_bank(bank)["sum16"]}
    print(json.dumps(info, indent=1))
    if not a.no_verify:
        print(json.dumps(verify(a.vsb, flash, waves, table, files), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
