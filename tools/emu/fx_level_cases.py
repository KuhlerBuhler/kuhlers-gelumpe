#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Insert and master effect levels with Korg's own DSP code (GNU bfin sim coupled to the ARM emulator).

A fixed test signal goes into SPORT0 RX (BLECH_SPORT_RX_SOURCE): a 1 kHz sine, then a louder noise burst.
Part 1 plays it through its oscillator "Audio In Mn" (pad 1 held), so it passes the part, its insert and the master
effect as on the device. Inserts are chosen with the IFX encoder and the IFX ON key, master effects with Korg's own
setter while the touch pad is held. SPORT0 TX is captured (BLECH_SPORT_TX_CAPTURE) and every window is compared with
the same signal without the effect. The codec and the analog output are not modeled, so only relative levels count
(docs/messungen/2026-11-16-fx-pegel-im-dsp-sim.md). Run by hand: a full levels run takes about 30 minutes.

    tools/emu/.venv/bin/python tools/emu/fx_level_cases.py levels --vsb PATCHED.VSB --worker blackfin-worker [--only A,B]
    tools/emu/.venv/bin/python tools/emu/fx_level_cases.py reset --vsb PATCHED.VSB --worker blackfin-worker
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import time

from blackfin_backend import BlackfinPort, BackendError
from blackfin_rom import SysControl
import dsp_model as dsp
from firmware import identify
from machine import Machine, blank_flash
from splash_cases import Dev

CORE_HZ = 516096000             # the SPORT0 test clock of blackfin_cases
RATE = 48000
WORDS = 4                       # slot words per frame; the DSP writes left to slot 0 and right to slot 2
SINE_HZ, SINE_S, BURST_S = 1000, 0.2, 0.05
LOOP = int(RATE * (SINE_S + BURST_S))
SINE_LEVEL, BURST_RMS = 0.25, 0.5          # of full scale: -12 dBFS sine, -6 dBFS RMS noise
GUARD = 480                     # frames skipped after each signal change: DSP latency and effect tails
WINDOW_S, SETTLE_S = 0.5, 0.3
GET = {"ifx": 0xC003E738, "mfx": 0xC003E750}      # the firmware's preset getters and counts (preset_cases.py)
COUNT = {"ifx": 0xC003EFDC, "mfx": 0xC003EFE4}
SET_MFX = 0xC0048A64
PATTERN, GLOBALS = 0xC033E6A4, 0xC0691334
PART_BASE, PART_STRIDE = 0x800, 0x330
MFX_SEND, IFX_ON, IFX_TYPE = 27, 32, 33     # part fields
SAMPLE_ENCODER, CUTOFF_ENCODER, IFX_ENCODER = 1, 2, 4
KNOBS = {"level": 0, "pan": 1, "pitch": 2}
KEY = {"exit": 0x0D, "ifx_on": 0x21, "mfx_send": 0x1A, "touchpad": 0x22}
AUDIO_IN = "Audio In Mn"
PART_VALUES = {"level": dsp.LEVEL, "pan_left": dsp.PAN_LEFT, "pan_right": dsp.PAN_RIGHT, "filter": dsp.FILTER,
               "ifx_on": dsp.IFX_ON, "mfx_send": dsp.MFX_SEND}

INSERTS = ("Loud Distortion", "Bounce Gate 16", "Bounce Gate 8", "Warm Drive", "Bit Grinder", "Glue Comp",
           "Bass Enhancer", "Hardtekk Kick")
MASTERS = ("Master Pumper", "Multi Tap", "Wow Tape", "Dub Delay", "Ping Pong", "Ladder Drive", "Ring Crush",
           "Master Limiter", "Master Tilt", "Master Warmth", "Master Glue")


