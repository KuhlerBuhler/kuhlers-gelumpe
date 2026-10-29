# SPDX-License-Identifier: GPL-2.0-only
"""A machine made from a snapshot goes on exactly as the one that was snapshotted (machine.py, bootcache.py).
Needs E2_VSB; skipped without it, a failure when E2_EMU_REQUIRED=1. E2_FLASH is optional."""

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import machine  # noqa: E402

VSB = os.environ.get("E2_VSB")
REQUIRED = os.environ.get("E2_EMU_REQUIRED") == "1"
BOOT, MORE = 1.5, 1.0


def digest(m):
    """Everything an outside check can see: the CPU, the whole RAM, the model's tables, the display."""
    A = m.A
    regs = [m.uc.reg_read(r) for r in [A.UC_ARM_REG_R0 + i for i in range(13)] + [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR, A.UC_ARM_REG_PC, A.UC_ARM_REG_CPSR]]
    h = hashlib.sha256()
    h.update(repr((m.time_ns, m.insns, m.frames, m.screens, len(m.panel_log), sorted(m.leds.items()), regs, sorted(m.regs.items()),
                   sorted(m.enabled), m.asserts, m.dsp_uploads, sorted(m.flash.commands.items()))).encode())
    h.update(bytes(b for row in m.fb for b in row))
    h.update(bytes(m.uc.mem_read(0xC0000000, 0x08000000)))
    h.update(bytes(m.flash.mem))
    card = m.mmc.card
    if card is not None:
        h.update(repr((card.sectors_read, card.sectors_written, sorted(card.commands.items()), card.state, sorted(m.mmc.regs.items()))).encode())
        h.update(bytes(card.medium.data))
    return h.hexdigest()


