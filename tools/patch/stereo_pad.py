"""Builds the stereo-pad patch (Stereo on one pad, docs/messungen/2026-10-29-stereo-ein-pad.md) for firmware 2.02, Hacktribe and Korg's own build.

The firmware pairs the parts 1+2, 3+4 and so on for a stereo sample: on an odd part (1, 3, ...) it plays the sample on two
voices, the left channel through this part, the right channel through the next one, and the next part's pad, LED and steps
belong to the pair. On an even part (2, 4, ...) a stereo sample plays on one voice with the DSP's own voice type for that
(type 4 of the 0x2E message, the left and right channel in one voice) and nothing is paired. With this patch every part
plays a stereo sample the way an even part does. Three places decide the pairing, each one gets a call into our code:

- 0xC007DE08 in the part's stereo mode (0xC007DDCC: 0 mono, 1 pair, 2 sliced): pad, selection, LEDs and the sequencer ask it.
- 0xC00413EC in the oscillator change: the even part claims or frees the next part when a stereo sample comes or goes.
- 0xC0099E2C in the voice setup (0xC0099D88): mode 3 (two voices, type 2) on an even part, mode 4 (one voice, type 4) on an odd one.

The pattern format does not change; a pattern keeps its bytes. The live input's pairing (oscillator 0x11 and 0x2D) stays
the firmware's. The page STEREO 1 PAD in BLECH > FEATURES writes the setting word SETTING (never written, FFFFFFFF, or 1 is on, 0 is
off, kept as bit 2 of byte 5 of the settings file). With the setting off, or EXIT held at power-on (docs/patcher.md,
"Notschalter"), all three places do what the firmware does.

    python3 tools/patch/stereo_pad.py --vsb SYSTEM.VSB [--out data/patches/stereo-pad.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import ramdecl  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC014FF00            # FF in all three builds, behind the last-pattern code, the end of the run 0xC0148880..0xC0150000
CODE_END = 0xC014FFFC
SETTING = 0xC014FFFC            # the last word of the run, FF in the file: the BLECH menu's page STEREO 1 PAD writes it

MODE_SITE = 0xC007DE08          # bne 0xC007DDF8: a stereo sample's part pairs when it is even (r5 the part, r0 1)
MODE_WAS = 0x1AFFFFFA
CLAIM_SITE = 0xC00413EC         # bne 0xC00414E4: an odd part skips the claim of the next part (flags of tst r1, #1)
CLAIM_WAS = 0x1A00003C
CLAIM_SKIP = 0xC00414E4
VOICE_SITE = 0xC0099E2C         # moveq r3, #3: the voice mode of a stereo sample on an even part
VOICE_WAS = 0x03A03003
PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 held keys
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)


def source():
    return f"""
.equ SETTING, {SETTING:#x}
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ CLAIM_SKIP, {CLAIM_SKIP:#x}
.org {CODE_AT:#x}

; Z set when the patch applies: the setting is not 0 and EXIT was not held at power-on; r12 and the flags change
sp_killed:
    ldr r12, =SETTING
    ldr r12, [r12]
    cmp r12, #0
    beq sp_firmware
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq sp_on
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    bxne lr
sp_on:
    cmp r12, r12
    bx lr
sp_firmware:
    movs r12, #1
    bx lr

; replaces bne 0xC007DDF8 after cmp r0, #0: returns 0 (no pair) instead of "the part is even"; the caller pops pc next
sp_mode:
    cmp r0, #0
    bxeq lr
    push {{lr}}
    bl sp_killed
    pop {{lr}}
    moveq r0, #0
    bxeq lr
    and r0, r5, #1
    eor r0, r0, #1
    bx lr

; replaces bne 0xC00414E4 after tst r1, #1: every part skips the claim of the next part, as an odd one does
sp_claim:
    bne sp_skip
    push {{lr}}
    bl sp_killed
    pop {{lr}}
    bxne lr
sp_skip:
    ldr lr, =CLAIM_SKIP
    bx lr

; replaces moveq r3, #3 (called only on an even part): mode 4, one voice, as on an odd part
sp_voice:
    push {{r12, lr}}
    bl sp_killed
    movne r3, #3
    moveq r3, #4
    pop {{r12, pc}}
.pool
"""


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bl_word(at, target, cond=0xE):
    return (cond << 28) | 0x0B000000 | (((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb):
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    if was(CODE_AT, len(code)) != b"\xff" * len(code):
        raise SystemExit(f"{CODE_AT:#x}..{CODE_AT + len(code):#x} is not free in this VSB")
    for site, word, what in ((MODE_SITE, MODE_WAS, "the part's stereo mode"), (CLAIM_SITE, CLAIM_WAS, "the oscillator change"),
                             (VOICE_SITE, VOICE_WAS, "the voice setup")):
        if struct.unpack("<I", was(site, 4))[0] != word:
            raise SystemExit(f"{what} is not where the patch expects it in this VSB ({site:#x})")
    calls = ((MODE_SITE, "sp_mode", 0xE, "the part's stereo mode calls sp_mode: 0 for a stereo sample on every part"),
             (CLAIM_SITE, "sp_claim", 0xE, "the oscillator change calls sp_claim: no part claims the next one"),
             (VOICE_SITE, "sp_voice", 0x0, "the voice setup calls sp_voice on an even part: mode 4, one voice"))
    changes = [{"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": sha(was(CODE_AT, len(code))),
                "note": "stereo pad: a stereo sample plays on one voice on every part, as on an even part"}]
    changes += [{"file": file_offset(site), "bytes": struct.pack("<I", bl_word(site, symbols[name], cond)).hex(),
                 "expect": sha(was(site, 4)), "note": note} for site, name, cond, note in calls]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "stereo-pad",
        "name": "Stereo auf einem Pad",
        "builds": ["hacktribe", "stock"],
        "changes": changes,
        "hooks": [
            {"site": f"0x{MODE_SITE:08X}", "kind": "instruction", "chain": "stereo-pair", "position": "replace", "swallow": False,
             "note": "a stereo sample never pairs its part with the next one"},
            {"site": f"0x{CLAIM_SITE:08X}", "kind": "instruction", "chain": "stereo-pair", "position": "replace", "swallow": False,
             "note": "the oscillator change leaves the next part alone"},
            {"site": f"0x{VOICE_SITE:08X}", "kind": "instruction", "chain": "stereo-pair", "position": "replace", "swallow": False,
             "note": "the voice setup takes mode 4 (one voice) on an even part too"},
        ],
        "startPhase": [
            {"file": file_offset(MODE_SITE), "length": 4, "why": "the start loads a pattern and asks each part's stereo mode, which now calls sp_mode"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "sp_mode runs with that call; it reads the setting word and the held keys"},
        ],
        "ram": [ramdecl.area(SETTING, 4, "the setting word of STEREO 1 PAD: FFFFFFFF or 1 on, 0 off; the BLECH menu writes it", "tools/patch/stereo_pad.py:SETTING")],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    text = json.dumps(build_patch(raw), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