def test_signal(sine_level=SINE_LEVEL, burst=True):
    """One loop of slot words: SINE_S of sine, then BURST_S of noise (fixed LCG), the same word in all four slots.
    Without the burst the sine runs through the whole loop (a whole number of periods)."""
    words = array.array('i')
    state = 1
    for n in range(LOOP):
        if n < RATE * SINE_S or not burst:
            value = sine_level * math.sin(2 * math.pi * SINE_HZ * n / RATE)
        else:
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            value = BURST_RMS * math.sqrt(3) * (state / 2 ** 31 - 1)
        sample = max(-0x800000, min(0x7FFFFF, round(value * 0x7FFFFF))) << 8
        words.extend((sample,) * WORDS)
    return words.tobytes()


def power(samples, hz):
    """Power of one frequency (Goertzel), as the mean square a sine of that frequency alone would have."""
    k = 2 * math.cos(2 * math.pi * hz / RATE)
    s1 = s2 = 0.0
    for x in samples:
        s1, s2 = x + k * s1 - s2, s1
    return 2 * (s1 * s1 + s2 * s2 - k * s1 * s2) / len(samples) ** 2


def db(value, ref):
    return round(10 * math.log10(value / ref), 2) if value > 0 and ref > 0 else None


def near(delta, limit=0.5):
    return delta is not None and abs(delta) < limit


def mean_square(samples):
    return sum(x * x for x in samples) / len(samples) if samples else 0.0


