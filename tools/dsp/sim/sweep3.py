"""Part 1: LEVEL, PAN, RESONANCE knobs and the CUTOFF encoder over several values, MIDI note 60 held 0.3 s: part parameters
+0x22/+0x23/+0x5F/+0x60 (last value) and the last 0x30 message for the part's filter (+0xA)."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from plugin_api24_cases import KNOBS, CUTOFF_ENCODER
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
b = dsp.part_base
last30 = []
om = dsp.message
dsp.message = lambda w: ((last30.append(list(w[2:8])) if len(w) > 7 and w[1] == 0x30 and w[3] == b + 0xA else None), om(w))[1]
def note():
    last30.clear()
    box.m.midi(bytes([0x90, 60, 100])); box.run(0.3)
    r = [dsp.params.get(b + k) for k in (0x22, 0x23, 0x5F, 0x60)]
    box.m.midi(bytes([0x80, 60, 0])); box.run(0.4)
    return [None if x is None else hex(x) for x in r], ' '.join('%x' % x for x in last30[-1]) if last30 else None
for name in ("level", "pan", "resonance"):
    for raw in (16, 48, 80, 112, 127):
        box.m.send([2, KNOBS[name], 0, raw, 0]); box.run(0.4)
        print(name, raw, *note())
    box.m.send([2, KNOBS[name], 0, 64, 0]); box.run(0.4)
for d in (0, -20, -20, 40, 40):
    if d: box.m.send([1, CUTOFF_ENCODER, 0, d & 0xFF, 0])
    box.run(0.4)
    print('cutoff', d, *note())
