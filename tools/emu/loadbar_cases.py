# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the loading bar patch (tools/patch/load_bar.py,
docs/ideen/41-startbild-ausbauen.md).

check.py runs `cases` on every patched copy that carries the patch's hooks. With a card and an
e2sSample.all the BLECH image is shown while the samples load, whatever the start image: the underline
is the bar, the eyes look around, no frame shows the window "Loading nnn%". Without a card, with EXIT held at
power-on and on every rescue path nothing of it runs. The reference for "as it was" is the same
copy with EXIT held at power-on, where no hook of the patch does anything.

    tools/emu/.venv/bin/python tools/emu/loadbar_cases.py cases --patched NEW.VSB [--flash dump.bin]
    tools/emu/.venv/bin/python tools/emu/loadbar_cases.py shots --patched NEW.VSB --png-dir DIR [--flash dump.bin]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import cardstore  # noqa: E402
import fat32  # noqa: E402
import load_bar as spec  # noqa: E402
import sampleset  # noqa: E402
from machine import load_flash  # noqa: E402
from sdcard import MemoryMedium, SDCard  # noqa: E402
from splash_cases import DESC13, SPLASH, Dev, display_of  # noqa: E402

IMAGE = 0xC0000000
KILL = spec.KILL_SWITCH
S_EXPECT, S_CUR, S_MAX, S_DONE, S_FRAME, S_MODE, S_DRAWN, S_FILL, S_DX, S_FACE, S_FACE_NOW = (4 * i for i in range(11))
SAMPLE = 0.01                   # seconds of device time between two looks at the display
LOADER = spec.LOAD_FUNC
_card = {}


def has_hooks(payload):
    """True when the flush of the frame function branches into the patch's code."""
    word = struct.unpack_from("<I", payload, spec.FLUSH - IMAGE)[0]
    if word >> 24 != 0xEA:
        return False
    off = (word & 0xFFFFFF) | (0xFF000000 if word & 0x800000 else 0)
    return spec.CODE_AT <= spec.FLUSH + 8 + (off << 2) < spec.CODE_END


def card_with(folder, samples=20, seconds=4):
    """A formatted card with an e2sSample.all of `samples` samples, together `seconds` of audio (made once per process)."""
    key = (folder, samples, seconds)
    if key not in _card:
        image = fat32.format_image(64 * 1024 * 1024)
        volume = fat32.Volume(image)
        if samples:
            volume.write(f"KORG/{folder}/Sample/e2sSample.all", sampleset.build(sampleset.sized(samples, int(seconds * 48000))))
        volume.close()
        _card[key] = bytes(image)
    return SDCard(MemoryMedium(bytearray(_card[key])))


class WatchedDev(Dev):
    """Runs the machine on exactly as asked. Dev.run first lets Korg's own build load its user data unseen (Machine.finish_boot,
    300 ms with a card and e2sSample.all, 6 s without a card), which would hide the start image, the first overlay frames and
    Korg's own loading bar from the looks every 10 ms; here the looks begin at power-on, as they do on Hacktribe, where finish_boot does nothing."""

    def run(self, seconds):
        self.m.run_until(self.m.time_ns / 1e9 + seconds)


def without_overlay(payload):
    """The same copy with the four calls the overlay hooks put back to the firmware's own functions (STAT, the text update, the loader,
    the flush), so everything else of the set stays and the difference to the copy is the overlay's alone. A run with EXIT held
    switches off every patch of the set, which is a different question."""
    out = bytearray(payload)
    for site, func, link in ((spec.STAT_CALL, spec.STAT_FUNC, True), (spec.PROGRESS_CALL, spec.PROGRESS_FUNC, True),
                             (spec.LOAD_CALL, spec.LOAD_FUNC, True), (spec.FLUSH, spec.FLUSH_FUNC, False)):
        word = (0xEB000000 if link else 0xEA000000) | (((func - (site + 8)) >> 2) & 0xFFFFFF)
        struct.pack_into("<I", out, site - IMAGE, word)
    return bytes(out)


