"""Emulator cases of plugin API 41: korg.audio.capture source 25, the Master, on a capture of its own or, while the native
recording runs, on the recording's capture; and the read-only leaves korg.record.running, korg.record.seconds and
korg.record.gaps. The firmware, the runtime and the plugin are real; the DSP side of the capture is synthetic, as in
plugin_api31_spectrum_cases.py, and the recording is set in its public fields (recording_runtime.py PUBLIC_FIELDS).

    python3 tools/emu/plugin_api41_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "patch"))
sys.path.insert(0, str(Path(__file__).parent))

import unicorn  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0  # noqa: E402

from tools.patch import recording_dsp, recording_runtime, script_hooks  # noqa: E402
import plugin_api31_spectrum_cases as spectrum  # noqa: E402
from machine import load_flash  # noqa: E402

WRITE_RAW = 0xC00146B4          # the DSP host write the recording reader uses (recording_reader.py RR_FW_WRITE_RAW)
INPUT = 0xFF802878              # the source BEGIN(0) points the capture at
MASTER = 0xFF802888             # script_audio_service.s AU_MASTER_WORD
FIELDS = recording_runtime.PUBLIC_FIELDS
NR_SETTING = 72                 # script_menu.s: NATIVE RECORDING ON

PROGRAMS = {
    "master": """const s = new Array(32); let st = -9; let ss = -9; let top = -1; let at = -1; let rr = -9; let rs = -9; let rg = -9;
korg.onEvent("frame", () => {
  st = korg.audio.capture(25);
  ss = korg.audio.spectrum(s, 32, 0);
  if (ss == 0) { top = -1; for (let i = 0; i < 32; i++) { if (s[i] > top) { top = s[i]; at = i; } } }
  rr = korg.record.running; rs = korg.record.seconds; rg = korg.record.gaps;
});""",
    "part": """let st = -9;
korg.onEvent("frame", () => { st = korg.audio.capture(3); });""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    spectrum.edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api41:{name}", "ok": bool(ok), "detail": str(detail)}


