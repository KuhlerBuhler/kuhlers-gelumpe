import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from unicorn.arm_const import UC_ARM_REG_SP
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
b = dsp.part_base; uc = box.m.uc
cur = [None]; log = []
om = dsp.message
def msg(w):
    cur[0] = w; r = om(w); cur[0] = None; return r
dsp.message = msg
osp = dsp.set_param
def sp(p, v, word=None):
    k = p - b
    if k in (0x22, 0x5F, 0x60) and cur[0] is not None and len(log) < 12:
        s = uc.reg_read(UC_ARM_REG_SP)
        st = [int.from_bytes(uc.mem_read(s + 4 * i, 4), 'little') for i in range(80)]
        log.append((hex(k), hex(v), [hex(x) for x in cur[0][1:12]], [hex(x) for x in st if 0xC0000000 <= x < 0xC0200000][:12]))
    return osp(p, v, word)
dsp.set_param = sp
box.m.midi(bytes([0x90, 60, 100])); box.run(0.3)
for l in log: print(l)
