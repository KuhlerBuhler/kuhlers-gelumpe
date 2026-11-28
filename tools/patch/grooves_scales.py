"""Builds the grooves-scales patch: 62 grooves and 70 scales on Korg's red build, like Hacktribe has them
(docs/messungen/2026-11-28-grooves-skalen-rot.md).

Korg's firmware has 25 grooves and 35 scales. Hacktribe added 37 grooves and 35 scales. This patch gives the red
build the same numbers, with grooves, chord tables and names of our own; no Hacktribe byte is in it, and no Korg
byte either. Korg's 25 grooves and 35 scales stay where they are in the menu and play as before.

Grooves. The firmware builds Korg's 25 groove templates (0x140 bytes each) at start into RAM (0xC068A03C), by code
at 0xC0051334 that reads the address from one literal. Four more literals give the readers (three, the groove engine)
and the name list the same address. All five point at GROOVES in erased image space: Korg's code then builds its 25
templates there itself, and our 37 follow as data (index 25 to 61). The menu wraps at 62 and the setter clamps at 61.

Scales. Four tables per scale, indexed by the scale number: steps (13 bytes, count and semitones), snap (12 signed
bytes, the way from each semitone to a scale tone), a name pointer and a pointer to the chord object. All four move
to erased image space with room for 70: the first 35 entries are copied at apply time from the user's own file (the
`copy` change of src/patch.mjs), the last 35 are ours. The chord object of a new scale is static data: the vtable
pointer, rows, variants and the address of its chord table; its row getter is a shared 3 word method that reads
that address from the object. The menu clamps at 69, the setter at 70 (Korg: 34 and 35).

Chord tables. A row is one chord pad (8 variants of 8 bytes: name index, root and bass, note count, up to 5 notes
in semitones from the key). Our rule, the same for every new scale with n steps: the chords of a row r are stacked
from the scale's own degrees (r, r+2, r+4, ...); variants 0 to 7 are the dyad, the triad, the seventh, the triad
with the octave, the triad with the ninth, an open seventh, a slash chord and a wide voicing. The name is the chord
the notes make (pitch class match, else the closest), as the firmware's 22 chord names allow.

The patch is data only: no code of ours runs, so EXIT at power-on cannot switch it off. Hacktribe has all of it.

    python3 tools/patch/grooves_scales.py --vsb SYSTEM.VSB [--out data/patches/grooves-scales.json]
    python3 tools/patch/grooves_scales.py --vsb SYSTEM.VSB --hacktribe HT.VSB      # compares scale steps only
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HEADER = 0x100
RAM = 0xC0000000
HACKTRIBE_CODE = (0x170100, 0x40)       # erased in Korg's own build, same rule as src/firmware.mjs buildOf

# ---- firmware places (Korg red 2.02) ----
GROOVE_RAM = 0xC068A03C                 # where Korg's builder puts its 25 templates
GROOVE_LITERALS = (0xC0047A28, 0xC0047A88, 0xC0047AE8, 0xC0052338)   # three readers, the builder
GROOVE_NAME_LITERAL = 0xC0080AF8        # the name list, template + 0x10
GROOVE_BUILDER_LITERAL = 0xC0052338     # read at start
GROOVE_CLAMPS = {                       # address: (original word, new word)
    0xC0049DA4: (0xE3520018, 0xE352003D),   # cmp r2, #24 -> #61, the setter
    0xC007BB88: (0x42822019, 0x4282203E),   # addmi r2, r2, #25 -> #62, menu wrap below 0
    0xC007BB90: (0xE3520018, 0xE352003D),   # cmp r2, #24 -> #61
    0xC007BB94: (0xC2422019, 0xC242203E),   # subgt r2, r2, #25 -> #62, menu wrap above the last
}
SCALE_STEPS, SCALE_SNAP, SCALE_NAMES, SCALE_OBJECTS = 0xC00DCF70, 0xC00DD148, 0xC00DD330, 0xC00DDB18
SCALE_PADS = 0xC00C5DB8                 # KEYBOARD: 16 notes per scale, read by the layout builder 0xC0044D28
SCALE_LITERALS = {
    0xC005423C: SCALE_STEPS, 0xC0054508: SCALE_SNAP, 0xC00545BC: SCALE_NAMES,
    0xC0055360: SCALE_OBJECTS, 0xC005537C: SCALE_OBJECTS, 0xC00553BC: SCALE_OBJECTS,
    0xC0044DA4: SCALE_PADS,
}
SCALE_CLAMPS = {
    0xC007CF24: (0xE3510022, 0xE3510045),   # cmp r1, #34 -> #69, the menu
    0xC007CF28: (0xA3A01022, 0xA3A01045),   # movge r1, #34 -> #69
    0xC004860C: (0xE3500023, 0xE3500046),   # cmp r0, #35 -> #70, the setter
    0xC0048610: (0xA3A00023, 0xA3A00046),   # movge r0, #35 -> #70
}
IONIAN_DTOR, IONIAN_DELETE = 0xC0054928, 0xC0054DA8    # the vtable of Korg's Ionian object, entries 0 and 1

# ---- sizes ----
KORG_GROOVES, GROOVES_TOTAL, TEMPLATE = 25, 62, 0x140
KORG_SCALES, SCALES_TOTAL = 35, 70
STEP_ENTRY, SNAP_ENTRY, PAD_ENTRY = 13, 12, 16
ROW, VARIANTS = 64, 8

# ---- our layout, erased image space of the red build ----
GROOVES = 0xC013C100                    # 62 templates; Korg's builder writes the first 25 at start
AREA = 0xC0141000                       # scale tables and chord data, up to AREA_END
AREA_END = 0xC014EE00                   # the update guard's code starts here
FREE_FROM = 0xC013C0B0                  # end of the DSP stream, erased up to AREA_END in Korg's red build

# The 22 chord names of the firmware (0xC00DD3E0) and the pitch classes we match them by. 'm9' is Korg's name
# for the minor triad with the ninth (it shows it on Ionian's minor rows); 'drone' and 'quintal' are not chords
# of thirds and are only used where nothing else fits.
CHORD_NAMES = ['', 'M7', 'add9', '7', 'M79', 'm', 'm7', 'm9', 'm7b5', '7sus4', 'dim', 'M7b5', 'dim7', '7b9', '9',
               'drone', 'mM7', 'm79', 'sus4', 'aug', 'quintal', 'octave']
QUALITIES = [
    ('', {0, 4, 7}), ('m', {0, 3, 7}), ('dim', {0, 3, 6}), ('aug', {0, 4, 8}), ('sus4', {0, 5, 7}),
    ('M7', {0, 4, 7, 11}), ('7', {0, 4, 7, 10}), ('m7', {0, 3, 7, 10}), ('m7b5', {0, 3, 6, 10}),
    ('dim7', {0, 3, 6, 9}), ('mM7', {0, 3, 7, 11}), ('M7b5', {0, 4, 6, 11}), ('7sus4', {0, 5, 7, 10}),
    ('add9', {0, 2, 4, 7}), ('m9', {0, 2, 3, 7}), ('M79', {0, 2, 4, 7, 11}), ('9', {0, 2, 4, 7, 10}),
    ('m79', {0, 2, 3, 7, 10}), ('7b9', {0, 1, 4, 7, 10}), ('quintal', {0, 2, 7}), ('drone', {0, 7}),
    ('octave', {0}),
]

# The 35 new scales: Hacktribe's numbers 35 to 69 with the same steps, so a pattern saved on Hacktribe plays the same
# scale here. The steps are the scales' own facts; the names are ours, at most 12 characters like Korg's.
SCALES = [
    ("Lydian Minor", [0, 2, 4, 6, 7, 8, 10]),
    ("Phrygian Dom", [0, 1, 4, 5, 7, 8, 10]),
    ("Major Bebop", [0, 2, 4, 5, 7, 8, 9, 11]),
    ("Minor Bebop", [0, 2, 3, 4, 5, 7, 9, 10]),
    ("Dom. Bebop", [0, 2, 4, 5, 7, 9, 10, 11]),
    ("Gregorian 4", [0, 2, 3, 5, 7, 8, 10, 11]),
    ("Lydian Dim", [0, 2, 3, 6, 7, 9, 10]),
    ("Aeolyptian", [0, 1, 3, 5, 6, 7, 11]),
    ("Superlocrian", [0, 1, 3, 4, 6, 8, 10]),
    ("Aeolian Pent", [0, 2, 3, 7, 8]),
    ("Kokin-joshi", [0, 1, 5, 7, 10]),
    ("Scottish", [0, 2, 5, 7, 9]),
    ("Iwato", [0, 1, 5, 6, 10]),
    ("Acoustic", [0, 2, 4, 6, 7, 9, 10]),
    ("Kamalamano", [0, 4, 5, 7, 8, 10]),
    ("Neapol. Maj", [0, 1, 3, 5, 7, 9, 11]),
    ("Neapol. min", [0, 1, 3, 5, 7, 8, 11]),
    ("Enigmatic", [0, 1, 4, 6, 8, 10, 11]),
    ("Shri Kalyan", [0, 2, 6, 7, 9]),
    ("Hung.Roman.", [0, 1, 2, 5, 6, 8, 9]),
    ("Salimic", [0, 2, 4, 6, 7, 10]),
    ("Epogimic", [0, 3, 4, 5, 8, 10]),
    ("Espla", [0, 1, 3, 4, 5, 6, 8, 10]),
    ("Spanish Octa", [0, 2, 3, 5, 6, 7, 8, 10]),
    ("Ionidyllic", [0, 2, 3, 5, 6, 8, 9, 10]),
    ("Epicryllic", [0, 2, 4, 5, 6, 8, 9, 10]),
    ("Cluster", [0, 1, 6, 7, 8, 9, 10]),
    ("Katycryllic", [0, 2, 5, 6, 7, 8, 9, 10]),
    ("Sindhura", [0, 2, 3, 5, 7, 11]),
    ("Chr.Hypolyd", [0, 1, 4, 6, 7, 8, 11]),
    ("Ionogian", [0, 2, 3, 4, 5, 9, 11]),
    ("Gycryllic", [0, 2, 3, 4, 6, 7, 9, 11]),
    ("Chr.Phrygian", [0, 3, 4, 5, 8, 10, 11]),
    ("Hamel", [0, 1, 3, 5, 7, 8, 10, 11]),
    ("Moptygic", [0, 2, 3, 4, 6, 7, 9, 10, 11]),
]

# Chord voicings by scale degree from the row's degree r (n = steps of the scale).
VOICINGS = [
    lambda n: [0, 2],                       # dyad
    lambda n: [0, 2, 4],                    # triad
    lambda n: [0, 2, 4, 6],                 # seventh
    lambda n: [0, 2, 4, n],                 # triad and octave
    lambda n: [0, 2, 4, n + 1],             # triad and ninth
    lambda n: [0, 4, 6, n + 2],             # open seventh
    lambda n: [0, 4, 6, n + 1, n + 3],      # slash chord over the root
    lambda n: [0, 6, n + 2, n + 4],         # wide
]


# ---- grooves ----
# A step is (offset, velocity, gate): offset in 96ths of a step, later is plus; velocity 1 to 127, 96 plays as
# written in Korg's own grooves; gate 96 is the full length.
def _lcg(seed):
    state = seed
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state


def _swing16(ratio, length=16):
    late = round(96 * (2 * ratio - 1))
    return [(late if i % 2 else 0, 96, 96) for i in range(length)]


def _swing8(ratio):
    late = round(192 * (2 * ratio - 1))
    return [((0, late // 2, late, late // 2)[i % 4], 96, 96) for i in range(16)]


def _humanize(seed, offset, velocity, gate, length=32):
    rnd = _lcg(seed)
    steps = []
    for i in range(length):
        o = 0 if i == 0 else next(rnd) % (2 * offset + 1) - offset
        v = 96 + next(rnd) % (2 * velocity + 1) - velocity
        g = 96 - next(rnd) % (gate + 1)
        steps.append((o, v, g))
    return steps


def _velocities(levels, length=16, offset=0, gate=96):
    return [(offset, levels(i), gate) for i in range(length)]


def _ramp(length, rising):
    vals = [round(24 + (127 - 24) * i / (length - 1)) for i in range(length)]
    return [(0, v, 96) for v in (vals if rising else vals[::-1])]


def _per_beat(offsets, velocities, gates=(96, 96, 96, 96), length=16):
    return [(offsets[i % 4], velocities[i % 4], gates[i % 4]) for i in range(length)]


GROOVE_LIST = [
    ("Swing 16th 54", _swing16(0.54)),
    ("Swing 16th 58", _swing16(0.58)),
    ("Swing 16th 62", _swing16(0.62)),
    ("Swing 16th 66", _swing16(0.66)),
    ("Swing 16th 71", _swing16(0.71)),
    ("Swing 8th 58", _swing8(0.58)),
    ("Swing 8th 62", _swing8(0.62)),
    ("Swing 8th 66", _swing8(0.66)),
    ("Shuffle", _per_beat((0, 31, 0, 31), (112, 72, 100, 72), (96, 72, 96, 72))),
    ("Humanize Light", _humanize(11, 3, 6, 6)),
    ("Humanize Mid", _humanize(23, 7, 12, 12)),
    ("Humanize Heavy", _humanize(37, 14, 22, 20)),
    ("Accent 1&3", _velocities(lambda i: 127 if i in (0, 8) else 84)),
    ("Accent Beats", _velocities(lambda i: 124 if i % 4 == 0 else 80)),
    ("Accent Offbeat", _velocities(lambda i: 124 if i % 4 == 2 else 80)),
    ("Accent 8ths", _velocities(lambda i: 110 if i % 2 == 0 else 64)),
    ("Ghost Notes", _per_beat((0, 0, 0, 0), (112, 36, 96, 36), (96, 60, 96, 60))),
    ("Push Light", [(-10, 96, 96)] * 16),
    ("Drag Light", [(10, 96, 96)] * 16),
    ("Push Offbeats", _per_beat((0, 0, -16, 0), (96, 96, 96, 96))),
    ("Late Backbeat", [((18, 104, 96) if i in (4, 12) else (0, 96, 96)) for i in range(16)]),
    ("Crescendo 2Bar", _ramp(32, True)),
    ("Decresc. 2Bar", _ramp(32, False)),
    ("Crescendo 4Bar", _ramp(64, True)),
    ("Decresc. 4Bar", _ramp(64, False)),
    ("Staccato", [(0, 96, 36)] * 16),
    ("Legato", [(0, 96, 127)] * 16),
    ("Long Short", [(0, 96, 110 if i % 2 == 0 else 40) for i in range(16)]),
    ("House Swing", _per_beat((0, 10, 0, 10), (88, 80, 118, 80), (96, 90, 80, 90))),
    ("2-Step", _per_beat((0, 26, 0, 26), (112, 70, 92, 70))),
    ("Lazy Feel", [(o, v, 96) for o, v in zip(
        (0, 20, 6, 26, 10, 22, 4, 30, 2, 18, 8, 24, 12, 20, 6, 28),
        (110, 70, 90, 64, 118, 72, 88, 66, 106, 74, 92, 62, 116, 70, 86, 68))]),
    ("3-3-2", [(0, 124 if i in (0, 3, 6) else 72, 96) for i in range(8)]),
    ("Bossa Feel", [((0, 120, 96) if i in (0, 3, 6, 10, 13) else (4, 76, 90)) for i in range(16)]),
    ("Samba Feel", _per_beat((0, -4, 6, -2), (100, 70, 84, 118))),
    ("Afro Feel", _per_beat((0, 20, 10, 30), (116, 76, 96, 80))),
    ("Reggae Skank", _per_beat((0, 0, 6, 0), (70, 60, 122, 60), (96, 80, 60, 80))),
    ("Halftime", [((12 if i % 2 else 0), (124 if i == 0 else 127 if i == 16 else 92 if i % 4 == 0 else 72), 96)
                  for i in range(32)]),
]


def template(name, steps):
    """One groove template in the firmware's format (0x140 bytes, read from Korg's own at runtime)."""
    if not 1 <= len(steps) <= 64 or 64 % len(steps):
        raise ValueError(f"{name}: a groove has 1 to 64 steps and divides 64")
    if len(name) > 15:
        raise ValueError(f"{name}: at most 15 characters")
    t = bytearray(TEMPLATE)
    t[0:4] = b"GVST"
    t[0x0C] = 0xFF
    t[0x10:0x10 + len(name)] = name.encode("ascii")
    t[0x22] = len(steps)
    t[0x23] = 0xFF
    for i, (o, v, g) in enumerate(steps):
        if not (-127 <= o <= 127 and 1 <= v <= 127 and 1 <= g <= 127):
            raise ValueError(f"{name}: step {i} out of range")
        t[0x30 + 4 * i:0x34 + 4 * i] = bytes((o & 0xFF, v, g, 0xFF))
    t[0x13C:0x140] = b"GVED"
    return bytes(t)


# ---- scales ----
def snap(steps):
    """Per semitone above the key, the way to the nearest scale tone (the octave counts); a tie goes up."""
    tones = steps + [12]
    out = []
    for s in range(12):
        best = min(tones, key=lambda t: (abs(t - s), -t))
        out.append(best - s)
    return out


def chord_name(notes):
    """(name index, root pc or None, bass pc or None) for notes in semitones from the key."""
    pcs = {n % 12 for n in notes}
    bass = notes[0] % 12
    best = None
    for root in [bass] + sorted(pcs - {bass}):
        rel = {(p - root) % 12 for p in pcs}
        for rank, (name, quality) in enumerate(QUALITIES):
            if name in ('octave', 'drone', 'quintal') and len(pcs) > len(quality):
                continue
            hit, extra, missing = len(rel & quality), len(rel - quality), len(quality - rel)
            if 0 not in quality & rel:
                continue
            score = (hit - 3 * extra - missing, root == bass, -rank)
            if best is None or score > best[0]:
                best = (score, name, root)
    _, name, root = best
    return CHORD_NAMES.index(name), root, None if root == bass else bass


def chord_table(steps):
    """One row per scale degree, 8 variants each, 64 bytes a row."""
    n = len(steps)
    note = lambda d: 12 * (d // n) + steps[d % n]  # noqa: E731
    table = bytearray()
    for r in range(n):
        for voicing in VOICINGS:
            notes = [note(r + d) for d in voicing(n)]
            name, root, bass = chord_name(notes)
            entry = bytearray(b"\xff" * 8)
            entry[0] = name
            entry[1] = ((root + 1) << 4) | (0 if bass is None else bass + 1)
            entry[2] = len(notes)
            entry[3:3 + len(notes)] = bytes(n_ & 0xFF for n_ in notes)
            table += entry
    return bytes(table)


def pad_notes(steps):
    """The 16 KEYBOARD notes of a scale, Korg's rule: the lower row is the first 8 notes of the scale from the root
    up, the upper row the same an octave higher (table order: lower row first)."""
    n = len(steps)
    row = [12 * (d // n) + steps[d % n] for d in range(8)]
    return bytes(row + [12 + x for x in row])


def scale_steps(steps):
    return bytes([len(steps)] + steps + [0] * (12 - len(steps)))


# ---- the patch ----
def off(address):
    return address - RAM + HEADER


def build_of(raw):
    if raw[0x10:0x13] == b"E2\0":
        return "synth"
    run = raw[HACKTRIBE_CODE[0]:HACKTRIBE_CODE[0] + HACKTRIBE_CODE[1]]
    return "stock" if run == b"\xff" * HACKTRIBE_CODE[1] else "hacktribe"


def word(raw, address):
    return struct.unpack_from("<I", raw, off(address))[0]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def layout():
    """Addresses of our tables in AREA, in order, and the bytes of everything that is ours."""
    at = AREA
    place = {}

    def take(key, size, align=4):
        nonlocal at
        at = (at + align - 1) & ~(align - 1)
        place[key] = at
        at += size

    take("steps", SCALES_TOTAL * STEP_ENTRY)
    take("snap", SCALES_TOTAL * SNAP_ENTRY)
    take("names", SCALES_TOTAL * 4)
    take("objects", SCALES_TOTAL * 4)
    take("method", 12)
    take("vtable", 24)
    take("objs", len(SCALES) * 16)
    take("chords", sum(len(s) for _, s in SCALES) * ROW)
    take("strings", sum(len(n) + 1 for n, _ in SCALES))
    take("pads", SCALES_TOTAL * PAD_ENTRY)
    if at > AREA_END:
        raise ValueError(f"the scale data ends at {at:#x}, beyond {AREA_END:#x}")
    return place, at


def ours():
    """(address, bytes) of all data the patch writes, the copied Korg entries left out."""
    place, _ = layout()
    blobs = []
    blobs.append((GROOVES + KORG_GROOVES * TEMPLATE, b"".join(template(n, s) for n, s in GROOVE_LIST)))
    blobs.append((place["steps"] + KORG_SCALES * STEP_ENTRY, b"".join(scale_steps(s) for _, s in SCALES)))
    blobs.append((place["pads"] + KORG_SCALES * PAD_ENTRY, b"".join(pad_notes(s) for _, s in SCALES)))
    blobs.append((place["snap"] + KORG_SCALES * SNAP_ENTRY, b"".join(bytes(v & 0xFF for v in snap(s)) for _, s in SCALES)))
    strings, names, at = b"", [], place["strings"]
    for name, _ in SCALES:
        names.append(at + len(strings))
        strings += name.encode("ascii") + b"\0"
    blobs.append((place["names"] + KORG_SCALES * 4, struct.pack(f"<{len(names)}I", *names)))
    blobs.append((place["strings"], strings))
    blobs.append((place["method"], struct.pack("<3I", 0xE590000C, 0xE0800301, 0xE12FFF1E)))   # ldr r0,[r0,#12]; add r0,r0,r1,lsl #6; bx lr
    blobs.append((place["vtable"], struct.pack("<6I", IONIAN_DTOR, IONIAN_DELETE, place["method"], 0, 0, 0)))
    objs, chords, ptrs = b"", b"", []
    for _, steps in SCALES:
        table = place["chords"] + len(chords)
        ptrs.append(place["objs"] + len(objs))
        objs += struct.pack("<4I", place["vtable"], len(steps), VARIANTS, table)
        chords += chord_table(steps)
    blobs.append((place["objs"], objs))
    blobs.append((place["chords"], chords))
    blobs.append((place["objects"] + KORG_SCALES * 4, struct.pack(f"<{len(ptrs)}I", *ptrs)))
    return place, blobs


def build_patch(raw):
    build = build_of(raw)
    if build != "stock":
        raise ValueError("the patch is for Korg's red build; Hacktribe has its own grooves and scales")
    for at in (*GROOVE_LITERALS,):
        if word(raw, at) != GROOVE_RAM:
            raise ValueError(f"the literal at {at:#x} does not point at the groove templates")
    if word(raw, GROOVE_NAME_LITERAL) != GROOVE_RAM + 0x10:
        raise ValueError("the groove name literal is not the measured one")
    for at, table in SCALE_LITERALS.items():
        if word(raw, at) != table:
            raise ValueError(f"the literal at {at:#x} does not point at {table:#x}")
    for at, (old, _) in {**GROOVE_CLAMPS, **SCALE_CLAMPS}.items():
        if word(raw, at) != old:
            raise ValueError(f"the clamp at {at:#x} is not the measured one")
    if any(b != 0xFF for b in raw[off(FREE_FROM):off(AREA_END)]):
        raise ValueError(f"{FREE_FROM:#x} to {AREA_END:#x} is not erased")
    erased = lambda n: sha(b"\xff" * n)  # noqa: E731
    place, blobs = ours()
    changes = []

    def put(address, new, note=None):
        old = raw[off(address):off(address) + len(new)]
        change = {"file": off(address), "bytes": new.hex(), "expect": sha(old)}
        if note:
            change["note"] = note
        changes.append(change)

    for at in GROOVE_LITERALS:
        put(at, struct.pack("<I", GROOVES), "groove templates")
    put(GROOVE_NAME_LITERAL, struct.pack("<I", GROOVES + 0x10), "groove names")
    for at, (_, new) in GROOVE_CLAMPS.items():
        put(at, struct.pack("<I", new), "62 grooves")
    targets = {SCALE_STEPS: place["steps"], SCALE_SNAP: place["snap"], SCALE_NAMES: place["names"], SCALE_OBJECTS: place["objects"],
               SCALE_PADS: place["pads"]}
    for at, table in SCALE_LITERALS.items():
        put(at, struct.pack("<I", targets[table]), "scale table")
    for at, (_, new) in SCALE_CLAMPS.items():
        put(at, struct.pack("<I", new), "70 scales")
    for old, size in ((SCALE_STEPS, STEP_ENTRY), (SCALE_SNAP, SNAP_ENTRY), (SCALE_NAMES, 4), (SCALE_OBJECTS, 4), (SCALE_PADS, PAD_ENTRY)):
        length = KORG_SCALES * size
        source = raw[off(old):off(old) + length]
        changes.append({"file": off(targets[old]), "expect": erased(length),
                        "copy": {"file": off(old), "length": length, "expect": sha(source)},
                        "note": "Korg's 35 scales, copied from the file at apply time"})
    for address, data in blobs:
        put(address, data)
    start_phase = [{"file": off(GROOVE_BUILDER_LITERAL), "length": 4,
                    "why": "the firmware builds its 25 groove templates at start, at the address of this literal"},
                   {"file": off(GROOVES), "length": KORG_GROOVES * TEMPLATE,
                    "why": "the firmware writes its 25 groove templates here at start"},
                   {"file": off(0xC0049DA4), "length": 4,
                    "why": "the start sets each part's groove through the setter, whose limit is now 61"},
                   {"file": off(0xC005423C), "length": 4,
                    "why": "the start sets the pattern's scale, which takes its steps through this literal"},
                   {"file": off(0xC005537C), "length": 4,
                    "why": "the start asks for the chord object of the pattern's scale through this literal"},
                   {"file": off(place["objects"]), "length": KORG_SCALES * 4,
                    "why": "the start reads the chord object of the pattern's scale from the moved table"}]
    return {
        "format": "gelumpe-patch", "version": 1, "id": "grooves-scales",
        "name": "Grooves und Skalen: 62 Grooves, 70 Skalen",
        "builds": ["stock"],
        "notNeededOn": ["hacktribe"],
        "changes": changes,
        "startPhase": start_phase,
        "ram": [{"at": f"0x{GROOVES:08X}", "length": KORG_GROOVES * TEMPLATE,
                 "what": "Korg's 25 groove templates, built there by the firmware at start", "source": "tools/patch/grooves_scales.py:GROOVES"}],
    }


def compare_hacktribe(ht):
    """Hacktribe's scale steps 35 to 69 against ours: the numbers must play the same scale."""
    steps_at = struct.unpack_from("<I", ht, off(0xC005423C))[0]
    bad = 0
    for i, (name, steps) in enumerate(SCALES):
        e = ht[off(steps_at) + (KORG_SCALES + i) * STEP_ENTRY:][:STEP_ENTRY]
        theirs = list(e[1:1 + e[0]])
        if theirs != steps:
            bad += 1
            print(f"scale {KORG_SCALES + i} {name}: ours {steps}, Hacktribe {theirs}")
    print(f"{len(SCALES) - bad} of {len(SCALES)} scales have Hacktribe's steps")
    return bad == 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--hacktribe", type=Path, help="compare the scale steps with this Hacktribe file, write nothing")
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    if a.hacktribe:
        raise SystemExit(0 if compare_hacktribe(a.hacktribe.read_bytes()) else 1)
    text = json.dumps(build_patch(raw), indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
