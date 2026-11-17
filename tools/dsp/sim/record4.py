"""Record every host-port write from power-on: card with one made-up user sample (slot 501), part 1 plays it on every
`every`th step. Output: pickle {rec: [(ns, addr, words)], play_ns, gates}."""
import pickle, struct, sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import fat32, sampleset
import pswitch_cases
import shortcut_cases as sc
import ht_osc_cases as ho
from dsp_model import DspModel
payload = Path(sys.argv[1]).read_bytes()[0x100:]
out = sys.argv[2]
every = int(sys.argv[3]) if len(sys.argv) > 3 else 4
frames = int(sys.argv[4]) if len(sys.argv) > 4 else 24000
slot = int(sys.argv[5]) if len(sys.argv) > 5 else 500
rec = []
orig = DspModel._flush
def flush(self):
    x = self._xfer
    if x and x[2]:
        rec.append((self.m.time_ns, x[0], list(x[2])))
    return orig(self)
DspModel._flush = flush
_Dev = pswitch_cases.Dev
class Dev(_Dev):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        DspModel.attach(self.m)
pswitch_cases.Dev = Dev
image = fat32.format_image(64 * 1024 * 1024)
vol = fat32.Volume(image)
vol.write(f"KORG/{ho.folder(payload)}/e2sSample.all", sampleset.build({500: ("T501", frames)}))
vol.close()
pswitch_cases.card_image = lambda: image
box = sc.SBox(payload, None, card=True, seconds=10.0)
dsp = DspModel.attach(box.m)
print('boot transfers', len(rec), 'at', box.m.time_ns / 1e9, 'loading', box.m.loading())
rec_at = box.dev.u32(ho.PATTERN_IN_RAM) + 4 + 0x800
print('part 1 sample before', struct.unpack("<H", bytes(box.m.uc.mem_read(rec_at + 8, 2)))[0])
if slot >= 0:
    box.m.uc.mem_write(rec_at + 8, struct.pack("<H", slot - 1))
    box.m.send([0x01, 0x01, 0x00, 1, 0])
    box.run(0.3)
print('part 1 sample', struct.unpack("<H", bytes(box.m.uc.mem_read(rec_at + 8, 2)))[0])
for part in range(16):
    for step in range(64):
        at = sc.PART + sc.STRIDE * part + sc.STEPS + 12 * step
        on = part == 0 and step % every == 0
        box.poke(at, 1 if on else 0)
        for i, value in enumerate((60, 100, 1, 60) if on else (), 1):
            box.poke(at + i, value)
box.run(0.3)
play_ns = box.m.time_ns
reads = __import__('collections').Counter()
_rd = box.m.dsp_read
def rd():
    x = box.m.dsp_xfer
    if x and x[0] == 0xA9: reads[x[1]] += 1
    return _rd()
box.m.dsp_read = rd
sc.play(box)
box.run(1.0)
pickle.dump({'rec': rec, 'play_ns': play_ns, 'gates': dsp.gates}, open(out, 'wb'))
from collections import Counter
c = Counter()
for t, a, w in rec: c[a >> 20] += len(w)
print('reads', sorted((hex(a), n) for a, n in reads.items())[:60])
print(len(rec), 'transfers, words per MB', {hex(k): v for k, v in sorted(c.items())}, 'gates', dsp.gates[-6:], 'asserts', box.m.asserts)
