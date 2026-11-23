"""Synthetic outcome checks for the native CPU mode observation."""
import unittest
import sampleset
import sample_ram_modes as modes
import unicorn
from unicorn import arm_const as R
from highram_watch import HighWatch


class Outcomes(unittest.TestCase):
    def pattern_switch(self, browse=None, apply=True, unrelated=False, premature=False, stale_view=False):
        from types import SimpleNamespace
        import pattern_switch
        events = []
        state = dict(current=0, chosen=0, playing=0, confirmed=False)
        flags = browse if browse is not None else (0xFFFFFFFF, 0xFFFFFFFF)
        player, selector, transport = 0xC100, 0xC200, 0xC300
        def read(address):
            values = {0xC034029C: player, 0xC03487E8: selector,
                      player + 0x318: state['current'], selector + 0x318: state['chosen'],
                      transport + 0x308: state['playing'],
                      pattern_switch.STATE + pattern_switch.S_BROWSE: flags[0],
                      pattern_switch.STATE + pattern_switch.S_ARMED: flags[1]}
            return values[address]
        def tap(key, wait):
            events.append(key)
            if key == 'play': state['playing'] = 1
            if key == 'stop': state['playing'] = 0
            if key == 'menu': state['confirmed'] = True
        def turn(delta, wait):
            if not stale_view: state['chosen'] += delta
        def run(seconds):
            if state['chosen'] and apply and (browse != (1, 0) or state['confirmed'] or premature):
                state['current'] = state['chosen'] + int(unrelated)
        probe = SimpleNamespace(m=SimpleNamespace(u32=read, screen=lambda: 1),
                                dev=SimpleNamespace(call=lambda address: transport, turn=turn),
                                phase=lambda name: None, slots=lambda: 40,
                                until=lambda test, limit, step: test(), run=run, tap=tap)
        session = object.__new__(modes.Session);session.p = probe
        result = {}
        class Observed(Exception): pass
        def record(name, facts, ok):
            if name == 'play/switch':
                result.update(facts=facts, ok=ok)
                raise Observed
        session.record = record
        with self.assertRaises(Observed): session.run(40)
        return result, events

    def test_pattern_confirm_browse_needs_native_menu_before_switch(self):
        result, events = self.pattern_switch((1, 0))
        self.assertTrue(result['ok'])
        self.assertEqual(events, ['play', 'menu', 'stop'])
        self.assertEqual(result['facts']['pattern_after'], 1)

    def test_minimal_firmware_switches_without_opening_menu(self):
        result, events = self.pattern_switch()
        self.assertTrue(result['ok'])
        self.assertEqual(events, ['play', 'stop'])
        self.assertEqual(result['facts']['pattern_after'], 1)

    def test_other_browse_words_do_not_trigger_menu(self):
        for flags in ((1, 1), (7, 0), (0, 0)):
            with self.subTest(flags=flags):
                result, events = self.pattern_switch(flags)
                self.assertTrue(result['ok'])
                self.assertEqual(events, ['play', 'stop'])

    def test_menu_without_an_actual_switch_does_not_pass(self):
        result, events = self.pattern_switch((1, 0), apply=False)
        self.assertFalse(result['ok'])
        self.assertEqual(events, ['play', 'menu', 'stop'])

    def test_switching_to_an_unrelated_pattern_does_not_pass(self):
        result, events = self.pattern_switch(unrelated=True)
        self.assertFalse(result['ok'])
        self.assertEqual(events, ['play', 'stop'])

    def test_inconsistent_browse_does_not_confirm_an_already_changed_pattern(self):
        result, events = self.pattern_switch((1, 0), premature=True)
        self.assertFalse(result['ok'])
        self.assertEqual(events, ['play', 'stop'])

    def test_browse_without_a_different_view_does_not_open_menu(self):
        result, events = self.pattern_switch((1, 0), stale_view=True)
        self.assertFalse(result['ok'])
        self.assertEqual(events, ['play', 'stop'])

    def test_export_rechecks_actual_file_after_returning_to_main(self):
        from types import SimpleNamespace
        before = sampleset.build(sampleset.sized(3, 300))
        samples = sampleset.sized(3, 300);samples[500] = ('imp', 123)
        state = {'file': sampleset.build(samples)}
        session = object.__new__(modes.Session)
        session.p = SimpleNamespace(root='own', read_card=lambda path: state['file'], m=SimpleNamespace(asserts=[]))
        session.results = []
        def flow(name, page, steps, completed):
            self.assertTrue(completed())
            state['file'] = before
        session.flow = flow
        with self.assertRaisesRegex(ValueError, 'outcome failed'):
            session.export_all(before, 246, 3)

    def test_target_observer_covers_primary_and_alias_without_workbuffer_callbacks(self):
        from types import SimpleNamespace
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        for at, size in ((0xC0000000, 0x400000), (0xC0D3A000, 4096),
                         (0xC273A000, 0x16000), (0xC674F000, 4096)):
            uc.mem_map(at, size)
        watch = HighWatch(SimpleNamespace(uc=uc, A=R), upper_only=True)
        uc.mem_write(0xC0030000, bytes.fromhex('000081e51eff2fe1'))
        for dest in (0xC0D3A940, 0xC274F000, 0xC674F000):
            uc.reg_write(R.UC_ARM_REG_R0, 77)
            uc.reg_write(R.UC_ARM_REG_R1, dest)
            uc.reg_write(R.UC_ARM_REG_LR, 0xC0031000)
            uc.emu_start(0xC0030000, 0xC0031000)
        rows = watch.report()['phases'][0]['accesses']
        self.assertEqual({row['start'] for row in rows}, {'0xc274f000', '0xc674f000'})
        self.assertTrue(watch.report()['upper_only'])

    def test_file_flow_waits_for_completion_before_exiting(self):
        events = []
        class Probe:
            def to_main(self): events.append('main')
            def phase(self, name): events.append('phase')
            def data_utility(self, name): return True
            def tap(self, key, wait): events.append(key)
            def until(self, test, limit, step):
                events.append('completion')
                return test()
        session = object.__new__(modes.Session);session.p = Probe()
        session.data_utility = lambda name: True
        session.flow('own', 'own', [('menu', 1)], lambda: True)
        self.assertEqual(events, ['main', 'phase', 'menu', 'completion', 'main'])
        events.clear()
        with self.assertRaises(ValueError):session.flow('own', 'own', [], lambda: False)
        self.assertEqual(events, ['main', 'phase', 'completion'])

    def data_utility(self, start=0, vtable=0xC00E31F8, list_screen=15, stalled=False, browser=True):
        from types import SimpleNamespace
        state = dict(screen=1, index=start, moved=[], visited=[])
        events = []
        manager, screen = 0xC100, 0xC200
        def read(address):
            return {0xC03404C0: manager, manager + 0x20: screen,
                    screen: vtable, screen + 0x20: state['index']}[address]
        def tap(key, wait):
            events.append(key)
            if key == 'menu':
                state['screen'] = {1: 3, 14: list_screen, 15: 39 if browser else 15}[state['screen']]
            elif key == 'left' and state['screen'] == 3: state['screen'] = 14
            elif key in ('left', 'right') and state['screen'] == 15:
                if not stalled: state['index'] += 1 if key == 'right' else -1
                state['moved'].append(state['index'])
            state['visited'].append(state['screen'])
        def main(): state['screen'] = 1
        probe = SimpleNamespace(m=SimpleNamespace(u32=read, screen=lambda: state['screen'],
                                                  profile=SimpleNamespace(screens=0xC03404C0)),
                                tap=tap, to_main=main, phase=lambda name: None,
                                data_utility=lambda name: False)
        session = object.__new__(modes.Session);session.p = probe
        return session, state, events

    def test_themed_import_uses_native_index_and_opens_real_browser(self):
        session, state, events = self.data_utility()
        session.flow('import WAV', 'import sample', [('menu', 1)])
        self.assertIn(39, state['visited'])
        self.assertEqual(state['moved'], list(range(1, 9)))
        self.assertEqual(events[:3], ['menu', 'left', 'menu'])

    def test_native_data_utility_indices_are_checked_in_both_directions(self):
        for name, target in (('import sample', 8), ('export sample', 9), ('export all sample', 10)):
            with self.subTest(name=name):
                session, state, events = self.data_utility(start=13)
                self.assertTrue(session.data_utility(name))
                self.assertEqual(state['moved'], list(range(12, target - 1, -1)))
                self.assertNotIn('right', events)
                self.assertEqual(state['screen'], 15)

    def test_data_utility_rejects_wrong_list_screen_or_class(self):
        for values in ({'list_screen': 45}, {'vtable': 0}, {'start': 14}):
            with self.subTest(values=values):
                session, state, _ = self.data_utility(**values)
                with self.assertRaisesRegex(ValueError, 'DATA UTILITY'):
                    session.data_utility('import sample')
                self.assertEqual(state['moved'], [])

    def test_data_utility_rejects_a_stalled_native_index(self):
        session, state, _ = self.data_utility(stalled=True)
        with self.assertRaisesRegex(ValueError, 'DATA UTILITY'):
            session.data_utility('import sample')
        self.assertEqual(state['moved'], [0])

    def test_import_without_native_browser_does_not_pass(self):
        session, state, _ = self.data_utility(browser=False)
        with self.assertRaisesRegex(ValueError, 'browser'):
            session.flow('import WAV', 'import sample', [('menu', 1)])
        self.assertNotIn(39, state['visited'])

    def test_bank_requires_real_complete_riff_records(self):
        generated = sampleset.build(sampleset.sized(3, 300))
        self.assertEqual(modes.bank_slots(generated), [500, 501, 502])
        for broken in (None, bytes(len(generated)), generated[:-1]):
            with self.assertRaises(ValueError):modes.bank_slots(broken)

    def test_wav_verifies_declared_data_not_just_extension(self):
        wav = sampleset.wav(500, 'Own', 123)
        self.assertEqual(modes.wav_data_size(wav), 246)
        for broken in (bytes(len(wav)), wav[:44], wav[:-1]):
            with self.assertRaises(ValueError):modes.wav_data_size(broken)

    def test_closed_capture_with_live_slot_or_cursor_is_not_discarded(self):
        facts = dict(closed=True, state_after_exit=0, slots_before=4, slots_after_exit=4,
                     cursor_before=100, cursor_after_exit=100, active_before={1: 'own'}, active_after={1: 'own'})
        self.assertTrue(modes.capture_discarded(facts))
        for key, value in (('closed', False), ('state_after_exit', 11), ('slots_after_exit', 5), ('cursor_after_exit', 200)):
            self.assertFalse(modes.capture_discarded({**facts, key: value}))
        self.assertFalse(modes.capture_discarded({**facts, 'active_after': {2: 'own'}}))

    def test_all_export_requires_changed_expected_current_sample(self):
        before = sampleset.build(sampleset.sized(3, 300))
        samples = sampleset.sized(3, 300);samples[500] = ('imp', 123)
        after = sampleset.build(samples)
        expected = dict(slot=500, name=b'imp', pcm_bytes=246, slots=[500, 501, 502])
        self.assertTrue(modes.export_matches(before, after, **expected))
        self.assertFalse(modes.export_matches(before, before, **expected))
        self.assertFalse(modes.export_matches(before, after, **{**expected, 'pcm_bytes': 200}))

    def test_upper_accesses_include_the_physical_alias_only_for_matching_targets(self):
        report = dict(phases=[dict(phase='own', accesses=[
            dict(kind='w', start='0xc274ea3c', end='0xc274eff0'),
            dict(kind='w', start='0xc274f000', end='0xc274f004'),
            dict(kind='w', start='0xc4000000', end='0xc4000004'),
            dict(kind='r', start='0xc674f000', end='0xc674f004')])])
        result = modes.upper_accesses(report)
        self.assertEqual(len(result), 2)
        self.assertEqual([row['kind'] for row in result], ['w', 'r'])


if __name__ == '__main__':
    unittest.main()
