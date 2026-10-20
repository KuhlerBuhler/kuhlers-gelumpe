"""Behavior checks for the one-bit screen studies, without firmware or hardware.

    python3 -B entwuerfe/design-1.3/geraet/test_anim.py
"""
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

import anim


def render_state(direction, state):
    return anim.render_frame(direction, state.progress, pose=state.pose,
                             started=state.started, done=state.done,
                             shift=state.shift, eaten=state.eaten)


def material(state):
    image = anim.blank()
    anim.draw_dashes(image, state)
    px = image.load()
    return frozenset((x, y) for y in range(64) for x in range(128) if px[x, y])


class FrameContractTests(unittest.TestCase):
    def test_every_demo_and_shutdown_frame_is_native_one_bit(self):
        for direction in anim.DIRECTIONS:
            for cue in anim.demo_timeline() + anim.motion_timeline():
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
        states = [anim.State(0, "ready", started=False), anim.State(1/3, "lift"),
                  anim.State(0.72, "draw"), anim.State(1, "settle", done=True)]
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
        boxes = {"werkbank": (4, 2, 108, 19), "typenschild": (60, 7, 124, 30)}
        timeline = anim.demo_timeline() + anim.motion_timeline()
        for direction, box in boxes.items():
            title = render_state(direction, timeline[0].state).crop(box)
            self.assertIsNotNone(title.getbbox(), "The protected title must be visible")
            for cue in timeline[1:]:
                with self.subTest(direction=direction, state=cue.state):
                    self.assertEqual(render_state(direction, cue.state).crop(box).tobytes(),
                                     title.tobytes(), "Motion must not alter BLECH or its spacing")

    def test_wordmark_and_table_do_not_move_with_the_gesture(self):
        boxes = {"wordmark": (0, 0, 128, 20), "table edge": (4, 55, 124, 56)}
        timeline = anim.demo_timeline()
        reference = render_state("werkbank", timeline[0].state)
        for name, box in boxes.items():
            expected = reference.crop(box)
            self.assertIsNotNone(expected.getbbox(), f"The protected {name} must be visible")
            for cue in timeline[1:]:
                with self.subTest(region=name, pose=cue.state.pose, shift=cue.state.shift):
                    self.assertEqual(render_state("werkbank", cue.state).crop(box).tobytes(),
                                     expected.tobytes())

    def test_the_figure_never_touches_the_wordmark(self):
        mark = anim.blank()
        anim.draw_bands(mark)
        mark.paste(255, (anim.WORDMARK_SHIFT, 0), anim.wordmark())
        for cue in anim.demo_timeline():
            with self.subTest(pose=cue.state.pose, shift=cue.state.shift):
                self.assertEqual(render_state("werkbank", cue.state).crop((0, 0, 128, 20)).tobytes(),
                                 mark.crop((0, 0, 128, 20)).tobytes())

    def test_eyes_look_then_shut_then_tear_open(self):
        clock = 0
        for cue in anim.demo_timeline():
            look = anim.unhinged_look(cue.state, clock)
            with self.subTest(pose=cue.state.pose, done=cue.state.done, t=clock):
                if not cue.state.started:
                    self.assertEqual(look, anim.EYES_LOOK, "The still splash looks at you")
                elif not cue.state.done:
                    self.assertEqual(look, anim.EYES_CLOSED, "Eyes shut while drawing, no twitch")
                else:
                    self.assertNotEqual(look[0], look[1], "Torn open with unequal pupils")
                    self.assertTrue(look[5], "The small eye is bloodshot")
            clock += cue.duration_ms
        for progress in (0.01, 0.37, 0.5, 0.88, 0.99):
            self.assertEqual(anim.unhinged_look(anim.pass_state(progress), 1234),
                             anim.EYES_CLOSED)

    def test_footer_shows_the_status_text(self):
        still = anim.render_frame("werkbank", 0, pose="ready", started=False).crop((0, 56, 128, 64))
        tagline = anim.blank()
        anim.text(tagline, "MEINE ELECTRIBE ROOCHT BLECH!", 4, 58, small=True)
        self.assertEqual(still.tobytes(), tagline.crop((0, 56, 128, 64)).tobytes(),
                         "The still splash has no status yet, only the tagline")
        self.assertEqual(anim.status_line(anim.pass_state(0.5)), "LADE SAMPLES...")
        self.assertEqual(anim.status_line(anim.pass_state(1, done=True)), "FERTIG")

    def test_progress_does_not_accumulate_horizontal_or_vertical_body_travel(self):
        def gesture_without_progress_pixels(progress, pose):
            image = anim.render_frame("werkbank", progress, pose=pose)
            draw = ImageDraw.Draw(image)
            ox, oy = anim.werkbank_origin(pose)
            # Only the two 7px eyes and the single material row may change.
            for cx, cy in ((ox + 21, oy + 14), (ox + 33, oy + 16)):
                draw.rectangle((cx-3, cy-3, cx+3, cy+3), fill=0)
            draw.rectangle((49, 53, 68, 53), fill=0)
            return image.crop((0, 20, 80, 55)).tobytes()

        for pose in anim.MOTION_POSES:
            expected = gesture_without_progress_pixels(0, pose)
            for progress in (0.08, 0.17, 0.5, 0.87, 0.999, 0.08):
                with self.subTest(pose=pose, progress=progress):
                    self.assertEqual(gesture_without_progress_pixels(progress, pose), expected,
                                     "Real progress may change pupils and material, never relocate the figure")


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


