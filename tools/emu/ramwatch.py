# SPDX-License-Identifier: GPL-2.0-only
"""Write watch on the RAM that BLECH owns in the image, and a map of the pages a run touched.

BLECH keeps its code, its state and its buffers in the free block of the image, `0xC01A2100` to
`0xC01FFFF0` (docs/patcher.md), and replaces some words of the firmware by branches. This module
hooks every write into the image and into its 64 MiB alias and says who wrote: our own code (a
program counter in the free block) or the firmware. The firmware writes variables of its own in
the image, so only a write into a BLECH range counts as foreign
(docs/messungen/2026-10-14-sample-speicher-voll.md).
"""

import collections

import unicorn

IMAGE = (0xC0000000, 0xC0200000)
ALIAS = 0x04000000                    # the RAM dump repeats the first 64 MiB (docs/messungen/2026-10-07-cpu-ram-fenster.md)
FREE_BASE, FREE_END = 0xC01A2100, 0xC01FFFF0
OWN_CODE = (0xC0180000, IMAGE[1])      # a program counter here is our own code (the pattern switch and the loading bar start at 0xC0180000)
PAGE = 0x1000


def diff_runs(base, patched, header=0x100, gap=8):
    """Address ranges `(start, end)` in the image where the two VSB files differ, runs closer than `gap` joined."""
    runs = []
    a, b = memoryview(base)[header:], memoryview(patched)[header:]
    if len(a) != len(b):
        raise ValueError("the two files differ in size")
    i, n = 0, len(a)
    while i < n:
        if a[i] == b[i]:
            i += 1
            continue
        start = last = i
        i += 1
        while i < n and i - last <= gap:
            if a[i] != b[i]:
                last = i
            i += 1
        runs.append((IMAGE[0] + start, IMAGE[0] + last + 1))
    return runs


def areas(layout):
    """The named parts of the free block, in address order, from the layout `script_hooks.build` reports
    and the fixed places of the older patches (tools/patch/splash_editor.py, mfx_switch.py)."""
    from tools.patch import script_hooks as h
    out = [
        ("splash editor code", 0xC01A2100, 0xC01A3C00),
        ("splash editor vtable copy", 0xC01A3C00, 0xC01A4000),
        ("splash editor state and buffers", 0xC0182000, 0xC0183000),
        ("Blechy's block (read only, the app built into BLECH)", h.BLECHY_BLOCK, h.BLECHY_BLOCK + len(h.blechy_block())),
        ("power-off picture code and frame", 0xC01A4A00, 0xC01A5000),
        ("MFX 2 code", 0xC01A5000, 0xC01A5C00),
        ("MFX 2 state and record", 0xC01A5C00, 0xC01A5E20),
        ("runtime code (VM, hooks, card, menu)", layout["code"], layout["codeEnd"]),
        ("menu screen table and class copy", h.MENU_TABLE, h.MENU_VTABLE + 72),
        ("runtime state, ring, LED", layout["runtime"], layout["runtimeEnd"]),
        ("menu items", h.MENU_ITEMS, h.MENU_ITEMS_END),
        ("menu state and settings buffers", h.MENU_STATE, h.MENU_STATE + 0x200),
        ("plugin pool", layout["pool"], layout["poolEnd"]),
        ("card work area (FIL, loader state)", layout["card"], layout["input"]),
        ("block buffer (file reads land here)", layout["input"], FREE_END),
    ]
    return out


