# SPDX-License-Identifier: GPL-2.0-only
"""The flash file: blank start, write-back of the firmware's changes, and what a restart finds."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flashstore import FLASH_SIZE, FlashError, FlashStore, default_dir  # noqa: E402
from machine import Flash  # noqa: E402
from server import Emulator, VSB_SIZE  # noqa: E402
from test_server import FakeMachine  # noqa: E402


class FlashMachine(FakeMachine):
    """A stand-in that keeps the flash it was given and changes it the way the firmware does."""

    def __init__(self, payload, flash):
        super().__init__(payload, flash)
        self.flash = Flash(flash)

    def run_until(self, seconds):
        super().run_until(seconds)
        if self.steps == 3:
            self.flash.mem[0x300000:0x300008] = b"PERSIST6"
            self.flash.dirty = True


class FlashTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FlashStore(Path(self.tmp.name) / "flash")
        self.machines = []

    def tearDown(self):
        self.tmp.cleanup()

    def emulator(self):
        def factory(payload, flash):
            m = FlashMachine(payload, flash)
            self.machines.append(m)
            return m

        emu = Emulator(factory, flash_store=self.store)
        emu.load_firmware(bytes(VSB_SIZE))
        return emu

    def run_a_while(self, emu, n=0):
        emu.start()
        deadline = time.monotonic() + 5
        while self.machines[n].steps < 5 and time.monotonic() < deadline:
            time.sleep(0.02)

    def test_without_a_file_the_device_starts_erased_and_nothing_is_written_until_the_firmware_changes_it(self):
        emu = self.emulator()
        self.run_a_while(emu)
        self.assertEqual(self.machines[0].flash.mem[0x220000:0x22000C], b"KORGele2sUSR", "the blank flash carries the user-data mark")
        emu.stop()
        self.assertEqual(self.store.path.read_bytes()[0x300000:0x300008], b"PERSIST6", "stopping writes the changes back")
        self.assertEqual(self.store.path.stat().st_size, FLASH_SIZE)

    def test_a_restart_boots_from_what_the_firmware_wrote(self):
        emu = self.emulator()
        self.run_a_while(emu)
        emu.stop()
        again = self.emulator()
        again.start()
        self.assertEqual(self.machines[1].flash.mem[0x300000:0x300008], b"PERSIST6")
        again.stop()

    def test_changes_are_written_while_the_device_runs(self):
        emu = self.emulator()
        emu.start()
        deadline = time.monotonic() + 8
        while not self.store.path.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertTrue(self.store.path.exists())
        emu.stop()

    def test_a_flash_file_of_the_wrong_size_is_refused_and_left_alone(self):
        self.store.path.write_bytes(b"short")
        emu = self.emulator()
        with self.assertRaises(ValueError) as e:
            emu.start()
        self.assertIn("Flash-Datei", str(e.exception))
        self.assertEqual(self.store.path.read_bytes(), b"short")
        with self.assertRaises(FlashError):
            self.store.load()

    def test_the_synth_keeps_its_user_data_in_a_file_of_its_own(self):
        emu = self.emulator()
        emu.build = "synth"          # what identify says of the blue Electribe's image
        self.run_a_while(emu)
        emu.stop()
        self.assertFalse(self.store.path.exists(), "the Sampler's flash file is left alone")
        own = self.store.path.with_name("flash-synth.bin")
        self.assertEqual(own.read_bytes()[0x300000:0x300008], b"PERSIST6")

    def test_hacktribe_for_the_blue_runs_on_the_blue_flash(self):
        def factory(payload, flash):
            m = FlashMachine(payload, flash)
            self.machines.append(m)
            return m

        blue_head = bytearray(VSB_SIZE)
        blue_head[0x10:0x13] = b"E2\0"
        emu = Emulator(factory, flash_store=self.store)
        emu.load_firmware(bytes(blue_head))
        self.run_a_while(emu)
        emu.stop()
        self.assertEqual(bytes(self.machines[0].flash.mem[0x220000:0x22000C]), b"KORGelec2USR", "a blank start has the blue's mark")
        self.assertFalse(self.store.path.exists(), "the red's flash file is left alone")
        self.assertEqual(self.store.path.with_name("flash-synth.bin").read_bytes()[0x300000:0x300008], b"PERSIST6")

    def test_the_check_takes_the_flash_of_the_hardware_of_the_original(self):
        calls = []
        emu = self.emulator()
        emu.checker = lambda base, patched, flash, allow, allow_code, progress=None: calls.append(flash) or {"ok": True, "checks": []}
        blue_head = bytearray(VSB_SIZE)
        blue_head[0x10:0x13] = b"E2\0"
        emu.check(bytes(blue_head) * 2, [])
        emu.check(bytes(VSB_SIZE) * 2, [])
        self.assertEqual(bytes(calls[0][0x220000:0x22000C]), b"KORGelec2USR")
        self.assertIsNone(calls[1], "a red original keeps the machine's own blank flash")
        self.store.other("flash-synth.bin").save(b"\x01" * FLASH_SIZE)
        emu.check(bytes(blue_head) * 2, [])
        self.assertEqual(calls[2][:4], b"\x01" * 4, "the blue's own flash file when there is one")
        emu.check(bytes(VSB_SIZE) * 2, [], hardware="blue")
        self.assertEqual(calls[3][:4], b"\x01" * 4, "Sampler head on the blue: the page names the hardware")

    def test_the_flash_folder_sits_next_to_the_card_folder(self):
        self.assertEqual(default_dir(Path("/a/b/sd")), Path("/a/b/flash"))


if __name__ == "__main__":
    unittest.main()
