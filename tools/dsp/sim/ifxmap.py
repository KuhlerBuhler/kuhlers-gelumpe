import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from plugin_api24_cases import KNOBS
vsb = Path(sys.argv[1]).read_bytes()
box = sc.SBox(vsb[0x100:], None, dsp=True)
dsp = DspModel.attach(box.m)
box.run(0.3)
box.m.send([1, 4, 0, 1, 0]); box.run(0.6)
e0, e1 = dsp.effect(0) or {}, dsp.effect(1) or {}
print('field0 unit', e0.get('unit'), 'field1 unit', e1.get('unit'))
base = 688624
for i in range(100):
    r = vsb[base + i * 524: base + (i + 1) * 524]
    if r[298] == e0.get('unit') and r[372] == e1.get('unit'):
        rows = [(r[18+28*k], r[19+28*k], r[20+28*k], r[22+28*k], r[24+28*k]) for k in range(10) if r[18+28*k]]
        print('rec', i, r[1:16].split(b'\0')[0], rows)
rest0, rest1 = dict(e0.get('params', {})), dict(e1.get('params', {}))
for raw in (64, 0, 0, 128, 0, 1, 2, 255):
    box.m.send([2, KNOBS["ifxEdit"], 0, raw, 0]); box.run(0.4)
    p0 = (dsp.effect(0) or {}).get('params', {}); p1 = (dsp.effect(1) or {}).get('params', {})
    print(raw, {k: round(v/256, 2) for k, v in sorted(p0.items()) if rest0.get(k) != v}, {k: round(v/256, 2) for k, v in sorted(p1.items()) if rest1.get(k) != v})
