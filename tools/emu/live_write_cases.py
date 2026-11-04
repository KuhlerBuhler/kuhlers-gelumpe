"""Emulator cases of the live write paths (docs/messungen/2026-11-03-live-schreibwege.md): for every value the firmware
lets the user change, the setter the firmware's own page or key calls, the byte it writes, and whether a plain byte
write is enough or the setter has to run (it also fills the copy behind the pattern block or a cache).

    PYTHONPATH=tools/patch python3 tools/emu/live_write_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

Addresses are the Sampler's; dev.a() gives the synth's from data/synth-map/live-write.json.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import menu_cases  # noqa: E402
from machine import load_flash  # noqa: E402

PATTERN_PTR = 0xC033E6A4        # the pattern object; its block starts at +4
GLOBALS_PTR = 0xC033E6A0        # the globals object; its block (GLST) starts at +4
OBJECT = 0x4274                 # the pattern object: the block, then the copy for the sound engine from block 0x4000
COPY = 0x4000                   # block offset where the copy behind the block starts
GETTER = 0xC004A3E8             # the tempo getter: a call that changes nothing, so poke and setter runs see the same calls
PART_SETTER = 0xC0048460        # the part setter the knobs and encoders call: r3 the parameter number, the value on the stack
MFX = 0x4004                    # object + this: what the master effect setters get in r0
PARTS = 0x400C                  # object + this: what the part setters get in r0
PART = lambda k: 0x800 + k      # noqa: E731  block offset of part 1's byte k

# block offset, size, value, setter, kind of call, what the setter does beyond the byte
#   "copy": also the copy behind the block, "cache": also the cache at the address, "steps": also the steps,
#   "screen": also the display, "byte": nothing else in the object (a plain write is enough for the stored value)
PATTERN = {
    "tempo": (34, 2, 1405, 0xC004A80C, "std", ("screen",)),
    "swing": (36, 1, 10, 0xC004A594, "std", ("byte",)),
    "length": (37, 1, 2, 0xC004A560, "std", ("steps",)),
    "beat": (38, 1, 2, 0xC004A4F8, "std", ("byte",)),
    "key": (39, 1, 5, 0xC004A6FC, "std", ("cache", 0xC068C280, 0x10)),
    "scale": (40, 1, 7, 0xC004A77C, "std", ("cache", 0xC068C280, 0x30)),
    "chordset": (41, 1, 3, 0xC004A534, "std", ("cache", 0xC068CFD0, 0x30)),
    "playLevel": (42, 1, 20, 0xC004A698, "std", ("copy",)),
    "gateArp": (49, 1, 30, 0xC004A5F8, "std", ("byte",)),
    "alternate1314": (68, 1, 0, 0xC004A614, "alt0", ("copy",)),
    "alternate1516": (69, 1, 0, 0xC004A614, "alt1", ("copy",)),
    "mfx.touch": (60, 1, 1, 0xC00488A0, "mfx", ("copy",)),
    "mfx.type": (61, 1, 5, 0xC0048A64, "mfx", ("copy",)),
    "mfx.padX": (62, 1, 77, 0xC0048924, "mfx", ("copy",)),
    "mfx.padY": (63, 1, 77, 0xC0048984, "mfx", ("copy",)),
    "mfx.hold": (65, 1, 1, 0xC00489E4, "mfx", ("copy",)),
    "chainTo": (15104, 2, 7, 0xC004A5B0, "std", ("byte",)),
    "chainRepeat": (15106, 1, 3, 0xC004A5D4, "std", ("byte",)),
    "part.lastStep": (PART(0), 1, 5, 0xC0048CE8, "part", ("byte",)),
    "part.mute": (PART(1), 1, 1, 0xC0049330, "part", ("copy",)),
    "part.voiceAssign": (PART(2), 1, 1, 0xC00493A0, "part", ("copy",)),
    "part.motionMode": (PART(3), 1, 2, 0xC0049410, "part", ("copy",)),
    "part.padVelocity": (PART(4), 1, 1, 0xC0049478, "part", ("copy",)),
    "part.scaleMode": (PART(5), 1, 1, 0xC00492A0, "part", ("cache", 0xC068C280, 0x30)),
    "part.priority": (PART(6), 1, 1, 0xC00494E8, "part", ("copy",)),
    "part.egOn": (PART(26), 1, 1, 0xC0049664, "part", ("copy",)),
    "part.mfxSend": (PART(27), 1, 0, 0xC00496D4, "part", ("copy",)),
    "part.grooveType": (PART(28), 1, 3, 0xC0049DA4, "part", ("byte",)),
    "part.grooveDepth": (PART(29), 1, 40, 0xC0049D7C, "part", ("byte",)),
    "part.ifxOn": (PART(32), 1, 1, 0xC0049DEC, "part", ("copy",)),
}

# globals block offset, value, setter; True where the setter is only the store
GLOBAL = {
    "triggerMode": (29, 1, 0xC0047380, False), "velocityCurve": (27, 2, 0xC00472D8, True),
    "clockMode": (40, 1, 0xC00473D4, False), "channel": (41, 5, 0xC0047454, False),
    "receiveFilter": (43, 1, 0xC00474E0, False), "sendFilter": (42, 1, 0xC004748C, False),
    "syncPolarity": (17, 1, 0xC00471C0, False), "syncResolution": (18, 0, 0xC00471F8, False),
    "metronome": (16, 3, 0xC00471B0, True), "tempoLock": (36, 1, 0xC0047788, False),
    "knobMode": (28, 2, 0xC00472E8, True), "touchScaleRange": (38, 3, 0xC004754C, False),
    "lcdContrast": (30, 30, 0xC0047584, False), "audioInThru": (20, 1, 0xC0047230, False),
    "batteryMode": (32, 1, 0xC00472F8, True), "autoPowerOff": (33, 0, 0xC0047308, False),
    "powerSave": (37, 1, 0xC0047348, False), "patternChangeLock": (19, 1, 0xC00475BC, True),
    "chainMode": (31, 1, 0xC00475CC, False),
}

# the pages of the Part menu (screen 7) and the byte of part 1 each one turns
PART_PAGES = [PART(0), PART(28), PART(29), PART(2), PART(6), PART(3), PART(4), PART(5)]
# panel inputs that edit part 1 through the part setter: the input, the parameter number, the byte
PART_INPUTS = [("knob LEVEL", [2, 0, 0, 60, 0], 19, PART(24)), ("encoder SAMPLE", [1, 1, 0, 1, 0], 8, PART(8)),
               ("encoder IFX", [1, 4, 0, 1, 0], 26, PART(33))]
# panel keys that edit part 1 with their own setter
PART_KEYS = [("IFX ON", 0x21, PART(32)), ("MFX SEND", 0x1A, PART(27)), ("AMP EG", 0x20, PART(26))]


def entry(name, ok, detail):
    return {"id": f"live_write:{name}", "ok": bool(ok), "detail": str(detail)}


def boot(payload, flash):
    dev = menu_cases.boot(payload, flash, card=False, seconds=2.0)
    dev.run(0.3)
    return dev


def ram(dev, address, n):
    return bytes(dev.m.uc.mem_read(address, n))


def changed(a, b, skip=()):
    return [i for i in range(len(a)) if a[i] != b[i] and i not in skip]


def call_setter(dev, obj, kind, setter, value):
    if kind == "std":
        dev.call(setter, obj, value, 1)
    elif kind in ("alt0", "alt1"):
        dev.call(setter, obj, int(kind[-1]), value, 1)
    elif kind == "mfx":
        dev.call(setter, obj + MFX, value, 1)
    else:
        dev.call(setter, obj + PARTS, 0, value, 1)


def pattern_cases(payload, flash):
    """Each field twice on one device: first the byte written alone, then put back and written by its setter."""
    out = []
    dev = boot(payload, flash)
    for name, (off, size, value, setter, kind, effect) in PATTERN.items():
        if effect[0] == "cache":
            dev = boot(payload, flash)      # an earlier setter may have left the cache as this one leaves it
        obj = dev.u32(PATTERN_PTR)
        at = obj + 4 + off
        own = set(range(4 + off, 4 + off + size))
        cache = (dev.a(effect[1]), effect[2]) if effect[0] == "cache" else None
        old = ram(dev, at, size)
        new = value.to_bytes(size, "little")
        if old == new:
            out.append(entry(f"{name}_value", False, f"the test value {value} is already there"))
            continue
        before, fb, kept = ram(dev, obj, OBJECT), dev.fb(), cache and ram(dev, *cache)
        dev.m.uc.mem_write(at, new)
        dev.call(GETTER, obj)
        dev.run(0.3)
        poked, poked_fb, poked_cache = ram(dev, obj, OBJECT), dev.fb(), cache and ram(dev, *cache)
        dev.m.uc.mem_write(at, old)
        dev.call(GETTER, obj)
        dev.run(0.3)
        base, base_fb, base_cache = ram(dev, obj, OBJECT), dev.fb(), cache and ram(dev, *cache)
        call_setter(dev, obj, kind, setter, value)
        dev.run(0.3)
        after, after_fb, after_cache = ram(dev, obj, OBJECT), dev.fb(), cache and ram(dev, *cache)
        poke_rest = changed(before, poked, own)
        set_rest = changed(base, after, own)
        wrote = after[4 + off:4 + off + size] == new and poked[4 + off:4 + off + size] == new
        if effect[0] == "copy":
            ok = wrote and not poke_rest and any(i >= 4 + COPY for i in set_rest)
            how = f"copy behind the block at {[hex(i - 4) for i in set_rest if i >= 4 + COPY][:4]}"
        elif effect[0] == "steps":
            ok = wrote and not poke_rest and any(PART(0x30) + 4 <= i < 4 + COPY for i in set_rest)
            how = f"{len(set_rest)} more bytes, steps among them"
        elif effect[0] == "cache":
            ok = wrote and not poke_rest and poked_cache == kept and after_cache != base_cache
            how = f"cache at {cache[0]:#x} unchanged by the byte, changed by the setter"
        elif effect[0] == "screen":
            ok = wrote and not poke_rest and poked_fb == fb and after_fb != base_fb
            how = "display unchanged by the byte, changed by the setter"
        else:
            ok = wrote and not poke_rest and not set_rest
            how = "the setter writes only the byte"
        out.append(entry(f"pattern_{name}", ok, f"block {off}: {old.hex()} -> {new.hex()}; {how}; "
                         f"byte alone also changed {[hex(i - 4) for i in poke_rest][:4]}, setter also {[hex(i - 4) for i in set_rest][:6]}"))
    return out


def mfx_cases(payload, flash):
    """MASTER FX and the touchpad write touch, X and Y; MFX HOLD writes hold."""
    import unicorn
    dev = boot(payload, flash)
    obj = dev.u32(PATTERN_PTR)
    block = lambda off: ram(dev, obj + 4 + off, 1)[0]   # noqa: E731

    def key(k):
        dev.m.send([0, k, 1, 0, 0])
        dev.run(0.05)
        dev.m.send([0, k, 0, 0, 0])
        dev.run(0.3)
    calls = []
    hook = dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: calls.append(a),
                             begin=dev.a(0xC00488A0), end=dev.a(0xC00489E4))
    dev.m.uc.ctl_flush_tb()
    key(0x06)
    dev.m.send([0, 0x22, 1, 0, 0])
    dev.m.send([5, 800 >> 8, 800 & 255, 200 >> 8, 200 & 255])
    dev.run(0.3)
    touched = (block(60), block(62), block(63))
    dev.m.send([0, 0x22, 0, 0, 0])
    dev.run(0.3)
    released = block(60)
    key(0x07)
    held = block(65)
    key(0x07)
    dev.m.uc.hook_del(hook)
    dev.m.uc.ctl_flush_tb()
    entries = {dev.a(a) for a in (0xC00488A0, 0xC0048924, 0xC0048984, 0xC00489E4)}
    return [entry("mfx_touchpad", touched[0] == 1 and released == 0 and entries <= set(calls),
                  f"touch, X, Y while held {touched}, touch after release {released}; setters called {[hex(a) for a in sorted(entries & set(calls))]}"),
            entry("mfx_hold_key", held == 1 and block(65) == 0, f"hold after MFX HOLD {held}, after the second press {block(65)}")]


def page_cases(payload, flash):
    """The Part menu pages turn the bytes the map gives; the GATE ARP page of the Pattern menu turns byte 49."""
    out = []
    dev = boot(payload, flash)
    obj = dev.u32(PATTERN_PTR)
    menu_cases.go(dev, 7)
    seen = []
    for off in PART_PAGES:
        a = ram(dev, obj + 4 + off, 1)[0]
        dev.turn(1, 0.3)
        b = ram(dev, obj + 4 + off, 1)[0]
        dev.turn(-1, 0.3)
        c = ram(dev, obj + 4 + off, 1)[0]
        seen.append((off - 0x800, a, b, c))
        dev.press(menu_cases.KEYS["edit_next"], 0.3)
    out.append(entry("part_menu_pages", all(a != b or b != c for _, a, b, c in seen), f"part byte, before, +1, -1: {seen}"))
    dev = boot(payload, flash)
    obj = dev.u32(PATTERN_PTR)
    menu_cases.go(dev, 3)
    for _ in range(10):
        dev.press(menu_cases.KEYS["edit_next"], 0.2)
    a = ram(dev, obj + 4 + 49, 1)[0]
    dev.turn(1, 0.3)
    b = ram(dev, obj + 4 + 49, 1)[0]
    out.append(entry("gate_arp_page", b == a + 1, f"byte 49 {a} -> {b}"))
    return out


def part_input_cases(payload, flash):
    """Knob and encoders go through the part setter with their parameter number; the keys have setters of their own.
    Both fill the copy behind the block, so a plain byte write is not the same."""
    import struct
    import unicorn
    out = []
    dev = boot(payload, flash)
    obj = dev.u32(PATTERN_PTR)
    params = []

    def hit(u, a, s, d):
        sp = u.reg_read(dev.m.A.UC_ARM_REG_SP)
        params.append((u.reg_read(dev.m.A.UC_ARM_REG_R3), struct.unpack("<I", bytes(u.mem_read(sp, 4)))[0] & 0xFF))
    hook = dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, hit, begin=dev.a(PART_SETTER), end=dev.a(PART_SETTER))
    dev.m.uc.ctl_flush_tb()
    for name, message, param, off in PART_INPUTS:
        params.clear()
        before = ram(dev, obj, OBJECT)
        dev.m.send(message)
        dev.run(0.4)
        after = ram(dev, obj, OBJECT)
        rest = changed(before, after)
        ok = any(p == param for p, _ in params) and (4 + off) in rest and any(i >= 4 + COPY for i in rest)
        out.append(entry(f"part_input_{name.split()[1].lower()}", ok, f"{name}: setter calls (parameter, value) {params[:3]}, "
                         f"changed {[hex(i - 4) for i in rest][:6]}"))
    dev.m.uc.hook_del(hook)
    dev.m.uc.ctl_flush_tb()
    for name, k, off in PART_KEYS:
        before = ram(dev, obj, OBJECT)
        dev.m.send([0, k, 1, 0, 0])
        dev.run(0.05)
        dev.m.send([0, k, 0, 0, 0])
        dev.run(0.3)
        rest = changed(before, ram(dev, obj, OBJECT))
        out.append(entry(f"part_key_{name.replace(' ', '_').lower()}", (4 + off) in rest and any(i >= 4 + COPY for i in rest),
                         f"{name}: changed {[hex(i - 4) for i in rest][:4]}"))
    return out


def global_cases(payload, flash):
    """Each global setter writes its byte of the GLST block; the plain ones change nothing else."""
    out = []
    dev = boot(payload, flash)
    g = dev.u32(GLOBALS_PTR)
    for name, (off, value, setter, plain) in GLOBAL.items():
        before = ram(dev, g, 0x104)
        dev.call(setter, g, value, 1)
        dev.run(0.1)
        after = ram(dev, g, 0x104)
        rest = changed(before, after, {4 + off})
        ok = after[4 + off] == value and before[4 + off] != value and not rest
        out.append(entry(f"global_{name}", ok, f"byte {off}: {before[4 + off]} -> {after[4 + off]}, other block bytes {rest[:4]}"
                         + (", the setter is the store alone" if plain else "")))
    return out


GROUPS = (pattern_cases, mfx_cases, page_cases, part_input_cases, global_cases)


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    return [e for group in GROUPS for e in group(payload, flash)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
