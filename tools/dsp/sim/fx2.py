import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
raw = []
ofb = dsp.fifo_buffer
dsp.fifo_buffer = lambda ws: (raw.append([w for w in ws]), ofb(ws))[1]
box.run(0.3)
r0 = len(raw)
box.m.send([1, 4, 0, 1, 0]); box.run(0.4)
for ws in raw[r0:]:
    print(' '.join('%x:%02x:%02x:%04x' % (w >> 28, w >> 22 & 63, w >> 16 & 63, w & 0xffff) for w in ws if w >> 22 & 63 != 62) or '-')
