"""Recording controller wiring in the complete native runtime."""
import struct
import unittest
from tools.patch import test_script_hooks as hooks
from tools.patch.card_gate import SD_INPUT


@unittest.skipUnless(hooks.UNICORN_AVAILABLE, 'Unicorn is required for runtime hooks')
class RecordingHookTests(unittest.TestCase):
    def machine(self):
        m = hooks.HookTests().machine()
        m[0].write(SD_INPUT, 0)    # a card is in: recording may start
        return m

    def test_default_off_and_exit_bypass_never_post_or_allocate(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        for armed, setting in ((0xFFFFFFFF, 0xFF), (0, 1), (1, 0), (1, 0xFF)):
            m.write(MENU_STATE, armed)
            m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], bytes([setting]))
            self.assertEqual(m.call('nr_enabled')[0], 0)
            self.assertEqual(m.call('nr_post', 1)[0], b.symbols['NR_DISABLED'])
            self.assertEqual(m.call('nr_service')[0], 0)
            self.assertEqual(m.call('nr_busy')[0], 0)
        m.write(MENU_STATE, 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
        self.assertEqual(m.call('nr_enabled')[0], 1)
        self.assertEqual(m.call('nr_post', 1)[0], 0)
        self.assertEqual(m.call('nr_busy')[0], 1)

    def test_recording_request_keeps_idle_timer_awake(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, IDLE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
        m.write(b.symbols['OS_TICKS'], 123456)
        m.write(b.symbols['APO_TIMER'], 0)
        m.call('nr_post', 1)
        m.write(m.runtime + b.symbols['RT_ARMED'], 0)
        m.call('script_frame_run', m.runtime)
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
        self.assertEqual(kinds[-3:], [61, 62, 68])
        self.assertEqual(kinds.count(68), 1)

    def test_play_in_record_setup_starts_once_and_record_stops_with_its_release_swallowed(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
        m.call('nr_init')
        field = lambda name: m.read(NATIVE_RECORDING + b.symbols[name])
        byte = lambda name: m.uc.mem_read(NATIVE_RECORDING + b.symbols[name], 1)[0]
        packet = m.input + 0x5000
        send = lambda key, pressed=1: (m.uc.mem_write(packet, bytes(12) + bytes([0, key, pressed, 0]) + bytes(8)),
                                       m.call('nr_input', packet)[0])[1]
        m.write(NATIVE_RECORDING + b.symbols['NR_SELECTED'], 1)
        self.assertEqual(send(0), 0)                            # outside the setup REC and PLAY stay the firmware's
        self.assertEqual(send(2), 0)
        self.assertEqual(field('NR_REQUEST'), 0)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        self.assertEqual(send(0), 0)                            # REC in the setup, idle: the firmware closes it, no take
        self.assertEqual(field('NR_REQUEST'), 0)
        self.assertEqual(send(0, 0), 0)
        self.assertEqual(send(2), 0)                            # PLAY: a take, and the firmware gets REC to close the setup
        self.assertEqual(field('NR_REQUEST'), 1)
        self.assertEqual(m.uc.mem_read(packet + 13, 1)[0], 0)
        self.assertEqual(byte('NR_PLAY_BOUND'), b.symbols['NR_PLAY_WAIT'])
        self.assertEqual(byte('NR_PLAY_INJECT'), b.symbols['NR_PLAY_PENDING'])
        self.assertEqual(send(2, 0), 0)                         # its release goes on as REC's
        self.assertEqual(m.uc.mem_read(packet + 13, 1)[0], 0)
        self.assertEqual(field('NR_HELD'), 0)
        self.assertEqual(send(2), 0)                            # busy: PLAY in the setup starts no second take
        self.assertEqual(field('NR_REQUEST'), 1)
        send(2, 0)
        self.assertEqual(send(0), 1)                            # REC in the setup stops the take, its release is swallowed
        self.assertEqual(field('NR_REQUEST'), 2)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 0)
        self.assertEqual(send(0, 0), 1)
        self.assertEqual(send(0, 0), 0)
        m.call('nr_service')
        self.assertEqual(m.call('nr_busy')[0], 0)

    def test_play_taken_by_the_setup_reaches_the_firmware_after_it_closed(self):
        m, b = self.machine()
        from tools.patch.script_hooks import NATIVE_RECORDING
        m.call('nr_init')
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_PLAY_INJECT'], bytes([b.symbols['NR_PLAY_PENDING']]))
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR
        pressed = []
        def press_key(uc, at, size, data):                      # korg.pressKey's path into the panel queue
            pressed.append(uc.reg_read(UC_ARM_REG_R0))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        at = b.symbols['script_press_key_glue']
        m.uc.hook_add(UC_HOOK_CODE, press_key, begin=at, end=at)
        m.call('nr_play_inject_frame')
        self.assertEqual(pressed, [])
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 0)
        m.call('nr_play_inject_frame')
        m.call('nr_play_inject_frame')
        self.assertEqual(pressed, [2])
        self.assertEqual(m.uc.mem_read(NATIVE_RECORDING + b.symbols['NR_PLAY_INJECT'], 1)[0], 2)
        packet = m.input + 0x5000
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)    # even a setup still open lets our own PLAY through
        for pressed, left in ((1, 1), (0, 0)):
            m.uc.mem_write(packet, bytes(12) + bytes([0, 2, pressed, 0, 0, 0, 0, b.symbols['PK_MARK']]) + bytes(4))
            self.assertEqual(m.call('nr_input', packet)[0], 0)
            self.assertEqual(m.uc.mem_read(packet + 13, 1)[0], 2)
            self.assertEqual(m.uc.mem_read(NATIVE_RECORDING + b.symbols['NR_PLAY_INJECT'], 1)[0], left)

    def test_take_started_by_play_ends_with_the_transport_stop_only(self):
        m, b = self.machine()
        from tools.patch.script_hooks import NATIVE_RECORDING
        m.call('nr_init')
        transport = b.symbols['HW_TRANSPORT']
        bound = lambda: m.uc.mem_read(NATIVE_RECORDING + b.symbols['NR_PLAY_BOUND'], 1)[0]
        m.write(NATIVE_RECORDING + b.symbols['NR_REQUEST'], 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_PLAY_BOUND'], bytes([b.symbols['NR_PLAY_WAIT']]))
        m.write(transport, 0)
        m.call('nr_transport_frame')                            # not playing yet: wait, no stop
        self.assertEqual((bound(), m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST'])), (1, 1))
        for state in (1, 2, 4, 3, 11):                          # play, pause, REC on and off, the firmware's own states
            m.write(transport, state)
            m.call('nr_transport_frame')
            self.assertEqual((bound(), m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST'])), (2, 1), state)
        m.write(transport, 0)
        m.call('nr_transport_frame')
        self.assertEqual((bound(), m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST'])), (0, 2))
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_PLAY_BOUND'], b'\xff')   # FF at power-on binds nothing
        m.write(NATIVE_RECORDING + b.symbols['NR_REQUEST'], 1)
        m.call('nr_transport_frame')
        self.assertEqual(m.read(NATIVE_RECORDING + b.symbols['NR_REQUEST']), 1)

    def test_source_dial_has_three_choices_without_changing_native_boolean_schema(self):
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
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
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
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
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
        m.call('nr_post', 1)
        m.write(NATIVE_RECORDING + b.symbols['NR_SETUP'], 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x00')   # NATIVE RECORDING OFF
        packet = m.input + 0x5000
        m.uc.mem_write(packet, bytes(12) + bytes([0, 0, 1, 0]) + bytes(8))
        self.assertEqual(m.call('nr_input', packet)[0], 1)
        m.call('nr_service')
        self.assertEqual(m.call('nr_busy')[0], 0)

    def test_source_choice_stays_record_until_capture_and_file_are_released(self):
        m, b = self.machine()
        from tools.patch.script_hooks import MENU_STATE, NATIVE_RECORDING
        m.write(MENU_STATE, 1)
        m.uc.mem_write(NATIVE_RECORDING + b.symbols['NR_SETTING'], b'\x01')   # NATIVE RECORDING ON
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

    def test_terminal_gap_counter_is_visible_beside_the_failure_reason(self):
        m, b = self.machine()
        from tools.patch.script_hooks import NATIVE_RECORDING
        m.call('nr_init')
        m.write(NATIVE_RECORDING + b.symbols['NR_ERROR'], 20)
        m.write(NATIVE_RECORDING + b.symbols['NR_GAPS'], 1)
        title, value = m.input + 0x6000, m.input + 0x6040
        m.call('nr_format', title, value)
        self.assertEqual(bytes(m.uc.mem_read(title, 32)).split(b'\0', 1)[0], b'Capture gap #1')

    def test_emulator_menu_model_includes_the_sampler_recording_feature(self):
        from tools.emu import menu_cases as menu
        from unittest.mock import patch
        with patch.object(menu, 'LAST_PAGE', False), patch.object(menu, 'STEREO_PAGE', False), patch.object(menu, 'NATIVE_RECORDING_PAGE', True, create=True):
            self.assertEqual(menu.feature_pages()[-3:], ['GLIDE CHAIN', 'GLIDE SWITCH', 'NATIVE RECORDING'])
        with patch.object(menu, 'NATIVE_RECORDING_PAGE', False, create=True):
            self.assertNotIn('NATIVE RECORDING', menu.feature_pages())
