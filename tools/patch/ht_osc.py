"""Builds the ht-osc patch (Hacktribe oscillators on the free slots, docs/messungen/2026-11-08-ht-osc-freie-plaetze.md) for Korg's own 2.02.

Korg's red firmware names its slots from a table of 421 entries (0xC00D9AB0, slots 0 to 420); the slots 421 to 499 (display
422 to 500) stay empty sample slots no import reaches, the user's samples start at 500 (display 501). An entry whose import
number (+0x12) is below 50 is a DSP oscillator: the number is the DSP's wave, the bytes +0x14 to +0x1F its parameters, no
sample data. Hacktribe uses 20 new waves of the same DSP code (the DSP code is identical in both builds) for its DUAL, OCT,
CHIP, RING, X and VPM oscillators. This patch writes 76 such entries to the slots 421 to 496 (display 422 to 497); the slots
497 to 499 stay empty. No byte of the entries is taken from Hacktribe: ENTRIES below is a field table, written from what
Hacktribe's own table holds (measured, `--hacktribe` compares the result against that table).

Five places get a call into our code:

- 0xC004F5A8 and 0xC004E354, `ldr r4, =0x1A5` in the factory start and in the start from e2sSample.all, the first slot the
  loop clears: ho_fill clears 421 to 496 itself, writes the entries over the names and lets the firmware clear from 497 on.
- 0xC0040D64, `cmp r4, #0x1A4` in the OSC selector (0xC0040D50): a DSP entry above slot 420 is skipped. ho_sel compares
  with 496 instead.
- 0xC00997A4, `cmp r0, #0x1A4` in the voice's slot lookup (0xC0099788): slots 421 to 499 give no entry, the voice stays
  silent. ho_voice compares with 496 instead.

- 0xC00362A4, `moveq r3, #0x24` in the import of one sample of e2sSample.all (0xC0035B10): the import (0xC004EDF0) refuses a
  sample whose slot holds a DSP entry, and the firmware then ends the whole file, the samples behind it stay unloaded.
  ho_skip returns 0 for a sample on 421 to 496 instead, the loader goes on with the next one.

The export (0xC004EBD4) skips DSP entries, so e2sSample.all never gives the slots 421 to 496.

The page HT OSC in BLECH > FEATURES writes the setting word SETTING (never written, FFFFFFFF, or 1 is on, 0 is off, kept as
bit 6 of byte 5 of the settings file). The start fills the slots before the BLECH menu reads the settings, so the menu calls
ho_apply (the first word of the code, CODE_AT) after it: with the setting off it clears the 76 slots again, before the
samples of e2sSample.all are loaded. With the setting off, or EXIT held at power-on (docs/patcher.md, "Notschalter"), all
five places do what the firmware does.

    python3 tools/patch/ht_osc.py --vsb SYSTEM.VSB [--out data/patches/ht-osc.json] [--hacktribe HACKTRIBE.VSB]
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

CODE_AT = 0xC014F000            # FF in all three builds, in the run 0xC0148880..0xC0150000, in front of the beat-eighth code (0xC014FC00)
CODE_END = 0xC014FBFC
SETTING = 0xC014FBFC            # the last word of the area, FF in the file: the BLECH menu's page HT OSC writes it

NAMES = 0xC047B08C              # the name table, 32 bytes per slot
FIRST = 421                     # slot 421 = display 422
LIMIT = 0x1A4                   # the firmware's last slot of its own table (420)
FACTORY_SITE = 0xC004F5A8       # ldr r4, =0x1A5: the factory start clears from 421
FACTORY_WAS = 0xE59F454C
FILE_SITE = 0xC004E354          # ldr r4, =0x1A5: the start from e2sSample.all clears from 421
FILE_WAS = 0xE59F4064
SEL_SITE = 0xC0040D64           # cmp r4, #0x1A4: the OSC selector skips a DSP entry above 420
SEL_WAS = 0xE3540F69
VOICE_SITE = 0xC00997A4         # cmp r0, #0x1A4: the voice's slot lookup gives no entry for 421 to 499
VOICE_WAS = 0xE3500F69
SKIP_SITE = 0xC00362A4          # moveq r3, #0x24: a sample the import (0xC004EDF0) refuses ends the whole file (0xC0035B10 returns 0x24)
SKIP_WAS = 0x03A03024
CLEAR = 0xC004DF90              # clear(slot, 1): the firmware's empty sample slot "SampleNNN"
MEMCPY = 0xC000985C
PANEL = 0xC033E6F8              # pointer to the panel object, +0x18 held keys
KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13)

# The oscillators in Hacktribe's order. Per type: name, category (+0x10), wave (+0x12, below 50: the DSP's wave), and the
# bytes +0x14 to +0x1B. Step types (X, VPM) take one entry per step: the name gets the step, +0x1C the step byte.
FIXED = [
    ("DUAL-SAW", 0x00, 0x09, "0000c13f38010000"),
    ("DUAL-SQU", 0x00, 0x0A, "fb00c13f3a010000"),
    ("DUAL-TRI", 0x00, 0x0B, "fb00c13f3a010000"),
    ("DUAL-SINE", 0x00, 0x0C, "fb00c13f35010000"),
    ("OCT-SAW", 0x00, 0x09, "0000d0307f010000"),
    ("OCT-SQU", 0x00, 0x0A, "0000d0307f010000"),
    ("OCT-TRI", 0x00, 0x0B, "0000d0307f010000"),
    ("OCT-SINE", 0x00, 0x0C, "ff00d0307f010000"),
    ("CHIP-TRI 1", 0x00, 0x23, "0000007f00010000"),
    ("CHIP-TRI 2", 0x00, 0x24, "0000012003010000"),
    ("CHIP-PULSE", 0x00, 0x22, "0000000871010000"),
    ("CHIP-NOISE", 0x00, 0x21, "0000007f0f010000"),
    ("RING-SAW", 0x00, 0x15, "0021c13f4b010000"),
    ("RING-SQU", 0x00, 0x16, "0021c13f5c010000"),
    ("RING-TRI", 0x00, 0x17, "0021c13f35010000"),
    ("RING-SINE", 0x00, 0x18, "0000c13f5c010000"),
]
X_TYPES = [("X-SAW", 0x19), ("X-SQUARE", 0x1A), ("X-TRI", 0x1B), ("X-SINE", 0x1C)]
X_PARAMS = "0000004420010000"
# semitones -> step byte, as Hacktribe's 27 X steps hold them; seven of them: two octaves, one octave, a fifth each way, and 0
X_STEPS = [("-24", 0xC1), ("-12", 0xD4), ("-7", 0xE4), ("0", 0x00), ("+7", 0x1C), ("+12", 0x30), ("+24", 0x3F)]
VPM_TYPES = [("VPM-SAW", 0x1D), ("VPM-SQUARE", 0x1E), ("VPM-TRI", 0x1F), ("VPM-SINE", 0x20)]
VPM_PARAMS = "0000007f20010000"
# the modulator ratio -> step byte (0.5 is 0, n is n); eight of Hacktribe's 33 steps, the octaves and 3
VPM_STEPS = [("0.5", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4), ("8", 8), ("16", 16), ("32", 32)]


def entry(name, category, wave, params, step=0):
    raw = name.encode("ascii")
    assert len(raw) < 16 and wave < 50
    return raw.ljust(16, b"\0") + struct.pack("<HH", category, wave) + bytes.fromhex(params) + struct.pack("<I", step)


def entries():
    out = [entry(*e) for e in FIXED]
    out += [entry(f"{n} {s}", 0x0A, w, X_PARAMS, b) for n, w in X_TYPES for s, b in X_STEPS]
    out += [entry(f"{n} {s}", 0x10, w, VPM_PARAMS, b) for n, w in VPM_TYPES for s, b in VPM_STEPS]
    return out


COUNT = 76
LAST = FIRST + COUNT - 1        # 496 = display 497


def source():
    table = "\n".join("    .byte " + ", ".join(f"{b:#04x}" for b in e) for e in entries())
    return f"""
