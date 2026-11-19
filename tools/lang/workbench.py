# SPDX-License-Identifier: GPL-2.0-only
"""Translation workbench for the firmware's menu texts (docs/firmware-sprache.md).

Reads your own firmware image, finds the text templates the menus show (emulator run with a hook on the text function),
and writes one file per build next to each other: address, English template, font, pointer words, width, and the German
text with its width from data/lang/de/korg-<build>.json. Reports templates without a German entry and German texts
wider than their space. The English text only goes into the output folder, which is ignored by git; never commit it.

    tools/emu/.venv/bin/python tools/lang/workbench.py --vsb ORIGINAL.BIN [--out .lang-work] [--screens 8 9 14]
"""

import argparse
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
# Korg's menu texts and the effect parameter records (docs/messungen/2026-11-19-firmware-sprache.md). Sampler builds only:
# the blue Electribe keeps its texts elsewhere, measured in phase 2 of the plan.
AREAS = {"menu": (0xC00A3000, 0xC00A8000), "fx": (0xC011F000, 0xC0124000)}
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


def load_german(build):
    path = ROOT / "data" / "lang" / "de" / f"korg-{build}.json"
    return json.loads(path.read_text("utf8"))["texts"] if path.exists() else {}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path, help="your own SYSTEM.VSB or ORIGINAL.BIN")
    p.add_argument("--out", type=Path, default=ROOT / ".lang-work", help="output folder, ignored by git")
    p.add_argument("--screens", type=int, nargs="*", help="screen numbers; default 0 to 44")
    a = p.parse_args()

    payload = a.vsb.read_bytes()[HEADER:]
    if identify(payload).build == "synth":
        sys.exit("the blue Electribe keeps its texts at other addresses; not measured yet (plan phase 2.1)")
    build = build_of(payload)
    if a.screens:
        lang_shown.SCREENS = a.screens
    shown = lang_shown.shown(payload)
    found = {area: strings(payload, *span) for area, span in AREAS.items()}
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
    per_area = {area: sum(1 for r in entries if r["area"] == area) for area in AREAS}
    print(f"{build}: {len(shown)} shown texts, templates {per_area}, "
          f"{sum(len(r['pointers']) for r in entries if r['area'] == 'menu')} pointer words to menu templates")
    print(f"without German: {len(missing)}, wider than their space: {len(wide)} {' '.join(wide)}")
    print(f"written: {out} and {out.with_suffix('.tsv')}")


if __name__ == "__main__":
    main()
