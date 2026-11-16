"""Build and run a harness ELF: DSP regions + MMR area as RAM + our own code at 0x03000000.

Usage: harness.py REGIONDIR RUN ASMFILE [sim args]. Exit status of the sim is printed; stdout passes through.
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkelf
here = os.path.dirname(os.path.abspath(__file__))
src, run, asm = sys.argv[1], sys.argv[2], sys.argv[3]
extra = sys.argv[4:]
BINUTILS = os.environ.get('BFIN_BINUTILS', os.path.join(os.path.dirname(here), 'binutils-build2'))
AS = os.path.join(BINUTILS, 'gas/as-new')
OBJCOPY = os.path.join(BINUTILS, 'binutils/objcopy')
HARNESS = 0x03000000
base = os.path.splitext(asm)[0]
subprocess.run([AS, asm, '-o', base + '.o'], check=True)
subprocess.run([OBJCOPY, '-O', 'binary', '-j', '.text', base + '.o', base + '.bin'], check=True)
meta = json.load(open(os.path.join(src, 'map.json')))
segs = [(m['target'], open(os.path.join(src, m['file']), 'rb').read()) for m in meta]
segs.append((HARNESS, open(base + '.bin', 'rb').read()))
elf = base + '.elf'
mkelf.write(elf, segs, HARNESS)
cmd = [run, '--environment', 'virtual', '--model', 'bf527']
for b, size in [(0, 0x4000000), (0xFF800000, 0x8000), (0xFF900000, 0x8000), (0xFFA00000, 0x14000),
                (0xFFC00000, 0x3FF000)]:
    cmd += ['--memory-region', f'0x{b:X},0x{size:X}']
cmd += extra + [elf]
p = subprocess.run(cmd)
print(f'[sim exit {p.returncode}]', file=sys.stderr)
