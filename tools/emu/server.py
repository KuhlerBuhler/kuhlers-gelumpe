# SPDX-License-Identifier: GPL-2.0-only
"""Local service that runs the emulated Electribe for the editor page.

The page uploads the user's own VSB, starts
the firmware and receives the display as a stream of server-sent events.
Only the Python standard library is used. The service listens on 127.0.0.1
(GELUMPE_HOST or --host, a container needs 0.0.0.0) and answers only requests
that carry the token printed at start and come from an allowed origin, because
any web page in the browser can reach 127.0.0.1.
"""

import _thread
import argparse
import base64
import hashlib
import hmac
import json
import os
import queue
import secrets
import shutil
import signal
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cardstore import CardError, CardStore, card_folder, default_dir  # noqa: E402
from firmware import ProfileError, hardware_of_head, identify, is_synth  # noqa: E402
from flashstore import FlashError, FlashStore, default_dir as default_flash_dir  # noqa: E402
import lifetime  # noqa: E402
from lcd import LcdResponse, taus  # noqa: E402
from sdcard import SDCard  # noqa: E402

MISSING_UNICORN = "Unicorn fehlt in diesem Python. Einmal npm run setup:emu ausführen, dann npm start neu starten."


def import_failure(error):
    """The answer to an ImportError: the setup hint only when Unicorn itself is missing. Any other module is named and its
    traceback goes to stderr (the app's ~/.gelumpe/emu.log), so a module the frozen service lacks is not taken for Unicorn."""
    if (error.name or "").split(".")[0] == "unicorn":
        return MISSING_UNICORN
    traceback.print_exception(error, file=sys.stderr)
    sys.stderr.flush()
    return f"Dem Emulator fehlt ein Modul: {error.name or error}"
VSB_SIZE = 0x200100
SYNTH_FLASH_FILE = "flash-synth.bin"   # the blue Electribe's user data, kept apart from flash.bin; Hacktribe for the blue uses it too
FLASH_SIZE = 0x1000000
FIRMWARE_AT = 0x20000       # where the flash holds the firmware image (machine.FIRMWARE_AT)
STEP_S = 0.02               # device time run between display checks
UNPACED_STATUS_NS = 20_000_000   # without pacing the status carries the device time this often
TOUCH_BUTTON = 0x22
POWER_HOLD_S = 2.0          # the device switches off only after the switch is held this long
MIDI_LIMIT = 0x10000        # a pattern dump is 18733 bytes, the whole MFX table in one write 59894
# A running firmware refreshes the panel LEDs about 265 times a second; a hang
# in a task or an interrupt stops that at once (docs/messungen/2026-10-10-haenger.md).
HANG_S = 2.0


def hardware_of(vsb):
    """"blue" or "red": the Electribe a VSB runs on. The head says it, also for Hacktribe for the blue (Sampler code)."""
    return "blue" if is_synth(vsb[0x100:]) or hardware_of_head(vsb) == "blue" else "red"


def blank_for(hardware, payload):
    """The flash a firmware starts from when there is none yet: None lets the machine choose by build, which is right
    except for Sampler code on the blue, which needs the blue's user-data mark (docs/ideen/65-blech-hacktribe-blau.md)."""
    if hardware != "blue" or payload is None or is_synth(payload):
        return None
    from machine import hardware_flash
    return bytes(hardware_flash("blue"))


def folder_of(vsb):
    """The folder below KORG/ the firmware in this VSB (header and payload) keeps its files in."""
    return card_folder(vsb)


class Conflict(Exception):
    """Fine request, wrong moment: the answer is 409 and the message says what to do first."""


