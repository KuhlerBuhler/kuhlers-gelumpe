"""Recording defers UI card writes while retaining their buffered changes."""
import unittest
from tools.patch import test_script_store as stores
from tools.patch.script_hooks import MENU_STATE, DATA_FILE


@unittest.skipUnless(stores.UNICORN_AVAILABLE, 'Unicorn is required for recording card interlocks')
class RecordingCardGateTests(unittest.TestCase):
    def machine(self):
        m = stores.NativeStoreTests().counter_machine()
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + m.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        return m

    def start(self, m):
        self.assertEqual(m.call('nr_post', 1)[0], 0)

    def stop(self, m):
        m.call('nr_post', 0)
        m.call('nr_service')
        self.assertEqual(m.call('nr_busy')[0], 0)

    def test_plugin_store_save_survives_recording_and_flushes_after_release(self):
        m = self.machine()
        entry = stores.NativeStoreTests().entry(m)
        m.write(m.runtime + m.symbols['RT_ENTRY'], entry)
        m.call('script_store_set_glue', 2, 123)
        m.call('script_store_save_glue')
        before = list(m.fat.opened)
        self.start(m)
        m.call('script_store_flush', m.runtime)
        self.assertEqual(m.fat.opened, before)
        self.assertEqual(m.read(m.runtime + stores.STORE_PENDING), 1)
        self.assertEqual(m.read(m.runtime + stores.STORE_WRITES), 0)
        self.stop(m)
        m.call('script_store_flush', m.runtime)
        self.assertEqual(m.read(m.runtime + stores.STORE_PENDING), 0)
        self.assertEqual(m.read(m.runtime + stores.STORE_WRITES), 1)
        saved = next(data for name, data in m.fat.files.items() if name.startswith('store.'))
        parsed = stores.node(parse=[saved.hex()])['parsed'][0]
        self.assertEqual(parsed['records'][0]['values'][2], 123)

    def test_plugin_data_remains_pending_and_keeps_exact_bytes_until_release(self):
        m = self.machine()
        block, payload = m.input + 0x80000, b'\x01\x80\x00\xff'
        m.uc.mem_write(block, b'counter' + bytes(9) + bytes(4) + payload)
        m.write(DATA_FILE, block)
        for name, value in (('DF_SIZE', len(payload)), ('DF_PENDING', 1), ('DF_FRAME', 0)):
            m.write(DATA_FILE + m.symbols[name], value)
        m.write(m.runtime + m.symbols['SCRIPT_CONTROL_FRAMES'], 1000)
        before = list(m.fat.opened)
        self.start(m)
        m.call('script_data_flush', m.runtime)
        self.assertEqual(m.fat.opened, before)
        self.assertEqual(m.read(DATA_FILE + m.symbols['DF_PENDING']), 1)
        self.stop(m)
        m.call('script_data_flush', m.runtime)
        self.assertEqual(m.read(DATA_FILE + m.symbols['DF_PENDING']), 0)
        self.assertEqual(m.fat.files['Data/counter/00.bin'], payload)

    def test_record_request_during_ui_open_waits_for_the_next_ui_boundary(self):
        from unicorn import UC_HOOK_CODE
        m = self.machine()
        entry = stores.NativeStoreTests().entry(m)
        m.write(m.runtime + m.symbols['RT_ENTRY'], entry)
        m.call('script_store_set_glue', 2, 321)
        m.call('script_store_save_glue')
        interrupted = []

        def request(uc, address, size, data):
            if interrupted:
                return
            interrupted.append(address)
            saved = uc.context_save()
            try:
                self.start(m)
                m.call('nr_service')
                self.assertEqual(m.read(m.symbols['NATIVE_RECORDING'] + m.symbols['NR_REQUEST']), 1)
                self.assertEqual(m.read(m.symbols['NATIVE_RECORDING'] + m.symbols['NR_CONTEXT']), 0)
            finally:
                uc.context_restore(saved)

        m.uc.hook_add(UC_HOOK_CODE, request, begin=m.symbols['FS_OPEN'], end=m.symbols['FS_OPEN'])
        m.call('script_store_flush', m.runtime)
        self.assertTrue(interrupted)
        self.assertEqual(m.read(m.runtime + stores.STORE_WRITES), 1)
        saved = next(data for name, data in m.fat.files.items() if name.startswith('store.'))
        parsed = stores.node(parse=[saved.hex()])['parsed'][0]
        self.assertEqual(parsed['records'][0]['values'][2], 321)
        self.assertEqual(m.read(m.symbols['NATIVE_RECORDING'] + m.symbols['NR_UI_READY']), 0)
        m.call('nr_ui_ack')
        self.assertEqual(m.read(m.symbols['NATIVE_RECORDING'] + m.symbols['NR_UI_READY']), 1)
        self.stop(m)

    def arm(self, m):
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + m.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        m.write(m.runtime + m.symbols['RT_ENTRY'], m.entry)

    def test_gif_card_read_waits_without_modifying_the_picture_array(self):
        from tools.patch import test_script_file as files
        files.NativeFileTests.setUpClass()
        helper = files.NativeFileTests()
        m = helper.machine({files.GIF + 'GIF07.E2G': helper.gif})
        self.arm(m)
        before = m.variables(m.entry)[:1024]
        opened = list(m.fat.opened)
        self.start(m)
        self.assertEqual(m.call('script_file_frame_glue', 1024 << 16, 7, 0)[0], 0xFFFFFFFF)
        self.assertEqual(m.variables(m.entry)[:1024], before)
        self.assertEqual(m.fat.opened, opened)
        self.stop(m)
        self.assertEqual(m.call('script_file_frame_glue', 1024 << 16, 7, 0)[0], 40)
        self.assertEqual(m.variables(m.entry)[:1024], files.node(read=[helper.gif.hex(), 0])['slots'])

    def test_media_folder_read_waits_and_preserves_the_cached_list(self):
        from tools.patch import test_script_file as files
        from tools.patch.script_hooks import MEDIA_LIST, MEDIA_END
        files.NativeMediaTests.setUpClass()
        helper = files.NativeMediaTests()
        m = helper.machine(helper.files)
        self.arm(m)
        before = bytes(m.uc.mem_read(MEDIA_LIST, MEDIA_END - MEDIA_LIST))
        self.start(m)
        self.assertEqual(m.call('script_file_count_glue', 0)[0], 0xFFFFFFFF)
        self.assertEqual(bytes(m.uc.mem_read(MEDIA_LIST, MEDIA_END - MEDIA_LIST)), before)
        self.stop(m)
        self.assertGreater(m.call('script_file_count_glue', 0)[0], 0)

    def test_settings_and_custom_export_are_queued_for_sd_without_flash_fallback(self):
        import struct
        from unicorn import UC_HOOK_CODE
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_PC, UC_ARM_REG_LR
        m = self.machine()
        m.uc.mem_write(MENU_STATE - 32, bytes(544))
        m.write(MENU_STATE, 1)
        m.uc.mem_write((MENU_STATE + m.symbols['MX_FLAGS2']) & 0xFFFFFFFF, b'\x20')
        m.uc.mem_map(m.symbols['LP_CODE'] & ~4095, 4096)
        m.write(m.symbols['LP_CODE'], 0xFFFFFFFF)
        m.write(m.symbols['SP_CODE'], 0xFFFFFFFF)
        attempts = []
        def firmware(uc, address, size, data):
            if address == m.symbols['menu_flash_save']:
                self.fail('deferred SD requests must not fall back to flash')
            if address == m.symbols['menu_pc_call']:
                uc.reg_write(UC_ARM_REG_R0, 0)
            else:
                pointer = uc.reg_read(UC_ARM_REG_R1)
                attempts.append(bytes(uc.mem_read(pointer, 80)).split(b'\0', 1)[0].decode())
                uc.reg_write(UC_ARM_REG_R0, 3)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        for name in ('FS_OPEN', 'menu_pc_call', 'menu_flash_save'):
            m.uc.hook_add(UC_HOOK_CODE, firmware, begin=m.symbols[name], end=m.symbols[name])
        self.start(m)
        m.call('menu_settings_save')
        m.call('menu_settings_write', 1)
        self.assertFalse(attempts)
        self.assertEqual(m.read(m.symbols['NATIVE_RECORDING'] + m.symbols['NR_DEFERRED']), 3)
        self.assertEqual(m.read(MENU_STATE + m.symbols['M_STATUS']), 0x58)
        m.call('nr_card_flush')
        self.assertFalse(attempts)
        self.stop(m)
        m.write(m.runtime + m.symbols['RT_ARMED'], 0)
        m.call('script_frame_run', m.runtime)
        self.assertEqual(attempts, ['SD:KORG/blechtribe/settings.b.bin', 'SD:KORG/blechtribe/e2sCustom.all'])
        self.assertEqual(m.read(m.symbols['NATIVE_RECORDING'] + m.symbols['NR_DEFERRED']), 0)

    def test_manual_card_actions_refuse_before_mutating_the_plugin_or_lists(self):
        m = self.machine()
        entry = stores.NativeStoreTests().entry(m)
        before = bytes(m.uc.mem_read(entry, 128))
        self.start(m)
        for name in ('menu_drop', 'menu_pon', 'menu_poff', 'menu_remove',
                     'menu_import', 'menu_export', 'menu_export_fx', 'menu_list',
                     'menu_desc_load', 'script_card_load'):
            with self.subTest(action=name):
                opened = list(m.fat.opened)
                m.call(name, entry, 0)
                self.assertEqual(m.fat.opened, opened)
                self.assertEqual(bytes(m.uc.mem_read(entry, 128)), before)
                self.assertEqual(m.read(MENU_STATE + m.symbols['M_STATUS']), 0x59)

    def test_directory_and_plugin_open_report_busy_without_changing_the_path(self):
        m = self.machine()
        path = m.symbols['LIST_PATH']
        m.uc.mem_write(path, b'cached path\0')
        before = bytes(m.uc.mem_read(path, 32))
        self.start(m)
        for name in ('menu_dir_open', 'menu_open_listed'):
            with self.subTest(action=name):
                self.assertEqual(m.call(name, path, path)[0], 0x39)
                self.assertEqual(bytes(m.uc.mem_read(path, 32)), before)
                self.assertEqual(m.read(MENU_STATE + m.symbols['M_STATUS']), 0x59)
