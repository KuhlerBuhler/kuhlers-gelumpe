import sys, time, struct, re
from jt import cmd, rd
STUB, MSG, FLAG = 0xC1000100, 0xC1000200, 0xC1000210
IRQ_OFF, IRQ_RESTORE, QUEUE_PUT, EVENT_SET, PANEL_QUEUE, IN_ISR = 0xC0000040, 0xC0000050, 0xC0024AFC, 0xC0000E9C, 0xC033E57C, 0xC06A2894
KEYS = dict(rec=0,stop=1,play=2,tap=3,left=8,menu=9,shift=10,partdec=11,right=12,exit=13,write=14,partinc=15)
RETPC = STUB + 0xC0
def build():
    code, lits = [], []
    def ldr(rd_, val):
        lits.append(val); code.append(("ldr", rd_, len(lits) - 1))
    w = code.append
    w(0xE92D5FFF); w(0xE10F4000)
    ldr(12, IRQ_OFF); w(0xE12FFF3C); w(0xE1A05000)
    ldr(0, PANEL_QUEUE); ldr(1, MSG); ldr(12, QUEUE_PUT); w(0xE12FFF3C)
    w(0xE1A00005); ldr(12, IRQ_RESTORE); w(0xE12FFF3C)
    ldr(0, PANEL_QUEUE); w(0xE590101C); w(0xE5900008); ldr(12, EVENT_SET); w(0xE12FFF3C)
    ldr(1, FLAG); w(0xE5912000); w(0xE2822001); w(0xE5812000); w(0xE5810004)
    w(0xE128F004); w(0xE8BD5FFF); w(("ldrpc",))
    pool = STUB + 4 * len(code)
    out = []
    for i, c in enumerate(code):
        here = STUB + 4 * i
        if isinstance(c, int): out.append(c)
        elif c[0] == "ldr": out.append(0xE59F0000 | c[1] << 12 | (pool + 4 * c[2] - here - 8))
        else: out.append(0xE59FF000 | (RETPC - here - 8))
    out += lits
    assert STUB + 4 * len(out) <= RETPC
    return out
def get(r): return int(re.search(r":\s*(0x[0-9a-f]+)", cmd(f"reg {r}")).group(1), 16)
def u32(a): return struct.unpack("<I", rd(a, 4))[0]
def install():
    cmd("halt")
    for i, wv in enumerate(build()): cmd(f"mww {STUB + 4*i:#x} {wv:#x}")
    cmd(f"mww {FLAG:#x} 0"); cmd(f"mww {FLAG+4:#x} 0"); cmd("resume")
def inject(msg):
    for _ in range(200):
        cmd("halt")
        pc, cpsr = get("pc"), get("cpsr")
        if cpsr & 0xBF == 0x13 and 0xC0000000 <= pc < 0xC0200000 and u32(IN_ISR) == 0:
            before = u32(FLAG)
            cmd(f"mww {MSG:#x} {struct.unpack('<I', bytes(msg))[0]:#x}"); cmd(f"mww {MSG+4:#x} 0")
            cmd(f"mww {RETPC:#x} {pc:#x}")
            cmd(f"reg pc {STUB:#x}"); cmd("resume")
            for _ in range(50):
                time.sleep(0.02); cmd("halt"); n = u32(FLAG); ev = u32(FLAG + 4); cmd("resume")
                if n != before: return ev
            raise SystemExit("stub did not finish")
        cmd("resume"); time.sleep(0.013)
    raise SystemExit("no task context")
def press(k):
    a = inject([0, KEYS[k], 1, 0]); time.sleep(0.15); b = inject([0, KEYS[k], 0, 0]); time.sleep(0.6)
    return hex(a), hex(b)
def show():
    cmd("halt"); img = rd(0xC031B310, 1024); cnt = rd(PANEL_QUEUE + 0x14, 2).hex(); cmd("resume")
    print("queue", cnt)
    for y in range(64):
        l = "".join("#" if (img[(y >> 3) * 128 + x] >> (y & 7)) & 1 else " " for x in range(128)).rstrip()
        if l.strip(): print(l)
if __name__ == "__main__":
    for k in sys.argv[1:]:
        if k == "install": install()
        elif k != "show": print(k, press(k))
    show()
