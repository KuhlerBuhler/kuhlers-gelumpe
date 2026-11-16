"""Each part knob of part 1 at raw 0, 64, 127, then MIDI note 60: per note command, the first data words of its first message
for the opened voice (voice parameters written as voice offsets), and the part's pattern byte."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel, VOICE, VOICE_WORDS
from plugin_api24_cases import KNOBS
OFF = {"level": 24, "pan": 25, "pitch": 36, "resonance": 14, "egInt": 15, "modDepth": 18, "attack": 20, "ifxEdit": 34,
       "decay": 21, "oscEdit": 11, "modSpeed": 17}
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
msgs = []
om = dsp.message
dsp.message = lambda w: (msgs.append(list(w[1:9])), om(w))[1]
part_at = box.u32(sc.PATPTR) + 4 + 0x800
def norm(w, v):
    lo, hi = VOICE + VOICE_WORDS * v, VOICE + VOICE_WORDS * (v + 1)
    return ['v%x' % (x - lo) if lo <= x < hi else '%x' % x for x in w]
for name in sys.argv[2].split(','):
    rows = []
    for raw in (0, 64, 127):
        box.m.send([2, KNOBS[name], 0, raw, 0]); box.run(0.4)
        byte = box.m.uc.mem_read(part_at + OFF[name], 1)[0]
        msgs.clear(); mark = len(dsp.gates)
        box.m.midi(bytes([0x90, 60, 100])); box.run(0.05)
        v = [g[1] for g in dsp.gates[mark:] if g[3]][0]
        box.run(0.25)
        first = {}
        for m in msgs:
            if m[0] in (9, 0x31, 0x26, 0x1F, 0x32): continue
            n = norm(m[1:], v)
            L = {0: 3, 1: 4, 2: 3, 0x16: 4, 0x2B: 2, 0x2C: 3, 0x2D: 2, 0x2E: 2}.get(m[0], 6)
            if m[0] in (0, 1, 2, 0x16) and n[1] == '4c3d': continue
            first.setdefault((m[0], n[0] if m[0] not in (0x2C, 0x30) else n[1]), set()).add(' '.join(n[:L]))
        box.m.midi(bytes([0x80, 60, 0])); box.run(0.4)
        rows.append((byte, first))
    keys = set().union(*(r[1] for r in rows))
    print(name, 'byte', [r[0] for r in rows])
    for k in sorted(keys):
        vals = [r[1].get(k) for r in rows]
        if len({frozenset(x) if x else None for x in vals}) > 1:
            print('   %#x %s' % k, [sorted(x)[:4] if x else None for x in vals])
