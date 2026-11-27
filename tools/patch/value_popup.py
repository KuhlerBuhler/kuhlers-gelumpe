"""Builds the value-popup patch: a key pressed while the value window of a knob is on the screen closes the window and does
what it does without the window (docs/hintergrund/display.md, "Werte-Fenster nach einem Regler").

Turning a knob or an encoder opens a value window (view 0x17, view 0x18 for the sample encoder) for about 5 seconds. Its key
handler ignores every key press and acts on the release only: it closes the window and posts the release again. The press
is lost, so MENU and WRITE right after a knob only close the window and need a second press. The filter keys LPF, HPF and
BPF are forwarded to the filter on release and keep the window.

The patch rewrites the handler in place, same length, same calls: a press closes the window and posts the same press again
(Korg's close sets the "no window" flag at once, so the posted press takes the path of the home screen), a release does the
same as before. SHIFT closes the window too, so that the home screen sees it and SHIFT + key works. The filter keys keep
the window and act on release as before.

Sampler (Korg's and Hacktribe's): two handlers, 0xC006543C (view 0x17) and 0xC0065498 (view 0x18). Synth: one, the place of
0xC0065498 (data/synth-map/value-popup.json).

The main dial does not go to the window's key handler but to the screen manager's encoder handler (0xC006EB90). With a
window open Korg's handler gives the dial to the home screen and leaves the window, and on every other screen, a menu among
them, the turn is lost. The patch rewrites that handler in place too: the dial closes a value window and goes to the
screen, as with no window. The other encoders still go to the window (a knob turn keeps the window). No start phase, no RAM.

    python3 tools/patch/value_popup.py --vsb SYSTEM.VSB [--out data/patches/value-popup.json]
    python3 tools/patch/value_popup.py --vsb blue/SYSTEM.VSB --build synth [--out data/patches/value-popup-synth.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import synthaddr  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

KNOB_KEYS = 0xC006543C          # key handler of the value window 0x17 (knobs, encoders)
SAMPLE_KEYS = 0xC0065498        # key handler of the value window 0x18 (the sample encoder)
DIAL = 0xC006EB90               # the screen manager's encoder handler: the main dial and the encoders
FIRMWARE_PLACES = ["SAMPLE_KEYS", "DIAL"]
WORDS = 23                      # 22 instructions and the literal of the forward to the filter

# The handler as the firmware has it. None: a branch out of the handler or the literal, checked by its kind only.
ORIGINAL = [
    0xE3520000,     # cmp   r2, #0
    0xE92D4010,     # push  {r4, lr}
    0xE1A0C000,     # mov   ip, r0
    0xE1A04001,     # mov   r4, r1
    0x18BD8010,     # popne {r4, pc}           a press: nothing
    0xE2413012,     # sub   r3, r1, #0x12
    0xE3530004,     # cmp   r3, #4
    0x8A000003,     # bhi   close
    0xE3A02001,     # mov   r2, #1
    0xE1A03312,     # lsl   r3, r2, r3
    0xE3130015,     # tst   r3, #0x15          LPF, HPF, BPF
    0x1A000004,     # bne   forward
    None,           # close: bl   (Korg's close of the window)
    0xE1A00004,     # mov   r0, r4
    0xE3A01000,     # mov   r1, #0             post the release again
    0xE8BD4010,     # pop   {r4, lr}
    None,           # b     (post the key)
    0xE59F300C,     # forward: ldr r3, [pc, #0xc]
    0xE1A0100C,     # mov   r1, ip
    0xE5930000,     # ldr   r0, [r3]
    0xE8BD4010,     # pop   {r4, lr}
    None,           # b     (the filter)
    None,           # .word (the filter's object)
]
KINDS = {12: 0xEB, 16: 0xEA, 21: 0xEA}

# Words 0 to 11. The close path (12 on) and the forward path (17 on) keep their places.
HEAD = """
    push  {r4, r5, r6, lr}
    mov   r4, r1
    mov   r5, r2
    sub   r3, r1, #0x12
    cmp   r3, #4
    tstls r3, #1
    bne   close
    cmp   r2, #0
    popne {r4, r5, r6, pc}
    b     forward
    mov   r0, r0
    mov   r0, r0
