"""Behavior checks for the one-bit screen studies, without firmware or hardware.

    python3 -B entwuerfe/design-1.3/geraet/test_anim.py
"""
import math
import unittest

from PIL import Image

import anim


def render_state(direction, state):
    return anim.render_frame(direction, state.progress, pose=state.pose,
                             travel=state.travel, started=state.started, done=state.done)


def material(state):
    image = anim.blank()
    anim.draw_dashes(image, state)
    px = image.load()
    return frozenset((x, y) for y in range(64) for x in range(128) if px[x, y])


class FrameContractTests(unittest.TestCase):
    def test_every_demo_and_shutdown_frame_is_native_one_bit(self):
        for direction in anim.DIRECTIONS:
            for cue in anim.demo_timeline():
                with self.subTest(direction=direction, state=cue.state):
                    frame = render_state(direction, cue.state)
                    self.assertEqual(frame.mode, "1")
                    self.assertEqual(frame.size, (128, 64))
        for frame in anim.shutdown_timeline()[0]:
            self.assertEqual((frame.mode, frame.size), ("1", (128, 64)))

    def test_rendering_is_repeatable_and_does_not_rewrite_source_art(self):
        def sources():
            paths = [anim.HERE / "blech-titel.png", *sorted(anim.r.SPRITES.glob("*.png"))]
            return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}

        before = sources()
        anim.title_mask.cache_clear()
        anim.character.cache_clear()
        states = [anim.State(0, started=False), anim.State(1/3, "lift"),
                  anim.State(0.72, "move", travel=1), anim.State(1, "rest", done=True)]
        first = {(direction, state): render_state(direction, state).tobytes()
                 for direction in anim.DIRECTIONS for state in states}
        for direction, state in reversed(list(first)):
            frame = render_state(direction, state)
            self.assertEqual(frame.tobytes(), first[direction, state])
            frame.paste(255, (0, 0, 128, 64))
            self.assertEqual(render_state(direction, state).tobytes(), first[direction, state],
                             "Changing a returned frame must not mutate a cached source")
        self.assertEqual(sources(), before, "Rendering must leave title and sprites untouched")

    def test_blech_stays_fixed_through_the_whole_demo(self):
        # Full title rectangles include the negative space between the letters.
        boxes = {"werkbank": (4, 2, 76, 19), "typenschild": (60, 7, 124, 30)}
        timeline = anim.demo_timeline()
        for direction, box in boxes.items():
            title = render_state(direction, timeline[0].state).crop(box)
            self.assertIsNotNone(title.getbbox(), "The protected title must be visible")
            for cue in timeline[1:]:
                with self.subTest(direction=direction, state=cue.state):
                    self.assertEqual(render_state(direction, cue.state).crop(box).tobytes(),
                                     title.tobytes(), "Motion must not alter BLECH or its spacing")


class FramePackingTests(unittest.TestCase):
    def test_both_bit_orders_match_independent_golden_pixel_anchors(self):
        frame = Image.new("1", (128, 64), 255)
        for xy in ((0, 0), (1, 7), (37, 8), (92, 15), (63, 34), (127, 63)):
            frame.putpixel(xy, 0)
        anchors = {
            "lsb": {0: 0x01, 1: 0x80, 165: 0x01, 220: 0x80, 575: 0x04, 1023: 0x80},
            "msb": {0: 0x80, 1: 0x01, 165: 0x80, 220: 0x01, 575: 0x20, 1023: 0x01},
        }
        for order, values in anchors.items():
            golden = bytearray(1024)
            for index, value in values.items():
                golden[index] = value
            with self.subTest(order=order):
                packed = anim.pack_frame(frame, bit_order=order)
                self.assertEqual(packed, bytes(golden))
                self.assertEqual(anim.unpack_frame(golden, bit_order=order).tobytes(), frame.tobytes())
                inverted = anim.pack_frame(frame, bit_order=order, controller_inverted=True)
                # Simulate the controller's A7 operation independently of the decoder.
                self.assertEqual(bytes(b ^ 0xff for b in inverted), bytes(golden))
                self.assertEqual(anim.unpack_frame(inverted, bit_order=order,
                                                   controller_inverted=True).tobytes(), frame.tobytes())


