# SPDX-License-Identifier: GPL-2.0-only
"""Emulator traces for dev mode (docs/messungen/2026-11-14-dev-mode-sperrbereiche.md).

With DEV MODE on, BLECH WRITE may write the firmware image in RAM. The code that carries a write (the SysEx path) and the
code that writes the flash (the flash path) stay closed even then. Which code that is, is measured here, not typed:

  sysex   the image code the emulator runs while it answers the device search, INFO, READ, WRITE BEGIN and DATA and a
          refusal over DIN, minus the code it also runs while idle on the main screen
  flash   the image code it runs inside the firmware's flash write (0xC0029AB8) when the BLECH settings go to the flash
          without a card (#521), and while SOFTWARE UPDATE writes the firmware, minus the idle code
  writes  the image bytes the firmware itself writes after the start (its own run time variables in the image): idle, a
          SysEx session, a pattern played for two seconds

USB-MIDI is not emulated, so the USB receive path is not in the sysex trace; it is closed by the constants of
tools/patch/blech_sysex.py instead (the two hooked functions, PORT_OF, TX_*), see the measurement file.

    tools/emu/.venv/bin/python tools/emu/sysex_trace.py sysex --patched out/devmode/ht-base.VSB --out data/traces/sysex-path-ht.json
    tools/emu/.venv/bin/python tools/emu/sysex_trace.py flash --patched out/devmode/ht-base.VSB --out data/traces/flash-path-ht.json
    tools/emu/.venv/bin/python tools/emu/sysex_trace.py writes --patched out/devmode/ht-base.VSB --out data/traces/image-writes-ht.json

Each output is {"what", "build", "vsb_sha256", "gap", "ranges": [[start, end), ...]} with RAM addresses as hex strings.

    tools/emu/.venv/bin/python tools/emu/sysex_trace.py closed [--check]

writes data/dev-closed.mjs from the constants of tools/patch/blech_sysex.py and the sysex and flash traces of ht and red:
the regions inside the firmware image that stay closed with DEV MODE on (data/protected.mjs). --check only compares.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import blech_sysex as spec  # noqa: E402
import node_json  # noqa: E402

IMAGE, IMAGE_END = 0xC0000000, 0xC0200000
GAP_CODE = 0x40                 # blocks closer than this are one range: a function's blocks the run did not take lie between
GAP_DATA = 0x10
FLASH_WRITE = 0xC0029AB8        # (object, address, length, source): the firmware's flash write (tools/patch/script_start_sampler.s)
IDLE_WINDOWS = 8                # idle samples of IDLE_SECONDS each; their union is taken off a scenario's blocks
IDLE_SECONDS = 2.0
SESSIONS = 2                    # the SysEx session runs this often; only blocks every run took count (timing noise of other tasks drops out)
# our own areas are closed by the constants of blech_sysex.py; they are left out of a trace so it shows only the firmware's code
OWN = ((spec.CODE_AT, spec.CODE_END), (spec.SAMPLE_AT, spec.SAMPLE_END), (spec.TABLE_AT, spec.TABLE_END))


def merge(ranges, gap):
    out = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return [(a & ~3, (b + 3) & ~3) for a, b in out]


def drop_own(ranges):
    out = []
    for a, b in ranges:
        if not any(a >= lo and b <= hi for lo, hi in OWN):
            out.append((a, b))
    return out


class Blocks:
    """The image's basic blocks the CPU runs while `on`, collected per name."""

    def __init__(self, uc):
        import unicorn
        self.on, self.got = False, set()
        uc.hook_add(unicorn.UC_HOOK_BLOCK, self._block, begin=IMAGE, end=IMAGE_END - 1)
        uc.ctl_flush_tb()

    def _block(self, _uc, addr, size, _data):
        if self.on:
            self.got.add((addr, addr + size))

    def take(self):
        got, self.got = self.got, set()
        return got


def idle(dev, blocks):
    seen = set()
    for _ in range(IDLE_WINDOWS):
        blocks.on = True
        dev.run(IDLE_SECONDS)
        blocks.on = False
        seen |= blocks.take()
    return seen


