# SPDX-License-Identifier: GPL-2.0-only
"""A FAT32 volume on a card image: format it, list, read, write and delete files.

The emulated firmware writes the same structures with its own FatFs, so this
reads whatever it left and edits it in place. Long file names, an MBR with one
partition (or a bare volume), two FAT copies and FSInfo are supported; FAT16 only
for reading (Fat16Volume, what the firmware's CARD FORMAT leaves); exFAT, FAT12
and a different sector size are not. Nothing here knows about the
emulator: it works on a bytearray, and the caller serialises access.
"""

import argparse
import struct
import sys
import time
from collections import namedtuple
from datetime import datetime

SECTOR = 512
MASK = 0x0FFFFFFF
EOC = 0x0FFFFFFF
MAX_SLOTS = 65535           # FatFs refuses directories with more entries than this
MIN_CLUSTERS = 65525        # below this count an image is FAT16 for every reader
PARTITION_START = 8192      # 4 MiB, where cards from the shop start their partition
ATTR_DIR, ATTR_VOLUME, ATTR_LFN = 0x10, 0x08, 0x0F
NAME_MAX = 255
LFN_BAD = set('"*/:<>?\\|') | {chr(i) for i in range(32)}
SHORT_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'()-@^_`{}~")

if sys.byteorder != "little":
    raise ImportError("the FAT is read in place and needs a little-endian host")


class FatError(Exception):
    """Anything wrong with a request or an image."""


class NotFound(FatError):
    pass


class Exists(FatError):
    pass


class CardFull(FatError):
    pass


class BadName(FatError):
    pass


class NotEmpty(FatError):
    pass


class Entry(namedtuple("Entry", "name short attr cluster size mtime slots")):
    __slots__ = ()

    @property
    def is_dir(self):
        return bool(self.attr & ATTR_DIR)


