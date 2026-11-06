# SPDX-License-Identifier: GPL-2.0-only
"""The local emulator service, run against a stand-in machine (no firmware, no Unicorn)."""

import base64
import contextlib
import hashlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as server_module  # noqa: E402
from server import Emulator, serve, VSB_SIZE, FIRMWARE_AT  # noqa: E402
from firmware import ProfileError  # noqa: E402
from machine import SysexReader  # noqa: E402
from cardstore import CardStore  # noqa: E402
from fat32 import Volume  # noqa: E402

ORIGIN = "http://127.0.0.1:8737"
TOKEN = "test-token"


class FakeMachine:
    """Draws a counter into the display and can be told to fail like the firmware."""

    def __init__(self, payload, flash, assert_after=None):
        self.payload, self.flash = payload, flash
        self.time_ns = 0
        self.fb = [[0] * 128 for _ in range(8)]
        self.leds = {}
        self.asserts = []
        self.assert_after = assert_after
        self.steps = 0
        self.sent = []
        self.midi_sent, self.replies = [], []
        self.powered = True
        self.panel_count = 0
        self.hang_after = None
        self.boot_after = None               # steps until the main screen; None: there from the start

    @property
    def booted(self):
        return self.boot_after is None or self.steps >= self.boot_after

    def midi(self, data):
        self.midi_sent.append(bytes(data))
        self.replies.append(bytes([0xF0, 0x42, 0x30, 0, 1, 0x24, 0x21, 0xF7]))

    def midi_out(self):
        out, self.replies = self.replies, []
        return out

    def send(self, msg):
        self.sent.append(list(msg))
        if msg[:2] == [0x06, 0]:
            self.powered = False             # the firmware lets go of the power hold

    def run_until(self, seconds):
        self.time_ns = int(seconds * 1e9)
        self.steps += 1
        if not self.hang_after or self.steps < self.hang_after:
            self.panel_count += 1
        self.fb[0][0] = self.steps & 0xFF
        self.leds = {7: 255} if self.steps > 1 else {}
        if self.assert_after and self.steps >= self.assert_after:
            self.asserts.append({"file": "AM180xSpi.cpp", "line": 55, "polled": []})


