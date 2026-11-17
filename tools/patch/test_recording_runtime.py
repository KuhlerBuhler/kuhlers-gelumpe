"""Task-owned recording allocation, public requests and resource lifetime."""
import struct
import unittest
from tools.patch.test_recording_service import Recorder, UNICORN
if UNICORN:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_CPSR


class Runtime(Recorder):
    def __init__(self):
        from tools.patch.recording_runtime import source
        from tools.patch.arm import assemble
        constants = '.equ NATIVE_RECORDING, 0x210000\n.equ MENU_STATE, 0x211000\n.equ M_ON, 0\n.equ MX_FLAGS2, 4\n.equ FLAGS2_NATIVE_RECORDING, 32\n.equ MG_ALLOC, 0xC0028DCC\n.equ MG_FREE, 0xC0028DD4\n.equ OS_TICKS, 0xC06A292C\n'
        super().__init__(code=assemble(constants + source(), origin=0x100000))
        self.uc.mem_map(0x210000, 0x2000)
        self.uc.mem_write(0x210000, b'\xff' * 64)
        self.uc.mem_map(0x600000, 0x202000)
        self.uc.mem_write(0x600000, b'\xa5' * 0x202000)
        self.heap, self.fail_alloc, self.on_alloc = [], False, None
        self.max_alloc = 0xFFFFFFFF
        self.require_irq_enabled = True
        self.uc.reg_write(UC_ARM_REG_CPSR, 0x13)
        self.uc.mem_map(self.s('MG_ALLOC') & ~4095, 4096)
        for name in ('MG_ALLOC', 'MG_FREE'):
            address = self.s(name)
            self.uc.mem_write(address, struct.pack('<I', 0xE12FFF1E))
            self.uc.hook_add(UC_HOOK_CODE, self.alloc, begin=address, end=address)
        self.enabled(True)

    def alloc(self, uc, address, size, data):
        assert not uc.reg_read(UC_ARM_REG_CPSR) & 0xC0
        assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
        name = 'alloc' if address == self.s('MG_ALLOC') else 'free'
        value = uc.reg_read(UC_ARM_REG_R0)
        self.heap.append((name, value))
        if self.on_alloc:
            self.on_alloc(name)
        uc.reg_write(UC_ARM_REG_R0, (0 if self.fail_alloc or value > self.max_alloc else 0x600000) if name == 'alloc' else 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def enabled(self, flag):
        self.uc.mem_write(0x211000, struct.pack('<II', 1, 32 if flag else 0))

    def public(self, field):
        return struct.unpack('<I', self.uc.mem_read(0x210000 + self.s(field), 4))[0]

    def post(self, start):
        # nr_post takes the command in r0; Writer.call supplies its context there.
        old = self.ctx
        self.ctx = start
        try:
            self.uc.reg_write(UC_ARM_REG_SP, self.stack + 0xF000)
            self.uc.reg_write(UC_ARM_REG_LR, self.stop)
            self.uc.reg_write(UC_ARM_REG_R0, start)
            self.uc.emu_start(self.s('nr_post'), self.stop, count=2000000)
            return self.uc.reg_read(UC_ARM_REG_R0)
        finally:
            self.ctx = old

    def step(self):
        return self.call('nr_service')

    def close(self):
        self.post(0)
        for _ in range(64):
            self.step()
            if not self.public('NR_PHASE'):
                return
        raise AssertionError('runtime retained resources')


@unittest.skipUnless(UNICORN, 'Unicorn is required for the recording runtime')
class RecordingRuntimeTests(unittest.TestCase):
    def test_disabled_feature_is_inert_and_commands_do_no_io(self):
        m = Runtime()
        m.enabled(False)
        self.assertEqual(m.post(1), m.s('NR_DISABLED'))
        for _ in range(3):
            m.step()
        self.assertFalse(m.heap)
        self.assertFalse(m.events)
        m.enabled(True)
        self.assertEqual(m.post(1), 0)
        self.assertEqual(m.call('nr_busy'), 1)
        self.assertFalse(m.heap)
        self.assertFalse(m.events)
        m.post(0)
        m.step()
        self.assertFalse(m.heap)

    def test_dynamic_ring_is_allocated_once_and_freed_after_finalization(self):
        m = Runtime()
        m.post(1)
        m.step()
        self.assertEqual(m.heap, [('alloc', m.s('RC_SIZE') + 2097152)])
        self.assertEqual(m.public('NR_PHASE'), 1)
        self.assertEqual(m.public('NR_CONTEXT'), 0x600000)
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(0x600000 + m.s('RC_CAPACITY'), 4))[0], 2097152)
        m.capture([0x12345678] * 1000, elapsed=20)
        m.step()
        m.close()
        self.assertEqual(m.heap[-1], ('free', 0x600000))
        self.assertEqual(m.public('NR_CONTEXT'), 0)
        self.assertEqual(m.public('NR_BYTES'), 4000)
        self.assertEqual(m.public('NR_NUMBER'), 1)
        self.assertFalse(m.handles)
        self.assertEqual(bytes(m.uc.mem_read(0x600000 + m.s('RC_SIZE') + 2097152, 16)), b'\xa5' * 16)
        m.post(1)
        m.step()
        m.close()
        self.assertIn('SD:Recordings/REC0002.WAV', m.files)

    def test_no_memory_reports_error_without_touching_card_or_dsp(self):
        m = Runtime()
        m.fail_alloc = True
        m.post(1)
        m.step()
        self.assertEqual(m.public('NR_ERROR'), m.s('NR_OOM'))
        self.assertEqual(m.public('NR_PHASE'), 0)
        self.assertFalse(m.events)
        self.assertEqual(m.call('nr_busy'), 0)

    def test_stop_during_allocation_cancels_before_file_creation(self):
        m = Runtime()
        def stop(name):
            if name == 'alloc':
                m.uc.mem_write(0x210000 + m.s('NR_REQUEST'), struct.pack('<I', 2))
        m.on_alloc = stop
        m.post(1)
        m.step()
        self.assertFalse(m.files)
        self.assertEqual(m.heap[-1], ('free', 0x600000))
        self.assertEqual(m.public('NR_PHASE'), 0)

    def test_close_failure_keeps_context_until_retry_and_flag_off_stops(self):
        m = Runtime()
        m.post(1)
        m.step()
        m.close_failures = 2
        m.enabled(False)
        m.step()
        self.assertEqual(m.public('NR_PHASE'), 2)
        self.assertEqual(len(m.heap), 1)
        self.assertEqual(m.call('nr_busy'), 1)
        m.step()
        m.step()
        self.assertEqual(m.heap[-1], ('free', 0x600000))
        self.assertEqual(m.public('NR_CONTEXT'), 0)
        self.assertNotEqual(m.public('NR_ERROR'), 0)

    def test_controller_remains_busy_until_heap_release_finishes(self):
        m = Runtime()
        def check(name):
            if name == 'free':
                self.assertNotEqual(m.public('NR_PHASE'), 0)
                self.assertEqual(m.public('NR_CONTEXT'), 0x600000)
        m.on_alloc = check
        m.post(1)
        m.step()
        m.close()

    def test_stop_during_file_open_is_preserved_for_the_next_task_step(self):
        m = Runtime()
        def stop(name):
            if name == 'OPEN':
                m.uc.mem_write(0x210000 + m.s('NR_REQUEST'), struct.pack('<I', 2))
        m.on_fat = stop
        m.post(1)
        m.step()
        self.assertEqual(m.public('NR_REQUEST'), 2)
        for _ in range(4):
            m.step()
        self.assertEqual(m.public('NR_CONTEXT'), 0)
        self.assertFalse(m.handles)
        self.assertEqual(m.heap[-1], ('free', 0x600000))

    def test_ring_uses_largest_available_supported_heap_block(self):
        m = Runtime()
        m.max_alloc = m.s('RC_SIZE') + 524288
        m.post(1)
        m.step()
        self.assertEqual(m.public('NR_PHASE'), 1)
        self.assertEqual(m.heap, [('alloc', m.s('RC_SIZE') + n) for n in (2097152, 1048576, 524288)])
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(0x600000 + m.s('RC_CAPACITY'), 4))[0], 524288)
        m.close()
        self.assertEqual(m.heap[-1], ('free', 0x600000))
