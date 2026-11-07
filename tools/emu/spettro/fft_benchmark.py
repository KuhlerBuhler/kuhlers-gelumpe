"""Build the bounded native FFT timing probe. Importing does not access MIDI."""
from pathlib import Path
import hashlib
from emulator import SOURCE, assemble, ORIGIN

SIZE = 49216
EXPECTED_SHA = '29ccb2ea6fcc949ceb048f779f0e9f20805053ba5d60ce6ecefd65005780fc0a'


def build():
    source = '\n'.join(((Path(__file__).parent/name) if name == 'fft_benchmark.s' else (SOURCE/name)).read_text()
                       for name in ('fft_benchmark.s', 'fft_fixed.s'))
    code = assemble(source, origin=ORIGIN)
    if len(code.bytes)>1024 or hashlib.sha256(code.bytes).hexdigest()!=EXPECTED_SHA:
        raise RuntimeError('Timing probe changed; repeat offline verification before pinning')
    return code
