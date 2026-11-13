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
    import fat32
    from sdcard import MemoryMedium, SDCard
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
        import machine
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
    import menu_cases as mc
    from splash_cases import Dev
    from tools.patch import script_hooks
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
    return out


GROUPS = (case_load, case_play, case_reject, case_off, case_menu)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own devices, so they can run side by side."""
    try:
        return GROUPS[i](payload, flash)
    except Exception as e:   # a case that breaks is a red entry, not a lost run
        return [entry(GROUPS[i].__name__, False, f"{type(e).__name__}: {e}")]


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
