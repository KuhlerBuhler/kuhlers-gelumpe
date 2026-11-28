import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
b = dsp.part_base
uc = box.m.uc
seen = {}
om = dsp.message
def msg(w):
    if len(w) > 4 and w[1] in (0, 0x16):
        n = w[2] + 1; st = 2 if w[1] == 0 else 3
        ps = [w[3 + st * i] for i in range(n) if 4 + st * i < len(w)]
        for p in ps:
            if p - b in (0x22, 0x23, 0x5F, 0x60) and p not in seen:
                sp = uc.reg_read(UC_ARM_REG_SP)
                stack = [int.from_bytes(uc.mem_read(sp + 4 * i, 4), 'little') for i in range(64)]
                seen[p] = (hex(uc.reg_read(UC_ARM_REG_LR)), [hex(x) for x in stack if 0xC0000000 <= x < 0xC0200000][:14], [hex(x) for x in w[1:3+st*n]])
    return om(w)
dsp.message = msg
box.m.midi(bytes([0x90, 60, 100])); box.run(0.3)
for p, v in seen.items(): print(hex(p - b), v)
