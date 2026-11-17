# SPDX-License-Identifier: GPL-2.0-only
"""Native recording worker on a virtual card with a synthetic capture source.

The isolated worker runs in scratch RAM; the integrated case uses the permanent
CommandTask hook and the native panel setup.
The original FatFs, SD driver and DSP host-port functions execute as ARM code.
The capture model supplies own stereo words; the real DSP arithmetic is checked
separately by tools/dsp/recording_patch_probe.py. No device access.
"""
import argparse
import io
import json
from pathlib import Path
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
import fat32
from dsp_model import DspModel
from sdcard import MemoryMedium, SDCard
from splash_cases import Dev, user_flash
from menu_cases import card_image
from tools.patch import recording_dsp as dsp_spec, recording_service, recording_runtime, script_hooks

CODE, CONTEXT, RING = 0xC3F00000, 0xC3F10000, 0xC3F20000
COMMAND_TICK = 0xC002A628


def has_hooks(payload):
    offset = dsp_spec.APPEND - 0xC0000000 + dsp_spec.MAGIC_ADDRESS - dsp_spec.CODE
    return payload[offset:offset + 4] == struct.pack('<I', dsp_spec.MAGIC)


def sample(index):
    return (((index * 17 + 1234) & 65535) << 16) | ((index * 31 + 4321) & 65535)


def pcm(first, count):
    return b''.join(struct.pack('<HH', sample(index) >> 16, sample(index) & 65535)
                    for index in range(first, first + count))


