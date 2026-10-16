"""Where a place of the Sampler firmware 2.02 sits in the blue Electribe 2's (the synth's) 2.02.

Both builds come from the same sources, so most of the code is word for word the same and only sits somewhere else. This
module aligns the two images and answers `at(address)` for an address of the Sampler build with the address of the same
place in the synth build, or says that it cannot. It is a build tool for patches: the user's files stay outside the
repository, nothing of them is written anywhere, and the answer is only addresses.

    python3 tools/patch/fwmap.py --ref SAMPLER.VSB --vsb SYNTH.VSB 0xC0026A8C 0xC033E6F8 ...

How an address is found:
  code and data in the image  the images are cut into runs of equal words (a branch offset, a pc-relative load offset and a
                              pointer into the firmware's address range count as equal), the runs found by anchors of six
                              words that exist once in each image and keep their order. An address inside a run moves by the
                              distance of the run. Whether the place is then the same is checked by `same_code`: the 16
                              words around it, masked like that, must be equal in both images.
  RAM behind the image        the address of a variable is found where the code loads it: a literal pool word that holds
                              the Sampler's address at a position where the synth's pool holds another one. The pair
                              counts when the vote over all such positions is unanimous.
"""

import argparse
import bisect
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = 0xC0000000
HEADER = 0x100
PAYLOAD = 0x200000
ANCHOR = 6
WINDOW = 16
REFINE_MIN = 4
REFINE_MAX = 6000


class Unmapped(Exception):
    pass


def _mask(w):
    if w & 0x0E000000 == 0x0A000000:
        return w & 0xFF000000
    if w & 0x0E1F0000 == 0x041F0000:
        return w & ~0x00800FFF
    if BASE <= w < BASE + 0x08000000:
        return BASE
    return w


def _words(payload):
    return struct.unpack(f"<{len(payload) // 4}I", payload)


def _longest_increasing(pairs):
    """The longest run of (a, b) pairs, sorted by a, whose b also increase."""
    tails, ends, parent = [], [], []
    for k, (_, b) in enumerate(pairs):
        j = bisect.bisect_left(tails, b)
        parent.append(ends[j - 1] if j else -1)
        if j == len(tails):
            tails.append(b)
            ends.append(k)
        else:
            tails[j] = b
            ends[j] = k
    out, k = [], ends[-1] if ends else -1
    while k != -1:
        out.append(pairs[k])
        k = parent[k]
    return out[::-1]


