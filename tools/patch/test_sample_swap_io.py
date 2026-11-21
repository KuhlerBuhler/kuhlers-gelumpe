"""Synthetic ARM execution of the bounded DSP transport."""
import struct
import unittest
from unittest.mock import patch
from pathlib import Path
import json

import unicorn
from unicorn import arm_const as R
import sample_swap_io as p


def word(n):
    return struct.pack('<I', n)


class Machine:
    def __init__(self, stuck=None, frozen=False, tick=0, period=0xffffffff, release_error=0, origin=p.CODE_AT, state=p.STATE, write_guard=None):
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        for at, size in ((0xc0000000,0x800000),(0xc274f000,0x30000),(0x60000000,0x1000),(0x01e26000,0x1000),(p.TIMER,0x1000)):
            self.uc.mem_map(at,size)
        self.state=state
        self.entry=origin
        self.code,self.symbols = p.build_code(origin=origin,state=state,poll_budget=32,write_guard=write_guard)
        self.uc.mem_write(origin,self.code)
        self.uc.mem_write(state,word(0))
        self.uc.mem_write(p.SEMA,word(1))
        self.uc.mem_write(p.STARTED,word(1))
        self.uc.mem_write(p.CURSOR,word(p.DSP_MIN+0x10000))
        self.uc.mem_write(p.TIMER+0x18,word(period))
        self.uc.mem_write(p.TIMER+0x20,word(0x80))
        self.uc.mem_write(p.TIMER+0x24,word(1))
        self.uc.mem_write(p.TIMER+0x10,word(tick))
        self.stuck,self.frozen,self.period=stuck,frozen,period
        self.ports=[]
        self.released=0
        self.release_error=release_error
        self.header=[]
        self.values=[]
        self.reads=0
        self.masked=0
        self.max_masked=0
        self.uc.hook_add(unicorn.UC_HOOK_CODE,self.step)
        self.uc.hook_add(unicorn.UC_HOOK_MEM_READ,self.read)
        self.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,self.write)

    def step(self,u,at,size,data):
        cpsr=u.reg_read(R.UC_ARM_REG_CPSR)
        self.masked=self.masked+1 if cpsr&0x80 else 0
        self.max_masked=max(self.max_masked,self.masked)
        if at==p.RELEASE:
            self.released+=1
            assert u.reg_read(R.UC_ARM_REG_SP)%8==0,'unaligned release stack'
            assert u.reg_read(R.UC_ARM_REG_R0)==1
            u.mem_write(p.SEMA,word(1))
            u.reg_write(R.UC_ARM_REG_R0,self.release_error)
            u.reg_write(R.UC_ARM_REG_R1,0xabcdef01)
            u.reg_write(R.UC_ARM_REG_PC,u.reg_read(R.UC_ARM_REG_LR))

    def read(self,u,access,at,size,value,data):
        if at==p.TIMER+0x10 and not self.frozen:
            old=struct.unpack('<I',u.mem_read(at,4))[0]
            u.mem_write(at,word((old+1500000)%(self.period+1)))
        if at==p.GPIO:
            stage='initial' if not self.header else 'ack' if not self.values and not self.reads else 'group'
            value=0 if stage=='initial' and self.stuck=='initial' else 2 if stage=='initial' or self.stuck==stage else 0
            u.mem_write(at,word(value))
            self.ports.append(('gpio',value))
        if at==p.PORT+2:
            value=0 if self.stuck=='status' else 0x80
            if self.stuck!='ack':value|=1
            u.mem_write(at,struct.pack('<H',value))
            self.ports.append(('status',value))
        if at==p.PORT:
            self.reads+=1
            u.mem_write(at,struct.pack('<H',0x1000+self.reads))
            self.ports.append(('read',size))

    def write(self,u,access,at,size,value,data):
        if at in (p.PORT,p.PORT+2):
            self.ports.append(('write',at,size,value))
            if len(self.header)<7:self.header.append(value & 0xffff)
            else:self.values.append(value & 0xffff)

    def run(self,op=1,ptr=0xc274f000,offset=None,count=32,cpsr=0x13):
        u=self.uc
        u.reg_write(R.UC_ARM_REG_CPSR,cpsr)
        u.reg_write(R.UC_ARM_REG_SP,0xc07ff000)
        for i in range(4,12):u.reg_write(R.UC_ARM_REG_R0+i,0xa000+i)
        for i,v in enumerate((op,ptr,p.DSP_MIN if offset is None else offset,count)):u.reg_write(R.UC_ARM_REG_R0+i,v)
        u.reg_write(R.UC_ARM_REG_LR,0xc0001000)
        u.emu_start(self.entry,0xc0001000,count=100000)
        assert u.reg_read(R.UC_ARM_REG_PC)==0xc0001000,'execution did not return'
        for i in range(4,12):assert u.reg_read(R.UC_ARM_REG_R0+i)==0xa000+i
        return u.reg_read(R.UC_ARM_REG_R0),u.reg_read(R.UC_ARM_REG_R1)


