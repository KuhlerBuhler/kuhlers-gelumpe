import sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from plugin_api24_cases import KNOBS
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
log = []
om = dsp.message
dsp.message = lambda w: (log.append(list(w[1:8])), om(w))[1]
for raw in (16, 127):
    box.m.send([2, KNOBS["resonance"], 0, raw, 0]); box.run(0.4)
    log.clear(); box.m.midi(bytes([0x90, 60, 100])); box.run(0.3); box.m.midi(bytes([0x80, 60, 0])); box.run(0.3)
    c = collections.Counter((w[0], w[2] if w[0] in (0x30, 0x2F) else w[1]) for w in log)
    print(raw, sorted((hex(a), hex(b), n) for (a, b), n in c.items() if a not in (0x31,))[:40])
    print([' '.join('%x' % x for x in w) for w in log if w[0] in (0x30, 0x2F, 0x33, 0x34, 0x35, 0x39)][-6:])
