"""Emulator cases of plugin API 14: korg.passKeys lets an open app choose the keys that reach the firmware
(and korg.display.take with SHIFT held still lets SHIFT's release through),
korg.seq.setPartValue edits a part as a knob does (pattern, sound engine, parameter window), korg.read.patternBytes and
korg.seq.writeSteps copy a part of a stored pattern into the one that plays, and the copy survives WRITE and a reload.

    PYTHONPATH=tools/patch python3 tools/emu/plugin_edit_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import node_json  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PATTERN_PTR = 0xC033E6A4        # the pattern in RAM, its block from +4
BANK = 0xC08B2940               # the pattern bank in RAM, 0x4000 per pattern
RUNNING = 0xC06B2420            # the number of the pattern in RAM
PART = 0xC06B2428               # the selected part
TRANSPORT = 0xC06BC318
MUTE = 0xC06B2F9D               # a part's mute byte, 0x330 per part
PART_AT = lambda part: 0x800 + 0x330 * part     # noqa: E731
STEP_AT = lambda part, step: PART_AT(part) + 0x30 + 12 * step   # noqa: E731
SHIFT = 10                     # the SHIFT key's number in the panel messages
SHIFT_OBJ = 0xC0040F04         # returns the object that holds the SHIFT flag at +0x358
APP_PAGE = 1                   # the page of the app in TOOLS, behind Blechy
SOURCE, TARGET, COMMAND = 5, 7, 9     # the stored pattern copied from, the part copied into, the pattern whose byte starts a step

# the part values the copy carries over, by PART_FIELDS index: every one the part edit writes, modType before its speed and depth
WRITABLE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 18]
PART_OFFSETS = {1: 12, 2: 13, 3: 14, 4: 15, 5: 16, 6: 17, 7: 18, 8: 20, 9: 21, 10: 24, 11: 25, 14: 34, 15: 36, 16: 37, 18: 11}

PROGRAMS = {
    "keys": """korg.app("Keys", "TOOLS");
korg.onEvent("open", () => { korg.passKeys(korg.key.PART_MUTE, 1); korg.passKeys(korg.key.PLAY, 0); });""",
    "nokeys": """korg.app("Keys", "TOOLS");
korg.onEvent("open", () => { });""",
    # no app: SHIFT pressed takes the display, a frame counter gives it back (alarykko, 13.11.)
    "taker": """let owned = 0;
let t = 0;
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.SHIFT && owned == 0) owned = korg.display.take();
});
korg.onEvent("frame", () => {
  if (owned != 1) return;
  korg.display.rect(0, 0, 128, 64);
  t = t + 1;
  if (t > 40) { korg.display.release(); owned = 2; }
});""",
    # the filter type byte of part 0 of pattern COMMAND says which edit to make, once each
    "edit": f"""let done = 0;
korg.onEvent("frame", () => {{
  let go = korg.read.patternValue({COMMAND}, 0, 1);
  if (go == done) return;
  done = go;
  if (go == 1) korg.parts[0].level = LEVEL;
  if (go == 2) korg.parts[5].pitch = -100;
  if (go == 3) korg.seq.setPartValue(0, 11, -20);
}});""",
    # the copy starts when part 2 of the stored pattern has the cutoff 33, the last byte the case writes
    "copy": f"""const steps = new Array(768);