class ServiceTest(unittest.TestCase):
    def setUp(self, assert_after=None):
        self.machines = []

        def factory(payload, flash):
            m = FakeMachine(payload, flash, self.assert_after)
            m.boot_after = self.boot_after
            self.machines.append(m)
            return m

        self.assert_after = assert_after
        self.boot_after = None
        self.server, _, self.emu = serve(0, token=TOKEN, origins={ORIGIN}, emulator=Emulator(factory, power_hold=0.2))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.emu.stop()
        self.server.shutdown()
        self.server.server_close()

    def request(self, method, path, body=b"", headers=None, token=TOKEN, origin=ORIGIN, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if origin: h["Origin"] = origin
        if token: h["X-Emu-Token"] = token
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r, json.loads(data) if data and r.getheader("Content-Type") == "application/json" else data

    def events(self, wanted, timeout=3, then=None):
        """Read the event stream until `wanted(seen)`. `then` runs once the stream is open: an event that is
        sent once (a MIDI reply) is not replayed to a client that connects later, so what causes it must come after."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        conn.request("GET", f"/events?token={TOKEN}", headers={"Host": f"127.0.0.1:{self.port}", "Origin": ORIGIN})
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), ORIGIN)
        if then:
            then()
        seen, kind, deadline = {}, None, time.monotonic() + timeout
        while time.monotonic() < deadline and not wanted(seen):
            line = r.fp.readline().decode().strip()
            if line.startswith("event: "): kind = line[7:]
            elif line.startswith("data: "): seen.setdefault(kind, []).append(json.loads(line[6:]))
        conn.close()
        return seen

    def test_refuses_without_token_from_other_origins_and_hosts(self):
        self.assertEqual(self.request("GET", "/status", token=None)[0].status, 401)
        self.assertEqual(self.request("GET", "/status", token="wrong")[0].status, 401)
        self.assertEqual(self.request("GET", "/status", origin="https://example.com")[0].status, 403)
        self.assertEqual(self.request("GET", "/status", host="evil.example:80")[0].status, 403)
        self.assertEqual(self.request("GET", "/status")[0].status, 200)

    def test_preflight_names_the_page_and_allows_the_token_header(self):
        r, _ = self.request("OPTIONS", "/firmware", token=None)
        self.assertEqual(r.status, 204)
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), ORIGIN)
        self.assertIn("X-Emu-Token", r.getheader("Access-Control-Allow-Headers"))
        self.assertEqual(self.request("OPTIONS", "/firmware", token=None, origin="https://example.com")[0].status, 403)

    def test_the_export_check_gets_original_copy_flash_and_the_allowed_spans(self):
        calls = []
        self.emu.checker = lambda base, patched, flash, allow, allow_code, boot_flash=None, progress=None: calls.append((base, patched, flash, allow, allow_code)) or {"ok": True, "checks": []}
        r, body = self.request("POST", "/check", body=bytes(VSB_SIZE))
        self.assertEqual(r.status, 400)
        self.assertIn("Original und Kopie", body["error"])
        patched = bytes(VSB_SIZE - 1) + b"\x01"
        r, body = self.request("POST", "/check?allow=0xF9954:1024", body=bytes(VSB_SIZE) + patched)
        self.assertEqual((r.status, body), (200, {"ok": True, "checks": []}))
        self.assertEqual(calls, [(bytes(VSB_SIZE), patched, None, [(0xF9954, 1024)], [])])
        calls.clear()
        self.request("POST", "/check?allow=0xF9954:1024&allowCode=0x2AEAC:4,0x1ABCD:44", body=bytes(VSB_SIZE) + patched)
        self.assertEqual(calls[0][3:], ([(0xF9954, 1024)], [(0x2AEAC, 4), (0x1ABCD, 44)]), "start-phase code a patch asked for reaches check.py")
        self.assertEqual(self.request("POST", "/check?allowCode=1", body=bytes(VSB_SIZE) + patched)[0].status, 400)
        self.assertEqual(self.request("POST", "/check?allow=1:2:3", body=bytes(VSB_SIZE) + patched)[0].status, 400)
        self.assertEqual(self.request("POST", "/check", body=b"\0" * 10)[0].status, 400)

    def test_check_progress_follows_the_run_and_ends_done_or_failed(self):
        self.assertEqual(self.request("GET", "/check/progress")[1], {"state": "idle"})
        self.assertEqual(self.request("GET", "/check/progress", token=None)[0].status, 401)
        seen = []
        snapshot = {"total": 2, "done": 1, "ok": 1, "fail": 0, "groups": [{"id": "menu_cases", "name": "Menü", "total": 2, "done": 1, "state": "running", "ok": 1, "fail": 0}]}

        def checker(base, patched, flash, allow, allow_code, boot_flash=None, progress=None):
            progress(snapshot)
            seen.append(self.request("GET", "/check/progress")[1])
            return {"ok": True, "checks": []}

        self.emu.checker = checker
        self.assertEqual(self.request("POST", "/check", body=bytes(VSB_SIZE) * 2)[0].status, 200)
        self.assertEqual(seen, [{"state": "running", **snapshot}], "a client polling during the run gets the latest snapshot")
        self.assertEqual(self.request("GET", "/check/progress")[1], {"state": "done", **snapshot})

        def broken(*args, boot_flash=None, progress=None):
            raise RuntimeError("boom")

        self.emu.checker = broken
        self.assertEqual(self.request("POST", "/check", body=bytes(VSB_SIZE) * 2)[0].status, 500)
        self.assertEqual(self.request("GET", "/check/progress")[1]["state"], "failed")

    def test_uploads_are_checked_before_anything_runs(self):
        r, body = self.request("POST", "/firmware", body=b"\0" * 100)
        self.assertEqual(r.status, 400)
        self.assertIn("genau", body["error"])
        r, body = self.request("POST", "/start", body=b"{}")
        self.assertEqual(r.status, 400)
        self.assertIn("VSB", body["error"])
        r, body = self.request("POST", "/flash", body=b"\0" * 10)
        self.assertEqual(r.status, 400)
        self.assertEqual(self.machines, [])

    def test_runs_the_firmware_and_streams_display_and_leds(self):
        self.assertEqual(self.request("POST", "/firmware", body=bytes(VSB_SIZE))[0].status, 200)
        r, status = self.request("POST", "/start", body=b"{}")
        self.assertEqual(r.status, 200)
        self.assertEqual(status["state"], "running")
        seen = self.events(lambda s: len(s.get("display", [])) >= 2 and {"7": 255} in s.get("leds", []))
        self.assertGreaterEqual(len(seen["display"]), 2, "the display changed and was sent again")
        self.assertEqual(len(seen["display"][-1]), 1368, "1024 bytes as base64")
        self.assertEqual(seen["leds"][-1], {"7": 255})
        m = self.machines[0]
        self.assertEqual((len(m.payload), m.flash), (VSB_SIZE - 0x100, None))

    def test_streams_the_display_as_levels_besides_the_one_bit_display(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        seen = self.events(lambda s: len(s.get("shade", [])) >= 3 and s.get("display"))
        levels = base64.b64decode(seen["shade"][-1])
        self.assertEqual(len(levels), 128 * 64, "one byte per pixel")
        self.assertLessEqual(max(levels), 15)
        self.assertEqual(len(base64.b64decode(seen["display"][-1])), 1024, "the 1-bit display stays as it was")
        self.assertNotEqual(seen["shade"][0], seen["shade"][-1], "and the levels move on")

    def test_a_page_that_drops_the_event_stream_leaves_no_traceback(self):
        """Windows reports a closed browser tab as ConnectionAbortedError, other systems as a broken pipe or a reset."""
        for error in (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            class Dropped:
                @staticmethod
                def dumps(data):
                    raise error()
            failed, done = [], threading.Event()
            finish = self.server.finish_request

            def finish_request(request, address):
                try:
                    finish(request, address)
                except BaseException as e:            # what socketserver would print as a traceback
                    failed.append(e)
                    raise
                finally:
                    done.set()

            with unittest.mock.patch.object(server_module, "json", Dropped), \
                    unittest.mock.patch.object(self.server, "finish_request", finish_request), \
                    contextlib.redirect_stderr(io.StringIO()):
                conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
                conn.request("GET", f"/events?token={TOKEN}", headers={"Host": f"127.0.0.1:{self.port}", "Origin": ORIGIN})
                self.assertEqual(conn.getresponse().status, 200)
                self.assertTrue(done.wait(3))
                conn.close()
            self.assertEqual(self.emu.clients, [], error.__name__)
            self.assertEqual(failed, [], error.__name__)

    def test_never_runs_faster_than_the_device(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        start = time.monotonic()
        self.request("POST", "/start", body=b"{}")
        time.sleep(0.5)
        self.request("POST", "/stop")
        device_s = self.machines[0].time_ns / 1e9
        self.assertLessEqual(device_s, time.monotonic() - start + 0.05)

    def test_a_missing_unicorn_is_named_instead_of_dropping_the_request(self):
        def missing(payload, flash):
            raise ModuleNotFoundError("No module named 'unicorn'", name="unicorn")
        self.emu.factory = missing
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        r, body = self.request("POST", "/start", body=b"{}")
        self.assertEqual(r.status, 500)
        self.assertIn("npm run setup:emu", body["error"])

    def test_another_missing_module_is_named_not_taken_for_unicorn(self):
        def missing(payload, flash):
            raise ModuleNotFoundError("No module named 'build_bootstrap'", name="build_bootstrap")
        self.emu.factory = missing
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        with contextlib.redirect_stderr(io.StringIO()) as log:
            r, body = self.request("POST", "/start", body=b"{}")
        self.assertEqual(r.status, 500)
        self.assertIn("build_bootstrap", body["error"])
        self.assertNotIn("npm run setup:emu", body["error"])
        self.assertIn("ModuleNotFoundError", log.getvalue(), "the traceback goes to the log")

    def wait_for(self, check, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not check():
            time.sleep(0.02)
        self.assertTrue(check())

    def test_controls_become_panel_messages(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        for cmd in [{"kind": "button", "index": 9, "down": True}, {"kind": "button", "index": 9, "down": False},
                    {"kind": "encoder", "index": 0, "delta": -1}, {"kind": "knob", "index": 3, "value": 200},
                    {"kind": "pad", "index": 15, "down": True, "velocity": 100}, {"kind": "pad", "index": 15, "down": False},
                    {"kind": "touch", "x": 1023, "y": 0x102, "down": True}, {"kind": "touch", "x": 5, "y": 6},
                    {"kind": "touch", "down": False}, {"kind": "adapter", "plugged": False}]:
            r, body = self.request("POST", "/input", body=json.dumps(cmd).encode())
            self.assertEqual(r.status, 200, body)
        m = self.machines[0]
        self.wait_for(lambda: len(m.sent) == 11)
        self.assertEqual(m.sent, [
            [0, 9, 1, 0, 0], [0, 9, 0, 0, 0], [1, 0, 0, 0xFF, 0], [2, 3, 0, 200, 0],
            [4, 15, 0, 100, 1], [4, 15, 0, 0, 0],
            [0, 0x22, 1, 0, 0], [5, 3, 0xFF, 1, 2], [5, 0, 5, 0, 6], [0, 0x22, 0, 0, 0],
            [7, 0, 0, 0, 0]])

    def test_controls_out_of_range_are_refused(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        for cmd in [{"kind": "knob", "index": 3, "value": 256}, {"kind": "knob", "index": 11, "value": 1},
                    {"kind": "button", "index": 0x40, "down": True}, {"kind": "button", "index": 1, "down": 1},
                    {"kind": "pad", "index": 16, "down": True, "velocity": 100}, {"kind": "touch", "x": 1024, "y": 0},
                    {"kind": "encoder", "index": 0, "delta": 200}, {"kind": "flash"}, []]:
            r, _ = self.request("POST", "/input", body=json.dumps(cmd).encode())
            self.assertEqual(r.status, 400, cmd)
        self.assertEqual(self.machines[0].sent, [])

    def test_sysex_goes_to_the_din_input_and_replies_come_back_as_events(self):
        search = bytes([0xF0, 0x42, 0x50, 0, 0, 0xF7])
        r, body = self.request("POST", "/midi", body=search)
        self.assertEqual(r.status, 400, "nothing runs yet")
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        for bad in [b"", bytes([0x90, 60, 100]), bytes([0xF0, 0x42, 0x80, 0xF7]), search[:-1]]:
            self.assertEqual(self.request("POST", "/midi", body=bad)[0].status, 400, bad)
        self.assertEqual(self.request("POST", "/midi", body=b"\xf0" + bytes(0x10000) + b"\xf7")[0].status, 413)
        seen = self.events(lambda s: s.get("midi"), then=lambda: self.assertEqual(self.request("POST", "/midi", body=search)[0].status, 200))
        self.assertEqual(seen["midi"], ["f0423000012421f7"])
        self.assertEqual(self.machines[0].midi_sent, [search])

    def test_sysex_before_the_main_screen_is_dropped_and_the_status_says_when_it_is_ready(self):
        self.boot_after = 25                 # steps of 20 ms device time, paced to real time
        search = bytes([0xF0, 0x42, 0x50, 0, 0, 0xF7])
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        _, started = self.request("POST", "/start", body=b"{}")
        self.assertEqual(started["booted"], False)
        r, status = self.request("POST", "/midi", body=search)
        self.assertEqual(r.status, 200, "a message into a starting device is lost, it is not an error")
        self.assertEqual(status["booted"], False)
        self.assertEqual(self.emu.midi_dropped, 1)
        self.assertEqual(self.machines[0].midi_sent, [], "nothing reached the firmware")
        self.wait_for(lambda: self.emu.status["booted"])
        seen = self.events(lambda s: s.get("midi"), then=lambda: self.assertEqual(self.request("POST", "/midi", body=search)[0].status, 200))
        self.assertEqual(seen["midi"], ["f0423000012421f7"])
        self.assertEqual(self.machines[0].midi_sent, [search], "only the one after the start")
        self.request("POST", "/start", body=b"{}")
        self.assertEqual(self.emu.status["booted"], False, "a restart starts the wait again")

    def test_the_power_switch_turns_the_device_off_and_on(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        self.request("POST", "/input", body=b'{"kind": "power", "down": true}')
        self.request("POST", "/input", body=b'{"kind": "power", "down": false}')
        time.sleep(0.4)
        self.assertEqual(self.machines[0].sent, [], "a short push does nothing")
        self.request("POST", "/input", body=b'{"kind": "power", "down": true}')
        time.sleep(0.4)
        self.request("POST", "/input", body=b'{"kind": "power", "down": false}')
        self.wait_for(lambda: self.emu.status["state"] == "off")
        # on mains power (the default) the firmware ignores the switch, so the service reports battery first
        self.assertEqual(self.machines[0].sent, [[7, 0, 0, 0, 0], [6, 1, 0, 0, 0], [6, 0, 0, 0, 0]])
        r, body = self.request("POST", "/input", body=b'{"kind": "button", "index": 9, "down": true}')
        self.assertEqual(r.status, 400)
        self.request("POST", "/input", body=b'{"kind": "power", "down": true}')
        self.assertEqual(self.emu.status["state"], "running")
        self.assertEqual(len(self.machines), 2, "switching on boots a fresh device")

    def test_the_device_is_on_mains_power_unless_told_otherwise(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        self.assertIs(self.machines[0].adapter, True, "on battery SOFTWARE UPDATE refuses with Battery Low")
        self.request("POST", "/input", body=b'{"kind": "adapter", "plugged": false}')
        self.request("POST", "/start", body=b"{}")
        self.assertIs(self.machines[1].adapter, False)

    def test_a_firmware_that_stops_talking_to_the_panel_is_reported_as_hung(self):
        self.emu.hang_s = 0.1
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        self.machines[0].hang_after = 3
        seen = self.events(lambda s: any(x["state"] == "hung" for x in s.get("status", [])))
        hung = [x for x in seen["status"] if x["state"] == "hung"][0]
        self.assertIn("hängt", hung["error"])
        self.machines[0].hang_after = None
        seen = self.events(lambda s: any(x["state"] == "running" for x in s.get("status", [])))
        self.assertTrue(any(x["state"] == "running" for x in seen["status"]), "back to running once it talks again")

    def test_a_firmware_assertion_stops_the_device_and_says_where(self):
        self.assert_after = 3
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        self.request("POST", "/start", body=b"{}")
        seen = self.events(lambda s: any(x["state"] == "crashed" for x in s.get("status", [])))
        crashed = [x for x in seen["status"] if x["state"] == "crashed"][0]
        self.assertIn("AM180xSpi.cpp", crashed["error"])


class CardMachine(FakeMachine):
    """A stand-in machine with a card slot: it writes one sector into the card when told to."""

    def __init__(self, payload, flash, assert_after=None):
        super().__init__(payload, flash, assert_after)
        self.card = None
        self.write_at = None
        self.write_lba, self.write_data = 0, bytes(512)

    def insert_card(self, card):
        self.card = card

    def eject_card(self):
        self.card = None

    def run_until(self, seconds):
        super().run_until(seconds)
        if self.card and self.write_at and self.steps == self.write_at:
            self.card.medium.write(self.write_lba, self.write_data)
            self.card.sectors_written += 1


class CardServiceTest(unittest.TestCase):
    """The /sd routes, over a card folder in a temporary directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "sd"
        self.machines = []
        self.opened = []
        self.stopped = False
        self.start_service()

    def start_service(self):
        self.store = CardStore(self.root, opener=self.opened.append)

        def factory(payload, flash):
            m = CardMachine(payload, flash)
            self.machines.append(m)
            return m

        self.server, _, self.emu = serve(0, token=TOKEN, origins={ORIGIN}, emulator=Emulator(factory, power_hold=0.2, cards=self.store))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.stopped = False

    def stop_service(self):
        if self.stopped:
            return
        self.emu.stop()
        self.server.shutdown()
        self.server.server_close()
        self.store.close()
        self.stopped = True

    def tearDown(self):
        self.stop_service()
        for where, dirs, files in os.walk(self.tmp.name):
            for n in dirs:
                os.chmod(os.path.join(where, n), 0o755)
        self.tmp.cleanup()

    request = ServiceTest.request
    events = ServiceTest.events
    wait_for = ServiceTest.wait_for

    @property
    def card(self):
        return self.root / "card"

    def firmware(self, folder=b"hacktribe"):
        """A stand-in firmware: the path literal and the sample file name, where the real one keeps them."""
        data = bytearray(VSB_SIZE)
        path, name = b"KORG/" + folder + b"/\x00", b"e2sSample.all\x00"
        data[0xA5778:0xA5778 + len(path)] = path
        data[0xA57C4:0xA57C4 + len(name)] = name
        return bytes(data)

    def boot(self, firmware=None):
        self.request("POST", "/firmware", body=firmware or self.firmware())
        self.assertEqual(self.request("POST", "/start", body=b"{}")[0].status, 200)

    def test_every_route_needs_the_token_the_page_origin_and_the_host(self):
        for method, path in [("GET", "/sd"), ("POST", "/sd/insert"), ("POST", "/sd/eject"), ("POST", "/sd/open"), ("POST", "/sd/system")]:
            self.assertEqual(self.request(method, path, token=None)[0].status, 401, (method, path))
            self.assertEqual(self.request(method, path, origin="https://example.com")[0].status, 403, (method, path))
            self.assertEqual(self.request(method, path, host="evil.example:80")[0].status, 403, (method, path))
        self.assertEqual(self.request("GET", "/sd")[0].status, 200)
        self.assertEqual(self.request("GET", "/sd/files")[0].status, 404, "the folder is browsed in the file manager")

    def test_without_a_card_folder_the_routes_say_so(self):
        server, _, _ = serve(0, token=TOKEN, origins={ORIGIN}, emulator=Emulator(lambda p, f: FakeMachine(p, f)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.port, kept = server.server_address[1], self.port
        try:
            r, body = self.request("GET", "/sd")
            self.assertEqual(r.status, 404)
            self.assertIn("Kartenordner", body["error"])
            self.assertEqual(self.request("POST", "/sd/insert")[0].status, 404)
        finally:
            server.shutdown()
            server.server_close()
            self.port = kept

    def test_the_card_starts_empty_in_the_layout_the_firmware_expects(self):
        r, state = self.request("GET", "/sd")
        self.assertEqual((state["available"], state["inserted"], state["running"], state["folder"]), (True, False, False, str(self.card)))
        self.assertEqual(sorted(str(p.relative_to(self.card)) for p in self.card.rglob("*")),
                         ["KORG", "KORG/hacktribe", "KORG/hacktribe/Sample", "KORG/hacktribe/System"])
        self.assertEqual([p for p in self.card.rglob("*") if p.is_file()], [])

    def test_the_layout_follows_the_firmware_and_takes_the_unused_one_away(self):
        self.request("POST", "/firmware", body=self.firmware(b"blechtribe"))
        self.assertEqual(self.request("GET", "/sd")[1]["korg"], "blechtribe")
        self.assertEqual(sorted(p.name for p in (self.card / "KORG").iterdir()), ["blechtribe"])
        self.assertTrue((self.card / "KORG" / "blechtribe" / "Sample").is_dir())
        (self.card / "KORG" / "blechtribe" / "Sample" / "e2sSample.all").write_bytes(b"mine")
        self.request("POST", "/firmware", body=self.firmware(b"hacktribe"))
        self.assertEqual(sorted(p.name for p in (self.card / "KORG").iterdir()), ["blechtribe", "hacktribe"], "a folder with a file in it stays")

    def test_open_shows_the_folder_in_the_file_manager(self):
        r, body = self.request("POST", "/sd/open")
        self.assertEqual((r.status, body["folder"]), (200, str(self.card)))
        self.assertEqual(self.opened, [self.card])

    def test_the_update_file_goes_where_the_loaded_firmware_looks_and_the_card_goes_in(self):
        update = bytes(range(256)) * (VSB_SIZE // 256)
        self.assertEqual(self.request("POST", "/sd/system", body=b"\0" * 10)[0].status, 400, "only a whole VSB")
        r, body = self.request("POST", "/sd/system", body=update)
        self.assertEqual((r.status, body["inserted"], body["korg"]), (200, True, "hacktribe"))
        self.assertEqual((self.card / "KORG" / "hacktribe" / "System" / "SYSTEM.VSB").read_bytes(), update)
        self.assertEqual(self.request("GET", "/status")[1]["card"], {"name": "SD-Karte"})
        self.request("POST", "/firmware", body=self.firmware(b"blechtribe"))
        self.request("POST", "/sd/eject")
        newer = bytes(VSB_SIZE)
        r, body = self.request("POST", "/sd/system", body=newer)
        self.assertEqual((r.status, body["korg"]), (200, "blechtribe"))
        self.assertEqual((self.card / "KORG" / "blechtribe" / "System" / "SYSTEM.VSB").read_bytes(), newer)

    def test_an_update_for_another_folder_leaves_the_files_of_the_running_firmware_where_they_are(self):
        (self.card / "KORG" / "hacktribe" / "Sample" / "e2sSample.all").write_bytes(b"my samples")
        self.request("POST", "/firmware", body=self.firmware(b"hacktribe"))
        r, body = self.request("POST", "/sd/system", body=self.firmware(b"blechtribe"))
        self.assertEqual((r.status, body["inserted"], body["korg"]), (200, True, "hacktribe"))
        self.assertFalse((self.card / "KORG" / "blechtribe" / "Sample" / "e2sSample.all").exists(), "no folder is copied behind the user's back")
        self.assertEqual((self.card / "KORG" / "hacktribe" / "Sample" / "e2sSample.all").read_bytes(), b"my samples")

    def test_the_update_file_replaces_the_one_on_a_card_that_is_already_in(self):
        self.boot()
        self.request("POST", "/sd/insert")
        update = bytes(VSB_SIZE - 1) + b"\x07"
        r, body = self.request("POST", "/sd/system", body=update)
        self.assertEqual((r.status, body["inserted"]), (200, True))
        self.assertEqual((self.card / "KORG" / "hacktribe" / "System" / "SYSTEM.VSB").read_bytes(), update)
        with self.machines[0].card.medium.lock:
            v = Volume(self.machines[0].card.medium.data)
            self.assertEqual(v.read("/KORG/hacktribe/System/SYSTEM.VSB"), update, "the running machine sees the new card")
            v.close()

    def test_inserting_copies_the_folder_in_and_write_protects_it(self):
        (self.card / "KORG" / "hacktribe" / "Sample").joinpath("e2sSample.all").write_bytes(b"samples" * 1000)
        (self.card / "readme.txt").write_text("hi")
        r, body = self.request("POST", "/sd/insert")
        self.assertEqual((r.status, body["inserted"]), (200, True))
        self.assertEqual(self.request("GET", "/status")[1]["card"], {"name": "SD-Karte"})
        self.assertFalse(os.access(self.card / "readme.txt", os.W_OK), "the file is read only")
        self.assertFalse(os.access(self.card, os.W_OK), "nothing can be added to the folder")
        with self.assertRaises(PermissionError):
            (self.card / "new.txt").write_text("x")
        self.request("POST", "/sd/eject")
        self.assertTrue(os.access(self.card, os.W_OK))
        (self.card / "new.txt").write_text("x")
        self.assertEqual(self.request("GET", "/sd")[1]["inserted"], False)

    def test_the_card_goes_into_the_machine_with_the_folder_as_its_files(self):
        (self.card / "KORG" / "hacktribe" / "Sample").joinpath("e2sSample.all").write_bytes(b"samples" * 1000)
        self.request("POST", "/sd/insert")
        self.boot()
        m = self.machines[0]
        self.assertIsNotNone(m.card, "the machine got a card")
        self.assertEqual(m.card.medium.sectors, 1024 * 2048)
        with m.card.medium.lock:
            v = Volume(m.card.medium.data)
            self.assertEqual(v.read("/KORG/hacktribe/Sample/e2sSample.all"), b"samples" * 1000)
            v.close()

    def test_what_the_firmware_writes_shows_up_in_the_folder_and_what_it_deletes_goes(self):
        (self.card / "old.txt").write_text("old")
        (self.card / "keep.txt").write_text("keep")
        self.request("POST", "/sd/insert")
        self.boot()
        m = self.machines[0]
        with m.card.medium.lock:
            v = Volume(m.card.medium.data, on_change=m.card.medium.touch)
            v.write("/KORG/hacktribe/Sample/501_kick.wav", b"RIFFdata")
            v.delete("/old.txt")
            v.close()
        self.wait_for(lambda: (self.card / "KORG" / "hacktribe" / "Sample" / "501_kick.wav").exists())
        # The mirror writes the new files first and deletes afterwards; the folder is protected again once it is through.
        protected = lambda: not os.access(self.card / "KORG" / "hacktribe" / "Sample" / "501_kick.wav", os.W_OK)
        self.wait_for(protected)
        self.assertEqual((self.card / "KORG" / "hacktribe" / "Sample" / "501_kick.wav").read_bytes(), b"RIFFdata")
        self.assertFalse((self.card / "old.txt").exists())
        self.assertEqual((self.card / "keep.txt").read_text(), "keep")
        self.assertIsNone(self.request("GET", "/sd")[1]["error"])

    def test_the_card_goes_in_and_out_while_the_device_runs(self):
        self.boot()
        m = self.machines[0]
        self.assertIsNone(m.card)
        (self.card / "a.txt").write_text("a")
        r, body = self.request("POST", "/sd/insert")
        self.assertEqual((r.status, body["inserted"]), (200, True))
        self.assertIsNotNone(m.card, "the running machine got the card")
        self.assertEqual(self.request("GET", "/status")[1]["card"], {"name": "SD-Karte"})
        self.assertFalse(os.access(self.card, os.W_OK))
        r, body = self.request("POST", "/sd/eject")
        self.assertEqual((r.status, body["inserted"]), (200, False))
        self.assertIsNone(m.card, "the machine lost it")
        self.assertTrue(os.access(self.card, os.W_OK))
        self.assertIsNone(self.request("GET", "/status")[1]["card"])

    def test_pulling_the_card_while_the_firmware_wrote_keeps_what_was_written(self):
        self.request("POST", "/sd/insert")
        self.boot()
        m = self.machines[0]
        with m.card.medium.lock:
            v = Volume(m.card.medium.data, on_change=m.card.medium.touch)
            v.write("/half.bin", b"written before the pull")
            v.close()
        self.assertEqual(self.request("POST", "/sd/eject")[0].status, 200)
        self.assertEqual((self.card / "half.bin").read_bytes(), b"written before the pull")

    def test_a_card_right_after_a_firmware_write_is_reported_busy(self):
        self.request("POST", "/sd/insert")
        self.boot()
        m = self.machines[0]
        m.write_lba, m.write_data, m.write_at = 100, bytes(512), m.steps + 2
        self.wait_for(lambda: m.card.sectors_written == 1)
        self.assertTrue(self.request("GET", "/sd")[1]["busy"])
        seen = self.events(lambda s: any(x["written"] == 1 for x in s.get("sd", [])))
        self.assertTrue(any(x["written"] == 1 for x in seen["sd"]), "the page hears about card writes")

    def test_a_folder_too_big_for_the_card_is_refused_and_stays_untouched(self):
        big = self.card / "big.bin"
        with open(big, "wb") as f:
            f.truncate(1100 * 1024 * 1024)
        r, body = self.request("POST", "/sd/insert")
        self.assertEqual(r.status, 400)
        self.assertIn("größer als die Karte", body["error"])
        self.assertTrue(os.access(self.card, os.W_OK))
        self.assertFalse(self.request("GET", "/sd")[1]["inserted"])

    def test_a_service_that_died_with_the_card_in_leaves_a_folder_that_is_free_again(self):
        (self.card / "a.txt").write_text("a")
        self.request("POST", "/sd/insert")
        self.assertFalse(os.access(self.card, os.W_OK))
        self.emu.stop()
        self.server.shutdown()
        self.server.server_close()
        self.store._stop.set()
        self.store._lockfile.close()                   # no eject: as if the process were gone
        self.stopped = True
        self.store = CardStore(self.root)
        self.assertTrue(os.access(self.card, os.W_OK))
        self.assertTrue(os.access(self.card / "a.txt", os.W_OK))
        self.assertFalse(self.store.inserted, "after a restart the card is out")
        self.store.close()


class UnpacedTest(unittest.TestCase):
    """--unthrottled (for tests): as fast as the CPU goes, with the device time in the status."""

    request = ServiceTest.request

    def setUp(self):
        self.machines = []

        def factory(payload, flash):
            self.machines.append(FakeMachine(payload, flash))
            return self.machines[-1]

        self.server, _, self.emu = serve(0, token=TOKEN, origins={ORIGIN}, emulator=Emulator(factory, pace=False))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.emu.stop()
        self.server.shutdown()
        self.server.server_close()

    def test_runs_ahead_of_the_device_and_reports_its_time(self):
        self.request("POST", "/firmware", body=bytes(VSB_SIZE))
        start = time.monotonic()
        self.request("POST", "/start", body=b"{}")
        deadline = time.monotonic() + 3
        while self.emu.status["device_ms"] < 2000 and time.monotonic() < deadline:
            time.sleep(0.01)
        wall = time.monotonic() - start
        self.request("POST", "/stop")
        self.assertGreaterEqual(self.emu.status["device_ms"], 2000, "two device seconds passed")
        self.assertLess(wall, 1.5, f"in {wall:.2f} s of wall time: not paced")


class SysexReaderTest(unittest.TestCase):
    def test_whole_messages_across_chunks_without_clock_or_notes(self):
        r = SysexReader()
        self.assertEqual(r.feed(bytes([0xF8, 0x90, 60, 100, 0xF0, 0x42])), [])
        self.assertEqual(r.feed(bytes([0x50, 0xF8, 0x01, 0xF7, 0xFE])), [bytes([0xF0, 0x42, 0x50, 0x01, 0xF7])])

    def test_a_message_cut_off_by_another_status_is_dropped(self):
        r = SysexReader()
        self.assertEqual(r.feed(bytes([0xF0, 0x42, 0x90, 60, 0xF7, 0xF0, 0x7E, 0xF7])), [bytes([0xF0, 0x7E, 0xF7])])


class RestartAfterUpdateTest(unittest.TestCase):
    """SOFTWARE UPDATE rewrites the firmware region of the flash; the next start runs that, not the file loaded first."""

    def setUp(self):
        self.machines = []

        def factory(payload, flash):
            m = FakeMachine(payload, flash)
            m.flash = types.SimpleNamespace(mem=bytearray(0x1000000), dirty=False)
            m.flash.mem[FIRMWARE_AT:FIRMWARE_AT + len(payload)] = payload      # what machine.py does
            self.machines.append(m)
            return m

        self.server, _, self.emu = serve(0, token=TOKEN, origins={ORIGIN}, emulator=Emulator(factory, pace=False))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.real_identify = server_module.identify
        server_module.identify = lambda payload: types.SimpleNamespace(build="hacktribe")

    def tearDown(self):
        server_module.identify = self.real_identify
        self.emu.stop()
        self.server.shutdown()
        self.server.server_close()

    request = ServiceTest.request

    def run_update(self, written):
        old = bytes([1]) * VSB_SIZE
        self.request("POST", "/firmware", body=old)
        self.request("POST", "/start", body=b"{}")
        self.emu.stop()
        flash = self.machines[0].flash.mem
        flash[FIRMWARE_AT:FIRMWARE_AT + 0x200000] = written
        return old

    def test_the_machine_starts_with_its_image_in_the_flash(self):
        old = bytes([1]) * VSB_SIZE
        self.request("POST", "/firmware", body=old)
        self.request("POST", "/start", body=b"{}")
        self.assertEqual(bytes(self.machines[0].flash.mem[FIRMWARE_AT:FIRMWARE_AT + 0x200000]), old[0x100:])

    def test_a_restart_after_an_update_runs_the_new_image_and_says_which(self):
        old = self.run_update(bytes([2]) * 0x200000)
        r, status = self.request("POST", "/start", body=b"{}")
        self.assertEqual(r.status, 200)
        self.assertEqual(self.machines[1].payload, bytes([2]) * 0x200000)
        self.assertEqual(status["firmware"]["sha256"], hashlib.sha256(bytes([2]) * 0x200000).hexdigest())
        self.assertNotEqual(status["firmware"]["sha256"], hashlib.sha256(old[0x100:]).hexdigest())

    def test_a_restart_without_an_update_runs_the_same_image(self):
        old = self.run_update(bytes([1]) * 0x200000)
        self.request("POST", "/start", body=b"{}")
        self.assertEqual(self.machines[1].payload, old[0x100:])

    def test_a_region_that_is_no_image_is_not_taken(self):
        server_module.identify = lambda payload: (_ for _ in ()).throw(ProfileError("nope"))
        old = self.run_update(b"\xff" * 0x200000)
        self.request("POST", "/start", body=b"{}")
        self.assertEqual(self.machines[1].payload, old[0x100:], "a half-written update leaves the loaded file in charge")

    def test_loading_a_file_beats_an_update_of_the_run_before(self):
        self.run_update(bytes([2]) * 0x200000)
        mine = bytes([3]) * VSB_SIZE
        self.request("POST", "/firmware", body=mine)
        self.request("POST", "/start", body=b"{}")
        self.assertEqual(self.machines[1].payload, mine[0x100:])


if __name__ == "__main__":
    unittest.main()
