"""Native helper contracts with synthetic inputs and independent results."""
import random
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from tools.patch import arm, tap_motion
from tools.patch.test_script_vm import BareMachine, contract_data, runtime_code, UNICORN_AVAILABLE

if UNICORN_AVAILABLE:
    from unicorn.arm_const import *
    from tools.emu.patch_performance import BlockCounter


@unittest.skipUnless(UNICORN_AVAILABLE, 'Unicorn is required for native ARM tests')
class NativeHelpers(unittest.TestCase):
    def setUp(self):
        self.m = BareMachine(runtime_code())
        self.counter = BlockCounter(self.m.uc)

    def seed(self, flags=0):
        for r in range(13):
            self.m.uc.reg_write(UC_ARM_REG_R0+r, 0xABC00000+r)
        cpsr = self.m.uc.reg_read(UC_ARM_REG_CPSR)
        self.m.uc.reg_write(UC_ARM_REG_CPSR, (cpsr & 0x0FFFFFFF) | flags << 28)

    def test_streaming_crc_results_registers_flags_and_read_bounds(self):
        from unicorn import UC_HOOK_MEM_READ
        m = self.m
        reads = []
        hook = m.uc.hook_add(UC_HOOK_MEM_READ, lambda u,a,p,s,v,d: reads.append((p,s)),
                             begin=m.input, end=m.input+0xFFFFF)
        for n in [0,1,2,3,7,16,255,1024,4096,32768]:
            data = bytes((i*37+11) & 255 for i in range(n))
            for alignment in range(4):
                for initial in [0,0xFFFFFFFF,0x12345678]:
                    with self.subTest(n=n, alignment=alignment, initial=initial):
                        start = m.input+64+alignment
                        m.uc.mem_write(m.input, b'\xA7'*64+bytes(alignment)+data+b'\xB6'*64)
                        self.seed()
                        reads.clear()
                        m.call('crc_update', start, n, initial)
                        expected = zlib.crc32(data, initial ^ 0xFFFFFFFF) ^ 0xFFFFFFFF
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R2), expected)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0), start+n)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R1), start+n)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R3),0 if n else 0xABC00003)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R12),0xEDB88320)
                        self.assertTrue(all(start <= p and p+s <= start+n for p,s in reads))
                        for r in range(4,12):
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0+r),0xABC00000+r)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR) >> 28, 6)
                        self.assertEqual(bytes(m.uc.mem_read(start,n)),data)
        m.uc.hook_del(hook)

    def test_crc_split_with_empty_chunks(self):
        m = self.m
        data = bytes((i*91+19) & 255 for i in range(4096))
        m.uc.mem_write(m.input,data)
        state,offset = 0xFFFFFFFF,0
        for n in [0,1,0,3,1024,0,3068,0]:
            m.call('crc_update',m.input+offset,n,state)
            state = m.uc.reg_read(UC_ARM_REG_R2)
            offset += n
        self.assertEqual(offset,len(data))
        self.assertEqual(state ^ 0xFFFFFFFF,zlib.crc32(data))

    def test_card_adapter_preserves_state_registers_and_stack_on_all_builds(self):
        from unicorn import UC_HOOK_MEM_WRITE
        from tools.patch.script_hooks import build
        m = self.m
        m.uc.mem_map(0xC0000000,0x200000)
        state = m.input+0x80000
        top = m.stack+0xF0000
        writes = []
        hook = m.uc.hook_add(UC_HOOK_MEM_WRITE, lambda u,a,p,s,v,d: writes.append((p,s)))
        try:
            for firmware in ['hacktribe','stock','synth']:
                built = build(contract_data()['include'],build=firmware)
                for at,data in built.sections:
                    m.uc.mem_write(at,data)
                m.uc.ctl_flush_tb()
                m.symbols['card_adapter'] = built.symbols['card_crc']
                crc_word = state+built.symbols['CARD_CRC']
                for n in [0,1,16,4096]:
                    data = bytes((i*37+11)&255 for i in range(n))
                    for alignment in range(4):
                        for initial in [0,0xFFFFFFFF,0x12345678]:
                            self.seed()
                            m.uc.reg_write(UC_ARM_REG_R5,state)
                            start = m.input+64+alignment
                            m.uc.mem_write(start,data or b'\xA7')
                            m.write(crc_word,initial)
                            writes.clear()
                            m.call('card_adapter',start,n)
                            expected = zlib.crc32(data,initial ^ 0xFFFFFFFF) ^ 0xFFFFFFFF
                            self.assertEqual(m.read(crc_word),expected)
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_R2),expected)
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0),start+n)
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_R1),start+n)
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_SP),top)
                            for r in range(4,12):
                                self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0+r),state if r==5 else 0xABC00000+r)
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR) >> 28,6)
                            for address,size in writes:
                                saved = top-8 <= address and address+size <= top
                                self.assertTrue(saved or address==crc_word and size==4)
        finally:
            m.uc.hook_del(hook)

    def test_fill_all_alignments_tails_registers_flags_and_guards(self):
        m = self.m
        for n in list(range(40))+[63,64,65,255,256,4096,163840]:
            for alignment in range(4):
                for value in [0,0x55,0xFF,0x123]:
                    with self.subTest(n=n, alignment=alignment, value=value):
                        self.seed(15)
                        start = m.input+64+alignment
                        m.uc.mem_write(m.input,b'\xA7'*(n+132))
                        m.call('mem_fill',start,value,n)
                        expected = b'\xA7'*(64+alignment)+bytes([value & 255])*n+b'\xA7'*(68-alignment)
                        self.assertEqual(bytes(m.uc.mem_read(m.input,n+132)),expected)
                        for r in range(3,13):
                            self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0+r),0xABC00000+r)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R0),start+n)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R1),value)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_R2),0)
                        self.assertEqual(m.uc.reg_read(UC_ARM_REG_CPSR) >> 28,6)

    def test_fill_large_buffer_uses_fewer_instructions(self):
        _,count = self.counter.measure(lambda:self.m.call('mem_fill',self.m.input,0,163840))
        self.assertLess(count,163840)

    def test_fill_writes_only_buffer_and_saved_scratch_word(self):
        from unicorn import UC_HOOK_MEM_WRITE
        m = self.m
        writes = []
        hook = m.uc.hook_add(UC_HOOK_MEM_WRITE, lambda u,a,p,s,v,d: writes.append((p,s)))
        try:
            for n in [0,1,15,16,17,31,32,33,255,4096]:
                for alignment in range(4):
                    start = m.input+64+alignment
                    writes.clear()
                    m.call('mem_fill',start,0x123,n)
                    for address,size in writes:
                        stack_word = address == m.stack+0xF0000-4 and size == 4
                        self.assertTrue(stack_word or start <= address and address+size <= start+n)
                        if size == 4:
                            self.assertEqual(address % 4,0)
        finally:
            m.uc.hook_del(hook)

    def test_tap_part_mla_preserves_full_register_and_flag_result(self):
        m = self.m
        source = tap_motion.source().split('tk_part:\n',1)[1].split('tk_blink:',1)[0]
        source = source[source.index('    mov r1, #0x330'):].split('    ldrb r6',1)[0]
        new = arm.assemble(source+'\nbx lr', origin=0x810000)
        old = arm.assemble('mov r1, #0x330\nmul r2, r0, r1\nadd r2, r4, r2\nbx lr',origin=0x800000)
        for name,code in [('old',old),('new',new)]:
            m.uc.mem_write(code.origin,code.bytes)
            m.symbols[name] = code.origin
        rng = random.Random(0xB1EC)
        pairs = [(n,0xC0100000) for n in range(16)]
        pairs += [(a,b) for a in [0,1,0x7FFFFFFF,0x80000000,0xFFFFFFFF]
                  for b in [0,1,0x7FFFFFFF,0x80000000,0xFFFFFFFF]]
        pairs += [(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(2209)]
        for i,(a,base) in enumerate(pairs):
            snapshots = []
            for name in ['old','new']:
                self.seed(i % 16)
                m.uc.reg_write(UC_ARM_REG_R4,base)
                _,count = self.counter.measure(lambda:m.call(name,a))
                snapshots.append(([m.uc.reg_read(UC_ARM_REG_R0+r) for r in range(13)],
                                  m.uc.reg_read(UC_ARM_REG_CPSR),count))
            self.assertEqual(snapshots[0][:2],snapshots[1][:2])
            self.assertEqual(snapshots[1][0][2],(a*0x330+base)&0xFFFFFFFF)
            self.assertLess(snapshots[1][2],snapshots[0][2])
        self.assertEqual(len(old.bytes)-len(new.bytes),4)

    def test_mla_variable_factors_match_every_register_and_flag(self):
        m = self.m
        rng = random.Random(0xC0DE)
        edges = [0,1,0x7FFFFFFF,0x80000000,0xFFFFFFFF]
        triples = [(a,b,c) for a in edges for b in edges for c in edges]
        triples += [tuple(rng.getrandbits(32) for _ in range(3)) for _ in range(2209)]
        for rd,rm,rs,rn in [(6,5,0,4),(8,7,0,4),(1,6,0,4)]:
            old = arm.assemble(f'mul r{rd}, r{rm}, r{rs}\nadd r{rd}, r{rd}, r{rn}\nbx lr',origin=0x800000)
            new = arm.assemble(f'mla r{rd}, r{rm}, r{rs}, r{rn}\nbx lr',origin=0x810000)
            for name,code in [('old',old),('new',new)]:
                m.uc.mem_write(code.origin,code.bytes)
                m.symbols[name] = code.origin
            m.uc.ctl_flush_tb()
            for i,(a,b,c) in enumerate(triples):
                snapshots = []
                for name in ['old','new']:
                    self.seed(i % 16)
                    for reg,val in [(rm,a),(rs,b),(rn,c)]:
                        m.uc.reg_write(UC_ARM_REG_R0+reg,val)
                    m.call(name)
                    snapshots.append(([m.uc.reg_read(UC_ARM_REG_R0+r) for r in range(13)],
                                      m.uc.reg_read(UC_ARM_REG_CPSR)))
                self.assertEqual(snapshots[0],snapshots[1])
                self.assertEqual(snapshots[1][0][rd],(a*b+c)&0xFFFFFFFF)
