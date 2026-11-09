"""Observe native sample-mode CPU accesses with generated files, no audio or DMA."""
import argparse
import json
import struct
from pathlib import Path

import fat32
import sampleset
from highram_watch import Probe, SWITCH_SCREEN
import pattern_switch

START, END, ALIAS = 0xC274F000, 0xC4000000, 0x04000000


def wav_chunks(data):
    if not data or len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('no complete RIFF/WAVE')
    limit = 8 + struct.unpack_from('<I', data, 4)[0]
    if limit > len(data):
        raise ValueError('truncated RIFF')
    chunks, pos = {}, 12
    while pos < limit:
        if pos + 8 > limit:
            raise ValueError('truncated WAVE chunk')
        size = struct.unpack_from('<I', data, pos + 4)[0]
        end = pos + 8 + size
        if end > limit:
            raise ValueError('WAVE chunk beyond RIFF')
        chunks[data[pos:pos+4]] = data[pos+8:end]
        pos = end + (size & 1)
    if b'data' not in chunks:
        raise ValueError('no PCM data chunk')
    return chunks


def wav_data_size(data):
    return len(wav_chunks(data)[b'data'])


def export_matches(before, after, slot, name, pcm_bytes, slots):
    if before == after or bank_slots(after) != slots:
        return False
    offset = struct.unpack_from('<I', after, 16 + slot * 4)[0]
    chunks = wav_chunks(after[offset:])
    esli = chunks.get(b'korg', b'')
    return (len(chunks[b'data']) == pcm_bytes and esli[:4] == b'esli'
            and len(esli) >= 8 + sampleset.ESLI and esli[10:26].split(b'\0', 1)[0] == name)


def bank_slots(data):
    if not data or len(data) < 4096 or data[:16] != b'e2s sample all\x1a\0':
        raise ValueError('no complete sample bank header')
    slots = []
    for index, offset in enumerate(struct.unpack_from('<1020I', data, 16)):
        if offset:
            if offset < 4096 or offset + 12 > len(data):
                raise ValueError('sample index outside bank')
            wav_data_size(data[offset:])
            slots.append(index)
    return slots


def capture_discarded(facts):
    return (facts['closed'] and facts['state_after_exit'] == 0
            and facts['slots_after_exit'] == facts['slots_before']
            and facts['cursor_after_exit'] == facts['cursor_before']
            and facts['active_after'] == facts['active_before'])


def upper_accesses(watch):
    found = []
    for phase in watch['phases']:
        for row in phase['accesses']:
            lo, hi = int(row['start'], 0), int(row['end'], 0)
            if any(lo < end and hi > start for start, end in ((START, END), (START + ALIAS, END + ALIAS))):
                found.append(dict(phase=phase['phase'], **row))
    return found