def card(files=None):
    import fat32
    import sdcard
    clock, fat32.clock = fat32.clock, lambda: 1767225600.0     # the same image every time
    try:
        img = fat32.format_image(64 * 1024 * 1024)
        volume = fat32.Volume(img)
        for path, data in (files or {}).items():
            volume.write(path, data)
        volume.close()
    finally:
        fat32.clock = clock
    return sdcard.SDCard(sdcard.MemoryMedium(img))


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        if not VSB:
            if REQUIRED:
                self.fail("E2_VSB is not set")
            self.skipTest("E2_VSB not set")
        try:
            import unicorn  # noqa: F401
        except ImportError:
            if REQUIRED:
                self.fail("Unicorn is not installed in this Python")
            self.skipTest("Unicorn not installed")
        self.payload = Path(VSB).read_bytes()[0x100:]
        self.flash = machine.load_flash(os.environ["E2_FLASH"].split(os.pathsep)) if os.environ.get("E2_FLASH") else None

    def straight(self, held=0):
        m = machine.Machine(self.payload, self.flash)
        m.held = held
        m.run_until(BOOT + MORE)
        return m

    def test_a_restored_machine_goes_on_as_the_original_would_have(self):
        for held in (0, 0x18000000):
            with self.subTest(held=held):
                m = machine.Machine(self.payload, self.flash)
                m.held = held
                m.run_until(BOOT)
                restored = machine.Machine.from_snapshot(m.snapshot(), self.payload, self.flash)
                restored.run_until(BOOT + MORE)
                self.assertEqual(digest(restored), digest(self.straight(held)))

    def test_stopping_to_take_a_snapshot_changes_nothing(self):
        m = machine.Machine(self.payload, self.flash)
        m.run_until(BOOT)
        m.snapshot()
        m.run_until(BOOT + MORE)
        self.assertEqual(digest(m), digest(self.straight()))

    def test_the_boot_cache_gives_the_same_machine_from_memory_and_from_its_file(self):
        import bootcache
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("GELUMPE_CACHE_DIR")
            old_switch = os.environ.pop("GELUMPE_CACHE", None)      # this test is about the cache, so it runs with it on
            os.environ["GELUMPE_CACHE_DIR"] = folder
            try:
                bootcache._memory.clear()
                first, _ = bootcache.booted(self.payload, self.flash, 0, BOOT)
                self.assertTrue(list((Path(folder) / "boot").iterdir()), "the boot was kept in a file")
                bootcache._memory.clear()
                second, _ = bootcache.booted(self.payload, self.flash, 0, BOOT)      # from the file
                third, _ = bootcache.booted(self.payload, self.flash, 0, BOOT)       # from memory
                self.assertEqual(digest(first), digest(second))
                self.assertEqual(digest(first), digest(third))
                second.run_until(BOOT + MORE)
                self.assertEqual(digest(second), digest(self.straight()))
            finally:
                bootcache._memory.clear()
                if old is None:
                    os.environ.pop("GELUMPE_CACHE_DIR")
                else:
                    os.environ["GELUMPE_CACHE_DIR"] = old
                if old_switch is not None:
                    os.environ["GELUMPE_CACHE"] = old_switch

    def test_a_card_in_the_slot_is_kept_and_goes_on_as_the_original(self):
        files = {"/KORG/blechtribe/Sample/placeholder": b"1"}

        def started():
            m = machine.Machine(self.payload, self.flash)
            m.adapter = True
            m.insert_card(card(files))
            return m

        straight = started()
        straight.run_until(BOOT + MORE)
        m = started()
        before = bytes(m.mmc.card.medium.data)
        m.run_until(BOOT)
        for base in (None, before):
            with self.subTest(card_base=base is not None):
                snap = m.snapshot(card_base=base)
                if base is None:
                    restored = machine.Machine.from_snapshot(snap, self.payload, self.flash)
                else:
                    restored = started()
                    held = restored.mmc.card
                    restored.restore(snap)
                    self.assertIs(restored.mmc.card, held, "the card the caller put in stays the object in the slot")
                restored.run_until(BOOT + MORE)
                self.assertEqual(digest(restored), digest(straight))

    def test_power_on_gives_the_machine_a_run_from_power_on_gives(self):
        import bootcache
        files = {"/KORG/blechtribe/Sample/placeholder": b"1"}

        def started():
            m = machine.Machine(self.payload, self.flash)
            m.adapter = True
            m.insert_card(card(files))
            return m

        straight = started()
        straight.finish_boot()           # Korg's builds load their user data first; the run counts from there
        straight.run_until(straight.time_ns / 1e9 + BOOT)
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get("GELUMPE_CACHE_DIR")
            old_switch = os.environ.pop("GELUMPE_CACHE", None)
            os.environ["GELUMPE_CACHE_DIR"] = folder
            try:
                bootcache._memory.clear()
                first = started()
                bootcache.power_on(first, BOOT)
                self.assertTrue(list((Path(folder) / "power-on").iterdir()), "the run was kept in a file")
                bootcache._memory.clear()
                second = started()
                bootcache.power_on(second, BOOT)       # from the file
                third = started()
                bootcache.power_on(third, BOOT)        # from memory
                for m in (first, second, third):
                    self.assertEqual(digest(m), digest(straight))
                for m in (second, straight):
                    m.press(0x09, True)
                    m.run_until(m.time_ns / 1e9 + 0.05)
                    m.press(0x09, False)
                    m.run_until(m.time_ns / 1e9 + MORE)
                self.assertEqual(digest(second), digest(straight))
                watched = started()
                watched.uc.hook_add(__import__("unicorn").UC_HOOK_CODE, lambda *a: None, begin=0, end=0)
                self.assertIsNone(bootcache._power_on_key(watched, "1.5"), "a hook someone added has to see the run")
            finally:
                bootcache._memory.clear()
                if old is None:
                    os.environ.pop("GELUMPE_CACHE_DIR")
                else:
                    os.environ["GELUMPE_CACHE_DIR"] = old
                if old_switch is not None:
                    os.environ["GELUMPE_CACHE"] = old_switch

    def test_a_card_on_a_folder_of_the_host_cannot_be_snapshotted(self):
        import sdcard

        class Folder(sdcard.MemoryMedium):
            pass

        m = machine.Machine(self.payload, self.flash)
        m.insert_card(sdcard.SDCard(Folder(bytearray(512 * 64))))
        with self.assertRaises(ValueError):
            m.snapshot()


if __name__ == "__main__":
    unittest.main()
