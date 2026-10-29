"""Build isolation and native startup contracts of the Synth runtime."""
import unittest

from tools.patch.script_hooks import build
from tools.patch.test_script_vm import contract_data, UNICORN_AVAILABLE


class SynthBuildTests(unittest.TestCase):
    def test_synth_has_its_own_start_and_screen_table(self):
        patch = build(contract_data()['include'], build='synth').patch_manifest()
        self.assertEqual(patch['builds'], ['synth'])
        sites = {int(hook['site'], 16) for hook in patch['hooks']}
        self.assertIn(0xC0028170, sites)
        self.assertTrue(sites.isdisjoint({0xC0038D34, 0xC0038D68}))
        copies = [change['copy'] for change in patch['changes'] if 'copy' in change]
        self.assertEqual(sorted(item['length'] for item in copies), [72, 148])

    def test_build_selection_does_not_retarget_the_next_sampler(self):
        include = contract_data()['include']
        sampler = build(include).patch_manifest()
        for variant in ('synth', 'stock'):
            with self.subTest(build=variant):
                build(include, build=variant)
                self.assertEqual(build(include).patch_manifest(), sampler)


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native startup tests')
class SynthStartupTests(unittest.TestCase):
    def test_only_normal_start_initializes_and_the_native_instruction_is_preserved(self):
        import unicorn
        from unicorn import arm_const as arm

        built = build(contract_data()['include'], build='synth')
        startup = ['menu_arm_load', 'migrate_start', 'blechy_boot', 'script_card_load', 'menu_recount']
        registers = [getattr(arm, f'UC_ARM_REG_R{i}') for i in range(13)] + [arm.UC_ARM_REG_SP, arm.UC_ARM_REG_CPSR]
        for name, pointer, held, mode, updating, active in [
            ('normal', 0xC0204000, 0, 0, 0, True),
            ('exit', 0xC0204000, 0x2000, 0, 0, False),
            ('panel_update', 0xC0204000, 0, 0, 1, False),
            ('special_mode', 0xC0204000, 0, 1, 0, False),
            ('no_panel', 0, 0, 0, 0, False),
            ('invalid_panel', 0xFFFFFFFF, 0, 0, 0, False),
        ]:
            with self.subTest(name=name):
                uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
                uc.ctl_set_cpu_model(arm.UC_CPU_ARM_926)
                uc.mem_map(0xC0000000, 0x800000)
                for address, data in built.sections:
                    uc.mem_write(address, data)
                uc.mem_write(0xC033E8F8, pointer.to_bytes(4, 'little'))
                if pointer not in (0, 0xFFFFFFFF):
                    uc.mem_write(pointer + 0x18, held.to_bytes(8, 'little') + bytes([mode, 0, updating]))
                for i, register in enumerate(registers[:13]):
                    uc.reg_write(register, 0x12340000 + i)
                uc.reg_write(arm.UC_ARM_REG_R4, 0xC0205000)
                uc.mem_write(0xC0205004, b'\x5A')
                uc.reg_write(arm.UC_ARM_REG_LR, 0xC002816C)
                uc.reg_write(arm.UC_ARM_REG_SP, 0xC0203000)
                uc.reg_write(arm.UC_ARM_REG_CPSR, 0xA0000053)
                expected = [uc.reg_read(register) for register in registers]
                expected[3] = 0x5A
                calls, native = [], []

                def stub(machine, address, size, label):
                    calls.append(label)
                    machine.reg_write(arm.UC_ARM_REG_PC, machine.reg_read(arm.UC_ARM_REG_LR))

                for label in startup:
                    address = built.symbols[label]
                    uc.hook_add(unicorn.UC_HOOK_CODE, stub, user_data=label, begin=address, end=address)

                def original(machine, address, size, user):
                    native.append([machine.reg_read(register) for register in registers])
                    self.assertEqual(machine.reg_read(arm.UC_ARM_REG_LR), 0xC002816C)
                    machine.emu_stop()

                uc.hook_add(unicorn.UC_HOOK_CODE, original, begin=0xC0028174, end=0xC0028174)
                uc.emu_start(built.symbols['script_card_hook'], 0, count=2000)
                self.assertEqual(calls, startup if active else [])
                self.assertEqual(native, [expected])


if __name__ == '__main__':
    unittest.main()
