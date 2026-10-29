"""Builds the beat-eighth patch: a fifth value "8" on the page BEAT of the Pattern menu, steps as eighth notes
(docs/messungen/2026-10-29-beat-achtel.md).

The pattern byte BEAT (block offset 38) picks the step length: the sequencer divides its ticks by the table at 0xC00E2DDC
(06 03 08 04 for 16, 32, 8 Tri, 16 Tri), 96 divided ticks are one step. The byte behind the table is not read by anything;
the patch writes 12 there, so BEAT 4 makes a step 1152 ticks, an eighth note. MIDI clock in and out stay at the real tempo,
Gate Arp follows the step (it divides by the same table).

Besides the table:
  menu        the clamp of the page BEAT (0xC007D13C) goes to 4 instead of 3
  display     the page shows "\\8" for 4 where it showed "?" (the literal of the fallback, 0xC0080F50); the list text
              (0xC008C124, red only) "8"
  export      EXPORT AUDIO and its siblings work out a part's length in samples from steps per quarter (08 03 06 for BEAT 1 to 3)
              and steps per bar (10 0C 0C); BEAT 0 and anything above 3 took 4 and 16. Four places, the same pattern of code:
              cmp #2 goes to cmp #3 and their two literals point at copies of the tables with a fourth entry, 2 steps per
              quarter and 16 per bar, so a BEAT 8 pattern exports as long as it plays
  slices      (red only) the step map of a sliced sample (0xC009A934) indexes a 4 by 4 table with (slice beat << 2) | BEAT; BEAT 4
              would read the next row. The getter call there becomes ldrb plus and #3, so BEAT 8 maps slices to steps as BEAT 16

No code of our own, no start phase. The new data (the text and the two tables) sits at 0xC014FC00, FF in all three builds in
front of the version text (0xC014FCF0). The tables are copies of the firmware's own with one byte over them.

    python3 tools/patch/beat_eighth.py --vsb SYSTEM.VSB [--out data/patches/beat-eighth.json]
    python3 tools/patch/beat_eighth.py --vsb blue/SYSTEM.VSB --build synth [--out data/patches/beat-eighth-synth.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import synthaddr  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

DATA_AT = 0xC014FC00            # FF in Hacktribe 2.02 and Korg's red and blue 2.02, before the version text at 0xC014FCF0
DATA_END = 0xC014FC10
TEXT = DATA_AT                  # "\\8": two one pixel spacers as in "\\8 Tri"; TEXT + 2 is "8"
QUARTER = DATA_AT + 4           # steps per quarter for BEAT 1 to 4: 08 03 06 02
BAR = DATA_AT + 8               # steps per bar for BEAT 1 to 4: 10 0C 0C 10

DIVIDER = 0xC00E2DDC            # 06 03 08 04, the sequencer's tick divider per BEAT
EIGHTH = 12                     # 96 x 12 = 1152 ticks of 2304 per quarter
MENU_CMP = 0xC007D13C           # cmp r1, #3 in the page BEAT's value change
MENU_MOV = 0xC007D140           # movge r1, #3
DISPLAY_LDR = 0xC0080F1C        # ldr r1, =0xC00A5A98 ("?"), the page's text for a value above 3
LIST_LDR = 0xC008C01C           # the same in the list text (red only)
EXPORT_CMP = [0xC002ED28, 0xC00327E8, 0xC00334C8, 0xC003371C]                  # cmp r3, #2 on BEAT - 1
EXPORT_LDR = [(0xC002ED2C, 0xC002ED38), (0xC00327EC, 0xC00327F8), (0xC00334CC, 0xC00334DC), (0xC0033720, 0xC0033734)]
SLICE_ARG = 0xC009AA74          # mov r0, fp (the pattern object) in the slice step map 0xC009A934 (red only)
SLICE_GET = 0xC009AA78          # bl 0xC004A378, the BEAT getter (ldrb r0, [r0, #0x2a]; bx lr)
BEAT_GETTER = 0xC004A378

SAMPLER_ONLY = ["LIST_LDR", "SLICE_ARG", "SLICE_GET", "BEAT_GETTER"]
FIRMWARE_PLACES = ["DIVIDER", "MENU_CMP", "MENU_MOV", "DISPLAY_LDR"]
EXPORT_PLACES = 4

QUARTER_STEPS = bytes([8, 3, 6])
BAR_STEPS = bytes([16, 12, 12])


def use_build(build):
    """For the synth (the blue Electribe 2) the firmware's places have their own addresses (data/synth-map/)."""
    global EXPORT_CMP, EXPORT_LDR
    synthaddr.use(globals(), FIRMWARE_PLACES, build)
    pristine = globals().setdefault("_SAMPLER_EXPORT", (list(EXPORT_CMP), list(EXPORT_LDR)))
    if build == "synth":
        try:
            EXPORT_CMP = [synthaddr.tr(a) for a in pristine[0]]
            EXPORT_LDR = [(synthaddr.tr(a), synthaddr.tr(b)) for a, b in pristine[1]]
        except synthaddr.Unmapped as error:
            raise SystemExit(f"the synth build cannot place: {error}")
    else:
        EXPORT_CMP, EXPORT_LDR = list(pristine[0]), list(pristine[1])


def file_offset(addr):
    return addr - RAM + HEADER


def sha(data):
    return hashlib.sha256(data).hexdigest()


def word(vsb, addr):
    return struct.unpack_from("<I", vsb, file_offset(addr))[0]


