# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the optional patch lang-de (docs/firmware-sprache.md).

check.py runs `cases` on every patched copy with the BLECH menu. With lang-de the BLECH pages are clean in German (no overlap, nothing
over the edge, labels whole), the umlauts draw, and sample pages show their German text; without it the menu reads the runtime's
English table. On Korg's own screens (0 to 44, turned and stepped) every translated text has its pointer words bent to
lang-de's copy, no English original of it is drawn, no German text runs over the edge or over another text, and no copy
of one is longer than its measured buffer; without lang-de every pointer word is the original.

    tools/emu/.venv/bin/python tools/emu/lang_cases.py cases --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import functools
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import lang_shown  # noqa: E402
import menu_cases as mc  # noqa: E402
import parallel  # noqa: E402
import synthaddr  # noqa: E402
from firmware import build_of  # noqa: E402
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

IMAGE = 0xC0000000
BLECH_JSON = ROOT / "data" / "lang" / "de" / "blech.json"
KORG_DIR = ROOT / "data" / "lang" / "de"
CHUNKS = 9                   # screen groups for the Korg screens, each a task of its own
UMLAUTS = {"Ä": "A", "Ö": "O", "Ü": "U", "ä": "a", "ö": "o", "ü": "u", "ß": "b"}


def has_page(payload):
    """True when the copy has the BLECH menu; the cases tell German and English apart themselves."""
    return mc.has_menu(payload)


def has_lang(payload):
    """True when lang-de's header (table, count, key) is in the copy."""
    return struct.unpack_from("<I", payload, script_hooks.LANG + 4 - IMAGE)[0] != 0xFFFFFFFF


def german():
    return {k: v["text"] for k, v in json.loads(BLECH_JSON.read_text("utf8"))["texts"].items() if "text" in v}


def entry(name, ok, detail):
    return {"id": f"lang:{name}", "ok": bool(ok), "detail": str(detail)}


def table_in_lang(dev):
    word = dev.u32(script_hooks.LANG_TEXTS)
    return script_hooks.LANG <= word < script_hooks.LANG_END, word


def pages_case(payload, flash=None):
    """With lang-de: every BLECH page of menu:pages_are_clean is clean in German; the Data Util line is the German one."""
    mc.for_build(payload)
    if not has_lang(payload):
        return []
    english, mc.PRESS = mc.PRESS, german()["str_press"]
    try:
        out = mc.page_cases(payload, flash)
    finally:
        mc.PRESS = english
    return [entry(c["id"].split(":", 1)[1] + "_de", c["ok"], c["detail"]) for c in out]


def draw_value(dev, value):
    """The frame with only `value` (Latin-1) on the value line of the BLECH screen."""
    widget = dev.u32(mc.screen_object(dev) + mc.MENU_WIDGET)
    scratch = script_hooks.CARD + 0xF00
    dev.m.uc.mem_write(scratch, value.encode("latin-1") + b"\0")
    dev.m.uc.mem_write(scratch + 64, b"\0")
    dev.m.uc.mem_write(widget + mc.ORIG_FLAG, b"\0")
    dev.call(mc.SET_VALUE, widget, scratch)
    dev.call(mc.SET_LINE3, widget, scratch + 64)
    dev.run(0.25)
    return mc.lit(mc.frame(dev))


def texts_case(payload, flash=None):
    """The table the menu reads, the umlauts on the value line, and three pages: German with lang-de, English without."""
    mc.for_build(payload)
    out = []
    dev = mc.boot(payload, flash)
    inside, word = table_in_lang(dev)
    de = has_lang(payload)
    out.append(entry("table", inside == de, f"LANG_TEXTS points at 0x{word:08x}, {'German' if inside else 'English'} table, lang-de {'in' if de else 'not in'} the copy"))
    texts = german()
    probes = [("list ANPASSUNG", lambda: mc.goto_top(dev, 2), "str_custom"),
              ("Data Util page 1", lambda: mc.goto_du(dev, 0), "str_export_custom"),
              ("DISPLAY page 2", lambda: mc.goto_group(dev, mc.GROUP_DISPLAY, 1), "str_bl_green")]
    shown = []
    for name, go, label in probes:
        go()
        title = mc.texts_of(dev)[0]
        shown.append((name, title, (title == texts[label]) == de))
    out.append(entry("pages_" + ("de" if de else "en"), all(ok for *_, ok in shown), shown))
    if de:
        mc.goto_du(dev, 0)
        wrong = []
        for letter, base in UMLAUTS.items():
            ink, plain = draw_value(dev, letter), draw_value(dev, base)
            if not ink or ink == plain:
                wrong.append(f"{letter}: {len(ink)} pixels, same as {base}: {ink == plain}")
        out.append(entry("umlauts_draw", not wrong, wrong or "ÄÖÜäöüß each draw, none like its base letter"))
    return out


def korg(payload):
    """The Korg texts of this build's language file: {template address: entry}."""
    build = "synth" if synthaddr.is_synth(payload) else build_of(payload)
    path = KORG_DIR / f"korg-{build}.json"
    return {int(k, 16): v for k, v in json.loads(path.read_text("utf8"))["texts"].items()} if path.exists() else {}


def word(payload, at):
    return struct.unpack_from("<I", payload, at - IMAGE)[0]


def cstring(payload, at):
    off = at - IMAGE
    return bytes(payload[off:payload.index(b"\0", off)])


