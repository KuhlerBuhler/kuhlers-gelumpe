# SPDX-License-Identifier: GPL-2.0-only
"""Compare sample cursor checkpoints with normal FatFs on an own fragmented bank."""
import hashlib
import struct

import fat32
import sampleset
from machine import DSP_DATA, Machine
from sdcard import MemoryMedium, SDCard
from splash_cases import Dev

META, CURSOR = 0xC036AD88, 0xC00F9C80


def bank():
    waves = []
    for slot, frames, kind in [(500, 16000, 'pcm16'), (501, 9008, 'pcm24'), (502, 7008, 'stereo16')]:
        wave = sampleset.wav(slot, f'anchor{slot}', frames, kind=kind)
        if slot == 501:
            chunks, at = [], 12
            while at < len(wave):
                length = struct.unpack_from('<I', wave, at + 4)[0] + 8
                chunks.append(wave[at:at + length])
                at += length
            body = b'WAVE' + b''.join(reversed(chunks)) + b'JUNK' + struct.pack('<I', 24) + bytes(24)
            wave = b'RIFF' + struct.pack('<I', len(body)) + body
        waves.append((slot, wave))
    table, body = [0] * sampleset.SLOTS, bytearray()
    for slot, wave in waves:
        table[slot] = sampleset.HEADER + len(body)
        body += wave
    return b'e2s sample all\x1a\0' + struct.pack('<1020I', *table) + body


def fragmented_card(folder):
    path = f'/KORG/{folder}/e2sSample.all'
    data = bank()
    image = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(image)
    volume.write(path, data)
    old = volume.chain(volume.stat(path).cluster)
    extra = volume._alloc(len(old))
    chain = []
    for index, cluster in enumerate(old):
        chosen, unused = (extra[index], cluster) if index % 2 else (cluster, extra[index])
        if chosen != cluster:
            src, dst = volume._cluster_at(cluster), volume._cluster_at(chosen)
            image[dst:dst + volume.csz] = image[src:src + volume.csz]
        volume._set(unused, 0)
        volume.free += 1
        chain.append(chosen)
    for index, cluster in enumerate(chain):
        volume._set(cluster, chain[index + 1] if index + 1 < len(chain) else fat32.EOC)
    assert volume.read(path) == data
    volume.close()
    return image


def load(payload, flash, image, held):
    import unicorn
    machine = Machine(bytes(payload), flash)
    machine.insert_card(SDCard(MemoryMedium(bytearray(image))))
    dsp, fat_steps, original = {}, [0], machine.write

    def write(address, value):
        transfer = machine.dsp_xfer
        if address == DSP_DATA and transfer and transfer[2] > 0 and 0x365EC0 <= transfer[1] < 0x1C65EC0:
            dsp[transfer[1]] = value & 0xFFFF
        return original(address, value)

    machine.write = write
    machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda *args: fat_steps.__setitem__(0, fat_steps[0] + 1),
                        begin=0xC009C5E4, end=0xC009C5E4)
    device = Dev(payload, flash, held=held, machine=machine)
    device.run(3)
    digest = hashlib.sha256(b''.join(struct.pack('<IH', address, value) for address, value in sorted(dsp.items()))).hexdigest()
    return {'active': [slot for slot in range(500, 503) if device.read(META + slot * 0x45C + 11, 1) == b'\1'],
            'metadata': device.read(META + 500 * 0x45C, 3 * 0x45C).hex(), 'pcm_sha256': digest,
            'pcm_words': len(dsp), 'cursor': device.u32(CURSOR), 'fat_steps': fat_steps[0], 'asserts': machine.asserts}


def cases(payload, flash, folder):
    image = fragmented_card(folder)
    normal, anchor = load(payload, flash, image, 0x2000), load(payload, flash, image, 0)
    detail = {'normal': {k: v for k, v in normal.items() if k != 'metadata'},
              'anchor': {k: v for k, v in anchor.items() if k != 'metadata'}}
    return [
        {'id': 'sample-anker-fragmentiert-pcm-und-metadaten',
         'ok': normal['active'] == anchor['active'] == [500, 501, 502]
               and normal['metadata'] == anchor['metadata'] and normal['pcm_sha256'] == anchor['pcm_sha256']
               and normal['pcm_words'] > 0 and normal['cursor'] == anchor['cursor']
               and not normal['asserts'] and not anchor['asserts'], 'detail': detail},
        {'id': 'sample-anker-weniger-fat-schritte', 'ok': 0 < anchor['fat_steps'] < normal['fat_steps'], 'detail': detail},
    ]
