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
def key(k):
    box.m.send([0, k, 1, 0, 0]); box.run(0.05); box.m.send([0, k, 0, 0, 0]); box.run(0.4)
for name, k in (("mfxSend", 0x1a), ("ampEg", 0x20), ("ifxOn", 0x21)):
    a = snap(); key(k); c = snap(); key(k); d = snap()
    print(name, {hex(o): (hex(a.get(o, -1)), hex(c.get(o, -1)), hex(d.get(o, -1))) for o in set(a) | set(c) if a.get(o) != c.get(o)}, sorted(hex(o) for o in c))
