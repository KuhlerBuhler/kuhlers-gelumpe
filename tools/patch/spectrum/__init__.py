"""The spectrum service behind korg.audio (API 31) on the Sampler builds.

Capture, ring reader, FFT and the column tables come from Spettro by Luigi (GitHub reflectiveboi, PR #429). The runtime
(script_hooks.build) assembles these files with script_audio_service.s; the synth has no native capture and links
script_audio_service_none.s instead.
"""
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ('capture.s', 'spectrum_worker.s', 'stream_capture.s', 'coefficients.s', 'fft_fixed.s', 'fft_frontend.s')
CONTEXT_SIZE = 103424
RATE, POINTS = 48000, 4096
VIEWS = (('full', 20000), ('bass', 2000))


def tables():
    """128 log columns from 20 Hz per view: FFT bin range, or for a column narrower than a bin the bin and a weight of 256
    (bit 31 set), which interpolates power and adds no resolution; then the Q8 mantissa table of the log2."""
    sections = []
    for name, high in VIEWS:
        edges = [20 * (high / 20) ** (i / 128) for i in range(129)]
        rows = []
        for a, b in zip(edges, edges[1:]):
            if (b - a) * POINTS / RATE < 1:
                position = math.sqrt(a * b) * POINTS / RATE
                start = min(2047, max(1, math.floor(position)))
                weight = round((position - start) * 256)
                if weight == 256:
                    start += 1
                    weight = 0
                end = 0x80000000 | weight
            else:
                start = min(2048, max(1, math.ceil(a * POINTS / RATE)))
                end = min(2049, max(start + 1, math.ceil(b * POINTS / RATE)))
            rows.append(f'    .word {start}, {end}')
        sections.append('spectrum_bins_' + name + ':\n' + '\n'.join(rows))
    sections.append('spectrum_log_fraction:\n    .word ' + ', '.join(str(round(256 * math.log2(1 + i / 16))) for i in range(16)))
    return '\n'.join(sections)


def source():
    return '\n'.join((HERE / name).read_text(encoding='utf-8') for name in FILES) + '\n.align 4\n' + tables() + '\n'