class Run:
    """A device booted with a card (or none), watched every 10 ms of device time until the main screen has been up for a while."""

    def __init__(self, payload, flash=None, held=0, card=True, samples=20, seconds=4, panel_version=None, limit=9.0):
        self.payload = bytes(payload)
        self.dev = WatchedDev(self.payload, flash, held)
        self.m = self.dev.m
        if panel_version is not None:
            self.m.panel_version = panel_version
        if card:
            self.m.insert_card(card_with(cardstore.card_folder(self.payload), samples, seconds))
        self.loader = []            # (start, end) of the loader in ms of device time
        self.hook_loader()
        self.frames = []            # (ms, display bytes, state words, screen number)
        self.main_at = None
        t = 0.0
        while t < limit and not self.m.asserts:
            self.dev.run(SAMPLE)
            t += SAMPLE
            screen = self.dev.screen()["number"]
            self.frames.append((self.m.time_ns / 1e6, self.dev.fb(), self.state(), screen))
            if screen == 1 and self.main_at is None:
                self.main_at = self.m.time_ns / 1e6
            if self.main_at is not None and self.m.time_ns / 1e6 > self.main_at + 300:
                break

    def hook_loader(self):
        """Notes when the sample loader starts and when it returns (the instruction after its caller's call)."""
        import unicorn
        from unicorn import arm_const as A
        uc, m, spans = self.m.uc, self.m, self.loader
        back = set()

        def leave(u, a, s, d):
            if spans and spans[-1][1] is None:
                spans[-1][1] = m.time_ns / 1e6

        def enter(u, a, s, d):
            spans.append([m.time_ns / 1e6, None])
            lr = u.reg_read(A.UC_ARM_REG_LR)
            if lr not in back:
                back.add(lr)
                u.hook_add(unicorn.UC_HOOK_CODE, leave, begin=lr, end=lr)
                u.ctl_flush_tb()
        uc.hook_add(unicorn.UC_HOOK_CODE, enter, begin=LOADER, end=LOADER)
        uc.ctl_flush_tb()

    def state(self):
        return tuple(self.dev.u32(spec.STATE + o) for o in (S_EXPECT, S_CUR, S_MAX, S_DONE, S_FRAME, S_MODE, S_DRAWN, S_FILL, S_DX, S_FACE, S_FACE_NOW))

    def loader_ms(self):
        return None if not self.loader or self.loader[0][1] is None else self.loader[0][1] - self.loader[0][0]


def vsb_image(payload):
    return bytes(payload[SPLASH - IMAGE:SPLASH - IMAGE + 1024])


def pixel(buf, x, y, v):
    """Set pixel (x, y) of a frame in the display's order (bit 0 is the top row of a page)."""
    i = (y >> 3) * 128 + x
    buf[i] = (buf[i] | (1 << (y & 7))) if v else (buf[i] & ~(1 << (y & 7)) & 0xFF)


def draw_face(frame, key):
    """The small face of `key` (place * 256 + level): dark pixels of the face whose dither threshold is below the level."""
    level, place = key & 0xFF, key >> 8 & 3
    x0, y0 = spec.FACE_PLACES[place]
    for dy, row in enumerate(spec.FACE):
        for dx, c in enumerate(row):
            if c == "X" and spec.BAYER[((y0 + dy) & 3) * 4 + ((x0 + dx) & 3)] < level:
                pixel(frame, x0 + dx, y0 + dy, 0)


def expected(image, fill, dx, blech, face=0):
    """The frame the patch draws for an image, a bar of `fill` pixels, the pupils `dx` to the side and the face `face`."""
    frame = bytearray(display_of(image))
    if blech:
        for x in range(88):
            lit = 0 if x < fill else x & 1
            pixel(frame, 20 + x, 61, lit)
            pixel(frame, 20 + x, 62, lit)
        for eye in (50, 77):
            for y in range(15, 18):
                for k in range(3):
                    pixel(frame, eye + k, y, 1)
        for eye in (50, 77):
            for y in range(15, 18):
                for k in range(3):
                    pixel(frame, eye + dx + k, y, 0)
        draw_face(frame, face)
    else:
        for x in range(fill):
            pixel(frame, x, 63, 0)
    return bytes(frame)


