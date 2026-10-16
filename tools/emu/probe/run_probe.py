"""Which Unicorn features run code on this system: plain run, CPU model, exits, MMIO."""
import sys
import unicorn
from unicorn import arm_const as A

NOP = b"\x00\x00\xa0\xe1"          # mov r0, r0
BASE = 0xC0000000

def make(cpu, exits, mmio):
    uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
    if cpu:
        uc.ctl_set_cpu_model(A.UC_CPU_ARM_926)
    uc.mem_map(BASE, 0x08000000, unicorn.UC_PROT_ALL)
    uc.mem_write(BASE, NOP * 0x400)
    if mmio:
        uc.mmio_map(0x01C00000, 0x400000, lambda u, o, s, d: 0, None, lambda u, o, s, v, d: None, None)
    if exits:
        uc.ctl_exits_enabled(True)
        uc.ctl_set_exits([BASE + 0x800, BASE + 0x900])
    return uc

case = sys.argv[1]
cpu, exits, mmio = ("cpu" in case), ("exits" in case), ("mmio" in case)
uc = make(cpu, exits, mmio)
print(case, "built", flush=True)
uc.emu_start(BASE, 0 if exits else BASE + 0x1000, count=100)
print(case, "ran, pc", hex(uc.reg_read(A.UC_ARM_REG_PC)), flush=True)
