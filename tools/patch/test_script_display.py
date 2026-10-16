"""Native korg.display.* against the browser display model, without firmware bytes."""
import json
import pathlib
import random
import struct
import subprocess
import sys
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.patch.test_script_vm import contract_data, blob, UNICORN_AVAILABLE
from tools.patch import test_script_hooks as hooks_tests
from tools.patch.test_script_card import crash

DISPLAY_RAM = 0xC031B310
EXPECT = """
import { readFileSync } from "node:fs";
import { Display, drawFault } from "./src/script/display.mjs";
const input = JSON.parse(readFileSync(0, "utf8"));
const hex = d => Buffer.from(d.bytes).toString("hex");
const out = input.scenarios.map(ops => {
  const d = new Display();
  for (const [name, ...args] of ops) {
    if (name === "fault") drawFault(d, ...args);
    else d[name](...args);
  }
  return hex(d);
});
process.stdout.write(JSON.stringify(out));
"""

def expected(scenarios):
    out = subprocess.check_output(['node','--input-type=module','-e',EXPECT],input=json.dumps(dict(scenarios=scenarios)).encode(),cwd=ROOT)
    return [bytes.fromhex(item) for item in json.loads(out)]

GLUE = dict(clear='script_display_clear_glue',text='script_display_text_glue',number='script_display_number_glue',
            pixel='script_display_pixel_glue',rect='script_display_rect_glue',clearRect='script_display_clear_rect_glue',
            bitmap='script_display_bitmap_glue',textNumber='script_display_text_number_glue')

def picture(rng, width, bands, spare=0):
    return [rng.choice([0,0,rng.randrange(256),rng.randrange(256),255,rng.randrange(-2**31,2**31)]) for _ in range(width*bands+spare)]

def scenarios():
    fixed = [
        [['clear']],
        [['text','Hello, World 0123456789',0,0]],
        [['text','ABCDEFGHIJKLMNOPQRSTUVWXYZ abcde',120,3],['text','fghijklmnopqrstuvwxyz',0,12],['text','Gjpqy',60,60],['text','~}{|',0,57]],
        [['number',v,x,y] for v,x,y in [(0,0,0),(7,10,10),(-7,20,20),(2147483647,0,30),(-2147483648,0,40),(1000000,100,50),(10,127,5),(-1,126,63)]],
        [['pixel',0,0,1],['pixel',127,63,1],['pixel',127,0,1],['pixel',0,63,1],['pixel',5,5,1],['pixel',5,5,0],['pixel',64,32,1]],
        [['rect',0,0,128,64]],
        [['rect',127,63,128,64],['rect',100,50,50,50]],
        [['rect',3,5,10,3],['rect',20,6,1,10],['rect',30,0,5,64],['rect',40,7,9,2],['rect',50,8,3,8],['rect',60,15,3,2]],
        [['rect',0,0,128,64],['clearRect',10,10,20,20],['clearRect',120,60,40,40],['clearRect',0,0,1,1],['clearRect',50,7,4,10]],
        [['text','Klicks',0,0],['number',12,0,16],['rect',60,30,8,8],['clearRect',62,32,4,4]],
        [['textNumber','Klicks ',12,0,0],['textNumber','BPM',-120,0,10],['textNumber','',7,60,20],['textNumber','x'*31,5,0,30],['textNumber','Ende',2147483647,100,50]],
        [['textNumber','Edge',-2147483648,110,63],['textNumber','Zeile',0,124,2],['textNumber','A',99,127,0]],
        [['bitmap',[255,255,255,255],0,0,4]],
        [['bitmap',[1,2,4,8,16,32,64,128],0,0,8],['bitmap',[1,2,4,8,16,32,64,128],20,3,8],['bitmap',[1,2,4,8,16,32,64,128],40,-3,4]],
        [['bitmap',[0xFF]*32,-4,-4,16],['bitmap',[0xFF]*32,120,60,16],['bitmap',[0xAA]*16,-128,-64,8],['bitmap',[0x55]*8,127,63,4]],
        [['bitmap',[255]*128*8,0,0,128],['bitmap',[0,0,0]+[255]*8,5,5,3]],
        [['bitmap',[7,7,7,7,7,7,7,7,7],10,10,4]],
    ]
    rng = random.Random(1234)
    texts = ['A','Zeile 12','x'*31,'~!@#$%^&*()','Hello','0123456789']
    random_ones = []
    for _ in range(60):
        ops = []
        for _ in range(25):
            kind = rng.choice(['clear','text','number','pixel','rect','clearRect','rect','pixel'])
            if kind == 'clear': ops.append(['clear'] if rng.random() < 0.1 else ['pixel',rng.randrange(128),rng.randrange(64),1])
            elif kind == 'text': ops.append(['text',rng.choice(texts),rng.randrange(128),rng.randrange(64)])
            elif kind == 'number': ops.append(['number',rng.choice([0,1,-1,9,10,99,100,12345,-98765,2147483647,-2147483648,rng.randrange(-2**31,2**31)]),rng.randrange(128),rng.randrange(64)])
            elif kind == 'pixel': ops.append(['pixel',rng.randrange(128),rng.randrange(64),rng.randrange(2)])
            else: ops.append([kind,rng.randrange(128),rng.randrange(64),rng.randrange(1,129),rng.randrange(1,65)])
        random_ones.append(ops)
    for _ in range(80):
        ops = []
        for _ in range(6):
            width = rng.choice([1,2,3,7,8,9,16,31,32,33,56,64,127,128])
            bands = rng.randrange(1,9)
            ops.append(['bitmap',picture(rng,width,bands,rng.choice([0,0,width-1,3])),rng.randrange(-128,128),rng.randrange(-64,64),width])
            if rng.random() < 0.3: ops.append(['textNumber',rng.choice(texts),rng.randrange(-100000,100000),rng.randrange(128),rng.randrange(64)])
        random_ones.append(ops)
    return fixed + random_ones

