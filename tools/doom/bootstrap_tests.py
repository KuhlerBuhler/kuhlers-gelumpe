#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prüft den eigenen ARM-Einstieg ohne Firmware oder Gerätetreiber."""
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm_const as A

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = json.loads((ROOT / 'tools/doom/layout.json').read_text())
PATCH = json.loads((ROOT / 'data/patches/doom-loader.json').read_text())
BASE = LAYOUT['bootstrap']
CODE = bytes.fromhex(next(c['bytes'] for c in PATCH['changes'] if c.get('file') == BASE - 0xC0000000 + 0x100))
PANEL, STACK, RETURN = 0xC0300000, 0xC0200000, 0xC00FFFF0


class EntryTests(unittest.TestCase):
    def entry(self, held, mode=0, update=0):
        uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        uc.mem_map(0xC0000000, 0x800000)
        uc.mem_write(BASE, CODE)
        uc.mem_write(0xC033E6F8, struct.pack('<I', PANEL))
        uc.mem_write(PANEL + 0x18, struct.pack('<Q', held))
        uc.mem_write(PANEL + 0x20, bytes([mode, 0, update]))
        uc.mem_write(0xC06A010C, struct.pack('<I', PANEL + 0x100))   # a registered volume: the loader goes on to open the files
        regs = [getattr(A, 'UC_ARM_REG_R' + str(i)) for i in range(13)]
        before = [0x12340000 + i for i in range(13)]
        uc.reg_write(A.UC_ARM_REG_CPSR, 0xA0000053)
        for reg, value in zip(regs, before):
            uc.reg_write(reg, value)
        uc.reg_write(A.UC_ARM_REG_SP, STACK)
        uc.reg_write(A.UC_ARM_REG_LR, RETURN)
        selected = []

        def step(machine, at, size, data):
            if at == RETURN:
                machine.emu_stop()
            elif not BASE <= at < BASE + len(CODE):
                selected.append(machine.reg_read(A.UC_ARM_REG_SP))
                machine.emu_stop()

        uc.hook_add(UC_HOOK_CODE, step)
        uc.emu_start(BASE, 0, count=200_000)
        return uc, regs, before, selected

    def test_selected_c_loader_calls_drivers_with_an_eight_byte_aligned_stack(self):
        uc, _, _, selected = self.entry(0x408)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0] % 8, 0, 'AAPCS requires SP modulo 8 = 0 at the C entry')

    def test_other_boot_modes_preserve_the_replaced_instruction_and_context(self):
        for held, mode, update in [(0, 0, 0), (0x400, 0, 0), (0x8, 0, 0),
                                   (0x2408, 0, 0), (0x100000408, 0, 0),
                                   (0x408, 1, 0), (0x408, 0, 1)]:
            with self.subTest(held=held, mode=mode, update=update):
                uc, regs, before, selected = self.entry(held, mode, update)
                self.assertEqual(selected, [])
                before[4] = before[0]
                self.assertEqual([uc.reg_read(reg) for reg in regs], before)
                self.assertEqual(uc.reg_read(A.UC_ARM_REG_SP), STACK)
                self.assertEqual(uc.reg_read(A.UC_ARM_REG_PC), RETURN)
                self.assertEqual(uc.reg_read(A.UC_ARM_REG_CPSR) & 0xF00000FF, 0xA0000053)