def signed(word):
    return word - (1 << 32) if word >= 0x80000000 else word


def entry(name, ok, detail):
    return {"id": f"loadbar:{name}", "ok": bool(ok), "detail": str(detail)}


def overlay_frames(run):
    """The frames in which the overlay was on and had drawn (the state says what was marked: fill and the pupils' step)."""
    return [f for f in run.frames if f[2][0] == 1 and f[2][6] == 1 and f[3] != 1]


def mismatches(run, image, blech):
    """(frames looked at, first frame that showed the overlay in ms, ms of the frames that are not the image with bar and pupils).

    The display follows the state by up to a frame (the pages are sent with the next flush), so a frame may show one of the
    last three states, page by page (the controller gets the pages one after the other, so a look in the middle of a transfer
    shows some pages new and some old); before the first frame that equals one, the display shows the start image the firmware drew early; and
    the one frame in which the firmware closes its window (just before the main screen) is its own."""
    frames, recent, bad, first = overlay_frames(run), [], [], None
    for t, fb, st, _ in frames:
        key = (st[7], signed(st[8]) if blech else 0, st[10] if blech else 0)
        if not recent or recent[-1][0] != key:
            recent = (recent + [(key, expected(image, key[0], key[1], blech, key[2]))])[-3:]
        if any(fb == exp for _, exp in recent) or all(any(fb[o:o + 128] == exp[o:o + 128] for _, exp in recent) for o in range(0, 1024, 128)):
            first = first if first is not None else t
        elif first is not None and not (run.main_at and t >= run.main_at - 60):
            bad.append(round(t, 1))
    return frames, first, bad


