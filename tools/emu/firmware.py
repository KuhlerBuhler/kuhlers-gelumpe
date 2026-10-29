# SPDX-License-Identifier: GPL-2.0-only
"""Which Sampler build is this image, and where do the places the emulator needs sit in it?

The emulator stands in for a few firmware routines (assert handler, flash read, DSP upload, the UART
send loop) and reads a few firmware variables (the screen manager, the panel object). Their addresses are
not fixed numbers of the emulator but facts of a build. Korg's own 2.02 and Hacktribe's 2.02 happen to put
all of them at the same addresses (measured, docs/emulator.md, "Original-Firmware"), and `identify` still
looks them up, so that a build that moved one is found where it is and one that lacks it is refused with
the name of what is missing, instead of being hooked at a wrong address.

The blue Electribe 2 (the synth, also numbered 2.02) is the same code base with every place moved by a few
thousand bytes; `identify` takes it as a third build, "synth" (docs/messungen/2026-10-15-blaue-electribe.md).

A place is found by its code, not by a table of file hashes, so a Hacktribe image whose presets, menus or
start image were edited, or one with patches in the rest of the code, is still recognised. The code is
compared as sixteen instruction words with everything that depends on where it sits masked out (branch
targets, pc-relative load offsets). The repository keeps only a hash of those masked words per place:
nothing of the firmware itself (no Korg data in the repository).

    tools/emu/.venv/bin/python tools/emu/firmware.py SYSTEM.VSB
    tools/emu/.venv/bin/python tools/emu/firmware.py SYSTEM.VSB --sign 0xC001E4AC
"""

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

BASE = 0xC0000000
PAYLOAD_SIZE = 0x200000
WINDOW = 16                  # instruction words a signature covers
HACKTRIBE_CODE = 0x170000    # payload offset of the code Hacktribe adds; erased (0xFF) in Korg's own build
HACKTRIBE_CODE_CHECK = 0x40


class ProfileError(ValueError):
    """The image is not a Sampler build the emulator knows how to hook; the message names what was not found."""


@dataclass(frozen=True)
class Site:
    """One place in the code. `at` is where it sits in the builds measured so far (tried first), `sig` the
    hash of the masked window that starts there. `entry` is the byte offset of the place inside the window.
    `reads` take a value out of the code: (name, byte offset, "literal"), the word an `ldr rX, [pc, #n]`
    at that offset loads, which is how the address of a variable is found."""
    name: str
    at: int
    sig: str
    entry: int = 0
    reads: tuple = ()


# Signatures made with `firmware.py IMAGE --sign ADDR`, from Korg's 2.02 and both Hacktribe images (they agree).
SITES = (
    Site("assert_handler", 0xC00298BC, "03177dac329e27b9"),   # the assertion: file name in r1, line in r2
    Site("flash_read", 0xC001E4AC, "31adb7ec114c982a"),       # driver read(dev, address, length, destination), 1 on success
    Site("dsp_upload", 0xC0011AB8, "077e5679104cf3a5"),       # boot(dsp, image, length), 271008 bytes over SPI1, 1 on success
    Site("tx_full", 0xC0024C98, "f95b578558319c82", entry=0x1C),   # UART send loop: the byte did not fit the queue
    Site("screens", 0xC002D048, "92aa343e391716b5", reads=(("screens", 4, "literal"),)),   # the screen manager singleton
    Site("panel", 0xC0028064, "7482ccd9ba4d8e6d", reads=(("panel", 4, "literal"),)),       # the panel object singleton
    Site("user_check", 0xC0029D78, "bff995be3a604677"),       # checks the user-data mark in flash
)
REQUIRED = ("assert_handler", "flash_read", "dsp_upload", "tx_full", "screens")

# The synth build (blue Electribe 2, 2.02). Six of the seven windows are word for word the Sampler's, only sitting
# elsewhere; the screen manager's is the same code that loads another singleton, so its signature (the pool word is
# part of it) is its own. `at` is where the places sit in the measured image.
SYNTH_AT = {"assert_handler": 0xC0026C34, "flash_read": 0xC0019DD4, "dsp_upload": 0xC000DD08, "tx_full": 0xC00205C0,
            "screens": 0xC002A1AC, "panel": 0xC00254D0, "user_check": 0xC00270BC}
