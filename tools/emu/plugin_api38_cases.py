"""Emulator cases of plugin API 38: the card reads korg.file.picture (a .bmp in Media/) and korg.file.frame (GIF00.E2G) in
every frame handler keep a plugin on, because the time inside a card read does not count against the frame budget
(CARD_READS in data/script/contract.mjs, tools/patch/script_media.s:card_timed). Ten reads in one handler go past the card
time a frame may leave out (CARD_READS.cardMs) and end in TIME, as a card that answers slowly would. korg.file.write reads the card at its first call
and counts as a card read too.

The Image Viewer (catalog app bmpviewer) on a card with pictures and animations in Media/: the screens and variables at each
step equal the browser's simulator (src/script/sim.mjs) byte for byte, in the display memory and on the panel (Machine.shown),
with DISPLAY INVERT ON and OFF; IMAGES pages and wraps, ANIMATIONS steps, plays, changes the speed and pauses; NO IMAGES,
NO ANIMATIONS, NO CARD and BAD FILE; playing at 48 ms reads a picture nearly every frame and the app stays on. The details
of the cases name the slowest handler, the time of each card read and the time of a frame while it plays.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_api38_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
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
import node_json  # noqa: E402
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
    "write": """const data = new Array(1024);
let got = 99;
let writes = 0;
korg.onEvent("frame", () => { got = korg.file.write(data, 0); writes = writes + 1; });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)
    for card, invert, steps in VIEWER_RUNS:
        edit.compiled({"bmpviewer": viewer_sim(card, invert, steps)["source"]})


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
    r = boot(vsb, flash, request, ["write"])
    w = r["write"]
    out.append(entry("write_every_frame", w["state"] == STATE_ARMED and w["fault"] == 0 and w["vars"].get("got") == 1024
                     and w["vars"].get("writes", 0) > 20 and w["ticks"] is not None and w["ticks"] < WARN_TICKS
                     and not r["asserts"], w))
    return out


FB = 0xC031B310                  # the LCD's 128x64 bytes in the firmware (tools/emu/catalog_app_cases.py)
NS_PER_TICK = 1e9 / 150e6        # Timer3

