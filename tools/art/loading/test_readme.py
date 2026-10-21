"""Check the encoded README media, including its final visible frames."""
import unittest
from PIL import Image, ImageSequence
import readme


def decoded(path):
    with Image.open(path) as gif:
        return [(frame.convert('L').resize((128, 64), Image.Resampling.NEAREST).tobytes(),
                 frame.info['duration']) for frame in ImageSequence.Iterator(gif)]


def expected(data):
    return bytes(255 * ((data[(y // 8) * 128 + x] >> (y % 8)) & 1)
                 for y in range(64) for x in range(128))


def check_loading(test, path):
    art = readme.lb.parse_loading(readme.lb.art())
    finale = {expected(readme.lb.compose_reference(art, readme.lb.loading_key(100, True, tick)))
              for tick in range(readme.lb.TICKS_N)}
    frames = decoded(path)
    test.assertTrue(finale.issubset({image for image, _ in frames}), 'all completion poses must be visible')
    test.assertEqual(frames[-1][0], expected(readme.lb.compose_reference(art, readme.lb.loading_key(100, True, 7))))
    test.assertGreaterEqual(frames[-1][1], 1100)
    test.assertGreaterEqual(sum(ms for image, ms in frames if image in finale), 1900)


class ReadmeMediaTests(unittest.TestCase):
    def test_loading_reaches_100_and_shows_the_whole_finale(self):
        check_loading(self, readme.OUT / 'blechtribe-start.gif')

    def test_shutdown_contains_wave_tube_dot_and_black(self):
        frames = decoded(readme.OUT / 'blechtribe-aus.gif')
        images = {image for image, _ in frames}
        for ms in (0, 125, 820, 880, 930, 970):
            self.assertIn(expected(readme.po.sequence(ms, True)), images)
        self.assertEqual(frames[-1][0], bytes(128 * 64))
        self.assertGreaterEqual(frames[-1][1], 600)


if __name__ == '__main__':
    unittest.main()