def panel_message(cmd):
    """One control used on the page, as the 5-byte panel message (data/panel.mjs)."""
    kind = cmd.get("kind")

    def number(key, low, high):
        v = cmd.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or not low <= v <= high:
            raise ValueError(f"{kind}: {key} muss zwischen {low} und {high} liegen.")
        return v

    def flag(key):
        v = cmd.get(key)
        if not isinstance(v, bool):
            raise ValueError(f"{kind}: {key} muss ja oder nein sein.")
        return 1 if v else 0

    if kind == "button":
        return [[0x00, number("index", 0, 0x21), flag("down"), 0, 0]]
    if kind == "encoder":
        return [[0x01, number("index", 0, 4), 0, number("delta", -16, 16) & 0xFF, 0]]
    if kind == "knob":
        return [[0x02, number("index", 0, 10), 0, number("value", 0, 255), 0]]
    if kind == "pad":
        down = flag("down")
        return [[0x04, number("index", 0, 15), 0, number("velocity", 1, 127) if down else 0, down]]
    if kind == "touch":
        if cmd.get("down") is False:
            return [[0x00, TOUCH_BUTTON, 0, 0, 0]]
        x, y = number("x", 0, 1023), number("y", 0, 1023)
        xy = [0x05, x >> 8, x & 0xFF, y >> 8, y & 0xFF]
        return [[0x00, TOUCH_BUTTON, 1, 0, 0], xy] if cmd.get("down") else [xy]
    if kind == "power":
        return [[0x06, flag("down"), 0, 0, 0]]
    if kind == "adapter":
        return [[0x07, flag("plugged"), 0, 0, 0]]
    raise ValueError("Unbekanntes Bedienelement.")


def real_machine(payload, flash):
    from machine import Machine
    return Machine(payload, flash)


def real_check(base, patched, flash, allow, allow_code=(), boot_flash=None, progress=None, quick=False):
    from check import check
    return check(base, patched, flash, allow, allow_code, progress=progress, quick=quick, boot_flash=boot_flash)


