"""Record every host-port write transfer (time ns, DSP address, 16-bit words) of a short sequencer run."""
import pickle, sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
payload = Path(sys.argv[1]).read_bytes()[0x100:]
out = sys.argv[2]
every = int(sys.argv[3]) if len(sys.argv) > 3 else 4
rec = []
orig = DspModel._flush
def flush(self):
    x = self._xfer
    if x and x[2]:
        rec.append((self.m.time_ns, x[0], list(x[2])))
    return orig(self)
DspModel._flush = flush
import pswitch_cases
_Dev = pswitch_cases.Dev
class Dev(_Dev):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        DspModel.attach(self.m)
pswitch_cases.Dev = Dev
box = sc.SBox(payload, None, card=False)
dsp = DspModel.attach(box.m)
print('boot transfers', len(rec), 'at', box.m.time_ns / 1e9)
for part in range(16):
    for step in range(64):
        at = sc.PART + sc.STRIDE * part + sc.STEPS + 12 * step
        on = part == 0 and step % every == 0
        box.poke(at, 1 if on else 0)
        for i, value in enumerate((60, 100, 1, 60) if on else (), 1):
            box.poke(at + i, value)
box.run(0.3)
mark = len(rec)
sc.play(box)
box.run(1.0)
pickle.dump({'rec': rec, 'play_index': mark, 'gates': dsp.gates}, open(out, 'wb'))
from collections import Counter
c = Counter()
for t, a, w in rec: c[a >> 16] += len(w)
print(len(rec), 'transfers, words per 64k page', {hex(k): v for k, v in c.items()}, 'gates', dsp.gates[:6])