# The Image Viewer as the catalog ships it, the card it reads and what the simulator shows at each named step. Argument 1 is the
# card ("media": pictures and animations in Media/, "empty": a start image outside Media/ only, "none": no card), argument 2
# DISPLAY INVERT (1 ON, the factory value, or 0), argument 3 the steps as JSON: [op, value, seconds, name] with op "open",
# "turn" (encoder delta), "key" (a korg.key name) or "wait"; after the op the simulator runs the seconds in 40 ms frames and
# keeps the display memory (display), the panel (lcd) and the variables under the name, when there is one.
VIEWER_SIM = """
import { readFileSync } from "node:fs";
import { PRESETS } from "./data/script/presets.mjs";
import { KEY_NAMES } from "./data/script/names.mjs";
import { OBJECTS } from "./data/script/objects.mjs";
import { SCRIPT_MEDIA } from "./data/script/contract.mjs";
import { compile } from "./src/script/compiler.mjs";
import { SimDevice } from "./src/script/sim.mjs";
import { encodeBmp } from "./src/splash-bmp.mjs";
import { encodeAnimation } from "./src/loading-anim.mjs";
const [card, invert, steps] = [process.argv[1], Number(process.argv[2]), JSON.parse(process.argv[3])];
const media = name => SCRIPT_MEDIA.folder + name;
const marker = new Uint8Array(128 * 64);
for (let y = 0; y < 20; y++) for (let x = 0; x < 40; x++) marker[y * 128 + x] = 1;
marker[128 * 64 - 1] = 1;
const topDown = encodeBmp(marker.map((v, i) => (i % 128 > 100 ? 1 - v : v)));
new DataView(topDown.buffer).setInt32(22, -64, true);
for (let y = 0; y < 32; y++) { const a = topDown.slice(62 + y * 16, 78 + y * 16); topDown.copyWithin(62 + y * 16, 62 + (63 - y) * 16, 78 + (63 - y) * 16); topDown.set(a, 62 + (63 - y) * 16); }
const broken = encodeBmp(marker);
new DataView(broken.buffer).setUint16(28, 24, true);
const frameOf = seed => Uint8Array.from({ length: 1024 }, (_, i) => (i * seed + seed) & 255);
const files = card === "media" ? new Map([
  [media("marker.bmp"), encodeBmp(marker)],
  [media("loading.blla"), new Uint8Array(readFileSync("assets/blechy/loading.blla"))],
  [media("top-down-picture-long.bmp"), topDown],
  [media("broken.bmp"), broken],
  [media("small.blla"), encodeAnimation({ progress: [frameOf(1), frameOf(2), frameOf(3)], loop: [frameOf(5), frameOf(7)] }).bytes],
  ["KORG/blechtribe/splash.bmp", encodeBmp(marker)],
]) : card === "empty" ? new Map([["KORG/blechtribe/splash.bmp", encodeBmp(marker)]]) : null;
const p = PRESETS.find(p => p.id === "bmpviewer");
const r = compile(p.source, { name: p.id });
let now = 0;
const d = new SimDevice({ card: files, now: () => now });
d.hardware.objects[OBJECTS.findIndex(o => o.path === "korg.menu.blech.customizations.display.invert")] = invert;
const loaded = d.load(r.blob);
d.frame();
const hex = b => Buffer.from(b).toString("hex");
const vars = () => Object.fromEntries(Object.entries(r.info.symbols).filter(([, s]) => s.kind === "var").map(([n, s]) => [n, loaded.script.vars[s.slot]]));
const out = {};
for (const [op, value, seconds, name] of steps) {
  if (op === "open") d.openApp(0);
  if (op === "turn") d.post("encoder", 0, value);
  if (op === "key") d.post("buttonPress", KEY_NAMES.find(k => k.name === value).value);
  for (let i = 0; i < Math.max(1, Math.round(seconds * 25)); i++) { now += 40; d.frame(); }
  if (name) out[name] = { display: hex(d.display.bytes), lcd: hex(d.lcd), vars: vars() };
}
process.stdout.write(JSON.stringify({ source: p.source, files: [...(files ?? new Map())].map(([k, v]) => ["/" + k, hex(v)]),
  steps: out, fault: d.status().scripts[0].fault ?? null }));
"""

KEYS = {"TAP": 3, "MENU": 9, "PART_LEFT": 11, "PART_RIGHT": 15}
SHOWN, LABEL = 2.5, 0.3          # seconds after a step: the name and place have gone (2 s), or still show
MEDIA_STEPS = [
    ["open", 0, 0.3, "list"],
    ["turn", 1, 0.3, "list_animations"],
    ["key", "PART_LEFT", 0.3, "list_images"],
    ["key", "MENU", LABEL, "image_0_named"],
    ["wait", 0, SHOWN, "image_0"],
    ["turn", 1, SHOWN, "image_1_top_down"],
    ["key", "PART_RIGHT", LABEL, "image_2_bad_file"],
    ["key", "PART_RIGHT", SHOWN, "image_wraps_to_0"],
    ["key", "PART_LEFT", SHOWN, "image_wraps_back_to_2"],
    ["key", "MENU", 0.3, "back_to_the_list"],
    ["turn", 1, 0.3, None],
    ["key", "MENU", SHOWN, "animation_0_picture_0"],
    ["key", "PART_LEFT", SHOWN, "animation_0_jump_to_last"],
    ["key", "PART_RIGHT", SHOWN, "animation_0_wraps_to_0"],
    ["key", "PART_RIGHT", SHOWN, "animation_0_picture_1"],
    ["turn", 1, SHOWN, "animation_1_picture_0"],
    ["key", "PART_RIGHT", SHOWN, "animation_1_picture_1"],
    ["key", "PART_LEFT", 0.3, None],
    ["key", "PART_LEFT", SHOWN, "animation_1_back_to_last"],
    ["key", "PART_RIGHT", 0.3, "animation_1_wraps_to_0"],
]
POLARITY_STEPS = [
    ["open", 0, 0.3, "list"],
    ["key", "MENU", SHOWN, "image_0"],
    ["key", "MENU", 0.3, None],
    ["turn", 1, 0.3, None],
    ["key", "MENU", 0.3, None],
    ["turn", 1, SHOWN, "animation_1_picture_0"],
]
EMPTY_STEPS = [
    ["open", 0, 0.3, "list"],
    ["key", "MENU", 0.3, "no_images"],
    ["turn", 1, 0.3, None],
    ["key", "PART_RIGHT", 0.3, None],
    ["key", "TAP", 0.3, "no_images_after_input"],
    ["key", "MENU", 0.3, None],
    ["turn", 1, 0.3, None],
    ["key", "MENU", 0.3, "no_animations"],
    ["key", "TAP", 0.3, "no_animations_after_tap"],
]
NO_CARD_STEPS = [
    ["open", 0, 0.3, "no_card"],
    ["key", "MENU", 0.3, "no_card_menu_stays"],
]
# (card, DISPLAY INVERT, steps)
VIEWER_RUNS = [("media", 1, MEDIA_STEPS), ("media", 0, POLARITY_STEPS), ("empty", 1, EMPTY_STEPS), ("none", 1, NO_CARD_STEPS)]
COMPARED = ("mode", "sel", "n0", "n1", "file", "frame", "total", "playing", "ms")


