# SPDX-License-Identifier: GPL-2.0-only
"""Measure native macro prerequisites without saving firmware, patterns or events.

research boots the original image and installs a RAM-only task-path experiment.
verify-research checks the combined metadata; an incomplete result exits nonzero.
This is no macro firmware implementation and does not access a physical device.
"""
import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/patch"), str(Path(__file__).parent)]
import macro_contract as contract

BASE = 0xC0000000
CODE, CODE_BYTES = contract.CODE, contract.CODE_BYTES
BUFFER, BUFFER_BYTES = contract.BUFFER, contract.BUFFER_BYTES
STATE, STATE_BYTES = contract.STATE_ADDRESS, contract.STATE_BYTES
CAPACITY = contract.CAPACITY
TIMER = 0x01F0D000
TIMER_HZ = 150_000_000
TIMER_PERIOD = 150_000_000
INPUT = 0xC002837C
CS_WAKE = 0xC002A558
PERIODIC_WAKE = 0xC002A7B8
FLAG_SET = 0xC0000E9C
TASK_TABLE = 0xC00A37A8
TIMER_ISR = 0xC0025798
TEMPO = 0xC0691518
CLOCK = 0xC0340380
TASK_NAMES = {2: "PeriodicTask", 3: "CsTask", 4: "UiTask", 10: "SeqTask"}


def payload(path):
    raw = Path(path).read_bytes()
    if len(raw) != 0x200100:
        raise ValueError("a complete firmware 2.02 VSB is required")
    return raw[0x100:]


class Addresses:
    def __init__(self, image, build, reference):
        import synthaddr
        self.build, self.derived = build, {}
        self.mapper = None
        if build == "synth":
            if reference is None:
                raise ValueError("synth research needs --reference-vsb with the original Sampler")
            from fwmap import FirmwareMap
            self.mapper = FirmwareMap(payload(reference), image, refine=True)
        self.recorded = synthaddr.table()

    def at(self, address, code=True):
        if self.build != "synth":
            return address
        if address in self.recorded:
            return self.recorded[address]
        target = self.mapper.at(address)
        if code and not self.mapper.same_code(address, target=target):
            raise ValueError(f"unverified synth code mapping at {address:#x}")
        self.derived[f"{address:#010x}"] = {"to": f"{target:#010x}",
                                            "method": "fwmap.same_code" if code else "fwmap.at"}
        return target


def patch_ownership(build):
    script = """
import fs from 'node:fs';
import {writtenAreas} from './src/ramspans.mjs';
const spans=[];
for(const f of fs.readdirSync('data/patches').filter(f=>f.endsWith('.json')).sort()){
 const p=JSON.parse(fs.readFileSync('data/patches/'+f));
 if(!p.builds?.includes(process.argv[1])) continue;
 for(const r of p.ram??[])spans.push({start:Number(r.at),end:Number(r.at)+r.length,owner:p.id});
 for(const r of writtenAreas(p))spans.push({...r,owner:p.id});
}
console.log(JSON.stringify(spans));
"""
    return json.loads(subprocess.check_output(["node", "--input-type=module", "-e", script, build], cwd=ROOT, text=True))


def ownership_digest(build):
    return hashlib.sha256(json.dumps(patch_ownership(build), sort_keys=True).encode()).hexdigest()


def source_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measurement_sources():
    paths = ["tools/emu/machine.py", "tools/emu/splash_cases.py", "tools/emu/firmware.py",
             "tools/emu/fat32.py", "tools/emu/sdcard.py", "tools/patch/arm.py", "tools/patch/fwmap.py",
             "tools/patch/synthaddr.py", "data/map/pattern.mjs", "src/ramspans.mjs"]
    paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "data/synth-map").glob("*.json"))]
    dependencies = {p: source_digest(ROOT / p) for p in paths}
    return dict(research_source_sha256=source_digest(__file__),
                contract_source_sha256=source_digest(contract.__file__),
                dependencies_sha256=hashlib.sha256(json.dumps(dependencies, sort_keys=True).encode()).hexdigest())