def build_name(payload):
    import synthaddr
    if synthaddr.is_synth(payload):
        return "blue"
    import sysex_cases
    return "ht" if sysex_cases.build_of(payload) == "hacktribe" else "red"


def report(what, payload, raw, ranges, gap, notes):
    return {"what": what, "build": build_name(payload), "vsb_sha256": hashlib.sha256(raw).hexdigest(), "gap": gap,
            "notes": notes, "ranges": [[f"{a:#010x}", f"{b:#010x}"] for a, b in ranges]}


def trace_sysex(raw, flash=None):
    """The SysEx path over DIN."""
    payload = raw[0x100:]
    import sysex_cases as sc
    dev = sc.Dev(payload, flash, 0)
    dev.run(1.0)
    blocks = Blocks(dev.m.uc)
    quiet = idle(dev, blocks)
    lk = sc.Link(dev)
    busy = None
    for _ in range(SESSIONS):
        blocks.on = True
        lk.find_channel()
        lk.info()
        lk.read(IMAGE + 0x40, 64)
        lk.read(IMAGE + 0x40, spec.MAX_BLOCK)
        lk.write(sc.SCRATCH, bytes(range(256)) * 4)
        lk.write(0xC0100000, bytes(16), send_data=False)          # a refusal at BEGIN
        lk.write(sc.SCRATCH, bytes(64), crc=1)                      # a bad CRC
        lk.flash(0x220000, 256)
        blocks.on = False
        got = blocks.take()
        busy = got if busy is None else busy & got
        quiet |= idle(dev, blocks)
    ranges = drop_own(merge(busy - quiet, GAP_CODE))
    return ranges, f"{len(busy)} blocks in every one of {SESSIONS} sessions, {len(quiet)} idle, {len(busy - quiet)} only in the sessions"


def trace_flash(raw, flash=None):
    """The flash path: inside the firmware's flash write when the BLECH settings go to the flash, and SOFTWARE UPDATE."""
    payload = raw[0x100:]
    import unicorn
    import menu_cases as mc
    dev = mc.boot(payload, flash, adapter=True, card=False, seconds=1.2)
    blocks = Blocks(dev.m.uc)
    quiet = idle(dev, blocks)
    uc = dev.m.uc
    calls = []

    def entered(u, _addr, _size, _data):
        lr = u.reg_read(unicorn.arm_const.UC_ARM_REG_LR) & ~1
        calls.append(lr)
        blocks.on = True

        def left(u2, _a, _s, _d):
            blocks.on = False
            u2.hook_del(handle[0])
        handle = [u.hook_add(unicorn.UC_HOOK_CODE, left, begin=lr, end=lr)]

    uc.hook_add(unicorn.UC_HOOK_CODE, entered, begin=FLASH_WRITE, end=FLASH_WRITE)
    uc.ctl_flush_tb()
    mc.goto_group(dev, mc.GROUP_FEATURES, mc.FEAT_TM)
    dev.turn(-1, wait=0)
    dev.run(4.0)
    settings = blocks.take()
    blocks.on = False

    update, note = trace_update(raw, flash)
    busy = settings | update
    ranges = merge(busy - quiet, GAP_CODE)
    return drop_own(ranges), (f"flash write entered {len(calls)} times from {[hex(c) for c in calls[:4]]}; {len(settings)} blocks inside it, "
                              f"{len(update)} during SOFTWARE UPDATE ({note}), {len(quiet)} idle")


