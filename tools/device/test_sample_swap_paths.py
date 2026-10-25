"""Offline guards and ARM driver checks for the bounded sample path probe."""
import struct
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample_swap_paths as p


class Guards(unittest.TestCase):
    def test_default_never_needs_midi(self):
        self.assertFalse(p.arguments([]).execute)
        with self.assertRaises(ValueError): p.arguments(['--execute'])
        with self.assertRaises(ValueError):
            p.arguments(['--execute', '--vsb', 'mine', '--slot', '645', '--unused-confirmed', '--stopped-confirmed', '--clock-mhz', '50'])

    def test_regions_are_disjoint_and_high_scratch_excludes_task_stack(self):
        p.check_regions()
        for at, length in p.REGIONS[1:]:
            self.assertGreaterEqual(at, 0xC274F000)
            self.assertLessEqual(at + length, 0xC4000000)

    def test_short_success_is_not_success(self):
        with self.assertRaises(RuntimeError): p.io_ok(dict(status=0, completed=15), 32)
        with self.assertRaises(RuntimeError): p.io_ok(dict(status=5, completed=16), 32)
        p.io_ok(dict(status=0, completed=16), 32)

    def test_riff_parser_obeys_chunk_lengths(self):
        pcm = b'\x11\x22' * 1024
        wave = b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, 48000, 96000, 2, 16) + b'data' + struct.pack('<I', len(pcm)) + pcm
        head = bytearray(4096)
        head[:16] = b'e2s sample all\x1a\0'
        struct.pack_into('<I', head, 16 + 644 * 4, 4096)
        data = bytes(head) + wave
        read = lambda off, n: data[off:off+n]
        self.assertEqual(p.card_pcm(read, 645, 1024), (4140, len(pcm)))
        malformed = bytearray(data)
        struct.pack_into('<I', malformed, 4096 + 40, 0xffffffff)
        with self.assertRaises(ValueError): p.card_pcm(lambda o,n: malformed[o:o+n], 645, 1024)
        stereo24 = bytearray(data)
        struct.pack_into('<H', stereo24, 4096 + 34, 24)
        with self.assertRaises(ValueError): p.card_pcm(lambda o,n: stereo24[o:o+n], 645, 1024)

    def test_cpu_reads_are_chunked_below_alsa_limit(self):
        counts=[]
        head=[0xf0,0x42,0x30,0,1,0x24]
        def ask(message):
            at,n=struct.unpack('<II',p.old.dec(message[7:-1]))
            counts.append(n)
            data=bytes(n)
            payload=struct.pack('<4I',0,at,n,p.zlib.crc32(data))+data
            return head+[0x69,*p.old.enc(payload),0xf7]
        link=p.Link(ask,0,0x24); link.largest=32768
        self.assertEqual(link.read(p.BACKUP,65536),bytes(65536))
        self.assertEqual(max(counts),2048)

    def test_delayed_confirmed_execute_keeps_success_but_rejects_timing(self):
        words=[0]*16
        words[0:4]=[p.MAGIC,99,0,512]
        words[p.R_BEFORE]=100; words[p.R_AFTER]=200; words[p.R_PERIOD]=p.TIMER_HZ-1
        class Link:
            def write_at(self,*args): pass
            def execute(self,token): pass
            def read(self,*args): return struct.pack('<16I',*words)
        with patch.object(p.time,'monotonic',side_effect=[0,2]), patch.object(p.secrets,'randbits',return_value=98):
            result=p.Driver(Link(),p.IO_CODE).io(1,p.VERIFY,0x365ec0,1024)
        self.assertEqual(result['status'],0)
        self.assertEqual(result['completed'],512)
        self.assertFalse(result['timing_valid'])
        self.assertIsNone(result['ticks'])

    def test_unknown_execute_never_sends_followup(self):
        class Link:
            def __init__(self): self.actions=[]
            def write_at(self, at, data): self.actions.append(('write',at))
            def execute(self, token): self.actions.append(('exec',token)); raise TimeoutError()
            def read(self, at, n): self.actions.append(('read',at)); return bytes(n)
        link=Link()
        with self.assertRaisesRegex(RuntimeError, 'no retry or cleanup'):
            p.Driver(link, 0xC2760000).call(p.io_driver(0, p.BACKUP, 0x365ec0, 1024, 99), 99)
        self.assertEqual([a[0] for a in link.actions], ['write','write','exec'])


