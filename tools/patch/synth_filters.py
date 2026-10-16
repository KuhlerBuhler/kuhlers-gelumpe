"""Builds the synth filters patch for Korg's original 2.02 (docs/messungen/2026-10-15-synth-filter.md).

Korg's firmware has all sixteen filter types in its tables and in the DSP, but its UI only ever picks
OFF and the three electribe filters: the LPF, HPF and BPF keys toggle between OFF and type 1, 7 and 12,
and the part setter folds any other type back onto those three. This patch lets the keys walk through
the other families and lets the setter keep what it is given, so a part can hold MS20, MG, P5, OB and
Acid filters the way Hacktribe's firmware lets it.

Two places change, nothing else, and no code is taken from Hacktribe (the table below is what its keys
were measured to do in the emulator, the code that reads it is our own):

  0xC006FCE8  the key handler of LPF, HPF and BPF (keys 0x12, 0x14, 0x16) has fetched the part's current
              type into r5 and the key into r4, and next compares r4 with the key codes and picks the new
              type from jump tables. The instruction becomes a branch into `select`, which reads the new
              type from a table of 3 x 17 bytes (key, current type) and rejoins at 0xC006FDDC, where the
              firmware compares it with the current one and stores it through its own command.
  0xC00495DC  the part setter folds types 2 to 6 to 1, 8 to 11 to 7 and 13 to 16 to 12 before it stores
              them. A conditional branch (which skips the folding for the types that need none) becomes
              a branch into `store`, which skips it for every type. Patterns that carry a synth type then
              keep it when they are loaded through this setter, instead of getting the electribe filter of
              the same family.

With EXIT held at power-on both places run the firmware's own instructions, so the device is Korg's again.

The table, per key, from the current type 0 to 16:

  LPF   cycles 1 2 3 4 5 6, then OFF, then 1; from the HPF or BPF families it goes to the LPF of the same
        make (7 to 1, 8 to 2, 9 to 4, 10 to 5, 11 to 6, 12 to 1, 13 to 2 ...); MG has no HPF or BPF
  HPF   cycles 7 8 9 10 11, OFF, 7; from another family to the HPF of the same make, from MG to 7
  BPF   cycles 12 13 14 15 16, OFF, 12; same for the others

The patch is for Korg's build only; Hacktribe's firmware does this itself. The key handler runs when a key
is pressed. The setter also runs at start (the 16 parts of the first pattern, about 310 ms after power-on,
long after the rescue paths); there `store` only looks at the panel object and the kill switch.

    python3 tools/patch/synth_filters.py --vsb SYSTEM.VSB [--out data/patches/synth-filters.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC0190000            # free (FF) in Korg's image, between the loading bar's area and the script runtime
CODE_END = 0xC0190100

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)

SELECT_HOOK = 0xC006FCE8        # cmp r4, #0x14 in the LPF/HPF/BPF key handler
SELECT_WORD = 0xE3540014
SELECT_REJOIN = 0xC006FDDC      # cmp r4, r5: nothing to do when the type stays, else the firmware's own command
SETTER_HOOK = 0xC00495DC        # bhi: skip the folding for the types that need none
SETTER_WORD = 0x8A000009
SETTER_SKIP = 0xC0049608        # where the folding ends

LPF, HPF, BPF = 0, 1, 2
FIRST = {LPF: 1, HPF: 7, BPF: 12}
LAST = {LPF: 6, HPF: 11, BPF: 16}
# the make of each type, by position in the family: electribe, MS20, MG, P5, OB, Acid
MAKE = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 0, 8: 1, 9: 3, 10: 4, 11: 5, 12: 0, 13: 1, 14: 3, 15: 4, 16: 5}
OF_MAKE = {LPF: [1, 2, 3, 4, 5, 6], HPF: [7, 8, 7, 9, 10, 11], BPF: [12, 13, 12, 14, 15, 16]}   # MG has no HPF or BPF: the electribe one


def family(t):
    return LPF if t <= 6 else HPF if t <= 11 else BPF


def next_type(key, current):
    """What the key makes of the current type (0 to 16)."""
    if current == 0:
        return FIRST[key]
    if family(current) == key:
        return 0 if current == LAST[key] else current + 1
    return OF_MAKE[key][MAKE[current]]


def table():
    return bytes(next_type(key, current) for key in (LPF, HPF, BPF) for current in range(17))


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ KILL, @KILL@               ; EXIT held at power-on
.equ KEY_ORIGINAL, @KEY_ORIGINAL@
.equ REJOIN, @REJOIN@
.equ SETTER_SKIP, @SETTER_SKIP@
.equ SETTER_FOLD, @SETTER_FOLD@

.org @CODE_AT@

; ===================================================== the LPF, HPF and BPF keys
; r4 = the key (0x12 LPF, 0x14 HPF, 0x16 BPF), r5 = the part's current type -> r4 = the type it becomes.
; With EXIT held at power-on (or no panel object) the firmware's own comparison runs, so the keys are Korg's.
; Any other key, or a current type above 16 (the setter never stores one), gives OFF, as the firmware's tables do.
select:
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq select_original
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    bne select_original
    cmp r5, #16
    bhi pick_off
    sub r0, r4, #0x12
    cmp r0, #4
    bhi pick_off
    tst r0, #1
    bne pick_off
    mov r0, r0, lsr #1
    add r0, r0, r0, lsl #4
    add r0, r0, r5
    ldr r1, =types
    ldrb r4, [r1, r0]
    b REJOIN
pick_off:
    mov r4, #0
    b REJOIN
select_original:
    cmp r4, #0x14
    b KEY_ORIGINAL

; ===================================================== the part setter
; Stands where the firmware's `bhi` was: types that need no folding go on as before (the flags are those of the
; firmware's own comparison). The others are kept as given, unless EXIT was held at power-on (or there is no panel
; object yet), then the firmware folds them onto the electribe filters as it always did.
; Uses r3 only, which the firmware sets right after this point.
store:
    bhi SETTER_SKIP
    ldr r3, =PANEL
    ldr r3, [r3]
    cmp r3, #0
    beq store_fold
    ldr r3, [r3, #0x18]
    tst r3, #KILL
    beq SETTER_SKIP
store_fold:
    b SETTER_FOLD
.pool
types:
.byte @TYPES@
"""


