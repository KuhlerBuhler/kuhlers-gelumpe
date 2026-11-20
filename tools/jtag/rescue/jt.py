import socket, sys, struct
s = socket.create_connection(("127.0.0.1", 6666))
def cmd(c):
    s.sendall(c.encode() + b"\x1a"); out = b""
    while not out.endswith(b"\x1a"): out += s.recv(65536)
    return out[:-1].decode()
def rd(addr, n):
    words = []
    while len(words) * 4 < n:
        k = min(1024, (n - len(words) * 4 + 3) // 4)
        r = cmd(f"read_memory {addr + len(words)*4:#x} 32 {k}")
        words += [int(x, 16) for x in r.split()]
    return b"".join(struct.pack("<I", w) for w in words)[:n]
def disp():
    img = rd(0xC031B310, 1024)
    return "\n".join("".join("#" if (img[(y >> 3) * 128 + x] >> (y & 7)) & 1 else " " for x in range(128)).rstrip() for y in range(0, 64, 2))
def find_remt():
    for start, end in ((0xC0150300, 0xC0170000), (0xC018D000, 0xC018FF00)):
        data = rd(start, end - start)
        for i in range(0, len(data) - 24, 4):
            if struct.unpack_from("<I", data, i)[0] == 0x544D4552:
                return start + i, struct.unpack_from("<6I", data, i)
if __name__ == "__main__":
    cmd("halt")
    try:
        for a in sys.argv[1:]:
            if a == "disp": print(disp())
            elif a == "remt": print([hex(x) for x in (find_remt() or (0,()))[1]], hex((find_remt() or (0,))[0]))
            elif a.startswith("w:"):
                _, addr, val = a.split(":"); print(cmd(f"mww {addr} {val}"))
            elif a.startswith("r:"):
                _, addr = a.split(":"); print(rd(int(addr, 16), 16).hex())
    finally:
        cmd("resume")
