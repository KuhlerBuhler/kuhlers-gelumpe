import sys, capstone
d = open(sys.argv[1], 'rb').read()[0x100:]
a, b = int(sys.argv[2], 16), int(sys.argv[3], 16)
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if len(sys.argv) > 4 else capstone.CS_MODE_ARM)
for i in md.disasm(d[a - 0xC0000000:b - 0xC0000000], a):
    print(hex(i.address), i.mnemonic, i.op_str)
