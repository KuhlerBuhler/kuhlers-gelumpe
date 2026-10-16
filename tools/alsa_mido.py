"""mido output adapter for the explicit-destination Linux ALSA sender."""
import re
import subprocess
from pathlib import Path


class PacedOutput:
    """Send SysEx without keeping an ALSA output port open."""

    def __init__(self, port_name, binary=None):
        match = re.search(r'(\d+:\d+)$', port_name)
        if not match:
            raise ValueError('ALSA destination missing from selected MIDI port')
        self.destination = match.group(1)
        self.binary = Path(binary or Path(__file__).with_name('alsa-sysex')).resolve()
        if not self.binary.is_file():
            raise ValueError('native ALSA sender missing')

    def send(self, message):
        if message.type != 'sysex':
            raise ValueError('paced output accepts SysEx only')
        result = subprocess.run(
            [str(self.binary), '--destination', self.destination],
            input=bytes(message.bytes()), capture_output=True, timeout=15,
        )
        if result.returncode:
            detail = result.stderr.decode(errors='replace').strip()
            raise RuntimeError('ALSA sender stopped: ' + detail)

    def close(self):
        pass
