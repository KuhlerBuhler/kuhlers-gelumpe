import re, sys, glob
S = sys.argv[1]
lines = []
for f in sorted(glob.glob(S + '/dis/*.s')):
    for l in open(f):
        m = re.match(r'\s*([0-9a-f]+):\t', l)
        if m: lines.append((int(m.group(1), 16), l.rstrip()))
lines.sort()
def func_of(a):
    best = None
    for addr, l in lines:
        if addr > a: break
        if 'LINK' in l or '[--SP] = RETS' in l: best = addr
    return best
def callers(t):
    out = []
    h, lo = f'{t >> 16:x}', f'{t & 0xffff:x}'
    for i, (addr, l) in enumerate(lines):
        if f'0x0x{t:x};' in l and ('CALL' in l or 'JUMP' in l): out.append((addr, 'direct'))
        elif re.search(rf'\.L = 0x{lo};', l):
            ctx = ' '.join(x[1] for x in lines[max(0, i-3):i+4])
            if re.search(rf'\.H = 0x{h};', ctx): out.append((addr, 'hl'))
    return out
t = int(sys.argv[2], 16)
for d in range(int(sys.argv[3]) if len(sys.argv) > 3 else 4):
    print(f'{t:#x}:', [(hex(a), k, hex(func_of(a) or 0)) for a, k in callers(t)])
    cs = callers(t)
    if not cs: break
    t = func_of(cs[0][0])
