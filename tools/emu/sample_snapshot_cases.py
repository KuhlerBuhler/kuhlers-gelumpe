"""Exercise the standalone snapshot writer with native descriptors, DSP and FatFs."""
import argparse
import json
import struct
from pathlib import Path
from unittest.mock import patch

import swap_cases as c
import sample_snapshot
import sample_store

CODE, SCRATCH, SNAPSHOT, PATH = 0xC1000000, 0xC3000000, 0xC3018000, 0xC3030000


def distinct_audio(frames, seed, tag, channels, bits):
    if tag != 1 or bits != 16:
        raise ValueError('snapshot cases require generated 16-bit PCM')
    return b''.join(struct.pack('<h', (frame * (151 + 12 * channel) + 17003 * channel + 91) % 60001 - 30000)
                    for frame in range(frames) for channel in range(channels))


def cases(payload):
    if not c.has_hooks(payload):
        raise ValueError('the production swap transport must already be installed')
    results = []
    for kind in ('pcm16', 'stereo16'):
        samples = {500: ('Own snapshot', 33003, 44100, kind), 550: ('Own other', 101)}
        with patch.object(c.sampleset, 'audio', distinct_audio):
            original = c.sampleset.build(samples)
            box = c.Box(payload, None, samples, [500], record_dsp=True)
            expected = c.wav_pcm(500, 33003, kind)
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
        acquired = box.dev.call(box.sym['owner_acquire'], 2)
        token = box.u32(c.spec.FILE_OWNER)
        status = box.dev.call(code.symbols['store_snapshot'], PATH, 500) if acquired == 0 else -1
        resolved = box.dev.call(box.sym['owner_resolve'], token) if status == 0 else -1
        released = box.dev.call(box.sym['owner_release'], token) if acquired == 0 else -1
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
        again_acquired = box.dev.call(box.sym['owner_acquire'], 2)
        again_token = box.u32(c.spec.FILE_OWNER)
        writes = []
        hook = box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda *_: writes.append(True),
                                 begin=sample_store.API['WRITE'], end=sample_store.API['WRITE'])
        try:
            again_status = box.dev.call(code.symbols['store_snapshot'], PATH, 500) if again_acquired == 0 else -1
        finally:
            box.m.uc.hook_del(hook)
        again_resolved = box.dev.call(box.sym['owner_resolve'], again_token) if again_status == 0 else -1
        again_released = box.dev.call(box.sym['owner_release'], again_token) if again_acquired == 0 else -1
        volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
        try:
            same = volume.read(path) == saved
        finally:
            volume.close()
        repeat_ok = again_acquired == again_status == again_resolved == again_released == 0 and same and not writes
        results.append(dict(id=f'native_snapshot_{kind}_appends_verified_full_entry',
                            ok=acquired == status == resolved == released == 0 and correct and metadata_equal and unchanged
                            and header == (1, channels, 44100, 44100 * channels * 2, channels * 2, 16)
                            and offset == len(original) and no_journal and repeat_ok and not box.m.asserts,
                            status=status, pcm_bytes=pcm_bytes, pcm_equal=correct,
                            changed_name_saved=metadata_equal,
                            owner_status=[acquired, resolved, released],
                            fmt=list(header), index=offset, expected_index=len(original),
                            unchanged_repeat=repeat_ok, repeated_file_writes=len(writes),
                            old_entries_unchanged=unchanged, journal_removed=no_journal,
                            standalone_adapter=True, native_menu_connected=False))
        saved_card = bytes(box.m.mmc.card.medium.data)
        with patch.object(c, 'card', lambda *args, **kwargs: c.SDCard(c.MemoryMedium(bytearray(saved_card)))):
            rebooted = c.Box(payload, None, samples, [500], record_dsp=True)
        pcm_equal = (rebooted.resident(500)
                     and rebooted.dsp_bytes(*rebooted.extent(500)) == expected)
        name_equal = bytes(rebooted.m.uc.mem_read(c.NAMES + 500 * 32 + 12, 16)) == name
        results.append(dict(id=f'native_snapshot_{kind}_survives_reboot',
                            ok=pcm_equal and name_equal and not rebooted.m.asserts,
                            pcm_equal=pcm_equal, changed_name_saved=name_equal, standalone_adapter=True))
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