@unittest.skipUnless(UNICORN_AVAILABLE,'Unicorn is required for native display tests')
class NativeDisplayTests(unittest.TestCase):
    BASE = 5              # the slot the picture starts at, so the handle's first half is not zero
    OWNER = 0x407000      # a script entry in the mapped input area, its variables follow at +0x1000

    def machine(self):
        m,built = hooks_tests.HookTests().machine()
        m.fb = m.runtime + built.symbols['RT_DISPLAY']
        m.apps = m.runtime + built.symbols['RT_APPS']
        m.write(self.OWNER+8,self.OWNER+0x1000)
        m.write(m.runtime+88,self.OWNER)        # the running script, as the VM sets it
        m.write(m.apps,self.OWNER)              # and it owns the display: an app that is open
        return m,built

    def run_ops(self,m,ops):
        m.uc.mem_write(m.fb,bytes(1024))
        for name,*args in ops:
            if name == 'clear': m.call(GLUE[name])
            elif name == 'text':
                m.uc.mem_write(m.input+0x6000,args[0].encode()+bytes(32-len(args[0])))
                m.call(GLUE[name],m.input+0x6000,args[1],args[2])
            elif name == 'number': m.call(GLUE[name],args[0] & 0xffffffff,args[1],args[2])
            elif name == 'textNumber':
                m.uc.mem_write(m.input+0x6000,args[0].encode()+bytes(32-len(args[0])))
                m.call(GLUE[name],m.input+0x6000,args[1] & 0xffffffff,args[2],args[3])
            elif name == 'bitmap':
                slots,x,y,width = args
                m.uc.mem_write(self.OWNER+0x1000+4*self.BASE,b''.join(struct.pack('<i',v) for v in slots))
                m.call(GLUE[name],self.BASE | len(slots) << 16,x & 0xffffffff,y & 0xffffffff,width)
            else: m.call(GLUE[name],*args)
        return bytes(m.uc.mem_read(m.fb,1024))

    def test_every_call_matches_the_browser_model_pixel_for_pixel(self):
        cases = scenarios()
        want = expected(cases)
        m,_ = self.machine()
        for i,(ops,wanted) in enumerate(zip(cases,want)):
            with self.subTest(case=i):
                self.assertEqual(self.run_ops(m,ops),wanted)

    def test_the_fuel_of_a_bitmap_call_covers_its_instructions(self):
        # the contract charges `cost` units for the call and `perItem` for each slot, at 10 instructions to a unit
        from unicorn import UC_HOOK_CODE
        api = next(a for a in contract_data()['apis'] if a['name'] == 'korg.display.bitmap')
        m,_ = self.machine()
        count = [0]
        m.uc.hook_add(UC_HOOK_CODE,lambda *_: count.__setitem__(0,count[0]+1))
        def instructions(slots,x,y,width):
            m.uc.mem_write(self.OWNER+0x1000+4*self.BASE,b''.join(struct.pack('<i',v) for v in slots))
            count[0] = 0
            m.call(GLUE['bitmap'],self.BASE | len(slots) << 16,x & 0xffffffff,y & 0xffffffff,width)
            return count[0]
        self.assertLessEqual(instructions([0],0,0,1),api['cost']*10)
        for width in (1,3,56,128):
            for bands in (1,8):
                for y in (-64,-9,-1,0,3,7,33,63):
                    for x in (0,100,-3):
                        slots = [255]*(width*bands)
                        self.assertLessEqual(instructions(slots,x,y,width),(api['cost']+len(slots)*api['perItem'])*10,(width,bands,y,x))

    def test_each_call_returns_zero_and_marks_the_display_active(self):
        m,_ = self.machine()
        self.assertEqual(m.read(m.runtime+180),0)
        self.assertEqual(m.call('script_display_pixel_glue',3,3,1),(0,0))
        self.assertEqual(m.read(m.runtime+180),1)
        for name,args in [('clear',()),('rect',(1,1,2,2)),('clearRect',(1,1,2,2)),('number',(5,0,0)),('bitmap',(1 | 8 << 16,0,0,8))]:
            m.write(m.runtime+180,0)
            self.assertEqual(m.call(GLUE[name],*args),(0,0),name)
            self.assertEqual(m.read(m.runtime+180),1,name)

    def test_only_the_owner_of_the_display_draws(self):
        m,_ = self.machine()
        for name,args in [('clear',()),('pixel',(3,3,1)),('rect',(0,0,8,8)),('clearRect',(0,0,8,8)),('number',(5,0,0)),('bitmap',(1 | 8 << 16,0,0,8))]:
            m.uc.mem_write(m.fb,b'\xaa'*1024)
            m.write(m.runtime+180,0)
            m.write(m.runtime+88,self.OWNER+4)      # another script runs
            self.assertEqual(m.call(GLUE[name],*args),(0,0),name)
            self.assertEqual(bytes(m.uc.mem_read(m.fb,1024)),b'\xaa'*1024,name)
            self.assertEqual(m.read(m.runtime+180),0,name)
        m.uc.mem_write(m.input+0x6000,b'text'+bytes(28))
        m.call(GLUE['text'],m.input+0x6000,0,0)
        self.assertEqual(bytes(m.uc.mem_read(m.fb,1024)),b'\xaa'*1024,'text')
        m.call(GLUE['textNumber'],m.input+0x6000,5,0,0)
        self.assertEqual(bytes(m.uc.mem_read(m.fb,1024)),b'\xaa'*1024,'textNumber')
        m.write(m.apps,0)                           # nobody owns it: nobody draws
        m.write(m.runtime+88,self.OWNER)
        m.call(GLUE['clear'])
        self.assertEqual(bytes(m.uc.mem_read(m.fb,1024)),b'\xaa'*1024)

    def test_the_picture_reaches_the_display_ram_only_while_someone_owns_the_display(self):
        m,_ = self.machine()
        m.call('script_display_rect_glue',0,0,128,8)
        manager = m.read(0xC03404C0)
        m.write(manager+0x2c,1)
        m.write(m.runtime+180,1)
        for owner,copy in [(self.OWNER,True),(0,False)]:
            m.write(m.apps,owner)
            m.uc.mem_write(DISPLAY_RAM,b'\x55'*1024)
            m.call('script_display_blit',m.runtime)
            self.assertEqual(bytes(m.uc.mem_read(DISPLAY_RAM,1024))==bytes(m.uc.mem_read(m.fb,1024)),copy,owner)

    def test_the_picture_is_copied_over_the_display_ram_only_while_the_main_screen_shows(self):
        m,_ = self.machine()
        m.call('script_display_rect_glue',0,0,128,8)
        manager = m.read(0xC03404C0)
        for state,active,copy in [(1,1,True),(3,1,False),(1,0,False),(1,1,True)]:
            m.uc.mem_write(DISPLAY_RAM,b'\x55'*1024)
            m.write(manager+0x2c,state)
            m.write(m.runtime+180,active)
            m.call('script_display_blit',m.runtime)
            self.assertEqual(bytes(m.uc.mem_read(DISPLAY_RAM,1024))==bytes(m.uc.mem_read(m.fb,1024)),copy,(state,active))
        for bad in (0,0xffffffff):
            m.write(0xC03404C0,bad);m.write(m.runtime+180,1)
            m.uc.mem_write(DISPLAY_RAM,b'\x55'*1024)
            m.call('script_display_blit',m.runtime)
            self.assertEqual(bytes(m.uc.mem_read(DISPLAY_RAM,1)),b'\x55')

    def test_a_faulted_script_leaves_its_name_line_and_error_on_the_display(self):
        m,_ = self.machine()
        error,entry = m.load(blob([0,1,5,1,0,13,9,0],vars=1,stack=2,handlers=[(2,0,1)]))
        self.assertEqual(error,0)
        self.assertEqual(m.run(entry,0),0)
        code = m.run(entry,2)
        self.assertEqual(code,contract_data()['error']['DIV_ZERO'])
        m.call('script_display_fault',m.runtime,entry)
        self.assertEqual(bytes(m.uc.mem_read(m.fb,1024)),bytes(1024),'a script that does not own the display leaves it alone')
        m.write(m.apps,entry)
        m.call('script_display_fault',m.runtime,entry)
        line = m.read(entry+24)
        self.assertGreater(line,-1)
        want = expected([[['fault','Test',line,'DIV_ZERO']]])[0]
        self.assertEqual(bytes(m.uc.mem_read(m.fb,1024)),want)
        self.assertEqual(m.read(m.runtime+180),1)

if __name__ == '__main__':
    unittest.main()
