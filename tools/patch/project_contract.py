# SPDX-License-Identifier: GPL-2.0-only
"""Research contracts for project imports, not a firmware loader or native lock.

The pure models constrain later emulator experiments. Declaration checks do not prove
that a proposed RAM area is unused by native code, DMA or a real device.
"""

import hashlib
import struct

BLOCK_SIZE = 0x4000
BANK_COUNT = 250
BANK_BYTES = BANK_COUNT * BLOCK_SIZE
FILE_PREFIX = 0x10100
RAM_START, RAM_END = 0xC0000000, 0xC4000000
ARENA_LIMIT = 13 * 1024 * 1024
SNAPSHOT_BYTES = 3 * BANK_BYTES + BLOCK_SIZE
UINT32_MAX = 0xFFFFFFFF
NATIVE_SAMPLE_TABLE_ENTRIES = 1020
NATIVE_SAMPLE_VISITED = 999
NATIVE_SAMPLE_MAX_RANGES = 16384
SOURCE_IDENTITY_BYTES = NATIVE_SAMPLE_MAX_RANGES * 40 + (NATIVE_SAMPLE_MAX_RANGES + 7) // 8
MIN_ARENA_BYTES = SNAPSHOT_BYTES + SOURCE_IDENTITY_BYTES


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"invalid {name}")
    return value


def bounded_range(offset, length, total):
    integer(total, 0, UINT32_MAX, "source length")
    integer(offset, 0, UINT32_MAX, "offset")
    integer(length, 0, UINT32_MAX, "length")
    end = offset + length
    if end > UINT32_MAX or end > total:
        raise ValueError("range exceeds source or wraps a 32-bit offset")
    return offset, end


def bank_bytes(raw):
    try:
        view = memoryview(raw).cast("B")
    except (TypeError, ValueError) as error:
        raise ValueError("pattern bank must contain bytes") from error
    if len(view) != BANK_BYTES:
        raise ValueError("pattern bank must hold exactly 250 complete blocks")
    return view


def changed_slots(actual_flash, candidate):
    """Indices whose complete persistable block differs from the actual flash bytes."""
    old, new = bank_bytes(actual_flash), bank_bytes(candidate)
    return [index for index in range(BANK_COUNT)
            if old[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]
            != new[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]]


def pattern_bank(raw):
    raw = bytes(raw)
    if len(raw) != FILE_PREFIX + BANK_BYTES:
        raise ValueError("invalid all-pattern file length")
    if raw[:5] != b"KORG\0" or raw[16:26] != b"e2sampler\0":
        raise ValueError("invalid all-pattern file header")
    for index in range(BANK_COUNT):
        at = FILE_PREFIX + index * BLOCK_SIZE
        if (raw[at:at + 4] != b"PTST" or struct.unpack_from("<I", raw, at + 4)[0] != BLOCK_SIZE
                or raw[at + 0x3BFC:at + 0x3C00] != b"PTED"):
            raise ValueError(f"invalid frame in pattern {index}")
    return raw[FILE_PREFIX:]


def project_path(name, filename, *, capacity):
    """Build a direct-child path within a caller-supplied byte capacity including NUL."""
    integer(capacity, 1, UINT32_MAX, "path capacity")
    if (not isinstance(name, str) or not name or name != name.strip(" ")
            or name in (".", "..") or name.endswith(".")
            or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name)):
        raise ValueError("invalid project directory name")
    if filename not in ("e2sPattern.all", "e2sSample.all"):
        raise ValueError("unsupported project filename")
    path = f"SD:KORG/blechtribe/Projects/{name}/{filename}"
    try:
        required = len(path.encode("utf8")) + 1
    except UnicodeEncodeError as error:
        raise ValueError("invalid project directory encoding") from error
    if required > capacity:
        raise ValueError("project path exceeds its buffer")
    return path


