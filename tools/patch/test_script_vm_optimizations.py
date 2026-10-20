"""Native arithmetic semantics and instruction budgets on synthetic inputs."""
import itertools
import pathlib
import random
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.patch.test_script_vm import (
    BareMachine, UNICORN_AVAILABLE, blob, contract_data, runtime_code,
)


def multiplication_pairs():
    edges = sorted({0, 1, -1, -(1 << 31), (1 << 31) - 1,
                    *(sign * (1 << bit) + delta for sign in (-1, 1)
                      for bit in (1, 7, 15, 23, 30) for delta in (-1, 0, 1))})
    pairs = list(itertools.product(edges, repeat=2))
    rng = random.Random(0xB1EC)
    while len(pairs) < 2225:
        pairs.append((rng.randrange(-(1 << 31), 1 << 31),
                      rng.randrange(-(1 << 31), 1 << 31)))
    return pairs


def measure_multiply(code):
    from unicorn import UC_HOOK_CODE
    op = contract_data()['op']
    machine = BareMachine(code)
    program = [op['HALT'], op['LOAD'], 0, 0, op['LOAD'], 1, 0,
               op['MUL'], op['STORE'], 2, 0, op['HALT']]
    event = next(e['id'] for e in contract_data()['events'] if e['name'] == 'frame')
    error, entry = machine.load(blob(program, vars=3, stack=2, handlers=[(event, 0, 1)]))
    if error:
        raise AssertionError(f'multiply program rejected: {error}')
    if machine.run(entry, 0):
        raise AssertionError('multiply program did not start')
    variables = machine.read(entry + code.symbols['SCRIPT_ENTRY_VARS'])
    counts = []
    handler_counts = []
    active = False
    count = handler_count = 0

    def count_instruction(_uc, address, _size, _data):
        nonlocal active, count, handler_count
        count += 1
        if address == code.symbols['op_mul']:
            active = True
        if address == code.symbols['run_next']:
            active = False
        if active:
            handler_count += 1

    hook = machine.uc.hook_add(UC_HOOK_CODE, count_instruction)
    try:
        for a, b in multiplication_pairs():
            machine.uc.mem_write(variables, struct.pack('<iiI', a, b, 0xDEADBEEF))
            active = False
            count = handler_count = 0
            if machine.run(entry, event):
                raise AssertionError(f'multiply failed for {a}, {b}')
            actual = machine.variables(entry)
            expected = ((a * b + (1 << 31)) % (1 << 32)) - (1 << 31)
            if actual != [a, b, expected]:
                raise AssertionError(f'{a} * {b}: {actual}, expected {expected}')
            counts.append(count)
            handler_counts.append(handler_count)
    finally:
        machine.uc.hook_del(hook)
    return {'pairs': len(counts), 'meanInstructions': sum(counts) / len(counts),
            'maxHandlerInstructions': max(handler_counts),
            'resultsMatch': True, 'vmCodeBytes': len(code.bytes)}


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native ARM tests')
class NativeOptimizationTests(unittest.TestCase):
    def test_multiply_wraps_signed_i32_without_a_data_dependent_loop(self):
        result = measure_multiply(runtime_code())
        self.assertEqual(result['pairs'], 2225)
        self.assertTrue(result['resultsMatch'])
        self.assertLessEqual(result['maxHandlerInstructions'], 10)


if __name__ == '__main__':
    unittest.main()