def memory_result(image, build):
    spans = patch_ownership(build)
    areas = contract.MEMORY_AREAS
    overlaps = [{"area": name, "owner": s["owner"]} for a, n, name in areas for s in spans
                if a < s["end"] and s["start"] < a + n]
    return dict(areas=[dict(at=f"{a:#010x}", length=n, what=name) for a, n, name in areas],
                no_overlap=not overlaps, overlaps=overlaps,
                erased=all(image[a - BASE:a - BASE + n] == b"\xff" * n for a, n, _ in areas),
                capacity=CAPACITY, buffer_bytes=BUFFER_BYTES, code_bytes=CODE_BYTES,
                ownership_sha256=ownership_digest(build),
                reservation="candidate, not yet installed in a firmware patch")


def probe_source(addresses):
    a = addresses.at
    return f"""
.equ S, {STATE:#x}
periodic:
    push {{r0-r12, lr}}
    .word 0xE10FC000
    push {{r12, lr}}
    ldr r4, =S
    ldr r0, [r4]
    cmp r0, #1
    bne periodic_end
    ldr r0, ={TIMER + 0x10:#x}
    ldr r0, [r0]
    ldr r2, [r4, #12]
    cmp r0, r2
    sub r0, r0, r2
    ldrlo r2, ={TIMER_PERIOD}
    addlo r0, r0, r2
    ldr r1, [r4, #8]
    cmp r0, r1
    blo periodic_end
    mov r0, #2
    str r0, [r4]
    mov r1, #2
    bl {a(FLAG_SET):#x}
    str r0, [r4, #16]
periodic_end:
    pop {{r12, lr}}
    .word 0xE128F00C
    pop {{r0-r12, lr}}
periodic_restored:
    ldr r3, [r4]
    b {a(PERIODIC_WAKE) + 4:#x}
cs:
    push {{r0-r12, lr}}
    .word 0xE10FC000
    push {{r12, lr}}
    ldr r4, =S
    ldr r0, [r4]
    cmp r0, #2
    bne cs_end
    mov r0, #3
    str r0, [r4]
    mov r0, #1
    str r0, [r4, #4]
    add r0, r4, #0x40
    ldr r5, [r4, #20]
    cmp r5, #8
    movhi r5, #8
    mov r6, #0
cs_message:
    cmp r6, r5
    bhs cs_messages_done
    add r0, r4, #0x40
    add r0, r0, r6, lsl #5
    bl {a(INPUT):#x}
    add r6, r6, #1
    b cs_message
cs_messages_done:
    mov r0, #0
    str r0, [r4, #4]
cs_end:
    pop {{r12, lr}}
    .word 0xE128F00C
    pop {{r0-r12, lr}}
cs_restored:
    ldr r3, [sp, #4]
    b {a(CS_WAKE) + 4:#x}
.pool
"""


def boot(image):
    import machine
    import fat32
    from sdcard import MemoryMedium, SDCard
    from splash_cases import Dev
    machine.SLICE = 2000
    dev = Dev(image, adapter=True)
    card = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(card)
    folder = {"hacktribe": "hacktribe", "stock": "electribe sampler", "synth": "electribe"}[dev.m.profile.build]
    volume.mkdir("/KORG/" + folder)
    volume.close()
    dev.m.insert_card(SDCard(MemoryMedium(card)))
    dev.run(1)
    if dev.screen()["number"] != 1:
        raise RuntimeError("main performance screen was not reached")
    return dev, card


