#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Führt originale ARM-Doom-Engine mit einem dateibasierten Testadapter aus."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_INTR, UC_HOOK_MEM_INVALID, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_PC, UC_ARM_REG_SP, UC_CPU_ARM_926


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--wad", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", default=120, type=int)
    parser.add_argument("--input", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    symbols = {}
    for line in (args.build / "symbols.txt").read_text().splitlines():
        items = line.split()
        if len(items) == 3:
            symbols[items[2]] = int(items[0], 16)
    wad = args.wad.read_bytes()
    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.ctl_set_cpu_model(UC_CPU_ARM_926)
    uc.mem_map(0x01000000, 0x06000000)
    uc.mem_write(0x01000000, (args.build / "doom-probe.bin").read_bytes())
    stack_initial = 0x06FFF000
    stack_window_bottom = stack_initial - 1024 * 1024
    stack_lowest_write = stack_initial
    stack_lowest_sp = stack_initial
    stack_write_count = 0
    uc.reg_write(UC_ARM_REG_SP, stack_initial)
    descriptors = {}
    logs = []
    frames = []
    reads = 0
    read_bytes = 0
    failures = []
    keys = []
    stopped = False

    def u32(symbol):
        return struct.unpack("<I", uc.mem_read(symbols[symbol], 4))[0]

    def cstr(address):
        value = bytearray()
        for i in range(4096):
            byte = uc.mem_read(address+i, 1)[0]
            if not byte:
                return value.decode("utf-8", errors="replace")
            value.append(byte)
        raise ValueError("Zeichenkette ohne Terminator")

    def interrupt(_uc, number, _data):
        nonlocal stopped, reads, read_bytes
        if number != 2:
            raise RuntimeError(f"Unerwarteter Interrupt {number}")
        op, a, b, c = [uc.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = -1
        if op == 1:
            path = cstr(a)
            if Path(path).name == "freedoom1.wad" and b & 3 == 0:
                result = max([2, *descriptors]) + 1
                descriptors[result] = 0
        elif op == 2:
            result = 0 if descriptors.pop(a, None) is not None else -1
        elif op == 3 and a in descriptors:
            position = descriptors[a]
            data = wad[position:position+c]
            uc.mem_write(b, data)
            descriptors[a] += len(data)
            result = len(data)
            reads += 1
            read_bytes += len(data)
        elif op == 4:
            data = bytes(uc.mem_read(b, c))
            logs.append(data.decode("utf-8", errors="replace"))
            result = c
        elif op == 5 and a in descriptors:
            offset = struct.unpack("<i", struct.pack("<I", b))[0]
            result = offset + (0 if c == 0 else descriptors[a] if c == 1 else len(wad))
            if result >= 0:
                descriptors[a] = result
        elif op == 6:
            result = len(wad) if Path(cstr(a)).name == "freedoom1.wad" else -1
        elif op == 7:
            failures.append(f"Engine exit {a}")
            stopped = True
            uc.emu_stop()
        elif op == 8:
            display = bytes(uc.mem_read(a, 1024))
            rgb = bytes(uc.mem_read(b, 320*200*4))
            frame = {"frame":c, "gametic":u32("gametic"), "gamestate":u32("gamestate"), "display_sha256":hashlib.sha256(display).hexdigest(), "rgb_sha256":hashlib.sha256(rgb).hexdigest(), "lit_pixels":sum(value.bit_count() for value in display), "viewangle":u32("viewangle")}
            frames.append(frame)
            if c in (1, args.frames):
                bitmap = bytes(sum(((display[(y>>3)*128+x+i] >> (y&7)) & 1) << (7-i) for i in range(8)) for y in range(64) for x in range(0,128,8))
                (args.output / f"frame-{c:03}.pbm").write_bytes(b"P4\n128 64\n"+bitmap)
            if len(frames) >= args.frames:
                stopped = True
                uc.emu_stop()
            result = 0
        elif op == 9:
            result = 0
            tick = u32("gametic")
            if args.input and ((not keys and tick >= 2) or (len(keys) == 1 and tick >= 12)):
                pressed = int(not keys)
                uc.mem_write(a, struct.pack("<I", pressed))
                uc.mem_write(b, bytes([0xAE]))
                keys.append({"gametic":tick, "pressed":pressed, "key":174})
                result = 1
        else:
            failures.append(f"Unbekannter Systemaufruf {op} ({a}, {b}, {c})")
            stopped = True
            uc.emu_stop()
        uc.reg_write(UC_ARM_REG_R0, result & 0xFFFFFFFF)

    def invalid(_uc, access, address, size, value, _data):
        failures.append(f"Ungültiger Speicherzugriff Typ {access}: 0x{address:08x}, {size} Byte")
        return False

    def stack_write(_uc, access, address, size, value, _data):
        nonlocal stack_lowest_write, stack_lowest_sp, stack_write_count
        stack_lowest_write = min(stack_lowest_write, address)
        stack_lowest_sp = min(stack_lowest_sp, uc.reg_read(UC_ARM_REG_SP))
        stack_write_count += 1

    uc.hook_add(UC_HOOK_MEM_WRITE, stack_write, begin=stack_window_bottom, end=stack_initial-1)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.hook_add(UC_HOOK_MEM_INVALID, invalid)
    started = time.monotonic()
    try:
        uc.reg_write(UC_ARM_REG_PC, symbols["probe_start"])
        while not stopped and time.monotonic()-started < 180:
            uc.emu_start(uc.reg_read(UC_ARM_REG_PC), 0, count=50_000_000)
        if not stopped:
            failures.append("Zeitlimit nach 180 Sekunden")
    except Exception as error:
        failures.append(str(error))
    report = {"cpu":"ARM926", "keys":keys, "frames":frames, "wad_sha256":hashlib.sha256(wad).hexdigest(), "wad_size":len(wad), "wad_read_calls":reads, "wad_bytes_read":read_bytes, "heap_acquired":u32("probe_heap_end")-symbols["__heap_start"], "heap_start":hex(symbols["__heap_start"]), "stack":{"initial_sp":hex(stack_initial), "window_bottom":hex(stack_window_bottom), "window_size":stack_initial-stack_window_bottom, "lowest_written_address":hex(stack_lowest_write), "written_high_water":stack_initial-stack_lowest_write, "lowest_sp_on_write":hex(stack_lowest_sp), "sp_high_water_on_write":stack_initial-stack_lowest_sp, "write_events":stack_write_count}, "host_seconds":time.monotonic()-started, "simulated_ms":u32("probe_ticks"), "failures":failures, "scope":"Engine mit Testadapter, keine Electribe Firmware oder Hardware"}
    (args.output / "console.log").write_text("".join(logs))
    (args.output / "result.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
    if failures or len(frames) != args.frames or not any(frame["gamestate"] == 0 and frame["gametic"] > 2 and frame["lit_pixels"] > 0 for frame in frames) or (args.input and (len(keys) != 2 or frames[-1]["viewangle"] == frames[0]["viewangle"])):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
