# SPDX-License-Identifier: GPL-2.0-only
"""The virtual SD card: one fixed folder on the host that the emulated Electribe sees as its card.

The folder (~/.gelumpe/sd/card, or GELUMPE_SD_DIR, or --sd-dir) is what the user
looks into with the file manager. Cards can hold Korg samples, so it lives in the
user's home and nowhere near a checkout. Inserting the card copies the folder
into a FAT32 image in memory, which is the medium the firmware reads and writes
(sdcard.py). While the card is inserted the folder is write-protected, and
whatever the firmware changes in the image is mirrored into it: a second after
the last write, and when the card is taken out. Nothing here deletes a file
the card did not contain when it went in.
"""

import json
import os
import re
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import fat32
from fat32 import Volume, open_volume
from firmware import is_synth

MIB = 1024 * 1024
CARD_MB = 1024                # the size at which the firmware's CARD FORMAT accepts the card (measured, 2026-10-10)
IDLE_S = 1.0                  # mirror the card once the firmware has been quiet this long
STALE_S = 60.0                # ... or at the latest this long after the first unmirrored change
BUSY_S = 2.0                  # a write this recent counts as "the firmware is working on the card"
SKIP_LIMIT = 50               # how many skipped files a clone report lists
FILE_LIMIT = (1 << 32) - 1
DEFAULT_FOLDER = "hacktribe"
LAYOUT = ("Sample", "System")  # folders the firmware keeps below KORG/<name>/; System is where SOFTWARE UPDATE looks
FOLDER_OK = re.compile(r"(?=.{1,32}\Z)[A-Za-z0-9_.-]+(?: [A-Za-z0-9_.-]+)*")   # a folder name below KORG/, single spaces inside
FOLDER_NAME = re.compile(rb"KORG/([A-Za-z0-9_. -]{1,32})/\x00")   # Korg's own build keeps its files in "electribe sampler", with a space


def default_dir():
    return Path(os.environ.get("GELUMPE_SD_DIR") or Path.home() / ".gelumpe" / "sd")


class CardError(Exception):
    """A request the store cannot do; the message is for the user."""


def card_folder(firmware):
    """The folder below KORG/ this firmware uses: the path literal that sits just before "e2sSample.all"."""
    data = bytes(firmware)
    payload = data[0x100:] if len(data) == 0x200100 else data
    if is_synth(payload):
        found = FOLDER_NAME.match(payload, 0x904D4)
        if not found or found[1] != b"electribe":
            raise CardError("Der gemessene Kartenordner der blauen Firmware fehlt.")
        return found[1].decode("ascii")
    end = data.find(b"e2sSample.all\x00")
    if end < 0:
        return DEFAULT_FOLDER
    found = FOLDER_NAME.findall(data[max(0, end - 0x200):end])
    return found[-1].decode("ascii") if found else DEFAULT_FOLDER


def open_in_file_manager(path):
    """Show a folder in the file manager of this computer."""
    if sys.platform == "win32":
        os.startfile(str(path))                       # noqa: S606 - a fixed folder of ours
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    try:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError as error:
        raise CardError(f"Der Dateimanager ließ sich nicht öffnen ({error.strerror}). Der Ordner ist {path}.") from None


def _write_json(path, obj):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class CardImage:
    """The medium the card model reads and writes (sdcard.py), kept in memory; `on_saved` mirrors it out."""

    def __init__(self, data, on_saved=None):
        self.data = data
        self.lock = threading.RLock()
        self.saving = threading.Lock()
        self.on_saved = on_saved
        self.dirty = False
        self.generation = 0
        self.dirty_since = 0.0
        self.last_write = 0.0       # monotonic time of the last change, 0 if none since loading

    @property
    def sectors(self):
        return len(self.data) // 512

    def read(self, lba):
        with self.lock:
            return bytes(self.data[lba * 512:(lba + 1) * 512])

    def write(self, lba, block):
        with self.lock:
            self.data[lba * 512:(lba + 1) * 512] = block
            self.touch()

    def touch(self):
        now = time.monotonic()
        with self.lock:
            if not self.dirty:
                self.dirty, self.dirty_since = True, now
            self.generation += 1
            self.last_write = now

    def busy(self):
        return self.last_write and time.monotonic() - self.last_write < BUSY_S

    def snapshot(self):
        with self.lock:
            return bytes(self.data)

    def save(self):
        """Mirror the image out if it changed. Returns whether it did."""
        with self.saving:
            with self.lock:
                if not self.dirty:
                    return False
                generation = self.generation
            if self.on_saved:
                self.on_saved(self)
            with self.lock:
                if generation == self.generation:
                    self.dirty = False
        return True

    def due(self):
        now = time.monotonic()
        return self.dirty and (now - self.last_write >= IDLE_S or now - self.dirty_since >= STALE_S)


