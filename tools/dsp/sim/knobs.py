"""Turn each part knob of part 1 to two values; print which DSP parameters change (relative to the part switch base)."""
import sys
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import menu_cases
from dsp_model import DspModel, PART_ON, PART_STRIDE
from plugin_api24_cases import KNOBS
payload = Path(sys.argv[1]).read_bytes()[0x100:]
dev = menu_cases.boot(payload, None)
dsp = DspModel.attach(dev.m)
base = dsp.part_base
def turn(index, raw):
    before = dict(dsp.params); c0 = dict(dsp.commands)
    dev.m.send([2, index, 0, raw, 0]); dev.run(0.4)
    ch = {p: v for p, v in dsp.params.items() if before.get(p) != v}
    cmds = {k: v - c0.get(k, 0) for k, v in dsp.commands.items() if v != c0.get(k, 0)}
    return ch, cmds
for name, index in KNOBS.items():
    rows = []
    for raw in (20, 100, 64):
        ch, cmds = turn(index, raw)
        rows.append(({(hex(p - base) if 0 <= p - base < PART_STRIDE else hex(p)): hex(v) for p, v in ch.items()}, {hex(k): v for k, v in cmds.items() if k not in (1, 0x31)}))
    print(name, rows)
