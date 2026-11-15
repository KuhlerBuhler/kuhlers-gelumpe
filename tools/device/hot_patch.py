# SPDX-License-Identifier: GPL-2.0-only
"""Write the changed bytes of a new firmware image into the running image in RAM, without SOFTWARE UPDATE (DEV MODE).

The Sampler's BLECH menu has a page DEV MODE (tools/patch/script_menu.s); while it is on, BLECH WRITE may change the firmware
image in RAM (0xC0000000..0xC0200000) outside the closed regions (data/dev-closed.mjs). This tool compares the image the device
runs (the base) with a new one, sorts every changed range into "hot ok" or "full update", and writes the hot ones over USB in
small groups, each range read back. A journal keeps the base bytes; --revert writes them back. Power off and on, and the device
runs the image from the flash again. Facts and limits: docs/messungen/2026-11-14-dev-mode-sperrbereiche.md.

It never writes the card or the flash, never runs EXEC and never presses keys. --dry-run reads only.

    python3 hot_patch.py --original ORIGINAL.BIN --new NEW.VSB --checked report.json --dry-run    # the table, READ only
    python3 hot_patch.py --original ORIGINAL.BIN --new NEW.VSB --checked report.json             # asks, then writes
    python3 hot_patch.py --revert out/hot-patch/hot-patch-1a2b3c4d.json                           # the base bytes back
    python3 hot_patch.py --emu BASE.VSB --original ORIGINAL.BIN --new NEW.VSB --checked r.json    # against the emulator

The new image needs a check report (tools/emu/check.py --report) whose VSB sha256 matches; without --checked the tool runs
the full check itself (hours on a busy machine; --allow-quick runs only the start scenarios and says so). The base is
SYSTEM.VSB from the card (FILE READ) unless --base or --chain names it, and is proven against the running image first.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Appended, not put first: the emulator's spawn workers run this script again, and tools/device/backlight.py would hide
# tools/emu/backlight.py from them.
for _p in (str(HERE), str(ROOT / "tools" / "patch")):
    if _p not in sys.path:
        sys.path.append(_p)

IMAGE, IMAGE_SIZE, HEADER = 0xC0000000, 0x200000, 0x100
DSP = (0xC00F9E10, 0xC013C0B0)          # the DSP's program, uploaded at the start (tools/emu/check.py DSP_STREAM)
TRANSPORT = 0xC06BC318                  # 0 stopped, 1 playing, 2 paused, 3/4 recording; same on ht and red (script_hw.s)
SAMPLER = 0x24                          # family byte of the search answer; 0x23 is the synth
JOIN = 16                               # changed runs closer than this are one range
BLOCK = 1024                            # bytes per WRITE DATA by default
PROOF_BLOCK = 0x8000
FLAG_WRITE, FLAG_DEV, FLAG_DEV_ON = 0x2, 0x200, 0x400
JOURNALS = ROOT / "out" / "hot-patch"
PYTHON = ROOT / "tools" / "emu" / ".venv" / "bin" / "python"


# ---------------------------------------------------------------- ranges

def merge(ranges, gap=0):
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(r) for r in out]


def overlaps(a, b, ranges):
    return [r for r in ranges if r[0] < b and a < r[1]]


def minus(ranges, holes):
    """`ranges` without the bytes in `holes`."""
    pieces = list(ranges)
    for h0, h1 in holes:
        pieces = [p for q0, q1 in pieces for p in ((q0, min(q1, h0)), (max(q0, h1), q1)) if p[1] > p[0]]
    return pieces


def diff(base, new, join=JOIN):
    """Changed ranges between two image payloads as RAM addresses, word aligned, runs closer than `join` bytes joined."""
    runs, i, n = [], 0, len(base)
    while i < n:
        if i % 4096 == 0 and base[i:i + 4096] == new[i:i + 4096]:
            i += 4096
            continue
        if base[i] != new[i]:
            j = i + 1
            while j < n and base[j] != new[j]:
                j += 1
            runs.append((IMAGE + (i & ~3), IMAGE + ((j + 3) & ~3)))
            i = j
        else:
            i += 1
    return merge(runs, join)


def payload_of(raw):
    if len(raw) != HEADER + IMAGE_SIZE:
        raise SystemExit(f"a VSB is {HEADER + IMAGE_SIZE:#x} bytes (header and image), this one {len(raw):#x}")
    return raw[HEADER:]


def at(payload, a, b):
    return payload[a - IMAGE:b - IMAGE]


# ---------------------------------------------------------------- what may not be written hot

def closed_regions(build):
    """data/dev-closed.mjs for one build: the regions the firmware keeps closed with DEV MODE on."""
    text = (ROOT / "data" / "dev-closed.mjs").read_text()
    part = re.search(rf"\b{build}: \[(.*?)\n  \]", text, re.S)
    if not part:
        raise SystemExit(f"data/dev-closed.mjs has no build {build}")
    return [(int(a, 16), int(b, 16)) for a, b in re.findall(r"start: (0x[0-9a-f]+), end: (0x[0-9a-f]+)", part.group(1))]


def declared_ram():
    """The RAM every patch declares (`ram` and `shares` of data/patches/*.json): data, never code."""
    out = []
    for path in sorted((ROOT / "data" / "patches").glob("*.json")):
        try:
            doc = json.loads(path.read_text())
        except ValueError:
            continue
        for r in (doc.get("ram") or []) + (doc.get("shares") or []) if isinstance(doc, dict) else []:
            a = int(r["at"], 16)
            out.append((a, a + int(r["length"])))
    return merge(out)


def traced_writes(build):
    """The firmware's own writes into the image after the start (data/traces/image-writes-<build>.json)."""
    doc = json.loads((ROOT / "data" / "traces" / f"image-writes-{build}.json").read_text())
    return [(int(a, 16), int(b, 16)) for a, b in doc["ranges"]]


def settled(payload, flash=None, seconds=5.0):
    """Bytes of the image the firmware itself changes within `seconds` after power on, in the emulator (.data, start values)."""
    sys.path.insert(0, str(ROOT / "tools" / "emu"))
    from machine import Machine
    m = Machine(bytes(payload), flash)
    m.run_until(seconds)
    ram = bytes(m.uc.mem_read(IMAGE, IMAGE_SIZE))
    return diff(payload, ram)


def start_phase(payload, flash=None):
    """Code and data the start reads, over every start scenario (tools/emu/bootmap.py)."""
    sys.path.insert(0, str(ROOT / "tools" / "emu"))
    import bootmap
    ranges, _ = bootmap.start_phase(bytes(payload), flash)
    return merge([tuple(r) for r in ranges["code"]] + [tuple(r) for r in ranges["data"]])


def build_of(payload):
    sys.path.insert(0, str(ROOT / "tools" / "emu"))
    from sysex_trace import build_name
    return build_name(bytes(payload))


class Context:
    """Everything the sorting needs besides the bytes: closed regions, DSP, start phase, data areas."""

    def __init__(self, closed, start, data, dsp=DSP):
        self.closed, self.start, self.data, self.dsp = merge(closed), merge(start), merge(data), dsp

    @classmethod
    def measure(cls, base, new, build, cache=JOURNALS, flash=None, say=print):
        """The context for base and new, the emulator parts cached per image sha in `cache`."""
        parts = {}
        for name, payload in (("base", base), ("new", new)):
            path = cache / f"context-{hashlib.sha256(payload).hexdigest()[:12]}.json"
            if path.exists():
                parts[name] = json.loads(path.read_text())
                continue
            say(f"emulator: start phase and start values of the {name} image (a few minutes, cached in {path.name})")
            doc = {"start": start_phase(payload, flash), "settled": settled(payload, flash)}
            cache.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc))
            parts[name] = doc
        start = [tuple(r) for p in parts.values() for r in p["start"]]
        data = declared_ram() + traced_writes(build) + [tuple(r) for p in parts.values() for r in p["settled"]]
        return cls(closed_regions(build), start, data)


# ---------------------------------------------------------------- sorting and order

def classify(ranges, base, new, running, ctx):
    """One row per changed range: {start, end, cls ("hot", "full", "skip"), reason}. `running(a, b)` is what the device has."""
    rows = []
    for a, b in ranges:
        row = {"start": a, "end": b}
        live = running(a, b)
        if overlaps(a, b, ctx.closed):
            row.update(cls="full", reason="closed region (SysEx or flash path)")
        elif overlaps(a, b, [ctx.dsp]):
            row.update(cls="full", reason="DSP program, uploaded at the start")
        elif overlaps(a, b, ctx.start):
            row.update(cls="full", reason="start phase")
        elif overlaps(a, b, ctx.data):
            row.update(cls="full", reason="data the firmware writes (RAM area, start value or runtime write)")
        elif live == at(new, a, b):
            row.update(cls="skip", reason="already applied")
        elif live != at(base, a, b):
            row.update(cls="full", reason="live data: the device's bytes differ from the base")
        else:
            row.update(cls="hot", reason="")
        rows.append(row)
    return rows


def targets(word, addr):
    """Where a word points into the image: an ARM B/BL/BLX target, or the word itself as a literal address."""
    out = []
    if (word >> 25) & 7 == 5:
        off = word & 0xFFFFFF
        off = off - (1 << 24) if off & 0x800000 else off
        out.append(addr + 8 + (off << 2))
    if IMAGE <= word < IMAGE + IMAGE_SIZE:
        out.append(word)
    return out


def group(rows, new):
    """Rows tied together: a range whose new words branch or point into another changed range is in that range's group.
    Returns a list of groups (lists of rows), in address order of their first row."""
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, r in enumerate(rows):
        for addr in range(r["start"], r["end"] - 3, 4):
            word = struct.unpack_from("<I", new, addr - IMAGE)[0]
            for t in targets(word, addr):
                for j, other in enumerate(rows):
                    if j != i and other["start"] <= t < other["end"]:
                        parent[find(i)] = find(j)
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(find(i), []).append(r)
    return sorted(groups.values(), key=lambda g: g[0]["start"])


def order(rows, base):
    """Inside a group: ranges over FF (new code in free space) first, then other ranges, single words (branches into the new
    code) last."""
    def rank(r):
        free = set(at(base, r["start"], r["end"])) == {0xFF}
        return (0 if free else 2 if r["end"] - r["start"] <= 4 else 1, r["start"])
    return sorted(rows, key=rank)


def plan(base, new, running, ctx, block=BLOCK):
    """The table and the write order: {rows, groups (ordered rows of the hot ranges), warnings, full}."""
    rows = classify(diff(base, new), base, new, running, ctx)
    hot = [r for r in rows if r["cls"] == "hot"]
    groups = [order(g, base) for g in group(hot, new)]
    for n, g in enumerate(groups, 1):
        for r in g:
            r["group"] = n
    warnings = [f"group {n}: {sum(r['end'] - r['start'] for r in g)} bytes in {len(g)} ranges, more than one block of {block}: "
                "not atomic, the device may crash while it is written" for n, g in enumerate(groups, 1)
                if sum(r["end"] - r["start"] for r in g) > block]
    return {"rows": rows, "groups": groups, "warnings": warnings, "full": [r for r in rows if r["cls"] == "full"]}


def table(p):
    lines = [f"{'range':23} {'bytes':>6}  {'class':11} group  reason"]
    for r in p["rows"]:
        cls = {"hot": "hot ok", "full": "full update", "skip": "skip"}[r["cls"]]
        lines.append(f"{r['start']:#010x}..{r['end']:#010x} {r['end'] - r['start']:6}  {cls:11} {r.get('group', ''):>5}  {r['reason']}")
    return "\n".join(lines + [f"warning: {w}" for w in p["warnings"]])


# ---------------------------------------------------------------- the check report

def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def accept_report(report, new_raw, allow_quick=False):
    """None when the report proves a passed check of exactly this VSB, else why not."""
    if report.get("vsb_sha256") != sha(new_raw):
        return "the check report is for another VSB (sha256 differs)"
    if not report.get("ok"):
        return "the check report says the check failed"
    if report.get("partial"):
        return "the check report covers only part of the cases (--cases or --shard)"
    if report.get("quick") and not allow_quick:
        return "the check report is a quick check (start scenarios only); pass --allow-quick to accept it"
    return None


def run_check(original, new_path, allow_quick, say=print):
    out = JOURNALS / f"check-{sha(new_path.read_bytes())[:8]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(PYTHON if PYTHON.exists() else sys.executable), str(ROOT / "tools" / "emu" / "check.py"), "--base", str(original),
           "--patched", str(new_path), "--report", str(out)] + (["--quick"] if allow_quick else [])
    say("running " + ("the QUICK check (start scenarios only, not the patches' cases)" if allow_quick else "the full check") + ": " + " ".join(cmd))
    subprocess.run(cmd, stdout=subprocess.DEVNULL, check=False)
    if not out.exists():
        raise SystemExit("check.py wrote no report")
    return json.loads(out.read_text())


# ---------------------------------------------------------------- the device

def progress(label, done, total):
    d = Path.home() / ".claude" / "progress"
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{label}.json.tmp"
        tmp.write_text(json.dumps({"label": label, "done": done, "total": total, "updatedAt": time.time()}))
        tmp.replace(d / f"{label}.json")
    except OSError:
        pass


def file_read(blech, size=HEADER + IMAGE_SIZE, block=4096, say=print):
    """SYSTEM.VSB from the card, FILE READ."""
    import blech_sysex as spec
    out = b""
    while len(out) < size:
        n = min(block, size - len(out))
        func, body = blech.talk(spec.FUNC_FREAD, struct.pack("<II", len(out), n))
        status, _, length, crc, total = struct.unpack_from("<5I", body)
        data = body[20:20 + length]
        if func != spec.REPLY_FREAD or status or length != n or zlib.crc32(data) != crc:
            raise SystemExit(f"FILE READ of SYSTEM.VSB at {len(out):#x}: status {status}; pass --base with the VSB the device runs")
        out += data
        progress("hot-patch", len(out), size)
    return out


def proof_ranges(ctx, changed, mode):
    """What the base proof reads: every code range of the image (full), or the 4 KiB blocks around the changed ranges (near)."""
    if mode == "near":
        want = merge([(a & ~0xFFF, (b + 0xFFF) & ~0xFFF) for a, b in changed])
    else:
        want = [(IMAGE, IMAGE + IMAGE_SIZE)]
    return minus(want, ctx.data)


def prove(blech, base, ctx, changed, mode="near", say=print):
    """READ the running image over the proof ranges and compare with the base; stops on the first difference."""
    ranges = proof_ranges(ctx, changed, mode)
    total, done = sum(b - a for a, b in ranges), 0
    say(f"base proof ({mode}): reading {total} bytes in {len(ranges)} ranges")
    for a, b in ranges:
        for x in range(a, b, PROOF_BLOCK):
            y = min(b, x + PROOF_BLOCK)
            got = blech.read(x, y - x)
            if got != at(base, x, y):
                bad = next(i for i in range(y - x) if got[i] != at(base, x, y)[i])
                raise SystemExit(f"base proof: the device runs other bytes at {x + bad:#010x} than the base; nothing written. "
                                 "Is the card's SYSTEM.VSB the one that was flashed? Pass --base with the image the device runs.")
            done += y - x
            progress("hot-patch", done, total)
    return total


def write_group(blech, rows, new, block):
    for r in rows:
        for x in range(r["start"], r["end"], block):
            y = min(r["end"], x + block)
            blech.write(x, at(new, x, y))
        if blech.read(r["start"], r["end"] - r["start"]) != at(new, r["start"], r["end"]):
            raise SystemExit(f"read back after the write at {r['start']:#010x}: other bytes; run --revert with the journal")


def journal_doc(base_path, base_raw, new_path, new_raw, groups, base, new, partial, chain=None):
    return {"schema": 1, "base": {"path": str(base_path), "sha256": sha(base_raw)}, "new": {"path": str(new_path), "sha256": sha(new_raw)},
            "chain": chain, "partial": partial, "written_groups": 0,
            "groups": [[{"start": f"{r['start']:#010x}", "end": f"{r['end']:#010x}", "base": at(base, r["start"], r["end"]).hex(),
                         "new": at(new, r["start"], r["end"]).hex()} for r in g] for g in groups]}


def chained_base(journal_path):
    """The image the device runs after the journal's hot patch: its base with every written group's new bytes."""
    doc = json.loads(Path(journal_path).read_text())
    raw = Path(doc["base"]["path"]).read_bytes()
    if sha(raw) != doc["base"]["sha256"]:
        raise SystemExit(f"{doc['base']['path']} is not the base the journal recorded")
    image = bytearray(payload_of(raw))
    for g in doc["groups"][:doc["written_groups"]]:
        for r in g:
            a = int(r["start"], 16)
            image[a - IMAGE:a - IMAGE + len(bytes.fromhex(r["new"]))] = bytes.fromhex(r["new"])
    return bytes(image), raw


def revert(blech, journal_path, block=BLOCK, say=print):
    """Write the journal's base bytes back, last group first; a range already at its base is left alone."""
    doc = json.loads(Path(journal_path).read_text())
    groups = doc["groups"][:doc["written_groups"]]
    for g in reversed(groups):
        for r in reversed(g):
            a, old, new = int(r["start"], 16), bytes.fromhex(r["base"]), bytes.fromhex(r["new"])
            live = blech.read(a, len(old))
            if live == old:
                continue
            if live != new:
                raise SystemExit(f"{a:#010x}: the device has neither the base nor the new bytes; nothing more written")
            for x in range(0, len(old), block):
                blech.write(a + x, old[x:x + block])
            if blech.read(a, len(old)) != old:
                raise SystemExit(f"{a:#010x}: read back after the revert differs")
    doc["written_groups"] = 0
    Path(journal_path).write_text(json.dumps(doc, indent=1))
    say(f"reverted {sum(len(g) for g in groups)} ranges; the device runs the base again")


def check_device(blech, emulator=False):
    """INFO and the search say: a Sampler with DEV MODE built in and on, writes allowed."""
    if blech.head[4] != SAMPLER:
        raise SystemExit("not an Electribe Sampler; DEV MODE is only on the Sampler")
    if not blech.flags & FLAG_DEV:
        raise SystemExit("this firmware has no DEV MODE (INFO without FLAG_DEV)")
    if not blech.flags & FLAG_WRITE:
        raise SystemExit("this firmware's BLECH refuses writes")
    if not blech.flags & FLAG_DEV_ON:
        raise SystemExit("DEV MODE is off: BLECH > DEV MODE, turn the dial up (it is off again after every power on)")


def connect(emu=None, dev_on=True):
    from remote_press import Blech
    if emu:
        from led_show import emulator_ask
        ask, m = emulator_ask(emu)
        if dev_on:
            import blech_sysex as spec
            m.uc.mem_write(spec.DEV_FLAG, struct.pack("<I", spec.DEV_MAGIC))
        return Blech(ask), m
    from led_show import mido_ask
    return Blech(mido_ask()), None


def run(blech, base_raw, base_path, new_raw, new_path, ctx, *, dry_run=False, partial=False, block=BLOCK, proof="near",
        playing_ok=False, confirm=None, chain=None, base_payload=None, journals=JOURNALS, say=print):
    """Steps 2 to 10 against a connected device. Returns the plan and the journal path (None on a dry run)."""
    base = base_payload or payload_of(base_raw)
    new = payload_of(new_raw)
    check_device(blech)
    if block > blech.largest:
        block = blech.largest
    changed = diff(base, new)
    prove(blech, base, ctx, changed, proof, say)
    p = plan(base, new, lambda a, b: blech.read(a, b - a), ctx, block)
    say(table(p))
    if p["full"] and not partial:
        say(f"{len(p['full'])} range(s) need a full update (SOFTWARE UPDATE); nothing written. --partial writes the hot ones anyway.")
        return p, None
    if dry_run or not p["groups"]:
        say("dry run: nothing written" if dry_run else "nothing to write")
        return p, None
    if not playing_ok and struct.unpack("<I", blech.read(TRANSPORT, 4))[0] != 0:
        raise SystemExit("the sequencer runs; stop it first (or --while-playing)")
    count = sum(r["end"] - r["start"] for g in p["groups"] for r in g)
    if confirm and not confirm(f"write {count} bytes in {len(p['groups'])} group(s) into the running image?"):
        raise SystemExit("not written")
    doc = journal_doc(base_path, base_raw, new_path, new_raw, p["groups"], base, new, bool(p["full"]), chain)
    journals.mkdir(parents=True, exist_ok=True)
    path = journals / f"hot-patch-{sha(new_raw)[:8]}.json"
    path.write_text(json.dumps(doc, indent=1))
    for n, g in enumerate(p["groups"], 1):
        doc["written_groups"] = n          # before the write: a crash in the middle still reverts this group
        path.write_text(json.dumps(doc, indent=1))
        write_group(blech, g, new, block)
        progress("hot-patch", n, len(p["groups"]))
    say(f"written: {count} bytes in {len(p['groups'])} group(s); journal {path}")
    return p, path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--original", type=Path, help="Korg's or Hacktribe's ORIGINAL.BIN the patches were built on (check.py --base)")
    ap.add_argument("--new", type=Path, help="the new VSB")
    ap.add_argument("--set", type=Path, help="build the new VSB from --original with this patch set (tools/patch/apply.mjs)")
    ap.add_argument("--checked", type=Path, help="check.py --report of the new VSB")
    ap.add_argument("--allow-quick", action="store_true", help="accept or run a quick check (start scenarios only)")
    ap.add_argument("--base", type=Path, help="the VSB the device runs (default: SYSTEM.VSB from the card)")
    ap.add_argument("--chain", type=Path, help="the journal of the last hot patch in this power-on: its result is the base")
    ap.add_argument("--emu", type=Path, help="talk to the emulator booted with this VSB (DEV MODE poked on) instead of USB")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--partial", action="store_true", help="write the hot ranges even when others need a full update")
    ap.add_argument("--block", type=int, default=BLOCK)
    ap.add_argument("--proof", choices=("full", "near"), default="near",
                    help="base proof near the changes (default) or over the whole image; full stops on a device, whose firmware "
                         "writes about 41 KB of the image at run time that the emulator does not see")
    ap.add_argument("--while-playing", action="store_true")
    ap.add_argument("--yes", action="store_true", help="do not ask before writing")
    ap.add_argument("--revert", type=Path, help="write a journal's base bytes back")
    a = ap.parse_args(argv)

    if a.revert:
        blech, _ = connect(a.emu)
        check_device(blech)
        revert(blech, a.revert, a.block)
        return 0
    if not a.original or not (a.new or a.set):
        ap.error("--original and --new (or --set) are needed")
    new_path = a.new
    if a.set:
        new_path = JOURNALS / f"new-{int(time.time())}.VSB"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["node", str(ROOT / "tools" / "patch" / "apply.mjs"), "--vsb", str(a.original), "--set", str(a.set),
                        "--out", str(new_path)], check=True)
    new_raw = new_path.read_bytes()
    payload_of(new_raw)
    report = json.loads(a.checked.read_text()) if a.checked else run_check(a.original, new_path, a.allow_quick)
    why = accept_report(report, new_raw, a.allow_quick)
    if why:
        raise SystemExit(f"{why}; nothing written")
    if report.get("quick"):
        print("NOTE: the new image passed only the QUICK check (start scenarios), not the patches' own cases")

    blech, _ = connect(a.emu)
    check_device(blech)
    chain = None
    if a.chain:
        base_payload, base_raw = chained_base(a.chain)
        base_path, chain = json.loads(a.chain.read_text())["base"]["path"], str(a.chain)
    elif a.base:
        base_raw, base_path, base_payload = a.base.read_bytes(), a.base, None
    else:
        print("reading SYSTEM.VSB from the card (FILE READ)")
        base_raw, base_path, base_payload = file_read(blech), "card:SYSTEM.VSB", None
        JOURNALS.mkdir(parents=True, exist_ok=True)
        (JOURNALS / f"card-{sha(base_raw)[:8]}.VSB").write_bytes(base_raw)
        base_path = JOURNALS / f"card-{sha(base_raw)[:8]}.VSB"
    base = base_payload or payload_of(base_raw)
    new = payload_of(new_raw)
    build = build_of(new)
    if build not in ("ht", "red"):
        raise SystemExit("DEV MODE is only on the Sampler (ht, red)")
    ctx = Context.measure(base, new, build)
    confirm = None if a.yes or a.emu else (lambda q: input(q + " [y/N] ").strip().lower() == "y")
    p, _ = run(blech, base_raw, base_path, new_raw, new_path, ctx, dry_run=a.dry_run, partial=a.partial, block=a.block,
               proof=a.proof, playing_ok=a.while_playing, confirm=confirm, chain=chain, base_payload=base_payload)
    return 1 if p["full"] and not a.partial else 0


if __name__ == "__main__":
    sys.exit(main())
