"""Macro file boundaries and the prerequisites for native integration."""
import struct
import unittest
import zlib

import macro_contract as macro


def recorder_evidence():
    initial = dict(screen=1, osc=0, level=100, pad_mode=3, selected_part=0, selected_pattern=0, mute4=0)
    actions = dict(encoder=("osc", 3), knob=("level", 40), mode=("pad_mode", 4),
                   menu=("screen", 3), part=("selected_part", 1), pattern=("selected_pattern", 1), mute=("mute4", 1))
    rows = [dict(case="baseline", before=dict(initial), after=dict(initial), file_bytes=64,
                 changed_bytes=0, contains_start_pattern=True, asserts=[])]
    for name, (field, value) in actions.items():
        rows.append(dict(case=name, before=dict(initial), after=dict(initial, **{field: value}),
                         file_bytes=80 if name in ("encoder", "knob", "mute") else 64,
                         changed_bytes=16 if name in ("encoder", "knob", "mute") else 1,
                         contains_start_pattern=True, asserts=[]))
    return dict(valid=True, cases=rows, playback=dict(asserts=[], before=dict(osc=20),
                                                    initial=dict(osc=0), final=dict(osc=20)))


class MacroContractTests(unittest.TestCase):
    def test_relative_encoder_and_equal_phase_order_round_trip(self):
        events = [(0, bytes([1, 1, 0, 3, 0])), (0, bytes([0, 13, 1, 0, 0])),
                  (1 << 32, bytes([0, 13, 0, 0, 0]))]
        raw = macro.encode("Uebergang", events, 2 << 32, capacity=8, generation=2)
        self.assertEqual(len(raw), 64 + 3 * 16)
        self.assertEqual(macro.decode(raw, capacity=8), ("Uebergang", events, 2 << 32, 2))

    def test_rejects_control_system_and_malformed_panel_messages(self):
        for msg in ([6, 1, 0, 0, 0], [3, 0, 0, 0, 0], [0, 35, 1, 0, 0],
                    [0, 1, 1, 0, 0], [1, 5, 0, 1, 0], [1, 1, 1, 3, 0],
                    [4, 16, 0, 127, 1], [5, 4, 0, 0, 0], [0, 13, 2, 0, 0]):
            with self.subTest(msg=msg), self.assertRaises(ValueError):
                macro.encode("Bad", [(0, bytes(msg))], 1, capacity=8)

    def test_file_bounds_and_reserved_bytes_are_validated_even_with_correct_crc(self):
        raw = macro.encode("OK", [(0, bytes([1, 1, 0, 3, 0]))], 1, capacity=8)
        for at, value in [(4, 2), (6, 63), (8, 255), (12, 0), (63, 1), (77, 1)]:
            bad = bytearray(raw)
            bad[at] = value
            struct.pack_into("<I", bad, 24, 0)
            struct.pack_into("<I", bad, 24, zlib.crc32(bad))
            with self.subTest(at=at), self.assertRaises(ValueError):
                macro.decode(bad, capacity=8)
        for bad in (raw[:-1], raw + b"\0", raw[:40]):
            with self.assertRaises(ValueError):
                macro.decode(bad, capacity=8)

    def test_capacity_phase_name_and_checksum_fail_closed(self):
        event = (0, bytes([1, 1, 0, 3, 0]))
        for events, end, name in [([], 1, "OK"), ([event] * 9, 1, "OK"),
                                  ([(2, event[1]), event], 3, "OK"),
                                  ([(2, event[1])], 1, "OK"), ([event], 1, "x" * 32),
                                  ([event], 1, "a\0b"), ([event], 1, "ä")]:
            with self.subTest(name=name, end=end), self.assertRaises(ValueError):
                macro.encode(name, events, end, capacity=8)
        raw = bytearray(macro.encode("OK", [event], 1, capacity=8))
        raw[-1] ^= 1
        with self.assertRaises(ValueError):
            macro.decode(raw, capacity=8)
        with self.assertRaises(ValueError):
            macro.encode("Too large", [event], 1, capacity=macro.CAPACITY + 1)

    def test_pad_velocity_keeps_both_original_bytes(self):
        msg = bytes([4, 3, 0x12, 0x34, 1])
        self.assertEqual(macro.panel_message(msg), msg)

    def test_phase_integral_carries_remainder_across_tempo_changes(self):
        phase = remainder = 0
        for _ in range(8000):
            phase, remainder = macro.advance(phase, remainder, 1000, 12000)
        self.assertEqual(phase, 16 << 32)
        phase2, _ = macro.advance(0, 0, 6_400_000, 15000)
        self.assertEqual(phase2, phase)
        phase, remainder = macro.advance(0, 0, 1_000_000, 12000)
        phase, remainder = macro.advance(phase, remainder, 1_000_000, 15000)
        self.assertEqual(phase, (9 << 31))

    def test_effective_tempo_comes_from_clock_period(self):
        self.assertEqual(macro.tempo_from_period(217_013_889), 12000)
        self.assertEqual(macro.tempo_from_period(173_611_111), 15000)
        for value in (0, 1, 2**32, -1):
            with self.assertRaises(ValueError):
                macro.tempo_from_period(value)

    def test_research_gate_does_not_accept_missing_or_invented_evidence(self):
        self.assertTrue(macro.research_errors({"schema": 1, "builds": []}))
        for report in ({}, {"schema": 1, "builds": [{"build": "hacktribe", "status": "PASS"}]}):
            self.assertTrue(macro.research_errors(report))

    def test_research_gate_checks_each_build_and_each_limit(self):
        import copy
        row = dict(firmware_sha256="a" * 64, asserts=[],
                   harness=dict(slice=2000, timer_irq_count=1000, timer_window_ms=1000),
                   input=dict(ordered=True, task="CsTask", origin_separated=True),
                   replay=dict(task="CsTask", irq_enabled=True, unsafe_calls=0, extra_latency_ms=[1] * 24,
                               due_lateness_ms=[1.35] * 24, normal_transport_calls=4, observed_transport_calls=8,
                               replay_ui_calls=4, transport_transitions=[dict(key=2, before=0, after=1),
                                                                         dict(key=1, before=1, after=0)],
                               registers_preserved=True, stack_bytes=64,
                               observed_stack_bytes=dict(cs=512, periodic=128),
                               wrapper_tasks=dict(cs=["CsTask"], periodic=["PeriodicTask"]),
                               burst_ordered=True, burst_max_extra_latency_ms=1.5, max_messages_per_wake=8),
                   tempo=dict(internal=True, stopped=True, external=True, asserts=[]),
                   memory=dict(no_overlap=True, erased=True, capacity=512, buffer_bytes=8192,
                               code_bytes=8192, areas=[dict(at=f"{a:#010x}", length=n, what=name)
                                   for a, n, name in macro.MEMORY_AREAS]))
        report = dict(schema=1, builds=[dict(copy.deepcopy(row), build=b) for b in macro.BUILDS])
        report["builds"][0]["event_recorder"] = recorder_evidence()
        self.assertEqual(macro.research_errors(report), [])
        sources = dict(research_source_sha256="1" * 64, contract_source_sha256="2" * 64)
        owners = {b: "3" * 64 for b in macro.BUILDS}
        for r in report["builds"]:
            r["section_sources"] = {s: dict(sources) for s in ("input", "tempo", "memory", "event")}
            r["memory"]["ownership_sha256"] = owners[r["build"]]
        self.assertEqual(macro.research_errors(report, sources=sources, ownership=owners), [])
        stale = copy.deepcopy(report)
        stale["builds"][0]["section_sources"]["input"]["research_source_sha256"] = "0" * 64
        self.assertTrue(any("input" in e for e in macro.research_errors(stale, sources=sources, ownership=owners)))
        owners["stock"] = "4" * 64
        self.assertTrue(any("ownership" in e for e in macro.research_errors(report, sources=sources, ownership=owners)))
        for section, field, value in [("harness", "timer_irq_count", 500),
                                      ("replay", "extra_latency_ms", [2.1] * 24),
                                      ("replay", "due_lateness_ms", [-1] * 24),
                                      ("replay", "transport_transitions", []),
                                      ("replay", "replay_ui_calls", 0),
                                      ("replay", "stack_bytes", 2048),
                                      ("replay", "observed_stack_bytes", {}),
                                      ("replay", "burst_ordered", False),
                                      ("replay", "wrapper_tasks", dict(cs=["SeqTask"])),
                                      ("memory", "capacity", 513),
                                      ("memory", "areas", []),
                                      ("tempo", "external", False),
                                      ("event_recorder", "valid", False)]:
            bad = copy.deepcopy(report)
            bad["builds"][0][section][field] = value
            with self.subTest(section=section, field=field):
                self.assertTrue(macro.research_errors(bad))
        bad = copy.deepcopy(report)
        bad["builds"][0]["event_recorder"]["playback"]["asserts"] = [dict(line=1)]
        self.assertTrue(macro.research_errors(bad))

    def test_recorder_comparison_rejects_missing_and_ineffective_cases(self):
        import copy
        good = recorder_evidence()
        self.assertEqual(macro.recorder_errors(good), [])
        for name in ("encoder", "knob", "mode", "menu", "part", "mute", "pattern"):
            bad = copy.deepcopy(good)
            row = next(r for r in bad["cases"] if r["case"] == name)
            row["after"] = dict(row["before"])
            with self.subTest(name=name):
                self.assertTrue(macro.recorder_errors(bad))
        bad = copy.deepcopy(good)
        bad["cases"].pop()
        self.assertTrue(macro.recorder_errors(bad))


if __name__ == "__main__":
    unittest.main()
