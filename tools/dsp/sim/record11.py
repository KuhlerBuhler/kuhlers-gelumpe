"""After boot: every peripheral register the firmware has ever written, grouped by 4 KiB page."""
import sys, collections
sys.path[:0] = ["tools/emu", "tools/patch", "."]
from pathlib import Path
import shortcut_cases as sc
box = sc.SBox(Path(sys.argv[1]).read_bytes()[0x100:], None, card=False, seconds=10.0)
pages = collections.defaultdict(list)
for a, v in box.m.regs.items():
    if 0x01C00000 <= a < 0x02000000: pages[a >> 12 << 12].append((a, v))
for p in sorted(pages):
    print(hex(p), len(pages[p]), [f'{a & 0xFFF:#x}={v:#x}' for a, v in sorted(pages[p])[:8]])
