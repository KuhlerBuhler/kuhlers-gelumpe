# SPDX-License-Identifier: GPL-2.0-only
"""The emulated Electribe's flash as one file that outlives the service, like the chip in the device.

Patterns, globals and the user-data mark live in the flash. The emulator boots from this
file and every change the firmware makes to the flash is written back, so what a pattern
import or WRITE stores is there after a restart. The file holds user data and stays out of
the repository: ~/.gelumpe/flash/flash.bin, or GELUMPE_FLASH_DIR, or --flash-dir. Without a
file the emulator starts from an erased flash that the firmware initialises itself
(machine.blank_flash).
"""

import os
from pathlib import Path

FLASH_SIZE = 0x1000000


class FlashError(Exception):
    """The flash file cannot be used; the message is for the user."""


def default_dir(sd_root=None):
    env = os.environ.get("GELUMPE_FLASH_DIR")
    if env:
        return Path(env)
    return (Path(sd_root).parent if sd_root else Path.home() / ".gelumpe") / "flash"


class FlashStore:
    def __init__(self, folder, name="flash.bin"):
        self.dir = Path(folder)
        self.path = self.dir / name
        self.dir.mkdir(parents=True, exist_ok=True)

    def other(self, name):
        """The store of another file in the same folder (the synth's user data is not the Sampler's)."""
        return FlashStore(self.dir, name)

    def load(self):
        """The saved flash, or None when there is none yet (the emulator then starts from an erased one)."""
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            return None
        if len(data) != FLASH_SIZE:
            raise FlashError(f"Die Flash-Datei {self.path} hat {len(data)} Byte, ein Flash hat {FLASH_SIZE}. "
                             "Sie wird nicht überschrieben; verschiebe sie, dann startet ein leerer Flash.")
        return data

    def save(self, mem):
        """Write the flash back whole: to a temporary file, flushed, then renamed over the old one."""
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(mem)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
