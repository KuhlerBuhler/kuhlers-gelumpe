"""Where the places of the Sampler firmware 2.02 sit in the blue Electribe 2's (the synth's) 2.02, as recorded entries.

The patches and the emulator's cases name firmware places by their Sampler address. For the synth build each place needs
the address it has there. The answers live in `data/synth-map/*.json` (addresses and the evidence for them, nothing of
the firmware), one file per patch or topic so that nobody edits the same file:

    { "entries": [ { "from": "0xC0036B50", "to": "0xC0031A20", "kind": "code", "why": "the same function, 16 words equal (fwmap)" } ] }

`kind` is "code" (an instruction or a function entry: the same code, found by fwmap or by reading both), "data" (a table or a
string in the image), "ram" (a variable behind the image, found where the synth's code loads it) or "same" (the address is
the same in both). `from` of a place the synth does not have is not an entry: `tr` says that it has none.

    tools/patch/synthaddr.py auto --ref SAMPLER.VSB --vsb SYNTH.VSB   add what fwmap finds, as data/synth-map/auto.json
    tools/patch/synthaddr.py show 0xC0036B50 ...                       the entries for these addresses

In a builder for the synth:

    import synthaddr
    synthaddr.retarget(globals(), ["PANEL", "DISPLAY", ...])      # module constants
    text = synthaddr.source(asm_text, own=[(CODE_AT, CODE_END)])  # every 0xC0... literal of an assembler source

Both refuse a firmware address that has no entry, naming it. A builder never guesses.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])
MAP_DIR = ROOT / "data" / "synth-map"
BASE = 0xC0000000
FIRMWARE_TO = BASE + 0x08000000          # the address range the firmware's pointers live in
FREE_FROM = 0xC013C0B0                   # above this the image is free space in the Sampler (and in the synth), our own code goes there
LITERAL = re.compile(r"\b0x[Cc]0[0-9A-Fa-f]{6}\b")

_table = None


class Unmapped(Exception):
    pass


def entries():
    """Every entry of every file in data/synth-map/, as (file name, entry)."""
    out = []
    for path in sorted(MAP_DIR.glob("*.json")):
        for entry in json.loads(path.read_text())["entries"]:
            out.append((path.name, entry))
    return out


def table():
    global _table
    if _table is None:
        _table = {}
        rows = entries()
        rejected = {int(entry["from"], 16) for _, entry in rows if entry.get("rejected")}
        for name, entry in rows:
            a, b = int(entry["from"], 16), int(entry["to"], 16)
            if a in rejected:
                continue
            if _table.get(a, b) != b:
                raise ValueError(f"{name}: {entry['from']} is mapped twice, to {_table[a]:#x} and {b:#x}")
            _table[a] = b
    return _table


def reload():
    global _table
    _table = None


def tr(address):
    """The synth's address for a Sampler address, or Unmapped."""
    try:
        return table()[address]
    except KeyError:
        raise Unmapped(f"{address:#010x} has no entry in data/synth-map/ (the synth build needs one)") from None


def retarget(namespace, names):
    """Replace the module constants `names` of a builder (a dict such as globals()) by their synth addresses."""
    missing = []
    for name in names:
        try:
            namespace[name] = tr(namespace[name])
        except Unmapped as error:
            missing.append(f"{name}: {error}")
    if missing:
        raise SystemExit("the synth build cannot place:\n  " + "\n  ".join(missing))


def use(namespace, names, build):
    """Put the module constants `names` of a builder (a dict such as globals()) to the addresses of `build`: the Sampler's as the
    module states them, or the synth's. Safe to call again and for the other build, the module's own numbers are kept aside."""
    pristine = namespace.setdefault("_SAMPLER_ADDRESSES", {})
    for name in names:
        pristine.setdefault(name, namespace[name])
    if build != "synth":
        namespace.update({name: pristine[name] for name in names})
        return
    missing = []
    found = {}
    for name in names:
        try:
            found[name] = tr(pristine[name])
        except Unmapped as error:
            missing.append(f"{name}: {error}")
    if missing:
        raise SystemExit("the synth build cannot place:\n  " + "\n  ".join(missing))
    namespace.update(found)