def trace_update(raw, flash=None):
    """SOFTWARE UPDATE with the same file on the card: the blocks from the confirming ENTER until the flash is quiet."""
    import synth_update_probe as sup
    payload = raw[0x100:]
    import hacktribe_blue_probe as hb
    import machine
    import synthaddr
    if flash is None:
        flash = bytes(machine.hardware_flash("blue" if synthaddr.is_synth(payload) else "red"))
    start = hb.device_flash(raw, flash)                      # a flash that holds the running image, as on the device
    folder = sup.update_folder(sup.probe_empty_card(payload, start, None)["opened"])
    if folder is None:
        return set(), "the firmware asked for no SYSTEM.VSB"
    rig = sup.Rig(payload, start, {f"/KORG/{folder}/System/SYSTEM.VSB": raw})
    if not sup.boot_to_main(rig):
        return set(), "did not reach the main screen"
    log = []
    rig.to_software_update(log)
    blocks = Blocks(rig.m.uc)
    quiet = set()
    for _ in range(IDLE_WINDOWS):
        blocks.on = True
        rig.run(IDLE_SECONDS)
        blocks.on = False
        quiet |= blocks.take()
    base = rig.flash_busy()
    rig.press("menu", 1.5)
    blocks.on = True
    spent, stable, last, presses = 0.0, 0, base, 0
    while spent < 120 and stable < 4:
        rig.run(1.0)
        spent += 1.0
        now = rig.flash_busy()
        stable = stable + 1 if now == last and now != base else 0     # quiet only counts once the update wrote
        last = now
        if now == base and presses < 4 and spent >= 2:
            rig.press("menu", 1.5)
            presses += 1
    blocks.on = False
    got = blocks.take()
    erases, programs = rig.flash_busy()
    return got - quiet, f"{erases - base[0]} erases, {programs - base[1]} programs, {presses} more ENTER presses"


def trace_writes(raw, flash=None):
    """The image bytes the firmware writes after the start."""
    payload = raw[0x100:]
    import unicorn
    import sysex_cases as sc
    dev = sc.Dev(payload, flash, 0)
    dev.run(1.0)
    written = set()

    def wrote(_uc, _access, addr, size, _value, _data):
        written.add((addr, addr + size))

    dev.m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, wrote, begin=IMAGE, end=IMAGE_END - 1)
    dev.run(3.0)
    lk = sc.Link(dev)
    lk.find_channel()
    lk.info()
    lk.read(IMAGE + 0x40, 1024)
    lk.write(sc.SCRATCH, bytes(512))
    dev.press("sequencer", 2.0)
    dev.press("sequencer", 1.0)
    dev.run(2.0)
    ranges = [r for r in merge(written, GAP_DATA)]
    return ranges, f"{len(written)} distinct writes into the image after the start"


CLOSED_FILE = ROOT / "data" / "dev-closed.mjs"
CLOSED_BUILDS = ("ht", "red")      # the Sampler builds; the synth has no DEV MODE
CLOSED_MAX = 100                   # regions per build; the table holds about 136 more than today's (TABLE_END - TABLE_AT)


def constant_ranges():
    """Our own SysEx code and data, from the constants: code, sample code, table, state with DEV_FLAG and the buffer, the
    file area, the two hooked words."""
    return [
        (spec.CODE_AT, spec.CODE_END, "CODE_AT"), (spec.SAMPLE_AT, spec.SAMPLE_END, "SAMPLE_AT"),
        (spec.TABLE_AT, spec.TABLE_END, "TABLE_AT"), (spec.STATE, spec.BUF_END, "STATE, DEV_FLAG, BUF"),
        (spec.FILE_AREA, spec.FILE_AREA_END, "FILE_AREA"), (spec.CLASSIFY_HOOK, spec.CLASSIFY_HOOK + 4, "CLASSIFY_HOOK"),
        (spec.PROCESS_HOOK, spec.PROCESS_HOOK + 4, "PROCESS_HOOK"),
    ]


DECLARED = ("import {allowedRegions} from './src/plan.mjs'; const b = process.argv[1] === 'ht' ? 'hacktribe' : 'stock';"
            "console.log(JSON.stringify(allowedRegions({build: b}).map(r => [r.start, r.end])));")


def node_requests():
    """None kept in data/emu/node-results.json: declared() reads src/plan.mjs, which many changes touch, and this tool for
    the developer runs from a checkout with Node."""