class TransportTests(unittest.TestCase):
    def test_writes_revalidate_after_acquiring_and_stale_work_releases_only_its_lease(self):
        guard = 0xC0002000
        for allowed in (0, 1):
            for op in (0, 1):
                with self.subTest(allowed=allowed, op=op):
                    m = Machine(write_guard=guard)
                    observed = []

                    def checked(uc, address, size, data):
                        observed.append((struct.unpack('<I', uc.mem_read(p.SEMA, 4))[0], list(m.ports)))
                        uc.reg_write(R.UC_ARM_REG_R0, allowed)
                        uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR))

                    m.uc.hook_add(unicorn.UC_HOOK_CODE, checked, begin=guard, end=guard)
                    expected = (p.OK, 32) if op == 0 or allowed else (7, 0)
                    self.assertEqual(m.run(op=op), expected)
                    self.assertEqual(len(observed), (2 if allowed else 1) if op else 0)
                    self.assertTrue(all(semaphore == 0 for semaphore, ports in observed))
                    if op:
                        self.assertEqual(observed[0], (0, []))
                    self.assertEqual(m.released, 1)
                    self.assertEqual(struct.unpack('<I', m.uc.mem_read(m.state, 4))[0], p.READY)
                    if op and not allowed:
                        self.assertEqual(m.ports, [])

    def test_a_job_cancelled_during_the_initial_wait_cannot_send_a_header(self):
        guard = 0xC0002000
        m = Machine(write_guard=guard)
        live = [True]

        def checked(uc, address, size, data):
            uc.reg_write(R.UC_ARM_REG_R0, int(live[0]))
            uc.reg_write(R.UC_ARM_REG_PC, uc.reg_read(R.UC_ARM_REG_LR))

        m.uc.hook_add(unicorn.UC_HOOK_CODE, checked, begin=guard, end=guard)
        m.uc.hook_add(unicorn.UC_HOOK_MEM_READ, lambda *_: live.__setitem__(0, False),
                      begin=p.GPIO, end=p.GPIO)
        self.assertEqual(m.run(), (7, 0))
        self.assertEqual(m.header, [])
        self.assertEqual(m.values, [])
        self.assertEqual(m.released, 1)
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(m.state, 4))[0], p.READY)

    def test_a_terminal_fault_during_the_initial_handshake_cannot_be_downgraded(self):
        m = Machine()
        injected = []

        def latch(uc, access, address, size, value, data):
            if not injected:
                injected.append(True)
                uc.mem_write(m.state, word(p.LATCHED))

        m.uc.hook_add(unicorn.UC_HOOK_MEM_READ, latch, begin=p.GPIO, end=p.GPIO)
        self.assertEqual(m.run(), (p.FAULT, 0))
        self.assertEqual(m.header, [])
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(m.state, 4))[0], p.LATCHED)
        self.assertEqual(m.released, 1)

    def test_a_terminal_fault_stops_each_word_and_cannot_be_cleared_at_completion(self):
        for completed in (0, 1, 16, 32):
            with self.subTest(completed=completed):
                m = Machine()
                injected = []

                def latch(uc, address, size, data):
                    if len(m.header) == 7 and len(m.values) == completed and not injected:
                        injected.append(True)
                        uc.mem_write(m.state, word(p.LATCHED))

                m.uc.hook_add(unicorn.UC_HOOK_CODE, latch,
                              begin=m.symbols['next_word'] if completed < 32 else m.symbols['word_done'],
                              end=m.symbols['next_word'] if completed < 32 else m.symbols['word_done'])
                self.assertEqual(m.run(), (p.FAULT, completed))
                self.assertEqual(len(m.values), completed)
                self.assertEqual(struct.unpack('<I', m.uc.mem_read(m.state, 4))[0], p.LATCHED)
                self.assertEqual(m.released, 1)

    def test_read_accepts_halfword_aligned_capture_spans_and_drains_the_last_group(self):
        for count in (1, 15, 16, 17, 31, 32):
            with self.subTest(count=count):
                m = Machine()
                ptr, offset = 0xc274f002, p.DSP_MIN + 2
                m.uc.mem_write(ptr - 2, b'LO' + b'\xcc' * (count * 2) + b'KEEP')
                self.assertEqual(m.run(op=0, ptr=ptr, offset=offset, count=count), (p.OK, count))
                rounded = (count + 15) & ~15
                self.assertEqual(m.header, [0xa9, offset & 0xffff, offset >> 16, rounded, 2, 0, 0])
                self.assertEqual(m.reads, rounded)
                self.assertEqual(bytes(m.uc.mem_read(ptr, count * 2)),
                                 struct.pack(f'<{count}H', *range(0x1001, 0x1001 + count)))
                self.assertEqual(bytes(m.uc.mem_read(ptr - 2, 2)), b'LO')
                self.assertEqual(bytes(m.uc.mem_read(ptr + count * 2, 4)), b'KEEP')
                self.assertEqual(m.released, 1)

    def test_read_tail_at_the_bank_end_uses_an_overlapping_in_bounds_block(self):
        for count in (1, 15, 17, 31):
            for gap in (0, 2):
                with self.subTest(count=count, gap=gap):
                    m = Machine()
                    ptr, offset = 0xc274f002, p.DSP_END - count * 2 - gap
                    m.uc.mem_write(p.CURSOR, word(p.DSP_END - gap))
                    m.uc.mem_write(ptr - 2, b'LO' + b'\xcc' * (count * 2) + b'KEEP')
                    self.assertEqual(m.run(op=0, ptr=ptr, offset=offset, count=count), (p.OK, count))
                    rounded = (count + 15) & ~15
                    start = p.DSP_END - rounded * 2
                    skipped = (offset - start) // 2
                    self.assertEqual(m.header, [0xa9, start & 0xffff, start >> 16, rounded, 2, 0, 0])
                    self.assertEqual(m.reads, rounded)
                    self.assertEqual(bytes(m.uc.mem_read(ptr, count * 2)),
                                     struct.pack(f'<{count}H', *range(0x1001 + skipped, 0x1001 + skipped + count)))
                    self.assertEqual(bytes(m.uc.mem_read(ptr - 2, 2)), b'LO')
                    self.assertEqual(bytes(m.uc.mem_read(ptr + count * 2, 4)), b'KEEP')
                    self.assertEqual(m.released, 1)

    def test_write_still_requires_a_full_aligned_group(self):
        for offset, count in ((p.DSP_MIN + 2, 16), (p.DSP_MIN, 1), (p.DSP_MIN, 17)):
            with self.subTest(offset=offset, count=count):
                m = Machine()
                self.assertEqual(m.run(op=1, offset=offset, count=count), (p.INVALID, 0))
                self.assertEqual(m.ports, [])

    def test_partial_read_timeout_reports_only_copied_words_and_latches(self):
        m = Machine(stuck='group')
        ptr = 0xc274f000
        m.uc.mem_write(ptr, b'\xcc' * 34 + b'KEEP')
        self.assertEqual(m.run(op=0, count=17), (p.TIMEOUT, 16))
        self.assertEqual(m.reads, 16)
        self.assertEqual(bytes(m.uc.mem_read(ptr + 32, 6)), b'\xcc\xccKEEP')
        self.assertEqual(m.released, 1)
        ports = list(m.ports)
        self.assertEqual(m.run(op=0, count=17), (p.FAULT, 0))
        self.assertEqual(m.ports, ports)

    def test_read_checks_logical_allocation_and_halfword_alignment(self):
        for kw in ({'offset': p.DSP_MIN + 1}, {'count': 32769}, {'ptr': 0xc274f001},
                   {'offset': p.DSP_MIN + 0x10000 - 2, 'count': 2}):
            with self.subTest(**kw):
                m = Machine()
                self.assertEqual(m.run(op=0, **kw), (p.INVALID, 0))
                self.assertEqual(m.ports, [])

    def test_write_and_read_are_actual_halfword_transfers(self):
        for op in (0,1):
            m=Machine()
            m.uc.mem_write(0xc274f000,b'\x34\x12'*32+b'KEEP')
            self.assertEqual(m.run(op=op),(p.OK,32))
            self.assertEqual(m.header,[0xab if op else 0xa9,p.DSP_MIN&0xffff,p.DSP_MIN>>16,32,2,0,0])
            self.assertEqual(m.released,1)
            self.assertLessEqual(m.max_masked,40)
            self.assertEqual(bytes(m.uc.mem_read(0xc274f040,4)),b'KEEP')
            if op:self.assertEqual(m.values,[0x1234]*32)
            else:self.assertEqual(bytes(m.uc.mem_read(0xc274f000,64)),struct.pack('<32H',*range(0x1001,0x1021)))

    def test_busy_never_touches_ports_or_releases_someone_elses_lock(self):
        m=Machine();m.uc.mem_write(p.SEMA,word(0))
        self.assertEqual(m.run(),(p.BUSY,0));self.assertEqual(m.ports,[]);self.assertEqual(m.released,0)

    def test_an_inflight_owner_is_busy_rather_than_a_latched_fault(self):
        m = Machine()
        m.uc.mem_write(p.STATE, word(1))
        m.uc.mem_write(p.SEMA, word(0))
        self.assertEqual(m.run(), (p.BUSY, 0))
        self.assertEqual(m.ports, [])
        self.assertEqual(m.released, 0)
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(p.STATE, 4))[0], 1)

    def test_an_orphaned_inflight_flag_is_latched_only_after_acquisition(self):
        m = Machine()
        m.uc.mem_write(p.STATE, word(1))
        self.assertEqual(m.run(), (p.FAULT, 0))
        self.assertEqual(m.released, 1)
        self.assertEqual(m.ports, [])
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(p.STATE, 4))[0], 2)

    def test_a_protocol_timeout_has_a_distinct_terminal_fault_value(self):
        m = Machine('ack', frozen=True)
        self.assertEqual(m.run()[0], p.TIMEOUT)
        self.assertEqual(struct.unpack('<I', m.uc.mem_read(p.STATE, 4))[0], 2)

    def test_every_stuck_phase_is_bounded_and_header_failure_latches(self):
        for stage in ('initial','status','ack','group'):
            for frozen in (False,True):
                m=Machine(stage,frozen)
                status,done=m.run()
                self.assertEqual(status,p.TIMEOUT,(stage,frozen));self.assertLess(done,32)
                self.assertEqual(m.released,1)
                fault=stage in ('ack','group')
                self.assertEqual(struct.unpack('<I',m.uc.mem_read(p.STATE,4))[0],2 if fault else 0)
                if fault:
                    ports=list(m.ports)
                    self.assertEqual(m.run(),(p.FAULT,0));self.assertEqual(m.ports,ports)

    def test_timer_wrap_and_non_maximum_period(self):
        for period in (149999999,0xffffffff):
            m=Machine('initial',tick=period-500000,period=period)
            self.assertEqual(m.run(),(p.TIMEOUT,0))

    def test_invalid_input_and_context_do_not_touch_ports(self):
        for kw in ({'count':0},{'count':17},{'count':32784},{'ptr':0xc274effe},{'ptr':0xc3fffff0},{'ptr':0xffffffff},{'offset':p.DSP_MIN-2},{'offset':0xfffffff0},{'op':2}):
            m=Machine();self.assertEqual(m.run(**kw),(p.INVALID,0));self.assertEqual(m.ports,[])
        for cpsr in (0x93,0x12,0x11,0x10,0x17,0x1b):
            m=Machine();self.assertEqual(m.run(cpsr=cpsr),(p.CONTEXT,0));self.assertEqual(m.ports,[])
        for at,v in ((p.STARTED,0),(p.IRQ_DEPTH,1)):
            m=Machine();m.uc.mem_write(at,word(v));self.assertEqual(m.run(),(p.CONTEXT,0));self.assertEqual(m.ports,[])

    def test_corrupt_allocation_and_failed_release_refuse_future_traffic(self):
        m=Machine();m.uc.mem_write(p.CURSOR,word(0xffffffff))
        self.assertEqual(m.run(),(p.INVALID,0));self.assertEqual(m.ports,[])
        m=Machine(release_error=0xffffffef)
        self.assertEqual(m.run(),(p.FAULT,32))
        ports=list(m.ports)
        self.assertEqual(m.run(),(p.FAULT,0));self.assertEqual(m.ports,ports)

    def test_relocated_probe_cannot_overwrite_own_code_or_state(self):
        for ptr in (0xc2760000,0xc276f000,0xc276eff0):
            m=Machine(origin=0xc2760000,state=0xc276f000)
            self.assertEqual(m.run(op=0,ptr=ptr),(p.INVALID,0))
            self.assertEqual(m.ports,[])
        m=Machine(origin=0xc2760000,state=0xc276f000)
        self.assertEqual(m.run(),(p.OK,32))

    def test_irq_flags_and_completed_count_survive_release(self):
        m=Machine('group',frozen=True)
        self.assertEqual(m.run(cpsr=0x53),(p.TIMEOUT,16))
        self.assertEqual(m.uc.reg_read(R.UC_ARM_REG_CPSR)&0xff,0x53)
        self.assertLessEqual(m.max_masked,40)

    def test_fault_is_checked_again_after_acquiring_ownership(self):
        m=Machine()
        def fault_before_acquire_returns(u,at,size,data):
            if at==m.symbols['acquired']:u.mem_write(p.STATE,word(1))
        m.uc.hook_add(unicorn.UC_HOOK_CODE,fault_before_acquire_returns)
        self.assertEqual(m.run(),(p.FAULT,0))
        self.assertEqual(m.ports,[])
        self.assertEqual(m.released,1)

    def test_bad_timer_and_unknown_state_are_refused(self):
        for at,v in ((p.TIMER+0x18,149999998),(p.TIMER+0x20,0x40),(p.TIMER+0x24,0)):
            m=Machine();m.uc.mem_write(at,word(v));self.assertEqual(m.run(),(p.BAD_TIMER,0));self.assertEqual(m.ports,[])
        m=Machine();m.uc.mem_write(p.STATE,word(0xffffffff));self.assertEqual(m.run(),(p.FAULT,0));self.assertEqual(m.ports,[])