def is_synth(payload):
    """Whether an image (the whole VSB or the payload behind its head) is the blue Electribe 2's."""
    from firmware import is_synth as check
    return check(payload[0x100:] if len(payload) == 0x200100 else payload)


def source(text, own=(), keep=()):
    """An assembler source with every firmware address literal (0xC0xxxxxx) replaced by the synth's.

    Addresses in the patch's own areas (`own`, [start, end) pairs) and the ones in `keep` stay: they are the patch's, not the firmware's.
    A literal without an entry is refused, with all of them named."""
    missing = set()

    def swap(match):
        value = int(match.group(0), 16)
        if value == BASE or value in keep or any(s <= value < e for s, e in own):
            return match.group(0)
        try:
            return f"0x{tr(value):08X}"
        except Unmapped:
            missing.add(value)
            return match.group(0)

    out = LITERAL.sub(swap, text)
    if missing:
        raise SystemExit("the synth build has no entry for: " + ", ".join(f"{a:#010x}" for a in sorted(missing)))
    return out


def literals(text):
    return {int(m.group(0), 16) for m in LITERAL.finditer(text)}


def write_js():
    """data/synth-sites.mjs: {synth address: Sampler address} of every code place, so that the hook registry (src/hooks.mjs),
    which knows the chains by the Sampler's addresses, can place a hook of a synth patch."""
    pairs = sorted((to, frm) for frm, to in table().items() if frm < BASE + 0x200000 and frm != to)
    lines = ["/**", " * The Sampler address of each place of the blue Electribe 2's firmware that has an entry in data/synth-map/.", " * Generated by tools/patch/synthaddr.py js: do not edit, add entries to data/synth-map/*.json and run it again.", " */",
             "export const SAMPLER_OF_SYNTH = new Map(["]
    lines += [f"  [0x{to:08X}, 0x{frm:08X}]," for to, frm in pairs]
    lines += ["]);", ""]
    (ROOT / "data" / "synth-sites.mjs").write_text("\n".join(lines))


def fuzzy(args):
    import bisect

    import fwmap
    import synthfind
    ref, tgt = fwmap.load(args.ref), fwmap.load(args.vsb)
    fm = fwmap.FirmwareMap(ref, tgt, refine=True)
    md = synthfind.disassembler()
    wanted = set()
    for pattern in ("tools/patch/*.py", "tools/patch/*.s", "tools/emu/*.py", "data/hooks.mjs"):
        for path in ROOT.glob(pattern):
            if not path.name.startswith("test_") and path.name not in ("fwmap.py", "synthaddr.py", "arm.py"):
                wanted |= literals(path.read_text())
    have = table()
    path = MAP_DIR / "fuzzy.json"
    out = []
    for address in sorted(wanted):
        if address in have or address < BASE + 0x1000 or address >= FREE_FROM:
            continue
        w = (address - BASE) // 4
        i = bisect.bisect_right(fm._starts, w)
        runs = [fm.runs[k] for k in (i - 1, i) if 0 <= k < len(fm.runs)]
        # where the neighbouring runs put it: the shift of the run before and of the run after
        centres = {BASE + (b - a) * 4 + (address - BASE) for a, b, _ in runs}
        lo = max(BASE, min(centres) - args.span)
        hi = min(BASE + 0x200000, max(centres) + args.span)
        best = synthfind.search(md, ref, tgt, address, lo, hi)
        if not best or best[0][0] < args.min or (len(best) > 1 and best[0][0] - best[1][0] < args.gap):
            print(f"  {address:#010x}  no clear match" + (f" (best {best[0][0]:.2f} at {best[0][1]:#x})" if best else ""))
            continue
        ratio, to = best[0]
        print(f"  {address:#010x} -> {to:#010x}  ratio {ratio:.2f}")
        out.append({"from": f"0x{address:08X}", "to": f"0x{to:08X}", "kind": "code", "why": f"synthfind: the closest instructions (ratio {ratio:.2f}), not yet read by a person", "fuzzy": True})
    path.write_text(json.dumps({"entries": out}, indent=1) + "\n")
    print(f"{len(out)} entries written to {path}")
    return 0


