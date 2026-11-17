"""Recording controller wiring in the complete native runtime."""
import struct
import unittest
from tools.patch import test_script_hooks as hooks


@unittest.skipUnless(hooks.UNICORN_AVAILABLE, 'Unicorn is required for runtime hooks')
class RecordingHookTests(unittest.TestCase):
    def machine(self):
        return hooks.HookTests().machine()

    def test_default_off_and_exit_bypass_never_post_or_allocate(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE
        for armed, flags in ((0xFFFFFFFF, 0xFF), (0, 32), (1, 0)):
            m.write(MENU_STATE, armed)
            m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, bytes([flags, 0xA5, 0xA5, 0xA5]))
            self.assertEqual(m.call('nr_enabled')[0], 0)
            self.assertEqual(m.call('nr_post', 1)[0], b.symbols['NR_DISABLED'])
            self.assertEqual(m.call('nr_service')[0], 0)
            self.assertEqual(m.call('nr_busy')[0], 0)
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        self.assertEqual(m.call('nr_enabled')[0], 1)
        self.assertEqual(m.call('nr_post', 1)[0], 0)
        self.assertEqual(m.call('nr_busy')[0], 1)

    def test_recording_request_keeps_idle_timer_awake(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, IDLE
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        m.write(b.symbols['OS_TICKS'], 123456)
        m.write(b.symbols['APO_TIMER'], 0)
        m.call('nr_post', 1)
        m.call('nr_frame')
        self.assertEqual(m.read(IDLE + b.symbols['IS_LAST']), 123456)
        m.call('nr_post', 0)
        m.call('nr_service')
        m.write(b.symbols['OS_TICKS'], 123999)
        m.call('nr_frame')
        self.assertEqual(m.read(IDLE + b.symbols['IS_LAST']), 123456)

    def test_sampler_features_end_with_native_recording_and_keep_existing_order(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE
        m.write(MENU_STATE + b.symbols['M_LEVEL'], 2)
        m.write(MENU_STATE + b.symbols['M_GROUP'], 4)
        m.uc.mem_map(0xC014F000, 4096)
        m.uc.mem_write(0xC014F000, b'\xff' * 4096)
        count = m.call('menu_page_count')[0]
        kinds = [m.call('menu_kind', i)[0] for i in range(count)]
        self.assertEqual(kinds[-3:], [61, 62, 64])
        self.assertEqual(kinds.count(64), 1)
        self.assertEqual(b.symbols['FLAGS2_KNOWN'] & 32, 32)

    def test_record_key_toggles_only_in_native_record_setup_and_swallows_its_release(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        m.call('nr_init')
        packet = m.input + 0x5000
        m.uc.mem_write(packet, bytes(12) + bytes([0, 0, 1, 0]) + bytes(8))
        m.write(NATIVE_RECORDING + b.symbols['NR_SELECTED'], 1)
        self.assertEqual(m.call('nr_input', packet)[0], 0)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        self.assertEqual(m.call('nr_input', packet)[0], 1)
        self.assertEqual(m.call('nr_busy')[0], 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 1)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 0)
        m.uc.mem_write(packet + 14, b'\0')
        self.assertEqual(m.call('nr_input', packet)[0], 1)
        self.assertEqual(m.call('nr_input', packet)[0], 0)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        m.uc.mem_write(packet + 14, b'\1')
        self.assertEqual(m.call('nr_input', packet)[0], 1)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 2)
        m.call('nr_service')
        self.assertEqual(m.call('nr_busy')[0], 0)
        # PLAY and transport REC outside setup retain their native behavior.
        m.uc.mem_write(packet + 13, b'\1')
        self.assertEqual(m.call('nr_input', packet)[0], 0)

    def test_source_dial_has_three_choices_without_changing_native_boolean_schema(self):
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        obj, engine = m.input + 0x6000, m.input + 0x7000
        m.write(obj + 0x24, engine)
        m.write(engine + 0x708, 0)
        m.uc.mem_map(0xC0070000, 4096)
        m.uc.mem_write(0xC0070688, struct.pack('<I', 0xE12FFF1E))
        events = []
        def notify(uc, address, size, data):
            pointer = uc.reg_read(UC_ARM_REG_R1)
            events.append((uc.reg_read(UC_ARM_REG_R0), bytes(uc.mem_read(pointer, 8))))
        m.uc.hook_add(UC_HOOK_CODE, notify, begin=0xC0070688, end=0xC0070688)
        for delta, native, record in ((1, 1, 0), (1, 1, 1), (1, 1, 1), (-1, 1, 0), (-1, 0, 0), (-1, 0, 0)):
            m.call('nr_source_hook', obj, delta & 0xFFFFFFFF)
            self.assertEqual(m.read(engine + 0x708), native)
            self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_SELECTED']), record)
        self.assertEqual([e[0] for e in events], [engine + 0x400] * 4)
        self.assertEqual([struct.unpack('<II', e[1]) for e in events], [(1, 1), (1, 1), (1, 1), (1, 0)])

    def test_capture_apps_are_unavailable_only_while_recording_is_busy(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        entry, block = m.input + 0x6000, m.input + 0x7000
        m.write(entry + b.symbols['SCRIPT_ENTRY_BLOB'], block)
        for code, requires in (([1, 33, 1, 129, 0], 0), ([33, 121, 0, 0], 0), ([33, 129, 1, 0], 1), ([1, 0, 0, 33, 129, 1, 0], 1)):
            m.uc.mem_write(block, hooks.blob(code, constants=(0x008121,), strings=('capture',)))
            self.assertEqual(m.call('nr_app_allowed', entry)[0], 1)
            m.call('nr_post', 1)
            self.assertEqual(m.call('nr_app_allowed', entry)[0], 1 - requires)
            self.assertEqual(m.call('script_audio_capture_glue', 1), (2, b.symbols['ERR_OK']))
            self.assertEqual(m.call('script_audio_capture_glue', 0), (1, b.symbols['ERR_OK']))
            m.call('nr_post', 0)
            m.call('nr_service')

    def test_status_text_uses_pcm_duration_and_visible_failure_reasons(self):
        m, b = self.machine()
        from tools.patch.script_hooks import NATIVE_RECORDING
        m.call('nr_init')
        title, value = m.input + 0x6000, m.input + 0x6040
        def text(address):
            return bytes(m.uc.mem_read(address, 32)).split(b'\0', 1)[0].decode()
        for phase, error, number, seconds, expected_title, expected_value in (
            (0, 0, 0, 0, 'Sampling Source', 'RECORD'),
            (3, 0, 0, 0, 'Opening...', 'RECORD'),
            (1, 0, 42, 3661, 'REC 01:01:01', 'REC0042'),
            (2, 0, 42, 3661, 'Saving...', 'REC0042'),
            (0, 0, 42, 3661, 'Saved 01:01:01', 'REC0042'),
            (0, 2, 42, 0, 'Card full', 'REC0042'),
            (0, 20, 42, 0, 'Capture gap', 'REC0042'),
            (0, 33, 0, 0, 'No memory', 'RECORD'),
        ):
            for name, data in (('NR_PHASE', phase), ('NR_ERROR', error), ('NR_NUMBER', number), ('NR_BYTES', seconds * 192000), ('NR_ELAPSED', 999999)):
                m.write(NATIVE_RECORDING + b.symbols[name], data)
            m.call('nr_format', title, value)
            self.assertEqual((text(title), text(value)), (expected_title, expected_value))

    def test_native_sampling_stays_blocked_until_disabled_recording_releases_ownership(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        m.call('nr_post', 1)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\0')
        packet = m.input + 0x5000
        m.uc.mem_write(packet, bytes(12) + bytes([0, 0, 1, 0]) + bytes(8))
        self.assertEqual(m.call('nr_input', packet)[0], 1)
        m.call('nr_service')
        self.assertEqual(m.call('nr_busy')[0], 0)

    def test_source_choice_stays_record_until_capture_and_file_are_released(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + b.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        m.call('nr_init')
        m.write(NATIVE_RECORDING + b.symbols['NR_SELECTED'], 1)
        m.call('nr_post', 1)
        obj, engine = m.input + 0x6000, m.input + 0x7000
        m.write(obj + 0x24, engine)
        m.write(engine + 0x708, 1)
        m.uc.mem_map(0xC0070000, 4096)
        m.uc.mem_write(0xC0070688, struct.pack('<I', 0xE12FFF1E))
        m.call('nr_source_hook', obj, 0xFFFFFFFF)
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_SELECTED']), 1)
        self.assertEqual(m.read(engine + 0x708), 1)