def pool(vsb, at):
    """The pool address and value of `ldr rX, [pc, #imm]` (also conditional) at `at`."""
    w = word(vsb, at)
    if (w & 0x0F7F0000) != 0x051F0000:
        raise SystemExit(f"{at:#x} is not an ldr from the literal pool in this VSB")
    imm = w & 0xFFF
    where = at + 8 + (imm if w & 0x00800000 else -imm)
    return where, word(vsb, where)


def bl_target(w, at):
    off = w & 0xFFFFFF
    if off & 0x800000:
        off -= 1 << 24
    return (at + 8 + (off << 2)) & 0xFFFFFFFF


def raw(vsb, addr, new, note):
    old = vsb[file_offset(addr):file_offset(addr) + len(new)]
    return {"file": file_offset(addr), "bytes": new.hex(), "expect": sha(old), "note": note}


def put_word(vsb, addr, old, new, note):
    if word(vsb, addr) != old:
        raise SystemExit(f"{addr:#x} holds {word(vsb, addr):#010x}, the patch expects {old:#010x}")
    return raw(vsb, addr, struct.pack("<I", new), note)


def copy_table(vsb, at, source, last, note):
    src = vsb[file_offset(source):file_offset(source) + 4]
    return {"file": file_offset(at), "copy": {"file": file_offset(source), "length": 4, "expect": sha(src)},
            "over": [{"at": 3, "bytes": bytes([last]).hex()}], "expect": sha(vsb[file_offset(at):file_offset(at) + 4]), "note": note}


def build_patch(vsb, build="hacktribe"):
    synth = build == "synth"
    if vsb[file_offset(DATA_AT):file_offset(DATA_END)] != b"\xff" * (DATA_END - DATA_AT):
        raise SystemExit(f"{DATA_AT:#x}..{DATA_END:#x} is not free in this VSB")
    table = vsb[file_offset(DIVIDER):file_offset(DIVIDER) + 8]
    if table != bytes([6, 3, 8, 4, 0, 0, 0, 0]):
        raise SystemExit(f"the divider table at {DIVIDER:#x} is {table.hex()}, the patch expects 0603080400000000")

    disp_pool, question = pool(vsb, DISPLAY_LDR)
    if vsb[file_offset(question):file_offset(question) + 2] != b"?\0":
        raise SystemExit("the BEAT page's fallback text is not \"?\" in this VSB")
    changes = [
        raw(vsb, DIVIDER + 4, bytes([EIGHTH]), "BEAT 4 divides the ticks by 12: a step is an eighth note (1152 ticks)"),
        raw(vsb, TEXT, b"\\\\8\0", "the text of BEAT 4, \\\\8 as \\\\8 Tri; from its third byte the list text 8"),
        put_word(vsb, MENU_CMP, 0xE3510003, 0xE3510004, "the page BEAT takes values up to 4 (cmp r1, #4)"),
        put_word(vsb, MENU_MOV, 0xA3A01003, 0xA3A01004, "movge r1, #4"),
        put_word(vsb, disp_pool, question, TEXT, "the page BEAT shows \\\\8 for 4 where it showed ?"),
    ]
    if not synth:
        list_pool, value = pool(vsb, LIST_LDR)
        if value != question:
            raise SystemExit("the list text's fallback is not the \"?\" of the BEAT page in this VSB")
        changes.append(put_word(vsb, list_pool, question, TEXT + 2, "the list text shows 8 for BEAT 4"))

    sources = {}
    for i, (cmp_at, ldrs) in enumerate(zip(EXPORT_CMP, EXPORT_LDR)):
        changes.append(put_word(vsb, cmp_at, 0xE3530002, 0xE3530003, f"export length {i + 1}: BEAT 1 to 4 read the tables (cmp r3, #3)"))
        for ldr in ldrs:
            where, value = pool(vsb, ldr)
            head = vsb[file_offset(value):file_offset(value) + 3]
            kind = {QUARTER_STEPS: "quarter", BAR_STEPS: "bar"}.get(head)
            if kind is None:
                raise SystemExit(f"the literal at {where:#x} points at {head.hex()}, neither steps per quarter nor per bar")
            sources.setdefault(kind, value)
            target = QUARTER if kind == "quarter" else BAR
            changes.append(put_word(vsb, where, value, target, f"export length {i + 1}: steps per {kind} from the table with BEAT 4"))
    changes.append(copy_table(vsb, QUARTER, sources["quarter"], 2, "steps per quarter for BEAT 1 to 4: the firmware's 8, 3, 6 and 2 for eighths"))
    changes.append(copy_table(vsb, BAR, sources["bar"], 16, "steps per bar for BEAT 1 to 4: the firmware's 16, 12, 12 and 16"))

    if not synth:
        if word(vsb, SLICE_ARG) != 0xE1A0000B or bl_target(word(vsb, SLICE_GET), SLICE_GET) != BEAT_GETTER:
            raise SystemExit("the slice step map does not call the BEAT getter with the pattern in fp where the patch expects it")
        if (word(vsb, BEAT_GETTER), word(vsb, BEAT_GETTER + 4)) != (0xE5D0002A, 0xE12FFF1E):
            raise SystemExit("the BEAT getter is not ldrb r0, [r0, #0x2a]; bx lr in this VSB")
        changes.append(put_word(vsb, SLICE_ARG, 0xE1A0000B, 0xE5DB002A, "slice step map: ldrb r0, [fp, #0x2a], the getter inline"))
        changes.append(put_word(vsb, SLICE_GET, word(vsb, SLICE_GET), 0xE2000003, "and r0, r0, #3: BEAT 4 takes the column of BEAT 16"))

    return {
        "format": "gelumpe-patch", "version": 1, "id": "beat-eighth",
        "name": "BEAT 8",
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
