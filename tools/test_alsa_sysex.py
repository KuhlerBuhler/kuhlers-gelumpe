"""Linux integration checks using virtual ALSA ports only."""
import re
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

import rtmidi
import mido
from alsa_mido import PacedOutput

BINARY = Path(sys.argv.pop(1)).resolve()

class AlsaSysexTests(unittest.TestCase):
    def setUp(self):
        self.name = 'offline-alsa-' + uuid.uuid4().hex
        self.receiver = rtmidi.MidiIn()
        self.receiver.ignore_types(sysex=False, timing=True, active_sense=True)
        self.receiver.open_virtual_port(self.name)
        self.messages = []
        self.receiver.set_callback(lambda event, data: self.messages.append(bytes(event[0])))
        ports = [p for p in rtmidi.MidiOut().get_ports() if self.name in p]
        self.assertEqual(len(ports), 1)
        match = re.search(r'(\d+:\d+)$', ports[0])
        self.assertIsNotNone(match)
        self.destination = match.group(1)
        self.port_name = ports[0]

    def tearDown(self):
        self.receiver.close_port()

    def send(self, data, destination=None):
        return subprocess.run([str(BINARY), '--destination', destination or self.destination], input=data, capture_output=True, timeout=10)

    def test_large_frames_reassemble_exactly(self):
        for length in (2349, 3519, 4104, 4690, 18733, 59894):
            with self.subTest(length=length):
                self.messages.clear()
                data = b'\xf0' + bytes((i * 17) % 128 for i in range(length - 2)) + b'\xf7'
                result = self.send(data)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                deadline = time.monotonic() + 2
                while not self.messages and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(self.messages, [data])

    def test_bad_frames_never_reach_port(self):
        for data in (b'', b'\xf0\x01', b'\x01\xf7', b'\xf0\x80\xf7', b'\xf0\x01\xf7\xf0\xf7'):
            with self.subTest(data=data):
                result = self.send(data)
                self.assertNotEqual(result.returncode, 0)
        time.sleep(0.05)
        self.assertEqual(self.messages, [])

    def test_mido_adapter_preserves_large_frame(self):
        output = PacedOutput(self.port_name, BINARY)
        message = mido.Message("sysex", data=[i % 128 for i in range(18731)])
        output.send(message)
        deadline = time.monotonic() + 2
        while not self.messages and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.messages, [bytes(message.bytes())])
        output.close()

    def test_adapter_rejects_non_sysex(self):
        output = PacedOutput(self.port_name, BINARY)
        with self.assertRaises(ValueError):
            output.send(mido.Message("note_on"))
        self.assertEqual(self.messages, [])

    def test_invalid_destination_fails(self):
        result = self.send(b'\xf0\x01\xf7', '999:0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.messages, [])

if __name__ == '__main__':
    unittest.main()