def _fat_name(name):
    """A host file name made fit for FAT: forbidden characters become _, trailing dots and spaces go."""
    fixed = "".join("_" if c in fat32.LFN_BAD else c for c in name).strip(" ").rstrip(". ")
    while len(fixed.encode("utf-16-le")) // 2 > fat32.NAME_MAX:
        fixed = fixed[:-1]
    return fixed or "_"


def clone_folder(volume, folder, origins=None):
    """Copy a host folder into a mounted volume, once. Returns a report; nothing in the folder is changed.
    `origins`, when given, is filled with card path -> path in the folder, for names FAT made different."""
    report = {"files": 0, "bytes": 0, "folders": 0, "renamed": 0, "skipped": []}

    def skip(path, why):
        report["skipped"].append({"path": str(path), "why": why})

    def walk(host, card_path):
        try:
            names = sorted(os.listdir(host), key=str.casefold)
        except OSError as error:
            skip(host, f"nicht lesbar: {error.strerror}")
            return
        used = set()
        for raw in names:
            child = Path(host) / raw
            if raw.startswith(".") or raw in ("Thumbs.db", "desktop.ini"):
                continue                                   # hidden files and what file managers leave behind
            if child.is_symlink():
                skip(child, "Verknüpfung, wird nicht verfolgt")
                continue
            name = _fat_name(raw)
            if name.casefold() in used:
                skip(child, "Name nach dem Anpassen doppelt")
                continue
            used.add(name.casefold())
            if name != raw:
                report["renamed"] += 1
            target = card_path.rstrip("/") + "/" + name
            if origins is not None:
                origins[target] = child.relative_to(folder).as_posix()
            if child.is_dir():
                volume.mkdir(target)
                report["folders"] += 1
                walk(child, target)
            elif child.is_file():
                try:
                    size = child.stat().st_size
                    if size > FILE_LIMIT:
                        skip(child, "größer als 4 GiB")
                        continue
                    volume.write(target, child.read_bytes())
                except OSError as error:
                    skip(child, f"nicht lesbar: {error.strerror}")
                    continue
                report["files"] += 1
                report["bytes"] += size
            else:
                skip(child, "weder Datei noch Ordner")

    walk(folder, "/")
    report["skipped"] = report["skipped"][:SKIP_LIMIT] if len(report["skipped"]) <= SKIP_LIMIT else \
        report["skipped"][:SKIP_LIMIT] + [{"path": "...", "why": f"{len(report['skipped']) - SKIP_LIMIT} weitere"}]
    return report


