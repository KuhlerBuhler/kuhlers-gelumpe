"""Native operand and arithmetic semantics on synthetic inputs."""
import hashlib
import itertools
import json
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


def decoder_vectors():
    edges = (0, 1, 0x7f, 0x80, 0xff, 0x100, 0x7fff, 0x8000, 0xffff)
    for opcode in contract_data()['opcodes']:
        values = itertools.product(edges, repeat=max(1, len(opcode['operands'])))
        for operands in values:
            encoded = bytes([opcode['code']])
            expected = []
            for operand, value in zip(opcode['operands'], operands):
                value &= (1 << (operand['size'] * 8)) - 1
                encoded += value.to_bytes(operand['size'], 'little')
                expected.append(value)
            for alignment in range(4):
                yield opcode, operands, alignment, encoded, (expected + [0, 0])[:2]


def measure_decoder(code):
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn import arm_const as arm
    machine = BareMachine(code)
    table = code.symbols['script_op_operands']
    frame = machine.input + 32
    count = writes = 0
    reads = []
    vectors, results, counts = [], [], []

    def instruction(_uc, _address, _size, _data):
        nonlocal count
        count += 1

    def memory(_uc, access, address, size, _value, _data):
        nonlocal writes
        from unicorn import UC_MEM_WRITE
        if access == UC_MEM_WRITE:
            writes += 1
            if not machine.stack <= address < machine.stack + 0x100000:
                raise AssertionError('decoder wrote outside the stack')
        elif machine.input <= address < machine.input + 0x100000 or table <= address < table + 512:
            reads.append((address, size))

    hooks = [machine.uc.hook_add(UC_HOOK_CODE, instruction),
             machine.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory)]
    saved = [(getattr(arm, f'UC_ARM_REG_R{i}'), 0x13570000 + i * 0x1111) for i in range(4, 12)]
    try:
        for opcode, operands, alignment, encoded, expected in decoder_vectors():
            address = frame + 16 + alignment
            guarded = bytearray(b'\xa5' * 64)
            guarded[16 + alignment:16 + alignment + len(encoded)] = encoded
            machine.uc.mem_write(frame, bytes(guarded))
            for register, value in saved:
                machine.uc.reg_write(register, value)
            count = 0
            reads.clear()
            actual = machine.call('decode_operands', address, opcode['code'])
            if list(actual) != expected:
                raise AssertionError(f"{opcode['name']}/{alignment}/{operands}: {actual} != {expected}")
            if any(machine.uc.reg_read(register) != value for register, value in saved):
                raise AssertionError('decoder changed a callee-saved register')
            if machine.uc.reg_read(arm.UC_ARM_REG_SP) != machine.stack + 0xf0000:
                raise AssertionError('decoder changed the stack pointer')
            if machine.uc.reg_read(arm.UC_ARM_REG_LR) != machine.stop:
                raise AssertionError('decoder changed the return address')
            if bytes(machine.uc.mem_read(frame, 64)) != guarded:
                raise AssertionError('decoder changed the guarded input')
            expected_reads = [(table + opcode['code'] * 2 + i, 1) for i in range(2)]
            expected_reads += [(address + i, 1) for i in range(1, len(encoded))]
            if sorted(reads) != sorted(expected_reads):
                raise AssertionError(f"{opcode['name']}: unexpected input or table reads {reads}")
            vectors.append([opcode['code'], list(operands), alignment, encoded.hex()])
            results.append(list(actual))
            counts.append(count)
    finally:
        for hook in hooks:
            machine.uc.hook_del(hook)
    return {'opcodes': len(contract_data()['opcodes']), 'vectors': len(vectors),
            'vectorsSha256': hashlib.sha256(json.dumps(vectors).encode()).hexdigest(),
            'resultsSha256': hashlib.sha256(json.dumps(results).encode()).hexdigest(),
            'meanInstructions': sum(counts) / len(counts), 'maxInstructions': max(counts),
            'memoryWrites': writes, 'vmCodeBytes': len(code.bytes),
            'decoderCodeBytes': code.symbols['set_sections'] - code.symbols['decode_operands'],
            'resultsMatch': True}


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native ARM tests')
class NativeDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = measure_decoder(runtime_code())

    def test_all_operands_preserve_values_registers_and_byte_accesses(self):
        self.assertGreaterEqual(self.result['vectors'], len(contract_data()['opcodes']) * 9 * 4)
        self.assertGreaterEqual(self.result['vectors'], 1224)
        self.assertTrue(self.result['resultsMatch'])

    def test_decoder_uses_no_stack_or_other_memory_writes(self):
        self.assertEqual(self.result['memoryWrites'], 0)

    def test_native_loader_rejects_each_truncated_operand_and_unknown_opcode(self):
        machine = BareMachine(runtime_code())
        errors = contract_data()['error']
        for opcode in contract_data()['opcodes']:
            for length in range(1, opcode['size']):
                with self.subTest(opcode=opcode['name'], length=length):
                    self.assertEqual(machine.load(blob([opcode['code']] + [0] * (length - 1)))[0], errors['TRUNCATED'])
        valid = {opcode['code'] for opcode in contract_data()['opcodes']}
        for opcode in range(256):
            if opcode not in valid:
                with self.subTest(opcode=opcode):
                    self.assertEqual(machine.load(blob([opcode]))[0], errors['BAD_OPCODE'])


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native ARM tests')
class NativeOptimizationTests(unittest.TestCase):
    def test_multiply_wraps_signed_i32_without_a_data_dependent_loop(self):
        result = measure_multiply(runtime_code())
        self.assertEqual(result['pairs'], 2225)
        self.assertTrue(result['resultsMatch'])
        self.assertLessEqual(result['maxHandlerInstructions'], 10)


if __name__ == '__main__':
    unittest.main()