def viewer_sim(card, invert, steps):
    return node_json.run(VIEWER_SIM, card, invert, json.dumps(steps, separators=(",", ":")))


class Probe:
    """Times taken in the emulator: each card read (card_timed, from the call of the glue to its return) by its glue, and each
    run of the runtime's frame hook (script_frame_hook, all plugins of one frame), in ns of the emulator's clock."""

    def __init__(self, dev, symbols):
        import unicorn
        self.dev, self.reads, self.frames, self.mark = dev, [], [], "start"
        glue = {symbols[f"script_file_{n}_glue"]: n for n in ("count", "name", "picture", "frame", "read", "write")}
        timed, hook = symbols["card_timed"], symbols["script_frame_hook"]
        pending = {}
        m, arm = dev.m, dev.m.A

        def card_in(uc, *_):
            pending["card"] = (m.time_ns, glue.get(uc.reg_read(arm.UC_ARM_REG_R12), "?"))

        def card_out(uc, *_):
            t, name = pending.pop("card", (None, None))
            if t is not None:
                self.reads.append((self.mark, name, m.time_ns - t))

        def frame_in(uc, *_):
            pending["frame"] = m.time_ns

        def frame_out(uc, *_):
            t = pending.pop("frame", None)
            if t is not None:
                self.frames.append((self.mark, m.time_ns - t))

        uc = m.uc
        uc.hook_add(unicorn.UC_HOOK_CODE, card_in, begin=timed, end=timed)
        uc.hook_add(unicorn.UC_HOOK_CODE, card_out, begin=timed + 16, end=timed + 16)      # behind blx r12
        uc.hook_add(unicorn.UC_HOOK_CODE, frame_in, begin=hook, end=hook)
        uc.hook_add(unicorn.UC_HOOK_CODE, frame_out, begin=hook + 20, end=hook + 20)       # behind bl script_frame_run

    def read_ms(self, name, mark=None):
        """The slowest read of a glue (in ms), within one mark or in all."""
        ns = [t for k, n, t in self.reads if n == name and (mark is None or k == mark)]
        return round(max(ns) / 1e6, 2) if ns else None

    def frame_ms(self, mark):
        ns = [t for k, t in self.frames if k == mark]
        return {"frames": len(ns), "max_ms": round(max(ns) / 1e6, 2), "mean_ms": round(sum(ns) / len(ns) / 1e6, 2)} if ns else None


