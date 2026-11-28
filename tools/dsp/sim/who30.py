import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_SP
from plugin_api24_cases import CUTOFF_ENCODER
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
uc = box.m.uc
seen = []
om = dsp.message
def msg(w):
    if len(w) > 2 and w[1] == 0x30 and len(seen) < 3:
        sp = uc.reg_read(UC_ARM_REG_SP)
        stack = [int.from_bytes(uc.mem_read(sp + 4 * i, 4), 'little') for i in range(96)]
        seen.append((hex(uc.reg_read(UC_ARM_REG_LR)), [hex(x) for x in stack if 0xC0000000 <= x < 0xC0200000][:16], [hex(x) for x in w[1:9]]))
    return om(w)
dsp.message = msg
box.m.midi(bytes([0x90, 60, 100])); box.run(0.3)
for s in seen: print(s)