class MappingGuards(unittest.TestCase):
    def link(self):
        class Memory:
            def __init__(self): self.memory={}; self.writes=[]
            def read(self,at,n): return bytes(self.memory.get(at+i,0) for i in range(n))
            def seed(self,at,data): self.memory.update((at+i,v) for i,v in enumerate(data))
            def info(self): return 2048
            def write_at(self,at,data): self.writes.append((at,len(data))); self.seed(at,data)
        link=Memory()
        for index in range(1000):
            link.seed(p.old.NAMES+index*32+30,struct.pack('<H',index+50))
            for base,stride,field in p.MAPPING_TABLES:
                link.seed(base+index*stride+field,struct.pack('<H',index))
        meta=bytearray(0x45C); struct.pack_into('<H',meta,22,644)
        struct.pack_into('<II',meta,0,0x365ec0,2048); meta[11]=1
        link.seed(p.old.CURSOR,struct.pack('<I',0x3666c0))
        link.seed(p.old.META+644*0x45C,meta)
        return link

    def test_target_rejects_import_or_intermediate_reordering_even_if_final_matches(self):
        for which in range(3):
            with self.subTest(which=which):
                link=self.link()
                if which==0:
                    link.seed(p.old.NAMES+644*32+30,struct.pack('<H',750))
                    base,stride,field=p.MAPPING_TABLES[0]
                    link.seed(base+700*stride+field,struct.pack('<H',644))
                else:
                    base,stride,field=p.MAPPING_TABLES[which-1]
                    link.seed(base+644*stride+field,struct.pack('<H',700))
                    base,stride,field=p.MAPPING_TABLES[which]
                    link.seed(base+700*stride+field,struct.pack('<H',644))
                with self.assertRaisesRegex(ValueError,'identity'):
                    p.identity_target(link,645)
                self.assertEqual(link.writes,[])

    def test_other_used_id_cannot_alias_onto_target(self):
        link=self.link()
        base,stride,field=p.MAPPING_TABLES[2]
        link.seed(base+700*stride+field,struct.pack('<H',644))
        with self.assertRaisesRegex(ValueError,'referenced'):
            p.assert_unused(link,645,{700})

    def test_alias_guard_restores_cpu_and_stops_before_any_dsp_call(self):
        import sample_swap_io
        link=self.link()
        before={at:link.read(at,n) for at,n in p.REGIONS}
        base,stride,field=p.MAPPING_TABLES[2]
        link.seed(base+700*stride+field,struct.pack('<H',644))
        calls=[]
        class Driver:
            def __init__(self,*args): pass
            def scan(self): return {700}
            def io(self,*args): calls.append(args); raise AssertionError('must not touch DSP')
        a=p.arguments(['--slot','645','--kib','1','--stopped-confirmed'])
        with patch.object(sample_swap_io,'validate_firmware'),patch.object(p,'Driver',Driver),self.assertRaisesRegex(RuntimeError,'referenced'):
            p.run(link,bytes(0x200100),a)
        self.assertEqual(calls,[])
        for at,data in before.items(): self.assertEqual(link.read(at,len(data)),data)

    def test_used_reordering_to_another_physical_sample_is_allowed(self):
        link=self.link()
        base,stride,field=p.MAPPING_TABLES[2]
        link.seed(base+700*stride+field,struct.pack('<H',701))
        p.assert_unused(link,645,{700})

    def test_unresolvable_used_import_number_refuses_proof(self):
        link=self.link()
        link.seed(p.old.NAMES+700*32+30,bytes(2))
        with self.assertRaisesRegex(ValueError,'cannot be resolved'):
            p.assert_unused(link,645,{700})


