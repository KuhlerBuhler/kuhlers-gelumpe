"""Native input and frame hooks over synthetic RAM only."""
import struct
import unittest
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from tools.patch.test_script_vm import BareMachine, contract_data, blob, UNICORN_AVAILABLE
try:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
except ModuleNotFoundError:
    pass

class SharedWordTests(unittest.TestCase):
    def test_load_bar_reads_the_app_picture_where_it_is(self):
        """tools/patch/load_bar.py leaves a frame equal to the open app's picture without the look; it names the address itself."""
        from tools.patch.script_hooks import build, RUNTIME
        from tools.patch import load_bar
        for name in ('hacktribe','stock'):
            built=build(contract_data()['include'],build=name)
            self.assertEqual(load_bar.APP_PICTURE,RUNTIME+built.symbols['RT_DISPLAY'],name)

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native hook tests')
class HookTests(unittest.TestCase):
    def machine(self):
        from tools.patch.script_hooks import build
        built = build(contract_data()['include'])
        machine = BareMachine(built.vm)
        machine.runtime = built.layout['runtime']
        machine.arena = built.layout['pool']
        from tools.patch.script_hooks import BLECHY_BLOCK,BLECHY_BLOCK_END
        machine.uc.mem_map(BLECHY_BLOCK,BLECHY_BLOCK_END-BLECHY_BLOCK)    # where the image holds the block of Blechy
        from tools.patch.script_hooks import MORE_START,MORE_END
        machine.uc.mem_map(MORE_START,(MORE_END-MORE_START+0xFFF)&~0xFFF)  # the second code area (display, store, hardware, events, apps)
        from tools.patch.script_hooks import runtime_profile
        work = runtime_profile('hacktribe').actions['MG_WORK']
        machine.uc.mem_map(work&~0xFFF,((work+0xF00+0xFFF)&~0xFFF)-(work&~0xFFF))  # the folder copy's work area, read by every input
        for address,data in built.sections[len(built.vm.sections):]:
            machine.uc.mem_write(address,data)
        machine.symbols.update(built.symbols)
        machine.call('script_runtime_init',machine.runtime,machine.arena,131072)
        from tools.patch.script_hooks import MENU_STATE
        machine.uc.mem_write(MENU_STATE,b'\xff'*0x200)    # an unarmed menu reads FF, as in the image
        machine.uc.mem_map(0xC0028000,4096)
        machine.uc.mem_map(0xC0083000,4096)
        machine.write(0xC0083710,0xC031BB2C)
        machine.uc.mem_map(0xC033E000,4096)
        machine.uc.mem_map(0xC0340000,4096)
        machine.uc.mem_map(0xC0345000,4096)    # the LED manager's pointer (0xC0345A1C), 0: the unsaved WRITE LED stays out
        machine.uc.mem_map(0xC0310000,0x10000)
        for at,size in [(0xC0690000,0x2000),(0xC06B2000,0x5000),(0xC06BC000,0x1000),(0xC06C2000,0x1000)]: machine.uc.mem_map(at,size)
        machine.write(0xC033E6F8,machine.input+0x1000)
        machine.write(0xC03404C0,machine.input+0x2000)
        machine.write(machine.input+0x202C,1)
        machine.write(machine.runtime+96,1)
        machine.uc.reg_write(UC_ARM_REG_CPSR,0xA0000013)
        return machine,built

    def post(self,machine,event,args=()):
        machine.uc.mem_write(machine.input+0x4000,struct.pack('<4i',event,*(list(args)+[0]*3)[:3]))
        return machine.call('script_ring_post',machine.runtime,machine.input+0x4000)[0]

    def test_ring_order_coalescing_overflow_and_wrap(self):
        machine,_ = self.machine()
        self.assertEqual(self.post(machine,5,[2,10]),1)
        self.assertEqual(self.post(machine,5,[2,700]),1)
        self.assertEqual(machine.read(machine.runtime+104),1)
        for i in range(63): self.assertEqual(self.post(machine,3,[i]),1)
        self.assertEqual(self.post(machine,3,[1]),0)
        self.assertEqual(machine.read(machine.runtime+20),1)
        for i in range(64):
            self.assertEqual(machine.call('script_ring_take',machine.runtime,machine.input+0x5000)[0],1)
            data = struct.unpack('<4i',machine.uc.mem_read(machine.input+0x5000,16))
            self.assertEqual(data[:3],(5,2,700) if i==0 else (3,i-1,0))
        self.assertEqual(machine.call('script_ring_take',machine.runtime,machine.input+0x5000)[0],0)
        machine.write(machine.runtime+104,0xffffffff)
        machine.write(machine.runtime+108,0xffffffff)
        self.assertEqual(self.post(machine,3,[7]),1)
        self.assertEqual(machine.read(machine.runtime+104),0)
        self.assertEqual(machine.call('script_ring_take',machine.runtime,machine.input+0x5000)[0],1)
        self.assertEqual(machine.read(machine.runtime+108),0)

    def input(self,machine,msg):
        ptr = machine.input+0x3000
        data = bytearray(32)
        data[12:17] = bytes(msg[:5])
        if len(msg)>5: data[24:26] = bytes(msg[5:7])
        machine.uc.mem_write(ptr,bytes(data))
        original = [ptr]+[0x12345000+i for i in range(1,13)]
        for i,value in enumerate(original): machine.uc.reg_write(UC_ARM_REG_R0+i,value)
        machine.uc.reg_write(UC_ARM_REG_SP,machine.stack+0xF0000)
        machine.uc.reg_write(UC_ARM_REG_LR,machine.stop)
        machine.uc.reg_write(UC_ARM_REG_CPSR,0xA0000013)
        hook = machine.uc.hook_add(UC_HOOK_CODE,lambda uc,*_:uc.emu_stop(),begin=machine.stop,end=machine.stop)
        try:
            machine.uc.emu_start(machine.symbols['script_input_hook'],0xC0028380,count=10000)
        finally:
            machine.uc.hook_del(hook)
        pc = machine.uc.reg_read(UC_ARM_REG_PC)
        self.assertIn(pc,[0xC0028380,machine.stop])
        self.assertEqual(machine.uc.reg_read(UC_ARM_REG_CPSR),0xA0000013)
        self.assertEqual(machine.uc.reg_read(UC_ARM_REG_SP),machine.stack+0xF0000)
        self.assertEqual(machine.uc.reg_read(UC_ARM_REG_LR),machine.stop)
        observed = [machine.uc.reg_read(UC_ARM_REG_R0+i) for i in range(13)]
        if pc==0xC0028380: original[3] = data[24]
        self.assertEqual(observed,original)
        return pc

    def test_input_normalization_and_capture(self):
        cases=[([0,4,1,0,0],(3,4,0,0)),([0,4,0,0,0],(4,4,0,0)),
            ([1,2,0,255,0],(6,2,-1,0)),([2,3,1,244,0],(5,3,500,0)),
            ([4,6,0,100,1],(7,6,1,100)),([5,1,144,1,144],(8,400,400,1))]
        for message,want in cases:
            with self.subTest(message=message):
                machine,_ = self.machine()
                machine.write(machine.runtime+148,0x37)
                self.assertEqual(self.input(machine,message),machine.stop)
                self.assertEqual(machine.call('script_ring_take',machine.runtime,machine.input+0x5000)[0],1)
                self.assertEqual(struct.unpack('<4i',machine.uc.mem_read(machine.input+0x5000,16)),want)

    def test_a_touch_position_says_whether_it_is_the_first_of_its_touch(self):
        machine,_ = self.machine()
        machine.write(machine.runtime+148,0x37)
        steps=[([0,34,1,0,0],(3,34,0,0)),                # the press, no position yet
            ([5,1,144,2,88],(8,400,600,1)),              # the first position after the press
            ([5,1,150,2,90],(8,406,602,0)),
            ([5,1,160,2,92],(8,416,604,0)),
            ([0,34,0,0,0],(4,34,0,0)),                   # the release
            ([5,0,10,0,20],(8,10,20,1)),                 # a position with no press first: still the first
            ([5,0,11,0,21],(8,11,21,0)),
            ([0,34,1,0,0],(3,34,0,0)),                   # a press while one touch is still down starts a new one
            ([5,0,12,0,22],(8,12,22,1)),
            ([0,34,0,0,0],(4,34,0,0)),
            ([0,5,1,0,0],(3,5,0,0)),                     # another key leaves the touch alone
            ([5,0,13,0,23],(8,13,23,1))]
        for message,want in steps:
            with self.subTest(message=message):
                self.input(machine,message)
                self.assertEqual(machine.call('script_ring_take',machine.runtime,machine.input+0x5000)[0],1)
                self.assertEqual(struct.unpack('<4i',machine.uc.mem_read(machine.input+0x5000,16)),want)

    def test_guards_reserved_types_flags_and_exit(self):
        cases=[dict(armed=0),dict(armed=2),dict(boot=0x2000),dict(panel=0),dict(panel=0xffffffff),dict(flags=[1,0]),dict(flags=[0,1])]
        for config in cases:
            with self.subTest(config=config):
                machine,_ = self.machine()
                machine.write(machine.runtime+148,0xffffffff)
                machine.write(machine.runtime+96,config.get('armed',1))
                machine.write(machine.input+0x1018,config.get('boot',0))
                if 'panel' in config: machine.write(0xC033E6F8,config['panel'])
                self.assertEqual(self.input(machine,[2,0,0,10,0]+config.get('flags',[0,0])),0xC0028380)
                self.assertEqual(machine.read(machine.runtime+104),0)
        for type in [3,6,7,8,255]:
            machine,_ = self.machine()
            machine.write(machine.runtime+148,0xffffffff)
            self.assertEqual(self.input(machine,[type,0,0,0,0]),0xC0028380)
            self.assertEqual(machine.read(machine.runtime+104),0)
        machine,_ = self.machine()
        machine.write(machine.runtime+148,0x37)
        self.assertEqual(self.input(machine,[0,13,1,0,0]),0xC0028380)

    def event_script(self,machine):
        code=[0,1,1,5,0,0,0,5,1,0,0,4,2,0,1,1,10,5,2,0,0]
        error,entry=machine.load(blob(code,vars=3,stack=2,
            handlers=[(1,0,1),(3,1,7),(2,0,11)]))
        self.assertEqual(error,0)
        self.assertEqual(machine.run(entry,0),0)
        return entry

    def test_ready_gate_order_and_repeated_frame(self):
        machine,_=self.machine()
        entry=self.event_script(machine)
        self.post(machine,3,[7])
        machine.write(machine.input+0x202C,0)
        self.assertEqual(machine.call('script_frame_run',machine.runtime)[0],0)
        self.assertEqual(machine.variables(entry),[0,0,0])
        self.assertEqual(machine.read(machine.runtime+108),0)
        machine.write(machine.input+0x202C,1)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(entry),[1,7,1])
        self.assertEqual(machine.read(entry+220),1)
        machine.write(machine.input+0x202C,4)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(entry),[1,7,2])

    def test_short_handlers_share_budget_and_resume_without_disabling_others(self):
        for start in [0,149999984]:
            with self.subTest(start=start):
                machine,_=self.machine()
                machine.write(machine.timer,start)
                entries=[]
                for _ in range(3):
                    error,entry=machine.load(blob([0,33,2,0,9,0],stack=1,
                        handlers=[(2,0,1)]))
                    self.assertEqual(error,0)
                    self.assertEqual(machine.run(entry,0),0)
                    entries.append(entry)
                def advance(uc,address,size,_):
                    if machine.read(machine.runtime+116)==1 and machine.read(machine.runtime+84)==2:
                        machine.write(machine.timer,(machine.read(machine.timer)+500000)%150000000)
                machine.uc.hook_add(UC_HOOK_CODE,advance,
                    begin=machine.symbols['op_halt'],end=machine.symbols['op_halt'])
                machine.call('script_frame_run',machine.runtime)
                self.assertEqual([machine.read(e+12) for e in entries],[2,3,2])
                self.assertEqual(machine.read(entries[1]+16),7)
                self.assertEqual(machine.read(machine.runtime+120),entries[2])
                self.assertEqual(machine.read(machine.runtime+156),1)
                self.assertEqual(len(machine.calls),2)
                machine.call('script_frame_run',machine.runtime)
                self.assertEqual(len(machine.calls),3)
                self.assertEqual(machine.read(entries[2]+12),2)
                self.assertEqual(machine.read(machine.runtime+144),3)

    def test_ring_interrupt_window_and_cpsr_restore(self):
        machine,_=self.machine()
        lengths=[]; current=[0]
        def observe(uc,address,size,_):
            if uc.reg_read(UC_ARM_REG_CPSR)&128: current[0]+=1
            elif current[0]: lengths.append(current[0]);current[0]=0
        machine.uc.hook_add(UC_HOOK_CODE,observe)
        for flags in [0xA0000013,0x60000013,0xA0000093]:
            machine.uc.reg_write(UC_ARM_REG_CPSR,flags)
            self.post(machine,5,[2,30])
            self.assertEqual(machine.uc.reg_read(UC_ARM_REG_CPSR),flags)
            machine.call('script_ring_take',machine.runtime,machine.input+0x5000)
            self.assertEqual(machine.uc.reg_read(UC_ARM_REG_CPSR),flags)
        self.assertTrue(lengths)
        self.assertLess(max(lengths),60)

    def test_frame_hook_preserves_registers_flags_and_original_literal(self):
        for armed in [0,1,2,0xffffffff]:
            for literal in [0xC031BB2C,0xC031C100]:
                with self.subTest(armed=armed,literal=literal):
                    machine,_=self.machine()
                    machine.write(machine.runtime+96,armed)
                    machine.write(0xC0083710,literal)
                    original=[0x33445500+i for i in range(13)]
                    for i,value in enumerate(original): machine.uc.reg_write(UC_ARM_REG_R0+i,value)
                    machine.uc.reg_write(UC_ARM_REG_SP,machine.stack+0xF0000)
                    machine.uc.reg_write(UC_ARM_REG_LR,machine.stop)
                    machine.uc.reg_write(UC_ARM_REG_CPSR,0x60000013)
                    machine.uc.emu_start(machine.symbols['script_frame_hook'],0xC0083700,count=100000)
                    original[0]=literal
                    self.assertEqual([machine.uc.reg_read(UC_ARM_REG_R0+i) for i in range(13)],original)
                    self.assertEqual(machine.uc.reg_read(UC_ARM_REG_SP),machine.stack+0xF0000)
                    self.assertEqual(machine.uc.reg_read(UC_ARM_REG_LR),machine.stop)
                    self.assertEqual(machine.uc.reg_read(UC_ARM_REG_CPSR),0x60000013)

    def test_pending_event_keeps_arguments_and_queue_for_next_frame(self):
        machine,_=self.machine()
        entries=[self.event_script(machine) for _ in range(3)]
        self.post(machine,3,[7])
        self.post(machine,3,[9])
        def advance(uc,address,size,_):
            if machine.read(machine.runtime+116)==1 and machine.read(machine.runtime+84)==3:
                machine.write(machine.timer,(machine.read(machine.timer)+500000)%150000000)
        machine.uc.hook_add(UC_HOOK_CODE,advance,
            begin=machine.symbols['op_halt'],end=machine.symbols['op_halt'])
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual([machine.variables(e)[1] for e in entries],[7,7,0])
        self.assertEqual(machine.read(machine.runtime+120),entries[2])
        self.assertEqual(machine.read(machine.runtime+128),7)
        self.assertEqual(machine.read(machine.runtime+108),1)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(entries[2])[1],7)
        self.assertEqual(machine.read(machine.runtime+108),2)
        self.assertEqual(machine.read(entries[1]+12),3)
        self.assertEqual(machine.read(entries[2]+12),2)

    def test_newly_posted_events_wait_for_next_cycle_snapshot(self):
        machine,_=self.machine()
        entry=self.event_script(machine)
        self.post(machine,3,[7])
        posted=[False]
        def enqueue(uc,address,size,_):
            if machine.read(machine.runtime+84)==3 and not posted[0]:
                head=machine.read(machine.runtime+104)
                at=machine.runtime+machine.symbols['RT_RING']+(head&63)*16
                machine.uc.mem_write(at,struct.pack('<4i',3,9,0,0))
                machine.write(machine.runtime+104,head+1)
                posted[0]=True
        machine.uc.hook_add(UC_HOOK_CODE,enqueue,
            begin=machine.symbols['op_halt'],end=machine.symbols['op_halt'])
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(entry),[1,7,1])
        self.assertEqual(machine.read(machine.runtime+104),2)
        self.assertEqual(machine.read(machine.runtime+108),1)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(entry),[1,9,2])

    def test_new_import_waits_for_own_ready_after_pending_cycle(self):
        machine,_=self.machine()
        entries=[]
        for _ in range(3):
            error,entry=machine.load(blob([0,33,2,0,9,0],stack=1,handlers=[(2,0,1)]))
            self.assertEqual(error,0)
            self.assertEqual(machine.run(entry,0),0)
            entries.append(entry)
        advancing=[True]
        def advance(uc,address,size,_):
            if advancing[0] and machine.read(machine.runtime+116)==1 and machine.read(machine.runtime+84)==2:
                machine.write(machine.timer,(machine.read(machine.timer)+500000)%150000000)
        machine.uc.hook_add(UC_HOOK_CODE,advance,
            begin=machine.symbols['op_halt'],end=machine.symbols['op_halt'])
        machine.call('script_frame_run',machine.runtime)
        imported=self.event_script(machine)
        advancing[0]=False
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(imported),[0,0,0])
        self.assertEqual(machine.read(imported+220),0)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(imported),[1,0,1])
        self.assertEqual(machine.read(imported+220),1)

    def test_fuel_fault_does_not_stop_other_scripts(self):
        machine,_=self.machine()
        loop=blob([0,28,1,0],handlers=[(2,0,1)])
        error,bad=machine.load(loop)
        self.assertEqual(error,0)
        self.assertEqual(machine.run(bad,0),0)
        healthy=self.event_script(machine)
        machine.write(machine.runtime+24,100)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(bad+12),3)
        self.assertEqual(machine.read(bad+16),1)
        self.assertEqual(machine.variables(healthy),[1,0,1])
        self.assertEqual(machine.read(machine.runtime+156),0)

    # ---- apps: korg.app, the open app, EXIT, frame and event filters, take and release ----

    def apps_base(self,machine,built):
        return machine.runtime+built.symbols['RT_APPS']

    def app_script(self,machine):
        """A script with an open handler (variable 0), a close handler (1) and a frame handler (2), each counting."""
        count=lambda slot: [4,slot,0,1,1,10,5,slot,0,0]
        code=[0]+count(0)+count(1)+count(2)
        error,entry=machine.load(blob(code,vars=3,stack=2,handlers=[(20,0,1),(21,0,11),(2,0,21)]))
        self.assertEqual(error,0)
        self.assertEqual(machine.run(entry,0),0)
        return entry

    def declare(self,machine,built,entries,groups=None):
        base=self.apps_base(machine,built)
        machine.write(base+4,len(entries))
        for i,entry in enumerate(entries):
            machine.write(base+8+12*i,entry)
            machine.write(base+8+12*i+4,machine.input+0x7000)
            machine.write(base+8+12*i+8,(groups or [0]*len(entries))[i])
        return base

    def drain(self,machine):
        out=[]
        while machine.call('script_ring_take',machine.runtime,machine.input+0x5000)[0]:
            out.append(struct.unpack('<4I',machine.uc.mem_read(machine.input+0x5000,16)))
        return out

    def test_exit_closes_the_open_app_before_any_plugin_sees_it(self):
        machine,built=self.machine()
        entry=self.app_script(machine)
        base=self.declare(machine,built,[entry])
        machine.write(base,entry)
        machine.write(machine.runtime+148,0xffffffff)
        self.assertEqual(self.input(machine,[0,13,1,0,0]),0xC0028380,'EXIT still reaches the firmware')
        self.assertEqual(machine.read(base),0,'the app is closed')
        self.assertEqual(self.drain(machine),[(21,entry,0,0)],'the app is told, no plugin sees the key')
        self.assertEqual(self.input(machine,[0,13,1,0,0]),0xC0028380)
        self.assertEqual(self.drain(machine),[(3,13,0,0)],'with no app open EXIT is an ordinary key for the plugins')

    def test_the_buttons_belong_to_the_open_app_but_encoders_and_pads_do_not(self):
        machine,built=self.machine()
        entry=self.app_script(machine)
        base=self.declare(machine,built,[entry])
        self.assertEqual(self.input(machine,[0,4,1,0,0]),0xC0028380,'a button passes on without an open app')
        self.drain(machine)
        machine.write(base,entry)
        self.assertEqual(self.input(machine,[0,4,1,0,0]),machine.stop,'the open app swallows the buttons')
        self.assertEqual(self.drain(machine),[(3,4,0,0)],'and the plugins still see them')
        self.assertEqual(self.input(machine,[1,0,0,255,0]),0xC0028380,'an encoder is not swallowed')
        self.assertEqual(self.input(machine,[4,5,0,100,1]),0xC0028380,'a pad is not swallowed')

    def test_app_events_reach_their_own_script_and_frame_only_an_open_app(self):
        machine,built=self.machine()
        one,two,plain=self.app_script(machine),self.app_script(machine),self.app_script(machine)
        base=self.declare(machine,built,[one,two])
        machine.write(machine.input+0x202C,1)
        machine.call('script_frame_run',machine.runtime)
        counts=lambda e: machine.variables(e)
        self.assertEqual([counts(one)[2],counts(two)[2],counts(plain)[2]],[0,0,1],'a closed app gets no frame, a plugin that is no app does')
        self.assertEqual(machine.call('script_app_open',0)[0],1)
        self.assertEqual(machine.read(base),one)
        machine.call('script_frame_run',machine.runtime)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual([counts(one)[0],counts(two)[0]],[1,0],'only the opened app got open')
        self.assertEqual([counts(one)[2],counts(two)[2],counts(plain)[2]],[2,0,3])
        self.assertEqual(machine.call('script_app_open',1)[0],0,'one app is open at a time')
        self.assertEqual(self.input(machine,[0,13,1,0,0]),0xC0028380)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual([counts(one)[1],counts(two)[1],counts(one)[2]],[1,0,2],'close reached the app, and its frames stopped')

    def test_open_needs_an_armed_plugin_clears_the_picture_and_marks_it_active(self):
        machine,built=self.machine()
        entry=self.app_script(machine)
        base=self.declare(machine,built,[entry])
        machine.uc.mem_write(machine.runtime+built.symbols['RT_DISPLAY'],b'\xaa'*1024)
        machine.write(entry+12,1)
        self.assertEqual(machine.call('script_app_open',0)[0],0,'a paused plugin does not open')
        self.assertEqual(machine.read(base),0)
        machine.write(entry+12,2)
        self.assertEqual(machine.call('script_app_open',5)[0],0,'no such app')
        self.assertEqual(machine.call('script_app_open',0)[0],1)
        self.assertEqual(bytes(machine.uc.mem_read(machine.runtime+built.symbols['RT_DISPLAY'],1024)),bytes(1024))
        self.assertEqual(machine.read(machine.runtime+180),1)
        self.assertEqual(self.drain(machine),[(20,entry,0,0)])
        machine.call('script_app_close',machine.runtime)
        self.assertEqual((machine.read(base),self.drain(machine)),(0,[(21,entry,0,0)]))
        self.assertEqual(bytes(machine.uc.mem_read(0xC06C226C,1)),b'\x01','closing makes the firmware repaint its main screen')
        machine.call('script_app_close',machine.runtime)
        self.assertEqual(self.drain(machine),[],'closing nothing says nothing')

    def test_the_app_closes_when_the_main_screen_is_gone(self):
        machine,built=self.machine()
        entry=self.app_script(machine)
        base=self.declare(machine,built,[entry])
        machine.write(base,entry)
        machine.write(machine.runtime+100,1)        # the main screen has been seen
        machine.write(machine.input+0x202C,3)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),0)
        machine.write(machine.input+0x202C,1)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.variables(entry)[1],1,'the app got close')

    def test_the_app_survives_the_screen_switch_that_is_still_on_its_way(self):
        machine,built=self.machine()
        entry=self.app_script(machine)
        base=self.declare(machine,built,[entry])
        machine.write(machine.runtime+100,1)
        machine.write(machine.input+0x202C,45)         # the menu is still the screen: the switch to the main screen is a queued message
        self.assertEqual(machine.call('script_app_open',0)[0],1)
        for frame in range(3):
            machine.call('script_frame_run',machine.runtime)
            self.assertEqual(machine.read(base),entry,'still open in frame %d'%frame)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),0,'a screen that never comes closes the app after the grace')
        self.assertEqual(machine.call('script_app_open',0)[0],1)
        machine.write(machine.input+0x202C,1)
        for frame in range(6): machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),entry,'with the main screen up the app stays open')

    def call_glue(self,machine,built,name,group,entry):
        machine.uc.mem_write(machine.input+0x6000,name.encode()+bytes(32-len(name)))
        machine.uc.mem_write(machine.input+0x6040,group.encode()+bytes(32-len(group)))
        machine.write(machine.runtime+88,entry)
        return machine.call('script_app_glue',machine.input+0x6000,machine.input+0x6040)

    def test_korg_app_registers_each_script_once_in_a_group_and_refuses_a_thirteenth(self):
        machine,built=self.machine()
        base=self.apps_base(machine,built)
        self.assertEqual(self.call_glue(machine,built,'Snake','GAMES',0x1000),(0,0))
        self.assertEqual(self.call_glue(machine,built,'Other','TOOLS',0x1000),(0,0),'the same script is the same app')
        self.assertEqual(self.call_glue(machine,built,'Klicker','TOOLS',0x2000),(1,0))
        self.assertEqual([machine.read(base+4),machine.read(base+8),machine.read(base+8+12+8)],[2,0x1000,1])
        self.assertEqual(machine.read(base+8+4),machine.input+0x6000,'the name stays in the block that holds it')
        error=contract_data()['error']['API_ARG']
        self.assertEqual(self.call_glue(machine,built,'X','MUSIC',0x3000),(0,error))
        self.assertEqual(self.call_glue(machine,built,'','GAMES',0x3000),(0,error))
        self.assertEqual(self.call_glue(machine,built,'X','GAMESX',0x3000),(0,error),'the group is compared whole')
        for i in range(10): self.assertEqual(self.call_glue(machine,built,'A%d'%i,'TOOLS',0x4000+i)[0],2+i)
        from tools.patch.script_hooks import MENU_STATE
        machine.write(MENU_STATE+36,0)
        self.assertEqual(self.call_glue(machine,built,'Late','GAMES',0x5000),(0xffffffff,0))
        self.assertEqual(machine.read(base+4),12)
        self.assertEqual(machine.read(MENU_STATE+36),0x37,'the import page says that no app place is left')

    def test_take_and_release(self):
        machine,built=self.machine()
        base=self.apps_base(machine,built)
        manager=machine.read(0xC03404C0)
        entry=self.app_script(machine)
        other=self.app_script(machine)
        machine.write(machine.runtime+88,other)
        machine.write(manager+0x2c,3)
        self.assertEqual(machine.call('script_display_take_glue')[0],0,'not while another screen shows')
        machine.write(manager+0x2c,1)
        machine.uc.mem_write(machine.runtime+built.symbols['RT_DISPLAY'],b'\xaa'*1024)
        self.assertEqual(machine.call('script_display_take_glue'),(1,0))
        self.assertEqual(machine.read(base),other)
        self.assertEqual(bytes(machine.uc.mem_read(machine.runtime+built.symbols['RT_DISPLAY'],1024)),bytes(1024))
        self.assertEqual(machine.call('script_display_take_glue')[0],1,'taking it twice is the same take')
        machine.write(machine.runtime+88,entry)
        self.assertEqual(machine.call('script_display_take_glue')[0],0,'one owner at a time')
        machine.call('script_display_release_glue')
        self.assertEqual(machine.read(base),other,'only the owner can release')
        machine.write(machine.runtime+88,other)
        machine.call('script_display_release_glue')
        self.assertEqual(machine.read(base),0)
        self.declare(machine,built,[entry])
        machine.write(machine.runtime+88,entry)
        self.assertEqual(machine.call('script_display_take_glue')[0],0,'an app is opened from the menu, not by itself')
        machine.write(machine.runtime+88,other)
        machine.call('script_display_take_glue')
        self.assertEqual(self.input(machine,[0,13,1,0,0]),0xC0028380)
        self.assertEqual(machine.read(base),0,'EXIT ends a takeover like it closes an app')
        self.assertEqual(bytes(machine.uc.mem_read(0xC06C226C,1)),b'\x01','the firmware repaints its main screen whole')
        self.assertEqual(self.drain(machine),[(21,other,0,0)])

    def test_public_patch_manifest_has_only_own_changes_and_registered_hooks(self):
        import hashlib
        from tools.patch.script_hooks import build,SITES,WORDS,RAM_BASE
        built=build(contract_data()['include'])
        patch=built.patch_manifest()
        self.assertEqual((patch['format'],patch['version'],patch['id']),('gelumpe-patch',1,'script-runtime'))
        self.assertEqual(len(patch['changes']),len(built.sections)+len(SITES)+len(WORDS)+3)
        for change,(address,data) in zip(patch['changes'],built.sections):
            self.assertEqual(change['file'],address-RAM_BASE+0x100)
            self.assertEqual(change['bytes'],data.hex())
            self.assertEqual(change['expect'],hashlib.sha256(b'\xff'*len(data)).hexdigest())
        first=len(built.sections)
        for change,(address,word,_) in zip(patch['changes'][first:first+len(SITES)],SITES):
            self.assertEqual(change['file'],address-RAM_BASE+0x100)
            self.assertEqual(change['expect'],hashlib.sha256(struct.pack('<I',word)).hexdigest())
            self.assertEqual(int.from_bytes(bytes.fromhex(change['bytes']),'little')>>24,0xea)
        self.assertEqual(len(patch['hooks']),19)
        self.assertEqual((patch['hooks'][3]['site'],patch['hooks'][3]['chain']),('0xC004C1B4','save'))
        self.assertEqual(patch['hooks'][0]['chain'],['key-dispatch','pattern-set'])
        self.assertEqual(patch['hooks'][0]['swallow'],True)
        self.assertEqual(patch['hooks'][1]['chain'],'frame')
        self.assertEqual(patch['hooks'][1]['position'],'after')
        self.assertEqual((patch['hooks'][2]['site'],patch['hooks'][2]['chain']),('0xC0038D68','start'))
        card=sum(built.symbols[end]-built.symbols[start] for start,end in [('script_early_hook','script_early_end'),('script_card_hook','script_card_wrapper_end'),('script_card_load','script_card_load_end'),('script_save_hook','script_save_hook_end')])
        self.assertEqual(len(patch['startPhase']),46)
        pairs=[('script_input_hook','script_input_pass_end'),('script_input_literals','script_input_literals_end'),
            ('script_frame_hook','script_frame_wrapper_end'),('script_frame_run','frame_gate_open'),('frame_return','script_frame_return_end'),
            ('script_ring_post','script_frame_hook'),('script_clock_update','script_play_glue'),('script_app_glue','script_display_take_glue')]
        pairs+=[('blechy_boot','blechy_boot_end'),('menu_arm','menu_arm_end'),('menu_arm_load','menu_arm_load_end'),('menu_settings_load','menu_settings_end'),('menu_needs_confirm','menu_confirm'),('menu_recount','menu_recount_end'),('menu_event_right','menu_hooks_end'),('led_meter_hook','look_hooks_end'),
            ('shortcut_input','shortcut_tick'),('shortcut_pool','shortcut_end'),('migrate_start','migrate_end'),('fx_card_load','fx_card_load_end')]
        spans=sum(built.symbols[end]-built.symbols[start] for start,end in pairs)
        self.assertEqual(sum(span['length'] for span in patch['startPhase']),spans+len(SITES)*4+len(WORDS)*4+184+card+len(built.sections[-1][1])+len(built.sections[0][1]))
        size=lambda change: len(change['bytes'])//2 if 'bytes' in change else change['copy']['length']
        written=set()
        for change in patch['changes']: written.update(range(change['file'],change['file']+size(change)))
        for span in patch['startPhase']:
            self.assertTrue(set(range(span['file'],span['file']+span['length']))<=written)
            self.assertGreater(len(span['why']),10)
        self.assertNotIn('expected',str(patch))

    def test_builder_rejects_original_literal_and_area_changes(self):
        from tools.patch.script_hooks import build,SITES,WORDS,RAM_BASE
        built=build(contract_data()['include'])
        base=bytearray(b'\xff'*0x200100)
        for address,value,_ in SITES:
            struct.pack_into('<I',base,address-RAM_BASE+0x100,value)
        for address,value,_ in WORDS:
            struct.pack_into('<I',base,address-RAM_BASE+0x100,value)
        struct.pack_into('<I',base,0xC0083710-RAM_BASE+0x100,0xC031BB2C)
        patched=built.apply(base)
        for address,_,name in SITES:
            word=struct.unpack_from('<I',patched,address-RAM_BASE+0x100)[0]
            self.assertEqual(word>>24,0xea)
        for address in [0xC0083710,built.layout['code'],built.layout['runtime'],built.layout['pool'],built.layout['card'],built.layout['input']]:
            changed=bytearray(base)
            changed[address-RAM_BASE+0x100]^=1
            with self.subTest(address=address),self.assertRaises(ValueError): built.apply(changed)

    # ---- Blechy, the app built into BLECH: his block lies in the image, outside the pool ----

    def arm_menu(self,machine,level=0):
        """The BLECH menu armed (EXIT was not held), at `level` of its screen."""
        from tools.patch.script_hooks import MENU_STATE
        machine.uc.mem_write(MENU_STATE,bytes(0x200))
        machine.write(MENU_STATE,1)
        machine.write(MENU_STATE+0xE0,level)
        return MENU_STATE

    def booted(self,machine,built):
        self.arm_menu(machine)
        machine.write(machine.runtime+96,0xffffffff)
        self.assertEqual(machine.call('blechy_boot',machine.runtime)[0],1)
        return machine.read(machine.runtime)

    def test_a_block_can_stay_outside_the_pool(self):
        from tools.patch.script_hooks import BLECHY_BLOCK
        machine,built=self.machine()
        block=built.sections[-1][1]
        error,entry=machine.call('script_load_block_ex',machine.runtime,BLECHY_BLOCK,len(block),1)
        self.assertEqual(error,0)
        size=built.symbols['SCRIPT_ENTRY_SIZE']
        vars=struct.unpack_from('<I',block,built.symbols['HDR_VAR_COUNT'])[0]
        self.assertEqual((machine.read(entry+4),machine.read(entry+8)),(BLECHY_BLOCK,entry+size),'the entry points at the image, its variables follow the entry')
        self.assertEqual(machine.read(machine.runtime+16),size+vars*4,'only the entry and the variables take room in the pool')
        _,copied=machine.call('script_load_block_ex',machine.runtime,BLECHY_BLOCK,len(block),0)
        _,again=machine.call('script_load_block',machine.runtime,BLECHY_BLOCK,len(block))
        self.assertEqual(machine.read(again+4),again+size,'script_load_block copies the block into the pool as before')
        self.assertEqual(machine.read(machine.runtime+16),size+vars*4+2*(size+len(block)+vars*4))

    def test_the_boot_without_an_armed_menu_changes_nothing(self):
        machine,built=self.machine()
        machine.call('script_runtime_init',machine.runtime,machine.arena,131072)
        machine.write(machine.runtime+96,0xffffffff)
        machine.write(machine.runtime,0xffffffff)
        self.assertEqual(machine.call('blechy_boot',machine.runtime)[0],0,'the menu reads FF: EXIT was held')
        self.assertEqual((machine.read(machine.runtime),machine.read(machine.runtime+96)),(0xffffffff,0xffffffff))

    def test_the_boot_loads_him_registers_him_hidden_runs_his_start_and_arms_the_runtime(self):
        machine,built=self.machine()
        entry=self.booted(machine,built)
        base=self.apps_base(machine,built)
        self.assertEqual(machine.read(entry+12),2,'his start body ran')
        self.assertEqual(machine.read(machine.runtime+96),1)
        hidden=built.symbols['SCRIPT_APPS_BUILTIN_GROUP']
        self.assertEqual([machine.read(base),machine.read(base+4),machine.read(base+8),machine.read(base+16)],[0,1,entry,hidden],'app 0 of a group no menu lists')
        self.assertEqual(machine.read(base+12),machine.read(entry+4)+built.symbols['HDR_NAME'])
        self.assertEqual(self.drain(machine),[],'booting posts nothing')

    def test_he_is_no_plugin_of_the_card_for_the_menu_the_store_and_the_leds(self):
        from tools.patch.script_hooks import MENU_STATE
        machine,built=self.machine()
        him=self.booted(machine,built)
        self.assertEqual(machine.call('menu_entry',0)[0],0,'no page of the PLUGINS group is his')
        machine.call('menu_recount')
        self.assertEqual(machine.read(MENU_STATE+40),0,'he is not counted')
        plugin=self.event_script(machine)
        self.assertEqual(machine.read(him),plugin,'the plugin of the card follows him in the list')
        self.assertEqual(machine.call('menu_entry',0)[0],plugin)
        self.assertEqual(machine.call('menu_entry',1)[0],0)
        machine.call('menu_recount')
        self.assertEqual(machine.read(MENU_STATE+40),1)

    def test_the_card_can_be_loaded_behind_him_and_a_damaged_file_leaves_him_alone(self):
        machine,built=self.machine()
        him=self.booted(machine,built)
        self.assertEqual(machine.read(him+12),2)
        self.assertEqual(machine.call('blechy_boot',machine.runtime)[0],1,'the loader starts over with him alone')
        again=machine.read(machine.runtime)
        self.assertEqual((machine.read(again),machine.read(again+12),machine.read(machine.runtime+4)),(0,2,again),'one entry, started again, armed')
        self.assertEqual(machine.read(machine.runtime+96),1)

    def test_the_app_limit_for_plugins_stays_twelve_with_him_in_the_table(self):
        machine,built=self.machine()
        self.booted(machine,built)
        base=self.apps_base(machine,built)
        for i in range(12): self.assertEqual(self.call_glue(machine,built,'A%d'%i,'TOOLS',0x4000+i)[0],1+i)
        self.assertEqual(self.call_glue(machine,built,'Late','GAMES',0x5000),(0xffffffff,0))
        self.assertEqual(machine.read(base+4),13)
        self.assertEqual(self.call_glue(machine,built,'Blechy','GAMES',machine.read(base+8)),(0,0),'his own call only names him')
        self.assertEqual(machine.read(base+8+8),built.symbols['SCRIPT_APPS_BUILTIN_GROUP'],'and his group stays hidden')

    def page(self,machine,screen=0x2D,level=3):
        self.arm_menu(machine,level)
        machine.write(machine.input+0x202C,screen)
        machine.write(machine.runtime+100,1)

    def test_he_opens_on_his_page_and_closes_when_the_firmware_leaves_it(self):
        machine,built=self.machine()
        him=self.booted(machine,built)
        base=self.apps_base(machine,built)
        self.page(machine)
        machine.call('blechy_follow')
        self.assertEqual(machine.read(base),him,'landing on the page opens him')
        self.assertEqual(self.drain(machine),[(20,him,0,0)],'he is told he is open')
        self.assertEqual(machine.read(machine.runtime+180),1,'the display is his')
        machine.call('blechy_follow')
        self.assertEqual(self.drain(machine),[],'once')
        for frame in range(6): machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),him,'he stays open for as long as the page shows, with no grace to run out')
        machine.write(machine.input+0x202C,3)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),0,'any other screen closes him')
        self.assertEqual(bytes(machine.uc.mem_read(0xC06C226C,1)),b'\x01','and the firmware repaints')
        machine.write(machine.input+0x202C,0x2D)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),him,'a second landing opens him again')

    def test_he_does_not_open_on_the_other_pages_of_the_menu_or_with_the_menu_off(self):
        machine,built=self.machine()
        him=self.booted(machine,built)
        base=self.apps_base(machine,built)
        for level in (0,1,2):
            self.page(machine,0x2D,level)
            machine.call('script_frame_run',machine.runtime)
            self.assertEqual(machine.read(base),0,'level %d of the screen is a menu'%level)
        self.page(machine,0x2D,3)
        machine.write(self.arm_menu(machine,3),0xffffffff)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),0,'an unarmed menu has no page of his')

    def test_his_page_does_not_close_a_plugin_app_and_a_plugin_app_does_not_close_him(self):
        machine,built=self.machine()
        him=self.booted(machine,built)
        base=self.apps_base(machine,built)
        app=self.app_script(machine)
        machine.write(base+4,2)
        machine.write(base+8+12,app)
        machine.write(base+8+12+4,machine.input+0x7000)
        machine.write(base+8+12+8,0)
        self.page(machine,1,0)
        machine.write(machine.runtime+100,1)
        self.assertEqual(machine.call('script_app_open',1)[0],1)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),app,'on the main screen the follower leaves the plugin app alone')
        machine.call('script_app_close',machine.runtime)
        frames=machine.variables(app)[2]
        self.page(machine)
        machine.call('script_frame_run',machine.runtime)
        machine.call('script_frame_run',machine.runtime)
        self.assertEqual(machine.read(base),him)
        self.assertEqual(machine.variables(app)[2],frames,'a closed app gets no frame')

    def test_the_keys_and_the_wheels_reach_the_firmware_on_his_page_and_only_the_touchpad_reaches_the_plugins(self):
        machine,built=self.machine()
        him=self.booted(machine,built)
        self.page(machine)
        machine.write(machine.runtime+148,0xffffffff)
        machine.call('script_frame_run',machine.runtime)
        self.drain(machine)
        for message,seen in [([0,0x0C,1,0,0],[]),([0,13,1,0,0],[]),([0,2,1,0,0],[]),([1,0,0,255,0],[]),([4,5,0,100,1],[]),
                             ([0,34,1,0,0],[(3,34,0,0)]),([5,1,144,2,88],[(8,400,600,1)]),([0,34,0,0,0],[(4,34,0,0)])]:
            with self.subTest(message=message):
                self.assertEqual(self.input(machine,message),0xC0028380,'the firmware gets everything: EDIT pages on, EXIT leaves')
                self.assertEqual(self.drain(machine),seen)
        self.page(machine,0x2D,0)
        self.assertEqual(self.input(machine,[0,34,1,0,0]),0xC0028380)
        self.assertEqual(self.drain(machine),[],'the other pages of the menu show the plugins nothing, as before')

if __name__=='__main__': unittest.main()
