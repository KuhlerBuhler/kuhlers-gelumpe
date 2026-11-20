"""Emulator checks for the egg on the page VERSION of the BLECH menu (tools/patch/script_egg.s).

MENU five times in a row on VERSION starts the show, four times does nothing; the LEDs blink at most 3 times a second, the pads
go red, blue, purple; the display light walks the colour wheel; the display shows the word and the start image by turns; EXIT
goes back to VERSION, the first time through NEW SAMPLE Unlocked for two seconds. The unlock is Global byte 251, which the
firmware keeps in the flash at switch-off (0x2300F7), and it stays there after a restart. menu_cases runs these as one part.

    tools/emu/.venv/bin/python tools/emu/egg_cases.py --patched NEW.VSB
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import menu_cases as mc  # noqa: E402
import last_pattern_cases  # noqa: E402

M_EGG = mc.script_hooks.EGG_WORK         # the egg's state byte (script_egg.s:M_EGG)
EGG_SLOT = 251                          # *GLOBALS + 251
EGG_FLASH = 0x2300F7                    # that byte in the flash (byte 247 of the Globals block at 0x230000)
UNLOCKED = 0x5A
SINGLE, PAD1_RED, PAD1_BLUE = 18, 44, 45   # REC, the two LEDs of pad 1 (data/script/names.mjs)
STEP = 0.05                              # the look every 50 ms


def egg(dev):
    return dev.read(M_EGG, 1)[0]


def unlock_byte(dev):
    at = mc.synthaddr.tr(mc.POWER_SAVE_OBJECT) if mc.synthaddr.is_synth(dev.payload) else mc.POWER_SAVE_OBJECT
    globals_at = dev.u32(at)
    return dev.read(globals_at + EGG_SLOT, 1)[0] if globals_at else None


def lit(fb):
    return sum(bin(b).count("1") for b in fb)


def presses(dev, n):
    for _ in range(n):
        mc.press(dev, "menu", wait=0.15)


def watch(dev, seconds):
    """Every STEP: (REC, pad 1 red, pad 1 blue, backlight levels, lit pixels of the frame buffer)."""
    out = []
    for _ in range(int(seconds / STEP)):
        dev.run(STEP)
        leds = dev.m.leds
        out.append((leds.get(SINGLE, 0), leds.get(PAD1_RED, 0), leds.get(PAD1_BLUE, 0),
                    tuple(mc.state(dev, mc.S_BL_R + 4 * k) for k in range(3)), lit(mc.frame(dev))))
    return out


def flashes_per_second(values, seconds):
    ons = sum(1 for a, b in zip(values, values[1:]) if not a and b)
    return ons / seconds


def colours(samples):
    """The colours pad 1 showed, in order, one per lit stretch."""
    out = []
    for red, blue in samples:
        colour = {(True, False): "red", (False, True): "blue", (True, True): "purple"}.get((bool(red), bool(blue)))
        if colour and (not out or out[-1] != colour):
            out.append(colour)
        elif not colour and out and out[-1] != "off":
            out.append("off")
    return [c for c in out if c != "off"]


def cases(payload, flash=None):
    return show_cases(payload, flash) + auto_save_cases(payload, flash)


def light_of(dev):
    return tuple(mc.state(dev, mc.S_BL_R + 4 * k) for k in range(3))


def auto_save_cases(payload, flash=None):
    """AUTO SAVE (on by default) compares the settings, the colour of the display light among them, when the BLECH screen is left.
    A screen switch of the firmware during the show ends the show first: the settings file keeps the colour from before, and the
    Globals with the unlock are not written either (the BLECH screen was left from level 1, not GLOBAL)."""
    dev = mc.boot(payload, flash, files=mc.CARD_FOLDER)
    dev.payload = payload
    mc.goto_top(dev, mc.LIST_VERSION)
    snap = dev.u32(mc.STATE + 0x1F8)                    # M_SNAP: AUTO SAVE took the checksum on entering
    light = light_of(dev)
    card = bytes(dev.m.mmc.card.medium.data)
    mc.count_erases(dev)
    presses(dev, 5)
    dev.run(1.0)
    during = (egg(dev), light_of(dev))
    mc.go(dev, 8)                                       # the firmware switches away while the show runs
    dev.run(0.5)
    after = (egg(dev), light_of(dev), dev.m.screen())
    same = bytes(dev.m.mmc.card.medium.data) == card
    return [{"id": "menu:egg_auto_save_keeps_the_show_out",
             "ok": bool(snap != 0 and during[0] == 1 and during[1] != light and after == (0, light, 8) and same and dev.erases == []
                        and not dev.m.asserts),
             "detail": f"checksum on entering {snap:#x}, light {light}, during the show {during}, after the switch {after}, "
                       f"card {'unchanged' if same else 'written'}, erases {dev.erases}"}]


def show_cases(payload, flash=None):
    out = []

    def add(name, ok, detail):
        out.append({"id": f"menu:egg_{name}", "ok": bool(ok), "detail": detail})

    dev = mc.boot(payload, flash)
    dev.payload = payload
    before = unlock_byte(dev)
    mc.goto_top(dev, mc.LIST_VERSION)
    shown = mc.texts_of(dev)
    presses(dev, 4)
    dev.run(0.5)
    first = before != UNLOCKED                          # a flash that was unlocked before shows no message
    add("four_presses_do_nothing", egg(dev) == 0 and mc.texts_of(dev) == shown and unlock_byte(dev) == before,
        f"egg {egg(dev)}, texts {mc.texts_of(dev)}, unlock byte {before} then {unlock_byte(dev)}")
    mc.press(dev, "edit_prev", wait=0.25)               # away and back: the count starts again
    mc.press(dev, "edit_next", wait=0.25)
    presses(dev, 1)
    add("count_starts_again_after_another_key", egg(dev) == 0 and mc.state(dev, mc.S_PAGE) == mc.LIST_VERSION,
        f"egg {egg(dev)} after 4 presses, EDIT away and back and one more")
    mc.goto_top(dev, 0)
    presses(dev, 1)                                     # MENU on another row goes into its group, no count
    mc.goto_top(dev, mc.LIST_VERSION)
    presses(dev, 5)
    started = (egg(dev), unlock_byte(dev), mc.state(dev, mc.S_LEVEL), mc.state(dev, mc.S_PAGE))
    add("five_presses_start_and_unlock", started == (1, UNLOCKED, 1, mc.LIST_VERSION), f"egg, unlock byte, level, page {started}")
    seen = watch(dev, 4.0)
    rec = [s[0] for s in seen]
    rate = flashes_per_second(rec, 4.0)
    add("leds_blink_at_most_3_a_second", 1.5 <= rate <= 3 and min(rec) == 0 and max(rec) == 255,
        f"REC lit {rate:.2f} times a second, levels {sorted(set(rec))}")
    pad = colours([(s[1], s[2]) for s in seen])
    add("pads_red_blue_purple", pad[:6] in (["red", "blue", "purple", "red", "blue", "purple"],
                                            ["blue", "purple", "red", "blue", "purple", "red"],
                                            ["purple", "red", "blue", "purple", "red", "blue"]), f"pad 1 showed {pad}")
    light = [s[3] for s in seen]
    add("display_light_walks_the_wheel", len(set(light)) >= 20 and all(max(c) == 15 for c in light),
        f"{len(set(light))} colours in 4 s, first {light[:3]}")
    pictures = [s[4] for s in seen]                     # a look can fall into the firmware's own drawing of the frame: the two
    two = [v for v, _ in Counter(pictures).most_common(2)]   # pictures shown most are the word and the image
    turns = [v for v in pictures if v in two]
    switches = sum(1 for a, b in zip(turns, turns[1:]) if a != b)
    add("word_and_start_image_by_turns", 3 <= switches <= 6 and len(two) == 2 and min(two) > 300 and len(turns) >= 0.9 * len(pictures),
        f"lit pixels {dict(Counter(pictures))}, {switches} changes between the two in 4 s")
    mc.press(dev, "exit", wait=0.3)
    message = (egg(dev), mc.texts_of(dev))
    dev.run(2.2)
    back = (egg(dev), mc.state(dev, mc.S_LEVEL), mc.state(dev, mc.S_PAGE), mc.texts_of(dev))
    settled = watch(dev, 1.0)
    want = (2, ("NEW SAMPLE", "Unlocked", "")) if first else (0, shown)
    add("exit_first_time_new_sample_message", message == want and back == (0, 1, mc.LIST_VERSION, shown),
        f"after EXIT {message}, 2.2 s later {back}")
    add("exit_gives_the_light_back", len(set((s[0], s[1], s[2], s[3]) for s in settled)) == 1 and not dev.m.asserts,
        f"LEDs and light over 1 s after the show {sorted(set((s[0], s[1], s[2], s[3]) for s in settled))}")
    presses(dev, 5)
    dev.run(0.5)
    again = egg(dev)
    mc.press(dev, "exit", wait=0.3)
    add("later_shows_skip_the_message", again == 1 and egg(dev) == 0 and mc.texts_of(dev) == shown,
        f"egg {again}, after EXIT {egg(dev)} {mc.texts_of(dev)}")
    kept = last_pattern_cases.switch_off(dev)
    add("unlock_kept_in_the_flash", kept is not None and kept[EGG_FLASH] == UNLOCKED,
        f"flash {EGG_FLASH:#x} after switch-off: {kept[EGG_FLASH] if kept else 'no switch-off'}")
    if kept is None:
        return out
    dev = mc.boot(payload, kept)
    dev.payload = payload
    mc.goto_top(dev, mc.LIST_VERSION)
    presses(dev, 5)
    dev.run(0.5)
    mc.press(dev, "exit", wait=0.3)
    add("unlock_survives_a_restart", unlock_byte(dev) == UNLOCKED and egg(dev) == 0 and mc.texts_of(dev) == shown,
        f"unlock byte {unlock_byte(dev)}, after the show and EXIT {egg(dev)} {mc.texts_of(dev)}")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patched", required=True)
    args = parser.parse_args()
    result = cases(Path(args.patched).read_bytes()[mc.HEADER:])
    print(json.dumps(result, indent=1))
    return 0 if all(c["ok"] for c in result) else 1


if __name__ == "__main__":
    sys.exit(main())