class World(spectrum.World):
    """The spectrum world with this module's programs, BEGIN(0) on the input and the host write of the source word."""
    def __init__(self, vsb, flash, name):
        kept, spectrum.PROGRAMS = spectrum.PROGRAMS, PROGRAMS   # World compiles the module's PROGRAMS
        try:
            super().__init__(vsb, flash, name)
        finally:
            spectrum.PROGRAMS = kept
        if self.build != "synth":
            self.dev.m.uc.hook_add(unicorn.UC_HOOK_CODE, self.dsp, begin=WRITE_RAW, end=WRITE_RAW)
            self.dev.m.uc.ctl_flush_tb()

    def nr(self, field, value=None):
        at = self.dev.a(script_hooks.NATIVE_RECORDING) + FIELDS[field]
        if value is not None:
            self.dev.m.uc.mem_write(at, struct.pack("<I", value))
        return self.dev.u32(at)

    def record(self, seconds, gaps=0, capture=True):
        """A running take as the recording keeps it, with the recording's capture on its tap (capture=False: the take has
        begun, its reader not yet)."""
        base = self.dev.a(script_hooks.NATIVE_RECORDING)
        self.dev.m.uc.mem_write(base + NR_SETTING, b"\x01")
        channels = 1 if self.build == "synth" else 2
        self.nr("BYTES", seconds * 48000 * 2 * channels)
        self.nr("GAPS", gaps)
        self.nr("PHASE", 1)
        if capture:
            self.capture()

    def capture(self):
        self.state[0], self.state[2], self.state[3], self.start = 1, spectrum.RING, recording_dsp.CAPTURE, self.ticks()

    def dsp(self, uc, at, size, data):
        args = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        if at == WRITE_RAW:
            target, source, count = args[1], args[2], args[3]
            off = target - spectrum.DSP_STATE
            if 0 <= off < 44 and off % 4 == 0:   # the firmware's other host writes go on to the real function
                self.events.append(("write", target))
                words = bytes(uc.mem_read(source, count * 2))
                for i in range(0, len(words) - 3, 4):
                    self.state[off // 4 + i // 4] = struct.unpack_from("<I", words, i)[0]
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            return
        if at == spectrum.BEGIN and args[0] == 0:
            self.state[0], self.state[2], self.state[3], self.start = 1, spectrum.RING, INPUT, self.ticks()
            self.events.append(("begin", 0))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            return
        super().dsp(uc, at, size, data)


def cases(vsb, flash=None):
    w = World(vsb, flash, "master")
    if w.build == "synth":
        w.record(3)
        w.dev.run(1.0)
        v = w.leaves()
        return [entry("synth_has_no_master_capture", v["st"] == 6 and v["ss"] == 6 and not w.dev.m.asserts,
                      f"build {w.build}: capture, spectrum {v['st'], v['ss']}"),
                entry("record_leaves_on_the_synth", (v["rr"], v["rs"], v["rg"]) == (1, 3, 0),
                      f"build {w.build}: running, seconds, gaps {v['rr'], v['rs'], v['rg']}")]
    out = []
    w.dev.run(0.5)
    idle = w.leaves()
    w.dev.run(1.0)
    v = w.leaves()
    want = spectrum.column(1000)
    writes = [e for e in w.events if e[0] == "write"]
    ok = (v["st"], v["ss"]) == (0, 0) and abs(v["at"] - want) <= 1 and 84 <= v["top"] <= 96
    out.append(entry("master_opens_its_own_capture", ok and ("begin", 0) in w.events and w.state[3] == MASTER and writes
                     and not w.dev.m.asserts,
                     f"build {w.build}: status {v['st'], v['ss']}, loudest slot {v['at']} (want {want}) at {v['top']} dB, "
                     f"source {w.state[3]:#x}, events {w.events}"))
    out.append(entry("record_leaves_idle", (idle["rr"], idle["rs"], idle["rg"]) == (0, 0, 0),
                     f"build {w.build}: running, seconds, gaps {idle['rr'], idle['rs'], idle['rg']}"))

    mark = len(w.events)
    w.record(2, capture=False)
    w.dev.run(0.2)
    closed = w.events[mark:]
    waiting = w.leaves()["st"]
    w.capture()
    w.dev.run(1.0)
    v = w.leaves()
    out.append(entry("recording_takes_over_the_master", closed == [("end",)] and waiting == 3 and len(w.events) == mark + 1
                     and (v["st"], v["ss"]) == (0, 0) and abs(v["at"] - want) <= 1 and not w.dev.m.asserts,
                     f"build {w.build}: own capture calls when the take began {closed} (want one end), status then {waiting} "
                     f"(want 3 wait), on the recording's capture {v['st'], v['ss']}, loudest slot {v['at']}"))

    r = World(vsb, flash, "master")
    r.record(3, gaps=1)
    r.dev.run(1.5)
    v = r.leaves()
    ok = (v["st"], v["ss"]) == (0, 0) and abs(v["at"] - want) <= 1 and 84 <= v["top"] <= 96
    out.append(entry("master_shares_the_recording", ok and not r.events and r.state[3] == recording_dsp.CAPTURE and not r.dev.m.asserts,
                     f"build {r.build}: status {v['st'], v['ss']}, loudest slot {v['at']} at {v['top']} dB, "
                     f"capture calls {r.events} (want none), source {r.state[3]:#x}"))
    out.append(entry("record_leaves_while_recording", (v["rr"], v["rs"], v["rg"]) == (1, 3, 1),
                     f"build {r.build}: running, seconds, gaps {v['rr'], v['rs'], v['rg']}"))

    p = World(vsb, flash, "part")
    p.record(1)
    p.dev.run(0.5)
    st = p.leaves()["st"]
    out.append(entry("part_source_busy_while_recording", st == 2 and not p.events and not p.dev.m.asserts,
                     f"build {p.build}: capture(3) {st} (want 2 busy), capture calls {p.events} (want none)"))
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
