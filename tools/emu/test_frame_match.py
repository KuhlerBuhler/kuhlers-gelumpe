import unittest
from frame_match import matches_pages


class FrameMatchTests(unittest.TestCase):
    def setUp(self):
        self.old = bytes([0x55])*1024
        self.new = bytes([0xAA])*1024
        self.candidates = [self.old,self.new]

    def scan(self, page, column):
        at = page*128+column
        return self.new[:at]+self.old[at:]

    def test_complete_pages_can_belong_to_different_known_pictures(self):
        self.assertTrue(matches_pages(self.old,self.candidates))
        self.assertTrue(matches_pages(self.new,self.candidates))
        for page in range(8):
            self.assertTrue(matches_pages(self.scan(page,0),self.candidates))

    def test_only_the_recorded_page_and_column_allow_a_partial_page(self):
        for page in range(8):
            for col in (1,2,64,66,127):
                frame = self.scan(page,col)
                self.assertTrue(matches_pages(frame,self.candidates,(page,col)),(page,col))
                self.assertFalse(matches_pages(frame,self.candidates))
                self.assertFalse(matches_pages(frame,self.candidates,((page+1)%8,col)))
                self.assertFalse(matches_pages(frame,self.candidates,(page,128-col if col!=64 else 63)))

    def test_corruption_and_a_second_partial_page_are_rejected(self):
        frame = self.scan(3,66)
        for at in (0,3*128+10,3*128+100,7*128):
            bad = bytearray(frame)
            bad[at] = 0xFF
            self.assertFalse(matches_pages(bytes(bad),self.candidates,(3,66)))
        bad = bytearray(frame)
        bad[4*128:4*128+12] = self.new[:12]
        self.assertFalse(matches_pages(bytes(bad),self.candidates,(3,66)))

    def test_invalid_lengths_empty_candidates_and_invalid_scan_are_rejected(self):
        self.assertFalse(matches_pages(bytes(1023),self.candidates))
        self.assertFalse(matches_pages(self.old,[]))
        self.assertFalse(matches_pages(self.old,[bytes(1023)]))
        for scan in ((-1,66),(8,66),(3,-1),(3,0),(3,128)):
            self.assertFalse(matches_pages(self.scan(3,66),self.candidates,scan))


if __name__ == '__main__':
    unittest.main()