const fields = [{", ".join(map(str, WRITABLE))}];
let read = 0; let wrote = 0; let done = 0;
korg.onEvent("frame", () => {{
  if (done == 1 || korg.read.patternValue({SOURCE}, 2, 2) != 33) return;
  done = 1;
  read = korg.read.patternBytes(steps, {SOURCE}, {STEP_AT(2, 0)});
  wrote = korg.seq.writeSteps(steps, {TARGET}, 0);
  for (let i = 0; i < {len(WRITABLE)}; i = i + 1) korg.seq.setPartValue({TARGET}, fields[i], korg.read.patternValue({SOURCE}, 2, fields[i]));
}});""",
}


def compiled(programs):
    """The include of the contract and the blobs and symbols of the programs, from the compiler of this checkout. The blocks
    are marked as probed by the editor, so an app on the card runs without the user allowing it in the menu."""
    return node_json.compiled(programs, probed=True)


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    # edit_cases compiles the edit with the LEVEL the knob left, a part value of 0 to 127
    for level in range(128):
        compiled({"edit": PROGRAMS["edit"].replace("LEVEL", str(level))})
    compiled({k: v for k, v in PROGRAMS.items() if k != "edit"})


def entry(name, ok, detail):
    return {"id": f"plugin_edit:{name}", "ok": bool(ok), "detail": str(detail)}


def boot(vsb, flash, programs, name):
    """An app on the card, as the user has it."""
    dev = script_cases.with_card(vsb, flash, {script_cases.CARD_FILE: script_cases.archive([bytes.fromhex(programs[name]["blob"])])})
    dev.run(2)
    return dev


def running(vsb, flash, built, programs, name):
    """A plugin that runs: installed into the runtime of a booted device, as the editor's test run does."""
    dev = menu_cases.boot(vsb[0x100:], flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    return dev, script_cases.install(dev, built, programs, [name])[name]


def pattern(dev):
    return dev.u32(PATTERN_PTR) + 4


def poke(dev, address, data):
    dev.m.uc.mem_write(address, bytes(data))


def tap_key(dev, key, wait=0.15):
    dev.m.send([0, key, 1, 0, 0])
    dev.run(0.08)
    dev.m.send([0, key, 0, 0, 0])
    dev.run(wait)


def pad(dev, index):
    dev.m.send([4, index, 0, 100, 1])
    dev.run(0.12)
    dev.m.send([4, index, 0, 0, 0])
    dev.run(0.12)


def mute_with_pad(dev, index):
    """PART MUTE held, the pad pressed: the firmware toggles that part's mute when it gets the key, and selects the part when
    it gets only the pad. -> the mute byte before and after."""
    before = dev.read(dev.a(MUTE) + 0x330 * index, 1)[0]
    dev.m.send([0, 16, 1, 0, 0])
    dev.run(0.1)
    pad(dev, index)
    dev.m.send([0, 16, 0, 0, 0])
    dev.run(0.15)
    return before, dev.read(dev.a(MUTE) + 0x330 * index, 1)[0]


def keys_cases(vsb, flash, programs):
    out = []
    plain = boot(vsb, flash, programs, "nokeys")
    script_cases.open_app(plain, menu_cases.GROUP_TOOLS, APP_PAGE)
    plain.run(0.2)
    mute = mute_with_pad(plain, 4)
    kept = mute[0] == mute[1] and plain.u32(PART) == 4
    tap_key(plain, 2, 0.3)
    played = plain.u32(TRANSPORT)
    tap_key(plain, 1, 0.3)
    out.append(entry("app_keeps_part_mute_play_passes", kept and played != 0 and not plain.m.asserts,
                     f"mute byte {mute}, part {plain.u32(PART)}, transport after PLAY {played}"))

    dev = boot(vsb, flash, programs, "keys")
    script_cases.open_app(dev, menu_cases.GROUP_TOOLS, APP_PAGE)
    dev.run(0.2)
    part = dev.u32(PART)
    mute = mute_with_pad(dev, 4)
    muted = mute[0] != mute[1] and dev.u32(PART) == part
    tap_key(dev, 2, 0.3)
    stopped = dev.u32(TRANSPORT)
    out.append(entry("pass_keys_part_mute_reaches_play_kept", muted and stopped == 0 and not dev.m.asserts,
                     f"mute byte {mute}, part {part} to {dev.u32(PART)}, transport after PLAY {stopped}"))
    dev.press("exit", 0.5)
    screen = dev.screen()["number"]
    record = dev.read(script_hooks.KEY_PASS, 8)
    tap_key(dev, 2, 0.3)
    again = dev.u32(TRANSPORT)
    tap_key(dev, 1, 0.3)
    out.append(entry("pass_keys_end_with_the_app", screen == 1 and record == b"\xff" * 8 and again != 0 and not dev.m.asserts,
                     f"screen {screen}, pass words {record.hex()}, transport after PLAY {again}"))
    return out


def shift_held(dev):
    """The firmware's SHIFT flag (+0x358 of the object SHIFT_OBJ returns, tools/patch/dice.py), 0 when it is up."""
    return dev.u32(dev.call(SHIFT_OBJ) + 0x358)


def take_cases(vsb, flash, programs):
    """korg.display.take() while SHIFT is held, SHIFT let go while the plugin owns the display, then korg.display.release():
    the firmware has to see SHIFT go up, and the LCD has to show the main screen again as it was before."""
    dev = boot(vsb, flash, programs, "taker")
    dev.run(0.5)
    before = dev.fb()
    dev.m.send([0, SHIFT, 1, 0, 0])
    dev.run(0.2)
    held = shift_held(dev)
    owner = dev.u32(menu_cases.apps_open_address())
    taken = dev.fb()
    dev.m.send([0, SHIFT, 0, 0, 0])
    dev.run(0.2)
    up = shift_held(dev)
    dev.run(2.0)
    back = dev.u32(menu_cases.apps_open_address())
    return [entry("take_lets_the_shift_release_reach_the_firmware", held != 0 and owner != 0 and up == 0 and not dev.m.asserts,
                  f"SHIFT flag held {held}, after the release while taken {up}, owner {owner:#x}"),
            entry("release_redraws_the_main_screen", back == 0 and taken != before and dev.fb() == before and shift_held(dev) == 0,
                  f"owner after release {back:#x}, picture shown {taken != before}, main screen back {dev.fb() == before}")]


def edit_cases(vsb, flash, built):
    out = []
    # the firmware's own knob: LEVEL of part 0 to a value, then the plugin sets the same value in another device
    knob, _ = running(vsb, flash, built, compiled({"edit": PROGRAMS["edit"].replace("LEVEL", "0")})["programs"], "edit")
    before = knob.read(pattern(knob), 0x4900)
    knob.m.send([2, 0, 0, 60, 0])
    knob.run(0.3)
    level = knob.read(pattern(knob) + PART_AT(0) + 24, 1)[0]
    by_knob = knob.read(pattern(knob), 0x4900)
    knob_changed = sorted(i for i in range(0x4900) if before[i] != by_knob[i])
    knob_screen = knob.fb()

    request = compiled({"edit": PROGRAMS["edit"].replace("LEVEL", str(level))})
    dev, _ = running(vsb, flash, built, request["programs"], "edit")
    at = pattern(dev)
    before = dev.read(at, 0x4900)
    poke(dev, dev.a(BANK) + COMMAND * 0x4000 + PART_AT(0) + 12, [1])
    dev.run(0.3)
    after = dev.read(at, 0x4900)
    changed = sorted(i for i in range(0x4900) if before[i] != after[i])
    out.append(entry("set_part_value_like_the_knob", changed == knob_changed and after[PART_AT(0) + 24] == level and level != before[PART_AT(0) + 24]
                     and not dev.m.asserts, f"level {level}, by plugin {changed}, by knob {knob_changed}"))
    out.append(entry("set_part_value_opens_the_window", dev.fb() == knob_screen, "the display as after the knob"))

    other = dev.read(at, 0x4900)
    screen = dev.fb()
    poke(dev, dev.a(BANK) + COMMAND * 0x4000 + PART_AT(0) + 12, [2])
    dev.run(0.3)
    after = dev.read(at, 0x4900)
    changed = sorted(i for i in range(0x4900) if other[i] != after[i])
    # from 0x4200 red and blue keep the last value the MIDI CC path sent, the knob as the call (set_part_value_like_the_knob)
    out.append(entry("set_part_value_clamps_another_part", after[PART_AT(5) + 36] == 0xC1 and len([i for i in changed if i < 0x4200]) == 2
                     and not dev.m.asserts,
                     f"pitch byte {after[PART_AT(5) + 36]:#x}, changed {changed}, display kept {dev.fb() == screen}"))
    poke(dev, dev.a(BANK) + COMMAND * 0x4000 + PART_AT(0) + 12, [3])
    dev.run(0.3)
    out.append(entry("set_part_value_signed_pan", dev.read(at + PART_AT(0) + 25, 1)[0] == 0xEC and not dev.m.asserts,
                     f"pan byte {dev.read(at + PART_AT(0) + 25, 1)[0]:#x}"))
    return out


def copy_cases(vsb, flash, programs, built):
    out = []
    dev, entry_at = running(vsb, flash, built, programs, "copy")
    bank = dev.a(BANK)
    source = bank + SOURCE * 0x4000
    steps = []
    for step in range(64):
        on = 1 if step % 3 else 0
        steps.append([on, 24 + step, 40 + step, step % 2, 37 + step % 24, 0 if step % 4 else 49, 0, 0])
    for step, record in enumerate(steps):
        poke(dev, source + STEP_AT(2, step), record)
    values = {1: 3, 3: 70, 4: 0xF6, 5: 5, 8: 12, 9: 90, 10: 101, 11: 0x0A, 14: 64, 15: 0xF0, 16: 20, 18: 77}
    for field, value in values.items():
        poke(dev, source + PART_AT(2) + PART_OFFSETS[field], [value])
    at = pattern(dev)
    tails = [dev.read(at + STEP_AT(TARGET, step) + 8, 4) for step in range(64)]
    poke(dev, source + PART_AT(2) + 13, [33])      # cutoff 33: the plugin copies
    dev.run(0.4)
    got = script_cases.variables(dev, entry_at, programs["copy"])
    live = dev.read(at, 0x4000)
    copied = [list(live[STEP_AT(TARGET, step):STEP_AT(TARGET, step) + 8]) for step in range(64)]
    kept = all(live[STEP_AT(TARGET, step) + 8:STEP_AT(TARGET, step) + 12] == tails[step] for step in range(64))
    out.append(entry("pattern_bytes_and_write_steps_copy_a_part", got["read"] == 768 and got["wrote"] == 64 and copied == steps and kept
                     and not dev.m.asserts, f"read {got['read']}, wrote {got['wrote']}, first bad {next((s for s in range(64) if copied[s] != steps[s]), None)}"))
    want = {**values, 2: 33}
    params = {field: live[PART_AT(TARGET) + PART_OFFSETS[field]] for field in want}
    source_now = dev.read(source + PART_AT(2), 0x40)
    want = {field: source_now[PART_OFFSETS[field]] for field in want}
    out.append(entry("set_part_value_copies_the_part_values", params == want, f"part {TARGET} {params}, source {want}"))

    ram = dev.read(at, 0x4000)
    n = dev.u32(RUNNING)
    for _ in range(3):
        dev.press(0x0E, 1.0)
        if dev.read(bank + n * 0x4000, 0x4000) == dev.read(at, 0x4000):
            break
    saved = dev.read(bank + n * 0x4000, 0x4000)
    dev.turn(1, 0.6)
    away = dev.u32(RUNNING)
    dev.turn(-1, 0.6)
    back = dev.u32(RUNNING), dev.read(pattern(dev), 0x4000)
    diff = [i for i in range(0x4000) if ram[i] != back[1][i]]
    out.append(entry("write_and_reload_keep_the_copy", saved == ram and away != n and back[0] == n and not diff and not dev.m.asserts,
                     f"saved as RAM {saved == ram}, away {away}, back {back[0]}, differs at {[hex(i) for i in diff[:8]]}"))
    return out


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    request = compiled({k: v for k, v in PROGRAMS.items() if k != "edit"})
    built = script_hooks.build(request["include"], build=identify(payload).build)
    return (keys_cases(vsb, flash, request["programs"]) + take_cases(vsb, flash, request["programs"]) + edit_cases(vsb, flash, built)
            + copy_cases(vsb, flash, request["programs"], built))


def main():
    import lifetime
    lifetime.load_gate()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
