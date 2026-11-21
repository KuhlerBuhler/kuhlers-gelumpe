"""Count every peripheral write (not the DSP host port) in 1 s idle and 1 s playing a user sample on part 1."""
import struct, sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import fat32, sampleset, pswitch_cases
import shortcut_cases as sc
import ht_osc_cases as ho
from machine import DSP_CTRL, DSP_DATA
payload = Path(sys.argv[1]).read_bytes()[0x100:]
image = fat32.format_image(64 * 1024 * 1024)
vol = fat32.Volume(image)
vol.write(f"KORG/{ho.folder(payload)}/e2sSample.all", sampleset.build({500: ("T501", 24000)}))
vol.close()
pswitch_cases.card_image = lambda: image
box = sc.SBox(payload, None, card=True, seconds=10.0)
rec_at = box.dev.u32(ho.PATTERN_IN_RAM) + 4 + 0x800
box.m.uc.mem_write(rec_at + 8, struct.pack("<H", 499))
box.m.send([0x01, 0x01, 0x00, 1, 0]); box.run(0.3)
for part in range(16):
    for step in range(64):
        at = sc.PART + sc.STRIDE * part + sc.STEPS + 12 * step
        on = part == 0 and step % 4 == 0
        box.poke(at, 1 if on else 0)
        for i, value in enumerate((60, 100, 1, 60) if on else (), 1):
            box.poke(at + i, value)
box.run(0.3)
cur = {}
vals = {}
_w = box.m.write
def w(a, v):
    if a not in (DSP_CTRL, DSP_DATA):
        cur[a] = cur.get(a, 0) + 1
        vals.setdefault(a, set())
        if len(vals[a]) < 4: vals[a].add(v)
    return _w(a, v)
box.m.write = w
box.run(1.0); idle = dict(cur); cur.clear()
sc.play(box); box.run(1.0); play = dict(cur)
print('page    addr        idle  play  values')
for a in sorted(set(idle) | set(play)):
    print(f'{a >> 12 << 12:#010x} {a:#010x} {idle.get(a,0):6} {play.get(a,0):6}  {[hex(x) for x in sorted(vals[a])]}')