class Emulator:
    """One emulated device, run on its own thread, paced to device time."""

    def __init__(self, factory=real_machine, power_hold=POWER_HOLD_S, checker=real_check, hang_s=HANG_S, cards=None, lcd_tau=(None, None), flash_store=None, pace=True):
        self.factory = factory
        self.pace = pace                    # False: as fast as the CPU goes (tests), device time is then what a client waits on
        self.lcd_tau = taus(*lcd_tau)         # seconds a pixel takes to follow, dark and clear (lcd.py)
        self.cards = cards
        self.flash_store = flash_store      # the flash file the device boots from and writes back to
        self.card = None                    # the SDCard of the running machine
        self.card_folder = None             # KORG/<this>/ is where the loaded firmware keeps its files
        self.build, self.build_reason = None, None     # which build the loaded firmware is (firmware.py)
        self.hang_s = hang_s
        self.checker = checker
        self.checking = threading.Lock()
        self.check_progress = {"state": "idle"}     # GET /check/progress: the last snapshot of check.py's progress, see progress.py
        self.power_hold = power_hold
        self.power_timer = None
        self.firmware = None
        self.flash = None
        self.machine = None
        self.ran = None                     # (machine, payload) of the last run, to see whether SOFTWARE UPDATE rewrote the firmware
        self.thread = None
        self.running = False
        self.lock = threading.Lock()
        self.card_lock = threading.RLock()  # starting the device and changing a card exclude each other
        self.clients = []
        self.shade = None                   # the display levels last published, as the page gets them
        self.inputs = queue.Queue()
        self.midi_in = queue.Queue()
        self.card_ops = queue.Queue()       # card changes for the running machine
        self.adapter = True                 # on mains power, as a device on the desk; on battery SOFTWARE UPDATE refuses ("Battery Low")
        self.midi_dropped = 0               # SysEx that came before the device had reached the main screen
        self.status = {"state": "empty", "booted": False, "speed": None, "device_ms": 0, "error": None, "card": self.card_summary(), "firmware": None}

    # ---- events --------------------------------------------------------------
    def subscribe(self):
        q = queue.Queue(maxsize=256)
        with self.lock:
            self.clients.append(q)
        q.put(("status", self.status))
        m = self.machine
        if m is not None:
            q.put(("display", self._display(m)))
            if self.shade is not None:
                q.put(("shade", self.shade))
            q.put(("leds", dict(m.leds)))
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def publish(self, kind, data):
        with self.lock:
            for q in self.clients:
                try:
                    q.put_nowait((kind, data))
                except queue.Full:
                    pass                      # a slow page skips frames

    def set_status(self, **changes):
        self.status = {**self.status, **changes}
        self.publish("status", self.status)

    # ---- card ----------------------------------------------------------------
    def card_summary(self):
        """The inserted card as the page shows it in the status, or None."""
        if self.cards is None or not self.cards.inserted:
            return None
        return {"name": "SD-Karte"}

    @property
    def live(self):
        return self.status["state"] in ("running", "hung")

    def card_busy(self):
        """The firmware wrote to the inserted card a moment ago, so the folder may be between two writes."""
        card = self.card
        return bool(self.live and card is not None and card.medium.busy())

    def insert_card(self, inserted):
        """The card goes in or comes out, also while the Electribe runs: the firmware polls the card-detect
        input (GPIO 4.1) and notices on its own. The change reaches the machine between two steps."""
        with self.card_lock:
            if inserted:
                self.cards.insert(self.card_folder)
                self._card_change(lambda m: self._plug(m, SDCard(self.cards.image)))
            else:
                self._card_change(lambda m: self._plug(m, None))
                self.cards.eject()
        self.set_status(card=self.card_summary())

    def _plug(self, m, card):
        self.card = card
        if card is None:
            m.eject_card()
        else:
            m.insert_card(card)

    def _card_change(self, change):
        """Apply `change(machine)` on the machine's own thread while it runs, directly when it does not."""
        if not self.live or self.machine is None:
            self.card = None
            return
        done = threading.Event()
        self.card_ops.put((change, done))
        if not done.wait(timeout=5) and self.running:
            raise Conflict("Die Electribe hat die Karte nicht übernommen. Gleich noch einmal.")

    def put_system(self, data):
        """The update file onto the card of the loaded firmware, and the card in: the way an update is tested.
        Other card folders are never touched: whoever wants the files of one firmware in the folder of another copies them."""
        if self.cards is None:
            raise Conflict("Dieser Dienst hat keinen Kartenordner.")
        if len(data) != VSB_SIZE:
            raise ValueError(f"Eine VSB hat genau {VSB_SIZE} Byte, diese hat {len(data)}.")
        with self.card_lock:
            if self.cards.inserted:
                self.insert_card(False)
            self.cards.put_system(self.card_folder, data)
            self.insert_card(True)

    def sd_state(self):
        c = self.cards
        if c is None:
            return {"available": False}
        card = self.card if self.live else None
        return {"available": True, "folder": str(c.dir), "korg": self.card_folder or "hacktribe",
                "inserted": c.inserted, "running": self.live, "busy": self.card_busy(), "error": c.sync_error,
                "stats": {"read": card.sectors_read, "written": card.sectors_written} if card else None}

    def save_cards(self):
        if self.cards is not None:
            try:
                self.cards.flush()
            except OSError as error:
                self.set_status(error=f"Die Karte konnte nicht gespeichert werden: {error.strerror}")

    @staticmethod
    def _display(m):
        shown = m.shown() if hasattr(m, "shown") else bytes(b for row in m.fb for b in row)
        return base64.b64encode(shown).decode("ascii")

    def publish_shade(self, lcd):
        """The display as it looks, one level (0 clear to 15 dark) per pixel, row by row (lcd.py)."""
        self.shade = base64.b64encode(lcd.shades()).decode("ascii")
        self.publish("shade", self.shade)

    # ---- control -------------------------------------------------------------
    def load_firmware(self, data):
        if len(data) != VSB_SIZE:
            raise ValueError(f"Eine VSB hat genau {VSB_SIZE} Byte, diese hat {len(data)}.")
        self.stop()
        self.ran = None                     # what an earlier run did to the flash does not apply to this file
        self.firmware = bytes(data)
        try:
            self.build, self.build_reason = identify(self.firmware[0x100:]).build, None
        except ProfileError as error:
            self.build, self.build_reason = None, str(error)
        self.card_folder = folder_of(self.firmware)
        if self.cards is not None:
            self.cards.ensure_layout(self.card_folder)
        self.set_status(state="loaded", error=None, firmware=self.firmware_summary())

    def firmware_summary(self):
        """What the page is told about the loaded firmware: which build it is (firmware.py), so that it can say
        which functions the build has, and the card folder it uses. An image the emulator does not know has
        no build; it is not refused here, starting it says why."""
        return {"build": self.build, "folder": self.card_folder, "reason": self.build_reason,
                "sha256": hashlib.sha256(self.firmware[0x100:]).hexdigest()}

    def hardware(self):
        """"blue" or "red": the Electribe the loaded firmware runs on."""
        if self.firmware is None:
            return "red"
        return "blue" if self.build == "synth" or hardware_of(self.firmware) == "blue" else "red"

    def flash_file(self, hardware=None):
        """The flash file of the hardware (default: the loaded firmware's): the blue keeps its user data apart from the red's."""
        if self.flash_store is None or (hardware or self.hardware()) != "blue":
            return self.flash_store
        return self.flash_store.other(SYNTH_FLASH_FILE)

    def load_flash(self, data):
        """Replace the flash (tests and tools; the page offers no import). With a flash file, it is the new content of that file."""
        if len(data) != FLASH_SIZE:
            raise ValueError(f"Ein Flash-Abbild hat genau 16 MiB, dieses hat {len(data)} Byte.")
        self.stop()
        if self.flash_store is not None:
            self.flash_file().save(data)
        else:
            self.flash = bytes(data)
        self.publish("flash", {"loaded": True})

    def current_flash(self, hardware=None, payload=None):
        """What the device boots from: the flash file, else an uploaded image, else None (erased). `hardware` and
        `payload` instead of the loaded firmware's: for a check of another file."""
        hardware = hardware or self.hardware()
        if self.flash_store is None:
            data = self.flash
        else:
            try:
                data = self.flash_file(hardware).load()
            except FlashError as error:
                raise ValueError(str(error)) from None
        if payload is None and self.firmware is not None:
            payload = self.firmware[0x100:]
        return data if data is not None else blank_for(hardware, payload)

    def save_flash(self, m):
        """Write the flash file back if the firmware changed the flash."""
        flash = getattr(m, "flash", None)
        if self.flash_store is None or flash is None or not getattr(flash, "dirty", False):
            return
        flash.dirty = False
        try:
            self.flash_file().save(flash.mem)
        except OSError as error:
            flash.dirty = True
            self.set_status(error=f"Der Flash konnte nicht gespeichert werden: {error.strerror}")

    def adopt_update(self):
        """A restart runs what the flash holds, like the device: when SOFTWARE UPDATE rewrote the firmware region
        during the last run and the result is an image the emulator knows, that is the firmware now. The header
        stays, only the payload is read."""
        if self.ran is None:
            return
        m, payload = self.ran
        self.ran = None
        flash = getattr(m, "flash", None)
        if flash is None:
            return
        region = bytes(flash.mem[FIRMWARE_AT:FIRMWARE_AT + len(payload)])
        if region == payload:
            return
        try:
            identify(region)
        except ProfileError:
            return                          # an update that did not finish leaves no image to start
        self.firmware = self.firmware[:0x100] + region
        self.card_folder = card_folder(self.firmware)
        if self.cards is not None:
            self.cards.ensure_layout(self.card_folder)
        self.set_status(firmware=self.firmware_summary())

    def start(self):
        if self.firmware is None:
            raise ValueError("Erst eine VSB laden.")
        self.stop()
        self.adopt_update()
        with self.card_lock:
            self.machine = self.factory(self.firmware[0x100:], self.current_flash())
            self.ran = (self.machine, self.firmware[0x100:])
            self.card = None
            if self.cards is not None and self.cards.inserted:
                self.card = SDCard(self.cards.image)
                self.machine.insert_card(self.card)
            self.machine.adapter = self.adapter
            self.inputs = queue.Queue()
            self.midi_in = queue.Queue()
            self.card_ops = queue.Queue()
            self.running = True
            self.thread = threading.Thread(target=self._run, args=(self.machine,), daemon=True)
            self.thread.start()
            self.midi_dropped = 0
            # booted: the firmware has shown its main screen (machine.py). Until then nothing sends it MIDI,
            # as on the device, where nothing can; the page reads this flag from the status.
            self.set_status(state="running", booted=getattr(self.machine, "booted", True), error=None, device_ms=0, speed=None)

    def stop(self):
        self.running = False
        t = self.thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=5)
        self.thread = None
        if self.status["state"] == "running":
            self.set_status(state="stopped")
        self.save_cards()

    def input(self, cmd):
        messages = panel_message(cmd)
        if cmd["kind"] == "adapter":
            self.adapter = cmd["plugged"]
        if self.status["state"] != "running":
            if cmd["kind"] == "power" and cmd["down"] and self.firmware is not None:
                self.start()                   # pressing the switch of a switched-off device starts it
                return
            if cmd["kind"] != "adapter":
                raise ValueError("Die Electribe läuft nicht.")
            return
        if cmd["kind"] == "power":
            # A short push does nothing on the device; the panel reports the
            # switch only once it has been held (measure:2026-10-08/panel-bedienung).
            if cmd["down"]:
                if self.power_timer is None:
                    self.power_timer = threading.Timer(self.power_hold, self.switch_off, args=(messages[0],))
                    self.power_timer.daemon = True
                    self.power_timer.start()
                return
            timer, self.power_timer = self.power_timer, None
            if timer is None or timer.is_alive():
                if timer is not None: timer.cancel()
                return
        for msg in messages:
            self.inputs.put(msg)

    def switch_off(self, held):
        # On mains power the firmware ignores the switch (measured in the emulator: still powered 4 s
        # after the hold). The page has no adapter to pull, so the service reports battery first; the
        # firmware then shuts down as it does on battery, saving what it saves there.
        if self.adapter:
            self.inputs.put(panel_message({"kind": "adapter", "plugged": False})[0])
        self.inputs.put(held)

    def check(self, pair, allow, allow_code=(), quick=False, hardware=None):
        """Export check (check.py) of the original VSB and its patched copy, sent one after the other. The start scenarios
        boot from the flash of the hardware the original runs on (by its head, or `hardware`), the user's own; the cases of
        the patches run on a blank flash of that hardware, as in CI: they expect Init patterns, not the user's.
        One check at a time; `quick` only the start scenarios."""
        if len(pair) != 2 * VSB_SIZE:
            raise ValueError(f"Die Prüfung braucht Original und Kopie, je {VSB_SIZE} Byte.")
        if not self.checking.acquire(blocking=False):
            raise ValueError("Es läuft schon eine Prüfung.")
        self.check_progress = {"state": "running"}
        try:
            hardware, payload = hardware or hardware_of(pair[:VSB_SIZE]), bytes(pair[0x100:VSB_SIZE])
            result = self.checker(bytes(pair[:VSB_SIZE]), bytes(pair[VSB_SIZE:]), blank_for(hardware, payload), allow, allow_code,
                                  boot_flash=self.current_flash(hardware, payload),
                                  progress=lambda snapshot: setattr(self, "check_progress", {"state": "running", **snapshot}),
                                  **({"quick": True} if quick else {}))
            self.check_progress = {**self.check_progress, "state": "done"}
            return result
        except BaseException:
            self.check_progress = {**self.check_progress, "state": "failed"}
            raise
        finally:
            self.checking.release()

    def midi(self, data):
        """One SysEx message into the DIN input of the running device. False when the device has not
        reached its main screen yet and the message was dropped (the firmware asserts on MIDI that early)."""
        if len(data) < 2 or data[0] != 0xF0 or data[-1] != 0xF7 or any(b & 0x80 for b in data[1:-1]):
            raise ValueError("Nur eine vollständige SysEx-Nachricht, F0 bis F7.")
        if self.status["state"] != "running":
            raise ValueError("Die Electribe läuft nicht.")
        if not self.status["booted"]:
            self.midi_dropped += 1          # a message into a device that has not started is lost, it is not held back
            return False
        self.midi_in.put(bytes(data))
        return True

    def _run(self, m):
        wall0, dev0 = time.monotonic(), m.time_ns
        last_fb, last_leds, last_report, report_ns = None, None, wall0, dev0
        status_ns = dev0
        alive_count, alive_ns = getattr(m, "panel_count", None), dev0
        last_sd = None
        lcd, self.shade = LcdResponse(*self.lcd_tau), None
        try:
            while self.running and m is self.machine:
                while not self.inputs.empty():
                    m.send(self.inputs.get_nowait())
                while not self.midi_in.empty():
                    m.midi(self.midi_in.get_nowait())
                while not self.card_ops.empty():
                    change, done = self.card_ops.get_nowait()
                    change(m)
                    done.set()
                m.run_until(m.time_ns / 1e9 + STEP_S)
                for msg in m.midi_out():
                    self.publish("midi", msg.hex())
                if not self.status["booted"] and getattr(m, "booted", True):
                    self.set_status(booted=True)
                if not getattr(m, "powered", True):
                    self.running = False
                    self.publish("display", self._display(m))
                    lcd.settle(m.fb, getattr(m, "lcd_reverse", False))
                    self.publish_shade(lcd)
                    self.publish("leds", {})
                    self.set_status(state="off", error=None)
                    return
                fb = self._display(m)
                if fb != last_fb:
                    self.publish("display", fb)
                    last_fb = fb
                if lcd.update(m.fb, m.time_ns, getattr(m, "lcd_reverse", False)):
                    self.publish_shade(lcd)
                leds = sorted(m.leds.items())
                if leds != last_leds:
                    self.publish("leds", dict(leds))
                    last_leds = leds
                card = self.card
                if card is not None:
                    sd = (card.sectors_read, card.sectors_written, bool(card.medium.busy()))
                    if sd != last_sd:
                        last_sd = sd
                        self.publish("sd", {"read": sd[0], "written": sd[1], "busy": sd[2]})
                count = getattr(m, "panel_count", None)
                if count != alive_count:
                    alive_count, alive_ns = count, m.time_ns
                    if self.status["state"] == "hung":
                        self.set_status(state="running", error=None)
                elif count is not None and m.time_ns - alive_ns > self.hang_s * 1e9 and self.status["state"] == "running":
                    self.set_status(state="hung", error=f"Die Firmware schickt seit {self.hang_s:g} s nichts mehr ans Bedienfeld; sie hängt vermutlich.")
                if m.asserts:
                    a = m.asserts[0]
                    self.running = False
                    self.set_status(state="crashed", error=f"Firmware-Assertion in {a['file']}, Zeile {a['line']}.")
                    return
                if self.pace:
                    ahead = (m.time_ns - dev0) / 1e9 - (time.monotonic() - wall0)
                    if ahead > 0:
                        time.sleep(ahead)          # never faster than the device
                    elif ahead < -0.1:
                        wall0, dev0 = time.monotonic(), m.time_ns   # behind: carry on in real time, no catching up
                elif m.time_ns - status_ns >= UNPACED_STATUS_NS:    # a test waits for device time, so it is told often
                    self.set_status(device_ms=round(m.time_ns / 1e6))
                    status_ns = m.time_ns
                now = time.monotonic()
                if now - last_report >= 1:
                    self.save_flash(m)
                    speed = (m.time_ns - report_ns) / 1e9 / (now - last_report)
                    self.set_status(device_ms=round(m.time_ns / 1e6), speed=round(speed, 2))
                    last_report, report_ns = now, m.time_ns
        except Exception as error:             # the firmware or a model failed
            self.running = False
            self.set_status(state="crashed", error=f"Emulator angehalten: {error}")
        finally:
            self.save_cards()                   # a card is written back whenever the device stops
            self.save_flash(m)


