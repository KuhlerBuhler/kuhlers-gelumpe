"""Write an ELF32 Blackfin executable from (address, bytes) segments, with program and section headers."""
import struct

def write(path, segments, entry):
    segs = [(a, bytes(b)) for a, b in segments if len(b)]
    n = len(segs)
    ehsize, phsize, shsize = 52, 32, 40
    off = ehsize + phsize * n
    ph, data, offs = b"", b"", []
    for a, b in segs:
        data += b"\0" * ((-(off + len(data))) % 4)
        o = off + len(data)
        offs.append(o)
        ph += struct.pack("<IIIIIIII", 1, o, a, a, len(b), len(b), 7, 4)
        data += b
    names = b"\0.shstrtab\0" + b"".join(b".r%d\0" % i for i in range(n))
    stroff = off + len(data)
    data += names
    data += b"\0" * ((-(off + len(data))) % 4)
    shoff = off + len(data)
    sh = b"\0" * shsize
    pos = len(b"\0.shstrtab\0")
    for i, (a, b) in enumerate(segs):
        sh += struct.pack("<IIIIIIIIII", pos, 1, 7, a, offs[i], len(b), 0, 0, 4, 0)
        pos += len(b".r%d\0" % i)
    sh += struct.pack("<IIIIIIIIII", 1, 3, 0, 0, stroff, len(names), 0, 0, 1, 0)
    eh = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
    eh += struct.pack("<HHIIIIIHHHHHH", 2, 106, 1, entry, ehsize, shoff, 0, ehsize, phsize, n, shsize, n + 2, n + 1)
    open(path, "wb").write(eh + ph + data + sh)
