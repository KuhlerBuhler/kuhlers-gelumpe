"""Each part knob of part 1 at two values, pad 1 after each: the DSP parameters whose value differs between the two notes."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
from dsp_model import DspModel, PART_STRIDE, VOICE, VOICE_WORDS, TEMPLATE
from plugin_api24_cases import KNOBS, CUTOFF_ENCODER
payload = Path(sys.argv[1]).read_bytes()[0x100:]
box = sc.SBox(payload, None)
dsp = DspModel.attach(box.m)
base = dsp.part_base
log = []
orig = dsp.set_param
def sp(param, value, word=None):
    log.append((param, value)); return orig(param, value, word)
dsp.set_param = sp
msgs = []
om = dsp.message
def msg(words):
    if len(words) > 2 and words[1] not in (0, 1, 2, 9, 0x16, 0x26, 0x31): msgs.append(tuple(words[1:12]))
    return om(words)
dsp.message = msg
def name(p):
    if 0 <= p - base < PART_STRIDE * 16: return ('part%d' % ((p - base) // PART_STRIDE), hex((p - base) % PART_STRIDE))
    if 0 <= p - VOICE < VOICE_WORDS * 24: return ('voice', hex((p - VOICE) % VOICE_WORDS))
    if 0 <= p - TEMPLATE < VOICE_WORDS * 16: return ('tmpl%d' % ((p - TEMPLATE) // VOICE_WORDS), hex((p - TEMPLATE) % VOICE_WORDS))
    return (hex(p),)
def note():
    log.clear(); msgs.clear(); box.pad(0); box.run(0.3)
    d = {}
    for p, v in log:
        if not (0x4C3B <= p <= 0x4C3F): d[name(p)] = v
    for m in msgs: d.setdefault(('cmd%#x' % m[0],), set()).add(' '.join('%x' % w for w in m[1:]))
    return d
def knob(index, raw):
    box.m.send([2, index, 0, raw, 0]); box.run(0.4)
def enc(delta):
    for _ in range(abs(delta)):
        box.m.send([3, CUTOFF_ENCODER, 0, 1 if delta > 0 else 0x7F, 0]); box.run(0.05)
    box.run(0.3)
note(); note()
ctrl = [(n, (lambda i: lambda r: knob(i, r))(i), (20, 110)) for n, i in KNOBS.items()]
for n, set_, (a, b) in ctrl:
    set_(a); x = note(); set_(b); y = note(); set_(64); note()
    diff = {k: (x.get(k), y.get(k)) for k in set(x) | set(y) if x.get(k) != y.get(k) and k[0] != ('0x4c3d',)}
    print(n, {('/'.join(k)): tuple(None if z is None else (sorted(z) if isinstance(z, set) else hex(z)) for z in v) for k, v in sorted(diff.items())})
