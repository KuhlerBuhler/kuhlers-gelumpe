"""Independent specification for the next capture pipeline. Offline, no MIDI imports.

This is a reference, NOT a firmware update. Time is derived from sample counts;
unread data is drained from the DSP ring, and gaps invalidate attack captures.
"""
from collections import deque
from dataclasses import dataclass
import math
import struct

RATE = 48000  # Working engine-rate hypothesis, requires physical calibration.
BASE = 0x01C722A0
CAPACITY = 4800
GUARD = 256


@dataclass(frozen=True)
class State:
    cursor: int
    tick: int
    source: int = 1
    active: bool = True
    recording: bool = False
    size: int = CAPACITY * 4


class CaptureGap(Exception):
    """Missing/ambiguous audio must never be rendered as a continuous trace."""


class RingReader:
    """A two-phase read plan; a transport supplies READ and before/after states.

    The caller publishes data only after finish succeeds. At first poll, or after
    a fault, start from a guarded cursor rather than inventing older samples.
    """
    def __init__(self):
        self.reader = None
        self.last_tick = None
        self.source = None
        self.samples = 0
        self.plan = None

    @staticmethod
    def validate(state):
        offset = state.cursor - BASE
        if (not state.active or state.recording or state.size != CAPACITY * 4
                or not 0 <= offset < CAPACITY * 4 or offset % 4):
            raise CaptureGap('Capture inactive, occupied, or invalid DSP cursor')
        return offset // 4

    def reset(self):
        self.reader = self.last_tick = self.source = self.plan = None

    def begin(self, state):
        try:
            writer = self.validate(state)
            end = (writer - GUARD) % CAPACITY
            if self.reader is None:
                self.reader, self.last_tick, self.source = end, state.tick, state.source
                return []
            elapsed = (state.tick - self.last_tick) & 0xFFFFFFFF
            if state.source != self.source or elapsed >= 80:
                raise CaptureGap('Source changed or ring-wrap count is ambiguous')
            count = (end - self.reader) % CAPACITY
            if count + GUARD >= CAPACITY:
                raise CaptureGap('Reader too close to overwritten data')
            first = min(count, CAPACITY - self.reader)
            spans = [(BASE + self.reader * 4, first * 4)] if first else []
            if count > first:
                spans.append((BASE, (count - first) * 4))
            self.plan = (state, end, count)
            return spans
        except CaptureGap:
            self.reset()
            raise

    def finish(self, state, payload):
        if self.plan is None:
            if payload:
                raise CaptureGap('Unexpected payload without a read plan')
            return b''
        before, end, count = self.plan
        try:
            writer = self.validate(state)
            if state.source != before.source or len(payload) != count * 4:
                raise CaptureGap('Source or read length changed')
            elapsed = (state.tick - before.tick) & 0xFFFFFFFF
            advance = (writer - (before.cursor - BASE) // 4) % CAPACITY
            margin = CAPACITY - count - GUARD
            if elapsed >= 80 or elapsed * RATE // 1000 >= margin or advance >= margin:
                raise CaptureGap('Snapshot may have been overwritten during transfer')
            self.reader, self.last_tick = end, before.tick
            self.samples += count
            self.plan = None
            return bytes(payload)
        except CaptureGap:
            self.reset()
            raise


class PeakBins:
    """Raw signed-16 peak level in fixed 1 ms bins, without per-frame normalization.

    A DC offset is retained honestly. It is not silently erased or labeled silence.
    Absolute peaks are a level display, not an exact mathematical AM envelope.
    """
    def __init__(self):
        self.bins = deque(maxlen=2048)
        self.index = 0
        self.in_bin = 0
        self.peak = [0, 0]

    def append(self, pcm):
        if len(pcm) % 4:
            raise ValueError('Expected packed signed-16 component pairs')
        for left, right in struct.iter_unpack('<hh', pcm):
            self.peak[0] = max(self.peak[0], abs(left))
            self.peak[1] = max(self.peak[1], abs(right))
            self.index += 1
            self.in_bin += 1
            if self.in_bin == 48:
                self.bins.append((self.index - 48, *self.peak))
                self.in_bin, self.peak = 0, [0, 0]


class AttackCapture:
    """Single-shot attack capture with pre-trigger and a fixed sample-clock horizon.

    Once complete, the view is held for inspection. Rearm explicitly for a new
    sound. Scale depends on the whole event and remains fixed across its decay.
    """
    def __init__(self, window_ms=512, threshold=256, pre_ms=10):
        if window_ms not in (128, 512, 2048) or not 0 < threshold <= 32768 or not 0 <= pre_ms < window_ms:
            raise ValueError('Invalid window, trigger or pre-trigger')
        self.total = window_ms * 48
        self.pre = pre_ms * 48
        self.threshold = threshold
        self.quiet_samples = 0
        self.armed = False
        self.pending = deque(maxlen=self.pre)
        self.audio = []
        self.index = 0
        self.trigger = None
        self.start = None
        self.done = False
        self.input_clipped = False
        self.invalid = False

    def gap(self):
        self.invalid = True
        self.audio.clear()
        self.pending.clear()

    def append(self, pcm):
        if self.invalid or self.done:
            return
        if len(pcm) % 4:
            raise ValueError('Expected packed component pairs')
        for pair in struct.iter_unpack('<hh', pcm):
            if self.done:
                break
            if self.trigger is None:
                level = max(abs(x) for x in pair)
                if level <= self.threshold // 2:
                    self.quiet_samples += 1
                    if self.quiet_samples >= 96:  # 2 ms of quiet before accepting an attack.
                        self.armed = True
                else:
                    self.quiet_samples = 0
                if level >= self.threshold and self.armed:
                    self.trigger = self.index
                    self.audio = list(self.pending)
                    self.start = self.index - len(self.audio)
                else:
                    self.pending.append(pair)
            if self.trigger is not None:
                self.audio.append(pair)
                self.input_clipped |= any(x in (-32768, 32767) for x in pair)
                self.done = len(self.audio) >= self.total
            self.index += 1

    def scale(self):
        if self.invalid or not self.audio:
            return 32768
        peak = max(abs(x) for pair in self.audio for x in pair)
        # Headroom is display range, not extra ADC/DSP resolution. Full-scale
        # numeric samples remain visibly inside the graph rather than at its edge.
        return max(1, math.ceil(peak * 1.1))

    def columns(self, component=0):
        if self.invalid or not self.done or component not in (0, 1):
            raise ValueError('No complete, valid capture')
        width = len(self.audio) // 128
        return [max(abs(pair[component]) for pair in self.audio[i*width:(i+1)*width])
                for i in range(128)]

    def heights(self, component=0, pixels=44):
        # One scale for the whole event and both components; never normalize the tail.
        scale = self.scale()
        return [min(pixels, (value * pixels + scale // 2) // scale) for value in self.columns(component)]


def signal_attack_decay(onset_ms=30, decay_ms=100, duration_ms=600, amplitude=24000, frequency=1000):
    result = bytearray()
    onset = onset_ms * 48
    for i in range(duration_ms * 48):
        value = 0 if i < onset else round(amplitude * math.exp(-(i-onset)/(48*decay_ms))
                                          * math.sin(2*math.pi*frequency*(i-onset)/RATE))
        result.extend(struct.pack('<hh', value, value))
    return bytes(result)