def source():
    text = SOURCE
    for key, value in {
        "KILL": f"{KILL_SWITCH:#x}", "KEY_ORIGINAL": f"{SELECT_HOOK + 4:#x}", "REJOIN": f"{SELECT_REJOIN:#x}",
        "SETTER_SKIP": f"{SETTER_SKIP:#x}", "SETTER_FOLD": f"{SETTER_HOOK + 4:#x}", "CODE_AT": f"{CODE_AT:#x}",
        "TYPES": ", ".join(str(b) for b in table()),
    }.items():
        text = text.replace(f"@{key}@", str(value))
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target):
    return struct.pack("<I", 0xEA000000 | (((target - (at + 8)) >> 2) & 0xFFFFFF))


def hex_addr(addr):
    return f"{addr:#010X}".replace("0X", "0x")


def build_patch(vsb):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def word(addr):
        return struct.unpack("<I", was(addr, 4))[0]

    if word(SELECT_HOOK) != SELECT_WORD:
        raise SystemExit("the LPF/HPF/BPF key handler does not compare the key with 0x14 where the patch expects it in this VSB")
    if word(SETTER_HOOK) != SETTER_WORD:
        raise SystemExit("the part's filter type setter does not start its folding with a conditional branch where the patch expects it in this VSB")
    if word(SELECT_REJOIN) != 0xE1540005:
        raise SystemExit("the key handler does not compare the new type with the current one where the patch rejoins it in this VSB")
    if was(CODE_AT, len(code)) != b"\xff" * len(code):
        raise SystemExit(f"{CODE_AT:#x} is not free in this VSB")

    return {
        "format": "gelumpe-patch", "version": 1, "id": "synth-filters", "builds": ["stock"], "notNeededOn": ["hacktribe"],
        "name": "Synth-Filter auf LPF, HPF und BPF in Korgs Original (MS20, MG, P5, OB, Acid)",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": sha(was(CODE_AT, len(code))),
             "note": "the selection of the next filter type for the LPF, HPF and BPF keys, the setter's skip of the folding, and the table"},
            {"file": file_offset(SELECT_HOOK), "bytes": branch(SELECT_HOOK, symbols["select"]).hex(), "expect": sha(was(SELECT_HOOK, 4)),
             "note": "the key handler's comparison of the key with 0x14 jumps to the selection"},
            {"file": file_offset(SETTER_HOOK), "bytes": branch(SETTER_HOOK, symbols["store"]).hex(), "expect": sha(was(SETTER_HOOK, 4)),
             "note": "the filter type setter's branch past the folding of types 2 to 6, 8 to 11 and 13 to 16 jumps to the patch"},
        ],
        "hooks": [
            {"site": hex_addr(SELECT_HOOK), "kind": "instruction", "chain": "filter-key", "position": "replace", "swallow": True,
             "note": "the keys choose the next filter type from the table instead of the firmware's jump tables (the firmware's comparison runs with EXIT held at power-on)"},
            {"site": hex_addr(SETTER_HOOK), "kind": "instruction", "chain": "filter-type-store", "position": "replace", "swallow": True,
             "note": "the setter stores the type as given (it folds it with EXIT held at power-on)"},
        ],
        "startPhase": [
            {"file": file_offset(SETTER_HOOK), "length": 4, "why": "the part setter runs for the 16 parts of the first pattern at about 310 ms, after the rescue paths, and now jumps to store"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "store: at start it only looks at the panel object and the kill switch and then does what the firmware's branch did or skips the folding; select and the table run on a key"},
        ],
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    patch = build_patch(raw)
    if a.listing:
        at, code, symbols = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