close:
"""
TAIL = {
    14: 0xE1A01005,     # mov   r1, r5             post the same press or release again
    15: 0xE8BD4070,     # pop   {r4, r5, r6, lr}
    18: 0xE1A01000,     # mov   r1, r0             r0 still holds the window
    20: 0xE8BD4070,     # pop   {r4, r5, r6, lr}
}


# The encoder handler (r0 the screen manager, r1 the encoder, 0 the main dial, r2 the step). With a window open the dial
# reaches the home screen only (the window stays) or the window 0x2a; on any other screen, a menu among them, it is lost.
# None: a branch out of the handler (close, then the tail call after the screen's dial), checked by its kind only.
DIAL_ORIGINAL = {
    "sampler": [
        0xE3510000, 0xE92D4038, 0xE5D03019, 0xE1A04000, 0xE1A05002, 0x1A000014, 0xE3530000, 0x0A000001,
        None, 0xEA000005, 0xE5903020, 0xE353002A, 0x0A000014, 0xE590301C, 0xE3530001, 0x18BD8038,
        0xE5D43018, 0xE3530000, 0x18BD8038, 0xE5940010, 0xE1A01005, 0xE5903000, 0xE5933028, 0xE12FFF33,
        0xE5940030, 0xE8BD4038, None, 0xE3530000, 0x0A000004, 0xE5D03018, 0xE3530000, 0x05900010,
        0x18BD8038, 0xEA000000, 0xE5940014, 0xE5903000, 0xE593301C, 0xE12FFF33, 0xE8BD8038,
    ],
    # The synth has no window 0x2a and checks the lock twice.
    "synth": [
        0xE3510000, 0xE92D4038, 0xE5D03019, 0xE1A04000, 0xE1A05002, 0x1A000013, 0xE3530000, 0x0A000003,
        None, 0xE5D43018, 0xE3530000, 0x0A000005, 0xE594301C, 0xE3530001, 0x18BD8038, 0xE5D43018,
        0xE3530000, 0x18BD8038, 0xE5940010, 0xE1A01005, 0xE5903000, 0xE5933028, 0xE12FFF33, 0xE5940030,
        0xE8BD4038, None, 0xE3530000, 0x0A000004, 0xE5D03018, 0xE3530000, 0x05900010, 0x18BD8038,
        0xEA000000, 0xE5900014, 0xE5903000, 0xE593301C, 0xE12FFF33, 0xE8BD8038,
    ],
}
DIAL_BRANCHES = {"sampler": {8: 0xEB, 26: 0xEA}, "synth": {8: 0xEB, 25: 0xEA}}

# The same handler with the value windows closed by the dial: a value window (0x17, on the Sampler also 0x18) is closed
# and the dial goes to the screen, as with no window. The window 0x2a keeps the dial, any other window keeps Korg's way.
# The other encoders keep their way; their call is a tail call now, which leaves the room for the new checks.
DIAL_HEAD = """
    cmp   r1, #0
    push  {r3, r4, r5, lr}
    ldrb  r3, [r0, #0x19]
    mov   r4, r0
    mov   r5, r2
    bne   other
    cmp   r3, #0
    ldreq ip, [r4, #0x20]
    movne ip, #0x17               @ no window: close and the screen, as Korg's handler does
"""
DIAL_CHECK = {
    "sampler": """
    cmp   ip, #0x2a
    beq   other
    subs  ip, ip, #0x17
    cmpne ip, #1
    ldrne r3, [r4, #0x1c]
    cmpne r3, #1
    popne {r3, r4, r5, pc}
    cmp   ip, #1
    blls  CLOSE
""",
    "synth": """
    cmp   ip, #0x17
    ldrne r3, [r4, #0x1c]
    cmpne r3, #1
    popne {r3, r4, r5, pc}
    cmp   ip, #0x17
    bleq  CLOSE
""",
}
DIAL_TAIL = """
    ldrb  r3, [r4, #0x18]
    cmp   r3, #0
    popne {r3, r4, r5, pc}
    ldr   r0, [r4, #0x10]
    mov   r1, r5
    ldr   r3, [r0]
    ldr   r3, [r3, #0x28]
    blx   r3
    ldr   r0, [r4, #0x30]
    pop   {r3, r4, r5, lr}
    b     AFTER
other:
    cmp   r3, #0
    ldreq r0, [r4, #0x14]
    beq   call
    ldrb  r3, [r4, #0x18]
    cmp   r3, #0
    popne {r3, r4, r5, pc}
    ldr   r0, [r4, #0x10]
call:
    ldr   ip, [r0]
    pop   {r3, r4, r5, lr}
    ldr   pc, [ip, #0x1c]
"""


def use_build(build):
    """For the synth (the blue Electribe 2) the handler has its own address (data/synth-map/)."""
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def words(vsb, addr):
    return list(struct.unpack_from(f"<{WORDS}I", vsb, file_offset(addr)))


def patched(addr, found):
    head = arm.assemble(HEAD + "    .word 0\n" * 5 + "forward:\n", addr)
    out = list(struct.unpack(f"<{len(head.bytes) // 4}I", head.bytes))[:12]
    if len(out) != 12 or head.symbols["close"] != addr + 48 or head.symbols["forward"] != addr + 68:
        raise SystemExit("the new head of the handler does not fit its 12 words")
    out += found[12:]
    for i, w in TAIL.items():
        out[i] = w
    return out


def handler(vsb, addr, name):
    found = words(vsb, addr)
    for i, (w, want) in enumerate(zip(found, ORIGINAL)):
        if want is None and i in KINDS and w >> 24 != KINDS[i] or want is not None and w != want:
            raise SystemExit(f"the key handler of the value window ({name}) at {addr:#x} is not the one the patch expects (word {i})")
    new = b"".join(struct.pack("<I", w) for w in patched(addr, found))
    old = vsb[file_offset(addr):file_offset(addr) + len(new)]
    return {"file": file_offset(addr), "bytes": new.hex(), "expect": sha(old),
            "note": f"value window {name}: a key press closes the window and runs the key; the filter keys keep it"}


def target(addr, word):
    return (addr + 8 + (((word & 0xFFFFFF) << 8) >> 6)) & 0xFFFFFFFF


def dial(vsb, build):
    """The encoder handler rewritten in place: the dial closes a value window and goes to the screen."""
    kind = "synth" if build == "synth" else "sampler"
    original, branches = DIAL_ORIGINAL[kind], DIAL_BRANCHES[kind]
    found = list(struct.unpack_from(f"<{len(original)}I", vsb, file_offset(DIAL)))
    for i, (w, want) in enumerate(zip(found, original)):
        if want is None and w >> 24 != branches[i] or want is not None and w != want:
            raise SystemExit(f"the encoder handler at {DIAL:#x} is not the one the patch expects (word {i})")
    close, after = (target(DIAL + 4 * i, found[i]) for i in branches)
    code = arm.assemble(f".equ CLOSE, {close:#x}\n.equ AFTER, {after:#x}\n" + DIAL_HEAD + DIAL_CHECK[kind] + DIAL_TAIL, DIAL).bytes
    if len(code) > 4 * len(original):
        raise SystemExit("the new encoder handler does not fit the old one")
    code += b"\x00\x00\xa0\xe1" * ((4 * len(original) - len(code)) // 4)   # mov r0, r0 after the end
    old = vsb[file_offset(DIAL):file_offset(DIAL) + len(code)]
    return {"file": file_offset(DIAL), "bytes": code.hex(), "expect": sha(old),
            "note": "encoder handler: the main dial closes a value window and goes to the screen (a menu among them)"}


def build_patch(vsb, build="hacktribe"):
    synth = build == "synth"
    changes = [] if synth else [handler(vsb, KNOB_KEYS, "0x17")]
    changes.append(handler(vsb, SAMPLE_KEYS, "0x18"))
    changes.append(dial(vsb, build))
    return {
        "format": "gelumpe-patch", "version": 1, "id": "value-popup",
        "name": "Keys close the value window",
        "builds": ["synth"] if synth else ["hacktribe", "stock"],
        "changes": changes,
        "ram": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    use_build(a.build)
    raw_vsb = a.vsb.read_bytes()
    if len(raw_vsb) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw_vsb, a.build), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