def make_handler(emu, token, origins):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        # ---- checks ----------------------------------------------------------
        def _origin(self):
            return self.headers.get("Origin")

        def _allowed(self, need_token=True):
            port = self.server.server_address[1]
            if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                return self._fail(403, "Falscher Host.")
            origin = self._origin()
            if origin is not None and origin not in origins:
                return self._fail(403, "Diese Seite darf den Emulator nicht steuern.")
            if need_token:
                given = parse_qs(urlparse(self.path).query).get("token", [""])[0] or self.headers.get("X-Emu-Token", "")
                if not hmac.compare_digest(given.encode(), token.encode()):
                    return self._fail(401, "Schlüssel fehlt oder ist falsch.")
            return True

        def _cors(self):
            origin = self._origin()
            if origin in origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def _send(self, code, body, ctype="application/json", headers=None):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self._cors()
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _fail(self, code, message):
            self._send(code, {"error": message})
            return False

        def _body(self, limit):
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = -1
            if n < 0 or n > limit:
                self.close_connection = True       # the unread body would be parsed as the next request
                self._fail(413, "Die Datei ist zu groß.")
                return None
            return self.rfile.read(n)

        # ---- routes ----------------------------------------------------------
        def do_OPTIONS(self):
            if not self._allowed(need_token=False):
                return
            self.send_response(204)
            self._cors()
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Emu-Token")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Content-Length", "0")
            self.end_headers()

        # ---- virtual SD card ---------------------------------------------------
        def _sd(self, method, path, query):
            """Everything under /sd. Errors of the card layers become the status codes a page can act on."""
            try:
                self._sd_route(method, path)
            except Conflict as error:
                self._fail(409, str(error))
            except (CardError, ValueError, json.JSONDecodeError) as error:
                self._fail(400, str(error))

        def _sd_route(self, method, path):
            cards = emu.cards
            if cards is None:
                return self._fail(404, "Dieser Dienst hat keinen Kartenordner.")
            if method == "GET" and path == "/sd":
                return self._send(200, emu.sd_state())
            if method == "POST" and path in ("/sd/insert", "/sd/eject"):
                if self._body(1024) is None:
                    return
                emu.insert_card(path == "/sd/insert")
                return self._send(200, emu.sd_state())
            if method == "POST" and path == "/sd/system":
                body = self._body(VSB_SIZE)
                if body is None:
                    return
                emu.put_system(body)
                return self._send(200, emu.sd_state())
            if method == "POST" and path == "/sd/open":
                if self._body(1024) is None:
                    return
                return self._send(200, {"folder": cards.open_folder()})
            self._fail(404, "Unbekannter Pfad.")

        def do_GET(self):
            if not self._allowed():
                return
            path = urlparse(self.path).path
            if path == "/sd" or path.startswith("/sd/"):
                return self._sd("GET", path, parse_qs(urlparse(self.path).query))
            if path == "/status":
                return self._send(200, emu.status)
            if path == "/events":
                return self._events()
            if path == "/check/progress":
                return self._send(200, emu.check_progress)
            self._fail(404, "Unbekannter Pfad.")

        def do_POST(self):
            if not self._allowed():
                return
            path = urlparse(self.path).path
            if path.startswith("/sd/"):
                return self._sd("POST", path, parse_qs(urlparse(self.path).query))
            try:
                if path == "/firmware":
                    body = self._body(VSB_SIZE)
                    if body is None: return
                    emu.load_firmware(body)
                elif path == "/flash":
                    body = self._body(FLASH_SIZE)
                    if body is None: return
                    emu.load_flash(body)
                elif path == "/start":
                    if self._body(1024) is None: return
                    emu.start()
                elif path == "/stop":
                    if self._body(1024) is None: return
                    emu.stop()
                elif path == "/midi":
                    body = self._body(MIDI_LIMIT)
                    if body is None: return
                    emu.midi(body)
                elif path == "/check":
                    body = self._body(2 * VSB_SIZE)
                    if body is None: return
                    query = parse_qs(urlparse(self.path).query)
                    spans = {key: [tuple(int(x, 0) for x in s.split(":")) for s in query.get(key, [""])[0].split(",") if s]
                             for key in ("allow", "allowCode")}
                    if any(len(a) != 2 for lst in spans.values() for a in lst):
                        raise ValueError("allow und allowCode sind Listen aus Stelle:Länge.")
                    hardware = query.get("hardware", [None])[0]
                    if hardware not in (None, "red", "blue"):
                        raise ValueError("hardware ist red oder blue.")
                    return self._send(200, emu.check(body, spans["allow"], spans["allowCode"], quick=query.get("quick", [""])[0] == "1", hardware=hardware))
                elif path == "/input":
                    body = self._body(1024)
                    if body is None: return
                    cmd = json.loads(body or b"{}")
                    if not isinstance(cmd, dict):
                        raise ValueError("Eine Eingabe ist ein Objekt.")
                    emu.input(cmd)
                else:
                    return self._fail(404, "Unbekannter Pfad.")
            except (ValueError, json.JSONDecodeError) as error:
                return self._fail(400, str(error))
            except ImportError as error:
                return self._fail(500, import_failure(error))
            except Exception as error:
                return self._fail(500, f"Emulator konnte nicht starten: {error}")
            self._send(200, emu.status)

        def _events(self):
            q = emu.subscribe()                  # before the headers: a client that has them is already on the list and misses no event
            try:
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                while True:
                    try:
                        kind, data = q.get(timeout=15)
                        chunk = f"event: {kind}\ndata: {json.dumps(data)}\n\n"
                    except queue.Empty:
                        chunk = ": keep-alive\n\n"
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                emu.unsubscribe(q)
                self.close_connection = True

    return Handler


