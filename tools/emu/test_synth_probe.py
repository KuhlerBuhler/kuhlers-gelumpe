# SPDX-License-Identifier: GPL-2.0-only
"""synth_probe.py: the bank builder and the readers run on made-up data, no firmware. The last class boots the
synth's own firmware (E2_BLUE_VSB, the SYSTEM.VSB of the blue Electribe 2) with a made-up bank and checks what it
sends to the DSP; it is skipped without the file, and runs only in the emulation runs (E2_LOCAL_REQUIRED or
E2_EMU_REQUIRED), a failure there when E2_EMU_REQUIRED=1."""

import importlib.util
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_probe as S  # noqa: E402

BLUE = os.environ.get("E2_BLUE_VSB")
REQUIRED = os.environ.get("E2_EMU_REQUIRED") == "1"
LOCAL = os.environ.get("E2_LOCAL_REQUIRED") == "1" or REQUIRED
UNICORN = importlib.util.find_spec("unicorn") is not None        # a Python without it cannot run the firmware


class Blocks(unittest.TestCase):
    def test_twelve_bit_values_survive_packing_for_every_length(self):
        for n in (1, 2, 3, 4, 5, 333, 2048):
            values = S.sine(n, 3) if n > 4 else [-2048, 2047, 0, -1][:n]
            self.assertEqual(S.unpack12(S.pack12(values), n), values)

    def test_a_stream_is_walked_by_its_block_heads(self):
        values = S.sine(5000, 7)
        data = b"STRM" + struct.pack("<III", 0xFFFFFFFF, len(values), S.checksum(values)) + b"\xff" * 16 + S.stream(values)
        walked = S.walk_stream(data, 0)
        self.assertEqual((walked["values"], walked["blocks"], walked["modes"], walked["end"]), (5000, 3, {7: 3}, len(data)))

    def test_a_coded_block_is_skipped_by_its_length(self):
        head = b"STRM" + struct.pack("<III", 0xFFFFFFFF, 6, 0) + b"\xff" * 16
        coded = struct.pack(">HH", (1 << 13) | 4, 3) + b"abc"
        raw = struct.pack(">H", (7 << 13) | 2) + S.pack12([1, 2])
        walked = S.walk_stream(head + coded + raw, 0)
        self.assertEqual((walked["values"], walked["modes"]), (6, {1: 1, 7: 1}))

    def test_the_checksum_is_the_sum_of_the_words_the_dsp_gets(self):
        self.assertEqual(S.checksum([1, -1, 0x7FF]), (16 + 0xFFF0 + 0x7FF0) & 0xFFFFFFFF)


class Bank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = S.build_bank(S.synthetic_waves())

    def test_the_bank_is_8_MiB_with_the_sum_the_firmware_checks(self):
        self.assertEqual(len(self.bank), S.BANK_SIZE)
        self.assertEqual(S.sum16(self.bank), 0)
        self.assertEqual(self.bank[:12], b"KORGelec2PCM")

    def test_it_reads_back_as_what_was_put_in(self):
        info = S.parse_bank(self.bank)
        self.assertTrue(info["counts_equal"])
        self.assertEqual((info["waves"]["count"], info["waves"]["one_shot"], info["waves"]["looped"]), (4, 4, 0))
        self.assertEqual(info["sections"]["SMPL"]["stream"]["values"], 200 + 300 + 1000 + 64)
        self.assertEqual(info["sections"]["SMPL"]["check"], S.checksum([v for _, w in S.synthetic_waves() for v in w]))
        self.assertEqual(info["waves"]["dsp_end"], S.DSP_BASE + S.LEAD_IN + 2 * 1564)

    def test_the_sections_sit_where_the_head_says_and_in_the_order_of_a_real_bank(self):
        at = {k: v["at"] for k, v in S.parse_bank(self.bank)["sections"].items()}
        self.assertEqual(sorted(at, key=at.get), ["DRMP", "DRUM", "MSPR", "MSRL", "MSVS", "SMPR", "SMPL"])
        self.assertEqual(at["DRMP"], 0x40)

    def test_a_bank_that_was_changed_no_longer_adds_up(self):
        broken = bytearray(self.bank)
        broken[0x4000] ^= 1
        self.assertNotEqual(S.sum16(broken), 0)

    def test_a_pcm_vsb_and_a_flash_dump_hold_the_same_bank(self):
        head = bytearray(S.HEADER)
        head[0x20:0x23] = b"PCM"
        self.assertEqual(S.bank_of(bytes(head) + self.bank), self.bank)
        self.assertEqual(S.bank_of(b"\xff" * S.BANK_FLASH + self.bank), self.bank)
        with self.assertRaises(ValueError):
            S.bank_of(b"\0" * 1000)

    def test_a_file_that_is_no_bank_is_refused(self):
        with self.assertRaises(ValueError):
            S.parse_bank(b"\xff" * S.BANK_SIZE)

    def test_the_expected_dsp_memory_is_the_values_times_16_behind_a_lead_in_of_sixteen(self):
        data = S.expected_dsp(S.synthetic_waves())
        self.assertEqual(len(data) % 32, 0)
        self.assertEqual(struct.unpack_from("<2H", data, 0), (0x4000, 0))
        first = S.synthetic_waves()[0][1]
        self.assertEqual(struct.unpack_from("<5H", data, S.LEAD_IN), tuple((v << 4) & 0xFFFF for v in first[:5]))