def pointers_case(payload, flash=None):
    """With lang-de each pointer word of a translated text points at its German copy in lang-de's area; without it
    every pointer word of the language file is the original (its hash)."""
    texts = korg(payload)
    if not has_page(payload) or not texts:
        return []
    de, wrong = has_lang(payload), []
    for address, e in texts.items():
        for p in e.get("pointers", []):
            at = int(p["at"], 16)
            if de and "text" in e:
                target = word(payload, at)
                inside = script_hooks.LANG <= target < script_hooks.LANG_END
                if not inside or cstring(payload, target) != e["text"].encode("latin-1"):
                    wrong.append(f"{p['at']} -> 0x{target:08x} for 0x{address:08x}")
            elif hashlib.sha256(struct.pack("<I", word(payload, at))).hexdigest() != p["expect"]:
                wrong.append(f"{p['at']} is not the original word of 0x{address:08x}")
    return [entry("korg_pointers", not wrong, wrong or f"{sum(len(e.get('pointers', [])) for e in texts.values())} words, lang-de {'in' if de else 'not in'} the copy")]


def english_twin(payload, texts):
    """The copy as it would be without lang-de's Korg pointers and table: every pointer word back on its template,
    lang-de's header erased."""
    twin = bytearray(payload)
    for address, e in texts.items():
        for p in e.get("pointers", []):
            if hashlib.sha256(struct.pack("<I", address)).hexdigest() == p["expect"]:
                struct.pack_into("<I", twin, int(p["at"], 16) - IMAGE, address)
    twin[script_hooks.LANG - IMAGE:script_hooks.LANG - IMAGE + 16] = b"\xff" * 16
    return bytes(twin)


def korg_screens_case(chunk, payload, flash=None):
    """With lang-de, screens of chunk `chunk`: no German text over the edge or over another text, no English original
    of a translated text drawn, no copy of a German text longer than its buffer."""
    texts = korg(payload)
    if not has_page(payload) or not has_lang(payload) or not any("text" in e for e in texts.values()):
        return []
    mc.for_build(payload)
    german = {e["text"] for e in texts.values() if "text" in e}
    english = {cstring(payload, a).decode("latin-1"): e["text"] for a, e in texts.items() if "text" in e}
    translations = sorted(english.items(), key=lambda kv: -len(kv[0]))
    english = {en: de for en, de in english.items() if en not in german}

    def translate(text):
        for en, de in translations:
            text = text.replace(en, de)
        return text
    copied = {}
    for a, e in texts.items():
        for p in e.get("pointers", []) if "text" in e else []:
            copied[word(payload, int(p["at"], 16))] = (a, e)
    screens = list(lang_shown.SCREENS)[chunk::CHUNKS]
    problems, shown_en, over, checked, stops = [], [], [], 0, []
    for screen in screens:
        parallel.shared = {"payload": payload, "flash": flash}
        seen = lang_shown.layout_task(screen, sorted(german))
        if seen["crashed"]:
            parallel.shared = {"payload": english_twin(payload, texts), "flash": flash}
            if lang_shown.layout_task(screen, [])["crashed"]:
                stops.append(screen)
            else:
                problems.append(("crash", screen, seen["crashed"], "not without lang-de"))
        found = [tuple(p) for p in seen["problems"]]
        if any(p[0] == "overlap" for p in found):
            # Korg's own redraws overlap on some screens; an overlap the English twin shows too is not lang-de's.
            parallel.shared = {"payload": english_twin(payload, texts), "flash": flash}
            twin = lang_shown.layout_task(screen, sorted(en for en, _ in translations))
            same = {(k, s, translate(a), translate(b)) for k, s, a, b in twin["problems"]}
            found = [p for p in found if p not in same and (p[0], p[1], p[3], p[2]) not in same]
        problems += found
        shown_en += [(screen, t) for t in seen["drawn"] if t in english]
        for source, size, lr in seen["copies"]:
            if source not in copied:
                continue
            a, e = copied[source]
            checked += 1
            room = e.get("buffer")
            if room == "string" or (room is None and size - 1 <= e["length"]) or (isinstance(room, int) and size <= room):
                continue
            over.append(f"0x{a:08x} {e['text']!r}: {size} bytes to the copy at 0x{lr:08x}, buffer {room}")
    name = ", ".join(map(str, screens)) + (f" (the emulator stops on {stops} with and without lang-de)" if stops else "")
    return [entry(f"korg_screens_de_{chunk}", not problems, problems or f"screens {name}: no German text over the edge or another text"),
            entry(f"korg_text_de_{chunk}", not shown_en, shown_en or f"screens {name}: no English original of a translated text drawn"),
            entry(f"format_buffers_de_{chunk}", not over, sorted(set(over)) or f"screens {name}: {checked} copies, each fits its buffer")]


GROUPS = (pages_case, texts_case, pointers_case) + tuple(functools.partial(korg_screens_case, c) for c in range(CHUNKS))


def cases_task(i):
    """Group `i` of the cases in a worker (parallel.py)."""
    import parallel
    return GROUPS[i](parallel.shared["payload"], parallel.shared["flash"])


def cases(payload, flash=None):
    return [c for group in GROUPS for c in group(payload, flash)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd", choices=["cases"])
    p.add_argument("--patched", required=True)
    p.add_argument("--flash")
    a = p.parse_args()
    payload = Path(a.patched).read_bytes()[mc.HEADER:]
    flash = load_flash(a.flash) if a.flash else None
    out = cases(payload, flash)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    sys.exit(0 if all(c["ok"] for c in out) else 1)


if __name__ == "__main__":
    main()
