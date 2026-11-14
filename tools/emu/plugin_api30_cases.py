"""Emulator cases of plugin API 30: korg.midi.cc, noteOn, noteOff and program send their bytes on DIN out under the MIDI SEND
FILTER, the event midiIn reports a channel message from DIN in, and korg.midi.hold keeps a message type from the firmware's
handler while the plugins still get it.

    python3 tools/emu/plugin_api30_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-11-plugin-api30-midi.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R1  # noqa: E402

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

UART1 = 0x01D0C000                              # DIN in and out (machine.py)
GLOBAL, CHANNEL_AT, FILTER_AT = 0xC033E6A0, 0x2D, 0x2E
HANDLER = 0xC003BB00                            # the firmware's handler of a received channel message (Sampler; Dev.a gives the synth's)

PROGRAMS = {
    "api30": """let ins = 0; let st = -1; let d1 = -1; let d2 = -1;
let sentCc = -1; let sentOn = -1; let sentOff = -1; let sentProgram = -1;
korg.onEvent("ready", () => {
  sentCc = korg.midi.cc(-1, 20, 64);
  sentOn = korg.midi.noteOn(3, 60, 100);
  sentOff = korg.midi.noteOff(3, 60);
  sentProgram = korg.midi.program(15, 5);
});
korg.onEvent("midiIn", (s, a, b) => { ins = ins + 1; st = s; d1 = a; d2 = b; });""",
    "holder": """let ins = 0; let st = -1;
korg.onEvent("ready", () => { korg.midi.hold(3, 1); });
korg.onEvent("midiIn", (s, a, b) => { ins = ins + 1; st = s; });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api30:{name}", "ok": bool(ok), "detail": str(detail)}


def hexes(data):
    return " ".join(f"{b:02x}" for b in data)


class World:
    def __init__(self, vsb, flash, name):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"][name]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(1.0)
        self.sym = self.built.symbols
        self.handled = []
        at = self.dev.a(HANDLER)
        self.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda uc, a, s, d: self.handled.append(uc.reg_read(UC_ARM_REG_R1) & 0xFF),
                               begin=at, end=at)
        self.dev.m.uc.ctl_flush_tb()
        self.mark = len(self.tx())
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], [name])[name]
        self.dev.run(0.5)

    def tx(self):
        return self.dev.m.uart[UART1]["tx"]

    def sent(self):
        """The bytes on DIN out since the last call, without real time bytes (clock, active sensing)."""
        data, self.mark = bytes(self.tx()[self.mark:]), len(self.tx())
        return bytes(b for b in data if b < 0xF8)

    def vars(self):
        return script_cases.variables(self.dev, self.at, self.program)

    def global_byte(self, at):
        return self.dev.m.uc.mem_read(self.dev.u32(GLOBAL) + at, 1)[0]

    def set_filter(self, value):
        self.dev.m.uc.mem_write(self.dev.u32(GLOBAL) + FILTER_AT, bytes([value]))

    def receive(self, message):
        self.handled.clear()
        self.dev.m.midi(list(message))
        self.dev.run(0.3)


def send_cases(w):
    """The calls of the ready handler: CC on the global channel, note on and off on channel 4, program on channel 16."""
    out = w.sent()
    v = w.vars()
    channel = w.global_byte(CHANNEL_AT)
    want = bytes([0xB0 | channel, 20, 64, 0x93, 60, 100, 0x83, 60, 0x40, 0xCF, 5])
    returns = (v["sentCc"], v["sentOn"], v["sentOff"], v["sentProgram"])
    return [entry("sends_byte_for_byte", out == want and returns == (1, 1, 1, 1) and not w.dev.m.asserts,
                  f"build {w.build}: DIN out {hexes(out)}, want {hexes(want)} (global channel {channel}), returns {returns}")]


def filter_cases(w):
    """MIDI SEND FILTER 0, 1, 2: CC and notes go out only with 0, a program change also with 1, as the firmware's own."""
    seen, ok = [], True
    for value in (0, 1, 2):
        w.set_filter(value)
        cc = w.dev.call(w.sym["script_midi_cc_glue"], 2, 7, 99)
        note = w.dev.call(w.sym["script_midi_note_on_glue"], 2, 64, 1)
        program = w.dev.call(w.sym["script_midi_program_glue"], 2, 9)
        w.dev.run(0.05)
        out = w.sent()
        want = (bytes([0xB2, 7, 99, 0x92, 64, 1]) if value == 0 else b"") + (bytes([0xC2, 9]) if value < 2 else b"")
        returns = (cc, note, program)
        ok = ok and out == want and returns == ((1, 1, 1) if value == 0 else (0, 0, 1) if value == 1 else (0, 0, 0))
        seen.append((value, returns, hexes(out)))
    w.set_filter(0)
    return [entry("send_filter_like_the_firmware", ok and not w.dev.m.asserts, f"build {w.build}: (filter, returns, DIN out) {seen}")]


def receive_cases(w):
    """A CC and a note from DIN in: one midiIn each with the three bytes, and the firmware's handler gets them as before."""
    seen, ok = [], True
    for message in ([0xB0, 0x07, 0x41], [0x95, 0x30, 0x22]):
        before = w.vars()["ins"]
        w.receive(message)
        v = w.vars()
        got = (v["ins"] - before, v["st"], v["d1"], v["d2"])
        ok = ok and got == (1, *message) and message[0] in w.handled
        seen.append((hexes(message), got, w.handled[:4]))
    return [entry("midi_in_reports_and_passes", ok and not w.dev.m.asserts, f"build {w.build}: (message, (events, status, data1, data2), handler saw) {seen}")]


def hold_cases(vsb, flash):
    """A plugin holds CCs (type 3): a CC reaches the plugin and not the firmware's handler, a note reaches both."""
    w = World(vsb, flash, "holder")
    w.receive([0xB0, 0x07, 0x41])
    cc = (w.vars()["ins"], list(w.handled))
    w.receive([0x90, 0x3C, 0x40])
    note = (w.vars()["ins"], w.vars()["st"], list(w.handled))
    ok = cc[0] == 1 and 0xB0 not in cc[1] and note[0] == 2 and note[1] == 0x90 and 0x90 in note[2]
    return [entry("hold_keeps_a_type_from_the_firmware", ok and not w.dev.m.asserts,
                  f"build {w.build}: after B0 07 41 (events, handler saw) {cc}, after 90 3C 40 {note}")]


def cases(vsb, flash=None):
    w = World(vsb, flash, "api30")
    out = send_cases(w)
    out += filter_cases(w)
    out += receive_cases(w)
    out += hold_cases(vsb, flash)
    return out


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
