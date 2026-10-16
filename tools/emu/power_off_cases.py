# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the Blechy power-off patch (tools/patch/power_off.py,
docs/messungen/2026-10-15-blechy-power-off.md).

check.py runs `cases` on every patched copy that carries the hook: switching the device off shows the sad Blechy
and his line instead of the firmware's box, the picture is there from the first display frame and stays until the
power is gone, with EXIT held at power-on the firmware's own box is what shows, the device switches off at the same
moment as without the patch, and the save writes exactly what it wrote before: the same flash commands with the same
data and the same card writes, compared with the same copy with only the hook put back (`reverted`).

    tools/emu/.venv/bin/python tools/emu/power_off_cases.py cases --patched NEW.VSB [--flash dump.bin]
    tools/emu/.venv/bin/python tools/emu/power_off_cases.py shots --patched NEW.VSB --png-dir DIR [--flash dump.bin]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patch"))

import bootcache  # noqa: E402
import menu_cases  # noqa: E402
import synthaddr  # noqa: E402
import power_off as spec  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import Dev, user_flash  # noqa: E402

HEADER = 0x100
IMAGE = 0xC0000000
KILL = spec.KILL_SWITCH
POWER_KEY = [6, 1, 0, 0, 0]
GLOBALS = 0xC0691324     # pointer to the Global settings, +0x29 is Power Save (0 to 2; docs/hintergrund/skript-laufzeit.md, 4.3)
POWER_SAVE = 0x29
LIMIT_S = 3.0           # the device is off after 1 s; mains power ignores the key and has to be left running that long
STEP_S = 0.005
RUNS = ["plain", "plain_stock", "edit", "edit_stock", "exit", "exit_stock", "mains", "blechy"]


def for_build(payload):
    """Put the patch module's places to the build of this image (the synth has its own addresses, data/synth-map/)."""
    spec.use_build("synth" if synthaddr.is_synth(payload) else "hacktribe")


def has_hook(payload):
    """True when the wait call of the power-off handler goes into our code."""
    for_build(payload)
    word = struct.unpack_from("<I", payload, spec.WAIT_CALL - IMAGE)[0]
    if word >> 24 != 0xEB:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= spec.WAIT_CALL + 8 + (off << 2) < spec.CODE_END


def reverted(payload):
    """The same copy with the hook put back to the original call, everything else of the patch left where it is."""
    out = bytearray(payload)
    struct.pack_into("<I", out, spec.WAIT_CALL - IMAGE, spec.bl_word(spec.WAIT_CALL, spec.WAIT_FUNC))
    return bytes(out)


def frame_of(payload):
    return bytes(payload[spec.FRAME_AT - IMAGE:spec.FRAME_AT - IMAGE + 1024])


def sha(data):
    return hashlib.sha256(data).hexdigest()[:16]


def traced(dev):
    """Logs of what the device writes: flash commands with their data, and card blocks. Returns (flash log, card log)."""
    flash, medium = dev.m.flash, dev.m.mmc.card.medium
    ops, card = {"erase": [], "program": hashlib.sha256(), "bytes": 0}, []
    erase, byte, write = flash.erase, flash.byte, medium.write

    def erase_(size):
        ops["erase"].append((flash.addr & ~(size - 1), size))
        return erase(size)

    def byte_(b):
        if flash.cmd == 0x02 and flash.wel and len(flash.buf) >= 3:
            ops["program"].update(struct.pack("<IB", flash.addr, b))
            ops["bytes"] += 1
        return byte(b)

    def write_(lba, block):
        card.append((lba, sha(bytes(block))))
        return write(lba, block)

    flash.erase, flash.byte, medium.write = erase_, byte_, write_
    return ops, card


