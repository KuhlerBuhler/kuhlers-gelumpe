import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel, PART_STRIDE
from plugin_api24_cases import KNOBS
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
b = dsp.part_base
def snap():
    dsp.params = {k: v for k, v in dsp.params.items() if not b <= k < b + PART_STRIDE}
    box.m.midi(bytes([0x90, 60, 100])); box.run(0.3)
    r = {k - b: v for k, v in dsp.params.items() if b <= k < b + PART_STRIDE}
    box.m.midi(bytes([0x80, 60, 0])); box.run(0.4)
    return r
base = snap()
print("sent offsets", sorted(hex(k) for k in base))
for name in KNOBS:
    if name in ("level", "pan", "resonance", "pitch"): continue
    vals = []
    for raw in (16, 112):
        box.m.send([2, KNOBS[name], 0, raw, 0]); box.run(0.4); vals.append(snap())
    box.m.send([2, KNOBS[name], 0, 64, 0]); box.run(0.3)
    diff = {hex(k): (hex(vals[0].get(k, -1)), hex(vals[1].get(k, -1))) for k in set(vals[0]) | set(vals[1]) if vals[0].get(k) != vals[1].get(k)}
    print(name, diff)
