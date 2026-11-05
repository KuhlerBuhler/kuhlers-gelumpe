"""Exercise the standalone snapshot writer with native descriptors, DSP and FatFs."""
import argparse
import json
import struct
from pathlib import Path
from unittest.mock import patch

import swap_cases as c
import sample_snapshot
import sample_store
from sample_residency_probe import publish_native

CODE, SCRATCH, SNAPSHOT, PATH = 0xC1000000, 0xC3000000, 0xC3018000, 0xC3030000


def distinct_audio(frames, seed, tag, channels, bits):
    if tag != 1 or bits != 16:
        raise ValueError('snapshot cases require generated 16-bit PCM')
    return b''.join(struct.pack('<h', (frame * (151 + 12 * channel) + 17003 * channel + 47 * seed + 91) % 60001 - 30000)
                    for frame in range(frames) for channel in range(channels))


def relocate(box, pcm):
    """Publish the generated replacement in an unused native row while the CPU is paused."""
    key, sentinel = 601, 602
    source_path = PATH + 256
    box.m.uc.mem_write(source_path, b'SD:/replacement.wav\0')
    opened = box.dev.call(c.spec.FIRMWARE['F_OPEN'], c.spec.FIL, source_path, 1)
    if opened != 0:
        raise AssertionError(f'replacement open failed: {opened}')
    box.dev.call(0xC004E1F4, c.spec.DESC)
    box.m.uc.mem_write(c.spec.STATE + c.spec.OFF['PREP'], struct.pack('<I', 1))
    try:
        parsed = box.dev.call(c.spec.FIRMWARE['PARSER'], c.spec.FIL, c.spec.DESC, 500, source_path)
    finally:
        box.m.uc.mem_write(c.spec.STATE + c.spec.OFF['PREP'], struct.pack('<I', 0))
        closed = box.dev.call(c.spec.FIRMWARE['F_CLOSE'], c.spec.FIL)
    if parsed != 0x7E or closed != 0:
        raise AssertionError(f'replacement parse/close failed: {parsed}/{closed}')
    for slot in range(500, 999):
        if box.u16(c.NAMES + slot * 32 + 30) == key + 50:
            if box.resident(slot):
                raise AssertionError('replacement row is already resident')
            box.m.uc.mem_write(c.NAMES + slot * 32 + 30, struct.pack('<H', sentinel + 50))
    base = (box.u32(c.CURSOR) + 31) & ~31
    staged = pcm.ljust((len(pcm) + 31) & ~31, b'\0')
    box.m.uc.mem_write(c.CURSOR, struct.pack('<I', base + len(staged)))
    box.m.uc.mem_write(c.spec.STAGE, staged)
    transferred = box.dev.call(box.sym['transfer'], 1, c.spec.STAGE, base, len(staged) // 2)
    descriptor = bytearray(box.m.uc.mem_read(c.spec.DESC, 0x4A0))
    struct.pack_into('<H', descriptor, 20, key + 50)
    struct.pack_into('<I', descriptor, 56, base)
    published = publish_native(box, descriptor, key, base)
    if transferred != 0 or published != 1 or box.meta_index(500) != key:
        raise AssertionError(f'replacement transfer/publication failed: {transferred}/{published}')
    box.m.dsp_mem.update(box.dsp)


def cases(payload):
    if not c.has_hooks(payload):
        raise ValueError('the production swap transport must already be installed')
    results = []
    for kind, moved in (('pcm16', False), ('stereo16', False), ('pcm16', True), ('stereo16', True)):
        label = kind + ('_relocated' if moved else '')
        frames = 8193 if moved else 33003
        samples = {500: ('Own snapshot', 101 if moved else frames, 44100, kind), 550: ('Own other', 101)}
        with patch.object(c.sampleset, 'audio', distinct_audio):
            original = c.sampleset.build(samples)
            replacement = c.sampleset.wav(600, 'Replacement', frames, rate=44100, kind=kind)
            box = c.Box(payload, None, samples, [500, 550], record_dsp=True,
                        extra={'/replacement.wav': replacement.hex()} if moved else None)
            expected = c.wav_pcm(600 if moved else 500, frames, kind)
            other_pcm = c.wav_pcm(550, 101)
        old_extent = box.extent(500)
        old_pcm = box.dsp_bytes(*old_extent)
        if moved:
            if old_pcm == expected[:len(old_pcm)]:
                raise AssertionError('replacement PCM must differ from the previous version')
            relocate(box, expected)
        mapping = [500, box.u16(c.NAMES + 500 * 32 + 30), box.meta_index(500)]
        box.m.dsp_mem.update(box.dsp)
        name = b'New snapshot'.ljust(16, b'\0')
        box.m.uc.mem_write(c.NAMES + 500 * 32 + 12, name)
        source = sample_store.source(SCRATCH) + sample_snapshot.source(SNAPSHOT, transfer=box.sym['transfer'])
        code = c.spec.arm.assemble(source, origin=CODE)
        box.m.uc.mem_write(CODE, code.bytes)
        folder = c.cardstore.card_folder(payload)
        path = f'KORG/{folder}/Sample/e2sSample.all'
        box.m.uc.mem_write(PATH, ('SD:/' + path + '\0').encode())
        box.m.uc.ctl_flush_tb()
        acquired = box.dev.call(box.sym['catalogue_begin'])
        token = box.u32(c.spec.FILE_OWNER)
        status = box.dev.call(code.symbols['store_snapshot'], PATH, 500) if acquired == 0 else -1
        completed = box.dev.call(box.sym['catalogue_end'], token, status) if acquired == 0 else -1
        volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
        try:
            saved = volume.read(path)
            try:
                volume.stat(path[:-3] + 'txn')
                no_journal = False
            except c.fat32.NotFound:
                no_journal = True
        finally:
            volume.close()
        offset = struct.unpack_from('<I', saved, 16 + 500 * 4)[0]
        entry = saved[offset:]
        header = struct.unpack_from('<HHIIHH', entry, 20)
        pcm_bytes = struct.unpack_from('<I', entry, 40)[0]
        channels = 2 if kind == 'stereo16' else 1
        unchanged = saved[4096:len(original)] == original[4096:]
        correct = pcm_bytes == len(expected) and entry[44:44 + pcm_bytes] == expected
        metadata_equal = entry[44 + pcm_bytes + 18:44 + pcm_bytes + 34] == name
        descriptor = 44 + pcm_bytes + 16
        file_mapping = [struct.unpack_from('<H', entry, descriptor + at)[0] for at in (0, 20, 78)]
        old_pcm_retained = not moved or box.dsp_bytes(*old_extent) == old_pcm
        other_retained = box.resident(550) and box.dsp_bytes(*box.extent(550)) == other_pcm
        catalogue_equal = box.u32(c.spec.HDR + 16 + 500 * 4) == offset
        again_acquired = box.dev.call(box.sym['catalogue_begin'])
        again_token = box.u32(c.spec.FILE_OWNER)
        writes = []
        hook = box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda *_: writes.append(True),
                                 begin=sample_store.API['WRITE'], end=sample_store.API['WRITE'])
        try:
            again_status = box.dev.call(code.symbols['store_snapshot'], PATH, 500) if again_acquired == 0 else -1
        finally:
            box.m.uc.hook_del(hook)
        again_completed = box.dev.call(box.sym['catalogue_end'], again_token, again_status) if again_acquired == 0 else -1
        volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
        try:
            same = volume.read(path) == saved
        finally:
            volume.close()
        owner = struct.unpack('<4I', box.m.uc.mem_read(c.spec.FILE_OWNER, 16))
        repeat_ok = (again_acquired == again_status == again_completed == 0 and same and not writes
                     and owner[0] == owner[2] == 0)
        results.append(dict(id=f'native_snapshot_{label}_appends_verified_full_entry',
                            ok=acquired == status == completed == 0 and correct and metadata_equal and unchanged
                            and header == (1, channels, 44100, 44100 * channels * 2, channels * 2, 16)
                            and offset == len(original) and no_journal and repeat_ok and not box.m.asserts
                            and file_mapping == [500, 550, 500] and old_pcm_retained and other_retained and catalogue_equal,
                            status=status, pcm_bytes=pcm_bytes, pcm_equal=correct,
                            changed_name_saved=metadata_equal,
                            owner_status=[acquired, completed], live_catalogue_equal=catalogue_equal,
                            fmt=list(header), index=offset, expected_index=len(original),
                            unchanged_repeat=repeat_ok, repeated_file_writes=len(writes),
                            old_entries_unchanged=unchanged, journal_removed=no_journal,
                            runtime_mapping=mapping, saved_mapping=file_mapping,
                            previous_pcm_retained=old_pcm_retained, other_sample_retained=other_retained,
                            standalone_adapter=True, native_menu_connected=False))
        saved_card = bytes(box.m.mmc.card.medium.data)
        with patch.object(c, 'card', lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(saved_card)))):
            rebooted = c.Box(payload, None, samples, [500, 550], record_dsp=True)
        pcm_equal = (rebooted.resident(500)
                     and rebooted.dsp_bytes(*rebooted.extent(500)) == expected)
        name_equal = bytes(rebooted.m.uc.mem_read(c.NAMES + 500 * 32 + 12, 16)) == name
        other_equal = (rebooted.resident(550) and rebooted.dsp_bytes(*rebooted.extent(550)) == other_pcm
                       and bytes(rebooted.m.uc.mem_read(c.NAMES + 550 * 32 + 12, 16)) == b'Own other'.ljust(16, b'\0'))
        results.append(dict(id=f'native_snapshot_{label}_survives_reboot',
                            ok=pcm_equal and name_equal and other_equal and not rebooted.m.asserts,
                            pcm_equal=pcm_equal, changed_name_saved=name_equal,
                            other_sample_retained=other_equal, standalone_adapter=True))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    args = parser.parse_args()
    checks = cases(args.patched.read_bytes()[c.HEADER:])
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, checks=checks), indent=2))
    return 0 if all(check['ok'] for check in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
