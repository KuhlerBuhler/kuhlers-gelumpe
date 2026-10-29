"""Reads a custom loading animation (docs/hintergrund/ladeanimation.md), the same as src/loading-anim.mjs, for the emulator cases.

    decode(blob) -> (progress, loop), lists of 1024-byte frame buffers
    validate(blob) -> None when good, else the reason (the checks the firmware makes)
    picture(blob, index, loop=None) -> what the overlay shows: progress picture `index`, loop list `loop` over it
"""
import struct

MAGIC = b"BLLA"
VERSION = 1
MAX_BYTES = 16384
FRAME_BYTES = 1024
HEADER_BYTES = 16


def validate(blob):
    if len(blob) < HEADER_BYTES:
        return "shorter than the header"
    if blob[:4] != MAGIC:
        return "wrong magic"
    if blob[4] != VERSION:
        return f"version {blob[4]}"
    if blob[5] > 100:
        return f"loop from {blob[5]} percent"
    n, m, table, size = struct.unpack_from("<HHHI", blob, 6)
    if size > MAX_BYTES:
        return f"{size} bytes, more than {MAX_BYTES}"
    if size > len(blob):
        return "the file is shorter than its size"
    if n < 1:
        return "no progress picture"
    count = n - 1 + m
    if table < HEADER_BYTES + FRAME_BYTES or table + 2 * count > size:
        return "list table outside the file"
    for i in range(count):
        p = struct.unpack_from("<H", blob, table + 2 * i)[0]
        if p + 2 > size:
            return f"list {i} outside the file"
        runs = struct.unpack_from("<H", blob, p)[0]
        p += 2
        for _ in range(runs):
            if p + 2 > size:
                return f"list {i} outside the file"
            head = struct.unpack_from("<H", blob, p)[0]
            at, length = head & 0x3FF, (head >> 10) + 1
            if at + length > FRAME_BYTES:
                return f"list {i} writes past byte 1023"
            p += 2 + length
            if p > size:
                return f"list {i} outside the file"
    return None


def _apply(frame, blob, p):
    runs = struct.unpack_from("<H", blob, p)[0]
    p += 2
    for _ in range(runs):
        head = struct.unpack_from("<H", blob, p)[0]
        at, length = head & 0x3FF, (head >> 10) + 1
        frame[at:at + length] = blob[p + 2:p + 2 + length]
        p += 2 + length
    return frame


def progress_index(n, permille):
    """The progress picture the firmware shows at `permille` (0 to 1000; 1000 only when the loader is done)."""
    return permille * (n - 1) // 1000


def loop_from(blob):
    """The percent from which the loop plays; 0: it plays while the progress stands."""
    return blob[5]


def _lists(blob):
    n, m, table = struct.unpack_from("<HHH", blob, 6)
    return n, m, struct.unpack_from(f"<{n - 1 + m}H", blob, table)


def decode(blob):
    bad = validate(blob)
    if bad:
        raise ValueError(f"no loading animation: {bad}")
    n, m, lists = _lists(blob)
    progress = [bytes(blob[HEADER_BYTES:HEADER_BYTES + FRAME_BYTES])]
    for k in range(1, n):
        progress.append(bytes(_apply(bytearray(progress[-1]), blob, lists[k - 1])))
    base = progress[progress_index(n, 10 * loop_from(blob))]
    loop = [bytes(_apply(bytearray(base), blob, lists[n - 1 + j])) for j in range(m)]
    return progress, loop


def picture(blob, index, loop=None):
    """Progress picture `index` with loop list `loop` written over it, as the overlay draws it (before the complement)."""
    n, _, lists = _lists(blob)
    frame = bytearray(blob[HEADER_BYTES:HEADER_BYTES + FRAME_BYTES])
    for k in range(1, index + 1):
        _apply(frame, blob, lists[k - 1])
    if loop is not None:
        _apply(frame, blob, lists[n - 1 + loop])
    return bytes(frame)
