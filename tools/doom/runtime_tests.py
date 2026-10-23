#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Isolierte ARM Tests des gebauten Adapters mit ausdrücklich simulierten Treibern."""
import argparse
import json
from pathlib import Path
import struct
import unittest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

BUILD = None
SHARED = json.loads((Path(__file__).parent / "layout.json").read_text())["shared"]
TICK, SCRATCH, TRAP = 0xC06A2930, 0xC0E00000, 0xC0F00000
WAD = b"SD:/KORG/blechtribe/Doom/doom.wad\0"
REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]


class Adapter:
    def __init__(self):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x2000000)
        self.uc.mem_write(0xC1000000, (BUILD / "doom-runtime.bin").read_bytes())
        self.symbols = {}
        for line in (BUILD / "symbols.txt").read_text().splitlines():
            fields = line.split()
            if len(fields) == 3:
                self.symbols[fields[2]] = int(fields[0], 16)
        self.word(self.symbols["shared"], SHARED)
        self.word(self.symbols["heap_end"], self.symbols["__heap_start"])
        self.word(self.symbols["clock_start"], 100)
        self.word(TICK, 100)
        self.uc.mem_write(SCRATCH, WAD)
        self.content = b"0123456789abcdef"
        self.messages, self.calls = [], []
        self.open_error = self.read_error = self.seek_error = 0
        self.powered = True
        self.instructions = 0
        self.clock_step = False
        self.uc.hook_add(UC_HOOK_CODE, self.step)

    def word(self, at, value=None):
        if value is None:
            return struct.unpack("<I", self.uc.mem_read(at, 4))[0]
        self.uc.mem_write(at, struct.pack("<I", value & 0xFFFFFFFF))

    def step(self, uc, at, size, data):
        self.instructions += 1
        if self.clock_step and self.instructions % 100 == 0:
            self.word(TICK, self.word(TICK) + 1)
        if at == TRAP:
            uc.emu_stop()
            return
        render = getattr(self, "render_stub", False) and at == self.symbols.get("R_RenderPlayerView")
        if not render and at not in (0xC0028600, 0xC009DB60, 0xC009DD74, 0xC009E404, 0xC009E3DC, 0xC0024B6C, 0xC0015DD0, 0xC001734C):
            return
        args = [uc.reg_read(r) for r in REGS]
        self.calls.append((at, args))
        result = 0
        if at == 0xC001734C:
            self.powered = False
            uc.emu_stop()
            return
        if at == 0xC009DB60:
            result = self.open_error
            self.word(args[0] + 8, 0)
            self.word(args[0] + 12, len(self.content))
        elif at == 0xC009DD74:
            result = self.read_error
            offset = self.word(args[0] + 8)
            chunk = self.content[offset:offset + args[2]] if not result else b""
            if chunk:
                uc.mem_write(args[1], chunk)
            self.word(args[3], len(chunk))
            self.word(args[0] + 8, offset + len(chunk))
        elif at == 0xC009E404:
            result = self.seek_error
            if not result:
                self.word(args[0] + 8, args[1])
        elif at == 0xC0024B6C:
            if self.messages:
                uc.mem_write(args[1], bytes(self.messages.pop(0)))
                result = 1
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def call(self, name, *args, count=300000):
        for reg, value in zip(REGS, args):
            self.uc.reg_write(reg, value & 0xFFFFFFFF)
        self.uc.reg_write(UC_ARM_REG_SP, 0xC1800000)
        self.uc.reg_write(UC_ARM_REG_LR, TRAP)
        self.uc.emu_start(self.symbols[name], 0xFFFFFFFF, count=count)
        if self.uc.reg_read(UC_ARM_REG_PC) != TRAP:
            raise AssertionError(f"{name} kehrt nicht innerhalb {count} Instruktionen zurück")
        return self.uc.reg_read(UC_ARM_REG_R0)