class ProgressTests(unittest.TestCase):
    def test_only_a_completed_loader_can_show_100_percent(self):
        for progress in (0.99, 0.999, 0.999999, 1.0, 1.5):
            with self.subTest(progress=progress):
                state = anim.State(progress)
                self.assertEqual(state.percent, 99)
                self.assertLess(state.value, 1)
                self.assertTrue(material(state), "Unfinished loading must retain some material")
        self.assertEqual(anim.State(0.4, done=True).percent, 100)
        self.assertFalse(material(anim.State(0.4, done=True)))

    def test_stalled_progress_cannot_consume_or_move_material(self):
        for progress in (0, 0.14, 1/3, 0.54, 2/3, 0.999):
            expected = material(anim.State(progress))
            for _ in range(3):
                for pose in ("contact", "lift", "move", "rest"):
                    for travel in (0, 0.5, 1):
                        with self.subTest(progress=progress, pose=pose, travel=travel):
                            self.assertEqual(material(anim.State(progress, pose, travel)), expected)

    def test_progress_jumps_remove_only_consumed_material_without_a_backlog(self):
        previous = material(anim.State(0))
        for progress in (0.08, 0.72, 0.72, 0.91, 0.999):
            current = material(anim.State(progress))
            self.assertTrue(current <= previous, "Remaining lines must not translate or reappear")
            self.assertEqual(current, material(anim.State(progress, "rest", travel=1)),
                             "The current progress must work without replaying earlier poses")
            previous = current
        self.assertLess(len(previous), len(material(anim.State(0))))
        self.assertFalse(material(anim.State(1, done=True)))


class MotionTests(unittest.TestCase):
    def test_tube_and_grip_stay_rigid_through_contact_and_lifted_poses(self):
        reference = anim.tube_geometry((8, 17))
        length = math.dist(reference.start, reference.tip)
        arm_lengths = (math.dist(reference.shoulder, reference.elbow),
                       math.dist(reference.elbow, reference.grip))
        # Include the raised head and the origins of all three compositions.
        for origin in ((8, 17), (8, 16), (20, 16), (29, 16), (0, 3), (7, -1)):
            for away in (0, 0.5, 1):
                with self.subTest(origin=origin, away=away):
                    tube = anim.tube_geometry(origin, away)
                    self.assertAlmostEqual(math.dist(tube.start, tube.tip), length)
                    axis = (tube.tip[0]-tube.start[0], tube.tip[1]-tube.start[1])
                    grip = (tube.grip[0]-tube.start[0], tube.grip[1]-tube.start[1])
                    self.assertAlmostEqual(axis[0]*grip[1]-axis[1]*grip[0], 0)
                    along = axis[0]*grip[0]+axis[1]*grip[1]
                    self.assertGreater(along, 0)
                    self.assertLess(along, length*length, "The hand grips between the ends")
                    self.assertAlmostEqual(math.dist(tube.shoulder, tube.elbow), arm_lengths[0])
                    self.assertAlmostEqual(math.dist(tube.elbow, tube.grip), arm_lengths[1])
                    self.assertEqual(tube.nose,
                                     (reference.nose[0]+origin[0]-8, reference.nose[1]+origin[1]-17))
                    if away == 0:
                        self.assertEqual(tube.start, tube.nose, "Contact must follow the head")
                    else:
                        self.assertGreater(math.dist(tube.start, tube.nose), 0,
                                           "Lifting the tube must really release the nose")

    def test_shutdown_fits_the_existing_one_second_wait(self):
        frames, durations = anim.shutdown_timeline()
        self.assertEqual(len(frames), len(durations))
        self.assertTrue(all(duration > 0 for duration in durations))
        self.assertEqual(sum(durations), 1000, "GIF loop pauses must stay outside device timing")
        self.assertIsNotNone(frames[0].getbbox())
        self.assertIsNone(frames[-1].getbbox(), "The tube effect must finish on a dark screen")


if __name__ == "__main__":
    unittest.main()
