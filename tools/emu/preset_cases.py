# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the preset-tables patch (tools/patch/preset_tables.py,
docs/messungen/2026-10-15-preset-tabellen.md).

check.py runs `cases_task` on every copy that carries the patch, red or blue (the blue's places: data/synth-map/). Two kinds
of copy come through:

  - the patch itself on a firmware without it: the factory presets are found at the same records as
    without the patch, the getters take indexes up to 127, the knob memory moved to the patch's table
    with the same bytes, every preset can be walked and selected, EXIT held at power-on boots the same way;
  - a copy the editor made of a firmware that has the patch already (presets added, records edited):
    the getters, the knob memory and the menus still hold together, every added slot has a record of its
    own, the menus reach it, and selecting the last one sends the DSP what selecting its source sends
    (the source is the earlier preset whose record it copies, found by comparing the bytes behind the name).

A copy of Korg's 2.02 with the effect catalog also has to hold Hacktribe's master effects as remakes on 33 to 36 and the
catalog's master effects from 37; a copy of Hacktribe keeps its own on 10, 11, 21 and 32 and the catalog from 33.
`ht-mfx` holds the remakes' DSP transfers against Hacktribe's own (same blocks, own values).

    tools/emu/.venv/bin/python tools/emu/preset_cases.py cases --base SYSTEM.VSB --patched NEW.VSB [--flash dump.bin]
    tools/emu/.venv/bin/python tools/emu/preset_cases.py ht-mfx --patched NEW.VSB --hacktribe HACKTRIBE.VSB
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
import preset_tables as spec  # noqa: E402
import synthaddr  # noqa: E402
from machine import load_flash  # noqa: E402
from mfx_cases import Box as MfxBox, DspLog, blank_for, open_mfx_type_page, same_dsp  # noqa: E402
from splash_cases import Dev  # noqa: E402
import lifetime  # noqa: E402
import parallel  # noqa: E402

HEADER = 0x100
IMAGE = 0xC0000000
GET = {"ifx": 0xC003E738, "mfx": 0xC003E750}
COUNT = {"ifx": 0xC003EFDC, "mfx": 0xC003EFE4}
SET_MFX = 0xC0048A64
PATTERN = 0xC033E6A4
GLOBALS = 0xC0691334
PART_BASE = 0x800
ENCODER_IFX = 4
KILL = 0x2000
BOOT_S = 6.0
BOOT_SYNTH_S = 10.0     # the blue's start takes longer to reach the main screen
NAME_END = 16           # the record's name is bytes 1 to 15; what the editor copies is the rest
MFX_DEVICE = 446        # the master stage's unit byte in a record (src/layout.mjs REC.stage.mfx)
# Hacktribe's own master effects: its slot (on a factory slot of Korg's 2.02) and the unit it plays; the remakes from the
# catalog (data/fx/catalog.mjs, `hacktribe`) go on 33 to 36 of Korg's 2.02, the catalog behind them from 37.
HT_MFX = (("Big Hall", 10, 54), ("Plate Reverb", 11, 56), ("Tap Delay Sync", 21, 60), ("Tube Drive", 32, 47))
CATALOG = Path(__file__).resolve().parents[2] / "data" / "patches" / "fx-catalog.json"


def place(payload, addr):
    """A Sampler place as this image has it."""
    return synthaddr.tr(addr) if synthaddr.is_synth(payload) else addr


def has_patch(payload):
    """True when the preset getters read their pointers from the patch's arrays."""
    return struct.unpack_from("<I", payload, place(payload, 0xC003E74C) - IMAGE)[0] == spec.ARRAY_IFX


class Box:
    def __init__(self, payload, flash, held=0):
        self.dev = Dev(bytes(payload), flash, held)
        self.dsp = DspLog(self.dev.m)
        self.dev.run(BOOT_SYNTH_S if self.dev.synth else BOOT_S)

    def raw(self, addr, n):
        """Bytes at an address the running firmware handed out: never translated as a Sampler place."""
        return bytes(self.dev.m.uc.mem_read(addr, n))

    def count(self, kind):
        return self.dev.call(COUNT[kind])

    def address(self, kind, index):
        return self.dev.call(GET[kind], index)

    def record(self, kind, index):
        return self.raw(self.address(kind, index), spec.RECORD)

    def ifx_type(self):
        return self.raw(self.dev.u32(PATTERN) + 4 + PART_BASE + 33, 1)[0]

    def mfx_type(self):
        return self.raw(self.dev.u32(PATTERN) + 4 + 61, 1)[0]

    def step_ifx(self, delta=1):
        self.dev.m.send([0x01, ENCODER_IFX, 0, delta & 0xFF, 0])
        self.dev.run(0.25)

    def set_mfx(self, value):
        self.dev.call(SET_MFX, self.dev.u32(GLOBALS) + 0x4004, value, 1)
        self.dev.run(0.3)

    def knob_rows(self, count):
        """The insert knob memory as the firmware sets it up: 16 rows of `count` bytes behind the literal of the init code."""
        table = struct.unpack_from("<I", self.dev.read(0xC00980A8, 4))[0]
        return table, self.raw(table, 16 * count)

    def goto_ifx(self, target, n):
        """Turn the INSERT encoder until the part holds type `target`, by the shorter way round."""
        for _ in range(2 * n):
            at = self.ifx_type()
            if at == target:
                return
            self.step_ifx(1 if (target - at) % n < n // 2 else -1)


def source_of(base, new, kind, n0, slot):
    """The earlier preset (1-based) whose record is the one at index `slot` but for the name, or None."""
    record = new.record(kind, slot)
    for i in range(n0):
        if base.record(kind, i)[NAME_END:] == record[NAME_END:] and base.record(kind, i)[0] == record[0]:
            return i + 1
    return None


def knob_memory_kept(base_rows, base_width, base_count, rows, count):
    keep = min(base_count, count)
    if any(value != 64 for p in range(16) for value in rows[p * count + keep:(p + 1) * count]):
        return False
    if base_width != base_count:
        return 255 not in rows
    return all(rows[p * count:p * count + keep] == base_rows[p * base_count:p * base_count + keep] for p in range(16))


def judge(base_payload, patched_payload, flash):
    checks = []

    def add(name, ok, detail):
        checks.append({"id": f"presets:{name}", "ok": bool(ok), "detail": detail})

    base, new = Box(base_payload, flash), Box(patched_payload, flash)
    patch_mode = not has_patch(base_payload)
    n0 = {k: base.count(k) for k in ("ifx", "mfx")}
    n1 = {k: new.count(k) for k in ("ifx", "mfx")}
    for kind in ("ifx", "mfx"):
        if patch_mode:
            same = all(base.record(kind, i) == new.record(kind, i) for i in range(n0[kind]))
            add(f"{kind}_factory_unchanged", n1[kind] >= n0[kind] and same and not new.dev.m.asserts,
                f"the {n0[kind]} presets of the {kind} menu come back from the getters with the same bytes as without the patch, menu length {n1[kind]} (the catalog's effects behind them)")
        rows = [new.address(kind, i) for i in (spec.OLD_SLOTS, 110, spec.CAPACITY - 1, spec.CAPACITY, 255)]
        valid = all(IMAGE <= a < IMAGE + 0x200000 - spec.RECORD for a in rows) and rows[3] == rows[2] == rows[4]
        add(f"{kind}_getter_to_127", valid,
            f"index 100, 110, 127, 128 and 255 give {[hex(a) for a in rows]}: inside the image, 128 and above clamp to 127")
    n = n1["ifx"]
    table, rows = new.knob_rows(n)
    base_table, base_rows = base.knob_rows(n0["ifx"])
    keep = min(n0["ifx"], n)
    base_row = base_payload[place(base_payload, 0xC0098084) - IMAGE]
    inconsistent = base_row != n0["ifx"]
    kept = knob_memory_kept(base_rows, base_row, n0["ifx"], rows, n)
    add("knob_memory", table == spec.EDIT_TABLE and (table != base_table or not patch_mode) and kept,
        f"the knob memory of the insert effect is at {table:#x} (the patch's table, the firmware's own was at {base_table:#x}), 16 rows of {n} bytes: "
        + (f"the base's row length is {base_row} for a menu of {n0['ifx']}, so no byte of the copy's table is left unset"
           if inconsistent else f"the first {keep} of a row as in the base after the same start, the {n - keep} added ones 64"))
    first = new.ifx_type()
    seen = [first]
    for _ in range(n + 2):
        new.step_ifx()
        seen.append(new.ifx_type())
    add("ifx_walk", seen == [(first + i) % n for i in range(n + 3)] and not new.dev.m.asserts,
        f"the INSERT type encoder walks {n + 2} steps through {n} entries and wraps from {n - 1} to 0: {seen[-5:]}")
    m = n1["mfx"]
    picked = {}
    for v in (0, m - 1):
        new.set_mfx(v)
        picked[v] = new.mfx_type()
    add("mfx_set", picked == {0: 0, m - 1: m - 1} and not new.dev.m.asserts, f"the master type setter takes 0 and {m - 1}: {picked}")
    if patch_mode:
        held = Box(patched_payload, flash, KILL)
        same = all(held.record(k, i) == base.record(k, i) for k in ("ifx", "mfx") for i in range(n0[k]))
        add("exit_held", same and not held.dev.m.asserts,
            "with EXIT held at power-on the device boots and the factory presets are the same (the patch is data only and has no code to leave out)")

    for kind in ("ifx", "mfx"):
        if n1[kind] <= n0[kind]:
            continue
        added = list(range(n0[kind], n1[kind]))
        addresses = [new.address(kind, i) for i in range(n1[kind])]
        names = [new.record(kind, i)[1:NAME_END].split(b"\0")[0] for i in added]
        add(f"{kind}_added_records", len(set(addresses)) == n1[kind] and all(names) and not new.dev.m.asserts,
            f"{len(added)} slots added to the {kind} menu ({n0[kind]} to {n1[kind]}), every one with a record of its own and a name")
        source = source_of(base, new, kind, n0[kind], n1[kind] - 1)
        if kind == "ifx":
            def dsp_for(target):
                new.goto_ifx((target - 1) % n1["ifx"], n1["ifx"])
                new.dsp.clear()
                new.step_ifx(1)
                new.dev.run(1.0)
                return new.dsp.changes()
        else:
            def mfx_dsp(index):
                new.dsp.clear()
                new.set_mfx(index)
                new.dev.run(1.0)
                return new.dsp.changes()
        if source is None:
            # edited records (the catalog, src/fx-append.mjs): no earlier preset to compare with, every slot has to reach the DSP
            sent = {i + 1: len(dsp_for(i) if kind == "ifx" else mfx_dsp(i)) for i in added}
            add(f"{kind}_added_select", all(sent.values()) and not new.dev.m.asserts,
                f"selecting each added {kind} slot sends the DSP transfers, no assertion: {sent}")
            continue
        if kind == "ifx":
            a, b = dsp_for(source - 1), dsp_for(n1["ifx"] - 1)
            add("added_ifx_dsp", len(a) > 0 and same_dsp(a, b),
                f"selecting the last added insert slot sends the DSP {len(b)} transfers, the same as preset {source}, whose record it copies ({len(a)})")
        else:
            new.set_mfx(0)
            a, b = mfx_dsp(source - 1), mfx_dsp(n1["mfx"] - 1)
            add("added_mfx_dsp", len(a) > 0 and same_dsp(a, b) and new.mfx_type() == n1["mfx"] - 1,
                f"selecting the last added master slot ({n1['mfx']}) sends the DSP {len(b)} transfers, the same as preset {source}, whose record it copies ({len(a)})")
    if n0["mfx"] == 32 and has_catalog(new):
        ht_mfx(base, new, add, flash, patched_payload)
    return checks


def name_of(box, kind, index):
    return box.record(kind, index)[1:NAME_END].split(b"\0")[0].decode("latin1")


def has_catalog(box):
    """True when the copy carries the effect catalog (src/fx-append.mjs): its first master effect is in the menu."""
    first = first_catalog_mfx()
    return any(name_of(box, "mfx", i) == first for i in range(box.count("mfx")))


def first_catalog_mfx():
    presets = json.loads(CATALOG.read_text())["presets"]
    return next(p["name"] for p in presets if p["kind"] == "mfx" and not p.get("hacktribe"))


def ht_mfx(base, new, add, flash, payload):
    """Hacktribe's master effects: remakes on 33 to 36 of Korg's 2.02, the catalog from 37; Hacktribe keeps its own and the catalog from 33."""
    first = first_catalog_mfx()
    if name_of(base, "mfx", HT_MFX[0][1] - 1) == HT_MFX[0][0]:
        kept = [name_of(new, "mfx", slot - 1) for _, slot, _ in HT_MFX]
        add("ht_mfx_hacktribe_keeps", kept == [n for n, _, _ in HT_MFX] and name_of(new, "mfx", 32) == first,
            f"Hacktribe keeps its own on 10, 11, 21, 32 ({kept}), the catalog starts at 33 with {name_of(new, 'mfx', 32)}")
        return
    got = [(name_of(new, "mfx", i), new.record("mfx", i)[MFX_DEVICE]) for i in range(32, 36)]
    add("ht_mfx_names", got == [(n, u) for n, _, u in HT_MFX] and not new.dev.m.asserts,
        f"master slots 33 to 36 hold the remakes of Hacktribe's own with its units: {got}")
    add("ht_mfx_catalog_from_37", new.count("mfx") > 36 and name_of(new, "mfx", 36) == first,
        f"the catalog's master effects start at 37 with {name_of(new, 'mfx', 36) if new.count('mfx') > 36 else None} (was 33)")
    sent = {}
    for i in range(32, 36):
        new.set_mfx(0)
        new.dsp.clear()
        new.set_mfx(i)
        new.dev.run(1.0)
        sent[i + 1] = (len(new.dsp.changes()), new.mfx_type())
    add("ht_mfx_select", all(n > 0 and t == s - 1 for s, (n, t) in sent.items()) and not new.dev.m.asserts,
        f"selecting 33 to 36 sets the type and sends the DSP transfers, no assertion: {sent}")
    page = MfxBox(payload, flash if flash is not None else blank_for(payload))
    n = new.count("mfx")
    opened = open_mfx_type_page(page)
    seen = [page.mfx()]
    for _ in range(n + 2):
        page.turn(1, 0.3)
        seen.append(page.mfx())
    add("ht_mfx_page_walk", opened and seen == [(seen[0] + i) % n for i in range(n + 3)] and not page.m.asserts,
        f"VALUE on the MFX TYPE page walks {n + 2} steps through {n} types, 33 to 36 included, and wraps from {n - 1} to 0: {seen[30:40]}")


def same_blocks(a, b):
    """True when two lists of DspLog.changes() load the same blocks: same transfers in the same order, same commands and
    lengths. The values may differ (a remake with its own values); same_dsp holds them equal as well."""
    return len(a) == len(b) and all(x[0] == y[0] and len(x[2]) == len(y[2]) for x, y in zip(a, b))


def compare_ht_mfx(patched, hacktribe):
    """The DSP transfers of the remakes on 33 to 36 against Hacktribe's own on its slots, one boot each."""
    mine, theirs = Box(patched, None), Box(hacktribe, None)

    def pick(box, index):
        box.set_mfx(0 if index else 1)
        box.dsp.clear()
        box.set_mfx(index)
        box.dev.run(1.0)
        return box.dsp.changes()
    out = {}
    for slot, (name, ht_slot, _) in enumerate(HT_MFX, 33):
        a, b = pick(mine, slot - 1), pick(theirs, ht_slot - 1)
        equal = sum(u == v for x, y in zip(a, b) for u, v in zip(x[2], y[2]))
        out[name] = {"slot": slot, "hacktribe_slot": ht_slot, "transfers": [len(a), len(b)], "same_blocks": same_blocks(a, b),
                     "same_dsp": same_dsp(a, b), "equal_words": [equal, sum(len(x[2]) for x in a)]}
    out["asserts"] = [list(mine.dev.m.asserts), list(theirs.dev.m.asserts)]
    return out


def cases_task():
    return judge(parallel.shared["base"], parallel.shared["payload"], parallel.shared["flash"])


def main():
    lifetime.load_gate()
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases", "ht-mfx"))
    p.add_argument("--base", type=Path)
    p.add_argument("--hacktribe", type=Path, help="ht-mfx: Hacktribe's own SYSTEM.VSB to compare the master remakes with")
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    a = p.parse_args()
    if a.what == "ht-mfx":
        result = compare_ht_mfx(a.patched.read_bytes()[HEADER:], a.hacktribe.read_bytes()[HEADER:])
        print(json.dumps(result, indent=1))
        return 0 if all(v["same_blocks"] for k, v in result.items() if k != "asserts") and not any(result["asserts"]) else 1
    base = a.base.read_bytes()[HEADER:]
    patched = a.patched.read_bytes()[HEADER:]
    flash = load_flash(a.flash) if a.flash else None
    if not has_patch(patched):
        print(json.dumps({"ok": False, "checks": [{"id": "presets:patch", "ok": False, "detail": "this copy does not carry the preset-tables patch"}]}))
        return 1

    def compute():
        checks = judge(base, patched, flash)
        return {"ok": all(c["ok"] for c in checks), "checks": checks}
    result = bootcache.cached_result("preset_cases", ("cases", base, patched, flash or b""), compute)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
