"""Run the extracted DSP program from 0xFFA00000 in the GNU sim, regions from map.json."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import mkelf
src, run = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]
meta = json.load(open(os.path.join(src, 'map.json')))
segs = [(m['target'], open(os.path.join(src, m['file']), 'rb').read()) for m in meta]
elf = os.path.join(os.path.dirname(__file__), 'boot.elf')
mkelf.write(elf, segs, 0xFFA00000)
cmd = [run, '--environment', os.environ.get('ENV','virtual'), '--model', 'bf527']
regions = [(0, 0x4000000)] if os.environ.get('ENV') == 'operating' else [(0, 0x4000000), (0xFF800000, 0x8000), (0xFF900000, 0x8000), (0xFFA00000, 0x14000)]
for base, size in regions:
    cmd += ['--memory-region', f'0x{base:X},0x{size:X}']
cmd += extra + [elf]
print(' '.join(cmd), file=sys.stderr)
sys.exit(subprocess.run(cmd).returncode)