SYNTH_SIG = {"screens": "60601afeda15e07a"}
SYNTH_SITES = tuple(replace(s, at=SYNTH_AT[s.name], sig=SYNTH_SIG.get(s.name, s.sig)) for s in SITES)
# What the firmware looks for at USER_MARK in flash before it accepts the user data.
SAMPLER_USER_MARK = b"KORGele2sUSR"
USER_MARKS = {"synth": b"KORGelec2USR"}
# The hardware a flash belongs to is its user-data mark: the Sampler code of Hacktribe runs on a blue Electribe 2 and
# finds the blue mark there (docs/ideen/65-blech-hacktribe-blau.md), so the mark is chosen by hardware, not by build.
HARDWARE_MARKS = {"red": SAMPLER_USER_MARK, "blue": USER_MARKS["synth"]}


def hardware_of_head(vsb):
    """"blue" when the head of a whole VSB names the blue Electribe 2 (file type "E2", the Sampler's is "E2S"), else
    "red". Hacktribe for the blue carries that head (src/firmware.mjs, isSynth)."""
    return "blue" if len(vsb) > 0x12 and vsb[0x10:0x12] == b"E2" and vsb[0x12] == 0 else "red"


def words(payload):
    return struct.unpack(f"<{len(payload) // 4}I", bytes(payload[:len(payload) // 4 * 4]))


def mask_word(w):
    """The word without what depends on where it sits: the offset of a branch, the offset of a pc-relative load."""
    if w & 0x0E000000 == 0x0A000000:
        return w & 0xFF000000
    if w & 0x0E1F0000 == 0x041F0000:
        return w & ~0x00800FFF
    return w


def digest(masked):
    return hashlib.sha256(struct.pack(f"<{len(masked)}I", *masked)).hexdigest()[:16]


def window(payload_words, offset):
    """Masked words of the window at payload byte `offset`."""
    return [mask_word(x) for x in payload_words[offset // 4:offset // 4 + WINDOW]]


def sign(payload, at):
    return digest(window(words(payload), at - BASE))


def search(payload, wanted):
    """{signature: [addresses]} of every window in the image that matches one of `wanted` (a set of signatures).
    Slow, about a second: only for a site that is not where it usually is."""
    w = [mask_word(x) for x in words(payload)]
    packed = struct.pack(f"<{len(w)}I", *w)
    found = {}
    for i in range(len(w) - WINDOW + 1):
        s = hashlib.sha256(packed[i * 4:i * 4 + WINDOW * 4]).hexdigest()[:16]
        if s in wanted:
            found.setdefault(s, []).append(BASE + i * 4)
    return found


def read_value(payload, window_at, entry_off, kind):
    """What a read takes out of the code at `window_at` + `entry_off`."""
    off = window_at - BASE + entry_off
    (w,) = struct.unpack_from("<I", payload, off)
    if kind == "literal":
        if w & 0x0E1F0000 != 0x041F0000:
            raise ProfileError(f"0x{window_at + entry_off:08x} ist kein pc-relativer Ladebefehl.")
        imm = w & 0xFFF
        target = off + 8 + (imm if w & 0x00800000 else -imm)
        return struct.unpack_from("<I", payload, target)[0]
    raise ValueError(kind)


@dataclass
class Profile:
    build: str                        # "hacktribe": Hacktribe's code is in the image; "stock": it is not; "synth": the blue Electribe 2
    sites: dict = field(default_factory=dict)     # name -> RAM address of the place
    values: dict = field(default_factory=dict)    # name -> what a read took out of the code
    moved: tuple = ()                 # sites found away from their usual address
    missing: tuple = ()               # sites not found or not readable (only optional ones, a missing required one is an error)

    def site(self, name):
        """Address of a place the caller cannot do without, or ProfileError that names it."""
        if name not in self.sites:
            raise ProfileError(f"{name} fehlt in diesem Abbild.")
        return self.sites[name]

    def value(self, name):
        if name not in self.values:
            raise ProfileError(f"{name} fehlt in diesem Abbild.")
        return self.values[name]

    @property
    def assert_handler(self): return self.sites["assert_handler"]
    @property
    def flash_read(self): return self.sites["flash_read"]
    @property
    def dsp_upload(self): return self.sites["dsp_upload"]
    @property
    def tx_full(self): return self.sites["tx_full"]
    @property
    def screens(self): return self.values["screens"]
    @property
    def user_mark(self):
        """The 12 bytes the firmware looks for in flash before it accepts the user data."""
        return USER_MARKS.get(self.build, SAMPLER_USER_MARK)

    def summary(self):
        """What the service tells the page (no firmware bytes)."""
        return {"build": self.build, "moved": list(self.moved), "missing": list(self.missing)}


def build_of(payload):
    """"hacktribe" when the code Hacktribe adds is in the image, else "stock". The code sits in a run that
    Korg's build leaves erased; a preset, menu or start image edit never touches it."""
    chunk = bytes(payload[HACKTRIBE_CODE:HACKTRIBE_CODE + HACKTRIBE_CODE_CHECK])
    return "stock" if chunk == b"\xff" * HACKTRIBE_CODE_CHECK else "hacktribe"


def identify(payload, sites=SITES, required=REQUIRED):
    """The Profile of a payload (the 0x200000 bytes behind the VSB header), or ProfileError. With the usual
    table, an image that is no Sampler build is tried as the synth's; the Sampler's error stands when it is not that either."""
    try:
        return _identify(payload, sites, required)
    except ProfileError as error:
        if sites is not SITES or len(payload) != PAYLOAD_SIZE:
            raise
        try:
            return _identify(payload, SYNTH_SITES, required, "synth")
        except ProfileError:
            raise error from None


def is_synth(payload):
    """Whether every place of the synth build sits where it was measured. No search, so cheap on any image."""
    if len(payload) != PAYLOAD_SIZE:
        return False
    w = words(payload)
    return all(digest(window(w, s.at - BASE)) == s.sig for s in SYNTH_SITES)


def _identify(payload, sites, required, build=None):
    if len(payload) != PAYLOAD_SIZE:
        raise ProfileError(f"Ein Sampler-Abbild hat {PAYLOAD_SIZE} Byte hinter dem Kopf, dieses hat {len(payload)}.")
    w = words(payload)
    found, moved, missing = {}, [], []
    lost = []
    for s in sites:
        off = s.at - BASE
        if 0 <= off <= PAYLOAD_SIZE - WINDOW * 4 and digest(window(w, off)) == s.sig:
            found[s.name] = s.at
        else:
            lost.append(s)
    if lost:
        # Look further only for what is not at its usual place.
        hits = search(payload, {s.sig for s in lost})
        for s in lost:
            at = hits.get(s.sig, [])
            if len(at) == 1:
                found[s.name] = at[0]
                moved.append(s.name)
            elif s.name in required:
                raise ProfileError(f"Das ist keine Sampler-2.02-Fassung, die der Emulator kennt: {s.name} " + ("ist mehrfach da." if at else "fehlt."))
            else:
                missing.append(s.name)
    profile = Profile(build or build_of(payload), {}, {}, tuple(moved))
    for s in sites:
        if s.name not in found:
            continue
        try:
            values = {key: read_value(payload, found[s.name], off, kind) for key, off, kind in s.reads}
        except ProfileError:
            if s.name in required:
                raise
            missing.append(s.name)
            continue
        profile.sites[s.name] = found[s.name] + s.entry
        profile.values.update(values)
    profile.missing = tuple(missing)
    return profile


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("vsb", type=Path)
    p.add_argument("--sign", action="append", default=[], metavar="ADDR",
                   help="print the signature of the window at this RAM address")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        print("VSB must contain a 0x100-byte header and 0x200000-byte payload", file=sys.stderr)
        return 1
    payload = raw[0x100:]
    for spec in a.sign:
        print(f"{spec} {sign(payload, int(spec, 0))}")
    if a.sign:
        return 0
    try:
        prof = identify(payload)
    except ProfileError as error:
        print(f"Nicht erkannt: {error}", file=sys.stderr)
        return 1
    print(json.dumps({**prof.summary(), "sites": {k: f"0x{v:08x}" for k, v in prof.sites.items()},
                      "values": {k: f"0x{v:x}" for k, v in prof.values.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