def case_bar(payload, flash):
    """The image stays, the bar grows to the end, the eyes move, no frame shows the window; the loader is no slower than without the patch."""
    out = []
    run = Run(payload, flash)
    ref = Run(payload, flash, KILL)
    off = Run(without_overlay(payload), flash)
    image = spec.ART.read_bytes()
    blech = True
    frames, first, bad = mismatches(run, image, blech)
    out.append(entry("overlay_frames_are_the_image", len(frames) >= 30 and first is not None and first < 300 and not bad and not run.m.asserts and run.main_at is not None,
                     (f"{len(frames)} looks at the display (every 10 ms) from {frames[0][0]:.0f} ms to {frames[-1][0]:.0f} ms: from {first and round(first)} ms on each is exactly the start image with the bar and the pupils "
                      f"as the state says, so none shows the window" + (f"; frames that differ at {bad[:5]} ms" if bad else "")) if frames else "no frame of the overlay"))
    fills = [st[7] for _, _, st, _ in frames]
    steps = {signed(st[8]) for _, _, st, _ in frames}
    out.append(entry("bar_grows_to_the_end", fills == sorted(fills) and fills and fills[-1] == (88 if blech else 128) and fills[0] < fills[-1] // 2,
                     f"the bar went from {fills[0]} to {fills[-1]} of {88 if blech else 128} pixels, never back"))
    out.append(entry("eyes_wander", len(steps) >= 5 and all(-5 <= s <= 5 for s in steps) if blech else True,
                     f"the pupils took {len(steps)} positions between {min(steps)} and {max(steps)} pixels" if blech else "not the BLECH image: no eyes"))
    # One card alone is noise: the same copy measured -0.12 % to +0.63 % with 18, 20 and 22 samples (unrelated changes elsewhere move
    # where the interrupts fall, docs/messungen/2026-10-18-ladebalken-streuung.md), so the sum over three cards is compared; the overlay
    # itself costs about half a percent there (six cards, every one of them slower), so the limit is 1 %
    pairs = [(run.loader_ms(), off.loader_ms())] + [(Run(payload, flash, samples=n).loader_ms(), Run(without_overlay(payload), flash, samples=n).loader_ms()) for n in (18, 22)]
    ok = all(m is not None and t is not None for m, t in pairs)
    mine, theirs = (sum(m for m, _ in pairs), sum(t for _, t in pairs)) if ok else (None, None)
    out.append(entry("loader_is_no_slower", ok and mine <= theirs * 1.01,
                     f"the loader ran {mine and round(mine, 1)} ms with the overlay, {theirs and round(theirs, 1)} ms in the same copy without the overlay's four calls, "
                     f"summed over cards of 20, 18 and 22 samples ({[(m and round(m, 1), t and round(t, 1)) for m, t in pairs]}); "
                     f"with EXIT held, every patch of the set off, the card of 20 took {ref.loader_ms() and round(ref.loader_ms(), 1)} ms"))
    out.append(entry("main_screen_is_no_later", run.main_at is not None and off.main_at is not None and run.main_at <= off.main_at + 20,
                     f"the main screen came at {run.main_at and round(run.main_at, 1)} ms with the overlay and at {off.main_at and round(off.main_at, 1)} ms in the same copy without it; "
                     f"with EXIT held, every patch of the set off, at {ref.main_at and round(ref.main_at, 1)} ms: the rest of the set starts later, the overlay does not"))
    keys = [st[10] for _, _, st, _ in frames]
    levels = sorted({k & 0xFF for k in keys})
    # the one frame in which the firmware closes its window, just before the main screen, is its own (as in mismatches)
    shown = [fb for t, fb, st, _ in frames if st[10] & 0xFF and not (run.main_at and t >= run.main_at - 60)]
    faces = [fb for fb in shown if fb != expected(image, 0, 0, blech) and any(fb)]
    margin = all(fb[(y >> 3) * 128 + x] == display_of(image)[(y >> 3) * 128 + x] for fb in shown for y in range(64) for x in list(range(0, 2)) + list(range(126, 128)))
    out.append(entry("faces_fade_in_at_the_edge", (not blech) or (len(levels) >= 3 and levels[0] == 0 and len(shown) >= 6 and len(faces) >= 6 and margin),
                     (f"the faces took the levels {levels} of 16, {len(shown)} looks at the display with a face, the two outer columns are the image's own in all of them; the exact pixels are part of overlay_frames_are_the_image")
                     if blech else "not the BLECH image: no faces"))
    after = [f for f in run.frames if f[3] == 1][-1][1]
    out.append(entry("main_screen_is_clean", after == [f for f in ref.frames if f[3] == 1][-1][1] and run.state()[0] == 2,
                     "300 ms after the main screen the display equals the one of the run with EXIT held, the overlay is over (state 2)"))
    stock_window = [f for f in ref.frames if f[3] == 0 and f[0] > 400]
    shown = any(fb != display_of(image) and any(fb) for _, fb, _, _ in stock_window)
    out.append(entry("reference_shows_the_window", shown, "with EXIT held the firmware's own window is on the display while the samples load, so the overlay is what covers it"))
    return out


def case_off(payload, flash):
    """Without a card, with EXIT held, and without e2sSample.all: nothing is expected, nothing is drawn."""
    out = []
    none = Run(payload, flash, card=False)
    bare = Run(without_overlay(payload), flash, card=False)
    held = Run(payload, flash, KILL)
    empty = Run(payload, flash, samples=0)
    for name, run in (("no_card", none), ("exit_held", held), ("no_sample_file", empty)):
        out.append(entry(f"{name}_is_stock", run.state()[0] != 1 and run.state()[0] != 2 and run.main_at is not None and not run.m.asserts,
                         f"the patch never expects a load (state {run.state()[0]:#x}) and the main screen comes at {run.main_at and round(run.main_at, 1)} ms"))
    # Korg's own build draws its own loading bar over the start image while it loads the user data (about 6 s without a card), so
    # "only the start image" holds on Hacktribe alone; what holds on both is that the overlay changes nothing: every look equals the one
    # of the same copy with the overlay's four calls put back (the last frame of a run may be missing in one of them: the end
    # of a run is 300 ms after the main screen, which the two reach within a few ms of each other)
    shown, bare_shown = [f[1] for f in none.frames], [f[1] for f in bare.frames]
    same = all(a == b for a, b in zip(shown, bare_shown)) and abs(len(shown) - len(bare_shown)) <= 2
    out.append(entry("no_card_draws_nothing", len(shown) >= 30 and same and any(any(fb) for fb in shown),
                     f"without a card the {len(shown)} looks at the display from power-on to 300 ms after the main screen are those of the same copy without the overlay's calls ({len(bare_shown)} looks), "
                     f"so no bar, no eyes, no face and no window of the overlay"))
    return out


