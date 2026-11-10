"""Emulator cases of the object tree (API 10, data/script/objects.mjs): a plugin sets the INTENSITY of the display light
through its path to 0 and back, the backlight pins go dark and light again; a value outside the range is clamped and
counted; a stored value outside the range is repaired at start.

API 17, one case per leaf of the other pages of CUSTOMIZATION and FEATURES: a plugin sets the leaf, the page of the menu BLECH
then shows the new value (and the leaf reads back what was set); PAD COLOR and SELECT COLOR swap where a write would make them
equal; korg.menu.blech.write() writes the settings file, and a restart reads the written values back.

    python3 tools/emu/objects_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import node_json  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

INTENSITY = "korg.menu.blech.customizations.display.intensity"
BLECH = "korg.menu.blech."
CUSTOM = BLECH + "customizations."

# (name, path below korg.menu.blech., the value the plugin sets). Each differs from the factory value.
SETS = [
    ("bl_red", "customizations.display.red", 15), ("bl_green", "customizations.display.green", 6), ("bl_blue", "customizations.display.blue", 0),
    ("invert", "customizations.display.invert", 0),
    ("led_mode", "customizations.led.mode", 1),
    ("led_red", "customizations.led.red", 0), ("led_green", "customizations.led.green", 11), ("led_blue", "customizations.led.blue", 15),
    ("m_still", "customizations.led.meter.still", 9), ("m_low", "customizations.led.meter.low", 4),
    ("m_mid", "customizations.led.meter.mid", 7), ("m_loud", "customizations.led.meter.loud", 8),
    ("pad", "customizations.padColor.part", 0), ("select", "customizations.padColor.select", 2), ("overlap", "customizations.padColor.overlap", 3),
    ("light", "customizations.powerSave.displayLight", 7), ("dim", "customizations.powerSave.ledDimming", 3),
    ("mfx2", "features.mfx2", 0), ("confirm", "features.patternConfirm", 0), ("tap", "features.tapMotion", 2), ("assist", "features.noteAssist", 0),
    ("last", "features.lastPattern", 0), ("stereo", "features.stereo1Pad", 0), ("init", "features.initPattern", 5),
]
SET_FRAME, READ_FRAME, SWAP_FRAME, WRITE_FRAME = 5, 12, 40, 60
# the plugin sets every leaf, reads every leaf back into a variable, swaps the pad colours with a write of PAD COLOR to SELECT COLOR's colour,
# and asks for the settings to be written
PAGES = "let n = 0;\n" + "".join(f"let g_{k} = -1;\n" for k, _, _ in SETS) + "let swapped_pad = -1; let swapped_select = -1;\n" + f"""korg.onEvent("frame", () => {{
  n = n + 1;
  if (n == {SET_FRAME}) {{
""" + "".join(f"    {BLECH}{path} = {value};\n" for _, path, value in SETS) + f"""  }}
  if (n == {READ_FRAME}) {{
""" + "".join(f"    g_{k} = {BLECH}{path};\n" for k, path, _ in SETS) + f"""  }}
  if (n == {SWAP_FRAME}) {{
    {CUSTOM}padColor.part = {dict((k, v) for k, _, v in SETS)['select']};
    swapped_pad = {CUSTOM}padColor.part;
    swapped_select = {CUSTOM}padColor.select;
  }}
  if (n == {WRITE_FRAME}) {BLECH}write();
}});"""
PROGRAMS = {
    "pages": PAGES,
    # frame 5: light off, frame 40: back to full
    "light": f"""let n = 0;
korg.onEvent("frame", () => {{
  n = n + 1;
  if (n == 5) {INTENSITY} = 0;
  if (n == 40) {INTENSITY} = 15;
}});""",
    # a value that only shows at run time: 99 is clamped to 15 and counted
    "clamp": f"""let v = 99;