def _dos_time(ts):
    t = time.localtime(ts)
    year = min(max(t.tm_year, 1980), 2107)
    return (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2), ((year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday


def _from_dos(date, tm):
    try:
        return datetime(1980 + (date >> 9), (date >> 5) & 15, date & 31, tm >> 11, (tm >> 5) & 63, (tm & 31) * 2).timestamp()
    except ValueError:
        return None


def clock():
    """The time stamped on new entries; tests replace it."""
    return time.time()


def lfn_checksum(short11):
    s = 0
    for c in short11:
        s = (((s & 1) << 7) + (s >> 1) + c) & 0xFF
    return s


def check_name(name):
    if not name or name != name.strip(" ") or name.endswith(".") or len(name) > NAME_MAX:
        raise BadName(f"Ungültiger Name: {name!r}.")
    if any(ch in LFN_BAD for ch in name) or name in (".", ".."):
        raise BadName(f"Ungültiger Name: {name!r}.")
    if len(name.encode("utf-16-le")) // 2 > NAME_MAX:
        raise BadName(f"Name zu lang: {name!r}.")
    return name


def short_alias(name, taken):
    """The 8.3 alias for a long name, as 11 bytes, and whether the long name also needs LFN entries."""
    upper = name.upper()
    base, dot, ext = upper.rpartition(".")
    if not dot:
        base, ext = upper, ""
    exact = (name == upper and len(base) <= 8 and len(ext) <= 3 and base and not name.startswith(".")
             and all(c in SHORT_OK for c in base + ext))
    if exact:
        alias = (base.ljust(8) + ext.ljust(3)).encode("ascii")
        if alias not in taken:
            return alias, False
    lossy = False

    def clean(s):
        nonlocal lossy
        out = []
        for ch in s:
            if ch in " .":
                lossy = True
            elif ch in SHORT_OK:
                out.append(ch)
            else:
                out.append("_")
                lossy = True
        return "".join(out)

    stem, tail = clean(base.lstrip(".")), clean(ext)
    if not stem:
        stem, lossy = "_", True
    if len(stem) > 8 or len(tail) > 3:
        lossy = True
    stem, tail = stem[:8], tail[:3]
    if not lossy:
        alias = (stem.ljust(8) + tail.ljust(3)).encode("ascii")
        if alias not in taken:
            return alias, name != upper
    n = 1
    while True:
        suffix = f"~{n}"
        alias = (stem[:8 - len(suffix)] + suffix).ljust(8).encode("ascii") + tail.ljust(3).encode("ascii")
        if alias not in taken:
            return alias, True
        n += 1


def geometry(size):
    """Sectors per cluster, FAT size and cluster count for a card of this many bytes."""
    if size % SECTOR or size < 64 * 1024 * 1024:
        raise FatError("Eine Karte hat mindestens 64 MiB und eine volle Zahl Sektoren.")
    part = size // SECTOR - PARTITION_START
    spc = 1
    while spc < 64 and part // (spc * 2) >= 70000:
        spc *= 2
    fatsz = (part // spc * 4 + SECTOR - 1) // SECTOR + 1
    while True:
        clusters = (part - 32 - 2 * fatsz) // spc
        need = ((clusters + 2) * 4 + SECTOR - 1) // SECTOR
        if need <= fatsz:
            return spc, fatsz, clusters
        fatsz = need


def format_image(size, label="GELUMPE", volume_id=None):
    """A freshly formatted card: MBR, one FAT32 partition, an empty root directory."""
    spc, fatsz, clusters = geometry(size)
    if clusters < MIN_CLUSTERS:
        raise FatError("Zu wenige Cluster für FAT32.")
    img = bytearray(size)
    total = size // SECTOR
    part = total - PARTITION_START
    entry = bytearray(16)
    entry[4], entry[5:8] = 0x0C, b"\xff\xff\xff"
    entry[8:16] = struct.pack("<II", PARTITION_START, part)
    img[446:462] = entry
    img[510:512] = b"\x55\xaa"
    label = label.upper().encode("ascii", "replace")[:11].ljust(11)
    boot = bytearray(SECTOR)
    boot[0:3], boot[3:11] = b"\xEB\x58\x90", b"MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, spc, 32, 2, 0, 0, 0xF8, 0, 63, 255, PARTITION_START, part)
    struct.pack_into("<IHHIHH", boot, 36, fatsz, 0, 0, 2, 1, 6)
    boot[64], boot[66] = 0x80, 0x29
    boot[67:71] = struct.pack("<I", volume_id if volume_id is not None else int(clock()) & 0xFFFFFFFF)
    boot[71:82], boot[82:90] = label, b"FAT32   "
    boot[510:512] = b"\x55\xaa"
    fsinfo = bytearray(SECTOR)
    fsinfo[0:4], fsinfo[484:488] = b"RRaA", b"rrAa"
    struct.pack_into("<II", fsinfo, 488, clusters - 1, 3)
    fsinfo[510:512] = b"\x55\xaa"
    base = PARTITION_START * SECTOR
    for at in (0, 6):
        img[base + at * SECTOR:base + (at + 1) * SECTOR] = boot
    for at in (1, 7):
        img[base + at * SECTOR:base + (at + 1) * SECTOR] = fsinfo
    for k in range(2):
        fat = base + (32 + k * fatsz) * SECTOR
        struct.pack_into("<III", img, fat, 0x0FFFFFF8, 0x0FFFFFFF, EOC)
    return img


class Volume:
    """Reads and edits the FAT32 volume in `img`; `on_change` runs after every edit."""

    def __init__(self, img, on_change=None):
        self.img = img
        self.on_change = on_change
        ps = 0
        boot = bytes(img[0:SECTOR])
        if boot[510:512] != b"\x55\xaa":
            raise FatError("Kein Dateisystem auf der Karte (Kennung 0xAA55 fehlt).")
        if boot[82:87] != b"FAT32":                      # not a bare volume: take the first partition
            ps = struct.unpack_from("<I", boot, 446 + 8)[0]
            if boot[446 + 4] in (0x04, 0x06, 0x0E):
                raise FatError("Die Karte hat FAT16 (so formatiert die Electribe sie mit CARD FORMAT). "
                               "Hier lässt sich nur FAT32 auflisten; das Abbild lässt sich trotzdem laden.")
            if boot[446 + 4] not in (0x0B, 0x0C) or not ps:
                raise FatError("Keine FAT32-Partition auf der Karte.")
        self.ps = ps
        b = bytes(img[ps * SECTOR:(ps + 1) * SECTOR])
        if b[82:87] != b"FAT32" or struct.unpack_from("<H", b, 11)[0] != SECTOR:
            raise FatError("Keine FAT32-Partition auf der Karte.")
        self.spc, self.rsv, self.nfat = b[13], struct.unpack_from("<H", b, 14)[0], b[16]
        total = struct.unpack_from("<I", b, 32)[0]
        self.fatsz = struct.unpack_from("<I", b, 36)[0]
        self.root = struct.unpack_from("<I", b, 44)[0]
        self.fsinfo = struct.unpack_from("<H", b, 48)[0]
        self.backup = struct.unpack_from("<H", b, 50)[0]
        self.label = b[71:82].decode("latin1").rstrip()
        self.csz = self.spc * SECTOR
        self.clusters = (total - self.rsv - self.nfat * self.fatsz) // self.spc
        self.data = (ps + self.rsv + self.nfat * self.fatsz) * SECTOR
        if self.spc not in (1, 2, 4, 8, 16, 32, 64) or self.clusters < MIN_CLUSTERS or (ps + total) * SECTOR > len(img):
            raise FatError("Das Dateisystem passt nicht zum Abbild.")
        view = memoryview(img)
        self.fats = [view[(ps + self.rsv + k * self.fatsz) * SECTOR:(ps + self.rsv + (k + 1) * self.fatsz) * SECTOR].cast("I")
                     for k in range(self.nfat)]
        self.free = sum(1 for c in range(2, self.clusters + 2) if not self.fats[0][c] & MASK)
        self.hint = 3

    def close(self):
        for f in self.fats:
            f.release()
        self.fats = []

    # ---- FAT ---------------------------------------------------------------------
    def next(self, c):
        return self.fats[0][c] & MASK

    def _set(self, c, v):
        for f in self.fats:
            f[c] = (f[c] & 0xF0000000) | v

    def chain(self, c):
        out = []
        while 2 <= c < self.clusters + 2:
            out.append(c)
            if len(out) > self.clusters:
                raise FatError("Zyklus in einer Clusterkette.")
            c = self.next(c)
        return out

    def _alloc(self, n):
        """n free clusters linked into one chain, taken from the hint on, so a file is usually one run."""
        fat, got, c = self.fats[0], [], self.hint
        for _ in range(self.clusters):
            if c >= self.clusters + 2:
                c = 2
            if not fat[c] & MASK:
                got.append(c)
                if len(got) == n:
                    break
            c += 1
        if len(got) < n:
            raise CardFull("Die Karte ist voll.")
        for a, b in zip(got, got[1:]):
            self._set(a, b)
        self._set(got[-1], EOC)
        self.hint = got[-1] + 1
        self.free -= n
        return got

    def _free_chain(self, first):
        n = 0
        for c in self.chain(first):
            self._set(c, 0)
            n += 1
        if n:
            self.free += n
            self.hint = min(self.hint, first)

    def _cluster_at(self, c):
        return self.data + (c - 2) * self.csz

    def _write_clusters(self, clusters, data):
        at = 0
        i = 0
        while i < len(clusters):
            j = i
            while j + 1 < len(clusters) and clusters[j + 1] == clusters[j] + 1:
                j += 1
            run = (j - i + 1) * self.csz
            chunk = data[at:at + run]
            o = self._cluster_at(clusters[i])
            self.img[o:o + run] = chunk + bytes(run - len(chunk))
            at += run
            i = j + 1

    def free_bytes(self):
        return self.free * self.csz

    def capacity(self):
        return self.clusters * self.csz

    # ---- directories ---------------------------------------------------------------
    def _slots(self, cl):
        out = []
        for c in self.chain(cl):
            base = self._cluster_at(c)
            out.extend(range(base, base + self.csz, 32))
        return out

    def entries(self, cl, dots=False):
        img, out, pending = self.img, [], []
        for off in self._slots(cl):
            first = img[off]
            if first == 0:
                break
            if first == 0xE5:
                pending = []
                continue
            attr = img[off + 11]
            if attr & 0x3F == ATTR_LFN:
                if first & 0x40:
                    pending = []
                pending.append((first & 0x1F, bytes(img[off + 1:off + 11] + img[off + 14:off + 26] + img[off + 28:off + 32]), img[off + 13], off))
                continue
            if attr & ATTR_VOLUME:
                pending = []
                continue
            raw = bytes(img[off:off + 11])
            shortname = raw[:8].decode("latin1").rstrip()
            if raw[0] == 0x05:
                shortname = "\xe5" + shortname[1:]
            ext = raw[8:11].decode("latin1").rstrip()
            lower = img[off + 12]
            if lower & 0x08:
                shortname = shortname.lower()
            if lower & 0x10:
                ext = ext.lower()
            name = shortname + ("." + ext if ext else "")
            slots = [off]
            seqs = [p[0] for p in pending]
            if pending and seqs == list(range(len(seqs), 0, -1)) and all(p[2] == lfn_checksum(raw) for p in pending):
                text = b"".join(p[1] for p in reversed(pending)).decode("utf-16-le", "replace")
                name = text.split("\x00")[0].rstrip("�￿") or name
                slots = [p[3] for p in pending] + [off]
            pending = []
            if not dots and name in (".", ".."):
                continue
            hi, lo = struct.unpack_from("<H", img, off + 20)[0], struct.unpack_from("<H", img, off + 26)[0]
            size = struct.unpack_from("<I", img, off + 28)[0]
            date, tm = struct.unpack_from("<HH", img, off + 24)[0], struct.unpack_from("<H", img, off + 22)[0]
            out.append(Entry(name, raw, attr, (hi << 16) | lo, size, _from_dos(date, tm), slots))
        return out

    def _find(self, cl, name):
        want = name.casefold()
        for e in self.entries(cl):
            if e.name.casefold() == want or self._short_text(e.short).casefold() == want:
                return e

    @staticmethod
    def _short_text(raw):
        base, ext = raw[:8].decode("latin1").rstrip(), raw[8:11].decode("latin1").rstrip()
        return base + ("." + ext if ext else "")

    def _entry_bytes(self, short11, attr, cluster, size, when):
        tm, date = _dos_time(when)
        e = bytearray(32)
        e[0:11], e[11] = short11, attr
        struct.pack_into("<HHHHHHHI", e, 14, tm, date, date, cluster >> 16, tm, date, cluster & 0xFFFF, size)
        return e

    def _add_entry(self, cl, name, attr, cluster, size, when):
        taken = {e.short for e in self.entries(cl, dots=True)}
        short, lfn = short_alias(name, taken)
        raw = bytearray()
        if lfn:
            units = name.encode("utf-16-le")
            if len(units) // 2 % 13:                      # a name that fills its last entry has no terminator
                units += b"\x00\x00"
            parts = -(-len(units) // 26)
            units = units.ljust(parts * 26, b"\xff")
            ck = lfn_checksum(short)
            for i in range(parts, 0, -1):
                chunk = units[(i - 1) * 26:i * 26]
                e = bytearray(32)
                e[0] = i | (0x40 if i == parts else 0)
                e[1:11], e[11], e[13], e[14:26], e[28:32] = chunk[0:10], ATTR_LFN, ck, chunk[10:22], chunk[22:26]
                raw += e
        raw += self._entry_bytes(short, attr, cluster, size, when)
        need = len(raw) // 32
        chain = self.chain(cl)
        slots = self._slots(cl)
        zero = next((i for i, off in enumerate(slots) if self.img[off] == 0), len(slots))
        at, run = None, 0
        for i in range(zero):                             # a run of deleted slots before the end mark
            run = run + 1 if self.img[slots[i]] == 0xE5 else 0
            if run == need:
                at = i - need + 1
                break
        if at is None:
            at = zero
            missing = zero + need - len(slots)
            if zero + need > MAX_SLOTS:
                raise CardFull("Das Verzeichnis ist voll.")
            if missing > 0:
                more = self._alloc(-(-missing * 32 // self.csz))
                for c in more:
                    o = self._cluster_at(c)
                    self.img[o:o + self.csz] = bytes(self.csz)
                self._set(chain[-1], more[0])
                slots = self._slots(cl)
        for k in range(need):
            self.img[slots[at + k]:slots[at + k] + 32] = raw[k * 32:(k + 1) * 32]

    # ---- paths ---------------------------------------------------------------------
    @staticmethod
    def parts(path):
        parts = [p for p in str(path).replace("\\", "/").split("/") if p]
        if any(p in (".", "..") for p in parts):
            raise BadName("Pfade mit . oder .. gibt es nicht.")
        return parts

    def _walk_dirs(self, parts, create=False, when=None):
        """The cluster of the directory named by `parts`; with `create` missing ones are made."""
        cl = self.root
        for p in parts:
            e = self._find(cl, p)
            if e is None:
                if not create:
                    raise NotFound(f"Nicht gefunden: {p}")
                cl = self._mkdir(cl, check_name(p), when if when is not None else clock())
            elif not e.is_dir:
                raise FatError(f"{p} ist eine Datei, kein Ordner.")
            else:
                cl = e.cluster or self.root
        return cl

    def _mkdir(self, parent, name, when):
        c = self._alloc(1)[0]
        o = self._cluster_at(c)
        self.img[o:o + self.csz] = bytes(self.csz)
        self.img[o:o + 32] = self._entry_bytes(b".          ", ATTR_DIR, c, 0, when)
        self.img[o + 32:o + 64] = self._entry_bytes(b"..         ", ATTR_DIR, 0 if parent == self.root else parent, 0, when)
        self._add_entry(parent, name, ATTR_DIR, c, 0, when)
        return c

    def _changed(self):
        if self.fsinfo and self.fsinfo < self.rsv:
            for at in (self.fsinfo, self.backup + self.fsinfo if self.backup else 0):
                o = (self.ps + at) * SECTOR
                if not at:
                    continue
                if self.img[o:o + 4] == b"RRaA":
                    struct.pack_into("<II", self.img, o + 488, self.free, self.hint)
        if self.on_change:
            self.on_change()

    # ---- public --------------------------------------------------------------------
    def stat(self, path):
        parts = self.parts(path)
        if not parts:
            return Entry("", b"", ATTR_DIR, self.root, 0, None, [])
        e = self._find(self._walk_dirs(parts[:-1]), parts[-1])
        if e is None:
            raise NotFound(f"Nicht gefunden: {path}")
        return e

    def listdir(self, path="/"):
        e = self.stat(path)
        if not e.is_dir:
            raise FatError(f"{path} ist eine Datei, kein Ordner.")
        return self.entries(e.cluster or self.root)

    def read(self, path):
        e = self.stat(path)
        if e.is_dir:
            raise FatError(f"{path} ist ein Ordner.")
        if not e.size:
            return b""
        chain = self.chain(e.cluster)
        if len(chain) * self.csz < e.size:
            raise FatError(f"{path}: die Clusterkette ist kürzer als die Datei.")
        out = bytearray()
        for c in chain:
            o = self._cluster_at(c)
            out += self.img[o:o + self.csz]
        return bytes(out[:e.size])

    def write(self, path, data, overwrite=False):
        """Create a file, and the folders on the way. An existing file is replaced only with `overwrite`."""
        parts = self.parts(path)
        if not parts:
            raise BadName("Ein Dateiname fehlt.")
        data = bytes(data)
        if len(data) >= 1 << 32:
            raise FatError("Eine Datei auf FAT32 ist höchstens 4 GiB groß.")
        name = check_name(parts[-1])
        need = -(-len(data) // self.csz)
        when = clock()
        try:
            cl = self._walk_dirs(parts[:-1])
            old = self._find(cl, name)
        except NotFound:
            cl, old = None, None
        if old is not None:
            if old.is_dir:
                raise Exists(f"{path} ist ein Ordner.")
            if not overwrite:
                raise Exists(f"{path} gibt es schon.")
        gain = len(self.chain(old.cluster)) if old is not None and old.cluster else 0
        if need + 4 > self.free + gain:                   # a little room for new directory clusters
            raise CardFull(f"Die Karte ist voll: {len(data)} Byte brauchen {need} Cluster, frei sind {self.free + gain}.")
        try:
            if old is not None:
                self._delete_entry(old)
            if cl is None:
                cl = self._walk_dirs(parts[:-1], create=True, when=when)
            clusters = self._alloc(need) if need else []
            self._write_clusters(clusters, data)
            self._add_entry(cl, name, 0x20, clusters[0] if clusters else 0, len(data), when)
        finally:
            self._changed()

    def mkdir(self, path):
        parts = self.parts(path)
        if not parts:
            return
        try:
            self._walk_dirs(parts, create=True)
        finally:
            self._changed()

    def _delete_entry(self, e):
        for off in e.slots:
            self.img[off] = 0xE5
        if e.cluster:
            self._free_chain(e.cluster)

    def delete(self, path, recursive=False):
        parts = self.parts(path)
        if not parts:
            raise BadName("Die Wurzel lässt sich nicht löschen.")
        try:
            parent = self._walk_dirs(parts[:-1])
            e = self._find(parent, parts[-1])
            if e is None:
                raise NotFound(f"Nicht gefunden: {path}")
            if e.is_dir:
                kids = self.entries(e.cluster)
                if kids and not recursive:
                    raise NotEmpty(f"{path} ist nicht leer.")
                for kid in kids:
                    self.delete("/".join(parts + [kid.name]), recursive=True)
            self._delete_entry(e)
        finally:
            self._changed()

    def walk(self, path="/"):
        """Every file and folder below `path`, as (path, Entry), folders before their content."""
        base = "/" + "/".join(self.parts(path))
        for e in self.listdir(path):
            full = base.rstrip("/") + "/" + e.name
            yield full, e
            if e.is_dir:
                yield from self.walk(full)

    def usage(self):
        return {"capacity": self.capacity(), "free": self.free_bytes(), "cluster": self.csz, "label": self.label}

    def check(self):
        """Problems found in the structures; an empty list means consistent."""
        problems = []
        if self.nfat > 1 and any(self.fats[0][c] & MASK != self.fats[k][c] & MASK
                                 for k in range(1, self.nfat) for c in range(self.clusters + 2)):
            problems.append("FAT-Kopien weichen ab")
        seen = {}
        used = 0

        def claim(c, who):
            nonlocal used
            for cc in self.chain(c):
                if cc in seen:
                    problems.append(f"Cluster {cc} gehört {who} und {seen[cc]}")
                seen[cc] = who
                used += 1

        claim(self.root, "/")

        def scan(cl, where):
            for e in self.entries(cl):
                full = where.rstrip("/") + "/" + e.name
                if e.is_dir:
                    if not e.cluster:
                        problems.append(f"{full}: Ordner ohne Cluster")
                        continue
                    claim(e.cluster, full)
                    scan(e.cluster, full)
                else:
                    n = len(self.chain(e.cluster)) if e.cluster else 0
                    if n != -(-e.size // self.csz):
                        problems.append(f"{full}: {n} Cluster für {e.size} Byte")
                    if e.cluster:
                        claim(e.cluster, full)

        scan(self.root, "/")
        counted = sum(1 for c in range(2, self.clusters + 2) if self.fats[0][c] & MASK)
        if counted != used:
            problems.append(f"{counted - used} Cluster belegt, aber nirgends eingetragen")
        return problems


class Fat16Volume(Volume):
    """A FAT16 volume, read only: what the firmware's CARD FORMAT leaves on a 1 GiB card."""

    def __init__(self, img, on_change=None):
        self.img = img
        self.on_change = on_change
        ps = 0
        boot = bytes(img[0:SECTOR])
        if boot[510:512] != b"\x55\xaa":
            raise FatError("Kein Dateisystem auf der Karte (Kennung 0xAA55 fehlt).")
        if boot[54:57] != b"FAT":
            if boot[446 + 4] not in (0x04, 0x06, 0x0E):
                raise FatError("Keine FAT16-Partition auf der Karte.")
            ps = struct.unpack_from("<I", boot, 446 + 8)[0]
        self.ps = ps
        b = bytes(img[ps * SECTOR:(ps + 1) * SECTOR])
        if b[510:512] != b"\x55\xaa" or struct.unpack_from("<H", b, 11)[0] != SECTOR or b[54:57] != b"FAT":
            raise FatError("Keine FAT16-Partition auf der Karte.")
        self.spc, self.rsv, self.nfat = b[13], struct.unpack_from("<H", b, 14)[0], b[16]
        root_entries = struct.unpack_from("<H", b, 17)[0]
        total = struct.unpack_from("<H", b, 19)[0] or struct.unpack_from("<I", b, 32)[0]
        self.fatsz = struct.unpack_from("<H", b, 22)[0]
        self.root, self.fsinfo, self.backup = 0, 0, 0     # the root directory is a fixed run of slots, not a chain
        self.label = b[43:54].decode("latin1").rstrip()
        self.csz = self.spc * SECTOR
        root_sectors = (root_entries * 32 + SECTOR - 1) // SECTOR
        first_root = (ps + self.rsv + self.nfat * self.fatsz) * SECTOR
        self.root_slots = list(range(first_root, first_root + root_entries * 32, 32))
        self.clusters = (total - self.rsv - self.nfat * self.fatsz - root_sectors) // self.spc
        self.data = first_root + root_sectors * SECTOR
        if self.spc not in (1, 2, 4, 8, 16, 32, 64) or not 0 < self.clusters < MIN_CLUSTERS or (ps + total) * SECTOR > len(img):
            raise FatError("Das Dateisystem passt nicht zum Abbild.")
        view = memoryview(img)
        self.fats = [view[(ps + self.rsv + k * self.fatsz) * SECTOR:(ps + self.rsv + (k + 1) * self.fatsz) * SECTOR].cast("H")
                     for k in range(self.nfat)]
        self.free = sum(1 for c in range(2, self.clusters + 2) if not self.fats[0][c])
        self.hint = 3

    def _slots(self, cl):
        return self.root_slots if cl == 0 else super()._slots(cl)

    def write(self, *args, **kwargs):
        raise FatError("Ein FAT16-Abbild lässt sich nur lesen.")

    mkdir = delete = write


def open_volume(img, on_change=None):
    """The volume in `img`, FAT32 for editing or, failing that, FAT16 for reading."""
    try:
        return Volume(img, on_change)
    except FatError as first:
        try:
            return Fat16Volume(img, on_change)
        except FatError:
            raise first from None


def main():
    parser = argparse.ArgumentParser(description="Look into a card image written by the emulator.")
    parser.add_argument("command", choices=["ls", "check", "cat"])
    parser.add_argument("image")
    parser.add_argument("path", nargs="?", default="/")
    args = parser.parse_args()
    with open(args.image, "rb") as f:
        v = Volume(bytearray(f.read()))
    if args.command == "check":
        problems = v.check()
        print("\n".join(problems) or "ok")
        return 1 if problems else 0
    if args.command == "cat":
        sys.stdout.buffer.write(v.read(args.path))
        return 0
    for path, e in v.walk(args.path):
        print(f"{'d' if e.is_dir else '-'} {e.size:10d} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