def case_rescue(payload, flash):
    """The panel update and the start modes get no overlay."""
    out = []
    runs = {"panel_update": Run(payload, flash, panel_version=0x95, limit=2.0), "start_mode_1": Run(payload, flash, 0x18000000, limit=2.0),
            "start_mode_8": Run(payload, flash, 0x00140000, limit=2.0), "start_mode_11": Run(payload, flash, 0x0A000000, limit=2.0),
            "update_offer": None}
    for name, run in runs.items():
        if run is None:
            continue
        out.append(entry(f"{name}_untouched", run.state()[0] not in (1, 2) and run.state()[4] in (0xFFFFFFFF, 0) and not run.m.asserts,
                         f"with the card and e2sSample.all in, the patch never expects a load on this start path (state {run.state()[0]:#x}, frames {run.state()[4]:#x})"))
    return out


def case_custom_image(payload, flash):
    """A start image that is not the BLECH one is seen until the load begins; while the samples load the BLECH image with bar and eyes is."""
    image = vsb_image(payload)
    other = bytes(b ^ 0x5A for b in image)
    changed = bytearray(payload)
    changed[SPLASH - IMAGE:SPLASH - IMAGE + 1024] = other
    run = Run(bytes(changed), flash)
    frames, first, bad = mismatches(run, spec.ART.read_bytes(), True)
    fills = [st[7] for _, _, st, _ in frames]
    steps = {signed(st[8]) for _, _, st, _ in frames}
    before = any(fb == display_of(other) for _, fb, st, _ in run.frames if st[6] != 1)
    return [entry("other_image_then_blech_with_eyes", before and len(frames) >= 30 and first is not None and not bad and st_mode(frames) == 1
                  and fills == sorted(fills) and fills[-1] == 88 and len(steps) >= 5,
                  f"the changed image on the display before the load: {before}; then {len(frames)} looks at the BLECH image with a bar of {fills[0] if fills else '?'} to "
                  f"{fills[-1] if fills else '?'} of 88 pixels and the pupils in {len(steps)} places" + (f"; frames that differ at {bad[:5]} ms" if bad else ""))]


def st_mode(frames):
    return frames[-1][2][5] if frames else None


class FailingCard:
    """A card whose reads stop answering from a moment on (no answer to the read command, as a card that gave up)."""

    def __init__(self, card, dev):
        self.card, self.dev, self.after = card, dev, None
        original = card.command

        def command(idx, arg):
            if idx in (17, 18) and self.after is not None and dev.m.time_ns / 1e9 >= self.after:
                return ("timeout",)
            return original(idx, arg)
        card.command = command