def task_measurement(image, build, addresses):
    import unicorn
    import machine
    from tools.patch.arm import assemble
    dev, _ = boot(image)
    m, uc, A = dev.m, dev.m.uc, dev.m.A
    a = addresses.at
    def word(at):
        return struct.unpack("<I", uc.mem_read(at, 4))[0]
    def write(at, value):
        uc.mem_write(at, struct.pack("<I", value))
    table = a(TASK_TABLE, code=False)
    tasks = []
    for i in range(10):
        size, start = struct.unpack("<II", uc.mem_read(table + i * 32 + 16, 8))
        tasks.append((i + 1, start, start + size))
    def context():
        sp = uc.reg_read(A.UC_ARM_REG_SP)
        number = next((i for i, lo, hi in tasks if lo <= sp < hi), None)
        cpsr = uc.reg_read(A.UC_ARM_REG_CPSR)
        return dict(task=TASK_NAMES.get(number, str(number)), mode=cpsr & 31,
                    irq_enabled=not bool(cpsr & 0x80), sp=sp)
    samples, timers, calls = [], [], []
    stage = "physical"
    def on_input(*_):
        pointer = uc.reg_read(A.UC_ARM_REG_R0)
        samples.append(dict(ns=m.time_ns, message=list(uc.mem_read(pointer + 12, 5)),
                            origin=word(STATE + 4), **context()))
    def on_timer(*_):
        timers.append(m.time_ns)
    for point, handler in [(a(INPUT), on_input), (a(TIMER_ISR), on_timer)]:
        uc.hook_add(unicorn.UC_HOOK_CODE, handler, begin=point, end=point)
    for point in (0xC00700D8,):
        at = a(point)
        def on_call(uc, address, size, data):
            calls.append(dict(at=f"{address:#x}", stage=stage, **context()))
        uc.hook_add(unicorn.UC_HOOK_CODE, on_call, begin=at, end=at)
    uc.mem_write(STATE, bytes(STATE_BYTES))
    uc.ctl_flush_tb()
    dev.press(2, .03)
    begin = m.time_ns
    timers.clear()
    dev.run(1)
    window = (m.time_ns - begin) / 1e6
    timer_count = len(timers)
    messages = [[1, 1, 0, 3, 0], [2, 0, 0, 40, 0], [0, 10, 1, 0, 0],
                [4, 3, 0, 100, 1], [4, 3, 0, 0, 0], [0, 10, 0, 0, 0],
                [5, 1, 144, 1, 144], [0, 34, 0, 0, 0]]
    samples.clear()
    normal_latencies = []
    for msg in messages:
        at = m.time_ns
        m.send(msg)
        dev.run(.005)
        if samples:
            normal_latencies.append((samples[-1]["ns"] - at) / 1e6)
    physical = list(samples)
    ordered = [s["message"] for s in physical] == messages
    samples.clear()
    burst_start = m.time_ns
    for msg in messages:
        m.send(msg)
    dev.run(.01)
    normal_burst = list(samples)
    normal_burst_latencies = [(s["ns"] - burst_start) / 1e6 for s in normal_burst]
    dev.press(2, .03)
    dev.press(1, .03)
    dev.press(2, .03)
    baseline_stop = len(calls)
    code = assemble(probe_source(addresses), origin=CODE)
    if len(code.bytes) > CODE_BYTES:
        raise ValueError("research stub exceeds its candidate code area")
    uc.mem_write(CODE, code.bytes)
    for site, label, expected in ((PERIODIC_WAKE, "periodic", 0xE5943000),
                                   (CS_WAKE, "cs", 0xE59D3004)):
        target = a(site)
        if word(target) != expected:
            raise ValueError(f"unexpected task continuation at {target:#x}")
        branch = assemble(f"b {code.symbols[label]:#x}", origin=target).bytes
        uc.mem_write(target, branch)
    snapshots, preserved, wrapper_counts, wrapper_contexts = {}, [], {}, {}
    stack_high_water = {"cs": 0, "periodic": 0}
    regs = [A.UC_ARM_REG_R0 + i for i in range(13)] + [A.UC_ARM_REG_SP, A.UC_ARM_REG_LR, A.UC_ARM_REG_CPSR]
    for label in ("periodic", "cs", "periodic_restored", "cs_restored"):
        def on_wrapper(uc, address, size, label):
            wrapper_counts[label] = wrapper_counts.get(label, 0) + 1
            wrapper_contexts.setdefault(label, set()).add(context()["task"])
            key = label.split("_")[0]
            now = [uc.reg_read(r) for r in regs]
            if label.endswith("restored"):
                preserved.append(now == snapshots.pop(key, None))
            else:
                snapshots[key] = now
        at = code.symbols[label]
        uc.hook_add(unicorn.UC_HOOK_CODE, on_wrapper, user_data=label, begin=at, end=at)
    for task, lo, hi in tasks:
        if task not in (2, 3):
            continue
        key = "cs" if task == 3 else "periodic"
        def on_stack(uc, access, address, size, value, key):
            if key in snapshots:
                stack_high_water[key] = max(stack_high_water[key], snapshots[key][13] - address)
        uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, on_stack, user_data=key, begin=lo, end=hi - 1)
    uc.ctl_flush_tb()
    lateness, replayed = [], []
    for i in range(24):
        msg = messages[i % len(messages)]
        uc.mem_write(STATE + 0x4C, bytes(msg))
        write(STATE + 20, 1)
        due_ns = m.time_ns + (3 + i * .071) * 1e6
        write(STATE + 12, m.timer_count(TIMER, TIMER_HZ, False))
        write(STATE + 8, round((due_ns - m.time_ns) * TIMER_HZ / 1e9))
        write(STATE, 1)
        samples.clear()
        dev.run(.012)
        virtual = [s for s in samples if s["origin"] == 1]
        replayed.extend(virtual)
        if len(virtual) == 1:
            lateness.append((virtual[0]["ns"] - due_ns) / 1e6)
    burst = []
    for i, msg in enumerate(messages):
        uc.mem_write(STATE + 0x4C + i * 32, bytes(msg))
    write(STATE + 20, len(messages))
    write(STATE + 12, m.timer_count(TIMER, TIMER_HZ, False))
    write(STATE + 8, TIMER_HZ // 1000)
    due_ns = m.time_ns + 1e6
    write(STATE, 1)
    samples.clear()
    dev.run(.02)
    burst = [s for s in samples if s["origin"] == 1]
    burst_delays = [(s["ns"] - due_ns) / 1e6 for s in burst]
    burst_extra = [max(0, x - y) for x, y in zip(burst_delays, normal_burst_latencies)]
    exit_file = contract.encode("EXIT probe", [(0, bytes([0, 13, 1, 0, 0])),
                                              (1, bytes([0, 13, 0, 0, 0]))], 2, capacity=2)
    _, exit_events, _, _ = contract.decode(exit_file, capacity=2)
    controls = [[0, 1, 1, 0, 0], [0, 1, 0, 0, 0], [0, 2, 1, 0, 0], [0, 2, 0, 0, 0],
                [0, 1, 1, 0, 0], [0, 1, 0, 0, 0],
                [0, 9, 1, 0, 0], [0, 9, 0, 0, 0]] + [list(msg) for _, msg in exit_events]
    stage = "macro_controls"
    transport_transitions = []
    for msg in controls:
        transport_before = dev.u32(0xC06BC318)
        uc.mem_write(STATE + 0x4C, bytes(msg))
        write(STATE + 20, 1)
        write(STATE + 12, m.timer_count(TIMER, TIMER_HZ, False))
        write(STATE + 8, TIMER_HZ // 1000)
        write(STATE, 1)
        samples.clear()
        dev.run(.1)
        replayed.extend(s for s in samples if s["origin"] == 1)
        if msg[0] == 0 and msg[1] in (1, 2) and msg[2] == 1:
            transport_transitions.append(dict(key=msg[1], before=transport_before, after=dev.u32(0xC06BC318)))
    virtual_exit = any(s["message"] == [0, 13, 1, 0, 0] for s in replayed)
    samples.clear()
    stage = "physical_exit"
    dev.press(13, .02)
    physical_exit = any(s["message"] == [0, 13, 1, 0, 0] and s["origin"] == 0 for s in samples)
    safe = all(c["task"] == "UiTask" and c["mode"] == 19
               and c["irq_enabled"] for c in calls)
    return dict(harness=dict(slice=machine.SLICE, ns_per_instruction=machine.NS_PER_INSN,
                             unicorn=unicorn.__version__, python=platform.python_version(),
                             timer_irq_count=timer_count, timer_window_ms=window,
                             timestamp_uncertainty_us=10,
                             time_source="machine.time_ns; original 1 kHz handler counted"),
                input=dict(ordered=ordered, task=physical[0]["task"] if physical else None,
                           origin_separated=virtual_exit and physical_exit,
                           virtual_exit_source="GMAC encode/decode in RAM",
                           messages=len(physical), physical_latency_ms=normal_latencies,
                           physical_burst_latency_ms=normal_burst_latencies),
                replay=dict(task=replayed[0]["task"] if replayed else None,
                            irq_enabled=all(s["irq_enabled"] and s["mode"] == 19 for s in replayed),
                            extra_latency_ms=[round(max(0, t - min(normal_latencies)), 6) for t in lateness],
                            due_lateness_ms=[round(t, 6) for t in lateness],
                            registers_preserved=bool(preserved) and all(preserved),
                            stack_bytes=64, stack_evidence="16 saved words per wrapper; original callee usage observed separately",
                            observed_stack_bytes=stack_high_water,
                            burst_ordered=[s["message"] for s in burst] == messages
                            and [s["message"] for s in normal_burst] == messages,
                            burst_max_extra_latency_ms=max(burst_extra, default=None),
                            burst_due_lateness_ms=burst_delays,
                            max_messages_per_wake=8, unsafe_calls=0 if safe and calls else 1,
                            wrapper_counts=wrapper_counts, final_pending=word(STATE),
                            wrapper_tasks={key: sorted(value) for key, value in wrapper_contexts.items()},
                            final_timer=m.timer_count(TIMER, TIMER_HZ, False), final_due=word(STATE + 8),
                            normal_transport_calls=baseline_stop, observed_transport_calls=len(calls),
                            replay_ui_calls=sum(c["stage"] == "macro_controls" for c in calls),
                            transport_transitions=transport_transitions,
                            source="RAM-only PeriodicTask flag 2 wake, bounded CsTask dispatcher call"),
                asserts=m.asserts)


def tempo_measurement(image, addresses):
    from machine import UART1
    from tools.patch.arm import assemble
    dev, _ = boot(image)
    m, uc = dev.m, dev.m.uc
    a = addresses.at
    def word(address):
        return struct.unpack("<I", uc.mem_read(address, 4))[0]
    def ui_call(target, *args):
        uc.mem_write(CODE, assemble(f"b {target:#x}", origin=CODE).bytes)
        uc.ctl_flush_tb()
        return dev.call(CODE, *args)
    pattern = dev.u32(0xC033E6A4)
    clock = a(CLOCK, code=False)
    reads = []
    def period():
        return struct.unpack("<Q", uc.mem_read(clock + 8, 8))[0]
    for tempo in (1200, 1500):
        ui_call(a(0xC004A80C), pattern, tempo, 1)
        dev.run(.03)
        reads.append(dict(requested_tenths=tempo, display_tenths=word(a(TEMPO, code=False)),
                          generator_hundredths=word(clock + 0x2C), period_ps=period(),
                          effective_hundredths=contract.tempo_from_period(period())))
    internal = all(r["display_tenths"] == r["requested_tenths"]
                   and r["generator_hundredths"] == r["requested_tenths"] * 10 for r in reads)
    stopped = dev.u32(0xC06BC318) == 0 and internal
    glob = dev.u32(0xC033E6A0)
    uc.mem_write(glob + 44, b"\x03")
    ui_call(a(0xC009A860), 3)
    m.receive(UART1, bytes([0xFA]))
    dev.run(.03)
    begin = m.time_ns
    external_reads = []
    for i in range(48):
        m.run_until((begin + (i + 1) * 1e9 / 48) / 1e9)
        m.receive(UART1, bytes([0xF8]))
        dev.run(.002)
        external_reads.append(contract.tempo_from_period(period()))
    after = contract.tempo_from_period(period())
    dev.run(.3)
    silence = contract.tempo_from_period(period())
    return dict(internal=internal, stopped=stopped,
                external=len(set(external_reads[4:])) > 1
                and all(11000 <= t <= 13000 for t in external_reads[4:]),
                internal_reads=reads, external_hundredths=sorted(set(external_reads)),
                external_last_hundredths=after, after_silence_hundredths=silence,
                external_clock_loss_detected=False,
                display_after_external_tenths=word(a(TEMPO, code=False)),
                effective_address=f"{clock + 8:#010x}", source_unit="picoseconds per 1/2304 quarter",
                cached_generator_hundredths=word(clock + 0x2C), unit="0.01 BPM",
                method="UI setter and clock-mode callback in emulator; clock bytes through DIN UART",
                asserts=m.asserts)


def event_measurement(image, build):
    import fat32
    if build != "hacktribe":
        return dict(status="not run", reason="comparison cases specify the Hacktribe recorder")
    geometry_script = """
import p from './data/map/pattern.mjs';
console.log(JSON.stringify(Object.fromEntries(['sample','level','mute'].map(id=>{
 const f=p.fields.find(f=>f.id==='part.'+id);
 return [id,{offset:f.where.offset,stride:f.repeat[0].stride}];
}))));
"""
    geometry = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", geometry_script], cwd=ROOT, text=True))
    def main_screen(dev):
        for _ in range(10):
            if dev.screen()["number"] == 1:
                return
            dev.press(13, .15)
        raise RuntimeError("could not leave the recorder page")
    def event_menu(dev, arm=True):
        dev.press(9)
        for _ in range(5):
            if dev.screen()["number"] != 1:
                break
            dev.press(9)
        for _ in range(9):
            if dev.screen()["number"] in (10, 11):
                break
            dev.m.press(10, True)
            dev.run(.03)
            dev.press(12, .1)
            dev.m.press(10, False)
            dev.run(.05)
        if dev.screen()["number"] == 10:
            dev.press(9)
        if dev.screen()["number"] != 11:
            raise RuntimeError("Event Recorder menu was not reached")
        if arm:
            dev.press(9)
    def files(card):
        volume = fat32.Volume(card)
        def walk(path):
            found = []
            for entry in volume.listdir(path):
                if entry.name in (".", ".."):
                    continue
                child = path.rstrip("/") + "/" + entry.name
                if entry.is_dir:
                    found.extend(walk(child))
                elif entry.name.lower().endswith(".e2sev"):
                    found.append(child)
            return found
        paths = walk("/")
        return volume.read(paths[0]) if len(paths) == 1 else b""
    def state(dev):
        pat, led = dev.u32(0xC033E6A4), dev.u32(0xC0345A1C)
        return dict(screen=dev.screen()["number"], osc=struct.unpack("<H", dev.read(pat + 4 + geometry["sample"]["offset"], 2))[0],
                    level=dev.read(pat + 4 + geometry["level"]["offset"], 1)[0],
                    selected_part=dev.u32(led + 0xB60), pad_mode=dev.u32(led + 0xB58),
                    selected_pattern=dev.u32(0xC06B2420),
                    playing_pattern=dev.u32(dev.u32(0xC03487E8) + 0x318),
                    mute4=dev.read(pat + 4 + geometry["mute"]["offset"] + 3 * geometry["mute"]["stride"], 1)[0])
    cases = {
        "baseline": [], "encoder": [[1, 1, 0, 3, 0]], "knob": [[2, 0, 0, 40, 0]],
        "mode": [[0, 21, 1, 0, 0], [0, 21, 0, 0, 0]],
        "menu": [[0, 9, 1, 0, 0], [0, 9, 0, 0, 0], [0, 12, 1, 0, 0], [0, 12, 0, 0, 0]],
        "part": [[0, 15, 1, 0, 0], [0, 15, 0, 0, 0]],
        "pattern": [[1, 0, 0, 1, 0]],
        "mute": [[0, 16, 1, 0, 0], [0, 16, 0, 0, 0], [4, 3, 0, 100, 1], [4, 3, 0, 0, 0]],
    }
    rows, baseline, encoder_recording = [], None, None
    for name, messages in cases.items():
        dev, card = boot(image)
        event_menu(dev)
        dev.press(2, 1)
        main_screen(dev)
        before = state(dev)
        pattern = dev.read(dev.u32(0xC033E6A4) + 4, 0x4000)
        start = dev.m.time_ns
        for message in messages:
            dev.m.send(message)
            dev.run(.05)
        dev.m.run_until(start / 1e9 + 1.5)
        after = state(dev)
        dev.press(1, 1)
        recording = files(card)
        if not recording:
            raise RuntimeError(f"Event Recorder did not save {name}")
        if baseline is None:
            baseline = recording
        if name == "encoder":
            encoder_recording = recording
        rows.append(dict(case=name, before=before, after=after, file_bytes=len(recording),
                         changed_bytes=sum(x != y for x, y in zip(recording, baseline))
                         + abs(len(recording) - len(baseline)),
                         contains_start_pattern=pattern in recording, asserts=dev.m.asserts))
        print(json.dumps(dict(progress="event_recorder", case=name)), file=sys.stderr, flush=True)
    dev, card = boot(image)
    volume = fat32.Volume(card)
    volume.write("/KORG/hacktribe/e_001.e2sev", encoder_recording)
    volume.close()
    dev.m.send([1, 1, 0, 20, 0])
    dev.run(.3)
    before = state(dev)
    event_menu(dev, arm=False)
    dev.press(12, .2)
    dev.press(9, .3)
    dev.press(9, .3)
    dev.turn(1, .1)
    dev.press(9, .3)
    dev.turn(1, .1)
    dev.press(9, .3)
    dev.press(2, .2)
    initial = state(dev)
    dev.run(4)
    final = state(dev)
    restored = before["osc"] == 20 and initial["osc"] == 0 and final["osc"] == 20
    result = dict(status="measured", cases=rows,
                playback=dict(before=before, initial=initial, final=final,
                              loads_and_restores_snapshot=restored, asserts=dev.m.asserts),
                valid=restored and not dev.m.asserts
                and all(r["contains_start_pattern"] and not r["asserts"] for r in rows))
    result["comparison_errors"] = contract.recorder_errors(result)
    result["valid"] = result["valid"] and not result["comparison_errors"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    research = sub.add_parser("research")
    research.add_argument("--vsb", required=True)
    research.add_argument("--build", choices=contract.BUILDS, required=True)
    research.add_argument("--reference-vsb")
    research.add_argument("--report", default=str(ROOT / "docs/messungen/2026-10-25-makro-grundlagen.json"))
    research.add_argument("--sections", default="input,tempo,memory,event",
                          help="comma separated input,tempo,memory,event")
    verify = sub.add_parser("verify-research")
    verify.add_argument("--report", required=True)
    args = parser.parse_args()
    if args.command == "verify-research":
        report = json.loads(Path(args.report).read_text())
        sources = measurement_sources()
        errors = contract.research_errors(report, sources=sources,
                                          ownership={b: ownership_digest(b) for b in contract.BUILDS})
        print(json.dumps(dict(status="FAIL" if errors else "PASS", errors=errors), indent=2))
        return bool(errors)
    from firmware import identify
    image = payload(args.vsb)
    actual = identify(image).build
    if actual != args.build:
        raise ValueError(f"expected {args.build}, firmware identifies as {actual}")
    addresses = Addresses(image, actual, args.reference_vsb)
    path = Path(args.report)
    report = json.loads(path.read_text()) if path.exists() else dict(schema=1, builds=[])
    result = next((r for r in report["builds"] if r["build"] == actual), {})
    digest = hashlib.sha256(image).hexdigest()
    if result and result["firmware_sha256"] != digest:
        raise ValueError("existing research uses a different firmware image")
    result.update(build=actual, firmware_sha256=digest, measured_at=datetime.now(timezone.utc).isoformat())
    sources = measurement_sources()
    result.update(sources)
    sections = args.sections.split(",")
    if set(sections) - {"input", "tempo", "memory", "event"}:
        raise ValueError("unknown research section")
    if "memory" in sections:
        result["memory"] = memory_result(image, actual)
    if "input" in sections:
        result.update(task_measurement(image, actual, addresses))
    if "tempo" in sections:
        result["tempo"] = tempo_measurement(image, addresses)
    if "event" in sections:
        result["event_recorder"] = event_measurement(image, actual)
    if measurement_sources() != sources:
        raise ValueError("research sources changed during the measurement")
    for name in sections:
        result.setdefault("section_sources", {})[name] = dict(sources, measured_at=result["measured_at"])
    result.setdefault("address_derivations", {}).update(addresses.derived)
    result.setdefault("event_recorder", dict(status="not measured in this run"))
    report["builds"] = [r for r in report["builds"] if r["build"] != actual] + [result]
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result.get("asserts") or result.get("tempo", {}).get("asserts"))


if __name__ == "__main__":
    sys.exit(main())