def run_case(payload, flash, name):
    """One switch-off. `name` is one of RUNS; "_stock" is the same copy with the hook put back. Returns plain data."""
    for_build(payload)
    stock = name.endswith("_stock")
    kind = name.removesuffix("_stock")
    dev = Dev(reverted(payload) if stock else payload, flash, KILL if kind == "exit" else 0)
    m = dev.m
    m.adapter = kind == "mains"
    medium = MemoryMedium(menu_cases.card_image(menu_cases.CARD_FOLDER))
    m.insert_card(SDCard(medium))
    dev.run(1.5)
    if kind == "edit":      # a changed Global setting that only the switch-off saves, and the BLECH settings written to the card before
        settings = dev.u32(GLOBALS) + POWER_SAVE
        dev.m.uc.mem_write(settings, bytes([(dev.read(settings, 1)[0] + 1) % 3]))
        menu_cases.goto_group(dev, menu_cases.GROUP_PLUGINS, 0)
        dev.turn(-1, wait=0.2)
        dev.press("write", wait=0.6)
        menu_cases.go(dev, 1)
        dev.run(0.5)
    if kind == "blechy":    # the device is on the page of Blechy, built into BLECH, and he has stopped waving
        menu_cases.goto_blechy(dev)
        dev.run(5.0)
    ours = frame_of(payload)
    ops, card = traced(dev)
    card_before = sha(bytes(medium.data))
    main = dev.fb()
    m.send(POWER_KEY)
    t0, timeline = m.time_ns, []
    while m.powered and (m.time_ns - t0) / 1e9 < LIMIT_S:
        dev.run(STEP_S)
        fb = dev.fb()
        label = "main" if fb == main else "ours" if fb == ours else "blank" if not any(fb) else "fb:" + sha(fb)
        if not timeline or timeline[-1][1] != label:
            timeline.append([round((m.time_ns - t0) / 1e6, 1), label])
    box = [t for t in timeline if t[1].startswith("fb:")]
    return {
        "name": name, "powered": bool(m.powered), "off_ms": None if m.powered else round((m.time_ns - t0) / 1e6, 1),
        "timeline": timeline, "box_frames": len(box), "first_ours_ms": next((t for t, k in timeline if k == "ours"), None),
        "flash_sha": sha(user_flash(m)), "flash_erases": ops["erase"], "flash_programmed": ops["bytes"],
        "flash_program_sha": ops["program"].hexdigest()[:16], "card_changed": sha(bytes(medium.data)) != card_before, "card_writes": card,
        "ours_lit": sum(bin(b).count("1") for b in ours), "asserts": list(m.asserts),
    }


def run_task(name):
    """run_case in a worker (parallel.py)."""
    import parallel
    return run_case(parallel.shared["payload"], parallel.shared["flash"], name)


def shows_picture(run):
    """The display goes from the main screen to the picture within 100 ms and then stays on it until the power is gone. One frame of the
    firmware's box may come in between: the window paints when it opens, at a time the display frame (every 40 ms) does not wait for.
    The picture may also be the first thing a look sees, when the first display frame came before the first look."""
    labels = [k for _, k in run["timeline"]]
    first = run["first_ours_ms"]
    if labels[:1] == ["main"]:
        labels = labels[1:]
    if labels[:1] and labels[0].startswith("fb:"):
        labels = labels[1:]
    return labels == ["ours", "blank"] and first is not None and first <= 100