class FirmwareMap:
    def __init__(self, ref, target, refine=False):
        """`ref` and `target` are the 0x200000 bytes behind the head of the two VSBs (Sampler, synth). With `refine` the gaps between
        two runs are aligned once more, word by word, so that code which differs only here and there is found too (the 16-word check
        `same_code` then fails more often: a place found that way is looked at, not trusted)."""
        self.ref, self.target = ref, target
        self.w_ref, self.w_tgt = _words(ref), _words(target)
        m_ref, m_tgt = [_mask(w) for w in self.w_ref], [_mask(w) for w in self.w_tgt]
        self.m_ref, self.m_tgt = m_ref, m_tgt
        index = []
        for masked in (m_ref, m_tgt):
            seen = defaultdict(list)
            for i in range(len(masked) - ANCHOR):
                key = tuple(masked[i:i + ANCHOR])
                if len(set(key)) > 2:
                    seen[key].append(i)
            index.append(seen)
        anchors = sorted((v[0], index[1][k][0]) for k, v in index[0].items() if len(v) == 1 and len(index[1].get(k, ())) == 1)
        runs = []
        for a, b in _longest_increasing(anchors):
            if runs and runs[-1][1] - runs[-1][0] == b - a and runs[-1][0] + runs[-1][2] >= a:
                runs[-1][2] = a + ANCHOR - runs[-1][0]
            else:
                runs.append([a, b, ANCHOR])
        for run in runs:
            a, b, n = run
            while a > 0 and b > 0 and m_ref[a - 1] == m_tgt[b - 1]:
                a, b, n = a - 1, b - 1, n + 1
            while a + n < len(m_ref) and b + n < len(m_tgt) and m_ref[a + n] == m_tgt[b + n]:
                n += 1
            run[:] = [a, b, n]
        runs.sort()
        merged = []
        for a, b, n in runs:
            if merged and merged[-1][0] + merged[-1][2] > a:
                if merged[-1][1] - merged[-1][0] == b - a:
                    merged[-1][2] = max(merged[-1][2], a + n - merged[-1][0])
                continue
            merged.append([a, b, n])
        if refine:
            merged = self._refined(merged)
        self.runs = [tuple(r) for r in merged]
        self._starts = [r[0] for r in self.runs]
        self.pointers = self._pointer_votes()

    def _refined(self, runs):
        """The runs plus the blocks of at least `REFINE_MIN` equal words that an alignment finds inside the gaps between them."""
        import difflib
        out = []
        edges = [(0, 0, 0), *runs, (len(self.m_ref), len(self.m_tgt), 0)]
        for (a1, b1, n1), (a2, b2, _) in zip(edges, edges[1:]):
            ga, gb = a1 + n1, b1 + n1
            if 0 < a2 - ga <= REFINE_MAX and 0 < b2 - gb <= REFINE_MAX:
                matcher = difflib.SequenceMatcher(None, self.m_ref[ga:a2], self.m_tgt[gb:b2], autojunk=False)
                out += [[ga + i, gb + j, n] for i, j, n in matcher.get_matching_blocks() if n >= REFINE_MIN]
        return sorted([*map(list, runs), *out])

    def _pointer_votes(self):
        """{Sampler address: synth address} of the pointers (words in the address range) at equal places of the runs."""
        votes = defaultdict(Counter)
        for a, b, n in self.runs:
            for k in range(n):
                x, y = self.w_ref[a + k], self.w_tgt[b + k]
                if BASE <= x < BASE + 0x08000000 and BASE <= y < BASE + 0x08000000:
                    votes[x][y] += 1
        return {x: c.most_common(1)[0][0] for x, c in votes.items() if len(c) == 1}

    def run_of(self, address):
        i = bisect.bisect_right(self._starts, (address - BASE) // 4) - 1
        if i >= 0:
            a, b, n = self.runs[i]
            if (address - BASE) // 4 < a + n:
                return a, b, n
        return None

    def code(self, address):
        """The synth address of a place inside the image, or Unmapped."""
        run = self.run_of(address)
        if run is None:
            raise Unmapped(f"{address:#x} is in no run of equal code")
        a, b, _ = run
        return address + (b - a) * 4

    def at(self, address):
        """The synth address of a Sampler address: inside the image by its run, behind it by the pointer votes."""
        if address < BASE + PAYLOAD:
            return self.code(address)
        if address in self.pointers:
            return self.pointers[address]
        raise Unmapped(f"{address:#x} is behind the image and no pointer to it was found at an equal place")

    def same_code(self, address, window=WINDOW, target=None):
        """Compare a complete masked code window, at the aligned or an explicitly measured target."""
        at = self.code(address) if target is None else target
        if address % 4 or at % 4 or window <= 0:
            return False
        i, j = (address - BASE) // 4, (at - BASE) // 4
        if i < 0 or j < 0 or i + window > len(self.m_ref) or j + window > len(self.m_tgt):
            return False
        return self.m_ref[i:i + window] == self.m_tgt[j:j + window]


def load(path):
    raw = Path(path).read_bytes()
    if len(raw) != HEADER + PAYLOAD:
        raise SystemExit(f"{path}: a VSB has {HEADER + PAYLOAD:#x} bytes")
    return raw[HEADER:]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ref", required=True, type=Path, help="the Sampler's SYSTEM.VSB (Korg's own or Hacktribe's)")
    p.add_argument("--vsb", required=True, type=Path, help="the synth's SYSTEM.VSB")
    p.add_argument("--target", type=lambda x: int(x, 0), help="verify one explicitly measured synth code address")
    p.add_argument("addresses", nargs="*")
    a = p.parse_args()
    fm = FirmwareMap(load(a.ref), load(a.vsb))
    if a.target is not None:
        if len(a.addresses) != 1:
            p.error("--target needs exactly one Sampler code address")
        address = int(a.addresses[0], 0)
        same = fm.same_code(address, target=a.target)
        print(f"{address:#010x} -> {a.target:#010x}  same code: {same}")
        return 0 if same else 1
    total = sum(n for _, _, n in fm.runs) * 4
    print(f"{len(fm.runs)} runs, {total / PAYLOAD:.1%} of the image, {len(fm.pointers)} pointers")
    for text in a.addresses:
        address = int(text, 0)
        try:
            to = fm.at(address)
            same = fm.same_code(address) if address < BASE + 0x100000 else None
            print(f"{address:#010x} -> {to:#010x}" + ("" if same is None else f"  same code: {same}"))
        except Unmapped as error:
            print(f"{address:#010x} -> {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