def measure(frames, first):
    """Level, peak, dropouts and spectrum of a window that starts at frame number `first` of the capture."""
    sine_end = int(RATE * SINE_S)
    mono = [(l + r) / 2 for l, r in frames]
    phase = [(first + i) % LOOP for i in range(len(frames))]
    sine = [x for x, p in zip(mono, phase) if GUARD <= p < sine_end]
    burst = [x for x, p in zip(mono, phase) if sine_end + GUARD // 4 <= p]
    block = RATE // 500                     # 2 ms
    envelope = [math.sqrt(mean_square(mono[i:i + block])) for i in range(0, len(mono) - block, block)
                if GUARD <= phase[i] and phase[i + block - 1] < sine_end and phase[i] < phase[i + block - 1]]
    median = sorted(envelope)[len(envelope) // 2] if envelope else 0.0
    piece = sine[:4800]
    others = {hz: power(piece, hz) for hz in range(500, 12001, 500) if hz != SINE_HZ} if len(piece) == 4800 else {}
    bit = burst[:1200]
    return dict(ms=sum(l * l + r * r for l, r in frames) / (2 * len(frames)) if frames else 0.0,
                peak=max((max(abs(l), abs(r)) for l, r in frames), default=0.0),
                sine_ms=mean_square(piece), tone=power(piece, SINE_HZ) if len(piece) == 4800 else 0.0,
                burst_ms=mean_square(bit),
                high=sum(power(bit, hz) for hz in range(8000, 20001, 2000)) if len(bit) == 1200 else 0.0,
                low=sum(power(bit, hz) for hz in range(400, 2001, 400)) if len(bit) == 1200 else 0.0,
                dips=sum(1 for e in envelope if e < median / 2), blocks=len(envelope),
                other=max(others.items(), key=lambda kv: kv[1], default=(None, 0.0)))


def compare(wet, dry):
    return dict(rms_db=db(wet['ms'], dry['ms']), peak_db=db(wet['peak'] ** 2, dry['peak'] ** 2),
                sine_db=db(wet['sine_ms'], dry['sine_ms']), burst_db=db(wet['burst_ms'], dry['burst_ms']),
                tone_share=round(wet['tone'] / wet['sine_ms'], 3) if wet['sine_ms'] else None,
                strongest_other_hz=wet['other'][0], strongest_other_db=db(wet['other'][1], wet['tone']),
                tilt_db=db(wet['high'], wet['low']), dry_tilt_db=db(dry['high'], dry['low']),
                dips=wet['dips'], dry_dips=dry['dips'], blocks=wet['blocks'],
                rms_dbfs=db(wet['ms'], 1), peak_dbfs=db(wet['peak'] ** 2, 1))


class Rig:
    """A booted device with the DSP sim, the test signal on the input and the output captured."""

    def __init__(self, payload, worker, work, signal=None):
        source, self.capture = Path(work) / 'rx.raw', Path(work) / 'tx.raw'
        source.write_bytes(signal or test_signal())
        os.environ['BLECH_SPORT_RX_SOURCE'] = str(source)
        os.environ['BLECH_SPORT_TX_CAPTURE'] = str(self.capture)
        self.port = BlackfinPort(worker, operating=True, timeout=15, rom=SysControl(),
                                 sport=dict(core_hz=CORE_HZ, input='file'), host_transport='fifo')
        self.port.__enter__()
        try:
            profile = identify(payload)
            self.build = profile.build
            self.m = Machine(payload, flash=blank_flash(), profile=profile, dsp_backend=self.port)
            self.dev = Dev(payload, machine=self.m)
            while not self.m.booted and self.m.time_ns < 12e9 and not self.m.asserts:
                self.m.run_until(self.m.time_ns / 1e9 + .1)
            if not self.m.booted:
                raise BackendError(f'no main screen after {self.m.time_ns / 1e9:.1f} s')
            self.m.finish_boot()
            self.run(0.5)
        except BaseException:
            self.close()
            raise

    def close(self):
        self.port.__exit__(None, None, None)

    def run(self, seconds):
        self.m.run_until(self.m.time_ns / 1e9 + seconds)

    def frame(self):
        return self.port.backend.sport_status()['tx_frames']

    def frames(self, start, end):
        with open(self.capture, 'rb') as file:
            file.seek(start * WORDS * 4)
            data = array.array('i')
            data.frombytes(file.read((end - start) * WORDS * 4))
        return [(data[i] / 2 ** 31, data[i + 2] / 2 ** 31) for i in range(0, len(data) - WORDS + 1, WORDS)]

    def window(self, seconds=WINDOW_S):
        first = self.frame()
        self.run(seconds)
        return measure(self.frames(first, self.frame()), first)

    def crashed(self):
        return self.port.backend.register(47) != 0 or bool(self.m.asserts)

    def part(self, field, part=0):
        return self.dev.read(self.dev.u32(PATTERN) + 4 + PART_BASE + part * PART_STRIDE + field, 1)[0]

    def key(self, name, wait=0.25):
        self.m.press(KEY[name], True)
        self.run(0.08)
        self.m.press(KEY[name], False)
        self.run(wait)

    def encoder(self, index, delta, wait=0.25):
        while delta:
            step = max(-60, min(60, delta))
            self.m.send([1, index, 0, step & 0xFF, 0])
            self.run(0.05)
            delta -= step
        self.run(wait)

    def names(self, kind):
        out = []
        for i in range(self.dev.call(COUNT[kind])):
            record = self.dev.call(GET[kind], i)
            out.append(self.dev.read(record + 1, 15).split(b'\0')[0].decode('latin-1').strip())
        return out

    def oscillators(self):
        """The oscillator names as the payload lists them (32-byte records), or [] on a build without that table."""
        image = bytes(self.m.uc.mem_read(0xC0000000, 0x200000))
        at = image.find(AUDIO_IN.encode() + b'\0')
        if at < 0:
            return []
        while at >= 32 and image[at - 32:at - 31].isalnum():
            at -= 32
        names = []
        while image[at:at + 1].isalnum():
            names.append(image[at:at + 16].split(b'\0')[0].decode('latin-1'))
            at += 32
        return names

    def tone_share(self, seconds=0.3):
        w = self.window(seconds)
        return w['tone'] / w['sine_ms'] if w['sine_ms'] > 1e-8 else 0.0

    def play_input(self):
        """Part 1's oscillator to Audio In Mn with the SAMPLE encoder and pad 1 held; the 1 kHz tone must reach the output."""
        names = self.oscillators()
        if AUDIO_IN not in names:
            raise BackendError(f'no {AUDIO_IN} oscillator on this build')
        self.encoder(SAMPLE_ENCODER, names.index(AUDIO_IN))
        self.m.send([4, 0, 0, 100, 1])
        self.run(0.3)
        for _ in range(3):
            if self.tone_share() > 0.5:
                return names
            self.encoder(SAMPLE_ENCODER, 1)
        raise BackendError('the part does not play the input')

    def set_ifx(self, index):
        for _ in range(3):
            at = self.part(IFX_TYPE)
            if at == index:
                break
            self.encoder(IFX_ENCODER, index - at)
        if not self.part(IFX_ON):
            self.key('ifx_on')
        return self.part(IFX_TYPE) == index and self.part(IFX_ON) == 1

    def ifx_off(self):
        if self.part(IFX_ON):
            self.key('ifx_on')

    def set_mfx(self, index):
        self.dev.call(SET_MFX, self.dev.u32(GLOBALS) + 0x4004, index, 1)
        self.run(0.2)

    def touch(self, down):
        self.m.press(KEY['touchpad'], down)
        if down:
            self.m.send([5, 500 >> 8, 500 & 0xFF, 500 >> 8, 500 & 0xFF])
        self.run(0.05)


def progress(label, done, total):
    folder = Path.home() / '.claude' / 'progress'
    try:
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f'{label}.json.tmp'
        tmp.write_text(json.dumps(dict(label=label, done=done, total=total, updatedAt=time.time(), staleAfter=900)))
        tmp.replace(folder / f'{label}.json')
    except OSError:
        pass


def levels(payload, worker, only=None, label='FX-Pegel', signal=None):
    """Every effect of INSERTS and MASTERS this build has, against the dry part, plus dropouts and spectrum."""
    report = dict(ok=False, inserts=[], masters=[], missing=[], checks={})
    wanted = [n for n in INSERTS + MASTERS if not only or n in only]
    with tempfile.TemporaryDirectory() as work:
        rig = Rig(payload, worker, work, signal)
        try:
            report['build'] = rig.build
            ifx_names, mfx_names = rig.names('ifx'), rig.names('mfx')
            report['counts'] = dict(ifx=len(ifx_names), mfx=len(mfx_names))
            total, done = len(wanted) + 2, 0
            progress(label, done, total)
            rig.play_input()
            if rig.part(MFX_SEND):
                rig.key('mfx_send')
            rig.ifx_off()
            dry = rig.window()
            report['dry'] = compare(dry, dry)
            done += 1
            for name in (n for n in INSERTS if n in wanted):
                if name not in ifx_names:
                    report['missing'].append(name)
                    continue
                index = ifx_names.index(name)
                chosen = rig.set_ifx(index)
                rig.run(SETTLE_S)
                wet = rig.window()
                mark = rig.frame()
                rig.run(0.05)
                row = dict(name=name, index=index, chosen=chosen, crashed=rig.crashed(), output_runs=rig.frame() > mark)
                row.update(compare(wet, dry))
                report['inserts'].append(row)
                done += 1
                progress(label, done, total)
                if row['crashed']:
                    raise BackendError(f'DSP stopped on {name}')
            rig.ifx_off()
            if not rig.part(MFX_SEND):
                rig.key('mfx_send')
            rig.run(SETTLE_S)
            master_dry = rig.window()
            report['master_dry'] = compare(master_dry, dry)
            done += 1
            for name in (n for n in MASTERS if n in wanted):
                if name not in mfx_names:
                    report['missing'].append(name)
                    continue
                index = mfx_names.index(name)
                rig.set_mfx(index)
                rig.touch(True)
                rig.run(SETTLE_S)
                wet = rig.window()
                rig.touch(False)
                rig.run(0.5)                     # delays ring out before the next one
                row = dict(name=name, index=index, crashed=rig.crashed())
                row.update(compare(wet, master_dry))
                report['masters'].append(row)
                done += 1
                progress(label, done, total)
            report['checks'] = dict(
                input_reaches_the_output=dry['tone'] / dry['sine_ms'] > 0.5 if dry['sine_ms'] else False,
                inserts_chosen=all(r['chosen'] for r in report['inserts']),
                output_keeps_running=all(r['output_runs'] for r in report['inserts']),
                no_dsp_crash=not rig.crashed())
            report['ok'] = all(report['checks'].values())
            report['model_s'] = rig.m.time_ns / 1e9
        except (BackendError, RuntimeError, ValueError) as error:
            report['error'] = str(error)
        finally:
            rig.close()
    return report


def reset(payload, worker):
    """#611/#506: change PITCH, LEVEL, PAN, CUTOFF, IFX TYPE and IFX ON of part 1 (init SAW, pad 1 held), then EXIT + pad 1.
    The part's whole parameter block at the DSP, its voice's PITCH word and the DSP output (level and brightness) must
    be as before the changes. Words of the block that change on their own while the part plays are DSP state, not
    parameters, and are left out. Turning IFX TYPE away and back with the encoder leaves the other type's parameter
    words in the block without changing the sound, so that round trip runs first as the reference for the insert:
    it must be audible, and after the reset the insert (IFX ON) must sound and read like after the round trip."""
    report = dict(ok=False, checks={})
    with tempfile.TemporaryDirectory() as work:
        rig = Rig(payload, worker, work)
        try:
            report['build'] = rig.build
            base = dsp.PART_ON['synth' if rig.build == 'synth' else 'sampler']
            w = dsp.VOICE_WORDS

            def voices():
                return struct.unpack(f'<{dsp.VOICES * w}I', rig.port.backend.read(dsp.slot(dsp.VOICE), dsp.VOICES * w * 4))

            def part_block():
                return struct.unpack(f'<{dsp.PART_STRIDE}I', rig.port.backend.read(dsp.slot(base), dsp.PART_STRIDE * 4))

            def state():
                block = part_block()
                first = rig.frame()
                before = voices()
                rig.run(0.3)
                later = voices()
                mono = [(l + r) / 2 for l, r in rig.frames(first, rig.frame())]
                gated = [v for v in range(dsp.VOICES) if later[v * w]]
                again = part_block()
                return dict(block=block, own={k for k in range(dsp.PART_STRIDE) if again[k] != block[k]}, gated=gated, pitch=sorted({later[v * w + dsp.PITCH] for v in gated}),
                            changing={v: [k for k in range(1, w) if later[v * w + k] != before[v * w + k]] for v in gated},
                            ms=mean_square(mono), edge=mean_square([b - a for a, b in zip(mono, mono[1:])]))

            def hold():
                rig.m.send([4, 0, 0, 100, 1])
                rig.run(0.3)

            hold()
            rig.key('ifx_on')
            reference = state()
            rig.encoder(IFX_ENCODER, 3)
            other = state()
            rig.encoder(IFX_ENCODER, -3)
            round_trip = state()
            rig.key('ifx_on')
            before = state()
            for knob, raw in (('pitch', 230), ('level', 30), ('pan', 240)):
                rig.m.send([2, KNOBS[knob], 0, raw, 0])
                rig.run(0.1)
            rig.encoder(CUTOFF_ENCODER, -30)
            rig.encoder(IFX_ENCODER, 3)
            if not rig.part(IFX_ON):
                rig.key('ifx_on')
            rig.run(1.0)
            turned = state()
            rig.m.send([4, 0, 0, 0, 0])
            rig.run(0.1)
            rig.m.press(KEY['exit'], True)
            rig.run(0.1)
            rig.m.send([4, 0, 0, 100, 1])
            rig.run(0.1)
            rig.m.send([4, 0, 0, 0, 0])
            rig.m.press(KEY['exit'], False)
            rig.run(0.5)
            hold()
            after = state()
            rig.key('ifx_on')
            after_ifx = state()
            names = {offset: name for name, offset in PART_VALUES.items()}
            label = lambda k: names.get(k, hex(k))
            own = set().union(*(x['own'] for x in (reference, other, round_trip, before, turned, after, after_ifx)))
            insert = {k for k in range(dsp.PART_STRIDE) if reference['block'][k] != before['block'][k]} - own
            leftover = {k for k in range(dsp.PART_STRIDE) if round_trip['block'][k] != reference['block'][k]} - own
            moved = [k for k in range(dsp.PART_STRIDE) if k not in own and turned['block'][k] != before['block'][k]]
            not_back = [k for k in range(dsp.PART_STRIDE)
                        if k not in own | insert | leftover and after['block'][k] != before['block'][k]]
            insert_not_back = [k for k in range(dsp.PART_STRIDE)
                               if k not in own | leftover and after_ifx['block'][k] != round_trip['block'][k]]
            bright = lambda x: x['edge'] / x['ms']
            report.update(moved=[label(k) for k in moved], not_back=[label(k) for k in not_back],
                          dsp_state=[label(k) for k in sorted(own)], insert_words=[label(k) for k in sorted(insert)],
                          insert_not_back=[label(k) for k in insert_not_back],
                          leftover_words=[label(k) for k in sorted(leftover)],
                          insert_output_db=db(after_ifx['ms'], reference['ms']),
                          insert_brightness_db=dict(other_type=db(bright(other), bright(reference)),
                                                    round_trip=db(bright(round_trip), bright(reference)),
                                                    after=db(bright(after_ifx), bright(reference))),
                          not_back_values={label(k): [before['block'][k], turned['block'][k], after['block'][k]]
                                           for k in not_back},
                          pitch=dict(before=before['pitch'], turned=turned['pitch'], after=after['pitch']),
                          changing=dict(before=before['changing'], after=after['changing']),
                          output_db=dict(turned=db(turned['ms'], before['ms']), after=db(after['ms'], before['ms'])),
                          brightness_db=dict(turned=db(turned['edge'] / turned['ms'], before['edge'] / before['ms']),
                                             after=db(after['edge'] / after['ms'], before['edge'] / before['ms'])),
                          dbfs=db(before['ms'], 1))
            report['checks'] = dict(
                part_sounds=before['ms'] > 1e-6,
                changes_reach_the_dsp=len(moved) >= 3 and turned['pitch'] != before['pitch'],
                part_block_back=not not_back,
                pitch_back=after['pitch'] == before['pitch'],
                insert_type_audible=abs(db(bright(other), bright(reference)) or 0) > 1,
                insert_back=not insert_not_back and near(db(after_ifx['ms'], reference['ms']))
                and near(db(bright(after_ifx), bright(reference))),
                sound_back=near(report['output_db']['after']) and near(report['brightness_db']['after']),
                no_dsp_crash=not rig.crashed())
            report['ok'] = all(report['checks'].values())
        except (BackendError, RuntimeError, ValueError) as error:
            report['error'] = str(error)
        finally:
            rig.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('levels', 'reset'))
    parser.add_argument('--vsb', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--only', default='', help='comma separated effect names, _ for a space')
    parser.add_argument('--label', default='FX-Pegel', help='name of the progress file')
    parser.add_argument('--sine-dbfs', type=float, default=-12.0, help='peak level of the test sine')
    parser.add_argument('--no-burst', action='store_true', help='sine only, no noise burst')
    args = parser.parse_args()
    try:
        raw = args.vsb.read_bytes()
        if len(raw) != 0x200100:
            raise ValueError('expected a complete SYSTEM.VSB')
        if args.mode == 'levels':
            report = levels(raw[0x100:], args.worker, only=[n.replace('_', ' ') for n in args.only.split(',') if n] or None,
                            label=args.label,
                            signal=test_signal(10 ** (args.sine_dbfs / 20), not args.no_burst))
        else:
            report = reset(raw[0x100:], args.worker)
    except (OSError, BackendError, ValueError) as error:
        report = dict(ok=False, error=str(error))
    print(json.dumps(report, indent=1))
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
