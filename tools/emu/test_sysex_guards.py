"""SysEx buffer guards share the image with live patch code, using only synthetic ARM."""
import struct
import unittest
from types import SimpleNamespace

import sysex_cases as s
import sample_swap as swap
import arm
import unicorn
from unicorn import arm_const as R

CALL, STOP = 0xC1000000, 0xC1000100


class BufferGuards(unittest.TestCase):
    def machine(self, swapped=False):
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        uc.mem_map(s.IMAGE, 0x200000)
        uc.mem_map(CALL, 0x1000)
        uc.mem_write(s.IMAGE, bytes([255]) * 0x200000)
        if swapped:
            site = next(site for site, _, _, label, *_ in swap.SITES if label == 'ss_giver')
            uc.mem_write(site, struct.pack('<I', swap.redirect(0xEA000000, site, swap.CODE1)))
            uc.mem_write(swap.STORE_CODE, b'OWN!')
            uc.mem_write(swap.STORE_CODE_END - 4, b'END!')
        uc.reg_write(R.UC_ARM_REG_CPSR, 0x13)
        dev = SimpleNamespace(m=SimpleNamespace(uc=uc))
        return uc, dev

    def access(self, uc, address, write=False, origin=CALL):
        op = 'str' if write else 'ldr'
        code = arm.assemble(f'ldr r0, ={address}\n{op} r1, [r0]\nbx lr\n.pool', origin=origin)
        uc.mem_write(origin, code.bytes)
        uc.reg_write(R.UC_ARM_REG_LR, STOP)
        uc.emu_start(origin, STOP, count=20)

    def test_installation_preserves_the_full_declared_live_swap_code(self):
        uc, dev = self.machine(True)
        before = bytes(uc.mem_read(swap.STORE_CODE, swap.STORE_CODE_END - swap.STORE_CODE))
        s.Link(dev)
        self.assertEqual(bytes(uc.mem_read(swap.STORE_CODE, len(before))), before)
        self.assertEqual(bytes(uc.mem_read(swap.STORE_CODE_END, s.spec.FILE_AREA - swap.STORE_CODE_END)),
                         bytes([0xD3]) * (s.spec.FILE_AREA - swap.STORE_CODE_END))

    def test_live_code_can_read_its_literal_pool(self):
        uc, dev = self.machine(True)
        s.Link(dev)
        self.access(uc, swap.STORE_CODE, origin=swap.CODE1)
        self.assertEqual(uc.reg_read(R.UC_ARM_REG_R1), int.from_bytes(b'OWN!', 'little'))

    def test_writing_live_code_is_still_refused(self):
        uc, dev = self.machine(True)
        s.Link(dev)
        with self.assertRaises(AssertionError):
            self.access(uc, swap.STORE_CODE, True)

    def test_a_sysex_buffer_overread_cannot_use_the_live_code_exception(self):
        uc, dev = self.machine(True)
        s.Link(dev)
        with self.assertRaisesRegex(AssertionError, 'undeclared read'):
            self.access(uc, swap.STORE_CODE, origin=s.spec.CODE_AT)

    def test_an_explicit_protocol_read_allows_only_the_requested_bytes(self):
        uc, dev = self.machine(True)
        link = s.Link(dev)

        def exchange(*args, **kwargs):
            self.access(uc, swap.STORE_CODE, origin=s.spec.CODE_AT)
            self.assertEqual(uc.reg_read(R.UC_ARM_REG_R1), int.from_bytes(b'OWN!', 'little'))
            with self.assertRaisesRegex(AssertionError, 'undeclared read'):
                self.access(uc, swap.STORE_CODE + 4, origin=s.spec.CODE_AT)
            return [], 0

        link.exchange = exchange
        link.ask(s.spec.FUNC_READ, struct.pack('<II', swap.STORE_CODE, 4))
        with self.assertRaisesRegex(AssertionError, 'undeclared read'):
            self.access(uc, swap.STORE_CODE, origin=s.spec.CODE_AT)

    def test_a_failed_exchange_does_not_leave_a_protocol_read_permission(self):
        uc, dev = self.machine(True)
        link = s.Link(dev)

        def failed(*args, **kwargs):
            raise RuntimeError('own exchange failed')

        link.exchange = failed
        with self.assertRaisesRegex(RuntimeError, 'own exchange failed'):
            link.ask(s.spec.FUNC_READ, struct.pack('<II', swap.STORE_CODE, 4))
        with self.assertRaisesRegex(AssertionError, 'undeclared read'):
            self.access(uc, swap.STORE_CODE, origin=s.spec.CODE_AT)

    def test_invalid_read_sizes_do_not_allow_access_to_the_live_code(self):
        for address, length in ((swap.STORE_CODE, 0), (swap.STORE_CODE, s.spec.MAX_BLOCK + 1), (0xFFFFFFFC, 8)):
            with self.subTest(address=address, length=length):
                uc, dev = self.machine(True)
                link = s.Link(dev)

                def exchange(*args, **kwargs):
                    self.access(uc, swap.STORE_CODE, origin=s.spec.CODE_AT)
                    return [], 0

                link.exchange = exchange
                with self.assertRaisesRegex(AssertionError, 'undeclared read'):
                    link.ask(s.spec.FUNC_READ, struct.pack('<II', address, length))

    def test_direct_emulator_changes_to_live_code_are_detected(self):
        uc, dev = self.machine(True)
        link = s.Link(dev)
        uc.mem_write(swap.STORE_CODE_END - 4, b'BAD!')
        with self.assertRaisesRegex(AssertionError, 'live swap code changed'):
            link.check_guards()

    def test_the_remaining_released_tail_refuses_both_reads_and_writes(self):
        for write in (False, True):
            with self.subTest(write=write):
                uc, dev = self.machine(True)
                s.Link(dev)
                with self.assertRaisesRegex(AssertionError, 'released RAM'):
                    self.access(uc, swap.STORE_CODE_END, write)

    def test_without_swap_the_original_full_tail_stays_guarded(self):
        for address in (s.spec.BUF_END, swap.STORE_CODE_END, s.spec.FILE_AREA - 4):
            with self.subTest(address=address):
                uc, dev = self.machine()
                s.Link(dev)
                self.assertEqual(bytes(uc.mem_read(address, 4)), bytes([0xD3]) * 4)
                with self.assertRaisesRegex(AssertionError, 'released RAM'):
                    self.access(uc, address)


if __name__ == '__main__':
    unittest.main()
