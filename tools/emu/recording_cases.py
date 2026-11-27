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
from tools.patch import recording_dsp as dsp_spec, recording_service, recording_runtime, recording_writer, script_hooks

CODE, CONTEXT, RING = 0xC3F00000, 0xC3F10000, 0xC3F20000
COMMAND_TICK = 0xC002A628
DOT_VRAM, DOT_COL = 0xC031B310, 78
DOT = bytes((0x38, 0x7C, 0x7C, 0x7C, 0x38))
OS_TICKS = 0xC06A292C
HW_TRANSPORT, HW_TRANSPORT_SYNTH = 0xC06BC318, 0xC0583C98   # the sequencer's state word (script_hooks.s:nr_transport_frame)
NR_PLAY_BOUND = 73                  # recording_runtime.s: 1 a take PLAY started waits for the transport, 2 it runs with it
REC_LED = 0x12


def has_hooks(payload):
    from tools.patch.synthaddr import is_synth
    config = dsp_spec.configuration('synth' if is_synth(payload) else 'hacktribe')
    offset = config['final'] + 16 - 0xC0000000 + dsp_spec.MAGIC_ADDRESS - dsp_spec.CODE
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
        self.state = 0xFF9031C8 if self.synth else 0xFF9031D0
        self.ring = 0x01371EC0 if self.synth else 0x01C722A0
        self.input = 0xFF802810 if self.synth else 0xFF802878
        self.active, self.started, self.frames = False, 0, 0
        # The real DSP takes 0x37 in its own time: ack_delay (seconds) holds it back, drop_next loses the next one.
        self.ack_delay, self.drop_next, self.pending = 0.0, False, None
        self.put(self.state, 0)
        self.put(self.state + 4, 19200)
        self.put(self.state + 8, self.ring)
        self.put(self.state + 12, self.input)
        if not self.synth:
            self.put(self.state + 40, 0)
        self.put(dsp_spec.MAGIC_ADDRESS, dsp_spec.MAGIC)
        # The taps see only what the DSP itself wrote: a tap gated on the word the ARM writes at STATE+12 reads the
        # stale cached line forever (recording_dsp.host_word_loads), so the loaded program decides, not the ARM.
        config = dsp_spec.configuration('synth' if self.synth else 'hacktribe')
        code = bytes(machine.uc.mem_read(config['final'] + 16, dsp_spec.PROGRAM_SIZE))
        self.tap_live = not dsp_spec.host_word_loads(code)

    def advance(self):
        if self.pending and self.m.time_ns >= self.pending[0]:
            words, self.pending = self.pending[1], None
            self.command(words)
        if not self.active:
            return
        until = int((self.m.time_ns - self.started) * 48000 // 1_000_000_000)
        pointer = self.word(self.state + 8)
        for index in range(self.frames, until):
            value = sample(index) if self.word(self.state + 12) == dsp_spec.CAPTURE and self.tap_live else 0
            self.put(pointer, value)
            pointer = self.ring + (pointer - self.ring + 4) % 19200
        self.frames = until
        self.put(self.state + 8, pointer)

    def _flush(self):
        self.advance()
        super()._flush()

    def answers(self, address):
        self.advance()
        return self.state <= address < self.state + (16 if self.synth else 44) or super().answers(address)

    def message(self, words):
        super().message(words)
        if len(words) >= 4 and words[1] == 0x37:
            if self.drop_next:
                self.drop_next = False
            elif self.ack_delay:
                self.pending = (self.m.time_ns + int(self.ack_delay * 1e9), list(words))
            else:
                self.command(words)

    def command(self, words):
        self.advance()
        self.active = bool(words[2])
        self.put(self.state, int(self.active))
        self.put(self.state + 12, self.input)
        if self.active:
            self.started, self.frames = self.m.time_ns, 0
            self.put(self.state + 8, self.ring)


def entry(name, ok, detail):
    return {'id': 'native_recording:' + name, 'ok': bool(ok), 'detail': str(detail)}


def feature_cases(payload, flash=None):
    if not has_hooks(payload):
        return []
    import menu_cases as mc
    dev = mc.boot(payload, flash, files=mc.CARD_FOLDER, adapter=True)
    from tools.patch.script_hooks import NATIVE_RECORDING
    setting = NATIVE_RECORDING + 72   # script_menu.s:NR_SETTING, 1 is ON
    flags = dev.read(mc.MX_FLAGS2, 1)[0]
    start = dev.read(setting, 1)[0]
    index = mc.feature_count() - 1
    mc.goto_group(dev, mc.GROUP_FEATURES, index)
    off = mc.texts_of(dev)
    dev.turn(1, wait=0.1)
    enabled = mc.texts_of(dev), dev.read(setting, 1)[0], dev.read(mc.MX_FLAGS2, 1)[0]
    dev.turn(-1, wait=0.1)
    disabled = mc.texts_of(dev), dev.read(setting, 1)[0], dev.read(mc.MX_FLAGS2, 1)[0]
    return [entry('feature_default_off_and_last', start != 1 and off == ('NATIVE RECORDING', 'OFF', '')
                  and mc.counter(dev) == (index, index + 1), f'page {index}, setting {start}, text {off}'),
            entry('feature_toggle_preserves_other_flags', enabled == (('NATIVE RECORDING', 'ON', ''), 1, flags)
                  and disabled == (off, 0, flags) and not dev.m.asserts, f'on {enabled}, off {disabled}, assertions {dev.m.asserts}')]


def blue_worker_cases(payload, flash=None):
    """Own mono controller with the original synth host port and FatFs in CommandTask."""
    if not has_hooks(payload):
        return []
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    before_flash = user_flash(dev.m)
    code = recording_service.build(build='synth', origin=CODE)
    uc = dev.m.uc
    uc.mem_write(CODE, code.bytes)
    uc.mem_write(CONTEXT, bytes(code.symbols['RC_SIZE']))
    for name, value in (('RC_RING', RING), ('RC_CAPACITY', 131072), ('RC_CHANNELS', 1)):
        uc.mem_write(CONTEXT + code.symbols[name], struct.pack('<I', value))
    read = lambda name: dev.u32(CONTEXT + code.symbols[name])
    call = lambda name, *args: dev.call(code.symbols[name], CONTEXT, *args, at=COMMAND_TICK)
    call('recorder_command', 1)
    started = call('recorder_pump') == 0 and read('RC_ACTIVE') == 1
    first = (dev.u32(CONTEXT + code.symbols['RC_READER'] + code.symbols['RR_CURSOR']) - dsp.ring) // 4
    for _ in range(4):
        dev.run(0.02)
        call('recorder_pump')
    call('recorder_command', 0)
    for _ in range(32):
        call('recorder_pump')
        if read('RC_ACTIVE') == 0:
            break
    volume = fat32.Volume(bytes(medium.data))
    try:
        content = volume.read('/Recordings/REC0001.WAV')
    finally:
        volume.close()
    with wave.open(io.BytesIO(content)) as wav:
        shape = wav.getnchannels(), wav.getframerate(), wav.getsampwidth()
        count = wav.getnframes()
        captured = wav.readframes(count)
    expected = b''.join(struct.pack('<H', sample(i) >> 16) for i in range(first, first + count))
    return [entry('blue_mono_wav', started and shape == (1, 48000, 2) and count > 0
                  and captured == expected and first + count == dsp.frames and len(content) == 512 + count * 2,
                  f'started {started}, shape {shape}, {count} frames from {first}, DSP frames {dsp.frames}, exact {captured == expected}'),
            entry('blue_mono_releases_ownership', read('RC_ERROR') == read('RC_ACTIVE') == read('RW_STATE') == 0
                  and not dsp.active and not dev.m.asserts and not dsp.faults,
                  f'error {read("RC_ERROR")}, phase {read("RC_ACTIVE")}, file {read("RW_STATE")}, capture {dsp.active}, assertions {dev.m.asserts}'),
            entry('blue_mono_no_flash_write', before_flash == user_flash(dev.m), 'only the private recording file is written')]


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



def wav_marker(content):
    chunks, cursor = {}, 12
    while cursor + 8 <= len(content):
        name, size = struct.unpack_from('<4sI', content, cursor)
        if cursor + 8 + size > len(content):
            raise ValueError('RIFF chunk exceeds the file')
        chunks[name] = content[cursor + 8:cursor + 8 + size]
        cursor += 8 + size + (size & 1)
    cue, associated = chunks.get(b'cue '), chunks.get(b'LIST')
    if cue is None or associated is None:
        return None
    count, ident, position, chunk, start, block, offset = struct.unpack('<III4sIII', cue)
    label, size, label_id = struct.unpack_from('<4sII', associated, 4)
    if count != 1 or chunk != b'data' or start or block or position != offset or associated[:4] != b'adtl' or label != b'labl' or ident != label_id:
        raise ValueError('invalid WAV cue or associated label')
    return offset, associated[16:12 + size].split(b'\0', 1)[0]


def runtime_cases(payload, flash=None, png=None, card_stall=False, defer_settings=False, remove_card=False, transport_play=False,
                  slow_card=False):
    """slow_card: every 512-byte block takes 1.5 ms to program, so one 64-KiB block holds the card 192 ms, about twice
    the DSP ring; the take must still be complete. card_stall: a single block stalls 400 ms, four times the DSP ring and
    longer than the 250 ms an SD card may stay busy on a write. The UiTask frame reads the ring while CommandTask waits on the
    card, so the take must still be complete (before it ended with a gap: REC on the red, 24.11.2026, status 20 after 1.1 s)."""
    from tools.patch import synthaddr
    synth = synthaddr.is_synth(payload)
    channels = 1 if synth else 2
    site = (0xC0027898 if synth else 0xC006B694) - 0xC0000000
    if not has_hooks(payload) or struct.unpack_from('<I', payload, site)[0] >> 24 != 0xEA:
        return []
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dev.m.mmc.clock = lambda: dev.m.time_ns
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    before_flash = user_flash(dev.m)
    field = lambda name: dev.u32(script_hooks.NATIVE_RECORDING + recording_runtime.PUBLIC_FIELDS[name])
    out = []
    dev.m.uc.mem_write(script_hooks.NATIVE_RECORDING + 72, b'\x01')   # script_menu.s:NR_SETTING, NATIVE RECORDING ON
    dev.m.press(0x0A, True)
    dev.run(0.03)
    dev.press(0, 0.05)
    dev.m.press(0x0A, False)
    dev.run(0.05)
    if not synth:
        dev.press(0x0C, 0.05)
        dev.turn(1, 0.03)
        dev.turn(1, 0.03)
    out.append(entry('native_stall_record_source' if card_stall else 'native_record_source', field('SETUP') == 1 and field('SELECTED') == 1,
                     'SHIFT+REC opens RECORD directly on the synth; the sampler selects its third source'))
    transport = lambda: dev.u32(HW_TRANSPORT_SYNTH if synth else HW_TRANSPORT)
    bound = lambda: dev.m.uc.mem_read(script_hooks.NATIVE_RECORDING + NR_PLAY_BOUND, 1)[0]
    prefix = 'native_stall_' if card_stall else ''

    def tap(key, hold=0.05, wait=0.01):
        dev.m.press(key, True)
        dev.run(hold)
        dev.m.press(key, False)
        dev.run(wait)

    def open_view(hold=0.05):
        dev.m.press(0x0A, True)
        dev.run(0.03 if hold > 0.02 else 0.01)
        tap(0, hold)
        dev.m.press(0x0A, False)
        dev.run(0.03 if hold > 0.02 else 0.01)

    def stop():                             # the sequencer's STOP ends a take PLAY started
        dev.press(1, 0.02)
        for _ in range(64):
            if field('PHASE') == 0:
                break
            dev.run(0.01)

    dev.press(1, 0.02)                      # key 1 is STOP (key 2 is PLAY)
    out.append(entry(prefix + 'stop_in_view_does_not_record', field('PHASE') == 0 and field('CONTEXT') == 0 and not dsp.active,
                     f'STOP: phase {field("PHASE")}, context {field("CONTEXT")}, capture {dsp.active}, setup {field("SETUP")}'))
    open_view()
    dev.press(0, 0.05)
    out.append(entry(prefix + 'rec_in_view_starts_nothing', field('PHASE') == 0 and field('CONTEXT') == 0 and not dsp.active
                     and field('SETUP') == 0 and transport() == 0,
                     f'REC closes the view as the firmware does: phase {field("PHASE")}, capture {dsp.active}, setup {field("SETUP")}, transport {transport()}'))
    open_view()
    dev.press(2, 0.01)                      # PLAY
    started = field('PHASE') == 1 and field('CONTEXT') != 0
    capacity = field('CAPACITY')
    playing, leds, sampling = set(), set(), set()
    for _ in range(5):
        playing.add(transport())
        leds.add(dev.m.leds[REC_LED])
        dev.run(0.01)
    out.append(entry(prefix + 'play_starts_take_and_pattern', started and playing == {1} and field('SETUP') == 0 and bound() == 2,
                     f'PLAY in RECORD: phase {field("PHASE")}, context {field("CONTEXT")}, transport {sorted(playing)}, setup {field("SETUP")}, bound {bound()}'))
    if not synth:
        out.append(entry(prefix + 'play_starts_no_korg_sampling', 11 not in playing and dev.screen()['window'] == 0,
                         f'transport {sorted(playing)} (11 is the firmware sampling), window {dev.screen()["window"]:#x}'))
    out.append(entry(prefix + 'take_leaves_rec_led_dark', leds == {0}, f'REC LED during the take: {sorted(leds)}'))
    if remove_card:
        dev.run(0.03)
        dev.m.eject_card()
        stop()
        if png:
            dev.png(png)
        volume = fat32.Volume(bytes(medium.data))
        try:
            content = volume.read('/Recordings/REC0001.WAV')
        finally:
            volume.close()
        with wave.open(io.BytesIO(content)) as wav:
            valid = wav.getnframes() * 4 <= len(content) - 512
        out = [entry('removed_card_releases_capture_and_heap', started and field('PHASE') == 0
                      and field('CONTEXT') == 0 and not dsp.active and field('ERROR') == 1 and not dev.m.asserts,
                      f'phase {field("PHASE")}, context {field("CONTEXT")}, capture {dsp.active}, error {field("ERROR")}, selected {field("SELECTED")}, setup {field("SETUP")}, assertions {dev.m.asserts}'),
                entry('removed_card_keeps_durable_prefix', valid and before_flash == user_flash(dev.m),
                      f'durable bytes {len(content)}, valid {valid}, user flash unchanged {before_flash == user_flash(dev.m)}')]
        if not out[0]['ok']:
            return out
        replacement = MemoryMedium(card_image())
        dev.m.insert_card(SDCard(replacement))
        dev.run(0.3)
        open_view()
        dev.press(2, 0.01)
        for _ in range(5):                  # the take may start one UI frame after the press
            restarted = field('PHASE') == 1 and field('CONTEXT') != 0
            if restarted:
                break
            dev.run(0.01)
        dev.run(0.03)
        stop()
        volume = fat32.Volume(bytes(replacement.data))
        try:
            following = volume.read('/Recordings/REC0002.WAV')
        except fat32.NotFound:
            return out + [entry('replacement_card_records_again', False,
                                f'file missing: started {restarted}, phase {field("PHASE")}, error {field("ERROR")}')]
        finally:
            volume.close()
        with wave.open(io.BytesIO(following)) as wav:
            count = wav.getnframes()
            captured = wav.readframes(count)
        out.append(entry('replacement_card_records_again', restarted and field('PHASE') == field('CONTEXT') == field('ERROR') == 0
                         and count > 0 and captured == pcm(0, count) and not dsp.active and not dev.m.asserts,
                         f'started {restarted}, phase {field("PHASE")}, error {field("ERROR")}, {count} frames, exact {captured == pcm(0, count)}, assertions {dev.m.asserts}'))
        return out
    stalls = []
    if defer_settings:
        from splash_cases import SWITCH_SCREEN
        import menu_cases as mc
        dev.m.uc.mem_write(script_hooks.MENU_STATE + mc.S_LEVEL, struct.pack('<II', 2, mc.GROUP_FEATURES))
        dev.m.uc.mem_write(script_hooks.MENU_STATE + mc.S_ENTER, bytes(4))
        dev.call(SWITCH_SCREEN, 45, 0)
        dev.run(0.01)
        dev.press(0x0E, 0.01)
        untouched = not mc.settings_raw(medium.data)
        out.append(entry('settings_wait_for_recording', field('DEFERRED') == 1 and untouched and field('PHASE') == 1,
                         f'WRITE: pending {field("DEFERRED")}, no settings file {untouched}, phase {field("PHASE")}, screen {dev.screen()}, texts {mc.texts_of(dev)}'))
        dev.press('exit', 0.01)
    elif transport_play:
        context = field('CONTEXT')
        tap(2, 0.015)                       # PLAY again pauses the pattern; short presses keep the take inside the capture model
        paused = transport()
        tap(0, 0.015)                       # REC stays the firmware's pattern recording
        armed = transport()
        out.append(entry('pause_and_rec_keep_take', field('PHASE') == 1 and dsp.active and paused not in (0, 11) and armed not in (0, 11),
                         f'PLAY and REC during the take: phase {field("PHASE")}, capture {dsp.active}, transport {paused} then {armed}'))
        open_view(0.015)
        for _ in range(20 if synth else 0): # the blue view says it is open one UI frame later, slower while the pattern plays
            if field('SETUP') == 1:
                break
            dev.run(0.01)
        tap(2, 0.015, 0.03 if synth else 0.01)   # the blue view leaves in the next UI frame
        out.append(entry('no_second_take_while_busy', field('PHASE') == 1 and field('CONTEXT') == context and transport() not in (0, 11)
                         and field('SETUP') == 0 and not dev.m.asserts,
                         f'PLAY in RECORD during a take: phase {field("PHASE")}, same context {field("CONTEXT") == context}, transport {transport()}, setup {field("SETUP")}'))
    elif slow_card:
        dev.m.mmc.write_busy = lambda: 1_500_000
        dev.run(1.2)
        dev.m.mmc.write_busy = None
    elif card_stall:
        armed = dev.m.time_ns + 200_000_000
        def stall():
            if dev.m.time_ns < armed or stalls:
                return 0
            stalls.append(dev.m.time_ns)
            return 400_000_000
        dev.m.mmc.write_busy = stall
        dev.run(0.6)
        dev.m.mmc.write_busy = None
    else:
        dev.run(0.1)
    stop()
    out.append(entry(prefix + 'stop_ends_take', started and field('PHASE') == 0 and bound() == 0 and transport() == 0,
                     f'STOP: phase {field("PHASE")}, bound {bound()}, transport {transport()}, error {field("ERROR")}'))
    if synth:
        open_view()                         # the view shows how the take ended
        dev.run(0.12)
        import menu_cases as mc
        shown = mc.texts_of(dev)
        out.append(entry('blue_finished_view', shown[0].startswith('Saved ') and shown[1] == 'REC0001',
                         f'phase {field("PHASE")}, texts {shown}'))
    if png:
        dev.run(0.04)
        dev.png(png)
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
    expected_status = 0
    outcome = 'native_stall_take_complete' if card_stall else 'native_record_wav'
    expected_pcm = (b''.join(struct.pack('<H', sample(i) >> 16) for i in range(first, first + count))
                    if synth else pcm(first, count))
    exact = shape == (channels, 48000, 2) and count > 0 and first < 4800 and captured == expected_pcm
    tail = first + count == dsp.frames
    out += [entry(outcome, started and field('PHASE') == 0 and field('ERROR') == expected_status
                  and field('CONTEXT') == 0 and field('BYTES') == count * channels * 2
                  and exact and tail and content[512:] == captured,
                  f'permanent CommandTask hook, {count} frames from {first}, ring {capacity} bytes; status {field("ERROR")}, expected {expected_status}; PCM exact {exact}'),
            # REC0005 on the red (2026-11-24) was a valid WAV of zeros: the loaded taps gated on a word the DSP never sees.
            entry('native_stall_take_has_audio' if card_stall else 'native_take_has_audio',
                  dsp.tap_live and count > 0 and any(captured),
                  f'taps independent of host-written words {dsp.tap_live}, {count} frames, non-zero bytes {sum(1 for b in captured if b)}'),
            entry('native_stall_no_flash_write' if card_stall else 'native_no_flash_write', before_flash == user_flash(dev.m), 'native RECORD leaves user flash unchanged'),
            entry('native_stall_no_assert' if card_stall else 'native_no_assert', not dev.m.asserts and not dsp.faults,
                  f'assertions {dev.m.asserts}, DSP faults {dsp.faults[:3]}')]
    out.append(entry('native_stall_take_has_no_gap' if card_stall else 'native_clean_take_has_no_gap',
                     field('GAPS') == 0 and wav_marker(content) is None and len(stalls) == card_stall,
                     f'no gap counter or marker on a complete take, card stalls {len(stalls)}'))
    dev.press('exit', 0.03)
    out.append(entry('native_stall_setup_closed' if card_stall else 'native_setup_closed', field('SETUP') == 0, 'EXIT ends the setup lifetime without retaining its view'))
    if defer_settings:
        dev.run(0.2)
        records = mc.settings_raw(medium.data)
        saved = [r for r in records.values() if len(r) >= 24 and r[:4] == b'GSET']
        # after the take the flash, the settings' main store, may follow the card file (script_menu.s menu_settings_save_card)
        out.append(entry('settings_saved_after_release', field('DEFERRED') == 0 and len(saved) == 1 and saved[0][4] & 0x1F == 6 and saved[0][6] & 0x80,
                         f'pending {field("DEFERRED")}, SD copies {len(saved)}, user flash written after the take {before_flash != user_flash(dev.m)}'))
        for result in out:
            result['id'] = result['id'].replace('native_recording:', 'native_recording:deferred_')
    if transport_play:
        for result in out:
            result['id'] = result['id'].replace('native_recording:', 'native_recording:transport_')
    if slow_card:
        for result in out:
            result['id'] = result['id'].replace('native_recording:', 'native_recording:slow_card_')
    return out


def fault_cases(payload, flash=None):
    """A DSP slow to take 0x37 still records; failed starts leave their fault in plain READ reach and no empty WAV."""
    from tools.patch import synthaddr
    synth = synthaddr.is_synth(payload)
    site = (0xC0027898 if synth else 0xC006B694) - 0xC0000000
    if not has_hooks(payload) or struct.unpack_from('<I', payload, site)[0] >> 24 != 0xEA:
        return []
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    base = script_hooks.NATIVE_RECORDING
    field = lambda name: dev.u32(base + recording_runtime.PUBLIC_FIELDS[name])
    fault = lambda name: [dev.u32(base + recording_runtime.PUBLIC_FIELDS[name] + 4 * n) for n in range(8)]
    dev.m.uc.mem_write(base + 72, b'\x01')   # script_menu.s:NR_SETTING, NATIVE RECORDING ON

    def take(during=0.05, spoil=False):
        dev.m.press(0x0A, True)
        dev.run(0.03)
        dev.press(0, 0.05)
        dev.m.press(0x0A, False)
        dev.run(0.05)
        if not synth and field('SELECTED') != 1:
            dev.press(0x0C, 0.05)
            dev.turn(1, 0.03)
            dev.turn(1, 0.03)
        for _ in range(20):
            if field('SETUP') == 1:
                break
            dev.run(0.01)
        dev.press(2, 0.01)
        dev.run(during)
        if spoil:                           # the source pointer goes back to the input mid-take, as a foreign 0x37 would do
            dsp.put(dsp.state + 12, dsp.input)
            dev.run(0.03)
        dev.press(1, 0.02)
        for _ in range(64):
            if field('PHASE') == 0 and field('CONTEXT') == 0:
                break
            dev.run(0.01)

    def files():
        volume = fat32.Volume(bytes(medium.data))
        found = {}
        try:
            for name in (f'REC{i:04d}.WAV' for i in range(1, 5)):
                try:
                    found[name] = len(volume.read('/Recordings/' + name))
                except fat32.NotFound:
                    pass
        finally:
            volume.close()
        return found

    out = []
    dsp.ack_delay = 0.004
    take()
    ack = field('ACK')
    out.append(entry('slow_dsp_ack_still_records', field('ERROR') == 0 and field('BYTES') > 0 and 0 < ack < 40 and 0 < field('STOP_ACK') < 40
                     and field('FAULTS') == 0,
                     f'DSP takes 0x37 after 4 ms: error {field("ERROR")}, bytes {field("BYTES")}, ack {ack} and {field("STOP_ACK")} ticks, faults {field("FAULTS")}'))
    dsp.ack_delay, dsp.drop_next = 0.0, True
    take()
    first = fault('FIRST')
    out.append(entry('failed_start_reports_fault', field('ERROR') == 21 and field('BYTES') == 0 and field('ACK') == 0xFFFFFFFF
                     and field('FAULTS') == 1 and first[0] == 0x11 and first[1] == 0 and fault('LAST') == first and first[6] < 200,
                     f'lost 0x37: error {field("ERROR")}, ack {field("ACK"):#x}, faults {field("FAULTS")}, first {[hex(v) for v in first]}'))
    names = files()
    if synth:                               # the synth's FatFs has no f_unlink: the empty take stays and counts
        out.append(entry('failed_start_keeps_count_without_unlink', set(names) == {'REC0001.WAV', 'REC0002.WAV'} and field('NUMBER') == 2,
                         f'files {names}, number {field("NUMBER")}'))
    else:
        out.append(entry('failed_start_leaves_no_wav', set(names) == {'REC0001.WAV'} and field('NUMBER') == 1,
                         f'files {names}, number {field("NUMBER")}'))
    take(spoil=True)
    last = fault('LAST')
    out.append(entry('lost_source_mid_take_reports_fault', field('ERROR') == 21 and field('FAULTS') == 2 and last[0] in (0x23, 0x33)
                     and last[4] == dsp.input and fault('FIRST') == first and field('BYTES') > 0,
                     f'error {field("ERROR")}, faults {field("FAULTS")}, last {[hex(v) for v in last]}, first kept {fault("FIRST") == first}'))
    names = files()
    kept = 'REC0003.WAV' if synth else 'REC0002.WAV'
    out.append(entry('take_with_samples_keeps_wav', kept in names and names[kept] > 512 and not dev.m.asserts,
                     f'files {names}, assertions {dev.m.asserts}'))
    return out


def checkpoint_cases(payload, flash=None, fail_sync=False):
    """Discard CPU/FatFs state at each checkpoint boundary and inspect only the SD image."""
    if not has_hooks(payload):
        return []
    from unicorn import UC_HOOK_CODE
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dev.run(0.8)
    code = recording_writer.build(build=dev.m.profile.build, origin=CODE)
    dev.m.uc.mem_write(CODE, code.bytes)
    dev.m.uc.mem_write(CONTEXT, bytes(code.symbols['RW_SIZE']))
    expected = bytes(range(256)) * 64 + b'\x01\x23\x45\x67' * 16
    dev.m.uc.mem_write(RING, expected)
    call = lambda name, *args: dev.call(code.symbols['rec_writer_' + name], CONTEXT, *args, at=COMMAND_TICK)

    def snapshot():
        volume = fat32.Volume(bytes(medium.data))
        try:
            content = volume.read('/Recordings/REC0001.WAV')
        finally:
            volume.close()
        with wave.open(io.BytesIO(content)) as wav:
            count = wav.getnframes()
            exact = wav.readframes(count) == expected[:count * 4]
        return dict(bytes=len(content), frames=count,
                    valid=exact and count * 4 <= len(content) - 512
                    and struct.unpack_from('<I', content, 4)[0] <= len(content) - 8)

    opened = call('open', 2)
    if opened:
        return [entry('checkpoint_open', False, f'open status {opened}')]
    empty = snapshot()
    cuts = []
    def cut(uc, address, size, data):
        cuts.append(snapshot())
    for name in ('rec_checkpoint_data_synced', 'rec_checkpoint_header_written',
                 'rec_checkpoint_position_restored', 'rec_checkpoint_done'):
        address = code.symbols[name]
        dev.m.uc.hook_add(UC_HOOK_CODE, cut, begin=address, end=address)
    if fail_sync:
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR
        failed = []
        def fail(uc, address, size, data):
            if not failed:
                failed.append(address)
                uc.reg_write(UC_ARM_REG_R0, 1)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        address = code.symbols['REC_FS_SYNC']
        dev.m.uc.hook_add(UC_HOOK_CODE, fail, begin=address, end=address)
    first = call('append', RING, 16384)
    checkpoint = call('checkpoint')
    if fail_sync:
        finished = call('finish')
        saved = snapshot()
        return [entry('checkpoint_fault_keeps_first_error', first == 0 and checkpoint == finished == code.symbols['RW_IO'],
                      f'append {first}, checkpoint {checkpoint}, finish {finished}'),
                entry('checkpoint_fault_power_cut_prefixes', len(cuts) >= 6 and all(s['valid'] for s in cuts)
                      and saved == dict(bytes=16896, frames=4096, valid=True) and not dev.m.asserts,
                      f'cuts {cuts}, saved {saved}, assertions {dev.m.asserts}')]
    second = call('append', RING + 16384, 64)
    checkpoint2 = call('checkpoint')
    saved = snapshot()
    finished = call('finish')
    return [entry('checkpoint_empty_is_durable', empty == dict(bytes=512, frames=0, valid=True), empty),
            entry('checkpoint_power_cut_prefixes', len(cuts) >= 8 and all(s['valid'] for s in cuts), cuts),
            entry('checkpoint_append_position_and_lengths', first == checkpoint == second == checkpoint2 == finished == 0
                  and saved == dict(bytes=512 + len(expected), frames=len(expected) // 4, valid=True)
                  and not dev.m.asserts,
                  f'saved {saved}, statuses {[first, checkpoint, second, checkpoint2, finished]}, assertions {dev.m.asserts}')]


def full_card_cases(payload, flash=None):
    if not has_hooks(payload):
        return []
    image = card_image()
    volume = fat32.Volume(image)
    for name in ('Plugin', 'Presets', 'Gif', 'Doom', 'Sample', 'System'):
        volume.mkdir('/KORG/blechtribe/' + name)
    volume.mkdir('/Recordings')
    volume.write('/FILLER.BIN', bytes((volume.free - 8) * volume.csz))
    volume.close()
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(image)
    dev.m.insert_card(SDCard(medium))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    before_flash = user_flash(dev.m)
    code = recording_service.build(build=dev.m.profile.build, origin=CODE)
    uc = dev.m.uc
    uc.mem_write(CODE, code.bytes)
    uc.mem_write(CONTEXT, bytes(code.symbols['RC_SIZE']))
    for name, value in (('RC_RING', RING), ('RC_CAPACITY', 131072), ('RC_CHANNELS', 2)):
        uc.mem_write(CONTEXT + code.symbols[name], struct.pack('<I', value))
    read = lambda name: dev.u32(CONTEXT + code.symbols[name])
    call = lambda name, *args: dev.call(code.symbols[name], CONTEXT, *args, at=COMMAND_TICK)
    call('recorder_command', 1)
    started = call('recorder_pump') == 0 and read('RC_ACTIVE') == 1
    first = (dev.u32(CONTEXT + code.symbols['RC_READER'] + code.symbols['RR_CURSOR']) - 0x01C722A0) // 4
    result = 0
    for _ in range(80):
        dev.run(0.02)
        result = call('recorder_pump')
        if result:
            break
    volume = fat32.Volume(bytes(medium.data))
    try:
        content = volume.read('/Recordings/REC0001.WAV')
    finally:
        volume.close()
    with wave.open(io.BytesIO(content)) as wav:
        count = wav.getnframes()
        captured = wav.readframes(count)
    return [entry('full_card_stops_and_releases', started and result == code.symbols['RW_FULL']
                  and read('RC_ERROR') == code.symbols['RW_FULL'] and read('RC_ACTIVE') == read('RW_STATE') == 0
                  and not dsp.active and not dev.m.asserts,
                  f'started {started}, result {result}, state {read("RC_ACTIVE")}/{read("RW_STATE")}, capture {dsp.active}, assertions {dev.m.asserts}'),
            entry('full_card_keeps_exact_prefix', count > 0 and captured == pcm(first, count)
                  and len(content) == 512 + count * 4 and before_flash == user_flash(dev.m),
                  f'{count} exact frames from {first}, file bytes {len(content)}, user flash unchanged {before_flash == user_flash(dev.m)}')]


def rollover_cases(payload, flash=None):
    """Use an 8-KiB segment limit with native FatFs; the unit case exercises 32-bit arithmetic."""
    if not has_hooks(payload):
        return []
    from tools.patch.arm import assemble
    dev = Dev(payload, flash, adapter=True)
    medium = MemoryMedium(card_image())
    dev.m.insert_card(SDCard(medium))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    before_flash = user_flash(dev.m)
    source = recording_service.source(dev.m.profile.build).replace('.equ RW_MAX_DATA, 0xFFFFFDFC', '.equ RW_MAX_DATA, 8192')
    code = assemble(source, origin=CODE)
    uc = dev.m.uc
    uc.mem_write(CODE, code.bytes)
    uc.mem_write(CONTEXT, bytes(code.symbols['RC_SIZE']))
    for name, value in (('RC_RING', RING), ('RC_CAPACITY', 131072), ('RC_CHANNELS', 2)):
        uc.mem_write(CONTEXT + code.symbols[name], struct.pack('<I', value))
    read = lambda name: dev.u32(CONTEXT + code.symbols[name])
    call = lambda name, *args: dev.call(code.symbols[name], CONTEXT, *args, at=COMMAND_TICK)
    call('recorder_command', 1)
    started = call('recorder_pump') == 0 and read('RC_ACTIVE') == 1
    first = (dev.u32(CONTEXT + code.symbols['RC_READER'] + code.symbols['RR_CURSOR']) - 0x01C722A0) // 4
    dev.run(0.05)
    call('recorder_command', 0)
    for _ in range(80):
        call('recorder_pump')
        if read('RC_ACTIVE') == 0:
            break
    volume = fat32.Volume(bytes(medium.data))
    try:
        paths = sorted(path for path, item in volume.walk() if path.startswith('/Recordings/REC') and not item.is_dir)
        files = [volume.read(path) for path in paths]
    finally:
        volume.close()
    captured, sizes = b'', []
    for content in files:
        with wave.open(io.BytesIO(content)) as wav:
            data = wav.readframes(wav.getnframes())
        sizes.append(len(data))
        captured += data
    return [entry('rollover_native_files_are_contiguous', started and len(files) >= 2
                  and all(0 < n <= 8192 for n in sizes) and all(n == 8192 for n in sizes[:-1])
                  and captured == pcm(first, len(captured) // 4) and all(len(f) == n + 512 for f, n in zip(files, sizes)),
                  f'paths {paths}, PCM sizes {sizes}, exact {captured == pcm(first, len(captured) // 4)}'),
            entry('rollover_native_releases_resources', read('RC_ERROR') == read('RC_ACTIVE') == read('RW_STATE') == 0
                  and read('RC_DROPPED') == 0 and not dsp.active and not dev.m.asserts and before_flash == user_flash(dev.m),
                  f'error {read("RC_ERROR")}, phase {read("RC_ACTIVE")}, file {read("RW_STATE")}, dropped {read("RC_DROPPED")}, capture {dsp.active}, assertions {dev.m.asserts}')]


def status_dot_cases(payload, flash=None, png=None):
    """The blinking dot on the main screen's top row while a recording runs outside the RECORD view."""
    from tools.patch import synthaddr
    synth = synthaddr.is_synth(payload)
    site = (0xC0027898 if synth else 0xC006B694) - 0xC0000000
    if not has_hooks(payload) or struct.unpack_from('<I', payload, site)[0] >> 24 != 0xEA:
        return []
    dev = Dev(payload, flash, adapter=True)
    dev.m.insert_card(SDCard(MemoryMedium(card_image())))
    dsp = CaptureModel.attach(dev.m)
    dev.run(0.8)
    field = lambda name: dev.u32(script_hooks.NATIVE_RECORDING + recording_runtime.PUBLIC_FIELDS[name])
    columns = lambda: bytes(b & 0xFE for b in dev.m.uc.mem_read(DOT_VRAM + DOT_COL, 5))

    def open_record():
        dev.m.press(0x0A, True)
        dev.run(0.03)
        dev.press(0, 0.05)
        dev.m.press(0x0A, False)
        dev.run(0.05)

    dev.m.uc.mem_write(script_hooks.NATIVE_RECORDING + 72, b'\x01')   # script_menu.s:NR_SETTING, NATIVE RECORDING ON
    before = columns()
    open_record()
    if not synth:
        dev.press(0x0C, 0.05)
        dev.turn(1, 0.03)
        dev.turn(1, 0.03)
    ticks = lambda: dev.u32(OS_TICKS)
    for _ in range(200):                    # start so that the blink turns within the window the capture model holds
        if 200 <= ticks() & 511 < 260:
            break
        dev.run(0.005)
    dev.press(2, 0.02)                      # PLAY starts the take and closes the view
    seen, wrong, frames = set(), 0, 0
    for _ in range(35):
        dev.run(0.01)
        if field('PHASE') != 1:
            break
        frames += 1
        state = columns()
        if state != (bytes(5) if ticks() & 512 else DOT):
            wrong += 1
        if png and state == DOT and DOT not in seen:
            dev.png(png)
        seen.add(state)
    running = frames >= 15                 # the capture model may end the take with a gap later; the dot only needs it running
    dev.press(1, 0.02)                      # STOP ends it
    for _ in range(64):
        if field('PHASE') == 0:
            break
        dev.run(0.01)
    dev.press('exit', 0.05)
    dev.run(0.1)
    after = columns()
    return [entry('status_dot_blinks_on_main_screen', running and seen == {DOT, bytes(5)} and wrong <= 2 and before == bytes(5),
                  f'{frames} samples while recording (phase {field("PHASE")}, error {field("ERROR")}), patterns {sorted(x.hex() for x in seen)}, off the blink {wrong} frames, before {before.hex()}'),
            entry('status_dot_gone_after_stop', field('PHASE') == 0 and after == bytes(5),
                  f'phase {field("PHASE")}, columns {after.hex()}')]


def cases(payload, flash=None, png=None):
    from tools.patch import synthaddr
    if synthaddr.is_synth(payload):
        return (feature_cases(payload, flash) + blue_worker_cases(payload, flash) + runtime_cases(payload, flash, png=png)
                + runtime_cases(payload, flash, transport_play=True) + fault_cases(payload, flash)
                + checkpoint_cases(payload, flash) + checkpoint_cases(payload, flash, fail_sync=True)
                + status_dot_cases(payload, flash))
    return (feature_cases(payload, flash) + worker_cases(payload, flash) + runtime_cases(payload, flash)
            + runtime_cases(payload, flash, png=png, card_stall=True) + runtime_cases(payload, flash, slow_card=True)
            + runtime_cases(payload, flash, defer_settings=True) + checkpoint_cases(payload, flash)
            + checkpoint_cases(payload, flash, fail_sync=True) + runtime_cases(payload, flash, remove_card=True)
            + full_card_cases(payload, flash) + rollover_cases(payload, flash)
            + runtime_cases(payload, flash, transport_play=True) + fault_cases(payload, flash)
            + status_dot_cases(payload, flash))


def cases_task():
    import parallel
    return cases(parallel.shared['payload'], parallel.shared['flash'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vsb', type=Path, required=True)
    ap.add_argument('--runtime-only', action='store_true')
    ap.add_argument('--card-stall', action='store_true')
    ap.add_argument('--slow-card', action='store_true')
    ap.add_argument('--png', type=Path)
    args = ap.parse_args()
    payload = args.vsb.read_bytes()[0x100:]
    result = runtime_cases(payload, png=args.png, card_stall=args.card_stall, slow_card=args.slow_card) if args.runtime_only else cases(payload, png=args.png)
    print(json.dumps(result, indent=1))
    return 0 if result and all(e['ok'] for e in result) else 1


if __name__ == '__main__':
    sys.exit(main())