class MotionExportTests(unittest.TestCase):
    def test_real_gifs_preserve_pixels_and_never_exceed_the_fps_cap(self):
        sequences = []
        for direction in anim.DIRECTIONS:
            timeline = anim.demo_timeline() if direction == "werkbank" else anim.layout_timeline()
            sequences.append((direction + "-loading", [render_state(direction, cue.state) for cue in timeline],
                              [cue.duration_ms for cue in timeline], False))
        motion = anim.motion_timeline()
        sequences.append(("werkbank-loop", [render_state("werkbank", cue.state) for cue in motion],
                          [cue.duration_ms for cue in motion], True))
        off_frames, off_durations = anim.shutdown_timeline()
        sequences.append(("shutdown", off_frames, off_durations, False))
        with TemporaryDirectory(prefix="anim-test-", dir=anim.ROOT.parent) as temporary:
            preview_dir, raw_dir = Path(temporary)/"preview", Path(temporary)/"raw"
            preview_dir.mkdir()
            raw_dir.mkdir()
            for name, frames, durations, include_loop in sequences:
                report = anim.export_sequence(name, frames, durations, preview_dir, raw_dir,
                                              include_loop=include_loop)
                self.assertEqual(len(list((raw_dir/name).glob("*.png"))), len(frames))
                # GIF encoders may combine equal consecutive frames into a longer hold.
                expected_steps = []
                for frame, duration in zip(frames, durations):
                    if expected_steps and frame.tobytes() == expected_steps[-1][0].tobytes():
                        expected_steps[-1][1] += duration
                    else:
                        expected_steps.append([frame, duration])
                for scale, suffix in ((1, "-1x"), (4, "")):
                    with self.subTest(sequence=name, scale=scale), Image.open(preview_dir/f"{name}{suffix}.gif") as gif:
                        self.assertEqual(gif.size, (128*scale, 64*scale))
                        self.assertEqual(gif.n_frames, len(expected_steps))
                        self.assertEqual(gif.info.get("loop"), 0)
                        decoded, actual_durations = [], []
                        for index, (frame, duration) in enumerate(expected_steps):
                            gif.seek(index)
                            rgb = gif.convert("RGB")
                            colors = rgb.getcolors(maxcolors=3)
                            self.assertIsNotNone(colors)
                            self.assertTrue({color for _, color in colors} <= {anim.LCD_DARK, anim.LCD_LIGHT})
                            expected = Image.new("RGB", (128, 64))
                            expected.putdata([anim.LCD_LIGHT if value else anim.LCD_DARK
                                              for value in frame.convert("L").tobytes()])
                            expected = expected.resize(rgb.size, Image.Resampling.NEAREST)
                            self.assertEqual(rgb.tobytes(), expected.tobytes(),
                                             "GIF compositing and scaling must preserve every intended pixel")
                            decoded.append(rgb.tobytes())
                            actual_durations.append(gif.info["duration"])
                            self.assertEqual(gif.info["duration"], duration)
                            self.assertGreaterEqual(gif.info["duration"], anim.MIN_FRAME_MS,
                                                    f"Frame {index} must hold at least {anim.MIN_FRAME_MS} ms, including the last before looping")
                        self.assertEqual(report["gif_frames"], gif.n_frames)
                        self.assertEqual(report["unique_frames"], len(set(decoded)))
                        self.assertEqual(report["duration_ms"], sum(actual_durations))
                self.assertEqual(report["full_frame_table_bytes"], len({f.tobytes() for f in frames})*1024)
                self.assertLessEqual(report["maximum_update_fps"], anim.MAX_FPS)
                self.assertGreaterEqual(report["minimum_frame_duration_ms"], anim.MIN_FRAME_MS)
                for index, frame in enumerate(frames):
                    with Image.open(raw_dir/name/f"{index:03d}.png") as raw:
                        self.assertEqual((raw.mode, raw.size), ("1", (128, 64)))
                        self.assertEqual(raw.tobytes(), frame.tobytes())

    def test_export_rejects_a_single_fast_hold_even_when_the_average_is_slow(self):
        first = anim.blank()
        second = first.copy()
        second.putpixel((10, 10), 255)
        with TemporaryDirectory(prefix="anim-test-", dir=anim.ROOT.parent) as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                anim.export_sequence("too-fast", [first, second], [anim.MIN_FRAME_MS - 1, 1801], root, root)
            with self.assertRaises(ValueError):
                anim.export_sequence("missing-duration", [first, second], [200], root, root)

    def test_loop_metrics_include_the_wrap_back_to_the_first_frame(self):
        first = anim.blank()
        second = first.copy()
        second.putpixel((0, 0), 255)
        third = second.copy()
        third.putpixel((127, 63), 255)
        frames = [first, second, third]
        once = anim.metrics(frames, [200]*3)
        loop = anim.metrics(frames, [200]*3, include_loop=True)
        self.assertEqual(once["changed_pixels_max"], 1)
        self.assertEqual(once["changed_pages_max"], 1)
        self.assertEqual(loop["changed_pixels_max"], 2,
                         "The largest change in this sequence is the return to frame one")
        self.assertEqual(loop["changed_bytes_max"], 2)
        self.assertEqual(loop["changed_pages_max"], 2)
        self.assertEqual(loop["changed_pixels_mean"], 1.33)


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
            first = anim.pass_state(progress)
            for _ in range(3):
                again = anim.pass_state(progress)
                with self.subTest(progress=progress):
                    self.assertEqual(again, first, "The frame depends on the loader value only")
                    self.assertEqual(material(again), material(first))

    def test_the_tip_eats_the_line_from_left_to_right(self):
        full = material(anim.State(0.4))
        self.assertEqual(full, frozenset((49 + i, 54 - k) for i, h in enumerate(anim.LUMPS) for k in range(h + 1)))
        previous = full
        for cue in anim.demo_timeline():
            current = material(cue.state)
            self.assertTrue(current <= previous, "Drawn line must not come back")
            if current and cue.state.pose == "draw":
                tip = anim.werkbank_tube(cue.state.pose, cue.state.shift).tip
                self.assertGreaterEqual(min(x for x, _ in current), round(tip[0]),
                                        "No line left behind the tube tip")
            previous = current
        self.assertFalse(previous, "Done shows no line")

    def test_completion_immediately_interrupts_every_motion_pose(self):
        expected = anim.render_frame("werkbank", 1, pose="settle", done=True).tobytes()
        for pose in anim.MOTION_POSES:
            with self.subTest(pose=pose):
                self.assertEqual(anim.render_frame("werkbank", 0.4, pose=pose, done=True).tobytes(),
                                 expected, "Completion must not wait for the gesture to finish")


