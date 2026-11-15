import sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0
mapper, fns = int(sys.argv[2], 16), [int(x, 16) for x in sys.argv[3].split(',')]
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
uc = box.m.uc
cnt = collections.Counter()
def h(uc, a, s, u):
    cnt[(hex(a), uc.reg_read(UC_ARM_REG_R0) if a == mapper else None)] += 1
for a in [mapper] + fns:
    uc.hook_add(UC_HOOK_CODE, h, begin=a, end=a)
try: uc.ctl_flush_tb()
except Exception as e: print("noflush", e)
box.m.midi(bytes([0x90, 60, 100])); box.run(0.3)
print(dict(cnt))