def case_card_error(payload, flash):
    """A card that stops answering while the samples load: the loader ends with the card error and the overlay goes at once, so
    the firmware's window is seen (device 18.10.: the image stayed over it). The power key while the start still runs switches off
    at once (it waited for the end of the start, batteries out was the way)."""
    import menu_cases
    from power_off_cases import POWER_KEY
    out = []
    dev = WatchedDev(bytes(payload), flash, 0)
    card = card_with(cardstore.card_folder(payload), 20, 4)
    fail = FailingCard(card, dev)
    dev.m.insert_card(card)
    ended = []
    import unicorn
    from unicorn import arm_const as A
    dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: ended.append((dev.m.time_ns / 1e9, u.reg_read(A.UC_ARM_REG_R0))),
                      begin=spec.LOAD_CALL + 4, end=spec.LOAD_CALL + 4)
    dev.run(0.5)
    fail.after = 0.5
    while not ended and dev.m.time_ns / 1e9 < 12:
        dev.run(0.05)
    dev.run(0.1)
    expect = dev.u32(spec.STATE)
    out.append(entry("card_error_ends_the_overlay", ended and ended[0][1] == 4 and expect == 2 and not dev.m.asserts,
                     f"the loader returned {ended[0][1] if ended else None} at {round(ended[0][0], 2) if ended else None} s, the overlay state is then {expect:#x} (2: over)"))
    if menu_cases.has_menu(payload) and not synthaddr_is_synth(payload):
        start = WatchedDev(bytes(payload), flash, 0)
        card = card_with(cardstore.card_folder(payload), 20, 4)
        hold = FailingCard(card, start)
        start.m.insert_card(card)
        start.run(0.5)
        hold.after = 0.5
        start.run(1.0)
        screen = start.screen()["number"]
        start.m.send(POWER_KEY)
        t = 0.0
        while start.m.powered and t < 2.0:
            start.run(0.05)
            t += 0.05
        held = WatchedDev(bytes(payload), flash, KILL)
        card = card_with(cardstore.card_folder(payload), 20, 4)
        stuck = FailingCard(card, held)
        held.m.insert_card(card)
        held.run(0.5)
        stuck.after = 0.5
        held.run(1.0)
        held.m.send(POWER_KEY)
        held.run(1.0)
        out.append(entry("power_key_during_the_start", screen == 0 and not start.m.powered and t <= 0.3 and held.m.powered,
                         f"screen {screen} while the start waits on the card, off {round(t, 2)} s after the power key; with EXIT held at power-on still on after 1 s (the firmware's way)"))
    return out


def synthaddr_is_synth(payload):
    import synthaddr
    return synthaddr.is_synth(payload)


GROUPS = (case_bar, case_off, case_rescue, case_custom_image, case_card_error)


def group_entries(payload, flash, i):
    """check.py entries of case group i; each boots its own devices, so they can run side by side."""
    return GROUPS[i](payload, flash)


def cases_task(i):
    """group_entries in a worker (parallel.py)."""
    import parallel
    return group_entries(parallel.shared["payload"], parallel.shared["flash"], i)


def cases(payload, flash=None):
    return [e for i in range(len(GROUPS)) for e in group_entries(payload, flash, i)]


def shots(payload, flash, png_dir):
    """The display while the samples load, in the first frame where a face is at full strength (docs/images/blech-ladebalken-gesicht.png)."""
    png_dir.mkdir(parents=True, exist_ok=True)
    run = Run(payload, flash, limit=0.0)
    for _ in range(400):
        run.dev.run(SAMPLE)
        st = run.state()
        if st[0] == 1 and st[10] & 0xFF == 16 and st[7] > 20:
            break
    else:
        raise SystemExit("no face at full strength while loading")
    run.dev.run(0.06)            # the display follows the state by a frame
    run.m.png(png_dir / "blech-ladebalken-gesicht.png", scale=5)
    return {"face": hex(run.state()[10]), "fill": run.state()[7], "ms": round(run.m.time_ns / 1e6)}


def main():
    import lifetime
    lifetime.exit_with_parent()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=("cases", "shots"))
    p.add_argument("--png-dir", type=Path)
    p.add_argument("--patched", required=True, type=Path)
    p.add_argument("--flash", nargs="*", default=[], type=Path)
    p.add_argument("--only", type=int, help="run one group")
    a = p.parse_args()
    payload = a.patched.read_bytes()[0x100:]
    flash = load_flash(a.flash) if a.flash else None
    if a.what == "shots":
        if not a.png_dir:
            p.error("shots needs --png-dir")
        print(json.dumps(shots(payload, flash, a.png_dir), indent=1))
        return 0
    entries = group_entries(payload, flash, a.only) if a.only is not None else cases(payload, flash)
    print(json.dumps(entries, indent=1))
    return 0 if all(e["ok"] for e in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