class NativeAdapterTest(unittest.TestCase):
    def setUp(self):
        self.arm = Adapter()

    def test_only_wad_and_readonly_reach_fatfs(self):
        a = self.arm
        self.assertEqual(a.call("_open", SCRATCH, 0, 0), 3)
        for flags in (1, 2, 0x200, 0x400, 8):
            self.assertEqual(a.call("_open", SCRATCH, flags, 0), 0xFFFFFFFF)
        a.uc.mem_write(SCRATCH + 100, b"SD:/OTHER.WAD\0")
        self.assertEqual(a.call("_open", SCRATCH + 100, 0, 0), 0xFFFFFFFF)
        self.assertEqual(len(a.calls), 1)
        self.assertEqual(a.calls[0][1][2], 1)

    def test_file_slots_close_and_io_failure(self):
        a = self.arm
        self.assertEqual([a.call("_open", SCRATCH, 0, 0) for _ in range(5)], [3, 4, 5, 6, 0xFFFFFFFF])
        self.assertEqual(a.call("_close", 4), 0)
        self.assertEqual(a.call("_read", 4, SCRATCH + 200, 1), 0xFFFFFFFF)
        self.assertEqual(a.call("_open", SCRATCH, 0, 0), 4)
        a.open_error = 1
        a.call("_close", 4)
        self.assertEqual(a.call("_open", SCRATCH, 0, 0), 0xFFFFFFFF)

    def test_read_seek_positions_and_bounds(self):
        a = self.arm
        a.call("_open", SCRATCH, 0, 0)
        self.assertEqual(a.call("_read", 3, SCRATCH + 200, 4), 4)
        self.assertEqual(bytes(a.uc.mem_read(SCRATCH + 200, 4)), b"0123")
        self.assertEqual(a.call("_lseek", 3, -2, 1), 2)
        self.assertEqual(a.call("_lseek", 3, -1, 2), 15)
        self.assertEqual(a.call("_read", 3, SCRATCH + 200, 8), 1)
        self.assertEqual(a.word(SHARED + 32), 2)
        self.assertEqual(a.word(SHARED + 36), 5)
        for offset, whence in ((-1, 0), (17, 0), (0x7FFFFFFF, 1), (0, 9)):
            self.assertEqual(a.call("_lseek", 3, offset, whence), 0xFFFFFFFF)
        a.seek_error = 1
        self.assertEqual(a.call("_lseek", 3, 0, 0), 0xFFFFFFFF)
        a.read_error = 1
        self.assertEqual(a.call("_read", 3, SCRATCH + 200, 1), 0xFFFFFFFF)

    def test_heap_rejects_overflow_and_negative_without_advancing(self):
        a = self.arm
        start, end = a.symbols["__heap_start"], a.symbols["__heap_limit"]
        self.assertEqual(a.call("_sbrk", end - start), start)
        self.assertEqual(a.call("_sbrk", 1), 0xFFFFFFFF)
        self.assertEqual(a.call("_sbrk", -1), 0xFFFFFFFF)
        self.assertEqual(a.word(a.symbols["heap_end"]), end)
        self.assertEqual(a.word(SHARED + 40), end - start)

    def test_panel_translation_releases_unknown_and_bounded_drain(self):
        a = self.arm
        for panel, key in ((11, 0xAD), (15, 0xAF), (8, 0xAC), (12, 0xAE), (2, 0xA3), (3, 0xA2), (0, 13), (9, 27), (13, 27)):
            for down in (1, 0):
                a.messages.append([0, panel, down, 0, 0])
                self.assertEqual(a.call("DG_GetKey", SCRATCH + 200, SCRATCH + 204), 1)
                self.assertEqual(a.word(SCRATCH + 200), down)
                self.assertEqual(a.uc.mem_read(SCRATCH + 204, 1)[0], key)
        a.messages = [[2, 0, 0, 0, 0]] * 40
        self.assertEqual(a.call("DG_GetKey", SCRATCH + 200, SCRATCH + 204), 0)
        self.assertEqual(len(a.messages), 8)
        self.assertEqual(a.word(SHARED + 44), 18)

    def test_pad_controls_hold_release_and_multiple_sources(self):
        a = self.arm
        mapping = {0: 0xA0, 1: 0xAD, 2: 0xA1, 6: ord("]"), 7: 0xA2,
                   8: 0xAC, 9: 0xAF, 10: 0xAE, 14: 0xB6, 15: 0xA3}
        for index, key in mapping.items():
            for down in (1, 0):
                a.messages.append([4, index, 0, 100, down])
                self.assertEqual(a.call("DG_GetKey", SCRATCH, SCRATCH + 4), 1)
                self.assertEqual(a.word(SCRATCH), down)
                self.assertEqual(a.uc.mem_read(SCRATCH + 4, 1)[0], key)
        a.messages += [[4, 1, 0, 90, 1], [0, 11, 1, 0, 0],
                       [4, 1, 0, 0, 0], [0, 11, 0, 0, 0]]
        self.assertEqual(a.call("DG_GetKey", SCRATCH, SCRATCH + 4), 1)
        self.assertEqual(a.word(SCRATCH), 1)
        self.assertEqual(a.call("DG_GetKey", SCRATCH, SCRATCH + 4), 1)
        self.assertEqual(a.word(SCRATCH), 0)
        self.assertEqual(a.call("DG_GetKey", SCRATCH, SCRATCH + 4), 0)
        a.messages += [[4, 1, 0, 100, 1], [4, 10, 0, 100, 1], [4, 15, 0, 100, 1]]
        keys = []
        for _ in range(3):
            self.assertEqual(a.call("DG_GetKey", SCRATCH, SCRATCH + 4), 1)
            keys.append(a.uc.mem_read(SCRATCH + 4, 1)[0])
        self.assertEqual(keys, [0xAD, 0xAE, 0xA3])
        a.messages += [[4, 16, 0, 100, 1], [4, 3, 0, 100, 1]]
        self.assertEqual(a.call("DG_GetKey", SCRATCH, SCRATCH + 4), 0)

    def test_pad_leds_are_bounded_cached_and_show_pressed_actions(self):
        a = self.arm
        a.word(0xC033E6FC, 0xC0100000)
        for i in range(10):
            a.word(TICK, 100 + i * 10)
            before = len(a.calls)
            a.call("doom_update_leds")
            self.assertLessEqual(len(a.calls) - before, 4)
        leds = {args[1]: args[2] for at, args in a.calls if at == 0xC0028600}
        self.assertEqual(len(leds), 32)
        self.assertEqual(leds[0x2F], 64)
        self.assertEqual(leds[0x4A], 96)
        self.assertEqual(leds[0x32], 0)
        before = len(a.calls)
        a.call("doom_update_leds")
        self.assertEqual(len(a.calls), before)
        a.messages.append([4, 15, 0, 100, 1])
        a.call("DG_GetKey", SCRATCH, SCRATCH + 4)
        a.word(TICK, 210)
        a.call("doom_update_leds")
        self.assertIn((0xC0028600, [0xC0100000, 0x4A, 255]),
                      [(at, args[:3]) for at, args in a.calls])
        a.messages.append([4, 15, 0, 0, 0])
        a.call("DG_GetKey", SCRATCH, SCRATCH + 4)
        a.word(TICK, 220)
        a.call("doom_update_leds")
        self.assertEqual([args[2] for at, args in a.calls if at == 0xC0028600 and args[1] == 0x4A][-1], 96)

    def test_controls_configure_gentle_turns_and_weapon_selection(self):
        a = self.arm
        a.call("doom_configure_controls")
        self.assertEqual(a.word(a.symbols["key_nextweapon"]), ord("]"))
        self.assertEqual(struct.unpack("<III", a.uc.mem_read(a.symbols["angleturn"], 12)), (320, 480, 240))

    def test_distant_lighting_is_bounded_without_fullbright(self):
        a = self.arm
        base = SCRATCH + 0x10000
        a.word(a.symbols["colormaps"], base)
        for name, count in (("scalelight", 16 * 48), ("zlight", 16 * 128)):
            address = a.symbols[name]
            a.uc.mem_write(address, struct.pack("<I", base + 31 * 256) * count)
            a.word(address + 4, base + 4 * 256)
        a.render_stub = True
        a.call("__wrap_R_RenderPlayerView", SCRATCH)
        for name, count in (("scalelight", 16 * 48), ("zlight", 16 * 128)):
            address = a.symbols[name]
            values = struct.unpack("<" + "I" * count, a.uc.mem_read(address, count * 4))
            self.assertEqual(values[0], base + 16 * 256)
            self.assertEqual(values[1], base + 4 * 256)
            self.assertTrue(all(base <= v <= base + 16 * 256 for v in values))
        a.call("__wrap_R_RenderPlayerView", SCRATCH)
        self.assertEqual(a.word(a.symbols["scalelight"]), base + 16 * 256)
        a.word(a.symbols["scalelight"], base + 30 * 256)
        a.call("__wrap_R_RenderPlayerView", SCRATCH)
        self.assertEqual(a.word(a.symbols["scalelight"]), base + 16 * 256)

    def test_dark_midtones_have_readable_light_coverage(self):
        a = self.arm
        pixels = a.symbols["__heap_start"]
        a.uc.mem_write(pixels, struct.pack("<I", 0x202020) * (320 * 200))
        a.word(a.symbols["DG_ScreenBuffer"], pixels)
        a.call("DG_DrawFrame", count=3000000)
        white = 8192 - sum(v.bit_count() for v in a.uc.mem_read(0xC031B310, 1024))
        self.assertGreaterEqual(white, 3000)
        self.assertLessEqual(white, 5000)

    def test_fixed_brightness_is_independent_of_other_image_regions(self):
        a = self.arm
        pixels = a.symbols["__heap_start"]
        frames = []
        for other in (0x606060, 0xFFFFFF):
            image = b"".join(struct.pack("<I", 0x202020 if x < 160 else other)
                             for y in range(200) for x in range(320))
            a.uc.mem_write(pixels, image)
            a.word(a.symbols["DG_ScreenBuffer"], pixels)
            a.call("DG_DrawFrame", count=3000000)
            frames.append(bytes(a.uc.mem_read(0xC031B310, 1024)))
        self.assertEqual(frames[0][:32], frames[1][:32])
        self.assertLess(sum(v.bit_count() for v in frames[0][:32]), 240)

    def test_clock_does_not_advance_on_reads_and_sleep_uses_external_ticks(self):
        a = self.arm
        a.word(TICK, 1234)
        self.assertEqual(a.call("DG_GetTicksMs"), 1134)
        self.assertEqual(a.call("DG_GetTicksMs"), 1134)
        self.assertEqual(a.word(TICK), 1234)
        a.clock_step = True
        before = a.word(TICK)
        a.call("DG_SleepMs", 5, count=5000)
        self.assertGreaterEqual(a.word(TICK) - before, 5)
        a.word(a.symbols["clock_start"], 0xFFFFFFF0)
        a.word(TICK, 0x20)
        a.clock_step = False
        self.assertEqual(a.call("DG_GetTicksMs"), 0x30)

    def test_console_wraps_and_sd_write_is_rejected(self):
        a = self.arm
        text = bytes(range(256)) * 9
        a.uc.mem_write(SCRATCH + 512, text)
        self.assertEqual(a.call("_write", 1, SCRATCH + 512, len(text)), len(text))
        self.assertEqual(a.word(SHARED + 56), len(text))
        self.assertEqual(bytes(a.uc.mem_read(SHARED + 68, 256)), text[-256:])
        a.call("_open", SCRATCH, 0, 0)
        calls = len(a.calls)
        self.assertEqual(a.call("_write", 3, SCRATCH + 512, 1), 0xFFFFFFFF)
        self.assertEqual(len(a.calls), calls)

    def test_exit_keeps_failure_visible_without_returning(self):
        a = self.arm
        a.word(SHARED + 16, 17)
        a.uc.reg_write(UC_ARM_REG_R0, 0xFFFFFFFF)
        a.uc.reg_write(UC_ARM_REG_SP, 0xC1800000)
        a.uc.reg_write(UC_ARM_REG_LR, TRAP)
        a.uc.emu_start(a.symbols["_exit"], 0xFFFFFFFF, count=100000)
        self.assertNotEqual(a.uc.reg_read(UC_ARM_REG_PC), TRAP)
        self.assertEqual(a.word(SHARED + 8), 0x80000000)
        self.assertEqual(a.word(SHARED + 12), 0xFFFFFFFF)
        self.assertEqual(a.word(SHARED + 60), 0xFFFFFFFF)
        self.assertEqual(a.word(SHARED + 16), 17)

    def test_quit_wrapper_runs_cleanup_and_displays_stopped(self):
        a = self.arm
        a.uc.reg_write(UC_ARM_REG_SP, 0xC1800000)
        a.uc.reg_write(UC_ARM_REG_LR, TRAP)
        a.uc.emu_start(a.symbols["__wrap_I_Quit"], 0xFFFFFFFF, count=100000)
        self.assertNotEqual(a.uc.reg_read(UC_ARM_REG_PC), TRAP)
        self.assertEqual(a.word(SHARED + 8), 6)
        self.assertEqual(a.word(SHARED + 12), 0)
        self.assertEqual(a.word(SHARED + 60), 0)
        self.assertEqual(bytes(a.uc.mem_read(0xC031B310 + 128 + 4, 5)), bytes([0x7F, 0x41, 0x41, 0x22, 0x1C]))
        self.assertEqual([regs[1] for at, regs in a.calls if at == 0xC0015DD0], [2, 3])

    def test_power_release_is_ignored_and_press_calls_only_final_gpio_service(self):
        a = self.arm
        a.messages = [[6, 0, 0, 0, 0], [0, 12, 1, 0, 0]]
        self.assertEqual(a.call("DG_GetKey", SCRATCH + 200, SCRATCH + 204), 1)
        self.assertTrue(a.powered)
        a.messages = [[6, 1, 0, 0, 0]]
        a.uc.reg_write(UC_ARM_REG_R0, SCRATCH + 200)
        a.uc.reg_write(UC_ARM_REG_R1, SCRATCH + 204)
        a.uc.reg_write(UC_ARM_REG_SP, 0xC1800000)
        a.uc.emu_start(a.symbols["DG_GetKey"], 0xFFFFFFFF, count=100000)
        self.assertFalse(a.powered)
        self.assertEqual(a.calls[-1][0], 0xC001734C)
        self.assertEqual(a.calls[-1][1][:2], [0x01E26000, 1])

    def test_error_idle_still_accepts_native_power_button(self):
        a = self.arm
        a.messages = [[6, 0, 0, 0, 0], [6, 1, 0, 0, 0]]
        a.uc.reg_write(UC_ARM_REG_R0, 0xFFFFFFFF)
        a.uc.reg_write(UC_ARM_REG_SP, 0xC1800000)
        a.uc.emu_start(a.symbols["_exit"], 0xFFFFFFFF, count=100000)
        self.assertFalse(a.powered)
        self.assertEqual(a.word(SHARED + 8), 0x80000000)
        self.assertEqual(a.word(SHARED + 12), 0xFFFFFFFF)
        self.assertEqual(a.calls[-1][0], 0xC001734C)
        self.assertEqual(a.calls[-1][1][:2], [0x01E26000, 1])

    def test_dark_scene_contours_use_the_display_contrast(self):
        a = self.arm
        pixels = a.symbols["__heap_start"]
        image = b"".join(struct.pack("<I", 0x181818 if x < 160 else 0x484848)
                         for y in range(200) for x in range(320))
        a.uc.mem_write(pixels, image)
        a.word(a.symbols["DG_ScreenBuffer"], pixels)
        a.call("DG_DrawFrame", count=3000000)
        frame = bytes(a.uc.mem_read(0xC031B310, 1024))
        dark = sum(frame[y * 128 + x].bit_count() for y in range(8) for x in range(48))
        light = sum(frame[y * 128 + x].bit_count() for y in range(8) for x in range(80, 128))
        self.assertGreater(dark - light, 500)
        self.assertGreater(light, 0)
        self.assertLess(dark, 48 * 64)

    def test_source_pixels_between_old_sample_points_affect_the_display(self):
        a = self.arm
        pixels = a.symbols["__heap_start"]
        image = bytearray(struct.pack("<I", 0x787878) * (320 * 200))
        a.uc.mem_write(pixels, bytes(image))
        a.word(a.symbols["DG_ScreenBuffer"], pixels)
        a.call("DG_DrawFrame", count=3000000)
        before = bytes(a.uc.mem_read(0xC031B310, 1024))
        for y in range(200):
            struct.pack_into("<I", image, (y * 320 + 1) * 4, 0xFFFFFF)
        a.uc.mem_write(pixels, bytes(image))
        a.call("DG_DrawFrame", count=3000000)
        after = bytes(a.uc.mem_read(0xC031B310, 1024))
        self.assertNotEqual(before, after)
        a.call("DG_DrawFrame", count=3000000)
        self.assertEqual(bytes(a.uc.mem_read(0xC031B310, 1024)), after)
        image = bytearray(struct.pack("<I", 0x787878) * (320 * 200))
        image[320 * 4:640 * 4] = struct.pack("<I", 0xFFFFFF) * 320
        a.uc.mem_write(pixels, bytes(image))
        a.call("DG_DrawFrame", count=3000000)
        self.assertNotEqual(bytes(a.uc.mem_read(0xC031B310, 1024)), before)

    def test_display_conversion_preserves_source_and_stack_guards(self):
        a = self.arm
        pixels = a.symbols["__heap_start"]
        image = bytes(range(256)) * 1000
        a.uc.mem_write(pixels, image)
        a.uc.mem_write(pixels - 32, b"\xa6" * 32)
        a.uc.mem_write(pixels + len(image), b"\x5a" * 32)
        a.uc.mem_write(0xC1800000 - 16384, b"\x93" * 32)
        a.word(a.symbols["DG_ScreenBuffer"], pixels)
        reads = []
        a.uc.hook_add(UC_HOOK_MEM_READ, lambda uc, kind, at, size, value, data: reads.append((at, size)),
                      begin=pixels, end=pixels + len(image) - 1)
        a.call("DG_DrawFrame", count=3000000)
        self.assertEqual(sorted(reads), [(pixels + i * 4, 4) for i in range(320 * 200)])
        self.assertEqual(bytes(a.uc.mem_read(pixels, len(image))), image)
        self.assertEqual(bytes(a.uc.mem_read(pixels - 32, 32)), b"\xa6" * 32)
        self.assertEqual(bytes(a.uc.mem_read(pixels + len(image), 32)), b"\x5a" * 32)
        self.assertEqual(bytes(a.uc.mem_read(0xC1800000 - 16384, 32)), b"\x93" * 32)

    def test_display_conversion_calls_both_native_spi_halves(self):
        a = self.arm
        pixels = a.symbols["__heap_start"]
        a.uc.mem_write(pixels, b"\xff\xff\xff\x00" * (320 * 200))
        a.word(a.symbols["DG_ScreenBuffer"], pixels)
        a.call("DG_DrawFrame", count=3000000)
        self.assertEqual(bytes(a.uc.mem_read(0xC031B310, 1024)), bytes(1024))
        self.assertEqual([(at, regs[:3]) for at, regs in a.calls], [(0xC0015DD0, [0xC031BB2C, 2, 0]), (0xC0015DD0, [0xC031BB2C, 3, 0])])
        self.assertEqual(a.word(SHARED + 16), 1)
        a.uc.mem_write(pixels, bytes(320 * 200 * 4))
        a.call("DG_DrawFrame", count=3000000)
        self.assertEqual(bytes(a.uc.mem_read(0xC031B310, 1024)), bytes([255]) * 1024)
        self.assertEqual(a.word(SHARED + 16), 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BUILD = args.build
    unittest.main(argv=[__file__, *remaining])
