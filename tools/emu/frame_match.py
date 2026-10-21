"""Compare an LCD snapshot with known pages and its recorded scan position."""


def matches_pages(frame, candidates, scan=None):
    candidates = tuple(candidates)
    if len(frame) != 1024 or not candidates or any(len(c) != 1024 for c in candidates):
        return False
    for page in range(8):
        at = page*128
        row = frame[at:at+128]
        if any(row == c[at:at+128] for c in candidates):
            continue
        if scan is not None and page == scan[0] and 0 < scan[1] < 128:
            col = scan[1]
            if (any(row[:col] == c[at:at+col] for c in candidates)
                    and any(row[col:] == c[at+col:at+128] for c in candidates)):
                continue
        return False
    return True
