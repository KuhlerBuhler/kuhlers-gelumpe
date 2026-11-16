"""Emulator cases of plugin API 38: the card reads korg.file.picture (a .bmp in Media/) and korg.file.frame (GIF00.E2G) in
every frame handler keep a plugin on, because the time inside a card read does not count against the frame budget
(CARD_READS in data/script/contract.mjs, tools/patch/script_media.s:card_timed). Ten reads in one handler go past the card
time a frame may leave out (CARD_READS.cardMs) and end in TIME, as a card that answers slowly would.

    python3 tools/emu/plugin_api38_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

STATE_ARMED, STATE_DISABLED = 2, 3       # data/script/contract.mjs SCRIPT_STATE
ERR_TIME = 7                             # data/script/contract.mjs ERRORS
WARN_TICKS = 75000                       # BUDGET.handlerWarnMs, 0.5 ms of Timer3 (150 MHz)
MEDIA = "/KORG/blechtribe/Media/"
GIF = "/KORG/blechtribe/Gif/GIF00.E2G"

PROGRAMS = {
    "picture": """const pic = new Array(1024);
let got = 99;
let n = 0;
let reads = 0;
korg.onEvent("frame", () => { if (n == 0) { n = korg.file.count(0); return; } got = korg.file.picture(pic, 0, 0, 0); reads = reads + 1; });""",
    "gif": """const pic = new Array(1024);
let got = 99;
let reads = 0;
korg.onEvent("frame", () => { got = korg.file.frame(pic, 0, 0); reads = reads + 1; });""",
    "many": """const pic = new Array(1024);
let n = 0;
let reads = 0;
korg.onEvent("frame", () => {
  if (n == 0) { n = korg.file.count(0); return; }
  for (let i = 0; i < 10; i = i + 1) { korg.file.picture(pic, 0, 0, 0); reads = reads + 1; }
});""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api38:{name}", "ok": bool(ok), "detail": str(detail)}


def marker_bmp():
    """128 x 64, 1 bit, bottom-up: a black block 40 x 20 at the top left."""
    off = 62
    b = bytearray(off + 16 * 64)
    b[0:2] = b"BM"
    struct.pack_into("<IHHI", b, 2, len(b), 0, 0, off)
    struct.pack_into("<IiiHHIIiiII", b, 14, 40, 128, 64, 1, 1, 0, 16 * 64, 2835, 2835, 2, 0)
    b[54:62] = bytes([0xff, 0xff, 0xff, 0, 0, 0, 0, 0])
    for y in range(20):
        row = off + (63 - y) * 16
        for x in range(40):
            b[row + (x >> 3)] |= 0x80 >> (x & 7)
    return bytes(b)


def gif_file():
    return b"GGIF" + struct.pack("<HH", 1, 1) + struct.pack("<H", 100) + b"\0\0" + bytes(1024)


def boot(vsb, flash, request, names, seconds=6.0):
    """A device with Media/marker.bmp and GIF00.E2G on the card and the given plugins, run for some seconds; per plugin its
    variables, state, fault and the ticks of its slowest handler."""
    payload = vsb[0x100:]
    built = script_hooks.build(request["include"], build=identify(payload).build)
    blobs = [bytes.fromhex(request["programs"][n]["blob"]) for n in names]
    dev = script_cases.with_card(vsb, flash, {**menu_cases.CARD_FOLDER, MEDIA + "marker.bmp": marker_bmp(), GIF: gif_file(),
                                              script_cases.CARD_FILE: script_cases.archive(blobs)})
    dev.run(seconds)
    out = {}
    for i, name in enumerate(names):
        at = script_cases.plugin_entry(dev, built.layout["runtime"], i)
        found = script_cases.variables(dev, at, request["programs"][name]) if at else {}
        out[name] = {"vars": {k: v for k, v in found.items() if k != "pic"}, "state": dev.u32(at + 12) if at else None,
                     "fault": dev.u32(at + 16) if at else None, "ticks": dev.u32(at + 40) if at else None}
    out["asserts"] = dev.m.asserts
    return out


def budget_cases(vsb, flash, request):
    r = boot(vsb, flash, request, ["picture", "gif"])
    pic, gif = r["picture"], r["gif"]
    out = [entry("picture_every_frame", pic["state"] == STATE_ARMED and pic["fault"] == 0 and pic["vars"].get("got") == 1
                 and pic["vars"].get("reads", 0) > 20 and not r["asserts"], pic),
           entry("gif_every_frame", gif["state"] == STATE_ARMED and gif["fault"] == 0 and gif["vars"].get("got") == 100
                 and gif["vars"].get("reads", 0) > 20, gif),
           entry("card_time_not_counted", pic["ticks"] is not None and pic["ticks"] < WARN_TICKS
                 and gif["ticks"] is not None and gif["ticks"] < WARN_TICKS,
                 f"slowest handler {pic['ticks']} and {gif['ticks']} ticks, warning at {WARN_TICKS}")]
    r = boot(vsb, flash, request, ["many"], seconds=5.0)
    many = r["many"]
    out.append(entry("card_time_capped", many["state"] == STATE_DISABLED and many["fault"] == ERR_TIME, many))
    return out


def cases(vsb, flash=None):
    menu_cases.for_build(vsb[0x100:])
    request = edit.compiled(PROGRAMS)
    return budget_cases(vsb, flash, request)


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
