"""Part 1 plays steps with notes 48, 60, 72 (sequencer), PITCH knob at three values; what the opened voices hold."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from plugin_api24_cases import KNOBS
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
for part in range(16):
    for step in range(64):
        at = sc.PART + sc.STRIDE * part + sc.STEPS + 12 * step
        on = part == 0 and step % 8 == 0
        box.poke(at, 1 if on else 0)
        for i, value in enumerate(((48, 60, 72)[step // 8 % 3], 100, 1, 60) if on else (), 1):
            box.poke(at + i, value)
for raw in (64, 0, 127, 96):
    box.m.send([2, KNOBS["pitch"], 0, raw, 0]); box.run(0.4)
    mark = len(dsp.gates)
    if raw == 64: sc.play(box)
    box.run(2.0)
    seen = []
    for t, v, p, on in dsp.gates[mark:]:
        if on: seen.append((dsp.voice(v)["note"], dsp.voice(v)["pitch"]))
    print('pitch knob', raw, sorted(set(seen)))
print(dsp.commands)