class Session:
    def __init__(self, vsb, count, frames, duration):
        self.input = Path(vsb)
        self.duration = duration
        self.replacement = sampleset.build(sampleset.sized(6, 72000, names='own'))
        self.p = Probe(self.input.read_bytes()[0x100:], None, count, 50000, frames,
                       extra_files={'/zzreplace.all': self.replacement}, upper_only=True)
        self.results = []

    def record(self, name, facts, ok):
        result = {**facts, 'mode': name, 'ok': bool(ok and not self.p.m.asserts)}
        self.results.append(result)
        print(json.dumps(result), flush=True)
        if not result['ok']:
            raise ValueError('mode outcome failed: ' + name)

    def data_utility(self, name):
        target = {'import sample': 8, 'export sample': 9, 'export all sample': 10}[name]
        p = self.p
        p.tap('menu', 0.4)
        for _ in range(32):
            if p.m.screen() == 14:
                break
            p.tap('left', 0.25)
        else:
            raise ValueError('DATA UTILITY header missing')
        p.tap('menu', 0.4)
        def index():
            if p.m.screen() != 15:
                raise ValueError('DATA UTILITY native list missing')
            screen = p.m.u32(p.m.u32(p.m.profile.screens) + 0x20)
            if p.m.u32(screen) != 0xC00E31F8:
                raise ValueError('DATA UTILITY native class differs')
            value = p.m.u32(screen + 0x20)
            if not 0 <= value < 14:
                raise ValueError('DATA UTILITY native index differs')
            return value
        current = index()
        for _ in range(14):
            if current == target:
                return True
            direction = 1 if target > current else -1
            p.tap('right' if direction > 0 else 'left', 0.25)
            following = index()
            if following != current + direction:
                raise ValueError('DATA UTILITY native index did not move as requested')
            current = following
        raise ValueError('DATA UTILITY target missing: ' + name)

    def flow(self, name, page, steps, completed=None):
        self.p.to_main()
        self.p.phase(name)
        if not self.data_utility(page):
            raise ValueError('DATA UTILITY page missing: ' + page)
        for number, (key, wait) in enumerate(steps):
            if key.startswith('turn'):
                self.p.dev.turn(int(key[4:]), wait)
            else:
                self.p.tap(key, wait)
            if number == 0 and page == 'import sample' and key == 'menu' and self.p.m.screen() != 39:
                raise ValueError('native IMPORT SAMPLE browser did not open')
        if completed is not None:
            if not self.p.until(completed, 120, 1):
                raise ValueError('native operation did not complete: ' + name)
        self.p.to_main()

    def wav_files(self):
        volume = fat32.Volume(bytes(self.p.m.mmc.card.medium.data))
        try:
            return {path: volume.read(path) for path, _ in volume.walk() if path.lower().endswith('.wav')}
        finally:
            volume.close()

    def slot_info(self, slot):
        p = self.p
        def u16(at): return struct.unpack('<H', p.m.uc.mem_read(at, 2))[0]
        key = u16(0xC047B080 + slot * 32 + 30) - 50
        if not 0 <= key < 1000: raise ValueError('invalid logical mapping')
        first = u16(0xC035738C + key * 32 + 16)
        second = u16(0xC035F06C + first * 16 + 8)
        physical = u16(0xC0350644 + second * 8 + 2)
        if not 0 <= physical < 1000: raise ValueError('invalid physical mapping')
        record = 0xC036AD88 + physical * 0x45C
        name = bytes(p.m.uc.mem_read(0xC047B080 + slot * 32 + 12, 16)).split(b'\0', 1)[0]
        return dict(name=name.decode(errors='replace'), pcm_bytes=p.m.u32(record + 4),
                    loaded=p.m.uc.mem_read(record + 11, 1)[0] == 1)

    def select_edit(self, slot):
        p = self.p
        p.to_main()
        p.dev.call(SWITCH_SCREEN, 37, 0)
        p.run(0.4)
        outer = p.m.u32(p.m.profile.screens)
        screen = p.m.u32(outer + 0x20)
        if p.m.u32(screen) != 0xC00E39C8:
            raise ValueError('native sample-selection screen differs')
        manager = p.dev.call(0xC0035AD8)
        loaded = p.dev.call(0xC007DEAC, manager, slot)
        if loaded != 1:
            raise ValueError('sample for edit is not loaded')
        current = p.m.u32(manager + 0x3FC)
        p.dev.call(0xC007EC74, manager, slot - current, 1)
        if p.m.u32(manager + 0x3FC) != slot:
            raise ValueError('native SELECT SAMPLE did not select target')
        p.dev.call(0xC0069364, screen)
        p.run(0.5)
        screen = p.m.u32(outer + 0x20)
        if p.m.u32(screen) != 0xC00E3980 or not p.m.uc.mem_read(0xC0345A20, 1)[0]:
            raise ValueError('native edit snapshot is not ready')
        if struct.unpack('<H', p.m.uc.mem_read(0xC0345A2C, 2))[0] != slot:
            raise ValueError('native snapshot belongs to another slot')
        key = struct.unpack('<H', p.m.uc.mem_read(0xC047B080 + slot * 32 + 30, 2))[0] - 50
        return screen, manager, key

    def edit(self, write):
        p = self.p
        name = 'sample edit WRITE' if write else 'sample edit EXIT'
        p.phase(name)
        _, _, key = self.select_edit(500)
        before = p.dev.call(0xC004E63C, key, 0)
        p.dev.call(0xC004E63C, key, 1)
        changed = p.dev.call(0xC004E63C, key, 0)
        if write:
            p.m.press(0x0E, True)
            p.run(0.1)
            p.m.press(0x0E, False)
            p.run(2.0)
        p.tap('exit', 1.0)
        p.to_main()
        after = p.dev.call(0xC004E63C, key, 0)
        if write:
            self.written_start = after
        self.record(name, dict(before=before, changed=changed, after=after),
                    changed != before and after == (changed if write else before))

    def export_all(self, before_bank, expected_pcm, count):
        p = self.p
        def complete_export():
            data = p.read_card(f'KORG/{p.root}/Sample/e2sSample.all')
            try:
                good = export_matches(before_bank, data, 500, b'imp', expected_pcm, list(range(500, 500 + count)))
            except ValueError:
                return False
            return good
        self.flow('all export', 'export all sample', [('menu', 1), ('menu', 1), ('menu', 1)], complete_export)
        data = p.read_card(f'KORG/{p.root}/Sample/e2sSample.all')
        slots = bank_slots(data)
        self.record('all export', dict(file_bytes=len(data), slots=len(slots)),
                    export_matches(before_bank, data, 500, b'imp', expected_pcm, list(range(500, 500 + count))))

    def play_switch(self):
        p = self.p
        p.phase('play and pattern change')
        player = p.m.u32(0xC034029C)
        selector = p.m.u32(0xC03487E8)
        transport = p.dev.call(0xC0030D28)
        pattern_before = p.m.u32(player + 0x318)
        p.tap('play', 0.5)
        playing = p.m.u32(transport + 0x308)
        p.run(4)
        p.dev.turn(1, 0.5)
        p.run(4)
        pattern_view = p.m.u32(selector + 0x318)
        pattern_before_confirm = p.m.u32(player + 0x318)
        browse = tuple(p.m.u32(pattern_switch.STATE + offset)
                       for offset in (pattern_switch.S_BROWSE, pattern_switch.S_ARMED))
        browse_valid = browse != (1, 0) or (pattern_before_confirm == pattern_before and pattern_view != pattern_before)
        confirmation_requested = browse == (1, 0) and browse_valid
        if confirmation_requested:
            p.tap('menu', 0.5)
            p.run(4)
        pattern_after = p.m.u32(player + 0x318)
        p.tap('stop', 0.5)
        stopped = p.m.u32(transport + 0x308)
        self.record('play/switch', dict(playing=playing, stopped=stopped, pattern_before=pattern_before,
                                        pattern_view=pattern_view, pattern_before_confirm=pattern_before_confirm,
                                        browse=browse, confirmation_requested=confirmation_requested, pattern_after=pattern_after),
                    playing != 0 and stopped == 0 and browse_valid
                    and pattern_after == pattern_view and pattern_after != pattern_before)

    def run(self, count):
        p = self.p
        p.phase('boot with generated library')
        booted = p.until(lambda: p.m.screen() == 1 and p.slots() == count, 160, 1)
        p.run(2.0)
        self.record('boot', dict(slots=p.slots()), booted)
        self.play_switch()
        for source, name in ((0, 'sampling'), (1, 'resampling')):
            for stereo in (0, 1):
                mode = name + (' stereo' if stereo else ' mono')
                p.phase(mode)
                row = p.capture(source, stereo, self.duration, 0x40000, int(source == 1))
                self.record(mode, row, row['ok'] and capture_discarded(row))
        self.flow('import WAV', 'import sample', [('menu', 1), ('turn1', 1), ('menu', 6), ('menu', 8), ('menu', 1)])
        name = bytes(p.m.uc.mem_read(0xC047B080 + 500 * 32 + 12, 4))
        imported = self.slot_info(500)
        self.record('import WAV', imported, imported == dict(name='imp', pcm_bytes=100000, loaded=True))
        self.edit(False)
        self.edit(True)
        before = set(self.wav_files())
        p.to_main()
        p.phase('single export')
        self.flow('single export', 'export sample', [('menu', 1), ('menu', 1), ('menu', 8), ('menu', 1)])
        files = self.wav_files()
        created = {path: wav_data_size(data) for path, data in files.items() if path not in before}
        expected_pcm = 100000 - 2 * self.written_start
        self.record('single export', dict(created=created, expected_pcm=expected_pcm),
                    len(created) == 1 and list(created.values()) == [expected_pcm]
                    and next(iter(created)).endswith('501_imp.wav'))
        before_bank = p.read_card(f'KORG/{p.root}/Sample/e2sSample.all')
        self.export_all(before_bank, expected_pcm, count)
        self.flow('import ALL through IMPORT SAMPLE', 'import sample', [('menu', 1), ('turn2', 1), ('menu', 1), ('menu', 15), ('menu', 1)])
        name = bytes(p.m.uc.mem_read(0xC047B080 + 500 * 32 + 12, 16)).split(b'\0', 1)[0]
        imported = [self.slot_info(slot) for slot in range(500, 506)]
        self.record('import ALL', dict(slots=p.slots(), imported=imported), p.slots() == 6
                    and all(row == dict(name=f'own{501+i}', pcm_bytes=24000, loaded=True) for i, row in enumerate(imported)))
        p.phase('delete sample')
        screen, manager, _ = self.select_edit(500)
        before = p.slots()
        p.dev.call(0xC0069538, screen, 9)
        p.tap('menu', 0.4)
        p.tap('menu', 1.0)
        p.to_main()
        loaded = p.dev.call(0xC007DEAC, manager, 500)
        self.record('delete', dict(slots_before=before, slots_after=p.slots(), loaded=loaded), p.slots() == before - 1 and loaded == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vsb', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=40)
    parser.add_argument('--sample-frames', type=int, default=300000)
    parser.add_argument('--capture-seconds', type=float, default=8)
    args = parser.parse_args()
    output = args.report.resolve()
    if any((part / '.git').exists() for part in (output, *output.parents)):
        raise ValueError('report must be outside a repository')
    session = Session(args.vsb, args.samples, args.sample_frames, args.capture_seconds)
    error = None
    try:
        session.run(args.samples)
    except (RuntimeError, ValueError) as failure:
        error = str(failure)
    session.p.phase('end')
    watch = session.p.watch.report()
    report = dict(hardware_contact=False, audio=False, dma=False, usb_transfer_modelled=False,
                  proves_free_ram=False, results=session.results, error=error,
                  asserts=session.p.m.asserts, watch=watch, upper_accesses=upper_accesses(watch),
                  emulated_seconds=session.p.m.time_ns / 1e9)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if error is None and not report['asserts'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