class ArmDrivers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
            from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
        except ImportError:
            raise unittest.SkipTest('unicorn unavailable')
        cls.api=(Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

    def machine(self, blob, short=False, io_status=0, enabled=True, prepare=None):
        Uc,arch,mode,hook,R0,R1,R2,R3,SP,LR,PC=self.api
        m=Uc(arch,mode)
        m.mem_map(0xC0000000,0x04000000)
        m.mem_map(0x01C40000,0x1000)
        m.mem_map(p.TIMER,0x1000)
        m.mem_write(p.TIMER+0x18, struct.pack('<I',p.TIMER_HZ-1))
        m.mem_write(p.TIMER+0x20, struct.pack('<II',0x80 if enabled else 0,1))
        m.mem_write(p.STUB,blob)
        m.mem_write(p.MMC_CLK,struct.pack('<I',0x105))
        m.reg_write(SP,0xC2000000)
        m.reg_write(LR,0xC0008000)
        m.reg_write(R0,123)
        if prepare: prepare(m)
        calls=[]
        self.clock_writes=[]
        from unicorn import UC_HOOK_MEM_WRITE
        m.hook_add(UC_HOOK_MEM_WRITE, lambda u,access,at,size,value,data: self.clock_writes.append(value) if at==p.MMC_CLK else None)
        def step(u,at,size,_):
            if at in (p.FS_OPEN,p.FS_SEEK,p.FS_READ,p.FS_CLOSE,0xC2760000):
                calls.append(at)
                if at==p.FS_READ:
                    n=u.reg_read(R2)
                    u.mem_write(u.reg_read(R3),struct.pack('<I', n-32 if short else n))
                elif at==0xC2760000:
                    u.reg_write(R1,u.reg_read(R3) if not io_status else 0)
                u.reg_write(R0, io_status if at==0xC2760000 else 0)
                u.reg_write(PC,u.reg_read(LR))
        m.hook_add(hook,step)
        m.emu_start(p.STUB,0xC0008000,count=200000)
        self.assertEqual(m.reg_read(PC),0xC0008000)
        result=struct.unpack('<16I',m.mem_read(p.RESULT,64))
        return m,calls,result

    def test_usage_scan_covers_last_bank_pattern_and_live_parts(self):
        def prepare(m):
            m.mem_write(p.VERIFY,bytes([255])*128)
            m.mem_write(p.VERIFY+8191,b'\x00')
            m.mem_write(p.LIVE_PTR,struct.pack('<I',0xC0800000))
            m.mem_write(p.BANK+249*0x4000+0x808,struct.pack('<H',1000))
            m.mem_write(p.BANK+249*0x4000+0x808+15*0x330,struct.pack('<H',1023))
            m.mem_write(0xC0800004+0x808,struct.pack('<H',777))
            m.mem_write(0xC0800004+0x808+15*0x330,struct.pack('<H',0xffff))
        m,calls,result=self.machine(p.scan_driver(123),prepare=prepare)
        self.assertEqual(calls,[])
        self.assertEqual(result[p.R_STATUS],0)
        self.assertEqual(result[p.R_COMPLETED],251*16)
        self.assertEqual(result[p.R_GOT],1)
        self.assertEqual(p.used_ids(m.mem_read(p.VERIFY,128)),{0,777,1000,1023})
        self.assertEqual(m.mem_read(p.VERIFY+8191,1),b'\x00')
        self.assertEqual(self.clock_writes,[])

    def test_usage_scan_rejects_invalid_live_pointer(self):
        def prepare(m): m.mem_write(p.LIVE_PTR,struct.pack('<I',0xfffffff0))
        _,calls,result=self.machine(p.scan_driver(123),prepare=prepare)
        self.assertEqual(calls,[])
        self.assertNotEqual(result[p.R_STATUS],0)
        self.assertEqual(result[p.R_COMPLETED],250*16)

    def test_short_file_read_closes_restores_clock_and_never_writes_dsp(self):
        blob=p.card_driver(4096,1024,123,write=True,clock_mhz=25,offset=0x365ec0,entry=0xC2760000)
        m,calls,result=self.machine(blob,short=True)
        self.assertNotIn(0xC2760000,calls)
        self.assertEqual(calls[-1],p.FS_CLOSE)
        self.assertNotEqual(result[p.R_STATUS],0)
        self.assertEqual(struct.unpack('<I',m.mem_read(p.MMC_CLK,4))[0],0x105)

    def test_disabled_timer_does_not_open_the_card(self):
        _,calls,result=self.machine(p.card_driver(4096,1024,123),enabled=False)
        self.assertEqual(calls,[])
        self.assertEqual(result[p.R_STATUS],4)

    def test_default_clock_is_never_written(self):
        self.machine(p.card_driver(4096,1024,123,write=True,offset=0x365ec0))
        self.assertEqual(self.clock_writes,[])

    def test_file_then_dsp_status_survives_close(self):
        blob=p.card_driver(4096,1024,123,write=True,offset=0x365ec0,entry=0xC2760000)
        _,calls,result=self.machine(blob,io_status=5)
        self.assertLess(calls.index(p.FS_READ),calls.index(0xC2760000))
        self.assertEqual(result[p.R_STATUS],5)
        self.assertEqual(calls[-1],p.FS_CLOSE)


class HostPipeline(unittest.TestCase):
    def fixture(self):
        import sample_swap_io
        class Memory:
            def __init__(self): self.mem={}; self.writes=[]
            def info(self): return 2048
            def read(self,at,n): return bytes(self.mem.get(at+i,0) for i in range(n))
            def write_at(self,at,data):
                self.writes.append((at,len(data)))
                self.seed(at,data)
            def seed(self,at,data): self.mem.update((at+i,v) for i,v in enumerate(data))
        link=Memory()
        index=644
        meta=bytearray(0x45C)
        struct.pack_into('<II',meta,0,0x365ec0,2048)
        meta[11]=1
        struct.pack_into('<H',meta,22,index)
        link.seed(p.old.META+index*0x45C,meta)
        link.seed(p.old.CURSOR,struct.pack('<I',0x3666c0))
        a=p.arguments(['--slot','645','--kib','1','--stopped-confirmed'])
        return link,a,sample_swap_io

    def test_latched_fault_is_refused_before_any_mutation(self):
        link,a,module=self.fixture()
        link.seed(p.MARKER,struct.pack('<II',p.MARK,1))
        with patch.object(module,'validate_firmware'), self.assertRaisesRegex(RuntimeError,'latched'):
            p.run(link,bytes(0x200100),a)
        self.assertEqual(link.writes,[])

    def test_io_fault_retains_marker_and_scratch_without_cleanup(self):
        link,a,module=self.fixture()
        class FaultDriver:
            def __init__(self,link,entry): self.link=link
            def scan(self): return set()
            def io(self,*args):
                self.link.seed(p.IO_STATE,struct.pack('<I',1))
                raise RuntimeError('bounded fault')
        with patch.object(module,'validate_firmware'), patch.object(p,'identity_target',return_value=[]), patch.object(p,'Driver',FaultDriver), patch.object(p,'assert_unused'), self.assertRaisesRegex(RuntimeError,'bounded fault'):
            p.run(link,bytes(0x200100),a)
        self.assertEqual(struct.unpack('<II',link.read(p.MARKER,8)),(p.MARK,1))
        self.assertEqual(link.writes[-1],(p.PATH,len(a.path)+1))

    def test_referenced_slot_is_refused_before_any_dsp_call(self):
        for raw_id in (644,645,646):
            with self.subTest(raw_id=raw_id):
                link,a,module=self.fixture()
                calls=[]
                class Driver:
                    def __init__(self,*args): pass
                    def scan(self): return {raw_id}
                    def io(self,*args): calls.append(args); raise AssertionError('must not touch DSP')
                with patch.object(module,'validate_firmware'), patch.object(p,'identity_target',return_value=[]), patch.object(p,'Driver',Driver), self.assertRaisesRegex(RuntimeError,'referenced'):
                    p.run(link,bytes(0x200100),a)
                self.assertEqual(calls,[])

    def test_standalone_usage_scan_restores_only_its_cpu_scratch(self):
        link,a,module=self.fixture()
        link.seed(p.STUB,b'original stub')
        link.seed(p.VERIFY,b'original bitmap')
        before=[link.read(at,n) for at,n in ((p.STUB,0x400),(p.VERIFY,128))]
        class Driver:
            def __init__(self,*args): pass
            def call(self,*args):
                bitmap=bytearray(128); bitmap[777//8]=1<<(777%8)
                link.seed(p.VERIFY,bitmap); link.seed(p.STUB,b'probe code')
                return dict(status=0,completed=251*16)
        with patch.object(module,'validate_firmware'),patch.object(p,'Driver',Driver):
            self.assertEqual(p.scan_usage(link,bytes(0x200100)),{777})
        for (at,n),raw in zip(((p.STUB,0x400),(p.VERIFY,128)),before):
            self.assertEqual(link.read(at,n),raw)
        self.assertEqual({at for at,n in link.writes},{p.STUB,p.VERIFY})

    def test_both_paths_really_change_pcm_and_restore_all_cpu_scratch(self):
        self.exercise()

    def test_corrupt_readback_runs_bounded_verified_restoration(self):
        self.exercise(corrupt=True)

    def test_bad_measurement_time_rejects_throughput_after_verified_restoration(self):
        self.exercise(invalid_time=True)

    def exercise(self,corrupt=False,invalid_time=False):
        link,a,module=self.fixture()
        before={at:link.read(at,n) for at,n in p.REGIONS}
        pcm=b'\x11\x22'*1024
        wave=b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,48000,96000,2,16)+b'data'+struct.pack('<I',len(pcm))+pcm
        header=bytearray(4096); header[:16]=b'e2s sample all\x1a\0'
        struct.pack_into('<I',header,16+644*4,4096)
        card=bytes(header)+wave
        dsps=[pcm[:1024]]
        changed=[]
        corrupt_once=[corrupt]
        class Driver:
            def __init__(self,link,entry): self.link=link
            def scan(self): return set()
            def io(self,op,buffer,offset,length):
                if op: dsps[0]=self.link.read(buffer,length); changed.append(dsps[0])
                else:
                    data=dsps[0]
                    if len(changed)==1 and corrupt_once[0]:
                        data=bytes(v^2 for v in data); corrupt_once[0]=False
                    self.link.seed(buffer,data)
                return dict(status=0,completed=length//2,ticks=150000,milliseconds=1,
                            timing_valid=not(invalid_time and op and len(changed)==1))
            def card(self,offset,length,write=False,clock_mhz=None,dsp_offset=0):
                self.link.seed(p.VERIFY,card[offset:offset+length])
                if write:
                    if dsps[0]==pcm[:length]: raise AssertionError('card test did not replace changed data')
                    dsps[0]=card[offset:offset+length]
                words=[0]*16; words[p.R_GOT]=length
                return dict(status=0,completed=length//2,ticks=150000,milliseconds=1,words=words)
        with patch.object(module,'validate_firmware'), patch.object(p,'identity_target',return_value=[]), patch.object(p,'Driver',Driver), patch.object(p,'assert_unused'):
            if corrupt:
                with self.assertRaisesRegex(RuntimeError,'original DSP bytes restored and verified'):
                    p.run(link,bytes(0x200100),a)
                self.assertEqual(dsps[0],pcm[:1024])
                self.assertEqual(struct.unpack('<II',link.read(p.MARKER,8)),(p.MARK,0))
                return
            if invalid_time:
                with self.assertRaisesRegex(RuntimeError,'no throughput reported; original DSP bytes and CPU scratch restored and verified'):
                    p.run(link,bytes(0x200100),a)
                self.assertEqual(dsps[0],pcm[:1024])
                for at,data in before.items(): self.assertEqual(link.read(at,len(data)),data)
                return
            result=p.run(link,bytes(0x200100),a)
        self.assertTrue(result['dsp_restored'])
        self.assertEqual(dsps[0],pcm[:1024])
        self.assertTrue(any(data!=pcm[:1024] for data in changed))
        for at,data in before.items(): self.assertEqual(link.read(at,len(data)),data)


if __name__=='__main__': unittest.main()
