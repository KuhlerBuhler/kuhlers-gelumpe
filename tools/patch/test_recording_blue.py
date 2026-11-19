"""Blue recording input, task handoff and mono display over synthetic RAM."""
import unittest
from functools import lru_cache
from tools.patch.test_script_vm import BareMachine, contract_data, UNICORN_AVAILABLE
from tools.patch.card_gate import SD_INPUT


@lru_cache(None)
def runtime():
    from tools.patch.script_hooks import build
    return build(contract_data()['include'], build='synth')


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for recording UI tests')
class BlueRecordingTests(unittest.TestCase):
    def machine(self):
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        b = runtime()
        m = BareMachine(b.vm)
        for at, data in b.sections[len(b.vm.sections):]:
            m.uc.mem_write(at, data)
        m.symbols.update(b.symbols)
        m.uc.mem_write(MENU_STATE, bytes(512))
        m.uc.mem_write(NATIVE_RECORDING, b'\xff' * 72)
        m.write(MENU_STATE + b.symbols['M_ON'], 1)
        m.uc.mem_write(MENU_STATE - 0x15, bytes([32]))
        m.uc.mem_map(b.symbols['PANEL'] & ~4095, 4096)
        m.write(b.symbols['PANEL'], m.input + 4096)
        m.uc.mem_map(SD_INPUT & ~4095, 4096)    # 0: a card is in, recording may start
        return m, b

    def packet(self, m, key=0, pressed=1):
        m.uc.mem_write(m.input, bytes(12) + bytes([key, 0, pressed, 0]))
        return m.call('nr_input', m.input)[0]

    def test_shift_record_posts_view_without_starting_or_calling_ui_from_input(self):
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m, b = self.machine()
        m.uc.mem_write(MENU_STATE + b.symbols['KP_SHIFT'], bytes([1]))
        self.assertEqual(self.packet(m), 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_VIEW_REQUEST']), 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 0)
        self.assertEqual(self.packet(m, pressed=0), 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_HELD']), 0)

    def test_plain_record_needs_view_and_play_never_posts_a_stop(self):
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m, b = self.machine()
        self.assertEqual(self.packet(m), 0)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        self.assertEqual(self.packet(m), 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_VIEW_REQUEST']), 2)
        self.packet(m, pressed=0)
        self.assertEqual(self.packet(m, key=1), 0)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_VIEW_REQUEST']), 2)
        self.assertEqual(self.packet(m), 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 0)

    def test_feature_off_passes_shift_record_to_the_firmware(self):
        from tools.patch.script_hooks import MENU_STATE
        m, b = self.machine()
        m.uc.mem_write(MENU_STATE - 0x15, bytes([0]))
        m.uc.mem_write(MENU_STATE + b.symbols['KP_SHIFT'], bytes([1]))
        self.assertEqual(self.packet(m), 0)

    def test_mono_duration_and_recording_page(self):
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m, b = self.machine()
        m.call('nr_init')
        for field, value in [('NR_PHASE', 1), ('NR_BYTES', 48000 * 2 * 61), ('NR_NUMBER', 42)]:
            m.write(NATIVE_RECORDING + b.symbols[field], value)
        m.write(MENU_STATE + b.symbols['M_LEVEL'], b.symbols['M_LEVEL_RECORD'])
        self.assertEqual(m.call('menu_kind', 0)[0], 65)
        self.assertEqual(m.call('menu_page_count')[0], 1)
        m.call('menu_texts', 0)
        read = lambda name: bytes(m.uc.mem_read(MENU_STATE + b.symbols[name], 32)).split(b'\0')[0]
        self.assertEqual(read('M_TITLE'), b'REC 00:01:01')
        self.assertEqual(read('M_VALUE'), b'REC0042')
        self.assertEqual(b.symbols['RR_CHANNELS'], 1)
        self.assertEqual(b.symbols['NR_SUPPORTED'], 1)

    def test_ui_frame_opens_view_and_clears_setup_when_play_leaves_it(self):
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_PC, UC_ARM_REG_LR
        m, b = self.machine()
        page = b.symbols['SCREEN_MANAGER'] & ~4095
        if page != b.symbols['PANEL'] & ~4095:
            m.uc.mem_map(page, 4096)
        manager = m.input + 8192
        m.write(b.symbols['SCREEN_MANAGER'], manager)
        m.write(manager + 0x20, m.input + 12288)
        switch = b.symbols['SWITCH_SCREEN']
        m.uc.mem_map(switch & ~4095, 4096)
        m.uc.mem_write(switch, bytes.fromhex('1eff2fe1'))
        calls = []
        def native(uc, at, size, data):
            if at == switch:
                calls.append(('screen', uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)))
                m.write(manager + 0x2C, uc.reg_read(UC_ARM_REG_R0))
            else:
                calls.append(('show', uc.reg_read(UC_ARM_REG_R0)))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        for at in (switch, b.symbols['menu_show']):
            m.uc.hook_add(UC_HOOK_CODE, native, begin=at, end=at)
        m.uc.mem_write(MENU_STATE + b.symbols['KP_SHIFT'], bytes([1]))
        self.packet(m)
        self.assertEqual(calls, [])
        m.call('nr_view_frame')
        self.assertEqual(calls, [('screen', b.symbols['MENU_SCREEN'], 0), ('show', m.input + 12288)])
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_SETUP']), 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_VIEW_REQUEST']), 0)
        self.assertEqual(m.read(MENU_STATE + b.symbols['M_LEVEL']), b.symbols['M_LEVEL_RECORD'])
        m.uc.mem_write(MENU_STATE + b.symbols['KP_SHIFT'], bytes([0]))
        self.packet(m, pressed=0)
        self.packet(m)
        m.call('nr_view_frame')
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 1)
        self.packet(m, pressed=0)
        self.packet(m)
        m.call('nr_view_frame')
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 2)
        m.write(NATIVE_RECORDING + b.symbols['NR_REQUEST'], 0)
        self.packet(m, pressed=0)
        self.packet(m)
        m.write(manager + 0x2C, 1)
        m.call('nr_view_frame')
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 0)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_SETUP']), 0)