def viewer_device(vsb, flash, request, ref, invert):
    """A device with the simulator's card and the Image Viewer on it, DISPLAY INVERT OFF from a settings file when asked. The card
    gets the files in the simulator's order (a list: node-results.json sorts the keys of an object), as FatFs lists them."""
    files = {**menu_cases.CARD_FOLDER, **{k: bytes.fromhex(v) for k, v in ref["files"]},
             script_cases.CARD_FILE: script_cases.archive([bytes.fromhex(request["programs"]["bmpviewer"]["blob"])])}
    if not invert:
        files[menu_cases.SETTINGS_PATHS[0]] = menu_cases.settings_file_v2(2, 3, menu_cases.look_word(0, invert=0))
    dev = script_cases.with_card(vsb, flash, files)
    dev.run(2)
    return dev


def viewer_step(dev, op, value, seconds):
    if op == "open":
        script_cases.open_app(dev, menu_cases.GROUP_TOOLS)
        dev.run(seconds)
    elif op == "turn":
        dev.turn(value, wait=seconds)
    elif op == "key":
        dev.m.press(KEYS[value], True)
        dev.run(0.05)
        dev.m.press(KEYS[value], False)
        dev.run(seconds)
    else:
        dev.run(seconds)


def viewer_run(vsb, flash, request, built, card, invert, steps, check, prefix, probe=False):
    """Runs the steps on the emulator and checks every named one against the simulator; returns the device, its plugin entry
    and the probe (or None)."""
    ref = viewer_sim(card, invert, steps)
    dev = viewer_device(vsb, flash, request, ref, invert)
    program = request["programs"]["bmpviewer"]
    at = script_cases.plugin_entry(dev, built.layout["runtime"], 0)
    if card == "none":
        dev.m.eject_card()
        dev.run(0.5)
    p = Probe(dev, built.symbols) if probe else None
    for op, value, seconds, name in steps:
        if p:
            p.mark = name or p.mark
        viewer_step(dev, op, value, seconds)
        if not name:
            continue
        want = ref["steps"][name]
        ram, panel = bytes(dev.read(FB, 1024)), dev.m.shown()
        got = script_cases.variables(dev, at, program)
        wrong = {k: (got.get(k), want["vars"].get(k)) for k in COMPARED if got.get(k) != want["vars"].get(k)}
        ram_diff = sum(a != b for a, b in zip(ram, bytes.fromhex(want["display"])))
        panel_diff = sum(a != b for a, b in zip(panel, bytes.fromhex(want["lcd"])))
        check(f"{prefix}_{name}", not wrong and ram_diff == 0 and panel_diff == 0 and not dev.m.asserts,
              f"display memory {ram_diff}, panel {panel_diff} of 1024 bytes differ from the simulator; variables (emulator, "
              f"simulator) that differ: {wrong}; reversed {dev.m.lcd_reverse}, asserts {dev.m.asserts}")
    return dev, at, p


