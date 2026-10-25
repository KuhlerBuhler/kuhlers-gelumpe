"""Native pad geometry on synthetic steps; no firmware required."""
import pathlib
import json
import random
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools/patch')]
import pad_colors
try:
    import unicorn
    from unicorn import arm_const as A
except ImportError:
    unicorn = None


def geometry(steps, voice, index):
    if not steps[index][0]:
        return 0
    tails, starts = 0, False
    def tied(i, note):
        return (0 < i < 64 and steps[i][0] and steps[i-1][0]
                and steps[i-1][1] == 127
                and note in steps[i-1][4:8] and note in steps[i][4:8])
    for note in steps[index][4:8]:
        if not note:
            continue
        back = 0
        while back < 16 and tied(index-back, note):
            back += 1
        if not back:
            starts = True
            continue
        forward = 0
        while forward < 16 and tied(index+forward+1, note):
            forward += 1
        tails += 256 * (forward+1) // (back+forward+1)
    if starts:
        return int(voice >= 2 and sum(bool(n) for n in steps[index][4:8]) >= 2)
    return min(tails, 256)+2 if tails else 0


class PadMachine:
    MANAGER, PATTERN, MODEL = 0xC0300000, 0xC0310000, 0xC0320000
    STOP = 0x10000

    def __init__(self):
        pad_colors.use_build('hacktribe')
        at, code, self.symbols = pad_colors.build_code()
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        self.uc.mem_map(0xC0000000, 0x400000)
        self.uc.mem_map(self.STOP, 0x1000)
        self.uc.mem_map(0xC0690000, 0x2000)                  # the display's pointer to the pattern's accessor (0xC0691388), 0: the pattern in RAM
        self.uc.mem_write(at, code)
        self.write(0xC033E6A4, self.PATTERN)
        self.write(0xC0348884, self.MODEL)
        self.write(self.MANAGER+0xB58, 4)
        self.instructions = 0
        self.uc.hook_add(unicorn.UC_HOOK_BLOCK, self.count)

    def count(self, uc, at, size, data):
        self.instructions += size//4

    def write(self, at, value):
        self.uc.mem_write(at, struct.pack('<I', value))

    def steps(self, steps, voice=2, part=0):
        live = self.PATTERN + 0x804 + part*0x330
        self.uc.mem_write(live+2, bytes([voice]))
        self.uc.mem_write(live+0x30, b''.join(bytes(s) for s in steps))
        self.write(self.MANAGER+0xB60, part)

    def run(self, index):
        u = self.uc
        u.reg_write(A.UC_ARM_REG_CPSR, 0x53)
        for i in range(4, 12):
            u.reg_write(getattr(A, f'UC_ARM_REG_R{i}'), 0xA000+i)
        u.reg_write(A.UC_ARM_REG_R4, self.MANAGER)
        u.reg_write(A.UC_ARM_REG_R8, 0x2C+2*(index%16))
        self.write(self.MODEL+0x344, index//16)
        saved = [u.reg_read(getattr(A, f'UC_ARM_REG_R{i}')) for i in range(4, 12)]
        sp = 0xC03FF000
        u.reg_write(A.UC_ARM_REG_SP, sp)
        u.reg_write(A.UC_ARM_REG_LR, self.STOP)
        self.instructions = 0
        u.emu_start(self.symbols['pc_chord'], self.STOP, count=100000)
        if u.reg_read(A.UC_ARM_REG_PC) != self.STOP:
            raise AssertionError('geometry did not return')
        assert saved == [u.reg_read(getattr(A, f'UC_ARM_REG_R{i}')) for i in range(4, 12)]
        assert u.reg_read(A.UC_ARM_REG_SP) == sp
        assert u.reg_read(A.UC_ARM_REG_CPSR) & 0xFF == 0x53
        return u.reg_read(A.UC_ARM_REG_R0), self.instructions


@unittest.skipUnless(unicorn, 'Unicorn is required for native ARM tests')
class PadGeometryTests(unittest.TestCase):
    def test_uniform_four_note_ties_have_a_bounded_local_cost(self):
        m = PadMachine()
        steps = [[1, 127, 100, 1, 61, 65, 68, 73, 0, 0, 0, 0] for _ in range(64)]
        m.steps(steps)
        got, cost = m.run(16)
        self.assertEqual(got, geometry(steps, 2, 16))
        self.assertLessEqual(cost, 1500)

    def test_all_tail_fractions_and_nonuniform_note_chains(self):
        m = PadMachine()
        for notes in ([61,0,0,0],[61,65,0,0],[61,65,68,0],[61,65,68,73],[0,65,0,73],[61,61,61,61]):
            for back in range(1,17):
                for forward in range(17):
                    steps = [[int(i <= back+forward),127,100,1,*notes,0,0,0,0] for i in range(64)]
                    m.steps(steps)
                    self.assertEqual(m.run(back)[0], geometry(steps,2,back), (notes,back,forward))
        rng = random.Random(341)
        for case in range(64):
            steps = []
            notes = [61,65,68,73]
            for i in range(64):
                if case%2:
                    rng.shuffle(notes)
                else:
                    notes[rng.randrange(4)] = rng.choice((0,61,65,68,73))
                steps.append([1,127 if i%17 else case%128,100,i%2,*notes,0,0,0,0])
            m.steps(steps,case%4)
            for i in range(64):
                self.assertEqual(m.run(i)[0], geometry(steps,case%4,i), (case,i))

    def test_the_viewed_pattern_gives_the_steps_while_the_display_points_at_it(self):
        m = PadMachine()
        viewed, accessor = 0xC0330000, 0xC0340000
        live = [[1,127,100,1,61,65,68,73,0,0,0,0] for _ in range(64)]
        other = [[1,127,100,1,61,0,0,0,0,0,0,0] for _ in range(64)]
        m.steps(live)
        self.assertEqual(m.run(16)[0], geometry(live, 2, 16))
        m.write(accessor + 4, viewed)
        m.uc.mem_write(viewed + 0x806, bytes([2]))
        m.uc.mem_write(viewed + 0x834, b''.join(bytes(step) for step in other))
        m.write(0xC0691388, accessor)
        self.assertEqual(m.run(16)[0], geometry(other, 2, 16))
        m.write(0xC0691388, 0)
        self.assertEqual(m.run(16)[0], geometry(live, 2, 16))

    def test_inputs_and_persistent_state_are_unchanged(self):
        m = PadMachine()
        steps = [[1,127,100,1,61,65,68,73,0,0,0,0] for _ in range(64)]
        m.steps(steps)
        m.uc.mem_write(pad_colors.STATE,b'\xff'*(pad_colors.STATE_END-pad_colors.STATE))
        regions = [(m.PATTERN,0x5000),(m.MANAGER,0xC00),(pad_colors.STATE,0x40)]
        before = [bytes(m.uc.mem_read(at,n)) for at,n in regions]
        for i in range(64):
            m.run(i)
        self.assertEqual(before,[bytes(m.uc.mem_read(at,n)) for at,n in regions])

    def test_memory_writes_stay_inside_the_bounded_stack_frame(self):
        m = PadMachine()
        m.steps([[1,127,100,1,61,65,68,73,0,0,0,0] for _ in range(64)])
        writes = []
        m.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,
                      lambda u,access,at,size,value,data: writes.append((at,size)))
        m.run(16)
        self.assertTrue(writes)
        self.assertTrue(all(0xC03FF000-40 <= at and at+size <= 0xC03FF000 for at,size in writes),writes)

    def test_synth_code_is_unchanged_and_sampler_fits_its_budget(self):
        try:
            for build,name in [('hacktribe','pad-colors'),('synth','pad-colors-synth')]:
                old = json.loads((ROOT/f'data/patches/{name}.json').read_text())
                old_code = bytes.fromhex(old['changes'][0]['bytes'])
                pad_colors.use_build(build)
                at,code,_ = pad_colors.build_code()
                self.assertEqual(at,pad_colors.CODE_AT)
                if build=='synth':
                    self.assertEqual(code,old_code)
                else:
                    self.assertLessEqual(len(code),2684+768)
                self.assertLessEqual(at+len(code),pad_colors.CODE_END)
        finally:
            pad_colors.use_build('hacktribe')

    def test_geometry_matches_independent_reference_at_boundaries_and_edits(self):
        m = PadMachine()
        rng = random.Random(0xB1EC)
        for voice in range(4):
            for length in (1, 2, 16, 17, 32, 64):
                steps = [[int(i < length), 127 if i+1 < length else 126, 100, i%2,
                          61, 65, 68, 73, 0, 0, 0, 0] for i in range(64)]
                m.steps(steps, voice)
                for index in range(64):
                    self.assertEqual(m.run(index)[0], geometry(steps, voice, index), (voice,length,index))
        for case in range(64):
            steps = [[rng.randrange(2), rng.choice((0,126,127)), 100, rng.randrange(2),
                      *[rng.choice((0,61,65,68,73)) for _ in range(4)], 0,0,0,0] for _ in range(64)]
            voice = case%4
            m.steps(steps, voice, case%16)
            for index in (0,1,15,16,31,32,47,48,62,63):
                self.assertEqual(m.run(index)[0], geometry(steps, voice, index), (case,index))

    def test_same_pointer_edits_context_and_unseen_steps_take_effect(self):
        m = PadMachine()
        steps = [[1,127,100,1,61,65,68,73,0,0,0,0] for _ in range(64)]
        for edit in (None, (31,1,126), (15,4,0), (16,0,0), (17,3,0), (17,5,72)):
            if edit:
                i,j,value = edit
                steps[i][j] = value
            for voice in range(4):
                for part in (0,7,15):
                    m.steps(steps, voice, part)
                    for index in (15,16,17,31,32):
                        self.assertEqual(m.run(index)[0], geometry(steps,voice,index), (edit,voice,part,index))
        for at,value in ((m.MANAGER+0xB58,0),(m.MANAGER+0xB60,16),(0xC033E6A4,0),(0xC0348884,0)):
            old = bytes(m.uc.mem_read(at,4))
            m.write(at,value)
            self.assertEqual(m.run(16)[0],0)
            m.uc.mem_write(at,old)


if __name__ == '__main__':
    unittest.main()
