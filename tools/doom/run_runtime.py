#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bootet den SD-Lader samt Original-Doom ausschließlich im Firmwareemulator."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/emu")]
from tools.doom.boot_probe import TASKS, SAMPLER
from tools.emu.machine import Machine, load_flash
from tools.emu.sdcard import MemoryMedium, SDCard
from tools.doom.artifacts import external_output
import unicorn
import fat32

SHARED = json.loads((Path(__file__).parent / "layout.json").read_text())["shared"]
ENGINE, END = 0xC1000000, 0xC1800000
FIELDS = "magic version stage error frames gametic gamestate viewangle file_reads bytes_read heap_used key_events last_key last_down console_head exit_status clock_millis".split()


class ObservedMedium(MemoryMedium):
    def __init__(self, data):
        super().__init__(data, read_only=True)
        self.write_calls = 0
        self.initial_sha256 = hashlib.sha256(data).hexdigest()
    def write(self, lba, block):
        self.write_calls += 1
        return super().write(lba, block)


class ObservedCard(SDCard):
    def __init__(self, medium):
        super().__init__(medium)
        self.write_commands = 0
    def command(self, idx, arg):
        if idx in (24, 25, 38): self.write_commands += 1
        return super().command(idx, arg)


def state(machine):
    values = struct.unpack("<17I", machine.uc.mem_read(SHARED, 68))
    result = dict(zip(FIELDS, values))
    if result["magic"] == 0x4D4F4F44:
        raw = bytes(machine.uc.mem_read(SHARED + 68, 2048))
        head = result["console_head"]
        raw = raw[:head] if head <= 2048 else raw[head % 2048:] + raw[:head % 2048]
        result["console"] = raw.decode("utf8", errors="replace")
    return result


def inspect_engine(machine, inspection):
    if not inspection: return None
    symbols, layout=inspection["symbols"],inspection["layout"]
    unsigned=lambda address:struct.unpack("<I",machine.uc.mem_read(address,4))[0]
    signed=lambda address:struct.unpack("<i",machine.uc.mem_read(address,4))[0]
    sized=lambda address,size:int.from_bytes(machine.uc.mem_read(address,size),"little")
    result={name:unsigned(symbols[symbol]) for name,symbol in
            [("menu","menuactive"),("current_menu","currentMenu"),("episode","gameepisode"),("map","gamemap"),("leveltime","leveltime"),("message","messageToPrint"),("message_needs_input","messageNeedsInput")]}
    player=symbols["players"]+unsigned(symbols["consoleplayer"])*layout["player_size"]
    actor=unsigned(player+layout["player_mo_offset"])
    result["menu"]=sized(symbols["menuactive"],layout["boolean_size"])
    result["message_needs_input"]=sized(symbols["messageNeedsInput"],layout["boolean_size"])
    result.update(health=signed(player+layout["player_health_offset"]),ammo_clip=signed(player+layout["player_ammo_offset"]),weapon=sized(player+layout["player_readyweapon_offset"],layout["player_readyweapon_size"]),usedown=sized(player+layout["player_usedown_offset"],layout["player_usedown_size"]))
    if ENGINE<=actor<END:
        result.update(x=signed(actor+layout["mobj_x_offset"]),y=signed(actor+layout["mobj_y_offset"]))
    else: result.update(x=None,y=None)
    return result


