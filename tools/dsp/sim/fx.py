"""FIFO entries and mailbox commands for IFX TYPE, IFX EDIT, IFX ON, MASTER FX touchpad."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
from collections import Counter
import shortcut_cases as sc
from dsp_model import DspModel
from plugin_api24_cases import KNOBS
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
msgs = []
om = dsp.message
dsp.message = lambda w: (msgs.append(list(w[1:10])), om(w))[1]
def step(name, fn, t=0.4):
    f0, m0 = len(dsp.fifo), len(msgs)
    fn(); box.run(t)
    fe = dsp.fifo[f0:]
    by = Counter((c, k) for _, c, k, _ in fe)
    last = {}
    for _, c, k, v in fe: last[(c, k)] = v
    print("==", name, len(fe), "fifo", Counter(m[0] for m in msgs[m0:]).most_common(8))
    for (c, k), n in sorted(by.items()):
        print("   ch %d code 0x%02x n %d last 0x%04x" % (c, k, n, last[(c, k)]))
def key(k):
    box.m.send([0, k, 1, 0, 0]); box.run(0.05); box.m.send([0, k, 0, 0, 0])
step("idle", lambda: None)
step("ifx type +1", lambda: box.m.send([1, 4, 0, 1, 0]))
step("ifx type +1", lambda: box.m.send([1, 4, 0, 1, 0]))
step("ifx edit 200", lambda: box.m.send([2, KNOBS["ifxEdit"], 0, 200, 0]))
step("ifx edit 40", lambda: box.m.send([2, KNOBS["ifxEdit"], 0, 40, 0]))
step("ifx on", lambda: key(0x21))
step("ifx on", lambda: key(0x21))
step("master fx", lambda: key(0x06))
step("touch 800,200", lambda: (box.m.send([0, 0x22, 1, 0, 0]), box.m.send([5, 3, 0x20, 0, 200])))
step("move 200,800", lambda: box.m.send([5, 0, 200, 3, 0x20]))
step("release", lambda: box.m.send([0, 0x22, 0, 0, 0]))
