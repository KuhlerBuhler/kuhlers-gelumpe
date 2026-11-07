"""Execute next-pipeline ARM against generated ring data and the independent reader."""
import struct
import unittest
from pathlib import Path
from emulator import ScopeMachine, assemble, ORIGIN, CTX, RING, RING_BYTES, TICKS, STACK, SOURCE
from measurement_reference import RingReader, State, CAPACITY
from unicorn.arm_const import UC_ARM_REG_R4

SIZE = 19328


class StreamMachine(ScopeMachine):
    def __init__(self):
        super().__init__()
        self.code=assemble((SOURCE/'stream_capture.s').read_text(),origin=ORIGIN)
        self.uc.mem_write(ORIGIN,self.code.bytes)
        self.uc.mem_write(CTX-16,bytes([0xA6])*16+bytes(SIZE)+bytes([0xB7])*16)
        self.word(CTX+8,0xFF90197C)
        self.state[0]=1;self.state[3]=0xFF90197C

    def poll(self,position,tick):
        self.tick(tick)
        self.state[2]=RING+(position%CAPACITY)*4
        for frame in range(max(0,position-CAPACITY),position):
            self.ring[frame%CAPACITY*4:frame%CAPACITY*4+4]=struct.pack('<I',frame)
        status=self.call('stream_poll',CTX)
        return status,bytes(self.uc.mem_read(CTX+128,self.word(CTX+12)))


class StreamTests(unittest.TestCase):
    def test_entire_stream_exactly_matches_reference_despite_poll_jitter(self):
        m=StreamMachine();r=RingReader();position=1200;tick=0;collected=[]
        self.assertEqual(m.poll(position,tick),(1,b''))
        r.begin(State(RING+(position%CAPACITY)*4,tick,0xFF90197C))
        for ms in (40,43,38,47,40,41,36,40,39,45):
            position+=ms*48;tick+=ms
            before=State(RING+(position%CAPACITY)*4,tick,0xFF90197C)
            spans=r.begin(before)
            status,data=m.poll(position,tick)
            self.assertEqual(status,0)
            ring={i%CAPACITY:i for i in range(position-CAPACITY,position)}
            expected=b''.join(struct.pack('<I',ring[(addr-RING)//4+i]) for addr,n in spans for i in range(n//4))
            self.assertEqual(data,r.finish(before,expected))
            collected.extend(v[0] for v in struct.iter_unpack('<I',data))
        self.assertEqual(collected,list(range(1200-256,position-256)))
        self.assertEqual(m.word(CTX+16),len(collected))

    def test_gap_is_detected_and_requires_reprime(self):
        m=StreamMachine();m.poll(1200,0)
        self.assertEqual(m.poll(6000,100),(4,b''))
        self.assertEqual(m.word(CTX),0)
        self.assertEqual(m.poll(7920,140),(1,b''))

    def test_source_loss_and_recording_never_read_audio(self):
        for slot,value in ((3,0xFF901A94),(10,1),(0,0)):
            m=StreamMachine();m.poll(1200,0);m.state[slot]=value
            m.calls.clear()
            self.assertEqual(m.poll(3120,40),(3,b''))
            self.assertFalse(any(c[0]=='read' and c[1]!=0xFF9031D0 for c in m.calls))

    def test_slow_transfer_is_rejected_without_advancing_reader(self):
        m=StreamMachine();m.poll(1200,0)
        m.after_pcm=lambda machine:machine.tick(120)
        self.assertEqual(m.poll(3120,40),(5,b''))
        self.assertEqual(m.word(CTX),0)

    def test_no_new_samples_does_not_publish_old_audio(self):
        m=StreamMachine();m.poll(1200,0)
        self.assertEqual(m.poll(1200,5),(0,b''))
        self.assertEqual(m.word(CTX+16),0)

    def test_tick_wrap_and_memory_register_boundaries(self):
        m=StreamMachine();m.poll(1200,0xFFFFFFF0)
        preserved=[0x76540000+i for i in range(8)]
        for i,value in enumerate(preserved):m.uc.reg_write(UC_ARM_REG_R4+i,value)
        self.assertEqual(m.poll(3120,24)[0],0)
        for i,value in enumerate(preserved):self.assertEqual(m.uc.reg_read(UC_ARM_REG_R4+i),value)
        self.assertEqual(bytes(m.uc.mem_read(CTX-16,16)),bytes([0xA6])*16)
        self.assertEqual(bytes(m.uc.mem_read(CTX+SIZE,16)),bytes([0xB7])*16)
        for address,size in m.writes:
            self.assertTrue(CTX<=address and address+size<=CTX+SIZE or STACK-4096<=address and address+size<=STACK)

    def test_arm_stream_preserves_known_attack_and_decay_end_to_end(self):
        from measurement_reference import AttackCapture, signal_attack_decay
        import math
        signal=signal_attack_decay(onset_ms=100,decay_ms=100,duration_ms=900)
        m=StreamMachine();capture=AttackCapture(window_ms=512)
        position=1200;tick=25
        def poll():
            m.tick(tick);m.state[2]=RING+(position%CAPACITY)*4
            for frame in range(max(0,position-CAPACITY),position):
                m.ring[frame%CAPACITY*4:frame%CAPACITY*4+4]=signal[frame*4:frame*4+4]
            status=m.call('stream_poll',CTX)
            data=bytes(m.uc.mem_read(CTX+128,m.word(CTX+12)))
            capture.append(data)
            return status
        self.assertEqual(poll(),1)
        for ms in [40,43,38,47,40,41,36]*3:
            position+=ms*48;tick+=ms
            self.assertEqual(poll(),0)
        self.assertTrue(capture.done)
        self.assertEqual(capture.trigger,100*48+1-(1200-256))
        for elapsed in (50,100,200):
            expected=24000*math.exp(-elapsed/100)
            actual=capture.columns()[(10+elapsed)//4]
            self.assertLess(abs(actual-expected)/expected,.06)


if __name__=='__main__':unittest.main()