def write_frame(path, frame):
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
    rows=[]
    for y in range(64):
        row=b"\0"+b"".join(bytes([0 if frame[(y//8)*128+x] & (1<<(y%8)) else 255])*6 for x in range(128))
        rows.extend([row]*6)
    header=struct.pack(">IIBBBBB",768,384,8,0,0,0,0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",header)+chunk(b"IDAT",zlib.compress(b"".join(rows)))+chunk(b"IEND",b""))


BEFORE_MOUNT={"globals","patterns"}       # what the firmware has done before the loader runs


def run(image, flash, program, wad, seconds=5.0, held=0x408, fault=None, output=None, card_mib=64, inspection=None, scenario="turn"):
    if output: output=external_output(output)
    machine = Machine(image[0x100:], flash)
    machine.held = held
    files = {"/KORG/blechtribe/Doom/doom.bin": program,
             "/KORG/blechtribe/Doom/doom.wad": wad}
    if fault == "missing-program": del files["/KORG/blechtribe/Doom/doom.bin"]
    if fault == "missing-wad": del files["/KORG/blechtribe/Doom/doom.wad"]
    if fault == "bad-wad": files["/KORG/blechtribe/Doom/doom.wad"] = b"INVALID-WAD"
    if fault == "corrupt-program":
        corrupt = bytearray(program); corrupt[0] ^= 1
        files["/KORG/blechtribe/Doom/doom.bin"] = bytes(corrupt)
    if fault == "short-program": files["/KORG/blechtribe/Doom/doom.bin"] = program[:-1]
    if card_mib not in (64,512): raise ValueError("Testkarte muss 64 oder 512 MiB haben")
    if fault != "no-card":
        card_data=fat32.format_image(card_mib*1024*1024,volume_id=0xD00D2026)
        volume=fat32.Volume(card_data)
        for path,data in files.items(): volume.write(path,data)
        volume.close()
        medium=ObservedMedium(card_data)
    else: medium=None
    card = ObservedCard(medium) if medium else None
    if card: machine.insert_card(card)
    tasks, sampler, entered = set(), set(), []
    for address, task in TASKS.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u,a,s,d: tasks.add(d), task, begin=address, end=address)
    for address, name in SAMPLER.items():
        machine.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u,a,s,d: sampler.add(d), name, begin=address, end=address)
    def entry(uc, address, size, data):
        if not entered:
            entered.append(dict(seconds=machine.time_ns/1e9, sp=machine.reg(machine.A.UC_ARM_REG_SP),
                                r0=machine.reg(machine.A.UC_ARM_REG_R0),
                                tick=struct.unpack("<I", uc.mem_read(0xC06A2930,4))[0]))
    machine.uc.hook_add(unicorn.UC_HOOK_CODE, entry, begin=ENGINE, end=ENGINE)
    guard_low, guard_high = b"DoomGuardLow"*4, b"DoomGuardHigh"*4
    machine.uc.mem_write(ENGINE-len(guard_low), guard_low)
    machine.uc.mem_write(END, guard_high)
    stack_guard = b"DoomStackGuard"*4
    machine.uc.mem_write(0xC17F0000, stack_guard)
    lowest_stack = [END]
    def stack_write(uc, access, address, size, value, data):
        lowest_stack[0] = min(lowest_stack[0], address)
    machine.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, stack_write, begin=0xC17F0000, end=END-1)
    history, events, error = [], [], None
    first_playing = None
    last_progress = -10
    controller=None
    if scenario=="controls":
        if not inspection: raise ValueError("Bedientest braucht Symbole und compilererzeugtes Layout")
        from tools.doom.controls_scenario import ControlsScenario
        controller=ControlsScenario()
    began = time.monotonic()
    try:
        while machine.time_ns < seconds*1e9 and not machine.asserts and machine.powered:
            machine.run_until(min(seconds, machine.time_ns/1e9+0.1))
            current = state(machine)
            if machine.time_ns/1e9 >= last_progress+10:
                last_progress=machine.time_ns/1e9
                print(f"{last_progress:.1f}s stage={current['stage']} frames={current['frames']} WAD={current['bytes_read']}B",file=sys.stderr,flush=True)
            if current["magic"] != 0x4D4F4F44: continue
            history.append({k:current[k] for k in ["stage","error","frames","gametic","viewangle","key_events","clock_millis"]} | {"seconds":machine.time_ns/1e9})
            if current["stage"] & 0x80000000: break
            if controller:
                engine=inspect_engine(machine,inspection) if current["stage"] in (5,6) else None
                if controller.step(machine,current,engine): break
                continue
            if current["stage"] == 5 and current["gametic"] >= 5 and not events:
                first_playing = dict(current)
                machine.send([0,12,1,0,0]); events.append(dict(frame=current["frames"], gametic=current["gametic"], down=True, index=12))
            elif len(events)==1 and current["gametic"] >= events[0]["gametic"]+8:
                machine.send([0,12,0,0,0]); events.append(dict(frame=current["frames"], gametic=current["gametic"], down=False, index=12))
            if current["stage"] == 5 and len(events)==2 and current["key_events"] >= 2 and current["gametic"] >= events[-1]["gametic"]+5: break
    except Exception as exc:
        error = repr(exc)
    current = state(machine)
    if controller and not machine.powered:
        controller.step(machine,current,inspect_engine(machine,inspection))
    lcd = bytes(b for row in machine.fb for b in row)
    report = dict(state=current, history=history, events=events, engine_entry=entered,
                  tasks=sorted(tasks), sampler=sorted(sampler), asserts=machine.asserts,
                  error=error, pc=hex(machine.reg(machine.A.UC_ARM_REG_PC)),
                  sp=hex(machine.reg(machine.A.UC_ARM_REG_SP)),
                  cpu={name:hex(machine.uc.reg_read(getattr(machine.A,"UC_ARM_REG_"+name))) for name in ["CPSR","SPSR","PC","LR","SP"]},
                  seconds=machine.time_ns/1e9, wall_seconds=time.monotonic()-began,
                  kernel_tick=struct.unpack("<I",machine.uc.mem_read(0xC06A2930,4))[0],
                  task1_stack=list(struct.unpack("<2I",machine.uc.mem_read(0xC00A37A8+16,8))),
                  sd_write_calls=medium.write_calls if medium else 0,
                  sd_write_commands=card.write_commands if card else 0,
                  sd_unchanged=hashlib.sha256(medium.data).hexdigest()==medium.initial_sha256 if medium else True,
                  card_mib=card_mib,
                  cluster_bytes=fat32.geometry(card_mib*1024*1024)[0]*512,
                  stack_high_water=END-lowest_stack[0],
                  engine=inspect_engine(machine,inspection) if inspection and current["stage"] in (5,6) else None,
                  powered=machine.powered,
                  leds=dict(machine.leds),
                  first_playing=first_playing,
                  guards_ok=bytes(machine.uc.mem_read(ENGINE-len(guard_low),len(guard_low)))==guard_low and bytes(machine.uc.mem_read(END,len(guard_high)))==guard_high and bytes(machine.uc.mem_read(0xC17F0000,len(stack_guard)))==stack_guard,
                  lcd_sha256=hashlib.sha256(lcd).hexdigest(),
                  framebuffer_nonzero=sum(x.bit_count() for x in lcd),
                  screen_manager=hex(struct.unpack("<I",machine.uc.mem_read(0xC03404C0,4))[0]))
    # The loader runs right after the firmware has mounted the card: by then it has read its globals and patterns from flash and
    # made its screen manager, nothing else of the sampler (no samples, no other task than 1 and 8).
    common_ok=not error and not machine.asserts and sampler<=BEFORE_MOUNT and tasks=={1,8} and report["guards_ok"] and report["sd_write_calls"]==0 and report["sd_write_commands"]==0 and report["sd_unchanged"]
    report["ok"] = common_ok and current["magic"]==0x4D4F4F44 and current["stage"]==5 and current["gametic"]>0 and current["key_events"]>=2 and first_playing is not None and current["viewangle"]!=first_playing["viewangle"] and 0<report["framebuffer_nonzero"]<8192
    if controller:
        report.update(scenario="controls",controls=dict(checks=controller.checks,events=controller.events,states=controller.states),game_frame_pixels=sum(x.bit_count() for x in controller.game_frame) if controller.game_frame else 0)
        report["ok"]=common_ok and bool(controller.checks) and all(c["ok"] for c in controller.checks) and not machine.powered and current["stage"]==6 and current["error"]==0 and 0<report["game_frame_pixels"]<8192
    if output:
        output.mkdir(parents=True, exist_ok=True)
        (output/"result.json").write_text(json.dumps(report,indent=2)+"\n")
        (output/"frame.bin").write_bytes(lcd)
        if controller and controller.game_frame: (output/"game-frame.bin").write_bytes(controller.game_frame)
        if controller and controller.initial_frame:
            (output/"initial-play.bin").write_bytes(controller.initial_frame)
            write_frame(output/"initial-play.png", controller.initial_frame)
        write_frame(output/"frame.png",lcd)
        if controller and controller.game_frame: write_frame(output/"game-frame.png",controller.game_frame)
    return report


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--program",type=Path,required=True)
    p.add_argument("--wad",type=Path,required=True)
    p.add_argument("--flash",type=Path,nargs="+",required=True)
    p.add_argument("--seconds",type=float,default=5.0)
    p.add_argument("--card-mib",type=int,choices=[64,512],default=64)
    p.add_argument("--scenario",choices=["turn","controls"],default="turn")
    p.add_argument("--held",type=lambda s:int(s,0),default=0x408)
    p.add_argument("--fault",choices=["no-card","missing-program","missing-wad","bad-wad","corrupt-program","short-program"])
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    inspection=None
    if a.program.with_name("layout.json").exists():
        symbols={parts[2]:int(parts[0],16) for line in a.program.with_name("symbols.txt").read_text().splitlines() if len(parts:=line.split())==3}
        inspection=dict(symbols=symbols,layout=json.loads(a.program.with_name("layout.json").read_text()))
    result=run(a.image.read_bytes(),load_flash(a.flash),a.program.read_bytes(),a.wad.read_bytes(),a.seconds,a.held,a.fault,a.output,a.card_mib,inspection,a.scenario)
    print(json.dumps(result,indent=2))
    sys.exit(0 if result["ok"] else 1)
