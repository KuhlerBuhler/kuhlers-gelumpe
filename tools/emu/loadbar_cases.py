# SPDX-License-Identifier: GPL-2.0-only
"""Emulator checks for the loading animation and the look (tools/patch/load_bar.py, tools/art/loading).

check.py runs `cases` on every patched copy that carries the patch's hooks. With a card and an
e2sSample.all Blechy draws the line while the samples load, whatever the start image: every frame is the
picture load_bar.compose_reference makes for the key in the state, the percent counts up, from 95 percent the
finale plays, no frame shows the window "Loading nnn%" and the display stays dark through the switch to
DISPLAY INVERT. Without a card, with EXIT held at power-on and on every rescue path nothing of it runs. The
reference for "as it was" is the same copy with EXIT held at power-on, where no hook of the patch does anything.

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
from frame_match import matches_pages  # noqa: E402

IMAGE = 0xC0000000
KILL = spec.KILL_SWITCH
S_EXPECT, S_CUR, S_MAX, S_DONE, S_FRAME, S_MODE, S_DRAWN, S_KEY, S_LAST = (4 * i for i in range(9))
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
        self.lcd_positions = {}
        self.main_at = None
        t = 0.0
        while t < limit and not self.m.asserts:
            self.dev.run(SAMPLE)
            t += SAMPLE
            screen = self.dev.screen()["number"]
            self.lcd_positions[self.m.time_ns / 1e6] = (self.m.lcd_page, self.m.lcd_col)
            self.frames.append((self.m.time_ns / 1e6, self.dev.fb(), self.state(), screen, self.m.shown()))
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
        return tuple(self.dev.u32(spec.STATE + o) for o in (S_EXPECT, S_CUR, S_MAX, S_DONE, S_FRAME, S_MODE, S_DRAWN, S_KEY, S_LAST))

    def loader_ms(self):
        return None if not self.loader or self.loader[0][1] is None else self.loader[0][1] - self.loader[0][0]


def vsb_image(payload):
    return bytes(payload[SPLASH - IMAGE:SPLASH - IMAGE + 1024])


ART = None


def art():
    global ART
    ART = ART or spec.parse_loading(spec.LOAD_ART.read_bytes())
    return ART


def pictures(key):
    """The picture for a key and its complement (drawn while the BLECH menu is not yet armed with DISPLAY INVERT ON)."""
    ref = spec.compose_reference(art(), key)
    return ref, bytes(b ^ 0xFF for b in ref)


def entry(name, ok, detail):
    return {"id": f"loadbar:{name}", "ok": bool(ok), "detail": str(detail)}


def overlay_frames(run):
    """The frames in which the overlay was on and had drawn."""
    return [f for f in run.frames if f[2][0] == 1 and f[2][6] == 1 and f[3] != 1]


def mismatches(run):
    """(frames looked at, first frame that showed the animation in ms, ms of the frames that are not one of its pictures).

    The display follows the state by a few frames (the pages of a new picture go out one after the other), so a frame may show
    any of the last three keys, page by page. The page currently being sent can have its prefix and suffix from different
    keys at the recorded LCD column. Before the first frame that equals one, the display shows the start image the
    firmware drew early; and the one frame in which the firmware closes its window (just before the main screen) is its own."""
    frames, recent, bad, first = overlay_frames(run), [], [], None
    for t, fb, st, _, _ in frames:
        if not recent or recent[-1][0] != st[7]:
            recent = (recent + [(st[7], pictures(st[7]))])[-3:]
        candidates = [p for _, pair in recent for p in pair]
        if matches_pages(fb, candidates, run.lcd_positions[t]):
            first = first if first is not None else t
        elif first is not None and not (run.main_at and t >= run.main_at - 60):
            bad.append(round(t, 1))
    return frames, first, bad


def dark_share(shown):
    return sum(bin(b).count("1") for b in shown) / 8192


def case_bar(payload, flash):
    """Blechy draws the line, the percent counts up, the finale from 95, at most 20 pictures a second, the display stays dark,
    no frame shows the window; the loader is no slower than without the patch."""
    out = []
    run = Run(payload, flash)
    ref = Run(payload, flash, KILL)
    off = Run(without_overlay(payload), flash)
    frames, first, bad = mismatches(run)
    out.append(entry("overlay_frames_are_the_animation", len(frames) >= 30 and first is not None and first < 300 and not bad and not run.m.asserts and run.main_at is not None,
                     (f"{len(frames)} looks at the display (every 10 ms) from {frames[0][0]:.0f} ms to {frames[-1][0]:.0f} ms: from {first and round(first)} ms on each is exactly "
                      f"the picture of the key in the state (or its complement before DISPLAY INVERT), so none shows the window" + (f"; frames that differ at {bad[:5]} ms" if bad else "")) if frames else "no frame of the overlay"))
    keys = [st[7] for _, _, st, _, _ in frames]
    pcts = [k & 0xFF for k in keys]
    out.append(entry("percent_counts_up", pcts == sorted(pcts) and pcts and pcts[0] <= 5 and pcts[-1] >= spec.FINALE_AT,
                     f"the percent went from {pcts[0] if pcts else '?'} to {pcts[-1] if pcts else '?'}, never back"))
    early = [k for k in keys if (k & 0xFF) < spec.FINALE_AT and k >> 16]
    late = [k for k in keys if (k & 0xFF) >= spec.FINALE_AT]
    out.append(entry("finale_from_95", late and not early,
                     f"{len(late)} looks at the finale (percent {sorted({k & 0xFF for k in late})}, pictures {sorted({k >> 16 for k in late})}), "
                     f"none of its pictures before {spec.FINALE_AT} percent"))
    changes = [t for (t, _, st, _, _), prev in zip(frames[1:], frames) if st[7] != prev[2][7]]
    gaps = [round(b - a) for a, b in zip(changes, changes[1:])]
    out.append(entry("at_most_20_pictures_a_second", all(g >= spec.FRAME_MS - 10 for g in gaps) and len(changes) >= 5,
                     f"{len(changes)} new pictures, the shortest gap {min(gaps) if gaps else None} ms (looks every 10 ms, so one look of slack)"))
    shares = [dark_share(f[4]) for f in run.frames if f[3] != 1 and f[0] >= (first or 0) and f[2][0] == 1]
    out.append(entry("display_stays_dark", shares and min(shares) >= 0.6 and run.m.lcd_reverse,
                     f"from the first picture to the main screen at least {min(shares) if shares else 0:.0%} of the pixels are dark on the panel, "
                     f"also while the controller is switched to DISPLAY INVERT (reversed at the end: {run.m.lcd_reverse})"))
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
    after = [f for f in run.frames if f[3] == 1][-1][1]
    out.append(entry("main_screen_is_clean", after == [f for f in off.frames if f[3] == 1][-1][1] and run.state()[0] == 2,
                     "300 ms after the main screen the display equals the one of the same copy without the overlay's calls, the overlay is over (state 2)"))
    stock_window = [f for f in ref.frames if f[3] == 0 and f[0] > 400]
    shown = any(fb != stock_window[0][1] for _, fb, _, _, _ in stock_window) if stock_window else False
    out.append(entry("reference_shows_the_window", shown, "with EXIT held the firmware's own window changes on the display while the samples load, so the overlay is what covers it"))
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
    """A start image of the user's own is seen until the load begins; while the samples load the animation is."""
    image = vsb_image(payload)
    other = bytes(b ^ 0x5A for b in image)
    changed = bytearray(payload)
    changed[SPLASH - IMAGE:SPLASH - IMAGE + 1024] = other
    run = Run(bytes(changed), flash)
    frames, first, bad = mismatches(run)
    pcts = [st[7] & 0xFF for _, _, st, _, _ in frames]
    before = any(fb == display_of(other) for _, fb, st, _, _ in run.frames if st[6] != 1)
    return [entry("own_image_then_the_animation", before and len(frames) >= 30 and first is not None and not bad and pcts == sorted(pcts) and pcts[-1] >= spec.FINALE_AT,
                  f"the changed image on the display before the load: {before}; then {len(frames)} looks at the animation from {pcts[0] if pcts else '?'} to "
                  f"{pcts[-1] if pcts else '?'} percent" + (f"; frames that differ at {bad[:5]} ms" if bad else ""))]


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
    once held for 5 s (it waited for the end of the start, batteries out was the way); a short press does nothing, where
    the firmware switches off at the end of the start."""
    import menu_cases
    from power_off_cases import POWER_KEY
    from machine import pin
    import power_off
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
    done = dev.u32(spec.STATE + S_DONE)
    out.append(entry("card_error_keeps_the_overlay", ended and ended[0][1] == 4 and expect == 1 and done != 1 and not dev.m.asserts,
                     f"the loader returned {ended[0][1] if ended else None} at {round(ended[0][0], 2) if ended else None} s, the overlay state is then {expect:#x} (1: still drawn), done {done:#x}"))
    # the firmware's box "Card Error" comes with the main screen a few seconds later; the overlay is over by then and the
    # display shows Blechy's card picture instead of the box, until EXIT
    picture = spec.card_frame(4)
    while dev.u32(spec.ERR_CODE) != 4 and dev.m.time_ns / 1e9 < 20:
        dev.run(0.1)
    dev.run(0.2)
    boxed_over = dev.u32(spec.STATE) == 2
    ram = lambda: bytes(b for row in dev.m.fb for b in row)
    boxed = boxed_over and dev.u32(spec.ERR_CODE) == 4 and ram() == picture
    dev.press("exit")
    dev.run(0.5)
    out.append(entry("card_error_picture", boxed and dev.u32(spec.ERR_CODE) == 0x26 and ram() != picture and not dev.m.asserts,
                     f"with the box up the display is the card picture: {boxed}; after EXIT the code is {dev.u32(spec.ERR_CODE):#x} and the picture is gone"))
    if menu_cases.has_menu(payload) and not synthaddr_is_synth(payload):
        def stuck_start(kill):
            dev = WatchedDev(bytes(payload), flash, kill)
            card = card_with(cardstore.card_folder(payload), 20, 4)
            hold = FailingCard(card, dev)
            dev.m.insert_card(card)
            dev.window = []         # the firmware's power-off handler reached its one-second wait behind the "Power Off" box
            dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d, dev=dev: dev.window.append(dev.m.time_ns / 1e9),
                              begin=power_off.WAIT_CALL, end=power_off.WAIT_CALL)
            dev.run(0.5)
            hold.after = 0.5
            dev.run(1.0)
            return dev

        def press(dev, release_after, limit=7.0):
            """The key goes down (pin GPIO 7.15 low, the panel sends 06 01) and comes up after release_after seconds, or never.
            Returns the seconds until the power went (or limit)."""
            dev.m.inputs[pin(7, 15)] = 0
            dev.m.send(POWER_KEY)
            t = 0.0
            while dev.m.powered and t < limit:
                if release_after is not None and t >= release_after:
                    dev.m.inputs[pin(7, 15)] = 1
                dev.run(0.05)
                t += 0.05
            return t

        start = stuck_start(0)
        screen = start.screen()["number"]
        t = press(start, None)
        short = stuck_start(0)
        press(short, 1.0, 10.0)
        held = stuck_start(KILL)
        t_held = press(held, None)
        out.append(entry("power_key_during_the_start", screen == 0 and not start.m.powered and 4.9 <= t <= 5.5 and not start.window
                         and short.m.powered and not short.window and not held.m.powered and held.window,
                         f"screen {screen} while the start waits on the card, off {round(t, 2)} s after the power key went down and stayed; "
                         f"let go after 1 s still on after 10 s, past the end of the start: {short.m.powered}; "
                         f"with EXIT held at power-on the firmware's way: its Power Off box at {[round(w, 2) for w in held.window]} s, "
                         f"at the end of the start, off {round(t_held, 2)} s after the key"))
    return out


def without_look(payload):
    """The same copy with the display send's page compare put back to the firmware's own function."""
    out = bytearray(payload)
    struct.pack_into("<I", out, spec.PAGE_CALL - IMAGE, 0xEB000000 | (((spec.PAGE_FUNC - (spec.PAGE_CALL + 8)) >> 2) & 0xFFFFFF))
    return bytes(out)


def case_look(payload, flash):
    """The look (tools/patch/load_bar.py, restyle_reference): with the BLECH menu armed and DISPLAY INVERT ON every frame the
    display gets is the firmware's frame with the look, exactly as the reference draws it, while the firmware's frame buffer
    stays its own; an open app, DISPLAY INVERT OFF and EXIT held at power-on get the frame as it is."""
    import menu_cases
    out = []
    ram = lambda dev: bytes(b for row in dev.m.fb for b in row)
    vram = lambda dev: dev.read(spec.VRAM_ADDR, 1024)
    looked = lambda dev: ram(dev) == spec.restyle_reference(vram(dev)) and ram(dev) != vram(dev)
    plain = lambda dev: ram(dev) == vram(dev)
    if not menu_cases.has_menu(payload):
        run = Run(payload, flash)
        return [entry("look_needs_the_menu", plain(run.dev) and run.main_at is not None and not run.m.asserts,
                      "without the plugin runtime the BLECH menu is never armed: the display shows the frame buffer as it is")]
    dev = menu_cases.boot(payload, flash, adapter=True)
    dev.run(0.3)
    bare = menu_cases.boot(without_look(payload), flash, adapter=True)
    bare.run(0.3)
    out.append(entry("look_main_screen", looked(dev) and vram(dev) == vram(bare) and plain(bare) and not dev.m.asserts,
                     "the main screen on the display is restyle_reference of the frame buffer, and the frame buffer is the one of the same copy "
                     "without the page hook (whose display shows it as it is)"))
    dev.m.send([2, 1, 0, 100, 0])
    dev.run(0.05)
    dev.m.send([2, 1, 0, 40, 0])
    dev.run(0.3)
    window = dev.screen()["window"]
    out.append(entry("look_value_window", window and looked(dev), f"turning a knob opens the value window ({window:#x}), it gets the look too"))
    dev.run(1.5)
    menu_cases.go(dev, 3)
    dev.run(0.4)
    out.append(entry("look_menu_page", dev.screen()["number"] == 3 and looked(dev), f"the Pattern menu with its page tab (screen {dev.screen()['number']})"))
    menu_cases.goto_blechy(dev)
    dev.run(0.5)
    out.append(entry("look_app_untouched", menu_cases.open_app_entry(dev) != 0 and plain(dev) and any(ram(dev)),
                     "with the built-in app open on its page the display is the app's picture as it drew it"))
    menu_cases.press(dev, "exit", wait=0.6)
    menu_cases.goto_page(dev, menu_cases.PAGE_INVERT)
    dev.turn(-1, wait=0.4)
    menu_cases.go(dev, 1)
    dev.run(0.5)
    out.append(entry("look_off_with_invert_off", menu_cases.state(dev, menu_cases.S_INVERT) == 0 and plain(dev) and not dev.m.asserts,
                     "DISPLAY INVERT OFF: the main screen goes out as the firmware drew it"))
    held = menu_cases.boot(payload, flash, held=KILL, adapter=True)
    held.run(0.3)
    out.append(entry("look_off_with_exit_held", plain(held) and any(ram(held)) and not held.m.asserts, "EXIT held at power-on: the frame as it is"))
    return out


def synthaddr_is_synth(payload):
    import synthaddr
    return synthaddr.is_synth(payload)


GROUPS = (case_bar, case_off, case_rescue, case_custom_image, case_card_error, case_look)


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
    """The display while the samples load, at 40 percent or more (docs/images/blech-laden.png)."""
    png_dir.mkdir(parents=True, exist_ok=True)
    run = Run(payload, flash, limit=0.0)
    for _ in range(400):
        run.dev.run(SAMPLE)
        st = run.state()
        if st[0] == 1 and st[6] == 1 and (st[7] & 0xFF) >= 40:
            break
    else:
        raise SystemExit("the load never got to 40 percent")
    run.dev.run(0.06)            # the display follows the state by a few frames
    run.m.png(png_dir / "blech-laden.png", scale=5)
    return {"percent": run.state()[7] & 0xFF, "ms": round(run.m.time_ns / 1e6)}


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
