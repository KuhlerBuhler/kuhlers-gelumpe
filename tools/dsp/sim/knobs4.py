"""Part 1: every part-region parameter write (offset, value) in 0.6 s after a knob turn plus a note, for knob values 0, 64, 127."""
import sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel, PART_STRIDE
from plugin_api24_cases import KNOBS
payload = Path(sys.argv[1]).read_bytes()[0x100:]
box = sc.SBox(payload, None)
dsp = DspModel.attach(box.m)
base = dsp.part_base
log = []
orig = dsp.set_param
dsp.set_param = lambda p, v, w=None: (log.append((p, v)), orig(p, v, w))[1]
for name in sys.argv[2].split(','):
    out = []
    for raw in (0, 64, 127):
        box.m.send([2, KNOBS[name], 0, raw, 0]); box.run(0.4)
        log.clear(); box.pad(0); box.run(0.2)
        seen = collections.OrderedDict()
        for p, v in log:
            k = p - base
            if 0 <= k < PART_STRIDE: seen[hex(k)] = hex(v)
        out.append(dict(seen))
    keys = sorted(set().union(*out), key=lambda k: int(k, 16))
    print(name, {k: [o.get(k) for o in out] for k in keys if len({o.get(k) for o in out}) > 1})