class MotionTests(unittest.TestCase):
    def test_one_pass_goes_from_0_to_100(self):
        timeline = anim.demo_timeline()
        shifts = [cue.state.shift for cue in timeline]
        self.assertEqual(shifts, sorted(shifts), "Blechy only moves right")
        self.assertEqual((shifts[0], shifts[-1]), (0, anim.SWEEP))
        self.assertTrue(timeline[-1].state.done)
        self.assertTrue(all(cue.duration_ms >= anim.MIN_FRAME_MS for cue in timeline))
        for progress in (0, 0.3, 0.6, 0.99):
            self.assertEqual(anim.pass_state(progress).shift % anim.SWEEP_STEP, 0)

    def test_tube_grip_and_arm_bones_stay_rigid_in_the_actual_poses(self):
        origins = [anim.werkbank_origin(pose) for pose in anim.MOTION_POSES]
        self.assertEqual({x for x, _ in origins}, {8})
        self.assertEqual((min(y for _, y in origins), max(y for _, y in origins)), (18, 21))
        for current, following in zip(origins, origins[1:] + origins[:1]):
            self.assertLessEqual(abs(following[1]-current[1]), 1,
                                 "At the limited frame rate the head advances at most one pixel, including loop wrap")
        for pose in anim.MOTION_POSES:
            with self.subTest(pose=pose):
                tube = anim.werkbank_tube(pose)
                length = math.dist(tube.start, tube.tip)
                self.assertAlmostEqual(length, 15)
                axis = (tube.tip[0]-tube.start[0], tube.tip[1]-tube.start[1])
                grip = (tube.grip[0]-tube.start[0], tube.grip[1]-tube.start[1])
                self.assertAlmostEqual(axis[0]*grip[1]-axis[1]*grip[0], 0)
                along = axis[0]*grip[0]+axis[1]*grip[1]
                self.assertAlmostEqual(along/(length*length), 0.63,
                                       msg="The hand must not slide along the straw")
                self.assertAlmostEqual(math.dist(tube.shoulder, tube.elbow), 9)
                self.assertAlmostEqual(math.dist(tube.elbow, tube.grip), 9)
                ox, oy = anim.werkbank_origin(pose)
                self.assertEqual(tube.nose, (ox+29, oy+23))
                if pose == "draw":
                    self.assertEqual(tube.start, tube.nose)
                    self.assertEqual(tube.tip, (49, 53), "The contact pose must reach the fixed supply")
                elif pose in ("ready", "settle"):
                    self.assertGreater(math.dist(tube.start, tube.nose), 0)
                    self.assertLess(tube.tip[1], 53, "The released straw must clear the material")

    def test_shutdown_fits_the_existing_one_second_wait(self):
        frames, durations = anim.shutdown_timeline()
        self.assertEqual(len(frames), len(durations))
        self.assertTrue(all(duration > 0 for duration in durations))
        self.assertEqual(sum(durations), 1000, "GIF loop pauses must stay outside device timing")
        self.assertIsNotNone(frames[0].getbbox())
        self.assertIsNone(frames[-1].getbbox(), "The tube effect must finish on a dark screen")


if __name__ == "__main__":
    unittest.main()
