# SPDX-License-Identifier: GPL-2.0-only
"""Phase-1 project experiments with native queued commands and synthetic data.

    tools/emu/.venv/bin/python tools/emu/project_cases.py research --base SYSTEM.VSB --report run.json

This is a research caller, not a project firmware implementation. Native flash reads
use an explicitly modelled dispatch adapter; native sample and slot-save commands do not.
"""

import argparse
import copy
import gc
import hashlib
import json
import struct
import sys
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/patch"), str(Path(__file__).parent)]

import fat32
import project_contract as contract
import sampleset
import unicorn
from machine import blank_flash
from project_probe import pattern_file
from sdcard import MemoryMedium, SDCard
from splash_cases import Dev

FLASH_BANK, RAM_BANK = 0x240000, 0xC08B2940
ARENA, ARENA_BYTES = 0xC3000000, 13 * 1024 * 1024
SCRATCH = 0xC3F00000
QUEUE, RUNNER, COMMANDS = 0xC002D5D8, 0xC034057C, 0xC03404C8
EXECUTORS = {0x0A: 0xC0038264, 0x22: 0xC0038D80}
FLASH_OBJECT, FLASH_READ = 0xC0029A40, 0xC002A090
ERASE, PROGRAM = 0xC001E7BC, 0xC001E6B0
SAMPLE_PATH, SAMPLE_META, SAMPLE_NAMES = 0xC0345A24, 0xC036AD88, 0xC047B08C
F_OPEN, F_READ = 0xC009DB60, 0xC009DD74
WORK, WORK_END = 0xC0D3A940, 0xC273AA40


def digest(data):
    return hashlib.sha256(data).hexdigest()


def renamed(block, label):
    data = bytearray(block)
    data[16:32] = label.encode("ascii")[:15].ljust(16, b"\0")
    return bytes(data)


@lru_cache(maxsize=1)
def synthetic_factory():
    from synth_probe import build_bank, expected_dsp
    waves = [(f"Own{i:03}", [((i * 13 + j * 29) % 3001) - 1500 for j in range(16)]) for i in range(411)]
    return build_bank(waves), expected_dsp(waves)