def mapper(payload):
    """`tr` for a loaded image: the synth's table for the blue Electribe 2's image, the identity for the Sampler's."""
    from firmware import is_synth
    return tr if is_synth(payload[0x100:] if len(payload) == 0x200100 else payload) else (lambda address: address)


def _auto(ref_path, vsb_path):
    import fwmap
    fm = fwmap.FirmwareMap(fwmap.load(ref_path), fwmap.load(vsb_path), refine=True)
    wanted = set()
    skip = ("fwmap.py", "synthaddr.py", "arm.py")
    for pattern in ("tools/patch/*.py", "tools/patch/*.s", "tools/emu/*.py", "data/hooks.mjs", "src/*.mjs", "data/*.mjs"):
        for path in ROOT.glob(pattern):
            if path.name.startswith("test_") or path.name in skip or path.name.endswith(".test.mjs"):
                continue
            wanted |= literals(path.read_text())
    have = {int(e['from'], 16) for _, e in entries() if not e.get('auto')}
    out, skipped = [], []
    for address in sorted(wanted):
        if address in have or address == BASE or FREE_FROM <= address < BASE + 0x200000:
            continue
        try:
            to = fm.at(address)
            if address < BASE + 0x100000 and not fm.same_code(address):
                skipped.append((address, "the 16 words around it differ"))
                continue
        except fwmap.Unmapped as error:
            skipped.append((address, str(error)))
            continue
        kind = "same" if to == address else ("ram" if address >= BASE + 0x200000 else "code")
        why = "fwmap: the same place (16 words equal once masked)" if kind == "code" else "fwmap: the pointer votes of the literal pools" if kind == "ram" else "fwmap: the same address"
        out.append({"from": f"0x{address:08X}", "to": f"0x{to:08X}", "kind": kind, "why": why, "auto": True})
    return out, skipped


def main():
    import argparse
    sys.path.insert(0, str(Path(__file__).parent))
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auto")
    a.add_argument("--ref", required=True, type=Path)
    a.add_argument("--vsb", required=True, type=Path)
    f = sub.add_parser("fuzzy", help="look for the code places `auto` could not find by comparing instructions; writes data/synth-map/fuzzy.json")
    f.add_argument("--ref", required=True, type=Path)
    f.add_argument("--vsb", required=True, type=Path)
    f.add_argument("--min", type=float, default=0.85, help="the best candidate needs at least this ratio")
    f.add_argument("--gap", type=float, default=0.08, help="and has to lead the second best by this much")
    f.add_argument("--span", type=lambda x: int(x, 0), default=0x6000, help="bytes to each side of the place where the neighbouring runs expect it")
    sub.add_parser("js", help="write data/synth-sites.mjs: the synth's place of every Sampler place, for src/hooks.mjs")
    s = sub.add_parser("show")
    s.add_argument("addresses", nargs="+")
    args = p.parse_args()
    if args.cmd == "fuzzy":
        return fuzzy(args)
    if args.cmd == "js":
        write_js()
        return 0
    if args.cmd == "show":
        for text in args.addresses:
            v = int(text, 0)
            print(f"{v:#010x} -> " + (f"{table()[v]:#010x}" if v in table() else "no entry"))
        return 0
    found, skipped = _auto(args.ref, args.vsb)
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    path = MAP_DIR / "auto.json"
    old = json.loads(path.read_text())["entries"] if path.exists() else []
    keep = [e for e in old if not e.get("auto")]
    merged = keep + found
    merged.sort(key=lambda e: int(e["from"], 16))
    path.write_text(json.dumps({"entries": merged}, indent=1) + "\n")
    print(f"{len(found)} entries written to {path}, {len(skipped)} addresses without one:")
    for address, why in skipped:
        print(f"  {address:#010x}  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
