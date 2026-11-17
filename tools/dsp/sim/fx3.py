"""Every staging go (field 0x28 code 0x39) and every slot command (0x30..0x32) from boot, then per action."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from plugin_api24_cases import KNOBS
dsp = None
class Box(sc.SBox):
    pass
import machine as M
orig = M.Machine.__init__
def init(self, *a, **k):
    orig(self, *a, **k)
    global dsp; dsp = DspModel.attach(self)
M.Machine.__init__ = init
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
pos = 0
def show(name):
    global pos
    st = {}
    out = []
    for t, c, k, v in dsp.fifo[pos:]:
        if c == 0x28:
            if k == 0x38: st['type'] = v
            if k == 0x39: out.append('load type 0x%x -> field %d' % (st.get('type', -1), v))
        elif k >= 0x30: out.append('field %d cmd 0x%x %x' % (c, k, v))
        elif c < 0x28: out.append('field %d p%d=%x' % (c, k, v))
    pos = len(dsp.fifo)
    print('==', name); [print('  ', o) for o in out[34:]]
msgs=[]
def hookmsg():
    om=dsp.message
    dsp.message=lambda w:(msgs.append(list(w[1:12])),om(w))[1]
def key(k):
    box.m.send([0, k, 1, 0, 0]); box.run(0.05); box.m.send([0, k, 0, 0, 0]); box.run(0.4)
show('boot')
hookmsg()
n0=len(msgs); key(0x21); show('ifx on'); print([[hex(x) for x in m] for m in msgs[n0:] if m[0] not in (1,0x31)])
box.m.send([1, 4, 0, 1, 0]); box.run(0.4); show('ifx type +1')
key(0x21); show('ifx on')
key(0x0f); show('part >')
box.m.send([1, 4, 0, 1, 0]); box.run(0.4); show('part2 ifx type +1')
box.m.send([2, KNOBS["ifxEdit"], 0, 200, 0]); box.run(0.4); show('part2 ifx edit')
