import sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import plugin_api23_cases as p
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0
mapper = int(sys.argv[2], 16)
w = p.World(Path(sys.argv[1]).read_bytes())
uc = w.dev.m.uc
seen = collections.Counter()
uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: seen.update([uc.reg_read(UC_ARM_REG_R0)]), begin=mapper, end=mapper)
uc.ctl_flush_tb()
def note():
    seen.clear(); w.dev.m.midi(bytes([0x90, 60, 100])); w.dev.run(0.2); w.dev.m.midi(bytes([0x80, 60, 0])); w.dev.run(0.05)
    return dict(seen)
print('start', w.value(0, 'filterType'), note())
for t in (0, 2, 5, 6, 8, 15):
    w.set_part(0, 'filterType', t)
    print('set', t, 'byte', w.value(0, 'filterType'), 'mapper', note())
