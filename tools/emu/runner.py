# SPDX-License-Identifier: GPL-2.0-only
"""Execute isolated Sampler 2.02 ARM routines from a user's VSB."""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

IMAGE_BASE = 0xC0000000
IMAGE_SIZE = 0x200000
RAM_END = 0xC274F000
HEAP_BASE = 0xC06A2940
HEAP_END = 0xC08A2940
CURSOR = 0xC03404AC
SCRATCH = 0x10000000
RETURN = SCRATCH + 0x1000
STACK = SCRATCH + 0x10000
GROW = 0xC002CEFC
BUFFER = 0xC00369F0


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_vsb(path):
    require(path.stat().st_size == IMAGE_SIZE + 0x100,
            "VSB must contain a 0x100-byte header and 0x200000-byte payload")
    data = path.read_bytes()
    require(len(data) == IMAGE_SIZE + 0x100, "VSB changed while reading")
    return data[0x100:], hashlib.sha256(data).hexdigest()


class Machine:
    def __init__(self, payload):
        import unicorn
        from unicorn import arm_const

        require(unicorn.__version__ == "2.1.4", "Install unicorn==2.1.4")
        self.reg = arm_const
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.cpu.mem_map(IMAGE_BASE, IMAGE_SIZE,
                          unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
        self.cpu.mem_write(IMAGE_BASE, payload)
        self.cpu.mem_map(IMAGE_BASE + IMAGE_SIZE,
                          RAM_END - IMAGE_BASE - IMAGE_SIZE,
                          unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
        self.cpu.mem_map(SCRATCH, 0x10000,
                          unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
        self.writes = []
        self.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, self.record_write)

    def record_write(self, cpu, access, address, size, value, user):
        self.writes.append((address, size))

    def word(self, address):
        return struct.unpack("<I", self.cpu.mem_read(address, 4))[0]

    def set_word(self, address, value):
        self.cpu.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def call(self, entry, argument):
        require(entry in (GROW, BUFFER), "Entry point is not supported")
        self.cpu.reg_write(self.reg.UC_ARM_REG_CPSR, 0xD3)
        self.cpu.reg_write(self.reg.UC_ARM_REG_SP, STACK)
        self.cpu.reg_write(self.reg.UC_ARM_REG_LR, RETURN)
        self.cpu.reg_write(self.reg.UC_ARM_REG_R0, argument & 0xFFFFFFFF)
        self.cpu.emu_start(entry, RETURN, timeout=2_000_000, count=200_000)
        pc = self.cpu.reg_read(self.reg.UC_ARM_REG_PC)
        require(pc == RETURN, f"Routine did not return (PC=0x{pc:08x})")
        for address, size in self.writes:
            output = CURSOR if entry == GROW else SCRATCH
            allowed = output <= address and address + size <= output + 4
            allowed = allowed or STACK - 0x1000 <= address < address + size <= STACK
            require(allowed, f"Unexpected ARM write at 0x{address:08x}")
        return self.cpu.reg_read(self.reg.UC_ARM_REG_R0)


def run(payload, digest):
    cases = [
        ("initialize", 0, 8, HEAP_BASE, HEAP_BASE + 8),
        ("fill-exactly", 0, HEAP_END - HEAP_BASE, HEAP_BASE, HEAP_END),
        ("reject-past-end", HEAP_END, 1, 0, HEAP_END),
        ("grow-from-base", HEAP_BASE, 4096, HEAP_BASE, HEAP_BASE + 4096),
        ("negative-lower-bound-missing", HEAP_BASE, -8, HEAP_BASE, HEAP_BASE - 8),
    ]
    results = []
    for name, cursor, increment, result, after in cases:
        machine = Machine(payload)
        machine.set_word(CURSOR, cursor)
        actual = machine.call(GROW, increment)
        final_cursor = machine.word(CURSOR)
        require(actual == result and final_cursor == after,
                f"{name}: unexpected return or cursor; firmware build may differ")
        results.append({"name": name, "initial_cursor": cursor,
                        "increment": increment, "result": actual,
                        "final_cursor": final_cursor})
    machine = Machine(payload)
    pointer = machine.call(BUFFER, SCRATCH)
    capacity = machine.word(SCRATCH)
    require(pointer == 0xC0D3A940 and capacity == 0x01A00100,
            "Unexpected work buffer; firmware build may differ")
    return {"schema": 1, "suite": "heap-and-buffer", "unicorn": "2.1.4",
            "firmware_sha256": digest, "hardware_contact": False,
            "stubs": [], "initial_state": "VSB payload plus zeroed RAM",
            "cases": results, "buffer": {"address": pointer, "capacity": capacity}}


def main():
    import lifetime
    lifetime.exit_with_parent()      # ends with the test run that started this, also when that is killed
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vsb", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload, digest = load_vsb(args.vsb)
        print(json.dumps(run(payload, digest), sort_keys=True))
    except ImportError:
        print("Install tools/emu/requirements.txt in tools/emu/.venv", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Emulation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
