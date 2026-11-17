import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import MASTER_FX, FX_IN, DspModel
vsb = Path(sys.argv[1]).read_bytes()
box = sc.SBox(vsb[0x100:], None, dsp=True)
dsp = DspModel.attach(box.m)
box.run(0.3)
key = lambda k: (box.m.send([0, k, 1, 0, 0]), box.run(0.05), box.m.send([0, k, 0, 0, 0]), box.run(0.4))
key(0x06)
eff = dsp.effect(MASTER_FX) or {}
print('master unit', eff.get('unit'), 'params at rest', eff.get('params'))
base = 741424
for i in range(100):
    r = vsb[base + i * 524: base + (i + 1) * 524]
    if r[446] == eff.get('unit'):
        rows = [(r[18+28*k], r[19+28*k], r[20+28*k], r[22+28*k], r[24+28*k]) for k in range(10) if r[18+28*k]]
        print('rec', i, r[1:16].split(b'\0')[0], 'map (src,chain,param,low,high)', rows)
box.m.send([0, 0x22, 1, 0, 0])
for x, y in ((256, 100), (768, 300), (100, 450), (300, 512), (50, 600), (50, 800), (50, 1000), (1000, 512)):
    box.m.send([5, x >> 8, x & 0xFF, y >> 8, y & 0xFF]); box.run(0.3)
    p = (dsp.effect(MASTER_FX) or {}).get('params', {})
    print('pad', x, y, {k: v for k, v in sorted(p.items()) if k != FX_IN and eff['params'].get(k) != v})
box.m.send([0, 0x22, 0, 0, 0])
