"""Tests for hot_patch.py: sorting, groups, order, check report, journal and revert, without emulator or device.

Each file in fixtures/hot_patch/ is a small map of base, new and running bytes over an otherwise zero image, the context
(closed regions, start phase, data, DSP) and the expected table.
"""
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hot_patch as hp  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "hot_patch"


def image(bytemap, under=None):
    out = bytearray(under if under is not None else bytes(hp.IMAGE_SIZE))
    for addr, data in bytemap.items():
        a = int(addr, 16) - hp.IMAGE
        out[a:a + len(bytes.fromhex(data))] = bytes.fromhex(data)
    return bytes(out)


def pairs(ranges):
    return [(int(a, 16), int(b, 16)) for a, b in ranges]


def context(c):
    return hp.Context(pairs(c.get("closed", [])), pairs(c.get("start", [])), pairs(c.get("data", [])), tuple(int(x, 16) for x in c["dsp"]))


class FakeBlech:
    """READ and WRITE on a byte array, the way remote_press.Blech answers."""

    def __init__(self, payload, flags=hp.FLAG_WRITE | hp.FLAG_DEV | hp.FLAG_DEV_ON, family=hp.SAMPLER):
        self.ram = bytearray(payload) + bytes(0x800000 - len(payload))     # up to the transport word
        self.flags, self.largest, self.head = flags, 0x8000, [0x42, 0x30, 0, 1, family]
        self.writes = []

    def read(self, a, n):
        return bytes(self.ram[a - hp.IMAGE:a - hp.IMAGE + n])

    def write(self, a, data, verify=True):
        self.writes.append((a, len(data)))
        self.ram[a - hp.IMAGE:a - hp.IMAGE + len(data)] = data


def load(name):
    c = json.loads((FIXTURES / f"{name}.json").read_text())
    base, new = image(c["base"]), image(c["new"])
    running = image(c.get("running", {}), base)
    return c, base, new, running


class Fixtures(unittest.TestCase):
    def test_every_fixture(self):
        names = sorted(p.stem for p in FIXTURES.glob("*.json"))
        self.assertGreaterEqual(len(names), 8)
        for name in names:
            with self.subTest(name):
                c, base, new, running = load(name)
                p = hp.plan(base, new, lambda a, b: running[a - hp.IMAGE:b - hp.IMAGE], context(c["context"]), c.get("block", hp.BLOCK))
                rows = [[f"{r['start']:#010x}", f"{r['end']:#010x}", r["cls"]] for r in p["rows"]]
                self.assertEqual(rows, c["expect"]["rows"], c["what"])
                self.assertEqual([[f"{r['start']:#010x}" for r in g] for g in p["groups"]], c["expect"]["groups"], c["what"])
                self.assertEqual(len(p["warnings"]), c["expect"]["warnings"], c["what"])


class Pieces(unittest.TestCase):
    def test_diff_joins_close_runs_and_aligns_to_words(self):
        base = bytes(hp.IMAGE_SIZE)
        new = image({"0xc0000101": "01", "0xc0000109": "01", "0xc0000200": "01"})
        self.assertEqual(hp.diff(base, new), [(0xC0000100, 0xC000010C), (0xC0000200, 0xC0000204)])

    def test_branch_target(self):
        self.assertEqual(hp.targets(0xEB013FFE, 0xC0100000), [0xC0150000])
        self.assertEqual(hp.targets(0xEAFFFFFE, 0xC0100000), [0xC0100000])     # b .
        self.assertEqual(hp.targets(0xC0123456, 0xC0100000), [0xC0123456])     # a literal pointer
        self.assertEqual(hp.targets(0xE3A00000, 0xC0100000), [])

    def test_minus(self):
        self.assertEqual(hp.minus([(0, 100)], [(10, 20), (50, 60), (200, 300)]), [(0, 10), (20, 50), (60, 100)])

    def test_dsp_constant_matches_check(self):
        text = (hp.ROOT / "tools" / "emu" / "check.py").read_text()
        self.assertIn("DSP_STREAM = slice(0xF9F10, 0x13C1B0)", text)
        self.assertEqual(hp.DSP, (0xC0000000 + 0xF9F10 - 0x100, 0xC0000000 + 0x13C1B0 - 0x100))

    def test_closed_regions_parse_both_builds(self):
        for build in ("ht", "red"):
            closed = hp.closed_regions(build)
            self.assertGreater(len(closed), 10)
            self.assertTrue(any(a <= 0xC0172100 < b for a, b in closed), "the SysEx code is closed")


