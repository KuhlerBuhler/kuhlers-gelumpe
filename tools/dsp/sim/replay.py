"""Replay recorded host-port traffic into the real DSP program in the GNU sim and read the output peak.

replay.py REGIONDIR RUN REC.pkl [--lead MS] [--frames-per-ms 48]
Writes before (play - lead) are applied without audio; from there on, every ms of device time runs 12 blocks of 4 frames
through the DSP's own frame function 0xFFA0141A, as the audio loop 0xFFA0010C does. Every ms the peak words 0xFF9030F4/F8
and the last output frame go to stdout.
"""
import argparse, json, os, pickle, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkelf
here = os.path.dirname(os.path.abspath(__file__))
BINUTILS = os.environ.get('BFIN_BINUTILS', os.path.join(os.path.dirname(here), 'binutils-build2'))
AS = os.path.join(BINUTILS, 'gas/as-new')
OBJCOPY = os.path.join(BINUTILS, 'binutils/objcopy')
HARNESS, SCRIPT, OUTBUF = 0x03000000, 0x02000000, 0x03100000
MAILBOX = 0xFF900A34

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('run'); ap.add_argument('rec')
ap.add_argument('--lead', type=float, default=100)
ap.add_argument('--tail', type=float, default=None, help='ms after play to stop')
ap.add_argument('--blocks-per-ms', type=int, default=12)
ap.add_argument('--dump', action='append', default=[])
args = ap.parse_args()
DUMPS = [tuple(int(x, 0) for x in d.split(',')) for d in args.dump]
data = pickle.load(open(args.rec, 'rb'))
rec, play = data['rec'], data['play_ns'] / 1e6
start = play - args.lead
end = play + args.tail if args.tail is not None else rec[-1][0] / 1e6 + 1

script = bytearray()
def op(*w): script.extend(struct.pack(f'<{len(w)}I', *w))
ms = start
mailboxes = 0
for t, addr, words in rec:
    t /= 1e6
    if t > end: break
    while t >= ms + 1 and ms < end:
        op(3, args.blocks_per_ms); op(4); ms += 1
    if t < start:
        ms = start
    body = struct.pack(f'<{len(words)}H', *words)
    body += b'\0' * (-len(body) % 4)
    op(2 if addr == MAILBOX else 1, addr, len(words)); script.extend(body)
    mailboxes += addr == MAILBOX
while ms < end:
    op(3, args.blocks_per_ms); op(4); ms += 1
for a, n in DUMPS:
    op(5, a, n)
op(0)