def native_sample_read_ranges(raw):
    """Unique F_READ ranges predicted from supported .all/WAV metadata before loading.

    Mirrors the Sampler's raw-size chunk walk, not a destructive import trace. Only
    unambiguous PCM16/PCM24 mono/stereo with fmt16 and one indexed ESLI is supported.
    This constrains source reads; it does not validate DSP capacity or all ESLI fields.
    """
    try:
        view = memoryview(raw).cast("B")
    except (TypeError, ValueError) as error:
        raise ValueError("sample set must contain bytes") from error
    total = integer(len(view), 4096, UINT32_MAX, "sample set length")
    if view[:16] != b"e2s sample all\x1a\0":
        raise ValueError("unsupported all-sample header")
    table = struct.unpack_from(f"<{NATIVE_SAMPLE_TABLE_ENTRIES}I", view, 16)
    if any(table[NATIVE_SAMPLE_VISITED:]):
        raise ValueError("sample set uses slots ignored by the native loader")
    ranges, seen, intervals = [], set(), []

    def add(offset, length):
        bounded_range(offset, length, total)
        key = (offset, length)
        if key not in seen:
            if len(ranges) >= NATIVE_SAMPLE_MAX_RANGES:
                raise ValueError("native sample read plan exceeds its metadata budget")
            seen.add(key)
            ranges.append(key)

    def chunk(at, limit):
        bounded_range(at, 8, limit)
        length = struct.unpack_from("<I", view, at + 4)[0]
        start, end = bounded_range(at + 8, length, limit)
        add(at, 8)
        return bytes(view[at:at + 4]), start, end

    add(0, 4096)
    offsets = [offset for offset in table[:NATIVE_SAMPLE_VISITED] if offset]
    if len(offsets) != len(set(offsets)):
        raise ValueError("ambiguous duplicate sample offsets")
    for slot, base in enumerate(table[:NATIVE_SAMPLE_VISITED]):
        if not base:
            continue
        if base < 4096:
            raise ValueError("sample overlaps the all-sample header")
        bounded_range(base, 12, total)
        if view[base:base + 4] != b"RIFF" or view[base + 8:base + 12] != b"WAVE":
            raise ValueError("unsupported RIFF/WAVE sample")
        riff_size = struct.unpack_from("<I", view, base + 4)[0]
        _, riff_end = bounded_range(base + 8, riff_size, total)
        if riff_size < 4:
            raise ValueError("truncated WAVE body")
        intervals.append((base, riff_end))
        add(base, 8)
        add(base + 8, 4)
        fmt = data = esli = None
        cursor = base + 12
        while cursor < riff_end:
            tag, start, end = chunk(cursor, riff_end)
            if tag == b"fmt ":
                if fmt is not None or end - start != 16:
                    raise ValueError("ambiguous or unsupported fmt chunk")
                fmt = start
            elif tag == b"data":
                if data is not None:
                    raise ValueError("ambiguous data chunk")
                data = (start, end - start)
            elif tag == b"korg":
                nested = start
                while nested < end:
                    nested_tag, nested_start, nested_end = chunk(nested, end)
                    if nested_tag == b"esli":
                        if esli is not None or nested_end - nested_start != 1172:
                            raise ValueError("ambiguous or unsupported ESLI record")
                        esli = nested_start
                    nested = nested_end
            cursor = end
        if fmt is None or data is None or esli is None:
            raise ValueError("whole-set sample lacks fmt, data or indexed ESLI")
        tag, channels, rate, byte_rate, align, bits = struct.unpack_from("<HHIIHH", view, fmt)
        if tag != 1 or channels not in (1, 2) or bits not in (16, 24):
            raise ValueError("unsupported sample format for the native read plan")
        expected_align = channels * (bits // 8)
        if not rate or align != expected_align or byte_rate != rate * align:
            raise ValueError("inconsistent PCM format fields")
        data_at, data_size = data
        if not data_size or data_size % expected_align:
            raise ValueError("empty or incomplete PCM frames")
        if struct.unpack_from("<H", view, esli)[0] != slot:
            raise ValueError("ESLI index differs from the all-sample table slot")
        add(fmt, 16)
        add(esli, 1172)
        add(data_at - 8, 8)
        bytes_per_value = bits // 8
        remaining = data_size // bytes_per_value
        cursor = data_at
        while remaining:
            values = min(remaining, 32768)
            count = values * bytes_per_value
            add(cursor, count)
            cursor += count
            remaining -= values
    ordered = sorted(intervals)
    if any(before[1] > after[0] for before, after in zip(ordered, ordered[1:])):
        raise ValueError("overlapping sample RIFF regions")
    return ranges


class SourceIdentity:
    """Fingerprints of predeclared reads; it does not hook the firmware's file API."""

    def __init__(self, total, fingerprints):
        self.total = total
        self.fingerprints = fingerprints
        self.seen = set()
        self.failed = False

    @classmethod
    def from_ranges(cls, raw, ranges, *, max_ranges=NATIVE_SAMPLE_MAX_RANGES):
        integer(max_ranges, 1, UINT32_MAX, "read-range capacity")
        raw = memoryview(raw).cast("B")
        integer(len(raw), 0, UINT32_MAX, "source length")
        fingerprints = {}
        for offset, length in ranges:
            start, end = bounded_range(offset, length, len(raw))
            if not length or (offset, length) in fingerprints or len(fingerprints) >= max_ranges:
                raise ValueError("duplicate, empty or excessive consumed ranges")
            fingerprints[offset, length] = hashlib.sha256(raw[start:end]).digest()
        if not fingerprints:
            raise ValueError("consumed-range contract is empty")
        return cls(len(raw), fingerprints)

    def observe(self, offset, raw):
        if self.failed:
            raise ValueError("source identity already failed")
        try:
            bounded_range(offset, len(raw), self.total)
            expected = self.fingerprints.get((offset, len(raw)))
            if expected is None or hashlib.sha256(raw).digest() != expected:
                raise ValueError("consumed bytes differ from the preflight contract")
        except (ValueError, TypeError):
            self.failed = True
            raise ValueError("unbound or changed source read") from None
        self.seen.add((offset, len(raw)))

    def complete(self):
        if self.failed or self.seen != self.fingerprints.keys():
            raise ValueError("source reads failed or did not cover the consumed-range contract")
        return True


class ImportOperation:
    """Sequential ownership model; native task/input exclusion needs separate evidence."""

    def __init__(self):
        self.generation = 0
        self.pending_confirmation = None
        self.locked = False
        self.flash_before = None
        self.ram_before = None
        self.editor_before = None
        self.mfx_before = None
        self.selection = None
        self.touched = set()

    def mutation(self, action):
        if self.locked:
            raise ValueError(f"{action} must wait for the active import")
        self.generation += 1

    def confirmation(self):
        if self.locked:
            raise ValueError("an import already owns the operation")
        self.pending_confirmation = self.generation
        return self.generation

    def acquire(self, token):
        if (self.locked or type(token) is not int or token != self.generation
                or token != self.pending_confirmation):
            raise ValueError("confirmation is stale or operation is already owned")
        self.locked = True
        self.pending_confirmation = None
        self.flash_before = self.ram_before = self.editor_before = self.mfx_before = None
        self.selection = None
        self.touched.clear()

    def capture(self, *, flash, ram, editor, selection, mfx):
        if not self.locked or self.flash_before is not None:
            raise ValueError("authoritative snapshots require exclusive ownership and one capture")
        bank_bytes(flash)
        bank_bytes(ram)
        integer(selection, 0, BANK_COUNT - 1, "selected pattern")
        editor, mfx = bytes(editor), bytes(mfx)
        if len(editor) != BLOCK_SIZE or MIN_ARENA_BYTES + len(mfx) > ARENA_LIMIT:
            raise ValueError("snapshot size exceeds the project budget")
        self.flash_before, self.ram_before = bytes(flash), bytes(ram)
        self.editor_before, self.mfx_before = editor, mfx
        self.selection = selection

    def mark_attempt(self, index):
        if not self.locked or self.flash_before is None:
            raise ValueError("write attempts require captured preimages under ownership")
        self.touched.add(integer(index, 0, BANK_COUNT - 1, "pattern index"))

    def attempt(self, index, writer):
        if not callable(writer):
            raise ValueError("writer must be callable")
        self.mark_attempt(index)
        return writer(index)

    def rollback_targets(self, actual_flash):
        if not self.locked or self.flash_before is None:
            raise ValueError("rollback requires an owned snapshot")
        actual = bank_bytes(actual_flash)
        return {index: self.flash_before[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]
                for index in sorted(self.touched)
                if actual[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]
                != self.flash_before[index * BLOCK_SIZE:(index + 1) * BLOCK_SIZE]}

    def recovered(self, actual_flash):
        if not self.locked or self.flash_before is None or bytes(bank_bytes(actual_flash)) != self.flash_before:
            raise ValueError("flash recovery has not been verified")
        at = self.selection * BLOCK_SIZE
        restored = dict(bank=self.flash_before, editor=self.flash_before[at:at + BLOCK_SIZE],
                        selection=self.selection, mfx=self.mfx_before)
        self.locked = False
        return restored


def project_area_errors(start, length, owners):
    """Check a proposed declaration against bounds and caller-supplied current owners."""
    errors = []
    try:
        integer(start, RAM_START, RAM_END - 1, "project area start")
        integer(length, MIN_ARENA_BYTES, ARENA_LIMIT, "project area length")
        _, end = bounded_range(start, length, RAM_END)
    except ValueError as error:
        return [str(error)]
    for owner in owners:
        if start < owner["end"] and owner["start"] < end:
            errors.append(f"project area overlaps {owner['name']}")
    return errors