class Pitch(unittest.TestCase):
    def test_a_wave_at_the_dsp_rate_is_keyed_at_its_root(self):
        self.assertEqual(S.pitch_word(60, 48000), 60 * 256)

    def test_half_the_rate_is_an_octave_up(self):
        self.assertEqual(S.pitch_word(60, 24000), 72 * 256)

    def test_44100_hertz_is_about_a_semitone_and_a_half_up(self):
        self.assertAlmostEqual(S.pitch_word(60, 44100) / 256 - 60, 1.4687, places=3)

    def test_it_is_the_same_step_the_firmware_adds_to_a_bank_made_for_44100_hertz(self):
        self.assertAlmostEqual(S.PITCH_ADDED_AT_LOAD, 256 * 12 * __import__("math").log2(48000 / 44100), delta=1.5)


class Code(unittest.TestCase):
    def test_an_arm_immediate_is_found_for_the_limit(self):
        self.assertEqual(S.arm_immediate(0x198), 0xF66)
        with self.assertRaises(ValueError):
            S.arm_immediate(0x12345)

    def test_compares_with_the_limit_are_found_with_any_condition_and_register(self):
        words = [0xE3500F66, 0xE1A00000, 0xD3510F66, 0xE3500F67, 0xE3300F66]       # cmp r0; nop; cmple r1; cmp #0x199; teq
        payload = struct.pack("<5I", *words)
        self.assertEqual(S.compare_sites(payload, end=len(payload)), [S.BASE, S.BASE + 8])

    def test_the_users_of_a_literal_are_the_loads_that_reach_it(self):
        # ldr r0, [pc, #4] at 0: the pool word sits at 0 + 8 + 4 = 12
        words = [0xE59F0004, 0xE1A00000, 0xE1A00000, 0x12345678, 0xE59F1000, 0x12345678]
        payload = struct.pack("<6I", *words)
        self.assertEqual(S.literal_users(payload, 0x12345678, end=len(payload)), [S.BASE])