class BuilderTests(unittest.TestCase):
    def test_build_code_rejects_overlapping_state_and_bad_configuration(self):
        for kw in ({'origin':1},{'state':1},{'poll_budget':0},{'poll_budget':0x100000000},{'state':p.CODE_AT+8}):
            with self.assertRaises(ValueError):p.build_code(**kw)

    def test_unmapped_images_are_refused(self):
        for raw in (b'',b'\xff'*0x200100,b'\x00'*0x200100):
            with self.assertRaises(ValueError):p.build_patch(raw)

    def test_patch_contains_only_own_code_and_cold_boot_state(self):
        raw=bytearray(b'\xff'*0x200100)
        with patch.object(p,'validate_firmware',return_value='stock'):
            result=p.build_patch(raw)
            self.assertEqual(result['builds'],['stock'])
            self.assertEqual(result['hooks'],[])
            self.assertEqual(len(result['changes']),2)
            self.assertEqual(result['changes'][1]['bytes'],'00000000')
            self.assertEqual(len(result['ram']),1)
            tail=result['ram'][0]
            self.assertEqual(int(tail['at'],0),p.CODE_AT+len(p.build_code()[0]))
            self.assertEqual(int(tail['at'],0)+tail['length'],p.CODE_END)
            for build in ('synth','hacktribe'):
                with self.assertRaises(ValueError):p.build_patch(raw,build)
            raw[p.file_offset(p.CODE_END)-1]=0
            with self.assertRaises(ValueError):p.build_patch(raw)
            raw[p.file_offset(p.CODE_END)-1]=0xff
            raw[p.file_offset(p.STATE)]=0
            with self.assertRaises(ValueError):p.build_patch(raw)

    def test_default_reservations_do_not_overlap_declared_patch_memory(self):
        own=((p.CODE_AT,p.CODE_END),(p.STATE,p.STATE_END))
        self.assertLessEqual(len(p.build_code()[0]),p.CODE_END-p.CODE_AT)
        root=Path(__file__).resolve().parents[2]
        for file in (root/'data/patches').glob('*.json'):
            doc=json.loads(file.read_text())
            if not set(doc.get('builds',[])) & {'stock','hacktribe'}:continue
            for area in doc.get('ram',[]):
                at=int(area['at'],0);end=at+area['length']
                for lo,hi in own:self.assertFalse(lo<end and at<hi,(file.name,area))


if __name__=='__main__':unittest.main()