def judge(runs):
    """The check.py entries [{id, ok, detail}] for the results of all RUNS, by name."""
    out = []

    def add(name, ok, detail):
        out.append({"id": f"power_off:{name}", "ok": bool(ok), "detail": detail})

    p, s = runs["plain"], runs["plain_stock"]
    full = "edit" in runs
    add("picture_shown", not p["powered"] and shows_picture(p) and p["ours_lit"] > 600 and not p["asserts"],
        f"display {p['timeline']} (main screen, at most one frame of the box before the picture, then the picture until the power is gone), {p['ours_lit']} pixels lit")
    labels = [k for _, k in s["timeline"]]
    add("stock_shows_the_box", not s["powered"] and "ours" not in labels and s["box_frames"] >= 1 and labels[0] == "main" and labels[-1] == "blank",
        f"with the hook put back the display shows the firmware's own box ({s['box_frames']} frames) and never the picture")
    add("switch_off_time", not p["powered"] and not s["powered"] and abs(p["off_ms"] - s["off_ms"]) <= 5,
        f"the power falls after {p['off_ms']} ms, {s['off_ms']} ms without the hook (the wait stays one second)")
    for what, a, b in (("save_identical", runs["plain"], runs["plain_stock"]), *((("save_identical_after_edit", runs["edit"], runs["edit_stock"]),) if full else ())):
        same = (a["flash_sha"], a["flash_erases"], a["flash_programmed"], a["flash_program_sha"], a["card_changed"], a["card_writes"]) == \
               (b["flash_sha"], b["flash_erases"], b["flash_programmed"], b["flash_program_sha"], b["card_changed"], b["card_writes"])
        busy = b["flash_programmed"] > 0
        add(what, same and busy and not a["powered"] and not b["powered"] and not a["asserts"],
            f"flash: {len(a['flash_erases'])} erases and {a['flash_programmed']} programmed bytes, card: {len(a['card_writes'])} block writes during the switch-off, "
            f"flash image {a['flash_sha']}, card changed: {a['card_changed']}; the same as without the hook: {same}; the original writes something at all: {busy}")
    if full:
        e = runs["edit"]
        add("picture_shown_after_edit", shows_picture(e) and e["flash_sha"] != p["flash_sha"],
            f"display {e['timeline']} with a changed Global setting (the flash differs from the plain run: {e['flash_sha'] != p['flash_sha']}) and BLECH settings on the card")
    x, xs = runs["exit"], runs["exit_stock"]
    add("exit_held_is_stock", not x["powered"] and "ours" not in [k for _, k in x["timeline"]] and [k for _, k in x["timeline"]] == [k for _, k in xs["timeline"]]
        and abs(x["off_ms"] - xs["off_ms"]) <= 2 and (x["flash_sha"], x["flash_program_sha"], x["card_changed"]) == (xs["flash_sha"], xs["flash_program_sha"], xs["card_changed"]),
        f"with EXIT held at power-on the display shows {[k for _, k in x['timeline']]}, never the picture, as without the hook")
    if full:
        b = runs["blechy"]
        add("picture_shown_on_blechys_page", not b["powered"] and shows_picture(b) and b["ours_lit"] > 600 and not b["asserts"],
            f"display {b['timeline']} on the page of Blechy (the live Blechy gives way to the picture of the Power Off window and does not paint over it)")
    a = runs["mains"]
    add("mains_power_ignores_the_key", a["powered"] and "ours" not in [k for _, k in a["timeline"]] and not a["asserts"],
        "on mains power the firmware ignores the power key, nothing of the patch shows and the device keeps running")
    return out


def runs_for(payload):
    """The runs a copy can do: the ones that edit a setting or open Blechy's page need the BLECH menu in the copy."""
    if payload is None or menu_cases.has_menu(payload):
        return RUNS
    return [name for name in RUNS if not name.startswith(("edit", "blechy"))]


def cases(payload, flash=None):
    """All cases for a patched copy, run one after the other. Returns the check.py entries."""
    return judge({name: run_case(payload, flash, name) for name in runs_for(payload)})


def cases_tasks(payload=None):
    """The runs as parallel.py tasks, and the function that turns their results into check.py entries."""
    runs = runs_for(payload)
    return [("power_off_cases", "run_task", (name,)) for name in runs], lambda done: judge(dict(zip(runs, done)))


def shots(payload, flash, png_dir):
    """The picture of the display at 0.5 s into the switch-off, with the patch. The firmware's own box is not
    saved: it shows Korg's font, which stays out of the repository."""
    png_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for file in ("blechy-power-off-emu.png",):
        dev = Dev(payload, flash, 0)
        dev.m.adapter = False
        dev.m.insert_card(SDCard(MemoryMedium(menu_cases.card_image(menu_cases.CARD_FOLDER))))
        dev.run(1.5)
        dev.m.send(POWER_KEY)
        dev.run(0.5)
        dev.m.png(png_dir / file, scale=5)
        out[file] = sha(dev.fb())
    return out


def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases", "shots"))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--png-dir", type=Path)
    a = p.parse_args()
    payload = a.patched.read_bytes()[HEADER:]
    flash = load_flash(a.flash) if a.flash else None
    if not has_hook(payload):
        print(json.dumps({"ok": False, "checks": [{"id": "power_off:hook", "ok": False, "detail": "this copy does not carry the power-off hook"}]}))
        return 1
    if a.what == "shots":
        if not a.png_dir:
            p.error("shots needs --png-dir")
        print(json.dumps(shots(payload, flash, a.png_dir), indent=1))
        return 0

    def compute():
        import parallel
        tasks, combine = cases_tasks(payload)
        checks = combine(parallel.run_tasks(tasks, {"payload": payload, "flash": flash}))
        return {"ok": all(c["ok"] for c in checks), "checks": checks}
    result = bootcache.cached_result("power_off_cases", ("cases", payload, flash or b""), compute)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
