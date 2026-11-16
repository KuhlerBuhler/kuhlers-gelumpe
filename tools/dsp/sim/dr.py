import re, sys
f, a, b = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
for l in open(f):
    m = re.match(r'\s*([0-9a-f]+):\t[^\t]*\t(.*)', l)
    if m and a <= int(m.group(1), 16) < b and m.group(2).strip(): print(m.group(1), m.group(2).strip())