def serve(port=8740, token=None, origins=(), emulator=None, host="127.0.0.1"):
    token = token or secrets.token_urlsafe(16)
    emu = emulator or Emulator()
    server = ThreadingHTTPServer((host, port), make_handler(emu, token, set(origins)))
    server.daemon_threads = True
    return server, token, emu


def watch_parent(pids):
    """Stop this service when any of the processes that started it (the desktop app, a test run, the
    launcher script) is gone, however it ended."""
    def stop():
        # Both end in the KeyboardInterrupt path of main(), which saves card and flash. SIGTERM has a
        # handler of ours; interrupt_main does nothing when the parent started us with SIGINT ignored.
        os.kill(os.getpid(), signal.SIGTERM) if sys.platform != "win32" else _thread.interrupt_main()

    lifetime.watch(pids, stop)


HARD_EXIT_S = 10


def inside_temp(path):
    """Whether `path` is a folder below the system's temporary folder, not that folder itself."""
    return Path(tempfile.gettempdir()).resolve() in Path(path).resolve().parents


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8740)
    parser.add_argument("--host", default=os.environ.get("GELUMPE_HOST", "127.0.0.1"),
                        help="address to listen on; 0.0.0.0 in a container, whose published port reaches "
                             "this address and not 127.0.0.1. Default GELUMPE_HOST, else 127.0.0.1")
    parser.add_argument("--page", default="http://127.0.0.1:8737",
                        help="origin of the editor page allowed to use the emulator")
    parser.add_argument("--allow-origin", action="append", default=[])
    parser.add_argument("--sd-dir", type=Path,
                        help="where the virtual SD card lives; default GELUMPE_SD_DIR, else ~/.gelumpe/sd")
    parser.add_argument("--flash-dir", type=Path,
                        help="where the emulated flash lives (flash.bin); default GELUMPE_FLASH_DIR, else flash/ next to the card folder")
    parser.add_argument("--lcd-tau-on", type=float, metavar="SECONDS",
                        help="time constant of a display pixel turning dark; default E2_LCD_TAU_ON, else lcd.py")
    parser.add_argument("--lcd-tau-off", type=float, metavar="SECONDS",
                        help="time constant of a display pixel turning clear; default E2_LCD_TAU_OFF, else lcd.py")
    parser.add_argument("--unthrottled", action="store_true",
                        help="for tests: run as fast as the CPU goes instead of in device time; the status then reports the device time every 20 ms of it")
    parser.add_argument("--parent-pid", type=int, action="append", default=[],
                        help="stop when this process ends, however it ended; the desktop app and the tests pass their own. Repeatable")
    parser.add_argument("--ephemeral", action="store_true",
                        help="for tests: delete the card folder and the flash folder when the service ends. "
                             "Needs --sd-dir inside the temporary folder; the flash then lives in <sd-dir>/flash")
    args = parser.parse_args()
    try:
        lcd_tau = taus(args.lcd_tau_on, args.lcd_tau_off)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        import unicorn  # noqa: F401
    except ImportError:
        print(f"Achtung: {MISSING_UNICORN}", file=sys.stderr, flush=True)
    if args.ephemeral and not (args.sd_dir and inside_temp(args.sd_dir) and (not args.flash_dir or inside_temp(args.flash_dir))):
        print("--ephemeral deletes folders, so --sd-dir (and --flash-dir) must be given and lie inside the temporary folder.", file=sys.stderr)
        return 1
    page = args.page.rstrip("/")
    # The desktop app attaches to a running service (service.json) from its own origin; the token still guards it.
    origins = {page, page.replace("127.0.0.1", "localhost"), "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost", *args.allow_origin}
    try:
        store = CardStore(args.sd_dir or default_dir())
    except (CardError, OSError) as error:
        print(f"Kartenordner: {error}", file=sys.stderr)
        return 1
    server, token, emu = serve(args.port, token=os.environ.get("E2_EMU_TOKEN"), origins=origins, host=args.host, emulator=Emulator(cards=store, lcd_tau=lcd_tau, flash_store=FlashStore(args.flash_dir or (store.root / "flash" if args.ephemeral else default_flash_dir(store.root))), pace=not args.unthrottled))

    def leave(*_):
        # If the way out below hangs (a stuck machine thread), do not stay behind as a process nobody owns.
        timer = threading.Timer(HARD_EXIT_S, os._exit, (1,))
        timer.daemon = True
        timer.start()
        raise KeyboardInterrupt            # unwinds to the save below, also for kill and a closed terminal

    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), leave)
    if args.parent_pid:
        watch_parent(args.parent_pid)
    shown = args.host if args.host not in ("0.0.0.0", "::") else "127.0.0.1"
    print(f"Emulator läuft auf http://{shown}:{args.port}")
    print(f"Die Karte ist der Ordner {store.dir}")
    print(f"Der Flash ist die Datei {emu.flash_store.path}")
    print(f"Display-Trägheit: dunkel {lcd_tau[0]:g} s, hell {lcd_tau[1]:g} s")
    print(f"Editor öffnen: {page}/#emu={args.port}:{token}", flush=True)
    announce = store.root / "service.json"
    try:                                   # port and token for the desktop app, owner only, gone when we leave
        fd = os.open(announce, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"port": args.port, "token": token, "pid": os.getpid()}, f)
    except OSError as error:
        print(f"service.json: {error}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            announce.unlink()
        except OSError:
            pass
        emu.stop()                         # joins the machine thread, which writes the card back
        store.close()
        if args.ephemeral:
            for folder in (emu.flash_store.dir, store.root):
                shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()       # the frozen service's check workers start from this same binary (parallel.py)
    sys.exit(main())
