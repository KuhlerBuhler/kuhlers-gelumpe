"""Native sequencer events from state comparison and the save hook, without firmware bytes."""
import pathlib
import struct
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import contract_data, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests
if UNICORN_AVAILABLE:
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import *

TRANSPORT, TEMPO, PATTERN, PART, STEP0, MUTE = 0xC06BC318, 0xC0691518, 0xC06B2420, 0xC06B2428, 0xC06904B0, 0xC06B2F9D

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native event tests')
class NativeEventTests(unittest.TestCase):
    def machine(self):
        m,built = hooks_tests.HookTests().machine()
        self.ids = {e['name']:e['id'] for e in contract_data()['events']}
        self.names = {v:k for k,v in self.ids.items()}
        return m,built

    def mutes(self,m,mask):
        for part in range(16): m.uc.mem_write(MUTE + 0x330 * part,bytes([(mask >> part) & 1]))

    def baseline(self,m):
        m.write(TRANSPORT,0); m.write(TEMPO,1600); m.write(PATTERN,0); m.write(PART,0); m.write(STEP0,0)
        self.mutes(m,0xffff)
        m.call('script_events_poll',m.runtime)
        self.assertEqual(self.drain(m),[])

    def drain(self,m):
        out = []
        while m.call('script_ring_take',m.runtime,m.input+0x5000)[0]:
            event,a,b,_ = struct.unpack('<4i',m.uc.mem_read(m.input+0x5000,16))
            out.append((self.names[event],a,b))
        return out

    def poll(self,m):
        m.call('script_events_poll',m.runtime)
        return self.drain(m)

    def test_the_first_poll_takes_the_state_as_it_is_without_events(self):
        m,_ = self.machine()
        m.write(TRANSPORT,1); m.write(TEMPO,999)
        m.call('script_events_poll',m.runtime)
        self.assertEqual(self.drain(m),[])
        self.assertEqual(self.poll(m),[])

    def test_transport_changes_become_play_stop_and_rec_once(self):
        m,_ = self.machine()
        self.baseline(m)
        for before,after,want in [(0,1,['play']),(1,0,['stop']),(0,2,['stop']),(2,3,['rec']),(3,4,[]),(4,1,['play']),(1,3,['rec']),(3,0,['stop']),(0,4,['rec']),(4,2,['stop']),(2,2,[])]:
            m.write(TRANSPORT,after)
            got = [e[0] for e in self.poll(m)]
            self.assertEqual(got,want,(before,after))

    def test_tempo_pattern_and_part_changes_carry_their_value(self):
        m,_ = self.machine()
        self.baseline(m)
        m.write(TEMPO,1234); m.write(PATTERN,77); m.write(PART,16)
        self.assertEqual(self.poll(m),[('tempo',1234,0),('patternChange',77,0),('partChange',16,0)])
        self.assertEqual(self.poll(m),[])

    def test_each_changed_mute_is_one_event_in_part_order(self):
        m,_ = self.machine()
        self.baseline(m)
        self.mutes(m,0xffff & ~(1 << 3) & ~(1 << 9))
        self.assertEqual(self.poll(m),[('mute',3,0),('mute',9,0)])
        self.mutes(m,0xffff & ~(1 << 9))
        self.assertEqual(self.poll(m),[('mute',3,1)])
        self.mutes(m,0)
        events = self.poll(m)
        self.assertEqual(len(events),15)
        self.assertEqual(events[0],('mute',0,0))

    def test_steps_follow_the_counter_and_every_fourth_is_a_beat(self):
        m,_ = self.machine()
        self.baseline(m)
        got = []
        for step in [1,2,3,4,5,63,0,0]:
            m.write(STEP0,step)
            got.append(self.poll(m))
        self.assertEqual(got[0:3],[[('step',1,0)],[('step',2,0)],[('step',3,0)]])
        self.assertEqual(got[3],[('step',4,0),('beat',0,0)])
        self.assertEqual(got[4],[('step',5,0)])
        self.assertEqual(got[5],[('step',63,0)])
        self.assertEqual(got[6],[('step',0,0),('beat',0,0)])
        self.assertEqual(got[7],[])

    def test_the_save_hook_posts_the_event_keeps_registers_and_continues_in_the_original_function(self):
        for config,posts in [(dict(),True),(dict(armed=0),False),(dict(armed=0xffffffff),False),(dict(boot=0x2000),False),(dict(panel=0),False),(dict(panel=0xffffffff),False)]:
            with self.subTest(config=config):
                m,_ = self.machine()
                m.write(m.runtime+96,config.get('armed',1))
                m.write(m.input+0x1018,config.get('boot',0))
                if 'panel' in config: m.write(0xC033E6F8,config['panel'])
                regs = [0x11110000+i for i in range(13)]
                for i,value in enumerate(regs): m.uc.reg_write(UC_ARM_REG_R0+i,value)
                sp = m.stack+0xF0000
                m.uc.reg_write(UC_ARM_REG_SP,sp)
                m.uc.reg_write(UC_ARM_REG_LR,0x22223333)
                m.uc.mem_map(0xC004C000,0x1000)
                m.uc.emu_start(m.symbols['script_save_hook'],0xC004C1B8,count=100000)
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_PC),0xC004C1B8)
                self.assertEqual([m.uc.reg_read(UC_ARM_REG_R0+i) for i in range(13)],regs)
                self.assertEqual(m.uc.reg_read(UC_ARM_REG_SP),sp-16)
                self.assertEqual(struct.unpack('<4I',m.uc.mem_read(sp-16,16)),(regs[4],regs[5],regs[6],0x22223333))
                self.assertEqual(self.drain(m),[('save',0,0)] if posts else [])

if __name__ == '__main__':
    unittest.main()