class CaptureModel(DspModel):
    """0x37 capture at 48 kHz; DSP code and SD latency are not inferred here."""
    def __init__(self, machine):
        super().__init__(machine)
        self.active, self.started, self.frames = False, 0, 0
        self.put(0xFF9031D0, 0)
        self.put(0xFF9031D4, 19200)
        self.put(0xFF9031D8, 0x01C722A0)
        self.put(0xFF9031DC, 0xFF802878)
        self.put(0xFF9031F8, 0)
        self.put(dsp_spec.MAGIC_ADDRESS, dsp_spec.MAGIC)

    def advance(self):
        if not self.active:
            return
        until = int((self.m.time_ns - self.started) * 48000 // 1_000_000_000)
        pointer = self.word(0xFF9031D8)
        for index in range(self.frames, until):
            value = sample(index) if self.word(0xFF9031DC) == dsp_spec.CAPTURE and self.word(dsp_spec.ENABLE) else 0
            self.put(pointer, value)
            pointer = 0x01C722A0 + (pointer - 0x01C722A0 + 4) % 19200
        self.frames = until
        self.put(0xFF9031D8, pointer)

    def _flush(self):
        self.advance()
        super()._flush()

    def answers(self, address):
        self.advance()
        return 0xFF9031D0 <= address < 0xFF9031FC or super().answers(address)

    def message(self, words):
        super().message(words)
        if len(words) >= 4 and words[1] == 0x37:
            self.advance()
            self.active = bool(words[2])
            self.put(0xFF9031D0, int(self.active))
            self.put(0xFF9031DC, 0xFF802878)
            if self.active:
                self.started, self.frames = self.m.time_ns, 0
                self.put(0xFF9031D8, 0x01C722A0)


def entry(name, ok, detail):
    return {'id': 'native_recording:' + name, 'ok': bool(ok), 'detail': str(detail)}


def worker_cases(payload, flash=None):
    if not has_hooks(payload):
        return []
    dev = Dev(payload, flash, adapter=True)
    if dev.synth:
        return [entry('build', False, 'the stereo worker is for the sampler builds')]
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    before_flash = user_flash(dev.m)
    code = recording_service.build(build=dev.m.profile.build, origin=CODE)
    uc = dev.m.uc
    uc.mem_write(CODE, code.bytes)
    uc.mem_write(CONTEXT, bytes(code.symbols['RC_SIZE']))
    write = lambda name, value: uc.mem_write(CONTEXT + code.symbols[name], struct.pack('<I', value))
    read = lambda name: struct.unpack('<I', bytes(uc.mem_read(CONTEXT + code.symbols[name], 4)))[0]
    write('RC_RING', RING)
    write('RC_CAPACITY', 131072)
    write('RC_CHANNELS', 2)

    def call(name, *args):
        return dev.call(code.symbols[name], CONTEXT, *args, at=COMMAND_TICK)

    started = call('recorder_command', 1) == 0 and call('recorder_pump') == 0 and read('RC_ACTIVE') == 1
    first = (struct.unpack('<I', bytes(uc.mem_read(CONTEXT + code.symbols['RC_READER'] + code.symbols['RR_CURSOR'], 4)))[0] - 0x01C722A0) // 4
    for _ in range(6):
        if call('recorder_pump') != 0:
            break
    call('recorder_command', 0)
    for _ in range(8):
        call('recorder_pump')
        if read('RC_ACTIVE') == 0:
            break
    volume = fat32.Volume(bytes(medium.data))
    try:
        content = volume.read('/Recordings/REC0001.WAV')
    finally:
        volume.close()
    with wave.open(io.BytesIO(content)) as wav:
        count = wav.getnframes()
        shape = (wav.getnchannels(), wav.getframerate(), wav.getsampwidth())
        captured = wav.readframes(count)
    out = [entry('worker_card_wav', started and read('RC_ACTIVE') == 0 and read('RC_ERROR') == 0
                 and shape == (2, 48000, 2) and count > 0 and captured == pcm(first, count)
                 and content[512:] == captured,
                 f'CommandTask worker, {count} stereo frames, status {read("RC_ERROR")}, format {shape}; native FatFs and SD driver'),
           entry('no_flash_write', before_flash == user_flash(dev.m), 'recording keeps user flash unchanged'),
           entry('no_assert', not dev.m.asserts and not dsp.faults, f'assertions {dev.m.asserts}, DSP faults {dsp.faults[:3]}')]
    return out


def runtime_cases(payload, flash=None, png=None, expect_gap=False):
    site = 0xC006B694 - 0xC0000000
    if not has_hooks(payload) or struct.unpack_from('<I', payload, site)[0] >> 24 != 0xEA:
        return []
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    before_flash = user_flash(dev.m)
    field = lambda name: dev.u32(script_hooks.NATIVE_RECORDING + recording_runtime.PUBLIC_FIELDS[name])
    out = []
    dev.m.uc.mem_write(script_hooks.MENU_STATE - 0x15, b'\x20')
    dev.m.press(0x0A, True)
    dev.run(0.03)
    dev.press(0, 0.05)
    dev.m.press(0x0A, False)
    dev.run(0.05)
    dev.press(0x0C, 0.05)
    dev.turn(1, 0.03)
    dev.turn(1, 0.03)
    out.append(entry('native_gap_record_source' if expect_gap else 'native_record_source', field('SETUP') == 1 and field('SELECTED') == 1,
                     'SHIFT+REC, source page and two dial steps select RECORD'))
    dev.press(1, 0.02)
    out.append(entry('native_gap_play_does_not_record' if expect_gap else 'play_does_not_record', field('PHASE') == 0 and field('CONTEXT') == 0 and not dsp.active,
                     f'PLAY: phase {field("PHASE")}, context {field("CONTEXT")}, capture {dsp.active}, setup {field("SETUP")}'))
    # Native PLAY leaves the setup; open it again before using its RECORD choice.
    dev.m.press(0x0A, True)
    dev.run(0.03)
    dev.press(0, 0.05)
    dev.m.press(0x0A, False)
    dev.run(0.03)
    dev.press(0, 0.01)
    started = field('PHASE') == 1 and field('CONTEXT') != 0
    capacity = field('CAPACITY')
    dev.run(0.4 if expect_gap else 0.1)
    if png:
        dev.png(png)
    dev.press(0, 0.02)
    for _ in range(64):
        if field('PHASE') == 0:
            break
        dev.run(0.01)
    volume = fat32.Volume(bytes(medium.data))
    try:
        content = volume.read('/Recordings/REC0001.WAV')
    except fat32.NotFound:
        return out + [entry('native_record_wav', False, f'WAV missing: phase {field("PHASE")}, status {field("ERROR")}, setup {field("SETUP")}, capture {dsp.active}, assertions {dev.m.asserts}')]
    finally:
        volume.close()
    with wave.open(io.BytesIO(content)) as wav:
        count, shape = wav.getnframes(), (wav.getnchannels(), wav.getframerate(), wav.getsampwidth())
        captured = wav.readframes(count)
    first = ((struct.unpack_from('<H', captured)[0] - 1234) * pow(17, -1, 65536)) & 65535
    expected_status = 20 if expect_gap else 0
    outcome = 'native_gap_is_reported' if expect_gap else 'native_record_wav'
    exact = shape == (2, 48000, 2) and count > 0 and first < 4800 and captured == pcm(first, count)
    tail = first + count <= dsp.frames if expect_gap else first + count == dsp.frames
    out += [entry(outcome, started and field('PHASE') == 0 and field('ERROR') == expected_status
                  and field('CONTEXT') == 0 and field('BYTES') == count * 4
                  and exact and tail and content[512:] == captured,
                  f'permanent CommandTask hook, {count} frames from {first}, ring {capacity} bytes; status {field("ERROR")}, expected {expected_status}; PCM exact {exact}'),
            entry('native_gap_no_flash_write' if expect_gap else 'native_no_flash_write', before_flash == user_flash(dev.m), 'native RECORD leaves user flash unchanged'),
            entry('native_gap_no_assert' if expect_gap else 'native_no_assert', not dev.m.asserts and not dsp.faults,
                  f'assertions {dev.m.asserts}, DSP faults {dsp.faults[:3]}')]
    dev.press('exit', 0.03)
    out.append(entry('native_gap_setup_closed' if expect_gap else 'native_setup_closed', field('SETUP') == 0, 'EXIT ends the setup lifetime without retaining its view'))
    return out


def cases(payload, flash=None):
    return worker_cases(payload, flash) + runtime_cases(payload, flash) + runtime_cases(payload, flash, expect_gap=True)


def cases_task():
    import parallel
    return cases(parallel.shared['payload'], parallel.shared['flash'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vsb', type=Path, required=True)
    ap.add_argument('--runtime-only', action='store_true')
    ap.add_argument('--expect-gap', action='store_true')
    ap.add_argument('--png', type=Path)
    args = ap.parse_args()
    payload = args.vsb.read_bytes()[0x100:]
    result = runtime_cases(payload, png=args.png, expect_gap=args.expect_gap) if args.runtime_only else cases(payload)
    print(json.dumps(result, indent=1))
    return 0 if result and all(e['ok'] for e in result) else 1


if __name__ == '__main__':
    sys.exit(main())
