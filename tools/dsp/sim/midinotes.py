"""MIDI note-ons on channel 1 (part 1) with notes 48, 60, 72 at velocity 100, PITCH knob at 64 and 0: the 0x2B/0x2C values
the opened voice gets, and the generator type word."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel, VOICE, VOICE_WORDS
from plugin_api24_cases import KNOBS
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None)
dsp = DspModel.attach(box.m)
msgs = []
om = dsp.message
dsp.message = lambda w: (msgs.append(list(w[:6])), om(w))[1]
for pitch in (64, 0):
    box.m.send([2, KNOBS["pitch"], 0, pitch, 0]); box.run(0.4)
    for note in (48, 60, 72):
        msgs.clear(); mark = len(dsp.gates)
        box.m.midi(bytes([0x90, note, 100])); box.run(0.2)
        opened = [g[1] for g in dsp.gates[mark:] if g[3]]
        box.m.midi(bytes([0x80, note, 0])); box.run(0.3)
        for v in opened[:1]:
            p = VOICE + VOICE_WORDS * v
            b = [m for m in msgs if m[1] == 0x2B and m[2] == p + 1][:2]
            c = [m for m in msgs if m[1] == 0x2C and m[3] == p + 2][:2]
            print('pitch', pitch, 'note', note, 'voice', v, '0x2B', [hex(m[3]) for m in b], '0x2C', [hex(m[4]) for m in c],
                  'type', hex(dsp.params.get(p + 3, -1)))