korg.onEvent("ready", () => {{
  {INTENSITY} = v;
}});""",
}


def compiled():
    """The include of the contract and the blobs of PROGRAMS, from the compiler of this checkout."""
    return node_json.compiled(PROGRAMS)


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    compiled()


def entry(name, ok, detail):
    return {"id": f"objects:{name}", "ok": bool(ok), "detail": str(detail)}


COLOUR = ["RED", "BLUE", "PINK"]                                # PAD COLOR and SELECT COLOR
METER = ["STOCK", "WHITE", "RED", "GREEN", "BLUE", "YELLOW", "CYAN", "PINK", "RAINBOW", "OFF"]
OVERLAP = ["AUTO", "RED", "BLUE", "PINK"]
PATCH_WORDS = {"confirm": 0xC0180F10, "tap": 0xC0188F00, "assist": 0xC0189F00}   # the words the patches behind the pages read
EVERY_VALUE = {k: v for k, _, v in SETS}


def hsv(red, green, blue):
    """The page's hue (0 to 95), saturation and brightness (0 to 15) of a stored colour, as look_hsv_get (tools/patch/script_hsv.s) works them out."""
    top, bottom = max(red, green, blue), min(red, green, blue)
    spread, hue = top - bottom, 0
    if spread:
        if red == top:
            part, hue = green - blue, 0
        elif green == top:
            part, hue = blue - red, 32
        else:
            part, hue = red - green, 64
        step = (abs(part) * 16 + spread // 2) // spread
        hue = (hue + (-step if part < 0 else step)) % 96
    return hue, (15 * spread + top // 2) // top, top


def page_values(feature_pages, du_pages):
    """(name, how to open the page, the value the page shows once the plugin has set SETS) for every page of the other leaves."""
    import menu_cases as m
    v = EVERY_VALUE
    bl, led = hsv(v["bl_red"], v["bl_green"], v["bl_blue"]), hsv(v["led_red"], v["led_green"], v["led_blue"])
    swapped_pad, swapped_select = v["select"], v["pad"]          # the write of PAD = SELECT's colour swaps the two
    pages = [
        ("bl_hue", (m.GROUP_DISPLAY, 0), str(bl[0])), ("bl_sat", (m.GROUP_DISPLAY, 1), str(bl[1])), ("bl_bright", (m.GROUP_DISPLAY, 2), str(bl[2])),
        ("invert", (m.GROUP_DISPLAY, 4), "ON" if v["invert"] else "OFF"),
        ("led_mode", (m.GROUP_LED, 0), ["METER", "COLOR", "OFF"][v["led_mode"]]),
        ("led_hue", (m.GROUP_LED, 1), str(led[0])), ("led_sat", (m.GROUP_LED, 2), str(led[1])), ("led_bright", (m.GROUP_LED, 3), str(led[2])),
        ("m_still", (m.GROUP_LED, 4), METER[v["m_still"]]), ("m_low", (m.GROUP_LED, 5), METER[v["m_low"]]),
        ("m_mid", (m.GROUP_LED, 6), METER[v["m_mid"]]), ("m_loud", (m.GROUP_LED, 7), METER[v["m_loud"]]),
        ("pad", (m.GROUP_PADS, 0), COLOUR[swapped_pad]), ("select", (m.GROUP_PADS, 1), COLOUR[swapped_select]),
        ("overlap", (m.GROUP_PADS, 2), OVERLAP[v["overlap"]]),
        ("light", (m.GROUP_PSAVE, 0), str(v["light"])), ("dim", (m.GROUP_PSAVE, 1), f"{[0, 10, 20, 30, 40, 50, 60, 70, 75, 80, 90, 100][v['dim']]}%"),
        ("mfx2", (m.GROUP_FEATURES, 0), "OFF, RESTART"), ("confirm", (m.GROUP_FEATURES, 1), "OFF"),
        ("tap", (m.GROUP_FEATURES, 2), ["OFF", "ON", "ONCE"][v["tap"]]), ("assist", (m.GROUP_FEATURES, 3), "OFF"),
    ]
    if "LAST PATTERN" in feature_pages:
        pages.append(("last", (m.GROUP_FEATURES, feature_pages.index("LAST PATTERN")), "OFF"))
    if "STEREO 1 PAD" in feature_pages:
        pages.append(("stereo", (m.GROUP_FEATURES, feature_pages.index("STEREO 1 PAD")), "OFF"))
    if "SET INIT PATTERN" in du_pages:
        pages.append(("init", ("du", du_pages.index("SET INIT PATTERN")), str(v["init"])))
    return pages


def page_text(dev, how):
    import menu_cases as m
    if how[0] == "du":
        m.goto_du(dev, how[1])
    else:
        m.goto_group(dev, *how)
    return m.texts_of(dev)


def pages_cases(payload, flash, request, built):
    """Phase 8: every leaf of the other pages of CUSTOMIZATION and FEATURES is set by a plugin and then shown by its page."""
    import menu_cases as m
    out = []
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    pages = page_values(m.feature_pages(), m.du_pages())
    before = {name: page_text(dev, how)[1] for name, how, _ in pages}
    script_cases.leave_menu(dev)
    entries = script_cases.install(dev, built, request["programs"], ["pages"])
    dev.run(4.0)
    got = script_cases.variables(dev, entries["pages"], request["programs"]["pages"])
    out.append(entry("read_back", all(got[f"g_{k}"] == v for k, _, v in SETS) and not dev.m.asserts,
                     {k: got[f"g_{k}"] for k, _, _ in SETS}))
    out.append(entry("pad_colors_swap", (got["swapped_pad"], got["swapped_select"]) == (EVERY_VALUE["select"], EVERY_VALUE["pad"]),
                     f"PAD {got['swapped_pad']}, SELECT {got['swapped_select']}"))
    words = {k: dev.u32(a) for k, a in PATCH_WORDS.items()}
    out.append(entry("patch_words_follow", words == {"confirm": 0, "tap": EVERY_VALUE["tap"], "assist": 0}, words))
    shown = {}
    for name, how, want in pages:
        shown[name] = page_text(dev, how)
        out.append(entry(f"page_{name}", shown[name][1] == want and before[name] != want and not dev.m.asserts,
                         f"before {before[name]!r}, shown {shown[name]}, want {want!r}"))
    script_cases.leave_menu(dev)
    files = menu_cases.read_settings_look(dev.m.mmc.card.medium.data)
    out.append(entry("write_saved", bool(files) and not dev.m.asserts, {k: v[:2] for k, v in files.items()}))
    again = restart(dev, payload, flash)
    stored = {name: page_text(again, how)[1] for name, how, _ in pages if name != "init"}
    want = {name: ("OFF" if name == "mfx2" else w) for name, _, w in pages if name != "init"}
    bad = {k: (stored[k], want[k]) for k in want if stored[k] != want[k]}
    out.append(entry("write_then_restart", not bad and not again.m.asserts, bad or "every page shows the written value after a restart"))
    return out


def restart(old, payload, flash):
    from splash_cases import Dev
    from sdcard import MemoryMedium, SDCard
    new = Dev(payload, flash, 0)
    new.m.adapter = True
    new.m.insert_card(SDCard(MemoryMedium(bytearray(old.m.mmc.card.medium.data))))
    new.run(2.0)
    return new


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    request = compiled()
    built = script_hooks.build(request["include"], build=identify(payload).build)
    at = (script_hooks.MENU_STATE + built.symbols["MX_INTENS"]) & 0xFFFFFFFF
    out = []

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    menu_cases.watch_pins(dev)
    script_cases.install(dev, built, request["programs"], ["light"])
    before = menu_cases.duty(dev, 0.1)[0]
    dev.run(0.3)
    dark = menu_cases.duty(dev, 0.8)[0], dev.read(at, 1)[0]
    dev.run(0.6)
    light = menu_cases.duty(dev, 0.5)[0], dev.read(at, 1)[0]
    out.append(entry("light_off_and_on", dark[1] == 0 and max(dark[0].values()) == 0 and light[1] == 15 and min(light[0].values()) == 1.0
                     and not dev.m.asserts, f"before {before}, off {dark}, on {light}"))

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    script_cases.install(dev, built, request["programs"], ["clamp"])
    dev.run(0.3)
    repairs = dev.u32(built.symbols["objects_repairs"])
    out.append(entry("clamped_and_counted", dev.read(at, 1)[0] == 15 and repairs == 1 and not dev.m.asserts, f"INTENSITY {dev.read(at, 1)[0]}, repairs {repairs}"))

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    dev.m.uc.mem_write(at, bytes([200]))
    dev.call(built.symbols["objects_repair"])
    out.append(entry("repaired_at_start", dev.read(at, 1)[0] == 15 and dev.u32(built.symbols["objects_repairs"]) == 1 and not dev.m.asserts,
                     f"INTENSITY {dev.read(at, 1)[0]}, repairs {dev.u32(built.symbols['objects_repairs'])}"))
    out += pages_cases(payload, flash, request, built)
    return out


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
