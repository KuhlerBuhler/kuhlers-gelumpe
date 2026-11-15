import sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import plugin_api23_cases as p
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP
disp = int(sys.argv[2], 16)
w = p.World(Path(sys.argv[1]).read_bytes())
uc = w.dev.m.uc
seen = collections.Counter()
def h(uc, a, s, u):
    sp = uc.reg_read(UC_ARM_REG_SP)
    seen[(uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2), uc.reg_read(UC_ARM_REG_R3), int.from_bytes(uc.mem_read(sp, 2), 'little'), uc.mem_read(sp + 4, 1)[0])] += 1
uc.hook_add(UC_HOOK_CODE, h, begin=disp, end=disp)
uc.ctl_flush_tb()
def note():
    seen.clear(); w.dev.m.midi(bytes([0x90, 60, 100])); w.dev.run(0.15); w.dev.m.midi(bytes([0x80, 60, 0])); w.dev.run(0.05)
    return sorted(seen.items(), key=lambda kv: -kv[1])[:4]
for n in ('cutoff', 'resonance', 'egInt', 'modDepth', 'filterType'):
    print(n, w.value(0, n))
print('start', note())

for c, r in ((0, 0), (1, 0), (64, 0), (100, 50)):
    w.set_part(0, 'cutoff', c); w.set_part(0, 'resonance', r)
    print(c, r, [(w.read(0, 'egInt'))], note())