class Watch:
    """Hooks all writes into the image and its alias. `blech` are the ranges that must stay the
    firmware's hands off: named areas of the free block and the words the patches changed."""

    def __init__(self, machine, named, patched_words, io=("card work area (FIL, loader state)", "block buffer (file reads land here)", "splash editor state and buffers")):
        self.m = machine
        self.A = machine.A
        self.named = sorted(named, key=lambda x: x[1])
        self.words = patched_words
        self.io = set(io)
        self.counts = collections.Counter()      # (kind, name) -> writes
        self.foreign = []                        # first foreign writes, as dicts
        self.foreign_pcs = collections.Counter()
        self.firmware_data = collections.Counter()   # 256-byte block in the image outside BLECH ranges -> writes by the firmware
        self.firmware_pcs = collections.defaultdict(set)
        self.io_times = []                       # device time of the first and last foreign write into an I/O buffer
        self.io_screens = collections.Counter()  # foreign writes into an I/O buffer by the screen the firmware showed
        self.alias_writes = []
        self.total = 0
        for lo, hi in (IMAGE, (IMAGE[0] + ALIAS, IMAGE[1] + ALIAS)):
            machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, self._write, begin=lo, end=hi - 1)
        machine.uc.ctl_flush_tb()

    def owner(self, addr):
        """Name of the BLECH range an address is in, else None."""
        for name, lo, hi in self.named:
            if lo <= addr < hi:
                return name
        if FREE_BASE <= addr < FREE_END:
            return "free block, unused part"
        for lo, hi in self.words:
            if lo <= addr < hi:
                return "word the patches changed"
        return None

    def _write(self, uc, access, addr, size, value, _):
        m = self.m
        self.total += 1
        pc = m.reg(self.A.UC_ARM_REG_PC)
        base = addr - ALIAS if addr >= IMAGE[0] + ALIAS else addr
        name = self.owner(base)
        if addr != base:
            if len(self.alias_writes) < 50:
                self.alias_writes.append(dict(pc=pc, addr=addr, size=size, ms=round(m.time_ns / 1e6, 2)))
            self.counts[("alias", name or "outside BLECH")] += 1
            if name is None:
                return
        own = OWN_CODE[0] <= pc < OWN_CODE[1]
        if name is None:
            if not own:
                self.firmware_data[base >> 8] += 1
                if len(self.firmware_pcs[base >> 8]) < 6:
                    self.firmware_pcs[base >> 8].add(pc)
            return
        if own:
            self.counts[("own", name)] += 1
            return
        kind = "foreign io" if name in self.io else "foreign"
        self.counts[(kind, name)] += 1
        if kind == "foreign io":
            now = round(m.time_ns / 1e6, 2)
            self.io_times = [self.io_times[0] if self.io_times else now, now]
            self.io_screens[m.screen()] += 1
            return
        self.foreign_pcs[pc] += 1
        if len(self.foreign) < 40:
            self.foreign.append(dict(pc=pc, addr=addr, size=size, value=value & 0xFFFFFFFF, area=name, ms=round(m.time_ns / 1e6, 2)))

    def report(self):
        rows = collections.defaultdict(lambda: {"own": 0, "foreign": 0, "foreign io": 0, "alias": 0})
        for (kind, name), n in self.counts.items():
            rows[name][kind] += n
        blocks = sorted(self.firmware_data)
        runs = []
        for b in blocks:
            if runs and b - runs[-1][1] <= 16:
                runs[-1][1] = b
                runs[-1][2] += self.firmware_data[b]
            else:
                runs.append([b, b, self.firmware_data[b]])
        return dict(
            writes_total=self.total,
            by_area={k: v for k, v in sorted(rows.items())},
            foreign=self.foreign,
            foreign_count=sum(v["foreign"] for v in rows.values()),
            foreign_io_count=sum(v["foreign io"] for v in rows.values()),
            foreign_io_window_ms=self.io_times,
            foreign_io_by_screen={str(k): v for k, v in sorted(self.io_screens.items(), key=lambda x: str(x[0]))},
            alias_writes=self.alias_writes,
            alias_count=sum(v["alias"] for v in rows.values()),
            firmware_in_image=[dict(start=r[0] << 8, end=(r[1] << 8) + 0x100, writes=r[2]) for r in runs],
        )


def non_zero_pages(machine, lo=0xC0200000, hi=0xC8000000, chunk=0x100000):
    """Indices (address // 4096) of the pages in [lo, hi) that hold anything but zeros."""
    zero = bytes(PAGE)
    out = set()
    for base in range(lo, hi, chunk):
        data = bytes(machine.uc.mem_read(base, min(chunk, hi - base)))
        for off in range(0, len(data), PAGE):
            if data[off:off + PAGE] != zero:
                out.add((base + off) // PAGE)
    return out


def page_runs(pages, gap=1):
    """Sorted page indices as `(first address, end address)` runs; pages up to `gap` apart are joined."""
    runs = []
    for p in sorted(pages):
        if runs and p - runs[-1][1] <= gap:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    return [(a * PAGE, (b + 1) * PAGE) for a, b in runs]


def dsp_transfers(machine, log):
    """Record the sample data writes to the DSP. `log` gets one dict per call of the firmware's DSP write
    (0xC0014284: r0 byte offset in the DSP memory, r1 source in CPU RAM, r2 count of 16-bit words) whose
    destination is in sample memory (below 0xFF000000); the host port itself is counted by the caller."""
    A = machine.A

    def hook(uc, addr, size, _):
        r0, r1, r2 = (uc.reg_read(r) for r in (A.UC_ARM_REG_R0, A.UC_ARM_REG_R1, A.UC_ARM_REG_R2))
        if r0 < 0xFF000000:
            log.append((round(machine.time_ns / 1e6, 1), r0, r1, r2, uc.reg_read(A.UC_ARM_REG_LR)))
    machine.uc.hook_add(unicorn.UC_HOOK_CODE, hook, begin=0xC0014284, end=0xC0014284)
    machine.uc.ctl_flush_tb()