def viewer_cases(vsb, flash):
    request = edit.compiled({"bmpviewer": viewer_sim(*VIEWER_RUNS[0])["source"]})
    program = request["programs"]["bmpviewer"]
    built = script_hooks.build(request["include"], build=identify(vsb[0x100:]).build)
    out = []

    def check(name, ok, detail=""):
        out.append(entry(f"viewer_{name}", ok, detail))

    dev, at, probe = viewer_run(vsb, flash, request, built, *VIEWER_RUNS[0], check, "invert_on", probe=True)
    v = lambda: script_cases.variables(dev, at, program)   # noqa: E731

    # small.blla stands at picture 0: TAP plays a picture every 96 ms, after the last comes picture 0 again
    probe.mark = "play_96"
    viewer_step(dev, "key", "TAP", 0.0)
    seen = []
    for _ in range(50):
        dev.run(0.04)
        seen.append(v()["frame"])
    changes = sum(a != b for a, b in zip(seen, seen[1:]))
    check("plays_every_96_ms_and_wraps", v()["playing"] == 1 and 17 <= changes <= 23 and 0 in seen[5:] and 4 in seen,
          f"{changes} pictures in 2 s, frames {seen}")
    probe.mark = "speed"
    viewer_step(dev, "key", "PART_RIGHT", 0.1)
    fast = v()["ms"]
    for _ in range(4):
        viewer_step(dev, "key", "PART_LEFT", 0.1)
    slow = v()["ms"]
    viewer_step(dev, "key", "TAP", 0.2)
    paused = v()
    dev.run(1.0)
    check("speed_48_to_384_and_tap_pauses", fast == 48 and slow == 384 and paused["playing"] == 0
          and v()["frame"] == paused["frame"], f"Part right {fast} ms, four times Part left {slow} ms, after TAP {paused['playing']}, "
                                               f"frame {paused['frame']} then {v()['frame']}")

    # loading.blla (Blechy, the largest) at 48 ms: a picture nearly every frame, the app stays on. The speed stays 384 ms
    # from above, three times Part right is 48 ms.
    probe.mark = "loading_blla_opened"
    viewer_step(dev, "turn", -1, 0.3)
    probe.mark = "loading_blla_start"
    viewer_step(dev, "key", "TAP", 0.1)
    for _ in range(3):
        viewer_step(dev, "key", "PART_RIGHT", 0.1)
    probe.mark = "play_48"
    before = len([r for r in probe.reads if r[1] == "picture"])
    dev.run(5.0)
    reads = len([r for r in probe.reads if r[1] == "picture"]) - before
    state, fault, ticks = dev.u32(at + 12), dev.u32(at + 16), dev.u32(at + 40)
    timing = {
        "slowest_handler_ms": round(ticks * NS_PER_TICK / 1e6, 3),
        "count_ms": probe.read_ms("count"),
        "name_ms": probe.read_ms("name"),
        "bmp_picture_ms": max(filter(None, [probe.read_ms("picture", k) for k in ("image_0_named", "image_1_top_down", "image_wraps_to_0")]), default=None),
        "bad_bmp_ms": probe.read_ms("picture", "image_2_bad_file"),
        "blla_first_picture_ms": probe.read_ms("picture", "animation_0_picture_0"),
        "blla_first_picture_again_ms": probe.read_ms("picture", "loading_blla_opened"),
        "blla_jump_to_last_ms": probe.read_ms("picture", "animation_0_jump_to_last"),
        "blla_step_ms": probe.read_ms("picture", "animation_0_picture_1"),
        "blla_picture_playing_48_ms": probe.read_ms("picture", "play_48"),
        "frame_playing_96": probe.frame_ms("play_96"),
        "frame_playing_48": probe.frame_ms("play_48"),
        "frame_list": probe.frame_ms("list_images"),
    }
    check("plays_loading_blla_at_48_ms_and_stays_on", state == STATE_ARMED and fault == 0 and v()["playing"] == 1
          and v()["ms"] == 48 and reads >= 80 and ticks < WARN_TICKS and not dev.m.asserts,
          f"{reads} pictures read in 5 s, state {state}, fault {fault}, slowest handler {ticks} ticks; timing {timing}")
    dev.press("exit", 0.5)
    check("exit_gives_the_main_screen_back", dev.screen()["number"] == 1 and not dev.m.asserts, dev.screen())

    for card, invert, steps in VIEWER_RUNS[1:]:
        prefix = {"media": "invert_off", "empty": "empty", "none": "no_card"}[card]
        dev, at, _ = viewer_run(vsb, flash, request, built, card, invert, steps, check, prefix)
        check(f"{prefix}_stays_on", dev.u32(at + 12) == STATE_ARMED and dev.u32(at + 16) == 0,
              f"state {dev.u32(at + 12)}, fault {dev.u32(at + 16)}")
    return out


def cases(vsb, flash=None):
    menu_cases.for_build(vsb[0x100:])
    request = edit.compiled(PROGRAMS)
    return budget_cases(vsb, flash, request) + viewer_cases(vsb, flash)


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