class ResearchDevice:
    def __init__(self, payload, card_files=None, flash=None):
        initial = blank_flash() if flash is None else bytearray(flash)
        if flash is None:
            initial[FLASH_BANK:FLASH_BANK + contract.BANK_BYTES] = pattern_file("BASE")[contract.FILE_PREFIX:]
            initial[0x800000:] = synthetic_factory()[0]
        self.dev = Dev(payload, initial)
        self.m, self.uc, self.A = self.dev.m, self.dev.m.uc, self.dev.m.A
        if self.m.profile.build not in ("stock", "hacktribe"):
            raise ValueError("project research has no measured Synth import addresses")
        self.events, self.spi, self.arena_accesses = [], [], []
        self.adapter, self.fault = None, None
        self.return_hooks, self.pending_returns = set(), {}
        self.native_reads, self.active_files = [], {}
        self.expected_files = card_files or {}
        self.identity_errors, self.identity_guard = [], False
        self.file_mutator = None
        self.source_contracts = {}
        self.read_adapter_calls = []
        self.factory_calls = []
        self.card_image = None
        self.uc.mem_write(ARENA, b"\xA7" * ARENA_BYTES)
        for start in (ARENA, ARENA + 0x4000000):
            self.uc.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE,
                             self.on_arena, begin=start, end=start + ARENA_BYTES - 1)
        for ident, address in EXECUTORS.items():
            self.uc.hook_add(unicorn.UC_HOOK_CODE, self.on_execute, ident, begin=address, end=address)
        for address in (ERASE, PROGRAM):
            self.uc.hook_add(unicorn.UC_HOOK_CODE, self.on_flash_driver, begin=address, end=address)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.on_open, begin=F_OPEN, end=F_OPEN)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.on_read, begin=F_READ, end=F_READ)
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self.on_factory, begin=0xC004D860, end=0xC004D860)
        original_erase, original_byte = self.m.flash.erase, self.m.flash.byte

        def erase(size):
            self.spi.append(dict(kind="erase", at=self.m.flash.addr & ~(size - 1), length=size))
            return original_erase(size)

        def byte(value):
            flash = self.m.flash
            result = original_byte(value)
            if flash.cmd == 0x02 and len(flash.buf) == 3 and flash.wel:
                self.spi.append(dict(kind="program", at=flash.addr, length=256))
            return result

        self.m.flash.erase, self.m.flash.byte = erase, byte
        if card_files:
            self.card_image = fat32.format_image(64 * 1024 * 1024)
            volume = fat32.Volume(self.card_image)
            for path, data in card_files.items():
                volume.write(path.removeprefix("SD:"), data)
            volume.close()
            self.m.insert_card(SDCard(MemoryMedium(self.card_image)))
        self.dev.run(1)
        if self.m.asserts:
            raise RuntimeError(f"native boot asserted: {self.m.asserts}")
        self.boot_spi = list(self.spi)
        self.spi.clear()

    def word(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def context(self):
        sp = self.uc.reg_read(self.A.UC_ARM_REG_SP)
        tcb = self.word(0xC06A289C)
        task = ((tcb - 0xC06A24E4) >> 5) + 1
        size, start = struct.unpack("<II", self.uc.mem_read(0xC00A37A8 + 4 * 32 + 16, 8))
        return dict(task=task, command_stack=start <= sp < start + size,
                    sp=hex(sp), mode=self.uc.reg_read(self.A.UC_ARM_REG_CPSR) & 31)

    def on_arena(self, uc, access, address, size, value, data):
        if len(self.arena_accesses) < 30:
            self.arena_accesses.append(dict(at=hex(address), size=size, access=access,
                                            pc=hex(uc.reg_read(self.A.UC_ARM_REG_PC))))

    def at_return(self, callback):
        address = self.uc.reg_read(self.A.UC_ARM_REG_LR)
        self.pending_returns.setdefault(address, []).append(callback)
        if address not in self.return_hooks:
            self.uc.hook_add(unicorn.UC_HOOK_CODE, self.on_return, begin=address, end=address)
            self.return_hooks.add(address)

    def on_return(self, uc, address, size, data):
        for callback in self.pending_returns.pop(address, []):
            callback()

    def on_execute(self, uc, address, size, ident):
        event = dict(command=ident, context=self.context(), object=uc.reg_read(self.A.UC_ARM_REG_R0))
        self.events.append(event)
        self.at_return(lambda: event.update(returned=True, result=uc.reg_read(self.A.UC_ARM_REG_R0)))
        if self.adapter:
            target, args = self.adapter
            self.adapter = None
            event["research_adapter"] = hex(target)
            for index, value in enumerate(args):
                uc.reg_write(self.A.UC_ARM_REG_R0 + index, value)
            uc.reg_write(self.A.UC_ARM_REG_PC, target)

    def on_factory(self, uc, address, size, data):
        event = dict(context=self.context(), args=[uc.reg_read(self.A.UC_ARM_REG_R0 + i) for i in range(2)])
        self.factory_calls.append(event)
        self.at_return(lambda: event.update(result=uc.reg_read(self.A.UC_ARM_REG_R0)))

    def on_flash_driver(self, uc, address, size, data):
        fault = self.fault
        if fault and not fault["fired"] and address == fault["entry"] and uc.reg_read(self.A.UC_ARM_REG_R1) == fault["index"]:
            fault["fired"] = True
            fault["context"] = self.context()
            if fault.get("capture_power_state"):
                self.power_cut_image = bytes(self.m.flash.mem)
                return
            uc.reg_write(self.A.UC_ARM_REG_R0, 0)
            uc.reg_write(self.A.UC_ARM_REG_PC, uc.reg_read(self.A.UC_ARM_REG_LR))

    def on_open(self, uc, address, size, data):
        obj, pointer = uc.reg_read(self.A.UC_ARM_REG_R0), uc.reg_read(self.A.UC_ARM_REG_R1)
        path = bytes(uc.mem_read(pointer, 256)).split(b"\0")[0].decode("ascii", errors="replace")
        if path in self.expected_files:
            self.active_files[obj] = path
        else:
            self.active_files.pop(obj, None)

    def on_read(self, uc, address, size, data):
        obj = uc.reg_read(self.A.UC_ARM_REG_R0)
        if obj not in self.active_files:
            return
        path = self.active_files[obj]
        offset, destination = self.word(obj + 8), uc.reg_read(self.A.UC_ARM_REG_R1)
        amount, count = uc.reg_read(self.A.UC_ARM_REG_R2), uc.reg_read(self.A.UC_ARM_REG_R3)
        if self.file_mutator:
            self.file_mutator(path, offset, amount)

        def returned():
            got = self.word(count)
            result = uc.reg_read(self.A.UC_ARM_REG_R0)
            payload = bytes(uc.mem_read(destination, got)) if got else b""
            matches = payload == self.expected_files[path][offset:offset + got]
            identity = self.source_contracts.get(path)
            if identity and got and result == 0:
                try:
                    identity.observe(offset, payload)
                except ValueError:
                    matches = False
            self.native_reads.append(dict(path=path, offset=offset, requested=amount, length=got,
                                          result=result, matches=matches, destination=hex(destination)))
            if not matches:
                self.identity_errors.append(dict(path=path, offset=offset, length=got))
                if self.identity_guard:
                    uc.reg_write(self.A.UC_ARM_REG_R0, 1)
        self.at_return(returned)

    def queue(self, ident, first=0, second=0, timeout=30):
        seen = len(self.events)
        self.dev.call(QUEUE, ident, first, second)
        end = self.m.time_ns / 1e9 + timeout
        while (len(self.events) == seen or self.word(self.word(RUNNER) + 0x10) & 0xFF) and self.m.time_ns / 1e9 < end and not self.m.asserts:
            self.m.run_until(self.m.time_ns / 1e9 + 0.02)
        if len(self.events) == seen or self.word(self.word(RUNNER) + 0x10) & 0xFF or self.m.asserts:
            raise RuntimeError(f"command {ident:#x} did not finish: {self.m.asserts}")
        event = self.events[seen]
        event["status"] = bytes(self.uc.mem_read(event["object"] + 0x18, 1))[0]
        if not event.get("returned"):
            raise RuntimeError("native command did not return through its dispatcher")
        return event

    def native_read(self, destination=ARENA):
        obj = self.dev.call(FLASH_OBJECT)
        self.adapter = FLASH_READ, (obj, destination, 0, contract.BANK_BYTES)
        event = self.queue(0x0A)
        if event["result"] != 1:
            raise RuntimeError("native flash bank read failed")
        self.read_adapter_calls.append(dict(destination=hex(destination), length=contract.BANK_BYTES,
                                            context=event["context"]))
        return bytes(self.uc.mem_read(destination, contract.BANK_BYTES))

    def replace_file_data(self, path, data):
        volume = fat32.Volume(self.card_image)
        entry = volume.stat(path.removeprefix("SD:"))
        if len(data) != entry.size:
            raise ValueError("source mutation must preserve file size and cluster allocation")
        volume._write_clusters(volume.chain(entry.cluster), data)

    def call_in_command(self, target, *args):
        self.adapter = target, args
        return self.queue(0x0A)

    def refresh_current(self, selection=0):
        manager = self.word(0xC034029C)
        event = self.call_in_command(0xC0079CF8, manager, selection, 1)
        self.m.run_until(self.m.time_ns / 1e9 + 0.1)
        return event

    def flash_bank(self):
        return bytes(self.m.flash.mem[FLASH_BANK:FLASH_BANK + contract.BANK_BYTES])

    def ram_bank(self):
        return bytes(self.uc.mem_read(RAM_BANK, contract.BANK_BYTES))

    def slots(self):
        return {str(i): bytes(self.uc.mem_read(SAMPLE_NAMES + i * 32, 16)).split(b"\0")[0].decode("ascii")
                for i in range(500, 1000) if bytes(self.uc.mem_read(SAMPLE_META + i * 0x45C + 11, 1))[0] == 1}

    def import_samples(self, path, timeout=30):
        self.uc.mem_write(SCRATCH, path.encode("ascii") + b"\0")
        self.dev.call(0xC00A26C0, SAMPLE_PATH, SCRATCH)
        return self.queue(0x22, 501, 0, timeout)

    def write_slot(self, index, block):
        self.uc.mem_write(RAM_BANK + index * contract.BLOCK_SIZE, block)
        return self.queue(0x0A, index)


def full_sample_research(payload):
    from sample_full import FACTORY_END, LIMIT

    path = "SD:KORG/blechtribe/Projects/FULL/e2sSample.all"
    frames = (LIMIT - FACTORY_END) // 2 - 32
    raw = sampleset.build({500: ("FULL-501", frames)})
    box = ResearchDevice(payload, {path: raw})
    arena_before = digest(box.uc.mem_read(ARENA, ARENA_BYTES))
    box.uc.mem_write(WORK, b"\x5A" * (WORK_END - WORK))
    flash_before = digest(box.m.flash.mem)
    first = box.m.time_ns
    event = box.import_samples(path, timeout=600)
    work = bytes(box.uc.mem_read(WORK, WORK_END - WORK))
    block = 4096
    high = next((end for end in range(len(work), 0, -block)
                 if work[max(0, end - block):end] != b"\x5A" * min(block, end)), 0)
    detail = dict(file_bytes=len(raw), pcm_bytes=2 * frames, headroom_bytes=LIMIT - FACTORY_END - 2 * frames,
                  event=event, active=box.slots(), cursor=hex(box.word(0xC00F9C80)),
                  work_changed_high_water=high, arena_cpu_accesses=box.arena_accesses,
                  arena_unchanged=digest(box.uc.mem_read(ARENA, ARENA_BYTES)) == arena_before,
                  native_read_calls=len(box.native_reads), native_read_bytes=sum(r["length"] for r in box.native_reads),
                  device_seconds=(box.m.time_ns - first) / 1e9, instructions=box.m.insns)
    return dict(checks=[dict(name="near-capacity-sample-memory-footprint", ok=event["status"] == 0
                            and box.slots() == {"500": "FULL-501"} and detail["arena_unchanged"]
                            and not box.arena_accesses and digest(box.m.flash.mem) == flash_before,
                            detail=detail)],
                assumptions=["Work buffer is poisoned only in the research model before the import.",
                             "Changed-page high water complements CPU arena watches; it is not a DMA or hardware proof."])


def sample_research(payload, full=False):
    a = "SD:KORG/blechtribe/Projects/A/e2sSample.all"
    b = "SD:KORG/blechtribe/Projects/B live 02/e2sSample.all"
    guard = "SD:KORG/blechtribe/Projects/CHECK/e2sSample.all"
    files = {a: sampleset.build({500: ("A-501", 32), 501: ("A-502", 48)}),
             b: sampleset.build({500: ("B-501", 96), 502: ("B-503", 16)}),
             guard: sampleset.build({500: ("CHECK", 8192)})}
    for kind, frames in (("pcm24", 44101), ("stereo16", 20000)):
        files[f"SD:KORG/blechtribe/Projects/{kind}/e2sSample.all"] = sampleset.build({500: (kind, frames, 48000, kind)})
    box = ResearchDevice(payload, files)
    checks = []

    def check(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=copy.deepcopy(detail)))

    card_before, flash_before = digest(box.card_image), bytes(box.m.flash.mem)
    for path, expected in ((a, {"500": "A-501", "501": "A-502"}),
                           (b, {"500": "B-501", "502": "B-503"}),
                           (a, {"500": "A-501", "501": "A-502"})):
        event = box.import_samples(path)
        check("native-samples-" + path.split("/")[-2], event["status"] == 0 and box.slots() == expected,
              dict(event=event, active=box.slots()))
    check("runtime-import-does-not-copy-card-files", digest(box.card_image) == card_before,
          dict(before=card_before, after=digest(box.card_image)))
    check("sample-import-does-not-change-flash", bytes(box.m.flash.mem) == flash_before,
          dict(before=digest(flash_before), after=digest(box.m.flash.mem)))

    format_reads = []
    for kind in ("pcm24", "stereo16"):
        path = f"SD:KORG/blechtribe/Projects/{kind}/e2sSample.all"
        raw = files[path]
        ranges = contract.native_sample_read_ranges(raw)
        identity = contract.SourceIdentity.from_ranges(raw, ranges)
        box.source_contracts[path] = identity
        box.native_reads.clear()
        event = box.import_samples(path)
        reads = [r for r in box.native_reads if r["path"] == path and r["length"] and r["result"] == 0]
        observed = {(r["offset"], r["length"]) for r in reads}
        completed = False
        try:
            completed = identity.complete()
        except ValueError:
            pass
        detail = dict(format=kind, event=event, preflight_ranges=len(ranges), observed_ranges=len(observed),
                      largest_native_read=max((r["length"] for r in reads), default=0),
                      source_complete=completed, source_matches=all(r["matches"] for r in reads))
        check("metadata-derived-native-ranges-" + kind, event["status"] == 0 and completed
              and set(ranges) == observed and detail["source_matches"], detail)
        format_reads.append(detail)
    box.native_reads.clear()
    event = box.import_samples(guard)
    reads = [r for r in box.native_reads if r["path"] == guard and r["length"] and r["result"] == 0]
    ranges = contract.native_sample_read_ranges(files[guard])
    observed_ranges = {(r["offset"], r["length"]) for r in reads}
    identity = contract.SourceIdentity.from_ranges(files[guard], ranges)
    for read in reads:
        identity.observe(read["offset"], files[guard][read["offset"]:read["offset"] + read["length"]])
    check("metadata-derived-native-file-ranges-bound", event["status"] == 0 and identity.complete()
          and observed_ranges == set(ranges) and all(r["matches"] for r in reads),
          dict(event=event, calls=len(reads), unique_ranges=len(ranges), ranges=ranges,
               preflight="ranges derived from file metadata before any import; trace only validates the prediction"))
    mutant = bytearray(files[guard])
    mutant[4096 + 44 + 1024] ^= 0x7F
    box.source_contracts[guard] = contract.SourceIdentity.from_ranges(files[guard], ranges)
    box.identity_guard = True
    mutated = []

    def mutate(path, offset, amount):
        if path == guard and not mutated:
            box.replace_file_data(guard, bytes(mutant))
            mutated.append(True)

    box.file_mutator = mutate
    original_observe = box.source_contracts[guard].observe

    def observe(offset, data):
        try:
            return original_observe(offset, data)
        except ValueError:
            box.replace_file_data(guard, files[guard])
            raise

    box.source_contracts[guard].observe = observe
    event = box.import_samples(guard)
    box.file_mutator = None
    check("same-size-A-B-A-consumed-source-change-rejected", bool(box.identity_errors) and event["status"] != 0
          and digest(box.card_image) == card_before,
          dict(event=event, mismatches=box.identity_errors, card_restored=digest(box.card_image) == card_before,
               guard="research hook checks actual returned bytes before the native consumer and reports a read error"))
    check("native-source-error-clears-partial-user-bank", not box.slots(), box.slots())

    box.identity_guard = False
    box.source_contracts.clear()
    box.import_samples(a)
    before_no_card = box.flash_bank()
    box.m.eject_card()
    from mfx_cases import DspLog
    dsp = DspLog(box.m)
    first_factory_call = len(box.factory_calls)
    event = box.import_samples(a)
    expected_dsp = synthetic_factory()[1]
    factory_transfers = [x for x in dsp.xfers if x[0] == 0xAB and x[1] < 0x1C65EC0 and x[2] == len(expected_dsp) // 2]
    transfers = [struct.pack(f"<{len(x[3])}H", *x[3]) for x in factory_transfers]
    calls = box.factory_calls[first_factory_call:]
    check("queued-missing-card-native-factory-recovery", event["status"] != 0 and not box.slots()
          and bool(calls) and all(c["result"] == 1 and c["context"]["task"] == 5 for c in calls)
          and transfers == [expected_dsp],
          dict(event=event, user_slots=box.slots(), native_factory_calls=calls,
               dsp_words=len(expected_dsp) // 2, expected_pcm_sha256=digest(expected_dsp),
               observed_pcm_sha256=[digest(x) for x in transfers],
               no_card_boot_factory_calls=len([c for c in box.factory_calls[:first_factory_call] if c["args"][1] == 1]),
               note="Hacktribe's error fallback loads its factory manager even though its no-card startup skips that path"))
    box.native_read(RAM_BANK)
    box.refresh_current(0)
    editor = box.word(0xC033E6A4) + 4
    check("no-card-native-flash-and-editor-recovery", box.ram_bank() == before_no_card
          and bytes(box.uc.mem_read(editor + 16, 16)) == before_no_card[16:32],
          dict(flash=digest(before_no_card), ram=digest(box.ram_bank()),
               editor_name=bytes(box.uc.mem_read(editor + 16, 16)).split(b"\0")[0].decode("ascii")))
    check("sample-commands-actual-command-task", all(e["context"]["task"] == 5 and e["context"]["command_stack"] for e in box.events),
          [dict(command=e["command"], context=e["context"]) for e in box.events])
    check("sample-routes-no-unexpected-arena-CPU-access", not box.arena_accesses, box.arena_accesses)
    check("sample-routes-no-native-assert", not box.m.asserts, box.m.asserts)
    return dict(checks=checks, native_file_reads=box.native_reads, format_reads=format_reads,
                read_adapters=box.read_adapter_calls,
                model_source_guard=True, remaining=["derive all read-range fingerprints for every accepted sample format",
                                                    "enforce scoped guard in a native project owner", "full-load footprint"])


def research(payload, include_mfx=True, full=False):
    box = ResearchDevice(payload)
    checks = []

    def check(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=copy.deepcopy(detail)))

    check("no-card-boot", box.dev.screen()["number"] == 1 and not box.m.asserts,
          dict(screen=box.dev.screen()["number"], asserts=box.m.asserts))
    check("no-card-boot-keeps-synthetic-flash-patterns", box.ram_bank() == box.flash_bank(),
          dict(flash=digest(box.flash_bank()), ram=digest(box.ram_bank())))
    check("no-card-boot-no-pattern-program", not any(FLASH_BANK <= e["at"] < FLASH_BANK + contract.BANK_BYTES for e in box.boot_spi), box.boot_spi)
    before = box.flash_bank()
    read = box.native_read()
    check("native-indexed-flash-read-in-command-task", read == before, box.events[-1])
    box.spi.clear()
    box.uc.mem_write(RAM_BANK, bytes(contract.BANK_BYTES))
    selected = contract.changed_slots(box.native_read(), before)
    for index in selected:
        box.write_slot(index, before[index * contract.BLOCK_SIZE:(index + 1) * contract.BLOCK_SIZE])
    box.uc.mem_write(RAM_BANK, before)
    check("flash-identical-project-ram-different-no-writes", not selected and not box.spi,
          dict(changed=selected, spi=box.spi))

    slot = 2
    old = before[slot * contract.BLOCK_SIZE:(slot + 1) * contract.BLOCK_SIZE]
    target = renamed(old, "A-prime")
    target_bank = bytearray(before)
    target_bank[slot * contract.BLOCK_SIZE:(slot + 1) * contract.BLOCK_SIZE] = target
    box.spi.clear()
    chosen = contract.changed_slots(box.native_read(), target_bank)
    result = box.write_slot(slot, target)
    check("one-changed-slot-native-queue-store", chosen == [slot] and result["status"] == 0 and box.flash_bank() == target_bank,
          dict(changed=chosen, event=result, spi=box.spi))
    lo, hi = FLASH_BANK + slot * contract.BLOCK_SIZE, FLASH_BANK + (slot + 1) * contract.BLOCK_SIZE
    check("native-writes-only-changed-slot", bool(box.spi) and all(lo <= e["at"] and e["at"] + e["length"] <= hi for e in box.spi), box.spi)
    box.spi.clear()
    again = contract.changed_slots(box.native_read(), target_bank)
    check("identical-reimport-no-native-program", not again and not box.spi, dict(changed=again, spi=box.spi))

    flash_before = bytes(box.m.flash.mem)
    baseline = box.flash_bank()
    operation = contract.ImportOperation()
    operation.acquire(operation.confirmation())
    operation.capture(flash=baseline, ram=box.ram_bank(), editor=target, selection=slot, mfx=b"")
    damaged = bytearray(renamed(target, "B-failed"))
    damaged[0x2000 + 123] ^= 0x55
    damaged = bytes(damaged)
    box.fault = dict(entry=ERASE, index=(lo // 4096) + 1, fired=False)
    event = operation.attempt(slot, lambda i: box.write_slot(i, damaged))
    failed_image = box.flash_bank()
    check("late-erase-failure-propagates", box.fault["fired"] and event["status"] != 0 and failed_image != baseline,
          dict(event=event, fault=box.fault, changed=contract.changed_slots(baseline, failed_image)))
    box.fault = None
    restored = operation.rollback_targets(box.native_read())
    for index, block in restored.items():
        box.write_slot(index, block)
    verified = box.native_read()
    recovered = operation.recovered(verified)
    check("partial-write-recovery-keeps-A-prime", verified == baseline and recovered["editor"] == target,
          dict(restored=list(restored), before=digest(baseline), after=digest(verified)))
    check("write-and-rollback-no-outside-flash-change", bytes(box.m.flash.mem) == flash_before,
          dict(before=digest(flash_before), after=digest(box.m.flash.mem)))

    box.fault = dict(entry=PROGRAM, index=(lo // 256) + 5, fired=False)
    event = box.write_slot(slot, renamed(target, "PAGE-failed"))
    mismatches = contract.changed_slots(baseline, box.native_read())
    check("page-failure-needs-readback", box.fault["fired"] and mismatches == [slot],
          dict(event=event, fault=box.fault, readback_changed=mismatches,
               native_reported_success=event["status"] == 0))
    box.fault = None
    box.write_slot(slot, target)
    box.native_read(RAM_BANK)
    check("native-read-restores-entire-ram-bank", box.ram_bank() == baseline,
          dict(expected=digest(baseline), ram=digest(box.ram_bank())))

    failed_recovery = contract.ImportOperation()
    failed_recovery.acquire(failed_recovery.confirmation())
    failed_recovery.capture(flash=baseline, ram=box.ram_bank(), editor=target, selection=slot, mfx=b"")
    failed_recovery.attempt(slot, lambda i: box.write_slot(i, damaged))
    box.fault = dict(entry=ERASE, index=(lo // 4096) + 1, fired=False)
    event = box.write_slot(slot, target)
    not_restored = box.native_read()
    accepted = True
    try:
        failed_recovery.recovered(not_restored)
    except ValueError:
        accepted = False
    check("failed-rollback-keeps-model-operation-unready", box.fault["fired"] and event["status"] != 0
          and not accepted and failed_recovery.locked and not_restored != baseline,
          dict(event=event, fault=box.fault, model_accepted_recovery=accepted,
               native_project_error_state_implemented=False))
    box.fault = None
    box.write_slot(slot, target)

    power_slot = 0
    box.fault = dict(entry=PROGRAM, index=(FLASH_BANK // 256) + 2, fired=False, capture_power_state=True)
    box.write_slot(power_slot, renamed(before[:contract.BLOCK_SIZE], "POWER-cut"))
    power_image = box.power_cut_image
    try:
        restarted = ResearchDevice(payload, flash=power_image)
        power_boot = dict(screen=restarted.dev.screen()["number"], asserts=restarted.m.asserts,
                          interrupted_pattern_sha256=digest(power_image[FLASH_BANK:FLASH_BANK + contract.BLOCK_SIZE]),
                          flash_sha256=digest(power_image))
        power_ok = power_boot["screen"] == 1 and not power_boot["asserts"]
    except RuntimeError as error:
        power_boot, power_ok = dict(error=str(error)), False
    check("partial-page-power-cut-native-no-card-reboot", box.fault["fired"] and power_ok, power_boot)
    box.fault = None
    box.write_slot(power_slot, before[:contract.BLOCK_SIZE])
    check("native-task-and-stack", all(e["context"]["task"] == 5 and e["context"]["command_stack"] for e in box.events),
          [dict(command=e["command"], adapter=e.get("research_adapter"), context=e["context"]) for e in box.events])
    check("native-no-unexpected-arena-CPU-access", not box.arena_accesses,
          dict(cpu_accesses=box.arena_accesses, intentional_read_adapters=box.read_adapter_calls,
               model_note="accelerated low-level flash read writes via the host API, outside CPU memory hooks"))
    check("native-no-assert", not box.m.asserts, box.m.asserts)
    samples = sample_research(payload, full)
    checks.extend(samples.pop("checks"))
    mfx = None
    if include_mfx:
        from project_mfx_cases import probe as mfx_probe
        mfx = mfx_probe(payload, box.m.profile.build)
        checks.extend(mfx.pop("checks"))
        gc.collect()
    from project_input_cases import probe as input_probe
    inputs = input_probe(payload, ResearchDevice)
    checks.extend(inputs.pop("checks"))
    gc.collect()
    footprint = None
    if full:
        footprint = full_sample_research(payload)
        checks.extend(footprint.pop("checks"))
    return dict(build=box.m.profile.build, checks=checks,
                samples=samples, mfx=mfx, inputs=inputs, footprint=footprint,
                assumptions=["Host contract chooses changed slots; no native project compare/loader is implemented.",
                             "Native commands 0x0A and 0x22 execute through the original queue in CommandTask.",
                             "Read-only bank helper is called via a one-command research dispatch adapter.",
                             "One driver failure is injected by returning failure, after earlier native SPI operations.",
                             "DSP and SD hardware are emulated; no sound or physical device access."],
                remaining=["native input/file exclusion", "native source-guard integration", "native composite MFX rollback"]
                + ([] if full else ["full-load memory footprint"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["research"])
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    raw = args.base.read_bytes()
    if len(raw) != 0x200100:
        raise ValueError("a complete firmware 2.02 VSB is required")
    result = research(raw[0x100:], full=args.full)
    result["input_sha256"] = digest(raw)
    result["research_sha256"] = digest(Path(__file__).read_bytes())
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(dict(build=result["build"], checks=len(result["checks"]),
                          failed=[c["name"] for c in result["checks"] if not c["ok"]])))
    return 0 if all(c["ok"] for c in result["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
