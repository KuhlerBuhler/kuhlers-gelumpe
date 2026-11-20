# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the optional patch lang-de (docs/firmware-sprache.md).

check.py runs `cases` on every patched copy with the BLECH menu. With lang-de the BLECH pages are clean in German (no overlap, nothing
over the edge, labels whole), the umlauts draw, and sample pages show their German text; without it the menu reads the runtime's
English table.

    tools/emu/.venv/bin/python tools/emu/lang_cases.py cases --patched NEW.VSB [--flash dump.bin]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases as mc  # noqa: E402
from machine import load_flash  # noqa: E402
from tools.patch import script_hooks  # noqa: E402

IMAGE = 0xC0000000
BLECH_JSON = ROOT / "data" / "lang" / "de" / "blech.json"
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


GROUPS = (pages_case, texts_case)


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
