# SPDX-License-Identifier: GPL-2.0-only
"""Translation workbench for the firmware's menu texts (docs/firmware-sprache.md).

Reads your own firmware image, finds the text templates the menus show (emulator run with a hook on the text function),
and writes one file per build next to each other: address, English template, font, pointer words, width, and the German
text with its width from data/lang/de/korg-<build>.json. Reports templates without a German entry and German texts
wider than their space. The English text only goes into the output folder, which is ignored by git; never commit it.

With --update, it also fills in the facts of every entry in data/lang/de/korg-<build>.json: the fonts it is drawn in,
the SHA-256 of the old text with its NUL, its length, and every pointer word with the SHA-256 of the old word. Entries
of the Hacktribe file that this build has under the same text are carried over with their buffer, so a text is translated
once. The data file gets addresses and hashes only, never the English text.

    tools/emu/.venv/bin/python tools/lang/workbench.py --vsb ORIGINAL.BIN [--out .lang-work] [--screens 8 9 14] [--update]
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "emu"))

import lang_shown  # noqa: E402
from firmware import build_of, identify  # noqa: E402

RAM = 0xC0000000
HEADER = 0x100
# Korg's menu texts and the effect parameter records (docs/messungen/2026-11-19-firmware-sprache.md). The blue
# Electribe keeps its menu texts lower (string density per 4 KiB page, measured on Korg's blue 2.02); its effect
# records are not located yet.
AREAS = {"menu": (0xC00A3000, 0xC00A8000), "fx": (0xC011F000, 0xC0124000)}
AREAS_SYNTH = {"menu": (0xC008E000, 0xC0093000)}
PLACEHOLDER = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[hlL]?[diouxXcsfeEgG%]")
MIN_PART = 3
# For a width estimate before the glyphs exist, an umlaut counts as its base letter and ß as b.
BASE_LETTER = str.maketrans({"Ä": "A", "Ö": "O", "Ü": "U", "ä": "a", "ö": "o", "ü": "u", "ß": "b"})


def strings(payload, start, end):
    """{address: text} of the NUL-terminated printable runs in [start, end)."""
    out = {}
    raw = payload[start - RAM:end - RAM]
    for m in re.finditer(rb"[\x20-\x7e]{2,}\x00", raw):
        out[start + m.start()] = m.group()[:-1].decode("ascii")
    return out


def pointers(payload, targets):
    """{address: [word address]}: the aligned words of the image that hold an address in `targets`."""
    found = {}
    for off in range(0, len(payload) - 3, 4):
        word = struct.unpack_from("<I", payload, off)[0]
        if word in targets:
            found.setdefault(word, []).append(RAM + off)
    return found


def parts(template):
    return [p for p in PLACEHOLDER.split(template) if len(p.strip()) >= MIN_PART]


def templates(found, shown):
    """[(address, area, template, fonts)] of the templates whose parts all appear in a shown text."""
    out = []
    for area, texts in found.items():
        for address, template in sorted(texts.items()):
            ps = parts(template)
            if not ps:
                continue
            fonts = set()
            for p in ps:
                hits = {font for text, font in shown if p in text}
                if not hits:
                    break
                fonts |= hits
            else:
                out.append((address, area, template, sorted(fonts)))
    return out


def data_path(build):
    return ROOT / "data" / "lang" / "de" / f"korg-{build}.json"


def load_german(build):
    path = data_path(build)
    return json.loads(path.read_text("utf8"))["texts"] if path.exists() else {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text_bytes(payload, address):
    """The NUL-terminated text at `address`, with its NUL."""
    off = address - RAM
    return bytes(payload[off:payload.index(b"\0", off) + 1])


def update_data(payload, build, areas, shown_fonts):
    """Fills in fonts, expect, length and pointers of the entries in korg-<build>.json; returns (file data, notes)."""
    path = data_path(build)
    data = json.loads(path.read_text("utf8"))
    texts = data["texts"]
    found = {}
    for span in areas.values():
        for address in strings(payload, *span):
            found.setdefault(sha(text_bytes(payload, address)), address)
    notes = []
    if build != "hacktribe":
        for key, entry in load_german("hacktribe").items():
            address = found.get(entry.get("expect"))
            if address is None:
                notes.append(f"{key}: not in this build")
                continue
            mine = texts.setdefault(f"0x{address:08x}", {})
            for k in ("text", "keep", "glossar", "buffer"):
                if k in entry:
                    mine[k] = entry[k]
                else:
                    mine.pop(k, None)
    keys = {int(k, 16): k for k in texts}
    ptrs = pointers(payload, set(keys))
    for address, key in sorted(keys.items()):
        entry = texts[key]
        raw = text_bytes(payload, address)
        entry["expect"] = sha(raw)
        entry["length"] = len(raw) - 1
        fonts = shown_fonts.get(address) or entry.get("fonts")
        if not fonts:
            notes.append(f"{key}: not drawn on the screens the tool shows, no fonts")
        entry["fonts"] = fonts or []
        entry.pop("font", None)
        entry["pointers"] = [{"at": f"0x{w:08x}", "expect": sha(struct.pack("<I", address))} for w in ptrs.get(address, [])]
        if not entry["pointers"]:
            notes.append(f"{key}: no pointer word")
    data["texts"] = dict(sorted(texts.items()))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf8")
    return notes


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path, help="your own SYSTEM.VSB or ORIGINAL.BIN")
    p.add_argument("--out", type=Path, default=ROOT / ".lang-work", help="output folder, ignored by git")
    p.add_argument("--screens", type=int, nargs="*", help="screen numbers; default 0 to 44")
    p.add_argument("--update", action="store_true", help="fill in the facts of data/lang/de/korg-<build>.json")
    a = p.parse_args()

    payload = a.vsb.read_bytes()[HEADER:]
    synth = identify(payload).build == "synth"
    build = "synth" if synth else build_of(payload)
    areas = AREAS_SYNTH if synth else AREAS
    if a.screens:
        lang_shown.SCREENS = a.screens
    shown, crashed = lang_shown.shown(payload)
    for screen, error in sorted(crashed.items()):
        print(f"screen {screen} not shown, the emulator stopped: {error}")
    found = {area: strings(payload, *span) for area, span in areas.items()}
    rows = templates(found, shown)
    ptrs = pointers(payload, {address for address, *_ in rows})
    german = load_german(build)

    measure = []
    for address, _, template, fonts in rows:
        bare = PLACEHOLDER.sub("", template)
        de = german.get(f"0x{address:08x}", {}).get("text")
        for font in fonts:
            measure.append((bare, font))
            if de is not None:
                measure.append((PLACEHOLDER.sub("", de).translate(BASE_LETTER), font))
    widths = dict(zip(measure, lang_shown.widths(payload, measure))) if measure else {}

    entries, missing, wide = [], [], []
    for address, area, template, fonts in rows:
        key = f"0x{address:08x}"
        entry = german.get(key, {})
        de = entry.get("text")
        bare = PLACEHOLDER.sub("", template)
        row = {"address": key, "area": area, "en": template, "fonts": fonts,
               "pointers": [f"0x{w:08x}" for w in ptrs.get(address, [])],
               "width": {str(f): widths[(bare, f)] for f in fonts},
               "de": de, "keep": entry.get("keep"), "space": entry.get("space")}
        if de is not None:
            row["widthDe"] = {str(f): widths[(PLACEHOLDER.sub("", de).translate(BASE_LETTER), f)] for f in fonts}
            if row["space"] is not None and max(row["widthDe"].values()) > row["space"]:
                wide.append(key)
        elif not entry.get("keep") and area == "menu":
            missing.append(key)
        entries.append(row)

    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / f"korg-{build}.json"
    out.write_text(json.dumps({"build": build, "shownTexts": len(shown), "templates": entries}, ensure_ascii=False, indent=1), "utf8")
    with (a.out / f"korg-{build}.tsv").open("w", encoding="utf8") as f:
        f.write("address\tarea\tfonts\tpointers\twidth\ten\tde\twidthDe\tspace\n")
        for r in entries:
            f.write("\t".join([r["address"], r["area"], ",".join(map(str, r["fonts"])), str(len(r["pointers"])),
                               ",".join(map(str, r["width"].values())), r["en"], r["de"] or "",
                               ",".join(map(str, r.get("widthDe", {}).values())), str(r["space"] or "")]) + "\n")
    per_area = {area: sum(1 for r in entries if r["area"] == area) for area in areas}
    print(f"{build}: {len(shown)} shown texts, templates {per_area}, "
          f"{sum(len(r['pointers']) for r in entries if r['area'] == 'menu')} pointer words to menu templates")
    print(f"without German: {len(missing)}, wider than their space: {len(wide)} {' '.join(wide)}")
    print(f"written: {out} and {out.with_suffix('.tsv')}")
    if a.update:
        notes = update_data(payload, build, areas, {address: fonts for address, _, _, fonts in rows})
        print(f"updated {data_path(build).relative_to(ROOT)}" + "".join(f"\n  {n}" for n in notes))


if __name__ == "__main__":
    main()