def declared(build):
    """The editor's declared writes in the image (src/plan.mjs): a closed region may not cover one, or the firmware would
    refuse an edit the editor makes every day."""
    got = node_json.run(DECLARED, build)
    return sorted((a, b) for a, b in got if a < IMAGE_END and b > IMAGE)


def cut(ranges, holes):
    """`ranges` without the bytes of `holes`, each piece rounded inward to words."""
    out = []
    for a, b in ranges:
        pieces = [(a, b)]
        for h0, h1 in holes:
            nxt = []
            for p0, p1 in pieces:
                if h1 <= p0 or h0 >= p1:
                    nxt.append((p0, p1))
                    continue
                if p0 < h0:
                    nxt.append((p0, h0 & ~3))
                if h1 < p1:
                    nxt.append(((h1 + 3) & ~3, p1))
            pieces = nxt
        out += [(p0, p1) for p0, p1 in pieces if p1 > p0]
    return out


def closed_regions(build, holes=None):
    """The closed regions of one build: the constants as they are, the traced ranges merged with the smallest gap (0x40 and
    up, doubled) that keeps the whole list at CLOSED_MAX or fewer, without the editor's declared writes."""
    holes = declared(build) if holes is None else holes
    traced = []
    for what in ("sysex", "flash"):
        doc = json.loads((ROOT / "data" / "traces" / f"{what}-path-{build}.json").read_text())
        traced += [(int(a, 16), int(b, 16)) for a, b in doc["ranges"]]
    own = [(a, b) for a, b, _ in constant_ranges()]
    gap = GAP_CODE
    while True:
        merged = [r for r in cut(merge(traced, gap), holes) if not any(r[0] >= a and r[1] <= b for a, b in own)]
        if len(merged) + len(own) <= CLOSED_MAX:
            break
        gap *= 2
    out = [{"start": a, "end": b, "from": f"tools/patch/blech_sysex.py:{name}"} for a, b, name in constant_ranges()]
    out += [{"start": a, "end": b, "from": f"data/traces/*-path-{build}.json (gap {gap:#x})"} for a, b in merged]
    folded = []
    for r in sorted(out, key=lambda r: r["start"]):
        if folded and r["start"] < folded[-1]["end"]:  # a constant inside a traced range, or the other way round
            last = folded[-1]
            last["end"] = max(last["end"], r["end"])
            last["from"] = f'{last["from"]} + {r["from"]}'
        else:
            folded.append(dict(r))
    return folded


def closed_text():
    lines = ["// Generated by tools/emu/sysex_trace.py closed from tools/patch/blech_sysex.py and data/traces/*-path-*.json; do not edit.",
             "// The regions inside the firmware image that stay closed with DEV MODE on (data/protected.mjs devClosed).",
             "export default {"]
    for build in CLOSED_BUILDS:
        lines.append(f"  {build}: [")
        for r in closed_regions(build):
            lines.append(f'    {{ start: {r["start"]:#010x}, end: {r["end"]:#010x}, from: "{r["from"]}" }},')
        lines.append("  ],")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main():
    if sys.argv[1:2] == ["closed"]:
        text = closed_text()
        if "--check" in sys.argv:
            same = CLOSED_FILE.exists() and CLOSED_FILE.read_text() == text
            print("data/dev-closed.mjs " + ("matches" if same else "differs from") + " the constants and traces", file=sys.stderr)
            return 0 if same else 1
        CLOSED_FILE.write_text(text)
        return 0
    import lifetime
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("sysex", "flash", "writes"))
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    raw = a.patched.read_bytes()
    payload = raw[0x100:]
    fn = {"sysex": trace_sysex, "flash": trace_flash, "writes": trace_writes}[a.what]
    ranges, notes = fn(raw)
    gap = GAP_DATA if a.what == "writes" else GAP_CODE
    out = report(a.what, payload, raw, ranges, gap, notes)
    text = json.dumps(out, indent=1) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
    print(f"{a.what} {out['build']}: {len(ranges)} ranges, {sum(b - c for c, b in ranges)} bytes; {notes}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
