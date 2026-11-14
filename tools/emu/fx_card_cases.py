# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the collection on the card (tools/patch/fx_card.s, src/fx-collection.mjs).

check.py runs `cases_task` on every patched copy that carries the loader, red or blue (the blue's places: data/synth-map/). A good file puts its insert and master
records where the firmware's getters point and its modulation type into the table the build reads, in RAM; the flash
ends up byte for byte as after a start without the file. A missing file, a wrong checksum, the wrong build, an index
past the menu, a cut file and EXIT held at power-on leave every record as the firmware has it.

    tools/emu/.venv/bin/python tools/emu/fx_card_cases.py cases --patched NEW.VSB [--flash dump.bin] [--only N]
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import fat32  # noqa: E402
import menu_cases  # noqa: E402
import synthaddr  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

PATH_IN_IMAGE = b"SD:KORG/blechtribe/Presets/e2sFx.all"
CARD_FILE = "/KORG/blechtribe/Presets/e2sFx.all"
MAGIC = 0x41584647
RECORD, MOD_RECORD = 0x20C, 0x58
GET = {"ifx": 0xC003E738, "mfx": 0xC003E750}
COUNT = {"ifx": 0xC003EFDC, "mfx": 0xC003EFE4}
MOD_COUNT = 72
KIND = {"ifx": 1, "mfx": 2, "mod": 3}
STATE = script_hooks.CARD + 0xFE0
STATUS = {2: "loaded", 3: "no panel", 4: "EXIT held", 5: "no file", 6: "bad header", 7: "wrong build", 8: "bad entry", 9: "bad checksum", 10: "read error"}
BOOT_S = 6.0
BOOT_SYNTH_S = 10.0     # the blue's start takes longer to reach the main screen
NAME = 1                # an FX record's name is bytes 1 to 15
MOD_NAME, MOD_DEPTH = 4, 26


BUILD = {"hacktribe": 1, "stock": 2, "synth": 3}         # the header's build word, src/fx-collection.mjs BUILDS
OTHER = {1: 2, 2: 1, 3: 2}                                 # a build the loader has to refuse


def has_hooks(payload):
    return PATH_IN_IMAGE in payload


def build_of(payload):
    return "synth" if synthaddr.is_synth(payload) else identify(payload).build


def mods(payload):
    """The modulation table the build reads (FX_MODS of tools/patch/script_hooks.py), at its own address."""
    build = build_of(payload)
    return synthaddr.tr(0xC00D81EC) if build == "synth" else 0xC00D81EC if build == "stock" else 0xC019FFFC


def raw(dev, addr, n):
    """Bytes at an address the running firmware handed out or the build's own address: no translation of Sampler places."""
    return bytes(dev.m.uc.mem_read(addr, n))


def entry(kind, index, data, text=b'{"format":"gelumpe-fx"}'):
    raw = struct.pack("<BBHHH", KIND[kind], index, len(text), len(data), 0) + data + text
    return raw + b"\0" * (-len(raw) % 4)


def collection(build, entries, crc_wrong=False, cut=0):
    body = b"".join(entries)
    total = 24 + len(body)
    crc = zlib.crc32(body) ^ (1 if crc_wrong else 0)
    data = struct.pack("<IHHIIII", MAGIC, 1, len(entries), total, crc, build, 0) + body
    return data[:len(data) - cut] if cut else data


def card(files):
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    volume.write("/KORG/blechtribe/Sample/.keep", b"")
    for path, data in files.items():
        volume.write(path, data)
    volume.close()
    return SDCard(MemoryMedium(bytearray(image)))


def boot(payload, flash, files, held=0):
    menu_cases.for_build(payload)     # export() walks the menu of this build
    dev = Dev(payload, flash, held)
    dev.m.insert_card(card(files))
    dev.run(BOOT_SYNTH_S if dev.synth else BOOT_S)
    return dev


def state(dev):
    status, loaded = struct.unpack("<II", raw(dev, STATE, 8))
    return status, loaded


def records(dev, payload):
    """The records the cases touch, as the running firmware has them."""
    return {"ifx": raw(dev, dev.call(GET["ifx"], 1), RECORD), "mfx": raw(dev, dev.call(GET["mfx"], 0), RECORD),
            "ifx2": raw(dev, dev.call(GET["ifx"], 2), RECORD), "mod": raw(dev, mods(payload) + 3 * MOD_RECORD, MOD_RECORD)}


def named(record, at, width, text):
    out = bytearray(record)
    out[at:at + width] = text.encode().ljust(width, b"\0")[:width]
    return bytes(out)


def plan(payload, flash):
    """A start without the file: the firmware's records, the flash after it, and the edited records a file brings."""
    base = boot(payload, flash, {})
    before = records(base, payload)
    want = {"ifx": named(before["ifx"], NAME, 15, "FXCARD IFX"), "mfx": named(before["mfx"], NAME, 15, "FXCARD MFX"),
            "mod": bytearray(named(before["mod"], MOD_NAME, 16, "FXCARD MOD"))}
    want["mod"][MOD_DEPTH] = 99 if want["mod"][MOD_DEPTH] != 99 else 98
    want["mod"] = bytes(want["mod"])
    good = [entry("ifx", 1, want["ifx"]), entry("mfx", 0, want["mfx"]), entry("mod", 3, want["mod"])]
    return base, before, want, good


def result(name, ok, detail):
    return {"id": f"fxcard:{name}", "ok": bool(ok), "detail": str(detail)}


def case_good(payload, flash):
    base, before, want, good = plan(payload, flash)
    build = BUILD[build_of(payload)]
    dev = boot(payload, flash, {CARD_FILE: collection(build, good)})
    now = records(dev, payload)
    status, loaded = state(dev)
    same_flash = bytes(dev.m.flash.mem) == bytes(base.m.flash.mem)
    return [
        result("loads_into_ram", status == 2 and loaded == 3 and now["ifx"] == want["ifx"] and now["mfx"] == want["mfx"] and now["mod"] == want["mod"],
               f"status {STATUS.get(status, status)}, {loaded} entries; insert {now['ifx'] == want['ifx']}, master {now['mfx'] == want['mfx']}, modulation {now['mod'] == want['mod']}"),
        result("others_stay", now["ifx2"] == before["ifx2"], "the insert record the file does not name is the firmware's"),
        result("flash_untouched", same_flash, "the flash after the start is the same as after a start without the file"),
        result("no_assert", not dev.m.asserts, f"asserts {dev.m.asserts[:2]}"),
    ]


def case_refused(payload, flash):
    base, before, want, good = plan(payload, flash)
    build = BUILD[build_of(payload)]
    files = {
        "missing": ({}, 5),
        "checksum": ({CARD_FILE: collection(build, good, crc_wrong=True)}, 9),
        "build": ({CARD_FILE: collection(OTHER[build], good)}, 7),
        "index": ({CARD_FILE: collection(build, [entry("ifx", 250, want["ifx"])])}, 8),
        "cut": ({CARD_FILE: collection(build, good, cut=8)}, None),
    }
    out = []
    for name, (card_files, expect) in files.items():
        dev = boot(payload, flash, card_files)
        status, loaded = state(dev)
        now = records(dev, payload)
        unchanged = all(now[k] == before[k] for k in ("ifx", "mfx", "mod"))
        out.append(result(f"refused_{name}", unchanged and loaded == 0 and (status == expect if expect else status in (6, 8, 10)) and not dev.m.asserts,
                          f"status {STATUS.get(status, status)}, {loaded} entries, records unchanged {unchanged}"))
    return out


def case_exit(payload, flash):
    base, before, want, good = plan(payload, flash)
    build = BUILD[build_of(payload)]
    dev = boot(payload, flash, {CARD_FILE: collection(build, good)}, held=menu_cases.KILL)
    status, loaded = state(dev)
    now = records(dev, payload)
    unchanged = all(now[k] == before[k] for k in ("ifx", "mfx", "mod"))
    # the blue's start wrapper (script_start_synth.s) skips all of BLECH with EXIT held, the loader does not run and its state stays erased
    skipped = (0, 4, 0xFFFFFFFF) if build == BUILD["synth"] else (0, 4)
    return [result("exit_held", status in skipped and unchanged, f"status {STATUS.get(status, status)}, records unchanged {unchanged}")]


def case_boot_effects(payload, flash):
    """The pattern of the start set its effects before the loader ran: the loader sends them again, so the DSP plays the records
    of the file. The last transfers of the start are the ones selecting the same record on a start without the file sends."""
    import preset_cases
    from mfx_cases import DspLog, same_dsp

    class Box(preset_cases.Box):
        def __init__(self, files):
            self.dev = Dev(bytes(payload), flash, 0)
            self.dsp = DspLog(self.dev.m)
            self.dev.m.insert_card(card(files))
            self.dev.run(BOOT_SYNTH_S if self.dev.synth else BOOT_S)

    ab = lambda changes: [t for t in changes if t[0] == 0xAB]
    build = BUILD[build_of(payload)]
    base = Box({})
    n = base.count("ifx")
    out = []
    for kind, k in (("ifx", 5), ("mfx", 5)):
        dev = Box({CARD_FILE: collection(build, [entry(kind, 0, base.record(kind, k))])})
        start = ab(dev.dsp.changes())
        if kind == "ifx":
            base.goto_ifx(k - 1, n); base.dsp.clear(); base.step_ifx(1); base.dev.run(1.0)
        else:
            base.set_mfx(3); base.dev.run(.5); base.dsp.clear(); base.set_mfx(k); base.dev.run(1.0)
        tail = ab(base.dsp.changes())[-3:]
        sent = len(tail) == 3 and any(same_dsp(start[i:i + 3], tail) for i in range(len(start) - 2))
        out.append(result(f"boot_{kind}_sent", sent and state(dev.dev)[0] == 2 and not dev.dev.m.asserts,
                          f"status {STATUS.get(state(dev.dev)[0])}, the record of the file reached the DSP at the start: {sent}"))
    return out


def case_version_text(payload, flash):
    """BLECH > VERSION says behind the firmware what the start did with e2sFx.all, nothing without a file. The third row stays empty:
    the firmware draws it on the row of the value. The value row on screen holds exactly the pixels of the value alone."""
    base, before, want, good = plan(payload, flash)
    build = BUILD[build_of(payload)]
    firmware = menu_cases.BASE_NAMES[build_of(payload)]
    out = []
    for name, files, tag in (("none", {}, ""), ("loaded", {CARD_FILE: collection(build, good)}, " FX"),
                             ("build", {CARD_FILE: collection(OTHER[build], good)}, " FX fw?"),
                             ("checksum", {CARD_FILE: collection(build, good, crc_wrong=True)}, " FX bad")):
        dev = boot(payload, flash, files)
        menu_cases.goto_top(dev, menu_cases.LIST_VERSION)
        texts = menu_cases.texts_of(dev)
        crowded = menu_cases.page_overlap(dev)
        menu_cases.goto_top(dev, menu_cases.LIST_VERSION)
        extra, missing = menu_cases.value_row_leftovers(dev)
        out.append(result(f"version_{name}", texts[1:] == (firmware + tag, "") and crowded is None and not extra and not missing and not dev.m.asserts,
                          f"value and third row {texts[1:]}, want {(firmware + tag, '')}; {crowded}; {len(extra)} pixels beside the value, "
                          f"{len(missing)} of it missing"))
    return out


def export(dev):
    """DATA UTILITY, our page EXPORT ALL EFFECTS, ENTER: the value it shows after, and the collection on the card then."""
    menu_cases.INIT_PAGE = raw(dev, menu_cases.INIT_CODE, 4) != b"\xff" * 4
    menu_cases.FX_EXPORT = True
    menu_cases.goto_du(dev, menu_cases.du_pages().index("EXPORT ALL EFFECTS"))
    title = menu_cases.text(dev, menu_cases.S_TITLE)
    menu_cases.press(dev, "menu", wait=1.0)
    volume = fat32.Volume(dev.m.mmc.card.medium.data)
    try:
        written = volume.read(CARD_FILE)
    except Exception:
        written = None
    volume.close()
    return title, menu_cases.text(dev, menu_cases.S_VALUE), written


def entries_of(data):
    """(kind, index, data, text) of each entry of a collection, and whether its CRC-32 is right."""
    count, total, crc = struct.unpack_from("<HII", data, 6)
    at, out = 24, []
    for _ in range(count):
        kind, index, text, size = struct.unpack_from("<BBHH", data, at)
        out.append((kind, index, data[at + 8:at + 8 + size], data[at + 8 + size:at + 8 + size + text]))
        at += (8 + size + text + 3) & ~3
    return out, total == len(data) and crc == zlib.crc32(data[24:])


def case_export(payload, flash):
    """EXPORT ALL EFFECTS writes the records in RAM into the collection that was loaded, each text as it was, an entry without
    text too, the CRC new; the next start loads it. Without a file it makes one; a file changed since the start or one the
    start did not load stays as it is."""
    base, before, want, good = plan(payload, flash)
    build = BUILD[build_of(payload)]
    bare = named(before["ifx2"], NAME, 15, "NO TEXT")
    original = collection(build, good + [entry("ifx", 2, bare, text=b"")])
    dev = boot(payload, flash, {CARD_FILE: original})
    edited = named(want["ifx"], NAME, 15, "EXPORTED IFX")
    dev.m.uc.mem_write(dev.call(GET["ifx"], 1), edited)
    dev.m.uc.mem_write(dev.call(GET["ifx"], 2), named(bare, NAME, 15, "CHANGED"))
    title, value, written = export(dev)
    was, _ = entries_of(original)
    now, crc_ok = entries_of(written or original)
    texts = [e[3] for e in now] == [e[3] for e in was]
    datas = [e[2] for e in now] == [edited, want["mfx"], want["mod"], named(bare, NAME, 15, "CHANGED")]
    again = boot(payload, flash, {CARD_FILE: written or b""})
    status, loaded = state(again)
    out = [result("export_writes_ram_keeps_text", title == "EXPORT ALL EFFECTS" and value == "exported" and written is not None and len(written) == len(original)
                  and crc_ok and texts and datas and not dev.m.asserts,
                  f"{title!r} {value!r}, {len(written or b'')} of {len(original)} bytes, CRC {crc_ok}, texts kept {texts}, records {datas}"),
           result("export_loads_again", status == 2 and loaded == 4 and records(again, payload)["ifx"] == edited,
                  f"status {STATUS.get(status, status)}, {loaded} entries, insert 1 is the exported one: {records(again, payload)['ifx'] == edited}")]
    out += export_new(payload, flash, build)
    broken = collection(build, good, crc_wrong=True)
    refused = boot(payload, flash, {CARD_FILE: broken})
    _, value, written = export(refused)
    out.append(result("export_keeps_a_file_not_loaded", value == "bad e2sFx.all" and written == broken and not refused.m.asserts, f"{value!r}, file kept {written == broken}"))
    changed = boot(payload, flash, {CARD_FILE: original})
    changed.m.uc.mem_write(STATE + 12, b"\x5a" * 4)    # FX_WANT: the CRC the loader read; another one stands for a file written since the start
    _, value, written = export(changed)
    out.append(result("export_refuses_a_changed_file", value == "bad e2sFx.all" and written == original and not changed.m.asserts, f"{value!r}, file kept {written == original}"))
    return out


def export_new(payload, flash, build):
    """Without a file EXPORT ALL EFFECTS makes one: every insert and master preset and every modulation type as RAM has them,
    no text, the CRC right, in a Presets folder it makes; the next start loads all of it, and a second export writes into it."""
    dev = boot(payload, flash, {})
    counts = {k: min(dev.call(a), 256) for k, a in COUNT.items()}
    edited = named(raw(dev, dev.call(GET["ifx"], 1), RECORD), NAME, 15, "NEW FILE IFX")
    dev.m.uc.mem_write(dev.call(GET["ifx"], 1), edited)
    ram = [(1, i, raw(dev, dev.call(GET["ifx"], i), RECORD)) for i in range(counts["ifx"])]
    ram += [(2, i, raw(dev, dev.call(GET["mfx"], i), RECORD)) for i in range(counts["mfx"])]
    ram += [(3, i, raw(dev, mods(payload) + i * MOD_RECORD, MOD_RECORD)) for i in range(MOD_COUNT)]
    _, value, written = export(dev)
    now, crc_ok = entries_of(written) if written else ([], False)
    same = [(k, i, d) for k, i, d, _ in now] == ram and all(t == b"" for *_, t in now)
    head = written is not None and struct.unpack_from("<IHHI", written)[:2] == (MAGIC, 1) and struct.unpack_from("<I", written, 16)[0] == build
    out = [result("export_without_file_makes_one", value == "exported" and head and crc_ok and same and not dev.m.asserts,
                  f"{value!r}, {len(now)} entries ({counts['ifx']} insert, {counts['mfx']} master, {MOD_COUNT} modulation), header {head}, CRC {crc_ok}, records as RAM {same}")]
    edited2 = named(edited, NAME, 15, "SECOND EXPORT")
    dev.m.uc.mem_write(dev.call(GET["ifx"], 1), edited2)
    _, value2, written2 = export(dev)
    now2, crc2 = entries_of(written2) if written2 else ([], False)
    second = value2 == "exported" and crc2 and len(now2) == len(now) and now2[1][2] == edited2
    again = boot(payload, flash, {CARD_FILE: written2 or b""})
    status, loaded = state(again)
    out.append(result("export_new_file_exports_and_loads_again", second and status == 2 and loaded == len(ram) and records(again, payload)["ifx"] == edited2,
                      f"second export {value2!r} CRC {crc2}, start: status {STATUS.get(status, status)}, {loaded} of {len(ram)} entries"))
    return out


GROUPS = (case_good, case_refused, case_exit, case_export, case_boot_effects, case_version_text)


def group_entries(payload, flash, i):
    return GROUPS[i](payload, flash)


def cases_task(i):
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def main():
    import lifetime
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases", "load", "export"))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    p.add_argument("--file", type=Path, help="load, export: boot with this e2sFx.all on the card")
    p.add_argument("--out", type=Path, help="export: where the collection goes after EXPORT ALL EFFECTS")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    if not has_hooks(payload):
        print(json.dumps([result("loader_present", False, "the copy has no loader for e2sFx.all")], indent=1))
        return 1
    if a.what == "load":
        dev = boot(payload, flash, {CARD_FILE: a.file.read_bytes()})
        status, loaded = state(dev)
        read = lambda kind, index: raw(dev, dev.call(GET[kind], index), RECORD) if kind != "mod" else raw(dev, mods(payload) + index * MOD_RECORD, MOD_RECORD)
        names = {"ifx": 1, "mfx": 2, "mod": 3}
        data = a.file.read_bytes()
        count, at, records = struct.unpack_from("<H", data, 6)[0], 24, []
        for _ in range(count):
            kind, index, text, size = struct.unpack_from("<BBHH", data, at)
            kind = next(k for k, v in names.items() if v == kind)
            records.append({"kind": kind, "index": index, "ram": read(kind, index).hex()})
            at += (8 + size + text + 3) & ~3
        print(json.dumps({"status": STATUS.get(status, status), "loaded": loaded, "records": records, "asserts": len(dev.m.asserts)}))
        return 0
    if a.what == "export":
        dev = boot(payload, flash, {CARD_FILE: a.file.read_bytes()})
        title, value, written = export(dev)
        if written is not None:
            a.out.write_bytes(written)
        print(json.dumps({"title": title, "value": value, "written": written is not None, "asserts": len(dev.m.asserts)}))
        return 0
    entries = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
