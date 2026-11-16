"""Emulator cases of plugin API 31: korg.audio.capture, korg.audio.spectrum and korg.audio.wave on the capture service from Spettro
by Luigi (GitHub reflectiveboi, PR #429). The firmware, the runtime and the plugin are real; the DSP side of the native capture is
synthetic, as in Spettro's own case: a sine of known amplitude in the ring the capture reads.

    python3 tools/emu/plugin_api31_spectrum_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]

The measurements are in docs/messungen/2026-11-12-plugin-api31-spektrum.md.
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0  # noqa: E402

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

READ, BEGIN, END = 0xC00141F8, 0xC0014368, 0xC00143E4   # the native capture (Sampler builds only, docs/messungen/2026-11-07-spettro.md)
DSP_STATE, RING, RING_BYTES = 0xFF9031D0, 0x01C722A0, 19200
OS_TICKS = 0xC06A292C
RATE = 48000

PROGRAMS = {
    "api31s": """const s = new Array(32); const w = new Array(64); let source = 1; let st = -9; let ss = -9; let sw = -9;
let top = -1; let at = -1; let wmax = -999; let wmin = 999;
korg.onEvent("frame", () => {
  st = korg.audio.capture(source);
  ss = korg.audio.spectrum(s, 32, 0);
  sw = korg.audio.wave(w);
  if (ss == 0) { top = -1; for (let i = 0; i < 32; i++) { if (s[i] > top) { top = s[i]; at = i; } } }
  if (sw == 0) { wmax = -999; wmin = 999; for (let i = 0; i < 64; i++) { if (w[i] > wmax) wmax = w[i]; if (w[i] < wmin) wmin = w[i]; } }
});""",
    "quitter": """let st = -9; let n = 0;
korg.onEvent("frame", () => { n = n + 1; if (n < 50) st = korg.audio.capture(3); });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api31_spectrum:{name}", "ok": bool(ok), "detail": str(detail)}


class World:
    def __init__(self, vsb, flash, name, hz=1000, amplitude=16384):
        self.payload = vsb[0x100:]
        menu_cases.for_build(self.payload)
        self.build = identify(self.payload).build
        self.request = edit.compiled(PROGRAMS)
        self.program = self.request["programs"][name]
        self.built = script_hooks.build(self.request["include"], build=self.build)
        self.dev = menu_cases.boot(self.payload, flash, files=menu_cases.CARD_FOLDER, seconds=2.0)
        self.dev.run(1.0)
        self.events, self.state, self.start = [], [0, RING_BYTES, RING, 0] + [0] * 7, 0
        self.ring = bytearray(RING_BYTES)
        self.tone(hz, amplitude)
        if self.build != "synth":
            for at in (READ, BEGIN, END):
                self.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, self.dsp, begin=at, end=at)
            self.dev.m.uc.ctl_flush_tb()
        self.at = script_cases.install(self.dev, self.built, self.request["programs"], [name])[name]

    def tone(self, hz, amplitude):
        self.wave = [round(amplitude * math.sin(2 * math.pi * hz * i / RATE)) for i in range(RATE)]

    def ticks(self):
        return self.dev.u32(OS_TICKS)

    def dsp(self, uc, at, size, data):
        """The native capture's DSP side: BEGIN opens the ring at the source's place, READ copies the state or ring words the
        clock has filled with the tone (48 frames per tick), END closes it."""
        args = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        if at == READ:
            src, dest, count, width = args
            if src == DSP_STATE:
                pos = ((self.ticks() - self.start) & 0xFFFFFFFF) * 48
                self.state[2] = RING + pos % 4800 * 4
                for frame in range(max(0, pos - 4800), pos):
                    v = self.wave[frame % RATE]
                    off = frame % 4800 * 4
                    self.ring[off:off + 4] = struct.pack("<hh", v, v)
                payload = struct.pack("<11I", *self.state)
            else:
                off = src - RING
                payload = self.ring[off:off + count * 2]
            uc.mem_write(dest, bytes(payload))
        elif at == BEGIN:
            selector = args[0]
            self.state[0], self.state[2], self.start = 1, RING, self.ticks()
            self.state[3] = 0xFF90197C + (selector - 1) * 0x118 if selector <= 16 else 0xFF901A98 + (selector - 17) * 0x230
            self.events.append(("begin", selector))
        elif at == END:
            self.state[0] = 0
            self.events.append(("end",))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def leaves(self):
        return script_cases.variables(self.dev, self.at, self.program)

    def service(self):
        at = self.dev.a(script_hooks.AUDIO_SERVICE)
        return [self.dev.m.u32(at + 4 * i) for i in range(4)]


def column(hz, bins=32):
    """The slot of korg.audio.spectrum(array, bins, 0) that holds a tone: 128 log columns from 20 Hz to 20 kHz, bins of them per slot."""
    c = math.floor(128 * math.log(hz / 20) / math.log(1000))
    return c * bins >> 7


def cases(vsb, flash=None):
    w = World(vsb, flash, "api31s")
    if w.build == "synth":
        w.dev.run(1.0)
        v = w.leaves()
        return [entry("synth_has_no_capture", (v["st"], v["ss"], v["sw"]) == (6, 6, 6) and not w.dev.m.asserts,
                      f"build {w.build}: capture, spectrum, wave {v['st'], v['ss'], v['sw']}")]
    out = []
    w.dev.run(1.5)
    v = w.leaves()
    want = column(1000)
    ok = (v["st"], v["ss"], v["sw"]) == (0, 0, 0) and abs(v["at"] - want) <= 1 and 84 <= v["top"] <= 96
    out.append(entry("spectrum_finds_a_sine", ok and ("begin", 1) in w.events and not w.dev.m.asserts,
                     f"build {w.build}: status {v['st'], v['ss'], v['sw']}, loudest slot {v['at']} (want {want}) at {v['top']} dB "
                     f"(-6 dB sine is 90), events {w.events}, service {[hex(x) for x in w.service()]}"))
    out.append(entry("wave_shows_the_sine", 56 <= v["wmax"] <= 64 and -64 <= v["wmin"] <= -56,
                     f"build {w.build}: wave max {v['wmax']}, min {v['wmin']} (16384 is 64 in the top 8 bits)"))
    w.tone(100, 4096)
    w.dev.run(1.0)
    v = w.leaves()
    want = column(100)
    ok = v["ss"] == 0 and abs(v["at"] - want) <= 1 and 66 <= v["top"] <= 82
    out.append(entry("spectrum_follows_a_quieter_bass_tone", ok,
                     f"build {w.build}: loudest slot {v['at']} (want {want}) at {v['top']} dB (-18 dB sine is 78)"))
    q = World(vsb, flash, "quitter")
    q.dev.run(1.0)
    first = q.leaves()["st"]
    q.dev.run(3.5)
    opened = [e for e in q.events if e[0] == "begin"]
    out.append(entry("lease_runs_out_and_closes_the_capture",
                     opened == [("begin", 3)] and q.events[-1] == ("end",) and q.service()[1] in (0xFFFFFFFF,) and not q.dev.m.asserts,
                     f"build {q.build}: status while asked {first}, events {q.events}, service {[hex(x) for x in q.service()]}"))
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