asm = r'''
	.text
_start:
	SP.L = 0x4600; SP.H = 0xff90;
	USP = SP; FP = SP; SP += -12;
	R0 = 0x400 (Z); R0 <<= 5;
	P1.L = 0x0878; P1.H = 0x01f1; CALL (P1);
	R0 = 0x3b (X);
	P1.L = 0x95f0; P1.H = 0xffa0; CALL (P1);
	P1.L = 0xec38; P1.H = 0x01f0; CALL (P1);
	P1.L = 0x08c8; P1.H = 0x01f1; CALL (P1);
	R0.L = 0x0ccc; R0.H = 0xff90;
	P1.L = 0x0164; P1.H = 0; CALL (P1);
	P1.L = 0xc8d4; P1.H = 0x01f0; CALL (P1);
	/* script pointer lives in [OUTBUF + 0x100] */
	P4.H = 0x0310; P4.L = 0;
	R0.H = 0x0200; R0.L = 0; [P4 + 0x100] = R0;
next:
	P4.H = 0x0310; P4.L = 0;
	P5 = [P4 + 0x100];
	R0 = [P5++];
	CC = R0 == 0; IF CC JUMP finish;
	R1 = 3 (X); CC = R0 == R1; IF CC JUMP blocks;
	R1 = 4 (X); CC = R0 == R1; IF CC JUMP emit;
	R1 = 5 (X); CC = R0 == R1; IF CC JUMP dump;
	/* 1 or 2: addr, count, halfwords */
	R7 = R0;
	P2 = [P5++];
	R2 = [P5++];
	P0 = R2;
	CC = R2 == 0; IF CC JUMP copied;
	LSETUP(cb, ce) LC0 = P0;
cb:	R3 = W[P5++] (Z);
ce:	W[P2++] = R3;
copied:
	R0 = P5; R0 += 3; R1 = -4 (X); R0 = R0 & R1; [P4 + 0x100] = R0;
	R1 = 2 (X); CC = R7 == R1; IF !CC JUMP next;
	P1.L = 0x3404; P1.H = 0xffc0; R0 = 0x10 (X); W[P1] = R0;
	R0 = 0x104 (Z);
	P1.L = 0x4ec8; P1.H = 0xffa0; CALL (P1);
	JUMP next;
blocks:
	R0 = [P5++]; [P4 + 0x100] = P5; [P4 + 0x104] = R0;
bloop:
	R4 = 0 (X);
frame:
	P4.H = 0xff80; P4.L = 0x2890;
	R5 = 0 (X);
	[P4 + -0x20] = R5; [P4 + -0x1c] = R5; [P4 + -0x18] = R5; [P4 + -0x14] = R5;
	P1.H = 0xff90; P1.L = 0x3170;
	[P1 + -0xcc] = R4;
	R1.H = 0xff80; R1.L = 0x0748;
	R0.H = 0xff90; R0.L = 0x0eac;
	[--SP] = R4;
	P1.L = 0x141a; P1.H = 0xffa0; CALL (P1);
	R4 = [SP++];
	R4 += 1; R0 = 4 (X); CC = R4 < R0; IF CC JUMP frame;
	P1.L = 0xe48c; P1.H = 0x01f0; CALL (P1);
	P5.H = 0xff80; P5.L = 0x0054; R0 = [P5]; R0 += 1; [P5] = R0;
	P4.H = 0x0310; P4.L = 0;
	R0 = [P4 + 0x104]; R0 += -1; [P4 + 0x104] = R0;
	CC = R0 == 0; IF !CC JUMP bloop;
	JUMP next;
emit:
	[P4 + 0x100] = P5;
	P1.H = 0xff90; P1.L = 0x30f4;
	R0 = [P1]; [P4 + 0x40] = R0; R0 = [P1 + 4]; [P4 + 0x44] = R0;
	P1.H = 0xff80; P1.L = 0x2890;
	R0 = [P1 + -0x10]; [P4 + 0x48] = R0; R0 = [P1 + -0xc]; [P4 + 0x4c] = R0;
	R0 = 1 (X); [P4 + 32] = R0;
	R0 = P4; R0 += 32; R0 += 32; [P4 + 36] = R0;
	R0 = 16 (X); [P4 + 40] = R0;
	R0 = P4; R0 += 32;
	P0 = 5 (X); EXCPT 0;
	JUMP next;
dump:
	R0 = [P5++]; R1 = [P5++]; [P4 + 0x100] = P5;
	[P4 + 36] = R0; [P4 + 40] = R1;
	R0 = 1 (X); [P4 + 32] = R0;
	R0 = P4; R0 += 32;
	P0 = 5 (X); EXCPT 0;
	JUMP next;
finish:
	R0 = 0 (X); [P4 + 32] = R0; R0 = P4; R0 += 32;
	P0 = 1 (X); EXCPT 0;
'''
base = os.path.join(here, 'replay')
open(base + '.s', 'w').write(asm)
subprocess.run([AS, base + '.s', '-o', base + '.o'], check=True)
subprocess.run([OBJCOPY, '-O', 'binary', '-j', '.text', base + '.o', base + '.bin'], check=True)
meta = json.load(open(os.path.join(args.src, 'map.json')))
segs = [(m['target'], open(os.path.join(args.src, m['file']), 'rb').read()) for m in meta]
segs += [(HARNESS, open(base + '.bin', 'rb').read()), (SCRIPT, bytes(script))]
mkelf.write(base + '.elf', segs, HARNESS)
cmd = [args.run, '--environment', 'virtual', '--model', 'bf527']
for b, size in [(0, 0x4000000), (0xFF800000, 0x8000), (0xFF900000, 0x8000), (0xFFA00000, 0x14000), (0xFFC00000, 0x3FF000)]:
    cmd += ['--memory-region', f'0x{b:X},0x{size:X}']
cmd.append(base + '.elf')
print(f'script {len(script)} bytes, {mailboxes} mailbox messages, {end - start:.0f} ms of audio', file=sys.stderr)
p = subprocess.run(cmd, capture_output=True)
open(base + '.err', 'wb').write(p.stderr)
print(f'sim exit {p.returncode}, stderr {len(p.stderr)} bytes in {base}.err', file=sys.stderr)
out = p.stdout
ndump = sum(n for a, n in DUMPS)
dumps, out = out[len(out) - ndump:], out[:len(out) - ndump]
open(base + '.dump', 'wb').write(dumps)
rows = [struct.unpack_from('<IIii', out, i) for i in range(0, len(out) - 15, 16)]
pickle.dump({'start_ms': start, 'play_ms': play, 'rows': rows}, open(base + '.out.pkl', 'wb'))
for i, r in enumerate(rows):
    if i % 25 == 0 or (i and rows[i - 1][:2] != r[:2] and i % 5 == 0):
        print(f'{start + i + 1 - play:8.0f} ms  peak L {r[0]:#010x} R {r[1]:#010x}  out {r[2]:11d} {r[3]:11d}')
