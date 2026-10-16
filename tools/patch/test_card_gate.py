"""Card gating uses a physical detect pin when the synth has not mounted FatFs."""
import struct
import unittest

import arm
import card_gate
try:
    import unicorn
    from unicorn.arm_const import UC_ARM_REG_R0
except ImportError:
    unicorn = None


@unittest.skipUnless(unicorn, 'Unicorn is required for native guard tests')
class CardGate(unittest.TestCase):
    def run_gate(self, build, detect=0, pointer=0, mounted=0):
        text = '.equ FATFS, 0x20000\n' + card_gate.source(build, 'off') + '\nmov r0, #1\nb done\noff:\nmov r0, #0\ndone:\nnop\n'
        built = arm.assemble(text, origin=0x10000)
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        for at in (0x10000, 0x20000, 0x30000, 0x01E26000):
            uc.mem_map(at, 0x1000)
        uc.mem_write(0x10000, built.bytes)
        uc.mem_write(0x20000, struct.pack('<I', pointer))
        uc.mem_write(0x30000, bytes([mounted]))
        uc.mem_write(0x01E26070, struct.pack('<I', detect))
        writes = []
        uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, lambda *args: writes.append(1))
        uc.emu_start(0x10000, built.symbols['done'])
        self.assertEqual(writes, [])
        return uc.reg_read(UC_ARM_REG_R0)

    def test_synth_detects_an_inserted_card_before_fatfs_mount(self):
        self.assertEqual(self.run_gate('synth', detect=0, pointer=0, mounted=0), 1)
        self.assertEqual(self.run_gate('synth', detect=2, pointer=0x30000, mounted=1), 0)

    def test_sampler_keeps_its_mounted_volume_rule(self):
        for build in ('stock', 'hacktribe'):
            self.assertEqual(self.run_gate(build, pointer=0), 0)
            self.assertEqual(self.run_gate(build, pointer=0x30000), 0)
            self.assertEqual(self.run_gate(build, pointer=0x30000, mounted=1), 1)