class LoaderTests(unittest.TestCase):
    def load(self, open_errors=()):
        program = (ROOT / 'third_party/doom/doom.bin').read_bytes()
        uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        uc.mem_map(0xC0000000, 0x2000000)
        uc.mem_write(BASE, CODE)
        uc.mem_write(0xC033E6F8, struct.pack('<I', PANEL))
        uc.mem_write(PANEL + 0x18, struct.pack('<Q', 0x408))
        uc.mem_write(0xC06A010C, struct.pack('<I', PANEL + 0x100))
        uc.reg_write(A.UC_ARM_REG_CPSR, 0x53)
        uc.reg_write(A.UC_ARM_REG_SP, STACK)
        uc.reg_write(A.UC_ARM_REG_LR, RETURN)
        opened, offsets, frames, stacks = [], [0], [], []
        stopped = []
        shared = LAYOUT['shared']

        def call(machine, at, size, data):
            stacks.append((at, machine.reg_read(A.UC_ARM_REG_SP)))
            args = [machine.reg_read(getattr(A, 'UC_ARM_REG_R' + str(i))) for i in range(4)]
            result = 0
            if at == 0xC009DB60:
                opened.append(at)
                result = open_errors[len(opened)-1] if len(opened) <= len(open_errors) else 0
                machine.mem_write(args[0] + 12, struct.pack('<I', len(program)))
            elif at == 0xC009DD74:
                block = program[offsets[0]:offsets[0] + args[2]]
                machine.mem_write(args[1], block)
                machine.mem_write(args[3], struct.pack('<I', len(block)))
                offsets[0] += len(block)
            elif at == 0xC0015DD0 and args[1] == 3:
                frames.append(bytes(machine.mem_read(0xC031B310, 1024)))
            elif at == 0xC0024B6C:
                stage = struct.unpack('<I', machine.mem_read(shared + 8, 4))[0]
                if stage == 0x80000000:
                    stopped.append('error')
                    machine.emu_stop()
                    return
            machine.reg_write(A.UC_ARM_REG_R0, result)
            machine.reg_write(A.UC_ARM_REG_PC, machine.reg_read(A.UC_ARM_REG_LR))

        for address in [0xC0025754, 0xC00005A0, 0xC0025A14, 0xC003FD20,
                        0xC009DB60, 0xC009DD74, 0xC009E3DC, 0xC0024B6C,
                        0xC0000B78, 0xC0015DD0]:
            uc.hook_add(UC_HOOK_CODE, call, begin=address, end=address)

        def engine(machine, at, size, data):
            stopped.append('engine')
            machine.emu_stop()
        uc.hook_add(UC_HOOK_CODE, engine, begin=0xC1000000, end=0xC1000000)

        def start(machine, at, size, data):
            stopped.append('start')
            machine.emu_stop()
        uc.hook_add(UC_HOOK_CODE, start, begin=RETURN, end=RETURN)
        uc.emu_start(BASE, 0, count=100_000_000)
        self.assertTrue(stopped, 'loader must reach the engine, its error idle or the normal start')
        self.assertTrue(all(sp % 8 == 0 for _, sp in stacks), stacks)
        values = struct.unpack('<4I', uc.mem_read(shared, 16))
        self.drivers = [at for at, _ in stacks if at in (0xC0025754, 0xC00005A0, 0xC0025A14, 0xC003FD20)]
        self.closed = sum(at == 0xC009E3DC for at, _ in stacks)
        return values, opened, offsets[0], frames, stopped

    def test_missing_files_return_to_the_normal_start_before_any_driver_call(self):
        for errors, opens, closes in [((4,), 1, 0), ((5,), 1, 0), ((13,), 1, 0), ((0, 4), 2, 1), ((0, 5), 2, 1)]:
            with self.subTest(errors=errors):
                values, opened, read, frames, stopped = self.load(errors)
                self.assertEqual(stopped, ['start'])
                self.assertEqual(values, (0, 0, 0, 0))
                self.assertEqual((len(opened), self.closed, read, frames, self.drivers), (opens, closes, 0, [], []))

    def test_lazy_mount_and_slow_card_reach_the_pinned_engine_with_visible_progress(self):
        values, opened, read, frames, stopped = self.load((3, 3))
        self.assertEqual(values, (0x4D4F4F44, 1, 3, 0))
        self.assertEqual(len(opened), 3)
        self.assertEqual(read, (ROOT / 'third_party/doom/doom.bin').stat().st_size)
        self.assertEqual(stopped, ['engine'])
        self.assertGreater(len(set(frames)), 10, 'BOOT, READ progress and START must reach the display')
        self.assertTrue(all(any(frame) for frame in frames))

    def test_exhausted_card_retries_show_an_error_without_entering_the_engine(self):
        values, opened, read, frames, stopped = self.load((3,) * 7)
        self.assertEqual(values, (0x4D4F4F44, 1, 0x80000000, 0x103))
        self.assertEqual(len(opened), 7, 'doom.wad once before the drivers, doom.bin six times after')
        self.assertEqual(read, 0)
        self.assertEqual(stopped, ['error'])
        self.assertEqual(len(set(frames)), 2)


if __name__ == '__main__':
    unittest.main()
