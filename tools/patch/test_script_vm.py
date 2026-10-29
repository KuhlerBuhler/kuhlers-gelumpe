"""Bare ARM script runtime tests; inputs contain no firmware bytes."""
import json
import re
import pathlib
import struct
import subprocess
import unittest
import sys
from functools import lru_cache
import zlib

try:
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm_const import *
    UNICORN_AVAILABLE = True
except ModuleNotFoundError:
    UNICORN_AVAILABLE = False

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

@lru_cache(None)
def contract_data():
    source = "import * as c from './data/script/contract.mjs'; import {asmInclude} from './src/script/arm-tables.mjs'; console.log(JSON.stringify({include:asmInclude(),op:c.OP,opcodes:c.OPCODES,error:c.ERROR,events:c.EVENTS,apis:c.API,header:c.HEADER,pool:c.SCRIPT_ENTRY}));"
    return json.loads(subprocess.check_output(['node', '--input-type=module', '-e', source], cwd=ROOT))

def blob(code, vars=0, stack=0, constants=(), handlers=(), strings=(), lines=(), flags=0):
    body = b''.join(struct.pack('<BBH', *h) for h in handlers)
    body += b''.join(struct.pack('<i', c) for c in constants)
    body += b''.join(s.encode()+bytes(32-len(s)) for s in strings)
    body += bytes(code)+bytes((-len(code)) % 4)
    body += b''.join(struct.pack('<HH', *l) for l in lines)
    h = struct.pack('<IHHIIIHHHHHHHH16s', 0x52435347, 2, 1, 52+len(body), 0, vars, 0, len(code), stack, len(handlers), len(constants), len(strings), len(lines), flags, b'Test')
    out = bytearray(h+body)
    struct.pack_into('<I', out, 12, zlib.crc32(out[16:]))
    return bytes(out)

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native ARM tests')
class NativeRuntimeTests(unittest.TestCase):
    def test_load_and_start_native_store(self):
        from tools.patch.script_vm import build
        machine = BareMachine(build(contract_data()['include']))
        code = [1, 7, 5, 0, 0, 0]
        error, entry = machine.load(blob(code, vars=1, stack=1))
        self.assertEqual(error, 0)
        self.assertEqual(machine.run(entry, 0), 0)
        self.assertEqual(machine.variables(entry), [7])
        self.assertEqual(machine.read(entry+12), 2)

    def test_builder_links_api_glue_from_generated_contract(self):
        from tools.patch.script_vm import build
        code = build(contract_data()['include'],origin=0x120000,
            glue={'API_KORG_MILLIS':0xABCDEF00})
        table = code.symbols['script_api_table']-code.origin
        api = code.symbols['API_KORG_MILLIS']
        size = code.symbols['SCRIPT_API_ENTRY_SIZE']
        self.assertEqual(struct.unpack_from('<I',code.bytes,table+api*size+12)[0],0xABCDEF00)
        with self.assertRaises(ValueError): build(contract_data()['include'],glue={0:123})

    def test_header_failure_is_atomic(self):
        from tools.patch.script_vm import build
        machine = BareMachine(build(contract_data()['include']))
        for data, error in [(b'bad',16), (b'not GSCR',17), (blob([0])[:-1],16)]:
            self.assertEqual(machine.load(data)[0], error)
            self.assertEqual(machine.read(machine.runtime+16), 0)

    def test_native_load_faults_leave_existing_script_armed(self):
        machine = BareMachine(runtime_code())
        error,entry = machine.load(blob([1,9,5,0,0,0],vars=1,stack=1))
        self.assertEqual(error,0)
        self.assertEqual(machine.run(entry,0),0)
        used = machine.read(machine.runtime+16)
        previous = bytes(machine.uc.mem_read(machine.arena,used))
        invalid = bytearray(blob([0]))
        invalid[-1] ^= 1
        self.assertEqual(machine.load(invalid)[0],contract_data()['error']['CHECKSUM'])
        self.assertEqual(machine.read(machine.runtime+16),used)
        self.assertEqual(bytes(machine.uc.mem_read(machine.arena,used)),previous)
        self.assertEqual(machine.variables(entry),[9])
        self.assertEqual(machine.read(entry+12),2)

    def test_pool_exact_boundary_and_one_more_block(self):
        machine = BareMachine(runtime_code())
        machine.write(machine.arena+131072,0x12345678)
        error,entry = machine.load(blob([0],vars=(131072-machine.symbols['SCRIPT_ENTRY_SIZE']-56)//4))
        self.assertEqual(error,0)
        self.assertEqual(machine.read(machine.runtime+16),131072)
        before = bytes(machine.uc.mem_read(machine.arena,131072))
        self.assertEqual(machine.load(blob([0]))[0],contract_data()['error']['POOL_BUDGET'])
        self.assertEqual(machine.read(machine.arena+131072),0x12345678)
        self.assertEqual(bytes(machine.uc.mem_read(machine.arena,131072)),before)
        self.assertEqual(len(machine.variables(entry)),(131072-machine.symbols['SCRIPT_ENTRY_SIZE']-56)//4)

    def test_invalid_code_cannot_allocate_or_arm(self):
        errors = contract_data()['error']
        cases = [
            (blob([255]),'BAD_OPCODE'),
            (blob([4,0],vars=1,stack=1),'TRUNCATED'),
            (blob([28,2,0,0]),'BAD_JUMP'),
            (blob([9,0]),'STACK'),
            (blob([1,1,0],stack=1),'STACK_MISMATCH'),
            (blob([31,0,0,0,9,0],stack=1),'RECURSION'),
            (blob([0],handlers=[(2,1,0)]),'BAD_HANDLER'),
            (blob([0],lines=[(0,0)]),'BAD_LINES'),
            (blob([0],lines=[(1,1)]),'BAD_LINES'),
            (blob([0],strings=['x'*32]),'BAD_STRING'),
        ]
        for data,name in cases:
            with self.subTest(name=name):
                machine = BareMachine(runtime_code())
                self.assertEqual(machine.load(data)[0],errors[name])
                self.assertEqual(machine.read(machine.runtime),0)
                self.assertEqual(machine.read(machine.runtime+16),0)

    def test_time_limit_wrap_and_per_event_maxima(self):
        code = [1,0,9]*128+[0]
        for start in [0,149999984]:
            for ticks in [750000,750001]:
                with self.subTest(start=start,ticks=ticks):
                    machine = BareMachine(runtime_code(),dict(timerStart=start))
                    error,entry = machine.load(blob(code,stack=1))
                    self.assertEqual(error,0)
                    def advance(uc,address,size,_):
                        if machine.read(machine.runtime+68)==256:
                            machine.write(machine.timer,(start+ticks)%150000000)
                    machine.uc.hook_add(UC_HOOK_CODE,advance,
                        begin=machine.symbols['run_next'],end=machine.symbols['run_next'])
                    exceeded = ticks > 750000
                    error = contract_data()['error']['TIME'] if exceeded else 0
                    operations = 256 if exceeded else 257
                    self.assertEqual(machine.run(entry,0),error)
                    self.assertEqual(machine.read(entry+32),operations)
                    self.assertEqual(machine.read(entry+36),operations)
                    self.assertEqual(machine.read(entry+40),ticks)
                    self.assertEqual(machine.read(entry+44),operations)
                    self.assertEqual(machine.read(entry+12),3 if exceeded else 2)

    def test_native_linked_dispatch_and_fault_isolation(self):
        machine = BareMachine(runtime_code())
        bad = blob([1,1,1,0,13,9,0],stack=2)
        healthy = blob([1,5,5,0,0,0],vars=1,stack=1)
        error,first = machine.load(bad)
        self.assertEqual(error,0)
        error,second = machine.load(healthy)
        self.assertEqual(error,0)
        self.assertEqual(machine.read(first),second)
        code,_ = machine.call('script_dispatch_event',machine.runtime,0,machine.input+0x80000)
        self.assertEqual(code,contract_data()['error']['DIV_ZERO'])
        self.assertEqual(machine.read(first+12),3)
        self.assertEqual(machine.read(second+12),2)
        self.assertEqual(machine.variables(second),[5])

    def test_more_than_sixteen_native_table_entries(self):
        machine = BareMachine(runtime_code())
        previous = None
        for i in range(33):
            error,entry = machine.load(blob([0]))
            self.assertEqual(error,0)
            if previous is not None: self.assertEqual(machine.read(previous),entry)
            previous = entry
        self.assertEqual(machine.read(previous),0)
        self.assertEqual(machine.read(machine.runtime+16),33*(machine.symbols['SCRIPT_ENTRY_SIZE']+56))
        self.assertEqual(machine.call('script_dispatch_event',machine.runtime,0,machine.input+0x80000)[0],0)
        entry = machine.read(machine.runtime)
        for _ in range(33):
            self.assertEqual(machine.read(entry+12),2)
            entry = machine.read(entry)
        self.assertEqual(entry,0)

    def test_native_per_event_time_maxima_are_independent(self):
        machine = BareMachine(runtime_code())
        error,entry = machine.load(blob([0,0,0],handlers=[(1,0,1),(2,0,2)]))
        self.assertEqual(error,0)
        self.assertEqual(machine.run(entry,0),0)
        ticks = [100]
        def elapsed(uc,address,size,_):
            machine.write(machine.timer,machine.read(machine.runtime+64)+ticks[0])
        machine.uc.hook_add(UC_HOOK_CODE,elapsed,
            begin=machine.symbols['run_finish'],end=machine.symbols['run_finish'])
        base = entry+machine.symbols['SCRIPT_ENTRY_MAX_EVENT_TICKS']
        for event,time in [(1,100),(2,250),(1,180),(2,90)]:
            ticks[0] = time
            self.assertEqual(machine.run(entry,event),0)
        self.assertEqual(machine.read(base+4),180)
        self.assertEqual(machine.read(base+8),250)
        self.assertEqual(machine.read(entry+40),250)

    def test_native_api_versions_use_both_bytes(self):
        from tools.patch.script_vm import build
        include = re.sub(r'\.equ SCRIPT_API_VERSION, \w+\n','.equ SCRIPT_API_VERSION, 0x100\n',contract_data()['include'])
        native = build(include)
        data = bytearray(blob([33,2,0,9,0],stack=1))
        struct.pack_into('<H',data,6,256)
        data = bytes(data)
        for since in [256,257]:
            for raw in [False,True]:
                with self.subTest(since=since,raw=raw):
                    machine = BareMachine(native)
                    table = machine.symbols['script_api_table']
                    size = machine.symbols['SCRIPT_API_ENTRY_SIZE']
                    at = table+2*size+machine.symbols['SCRIPT_API_SINCE']
                    machine.uc.mem_write(at,struct.pack('<H',since))
                    code,entry = machine.raw_load(data) if raw else machine.load(data)
                    if raw or since==256:
                        self.assertEqual(code,0)
                        code = machine.run(entry,0)
                    self.assertEqual(code,0 if since==256 else contract_data()['error']['API_VERSION'])

    def test_native_runtime_api_version_accepts_full_u16_range(self):
        from tools.patch.script_vm import build
        for version in [257,65535]:
            with self.subTest(version=version):
                include = re.sub(r'\.equ SCRIPT_API_VERSION, \S+\n',f'.equ SCRIPT_API_VERSION, {version}\n',contract_data()['include'])
                native = build(include)
                machine = BareMachine(native)
                data = bytearray(blob([33,2,0,9,0],stack=1))
                struct.pack_into('<H',data,6,version)
                table = machine.symbols['script_api_table']
                size = machine.symbols['SCRIPT_API_ENTRY_SIZE']
                at = table+2*size+machine.symbols['SCRIPT_API_SINCE']
                machine.uc.mem_write(at,struct.pack('<H',version))
                code,entry = machine.load(bytes(data))
                self.assertEqual(code,0)
                self.assertEqual(machine.run(entry,0),0)

    def test_declared_sections_and_appendix_boundary(self):
        machine = BareMachine(runtime_code())
        data = blob([0])
        error,entry = machine.load(data+b'let text = 1;')
        self.assertEqual(error,0)
        self.assertEqual(machine.read(machine.runtime+16),len(data)+machine.symbols['SCRIPT_ENTRY_SIZE'])
        self.assertEqual(machine.run(entry,0),0)

    def test_raw_runtime_adapter_still_checks_container_in_arm(self):
        machine = BareMachine(runtime_code())
        corrupted = bytearray(blob([255]))
        corrupted[-1] ^= 1
        self.assertEqual(machine.raw_load(bytes(corrupted))[0],contract_data()['error']['CHECKSUM'])

    def test_api_glue_has_eight_byte_aligned_stack(self):
        machine = BareMachine(runtime_code())
        error,entry = machine.load(blob([33,2,0,9,0],stack=1))
        self.assertEqual(error,0)
        self.assertEqual(machine.run(entry,0),0)
        self.assertEqual(machine.glue_stacks,[0])

    def test_native_returns_preserve_callee_registers_and_canaries(self):
        machine = BareMachine(runtime_code())
        size = machine.symbols['SCRIPT_RUNTIME_SIZE']
        machine.write(machine.runtime+size,0xabcdef12)
        values = [0x12340000+i for i in range(8)]
        for i,value in enumerate(values): machine.uc.reg_write(UC_ARM_REG_R4+i,value)
        self.assertEqual(machine.load(blob([0]))[0],0)
        self.assertEqual([machine.uc.reg_read(UC_ARM_REG_R4+i) for i in range(8)],values)
        entry = machine.read(machine.runtime)
        self.assertEqual(machine.run(entry,0),0)
        self.assertEqual([machine.uc.reg_read(UC_ARM_REG_R4+i) for i in range(8)],values)
        self.assertEqual(machine.read(machine.runtime+size),0xabcdef12)

class BareMachine:
    def __init__(self, code, case=None):
        if not UNICORN_AVAILABLE:
            raise RuntimeError('Unicorn is required to execute native ARM cases')
        self.case = case or {}
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.origin = code.origin
        self.runtime = 0x200000
        self.arena = 0x300000
        self.input = 0x400000
        self.stack = 0x500000
        self.stop = 0x600000
        self.timer = 0x01F0D010
        self.symbols = code.symbols
        for address, size in [(self.origin&~0xFFF,0x100000),(self.runtime,0x100000),(self.arena,0x100000),(self.input,0x100000),(self.stack,0x100000),(self.stop,0x1000),(self.timer & ~4095,4096)]:
            self.uc.mem_map(address,size)
        self.uc.mem_write(self.origin,code.bytes)
        self.calls = []
        self.glue_stacks = []
        self.raw_next = 0x700000
        self.uc.mem_map(self.raw_next, 0x1000000)
        self.install_glue()
        self.uc.mem_write(self.timer,struct.pack('<I', self.case.get('timerStart',0)))
        self.call('script_runtime_init', self.runtime, self.arena, self.case.get('arenaSize',131072))
        self.write(self.runtime+24, self.case.get('fuel',20000))

    def read(self, address):
        return struct.unpack('<I',self.uc.mem_read(address,4))[0]

    def write(self, address, value):
        self.uc.mem_write(address,struct.pack('<I',value & 0xffffffff))

    def call(self, symbol, *args):
        self.uc.reg_write(UC_ARM_REG_SP,self.stack+0xF0000)
        self.uc.reg_write(UC_ARM_REG_LR,self.stop)
        for i,v in enumerate(args): self.uc.reg_write(UC_ARM_REG_R0+i,v)
        self.uc.emu_start(self.symbols[symbol],self.stop,count=20000000)
        if self.uc.reg_read(UC_ARM_REG_PC) != self.stop:
            raise AssertionError(f'native {symbol} did not return')
        return self.uc.reg_read(UC_ARM_REG_R0),self.uc.reg_read(UC_ARM_REG_R1)

    def load(self, data):
        self.uc.mem_write(self.input,bytes(data))
        return self.call('script_load_block',self.runtime,self.input,len(data))

    def run(self, entry, event, args=()):
        self.uc.mem_write(self.input+0x80000,b''.join(struct.pack('<i',v) for v in args)+bytes(16))
        return self.call('script_run_event',self.runtime,entry,event,self.input+0x80000)[0]

    def variables(self, entry):
        count = self.read(self.read(entry+4)+16)
        return list(struct.unpack('<'+'i'*count,self.uc.mem_read(self.read(entry+8),count*4)))

    def install_glue(self):
        targets = {}
        for api in contract_data()['apis']:
            address = self.origin+0x80000+api['id']*16
            self.uc.mem_write(address,bytes.fromhex('0000a0e30010a0e31eff2fe1'))
            self.write(self.symbols['script_api_table']+api['id']*48+12,address)
            targets[address] = api
        def glue(uc, address, size, _):
            api = targets.get(address)
            if api is None: return
            args = []
            for i, spec in enumerate(api['args']):
                value = uc.reg_read(UC_ARM_REG_R0+i)
                if spec['kind'] == 'str':
                    value = bytes(uc.mem_read(value,32)).split(b'\0')[0].decode('ascii')
                elif spec['kind'] == 'arr':
                    first,length = value & 0xffff,value >> 16
                    entry = struct.unpack('<I',uc.mem_read(self.runtime+88,4))[0]
                    slots = struct.unpack('<I',uc.mem_read(entry+8,4))[0]
                    value = list(struct.unpack(f'<{length}i',uc.mem_read(slots+4*first,4*length)))
                elif value & 0x80000000: value -= 0x100000000
                args.append(value)
            self.calls.append([api['name'],*args])
            self.glue_stacks.append(uc.reg_read(UC_ARM_REG_SP) & 7)
            uc.reg_write(UC_ARM_REG_R0,self.case.get('apiReturns',{}).get(api['name'],0) & 0xffffffff)
            uc.reg_write(UC_ARM_REG_R1,self.case.get('apiFaults',{}).get(api['name'],0))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        self.uc.hook_add(UC_HOOK_CODE,glue,begin=self.origin+0x80000,end=self.origin+0x81000)

    def raw_load(self, data):
        def container_only(uc,address,size,_):
            uc.reg_write(UC_ARM_REG_R0,0)
            uc.reg_write(UC_ARM_REG_PC,self.symbols['load_return'])
        hook = self.uc.hook_add(UC_HOOK_CODE,container_only,
            begin=self.symbols['verify_code'],end=self.symbols['verify_code'])
        try:
            error,_ = self.load(data)
        finally:
            self.uc.hook_del(hook)
        if error: return error,0
        entry = self.raw_next
        entry_size = self.symbols['SCRIPT_ENTRY_SIZE']
        block = entry+entry_size
        total = struct.unpack_from('<I',data,8)[0]
        count = struct.unpack_from('<I',data,16)[0]
        variables = block+total
        self.raw_next = (variables+count*4+4095) & ~4095
        self.uc.mem_write(block,data)
        self.uc.mem_write(entry,bytes(entry_size))
        self.write(entry+4,block)
        self.write(entry+8,variables)
        self.write(entry+12,1)
        return 0,entry

    def snapshot(self, entry):
        state = {1:'loaded',2:'armed',3:'disabled'}[self.read(entry+12)]
        event = contract_data()['events'][self.read(entry+28)]['name']
        fault = None
        if state == 'disabled':
            fault = dict(code=self.read(entry+16),offset=self.read(entry+20),line=self.read(entry+24),event=event)
        return dict(state=state,vars=self.variables(entry),fault=fault)

    def run_snapshot(self, entry, index, name, args=()):
        event = next(e['id'] for e in contract_data()['events'] if e['name']==name)
        code = self.run(entry,event,args)
        handled = bool(self.read(self.runtime+92))
        return dict(script=index,event=name,code=code,handled=handled,
            offset=self.read(entry+20) if handled else 0,line=self.read(entry+24) if handled else 0,
            ops=self.read(entry+32) if handled else 0,cost=self.read(entry+36) if handled else 0)

@lru_cache(None)
def runtime_code():
    from tools.patch.script_vm import build
    return build(contract_data()['include'])

def run_case(case):
    machine = BareMachine(runtime_code(),case)
    loads, runs, entries = [], [], []
    for i, script in enumerate(case['scripts']):
        data = bytes.fromhex(script['blob'])+bytes.fromhex(script.get('appendix',''))
        if script.get('verify',True): code,entry = machine.load(data)
        else: code,entry = machine.raw_load(data)
        offset = machine.read(machine.runtime+76)
        loads.append(dict(ok=code==0,code=code,offset=None if not code or offset==0xffffffff else offset))
        entries.append(entry if not code else None)
        if not code: runs.append(machine.run_snapshot(entry,i,'start'))
    for event in case.get('events',[]):
        for i,entry in enumerate(entries):
            if entry: runs.append(machine.run_snapshot(entry,i,event['name'],event.get('args',[])))
    return dict(loads=loads,runs=runs,calls=machine.calls,scripts=[machine.snapshot(e) if e else None for e in entries])

if __name__ == '__main__':
    if '--cases' in sys.argv:
        inputs = json.load(sys.stdin)
        cases = inputs['cases'] if isinstance(inputs,dict) else inputs
        json.dump([run_case(case) for case in cases],sys.stdout)
    else: unittest.main()