def folder_size(folder, cluster):
    """What a folder would take on a card with this cluster size, a rough upper bound for the up-front check."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        total += cluster * 2
        for n in filenames:
            if n.startswith("."):
                continue
            try:
                size = os.lstat(os.path.join(dirpath, n)).st_size
            except OSError:
                continue
            total += -(-size // cluster) * cluster + cluster
    return total




def _signature(entry):
    return (entry.size, entry.mtime, entry.cluster)


class CardStore:
    def __init__(self, root=None, flusher=True, opener=open_in_file_manager):
        self.root = Path(root) if root else default_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self._lockfile = self._claim()
        self.dir = self.root / "card"
        self.opener = opener
        self.lock = threading.RLock()
        self.sync = threading.Lock()
        self.image = None             # the CardImage while the card is inserted
        self.manifest = {}            # card path -> (signature, path in the folder, is a folder) of what the card held
        self.sync_error = None
        state = self._read_json(self.root / "state.json") or {}
        self.skeleton = [n for n in state.get("skeleton", []) if isinstance(n, str) and FOLDER_OK.fullmatch(n)]
        if self.dir.is_dir():
            self._protect(False)      # a service that died with the card in leaves the folder write-protected
        else:
            self.dir.mkdir()
            self.ensure_layout(DEFAULT_FOLDER)
        self._stop = threading.Event()
        self._thread = None
        if flusher:
            self._thread = threading.Thread(target=self._flush_loop, daemon=True)
            self._thread.start()

    def _claim(self):
        """Only one service may own the card folder at a time: two would mirror over each other."""
        f = open(self.root / ".lock", "a+")
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass                                           # no flock here; the check is skipped
        except OSError:
            f.close()
            raise CardError(f"Der Kartenordner {self.root} wird schon von einem anderen Emulator-Dienst benutzt.")
        return f

    @staticmethod
    def _read_json(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    @property
    def inserted(self):
        return self.image is not None

    # ---- the folder ---------------------------------------------------------------
    def _protect(self, on):
        """Write-protect the whole folder, or give it back. Best effort: the file manager honours it."""
        paths = []
        for where, dirs, files in os.walk(self.dir):
            paths.extend(os.path.join(where, n) for n in files if not os.path.islink(os.path.join(where, n)))
            paths.extend(os.path.join(where, n) for n in dirs if not os.path.islink(os.path.join(where, n)))
            paths.append(where)
        dirs = {p for p in paths if os.path.isdir(p)}
        # protecting goes from the leaves to the root, giving back from the root to the leaves
        for p in sorted(paths, key=lambda p: p.count(os.sep), reverse=on):
            mode = (0o555 if p in dirs else 0o444) if on else (0o755 if p in dirs else 0o644)
            try:
                if stat.S_IMODE(os.stat(p).st_mode) != mode:
                    os.chmod(p, mode)
            except OSError:
                pass

    def ensure_layout(self, name):
        """KORG/<name>/Sample and System, the folders this firmware looks in. An empty layout made for
        another firmware is taken away again; anything with a file in it stays."""
        if self.inserted:
            return
        if not FOLDER_OK.fullmatch(name or ""):
            name = DEFAULT_FOLDER
        korg = self.dir / "KORG"
        with self.lock:
            for old in [n for n in self.skeleton if n != name]:
                self.skeleton.remove(old)
                for where, dirs, files in os.walk(korg / old, topdown=False):
                    if not files and not os.listdir(where):
                        os.rmdir(where)
            made = not (korg / name).exists()
            for sub in LAYOUT:
                (korg / name / sub).mkdir(parents=True, exist_ok=True)
            if made and name not in self.skeleton:
                self.skeleton.append(name)
            _write_json(self.root / "state.json", {"skeleton": self.skeleton})

    def put_system(self, name, data):
        """SYSTEM.VSB where SOFTWARE UPDATE of the firmware using KORG/<name>/ looks for it. Only with the card out."""
        if self.inserted:
            raise CardError("Die Karte muss ausgelegt sein, damit eine Datei in den Ordner kommt.")
        if not FOLDER_OK.fullmatch(name or ""):
            name = DEFAULT_FOLDER
        self.ensure_layout(name)
        target = self.dir / "KORG" / name / "System" / "SYSTEM.VSB"
        with self.lock:
            if name == "electribe":
                other = [p.name for p in target.parent.iterdir()
                         if p.suffix.upper() == ".VSB" and p.name != "SYSTEM.VSB"]
                if other:
                    raise CardError("Im blauen System-Ordner darf nur SYSTEM.VSB liegen. Weitere Dateien: " + ", ".join(sorted(other)))
            self._keep_previous(target, data)
            tmp = target.with_name(".SYSTEM.VSB.gelumpe-tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)

    @staticmethod
    def _keep_previous(target, data):
        """A SYSTEM.VSB that is already there and differs stays as KORG/<name>/SYSTEM-vorher.VSB (outside System/, where
        the firmware does not look); an earlier SYSTEM-vorher.VSB is never overwritten, the next gets a number."""
        try:
            old = target.read_bytes()
        except FileNotFoundError:
            return
        if old == data:
            return
        folder = target.parent.parent
        for n in range(1, 1000):
            keep = folder / ("SYSTEM-vorher.VSB" if n == 1 else f"SYSTEM-vorher-{n}.VSB")
            try:
                if keep.read_bytes() == old:
                    return
            except FileNotFoundError:
                keep.write_bytes(old)
                return

    def open_folder(self):
        self.opener(self.dir)
        return str(self.dir)

    # ---- inserting -----------------------------------------------------------------
    def insert(self, folder=None):
        """Copy the folder into a fresh image and write-protect it. Returns the clone report."""
        with self.lock:
            if self.inserted:
                return None
            if folder:
                self.ensure_layout(folder)
            size = CARD_MB * MIB
            cluster = fat32.geometry(size)[0] * 512
            if folder_size(self.dir, cluster) > size:
                raise CardError(f"Der Kartenordner ist größer als die Karte ({CARD_MB} MiB). Nimm Dateien heraus.")
            img = fat32.format_image(size)
            origins = {}
            vol = Volume(img)
            try:
                try:
                    report = clone_folder(vol, self.dir, origins)
                except fat32.CardFull:
                    raise CardError(f"Der Kartenordner ist größer als die Karte ({CARD_MB} MiB). Nimm Dateien heraus.") from None
                self.manifest = {path: (_signature(e), origins.get(path, path.lstrip("/")), e.is_dir) for path, e in vol.walk("/")}
            finally:
                vol.close()
            self.sync_error = None
            self.image = CardImage(img, on_saved=self._mirror)
            self._protect(True)
            return report

    def eject(self):
        """Mirror what the firmware left on the card, then give the folder back."""
        with self.lock:
            image = self.image
            if image is None:
                return
            self._mirror(image)
            self.image = None
            self.manifest = {}
            self._protect(False)

    # ---- the image goes back into the folder -----------------------------------------
    def _mirror(self, image):
        with self.sync:
            if image is not self.image:
                return
            try:
                with image.lock:
                    vol = open_volume(image.data)
                    try:
                        now, fresh = {}, {}
                        for path, e in vol.walk("/"):
                            now[path] = (_signature(e), e.is_dir, e.mtime)
                            if not e.is_dir and self.manifest.get(path, (None,))[0] != _signature(e):
                                fresh[path] = vol.read(path)
                    finally:
                        vol.close()
                self._apply(now, fresh)
                self.sync_error = None
            except fat32.FatError as error:
                self.sync_error = str(error)
            except Exception as error:                     # a card the firmware is formatting right now reads as nonsense
                self.sync_error = f"Die Karte ließ sich nicht in den Ordner übernehmen: {getattr(error, 'strerror', None) or error}"

    def _apply(self, now, fresh):
        self._protect(False)
        try:
            manifest = self.manifest
            for path in sorted(now, key=lambda p: p.count("/")):
                signature, is_dir, mtime = now[path]
                if path in manifest and manifest[path][0] == signature and manifest[path][2] == is_dir:
                    continue
                known = manifest.get(path)
                rel = known[1] if known else path.lstrip("/")
                host = self.dir / rel
                try:
                    if is_dir:
                        host.mkdir(parents=True, exist_ok=True)
                    else:
                        host.parent.mkdir(parents=True, exist_ok=True)
                        tmp = host.with_name(f".{host.name}.gelumpe-tmp")
                        tmp.write_bytes(fresh[path])
                        if mtime:
                            os.utime(tmp, (mtime, mtime))
                        os.replace(tmp, host)
                except OSError as error:
                    self.sync_error = f"{rel}: {error.strerror or error}"
                    continue
                manifest[path] = (signature, rel, is_dir)
            for path in sorted((p for p in manifest if p not in now), key=lambda p: p.count("/"), reverse=True):
                host = self.dir / manifest.pop(path)[1]
                try:
                    host.rmdir() if host.is_dir() and not host.is_symlink() else host.unlink()
                except OSError:
                    pass                                   # a folder with something of the user's in it stays
        finally:
            self._protect(True)

    def flush(self):
        """Mirror the card now if it changed."""
        image = self.image
        return bool(image and image.save())

    def _flush_loop(self):
        while not self._stop.wait(0.5):
            image = self.image
            if image is not None and image.due():
                try:
                    image.save()
                except Exception:
                    pass                                   # try again next round; the data is still in memory

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.eject()
        self._lockfile.close()
