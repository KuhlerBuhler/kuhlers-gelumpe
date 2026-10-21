"""Native validator bounds and reuse checks with synthetic script blocks."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.patch.test_script_vm import BareMachine, UNICORN_AVAILABLE, blob, contract_data, runtime_code

if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_R4, UC_ARM_REG_SP


@unittest.skipUnless(UNICORN_AVAILABLE, "Unicorn is required for native ARM tests")
class ValidatorBoundsTests(unittest.TestCase):
    def regions(self, machine):
        for name in ("BOUNDARIES", "ARGC", "FNSTATE", "NEED", "DEEP", "DEPTH", "WORK"):
            width = 4 if name == "WORK" else 1
            yield name, machine.runtime + machine.symbols["RT_" + name], width

    def checked_load(self, machine, data, length, expected):
        limit = machine.symbols["LIM_CODE"]
        regions = list(self.regions(machine))
        for _, address, width in regions:
            machine.uc.mem_write(address, b"\xa5" * (limit * width))
        used = machine.read(machine.runtime + 16)
        old_entries = bytes(machine.uc.mem_read(machine.arena, used))
        old_links = bytes(machine.uc.mem_read(machine.runtime, 8))
        for n in range(8):
            machine.uc.reg_write(UC_ARM_REG_R4 + n, 0x13570000 + n)
        control = machine.uc.reg_read(UC_ARM_REG_CPSR) & 0x1ff
        outside = []

        def access(_uc, kind, address, size, _value, _data):
            for name, start, width in regions:
                if start <= address < start + limit * width:
                    if address + size > start + length * width and len(outside) < 8:
                        outside.append((name, kind, address - start, size))
                    break

        hook = machine.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, access,
                                   begin=regions[0][1], end=machine.runtime + machine.symbols["RT_RING"] - 1)
        try:
            result, entry = machine.load(data)
        finally:
            machine.uc.hook_del(hook)
        self.assertEqual(result, expected)
        self.assertFalse(outside, outside)
        for _, address, width in regions:
            self.assertEqual(bytes(machine.uc.mem_read(address + length * width, (limit - length) * width)),
                             b"\xa5" * ((limit - length) * width))
        self.assertEqual([machine.uc.reg_read(UC_ARM_REG_R4 + n) for n in range(8)],
                         [0x13570000 + n for n in range(8)])
        self.assertEqual(machine.uc.reg_read(UC_ARM_REG_SP), machine.stack + 0xF0000)
        self.assertEqual(machine.uc.reg_read(UC_ARM_REG_CPSR) & 0x1ff, control)
        if result:
            self.assertEqual(machine.read(machine.runtime + 16), used)
            self.assertEqual(bytes(machine.uc.mem_read(machine.arena, used)), old_entries)
            self.assertEqual(bytes(machine.uc.mem_read(machine.runtime, 8)), old_links)
        return result, entry

    def test_short_loader_instruction_budget(self):
        machine = BareMachine(runtime_code())
        count = [0]
        hook = machine.uc.hook_add(UC_HOOK_CODE, lambda *_: count.__setitem__(0, count[0] + 1))
        try:
            self.assertEqual(machine.load(blob([0]))[0], 0)
        finally:
            machine.uc.hook_del(hook)
        self.assertLess(count[0], 20000, count[0])

    def test_runtime_initialization_still_clears_all_scratch(self):
        machine = BareMachine(runtime_code())
        for _, address, width in self.regions(machine):
            machine.uc.mem_write(address, b"\xa5" * (machine.symbols["LIM_CODE"] * width))
        self.assertEqual(machine.call("script_runtime_init", machine.runtime, machine.arena, 131072)[0], 0)
        for _, address, width in self.regions(machine):
            self.assertEqual(bytes(machine.uc.mem_read(address, machine.symbols["LIM_CODE"] * width)),
                             bytes(machine.symbols["LIM_CODE"] * width))

    def test_dirty_long_short_failure_and_long_loads(self):
        machine = BareMachine(runtime_code())
        op = contract_data()["op"]
        error = contract_data()["error"]
        long_code = [op["PUSHB"], 1, op["DROP"]] * 200 + [op["HALT"]]
        cases = [(long_code, 1, 0), ([op["HALT"]], 0, 0),
                 ([op["JMP"], 1, 0], 0, error["BAD_JUMP"]),
                 ([op["CALL"], 6, 0, 0, op["DROP"], op["HALT"], op["PUSHB"], 7, op["RET"]], 1, 0),
                 ([op["PUSHB"], 1], 1, error["BAD_JUMP"]),
                 ([op["HALT"]], 0, 0), (long_code, 1, 0)]
        for code, stack, expected in cases:
            with self.subTest(code_length=len(code), expected=expected):
                _, entry = self.checked_load(machine, blob(code, stack=stack), len(code), expected)
                if not expected:
                    self.assertEqual(machine.run(entry, 0), 0)

    def test_empty_maximum_and_over_limit(self):
        machine = BareMachine(runtime_code(), {"arenaSize": 900000})
        limit = machine.symbols["LIM_CODE"]
        self.checked_load(machine, blob([]), 0, contract_data()["error"]["BAD_JUMP"])
        code = [1, 0, 9] * ((limit - 1) // 3) + [0]
        self.assertEqual(len(code), limit)
        self.checked_load(machine, blob(code, stack=1), limit, 0)
        self.checked_load(machine, blob(code + [0], stack=1), 0, contract_data()["error"]["LIMITS"])

    def test_handler_and_line_boundaries_ignore_old_markers(self):
        machine = BareMachine(runtime_code())
        error = contract_data()["error"]
        code = [0]
        for handlers, lines, expected in [([], [], 0), ([(1, 0, 0)], [], 0),
                                         ([(1, 0, 1)], [], error["BAD_HANDLER"]),
                                         ([], [(0, 1)], 0), ([], [(1, 1)], error["BAD_LINES"])]:
            with self.subTest(handlers=handlers, lines=lines):
                self.checked_load(machine, blob(code, handlers=handlers, lines=lines), 1, expected)

    def test_branch_worklists_and_nested_function_restarts(self):
        machine = BareMachine(runtime_code())
        code = [1, 1, 29, 7, 0, 0, 0, 0]
        self.checked_load(machine, blob(code, stack=1), len(code), 0)
        code = [31, 6, 0, 0, 9, 0, 31, 11, 0, 0, 32, 1, 7, 32]
        self.checked_load(machine, blob(code, stack=1), len(code), 0)
        self.checked_load(machine, blob([31, 0, 0, 0, 9, 0], stack=1), 6,
                          contract_data()["error"]["RECURSION"])

    def test_invalid_streams_and_full_pool_leave_old_entries_unchanged(self):
        machine = BareMachine(runtime_code())
        error = contract_data()["error"]
        _, previous_entry = self.checked_load(machine, blob([1, 42, 5, 0, 0, 0], vars=1, stack=1), 6, 0)
        for data, length, expected in [(blob([255]), 1, error["BAD_OPCODE"]),
                                       (blob([4, 0], vars=1), 2, error["TRUNCATED"]),
                                       (blob([28, 3, 0]), 3, error["BAD_JUMP"]),
                                       (blob([1, 1, 29, 1, 0, 0], stack=1), 6, error["BAD_JUMP"]),
                                       (blob([0])[:-1], 0, error["TRUNCATED"])]:
            with self.subTest(expected=expected, length=length):
                self.checked_load(machine, data, length, expected)
                self.assertEqual(machine.run(previous_entry, 0), 0)
                self.assertEqual(machine.variables(previous_entry), [42])
        machine.write(machine.runtime + 12, machine.read(machine.runtime + 16))
        self.checked_load(machine, blob([0]), 1, error["POOL_BUDGET"])


if __name__ == "__main__":
    unittest.main()