@unittest.skipUnless(BLUE and LOCAL and (UNICORN or REQUIRED), "needs E2_BLUE_VSB in an emulation run, and Unicorn")
class Firmware(unittest.TestCase):
    """Boots the synth's firmware on a made-up bank. Every number below is in docs/messungen/2026-10-15-synth-samples.md."""

    @classmethod
    def setUpClass(cls):
        import machine
        cls.machine = machine
        cls.payload = S.load_payload(BLUE)
        cls.waves = S.synthetic_waves()
        cls.flash = S.blank_synth_flash(machine, S.build_bank(cls.waves))

    def probe(self, seconds=2.0):
        p = S.Probe(self.payload, self.flash)
        p.run_to(seconds)
        return p

    def test_the_oscillator_table_is_where_the_probe_expects_it(self):
        self.assertTrue(S.check_osc(self.payload))
        table = S.osc_table(self.payload)
        self.assertEqual((len(table), table[S.OSC_SAW]["wave"], max(t["wave"] for t in table)), (S.OSC_COUNT, 1, 411))

    def test_it_boots_and_streams_every_value_as_a_16_bit_word_from_the_dsp_base(self):
        p = self.probe()
        self.assertEqual((p.m.screen(), p.m.asserts), (1, []))
        self.assertEqual(p.dsp_bytes(S.DSP_BASE, len(S.expected_dsp(self.waves))), S.expected_dsp(self.waves))
        self.assertEqual([t["address"] for t in p.tx if t["cmd"] == 0xAB and t["address"] < 0xFF000000], [S.DSP_BASE])

    def test_the_bank_is_read_into_the_work_buffer_in_ten_pieces(self):
        reads = [r for r in self.probe().flash_reads if r["flash"] >= S.BANK_FLASH]
        self.assertEqual((len(reads), sum(r["bytes"] for r in reads), reads[0]["ram"]), (10, S.BANK_SIZE, S.WORK_BUFFER[0]))

    def test_the_tables_hold_the_counts_and_the_start_the_loader_made_of_them(self):
        p = self.probe()
        self.assertEqual(p.tables()["counts"], {"count_instruments": 4, "count_mspr": 4, "count_msrl": 4, "count_smpr": 4, "count_drmp": 1})
        c = p.chain(S.PCM_FIRST_WAVE + 1)
        self.assertEqual((c["sample"], c["smpr"][0]), (1, S.DSP_BASE + S.LEAD_IN + 400))
        self.assertEqual(c["pitch_word"], 0x4800 + S.PITCH_ADDED_AT_LOAD)

    def test_a_note_on_an_instrument_sends_its_start_loop_and_pitch(self):
        p = self.probe(3.0)
        p.select_osc(1)
        note = p.press_pad()
        self.assertEqual(note["call"]["wave"], S.PCM_FIRST_WAVE + 1)
        self.assertEqual(note["voice_params"], {"start": hex(S.DSP_BASE + S.LEAD_IN + 400), "loop_start": hex(598 << 12), "loop_length": "0x0",
                                                "pitch": hex((0x4800 + S.PITCH_ADDED_AT_LOAD) << 16)})

    def test_a_loop_is_sent_as_its_start_and_its_length_and_a_moved_wave_changes_only_the_start(self):
        p = self.probe(3.0)
        c = p.chain(S.PCM_FIRST_WAVE + 1)
        p.set_smpr(c["sample"], start=0x1400000, loop=200, end=598)
        p.select_osc(1)
        note = p.press_pad()
        self.assertEqual(note["voice_params"], {"start": "0x1400000", "loop_start": hex(200 << 12), "loop_length": hex(398 << 12),
                                                "pitch": hex((0x4800 + S.PITCH_ADDED_AT_LOAD) << 16)})
        voices = {note["call"]["voice"]}
        p.set_smpr(c["sample"], start=0x1400020)
        again = p.press_pad()
        voices.add(again["call"]["voice"])
        self.assertEqual(len(voices), 2, "the next note takes the next voice")
        changed = {k for k in note["voice_params"] if note["voice_params"][k] != again["voice_params"][k]}
        self.assertEqual(changed, {"start"})

    def test_the_end_of_the_pcm_load_is_a_place_where_the_card_and_the_dsp_functions_work(self):
        p = S.Probe(self.payload, self.flash)
        self.assertTrue(p.run_to_pc(S.FUNCS["pcm_loaded"], 2.0))
        self.assertEqual(p.reg(6), 1)
        buffer, data = 0xC0140000, b"".join(struct.pack("<h", i * 100) for i in range(64))
        p.uc.mem_write(buffer, data)
        port = p.call_here(S.FUNCS["dsp_port"])
        end = S.DSP_BASE + len(S.expected_dsp(self.waves))
        p.call_here(S.FUNCS["dsp_write"], port, end, buffer, 64)
        self.assertEqual(p.dsp_bytes(end, len(data)), data)

    def test_an_appended_instrument_plays_from_the_address_it_was_written_to(self):
        p = S.Probe(self.payload, self.flash)
        self.assertTrue(p.run_to_pc(S.FUNCS["pcm_loaded"], 2.0))
        target = S.DSP_BASE + len(S.expected_dsp(self.waves))
        n = S.append_instrument(p, "IMPORT1", target, 998, 998, S.ONE_SHOT | 0x34, S.pitch_word(60, 32000))
        S.repoint_osc(p, 334, "IMPORT 1", n)
        p.leave()
        p.run_to(3.0)
        p.select_osc(334)
        note = p.press_pad()
        self.assertEqual((n, note["call"]["wave"]), (4, S.PCM_FIRST_WAVE + 4))
        self.assertEqual((note["voice_params"]["start"], note["voice_params"]["pitch"]), (hex(target), hex(S.pitch_word(60, 32000) << 16)))
        self.assertEqual(S.osc_table(bytes(p.read(S.BASE, S.PAYLOAD)))[334]["name"], "IMPORT 1")

    def test_exit_held_at_power_on_is_visible_where_the_card_loader_looks(self):
        for held, want in ((0, 0), (0x2000, 0x2000)):
            p = S.Probe(self.payload, self.flash)
            p.m.held = held
            self.assertTrue(p.run_to_pc(S.FUNCS["pcm_loaded"], 2.0))
            panel = p.u32(p.m.profile.values["panel"])
            self.assertEqual(p.u32(panel + 0x18) & 0x2000, want)


if __name__ == "__main__":
    unittest.main()