class Report(unittest.TestCase):
    raw = b"\0" * 16

    def report(self, **kw):
        return {"vsb_sha256": hashlib.sha256(self.raw).hexdigest(), "ok": True, "quick": False, "partial": False, **kw}

    def test_a_new_image_without_a_matching_report_is_refused(self):
        self.assertIn("another VSB", hp.accept_report({**self.report(), "vsb_sha256": "0" * 64}, self.raw))
        self.assertIn("failed", hp.accept_report(self.report(ok=False), self.raw))
        self.assertIn("part", hp.accept_report(self.report(partial=True), self.raw))
        self.assertIn("quick", hp.accept_report(self.report(quick=True), self.raw))
        self.assertIsNone(hp.accept_report(self.report(quick=True), self.raw, allow_quick=True))
        self.assertIsNone(hp.accept_report(self.report(), self.raw))


class Device(unittest.TestCase):
    def setUp(self):
        c, self.base, self.new, _ = load("ff_code_and_branch")
        self.ctx = context(c["context"])
        self.tmp = Path(tempfile.mkdtemp())
        self.base_raw, self.new_raw = bytes(hp.HEADER) + self.base, bytes(hp.HEADER) + self.new
        (self.tmp / "base.VSB").write_bytes(self.base_raw)

    def go(self, blech, **kw):
        return hp.run(blech, self.base_raw, self.tmp / "base.VSB", self.new_raw, self.tmp / "new.VSB", self.ctx,
                      proof="near", journals=self.tmp, say=lambda *_: None, **kw)

    def test_write_in_order_then_revert(self):
        dev = FakeBlech(self.base)
        p, journal = self.go(dev)
        self.assertEqual(dev.writes, [(0xC0150000, 32), (0xC0100000, 4)], "FF code first, the branch word last")
        self.assertEqual(bytes(dev.ram[:hp.IMAGE_SIZE]), self.new)
        doc = json.loads(journal.read_text())
        self.assertEqual(doc["written_groups"], 1)
        self.assertEqual(doc["base"]["sha256"], hashlib.sha256(self.base_raw).hexdigest())
        hp.revert(dev, journal, say=lambda *_: None)
        self.assertEqual(bytes(dev.ram[:hp.IMAGE_SIZE]), self.base)

    def test_chained_base_is_the_base_with_the_written_groups(self):
        dev = FakeBlech(self.base)
        _, journal = self.go(dev)
        chained, raw = hp.chained_base(journal)
        self.assertEqual(chained, self.new)
        self.assertEqual(raw, self.base_raw)

    def test_dry_run_writes_nothing(self):
        dev = FakeBlech(self.base)
        _, journal = self.go(dev, dry_run=True)
        self.assertIsNone(journal)
        self.assertEqual(dev.writes, [])

    def test_refusals_before_any_write(self):
        for blech, text in ((FakeBlech(self.base, flags=hp.FLAG_WRITE | hp.FLAG_DEV), "off"),
                            (FakeBlech(self.base, flags=hp.FLAG_WRITE), "no DEV MODE"),
                            (FakeBlech(self.base, family=0x23), "Sampler")):
            with self.assertRaises(SystemExit) as cm:
                self.go(blech)
            self.assertIn(text, str(cm.exception))
            self.assertEqual(blech.writes, [])

    def test_base_proof_stops_on_another_image(self):
        other = bytearray(self.base)
        other[0x150010] = 0x12          # inside the near block of the change, not in a data area
        dev = FakeBlech(bytes(other))
        with self.assertRaises(SystemExit) as cm:
            self.go(dev)
        self.assertIn("base proof", str(cm.exception))
        self.assertEqual(dev.writes, [])

    def test_playing_sequencer_stops_the_write(self):
        dev = FakeBlech(self.base)
        dev.ram[hp.TRANSPORT - hp.IMAGE:hp.TRANSPORT - hp.IMAGE + 4] = struct.pack("<I", 1)
        with self.assertRaises(SystemExit) as cm:
            self.go(dev)
        self.assertIn("sequencer", str(cm.exception))
        self.assertEqual(dev.writes, [])

    def test_a_full_update_range_stops_the_run_unless_partial(self):
        new = bytearray(self.new)
        new[0x100] = 0x55
        self.ctx.start = [(0xC0000000, 0xC0001000)]
        self.new_raw = bytes(hp.HEADER) + bytes(new)
        dev = FakeBlech(self.base)
        p, journal = self.go(dev)
        self.assertIsNone(journal)
        self.assertEqual(dev.writes, [])
        p, journal = self.go(dev, partial=True)
        self.assertTrue(json.loads(journal.read_text())["partial"])
        self.assertEqual(dev.ram[0x100], 0)


if __name__ == "__main__":
    unittest.main()