.equ SETTING, {SETTING:#x}
.equ PANEL, {PANEL:#x}
.equ KILL, {KILL_SWITCH:#x}
.equ NAMES, {NAMES:#x}
.equ CLEAR, {CLEAR:#x}
.equ MEMCPY, {MEMCPY:#x}
.org {CODE_AT:#x}

; called by the BLECH menu after it read the settings (CODE_AT, fixed): with the setting off the slots the start filled are
; cleared again; r0 to r3 and r12 change
ho_apply:
    push {{r4, lr}}
    ldr r0, =SETTING
    ldr r0, [r0]
    cmp r0, #0
    popne {{r4, pc}}
    ldr r0, =NAMES + {FIRST * 32 + 0x10:#x}
    ldr r0, [r0]
    mov r0, r0, lsr #16
    cmp r0, #0x31
    pophi {{r4, pc}}
    bl ho_clear
    pop {{r4, pc}}

; clears the slots FIRST to LAST the firmware's way; r4 the slot after them, r0 to r3 and r12 change
ho_clear:
    push {{r5, lr}}
    ldr r4, ={FIRST}
    ldr r5, ={LAST + 1}
ho_clear_next:
    mov r0, r4
    mov r1, #1
    ldr r12, =CLEAR
    blx r12
    add r4, r4, #1
    cmp r4, r5
    bne ho_clear_next
    pop {{r5, pc}}

; Z set when the patch applies: the setting is not 0 and EXIT was not held at power-on; r12 and the flags change
ho_on:
    ldr r12, =SETTING
    ldr r12, [r12]
    cmp r12, #0
    beq ho_firmware
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq ho_yes
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    bxne lr
ho_yes:
    cmp r12, r12
    bx lr
ho_firmware:
    movs r12, #1
    bx lr

; replaces ldr r4, =0x1A5 in front of the clear loop of both starts: r4 the first slot the loop clears; r0 to r3 change
ho_fill:
    push {{r5, lr}}
    bl ho_on
    ldrne r4, ={FIRST}
    popne {{r5, pc}}
    bl ho_clear
    ldr r0, =NAMES + {FIRST * 32:#x}
    ldr r1, =ho_table
    mov r2, #{COUNT * 32:#x}
    ldr r12, =MEMCPY
    blx r12
    ldr r4, ={LAST + 1}
    pop {{r5, pc}}

; replaces moveq r3, #0x24 (called only when the import refused the sample, Z set): a sample for 421 to 496 returns 0, the
; loader goes on with the next one; any other keeps 0x24. Z stays set, r8 the sample's record (+0 its slot)
ho_skip:
    push {{lr}}
    mov r3, #0x24
    bl ho_on
    bne ho_skip_out
    ldrb r0, [r8]
    ldrb r1, [r8, #1]
    orr r0, r0, r1, lsl #8
    ldr r1, ={FIRST}
    cmp r0, r1
    blo ho_skip_out
    ldr r1, ={LAST}
    cmp r0, r1
    movls r3, #0
ho_skip_out:
    cmp r3, r3
    pop {{pc}}

; replaces cmp r4, #0x1A4 in the OSC selector: the flags of cmp r4 with the last slot that may hold a DSP entry
ho_sel:
    push {{lr}}
    bl ho_on
    pop {{lr}}
    movne r12, #{LIMIT:#x}
    ldreq r12, ={LAST}
    cmp r4, r12
    bx lr

; replaces cmp r0, #0x1A4 in the voice's slot lookup, the same for r0
ho_voice:
    push {{lr}}
    bl ho_on
    pop {{lr}}
    movne r12, #{LIMIT:#x}
    ldreq r12, ={LAST}
    cmp r0, r12
    bx lr
.pool
.align 4
ho_table:
{table}
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


def check_hacktribe(vsb):
    """Each generated entry against the entry of the same name in Hacktribe's slot table (0xC00D9AB0, 274 entries)."""
    table = 0xC00D9AB0
    theirs = {}
    for i in range(274):
        e = vsb[file_offset(table) + i * 32:file_offset(table) + i * 32 + 32]
        theirs[e[:16].rstrip(b"\0")] = e
    for e in entries():
        name = e[:16].rstrip(b"\0")
        if theirs.get(name) != e:
            raise SystemExit(f"{name.decode()} differs from Hacktribe's entry")
    return len(entries())


def build_patch(vsb):
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
    if len(entries()) != COUNT:
        raise SystemExit("the table must have COUNT entries")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    if was(CODE_AT, CODE_END + 4 - CODE_AT) != b"\xff" * (CODE_END + 4 - CODE_AT):
        raise SystemExit(f"{CODE_AT:#x}..{CODE_END + 4:#x} is not free in this VSB")
    sites = ((FACTORY_SITE, FACTORY_WAS, "the factory start"), (FILE_SITE, FILE_WAS, "the start from e2sSample.all"),
             (SKIP_SITE, SKIP_WAS, "the loader's refusal"), (SEL_SITE, SEL_WAS, "the OSC selector"), (VOICE_SITE, VOICE_WAS, "the voice's slot lookup"))
    for site, word, what in sites:
        if struct.unpack("<I", was(site, 4))[0] != word:
            raise SystemExit(f"{what} is not where the patch expects it in this VSB ({site:#x})")
    calls = ((FACTORY_SITE, "ho_fill", 0xE, "the factory start calls ho_fill: the oscillators on 421 to 496, the loop clears from 497"),
             (FILE_SITE, "ho_fill", 0xE, "the start from e2sSample.all calls ho_fill: the same"),
             (SKIP_SITE, "ho_skip", 0x0, "the loader calls ho_skip when the import refuses a sample: one for 421 to 496 is skipped, the rest still loads"),
             (SEL_SITE, "ho_sel", 0xE, "the OSC selector calls ho_sel: DSP entries up to slot 496"),
             (VOICE_SITE, "ho_voice", 0xE, "the voice's slot lookup calls ho_voice: entries up to slot 496"))
    changes = [{"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": sha(was(CODE_AT, len(code))),
                "note": "ht osc: 76 Hacktribe oscillators on the empty slots 422 to 497"}]
    changes += [{"file": file_offset(site), "bytes": struct.pack("<I", bl_word(site, symbols[name], cond)).hex(),
                 "expect": sha(was(site, 4)), "note": note} for site, name, cond, note in calls]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "ht-osc",
        "name": "Hacktribe-Oszillatoren auf freien Plätzen",
        "builds": ["stock"], "notNeededOn": ["hacktribe"],
        "changes": changes,
        "hooks": [
            {"site": f"0x{FACTORY_SITE:08X}", "kind": "instruction", "chain": "ht-osc", "position": "replace", "swallow": False,
             "note": "the factory start fills the slots 421 to 496 with oscillators"},
            {"site": f"0x{FILE_SITE:08X}", "kind": "instruction", "chain": "ht-osc", "position": "replace", "swallow": False,
             "note": "the start from e2sSample.all fills the slots 421 to 496 with oscillators"},
            {"site": f"0x{SKIP_SITE:08X}", "kind": "instruction", "chain": "ht-osc", "position": "replace", "swallow": False,
             "note": "a sample of e2sSample.all for the slots 421 to 496 is skipped, the rest of the file still loads"},
            {"site": f"0x{SEL_SITE:08X}", "kind": "instruction", "chain": "ht-osc", "position": "replace", "swallow": False,
             "note": "the OSC selector takes DSP entries up to slot 496"},
            {"site": f"0x{VOICE_SITE:08X}", "kind": "instruction", "chain": "ht-osc", "position": "replace", "swallow": False,
             "note": "the voice's slot lookup gives entries up to slot 496"},
        ],
        "startPhase": [
            {"file": file_offset(FILE_SITE), "length": 4, "why": "the start from e2sSample.all names the slots, which now calls ho_fill"},
            {"file": file_offset(FACTORY_SITE), "length": 4, "why": "the factory start names the slots, which now calls ho_fill"},
            {"file": file_offset(VOICE_SITE), "length": 4, "why": "the voice's slot lookup runs when the first pattern loads at start, which now calls ho_voice"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "ho_fill and ho_voice run with those calls; they read the setting word and the held keys"},
        ],
        "ram": [ramdecl.area(SETTING, 4, "the setting word of HT OSC: FFFFFFFF or 1 on, 0 off; the BLECH menu writes it", "tools/patch/ht_osc.py:SETTING")],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--hacktribe", type=Path, help="Hacktribe's SYSTEM.VSB: compare the entries with its table, write nothing of it")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    if a.hacktribe:
        n = check_hacktribe(a.hacktribe.read_bytes())
        print(f"{n} entries match Hacktribe's table", file=sys.stderr)
    text = json.dumps(build_patch(raw), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
