p0=0
import re, sys
off = 0  # bytes from slot start at ffa01a22 (after 5 words read, P2 at +0x14? computed below)
lines = [l for l in open(sys.argv[1])]
start, end, off = int(sys.argv[2], 16), int(sys.argv[3], 16), int(sys.argv[4], 16)
for l in lines:
    m = re.match(r'\s*([0-9a-f]+):\t[^\t]*\t(.*)', l)
    if not m: continue
    a = int(m.group(1), 16); ins = m.group(2).strip()
    if not (start <= a < end): continue
    note = ''
    mc = re.match(r'P0 = (0x[0-9a-f]+) \(X\)', ins)
    if mc: p0 = int(mc.group(1), 16)
    if ins.startswith('P2 = P0 + P2') or ins.startswith('P2 = P2 + P0'): off += p0; print(hex(a), ins, '<< P2 ->', off//4); continue
    mc = re.match(r'P2 \+= (0x[0-9a-f]+)', ins)
    if mc: off += int(mc.group(1), 16); print(hex(a), ins, '<< P2 ->', off//4); continue
    for mm in re.finditer(r'\[P2(\+\+|--)?\]|\[P2 \+ (-?0x[0-9a-f]+)\]', ins):
        if mm.group(2): note += ' w%d' % ((off + int(mm.group(2), 16)) // 4)
        else:
            note += ' w%d' % (off // 4)
            if mm.group(1) == '++': off += 4
            elif mm.group(1) == '--': off -= 4
    if 'P2' in ins and not note: note = ' ?P2'
    if note: print(hex(a), ins[:70], '<<', note)
